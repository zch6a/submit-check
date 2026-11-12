r"""Before uploading the source to arXiv, which publishes it: what does not print but would be public: comments
(often notes between co-authors, old numbers, reviewers' names), \iffalse blocks, and .tex files the paper does not use.
"""

from __future__ import annotations

import re
from pathlib import Path

from paper_proof.latex import read_source
from paper_proof.numbers import Finding

# Comment lines that say nothing (separators, template boilerplate) are not worth reporting.
EMPTY_COMMENT = re.compile(r"^\s*%+[\s%=\-*#~_.]*$|^\s*%\s*!TEX|^\s*%\s*auto-ignore", re.I)


def check(files: list[Path], root: Path) -> list[Finding]:
    out: list[Finding] = []
    comments: list[tuple[str, int, str]] = []
    blocks: list[tuple[str, int]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = read_source(path)
        for n, line in enumerate(text.split("\n"), 1):
            m = re.search(r"(?<!\\)%(.*)$", line)
            if m and not EMPTY_COMMENT.match("%" + m.group(1)) and len(m.group(1).strip()) > 2:
                comments.append((rel, n, m.group(1).strip()))
        for m in re.finditer(r"\\iffalse\b", text):
            blocks.append((rel, text.count("\n", 0, m.start()) + 1))
    if comments:
        examples = "; ".join(f"{f}:{n} {c[:50]!r}" for f, n, c in comments[:3])
        out.append(
            Finding(
                "arxiv-comments",
                "warning",
                comments[0][0],
                comments[0][1],
                f"{len(comments)} comment lines will be public with the source (e.g. {examples}); arxiv_latex_cleaner removes them",
            )
        )
    for f, n in blocks:
        out.append(Finding("arxiv-iffalse", "warning", f, n, "an \\iffalse block: it does not print, but it is public with the source"))
    used = {p.resolve() for p in files}
    for p in sorted(root.rglob("*.tex")):
        if p.resolve() not in used:
            out.append(
                Finding(
                    "arxiv-unused-file", "note", p.relative_to(root).as_posix(), 1, "not used by the paper, but it would be uploaded with the source"
                )
            )
    return out
