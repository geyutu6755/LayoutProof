"""Chinese-typesetting fixtures.

Demonstrates planting the Microsoft YaHei / Source Han Sans font name,
mixed CJK + Latin/digit text, full-width punctuation, and kinsoku (line
break forbidden) scenarios — both a well-typeset slide and a broken one.
"""

from __future__ import annotations

from pathlib import Path

from pptx.util import Emu, Pt

from genutil import (CJK_FONT, add_textbox, add_title, blank_slide, new_pres,
                     save, set_slide_bg)
from pptx.dml.color import RGBColor


def build(corpus_dir: Path) -> list[dict]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    prs = new_pres()

    # Slide 1: well-typeset Chinese.
    s = blank_slide(prs)
    add_title(s, "中文排版示例（规范）", font_name=CJK_FONT)
    add_textbox(
        s,
        "本页使用「微软雅黑」字体。中西文混排时，"
        "在中文与 English、数字 123 之间保留适当间距，"
        "标点使用全角符号，例如：你好，世界。",
        Emu(600000), Emu(1600000), Emu(10800000), Emu(2600000),
        size=Pt(22), font_name=CJK_FONT,
    )
    add_textbox(
        s,
        "参考文献：张三．《古代汉语纲要》．北京：中华书局，2023．",
        Emu(600000), Emu(4400000), Emu(10800000), Emu(900000),
        size=Pt(18), font_name=CJK_FONT,
    )

    # Slide 2: kinsoku / spacing / mixed-width punctuation violations.
    s = blank_slide(prs)
    add_title(s, "中文排版问题（待修正）", font_name=CJK_FONT)
    # Line 2 deliberately starts with a comma (行首禁则).
    tb = add_textbox(
        s,
        "第一章 绪论",
        Emu(600000), Emu(1500000), Emu(10800000), Emu(700000),
        size=Pt(22), font_name=CJK_FONT,
    )
    p2 = tb.text_frame.add_paragraph()
    r2 = p2.add_run()
    r2.text = "，此处逗号错误地出现在行首。"
    r2.font.size = Pt(22)
    r2.font.name = CJK_FONT
    # CJK glued to Latin and digits without spacing; half-width comma after CJK.
    add_textbox(
        s,
        "使用Python编写脚本v2.0,完成数据处理。",
        Emu(600000), Emu(2800000), Emu(10800000), Emu(700000),
        size=Pt(22), font_name=CJK_FONT,
    )
    # Line ending with an opening bracket / forbidden tail.
    add_textbox(
        s,
        "引用来源见［1］［2］",
        Emu(600000), Emu(3800000), Emu(10800000), Emu(700000),
        size=Pt(22), font_name=CJK_FONT,
    )

    out = corpus_dir / "chinese_typesetting.pptx"
    save(prs, out)
    return [
        {
            "file": "chinese_typesetting.pptx",
            "category": "chinese",
            "expected_rule_ids": ["cjk_typography"],
            "expected_severity_counts": {"error": 0, "warning": 1, "info": 0},
            "summary": "Two slides: well-typeset CJK (YaHei, full-width punctuation, proper CJK-Latin spacing) "
                       "and a broken slide with line-start comma, glued CJK-Latin, and half-width comma.",
        }
    ]
