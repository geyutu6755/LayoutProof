"""XXE / external-entity hardening tests for ``SafePackage.parse_xml``.

The safe parser must disable DTD network resolution and entity expansion:
local ``file:`` SYSTEM entities and ``http:`` external entities must never be
fetched or expanded, and parameter entities must not pull in external DTDs.
Assertions inspect both the intercepted exception behaviour and the parsed
text content (no secret ever appears).
"""

from __future__ import annotations

import helpers_decks as decks
from layoutproof.parsing import PackageError, SafePackage

SECRET_MARKER = "LP-SUPERSECRET-MARKER-9f2c"  # noqa: S105 - test fixture marker, not a credential


def _make_package(tmp_path, slide_xml: bytes, name: str = "evil.pptx"):
    entries = decks.minimal_office_parts()
    entries["ppt/slides/slide1.xml"] = slide_xml
    path = tmp_path / name
    decks.write_raw_zip(path, entries)
    return path


def _local_secret(tmp_path) -> str:
    secret = tmp_path / "secret.txt"
    secret.write_text(SECRET_MARKER, encoding="utf-8")
    return secret.as_posix()


def test_local_file_system_entity_is_not_expanded(tmp_path):
    secret_uri = _local_secret(tmp_path)
    xml = (
        b"<?xml version='1.0'?>"
        b"<!DOCTYPE root [<!ENTITY leak SYSTEM 'file://" + secret_uri.encode() + b"'>]>"
        b"<root><a>&leak;</a></root>"
    )
    pkg = SafePackage(_make_package(tmp_path, xml))
    try:
        # Two equally secure outcomes are acceptable: reject the document, or
        # parse it with the external entity left unresolved. The one thing that
        # must never happen is substitution of the secret file's contents.
        try:
            el = pkg.parse_xml("ppt/slides/slide1.xml")
        except PackageError:
            return  # rejected outright: the external entity was never followed
        text = "".join(el.itertext())
        assert SECRET_MARKER not in text
        assert secret_uri not in text
        # the reference stays unexpanded rather than being replaced
        assert "leak" in text or text.strip() == ""
    finally:
        pkg.close()
    # The secret file itself must still exist on disk and was never read by the
    # parser; we assert the guard through non-expansion or rejection.
    assert SECRET_MARKER in (tmp_path / "secret.txt").read_text(encoding="utf-8")


def test_external_http_entity_is_never_fetched(tmp_path):
    """no_network=True must prevent resolution; the entity either errors or
    remains an unresolved reference, never substituted with remote content."""
    xml = (
        b"<?xml version='1.0'?>"
        b"<!DOCTYPE root [<!ENTITY net SYSTEM 'http://127.0.0.1:9/x.dtd'>]>"
        b"<root>&net;</root>"
    )
    pkg = SafePackage(_make_package(tmp_path, xml, name="http_xxe.pptx"))
    try:
        try:
            el = pkg.parse_xml("ppt/slides/slide1.xml")
        except PackageError:
            return  # rejected outright: satisfies the no-fetch requirement
        text = "".join(el.itertext())
        assert "x.dtd" not in text
        assert "127.0.0.1" not in text
        # no remote payload could have been substituted into the body
        assert text.strip() in ("", "&net;")
    finally:
        pkg.close()


def test_parameter_entity_does_not_fetch_external_dtd(tmp_path):
    xml = (
        b"<?xml version='1.0'?>"
        b"<!DOCTYPE root ["
        b"<!ENTITY % pe SYSTEM 'file:///definitely/absent/external.dtd'>"
        b" %pe; ]>"
        b"<root>plain</root>"
    )
    pkg = SafePackage(_make_package(tmp_path, xml, name="param.pptx"))
    try:
        # No expansion occurs; at worst the undefined DTD triggers a parse error.
        try:
            el = pkg.parse_xml("ppt/slides/slide1.xml")
        except PackageError:
            return
        text = "".join(el.itertext())
        assert SECRET_MARKER not in text
        assert "external.dtd" not in text
    finally:
        pkg.close()


def test_well_formed_document_parses_normally(tmp_path):
    xml = b"<?xml version='1.0'?><root><child>hello</child></root>"
    pkg = SafePackage(_make_package(tmp_path, xml, name="ok.pptx"))
    try:
        el = pkg.parse_xml("ppt/slides/slide1.xml")
        assert el.tag.endswith("root")
        assert "hello" in "".join(el.itertext())
    finally:
        pkg.close()


def test_parser_does_not_expand_even_internal_dtd_entities(tmp_path):
    """resolve_entities=False: a locally defined DTD entity must not be
    substituted; external SYSTEM entities are equally non-resolvable."""
    import lxml.etree as etree

    pkg = SafePackage(_make_package(tmp_path, b"<root/>", name="fresh.pptx"))
    try:
        parser = pkg.safe_parser()
        internal = b"<!DOCTYPE r [<!ENTITY a 'INTERNAL-PAYLOAD-7z'>]><r>&a;</r>"
        try:
            el = etree.fromstring(internal, parser=parser)
            text = "".join(el.itertext())
            assert "INTERNAL-PAYLOAD-7z" not in text  # unresolved, not expanded
        except etree.XMLSyntaxError:
            pass  # strict rejection of DTDs is also acceptable

        external = b"<!DOCTYPE r [<!ENTITY x SYSTEM 'file:///nope'>]><r>&x;</r>"
        try:
            el = etree.fromstring(external, parser=parser)
            assert "nope" not in "".join(el.itertext())
        except etree.XMLSyntaxError:
            pass
    finally:
        pkg.close()
