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

  4. THE TWO FALLBACKS that do not use the derivation. `app/src/server.ts` bundled with NO
     port define, with `fetch` stubbed, must refuse by name and address no base port. A copy
     of `scripts/screenshot.sh` that cannot derive its port may fall back to 5173 only in a
     primary checkout. Neither arm loads a page or opens a socket.

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


def client_fallback_answers(tmp: Path) -> dict:
    """Bundle the real `app/src/server.ts` WITHOUT `vite.config.ts`'s port define, and ask it.

    This is the bundle `FALLBACK_BASE` exists for. `fetch` is a stub that records the URL and
    rejects, so this opens no socket, on the old code or the new. The answer is every URL the
    client tried, the code a read refused with, and one photo URL.
    """
    bundle = tmp / "server-no-define.mjs"
    esbuild = ROOT / "app" / "node_modules" / ".bin" / "esbuild"
    built = subprocess.run(
        [str(esbuild), str(ROOT / "app" / "src" / "server.ts"), "--bundle", "--format=esm",
         "--platform=neutral", "--define:__BN_DEMO__=false", "--define:import.meta.env={}",
         "--external:./demoServer", f"--outfile={bundle}", "--log-level=error"],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if built.returncode != 0:
        raise SystemExit(
            "esbuild could not bundle app/src/server.ts — the client fallback is unproven,\n"
            "which is not the same as safe:\n" + (built.stderr.strip() or "(no stderr)")
        )
    script = (
        "const calls = [];\n"
        "globalThis.fetch = (url) => { calls.push(String(url));"
        " return Promise.reject(new Error('stub')); };\n"
        "const m = await import(%s);\n"
        "let code = null;\n"
        "try { await m.getStatus(); } catch (err) { code = err && err.code; }\n"
        "console.log(JSON.stringify({ calls, code, photo: m.photoUrl(1, 1) }));\n"
        % json.dumps(bundle.as_uri())
    )
    done = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=str(tmp), capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            "node could not run the bundled client — the fallback is unproven:\n"
            + (done.stderr.strip() or "(no stderr)")
        )
    return json.loads(done.stdout.strip().splitlines()[-1])


def screenshot_refuses(tmp: Path, kind: str) -> bool:
    """Run a copy of `scripts/screenshot.sh` in a tree that CANNOT derive its port.

    The tree has no `server/ports.py`, so the derivation fails and the fallback decides. It
    has no `app/node_modules`, so a run that does not refuse stops at that check, before any
    render. No page loads either way. True when the script refused for the port.
    """
    tree = tmp / f"shot-{kind}"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "screenshot.sh", tree / "scripts" / "screenshot.sh")
    if kind == "primary":
        (tree / ".git").mkdir()
    elif kind == "linked":
        (tree / ".git").write_text("gitdir: /nowhere/.git/worktrees/copy\n", encoding="utf-8")
    done = subprocess.run(
        ["bash", str(tree / "scripts" / "screenshot.sh")],
        cwd=str(tree), capture_output=True, text=True, check=False, timeout=60,
    )
    return done.returncode != 0 and "dev port could not be derived" in done.stderr


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

        # The client bundle with no port define: it must refuse, and never call a base port.
        client = client_fallback_answers(Path(tmp))
        live = (f":{ports.CAPTURE_BASE_PORT}", f":{ports.DEV_BASE_PORT}")
        for url in client["calls"] + [client["photo"]]:
            if any(port in url for port in live):
                failures.append(
                    f"a client bundle with no port define addresses {url}, the PRIMARY "
                    f"checkout's live port (D-no-git-no-live-port, a copied tree never gets "
                    f"the live port)"
                )
        if client["calls"]:
            failures.append(
                f"a client bundle with no port define fetched {client['calls']} — it must "
                f"refuse before any request"
            )
        if client["code"] != "no_server_address":
            failures.append(
                f"a client bundle with no port define refused with {client['code']!r}, "
                f"want 'no_server_address'"
            )

        # The screenshot runner's fallback: only a primary checkout may fall back to 5173.
        for kind in TREE_KINDS:
            refused = screenshot_refuses(Path(tmp), kind)
            if refused != (kind != "primary"):
                failures.append(
                    f"{kind} tree: scripts/screenshot.sh "
                    f"{'refused' if refused else 'fell back to the base dev port'} when it "
                    f"could not derive its port; only the primary checkout may fall back"
                )

        if failures:
            print("port agreement: FAILED")
            for line in failures:
                print(f"  {line}")
            return 1

        print(
            f"port agreement: {len(as_strings)} paths, slots identical; "
            f"this checkout dev {ports.dev_port()} / capture {ports.capture_port()} on both "
            f"sides; {len(trees)} copied trees ({', '.join(TREE_KINDS)}) answer their own kind; "
            f"a client with no port define refuses; screenshot.sh falls back only when primary"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
