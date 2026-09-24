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

  3. THE THREE KINDS OF TREE, on COPIES (D-no-git-no-live-port, a copied tree never gets
     the live port). Both files are copied into three throwaway trees, and each copy is asked
     for its OWN default ports, through the same module-location read a real build makes:
       - `.git` a DIRECTORY, the primary checkout: 8000 and 5173, on both sides.
       - `.git` a FILE, a linked worktree: its band plus its slot, on both sides.
       - NO `.git`, a scratch copy or an exported tree: its band plus its slot, on both
         sides, and NEVER 8000 or 5173. On 2026-09-23 a copy of main with no `.git` built
         an app that called the owner's live server on 8000. This arm holds that case.
     A copy, not a path fed to a function, because the incident was the module reading where
     it LIVES. Only a copy reaches that read.

Stdlib only, and it never writes outside the temporary directory it creates and destroys.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import ports  # noqa: E402

CASES = 12


# The three kinds of tree the derivation must tell apart, by what sits at `<root>/.git`.
TREE_KINDS = ("primary", "linked", "no-git")


def node_answers(paths: list[str], copies: list[str]) -> dict:
    """Run the real `app/devPort.ts`, and each COPY of it, and read back their answers.

    `copies` are the `app/devPort.ts` files inside the throwaway trees. Each one is imported
    from where it sits, so its `DEV_PORT` and `CAPTURE_PORT` are what a build from that tree
    would bake.
    """
    script = (
        "const m = await import(%s);\n"
        "const paths = JSON.parse(process.argv[1]);\n"
        "const copies = JSON.parse(process.argv[2]);\n"
        "const trees = [];\n"
        "for (const url of copies) {\n"
        "  const c = await import(url);\n"
        "  trees.push({ devPort: c.DEV_PORT, capturePort: c.CAPTURE_PORT });\n"
        "}\n"
        "console.log(JSON.stringify({\n"
        "  slots: paths.map((p) => m.slotFor(p)),\n"
        "  devPort: m.DEV_PORT,\n"
        "  capturePort: m.CAPTURE_PORT,\n"
        "  trees,\n"
        "}));\n" % json.dumps((ROOT / "app" / "devPort.ts").as_uri())
    )
    done = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script,
         json.dumps(paths), json.dumps([Path(c).as_uri() for c in copies])],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            "node could not evaluate app/devPort.ts — the agreement is unproven, which is\n"
            "not the same as agreed:\n" + (done.stderr.strip() or "(no stderr)")
        )
    return json.loads(done.stdout.strip().splitlines()[-1])


def build_tree(tmp: Path, kind: str) -> Path:
    """A throwaway tree holding copies of both files, with `.git` shaped by `kind`."""
    tree = tmp / f"copy-{kind}"
    (tree / "server").mkdir(parents=True)
    (tree / "app").mkdir()
    shutil.copy2(ROOT / "server" / "ports.py", tree / "server" / "ports.py")
    shutil.copy2(ROOT / "app" / "devPort.ts", tree / "app" / "devPort.ts")
    # `app/package.json` says `"type": "module"`. The copy needs the same, or node reads
    # `import.meta` in a CommonJS scope.
    (tree / "app" / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    if kind == "primary":
        (tree / ".git").mkdir()
    elif kind == "linked":
        (tree / ".git").write_text("gitdir: /nowhere/.git/worktrees/copy\n", encoding="utf-8")
    return tree


def python_answers(tree: Path) -> dict:
    """Load the COPY of `server/ports.py` and read its no-argument answers.

    The copy's `REPO_ROOT` is the copy's own tree, as it is for a server started there.
    `PKMNSCAN_PORT` is set aside for the call: it is an override, and this reads the
    derivation under it.
    """
    spec = importlib.util.spec_from_file_location(
        f"ports_copy_{tree.name.replace('-', '_')}", tree / "server" / "ports.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = os.environ.pop(ports.PORT_ENV, None)
    try:
        return {
            "devPort": module.dev_port(),
            "capturePort": module.capture_port(),
            "slot": module.slot_for(tree),
        }
    finally:
        if saved is not None:
            os.environ[ports.PORT_ENV] = saved


def expected(kind: str, slot: int) -> tuple:
    """(dev, capture) a tree of this kind must answer. The constants are the module's own."""
    if kind == "primary":
        return ports.DEV_BASE_PORT, ports.CAPTURE_BASE_PORT
    return ports.DEV_LOW + slot, ports.CAPTURE_LOW + slot


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

        trees = [build_tree(Path(tmp), kind) for kind in TREE_KINDS]
        theirs = node_answers(as_strings, [str(t / "app" / "devPort.ts") for t in trees])
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

        # The three kinds of tree, each a copy asked for its own default ports.
        for kind, tree, node_tree in zip(TREE_KINDS, trees, theirs["trees"]):
            py_tree = python_answers(tree)
            want_dev, want_capture = expected(kind, py_tree["slot"])
            for side, got in (("python", py_tree), ("node", node_tree)):
                if (got["devPort"], got["capturePort"]) != (want_dev, want_capture):
                    failures.append(
                        f"{kind} tree: {side} answers dev {got['devPort']} / capture "
                        f"{got['capturePort']}, want dev {want_dev} / capture {want_capture}"
                    )
                if kind != "primary" and (
                    got["capturePort"] == ports.CAPTURE_BASE_PORT
                    or got["devPort"] == ports.DEV_BASE_PORT
                ):
                    failures.append(
                        f"{kind} tree: {side} answers the PRIMARY checkout's live port. A "
                        f"build here would call the owner's live server "
                        f"(D-no-git-no-live-port, a copied tree never gets the live port)"
                    )

        if failures:
            print("port agreement: FAILED")
            for line in failures:
                print(f"  {line}")
            return 1

        print(
            f"port agreement: {len(as_strings)} paths, slots identical; "
            f"this checkout dev {ports.dev_port()} / capture {ports.capture_port()} on both "
            f"sides; {len(trees)} copied trees ({', '.join(TREE_KINDS)}) answer their own kind"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
