r"""What should not be in any version that leaves your hands: visible to-do notes and editing marks (\todo{...},
TODO / FIXME / XXX in the text, "[citation needed]", "??" typed by hand). Comments are already
gone (they never reach the PDF): only what prints is reported.
"""

from __future__ import annotations

import bisect
import re

from paper_proof.numbers import Finding

# Commands whose definition is a no-op in the final paper are still worth a look; a \newcommand{\todo}[1]{} that
# swallows its argument prints nothing, so definitions that discard the argument are recognised and skipped.
# (\hl and \colorbox highlight on purpose, in prompts and tables: not edit marks.)
TODO_COMMANDS = re.compile(r"\\(todo|todoinline|fixme|tbd|missingfigure)\s*(?:\[[^\]\n]{0,200}\])?\s*\{", re.I)
# In capitals only ("todo" is often a toggle's name); XXX is left out: it is an ISBN placeholder or a tabularx column
# spec as often as a note.
TODO_WORDS = re.compile(r"(?<![\w\\{])(?:TODO|FIXME|TBD)(?![\w}])|(?i:\[\s*citation needed\s*\]|\[\s*ref\s*\?\s*\]|\[\s*cite\s*\])|(?<![?\w])\?\?\?+")


def _defined_silent(texts: dict[str, str], name: str) -> bool:
    """\\newcommand{\\todo}[1]{} (or \\renewcommand): the command prints nothing, so uses of it are harmless."""
    for text in texts.values():
        # \newcommand{\todo}[1]{}, \newcommand*{\todo}[1]{}, \renewcommand, \def\todo#1{}
        m = re.search(r"\\(?:re)?newcommand\*?\s*\{?\\" + re.escape(name) + r"\}?\s*(?:\[\d\])?(?:\[[^\]\n]{0,100}\])?\s*\{\s*\}", text) or re.search(
            r"\\def\s*\\" + re.escape(name) + r"\s*(?:#\d)*\s*\{\s*\}", text
        )
        if m:
            return True
        if re.search(r"\\usepackage\s*\[[^\]]*\bdisable\b[^\]]*\]\s*\{todonotes\}", text):
            return name.lower().startswith("todo")
    return False


def check(texts: dict[str, str]) -> list[Finding]:
    out: list[Finding] = []
    definitions = re.compile(r"\\(?:re)?newcommand|\\providecommand|\\def\\|\\DeclareRobustCommand|\\NewDocumentCommand")
    silent: dict[str, bool] = {}
    for file, text in texts.items():
        lines = text.split("\n")
        starts = [0]  # where each line starts: line numbers by bisection, not by counting from the top each time
        for line in lines[:-1]:
            starts.append(starts[-1] + len(line) + 1)

        def line_of(pos: int) -> int:
            return bisect.bisect_right(starts, pos)  # noqa: B023 (used inside this file's loop only)

        for m in TODO_COMMANDS.finditer(text):
            n = line_of(m.start())
            name = m.group(1)
            if name not in silent:
                silent[name] = _defined_silent(texts, name)
            if definitions.search(lines[n - 1]) or silent[name]:
                continue
            out.append(Finding("todo", "warning", file, n, f"an editing note left in the text: \\{name}{{...}}"))
        for m in TODO_WORDS.finditer(text):
            n = line_of(m.start())
            if definitions.search(lines[n - 1]) or "\\url" in lines[n - 1]:
                continue
            out.append(Finding("todo", "warning", file, n, f'"{m.group(0)}" left in the text'))
    return out
