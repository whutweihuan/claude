---
last_mapped_commit: 8285931c1a64edb6f3b03a5396a6eb07a8d3d8d1
last_mapped_at: 2026-11-11
---
# External Integrations

**Analysis Date:** 2026-11-11

## Summary

The three applications in this repository are **fully local and offline**. They make no network requests, use no remote APIs, databases, authentication providers, analytics, or webhooks. All external interaction is with the local filesystem and locally-installed image codecs.

The only outbound network behavior in the repo belongs to the installed Claude Code / GSD tooling layer (`.claude/`), not to the application code.

## APIs & External Services

**Application code:**
- None. Verified by grepping `image_add/`, `img_compress/`, and `snake_game/` for `requests`, `urllib`, `http`, `socket`, `openai`, `anthropic`, `stripe`, `supabase`, `boto`, `redis`, `sqlite3`, API keys, and `os.environ`/`getenv`. The only URL match is a manual install hint printed to users.

**Tooling layer (not application runtime):**
- npm registry (`@opengsd/gsd-core`) - Background update check executed by the Claude Code session-start hook.
  - Implementation: `npm view @opengsd/gsd-core version`, wrapped in `checkLatestVersion()` at `.claude/gsd-core/bin/check-latest-version.cjs:92`.
  - Caller: `.claude/hooks/gsd-check-update-worker.js`; registered via the `SessionStart` hook in `.claude/settings.local.json`.
  - Timeout: 15,000 ms (`NPM_VIEW_TIMEOUT_MS`), failures swallowed and cached as `latest: "unknown"`.
  - Result cache: `gsd-update-check-opengsd-gsd-core.json` written atomically outside the app trees.
  - Auth: none; public npm registry via the local npm CLI. No tokens requested or stored.
- GitHub (`open-gsd/gsd-core`) - Referenced by the GSD package identity for changelog and manual-install instructions (`.claude/gsd-core/bin/lib/package-identity.cjs`). No runtime fetch during normal use.
- GitHub (`github.com/koalaman/shellcheck`) - Only used by `.claude/scripts/lib/shellcheck-fetch.cjs` when a shellcheck binary is explicitly fetched for tooling tests; not part of application flows.

## Data Storage

**Databases:**
- None. No SQL/NoSQL client, ORM, or connection string anywhere.

**File Storage:**
- Local filesystem only.
- `image_add/stitch.py` reads image files/folders/globs and writes a single stitched output (default `stitched.png`).
- `img_compress/compress.py` reads image files/folders and writes `<stem>_compressed.<ext>` into a user-selected output directory. Outputs are written to a temporary file first, then moved into place so partial files are not left behind (`img_compress/compress.py`, compression write path).
- Originals are never modified or overwritten (enforced by naming and by `kept_original` logic).
- `snake_game/` keeps all state in memory only.

**Caching:**
- Application: none.
- Tooling: GSD update-check JSON cache (see above) and `.claude/.gsd-profile`; not used by the Python apps.

## Authentication & Identity

**Auth Provider:**
- Not applicable. No accounts, login, tokens, sessions, or OAuth. The tools are single-user local desktop utilities.
- The only credential-adjacent configuration is the Git remote using SSH (`git@github.com:whutweihuan/claude.git`), handled by the developer's SSH agent, not by application code.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, telemetry, or remote logging.

**Logs:**
- Human-readable console output only.
- `image_add/stitch.py` prints warnings to `stderr` via `warn()`; CLI exit code 0 on success, 1 on failure.
- `img_compress/compress.py` returns structured `CompressResult` records and prints a batch summary; CLI exit code 0 when at least one image succeeds, 1 when all fail or arguments are invalid.
- GUI apps report progress and errors through Tkinter message boxes and a status list.

## CI/CD & Deployment

**Hosting:**
- None. Source-only local tools; no server or hosting provider.

**CI Pipeline:**
- None detected. No `.github/workflows/`, `.gitlab-ci.yml`, or other CI config in the repository.

**Distribution:**
- Clone the repo, install `requirements.txt` per app, and launch with `run_gui.bat` / `python <module>.py`.
- GSD tooling is installed in-tree under `.claude/` (v1.20.1), managed via `.claude/gsd-file-manifest.json` and `.claude/gsd-install-state.json`.

## Environment Configuration

**Required env vars:**
- None for the applications.
- The Claude Code hook launcher resolves a Node.js binary from common paths (`C:/Program Files/nodejs/node.exe`, `command -v node`, `/usr/local/bin/node`, `/usr/bin/node`) as seen in `.claude/settings.local.json`.

**Secrets location:**
- No application secrets exist.
- `.claude/settings.local.json` contains only `hooks`, `worktree`, and `permissions` keys; it is untracked (`git status` shows `?? .claude/settings.local.json`).

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None from application code.
- Tooling: the GSD session-start update-check worker calls the npm registry; this is a pull, not a webhook.

## Third-Party Codec Integrations

These are local library integrations, not network services:

- **Pillow codecs** (`image_add/stitch.py`, `img_compress/compress.py`): JPEG, PNG, WebP, BMP, GIF, TIFF encode/decode; EXIF orientation via `ImageOps.exif_transpose`; ICC profiles via `ImageCms`.
- **pillow-heif** (`img_compress/compress.py:16-21`): registers HEIC/HEIF openers globally with Pillow. Optional at import time; absence is surfaced as a user-facing "install pillow-heif" message (`img_compress/compress.py:288-292`).
- **Python stdlib modules**: `tkinter` (GUI), `argparse` (CLI), `threading`/`queue` (GUI workers), `random` (snake game), `tempfile`/`shutil`/`os`/`pathlib` (filesystem).

## Manual Package Mirror Reference

`img_compress/README.md` and the HEIC error message recommend the Tsinghua PyPI mirror for installing dependencies:

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

This is a documented install instruction, not a runtime integration.

## Integration Risks

- **pillow-heif optionality:** HEIC support is conditional on a third-party wheel that can be blocked by corporate proxies (documented in `img_compress/README.md`). Missing it degrades gracefully for non-HEIC formats but rejects HEIC inputs.
- **Pillow 10.4 encoder quirks:** `img_compress/README.md` documents avoiding certain JPEG parameter combinations due to a Pillow 10.4 encoding error, coupling behavior to the pinned dependency version.
- **Tooling network call:** the GSD update check shells out to `npm view`, which can hang or fail behind proxies; it is bounded by a 15-second timeout and failures are non-fatal.

---

*Integration audit: 2026-11-11*
