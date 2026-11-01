# QUALITY_GATES.md — Non-Skippable Quality Checks

These gates must pass before any task is marked complete or a release is cut.
Do not weaken them.

## 1. Test gates

- All tests pass: `pytest` (unit, integration, CLI e2e).
- Every detection rule has both a **positive** sample (fires) and a **negative**
  sample (does not fire).
- A fixed defect is converted into a permanent regression test.
- Corrupt/untrusted input tests: bad zip, malformed XML, zip-slip, oversized,
  duplicate entries, missing parts.
- Idempotency/determinism: running a scan twice yields identical JSON (excluding
  the timestamp).
- Coverage target: ≥ 85% for the core package; no new untested rule.

## 2. Correctness gates

- Planted defects in the fixture corpus are detected and located with the correct
  rule id and severity.
- Clean and legitimate complex decks produce no significant false positives; the
  measured FP rate is recorded in the release notes.
- Severity tiers are respected; deterministic vs heuristic confidence is honest.

## 3. Fix gates

- Fixes never overwrite the source; a new file and optional backup are created.
- Re-scan of the fixed file opens correctly and shows a real reduction in issues.
- No fix introduces a new structural error; the fixed file re-opens in python-pptx.

## 4. Report gates

- HTML report renders in a real browser; layout is inspected (not assumed).
- JSON output validates against the committed JSON schema.
- Bilingual (Chinese/English) content renders without encoding errors.

## 5. Packaging gates

- Clean virtualenv install succeeds (`pip install .` and editable install).
- One command scans a real PPTX and returns the documented exit code.
- CLI exit codes follow the contract: 0/1/2/3.

## 6. Release gates

- CHANGELOG entry describes real, verified changes.
- Unverified features are not labelled complete.
- No meaningless version bumps or empty commits.
