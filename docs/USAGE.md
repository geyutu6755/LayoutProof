# LayoutProof Usage Guide

This is the detailed reference: every rule, every configuration knob, and the common workflows. For a short onboarding see the [README](../README.md).

## Command surface

```text
layoutproof scan   <file|dir> [options]
layoutproof fix    <file>     [options]     # safe repairs written to a new file, then re-verified
layoutproof demo   [options]                # generate a broken deck and its fixed counterpart
layoutproof --version
layoutproof --help
```

`scan` is the default: a bare path such as `layoutproof deck.pptx` is equivalent to `layoutproof scan deck.pptx`.

### `scan` options

| Flag | Default | Description |
|---|---|---|
| `target` (positional) | required | A `.pptx` file, or a directory of `.pptx` files. |
| `-r`, `--recursive` | off | Recursively find `*.pptx` under a directory. |
| `--json` | off | Emit the stable JSON report instead of the text report. |
| `--profile {core,full}` | `core` | Which rule set to run. |
| `--config FILE` | none | Load thresholds / rule toggles from a TOML or JSON file. |
| `--fail-on {error,warning,info}` | `warning` | Minimum severity that fails the build (exit `1`). |
| `-o`, `--output FILE` | stdout | Write the report to a file. |

### `fix` options

| Flag | Default | Description |
|---|---|---|
| `target` (positional) | required | A single `.pptx` file. |
| `-o`, `--output FILE` | `<name>.fixed.pptx` | Where the repaired deck is written. |
| `--no-backup` | off | Do not keep a `.bak` next to the source. |
| `--json` | off | Emit the fix report as JSON. |
| `--profile`, `--config`, `--fail-on` | as scan | Same semantics as `scan`. |

### `demo` options

| Flag | Default | Description |
|---|---|---|
| `--dir DIR` | `.` | Where demo decks would be written. |
| `--json` | off | Emit a JSON summary. |

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Clean — no issue at or above `--fail-on`. |
| `1` | Quality gate failed. |
| `2` | Usage/input error: bad arguments, no `.pptx` found, or a file that is not a valid zip/OOXML package. |
| `3` | Internal error: unexpected tool failure. |

## The rules

Rules are referenced by a stable `rule_id` in the JSON output. Severity drives the quality gate.

| `rule_id` | Severity | In `core`? | Auto-fixable? | What it detects |
|---|---|:--:|:--:|---|
| `offslide_object` | error | ✅ | ✅ | A shape or media element is fully or partially outside the slide canvas. |
| `font_too_small` | error | ✅ | ✅ | Effective font size below the readable floor (`min_font_size_pt`, default 12 pt). |
| `text_overflow` | warning | ✅ | ✅ | Estimated text height exceeds the text box, suggesting clipping or auto-shrink. |
| `unfinished_placeholder` | warning | ✅ | ✅ | Default PowerPoint prompts (`click to add title`), `TODO`/`TBD`/`FIXME`, `lorem ipsum`, or Chinese placeholders (`待补充`, `点击添加标题` …). |
| `media_broken` | error | ✅ | ❌ | An image/media relationship points to a missing, unreadable or corrupted part. |
| `broken_reference` | error | ✅ | ❌ | A hyperlink, slide jump or relationship target does not resolve to an existing part or slide. |
| `structure_anomaly` | error | ✅ | ❌ | Malformed OOXML, unsafe zip entries, duplicates, oversized payload, or missing required parts. |
| `object_overlap` | warning | ❌ (full) | ❌ | Two non-decorative objects overlap by more than `overlap_ratio_threshold` (default 0.30). |
| `low_contrast` | warning | ❌ (full) | ✅ | Text/background contrast below `min_contrast_ratio` (4.5 for body, 3.0 for large text ≥ 18 pt). |
| `blank_slide` | warning | ❌ (full) | ❌ | A slide with no visible content, placeholder text or usable media. |
| `missing_alt_text` | info | ❌ (full) | ❌ | A meaningful image has no alternative text (accessibility). |
| `cjk_typography` | warning | ❌ (full) | ✅ | Simplified-Chinese typesetting issues: kinsoku line start/end, CJK–Latin/digit spacing, mixed full/half-width punctuation. |

`core` is tuned for the first-minute experience: deterministic, low false positives. `full` adds heuristic rules (overlap, contrast, blanks, alt text, CJK typography) that are better suited to a final pre-export gate.

## Configuration reference

`--config` accepts a `.toml` or `.json` file. A `[tool.layoutproof]` table inside `pyproject.toml`-style files is also unwrapped. All keys are optional.

```toml
# --- Readability ---
min_font_size_pt = 12.0
min_contrast_ratio = 4.5          # WCAG AA for body text
large_text_pt = 18.0             # threshold for "large text"
large_text_contrast_ratio = 3.0   # relaxed ratio for large text

# --- Geometry / layout ---
overlap_ratio_threshold = 0.30    # fraction of the smaller shape
offslide_fraction_threshold = 0.05
overflow_ratio_threshold = 0.15

# --- Safety ---
max_file_size_mb = 100

# --- Quality gate ---
fail_on = "warning"              # error | warning | info

# --- Rule toggles (override the profile) ---
# enabled_rules = ["offslide_object", "font_too_small"]
# disabled_rules = ["cjk_typography"]

# --- Custom placeholder / decoration detection ---
# placeholder_patterns = ["click to add title", "待补充"]
# decorative_name_hints = ["background", "decor", "背景", "装饰"]
```

Equivalent JSON:

```json
{
  "min_font_size_pt": 14.0,
  "fail_on": "error",
  "disabled_rules": ["cjk_typography"]
}
```

### Common recipes

**Gate CI on hard errors only (ignore warnings):**

```bash
layoutproof scan deck.pptx --fail-on error
```

**Strictest gate (even info fails):**

```bash
layoutproof scan deck.pptx --fail-on info
```

**Run the full accessibility + typography suite:**

```bash
layoutproof scan deck.pptx --profile full
```

**Silence a noisy rule while keeping the rest of `full`:**

```bash
layoutproof scan deck.pptx --profile full --config quiet.toml
# quiet.toml:
# disabled_rules = ["missing_alt_text"]
```

**Whitelist only structural safety rules:**

```toml
# safety.toml
enabled_rules = ["offslide_object", "media_broken", "broken_reference", "structure_anomaly"]
fail_on = "error"
```

```bash
layoutproof scan deck.pptx --config safety.toml
```

## JSON report shape

For a single file the output is an object; for a directory scan with multiple files it is an array. Top-level keys:

```jsonc
{
  "schema_version": "1.0",
  "tool": { "name": "layoutproof", "version": "0.1.0a1" },
  "file": { "path": "...", "name": "deck.pptx" },
  "status": "ok",            // or "error" when the package cannot be opened
  "error": null,             // string when status == "error"
  "timestamp": "2026-...Z",
  "slide_count": 11,
  "summary": { "error": 2, "warning": 6, "info": 0, "total": 8 },
  "issues": [
    {
      "rule_id": "offslide_object",
      "severity": "error",
      "slide_index": 0,
      "slide_number": 1,
      "shape_id": "3",
      "shape_name": "Rectangle 2",
      "location": { "x": 12700000, "y": 2000000, "width": 2000000, "height": 1200000 },
      "normalized_location": { "x": 1.04, "y": 0.29, "width": 0.16, "height": 0.17 },
      "detail": "100% outside slide",
      "confidence": 1.0,
      "fixable": true,
      "fix_id": "move_into_slide",
      "evidence": {}
    }
  ],
  "config": { /* effective QualityConfig */ }
}
```

The machine-readable contract is versioned in [`src/layoutproof/report/schema.json`](../src/layoutproof/report/schema.json). Treat `rule_id`, `severity`, and the issue keys as stable; agents should branch on them rather than on the human text.

## Typical agent / CI loop

```bash
# 1. Generate a deck (your pipeline)
# 2. Gate it
layoutproof scan out/ --recursive --profile full --json -o report.json
# 3. Branch on exit code:
#    0 -> publish
#    1 -> read report.json, feed the issues back into generation
#    2 -> deck is malformed; regenerate from a healthy template
#    3 -> internal/tool error; alert
```
