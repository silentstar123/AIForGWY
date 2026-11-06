# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import key_lib


class KeyLibTest(unittest.TestCase):
    def test_special_kinds(self) -> None:
        self.assertEqual(key_lib.kind_of("专报信息.docx"), "专报")
        self.assertEqual(key_lib.kind_of("第15期.docx", "副主任办公会议纪要"), "纪要")
        self.assertEqual(key_lib.kind_of("通知.docx", "关于转发省发改委文件的通知"), "转发通知")

    def test_body_paragraphs_filters_short_and_recipient(self) -> None:
        paragraphs = ["市发改委：", "短", "这是一段足够长的正文内容，用来测试过滤。"]
        self.assertEqual(key_lib.body_paragraphs(paragraphs),
                         ["这是一段足够长的正文内容，用来测试过滤。"])

    def test_score_prefers_authored_minutes(self) -> None:
        entry = {"kind": "纪要", "titleFont": "方正小标宋简体", "titleSize": 22,
                 "titleAlign": 1, "bodyFont": "仿宋_GB2312", "bodySize": 16,
                 "indentPt": 32, "marginsCm": [3.5, 3.5, 2.7, 2.7],
                 "recipient": "", "date": "2026年1月1日", "tables": 0, "chars": 1200}
        ordinary = key_lib.score(entry, Path(r"G:\高技术\普通\a.docx"))
        authored = key_lib.score(entry, Path(r"G:\高技术\副主任办公会议纪要\第2期.docx"))
        self.assertGreater(authored, ordinary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
