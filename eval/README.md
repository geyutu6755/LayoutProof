# LayoutProof offline evaluation corpus

This directory contains a self-contained, repeatable evaluation set for the
LayoutProof static PPTX quality detector. It does **not** modify `src/`,
`tests/`, `.github/`, `docs/` or `web/`; all generators, corpus files,
reference labels, metrics and findings live here.

## 1. Directory layout

```
eval/
├─ README.md
├─ generators/
│  ├─ common.py                 # shared python-pptx / zip-surgery helpers
│  ├─ schema.py                 # judgement schema, severity map, scope helper
│  ├─ gen_python.py             # 38 python-pptx authored decks + GT records
│  ├─ gen_pptxgenjs.js          # 14 PptxGenJS authored decks + GT part manifest
│  ├─ convert_libreoffice.py     # 14 LibreOffice headless resave derivatives
│  └─ build_corpus.py           # orchestrates all sources and writes manifest
├─ corpus/
│  ├─ python_pptx/*.pptx       # 38 authored files
│  ├─ pptxgenjs/*.pptx          # 14 authored files (+ manifest_part.json)
│  ├─ libreoffice/*.pptx        # 14 LO resave derivatives
│  └─ ground_truth/manifest.json# merged structured ground truth
├─ scripts/run_eval.py           # core/full scan, confusion matrix, timing, reports
├─ results/
│  ├─ core_metrics.json
│  ├─ full_metrics.json
│  ├─ distribution.json
│  ├─ timing.json
│  ├─ eval_report.md
│  └─ FINAL_REPORT.md
├─ findings/
│  ├─ observed_mismatches.json   # machine-readable FP/FN/count/severity deviations
│  └─ SRC_FINDINGS.md           # prioritized src observations (no src edits made)
└─ nodeenv/                      # local-only pptxgenjs dependency (never global)
```

## 2. How to reproduce

From the project root (`E:\ai测试\LayoutProof`):

```powershell
# 1. (Re)generate corpus and merged ground truth
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\generators\build_corpus.py

# 2. Run core + full profiles and write results/
E:\ai测试\LayoutProof\.venv\Scripts\python.exe eval\scripts\run_eval.py
```

Notes:

- The Python interpreter already resolves `layoutproof` from `src/`; the runner
  also inserts `src/` on `sys.path` defensively.
- PptxGenJS was installed locally under `eval/nodeenv` with `npm install
  pptxgenjs`; no global package was installed.
- LibreOffice conversion uses `.rendertools/lo/program/soffice.com`. If it is
  unavailable, `build_corpus.py` warns and skips the derivative bucket; authored
  files and metrics still run.
- `build_corpus.py` refreshes generated `.pptx` files under `eval/corpus`; it
  never writes outside `eval/`.

## 3. Ground-truth design

### 3.1 Record schema (`corpus/ground_truth/manifest.json`)

Each record has:

| Field | Meaning |
|---|---|
| `content_id` | stable authored scenario id; derivatives append `_lo` |
| `file` | path relative to `corpus/` |
| `source` | `python_pptx`, `pptxgenjs`, or `libreoffice_resave` |
| `language` | `en`, `zh`, or `mixed` |
| `aspect` | `16:9` or `4:3` |
| `scenario` / `description` | scenario slug and construction rationale |
| `parent` | parent authored file for LO derivatives, otherwise `null` |
| `expected_status` | `ok` or `error` (the truncated-zip probe) |
| `judgements[]` | one structured expectation per rule |

A judgement contains:

- `rule_id` (one of the 12 stable rule ids);
- `expect`:
  - `positive` — a defect was deliberately constructed; the rule should fire;
  - `negative` — a deliberately clean/legal sample; the rule must stay silent;
  - `unknown` — renderer/font/background dependent or unopenable; excluded
    from P/R/F1 and listed in the report;
- `profiles`: `both` (core + full), `core`, or `full`;
- `expected_severity` from the stable rule catalogue;
- `basis` (why the label follows from construction), `note`, optional
  `expected_count`.

### 3.2 Matching method

`scripts/run_eval.py` uses an **existence-level** confusion matrix, which is
robust for heuristic rules:

- positive judgement + detector output count `>= 1` => TP; otherwise FN;
- negative judgement + detector output count `>= 1` => FP; otherwise TN;
- `unknown` labels and `expected_status=error` files are excluded;
- rules a file does not mention are implicitly unknown, so TN support is not
  manufactured;
- `expected_count` and severity are recorded as secondary checks and surfaced
  in flags/mismatches, not used to change P/R/F1.

`core` evaluates the 7 core rules; `full` evaluates all 12. Core-rule
judgements are scored under both profiles; full-only rules only under `full`.

### 3.3 Why labels are credible

Positive labels come from direct construction: coordinates beyond slide bounds,
explicit sub-threshold font sizes, tiny/no-wrap text boxes, corrupted or
missing media parts, dangling/missing internal relationships, unsafe zip
entries, placeholder prompt strings, overlap ratios, contrast ratios, missing
alt text, and CJK punctuation/spacing violations. Negative labels come from
explicit clean constructions (valid images, valid internal targets, absorbed
card labels, grouped decorations, named decorative elements, `normAutofit`,
inherited sizes, safe margins, external URLs, proper Chinese punctuation).
Labels were authored before inspecting detector output; the runner then compares
construction intent against actual findings.

## 4. Corpus coverage

Latest generated corpus: **66 physical files** = 52 authored unique content ids
(38 python-pptx + 14 PptxGenJS) + 14 LibreOffice resave derivatives.

- Sources: `python_pptx=38`, `pptxgenjs=14`, `libreoffice_resave=14`.
- Languages: `en=50`, `zh=13`, `mixed=3` (derivatives inherit parent labels).
- Aspects: `16:9=62`, `4:3=4`.
- Constructed positive coverage (29 positive judgement records):
  - core: `offslide_object=3`, `text_overflow=3`, `font_too_small=2`,
    `unfinished_placeholder=3`, `media_broken=2`, `broken_reference=2`,
    `structure_anomaly=1`;
  - full-only: `object_overlap=2`, `low_contrast=4`, `blank_slide=2`,
    `missing_alt_text=2`, `cjk_typography=3`.
- Judgement labels in the merged manifest: `positive=29`, `negative=145`,
  explicit `unknown=39`; rules not listed on a file remain implicitly unknown.
- Legal/negative coverage includes native tables, a native chart, valid images,
  native title/content layout placeholders, absorbed labels, grouped
  decorations, named decorative shapes, partial picture captions, external
  hyperlinks, valid internal rels, `normAutofit`, inherited font sizes, safe
  margins, full-bleed backgrounds, and well-typeset Chinese text.

## 5. Metrics outputs

`results/eval_report.md` is the human-readable summary; JSON files retain exact
counts and per-file timing. `findings/SRC_FINDINGS.md` ranks observed FP/FN
patterns and inferred coverage gaps. `findings/observed_mismatches.json` stores
the machine-readable evidence behind those observations.

## 6. Boundary and honesty notes

- No deterministic detection uses network access, API keys, or uploaded files.
- The truncated-zip probe (`p37`) is expected to return `status=error`; it is
  excluded from the confusion matrix rather than counted as a rule hit.
- LO derivatives are round-trip artifacts, not independent authored decks;
  geometry/contrast heuristics on them are marked `unknown`.
- Observed FP samples are intentionally retained as negative expectations so
  the runner can quantify real false positives; they are documented in
  `findings/SRC_FINDINGS.md` rather than patched in `src/`.
