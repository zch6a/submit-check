"""The reports: for the terminal, as Markdown (a pull request, a job summary). JSON is built in cli.py."""

from __future__ import annotations

from collections import Counter

from paper_proof.numbers import Finding
from paper_proof.report import _code, _md, visible

from . import __version__, rules

ORDER = ["error", "warning", "note"]


COLOR = {"error": "31;1", "warning": "33", "note": "2"}


def list_venues() -> str:
    lines = []
    for v in sorted(rules.all_venues().values(), key=lambda v: v.id):
        pages = f"{v.pages_submission} pages" + (f" ({v.pages_camera_ready} camera-ready)" if v.pages_camera_ready else "")
        req = "; requires " + ", ".join(r.what for r in v.required) if v.required else ""
        lines.append(f"{v.id:12} {v.name}: {pages}, not counting {', '.join(v.not_counted)}{req}\n{'':13}{v.source} (read {v.verified})")
    return "\n".join(lines)


def _summary(findings: list[Finding]) -> str:
    c = Counter(f.severity for f in findings)
    parts = [f"{c[k]} {k.upper() if k != 'note' else k}{'S' if k != 'note' and c[k] > 1 else ''}" for k in ORDER if c[k]]
    return ", ".join(parts) or "nothing found"


def text(findings: list[Finding], header: dict, venue, color: bool) -> str:
    paint = (lambda code, s: f"\x1b[{code}m{s}\x1b[0m") if color else (lambda code, s: s)
    what = f"{venue.name} rules" if venue else "no venue rules (pass --venue)"
    tmpl = f"template {header['template']} ({header['template_mode']} mode)" if header["template"] else "no known template"
    out = [f"submit-check {__version__} · {visible(header['paper'])}: {header['mode']}, {what}, {tmpl}", ""]
    for f in findings:
        where = f"{visible(f.file)}:{f.line}" if f.line else visible(f.file)
        out.append(f"{paint(COLOR[f.severity], f.severity.upper().ljust(8) if f.severity != 'note' else 'note    ')} {where}  {visible(f.message)}")
    if findings:
        out.append("")
    out.append("Summary: " + _summary(findings))
    return "\n".join(out)


def markdown(findings: list[Finding], header: dict, venue) -> str:
    out = [f"### submit-check: {_md(header['mode'])} against {_md(venue.name) if venue else 'no venue rules'}", "", f"**{_summary(findings)}**"]
    if findings:
        out += ["", "| | Where | Found |", "|---|---|---|"]
        out += [f"| {f.severity.upper()} | {_code(f'{f.file}:{f.line}')} | {_md(f.message)} |" for f in findings]
    return "\n".join(out)
