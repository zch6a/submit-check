---
name: submit-check
description: "Check a LaTeX paper against a conference's submission rules with submit-check before it is submitted, made camera-ready, or posted to arXiv. Finds what breaks double-blind review (a template in final mode, names, acknowledgements, e-mails, links to the authors' code, first-person self-citation, funding lines, PDF metadata), the page limit, missing required sections (NeurIPS checklist, ICML impact statement, ACL Limitations), Type 3 or unembedded fonts, leftover TODO notes, and the comments an arXiv source would make public. Use when the user is about to submit a paper, prepares a camera-ready, or uploads LaTeX source to arXiv."
license: MIT
compatibility: "Needs Python 3.10+ and uv. Runs submit-check with uvx from GitHub (git+https://github.com/zch6a/submit-check) unless a submit-check command is installed. Offline: nothing is sent anywhere."
metadata:
  homepage: https://github.com/zch6a/submit-check
---

# Checking a submission with submit-check

```bash
uvx --from git+https://github.com/zch6a/submit-check submit-check path/to/paper
```

Use `submit-check` instead of the `uvx ...` prefix if it is installed. `path/to/paper` is the LaTeX project folder or
its main `.tex`; the compiled PDF next to the main file is checked too (or pass `--pdf`). Options:

- `--venue neurips2025` (or icml2025, iclr2026, acl-arr, cvpr2026, aaai2026): the rules; by default they follow the
  template. `submit-check --list-venues` shows every rule with the official page it comes from.
- `--mode submission` (default, double-blind), `--mode camera-ready`, `--mode arxiv` (before uploading the source).
- `--format json` for every finding with file and line.

## Acting on the results

- ERROR: the submission breaks a rule or gives the authors away (template in final mode, names, e-mail,
  acknowledgements, a missing required section, over the page limit, the author in the PDF metadata). Tell the user
  each one with its file and line; they are usually quick to fix, and fixing them yourself is fine when the change is
  mechanical (switch the template option, remove the acknowledgements until the camera-ready, `pdfauthor={}`).
- WARNING: likely a leak or a leftover (a link to the authors' code, "our previous work [12]", a funding line, a
  `\todo`). Show them; rewording self-citations in the third person is the author's call, not yours.
- note: worth a look (the template is loaded inside a condition, the rules are another year's).

Rules change every year: if a rule looks wrong, check the source the report cites and tell the user.
