"""Adversarial tests for the on-disk zip loader in ``parsing/package.py``.

Targets the real implementation: ZIP-slip / absolute / backslash member names,
duplicate entries, entry and uncompressed-size quotas, missing required parts,
bad archives, oversize files, on-demand (never-to-disk) reads and malformed
XML parts. Every assertion reflects an actual intercepted behaviour or error
message from :class:`SafePackage`.
"""

from __future__ import annotations

import zipfile

import pytest

import helpers_decks as decks
from layoutproof.config import QualityConfig
from layoutproof.parsing import PackageError, SafePackage
import layoutproof.parsing.package as pkg_mod
from layoutproof.parsing.package import _is_unsafe_name


def test_empty_member_name_is_unsafe():
    assert _is_unsafe_name("") is True
    assert _is_unsafe_name("ppt/slides/slide1.xml") is False
    assert _is_unsafe_name("ppt/slides/./slide1.xml") is False


# ---------------------------------------------------------------------------
# Rejected archive inputs
# ---------------------------------------------------------------------------
def test_missing_path_rejected(tmp_path):
    with pytest.raises(PackageError, match="File not found"):
        SafePackage(tmp_path / "nope.pptx")


def test_directory_rejected(tmp_path):
    with pytest.raises(PackageError, match="Not a file"):
        SafePackage(tmp_path)


def test_unsupported_suffix_rejected(tmp_path):
    f = tmp_path / "deck.txt"
    f.write_bytes(b"PK\x03\x04")
    with pytest.raises(PackageError, match="Unsupported file type"):
        SafePackage(f)


def test_non_zip_bytes_rejected(tmp_path):
    f = tmp_path / "garbage.pptx"
    f.write_bytes(b"this is plain text, not a zip archive")
    with pytest.raises(PackageError, match="Not a valid zip/pptx package"):
        SafePackage(f)


def test_oversize_file_rejected_before_parsing(tmp_path):
    f = decks.save_clean_deck(tmp_path / "clean.pptx")
    cfg = QualityConfig(max_file_size_mb=0)  # zero budget rejects any non-empty file
    with pytest.raises(PackageError, match="exceeds max size"):
        SafePackage(f, config=cfg)


# ---------------------------------------------------------------------------
# Member-name attacks: zip slip, absolute paths, drive letters, backslashes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_name", [
    "../evil.txt",
    "../../../windows/system32/evil.bin",
    "ppt/../../secret.cfg",
    "/etc/passwd",
])
def test_unsafe_member_names_are_flagged_never_extracted(tmp_path, bad_name):
    entries = decks.minimal_office_parts()
    entries[bad_name] = b"payload"
    pkg_path = decks.write_raw_zip(tmp_path / "slip.pptx", entries)

    before = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
    pkg = SafePackage(pkg_path)
    try:
        joined = "\n".join(pkg.anomalies)
        assert "Unsafe zip entry name" in joined
        # the dangerous part is deliberately excluded from the trusted set
        assert not pkg.has_part(bad_name)
        # normal parts remain readable and nothing is written to disk anywhere
        assert pkg.has_part("ppt/slides/slide1.xml")
        assert pkg.read("ppt/slides/slide1.xml")
        after = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")}
        assert after <= before | {pkg_path.name}
    finally:
        pkg.close()


@pytest.mark.parametrize("bad_name,expected", [
    ("", True),
    ("../evil.txt", True),
    ("ppt/../../secret.cfg", True),
    ("/etc/passwd", True),
    (r"C:\Windows\win.ini", True),
    (r"ppt\slides\slide1.xml", True),
    ("a\\b", True),
    ("ppt/slides/slide1.xml", False),
    ("./ppt/notes.xml", False),
])
def test_name_classifier_blocks_windows_style_and_absolute_names(bad_name, expected):
    # zipfile normalises backslashes on write, so the backslash / drive-letter
    # branches of the classifier are verified at the pure-function level.
    assert _is_unsafe_name(bad_name) is expected


def test_benign_member_names_pass_clean(tmp_path):
    entries = decks.minimal_office_parts()
    entries["ppt/slides/slideLayout1.xml"] = b"<a/>"
    entries["./ppt/notes.xml"] = b"<a/>"
    pkg_path = decks.write_raw_zip(tmp_path / "ok.pptx", entries)
    pkg = SafePackage(pkg_path)
    try:
        assert not any("Unsafe zip entry name" in a for a in pkg.anomalies)
        assert pkg.has_part("ppt/slides/slide1.xml")
    finally:
        pkg.close()


# ---------------------------------------------------------------------------
# Duplicate entries and structural requirements
# ---------------------------------------------------------------------------
def test_duplicate_member_entry_flagged_and_deduped(tmp_path):
    entries = decks.minimal_office_parts()
    bad = decks.write_raw_zip(
        tmp_path / "dup.pptx", entries,
        duplicates=[("ppt/slides/slide1.xml", b"<another copy/>")],
    )
    pkg = SafePackage(bad)
    try:
        assert any("Duplicate zip entry" in a for a in pkg.anomalies)
        # membership uses the deduplicated trusted set, not raw occurrence count
        assert pkg.has_part("ppt/slides/slide1.xml")
    finally:
        pkg.close()


def test_missing_required_parts_recorded_as_anomalies(tmp_path):
    f = decks.write_raw_zip(tmp_path / "naked.pptx", {"ppt/random.xml": b"<x/>"})
    pkg = SafePackage(f)
    try:
        joined = "\n".join(pkg.anomalies)
        assert "Missing required [Content_Types].xml" in joined
        assert "Missing ppt/presentation.xml main part" in joined
    finally:
        pkg.close()


# ---------------------------------------------------------------------------
# Quotas: entry count and aggregate uncompressed size
# ---------------------------------------------------------------------------
def test_entry_count_quota_monitored(tmp_path, monkeypatch):
    monkeypatch.setattr(pkg_mod, "MAX_ENTRIES", 5)
    entries = {f"ppt/many/{i}.xml": b"<x/>" for i in range(8)}
    entries.update(decks.minimal_office_parts())
    f = decks.write_raw_zip(tmp_path / "many.pptx", entries)
    pkg = SafePackage(f)
    try:
        assert any("entries (limit 5)" in a for a in pkg.anomalies)
    finally:
        pkg.close()


def test_uncompressed_size_quota_monitored(tmp_path, monkeypatch):
    monkeypatch.setattr(pkg_mod, "MAX_TOTAL_UNCOMPRESSED", 2048)
    entries = decks.minimal_office_parts()
    entries["ppt/slides/big.xml"] = b"A" * 5000
    f = decks.write_raw_zip(tmp_path / "big.pptx", entries)
    pkg = SafePackage(f)
    try:
        assert any("exceeds uncompressed size limits" in a for a in pkg.anomalies)
    finally:
        pkg.close()


# ---------------------------------------------------------------------------
# Reads: missing / corrupt parts and XML parsing errors
# ---------------------------------------------------------------------------
def test_read_missing_part_raises_package_error(tmp_path):
    f = decks.write_raw_zip(tmp_path / "min.pptx", decks.minimal_office_parts())
    pkg = SafePackage(f)
    try:
        with pytest.raises(PackageError, match="Missing package part"):
            pkg.read("ppt/slides/absent.xml")
    finally:
        pkg.close()


def test_parse_xml_malformed_part_raises_package_error(tmp_path):
    entries = decks.minimal_office_parts()
    entries["ppt/slides/slide1.xml"] = b"<p:sld><unclosed><"
    f = decks.write_raw_zip(tmp_path / "badxml.pptx", entries)
    pkg = SafePackage(f)
    try:
        with pytest.raises(PackageError, match="Malformed XML in ppt/slides/slide1.xml"):
            pkg.parse_xml("ppt/slides/slide1.xml")
    finally:
        pkg.close()


def test_high_ratio_compressible_payload_read_in_memory_only(tmp_path):
    """A tiny on-disk zip decompressing to a large repetitive member must be
    read on demand without ever being extracted to the filesystem."""
    entries = decks.minimal_office_parts()
    entries["ppt/slides/filler.xml"] = b"<x>" + b"A" * 200_000 + b"</x>"
    f = decks.write_raw_zip(tmp_path / "ratio.pptx", entries)
    disk_bytes = f.stat().st_size
    assert disk_bytes < 50_000  # highly compressed on disk
    before = set(tmp_path.rglob("*"))
    pkg = SafePackage(f)
    try:
        data = pkg.read("ppt/slides/filler.xml")
        assert len(data) == 200_000 + 7
    finally:
        pkg.close()
    after = set(tmp_path.rglob("*"))
    assert after == before  # no extraction artefacts left on disk


def test_zipfile_object_closed_on_context_exit(tmp_path):
    f = decks.write_raw_zip(tmp_path / "ctx.pptx", decks.minimal_office_parts())
    with SafePackage(f) as pkg:
        assert pkg.read("ppt/presentation.xml")
    # closing twice must not raise
    pkg.close()
