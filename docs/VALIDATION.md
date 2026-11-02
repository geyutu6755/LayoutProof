# VALIDATION.md — Verification Record & Evidence Log

This file is the durable, honest record of what LayoutProof has actually been
tested against. It is updated on every checkpoint. Claims are only recorded
here when they were observed in a real run; anything unverified is listed
under "Not verified" rather than implied.

Last updated: 2026-11-02

## 1. Environment under test

- OS: Windows (Local PC), PowerShell, Python 3.13.16 (runtime) / venv.
- Git: 2.55.0; remote `origin` = https://github.com/geyutu6755/LayoutProof.
- Renderer: LibreOffice 26.2.7.3 (isolated admin install under `.rendertools/lo`,
  no system registry changes), invoked via `LAYOUTPROOF_SOFFICE`.
- Image backend: PyMuPDF 2.0 (MuPDF 1.28.5), `import pymupdf`.
- Linux: **tested in CI** on `ubuntu-latest` (Python 3.11/3.12/3.13). macOS:
  **not tested** — no CI job or host available, so no macOS claim is made.

## 2. Test & coverage status

- Full suite (default run): **224 collected, 219 passed, 5 skipped, 0 failed,
  0 errors** (independently observed 2026-11-02).
- The 5 skips are intentional and documented in `tests/SKIP_NOTES.md`: 2
  render-chain tests when no renderer is configured, 2 heavy-media tests
  (gated by `LAYOUTPROOF_PERF=1`), and 1 isolated-venv lifecycle test.
  With the renderer env set, the render-chain tests pass and the skipped count
  drops to 3.
- **CI matrix (GitHub Actions): all jobs green on the latest commit** — six
  test jobs (`ubuntu-latest` + `windows-latest` × Python 3.11/3.12/3.13) and
  one `ruff` lint job. This is the cross-platform evidence; run ids and
  conclusions were read back through the Actions API.
- Line coverage: **86%** without renderer, **88%** with renderer
  (`pytest --cov=layoutproof`, branch metric). The
  formal suite raised `parsing/package.py` from 54% to 98%, `models.py` to
  98%, `engine.py` to 90%.
- Formal test directories now present: `tests/fuzz`, `tests/security`,
  `tests/contract`, `tests/performance`, `tests/install`, plus a shared
  `tests/helpers_decks.py`. Coverage is treated as a signal, not the goal;
  uncovered branches are mostly defensive `except` paths and renderer/
  gated edge cases.
- The multi-strategy fix upgrade adds `tests/unit/test_fix_strategies.py`
  (20 tests) and the web UI adds `web/tests` (45 tests) plus 16 Node
  client-logic tests, all independently re-run green.

## 3. Contract verification

- JSON output validates against `report/schema.json` (`ScanResult`), including
  off-slide normalized coordinates outside `[0,1]` (schema deliberately allows
  negative x/y and width/height > 1).
- Exit codes: 0 clean, 1 issues, 2 usage, 3 internal; driven by
  `exit_code_for(result, fail_on)` and exercised by CLI tests.
- Reproducibility: repeated scans produce identical JSON after the timestamp
  is removed.
- Source read-only: fix operations preserve the source SHA-256 (hash compared
  before/after); fixes always write a new file.

## 4. Rendering verification

- Real chain PPTX -> PDF -> PNG observed end-to-end on multiple corpus files.
- HTML report embeds slides as base64 data URIs with issue markers and
  before/after grids; verified 2 data URIs + 4 markers on the demo e2e.
- Demo broken deck: 4 issues (2 error / 2 warning) -> fixed -> 0 issues;
  rendered before/after images visually confirm off-slide move, font increase,
  overflow fit and placeholder removal.
- Static fallback is returned (never presented as real rendering) when the
  renderer is absent, PyMuPDF is missing, or conversion raises.
- **Real-browser verification (headless Edge):** the self-contained HTML
  reports were loaded in a real Chromium browser and their full-page layout
  inspected, in both English and Chinese. The rendered pages show the summary
  cards (2 error / 2 warning / 0 info / 4 total / 1 slide), the
  "REAL RENDERING" badge, the actual LibreOffice-rendered slide with issue
  markers, the filters and location-preview panels, and the four detailed
  issue cards (rule id, auto-fix badge, location, explanation, recommendation,
  confidence, Locate). Chinese rendering shows no encoding errors. The
  loopback Web UI landing page (drag-and-drop zone, static-fallback badge,
  language toggle) was likewise browser-verified.
- **Renderer discovery defect fixed:** the GUI `soffice.exe` does not return
  console output (`--version` hangs), so a pinned/non-standard `.exe` path
  failed detection. The discovery now prefers the sibling `soffice.com`
  console wrapper for *every* Windows candidate (not just the two standard
  install paths), covered by four regression tests in
  `tests/unit/test_render.py`. Existence checks use `os.path.exists` rather
  than `pathlib.Path`: `Path()` dispatches on `os.name`, so a test that
  fakes `os.name="nt"` on Linux otherwise tried to instantiate `WindowsPath`
  and crashed the session. `os.path` is bound to the platform module at
  import and does not dispatch.

## 5. Detection accuracy (current corpus)

- Independent evaluation set (`eval/`): 66 physical files, 52 unique authored
  decks (python-pptx + PptxGenJS) plus 14 LibreOffice resaves; 39 explicitly
  "unknown" cases excluded from scoring.
- After the two false-positive fixes, both profiles score **P=R=F1=1.0** on
  the judged cases (0 FP / 0 FN, 0 mismatches). This is a property of this
  corpus and its ground truth, not a claim of universal perfection; real-world
  edge cases remain under continuous evaluation.
- Mean detection time ~18-20 ms/file, max ~124 ms (full detail in
  `eval/results/timing.json`).
- Clean decks (`clean_basic`, `clean_agenda`, `complex_overloaded`,
  `crossrender_native_16x9`): zero false positives.
- `broken_all.pptx`: 11 planted defects detected (13 findings across
  severities; multiple placeholders on slide 7).
- `chinese_typesetting.pptx`: good slide 0 findings; bad slide 2 CJK findings
  (kinsoku line start, half-width punctuation).
- `crossrender_flat_4x3.pptx`: 1 real off-slide finding (title box past 4:3).
- `broken_structure.pptx`: status=error, "not a valid zip/pptx package".

## 6. Security checks (status)

- In-memory zip loader guards against zip-slip, duplicate entries,
  compression bombs (entry-count and total-size quotas) and unsafe XML;
  formal adversarial tests now assert the real error messages for all of
  these in `tests/security`.
- XML entity safety: local `file:` SYSTEM entities, external `http:` entities
  and parameter entities are blocked with entity resolution and network
  access disabled; a secret-marker probe confirms no file content leaks. The
  test is platform-agnostic and accepts either rejection or safe
  non-expansion (the earlier Windows-only pass relied on an accidental
  malformed file URI; it now asserts the real security property on Linux too).
- Fuzz: byte mutation/truncation/flips and structured edge cases never raise
  an uncaught exception and never return the internal exit code 3.
- Real defect fixed: the HTML report's JSON data block was vulnerable to a
  `</script>` stored-XSS breakout via malicious shape names/details. It now
  escapes `<`, `>`, `&` as unicode escapes (`_json_script_payload`), covered
  by permanent regression tests in `tests/contract/test_html_output_safety.py`.
- Performance: real ~10 MB and ~50 MB media decks (gated) scan within
  documented time/memory bounds; see `tests/performance/PERF_RESULTS.md`.

## 7. Not verified / blocked

- Headless Edge `--headless` (old mode) produced no file; the newer
  `--headless=new` mode with a separate user-data-dir works and was used for
  the browser verification above. The Web UI's post-upload data view is not
  separately screenshotted (a fresh headless session has no upload), but its
  rendering logic is covered by 45 pytest HTTP tests and 16 Node tests.
- No `gh` CLI; GUI automation backends unavailable in prior attempts.
- macOS runtime behavior; WPS/PowerPoint-specific rendering fidelity.
- PyPI publishing: not performed (requires separate authorization). Only the
  GitHub prerelease v0.1.0a1 (wheel + sdist) exists.

## 8. Change log of validation

- 2026-11-02: Initial record. 100 tests / 86% coverage; render chain verified;
  static-fallback and JSON-schema contracts confirmed; GitHub push observed.
- 2026-11-02: Independent 66-file evaluation set added; two confirmed false
  positives (decorative off-slide, placeholder prose) fixed with regression
  tests; judged corpus now 0 FP/0 FN, 105 tests pass.
- 2026-11-02: Formal fuzz/security/contract/performance/install test system
  added (200 collected, 194 passed/6 skipped); real stored-XSS defect in the
  HTML report fixed and covered by regression tests; package module coverage
  raised to 98%.
- 2026-11-02: Multi-strategy fix engine (collision-aware overflow chain,
  collision-free off-slide placement, resolved/unchanged/regressed/skipped
  classification) and a stdlib-only loopback web UI added; 220 collected,
  214 passed/6 skipped (216/4 with renderer), 86%/88% coverage; hands-on
  competitor re-analysis based on real installs recorded in market research.
- 2026-11-02: Build modernized (SPDX license, setuptools>=77, warning-free
  sdist/wheel); prerelease v0.1.0a1 published with two assets and 14 topics;
  bilingual FAQ added. Fixed two cross-platform CI defects (XXE test URI
  accident; cp1252 stdout encoding on both the child and the subprocess
  parent). CI now green: Ubuntu + Windows × 3.11/3.12/3.13 plus ruff; local
  suite 215 passed, 5 skipped, 0 failures.
- 2026-11-02: Unlocked real-browser screenshots via headless Edge
  (`--headless=new` + separate user-data-dir) and verified the English and
  Chinese HTML reports plus the loopback Web UI landing layout. Fixed a real
  renderer-discovery bug where a pinned/non-standard `soffice.exe` (GUI,
  no console output) failed detection; console-wrapper selection now applies
  to every Windows candidate. A follow-up Linux failure (`pathlib.Path`
  dispatching on a faked `os.name`) was fixed by using `os.path.exists`.
  CI re-verified green on bc18c7b: all 7 jobs (lint + Ubuntu/Windows ×
  3.11/3.12/3.13). 224 collected, 219 passed/5 skipped.
