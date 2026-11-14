# submit-check：开发与打磨日志

## 开发（2026-11-13）

- 仓库骨架：Python + uv，依赖 paper-proof v0.1.0（git 依赖，复用它的 LaTeX 工程读取：\input、注释、\iffalse）、pypdf、tomli（3.10）。
- 模板与模式识别：NeurIPS（[final]/[preprint]）、ICML（[accepted]）、ICLR（\iclrfinalcopy）、CVPR/ICCV/WACV（[review]）、ACL（[review]）、ECCV（[review]）、AAAI（[submission]）。
- 匿名泄露：模板处于会打印作者的模式；不认识的模板时 \author 里有真名；致谢一节（NeurIPS 的 ack 环境模板会自动隐藏，不报）；正文里的邮箱；\thanks；
  指向作者自己代码/主页的链接；第一人称自引；资助信息。
- 残留标记：\todo / \fixme、TODO / FIXME / XXX、[citation needed]、红色文字（\todo 被定义成空命令时不报）。
- 在 50 篇已发表论文源码上看匹配质量（这些是终稿，命中的东西放在投稿版里确实会泄露）：
  - \hl 在 ResNet 的表、CoT 的提示里是有意的高亮，不是编辑标记 → 不再算。
  - “In our work / In our paper”指的是本文 → 只有带 previous/prior/earlier，或后面紧跟引用时才算自引。
  - 指向 pytorch、tensorflow、openai 的链接是引用别人的代码 → 只有句子里说“our code / we release / is available at”时才算泄露。
  - \author 里的邮箱交给作者块那条去报，不再重复。
  - 测试时抓到一个窗口起点为 -1 导致切片为空的 bug（链接前没有句号时“自己代码”的上下文永远为空），已修。
- 8 个测试。
- **会议规则库**（src/submit_check/rules/*.toml）：逐个读了官方投稿说明再写，每个值旁边引原句，记来源网址和核实日期（2026-11-13）：
  NeurIPS 2025（正文 9 页、终稿 10 页，参考文献/checklist/附录不计，必须有 checklist）、ICML 2025（8 页、终稿 9 页，必须有 Impact Statement）、
  ICLR 2026（9 页、终稿 10 页，Reproducibility Statement 强烈建议）、ACL ARR（长文 8 页，必须有 Limitations 一节，否则直接拒稿）、
  CVPR 2026（8 页，不含参考文献；官方页没写终稿页数，就不写）、AAAI-26（7 页 + 参考文献与复现清单，US Letter，Type 1/TrueType 字体）。官方页没说清的一律不写。
- **规则检查**：模板与会议是否一致、终稿是否还停在评审模式、必需章节在不在。没指定 --venue 时按模板找规则，年份不对就用这一会议最新的规则并说明。
- **PDF 检查**（pypdf）：References 之前的正文页数对照上限（References 所在页上方有内容也算一页）、元数据里的作者名和带用户名的路径、Type 3 字体、没嵌入的字体、纸张大小。
- **arXiv 模式**：arXiv 会公开源码——注释行、\iffalse 块、论文没用到的 .tex 文件都列出来。
- **测量（50 篇已发表论文的 arXiv 源码）**：
  - camera-ready 模式（这些就是终稿，应当几乎不报）：第一版报“缺 checklist / Impact Statement / Limitations”24 处——拿 2025 年的规则要求 2017 年的论文，不合理；
    用的是“同一会议最新规则”时，缺章节降为提示并注明“新规则要求”。彩色文字（提示词、例子里大量是有意的）整项去掉。小写 todo（toggle 名）、XXX（ISBN 占位、tabularx 列格式）误报 → 只认大写 TODO/FIXME/TBD。
    FlashAttention 在 \iftoggle{arxiv}{}{\usepackage{neurips_2022}} 里加载模板，源码看不出 PDF 用的是哪种模式 → 条件里加载的模板只给提示。
    现在 camera-ready 模式下只剩 LDM 的 9 处 \todo{…}——它把 \todo 定义成红字打印，确实留在了 arXiv 版里。
  - arXiv 模式：注释一开始举的例子全是模板自带的（“allow utf-8 input”）→ 导言区的注释算模板的，只拿正文里的注释举例和定级。现在举出来的是作者真正的笔记，例如 Transformer 源码里的 “TODO(noam): update re…”。
  - 注入匿名泄露（五类、每类三种写法，插在正文段落之间）：750 处全部在注入的那一行查出。
  - 页数：5 篇真实论文的 PDF（Transformer、LoRA、DPO、LLaMA、DINOv2）上 References 标题都找对了页，紧跟在致谢或结论之后、第一条参考文献之前；
    DPO 的标题在第 11 页顶部 → 正文 10 页，正好是 NeurIPS 2023 终稿的 9+1 页。PDF 测完已删。
- **示例论文** examples/paper（ICML 2025，故意埋了问题）：模板在 [accepted] 模式、邮箱、致谢、第一人称自引、自己代码的链接、\todo、资助、缺 Impact Statement 全部查出；
  arXiv 模式下导言区的 “TODO(jd): ask Ada …” 一开始被当成模板注释 → 带 TODO/FIXME/XXX 的注释不论在哪都算作者自己的。
- **GitHub Action**（composite，只读，结果写进任务摘要，JSON 报告作输出）、**CI**（三系统 × 两个 Python，pytest/ruff/mypy，再用 action 跑示例并断言八类问题都在）、**Agent Skill**。17 个测试。
- **文档与发布**：中英 README（真实输出、每条规则带出处的表、准确度、做不到的事、完全离线）、CONTRIBUTING（怎么加一个会议：一个 TOML 文件、每个值上面引原句）、SECURITY、CHANGELOG、release 工作流、社交预览图。
- **建仓库** https://github.com/zch6a/submit-check 并推送。第一次 CI 在 Python 3.10 上挂了：又是“doctest 写在文档字符串第一行”（paper-proof 踩过的同一个坑）。
  修好后加了一个测试专门禁止这种写法，两个仓库都加上；以后推送前也在本地跑 3.10。CI 全绿。18 个测试。

## 第 1 轮打磨（2026-11-13，进行中）

- **新规则**：读官方页后加了 ECCV 2026（14 页不含参考文献；投稿正文**不允许附录**——为此给规则加了“禁止出现”的一类）和 KDD 2026 研究赛道（8 页，录用后 9 页正文；ACM acmart 模板，`anonymous` 选项才匿名——模板识别加上 acmart）。
  IJCAI 2026 的官方页在那个地址 404，读不到就不写。
- **对照 README 实测**：只给 PDF（带 / 不带 --venue）、损坏的 PDF、不存在的 --pdf、没有 \documentclass 的片段、没有 .tex 的文件夹、Latin-1 编码的 .tex、不存在的路径、什么都不给——
  改了两处：不存在的路径直接说“没有这个文件或文件夹”；片段文件照查但提示“这不是主文件，只查了它和它 \input 的”。
- 独立代码审查（子代理，只读、不联网）进行中。19 个测试。
- README 顶部加演示图 docs/demo.png（scripts/render_demo.py：真实彩色输出转 HTML、无头 Chrome 渲染，不截屏），文字版收进折叠块。
- **独立代码审查**（子代理，只读、不联网）找到 15 个问题、复现 14 个，全部修好，每个都有回归测试（tests/test_review_regressions.py，16 个）：
  1. **页数把不计入的章节也算进去了**：ICML 的 Impact Statement、ACL 的 Limitations 在 References 之前，正好卡在上限的论文会被误报超页 → 正文算到第一个“不计入”章节为止。
  2. 图（form XObject）里的 Type 3 字体没查到（matplotlib 的图就是这样）→ 递归查 XObject。
  3. **mAP@0.5、AP@0.75、transformers@4.36.2 被当成邮箱**（检测论文几乎都有）→ 邮箱要求以字母顶级域名结尾；ICML 的 \icmlcorrespondingauthor、AAAI 的 \affiliations、acmart 的 \email 在评审模式下由模板隐藏，不报；不认识的模板时“Anonymous”作者块里的邮箱照样报。
  4. Windows 上输出被重定向（cp1252）时，Markdown 报告里的零宽空格让程序崩溃（Action 在 windows 上会挂）→ 两个工具都把 stdout 改成 UTF-8；用 cp1252 子进程测过三种格式。
  5. 平方级正则：*.github.io 那一支没锚定（20 万个字符要 70 秒）、`\usepackage[` 重复 2 万次 12.8 秒、未闭合的 \author{ 重复 4000 次 3.8 秒、TODO 行数翻倍耗时翻四倍 → 都加了边界或改成线性。
  6. arXiv 模式仍按会议页数报超页 → arXiv 版不套会议规则。
  7. 模板写在 \input 的文件里时，报的文件和行号是主文件的 → 按文件识别模板。
  8. 奇怪的 PDF（/Info 不是字典、没有 MediaBox、MediaBox 坐标为负）会崩溃或量错纸张 → 都兜住，纸张用宽高。
  9. \ifcamera\iclrfinalcopy\fi 这种开关后面的终稿模式被当真 → 算“条件加载”。
  10. “As we previously showed in Section 3”“our previous results in Table 2”被当成自引；“the ResNet implementation available at github.com/pytorch/vision”被当成自己的代码 → 这类说法后面要紧跟 \cite 才算；“available at”单独不再算“自己的”。
  11. 漏报：\paragraph{Acknowledgments.}、“Acknowledgments and Disclosure of Funding”、“Code: \url{…}”、\PassOptionsToPackage{final}{neurips_2025} → 都能查出。
  12. arXiv 注释：`\\%` 之后的注释没算、注释里的 “% \iffalse” 被当成 \iffalse 块 → 改用偶数个反斜杠的规则、在去掉注释的文本里找 \iffalse。
  13. 选错规则：ECCV 的 ID=12345 被当成年份 2045 → 认 year= 选项；acmart 是 ACM 几十个会议共用的，不再默认套 KDD，要用 --venue；EMNLP 2025 这类近年的 ACL 系模板直接用 ARR 规则（老模板仍按“新规则只给提示”，因为不知道当年有没有这条要求）。
  14. References 标题：伪小型大写（“R EFERENCES”）找不到、目录页里的“References”被当成标题、页眉占一行时短页多算一页 → 都修好。
  15. 用 \newcommand* 或 \def 定义成空的 \todo 仍被报 → 认出来。
  另：Action 改用 `--pdf=$PDF` / `--venue=$VENUE`，以 “-” 开头的值不会被当成选项。
- 修完重测：50 篇终稿 camera-ready 模式仍只剩 LDM 的 9 处 \todo；注入泄露 750/750。示例论文的邮箱一条从第 20 行（模板终稿模式下本就会印出、已由模板那条覆盖）变成正文第 30 行，README 输出、演示图和社交预览图随之更新。35 个测试（3.10 / 3.13）。
- **命令行**：`--venue`、`--mode submission|camera-ready|arxiv`、`--pdf`（默认找主文件同名 PDF）、`--list-venues`（每条规则和来源）、终端/JSON/Markdown。14 个测试（测试用的 PDF 在测试里手写生成，不用真实论文）。

## 第 2 轮打磨（2026-11-13）

- **文档与规则一致**：新测试 tests/test_readme_rules.py——中英 README 规则表里的会议、页数、出处必须和 rules/*.toml 一致，以后改规则忘改 README 会直接挂测试。
- **体验**：`--help` 里每个选项都有说明，`--venue` 直接列出可选的会议；按 README 从 GitHub 全新安装（连同 paper-proof v0.1.0）约 20 秒，能跑。

## 第 3 轮打磨（2026-11-13）

- **IJCAI-ECAI 2026**：找到了官方主赛道征稿页（2026.ijcai.org/ijcai-ecai-2026-call-for-papers-main-track/），读后加规则：正文 7 页 + 参考文献 2 页。
  IJCAI 的样式包有没有自动隐藏作者的选项，官方页没说——不确定就不假设：认出 ijcai 模板但模式记为“未知”，作者名直接检查，不报“模板模式不对”。共 9 个会议。37 个测试。

## 第 4 轮打磨（2026-11-13）

- **代码**：anonymity.check 原来一个 100 行的函数，拆成模板模式、作者块、致谢、邮箱、链接、自引与资助几个小函数，共用一个“在不在某些区间里”的辅助；
  cli.py 里的终端和 Markdown 报告搬进 report.py（用脚本按 AST 搬，不手抄），cli.py 从 250 行降到 150 行。CONTRIBUTING 的源码表同步。
- 拆完重测：37 个测试、mypy、ruff 全过；50 篇终稿 camera-ready 模式仍只剩 LDM 的 9 处 \todo，注入泄露 750/750，示例论文输出一字不变。

## 第 5 轮打磨与发布（2026-11-13）

- **文档对照行为**：README 规则那一行补上“不许出现的内容（ECCV 投稿正文里的附录）”；说明 ACM acmart 要用 --venue（一个模板对应几十个会议）；Action 示例改用 `@v0`。
- **发布 v0.1.0**：CI 绿后打 tag，release 工作流（只读任务里测试、构建、取 CHANGELOG；写权限任务只调 gh）建了 GitHub Release（wheel + 源码包），v0 标签指向它。不发 PyPI。

### 2026-11-14 — Chinese README: AI tone

- 1 place: a 3-item 顿号 list inside a sentence reworded (what each rules value cites: the quoted sentence, then its address and reading date).
- The checks follow the findings of lieflat-less-ai-tone (shiujan, CC BY-NC 4.0); its findings applied, its text not copied.
- Left as they are: the colon-led lists (what it checks, the examples of desk rejections, what was fixed), 这是检查，不是匿名的保证 (a real scope limit, not a made-up misreading), the rules table the README test reads.

### 2026-11-14 — v0.1.1

Putting every tool's skill into one marketplace (research-kit) and running `claude plugin validate` on each
showed this one's SKILL.md frontmatter did not parse: a plain YAML value with `: ` inside ("…: text size…")
starts a new key, so Claude Code loaded the skill with no description, and an agent would never pick it. The
description and compatibility values are quoted (a JSON string is a YAML double-quoted scalar); validation passes.
Released as 0.1.1 so that `v0`, which the marketplace installs from, carries the fix.

### 2026-11-14 — a link to research-kit

Both READMEs now end (before the licence) with a short section pointing to research-kit, the toolkit's front door: all
thirteen tools in the order of the work, and one Claude Code plugin marketplace for their skills. Documentation only.

### 2026-11-14 — the release workflow and plain tags

The release workflow moves the major tag (v0) to the released commit. For a plain (lightweight) tag it asked GitHub
for a tag object at the commit's sha; that request fails, gh prints the error body on stdout, and the `|| echo` kept
that text in front of the sha, so v0 would not have moved. It now reads the ref's type and follows a tag object only
for an annotated tag, and stops if what it got is not a sha (the same fix arxiv-diff had in its final review).
Releases so far used annotated tags and were not affected.

### 2026-11-14 — 0.2.0: supplementary material and camera-ready

Chosen from research-kit's list of needs nothing covers: "anonymize everything submitted, not just the PDF"
(anonymous_github hides names in a hosted view only; no tool scans supplementary zips) and "camera-ready checks for ML
venues beyond ACL" (aclpubcheck covers the ACL template only).

**`supplementary.py`**: a zip or a folder, read in memory (20 MB a file, 400 MB in all, 20,000 files), one level of
nested zips. Folders (`.git`, `wandb/`, `mlruns/`, `.idea`, `__MACOSX`), credential files, names in file paths; in text
files: names, secrets, e-mails, user paths, author and copyright lines, W&B entities, GitHub accounts; notebooks read
as cells and outputs; PDFs (metadata and text, each finding once per PDF), Office properties, EXIF and PNG text, MP4
tags, all without new dependencies. Names from the paper's `\author` block are matched as written, reversed, and
joined (`jane_doe`, `janedoe`).

**Measured on 15 public research repositories** (zips from GitHub, to a temporary folder, deleted after):
- first run: 1,783 author/copyright findings, most from vendored code (HuggingFace headers copied into LoRA, CUTLASS
  headers in FlashAttention). Now the project's own licence and metadata at the top of the material are warnings,
  and every other header goes into one list per material (with counts);
- the same e-mail or user name in 86 places (`/home/mfuntowicz` in notebooks): one finding with "and 85 more places";
- `git@github.com`, `user:password@host` in URLs, `/home/something` are not addresses or users;
- "Copyright License. Subject to..." and "WIPO Copyright Treaty" (Apache and Creative Commons texts) were read as names;
- "Copyright (c) 2021 OpenAI" was missed (one word): now found. Result: 14 of 15 at warning level, DINO by a note.

**`camera.py`**: placeholder authors, anonymised links, "Anonymous" references, "under review", `\linenumbers`,
`draft`, the PDF's title. On the 50 arXiv sources: ReAct's anonymous.4open.science link and ConvNeXt's "Anonymous"
reference to ConvMixer are real. Fixed on the way: a nested quantifier in the "submitted to ..." pattern made the run
hang (catastrophic backtracking); `\usepackage{lineno}` alone numbers nothing (Chinchilla keeps `% \linenumbers`);
`Jordan~Hoffmann` is a name; uncited "Anonymous" entries never print.

13 tests (49 in all); README and Chinese README (what it checks, measured results, usage), Action input, Skill,
CHANGELOG; `examples/supplementary/code` with planted leaks.

### 2026-11-14 — 0.3.0: submit-check move

From research-kit's list: "move a paper between venue templates with a report of what breaks" (Pandoc loses custom
macros and venue environments; nothing knows page limits or style-file quirks). This is the report; the edits stay
with the author (or their agent, from the report).

`move.py`: the template line, a table of commands each family defines (ICML's title and author block and its
`\twocolumn[...]` wrapper, ICLR's final-copy switch, CVPR's paper ID and conference macros, ACL's, AAAI's, IJCAI's,
llncs', acmart's), column counts per family, the venues' required and forbidden sections from the rules files, the
bibliography styles of the kits, and the PDF's page count through pdfcheck.

Measured on the 50 arXiv sources (fetched again, deleted after): 43 have a known template, each moved to another
venue. 121 old-template commands, 43 template swaps, 37 section notes, 28 bibliography styles: read through, all
right. Column notes were 313 (one per float); now one per file and kind with a count (137). `\twocolumn[` is LaTeX's,
not ICML's: its message now says it is part of the title block ICML expects. 3 tests.

### 2026-11-14 — 0.4.0: LLM policies, supplementary material and author response

research-kit's deadline table lacked what its gap names: LLM policies, supplementary deadlines, rebuttal windows. The
nine official pages the rules come from were read again for these. The quotes came through a summarising reader
first; each was then checked against the page's own text (tags stripped): 19 of 24 matched as given; 4 were the
summariser closing a sentence early ("..., and may be rejected without review" given as a full stop), and IJCAI's
response period has a space before its colon; the files keep the page's own wording. ICLR's "responses as comments on OpenReview" was checked the same way. Where a
page says nothing (AAAI on LLMs, CVPR on supplementary deadlines), the value is empty, not guessed.

Notes in submission mode only where the paper can act: an ICLR paper with no LLM-usage section (whether LLMs were used,
the tool cannot know: a note), ACL and KDD's disclosure, ECCV's rule on citing non-existent material. 1 test.
