# -*- coding: utf-8 -*-
"""work.py 的工作会话测试：起、记步、收工、出报告。"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import work


class SessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = work.main(["--root", str(self.root), *args])
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def test_full_cycle(self) -> None:
        start = json.loads(self.run_cli("start", "--title", "处理收文", "--no-pet"))
        self.assertEqual(start["title"], "处理收文")
        name = start["session"]
        self.run_cli("--session", name, "step", "--note", "查收", "--artifact", "a.md")
        self.run_cli("--session", name, "finish", "--summary", "完成 1 件")
        text = self.run_cli("--session", name, "report")
        self.assertIn("处理收文", text)
        self.assertIn("查收", text)
        self.assertIn("产出：a.md", text)
        self.assertIn("完成 1 件", text)

    def test_status_and_list(self) -> None:
        self.run_cli("start", "--title", "甲", "--no-pet")
        self.assertIn("进行中", self.run_cli("status"))
        names = json.loads(self.run_cli("list"))
        self.assertEqual(len(names), 1)

    def test_missing_session_raises(self) -> None:
        with self.assertRaises(SystemExit):
            work.main(["--root", str(self.root), "status"])

    def test_unknown_session_raises(self) -> None:
        with self.assertRaises(SystemExit):
            work.load(self.root / "nope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
