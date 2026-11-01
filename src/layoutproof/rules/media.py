"""Rule: broken or unreadable media (images) inside the package.

Deterministic, offline checks performed directly against the OOXML zip:

* an image relationship (blip -> ``ppt/media/*``) points at a part that is
  missing from the package,
* the image part exists but its bytes are not a decodable image: we first
  check the magic signature (PNG/JPEG/GIF), then try ``PIL.Image.open`` plus
  ``verify()``/``load()`` -- any failure yields ``bad_signature`` or
  ``decode_error`` evidence.

python-pptx silently drops relationship entries whose target part cannot be
resolved when it loads a deck, so we read the raw ``.rels`` XML ourselves
through :class:`SafePackage` instead of trusting the parsed rel list.
"""

from __future__ import annotations

import io
import posixpath
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, SafePackage
from .base import Rule, register_rule

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8"
_GIF_SIG = b"GIF8"


def _image_content_error(data: bytes) -> str | None:
    """Return None for a valid image, otherwise 'bad_signature'/'decode_error'."""
    if len(data) < 8:
        return "bad_signature"
    if not (
        data[:8] == _PNG_SIG
        or data[:2] == _JPEG_SIG
        or data[:4] == _GIF_SIG
    ):
        return "bad_signature"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
    except Exception:
        return "decode_error"
    return None


@register_rule
class MediaBrokenRule(Rule):
    rule_id = RuleId.MEDIA_BROKEN
    confidence = 1.0

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        pkg = SafePackage(model.path, self.config)
        try:
            for slide in model.slides:
                slide_part = slide.part_name.lstrip("/")
                rels_name = posixpath.join(
                    posixpath.dirname(slide_part), "_rels", posixpath.basename(slide_part) + ".rels"
                )
                if not pkg.has_part(rels_name):
                    continue
                root = pkg.parse_xml(rels_name)
                for rel in root:
                    if rel.tag != f"{{{_REL_NS}}}Relationship":
                        continue
                    rtype = rel.get("Type") or ""
                    if "/image" not in rtype:
                        continue
                    target = rel.get("Target") or ""
                    mode = rel.get("TargetMode") or ""
                    if mode == "External" or target.startswith(("http://", "https://", "mailto:")):
                        continue
                    resolved = posixpath.normpath(
                        posixpath.join(posixpath.dirname(slide_part), target)
                    )
                    reason: str | None = None
                    extra: dict = {}
                    if not pkg.has_part(resolved):
                        reason = "missing_image_part"
                    else:
                        try:
                            data = pkg.read(resolved)
                        except Exception as exc:
                            reason = "unreadable_part"
                            extra = {"read_error": str(exc)}
                        else:
                            err = _image_content_error(data)
                            if err is not None:
                                reason = err
                    if reason is None:
                        continue
                    if reason == "missing_image_part":
                        detail = f"image part missing from package: {resolved}"
                    elif reason == "unreadable_part":
                        detail = f"image part unreadable: {resolved}"
                    else:
                        detail = f"image content invalid ({reason}): {resolved}"
                    yield self._issue(
                        slide,
                        None,
                        detail=detail,
                        evidence={
                            "reason": reason,
                            "rId": rel.get("Id"),
                            "target": target,
                            "resolved": resolved,
                            **extra,
                        },
                    )
        finally:
            pkg.close()
