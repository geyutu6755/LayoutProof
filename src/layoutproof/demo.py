"""Self-contained offline demo: build a deliberately broken deck, scan it,
fix it, and print a before/after comparison.

Nothing leaves the machine: the broken deck is generated in-process, repaired
by :func:`layoutproof.fix.engine.fix_file`, and the fixed deck re-scanned.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from .cli import render_fix_text, render_text
from .config import QualityConfig
from .engine import scan_file
from .fix.engine import fix_file
from .models import EXIT_CLEAN, EXIT_INTERNAL

# Default deck is 10in x 7.5in (the python-pptx default).
_BROKEN_NAME = "broken.pptx"
_FIXED_NAME = "fixed.pptx"


def _build_broken(path: Path) -> None:
    """Generate a deck that deliberately trips several core-profile rules.

    * CJK / Latin mixed body text with an 8pt run  -> font_too_small
    * long text crammed into a short box, no autofit -> text_overflow
    * a box placed fully past the right slide edge    -> offslide_object
    * leftover placeholder / TODO text                -> unfinished_placeholder
    """
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # 1. Tiny font body (8pt, below the 12pt minimum).
    tiny = slide.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(4.2), Inches(0.8))
    tf = tiny.text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = "小字号正文：这一段使用了 8pt 字体，投影时几乎无法辨认。"
    run.font.size = Pt(8)

    # 2. Long CJK/Latin mixed text in a deliberately short box.
    overflow = slide.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(5.0), Inches(0.55))
    tf = overflow.text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = (
        "LayoutProof 自动排版检测演示：这是一段故意写得很长的中文混排正文，"
        "文本框高度却被压得很矮，用来稳定触发文字溢出与裁切问题，"
        "等待安全自动修复引擎把它处理掉。"
    )
    run.font.size = Pt(18)

    # 3. Object parked fully outside the right edge of the canvas.
    off = slide.shapes.add_textbox(Inches(11.5), Inches(0.5), Inches(2.6), Inches(0.8))
    run = off.text_frame.paragraphs[0].add_run()
    run.text = "完全滑出画布的越界备注（offslide object）。"
    run.font.size = Pt(18)

    # 4. Leftover placeholder / TODO text.
    ph = slide.shapes.add_textbox(Inches(0.6), Inches(4.2), Inches(4.0), Inches(0.8))
    run = ph.text_frame.paragraphs[0].add_run()
    run.text = "点击添加标题（TODO 待补充）"
    run.font.size = Pt(18)

    prs.save(str(path))


def run_demo(directory: str | Path, json_out: bool = False) -> int:
    """Generate + fix a broken deck inside ``directory``.

    Returns a process exit code (0 on success).
    """
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    broken = d / _BROKEN_NAME
    fixed = d / _FIXED_NAME

    try:
        _build_broken(broken)
    except Exception as exc:
        print(f"demo: failed to build broken deck: {exc}", file=sys.stderr)
        return EXIT_INTERNAL

    config = QualityConfig()
    before = scan_file(broken, config, profile="core")
    report = fix_file(broken, output_path=fixed, config=config,
                      profile="core", make_backup=True)

    if json_out:
        payload = {
            "broken": str(broken),
            "fixed": str(fixed),
            "scan_before": before.to_dict(),
            "fix_report": report.to_dict(),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("==[ 扫描故意埋雷的 broken.pptx ]==================================")
        print(render_text(before))
        print()
        print("==[ 安全自动修复 -> fixed.pptx ]===================================")
        print(render_fix_text(report))
        print()
        print(f"demo files: {broken}  +  {fixed}")

    return EXIT_CLEAN if report.success else EXIT_INTERNAL
