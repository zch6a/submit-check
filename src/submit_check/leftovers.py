r"""What should not be in any version that leaves your hands: visible to-do notes and editing marks (\todo{...},
TODO / FIXME / XXX in the text, \hl{...}, red text, "[citation needed]", "??" typed by hand). Comments are already
gone (they never reach the PDF): only what prints is reported.
"""

from __future__ import annotations

import re

from paper_proof.numbers import Finding

# Commands whose definition is a no-op in the final paper are still worth a look; a \newcommand{\todo}[1]{} that
# swallows its argument prints nothing, so definitions that discard the argument are recognised and skipped.
# (\hl and \colorbox highlight on purpose, in prompts and tables: not edit marks.)
TODO_COMMANDS = re.compile(r"\\(todo|todoinline|fixme|tbd|missingfigure)\s*(?:\[[^\]]*\])?\s*\{", re.I)
TODO_WORDS = re.compile(
    r"(?<![\w\\])(?:TODO|FIXME|TBD|XXX+)(?![\w])|\[\s*citation needed\s*\]|\[\s*ref\s*\?\s*\]|\[\s*cite\s*\]|(?<![?\w])\?\?\?+", re.I
)
RED = re.compile(r"\\(?:textcolor|color)\s*\{\s*(?:red|blue|magenta|orange)\s*\}", re.I)


def _defined_silent(texts: dict[str, str], name: str) -> bool:
    """\\newcommand{\\todo}[1]{} (or \\renewcommand): the command prints nothing, so uses of it are harmless."""
    for text in texts.values():
        m = re.search(r"\\(?:re)?newcommand\s*\{?\\" + re.escape(name) + r"\}?\s*(?:\[\d\])?(?:\[[^\]]*\])?\s*\{\s*\}", text)
        if m:
            return True
        if re.search(r"\\usepackage\s*\[[^\]]*\bdisable\b[^\]]*\]\s*\{todonotes\}", text):
            return name.lower().startswith("todo")
    return False


def check(texts: dict[str, str]) -> list[Finding]:
    out: list[Finding] = []
    definitions = re.compile(r"\\(?:re)?newcommand|\\providecommand|\\def\\|\\DeclareRobustCommand|\\NewDocumentCommand")
    for file, text in texts.items():
        lines = text.split("\n")
        for m in TODO_COMMANDS.finditer(text):
            line_text = lines[text.count("\n", 0, m.start())]
            if definitions.search(line_text) or _defined_silent(texts, m.group(1)):
                continue
            out.append(
                Finding("todo", "warning", file, text.count("\n", 0, m.start()) + 1, f"an editing note left in the text: \\{m.group(1)}{{...}}")
            )
        for m in TODO_WORDS.finditer(text):
            line_text = lines[text.count("\n", 0, m.start())]
            if definitions.search(line_text) or "\\url" in line_text:
                continue
            out.append(Finding("todo", "warning", file, text.count("\n", 0, m.start()) + 1, f'"{m.group(0)}" left in the text'))
        for m in RED.finditer(text):
            line_text = lines[text.count("\n", 0, m.start())]
            if definitions.search(line_text) or "definecolor" in line_text or "hypersetup" in line_text:
                continue
            out.append(Finding("colored-text", "note", file, text.count("\n", 0, m.start()) + 1, "coloured text (an edit mark left in?)"))
    return out
