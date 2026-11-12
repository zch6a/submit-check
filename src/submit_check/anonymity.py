r"""What gives a double-blind submission away, found in the LaTeX source (comments and \iffalse blocks already gone:
they do not reach the PDF).

- the template in a mode that prints the authors (`[final]`, `[preprint]`, `[accepted]`, `\iclrfinalcopy`), or, with
  a template that does not hide them, real names in `\author`;
- acknowledgements and funding (outside the environments that templates hide by themselves, like NeurIPS's `ack`);
- e-mail addresses, `\thanks`, links to personal pages and to code under an account (github.com/<user>, *.github.io,
  ~user pages; anonymous.4open.science is fine);
- self-citation in the first person ("our previous work [12]", "as we showed in [12]"): cite your own work in the third
  person.

Each finding has a file and a line.
"""

from __future__ import annotations

import re

from paper_proof.numbers import Finding

from .templates import Template

ANONYMOUS = re.compile(r"anonymous|author\s*names?\s*withheld|blind|submission\s*\d*|paper\s*id|\bID\b", re.I)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Links that point to a person or an account (code hosted under a user, a personal page). Anonymised services pass.
ACCOUNT_LINK = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|huggingface\.co|twitter\.com|x\.com|linkedin\.com/in)/"
    r"(?!anonymous|anon\b|[^/\s}]*anonym)[\w.-]+"
    r"|(?:https?://)?[\w-]+\.github\.io\b"
    r"|https?://[^\s}]*/~[\w.-]+",
    re.I,
)
# A link gives the authors away when the text offers it as theirs; a link to someone else's library does not.
OWN = re.compile(
    r"\bour\s+(?:code|implementation|models?|data(?:set)?s?|project|repository|website|page|demo)\b|\bwe\s+(?:release|provide|make|open-?source|publish|share)\b"
    r"|\b(?:code|implementation|models?|data|datasets?|project\s+page|demo)\s+(?:and\s+\w+\s+)?(?:is|are|will\s+be)\s+(?:publicly\s+|made\s+|freely\s+)?(?:available|released|open-?sourced?)\b"
    r"|\bavailable\s+(?:at|on|from)\b|\bcan\s+be\s+found\s+(?:at|on)\b|\bproject\s+page\b",
    re.I,
)
ANONYMISED = re.compile(r"anonymous\.4open\.science|openreview\.net|anonymous|anonymized|anonymised", re.I)
SELF_CITE = re.compile(
    r"\b(?:our|my)\s+(?:(?:previous|prior|earlier|recent|own|past)\s+)+(?:work|paper|study|studies|method|approach|results?)s?\b"
    # "in our work" alone is this paper; with a citation right after it, it is an earlier one
    r"|\b(?:in|as\s+(?:shown|described|proposed)\s+in)\s+our\s+(?:previous\s+|prior\s+|earlier\s+)?(?:work|paper)s?\s*~?\s*(?:\(\s*)?\\cite"
    r"|\bwe\s+(?:previously|have\s+previously|earlier)\s+(?:showed|shown|proposed|introduced|presented|developed|described)\b"
    r"|\b(?:extends?|extending|builds?\s+on|building\s+on)\s+our\s+(?:previous\s+|prior\s+|earlier\s+)?(?:\w+\s+)?(?:work|paper|conference\s+paper)\b",
    re.I,
)
ACK_HEADING = re.compile(
    r"\\(?:section|subsection|paragraph)\*?\s*\{\s*(?:\\\w+\s*)?Acknowledg[e]?ments?\s*\}|\\begin\{(?:acknowledgments?|acknowledgements?)\}", re.I
)
NEURIPS_ACK = re.compile(r"\\begin\{ack\}", re.I)
FUNDING = re.compile(
    r"\b(?:supported|funded|sponsored)\s+(?:in\s+part\s+)?by\s+(?:the\s+)?(?:\w+\s+){0,6}?(?:grant|award|fellowship|foundation|NSF|NSFC|DARPA|ERC|DFG|NIH|JSPS)\b"
    r"|\bgrant\s+(?:no\.?|number|#)\s*[\w-]+",
    re.I,
)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _group(text: str, start: int) -> tuple[int, int] | None:
    """The braced argument that starts at `start` ('{' expected), as (inside start, inside end)."""
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2  # an escaped character (\{, \}) is not a brace
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start + 1, i
        i += 1
    return None


def _author_blocks(text: str) -> list[tuple[int, str]]:
    out = []
    for m in re.finditer(r"\\(?:author|icmlauthor|aaaiauthor)\s*(?:\[[^\]]*\])?\s*(?=\{)", text):
        g = _group(text, m.end())
        if g:
            out.append((g[0], text[g[0] : g[1]]))
    return out


def _real_names(block: str) -> bool:
    """Whether an \\author block holds something other than a placeholder ("Anonymous Authors", "Paper ID 1234")."""
    words = re.sub(r"\\[A-Za-z@]+|[{}\\$^_&~,.;:()0-9*]", " ", block)
    words = re.sub(r"\s+", " ", words).strip()
    return bool(words) and not ANONYMOUS.search(words)


def check(texts: dict[str, str], template: Template, mode: str = "submission") -> list[Finding]:
    """Findings for a project's texts (file -> text without comments). `mode` is "submission" (double-blind),
    "camera-ready" or "arxiv": only a submission must be anonymous."""
    if mode != "submission":
        return []
    out: list[Finding] = []
    main_file = next(iter(texts), "")
    if template.venue and template.conditional:
        out.append(
            Finding(
                "template-mode",
                "note",
                main_file,
                template.line,
                f"the {template.package} template is loaded inside a condition (\\iftoggle, \\if...): check that the "
                "submission is built in its anonymous mode",
            )
        )
    elif template.venue and not template.hides_authors:
        out.append(
            Finding(
                "template-mode",
                "error",
                main_file,
                template.line,
                f"the {template.package} template is in {template.mode} mode ({', '.join(template.options) or 'no review option'}): "
                "it prints the authors' names; use its anonymous submission mode",
            )
        )
    for file, text in texts.items():
        if not template.venue:  # a known template in final mode is reported once, above
            for pos, block in _author_blocks(text):
                if _real_names(block):
                    out.append(Finding("author-names", "error", file, _line(text, pos), "the \\author block has names in it, and nothing hides them"))
        for m in re.finditer(r"\\thanks\s*\{", text):
            if not template.hides_authors or not any(s <= m.start() < s + len(b) for s, b in _author_blocks(text)):
                out.append(
                    Finding(
                        "thanks", "warning", file, _line(text, m.start()), "\\thanks{...} (funding, affiliation or contact) gives the authors away"
                    )
                )
        hidden = [(m.start(), text.find("\\end{ack}", m.start())) for m in NEURIPS_ACK.finditer(text)] if template.venue == "neurips" else []
        for m in ACK_HEADING.finditer(text):
            out.append(
                Finding(
                    "acknowledgements",
                    "error",
                    file,
                    _line(text, m.start()),
                    "acknowledgements in a submission (they name people, groups and grants): remove them until the camera-ready"
                    + (" or move them into the template's ack environment, which is hidden in review mode" if template.venue == "neurips" else ""),
                )
            )
        # addresses in \author are the author block's business (hidden by the template, or reported above)
        author_spans = [(s, s + len(b)) for s, b in _author_blocks(text)]
        for m in EMAIL.finditer(text):
            if any(s <= m.start() < e for s, e in author_spans + hidden):
                continue
            out.append(Finding("email", "error", file, _line(text, m.start()), f"an e-mail address in the text: {m.group(0)}"))
        for m in ACCOUNT_LINK.finditer(text):
            around = text[max(0, m.start() - 40) : m.end() + 40]
            if ANONYMISED.search(around) or any(s <= m.start() < e for s, e in hidden + author_spans):
                continue
            sentence_start = max(0, text.rfind(". ", 0, m.start()), text.rfind("\n\n", 0, m.start()), m.start() - 160)
            if not OWN.search(text[sentence_start : m.start()] + " " + text[m.end() : m.end() + 60]):
                continue  # someone else's code or page, cited
            out.append(
                Finding(
                    "account-link",
                    "warning",
                    file,
                    _line(text, m.start()),
                    f"a link to an account or a personal page: {m.group(0)} (use an anonymised copy, e.g. anonymous.4open.science)",
                )
            )
        for m in SELF_CITE.finditer(text):
            if any(s <= m.start() < e for s, e in hidden):
                continue
            out.append(
                Finding(
                    "self-citation",
                    "warning",
                    file,
                    _line(text, m.start()),
                    f'"{m.group(0)}": citing your own work in the first person tells reviewers who you are; cite it in the third person',
                )
            )
        for m in FUNDING.finditer(text):
            if any(s <= m.start() < e for s, e in hidden):
                continue
            out.append(Finding("funding", "warning", file, _line(text, m.start()), f'funding information in a submission: "{m.group(0)}"'))
    return out
