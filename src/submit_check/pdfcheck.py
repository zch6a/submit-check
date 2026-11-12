"""The compiled PDF: content pages against the limit (everything before the References heading), metadata that names
the authors, fonts that are Type 3 or not embedded, and the paper size."""

from __future__ import annotations

import re
from pathlib import Path

from paper_proof.numbers import Finding

from .rules import Venue

REFERENCES = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references|bibliography)\s*$", re.I | re.M)
SIZES = {"letter": (612, 792), "a4": (595, 842)}


def _reader(path: Path):
    from pypdf import PdfReader

    return PdfReader(str(path))


def content_pages(texts: list[str]) -> tuple[int | None, float | None]:
    """(the page the References heading is on, 1-based; how far down that page it is, 0..1)."""
    for i, t in enumerate(texts):
        m = REFERENCES.search(t)
        if m:
            return i + 1, m.start() / max(len(t), 1)
    return None, None


def check(pdf: Path, venue: Venue | None, mode: str) -> list[Finding]:
    name = pdf.name
    try:
        reader = _reader(pdf)
        pages = reader.pages
        texts = [(p.extract_text() or "") for p in pages]
    except Exception as e:  # damaged, encrypted
        return [Finding("pdf", "error", name, 0, f"cannot read the PDF ({e.__class__.__name__}: {str(e)[:100]})")]
    out: list[Finding] = []
    # pages
    limit = None
    if venue:
        limit = venue.pages_camera_ready if mode == "camera-ready" and venue.pages_camera_ready else venue.pages_submission
    ref_page, where = content_pages(texts)
    if venue and limit and ref_page:
        # The page where References starts holds content above the heading: it counts as a content page unless the
        # heading is at its very top.
        used = ref_page - 1 + (1 if where and where > 0.05 else 0)
        if used > limit:
            kind = "camera-ready" if mode == "camera-ready" else "submission"
            msg = f"{used} pages of content before the references; {venue.name} allows {limit} ({kind}; {venue.source})"
            out.append(Finding("page-limit", "error", name, ref_page, msg))
    elif limit and not ref_page:
        out.append(Finding("page-limit", "note", name, 0, f"no References heading found: the {limit}-page limit could not be checked"))
    # metadata
    meta = reader.metadata or {}
    if mode == "submission":
        for key in ("/Author", "/Creator", "/Producer", "/Title", "/Subject", "/Keywords"):
            value = str(meta.get(key, "") or "")
            if key == "/Author" and value.strip() and not re.search(r"anonymous", value, re.I):
                out.append(
                    Finding("pdf-metadata", "error", name, 0, f"the PDF's metadata names the author: {value[:80]!r} (set pdfauthor={{}} in hyperref)")
                )
            elif re.search(r"[A-Za-z]:\\Users\\|/home/|/Users/", value):
                out.append(Finding("pdf-metadata", "warning", name, 0, f"the PDF's {key[1:]} holds a path with a user name: {value[:80]!r}"))
    # fonts
    type3, not_embedded = set(), set()
    for page in pages:
        try:
            fonts = page.get("/Resources", {}).get("/Font", {}) or {}
        except Exception:
            continue
        for ref in fonts.values():
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
    if type3:
        sev = "error" if venue and venue.no_type3_fonts else "warning"
        out.append(
            Finding(
                "type3-fonts", sev, name, 0, f"Type 3 (bitmap) fonts: {', '.join(sorted(type3)[:6])} (often from a figure; publishers reject them)"
            )
        )
    if not_embedded:
        out.append(
            Finding(
                "fonts-not-embedded",
                "warning",
                name,
                0,
                f"fonts not embedded: {', '.join(sorted(not_embedded)[:6])} (embed all fonts: pdflatex does, a figure may not)",
            )
        )
    # paper size
    if venue and venue.paper in SIZES and pages:
        w, h = (float(x) for x in pages[0].mediabox[2:])
        want = SIZES[venue.paper]
        if abs(w - want[0]) > 3 or abs(h - want[1]) > 3:
            out.append(
                Finding("paper-size", "error", name, 1, f"the page is {w:.0f}×{h:.0f} pt; {venue.name} wants {venue.paper} ({want[0]}×{want[1]} pt)")
            )
    return out
