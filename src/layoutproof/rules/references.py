"""Rule: broken internal references / hyperlinks / slide jumps.

Offline detection performed directly against the OOXML package (python-pptx
silently drops relationship entries whose target part fails to resolve while
loading, so the parsed rel list cannot be trusted for this check):

* an internal relationship whose target part does not exist in the package
  (e.g. a hyperlink/slide-jump rId pointing to a deleted slide part),
* a *dangling relationship reference*: the slide XML uses ``r:id`` /
  ``r:embed`` / ``r:link`` for an rId that has no entry at all in that
  slide's ``.rels``,
* external ``http(s)`` / ``mailto`` URLs are explicitly out of scope.

When the broken relationship is referenced by an ``hlinkClick`` action in the
slide XML (e.g. ``ppaction://hlinksldjump``), the action is surfaced as
evidence.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel, SafePackage
from .base import Rule, register_rule

_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@register_rule
class BrokenReferenceRule(Rule):
    rule_id = RuleId.BROKEN_REFERENCE
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
                slide_xml = pkg.parse_xml(slide_part)
                root = pkg.parse_xml(rels_name)

                rel_ids: set[str] = set()
                for rel in root:
                    if rel.tag != f"{{{_REL_NS}}}Relationship":
                        continue
                    rel_ids.add(rel.get("Id") or "")
                    rtype = rel.get("Type") or ""
                    target = rel.get("Target") or ""
                    mode = rel.get("TargetMode") or ""
                    if mode == "External" or target.startswith(("http://", "https://", "mailto:")):
                        continue  # external URLs are not judged offline
                    if "/image" in rtype:
                        continue  # media_broken owns image parts
                    resolved = posixpath.normpath(
                        posixpath.join(posixpath.dirname(slide_part), target)
                    )
                    if pkg.has_part(resolved):
                        continue
                    rid = rel.get("Id")
                    action = self._action_for(slide_xml, rid)
                    yield self._issue(
                        slide,
                        None,
                        detail=f"internal reference does not resolve: {resolved}",
                        evidence={
                            "reason": "missing_target",
                            "rId": rid,
                            "target": target,
                            "resolved": resolved,
                            "rel_type": rtype,
                            "action": action,
                        },
                    )

                # Dangling reference: slide XML uses an rId that has no entry
                # in this slide's .rels at all.
                referenced = self._referenced_rids(slide_xml)
                for rid in sorted(referenced - rel_ids):
                    yield self._issue(
                        slide,
                        None,
                        detail=f"dangling relationship reference: {rid} has no entry in .rels",
                        evidence={
                            "reason": "dangling_rId",
                            "rId": rid,
                        },
                    )
        finally:
            pkg.close()

    @staticmethod
    def _referenced_rids(slide_xml) -> set[str]:
        """Collect every r:id / r:embed / r:link value used in the slide XML."""
        out: set[str] = set()
        try:
            for node in slide_xml.iter():
                for attr in ("id", "embed", "link"):
                    value = node.get(f"{{{_R}}}{attr}")
                    if value:
                        out.add(value)
        except Exception:
            pass
        return out

    @staticmethod
    def _action_for(slide_xml, rid: str | None) -> str | None:
        """Find the action attribute on an hlinkClick element using this rId."""
        if not rid:
            return None
        try:
            for node in slide_xml.iter():
                if node.get(f"{{{_R}}}id") == rid:
                    action = node.get("action")
                    if action:
                        return action
        except Exception:
            pass
        return None
