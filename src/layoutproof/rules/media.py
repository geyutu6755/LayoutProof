"""Rule: broken or unreadable media (images) inside the package.

Deterministic, offline checks performed directly against the OOXML zip:

* an image relationship (blip -> ``ppt/media/*``) points at a part that is
  missing from the package (deleted / corrupted media file), or
* a ghost image relationship exists with no resolvable target part.

python-pptx silently drops relationship entries whose target part cannot be
resolved when it loads a deck, so we read the raw ``.rels`` XML ourselves
through :class:`SafePackage` instead of trusting the parsed rel list.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, SafePackage
from .base import Rule, register_rule

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


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
                    if pkg.has_part(resolved):
                        continue
                    yield self._issue(
                        slide,
                        None,
                        detail=f"image part missing from package: {resolved}",
                        evidence={
                            "reason": "missing_image_part",
                            "rId": rel.get("Id"),
                            "target": target,
                            "resolved": resolved,
                        },
                    )
        finally:
            pkg.close()
