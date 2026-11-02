#!/usr/bin/env python3
"""Runnable end-to-end example for AI agents.

This simulates a generator (the way an AI coding tool builds a .pptx), then
drives the whole LayoutProof loop using only the public, stable API:

    generate a deck -> scan -> read the structured errors -> apply safe fixes
    -> re-scan to confirm the gate now passes

Everything is offline, the source file is never modified, and the fixes are
written to a new file. Run it with:

    python examples/agent_e2e.py
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof import ScanResult, fix_file, scan_file
from layoutproof.models import EXIT_CLEAN, exit_code_for


def generate_deck(path: Path) -> None:
    """Stand-in for an AI generator: a deck with a couple of real defects."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # An 8pt run is below the readable minimum (font_too_small).
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(4), Inches(0.8))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "This run uses an 8pt font and is hard to read."
    run.font.size = Pt(8)

    # A shape parked fully outside the right edge (offslide_object).
    off = slide.shapes.add_textbox(Inches(11.5), Inches(0.5), Inches(2.5), Inches(0.8))
    off.text_frame.paragraphs[0].add_run().text = "Off-slide note"

    prs.save(str(path))


def main() -> int:
    work = Path(__file__).resolve().parent / "_agent_e2e_out"
    work.mkdir(parents=True, exist_ok=True)
    deck = work / "generated.pptx"
    fixed = work / "generated.fixed.pptx"

    # 1. The generator produces a deck.
    generate_deck(deck)

    # 2. Scan it. The result is a stable, machine-readable object.
    result: ScanResult = scan_file(deck, profile="full")
    print(f"status={result.status} total_issues={result.summarize().total}")
    for issue in result.issues:
        print(f"  - {issue.rule_id} [{issue.severity.value}] slide {issue.slide_number}")

    # 3. Apply the deterministic safe fixes (source stays read-only).
    report = fix_file(deck, fixed, profile="full", make_backup=False)
    print(f"applied={len(report.applied)} skipped={len(report.skipped)}")

    # 4. Re-scan the new file and evaluate the quality gate.
    recheck = scan_file(fixed, profile="full")
    code = exit_code_for(recheck, fail_on="warning")
    print(f"recheck total_issues={recheck.summarize().total} exit_code={code}")
    return EXIT_CLEAN if code == EXIT_CLEAN else 1


if __name__ == "__main__":
    raise SystemExit(main())
