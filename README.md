<div align="center">

# submit-check

**Don't get desk-rejected for something a script could have caught.** submit-check reads your LaTeX project and the
compiled PDF, and checks them against the venue's submission rules: nothing gives the authors away, the template is
in the right mode, the required sections are there, the content fits the page limit, the PDF's fonts and metadata are
clean, and no `\todo` is left. Before you post the source to arXiv, it lists the comments the world would read.

<a href="https://github.com/zch6a/submit-check/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/zch6a/submit-check/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
<img alt="Offline" src="https://img.shields.io/badge/network-none-2ea44f">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>

**English** · [简体中文](README.zh-CN.md)

</div>

---

Every year, papers are desk-rejected for things nobody meant to leave in: the template's camera-ready option still
on, an acknowledgements section naming the lab, "as we showed in our previous work [12]", a GitHub link under the
author's own account, a missing Limitations section at ACL, the author's name in the PDF's metadata, a tenth page.
This is submit-check's real output on [the example paper](examples/paper/main.tex):

```text
$ submit-check examples/paper
submit-check 0.1.0 · examples/paper: submission, ICML 2025 rules, template icml2025 (final mode)

ERROR    main.tex:1  ICML 2025 requires an Impact Statement section, and it is not in the paper (https://icml.cc/Conferences/2025/CallForPapers)
ERROR    main.tex:6  the icml2025 template is in final mode (accepted): it prints the authors' names; use its anonymous submission mode
ERROR    main.tex:20  an e-mail address in the text: jane.doe@example-university.edu
ERROR    main.tex:35  acknowledgements in a submission (they name people, groups and grants): remove them until the camera-ready
WARNING  main.tex:29  "extends our earlier conference paper": citing your own work in the first person tells reviewers who you are; cite it in the third person
WARNING  main.tex:30  a link to an account or a personal page: https://github.com/janedoe42 (use an anonymised copy, e.g. anonymous.4open.science)
WARNING  main.tex:33  an editing note left in the text: \todo{...}
WARNING  main.tex:36  funding information in a submission: "supported by the National Science Foundation"
WARNING  main.tex:37  funding information in a submission: "grant no. 1234567"

Summary: 4 ERRORS, 5 WARNINGS
```

## What it checks

| | |
|---|---|
| **Template and mode** | NeurIPS, ICML, ICLR, CVPR/ICCV/WACV, ACL (ARR), ECCV, AAAI and ACM (`acmart`) templates, and whether they are in their anonymous mode (`[final]`, `[preprint]`, `[accepted]`, `\iclrfinalcopy` print the authors; `acmart` needs `anonymous`); the template matches the venue; a camera-ready is not left in review mode |
| **Anonymity** | names in `\author` when nothing hides them; acknowledgements (NeurIPS's `ack` environment is hidden by its template and passes); e-mail addresses; `\thanks`; links to the authors' own code or pages (a link to someone else's library passes; anonymous.4open.science passes); first-person self-citation; funding and grant numbers; the PDF's Author field and user paths in its metadata |
| **The venue's rules** | content pages before the References heading against the limit (submission or camera-ready); required sections: the NeurIPS paper checklist, ICML's Impact Statement, ACL's Limitations section, AAAI's reproducibility checklist |
| **The PDF** | Type 3 (bitmap) fonts, fonts not embedded, the paper size (AAAI: US Letter) |
| **Leftovers** | `\todo{}`, `\fixme{}`, TODO / FIXME / TBD in the text, "[citation needed]", "???" (a `\todo` defined to print nothing passes) |
| **arXiv** (`--mode arxiv`) | arXiv publishes your source: the comment lines that would be public (the authors' own notes first, not the template's), `\iffalse` blocks, `.tex` files the paper does not use |

Only what prints is checked for leaks: comments and `\iffalse` blocks never reach the PDF (they matter for arXiv, and
`--mode arxiv` reports them).

## The rules, and where they come from

Each venue's rules are a small TOML file in [`src/submit_check/rules/`](src/submit_check/rules/), with every value next to
the sentence of the official call for papers it comes from, the page's address, and the date it was read.
`submit-check --list-venues` prints them.

| Venue | Pages (camera-ready) | Not counted | Required | Source (read 2026-11-13) |
|---|---|---|---|---|
| NeurIPS 2025 (`neurips2025`) | 9 (10) | references, checklist, appendix | paper checklist | [call for papers](https://neurips.cc/Conferences/2025/CallForPapers) |
| ICML 2025 (`icml2025`) | 8 (9) | references, impact statement, appendix | Impact Statement | [call for papers](https://icml.cc/Conferences/2025/CallForPapers) |
| ICLR 2026 (`iclr2026`) | 9 (10) | references, appendix, statements | (Reproducibility Statement encouraged) | [author guide](https://iclr.cc/Conferences/2026/AuthorGuide) |
| ACL Rolling Review (`acl-arr`) | 8, long papers | references, limitations, ethics, appendix | Limitations section | [call for papers](https://aclrollingreview.org/cfp) |
| CVPR 2026 (`cvpr2026`) | 8 | references | | [author guidelines](https://cvpr.thecvf.com/Conferences/2026/AuthorGuidelines) |
| ECCV 2026 (`eccv2026`) | 14 | references | no appendix in the main submission | [submission policies](https://eccv.ecva.net/Conferences/2026/SubmissionPolicies) |
| KDD 2026, research track (`kdd2026`) | 8 (9) | references, appendix | ACM template, `anonymous` option | [call for papers](https://kdd2026.kdd.org/research-track-call-for-papers/) |
| AAAI-26 (`aaai2026`) | 7 | references, reproducibility checklist | reproducibility checklist; US Letter; Type 1/TrueType fonts | [submission instructions](https://aaai.org/conference/aaai/aaai-26/submission-instructions/) |

What an official page does not state (CVPR's camera-ready length, for instance) is not in the rules. Rules change
every year: a pull request with the new value, the sentence and the source is the way to fix one, and adding a venue
is one file ([CONTRIBUTING](CONTRIBUTING.md)).

Without `--venue`, the template chooses the rules. For an older template (`neurips_2023`), the venue's newest rules are
used and the report says so; a section those newer rules require is then only a note.

## How accurate it is

Measured on the arXiv sources of 50 well-known papers (the list is in paper-proof's
[`scripts/papers.txt`](https://github.com/zch6a/paper-proof/blob/main/scripts/papers.txt); the sources are fetched for
the measurement and never stored here):

- **False alarms.** These are camera-ready versions, so `--mode camera-ready` should find nothing. It finds the 9
  `\todo{}` notes the Stable Diffusion (LDM) source really prints in red, and nothing else. On the way there:
  newer rules were judged too strictly against older papers, coloured text and lower-case "todo"/"XXX" (toggle names,
  ISBN placeholders, table column specs) raised alarms, and a template loaded inside `\iftoggle` (FlashAttention)
  was taken at face value; all fixed.
- **Missed leaks.** Five kinds of leak (own-code link, first-person self-citation, acknowledgements, e-mail, funding),
  each in three wordings, put into the body of each of the 50 papers: **750 of 750 found**, each at its line.
- **Page counting.** On the PDFs of five of them, the References heading was found on the right page each time.
- **arXiv.** On the same sources as arXiv publishes them, `--mode arxiv` points to the authors' own notes, such as
  the Transformer source's "TODO(noam): update re…".

What it cannot know:
- Whether a link, a self-citation or a dataset gives you away in a way it has no pattern for (a lab-specific tool's
  name, a demo video, a figure with your logo). It is a check, not a guarantee of anonymity.
- Rules it does not have: workshop formats, journal templates, venues not listed. Then it still checks anonymity,
  leftovers and the PDF.
- The page count of a PDF without a References heading (it says so).

## Install

Python 3.10+. With [uv](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/zch6a/submit-check submit-check path/to/paper
```

or install it: `uv tool install git+https://github.com/zch6a/submit-check`.

## Use

```bash
submit-check paper/                          # a LaTeX project folder (the main .tex is found), its main.pdf if present
submit-check paper/ --venue neurips2025      # the rules to use (default: from the template)
submit-check paper/ --pdf build/paper.pdf    # the compiled PDF, if it is elsewhere
submit-check paper/ --mode camera-ready      # names and acknowledgements are fine now; the camera-ready page limit
submit-check paper/ --mode arxiv             # before uploading the source to arXiv
submit-check paper.pdf --venue icml2025      # a PDF alone: pages, metadata, fonts
submit-check --list-venues                   # every rule, with its source
```

`--format json` gives every finding with its file and line; `--format md` a table for a pull request. Exit codes: 0
nothing at the `--fail-on` level (`error` by default; `warning`, `never`), 1 something found, 2 the input could not be
read.

## On every push (GitHub Action)

For a paper kept in a repository (an Overleaf project synced with GitHub works too):

```yaml
name: submit-check
on: [push, pull_request]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: zch6a/submit-check@main
        with:
          path: paper
          venue: neurips2025   # optional: from the template otherwise
          # pdf: paper/main.pdf
```

The report goes to the job summary; the JSON report is the `report` output. Read-only, and it runs nothing from your
repository.

## In your AI agent (Agent Skill)

[`plugin/skills/submit-check/SKILL.md`](plugin/skills/submit-check/SKILL.md) tells Claude Code and other agents that
read Agent Skills to run submit-check before a submission, a camera-ready or an arXiv upload, and how to act on each
kind of finding.

## Privacy

Nothing is sent anywhere: the rules ship with the tool, and the paper and the PDF are read locally. It reads the
LaTeX project through [paper-proof](https://github.com/zch6a/paper-proof)'s reader (`\input`, comments, `\iffalse`),
whose reference checks it does not use.

## License

MIT
