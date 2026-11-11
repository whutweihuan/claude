---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
# Codebase Structure

**Analysis Date:** 2026-11-11

## Directory Layout

```text
claude/
├── CLAUDE.md                  # Project instructions (superpowers-zh skill framework rules)
├── .claude/                   # Claude Code tooling: agents, commands, skills, hooks, GSD core
│   ├── skills/                # 22 installed skills, one dir each with SKILL.md
│   ├── agents/                # GSD subagent definitions
│   ├── commands/              # GSD slash commands
│   ├── gsd-core/              # GSD framework implementation
│   ├── hooks/                 # Tool hooks
│   └── settings.local.json    # Local harness settings (untracked)
├── .agents/skills/            # Agent-level skills (cost-mode)
├── .planning/                 # GSD planning artifacts (this document lives here)
│   └── codebase/              # Codebase map documents
├── image_add/                 # Tool 1: 图片拼接 (image stitching)
│   ├── stitch.py              # Core imaging logic + CLI (412 lines)
│   ├── stitch_gui.py          # Tkinter GUI (319 lines)
│   ├── test_stitch.py         # unittest suite (190 lines)
│   ├── run_gui.bat            # Windows launcher (pythonw)
│   ├── requirements.txt       # Pillow>=9.1
│   ├── README.md              # Chinese user/CLI documentation
│   └── skills-lock.json       # Skill lockfile (cost-mode)
├── img_compress/              # Tool 2: 图片压缩 (image compression)
│   ├── compress.py            # Core compression logic + CLI (499 lines)
│   ├── compress_gui.py        # Tkinter GUI (401 lines)
│   ├── test_compress.py       # unittest suite, 8 classes (501 lines)
│   ├── test_gui_smoke.py      # GUI smoke tests (81 lines)
│   ├── run_gui.bat            # Windows launcher (pythonw)
│   ├── requirements.txt       # Pillow>=10.4, pillow-heif>=0.18
│   ├── README.md              # Chinese user/CLI documentation
│   └── docs/superpowers/      # Design spec + implementation plan (committed)
│       ├── specs/2026-11-10-image-compressor-design.md
│       └── plans/2026-11-10-image-compressor.md
├── snake_game/                # Tool 3: 贪吃蛇 (snake game)
│   ├── snake.py               # Pure domain model (111 lines)
│   ├── snake_gui.py           # Tkinter canvas GUI (216 lines)
│   ├── test_snake.py          # unittest suite (123 lines)
│   └── run_snake.bat          # Windows launcher (pythonw)
├── __pycache__/               # Stray compiled test artifact at repo root
└── (no .gitignore, no pyproject.toml, no setup.py, no CI config)
```

## Directory Purposes

**`image_add/`:**
- Purpose: Self-contained image stitching tool (horizontal/vertical long-image composition).
- Contains: One core module with CLI, one GUI module, one test module, requirements, launcher, README.
- Key files: `image_add/stitch.py`, `image_add/stitch_gui.py`, `image_add/test_stitch.py`.

**`img_compress/`:**
- Purpose: Self-contained image compression tool with four presets, format conversion, and batch processing.
- Contains: Core+CLI, GUI, two test modules, requirements, launcher, README, and committed design artifacts.
- Key files: `img_compress/compress.py`, `img_compress/compress_gui.py`, `img_compress/test_compress.py`, `img_compress/test_gui_smoke.py`.

**`img_compress/docs/superpowers/`:**
- Purpose: Preserved design and implementation-plan documents for the compressor.
- Contains: `specs/` design contract and `plans/` task-by-task implementation plan.
- Key files: `img_compress/docs/superpowers/specs/2026-11-10-image-compressor-design.md`, `img_compress/docs/superpowers/plans/2026-11-10-image-compressor.md`.

**`snake_game/`:**
- Purpose: Self-contained Tkinter snake game with UI-independent domain logic.
- Contains: Domain module, GUI module, test module, launcher (no README, no requirements — stdlib only).
- Key files: `snake_game/snake.py`, `snake_game/snake_gui.py`, `snake_game/test_snake.py`.

**`.claude/`:**
- Purpose: Claude Code / GSD framework installation and project skills.
- Contains: `skills/` (22 skill directories), `agents/`, `commands/`, `gsd-core/`, `hooks/`, `scripts/`, settings files, install-state and manifest JSON.
- Key files: `CLAUDE.md` (repo root) documents the skill rules; `.claude/skills/<name>/SKILL.md` per skill.

**`.planning/`:**
- Purpose: GSD planning state and codebase map.
- Contains: `codebase/` documents (this file, `ARCHITECTURE.md`); future phases/plans land here.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

## Key File Locations

**Entry Points:**
- `image_add/stitch.py`: CLI entry `main()` at line 373; module guard at line 405.
- `image_add/stitch_gui.py`: GUI `main()` at line 309.
- `img_compress/compress.py`: CLI entry `main()` at line 452.
- `img_compress/compress_gui.py`: GUI `main()` at line 391.
- `snake_game/snake_gui.py`: GUI `main()` at line 209.
- `image_add/run_gui.bat`, `img_compress/run_gui.bat`, `snake_game/run_snake.bat`: Windows `pythonw` launchers that `cd` into their own directory first.

**Configuration:**
- `img_compress/requirements.txt`: `Pillow>=10.4`, `pillow-heif>=0.18`.
- `image_add/requirements.txt`: `Pillow>=9.1`.
- `snake_game/`: no requirements file (stdlib `tkinter` + `random` only).
- No project-wide config: no `pyproject.toml`, `setup.py`, `setup.cfg`, `tox.ini`, `pytest.ini`, linter, or formatter config.
- No `.gitignore`, so `__pycache__/` directories and `.pyc` files appear in git status.

**Core Logic:**
- `image_add/stitch.py`: `expand_inputs` (60), `load_images` (114), `fit_images` (146), `stitch` (179), `save_result` (214), `stitch_to_file` (266).
- `img_compress/compress.py`: `LEVELS` presets (30), `expand_inputs` (121), `unique_output_path` (152), `_save_image` (236), `compress_image` (280), `compress_files` (371).
- `snake_game/snake.py`: `SnakeGame` (19), `turn` (58), `step` (71), `_spawn_food` (103).

**GUI Logic:**
- `img_compress/compress_gui.py`: `CompressApp._build_ui` (58), `start` (243), `_worker` (291), `_poll` (303), `_finish` (329).
- `image_add/stitch_gui.py`: `StitchApp._build_ui` (53), `start` (222), `_worker` (276), `_poll` (288).
- `snake_game/snake_gui.py`: `SnakeApp._build_ui` (62), `_draw` (91), `_tick` (140), `_on_key` (158).

**Testing:**
- `image_add/test_stitch.py`: `StitchTests` (line 30) — pixel assertions plus in-process CLI calls via `run_tool()`.
- `img_compress/test_compress.py`: `ExpandInputsTests` (18), `CompressImageTests` (55), `ConvertAndResizeTests` (127), `TransparencyAndMetadataTests` (206), `ExtraFormatsTests` (308), `HeifTests` (346), `BatchTests` (380), `CliTests` (446).
- `img_compress/test_gui_smoke.py`: `GuiSmokeTests` (20) — real `Tk` root (withdrawn), mocked `messagebox`, polling `busy` flag.
- `snake_game/test_snake.py`: `SnakeTests` (11) — deterministic `random.Random(42)` injection.

## Naming Conventions

**Files:**
- Core modules: `<noun>.py` with no prefix — `stitch.py`, `compress.py`, `snake.py`.
- GUI companions: `<core>_gui.py` — `stitch_gui.py`, `compress_gui.py`, `snake_gui.py`.
- Tests: `test_<core>.py` — `test_stitch.py`, `test_compress.py`, `test_snake.py`; GUI tests use `test_gui_smoke.py`.
- Launchers: `run_gui.bat` for image tools, `run_snake.bat` for the game.
- Docs: `README.md`; dated design artifacts follow `YYYY-MM-DD-<topic>-<kind>.md` under `docs/superpowers/{specs,plans}/`.

**Directories:**
- Tools are top-level directories. Naming is inconsistent: two are `<domain>_<verb>` English (`image_add`, `img_compress`) and one is `<domain>_game` (`snake_game`); `image_add` vs `img_compress` also differ in abbreviation style.
- Tool-internal docs use the nested `docs/superpowers/specs|plans/` convention.

**Functions:**
- `snake_case` throughout. Private helpers are underscore-prefixed (`_is_generated`, `_dedupe_paths`, `_normalize_format`, `_has_transparency`, `_to_rgba`, `_flatten_alpha`, `_resize_if_needed`, `_quantize_png`, `_palette_transparency_index`, `_save_image`, `_format_size`, `_worker`, `_poll`, `_finish`, `_build_ui`, `_append`, `_update_count`, `_path_key`, `_toggle_bg`, `_toggle_max_edge`, `_draw`, `_overlay`, `_tick`, `_schedule`, `_cancel`, `_on_key`, `_toggle_pause`, `_restart`, `_on_close`, `_center_window`, `_update_score`).
- GUI event handlers are named after the user action without an `on_` prefix (`add_files`, `add_folder`, `remove_selected`, `move_selected`, `clear_all`, `browse_output`, `start`).
- CLI `main(argv=None)` accepts an argv list so tests can call it in-process.

**Variables:**
- `snake_case`; Tk variables use the `*_var` suffix (`level_var`, `format_var`, `output_var`, `max_edge_var`, `limit_var`, `transparent_var`, `status_var`, `count_var`, `score_var`).
- Tk widget attributes are plain nouns (`tree`, `listbox`, `canvas`, `progress`, `start_btn`, `bg_entry`, `max_edge_spin`).
- Module constants are `UPPER_SNAKE_CASE` (`SUPPORTED_EXTS`, `OUTPUT_FORMATS`, `LEVELS`, `FORMAT_BY_EXT`, `EXT_BY_FORMAT`, `OUTPUT_FORMAT_MAP`, `SAVEABLE_FORMATS`, `GENERATED_RE`, `HEIF_AVAILABLE`, `SPEED_MS`, `GRID`, `CELL`, `UP`, `DOWN`, `LEFT`, `RIGHT`).

**Types:**
- Classes use `PascalCase` (`ToolError`, `SkipImage`, `CompressResult`, `BatchResult`, `SnakeGame`, `StitchApp`, `CompressApp`, `SnakeApp`).
- Test classes use `PascalCase` ending in `Tests` (`StitchTests`, `CompressImageTests`, `GuiSmokeTests`, `SnakeTests`).
- Result types are `@dataclass` field declarations without type annotations in `CompressResult`/`BatchResult` (`source: Path`, `results: list`, etc.).

## Where to Add New Code

**New Feature in an Existing Tool:**
- Primary code: the tool's core module — `image_add/stitch.py` or `img_compress/compress.py` for processing behavior; `snake_game/snake.py` for game rules.
- Tests: the matching `test_*.py` in the same directory, using a `tempfile.TemporaryDirectory()` fixture and Pillow-generated images (see `img_compress/test_compress.py:55-72`).
- GUI wiring (if user-facing): the matching `*_gui.py` — collect widget state in `start()`, pass a kwargs dict to the core function, render returned dataclasses in `_finish()`. Keep all image logic out of the GUI module.

**New CLI Option:**
- Add an `argparse` argument in `build_parser()` (`image_add/stitch.py:313`, `img_compress/compress.py:433`), thread it through `main()` into the core function as a keyword argument with a default, then document it in the tool's `README.md` parameter table.

**New Image Format:**
- Add the extension to `SUPPORTED_EXTS` and the extension/format maps (`FORMAT_BY_EXT`, `EXT_BY_FORMAT`, and `SUPPORTED_EXTS` in `img_compress/compress.py:24-58`; `SUPPORTED_EXTS`/`OUTPUT_FORMATS` in `image_add/stitch.py:29-39`).
- Add a branch in `_save_image()` (`img_compress/compress.py:236`) or `save_result()` (`image_add/stitch.py:214`).
- Add a test class in `test_compress.py` (follow `ExtraFormatsTests`, line 308).

**New Tool:**
- Create a new top-level directory `<tool_name>/` containing `<core>.py`, `<core>_gui.py`, `test_<core>.py`, `run_gui.bat`, `requirements.txt` (if third-party deps), and `README.md`.
- Follow the existing split: core owns argparse and domain logic; GUI imports the core by bare name and must be launched from inside the directory.
- If functionality is shared across tools, a `common/` package does not exist yet — either duplicate the helper following current practice or introduce a shared package and update every launcher (`cd` behavior / `PYTHONPATH`) accordingly.

**Utilities:**
- Shared helpers today are duplicated per tool. Put new generic helpers in the core module that needs them (`natural_key` and `_format_size` patterns). Do not create cross-tool imports from a GUI module.

**New Documentation:**
- User/CLI documentation goes in the tool's `README.md` (Chinese). Design contracts go to `<tool>/docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`; implementation plans go to `<tool>/docs/superpowers/plans/YYYY-MM-DD-<topic>.md`, matching `img_compress`.

## Special Directories

**`__pycache__/`:**
- Purpose: CPython bytecode caches generated on import/test runs.
- Generated: Yes.
- Committed: Some `.pyc` files are tracked historically (e.g. `img_add/__pycache__/stitch.cpython-38.pyc` appears in git status as deleted); there is no `.gitignore` to exclude them. New caches should not be committed.

**`.claude/`:**
- Purpose: Claude Code + GSD framework installation (skills, agents, commands, hooks, core scripts).
- Generated: Partly (install manifest, migration journal, install state); `skills/`, `agents/`, `commands/`, `gsd-core/` are the installed framework.
- Committed: Mix — `.claude/settings.local.json`, `.gsd-profile`, install-state and migration-journal files are untracked; several framework dirs are currently untracked on this branch.

**`.agents/skills/`:**
- Purpose: Agent-level skill installation (`cost-mode`), mirrored from `.claude/skills/`.
- Generated: Yes (installed by skill tooling).
- Committed: Currently untracked.

**`.planning/`:**
- Purpose: GSD planning artifacts, including this codebase map.
- Generated: Yes (by GSD commands).
- Committed: Reported untracked by `git status`; intended to be versioned with the project.

**`img_compress/docs/superpowers/`:**
- Purpose: Architecture/design records for the compressor.
- Generated: No (hand-authored).
- Committed: Yes.

**`image_add/skills-lock.json`:**
- Purpose: Hash-pinned lockfile for installed skills used in that tool directory.
- Generated: Yes.
- Committed: Present in the working tree, currently untracked alongside the directory.

---

*Structure analysis: 2026-11-11*
