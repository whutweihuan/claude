#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片压缩工具核心逻辑与命令行入口。"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

HEIF_AVAILABLE = False
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    pass

SUPPORTED_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
    ".tif", ".tiff", ".heic", ".heif",
}
GENERATED_RE = re.compile(r"_compressed(?:_\d+)?$", re.IGNORECASE)

LEVELS = {
    "light": {
        "label": "轻度", "jpeg_quality": 90, "webp_quality": 85,
        "heic_quality": 85, "png_colors": None, "gif_colors": 256,
    },
    "standard": {
        "label": "标准", "jpeg_quality": 75, "webp_quality": 75,
        "heic_quality": 70, "png_colors": 256, "gif_colors": 256,
    },
    "strong": {
        "label": "强力", "jpeg_quality": 55, "webp_quality": 55,
        "heic_quality": 50, "png_colors": 128, "gif_colors": 128,
    },
    "extreme": {
        "label": "极限", "jpeg_quality": 35, "webp_quality": 35,
        "heic_quality": 30, "png_colors": 64, "gif_colors": 64,
    },
}
FORMAT_BY_EXT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
    ".bmp": "BMP", ".gif": "GIF", ".tif": "TIFF", ".tiff": "TIFF",
    ".heic": "HEIF", ".heif": "HEIF",
}
EXT_BY_FORMAT = {
    "JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp",
    "GIF": ".gif", "TIFF": ".tif", "HEIF": ".heic",
}
OUTPUT_FORMAT_MAP = {"jpg": "JPEG", "webp": "WEBP", "png": "PNG"}
SAVEABLE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "HEIF"}


class ToolError(Exception):
    """可读的用户错误。"""


class SkipImage(ToolError):
    """可以跳过而不算失败的图片。"""


@dataclass
class CompressResult:
    source: Path
    output: Path
    original_size: int
    output_size: int
    source_format: str
    output_format: str
    width: int
    height: int
    kept_original: bool = False
    note: str = ""


@dataclass
class BatchResult:
    results: list
    skipped: list
    failures: list
    total_original: int
    total_output: int


def warn(message):
    print("警告: " + message, file=sys.stderr)


def natural_key(text):
    """自然排序键: 1.jpg < 2.jpg < 10.jpg"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(text))]


def is_image_file(path):
    return path.suffix.lower() in SUPPORTED_EXTS


def _is_generated(path):
    return bool(GENERATED_RE.search(path.stem))


def _dedupe_paths(files):
    seen = set()
    unique = []
    for path in files:
        key = os.path.normcase(str(path.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def expand_inputs(inputs, recursive=False):
    """展开文件和目录，返回去重后的图片路径，保持输入或自然排序。"""
    files = []
    for raw in inputs:
        path = Path(raw)
        if path.is_file():
            # 用户明确指定的文件不检查后缀，交给 Pillow 判断
            files.append(path)
        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            matched = sorted(
                (p for p in iterator if p.is_file()
                 and is_image_file(p) and not _is_generated(p)),
                key=lambda p: natural_key(p.relative_to(path).as_posix()),
            )
            if not matched:
                warn("目录中没有找到可处理的图片: " + str(path))
            files.extend(matched)
        else:
            raise ToolError("输入路径不存在: " + str(raw))
    return _dedupe_paths(files)


def resolve_level(level):
    try:
        return LEVELS[level]
    except KeyError:
        raise ToolError(
            "未知压缩档位: %r（可用: light/standard/strong/extreme）" % level)


def unique_output_path(output_dir, source, ext):
    base = source.stem + "_compressed"
    index = 0
    while True:
        suffix = "" if index == 0 else "_%d" % index
        candidate = output_dir / (base + suffix + ext)
        if not candidate.exists() and candidate.resolve() != source.resolve():
            return candidate
        index += 1


def _normalize_format(fmt, source):
    if fmt:
        fmt = fmt.upper()
        if fmt in ("JPG", "MPO"):
            return "JPEG"
        return fmt
    return FORMAT_BY_EXT.get(Path(source).suffix.lower(), "")


def _has_transparency(img):
    """同时识别 alpha 通道和 PNG/GIF 的 tRNS 透明信息。"""
    return ("A" in img.getbands()
            or img.info.get("transparency") is not None)


def _to_rgba(img):
    if img.mode == "RGBA":
        return img.copy()
    return img.convert("RGBA")


def _flatten_alpha(img):
    """把透明像素合成到白底，返回 RGB 图像。"""
    if _has_transparency(img):
        rgba = _to_rgba(img)
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return img.convert("RGB")


def _resize_if_needed(img, max_edge):
    """限制长边，只缩小不放大；返回 (图像, 是否实际缩放)。"""
    if max_edge is None:
        return img, False
    if not isinstance(max_edge, int) or max_edge <= 0:
        raise ToolError("长边必须是正整数")
    if max(img.size) <= max_edge:
        return img, False
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    return img, True


def _quantize_png(img, colors):
    try:
        source = _to_rgba(img) if _has_transparency(img) else img.convert("RGB")
        result = source.quantize(colors=colors, method=Image.FASTOCTREE)
        # 某些源文件会把 RGB 颜色键（tuple）带进 P 模式结果，
        # PNG 保存器无法处理这种 transparency，只保留合法的索引/alpha 信息。
        transparency = result.info.get("transparency")
        if transparency is not None and not isinstance(
                transparency, (bytes, bytearray, int)):
            result.info.pop("transparency", None)
        return result
    except Exception:
        return img


def _palette_transparency_index(img):
    """返回 P 模式调色板中第一个完全透明的索引，找不到则 None。"""
    if img.mode != "P":
        return None
    try:
        palette = img.getpalette("RGBA")
    except Exception:
        return None
    if not palette:
        return None
    for index in range(min(len(palette) // 4, 256)):
        if palette[index * 4 + 3] == 0:
            return index
    return None


def _save_image(img, path, target_format, preset, icc_profile):
    save_kwargs = {}
    if icc_profile and target_format in ("JPEG", "PNG", "WEBP", "TIFF"):
        save_kwargs["icc_profile"] = icc_profile

    if target_format == "JPEG":
        img = _flatten_alpha(img)
        is_light = preset is LEVELS["light"]
        save_kwargs.update(
            quality=preset["jpeg_quality"],
            # Pillow 10.4 在 q90 + 4:4:4 + optimize 下会报编码错误；
            # 轻度档关闭 optimize，画质和 4:4:4 采样保持不变。
            optimize=not is_light,
            subsampling=0 if is_light else 2,
        )
    elif target_format == "PNG":
        if preset["png_colors"]:
            img = _quantize_png(img, preset["png_colors"])
        save_kwargs.update(optimize=True, compress_level=9)
    elif target_format == "WEBP":
        if img.mode not in ("RGB", "RGBA"):
            img = _to_rgba(img) if _has_transparency(img) else img.convert("RGB")
        save_kwargs.update(quality=preset["webp_quality"], method=6)
    elif target_format == "TIFF":
        if img.mode not in ("RGB", "RGBA", "L", "CMYK", "I;16"):
            img = _to_rgba(img) if _has_transparency(img) else img.convert("RGB")
        save_kwargs.update(compression="tiff_deflate")
    elif target_format == "BMP":
        img = _flatten_alpha(img)
    elif target_format == "GIF":
        img = _quantize_png(img, preset["gif_colors"])
        transparency = _palette_transparency_index(img)
        if transparency is not None:
            save_kwargs["transparency"] = transparency
        save_kwargs.update(optimize=True)
    elif target_format == "HEIF":
        img = _flatten_alpha(img)
        save_kwargs.update(quality=preset["heic_quality"])
    else:
        raise ToolError("暂不支持的输出格式: " + target_format)

    img.save(str(path), format=target_format, **save_kwargs)


def compress_image(source, output_dir, level="standard",
                   output_format="keep", max_edge=None):
    """压缩单张图片并返回结果。"""
    preset = resolve_level(level)
    if max_edge is not None and (not isinstance(max_edge, int) or max_edge <= 0):
        raise ToolError("长边必须是正整数")

    source = Path(source)
    if source.suffix.lower() in (".heic", ".heif") and not HEIF_AVAILABLE:
        raise ToolError(
            "HEIC/HEIF 需要 pillow-heif，请先安装: "
            "python -m pip install -i "
            "https://pypi.tuna.tsinghua.edu.cn/simple pillow-heif==0.18.0")
    original_size = source.stat().st_size
    try:
        with Image.open(str(source)) as opened:
            if getattr(opened, "n_frames", 1) > 1:
                raise SkipImage("暂不支持动图: " + str(source))
            source_format = _normalize_format(opened.format, source)
            icc_profile = opened.info.get("icc_profile")
            img = ImageOps.exif_transpose(opened)
            img.load()
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError("无法读取图片 %s: %s" % (source, exc))

    if source_format not in SAVEABLE_FORMATS:
        raise ToolError("暂不支持的输入格式: " + (source_format or str(source)))
    if output_format == "keep":
        target_format = source_format
    else:
        target_format = OUTPUT_FORMAT_MAP.get(output_format)
        if target_format is None:
            raise ToolError("未知输出格式: " + str(output_format))
    if target_format not in SAVEABLE_FORMATS:
        raise ToolError("暂不支持的输出格式: " + target_format)
    ext = EXT_BY_FORMAT.get(target_format)
    if ext is None:
        raise ToolError("暂不支持的输出格式: " + target_format)

    img, resized = _resize_if_needed(img, max_edge)

    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ToolError("无法创建输出目录 %s: %s" % (output_dir, exc))

    output = unique_output_path(output_dir, source, ext)
    handle, temp_name = tempfile.mkstemp(
        prefix=".compress_", suffix=".tmp", dir=str(output_dir))
    os.close(handle)
    try:
        _save_image(img, temp_name, target_format, preset, icc_profile)
        os.replace(temp_name, str(output))
    except Exception:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise

    output_size = output.stat().st_size
    kept_original = False
    note = ""
    if (target_format == source_format and not resized
            and output_size >= original_size):
        output.unlink()
        shutil.copy2(str(source), str(output))
        output_size = output.stat().st_size
        kept_original = True
        note = "压缩后体积未减小，已保留原图"
    elif output_size >= original_size:
        note = "处理后的文件体积大于原图"

    width, height = img.size
    return CompressResult(
        source=source,
        output=output,
        original_size=original_size,
        output_size=output_size,
        source_format=source_format,
        output_format=target_format,
        width=width,
        height=height,
        kept_original=kept_original,
        note=note,
    )


def compress_files(inputs, output_dir=None, level="standard",
                   output_format="keep", max_edge=None, recursive=False,
                   progress=None):
    """批量压缩，单张失败或跳过不影响其余图片。"""
    files = []
    failures = []
    for raw in inputs:
        try:
            files.extend(expand_inputs([raw], recursive))
        except ToolError as exc:
            failures.append((Path(raw), str(exc)))
    files = _dedupe_paths(files)
    if not files and not failures:
        raise ToolError("没有找到可处理的图片")
    if not files:
        return BatchResult(
            results=[], skipped=[], failures=failures,
            total_original=0, total_output=0)

    if output_dir is None:
        output_dir = files[0].parent / "compressed"
    else:
        output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ToolError("无法创建输出目录 %s: %s" % (output_dir, exc))

    results = []
    skipped = []
    total = len(files)
    for index, source in enumerate(files):
        if progress is not None:
            progress(index, total, source)
        try:
            results.append(compress_image(
                source, output_dir, level=level,
                output_format=output_format, max_edge=max_edge))
        except SkipImage as exc:
            skipped.append((source, str(exc)))
        except Exception as exc:  # noqa: BLE001 - 单张失败不影响整体
            failures.append((source, str(exc)))

    return BatchResult(
        results=results,
        skipped=skipped,
        failures=failures,
        total_original=sum(item.original_size for item in results),
        total_output=sum(item.output_size for item in results),
    )


def _format_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d B" % value
            return "%.1f %s" % (value, unit)
        value /= 1024.0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="compress.py", description="图片压缩工具")
    parser.add_argument("inputs", nargs="+", help="图片文件或文件夹")
    parser.add_argument(
        "-l", "--level", choices=list(LEVELS), default="standard",
        help="压缩档位（默认 standard）")
    parser.add_argument(
        "-o", "--output", default=None, help="输出目录")
    parser.add_argument(
        "-f", "--format", choices=["keep", "jpg", "webp", "png"],
        default="keep", help="输出格式（默认 keep）")
    parser.add_argument(
        "--max-size", type=int, default=None, help="限制长边像素，只缩小不放大")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="文件夹包含子目录")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_size is not None and args.max_size <= 0:
        parser.error("长边必须是正整数")

    try:
        summary = compress_files(
            args.inputs,
            output_dir=args.output,
            level=args.level,
            output_format=args.format,
            max_edge=args.max_size,
            recursive=args.recursive,
        )
    except ToolError as exc:
        print("错误: " + str(exc), file=sys.stderr)
        return 1

    for item in summary.results:
        line = "完成: %s -> %s (%s -> %s)" % (
            item.source, item.output,
            _format_size(item.original_size), _format_size(item.output_size))
        if item.note:
            line += " [" + item.note + "]"
        print(line)
    for path, reason in summary.skipped:
        print("跳过: %s (%s)" % (path, reason), file=sys.stderr)
    for path, reason in summary.failures:
        print("失败: %s (%s)" % (path, reason), file=sys.stderr)

    if summary.total_original:
        change = 100.0 * (1.0 - summary.total_output / summary.total_original)
        if change >= 0:
            volume = "节省 %.1f%%" % change
        else:
            volume = "增加 %.1f%%" % abs(change)
    else:
        volume = "无可统计体积"
    print("完成: 成功 %d 张, 跳过 %d 张, 失败 %d 张, 总体积 %s -> %s (%s)" % (
        len(summary.results), len(summary.skipped), len(summary.failures),
        _format_size(summary.total_original), _format_size(summary.total_output),
        volume))
    return 0 if summary.results else 1


if __name__ == "__main__":
    sys.exit(main())
