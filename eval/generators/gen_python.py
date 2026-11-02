"""python-pptx authored eval corpus.

Each scenario builds one independent .pptx and a structured ground-truth
record.  Positive samples are planted directly; negative samples are explicit
clean constructions; everything else stays unjudged (unknown) so the metric
script cannot inflate support.  Zip surgery (media/rel/structure probes) happens
after python-pptx saves, exactly like a real malformed export.
"""

from __future__ import annotations

import io
from pathlib import Path

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Emu, Pt

import common as C
from schema import J, record

YH = "Microsoft YaHei"
SONG = "SimSun"

OUT_SUBDIR = "python_pptx"


# ---------------------------------------------------------------------------
# small local builders
# ---------------------------------------------------------------------------
def title(slide, text, *, size=28, color=(0x22, 0x22, 0x22), font=None):
    return C.textbox(slide, text, 600000, 350000, 11000000, 900000,
                     size=size, bold=True, color=color, font_name=font)


def add_table(slide, data, x=600000, y=3200000, w=5400000, h=2200000, font=14):
    rows, cols = len(data), len(data[0])
    gframe = slide.shapes.add_table(rows, cols, Emu(x), Emu(y), Emu(w), Emu(h))
    tbl = gframe.table
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(font)
                    run.font.bold = (r == 0)
    return gframe


def add_chart(slide, x=6400000, y=2200000, w=5200000, h=3200000):
    data = CategoryChartData()
    data.categories = ["Q1", "Q2", "Q3", "Q4"]
    data.add_series("Revenue", (12, 14, 15, 18))
    data.add_series("Cost", (9, 10, 11, 12))
    gframe = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Emu(x), Emu(y), Emu(w), Emu(h), data
    )
    gframe.chart.has_legend = True
    gframe.chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    return gframe


# ---------------------------------------------------------------------------
# scenario definitions: (record-factory, builder, post-config)
# ---------------------------------------------------------------------------
def scenarios():
    S = []

    # ---- clean / negative samples -------------------------------------
    def b_p01(prs):
        s = C.blank(prs)
        C.solid_bg(s, (255, 255, 255))
        title(s, "Quarterly Business Review")
        C.textbox(s, "Revenue rose steadily through the year, led by the Q4 product launch. "
                     "The sales team expanded coverage in three new regions.",
                  600000, 1500000, 10800000, 1100000, size=18)
        add_table(s, [["Quarter", "Revenue", "Growth"],
                      ["Q1", "$1.2M", "+8%"], ["Q2", "$1.4M", "+12%"], ["Q3", "$1.5M", "+7%"]])
        C.add_pic(s, (120, 160, 210), 6400000, 3200000, 4800000, 2200000, alt="Regional map")

    S.append((record("p01", f"{OUT_SUBDIR}/p01_clean_en_table_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_en_table_media",
                      "Clean English deck: explicit solid white bg, readable 14-18pt text, "
                      "native table, valid PNG with alt text, no overlap.",
                      [J("offslide_object", "negative", "all shapes inside canvas margins"),
                       J("font_too_small", "negative", "explicit sizes 14-18pt, >=12pt threshold"),
                       J("text_overflow", "negative", "boxes tall enough for one wrapped paragraph"),
                       J("unfinished_placeholder", "negative", "real prose, no TODO/click prompt"),
                       J("media_broken", "negative", "valid embedded PNG"),
                       J("broken_reference", "negative", "no internal or dangling relationship"),
                       J("object_overlap", "negative", "table/media/title do not overlap content shapes"),
                       J("low_contrast", "negative", "dark text on explicit white background"),
                       J("blank_slide", "negative", "text, table and picture present"),
                       J("missing_alt_text", "negative", "content picture carries alt text"),
                       J("structure_anomaly", "negative", "valid zip: required parts present, no unsafe/duplicate entries")]),
              b_p01, None))

    def b_p02(prs):
        s = C.blank(prs)
        C.solid_bg(s, (255, 255, 255))
        title(s, "中文排版规范示例", font=YH)
        C.textbox(s, "本页使用「微软雅黑」。中西文混排时，中文与 English、数字 123 "
                     "之间保留单个正常空格，标点使用全角符号，例如：你好，世界。",
                  600000, 1600000, 10800000, 2200000, size=20, font_name=YH)

    S.append((record("p02", f"{OUT_SUBDIR}/p02_clean_zh_typeset_16x9.pptx",
                      "python_pptx", "zh", "16:9", "clean_zh_kinsoku",
                      "Clean well-typeset Simplified Chinese page: full-width punctuation, "
                      "single normal CJK-Latin space, no forbidden line-start punctuation.",
                      [J("cjk_typography", "negative",
                         "full-width punctuation, one normal CJK-Latin space, balanced kinsoku"),
                       J("unfinished_placeholder", "negative", "real Chinese prose"),
                       J("blank_slide", "negative", "content present"),
                       J("low_contrast", "negative", "dark text on explicit white")]),
              b_p02, None))

    def b_p03(prs):
        s = C.blank(prs)
        title(s, "Bilingual Mix / 双语混排")
        C.textbox(s, "项目 Project 名称 Name 为 LayoutProof，版本 v1.0，负责人 3 名。",
                  600000, 1600000, 10800000, 900000, size=18, font_name=YH)
        C.textbox(s, "规范使用全角中文标点与半角英文词汇，间距保持一致。",
                  600000, 2800000, 10800000, 900000, size=18, font_name=YH)

    S.append((record("p03", f"{OUT_SUBDIR}/p03_clean_mixed_16x9.pptx",
                      "python_pptx", "mixed", "16:9", "clean_bilingual",
                      "Mixed Chinese/English deck with normal spacing and full-width punctuation.",
                      [J("cjk_typography", "negative", "single spaces, full-width punctuation, no forbidden starts"),
                       J("unfinished_placeholder", "negative", "real content"),
                       J("object_overlap", "negative", "two separated text boxes")]),
              b_p03, None))

    def b_p04(prs):
        prs.slide_width, prs.slide_height = C.DIMS["4:3"]
        s = C.blank(prs)
        C.textbox(s, "4:3 Clean Slide", 450000, 350000, 8200000, 900000, size=28, bold=True)
        C.textbox(s, "Every shape keeps a safe margin inside the 10 x 7.5 inch canvas.",
                  450000, 1600000, 8200000, 1200000, size=18)
        C.add_pic(s, (150, 190, 150), 450000, 3400000, 3800000, 2200000, alt="Bar chart sketch")

    S.append((record("p04", f"{OUT_SUBDIR}/p04_clean_en_4x3.pptx",
                      "python_pptx", "en", "4:3", "clean_4_3",
                      "4:3 slide authored entirely within the narrower canvas (no 16:9 geometry).",
                      [J("offslide_object", "negative", "all boxes inside 4:3 bounds"),
                       J("text_overflow", "negative", "ample text box heights"),
                       J("blank_slide", "negative", "content present"),
                       J("missing_alt_text", "negative", "picture has alt text")]),
              b_p04, None))

    def b_p05(prs):
        s = C.blank(prs)
        title(s, "Deliberate Decorative Stack")
        # three non-overlapping plain cards; one label absorbed into its card
        a = C.rect(s, 1200000, 1800000, 3000000, 1800000, fill=(0xE8, 0xEF, 0xF8))
        C.textbox(s, "Card One label", 1300000, 1900000, 2800000, 600000, size=16)
        C.rect(s, 4700000, 1800000, 3000000, 1800000, fill=(0xF8, 0xEE, 0xE8))
        C.rect(s, 8200000, 1800000, 3000000, 1800000, fill=(0xEE, 0xF6, 0xEA))
        # decorative background band behind, named hint + decorative flag
        band = C.rect(s, 0, 6200000, 12192000, 658000, fill=(0xEE, 0xEE, 0xEE),
                      line=None, name="background divider")
        C.mark_decorative(band)
        # grouped decorative bubbles (children skipped by overlap rule)
        bubbles = []
        for i in range(4):
            b = C.rect(s, 1400000 + i * 1400000, 4200000, 900000, 900000,
                       fill=(120 + i * 25, 150, 210), line=None, name="decorative bubble")
            bubbles.append(b)
        s.shapes.add_group_shape(bubbles)

    S.append((record("p05", f"{OUT_SUBDIR}/p05_clean_decorative_group_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_decorative_group",
                      "Rich but valid layout: separated cards, absorbed card label, named "
                      "decorative band and a grouped decorative set; must not collide.",
                      [J("object_overlap", "negative",
                         "cards are separated; label absorbed into card; grouped children skipped; band flagged decorative"),
                       J("offslide_object", "negative", "decorative band reaches edge but stays inside"),
                       J("blank_slide", "negative", "content present")]),
              b_p05, None))

    def b_p06(prs):
        s = C.blank(prs)
        title(s, "Photo with Caption Overlay")
        C.add_pic(s, (90, 130, 180), 7600000, 1700000, 3400000, 2400000, alt="Conference photo")
        C.textbox(s, "1. Goals\n2. Scope\n3. Timeline", 800000, 1700000, 8600000, 3600000, size=18)

    S.append((record("p06", f"{OUT_SUBDIR}/p06_clean_picture_caption_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_picture_overlay",
                      "Intentional photo+caption overlay covering less than 90% of the picture; "
                      "caption must not be reported as a collision; picture carries alt text.",
                      [J("object_overlap", "negative", "text covers <90% of picture (deliberate overlay)"),
                       J("missing_alt_text", "negative", "picture alt text present"),
                       J("media_broken", "negative", "valid PNG"),
                       J("blank_slide", "negative", "content present")]),
              b_p06, None))

    def b_p07(prs):
        s = C.blank(prs)
        title(s, "Auto-Shrink Enabled")
        tb = C.textbox(s, "This paragraph repeats a long sentence many times so that, "
                          "without auto-fit, it could look crowded, but PowerPoint shrinks it "
                          "itself because normAutofit / text-to-fit-shape is enabled.",
                       600000, 1600000, 10800000, 1600000, size=18)
        tb.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    S.append((record("p07", f"{OUT_SUBDIR}/p07_clean_normautofit_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_normautofit",
                      "Dense text with normAutofit enabled; renderer-owned shrinking must be skipped.",
                      [J("text_overflow", "negative", "normAutofit enabled -> rule intentionally skips"),
                       J("offslide_object", "negative", "inside canvas")]),
              b_p07, None))

    def b_p08(prs):
        s = C.blank(prs)
        title(s, "Inherited Font Sizes")
        # no explicit run size: falls back to theme/master; must not be judged.
        C.textbox(s, "Long prose that would be hard to size offline, but every run inherits "
                      "its size from the theme, so both size and overflow rules skip it.",
                   600000, 1600000, 10800000, 1800000, size=None)

    S.append((record("p08", f"{OUT_SUBDIR}/p08_clean_inherited_font_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_inherited_size",
                      "Text frames carry no explicit font size (inherited from theme); rules "
                      "must stay silent rather than guessing a small size.",
                      [J("font_too_small", "negative", "no explicit run size -> rule skips inherited sizes"),
                       J("text_overflow", "negative", "no explicit size -> rule skips"),
                       J("blank_slide", "negative", "content present")]),
              b_p08, None))

    def b_p09(prs):
        s = C.blank(prs)
        title(s, "Tight but Safe Margins")
        C.rect(s, 11700000, 6000000, 350000, 650000, fill=(0xDD, 0xDD, 0xDD), line=None)

    S.append((record("p09", f"{OUT_SUBDIR}/p09_clean_safe_margin_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_safe_margin",
                      "A small accent bar that ends before the right/bottom canvas edges.",
                      [J("offslide_object", "negative", "bar rectangle fully inside canvas")]),
              b_p09, None))

    def b_p10(prs):
        s = C.blank(prs)
        title(s, "External Reference")
        tb = C.textbox(s, "Open project documentation", 600000, 1700000, 10000000, 800000, size=20)
        tb.text_frame.paragraphs[0].runs[0].hyperlink.address = "https://example.com/docs"

    S.append((record("p10", f"{OUT_SUBDIR}/p10_clean_external_link_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_external_hyperlink",
                      "External https hyperlink; offline rules must not treat it as broken internal ref.",
                      [J("broken_reference", "negative", "external http URL is out of offline scope")]),
              b_p10, None))

    def b_p11(prs):
        s = C.blank(prs)
        title(s, "Valid Internal Target")
        C.blank(prs)  # slide 2 exists as the valid internal target
        return None

    valid_rel = (f'<Relationship Id="rId200" Type="{C.REL_SLIDE}" Target="slide2.xml"/>')
    S.append((record("p11", f"{OUT_SUBDIR}/p11_clean_valid_internal_rel_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_internal_rel",
                      "Internal relationship targeting an existing slide part; not broken.",
                      [J("broken_reference", "negative", "internal rel resolves to existing slide2.xml")]),
              b_p11, {"extra_rels": {"ppt/slides/_rels/slide1.xml.rels": valid_rel}}))

    def b_p12(prs):
        s = C.blank(prs)
        title(s, "Healthy Media Gallery")
        C.add_pic(s, (180, 100, 100), 800000, 1700000, 3000000, 2100000, alt="Product photo A")
        C.add_pic(s, (100, 180, 120), 4300000, 1700000, 3000000, 2100000, alt="Product photo B")
        C.add_pic(s, (120, 120, 200), 7800000, 1700000, 3000000, 2100000, alt="Product photo C")

    S.append((record("p12", f"{OUT_SUBDIR}/p12_clean_media_alts_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_images_alts",
                      "Three valid PNGs, each with alternative text.",
                      [J("media_broken", "negative", "all PNGs decode and parts exist"),
                       J("missing_alt_text", "negative", "every picture has descr alt text"),
                       J("structure_anomaly", "negative", "well-formed OOXML package")]),
              b_p12, None))

    def b_p13(prs):
        s = C.blank(prs)
        title(s, "Tables and Charts")
        add_table(s, [["Metric", "2025", "2026"], ["Users", "42k", "61k"], ["Retention", "71%", "78%"]],
                  x=600000, y=1600000, w=5000000, h=1800000)
        add_chart(s)

    S.append((record("p13", f"{OUT_SUBDIR}/p13_clean_table_chart_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_table_chart",
                      "Native table plus clustered column chart on separated regions; no defects.",
                      [J("blank_slide", "negative", "table and chart are content"),
                       J("object_overlap", "negative", "table and chart occupy non-overlapping regions"),
                       J("offslide_object", "negative", "inside canvas"),
                       J("structure_anomaly", "negative", "well-formed OOXML package")]),
              b_p13, None))

    def b_p14(prs):
        s = C.blank(prs)
        C.add_pic(s, (40, 60, 100), 0, 0, 12192000, 6858000, size=(1219, 686))  # full-bleed bg
        C.textbox(s, "Content over a Background", 600000, 600000, 10000000, 900000, size=28,
                  color=(255, 255, 255), bold=True)
        C.add_pic(s, (200, 180, 120), 600000, 1800000, 4200000, 2800000, alt="Insight chart")

    S.append((record("p14", f"{OUT_SUBDIR}/p14_clean_bg_and_content_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_fullbleed_bg",
                      "Full-bleed background picture auto-exempted as background; real content "
                      "picture has alt text; slide is not blank.",
                      [J("blank_slide", "negative", "content text and picture present"),
                       J("missing_alt_text", "negative", "background exempt; content picture has alt"),
                       J("media_broken", "negative", "valid images"),
                       J("low_contrast", "unknown",
                         "body text sits over a full-bleed picture; background color cannot be "
                         "resolved offline, so the contrast rule fails open",
                         note="renderer/picture-background dependent; excluded from matrix")]),
              b_p14, None))

    # ---- positive samples ----------------------------------------------
    def b_p15(prs):
        s = C.blank(prs)
        title(s, "Off-slide Shape (fully outside)")
        C.rect(s, 13200000, 2200000, 2600000, 1400000, fill=(0xFF, 0xCC, 0xCC), line=None)

    S.append((record("p15", f"{OUT_SUBDIR}/p15_offslide_fully_right_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_offslide_fully",
                      "Rectangle fully beyond the right edge of the 16:9 canvas.",
                      [J("offslide_object", "positive", "shape fully outside x>slide width", expected_count=1),
                       J("blank_slide", "negative", "title text present")]),
              b_p15, None))

    def b_p16(prs):
        prs.slide_width, prs.slide_height = C.DIMS["4:3"]
        s = C.blank(prs)
        C.textbox(s, "4:3 Partial Bleed", 450000, 350000, 8200000, 900000, size=28, bold=True)
        C.rect(s, 8400000, 6200000, 2400000, 1500000, fill=(0xFF, 0xDD, 0xCC), line=None)

    S.append((record("p16", f"{OUT_SUBDIR}/p16_offslide_partial_bottom_4x3.pptx",
                      "python_pptx", "en", "4:3", "pos_offslide_partial",
                      "Rectangle crosses the bottom/right edge of the 4:3 canvas (>5% outside).",
                      [J("offslide_object", "positive", "shape partially outside 4:3 bounds", expected_count=1)]),
              b_p16, None))

    def b_p17(prs):
        s = C.blank(prs)
        title(s, "Overflow: No Wrap, Tiny Box")
        C.textbox(s, "A very long single line that cannot wrap and the box height is tiny.",
                  600000, 1800000, 9000000, 130000, size=24, wrap=False)

    S.append((record("p17", f"{OUT_SUBDIR}/p17_overflow_nowrap_tinybox_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_overflow_nowrap",
                      "Wrap disabled; 24pt text in a ~0.14in tall box; height clearly insufficient.",
                      [J("text_overflow", "positive", "single unwrapped line needs more pt than box height", expected_count=1)]),
              b_p17, None))

    def b_p18(prs):
        s = C.blank(prs)
        title(s, "Overflow: Dense Wrapped Text")
        long = ("This sentence repeats enough words to require many wrapped lines in a narrow, "
                "short box where the estimated leading height far exceeds the available height. "
                "Adaptive shrink is off and the explicit font size remains twenty points. ") * 3
        C.textbox(s, long, 600000, 1700000, 1400000, 550000, size=20, wrap=True)

    S.append((record("p18", f"{OUT_SUBDIR}/p18_overflow_dense_wrapped_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_overflow_wrapped",
                      "Narrow short box with repeated wrapped text at 20pt; estimated lines far "
                      "exceed box capacity; autofit disabled.",
                      [J("text_overflow", "positive", "heuristic estimated lines >> box capacity", expected_count=1)]),
              b_p18, None))

    def b_p19(prs):
        s = C.blank(prs)
        title(s, "Tiny 9pt Footnote", font=YH)
        C.textbox(s, "注：本页数据为示例，仅供内部讨论使用。",
                  600000, 3000000, 10800000, 700000, size=9, font_name=YH)

    S.append((record("p19", f"{OUT_SUBDIR}/p19_font_tiny_9pt_zh_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_font_small",
                      "Explicit 9pt Chinese footnote below the 12pt minimum; box itself is "
                      "generous so this isolates the font-size defect.",
                      [J("font_too_small", "positive", "explicit 9pt < 12pt threshold", expected_count=1),
                       J("text_overflow", "negative", "box height ample for one 9pt line")]),
              b_p19, None))

    def b_p20(prs):
        s = C.blank(prs)
        C.solid_bg(s, (255, 255, 255))
        C.textbox(s, "浅灰小字对比度不足", 600000, 1800000, 10800000, 900000,
                  size=12, color=(0x99, 0x99, 0x99), font_name=YH)

    S.append((record("p20", f"{OUT_SUBDIR}/p20_contrast_gray_small_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_contrast_small",
                      "12pt #999 on explicit white; ratio ~2.85 below normal 4.5 threshold.",
                      [J("low_contrast", "positive", "gray small text below 4.5:1", expected_count=1,
                         profiles="full")]),
              b_p20, None))

    def b_p21(prs):
        s = C.blank(prs)
        C.solid_bg(s, (255, 255, 255))
        C.textbox(s, "灰色大字仍偏淡", 600000, 1800000, 10800000, 1200000,
                  size=24, color=(0x99, 0x99, 0x99), font_name=YH)

    S.append((record("p21", f"{OUT_SUBDIR}/p21_contrast_gray_large_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_contrast_large",
                      "24pt #999 on white; ratio ~2.85 below the large-text 3.0 threshold.",
                      [J("low_contrast", "positive", "large gray text below 3.0:1", expected_count=1,
                         profiles="full")]),
              b_p21, None))

    def b_p22(prs):
        s = C.blank(prs)
        tb = C.textbox(s, "同色填充与同色文字", 600000, 1800000, 6000000, 1800000,
                       size=14, color=(0x88, 0x88, 0x88), font_name=YH)
        tb.fill.solid()
        tb.fill.fore_color.rgb = C.rgb((0x88, 0x88, 0x88))

    S.append((record("p22", f"{OUT_SUBDIR}/p22_contrast_shape_fill_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_contrast_shapefill",
                      "Text color identical to its own solid shape fill; basis=shape_fill.",
                      [J("low_contrast", "positive", "foreground ~= background fill, ratio near 1:1",
                         expected_count=1, profiles="full")]),
              b_p22, None))

    def b_p23(prs):
        C.blank(prs)

    S.append((record("p23", f"{OUT_SUBDIR}/p23_blank_only_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_blank",
                      "Deliberately empty blank-layout slide with no shapes at all.",
                      [J("blank_slide", "positive", "no content shape, placeholder text or media",
                         expected_count=1, profiles="full")]),
              b_p23, None))

    def b_p24(prs):
        s = C.blank(prs)
        C.textbox(s, "Click to add title", 600000, 400000, 10000000, 900000, size=28)
        C.textbox(s, "TODO: fill in the Q3 numbers before review", 600000, 1800000, 10000000, 700000, size=18)
        C.textbox(s, "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                  600000, 2800000, 10000000, 700000, size=18)

    S.append((record("p24", f"{OUT_SUBDIR}/p24_placeholder_en_patterns_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_placeholder_en",
                      "Three English placeholder leftovers: click prompt, TODO, Lorem ipsum.",
                      [J("unfinished_placeholder", "positive", "three separate prompt runs match patterns",
                         expected_count=3)]),
              b_p24, None))

    def b_p25(prs):
        s = C.blank(prs)
        C.textbox(s, "待补充：季度财报数据", 600000, 500000, 10000000, 800000, size=22, font_name=YH)
        C.textbox(s, "此处输入封面副标题", 600000, 1700000, 10000000, 800000, size=22, font_name=YH)
        C.textbox(s, "本页占位内容，尚未替换。", 600000, 2900000, 10000000, 800000, size=22, font_name=YH)

    S.append((record("p25", f"{OUT_SUBDIR}/p25_placeholder_zh_patterns_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_placeholder_zh",
                      "Chinese placeholder leftovers: 待补充 / 此处输入 / 占位.",
                      [J("unfinished_placeholder", "positive", "three Chinese prompt texts match",
                         expected_count=3)]),
              b_p25, None))

    def b_p26(prs):
        s = C.blank(prs)
        title(s, "Two Colliding Cards")
        C.rect(s, 1800000, 1800000, 4200000, 2200000, fill=(0xCC, 0xDD, 0xFF), line=None)
        C.rect(s, 3600000, 2600000, 4200000, 2200000, fill=(0xFF, 0xDD, 0xCC), line=None)

    S.append((record("p26", f"{OUT_SUBDIR}/p26_overlap_two_cards_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_overlap_cards",
                      "Two plain filled rectangles overlap well beyond 30% of the smaller shape.",
                      [J("object_overlap", "positive", "plain content cards overlap >=30%",
                         expected_count=1, profiles="full")]),
              b_p26, None))

    def b_p27(prs):
        s = C.blank(prs)
        title(s, "中文禁则问题", font=YH)
        tb = C.textbox(s, "第一章 绪论", 600000, 1600000, 10800000, 700000, size=22, font_name=YH)
        C.add_paragraph(tb, "，逗号错误地出现在段落行首。", size=22, font_name=YH)

    S.append((record("p27", f"{OUT_SUBDIR}/p27_cjk_kinsoku_start_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_cjk_kinsoku",
                      "A paragraph opens with a forbidden closing comma (行首禁则).",
                      [J("cjk_typography", "positive", "kinsoku_line_start: comma at paragraph start",
                         expected_count=1, profiles="full")]),
              b_p27, None))

    def b_p28(prs):
        s = C.blank(prs)
        title(s, "中英标点与空格问题", font=YH)
        C.textbox(s, "你好,世界。中文  abc之间存在两个连续空格。",
                  600000, 1600000, 10800000, 1200000, size=22, font_name=YH)

    S.append((record("p28", f"{OUT_SUBDIR}/p28_cjk_halfwidth_space_16x9.pptx",
                      "python_pptx", "zh", "16:9", "pos_cjk_halfwidth_space",
                      "Half-width ASCII comma after CJK plus two consecutive CJK-Latin spaces.",
                      [J("cjk_typography", "positive",
                         "halfwidth_punct + cjk_latin_space (>=2 spaces)", expected_count=1, profiles="full")]),
              b_p28, None))

    def b_p29(prs):
        s = C.blank(prs)
        title(s, "Picture Without Alt Text")
        C.add_pic(s, (150, 150, 200), 2000000, 1700000, 4200000, 2800000, alt=None)

    S.append((record("p29", f"{OUT_SUBDIR}/p29_missing_alt_picture_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_missing_alt",
                      "Meaningful picture with descr/title stripped; no decorative flag.",
                      [J("missing_alt_text", "positive", "visible non-bg picture with no alt text",
                         expected_count=1, profiles="full"),
                       J("media_broken", "negative", "PNG bytes are valid")]),
              b_p29, None))

    def b_p30(prs):
        s = C.blank(prs)
        title(s, "Missing Media Part")
        C.add_pic(s, (200, 100, 100), 2000000, 1700000, 4200000, 2800000, alt="x")
    S.append((record("p30", f"{OUT_SUBDIR}/p30_media_missing_part_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_media_missing",
                      "Picture relationship present but its media part deleted in zip surgery.",
                      [J("media_broken", "positive", "rel targets missing_image_part", expected_count=1)]),
              b_p30, {"drop_first_media": True}))

    def b_p31(prs):
        s = C.blank(prs)
        title(s, "Corrupted Media Bytes")
        C.add_pic(s, (100, 200, 100), 2000000, 1700000, 4200000, 2800000, alt="x")
    S.append((record("p31", f"{OUT_SUBDIR}/p31_media_corrupt_bytes_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_media_corrupt",
                      "Media part exists but bytes fail the PNG/JPEG/GIF magic and decode check.",
                      [J("media_broken", "positive", "bad_signature on existing media part",
                         expected_count=1)]),
              b_p31, {"corrupt_first_media": True}))

    def b_p32(prs):
        s = C.blank(prs)
        title(s, "Broken Internal Reference")
        C.textbox(s, "Jump to appendix", 600000, 1700000, 9000000, 800000, size=20)
    extra = (f'<Relationship Id="rId910" Type="{C.REL_HYPERLINK}" '
             f'Target="../slides/no_such_appendix.xml"/>')
    S.append((record("p32", f"{OUT_SUBDIR}/p32_ref_missing_target_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_ref_missing_target",
                      "Internal hyperlink relationship points at a slide part that does not exist.",
                      [J("broken_reference", "positive", "missing_target internal rel", expected_count=1)]),
              b_p32, {"extra_rels": {"ppt/slides/_rels/slide1.xml.rels": extra}}))

    def b_p33(prs):
        s = C.blank(prs)
        title(s, "Dangling Relationship rId")
    inject = '<a:hlinkClick r:id="rId99"/>'
    S.append((record("p33", f"{OUT_SUBDIR}/p33_ref_dangling_rid_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_ref_dangling",
                      "Slide XML references rId99 that has no entry in its .rels (dangling).",
                      [J("broken_reference", "positive", "dangling_rId reference without rel entry",
                         expected_count=1)]),
              b_p33, {"xml_inject": {"ppt/slides/slide1.xml": inject}}))

    def b_p34(prs):
        s = C.blank(prs)
        title(s, "Unsafe Package Entry Probe")
        C.textbox(s, "Normal valid body text inside the deck.", 600000, 1700000, 9000000, 900000, size=18)
    S.append((record("p34", f"{OUT_SUBDIR}/p34_structure_unsafe_entry_16x9.pptx",
                      "python_pptx", "en", "16:9", "pos_structure_unsafe_entry",
                      "A harmless unused zip entry with an unsafe relative path triggers the "
                      "package anomaly check; the real parts remain openable.",
                      [J("structure_anomaly", "positive", "SafePackage flags unsafe entry name",
                         expected_count=1)]),
              b_p34, {"unsafe_entry": "ppt/../../eval-probe.txt"}))

    def b_p35(prs):
        s = C.blank(prs)
        title(s, "Decorative Element Near Edge (behavior probe)")
        deco = C.rect(s, 12400000, 5000000, 2600000, 1400000, fill=(0xEE, 0xEE, 0xEE),
                      line=None, name="background ornament")
        C.mark_decorative(deco)
    S.append((record("p35", f"{OUT_SUBDIR}/p35_probe_decorative_offslide_16x9.pptx",
                      "python_pptx", "en", "16:9", "probe_decorative_offslide",
                      "Probe: a fully outside shape that is both named decorative and carries the "
                      "decorative flag. Product intent says decorative extras should be exempt; "
                      "treated as a negative expectation and any fire recorded as a suspected FP.",
                      [J("offslide_object", "negative",
                         "intent: flagged decorative element should be exempt; suspect FP if fired",
                         note="decorative flag currently only used by overlap/alt/blank, not offslide")]),
              b_p35, None))

    def b_p36(prs):
        s = C.blank(prs)
        title(s, "Legitimate Words Containing Prompt Substrings")
        C.textbox(s, "The team archived the todo list before the quarterly review.",
                  600000, 1700000, 10800000, 800000, size=18)
        C.textbox(s, "The placeholder API contract was approved by the committee.",
                  600000, 2800000, 10800000, 800000, size=18)
    S.append((record("p36", f"{OUT_SUBDIR}/p36_probe_placeholder_substring_16x9.pptx",
                      "python_pptx", "en", "16:9", "probe_placeholder_substring",
                      "Probe: real English sentences containing the substring 'todo' and "
                      "'placeholder'. Substring matching risks FP; any fire recorded as suspected FP.",
                      [J("unfinished_placeholder", "negative",
                         "normal prose; prompt patterns should match only standalone markers",
                         note="substring match on 'todo'/'placeholder' likely false positives")]),
              b_p36, None))

    def b_p37(prs):
        s = C.blank(prs)
        title(s, "Truncated Corrupt Package")
    S.append((record("p37", f"{OUT_SUBDIR}/p37_error_truncated_zip.pptx",
                      "python_pptx", "en", "16:9", "error_truncated_zip",
                      "Truncated zip central directory; scan_file expected status=error and no "
                      "issues emitted; excluded from the confusion matrix.",
                      [], expected_status="error",
                      build_note="Bytes truncated after save; likely BadZipFile -> status error."),
              b_p37, {"truncate": True}))

    def b_p38(prs):
        s = prs.slides.add_slide(prs.slide_layouts[1])  # title + content layout
        C.solid_bg(s, (255, 255, 255))
        title = s.shapes.title
        title.text = "Layout Slide Demo"
        for para in title.text_frame.paragraphs:
            for run in para.runs:
                run.font.size = Pt(28)
                run.font.bold = True
        body = next(p for p in s.placeholders if p.placeholder_format.idx == 1)
        body.text = ("This slide uses the title-and-content slide layout and populates its "
                    "native content region rather than a blank custom text frame.")
        for para in body.text_frame.paragraphs:
            for run in para.runs:
                run.font.size = Pt(18)

    S.append((record("p38", f"{OUT_SUBDIR}/p38_clean_layout_placeholder_16x9.pptx",
                      "python_pptx", "en", "16:9", "clean_layout_placeholder",
                      "Native title/content layout with populated placeholders; explicit "
                      "sizes and safe inherited layout geometry.",
                      [J("offslide_object", "negative", "layout placeholders remain inside canvas"),
                       J("font_too_small", "negative", "explicit 18/28pt run sizes"),
                       J("text_overflow", "negative", "body box has ample inherited height"),
                       J("unfinished_placeholder", "negative", "real prose replaces layout prompt"),
                       J("media_broken", "negative", "no external or broken media part"),
                       J("broken_reference", "negative", "valid slide/layout relationships"),
                       J("object_overlap", "negative", "title and body placeholders do not collide"),
                       J("low_contrast", "negative", "dark text on explicit white background"),
                       J("blank_slide", "negative", "title and body content present"),
                       J("structure_anomaly", "negative", "well-formed OOXML package")]),
              b_p38, None))

    return S


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------
def build_all(corpus_dir: Path) -> list[dict]:
    records = []
    target_root = corpus_dir / OUT_SUBDIR
    target_root.mkdir(parents=True, exist_ok=True)

    for rec, build_fn, post in scenarios():
        prs = C.new_prs("16:9")
        ctx = build_fn(prs) or {}
        raw = target_root / ("_raw_" + Path(rec["file"]).name)
        C.save(prs, raw)
        final = corpus_dir / rec["file"]

        if post:
            if post.get("drop_first_media"):
                media = C.list_media(raw)
                C.rewrite_zip(raw, final, drop={media[0]})
            elif post.get("corrupt_first_media"):
                media = C.list_media(raw)
                C.rewrite_zip(raw, final, mutate={media[0]: b"\x00\x01NOT_A_REAL_PNG\x00" * 4})
            elif post.get("unsafe_entry"):
                C.rewrite_zip(raw, final, extra_entries={post["unsafe_entry"]: b"eval-only probe"})
            elif post.get("truncate"):
                data = raw.read_bytes()
                final.write_bytes(data[:-260])
            else:
                C.rewrite_zip(raw, final,
                               extra_rels=post.get("extra_rels"),
                               xml_inject=post.get("xml_inject"))
        else:
            C.rewrite_zip(raw, final)

        raw.unlink(missing_ok=True)
        records.append(rec)
    return records


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    out = build_all(root / "corpus")
    print(f"python generator: {len(out)} records")
