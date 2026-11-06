# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import case_lib


class CaseLibTest(unittest.TestCase):
    def test_kind_from_filename_first(self) -> None:
        self.assertEqual(case_lib.kind_of("关于报送情况的通知"), "通知")
        self.assertEqual(case_lib.kind_of("请示1.docx"), "请示")
        self.assertEqual(case_lib.kind_of("回函.docx"), "函")

    def test_forwarding_notice_subtype(self) -> None:
        self.assertEqual(case_lib.kind_of("通知.docx",
                                          "关于转发省发改委《管理办法》的通知"), "转发通知")
        self.assertEqual(case_lib.kind_of("会签函.docx",
                                          "关于商请联合会签《关于转发某文件的通知》的函"), "函")

    def test_kind_from_title_fallback(self) -> None:
        self.assertEqual(case_lib.kind_of("无名文件.docx", "关于xx工作情况的报告"), "报告")

    def test_median(self) -> None:
        self.assertEqual(case_lib._median([16, 22, 18]), 18)
        self.assertEqual(case_lib._median([16, 18]), 17)
        self.assertIsNone(case_lib._median([]))

    def test_match_filters_kind_and_keyword(self) -> None:
        entries = [
            {"kind": "通知", "title": "关于场景汇的通知", "preview": "", "name": "a", "score": 9},
            {"kind": "报告", "title": "关于场景汇的报告", "preview": "", "name": "b", "score": 10},
        ]
        hits = case_lib.match(entries, kind="通知", keyword="场景汇")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "通知")

    def test_profile_uses_default_for_missing_font(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = case_lib.PROFILES
            case_lib.PROFILES = Path(tmp)
            try:
                case_lib.write_profiles([
                    {"kind": "函", "titleFont": "", "titleSize": 22, "bodyFont": "",
                     "bodySize": 16, "indentPt": 32, "lineSpacing": 28,
                     "marginsCm": [3.5, 3.5, 2.8, 2.8], "headings": [],
                     "id": "1", "title": "t", "file": "f"},
                ])
                profile = json.loads((Path(tmp) / "函.json").read_text(encoding="utf-8"))
            finally:
                case_lib.PROFILES = original
        self.assertEqual(profile["titleFont"], "")
        self.assertEqual(profile["sampleCount"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
