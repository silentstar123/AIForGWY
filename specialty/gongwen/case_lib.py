# -*- coding: utf-8 -*-
"""从本机公文里提取版式，建立可检索的案例库。

    python specialty/gongwen/case_lib.py scan
    python specialty/gongwen/case_lib.py list --kind 通知
    python specialty/gongwen/case_lib.py profile --kind 通知
    python specialty/gongwen/case_lib.py brief --kind 通知
    python specialty/gongwen/case_lib.py match --kind 报告 --keyword 场景汇

只读本地 .docx，不联网。案例库保存在 cases/ 下，含原文摘录，默认不入 git。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
LIBRARY = CASES / "library.json"
PROFILES = CASES / "profiles"
INDEX_MD = CASES / "案例库.md"

KINDS = ("转发通知", "请示", "批复", "报告", "通知", "函", "纪要", "方案", "总结",
         "意见", "讲话", "汇报", "简报", "通报", "公告")
DATE_RE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
HEAD_RE = re.compile(r"^([一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+[.、])")


def kind_of(name: str, text: str = "") -> str:
    haystack = f"{name} {text[:200]}"
    if (text or name).strip().endswith("的函"):
        return "函"
    if "转发" in haystack and ("关于转发" in haystack or "转发省" in haystack):
        return "转发通知"
    for kind in KINDS:
        if kind in name:
            return kind
    for kind in KINDS:
        if kind in (text or "")[:200]:
            return kind
    return "其他"


def east_font(run) -> str:
    try:
        rpr = run._element.rPr
        if rpr is not None and rpr.rFonts is not None:
            return rpr.rFonts.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia") or ""
    except Exception:
        pass
    return run.font.name or ""


def para_font(paragraph) -> tuple[str, float | None]:
    for run in paragraph.runs:
        if run.text.strip():
            return east_font(run), run.font.size.pt if run.font.size else None
    return "", None


def pick_title(paragraphs) -> tuple[str, int, int]:
    """标题不一定在第一段：请示先有文号/签发人，通知先有发文机关标志。"""
    best_index = 0
    best_size = 0.0
    for index, paragraph in enumerate(paragraphs[:6]):
        text = paragraph.text.strip()
        if not text:
            continue
        _font, size = para_font(paragraph)
        if size and size >= 20:
            if len(text) <= 15 and index + 1 < len(paragraphs):
                _next_font, next_size = para_font(paragraphs[index + 1])
                if next_size and next_size >= 20:
                    continue
            if size > best_size:
                best_index, best_size = index, size
    if best_size == 0:
        return paragraphs[0].text.strip(), 0, 0

    title = paragraphs[best_index].text.strip()
    end = best_index
    font, _size = para_font(paragraphs[best_index])
    for index in range(best_index + 1, min(best_index + 3, len(paragraphs))):
        text = paragraphs[index].text.strip()
        if not text or text.endswith("：") or len(title) >= 45:
            break
        next_font, next_size = para_font(paragraphs[index])
        if next_size and next_size >= 20 and (next_font == font or not next_font):
            title += text
            end = index
        else:
            break
    return title, best_index, end


def extract(path: Path) -> dict | None:
    from docx import Document

    try:
        doc = Document(str(path))
    except Exception:
        return None
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return None
    text = "\n".join(p.text.strip() for p in paragraphs)
    if not 120 <= len(text) <= 20000:
        return None

    section = doc.sections[0]
    title, title_index, title_end = pick_title(paragraphs)
    title_p = paragraphs[title_index]
    title_font, title_size = para_font(title_p)
    title_align = int(title_p.alignment) if title_p.alignment is not None else None

    body_p = next((p for p in paragraphs[title_end + 1:] if len(p.text.strip()) > 20),
                  paragraphs[min(title_end + 1, len(paragraphs) - 1)])
    body_font, body_size = para_font(body_p)
    indent = body_p.paragraph_format.first_line_indent
    indent_pt = round(indent.pt, 1) if indent is not None else None
    if not indent_pt and body_size:
        indent_pt = round(body_size * 2, 1)  # 正文两字符，样式缩进也算
    line = body_p.paragraph_format.line_spacing
    line_pt = round(line.pt, 1) if hasattr(line, "pt") else line

    recipient = ""
    for p in paragraphs[title_end + 1:title_end + 6]:
        t = p.text.strip()
        if t.endswith("：") and len(t) <= 40:
            recipient = t
            break

    date = ""
    signature = ""
    for p in reversed(paragraphs[-4:]):
        t = p.text.strip()
        if DATE_RE.search(t):
            date = t
        elif len(t) <= 40 and not signature:
            signature = t

    headings = [re.split(r"[。；]", p.text.strip())[0][:40]
                for p in paragraphs if HEAD_RE.match(p.text.strip())][:8]
    tail = [p.text.strip() for p in paragraphs[-5:]]

    return {
        "title": title,
        "titleFont": title_font,
        "titleSize": title_size,
        "titleAlign": title_align,
        "bodyFont": body_font,
        "bodySize": body_size,
        "indentPt": indent_pt,
        "lineSpacing": line_pt,
        "marginsCm": [round(section.top_margin.cm, 2), round(section.bottom_margin.cm, 2),
                      round(section.left_margin.cm, 2), round(section.right_margin.cm, 2)],
        "recipient": recipient,
        "date": date,
        "signature": signature,
        "headings": headings,
        "tail": tail,
        "chars": len(text),
        "tables": len(doc.tables),
        "preview": text[:300],
    }


def score(entry: dict) -> int:
    value = 0
    if entry["titleSize"] and entry["titleSize"] >= 18:
        value += 2
    if entry["titleFont"] in ("方正小标宋简体", "方正小标宋_GBK", "宋体", "黑体"):
        value += 1
    if entry["titleAlign"] == 1:
        value += 1
    if entry["bodyFont"] in ("仿宋_GB2312", "仿宋", "FangSong_GB2312"):
        value += 2
    if entry["bodySize"] and 14 <= entry["bodySize"] <= 18:
        value += 1
    if entry["indentPt"] and 28 <= entry["indentPt"] <= 36:
        value += 1
    top, bottom, left, right = entry["marginsCm"]
    if 3.0 <= top <= 3.8 and 3.0 <= bottom <= 3.8 and 2.4 <= left <= 3.0:
        value += 1
    if entry["recipient"]:
        value += 1
    if entry["date"]:
        value += 1
    if entry["tables"] <= 2:
        value += 1
    if entry["chars"] <= 8000:
        value += 1
    return value


def scan(roots: list[Path], *, min_score: int = 8, per_kind: int = 8) -> dict:
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.docx"):
            name = path.name
            if name.startswith("~$"):
                continue
            if path.stat().st_size < 8_000 or path.stat().st_size > 3_000_000:
                continue
            if any(bad in name for bad in ("申报", "评价材料", "统计表", "附件", "模板", "空白")):
                continue
            if kind_of(name) == "其他":
                continue
            candidates.append(path)

    entries: list[dict] = []
    seen: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    for path in candidates:
        kind = kind_of(path.name)
        try:
            data = extract(path)
        except Exception:
            continue
        if not data:
            continue
        kind = kind_of(path.name, data["title"]) or kind
        value = score(data)
        if value < min_score:
            continue
        digest = hashlib.sha1((data["title"] + str(data["chars"])).encode("utf-8")).hexdigest()[:10]
        if digest in seen:
            continue
        title_key = (kind, re.sub(r"\s+", "", data["title"]))
        if title_key in seen_titles:
            continue
        seen.add(digest)
        seen_titles.add(title_key)
        entries.append({
            "id": digest,
            "kind": kind,
            "file": str(path),
            "name": path.name,
            "score": value,
            **data,
        })

    entries.sort(key=lambda item: (-item["score"], item["kind"], item["chars"]))
    kept: list[dict] = []
    counts: Counter[str] = Counter()
    for entry in entries:
        if counts[entry["kind"]] >= per_kind:
            continue
        counts[entry["kind"]] += 1
        kept.append(entry)

    library = {
        "scannedAt": datetime.now().isoformat(timespec="seconds"),
        "roots": [str(root) for root in roots],
        "total": len(kept),
        "entries": kept,
    }
    CASES.mkdir(parents=True, exist_ok=True)
    LIBRARY.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")
    write_profiles(kept)
    write_index(kept)
    return {"total": len(kept), "kinds": dict(counts)}


def _median(values: list[float]) -> float | None:
    values = sorted(value for value in values if value is not None)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else round((values[middle - 1] + values[middle]) / 2, 2)


def _mode(values, default: str = "") -> str:
    counter = Counter(value for value in values if value)
    return counter.most_common(1)[0][0] if counter else default


def write_profiles(entries: list[dict]) -> None:
    PROFILES.mkdir(parents=True, exist_ok=True)
    for kind in sorted({entry["kind"] for entry in entries}):
        group = [entry for entry in entries if entry["kind"] == kind]
        profile = {
            "kind": kind,
            "sampleCount": len(group),
            "titleFont": _mode(entry["titleFont"] for entry in group),
            "titleSize": _median([entry["titleSize"] for entry in group]),
            "bodyFont": _mode(entry["bodyFont"] for entry in group),
            "bodySize": _median([entry["bodySize"] for entry in group]),
            "indentPt": _median([entry["indentPt"] for entry in group]),
            "lineSpacing": _median([entry["lineSpacing"] for entry in group if isinstance(entry["lineSpacing"], (int, float))]),
            "marginsCm": [_median([entry["marginsCm"][index] for entry in group]) for index in range(4)],
            "samples": [{"id": entry["id"], "title": entry["title"], "file": entry["file"],
                         "headings": entry["headings"][:4]} for entry in group[:4]],
        }
        (PROFILES / f"{kind}.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def write_index(entries: list[dict]) -> None:
    lines = ["# 公文案例库", "",
             f"扫描时间：{datetime.now():%Y-%m-%d %H:%M}；共 {len(entries)} 篇。", "",
             "| 文种 | 标题 | 版式分 | 文件 |", "|---|---|---:|---|"]
    for entry in entries:
        title = entry["title"].replace("|", "｜")[:40]
        lines.append(f"| {entry['kind']} | {title} | {entry['score']} | `{entry['file']}` |")
    lines += ["", "## 各文种版式", ""]
    for path in sorted(PROFILES.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        lines += [f"### {profile['kind']}（{profile['sampleCount']} 篇）", "",
                  f"- 标题：{profile['titleFont']} {profile['titleSize']} pt，居中",
                  f"- 正文：{profile['bodyFont']} {profile['bodySize']} pt，首行缩进 {profile['indentPt']} pt",
                  f"- 页边距：上 {profile['marginsCm'][0]} / 下 {profile['marginsCm'][1]} / 左 {profile['marginsCm'][2]} / 右 {profile['marginsCm'][3]} cm",
                  ""]
    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")


def load() -> dict:
    if not LIBRARY.is_file():
        raise SystemExit("案例库还没建，先跑：python specialty/gongwen/case_lib.py scan")
    return json.loads(LIBRARY.read_text(encoding="utf-8"))


def match(entries: list[dict], kind: str = "", keyword: str = "", limit: int = 5) -> list[dict]:
    hits = []
    for entry in entries:
        if kind and entry["kind"] != kind:
            continue
        haystack = entry["title"] + entry["preview"] + entry["name"]
        if keyword and keyword not in haystack:
            continue
        hits.append(entry)
    hits.sort(key=lambda item: -item["score"])
    return hits[:limit]


def brief(kind: str) -> str:
    profile_path = PROFILES / f"{kind}.json"
    if not profile_path.is_file():
        return f"没有 {kind} 的案例。"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    lines = [f"# {kind}写作参考", "",
             f"- 标题：{profile['titleFont']} {profile['titleSize']} pt，居中",
             f"- 正文：{profile['bodyFont']} {profile['bodySize']} pt",
             f"- 首行缩进：{profile['indentPt']} pt",
             f"- 行距：{profile['lineSpacing']}",
             f"- 页边距（上/下/左/右 cm）：{' / '.join(str(value) for value in profile['marginsCm'])}",
             "", "## 参考篇目"]
    for sample in profile["samples"]:
        lines.append(f"- {sample['title']}（{sample['file']}）")
        if sample["headings"]:
            lines.append(f"  - 结构：{'；'.join(sample['headings'])}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="公文案例库")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--roots", nargs="*", default=[r"G:\办公", str(Path.home() / "Desktop")])
    p_scan.add_argument("--min-score", type=int, default=8)
    p_scan.add_argument("--per-kind", type=int, default=8)
    p_list = sub.add_parser("list")
    p_list.add_argument("--kind", default="")
    p_list.add_argument("--limit", type=int, default=20)
    p_show = sub.add_parser("show")
    p_show.add_argument("id")
    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--kind", required=True)
    p_brief = sub.add_parser("brief")
    p_brief.add_argument("--kind", required=True)
    p_match = sub.add_parser("match")
    p_match.add_argument("--kind", default="")
    p_match.add_argument("--keyword", default="")
    p_match.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    if args.cmd == "scan":
        result = scan([Path(root) for root in args.roots], min_score=args.min_score,
                      per_kind=args.per_kind)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    library = load()
    entries = library["entries"]
    if args.cmd == "list":
        for entry in entries:
            if args.kind and entry["kind"] != args.kind:
                continue
            print(f"{entry['id']}  {entry['kind']}  {entry['score']}  {entry['title'][:50]}")
            if not args.kind:
                continue
        return 0
    if args.cmd == "show":
        entry = next((item for item in entries if item["id"] == args.id), None)
        if not entry:
            raise SystemExit("没找到这个 id")
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "profile":
        path = PROFILES / f"{args.kind}.json"
        if not path.is_file():
            raise SystemExit(f"没有 {args.kind} 的版式")
        print(path.read_text(encoding="utf-8"))
        return 0
    if args.cmd == "brief":
        print(brief(args.kind))
        return 0
    for entry in match(entries, args.kind, args.keyword, args.limit):
        print(f"{entry['id']}  {entry['kind']}  {entry['score']}  {entry['title'][:60]}")
        print(f"  {entry['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
