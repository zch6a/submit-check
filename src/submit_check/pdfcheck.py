"""The compiled PDF: content pages against the limit (everything before the References heading, and before the
sections the venue does not count, like ICML's Impact Statement or ACL's Limitations), metadata that names the
authors, fonts that are Type 3 or not embedded (in figures too), and the paper size."""

from __future__ import annotations

import re
from pathlib import Path

from paper_proof.numbers import Finding

from .rules import Venue

SIZES = {"letter": (612, 792), "a4": (595, 842)}


def _spaced(word: str) -> str:
    """A heading word as PDF text may give it: "REFERENCES", or faked small capitals "R EFERENCES"."""
    return r"\s?".join(re.escape(c) for c in word)


def _heading(words: str) -> re.Pattern[str]:
    alternatives = "|".join(_spaced(w) for w in words.split("|"))
    return re.compile(r"^\s*(?:[A-Z]?\d+(?:\.\d+)*\.?\s*)?(?:" + alternatives + r")\.?\s*$", re.I | re.M)


REFERENCES = _heading("References|Bibliography")
# Sections before the references that venues do not count, by the names used in `not_counted`.
NOT_COUNTED_HEADINGS = {
    "impact statement": _heading("Impact Statement|Broader Impact|Broader Impacts|Societal Impact"),
    "limitations": _heading("Limitations"),
    "ethics": _heading("Ethics Statement|Ethical Considerations|Ethics"),
    "ethics statement": _heading("Ethics Statement"),
    "reproducibility statement": _heading("Reproducibility Statement"),
}
# What follows a real References heading: an entry ([1] ..., or a line with a year), not a table-of-contents page number.
ENTRY = re.compile(r"\[\d+\]|\b(?:19|20)\d{2}[a-z]?\b")


def _reader(path: Path):
    from pypdf import PdfReader

    return PdfReader(str(path))


def _lines_before(text: str, pos: int) -> int:
    """Non-empty lines above a position on its page, the running header excluded (it is the first line at most)."""
    lines = [x for x in text[:pos].split("\n") if x.strip()]
    return max(0, len(lines) - 1)


def find_heading(texts: list[str], pattern: re.Pattern[str], need_entry: bool = False) -> tuple[int, int] | None:
    """(page, 1-based; lines of content above it on that page) of the first heading matching `pattern`."""
    for i, t in enumerate(texts):
        for m in pattern.finditer(t):
            if need_entry and not ENTRY.search(t[m.end() : m.end() + 400] + (texts[i + 1][:400] if i + 1 < len(texts) else "")):
                continue  # "References ..... 12" in a table of contents
            return i + 1, _lines_before(t, m.start())
    return None


def content_pages(texts: list[str], not_counted: list[str] | tuple[str, ...] = ()) -> tuple[int | None, int | None, str]:
    """(content pages, the page where the content ends, what ends it: "References" or the first section not counted).
    The page where it ends counts when there is content above the heading on it."""
    refs = find_heading(texts, REFERENCES, need_entry=True)
    if refs is None:
        return None, None, ""
    end, what = refs, "References"
    for name in not_counted:
        pattern = NOT_COUNTED_HEADINGS.get(name)
        found = find_heading(texts[: refs[0]], pattern) if pattern else None
        if found and found < end:
            end, what = found, name
    page, above = end
    return page - 1 + (1 if above > 0 else 0), page, what


def _fonts(resources, seen: set[int], type3: set[str], not_embedded: set[str]) -> None:
    """Fonts of a resource dictionary and of the form XObjects it uses (figures carry their own fonts)."""
    try:
        res = resources.get_object() if hasattr(resources, "get_object") else resources
        if not hasattr(res, "get"):
            return
        fonts = res.get("/Font")
        fonts = fonts.get_object() if hasattr(fonts, "get_object") else fonts
        for ref in fonts.values() if hasattr(fonts, "values") else []:
            try:
                font = ref.get_object()
                base = str(font.get("/BaseFont", "?")).lstrip("/")
                if font.get("/Subtype") == "/Type3":
                    type3.add(base)
                    continue
                desc = font.get("/FontDescriptor")
                if font.get("/Subtype") == "/Type0":
                    desc = font["/DescendantFonts"][0].get_object().get("/FontDescriptor")
                if desc is not None:
                    d = desc.get_object()
                    if not any(k in d for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                        not_embedded.add(base)
                elif font.get("/Subtype") in ("/Type1", "/TrueType"):
                    not_embedded.add(base)  # one of the standard 14, referenced by name only
            except Exception:
                continue
        xobjects = res.get("/XObject")
        xobjects = xobjects.get_object() if hasattr(xobjects, "get_object") else xobjects
        for ref in xobjects.values() if hasattr(xobjects, "values") else []:
            key = getattr(ref, "idnum", None) or id(ref)
            if key in seen:
                continue
            seen.add(key)
            try:
                x = ref.get_object()
                if x.get("/Subtype") == "/Form" and "/Resources" in x:
                    _fonts(x["/Resources"], seen, type3, not_embedded)
            except Exception:
                continue
    except Exception:
        return


def check(pdf: Path, venue: Venue | None, mode: str) -> list[Finding]:
    name = pdf.name
    try:
        reader = _reader(pdf)
        pages = reader.pages
        texts = [(p.extract_text() or "") for p in pages]
    except Exception as e:  # damaged, encrypted
        return [Finding("pdf", "error", name, 0, f"cannot read the PDF ({e.__class__.__name__}: {str(e)[:100]})")]
    out: list[Finding] = []
    venue_rules = venue if mode != "arxiv" else None  # an arXiv version follows arXiv's rules, not the venue's
    # pages
    limit = None
    if venue_rules:
        limit = venue_rules.pages_camera_ready if mode == "camera-ready" and venue_rules.pages_camera_ready else venue_rules.pages_submission
    if venue_rules and limit:
        used, page, what = content_pages(texts, venue_rules.not_counted)
        if used is None:
            out.append(Finding("page-limit", "note", name, 0, f"no References heading found: the {limit}-page limit could not be checked"))
        elif used > limit:
            kind = "camera-ready" if mode == "camera-ready" else "submission"
            before = "the references" if what == "References" else f"the {what} section (not counted)"
            msg = f"{used} pages of content before {before}; {venue_rules.name} allows {limit} ({kind}; {venue_rules.source})"
            out.append(Finding("page-limit", "error", name, page or 0, msg))
    # metadata
    if mode == "submission":
        try:
            meta = reader.metadata or {}
            items = {k: str(meta.get(k, "") or "") for k in ("/Author", "/Creator", "/Producer", "/Title", "/Subject", "/Keywords")}
        except Exception:
            items = {}
        for key, value in items.items():
            if key == "/Author" and value.strip() and not re.search(r"anonymous", value, re.I):
                out.append(
                    Finding("pdf-metadata", "error", name, 0, f"the PDF's metadata names the author: {value[:80]!r} (set pdfauthor={{}} in hyperref)")
                )
            elif re.search(r"[A-Za-z]:\\Users\\|/home/|/Users/", value):
                out.append(Finding("pdf-metadata", "warning", name, 0, f"the PDF's {key[1:]} holds a path with a user name: {value[:80]!r}"))
    # fonts
    type3: set[str] = set()
    not_embedded: set[str] = set()
    seen: set[int] = set()
    for page in pages:
        try:
            _fonts(page.get("/Resources", {}), seen, type3, not_embedded)
        except Exception:
            continue
    if type3:
        sev = "error" if venue_rules and venue_rules.no_type3_fonts else "warning"
        msg = f"Type 3 (bitmap) fonts: {', '.join(sorted(type3)[:6])} (often from a figure; publishers reject them)"
        out.append(Finding("type3-fonts", sev, name, 0, msg))
    if not_embedded:
        msg = f"fonts not embedded: {', '.join(sorted(not_embedded)[:6])} (embed all fonts: pdflatex does, a figure may not)"
        out.append(Finding("fonts-not-embedded", "warning", name, 0, msg))
    # paper size
    if venue_rules and venue_rules.paper in SIZES and pages:
        try:
            box = pages[0].mediabox
            w, h = float(box.width), float(box.height)
        except Exception:
            w = h = 0.0
        want = SIZES[venue_rules.paper]
        if w and (abs(w - want[0]) > 3 or abs(h - want[1]) > 3):
            msg = f"the page is {w:.0f}×{h:.0f} pt; {venue_rules.name} wants {venue_rules.paper} ({want[0]}×{want[1]} pt)"
            out.append(Finding("paper-size", "error", name, 1, msg))
    return out
