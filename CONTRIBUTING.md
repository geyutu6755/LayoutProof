# Contributing to LayoutProof

Thanks for helping make local PPTX quality checks more reliable. This guide covers how to set up a development environment, the conventions we follow, and what we expect before a pull request is merged.

## Development environment

LayoutProof targets **Python ≥ 3.11** (we test 3.11, 3.12 and 3.13).

```bash
git clone https://github.com/layoutproof/layoutproof.git
cd LayoutProof

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .[dev]
```

Editable install gives you the `layoutproof` command pointing at your working tree, so changes to `src/` are live immediately.

Verify the setup:

```bash
layoutproof --version
pytest
```

## Code conventions

- **Style.** Standard-library-first, type-hinted Python. We follow PEP 8 with the project's existing line length and import order; run the formatter of your choice consistent with the surrounding file. No mandatory linter is configured yet, but please keep diffs clean and self-contained.
- **Rules are the unit of behavior.** Every detection rule lives in its own module under `src/layoutproof/rules/`, subclasses the `Rule` base, and registers itself. Do not add ad-hoc checks inside the engine or CLI.
- **Stable identifiers are a contract.** New rules go through `RuleId` and `RULES` in `src/layoutproof/models.py`, with bilingual `title_en/title_zh`, `explanation_*` and `recommendation_*`. Never change the string value of an existing `rule_id` — it is part of the JSON schema consumed by agents and CI.
- **Config knobs belong in `QualityConfig`** (`src/layoutproof/config.py`), never as magic numbers in a rule. New thresholds must have a sensible default and be documented.
- **Profiles.** Put high-confidence, low-false-positive rules in `CORE_PROFILE`; experimental or heuristic-heavy rules ship only in `FULL_PROFILE`.
- **No network, no side effects.** The package must remain offline and read-only with respect to the user's source files. Do not introduce `requests`, downloads, or writes outside an explicitly requested output path.

## Testing requirements

We use `pytest`. Tests live under `tests/unit/`.

### Every rule ships yin and yang tests

For each detection rule:

- **Yin (positive):** a fixture or synthetic presentation where the rule *must* fire, asserting the exact `rule_id` (and, where relevant, `slide_number` / `shape_name` / `detail`).
- **Yang (negative):** a clean or near-clean presentation where the same rule *must not* fire. A rule that cannot be shown to stay silent on healthy decks has not earned its place in `core`.

When a rule is tuned (threshold changed, heuristic adjusted), both sides must be updated and re-verified.

### A discovered defect becomes a regression test first

If a bug reaches a released build:

1. Add the minimal failing fixture (or a synthetic generator under `test_fixtures/generators/`) that reproduces it.
2. Write the test that fails on current `main`.
3. Then fix the code.

The regression test stays in the suite forever. This is how we keep false positives and missed detections from coming back.

### Running the tests

```bash
pytest                  # full suite
pytest tests/unit/test_cjk.py -v   # one rule
pytest -k overflow
```

A green suite on your machine is required before opening a PR. CI runs the same commands on Ubuntu and Windows across Python 3.11–3.13.

## Adding or modifying a rule

1. Add the `RuleId` enum member and a bilingual `RuleSpec` in `models.py`.
2. Create `src/layoutproof/rules/<name>.py` with a `check(model)` returning `Issue` objects.
3. Register it and decide whether it belongs in `CORE_PROFILE` or only `FULL_PROFILE`.
4. Write yin + yang tests under `tests/unit/`.
5. If the rule is auto-fixable, set `fix_id` on the spec and wire the action in the fix engine (currently alpha).

## Commit and pull request flow

1. Branch from `main`: `git checkout -b feat/short-description` or `fix/short-description`.
2. Keep commits focused; write messages that say *why*, not just *what*.
3. Make sure `pytest` passes and the new behavior is covered by tests.
4. Open a pull request against `main`. In the description:
   - what problem it solves,
   - how you verified it (commands run, sample fixture),
   - any user-visible change to CLI flags, rule IDs, exit codes or the JSON schema.
5. CI must be green. Reviewers may ask for yang tests, lower false positives, or documentation updates before merge.

## Reporting bugs

Open a GitHub issue with the smallest `.pptx` that reproduces the problem, the command you ran, the observed vs. expected result, and your OS / Python version. Because LayoutProof reads files locally, please do not attach sensitive decks publicly.

## Security-sensitive changes

Anything touching zip parsing, XML parsing, file paths, or the fix engine's write path is treated as security-sensitive. Read [SECURITY.md](SECURITY.md) before opening such a PR, and flag the change in the description.
