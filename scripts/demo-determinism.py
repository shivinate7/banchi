#!/usr/bin/env python3
"""Whether `make demo` writes the same `app/demo/bundle.json` twice.

THE FAILURE THIS EXISTS TO CATCH IS INVISIBLE TO `demo-freshness.py`. That check compares a
digest of the WIRE SHAPE (`app/src/types.ts`, `app/src/server.ts`) against what the bundle
was recorded against — it proves the bundle still fits the contract, never that the bundle's
own CONTENT is the one `docs/specs/demo.md` §4 promises: "an unchanged tree rebuilds the
store byte-identically." Measured (review round, identity-follows-sku.md lane 6, before
`Inventory.bind_sku` grew its `at` parameter): 97 `bound_at` values differed between two
`make demo` runs, over a store built from one fixed `SEED`/`NOW`, and `demo-freshness` was
green through every one of them — a real `now()` stamp reached the recorded wire from inside
the one writer `scripts/demo-seed.py` is supposed to control every field of.

WHAT THIS COMPARES. Two full `make demo` runs, each into its own scratch `PKMNSCAN_HOME`
(never the checkout's real `demo/`, never the owner's — D43), `app/demo/bundle.json` copied
out between them (its path is fixed by `scripts/demo-record.py:BUNDLE`, not derived from
`PKMNSCAN_HOME`, so the two runs would otherwise overwrite one file), then diffed as JSON:
every leaf value that moved is reported by its own JSON pointer.

A MOVED POINTER IS NOT AUTOMATICALLY A FAILURE. A handful are known, named, and OUT OF
SCOPE for this check — request-time and process-time stamps that have nothing to do with the
seed's own determinism:

  - `changed_at` / `updated_at` on `/orders`, `/pipeline/runs*` and `/pipeline/pricing*` —
    the order ledger's own ingest stamp and a run directory's REAL, unfaked mtime, both
    downstream of `./pkmnscan join` actually touching disk a second later on the second run.
  - `modified` under `/pipeline/runs/demo-box1` and `/pipeline/runs/demo-box3` — the same
    run-directory mtime, read a second way.
  - `boot_id` / `started_at` on `/status`, and `batch` on `POST /shipping/batches` — the
    RECORDING SERVER's own process identity and the shipping batch id it mints per request,
    neither one a fact `demo-seed.py` writes at all.
  - `at` under `/orders`' own `progress` entries, and `written_at` under `/pipeline/pricing*`
    — FOUND BY THIS CHECK, NOT NAMED IN THE REVIEW ROUND THAT ASKED FOR IT. `store/
    orders.py:record_pull` stamps `stored.at = now()` unconditionally, with no override
    parameter (`scripts/demo-seed.py` calls it for two of the seven demo orders); `written_at`
    is `pipeline/pricing.json`'s own write moment, from the SAME real `./pkmnscan join` runs
    `docs/specs/demo.md` §4 already documents as genuinely real. Neither writer is `bind_sku`
    or touched by lane 6's diff — both are the SAME class of pre-existing, out-of-scope stamp
    as the six above, surfaced only because this check compares structure rather than a hand
    read of a diff. Not fixed here, on the same ruling that left the first six alone.

EVERY ALLOWED POINTER IS MATCHED BY ITS WHOLE PATH, NOT BY A BARE KEY ANYWHERE IN IT —
`ALLOWED_PATTERNS` (identity-follows-sku.md lane 7's own fix) is a vocabulary of "shapes of
pointer", not a vocabulary of "kinds of key". The check used to be `ALLOWED_KEYS`, a flat set
of names tested against every SEGMENT of a pointer (`ALLOWED_KEYS & set(pointer.split("/"))`)
— so a bare `at` excused an `at` ANYWHERE in the tree, whatever it sat beside, which is not
what "an order's own ingest stamp" or "a run directory's mtime" meant to claim. A future
writer that stamped `at` on something `scripts/demo-seed.py` does NOT hold fixed — an event
line, a new record — would have been excused by the same bare key, silently, and this check
exists specifically to catch a stamp like that reaching the wire. `written_at` sitting one
level ABOVE the run name it is keyed by (`.../pipeline/pricing/body/written_at/demo-box1`) is
why each pattern below matches the run segment with a wildcard rather than the literal name —
a ninth run would otherwise need a new pattern for no reason — never why the check reads
bare keys. A pointer matching no pattern in `ALLOWED_PATTERNS` fails the run: that is a value
`scripts/demo-seed.py` is supposed to hold fixed, moving anyway.

NOT IN `make check` (D18, docs/specs/demo.md's own rule for every `demo-*` target: a
generator may write, and nothing that writes may gate a commit — `demo-freshness` is off it
for the identical reason). Two full seed-and-record passes are real time; `make
demo-determinism` runs it by hand, or in a session verifying a change to `demo-seed.py` or to
any writer it calls (`Inventory.bind_sku`/`record_identification`, first among them).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, List, Pattern, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "app" / "demo" / "bundle.json"

# The shapes of pointer this check already knows are request-time or process-time, never the
# seed's own data — see the module docstring for what each one is and why. Each pattern
# `fullmatch`es the WHOLE pointer, so a bare key never excuses a pointer that only happens to
# contain it somewhere else in the tree (the defect lane 7 of identity-follows-sku.md fixed:
# `ALLOWED_KEYS` used to be a flat set of keys tested against every segment). `[^/]+` stands
# in for a run name or a list index — never a literal, so a ninth run or a longer list needs
# no new entry — and every pattern is anchored on `/responses/` because that is the one place
# a request/process-time stamp can reach the wire from.
ALLOWED_PATTERNS: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("orders: the order ledger's own ingest stamp",
     re.compile(r"^/responses//orders/body/orders/\d+/changed_at$")),
    ("orders: a walk's own progress stamp",
     re.compile(r"^/responses//orders/body/orders/\d+/progress/\d+/at$")),
    ("pipeline pricing: a SKU's own reading time",
     re.compile(r"^/responses//pipeline/pricing(?:\?[^/]*)?/body/roster/\d+/updated_at$")),
    ("pipeline pricing: a run's own reading time",
     re.compile(r"^/responses//pipeline/pricing(?:\?[^/]*)?/body/runs/\d+/updated_at$")),
    # `written_at` sits one level ABOVE the run name it is keyed by
    # (`.../pipeline/pricing/body/written_at/demo-box1`) — the module docstring's own example.
    ("pipeline pricing: the join's own write moment, keyed by run",
     re.compile(r"^/responses//pipeline/pricing(?:\?[^/]*)?/body/written_at/[^/]+$")),
    ("pipeline runs: the runs list's own reading time",
     re.compile(r"^/responses//pipeline/runs/body/runs/\d+/updated_at$")),
    ("pipeline runs: a run directory's real, unfaked file mtime",
     re.compile(r"^/responses//pipeline/runs/demo-box[13]/body/files/\d+/modified$")),
    ("pipeline runs: a run directory's manifest mtime",
     re.compile(r"^/responses//pipeline/runs/demo-box[13]/body/manifest/updated_at$")),
    ("pipeline runs: a run directory's real, unfaked mtime",
     re.compile(r"^/responses//pipeline/runs/demo-box[13]/body/updated_at$")),
    ("status: the recording server's own boot id",
     re.compile(r"^/responses//status/body/boot_id$")),
    ("status: the recording server's own start moment",
     re.compile(r"^/responses//status/body/started_at$")),
    ("shipping: the batch id this request mints",
     re.compile(r"^/responses/POST /shipping/batches/body/batch$")),
)


def _allowed(pointer: str) -> str:
    """The name of the `ALLOWED_PATTERNS` entry `pointer` matches whole, or `""`."""
    for name, pattern in ALLOWED_PATTERNS:
        if pattern.match(pointer):
            return name
    return ""


def _diff(before: Any, after: Any, pointer: str, out: List[Tuple[str, Any, Any]]) -> None:
    """Every leaf where `before` and `after` disagree, as `(json_pointer, before, after)`."""
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _diff(
                before.get(key, "<absent>"), after.get(key, "<absent>"),
                "%s/%s" % (pointer, key), out,
            )
        return
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for index, (b, a) in enumerate(zip(before, after)):
            _diff(b, a, "%s/%d" % (pointer, index), out)
        return
    if before != after:
        out.append((pointer, before, after))


def _run_demo(home: str) -> Path:
    """One full `make demo` into a scratch `PKMNSCAN_HOME`, returning a COPY of the bundle
    it wrote — copied out because `BUNDLE`'s path does not vary with `home`, so the next call
    would otherwise overwrite it before this one is read."""
    subprocess.run(
        ["make", "demo", "DEMO_HOME=%s" % home], cwd=REPO_ROOT, check=True,
        stdout=subprocess.DEVNULL,
    )
    if not BUNDLE.exists():
        raise SystemExit("demo determinism: `make demo DEMO_HOME=%s` wrote no bundle" % home)
    copy = REPO_ROOT / (".demo-determinism-%s.json" % home)
    copy.write_bytes(BUNDLE.read_bytes())
    return copy


def main() -> int:
    homes = ("demo-determinism-a", "demo-determinism-b")
    copies: List[Path] = []
    try:
        for home in homes:
            copies.append(_run_demo(home))

        before = json.loads(copies[0].read_text())
        after = json.loads(copies[1].read_text())
        moved: List[Tuple[str, Any, Any]] = []
        _diff(before, after, "", moved)

        # By WHOLE PATH, never a bare key anywhere in it — see the module docstring for why.
        unexpected = [(p, b, a) for p, b, a in moved if not _allowed(p)]

        print("demo determinism: %d value(s) moved between two `make demo` runs, %d expected "
              "(request/process-time stamps), %d NOT expected"
              % (len(moved), len(moved) - len(unexpected), len(unexpected)))
        if unexpected:
            print("  UNEXPECTED — these are the seed's own data and should have been fixed "
                  "by `SEED`/`NOW`:")
            for pointer, before_v, after_v in unexpected[:40]:
                print("    %s: %r -> %r" % (pointer, before_v, after_v))
            if len(unexpected) > 40:
                print("    … and %d more" % (len(unexpected) - 40))
            return 1

        print("  every moved value matches a known request/process-time shape:")
        for name, _ in ALLOWED_PATTERNS:
            print("    - %s" % name)
        print("  the seed's own data is byte-identical across both runs.")
        return 0
    finally:
        for copy in copies:
            copy.unlink(missing_ok=True)
        for home in homes:
            shutil.rmtree(REPO_ROOT / home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
