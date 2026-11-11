"""shareFile 的 HTTP 服务：口令会话、文件列表、上传与下载。"""

import json
import math
import os
import queue
import secrets
import socket
import threading
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import share_core as core

SESSION_COOKIE = "sf_session"
SESSION_MAX_AGE = 43200
MAX_JSON_BODY = 4096
MAX_LOGIN_FAILURES = 5
LOCKOUT_SECONDS = 60
LISTING_CACHE_SECONDS = 1.0
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "shareFile"
DOWNLOAD_BLOCK = 4 * 1024 * 1024
PROGRESS_INTERVAL = 0.25


class RateLimited(Exception):
    """同一 IP 的错误口令次数过多，暂时锁定。"""

    def __init__(self, retry_after):
        super(RateLimited, self).__init__("too many attempts")
        self.retry_after = retry_after


def generate_pin():
    return "%04d" % secrets.randbelow(10000)


class ShareState(object):
    """线程安全的共享状态：目录、口令、会话、限流与传输事件。"""

    def __init__(self, shared_dir, pin=None, events=None, read_only=False):
        self._lock = threading.RLock()
        self._shared_dir = Path(shared_dir).resolve()
        self._pin = pin if pin is not None else generate_pin()
        self._sessions = set()
        self._failures = {}
        self._read_only = bool(read_only)
        self.events = events if events is not None else queue.Queue(maxsize=1000)
        self._listing_cache = None
        self._listing_root = None
        self._listing_at = 0.0

    @property
    def shared_dir(self):
        with self._lock:
            return self._shared_dir

    @property
    def pin(self):
        with self._lock:
            return self._pin

    def set_shared_dir(self, path):
        with self._lock:
            self._shared_dir = Path(path).resolve()
            self._listing_cache = None
            self._listing_root = None

    def set_read_only(self, read_only):
        with self._lock:
            self._read_only = bool(read_only)

    def regenerate_pin(self):
        with self._lock:
            self._pin = generate_pin()
            self._sessions.clear()
            self._failures.clear()
            return self._pin

    def login(self, pin, client_ip):
        now = time.time()
        with self._lock:
            count, locked_until = self._failures.get(client_ip, (0, 0.0))
            if locked_until > now:
                raise RateLimited(int(math.ceil(locked_until - now)))

            if not isinstance(pin, str) or not secrets.compare_digest(pin, self._pin):
                count += 1
                if count >= MAX_LOGIN_FAILURES:
                    self._failures[client_ip] = (0, now + LOCKOUT_SECONDS)
                else:
                    self._failures[client_ip] = (count, 0.0)
                return None

            self._failures.pop(client_ip, None)
            token = secrets.token_hex(32)
            self._sessions.add(token)
            return token

    def is_authed(self, token):
        if not token:
            return False
        with self._lock:
            return token in self._sessions

    def logout(self, token):
        with self._lock:
            self._sessions.discard(token)

    def revoke_sessions(self):
        with self._lock:
            self._sessions.clear()

    def can_write(self):
        with self._lock:
            return not self._read_only

    def emit(self, **event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            pass

    def list_files(self):
        now = time.time()
        with self._lock:
            root = self._shared_dir
            if (
                self._listing_cache is not None
                and self._listing_root == root
                and now - self._listing_at < LISTING_CACHE_SECONDS
            ):
                return list(self._listing_cache)

        files = core.iter_files(root)

        with self._lock:
            self._listing_cache = list(files)
            self._listing_root = root
            self._listing_at = time.time()
        return files

    def invalidate_listing(self):
        with self._lock:
            self._listing_cache = None
            self._listing_root = None


class ShareHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows 的 SO_REUSEADDR 会允许绑定已占用端口，导致端口回退失效。
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, handler, state):
        self.state = state
        super(ShareHTTPServer, self).__init__(address, handler)


class ShareServer(object):
    """把 HTTP 服务包装成可启动、可停止、可换目录的对象。"""

    def __init__(self, shared_dir, port=8000, pin=None, host="0.0.0.0",
                 events=None, read_only=False):
        self._state = ShareState(shared_dir, pin=pin, events=events, read_only=read_only)
        self._host = host
        self._requested_port = int(port)
        self._httpd = None
        self._thread = None
        self._port = None

    @property
    def state(self):
        return self._state

    @property
    def port(self):
        return self._port

    @property
    def pin(self):
        return self._state.pin

    def set_shared_dir(self, path):
        self._state.set_shared_dir(path)

    def regenerate_pin(self):
        return self._state.regenerate_pin()

    def start(self):
        if self._httpd is not None:
            return self._port

        if self._requested_port == 0:
            candidates = [0]
        else:
            candidates = [
                self._requested_port + offset
                for offset in range(11)
                if self._requested_port + offset <= 65535
            ]

        last_error = None
        for port in candidates:
            try:
                httpd = ShareHTTPServer((self._host, port), ShareRequestHandler, self._state)
            except OSError as exc:
                last_error = exc
                continue

            self._httpd = httpd
            self._port = httpd.server_address[1]
            self._thread = threading.Thread(
                target=httpd.serve_forever, name="sharefile-http", daemon=True
            )
            self._thread.start()
            return self._port

        if last_error is not None:
            raise last_error
        raise OSError("no available port")

    def stop(self):
        httpd = self._httpd
        if httpd is None:
            return
        self._httpd = None
        try:
            httpd.shutdown()
        finally:
            httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._port = None


class ShareRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "shareFile"
    sys_version = ""
    wbufsize = 0

    @property
    def state(self):
        return self.server.state

    def setup(self):
        BaseHTTPRequestHandler.setup(self)
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def log_message(self, format, *args):
        return

    # ---- 响应工具 ----

    def _send(self, status, body, content_type, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", extra_headers)

    def _reject(self, status, payload):
        self.close_connection = True
        self._json(status, payload)

    def _cookie_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:
            return None
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _authed(self):
        return self.state.is_authed(self._cookie_token())

    def _require_auth(self):
        if self._authed():
            return True
        self._json(401, {"error": "unauthorized"})
        return False

    def _read_json(self):
        length_text = self.headers.get("Content-Length")
        try:
            length = int(length_text)
        except (TypeError, ValueError):
            return None
        if length < 0 or length > MAX_JSON_BODY:
            return None
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    # ---- 路由 ----

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/session":
            self._handle_session()
        elif path == "/api/files":
            self._handle_files()
        elif path == "/download":
            self._handle_download(head_only=False)
        else:
            self._json(404, {"error": "not_found"})

    def do_HEAD(self):
        if urlparse(self.path).path == "/download":
            self._handle_download(head_only=True)
        else:
            self._send(404, b"", "application/json; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            self._handle_login()
        elif path == "/api/logout":
            self._handle_logout()
        else:
            self._json(404, {"error": "not_found"})

    def do_PUT(self):
        self.close_connection = True
        self._json(404, {"error": "not_found"})

    # ---- API ----

    def _handle_session(self):
        self._json(200, {"authed": self._authed()})

    def _handle_login(self):
        if self.headers.get(CSRF_HEADER) != CSRF_VALUE:
            self._reject(403, {"error": "forbidden"})
            return

        payload = self._read_json()
        if not isinstance(payload, dict) or not isinstance(payload.get("pin"), str):
            self._json(400, {"error": "bad_request"})
            return

        try:
            token = self.state.login(payload["pin"], self.client_address[0])
        except RateLimited as exc:
            self._json(
                429,
                {"error": "too_many_attempts", "retry": max(1, int(exc.retry_after))},
            )
            return

        if token is None:
            self._json(401, {"error": "wrong_pin"})
            return

        cookie = "%s=%s; HttpOnly; SameSite=Lax; Path=/; Max-Age=%d" % (
            SESSION_COOKIE, token, SESSION_MAX_AGE,
        )
        self._json(200, {"ok": True}, [("Set-Cookie", cookie)])

    def _handle_logout(self):
        if self.headers.get(CSRF_HEADER) != CSRF_VALUE:
            self._reject(403, {"error": "forbidden"})
            return

        token = self._cookie_token()
        if token:
            self.state.logout(token)

        expired = "%s=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0" % SESSION_COOKIE
        self._json(200, {"ok": True}, [("Set-Cookie", expired)])

    def _handle_files(self):
        if not self._require_auth():
            return
        self._json(
            200,
            {"files": self.state.list_files(), "read_only": not self.state.can_write()},
        )

    def _handle_download(self, head_only):
        if not self._require_auth():
            return

        query = parse_qs(urlparse(self.path).query)
        rel = (query.get("path") or [""])[0]
        if not rel:
            self._json(400, {"error": "missing_path"})
            return

        try:
            target = core.resolve_shared_path(self.state.shared_dir, rel)
        except core.UnsafePath:
            self._reject(400, {"error": "unsafe_path"})
            return

        if not target.is_file():
            self._json(404, {"error": "not_found"})
            return

        try:
            size = target.stat().st_size
        except OSError:
            self._json(404, {"error": "not_found"})
            return

        try:
            parsed_range = core.parse_range(self.headers.get("Range"), size)
        except core.RangeNotSatisfiable:
            self._send(
                416,
                b"",
                "application/json; charset=utf-8",
                [
                    ("Accept-Ranges", "bytes"),
                    ("Content-Range", "bytes */%d" % size),
                ],
            )
            return

        if parsed_range is None:
            start, end = 0, size - 1
            status = 200
            extra = []
        else:
            start, end = parsed_range
            status = 206
            extra = [("Content-Range", "bytes %d-%d/%d" % (start, end, size))]

        length = max(0, end - start + 1)
        disposition = "attachment; filename=\"download\"; filename*=UTF-8''%s" % quote(
            target.name, safe=""
        )

        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", disposition)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for key, value in extra:
            self.send_header(key, value)
        self.end_headers()

        if head_only or length <= 0:
            return

        name = target.name
        self.state.emit(kind="download", phase="start", name=name, size=length)
        sent = 0
        started = time.time()
        last_emit = started
        sendfile_ok = hasattr(self.connection, "sendfile")

        try:
            with open(str(target), "rb") as handle:
                while sent < length:
                    chunk = min(DOWNLOAD_BLOCK, length - sent)
                    offset = start + sent

                    if sendfile_ok:
                        try:
                            self.connection.sendfile(handle, offset, chunk)
                        except (AttributeError, NotImplementedError):
                            if sent:
                                raise
                            sendfile_ok = False
                        except OSError:
                            if sent:
                                raise
                            sendfile_ok = False

                    if not sendfile_ok:
                        handle.seek(offset)
                        data = handle.read(chunk)
                        if not data:
                            break
                        self.wfile.write(data)

                    sent += chunk
                    now = time.time()
                    if now - last_emit >= PROGRESS_INTERVAL:
                        self.state.emit(
                            kind="download",
                            phase="progress",
                            name=name,
                            done=sent,
                            total=length,
                            speed=sent / max(now - started, 1e-6),
                        )
                        last_emit = now
        except (BrokenPipeError, ConnectionResetError):
            self.state.emit(kind="download", phase="error", name=name)
            self.close_connection = True
            return
        except OSError:
            self.state.emit(kind="download", phase="error", name=name)
            self.close_connection = True
            return

        self.state.emit(
            kind="download", phase="done", name=name, done=length, size=length
        )
