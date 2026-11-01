"""Unit tests for the broken_reference rule (zip surgery injects broken rels)."""

from __future__ import annotations

import zipfile

from pptx import Presentation

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.references import BrokenReferenceRule


def _rebuild(src, dst, extra_rels: dict[str, str] | None = None,
             slide_xml_inject: str | None = None):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(
        dst, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if extra_rels and item.filename in extra_rels:
                text = data.decode("utf-8")
                assert "</Relationships>" in text
                data = text.replace(
                    "</Relationships>", extra_rels[item.filename] + "</Relationships>"
                ).encode("utf-8")
            if slide_xml_inject and item.filename == "ppt/slides/slide1.xml":
                text = data.decode("utf-8")
                assert "</p:spTree>" in text
                data = text.replace(
                    "</p:spTree>", slide_xml_inject + "</p:spTree>"
                ).encode("utf-8")
            zout.writestr(item, data)


def test_broken_reference_positive_negative(tmp_path):
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])  # slide 1
    prs.slides.add_slide(prs.slide_layouts[6])  # slide 2

    raw = tmp_path / "ref_raw.pptx"
    prs.save(str(raw))

    hyperlink = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    )
    slide_rel = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
    )
    rel_patch = (
        # positive A: internal hyperlink -> slide part that does not exist
        f'<Relationship Id="rId910" Type="{hyperlink}" Target="../slides/no_such_slide.xml"/>'
        # negative 1: external URL -> out of scope
        f'<Relationship Id="rId911" Type="{hyperlink}" Target="https://example.com" TargetMode="External"/>'
        # negative 2: internal rel to an existing slide part
        f'<Relationship Id="rId912" Type="{slide_rel}" Target="slide2.xml"/>'
    )
    # positive B: slide XML references rId99 with no entry in .rels at all
    xml_inject = '<a:hlinkClick r:id="rId99"/>'

    broken = tmp_path / "ref_broken.pptx"
    _rebuild(
        raw,
        broken,
        extra_rels={"ppt/slides/_rels/slide1.xml.rels": rel_patch},
        slide_xml_inject=xml_inject,
    )

    model = build_model(str(broken), QualityConfig())
    issues = list(BrokenReferenceRule(QualityConfig()).check(model))

    # two positives: missing target (rId910) + dangling reference (rId99)
    assert len(issues) == 2
    by_rid = {i.evidence["rId"]: i for i in issues}
    assert set(by_rid) == {"rId910", "rId99"}

    missing = by_rid["rId910"]
    assert missing.evidence["reason"] == "missing_target"
    assert "no_such_slide" in missing.evidence["resolved"]
    assert missing.confidence == 1.0

    dangling = by_rid["rId99"]
    assert dangling.evidence["reason"] == "dangling_rId"
    assert dangling.slide_index == 0


def test_clean_deck_has_no_reference_issues(tmp_path):
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    path = tmp_path / "ref_clean.pptx"
    prs.save(str(path))
    model = build_model(str(path), QualityConfig())
    issues = list(BrokenReferenceRule(QualityConfig()).check(model))
    assert issues == []
