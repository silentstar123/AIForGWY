# -*- coding: utf-8 -*-
"""PDF 取字：先读文字层，没有就用 rapidocr 识别前几页。

rapidocr_onnxruntime 是本机已装的轻量 ONNX 引擎，一张 200dpi 的 A4 约 2–6 秒。
没有安装时 available() 返回 False，调用方退回文件名。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

DPI = 200
DEFAULT_PAGES = 3
_engine: Any = None


def available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        import fitz  # noqa: F401
    except Exception:
        return False
    return True


def text_layer(path: Path, pages: int = DEFAULT_PAGES) -> str:
    try:
        import fitz
    except Exception:
        return ""
    try:
        with fitz.open(str(path)) as doc:
            return "\n".join(doc[index].get_text() for index in range(min(pages, len(doc))))
    except Exception:
        return ""


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_page(path: Path, index: int, dpi: int = DPI) -> str:
    import fitz

    engine = _get_engine()
    with fitz.open(str(path)) as doc:
        if index >= len(doc):
            return ""
        pix = doc[index].get_pixmap(dpi=dpi)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "page.png"
            pix.save(str(image))
            result, _ = engine(str(image))
    if not result:
        return ""
    return "\n".join(str(item[1]) for item in result)


def ocr_pdf(path: Path, pages: int = DEFAULT_PAGES, dpi: int = DPI) -> str:
    try:
        import fitz
    except Exception:
        return ""
    try:
        with fitz.open(str(path)) as doc:
            count = min(pages, len(doc))
    except Exception:
        return ""
    return "\n".join(ocr_page(path, index, dpi) for index in range(count))


def pdf_text(path: Path, pages: int = DEFAULT_PAGES, dpi: int = DPI) -> str:
    """有文字层就用文字层，否则 OCR；两者都没有返回空串。"""
    text = text_layer(path, pages)
    if text.strip():
        return text
    return ocr_pdf(path, pages, dpi)
