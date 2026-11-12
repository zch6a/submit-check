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
    for m in PACKAGE.finditer(text):
        opts, names = _options(m.group(1)), [n.strip() for n in m.group(2).split(",")]
        line = text.count("\n", 0, m.start()) + 1
        for name in names:
            low = name.lower()
            if low.startswith("neurips") or low.startswith("nips"):
                mode = "final" if "final" in opts else "preprint" if "preprint" in opts else "review"
                return Template("neurips", _year(low), name, mode, opts, line)
            if low.startswith("icml"):
                return Template("icml", _year(low), name, "final" if "accepted" in opts else "review", opts, line)
            if low.startswith("iclr"):
                final = bool(re.search(r"\\iclrfinalcopy\b", text))
                return Template("iclr", _year(low), name, "final" if final else "review", opts, line)
            if low in ("cvpr", "iccv", "wacv") or re.match(r"(cvpr|iccv|wacv)\d*$", low):
                mode = "review" if "review" in opts else "final" if ("final" in opts or "camera" in opts) else "final"
                return Template("cvpr" if low.startswith("cvpr") else low[:4], _year(low), name, mode, opts, line)
            if low in ("acl", "acl2023", "acl_natbib", "naacl", "emnlp") or low.startswith("acl"):
                return Template("acl", _year(low), name, "review" if "review" in opts else "final", opts, line)
            if low.startswith("eccv"):
                return Template("eccv", _year(low) or _year(",".join(opts)), name, "review" if "review" in opts else "final", opts, line)
            if low.startswith("aaai"):
                return Template("aaai", _year(low), name, "review" if ("submission" in opts or "anonymous" in opts) else "final", opts, line)
    return Template("", None, "", "", [], 0)
