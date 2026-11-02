#!/usr/bin/env python3
"""The waiting page's database, as a committed record (D-waiting-page-export).

Protects: any account can read the page's items, answers and groups from the repo, and no secret reaches it.
Governs: D-waiting-page-export

THE PAGE'S DATA LIVES IN THE ARTIFACT'S DATABASE, AND ONLY CLAUDE CAN READ IT. ArtifactData is a
tool call, not an API a script can reach. So the export is two halves. The page writer reads each
collection with ArtifactData `list` and `out_dir` into a fresh, empty scratch folder. This script
turns that folder into `docs/waiting/`, after a scan for secrets and personal data. A hit writes
nothing, so a secret never reaches the working tree.

    scripts/waiting-export.py --calls            the page URL and the four reads to make
    scripts/waiting-export.py <scratch-dir>      scan, then write docs/waiting/*.json
    scripts/waiting-export.py --selftest         red on a fake token, green on a clean export

Exit 0: written or unchanged (it prints which). Exit 1: a scan hit, or a malformed folder.
Cost: one python process per wake, four files written at most, no network. Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
EXTRAS = ROOT / ".claude" / "layout-extras.json"
RECORDS = ROOT / "docs" / "waiting"
COLLECTIONS = ("items", "answers", "groups", "meta")

# A hit names the kind and where, never the matched text.
PATTERNS = (
    ("github token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{20,})"),
    ("api key", r"\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|[sr]k_live_[A-Za-z0-9]{10,}|AIza[\w-]{30,})"),
    ("aws key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("jwt", r"\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"),
    ("private key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("bearer token", r"(?i)\b(?:bearer|basic)\s+[\w.~+/=-]{20,}"),
    # No leading \b: a .env name such as TCG_TRACKING_KEY ends the word on `_`, not before it.
    # After `:` the value needs a digit, so prose like "the join key: number_index_key" passes.
    # A `$NAME` or `{expr}` value is a reference, not a secret.
    ("password or key value",
     r"(?i)(?:password|passwd|secret|key|token|cookie|clearance)"
     r"(?:\s*=\s*['\"]?(?![$\{])|\s*:\s*['\"]?(?![$\{])(?=[^\s'\"<>]*\d))[^\s'\"<>]{8,}"),
    ("cookie", r"(?i)(?:\bset-cookie\s*:|\bcookie\s*:\s*\w+=|\b(?:sessionid|csrftoken|sid)=[\w%.-]{16,})"),
    ("email address", r"[\w.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]"),
    ("phone number", r"(?<![\w.-])(?:\+1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?![\w.-])"),
    # Case-sensitive: street words are capitalized or all caps, so "3 records in place" and
    # "5 cards in this lane" pass.
    ("street address",
     r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:(?:[A-Z][a-z]+|[A-Z]+|\d+(?:st|nd|rd|th))\s+){1,3}"
     r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Pl|Place"
     r"|ST|STREET|AVE|AVENUE|RD|ROAD|BLVD|DR|DRIVE|LN|LANE|CT|COURT|PL|PLACE)\b"
     r"|\bP\.?O\.? Box \d+|\b[A-Z][a-z]+, [A-Z]{2} \d{5}\b"),
)
COMPILED = tuple((name, re.compile(rx)) for name, rx in PATTERNS)


def page_url() -> str:
    return json.loads(EXTRAS.read_text())["waiting-page"]


def read_folder(scratch: Path) -> Dict[str, dict]:
    """`{collection: {doc_id: document}}` from ArtifactData's `<out_dir>/<collection>/<id>.json`.

    An empty collection leaves no folder, so it reads as `{}`. A folder with no `meta/page.json`
    is not an export, and is refused.
    """
    if not (scratch / "meta" / "page.json").is_file():
        raise SystemExit(f"waiting-export: {scratch} holds no meta/page.json, so it is not an export")
    out: Dict[str, dict] = {}
    for name in COLLECTIONS:
        folder = scratch / name
        out[name] = {p.stem: json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))} if folder.is_dir() else {}
    return out


def scan(value, where: str, hits: List[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            scan(key, f"{where} key", hits)
            scan(item, f"{where}.{key}", hits)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            scan(item, f"{where}[{i}]", hits)
    elif isinstance(value, str):
        hits.extend(f"{name} in {where}" for name, rx in COMPILED if rx.search(value))


def render(docs: dict) -> str:
    return json.dumps(docs, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export(scratch: Path, records: Path, url: str) -> int:
    data = read_folder(scratch)
    data["meta"] = {"documents": data["meta"], "source": url}
    hits: List[str] = []
    for name in COLLECTIONS:
        scan(data[name], name, hits)
    if hits:
        print("waiting-export: STOPPED, nothing written. The scan found:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        print("Remove it from the page's database, read again, and rerun.", file=sys.stderr)
        return 1
    records.mkdir(parents=True, exist_ok=True)
    changed = []
    for name in COLLECTIONS:
        path = records / f"{name}.json"
        text = render(data[name])
        if not path.is_file() or path.read_text() != text:
            path.write_text(text)
            changed.append(path.name)
    print("waiting-export: changed " + ", ".join(changed) if changed else "waiting-export: unchanged")
    return 0


def calls() -> None:
    url = page_url()
    print(f"page: {url}")
    print("Read each into one fresh, empty folder: ArtifactData list, query.limit 1000, "
          "out_dir <folder>, and page with next_cursor until none comes back.")
    for name in COLLECTIONS:
        print(f"  collection {name}")
    print("Then: python3 scripts/waiting-export.py <folder>")


def selftest() -> int:
    def fixture(base: Path, context: str) -> Path:
        for rel, doc in {
            "meta/page.json": {"writer": "banchi-coordinator"},
            "items/one.json": {"id": "one", "n": 1, "status": "open", "context": context},
        }.items():
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
            (base / rel).write_text(json.dumps(doc))
        return base

    failures: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Built at run time so no literal token sits in this file.
        fake_token = "ghp_" + "x" * 36
        red_records = tmp_path / "red-out"
        if export(fixture(tmp_path / "red", f"use {fake_token} here"), red_records, "u") != 1:
            failures.append("a fake token did not stop the export")
        if red_records.exists():
            failures.append("a stopped export still wrote files")
        for label, text in (("email", "mail a@b.co"), ("private key", "-----BEGIN RSA PRIVATE KEY-----"),
                            ("address", "ship to 12 Elm Street"), ("password", "password: hunter22"),
                            (".env line", "TCG_TRACKING_KEY=" + "a1" * 8),
                            ("upper-case address", "123 N MAIN ST APT 4"),
                            ("city line", "Austin, TX 78701"), ("phone", "+1-512-555-0142"),
                            ("ordinal address", "400 W 5th St"), ("po box", "PO Box 1234"),
                            ("basic auth", "Authorization: Basic " + "dXNlcjpw" * 3),
                            ("stripe key", "sk_" + "live_" + "a1" * 8),
                            ("google key", "AIza" + "B2" * 17),
                            ("bare cookie", "cf_clearance=" + "c3" * 8)):
            if export(fixture(tmp_path / label.replace(" ", "-"), text), tmp_path / "x", "u") != 1:
                failures.append(f"a fake {label} did not stop the export")

        # This repo's own idioms, each once a false alarm.
        for text in ("Rewrite 3 records in place", "5 cards in this lane", "Back up 5 files to iCloud Drive",
                     "The join key: number_index_key", "cache key: sku:game:number", "API_KEY=$TCG_KEY", "key={selectedRow.key}",
                     "Order 12345 shipped, so 12345 items remain", "token budget per lane"):
            hits: List[str] = []
            scan(text, "idiom", hits)
            if hits:
                failures.append(f"ordinary text {text!r} raised {hits}")

        green_records = tmp_path / "green-out"
        if export(fixture(tmp_path / "green", "Pick a price source; see item 70 and PR 971."),
                  green_records, "u") != 0:
            failures.append("a clean export was stopped")
        written = sorted(p.name for p in green_records.glob("*.json"))
        if written != sorted(f"{n}.json" for n in COLLECTIONS):
            failures.append(f"a clean export wrote {written}")
        elif json.loads((green_records / "answers.json").read_text()) != {}:
            failures.append("an empty collection did not write {}")
        before = {p.name: p.stat().st_mtime_ns for p in green_records.glob("*.json")}
        export(tmp_path / "green", green_records, "u")
        if before != {p.name: p.stat().st_mtime_ns for p in green_records.glob("*.json")}:
            failures.append("an unchanged export rewrote files")
    for failure in failures:
        print(f"waiting-export selftest: FAIL {failure}", file=sys.stderr)
    print("waiting-export selftest: " + ("FAIL" if failures else "PASS"))
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--selftest"]:
        return selftest()
    if args == ["--calls"]:
        calls()
        return 0
    if len(args) == 1 and not args[0].startswith("-"):
        return export(Path(args[0]), RECORDS, page_url())
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
