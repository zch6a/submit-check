"""submit-check move, on made-up papers (no network)."""

from __future__ import annotations

import json

from submit_check import move, rules, templates
from submit_check.cli import run

NEURIPS = r"""\documentclass{article}
\usepackage{neurips_2025}
\begin{document}
\title{X}\author{Ada \And Charles}
\maketitle
\section{Method}
\begin{figure}[t]\includegraphics[width=\textwidth]{a.pdf}\caption{A.}\end{figure}
\begin{table}[t]\resizebox{\textwidth}{!}{x}\caption{T.}\end{table}
\begin{figure}[t]\includegraphics[width=0.5\linewidth]{b.pdf}\end{figure}
\begin{ack}Thanks.\end{ack}
\section*{NeurIPS Paper Checklist}
\bibliographystyle{plainnat}
\end{document}
"""


def report(tex: str, to: str):
    texts = {"main.tex": tex}
    t = templates.detect_project(texts)
    src, _ = rules.pick(None, t)
    return move.check(texts, t, rules.all_venues()[to], src)


def test_neurips_to_icml():
    r = report(NEURIPS, "icml2025")
    msgs = [(i.what, i.line, i.message) for i in r.items]
    assert r.source == "NeurIPS" and r.target.startswith("ICML")
    assert any(w == "template" and ln == 2 and "replace neurips_2025 with the ICML template" in m for w, ln, m in msgs)
    assert any(w == "commands" and ln == 10 and "\\begin{ack}" in m for w, ln, m in msgs)
    wide = [ln for w, ln, m in msgs if w == "columns" and "\\textwidth" in m]
    assert wide == [7, 8]  # the half-width figure is fine
    assert any(w == "sections" and "Impact Statement" in m for w, _, m in msgs)  # ICML requires it
    assert any(w == "sections" and "checklist" in m and "does not" in m for w, _, m in msgs)  # only NeurIPS asked for it


def test_icml_to_neurips_two_columns_to_one(tmp_path):
    tex = r"""\documentclass{article}\usepackage{icml2025}
\begin{document}
\twocolumn[\icmltitle{X}\icmlauthor{A}{u}]
\begin{figure*}[t]x\end{figure*}
\bibliographystyle{icml2025}
\end{document}"""
    r = report(tex, "neurips2025")
    kinds = {i.what for i in r.items}
    assert {"template", "commands", "columns", "sections", "bibliography"} <= kinds
    assert any("figure* spans both columns" in i.message and i.line == 4 for i in r.items)
    assert any(i.what == "bibliography" and "icml2025" in i.message for i in r.items)
    assert any("NeurIPS paper checklist" in i.message for i in r.items)


def test_same_family_and_cli(tmp_path, capsys):
    r = report(NEURIPS, "neurips2025")
    assert [i.message for i in r.items if i.what == "template"][0].startswith("already the NeurIPS template")
    assert not [i for i in r.items if i.what in ("commands", "columns")]
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "main.tex").write_text(NEURIPS, encoding="utf-8")
    assert run(["move", str(paper), "--to", "acl-arr", "--format", "json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["source"] == "NeurIPS" and any("Limitations" in i["message"] for i in doc["items"])
    assert run(["move", str(paper), "--to", "nowhere2030"]) == 2
    assert run(["move", str(tmp_path / "missing"), "--to", "acl-arr"]) == 2
