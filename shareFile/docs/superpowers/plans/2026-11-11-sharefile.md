# 局域网文件共享（shareFile）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `shareFile/` 下做一个电脑端小窗口 + 浏览器网页的局域网文件共享工具，支持 Windows/macOS/Linux 主机与 iOS/Android 浏览器，传文本和视频，速度优先。

**架构：** Tkinter 主窗口在后台线程启动 `ThreadingHTTPServer`；浏览器登录 4 位口令后，通过 JSON API 列目录、流式下载（支持 Range）和流式上传；共享目录、口令、传输事件由线程安全的 `ShareState` 管理。

**技术栈：** Python 3.8+、Tkinter、标准库 `http.server`/`socketserver`/`json`/`socket`；二维码 `segno`（可选依赖）；前端原生 HTML/CSS/JS，无框架。

**规格：** `shareFile/docs/superpowers/specs/2026-11-11-sharefile-design.md`

## 全局约束

- 目标运行时为 Python 3.8.3：不用 `Path.is_relative_to`、`str.removeprefix`、`dict | dict`、`list[str]` 注解等 3.9+ 语法。
- 核心与服务器模块不得 `import segno`；只有 `share_app.py` 可选导入。
- 除 `segno` 外不引入第三方依赖；测试只用 `unittest`。
- 所有面向用户的文字用中文；源文件 UTF-8。
- 文件传输必须流式：读写块 1 MiB，绝不让内存占用随文件大小增长。
- 下载分块发送块 4 MiB；传输进度事件最多每 250 ms 一条。
- 上传同时最多 3 个（前端限制）；同名文件自动编号，绝不覆盖。
- 会话 Cookie 有效期 43200 秒；同一 IP 连续 5 次口令错误锁定 60 秒。
- 端口从配置值开始，依次尝试 +0…+10；`port=0` 用于测试，直接让系统分配。
- Web 目录 `shareFile/web/`，默认共享目录 `shareFile/shared/`，配置 `shareFile/config.json`。
- 路径安全以 `share_core.resolve_shared_path` 为唯一入口；所有下载/上传都必须经过它。
- 提交信息用 `feat(sharefile):` / `test(sharefile):` / `docs(sharefile):` 前缀，结尾带 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## 审查重点（Review Focus）

1. **上传中途断开或取消**：不能留下半截文件、占用目标文件名或残留 `.part`；期望临时文件被清理，目标目录不出现该文件。
2. **危险文件名**：`../../x`、`C:\x`、`/etc/passwd`、Windows 非法字符、`CON`/`LPT1` 保留名、超长名、中文/emoji；期望只能落到共享根层且保存名合法。
3. **Range 边界**：`bytes=末尾-`、`bytes=超长-`、`bytes=-后缀`、零字节文件、多段 Range；期望 206/416 与字节范围精确。
4. **只读目录、端口全占用、没有可用的局域网地址**：期望状态清楚，浏览/下载不被误伤，上传被明确禁用。
5. **并发同名上传与并发下载**：期望不覆盖、不串内容，编号唯一。

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `shareFile/share_core.py` | 纯函数：文件名清洗、共享路径解析、Range 解析、目录遍历、大小与编号格式化 |
| `shareFile/share_server.py` | `ShareState` 会话/口令/共享目录状态，`ShareServer` 绑定端口，HTTP 路由与流式传输 |
| `shareFile/share_app.py` | Tkinter 窗口、配置读写、网卡枚举、二维码、传输记录、启动入口 |
| `shareFile/web/index.html` | 登录视图与文件视图骨架 |
| `shareFile/web/app.js` | 登录、列表、下载链接、并发上传与进度 |
| `shareFile/web/style.css` | 移动优先布局、深色模式、触控目标 |
| `shareFile/test_core.py` | 纯函数单元测试 |
| `shareFile/test_server.py` | 真实 HTTP 服务器的认证、列表、上传、下载、Range、并发测试 |
| `shareFile/test_gui_smoke.py` | 子进程 DPI + GUI 布局与一次上传冒烟测试 |
| `shareFile/requirements.txt` | `segno` |
| `shareFile/run_share.bat` / `run_share.sh` | Windows / macOS、Linux 启动脚本 |
| `shareFile/README.md` | 运行、使用、防火墙与限制说明 |
| `shareFile/.gitignore` | 配置、共享目录内容、缓存、临时文件 |
| `shareFile/shared/.gitkeep` | 保留默认共享目录 |

---

## 任务 1：文件名清洗与共享路径安全

**文件：**
- 创建：`shareFile/share_core.py`
- 创建：`shareFile/test_core.py`

**接口（后续任务使用）：**

```python
class ShareError(Exception): ...
class UnsafePath(ShareError): ...

def sanitize_filename(name: str) -> str
def resolve_shared_path(root: Path, rel: str) -> Path
```

- [ ] **步骤 1：编写失败的测试**

`shareFile/test_core.py`：

```python
import os
import tempfile
import unittest
from pathlib import Path

import share_core as core


class SanitizeFilenameTests(unittest.TestCase):
    def test_keeps_chinese_space_and_emoji(self):
        self.assertEqual(core.sanitize_filename("🎬 视频 片段.mp4"), "🎬 视频 片段.mp4")

    def test_strips_directories(self):
        self.assertEqual(core.sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(core.sanitize_filename(r"C:\temp\a.mp4"), "a.mp4")

    def test_removes_windows_forbidden_chars(self):
        self.assertEqual(core.sanitize_filename('a<b>c:d"e|f?g*h.txt'), "abcdefgh.txt")

    def test_reserved_device_name_gets_prefix(self):
        self.assertEqual(core.sanitize_filename("CON.txt"), "file-CON.txt")
        self.assertEqual(core.sanitize_filename("lpt1"), "file-lpt1")

    def test_empty_or_dots_becomes_file(self):
        self.assertEqual(core.sanitize_filename("   ..."), "file")

    def test_truncates_to_200_chars_keeping_suffix(self):
        result = core.sanitize_filename("a" * 300 + ".txt")
        self.assertLessEqual(len(result), 200)
        self.assertTrue(result.endswith(".txt"))


class ResolveSharedPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.txt").write_text("x", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepts_nested_relative_path(self):
        got = core.resolve_shared_path(self.root, "sub/a.txt")
        self.assertEqual(got, (self.root / "sub" / "a.txt").resolve())

    def test_accepts_backslash_separator(self):
        self.assertEqual(core.resolve_shared_path(self.root, r"sub\a.txt").name, "a.txt")

    def test_rejects_parent_traversal(self):
        with self.assertRaises(core.UnsafePath):
            core.resolve_shared_path(self.root, "../../secret.txt")

    def test_rejects_absolute_and_drive_paths(self):
        for bad in ("/etc/passwd", r"C:\Windows\win.ini", "C:relative"):
            with self.subTest(bad=bad):
                with self.assertRaises(core.UnsafePath):
                    core.resolve_shared_path(self.root, bad)

    def test_rejects_null_byte(self):
        with self.assertRaises(core.UnsafePath):
            core.resolve_shared_path(self.root, "a\x00b")

    @unittest.skipIf(os.name == "nt", "Windows 创建符号链接需要额外权限")
    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, str(self.root / "link"))
            with self.assertRaises(core.UnsafePath):
                core.resolve_shared_path(self.root, "link/secret.txt")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_core -v`  
预期：ERROR/FAIL，提示 `No module named 'share_core'`。

- [ ] **步骤 3：实现 `share_core.py` 的清洗与路径函数**

`sanitize_filename`：把 `\` 当分隔符取最后一段；删除 `<>:"/\|?*` 与 `ord(ch) < 32` 的字符；去掉首尾空白并把结尾的 `.` 去掉；结果为空则用 `file`；若扩展名前的 stem（大写）属于 `CON/PRN/AUX/NUL/COM1-9/LPT1-9`，整体加前缀 `file-`；超过 200 字符时保留后缀、截断 stem。

`resolve_shared_path`：拒绝空串、NUL、以 `/` 或 `\` 开头、匹配 `^[A-Za-z]:` 的输入；把 `\` 规范成 `/`，按 `/` 拆分，丢弃空段与 `.`，任一段为 `..` 则拒绝；用 `root.joinpath(*parts).resolve(strict=False)`，再用 `os.path.commonpath` 与 `os.path.normcase` 比较是否仍在 `root.resolve()` 内，否则抛 `UnsafePath`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd shareFile && python -m unittest test_core -v`  
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/share_core.py shareFile/test_core.py
git commit -m "feat(sharefile): 文件名清洗与共享路径越界防护

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 2：Range 解析、目录列表与命名工具

**文件：**
- 修改：`shareFile/share_core.py`
- 修改：`shareFile/test_core.py`

**接口（后续任务使用）：**

```python
class RangeNotSatisfiable(ShareError):
    size: int

# 返回闭区间 (start, end)；无 Range 头返回 None；非法/不可满足抛异常
def parse_range(header: Optional[str], size: int) -> Optional[Tuple[int, int]]

# 每项：{"path": "sub/a.txt", "name": "a.txt", "size": int, "mtime": int}
def iter_files(root: Path) -> List[Dict[str, object]]

# index=0 返回原名，index>0 返回 "stem (index)suffix"
def numbered_name(name: str, index: int) -> str

def format_size(size: int) -> str
```

- [ ] **步骤 1：编写失败的测试**

追加到 `shareFile/test_core.py`：

```python
class RangeTests(unittest.TestCase):
    def test_no_header_returns_none(self):
        self.assertIsNone(core.parse_range(None, 100))

    def test_closed_range(self):
        self.assertEqual(core.parse_range("bytes=10-19", 100), (10, 19))

    def test_open_ended_and_suffix(self):
        self.assertEqual(core.parse_range("bytes=90-", 100), (90, 99))
        self.assertEqual(core.parse_range("bytes=-10", 100), (90, 99))

    def test_clamps_end_to_size(self):
        self.assertEqual(core.parse_range("bytes=90-200", 100), (90, 99))

    def test_unsatisfiable_or_invalid(self):
        for header in ("bytes=100-", "bytes=200-300", "bytes=5-2", "bytes=0-1,3-4", "items=0-1"):
            with self.subTest(header=header):
                with self.assertRaises(core.RangeNotSatisfiable) as ctx:
                    core.parse_range(header, 100)
                self.assertEqual(ctx.exception.size, 100)

    def test_zero_size_file_has_no_valid_range(self):
        with self.assertRaises(core.RangeNotSatisfiable):
            core.parse_range("bytes=0-", 0)


class ListFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sub").mkdir()
        (self.root / "a.txt").write_text("abc", encoding="utf-8")
        (self.root / "sub" / "b.mp4").write_bytes(b"x" * 10)
        (self.root / ".hidden").write_text("no", encoding="utf-8")
        (self.root / "~$temp.docx").write_text("no", encoding="utf-8")
        (self.root / ".sharefile-tmp").mkdir()
        (self.root / ".sharefile-tmp" / "upload-1.part").write_bytes(b"x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_relative_posix_paths_and_metadata(self):
        files = core.iter_files(self.root)
        self.assertEqual([f["path"] for f in files], ["a.txt", "sub/b.mp4"])
        self.assertEqual(files[0]["size"], 3)
        self.assertEqual(files[0]["name"], "a.txt")
        self.assertIsInstance(files[0]["mtime"], int)

    def test_sorted_case_insensitively(self):
        (self.root / "B.txt").write_text("b", encoding="utf-8")
        paths = [f["path"] for f in core.iter_files(self.root)]
        self.assertEqual(paths, ["a.txt", "B.txt", "sub/b.mp4"])


class NameAndSizeTests(unittest.TestCase):
    def test_numbered_name(self):
        self.assertEqual(core.numbered_name("a.txt", 0), "a.txt")
        self.assertEqual(core.numbered_name("a.txt", 1), "a (1).txt")
        self.assertEqual(core.numbered_name("archive.tar.gz", 2), "archive.tar (2).gz")

    def test_format_size(self):
        self.assertEqual(core.format_size(0), "0 B")
        self.assertEqual(core.format_size(1536), "1.5 KB")
        self.assertEqual(core.format_size(5 * 1024 * 1024), "5.0 MB")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_core -v`  
预期：新增用例 FAIL，提示 `parse_range` / `iter_files` 等不存在。

- [ ] **步骤 3：实现四个函数**

- `parse_range`：`header is None` 返回 `None`；必须匹配 `^bytes=`（不区分大小写）；含 `,` 视为非法；解析 `start-end` / `start-` / `-suffix`；`size <= 0`、`start >= size`、`start > end`、`suffix <= 0` 抛 `RangeNotSatisfiable(size)`；`end` 超过 `size-1` 时截断。
- `iter_files`：`os.walk(root, followlinks=False)`；跳过以 `.` 开头的目录/文件、以 `~$` 开头的文件、`.sharefile-tmp`、符号链接；文件名不能编码为 UTF-8 时跳过；返回 `path` 用 `/` 连接；按 `path.casefold()` 排序。
- `numbered_name`：`os.path.splitext` 拆 stem/suffix，`index=0` 原名，否则 `f"{stem} ({index}){suffix}"`。
- `format_size`：B/KB/MB/GB，KB 以上保留 1 位小数。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd shareFile && python -m unittest test_core -v`  
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/share_core.py shareFile/test_core.py
git commit -m "feat(sharefile): Range 解析、目录列表与命名工具

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 3：服务器骨架、口令认证与文件列表 API

**文件：**
- 创建：`shareFile/share_server.py`
- 创建：`shareFile/test_server.py`

**接口（后续任务使用）：**

```python
class RateLimited(Exception):
    retry_after: int

class ShareState:
    def __init__(self, shared_dir: Path, pin: Optional[str] = None,
                 events: Optional[queue.Queue] = None, read_only: bool = False)
    shared_dir: Path            # property，读时加锁
    pin: str                    # property
    def set_shared_dir(self, path: Path) -> None
    def set_read_only(self, read_only: bool) -> None
    def regenerate_pin(self) -> str
    def login(self, pin: str, client_ip: str) -> str     # 成功返回 token；错误返回 None；锁定抛 RateLimited
    def is_authed(self, token: Optional[str]) -> bool
    def logout(self, token: str) -> None
    def revoke_sessions(self) -> None
    def can_write(self) -> bool
    def emit(self, **event) -> None
    def list_files(self) -> List[Dict[str, object]]
    def invalidate_listing(self) -> None

class ShareServer:
    def __init__(self, shared_dir: Path, port: int = 8000, pin: Optional[str] = None,
                 host: str = "0.0.0.0", events: Optional[queue.Queue] = None,
                 read_only: bool = False)
    def start(self) -> int      # 返回实际端口
    def stop(self) -> None
    def set_shared_dir(self, path: Path) -> None
    def regenerate_pin(self) -> str
    state: ShareState
    port: int
    pin: str
```

- [ ] **步骤 1：编写失败的测试**

`shareFile/test_server.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_server -v`  
预期：ERROR，提示 `No module named 'share_server'`。

- [ ] **步骤 3：实现服务器骨架与认证**

要点：

- `ShareState` 用 `threading.Lock` 保护：`_shared_dir`、`_pin`、`_sessions`、`_failures`、`_read_only`、列表缓存（时间戳 1 秒）。
- `login`：若该 IP 在锁定中抛 `RateLimited(ceil(剩余秒))`；口令错误累计，达到 5 次设 `locked_until = time.time() + 60`；成功则清空该 IP 记录并 `secrets.token_hex(32)` 生成 token。
- `emit`：`queue.Queue(maxsize=1000)`，满时丢弃，不阻塞。
- `ShareServer.start`：在 `port..port+10` 中依次尝试绑定（`port=0` 只绑定一次 0）；创建 `ShareHTTPServer(ThreadingHTTPServer)`，`daemon_threads = True`，后台 `daemon=True` 线程跑 `serve_forever`。
  - `allow_reuse_address` 在 Windows 上设为 `False`（Windows 的 `SO_REUSEADDR` 会允许绑定已占用端口，导致端口回退失效），其他平台为 `True`。
- `ShareRequestHandler`：`log_message` 置空；`protocol_version = "HTTP/1.1"`（响应必须正确设置 `Content-Length`）；每个连接设置 `TCP_NODELAY`，失败忽略。
- 路由：`GET /api/session`、`POST /api/login`、`POST /api/logout`、`GET /api/files`；其余 404。`logout` 只从会话集合移除当前 token，并回写一个过期的 `sf_session` Cookie。
- Cookie：`sf_session=<token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=43200`。
- 所有响应加 `X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`Cache-Control: no-store`；HTML 另加 `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'`。
- `POST /api/login` 与 `/api/logout` 要求 `X-Requested-With: shareFile`，否则 403；JSON 体上限 4 KiB。
- `GET /api/files` 返回 `{"files": [...], "read_only": bool}`，使用 `core.iter_files`。
- 401 响应 `{"error": "unauthorized"}`；429 响应 `{"error": "too_many_attempts", "retry": N}`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd shareFile && python -m unittest test_server -v`  
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/share_server.py shareFile/test_server.py
git commit -m "feat(sharefile): HTTP 服务骨架与口令会话认证

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 4：流式下载与 Range

**文件：**
- 修改：`shareFile/share_server.py`
- 修改：`shareFile/test_server.py`

**接口：**
- `GET /download?path=<相对路径>`，认证必需。
- 200：完整文件；206：单段 Range；416：非法/不可满足。
- 响应头：`Accept-Ranges: bytes`、`Content-Disposition: attachment; filename*=UTF-8''...`、`Content-Length`、`X-Content-Type-Options: nosniff`。
- 支持 `HEAD`，只回头不回体。

- [ ] **步骤 1：编写失败的测试**

追加到 `shareFile/test_server.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_server.DownloadTests -v`  
预期：404，断言失败（下载路由尚未实现）。

- [ ] **步骤 3：实现下载路由**

- 从查询串取 `path`，缺失返回 400；`core.resolve_shared_path` 抛 `UnsafePath` 返回 400。
- 目标不是普通文件返回 404；`stat().st_size` 作为总长度。
- `core.parse_range`：`None` → 200 全文件；`(start, end)` → 206，`Content-Range: bytes {start}-{end}/{size}`；抛 `RangeNotSatisfiable` → 416，`Content-Range: bytes */{size}`，`Content-Length: 0`。
- `Content-Type: application/octet-stream`；文件名用 `urllib.parse.quote(name, safe="")` 生成 `filename*=UTF-8''...`，同时给 ASCII 回退 `filename="download"`。
- 发送：以 4 MiB 为一块循环调用 `self.connection.sendfile(f, offset, count)`；只有在**尚未发出任何字节**时捕获 `AttributeError`/`OSError`/`NotImplementedError` 才退回 `seek` + `read` + `self.wfile.write`；已发出部分字节后再失败则直接中断，避免重复发送。每次发送后 `done += n`，距上次事件超过 0.25 秒发一条 `kind="download"` 的进度事件；结束发 `phase="done"`；`BrokenPipeError`/`ConnectionResetError` 静默结束并发 `phase="error"`。
- `HEAD`：只写头，不写体。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd shareFile && python -m unittest test_server.DownloadTests -v`  
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/share_server.py shareFile/test_server.py
git commit -m "feat(sharefile): 流式下载与 Range 支持

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 5：流式上传、原子落盘与并发命名

**文件：**
- 修改：`shareFile/share_server.py`
- 修改：`shareFile/test_server.py`

**接口：**
- `PUT /api/upload?name=<文件名>`，认证 + `X-Requested-With: shareFile` 必需。
- 请求体为原始文件内容，必须带 `Content-Length`；成功 `201 {"name": 实际名, "size": N}`。
- 失败：411 无长度、400 空体、403 只读/缺 CSRF、507 磁盘空间不足、500 其他写入错误。

- [ ] **步骤 1：编写失败的测试**

追加到 `shareFile/test_server.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_server.UploadTests -v`  
预期：404 或断言失败。

- [ ] **步骤 3：实现上传路由**

- 认证、CSRF、`Content-Length`（缺失 411、非正整数 400）、`state.can_write()`（否则 403）检查顺序固定。
- `request_root = state.shared_dir`（开头快照；运行中换目录只影响后续请求）。
- `name = core.sanitize_filename(query name)`；临时目录 `request_root/".sharefile-tmp"`，文件名 `upload-<token>.part`。
- 循环 `remaining = length`，每次 `read(min(1 MiB, remaining))`；`b""` 提前结束则清理并 400；`OSError` 清理并按 `errno.ENOSPC` 返回 507，其他 500。
- 落盘：`for i in range(10000)` 用 `core.numbered_name(name, i)` 得到候选，`os.open(candidate, O_CREAT|O_EXCL|O_WRONLY)` 占位；成功后关闭、`os.replace(temp, candidate)`；`FileExistsError` 继续下一个。
- 成功后 `state.invalidate_listing()`，发 `start`/`done` 事件，返回 201 与实际保存名。
- 每 250 ms 发一条 `phase="progress"` 事件（`done`、`total`、`speed`=字节/秒）。
- 任何异常路径都确保关闭并删除临时文件；响应后清理空临时目录（忽略错误）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd shareFile && python -m unittest test_server -v`  
预期：全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/share_server.py shareFile/test_server.py
git commit -m "feat(sharefile): 流式上传、原子落盘与并发命名

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 6：Tkinter 主窗口、二维码与传输记录

**文件：**
- 创建：`shareFile/share_app.py`
- 创建：`shareFile/test_gui_smoke.py`
- 创建：`shareFile/requirements.txt`

**接口（测试与运行入口使用）：**

```python
def enable_dpi_awareness() -> None
def load_config(path: Path, default_dir: Path) -> Dict[str, object]
def save_config(path: Path, shared_dir: Path, port: int) -> None
def choose_addresses(candidates: List[str]) -> List[str]  # 过滤回环/链路本地、去重、私有网段优先、空则 ["127.0.0.1"]
def get_lan_addresses() -> List[str]      # 采集候选地址后交给 choose_addresses
def is_writable(path: Path) -> bool       # 封装 os.access(path, os.W_OK)

class ShareApp(tk.Tk):
    def __init__(self, config_path: Path, shared_dir: Optional[Path] = None,
                 port: Optional[int] = None)
    # 供测试读取：
    path_label, address_combo, pin_label, qr_canvas, transfer_tree, status_label
    path_var, address_var, pin_var, status_var
    server: ShareServer
    def close(self) -> None

def main() -> None
```

- [ ] **步骤 1：编写失败的测试**

`shareFile/test_gui_smoke.py`：

```python
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
```

同文件底部加入探针入口：

```python
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
```

`shareFile/requirements.txt`：

```
segno>=1.5,<2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_gui_smoke -v`  
预期：ERROR，提示 `No module named 'share_app'`。

- [ ] **步骤 3：实现配置、地址与 DPI 辅助函数**

- `enable_dpi_awareness`：Windows 下先 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`，失败再 `ctypes.windll.user32.SetProcessDPIAware()`，全部 try/except。
- `load_config`：文件不存在/JSON 损坏/字段缺失 → 返回 `{"shared_dir": str(default_dir.resolve()), "port": 8000}`；`shared_dir` 为相对路径时相对配置目录解析。
- `save_config`：写 `<path>.tmp` 后 `os.replace`。
- `choose_addresses`：过滤空串、`127.*`、`169.254.*`，去重并保持稳定顺序；私有网段（`10.*`、`192.168.*`、`172.16–31.*`）排前面，其余公网地址排后面；结果为空返回 `["127.0.0.1"]`。
- `get_lan_addresses`：UDP socket 连接 `8.8.8.8:80` 取本机地址（不实际发包），再合并 `getaddrinfo(gethostname())`，交给 `choose_addresses`。
- `is_writable`：`os.access(str(path), os.W_OK)`。

运行：`cd shareFile && python -m unittest test_gui_smoke.ConfigTests -v`  
预期：3 个测试 PASS。

- [ ] **步骤 4：实现主窗口、二维码与事件轮询**

- `ShareApp.__init__`：
  - 读配置（显式参数优先）；确保共享目录存在；`is_writable(shared)` 决定只读。
  - 创建 `queue.Queue()`、`ShareServer(...)`；`start()` 失败不让 Tk 崩溃：状态栏红字，`self.server = None`。
  - 布局（自然宽度、`grid`/`pack` 权重）：共享目录行（`path_label` 截断到 40 字符 + 选择/打开按钮）、地址 `ttk.Combobox(readonly)` + 复制、`qr_canvas`（220×220）、口令 `pin_label` + 换口令、`ttk.Treeview` 五列、`status_label`。
  - 创建后 `update_idletasks()`，`w=max(560, reqwidth)`、`h=max(760, reqheight)`，`geometry` 与 `minsize(w, h)`。
  - `after(200, self.poll_events)`。
- `draw_qr(url)`：`try: import segno`；`qr = segno.make(url, error="m")`，取 `qr.matrix`，清空画布，白色背景，按 4 模块静区计算 `scale = max(1, 220 // (size + 8))`，把每行连续黑模块合并成一个 `create_rectangle`。`ImportError` 时画一段中文提示文字与 `pip install segno`。
- 事件轮询：按 `(kind, name)` 维护 `Treeview` iid；`phase="start"` 插入一行，进度更新进度列与速度列（`format_size` + `/s`），`done` 置 100%，`error` 标红；超过 100 条删除最旧。
- 按钮：选择目录（`filedialog.askdirectory` → `state.set_shared_dir` → 保存配置 → 刷新标签与只读状态）；打开目录（Windows `os.startfile`，macOS `open`，Linux `xdg-open`）；复制地址（剪贴板）；换口令（`state.regenerate_pin()`）。
- 只读时状态栏显示“只读”，并禁用上传相关提示（主机端无上传按钮，网页通过 API 的 `read_only` 感知）。
- `close()`：若 `server` 非空则 `server.stop()`，然后 `destroy()`；`protocol("WM_DELETE_WINDOW", self.close)`。
- `main()`：`enable_dpi_awareness()` → 配置路径取脚本同目录 `config.json` → 创建窗口 → `mainloop()`；启动异常用 `messagebox.showerror`。

- [ ] **步骤 5：运行测试验证通过**

先安装依赖（仅本机一次性）：

```bash
python -m pip install -r shareFile/requirements.txt
```

运行：`cd shareFile && python -m unittest test_gui_smoke -v`  
预期：全部 PASS，探针 JSON 中 `pin` 为 4 位数字、`transfer_rows >= 1`、`file_saved` 为 true。

- [ ] **步骤 6：Commit**

```bash
git add shareFile/share_app.py shareFile/test_gui_smoke.py shareFile/requirements.txt
git commit -m "feat(sharefile): Tkinter 主窗口、二维码与传输记录

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 7：浏览器端登录、列表与上传

**文件：**
- 创建：`shareFile/web/index.html`
- 创建：`shareFile/web/app.js`
- 创建：`shareFile/web/style.css`
- 修改：`shareFile/share_server.py`
- 修改：`shareFile/test_server.py`

**接口：**
- `GET /` 返回 `web/index.html`；`GET /static/app.js`、`GET /static/style.css` 返回对应资源（白名单，只有这两个文件名）。
- HTML 必须包含 id：`login-view`、`login-form`、`pin-input`、`login-error`、`files-view`、`file-list`、`refresh-btn`、`upload-input`、`drop-zone`、`upload-queue`、`readonly-badge`、`empty-state`。
- 前端请求头统一带 `X-Requested-With: shareFile`（上传、登录、退出）。

- [ ] **步骤 1：编写失败的测试**

追加到 `shareFile/test_server.py`：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd shareFile && python -m unittest test_server.WebAssetTests -v`  
预期：404，断言失败。

- [ ] **步骤 3：实现网页与静态路由**

服务器：启动时读取 `web/index.html`、`web/app.js`、`web/style.css` 到内存；`GET /` 返回 HTML（UTF-8，`Content-Type: text/html; charset=utf-8`，带 CSP）；`GET /static/<name>` 只接受 `app.js`、`style.css`，否则 404；JS/CSS 带 `Cache-Control: max-age=3600`。

`index.html` 结构：

```html
<main id="login-view">
  <form id="login-form">
    <input id="pin-input" inputmode="numeric" maxlength="4" autocomplete="off">
    <button>进入</button>
    <p id="login-error" role="alert"></p>
  </form>
</main>
<main id="files-view" hidden>
  <header>
    <span id="folder-name">共享文件</span>
    <button id="refresh-btn">刷新</button>
    <label>上传<input id="upload-input" type="file" multiple></label>
    <span id="readonly-badge" hidden>只读</span>
  </header>
  <div id="drop-zone">把文件拖到这里</div>
  <ul id="file-list"></ul>
  <p id="empty-state" hidden>共享文件夹还是空的，点上传或把文件拖进来。</p>
  <ul id="upload-queue"></ul>
</main>
```

`app.js` 要点：

- 启动先 `GET /api/session`，`authed` 决定显示哪个视图。
- 登录 `POST /api/login`，`401` 显示“口令错误”，`429` 显示需等待秒数；成功显示文件视图并加载列表。
- `loadFiles()`：`GET /api/files`，按 `path` 用 `textContent` 渲染行；下载链接 `/download?path=` + `encodeURIComponent(path)`；`read_only` 时禁用上传输入并显示徽章。
- 上传：文件队列 + 最多 3 个并发；每个文件用 `XMLHttpRequest` `PUT /api/upload?name=<encodeURIComponent(name)>`，直接 `send(file)`；`upload.onprogress` 更新进度与速度；取消调用 `abort()`；完成后刷新列表。
- 拖拽区 `dragover`/`drop` 调 `uploadFiles(event.dataTransfer.files)`。
- 页面可见且无上传时，每 10 秒 `loadFiles()`；上传期间暂停。
- 所有网络错误在 `#upload-queue` 中就地显示，不弹 `alert`。

`style.css` 要点：移动优先，列表行在窄屏可换行；按钮/输入触控高度 ≥ 44px；`@media (prefers-color-scheme: dark)` 提供深色配色；`#drop-zone` 虚线边框，拖拽悬停高亮。

- [ ] **步骤 4：运行测试验证通过**

```bash
cd shareFile
node --check web/app.js
python -m unittest test_server.WebAssetTests -v
```

预期：Node 无输出、退出码 0；三个测试 PASS。

- [ ] **步骤 5：Commit**

```bash
git add shareFile/web shareFile/share_server.py shareFile/test_server.py
git commit -m "feat(sharefile): 浏览器登录、文件列表与并发上传

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 8：启动脚本、README、忽略规则与全量验收

**文件：**
- 创建：`shareFile/run_share.bat`
- 创建：`shareFile/run_share.sh`
- 创建：`shareFile/README.md`
- 创建：`shareFile/.gitignore`
- 创建：`shareFile/shared/.gitkeep`

- [ ] **步骤 1：写启动脚本**

`run_share.bat`：

```bat
@echo off
cd /d "%~dp0"
python share_app.py
if errorlevel 1 pause
```

`run_share.sh`：

```sh
#!/bin/sh
cd "$(dirname "$0")"
exec python3 share_app.py
```

- [ ] **步骤 2：写 `.gitignore`**

```gitignore
config.json
shared/*
!shared/.gitkeep
__pycache__/
*.pyc
.sharefile-tmp/
```

- [ ] **步骤 3：写 README**

必须包含：一句话介绍；Windows / macOS / Linux 运行步骤（含 `pip install -r requirements.txt`，Linux 缺 Tkinter 时 `python3-tk`）；手机使用步骤（扫码 → 4 位口令 → 下载/上传）；速度预期（千兆有线约 110 MB/s，Wi-Fi 取决于环境）；Windows 防火墙提示；限制（仅可信局域网、4 位口令不是公网安全方案、网页端不能删除、访客 Wi-Fi 客户端隔离会导致无法访问）；测试命令。

- [ ] **步骤 4：跑全量测试**

```bash
cd shareFile
python -m unittest -v
node --check web/app.js
```

预期：全部 PASS，Node 退出码 0。

- [ ] **步骤 5：手动验收**

```bash
cd shareFile
python share_app.py
```

逐项确认规格第 16 节：

1. 窗口显示地址、二维码、4 位口令、运行状态。
2. 本机浏览器打开地址 → 输错口令有提示 → 正确口令进入。
3. 上传一个 ≥ 100 MB 的视频，网页进度与主机传输记录同时更新，文件大小一致。
4. 下载该视频，支持暂停后用 `Range` 继续（可用 `curl -r` 验证）。
5. 手机（同 Wi-Fi）扫码完成一次上传和一次下载。
6. 把共享目录改到一个只读目录：列表与下载可用，上传被禁用并显示“只读”。
7. 传输 1 GB 文件期间观察任务管理器内存不随文件增长，窗口可拖动。

- [ ] **步骤 6：Commit**

```bash
git add shareFile/run_share.bat shareFile/run_share.sh shareFile/README.md shareFile/.gitignore shareFile/shared/.gitkeep
git commit -m "docs(sharefile): 启动脚本、使用说明与忽略规则

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```
