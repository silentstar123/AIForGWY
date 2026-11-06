# -*- coding: utf-8 -*-
"""vision.py 的几何、网格、OCR 框和模板匹配测试（不点真实鼠标）。"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

import vision  # 先导入 vision，它会把自己依赖的 screen 目录加进 sys.path
import screen  # noqa: E402


class GridTest(unittest.TestCase):
    def test_grid_lines(self) -> None:
        xs, ys = vision.grid_lines(250, 120, 100)
        self.assertEqual(xs, [0, 100, 200])
        self.assertEqual(ys, [0, 100])

    def test_draw_grid_keeps_size(self) -> None:
        image = Image.new("RGB", (220, 130), "white")
        out = vision.draw_grid(image, 100)
        self.assertEqual(out.size, (220, 130))


class BoxTest(unittest.TestCase):
    def test_box_from_points(self) -> None:
        box = vision.box_from_points([[10, 20], [60, 20], [60, 40], [10, 40]], "登录", 0.98)
        self.assertEqual((box.left, box.top, box.right, box.bottom), (10, 20, 60, 40))
        self.assertEqual(box.center, (35, 30))


class MapTest(unittest.TestCase):
    SIDE = {"bbox": [100, 200, 900, 800], "width": 800, "height": 600, "source": "monitor:1"}

    def test_map_point(self) -> None:
        self.assertEqual(vision.map_point(self.SIDE, 0, 0), (100, 200))
        self.assertEqual(vision.map_point(self.SIDE, 799, 599), (899, 799))

    def test_out_of_bounds(self) -> None:
        with self.assertRaises(SystemExit):
            vision.map_point(self.SIDE, 800, 10)

    def test_monitor_source_never_changed(self) -> None:
        self.assertFalse(vision.bbox_changed(self.SIDE))


class ComboTest(unittest.TestCase):
    def test_parse_combo(self) -> None:
        self.assertEqual(vision.parse_combo("ctrl+a"), [0x11, 0x41])
        self.assertEqual(vision.parse_combo("ctrl+shift+enter"), [0x11, 0x10, 0x0D])

    def test_unknown_key(self) -> None:
        with self.assertRaises(SystemExit):
            vision.parse_combo("ctrl+不存在")


class ShotTest(unittest.TestCase):
    def test_write_and_load_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shot.png"
            image = Image.new("RGB", (300, 200), "white")
            data = vision.write_shot(image, (10, 20, 310, 220), "monitor:1", out,
                                     grid=True, ocr=False)
            self.assertTrue(out.is_file())
            loaded = vision.load_sidecar(out.with_suffix(".json"))
        self.assertEqual(loaded["width"], 300)
        self.assertEqual(loaded["bbox"], [10, 20, 310, 220])
        self.assertEqual(data["source"], "monitor:1")

    def test_click_dry_run_maps_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "shot.json"
            sidecar.write_text(json.dumps({
                "file": "x.png", "bbox": [100, 200, 400, 400], "width": 300, "height": 200,
                "source": "monitor:1", "ocr": []}), encoding="utf-8")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = vision.main(["click", "--shot", str(sidecar), "--x", "30", "--y", "40"])
        self.assertEqual(code, 0)
        result = json.loads(buffer.getvalue())
        self.assertEqual(result["wouldClick"], [130, 240])

    def test_drag_raw_keeps_absolute_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "shot.json"
            sidecar.write_text(json.dumps({
                "file": "x.png", "bbox": [3520, 0, 5440, 1080], "width": 1920,
                "height": 1080, "source": "monitor:3", "ocr": []}), encoding="utf-8")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = vision.main(["drag", "--shot", str(sidecar), "--x1", "5000", "--y1", "16",
                                    "--x2", "600", "--y2", "200", "--raw"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["wouldDrag"],
                         [[5000, 16], [600, 200]])


class TemplateTest(unittest.TestCase):
    def test_find_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Image.new("RGB", (200, 120), "white")
            for x in range(70, 100):
                for y in range(40, 70):
                    edge = x in (70, 71, 98, 99) or y in (40, 41, 68, 69)
                    base.putpixel((x, y), (0, 0, 0) if edge else (200, 200, 200))
            image_path = Path(tmp) / "screen.png"
            base.save(image_path)
            template = base.crop((70, 40, 100, 70))
            template_path = Path(tmp) / "tpl.png"
            template.save(template_path)
            result = vision.find_template(image_path, template_path, 0.95)
        self.assertTrue(result["found"], result)
        self.assertEqual(result["center"], [85, 55])
        self.assertGreater(result["score"], 0.95)

    def test_uniform_template_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "a.png"
            template = Path(tmp) / "b.png"
            Image.new("RGB", (60, 60), "white").save(image)
            Image.new("RGB", (10, 10), "black").save(template)
            with self.assertRaises(SystemExit):
                vision.find_template(image, template)


class PickBoxTest(unittest.TestCase):
    BOXES = [
        vision.Box(text="搜索或输入 Web 地址", score=0.9, left=10, top=10, right=200, bottom=30),
        vision.Box(text="登录", score=0.9, left=300, top=10, right=340, bottom=30),
        vision.Box(text="登录状态", score=0.9, left=300, top=40, right=380, bottom=60),
    ]

    def test_exact_match_wins(self) -> None:
        box = vision.pick_box(self.BOXES, "登录")
        self.assertEqual(box.left, 300)
        self.assertEqual(box.top, 10)

    def test_substring_match(self) -> None:
        box = vision.pick_box(self.BOXES, "Web 地址")
        self.assertIn("Web", box.text)

    def test_missing_returns_none(self) -> None:
        self.assertIsNone(vision.pick_box(self.BOXES, "不存在的文字"))


class FastCaptureTest(unittest.TestCase):
    def test_grab_size(self) -> None:
        image = vision.grab((0, 0, 120, 80))
        self.assertEqual(image.size, (120, 80))

    def test_diff_detects_change(self) -> None:
        a = Image.new("RGB", (60, 40), "white")
        b = a.copy()
        for x in range(10, 20):
            for y in range(10, 20):
                b.putpixel((x, y), (0, 0, 0))
        result = vision.diff_images(a, b)
        self.assertGreater(result["changedRatio"], 0)
        self.assertEqual(result["box"], [10, 10, 20, 20])

    def test_diff_identical_is_zero(self) -> None:
        a = Image.new("RGB", (30, 30), "white")
        self.assertEqual(vision.diff_images(a, a)["changedRatio"], 0.0)

    def test_watch_reports_motion(self) -> None:
        still = Image.new("RGB", (40, 30), "white")
        moving = still.copy()
        moving.putpixel((5, 5), (0, 0, 0))
        frames = [still, still, moving, still]
        counter = {"i": 0}

        def fake_grab(_bbox):
            value = frames[counter["i"] % len(frames)]
            counter["i"] += 1
            return value

        original = vision.grab
        vision.grab = fake_grab
        try:
            result = vision.watch((0, 0, 40, 30), seconds=0.05, fps=200)
        finally:
            vision.grab = original
        self.assertGreaterEqual(result["frames"], 2)
        self.assertGreater(result["maxChange"], 0)


class AskTest(unittest.TestCase):
    def test_payload_contains_image_and_prompt(self) -> None:
        import io as _io
        from unittest import mock

        captured = {}

        class FakeResponse(_io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_open(request, timeout=None):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(json.dumps({"response": "点左上角", "done": True}).encode())

        class FakeOpener:
            def open(self, request, timeout=None):
                return fake_open(request, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "shot.png"
            Image.new("RGB", (20, 20), "white").save(image)
            with mock.patch("urllib.request.build_opener", lambda *a, **k: FakeOpener()):
                result = vision.ollama_ask(image, "按钮在哪？", model="qwen2.5vl:3b")
        self.assertEqual(result["response"], "点左上角")
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/generate")
        self.assertEqual(captured["body"]["model"], "qwen2.5vl:3b")
        self.assertEqual(captured["body"]["prompt"], "按钮在哪？")
        self.assertTrue(captured["body"]["images"][0])


class StaleAndWaitTest(unittest.TestCase):
    def make_shot(self, tmp: str) -> dict:
        image = Path(tmp) / "shot.png"
        Image.new("RGB", (60, 40), "white").save(image)
        return {"file": str(image), "bbox": [0, 0, 60, 40], "width": 60, "height": 40,
                "source": "monitor:1", "ocr": []}

    def test_verify_same_image_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = self.make_shot(tmp)
            original = vision.grab
            vision.grab = lambda bbox: Image.new("RGB", (60, 40), "white")
            try:
                result = vision.verify_shot(sidecar)
            finally:
                vision.grab = original
        self.assertTrue(result["ok"])

    def test_verify_changed_image_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = self.make_shot(tmp)
            changed = Image.new("RGB", (60, 40), "black")
            original = vision.grab
            vision.grab = lambda bbox: changed
            try:
                result = vision.verify_shot(sidecar)
            finally:
                vision.grab = original
        self.assertFalse(result["ok"])
        self.assertEqual(result["changedRatio"], 1.0)

    def test_wait_stable_returns(self) -> None:
        still = Image.new("RGB", (30, 20), "white")
        original = vision.grab
        vision.grab = lambda bbox: still
        try:
            result = vision.wait_stable((0, 0, 30, 20), interval=0.001, stable=2, timeout=1)
        finally:
            vision.grab = original
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["frames"], 3)

    def test_wait_stable_times_out(self) -> None:
        original = vision.grab
        counter = {"i": 0}

        def noisy(_bbox):
            counter["i"] += 1
            return Image.new("RGB", (30, 20), "white" if counter["i"] % 2 else "black")

        vision.grab = noisy
        try:
            result = vision.wait_stable((0, 0, 30, 20), interval=0.001, stable=2, timeout=0.05)
        finally:
            vision.grab = original
        self.assertFalse(result["ok"])

    def test_doctor_reports_environment(self) -> None:
        result = vision.doctor()
        self.assertIn("mss", result)
        self.assertIn("ocr", result)
        self.assertIsNotNone(result["capture"])


class WindowTargetTest(unittest.TestCase):
    def test_resolve_by_hwnd_matches_listed_window(self) -> None:
        windows = screen.list_windows()
        if not windows:
            self.skipTest("没有可见窗口")
        target = windows[0]
        found = screen.resolve_window(hwnd=target.hwnd)
        self.assertIsNotNone(found)
        self.assertEqual(found.hwnd, target.hwnd)

    def test_resolve_missing_hwnd(self) -> None:
        self.assertIsNone(screen.resolve_window(hwnd=999999999))

    def test_find_windows_sorted_by_area(self) -> None:
        matches = screen.find_windows("Microsoft Edge")
        areas = [w.width * w.height for w in matches]
        self.assertEqual(areas, sorted(areas, reverse=True))


class TraceTest(unittest.TestCase):
    def test_trace_appends_jsonl(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(vision, "HERE", Path(tmp)):
                vision.trace({"action": "click", "point": [1, 2]})
                files = list((Path(tmp) / "traces").glob("*.jsonl"))
                self.assertEqual(len(files), 1)
                record = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["action"], "click")
        self.assertEqual(record["point"], [1, 2])


class ChooseFileTest(unittest.TestCase):
    def test_dry_run_without_dialog(self) -> None:
        from unittest import mock

        with mock.patch.object(vision, "find_file_dialog", lambda: None):
            with self.assertRaises(SystemExit):
                vision.choose_file("C:\\x.txt", dry_run=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
