# LayoutProof Web UI — offline localhost interface

A small, dependency-light web UI for LayoutProof. It **wraps the existing public
Python API** (`scan_file`, `fix_file`, `render_presentation`,
`layoutproof.report`) and adds **no detection, repair or rendering logic of its
own**. The server uses only the Python standard library (`http.server`), binds
to the loopback interface, makes no outbound network calls, and loads no CDN or
external assets.

## Directory layout

```
web/
├── __init__.py
├── __main__.py          # enables `python -m web`
├── server.py            # stdlib ThreadingHTTPServer + CLI (loopback only)
├── app.py               # route dispatch; orchestrates the public API
├── store.py             # server-managed per-session workspace; path containment
├── upload.py            # size gate, extension whitelist, zip central-directory audit
├── static/
│   ├── index.html
│   ├── style.css
│   ├── i18n.js          # English / Chinese strings (pure module)
│   ├── logic.js         # counts, grouping, diffs, markers, name validation (pure)
│   └── app.js           # DOM glue + fetch calls
├── tests/               # pytest suite for every endpoint and safety negative
└── node-tests/          # node:test suite for the pure client logic (no deps)
```

## Requirements

- Python 3.11+ with the project virtual environment (the `layoutproof` package
  and its existing dependencies are reused as-is).
- Optional: LibreOffice/`soffice` for real slide rendering. When it is absent
  the UI shows an explicit **static-fallback** badge and geometry markers only;
  static detection still works fully offline.

## Run

From the project root (`E:\ai测试\LayoutProof`):

```powershell
# ephemeral free port (recommended for daily use)
.venv\Scripts\python.exe -m web.server

# fixed port
.venv\Scripts\python.exe -m web.server --port 8765

# custom managed workspace + upload ceiling
.venv\Scripts\python.exe -m web.server --port 8765 --workdir .web-work --max-mb 20
```

Then open the printed `http://127.0.0.1:<port>/` URL. Stop with `Ctrl+C`.

| Option        | Default            | Meaning |
|---------------|--------------------|---------|
| `--host`      | `127.0.0.1`        | Loopback only; non-loopback binds are refused. |
| `--port`      | `0` (ephemeral)    | TCP port; `0` picks a free port. |
| `--workdir`   | private temp dir    | Root for per-session uploads, fixed decks and renders. |
| `--max-mb`    | `50`               | Upload size ceiling. |
| `--verbose`   | off                | Echo HTTP requests to the console. |

## UI workflow

1. **Upload** a `.pptx` by drag-and-drop or file picker.
2. **Overview**: severity summary chips, a per-slide issue list with counts,
   and issue markers positioned over the slide using normalized geometry.
   If a renderer exists, real slide images are shown; otherwise a disclosed
   static-fallback badge replaces the images.
3. **One-click Fix** calls `fix_file`, then displays before/after issue counts
   and applied/skipped repairs; the fixed deck can be downloaded.
4. **Downloads**: fixed `.pptx`, schema-validated JSON report, and a
   self-contained bilingual HTML report.
5. The **EN / 中文 toggle** switches all UI labels client-side; the HTML report
   endpoint also accepts `?lang=zh|en`.

## HTTP API (JSON, except downloads/images)

| Method | Path | Purpose | Success / errors |
|---|---|---|---|
| GET | `/` | Local SPA index | 200 / 405 on non-GET |
| GET | `/static/<file>` | Whitelisted local assets | 200 / 404 |
| GET | `/api/health` | Server, tool version, renderer status, `offline: true` | 200 |
| GET | `/api/meta` | Bilingual rule catalog, profiles, severities, upload limit | 200 |
| POST | `/api/upload` | Multipart field `file`; validates size/extension/zip; creates a session | 201; 400 invalid; 413 oversized |
| POST | `/api/scan` | `{session_id, profile?}` → `scan_file` + per-slide overview | 200 / 400 bad profile, 404 unknown session |
| GET | `/api/state/<session_id>` | Scanned/fixed flags and file presence | 200 / 404 |
| POST | `/api/fix` | `{session_id, profile?}` → `fix_file`; re-scans output; before/after counts | 200 / 404 |
| GET | `/api/render/<session_id>/<before\|after>` | `render_presentation` manifest (cached) | 200 / 400 bad stage, 404 missing session or fixed deck |
| GET | `/api/image/<session_id>/<stage>/<n>.png` | One rendered slide | 200 image / 400 bad number / 404 fallback or missing |
| GET | `/api/download/fixed/<session_id>` | Server-created fixed `.pptx` attachment | 200 / 404 not fixed |
| GET | `/api/report/json/<session_id>` | Validated JSON envelope attachment | 200 / 404 |
| GET | `/api/report/html/<session_id>?lang=en\|zh` | Self-contained HTML report attachment | 200 / 404 |

Session ids are 16 hex tokens generated server-side; clients never supply a
filesystem path or stored filename.

## Safety model

- **Loopback-only bind**; the CLI rejects non-loopback `--host` values.
- **Upload gate**: declared and actual byte size ceiling; `.pptx` extension
  whitelist; empty upload rejected; multipart must contain a named file part;
  the archive central directory is inspected (zip-slip member names,
  duplicates, missing `[Content_Types].xml` / `ppt/presentation*.xml`, entry
  and uncompressed-size quotas) without extracting anything.
- **Untrusted client filenames** are reduced to a display basename; bytes are
  always stored under fixed names (`source.pptx`, `fixed.pptx`) inside the
  server-managed session directory.
- **Source deck read-only**: the fix path writes a new `fixed.pptx`; the engine
  is invoked with `make_backup=False`; an integration test compares source SHA-256
  before and after repair.
- **Containment**: image, report and fixed-download paths resolve and are
  verified inside the session directory; traversal strings (`..`, encoded
  separators) yield 400/404.
- **No network**: no CDN, fonts, or remote script/style references; static asset
  tests assert `http(s)://` absence in served assets.

## Tests

```powershell
# web endpoint + safety suite (pytest, depends on the venv)
.venv\Scripts\python.exe -m pytest web/tests -q

# existing core suite must remain green (unchanged by this package)
.venv\Scripts\python.exe -m pytest -q

# lint/format on the new package
.venv\Scripts\ruff check web
.venv\Scripts\ruff format --check web

# client interactive logic (Node built-in test runner, no npm deps)
node --test web/node-tests/i18n.test.cjs web/node-tests/logic.test.cjs
# If `node` is not on PATH, pass the explicit node executable instead.
```

`web/tests/` does not reuse the repository's existing test helpers; the existing
`tests/`, `src/layoutproof/fix/`, `eval/`, `docs/` and `.github/` trees were not
modified by this package.

## Verification notes and limitations

- Endpoint behavior, security negatives and the fix loop are covered by real
  pytest tests that boot the actual stdlib server and exercise the real
  `scan_file` / `fix_file` pipeline on generated decks.
- The client counting/grouping/diff/validation/marker logic is covered by the
  dependency-free Node suite; `app.js` itself remains DOM glue.
- No real-browser screenshot automation was available in the build environment
  (headless Edge screenshots do not persist here); the visual layout was
  therefore **not** asserted by a browser snapshot. Without LibreOffice the
  render endpoint returns the disclosed `static_fallback` manifest and the UI
  badge shows that reason; geometry markers remain available from detection.
