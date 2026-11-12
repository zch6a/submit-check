# Changelog

## 0.1.0

First release.

- Templates and their modes: NeurIPS, ICML, ICLR, CVPR/ICCV/WACV, ACL (ARR), ECCV, AAAI; loaded inside a condition.
- Anonymity: the template's mode, names, acknowledgements, e-mail addresses, `\thanks`, links to the authors' own code
  or pages, first-person self-citation, funding, the PDF's metadata.
- Rules for NeurIPS 2025, ICML 2025, ICLR 2026, ACL Rolling Review, CVPR 2026 and AAAI-26, each value with the
  official sentence, page and date: page limits, required sections, the template.
- The PDF: content pages before the references, Type 3 and unembedded fonts, paper size.
- Leftover to-do notes; `--mode arxiv` for what an arXiv source would make public.
- Text, JSON and Markdown reports; a GitHub Action; an Agent Skill.
- Measured on 50 published papers: camera-ready mode reports only the 9 `\todo` notes one of them really prints;
  750 of 750 injected leaks found.
