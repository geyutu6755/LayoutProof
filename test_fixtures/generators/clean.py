"""Clean, well-laid-out decks.

These are the negative-control fixtures used to measure the false-positive
rate.  Every object is on-slide, font sizes are >= 18 pt, text fits its box,
pictures carry alt text, and contrast is comfortable.
"""

from __future__ import annotations

from pathlib import Path

from pptx.util import Emu, Inches, Pt

from genutil import (CJK_FONT, SLIDE_H, SLIDE_W, add_pic, add_textbox, add_title,
                     blank_slide, new_pres, save)

DARK = None  # placeholder


def _basic(corpus: Path) -> dict:
    prs = new_pres()

    # Slide 1: title + body paragraph, picture with alt text.
    s = blank_slide(prs)
    add_title(s, "Clean Deck — Quarterly Review")
    add_textbox(
        s,
        "This deck demonstrates a healthy layout: every shape sits inside the "
        "slide, body text is large enough to read, and the picture below has "
        "alternative text for screen readers.",
        Emu(600000), Emu(1500000), Emu(10800000), Emu(1800000),
        size=Pt(20),
    )
    add_pic(s, (90, 150, 200), Emu(600000), Emu(3600000), Emu(4200000), Emu(2400000),
            alt="Line chart placeholder showing steady quarterly growth")

    # Slide 2: two-column bullets, comfortably spaced.
    s = blank_slide(prs)
    add_title(s, "Key Takeaways")
    add_textbox(
        s,
        "• Revenue grew 12% quarter over quarter\n"
        "• Customer churn stayed flat at 2.1%\n"
        "• New onboarding flow reduced time-to-value by 30%",
        Emu(600000), Emu(1500000), Emu(10800000), Emu(3200000),
        size=Pt(20),
    )

    save(prs, corpus / "clean_basic.pptx")
    return {
        "file": "clean_basic.pptx",
        "category": "clean",
        "expected_rule_ids": [],
        "expected_severity_counts": {"error": 0, "warning": 0, "info": 0},
        "summary": "Two-slide healthy deck: on-slide shapes, 20pt body, alt-text image, good contrast.",
    }


def _agenda(corpus: Path) -> dict:
    prs = new_pres()

    s = blank_slide(prs)
    add_title(s, "Project Onboarding Agenda", font_name=CJK_FONT)
    add_textbox(
        s,
        "1.  Goals and scope\n"
        "2.  Stakeholders\n"
        "3.  Milestones and risks\n"
        "4.  Open discussion",
        Emu(800000), Emu(1600000), Emu(9000000), Emu(3600000),
        size=Pt(22), font_name=CJK_FONT,
    )
    add_pic(s, (120, 180, 130), Emu(8200000), Emu(1800000), Emu(2800000), Emu(2000000),
            alt="Green landscape illustration for the onboarding cover")

    # Slide 2: closing slide with a single centred line.
    s = blank_slide(prs)
    add_title(s, "Thank you", top=Emu(2600000))
    add_textbox(s, "Questions? Reach out in the team channel.",
                Emu(600000), Emu(3800000), Emu(10800000), Emu(900000),
                size=Pt(20), align=2)

    save(prs, corpus / "clean_agenda.pptx")
    return {
        "file": "clean_agenda.pptx",
        "category": "clean",
        "expected_rule_ids": [],
        "expected_severity_counts": {"error": 0, "warning": 0, "info": 0},
        "summary": "Agenda deck with CJK font name planted, centred closing slide, alt-text image.",
    }


def build(corpus_dir: Path) -> list[dict]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    return [_basic(corpus_dir), _agenda(corpus_dir)]
