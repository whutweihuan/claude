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
