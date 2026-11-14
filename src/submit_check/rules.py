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
    forbidden: list[Required] = field(default_factory=list)  # what must not be there (ECCV: an appendix)
    paper: str = ""
    no_type3_fonts: bool = False
    policy: dict[str, str] = field(default_factory=dict)  # llm, llm_disclose, supplementary, rebuttal: what the page says

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
        forbidden=[Required(**r) for r in data.get("forbidden", [])],
        paper=data.get("pdf", {}).get("paper", ""),
        no_type3_fonts=data.get("pdf", {}).get("no_type3_fonts", False),
        policy={k: str(v) for k, v in data.get("policy", {}).items() if str(v)},
    )


def all_venues() -> dict[str, Venue]:
    """Every venue in rules/, by id.

    >>> sorted(all_venues())[:3]
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
    if template.venue == "acm":
        # ACM's class serves dozens of venues: which rules apply cannot be told from it
        notes.append(
            Finding("rules-year", "note", template.file, template.line, "an ACM template (acmart): pass --venue (e.g. kdd2026) to check its rules")
        )
        return None, notes
    same = [v for v in venues.values() if v.template == template.venue]
    if not same:
        return None, notes
    # Rules for that year; or rules with no year (ACL Rolling Review: ACL, EMNLP, NAACL), which hold for a recent template
    # (or one with no year); an older template (acl2019) may predate them, as with any other year's rules.
    exact = [v for v in same if v.year == template.year] or [
        v for v in same if v.year is None and (template.year is None or template.year >= int(v.verified[:4]) - 1)
    ]
    if exact:
        return exact[0], notes
    newest = max(same, key=lambda v: v.year or 0)
    notes.append(
        Finding(
            "rules-year",
            "note",
            template.file,
            template.line,
            f"no rules for {template.package}; checked against {newest.name} ({newest.source}): pass --venue if that is wrong",
        )
    )
    return newest, notes


HEADING = re.compile(r"\\(?:section|subsection|paragraph|chapter)\*?\s*(?:\[[^\]\n]{0,200}\])?\s*\{([^}\n]{0,300})\}")


def check(texts: dict[str, str], venue: Venue, template: Template, mode: str) -> list[Finding]:
    out: list[Finding] = []
    main_file = template.file or next(iter(texts), "")
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
    if mode == "camera-ready" and template.hides_authors and not template.conditional:
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
    if mode == "submission":
        out += policy_notes(texts, venue, main_file, headings)
    for r in venue.forbidden:
        if mode not in r.modes:
            continue
        for file, text in texts.items():
            m = re.search(r.pattern, text, re.I)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                out.append(Finding("forbidden", r.severity, file, line, f"{venue.name} does not allow {r.what} ({venue.source})"))
                break
    return out


def policy_notes(texts: dict[str, str], venue: Venue, main_file: str, headings: str) -> list[Finding]:
    """What the venue says about LLM use, where the paper can act on it (notes: whether LLMs were used, the tool cannot know)."""
    out: list[Finding] = []
    where = venue.policy.get("llm_disclose", "")
    if where and "section" in where:
        if not re.search(r"\bLLMs?\b|language\s+models?\s+usage|use\s+of\s+(?:large\s+language\s+models|LLMs|AI)", headings, re.I):
            out.append(Finding("llm-policy", "note", main_file, 1, f"{venue.name}: if LLMs were used significantly, describe it in {where}; "
                                                                   f"not disclosing it can lead to desk rejection ({venue.source})"))  # fmt: skip
    elif where:
        out.append(
            Finding("llm-policy", "note", main_file, 1, f"{venue.name}: any use of LLMs or generative AI is disclosed in {where} ({venue.source})")
        )
    if "non-existent" in venue.policy.get("llm", ""):
        out.append(Finding("llm-policy", "note", main_file, 1, f"{venue.name} rejects papers that cite non-existent material: check the references "
                                                               f"(paper-proof does) ({venue.source})"))  # fmt: skip
    return out
