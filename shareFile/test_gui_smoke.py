import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def test_invalid_config_falls_back_to_defaults(self):
        import share_app
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{not json", encoding="utf-8")
            cfg = share_app.load_config(path, Path(tmp) / "shared")
            self.assertEqual(cfg["shared_dir"], str((Path(tmp) / "shared").resolve()))

    def test_address_selection_prefers_private_and_falls_back(self):
        import share_app
        self.assertEqual(share_app.choose_addresses([]), ["127.0.0.1"])
        self.assertEqual(
            share_app.choose_addresses(["8.8.8.8", "192.168.1.5", "10.0.0.2", "192.168.1.5"]),
            ["192.168.1.5", "10.0.0.2", "8.8.8.8"],
        )

    def test_writable_detection_uses_os_access(self):
        from unittest import mock
        import share_app
        with mock.patch("share_app.os.access", return_value=False):
            self.assertFalse(share_app.is_writable(Path(".")))


class GuiSmokeTests(unittest.TestCase):
    def test_window_layout_and_upload_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--probe", tmp],
                capture_output=True, text=True, timeout=90,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertGreaterEqual(data["window_w"], data["req_w"])
            self.assertGreaterEqual(data["min_w"], data["req_w"])
            self.assertTrue(data["path_fits"])
            self.assertRegex(data["pin"], r"^\d{4}$")
            self.assertTrue(data["address"].startswith("http://"))
            self.assertTrue(data["address"].endswith(":%d/" % data["port"]))
            self.assertTrue(data["file_saved"])
            self.assertGreaterEqual(data["transfer_rows"], 1)


def _probe(tmp):
    import time
    import urllib.request
    import share_app

    share_app.enable_dpi_awareness()
    shared = Path(tmp) / "shared"
    shared.mkdir()
    app = share_app.ShareApp(config_path=Path(tmp) / "config.json",
                             shared_dir=shared, port=0)
    app.update()
    app.update_idletasks()

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    base = "http://127.0.0.1:%d" % app.server.port
    login = urllib.request.Request(
        base + "/api/login",
        data=json.dumps({"pin": app.pin_var.get()}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Requested-With": "shareFile"},
    )
    opener.open(login, timeout=10).read()
    put = urllib.request.Request(
        base + "/api/upload?name=probe%20file.txt", data=b"hello", method="PUT",
        headers={"X-Requested-With": "shareFile"},
    )
    opener.open(put, timeout=10).read()

    deadline = time.time() + 3
    while time.time() < deadline and not app.transfer_tree.get_children():
        app.update()
        time.sleep(0.1)

    result = {
        "window_w": app.winfo_width(),
        "window_h": app.winfo_height(),
        "req_w": app.winfo_reqwidth(),
        "min_w": app.minsize()[0],
        "path_fits": app.path_label.winfo_reqwidth() <= app.winfo_width(),
        "pin": app.pin_var.get(),
        "address": app.address_var.get(),
        "port": app.server.port,
        "qr_items": len(app.qr_canvas.find_all()),
        "file_saved": (shared / "probe file.txt").read_bytes() == b"hello",
        "transfer_rows": len(app.transfer_tree.get_children()),
    }
    app.close()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__" and "--probe" in sys.argv:
    _probe(sys.argv[sys.argv.index("--probe") + 1])
