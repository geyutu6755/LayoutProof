"""Unit tests for the broken_reference rule (zip surgery injects broken rels)."""

from __future__ import annotations

import zipfile

from pptx import Presentation

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.references import BrokenReferenceRule


def _rebuild(src, dst, extra_rels: dict[str, str]):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in extra_rels:
                text = data.decode("utf-8")
                assert "</Relationships>" in text
                data = text.replace(
                    "</Relationships>", extra_rels[item.filename] + "</Relationships>"
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
    patch = (
        # positive: internal hyperlink -> slide part that does not exist
        f'<Relationship Id="rId910" Type="{hyperlink}" Target="../slides/no_such_slide.xml"/>'
        # negative 1: external URL -> out of scope
        f'<Relationship Id="rId911" Type="{hyperlink}" Target="https://example.com" TargetMode="External"/>'
        # negative 2: internal rel to an existing slide part
        f'<Relationship Id="rId912" Type="{slide_rel}" Target="slide2.xml"/>'
    )

    broken = tmp_path / "ref_broken.pptx"
    _rebuild(raw, broken, {"ppt/slides/_rels/slide1.xml.rels": patch})

    model = build_model(str(broken), QualityConfig())
    issues = list(BrokenReferenceRule(QualityConfig()).check(model))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "broken_reference"
    assert issue.confidence == 1.0
    assert issue.evidence["rId"] == "rId910"
    assert "no_such_slide" in issue.evidence["target"]
    assert issue.slide_index == 0
