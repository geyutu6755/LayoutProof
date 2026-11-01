# LayoutProof

**Local-first, deterministic quality assurance for PowerPoint (`.pptx`) files — built for AI-generated decks and the agents that produce them.**

[English](#-english-documentation) · [中文文档](#-中文文档)

---

## 🇬🇧 English Documentation

### What it is

LayoutProof inspects `.pptx` files on your own machine and flags layout, readability, accessibility and package-integrity problems before a deck is shipped. It is aimed squarely at the *happy path failure mode* of generative slide pipelines: text that overflows its box, objects parked off-slide, 8&nbsp;pt body copy, broken media relationships, leftover `click to add title` placeholders, and simplified-Chinese typography glitches.

> One-line value: **catch broken AI-generated decks locally, with stable JSON and exit codes an agent can act on — no upload, no subscription, no PowerPoint required.**

### Who it is for

- **AI / LLM agents and slide-generation pipelines** that emit `.pptx` and need a deterministic quality gate in CI or in an agent loop.
- **Developers and content teams** building decks programmatically (python-pptx, templates, RAG-to-slide) who want low-false-positive linting.
- **Chinese-language deck authors** who need simplified-Chinese typography checks (kinsoku, CJK–Latin spacing, full/half-width punctuation).

### Core features

- **Fully offline.** No network calls, no telemetry, no cloud upload. Pure Python on your machine.
- **12 stable, versioned rules** across geometry, typography, accessibility and OOXML package integrity.
- **Two profiles.** `core` (default) ships 7 high-confidence, low-false-positive rules; `full` enables all 12.
- **Agent-friendly contract.** A machine-readable JSON report (schema `1.0`) plus a four-value exit code that CI and agents can branch on.
- **Safe by construction.** Reads `.pptx` as a hardened zip/XML stream, never executes embedded content, and refuses to walk outside the files you point it at.
- **Bilingual findings.** Every rule carries an English and a Chinese title, explanation and recommendation.

### Install

Requires **Python ≥ 3.11**.

```bash
# from PyPI (once published)
pip install layoutproof

# or with pipx for an isolated global CLI
pipx install layoutproof

# from a local checkout (development)
pip install -e .[dev]
```

After install, the `layoutproof` command is available:

```bash
layoutproof --version
# LayoutProof 0.1.0a1
```

### Quick start

`scan` is the default command — a bare path is equivalent to `layoutproof scan <path>`.

**Scan a single deck (human-readable report):**

```bash
layoutproof scan test_fixtures/corpus/broken_all.pptx
```

```text
LayoutProof 0.1.0a1 - broken_all.pptx
========================================
Slides: 11 | errors 2  warnings 6  info 0

ERROR offslide_object        slide 1 [Rectangle 2]
        Object outside slide bounds
        -> 100% outside slide
        fix: Move the object fully inside the slide bounds, or delete it if it is unused.

WARN  text_overflow          slide 2 [TextBox 2]
        Suspected text overflow or clipping
        -> estimated 13 line(s) need ~402pt but box is only 55pt tall
        fix: Enlarge the text box, reduce the text, or enable auto-fit/shrink text on overflow.

WARN  font_too_small         ...
```

**A clean deck exits `0`:**

```bash
layoutproof scan test_fixtures/corpus/clean_basic.pptx
```

```text
LayoutProof 0.1.0a1 - clean_basic.pptx
========================================
Slides: 2 | errors 0  warnings 0  info 0

No issues found. Deck passed the selected profile.
```

**Scan a whole directory (add `-r` to recurse):**

```bash
layoutproof scan test_fixtures/corpus
layoutproof scan test_fixtures/corpus -r
```

**Emit machine-readable JSON (one object for a single file, an array for many):**

```bash
layoutproof scan deck.pptx --json
```

```json
{
  "schema_version": "1.0",
  "tool": { "name": "layoutproof", "version": "0.1.0a1" },
  "file": { "path": "deck.pptx", "name": "deck.pptx" },
  "status": "ok",
  "error": null,
  "slide_count": 11,
  "summary": { "error": 2, "warning": 6, "info": 0, "total": 8 },
  "issues": [
    {
      "rule_id": "offslide_object",
      "severity": "error",
      "slide_number": 1,
      "shape_name": "Rectangle 2",
      "detail": "100% outside slide",
      "fixable": true
    }
  ]
}
```

**Gate strictly on errors (instead of the default warnings):**

```bash
layoutproof scan deck.pptx --fail-on error
```

**Enable all 12 rules (overlap, blank slides, alt text, CJK typography …):**

```bash
layoutproof scan deck.pptx --profile full
```

**`fix` and `demo` subcommands.** The CLI includes `fix` (safe automatic repairs + re-verify) and `demo` (generate a broken deck and its fixed counterpart). Both are fully wired in this build. The source is never modified: fixes write a new file (and an optional backup), then re-scan it to confirm the reduction.

```text
$ layoutproof fix deck.pptx
Before: 4 issues -> After: 0 (removed 4)
  + increase_font_size (font_too_small)
  + autofit_text (text_overflow)
  + move_into_slide (offslide_object)
  + clear_placeholder (unfinished_placeholder)

$ layoutproof demo --dir ./demo
```

Issues that cannot be repaired safely (overlap, blank, media, references, alt text, structure) are reported as skipped with a manual-review note rather than faked.

### JSON output & exit codes

`layoutproof scan` writes a JSON document conforming to `src/layoutproof/report/schema.json` (`schema_version: "1.0"`). Top-level keys: `tool`, `file`, `status` (`ok` | `error`), `error`, `slide_count`, `summary` (`error`/`warning`/`info`/`total`), `issues[]`, and the effective `config`. Each issue carries `rule_id`, `severity`, `slide_index`/`slide_number`, `shape_id`/`shape_name`, `location`/`normalized_location` (EMU and fraction of slide), `detail`, `confidence`, `fixable`, `fix_id` and `evidence`.

| Exit code | Meaning | When |
|---:|---|---|
| `0` | Clean | No issue at or above the `--fail-on` threshold. |
| `1` | Quality gate failed | At least one issue meets/exceeds the threshold (default: any warning). |
| `2` | Usage / input error | Bad arguments, no `.pptx` found at the target, **or** a file that cannot be opened as a valid zip/OOXML package. |
| `3` | Internal error | Unexpected failure, or a subcommand whose engine is not present in this build. |

Default `--fail-on` is `warning`: warnings fail the build, info does not. Set `--fail-on error` to gate only on deterministic errors, or `--fail-on info` for the strictest gate.

### Configuration & profiles

Pass a TOML or JSON file with `--config` (a `[tool.layoutproof]` table is also accepted, e.g. in `pyproject.toml`):

```toml
# layoutproof.toml
min_font_size_pt = 14.0        # body text readability floor
min_contrast_ratio = 4.5       # WCAG AA body text
large_text_pt = 18.0           # large-text threshold
large_text_contrast_ratio = 3.0 # large-text contrast floor
overlap_ratio_threshold = 0.30 # share of the smaller shape that counts as overlap
offslide_fraction_threshold = 0.05
overflow_ratio_threshold = 0.15
max_file_size_mb = 100
fail_on = "warning"            # error | warning | info

# enabled_rules = ["offslide_object", "font_too_small"]  # whitelist (overrides profile)
# disabled_rules = ["cjk_typography"]                      # blacklist
```

`--profile` selects which rules run; explicit `enabled_rules` / `disabled_rules` in the config always win over the profile.

| Profile | Rules enabled |
|---|---|
| `core` (default) | `offslide_object`, `font_too_small`, `text_overflow`, `unfinished_placeholder`, `media_broken`, `broken_reference`, `structure_anomaly` |
| `full` | All 12 rules above, plus `object_overlap`, `low_contrast`, `blank_slide`, `missing_alt_text`, `cjk_typography` |

See [`docs/USAGE.md`](docs/USAGE.md) for the full rule catalogue and more config examples.

### Using in GitHub Actions

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"
- name: Install
  run: pip install layoutproof
- name: Quality gate on generated decks
  run: layoutproof scan generated/ --recursive --profile full --fail-on error
```

The repository ships a ready-made CI workflow at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) that installs the package and runs the test suite on Ubuntu and Windows across Python 3.11–3.13.

### Project structure

```
LayoutProof/
├── src/layoutproof/
│   ├── cli.py            # argparse entrypoint (scan/fix/demo)
│   ├── engine.py        # scan_file(): parse -> run rules -> attach anomalies
│   ├── models.py        # frozen data contract, rule catalogue, exit codes
│   ├── config.py        # QualityConfig load (TOML/JSON) and thresholds
│   ├── parsing/         # zip/OOXML package + geometry model
│   ├── rules/           # one module per detection rule
│   ├── fix/             # safe repair engine (new-file output, re-verify)
│   └── report/          # JSON output + schema, self-contained HTML report
├── tests/unit/          # per-rule yin/yang tests
├── test_fixtures/       # generated corpus (.pptx) + manifest
└── docs/USAGE.md         # detailed rule & config reference
```

### Development & testing

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Unix: source .venv/bin/activate
pip install -e .[dev]
pytest
```

Every detection rule ships with *yin* (should fire) and *yang* (should not fire) unit tests under `tests/unit/`. A defect discovered in production is turned into a regression fixture before it is fixed.

### Known limitations

- No rendering: overflow/overlap are estimated from geometry and font metrics, not from a rendered slide. Results are high-precision but approximate.
- No `.ppt` (binary) or `.key` support — only `.pptx`.
- Contrast resolves explicit fills and the master theme background (`bg1`/`tx1`); other theme-derived or gradient-only colors stay conservative.
- Pure-EMU geometry means screen-ratio assumptions follow the slide dimensions in the file.

### License

MIT — see [LICENSE](LICENSE).

### Minimal manual release steps

There is no CI publish step in this repository yet. To cut a release by hand:

1. Bump `version` in `pyproject.toml` and add a `CHANGELOG.md` entry.
2. Ensure `python -m pytest` is green on the supported matrix (3.11/3.12/3.13, Ubuntu + Windows).
3. Build: `python -m build` (requires `pip install build`).
4. Verify the artifact: `twine check dist/*`.
5. Upload: `twine upload dist/*` (you need PyPI maintainer rights).
6. Tag the commit: `git tag vX.Y.Z && git push origin vX.Y.Z`.

---

## 🇨🇳 中文文档

[切换到 English](#-english-documentation)

### 项目定位

LayoutProof 在**本机**对 PowerPoint（`.pptx`）文件做确定性质量检查，在演示文稿交付前拦截版式、可读性、可访问性与包完整性问题。它专门面向生成式幻灯片流水线最常见的失败模式：文字溢出文本框、对象落在页面外、8&nbsp;pt 正文、损坏的媒体关系、残留的 `点击添加标题` 占位符，以及简体中文排版错误。

> 一句话价值：**在本地拦截坏掉的 AI 生成 PPT，输出 Agent 可直接消费的稳定 JSON 与退出码——不上传、不订阅、无需安装 PowerPoint。**

### 目标用户

- **AI / LLM Agent 与幻灯片生成流水线**：需要在 CI 或 Agent 闭环里做确定性质量门禁。
- **程序化生成幻灯片的开发者与内容团队**（python-pptx、模板、RAG 转幻灯片）：需要低误报的 lint。
- **中文 PPT 作者**：需要简体中文排版检查（避头尾、中西文间距、全半角标点）。

### 核心特性

- **完全离线**：无网络请求、无遥测、无云端上传。
- **12 条稳定且带版本号的规则**，覆盖几何、排版、可访问性与 OOXML 包完整性。
- **双 profile**：`core`（默认）7 条高置信低误报规则；`full` 开启全部 12 条。
- **Agent 友好契约**：机器可读 JSON 报告（schema `1.0`）+ 四值退出码。
- **安全构造**：以加固的 zip/XML 流读取 `.pptx`，绝不执行嵌入内容，绝不遍历你指定范围之外的文件。
- **双语结论**：每条规则都带中英文标题、解释与修复建议。

### 安装

需要 **Python ≥ 3.11**。

```bash
# 从 PyPI（发布后）
pip install layoutproof

# 或用 pipx 安装为隔离的全局命令
pipx install layoutproof

# 本地开发可编辑安装
pip install -e .[dev]
```

### 快速开始

`scan` 是默认子命令，直接跟路径即可。

```bash
# 扫描单个文件
layoutproof scan test_fixtures/corpus/broken_all.pptx

# 干净文件退出码为 0
layoutproof scan test_fixtures/corpus/clean_basic.pptx

# 扫描目录（-r 递归）
layoutproof scan test_fixtures/corpus -r

# 输出 JSON（单文件为对象，多文件为数组）
layoutproof scan deck.pptx --json

# 仅以 error 作为门禁
layoutproof scan deck.pptx --fail-on error

# 开启全部 12 条规则
layoutproof scan deck.pptx --profile full
```

`fix`（安全自动修复并复跑）与 `demo`（生成示例坏文件与修复后文件）两个子命令均已在本构建中打通。修复绝不改动源文件：结果写入新文件（可另选备份），随后重新扫描确认问题减少。无法安全修复的问题（重叠、空白、媒体、引用、替代文本、结构）会列入 skipped 并标注需人工，不会伪造。

### JSON 输出与退出码

`scan` 输出符合 `src/layoutproof/report/schema.json`（`schema_version: "1.0"`）的 JSON。每条 issue 含 `rule_id`、`severity`、`slide_number`、`shape_name`、`detail`、`fixable`、`fix_id` 等字段。

| 退出码 | 含义 | 触发条件 |
|---:|---|---|
| `0` | 干净 | 没有达到 `--fail-on` 阈值的问题。 |
| `1` | 质量门禁未过 | 存在达到/超过阈值的问题（默认：任一 warning）。 |
| `2` | 用法/输入错误 | 参数错误、目标下无 `.pptx`，**或**文件不是合法的 zip/OOXML 包。 |
| `3` | 内部错误 | 意外异常，或本构建中未提供对应引擎的子命令。 |

默认 `--fail-on warning`：warning 即失败，info 不失败。`--fail-on error` 仅以确定性错误为门禁，`--fail-on info` 为最严门禁。

### 配置与 profile

用 `--config` 传入 TOML 或 JSON（也支持 `[tool.layoutproof]` 表）：

```toml
min_font_size_pt = 14.0
min_contrast_ratio = 4.5
large_text_pt = 18.0
large_text_contrast_ratio = 3.0
overlap_ratio_threshold = 0.30
offslide_fraction_threshold = 0.05
overflow_ratio_threshold = 0.15
max_file_size_mb = 100
fail_on = "warning"
```

`core` 默认启用 7 条高置信规则；`full` 额外开启 `object_overlap`、`low_contrast`、`blank_slide`、`missing_alt_text`、`cjk_typography`。配置中显式的 `enabled_rules` / `disabled_rules` 优先级高于 profile。完整规则目录见 [`docs/USAGE.md`](docs/USAGE.md)。

### GitHub Actions 用法

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install layoutproof
- run: layoutproof scan generated/ --recursive --profile full --fail-on error
```

仓库自带 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)，在 Ubuntu 与 Windows、Python 3.11–3.13 矩阵上安装并运行测试。

### 开发与测试

```bash
python -m venv .venv
pip install -e .[dev]
pytest
```

每条规则在 `tests/unit/` 下都有"阴（应触发）/阳（不应触发）"成对测试；生产发现的缺陷先补回归夹具再修复。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

### 已知限制

- 不做渲染：溢出/重叠基于几何与字体度量估算，高精度但近似。
- 仅支持 `.pptx`，不支持旧版二进制 `.ppt` 或 Keynote。
- 对比度可解析显式填充与母版主题背景（bg1/tx1）；其他主题色/渐变场景保守处理。

### 许可证

MIT，见 [LICENSE](LICENSE)。

### 最小人工发布步骤

本仓库暂无自动发布 CI，手动发版流程：

1. 升级 `pyproject.toml` 中的 `version`，并在 `CHANGELOG.md` 记录变更。
2. 在支持矩阵（3.11/3.12/3.13，Ubuntu + Windows）上跑通 `pytest`。
3. 构建：`python -m build`（需 `pip install build`）。
4. 校验：`twine check dist/*`。
5. 上传：`twine upload dist/*`（需 PyPI 维护者权限）。
6. 打标签：`git tag vX.Y.Z && git push origin vX.Y.Z`。
