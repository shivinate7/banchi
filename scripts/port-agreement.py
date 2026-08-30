#!/usr/bin/env python3
"""Prove `server/ports.py` and `app/devPort.ts` still answer the same numbers.

WHY THIS EXISTS. D43 puts one algorithm in two languages because neither side can import the
other: Python SERVES the capture port and TypeScript ADDRESSES it, and the whole point of the
decision is that they agree about which port this checkout owns. If they ever disagree the
failure is silent and total — the app asks for a port nothing is listening on, or worse, one
ANOTHER tree is listening on, which is the exact defect D43 was written to remove.

This repo has been bitten by an unasserted cross-language seam before and the entry is in
`docs/GATES.md`: two new game prompts named their identifier field differently from what
`cli/resolve.py` read, which would have parsed cleanly, recorded cleanly, and handed the join
a card with `number=None` — `no_catalog_row` for every card in the run, blaming the export.
"The seam is now asserted end to end" is the lesson; this is the same shape.

WHAT IT COMPARES, and it is deliberately two different things:

  1. THE SLOT, over real directories. `slot_for` / `slotFor` are pure functions of a path, so
     they can be fed the same inputs directly. REAL directories rather than invented strings,
     because both sides canonicalise through realpath and a path that does not exist
     canonicalises differently in the two languages — Python's `Path.resolve()` resolves the
     existing prefix of a missing path while Node's `realpathSync` throws and this falls back
     to the raw string. Half these cases live under the temp dir precisely because `/tmp` is a
     symlink to `/private/tmp` on this machine, which is the case that would expose it.

  2. THE PORTS, on THIS checkout only. `capturePort()` reads its own module URL and takes no
     argument, so the composed answer — base, band and slot together — can only be compared
     where both sides are looking at the same tree. That is one case, and it is the case that
     matters: it is the pair a running `make server` and a running `make dev` actually use.

WHAT IT DOES NOT COVER, said plainly rather than implied by a green run: the main tree's
branch of the derivation is asserted against the documented constants on the Python side only,
because proving TypeScript's requires running it from a checkout whose `.git` is a directory
and this test does not move itself between trees.

Stdlib only, and it never writes outside the temporary directory it creates and destroys.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import ports  # noqa: E402

CASES = 12


def node_answers(paths: list[str]) -> dict:
    """Run the real `app/devPort.ts` — never a copy of it — and read back its answers."""
    script = (
        "const m = await import(%s);\n"
        "const paths = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify({\n"
        "  slots: paths.map((p) => m.slotFor(p)),\n"
        "  devPort: m.DEV_PORT,\n"
        "  capturePort: m.CAPTURE_PORT,\n"
        "}));\n" % json.dumps((ROOT / "app" / "devPort.ts").as_uri())
    )
    done = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script,
         json.dumps(paths)],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            "node could not evaluate app/devPort.ts — the agreement is unproven, which is\n"
            "not the same as agreed:\n" + (done.stderr.strip() or "(no stderr)")
        )
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkmnscan-ports.") as tmp:
        roots = []
        for index in range(CASES):
            path = Path(tmp) / f"tree-{index:02d}"
            path.mkdir()
            roots.append(path)
        # The real checkout too: the one path anybody actually derives a port from.
        roots.append(ROOT)
        as_strings = [str(path) for path in roots]

        theirs = node_answers(as_strings)
        mine = [ports.slot_for(path) for path in roots]

        failures = []
        for path, want, got in zip(as_strings, mine, theirs["slots"]):
            if want != got:
                failures.append(f"slot disagrees for {path}: python {want}, node {got}")

        for label, want, got in (
            ("capture port", ports.capture_port(), theirs["capturePort"]),
            ("dev port", ports.dev_port(), theirs["devPort"]),
        ):
            if want != got:
                failures.append(f"{label} disagrees for this checkout: python {want}, node {got}")

        # The main-tree branch, Python side. One-sided and the docstring says so.
        main_tree = Path(tmp) / "main-like"
        main_tree.mkdir()
        (main_tree / ".git").mkdir()
        if ports.capture_port(main_tree) != ports.CAPTURE_BASE_PORT:
            failures.append("a checkout whose .git is a DIRECTORY must answer the base port")

        if failures:
            print("port agreement: FAILED")
            for line in failures:
                print(f"  {line}")
            return 1

        print(
            f"port agreement: {len(as_strings)} paths, slots identical; "
            f"this checkout dev {ports.dev_port()} / capture {ports.capture_port()} on both sides"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
