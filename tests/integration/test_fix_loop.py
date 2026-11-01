"""Integration test: the full detect -> locate -> fix -> re-verify loop."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from layoutproof.config import QualityConfig
from layoutproof.engine import scan_file
from layoutproof.fix.engine import fix_file


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _make_broken(path: Path) -> None:
    """Programmatically build a deck that trips the core fixable rules."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # 1. Tiny font (8pt < 12pt minimum).
    tiny = slide.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(4.0), Inches(0.8))
    tiny.text_frame.word_wrap = True
    r = tiny.text_frame.paragraphs[0].add_run()
    r.text = "小字号正文：这段文字故意用了 8pt，难以阅读。"
    r.font.size = Pt(8)

    # 2. Long CJK text in a short box, no autofit.
    ov = slide.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(4.5), Inches(0.5))
    ov.text_frame.word_wrap = True
    r = ov.text_frame.paragraphs[0].add_run()
    r.text = ("LayoutProof 检测演示：这是一段故意写得很长的中文混排正文，"
              "文本框被刻意压得很矮，用来触发文字溢出与裁切问题。")
    r.font.size = Pt(18)

    # 3. Object fully outside the right edge.
    off = slide.shapes.add_textbox(Inches(11.5), Inches(0.5), Inches(2.5), Inches(0.8))
    r = off.text_frame.paragraphs[0].add_run()
    r.text = "越界备注，完全滑出画布。"
    r.font.size = Pt(18)

    # 4. Leftover placeholder text.
    ph = slide.shapes.add_textbox(Inches(0.6), Inches(4.2), Inches(4.0), Inches(0.8))
    r = ph.text_frame.paragraphs[0].add_run()
    r.text = "点击添加标题（TODO 待补充）"
    r.font.size = Pt(18)

    prs.save(str(path))


def test_fix_loop_reduces_issues_and_keeps_source(tmp_path):
    src = tmp_path / "deck.pptx"
    _make_broken(src)
    out = tmp_path / "deck.fixed.pptx"

    config = QualityConfig()
    before = scan_file(src, config, profile="core")
    src_hash_before = _sha256(src)

    report = fix_file(src, output_path=out, config=config,
                      profile="core", make_backup=True)

    # Output file was created.
    assert out.exists(), "fixed deck was not produced"
    # Source bytes are byte-for-byte unchanged.
    assert _sha256(src) == src_hash_before, "source file was modified!"
    # Backup copy exists.
    assert (tmp_path / "deck.bak.pptx").exists(), "backup .pptx missing"
    # The loop actually removed issues.
    assert report.before_summary["total"] > 0
    assert report.after_summary["total"] < report.before_summary["total"]
    assert report.applied, "expected at least one applied fix"
    # Output re-scans cleanly (no new structural errors).
    after = scan_file(out, config, profile="core")
    assert after.status == "ok"
    assert after.summarize().total < before.summarize().total
    # Output opens with python-pptx (implicit in scan_file; assert again here).
    from pptx import Presentation
    reopened = Presentation(str(out))
    assert len(reopened.slides) == before.slide_count
    assert report.success is True


def test_scan_json_is_idempotent(tmp_path):
    src = tmp_path / "idemp.pptx"
    _make_broken(src)
    config = QualityConfig()
    first = scan_file(src, config, profile="core").to_dict()
    second = scan_file(src, config, profile="core").to_dict()
    # Only the wall-clock timestamp should differ.
    first.pop("timestamp")
    second.pop("timestamp")
    assert first == second


def test_fix_result_is_reproducible(tmp_path):
    src = tmp_path / "repro.pptx"
    _make_broken(src)
    config = QualityConfig()
    r1 = fix_file(src, output_path=tmp_path / "a.fixed.pptx",
                  config=config, make_backup=False).to_dict()
    r2 = fix_file(src, output_path=tmp_path / "b.fixed.pptx",
                  config=config, make_backup=False).to_dict()
    assert r1["after"] == r2["after"]
    assert sorted(a["rule_id"] for a in r1["applied"]) == \
           sorted(a["rule_id"] for a in r2["applied"])
