#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compress.py 的自动化测试。运行: python -m unittest -v"""

import contextlib
import io
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageCms

import compress


class ExpandInputsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        for name in ("1.jpg", "2.png", "10.jpg", "photo_compressed.jpg",
                     "photo_compressed_1.png"):
            (self.dir / name).write_bytes(b"x")
        (self.dir / "child").mkdir()
        (self.dir / "child" / "3.webp").write_bytes(b"x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_directory_is_natural_sorted_deduped_and_skips_generated(self):
        paths = compress.expand_inputs(
            [str(self.dir), str(self.dir / "1.jpg"), str(self.dir / "1.jpg")],
            recursive=False,
        )
        self.assertEqual([p.name for p in paths], ["1.jpg", "2.png", "10.jpg"])

    def test_recursive_includes_subdirectory(self):
        paths = compress.expand_inputs([str(self.dir)], recursive=True)
        self.assertIn("3.webp", [p.name for p in paths])

    def test_unicode_and_space_path(self):
        folder = self.dir / "毕业 照片"
        folder.mkdir()
        image = folder / "长图 01.jpg"
        image.write_bytes(b"x")
        paths = compress.expand_inputs([str(folder)], recursive=False)
        self.assertEqual(paths, [image])

    def test_missing_path_raises_tool_error(self):
        with self.assertRaises(compress.ToolError):
            compress.expand_inputs([str(self.dir / "缺失.jpg")], recursive=False)


class CompressImageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def make_noise_jpeg(self, path, size=(640, 480), quality=95):
        rng = random.Random(42)
        img = Image.new("RGB", size)
        img.putdata([
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(size[0] * size[1])
        ])
        img.save(path, "JPEG", quality=quality)
        return path

    def test_jpeg_standard_reduces_size_and_keeps_dimensions(self):
        src = self.make_noise_jpeg(self.dir / "photo.jpg")
        result = compress.compress_image(src, self.out, level="standard")
        self.assertEqual(result.output.name, "photo_compressed.jpg")
        self.assertLess(result.output_size, result.original_size)
        with Image.open(result.output) as img:
            self.assertEqual(img.size, (640, 480))

    def test_extreme_is_smaller_than_light(self):
        src = self.make_noise_jpeg(self.dir / "photo.jpg")
        light = compress.compress_image(src, self.dir / "light", level="light")
        extreme = compress.compress_image(src, self.dir / "extreme", level="extreme")
        self.assertLess(extreme.output_size, light.output_size)

    def test_png_and_webp_keep_format(self):
        for ext, fmt in ((".png", "PNG"), (".webp", "WEBP")):
            src = self.dir / ("pixel" + ext)
            Image.new("RGB", (40, 30), (200, 30, 40)).save(src)
            result = compress.compress_image(src, self.out, level="standard")
            self.assertEqual(result.output.suffix, ext)
            with Image.open(result.output) as img:
                self.assertEqual(img.format, fmt)

    def test_collision_suffixes_and_original_unchanged(self):
        src = self.make_noise_jpeg(self.dir / "photo.jpg")
        original = src.read_bytes()
        first = compress.compress_image(src, self.dir, level="standard")
        second = compress.compress_image(src, self.dir, level="standard")
        self.assertEqual(first.output.name, "photo_compressed.jpg")
        self.assertEqual(second.output.name, "photo_compressed_1.jpg")
        self.assertEqual(src.read_bytes(), original)

    def test_keeps_original_when_recompression_larger(self):
        src = self.dir / "tiny.jpg"
        Image.new("RGB", (16, 16), (128, 128, 128)).save(
            src, "JPEG", quality=1, optimize=True)
        result = compress.compress_image(src, self.out, level="light")
        self.assertTrue(result.kept_original)
        self.assertEqual(result.output.read_bytes(), src.read_bytes())

    def test_unknown_level_is_rejected(self):
        src = self.make_noise_jpeg(self.dir / "photo.jpg")
        with self.assertRaises(compress.ToolError):
            compress.compress_image(src, self.out, level="nope")

    def test_unicode_output_path(self):
        src = self.make_noise_jpeg(self.dir / "照片 01.jpg")
        out = self.dir / "毕业 输出"
        result = compress.compress_image(src, out, level="standard")
        self.assertTrue(result.output.exists())
        self.assertIn("照片 01_compressed", result.output.name)


class ConvertAndResizeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def make_alpha_png(self, path):
        rng = random.Random(3)
        base = Image.new("RGB", (200, 200))
        base.putdata([
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(200 * 200)
        ])
        img = base.convert("RGBA")
        for x in range(50):
            for y in range(50):
                img.putpixel((x, y), (0, 0, 0, 0))
        img.save(path, "PNG")
        return path

    def test_convert_alpha_png_to_webp_keeps_transparency(self):
        src = self.make_alpha_png(self.dir / "alpha.png")
        result = compress.compress_image(
            src, self.out, level="standard", output_format="webp")
        self.assertEqual(result.output.suffix, ".webp")
        with Image.open(result.output) as img:
            self.assertLess(img.convert("RGBA").getpixel((10, 10))[3], 10)
            self.assertGreater(img.convert("RGBA").getpixel((100, 100))[3], 240)

    def test_convert_alpha_png_to_jpg_flattens_white(self):
        src = self.make_alpha_png(self.dir / "alpha.png")
        result = compress.compress_image(
            src, self.out, level="standard", output_format="jpg")
        with Image.open(result.output) as img:
            r, g, b = img.convert("RGB").getpixel((10, 10))
            self.assertGreater(min(r, g, b), 240)

    def test_png_quantization_reduces_colors_and_keeps_alpha(self):
        src = self.make_alpha_png(self.dir / "alpha.png")
        result = compress.compress_image(src, self.out, level="strong")
        with Image.open(result.output) as img:
            self.assertLess(img.convert("RGBA").getpixel((10, 10))[3], 10)
            colors = img.convert("RGB").getcolors(maxcolors=257)
            self.assertIsNotNone(colors)
            self.assertLessEqual(len(colors), 128)

    def test_resize_long_edge_and_no_upscale(self):
        src = self.dir / "long.jpg"
        Image.new("RGB", (1200, 600), (100, 120, 140)).save(src, "JPEG")
        resized = compress.compress_image(src, self.out, max_edge=400)
        with Image.open(resized.output) as img:
            self.assertEqual(img.size, (400, 200))
        bigger = compress.compress_image(src, self.dir / "bigger", max_edge=4000)
        with Image.open(bigger.output) as img:
            self.assertEqual(img.size, (1200, 600))

    def test_long_image_without_limit_keeps_dimensions(self):
        src = self.dir / "tall.jpg"
        Image.new("RGB", (200, 4000), (80, 90, 100)).save(src, "JPEG")
        result = compress.compress_image(src, self.out, level="standard")
        self.assertEqual((result.width, result.height), (200, 4000))

    def test_format_conversion_larger_result_is_kept(self):
        rng = random.Random(7)
        img = Image.new("RGB", (200, 200))
        img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                     for _ in range(200 * 200)])
        src = self.dir / "photo.jpg"
        img.save(src, "JPEG", quality=95)
        result = compress.compress_image(
            src, self.out, level="light", output_format="png")
        self.assertEqual(result.output.suffix, ".png")
        self.assertFalse(result.kept_original)
        self.assertIn("体积大于原图", result.note)


class TransparencyAndMetadataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def make_palette_trns_png(self, path):
        img = Image.new("P", (200, 200), 1)
        palette = [0, 0, 0, 220, 30, 40, 30, 200, 80] + [0, 0, 0] * 253
        img.putpalette(palette)
        for x in range(50):
            for y in range(50):
                img.putpixel((x, y), 0)
        img.save(path, "PNG", transparency=0)
        return path

    def make_rgb_trns_png(self, path):
        img = Image.new("RGB", (200, 200), (220, 30, 40))
        for x in range(50):
            for y in range(50):
                img.putpixel((x, y), (255, 0, 255))
        img.save(path, "PNG", transparency=(255, 0, 255))
        return path

    def test_palette_trns_png_standard_keeps_transparency(self):
        src = self.make_palette_trns_png(self.dir / "palette.png")
        result = compress.compress_image(src, self.out, level="standard")
        with Image.open(result.output) as img:
            rgba = img.convert("RGBA")
            self.assertLess(rgba.getpixel((10, 10))[3], 10)
            self.assertGreater(rgba.getpixel((100, 100))[3], 240)

    def test_rgb_trns_png_standard_keeps_transparency(self):
        src = self.make_rgb_trns_png(self.dir / "rgb.png")
        result = compress.compress_image(src, self.out, level="standard")
        with Image.open(result.output) as img:
            rgba = img.convert("RGBA")
            self.assertLess(rgba.getpixel((10, 10))[3], 10)
            self.assertGreater(rgba.getpixel((100, 100))[3], 240)

    def test_palette_trns_png_to_jpg_flattens_white(self):
        src = self.make_palette_trns_png(self.dir / "palette.png")
        result = compress.compress_image(
            src, self.out, level="standard", output_format="jpg")
        with Image.open(result.output) as img:
            r, g, b = img.convert("RGB").getpixel((10, 10))
            self.assertGreater(min(r, g, b), 240)

    def test_palette_trns_png_to_webp_keeps_transparency(self):
        src = self.make_palette_trns_png(self.dir / "palette.png")
        result = compress.compress_image(
            src, self.out, level="standard", output_format="webp")
        with Image.open(result.output) as img:
            self.assertLess(img.convert("RGBA").getpixel((10, 10))[3], 10)

    def test_transparent_gif_keeps_transparency(self):
        src = self.dir / "transparent.gif"
        img = Image.new("P", (100, 100), 1)
        palette = [0, 0, 0, 220, 30, 40, 30, 200, 80] + [0, 0, 0] * 253
        img.putpalette(palette)
        for x in range(30):
            for y in range(30):
                img.putpixel((x, y), 0)
        img.save(src, "GIF", transparency=0)
        result = compress.compress_image(src, self.out, level="strong")
        with Image.open(result.output) as out:
            self.assertLess(out.convert("RGBA").getpixel((10, 10))[3], 10)

    def test_animated_webp_is_skipped(self):
        src = self.dir / "anim.webp"
        frames = [Image.new("RGB", (20, 20), color) for color in
                  ((255, 0, 0), (0, 255, 0))]
        frames[0].save(src, "WEBP", save_all=True, append_images=frames[1:],
                       duration=100, loop=0)
        with self.assertRaises(compress.SkipImage):
            compress.compress_image(src, self.out)

    def test_exif_orientation_applied_and_stripped(self):
        src = self.dir / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (200, 100), (20, 80, 140)).save(
            src, "JPEG", exif=exif)
        result = compress.compress_image(src, self.out)
        with Image.open(result.output) as img:
            self.assertEqual(img.size, (100, 200))
            self.assertIsNone(img.getexif().get(274))

    def test_icc_profile_preserved(self):
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        icc = profile.tobytes()
        src = self.dir / "icc.jpg"
        Image.new("RGB", (80, 60), (90, 110, 130)).save(
            src, "JPEG", icc_profile=icc)
        result = compress.compress_image(src, self.out, level="standard")
        with Image.open(result.output) as img:
            self.assertEqual(img.info.get("icc_profile"), icc)


class ExtraFormatsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def test_bmp_and_tiff_keep_format(self):
        for ext, fmt in ((".bmp", "BMP"), (".tif", "TIFF")):
            src = self.dir / ("sample" + ext)
            Image.new("RGB", (80, 60), (40, 90, 160)).save(src)
            result = compress.compress_image(src, self.out, level="standard")
            self.assertEqual(result.output.suffix, ext)
            with Image.open(result.output) as img:
                self.assertEqual(img.format, fmt)

    def test_static_gif_keeps_format(self):
        src = self.dir / "static.gif"
        img = Image.new("RGB", (40, 40), (10, 20, 30))
        img.save(src, "GIF")
        result = compress.compress_image(src, self.out, level="strong")
        self.assertEqual(result.output.suffix, ".gif")
        with Image.open(result.output) as out:
            self.assertEqual(out.format, "GIF")

    def test_animated_gif_is_skipped(self):
        src = self.dir / "anim.gif"
        frames = [Image.new("RGB", (20, 20), color) for color in
                  ((255, 0, 0), (0, 255, 0))]
        frames[0].save(src, "GIF", save_all=True, append_images=frames[1:],
                       duration=100, loop=0)
        with self.assertRaises(compress.SkipImage) as ctx:
            compress.compress_image(src, self.out, level="standard")
        self.assertIn("动图", str(ctx.exception))


class HeifTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    @unittest.skipUnless(compress.HEIF_AVAILABLE, "pillow-heif 未安装")
    def test_heic_roundtrip(self):
        src = self.dir / "photo.heic"
        rng = random.Random(11)
        img = Image.new("RGB", (160, 120))
        img.putdata([
            (rng.randrange(256), rng.randrange(256), rng.randrange(256))
            for _ in range(160 * 120)
        ])
        img.save(src, format="HEIF", quality=95)
        result = compress.compress_image(src, self.out, level="standard")
        self.assertEqual(result.output.suffix, ".heic")
        self.assertFalse(result.kept_original)
        with Image.open(result.output) as out:
            self.assertIn(out.format, ("HEIF", "HEIC"))

    def test_missing_plugin_has_install_hint(self):
        src = self.dir / "photo.heic"
        src.write_bytes(b"x")
        with mock.patch.object(compress, "HEIF_AVAILABLE", False):
            with self.assertRaises(compress.ToolError) as ctx:
                compress.compress_image(src, self.out)
        self.assertIn("pillow-heif", str(ctx.exception))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_mixed_batch_continues_and_reports(self):
        good = self.dir / "good.jpg"
        Image.new("RGB", (200, 150), (120, 40, 80)).save(good, "JPEG")
        bad = self.dir / "bad.jpg"
        bad.write_bytes(b"not an image")
        anim = self.dir / "anim.gif"
        frames = [Image.new("RGB", (20, 20), c) for c in
                  ((255, 0, 0), (0, 255, 0))]
        frames[0].save(anim, "GIF", save_all=True, append_images=frames[1:])
        events = []
        result = compress.compress_files(
            [str(good), str(bad), str(anim)],
            output_dir=self.dir / "out",
            progress=lambda done, total, src: events.append((done, total, src.name)),
        )
        self.assertEqual(len(result.results), 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(events), 3)

    def test_default_output_dir(self):
        src = self.dir / "photo.jpg"
        Image.new("RGB", (120, 90), (30, 60, 90)).save(src, "JPEG")
        result = compress.compress_files([str(src)])
        self.assertEqual(result.results[0].output.parent, self.dir / "compressed")

    def test_recursive_directory_skips_generated_outputs(self):
        root = self.dir / "album"
        (root / "compressed").mkdir(parents=True)
        (root / "a.jpg").write_bytes(b"x")
        (root / "compressed" / "a_compressed.jpg").write_bytes(b"x")
        paths = compress.expand_inputs([str(root)], recursive=True)
        self.assertEqual([p.name for p in paths], ["a.jpg"])

    def test_empty_directory_raises(self):
        empty = self.dir / "empty"
        empty.mkdir()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(compress.ToolError):
                compress.compress_files([str(empty)], output_dir=self.dir / "out")

    def test_all_failures_does_not_raise(self):
        bad = self.dir / "bad.jpg"
        bad.write_bytes(b"broken")
        result = compress.compress_files([str(bad)], output_dir=self.dir / "out")
        self.assertEqual(len(result.results), 0)
        self.assertEqual(len(result.failures), 1)

    def test_missing_explicit_path_continues(self):
        good = self.dir / "good.jpg"
        Image.new("RGB", (120, 90), (30, 60, 90)).save(good, "JPEG")
        missing = self.dir / "gone.jpg"
        result = compress.compress_files(
            [str(good), str(missing)], output_dir=self.dir / "out")
        self.assertEqual(len(result.results), 1)
        self.assertEqual(len(result.failures), 1)


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = compress.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_cli_compresses_and_returns_zero(self):
        src = self.dir / "照片 01.jpg"
        Image.new("RGB", (200, 150), (10, 80, 120)).save(src, "JPEG")
        code, out, err = self.run_cli([
            str(src), "-l", "strong", "-o", str(self.dir / "out"), "-f", "webp",
        ])
        self.assertEqual(code, 0)
        self.assertIn("完成", out)
        self.assertTrue((self.dir / "out" / "照片 01_compressed.webp").exists())

    def test_cli_all_failures_return_one(self):
        bad = self.dir / "bad.jpg"
        bad.write_bytes(b"broken")
        code, out, err = self.run_cli([str(bad), "-o", str(self.dir / "out")])
        self.assertEqual(code, 1)
        self.assertIn("失败", err)

    def test_cli_reports_kept_original(self):
        src = self.dir / "tiny.jpg"
        Image.new("RGB", (16, 16), (128, 128, 128)).save(
            src, "JPEG", quality=1, optimize=True)
        code, out, err = self.run_cli([
            str(src), "-l", "light", "-o", str(self.dir / "out"),
        ])
        self.assertEqual(code, 0)
        self.assertIn("保留原图", out)

    def test_cli_rejects_unknown_level(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                compress.main(["x.jpg", "-l", "nope"])
        self.assertEqual(ctx.exception.code, 2)

    def test_cli_max_size_must_be_positive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                compress.main(["x.jpg", "--max-size", "0"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
