"""Defensive handling of damaged relationships and hostile textual content.

The scanner must never crash on damaged .rels parts and must never treat
deck-supplied text (shape names / details) as executable markup. Escape
behaviour for the HTML report lives in ``tests/contract/test_html_output_safety.py``;
here we cover the scanning and JSON layers plus on-disk containment.
"""

from __future__ import annotations

import zipfile

import pytest
from pptx.util import Inches

import helpers_decks as decks
from layoutproof.cli import main
from layoutproof.engine import scan_file
from layoutproof.parsing import PackageError, SafePackage
from layoutproof.report import validate_output


def _repack_with_rewritten_part(src_pptx, target_pptx, part_name: str, new_bytes: bytes):
    with zipfile.ZipFile(src_pptx, "r") as zin, \
            zipfile.ZipFile(target_pptx, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == part_name:
                data = new_bytes
            zout.writestr(item, data)


def _slide_rels_name(pptx_path) -> str:
    with zipfile.ZipFile(pptx_path) as z:
        return next(n for n in z.namelist()
                     if n.startswith("ppt/slides/_rels/") and n.endswith(".rels"))


def test_corrupt_relationships_part_degrades_to_status_error(tmp_path, capsys):
    good = decks.save_clean_deck(tmp_path / "good.pptx")
    rels_name = _slide_rels_name(good)
    broken = tmp_path / "broken_rels.pptx"
    _repack_with_rewritten_part(
        good, broken, rels_name,
        b'<?xml version="1.0"?><Relationships><Relationship Id="rId1" Broken >>>',
    )

    result = scan_file(broken, profile="full")
    assert result.status == "error"
    assert result.error
    validate_output(result.to_dict())

    code = main(["scan", str(broken)])
    assert code == 2  # usage/abort, never internal code 3
    assert "Failed to scan" in capsys.readouterr().out


def test_truncated_zip_with_pptx_extension_never_raises_out(tmp_path):
    good = decks.save_clean_deck(tmp_path / "good.pptx")
    data = good.read_bytes()
    for cut in (0.5, 0.2, 0.02):
        bad = tmp_path / f"trunc_{int(cut*100)}.pptx"
        bad.write_bytes(data[: max(8, int(len(data) * cut))])
        result = scan_file(bad, profile="core")
        assert result.status in ("ok", "error")
        validate_output(result.to_dict())


def test_hostile_text_in_shape_names_survives_json_safely(tmp_path):
    path = tmp_path / "hostile_names.pptx"
    prs = decks.blank_prs()
    slide = decks.add_blank_slide(prs)
    payload = "<script>alert(1)</script> & \"quoted\" 'apos'"
    decks.add_textbox(slide, Inches(1), Inches(1),
                      Inches(6), Inches(1),
                      "body", font_pt=18, name=payload)
    prs.save(str(path))

    result = scan_file(path, profile="full")
    payload_dict = result.to_dict()
    validate_output(payload_dict)
    # JSON layer keeps the literal text as data (escaped by json.dumps later);
    # it must not be interpreted during scanning and must not crash detection.
    assert isinstance(payload_dict["issues"], list)


def test_unsafe_member_is_untrusted_but_never_extracted_to_disk(tmp_path):
    entries = decks.minimal_office_parts()
    entries["../secret.txt"] = b"cannot-reach-me"
    f = decks.write_raw_zip(tmp_path / "with_slip.pptx", entries)
    pkg = SafePackage(f)
    try:
        # trusted membership gate excludes traversal members from rule logic
        assert not pkg.has_part("../secret.txt")
        # raw in-memory access does not materialise anything on disk
        before = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
        assert pkg.read("../secret.txt") == b"cannot-reach-me"
        after = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
        assert after == before
        # a genuinely missing member surfaces as a PackageError
        with pytest.raises(PackageError, match="Missing package part"):
            pkg.read("ppt/slides/absent.xml")
    finally:
        pkg.close()
