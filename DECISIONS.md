# DECISIONS.md — Technical Decisions

Record significant decisions with context and consequences.

## D-001 Language and runtime

- **Decision:** Python 3.11+ (developed on 3.13).
- **Why:** Rich OOXML ecosystem, fast onboarding, matches the target developers.
- **Consequence:** Distributed via pip; stdlib `argparse` for the CLI.

## D-002 PPTX parsing stack

- **Decision:** Use `python-pptx` for high-level shapes plus direct `lxml` access
  for details python-pptx does not expose (alt text, decorative flag, autofit,
  hidden state).
- **Why:** Avoids re-implementing OOXML object mapping while retaining full control.
- **Consequence:** Two views of the same file are reconciled in one object model.

## D-003 Safe, in-memory package handling

- **Decision:** Never extract to disk; validate zip entries and parse XML with
  entity resolution and network disabled.
- **Why:** Mitigates zip-slip, bombs and unsafe XML on untrusted AI-generated files.

## D-004 Three-tier severity and confidence

- **Decision:** `error` / `warning` / `info`; heuristic rules carry <1.0 confidence.
- **Why:** Lets agents and CI separate deterministic failures from judgment calls.

## D-005 False-positive-first calibration

- **Decision:** Default `core` profile runs only high-confidence rules; inherited
  font sizes are not judged; background/decorative objects are recognized.
- **Why:** Research shows agents disable a gate that floods them with false positives.

## D-006 Non-destructive fixing with re-verification

- **Decision:** Fixes write a new file (and optional backup), then re-scan and
  report before/after counts.
- **Why:** Rewriting a user's deck silently is how content gets lost; the source
  must remain untouched.

## D-007 Renderer is optional

- **Decision:** Static detection fully works without LibreOffice; rendered checks
  are opt-in and announce when they did not run.
- **Why:** Guarantees a usable offline default across environments.

## D-008 Differentiation focus

- **Decision:** Invest in Simplified Chinese typography, low FP calibration, the
  safe fix/rerun loop, and a built-in `demo`; do not rebuild capabilities already
  solved by archforge / ooxml-integrity / accessibleoffice.
- **Why:** Evidence in `docs/MARKET_RESEARCH.md`.

## D-009 Publishing

- **Decision:** Keep full local git history. If no valid GitHub authorization is
  present, document minimal manual publish steps instead of faking a release.
