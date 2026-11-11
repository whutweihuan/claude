"""shareFile 的纯函数工具：文件名清洗、共享路径解析。

这个模块不导入任何第三方库，也不做 I/O 之外的副作用，方便单元测试。
"""

import os
import re
from pathlib import Path

_INVALID_CHARS = set('<>:"/\\|?*')
_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM%d" % i for i in range(1, 10)}
    | {"LPT%d" % i for i in range(1, 10)}
)
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class ShareError(Exception):
    """shareFile 的可预期错误基类。"""


class UnsafePath(ShareError):
    """请求路径越出共享目录。"""


class RangeNotSatisfiable(ShareError):
    """Range 头非法或超出文件范围。"""

    def __init__(self, size):
        # type: (int) -> None
        super(RangeNotSatisfiable, self).__init__("range not satisfiable")
        self.size = size


def sanitize_filename(name):
    # type: (str) -> str
    """把上传方给的名字压成一个安全的、单层的文件名。

    只保留最后一段；去掉 Windows 非法字符与控制字符；处理保留设备名与超长名。
    返回空名时使用 ``file``。
    """
    if not isinstance(name, str):
        name = str(name)

    name = name.replace("\\", "/").split("/")[-1]
    name = "".join(
        ch for ch in name if ch not in _INVALID_CHARS and ord(ch) >= 32
    )
    name = name.strip().rstrip(". ")

    if not name:
        return "file"

    stem, suffix = os.path.splitext(name)
    if stem.upper() in _RESERVED_NAMES:
        name = "file-" + name
        stem, suffix = os.path.splitext(name)

    if len(name) > 200:
        keep = 200 - len(suffix)
        if keep < 1:
            name = name[:200]
        else:
            name = stem[:keep] + suffix

    return name


def resolve_shared_path(root, rel):
    # type: (Path, str) -> Path
    """把相对路径解析为共享目录内的真实路径。

    拒绝空路径、NUL、绝对路径、盘符路径、任何 ``..`` 段，以及通过符号链接
    逃出共享目录的路径。返回的是 ``resolve`` 后的绝对路径。
    """
    if not isinstance(rel, str):
        raise UnsafePath("path must be text")
    if not rel or "\x00" in rel:
        raise UnsafePath("empty or invalid path")

    normalized = rel.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_RE.match(normalized):
        raise UnsafePath("absolute paths are not allowed")

    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise UnsafePath("parent traversal is not allowed")

    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*parts).resolve(strict=False)

    try:
        common = os.path.commonpath([str(root_resolved), str(candidate)])
    except ValueError:
        raise UnsafePath("path is on a different drive")

    if os.path.normcase(common) != os.path.normcase(str(root_resolved)):
        raise UnsafePath("path escapes the shared directory")

    return candidate


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$", re.IGNORECASE)


def parse_range(header, size):
    # type: (str, int) -> object
    """解析单段 HTTP Range，返回闭区间 ``(start, end)``。

    ``header`` 为 None 时返回 None；非法、多段或越界抛 ``RangeNotSatisfiable``。
    """
    if header is None:
        return None
    if not isinstance(header, str) or size <= 0:
        raise RangeNotSatisfiable(size)

    value = header.strip()
    if "," in value:
        raise RangeNotSatisfiable(size)

    match = _RANGE_RE.match(value)
    if not match:
        raise RangeNotSatisfiable(size)

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise RangeNotSatisfiable(size)

    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            raise RangeNotSatisfiable(size)
        return (max(0, size - suffix), size - 1)

    start = int(start_text)
    if start >= size:
        raise RangeNotSatisfiable(size)

    if end_text:
        end = int(end_text)
        if end < start:
            raise RangeNotSatisfiable(size)
        end = min(end, size - 1)
    else:
        end = size - 1

    return (start, end)


def iter_files(root):
    # type: (Path) -> list
    """递归列出共享目录中的可见文件，返回相对 POSIX 路径的元数据。"""
    root_text = str(root)
    entries = []

    for dirpath, dirnames, filenames in os.walk(root_text, followlinks=False):
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".")
            and not os.path.islink(os.path.join(dirpath, name))
        ]

        for name in filenames:
            if name.startswith(".") or name.startswith("~$"):
                continue

            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue

            try:
                stat = os.stat(full)
            except OSError:
                continue

            rel = os.path.relpath(full, root_text).replace(os.sep, "/")
            try:
                rel.encode("utf-8")
            except UnicodeEncodeError:
                continue

            entries.append(
                {
                    "path": rel,
                    "name": name,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                }
            )

    entries.sort(key=lambda item: item["path"].casefold())
    return entries


def numbered_name(name, index):
    # type: (str, int) -> str
    """给同名文件生成 ``stem (index)suffix``；index 为 0 时返回原名。"""
    if index <= 0:
        return name
    stem, suffix = os.path.splitext(name)
    return "%s (%d)%s" % (stem, index, suffix)


def format_size(size):
    # type: (int) -> str
    """把字节数格式化为人类可读的 B/KB/MB/GB/TB。"""
    size = int(size)
    if size < 1024:
        return "%d B" % size

    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024 or unit == "TB":
            return "%.1f %s" % (value, unit)

    return "%.1f TB" % value
