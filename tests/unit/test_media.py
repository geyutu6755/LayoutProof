"""Unit tests for the media_broken rule (zip surgery creates broken media)."""

from __future__ import annotations

import io
import zipfile

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from layoutproof.config import QualityConfig
from layoutproof.parsing import build_model
from layoutproof.rules.media import MediaBrokenRule


def _png_bytes(color=(10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, "PNG")
    return buf.getvalue()


def _rebuild(src, dst, drop=(), extra_rels: dict[str, str] | None = None):
    """Rewrite the zip, optionally dropping parts and appending rels."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in drop:
                continue
            data = zin.read(item.filename)
            if extra_rels and item.filename in extra_rels:
                text = data.decode("utf-8")
                assert "</Relationships>" in text
                data = text.replace("</Relationships>", extra_rels[item.filename] + "</Relationships>").encode("utf-8")
            zout.writestr(item, data)


def _list_media(path):
    with zipfile.ZipFile(path) as zf:
        return sorted(n for n in zf.namelist() if n.startswith("ppt/media/"))


def test_media_broken_positive_and_negative(tmp_path):
    prs = Presentation()

    # slide 1: healthy image
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    s1.shapes.add_picture(io.BytesIO(_png_bytes((10, 120, 200))), Inches(1), Inches(1), Inches(2), Inches(1))

    # slide 2: healthy image now, its part will be deleted from the zip
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    s2.shapes.add_picture(io.BytesIO(_png_bytes((200, 30, 30))), Inches(1), Inches(1), Inches(2), Inches(1))

    raw = tmp_path / "media_raw.pptx"
    prs.save(str(raw))
    media = _list_media(raw)
    assert len(media) == 2

    ghost_rel = (
        '<Relationship Id="rId900" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/ghost.png"/>'
    )
    broken = tmp_path / "media_broken.pptx"
    _rebuild(
        raw,
        broken,
        drop={media[1]},  # delete slide 2's image part
        extra_rels={"ppt/slides/_rels/slide1.xml.rels": ghost_rel},
    )

    model = build_model(str(broken), QualityConfig())
    issues = list(MediaBrokenRule(QualityConfig()).check(model))

    # two positives: deleted part on slide 2, ghost image rel on slide 1
    assert len(issues) == 2
    reasons = {i.evidence.get("reason") for i in issues}
    assert reasons == {"missing_image_part"}
    resolved = {i.evidence["resolved"] for i in issues}
    assert "ppt/media/image2.png" in resolved
    assert any("ghost.png" in r for r in resolved)

    # slide 2 (index 1) lost its media file
    assert 1 in {i.slide_index for i in issues}
    assert all(i.rule_id == "media_broken" and i.confidence == 1.0 for i in issues)


def test_healthy_deck_has_no_media_issues(tmp_path):
    blob = _png_bytes()
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(1), Inches(2), Inches(1))
    path = tmp_path / "media_ok.pptx"
    prs.save(str(path))
    model = build_model(str(path), QualityConfig())
    issues = list(MediaBrokenRule(QualityConfig()).check(model))
    assert issues == []


def test_existing_but_corrupt_image_is_flagged(tmp_path):
    """Image part exists in the package but its bytes are not a real image."""
    blob = _png_bytes((10, 120, 200))
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(io.BytesIO(blob), Inches(1), Inches(1), Inches(2), Inches(1))
    raw = tmp_path / "media_corrupt_raw.pptx"
    prs.save(str(raw))

    broken = tmp_path / "media_corrupt.pptx"
    garbage = b"\x00\x01NOT_A_REAL_PNG" + b"\x00" * 28  # 36 bytes, bad magic
    with zipfile.ZipFile(raw) as zin, zipfile.ZipFile(
        broken, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = garbage if item.filename == "ppt/media/image1.png" else zin.read(item.filename)
            zout.writestr(item, data)

    model = build_model(str(broken), QualityConfig())
    issues = list(MediaBrokenRule(QualityConfig()).check(model))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule_id == "media_broken"
    assert issue.evidence["reason"] == "bad_signature"
    assert issue.evidence["resolved"] == "ppt/media/image1.png"
