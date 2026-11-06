# -*- coding: utf-8 -*-
"""图像操作画布：截图、网格、OCR 文字框、按图像坐标点击/输入。

给视觉模型用的最小工具集：
  - shot 截一块窗口或显示器，带坐标网格和可选的 OCR 框；
  - 每个截图旁边写一份 .json，记下截图区域在屏幕上的位置；
  - click 用图片里的坐标，按 .json 映射回屏幕坐标，先校验窗口没挪动；
  - type/key/scroll/drag 走 Win32，输入中文用剪贴板粘贴。

所有会动鼠标键盘的命令都要 --yes 才执行，默认只回显将要做什么。

用法：
    python specialty/vision/vision.py shot --window "记事本" --out shot.png --grid --ocr
    python specialty/vision/vision.py click --shot shot.json --x 320 --y 180 --yes
    python specialty/vision/vision.py type --text "你好" --yes
    python specialty/vision/vision.py key --combo ctrl+a --yes
    python specialty/vision/vision.py scroll --dy -3 --yes
    python specialty/vision/vision.py find --image shot.png --template icon.png
"""
from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "screen"))

import screen  # noqa: E402  (同目录的截图与窗口工具)

GRID_STEP = 100
_engine = None


@dataclass
class Box:
    text: str
    score: float
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


def grid_lines(width: int, height: int, step: int = GRID_STEP) -> tuple[list[int], list[int]]:
    return list(range(0, width + 1, step)), list(range(0, height + 1, step))


def box_from_points(points: list[list[float]], text: str, score: float) -> Box:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return Box(text=text, score=score, left=int(min(xs)), top=int(min(ys)),
               right=int(max(xs)), bottom=int(max(ys)))


def ocr_image(image) -> list[Box]:
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    result, _ = _engine(image)
    boxes: list[Box] = []
    for item in result or []:
        points, text, score = item[0], item[1], float(item[2])
        boxes.append(box_from_points(points, str(text), score))
    return boxes


def draw_grid(image, step: int = GRID_STEP):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    width, height = image.size
    xs, ys = grid_lines(width, height, step)
    for x in xs:
        draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 120), width=1)
        draw.text((x + 2, 2), str(x), fill=(200, 0, 0))
    for y in ys:
        draw.line([(0, y), (width, y)], fill=(0, 0, 255, 120), width=1)
        draw.text((2, y + 1), str(y), fill=(0, 0, 200))
    return image


def draw_boxes(image, boxes: list[Box]):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    for index, box in enumerate(boxes):
        draw.rectangle([box.left, box.top, box.right, box.bottom], outline=(0, 160, 0), width=2)
        cx, cy = box.center
        draw.text((cx, cy), f"{index}", fill=(0, 120, 0))
    return image


_sct = None


def grab(bbox: tuple[int, int, int, int], *, fast: bool = True):
    """截一块区域。fast 用 mss（约 30–60fps），失败退回 PIL。"""
    global _sct
    if fast:
        try:
            import mss
            from PIL import Image

            if _sct is None:
                _sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
            shot = _sct.grab({"left": bbox[0], "top": bbox[1],
                              "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]})
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        except Exception:
            pass
    from PIL import ImageGrab

    return ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")


def capture(source: argparse.Namespace):
    if getattr(source, "virtual", False):
        source.monitor = screen.virtual_monitor_index(getattr(source, "virtual_index", 1))
    if source.window or getattr(source, "hwnd", None):
        found = screen.resolve_window(title=source.window, hwnd=getattr(source, "hwnd", None))
        if not found:
            raise SystemExit(f"没找到窗口（title={source.window!r} hwnd={getattr(source, 'hwnd', None)}）")
        bbox = screen.client_bbox(found.hwnd)
        window = found.title
        source.hwnd_used = found.hwnd
    else:
        monitors = screen.list_monitors()
        if not 1 <= source.monitor <= len(monitors):
            raise SystemExit(f"显示器编号超出范围 1–{len(monitors)}")
        bbox = monitors[source.monitor - 1].bbox
        window = f"monitor:{source.monitor}"
    return grab(bbox), bbox, window


def pick_box(boxes: list[Box], text: str) -> Box | None:
    needle = text.strip()
    if not needle:
        return None
    for box in boxes:
        if box.text.strip() == needle:
            return box
    for box in boxes:
        if needle in box.text:
            return box
    return None


def diff_images(before, after, threshold: int = 24) -> dict[str, Any]:
    """返回变化像素比例和变化区域，用来判断画面有没有动。"""
    import numpy as np

    a = np.asarray(before.convert("RGB"), dtype=np.int16)
    b = np.asarray(after.convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        raise SystemExit("两张图尺寸不一致")
    changed = np.abs(a - b).max(axis=2) > threshold
    ratio = float(changed.mean())
    box = None
    if changed.any():
        ys, xs = np.where(changed)
        box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    return {"changedRatio": round(ratio, 5), "box": box,
            "size": [int(a.shape[1]), int(a.shape[0])]}


def burst(bbox: tuple[int, int, int, int], count: int, interval: float,
          out_dir: Path, prefix: str = "frame") -> dict[str, Any]:
    """连拍，用于看动画/游戏的变化；返回帧文件和实际帧率。"""
    import time

    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    start = time.time()
    for index in range(max(1, count)):
        image = grab(bbox)
        path = out_dir / f"{prefix}_{index:03d}.png"
        image.save(str(path))
        files.append(str(path))
        if interval > 0:
            time.sleep(interval)
    elapsed = max(1e-6, time.time() - start)
    return {"frames": files, "count": len(files), "seconds": round(elapsed, 3),
            "fps": round(len(files) / elapsed, 1)}


def watch(bbox: tuple[int, int, int, int], seconds: float, fps: float,
          out_dir: Path | None = None, *, threshold: int = 24,
          motion_ratio: float = 0.01) -> dict[str, Any]:
    """按帧率看一段时间，报告画面变化；只保存明显变化的帧。"""
    import time

    interval = 1.0 / max(1.0, fps)
    deadline = time.time() + max(0.0, seconds)
    previous = None
    changes: list[float] = []
    saved: list[str] = []
    frames = 0
    start = time.time()
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    while time.time() < deadline:
        image = grab(bbox)
        frames += 1
        if previous is not None:
            diff = diff_images(previous, image, threshold)
            changes.append(diff["changedRatio"])
            if out_dir and diff["changedRatio"] >= motion_ratio and len(saved) < 30:
                path = out_dir / f"motion_{len(saved):03d}.png"
                image.save(str(path))
                saved.append(str(path))
        previous = image
        time.sleep(interval)
    elapsed = max(1e-6, time.time() - start)
    return {"frames": frames, "seconds": round(elapsed, 3), "fps": round(frames / elapsed, 1),
            "maxChange": round(max(changes), 5) if changes else 0.0,
            "avgChange": round(sum(changes) / len(changes), 5) if changes else 0.0,
            "saved": saved}


def write_shot(image, bbox, source: str, out: Path, *, grid: bool, ocr: bool) -> dict[str, Any]:
    # 先识别干净画面，再叠加网格和框，避免网格线干扰 OCR
    boxes: list[Box] = ocr_image(image) if ocr else []
    if grid:
        image = draw_grid(image)
    if boxes:
        image = draw_boxes(image, boxes)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out))
    sidecar = {
        "file": str(out),
        "bbox": list(bbox),
        "width": image.width,
        "height": image.height,
        "source": source,
        "ocr": [
            {"index": i, "text": b.text, "score": round(b.score, 3),
             "center": list(b.center), "box": [b.left, b.top, b.right, b.bottom]}
            for i, b in enumerate(boxes)
        ],
    }
    out.with_suffix(".json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sidecar


def load_sidecar(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"找不到截图信息 {path}，先运行 shot")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_shot(sidecar: dict[str, Any], *, max_change: float = 0.35) -> dict[str, Any]:
    """点击前核对画面是否还和截图一致；变化过大说明内容已经过期。"""
    from PIL import Image

    stored = Path(sidecar["file"])
    if not stored.exists():
        return {"ok": True, "reason": "no-image", "changedRatio": 0.0}
    before = Image.open(stored).convert("RGB")
    current = grab(tuple(sidecar["bbox"]))
    if before.size != current.size:
        return {"ok": False, "reason": "size", "changedRatio": 1.0}
    diff = diff_images(before, current)
    return {"ok": diff["changedRatio"] <= max_change,
            "changedRatio": diff["changedRatio"], "reason": "pixels"}


def wait_stable(bbox: tuple[int, int, int, int], *, interval: float = 0.25,
                stable: int = 2, timeout: float = 10.0, threshold: int = 24,
                max_change: float = 0.01) -> dict[str, Any]:
    """等画面连续 stable 帧几乎不变，返回最后一帧。"""
    import time

    deadline = time.time() + max(0.1, timeout)
    previous = None
    calm = 0
    frames = 0
    while time.time() < deadline:
        image = grab(bbox)
        frames += 1
        if previous is not None:
            ratio = diff_images(previous, image, threshold)["changedRatio"]
            calm = calm + 1 if ratio <= max_change else 0
            if calm >= stable:
                return {"ok": True, "frames": frames, "waited": round(time.time() - (deadline - timeout), 2)}
        previous = image
        time.sleep(interval)
    return {"ok": False, "frames": frames, "timeout": timeout}


def map_point(sidecar: dict[str, Any], x: int, y: int) -> tuple[int, int]:
    left, top, right, bottom = sidecar["bbox"]
    if not (0 <= x < sidecar["width"] and 0 <= y < sidecar["height"]):
        raise SystemExit(f"坐标 ({x},{y}) 超出截图范围 {sidecar['width']}x{sidecar['height']}")
    return left + int(x), top + int(y)


def bbox_changed(sidecar: dict[str, Any], *, tolerance: int = 4) -> bool:
    """窗口挪动过就返回 True；window:/hwnd: 来源都能核对。"""
    source = sidecar.get("source", "")
    if source.startswith("hwnd:"):
        found = screen.resolve_window(hwnd=int(source[len("hwnd:"):]))
    elif source.startswith("window:"):
        found = screen.find_window(source[len("window:"):])
    else:
        return False
    if not found:
        return True
    current = screen.client_bbox(found.hwnd)
    return any(abs(a - b) > tolerance for a, b in zip(current, sidecar["bbox"]))


def move_cursor(x: int, y: int) -> None:
    import win32api

    win32api.SetCursorPos((int(x), int(y)))


def mouse_click(x: int, y: int, *, button: str = "left", double: bool = False) -> None:
    import time

    import win32api
    import win32con

    down, up = ((win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP)
                if button == "left" else
                (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP))
    win32api.SetCursorPos((int(x), int(y)))
    for _ in range(2 if double else 1):
        win32api.mouse_event(down, 0, 0, 0, 0)
        win32api.mouse_event(up, 0, 0, 0, 0)
        if double:
            time.sleep(0.08)


def mouse_drag(x1: int, y1: int, x2: int, y2: int) -> None:
    import win32api
    import win32con

    win32api.SetCursorPos((int(x1), int(y1)))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    steps = 12
    for i in range(1, steps + 1):
        win32api.SetCursorPos((int(x1 + (x2 - x1) * i / steps), int(y1 + (y2 - y1) * i / steps)))
        time.sleep(0.02)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
}
for _i in range(1, 13):
    VK[f"f{_i}"] = 0x6F + _i
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)


def parse_combo(combo: str) -> list[int]:
    keys = [part.strip().lower() for part in combo.replace("+", " ").split() if part.strip()]
    if not keys:
        raise SystemExit("按键组合为空")
    codes: list[int] = []
    for key in keys:
        if key not in VK:
            raise SystemExit(f"不认识的键 {key!r}")
        codes.append(VK[key])
    return codes


def key_combo(combo: str) -> None:
    import win32api
    import win32con

    codes = parse_combo(combo)
    for code in codes:
        win32api.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)


def type_text(text: str) -> None:
    import win32clipboard
    import win32con

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
    key_combo("ctrl+v")


def scroll(dy: int) -> None:
    import win32api
    import win32con

    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, int(dy) * 120, 0)


def _imread(path: Path):
    """cv2.imread 读不了中文路径，改用 imdecode。"""
    import cv2
    import numpy as np

    data = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def find_template(image_path: Path, template_path: Path, threshold: float = 0.85) -> dict[str, Any]:
    import cv2

    image = _imread(image_path)
    template = _imread(template_path)
    if image is None or template is None:
        raise SystemExit("图片读不出来")
    if float(template.std()) < 1e-6:
        raise SystemExit("模板几乎是纯色，没有纹理，换一张带图案的截图")
    result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    score = float(score)
    height, width = template.shape[:2]
    if score < threshold:
        return {"found": False, "score": round(float(score), 3)}
    center = (location[0] + width // 2, location[1] + height // 2)
    return {"found": True, "score": round(float(score), 3), "center": list(center),
            "box": [location[0], location[1], location[0] + width, location[1] + height]}


def ollama_ask(image_path: Path, prompt: str, *, model: str = "qwen2.5vl:3b",
               host: str = "http://127.0.0.1:11434", timeout: float = 120.0) -> dict[str, Any]:
    """把截图交给本地 Ollama 视觉模型，返回它的回答。"""
    import base64
    import urllib.request

    data = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    payload = {"model": model, "prompt": prompt, "images": [data], "stream": False}
    request = urllib.request.Request(
        host.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return {"model": model, "response": body.get("response", ""),
            "done": body.get("done", False)}


def doctor() -> dict[str, Any]:
    result: dict[str, Any] = {"mss": False, "ocr": False, "canvas": None, "capture": None}
    try:
        import mss  # noqa: F401
        result["mss"] = True
    except Exception:
        pass
    try:
        import rapidocr_onnxruntime  # noqa: F401
        result["ocr"] = True
    except Exception:
        pass
    try:
        result["canvas"] = screen.virtual_monitor_index()
    except SystemExit:
        pass
    try:
        monitors = screen.list_monitors()
        image = grab(monitors[0].bbox)
        result["capture"] = [image.width, image.height]
    except Exception as exc:
        result["captureError"] = str(exc)
    return result


def trace(event: dict[str, Any]) -> None:
    """把动作追加到当天轨迹文件，便于回放和审计。"""
    from datetime import datetime

    directory = HERE / "traces"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now():%Y%m%d}.jsonl"
    record = {"at": datetime.now().isoformat(timespec="seconds"), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _window_text(hwnd: int) -> str:
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_double)


def find_file_dialog() -> int | None:
    """找可见的 #32770 文件对话框（Win32 枚举，不依赖 UIA）。"""
    import ctypes

    user32 = ctypes.windll.user32
    found: list[int] = []
    keys = ("打开", "Open", "选择", "浏览", "上传", "另存为", "Save")

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or _class_name(hwnd) != "#32770":
            return True
        if any(key in _window_text(hwnd) for key in keys):
            found.append(hwnd)
        return True

    user32.EnumWindows(ENUM_PROC(callback), 0)
    return found[0] if found else None


def find_filename_edit(dialog: int) -> int | None:
    import ctypes

    user32 = ctypes.windll.user32
    edits: list[int] = []

    def callback(hwnd, _):
        if _class_name(hwnd) == "Edit" and user32.IsWindowVisible(hwnd):
            edits.append(hwnd)
        return True

    user32.EnumChildWindows(dialog, ENUM_PROC(callback), 0)
    for edit in edits:
        if "ComboBox" in _class_name(user32.GetParent(edit)):
            return edit
    return edits[0] if edits else None


def find_open_button(dialog: int) -> int | None:
    import ctypes

    user32 = ctypes.windll.user32
    buttons: list[int] = []
    keys = ("打开", "Open", "选择", "Select", "保存", "Save")

    def callback(hwnd, _):
        if _class_name(hwnd) == "Button" and user32.IsWindowVisible(hwnd):
            text = _window_text(hwnd)
            if any(key in text for key in keys):
                buttons.append(hwnd)
        return True

    user32.EnumChildWindows(dialog, ENUM_PROC(callback), 0)
    return buttons[0] if buttons else None


def click_window_center(hwnd: int) -> None:
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    mouse_click((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)


def choose_file(path: str, *, dialog: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    """在系统文件对话框里填入路径并确认。

    必须用真实输入（点击输入框、Ctrl+A、粘贴、回车）：直接 SetWindowText 不会
    触发对话框的校验，打开按钮会一直不可用。
    """
    import ctypes

    user32 = ctypes.windll.user32
    target = dialog or find_file_dialog()
    if not target:
        raise SystemExit("没找到文件对话框（#32770）。先点上传按钮把对话框打开")
    edit = find_filename_edit(target)
    if not edit:
        raise SystemExit("文件对话框里没找到文件名输入框")
    plan = {"dialog": _window_text(target), "dialogHwnd": target, "path": path,
            "edit": _window_text(edit)}
    if dry_run:
        return {**plan, "dryRun": True}

    user32.SetForegroundWindow(target)
    time.sleep(0.2)
    click_window_center(edit)
    time.sleep(0.15)
    key_combo("ctrl+a")
    type_text(path)
    time.sleep(0.5)
    key_combo("enter")
    time.sleep(0.8)

    closed = not bool(user32.IsWindowVisible(target))
    button = None
    if not closed:
        button = find_open_button(target)
        if button:
            click_window_center(button)
            time.sleep(0.8)
            closed = not bool(user32.IsWindowVisible(target))
    return {**plan, "submitted": True, "closed": closed, "button": button}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="图像操作画布")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_shot = sub.add_parser("shot", help="截图并写 .json")
    p_shot.add_argument("--window")
    p_shot.add_argument("--hwnd", type=int, help="按窗口句柄精确指定")
    p_shot.add_argument("--monitor", type=int, default=1)
    p_shot.add_argument("--virtual", action="store_true", help="截虚拟画布")
    p_shot.add_argument("--virtual-index", type=int, default=1, help="第几块虚拟屏")
    p_shot.add_argument("--out", required=True)
    p_shot.add_argument("--grid", action="store_true", help="画坐标网格")
    p_shot.add_argument("--ocr", action="store_true", help="识别文字框并标注")

    p_click = sub.add_parser("click", help="按图片坐标点击")
    p_click.add_argument("--shot", required=True, help="shot 写出的 .json")
    p_click.add_argument("--x", type=int, required=True)
    p_click.add_argument("--y", type=int, required=True)
    p_click.add_argument("--button", choices=("left", "right"), default="left")
    p_click.add_argument("--double", action="store_true")
    p_click.add_argument("--force", action="store_true", help="画面变了也照点")
    p_click.add_argument("--yes", action="store_true")

    p_type = sub.add_parser("type", help="输入文本（剪贴板粘贴）")
    p_type.add_argument("--text", required=True)
    p_type.add_argument("--yes", action="store_true")

    p_key = sub.add_parser("key", help="按键或组合键")
    p_key.add_argument("--combo", required=True)
    p_key.add_argument("--yes", action="store_true")

    p_scroll = sub.add_parser("scroll", help="滚轮，正数向上")
    p_scroll.add_argument("--dy", type=int, required=True)
    p_scroll.add_argument("--shot", help="可选：先按截图坐标移动鼠标再滚")
    p_scroll.add_argument("--x", type=int)
    p_scroll.add_argument("--y", type=int)
    p_scroll.add_argument("--yes", action="store_true")

    p_drag = sub.add_parser("drag", help="拖拽（图片坐标）")
    p_drag.add_argument("--shot", required=True)
    p_drag.add_argument("--x1", type=int, required=True)
    p_drag.add_argument("--y1", type=int, required=True)
    p_drag.add_argument("--x2", type=int, required=True)
    p_drag.add_argument("--y2", type=int, required=True)
    p_drag.add_argument("--raw", action="store_true", help="坐标是屏幕绝对坐标，不做映射")
    p_drag.add_argument("--force", action="store_true")
    p_drag.add_argument("--yes", action="store_true")

    p_find = sub.add_parser("find", help="模板匹配")
    p_find.add_argument("--image", required=True)
    p_find.add_argument("--template", required=True)
    p_find.add_argument("--threshold", type=float, default=0.85)

    p_click_text = sub.add_parser("click-text", help="按截图里的文字点击")
    p_click_text.add_argument("--shot", required=True, help="shot 写出的 .json")
    p_click_text.add_argument("--text", required=True)
    p_click_text.add_argument("--force", action="store_true")
    p_click_text.add_argument("--yes", action="store_true")

    p_speed = sub.add_parser("speed", help="测这一块屏的截图帧率")
    p_speed.add_argument("--monitor", type=int, default=1)
    p_speed.add_argument("--window")
    p_speed.add_argument("--virtual", action="store_true")
    p_speed.add_argument("--virtual-index", type=int, default=1)
    p_speed.add_argument("--frames", type=int, default=30)

    p_burst = sub.add_parser("burst", help="连拍，用来看动画或游戏")
    p_burst.add_argument("--monitor", type=int, default=1)
    p_burst.add_argument("--window")
    p_burst.add_argument("--virtual", action="store_true")
    p_burst.add_argument("--virtual-index", type=int, default=1)
    p_burst.add_argument("--count", type=int, default=10)
    p_burst.add_argument("--interval", type=float, default=0.05)
    p_burst.add_argument("--out-dir", required=True)

    p_watch = sub.add_parser("watch", help="按帧率观察画面变化，只保存变动帧")
    p_watch.add_argument("--monitor", type=int, default=1)
    p_watch.add_argument("--window")
    p_watch.add_argument("--virtual", action="store_true")
    p_watch.add_argument("--virtual-index", type=int, default=1)
    p_watch.add_argument("--seconds", type=float, default=5)
    p_watch.add_argument("--fps", type=float, default=10)
    p_watch.add_argument("--out-dir")

    p_diff = sub.add_parser("diff", help="比较两张图的变化")
    p_diff.add_argument("--a", required=True)
    p_diff.add_argument("--b", required=True)
    p_diff.add_argument("--threshold", type=int, default=24)

    p_ask = sub.add_parser("ask", help="把截图交给本地 Ollama 视觉模型")
    p_ask.add_argument("--image", required=True)
    p_ask.add_argument("--prompt", required=True)
    p_ask.add_argument("--model", default="qwen2.5vl:3b")
    p_ask.add_argument("--host", default="http://127.0.0.1:11434")

    p_wait = sub.add_parser("wait", help="等画面稳定再截图")
    p_wait.add_argument("--monitor", type=int, default=1)
    p_wait.add_argument("--window")
    p_wait.add_argument("--virtual", action="store_true")
    p_wait.add_argument("--virtual-index", type=int, default=1)
    p_wait.add_argument("--timeout", type=float, default=10)
    p_wait.add_argument("--interval", type=float, default=0.25)
    p_wait.add_argument("--stable", type=int, default=2)

    sub.add_parser("doctor", help="自检采集、OCR、画布")

    p_choose = sub.add_parser("choose-file", help="在系统文件对话框里选文件")
    p_choose.add_argument("--path", required=True)
    p_choose.add_argument("--hwnd", type=int, help="对话框句柄，默认自动找 #32770")
    p_choose.add_argument("--yes", action="store_true")

    p_trace = sub.add_parser("trace", help="查看动作轨迹")
    p_trace.add_argument("--tail", type=int, default=20)

    args = parser.parse_args(argv)

    if args.cmd == "shot":
        image, bbox, source = capture(args)
        if getattr(args, "hwnd", None):
            label = f"hwnd:{args.hwnd}"
        elif args.window:
            label = f"window:{args.window}"
        else:
            label = f"monitor:{args.monitor}"
        data = write_shot(image, bbox, label, Path(args.out), grid=args.grid, ocr=args.ocr)
        trace({"action": "shot", "out": str(args.out), "source": label})
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "click":
        sidecar = load_sidecar(Path(args.shot))
        if bbox_changed(sidecar):
            raise SystemExit("窗口位置变了，重新 shot 再点")
        x, y = map_point(sidecar, args.x, args.y)
        if not args.yes:
            print(json.dumps({"wouldClick": [x, y], "imagePoint": [args.x, args.y],
                              "button": args.button, "double": args.double},
                             ensure_ascii=False))
            return 0
        if not args.force:
            check = verify_shot(sidecar)
            if not check["ok"]:
                raise SystemExit(f"画面变了（{check['changedRatio']:.0%}），重新 shot，"
                                 "或加 --force 强制点击")
        mouse_click(x, y, button=args.button, double=args.double)
        trace({"action": "click", "point": [x, y], "button": args.button,
               "double": args.double})
        print(json.dumps({"clicked": [x, y], "button": args.button,
                          "double": args.double}, ensure_ascii=False))
        return 0

    if args.cmd == "type":
        if not args.yes:
            print(json.dumps({"wouldType": args.text}, ensure_ascii=False))
            return 0
        type_text(args.text)
        trace({"action": "type", "length": len(args.text), "text": args.text[:80]})
        print(json.dumps({"typed": len(args.text)}, ensure_ascii=False))
        return 0

    if args.cmd == "key":
        if not args.yes:
            print(json.dumps({"wouldPress": parse_combo(args.combo)}, ensure_ascii=False))
            return 0
        key_combo(args.combo)
        trace({"action": "key", "combo": args.combo})
        print(json.dumps({"pressed": args.combo}, ensure_ascii=False))
        return 0

    if args.cmd == "scroll":
        if not args.yes:
            print(json.dumps({"wouldScroll": args.dy}, ensure_ascii=False))
            return 0
        if args.shot and args.x is not None and args.y is not None:
            sidecar = load_sidecar(Path(args.shot))
            move_cursor(*map_point(sidecar, args.x, args.y))
        scroll(args.dy)
        trace({"action": "scroll", "dy": args.dy})
        print(json.dumps({"scrolled": args.dy}, ensure_ascii=False))
        return 0

    if args.cmd == "drag":
        sidecar = load_sidecar(Path(args.shot))
        if args.raw:
            x1, y1, x2, y2 = args.x1, args.y1, args.x2, args.y2
        else:
            if bbox_changed(sidecar):
                raise SystemExit("窗口位置变了，重新 shot 再拖")
            x1, y1 = map_point(sidecar, args.x1, args.y1)
            x2, y2 = map_point(sidecar, args.x2, args.y2)
        if not args.yes:
            print(json.dumps({"wouldDrag": [[x1, y1], [x2, y2]]}, ensure_ascii=False))
            return 0
        if not args.raw and not getattr(args, "force", False):
            check = verify_shot(sidecar)
            if not check["ok"]:
                raise SystemExit(f"画面变了（{check['changedRatio']:.0%}），重新 shot，"
                                 "或加 --force 强制拖拽")
        mouse_drag(x1, y1, x2, y2)
        trace({"action": "drag", "from": [x1, y1], "to": [x2, y2]})
        print(json.dumps({"dragged": [[x1, y1], [x2, y2]]}, ensure_ascii=False))
        return 0

    if args.cmd == "find":
        print(json.dumps(find_template(Path(args.image), Path(args.template),
                                       args.threshold), ensure_ascii=False))
        return 0

    if args.cmd == "click-text":
        sidecar = load_sidecar(Path(args.shot))
        if bbox_changed(sidecar):
            raise SystemExit("窗口位置变了，重新 shot 再点")
        boxes = [Box(text=item["text"], score=item.get("score", 0),
                     left=item["box"][0], top=item["box"][1],
                     right=item["box"][2], bottom=item["box"][3])
                 for item in sidecar.get("ocr", [])]
        box = pick_box(boxes, args.text)
        if box is None:
            raise SystemExit(f"截图里没找到文字 {args.text!r}")
        x, y = map_point(sidecar, *box.center)
        if not args.yes:
            print(json.dumps({"wouldClick": [x, y], "text": box.text,
                              "center": list(box.center)}, ensure_ascii=False))
            return 0
        if not args.force:
            check = verify_shot(sidecar)
            if not check["ok"]:
                raise SystemExit(f"画面变了（{check['changedRatio']:.0%}），重新 shot，"
                                 "或加 --force 强制点击")
        mouse_click(x, y)
        trace({"action": "click-text", "point": [x, y], "text": box.text})
        print(json.dumps({"clicked": [x, y], "text": box.text}, ensure_ascii=False))
        return 0

    if args.cmd == "speed":
        _, bbox, _ = capture(args)
        import time

        frames = max(1, args.frames)
        start = time.time()
        for _ in range(frames):
            grab(bbox)
        elapsed = time.time() - start
        print(json.dumps({"bbox": bbox, "frames": frames, "seconds": round(elapsed, 3),
                          "fps": round(frames / elapsed, 1)}, ensure_ascii=False))
        return 0

    if args.cmd == "burst":
        _, bbox, _ = capture(args)
        print(json.dumps(burst(bbox, args.count, args.interval, Path(args.out_dir)),
                         ensure_ascii=False))
        return 0

    if args.cmd == "watch":
        _, bbox, _ = capture(args)
        result = watch(bbox, args.seconds, args.fps,
                       Path(args.out_dir) if args.out_dir else None)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.cmd == "diff":
        from PIL import Image

        result = diff_images(Image.open(args.a), Image.open(args.b), args.threshold)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.cmd == "ask":
        try:
            result = ollama_ask(Path(args.image), args.prompt, model=args.model, host=args.host)
        except Exception as exc:
            raise SystemExit(f"调用 Ollama 失败：{exc}\n先运行：ollama pull {args.model}") from exc
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.cmd == "wait":
        _, bbox, _ = capture(args)
        result = wait_stable(bbox, interval=args.interval, stable=args.stable,
                             timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1

    if args.cmd == "doctor":
        result = doctor()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("capture") else 1

    if args.cmd == "choose-file":
        try:
            result = choose_file(args.path, dialog=args.hwnd, dry_run=not args.yes)
        except SystemExit as exc:
            print(str(exc))
            return 1
        if args.yes:
            trace({"action": "choose-file", "path": args.path})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "trace":
        from datetime import datetime

        path = HERE / "traces" / f"{datetime.now():%Y%m%d}.jsonl"
        if not path.exists():
            print("今天还没有动作记录")
            return 0
        lines = path.read_text(encoding="utf-8").splitlines()[-max(1, args.tail):]
        print("\n".join(lines))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
