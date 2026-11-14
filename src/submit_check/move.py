r"""submit-check move: what changes when a paper moves to another venue (a rejected paper resubmitted elsewhere).

    submit-check move paper/ --to icml2025

It reads the paper and the target venue's rules and lists, each with its file and line:

- the template to swap (the line that loads the current one, and the target's family and official page);
- commands only the current template defines (\icmlauthor, \iclrfinalcopy, \cvprPaperID, \institute, ...): they
  stop compiling, or print nothing, under the target's template;
- one column to two (or back): figures and tables set to \textwidth inside a one-column-wide float, figure* that
  becomes an ordinary figure;
- sections the target requires that the paper lacks (ICML's Impact Statement, ACL's Limitations), and sections only
  the old venue asked for (the NeurIPS checklist);
- the bibliography style of the old kit;
- the page count of the compiled PDF against the target's limit (the new layout changes it: a first estimate).

Nothing is changed in the files; the report is the to-do list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import pdfcheck
from .rules import Venue
from .templates import Template

ONE_COLUMN = {"neurips", "iclr", "eccv"}
TWO_COLUMN = {"icml", "cvpr", "iccv", "wacv", "acl", "aaai", "ijcai", "acm"}
FAMILY_NAME = {"neurips": "NeurIPS", "iclr": "ICLR", "icml": "ICML", "cvpr": "CVPR", "iccv": "ICCV", "wacv": "WACV", "acl": "ACL",
               "eccv": "ECCV (llncs)", "aaai": "AAAI", "ijcai": "IJCAI", "acm": "ACM (acmart)"}  # fmt: skip
# Commands (and environments) a template family defines and others do not.
OWN_COMMANDS: dict[str, list[str]] = {
    "icml": [r"\\icmltitle\b", r"\\icmltitlerunning\b", r"\\icmlauthor\b", r"\\begin\{icmlauthorlist\}", r"\\icmlaffiliation\b",
             r"\\icmlcorrespondingauthor\b", r"\\icmlsetsymbol\b", r"\\icmlkeywords\b", r"\\icmlEqualContribution\b",
             r"\\printAffiliationsAndNotice\b", r"\\twocolumn\["],
    "iclr": [r"\\iclrfinalcopy\b"],
    "neurips": [r"\\begin\{ack\}"],
    "cvpr": [r"\\cvprPaperID\b", r"\\def\\confName\b", r"\\def\\confYear\b", r"\\cvprfinalcopy\b", r"\\def\\paperID\b"],
    "acl": [r"\\aclfinalcopy\b", r"\\aclpaperid\b"],
    "aaai": [r"\\nocopyright\b", r"\\affiliations\b", r"\\pdfinfo\b"],
    "ijcai": [r"\\ijcaifinalcopy\b"],
    "eccv": [r"\\institute\b", r"\\titlerunning\b", r"\\authorrunning\b", r"\\orcidID\b"],
    "acm": [r"\\affiliation\b", r"\\institution\b", r"\\acmConference\b", r"\\ccsdesc\b", r"\\settopmatter\b", r"\\acmYear\b",
            r"\\begin\{CCSXML\}", r"\\keywords\b"],
}  # fmt: skip
BIBSTYLE_KIT = {"icml": r"icml\d*", "iclr": r"iclr\d*_conference", "aaai": r"aaai\d*", "acl": r"acl_natbib", "eccv": r"splncs\d*",
                "acm": r"ACM-Reference-Format", "cvpr": r"ieee(?:nat)?_fullname", "ijcai": r"named"}  # fmt: skip
WIDE = re.compile(r"\\begin\{(figure|table)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}", re.S)
STARRED = re.compile(r"\\begin\{(figure|table)\*\}")


@dataclass
class Item:
    what: str  # template, commands, columns, sections, bibliography, pages
    message: str
    file: str = ""
    line: int = 0


@dataclass
class MoveReport:
    source: str
    target: str
    items: list[Item] = field(default_factory=list)

    def text(self) -> str:
        out = [f"submit-check move: from {self.source} to {self.target}", ""]
        titles = {"template": "Template", "commands": "Commands of the old template", "columns": "Columns",
                  "sections": "Sections", "bibliography": "Bibliography", "pages": "Pages"}  # fmt: skip
        for key, title in titles.items():
            items = [i for i in self.items if i.what == key]
            if not items:
                continue
            out.append(title)
            out += [f"  {(i.file + ':' + str(i.line) + '  ') if i.file and i.line else ''}{i.message}" for i in items]
            out.append("")
        if not self.items:
            out.append("Nothing found to change.")
        return "\n".join(out).rstrip() + "\n"

    def json(self) -> dict:
        return {"source": self.source, "target": self.target, "items": [i.__dict__ for i in self.items]}


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check(texts: dict[str, str], template: Template, target: Venue, source: Venue | None = None, pdf: Path | None = None) -> MoveReport:
    fam, tfam = template.venue, target.template
    r = MoveReport(FAMILY_NAME.get(fam, template.package or "no known template"), target.name)
    # the template
    if fam and fam == tfam:
        name = FAMILY_NAME.get(tfam, tfam)
        r.items.append(Item("template", f"already the {name} template ({template.package}): check the year against {target.name}",
                            template.file, template.line))  # fmt: skip
    else:
        where = f"{template.package}" if template.package else "no venue template"
        r.items.append(Item("template", f"replace {where} with the {FAMILY_NAME.get(tfam, tfam)} template in its submission mode "
                                        f"(the kit is linked from {target.source})", template.file, template.line))  # fmt: skip
    # commands of the old template
    if fam and fam != tfam:
        for file, text in texts.items():
            for pat in OWN_COMMANDS.get(fam, []):
                for m in re.finditer(pat, text):
                    name = m.group(0)
                    hint = _hint(name, tfam)
                    what = (
                        "part of the title block the ICML template expects"
                        if name == "\\twocolumn["
                        else f"defined by the {FAMILY_NAME[fam]} template only"
                    )
                    r.items.append(Item("commands", f"{name}: {what}{hint}", file, _line(text, m.start())))
    r.items.sort(key=lambda i: (i.what != "template", i.file, i.line))
    # columns
    old_cols = 1 if fam in ONE_COLUMN else 2 if fam in TWO_COLUMN else 0
    new_cols = 1 if tfam in ONE_COLUMN else 2 if tfam in TWO_COLUMN else 0
    if old_cols == 1 and new_cols == 2:
        for file, text in texts.items():
            for m in WIDE.finditer(text):
                if re.search(r"width\s*=\s*(?:0?\.\d+|1(?:\.0)?)?\s*\\textwidth|\\resizebox\s*\{\s*(?:0?\.\d+)?\s*\\textwidth", m.group(2)):
                    r.items.append(Item("columns", f"a {m.group(1)} set to \\textwidth: in two columns it overflows its column; "
                                                   f"make it {m.group(1)}* (both columns) or \\columnwidth",
                                        file, _line(text, m.start())))  # fmt: skip
        r.items.append(Item("columns", "one column becomes two: every figure's text prints smaller (fig-check measures it)"))
    elif old_cols == 2 and new_cols == 1:
        for file, text in texts.items():
            for m in STARRED.finditer(text):
                r.items.append(Item("columns", f"{m.group(1)}* spans both columns; in one column it is an ordinary {m.group(1)}",
                                    file, _line(text, m.start())))  # fmt: skip
    r.items = _per_file(r.items)
    # sections
    everything = "\n".join(texts.values())
    headings = " | ".join(re.findall(r"\\(?:section|subsection|paragraph)\*?\s*\{([^}\n]{0,300})\}", everything))
    for req in target.required:
        if "submission" not in req.modes:
            continue
        where = headings if req.heading else everything + " " + " ".join(texts)
        if not re.search(req.pattern, where, re.I):
            r.items.append(Item("sections", f"add {req.what}: {target.name} requires it ({target.source})"))
    if source:
        for req in source.required:
            where = headings if req.heading else everything + " " + " ".join(texts)
            asked = any(re.search(req.pattern, x.pattern, re.I) or x.what == req.what for x in target.required)
            if re.search(req.pattern, where, re.I) and not asked:
                r.items.append(Item("sections", f"{req.what}: {source.name} asked for it, {target.name} does not (keep it only if it fits the "
                                                f"page limit and the venue's rules)"))  # fmt: skip
    for fb in target.forbidden:
        for file, text in texts.items():
            hit = re.search(fb.pattern, text, re.I)
            if hit:
                r.items.append(Item("sections", f"{target.name} does not allow {fb.what} ({target.source})", file, _line(text, hit.start())))
                break
    # bibliography style
    for file, text in texts.items():
        for m in re.finditer(r"\\bibliographystyle\s*\{([^}]+)\}", text):
            style = m.group(1).strip()
            kit = next((f for f, rx in BIBSTYLE_KIT.items() if re.fullmatch(rx, style)), None)
            if kit and kit != tfam:
                r.items.append(Item("bibliography", f"\\bibliographystyle{{{style}}} comes with the {FAMILY_NAME[kit]} kit: use the style in "
                                                    f"the {FAMILY_NAME.get(tfam, tfam)} kit", file, _line(text, m.start())))  # fmt: skip
    # pages
    if pdf is not None and target.pages_submission:
        try:
            reader = pdfcheck._reader(pdf)
            pages = [(p.extract_text() or "") for p in reader.pages]
            used, _, _ = pdfcheck.content_pages(pages, target.not_counted)
        except Exception:  # noqa: BLE001 - a PDF that cannot be read leaves the page count out
            used = None
        if used is not None:
            verdict = "over" if used > target.pages_submission else "within"
            r.items.append(Item("pages", f"{used} pages of content in {pdf.name} as it is now, {verdict} {target.name}'s "
                                         f"{target.pages_submission}; the new template's page size, margins and columns change "
                                         f"the count: compile it to know"))  # fmt: skip
    return r


def _hint(name: str, target: str) -> str:
    """What to write instead, where it is simple."""
    if (
        name.startswith(("\\icmlauthor", "\\begin{icmlauthorlist}", "\\icmlaffiliation", "\\icmlcorrespondingauthor", "\\institute", "\\affiliation"))
        and name != "\\icmlauthorlist"
    ):
        return ": move the authors into \\author{...} as the target's template asks"
    if name == "\\icmltitlerunning":
        return ": delete it (or use the target template's running-title command, if it has one)"
    if name.startswith("\\icmltitle"):
        return ": use \\title{...}"
    if name == "\\twocolumn[":
        return ": drop the \\twocolumn[...] wrapper and use \\maketitle"
    if name == "\\printAffiliationsAndNotice":
        return ": delete it"
    if name in ("\\iclrfinalcopy", "\\cvprfinalcopy", "\\aclfinalcopy", "\\ijcaifinalcopy", "\\nocopyright"):
        return ": delete it"
    if name == "\\begin{ack}":
        return ": use an unnumbered \\section*{Acknowledgments} (and leave it out of a double-blind submission)"
    return ""


def _per_file(items: list[Item]) -> list[Item]:
    """Column notes: one per file and kind (a paper has dozens of floats), the first line and how many."""
    out: list[Item] = []
    seen: dict[tuple[str, str], int] = {}
    count: dict[tuple[str, str], int] = {}
    for i in items:
        if i.what != "columns" or not i.file:
            out.append(i)
            continue
        key = (i.file, i.message[:20])
        if key in seen:
            count[key] += 1
            continue
        seen[key], count[key] = len(out), 1
        out.append(i)
    for key, idx in seen.items():
        if count[key] > 1:
            i = out[idx]
            out[idx] = Item(i.what, f"{i.message} (and {count[key] - 1} more in this file)", i.file, i.line)
    return out
