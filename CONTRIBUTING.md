# Contributing

The most useful contributions are **rules** (a new venue, a new year, a correction) and **false alarms or missed leaks
on real papers** (an issue with the arXiv id or a few lines of LaTeX, and what submit-check said or missed).

## Adding or fixing a venue's rules

One TOML file per venue and year in `src/submit_check/rules/`. Copy the closest one and change it:

```toml
[venue]
id = "neurips2026"
name = "NeurIPS 2026"
source = "https://neurips.cc/Conferences/2026/CallForPapers"   # the official page
verified = "2027-03-01"                                          # the day you read it
template = "neurips"                                             # the template family (see templates.py)

[pages]
# "The main text of a submitted paper is limited to nine content pages ..."   <- the sentence, quoted
submission = 9
camera_ready = 10
not_counted = ["references", "checklist", "appendix"]

[[required]]
# "authors are required to complete a paper checklist"
what = "the NeurIPS paper checklist"
pattern = 'checklist'          # a regular expression; heading = true to look only in section titles
modes = ["submission", "camera-ready"]
severity = "error"
```

Only what the official page states: quote the sentence above each value. If the page does not say it, leave it out.

## Development

```bash
uv sync
uv run pytest -q          # no test reaches the network; the PDFs are written by the tests
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

A new check comes with a test built from the real case that motivated it, and the measurement still holds:
`scripts/inject_leaks.py` (injected leaks found), and `--mode camera-ready` on published papers (nearly silent).
Fetch sources with paper-proof's `scripts/fetch_arxiv_sources.py`, into a folder outside this repository. Never commit
papers' sources or PDFs.

## Where things are

| | |
|---|---|
| `templates.py` | which venue's template, in which mode |
| `anonymity.py`, `leftovers.py` | double-blind leaks; to-do notes |
| `rules.py`, `rules/*.toml` | the venues' rules and the checks that need them |
| `pdfcheck.py` | pages, metadata, fonts, paper size |
| `arxivcheck.py` | what an arXiv source would make public |
| `cli.py` | the command line and the reports |
