r"""Supplementary material and camera-ready checks, on material made up here (no real paper, no network)."""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

from submit_check import camera, supplementary, templates
from submit_check.cli import run

from .pdfs import build

TOKEN = "hf_" + "A1b2C3d4" * 5  # made up, the right shape


def jpeg_with_exif(artist: str, gps: bool = True) -> bytes:
    value = artist.encode() + b"\x00"
    entries = [(0x013B, 2, len(value), 0)]  # offset filled below
    if gps:
        entries.append((0x8825, 4, 1, 0))
    ifd_size = 2 + 12 * len(entries) + 4
    data_at = 8 + ifd_size
    tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(entries))
    for tag, typ, n, _ in entries:
        tiff += struct.pack("<HHI", tag, typ, n) + struct.pack("<I", data_at if tag == 0x013B else 0)
    tiff += b"\x00\x00\x00\x00" + value
    app1 = b"Exif\x00\x00" + tiff
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


def png_with_author(author: str) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + b"\x00\x00\x00\x00"

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", b"\x00" * 13) + chunk(b"tEXt", b"Author\x00" + author.encode()) + chunk(b"IEND", b"")


def docx_by(creator: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("docProps/core.xml", f"<cp:coreProperties><dc:creator>{creator}</dc:creator></cp:coreProperties>")
        z.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def mp4_by(artist: str) -> bytes:
    body = artist.encode()
    data = struct.pack(">I", 16 + len(body)) + b"data" + b"\x00\x00\x00\x01" + b"\x00\x00\x00\x00" + body
    item = struct.pack(">I", 8 + len(data)) + b"\xa9ART" + data
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16 + item


def notebook(output: str) -> str:
    cell = {"cell_type": "code", "source": ["load()\n"], "outputs": [{"output_type": "stream", "text": [output]}]}
    return json.dumps({"cells": [cell], "metadata": {}})


def make_zip(path: Path, files: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def kinds(found):
    return sorted({f.kind for f in found})


def test_a_clean_zip_has_nothing(tmp_path):
    z = make_zip(
        tmp_path / "supp.zip",
        {
            "README.md": "Run `python train.py`. Built on https://github.com/huggingface/transformers.\n",
            "train.py": "import torch\nDATA = './data'\nauthor: str = 'x'\n",
        },
    )
    found = supplementary.check(z)
    assert kinds(found) == ["supp-accounts"]  # only the list of accounts linked, to check by hand
    assert "huggingface" in found[0].message


def test_everything_that_gives_the_authors_away(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("contact.txt", "questions: jane.doe@example-university.edu\n")
    pdf = build(tmp_path / "appendix.pdf", [["Appendix A", "Thanks to Jane Doe for the data."]], info=b"<< /Author (Jane Doe) >>").read_bytes()
    z = make_zip(
        tmp_path / "supp.zip",
        {
            ".git/config": '[remote "origin"]\n\turl = git@github.com:janedoe42/sma.git\n[user]\n\tname = Jane Doe\n',
            ".git/logs/HEAD": "0" * 40 + " " + "1" * 40 + " Jane Doe <jane@uni.edu> 1700000000 +0000\tcommit: init\n",
            "README.md": "git clone https://github.com/janedoe42/sma\n",
            "train.py": "ROOT = '/home/jdoe/datasets/wmt'\nwandb.init(project='sma', entity='jdoe-lab')\nTOKEN = '" + TOKEN + "'\n",
            "LICENSE": "MIT License\n\nCopyright (c) 2025 Jane Doe\n",
            "third_party/fairseq/LICENSE": "Copyright (c) Facebook, Inc. and its affiliates.\n",
            "analysis.ipynb": notebook("FileNotFoundError: C:\\Users\\jdoe\\data\\x.csv\n"),
            "figs/photo.jpg": jpeg_with_exif("J. Doe"),
            "figs/plot.png": png_with_author("Ada Lovelace"),
            "notes.docx": docx_by("Jane Doe"),
            "demo.mp4": mp4_by("Jane Doe"),
            "appendix.pdf": pdf,
            "data/extra.zip": inner.getvalue(),
            "wandb/run-1/files/config.yaml": "x: 1\n",
            ".env": "KEY=1\n",
        },
    )
    found = supplementary.check(z, ["Jane Doe"])
    by = {(f.kind, f.file.split("supp.zip/")[-1]) for f in found}
    msgs = "\n".join(f"{f.severity} {f.file}:{f.line} {f.message}" for f in found)
    for kind, file in [
        ("supp-folder", ".git/"),
        ("supp-git", ".git/config"),
        ("supp-git", ".git/logs/HEAD"),
        ("supp-path", "train.py"),
        ("supp-wandb", "train.py"),
        ("supp-secret", "train.py"),
        ("supp-name", "LICENSE"),
        ("supp-metadata", "figs/photo.jpg"),
        ("supp-metadata", "figs/plot.png"),
        ("supp-metadata", "notes.docx"),
        ("supp-metadata", "demo.mp4"),
        ("supp-metadata", "appendix.pdf"),
        ("supp-name", "appendix.pdf p.1"),
        ("supp-email", "data/extra.zip/contact.txt"),
        ("supp-folder", "wandb/"),
        ("supp-secret", ".env"),
    ]:
        assert (kind, file) in by, (kind, file, msgs)
    # one user name, two places (the script and the notebook's output): one finding
    (path,) = [f for f in found if f.kind == "supp-path"]
    assert "jdoe" in path.message and "(and 1 more place)" in path.message
    assert not any("third_party" in f.file for f in found), msgs  # someone else's licence
    assert TOKEN not in msgs  # a secret is shown only by its first characters
    assert any(f.kind == "supp-accounts" and "janedoe42" in f.message for f in found)
    gps = [f for f in found if "GPS" in f.message]
    assert gps and gps[0].file.endswith("photo.jpg")


def test_a_folder_works_like_a_zip(tmp_path):
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.sh").write_text("python train.py --data /Users/adalove/data\n", encoding="utf-8")
    (tmp_path / "code" / "README").write_text("Contact: ada@example-uni.org\n", encoding="utf-8")
    found = supplementary.check(tmp_path / "code")
    assert kinds(found) == ["supp-email", "supp-path"]
    assert found[0].file.startswith("code/")


def test_placeholders_are_not_names(tmp_path):
    z = make_zip(
        tmp_path / "s.zip",
        {
            "run.sh": "cd /home/user/project && python /home/runner/work/x.py\nexport P=/Users/$USER/data\n",
            "setup.py": "setup(name='sma', author='Anonymous', author_email='anonymous@example.com')\n",
            "LICENSE": "Copyright (c) [year] [fullname]\n",
            "cfg.yaml": "wandb:\n  entity: null\n",
        },
    )
    assert supplementary.check(z) == []


def test_names_from_the_paper_and_name_orders():
    names = supplementary.names_from_paper({"m.tex": r"\author{Jane Doe\thanks{x} \and Ada King Lovelace \\ Example University}"})
    assert "Jane Doe" in names and "Ada King Lovelace" in names
    pattern = supplementary._name_pattern(["Jane Doe"])
    assert pattern.search("jane_doe/data") and pattern.search("Doe, Jane") is None and pattern.search("doe.jane")
    assert pattern.search("Janet Doerr") is None


def test_unreadable_and_too_big(tmp_path, monkeypatch):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    assert kinds(supplementary.check(bad)) == ["supp-unreadable"]
    monkeypatch.setattr(supplementary, "MAX_FILE", 10)
    z = make_zip(tmp_path / "big.zip", {"a.txt": "x" * 100})
    assert kinds(supplementary.check(z)) == ["supp-skipped"]


def test_cli_reads_the_authors_from_the_paper(tmp_path, capsys):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.tex").write_text(
        r"\documentclass{article}\usepackage{icml2025}\begin{document}\icmlauthor{Jane Doe}{u}x\end{document}", encoding="utf-8"
    )
    z = make_zip(tmp_path / "supp.zip", {"NOTES.txt": "ask Jane Doe\n"})
    assert run([str(paper), "--supplementary", str(z), "--venue", "icml2025", "--format", "json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert [f["kind"] for f in out["findings"] if f["kind"].startswith("supp")] == ["supp-name"]
    assert out["supplementary"] == [str(z)]
    # only the material, no paper: names from --author
    assert run(["--supplementary", str(z), "--author", "Jane Doe"]) == 1
    assert "supp.zip/NOTES.txt:1" in capsys.readouterr().out
    # a camera-ready has nothing to hide: only secrets are reported
    assert run([str(paper), "--supplementary", str(z), "--venue", "icml2025", "--mode", "camera-ready", "--format", "json"]) in (0, 1)
    assert not [f for f in json.loads(capsys.readouterr().out)["findings"] if f["kind"].startswith("supp")]


def cr(tex: str, root: Path | None = None):
    return camera.check({"main.tex": tex}, templates.detect(tex), root)


def test_camera_ready_leftovers_from_the_review_version(tmp_path):
    tex = "\n".join(
        [
            r"\documentclass[draft]{article}\usepackage[accepted]{icml2025}\usepackage{lineno}\linenumbers",
            r"\icmlauthor{Anonymous Authors}{x}",
            r"Code: \url{https://anonymous.4open.science/r/sma-1234}.",
            r"As shown by Anonymous (2024), the data is available upon acceptance.",
            r"This paper is under review~\\cite{me}.",
        ]
    )
    (tmp_path / "refs.bib").write_text("@article{me,\n  author = {Anonymous},\n  title={x}}\n", encoding="utf-8")
    found = cr(tex, tmp_path)
    assert kinds(found) == ["cr-anonymous-cite", "cr-anonymous-link", "cr-authors", "cr-draft", "cr-line-numbers", "cr-under-review"]
    assert any(f.file == "refs.bib" and f.line == 2 for f in found)
    assert sum(f.kind == "cr-anonymous-link" for f in found) == 2  # the 4open link and "available upon acceptance"
    (tmp_path / "refs.bib").write_text("@article{other,\n  author = {Anonymous},\n  title={x}}\n", encoding="utf-8")
    assert not any(f.file == "refs.bib" for f in cr(tex, tmp_path))  # not cited: never printed


def test_a_clean_camera_ready():
    tex = r"\usepackage[accepted]{icml2025}\icmlauthor{Jane Doe}{u} Code: \url{https://github.com/janedoe42/sma}. Anonymous reviewers helped."
    assert cr(tex) == []
    # names joined by ~ (Chinchilla's source), lineno loaded with \linenumbers commented out (gone with the comments)
    assert cr(r"\usepackage{lineno}\author[$\star$]{Jordan~Hoffmann}") == []


def test_camera_ready_pdf_title(tmp_path):
    no_title = build(tmp_path / "a.pdf", [["x"]], info=b"<< /Producer (pdfTeX) >>")
    titled = build(tmp_path / "b.pdf", [["x"]], info=b"<< /Title (Sparse Mixture Adapters) >>")
    assert kinds(camera.pdf_check(no_title)) == ["cr-pdf-title"]
    assert camera.pdf_check(titled) == []


def test_own_licence_and_copied_headers(tmp_path):
    z = make_zip(
        tmp_path / "s.zip",
        {
            "LICENSE": "MIT License\n\nCopyright (c) 2025 Jane Doe\n",
            "src/a.py": "# Copyright 2024 The HuggingFace Team. All rights reserved.\n",
            "src/b.py": "# Copyright 2024 The HuggingFace Team. All rights reserved.\n",
        },
    )
    found = supplementary.check(z)
    (own,) = [f for f in found if f.kind == "supp-author"]
    assert own.file == "s.zip/LICENSE" and own.line == 3 and "Jane Doe" in own.message
    (holders,) = [f for f in found if f.kind == "supp-holders"]
    assert holders.severity == "note" and "The HuggingFace Team (2×)" in holders.message
