import http.client
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

from share_server import ShareServer


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "shared"
        self.root.mkdir()
        self.server = ShareServer(self.root, port=0, pin="1234")
        self.server.start()
        self.port = self.server.port
        self.cookie = None

    def tearDown(self):
        self.server.stop()
        self._tmp.cleanup()

    def request(self, method, path, body=None, headers=None, auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = dict(headers or {})
        if auth and self.cookie:
            h["Cookie"] = self.cookie
        conn.request(method, path, body=body, headers=h)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp, data

    def login(self, pin="1234"):
        resp, body = self.request(
            "POST", "/api/login", json.dumps({"pin": pin}).encode("utf-8"),
            {"Content-Type": "application/json", "X-Requested-With": "shareFile"},
            auth=False,
        )
        if resp.status == 200:
            raw = resp.getheader("Set-Cookie") or ""
            self.cookie = raw.split(";")[0]
        return resp, body


class AuthTests(ServerTestCase):
    def test_files_requires_login(self):
        resp, _ = self.request("GET", "/api/files", auth=False)
        self.assertEqual(resp.status, 401)

    def test_login_sets_cookie_and_session_reports_authed(self):
        resp, _ = self.login()
        self.assertEqual(resp.status, 200)
        self.assertIn("sf_session=", resp.getheader("Set-Cookie") or "")
        resp, body = self.request("GET", "/api/session")
        self.assertEqual(json.loads(body), {"authed": True})

    def test_session_reports_false_without_cookie(self):
        resp, body = self.request("GET", "/api/session", auth=False)
        self.assertEqual(resp.status, 200)
        self.assertEqual(json.loads(body), {"authed": False})

    def test_logout_revokes_session(self):
        self.login()
        resp, _ = self.request("POST", "/api/logout", b"", {"X-Requested-With": "shareFile"})
        self.assertEqual(resp.status, 200)
        resp, _ = self.request("GET", "/api/files")
        self.assertEqual(resp.status, 401)

    def test_wrong_pin_locks_after_five_attempts(self):
        for _ in range(5):
            resp, _ = self.login("0000")
            self.assertEqual(resp.status, 401)
        resp, body = self.login("0000")
        self.assertEqual(resp.status, 429)
        self.assertGreaterEqual(json.loads(body)["retry"], 1)

    def test_regenerate_pin_revokes_existing_session(self):
        self.login()
        self.server.regenerate_pin()
        resp, _ = self.request("GET", "/api/files")
        self.assertEqual(resp.status, 401)


class FilesApiTests(ServerTestCase):
    def test_lists_shared_files_after_login(self):
        (self.root / "a.txt").write_text("abc", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.mp4").write_bytes(b"x")
        self.login()
        resp, body = self.request("GET", "/api/files")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertEqual([f["path"] for f in data["files"]], ["a.txt", "sub/b.mp4"])
        self.assertFalse(data["read_only"])

    def test_port_falls_back_when_busy(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("0.0.0.0", 0))
        blocker.listen(1)
        busy = blocker.getsockname()[1]
        other = ShareServer(self.root, port=busy, pin="9999")
        try:
            actual = other.start()
            self.assertNotEqual(actual, busy)
        finally:
            other.stop()
            blocker.close()
