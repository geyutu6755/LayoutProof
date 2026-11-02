# Findings for LayoutProof source rules (observations only)

This file records findings discovered while building and scoring the eval
corpus. **No file under `src/`, `tests/`, `.github/`, `docs/` or `web/` was
modified**; remediation should be implemented separately by the product team.

Evidence basis:

- machine-readable deviations: `findings/observed_mismatches.json`
- exact counts: `results/core_metrics.json`, `results/full_metrics.json`
- rule source inspected during evaluation: `src/layoutproof/rules/*.py` and
  `src/layoutproof/engine.py`

Latest run summary (existence-level; unknown/error files excluded):

| profile | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| core (7 rules) | 16 | 2 | 0 | 0.8889 | 1.0000 | 0.9412 |
| full (12 rules) | 29 | 2 | 0 | 0.9355 | 1.0000 | 0.9667 |

No severity mismatches were observed. The two FP patterns below are retained in
the corpus as deliberate negative probes, so they are real measured deviations,
not guessed issues.

---

## P1 — Observed FP (error severity): decorative/off-slide element not exempt

- **Rule:** `offslide_object`
- **Evidence:** `corpus/python_pptx/p35_probe_decorative_offslide_16x9.pptx`
  has one shape named `background ornament` that also carries the OOXML
  `<p:decorative/>` flag. Ground truth marks `offslide_object` as a deliberate
  negative. Both profiles report `FP:offslide_object`, count 1.
- **Why it fires:** the off-slide rule skips only `is_background`; it does not
  consult `is_decorative` or the decorative name hints that `object_overlap`,
  `missing_alt_text` and `blank_slide` already use.
- **Impact:** **high** because this rule maps to `error` severity and can fail a
  quality gate even when the offending shape is an intentional ornament outside
  the visible frame.
- **Suggested direction (do not implement here):** exempt shapes carrying the
  decorative flag or matching decorative name hints, or downgrade such cases to
  `warning`/`info`; keep `error` for content-bearing shapes outside the canvas.

## P2 — Observed FP (warning severity): placeholder patterns use substring matching

- **Rule:** `unfinished_placeholder`
- **Evidence:** `corpus/python_pptx/p36_probe_placeholder_substring_16x9.pptx`
  contains normal English prose:
  - “The team archived the **todo** list before the quarterly review.”
  - “The **placeholder** API contract was approved by the committee.”
  Ground truth marks the rule negative; both profiles report
  `FP:unfinished_placeholder`, count 2.
- **Why it fires:** the rule lowercases the whole shape text and checks whether
  any prompt pattern (`todo`, `placeholder`, etc.) appears as a substring.
  Common legitimate words/phrases containing those substrings therefore match.
- **Impact:** **medium-high** for real decks: plausible prose and technical
  vocabulary can produce false warnings; accumulated FPs erode trust in the
  warning channel.
- **Suggested direction:** use standalone token/word-boundary matching, prefer
  directive markers (`TODO:`, `TBD`, `Click to add …`, `Lorem ipsum …`), and add
  a small exclusion list for legitimate compounds; keep Chinese prompt phrases
  anchored to full prompt idioms rather than short substrings.

## P3 — Coverage/visibility gap: unopenable/corrupt packages return `status=error` with no structured rule finding

- **Rule:** `structure_anomaly`
- **Evidence:** `corpus/python_pptx/p37_error_truncated_zip.pptx` was truncated
  after save. `scan_file` returns `status="error"` (“File is not a zip file”)
  and an empty issue list; it does not emit a `structure_anomaly` issue.
- **Why it happens:** `engine.scan_file` catches `PackageError`/open failures and
  returns an error result before the deterministic package anomalies are
  appended. `SafePackage` anomalies are only surfaced after `build_model`
  succeeds, so a truncated or otherwise unopenable package has no structured
  finding even though it is precisely the kind of malformed package this rule
  describes.
- **Impact:** **medium-high** for robustness/security reporting: corrupt or
  truncated files disappear from rule-based summaries and only appear as a
  non-zero CLI/JSON status; downstream consumers that aggregate issues by rule
  will under-report package corruption.
- **Suggested direction:** when opening fails, still serialize the package-level
  anomalies that `SafePackage` collected (unsafe entry names, missing required
  parts, duplicate entries, size limits) into either a `structure_anomaly`
  finding or a dedicated structured error payload; separate “cannot parse” from
  “parsed with anomalies”.

## P4 — Inferred gap: inherited font sizes and inherited-size overflow are invisible

- **Rules:** `font_too_small`, `text_overflow`
- **Evidence/rationale:** `corpus/python_pptx/p08_clean_inherited_font_16x9.pptx`
  was constructed as a clean sample because both rules skip shapes without an
  explicit run size. This is a deliberate anti-FP design, but it means text
  that inherits a tiny size from a layout/master placeholder cannot be reported
  offline without resolving theme defaults.
- **Impact:** **medium**; likely low FP risk but possible FN risk on templates
  whose body placeholders define small sizes.
- **Suggested direction:** optionally resolve placeholder/master default sizes
  and report inherited cases at lower confidence, clearly labelled as inferred.

## P5 — Inferred accessibility gap: any non-empty `descr` counts as alt text

- **Rule:** `missing_alt_text`
- **Evidence/rationale:** the parser sets `has_alt_text` when `descr` is
  non-empty. PptxGenJS writes a default `descr="preencoded.png"` when `altText`
  is omitted; the eval generator strips that default to create a positive sample,
  but real exports may retain filename-only or auto-generated descriptions.
  Such text is not a meaningful screen-reader description.
- **Impact:** **medium**; accessibility findings can be missed when an image has
  only a filename or generic placeholder description.
- **Suggested direction:** treat filename-like defaults (e.g. `*.png`,
  `image1`) and strings identical to the shape name as absent/weak alt text, and
  optionally emit an `info` suggestion for short generic descriptions.

## P6 — Inferred heuristic limitation: text overflow uses Latin glyph advance only

- **Rule:** `text_overflow`
- **Evidence/rationale:** the offline estimate uses a constant 0.45em glyph
  width for Latin text; CJK glyphs are wider and line breaking differs. The
  corpus currently proves CJK typography violations but has no CJK box-overflow
  positive sample. Wrapped Chinese text near a narrow box could be estimated
  incorrectly in either direction.
- **Impact:** **medium** for the mixed-language target audience; low on the
  deterministic rules but relevant to this warning heuristic.
- **Suggested direction:** use script-aware average advance widths; compare
  against optional rendered measurements where available, and label uncertainty
  through confidence.

## P7 — Borderline behavior: background-only slides are reported as blank

- **Rule:** `blank_slide`
- **Evidence/rationale:** the rule ignores background/decorative shapes but
  still reports a slide when it contains no text or non-background media. A
  designed template with only a full-bleed background image can therefore be
  flagged as blank depending on how the background is represented.
- **Impact:** **low-medium**; depends on product definition of “blank”.
- **Suggested direction:** define explicitly whether a background-only slide is
  blank; if not, exclude slides whose only visible shape is an exempt background
  picture; otherwise keep the warning but document the semantic choice.

## P8 — Inferred limitation: contrast fails open on unresolved backgrounds

- **Rule:** `low_contrast`
- **Evidence:** `corpus/python_pptx/p14_clean_bg_and_content_16x9.pptx` marks
  this rule `unknown` because text sits over a full-bleed picture; the rule
  deliberately emits nothing when foreground/background colors cannot both be
  resolved. This avoids false positives but may miss low contrast over photos
  or theme accent fills.
- **Impact:** **low-medium**; acceptable offline, but a known detection ceiling.
- **Suggested direction:** add an optional renderer-backed sample or an `info`
  hint for unresolvable contrast pairs; keep the static rule fail-open.

## P9 — Lower priority: overlap heuristics and derivative coverage

- `object_overlap` correctly skips grouped children, absorbed card labels,
  named decorations and picture captions covering less than 90% of a picture
  (verified by negative samples); no observed FP/FN. Ratio still uses the smaller
  rectangle, so thin decorative bands may be under-assessed; revisit only after
  the higher-ranked findings are addressed.
- The 14 LibreOffice derivatives carry negative GT only; geometry/contrast
  judgements are marked `unknown` because LO rewrites coordinates and fonts.
  They therefore broaden source coverage without injecting heuristic noise into
  the confusion matrix. A future phase can add render-based LO positive samples.

## Maintenance note

After any rule change, rerun:

```powershell
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\generators\build_corpus.py
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\scripts\run_eval.py
```

and compare `results/eval_report.md` plus `findings/observed_mismatches.json`.
The current corpus must not be treated as a substitute for renderer-based
evaluation; its strength is deterministic, offline, reproducible detection of
structure/geometry/text/package defects.
