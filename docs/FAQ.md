# FAQ — LayoutProof

[English](#english) · [中文](#中文)

---

## English

### What does LayoutProof actually do?

It opens a `.pptx` on your machine and reports layout, readability,
accessibility and package-integrity problems — off-slide objects, text
overflow, tiny fonts, low contrast, broken media/references, leftover
placeholders and CJK typography. Every finding has a severity, an exact
location and a recommended fix. It does not upload anything.

### Do I need PowerPoint or LibreOffice installed?

No. The core detection and the safe fixes run fully offline with no Office
application. LibreOffice is only needed if you want *real rendered slide
images*; when it is absent the tool tells you it is using a static fallback
instead of pretending otherwise.

### Is my file modified?

No. The source is read-only and its SHA-256 is checked before and after.
Fixes always write a separate file (plus an optional backup).

### What is the difference between the `core` and `full` profiles?

`core` (default) runs seven high-confidence, low-false-positive rules.
`full` adds style/accessibility rules such as overlap, blank slides,
contrast, alt text and CJK typography.

### How do I use it in CI or an agent loop?

Use the stable JSON output and the exit code. `0` means the gate passed,
`1` means findings at or above the threshold, `2` is a usage/input error,
and `3` is an internal error. See
[`docs/AGENT_INTEGRATION.md`](AGENT_INTEGRATION.md) for the full contract.

### Why is a problem reported as `unchanged` after a fix?

A safe repair was applied but the heuristic still crosses the threshold.
You should change the generator and regenerate rather than repeatedly
running the same fix. LayoutProof never deletes content to force a pass.

### Which issues cannot be fixed automatically?

Overlap, blank slides, broken media, broken references, structural
anomalies and missing alt text need a human decision. They are returned
under `skipped` with a reason and a recommended path, never faked.

### Does it support Word, `.ppt`, or Keynote?

The first release targets `.pptx` only. Word/.docx is planned later;
legacy `.ppt` and Keynote are not supported.

### How accurate is it?

On the 66-file independent evaluation, judged items score
Precision = Recall = F1 = 1.0 with 0 false positives / 0 false negatives.
That result is specific to that corpus and its ground truth; explicitly
unknown cases are excluded rather than hidden.

---

## 中文

### LayoutProof 到底做什么？

它在本机打开 `.pptx`，报告版式、可读性、可访问性与包完整性问题——越界对象、文字溢出、字号过小、对比度过低、媒体/引用损坏、占位符残留和中文排版。每条问题都带严重度、精确位置和修复建议，全程不上传任何数据。

### 我需要安装 PowerPoint 或 LibreOffice 吗？

不需要。核心检测与安全修复完全离线运行，不依赖 Office 应用。只有在需要*真实渲染图*时才用到 LibreOffice；缺失时会明确告知使用静态回退，而不是假装已渲染。

### 我的文件会被修改吗？

不会。源文件只读，修复前后会校验 SHA-256。修复总是写入独立新文件（可另选备份）。

### `core` 和 `full` 两个 profile 有什么区别？

`core`（默认）运行 7 条高置信、低误报规则；`full` 额外开启重叠、空白页、对比度、替代文本和中文排版等样式/可访问性规则。

### 如何在 CI 或 Agent 闭环中使用？

使用稳定的 JSON 输出和退出码：`0` 表示门禁通过，`1` 表示存在达到阈值的问题，`2` 为用法/输入错误，`3` 为内部错误。完整契约见 [`docs/AGENT_INTEGRATION.md`](AGENT_INTEGRATION.md)。

### 为什么修复后某问题被标记为 `unchanged`？

安全修复已应用，但启发式判断仍超过阈值。你应修改生成器并重新生成，而不是反复运行同一修复。LayoutProof 绝不会为了通过而删除内容。

### 哪些问题不能自动修复？

重叠、空白页、媒体损坏、引用损坏、结构异常和缺失替代文本需要人工判断，会列入 `skipped` 并给出原因和建议路径，绝不伪造。

### 支持 Word、`.ppt` 或 Keynote 吗？

首个版本只针对 `.pptx`；Word/.docx 计划后续支持，旧版 `.ppt` 与 Keynote 不支持。

### 它的准确率如何？

在 66 份独立评测上，已判定项的精确率、召回率、F1 均为 1.0，0 误报 / 0 漏报。该结果仅针对该语料及其标注，明确未知的情况会被排除而非隐藏。
