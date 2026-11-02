# CHANGELOG.md

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and uses semantic versioning.

## [Unreleased]

## [0.2.0b1] — 2026-11-02

### Added

- Real rendering chain: isolated LibreOffice converts PPTX to PDF, and PyMuPDF
  rasterizes slides to PNG with a render manifest; the report embeds the actual
  rendered slides with issue markers and an explicit "real rendering" badge.
- 66-file independent evaluation set (52 unique authored decks plus LibreOffice
  resaves) with per-rule Precision/Recall and timing, recorded under `eval/`.
- Multi-strategy fix upgrade: collision-aware overflow chain (enlarge → shrink
  → normal autofit, never deleting content), collision-free off-slide placement
  with a safe margin, and per-issue resolved/unchanged/regressed/skipped
  classification via an additive `DetailedFixReport` that keeps the legacy JSON
  contract byte-stable.
- Local-only loopback Web UI (stdlib server, no external CDN) with upload,
  scan, fix and report flows and English/Chinese localization.
- Formal fuzz, security, contract, performance and install test suites.
- Bilingual FAQ, contributor/security governance and 14 repository topics.

### Fixed

- A real stored-XSS breakout in the HTML report's JSON data block; script
  payloads are now escaped with permanent regression tests.
- Two false positives (decorative off-slide shapes; placeholder prose).
- A renderer-discovery bug where a pinned/non-standard GUI `soffice.exe` (which
  does not return console output) failed detection: the sibling `soffice.com`
  console wrapper is now preferred for every Windows candidate. Existence
  checks use `os.path.exists` because `pathlib.Path` dispatches on `os.name`
  and broke the cross-platform tests.
- Cross-platform CI defects: the XXE test no longer relies on a Windows-only
  malformed file URI; the CLI and its subprocess tests handle UTF-8 so
  cp1252 Windows runners no longer crash.
- A version-alignment bug: the CLI/report version was a hardcoded constant
  that stayed at 0.1.0a1 after a version bump. It now reads the installed
  distribution version via `importlib.metadata`, with a regression test.

### Security

- DNS-rebinding hardening for the loopback Web UI: requests with a
  non-loopback, missing or malformed Host header are rejected with 403 via
  `is_loopback_host`, covered by dedicated tests.

### Verified

- The full suite passes on both platforms: 224 collected, 219 passed,
  5 intentionally skipped, 0 failures; core coverage 86% (gate 85%).
- On the judged corpus, core and full profiles score P=R=F1=1.0 with 0 FP /
  0 FN; 39 explicitly "unknown" cases are excluded honestly.
- The English and Chinese HTML reports and the loopback Web UI were verified
  in a real Chromium browser (headless Edge): the upload data view and the
  One-click Fix before/after comparison show 4 issues removed and resolved=4.
  With a real renderer, the Web UI embeds the actual rendered slide with
  markers before and after the fix.
- CI is green across Ubuntu + Windows × Python 3.11/3.12/3.13 plus a ruff
  job, and now lints and tests the web package as well.

### Known limitations

- macOS is not tested (no CI job); Linux coverage is Ubuntu-only.
- PyPI publication and the stable 1.0.0 release remain gated; only GitHub
  prereleases (v0.1.0a1, v0.2.0b1) are published.

## [0.1.0a1] — 2026-11-02

### Added

- Project skeleton, packaging (`pyproject.toml`) and editable install.
- Frozen data contracts: three-tier severity, 12 stable rule ids, bilingual
  rule catalogue, deterministic JSON schema v1.0 and the exit-code contract
  (0 clean / 1 issues / 2 usage / 3 internal).
- Safe in-memory PPTX loader: zip-slip, duplicate-entry, compression-bomb
  and unsafe-XML protection.
- Presentation object model: shapes, geometry, text runs, font sizes/colors,
  placeholder, decorative/background recognition and relationships.
- 12 detection rules across two profiles: a 7-rule high-confidence `core`
  profile and the 12-rule `full` profile.
- Public reproducible corpus with generators: clean, broken, Chinese,
  complex and cross-renderer categories.
- Safe auto-fix engine with six fix actions; non-fixable issues are marked
  as skipped rather than faked. The source file is never modified; the
  output and optional backup are written as new files.
- Bilingual HTML report (filters, locating, before/after comparison) and
  schema-validated JSON output.
- Built-in `layoutproof demo` one-minute first-run experience.
- GitHub Actions CI across Ubuntu/Windows and Python 3.11–3.13.
- Governance docs (`AGENTS`, `PRODUCT_SPEC`, `BACKLOG`, `DECISIONS`,
  `QUALITY_GATES`, `RUN_STATE`) and a market research report with
  competitor cards and a differentiation plan.

### Verified

- Every planted defect in the corpus is detected and located with the
  correct rule id and severity; clean and legitimate complex decks produce
  zero false positives.
- The detect → locate → auto-fix → revalidate loop closes: the demo broken
  deck goes from 4 issues to 0 while the source SHA-256 stays identical.
- Repeated scans produce identical JSON after dropping the timestamp.
- A fresh, non-editable virtualenv install and a single-command scan work.
- Test coverage of the core package is 87% (gate: 85%).

### Known limitations

- No LibreOffice/PowerPoint in the build environment, so cross-renderer
  notes are static and the HTML location preview uses normalized boxes
  rather than a rendered slide.
- No GitHub authorization is available; the README lists minimal manual
  publish steps and nothing is published or version-bumped artificially.
