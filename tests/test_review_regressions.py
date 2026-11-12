"""Regressions for the bugs an independent code review found, each with the input that reproduced it. No network."""

import os
import subprocess
import sys
import time
from pathlib import Path

from submit_check import anonymity, arxivcheck, leftovers, pdfcheck, rules, templates
from submit_check.cli import run

from .pdfs import build

V = rules.all_venues()
BODY = [["Introduction", "text"] for _ in range(8)]
REFS = ["References", "[1] A. Author. A paper. In NeurIPS, 2020."]


def anon(tex: str):
    return anonymity.check({"main.tex": tex}, templates.detect(tex))


def kinds(findings):
    return sorted(f.kind for f in findings)


# 1. sections the venue does not count, before the references
def test_impact_statement_and_limitations_are_not_counted(tmp_path):
    icml = build(tmp_path / "i.pdf", BODY + [["Impact Statement", "This paper presents work ..."] * 20, REFS])
    assert not [f for f in pdfcheck.check(icml, V["icml2025"], "submission") if f.kind == "page-limit"]
    acl = build(tmp_path / "a.pdf", BODY + [["Limitations", "Our method ..."] * 15, REFS])
    assert not [f for f in pdfcheck.check(acl, V["acl-arr"], "submission") if f.kind == "page-limit"]
    over = build(tmp_path / "o.pdf", BODY + [["more"] * 30, ["Limitations", "x"], REFS])
    (f,) = [f for f in pdfcheck.check(over, V["acl-arr"], "submission") if f.kind == "page-limit"]
    assert "9 pages of content before the limitations section" in f.message


# 2. Type 3 fonts inside a figure
def test_type3_font_in_a_figure(tmp_path):
    pdf = build(tmp_path / "f.pdf", [["Intro"], REFS], figure_type3=True)
    (f,) = [f for f in pdfcheck.check(pdf, V["aaai2026"], "submission") if f.kind == "type3-fonts"]
    assert f.severity == "error"


# 3. e-mail look-alikes; addresses the template hides
def test_not_emails_and_hidden_addresses():
    assert anon(r"\usepackage{neurips_2025} We report mAP@0.5 and AP@0.75, with transformers@4.36.2.") == []
    assert anon(r"\usepackage{icml2025}\icmlcorrespondingauthor{Jane Doe}{jdoe@mit.edu}") == []
    assert anon(r"\usepackage[submission]{aaai2026}\affiliations{MIT\\ jdoe@mit.edu}") == []
    assert anon(r"\documentclass[sigconf,anonymous,review]{acmart}\email{jdoe@mit.edu}") == []
    # with no known template, an address in an "Anonymous" author block still gives the author away
    assert kinds(anon(r"\documentclass{article}\author{Anonymous \\ \texttt{jdoe@stanford.edu}}")) == ["email"]


# 4. a redirected stdout on Windows
def test_reports_survive_a_non_utf8_stdout(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\\usepackage{icml2025}\\begin{document}\\url{https://x.org} 张三@pku.edu.cn\\end{document}", encoding="utf-8"
    )
    src = str(Path(__file__).resolve().parent.parent / "src")
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=src + os.pathsep + os.environ.get("PYTHONPATH", ""))
    for fmt in ("md", "json", "text"):
        p = subprocess.run(
            [sys.executable, "-c", "from submit_check.cli import main; main()", str(tmp_path), "--format", fmt, "--fail-on", "never"],
            env=env,
            capture_output=True,
        )
        assert p.returncode == 0, p.stderr.decode("utf-8", "replace")[-300:]
        # (Markdown puts a zero-width space after "@", so that GitHub makes no mention of it)
        assert "张三".encode() in p.stdout and b"pku.edu.cn" in p.stdout


# 5. quadratic regular expressions
def test_long_hostile_lines_are_fast():
    start = time.perf_counter()
    anon(r"\usepackage{neurips_2025} " + "x" * 200_000)
    templates.detect("\\usepackage[" * 20_000)
    leftovers.check({"m.tex": "TODO\n" * 20_000})
    anon("\\author{" * 2_000)
    assert time.perf_counter() - start < 5


# 6. arXiv mode does not apply the venue's page limit
def test_arxiv_mode_has_no_page_limit(tmp_path):
    pdf = build(tmp_path / "p.pdf", BODY * 2 + [REFS])
    assert not [f for f in pdfcheck.check(pdf, V["neurips2025"], "arxiv") if f.kind == "page-limit"]


# 7. the template in an \input file
def test_template_in_an_input_file():
    t = templates.detect_project({"main.tex": r"\documentclass{article}\input{preamble}", "preamble.tex": "\n\n\\usepackage[final]{neurips_2025}"})
    assert (t.file, t.line, t.mode) == ("preamble.tex", 3, "final")


# 8. unusual PDFs
def test_pdf_without_mediabox_or_with_a_strange_info(tmp_path):
    pdfcheck.check(build(tmp_path / "m.pdf", [["Intro"], REFS], mediabox=None), V["aaai2026"], "submission")
    pdfcheck.check(build(tmp_path / "i.pdf", [["Intro"], REFS], info=b"[1 2 3]"), V["aaai2026"], "submission")
    flipped = build(tmp_path / "f.pdf", [["Intro"], REFS], mediabox="0 -792 612 0")
    assert not [f for f in pdfcheck.check(flipped, V["aaai2026"], "submission") if f.kind == "paper-size"]


# 9. \iclrfinalcopy behind a switch that is off
def test_iclr_final_copy_behind_a_switch():
    t = templates.detect(r"\usepackage{iclr2026_conference}\newif\ifcamera\camerafalse\ifcamera\iclrfinalcopy\fi")
    assert t.conditional


# 10. ordinary prose
def test_prose_that_is_not_a_leak():
    assert anon(r"\usepackage{icml2025} As we previously showed in Section~\ref{s}, our previous results in Table 2 hold.") == []
    assert anon(r"\usepackage{icml2025} We use the ResNet implementation available at \url{https://github.com/pytorch/vision}.") == []


# 11. leaks that were missed
def test_leaks_that_were_missed():
    assert kinds(anon(r"\usepackage{icml2025}\paragraph{Acknowledgments.} We thank Bob.")) == ["acknowledgements"]
    assert kinds(anon(r"\usepackage{neurips_2025}\section*{Acknowledgments and Disclosure of Funding} Bob.")) == ["acknowledgements"]
    assert kinds(anon(r"\usepackage{icml2025} Code: \url{https://github.com/jdoe/myproj}")) == ["account-link"]
    assert templates.detect(r"\PassOptionsToPackage{final}{neurips_2025}\usepackage{neurips_2025}").mode == "final"


# 12. arXiv comments
def test_arxiv_comment_after_a_line_break_and_iffalse_in_a_comment(tmp_path):
    (tmp_path / "main.tex").write_text("A line\\\\% secret reviewer is Bob Smith, ask him\n% \\iffalse not a block\n", encoding="utf-8")
    found = arxivcheck.check([tmp_path / "main.tex"], tmp_path)
    assert [f.kind for f in found] == ["arxiv-comments"] and "Bob Smith" in found[0].message


# 13. the venue picked from the template
def test_venue_picking():
    v, notes = rules.pick(None, templates.detect(r"\usepackage[review]{acl}"))
    assert v.id == "acl-arr" and notes == []  # ARR's rules have no year: they hold for a template without one
    v, notes = rules.pick(None, templates.detect(r"\usepackage[review]{EMNLP2025}"))
    assert v.id == "acl-arr" and notes == []  # and for a recent one
    assert rules.pick(None, templates.detect(r"\usepackage{acl2019}"))[1][0].kind == "rules-year"  # older: may predate them
    assert rules.pick(None, templates.detect(r"\documentclass[sigconf]{acmart}"))[0] is None
    assert templates.detect(r"\usepackage[review,ID=12345,year=2024]{eccv}").year == 2024


# 14. the References heading
def test_references_heading_variants(tmp_path):
    small_caps = build(tmp_path / "s.pdf", BODY + [["more"] * 30, ["R EFERENCES", "[1] A. Author. 2020."]])
    (f,) = [f for f in pdfcheck.check(small_caps, V["icml2025"], "submission") if f.kind == "page-limit"]
    assert f.severity == "error"  # found, and over the limit
    toc = build(tmp_path / "t.pdf", [["Contents", "References 12"]] + BODY + [["more"] * 30, REFS])
    assert [f.kind for f in pdfcheck.check(toc, V["icml2025"], "submission") if f.kind == "page-limit"] == ["page-limit"]
    header = build(tmp_path / "h.pdf", BODY + [["Published as a conference paper at ICLR 2026", *REFS]])
    assert not [f for f in pdfcheck.check(header, V["icml2025"], "submission") if f.kind == "page-limit"]


# 15. silent \todo definitions
def test_silent_todo_definitions():
    assert leftovers.check({"m.tex": "\\newcommand*{\\todo}[1]{}\nx \\todo{a}"}) == []
    assert leftovers.check({"m.tex": "\\def\\todo#1{}\nx \\todo{a}"}) == []


def test_an_option_value_that_starts_with_a_dash(tmp_path, capsys):
    # the Action passes --pdf=$PDF: a value starting with "-" stays a value instead of being read as an option
    (tmp_path / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")
    assert run([str(tmp_path), "--pdf=-weird.pdf"]) == 2
    assert "cannot read -weird.pdf" in capsys.readouterr().err
