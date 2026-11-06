# -*- coding: utf-8 -*-
"""virtualscreen.py 的识别测试：分类、状态结构、无虚拟屏时的 require。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import virtualscreen


class ClassifyTest(unittest.TestCase):
    def test_virtual_adapters(self) -> None:
        for name in ("OrayIddDriver Device", "Virtual Display Driver", "usbmmidd",
                     "IddSampleDriver"):
            self.assertEqual(virtualscreen.classify(name), "virtual", name)

    def test_physical_adapters(self) -> None:
        for name in ("NVIDIA GeForce RTX 2080 SUPER", "Intel(R) UHD Graphics 750",
                     "Generic PnP Monitor"):
            self.assertEqual(virtualscreen.classify(name), "physical", name)


class StatusTest(unittest.TestCase):
    def test_status_shape(self) -> None:
        data = virtualscreen.status()
        self.assertIn("adapters", data)
        self.assertIn("virtualActive", data)
        self.assertIsInstance(data["virtualActive"], bool)
        for adapter in data["adapters"]:
            for key in ("name", "description", "attached", "virtual", "monitors"):
                self.assertIn(key, adapter)
            self.assertIsInstance(adapter["monitors"], list)

    def test_require_rejects_when_inactive(self) -> None:
        with self.assertRaises(SystemExit):
            virtualscreen.require_virtual({"virtualActive": False})

    def test_require_accepts_when_active(self) -> None:
        data = {"virtualActive": True, "virtualAdapter": "\\\\.\\DISPLAY9"}
        self.assertEqual(virtualscreen.require_virtual(data), data)

    def test_format_mentions_state(self) -> None:
        text = virtualscreen.format_status(virtualscreen.status())
        self.assertTrue("虚拟" in text or "没有启用中的虚拟屏" in text)

    def test_canvas_matches_active_virtual(self) -> None:
        data = virtualscreen.status()
        if data["virtualActive"]:
            self.assertIsNotNone(data["canvas"], "有虚拟屏时应当能给出画布")
            self.assertGreaterEqual(data["canvas"]["width"], 640)


class EnsureTest(unittest.TestCase):
    def fake_status(self, active: bool) -> dict:
        return {"adapters": [{"name": "\\\\.\\DISPLAY25", "description": "Virtual Display Driver",
                              "attached": active, "primary": False, "virtual": True,
                              "monitors": ["m"] if active else []}],
                "virtualActive": active, "virtualAdapter": "\\\\.\\DISPLAY25" if active else None,
                "monitors": [], "canvas": {"index": 3} if active else None}

    def test_ready_when_active(self) -> None:
        result = virtualscreen.ensure(status_fn=lambda: self.fake_status(True),
                                      runner=lambda cmd: None, sleep=lambda s: None)
        self.assertEqual(result["stage"], "ready")
        self.assertEqual(result["canvas"], {"index": 3})

    def test_extend_recovers(self) -> None:
        calls = {"n": 0}

        def fake_status():
            calls["n"] += 1
            return self.fake_status(calls["n"] > 1)

        commands = []
        result = virtualscreen.ensure(status_fn=fake_status,
                                      runner=lambda cmd: commands.append(cmd),
                                      sleep=lambda s: None)
        self.assertEqual(result["stage"], "extended")
        self.assertTrue(commands and commands[0][0] == "DisplaySwitch.exe")

    def test_needs_restart_when_device_present(self) -> None:
        result = virtualscreen.ensure(status_fn=lambda: self.fake_status(False),
                                      extend=False, runner=lambda cmd: None, sleep=lambda s: None)
        self.assertEqual(result["stage"], "needs-restart")
        self.assertIn("setup.ps1", result["hint"])

    def test_needs_install_when_nothing(self) -> None:
        empty = {"adapters": [], "virtualActive": False, "virtualAdapter": None,
                 "monitors": [], "canvas": None}
        result = virtualscreen.ensure(status_fn=lambda: empty, extend=False,
                                      runner=lambda cmd: None, sleep=lambda s: None)
        self.assertEqual(result["stage"], "needs-install")
        self.assertIn("install-vdd.ps1", result["hint"])


class CountTest(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vdd_settings.xml"
        self.path.write_text(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            "<vdd_settings><monitors><count>1</count></monitors>"
            "<gpu><friendlyname>default</friendlyname></gpu></vdd_settings>\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_configured_count(self) -> None:
        self.assertEqual(virtualscreen.configured_count(self.path), 1)

    def test_set_configured_count_keeps_other_tags(self) -> None:
        info = virtualscreen.set_configured_count(3, self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("<count>3</count>", text)
        self.assertIn("<friendlyname>default</friendlyname>", text)
        self.assertTrue(Path(info["backup"]).is_file())
        self.assertEqual(virtualscreen.configured_count(self.path), 3)

    def test_rejects_out_of_range(self) -> None:
        for bad in (0, 5):
            with self.assertRaises(ValueError):
                virtualscreen.set_configured_count(bad, self.path)

    def test_set_count_dry_run_is_pending(self) -> None:
        from unittest import mock

        with mock.patch.object(virtualscreen, "VDD_SETTINGS", self.path):
            result = virtualscreen.set_count(2)
        self.assertEqual(result["stage"], "pending")
        self.assertEqual(result["requested"], 2)
        self.assertEqual(virtualscreen.configured_count(self.path), 2)

    def test_set_count_needs_admin_when_restart_denied(self) -> None:
        class Denied:
            returncode = 1
            stdout = ""
            stderr = "Access is denied."

        from unittest import mock

        with mock.patch.object(virtualscreen, "VDD_SETTINGS", self.path):
            result = virtualscreen.set_count(2, apply=True,
                                             runner=lambda cmd: Denied(),
                                             sleep=lambda s: None,
                                             status_fn=lambda: {"virtualMonitors": []})
        self.assertEqual(result["stage"], "needs-admin")
        self.assertIn("pnputil", result["hint"])

    def test_set_count_elevate_retries_and_applies(self) -> None:
        class Denied:
            returncode = 1
            stdout = ""
            stderr = "Access is denied."

        class Ok:
            returncode = 0
            stdout = ""
            stderr = ""

        calls: list[list[str]] = []

        def runner(command):
            calls.append(command)
            return Denied() if command[0] == "pnputil" else Ok()

        from unittest import mock

        with mock.patch.object(virtualscreen, "VDD_SETTINGS", self.path):
            result = virtualscreen.set_count(
                2, apply=True, elevate=True, runner=runner, sleep=lambda s: None,
                status_fn=lambda: {"virtualMonitors": [{"index": 4}, {"index": 5}]})
        self.assertEqual(result["stage"], "applied")
        self.assertEqual(result["actual"], 2)
        self.assertTrue(any(command[0] == "powershell" for command in calls))


class HelperTest(unittest.TestCase):
    def test_request_restart_needs_helper(self) -> None:
        from unittest import mock

        with mock.patch.object(virtualscreen, "helper_status", lambda: {"installed": False}):
            result = virtualscreen.request_restart(timeout=1)
        self.assertEqual(result["stage"], "needs-helper")
        self.assertIn("install-helper.ps1", result["hint"])

    def test_request_restart_reads_helper_result(self) -> None:
        import json
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            flag = base / "restart.flag"
            result_file = base / "result.json"

            def fake_sleep(_seconds):
                result_file.write_text(json.dumps({"ok": True, "exitCode": 0}),
                                       encoding="utf-8")

            with mock.patch.object(virtualscreen, "HELPER_DIR", base), \
                    mock.patch.object(virtualscreen, "HELPER_FLAG", flag), \
                    mock.patch.object(virtualscreen, "HELPER_RESULT", result_file), \
                    mock.patch.object(virtualscreen, "helper_status",
                                      lambda: {"installed": True}):
                result = virtualscreen.request_restart(timeout=5, sleep=fake_sleep)
        self.assertEqual(result["stage"], "applied")
        self.assertTrue(result["result"]["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
