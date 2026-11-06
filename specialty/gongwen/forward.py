# -*- coding: utf-8 -*-
"""把收到的省文件抄成一份转发通知：生成 docx、附上原文件、写清哪些字段是推出来的。

用法：
    python specialty/gongwen/forward.py --source "G:\\...\\省文件.pdf" --out-dir .\\转发包 ^
        --document-no 廊发改技术〔2026〕368号 --recipients "各县（市、区）发改局" ^
        --doc-date 2026年10月29日 --purpose "贯彻落实省委省政府部署"

产出一个目录：
    转发通知.docx
    附件1 <省文件标题>.pdf
    转发通知.spec.json
    转发说明.md
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

import gongwen_docx
import ocr

NUMBER_RE = re.compile(r"[\u4e00-\u9fff]{1,12}[〔\[［【]\d{4}[〕\]］】]\s*\d{1,4}\s*号")
TITLE_SUFFIX = ("通知", "函", "意见", "办法", "纪要", "批复", "决定", "方案", "规则", "指南")
FILENAME_PREFIX = re.compile(r"^\d{8}\s+\d+\s+")
ISSUER_HINT = ("委员会", "人民政府", "省政府", "省委", "厅", "局", "海关", "税务局",
             "办公室", "组委会", "指挥部", "领导小组")


@dataclass
class Source:
    path: Path
    title: str = ""
    document_no: str = ""
    issuer: str = ""
    warnings: list[str] = field(default_factory=list)


# 呈办笺/收文办理单上的固定栏目和批示行，不是文件本身内容，抽取时整行丢弃。
# STRONG：看到就丢；LABEL：短栏目标签才丢。发文机关红头行（…办公室/…委员会/…组委会）绝不丢。
NOISE_STRONG = ("呈办笺", "呈批", "值班室", "批示", "拟办", "办理结果",
                "收文号", "收文时间", "收文人", "密级", "份数", "阅示")
NOISE_TITLE_PREFIX = "标题"
NOISE_LABEL = ("来文", "文号", "单位", "标题", "原文", "编号", "办文")

# 发文机关全称 → 标题/正文里的惯用简称（只影响显示，可用 --source-organ 覆盖）
ORGAN_ALIASES = {
    "河北省发展和改革委员会": "省发改委",
    "河北省发展改革委": "省发改委",
}


def drop_noise(lines: list[str]) -> list[str]:
    """过滤呈办笺、收文办理单上的栏目行和批示行，保留发文机关红头行和正文。"""
    kept = []
    for line in lines:
        if any(hint in line for hint in NOISE_STRONG):
            continue
        stripped = line.strip()
        if stripped.startswith(NOISE_TITLE_PREFIX) and "《" not in line:
            continue
        if "《" not in line and len(stripped) <= 14 and any(
                stripped == label or stripped.startswith(label + "：")
                or (stripped.startswith(label) and len(stripped) <= len(label) + 2)
                for label in NOISE_LABEL):
            continue
        kept.append(line)
    return kept


def run_size(run) -> float:
    return run.font.size.pt if run.font.size else 0.0


def run_east_asia(run) -> str | None:
    rpr = run._element.rPr
    if rpr is None or rpr.rFonts is None:
        return None
    return rpr.rFonts.get(qn("w:eastAsia"))


def filename_title(path: Path) -> str:
    stem = FILENAME_PREFIX.sub("", path.stem)
    return stem.strip() or path.stem


def is_receiver_line(text: str) -> bool:
    return text.strip().endswith(("：", ":"))


def looks_like_heading(text: str, size: float) -> bool:
    if size >= 20:
        return True
    return len(text) <= 2 and text.endswith("文件")


def is_issuer_line(text: str) -> bool:
    return (
        any(hint in text for hint in ISSUER_HINT)
        and len(text) <= 40
        and not text.startswith(("关于", "印发", "转发"))
        and not is_receiver_line(text)
    )


def is_title_start(text: str) -> bool:
    return text.startswith(("关于", "印发", "转发", "批转")) or "关于" in text[:6]


def extract_docx(path: Path) -> Source:
    source = Source(path=path)
    doc = Document(str(path))
    rows: list[tuple[str, float]] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        sizes = [run_size(r) for r in para.runs if r.text.strip()]
        rows.append((text, max(sizes) if sizes else 0.0))

    number_index = -1
    for i, (text, _) in enumerate(rows):
        match = NUMBER_RE.search(text)
        if match:
            source.document_no = re.sub(r"\s+", "", match.group(0))
            number_index = i
            break

    head = rows[: number_index if number_index >= 0 else len(rows)]
    issuer_parts = [text for text, size in head if size >= 24 and not looks_like_heading(text, size)]
    if not issuer_parts:
        issuer_parts = [text for text, _ in head if is_issuer_line(text)][:3]

    title_index = -1
    if number_index >= 0:
        for i in range(number_index + 1, len(rows)):
            text, _ = rows[i]
            if is_receiver_line(text):
                break
            if is_issuer_line(text) and not issuer_parts:
                issuer_parts.append(text)
                continue
            if is_title_start(text):
                title_index = i
                break
        if title_index >= 0:
            pieces: list[str] = []
            for text, _ in rows[title_index:]:
                if is_receiver_line(text):
                    break
                pieces.append(text)
                if text.endswith(TITLE_SUFFIX):
                    break
            source.title = "".join(pieces).strip()

    source.issuer = "".join(issuer_parts).strip()
    if not source.title:
        source.title = filename_title(path)
        source.warnings.append("标题取自已收文件名，请核对")
    return source


def normalize_number(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    return (value.replace("[", "〔").replace("]", "〕")
            .replace("［", "〔").replace("］", "〕")
            .replace("【", "〔").replace("】", "〕"))


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def parse_text_source(path: Path, text: str) -> Source:
    """从文字层或 OCR 文本里抽标题、文号、发文机关。"""
    source = Source(path=path)
    lines = [clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    lines = drop_noise(lines)

    number_index = -1
    for index, line in enumerate(lines):
        match = NUMBER_RE.search(line)
        if match:
            source.document_no = normalize_number(match.group(0))
            number_index = index
            break

    # 先定位被转发文件的标题行。呈办笺里也会写一遍标题，
    # 真标题向后几行内必有「主送：」式冒号行，用它验证。
    title_row = -1
    for i, line in enumerate(lines):
        if not is_title_start(line):
            continue
        lookahead = lines[i + 1:i + 5]
        if any(is_receiver_line(l) for l in lookahead) or i + 1 >= len(lines):
            title_row = i
            break

    # 发文机关红头行紧挨标题上方，OCR 可能拆成多行，向上收连续无标点、非文号、非日期的行
    if title_row > 0:
        parts: list[str] = []
        for j in range(title_row - 1, -1, -1):
            line = lines[j]
            if NUMBER_RE.search(line) or is_receiver_line(line):
                break
            if line.strip().startswith("文号"):
                break
            if line.endswith(("。", "，", "：", "；", "、", ":", ",")):
                break
            if re.fullmatch(r"[0-9A-Za-z]+", line):
                break
            if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", line):
                break
            if any(h in line for h in NOISE_STRONG):
                break
            parts.insert(0, line)
            if len("".join(parts)) > 30:
                break
        if parts:
            source.issuer = "".join(parts).replace("文件", "").strip()
    if not source.issuer:
        head = lines[: number_index if number_index >= 0 else min(len(lines), 8)]
        for line in head:
            if line.endswith("文件") or is_issuer_line(line):
                source.issuer = line.replace("文件", "").strip()
                break

    start = title_row if title_row >= 0 else (number_index + 1 if number_index >= 0 else 0)
    pieces: list[str] = []
    for line in lines[start:]:
        if is_receiver_line(line):
            break
        if not pieces:
            if line.startswith("标题"):
                line = line[2:].strip()
            if not is_title_start(line):
                continue
        pieces.append(line)
        joined = "".join(pieces)
        # 标题可能被 OCR 拆行（如「…的通」「知」），按拼接结果判断结尾
        if any(joined.endswith(suffix) for suffix in TITLE_SUFFIX) or len(joined) > 120:
            break
    source.title = "".join(pieces).strip()
    return source


def extract_pdf(path: Path, *, text: str | None = None, use_ocr: bool = True,
                pages: int = 3) -> Source:
    if text is None:
        layer = ocr.text_layer(path, pages)
        if layer.strip():
            text, mode = layer, "text"
        elif use_ocr:
            text, mode = ocr.ocr_pdf(path, pages), "ocr"
        else:
            text, mode = "", "none"
    else:
        mode = "given"
    if text.strip():
        source = parse_text_source(path, text)
        if not source.title:
            source.title = filename_title(path)
            source.warnings.append("PDF 里没找到标题行，标题取自已收文件名")
        elif source.document_no:
            source.warnings.append(
                "扫描件已用 OCR 识别，标题和文号请核对" if mode == "ocr"
                else "从 PDF 文字层抽取，标题和文号请核对")
        else:
            source.warnings.append("没识别到来文文号，请在 spec 里补")
        return source
    source = Source(path=path)
    source.title = filename_title(path)
    source.warnings.append("PDF 没有文字层，标题取自已收文件名；文号请手工核对")
    return source


def extract(path: Path, *, use_ocr: bool = True, pages: int = 3) -> Source:
    if path.suffix.lower() == ".docx":
        return extract_docx(path)
    if path.suffix.lower() == ".pdf":
        return extract_pdf(path, use_ocr=use_ocr, pages=pages)
    source = Source(path=path)
    source.title = filename_title(path)
    source.warnings.append(f"不支持自动抽取 {path.suffix}，标题取文件名")
    return source


def safe_name(name: str) -> str:
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return re.sub(r"\s+", " ", name).strip()[:80] or "附件"


def build_package(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = [extract(Path(p), use_ocr=not getattr(args, "no_ocr", False),
                       pages=getattr(args, "ocr_pages", 3)) for p in args.source]
    for i, number in enumerate(args.source_number or []):
        if i < len(sources) and number:
            sources[i].document_no = number
    warnings: list[str] = []
    for item in sources:
        warnings.extend(f"{item.path.name}: {w}" for w in item.warnings)
        if not item.document_no:
            warnings.append(f"{item.path.name}: 没有识别到来文文号，转到 spec 里后请补")

    title_override = args.title
    # 发文机关显示名：命令行给了就用给的；没给就把识别出的全称换成惯用简称
    organ = args.source_organ
    if not organ:
        extracted = next((s.issuer for s in sources if s.issuer), "")
        organ = ORGAN_ALIASES.get(extracted) or extracted or "省发改委"
    if title_override:
        title = title_override
    elif len(sources) == 1:
        title = f"关于转发{organ}{gongwen_docx.wrap_title(sources[0].title)}的通知"
    else:
        names = "和".join(gongwen_docx.wrap_title(s.title) for s in sources)
        title = f"关于转发{organ}{names}的通知"

    spec = {
        "kind": "转发通知",
        "issuer": args.issuer,
        "documentNo": args.document_no,
        "title": title,
        "sourceOrgan": organ,
        "purpose": args.purpose,
        "requirement": args.requirement,
        "sources": [
            {"title": s.title, "documentNo": s.document_no or "【来文文号待核实】"}
            for s in sources
        ],
        "recipients": args.recipients or ["【主送机关待核实】"],
        "attachments": [
            f"{i}. {s.title}" for i, s in enumerate(sources, start=1)
        ],
        "signers": [args.issuer],
        "date": args.doc_date,
    }
    if getattr(args, "contact", ""):
        spec["contact"] = args.contact
    if getattr(args, "contact_phone", ""):
        spec["contactPhone"] = args.contact_phone
    if getattr(args, "email", ""):
        spec["email"] = args.email

    docx_path = out_dir / "转发通知.docx"
    gongwen_docx.build(spec, gongwen_docx.load_profile(), docx_path)

    copied: list[str] = []
    if not args.no_copy:
        for i, item in enumerate(sources, start=1):
            target = out_dir / f"附件{i} {safe_name(item.title)}{item.path.suffix.lower()}"
            shutil.copy2(item.path, target)
            copied.append(target.name)

    (out_dir / "转发通知.spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    notes = [
        "# 转发说明",
        "",
        f"- 转发通知：{docx_path.name}",
        f"- 来文：{len(sources)} 件",
    ]
    for i, item in enumerate(sources, start=1):
        notes.append(f"  {i}. {item.title}（{item.document_no or '文号待核实'}）")
        notes.append(f"     源文件：{item.path}")
    for name in copied:
        notes.append(f"- 附件：{name}")
    if warnings:
        notes += ["", "## 待核对"] + [f"- {w}" for w in warnings]
    notes += ["", "## 边界", "", "文号、成文日期、署名只用给定值；没有识别到的写「待核实」。"]
    (out_dir / "转发说明.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    return {
        "outDir": str(out_dir),
        "docx": str(docx_path),
        "attachments": copied,
        "spec": spec,
        "warnings": warnings,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="把收到的省文件抄成转发通知并打包")
    parser.add_argument("--source", action="append", required=True, help="省文件 pdf/docx，可重复")
    parser.add_argument("--source-number", action="append", default=[],
                        help="来文文号，按 --source 顺序补齐；扫描件识别不出时用")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--issuer", default="廊坊市发展和改革委员会")
    parser.add_argument("--document-no", default="【发文字号待办文系统填写】")
    parser.add_argument("--source-organ", default=None,
                        help="标题/正文里发文机关的写法，如 省发改委；不填则按识别结果取惯用简称")
    parser.add_argument("--recipients", default="")
    parser.add_argument("--purpose", default="贯彻落实上级部署")
    parser.add_argument("--requirement", default="认真贯彻执行")
    parser.add_argument("--contact", default="", help="落款前联系人行：姓名")
    parser.add_argument("--contact-phone", default="", help="落款前联系人行：电话")
    parser.add_argument("--email", default="", help="落款前邮箱行")
    parser.add_argument("--doc-date", default="【成文日期待办文系统填写】")
    parser.add_argument("--title", help="覆盖自动拼的标题")
    parser.add_argument("--no-ocr", action="store_true", help="扫描件不做 OCR，只读文字层")
    parser.add_argument("--ocr-pages", type=int, default=3, help="OCR 前几页，默认 3")
    parser.add_argument("--no-copy", action="store_true", help="不复制附件，只生成通知")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args(argv)

    result = build_package(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"已生成 {result['docx']}")
        for name in result["attachments"]:
            print(f"附件 {name}")
        if result["warnings"]:
            print("待核对：")
            for item in result["warnings"]:
                print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
