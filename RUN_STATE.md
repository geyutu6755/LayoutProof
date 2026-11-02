# RUN_STATE.md — Current State & Recovery Entry

## Current phase

**v1 loop closed with real rendering, multi-strategy fixes, an offline
loopback web UI, and a 66-file independent evaluation. A pre-release
v0.1.0a1 is published; CI is green across the full Ubuntu + Windows
matrix. Not yet a stable 1.0.0.**

Last updated: 2026-11-02

## What is done

- Environment: Windows, PowerShell, Python 3.13.16, git 2.55; virtualenv at
  `.venv` (python-pptx, lxml, Pillow, pytest, pytest-cov, jsonschema,
  jinja2, PyMuPDF, ruff); editable install; `layoutproof` console entry works.
- Frozen contracts in `models.py`: 12 stable rule ids, three-tier severity,
  bilingual catalogue, deterministic JSON schema, exit codes 0/1/2/3.
- Safe loader in `parsing/package.py` (zip-slip, duplicate, compression-bomb,
  unsafe-XML protection); object model and geometry modules.
- 12 detection rules, positive/negative tests; `core` (7 rules) and `full`
  (12 rules) profiles; all thresholds read from config.
- Real rendering in `render/`: isolated LibreOffice PPTX -> PDF -> PyMuPDF
  PNG, render manifest, honest `static_fallback` when no renderer exists.
- Multi-strategy fix engine in `fix/engine.py`:
  - overflow chain: enlarge (collision-aware) -> shrink (never below min pt)
    -> normAutofit; content is never deleted;
  - off-slide repair with 0.1 in margin and deterministic collision-free
    placement; oversized shapes flagged for manual resize;
  - per-issue classification resolved/unchanged/regressed/skipped;
  - `fix/outcomes.py` `DetailedFixReport` is additive — the legacy FixReport
    JSON schema stays byte-stable.
- Offline loopback web UI in `web/`: stdlib-only, loopback-bound, upload
  zip audit, scan/fix/render/report flows, EN/ZH, no external CDN.
- Formal quality/security suite: fuzz, security, contract, performance,
  install tests; a stored-XSS defect in the HTML report was found and fixed.
- Independent evaluation: 66 physical decks (52 unique authored), per-rule
  Precision/Recall; after two false-positive fixes, P=R=F1=1.0 on judged
  items (39 unknown excluded honestly).
- Open-source engineering: LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT,
  ROADMAP, issue templates, CI with ruff lint; market research with a
  hands-on re-analysis (real competitor installs) in `docs/MARKET_RESEARCH.md`.
- Release & discoverability: annotated tag `v0.1.0a1` with a prerelease
  GitHub Release (wheel + sdist assets), 14 repository topics, and a
  bilingual `docs/FAQ.md`.
- Cross-platform CI is green: Ubuntu + Windows on Python 3.11/3.12/3.13,
  plus the ruff lint job. Two platform-specific defects were fixed:
  - the XXE local-entity test no longer relies on a Windows-only malformed
    file URI and now asserts the real security property on both platforms;
  - the CLI reconfigures stdout/stderr to UTF-8, and the CLI subprocess
    tests decode as UTF-8, removing cp1252 encode/decode crashes.

## Verified metrics

- Local Windows suite: 220 collected, 215 passed, 5 skipped (environment
  gates: 1 install cycle, 2 no-renderer, 2 perf), 0 failures / 0 errors.
- CI matrix: all 6 test jobs (Ubuntu + Windows × 3.11/3.12/3.13) and the
  ruff lint job pass on the latest commit.
- Coverage: 86% without renderer, 88% with renderer.
- Eval corpus (judged items): core and full micro P=R=F1=1.0, 0 FP / 0 FN.
- Deterministic JSON after dropping the timestamp; fix preserves source
  SHA-256 and always writes a new file; report success requires zero
  regressions.

## Known limitations

- macOS is not tested in CI (no job); Linux coverage is Ubuntu-only.
- Headless Edge screenshots do not persist; web UI visual layout is
  verified via HTTP integration + Node logic tests, not a real-browser shot.
- The full isolated venv install/upgrade cycle stays skipped unless
  `LAYOUTPROOF_INSTALL_TEST=1`; no GB-scale bomb is constructed (quota
  thresholds are triggered instead).
- Eval P=R=F1=1.0 holds only for this corpus's judged items; 39 unknown
  cases are excluded, real-world edge cases remain.
- No PyPI publication and no stable release yet; only the GitHub
  prerelease v0.1.0a1 exists.

## How to recover / resume

1. Confirm the environment: `.venv\Scripts\python.exe -m pytest -q`
2. Read `BACKLOG.md` and `docs/VALIDATION.md` for the next open item.
3. Follow the working loop in `AGENTS.md`; commit each real increment.
4. Update this file, `BACKLOG.md` and `docs/VALIDATION.md` after every checkpoint.
