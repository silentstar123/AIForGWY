# -*- coding: utf-8 -*-
"""DDL 任务台账：记录波洛日常要办的事，支持一次性和周期任务。

数据只存本机 tasks.json，不外传。所有命令可用 --on YYYY-MM-DD 指定"今天"便于测试。
"""
import argparse
import calendar
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "tasks.json"

WEEKDAYS = "一二三四五六日"


def _load():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"seq": 0, "tasks": []}


def _save(data):
    STORE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _parse_date(s):
    return date.fromisoformat(s)


_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def parse_recur(text):
    """把口语周期写成结构化 recur。认不出返回 None。

    支持：每月10号/每月十日、每周一…每周日、每天/每日、每年11月9日。
    """
    t = text.strip()
    m = re.fullmatch(r"每月\s*(\d{1,2})\s*[号日]?", t)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 31:
            return {"freq": "monthly", "day": d}
        return None
    m = re.fullmatch(r"每周\s*([一二三四五六日天])", t)
    if m:
        return {"freq": "weekly", "weekday": _CN_NUM[m.group(1)] % 7}  # 日=0
    if t in ("每天", "每日"):
        return {"freq": "daily"}
    m = re.fullmatch(r"每年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]?", t)
    if m:
        return {"freq": "yearly", "month": int(m.group(1)), "day": int(m.group(2))}
    return None


def occurrence_on(recur, today):
    """返回该周期任务在 today 所在周期内的应办日期（可能晚于 today）。"""
    f = recur["freq"]
    if f == "daily":
        return today
    if f == "weekly":
        delta = (today.weekday() - recur["weekday"]) % 7
        return today - timedelta(days=delta)
    if f == "monthly":
        last = calendar.monthrange(today.year, today.month)[1]
        return today.replace(day=min(recur["day"], last))
    if f == "yearly":
        try:
            return today.replace(month=recur["month"], day=recur["day"])
        except ValueError:  # 闰日等，退到当月最后一天
            last = calendar.monthrange(today.year, recur["month"])[1]
            return date(today.year, recur["month"], last)
    raise ValueError(f"未知周期: {f}")


def describe_recur(recur):
    f = recur["freq"]
    if f == "daily":
        return "每天"
    if f == "weekly":
        return f"每周{WEEKDAYS[recur['weekday']]}"
    if f == "monthly":
        return f"每月{recur['day']}号"
    if f == "yearly":
        return f"每年{recur['month']}月{recur['day']}号"
    return str(recur)


def _status(task, today):
    """返回 (应办日期或None, 状态标签)。状态：逾期/今日/临近N天/已完成/未到期。"""
    if task["kind"] == "once":
        due = _parse_date(task["due"])
        if task.get("done"):
            return due, "已完成"
        diff = (due - today).days
        if diff < 0:
            return due, f"逾期{-diff}天"
        if diff == 0:
            return due, "今日截止"
        return due, f"还剩{diff}天"
    occ = occurrence_on(task["recur"], today)
    key = occ.isoformat()
    if key in task.get("doneDates", []):
        return occ, "本期已完成"
    diff = (occ - today).days
    if diff < 0:
        return occ, f"逾期{-diff}天"
    if diff == 0:
        return occ, "今日"
    return occ, f"{diff}天后"


def cmd_add(args):
    data = _load()
    data["seq"] += 1
    task = {
        "id": f"t{data['seq']:03d}",
        "title": args.title,
        "note": args.note or "",
        "created": date.today().isoformat(),
    }
    if args.recur:
        recur = parse_recur(args.recur)
        if not recur:
            print(f"认不出周期「{args.recur}」，支持：每月10号 / 每周一 / 每天 / 每年11月9日")
            sys.exit(2)
        task["kind"] = "recurring"
        task["recur"] = recur
        task["doneDates"] = []
    else:
        if not args.due:
            print("一次性任务要有截止日期：--due 2026-11-09；周期任务用 --recur 每月10号")
            sys.exit(2)
        task["kind"] = "once"
        task["due"] = args.due
        task["done"] = False
    data["tasks"].append(task)
    _save(data)
    tag = describe_recur(task["recur"]) if task["kind"] == "recurring" else f"截止 {task['due']}"
    print(f"已记录 [{task['id']}] {task['title']}（{tag}）")


def _iter_due(tasks, today, window=3):
    """今天该提醒的：(task, 应办日期, 状态标签)，按应办日期升序。"""
    rows = []
    for t in tasks:
        occ, status = _status(t, today)
        if t["kind"] == "once":
            if t.get("done"):
                continue
            if (occ - today).days <= window:  # 逾期/今日/临近窗口内才提醒
                rows.append((t, occ, status))
        else:
            # 只提醒本期应办（含今天之后的 window 天内）；逾期和今天必提醒
            if (occ - today).days <= window:
                rows.append((t, occ, status))
    rows.sort(key=lambda r: r[1])
    return rows


def cmd_today(args):
    data = _load()
    rows = _iter_due(data["tasks"], _parse_date(args.on), args.window)
    if not rows:
        print("今天没有待办。")
        return
    print(f"{'='*40}\n今日待办（{_parse_date(args.on).strftime('%Y-%m-%d %a')}）\n{'='*40}")
    for t, occ, status in rows:
        note = f" ｜ {t['note']}" if t.get("note") else ""
        print(f"[{t['id']}] {status}｜{t['title']}｜应办 {occ.isoformat()}{note}")
    print("完成的直接回复序号或事项，我画勾。")


def _find(tasks, key):
    for t in tasks:
        if t["id"] == key:
            return t
    if key.isdigit():
        n = int(key)
        if 1 <= n <= len(tasks):
            return tasks[n - 1]
    return None


def cmd_done(args):
    data = _load()
    today = _parse_date(args.on)
    task = _find(data["tasks"], args.id)
    if not task:
        print(f"没找到任务 {args.id}")
        sys.exit(1)
    if task["kind"] == "once":
        task["done"] = True
        task["doneDate"] = today.isoformat()
    else:
        occ = occurrence_on(task["recur"], today)
        key = occ.isoformat()
        if key not in task["doneDates"]:
            task["doneDates"].append(key)
        task["doneDates"].sort()
    _save(data)
    print(f"✔ 已勾选 [{task['id']}] {task['title']}")


def cmd_list(args):
    data = _load()
    if not data["tasks"]:
        print("台账是空的。")
        return
    today = _parse_date(args.on)
    for t in data["tasks"]:
        occ, status = _status(t, today)
        if t["kind"] == "once":
            tag = f"截止 {t['due']}"
        else:
            tag = describe_recur(t["recur"])
        print(f"[{t['id']}] {t['title']}｜{tag}｜{status}")


def cmd_remove(args):
    data = _load()
    task = _find(data["tasks"], args.id)
    if not task:
        print(f"没找到任务 {args.id}")
        sys.exit(1)
    data["tasks"].remove(task)
    _save(data)
    print(f"已删除 [{task['id']}] {task['title']}")


def main(argv=None):
    p = argparse.ArgumentParser(description="DDL 任务台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("add", help="记一件事")
    sp.add_argument("title")
    sp.add_argument("--due", help="截止日期 YYYY-MM-DD（一次性任务）")
    sp.add_argument("--recur", help="周期：每月10号 / 每周一 / 每天 / 每年11月9日")
    sp.add_argument("--note", help="备注")
    sp.set_defaults(fn=cmd_add)

    sp = sub.add_parser("today", help="今天该办什么")
    sp.add_argument("--on", default=date.today().isoformat())
    sp.add_argument("--window", type=int, default=3, help="临近提醒窗口（天）")
    sp.set_defaults(fn=cmd_today)

    sp = sub.add_parser("list", help="全部任务")
    sp.add_argument("--on", default=date.today().isoformat())
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("done", help="画勾完成")
    sp.add_argument("id", help="任务 id（t003）或 list 里的序号")
    sp.add_argument("--on", default=date.today().isoformat())
    sp.set_defaults(fn=cmd_done)

    sp = sub.add_parser("remove", help="删除任务")
    sp.add_argument("id")
    sp.set_defaults(fn=cmd_remove)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
