# PPTX / Office 文档质量检查与自动修复 —— 开源竞品调研报告

> 服务于 LayoutProof 的产品定位：首版只聚焦 **AI 生成的 `.pptx` 自动化质量验收**，目标用户是用 Claude Code / Codex / Qoder 等 AI 编码工具生成 PPTX 的开发者；核心闭环为 **生成 → 检测 → 定位 → 自动修复 → 重新验证**，强调离线、稳定 JSON schema、明确退出码、低 Agent 集成成本。

- 调研完成日期：**2026-11-02**（信息检索窗口：2026-11）
- 调研方式：**静态调研**。所有结论来自公开 PyPI 页面、GitHub 仓库 README / 仓库元数据、官方文档站；本报告未在本机实际安装运行任一竞品（网络/时间约束下仅做证据级静态分析），凡涉及"运行结果"的说法均标注为 README 自述。
- 证据原则：每个项目均给出可访问 URL；找不到可信来源的项目明确写"未找到可信来源"，不编造能力与链接。

---

## 1. 调研方法与信息来源

1. 以五个指定项目名（archforge、overset、pptx-lint、docx-integrity、accessibleoffice）+ GitHub 仓库搜索（`github.com/search`）+ PyPI 项目页逐一核实真实仓库。
2. 沿"AI 生成 PPTX 质量门禁"主题扩检：`pptx-audit-and-fix`、rule-based pptx linter、OOXML 校验器、Microsoft Accessibility Checker 开源复刻等方向，补入 intern、pptlint、ooxml-integrity 等。
3. 对每个项目抓取其 README / PyPI 长描述，提取：一句话定位、能力清单（具体规则）、最近发布/提交时间、Star/Fork 量级、许可证、技术栈、自述局限性。
4. 交叉比对"已被完整解决的能力"与"空白/痛点"，落到 LayoutProof 的差异化与首版设计建议。

主要来源类型：
- PyPI 项目页（含 Release history、Provenance、License、Requires-Python）
- GitHub 仓库主页（README、About、Star/Fork、Commits、Topics）
- 项目官方文档站（如 markusz.github.io/intern、love-ash.github.io/archforge）
- Microsoft 官方 Accessibility Checker 规则文档（用于对照 accessibleoffice）

---

## 2. 逐项目深度卡片

### 2.1 archforge  ⭐ 最直接、最成熟的对标竞品

- **真实仓库 URL**：https://github.com/Love-Ash/archforge （PyPI：https://pypi.org/project/archforge/ ）
- **一句话定位**：面向 AI 生成 PPTX 的"发布前预检 linter"，在人工看到渲染之前，纯读 `.pptx`（XML / 字体解析链 / 几何 / 图片 alpha）找出静默缺陷。
- **维护状态**：活跃。最新版 **0.11.0（2026-09-01）**，2026-07 至 09 密集发版（0.1.0→0.11.0 共 20+ 个 release），作者 Minjae Kwon (Ash)，单维护者，有 GitHub Discussions / good first issue / pre-commit / GitHub Action。
- **许可证**：MIT（© Minjae Kwon）
- **技术栈**：Python ≥3.9；纯离线、不依赖 PowerPoint；输出 CLI / `--json` / `--sarif` / `--junit` / `--html` 标注报告；自带 `archforge skill --install`（Agent Skills 包，教 Claude Code / Codex 走 build-lint-fix 循环）。
- **能力清单（具体到规则码）**：
  - `E1` 渲染时实际用于韩文的字体是 Latin-only → 静默 Malgun 字体回退（**CJK 深度，Hangul 优先**；按实测 PowerPoint COM 解析链 `a:ea > defRPr > lstStyle > theme ea > a:latin > OS fallback` 建模）。
  - `E2` 用破折号族字符当句读标点（AI 生成 deck 的头号"马脚"）；数字区间/减号默认放行，`--strict` 全拦。
  - `E3` autofit + 占位符继承链后有效字号 < 5pt，不可读。
  - `E4` 连续韩文/汉字上的正 letter-spacing（字距损伤；含假名 run 豁免）。
  - WARN：`W1` 正文框 <9pt、`W5` 继承链无字号、`W6` 4+ 页同布局骨架、`W7` 文字压图片对比度（需 `--render`）、`W8` 窄框小 CJK、`W9` 竖条当列表符、`W11` AI 套话、`W13` 原生阴影/发光/3D、`W18` 输入残缺导致结果不完整、`W19/W20` 文字与自身填充/下层图形对比度不足。
  - **自动修复**：0.8.1 起 `archforge fix deck.pptx -o fixed.pptx`，自动修 `E1/E2/E4`。
  - Profile 分档：`core`（默认，机械门禁）/ `full`（+AI-tell、风格规则，机器生成 deck 用这个）/ `editorial`。
  - 退出码 / 门禁：`--fail-incomplete`，`summary.pass` 作为诚实 gate；SARIF 接 CodeQL。
- **局限性 / 证据摘录**：
  - "Font-fallback and letter-tracking detection (E1/E4) is CJK-specific by design — deepest for **Hangul** — and does not fire on Latin-only decks."（中文排版不是其深度方向）
  - "the target renderer is **PowerPoint for Windows**."（跨渲染器一致性未覆盖）
  - 自己承认："A passing lint is not a finished deck… composition and narrative still need eyes on renders."（只做机械缺陷，不做审美/内容）
  - 0.8.1 才有自动修复，且只覆盖 E1/E2/E4 三类；修复后是否自动复跑验证未在 README 体现闭环。
- **证据 URL**：https://pypi.org/project/archforge/

---

### 2.2 overset

- **真实仓库 URL**：https://github.com/rogermsc/overset
- **一句话定位**：**Baseline-free（无需截图基线）的生成 deck 布局校验**——专门抓"渲染器把内容静默丢掉"这类没有任何报错的问题。
- **维护状态**：极新、极小。**1 个 commit**，0 star / 0 fork，GitHub 搜索显示最近更新 8 月（2026-08-03）；Topics 含 `generative-ai` `llm` `powerpoint` `pptx` `validation`。PyPI 尚未发布（`pip install git+https://…`，"PyPI release pending"）。
- **许可证**：MIT
- **技术栈**：Python；分层依赖——Capacity 层零依赖；`.pptx` 层 `pip install "overset[pptx]"` 用 EMU 精确坐标 + **LibreOffice 渲染**读真实字形位置（无 LibreOffice 则"响亮地跳过"而非估算）；HTML 层用 headless 浏览器几何。
- **能力清单**：
  - **容量层**：`Layout(items="cards", min_items=4, max_items=4)` 声明布局槽位；超过 max_items → 渲染时静默丢内容（major）；低于 min_items → 页面留空洞（几乎没人查的反向缺陷）。
  - **pptx 层**：形状越界是算术问题（EMU，无估算）；文字是否装得下不猜，交给 LibreOffice 渲染后读真实 glyph 位置。
  - **HTML 层**：off-canvas、被自身 box 裁切、越过预留带、text-on-text 碰撞。
  - 输出：`--json`、`--report`（独立 HTML，在 slide 轮廓上画每处问题）；**有 major 即退出码 1**，直接进 CI。
  - 两条设计铁律："measured-and-wrong fails closed；cannot-measure fails open"（测不准就警告放行，不因为缺依赖堵死流水线）；"A check that didn't run says so"（没跑的检查必须声明，安静跑完≠干净）。
- **局限性 / 证据摘录**：
  - 明确**不做自动修复**："It doesn't auto-fix. Silently rewriting a deck to make it fit is how you lose a user's content — the failure mode this exists to expose."
  - 不做设计好坏判断、不做基线 diff、不生成 deck。
  - pptx 渲染测的是 **LibreOffice** 渲染，"PowerPoint's own engine can differ for unusual type sizes"；自述 212 张人工认可 deck 上误报 1.9%（某模板超大装饰数字）。
  - 成熟度极低（1 commit），生产可用性未验证。
- **证据 URL**：https://github.com/rogermsc/overset

---

### 2.3 pptx-lint

- **真实仓库 URL**：https://github.com/LeppardWang/pptx-lint （PyPI：https://pypi.org/project/pptx-lint/ ）
- **一句话定位**：python-pptx 生成 deck 的轻量 lint / 质量检查器。
- **维护状态**：最小化、近似停滞。**0.2.0（2026-06-27）**，仅 0.1.0 / 0.2.0 两个 release，整包 wheel 仅 12.1 kB，单维护者（PyPI 用户 Lai5），无 provenance。
- **许可证**：MIT
- **技术栈**：Python ≥3.9；CLI（单文件/目录）+ 库 API（`from pptx_lint.checker import check_pptx`）；纯文本表格报告。
- **能力清单**：
  - `Overflow`（Error）：形状 left/top<0 或 right/bottom>slide 尺寸。
  - `Empty slide`（Error）：零形状的页。
  - `Overlap`（Warning）：两形状重叠 > 较小形状面积 50%。
  - `Fake table`（Warning）：≥4 个文本框排成 ≥2×2 网格（本该用 `add_table()`）。
  - `Small font`（Info）：< 8pt。
- **局限性 / 证据摘录**：
  - 无稳定 JSON schema、无明确退出码约定、无 SARIF、无 CI/Agent 集成说明、**无自动修复**。
  - 溢出/重叠基于硬编码坐标，不做字体度量、不做渲染、不做 CJK 感知；"Fake table" 规则对 AI 生成 deck 意义有限。
  - 自述面向"用 python-pptx 的人"踩过的坑，是入门级而非生产级门禁。
- **证据 URL**：https://pypi.org/project/pptx-lint/

---

### 2.4 docx-integrity

- **精确同名仓库检索结论**：以 `docx-integrity` 在 GitHub 仓库搜索，**未找到**名为 `docx-integrity`、定位为"docx/pptx 质量与修复"的开源项目；搜索结果多为无关的学术诚信/取证类仓库。
- **最接近的真实项目（按能力匹配）：ooxml-integrity**
  - **真实仓库 URL**：https://github.com/Dmitry-Kov/ooxml-integrity （PyPI：https://pypi.org/project/ooxml-integrity/ ）
  - **一句话定位**：对**自动编辑后的 `.docx` / `.pptx`** 做完整性检查——找断链的批注锚点、丢失的修订、孤儿脚注、以及 deck 里文字可能溢出框的问题。
  - **维护状态**：活跃。**0.8.1（2026-10-12）**，带 PyPI provenance（GitHub Actions 签名），发版频繁。
  - **许可证**：MIT；技术栈 Python（3.9–3.14），纯本地、不渲染、不调模型、不联网；输出 `--json` / SARIF / GitHub Action。
  - **能力清单（规则码极细）**：
    - docx：`PKG001-010` OPC 包完整性/Content-Types/unsafe part name；`XML001` XML 良构；`REL001-003` r:id/r:embed/r:link 解析；`STY001/002` 未定义样式；`NUM001-004` 编号链；`FTN001-002` 脚注；`CMT001-006` 批注锚点一致性；`REV001-003` 修订 ID 冲突；`TBL001-002` tblGrid/单元格；`FID001-014` **编辑后相对原始稿的"丢失/新增"对账**（构造计数、文字量、批注/脚注/页眉页脚丢失）。
    - pptx：文字 likely overflow its box（读本地字体文件估算）。
  - **自动修复（明确只做 3 类、且结果唯一的修复）**：`anchor-replies`（CMT005，回复继承父批注范围）、`renumber-revisions`（REV001 重复修订 ID 换新）、`content-type`（PKG010，修正 Override）；修完**重新检查再写盘**，输入文件永不改动，退出码区分 0/1/2/3。
  - 退出码：0=无 ≥fail-on 发现；1=有；2=用法错误；3=fix 后复检失败。
- **局限性 / 证据摘录**：
  - 重心在 **docx 完整性与"编辑前后对账"**，pptx 侧只做了文字溢出估算，不做布局/排版/字体回退。
  - 绝大多数发现"无法从文件修复"（丢了的批注/样式/修订只能猜），只修 3 类唯一解。
  - 对 LayoutProof 的启示：它把"诚实报告覆盖范围（`INT001` 检查未完成也算 error）"和"修前修后复检"做成了一等公民，这点值得借鉴。
- **证据 URL**：https://pypi.org/project/ooxml-integrity/

---

### 2.5 accessibleoffice

- **真实仓库 URL**：https://github.com/ildunari/accessibleoffice
- **一句话定位**：在 `.docx` / `.pptx` 上**检测并修复** Microsoft Office 可访问性问题，直接在 OOXML 上复刻微软官方 Accessibility Checker 规则目录（因为微软不开放应用内检查器 API）。
- **维护状态**：雏形但工程化程度高。**60 commits**，0 star / 0 fork，最近更新 6 月（2026-06-10）；含 Tauri 2 桌面 GUI（.dmg/.exe/.AppImage）+ CLI。
- **许可证**：仓库 README 未在抓取片段中明示 SPDX（About 区未显示 license 徽章）；**许可证待核实**（见"未决项"）。
- **技术栈**：Python（包名 `a11yfix`，uv 管理，pytest/ruff/black/mypy）+ Tauri 桌面端；修复通过 `officecli` 写盘；AI 后端可插拔（Claude Code OAuth / Anthropic SDK / OpenAI / OpenRouter / pi / opencode / codex）。
- **能力清单（4 阶段流水线）**：
  - Stage 1 检测：规则引擎跑 OOXML，规则带 WCAG 映射（`docs/rule-catalog.md`）。
  - Stage 2 确定性自动修复：文档标题、表格表头行、文档语言（`--default-lang`）。
  - Stage 3 单次 AI 修复：生成 alt text、链接文字、幻灯片标题。
  - Stage 4 Agentic 复审：把 Stage 1–3 的 **manifest JSON** 喂给 Claude Code / Codex 处理剩余判断题（对比度、阅读顺序永不自动改，留给人）。
  - 模式：`--mode scan`（只读，CI/审计）/ `auto`（默认，确定性、不联网、不烧 token）/ `full`（全流水线 + 交互式 Claude Code）/ `--dry-run`。
  - 诚实性：每个发现按"AI 可修 / 确定性可修 / 需人工"分类；没修任何东西就字节级不动文件；缺后端不报错，降级为 partial。
- **局限性 / 证据摘录**：
  - 领域是**可访问性**（alt text、标题层级、对比度、阅读顺序），不是布局溢出/重叠/字体回退。
  - `full` 模式强依赖外部 Agent CLI（Claude Code / Codex）在 PATH，重依赖；离线纯确定性只覆盖少数机械项。
  - 0 star、单人项目，规则覆盖度与误报率未公开校准数据。
- **证据 URL**：https://github.com/ildunari/accessibleoffice

---

### 2.6 intern（额外竞品，Rust 实现，带自动修复）

- **真实仓库 URL**：https://github.com/markusz/intern （文档站：https://markusz.github.io/intern/ ）
- **一句话定位**：开源、规则化、CI 友好的 PowerPoint linter，"因为你的实习生有更重要的事去对齐文本框"。
- **维护状态**：雏形但完成度高。**60 commits，2 star / 0 fork**；MIT；Rust（`intern-core` 引擎库 + `intern` CLI），提供 Homebrew / 预编译二进制（含 Windows）/ `cargo install`。
- **能力清单（29 条规则，4 类）**：
  - 对齐：`LEFT/RIGHT/BOTTOM_MARGIN`、`TITLE_MARGIN`、`CLOSE_X/CLOSE_Y`、`TITLE_Y`、`TITLE_X_WIDTH`、`TEXT_ELEMENT_OVERLAP`、`ELEMENT_OVERFLOW`。
  - 排版：`TITLE_FONT_SIZE`、`FONT_SIZE_VARIETY`、`BODY_FONT_FAMILY`、`FONT_VARIETY`、`COLOR_VARIETY`。
  - 文字质量：`DOUBLE_SPACE`、`LEADING_SPACE`、`REPEATED_WORD`、`BULLET_CAPITALIZATION/PUNCTUATION/LENGTH`、`ALL_CAPS`。
  - 结构：`TITLE_LENGTH`、`TITLE_TRAILING_PUNCT`、`DUPLICATE_TITLE`、`EMPTY_TEXTBOX`、`TITLE_PRESENT`、`SLIDE_COUNT`。
  - **自动修复**：`intern fix deck.pptx` 原地修对齐、字号、空白；`intern ignore` 把抑制指令写进演讲者备注并备份 `.bak`。
  - 工程化：`--output json`、**退出码 0=干净/仅 warning，1=有 error**、`.intern.toml` 配置、阈值 `--threshold <px>`、可 `--rules/--disable`。
- **局限性 / 证据摘录**：
  - 规则偏"风格一致性/排版洁癖"（边距、字体种类数、bullet 长度、标题尾标点），**不做字体回退、不做 CJK、不做渲染级文字溢出**（基于 EMU 几何）。
  - 2 star、生态未起；自动修复只覆盖对齐/字号/空白三类。
- **证据 URL**：https://github.com/markusz/intern

---

### 2.7 pptx-audit-and-fix（额外竞品，Claude Skill 形态）

- **真实仓库 URL**：https://github.com/tivojn/pptx-audit-and-fix
- **一句话定位**：独立 Python 工具，对 `.pptx` 布局问题做 5 阶段审计 + 自动修复，无需 PowerPoint。
- **维护状态**：极早期。**2 commits，0 star / 0 fork**，最近更新 3 月（2026-03-13）；仓库本身是一个 **Claude Code Skill**（含 `SKILL.md` + `references/pptx_audit.py`）。
- **许可证**：MIT；技术栈 python-pptx + Pillow + lxml。
- **能力清单（5 阶段）**：
  1. 结构扫描：形状互叠、越界、装饰线穿过文字。
  2. 文字真相：用字体度量估算真实渲染文字高度，抓文字溢出框。
  3. 视觉可读性：<14pt 字号、低对比文字（WCAG 亮度）、深底红字警告。
  4. 布局一致性：贴边 <36pt 边距、垂直间距不均、空占位符。
  5. 构图覆盖：overlay 形状挡住全幅背景图（单形状 >30% WARNING，合计 >50% CRITICAL）。
  - **自动修复**：文字框 resize 适配内容（溢出 >8pt）、resize 后**迭代垂直重排**防级联重叠、字号提到最小 14pt、删空占位符。
- **局限性 / 证据摘录（自述）**：
  - "Text height: Estimated via font metrics (**~90% accurate**) vs exact from PowerPoint renderer."
  - "No screenshot/AI review — structural analysis only."
  - 构图覆盖只测面积比，判断不了背景图焦点是否被挡。
  - 以 Skill 路径 `~/.claude/skills/...` 组织，分发形态是 Claude 技能而非独立 CLI 包。
- **证据 URL**：https://github.com/tivojn/pptx-audit-and-fix

---

### 2.8 其他扫到但未深做卡片的相关项目

- **pptlint**（https://pypi.org/project/pptlint/ ，仓库 `github.com/kdnsna/pptlint`，由旧名 `decklint` 迁移，MIT）：PyPI 页本次抓取被反爬拦截，仅从搜索摘要确认其存在与 MIT、命令名 `pptlint`（旧 `decklint` 作兼容别名）；**能力细节未取到，按"未充分证实"处理**。
- **@xarsh/ooxml-validator**（npm，MIT，v0.4.0）：OOXML schema 校验器，偏包/XML 良构，不做布局。
- **community-access**（https://community-access.github.io/ ）：一组 Word/Excel/PowerPoint 可访问性扫描 Agent，同样基于微软公开规则映射 WCAG 2.1 AA；与 accessibleoffice 同赛道，未取到独立仓库 URL。
- **Microsoft Accessibility Checker（官方、闭源、桌面内建）**：规则目录见 https://support.microsoft.com/en-us/office/rules-for-the-accessibility-checker-651e08f2-0fc3-4e10-aaca-74b4a67101c1 —— accessibleoffice / community-access 都是它的开源复刻对照物。

---

## 3. 目标用户画像

**核心用户**：用 AI 编码工具（Claude Code、Codex、Qoder、Cursor 等）程序化生成 `.pptx` 的开发者 / 技术创作者。

典型工作流与痛点：
1. 用 python-pptx / PptxGenJS / OfficeCLI / 模板脚本让 Agent 生成一份 deck。
2. "build succeeded" 不等于"渲染正确"——缺陷藏在字体槽、autofit 缩放、坐标里，**代码评审看不见**（archforge 原话："Code review cannot see any of it, because the defects live in font slots, autofit scales, and coordinates that only materialize at render time."）。
3. 他们要的不是"设计审美建议"，而是：**一条命令、退出码 0/1、稳定 JSON、能被 Agent 消费并据此改代码、最好还能自动改一版再复跑**。
4. 强约束：**离线、不装 PowerPoint、不烧 token、CI 可跑、结果可复现**。

次级用户：把 PPTX 生成接入 CI/发布流水线的团队（需要 SARIF、baseline、抑制机制）；需要可访问性合规的政府/教育类 deck 作者（accessibleoffice 赛道）。

---

## 4. 竞品能力对比矩阵

图例：✅ 明确支持且有证据；🟡 部分/估算/需额外依赖；❌ 未做；— 不适用。

| 检测 / 修复维度 | archforge | overset | pptx-lint | ooxml-integrity | accessibleoffice | intern | pptx-audit-and-fix |
|---|---|---|---|---|---|---|---|
| 纯离线、不装 PowerPoint | ✅ | ✅（pptx 文字层需 LibreOffice） | ✅ | ✅ | ✅（auto 模式） | ✅ | ✅ |
| 形状越界 / off-slide | 🟡（几何近似） | ✅（EMU 精确算术） | ✅ | — | — | ✅ ELEMENT_OVERFLOW | ✅ |
| 形状互叠检测 | 🟡 colliding frames | 🟡 text-on-text（HTML 层） | ✅ >50% 面积 | — | — | ✅ TEXT_ELEMENT_OVERLAP | ✅ |
| 文字溢出框（渲染级） | 🟡（autofit 链推算） | ✅（LibreOffice 实测 glyph） | ❌ | 🟡 字体度量估算 | — | ❌（几何） | 🟡（字体度量 ~90%） |
| 过小字号 / 不可读 | ✅ E3/W1/W8 | 🟡 空占位符 | ✅ <8pt | — | — | ✅ FONT_SIZE 类 | ✅ <14pt |
| 空页 / 空占位符 | 🟡 | ✅ minor | ✅ Empty slide | — | — | ✅ EMPTY_TEXTBOX | ✅ 删除 |
| 字体回退 / 缺字形（CJK） | ✅ **E1，Hangul 深度** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 字距 / 标点 AI 马脚 | ✅ E2/E4/W11 | ❌ | ❌ | 🟡 TXT002 双转义 | ❌ | 🟡 尾标点/双空格 | ❌ |
| 对比度 / 可读性 | 🟡 W7/W19/W20 | ❌ | ❌ | — | ✅（人工判） | 🟡 COLOR_VARIETY | ✅ WCAG 亮度 |
| 可访问性（alt/标题层级/WCAG） | ❌ | ❌ | ❌ | ❌ | ✅ **核心** | ❌ | ❌ |
| OOXML 包完整性 / 断链 / 修订丢失 | ❌ | ❌ | ❌ | ✅ **核心，规则极细** | 🟡 | ❌ | ❌ |
| 编辑前后内容丢失对账 | ❌ | ❌ | ❌ | ✅ FID 系列 | ❌ | ❌ | ❌ |
| 布局容量 / 静默丢内容 | ❌ | ✅ **核心（min/max slots）** | ❌ | ❌ | — | ❌ | 🟡 构图覆盖 |
| 稳定 JSON 输出 | ✅ schema 2.0 | ✅ | 🟡（仅文本表/库） | ✅ | ✅ manifest schema | ✅ `--output json` | 🟡（print report） |
| 明确退出码 / CI 门禁 | ✅ fail-incomplete | ✅ major→1 | ❌ | ✅ 0/1/2 | 🟡 partial 概念 | ✅ 0/1 | ❌ |
| SARIF / GitHub Action / pre-commit | ✅ 全套 | 🟡（退出码可接） | ❌ | ✅ Action+SARIF | 🟡 scan 模式 | ✅（二进制/brew） | ❌ |
| 自动修复 | 🟡 E1/E2/E4 | ❌（明确拒绝） | ❌ | 🟡 仅 3 类唯一解 | 🟡 确定性 3 项 + AI | ✅ 对齐/字号/空白 | ✅ resize/重排/提字号 |
| 修复后自动复跑验证 | ❓ 未见闭环 | — | — | ✅（fix 后复检再写） | 🟡 manifest→stage4 | ❓ | 🟡 fix_all 后 save |
| Agent 集成（SKILL.md / build-lint-fix） | ✅ `skill --install` | ❌ | ❌ | 🟡 Action | ✅ Claude Code/Codex | ❌ | ✅（本身就是 Skill） |
| 目标渲染器覆盖 | PowerPoint Win 单点 | LibreOffice 单点 | 无渲染 | 无渲染 | 无渲染 | 无渲染 | 无渲染（估算） |
| 中文排版深度 | 🟡 CJK 感知但偏韩文 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 维护成熟度 | **高**（v0.11，活跃） | 极低（1 commit） | 低（停在 0.2） | **高**（v0.8.1） | 雏形（60 commit，0 star） | 雏形（2 star） | 雏形（2 commit） |

---

## 5. 差异化结论

### 5.1 已被竞品完整解决 —— LayoutProof 首版不要重复造轮子

这些能力在 archforge / intern / ooxml-integrity 上已经做得相当到位，LayoutProof 做"同一套"只会变成第 N 个 0-star 玩具：

1. **几何级越界 / 重叠 / 空页检测**：intern（ELEMENT_OVERFLOW、TEXT_ELEMENT_OVERLAP）、overset（EMU 精确算术）、pptx-lint 都已覆盖；EMU 坐标判断越界是小学算术，没有技术壁垒。
2. **过小字号、边距、对齐一致性**：intern 29 条规则、archforge E3/W1/W8 已成体系。
3. **稳定 JSON + 明确退出码 + CI 门禁**：archforge（schema 2.0、fail-incomplete、SARIF、pre-commit、GitHub Action）是标杆，已把"Agent 友好"这件事做到位。
4. **OOXML 包完整性 / 断链 / 修订丢失对账**：ooxml-integrity 规则码细到 PKG010、FID014，且做了"修前修后复检"——这块 LayoutProof 不必重做（若需要可在文档里指向它）。
5. **可访问性规则**：accessibleoffice 已直接复刻微软规则目录 + WCAG 映射，不是 LayoutProof 的战场。
6. **Agent build-lint-fix 循环范式**：archforge 已自带 `skill --install` 并写了 Claude Code / Codex 配方；pptx-audit-and-fix 本身就是一个 Claude Skill。说明"Agent 集成"这个点**不再是差异化，而是入场券**。

### 5.2 空白 / 痛点 —— LayoutProof 可以立足的地方

1. **中文排版（CJK 简体）深度检测 = 明确空白。**
   archforge 的字体回退/字距规则是"Hangul-deep"，并自述"does not fire on Latin-only decks"；intern / pptx-audit / pptx-lint 完全不做 CJK。简体中文场景的痛点——**标点悬挂/避头尾（kinsoku）、中西文混排间距、中文字体（思源/微软雅黑/苹方）缺失回退、破折号/省略号占位、全半角混排**——没有任何竞品覆盖。这是最硬的差异化楔子。
2. **误报率 / 校准是普遍痛点，也是信任来源。**
   archforge 专门写了"在 29 份真实 deck 上测量、 deliberately 不在 5–9pt 区间设卡（否则用几百个误报换不到一次真捕获）"；pptx-audit 自认字体度量"~90% accurate"；overset 自认 LibreOffice 渲染误报 1.9%。**谁能把"默认配置低误报、可解释、可按报告反馈沉淀 fixture"做好，谁就能在 Agent 场景赢信任**——因为 Agent 一旦被误报轰炸就会关掉这个 gate。
3. **真正的"检测→修复→复跑"闭环仍然残缺。**
   archforge 只自动修 3 类、未见复跑；overset 明确拒绝自动修；intern 修对齐/字号但不复跑；ooxml-integrity 是唯一做了"修后复检再写盘"的，但它只修 3 类 docx 问题。**一个安全、可解释、修完自动复检并给出"改了哪些字节/为什么"的闭环，在 pptx 布局领域尚属空白。**
4. **跨渲染器一致性没人真正解决。**
   archforge 目标锁定 PowerPoint Windows；overset 锁定 LibreOffice；ppt-audit 用字体度量估算；没有任何工具给出"同一份 deck 在 PowerPoint / WPS / LibreOffice / Google Slides / Keynote 渲染是否一致"的矩阵。AI 生成 deck 的真实消费端常常不是 PowerPoint，这是真实痛点（可做轻量版：声明目标渲染器 + 只报该渲染器下高置信问题）。
5. **首分钟价值（几分钟内一条命令见效）尚未被普遍打透。**
   archforge 的 `archforge demo`（当场 build 一个坏 deck + 一个修好的并各自 lint）是全场最佳的"啊哈"时刻；其余竞品 README 仍停留在"install → lint your own deck"，新用户要自己有一个坏 deck 才看得到价值。

---

## 6. "首次使用价值"设计建议（几分钟内一条命令见效）

对标 archforge `demo` 但要做得更傻瓜，让新用户（或新会话里的 Agent）在 60 秒内看到 LayoutProof 干活：

1. **内置 `layoutproof demo`**：当场生成一份**故意埋雷的 `broken.pptx`**（中文混排 + 一个缺字形回退 + 一个文字溢出 + 一个重叠），跑检测打印高亮问题，再跑 `layoutproof fix` 输出 `fixed.pptx`，**两文件并排对比报告**。用户不需要先有自己的 deck。
2. **一条命令、零配置、离线**：`pipx install layoutproof` 后 `layoutproof demo` 即成功；不要求 PowerPoint、不要求 LibreOffice、不联网、不要 API key。
3. **输出立刻可被人看懂**：终端高亮表（页码 / 规则码 / 一句话 / 建议修复动作）+ `--json` 给 Agent；首个问题必须是"看得见的真问题"，不要拿风格类 WARN 充数。
4. **退出码讲故事**：有 error 退出 1、干净退出 0、用法错退出 2——Agent 一眼知道要不要进入修复分支。
5. **修复后自动复跑**：`layoutproof fix` 写盘前/后各跑一遍，报告里写"本次修复了 N 处、复跑后剩余 M 处、其中 K 处需人工"，把 5.2.3 的闭环做成默认行为，而不是参数。
6. **首版规则聚焦 5–8 条高置信、低误报、AI 高频犯的中文/布局缺陷**，宁可少而准（参考 archforge "deliberately 不设卡的区间"哲学），把误报压下去；风格类规则全部默认关、做成 profile。

---

## 7. 未决项 / 证据缺口（诚实声明）

- **accessibleoffice 的许可证**：抓取的 README 片段与 About 区未显示 SPDX 许可证徽章，需后续到仓库根 `LICENSE` 文件核实（本报告不臆断）。
- **pptlint（kdnsna/pptlint）**：PyPI 页本次被反爬拦截，仅确认存在与 MIT、命令名；能力清单未取证，未进入对比矩阵计分。
- **本报告为静态调研**：未在本机 `pip install` 任一竞品实测其真实输出/误报率/安装体积；上述"维护状态"基于 PyPI release history 与 GitHub 仓库元数据，Star 数为抓取时点快照。
- **`docx-integrity` 精确同名项目未找到**：以能力最接近的 `ooxml-integrity` 代之并明确标注，未编造一个不存在的仓库。

---

## 7B. 实测再分析（真实安装运行，非静态）

> 本节为第二轮增量：在**隔离虚拟环境**中真实安装并运行可合法安装的竞品，对**同一份含已知缺陷的测试 deck**做横向实测，以替代 README 自述。所有数字均来自本机真实运行（2026-11-02）。

### 7B.1 实测方法

- 隔离环境：项目内独立 venv（`competitor_lab/venv`，已 gitignore，不污染项目主环境），pip 走华为云镜像。
- 真实安装版本：**pptx-lint 0.2.0**、**archforge 0.11.0**、**ooxml-integrity 0.8.4**（比静态报告的 0.8.1 更新；新增 `mcp`/`anonymize` 子命令）。
- 共同测试 deck `common_defects.pptx`（python-pptx 默认 10″×7.5″ 画幅），三张幻灯片：
  - 第 1 页：干净页；
  - 第 2 页：一个**完全越界**文本框（left=14″）+ 一个 **run 级 7pt 小字**；
  - 第 3 页：**完全空白**。
- 另用 `para_font.pptx`（孤立文本框，**段落级 7pt**）做对照，区分"段落级"与"run 级"字号检测。

### 7B.2 同一 deck 实测结果对照

| 缺陷 | pptx-lint 0.2.0 | archforge 0.11.0 | ooxml-integrity 0.8.4 |
|---|---|---|---|
| 完全越界形状 | Overflow，**error** | W16，**warning**（estimate，未渲染确认） | PPT004，**info** |
| run 级 7pt 小字 | 未检出 | 未检出 | 未检出 |
| 空白页 | EmptySlide，**error** | 未检出（无空白页规则） | 未检出 |
| 4:3 画幅 | 仅打印"非标准"提示，**不计入** warning | — | — |
| 实测退出码 | **1** | **0** | **0** |

段落级 7pt 对照（`para_font.pptx`）：仅 **pptx-lint 报 SmallFont（info）**；archforge 与 ooxml-integrity 均 0 发现。

### 7B.3 证据级关键发现

1. **同一缺陷，三种严重度。** 越界形状在 pptx-lint 是 error、archforge 是 warning、ooxml-integrity 是 info；默认配置下只有 pptx-lint 因此返回退出码 1。用户对"同一问题有多严重"在不同工具间得不到一致答案。
2. **run 级小字是三家共同盲区。** 源码核对：pptx-lint 的字号取自段落级 `paragraph.font.size`，run 级或继承字号返回 None 即静默跳过（`rules/font_size.py` 第 11 行 `if fi['size'] is not None`）；而 AI 生成 deck 常把字号设在 run 上。段落级 7pt 仅 pptx-lint 可报。
3. **archforge 对孤立文本框刻意不判"正文小字"。** `explain W1` 注明"Ignore for sources/captions"——单文本框被当作标题/说明而非正文，故 W1 不触发，是其压低误报的有意取舍。
4. **空白页只有 pptx-lint 覆盖；** archforge 的规则集（E1–E4、W1、W5–W22）不含空白页规则。
5. **ooxml-integrity 的覆盖披露最透明。** 它逐项标注 checked/not-present/skipped/unsupported 及原因（如"3 个 spAutoFit 形状不参与溢出判断""完整 PPTX OPC 图未校验，仅跟随布局所需关系"），不把"没检查"伪装成"干净"。
6. **修复范围实测确认。** archforge `fix` 仅处理 E1/E2/E4 且重新 lint，对本 deck 的越界 warning 显示"0 fixes applied"；ooxml-integrity 的 `fix` 仅支持 docx；pptx-lint 无修复。三者在 pptx 布局缺陷上均无"越界即修"的能力。

### 7B.4 对 LayoutProof 的证据支撑

- 实测佐证了静态报告的差异化判断：**run 级/继承字号检测、空白页检测、以及"越界→安全回位→复检"的闭环**在现有工具中确实缺失或分级不一致，LayoutProof 补齐这些点有真实对照证据，而非凭空主张。
- 值得借鉴：ooxml-integrity 的"coverage 显式披露"与 archforge 的"按文本角色控制误报"，两者都把诚实性和低误报作为一等公民——LayoutProof 已在报告中用静态/渲染徽章与未知项标注对齐这一做法。
- 边界：本次仅实测 3 个 pip 可装工具；overset/intern 等需源码或编译、accessibleoffice 重依赖，未在本轮实测，相关结论仍以静态部分为准。

---

## 8. 参考链接列表

- archforge（GitHub）：https://github.com/Love-Ash/archforge
- archforge（PyPI，含完整规则表/发布历史/Provenance）：https://pypi.org/project/archforge/
- archforge 在线试玩：https://love-ash.github.io/archforge
- overset（GitHub）：https://github.com/rogermsc/overset
- pptx-lint（GitHub）：https://github.com/LeppardWang/pptx-lint
- pptx-lint（PyPI）：https://pypi.org/project/pptx-lint/
- ooxml-integrity（GitHub，即 docx-integrity 最接近替代）：https://github.com/Dmitry-Kov/ooxml-integrity
- ooxml-integrity（PyPI）：https://pypi.org/project/ooxml-integrity/
- accessibleoffice（GitHub）：https://github.com/ildunari/accessibleoffice
- intern（GitHub）：https://github.com/markusz/intern
- intern 文档站：https://markusz.github.io/intern/
- pptx-audit-and-fix（GitHub）：https://github.com/tivojn/pptx-audit-and-fix
- pptlint（PyPI，未充分取证）：https://pypi.org/project/pptlint/
- @xarsh/ooxml-validator（npm）：https://www.npmjs.com/package/@xarsh/ooxml-validator
- community-access（可访问性 Agent 集合）：https://community-access.github.io/
- Microsoft Accessibility Checker 规则目录（官方）：https://support.microsoft.com/en-us/office/rules-for-the-accessibility-checker-651e08f2-0fc3-4e10-aaca-74b4a67101c1
- Microsoft Accessibility Checker 使用说明：https://support.microsoft.com/en-us/office/improve-accessibility-with-the-accessibility-checker-a16f6de0-2f39-4a2b-8bd8-5ad801426c7f

---

*报告完。所有事实均附上述 URL；凡标注"未找到可信来源 / 未充分取证 / 自述"处，请勿当作已独立验证的结论使用。*
