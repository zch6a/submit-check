"""Small PDFs written by hand for the tests: one line of text per string, one list per page; optionally a figure (a
form XObject) that uses a Type 3 font, an /Info dictionary, a page size or no MediaBox at all."""

from __future__ import annotations

from pathlib import Path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream(data: bytes, extra: bytes = b"") -> bytes:
    return b"<< /Length " + str(len(data)).encode() + extra + b" >>\nstream\n" + data + b"\nendstream"


def build(
    path: Path,
    pages: list[list[str]],
    *,
    figure_type3: bool = False,
    info: bytes = b"<< /Producer (pdfTeX) >>",
    mediabox: str | None = "0 0 612 792",
) -> Path:
    # 1 catalog, 2 pages, 3 Helvetica, 4 a Type 3 font, 5 info, 6 the figure; then a page and its content per page
    objs: list[bytes] = [b"", b"", b"", b"", b"", b""]
    objs[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objs[3] = (
        b"<< /Type /Font /Subtype /Type3 /BaseFont /Bitmap /FontBBox [0 0 1 1] /FontMatrix [1 0 0 1 0 0] "
        b"/CharProcs << >> /Encoding << /Differences [] >> /Resources << >> >>"
    )
    objs[4] = info
    objs[5] = _stream(b"BT /T3 9 Tf 0 0 Td (a) Tj ET", b" /Type /XObject /Subtype /Form /BBox [0 0 100 100] /Resources << /Font << /T3 4 0 R >> >>")
    kids = []
    for lines in pages:
        pid = len(objs) + 1
        kids.append(pid)
        body = "\n".join(["BT", "/F1 9 Tf", "11 TL", "40 750 Td"] + [f"({_esc(x)}) Tj T*" for x in lines] + ["ET"])
        if figure_type3:
            body += "\nq /Fig Do Q"
        res = b"<< /Font << /F1 3 0 R >> " + (b"/XObject << /Fig 6 0 R >> " if figure_type3 else b"") + b">>"
        box = f"/MediaBox [{mediabox}] " if mediabox else ""
        objs.append(f"<< /Type /Page /Parent 2 0 R {box}/Contents {pid + 1} 0 R /Resources ".encode() + res + b" >>")
        objs.append(_stream(body.encode()))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
