# -*- coding: utf-8 -*-
"""screen.py 的几何测试：画布坐标、摆位计算、显示器枚举。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import screen


class GeometryTest(unittest.TestCase):
    def test_parse_size(self) -> None:
        self.assertEqual(screen.parse_size("1280x800"), (1280, 800))
        self.assertEqual(screen.parse_size("1024X768"), (1024, 768))
        with self.assertRaises(SystemExit):
            screen.parse_size("big")

    def test_monitor_bbox(self) -> None:
        monitor = screen.Monitor(index=2, left=1920, top=0, width=1600, height=900, primary=False)
        self.assertEqual(monitor.bbox, (1920, 0, 3520, 900))

    def test_place_centers_window(self) -> None:
        monitor = screen.Monitor(index=2, left=1920, top=0, width=1600, height=900, primary=False)
        window = screen.Window(hwnd=1, title="x", left=0, top=0, width=100, height=100)
        plan = screen.place_window(window, monitor, size=(1200, 800), apply=False)
        self.assertEqual(plan["rect"], (2120, 50, 1200, 800))
        self.assertFalse(plan["applied"])

    def test_place_maximize_uses_full_monitor(self) -> None:
        monitor = screen.Monitor(index=1, left=0, top=0, width=1920, height=1080, primary=True)
        window = screen.Window(hwnd=2, title="x", left=0, top=0, width=10, height=10)
        plan = screen.place_window(window, monitor, maximize=True, apply=False)
        self.assertEqual(plan["rect"], (0, 0, 1920, 1080))

    def test_place_rejects_oversize(self) -> None:
        monitor = screen.Monitor(index=2, left=1920, top=0, width=1600, height=900, primary=False)
        window = screen.Window(hwnd=3, title="x", left=0, top=0, width=10, height=10)
        with self.assertRaises(SystemExit):
            screen.place_window(window, monitor, size=(2000, 900), apply=False)

    def test_monitors_enumerated(self) -> None:
        monitors = screen.list_monitors()
        self.assertGreaterEqual(len(monitors), 1)
        self.assertTrue(any(m.primary for m in monitors))
        for monitor in monitors:
            self.assertGreater(monitor.width, 0)
            self.assertGreater(monitor.height, 0)

    def test_window_lookup_returns_none_for_missing(self) -> None:
        self.assertIsNone(screen.find_window("这个标题一定不存在-9f3c2a"))


class ModeTest(unittest.TestCase):
    def test_devmode_layout_matches_windows(self) -> None:
        import ctypes

        self.assertEqual(ctypes.sizeof(screen.DEVMODE), 220)

    def test_set_mode_unknown_display_raises(self) -> None:
        with self.assertRaises(SystemExit):
            screen.set_mode(r"\\.\DISPLAY_NOT_EXIST", 800, 600)

    def test_virtual_monitor_index(self) -> None:
        try:
            index = screen.virtual_monitor_index()
        except SystemExit:
            self.skipTest("当前没有虚拟屏")
        self.assertGreaterEqual(index, 1)
        self.assertLessEqual(index, len(screen.list_monitors()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
