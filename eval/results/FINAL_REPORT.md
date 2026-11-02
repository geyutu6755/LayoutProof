# LayoutProof eval final report

Generated from `eval/corpus/ground_truth/manifest.json`,
`eval/results/core_metrics.json`, `eval/results/full_metrics.json`,
`eval/results/distribution.json` and `eval/results/timing.json`.

## 1. Scope and boundary

- Worked only under `E:\ai测试\LayoutProof\eval\`.
- No source change was made in `src/`, `tests/`, `.github/`, `docs/` or `web/`;
  suspected source behaviors are recorded, not patched.
- Existing files under `test_fixtures/corpus/` were excluded from this eval set.
- The runner uses offline `layoutproof.scan_file(..., profile=...)`; no network,
  API key or upload is involved.

## 2. Eval directory structure

```
eval/
├─ README.md
├─ results/FINAL_REPORT.md
├─ generators/
│  ├─ common.py
│  ├─ schema.py
│  ├─ gen_python.py
│  ├─ gen_pptxgenjs.js
│  ├─ convert_libreoffice.py
│  └─ build_corpus.py
├─ corpus/
│  ├─ python_pptx/                         # 38 authored .pptx
│  ├─ pptxgenjs/                            # 14 authored .pptx + manifest_part.json
│  ├─ libreoffice/                          # 14 LO headless resave derivatives
│  └─ ground_truth/manifest.json
├─ scripts/run_eval.py
├─ results/
│  ├─ core_metrics.json
│  ├─ full_metrics.json
│  ├─ distribution.json
│  ├─ timing.json
│  └─ eval_report.md
├─ findings/
│  ├─ observed_mismatches.json
│  └─ SRC_FINDINGS.md
└─ nodeenv/                                 # local pptxgenjs@4.0.1 dependency
```

## 3. Corpus size and distribution

| Quantity | Value |
|---|---:|
| Physical `.pptx` files | 66 |
| Unique authored content ids (python-pptx + PptxGenJS) | 52 |
| LibreOffice resave derivatives | 14 |
| Manifest records | 66 |
| Scanned `ok` files | 65 |
| Expected `error` files excluded from matrix | 1 (`p37`) |
| Manifest validation problems | 0 |
| Runner missing files | 0 |

By source:

| Source | Physical files |
|---|---:|
| python_pptx | 38 |
| pptxgenjs | 14 |
| libreoffice_resave | 14 |

By content/format:

| Dimension | Breakdown |
|---|---|
| Language | en=50, zh=13, mixed=3 |
| Aspect ratio | 16:9=62, 4:3=4 |
| Judgement labels | positive=29, negative=145, explicit unknown=39 |

Positive rule coverage:

- Core: `offslide_object=3`, `text_overflow=3`, `font_too_small=2`,
  `unfinished_placeholder=3`, `media_broken=2`, `broken_reference=2`,
  `structure_anomaly=1`.
- Full-only: `object_overlap=2`, `low_contrast=4`, `blank_slide=2`,
  `missing_alt_text=2`, `cjk_typography=3`.

Negative/legal coverage includes native tables, a native chart, valid images,
native title/content layout placeholders, separated cards, absorbed labels,
grouped/named decorations, external hyperlinks, valid internal relationships,
`normAutofit`, inherited font sizes, safe margins, full-bleed backgrounds and
well-typeset Chinese punctuation/spacing.

## 4. Ground-truth method

Each manifest record stores `content_id`, relative `file`, source, language,
aspect, scenario, construction rationale, parent derivative link, expected scan
status and a list of structured judgements.

- `positive`: a defect was planted directly in coordinates, XML, zip parts,
  relationships, colors, text or alt metadata; the rule should fire.
- `negative`: the sample was deliberately legal/clean; the rule should stay
  silent.
- `unknown`: renderer/font/background-dependent or unopenable; excluded from
  P/R/F1 rather than forced into a true-negative count.
- Unlisted rules on a file are implicitly unknown.
- Matching is existence-level for TP/FP/FN; `expected_count` and severity are
  secondary checks. `expected_status=error` files do not feed the confusion
  matrix.

## 5. Metrics

### 5.1 Core profile (7 rules)

Micro-average: TP=16, FP=2, FN=0; Precision=0.8889, Recall=1.0000,
F1=0.9412.

Macro-average over 7 evaluated rules: Precision=0.9286, Recall=1.0000,
F1=0.9592.

| Rule | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| broken_reference | 2 | 0 | 0 | 8 | 1.0000 | 1.0000 | 1.0000 |
| font_too_small | 2 | 0 | 0 | 6 | 1.0000 | 1.0000 | 1.0000 |
| media_broken | 2 | 0 | 0 | 15 | 1.0000 | 1.0000 | 1.0000 |
| offslide_object | 3 | 1 | 0 | 16 | 0.7500 | 1.0000 | 0.8571 |
| structure_anomaly | 1 | 0 | 0 | 11 | 1.0000 | 1.0000 | 1.0000 |
| text_overflow | 3 | 0 | 0 | 13 | 1.0000 | 1.0000 | 1.0000 |
| unfinished_placeholder | 3 | 1 | 0 | 11 | 0.7500 | 1.0000 | 0.8571 |

### 5.2 Full profile (12 rules)

Micro-average: TP=29, FP=2, FN=0; Precision=0.9355, Recall=1.0000,
F1=0.9667.

Macro-average over 12 evaluated rules: Precision=0.9583, Recall=1.0000,
F1=0.9762.

| Rule | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| blank_slide | 2 | 0 | 0 | 23 | 1.0000 | 1.0000 | 1.0000 |
| broken_reference | 2 | 0 | 0 | 8 | 1.0000 | 1.0000 | 1.0000 |
| cjk_typography | 3 | 0 | 0 | 7 | 1.0000 | 1.0000 | 1.0000 |
| font_too_small | 2 | 0 | 0 | 6 | 1.0000 | 1.0000 | 1.0000 |
| low_contrast | 4 | 0 | 0 | 5 | 1.0000 | 1.0000 | 1.0000 |
| media_broken | 2 | 0 | 0 | 15 | 1.0000 | 1.0000 | 1.0000 |
| missing_alt_text | 2 | 0 | 0 | 14 | 1.0000 | 1.0000 | 1.0000 |
| object_overlap | 2 | 0 | 0 | 14 | 1.0000 | 1.0000 | 1.0000 |
| offslide_object | 3 | 1 | 0 | 16 | 0.7500 | 1.0000 | 0.8571 |
| structure_anomaly | 1 | 0 | 0 | 11 | 1.0000 | 1.0000 | 1.0000 |
| text_overflow | 3 | 0 | 0 | 13 | 1.0000 | 1.0000 | 1.0000 |
| unfinished_placeholder | 3 | 1 | 0 | 11 | 0.7500 | 1.0000 | 0.8571 |

Observed severity mismatches: none. Observed FN: none.

## 6. Detection timing

Latest run, per-file timing stored in `results/timing.json`:

| Profile | Scans | Total ms | Mean ms/file | Median ms | p90 ms | Max ms |
|---|---:|---:|---:|---:|---:|---:|
| core | 66 | 1184.489 | 17.947 | 14.281 | 23.420 | 124.247 |
| full | 66 | 1317.523 | 19.962 | 18.812 | 26.065 | 35.418 |

Timing is machine/process-load dependent; exact per-file `core_ms` and
`full_ms` values are retained in `timing.json`.

## 7. Real observed mismatches

1. `python_pptx/p35_probe_decorative_offslide_16x9.pptx`
   - `offslide_object`: FP=1 under both profiles.
   - Shape carries the decorative flag and decorative name but the rule only
     exempts backgrounds, so it emits an error-level finding on a deliberate
     ornament.

2. `python_pptx/p36_probe_placeholder_substring_16x9.pptx`
   - `unfinished_placeholder`: FP=2 under both profiles.
   - Normal English prose contains the substrings `todo` and `placeholder`;
     the rule uses lowercase substring matching and reports them.

Prioritized inferred gaps and borderline behavior are in
`findings/SRC_FINDINGS.md`: corrupt-package error visibility, inherited-size
blind spots, filename-only alt text, Latin-width overflow estimates,
background-only blank semantics, and fail-open contrast backgrounds.

## 8. Reproduction

```powershell
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\generators\build_corpus.py
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\scripts\run_eval.py
```

The first command rebuilds generated `.pptx` files and `manifest.json`; the
second scans core and full, writes JSON timing and Markdown reports, and emits
machine-readable mismatches under `findings/`.

## 9. Gap to the ≥50-file target

No quantitative gap: 66 physical files and 52 unique authored content ids both
exceed 50. Caveat: 14 physical files are LibreOffice round-trip derivatives
added for generator/source diversity, while the 52 authored ids come directly
from python-pptx (38) and PptxGenJS (14). Remaining evaluation ceilings are
coverage rather than count: renderer-based visual contrast, embedded/exotic
font rendering, CJK box-overflow measurement and true-render overlap could be
added later; those scenarios are currently labeled unknown or inferred gaps.
