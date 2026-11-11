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


class DownloadTests(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.name = "video 片段.mp4"
        self.payload = bytes(range(256)) * 40
        (self.root / self.name).write_bytes(self.payload)
        self.login()

    def _path(self):
        return "/download?path=" + urllib.parse.quote(self.name)

    def test_download_requires_login(self):
        resp, _ = self.request("GET", self._path(), auth=False)
        self.assertEqual(resp.status, 401)

    def test_full_download(self):
        resp, body = self.request("GET", self._path())
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, self.payload)
        self.assertIn("attachment", resp.getheader("Content-Disposition"))
        self.assertEqual(resp.getheader("Accept-Ranges"), "bytes")

    def test_zero_byte_file_and_range(self):
        (self.root / "empty.txt").write_bytes(b"")
        path = "/download?path=empty.txt"
        resp, body = self.request("GET", path)
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(resp.getheader("Content-Length"), "0")
        resp, _ = self.request("GET", path, headers={"Range": "bytes=0-"})
        self.assertEqual(resp.status, 416)

    def test_closed_range(self):
        resp, body = self.request("GET", self._path(), headers={"Range": "bytes=100-199"})
        self.assertEqual(resp.status, 206)
        self.assertEqual(body, self.payload[100:200])
        self.assertEqual(resp.getheader("Content-Range"), "bytes 100-199/10240")

    def test_suffix_and_open_ranges(self):
        resp, body = self.request("GET", self._path(), headers={"Range": "bytes=-10"})
        self.assertEqual(body, self.payload[-10:])
        resp, body = self.request("GET", self._path(), headers={"Range": "bytes=10230-"})
        self.assertEqual(body, self.payload[10230:])

    def test_invalid_range_returns_416(self):
        resp, body = self.request("GET", self._path(), headers={"Range": "bytes=99999-"})
        self.assertEqual(resp.status, 416)
        self.assertEqual(resp.getheader("Content-Range"), "bytes */10240")

    def test_head_returns_length_without_body(self):
        resp, body = self.request("HEAD", self._path())
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(resp.getheader("Content-Length"), "10240")

    def test_traversal_is_rejected(self):
        (self.tmp / "secret.txt").write_text("secret", encoding="utf-8")
        resp, body = self.request("GET", "/download?path=" + urllib.parse.quote("../secret.txt"))
        self.assertIn(resp.status, (400, 403))
        self.assertNotIn(b"secret", body)

    def test_concurrent_downloads_are_identical(self):
        results = []

        def worker():
            results.append(self.request("GET", self._path())[1])

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r == self.payload for r in results))
