r"""Before uploading the source to arXiv, which publishes it: what does not print but would be public: comments
(often notes between co-authors, old numbers, reviewers' names), \iffalse blocks, and .tex files the paper does not use.
"""

from __future__ import annotations

import re
from pathlib import Path

from paper_proof.latex import read_source
from paper_proof.numbers import Finding

# Comment lines that say nothing (separators, template boilerplate) are not worth reporting.
# Comments that come with the venues' templates and example papers.
BOILERPLATE = re.compile(
    r"allow utf-8 input|8-bit T1 fonts|hyperlinks|simple URL typesetting|professional-quality tables|blackboard math|"
    r"compact symbols|microtypograph|colou?rs|nicefrac|uncomment (?:this|the following) line|pass options to natbib|"
    r"before loading|for neurips formatting|for latex2e|optional math commands|\[review\|final|camera-ready|"
    r"for bold caption labels|recommended,? but optional|use the following line|for the final version|"
    r"if you use|attempt to make hyperref|^\s*file \S+\.tex|based on the style files",
    re.I,
)
EMPTY_COMMENT = re.compile(r"^\s*%+[\s%=\-*#~_.]*$|^\s*%\s*!TEX|^\s*%\s*auto-ignore", re.I)


def check(files: list[Path], root: Path) -> list[Finding]:
    out: list[Finding] = []
    comments: list[tuple[str, int, str, bool]] = []  # file, line, text, in the body
    blocks: list[tuple[str, int]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = read_source(path)
        # In the main file, the preamble's comments are the template's and the packages'; the notes about the paper
        # are in the body (and in every \input file).
        begin = re.search(r"^[^%\n]*\\begin\{document\}", text, re.M)
        first_body_line = text.count("\n", 0, begin.start()) + 1 if begin else 1
        for n, line in enumerate(text.split("\n"), 1):
            m = re.search(r"(?<!\\)%(.*)$", line)
            if m and not EMPTY_COMMENT.match("%" + m.group(1)) and len(m.group(1).strip()) > 2:
                note = m.group(1).strip()
                # a note to a co-author is the authors' own wherever it is, preamble included
                comments.append((rel, n, note, n >= first_body_line or bool(re.search(r"\b(?:TODO|FIXME|XXX)\b", note))))
        for m in re.finditer(r"\\iffalse\b", text):
            blocks.append((rel, text.count("\n", 0, m.start()) + 1))
    if comments:
        # The template's own comments ("allow utf-8 input") are harmless; notes in prose and commented-out text are
        # what people regret publishing: those are shown first, and only they make it a warning.
        body = [c for c in comments if c[3] and not BOILERPLATE.search(c[2])]
        prose = [c for c in body if not c[2].lstrip().startswith("\\") and len(c[2].split()) >= 4]
        shown = (prose or body or comments)[:3]
        examples = "; ".join(f"{f}:{n} {c[:60]!r}" for f, n, c, _ in shown)
        out.append(
            Finding(
                "arxiv-comments",
                "warning" if body else "note",
                shown[0][0],
                shown[0][1],
                f"{len(comments)} comment lines will be public with the source, {len(body)} of them the authors' own "
                f"({len(prose)} notes in prose, e.g. {examples}); arxiv_latex_cleaner removes them",
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
