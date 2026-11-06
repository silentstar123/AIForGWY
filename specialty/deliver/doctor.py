# -*- coding: utf-8 -*-
"""交付自检：到客户现场先跑这一条，把环境问题一次说清。

    python specialty/deliver/doctor.py
    python specialty/deliver/doctor.py --json

检查：Python 版本、依赖、OCR、显示器与 DPI、虚拟屏与小助手、关键路径写权限、磁盘空间。
任何 FAIL 都会让退出码为 1。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "screen"))
sys.path.insert(0, str(ROOT / "virtualscreen"))

CHECKS: list[dict] = []


def add(name: str, status: str, detail: str, fix: str = "") -> None:
    CHECKS.append({"name": name, "status": status, "detail": detail, "fix": fix})


def check_python() -> None:
    version = sys.version_info
    ok = version >= (3, 10)
    add("Python", "OK" if ok else "FAIL",
        f"{version.major}.{version.minor}.{version.micro}",
        "" if ok else "装 Python 3.12，并勾选 Add to PATH")


def check_deps() -> None:
    modules = {
        "docx": "python-docx",
        "fitz": "PyMuPDF",
        "PIL": "Pillow",
        "mss": "mss",
        "rapidocr_onnxruntime": "rapidocr_onnxruntime",
        "win32api": "pywin32",
    }
    missing = [package for module, package in modules.items()
               if importlib.util.find_spec(module) is None]
    if missing:
        add("依赖", "FAIL", "缺 " + "、".join(missing),
            "pip install -r specialty/requirements.txt")
    else:
        add("依赖", "OK", f"{len(modules)} 个模块齐全")


def check_ocr() -> None:
    if importlib.util.find_spec("rapidocr_onnxruntime") is None:
        add("OCR", "WARN", "未安装，扫描件只能退回文件名", "pip install rapidocr_onnxruntime")
        return
    add("OCR", "OK", "rapidocr 可用")


def check_display() -> None:
    try:
        import screen

        monitors = screen.list_monitors()
        dpi = [screen.dpi_for_monitor(m.index) for m in monitors]
        detail = "；".join(f"{m.index}: {m.width}x{m.height}@{m.left},{m.top} dpi{d}"
                          for m, d in zip(monitors, dpi))
        scaled = [d for d in dpi if d != 96]
        add("显示器", "WARN" if scaled else "OK", detail,
            "有非 100% 缩放，坐标可能偏，现场先核实" if scaled else "")
    except Exception as exc:
        add("显示器", "FAIL", f"枚举失败：{exc}")


def check_virtual() -> None:
    try:
        import virtualscreen

        configured = virtualscreen.configured_count()
        actual = len(virtualscreen.virtual_monitors())
        helper = virtualscreen.helper_status()
        detail = f"配置 {configured} 块，激活 {actual} 块，小助手 {'已装' if helper['installed'] else '未装'}"
        status = "OK" if actual > 0 else "WARN"
        add("虚拟屏", status, detail,
            "" if actual else "python specialty/virtualscreen/virtualscreen.py ensure")
    except Exception as exc:
        add("虚拟屏", "FAIL", f"检测失败：{exc}")


def check_paths() -> None:
    try:
        with tempfile.NamedTemporaryFile(dir=ROOT, prefix=".doctor-", delete=True) as handle:
            handle.write(b"ok")
        add("工作目录写权限", "OK", str(ROOT))
    except Exception as exc:
        add("工作目录写权限", "FAIL", str(exc), "换目录或修 ACL")
    vdd = Path(r"C:\VirtualDisplayDriver\vdd_settings.xml")
    if vdd.is_file():
        add("VDD 配置", "OK", str(vdd))
    else:
        add("VDD 配置", "WARN", "没找到 vdd_settings.xml", "先装 Virtual Display Driver")


def check_disk() -> None:
    usage = shutil.disk_usage(ROOT)
    free = usage.free / (1024 ** 3)
    add("磁盘", "OK" if free >= 2 else "WARN", f"剩余 {free:.1f} GB",
        "" if free >= 2 else "空间偏小，截图和 profile 会占地方")


def run_checks() -> list[dict]:
    for func in (check_python, check_deps, check_ocr, check_display, check_virtual,
                 check_paths, check_disk):
        try:
            func()
        except Exception as exc:
            add(func.__name__, "FAIL", f"检查异常：{exc}")
    return CHECKS


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="交付自检")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    checks = run_checks()
    failed = [c for c in checks if c["status"] == "FAIL"]
    warned = [c for c in checks if c["status"] == "WARN"]
    if args.json:
        print(json.dumps({"checks": checks, "failed": len(failed),
                          "warned": len(warned)}, ensure_ascii=False, indent=2))
    else:
        symbols = {"OK": "✓", "WARN": "!", "FAIL": "✗"}
        for check in checks:
            line = f"{symbols[check['status']]} {check['name']}: {check['detail']}"
            print(line)
            if check["fix"]:
                print(f"    → {check['fix']}")
        print(f"\n合计 {len(checks)} 项：{len(failed)} 失败，{len(warned)} 提醒")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
