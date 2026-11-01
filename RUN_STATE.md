# RUN_STATE.md — Current State & Recovery Entry

## Current phase

**Foundation complete; detection/fix/report work in progress.**

Last updated: 2026-11-02

## What is done

- Environment verified: Windows, PowerShell 7.6.4, Python 3.13.16, git 2.55.
- Virtualenv at `.venv` with python-pptx, lxml, Pillow, pytest, jsonschema, jinja2.
- Package installed in editable mode; `layoutproof` console entry point works.
- Frozen contracts in `src/layoutproof/models.py` (12 rules, 3-tier severity,
  bilingual rule catalogue, JSON schema v1.0).
- Safe loader in `src/layoutproof/parsing/package.py`; object model in
  `parsing/presentation.py`; geometry in `parsing/geometry.py`.
- Seed rules implemented and verified: `offslide_object`, `font_too_small`.
- Smoke test proves both rules detect planted defects and no FP on clean shapes.
- Market research delivered: `docs/MARKET_RESEARCH.md`.

## What is next

1. Remaining detection rules (text overflow, overlap, contrast, blank, placeholder,
   media, references, alt text, CJK typography) with unit tests.
2. Reproducible fixture corpus and generator scripts.
3. Fix engine + re-verification; full CLI e2e.
4. HTML/JSON reports; packaging and publish docs.

## How to recover / resume

1. Confirm venv: `.venv\Scripts\python.exe -m pytest -q`
2. Read `BACKLOG.md` and pick the first open highest-priority item.
3. Run the working loop in `AGENTS.md`; commit each real increment.
4. Update this file and `BACKLOG.md` after every checkpoint.

## Blockers

None. (No GitHub authorization has been confirmed yet; publishing may require
manual steps — see `DECISIONS.md`.)
