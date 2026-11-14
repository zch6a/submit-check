r"""Run the supplementary-material check on zips of public research code, and print every finding, for reading by hand.
The repositories are listed in scripts/supplementary_repos.txt; none is anonymous, so each should give its authors
away. Download them to a folder of your choice (never into this repository), for example:

    while read r; do curl -sL -o "OUT/${r/\//__}.zip" "https://codeload.github.com/$r/zip/HEAD"; done < scripts/supplementary_repos.txt
    uv run python scripts/measure_supplementary.py OUT
"""

import sys
from collections import Counter
from pathlib import Path

from submit_check import supplementary

total: Counter = Counter()
for z in sorted(Path(sys.argv[1]).glob("*.zip")):
    found = supplementary.check(z)
    counts = Counter(f.kind for f in found)
    total.update(counts)
    print(f"== {z.name} {dict(counts)}")
    for f in found:
        if f.kind != "supp-accounts":
            print(f"   {f.severity:7} {f.file.split('/', 1)[-1][:70]}:{f.line}  {f.message[:150]}")
print(total)
