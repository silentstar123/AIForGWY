# -*- coding: utf-8 -*-
"""按本机样本的公文版式生成和核对 .docx。

用法：
    python specialty/gongwen/docx.py template 转发通知 --out spec.json
    python specialty/gongwen/docx.py build spec.json --out 通知.docx
    python specialty/gongwen/docx.py inspect 样本.docx --out dump.txt

版式数据在 specialty/gongwen/format.json，可以用 inspect 的输出核对后再改。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
PROFILE_PATH = HERE / "format.json"

HEADING1 = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")
NESTED_OPEN = "〈"
NESTED_CLOSE = "〉"


def load_profile(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or PROFILE_PATH).read_text(encoding="utf-8"))


def set_run(run, *, ea: str, size_pt: float, latin: str = "Times New Roman",
            bold: bool | None = None, color: str | None = None) -> None:
    run.font.name = latin
    run.font.size = Pt(size_pt)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:eastAsia"), ea)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)


def set_para(para, *, align=None, line_pt: float | None = None,
             first_indent_pt: float | None = None, left_indent_pt: float | None = None,
             right_indent_pt: float | None = None, before_pt: float = 0, after_pt: float = 0) -> None:
    pf = para.paragraph_format
    if align is not None:
        pf.alignment = align
    if line_pt is not None:
        pf.line_spacing = Pt(line_pt)
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    if first_indent_pt is not None:
        pf.first_line_indent = Pt(first_indent_pt)
    if left_indent_pt is not None:
        pf.left_indent = Pt(left_indent_pt)
    if right_indent_pt is not None:
        pf.right_indent = Pt(right_indent_pt)
    pf.space_before = Pt(before_pt)
    pf.space_after = Pt(after_pt)


def add_border(para, *, top: bool = False, bottom: bool = False, size: int = 4,
               color: str = "000000") -> None:
    ppr = para._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    for edge, on in (("top", top), ("bottom", bottom)):
        if not on:
            continue
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "1")
        el.set(qn("w:color"), color)
        pbdr.append(el)


def add_page_field(para, profile: dict[str, Any]) -> None:
    font = profile["fonts"]
    ea = font["pageNumber"]
    size = font["pageNumberSizePt"]
    latin = font["latin"]
    first = para.add_run("— ")
    set_run(first, ea=ea, size_pt=size, latin=latin)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    inner = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    rfonts.set(qn("w:eastAsia"), ea)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rpr.append(rfonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    inner.append(rpr)
    t = OxmlElement("w:t")
    t.text = "1"
    inner.append(t)
    fld.append(inner)
    para._p.append(fld)
    last = para.add_run(" —")
    set_run(last, ea=ea, size_pt=size, latin=latin)


def heading_level(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    if len(stripped) > 1 and stripped[0] in HEADING1 and stripped[1] in "、.":
        return 1
    if stripped.startswith("（") and "）" in stripped[:4]:
        return 2
    return 0


def nest_title(title: str) -> str:
    """把标题里内层的《》换成〈〉，避免《…《…》…》嵌套。"""
    out: list[str] = []
    depth = 0
    for ch in title:
        if ch == "《":
            depth += 1
            out.append(ch if depth == 1 else NESTED_OPEN)
        elif ch == "》":
            out.append("》" if depth <= 1 else NESTED_CLOSE)
            depth = max(0, depth - 1)
        else:
            out.append(ch)
    return "".join(out)


def wrap_title(title: str) -> str:
    """给书名号标题加外层《》，内层《》一律转成〈〉。"""
    inner = str(title).strip()
    for opener, closer in (("《", "〈"), ("》", "〉")):
        inner = inner.replace(opener, closer)
    return f"《{inner}》"


def compose_forward(spec: dict[str, Any]) -> tuple[str, list[str]]:
    """生成转发类公文的标题和正文缘由段。"""
    sources = spec.get("sources") or []
    organ = spec.get("sourceOrgan") or "上级机关"
    requirement = spec.get("requirement") or "认真贯彻执行"
    purpose = spec.get("purpose")
    items = []
    for item in sources:
        title = str(item.get("title") or "").strip()
        number = str(item.get("documentNo") or "").strip()
        items.append(wrap_title(title) + (f"（{number}）" if number else ""))
    joined = "和".join(items) if items else "有关文件"
    lead = f"为{purpose}，" if purpose else ""
    body = (
        f"{lead}{organ}下发了{joined}，"
        f"现{'一并' if len(items) > 1 else ''}转发给你们，请{requirement}。"
    )
    if len(sources) == 1:
        title = f"关于转发{organ}{wrap_title(str(sources[0].get('title') or ''))}的通知"
    else:
        names = "和".join(wrap_title(str(item.get("title") or "")) for item in sources)
        title = f"关于转发{organ}{names}的通知"
    return spec.get("title") or title, [body]


def wrap_title_lines(title: str, max_chars: int = 20) -> list[str]:
    """按每行最多 max_chars 个字断开标题，优先在标点后换行，避免末行只剩一两个字。

    英文字母和数字视为整体，不在中间断开（避免把「2026」断成两行）；
    书名号《》前后也允许换行。
    """
    text = str(title).strip()
    if len(text) <= max_chars:
        return [text]

    # 把连续的英文/数字捆成原子块，断行时不拆开
    units: list[str] = []
    buf = ""
    for ch in text:
        if ch.isascii() and ch.isalnum():
            buf += ch
        else:
            if buf:
                units.append(buf)
                buf = ""
            units.append(ch)
    if buf:
        units.append(buf)

    total = len(units)
    # 超长标题（两行都摆不下）不硬拆，交回 Word 自然换行——手动断行反而容易切断词
    if total > 40:
        return [text]
    count = (total + max_chars - 1) // max_chars
    target = (total + count - 1) // count
    # 文种词尾的首字：断行后若只剩「知》的通知」这类尾巴，会把「通知」拆开，禁止在这里断
    TAIL_HEADS = "知见法复要案则南定函"
    lines: list[str] = []
    current = ""
    for index, unit in enumerate(units):
        current += unit
        rest = total - index - 1
        if rest == 0:
            break
        remainder = "".join(units[index + 1:])
        if remainder[:1] in TAIL_HEADS and len(remainder) <= 6:
            continue
        if remainder[:1] in "》〉" and len(remainder) <= 4:
            continue
        if len(current) >= target and (unit in "、，。；：）》」』《" or len(current) >= max_chars
                                       or rest <= 2):
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def add_right_tab(para, width_pt: float) -> None:
    from docx.enum.text import WD_TAB_ALIGNMENT
    para.paragraph_format.tab_stops.add_tab_stop(Pt(width_pt), WD_TAB_ALIGNMENT.RIGHT)


def build(spec: dict[str, Any], profile: dict[str, Any], out_path: Path) -> Path:
    fonts = profile["fonts"]
    spacing = profile["spacing"]
    page = profile["page"]
    line_pt = float(spec.get("lineSpacingPt") or spacing["lineSpacingPt"])
    body_chars = float(spec.get("firstLineIndentChars") or spacing["firstLineIndentChars"])
    body_size = fonts["bodySizePt"]
    indent_pt = body_chars * body_size

    if spec.get("kind") == "转发通知" and not spec.get("body"):
        title, body = compose_forward(spec)
        spec = {**spec, "title": spec.get("title") or title, "body": body}
    if spec.get("kind") == "转发通知" and not spec.get("allowSections"):
        numbered = [p for p in spec.get("body", [])
                    if str(p).strip().startswith(("一、", "二、", "三、", "四、", "五、",
                                                  "（一）", "（二）", "1."))]
        if numbered:
            raise SystemExit(
                "转发通知正文不要分「一、二、」这类条目；把要求接在缘由后面写成一段话，"
                "确实需要分条时在 spec 里加 \"allowSections\": true。")
    if not spec.get("title"):
        raise SystemExit("spec 缺少 title；转发类公文也可以给 sources 自动生成。")

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.size = Pt(body_size)
    normal.font.name = fonts["latin"]
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:eastAsia"), fonts["body"])
    normal.paragraph_format.line_spacing = Pt(line_pt)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY

    section = doc.sections[0]
    section.page_width = Cm(page["widthCm"])
    section.page_height = Cm(page["heightCm"])
    section.top_margin = Cm(page["marginTopCm"])
    section.bottom_margin = Cm(page["marginBottomCm"])
    section.left_margin = Cm(page["marginLeftCm"])
    section.right_margin = Cm(page["marginRightCm"])
    section.header_distance = Cm(page["headerCm"])
    section.footer_distance = Cm(page["footerCm"])

    footer_p = section.footer.paragraphs[0]
    set_para(footer_p, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_page_field(footer_p, profile)

    def empty(n: int = 1) -> None:
        for _ in range(n):
            p = doc.add_paragraph()
            set_para(p, line_pt=line_pt)

    def text(value: str, *, ea: str = fonts["body"], size: float = body_size,
             align=None, indent: float = 0.0, bold: bool | None = None,
             color: str | None = None, right_indent: float = 0.0) -> Any:
        p = doc.add_paragraph()
        set_para(p, align=align, line_pt=line_pt, first_indent_pt=indent,
                 right_indent_pt=right_indent)
        run = p.add_run(value)
        set_run(run, ea=ea, size_pt=size, latin=fonts["latin"], bold=bold, color=color)
        return p

    security = spec.get("security")
    urgency = spec.get("urgency")
    if security:
        text(security, ea=fonts["heading1"], align=WD_ALIGN_PARAGRAPH.LEFT)
    if urgency:
        text(urgency, ea=fonts["heading1"], align=WD_ALIGN_PARAGRAPH.LEFT)
    if security or urgency:
        empty()

    usable_pt = (page["widthCm"] - page["marginLeftCm"] - page["marginRightCm"]) * 28.3464566929
    empty()
    signer = str(spec.get("signer") or "").strip()
    if spec.get("documentNo"):
        if signer:
            para = doc.add_paragraph()
            set_para(para, line_pt=line_pt, align=WD_ALIGN_PARAGRAPH.LEFT)
            add_right_tab(para, usable_pt)
            label = para.add_run(str(spec["documentNo"]) + "\t" + "签发人：")
            set_run(label, ea=fonts["body"], size_pt=body_size, latin=fonts["latin"])
            name = para.add_run(signer)
            set_run(name, ea=fonts["heading2"], size_pt=body_size, latin=fonts["latin"])
        else:
            text(spec["documentNo"], align=WD_ALIGN_PARAGRAPH.CENTER)
        empty()
    if spec.get("redLine"):
        para = doc.add_paragraph()
        set_para(para, line_pt=8)
        add_border(para, bottom=True, size=12, color="FF0000")
    if spec.get("issuer"):
        text(spec["issuer"], ea=fonts["title"], size=fonts["titleSizePt"],
             align=WD_ALIGN_PARAGRAPH.CENTER, color=(profile.get("letterhead") or {}).get("color"))
        empty()

    title_lines = spec.get("titleLines") or wrap_title_lines(
        spec["title"], int(spec.get("titleCharsPerLine") or 20))
    for line in title_lines:
        text(line, ea=fonts["title"], size=fonts["titleSizePt"], align=WD_ALIGN_PARAGRAPH.CENTER)
    empty()

    meta = spec.get("meta") or {}
    meta_labels = (("时间", "time"), ("地点", "place"), ("主持人", "host"),
                   ("出席", "attendees"), ("列席", "observers"))
    rendered_meta = 0
    for label, key in meta_labels:
        if meta.get(key):
            text(f"{label}：{meta[key]}", ea=fonts["heading1"])
            rendered_meta += 1
    if rendered_meta:
        empty()

    recipients = spec.get("recipients") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    if recipients:
        line = "、".join(str(r).strip().rstrip("：:") for r in recipients if str(r).strip())
        if line:
            text(line + "：", indent=0)

    for para_text in spec.get("body") or []:
        if not str(para_text).strip():
            empty()
            continue
        level = heading_level(str(para_text))
        ea = fonts["heading1"] if level == 1 else (fonts["heading2"] if level == 2 else fonts["body"])
        text(str(para_text), ea=ea, indent=indent_pt)

    attachments = spec.get("attachments") or []
    if attachments:
        first = f"附件：{attachments[0]}"
        text(first, indent=indent_pt)
        for item in attachments[1:]:
            text(str(item), indent=indent_pt + 3 * body_size)

    for note in spec.get("notes") or []:
        text(str(note), indent=indent_pt)

    # 联系人/邮箱：转发、征集类通知常见，右对齐排在落款之前
    contact = str(spec.get("contact") or "").strip()
    contact_phone = str(spec.get("contactPhone") or "").strip()
    email = str(spec.get("email") or "").strip()
    if contact or email:
        empty()
    if contact:
        gap = "　" * 4 if contact_phone else ""
        text(f"联系人：{contact}{gap}{contact_phone}",
             align=WD_ALIGN_PARAGRAPH.RIGHT, right_indent=2 * body_size)
    if email:
        text(f"邮　　箱：{email}",
             align=WD_ALIGN_PARAGRAPH.RIGHT, right_indent=2 * body_size)

    empty()
    for signer in spec.get("signers") or []:
        text(str(signer), align=WD_ALIGN_PARAGRAPH.RIGHT, right_indent=2 * body_size)
    if spec.get("date"):
        text(spec["date"], align=WD_ALIGN_PARAGRAPH.RIGHT, right_indent=2 * body_size)

    cc = spec.get("cc")
    printer = spec.get("printer")
    print_date = spec.get("printDate")
    if cc or printer or print_date:
        empty()
        if cc:
            para = text(f"抄送：{cc}", size=14, indent=0)
            add_border(para, top=True)
        para = doc.add_paragraph()
        set_para(para, line_pt=20, align=WD_ALIGN_PARAGRAPH.LEFT)
        add_right_tab(para, usable_pt)
        left = para.add_run(str(printer or ""))
        set_run(left, ea=fonts["body"], size_pt=14, latin=fonts["latin"])
        right_text = f"{print_date or ''}{'印发' if print_date else ''}"
        right = para.add_run("\t" + right_text)
        set_run(right, ea=fonts["body"], size_pt=14, latin=fonts["latin"])
        add_border(para, top=True, bottom=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def inspect(path: Path, profile: dict[str, Any]) -> str:
    """把样本的字号、字体、行距、页边距打印出来，用于核对 format.json。"""
    doc = Document(str(path))
    lines: list[str] = [f"FILE: {path}"]
    sec = doc.sections[0]
    lines.append(
        f"page {sec.page_width.cm:.2f}x{sec.page_height.cm:.2f}cm "
        f"margins T/B/L/R {sec.top_margin.cm:.2f}/{sec.bottom_margin.cm:.2f}/"
        f"{sec.left_margin.cm:.2f}/{sec.right_margin.cm:.2f}cm"
    )
    for i, para in enumerate(doc.paragraphs):
        if not para.text.strip():
            continue
        pf = para.paragraph_format
        ls = f"{pf.line_spacing.pt:.1f}pt" if hasattr(pf.line_spacing, "pt") else str(pf.line_spacing)
        lines.append(
            f"[{i:03d}] align={pf.alignment} first={pf.first_line_indent} "
            f"ls={ls} text={para.text[:60]!r}"
        )
        for run in para.runs:
            if not run.text.strip():
                continue
            rpr = run._element.rPr
            ea = None
            if rpr is not None and rpr.rFonts is not None:
                ea = rpr.rFonts.get(qn("w:eastAsia"))
            lines.append(
                f"      run ea={ea} ascii={run.font.name} size={run.font.size.pt if run.font.size else None} "
                f"bold={run.font.bold} text={run.text[:40]!r}"
            )
    footer_texts = [p.text for p in sec.footer.paragraphs if p.text.strip()]
    if footer_texts:
        lines.append(f"footer: {footer_texts}")
    return "\n".join(lines)


def collect_docx(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(p for p in path.rglob("*.docx") if not p.name.startswith("~$"))
        elif path.suffix.lower() == ".docx" and path.is_file():
            found.append(path)
    return sorted(set(found))


def east_asia_of(run) -> str | None:
    rpr = run._element.rPr
    if rpr is None or rpr.rFonts is None:
        return None
    return rpr.rFonts.get(qn("w:eastAsia"))


def learn(paths: list[str], profile: dict[str, Any]) -> dict[str, Any]:
    """从样本里统计出现最多的正文版式，给出可以写回 format.json 的候选值。"""
    from collections import Counter

    body_font: Counter = Counter()
    body_size: Counter = Counter()
    line_spacing: Counter = Counter()
    first_indent: Counter = Counter()
    margins: Counter = Counter()
    pages: Counter = Counter()
    docs = 0
    skipped = 0
    for path in collect_docx(paths):
        try:
            doc = Document(str(path))
        except Exception:
            skipped += 1
            continue
        docs += 1
        sec = doc.sections[0]
        pages[(round(sec.page_width.cm, 1), round(sec.page_height.cm, 1))] += 1
        margins[(
            round(sec.top_margin.cm, 1), round(sec.bottom_margin.cm, 1),
            round(sec.left_margin.cm, 1), round(sec.right_margin.cm, 1),
        )] += 1
        for para in doc.paragraphs:
            text = para.text.strip()
            if len(text) < 8:
                continue
            runs = [r for r in para.runs if r.text.strip()]
            if not runs:
                continue
            run = runs[0]
            size = run.font.size.pt if run.font.size else None
            if size is None or size >= 20:
                continue
            body_font[east_asia_of(run)] += len(text)
            body_size[size] += len(text)
            spacing = para.paragraph_format.line_spacing
            if hasattr(spacing, "pt"):
                line_spacing[round(spacing.pt, 1)] += 1
            indent = para.paragraph_format.first_line_indent
            if indent is not None:
                first_indent[round(indent.pt, 1)] += 1

    def top(counter: Counter) -> Any:
        return counter.most_common(1)[0][0] if counter else None

    page = top(pages) or (21.0, 29.7)
    margin = top(margins) or (3.5, 3.5, 2.7, 2.7)
    body_size_pt = top(body_size) or profile["fonts"]["bodySizePt"]
    line_pt = top(line_spacing) or profile["spacing"]["lineSpacingPt"]
    indent_pt = top(first_indent) or profile["spacing"]["firstLineIndentChars"] * body_size_pt
    return {
        "samples": docs,
        "skipped": skipped,
        "page": {"widthCm": page[0], "heightCm": page[1]},
        "marginsCm": {"top": margin[0], "bottom": margin[1], "left": margin[2], "right": margin[3]},
        "bodyFont": top(body_font),
        "bodySizePt": body_size_pt,
        "lineSpacingPt": line_pt,
        "firstLineIndentPt": indent_pt,
        "counts": {
            "bodyFont": body_font.most_common(5),
            "bodySizePt": body_size.most_common(5),
            "lineSpacingPt": line_spacing.most_common(5),
            "firstLineIndentPt": first_indent.most_common(5),
        },
    }


def apply_learned(profile: dict[str, Any], learned: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(profile))
    updated.setdefault("page", {}).update(learned["page"])
    updated["page"].update({
        "marginTopCm": learned["marginsCm"]["top"],
        "marginBottomCm": learned["marginsCm"]["bottom"],
        "marginLeftCm": learned["marginsCm"]["left"],
        "marginRightCm": learned["marginsCm"]["right"],
    })
    if learned.get("bodyFont"):
        updated["fonts"]["body"] = learned["bodyFont"]
    updated["fonts"]["bodySizePt"] = learned["bodySizePt"]
    updated["spacing"]["lineSpacingPt"] = learned["lineSpacingPt"]
    if learned.get("bodySizePt"):
        updated["spacing"]["firstLineIndentChars"] = round(
            learned["firstLineIndentPt"] / learned["bodySizePt"], 2)
    return updated


def check(path: Path, profile: dict[str, Any]) -> dict[str, Any]:
    """核对一份 docx 是否落在 format.json 的版式里，返回问题清单。"""
    from collections import Counter

    fonts = profile["fonts"]
    spacing = profile["spacing"]
    page = profile["page"]
    doc = Document(str(path))
    issues: list[str] = []
    sec = doc.sections[0]
    for label, actual, expected in (
        ("页宽", sec.page_width.cm, page["widthCm"]),
        ("页高", sec.page_height.cm, page["heightCm"]),
        ("上边距", sec.top_margin.cm, page["marginTopCm"]),
        ("下边距", sec.bottom_margin.cm, page["marginBottomCm"]),
        ("左边距", sec.left_margin.cm, page["marginLeftCm"]),
        ("右边距", sec.right_margin.cm, page["marginRightCm"]),
    ):
        if abs(actual - expected) > 0.1:
            issues.append(f"{label} {actual:.2f}cm，样本是 {expected}cm")

    font_counter: Counter = Counter()
    size_counter: Counter = Counter()
    spacing_counter: Counter = Counter()
    indent_counter: Counter = Counter()
    for para in doc.paragraphs:
        text = para.text.strip()
        if len(text) < 8 or heading_level(text):
            continue
        for run in para.runs:
            if not run.text.strip():
                continue
            font_counter[east_asia_of(run)] += len(run.text)
            if run.font.size:
                size_counter[round(run.font.size.pt, 1)] += len(run.text)
        line = para.paragraph_format.line_spacing
        if hasattr(line, "pt"):
            spacing_counter[round(line.pt, 1)] += 1
        indent = para.paragraph_format.first_line_indent
        if indent is not None:
            indent_counter[round(indent.pt, 1)] += 1

    def top(counter: Counter) -> Any:
        return counter.most_common(1)[0][0] if counter else None

    body_font = top(font_counter)
    body_size = top(size_counter)
    body_spacing = top(spacing_counter)
    body_indent = top(indent_counter)
    if body_font and body_font != fonts["body"]:
        issues.append(f"正文字体是 {body_font}，样本是 {fonts['body']}")
    if body_size and abs(body_size - fonts["bodySizePt"]) > 0.5:
        issues.append(f"正文字号是 {body_size}pt，样本是 {fonts['bodySizePt']}pt")
    if body_spacing and abs(body_spacing - spacing["lineSpacingPt"]) > 0.5:
        issues.append(f"正文行距是 {body_spacing}pt，样本是 {spacing['lineSpacingPt']}pt")
    expected_indent = spacing["firstLineIndentChars"] * fonts["bodySizePt"]
    if body_indent and abs(body_indent - expected_indent) > 1:
        issues.append(f"正文首行缩进是 {body_indent}pt，样本是 {expected_indent}pt")

    title_runs = [run for para in doc.paragraphs for run in para.runs
                  if run.text.strip() and run.font.size and run.font.size.pt >= 20]
    if title_runs:
        title = max(title_runs, key=lambda r: r.font.size.pt)
        if east_asia_of(title) != fonts["title"]:
            issues.append(f"标题字体是 {east_asia_of(title)}，样本是 {fonts['title']}")
        if abs(title.font.size.pt - fonts["titleSizePt"]) > 0.5:
            issues.append(f"标题字号是 {title.font.size.pt}pt，样本是 {fonts['titleSizePt']}pt")
    else:
        issues.append("没有找到二号以上的标题")

    footer_xml = doc.sections[0].footer.paragraphs[0]._p.xml if doc.sections[0].footer.paragraphs else ""
    if "PAGE" not in footer_xml:
        issues.append("页脚没有页码域")

    return {
        "file": str(path),
        "ok": not issues,
        "issues": issues,
        "observed": {
            "bodyFont": body_font, "bodySizePt": body_size,
            "lineSpacingPt": body_spacing, "firstLineIndentPt": body_indent,
        },
    }


def template(kind: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": kind,
        "issuer": "【发文机关，待办文系统填写】",
        "documentNo": "【发文字号，待办文系统填写】",
        "title": f"关于【事由】的{kind}",
        "recipients": ["【主送机关】"],
        "body": ["【缘由：为什么现在办。】", "【事项】", "请遵照执行。"],
        "attachments": [],
        "signers": ["【发文机关，待办文系统填写】"],
        "date": "【成文日期，待办文系统填写】",
    }
    if kind == "转发通知":
        base.update({
            "title": "",
            "sources": [{"organ": "【上级机关】", "title": "【被转发文件标题】", "documentNo": "【来文文号】"}],
            "sourceOrgan": "【上级机关】",
            "purpose": "【目的】",
            "requirement": "认真贯彻执行",
            "body": [],
        })
    if kind == "请示":
        base["body"] = ["【理由】", "【事项】", "妥否，请批示。"]
        base["signer"] = ""
    elif kind == "报告":
        base["body"] = ["【工作情况】", "特此报告。"]
        base["signer"] = ""
    elif kind == "函":
        base["body"] = ["【商洽或询问事项】", "请予函复。"]
    elif kind == "批复":
        base["body"] = ["《【来文标题】》（【来文文号】）收悉。", "【同意/原则同意/不同意】。【执行要求】。"]
    elif kind == "纪要":
        base.update({
            "title": "【会议名称】纪要",
            "issuer": "",
            "documentNo": "",
            "recipients": [],
            "meta": {"time": "【时间】", "place": "【地点】", "host": "【主持人】", "attendees": "【出席】"},
            "body": ["会议听取了【】。", "一、议定事项", "1. 【事项】。负责人：【】。完成时限：【】。"],
            "signers": [],
            "date": "",
        })
    return base


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="按样本版式生成和核对公文 docx")
    parser.add_argument("--profile", default=str(PROFILE_PATH))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="按 spec JSON 生成 docx")
    p_build.add_argument("spec")
    p_build.add_argument("--out", required=True)

    p_tpl = sub.add_parser("template", help="输出某个文种的 spec 骨架")
    p_tpl.add_argument("kind")
    p_tpl.add_argument("--out")

    p_ins = sub.add_parser("inspect", help="打印样本 docx 的版式")
    p_ins.add_argument("file")
    p_ins.add_argument("--out")

    p_check = sub.add_parser("check", help="核对 docx 是否符合 format.json")
    p_check.add_argument("file")
    p_check.add_argument("--json", action="store_true")

    p_learn = sub.add_parser("learn", help="统计一批样本的版式，给出 format.json 候选值")
    p_learn.add_argument("paths", nargs="+", help="docx 文件或目录，可给多个")
    p_learn.add_argument("--out", help="把统计结果写成 JSON")
    p_learn.add_argument("--write", action="store_true", help="写回 format.json（先备份）")

    args = parser.parse_args(argv)
    profile = load_profile(Path(args.profile))

    if args.cmd == "build":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
        out = build(spec, profile, Path(args.out))
        print(f"已生成 {out}")
        return 0
    if args.cmd == "template":
        text = json.dumps(template(args.kind), ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
            print(f"已写出 {args.out}")
        else:
            print(text)
        return 0
    if args.cmd == "inspect":
        report = inspect(Path(args.file), profile)
        if args.out:
            Path(args.out).write_text(report + "\n", encoding="utf-8")
            print(f"已写出 {args.out}")
        else:
            print(report)
        return 0
    if args.cmd == "check":
        result = check(Path(args.file), profile)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("版式通过" if result["ok"] else "版式有问题：")
            for issue in result["issues"]:
                print(f"- {issue}")
        return 0 if result["ok"] else 1
    if args.cmd == "learn":
        learned = learn(args.paths, profile)
        text = json.dumps(learned, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
            print(f"已写出 {args.out}")
        else:
            print(text)
        if args.write:
            target = Path(args.profile)
            backup = target.with_suffix(".backup.json")
            backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            target.write_text(
                json.dumps(apply_learned(profile, learned), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            print(f"已写回 {target}（备份 {backup}）")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
