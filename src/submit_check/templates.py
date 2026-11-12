r"""Which venue's template a paper uses, and in which mode: whether the template itself hides the authors (review) or
prints them (final, camera-ready, preprint). Read from \documentclass and \usepackage options, and from the
switches some templates use instead (\iclrfinalcopy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PACKAGE = re.compile(r"\\(?:usepackage|documentclass|RequirePackage)\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}")


@dataclass
class Template:
    venue: str  # "neurips", "icml", "iclr", "cvpr", "acl", "eccv", "aaai", "" when unknown
    year: int | None
    package: str
    mode: str  # "review" (authors hidden by the template), "final", "preprint", or "" when unknown
    options: list[str]
    line: int
    pos: int = 0  # where the \usepackage is, in the text
    conditional: bool = False  # loaded inside \iftoggle / \if...\fi: which mode the PDF gets is not known from the source

    @property
    def hides_authors(self) -> bool:
        return self.mode == "review"


def _options(s: str | None) -> list[str]:
    return [o.strip() for o in (s or "").split(",") if o.strip()]


def _year(package: str) -> int | None:
    m = re.search(r"(20\d{2}|\d{2})(?!\d)", package)
    if not m:
        return None
    y = int(m.group(1))
    return y if y > 2000 else 2000 + y


def detect(text: str) -> Template:
    r"""The template of the main file's text (comments already removed).

    >>> detect(r"\documentclass{article}\usepackage{neurips_2025}").mode
    'review'
    >>> t = detect(r"\usepackage[final]{neurips_2025}"); (t.venue, t.year, t.mode)
    ('neurips', 2025, 'final')
    >>> detect(r"\usepackage[accepted]{icml2025}").mode, detect(r"\usepackage{icml2025}").mode
    ('final', 'review')
    >>> detect(r"\usepackage{iclr2026_conference}\iclrfinalcopy").mode
    'final'
    >>> detect(r"\usepackage[review]{acl}").mode, detect(r"\usepackage{acl}").mode
    ('review', 'final')
    >>> detect(r"\usepackage[review,year=2024,ID=1234]{eccv}").venue
    'eccv'
    """
    t = _detect(text)
    if t.venue:
        from paper_proof.numbers import conditional_spans

        t.conditional = any(s <= t.pos < e for s, e in conditional_spans(text))
    return t


def _detect(text: str) -> Template:
    for m in PACKAGE.finditer(text):
        found = _family(text, m)
        if found:
            return found
    return Template("", None, "", "", [], 0)


def _family(text: str, m: re.Match) -> Template | None:
    """The template one \\usepackage / \\documentclass loads, if it is a venue's."""
    opts, names = _options(m.group(1)), [n.strip() for n in m.group(2).split(",")]
    line, pos = text.count("\n", 0, m.start()) + 1, m.start()
    for name in names:
        low = name.lower()
        if low.startswith(("neurips", "nips")):
            mode = "final" if "final" in opts else "preprint" if "preprint" in opts else "review"
            return Template("neurips", _year(low), name, mode, opts, line, pos)
        if low.startswith("icml"):
            return Template("icml", _year(low), name, "final" if "accepted" in opts else "review", opts, line, pos)
        if low.startswith("iclr"):
            final = bool(re.search(r"\\iclrfinalcopy\b", text))
            return Template("iclr", _year(low), name, "final" if final else "review", opts, line, pos)
        if re.match(r"(cvpr|iccv|wacv)\d*$", low):
            # the CVF author kit: [review] for submission, [final] (or nothing) for the camera-ready
            return Template(low[:4], _year(low), name, "review" if "review" in opts else "final", opts, line, pos)
        if low.startswith(("acl", "naacl", "emnlp")):
            return Template("acl", _year(low), name, "review" if "review" in opts else "final", opts, line, pos)
        if low.startswith("eccv"):
            return Template("eccv", _year(low) or _year(",".join(opts)), name, "review" if "review" in opts else "final", opts, line, pos)
        if low.startswith("aaai"):
            mode = "review" if ("submission" in opts or "anonymous" in opts) else "final"
            return Template("aaai", _year(low), name, mode, opts, line, pos)
    return None
