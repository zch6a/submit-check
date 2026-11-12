"""submit-check on the command line."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from paper_proof.latex import find_main, read_project
from paper_proof.numbers import Finding
from paper_proof.report import _code, _md, use_color, visible

from . import __version__, anonymity, arxivcheck, leftovers, pdfcheck, rules, templates

ORDER = ["error", "warning", "note"]
COLOR = {"error": "31;1", "warning": "33", "note": "2"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="submit-check",
        description="Check a LaTeX paper against a venue's submission rules before you submit: anonymity leaks, the "
        "template and its mode, required sections, page limit, PDF metadata and fonts, leftover notes.",
    )
    p.add_argument("--version", action="version", version=f"submit-check {__version__}")
    p.add_argument("paper", nargs="?", metavar="PAPER", help="the LaTeX project folder or its main .tex file (or only a PDF)")
    p.add_argument("--venue", help="the rules to check against (see --list-venues); default: from the template")
    p.add_argument(
        "--mode",
        choices=["submission", "camera-ready", "arxiv"],
        default="submission",
        help="submission (double-blind, default), camera-ready, or arxiv (the source will be public)",
    )
    p.add_argument("--pdf", type=Path, help="the compiled PDF (default: the main file's .pdf, if there is one)")
    p.add_argument("--format", choices=["text", "json", "md"], default="text")
    p.add_argument("--fail-on", choices=["error", "warning", "never"], default="error", help="when to exit 1 (default: error)")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--list-venues", action="store_true", help="list the venues with rules, and where each rule comes from")
    return p


def list_venues() -> str:
    lines = []
    for v in sorted(rules.all_venues().values(), key=lambda v: v.id):
        pages = f"{v.pages_submission} pages" + (f" ({v.pages_camera_ready} camera-ready)" if v.pages_camera_ready else "")
        req = "; requires " + ", ".join(r.what for r in v.required) if v.required else ""
        lines.append(f"{v.id:12} {v.name}: {pages}, not counting {', '.join(v.not_counted)}{req}\n{'':13}{v.source} (read {v.verified})")
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_venues:
        print(list_venues())
        return 0
    if not args.paper:
        print("submit-check: give the paper's folder or main .tex file (or --list-venues)", file=sys.stderr)
        return 2
    path = Path(args.paper)
    findings: list[Finding] = []
    texts: dict[str, str] = {}
    template = templates.detect("")
    pdf = args.pdf
    root = path if path.is_dir() else path.parent
    if path.suffix.lower() == ".pdf":
        pdf, main = path, None
    else:
        main = find_main(path) if path.is_dir() else path
        if main is None or not main.is_file():
            print(f"submit-check: {path}: no main .tex file (one with \\documentclass and \\begin{{document}})", file=sys.stderr)
            return 2
        proj = read_project(main)
        texts = proj.texts
        root = proj.main.parent
        template = templates.detect("\n".join(texts.values()))
        if pdf is None and main.with_suffix(".pdf").is_file():
            pdf = main.with_suffix(".pdf")
    try:
        venue, notes = rules.pick(args.venue, template)
    except KeyError as e:
        print(f"submit-check: {e.args[0]}", file=sys.stderr)
        return 2
    main_name = next(iter(texts), path.name)
    findings += [Finding(n.kind, n.severity, n.file or main_name, n.line, n.message) for n in notes]
    if texts:
        findings += anonymity.check(texts, template, args.mode)
        findings += leftovers.check(texts)
        if venue and args.mode != "arxiv":  # an arXiv version follows arXiv's rules, not the venue's
            found = rules.check(texts, venue, template, args.mode)
            if notes:
                # The rules are another year's (the template's family, newest rules): the year is already explained,
                # and a section that year requires may not have been required when the paper was written.
                found = [
                    Finding(f.kind, "note", f.file, f.line, f.message + " (in the newer rules)") if f.kind == "required-section" else f
                    for f in found
                    if f.kind != "template-year"
                ]
            findings += found
        if args.mode == "arxiv":
            findings += arxivcheck.check(proj.files, root)
    if pdf is not None:
        if not pdf.is_file():
            print(f"submit-check: cannot read {pdf}", file=sys.stderr)
            return 2
        findings += pdfcheck.check(pdf, venue, args.mode)
    findings.sort(key=lambda f: (ORDER.index(f.severity), f.file, f.line))
    header = {
        "paper": str(path),
        "venue": venue.id if venue else None,
        "template": template.package or None,
        "template_mode": template.mode or None,
        "mode": args.mode,
        "pdf": str(pdf) if pdf else None,
    }
    if args.format == "json":
        print(
            json.dumps(
                {"tool": "submit-check", "version": __version__, **header, "findings": [f.to_dict() for f in findings]}, indent=2, ensure_ascii=False
            )
        )
    elif args.format == "md":
        print(markdown(findings, header, venue))
    else:
        print(text(findings, header, venue, use_color(choice=args.color)))
    if args.fail_on == "never":
        return 0
    bad = {"error"} if args.fail_on == "error" else {"error", "warning"}
    return 1 if any(f.severity in bad for f in findings) else 0


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


def main() -> None:
    sys.exit(run())
