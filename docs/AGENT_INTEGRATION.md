# Agent Integration Guide

LayoutProof is designed to be driven by AI coding agents and CI pipelines. It
runs fully offline, emits stable machine-readable output, and never modifies
the source file. This guide documents the integration contract and includes a
runnable example ([`examples/agent_e2e.py`](../examples/agent_e2e.py)).

## 1. Integration model

The typical loop an agent runs:

1. Generate (or edit) a `.pptx` with your generator.
2. Scan it with LayoutProof.
3. Read the structured findings and either:
   - change the generator code and regenerate, or
   - apply the deterministic safe fixes to produce a new file.
4. Re-scan until the quality gate (exit code) is clean.

No network, API key, or account is required. The detector never uploads data.

## 2. Public Python API

```python
from layoutproof import scan_file, fix_file
from layoutproof.models import exit_code_for

result = scan_file("deck.pptx", profile="full")   # core (default) or full
for issue in result.issues:
    print(issue.rule_id, issue.severity.value, issue.slide_number, issue.shape_id)

report = fix_file("deck.pptx", "deck.fixed.pptx", profile="full", make_backup=False)
recheck = scan_file("deck.fixed.pptx", profile="full")
exit_code = exit_code_for(recheck, fail_on="warning")
```

`scan_file` never raises for a bad deck: it returns a `ScanResult` with
`status="error"` and an `error` message. `fix_file` returns a `FixReport`
listing `applied` and `skipped` fixes plus before/after summaries.

## 3. Command-line interface

```bash
layoutproof scan deck.pptx --json --profile full
layoutproof fix deck.pptx -o deck.fixed.pptx --json
layoutproof render deck.pptx --html report.html
```

`--json` emits the same stable document as the Python API. The `render`
subcommand produces real rendered slides when a renderer is available and a
disclosed static fallback otherwise — it never presents a static estimate as a
real render.

## 4. Exit codes

| Code | Meaning |
|------|---------|
| `0`  | No issues at or above the `fail-on` threshold (clean gate). |
| `1`  | Quality gate failed (findings at/above the threshold). |
| `2`  | Usage error (bad arguments, missing input). |
| `3`  | Unexpected internal error. |

The threshold is configurable with `fail_on` (`error` / `warning` / `info`;
default `warning`). Compute the same code in-process with
`exit_code_for(result, fail_on)`.

## 5. Stable identifiers and locations

- **Rule ids** are stable strings (e.g. `font_too_small`, `offslide_object`),
  not generated indices — safe to branch on.
- Each issue carries a **slide number**, a **shape id/name**, and a
  `normalized_location` (fractions of slide width/height) so an agent can
  locate the exact object. Coordinates may fall outside `[0,1]` for objects
  sitting off the slide; this is intentional, not an error.
- Findings are sorted deterministically by slide, shape and rule id.

## 6. Fixes, diffs, and unfixable items

- Each applied fix maps one-to-one to a rule and records its `action`
  (e.g. `move_into_slide`, `increase_font_size`, `autofit_text`).
- The `FixReport` includes before/after summaries and an `issues_removed`
  count, giving a direct diff. The source SHA-256 is unchanged; output is
  always a new file.
- Issues without a safe repair (e.g. `object_overlap`, `broken_reference`,
  `media_broken`, `missing_alt_text`) are returned under `skipped` with a
  reason, so the agent can hand them to a human instead of pretending they
  were resolved.

## 7. Determinism and repeatability

Repeated scans of the same file produce identical JSON once the `timestamp`
field is removed. The whole flow is safe to re-run; fixes are idempotent and
never overwrite the input.

## 8. GitHub Actions

```yaml
quality-gate:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.13"
    - run: pip install ".[dev]"
    - run: layoutproof scan path/to/deck.pptx --profile full
```

The repository's own CI already runs `ruff` and the full test matrix. Because
a renderer is not installed on the CI runners, rendered checks there fall back
to the static path and are clearly marked as such.
