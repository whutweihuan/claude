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
from unittest import mock

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

    def login_cookie(self, port, pin="1234"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(
            "POST", "/api/login", json.dumps({"pin": pin}).encode("utf-8"),
            {"Content-Type": "application/json", "X-Requested-With": "shareFile"},
        )
        resp = conn.getresponse()
        cookie = (resp.getheader("Set-Cookie") or "").split(";")[0]
        resp.read()
        conn.close()
        return cookie


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


class UploadTests(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.headers = {"X-Requested-With": "shareFile"}

    def upload(self, name, data):
        return self.request(
            "PUT", "/api/upload?name=" + urllib.parse.quote(name),
            data, self.headers,
        )

    def test_upload_requires_login(self):
        resp, _ = self.request(
            "PUT", "/api/upload?name=a.txt", b"x",
            {"X-Requested-With": "shareFile"}, auth=False,
        )
        self.assertEqual(resp.status, 401)

    def test_upload_and_download_roundtrip_utf8_name(self):
        data = os.urandom(8 * 1024 * 1024)
        name = "手机 录像 01.mp4"
        resp, body = self.upload(name, data)
        self.assertEqual(resp.status, 201)
        self.assertEqual(json.loads(body)["name"], name)
        self.assertEqual((self.root / name).read_bytes(), data)
        resp, got = self.request("GET", "/download?path=" + urllib.parse.quote(name))
        self.assertEqual(got, data)
        resp, listing = self.request("GET", "/api/files")
        self.assertIn(name, [f["path"] for f in json.loads(listing)["files"]])

    def test_duplicate_upload_gets_suffix(self):
        self.upload("a.txt", b"hello")
        resp, body = self.upload("a.txt", b"world")
        self.assertEqual(json.loads(body)["name"], "a (1).txt")
        self.assertEqual((self.root / "a.txt").read_bytes(), b"hello")
        self.assertEqual((self.root / "a (1).txt").read_bytes(), b"world")

    def test_name_with_traversal_stays_in_root(self):
        resp, body = self.upload("../../evil.txt", b"x")
        self.assertEqual(resp.status, 201)
        self.assertEqual(json.loads(body)["name"], "evil.txt")
        self.assertFalse((self.tmp / "evil.txt").exists())
        self.assertTrue((self.root / "evil.txt").exists())

    def test_empty_body_rejected(self):
        resp, _ = self.upload("a.txt", b"")
        self.assertEqual(resp.status, 400)

    def test_missing_csrf_header_rejected(self):
        resp, _ = self.request("PUT", "/api/upload?name=a.txt", b"x", {})
        self.assertEqual(resp.status, 403)

    def test_read_only_rejects_upload_but_allows_listing(self):
        self.server.state.set_read_only(True)
        resp, _ = self.upload("a.txt", b"x")
        self.assertEqual(resp.status, 403)
        resp, body = self.request("GET", "/api/files")
        self.assertEqual(resp.status, 200)
        self.assertTrue(json.loads(body)["read_only"])

    def test_aborted_upload_leaves_no_file_or_temp(self):
        body = b"x" * 1024
        raw = (
            "PUT /api/upload?name=broken.bin HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Cookie: %s\r\n"
            "X-Requested-With: shareFile\r\n"
            "Content-Length: 1048576\r\n\r\n" % self.cookie
        ).encode("ascii")
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(raw + body)
        sock.close()
        time.sleep(0.5)
        self.assertFalse((self.root / "broken.bin").exists())
        temp_dir = self.root / ".sharefile-tmp"
        leftovers = list(temp_dir.glob("*")) if temp_dir.exists() else []
        self.assertEqual(leftovers, [])

    def test_concurrent_same_name_uploads_get_unique_names(self):
        names = []
        errors = []

        def worker(value):
            try:
                resp, body = self.upload("same.txt", bytes([value]) * 4096)
                if resp.status != 201:
                    errors.append(resp.status)
                else:
                    names.append(json.loads(body)["name"])
            except Exception as exc:
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(set(names)), 3)
        self.assertEqual(sorted(p.name for p in self.root.glob("same*")),
                         sorted(["same.txt", "same (1).txt", "same (2).txt"]))

    def test_switch_shared_dir_applies_to_new_uploads(self):
        new_root = self.tmp / "new"
        new_root.mkdir()
        self.server.set_shared_dir(new_root)
        resp, body = self.upload("moved.txt", b"new")
        self.assertEqual(resp.status, 201)
        self.assertTrue((new_root / "moved.txt").exists())
        self.assertFalse((self.root / "moved.txt").exists())

    def test_temp_dir_is_kept_after_successful_upload(self):
        resp, _ = self.upload("one.txt", b"x")
        self.assertEqual(resp.status, 201)
        self.assertTrue((self.root / ".sharefile-tmp").is_dir())

    def test_upload_name_colliding_with_directory_gets_suffix(self):
        (self.root / "photos").mkdir()
        resp, body = self.upload("photos", b"x")
        self.assertEqual(resp.status, 201)
        self.assertEqual(json.loads(body)["name"], "photos (1)")
        self.assertEqual((self.root / "photos (1)").read_bytes(), b"x")

    def test_many_concurrent_uploads_leave_no_temp_files(self):
        errors = []

        def worker(worker_id):
            for index in range(20):
                name = "stress-%d-%d.txt" % (worker_id, index)
                try:
                    resp, body = self.upload(name, b"x" * 1024)
                    if resp.status != 201:
                        errors.append((name, resp.status, body[:80]))
                except Exception as exc:
                    errors.append((name, repr(exc)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(list(self.root.glob("stress-*.txt"))), 160)
        leftovers = list((self.root / ".sharefile-tmp").glob("*.part"))
        self.assertEqual(leftovers, [])

    def test_stalled_upload_times_out_and_cleans_temp(self):
        with mock.patch("share_server.CLIENT_TIMEOUT", 0.2):
            server = ShareServer(self.root, port=0, pin="1234")
            server.start()
            try:
                port = server.port
                cookie = self.login_cookie(port)
                sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                raw = (
                    "PUT /api/upload?name=stalled.bin HTTP/1.1\r\n"
                    "Host: 127.0.0.1\r\n"
                    "Cookie: %s\r\n"
                    "X-Requested-With: shareFile\r\n"
                    "Content-Length: 1048576\r\n\r\n" % cookie
                ).encode("ascii")
                sock.sendall(raw + b"x" * 100)

                temp_dir = self.root / ".sharefile-tmp"
                deadline = time.time() + 2
                while time.time() < deadline and not list(temp_dir.glob("*.part")):
                    time.sleep(0.02)
                self.assertTrue(list(temp_dir.glob("*.part")), "upload did not start")

                time.sleep(0.6)
                self.assertEqual(list(temp_dir.glob("*.part")), [])
                self.assertFalse((self.root / "stalled.bin").exists())
                sock.close()
            finally:
                server.stop()


class UnavailableDirTests(ServerTestCase):
    def test_unavailable_shared_dir_blocks_all_file_operations(self):
        self.login()
        self.server.state.set_usable(False)
        resp, _ = self.request("GET", "/api/files")
        self.assertEqual(resp.status, 503)
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        resp, _ = self.request("GET", "/download?path=a.txt")
        self.assertEqual(resp.status, 503)
        resp, _ = self.request(
            "PUT", "/api/upload?name=a.txt", b"x",
            {"X-Requested-With": "shareFile"},
        )
        self.assertEqual(resp.status, 503)


class WebAssetTests(ServerTestCase):
    def test_index_contains_both_views_and_controls(self):
        resp, body = self.request("GET", "/", auth=False)
        self.assertEqual(resp.status, 200)
        text = body.decode("utf-8")
        for token in ("login-view", "files-view", "pin-input", "upload-input",
                      "file-list", "refresh-btn", "readonly-badge"):
            self.assertIn(token, text)

    def test_static_assets_are_served(self):
        markers = {"/static/app.js": "X-Requested-With", "/static/style.css": "@media"}
        for path, marker in markers.items():
            resp, body = self.request("GET", path, auth=False)
            self.assertEqual(resp.status, 200)
            self.assertIn(marker, body.decode("utf-8"))

    def test_unknown_static_file_is_404(self):
        resp, _ = self.request("GET", "/static/../share_server.py", auth=False)
        self.assertEqual(resp.status, 404)
