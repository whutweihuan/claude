---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
<!-- refreshed: 2026-11-11 -->
# Coding Conventions

**Analysis Date:** 2026-11-11

## Scope

The repository contains three independent, self-contained Python 3.8 desktop tools:

- `img_compress/` - image compression (`compress.py` core/CLI + `compress_gui.py` Tkinter)
- `image_add/` - image stitching (`stitch.py` core/CLI + `stitch_gui.py` Tkinter)
- `snake_game/` - snake game (`snake.py` pure logic + `snake_gui.py` Tkinter)

There is no package hierarchy, no `__init__.py`, no `pyproject.toml`, `setup.cfg`, `.editorconfig`, or linter config. Each directory is executed/tested from inside itself. Conventions below are the de-facto norms to follow when adding code, derived from all source files.

## Naming Patterns

**Files:**
- Modules: `snake_case.py` - `compress.py`, `stitch.py`, `snake.py`
- GUI shells: `<module>_gui.py` - `compress_gui.py`, `stitch_gui.py`, `snake_gui.py`
- Tests: `test_<module>.py` and `test_<feature>.py` - `test_compress.py`, `test_stitch.py`, `test_snake.py`, `test_gui_smoke.py`
- Windows launchers: `run_gui.bat` (image tools), `run_snake.bat`; all `cd /d "%~dp0"` then `start "" pythonw <gui>.py`
- Dependencies: `requirements.txt` (one per project); docs: `README.md`

**Functions:**
- `snake_case` verbs describing the action: `expand_inputs`, `resolve_level`, `compress_image`, `compress_files`, `stitch_to_file`, `limit_size`, `build_parser`, `main`
- Validation/parsing helpers are named for the constraint they enforce: `positive_int`, `non_negative_int`, `quality_int` in `image_add/stitch.py`
- Private helpers use a leading underscore: `_is_generated`, `_dedupe_paths`, `_normalize_format`, `_flatten_alpha`, `_resize_if_needed`, `_quantize_png`, `_save_image`, `_format_size` in `img_compress/compress.py`; `_build_ui`, `_worker`, `_poll`, `_append`, `_update_count` in GUI classes
- Test helpers use `make_*` or `run_*`: `make_noise_jpeg`, `make_alpha_png`, `make_game`, `run_cli`, `run_tool`, `rgb_at`

**Variables:**
- `snake_case`; `path` for a single `Path`, `files` for a list, `summary`/`result` for dataclass results
- Callback parameter is literally `progress` and is called as `progress(index, total, source)` (`img_compress/compress.py`)

**Types/Classes:**
- `PascalCase` nouns: `ToolError`, `SkipImage`, `CompressResult`, `BatchResult`, `CompressApp`, `StitchApp`, `SnakeGame`, `SnakeApp`
- Exceptions always end in `Error`; GUI classes end in `App`; pure logic classes are the domain noun (`SnakeGame`)
- Test classes are `<Feature>Tests`: `ExpandInputsTests`, `CompressImageTests`, `ConvertAndResizeTests`, `TransparencyAndMetadataTests`, `ExtraFormatsTests`, `HeifTests`, `BatchTests`, `CliTests`, `StitchTests`, `SnakeTests`, `GuiSmokeTests`
- Test methods are full behavioral sentences: `test_directory_is_natural_sorted_deduped_and_skips_generated`, `test_moving_into_vacated_tail_cell_is_allowed`, `test_transparent_to_jpeg_flattens_white`

**Constants:**
- Module-level `UPPER_SNAKE_CASE`: `SUPPORTED_EXTS`, `GENERATED_RE`, `LEVELS`, `FORMAT_BY_EXT`, `EXT_BY_FORMAT`, `OUTPUT_FORMAT_MAP`, `SAVEABLE_FORMATS`, `HEIF_AVAILABLE` in `img_compress/compress.py`; `OUTPUT_FORMATS`, `SUPPORTED_EXTS` in `image_add/stitch.py`
- GUI/theme constants are module-level in `snake_game/snake_gui.py`: `GRID`, `CELL`, `BOARD`, `SPEED_MS`, `BG`, `BOARD_BG`, `GRID_LINE`, `SNAKE_BODY`, `SNAKE_HEAD`, `FOOD`, `TEXT`, `MUTED`, `FONT`, `KEYS`
- Label dictionaries map Chinese UI text to internal values: `LEVEL_LABELS`, `FORMAT_LABELS` in `img_compress/compress_gui.py`; `FIT_LABELS`, `ALIGN_LABELS` in `image_add/stitch_gui.py`

## Code Style

**File header (every Python file):**
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片压缩工具核心逻辑与命令行入口。"""
```
Followed by a Chinese module docstring that states purpose and, for scripts, how to run: `"""stitch.py 的自动化测试。运行: python test_stitch.py -v"""` (`image_add/test_stitch.py:3`), `"""贪吃蛇游戏逻辑（与界面无关，可单独测试）。\n\n运行测试: python -m unittest test_snake -v\n启动游戏: python snake_gui.py\n"""` (`snake_game/snake.py:3`).

**Formatting:**
- 4-space indentation, no tabs, two blank lines between top-level definitions, one blank line between methods
- Line length targets PEP 8's 79-88. Core modules are close; GUI layout files exceed it (`image_add/stitch_gui.py` has 15 lines > 88 chars, `img_compress/compress_gui.py` 8). Prefer wrapping long widget calls across lines as in `img_compress/compress_gui.py:111-114`.
- No formatter is configured; do not reformat existing files wholesale.

**Strings:**
- Double quotes are the default for literals; single quotes appear for short keys/markers (`'w'`, `""` empty string)
- Old-style `%` formatting is used everywhere, NOT f-strings (Python 3.8 compatibility): `"无法读取图片 %s: %s" % (source, exc)` (`img_compress/compress.py:305`), `"警告: " + message` for simple concatenation
- All user-facing text, comments, docstrings, and error messages are Simplified Chinese; identifiers and internal format names stay English (`JPEG`, `WEBP`, `HEIF`)

**Comments and sections:**
- Comments explain non-obvious behavior or a library workaround, e.g. `# Pillow 10.4 在 q90 + 4:4:4 + optimize 下会报编码错误；` (`img_compress/compress.py:246-247`) and `# 不增长时，尾巴这一格会在同一步腾出来，可以进入` (`snake_game/snake.py:89`)
- Long classes are divided by section comments:
  - `# ---------- 界面 ----------`, `# ---------- 列表操作 ----------`, `# ---------- 压缩 ----------` (`img_compress/compress_gui.py`)
  - `# ----- 状态管理 -----`, `# ----- 操作 -----`, `# ----- 内部 -----` (`snake_game/snake.py`)
  - `# ----- 初始状态 -----`, `# ----- 碰撞 -----` in tests (`snake_game/test_snake.py`)
- Docstrings are one-line Chinese summaries for non-trivial functions: `"""展开文件和目录，返回去重后的图片路径，保持输入或自然排序。"""` (`img_compress/compress.py:122`)

## Import Organization

**Order:**
1. Shebang + coding comment + module docstring
2. Standard library, alphabetical: `argparse`, `contextlib`, `dataclasses`, `io`, `os`, `queue`, `random`, `re`, `shutil`, `sys`, `tempfile`, `threading`, `tkinter`, `unittest`, `pathlib.Path`, `unittest.mock`
3. Third-party: `from PIL import Image, ImageOps` / `ImageCms`
4. Local sibling module imported by bare name: `import compress`, `import stitch`, `import snake`, `import compress_gui`

**Patterns:**
- `from pathlib import Path` is preferred for path construction; `os.path.normcase` is used only for case-insensitive keys (`_path_key`, `_dedupe_paths`)
- `glob` is aliased as `globmod` (`import glob as globmod`, `image_add/stitch.py:18`) to avoid clashing with variable names
- Optional dependencies use guarded import and a module-level capability flag:
```python
HEIF_AVAILABLE = False
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    pass
```
(`img_compress/compress.py:16-22`)
- Missing required Pillow in `image_add/stitch.py` exits with an install hint: `sys.exit("缺少 Pillow 库，请先执行: python -m pip install Pillow")`
- Tkinter in tests is guarded with `try: import tkinter as tk / except ImportError: tk = None` (`img_compress/test_gui_smoke.py:11-14`)

**No path aliases or package-relative imports:** tests rely on being run from the project directory (`import compress` resolves because cwd is `img_compress/`). Do not introduce packages without updating run instructions.

## Error Handling

**Domain exception hierarchy:**
- `class ToolError(Exception): """可读的用户错误。"""` in both `img_compress/compress.py:61` and `image_add/stitch.py:42`
- `class SkipImage(ToolError): """可以跳过而不算失败的图片。"""` in `img_compress/compress.py:65`
- Raise `ToolError` with actionable Chinese text, including alternatives: `"未知压缩档位: %r（可用: light/standard/strong/extreme）" % level` (`img_compress/compress.py:148`)

**CLI boundary:**
- `main()` catches `ToolError`, prints `"错误: " + str(exc)` to `sys.stderr`, returns exit code `1`
- Argparse validation failures use `parser.error(...)` (exit code 2) or `argparse.ArgumentTypeError` validators
- Success codes: `compress.py` returns `0` if any results, else `1`; `stitch.py` returns `0`; `KeyboardInterrupt` returns `130` (`image_add/stitch.py:411-412`)
- Do not let raw exceptions escape to the terminal; wrap library errors: `raise ToolError("无法读取图片 %s: %s" % (source, exc))` (`img_compress/compress.py:304-305`)

**Batch/partial-failure policy:**
- One bad input must never abort a batch. Per-item loops catch and record: `except Exception as exc:  # noqa: BLE001 - 单张失败不影响整体` (`img_compress/compress.py:411`, `image_add/stitch.py:124`)
- `SkipImage` goes to `skipped`, other exceptions go to `failures`, successes to `results`
- GUI workers catch `ToolError` separately from `Exception` and push `("error", message)` onto the queue (`img_compress/compress_gui.py:295-301`)

**File safety:**
- Never overwrite the source. Output name is `<stem>_compressed<ext>` with `_1`, `_2` collision suffix (`unique_output_path`, `img_compress/compress.py:152-160`)
- Atomic writes: `tempfile.mkstemp(prefix=".compress_", suffix=".tmp", dir=...)` then `os.replace`; clean up temp file on failure (`img_compress/compress.py:330-341`)
- Directory scanning excludes previously generated files via `GENERATED_RE` (`_compressed` suffix)
- Recovery rule: when same format, no resize, and output is not smaller, copy the original instead and set `kept_original=True`/`note` (`img_compress/compress.py:346-354`)

**GUI error reporting:**
- Validation errors: `messagebox.showerror("参数错误", "...")` and return early
- Missing preconditions: `messagebox.showinfo("提示", "...")`
- Save overwrite confirmation: `messagebox.askyesno("确认覆盖", ...)` (`image_add/stitch_gui.py:250-252`)
- Background-thread errors are never raised on the Tk thread; they are queued and shown by the polling method

## Logging / Output

- No logging framework and no log files. Use `print`.
- Results to stdout; warnings and failures to stderr with fixed prefixes:
  - `"完成: ..."`, `"跳过: ..."`, `"失败: ..."`, `"错误: ..."`, `"警告: ..."`
- Central helper `warn(message)` prints `"警告: " + message` to `sys.stderr` (`img_compress/compress.py:92`, `image_add/stitch.py:46`)
- Human-readable size formatting through `_format_size(size)` (`img_compress/compress.py:423`) with units `B/KB/MB/GB`; GUI duplicates this helper locally (`img_compress/compress_gui.py:32`)

## Function Design

- Core functions are pure where possible and take/return plain data; results use `@dataclass` records (`CompressResult`, `BatchResult` with fields `source`, `output`, `original_size`, `output_size`, `source_format`, `output_format`, `width`, `height`, `kept_original`, `note`).
- Long batch operations accept an optional `progress` callback instead of importing UI concerns (`compress_files(..., progress=None)`).
- Keep GUI code free of image processing; call into `compress.py` / `stitch.py` / `snake.py` only.
- Public functions get short Chinese docstrings; private helpers may omit them.
- Argument parsing is isolated in `build_parser()` so `main(argv=None)` is testable in-process.
- Every script ends with:
```python
if __name__ == "__main__":
    sys.exit(main())
```

## GUI Conventions (Tkinter)

- One top-level class per GUI: `CompressApp`, `StitchApp`, `SnakeApp`, constructed with `root` and owning all widgets/state
- `_build_ui()` builds layout; private `_toggle_*` handlers enable/disable dependent widgets
- Long-running work runs in `threading.Thread(target=self._worker, args=(params,), daemon=True)`; UI updates are delivered through `queue.Queue` and polled with `self.root.after(100, self._poll)` (`img_compress/compress_gui.py:288-327`)
- Worker never touches Tk widgets; it only enqueues messages
- Busy flag (`self.busy`) prevents concurrent starts; start button is disabled during work
- `main()` applies the Windows `vista` theme when available: `if "vista" in style.theme_names(): style.theme_use("vista")`
- Standard widgets: `ttk.Frame`, `ttk.LabelFrame`, `ttk.Treeview` (compress), `tk.Listbox` (stitch), `tk.Canvas` (snake); paddings are 6/8/10/12/18, `padding=12` outer frame

## Module Design

- Three parallel self-contained projects, each with core logic, GUI, tests, README, requirements. Do not share code across projects; duplication (e.g. `_format_size`, `natural_key`) is intentional to keep each folder runnable standalone.
- Public API of each core module is imported directly (`compress.compress_files`, `stitch.stitch_to_file`, `snake.SnakeGame`); there are no barrel files.
- GUI modules are thin and import the sibling core module by bare name.

## Language and Encoding

- UTF-8 everywhere, declared with `# -*- coding: utf-8 -*-`; Chinese text is stored directly (no escape sequences).
- Windows launchers use `pythonw` to avoid a console window; `cd /d "%~dp0"` makes them cwd-independent.
- README files are Chinese Markdown, documenting install, GUI steps, CLI flags as tables, tier tables, and limitations.

## What to Avoid

- Do not use f-strings if Python 3.8 support is to be preserved; use `%` formatting.
- Do not introduce pytest fixtures or packages without updating the documented commands (`python -m unittest`).
- Do not write English user-facing messages; UI, CLI, errors, and docs are Chinese.
- Do not overwrite source images or write outputs non-atomically.
- Do not raise raw third-party exceptions across the CLI/GUI boundary; convert to `ToolError`.
- Do not add shared utility modules across the three projects; keep each directory standalone.

---

*Convention analysis: 2026-11-11*
