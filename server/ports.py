"""Which ports THIS checkout serves on, derived from where the checkout is.

THE STORE IS ALREADY PER-CHECKOUT AND THE PORT WAS NOT. THAT MISMATCH IS THE WHOLE BUG.
`store/files.py:home()` defaults to `REPO_ROOT` — the checkout the code is running from — so
every worktree has its own `inventory/`, its own `runs/` and its own `captures/`. The capture
server's port was the bare constant 8000 in every one of them, and `app/src/server.ts` asked
for `http://localhost:8000` no matter which tree served it.

So the app in tree A talks to whichever server won the bind, and that server writes to ITS
tree's store. Both directions are wrong and one of them loses data:

  * a worktree's UI drives the owner's real 767-card inventory, or
  * the MAIN tree's UI — the one the owner actually captures from — is answered by a
    worktree's server and writes photographs into a directory that is deleted with the
    worktree.

`app/tests/inventory.spec.ts` already had the first half written down: "an unstubbed read is
a request to whatever is listening on port 8000, which in this repo is the owner's actual
capture server over their actual 767-card inventory." That comment is a bug report nobody
had filed. The port has to follow the store, because the store is the thing being addressed.

DERIVED, NOT ALLOCATED, AND THE SAME SLOT AS THE DEV PORT. `app/devPort.ts` already solved
this for Vite and Playwright and this is its other half; the derivation is deliberately
identical so there is one rule rather than two spellings, and both ports share ONE slot so a
tree reads as a pair — 5285 beside 8185. An allocator handing out the next free port would
answer differently every run, and `strictPort` could then not tell "someone else is here"
from "I moved".

THE MAIN WORKING TREE KEEPS 8000, exactly as it keeps 5173, so nothing about the ordinary
single-checkout workflow changes and every doc that names the number stays true.

TWO IMPLEMENTATIONS OF ONE ALGORITHM, WHICH IS A DRIFT RISK AND IS TESTED RATHER THAN
TRUSTED. Python serves and TypeScript addresses, and neither can import the other. They agree
because `scripts/port-agreement.py` runs both over the same paths and diffs them, in `make
check`. A seam asserted beats a seam assumed — this repo's own lesson, from the multi-game
prompt field that would have parsed cleanly and joined nothing.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

PORT_ENV = "PKMNSCAN_PORT"

REPO_ROOT = Path(__file__).resolve().parents[1]

# The main tree's numbers. Both are load-bearing prose: CLAUDE.md, the Makefile's help and
# docs/specs all name them, and scripts/views.txt points the screenshot runner at 5173.
CAPTURE_BASE_PORT = 8000
DEV_BASE_PORT = 5173

# One slot per checkout, two ports from it. The bands are far enough apart that a tree's
# pair is readable at a glance and neither can collide with the other's range.
CAPTURE_LOW = 8100
DEV_LOW = 5200
SLOTS = 300


def is_linked_worktree(root: Path) -> bool:
    """A linked worktree's `.git` is a FILE, not a directory.

    The same one fact `app/devPort.ts`, `scripts/worktree-guard.sh` and
    `scripts/docs-audit.py` all detect on, spelled the same way on purpose. No `.git` at all
    — a tarball, a container copy, a CI checkout that stripped it — behaves like the main
    tree, because inventing a port for a checkout with no identity to derive one from is
    worse than the documented default.
    """
    try:
        return (root / ".git").is_file()
    except OSError:
        return False


def slot_for(root: Path) -> int:
    """This checkout's slot, 0..SLOTS-1.

    sha256 of the resolved absolute path, first four bytes big-endian, modulo the band. The
    TypeScript twin does exactly this, and `scripts/port-agreement.py` is what proves it
    still does. `resolve()` rather than `absolute()` so a path reached through a symlink
    hashes the same as the path itself — `/tmp` is a symlink to `/private/tmp` on this
    machine and one worktree genuinely lives under it.
    """
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % SLOTS


def _port(root: Path, base: int, low: int) -> int:
    return base if not is_linked_worktree(root) else low + slot_for(root)


def capture_port(root: Path = REPO_ROOT) -> int:
    """The port `make server` binds and the app addresses.

    `PKMNSCAN_PORT` overrides, the same knob and the same shape as `PKMNSCAN_HOME` — where
    this server listens is the operator's call, and the Fulfiller's device reaching this Mac
    by address is the case `docs/specs/capture-app.md` §11 leaves open. An unparseable or
    out-of-range value is IGNORED rather than obeyed: a typo in an env var must not put the
    server somewhere no client will look, which is this whole module's failure mode arriving
    by another road.
    """
    override = os.environ.get(PORT_ENV, "").strip()
    if override:
        try:
            value = int(override)
        except ValueError:
            value = 0
        if 1 <= value <= 65535:
            return value
    return _port(root, CAPTURE_BASE_PORT, CAPTURE_LOW)


def dev_port(root: Path = REPO_ROOT) -> int:
    """The Vite port for this checkout. Python's read of `app/devPort.ts`'s answer.

    Nothing in the Python tree serves on it. It exists so `make status` and the SessionStart
    guard can PRINT both of a tree's ports without shelling out to node, and so the agreement
    test has something to compare on the dev side as well — the two derivations sharing a
    slot is the property most likely to be broken by an edit to one of them.
    """
    return _port(root, DEV_BASE_PORT, DEV_LOW)
