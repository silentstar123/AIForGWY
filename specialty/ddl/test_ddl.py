# -*- coding: utf-8 -*-
"""ddl.py 测试：用临时 STORE，固定 --on 日期。"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

import ddl


class DdlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name) / "tasks.json"
        self._patcher = mock.patch.object(ddl, "STORE", self.store)
        self._patcher.start()
        self.out = io.StringIO()

    def tearDown(self):
        self._patcher.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv):
        with redirect_stdout(self.out):
            ddl.main(list(argv))

    def tasks(self):
        return json.loads(self.store.read_text(encoding="utf-8"))["tasks"]

    # ---- add ----
    def test_add_once(self):
        self.run_cli("add", "数字政府报告", "--due", "2026-11-09")
        t = self.tasks()[0]
        self.assertEqual(t["kind"], "once")
        self.assertEqual(t["due"], "2026-11-09")
        self.assertIn("t001", self.out.getvalue())

    def test_add_recur_monthly(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.assertEqual(self.tasks()[0]["recur"], {"freq": "monthly", "day": 10})

    def test_add_recur_weekly_sunday_is_zero(self):
        self.run_cli("add", "周报", "--recur", "每周日")
        self.assertEqual(self.tasks()[0]["recur"], {"freq": "weekly", "weekday": 0})

    def test_add_recur_daily(self):
        self.run_cli("add", "打卡", "--recur", "每天")
        self.assertEqual(self.tasks()[0]["recur"]["freq"], "daily")

    def test_add_once_without_due_fails(self):
        with self.assertRaises(SystemExit):
            self.run_cli("add", "没日期的事")

    def test_add_bad_recur_fails(self):
        with self.assertRaises(SystemExit):
            self.run_cli("add", "怪任务", "--recur", "每季度")

    # ---- parse_recur ----
    def test_parse_recur_yearly(self):
        self.assertEqual(
            ddl.parse_recur("每年11月9日"),
            {"freq": "yearly", "month": 11, "day": 9},
        )

    # ---- occurrence_on ----
    def test_monthly_occurrence_same_month(self):
        r = {"freq": "monthly", "day": 10}
        self.assertEqual(ddl.occurrence_on(r, date(2026, 11, 6)), date(2026, 11, 10))

    def test_monthly_occurrence_clamps_short_month(self):
        r = {"freq": "monthly", "day": 31}
        self.assertEqual(ddl.occurrence_on(r, date(2026, 11, 6)), date(2026, 11, 30))

    def test_weekly_occurrence(self):
        r = {"freq": "weekly", "weekday": 0}  # 周一
        self.assertEqual(ddl.occurrence_on(r, date(2026, 11, 6)), date(2026, 11, 2))

    # ---- today ----
    def test_today_shows_overdue_and_today(self):
        self.run_cli("add", "逾期的事", "--due", "2026-11-04")
        self.run_cli("add", "今天截止", "--due", "2026-11-06")
        self.run_cli("add", "还有五天", "--due", "2026-11-11")
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-11-06")
        text = self.out.getvalue()
        self.assertIn("逾期2天", text)
        self.assertIn("今日截止", text)
        self.assertNotIn("还有五天", text)  # 默认窗口 3 天

    def test_today_recur_not_yet_due_shown_in_window(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-11-06", "--window", "4")
        self.assertIn("4天后", self.out.getvalue())
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-11-05", "--window", "3")
        self.assertNotIn("项目督导", self.out.getvalue())  # 5 天后超窗口

    def test_today_recur_overdue(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-11-12")
        self.assertIn("逾期2天", self.out.getvalue())

    def test_today_empty(self):
        self.out = io.StringIO()
        self.run_cli("today")
        self.assertIn("没有待办", self.out.getvalue())

    def test_done_once_disappears_from_today(self):
        self.run_cli("add", "交报告", "--due", "2026-11-06")
        self.run_cli("done", "t001", "--on", "2026-11-06")
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-11-06")
        self.assertIn("没有待办", self.out.getvalue())

    def test_done_recur_only_this_period(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.run_cli("done", "t001", "--on", "2026-11-10")
        self.assertEqual(self.tasks()[0]["doneDates"], ["2026-11-10"])
        # 勾的是 11 月的，12 月照样提醒
        self.out = io.StringIO()
        self.run_cli("today", "--on", "2026-12-10")
        self.assertIn("项目督导", self.out.getvalue())

    def test_done_recur_same_period_twice_no_duplicate(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.run_cli("done", "t001", "--on", "2026-11-10")
        self.run_cli("done", "t001", "--on", "2026-11-12")
        self.assertEqual(self.tasks()[0]["doneDates"], ["2026-11-10"])

    def test_done_by_index(self):
        self.run_cli("add", "甲", "--due", "2026-11-06")
        self.run_cli("add", "乙", "--due", "2026-11-06")
        self.run_cli("done", "2", "--on", "2026-11-06")
        ts = self.tasks()
        self.assertFalse(ts[0]["done"])
        self.assertTrue(ts[1]["done"])

    def test_remove(self):
        self.run_cli("add", "不要了", "--due", "2026-11-06")
        self.run_cli("remove", "t001")
        self.assertEqual(self.tasks(), [])

    def test_list_shows_recur_desc(self):
        self.run_cli("add", "项目督导", "--recur", "每月10号")
        self.out = io.StringIO()
        self.run_cli("list", "--on", "2026-11-06")
        self.assertIn("每月10号", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
