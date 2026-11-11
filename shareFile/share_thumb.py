"""图片缩略图生成与内存缓存。

Pillow 是可选依赖：没有安装时 ``IMAGE_AVAILABLE`` 为 False，
``get_thumbnail`` 返回 None，网页会退回成占位图标，不影响上传下载。
"""

import io
import os
import threading
from collections import OrderedDict

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

THUMBNAIL_MAX_SIDE = 320
JPEG_QUALITY = 80
CACHE_MAX_ENTRIES = 256

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")

IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

_MISSING = object()


class ThumbnailCache(object):
    """按文件版本缓存缩略图；用 None 记住失败结果，避免反复解码坏图。"""

    def __init__(self, max_entries=CACHE_MAX_ENTRIES):
        self._lock = threading.Lock()
        self._entries = OrderedDict()
        self._max_entries = max(1, int(max_entries))

    def lookup(self, key):
        with self._lock:
            if key not in self._entries:
                return _MISSING
            value = self._entries[key]
            self._entries.move_to_end(key)
            return value

    def store(self, key, value):
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self):
        with self._lock:
            return len(self._entries)


_cache = ThumbnailCache()


def is_image_name(name):
    """按扩展名判断是否能生成缩略图。"""
    return os.path.splitext(str(name))[1].lower() in IMAGE_EXTENSIONS


def image_content_type(name):
    return IMAGE_CONTENT_TYPES.get(os.path.splitext(str(name))[1].lower())


def clear_cache():
    _cache.clear()


def get_thumbnail(path, stat=None):
    """返回 JPEG 缩略图字节；没有 Pillow、文件读不到或不是图片时返回 None。"""
    if Image is None:
        return None

    try:
        st = stat or os.stat(str(path))
    except OSError:
        return None

    key = (
        os.path.normcase(os.path.abspath(str(path))),
        getattr(st, "st_mtime_ns", int(st.st_mtime * 1000000000)),
        st.st_size,
    )
    cached = _cache.lookup(key)
    if cached is not _MISSING:
        return cached

    try:
        data = _render(path)
    except Exception:
        data = None
    _cache.store(key, data)
    return data


def _render(path):
    with Image.open(str(path)) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source)
        image.thumbnail((THUMBNAIL_MAX_SIDE, THUMBNAIL_MAX_SIDE), Image.LANCZOS)

        if image.mode == "P" and "transparency" in image.info:
            image = image.convert("RGBA")
        if image.mode in ("RGBA", "LA"):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
        else:
            image = image.convert("RGB")

        output = io.BytesIO()
        image.save(output, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return output.getvalue()
