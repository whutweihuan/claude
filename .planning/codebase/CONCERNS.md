---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
# Codebase Concerns

**Analysis Date:** 2026-11-11

**Scope:** Full repository — three independent local Python tools:
`img_compress/` (image compression), `image_add/` (image stitching; formerly `img_add/`), and
`snake_game/` (tkinter Snake). Tests were executed on this date under Python 3.8.3 with
Pillow 10.4.0 and pillow-heif 0.18.0: `img_compress` 43 tests OK, `image_add` 13 tests OK,
`snake_game` 11 tests OK.

## Tech Debt

**No repository-level project definition or test runner:**
- Issue: There is no root `README.md`, `pyproject.toml`, `setup.cfg`, `pytest.ini`, `tox.ini`, or CI config. Each tool is a standalone script that imports its sibling module by current working directory (`import compress`, `import stitch`, `import snake`).
- Files: repository root; `img_compress/compress_gui.py:12`, `image_add/stitch_gui.py:14`, `snake_game/snake_gui.py:7`, all `test_*.py` files.
- Impact: `python -m unittest discover` from the repository root discovers and runs 0 tests (verified). Tests must be run separately inside each tool directory, so a single command cannot validate the repo. Any future shared code cannot be imported cleanly.
- Fix approach: Add a root `pyproject.toml` or `pytest.ini` with `testpaths = img_compress image_add snake_game`, add `__init__.py` only if a package structure is desired, and document one canonical test command at the root.

**Duplicated utility and input-expansion logic between tools:**
- Issue: `ToolError`, `warn`, `natural_key`, `is_image_file`, path de-duplication, and `expand_inputs` are implemented twice with subtle behavioral drift. `compress.py` filters generated `_compressed` outputs and does not support globs; `stitch.py` supports globs and filters only the output path.
- Files: `img_compress/compress.py:61-141`, `image_add/stitch.py:42-101`.
- Impact: Bug fixes or new supported formats must be applied twice and can diverge (e.g., `SUPPORTED_EXTS` in `compress.py:24-27` includes HEIC/HEIF; `stitch.py:29` does not). Duplicate `_format_size` also exists in `img_compress/compress.py:423-430` and `img_compress/compress_gui.py:32-39`.
- Fix approach: Extract a shared `imgtools/` module (path discovery, size formatting, natural sort) once the root project layout exists; keep tool-specific format tables local.

**Version-control hygiene is poor:**
- Issue: No `.gitignore` anywhere in the repo. Compiled bytecode is tracked: root `__pycache__/stitch.cpython-38.pyc`, root `__pycache__/stitch_gui.cpython-38.pyc`, and `img_add/__pycache__/stitch.cpython-38.pyc`. The working tree currently shows all of `img_add/` deleted and an untracked `image_add/` copy, so the rename is not committed and history for the stitching tool is split across paths.
- Files: repository root, `.gitignore` (missing), `img_add/*` (tracked, deleted in working tree), `image_add/*` (untracked).
- Impact: `.pyc` files create noisy diffs and stale-artifact confusion (root bytecode exists with no root source files). The uncommitted rename risks losing or duplicating the tool. Future virtualenvs, caches, output images, and local Claude settings have no ignore rules.
- Fix approach: Add `.gitignore` entries for `__pycache__/`, `*.py[cod]`, `.venv/`, `compressed/`, `.claude/settings.local.json`, and generated images; `git rm -r --cached` the tracked `__pycache__`; stage the `img_add` → `image_add` rename so git records history.

**Stale build/planning artifacts:**
- Issue: `image_add/skills-lock.json` is a leftover from a skill installer and references `cost-mode`, unrelated to image stitching. `img_compress/docs/superpowers/plans/2026-11-10-image-compressor.md` states "当前目录不是 Git 仓库" ("the current directory is not a Git repository"), which is false.
- Files: `image_add/skills-lock.json`, `img_compress/docs/superpowers/plans/2026-11-10-image-compressor.md`.
- Impact: Misleads future agents and contributors; planning docs are checked in but not reconciled with the actual repository state.
- Fix approach: Delete `image_add/skills-lock.json`; correct the plan header or move historical plans outside the shipped tool directory.

**Documentation drift in `CLAUDE.md`:**
- Issue: `CLAUDE.md` claims "21 个 skills" and lists 21, but `.claude/skills/` contains 22 skill directories including `cost-mode`, which is omitted from the list.
- Files: `CLAUDE.md`, `.claude/skills/`.
- Impact: Low, but onboarding instructions are inaccurate and the cost-mode skill is invisible to readers of the core rule list.
- Fix approach: Update the count and bullet list, or generate the list from the directory.

**Windows-only assumptions are undocumented at the code level:**
- Issue: Launch scripts rely on `pythonw` being on `PATH` and use Windows batch syntax. The GUI optionally selects the `vista` theme and uses the `Microsoft YaHei UI` font (`snake_game/snake_gui.py:23`, `:311-313`).
- Files: `img_compress/run_gui.bat`, `image_add/run_gui.bat`, `snake_game/run_snake.bat`, `img_compress/compress_gui.py:391-397`, `img_compress/compress_gui.py:394`, `image_add/stitch_gui.py:309-315`.
- Impact: Launching on macOS/Linux or in a venv where `pythonw` is absent fails silently or opens the wrong interpreter; font fallback is implicit.
- Fix approach: Document Windows-only support explicitly (READMEs partially do) or add cross-platform launch instructions; resolve the interpreter path in the batch files if multiple Pythons are common.

## Known Bugs

**Compression silently skips legitimate filenames ending in `_compressed`:**
- Symptoms: A user file named `holiday_compressed.jpg` or `report_compressed_1.png` is excluded from folder scans even though it was never produced by this tool. The output count is lower than the visible file count.
- Files: `img_compress/compress.py:28`, `_is_generated` at `:106-107`, used at `:133`.
- Trigger: Put a file with that suffix in an input directory and run `python compress.py <dir>`.
- Workaround: Rename the file or pass it explicitly (`expand_inputs` does not apply the filter to explicit files, `compress.py:126-128`).
- Fix: Track generated files by a manifest or by comparing against known outputs, or only exclude files whose metadata/output pattern fully matches and warn when skipping.

**Stitch CLI output is only excluded when the output path is identical; a renamed output can be re-ingested:**
- Symptoms: Running `stitch.py ./photos -o out1.png`, then `stitch.py ./photos -o out2.png` includes `out1.png` as an input image, producing an ever-growing composite. `image_add/README.md` promises automatic exclusion of "上次生成的输出文件" without this caveat.
- Files: `image_add/stitch.py:384-389`, README statement at `image_add/README.md:65-66`.
- Trigger: Run twice against the same folder with different output names.
- Workaround: Write outputs outside the input directory, or delete the previous output.
- Fix: Exclude any file matching generated-output patterns (similar to `_compressed`) or record generated outputs; update the README.

**Stitch folder import does not handle `ToolError` (GUI callback crash):**
- Symptoms: If the chosen folder becomes inaccessible or `expand_inputs` raises, tkinter logs an unhandled callback traceback and no user-facing dialog appears.
- Files: `image_add/stitch_gui.py:157-166` (no try/except around `stitch.expand_inputs`), contrasted with `img_compress/compress_gui.py:183-187` which handles `compress.ToolError`.
- Trigger: Delete/move the folder between selection and import, or hit a permission error.
- Workaround: Restart the GUI.
- Fix: Wrap the call and show `messagebox.showerror`, matching the compressor GUI.

**`--sort mtime` can crash with a raw traceback if a file disappears:**
- Symptoms: `os.path.getmtime` raises `OSError` while sorting, outside any `ToolError` handling, so the CLI prints a Python traceback instead of a friendly error.
- Files: `image_add/stitch.py:104-111`, CLI wrapper `:405-412` catches only `ToolError` and `KeyboardInterrupt`.
- Trigger: Files deleted or locked by another process between expansion and sorting.
- Fix: Catch `OSError` per file or wrap sorting/stat calls in `ToolError`, and warn/skip missing files.

**CLI stitch overwrites existing output without confirmation:**
- Symptoms: `-o existing.png` replaces the file silently. The GUI asks for confirmation (`stitch_gui.py:250-252`), the CLI does not.
- Files: `image_add/stitch.py:214-251` (`save_result` writes directly), CLI path `:395-401`.
- Trigger: Point `-o` at any existing important file.
- Workaround: Use a new output name.
- Fix: Add `--overwrite`/`--no-overwrite` behavior or warn and abort by default, consistent with the GUI.

**Stitch memory errors surface as a generic error in the GUI and as a traceback in the CLI:**
- Symptoms: `MemoryError` during canvas allocation is not wrapped. In `stitch_gui.py:276-286` the generic handler reports "发生未知错误" with a nondiagnostic message; in the CLI it propagates through `main` and produces a traceback.
- Files: `image_add/stitch.py:179-211`, `image_add/stitch.py:254-263`, `image_add/stitch_gui.py:276-286`, `image_add/stitch.py:405-412`.
- Trigger: Large albums or very large source images.
- Fix: Catch `MemoryError` around `stitch`/`limit_size` and raise `ToolError` with guidance to reduce inputs or use `--max-size` (noting that `--max-size` currently cannot prevent peak allocation — see Performance Bottlenecks).

**Broad exception swallowing hides quantization failures:**
- Symptoms: `_quantize_png` catches every exception and silently returns the unquantized image, so a palette/transparency regression produces a larger output with no warning.
- Files: `img_compress/compress.py:205-217`.
- Impact: PNG/GIF compression silently degrades; tests only assert happy paths.
- Fix: Narrow the caught exception types and emit a warning (`warn(...)`) or a result note when quantization is skipped.

**Compression progress can show 100% while files failed:**
- Symptoms: `_finish` sets the progress bar to `len(self.files)` regardless of failures/skips.
- Files: `img_compress/compress_gui.py:329-332`.
- Impact: Cosmetic, but confusing during batches with failures.
- Fix: Set value to processed count and display success/failure counts already present in the summary.

**HEIF registration failure is completely silent:**
- Symptoms: `ImportError` from `pillow_heif` is swallowed at import time; the GUI/CLI behaves as if HEIC is unsupported only when a HEIC file is supplied, and the listing still advertises HEIC in file dialogs.
- Files: `img_compress/compress.py:16-22`, `img_compress/compress_gui.py:15`.
- Impact: Users with a broken/partial pillow-heif install see a late error; no startup warning.
- Fix: Emit a one-time warning when HEIC support is unavailable, or show it in the GUI status line.

## Security Considerations

**Untrusted image parsing with no resource limits:**
- Risk: Pillow parses arbitrary user-supplied files. There is no explicit `Image.MAX_IMAGE_PIXELS` policy and no handling of `DecompressionBombWarning`/`DecompressionBombError`. A crafted image can consume large amounts of memory/CPU or abort a batch.
- Files: `img_compress/compress.py:295-301`, `image_add/stitch.py:114-126`.
- Current mitigation: Per-image failures are caught in batch mode (`compress.py:471-483`); Pillow's built-in bomb guard still raises/warns at default thresholds. GUI work runs on a background thread (`compress_gui.py:288`) but the stitch GUI still allocates full images.
- Recommendations: Set a documented pixel limit, catch `Image.DecompressionBombError` explicitly, and test with large/corrupt inputs.

**Dependency surface is unpinned and install instructions are mirror-specific:**
- Risk: `requirements.txt` files use only lower bounds (`Pillow>=10.4`, `pillow-heif>=0.18`, `Pillow>=9.1`). There is no lock file or hash checking. The HEIC error message hard-codes `pillow-heif==0.18.0` and a Tsinghua mirror (`compress.py:288-292`), while requirements allow any newer version. Future Pillow/pillow-heif releases may change encoders or drop Python 3.8, silently changing output quality or breaking installs.
- Files: `img_compress/requirements.txt`, `image_add/requirements.txt`, `img_compress/compress.py:288-292`, `img_compress/README.md:26-33`.
- Current mitigation: READMEs document the tested versions and the local environment is exactly Pillow 10.4.0 / pillow-heif 0.18.0.
- Recommendations: Pin exact versions (or add a constraints file), keep the install hint and requirements consistent, and document the supported version matrix.

**Vendored third-party skill scripts are committed:**
- Risk: `.claude/skills/` and `.agents/skills/` include executable shell scripts and a Node server from third-party repositories (e.g., `.claude/skills/brainstorming/scripts/server.cjs`, `.claude/skills/brainstorming/scripts/start-server.sh`). They are part of the agent tooling, not the image tools, but they are trust-relevant code in the repository.
- Files: `.claude/skills/**`, `.agents/skills/**`.
- Current mitigation: No credentials are stored in the product code; no `.env` or secret files were found. `.claude/settings.local.json` exists but was not inspected because it is local configuration.
- Recommendations: Document the provenance and version of vendored skills; review changes to these scripts like application code.

**Output collision check is subject to a time-of-check/time-of-use race:**
- Risk: `unique_output_path` checks `candidate.exists()` and later `os.replace` writes the path. Two simultaneous runs can select the same output and overwrite each other's result.
- Files: `img_compress/compress.py:152-160`, `:329-335`.
- Current mitigation: Single-user desktop usage makes concurrent runs unlikely.
- Recommendations: Open the output with exclusive creation (`os.open(..., O_CREAT | O_EXCL)`) or use per-run temporary directories when concurrency becomes possible.

**No secrets detected:** No `.env`, credential, key, or token files were found in the product directories. Error messages contain local paths, which is acceptable for a local desktop tool.

## Performance Bottlenecks

**Stitch loads every image and the full canvas into memory:**
- Problem: `load_images` converts every source to RGBA and keeps all of them alive (`image_add/stitch.py:114-126`); `stitch` allocates the entire composite (`:179-211`). For a 100-photo album at 12 MP, RGBA sources alone can approach several GB before the canvas is allocated.
- Files: `image_add/stitch.py:114-211`, `image_add/stitch_gui.py:276-286`.
- Cause: The design is "load all → resize all → paste all"; no streaming or per-image downscaling before accumulation.
- Improvement path: Downscale each image to the target cross-axis size before storing it; compute final dimensions first and, if only a downscaled result is requested, resize each contribution before pasting. Wrap allocation failures in a friendly `ToolError`.

**`--max-size` does not reduce peak memory:**
- Problem: `limit_size` resizes only after the full-size canvas has been created (`image_add/stitch.py:254-263`, called at `:281`). Users reasonably expect `--max-size` to bound resource use; it bounds only the saved output.
- Files: `image_add/stitch.py:266-283`.
- Improvement path: Compute the final scale from the source sizes, then scale each image/canvas incrementally; state the limitation in the README.

**Compression is strictly sequential:**
- Problem: Batch compression processes one image at a time (`img_compress/compress.py:402-412`). Large JPEG/HEIC batches use one core, and GUI progress advances only per completed image.
- Files: `img_compress/compress.py:371-420`.
- Improvement path: Optional bounded thread/process pool (Pillow releases the GIL for much of encode/decode) with deterministic ordering and progress reporting; keep the default single-threaded for predictable memory.

**Recursive directory scans are unbounded:**
- Problem: `rglob("*")` walks the entire tree and collects all matches before any compression starts (`img_compress/compress.py:130-138`, `image_add/stitch.py:76-84`). A pointed-at home directory can scan huge trees and stat many files.
- Files: `img_compress/compress.py:121-141`, `image_add/stitch.py:60-101`.
- Improvement path: Stream candidates to the worker, cap directory depth or file count with a warning, and provide progress during discovery.

**GUI per-file tree updates in large batches:**
- Problem: Each result updates a `ttk.Treeview` row (`img_compress/compress_gui.py:350-363`); thousands of rows plus a 100 ms polling loop can make the GUI sluggish.
- Files: `img_compress/compress_gui.py:303-327`, `:329-388`.
- Improvement path: Batch row updates, or use a virtualized list for very large batches.

## Fragile Areas

**Duplicated `expand_inputs` implementations with different semantics:**
- Files: `img_compress/compress.py:121-141`, `image_add/stitch.py:60-101`.
- Why fragile: The two tools advertise the same user concept ("file, folder, or glob") but behave differently: glob support exists only in `stitch.py`; generated-output filtering exists only in `compress.py`. Fixes and tests in one tool do not protect the other.
- Safe modification: Change both together and run both suites; ideally consolidate first.
- Test coverage: Good per-tool tests, but no cross-tool consistency test.

**GUI threading and widget lifetime:**
- Files: `img_compress/compress_gui.py:288-327`, `image_add/stitch_gui.py:270-306`.
- Why fragile: Background threads put messages on a `queue.Queue`; the Tk `after` poller touches widgets. Closing the window while work is running destroys the root, while the daemon worker keeps running and writing to the queue. There is no cancellation path, and long stitches cannot be stopped except by killing the process. A new `start()` during an error transition relies on `busy` and button state staying in sync.
- Safe modification: Add a cancellation event checked in the worker loop, guard widget updates with `winfo_exists()`, and disable the close button or prompt on close while busy.
- Test coverage: One compress GUI smoke test (`img_compress/test_gui_smoke.py`) covers the happy path and a missing file; no stitch GUI tests, no close-during-work tests.

**Import-by-cwd script layout:**
- Files: `img_compress/compress_gui.py:12`, `image_add/stitch_gui.py:14`, `snake_game/snake_gui.py:7`, `img_compress/test_gui_smoke.py:17`.
- Why fragile: Modules are imported as top-level names. Running from a different directory, packaging the tools, or introducing a shared module breaks imports. `python -m img_compress.compress` also fails without `__init__.py`.
- Safe modification: Add packages or adjust `sys.path` deliberately; do not rename sibling modules without updating all tests and launchers.
- Test coverage: None for invocation from other entry points.

**Tests assume the process working directory and a graphical display:**
- Files: all test modules; `img_compress/test_gui_smoke.py:21-27`, `:39-46` (skips when Tk or display is unavailable).
- Why fragile: Root-level discovery runs zero tests. GUI smoke tests use `root.update()` in a time-boxed busy loop (`test_gui_smoke.py:63-68`), which can be flaky on slow or headless CI. Tests also depend on Pillow APIs beyond the stated minimum (`Image.Exif` in `test_compress.py:288`, `Image.Resampling` in `image_add/stitch.py:161`) while `image_add/requirements.txt` says only `Pillow>=9.1`.
- Safe modification: Run each suite from its own directory as documented; add a root test configuration before adding CI.
- Test coverage: No CI, no coverage measurement, no lint/type checks.

**Python 3.8 runtime is end-of-life and constrains dependencies:**
- Files: `img_compress/README.md:21-24`, `image_add/README.md:6-9`; local interpreter is Python 3.8.3.
- Why fragile: Python 3.8 receives no security updates. Newer Pillow/pillow-heif releases may not publish 3.8 wheels, so the declared `>=` ranges can resolve to versions that fail to install or behave differently. The code uses syntax compatible with 3.8 (`list` annotations without parameters in dataclasses, `from __future__` not needed), so moving to 3.9+ is low-risk.
- Safe modification: Pin exact working versions now; plan an upgrade to a supported Python (3.10+ recommended) and re-run all suites.
- Test coverage: Only tested on this machine's 3.8.3.

## Scaling Limits

**Stitch composite size:**
- Current capacity: Limited by available RAM and Pillow's canvas size; `--max-size` caps only the saved result. No explicit maximum input count or pixel budget.
- Limit: Large albums / panorama-sized images can raise `MemoryError` or make the process unresponsive; there is no preflight dimension check.
- Scaling path: Precompute output dimensions, validate against a configurable pixel budget, downscale before allocation, and report a clear error.

**Batch compression throughput:**
- Current capacity: One image at a time; a few hundred large photos take correspondingly long with no parallelism.
- Limit: Time, not correctness; the GUI remains responsive via the worker thread but offers no cancel.
- Scaling path: Bounded worker pool and cancellation support.

**GUI row count:**
- Current capacity: A few thousand rows remain usable in `ttk.Treeview`/`tk.Listbox`.
- Limit: Tens of thousands of files make updates and selection sluggish.
- Scaling path: Virtualized list or chunked updates.

**Snake board size:**
- Current capacity: Fixed 20×20 grid (`snake_game/snake_gui.py:9-10`); `_spawn_food` rebuilds the full free-cell list on every food (`snake_game/snake.py:103-111`), which is trivial at 400 cells.
- Limit: Only relevant if the board size becomes configurable; O(width×height) per food and full canvas redraw per tick would degrade.
- Scaling path: Sample free cells without materializing the list, or maintain a free-cell set.

## Dependencies at Risk

**Pillow (`Pillow>=10.4`, installed 10.4.0):**
- Risk: Unpinned upper bound combined with Python 3.8; future versions may remove 3.8 wheels, change codec defaults, or contain security fixes that cannot be installed without a Python upgrade. The code also relies on a version-specific workaround for Pillow 10.4 (`compress.py:246-249`).
- Impact: Install failures or silent quality/output changes; security exposure if the pinned version later receives a CVE fix.
- Migration plan: Pin `Pillow==10.4.0` for reproducibility now; upgrade Python first, then re-test encoder behavior and remove the 10.4-specific workaround only after verification.

**pillow-heif (`pillow-heif>=0.18`, installed 0.18.0):**
- Risk: Version hint in code hard-codes `==0.18.0` while requirements allow newer; HEIF encoder parameters (`quality`) and plugin registration behavior can change. Import failure is silent (`compress.py:16-22`).
- Impact: HEIC/HEIF compression may stop working or produce different results after a dependency update; users see a late, confusing error.
- Migration plan: Pin the tested version, surface an explicit startup warning when unavailable, and add a manual HEIC round-trip check to the test run.

**Tkinter (standard library):**
- Risk: Bundled with the Python 3.8 installation; behavior varies by platform/theme, and headless environments cannot run the GUIs. The `vista` theme and `Microsoft YaHei UI` font are Windows-specific.
- Impact: GUI tests skip or fail on non-Windows/headless machines; UI appearance differs.
- Migration plan: Treat GUI as best-effort Windows-only, document it, and keep core logic GUI-independent (already true).

**Vendored skills under `.claude/` and `.agents/`:**
- Risk: Third-party code without a visible update mechanism; `image_add/skills-lock.json` is already stale relative to the repository state.
- Impact: Supply-chain and maintenance risk for the agent tooling; no effect on the three tools at runtime.
- Migration plan: Remove stale lock files, keep vendored skills in a separate managed location, and record their versions.

## Missing Critical Features

**Cancellation and safe shutdown for long operations:**
- Problem: Neither GUI can cancel a running batch/stitch; closing the window leaves a daemon thread running until process exit.
- Blocks: Usable behavior on large albums; clean shutdown semantics.

**Single-command, CI-compatible test execution:**
- Problem: No root test configuration; root-level `unittest discover` finds 0 tests, and no CI exists.
- Blocks: Automated verification of changes and regression protection across tools.

**Overwrite protection and dry-run for CLI operations:**
- Problem: `stitch.py` overwrites output silently; neither CLI offers `--dry-run` or a preview of the planned output dimensions.
- Blocks: Safe use in scripts and batch jobs.

**Animated image support:**
- Problem: Multi-frame GIF/WebP inputs are skipped (`compress.py:296-297`) and stitching treats only the first frame via Pillow's default open behavior.
- Blocks: Processing modern phone/web animations; documented as a limitation but a common expectation.

**Settings persistence and drag-and-drop:**
- Problem: GUI settings reset on each launch; no drag-and-drop, target-file-size search, cropping, or packaging/installer.
- Blocks: Convenience features only; explicitly out of scope in `img_compress/README.md:109`.

**Root documentation and license:**
- Problem: No root README explaining the three tools or how to install/test them together; no license file.
- Blocks: Onboarding and any redistribution.

## Test Coverage Gaps

**Stitch GUI:**
- What's not tested: `image_add/stitch_gui.py` has no automated tests — add/remove/reorder list operations, transparent-background toggle, output overwrite confirmation, validation errors, worker/poller flow, and the unhandled `ToolError` path described above.
- Files: `image_add/stitch_gui.py`.
- Risk: GUI regressions ship unnoticed; the folder-import crash is unguarded by tests.
- Priority: High.

**Snake GUI:**
- What's not tested: `snake_game/snake_gui.py` state machine (`ready`/`running`/`paused`/`over`), key handling, timer cancellation on pause/restart/close, and rendering. Only `snake_game/snake.py` logic is covered (11 tests).
- Files: `snake_game/snake_gui.py`, `snake_game/test_snake.py`.
- Risk: Timing/state bugs (e.g., double timers after pause/restart) are invisible.
- Priority: Medium.

**CLI and edge-case behavior:**
- What's not tested: glob inputs in `stitch.py:66-74`, `--sort mtime`/`--reverse` combinations, `--fit first`, `--quality` boundaries in the CLI, `--max-size` combined with transparent output, missing/locked files during `apply_sort`, permission-denied directories, concurrent output collisions, and `MemoryError` handling.
- Files: `image_add/stitch.py`, `img_compress/compress.py`.
- Risk: The `mtime` traceback and overwrite behavior above are exactly the kind of untested paths that fail in real use.
- Priority: High for `mtime`/overwrite; Medium for the rest.

**Compression GUI error paths:**
- What's not tested: Worker exceptions, close-during-batch, output-directory creation failure, repeated starts, and large-list performance. The smoke test covers only the happy path plus one missing file (`img_compress/test_gui_smoke.py:40-77`).
- Files: `img_compress/compress_gui.py`, `img_compress/test_gui_smoke.py`.
- Risk: UI can remain stuck in "busy" or crash on close; flaky test behavior on slow machines.
- Priority: Medium.

**Malformed and adversarial inputs:**
- What's not tested: Truncated EXIF, corrupt ICC profiles, decompression bombs, symlink loops, zero-byte images, and images whose extension does not match their content.
- Files: `img_compress/compress.py`, `image_add/stitch.py`.
- Risk: Resource exhaustion or unhelpful tracebacks outside the per-image catch block (e.g., `source.stat()` at `compress.py:293` runs before the guarded `open`).
- Priority: Medium.

**Environment/version coverage:**
- What's not tested: Any Python other than 3.8.3, Windows without the `vista` theme, non-Windows platforms, and pillow-heif absent (only mocked for one HEIC test at `test_compress.py:371-377`).
- Files: all test suites.
- Risk: The unpinned dependency ranges and EOL interpreter are unvalidated.
- Priority: Medium.

---

*Concerns audit: 2026-11-11*
