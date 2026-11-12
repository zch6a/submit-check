r"""Which venue's template a paper uses, and in which mode: whether the template itself hides the authors (review) or
prints them (final, camera-ready, preprint). Read from \documentclass and \usepackage options, and from the
switches some templates use instead (\iclrfinalcopy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PACKAGE = re.compile(r"\\(?:usepackage|documentclass|RequirePackage)\s*(?:\[([^\]\n]{0,500})\])?\s*\{([^}\n]{1,300})\}")
PASS_OPTIONS = re.compile(r"\\PassOptionsToPackage\s*\{([^}\n]{0,300})\}\s*\{([^}\n]{1,100})\}")


@dataclass
class Template:
    venue: str  # "neurips", "icml", "iclr", "cvpr", "acl", "eccv", "aaai", "" when unknown
    year: int | None
    package: str
    mode: str  # "review" (authors hidden by the template), "final", "preprint", or "" when unknown
    options: list[str]
    line: int
    pos: int = 0  # where the \usepackage is, in its file
    file: str = ""  # the file it is in (the main file, or one it \inputs)
    conditional: bool = False  # loaded inside \iftoggle / \if...\fi: which mode the PDF gets is not known from the source

    @property
    def hides_authors(self) -> bool:
        return self.mode == "review"


def _options(s: str | None) -> list[str]:
    return [o.strip() for o in (s or "").split(",") if o.strip()]


def _year(package: str, opts: list[str] | tuple[str, ...] = ()) -> int | None:
    """The year in the package's name (neurips_2025, icml2025, acl2019) or in a year= option (ECCV)."""
    for o in opts:
        m = re.fullmatch(r"year\s*=\s*(20\d{2})", o)
        if m:
            return int(m.group(1))
    m = re.search(r"(?<![\d=])(20\d{2}|\d{2})(?!\d)", package)
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

        spans = conditional_spans(text)
        t.conditional = any(s <= t.pos < e for s, e in spans)
        # \iclrfinalcopy behind a switch (\ifcamera\iclrfinalcopy\fi): the mode is not known from the source
        m = re.search(r"\\iclrfinalcopy\b", text)
        if t.venue == "iclr" and m and any(s <= m.start() < e for s, e in spans):
            t.conditional = True
    return t


def detect_project(texts: dict[str, str]) -> Template:
    """The template of a project: the first file (main file first, then what it \\inputs) that loads one."""
    for file, text in texts.items():
        t = detect(text)
        if t.venue:
            t.file = file
            return t
    return Template("", None, "", "", [], 0)


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
    # options given elsewhere: \PassOptionsToPackage{final}{neurips_2025}
    for po in PASS_OPTIONS.finditer(text):
        if any(n.strip() in names for n in po.group(2).split(",")):
            opts = opts + _options(po.group(1))
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
            return Template("eccv", _year(low, opts), name, "review" if "review" in opts else "final", opts, line, pos)
        if re.match(r"ijcai\d*$", low):
            # the IJCAI kit: whether it hides the authors by itself is not known here, so the names are checked
            return Template("ijcai", _year(low), name, "", opts, line, pos)
        if low == "acmart":
            # ACM's class (KDD, many ACM venues): `anonymous` hides the authors
            return Template("acm", None, name, "review" if "anonymous" in opts else "final", opts, line, pos)
        if low.startswith("aaai"):
            mode = "review" if ("submission" in opts or "anonymous" in opts) else "final"
            return Template("aaai", _year(low), name, mode, opts, line, pos)
    return None
