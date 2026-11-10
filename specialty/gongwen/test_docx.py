# -*- coding: utf-8 -*-
"""docx.py 的版式回归测试：不看渲染效果，只核对 Word 里会保存的属性。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx import Document
from docx.oxml.ns import qn

import gongwen_docx


def east_asia(run) -> str | None:
    rpr = run._element.rPr
    if rpr is None or rpr.rFonts is None:
        return None
    return rpr.rFonts.get(qn("w:eastAsia"))


class ForwardNoticeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = gongwen_docx.load_profile()
        self.spec = {
            "kind": "转发通知",
            "issuer": "廊坊市发展和改革委员会",
            "documentNo": "廊发改技术〔2026〕368号",
            "sourceOrgan": "省发改委",
            "sources": [
                {"title": "河北省新兴产业创新中心管理办法", "documentNo": "冀发改高技规〔2026〕9号"},
                {"title": "河北省产业技术工程化中心管理办法", "documentNo": "冀发改高技规〔2026〕10号"},
            ],
            "purpose": "全面落实创新驱动发展战略",
            "requirement": "认真贯彻执行",
            "recipients": ["市有关部门", "各县（市、区）发改局"],
            "attachments": ["1. 河北省新兴产业创新中心管理办法", "2. 河北省产业技术工程化中心管理办法"],
            "signers": ["廊坊市发展和改革委员会"],
            "date": "2026年10月27日",
        }
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out.docx"
        gongwen_docx.build(self.spec, self.profile, self.out)
        self.doc = Document(str(self.out))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_page_and_margins(self) -> None:
        sec = self.doc.sections[0]
        self.assertAlmostEqual(sec.page_width.cm, 21.0, places=1)
        self.assertAlmostEqual(sec.page_height.cm, 29.7, places=1)
        self.assertAlmostEqual(sec.top_margin.cm, 3.5, places=1)
        self.assertAlmostEqual(sec.left_margin.cm, 2.7, places=1)

    def test_title_uses_xiaobiaosong_22(self) -> None:
        titles = [p for p in self.doc.paragraphs if p.text.startswith("关于转发")]
        self.assertEqual(len(titles), 1)
        run = titles[0].runs[0]
        self.assertEqual(east_asia(run), "方正小标宋简体")
        self.assertEqual(run.font.size.pt, 22)

    def test_body_uses_fangsong_16_and_exact_spacing(self) -> None:
        body = [p for p in self.doc.paragraphs if p.text.startswith("为全面落实")]
        self.assertEqual(len(body), 1)
        para = body[0]
        self.assertEqual(east_asia(para.runs[0]), "仿宋_GB2312")
        self.assertEqual(para.runs[0].font.size.pt, 16)
        self.assertAlmostEqual(para.paragraph_format.first_line_indent.pt, 32, places=1)
        self.assertAlmostEqual(para.paragraph_format.line_spacing.pt, 28, places=1)

    def test_recipients_line_ends_with_colon(self) -> None:
        line = [p for p in self.doc.paragraphs if p.text.startswith("市有关部门")][0]
        self.assertTrue(line.text.endswith("："))

    def test_forward_body_mentions_both_sources(self) -> None:
        text = "\n".join(p.text for p in self.doc.paragraphs)
        self.assertIn("冀发改高技规〔2026〕9号", text)
        self.assertIn("冀发改高技规〔2026〕10号", text)
        self.assertIn("一并转发给你们", text)

    def test_signature_and_date_are_right_aligned(self) -> None:
        sig = [p for p in self.doc.paragraphs if p.text == "廊坊市发展和改革委员会"][-1]
        date = [p for p in self.doc.paragraphs if p.text == "2026年10月27日"][0]
        self.assertEqual(str(sig.paragraph_format.alignment), "RIGHT (2)")
        self.assertEqual(str(date.paragraph_format.alignment), "RIGHT (2)")

    def test_footer_has_page_field(self) -> None:
        xml = self.doc.sections[0].footer.paragraphs[0]._p.xml
        self.assertIn("PAGE", xml)


class HeadingTest(unittest.TestCase):
    def test_levels(self) -> None:
        self.assertEqual(gongwen_docx.heading_level("一、总体要求"), 1)
        self.assertEqual(gongwen_docx.heading_level("（二）重点任务"), 2)
        self.assertEqual(gongwen_docx.heading_level("1. 具体事项"), 0)

    def test_nested_title(self) -> None:
        self.assertEqual(
            gongwen_docx.nest_title("转发《关于印发〈甲〉的通知》"),
            "转发《关于印发〈甲〉的通知》",
        )
        self.assertEqual(
            gongwen_docx.nest_title("关于转发《关于印发《甲》的通知》的通知"),
            "关于转发《关于印发〈甲〉的通知》的通知",
        )
        self.assertEqual(
            gongwen_docx.wrap_title("关于印发《甲》的通知"),
            "《关于印发〈甲〉的通知》",
        )


class TemplateTest(unittest.TestCase):
    def test_every_kind_builds(self) -> None:
        profile = gongwen_docx.load_profile()
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ("通知", "请示", "报告", "函", "批复", "纪要", "转发通知"):
                spec = gongwen_docx.template(kind)
                self.assertEqual(spec["kind"], kind)
                if kind == "转发通知":
                    spec.update({
                        "issuer": "某委", "documentNo": "〔2026〕1号",
                        "sourceOrgan": "省厅",
                        "sources": [{"title": "甲办法", "documentNo": "〔2026〕2号"}],
                        "recipients": ["各单位"], "signers": ["某委"], "date": "2026年1月1日",
                    })
                out = Path(tmp) / f"{kind}.docx"
                gongwen_docx.build(spec, profile, out)
                self.assertTrue(out.is_file())


class BodyLayoutTest(unittest.TestCase):
    def test_heading_uses_hei_ti_and_subheading_kai_ti(self) -> None:
        profile = gongwen_docx.load_profile()
        spec = {
            "kind": "通知", "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": "关于加强某项工作的通知", "recipients": ["各单位"],
            "body": ["一、总体要求", "（一）重点任务", "正文内容。"],
            "signers": ["某委"], "date": "2026年1月1日",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a.docx"
            gongwen_docx.build(spec, profile, out)
            doc = Document(str(out))
        h1 = [p for p in doc.paragraphs if p.text == "一、总体要求"][0]
        h2 = [p for p in doc.paragraphs if p.text == "（一）重点任务"][0]
        self.assertEqual(east_asia(h1.runs[0]), "黑体")
        self.assertEqual(east_asia(h2.runs[0]), "楷体_GB2312")

    def test_body_dict_entry_uses_custom_font(self) -> None:
        # 撤销请示的无编号节标题：{"text": ..., "font": "黑体"}
        profile = gongwen_docx.load_profile()
        spec = {
            "kind": "请示", "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": "关于撤销某中心的请示", "recipients": ["省发改委"],
            "body": [
                "现将具体情况汇报如下：",
                {"text": "某中心全称", "font": "黑体"},
                "该中心于2024年批复建设。",
            ],
            "signers": ["某委"], "date": "2026年1月1日",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "c.docx"
            gongwen_docx.build(spec, profile, out)
            doc = Document(str(out))
        heading = [p for p in doc.paragraphs if p.text == "某中心全称"][0]
        self.assertEqual(east_asia(heading.runs[0]), "黑体")
        body = [p for p in doc.paragraphs if p.text == "该中心于2024年批复建设。"][0]
        self.assertEqual(east_asia(body.runs[0]), "仿宋_GB2312")

    def test_meta_lines_render_for_minutes(self) -> None:
        profile = gongwen_docx.load_profile()
        spec = gongwen_docx.template("纪要")
        spec.update({
            "title": "某会议纪要", "recipients": [],
            "meta": {"time": "2026年10月27日", "place": "第一会议室", "host": "某某"},
            "signers": [], "body": ["会议听取了有关情况。"],
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.docx"
            gongwen_docx.build(spec, profile, out)
            doc = Document(str(out))
        time_line = [p for p in doc.paragraphs if p.text.startswith("时间：")][0]
        self.assertEqual(time_line.text, "时间：2026年10月27日")
        self.assertEqual(east_asia(time_line.runs[0]), "黑体")


class LearnTest(unittest.TestCase):
    def test_learn_recovers_profile_from_built_samples(self) -> None:
        profile = gongwen_docx.load_profile()
        spec = gongwen_docx.template("通知")
        spec.update({
            "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": "关于加强某项工作的通知", "recipients": ["各单位"],
            "body": ["为做好有关工作，现将有关事项通知如下。", "一、总体要求", "请认真贯彻执行。"],
            "signers": ["某委"], "date": "2026年1月1日",
        })
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(3):
                gongwen_docx.build(spec, profile, Path(tmp) / f"{i}.docx")
            learned = gongwen_docx.learn([tmp], profile)
        self.assertEqual(learned["samples"], 3)
        self.assertEqual(learned["bodyFont"], "仿宋_GB2312")
        self.assertEqual(learned["bodySizePt"], 16)
        self.assertEqual(learned["lineSpacingPt"], 28)
        self.assertEqual(learned["marginsCm"]["left"], 2.7)
        self.assertEqual(learned["firstLineIndentPt"], 32)

    def test_apply_learned_keeps_unknown_fields(self) -> None:
        profile = gongwen_docx.load_profile()
        learned = {
            "page": {"widthCm": 21.0, "heightCm": 29.7},
            "marginsCm": {"top": 3.5, "bottom": 3.5, "left": 2.8, "right": 2.6},
            "bodyFont": "仿宋", "bodySizePt": 16, "lineSpacingPt": 29.2, "firstLineIndentPt": 32,
        }
        updated = gongwen_docx.apply_learned(profile, learned)
        self.assertEqual(updated["fonts"]["body"], "仿宋")
        self.assertEqual(updated["page"]["marginLeftCm"], 2.8)
        self.assertEqual(updated["spacing"]["lineSpacingPt"], 29.2)
        self.assertEqual(updated["fonts"]["title"], "方正小标宋简体")


class CheckTest(unittest.TestCase):
    def test_generated_notice_passes_check(self) -> None:
        profile = gongwen_docx.load_profile()
        spec = gongwen_docx.template("通知")
        spec.update({"issuer": "某委", "documentNo": "〔2026〕1号",
                     "title": "关于加强某项工作的通知", "recipients": ["各单位"],
                     "body": ["为做好有关工作，现将有关事项通知如下。", "请认真贯彻执行。"],
                     "signers": ["某委"], "date": "2026年1月1日"})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ok.docx"
            gongwen_docx.build(spec, profile, out)
            result = gongwen_docx.check(out, profile)
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(result["observed"]["bodyFont"], "仿宋_GB2312")

    def test_wrong_body_font_is_reported(self) -> None:
        profile = gongwen_docx.load_profile()
        spec = gongwen_docx.template("通知")
        spec.update({"issuer": "某委", "documentNo": "〔2026〕1号",
                     "title": "关于加强某项工作的通知", "recipients": ["各单位"],
                     "body": ["为做好有关工作，现将有关事项通知如下。"],
                     "signers": ["某委"], "date": "2026年1月1日"})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bad.docx"
            gongwen_docx.build(spec, profile, out)
            doc = Document(str(out))
            body = [p for p in doc.paragraphs if p.text.startswith("为做好")][0]
            for run in body.runs:
                gongwen_docx.set_run(run, ea="宋体", size_pt=14)
            doc.save(str(out))
            result = gongwen_docx.check(out, profile)
        self.assertFalse(result["ok"])
        self.assertTrue(any("正文字体" in issue for issue in result["issues"]))
        self.assertTrue(any("正文字号" in issue for issue in result["issues"]))


class BuildExtrasTest(unittest.TestCase):
    def build_doc(self, spec: dict) -> Document:
        profile = gongwen_docx.load_profile()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        out = Path(self.tmp.name) / "x.docx"
        gongwen_docx.build(spec, profile, out)
        return Document(str(out))

    def test_wrap_title_lines_balances(self) -> None:
        self.assertEqual(gongwen_docx.wrap_title_lines("关于某事的通知"), ["关于某事的通知"])
        title = "关于转发省发改委《关于印发创新平台管理办法的通知》的通知"
        lines = gongwen_docx.wrap_title_lines(title, 20)
        self.assertEqual("".join(lines), title)
        self.assertTrue(all(len(line) <= 20 for line in lines))
        self.assertGreaterEqual(len(lines), 2)

    def test_long_title_is_split_in_docx(self) -> None:
        # 默认标题整段一行自然换行；确需手排时给 titleLines
        medium = "关于转发省发改委《关于印发河北省企业技术中心管理办法的通知》的通知"
        doc = self.build_doc({
            "kind": "通知", "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": medium, "recipients": ["各单位"], "body": ["正文。"],
            "signers": ["某委"], "date": "2026年1月1日",
        })
        title_paras = [p for p in doc.paragraphs
                       if p.runs and p.runs[0].font.size and p.runs[0].font.size.pt == 22
                       and p.text != "某委"]
        self.assertEqual(len(title_paras), 1)
        self.assertEqual(title_paras[0].text, medium)

    def test_title_lines_override_splits(self) -> None:
        title = "关于转发省发改委《关于印发河北省新兴产业创新中心管理办法和产业技术工程化中心管理办法的通知》的通知"
        doc = self.build_doc({
            "kind": "通知", "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": title,
            "titleLines": ["关于转发省发改委《关于印发河北省新兴产业创新中心", "管理办法和产业技术工程化中心管理办法的通知》的通知"],
            "recipients": ["各单位"], "body": ["正文。"],
            "signers": ["某委"], "date": "2026年1月1日",
        })
        title_paras = [p for p in doc.paragraphs
                       if p.runs and p.runs[0].font.size and p.runs[0].font.size.pt == 22
                       and p.text != "某委"]
        self.assertGreaterEqual(len(title_paras), 2)
        self.assertEqual("".join(p.text for p in title_paras), title)

    def test_approval_signer_shares_line_with_document_number(self) -> None:
        doc = self.build_doc({
            "kind": "请示", "issuer": "某委", "documentNo": "廊发改〔2026〕9号",
            "signer": "张三", "title": "关于购置设备的请示", "recipients": ["市局"],
            "body": ["理由。", "妥否，请批示。"], "signers": ["某委"], "date": "2026年1月1日",
        })
        line = [p for p in doc.paragraphs if "签发人" in p.text][0]
        self.assertIn("廊发改〔2026〕9号", line.text)
        self.assertIn("签发人：张三", line.text)
        self.assertEqual(str(line.paragraph_format.alignment), "LEFT (0)")
        name_run = [r for r in line.runs if r.text == "张三"][0]
        self.assertEqual(east_asia(name_run), "楷体_GB2312")

    def test_red_line_border(self) -> None:
        doc = self.build_doc({
            "kind": "通知", "issuer": "某委", "documentNo": "〔2026〕1号", "redLine": True,
            "title": "关于某事的通知", "recipients": ["各单位"], "body": ["正文。"],
            "signers": ["某委"], "date": "2026年1月1日",
        })
        borders = [p for p in doc.paragraphs if "w:pBdr" in p._p.xml]
        self.assertTrue(any("FF0000" in p._p.xml for p in borders))

    def test_forward_rejects_numbered_sections(self) -> None:
        with self.assertRaises(SystemExit):
            self.build_doc({
                "kind": "转发通知", "title": "关于转发某文件的通知",
                "recipients": ["各单位"],
                "body": ["现转发给你们，请认真贯彻执行。", "一、请按要求办理。"],
                "signers": ["某委"], "date": "2026年1月1日",
            })

    def test_forward_allows_sections_when_explicit(self) -> None:
        doc = self.build_doc({
            "kind": "转发通知", "title": "关于转发某文件的通知",
            "recipients": ["各单位"],
            "body": ["现转发给你们，请认真贯彻执行。", "一、请按要求办理。"],
            "signers": ["某委"], "date": "2026年1月1日", "allowSections": True,
        })
        self.assertTrue(any("一、请按要求办理" in p.text for p in doc.paragraphs))

    def test_masthead_block(self) -> None:
        doc = self.build_doc({
            "kind": "通知", "issuer": "某委", "documentNo": "〔2026〕1号",
            "title": "关于某事的通知", "recipients": ["各单位"], "body": ["正文。"],
            "signers": ["某委"], "date": "2026年1月1日",
            "cc": "各县（市、区）发改局", "printer": "某委办公室", "printDate": "2026年10月29日",
        })
        cc_line = [p for p in doc.paragraphs if p.text.startswith("抄送：")][0]
        self.assertIn("w:pBdr", cc_line._p.xml)
        print_line = [p for p in doc.paragraphs if "某委办公室" in p.text][0]
        self.assertIn("2026年10月29日印发", print_line.text)
        self.assertIn("w:tab", print_line._p.xml)

    def test_minutes_template_has_no_masthead_fields(self) -> None:
        spec = gongwen_docx.template("纪要")
        self.assertEqual(spec["issuer"], "")
        self.assertEqual(spec["documentNo"], "")
        self.assertEqual(spec["signers"], [])

    def test_template_titles_match_kind(self) -> None:
        for kind in ("通知", "请示", "报告", "函", "批复"):
            self.assertTrue(gongwen_docx.template(kind)["title"].endswith(kind), kind)


if __name__ == "__main__":
    unittest.main(verbosity=2)
