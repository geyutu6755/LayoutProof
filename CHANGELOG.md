# CHANGELOG.md

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and uses semantic versioning.

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
