# Changelog

## 0.2.1 — 2026-11-14

- The Claude Code plugin's manifest (`plugin/.claude-plugin/plugin.json`) says 0.2.1: it had stayed at an older
  version through the last release, so the marketplace showed the old one (found by `repro-score release`).
- A `CITATION.cff`, for GitHub's "Cite this repository".

## 0.2.0 — 2026-11-14

**Supplementary material** (`--supplementary ZIP_OR_FOLDER`, repeatable; `--author NAME`): what gives the authors away
besides the paper. The authors' names (from `--author` and the paper's `\author` block), e-mail addresses, paths with
a user name, the project's own licence and metadata, a W&B entity, a `.git` folder (and the names in its config and
history), run logs, editor folders, API keys and tokens (shown by their first characters), a PDF's Author field and
text, an Office file's creator, a photo's EXIF Artist/Copyright/GPS, a PNG's Author, a video's artist tag, a zip in the
zip. Copyright headers of copied code and links to GitHub accounts are one note each. Read in memory, nothing
extracted. With no paper, `submit-check --supplementary DIR` checks the material alone. In camera-ready and arXiv
modes only secrets are reported. The GitHub Action has a `supplementary` input.

Measured on the code of 15 well-known papers (none anonymous): 14 give their authors away at warning level, the 15th
(DINO) through copyright headers listed in a note.

**Camera-ready** (`--mode camera-ready`): the author block still a placeholder; anonymised links
(anonymous.4open.science, "available upon acceptance"); cited references by "Anonymous"; "under review", "Paper ID"
in the text; `\linenumbers`; `draft` mode; no title in the PDF's metadata. On the 50 arXiv sources it finds two real
leftovers besides the 9 `\todo` notes already found (ReAct's anonymous code link, ConvNeXt's "Anonymous" reference).

## 0.1.1 — 2026-11-14

- The agent skill's frontmatter is valid YAML again: its description held a `: `, which YAML reads as a new key, so
  the whole frontmatter failed to parse and the skill loaded without its description (`claude plugin validate`
  reported it). The values are quoted now.

## 0.1.0

First release.

- Templates and their modes: NeurIPS, ICML, ICLR, CVPR/ICCV/WACV, ACL (ARR), ECCV, AAAI; loaded inside a condition.
- Anonymity: the template's mode, names, acknowledgements, e-mail addresses, `\thanks`, links to the authors' own code
  or pages, first-person self-citation, funding, the PDF's metadata.
- Rules for NeurIPS 2025, ICML 2025, ICLR 2026, ACL Rolling Review, CVPR 2026, ECCV 2026, KDD 2026 and AAAI-26, each value with the
  official sentence, page and date: page limits, required sections, the template.
- The PDF: content pages before the references, Type 3 and unembedded fonts, paper size.
- Leftover to-do notes; `--mode arxiv` for what an arXiv source would make public.
- Text, JSON and Markdown reports; a GitHub Action; an Agent Skill.
- Hardened after an independent code review: sections the venues do not count, fonts inside figures, e-mail look-alikes (mAP@0.5), addresses the template hides, Windows consoles, quadratic patterns, unusual PDFs, the References heading (small capitals, tables of contents).
- Measured on 50 published papers: camera-ready mode reports only the 9 `\todo` notes one of them really prints;
  750 of 750 injected leaks found.
