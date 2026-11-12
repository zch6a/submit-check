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
- **命令行**：`--venue`、`--mode submission|camera-ready|arxiv`、`--pdf`（默认找主文件同名 PDF）、`--list-venues`（每条规则和来源）、终端/JSON/Markdown。14 个测试（测试用的 PDF 在测试里手写生成，不用真实论文）。
