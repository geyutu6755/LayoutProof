"""Rule: common Simplified-Chinese typesetting problems (heuristic).

Only fires on text that actually contains CJK characters. Low-false-positive
checks, each tagged in ``evidence.hit_types``:

* ``kinsoku_line_start``  - a paragraph/line opens with a closing punctuation
  that should never begin a line (行頭禁則: e.g. 。，、；：？！」』】》…),
* ``kinsoku_line_end``    - a paragraph/line closes with an opening punctuation
  that should never end a line (行末禁則: e.g. （「『【《“),
* ``cjk_latin_space``     - two or more ASCII spaces between a CJK character
  and an ASCII letter/digit (多个连续中西文空格；单个正常空格不报，
  glued 零空格属风格选择也不报),
* ``halfwidth_punct``     - half-width ASCII punctuation adjacent to CJK text
  where full-width punctuation is expected (全/半角混用).

The kinsoku check operates at paragraph granularity (a PPT paragraph is the
closest offline proxy for a wrapped line), which is why this stays a 0.75
confidence heuristic rather than a deterministic finding.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import Issue, RuleId
from ..parsing import PresentationModel
from .base import Rule, register_rule

_CJK = r"[\u3400-\u4dbf\u4e00-\u9fff]"
_CJK_RE = re.compile(_CJK)

# 行頭禁則：不能出现在行首的闭合标点（closing punctuation）。
KINSOKU_LINE_START = set("、。，．；：？！”’）」』］｝》〉…—·")
# 行末禁則：不能出现在行末的开放标点（opening punctuation）。
KINSOKU_LINE_END = set("（(「『［｛【《〈〔“‘")

# 中文/全角字符与拉丁字母或数字之间夹着 >=2 个连续 ASCII 空白。
# 单个正常中西文空格（zhRym/现代中文排版推荐的正确间距）不报。
_CJK_LATIN_SPACE_RE = re.compile(rf"{_CJK}[ \t]{{2,}}[A-Za-z0-9]|[A-Za-z0-9][ \t]{{2,}}{_CJK}")

# 半角标点紧邻中文（小数点两侧均为数字的情况被排除，避免误报 3.14）。
_HALFWIDTH_PUNCT_RE = re.compile(
    rf"{_CJK}[,;:!?.)]"  # 中文 + 半角标点
    rf"|[,;:!?]{_CJK}"  # 半角标点 + 中文
    rf"|{_CJK}\.(?![0-9])"  # 中文.非数字
    rf"|(?<![0-9])\.{_CJK}"  # 非数字.中文
)


@register_rule
class CjkTypographyRule(Rule):
    rule_id = RuleId.CJK_TYPOGRAPHY
    confidence = 0.75

    def check(self, model: PresentationModel) -> Iterable[Issue]:
        for slide in model.slides:
            for shape in slide.visible_shapes:
                if not shape.paragraphs:
                    continue
                hit_types: set[str] = set()
                kinsoku_hits: list[str] = []

                for para in shape.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    if not _CJK_RE.search(text):
                        continue
                    if text[0] in KINSOKU_LINE_START:
                        hit_types.add("kinsoku_line_start")
                        kinsoku_hits.append(f"start:{text[0]}")
                    if text[-1] in KINSOKU_LINE_END:
                        hit_types.add("kinsoku_line_end")
                        kinsoku_hits.append(f"end:{text[-1]}")

                full_text = "\n".join(p.text for p in shape.paragraphs)
                if not _CJK_RE.search(full_text):
                    continue
                if _CJK_LATIN_SPACE_RE.search(full_text):
                    hit_types.add("cjk_latin_space")
                if _HALFWIDTH_PUNCT_RE.search(full_text):
                    hit_types.add("halfwidth_punct")

                if not hit_types:
                    continue
                yield self._issue(
                    slide,
                    shape,
                    detail=f"CJK typesetting issue: {', '.join(sorted(hit_types))}",
                    evidence={
                        "hit_types": sorted(hit_types),
                        "kinsoku_hits": kinsoku_hits,
                        "line_start_forbidden": "".join(sorted(KINSOKU_LINE_START)),
                        "line_end_forbidden": "".join(sorted(KINSOKU_LINE_END)),
                        "sample": full_text[:80],
                    },
                )
