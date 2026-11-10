#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片拼接工具
============

把多张图片按「横排」或「竖排」拼成一张长图。

示例:
    python stitch.py a.jpg b.jpg c.jpg -d horizontal -o 横排.png
    python stitch.py ./photos -d vertical --gap 20 --bg white -o 竖排.jpg
    python stitch.py "D:/照片/*.jpg" -d h --fit max -o out.jpg

支持的输入格式: jpg / jpeg / png / bmp / gif / webp / tif / tiff
"""

import argparse
import glob as globmod
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageColor, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("缺少 Pillow 库，请先执行: python -m pip install Pillow")

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

OUTPUT_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".bmp": "BMP",
    ".webp": "WEBP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


class ToolError(Exception):
    """可读的用户错误。"""


def warn(message):
    print("警告: " + message, file=sys.stderr)


def natural_key(text):
    """自然排序键: 1.jpg < 2.jpg < 10.jpg"""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(text))]


def is_image_file(path):
    return path.suffix.lower() in SUPPORTED_EXTS


def expand_inputs(inputs, recursive):
    """展开文件、目录和通配符，返回图片路径列表（保持输入顺序）。"""
    files = []
    for raw in inputs:
        path = Path(raw)

        if globmod.has_magic(raw):
            matches = [Path(p) for p in globmod.glob(raw, recursive=True)]
            matched = sorted(
                (p for p in matches if p.is_file() and is_image_file(p)),
                key=lambda p: natural_key(p.name),
            )
            if not matched:
                warn("通配符没有匹配到图片: " + raw)
            files.extend(matched)

        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            matched = sorted(
                (p for p in iterator if p.is_file() and is_image_file(p)),
                key=lambda p: natural_key(p.relative_to(path).as_posix()),
            )
            if not matched:
                warn("目录中没有找到图片: " + raw)
            files.extend(matched)

        elif path.is_file():
            # 用户明确指定的文件不检查后缀，交给 Pillow 判断
            files.append(path)

        else:
            raise ToolError("输入路径不存在: " + raw)

    # 去重，保持先后顺序
    seen = set()
    unique = []
    for p in files:
        key = os.path.normcase(str(p.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def apply_sort(files, mode, reverse):
    if mode == "name":
        files = sorted(files, key=lambda p: natural_key(p.name))
    elif mode == "mtime":
        files = sorted(files, key=lambda p: os.path.getmtime(str(p)))
    if reverse:
        files = list(reversed(files))
    return files


def load_images(files):
    """读取图片并处理 EXIF 方向。无法读取的图片给出警告后跳过。"""
    loaded = []
    for path in files:
        try:
            with Image.open(str(path)) as src:
                img = ImageOps.exif_transpose(src)
                img.load()
                # 复制一份，避免文件关闭后图像失效；同时统一为 RGBA
                loaded.append((path, img.convert("RGBA")))
        except Exception as exc:  # noqa: BLE001 - 单张失败不影响整体
            warn("跳过无法读取的图片 %s (%s)" % (path, exc))
    return loaded


def resolve_background(value):
    """把颜色名/十六进制解析为 RGBA；`transparent` 表示透明。"""
    value = value.strip()
    if value.lower() in ("transparent", "none"):
        return None
    try:
        rgb = ImageColor.getrgb(value)
    except ValueError:
        raise ToolError(
            "无法识别的背景色: %r（可用 white、black、#rrggbb、rgb(255,0,0) 或 transparent）"
            % value
        )
    if len(rgb) == 4:
        return rgb
    return (rgb[0], rgb[1], rgb[2], 255)


def fit_images(images, direction, mode):
    """按需把所有图片在「交叉方向」上缩放到统一尺寸，保持宽高比。"""
    if mode == "none" or len(images) <= 1:
        return images

    if direction == "horizontal":
        # 统一高度
        if mode == "max":
            target = max(img.height for _, img in images)
        else:  # first
            target = images[0][1].height
        result = []
        for path, img in images:
            if img.height != target:
                width = max(1, round(img.width * target / img.height))
                img = img.resize((width, target), Image.Resampling.LANCZOS)
            result.append((path, img))
        return result

    # vertical: 统一宽度
    if mode == "max":
        target = max(img.width for _, img in images)
    else:  # first
        target = images[0][1].width
    result = []
    for path, img in images:
        if img.width != target:
            height = max(1, round(img.height * target / img.width))
            img = img.resize((target, height), Image.Resampling.LANCZOS)
        result.append((path, img))
    return result


def stitch(images, direction, gap, align, bg_rgba):
    """把 RGBA 图片列表拼接为一张 RGBA 大图。"""
    horizontal = direction == "horizontal"

    main_sizes = [img.width if horizontal else img.height for _, img in images]
    cross_sizes = [img.height if horizontal else img.width for _, img in images]

    if horizontal:
        width = sum(main_sizes) + gap * (len(images) - 1)
        height = max(cross_sizes)
    else:
        width = max(cross_sizes)
        height = sum(main_sizes) + gap * (len(images) - 1)

    canvas_color = bg_rgba if bg_rgba is not None else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (width, height), canvas_color)

    cursor = 0
    for (_, img), main in zip(images, main_sizes):
        cross_total, cross_size = (
            (height, img.height) if horizontal else (width, img.width)
        )
        if align == "center":
            offset = (cross_total - cross_size) // 2
        elif align == "end":
            offset = cross_total - cross_size
        else:  # start
            offset = 0
        position = (cursor, offset) if horizontal else (offset, cursor)
        canvas.paste(img, position, img)
        cursor += main + gap

    return canvas


def save_result(canvas, output, bg_rgba, quality):
    """按输出扩展名保存；不支持透明度的格式会先用背景色铺底。"""
    suffix = output.suffix.lower()
    if suffix not in OUTPUT_FORMATS:
        raise ToolError(
            "不支持的输出格式: %r（可用: %s）"
            % (suffix or output.name, ", ".join(sorted(OUTPUT_FORMATS)))
        )
    fmt = OUTPUT_FORMATS[suffix]

    if fmt in ("JPEG", "BMP"):
        if bg_rgba is None:
            base_rgb = (255, 255, 255)
            note = "透明背景在 %s 中不支持，已用白色铺底"
        else:
            base_rgb = bg_rgba[:3]
            note = None
        flat = Image.new("RGB", canvas.size, base_rgb)
        flat.paste(canvas, mask=canvas.getchannel("A"))
        out_img = flat
        if note:
            warn(note % fmt)
    else:
        out_img = canvas

    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
    elif fmt == "WEBP":
        save_kwargs["quality"] = quality
    elif fmt == "TIFF":
        save_kwargs["compression"] = "tiff_lzw"

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_img.save(str(output), format=fmt, **save_kwargs)
    except OSError as exc:
        raise ToolError("保存失败: %s (%s)" % (output, exc))


def limit_size(canvas, max_size):
    """把长边限制在 max_size 像素以内。"""
    if not max_size:
        return canvas
    longest = max(canvas.size)
    if longest <= max_size:
        return canvas
    scale = max_size / longest
    size = (max(1, round(canvas.width * scale)), max(1, round(canvas.height * scale)))
    return canvas.resize(size, Image.Resampling.LANCZOS)


def stitch_to_file(files, output, direction="horizontal", gap=0,
                   align="center", bg="white", fit="none",
                   quality=95, max_size=0):
    """完整流程: 读取 -> 缩放 -> 拼接 -> 保存。返回 (图片数, (宽, 高))。"""
    if not files:
        raise ToolError("没有找到可用的图片")

    output = Path(output)
    bg_rgba = resolve_background(bg)
    images = load_images(files)
    if not images:
        raise ToolError("所有图片都无法读取")

    images = fit_images(images, direction, fit)
    canvas = stitch(images, direction, gap, align, bg_rgba)
    canvas = limit_size(canvas, max_size)
    save_result(canvas, output, bg_rgba, quality)
    return len(images), canvas.size


def positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("必须是整数: %r" % text)
    if value <= 0:
        raise argparse.ArgumentTypeError("必须大于 0: %r" % text)
    return value


def non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("必须是整数: %r" % text)
    if value < 0:
        raise argparse.ArgumentTypeError("不能小于 0: %r" % text)
    return value


def quality_int(text):
    value = positive_int(text)
    if value > 100:
        raise argparse.ArgumentTypeError("质量范围为 1-100")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="stitch.py",
        description="图片拼接工具：把多张图片横排或竖排拼成一张长图。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python stitch.py 1.png 2.png 3.png -d horizontal -o 横排.png
  python stitch.py ./photos -d vertical --gap 20 -o 竖排.png
  python stitch.py "D:/照片/*.jpg" -d h --fit max --bg "#f0f0f0" -o out.jpg
""",
    )
    parser.add_argument(
        "inputs", nargs="+", metavar="图片/目录/通配符",
        help="输入图片；也可以给目录（默认只取该目录下的图片）或带引号的通配符",
    )
    parser.add_argument(
        "-d", "--direction", default="horizontal",
        choices=["horizontal", "vertical", "h", "v", "row", "column"],
        help="拼接方向: horizontal/h/row 横排（默认）, vertical/v/column 竖排",
    )
    parser.add_argument(
        "-o", "--output", default="stitched.png",
        help="输出文件路径（默认 stitched.png；格式由扩展名决定）",
    )
    parser.add_argument(
        "--gap", type=non_negative_int, default=0,
        help="图片之间的间距，像素（默认 0）",
    )
    parser.add_argument(
        "--bg", default="white",
        help="背景色: white/black/#rrggbb/rgb(...)/transparent（默认 white）",
    )
    parser.add_argument(
        "--align", default="center", choices=["start", "center", "end"],
        help="交叉方向的对齐方式: start/center/end（默认 center）",
    )
    parser.add_argument(
        "--fit", default="none", choices=["none", "max", "first"],
        help="交叉方向尺寸不统一时: none 保持原样（默认）, max 统一到最大值, first 统一到第一张",
    )
    parser.add_argument(
        "--sort", default="auto", choices=["auto", "name", "mtime"],
        help="排序方式: auto 保持输入/目录自然顺序（默认）, name 按文件名自然排序, mtime 按修改时间",
    )
    parser.add_argument("--reverse", action="store_true", help="反转图片顺序")
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="递归读取子目录中的图片（仅对目录输入有效）",
    )
    parser.add_argument(
        "--max-size", type=positive_int, default=0,
        help="限制输出长边最大像素数（默认不限制）",
    )
    parser.add_argument(
        "--quality", type=quality_int, default=95,
        help="JPEG/WebP 输出质量 1-100（默认 95）",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    direction = {"h": "horizontal", "row": "horizontal",
                 "v": "vertical", "column": "vertical"}.get(
        args.direction, args.direction)

    output = Path(args.output)
    files = expand_inputs(args.inputs, args.recursive)

    # 防止把上次生成的结果又拼进去（例如对同一目录重复执行）
    output_key = os.path.normcase(str(output.resolve()))
    before = len(files)
    files = [p for p in files if os.path.normcase(str(p.resolve())) != output_key]
    if len(files) != before:
        warn("已自动排除输出文件本身: " + str(output))

    files = apply_sort(files, args.sort, args.reverse)
    if not files:
        raise ToolError("没有找到可用的图片")

    count, size = stitch_to_file(
        files, output,
        direction=direction, gap=args.gap, align=args.align,
        bg=args.bg, fit=args.fit, quality=args.quality,
        max_size=args.max_size,
    )
    print("已拼接 %d 张图片 -> %s (%d x %d)" % (count, output, size[0], size[1]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ToolError as exc:
        print("错误: " + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
