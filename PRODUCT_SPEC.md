# PRODUCT_SPEC.md — Requirements & Acceptance Criteria

## Product

LayoutProof — Local-first Office Document Quality Assurance. v1 focuses on
automated quality acceptance of **AI-generated `.pptx`** files.

## Goals

1. Detect layout/readability/structure/accessibility defects in PPTX.
2. Locate every defect precisely (slide, shape, coordinates).
3. Auto-fix safe, deterministic classes of defects without touching the source.
4. Re-verify after fixing and prove the issue count really drops.
5. Be trivially callable by AI agents: stable JSON schema, explicit exit codes.
6. Deliver value in minutes via a single command and a built-in `demo`.

## Detection scope (v1)

| Rule id | Severity | What it catches |
|---|---|---|
| `offslide_object` | error | shapes/media fully or partially outside the slide |
| `text_overflow` | warning | suspected text overflow or clipping |
| `object_overlap` | warning | unexpected occlusion/collision of non-decorative objects |
| `font_too_small` | error | explicit font size below readable threshold |
| `low_contrast` | warning | text/background contrast below threshold |
| `blank_slide` | warning | slides with no visible content |
| `unfinished_placeholder` | warning | placeholder prompts, TODO/TBD, Lorem ipsum |
| `media_broken` | error | missing/unreadable/corrupt media parts |
| `broken_reference` | error | unresolvable hyperlinks/slide jumps/relationships |
| `structure_anomaly` | error | malformed package, unsafe entries, missing parts |
| `missing_alt_text` | info | meaningful images without alt text |
| `cjk_typography` | warning | kinsoku, CJK-Latin spacing, full/half-width punctuation |

## Functional requirements

- **CLI**: `scan`, `fix`, `demo`; single file or directory, batch and recursive.
- **Output**: deterministic JSON (schema versioned) and a bilingual local HTML report.
- **Exit codes**: 0 clean, 1 quality gate failed, 2 usage/input error, 3 internal.
- **Config**: TOML/JSON thresholds, rule enable/disable, fail-on severity.
- **Fix**: writes `<name>.fixed.pptx` (and optional backup), records each action,
  re-scans and reports before/after counts.
- **Test corpus**: reproducible fixtures covering clean, broken, Chinese fonts,
  complex layouts and cross-renderer differences, with generator scripts committed.

## Core quality metrics

- Detection accuracy (planted defects found / total planted).
- False-positive rate on clean/legitimate complex files.
- First-use experience (time/commands to first real result).
- AI-agent integration difficulty (JSON stability, exit codes, scriptability).

## Acceptance criteria

- A new user can install in a clean virtualenv and scan a real PPTX with one command.
- Every planted defect class is detected and located; each rule has positive and
  negative tests.
- No significant false positives on clean/complex files; FP rate is recorded.
- Repeated runs produce identical, deterministic output.
- Auto-fix produces a new openable file and re-verification shows fewer issues.
- HTML report is actually rendered and inspected; JSON validates against its schema.
- Unit, integration, CLI e2e, corrupt/untrusted input and idempotency tests all pass.
