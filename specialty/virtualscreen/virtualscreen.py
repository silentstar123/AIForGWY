# -*- coding: utf-8 -*-
"""虚拟显示器：识别当前用的是物理屏还是虚拟屏，并给出常驻虚拟屏的启用方式。

Windows 把虚拟屏和物理屏一样当显示器用，所以截图、摆窗、坐标映射完全一致；
区别只在“这块屏从哪来”。本机已装的向日葵（Oray）IDD 驱动就是一个虚拟显示
提供方，但启用它需要管理员权限，脚本见同目录 setup.ps1。

用法：
    python specialty/virtualscreen/virtualscreen.py status
    python specialty/virtualscreen/virtualscreen.py require   # 没有虚拟屏时退出码 1
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "screen"))

import screen  # noqa: E402

VDD_SETTINGS = Path(os.environ.get("DSH_VDD_SETTINGS", r"C:\VirtualDisplayDriver\vdd_settings.xml"))
VDD_INSTANCE = os.environ.get("DSH_VDD_INSTANCE", r"ROOT\DISPLAY\0001")
MAX_VIRTUAL = 4
HELPER_DIR = Path(os.environ.get("DSH_HELPER_DIR", r"C:\ProgramData\DSHDisplay"))
HELPER_QUEUE = HELPER_DIR / "queue"
HELPER_FLAG = HELPER_QUEUE / "restart.flag"
HELPER_RESULT = HELPER_QUEUE / "result.json"
HELPER_MARKER = HELPER_QUEUE / "installed.json"
HELPER_TASK = "DSHDisplayHelper"

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

VIRTUAL_HINTS = ("orayidd", "idddriver", "iddsample", "iddcx", "virtual display",
                 "virtualdisplay", "vdd", "usbmmidd", "parsec", "spacedesk",
                 "indirect display", "meta virtual")


class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("DeviceName", wt.WCHAR * 32),
        ("DeviceString", wt.WCHAR * 128),
        ("StateFlags", wt.DWORD),
        ("DeviceID", wt.WCHAR * 128),
        ("DeviceKey", wt.WCHAR * 128),
    ]


@dataclass
class Adapter:
    name: str
    description: str
    attached: bool
    primary: bool
    virtual: bool
    monitors: list[str]


def classify(description: str) -> str:
    lowered = (description or "").lower()
    return "virtual" if any(hint in lowered for hint in VIRTUAL_HINTS) else "physical"


def _enum(device_name: str | None) -> list[DISPLAY_DEVICE]:
    out: list[DISPLAY_DEVICE] = []
    index = 0
    while True:
        device = DISPLAY_DEVICE()
        device.cb = ctypes.sizeof(device)
        if not user32.EnumDisplayDevicesW(device_name, index, ctypes.byref(device), 0):
            break
        out.append(device)
        index += 1
    return out


def adapters() -> list[Adapter]:
    found: list[Adapter] = []
    for device in _enum(None):
        monitors = [m.DeviceString or m.DeviceID for m in _enum(device.DeviceName)]
        found.append(Adapter(
            name=device.DeviceName,
            description=device.DeviceString,
            attached=bool(device.StateFlags & 1),
            primary=bool(device.StateFlags & 4),
            virtual=classify(device.DeviceString) == "virtual",
            monitors=monitors,
        ))
    return found


def active_virtual() -> Adapter | None:
    for adapter in adapters():
        if adapter.virtual and adapter.attached and adapter.monitors:
            return adapter
    return None


def virtual_monitors() -> list[screen.Monitor]:
    """所有虚拟适配器对应的画布，按已连接顺序。"""
    attached = [a for a in adapters() if a.attached]
    monitors = screen.list_monitors()
    found: list[screen.Monitor] = []
    for index, adapter in enumerate(attached):
        if adapter.virtual and adapter.monitors and index < len(monitors):
            found.append(monitors[index])
    return found


def canvas_monitor() -> screen.Monitor | None:
    """虚拟屏对应的画布：按已连接显示器的顺序对应第 N 块监视器。"""
    found = virtual_monitors()
    return found[0] if found else None


def configured_count(path: Path | None = None) -> int:
    """VDD 配置里声明的显示器数量。"""
    target = Path(path or VDD_SETTINGS)
    if not target.is_file():
        return 0
    match = re.search(r"<count>\s*(\d+)\s*</count>",
                      target.read_text(encoding="utf-8", errors="replace"))
    return int(match.group(1)) if match else 0


def set_configured_count(count: int, path: Path | None = None) -> dict[str, Any]:
    """改写 vdd_settings.xml 的显示器数量（不需要管理员；重启设备才生效）。"""
    if not 1 <= count <= MAX_VIRTUAL:
        raise ValueError(f"虚拟屏数量应在 1–{MAX_VIRTUAL}，收到 {count}")
    target = Path(path or VDD_SETTINGS)
    if not target.is_file():
        raise SystemExit(f"找不到 VDD 配置：{target}")
    text = target.read_text(encoding="utf-8")
    new_text, replaced = re.subn(r"<count>\s*\d+\s*</count>",
                                 f"<count>{count}</count>", text, count=1)
    if not replaced:
        raise SystemExit(f"{target} 里没有 <count> 节点")
    backup = target.with_suffix(".xml.bak")
    shutil.copy2(target, backup)
    target.write_text(new_text, encoding="utf-8")
    return {"path": str(target), "count": count, "backup": str(backup)}


def helper_status() -> dict[str, Any]:
    """看 SYSTEM 小助手装没装：普通用户查不了 SYSTEM 任务，改看安装标记。"""
    installed = HELPER_MARKER.is_file()
    return {"installed": installed, "task": HELPER_TASK,
            "dir": str(HELPER_DIR), "marker": str(HELPER_MARKER)}


def request_restart(timeout: float = 120, sleep=None) -> dict[str, Any]:
    """写标志文件，等 SYSTEM 小助手重启显示设备；不需要 UAC。"""
    import time

    sleep = sleep or time.sleep
    if not helper_status()["installed"]:
        return {"stage": "needs-helper",
                "hint": "需要管理员装一次小助手：\n"
                        "  powershell -ExecutionPolicy Bypass -File "
                        f"\"{HERE / 'install-helper.ps1'}\""}
    start = time.time()
    HELPER_FLAG.parent.mkdir(parents=True, exist_ok=True)
    HELPER_RESULT.unlink(missing_ok=True)
    HELPER_FLAG.write_text(str(start), encoding="utf-8")
    deadline = start + max(10.0, timeout)
    while time.time() < deadline:
        if HELPER_RESULT.is_file() and HELPER_RESULT.stat().st_mtime >= start - 1:
            try:
                payload = json.loads(HELPER_RESULT.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                return {"stage": "failed", "error": str(exc)}
            return {"stage": "applied" if payload.get("ok") else "failed",
                    "result": payload, "waited": round(time.time() - start, 1)}
        sleep(2)
    return {"stage": "timeout", "waited": round(time.time() - start, 1),
            "hint": f"计划任务 {HELPER_TASK} 没在时限内跑；检查任务状态"}


def ask_permission(message: str) -> dict[str, Any]:
    """让桌宠弹一条气泡，向在场的人要管理员权限。"""
    pet = HERE.parent / "pet" / "pet.py"
    try:
        subprocess.run([sys.executable, str(pet), "bubble", message],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=10)
        return {"asked": True, "via": "pet"}
    except Exception as exc:
        return {"asked": False, "error": str(exc)}


def _restart_elevated(instance: str, sleep, runner) -> None:
    """用一次 UAC 提升去重启显示设备并重新扩展桌面。"""
    import tempfile

    script = (
        f'pnputil /restart-device "{instance}"\n'
        "Start-Sleep -Seconds 3\n"
        "DisplaySwitch.exe /extend\n"
        "Start-Sleep -Seconds 2\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                     encoding="utf-8-sig") as handle:
        handle.write(script)
        path = handle.name
    try:
        command = (
            "Start-Process powershell -Verb RunAs -Wait -ArgumentList "
            f"'@(\"-NoProfile\",\"-ExecutionPolicy\",\"Bypass\",\"-File\",\"{path}\")'"
        )
        runner(["powershell", "-NoProfile", "-Command", command])
    finally:
        Path(path).unlink(missing_ok=True)
    sleep(2)


def set_count(count: int, *, apply: bool = False, elevate: bool = False,
              helper: bool = False, ask: bool = False,
              runner=None, sleep=None, status_fn=None) -> dict[str, Any]:
    """决定开几块虚拟屏：改配置；apply 时尝试重启设备（需要管理员）。"""
    import time

    sleep = sleep or time.sleep
    status_fn = status_fn or status
    runner = runner or (lambda command: subprocess.run(command, capture_output=True, text=True))

    current = configured_count()
    actual_now = len(virtual_monitors())
    if count == current and (actual_now >= count or not apply):
        return {"stage": "unchanged", "configured": current, "actual": actual_now}
    if apply and helper and not helper_status()["installed"]:
        return {"stage": "needs-helper", "configured": current, "requested": count,
                "hint": "需要管理员装一次小助手：\n"
                        "  powershell -ExecutionPolicy Bypass -File "
                        f"\"{HERE / 'install-helper.ps1'}\""}
    info = set_configured_count(count)
    if not apply:
        return {"stage": "pending", "configured": current, "requested": count,
                "backup": info["backup"],
                "hint": "加 --apply 重启显示设备后生效；重启设备需要管理员权限"}

    result = runner(["pnputil", "/restart-device", VDD_INSTANCE])
    output = f"{getattr(result, 'stdout', '') or ''}{getattr(result, 'stderr', '') or ''}"
    code = getattr(result, "returncode", 1)
    denied = code != 0 or "Access is denied" in output or "拒绝访问" in output
    if denied and helper:
        restarted = request_restart(sleep=sleep)
        data = status_fn()
        actual = len(data.get("virtualMonitors") or [])
        return {"stage": "applied" if actual >= count else restarted["stage"],
                "configured": count, "actual": actual,
                "virtualMonitors": data.get("virtualMonitors"),
                "helper": restarted}
    if denied and elevate:
        _restart_elevated(VDD_INSTANCE, sleep, runner)
        data = status_fn()
        actual = len(data.get("virtualMonitors") or [])
        return {"stage": "applied" if actual >= count else "needs-admin",
                "configured": count, "actual": actual,
                "virtualMonitors": data.get("virtualMonitors"),
                "hint": "" if actual >= count else "UAC 被拒绝或新屏没起来，手动跑一次：\n"
                        f'  pnputil /restart-device "{VDD_INSTANCE}"'}
    if denied:
        result = {"stage": "needs-admin", "configured": count, "instance": VDD_INSTANCE,
                  "hint": "配置已改，设备没重启。管理员执行一次：\n"
                          f'  pnputil /restart-device "{VDD_INSTANCE}"\n'
                          "  然后 DisplaySwitch.exe /extend；\n"
                          "  或加 --elevate 弹一次 UAC；\n"
                          "  或装一次小助手后加 --helper（之后零 UAC）：\n"
                          f"  powershell -ExecutionPolicy Bypass -File \"{HERE / 'install-helper.ps1'}\""}
        if ask:
            result["asked"] = ask_permission(
                "改虚拟屏数量需要管理员权限，您看下弹窗或命令，批一下我再继续。")
        return result

    sleep(3)
    runner(["DisplaySwitch.exe", "/extend"])
    sleep(2)
    data = status_fn()
    return {"stage": "applied", "configured": count,
            "actual": len(data.get("virtualMonitors") or []),
            "virtualMonitors": data.get("virtualMonitors")}


def status() -> dict[str, Any]:
    adapters_list = [asdict(a) for a in adapters()]
    active = active_virtual()
    canvases = [asdict(m) for m in virtual_monitors()]
    return {
        "adapters": adapters_list,
        "virtualActive": active is not None,
        "virtualAdapter": active.name if active else None,
        "monitors": [asdict(m) for m in screen.list_monitors()],
        "canvas": canvases[0] if canvases else None,
        "virtualMonitors": canvases,
        "configuredCount": configured_count(),
    }


def require_virtual(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or status()
    if not data["virtualActive"]:
        raise SystemExit(
            "当前没有启用中的虚拟显示器。\n"
            "用管理员身份运行一次：\n"
            f"  powershell -ExecutionPolicy Bypass -File \"{HERE / 'setup.ps1'}\" -Action restart\n"
            "或安装 Virtual Display Driver（VDD）后重启。"
        )
    return data


def format_status(data: dict[str, Any]) -> str:
    lines = ["# 显示适配器", ""]
    for adapter in data["adapters"]:
        if not adapter["attached"] and not adapter["virtual"]:
            continue
        kind = "虚拟" if adapter["virtual"] else "物理"
        state = "已启用" if adapter["attached"] else "未启用"
        lines.append(f"- {adapter['name']} · {adapter['description']} · {kind} · {state} · "
                     f"监视器 {len(adapter['monitors'])} 个")
    lines.append("")
    actual = len(data.get("virtualMonitors") or [])
    lines.append(f"配置：{data.get('configuredCount', 0)} 块虚拟屏；已激活：{actual} 块")
    if data["virtualActive"]:
        lines.append(f"当前画布：{data['virtualAdapter']}（{len(data['monitors'])} 块屏）")
    else:
        lines.append("当前没有启用中的虚拟屏；截图会落在物理屏上。")
    return "\n".join(lines)


def ensure(*, extend: bool = True, install: bool = False,
           runner=None, status_fn=None, sleep=None) -> dict[str, Any]:
    """确保有一块可用的虚拟屏：已启用 → 扩展 → 装驱动（可选，需 UAC）。

    runner 用来执行外部命令，测试时可注入。
    """
    import subprocess
    import time

    status_fn = status_fn or status
    sleep = sleep or time.sleep
    runner = runner or (lambda command: subprocess.run(command, capture_output=True, text=True))

    data = status_fn()
    if data["virtualActive"]:
        return {"stage": "ready", "canvas": data["canvas"],
                "adapter": data["virtualAdapter"]}

    if extend:
        runner(["DisplaySwitch.exe", "/extend"])
        sleep(2)
        data = status_fn()
        if data["virtualActive"]:
            return {"stage": "extended", "canvas": data["canvas"],
                    "adapter": data["virtualAdapter"]}

    virtual_devices = [a for a in data["adapters"] if a["virtual"]]
    if virtual_devices:
        return {"stage": "needs-restart", "adapter": virtual_devices[0]["name"],
                "hint": "驱动在，但监视器没激活。管理员运行一次："
                        "powershell -ExecutionPolicy Bypass -File "
                        f"\"{HERE / 'setup.ps1'}\" -Action restart"}

    if not install:
        return {"stage": "needs-install",
                "hint": "没有虚拟显示驱动。管理员运行一次："
                        "powershell -ExecutionPolicy Bypass -File "
                        f"\"{HERE / 'install-vdd.ps1'}\" -Action install"}

    installer = HERE / "install-vdd.ps1"
    ps = ("Start-Process powershell -Verb RunAs -Wait -ArgumentList "
          f"@('-ExecutionPolicy','Bypass','-File','{installer}','-Action','install')")
    result = runner(["powershell", "-NoProfile", "-Command", ps])
    sleep(3)
    data = status_fn()
    if data["virtualActive"]:
        return {"stage": "installed", "canvas": data["canvas"],
                "adapter": data["virtualAdapter"]}
    return {"stage": "install-failed",
            "detail": getattr(result, "stderr", "") or "",
            "hint": "UAC 被拒绝或安装失败；改用管理员窗口手动运行 install-vdd.ps1"}


def canvas(*, ensure_first: bool = False, index: int = 1) -> dict[str, Any]:
    if ensure_first:
        ensure()
    data = status()
    if not data["virtualActive"]:
        raise SystemExit("没有启用中的虚拟屏，先运行 virtualscreen.py ensure")
    monitors = data.get("virtualMonitors") or []
    if not 1 <= index <= len(monitors):
        raise SystemExit(f"只有 {len(monitors)} 块虚拟屏，要第 {index} 块没有")
    return monitors[index - 1]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="虚拟显示器状态与画布选择")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    sub.add_parser("require", help="没有虚拟屏时以退出码 1 结束")
    p_set = sub.add_parser("set", help="设置虚拟屏分辨率")
    p_set.add_argument("--width", type=int, default=1600)
    p_set.add_argument("--height", type=int, default=900)
    p_ensure = sub.add_parser("ensure", help="确保有虚拟屏：扩展/提示安装")
    p_ensure.add_argument("--no-extend", action="store_true")
    p_ensure.add_argument("--install", action="store_true", help="需要时用 UAC 启动安装脚本")
    p_ensure.add_argument("--monitors", type=int, help="目标数量：不够就先改配置并重启设备")
    p_ensure.add_argument("--elevate", action="store_true", help="必要时弹一次 UAC")
    p_ensure.add_argument("--helper", action="store_true", help="用 SYSTEM 小助手重启设备")
    p_canvas = sub.add_parser("canvas", help="输出画布编号和矩形")
    p_canvas.add_argument("--ensure", action="store_true")
    p_canvas.add_argument("--index", type=int, default=1, help="第几块虚拟屏，从 1 开始")
    p_count = sub.add_parser("count", help="看配置了几块虚拟屏、实际激活几块")
    p_setcount = sub.add_parser("set-count", help="决定开几块虚拟屏")
    p_setcount.add_argument("count", type=int)
    p_setcount.add_argument("--apply", action="store_true",
                            help="写入后重启显示设备（需要管理员）")
    p_setcount.add_argument("--elevate", action="store_true",
                            help="没权限时弹一次 UAC 自动重启设备")
    p_setcount.add_argument("--helper", action="store_true",
                            help="用已安装的 SYSTEM 小助手重启（零 UAC）")
    p_setcount.add_argument("--ask", action="store_true",
                            help="需要权限时让桌宠弹气泡向人求授权")
    sub.add_parser("helper-status", help="看 SYSTEM 小助手装没装")
    p_restart = sub.add_parser("request-restart", help="请 SYSTEM 小助手重启显示设备")
    p_restart.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)

    if args.cmd == "helper-status":
        print(json.dumps(helper_status(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "request-restart":
        print(json.dumps(request_restart(args.timeout), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "count":
        print(json.dumps({"configured": configured_count(),
                          "actual": len(virtual_monitors())}, ensure_ascii=False))
        return 0

    if args.cmd == "set-count":
        try:
            result = set_count(args.count, apply=args.apply, elevate=args.elevate,
                               helper=args.helper, ask=args.ask)
        except (ValueError, SystemExit) as exc:
            print(str(exc))
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["stage"] in {"unchanged", "applied", "pending"} else 1

    if args.cmd == "ensure":
        if args.monitors and configured_count() < args.monitors:
            changed = set_count(args.monitors, apply=True, elevate=args.elevate,
                                helper=args.helper, ask=True)
            print(json.dumps({"setCount": changed}, ensure_ascii=False, indent=2))
            if changed["stage"] not in {"applied", "unchanged"}:
                return 1
        result = ensure(extend=not args.no_extend, install=args.install)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["stage"] in {"ready", "extended", "installed"} else 1

    if args.cmd == "canvas":
        try:
            print(json.dumps(canvas(ensure_first=args.ensure, index=args.index),
                             ensure_ascii=False))
            return 0
        except SystemExit as exc:
            print(str(exc))
            return 1

    data = status()
    if args.cmd == "status":
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else format_status(data))
        return 0
    if args.cmd == "set":
        require_virtual(data)
        result = screen.set_mode(data["virtualAdapter"], args.width, args.height)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    require_virtual(data)
    print(f"虚拟屏可用：{data['virtualAdapter']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
