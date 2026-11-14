r"""A camera-ready (`--mode camera-ready`): what the review version needed and the published one must not keep.

- the author block still a placeholder ("Anonymous Authors", "Paper ID 1234");
- links still pointing to the anonymised copy (anonymous.4open.science, "link removed for review");
- your own work still cited as "Anonymous" (in the text or the .bib);
- "Under review", "Submitted to", "Anonymous submission" left in a header or the text;
- line numbers (`\linenumbers`) and `draft` mode (it leaves figures out);
- (the PDF) no title in its metadata.

The template's own review mode, the page limit with the extra page, the required sections (the NeurIPS checklist stays
in the camera-ready) and the PDF's fonts are checked as for a submission.
"""

from __future__ import annotations

import re
from pathlib import Path

from paper_proof.numbers import Finding

from .anonymity import _author_blocks, _real_names
from .templates import Template

ANON_LINK = re.compile(
    r"anonymous\.4open\.science[^\s}]*|anonymous\.github\.io[^\s}]*|"
    r"\b(?:link|url|code|repository)\s+(?:removed|hidden|omitted|withheld|redacted|anonymi[sz]ed)\s+(?:for|during)\s+(?:the\s+)?(?:review|submission|anonymity)\b|"
    r"\b(?:will\s+be\s+(?:released|provided|made\s+available|added)|available)\s+(?:after|upon)\s+(?:the\s+)?(?:review|acceptance|publication)\b",
    re.I,
)
ANON_CITE_TEXT = re.compile(r"\bAnonymous\s*(?:et\s+al\.?\s*)?[,~]?\s*\(?(?:19|20)\d{2}[a-z]?\)?|\[\s*Anonymous\s*\]", re.I)
ANON_BIB = re.compile(r"\bauthor\s*=\s*[{\"]\s*\{?\s*Anonymous\b", re.I)
UNDER_REVIEW = re.compile(
    r"\bunder\s+review\b|\bsubmitted\s+to\s+(?:the\s+)?(?:[\w-]+\s+){0,6}?(?:conference|workshop|journal|NeurIPS|ICML|ICLR|ACL|EMNLP|CVPR|AAAI|IJCAI|KDD)\b|"
    r"\banonymous\s+(?:submission|authors?)\b|\bpaper\s+ID\s*[:#]?\s*\d+|\bdo\s+not\s+distribute\b",
    re.I,
)
# loading lineno numbers nothing by itself (papers keep it with "% \\linenumbers"): \\linenumbers does
LINENO = re.compile(r"\\linenumbers\b")
DRAFT = re.compile(r"\\documentclass\s*\[[^\]\n]*\bdraft\b[^\]\n]*\]")


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check(texts: dict[str, str], template: Template, root: Path | None = None) -> list[Finding]:
    """Findings for a camera-ready's texts (file -> text without comments); `root` to read the .bib files too."""
    out: list[Finding] = []
    blocks = [(f, t, s, b) for f, t in texts.items() for s, b in _author_blocks(t)]
    # \icmlauthor{Name}{key}: the affiliation keys are blocks too, so a name is two words starting with capitals
    if blocks and not any(_real_names(b) and re.search(r"[A-Z][\w'.-]*(?:\s|~|\\[ ,])+[A-Z]", b) for _, _, _, b in blocks):
        f, t, s, _ = blocks[0]
        out.append(Finding("cr-authors", "error", f, _line(t, s), "the author block is still a placeholder: put the authors' names in"))
    elif not blocks and not template.venue:
        out.append(Finding("cr-authors", "warning", next(iter(texts), ""), 1, "no \\author block found: a camera-ready names its authors"))
    for file, text in texts.items():
        for m in ANON_LINK.finditer(text):
            msg = f'"{m.group(0)[:80]}": the review version\'s placeholder; link the real code or page now'
            out.append(Finding("cr-anonymous-link", "warning", file, _line(text, m.start()), msg))
        for m in ANON_CITE_TEXT.finditer(text):
            out.append(Finding("cr-anonymous-cite", "warning", file, _line(text, m.start()), f'"{m.group(0)}": cite your own work by name now'))
        for m in UNDER_REVIEW.finditer(text):
            # the template's own words in a header are reported as its mode; these are in the paper's text
            out.append(Finding("cr-under-review", "warning", file, _line(text, m.start()), f'"{m.group(0)}" in a camera-ready'))
        for m in LINENO.finditer(text):
            out.append(
                Finding(
                    "cr-line-numbers",
                    "warning",
                    file,
                    _line(text, m.start()),
                    "line numbers are on (\\linenumbers): turn them off for the camera-ready",
                )
            )
        for m in DRAFT.finditer(text):
            out.append(
                Finding("cr-draft", "warning", file, _line(text, m.start()), "draft mode: figures print as empty boxes and overfull lines are marked")
            )
    if root is not None:
        cited = {
            k.strip() for t in texts.values() for g in re.findall(r"\\\w*cite\w*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}", t) for k in g.split(",")
        }
        for bib in sorted(root.rglob("*.bib"))[:50]:
            try:
                text = bib.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in ANON_BIB.finditer(text):
                head = re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", text[: m.start()])
                if head and head[-1] not in cited and "*" not in cited:
                    continue  # an entry the paper does not cite never prints
                rel = bib.relative_to(root).as_posix()
                out.append(
                    Finding(
                        "cr-anonymous-cite",
                        "warning",
                        rel,
                        _line(text, m.start()),
                        "a reference with author Anonymous (a paper under review when cited, or your own): give its authors and venue now",
                    )
                )
    return out


def pdf_check(pdf: Path) -> list[Finding]:
    """The camera-ready PDF's metadata: a title (indexers and screen readers use it)."""
    try:
        from pypdf import PdfReader

        meta: dict = PdfReader(str(pdf)).metadata or {}
        title = str(meta.get("/Title", "") or "").strip()
    except Exception:
        return []
    if not title or re.fullmatch(r"(?:untitled|main|paper)(?:\.\w+)?", title, re.I):
        return [Finding("cr-pdf-title", "note", pdf.name, 0, "the PDF has no title in its metadata (set pdftitle in \\hypersetup)")]
    return []
