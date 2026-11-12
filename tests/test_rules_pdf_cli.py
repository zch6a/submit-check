"""Rules, the PDF checks and the command line, on synthetic papers and hand-written PDFs (no network)."""

import json
from pathlib import Path

from submit_check import pdfcheck, rules, templates
from submit_check.cli import run


def make_pdf(path: Path, pages: list[list[str]], author: str = "", font: str = "Type1", size=(612, 792)) -> Path:
    """A small PDF: one text line per string, one list per page; an /Info Author; a Type1 (not embedded) or Type3 font."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objs: list[bytes] = []
    n_pages = len(pages)
    page_ids = [3 + 2 * i for i in range(n_pages)]
    font_id = 3 + 2 * n_pages
    info_id = font_id + 1
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {n_pages} >>".encode())
    for lines in pages:
        content = "\n".join(["BT", "/F1 9 Tf", "11 TL", f"40 {size[1] - 40} Td"] + [f"({esc(x)}) Tj T*" for x in lines] + ["ET"]).encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] /Contents {len(objs) + 2} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    if font == "Type3":
        objs.append(
            b"<< /Type /Font /Subtype /Type3 /BaseFont /Bitmap /FontBBox [0 0 1 1] /FontMatrix [1 0 0 1 0 0] "
            b"/CharProcs << >> /Encoding << >> /Resources << >> >>"
        )
    else:
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(f"<< /Author ({esc(author)}) /Producer (pdfTeX) >>".encode())
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


ICML = rules.all_venues()["icml2025"]


def test_page_limit_counts_pages_before_the_references(tmp_path):
    body = [["Introduction", "text"] for _ in range(9)]
    pdf = make_pdf(tmp_path / "p.pdf", body + [["more text"] * 30 + ["References", "[1] A paper."]])
    (f,) = [x for x in pdfcheck.check(pdf, ICML, "submission") if x.kind == "page-limit"]
    assert "10 pages of content before the references; ICML 2025 allows 8" in f.message
    ok = make_pdf(tmp_path / "q.pdf", body[:8] + [["References", "[1] A paper."]])
    assert not [x for x in pdfcheck.check(ok, ICML, "submission") if x.kind == "page-limit"]
    # camera-ready allows one page more
    nine = make_pdf(tmp_path / "r.pdf", body + [["References", "[1] A paper, 2020."]])
    assert not [x for x in pdfcheck.check(nine, ICML, "camera-ready") if x.kind == "page-limit"]


def test_metadata_fonts_and_paper_size(tmp_path):
    aaai = rules.all_venues()["aaai2026"]
    pdf = make_pdf(tmp_path / "m.pdf", [["References", "[1] A paper, 2020."]], author="Ada Lovelace", font="Type3", size=(595, 842))
    found = {f.kind: f for f in pdfcheck.check(pdf, aaai, "submission")}
    assert "Ada Lovelace" in found["pdf-metadata"].message
    assert found["type3-fonts"].severity == "error"  # AAAI asks for Type 1 or TrueType
    assert "wants letter" in found["paper-size"].message
    plain = make_pdf(tmp_path / "n.pdf", [["References", "[1] A paper, 2020."]])
    assert "fonts-not-embedded" in {f.kind for f in pdfcheck.check(plain, aaai, "camera-ready")}
    assert "pdf-metadata" not in {f.kind for f in pdfcheck.check(pdf, aaai, "camera-ready")}  # names are fine then


def test_required_sections_and_template():
    acl = rules.all_venues()["acl-arr"]
    tex = r"\documentclass{article}\usepackage[review]{acl}\begin{document}\section{Introduction}x\end{document}"
    t = templates.detect(tex)
    (f,) = rules.check({"main.tex": tex}, acl, t, "submission")
    assert "Limitations" in f.message
    good = tex.replace(r"\end{document}", r"\section*{Limitations}We did not.\end{document}")
    assert rules.check({"main.tex": good}, acl, t, "submission") == []
    # an ICML paper written with the NeurIPS template
    wrong = r"\usepackage{neurips_2025}\section{Impact Statement}"
    assert [f.kind for f in rules.check({"m.tex": wrong}, ICML, templates.detect(wrong), "submission")] == ["wrong-template"]


def test_eccv_forbids_an_appendix_and_kdd_uses_acmart():
    eccv = rules.all_venues()["eccv2026"]
    tex = r"\usepackage[review,year=2026,ID=1]{eccv}\section{Method}x\appendix\section{Proofs}"
    (f,) = rules.check({"main.tex": tex}, eccv, templates.detect(tex), "submission")
    assert f.kind == "forbidden" and "appendix" in f.message
    final = tex.replace("[review,", "[")
    assert rules.check({"main.tex": final}, eccv, templates.detect(final), "camera-ready") == []  # appendix fine then
    kdd = r"\documentclass[sigconf,anonymous,review]{acmart}"
    t = templates.detect(kdd)
    assert (t.venue, t.mode) == ("acm", "review")
    assert templates.detect(r"\documentclass[sigconf]{acmart}").mode == "final"
    v, notes = rules.pick(None, t)  # acmart serves many ACM venues: --venue decides
    assert v is None and notes[0].kind == "rules-year"
    assert rules.pick("kdd2026", t)[0].id == "kdd2026"


def test_ijcai_template_mode_is_not_assumed():
    from submit_check import anonymity

    tex = r"\documentclass{article}\usepackage{ijcai26}\author{Jane Doe \\ MIT \\ jdoe@mit.edu}"
    t = templates.detect(tex)
    assert (t.venue, t.year, t.mode) == ("ijcai", 2026, "")
    kinds = sorted(f.kind for f in anonymity.check({"main.tex": tex}, t))
    assert kinds == ["author-names"]  # the names themselves, not a mode the template may not have
    assert rules.pick(None, t)[0].id == "ijcai2026"


def test_picking_the_venue_from_the_template():
    v, notes = rules.pick(None, templates.detect(r"\usepackage{icml2025}"))
    assert v.id == "icml2025" and notes == []
    v, notes = rules.pick(None, templates.detect(r"\usepackage{neurips_2023}"))
    assert v.id == "neurips2025" and notes[0].kind == "rules-year"


EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "paper"


def test_the_example_paper(capsys):
    assert run([str(EXAMPLE), "--format", "json"]) == 1
    kinds = {f["kind"] for f in json.loads(capsys.readouterr().out)["findings"]}
    assert {"template-mode", "email", "acknowledgements", "self-citation", "account-link", "todo", "funding", "required-section"} <= kinds
    run([str(EXAMPLE), "--mode", "arxiv", "--format", "json"])
    found = json.loads(capsys.readouterr().out)["findings"]
    (c,) = [f for f in found if f["kind"] == "arxiv-comments"]
    assert c["severity"] == "warning" and "TODO(jd)" in c["message"]  # a note to a co-author, even in the preamble


def test_command_line(tmp_path, capsys):
    (tmp_path / "main.tex").write_text(
        r"""\documentclass{article}\usepackage{icml2025}\begin{document}
Our code is at \url{https://github.com/adalovelace/engine}. \todo{fix}
\section{Impact Statement} None.
\end{document}""",
        encoding="utf-8",
    )
    make_pdf(tmp_path / "main.pdf", [["Intro"], ["References", "[1] A paper, 2020."]], author="Ada")
    code = run([str(tmp_path), "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert data["venue"] == "icml2025" and data["template_mode"] == "review" and data["pdf"].endswith("main.pdf")
    assert {f["kind"] for f in data["findings"]} == {"account-link", "todo", "pdf-metadata", "fonts-not-embedded"}
    assert code == 1  # the metadata names the author
    assert run([str(tmp_path), "--fail-on", "never"]) == 0
    assert run([str(tmp_path), "--venue", "nope"]) == 2
    assert run(["--list-venues"]) == 0
    assert run([str(tmp_path / "nope")]) == 2
    capsys.readouterr()
    (tmp_path / "part.tex").write_text("A section \\todo{x}.", encoding="utf-8")
    run([str(tmp_path / "part.tex"), "--format", "json", "--fail-on", "never"])
    assert "not-main-file" in {f["kind"] for f in json.loads(capsys.readouterr().out)["findings"]}
