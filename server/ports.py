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
single-checkout workflow changes and every doc that names the number stays true. ONLY the
main working tree keeps them: a tree must show a `.git` DIRECTORY to get the base ports, and
a tree with no `.git` takes a slot like a linked worktree (D-no-git-no-live-port, a copied
tree never gets the live port).

TWO IMPLEMENTATIONS OF ONE ALGORITHM, WHICH IS A DRIFT RISK AND IS TESTED RATHER THAN
TRUSTED. Python serves and TypeScript addresses, and neither can import the other. They agree
because `scripts/port-agreement.py` runs both over the same paths and diffs them, in `make
check`. A seam asserted beats a seam assumed — this repo's own lesson, from the multi-game
prompt field that would have parsed cleanly and joined nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

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

# THE SLOT REGISTRY (D-a-claimed-slot-and-a-server-that-names-its-checkout). A hash into 300
# slots is not "every checkout has its own ports". Two live worktrees on this Mac hashed into
# one slot on 2026-09-24, and a design-check in one of them tested the other's code, green.
# So a checkout may CLAIM a slot, once, in one machine-wide file keyed by its resolved path.
# The derivation READS the file and never writes it. `scripts/port-slots.py claim` is the one
# writer. A missing, unreadable or malformed file, or no entry for this path, reads as "not
# claimed", and the hash answers as before. `app/devPort.ts` reads the same file the same way.
SLOT_REGISTRY_ENV = "PKMNSCAN_SLOT_REGISTRY"
SLOT_REGISTRY_NAME = "port-slots.json"


def is_linked_worktree(root: Path) -> bool:
    """A linked worktree's `.git` is a FILE, not a directory.

    The same one fact `scripts/worktree-guard.sh` and `scripts/docs-audit.py` detect on,
    spelled the same way on purpose. `scripts/serve.py` and `scripts/status.py` call it to
    ask "is this a linked worktree?" and nothing else.

    THE PORT DOES NOT ASK THIS QUESTION ANY MORE (D-no-git-no-live-port, a copied tree never
    gets the live port). A tree with no `.git` is not a linked worktree, and this answers
    False for it, as it always did. The port used to read that False as "the primary
    checkout" and gave such a tree 8000. `is_primary_checkout` below is the question the
    port asks now.
    """
    try:
        return (root / ".git").is_file()
    except OSError:
        return False


def is_primary_checkout(root: Path) -> bool:
    """The primary checkout's `.git` is a DIRECTORY. Only this tree keeps 8000 and 5173.

    D-no-git-no-live-port, a copied tree never gets the live port. On 2026-09-23 a scratch
    copy of main with no `.git` built an app. The old rule read "no `.git`" as "the primary
    checkout", so that app called 8000, the owner's LIVE capture server, and read the real
    store. Any press there would have written to it.

    So the base port is kept by the one tree that proves it is a primary checkout: a
    `.git` directory. Everything else takes a slot from its own path, as a linked worktree
    does. That covers a tarball, a container copy, a copy without its `.git`, and a failed
    stat. A wrong guess here now costs a moved port, never a write to the owner's store.

    A plain `cp -r` copies `.git` too, and so does a second clone. Such a tree IS a primary
    checkout of its own and still gets 8000. That is an accepted risk, recorded in the
    decision entry.

    `app/devPort.ts:isPrimaryCheckout` is its twin, and `make port-agreement` asks both
    of them over a copy of each kind of tree.
    """
    try:
        return (root / ".git").is_dir()
    except OSError:
        return False


def slot_registry() -> Optional[Path]:
    """Where the claimed slots are recorded. `PKMNSCAN_SLOT_REGISTRY` overrides.

    The default sits beside D122's machine-wide suite lock, under `~/.pkmnscan/`, because a
    slot is a fact about this machine and not about any one checkout. None when there is no
    home directory to find, and then nothing is claimed.
    """
    override = os.environ.get(SLOT_REGISTRY_ENV, "").strip()
    if override:
        return Path(override)
    try:
        return Path.home() / ".pkmnscan" / SLOT_REGISTRY_NAME
    except (RuntimeError, KeyError, OSError):
        return None


def canonical(root: Path) -> str:
    """The one spelling of a checkout's path that the hash and the registry both key on."""
    return str(root.resolve())


def hashed_slot(root: Path) -> int:
    """The slot the path alone derives, 0..SLOTS-1. Used when no slot is claimed.

    sha256 of the resolved absolute path, first four bytes big-endian, modulo the band. The
    TypeScript twin does exactly this, and `scripts/port-agreement.py` is what proves it
    still does. `resolve()` rather than `absolute()` so a path reached through a symlink
    hashes the same as the path itself — `/tmp` is a symlink to `/private/tmp` on this
    machine and one worktree genuinely lives under it.
    """
    digest = hashlib.sha256(canonical(root).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % SLOTS


def read_claims(registry: Optional[Path] = None) -> dict:
    """Every claimed slot, `{canonical path: slot}`. Empty when the file cannot be read.

    Only whole-number slots inside the band are kept, so a hand-edited or damaged entry reads
    as "not claimed" and never as a port outside the band.
    """
    path = registry if registry is not None else slot_registry()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    slots = data.get("slots") if isinstance(data, dict) else None
    if not isinstance(slots, dict):
        return {}
    return {
        key: value for key, value in slots.items()
        if isinstance(key, str) and type(value) is int and 0 <= value < SLOTS
    }


def claimed_slot(root: Path) -> Optional[int]:
    """This checkout's claimed slot, or None when it has claimed none."""
    return read_claims().get(canonical(root))


def slot_for(root: Path) -> int:
    """This checkout's slot, 0..SLOTS-1: the claimed slot if there is one, else the hash.

    `app/devPort.ts:slotFor` is the twin, and `scripts/port-agreement.py` proves the two
    answer the same over the same registry.
    """
    claimed = claimed_slot(root)
    return claimed if claimed is not None else hashed_slot(root)


def _port(root: Path, base: int, low: int) -> int:
    return base if is_primary_checkout(root) else low + slot_for(root)


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


def agent_label(root: Path = REPO_ROOT) -> str:
    """The LaunchAgent's label for this checkout — `make launch-agent` installs under it.

    THE LABEL FOLLOWS THE PATH EXACTLY AS THE PORT FOLLOWS THE STORE, and it is here rather
    than in `scripts/serve.py` for that reason: it is the same `slot_for` answering the same
    question about which checkout this is, and a second derivation of that would be a second
    thing to keep in step. Two checkouts installing one label would have the later one
    silently replace the earlier's agent.

    `scripts/port-agreement.py` compares `slot_for`, `capture_port` and `dev_port` across the
    two languages and is untouched by this — `app/devPort.ts` has no reason to know about
    launchd, so this is deliberately Python-only and the agreement test stays a comparison of
    the three things both sides really do compute.
    """
    return f"com.pkmnscan.serve.{slot_for(root)}"
