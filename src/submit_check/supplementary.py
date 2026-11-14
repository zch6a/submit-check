r"""Supplementary material (a .zip or a folder): what gives the authors away besides the paper.

Reviewers download the zip and open it. What they can find there:

- a `.git` folder (its config and logs name the authors), run logs (`wandb/`, `mlruns/`), editor folders;
- the authors' names: those given with `--author`, and those in the paper's `\author` block;
- e-mail addresses, paths with a user name (`/home/jdoe/...`, `C:\Users\jdoe\...`), author and copyright lines,
  a W&B entity, links to GitHub accounts (listed once, to check none is yours);
- secrets: API keys and tokens (revoke them: the zip may be public after the review);
- inside files: a PDF's Author field (and its text), an Office file's creator, a photo's Artist, Copyright and GPS
  tags, a video's artist tag; a zip inside the zip, one level down.

Nothing is extracted to disk; every file is read in memory, at most 20 MB each and 400 MB in all. Each finding names
the file inside the material, and the line for text.
"""

from __future__ import annotations

import io
import json
import re
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from paper_proof.numbers import Finding

from .anonymity import EMAIL

MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 400 * 1024 * 1024
MAX_FILES = 20000

TEXT_SUFFIXES = {
    ".py",
    ".ipynb",
    ".md",
    ".txt",
    ".rst",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
    ".sh",
    ".bash",
    ".zsh",
    ".r",
    ".m",
    ".jl",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cu",
    ".java",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".lua",
    ".tex",
    ".bib",
    ".cff",
    ".csv",
    ".tsv",
    ".log",
    ".html",
    ".xml",
    ".env",
    ".conf",
    ".slurm",
    ".sbatch",
    ".pbs",
    ".gitignore",
}
TEXT_NAMES = {"license", "licence", "readme", "makefile", "dockerfile", "requirements", "authors", "contributors", "notice", "config"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v"}
OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
# Code that is someone else's: its copyright and e-mail lines are not the authors'.
VENDORED = re.compile(r"(?:^|/)(?:third[_-]?party|vendor|vendored|external|extern|site-packages|node_modules|deps)/", re.I)

# Folders that should not be in the material at all.
FOLDERS = [
    (re.compile(r"(?:^|/)\.git/"), "error", "a .git folder: its config and history name the authors (zip a clean copy: git archive)"),
    (re.compile(r"(?:^|/)(?:wandb|mlruns|lightning_logs)/"), "warning", "run logs ({0}): they hold user names, host names and paths"),
    (re.compile(r"(?:^|/)(?:\.idea|\.vscode)/"), "note", "an editor's settings folder ({0}): it can hold paths with your user name"),
    (re.compile(r"(?:^|/)__MACOSX/"), "note", "__MACOSX (macOS zip metadata): zip from the command line, or delete it"),
    (re.compile(r"(?:^|/)\.ipynb_checkpoints/"), "note", "notebook checkpoints (.ipynb_checkpoints): old copies, with old outputs"),
]
SECRET_FILES = re.compile(r"(?:^|/)(?:\.env|id_rsa|id_ed25519|\.netrc|\.pypirc|credentials(?:\.json)?|\.git-credentials)$", re.I)

# Paths with a user name. Placeholders and machine accounts are not names.
USER_PATH = re.compile(r"(?:/home/|/Users/|[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/))([A-Za-z][\w.-]{1,39})")
NOT_USERS = {
    "user",
    "username",
    "you",
    "your",
    "yourname",
    "your_name",
    "me",
    "name",
    "runner",
    "ubuntu",
    "root",
    "admin",
    "anonymous",
    "anon",
    "xxx",
    "xxxx",
    "foo",
    "bar",
    "example",
    "shared",
    "public",
    "default",
    "guest",
    "path",
    "docker",
    "jovyan",
    "vscode",
    "travis",
    "circleci",
    "appveyor",
    "work",
    "project",
    "projects",
    "data",
    "home",
    "users",
    "test",
    "runneradmin",
    "builder",
    "vagrant",
    "ec2-user",
    "centos",
    "pi",
    "colab",
    "app",
    "linuxbrew",
    "nobody",
    "something",
    "someone",
    "myuser",
    "my_user",
    "john",
    "johndoe",
    "jdoe_example",
}
# The project's own licence and metadata at the top of the material (a zip often has one folder around everything).
OWN_METADATA = re.compile(r"^[^/]+/(?:[^/]+/)?(?:LICEN[CS]E(?:\.\w+)?|setup\.py|setup\.cfg|pyproject\.toml|CITATION\.cff|package\.json)$", re.I)
AUTHOR_LINE = re.compile(
    r"""(?:^|[\s#*/'"(])(?:__author__\s*=\s*|@author:?\s*|author(?:s)?\s*[:=]\s*\[?\s*(?:\{\s*name\s*=\s*)?|"""
    r"""copyright\s*(?:\(c\)|©)?\s*(?:\d{4}(?:\s*[-,]\s*\d{4})*,?\s*)?)['"]?((?-i:[A-Z])[\w'.-]+(?:,?[ \t]+(?-i:[A-Z])[\w'.-]*){0,4})""",
    re.I | re.M,
)
NOT_AUTHORS = re.compile(
    r"^(?:anonymous|anon|the\s+(?:authors?|contributors)|authors?|contributors|\[?(?:year|fullname|name|yyyy)\]?|your\s+name|"
    r"\(?c\)?\b|holder|owner|notice|licen[cs]e\b|treaty|act\b|law\b|office\b|protection\b|and\b|or\b|by\b|the\s+above|all\s+rights|\d)",
    re.I,
)
WANDB_ENTITY = re.compile(r"""\bentity\s*[=:]\s*['"]([\w-]{2,64})['"]|WANDB_ENTITY\s*=\s*['"]?([\w-]{2,64})""")
GITHUB_ACCOUNT = re.compile(r"github\.com[/:]([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))(?=[/\s'\")\]>.,]|$)", re.I)
NOT_ACCOUNTS = {"anonymous", "user", "username", "your-username", "yourname", "orgs", "features", "about", "login", "settings", "topics", "sponsors"}
SECRETS = [
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "a Hugging Face token"),
    (re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"), "an OpenAI or Anthropic API key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), "a GitHub token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "a Google API key"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "a Slack token"),
    (re.compile(r"""WANDB_API_KEY\s*[=:]\s*['"]?([0-9a-f]{40})\b"""), "a W&B API key"),
]


@dataclass
class Entry:
    name: str  # path inside the material, with "/"
    data: bytes


def _entries(path: Path, prefix: str = "") -> tuple[list[Entry], list[Finding]]:
    """Every file of a zip or a folder, in memory, within the limits."""
    out: list[Entry] = []
    notes: list[Finding] = []
    total = 0
    label = prefix or path.name

    def too_big(name: str, size: int) -> bool:
        nonlocal total
        if size > MAX_FILE:
            notes.append(Finding("supp-skipped", "note", f"{label}/{name}", 0, f"not read: {size / (1024 * 1024):.1f} MB is over the 20 MB a file"))
            return True
        if total + size > MAX_TOTAL:
            notes.append(Finding("supp-skipped", "note", f"{label}/{name}", 0, "not read: the material is over 400 MB in all"))
            return True
        total += size
        return False

    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file())
        for p in files[:MAX_FILES]:
            name = p.relative_to(path).as_posix()
            if not too_big(name, p.stat().st_size):
                out.append(Entry(name, p.read_bytes()))
        dirs = {p.relative_to(path).as_posix() + "/" for p in path.rglob("*") if p.is_dir()}
        out += [Entry(d, b"") for d in sorted(dirs)]  # empty entries mark folders (a .git with nothing read is still a .git)
    else:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist()[:MAX_FILES]:
                if info.is_dir():
                    out.append(Entry(info.filename, b""))
                elif not too_big(info.filename, info.file_size):
                    with z.open(info) as f:
                        out.append(Entry(info.filename, f.read(MAX_FILE + 1)[:MAX_FILE]))
    return out, notes


def _is_text(e: Entry) -> bool:
    p = PurePosixPath(e.name.lower())
    if p.suffix in TEXT_SUFFIXES or p.stem in TEXT_NAMES or p.name in TEXT_NAMES:
        return True
    return bool(e.data) and b"\x00" not in e.data[:8192] and p.suffix == ""


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _name_pattern(names: list[str]) -> re.Pattern[str] | None:
    """The authors' names, each as written or with its parts in another order or joined (jane.doe, jdoe is too loose)."""
    alts = []
    for n in names:
        parts = [p for p in re.split(r"[\s.]+", n.strip()) if len(p) > 1]
        if not parts:
            continue
        alts.append(r"[\s._-]?".join(re.escape(p) for p in parts))
        if len(parts) >= 2:
            alts.append(r"[\s._-]?".join(re.escape(p) for p in reversed(parts)))
    return re.compile(r"(?<![A-Za-z])(?:" + "|".join(alts) + r")(?![a-z])", re.I) if alts else None


def _redact(secret: str) -> str:
    return f"{secret[:6]}…({len(secret)} characters)"


def scan_text(where: str, text: str, names: re.Pattern[str] | None, vendored: bool = False) -> tuple[list[Finding], set[str]]:
    """Findings for one text file (or a PDF's text), and the GitHub accounts it links to."""
    out: list[Finding] = []
    # a notebook keeps "\\" in its JSON strings and "\n" between lines of a cell; reading it as it prints keeps lines
    if names:
        seen_lines = set()
        for m in names.finditer(text):
            line = _line(text, m.start())
            if line not in seen_lines:
                seen_lines.add(line)
                out.append(Finding("supp-name", "error", where, line, f"an author's name: {m.group(0)!r}"))
    for pattern, what in SECRETS:
        for m in pattern.finditer(text):
            secret = m.group(1) if m.groups() else m.group(0)
            out.append(
                Finding(
                    "supp-secret", "error", where, _line(text, m.start()), f"{what}: {_redact(secret)} (revoke it; the material may become public)"
                )
            )
    if not vendored:
        for m in EMAIL.finditer(text):
            addr = m.group(0)
            if re.search(
                r"@(?:example\.(?:com|org)|users\.noreply\.github\.com|github\.com|anonymous)|^(?:noreply|no-reply|anonymous|git)@", addr, re.I
            ):
                continue
            if text[max(0, m.start() - 1) : m.start()] == ":" or text[max(0, m.start() - 3) : m.start()] == "://":
                continue  # user:password@host in a URL, or git@host
            out.append(Finding("supp-email", "warning", where, _line(text, m.start()), f"an e-mail address: {addr}"))
        for m in AUTHOR_LINE.finditer(text):
            who = re.sub(r"[.,]?\s+All$", "", m.group(1).strip()).strip(" .,;:'\"")  # "... Inc. All rights reserved"
            if NOT_AUTHORS.match(who):
                continue
            if OWN_METADATA.search(where):
                msg = f'the project\'s own licence or metadata names: {who[:70]!r} (put "Anonymous" until the camera-ready)'
                out.append(Finding("supp-author", "warning", where, _line(text, m.start(1)), msg))
            else:  # a header in a source file: often copied code; listed once for the whole material
                out.append(Finding("supp-holder", "note", where, _line(text, m.start(1)), who[:70]))
    for m in USER_PATH.finditer(text):
        if m.group(1).lower() not in NOT_USERS and not m.group(1).startswith(("$", "%", "<")):
            out.append(Finding("supp-path", "warning", where, _line(text, m.start()), f"a path with a user name: {m.group(0)}"))
    for m in WANDB_ENTITY.finditer(text):
        entity = m.group(1) or m.group(2)
        if entity.lower() not in NOT_USERS and entity.lower() not in {"none", "null", "entity"}:
            out.append(Finding("supp-wandb", "warning", where, _line(text, m.start()), f"a W&B entity (a user or team name): {entity}"))
    accounts = {m.group(1) for m in GITHUB_ACCOUNT.finditer(text) if m.group(1).lower() not in NOT_ACCOUNTS}
    return _dedupe(out), accounts


def _dedupe(found: list[Finding]) -> list[Finding]:
    seen, out = set(), []
    for f in found:
        key = (f.kind, f.file, f.line, f.message)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


# ---- what is inside binary files ----


def _exif(data: bytes) -> dict[str, str]:
    """Artist, Copyright, XPAuthor and whether there is GPS, from a JPEG's or a TIFF's EXIF (no library)."""
    tiff = b""
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker, size = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
            if marker == 0xE1 and data[i + 4 : i + 10] == b"Exif\x00\x00":
                tiff = data[i + 10 : i + 2 + size]
                break
            if marker in (0xDA, 0xD9):
                break
            i += 2 + size
    elif data[:4] in (b"II*\x00", b"MM\x00*"):
        tiff = data
    if len(tiff) < 8:
        return {}
    end = "<" if tiff[:2] == b"II" else ">"
    out: dict[str, str] = {}
    try:
        (offset,) = struct.unpack(end + "I", tiff[4:8])
        (count,) = struct.unpack(end + "H", tiff[offset : offset + 2])
        for k in range(min(count, 200)):
            e = tiff[offset + 2 + 12 * k : offset + 14 + 12 * k]
            tag, typ, n = struct.unpack(end + "HHI", e[:8])
            if tag == 0x8825:
                out["GPS"] = "yes"
                continue
            if tag not in (0x013B, 0x8298, 0x9C9D):
                continue
            size = n * (1 if typ in (1, 2, 7) else 2 if typ == 3 else 4)
            raw = e[8 : 8 + size] if size <= 4 else tiff[struct.unpack(end + "I", e[8:12])[0] :][:size]
            value = raw.decode("utf-16-le", "ignore") if tag == 0x9C9D else raw.decode("utf-8", "ignore")
            value = value.strip("\x00 ")
            if value:
                out[{0x013B: "Artist", 0x8298: "Copyright", 0x9C9D: "Author"}[tag]] = value
    except (struct.error, IndexError):
        return out
    return out


def _png_text(data: bytes) -> dict[str, str]:
    """A PNG's tEXt and iTXt fields that name a person."""
    out: dict[str, str] = {}
    i = 8
    while i + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[i : i + 8])
        body = data[i + 8 : i + 8 + size]
        if kind in (b"tEXt", b"iTXt"):
            key, _, value = body.partition(b"\x00")
            if kind == b"iTXt":
                value = value[2:].split(b"\x00", 2)[-1]
            if key.decode("latin-1") in ("Author", "Artist", "Copyright", "Creator"):
                out[key.decode("latin-1")] = value.decode("utf-8", "ignore").strip()
        if kind == b"IEND":
            break
        i += 12 + size
    return out


def _video_tags(data: bytes) -> dict[str, str]:
    """An MP4/MOV's artist, author and location tags (iTunes-style "©ART" or QuickTime user data)."""
    out: dict[str, str] = {}
    for tag, label in ((b"\xa9ART", "artist"), (b"\xa9aut", "author"), (b"\xa9xyz", "location"), (b"auth", "author")):
        pos = data.find(tag)
        while pos != -1:
            after = data[pos + 4 : pos + 4 + 600]
            if after[4:8] == b"data":  # ilst: [size]['data'][type][locale][value]
                (size,) = struct.unpack(">I", after[:4])
                value = after[16:size]
            else:  # QuickTime: [length 2][language 2][text]
                (size,) = struct.unpack(">H", after[:2]) if len(after) >= 2 else (0,)
                value = after[4 : 4 + size]
            text = value.decode("utf-8", "ignore").strip("\x00 ")
            if text and text.isprintable() and 1 < len(text) < 200:
                out[label] = text
                break
            pos = data.find(tag, pos + 4)
    return out


def _office(data: bytes) -> dict[str, str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            core = z.read("docProps/core.xml").decode("utf-8", "ignore")
    except (KeyError, zipfile.BadZipFile):
        return {}
    out = {}
    for tag, label in (("dc:creator", "creator"), ("cp:lastModifiedBy", "last modified by")):
        m = re.search(rf"<{tag}>([^<]+)</{tag}>", core)
        if m and m.group(1).strip():
            out[label] = m.group(1).strip()
    return out


def _pdf(where: str, data: bytes, names: re.Pattern[str] | None) -> tuple[list[Finding], set[str]]:
    from pypdf import PdfReader

    out: list[Finding] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        meta: dict = reader.metadata or {}
        author = str(meta.get("/Author", "") or "")
        if author.strip() and not re.search(r"anonymous", author, re.I):
            out.append(Finding("supp-metadata", "error", where, 0, f"the PDF's metadata names the author: {author[:80]!r}"))
        for field in ("/Creator", "/Producer", "/Title"):
            value = str(meta.get(field, "") or "")
            if USER_PATH.search(value):
                out.append(Finding("supp-metadata", "warning", where, 0, f"the PDF's {field[1:]} holds a path with a user name: {value[:80]!r}"))
        pages = [p.extract_text() or "" for p in reader.pages[:200]]
    except Exception as e:
        return [Finding("supp-unreadable", "note", where, 0, f"cannot read the PDF ({e.__class__.__name__})")], set()
    found, accounts = set(), set()
    for i, page in enumerate(pages, 1):
        f, a = scan_text(where, page, names)
        accounts |= a
        for x in f:
            key = (x.kind, x.message)
            if key not in found:  # once per PDF: a name in a running header is on every page
                found.add(key)
                out.append(Finding(x.kind, x.severity, f"{where} p.{i}", 0, x.message))
    return out, accounts


def _binary(where: str, e: Entry, names: re.Pattern[str] | None) -> list[Finding]:
    suffix = PurePosixPath(e.name.lower()).suffix
    tags: dict[str, str] = {}
    what = ""
    if suffix in IMAGE_SUFFIXES:
        tags, what = (_png_text(e.data) if e.data[:8] == b"\x89PNG\r\n\x1a\n" else _exif(e.data)), "the image's metadata"
    elif suffix in VIDEO_SUFFIXES:
        tags, what = _video_tags(e.data), "the video's metadata"
    elif suffix in OFFICE_SUFFIXES:
        tags, what = _office(e.data), "the document's properties"
    out = []
    for key, value in tags.items():
        if key == "GPS":
            out.append(Finding("supp-metadata", "warning", where, 0, f"{what} has GPS coordinates: where the photo was taken"))
        elif key == "location":
            out.append(Finding("supp-metadata", "warning", where, 0, f"{what} has a location: {value[:40]}"))
        elif not re.search(r"anonymous", value, re.I):
            sev = "error" if names and names.search(value) else "warning"
            out.append(Finding("supp-metadata", sev, where, 0, f"{what}: {key} {value[:80]!r}"))
    return out


def _git(entries: list[Entry], label: str) -> list[Finding]:
    """What a .git folder gives away: the user and remote in its config, the names in its logs."""
    out = []
    for e in entries:
        if re.search(r"(?:^|/)\.git/config$", e.name):
            text = _decode(e.data)
            for m in re.finditer(r"url\s*=\s*(\S+)|name\s*=\s*(.+)|email\s*=\s*(\S+)", text):
                value = (m.group(1) or m.group(2) or m.group(3)).strip()
                out.append(Finding("supp-git", "error", f"{label}/{e.name}", _line(text, m.start()), f"the git config: {value[:90]}"))
        elif re.search(r"(?:^|/)\.git/logs/HEAD$", e.name):
            people = sorted({m.group(1).strip() for m in re.finditer(r"[0-9a-f]{40} [0-9a-f]{40} ([^<\n]{1,80}) <", _decode(e.data))})
            if people:
                out.append(Finding("supp-git", "error", f"{label}/{e.name}", 0, f"the git history names: {', '.join(people[:5])}"))
    return out


def check(path: Path, names: list[str] | None = None, depth: int = 0, label: str = "") -> list[Finding]:
    """Findings for supplementary material at `path` (a .zip or a folder). `names` are the authors' names."""
    label = label or path.name
    try:
        entries, out = _entries(path, label)
    except (zipfile.BadZipFile, OSError) as err:
        return [Finding("supp-unreadable", "error", label, 0, f"cannot read the supplementary material ({err.__class__.__name__}: {str(err)[:80]})")]
    pattern = _name_pattern(names or [])
    folders_seen: set[str] = set()
    for e in entries:
        for rx, sev, msg in FOLDERS:
            m = rx.search(e.name)
            if m:
                top = e.name[: m.end()]
                if top not in folders_seen:
                    folders_seen.add(top)
                    out.append(Finding("supp-folder", sev, f"{label}/{top}", 0, msg.format(top.rstrip("/").split("/")[-1])))
        if SECRET_FILES.search(e.name):
            out.append(Finding("supp-secret", "error", f"{label}/{e.name}", 0, "a file that holds credentials: leave it out"))
        if pattern and pattern.search(e.name):
            out.append(Finding("supp-name", "error", f"{label}/{e.name}", 0, "an author's name in a file or folder name"))
    out += _git(entries, label)
    accounts: dict[str, str] = {}
    for e in entries:
        if not e.data or "/.git/" in "/" + e.name:
            continue
        where = f"{label}/{e.name}"
        suffix = PurePosixPath(e.name.lower()).suffix
        if suffix == ".pdf" or e.data[:5] == b"%PDF-":
            found, acc = _pdf(where, e.data, pattern)
            out += found
            accounts.update({a: where for a in acc if a not in accounts})
        elif suffix == ".zip" and depth == 0:
            inner = _nested(e, pattern, names or [], where)
            out += inner
        elif suffix in IMAGE_SUFFIXES | VIDEO_SUFFIXES | OFFICE_SUFFIXES:
            out += _binary(where, e, pattern)
        elif _is_text(e):
            text = _decode(e.data)
            if suffix == ".ipynb":
                text = _notebook(text)
            found, acc = scan_text(where, text, pattern, vendored=bool(VENDORED.search(e.name)))
            out += found
            accounts.update({a: where for a in acc if a not in accounts})
    out = _grouped(out)
    if accounts:
        shown = ", ".join(sorted(accounts, key=str.lower)[:15]) + (f" and {len(accounts) - 15} more" if len(accounts) > 15 else "")
        out.append(Finding("supp-accounts", "note", label, 0, f"links to GitHub accounts: {shown}; check none of them is yours"))
    return out


def _grouped(found: list[Finding]) -> list[Finding]:
    """One finding per address, user path or entity (the first place, with how many more); the copyright holders of
    source-file headers as one list."""
    out: list[Finding] = []
    first: dict[tuple[str, str], int] = {}
    more: dict[tuple[str, str], int] = {}
    holders: dict[str, int] = {}
    holder_at: dict[str, Finding] = {}
    named = {(f.file, f.line) for f in found if f.kind == "supp-name"}
    for f in found:
        if f.kind == "supp-author" and (f.file, f.line) in named:
            continue  # the same line, already reported for the name
        if f.kind == "supp-holder":
            holders[f.message] = holders.get(f.message, 0) + 1
            holder_at.setdefault(f.message, f)
            continue
        if f.kind in ("supp-email", "supp-path", "supp-wandb"):
            value = f.message
            if f.kind == "supp-path":
                value = re.sub(r"^(a path with a user name: \S*?(?:/home/|/Users/|Users[\\/]+))([\w.-]+).*", r"\2", f.message)
            key = (f.kind, value)
            if key in first:
                more[key] = more.get(key, 0) + 1
                continue
            first[key] = len(out)
        out.append(f)
    for key, n in more.items():
        f = out[first[key]]
        out[first[key]] = Finding(f.kind, f.severity, f.file, f.line, f"{f.message} (and {n} more place{'s' if n > 1 else ''})")
    if holders:
        top = sorted(holders, key=lambda h: -holders[h])
        shown = "; ".join(f"{h} ({holders[h]}×)" for h in top[:10]) + (f"; and {len(top) - 10} more" if len(top) > 10 else "")
        where = holder_at[top[0]]
        out.append(
            Finding(
                "supp-holders",
                "note",
                where.file.split("/")[0],
                0,
                f"copyright and author lines in the files name: {shown}; check none is you or your group",
            )
        )
    return out


def _notebook(text: str) -> str:
    """A notebook's cells and outputs as they print, one line per line (paths in outputs included)."""
    try:
        nb = json.loads(text)
    except ValueError:
        return text
    lines: list[str] = []
    for cell in nb.get("cells", []) if isinstance(nb, dict) else []:
        src = cell.get("source", "")
        lines += src if isinstance(src, list) else [src]
        for o in cell.get("outputs", []) or []:
            for v in [o.get("text", "")] + list((o.get("data") or {}).get("text/plain", []) or []):
                lines += v if isinstance(v, list) else [v]
            lines += o.get("traceback", []) or []
    meta = json.dumps(nb.get("metadata", {})) if isinstance(nb, dict) else ""
    return "".join(x if x.endswith("\n") else x + "\n" for x in lines) + meta


def _nested(e: Entry, pattern: re.Pattern[str] | None, names: list[str], where: str) -> list[Finding]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "inner.zip"
        p.write_bytes(e.data)
        return check(p, names, depth=1, label=where)


def names_from_paper(texts: dict[str, str]) -> list[str]:
    r"""The authors' names in the paper's \author or \icmlauthor blocks (a review-mode template hides them, but they
    are often there).

    >>> names_from_paper({"m.tex": r"\icmlauthor{Jane Doe}{uni}\icmlauthor{Ada Lovelace}{uni}"})
    ['Jane Doe', 'Ada Lovelace']
    >>> names_from_paper({"m.tex": r"\author{Anonymous Authors}"})
    []
    """
    from .anonymity import _author_blocks, _real_names

    out: list[str] = []
    for text in texts.values():
        for _, block in _author_blocks(text):
            if not _real_names(block):
                continue
            block = re.sub(r"\\(?:thanks|footnote|texttt|url|href)\s*\{[^{}]*\}|\\\\|\\and\b|\\AND\b|\$[^$]*\$", "\n", block)
            block = re.sub(r"\\[A-Za-z@]+\*?|[{}~]", " ", block)
            for part in re.split(r"\n|,|\band\b", block):
                part = re.sub(r"\s+", " ", part).strip(" .;:*0-9")
                words = part.split()
                looks_like_a_name = 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Z][\w'.-]*", w) for w in words)
                if looks_like_a_name and not EMAIL.search(part) and part not in out:
                    out.append(part)
    return out
