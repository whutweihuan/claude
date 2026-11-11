#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stitch.py 的自动化测试。运行: python test_stitch.py -v"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import stitch


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def make_image(path, size, color):
    Image.new("RGBA", size, color).save(path)


def rgb_at(path, xy):
    with Image.open(str(path)) as img:
        return img.convert("RGBA").getpixel(xy)


class StitchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.a = self.dir / "a.png"      # 100 x 60 红
        self.b = self.dir / "b.png"      # 80 x 100 绿
        self.c = self.dir / "c.png"      # 60 x 40 蓝
        make_image(self.a, (100, 60), RED)
        make_image(self.b, (80, 100), GREEN)
        make_image(self.c, (60, 40), BLUE)

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = stitch.main(args)
        self.assertEqual(code, 0)
        return out.getvalue(), err.getvalue()

    def test_horizontal_with_gap_and_center_align(self):
        out = self.dir / "h.png"
        self.run_tool([
            str(self.a), str(self.b), str(self.c),
            "-d", "horizontal", "--gap", "10", "-o", str(out),
        ])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, (260, 100))
        # 交叉方向居中对齐
        self.assertEqual(rgb_at(out, (0, 0)), (255, 255, 255, 255))
        self.assertEqual(rgb_at(out, (0, 20)), RED)
        self.assertEqual(rgb_at(out, (110, 0)), GREEN)
        self.assertEqual(rgb_at(out, (200, 30)), BLUE)
        # 间距处为背景色
        self.assertEqual(rgb_at(out, (105, 50)), (255, 255, 255, 255))

    def test_vertical(self):
        out = self.dir / "v.png"
        self.run_tool([
            str(self.a), str(self.b), str(self.c),
            "-d", "vertical", "--gap", "10", "-o", str(out),
        ])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, (100, 220))
        self.assertEqual(rgb_at(out, (0, 0)), RED)           # 第一张铺满整个宽度
        self.assertEqual(rgb_at(out, (0, 10)), RED)          # 第一张 y=0..59
        self.assertEqual(rgb_at(out, (10, 70)), GREEN)       # 第二张从 y=70 开始，水平居中
        self.assertEqual(rgb_at(out, (0, 70)), (255, 255, 255, 255))
        self.assertEqual(rgb_at(out, (20, 180)), BLUE)       # 第三张从 y=180 开始

    def test_transparent_background(self):
        # 中间留出透明区域: 80x100 的绿色图只画左半边
        partial = self.dir / "partial.png"
        img = Image.new("RGBA", (80, 100), (0, 0, 0, 0))
        img.paste(Image.new("RGBA", (40, 100), GREEN), (0, 0))
        img.save(str(partial))
        out = self.dir / "t.png"
        self.run_tool([
            str(self.a), str(partial),
            "-d", "horizontal", "--bg", "transparent", "-o", str(out),
        ])
        self.assertEqual(rgb_at(out, (150, 50)), (0, 0, 0, 0))  # 透明区域保持透明
        self.assertEqual(rgb_at(out, (110, 50)), GREEN)

    def test_transparent_to_jpeg_flattens_white(self):
        out = self.dir / "t.jpg"
        _, err = self.run_tool([
            str(self.a), str(self.c),
            "-d", "horizontal", "--bg", "transparent", "--gap", "20",
            "-o", str(out),
        ])
        self.assertIn("透明背景", err)
        # JPEG 有损压缩，纯白附近允许少量偏差
        r, g, b, a = rgb_at(out, (105, 50))
        self.assertTrue(min(r, g, b) >= 250, "应为白色背景，实际为 %r" % ((r, g, b),))

    def test_natural_sort_from_directory(self):
        d = self.dir / "photos"
        d.mkdir()
        make_image(d / "1.png", (10, 10), RED)
        make_image(d / "2.png", (10, 10), GREEN)
        make_image(d / "10.png", (10, 10), BLUE)
        out = self.dir / "sorted.png"
        self.run_tool([str(d), "-d", "v", "--gap", "0", "-o", str(out)])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, (10, 30))
        self.assertEqual(rgb_at(out, (0, 0)), RED)
        self.assertEqual(rgb_at(out, (0, 10)), GREEN)
        self.assertEqual(rgb_at(out, (0, 20)), BLUE)

    def test_reverse(self):
        out = self.dir / "rev.png"
        self.run_tool([
            str(self.a), str(self.b), str(self.c),
            "-d", "horizontal", "--reverse", "-o", str(out),
        ])
        self.assertEqual(rgb_at(out, (0, 30)), BLUE)

    def test_fit_max_uniform_height(self):
        out = self.dir / "fit.png"
        self.run_tool([
            str(self.a), str(self.b),
            "-d", "horizontal", "--fit", "max", "-o", str(out),
        ])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, (247, 100))  # a 等比放大到高 100、宽 167，再加上 b 的 80

    def test_max_size(self):
        out = self.dir / "small.png"
        self.run_tool([
            str(self.a), str(self.b), str(self.c),
            "-d", "horizontal", "--gap", "10", "--max-size", "130",
            "-o", str(out),
        ])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, (130, 50))

    def test_gap_and_bg(self):
        out = self.dir / "bg.png"
        self.run_tool([
            str(self.a), str(self.c),
            "-d", "horizontal", "--gap", "10", "--bg", "#123456",
            "--align", "start", "-o", str(out),
        ])
        self.assertEqual(rgb_at(out, (100, 50)), (0x12, 0x34, 0x56, 255))
        self.assertEqual(rgb_at(out, (0, 0)), RED)
        self.assertEqual(rgb_at(out, (110, 0)), BLUE)

    def test_output_excluded_on_rerun(self):
        d = self.dir / "photos2"
        d.mkdir()
        make_image(d / "1.png", (30, 20), RED)
        make_image(d / "2.png", (30, 20), GREEN)
        out = d / "stitched.png"
        self.run_tool([str(d), "-d", "v", "-o", str(out)])
        with Image.open(str(out)) as img:
            first = img.size
        self.run_tool([str(d), "-d", "v", "-o", str(out)])
        with Image.open(str(out)) as img:
            self.assertEqual(img.size, first)
            self.assertEqual(img.size, (30, 40))

    def test_missing_input(self):
        with self.assertRaises(stitch.ToolError):
            stitch.expand_inputs([str(self.dir / "nope.png")], False)

    def test_no_images(self):
        empty = self.dir / "empty"
        empty.mkdir()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(stitch.ToolError):
                stitch.main([str(empty), "-o", str(self.dir / "x.png")])

    def test_bad_background(self):
        with self.assertRaises(stitch.ToolError):
            stitch.resolve_background("not-a-color")


if __name__ == "__main__":
    unittest.main()
