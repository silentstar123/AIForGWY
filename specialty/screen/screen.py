# -*- coding: utf-8 -*-
"""屏幕画布：把一块显示器或一个窗口当成独立画布来截图和定位。

思路是「一次只看一个屏幕」：agent 只截目标显示器/窗口的那一块，坐标按同一
块区域回算，不碰整个桌面。配合固定窗口位置，识别和点击都只在一个坐标系里。

用法：
    python specialty/screen/screen.py list
    python specialty/screen/screen.py capture --monitor 2 --out shot.png
    python specialty/screen/screen.py capture --window "发改委项目管理库" --out win.png
    python specialty/screen/screen.py place --window "发改委项目管理库" --monitor 2 --maximize
    python specialty/screen/screen.py click --monitor 2 --x 640 --y 360 --yes
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINTL(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MODE1(ctypes.Structure):
    _fields_ = [("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
                ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
                ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
                ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short)]


class _MODE2(ctypes.Structure):
    _fields_ = [("dmPosition", POINTL), ("dmDisplayOrientation", ctypes.c_ulong),
                ("dmDisplayFixedOutput", ctypes.c_ulong)]


class _UNION1(ctypes.Union):
    _fields_ = [("m1", _MODE1), ("m2", _MODE2)]


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort), ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_ulong),
        ("u1", _UNION1),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort),
        ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
        ("u2", ctypes.c_ulong),
        ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong), ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong),
    ]


DM_POSITION = 0x20
DM_PELSWIDTH = 0x80000
DM_PELSHEIGHT = 0x100000
ENUM_CURRENT_SETTINGS = -1
CDS_UPDATEREGISTRY = 0x00000001


def set_mode(display: str, width: int, height: int, *,
             x: int | None = None, y: int | None = None) -> dict[str, Any]:
    """改一块显示器的分辨率和位置。display 形如 \\\\.\\DISPLAY25。"""
    mode = DEVMODE()
    mode.dmSize = ctypes.sizeof(DEVMODE)
    if not user32.EnumDisplaySettingsW(display, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)):
        raise SystemExit(f"读不到 {display} 的当前显示模式")
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
    mode.dmPelsWidth = int(width)
    mode.dmPelsHeight = int(height)
    if x is not None and y is not None:
        mode.dmFields |= DM_POSITION
        mode.u1.m2.dmPosition = POINTL(int(x), int(y))
    result = user32.ChangeDisplaySettingsExW(display, ctypes.byref(mode), None,
                                             CDS_UPDATEREGISTRY, None)
    return {"display": display, "width": width, "height": height,
            "position": [x, y] if x is not None else None, "result": result}


@dataclass
class Monitor:
    index: int
    left: int
    top: int
    width: int
    height: int
    primary: bool

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)


@dataclass
class Window:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


MONITORPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                                 ctypes.POINTER(RECT), ctypes.c_double)


def list_monitors() -> list[Monitor]:
    found: list[Monitor] = []

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    def callback(hmonitor, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
        rect = info.rcMonitor
        found.append(Monitor(index=len(found) + 1, left=rect.left, top=rect.top,
                             width=rect.right - rect.left, height=rect.bottom - rect.top,
                             primary=bool(info.dwFlags & 1)))
        return True

    user32.EnumDisplayMonitors(0, 0, MONITORPROC(callback), 0)
    return found


def list_windows() -> list[Window]:
    found: list[Window] = []

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
            return True
        found.append(Window(hwnd=hwnd, title=buffer.value, left=rect.left, top=rect.top,
                            width=rect.right - rect.left, height=rect.bottom - rect.top))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_double)(callback), 0)
    return found


def find_windows(title: str) -> list[Window]:
    """标题包含 title 的窗口，按面积从大到小。"""
    return sorted((w for w in list_windows() if title in w.title),
                  key=lambda w: w.width * w.height, reverse=True)


def find_window(title: str) -> Window | None:
    matches = find_windows(title)
    return matches[0] if matches else None


def resolve_window(*, title: str | None = None, hwnd: int | None = None) -> Window | None:
    """优先按 hwnd 精确匹配，否则按标题取面积最大的那个。"""
    if hwnd:
        for window in list_windows():
            if window.hwnd == hwnd:
                return window
        return None
    if title:
        return find_window(title)
    return None


def dpi_for_monitor(index: int = 1) -> int:
    """取某块显示器的 DPI（96 表示 100%）。"""
    try:
        monitors = list_monitors()
        point = wt.POINT(monitors[index - 1].left + 1, monitors[index - 1].top + 1)
        x, y = ctypes.c_uint(), ctypes.c_uint()
        monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        if ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(x), ctypes.byref(y)) == 0:
            return int(x.value)
    except Exception:
        pass
    return 96


def client_bbox(hwnd: int) -> tuple[int, int, int, int]:
    """客户区（去掉标题栏和边框）在屏幕坐标系里的矩形。"""
    rect = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    point = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    return (point.x, point.y, point.x + rect.right, point.y + rect.bottom)


def capture_bbox(bbox: tuple[int, int, int, int], out: Path) -> dict[str, Any]:
    from PIL import ImageGrab

    image = ImageGrab.grab(bbox=bbox, all_screens=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out))
    return {"file": str(out), "width": image.width, "height": image.height, "bbox": bbox}


def place_window(window: Window, monitor: Monitor, *, size: tuple[int, int] | None = None,
                 maximize: bool = False, apply: bool = False) -> dict[str, Any]:
    SW_MAXIMIZE = 3
    SW_RESTORE = 9
    if maximize:
        target = monitor.bbox
    elif size:
        width, height = size
        if width > monitor.width or height > monitor.height:
            raise SystemExit(f"窗口 {width}x{height} 超过显示器 {monitor.width}x{monitor.height}")
        target = (monitor.left + (monitor.width - width) // 2,
                  monitor.top + (monitor.height - height) // 2, width, height)
    else:
        target = (monitor.left, monitor.top, monitor.width, monitor.height)
    plan = {"hwnd": window.hwnd, "title": window.title, "monitor": monitor.index,
            "rect": target, "maximize": maximize, "applied": False}
    if not apply:
        return plan
    if maximize:
        # 先移到目标屏，再最大化；否则 ShowWindow 会在窗口当前所在的屏上最大化
        user32.ShowWindow(window.hwnd, SW_RESTORE)
        user32.SetWindowPos(window.hwnd, 0, monitor.left, monitor.top,
                            monitor.width, monitor.height, 0x0040)
        user32.ShowWindow(window.hwnd, SW_MAXIMIZE)
    else:
        left, top, width, height = target
        user32.SetWindowPos(window.hwnd, 0, left, top, width, height, 0x0040)
    plan["applied"] = True
    actual = Window(hwnd=window.hwnd, title=window.title, left=0, top=0, width=0, height=0)
    rect = RECT()
    if user32.GetWindowRect(window.hwnd, ctypes.byref(rect)):
        plan["actual"] = [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top]
    return plan


def move_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def click(x: int, y: int) -> None:
    import win32api
    import win32con

    move_cursor(x, y)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def resolve_bbox(args: argparse.Namespace) -> tuple[int, int, int, int]:
    hwnd = getattr(args, "hwnd", None)
    if hwnd or args.window:
        found = resolve_window(title=args.window, hwnd=hwnd)
        if not found:
            raise SystemExit(f"没找到窗口（title={args.window!r} hwnd={hwnd}）")
        return client_bbox(found.hwnd)
    monitors = list_monitors()
    if not 1 <= args.monitor <= len(monitors):
        raise SystemExit(f"显示器编号超出范围 1–{len(monitors)}")
    return monitors[args.monitor - 1].bbox


def parse_size(text: str) -> tuple[int, int]:
    try:
        width, _, height = text.lower().partition("x")
        return int(width), int(height)
    except ValueError as exc:
        raise SystemExit(f"尺寸格式应为 宽x高，收到 {text!r}") from exc


def virtual_monitor_index(index: int = 1) -> int:
    """向 virtualscreen 查询第 index 块虚拟画布的显示器编号。"""
    import subprocess
    import sys

    script = Path(__file__).resolve().parent.parent / "virtualscreen" / "virtualscreen.py"
    output = subprocess.run([sys.executable, str(script), "canvas", "--index", str(index)],
                            capture_output=True, text=True, encoding="utf-8")
    if output.returncode != 0:
        raise SystemExit(output.stdout.strip() or "没有可用的虚拟屏，先运行 virtualscreen.py ensure")
    return int(json.loads(output.stdout)["index"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="单屏/单窗口画布：枚举、截图、摆位、点击")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出显示器和可见窗口")
    p_list.add_argument("--json", action="store_true")

    p_cap = sub.add_parser("capture", help="只截一块屏或一个窗口")
    p_cap.add_argument("--monitor", type=int, default=1)
    p_cap.add_argument("--window")
    p_cap.add_argument("--hwnd", type=int, help="按窗口句柄精确指定")
    p_cap.add_argument("--virtual", action="store_true", help="截虚拟画布")
    p_cap.add_argument("--virtual-index", type=int, default=1, help="第几块虚拟屏")
    p_cap.add_argument("--out", required=True)

    p_place = sub.add_parser("place", help="把窗口摆到指定显示器（默认只演练）")
    p_place.add_argument("--window")
    p_place.add_argument("--hwnd", type=int, help="按窗口句柄精确指定")
    p_place.add_argument("--monitor", type=int, default=1)
    p_place.add_argument("--virtual", action="store_true", help="摆到虚拟画布")
    p_place.add_argument("--virtual-index", type=int, default=1, help="第几块虚拟屏")
    p_place.add_argument("--size", help="宽x高，例如 1280x800")
    p_place.add_argument("--maximize", action="store_true")
    p_place.add_argument("--apply", action="store_true", help="真的移动窗口")

    p_click = sub.add_parser("click", help="按画布坐标点击（默认只演练）")
    p_click.add_argument("--monitor", type=int, default=1)
    p_click.add_argument("--window")
    p_click.add_argument("--hwnd", type=int)
    p_click.add_argument("--x", type=int, required=True)
    p_click.add_argument("--y", type=int, required=True)
    p_click.add_argument("--yes", action="store_true", help="真的点击")

    p_set = sub.add_parser("set", help="设置某块显示器的分辨率和位置")
    p_set.add_argument("--display", required=True, help=r"例如 \\.\DISPLAY25")
    p_set.add_argument("--width", type=int, required=True)
    p_set.add_argument("--height", type=int, required=True)
    p_set.add_argument("--x", type=int)
    p_set.add_argument("--y", type=int)

    args = parser.parse_args(argv)

    if args.cmd == "list":
        monitors = [asdict(m) for m in list_monitors()]
        for item in monitors:
            item["dpi"] = dpi_for_monitor(item["index"])
        windows = [asdict(w) for w in list_windows()]
        if args.json:
            print(json.dumps({"monitors": monitors, "windows": windows},
                             ensure_ascii=False, indent=2))
        else:
            print("显示器：")
            for item in monitors:
                print(f"  {item['index']}: {item['width']}x{item['height']} "
                      f"@ ({item['left']},{item['top']}) dpi={item['dpi']}"
                      f"{' 主屏' if item['primary'] else ''}")
            print("窗口：")
            for item in windows[:20]:
                print(f"  {item['hwnd']:>9} {item['width']:>4}x{item['height']:<4} "
                      f"@ ({item['left']},{item['top']}) {item['title'][:50]}")
        return 0

    if args.cmd == "capture":
        if getattr(args, "virtual", False):
            args.monitor = virtual_monitor_index(getattr(args, "virtual_index", 1))
        bbox = resolve_bbox(args)
        result = capture_bbox(bbox, Path(args.out))
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.cmd == "place":
        if getattr(args, "virtual", False):
            args.monitor = virtual_monitor_index(getattr(args, "virtual_index", 1))
        hwnd = getattr(args, "hwnd", None)
        found = resolve_window(title=args.window, hwnd=hwnd)
        if not found:
            raise SystemExit(f"没找到窗口（title={args.window!r} hwnd={hwnd}）")
        monitors = list_monitors()
        if not 1 <= args.monitor <= len(monitors):
            raise SystemExit(f"显示器编号超出范围 1–{len(monitors)}")
        plan = place_window(found, monitors[args.monitor - 1],
                            size=parse_size(args.size) if args.size else None,
                            maximize=args.maximize, apply=args.apply)
        if not hwnd:
            candidates = find_windows(args.window)
            if len(candidates) > 1:
                plan["ambiguous"] = [{"hwnd": w.hwnd, "title": w.title} for w in candidates[:5]]
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "click":
        bbox = resolve_bbox(args)
        screen_x, screen_y = bbox[0] + args.x, bbox[1] + args.y
        if not args.yes:
            print(json.dumps({"wouldClick": [screen_x, screen_y], "bbox": bbox,
                              "hint": "加 --yes 才真的点"}, ensure_ascii=False))
            return 0
        click(screen_x, screen_y)
        print(json.dumps({"clicked": [screen_x, screen_y]}, ensure_ascii=False))
        return 0

    if args.cmd == "set":
        print(json.dumps(set_mode(args.display, args.width, args.height,
                                  x=args.x, y=args.y), ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
