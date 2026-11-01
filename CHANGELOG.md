# CHANGELOG.md

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and uses semantic versioning.

## [0.1.0a1] — 2026-11-02

### Added

- Project skeleton, packaging (`pyproject.toml`) and editable install.
- Frozen data contracts: three-tier severity, 12 stable rule ids, bilingual rule
  catalogue, deterministic JSON schema v1.0 and exit-code contract.
- Safe in-memory PPTX loader: zip-slip, duplicate entry, compression-bomb and
  unsafe-XML protection.
- Presentation object model: shapes, geometry, text runs, font sizes/colors,
  placeholder, decorative/background recognition and relationships.
- Geometry primitives and EMU/unit conversions.
- First two detection rules: `offslide_object` and `font_too_small`.
- CLI scaffold with `scan`, `fix`, `demo` subcommands and JSON output.
- Governance docs: AGENTS, PRODUCT_SPEC, BACKLOG, RUN_STATE, QUALITY_GATES,
  DECISIONS.
- Market research report with seven competitor cards and a differentiation plan.

### Verified

- Smoke test: both seed rules detect planted defects and produce no false positive
  on a clean in-slide title; JSON output is well-formed and the CLI returns the
  expected exit code.
