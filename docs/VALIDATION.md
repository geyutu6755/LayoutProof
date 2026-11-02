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
- Linux/macOS: **not tested** — no such host available. Cross-platform support
  is not claimed beyond the pure-Python/offline design intent.

## 2. Test & coverage status

- Full suite: **100 tests pass** (observed 2026-11-02).
- Line coverage: **86%** (`pytest --cov=layoutproof`), render module
  backend 82% / engine 88% / images 91%.
- Coverage is treated as a signal, not the goal; uncovered branches are
  mostly defensive `except` paths and renderer-specific edge cases.

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

## 5. Detection accuracy (current corpus)

- Clean decks (`clean_basic`, `clean_agenda`, `complex_overloaded`,
  `crossrender_native_16x9`): zero false positives.
- `broken_all.pptx`: 11 planted defects detected (13 findings total across
  severities; multiple placeholders on slide 7).
- `chinese_typesetting.pptx`: good slide 0 findings; bad slide 2 CJK findings
  (kinsoku line start, half-width punctuation).
- `crossrender_flat_4x3.pptx`: 1 real off-slide finding (title box past 4:3).
- `broken_structure.pptx`: status=error, "not a valid zip/pptx package".
- A larger independent evaluation set and per-rule Precision/Recall are
  tracked separately (see `eval/`); not yet at the 50-file target.

## 6. Security checks (status)

- In-memory zip loader guards against zip-slip, duplicate entries,
  compression bombs and unsafe XML (entity resolution/network disabled).
- Detailed adversarial tests (fuzz, malformed relationships, XSS, large-file
  memory/time) are being formalized; results appended here as they land.

## 7. Not verified / blocked

- Edge headless `--screenshot` currently produces no file in this environment
  (even for trivial HTML), so browser-rendered report screenshots and Web UI
  automation could not be captured via that path.
- No `gh` CLI; GUI automation backends unavailable in prior attempts.
- Linux/macOS runtime behavior; WPS/PowerPoint-specific rendering fidelity.
- PyPI publishing: not performed (requires separate authorization).

## 8. Change log of validation

- 2026-11-02: Initial record. 100 tests / 86% coverage; render chain verified;
  static-fallback and JSON-schema contracts confirmed; GitHub push observed.
