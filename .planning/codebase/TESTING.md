---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
<!-- refreshed: 2026-11-11 -->
# Testing Patterns

**Analysis Date:** 2026-11-11

## Test Framework

**Runner:**
- Python standard library `unittest` (no pytest, no nose, no third-party test runner)
- No config file: no `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`, or `conftest.py`
- Python 3.8+ (per `img_compress/README.md`); tests import sibling modules by bare name, so they must run from the project directory

**Assertion Library:**
- `unittest.TestCase` assertion methods only: `assertEqual`, `assertLess`, `assertLessEqual`, `assertGreater`, `assertIn`, `assertNotIn`, `assertIsNone`, `assertIsNotNone`, `assertTrue`, `assertFalse`, `assertRaises`
- One custom failure message: `self.assertTrue(min(r, g, b) >= 250, "应为白色背景，实际为 %r" % ((r, g, b),))` (`image_add/test_stitch.py:105`)

**Run Commands:**
```bash
# img_compress - all tests (run from img_compress/)
python -m unittest -v

# img_compress - one class / module
python -m unittest test_compress.CompressImageTests -v
python -m unittest test_gui_smoke -v

# image_add - all tests
python test_stitch.py -v
# or, from image_add/
python -m unittest test_stitch -v

# snake_game - all tests
python -m unittest test_snake -v
# or
python test_snake.py -v
```
Coverage commands: none configured (`coverage.py`/`pytest-cov` not used or documented).

## Test File Organization

**Location:**
- Co-located: tests live at each project root beside the module under test, not in a `tests/` subtree
- `img_compress/test_compress.py` -> `img_compress/compress.py`
- `img_compress/test_gui_smoke.py` -> `img_compress/compress_gui.py`
- `image_add/test_stitch.py` -> `image_add/stitch.py`
- `snake_game/test_snake.py` -> `snake_game/snake.py`

**Naming:**
- `test_<module>.py` for logic tests; `test_<aspect>.py` for specialized suites (`test_gui_smoke.py`)
- Test classes group one feature/behavior area: `ExpandInputsTests`, `CompressImageTests`, `ConvertAndResizeTests`, `TransparencyAndMetadataTests`, `ExtraFormatsTests`, `HeifTests`, `BatchTests`, `CliTests`, `StitchTests`, `SnakeTests`, `GuiSmokeTests`
- Test methods: `test_<expected behavior in snake_case>`; prefer full sentences, e.g. `test_recompression_larger_result_is_kept`, `test_two_quick_turns_are_buffered`, `test_output_excluded_on_rerun`

**Structure:**
```
img_compress/
├── compress.py
├── compress_gui.py
├── test_compress.py          # 41 tests across 8 classes
└── test_gui_smoke.py         # 2 tests
image_add/
├── stitch.py
├── stitch_gui.py
└── test_stitch.py            # 13 tests, 1 class
snake_game/
├── snake.py
├── snake_gui.py
└── test_snake.py             # 11 tests, 1 class
```

**Current test totals:** 67 test methods (41 + 2 + 13 + 11).

## Test Structure

**Suite Organization:**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stitch.py 的自动化测试。运行: python test_stitch.py -v"""

import unittest
from pathlib import Path

from PIL import Image

import stitch


class StitchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        ...

    def tearDown(self):
        self._tmp.cleanup()

    def test_horizontal_with_gap_and_center_align(self):
        ...
```
Test modules always start with the same shebang/coding/docstring header as production code.

**Setup pattern:**
- `setUp` creates `self._tmp = tempfile.TemporaryDirectory()` and `self.dir = Path(self._tmp.name)`; optional `self.out = self.dir / "out"`
- Fixtures are real files written with Pillow or `write_bytes(b"x")`
- `tearDown` calls `self._tmp.cleanup()`; one variant uses `with tempfile.TemporaryDirectory() as tmp:` inline when GUI lifetime matters (`img_compress/test_gui_smoke.py:30`)
- Tests never write outside the temporary directory; output directories are subfolders such as `self.dir / "out"`

**Assertion pattern:**
- Behavioral assertions over implementation details: output file exists, suffix/format, size, pixel color, `kept_original`, `note`
- Pixel checks open the output with a context manager and convert explicitly:
```python
with Image.open(result.output) as img:
    self.assertEqual(img.size, (640, 480))
```
- RGBA alpha thresholds are used for transparency: `assertLess(alpha, 10)` for transparent, `assertGreater(alpha, 240)` for opaque
- Lossy formats allow tolerance: `assertGreater(min(r, g, b), 240)` or `>= 250` with a bilingual failure message

## Mocking

**Framework:** `unittest.mock` only.

**Patterns:**
```python
# Capability flag patched at module level
with mock.patch.object(compress, "HEIF_AVAILABLE", False):
    with self.assertRaises(compress.ToolError) as ctx:
        compress.compress_image(src, self.out)
self.assertIn("pillow-heif", str(ctx.exception))
```
(`img_compress/test_compress.py:371-377`)

```python
# Tk dialogs patched so the GUI flow can run headless
with mock.patch.object(compress_gui.messagebox, "showinfo"), \
        mock.patch.object(compress_gui.messagebox, "showwarning"), \
        mock.patch.object(compress_gui.messagebox, "showerror"):
    app.start()
```
(`img_compress/test_gui_smoke.py:60-62`)

**What to Mock:**
- Optional-dependency availability flags (`HEIF_AVAILABLE`)
- Tkinter `messagebox` dialogs (modal, would block tests)
- Nothing else. File dialogs are not exercised; tests call internal methods such as `app._append(path)` directly instead of `add_files()`

**What NOT to Mock:**
- Pillow, the filesystem, `Path`, or the core compression/stitching logic - tests generate real images and inspect real output files
- Threads in GUI smoke tests are not mocked; tests wait on real state

**Dependency substitution:** Instead of mocks, core modules accept injected deterministic dependencies:
- `SnakeGame(rng=random.Random(42))` for reproducible food placement (`snake_game/snake.py:33`)
- `compress_files(..., progress=lambda done, total, src: ...)` to capture progress events (`img_compress/test_compress.py:401`)

## Fixtures and Factories

**Test Data:**
```python
# Factory helper at module scope
def make_image(path, size, color):
    Image.new("RGBA", size, color).save(path)

def rgb_at(path, xy):
    with Image.open(str(path)) as img:
        return img.convert("RGBA").getpixel(xy)
```
(`image_add/test_stitch.py:21-27`)

```python
# Noise image with seeded RNG so compression is deterministic and compressible
def make_noise_jpeg(self, path, size=(640, 480), quality=95):
    rng = random.Random(42)
    img = Image.new("RGB", size)
    img.putdata([
        (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        for _ in range(size[0] * size[1])
    ])
    img.save(path, "JPEG", quality=quality)
    return path
```
(`img_compress/test_compress.py:64-72`)

Other factories in `img_compress/test_compress.py`: `make_alpha_png` (random seed 3), `make_palette_trns_png`, `make_rgb_trns_png`. The snake suite uses a helper that injects a seeded RNG by default:
```python
def make_game(self, **kwargs):
    kwargs.setdefault("rng", random.Random(42))
    return SnakeGame(**kwargs)
```
(`snake_game/test_snake.py:12-14`)

**Location:**
- Factories are private methods on the test class when they need `self.dir`, or module-level functions when stateless (`make_image`, `rgb_at`)
- Named color constants at module scope: `RED`, `GREEN`, `BLUE` as RGBA tuples (`image_add/test_stitch.py:16-18`)

## Coverage

**Requirements:** None. No coverage threshold, no CI workflow, no badge. README documents manual commands only.

**View Coverage:** Not available - no coverage tooling is installed or configured.

**Practical coverage:** Strong on core logic (input expansion, compression levels, format conversion, transparency, EXIF/ICC, collisions, batching, CLI exit codes), snake rules (movement, buffering, growth, collisions, reset), and GUI smoke paths. Untested: `image_add/stitch_gui.py` (no GUI test), `snake_game/snake_gui.py` (no GUI test), file dialogs, and error paths of some save formats.

## Test Types

**Unit Tests:**
- Direct calls into core functions and classes; the bulk of the suite
- Input discovery/sorting/deduplication: `ExpandInputsTests`
- Single-image compression semantics: `CompressImageTests`
- Conversion/resize/transparency/metadata: `ConvertAndResizeTests`, `TransparencyAndMetadataTests`, `ExtraFormatsTests`, `HeifTests`
- Snake rules: `SnakeTests`

**Integration Tests:**
- Batch workflow `compress_files` with mixed good/bad/animated inputs and progress capture: `BatchTests`
- End-to-end core pipeline for stitching, invoked through `stitch.main(args)` then inspecting the output image: `StitchTests.run_tool`
- GUI smoke through the real Tk event loop: `GuiSmokeTests`

**CLI Tests:**
- `CliTests` calls `compress.main(argv)` in-process, not via subprocess
- Stdout/stderr captured with `contextlib.redirect_stdout` / `redirect_stderr` into `io.StringIO`
- Exit codes verified (`0` success, `1` all failures, `2` argparse errors via `SystemExit`)
```python
def run_cli(self, args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = compress.main(args)
    return code, out.getvalue(), err.getvalue()
```

**E2E Tests:** Not used. No subprocess, browser, or packaged-binary tests.

## Common Patterns

**Async/threaded GUI testing:**
```python
app.start()
deadline = time.time() + 20
while app.busy and time.time() < deadline:
    root.update()
    time.sleep(0.05)
root.update()
self.assertFalse(app.busy)
```
(`img_compress/test_gui_smoke.py:63-70`) - real bounded polling with a 20-second deadline; never an unbounded `sleep`.

**GUI test harness:**
- Create `root = tk.Tk()` inside the test; skip if `tkinter` is missing or `TclError` is raised (headless)
- `root.withdraw()` to hide the window; `root.update_idletasks()`/`root.update()` to process events
- Always `root.destroy()` in `finally`
- Interact with internals (`app._append`, `app.path_items`, `app.tree.set`) rather than simulating clicks

**Error testing:**
```python
with self.assertRaises(compress.ToolError):
    compress.compress_image(src, self.out, level="nope")

with self.assertRaises(compress.SkipImage) as ctx:
    compress.compress_image(src, self.out, level="standard")
self.assertIn("动图", str(ctx.exception))
```
Assert both exception type and a meaningful message fragment.

**CLI system-exit testing:**
```python
with contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(SystemExit) as ctx:
        compress.main(["x.jpg", "--max-size", "0"])
self.assertEqual(ctx.exception.code, 2)
```

**Expected-warning suppression:** Tests that intentionally trigger `warn()` redirect stderr to keep output clean:
```python
with contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(compress.ToolError):
        compress.compress_files([str(empty)], output_dir=self.dir / "out")
```

**Conditional skips:**
- `@unittest.skipUnless(compress.HEIF_AVAILABLE, "pillow-heif 未安装")` (`img_compress/test_compress.py:355`)
- `@unittest.skipIf(tk is None, "Tkinter 不可用")` plus `self.skipTest("当前环境没有图形显示")` on `TclError` (`img_compress/test_gui_smoke.py:21, 25-26`)
- Never silently skip without a reason string

**Determinism:**
- Seeded `random.Random(42)` (also 3, 7, 11) for generated pixel noise
- Fixed image dimensions and solid colors for geometric assertions
- Pixel coordinates are derived from documented sizes (e.g. output `(260, 100)` for three images with `--gap 10`)

**Regression / safety assertions:**
- Source bytes unchanged after compression: `self.assertEqual(src.read_bytes(), original)` (`img_compress/test_compress.py:104`)
- Rerunning against a directory does not re-ingest generated output (`test_output_excluded_on_rerun`, `test_recursive_directory_skips_generated_outputs`)
- Unicode and space paths are a first-class case: `"毕业 照片"`, `"长图 01.jpg"`, `"照片 01.jpg"`

**Test runner footer:**
```python
if __name__ == "__main__":
    unittest.main()
```
`snake_game/test_snake.py:123` uses `unittest.main(verbosity=2)`.

## Guidelines for New Tests

- Add tests to the existing `test_<module>.py` in the same project, as a new `<Feature>Tests` class.
- Create fixtures in `setUp` via `tempfile.TemporaryDirectory()`; clean up in `tearDown`.
- Generate real images with Pillow; never mock the file system or image library.
- Use seeded `random.Random(N)` whenever randomness affects output.
- Test behavior (size, format, pixels, exit code, message fragment) not private call sequences.
- Cover Chinese/space paths for any new path-handling code, and batch isolation (one bad file must not abort the rest) for any new batch loop.
- Skip optional-dependency tests with an explicit reason; do not gate the whole suite on optional packages.
- Keep commands in README/docstrings consistent with `python -m unittest`, since no pytest is available.

---

*Testing analysis: 2026-11-11*
