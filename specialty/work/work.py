# -*- coding: utf-8 -*-
r"""工作台：把一件活拆成步骤、留痕、收尾出报告。

一次会话一个目录，记录做了什么、产出了什么文件、截图在哪：

    python specialty/work/work.py start --title "处理今日收文"
    python specialty/work/work.py step --note "查收今日文件" --artifact G:\...\清单.md
    python specialty/work/work.py status
    python specialty/work/work.py finish --summary "已收 6 件，转发出 1 份"
    python specialty/work/work.py report
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "sessions"
PET = HERE.parent / "pet" / "pet.py"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _session_dir(root: Path, name: str | None = None) -> Path:
    if name:
        return root / name
    return root / datetime.now().strftime("%Y%m%d-%H%M%S")


def new_session(root: Path, title: str, *, pet: bool = True) -> dict:
    folder = _session_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    data = {"title": title, "startedAt": _now(), "steps": [],
            "finishedAt": None, "summary": ""}
    _save(folder, data)
    if pet:
        _bubble(f"开工：{title}")
    return {"session": folder.name, **data}


def _save(folder: Path, data: dict) -> None:
    (folder / "session.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(folder: Path) -> dict:
    path = folder / "session.json"
    if not path.is_file():
        raise SystemExit(f"不是工作会话目录：{folder}")
    return json.loads(path.read_text(encoding="utf-8"))


def add_step(folder: Path, note: str, *, artifacts: list[str] | None = None,
             shot: str | None = None, pet: bool = False) -> dict:
    data = load(folder)
    data["steps"].append({"at": _now(), "note": note,
                          "artifacts": artifacts or [], "shot": shot})
    _save(folder, data)
    if pet:
        _bubble(note)
    return data


def finish(folder: Path, summary: str, *, pet: bool = True) -> dict:
    data = load(folder)
    data["finishedAt"] = _now()
    data["summary"] = summary
    _save(folder, data)
    if pet:
        _bubble(f"收工：{summary}"[:60])
        _remember(f"工作记录｜{data['title']}｜{summary}")
    return data


def _remember(text: str) -> None:
    """把收工结果记进桌宠的记忆；桌宠没开就跳过。"""
    if not PET.is_file():
        return
    try:
        subprocess.run([sys.executable, str(PET), "remember", text],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=8)
    except Exception:
        pass


def report(folder: Path) -> str:
    data = load(folder)
    lines = [f"# {data['title']}", "",
             f"- 开始：{data['startedAt']}",
             f"- 结束：{data.get('finishedAt') or '进行中'}"]
    if data.get("summary"):
        lines.append(f"- 结果：{data['summary']}")
    lines += ["", "## 步骤", ""]
    if not data["steps"]:
        lines.append("（还没有步骤）")
    for index, step in enumerate(data["steps"], 1):
        lines.append(f"{index}. {step['at'][11:]}  {step['note']}")
        for item in step.get("artifacts") or []:
            lines.append(f"   - 产出：{item}")
        if step.get("shot"):
            lines.append(f"   - 截图：{step['shot']}")
    return "\n".join(lines)


def recent(root: Path, limit: int = 10) -> list[str]:
    if not root.is_dir():
        return []
    folders = sorted((p for p in root.iterdir() if (p / "session.json").is_file()),
                     key=lambda p: p.name, reverse=True)
    return [p.name for p in folders[:limit]]


def _bubble(text: str) -> None:
    """有桌宠就弹个气泡，没开就算了。"""
    if not PET.is_file():
        return
    try:
        subprocess.run([sys.executable, str(PET), "bubble", text],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=8)
    except Exception:
        pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="工作台：拆步骤、留痕、出报告")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--session", help="指定已有会话目录名")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start")
    p_start.add_argument("--title", required=True)
    p_start.add_argument("--no-pet", action="store_true")
    p_step = sub.add_parser("step")
    p_step.add_argument("--note", required=True)
    p_step.add_argument("--artifact", action="append", default=[])
    p_step.add_argument("--shot")
    p_step.add_argument("--pet", action="store_true")
    sub.add_parser("status")
    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--summary", required=True)
    sub.add_parser("report")
    p_list = sub.add_parser("list")

    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "start":
        print(json.dumps(new_session(root, args.title, pet=not args.no_pet),
                         ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "list":
        print(json.dumps(recent(root), ensure_ascii=False))
        return 0

    if args.session:
        folder = _session_dir(root, args.session)
    else:
        names = recent(root, 1)
        if not names:
            raise SystemExit("还没有工作会话，先运行 start")
        folder = root / names[0]

    if args.cmd == "step":
        print(json.dumps(add_step(folder, args.note, artifacts=args.artifact,
                                  shot=args.shot, pet=args.pet), ensure_ascii=False))
        return 0
    if args.cmd == "status":
        data = load(folder)
        print(f"{data['title']} · {len(data['steps'])} 步 · "
              f"{'已收工' if data.get('finishedAt') else '进行中'}")
        return 0
    if args.cmd == "finish":
        print(json.dumps(finish(folder, args.summary), ensure_ascii=False))
        return 0
    print(report(folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
