---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
# Technology Stack

**Analysis Date:** 2026-11-11

## Repository Composition

This repository is a Claude Code workspace containing three independent, locally-run Python desktop tools plus an installed AI-agent tooling layer. There is no shared application, server, or build pipeline.

| Area | Location | Purpose |
|------|----------|---------|
| Image stitcher | `image_add/` | Stitch multiple images horizontally/vertically (GUI + CLI) |
| Image compressor | `img_compress/` | Batch photo compression with presets (GUI + CLI) |
| Snake game | `snake_game/` | Tkinter desktop game with testable core logic |
| AI agent tooling | `.claude/`, `.agents/` | GSD framework, superpowers skills, Claude Code hooks |
| Planning | `.planning/` | Codebase analysis docs (this directory) |

## Languages

**Primary:**
- Python 3.8.3 - All three applications. Verified with `python --version` and by committed `*.cpython-38.pyc` bytecode.

**Secondary:**
- JavaScript (CommonJS) - Claude Code / GSD hooks and scripts in `.claude/hooks/`, `.claude/scripts/`, `.claude/gsd-core/bin/`. Runs on Node.js v26.13.0 (verified).
- Bash - Hook helper scripts (`.claude/hooks/*.sh`, `.claude/skills/*/scripts/*.sh`).
- Windows Batch - Application launchers: `image_add/run_gui.bat`, `img_compress/run_gui.bat`, `snake_game/run_snake.bat`.
- Markdown - Skills, commands, design docs, READMEs.

## Runtime

**Environment:**
- CPython 3.8.3 on Windows 10/11 (x64). Applications target "Python 3.8+" per READMEs and design docs.
- Tk 8.6 (verified) for all GUI front ends. Bundled with the Windows Python installer.
- Node.js v26.13.0 - tooling layer only, not used by the Python applications.

**Package Manager:**
- pip with per-app `requirements.txt`. No lockfile, no virtualenv, no `pyproject.toml`, no `setup.py`, no project root `package.json`.
- Dependencies are installed system-wide (verified: Pillow 10.4.0, pillow-heif 0.18.0 present in the active interpreter).

## Frameworks

**Core:**
- Python standard library only - `argparse` (CLI), `tkinter`/`ttk` (GUI), `threading` + `queue` (background workers), `pathlib`, `unittest`. No web framework, no ORM, no async framework.
- Pillow 10.4.0 - All image decode/encode/transform work in `image_add/stitch.py` and `img_compress/compress.py`.
- pillow-heif 0.18.0 - Optional HEIC/HEIF codec registration in `img_compress/compress.py`.

**Testing:**
- `unittest` (stdlib) - All test suites.
- `unittest.mock` - Patching in `image_add/test_stitch.py`, `img_compress/test_compress.py`, `img_compress/test_gui_smoke.py`.
- `tempfile.TemporaryDirectory` - Filesystem isolation for image tests.

**Build/Dev:**
- No build system. Applications run directly from source.
- `.bat` launchers start the GUI with `pythonw` (no console window).
- GSD framework v1.20.1 (`.claude/gsd-core/VERSION`) and 21 superpowers skills (`.claude/skills/`) provide the agent workflow, not application runtime.

## Key Dependencies

**Critical:**
- `Pillow>=9.1` (`image_add/requirements.txt`) - Image open/save, resizing, EXIF orientation, ICC handling, color parsing.
- `Pillow>=10.4` (`img_compress/requirements.txt`) - Compression presets rely on Pillow 10.4 encoder behavior.
- `pillow-heif>=0.18` (`img_compress/requirements.txt`) - HEIC/HEIF support. Imported defensively: if missing, `HEIF_AVAILABLE=False` and only HEIC inputs are rejected (see `img_compress/compress.py:16-21`, `img_compress/compress.py:288-292`).

**Infrastructure:**
- None. Applications have no server, database, queue, or cloud dependency.
- `snake_game/` has no third-party dependency at all; it uses `random` and `tkinter` only.

## Dependency Versions Observed

| Package | Declared | Installed |
|---------|----------|-----------|
| Pillow | `>=9.1` (image_add), `>=10.4` (img_compress) | 10.4.0 |
| pillow-heif | `>=0.18` (img_compress) | 0.18.0 |
| Python | `3.8+` | 3.8.3 |
| Tk | bundled | 8.6 |
| Node.js | not declared (tooling) | 26.13.0 |

## Configuration

**Environment:**
- No `.env` files and no environment-variable requirements in application code. Confirmed: no `os.environ` / `getenv` usage in `image_add/`, `img_compress/`, or `snake_game/`.
- No secrets or credential files in the tracked application trees.

**Application config:**
- `image_add/requirements.txt` - Pillow dependency.
- `img_compress/requirements.txt` - Pillow + pillow-heif dependencies.
- `image_add/run_gui.bat`, `img_compress/run_gui.bat`, `snake_game/run_snake.bat` - `pythonw` launch scripts.
- CLI defaults are hard-coded in `image_add/stitch.py` (`main`, `build_parser`) and `img_compress/compress.py` (`LEVELS`, `build_parser`).

**Tooling config:**
- `.claude/settings.local.json` - hook registrations and permission allowlist (`Read`/`Edit` on `.planning/*` and `STATE.md`).
- `.claude/gsd-install-state.json` - GSD install/migration state.
- `.claude/gsd-file-manifest.json` - GSD managed-file manifest.
- `.claude/.gsd-profile` - GSD profile selection.
- `.agents/skills/cost-mode/` - duplicate cost-mode skill for non-Claude runtimes.
- No `.planning/config.json` present (GSD defaults apply).

## Testing Commands

```bash
# image_add
cd image_add && python test_stitch.py -v

# img_compress (core + GUI smoke)
cd img_compress && python -m unittest -v

# snake_game
cd snake_game && python -m unittest test_snake -v
```

GUI smoke tests self-skip when no display is available (`img_compress/test_gui_smoke.py:20-31`).

## Platform Requirements

**Development:**
- Windows 10/11 (primary target per `img_compress/README.md` and design doc).
- Python 3.8+ with Tkinter.
- `pip install -r requirements.txt` in each app directory.
- Optional: Node.js for `.claude/` hooks (the GSD layer degrades gracefully if Node is absent).

**Production:**
- No deployment target. These are local desktop utilities distributed as source directories launched by `.bat` files or `python <tool>.py`.
- All image processing is local; no service, container, or hosted environment.

## Notable Constraints

- Python 3.8 compatibility is mandatory: code avoids 3.9+ syntax (no built-in generic annotations like `list[str]`, no `match`), and pinning reflects 3.8-compatible wheels (`pillow-heif==0.18.0` noted in `img_compress/compress.py:290-292`).
- The three apps are fully independent; there is no cross-app import or shared library.
- `img_add/` currently appears in `git status` as deleted and is replaced by `image_add/`; the working tree is the source of truth for this analysis.

---

*Stack analysis: 2026-11-11*
