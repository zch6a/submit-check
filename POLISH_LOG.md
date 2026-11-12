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
