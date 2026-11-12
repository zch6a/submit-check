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
# The last label of the domain must be letters (a top-level domain): mAP@0.5, transformers@4.36.2 are not addresses.
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})*\.[A-Za-z]{2,24}\b")
# Links that point to a person or an account (code hosted under a user, a personal page). Anonymised services pass.
ACCOUNT_LINK = re.compile(
    r"(?:https?://)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|huggingface\.co|twitter\.com|x\.com|linkedin\.com/in)/"
    r"(?!anonymous|anon\b|[^/\s}]*anonym)[\w.-]+"
    r"|(?:https?://)?(?<![\w-])[\w-]{1,100}\.github\.io\b"
    r"|https?://[^\s}]{0,200}/~[\w.-]+",
    re.I,
)
# A link gives the authors away when the text offers it as theirs; a link to someone else's library does not.
OWN = re.compile(
    r"\bour\s+(?:code|implementation|models?|data(?:set)?s?|project|repository|website|page|demo)\b|\bwe\s+(?:release|provide|make|open-?source|publish|share)\b"
    r"|\b(?:code|implementation|models?|data|datasets?|project\s+page|demo)\s+(?:and\s+\w+\s+)?(?:is|are|will\s+be)\s+(?:publicly\s+|made\s+|freely\s+)?(?:available|released|open-?sourced?)\b"
    r"|\bproject\s+page\b",
    re.I,
)
# "Code: \url{...}" right before the link
OWN_LABEL = re.compile(r"\b(?:code|project(?:\s+page)?|website|demo|repository|repo)\s*:\s*(?:\\(?:url|href)\s*\{)?\s*$", re.I)
ANONYMISED = re.compile(r"anonymous\.4open\.science|openreview\.net|anonymous|anonymized|anonymised", re.I)
SELF_CITE = re.compile(
    r"\b(?:our|my)\s+(?:(?:previous|prior|earlier|recent|own|past)\s+)+(?:work|paper|study|studies)s?\b"
    # "our previous results" or "we previously showed" can be about this paper ("in Section 3"): only with a
    # citation right after them are they an earlier paper
    r"|\b(?:our|my)\s+(?:(?:previous|prior|earlier|recent|own|past)\s+)+(?:method|approach|results?|model|system)s?\s*~?\s*(?:\(\s*)?\\cite"
    # "in our work" alone is this paper; with a citation right after it, it is an earlier one
    r"|\b(?:in|as\s+(?:shown|described|proposed)\s+in)\s+our\s+(?:previous\s+|prior\s+|earlier\s+)?(?:work|paper)s?\s*~?\s*(?:\(\s*)?\\cite"
    r"|\bwe\s+(?:previously|have\s+previously|earlier)\s+(?:showed|shown|proposed|introduced|presented|developed|described)\b[^.]{0,80}?\\cite"
    r"|\b(?:extends?|extending|builds?\s+on|building\s+on)\s+our\s+(?:previous\s+|prior\s+|earlier\s+)?(?:\w+\s+)?(?:work|paper|conference\s+paper)\b",
    re.I,
)
ACK_HEADING = re.compile(
    r"\\(?:section|subsection|subsubsection|paragraph)\*?\s*\{\s*(?:\\\w+\s*)?Acknowledg(?:e)?ments?\b[^{}]{0,80}\}"
    r"|\\begin\{(?:acknowledgments?|acknowledgements?)\}",
    re.I,
)
# Commands whose argument a review-mode template hides along with the authors.
AUTHOR_COMMANDS = r"author|icmlauthor|aaaiauthor|icmlcorrespondingauthor|icmlaffiliation|affiliations?|email|institute|address"
NEURIPS_ACK = re.compile(r"\\begin\{ack\}", re.I)
FUNDING = re.compile(
    r"\b(?:supported|funded|sponsored)\s+(?:in\s+part\s+)?by\s+(?:the\s+)?(?:\w+\s+){0,6}?(?:grant|award|fellowship|foundation|NSF|NSFC|DARPA|ERC|DFG|NIH|JSPS)\b"
    r"|\bgrant\s+(?:no\.?|number|#)\s*[\w-]+",
    re.I,
)


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _group(text: str, start: int) -> tuple[int, int] | None:
    """The braced argument that starts at `start` ('{' expected), as (inside start, inside end). An argument longer
    than any author block (5000 characters) is not one: unbalanced braces must not make every scan run to the end."""
    depth, i = 0, start
    while i < min(len(text), start + 5000):
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


def _author_blocks(text: str, commands: str = "author|icmlauthor|aaaiauthor") -> list[tuple[int, str]]:
    """The arguments of the author commands, every braced argument of each (\\icmlcorrespondingauthor{name}{email})."""
    out = []
    for m in re.finditer(r"\\(?:" + commands + r")\s*(?:\[[^\]\n]{0,200}\])?\s*(?=\{)", text):
        pos = m.end()
        for _ in range(3):
            g = _group(text, pos)
            if not g:
                break
            out.append((g[0], text[g[0] : g[1]]))
            nxt = re.match(r"\s*\{", text[g[1] + 1 : g[1] + 20])
            if not nxt:
                break
            pos = g[1] + 1 + nxt.end() - 1
    return out


def _real_names(block: str) -> bool:
    """Whether an \\author block holds something other than a placeholder ("Anonymous Authors", "Paper ID 1234")."""
    words = re.sub(r"\\[A-Za-z@]+|[{}\\$^_&~,.;:()0-9*]", " ", block)
    words = re.sub(r"\s+", " ", words).strip()
    return bool(words) and not ANONYMOUS.search(words)


Spans = list[tuple[int, int]]


def _inside(pos: int, spans: Spans) -> bool:
    return any(s <= pos < e for s, e in spans)


def _template_mode(template: Template, main_file: str) -> list[Finding]:
    """A known template in a mode that prints the authors (or loaded behind a condition, where the mode is unknown)."""
    if template.venue and template.conditional:
        msg = (
            f"the {template.package} template is loaded inside a condition (\\iftoggle, \\if...): check that the "
            "submission is built in its anonymous mode"
        )
        return [Finding("template-mode", "note", main_file, template.line, msg)]
    if template.venue and template.mode and not template.hides_authors:
        msg = (
            f"the {template.package} template is in {template.mode} mode ({', '.join(template.options) or 'no review option'}): "
            "it prints the authors' names; use its anonymous submission mode"
        )
        return [Finding("template-mode", "error", main_file, template.line, msg)]
    return []


def _authors(file: str, text: str, template: Template) -> tuple[list[Finding], Spans]:
    """Names in \\author when nothing hides them, \\thanks; and the spans whose addresses and links are not to be
    reported again: what a review-mode template hides, what a known template in final mode prints (reported once, as
    its mode), or, with no known template, the author blocks already reported for their names (an e-mail in an
    "Anonymous" block is still a leak)."""
    out: list[Finding] = []
    blocks = _author_blocks(text)  # once: there may be many \\thanks
    named = [(s, b) for s, b in blocks if _real_names(b)]
    known_mode = bool(template.venue and template.mode)
    if not known_mode:
        for pos, _block in named:
            out.append(Finding("author-names", "error", file, _line(text, pos), "the \\author block has names in it, and nothing hides them"))
    exempt = [(s, s + len(b)) for s, b in (_author_blocks(text, AUTHOR_COMMANDS) if template.hides_authors or known_mode else named)]
    for m in re.finditer(r"\\thanks\s*\{", text):
        if not template.hides_authors or not any(s <= m.start() < s + len(b) for s, b in blocks):
            out.append(
                Finding("thanks", "warning", file, _line(text, m.start()), "\\thanks{...} (funding, affiliation or contact) gives the authors away")
            )
    return out, exempt


def _acknowledgements(file: str, text: str, template: Template) -> list[Finding]:
    advice = " or move them into the template's ack environment, which is hidden in review mode" if template.venue == "neurips" else ""
    msg = "acknowledgements in a submission (they name people, groups and grants): remove them until the camera-ready" + advice
    return [Finding("acknowledgements", "error", file, _line(text, m.start()), msg) for m in ACK_HEADING.finditer(text)]


def _emails(file: str, text: str, skip: Spans) -> list[Finding]:
    return [
        Finding("email", "error", file, _line(text, m.start()), f"an e-mail address in the text: {m.group(0)}")
        for m in EMAIL.finditer(text)
        if not _inside(m.start(), skip)
    ]


def _links(file: str, text: str, skip: Spans) -> list[Finding]:
    """Links to an account or a personal page that the text offers as the authors' own."""
    out = []
    for m in ACCOUNT_LINK.finditer(text):
        around = text[max(0, m.start() - 40) : m.end() + 40]
        if ANONYMISED.search(around) or _inside(m.start(), skip):
            continue
        sentence_start = max(0, text.rfind(". ", 0, m.start()), text.rfind("\n\n", 0, m.start()), m.start() - 160)
        before = text[sentence_start : m.start()]
        if not OWN.search(before + " " + text[m.end() : m.end() + 60]) and not OWN_LABEL.search(re.sub(r"https?://\S*$", "", before)):
            continue  # someone else's code or page, cited
        msg = f"a link to an account or a personal page: {m.group(0)} (use an anonymised copy, e.g. anonymous.4open.science)"
        out.append(Finding("account-link", "warning", file, _line(text, m.start()), msg))
    return out


def _phrases(file: str, text: str, skip: Spans) -> list[Finding]:
    """First-person self-citation and funding lines."""
    out = []
    for m in SELF_CITE.finditer(text):
        if not _inside(m.start(), skip):
            msg = f'"{m.group(0)}": citing your own work in the first person tells reviewers who you are; cite it in the third person'
            out.append(Finding("self-citation", "warning", file, _line(text, m.start()), msg))
    for m in FUNDING.finditer(text):
        if not _inside(m.start(), skip):
            out.append(Finding("funding", "warning", file, _line(text, m.start()), f'funding information in a submission: "{m.group(0)}"'))
    return out


def check(texts: dict[str, str], template: Template, mode: str = "submission") -> list[Finding]:
    """Findings for a project's texts (file -> text without comments). `mode` is "submission" (double-blind),
    "camera-ready" or "arxiv": only a submission must be anonymous."""
    if mode != "submission":
        return []
    out = _template_mode(template, template.file or next(iter(texts), ""))
    for file, text in texts.items():
        found, exempt = _authors(file, text, template)
        out += found
        # NeurIPS's ack environment is hidden by its template in review mode, with what is in it
        hidden = [(m.start(), text.find("\\end{ack}", m.start())) for m in NEURIPS_ACK.finditer(text)] if template.venue == "neurips" else []
        out += _acknowledgements(file, text, template)
        out += _emails(file, text, exempt + hidden)
        out += _links(file, text, hidden + exempt)
        out += _phrases(file, text, hidden)
    return out
