"""Unit tests for the missing_alt_text rule."""

from __future__ import annotations

import io

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.alt_text import MissingAltTextRule


def _png_bytes(color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, "PNG")
    return buf.getvalue()


def _set_descr(pic, descr: str) -> None:
    cnv = pic._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
    cnv.set("descr", descr)


def _clear_descr(pic) -> None:
    cnv = pic._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
    if "descr" in cnv.attrib:
        del cnv.attrib["descr"]


def _mark_decorative(pic) -> None:
    cnv = pic._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
    etree.SubElement(cnv, qn("p:decorative"))


def _run_rule(prs, path):
    prs.save(str(path))
    model = build_model(str(path), QualityConfig())
    return list(MissingAltTextRule(QualityConfig()).check(model))


def test_missing_alt_text_positive_and_exemptions(tmp_path):
    blob = _png_bytes()
    prs = Presentation()

    # positive: meaningful picture without alt text
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    pic = s1.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(1), Inches(2), Inches(1))
    _clear_descr(pic)

    # negative 1: picture WITH alt text
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    pic = s2.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(1), Inches(2), Inches(1))
    _set_descr(pic, "公司标志")

    # negative 2: decorative picture (explicit decorative flag), no alt
    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    pic = s3.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(1), Inches(2), Inches(1))
    _mark_decorative(pic)

    # negative 3: full-bleed background picture (auto-detected), no alt
    s4 = prs.slides.add_slide(prs.slide_layouts[6])
    s4.shapes.add_picture(
        io.BytesIO(blob), 0, 0, prs.slide_width, prs.slide_height
    )

    issues = _run_rule(prs, tmp_path / "alt.pptx")

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "missing_alt_text"
    assert issue.slide_index == 0
    assert issue.confidence == 1.0
