# Roadmap

LayoutProof is a local-first quality-acceptance tool for AI-generated
PowerPoint (.pptx) files. This roadmap reflects the current, verified state
and the planned direction. It is not a promise of dates; items move based on
real evidence from the test suite and the independent evaluation set
(`docs/VALIDATION.md`).

## Released / working (pre-release `0.1.0a1`)

- Fully offline static detection: 12 rules across two profiles
  (`core`: 7 high-confidence rules; `full`: all 12).
- Stable machine-readable JSON validated against a bundled schema, with
  deterministic output and documented exit codes (0/1/2/3).
- Safe automatic fixes (six actions) with mandatory re-verification; the
  source file is never modified and fixes always write a new file.
- Bilingual (English/中文) self-contained HTML report with filters, locating
  and before/after comparison.
- Real rendering chain PPTX -> PDF -> PNG via an isolated LibreOffice
  install, with slides embedded in the report and issue markers overlaid;
  a disclosed static fallback when no renderer is available.
- CLI subcommands `scan`, `fix`, `render`, `demo`; GitHub Actions CI.

## In progress

- Formal quality system: fuzz/boundary, adversarial security, performance
  and memory pressure, JSON contract and install tests.
- Independent evaluation set (target 50+ diverse files) with per-rule
  Precision/Recall/F1 and detection-time metrics.
- Multi-strategy fix upgrades with a fix-quality assessment (issues solved,
  new issues introduced, layout/readability preserved).

## Next

- Local-only Web UI (localhost) with drag-and-drop, real slide preview,
  per-slide locating, one-click safe fixing and download.
- Agent integration guide and a runnable end-to-end example
  (generate PPTX -> detect -> read errors -> fix or change generator ->
  re-generate -> re-check), plus deterministic fix commands.
- Richer rendered checks: font fallback, real text clipping and newly
  introduced occlusion detection.

## Later / under consideration

- Broader renderer diagnostics and cross-renderer fidelity notes.
- Additional output formats and rule packs based on evaluation evidence.
- Word/.docx support is explicitly **deferred** and will be considered only
  after the PPTX stable release matures.

## Stable release criteria

A stable 1.0.0 is only published when reliability, accuracy, security,
user experience and formal delivery criteria all pass. See
`QUALITY_GATES.md` and `docs/VALIDATION.md`. Standards will not be lowered
to ship a version.
