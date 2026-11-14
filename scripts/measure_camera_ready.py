"""Run the camera-ready checks on arXiv sources (fetched with paper-proof's scripts/fetch_arxiv_sources.py, the ids in
its scripts/papers.txt) and print what is not a note. These are published versions: whatever is found is either a
real leftover of the review version or a false alarm.

    uv run python scripts/measure_camera_ready.py SOURCES_DIR
"""

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

from submit_check.cli import run

kinds: Counter = Counter()
for d in sorted(p for p in Path(sys.argv[1]).iterdir() if p.is_dir()):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        run([str(d), "--mode", "camera-ready", "--format", "json", "--fail-on", "never"])
    try:
        findings = json.loads(out.getvalue())["findings"]
    except ValueError:
        print(f"{d.name}: not read")
        continue
    for f in findings:
        kinds[f["kind"]] += 1
        if f["severity"] != "note":
            print(f"{d.name} {f['severity']:7} {f['kind']:20} {f['file']}:{f['line']}  {f['message'][:120]}")
print(kinds)
