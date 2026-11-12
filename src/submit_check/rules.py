"""Venue rules, one TOML file per venue and year in rules/ (each value with the official page it comes from), and the
checks that need them: the template matches the venue, the required sections are there."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from importlib import resources

from paper_proof.numbers import Finding

from .templates import Template

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass
class Required:
    what: str
    pattern: str
    heading: bool = False
    modes: list[str] = field(default_factory=lambda: ["submission", "camera-ready"])
    severity: str = "error"


@dataclass
class Venue:
    id: str
    name: str
    source: str
    verified: str
    template: str
    pages_submission: int | None
    pages_camera_ready: int | None
    not_counted: list[str]
    anonymous: bool
    required: list[Required]
    paper: str = ""
    no_type3_fonts: bool = False

    @property
    def year(self) -> int | None:
        m = re.search(r"(20\d{2})", self.id)
        return int(m.group(1)) if m else None


def _venue(data: dict) -> Venue:
    v, pages = data["venue"], data.get("pages", {})
    return Venue(
        id=v["id"],
        name=v["name"],
        source=v["source"],
        verified=v["verified"],
        template=v.get("template", ""),
        pages_submission=pages.get("submission"),
        pages_camera_ready=pages.get("camera_ready"),
        not_counted=pages.get("not_counted", []),
        anonymous=data.get("anonymity", {}).get("required", True),
        required=[Required(**r) for r in data.get("required", [])],
        paper=data.get("pdf", {}).get("paper", ""),
        no_type3_fonts=data.get("pdf", {}).get("no_type3_fonts", False),
    )


def all_venues() -> dict[str, Venue]:
    """>>> sorted(all_venues())[:3]
    ['aaai2026', 'acl-arr', 'cvpr2026']
    """
    out = {}
    for f in resources.files("submit_check").joinpath("rules").iterdir():
        if f.name.endswith(".toml"):
            v = _venue(tomllib.loads(f.read_text(encoding="utf-8")))
            out[v.id] = v
    return out


def pick(venue_id: str | None, template: Template) -> tuple[Venue | None, list[Finding]]:
    """The venue to check against: the one asked for, else the template's (its year, or the newest we have)."""
    venues = all_venues()
    notes: list[Finding] = []
    if venue_id:
        if venue_id not in venues:
            raise KeyError(f"no rules for {venue_id!r}; known: {', '.join(sorted(venues))}")
        return venues[venue_id], notes
    same = [v for v in venues.values() if v.template == template.venue]
    if not same:
        return None, notes
    exact = [v for v in same if v.year == template.year]
    if exact:
        return exact[0], notes
    newest = max(same, key=lambda v: v.year or 0)
    notes.append(
        Finding(
            "rules-year",
            "note",
            "",
            template.line,
            f"no rules for {template.package}; checked against {newest.name} ({newest.source}): pass --venue if that is wrong",
        )
    )
    return newest, notes


HEADING = re.compile(r"\\(?:section|subsection|paragraph|chapter)\*?\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


def check(texts: dict[str, str], venue: Venue, template: Template, mode: str) -> list[Finding]:
    out: list[Finding] = []
    main_file = next(iter(texts), "")
    if venue.template and template.venue and template.venue != venue.template:
        out.append(
            Finding(
                "wrong-template", "error", main_file, template.line, f"{venue.name} requires its own template, but the paper uses {template.package}"
            )
        )
    elif venue.template and not template.venue:
        out.append(Finding("wrong-template", "warning", main_file, 1, f"no {venue.name} template found (the venue requires its own)"))
    if template.year and venue.year and template.year != venue.year and template.venue == venue.template:
        out.append(
            Finding("template-year", "warning", main_file, template.line, f"the template is {template.package}, the rules are for {venue.name}")
        )
    if mode == "camera-ready" and template.hides_authors:
        out.append(
            Finding("template-mode", "error", main_file, template.line, f"a camera-ready in review mode: {template.package} hides the authors")
        )
    headings = " | ".join(h for t in texts.values() for h in HEADING.findall(t))
    files = " ".join(texts)
    everything = "\n".join(texts.values())
    for r in venue.required:
        if mode not in r.modes:
            continue
        where = headings if r.heading else everything + " " + files
        if not re.search(r.pattern, where, re.I):
            out.append(
                Finding("required-section", r.severity, main_file, 1, f"{venue.name} requires {r.what}, and it is not in the paper ({venue.source})")
            )
    return out
