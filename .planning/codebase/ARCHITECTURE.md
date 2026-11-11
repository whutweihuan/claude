---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
<!-- refreshed: 2026-11-11 -->
# Architecture

**Analysis Date:** 2026-11-11

## System Overview

This repository is a collection of three independent, single-purpose Python desktop tools that share a common shape but no shared code. Each tool is a flat directory containing a core module (domain logic + CLI), a thin Tkinter GUI module, and a `unittest` suite. There is no package, no build system, and no cross-tool imports.

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     Repository root (no package)                      │
│                                                                      │
│  ┌────────────────────┐ ┌────────────────────┐ ┌──────────────────┐  │
│  │ image_add/          │ │ img_compress/       │ │ snake_game/      │  │
│  │ 图片拼接             │ │ 图片压缩             │ │ 贪吃蛇            │  │
│  └─────────┬──────────┘ └─────────┬──────────┘ └────────┬─────────┘  │
└────────────┼──────────────────────┼─────────────────────┼────────────┘
             │                      │                     │
             ▼                      ▼                     ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  Tkinter adapter      │ │  Tkinter adapter      │ │  Tkinter adapter     │
│  `stitch_gui.py`      │ │  `compress_gui.py`    │ │  `snake_gui.py`      │
│  (thread + queue)     │ │  (thread + queue)     │ │  (after() game loop) │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │ import                   │ import                   │ import
           ▼                          ▼                          ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  Core + CLI           │ │  Core + CLI           │ │  Pure domain model   │
│  `stitch.py`          │ │  `compress.py`        │ │  `snake.py`          │
│  Pillow imaging       │ │  Pillow + pillow-heif │ │  no UI, rng injected │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                          │                          │
           ▼                          ▼                          ▼
      Output image file          Output image files          Canvas rendering
      (PNG/JPEG/WebP/...)        (per-file `_compressed`)    (in-memory only)
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Stitch CLI + core | Input discovery, natural sorting, EXIF transpose, fit/alignment, canvas compositing, save-format flattening | `image_add/stitch.py` |
| Stitch GUI | File list ordering (up/down), options, background worker, result dialog | `image_add/stitch_gui.py` |
| Stitch launcher | Windows double-click entry using `pythonw` | `image_add/run_gui.bat` |
| Stitch tests | Pixel-level assertions on stitched output and CLI behavior | `image_add/test_stitch.py` |
| Compress CLI + core | Input discovery, compression presets, format conversion, resizing, per-file transactional save, batch aggregation | `img_compress/compress.py` |
| Compress GUI | Treeview file list with size columns, progress bar, queue-driven worker | `img_compress/compress_gui.py` |
| Compress GUI smoke tests | Builds a real `Tk` root, drives `start()`, asserts statuses | `img_compress/test_gui_smoke.py` |
| Compress tests | Eight test classes covering discovery through HEIC and CLI | `img_compress/test_compress.py` |
| Snake domain | Grid game state machine: turn buffering, movement, growth, collision, food spawn | `snake_game/snake.py` |
| Snake GUI | Canvas drawing, keyboard mapping, pause/restart, fixed-rate tick | `snake_game/snake_gui.py` |
| Snake tests | Deterministic game-logic tests via injected `random.Random(42)` | `snake_game/test_snake.py` |

## Pattern Overview

**Overall:** Layered "core module + thin GUI adapter" per tool, in a flat multi-tool repository.

**Key Characteristics:**
- **Domain logic has no UI dependency.** `stitch.py`, `compress.py`, and `snake.py` are importable and testable without Tkinter. The GUI modules import the core module by bare name (`import stitch`, `import compress`, `import snake`).
- **CLI lives beside the domain logic.** `stitch.py` and `compress.py` each own `build_parser()` and `main(argv=None)`, guarded by `if __name__ == "__main__"`. This lets tests call `main()` in-process with captured stdout/stderr.
- **The GUI is a pure adapter.** It collects widget state, builds a kwargs dict, hands it to a core function, and renders returned result objects. No image processing happens in GUI code.
- **Each tool is independently runnable.** You `cd` into the tool directory (or use its `.bat` file, which does `cd /d "%~dp0"`) and run Python there; there are no `__init__.py` files or path configuration.
- **Tests are the integration contract.** `unittest` classes exercise the core functions directly and, for compress, also drive the GUI with a withdrawn root.

## Layers

**Domain / Core layer:**
- Purpose: Image/game operations with no knowledge of widgets or terminals.
- Location: `image_add/stitch.py`, `img_compress/compress.py`, `snake_game/snake.py`
- Contains: Pure functions (`expand_inputs`, `fit_images`, `stitch`, `save_result`, `compress_image`, `compress_files`), data classes (`CompressResult`, `BatchResult`), the `SnakeGame` class, exception types (`ToolError`, `SkipImage`), preset/format constant tables.
- Depends on: Pillow (`image_add`, `img_compress`), optional `pillow_heif`, Python stdlib (`pathlib`, `dataclasses`, `tempfile`, `re`, `random`). `snake.py` depends only on `random`.
- Used by: the matching GUI module, the matching CLI entry point, and tests.

**CLI adapter layer:**
- Purpose: Translate argv into core calls and print human-readable summaries.
- Location: `build_parser()` / `main()` in `image_add/stitch.py:313-412` and `img_compress/compress.py:433-499`.
- Contains: `argparse` definitions, argument validators (`positive_int`, `non_negative_int`, `quality_int`), output formatting (`_format_size`).
- Depends on: the core functions in the same file.
- Used by: `python stitch.py ...`, `python compress.py ...`, and tests that invoke `main(argv)`.

**GUI adapter layer:**
- Purpose: Tkinter view/controller, parameter validation, background execution, result presentation.
- Location: `image_add/stitch_gui.py`, `img_compress/compress_gui.py`, `snake_game/snake_gui.py`
- Contains: an `*App` class per tool (`StitchApp`, `CompressApp`, `SnakeApp`), `_build_ui()`, list manipulation methods, `start()`/`_worker()`/`_poll()` for the image tools, `_tick()` for snake.
- Depends on: the core module and `tkinter`, plus `threading`/`queue` for the image tools.
- Used by: `run_gui.bat` / `run_snake.bat`, or direct `python <tool>_gui.py`.

**Test layer:**
- Purpose: Verify core behavior and (for compress) GUI wiring.
- Location: `image_add/test_stitch.py`, `img_compress/test_compress.py`, `img_compress/test_gui_smoke.py`, `snake_game/test_snake.py`
- Contains: `unittest.TestCase` classes, temp-directory fixtures, Pillow-based image factories, mocked dialogs.
- Depends on: the core/GUI modules in the same directory.
- Used by: developers via `python -m unittest`, not by production code.

## Data Flow

### Compress: CLI request path

1. `main()` parses args and rejects non-positive `--max-size` (`img_compress/compress.py:452-456`).
2. `compress_files()` expands each input path into files, collecting per-input `ToolError`s instead of aborting (`img_compress/compress.py:371-397`).
3. `expand_inputs()` filters by extension, skips generated `_compressed` files, natural-sorts directory contents, then dedupes by normalized absolute path (`img_compress/compress.py:121-141`).
4. For each file, `compress_image()` opens with Pillow, rejects multi-frame animations with `SkipImage`, resolves source format, applies EXIF transpose, and optionally resizes (`img_compress/compress.py:280-321`).
5. `_save_image()` selects encoder parameters per preset and target format (`img_compress/compress.py:236-277`).
6. Output is written to a `tempfile.mkstemp` file in the output directory and atomically promoted with `os.replace` (`img_compress/compress.py:329-341`).
7. If same-format, not resized, and output is not smaller, the processed file is deleted and the original copied instead (`kept_original=True`) (`img_compress/compress.py:343-354`).
8. Batch totals and failure/skip lists are returned as `BatchResult`; `main()` prints a per-file list plus a summary and returns 0 if any file succeeded (`img_compress/compress.py:471-495`).

### Compress: GUI request path

1. `CompressApp.start()` validates images/output/max-edge, resets Treeview statuses, disables the button, sets progress maximum (`img_compress/compress_gui.py:243-289`).
2. A daemon thread runs `_worker()`, which calls `compress.compress_files(..., progress=callback)` (`img_compress/compress_gui.py:288-301`).
3. The progress callback pushes `("progress", done, total, source)` tuples onto a `queue.Queue`; completion pushes `("done", summary)` or `("error", message)`.
4. The Tk main thread polls with `root.after(100, self._poll)` and drains the queue with `get_nowait()`, updating the progress bar, status label, and row status (`img_compress/compress_gui.py:303-327`).
5. `_finish()` maps `summary.results`/`skipped`/`failures` back to Treeview items via normalized path keys and shows a summary dialog (`img_compress/compress_gui.py:329-388`).

### Stitch: GUI request path

1. User-ordered `self.files` list is the source of truth; the Listbox mirrors it (`image_add/stitch_gui.py:168-203`).
2. `start()` validates gap/quality/output/background, confirms overwrite, then spawns a daemon worker (`image_add/stitch_gui.py:222-273`).
3. `_worker()` calls `stitch.stitch_to_file(**params)` and queues `("ok", message, skipped)` or `("error", message, 0)` (`image_add/stitch_gui.py:276-286`).
4. `_poll()` either drains one message or reschedules itself every 100 ms while the queue is empty (`image_add/stitch_gui.py:288-306`).

### Stitch: core pipeline

1. `expand_inputs()` handles files, directories, and glob patterns, natural-sorting matches (`image_add/stitch.py:60-101`).
2. `apply_sort()` optionally reorders by name or mtime and reverses (`image_add/stitch.py:104-111`).
3. `load_images()` applies EXIF transpose, forces RGBA, and skips unreadable files with a warning (`image_add/stitch.py:114-126`).
4. `fit_images()` scales the cross-axis to max/first size when requested (`image_add/stitch.py:146-176`).
5. `stitch()` computes canvas dimensions, fills background, and pastes each image with start/center/end alignment (`image_add/stitch.py:179-211`).
6. `limit_size()` downsamples if the long edge exceeds `--max-size` (`image_add/stitch.py:254-263`).
7. `save_result()` flattens transparency to the background color for JPEG/BMP and saves with format-specific options (`image_add/stitch.py:214-251`).

### Snake: game loop

1. `SnakeApp.__init__` creates `SnakeGame(20, 20)`, binds `<KeyPress>`, draws board and "press arrow to start" overlay (`snake_game/snake_gui.py:41-58`).
2. First direction key calls `game.turn(dir)`, transitions `ready -> running`, and schedules `_tick` with `root.after(SPEED_MS, ...)` at 125 ms (`snake_game/snake_gui.py:158-180`).
3. Each tick calls `game.step()`, redraws the whole canvas, updates score, and checks `game_over` (`snake_game/snake_gui.py:140-154`).
4. Space toggles `running`/`paused` by cancelling or re-scheduling the `after` handle; `R` resets after game over (`snake_game/snake_gui.py:182-202`).
5. `SnakeGame.step()` consumes one buffered turn, computes the new head, checks wall/self collision, grows or pops the tail, and respawns food from free cells (`snake_game/snake.py:71-111`).

**State Management:**
- GUI state lives in the `*App` instances (`files`, `busy`, `queue`, Tk variables).
- Game state lives entirely in `SnakeGame` (`body`, `direction`, `_pending`, `score`, `food`, `game_over`); the GUI keeps a parallel `state` string (`ready/running/paused/over`).
- Image tools are stateless per operation; results are returned as dataclasses rather than stored globally.

## Key Abstractions

**`ToolError` / `SkipImage`:**
- Purpose: Distinguish user-facing failures from skippable inputs.
- Examples: `image_add/stitch.py:42-44`, `img_compress/compress.py:61-67`
- Pattern: Raised by core, caught at CLI/GUI boundary; `SkipImage` is collected into `BatchResult.skipped` and does not fail the batch.

**`CompressResult` / `BatchResult`:**
- Purpose: Typed result records decoupling core from presentation.
- Examples: `img_compress/compress.py:69-90`
- Pattern: `@dataclass` with source/output paths, byte sizes, formats, dimensions, `kept_original`, `note`; batch totals are summed by the core.

**Preset tables (`LEVELS`, `FORMAT_BY_EXT`, `EXT_BY_FORMAT`, `OUTPUT_FORMAT_MAP`):**
- Purpose: Data-driven compression and format mapping.
- Examples: `img_compress/compress.py:30-58`, `image_add/stitch.py:29-39`
- Pattern: Module-level constant dicts; encoder branch in `_save_image()` reads a preset and target format.

**`natural_key()`:**
- Purpose: Human-friendly ordering so `1.jpg < 2.jpg < 10.jpg`.
- Examples: `image_add/stitch.py:50-53`, `img_compress/compress.py:96-99` (duplicated by design; no shared lib)
- Pattern: `re.split(r"(\d+)", ...)` producing int/str parts.

**`unique_output_path()`:**
- Purpose: Never overwrite an existing file or the source.
- Examples: `img_compress/compress.py:152-160`
- Pattern: `stem + "_compressed"` plus `_1`, `_2`, ... until a free name is found.

**Progress callback:**
- Purpose: Let the GUI observe batch progress without importing the GUI.
- Examples: `img_compress/compress.py:371-408` (`progress(index, total, source)`), invoked from `compress_gui.py:291-300`
- Pattern: Optional callable injected into core; GUI implementation writes to a queue.

**Queue message tuples:**
- Purpose: Thread-safe handoff from worker thread to Tk main thread.
- Examples: `img_compress/compress_gui.py:291-301`, `image_add/stitch_gui.py:276-286`
- Pattern: `(kind, payload...)` tuples drained by `_poll()`.

## Entry Points

**Stitch CLI:**
- Location: `image_add/stitch.py:373-412`
- Triggers: `python stitch.py <inputs> [options]`
- Responsibilities: Parse args, normalize direction aliases, exclude a pre-existing output file from inputs, sort, call `stitch_to_file()`, print result, map `ToolError` to exit 1.

**Stitch GUI:**
- Location: `image_add/stitch_gui.py:309-319`, launched via `image_add/run_gui.bat`
- Triggers: `python stitch_gui.py` or double-click `run_gui.bat`
- Responsibilities: Create `Tk` root, apply `vista` theme if available, run `StitchApp`.

**Compress CLI:**
- Location: `img_compress/compress.py:452-499`
- Triggers: `python compress.py <inputs> [options]`
- Responsibilities: Parse args, run `compress_files()`, print per-file and summary lines, exit 0 if at least one success.

**Compress GUI:**
- Location: `img_compress/compress_gui.py:391-401`, launched via `img_compress/run_gui.bat`
- Triggers: `python compress_gui.py` or double-click `run_gui.bat`
- Responsibilities: Create `Tk` root, apply `vista` theme, run `CompressApp`; also constructible in tests via `CompressApp(root)`.

**Snake GUI:**
- Location: `snake_game/snake_gui.py:209-216`, launched via `snake_game/run_snake.bat`
- Triggers: `python snake_gui.py` or double-click `run_snake.bat`
- Responsibilities: Create `Tk` root and run `SnakeApp`; no CLI variant (domain module is import-only).

## Architectural Constraints

- **Threading:** Tk widgets are touched only from the main thread. `compress_gui` and `stitch_gui` run core work in a `threading.Thread(daemon=True)` and communicate through `queue.Queue`. `snake_gui` is single-threaded, driven by `root.after()`.
- **Global state:** Module-level constants only (`LEVELS`, format maps, `SUPPORTED_EXTS`, snake direction tuples). `HEIF_AVAILABLE` is a module-level capability flag set at import in `img_compress/compress.py:16-22`; `register_heif_opener()` is a global Pillow side effect.
- **Import path coupling:** GUI modules import their core by bare module name (`import compress`, `import stitch`, `import snake`), so they must be launched with the tool directory as the working directory. The `.bat` files enforce this with `cd /d "%~dp0"`. Running from repo root (e.g. `python img_compress/compress_gui.py`) fails to resolve `compress`.
- **No shared library:** Identical helpers (`natural_key`, `_format_size`, input expansion) are duplicated across tools. There is no `__init__.py`, `setup.py`, or `pyproject.toml`, and no tool imports from a sibling.
- **Atomic image writes:** `compress.py` writes to a temp file and `os.replace`s it; `stitch.py` writes directly to the target path.
- **Image size limits are application-level only;** no streaming or chunked processing — all images are loaded fully into memory.
- **Python version:** READMEs state Python 3.8+; code uses dataclasses, f-string-free `%` formatting, and `Image.Resampling` (Pillow >= 9.1).
- **Platform:** Windows-first (`.bat` + `pythonw`, `os.path.normcase`, `vista` theme preference), but `pathlib` keeps the core cross-platform.

## Anti-Patterns

### Duplicated helpers across tools

**What happens:** `natural_key()`, `_format_size()`, path dedupe, and input expansion are reimplemented in each tool (`image_add/stitch.py:50-53`, `img_compress/compress.py:96-99`; `_format_size` in both `img_compress/compress.py:423-431` and `img_compress/compress_gui.py:32-39`).
**Why it's wrong:** Fixes must be applied in multiple places and behavior can drift; `compress.py` and `compress_gui.py` already carry byte-identical copies of `_format_size`.
**Do this instead:** When touching a helper, update every copy; if a fourth tool appears, extract a shared `common/` module and add it to each tool's import path (currently none exists).

### GUI importing core by bare module name

**What happens:** `compress_gui.py`, `stitch_gui.py`, and `snake_gui.py` assume the process CWD is the tool directory.
**Why it's wrong:** Launching `python img_compress/compress_gui.py` from the repo root raises `ModuleNotFoundError: compress`, and tests only pass when run from inside the tool directory.
**Do this instead:** Either keep the documented `cd`-first / `.bat` launch convention, or package each tool (add `__init__.py` + relative imports) before adding any cross-directory entry point.

### Whole-canvas redraw every snake tick

**What happens:** `SnakeApp._tick()` calls `_draw()`, which deletes all canvas items and recreates grid lines, food, and every snake segment each 125 ms (`snake_game/snake_gui.py:91-115, 140-154`).
**Why it's wrong:** It is simple and correct at 20x20, but O(cells) work per tick and a full flicker-free redraw cost; it will not scale to larger boards or smoother frame rates.
**Do this instead:** For the current 20x20 / 8 fps scope this is acceptable; if the board grows, move to per-item updates (tag snake segments and move/delete individually).

### Broad `except Exception` in loop boundaries

**What happens:** `compress_files()` catches every exception per file (`img_compress/compress.py:409-412`), and both GUIs catch `Exception` in workers (`img_compress/compress_gui.py:300-301`, `image_add/stitch_gui.py:285-286`).
**Why it's wrong:** Real programming errors are reported as per-file failures, hiding bugs behind a "跳过/失败" count.
**Do this instead:** Catch `ToolError`/`SkipImage` explicitly and let unexpected exceptions surface during development; the existing `# noqa: BLE001` comments mark the intentional trade-off.

## Error Handling

**Strategy:** Typed user-facing exceptions at the core boundary, with per-item isolation in batch operations.

**Patterns:**
- Core raises `ToolError` with a human-readable Chinese message; `SkipImage` (subclass) marks non-failures (`img_compress/compress.py:61-67`).
- CLI catches `ToolError` and returns exit code 1; `stitch.py` also catches `KeyboardInterrupt` and exits 130 (`image_add/stitch.py:405-412`).
- GUI workers catch `ToolError` and `Exception`, pushing an error message to the queue and re-enabling the start button (`img_compress/compress_gui.py:298-301`).
- Batch processing isolates failures into `BatchResult.failures` / `.skipped` and continues (`img_compress/compress.py:399-420`).
- Unreadable images in stitch are warned about on stderr and skipped (`image_add/stitch.py:114-126`).
- Missing Pillow is handled at import with `sys.exit` in `stitch.py:24-27`; `compress.py` imports Pillow unguarded and will traceback instead.

## Cross-Cutting Concerns

**Logging:** `print` only. `warn()` writes `"警告: ..."` to stderr in both image tools (`image_add/stitch.py:46-47`, `img_compress/compress.py:92-93`). GUI reports via the status label and `messagebox`. No logging framework or log files.

**Validation:** CLI validates types in argparse (`positive_int`, `non_negative_int`, `quality_int`); GUI validates widget strings before dispatch (`compress_gui.py:255-263`, `stitch_gui.py:229-257`); core re-validates critical values (`max_edge`, unknown level/format) so it is safe to call programmatically.

**Authentication:** None — all tools are local-only, with no network access, no accounts, and no cloud upload (stated explicitly in `img_compress/README.md`).

**Persistence:** None beyond the output image files. No database, config file, or saved user preferences.

---

*Architecture analysis: 2026-11-11*
