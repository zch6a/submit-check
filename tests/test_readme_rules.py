"""The README's rules table says what the rules files say: every venue in both, the same pages and sources."""

import re
from pathlib import Path

from submit_check import rules

ROOT = Path(__file__).resolve().parent.parent


def table(readme: str) -> dict[str, tuple[str, str]]:
    """venue id -> (pages cell, row) from the rules table."""
    out = {}
    for line in readme.split("\n"):
        m = re.match(r"\|[^|]*\(`([\w-]+)`\)[^|]*\|\s*([^|]*)\|", line) or re.match(r"\|[^|]*（`([\w-]+)`）[^|]*\|\s*([^|]*)\|", line)
        if m:
            out[m.group(1)] = (m.group(2).strip(), line)
    return out


def test_both_readmes_list_every_venue_with_its_pages_and_source():
    venues = rules.all_venues()
    for name in ("README.md", "README.zh-CN.md"):
        rows = table((ROOT / name).read_text(encoding="utf-8"))
        assert set(rows) == set(venues), (name, set(rows) ^ set(venues))
        for vid, (pages, row) in rows.items():
            v = venues[vid]
            # "9 (10)", "8, long papers", "8（9）", "8（长文）": the numbers must be the rules' numbers
            numbers = [int(x) for x in re.findall(r"\d+", pages)]
            assert numbers[: 2 if v.pages_camera_ready else 1] == [x for x in (v.pages_submission, v.pages_camera_ready) if x], (name, vid, pages)
            assert v.source in row, (name, vid, "source")
