r"""Anonymity and leftovers on small synthetic LaTeX (no real paper, no network)."""

from submit_check import anonymity, leftovers, templates


def run(tex: str, mode: str = "submission"):
    return anonymity.check({"main.tex": tex}, templates.detect(tex), mode)


def kinds(findings):
    return sorted(f.kind for f in findings)


def test_a_template_in_final_mode_prints_the_authors():
    tex = r"\documentclass{article}\usepackage[final]{neurips_2025}\author{Ada Lovelace}\begin{document}x\end{document}"
    assert kinds(run(tex)) == ["template-mode"]
    assert run(tex.replace("[final]", "")) == []  # the template hides the authors itself
    assert run(tex, "camera-ready") == []  # nothing to hide in a camera-ready


def test_a_template_loaded_inside_a_condition():
    # FlashAttention: \iftoggle{arxiv}{}{\usepackage{neurips_2022}}: the mode of the PDF is not in the source
    tex = r"\newtoggle{arxiv}\iftoggle{arxiv}{}{\usepackage{neurips_2022}}\author{Tri Dao}"
    t = templates.detect(tex)
    assert t.conditional
    (f,) = run(tex)
    assert f.kind == "template-mode" and f.severity == "note"


def test_leftover_words_in_capitals_only():
    assert leftovers.check({"m.tex": r"\newtoggle{todo} \begin{tabularx}{\textwidth}{l|XXX} ISBN 978-1-XXXX"}) == []
    assert [f.kind for f in leftovers.check({"m.tex": "TODO: rewrite this. FIXME"})] == ["todo", "todo"]


def test_names_with_a_template_that_does_not_hide_them():
    tex = r"\documentclass{article}\author{Ada Lovelace \\ University of London}\begin{document}x\end{document}"
    assert kinds(run(tex)) == ["author-names"]
    assert run(tex.replace("Ada Lovelace \\\\ University of London", "Anonymous Authors")) == []


def test_acknowledgements_emails_thanks_and_funding():
    tex = r"""\documentclass{article}\usepackage{icml2025}\begin{document}
Write to ada@example.org for the data.
\section*{Acknowledgements}
We thank Charles\thanks{Cambridge}. This work was supported by the NSF grant no. 12345.
\end{document}"""
    assert kinds(run(tex)) == ["acknowledgements", "email", "funding", "funding", "thanks"]


def test_neurips_ack_environment_is_hidden_by_the_template():
    tex = r"\usepackage{neurips_2025}\begin{ack}Supported by grant no. 42 and ada@example.org.\end{ack}"
    assert run(tex) == []


def test_links_that_point_to_the_authors():
    ours = r"\usepackage{icml2025} Our code is available at \url{https://github.com/adalovelace/engine}."
    assert kinds(run(ours)) == ["account-link"]
    theirs = r"\usepackage{icml2025} We build on PyTorch (\url{https://github.com/pytorch/pytorch})."
    assert run(theirs) == []
    anonymised = r"\usepackage{icml2025} Code is available at \url{https://anonymous.4open.science/r/engine}."
    assert run(anonymised) == []


def test_first_person_self_citation():
    tex = r"\usepackage{icml2025} As shown in our previous work \cite{lovelace1843}, engines compute. In our work, we go further."
    (f,) = run(tex)
    assert f.kind == "self-citation" and "our previous work" in f.message
    assert run(r"\usepackage{icml2025} In our paper~\cite{lovelace1843} we showed it.")[0].kind == "self-citation"


def test_leftover_notes():
    tex = r"""\newcommand{\todo}[1]{\textcolor{red}{#1}}
Results are good \todo{check the numbers}. TODO: rewrite. See [citation needed]."""
    assert kinds(leftovers.check({"m.tex": tex})) == ["todo", "todo", "todo"]
    silent = r"\newcommand{\todo}[1]{}" + "\nResults \\todo{check}."
    assert leftovers.check({"m.tex": silent}) == []
