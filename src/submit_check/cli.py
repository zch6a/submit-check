"""submit-check on the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paper_proof.latex import find_main, read_project
from paper_proof.numbers import Finding
from paper_proof.report import use_color

from . import __version__, anonymity, arxivcheck, camera, leftovers, pdfcheck, rules, supplementary, templates
from .report import ORDER, list_venues, markdown, text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="submit-check",
        description="Check a LaTeX paper against a venue's submission rules before you submit: anonymity leaks, the "
        "template and its mode, required sections, page limit, PDF metadata and fonts, leftover notes.",
    )
    p.add_argument("--version", action="version", version=f"submit-check {__version__}")
    p.add_argument("paper", nargs="?", metavar="PAPER", help="the LaTeX project folder or its main .tex file (or only a PDF)")
    p.add_argument(
        "--venue", help=f"the rules to check against: {', '.join(sorted(rules.all_venues()))} (see --list-venues); default: from the template"
    )
    p.add_argument(
        "--mode",
        choices=["submission", "camera-ready", "arxiv"],
        default="submission",
        help="submission (double-blind, default), camera-ready, or arxiv (the source will be public)",
    )
    p.add_argument("--pdf", type=Path, help="the compiled PDF (default: the main file's .pdf, if there is one)")
    p.add_argument(
        "--supplementary",
        type=Path,
        action="append",
        default=[],
        metavar="ZIP_OR_FOLDER",
        help="supplementary material (a .zip or a folder; repeat for several) to check for what gives the authors away: "
        "names, e-mail addresses, user paths, .git, file metadata, secrets",
    )
    p.add_argument(
        "--author",
        action="append",
        default=[],
        metavar="NAME",
        help="an author's name to look for in the supplementary material (repeat for each; the paper's \\author block is read too)",
    )
    p.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="report format: text (default), json (every finding with file and line), md (a table for a pull request)",
    )
    p.add_argument("--fail-on", choices=["error", "warning", "never"], default="error", help="when to exit 1 (default: error)")
    p.add_argument(
        "--color", choices=["auto", "always", "never"], default="auto", help="colours in the text report (default: auto, only on a terminal)"
    )
    p.add_argument("--list-venues", action="store_true", help="list the venues with rules, and where each rule comes from")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_venues:
        print(list_venues())
        return 0
    if not args.paper and not args.supplementary:
        print("submit-check: give the paper's folder or main .tex file (or --list-venues)", file=sys.stderr)
        return 2
    for supp in args.supplementary:
        if not supp.exists():
            print(f"submit-check: {supp}: no such file or folder", file=sys.stderr)
            return 2
    if not args.paper:
        return _report(
            supp_findings(args, {}),
            {
                "paper": ", ".join(map(str, args.supplementary)),
                "venue": None,
                "template": None,
                "template_mode": None,
                "mode": args.mode,
                "pdf": None,
                "only_supplementary": True,
            },
            None,
            args,
        )
    path = Path(args.paper)
    if not path.exists():
        print(f"submit-check: {path}: no such file or folder", file=sys.stderr)
        return 2
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
        if "\\documentclass" not in next(iter(texts.values()), ""):
            findings.append(
                Finding(
                    "not-main-file",
                    "note",
                    main.name,
                    1,
                    "no \\documentclass: this is not the main file, so only it (and what it \\inputs) was checked; give the "
                    "project folder or its main .tex",
                )
            )
        root = proj.main.parent
        template = templates.detect_project(texts)
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
        if args.mode == "camera-ready":
            findings += camera.check(texts, template, root)
    if pdf is not None:
        if not pdf.is_file():
            print(f"submit-check: cannot read {pdf}", file=sys.stderr)
            return 2
        findings += pdfcheck.check(pdf, venue, args.mode)
        if args.mode == "camera-ready":
            findings += camera.pdf_check(pdf)
    findings += supp_findings(args, texts)
    header = {
        "paper": str(path),
        "venue": venue.id if venue else None,
        "template": template.package or None,
        "template_mode": template.mode or None,
        "mode": args.mode,
        "pdf": str(pdf) if pdf else None,
    }
    return _report(findings, header, venue, args)


def supp_findings(args: argparse.Namespace, texts: dict[str, str]) -> list[Finding]:
    """The supplementary material: everything for a submission; in another mode only secrets (nothing to hide then)."""
    out: list[Finding] = []
    names = list(dict.fromkeys(args.author + supplementary.names_from_paper(texts)))
    for supp in args.supplementary:
        found = supplementary.check(supp, names)
        if args.mode != "submission":
            found = [f for f in found if f.kind == "supp-secret"]
        out += found
    return out


def _report(findings: list[Finding], header: dict, venue, args: argparse.Namespace) -> int:
    findings.sort(key=lambda f: (ORDER.index(f.severity), f.file, f.line))
    if args.supplementary:
        header["supplementary"] = [str(s) for s in args.supplementary]
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


def main() -> None:
    # The reports hold non-ASCII text (names, zero-width spaces that break links in Markdown): a redirected stdout on
    # Windows (cp1252) must not crash on them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(run())
