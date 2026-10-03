#!/usr/bin/env python3
"""`make tests-page` — writes docs/TESTS.md: what each test file protects, in one plain sentence.

The owner could not see what the tests protect, or whether the rule under a test still
stands. Every test file now carries a `Protects:` line and a `Governs:` line in its own header
comment. This script reads those lines and writes one page, grouped by area. The page flags each
test whose `Governs:` cites a decision the corpus marks as superseded (`decisions_corpus.py`'s
`supersession`, the one home for that fact).

THE ROSTER. Browser specs (`app/tests/*.spec.ts`), unit tests (`app/tests/unit/*.unit.ts`), harness tests (`harness/tests/t*.py`) and
the dedicated self-test files (`scripts/*-selftest.py`, `scripts/*-selftest.sh`). A guard whose
self-test lives inside its own script is not in the roster.

D18: this script writes, so it never runs on the commit path. `make docs-audit`'s `test purposes`
row calls `render()` and compares. It never calls `--write`.

    scripts/tests_page.py            print the page
    scripts/tests_page.py --write    write docs/TESTS.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import decisions_corpus  # noqa: E402

PAGE = ROOT / "docs" / "TESTS.md"
TIERS = """## Test tiers

| Tier | Run by | Holds |
| --- | --- | --- |
| Unit | `make unit`, in `make check` | `app/tests/unit/*.unit.ts`. Logic or data with no layout and no real interaction. Playwright's runner, no browser, no dev server. The whole tier stays under 10 s. |
| Browser | `make design-check` | `app/tests/*.spec.ts`. Anything that needs a page: a measured size, position or computed style, a click, key, focus or drag, a timer or the router running in a page. |
| Python | `make harness`, the self-tests | `harness/tests/`, `scripts/*-selftest.py`. |

**A test belongs in the unit tier when its verdict is the same if no page ever drew.** A pure function, a table read from `ROUTES` or a JSON file, a parser, a judge fed arrays. If the answer depends on layout, on a real interaction, or on wiring that only a page has, it stays in the browser tier. A unit-tested function still gets one browser case that proves the page calls it (the tab title is the pilot: the function is `tests/unit/tab-title.unit.ts`, the shell stamping it is one case in `scaffold.spec.ts`). Existing browser tests move only when a lane is named for them.
"""

ROSTER_GLOBS = (
    "app/tests/*.spec.ts",
    "app/tests/unit/*.unit.ts",
    "harness/tests/t*.py",
    "scripts/*-selftest.py",
    "scripts/*-selftest.sh",
)
HEADER_LINES = 80
_LINE = re.compile(r"^\s*(?://|#|\*)?\s*(Protects|Governs):[ \t]+(.+?)\s*$")
_ID = re.compile(r"\bD[1-9][0-9]{0,2}\b")

# First match wins. A file no rule names lands in UNFILED, and the audit row refuses it.
AREAS: Tuple[Tuple[str, str], ...] = (
    ("Capture", r"capture-|motion|dispenser|t9_traces"),
    ("Review and identity", r"review|absent-photo|confirm-identity|correct-answer|card-variants|t1_|t3_|t4_"),
    ("Inventory and boxes", r"inventory|boxmap|empty-section|section-ruler|locating|deleted-boxes|t7_"),
    ("Pricing and runs", r"pricing|product-history|live-reconcile|run-panel|photo-cache|t5_|t2_"),
    ("Orders, sales and shipping", r"orders|order-walk|shipping|revenue|home|t11_"),
    ("The Fulfiller's screen", r"fulfillment|pull-confirm"),
    ("Shell, kit and layout", r"nav|themes|stability|scaffold|page-edge|status-busy|phone|wide|cursor|icon-button|button-stack|filters|filter-standard|kit-data|gallery|brand|^match|did-you-mean|tab-title|t6_"),
    ("Text and money checks", r"machine-words|money|text-shape|text-checks"),
    ("Public demo", r"demo-"),
    ("Code cards", r"t8_"),
    ("Store, identity and prices", r"cid-|holdings|identity-|sku|readings|price|archive|submission|repair-born|catalog-index|stockimages|pipeline-trends|pricehistory"),
    ("Repository guards and tooling", r"claim-|githooks|guard-shell|hand-search|janitor|merge-|reap-|serve-|silent-write|subagent|sync-|verdict|worktree-provision"),
)
UNFILED = "Unfiled (add a rule to AREAS in scripts/tests_page.py)"


def roster() -> List[Path]:
    out: List[Path] = []
    for pattern in ROSTER_GLOBS:
        out.extend(sorted(ROOT.glob(pattern)))
    return out


def area_of(path: Path) -> str:
    stem = path.name
    for name, rx in AREAS:
        if re.search(rx, stem):
            return name
    return UNFILED


def header(path: Path) -> Dict[str, str]:
    """The `Protects:` and `Governs:` lines from the top of a file. Missing keys are absent."""
    found: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").split("\n")[:HEADER_LINES]:
        m = _LINE.match(line)
        if m and m.group(1) not in found:
            found[m.group(1)] = m.group(2)
    return found


def governs(head: Dict[str, str]) -> List[str]:
    return _ID.findall(head.get("Governs", ""))


def flags(ids: List[str]) -> List[str]:
    out = []
    for ident in ids:
        s = decisions_corpus.supersession(ident)
        if s:
            out.append(f"{ident} {'in part ' if s['kind'] == 'part' else ''}superseded by {s['by']}")
    return out


def render() -> str:
    rows: Dict[str, List[Tuple[str, str, List[str]]]] = {}
    flagged: List[Tuple[str, List[str]]] = []
    for path in roster():
        rel = path.relative_to(ROOT).as_posix()
        head = header(path)
        ids = governs(head)
        sentence = head.get("Protects", "(no Protects line)").replace("|", "\\|")
        rows.setdefault(area_of(path), []).append((rel, sentence, ids))
        f = flags(ids)
        if f:
            flagged.append((rel, f))
    total = sum(len(v) for v in rows.values())
    out = [
        "Generated by `make tests-page` from each test file's own `Protects:` and `Governs:` header lines. Never hand-edit. Edit the header, then run it again.",
        "",
        "# What each test protects",
        "",
        f"{total} test files. One sentence each, grouped by area. `Governs:` names the decisions the test relies on.",
        "",
        "## Tests that cite a superseded decision",
        "",
    ]
    if flagged:
        out.append("Each test below still cites a decision that the corpus marks as superseded. A whole supersession means the test relies on a repealed rule. \"In part\" means the entry still stands except for the part the later entry names. For each, check that the test relies on the part that stands, and move its header to the live decision if not.")
        out.append("")
        for rel, f in flagged:
            out.append(f"- `{rel}`: {'; '.join(f)}")
    else:
        out.append("None.")
    out += ["", TIERS.rstrip("\n")]
    order = [n for n, _ in AREAS] + [UNFILED]
    for area in order:
        if area not in rows:
            continue
        out += ["", f"## {area}", "", "| File | Protects | Governs |", "| --- | --- | --- |"]
        for rel, sentence, ids in rows[area]:
            out.append(f"| `{rel}` | {sentence} | {', '.join(ids) or 'none'} |")
    return "\n".join(out) + "\n"


def main(argv: List[str]) -> int:
    text = render()
    if "--write" in argv:
        PAGE.write_text(text, encoding="utf-8")
        print(f"wrote {PAGE.relative_to(ROOT)}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
