#!/usr/bin/env python3
"""Record a demo store's wire answers into a fixture bundle the static app replays.

THE SEAM THIS EXISTS FOR. `app/src/server.ts` makes exactly one `fetch` — every one of its
84 client functions funnels through `request()` — and every stored photograph is addressed
by one `photoUrl(box, index)`. So two functions are the whole surface between this product
and its capture server, and swapping them for a recording turns the real app into a static
one without a mock of anything above them. The screens, the kit, the shell and the router
are the SAME CODE the owner runs; only the wire is frozen.

WHY RECORDED RATHER THAN HAND-AUTHORED. Fixtures written by hand drift from `types.ts` and
contradict each other — a card on the pricing screen that is in no box, a listing whose SKU
no card holds. Recording a real server over a real store cannot produce either: whatever
the app reads, the server composed out of one store, so the bundle is internally consistent
by construction and re-recording is how it stays that way.

WHAT IS SWEPT. Reads only. Every GET the client can build (`request(` in `server.ts`),
crossed with the parameter space of the store actually in front of us — every box, every
card, every run, every order. Writes are NOT recorded: `app/src/demoServer.ts` applies
those to its own copy of the snapshot, because a demo where pressing the button does
nothing teaches the opposite of what this product is.

    PKMNSCAN_HOME=demo ./scripts/demo-record.py

Spawns its own capture server on its own port and stops it again, so it neither needs nor
disturbs `make up` — which on the main checkout is the owner's live server over their real
store, and is never this script's to touch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from demo_scrub import audit, replacements, scrub  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BUNDLE = REPO_ROOT / "app" / "demo" / "bundle.json"
PHOTO_OUT = REPO_ROOT / "app" / "public" / "demo" / "photos"
APP_SERVER_TS = REPO_ROOT / "app" / "src" / "server.ts"
APP_TYPES_TS = REPO_ROOT / "app" / "src" / "types.ts"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


# ------------------------------------------------------------------------ the wire hash


def wire_digest() -> str:
    """A digest of the contract this bundle was recorded against.

    `types.ts` declares every shape on the wire and `server.ts` every path that can be
    asked for, so a change to either is a change this recording may no longer cover. The
    staleness check compares this against the tree; that is the whole mechanism, and it
    exists because a stale bundle fails BLANK rather than loudly — a screen reading a field
    the recording predates renders empty, and nothing else in this repo would notice.
    """
    digest = hashlib.sha256()
    for path in (APP_TYPES_TS, APP_SERVER_TS):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


# --------------------------------------------------------------------------- the server


class Server:
    """The capture server, spawned on its own port over the demo store and stopped after.

    NOT `make up`. That target's supervisor is the owner's live server on the main
    checkout, kept alive at login by `make launch-agent` over their real inventory —
    CLAUDE.md is explicit that it is not a session's to restart, and a recorder that
    bounced it would take their store offline to build a demo.
    """

    def __init__(self, home: Path, port: int) -> None:
        self.home = home
        self.port = port
        self.base = "http://127.0.0.1:%d" % port
        self.process: Optional[subprocess.Popen] = None

    def __enter__(self) -> "Server":
        env = dict(os.environ)
        env["PKMNSCAN_HOME"] = str(self.home)
        env["PKMNSCAN_PORT"] = str(self.port)
        self.process = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "server" / "capture_server.py")],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.process.poll() is not None:
                out = self.process.stdout.read().decode("utf-8", "replace")
                raise SystemExit("capture server exited before answering:\n%s" % out)
            try:
                urllib.request.urlopen(self.base + "/status", timeout=1).read()
                return self
            except Exception:
                time.sleep(0.25)
        raise SystemExit("capture server did not answer /status within 30s")

    def __exit__(self, *exc) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def get(self, path: str):
        """One GET, as (status, parsed body). A 404 is data, not a crash — the sweep asks
        for paths this build of the server may not answer, and which ones those are is
        exactly what the coverage report at the end is for."""
        try:
            with urllib.request.urlopen(self.base + path, timeout=30) as response:
                body = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            status = exc.code
        except Exception as exc:
            return None, {"error": str(exc)}
        try:
            return status, json.loads(body)
        except ValueError:
            return status, None


# ---------------------------------------------------------------------------- the sweep


def parameter_space(home: Path) -> Dict[str, List[str]]:
    """Every value the client could put in a path, read off the store itself.

    Read from the store rather than listed here, so a seed that grows a fifth box is swept
    without this file being touched. A hand-kept list is the same defect the route census
    exists to catch, one lane over.
    """
    os.environ["PKMNSCAN_HOME"] = str(home)
    from store import Store  # imported late: it reads PKMNSCAN_HOME at call time

    snapshot = Store().read()
    boxes = sorted({str(int(b.box)) for b in snapshot.inventory.boxes.values()})
    cards = sorted(
        {"%d/%d" % (int(c.box), int(c.index)) for c in snapshot.inventory.cards.values()}
    )
    games = sorted({c.game for c in snapshot.inventory.cards.values() if c.game})
    # Search terms a viewer would plausibly type — a name they can see on a card in the
    # demo, plus a number and a bare SKU, because those are three different code paths
    # through `do_search` and a demo that only covers one leaves two blank.
    named = [c.name for c in snapshot.inventory.cards.values() if c.name]
    terms = sorted({n.split(" ")[0] for n in named})[:12]
    # EVERY SKU, not a sample. `#/inventory`'s card panel searches the store for the SELECTED
    # card's SKU to find its other copies, so a sample covers the sampled cards and answers
    # `demo_not_recorded` on every other one — which is what it did, on the first card
    # clicked. The responses are small; completeness here is worth the kilobytes.
    skus = sorted({c.sku for c in snapshot.inventory.cards.values() if c.sku})
    numbers = sorted({c.number for c in snapshot.inventory.cards.values() if c.number})[:8]
    return {
        "boxes": boxes,
        "cards": cards,
        "games": games,
        "search": terms + skus + numbers,
        "orders": sorted(snapshot.ledger.orders.keys()),
    }


def sweep(server: Server, space: Dict[str, List[str]]):
    """Every GET the client can build, against every parameter the store holds.

    The path list mirrors `request(` in `app/src/server.ts` — the GET half of it. Writes
    are deliberately absent; `demoServer.ts` owns those.
    """
    recorded: Dict[str, dict] = {}
    skipped: List[str] = []

    def take(path: str) -> None:
        status, body = server.get(path)
        if status is None or body is None:
            return
        # 200s ONLY. The sweep deliberately asks for paths this server may not answer with a
        # GET — `/inventory/<box>/<index>` is a PUT surface, and the app reads a card out of
        # the whole-store payload — so a 404 here means "not a read", not "a read that
        # failed". Recording one would teach `demoServer.ts` to answer a live route with a
        # stored error, which is worse than not answering it at all.
        if status != 200:
            skipped.append("%s -> %d" % (path, status))
            return
        recorded[path] = {"status": status, "body": body}

    # Whole-store reads. `/inventory` is the big one and the app asks for it on nearly
    # every screen, which is what makes a recording worth having at all.
    for path in (
        "/status", "/games", "/boxes", "/inventory", "/queues", "/pricing",
        "/orders", "/codes", "/codes/lots", "/pipeline/runs", "/pipeline/markdowns",
        "/pipeline/pricing", "/shipping/batches",
    ):
        take(path)

    for box in space["boxes"]:
        take("/boxes/%s" % box)
        take("/boxes/%s/listings" % box)
        take("/boxes/%s/photos" % box)
        take("/inventory/%s" % box)

    for key in space["cards"]:
        take("/inventory/%s" % key)

    for game in space["games"]:
        take("/tcg/sets?game=%s" % urllib.parse.quote(game))

    for term in space["search"]:
        take("/search?q=%s" % urllib.parse.quote(term))

    # Every run the runs screen lists, and its scope — the free preflight D76 draws before
    # the money gate is anywhere near being pressed.
    runs = recorded.get("/pipeline/runs", {}).get("body") or {}
    names = []
    if isinstance(runs, dict):
        for entry in runs.get("runs") or []:
            # `"run"`, NOT `"name"` — `server/pipeline_routes.py:_summary` keys the run's
            # directory name as `run`. Reading `name` collected nothing, silently: the sweep
            # recorded no run detail at all and the demo answered `demo_not_recorded` the
            # first time anybody clicked a run. Found by clicking one.
            if isinstance(entry, dict) and entry.get("run"):
                names.append(str(entry["run"]))
    for name in names:
        quoted = urllib.parse.quote(name)
        take("/pipeline/runs/%s" % quoted)
        take("/pipeline/runs/%s/scope" % quoted)

    return recorded, skipped


# -------------------------------------------------------------------------- photographs


def copy_photos(home: Path) -> int:
    """The seed's drawn cards, into where Vite will bundle them.

    `photoUrl(box, index)` composes `${base}/photo/${box}/${index}` against the capture
    server; the demo build points it at this directory instead. Copied rather than served,
    because the whole object of the exercise is a build with no server behind it.
    """
    source = home / "captures" / "cards"
    if PHOTO_OUT.exists():
        shutil.rmtree(PHOTO_OUT)
    if not source.is_dir():
        return 0
    written = 0
    for photo in sorted(source.glob("box*/*.jpg")):
        box = photo.parent.name.replace("box", "")
        # Named by the STORE index, undecorated — `photoUrl` composes `/photo/3/17`, and a
        # zero-padded stem here would need the client to know the padding. D52: the URL
        # names a photograph, and the demo keeps that exact contract.
        target = PHOTO_OUT / box / ("%d.jpg" % int(photo.stem))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(photo, target)
        written += 1
    return written


# ------------------------------------------------------------------------------- entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=os.environ.get("PKMNSCAN_HOME", "demo"))
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve()
    if not (home / "inventory" / "store.sqlite").exists():
        raise SystemExit(
            "no demo store at %s — run `make demo-seed` first." % (home / "inventory")
        )

    space = parameter_space(home)
    port = free_port()
    with Server(home, port) as server:
        recorded, skipped = sweep(server, space)

    photos = copy_photos(home)

    pairs = replacements(REPO_ROOT, home)
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wire": wire_digest(),
        "routes": len(recorded),
        "photos": photos,
        # NO `recorded_at`. A wall-clock stamp would make every rebuild a diff even when
        # nothing changed, and the whole value of a deterministic seed is that an unchanged
        # tree produces an unchanged bundle — which is what lets CI publish on every push
        # without churning the repo.
        "responses": scrub(recorded, pairs),
    }
    document = json.dumps(payload, indent=1, sort_keys=True) + "\n"

    # The scrubber checks its own work over the finished document rather than trusting the
    # walk to have visited every branch. This bundle is published; a step that cannot prove
    # the result is clean is not one to leave running unattended in CI.
    leaks = audit(document)
    if leaks:
        raise SystemExit(
            "refusing to write %s — %d machine path(s) survived scrubbing:\n  %s"
            % (BUNDLE.name, len(leaks), "\n  ".join(leaks))
        )
    BUNDLE.write_text(document)

    size = BUNDLE.stat().st_size / 1024.0
    print("recorded %d routes (%.0f KB) and %d photographs" % (len(recorded), size, photos))
    print("  bundle  %s" % BUNDLE.relative_to(REPO_ROOT))
    print("  photos  %s" % PHOTO_OUT.relative_to(REPO_ROOT))
    print("  wire    %s" % payload["wire"])
    if skipped:
        print("  %d path(s) answered no GET and were not recorded:" % len(skipped))
        shapes = sorted({"".join("N" if ch.isdigit() else ch for ch in entry) for entry in skipped})
        for shape in shapes[:8]:
            print("    %s" % shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
