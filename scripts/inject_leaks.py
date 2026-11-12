"""Recall on injected anonymity leaks: each of five leaks put into the body of each paper (in memory), one at a time,
checked in submission mode. The sources are arXiv's (fetch them with paper-proof's scripts/fetch_arxiv_sources.py).

    uv run python scripts/inject_leaks.py SOURCES_DIR
"""

import random
import re
import sys
from collections import Counter
from pathlib import Path

from paper_proof.latex import find_main, read_project

from submit_check import anonymity, templates

# Several phrasings of each leak, as authors write them.
LEAKS = {
    "account-link": [
        "Our code is available at \\url{https://github.com/janedoe42/fastmodel}.",
        "We release our implementation at \\href{https://gitlab.com/janedoe/fm}{gitlab.com/janedoe/fm}.",
        "Videos are on the project page: \\url{https://janedoe42.github.io/fastmodel}.",
    ],
    "self-citation": [
        "As we showed in our previous work~\\cite{doe2023fast}, this holds in general.",
        "This paper extends our earlier conference paper~\\cite{doe2023fast} with new experiments.",
        "We previously proposed a related estimator~\\citep{doe2022est}.",
    ],
    "acknowledgements": [
        "\\section*{Acknowledgments} We thank Jane Doe for helpful discussions.",
        "\\subsection*{Acknowledgement} The authors thank the reviewers.",
        "\\begin{acknowledgements} We thank our colleagues. \\end{acknowledgements}",
    ],
    "email": [
        "Questions can be sent to jane.doe@example-university.edu.",
        "Contact: \\texttt{jdoe@lab.example.org}.",
        "Correspondence to J. Doe (\\href{mailto:jdoe@example.com}{jdoe@example.com}).",
    ],
    "funding": [
        "This work was supported by the National Science Foundation under grant no. 1234567.",
        "This research was funded by the ERC (grant agreement No 101000).",
        "The first author was supported in part by a Google PhD Fellowship.",
    ],
}

random.seed(0)
root = Path(sys.argv[1])
stats: Counter = Counter()
misses = []
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    proj = read_project(find_main(d))
    files = list(proj.texts)
    main = files[0]
    text = proj.texts[main]
    begin = text.find("\\begin{document}")
    end = text.rfind("\\end{document}")
    if begin < 0 or end < 0:
        continue
    # a paragraph break inside the body, not inside an environment's argument
    breaks = [m.end() for m in re.finditer(r"\n\s*\n", text[begin:end])]
    if not breaks:
        continue
    pos = begin + random.choice(breaks)
    t = templates.detect("\n".join(proj.texts.values()))
    t.mode, t.conditional = "review", False  # as a submission would be built
    before = {f.kind for f in anonymity.check(proj.texts, t)}
    for kind, leaks in LEAKS.items():
        for leak in leaks:
            mutated = dict(proj.texts)
            mutated[main] = text[:pos] + "\n" + leak + "\n\n" + text[pos:]
            line = text.count("\n", 0, pos) + 2
            found = [f for f in anonymity.check(mutated, t) if f.kind == kind and f.file == main and f.line == line]
            stats[f"{kind} injected"] += 1
            if found:
                stats[f"{kind} found"] += 1
            else:
                misses.append(f"{d.name} {kind}: {leak[:60]!r} (already reported there: {kind in before})")
print({k: v for k, v in sorted(stats.items())})
for m in misses[:20]:
    print("miss", m)
