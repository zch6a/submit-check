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
- **命令行**：`--venue`、`--mode submission|camera-ready|arxiv`、`--pdf`（默认找主文件同名 PDF）、`--list-venues`（每条规则和来源）、终端/JSON/Markdown。14 个测试（测试用的 PDF 在测试里手写生成，不用真实论文）。
