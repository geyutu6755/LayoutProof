# AGENTS.md — Development Rules & Operational Constraints

This file is the operating contract for every human and AI agent working on
**LayoutProof**. Read it before changing code.

## 1. Product boundary (v1)

- Scope is **AI-generated PowerPoint (.pptx) automated quality acceptance only**.
- Word/.docx work is explicitly deferred. Do not add Word features in v1.
- Target users: developers/creators who generate PPTX with Claude Code, Codex,
  Qoder and similar AI coding tools.
- The v1 must close the loop: **generate → detect → locate → auto-fix → re-verify**.

## 2. Hard rules

- All core static detection runs **fully offline**: no API keys, no accounts,
  no uploads, no network calls.
- The user's original file is **read-only**. Fixes always write a new file (or an
  explicit backup); never overwrite the source.
- Never read or write files outside the project directory except the user-provided
  input path that is explicitly scanned.
- Do not fake detection with fixed/demo data. Findings must derive from the real
  parsed file.
- Every rule emits three-tier severity (`error` / `warning` / `info`) and provides
  location (slide number, shape id/name, coordinates), reason and actionable advice.
- Treat background images, decorative elements and deliberate stacking correctly to
  keep false positives low. Inherited (implicit) font sizes are not judged.

## 3. Security

- Guard against malicious/corrupt zip packages, zip-slip entry names, duplicate
  entries, compression bombs, oversized files and unsafe XML.
- XML is parsed with entity resolution and network access disabled.

## 4. Engineering

- Python 3.11+; modular, testable architecture; prefer mature dependencies.
- Static detection must work without LibreOffice. Rendered checks are optional and
  must clearly state when they did not run.
- Add a test for every new rule (positive and negative sample). A fixed bug becomes
  a permanent regression test.
- Never delete tests, lower thresholds or fabricate output to make a suite pass.

## 5. Working loop

```
read RUN_STATE → pick priority task → implement → test → independent review
→ fix → git checkpoint → update BACKLOG → next round
```

Priority order: **P0** crashes/data safety/wrong output/core failure → **P1**
detection errors/major false positives/cross-platform/install → **P2** UX/report
readability/performance/config/feature expansion → **P3** polish/docs/low value.

If a task repeatedly fails, record the root cause, isolate it and continue with
independent work. Do not loop on the same failing command.

## 6. Definition of done

- Code is committed with a real, reviewable increment.
- Tests, lint and the quality gates pass; new behavior is covered by tests.
- `RUN_STATE.md` reflects the current state and the recovery entry point.
- Unverified features are not marked complete.
