# 图片压缩工具实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 Windows 上交付一个可单张/批量压缩图片的本地工具，支持四档压缩强度、保持原格式或转换 JPG/WebP/PNG、可选长边缩放，并提供图形界面和命令行入口。

**架构：** `compress.py` 存放与界面无关的输入发现、单图压缩、批量汇总和 CLI；`compress_gui.py` 只是 Tkinter 前端，通过回调报告进度。核心处理全部基于 Pillow，HEIC 通过 `pillow-heif` 注册的编解码器读写。输出先写临时文件再替换，避免留下半成品。

**技术栈：** Python 3.8+、Tkinter、Pillow 10.4、pillow-heif 0.18（Python 3.8 兼容版本）

**规格：** `img_compress/docs/superpowers/specs/2026-11-10-image-compressor-design.md`

## 全局约束

- 所有产品代码、测试和文档放在 `img_compress/` 下；不修改 `img_add/`。
- 支持输入：JPG/JPEG、PNG、WebP、BMP、TIFF、HEIC/HEIF、静态 GIF；多帧动图跳过。
- 四档取值以规格第 5 节为准，默认 `standard`。
- 默认保持原格式；可选输出 `jpg`、`webp`、`png`。
- 绝不覆盖原图；输出名为 `<stem>_compressed.<ext>`，冲突时追加 `_1`、`_2`。
- 同格式且未实际缩放时，若结果不小于原图，则复制原图并标记 `kept_original=True`。
- 应用 EXIF 方向后移除 EXIF；ICC 配置在 Pillow 支持的目标格式中保留。
- 不实现资源管理器拖放；不实现动画帧处理、证件照裁剪、目标文件大小搜索。
- 所有面向用户的文字使用中文。
- 当前目录不是 Git 仓库，本计划不执行 `git commit`；每个任务以“当前任务测试通过”作为检查点。
- 命令默认在 `D:\000_study\020_code\claude\img_compress` 下执行。

## 审查重点（Review Focus）

- **中文和空格路径**：输入、输出目录、文件名包含中文或空格时仍能正确读写；由任务 1 的路径展开测试、任务 2 的压缩输出测试、任务 7 的 CLI 测试覆盖。
- **损坏或伪装扩展名的图片**：单张失败不能拖垮整批，必须记录原因并继续；由任务 6 的混合批次测试和任务 7 的“全部失败返回 1”测试覆盖。
- **递归目录与生成文件**：文件夹扫描不能把上次生成的 `_compressed` 文件再次当作输入；由任务 1 的生成文件排除测试、任务 6 的递归输出目录测试覆盖。
- **超长图和大图**：毕业长图在未勾选缩放时必须保持原尺寸；缩放时只缩长边、不改宽高比；由任务 2 的尺寸保持测试、任务 3 的长图缩放测试覆盖。
- **源目录等于输出目录**：输出文件名必须避让原图，原图字节不能被改写；由任务 2 的同目录重复压缩测试覆盖。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `img_compress/compress.py` | 常量、输入发现、压缩核心、批量汇总、CLI |
| `img_compress/compress_gui.py` | Tkinter 界面、后台线程、进度队列 |
| `img_compress/test_compress.py` | 核心逻辑、批量、CLI、HEIC 测试 |
| `img_compress/test_gui_smoke.py` | GUI 构建与文件列表冒烟测试 |
| `img_compress/requirements.txt` | Pillow、pillow-heif |
| `img_compress/run_gui.bat` | Windows 双击启动 GUI |
| `img_compress/README.md` | 安装、使用、档位和限制说明 |

---

### 任务 1：项目骨架与输入发现

**文件：**
- 创建：`img_compress/compress.py`
- 创建：`img_compress/test_compress.py`
- 创建：`img_compress/requirements.txt`

**接口：**
- `SUPPORTED_EXTS: set`
- `ToolError(Exception)`
- `natural_key(text) -> list`
- `is_image_file(path: Path) -> bool`
- `expand_inputs(inputs, recursive: bool) -> list[Path]`

- [ ] **步骤 1：编写失败的测试**

在 `test_compress.py` 写入以下测试骨架，覆盖目录展开、自然排序、去重、生成文件排除、递归和中文空格路径：

```python
import tempfile
import unittest
from pathlib import Path
from PIL import Image

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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.ExpandInputsTests -v`

预期：FAIL/ERROR，提示 `ModuleNotFoundError: No module named 'compress'`。

- [ ] **步骤 3：实现常量和输入发现**

在 `compress.py` 建立 UTF-8 文件头，导入 `os`、`re`、`sys`、`Path`、Pillow。实现：

- `SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif"}`
- `GENERATED_RE = re.compile(r"_compressed(?:_\d+)?$", re.IGNORECASE)`
- `ToolError` 与 `warn(message)`（警告写 stderr）。
- `natural_key` 把数字段转为整数，其余转小写。
- `is_image_file` 只判断后缀。
- `expand_inputs`：
  - 显式文件无论后缀都加入；路径不存在抛 `ToolError("输入路径不存在: ...")`。
  - 目录只收受支持后缀，排除 `GENERATED_RE` 匹配的 stem；非递归用 `iterdir()`，递归用 `rglob("*")`。
  - 目录内按 `relative_to(path).as_posix()` 的自然键排序；空目录只警告。
  - 用 `os.path.normcase(str(p.resolve()))` 去重并保持首次出现顺序。

同时写入 `requirements.txt`：

```text
Pillow>=10.4
pillow-heif>=0.18
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.ExpandInputsTests -v`

预期：4 个测试全部 PASS。

- [ ] **步骤 5：检查点**

运行：`python -m unittest -v`。记录当前测试通过；当前不是 Git 仓库，不提交。

---

### 任务 2：单图压缩与四档预设

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/test_compress.py`

**接口：**
- `LEVELS: dict[str, dict]`
- `resolve_level(level: str) -> dict`
- `unique_output_path(output_dir: Path, source: Path, ext: str) -> Path`
- `CompressResult`（字段：`source`, `output`, `original_size`, `output_size`, `source_format`, `output_format`, `width`, `height`, `kept_original`, `note`）
- `compress_image(source, output_dir, level="standard", output_format="keep", max_edge=None) -> CompressResult`

- [ ] **步骤 1：编写失败的测试**

在 `test_compress.py` 添加：

```python
import io
import random


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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.CompressImageTests -v`

预期：FAIL/ERROR，提示 `AttributeError: module 'compress' has no attribute 'compress_image'`。

- [ ] **步骤 3：实现四档预设和同格式压缩**

在 `compress.py` 增加：

```python
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
```

实现 `resolve_level`：键不存在时抛 `ToolError`，消息列出 `light/standard/strong/extreme`。

实现 `unique_output_path`：

- 基名 `source.stem + "_compressed"`。
- 依次尝试 `base+ext`、`base_1+ext`、`base_2+ext`……
- 用 `resolve()` 比较，避免与原图或已有文件重名。

实现 `CompressResult`（`@dataclass`）。实现 `_save_image(img, path, target_format, preset, icc_profile)`：

- `JPEG`：有 alpha 时白底合成 RGB；`quality=preset["jpeg_quality"]`，`optimize=True`，轻度 `subsampling=0`，其余 `subsampling=2`。
- `PNG`：`optimize=True`，`compress_level=9`；本任务先不做调色板量化。
- `WEBP`：`quality=preset["webp_quality"]`，`method=6`。
- 其他格式先抛 `ToolError("暂不支持的输出格式: ...")`。
- 支持的格式传入 `icc_profile`（若存在且不为空）。

实现 `compress_image`：

- 校验 level；本任务若 `output_format != "keep"` 或 `max_edge is not None`，抛 `ToolError`（任务 3 再扩展）。
- 用 `Image.open(source)` 打开，`ImageOps.exif_transpose`，`load()`；记录原始 `img.format` 和 `icc_profile`。
- 源格式规范化为 `JPEG/PNG/WEBP/...`；目标格式取源格式；目标扩展名取 `EXT_BY_FORMAT`。
- 创建输出目录；生成唯一输出路径；先写到同目录临时文件（`.tmp` 后缀），用显式 `format=target_format` 保存，成功后 `os.replace`；异常时删除临时文件并重抛。
- 比较大小：若目标格式等于源格式且未缩放，并且输出大小 `>=` 原图大小，则删除输出、`shutil.copy2(source, output)`，设置 `kept_original=True` 和说明“压缩后体积未减小，已保留原图”。
- 返回 `CompressResult`，尺寸取保存前 `img.size`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.CompressImageTests -v`

预期：7 个测试全部 PASS。

- [ ] **步骤 5：检查点**

运行：`python -m unittest -v`。记录通过数；不提交。

---

### 任务 3：格式转换、长边缩放与透明通道

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/test_compress.py`

**接口：**
- `compress_image(source, output_dir, level="standard", output_format="keep", max_edge=None)` 扩展为支持 `output_format in {"keep", "jpg", "webp", "png"}` 和正整数 `max_edge`。

- [ ] **步骤 1：编写失败的测试**

添加：

```python
class ConvertAndResizeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def make_alpha_png(self, path):
        img = Image.new("RGBA", (200, 200), (220, 30, 40, 255))
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
            src, self.out, level="standard", output_format="png")
        self.assertEqual(result.output.suffix, ".png")
        self.assertFalse(result.kept_original)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.ConvertAndResizeTests -v`

预期：FAIL，`ToolError: 暂不支持转换输出格式` 或尺寸断言失败。

- [ ] **步骤 3：实现格式转换、缩放和透明处理**

- `OUTPUT_FORMAT_MAP = {"jpg": "JPEG", "webp": "WEBP", "png": "PNG"}`。
- 解析目标格式：`keep` 用源格式，其余查 `OUTPUT_FORMAT_MAP`；未知值抛 `ToolError`。
- 校验 `max_edge`：`None` 或正整数；`<= 0` 抛 `ToolError("长边必须是正整数")`。
- 实现 `_resize_if_needed(img, max_edge)`：仅当 `max(img.size) > max_edge` 时用 `img.thumbnail((max_edge, max_edge), Image.LANCZOS)`，返回 `(img, resized_bool)`；不放大。
- 实现 `_flatten_alpha(img)`：把带 alpha 的图像合成到白色 RGBA 底，返回 RGB；没有 alpha 时直接转 RGB。
- 在 `_save_image` 的 `PNG` 分支加入量化：若 `preset["png_colors"]` 非空，先转 `RGBA` 或 `RGB` 再 `quantize(colors=n, method=Image.FASTOCTREE)`；失败时退回普通 PNG 无损保存。
- 对 `JPEG` 使用 `_flatten_alpha`；`WEBP`/`PNG` 保留透明。
- 回退规则改为：仅当 `target_format == source_format` 且 `resized is False` 且输出不小于原图时才复制原图。格式转换或实际缩放时保留处理后结果，即使更大也在 `note` 中写“转换后体积增大”。
- 更新 `CompressResult.output_format` 为目标格式。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.ConvertAndResizeTests -v`

预期：6 个测试全部 PASS。

- [ ] **步骤 5：运行全量测试**

运行：`python -m unittest -v`。预期：任务 1-3 所有测试通过。

---

### 任务 4：BMP/TIFF/GIF 与动图跳过

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/test_compress.py`

**接口：**
- 新增 `SkipImage(ToolError)`；`compress_image` 遇到 `n_frames > 1` 时抛出。
- `_save_image` 支持 `BMP`、`TIFF`、`GIF`。

- [ ] **步骤 1：编写失败的测试**

添加：

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.ExtraFormatsTests -v`

预期：FAIL，BMP/TIFF/GIF 抛出“暂不支持的输出格式”，动图没有抛出 `SkipImage`。

- [ ] **步骤 3：实现剩余格式**

- 在打开图片后检查 `getattr(img, "n_frames", 1) > 1`，若是则抛 `SkipImage("暂不支持动图: ...")`。
- `_save_image` 增加：
  - `TIFF`：`compression="tiff_deflate"`，可带 `icc_profile`。
  - `BMP`：普通保存，不传 `quality`/`optimize`。
  - `GIF`：用 `preset["gif_colors"]` 量化后保存，`optimize=True`；静态图才允许。
- 保持原格式时扩展名：`.tif`/`.tiff` 统一输出 `.tif`，其他保持映射。
- 回退规则不变：BMP 同格式重编码通常更大，会被复制原图；这是预期行为。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.ExtraFormatsTests -v`

预期：3 个测试全部 PASS。

- [ ] **步骤 5：运行全量测试**

运行：`python -m unittest -v`。

---

### 任务 5：HEIC/HEIF 读写

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/requirements.txt`
- 修改：`img_compress/test_compress.py`

**接口：**
- 模块级 `HEIF_AVAILABLE: bool`
- HEIC/HEIF 输入在插件缺失时抛 `ToolError`，消息包含 `pillow-heif` 和安装命令。

- [ ] **步骤 1：安装依赖**

运行：

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pillow-heif==0.18.0
```

验证：`python -c "import pillow_heif; print(pillow_heif.__version__)"` 输出 `0.18.0`。

- [ ] **步骤 2：编写失败的测试**

添加：

```python
from unittest import mock


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
        Image.new("RGB", (64, 48), (90, 120, 150)).save(src, format="HEIF")
        result = compress.compress_image(src, self.out, level="standard")
        self.assertEqual(result.output.suffix, ".heic")
        with Image.open(result.output) as img:
            self.assertIn(img.format, ("HEIF", "HEIC"))

    def test_missing_plugin_has_install_hint(self):
        src = self.dir / "photo.heic"
        src.write_bytes(b"x")
        with mock.patch.object(compress, "HEIF_AVAILABLE", False):
            with self.assertRaises(compress.ToolError) as ctx:
                compress.compress_image(src, self.out)
        self.assertIn("pillow-heif", str(ctx.exception))
```

- [ ] **步骤 3：运行测试验证失败**

运行：`python -m unittest test_compress.HeifTests -v`

预期：`HEIF_AVAILABLE` 不存在导致 ERROR；或在实现前 HEIC 断言失败。

- [ ] **步骤 4：实现 HEIC 支持**

- 模块级：

```python
HEIF_AVAILABLE = False
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    pass
```

- 在 `compress_image` 打开文件前：若后缀是 `.heic/.heif` 且 `HEIF_AVAILABLE` 为假，抛 `ToolError`，消息包含 `pillow-heif` 和 `python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pillow-heif==0.18.0`。
- 目标格式为 `HEIF` 且插件缺失时同样报错。
- `_save_image` 的 `HEIF` 分支：有 alpha 时 `_flatten_alpha` 转 RGB，`img.save(path, format="HEIF", quality=preset["heic_quality"])`。
- 目标扩展名 `.heic`；源 `.heif` 默认输出 `.heic`（同格式）。
- 完成后确保 `requirements.txt` 含 `pillow-heif>=0.18`。

- [ ] **步骤 5：运行测试验证通过**

运行：`python -m unittest test_compress.HeifTests -v`

预期：2 个测试 PASS（HEIC 测试实际执行，不跳过）。

- [ ] **步骤 6：检查点**

运行：`python -m unittest -v`。

---

### 任务 6：批量处理与错误汇总

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/test_compress.py`

**接口：**
- `BatchResult`（字段：`results`, `skipped`, `failures`, `total_original`, `total_output`）
- `compress_files(inputs, output_dir=None, level="standard", output_format="keep", max_edge=None, recursive=False, progress=None) -> BatchResult`
- `progress(done: int, total: int, source: Path)` 在每张图开始前调用。

- [ ] **步骤 1：编写失败的测试**

添加：

```python
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
        with self.assertRaises(compress.ToolError):
            compress.compress_files([str(empty)], output_dir=self.dir / "out")

    def test_all_failures_does_not_raise(self):
        bad = self.dir / "bad.jpg"
        bad.write_bytes(b"broken")
        result = compress.compress_files([str(bad)], output_dir=self.dir / "out")
        self.assertEqual(len(result.results), 0)
        self.assertEqual(len(result.failures), 1)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.BatchTests -v`

预期：FAIL，`compress_files` 不存在。

- [ ] **步骤 3：实现批量处理**

- 用 `@dataclass` 定义 `BatchResult`；`skipped`/`failures` 元素为 `(Path, str)`。
- `compress_files`：
  - `files = expand_inputs(inputs, recursive)`；为空抛 `ToolError("没有找到可处理的图片")`。
  - 输出目录：`Path(output_dir)`；未提供时 `files[0].parent / "compressed"`；`mkdir(parents=True, exist_ok=True)`，失败包成 `ToolError`。
  - 逐张调用 `compress_image`，每张开始前调用 `progress(done, total, source)`。
  - 捕获 `SkipImage` 放入 `skipped`；捕获其他 `Exception` 放入 `failures`，消息带异常文本；继续。
  - 汇总 `total_original`/`total_output` 只统计成功结果。
- 不在此函数中打印；由 CLI/GUI 决定展示方式。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.BatchTests -v`

预期：5 个测试 PASS。

- [ ] **步骤 5：运行全量测试**

运行：`python -m unittest -v`。

---

### 任务 7：命令行入口

**文件：**
- 修改：`img_compress/compress.py`
- 修改：`img_compress/test_compress.py`

**接口：**
- `build_parser() -> argparse.ArgumentParser`
- `main(argv=None) -> int`（0 表示至少一张成功；1 表示全部失败或参数级错误）

- [ ] **步骤 1：编写失败的测试**

添加：

```python
import contextlib


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

    def test_cli_rejects_unknown_level(self):
        with self.assertRaises(SystemExit):
            compress.main(["x.jpg", "-l", "nope"])

    def test_cli_max_size_must_be_positive(self):
        with self.assertRaises(SystemExit):
            compress.main(["x.jpg", "--max-size", "0"])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_compress.CliTests -v`

预期：FAIL，`main` 不存在。

- [ ] **步骤 3：实现 CLI**

- `build_parser`：
  - 位置参数 `inputs`，`nargs="+"`。
  - `-l/--level`，`choices=list(LEVELS)`，默认 `standard`。
  - `-o/--output`，输出目录，默认 `None`。
  - `-f/--format`，`choices=["keep", "jpg", "webp", "png"]`，默认 `keep`。
  - `--max-size`，自定义正整数校验：`<= 0` 时 `parser.error("长边必须是正整数")`。
  - `-r/--recursive`，`action="store_true"`。
- `main(argv=None)`：
  - 捕获 `ToolError`，stderr 输出 `错误: ...`，返回 1。
  - 调用 `compress_files`；每张成功输出一行，包含输出路径、原大小和结果大小。
  - 跳过/失败分别输出到 stderr，例如 `跳过: file (原因)`、`失败: file (原因)`。
  - 输出一行汇总，包含“完成”“成功”“跳过”“失败”和总节省百分比。
  - 返回 0 当 `summary.results` 非空，否则 1。
- 用 `if __name__ == "__main__": sys.exit(main())`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest test_compress.CliTests -v`

预期：4 个测试 PASS。

- [ ] **步骤 5：手动命令验证**

运行：

```bash
python -c "from PIL import Image; Image.new('RGB', (400, 300), (20, 60, 120)).save('cli_sample.jpg', 'JPEG')"
python compress.py cli_sample.jpg -l standard -o out -f webp
```

预期：输出中文完成信息，`out/cli_sample_compressed.webp` 存在；退出码为 0。

- [ ] **步骤 6：检查点**

运行：`python -m unittest -v`。

---

### 任务 8：图形界面、启动脚本与文档

**文件：**
- 创建：`img_compress/compress_gui.py`
- 创建：`img_compress/test_gui_smoke.py`
- 创建：`img_compress/run_gui.bat`
- 创建：`img_compress/README.md`

**接口：**
- `CompressApp(root)`，内部使用 `compress.LEVELS`、`compress.compress_files`。
- `main()` 启动 Tk 主循环。

- [ ] **步骤 1：编写 GUI 冒烟测试**

创建 `test_gui_smoke.py`：

```python
import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:
    tk = None

from PIL import Image
import compress_gui


class GuiSmokeTests(unittest.TestCase):
    @unittest.skipIf(tk is None, "Tkinter 不可用")
    def test_window_builds_and_file_list_updates(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("当前环境没有图形显示")
        root.withdraw()
        try:
            app = compress_gui.CompressApp(root)
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "a.jpg"
                Image.new("RGB", (20, 20), (1, 2, 3)).save(src, "JPEG")
                app._append(src)
                self.assertEqual(len(app.tree.get_children()), 1)
            root.update_idletasks()
        finally:
            root.destroy()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest test_gui_smoke -v`

预期：FAIL/ERROR，`No module named 'compress_gui'`。

- [ ] **步骤 3：实现 Tkinter 界面**

`compress_gui.py` 结构：

- `IMAGE_TYPES = [("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff *.heic *.heif"), ("所有文件", "*.*")]`
- `LEVEL_LABELS = {"轻度": "light", "标准": "standard", "强力": "strong", "极限": "extreme"}`，默认“标准”。
- `FORMAT_LABELS = {"保持原格式": "keep", "JPG": "jpg", "WebP": "webp", "PNG": "png"}`。
- `CompressApp.__init__`：标题“图片压缩工具”，约 920×680，最小 780×560；保存 `files`、`queue`、`busy`；构建 UI。
- UI：
  - 顶部 `LabelFrame("图片列表")` 内放 `Treeview`，列 `file/original/result/status`，只读；纵向滚动条。
  - 按钮行：添加图片、添加文件夹、删除选中、清空；右侧“共 N 张”。
  - `LabelFrame("压缩设置")`：
    - 压缩档位 `Combobox(state="readonly")`，值 `list(LEVEL_LABELS)`，默认“标准”。
    - 输出格式 `Combobox`，默认“保持原格式”。
    - “限制长边”`Checkbutton` + `Spinbox(1..100000)` 默认 1920，未勾选时禁用。
    - 输出文件夹 `Entry` + “浏览...”。
  - 底部：开始压缩按钮、`Progressbar`、状态文本。
- 文件操作：
  - `_append(path)` 去重，插入 Treeview，原始大小用 `_format_size`；首张图且输出目录为空时设为 `path.parent / "compressed"`；更新计数。
  - `add_files` 用 `filedialog.askopenfilenames`。
  - `add_folder` 用 `filedialog.askdirectory`，再 `compress.expand_inputs([folder], recursive=self.recursive_var.get())`；按钮行增加“包含子文件夹”复选框，绑定 `self.recursive_var = tk.BooleanVar(value=False)`。
  - `remove_selected` 删除 Treeview 选中项及对应文件。
  - `clear_all` 清空。
- 开始压缩：
  - 校验文件列表、输出目录、长边（勾选时必须正整数）。
  - 读取档位和格式映射，作为参数传入后台线程。
  - `busy=True`，禁用开始按钮，进度条归零。
  - 线程调用 `compress.compress_files(..., progress=lambda done,total,src: self.queue.put(("progress", done, total, src)))`；完成后放 `("done", summary)`；异常放 `("error", message)`。
  - `_poll` 每 100ms 处理队列：更新进度条/状态；完成时刷新 Treeview 的结果和状态列，弹窗汇总成功/跳过/失败和总节省体积；恢复按钮。
- 输出命名冲突和原图保护完全复用 `compress.py`，GUI 不重复实现。
- `main()` 使用 `vista` 主题（若存在），创建 `CompressApp` 并 `mainloop`。

- [ ] **步骤 4：创建启动脚本**

`run_gui.bat`：

```bat
@echo off
cd /d "%~dp0"
start "" pythonw compress_gui.py
```

- [ ] **步骤 5：运行 GUI 冒烟测试**

运行：`python -m unittest test_gui_smoke -v`

预期：PASS；窗口被 withdraw 后销毁，不残留进程。

- [ ] **步骤 6：编写 README**

`README.md` 至少包含：

- 功能简介和适用场景；
- 安装：`python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`；
- GUI：双击 `run_gui.bat` 或 `python compress_gui.py`，说明添加图片、文件夹、档位、格式、长边、输出目录；
- CLI 示例和参数表；
- 四档预设表（照规格第 5 节）；
- 支持格式和限制：动图跳过、BMP 原格式通常不变小、证件照只缩放不裁剪、不覆盖原图、EXIF 被移除；
- 测试命令：`python -m unittest -v`；
- 文件表。

- [ ] **步骤 7：全量验证**

运行：`python -m unittest -v`。预期：全部测试 PASS，HEIC 测试实际执行。

运行 GUI 冒烟：

```bash
python -c "import tkinter as tk, compress_gui; root=tk.Tk(); root.withdraw(); app=compress_gui.CompressApp(root); root.update_idletasks(); root.destroy(); print('GUI OK')"
```

预期输出 `GUI OK`。

手动压缩一张真实样例（若无样例，用临时生成图）：

```bash
python -c "from PIL import Image; Image.new('RGB', (1200, 800), (40, 90, 140)).save('sample.jpg', 'JPEG')"
python compress.py sample.jpg -l standard -o out -f keep
```

预期：`out/sample_compressed.jpg` 存在，终端汇总包含节省百分比。

- [ ] **步骤 8：完成检查点**

对照规格第 10 节逐条确认验收标准；记录每条对应的测试或手动证据。不提交 Git。
