# BACKLOG.md — Maintained Task Queue

Status legend: `[x]` done · `[~]` in progress · `[ ]` pending · `[-]` blocked

## P0 — crashes / data safety / wrong output / core failure

- [x] P0-1 Verify Python/pip/git environment and create virtualenv
- [x] P0-2 Safe package loader (zip-slip, duplicates, bombs, safe XML)
- [x] P0-3 Frozen data contracts and stable JSON schema
- [x] P0-4 Complete all detection rules with positive/negative tests
- [x] P0-5 Auto-fix engine with re-verification (no source overwrite)
- [x] P0-6 CLI end-to-end incl. batch, exit codes and corrupt input
- [x] P0-7 HTML report and JSON schema validation

## P1 — detection errors / major false positives / cross-platform / install

- [x] P1-1 Reproducible fixture corpus (clean, broken, Chinese, complex, cross-renderer)
- [x] P1-2 False-positive calibration on clean/legitimate complex decks
- [x] P1-3 Background/decorative/intentional-stacking recognition
- [x] P1-4 Clean virtualenv install and one-command smoke verification
- [x] P1-5 Determinism / idempotency across repeated runs

## P2 — UX / report readability / performance / config / expansion

- [x] P2-1 Bilingual HTML report with filters, locating and before/after compare
- [x] P2-2 Built-in `layoutproof demo` first-minute experience
- [x] P2-3 Configurable rules and profiles (core / full)
- [x] P2-4 GitHub Actions workflow and examples
- [x] P2-5 Performance and memory review on large decks (real measured
  trends and ~10/50 MB media decks in `tests/performance/PERF_RESULTS.md`)

## P3 — polish / docs / low value

- [x] P3-1 Bilingual README, CONTRIBUTING, SECURITY, LICENSE
- [x] P3-2 Known limitations documented (real-browser screenshots still
  unavailable; verified via HTTP integration + Node logic instead)
- [x] P3-3 Cross-renderer notes (LibreOffice / PowerPoint / WPS), static
- [x] P3-4 Pre-release v0.1.0a1 published (wheel + sdist, 14 topics,
  bilingual FAQ); stable 1.0.0 and PyPI publication remain gated

## P4 — release hardening / external experience

- [x] P4-1 Cross-platform CI green: Ubuntu + Windows × 3.11/3.12/3.13 + ruff
- [x] P4-2 Build modernization (SPDX license, setuptools>=77, warning-free)
- [x] P4-3 Hands-on competitor re-analysis on real installs
- [ ] P4-4 Stable 1.0.0 gate (all five release criteria met, no lowered bar)
- [ ] P4-5 PyPI publication and richer external experience (GIF/video/
  tutorial) without fabricated data
