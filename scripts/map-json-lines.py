#!/usr/bin/env python3
"""Write the `docs/map/` lines for this repo's tracked json files, with the decisions each one carried.

THE REMEDY FOR THE DEBT `DEBT120`. The shared map check reads every tracked file whose
extension is in `map.config.json`'s `codeExtensions`, so adding `json` there stalls it on the large json
files outside `mapPaths`. Once the shared check reads only `mapPaths`: add `json` to `codeExtensions`, run
this script with `--write`, then run `make map-check`.

    scripts/map-json-lines.py            print the lines it would add, and write nothing
    scripts/map-json-lines.py --write    add them, each in the page and the sorted place its neighbours have

A json file under `mapPaths` that already has a map line is left alone, so a second run adds nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = (("app/src/", "app-src"), ("app/tests/", "app-tests"), ("app/", "app-root"),
         ("geometry/", "geometry"), ("scripts/", "scripts"))

# One plain sentence for each json file. A number outside backticks fails MAP9, so none appears here.
TXT = {
    "app/package-lock.json": "The locked dependency tree of the app, written by npm.",
    "app/package.json": "The app's npm manifest: its dependencies and the scripts the Makefile runs.",
    "app/src/kit/didyoumean.cases.json": "The case table for the did-you-mean suggester: a query, the names on offer and the expected suggestion.",
    "app/src/kit/match.cases.json": "The one case table for `kit/match.ts`: query, fields and the expected verdict, one row per rule the matcher states.",
    "app/tests/copy-casing-allow.json": "The pending list of casing findings, route to finding to lane. It starts empty and only shrinks.",
    "app/tests/copy-voice-allow.json": "The pending list of first-person strings, route to finding to lane. It starts empty and only shrinks.",
    "app/tests/machine-words-allow.json": "The shrinking pending list `text-checks.spec.ts` reads, route to word or path to lane, with no wildcard.",
    "app/tests/money-face-allow.json": "The shrinking pending list `text-checks.spec.ts` reads, route to amount to lane. An entry excuses one figure on one route.",
    "app/tests/request-budget-allow.json": "The shrinking list `request-budget.spec.ts` reads, rule and route to measurement. A screen on it is measured and not failed.",
    "app/tests/stability-allow.json": "The shrinking list `stability.spec.ts` reads, case and route to reason. A screen on it is measured and not failed.",
    "app/tests/text-shape-allow.json": "The shrinking pending list `text-checks.spec.ts` reads, route to assertion to finding key to lane.",
    "app/tsconfig.json": "The TypeScript compiler settings for the app.",
    "geometry/model/labels.json": "Corner labels on the owner's rig photographs, the first batch, with rejected rows dropped at build.",
    "geometry/model/labels_new.json": "Corner labels on the owner's rig photographs, the last batch.",
    "scripts/browser-spec-times.json": "The measured run time of each Playwright spec, which `scripts/browser-scope.py` reads to split the browser shards.",
    "scripts/commands-internal.json": "The make targets that exist for CI or for another target and are not for a person to run, each with the reason.",
    "scripts/error-words-allow.json": "The shrinking offender list for the error-words row: file to the start of a message to the lane that owes it.",
    "scripts/fixed-sleep-allow.json": "The browser specs allowed to keep a fixed sleep, each with its count and reason.",
    "scripts/kit-adoption-allow.json": "The shrinking offender list for `scripts/kit-adoption.mjs` (static, file to rule to lane) and `app/tests/scaffold.spec.ts` (runtime, route to assertion to lane).",
    "scripts/layout-transition-allow.json": "The layout properties allowed to transition, by file, selector and property, each with its reason.",
    "scripts/machine-words-allow.json": "The shrinking offender list for the no-mechanism-on-screen row, file to word to lane.",
    "scripts/machine-words.json": "The word list for the no-mechanism-on-screen row, and `repoTopDirs`, the repository's top directories. The audit and `app/tests/text-checks.spec.ts` both read it.",
    "scripts/markdown-spelling-allow.json": "The shrinking offender list for the identifier-spelling row, markdown half: file to lane, and spelling to the British words that file uses.",
    "scripts/motion-literal-allow.json": "The files allowed to carry a raw motion literal. It holds none.",
    "scripts/no-owner-quotes-allow.json": "The shrinking offender list for the no-owner-quotes row: file to lane, and marker to one marker per occurrence in `docs/`.",
    "scripts/token-literal-allow.json": "The files allowed to carry a raw token literal. It holds none.",
    "scripts/token-literal-check.json": "The per-file ceiling of the token-literal ratchet, written by `scripts/token-literal-check-pin.py`.",
    "scripts/typed-interpunct-allow.json": "The shrinking offender list for the typed-interpunct row: file to lane, and the strings that type a middle dot or bullet.",
}

# The decision ids each file carried before the map file was retired. A file absent here carried none.
IDS = {
    'app/src/kit/match.cases.json': ['D5'],
    'app/tests/machine-words-allow.json': ['D196', 'D274', 'D284'],
    'app/tests/money-face-allow.json': ['D221', 'D284'],
    'app/tests/request-budget-allow.json': ['D207'],
    'app/tests/stability-allow.json': ['D313'],
    'app/tests/text-shape-allow.json': ['D284'],
    'geometry/model/labels.json': ['D125'],
    'geometry/model/labels_new.json': ['D125'],
    'scripts/error-words-allow.json': ['D22', 'D32', 'D58', 'D91', 'D196', 'D284'],
    'scripts/machine-words-allow.json': ['D196', 'D284'],
    'scripts/machine-words.json': ['D1', 'D2', 'D9', 'D11', 'D24', 'D58', 'D63', 'D86', 'D87', 'D99', 'D273', 'D174', 'D181', 'D196', 'D260', 'D284'],
    'scripts/markdown-spelling-allow.json': ['D60', 'D280'],
    'scripts/no-owner-quotes-allow.json': ['D280', 'D318', 'D100', 'D136', 'D141', 'D287', 'D103', 'D134', 'D145', 'D155', 'D162', 'D164', 'D176', 'D179', 'D213', 'D220', 'D241', 'D242', 'D254', 'D259', 'D260', 'D264', 'D271', 'D272', 'D273', 'D291', 'D293', 'D296', 'D299', 'D300', 'D301', 'D307'],
    'scripts/typed-interpunct-allow.json': ['D41', 'D218', 'D280'],
}


def main(argv) -> int:
    write = "--write" in argv
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    missing = [f for f in TXT if f not in tracked]
    if missing:
        print("not tracked any more, so no line: " + ", ".join(missing), file=sys.stderr)
    mapped = set()
    for page in (ROOT / "docs" / "map").glob("*.md"):
        mapped.update(re.findall(r"^- `([^`]+)` — ", page.read_text(encoding="utf-8"), re.M))
    added = 0
    for path, sentence in sorted(TXT.items()):
        if path in missing or path in mapped:
            continue
        page = ROOT / "docs" / "map" / (next(name for prefix, name in PAGES if path.startswith(prefix)) + ".md")
        lines = page.read_text(encoding="utf-8").split("\n")
        new = [f"- `{path}` — {sentence}"]
        if IDS.get(path):
            new.append("  - Decisions: " + ", ".join(f"`{d}`" for d in IDS[path]))
        start = lines.index("## Code files")
        at = None
        for i in range(start + 1, len(lines)):
            if lines[i].startswith("## "):
                at = i
                while lines[at - 1] == "":
                    at -= 1
                break
            found = re.match(r"^- `([^`]+)` — ", lines[i])
            if found and found.group(1) > path:
                at = i
                break
        if at is None:
            at = len(lines)
            while lines[at - 1] == "":
                at -= 1
        print(f"{page.name}: {new[0][:100]}")
        added += 1
        if write:
            lines[at:at] = new
            page.write_text("\n".join(lines), encoding="utf-8")
    print(f"{added} line(s) {'added' if write else 'would be added'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
