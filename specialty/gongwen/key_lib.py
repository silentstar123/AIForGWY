# -*- coding: utf-8 -*-
"""重点文库：从 G:\办公\办公 和 G:\高技术 里学习本人的写法。

    python specialty/gongwen/key_lib.py build
    python specialty/gongwen/key_lib.py style
    python specialty/gongwen/key_lib.py brief --kind 通知
    python specialty/gongwen/key_lib.py match --kind 报告 --keyword 场景汇

只读本地 .docx，不联网。重点文库含原文摘录和路径，默认不入 git。
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
sys.path.insert(0, str(HERE))

import case_lib  # noqa: E402

ROOTS = [Path(r"G:\办公\办公"), Path(r"G:\高技术")]
OUT = HERE / "cases" / "key"
LIBRARY = OUT / "library.json"
STYLE_MD = OUT / "style.md"
INDEX_MD = OUT / "重点文库.md"

KINDS = ("纪要", "专报", "通知", "请示", "报告", "函", "汇报", "总结", "方案", "意见", "讲话")
SKIP_DIRS = ("企业技术中心管理", "申报", "评价材料", "统计表")
SKIP_NAMES = ("申报", "评价材料", "统计表", "附件", "模板", "空白", "副本", "~$")

PHRASES = ("现将", "根据", "按照", "为确保", "为进一步", "一是", "二是", "三是", "同时", "此外",
           "下一步", "截至目前", "现将有关事项通知如下", "请认真贯彻执行",
           "请遵照执行", "特此通知", "妥否，请批示", "特此报告", "请予函复",
           "经研究", "会议指出", "会议强调", "会议要求", "会议议定")


def opening_class(text: str) -> str:
    for prefix in ("为", "根据", "按照", "现将", "近日", "近年来", "经研究"):
        if text.startswith(prefix):
            return f"{prefix}……"
    return text[:10]


def kind_of(name: str, text: str = "") -> str:
    if "专报" in name:
        return "专报"
    if "纪要" in name:
        return "纪要"
    return case_lib.kind_of(name, text)


SKIP_LINE = re.compile(
    r"(〔\d{4}〕|签发人|^[报呈][:：]|^专报[:：]|^抄送|^印发|联系人|联系电话|^信\s*息\s*中|^—|^\d{4}\s*年)")


def body_paragraphs(paragraphs: list[str]) -> list[str]:
    return [text for text in paragraphs
            if len(text) >= 12 and not text.endswith("：") and not SKIP_LINE.search(text)]


def analyze(path: Path) -> dict | None:
    from docx import Document

    try:
        doc = Document(str(path))
    except Exception:
        return None
    paras = [p for p in doc.paragraphs if p.text.strip()]
    paragraphs = [p.text.strip() for p in paras]
    text = "\n".join(paragraphs)
    if not 120 <= len(text) <= 20000:
        return None
    base = case_lib.extract(path)
    if not base:
        return None
    body = body_paragraphs(paragraphs)
    body = [item for item in body
            if item not in (base["title"], base["signature"], base["date"])
            and not re.search(r"\d{4}\s*年\s*\d{1,2}\s*月", item)
            and not item.startswith("—")]
    if not body:
        return None
    opening = ""
    closing = ""
    for item in body:
        if len(item) >= 20 and not case_lib.HEAD_RE.match(item):
            opening = item[:80]
            break
    for item in reversed(body):
        if len(item) >= 20 and not case_lib.HEAD_RE.match(item):
            closing = item[:80]
            break
    body_text = "\n".join(body)
    sentences = [part for part in re.split(r"[。！？；]", body_text) if len(part) >= 6]
    body_set = set(body)
    body_objects = [p for p in paras if p.text.strip() in body_set]
    fonts = Counter(case_lib.para_font(p)[0] for p in body_objects if case_lib.para_font(p)[0])
    sizes = Counter(case_lib.para_font(p)[1] for p in body_objects if case_lib.para_font(p)[1])
    indents = Counter(round(p.paragraph_format.first_line_indent.pt, 1)
                      for p in body_objects if p.paragraph_format.first_line_indent)
    lines = Counter(round(p.paragraph_format.line_spacing.pt, 1)
                    for p in body_objects
                    if hasattr(p.paragraph_format.line_spacing, "pt"))
    if fonts:
        base["bodyFont"] = fonts.most_common(1)[0][0]
    if sizes:
        base["bodySize"] = sizes.most_common(1)[0][0]
    if indents:
        base["indentPt"] = indents.most_common(1)[0][0]
    if lines:
        base["lineSpacing"] = lines.most_common(1)[0][0]
    phrases = {phrase: text.count(phrase) for phrase in PHRASES if phrase in text}
    return {
        **base,
        "kind": kind_of(path.name, base["title"]),
        "opening": opening,
        "closing": closing,
        "paragraphs": len(body),
        "sentences": len(sentences),
        "avgParagraph": round(sum(len(item) for item in body) / len(body), 1),
        "avgSentence": round(sum(len(item) for item in sentences) / len(sentences), 1) if sentences else 0,
        "phrases": phrases,
        "headings": base["headings"][:8],
    }


def score(entry: dict, path: Path) -> float:
    value = float(case_lib.score(entry))
    if entry["kind"] in ("纪要", "专报"):
        value += 2
    if "副主任办公会议纪要" in str(path) or "专报信息" in str(path):
        value += 3
    if "G:\\高技术" in str(path):
        value += 1
    if entry["kind"] == "其他":
        value -= 5
    return value


def build(roots: list[Path], *, min_score: int = 8, per_kind: int = 6, limit: int = 45) -> dict:
    entries: list[dict] = []
    seen_titles: set[tuple[str, str]] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.docx"):
            name = path.name
            if any(bad in name for bad in SKIP_NAMES):
                continue
            if any(part in str(path) for part in SKIP_DIRS):
                continue
            if path.stat().st_size < 8_000 or path.stat().st_size > 3_000_000:
                continue
            data = analyze(path)
            if not data or data["kind"] == "其他":
                continue
            value = score(data, path)
            if value < min_score:
                continue
            key = (data["kind"], re.sub(r"\s+", "", data["title"]),
                   data.get("date") or str(data["chars"]))
            if key in seen_titles:
                continue
            seen_titles.add(key)
            entries.append({
                "id": hashlib.sha1(
                    (data["title"] + str(data["chars"])).encode("utf-8")).hexdigest()[:10],
                "score": round(value, 1),
                "file": str(path),
                "name": name,
                **data,
            })

    entries.sort(key=lambda item: (-item["score"], item["kind"]))
    counts: Counter[str] = Counter()
    kept: list[dict] = []
    # 先保证每个文种至少两篇，再按分数补足，避免高分文种挤掉报告、纪要。
    for entry in entries:
        if counts[entry["kind"]] >= min(3, per_kind) or len(kept) >= limit:
            continue
        counts[entry["kind"]] += 1
        kept.append(entry)
    for entry in entries:
        if entry in kept:
            continue
        if counts[entry["kind"]] >= per_kind or len(kept) >= limit:
            continue
        counts[entry["kind"]] += 1
        kept.append(entry)

    OUT.mkdir(parents=True, exist_ok=True)
    LIBRARY.write_text(json.dumps({
        "builtAt": datetime.now().isoformat(timespec="seconds"),
        "roots": [str(root) for root in roots],
        "total": len(kept),
        "entries": kept,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    write_style(kept)
    write_index(kept)
    return {"total": len(kept), "kinds": dict(counts)}


def write_style(entries: list[dict]) -> None:
    paragraphs = [entry["avgParagraph"] for entry in entries]
    sentences = [entry["avgSentence"] for entry in entries]
    phrases = Counter()
    for entry in entries:
        phrases.update(entry["phrases"])
    closings = Counter(entry["closing"][:20] for entry in entries if entry["closing"])
    openings = Counter(opening_class(entry["opening"]) for entry in entries if entry["opening"])

    lines = ["# 写作风格画像", "",
             f"样本 {len(entries)} 篇，来自 `G:\\办公\\办公` 和 `G:\\高技术`。", "",
             "## 篇幅", "",
             f"- 平均段长：{round(sum(paragraphs)/len(paragraphs), 1)} 字",
             f"- 平均句长：{round(sum(sentences)/len(sentences), 1)} 字", "",
             "## 常用开头", ""]
    for text, count in openings.most_common(8):
        lines.append(f"- {text}（{count} 次）")
    lines += ["", "## 常用结尾", ""]
    for text, count in closings.most_common(8):
        lines.append(f"- {text}（{count} 次）")
    lines += ["", "## 高频表达", ""]
    for text, count in phrases.most_common(15):
        lines.append(f"- {text}：{count} 次")
    lines += ["", "## 结构习惯", ""]
    heading_samples = Counter()
    for entry in entries:
        for heading in entry["headings"]:
            heading_samples[heading[:24]] += 1
    for text, count in heading_samples.most_common(10):
        lines.append(f"- {text}（{count} 次）")
    lines += ["", "## 从样本里看写法", "",
              "- 通知/转发：先交代依据和省文件文号，再写「现将……转发给你们，请……」，附件列省文件；",
              "- 报告/汇报：先总述进展，再按「一、二、三」分块，每段先结论后事实；",
              "- 纪要：开头「会议听取了……」，议定事项逐条写承办和要求；",
              "- 函：先引对方文件标题，再表态，结尾「特此函复」或「请予函复」；",
              "- 高频节奏：一是/二是/三是、按照、现将、下一步、截至目前。"]
    STYLE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index(entries: list[dict]) -> None:
    lines = ["# 重点文库", "",
             f"构建：{datetime.now():%Y-%m-%d %H:%M}；共 {len(entries)} 篇。", "",
             "| 文种 | 标题 | 分 | 段长 | 文件 |", "|---|---|---:|---:|---|"]
    for entry in entries:
        lines.append(f"| {entry['kind']} | {entry['title'][:44]} | {entry['score']} | "
                     f"{entry['avgParagraph']} | `{entry['file']}` |")
    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")


def load() -> dict:
    if not LIBRARY.is_file():
        raise SystemExit("重点文库还没建，先跑：python specialty/gongwen/key_lib.py build")
    return json.loads(LIBRARY.read_text(encoding="utf-8"))


def brief(kind: str) -> str:
    library = load()
    group = [entry for entry in library["entries"] if entry["kind"] == kind]
    if not group:
        return f"重点文库没有 {kind} 的样本。"
    first = group[0]
    lines = [f"# {kind}重点参考", "",
             f"- 标题：{first['titleFont']} {first['titleSize']} pt，居中",
             f"- 正文：{first['bodyFont']} {first['bodySize']} pt",
             f"- 首行缩进：{first['indentPt']} pt；行距：{first['lineSpacing']}",
             f"- 页边距：{' / '.join(str(value) for value in first['marginsCm'])} cm",
             f"- 平均段长：{round(sum(e['avgParagraph'] for e in group)/len(group), 1)} 字",
             "", "## 参考篇目"]
    for entry in group:
        lines.append(f"- {entry['title']}（{entry['file']}）")
        lines.append(f"  - 开头：{entry['opening']}")
        lines.append(f"  - 结尾：{entry['closing']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="重点文库")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_build = sub.add_parser("build")
    p_build.add_argument("--roots", nargs="*", default=[str(root) for root in ROOTS])
    p_build.add_argument("--min-score", type=int, default=8)
    p_build.add_argument("--per-kind", type=int, default=6)
    p_build.add_argument("--limit", type=int, default=45)
    p_style = sub.add_parser("style")
    p_brief = sub.add_parser("brief")
    p_brief.add_argument("--kind", required=True)
    p_match = sub.add_parser("match")
    p_match.add_argument("--kind", default="")
    p_match.add_argument("--keyword", default="")
    p_match.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    if args.cmd == "build":
        result = build([Path(root) for root in args.roots], min_score=args.min_score,
                       per_kind=args.per_kind, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "style":
        if not STYLE_MD.is_file():
            raise SystemExit("先 build")
        print(STYLE_MD.read_text(encoding="utf-8"))
        return 0
    if args.cmd == "brief":
        print(brief(args.kind))
        return 0
    library = load()
    for entry in case_lib.match(library["entries"], args.kind, args.keyword, args.limit):
        print(f"{entry['id']}  {entry['kind']}  {entry['score']}  {entry['title'][:60]}")
        print(f"  {entry['file']}")
        print(f"  开头：{entry['opening']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
