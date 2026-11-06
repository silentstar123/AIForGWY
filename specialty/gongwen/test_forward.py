# -*- coding: utf-8 -*-
"""forward.py 的抽取与打包测试：用生成的省文件样张反推，不依赖内网。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import forward
import gongwen_docx


def make_provincial(path: Path, *, with_number: bool = True) -> Path:
    spec = {
        "kind": "通知",
        "issuer": "河北省发展和改革委员会",
        "documentNo": "冀发改高技规〔2026〕11号" if with_number else "",
        "title": "关于印发《河北省发展改革委企业技术中心管理办法》的通知",
        "recipients": ["各市（含定州、辛集市）发展改革委（局）"],
        "body": ["现将《河北省发展改革委企业技术中心管理办法》印发给你们，请认真贯彻执行。"],
        "signers": ["河北省发展和改革委员会"],
        "date": "2026年10月23日",
    }
    gongwen_docx.build(spec, gongwen_docx.load_profile(), path)
    return path


class ExtractTest(unittest.TestCase):
    def test_extract_docx_title_number_issuer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx")
            source = forward.extract(path)
        self.assertEqual(source.document_no, "冀发改高技规〔2026〕11号")
        self.assertEqual(source.title, "关于印发《河北省发展改革委企业技术中心管理办法》的通知")
        self.assertEqual(source.issuer, "河北省发展和改革委员会")
        self.assertEqual(source.warnings, [])

    def test_filename_title_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx", with_number=False)
            source = forward.extract(path)
        self.assertEqual(source.title, "关于印发办法的通知")
        self.assertTrue(source.warnings)

    def test_pdf_without_text_layer_falls_back_to_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20261026 7 关于印发《河北省产业技术工程化中心管理办法》的通知.pdf"
            path.write_bytes(b"%PDF-1.4\n%stub\n")
            source = forward.extract(path)
        self.assertEqual(source.title, "关于印发《河北省产业技术工程化中心管理办法》的通知")
        self.assertIn("没有文字层", source.warnings[0])


class OcrTextTest(unittest.TestCase):
    def test_parse_text_from_ocr_lines(self) -> None:
        text = "\n".join([
            "河北省发展和改革委员会文件",
            "冀发改高技规〔2026]10号",
            "河北省发展和改革委员会",
            "关于印发《河北省产业技术工程化中心",
            "管理办法》的通知",
            "各市（含定州、辛集市）发展改革委（局）：",
            "为深入实施创新驱动发展战略。",
        ])
        source = forward.extract_pdf(Path("20261026 7 关于印发办法的通知.pdf"), text=text,
                                     use_ocr=False)
        self.assertEqual(source.document_no, "冀发改高技规〔2026〕10号")
        self.assertEqual(source.title, "关于印发《河北省产业技术工程化中心管理办法》的通知")
        self.assertEqual(source.issuer, "河北省发展和改革委员会")

    def test_receipt_sheet_title_line(self) -> None:
        text = "\n".join([
            "廊坊市发展和改革委员会文件呈办笺",
            "收文号：省发改697号",
            "标题关于印发《河北省产业技术工程化中心管理办法》的通知",
        ])
        source = forward.extract_pdf(Path("x.pdf"), text=text, use_ocr=False)
        self.assertEqual(source.title, "关于印发《河北省产业技术工程化中心管理办法》的通知")

    def test_mixed_brackets_are_normalized(self) -> None:
        self.assertEqual(forward.normalize_number("冀发改高技规〔2026]10 号"),
                         "冀发改高技规〔2026〕10号")

    def test_no_title_line_falls_back_to_filename(self) -> None:
        source = forward.extract_pdf(Path("20261026 7 关于印发办法的通知.pdf"),
                                     text="正文没有标题行\n", use_ocr=False)
        self.assertEqual(source.title, "关于印发办法的通知")
        self.assertTrue(source.warnings)


class PackageTest(unittest.TestCase):
    def test_build_package_writes_docx_attachment_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx")
            out = Path(tmp) / "转发包"
            code = forward.main([
                "--source", str(src), "--out-dir", str(out),
                "--document-no", "廊发改技术〔2026〕368号",
                "--recipients", "各县（市、区）发改局",
                "--doc-date", "2026年10月29日",
                "--purpose", "贯彻落实省委省政府部署",
            ])
            self.assertEqual(code, 0)
            self.assertTrue((out / "转发通知.docx").is_file())
            self.assertTrue((out / "转发说明.md").is_file())
            attachments = [p for p in out.iterdir() if p.name.startswith("附件1")]
            self.assertEqual(len(attachments), 1)
            spec = json.loads((out / "转发通知.spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["documentNo"], "廊发改技术〔2026〕368号")
        self.assertEqual(spec["sources"][0]["documentNo"], "冀发改高技规〔2026〕11号")
        self.assertTrue(spec["title"].startswith("关于转发省发改委《"))
        self.assertTrue(spec["title"].endswith("的通知"))
        self.assertIn("〈河北省发展改革委企业技术中心管理办法〉", spec["title"])

    def test_missing_number_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx", with_number=False)
            out = Path(tmp) / "包"
            forward.main(["--source", str(src), "--out-dir", str(out), "--no-copy"])
            spec = json.loads((out / "转发通知.spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["sources"][0]["documentNo"], "【来文文号待核实】")

    def test_source_number_overrides_missing_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx", with_number=False)
            out = Path(tmp) / "包"
            forward.main(["--source", str(src), "--out-dir", str(out), "--no-copy",
                          "--source-number", "冀发改高技规〔2026〕11号"])
            spec = json.loads((out / "转发通知.spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["sources"][0]["documentNo"], "冀发改高技规〔2026〕11号")

    def test_no_copy_skips_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = make_provincial(Path(tmp) / "20261023 2 关于印发办法的通知.docx")
            out = Path(tmp) / "包"
            forward.main(["--source", str(src), "--out-dir", str(out), "--no-copy"])
            self.assertFalse([p for p in out.iterdir() if p.name.startswith("附件")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
