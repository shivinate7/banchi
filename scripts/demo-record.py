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

RESUMABLE (PR 4B lane M). A real mirror sweep over hundreds of routes can run for minutes,
and it used to lose everything if it was killed partway. Each route's answer now lands in
`WorkArea` — a gitignored cache under `.demo-record-work/<key>/` — the instant it is taken,
keyed by a digest of the store's own content (`snapshot_key`). A re-run over the SAME store
skips every route already there; a DIFFERENT store starts over, because its key differs.

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
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from demo_scrub import audit, replacements, scrub  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BUNDLE = REPO_ROOT / "app" / "demo" / "bundle.json"
PHOTO_OUT = REPO_ROOT / "app" / "public" / "demo" / "photos"
APP_SERVER_TS = REPO_ROOT / "app" / "src" / "server.ts"
APP_TYPES_TS = REPO_ROOT / "app" / "src" / "types.ts"

# The resume cache (PR 4B lane M). Outside `home` on purpose — see WorkArea below.
WORK_ROOT = REPO_ROOT / ".demo-record-work"


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


# ------------------------------------------------------------------ resume, keyed by content


def snapshot_key(home: Path) -> str:
    """A content digest of the store `home` holds right now — never its mtime, and not the
    same thing as `wire_digest()` above. That one is the CODE contract (`types.ts`,
    `server.ts`); this one is the DATA a sweep over `home` would actually read.

    `inventory/store.sqlite` is the store of record (D88), and `inventory/prices.json` is
    the pricing answer beside it, kept in its own file rather than a table (D86 amended) —
    together they are what CLAUDE.md calls "the store." Hashing bytes rather than mtimes
    means a `demo-mirror.py` rebuild that recreates `home` byte-for-byte from an unchanged
    snapshot still resumes; a copy always gets a new mtime even when nothing changed.
    """
    digest = hashlib.sha256()
    for name in ("store.sqlite", "prices.json"):
        path = home / "inventory" / name
        if path.is_file():
            digest.update(b"\0%s\0" % name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


class WorkArea:
    """Where each route's answer lands the instant it is taken, so a killed sweep can
    resume instead of starting from zero (the owner: "is there anyway u can have it
    chunking so that way it's not starting from zero each time").

    LIVES OUTSIDE `home`, at a fixed, gitignored location keyed by `snapshot_key(home)`,
    never by `home`'s own path. `demo-mirror.py`'s `build()` deletes and recreates `home`
    from its snapshot on EVERY invocation, so a cache placed inside `home` would be wiped by
    the very rebuild the owner reruns after a kill. A different snapshot hashes to a
    different key and so reads an empty directory — it starts fresh, with no rule needed
    to notice the change.

    SCRUBBED BEFORE IT TOUCHES DISK, NEVER AFTER (review finding, PR 4B lane M round 2).
    `main()` used to scrub only once, over the whole assembled `recorded` dict, right
    before writing the published bundle — so nothing unscrubbed ever left the ONE process
    that read the store. This cache is a SECOND, PERSISTENT copy that survives the process
    exiting, so an order or pick route's raw body (a buyer's name, D193) must never sit
    here unscrubbed, whether or not the store it came from was already scrubbed upstream
    (`demo-mirror.py:build()`) — D295's outcome is that nothing unscrubbed sits anywhere.
    `pairs` is the same `demo_scrub.replacements()` list `main()` already computes.
    Scrubbing is a plain string replace, so scrubbing an already-scrubbed value again (the
    whole-dict pass in `main()` still runs, as a second, harmless check) changes nothing —
    idempotent by construction, which is what keeps a resumed bundle byte-identical.
    """

    def __init__(self, home: Path, pairs: Sequence[Tuple[str, str]] = ()) -> None:
        self.key = snapshot_key(home)
        self.dir = WORK_ROOT / self.key
        self.pairs = list(pairs)

    def load(self) -> Dict[str, dict]:
        """Every route this key already holds an answer for.

        A NON-JSON FILE IS NEVER COUNTED AS RECORDED. That is the shape a write leaves only
        if it was interrupted before its `save()` below completed its rename — so a route
        left in that state is asked for again, exactly as if it had never been taken.
        """
        out: Dict[str, dict] = {}
        if not self.dir.is_dir():
            return out
        for file in sorted(self.dir.glob("*.json")):
            try:
                payload = json.loads(file.read_text("utf-8"))
            except ValueError:
                continue
            out[payload["key"]] = payload["entry"]
        return out

    def save(self, key: str, entry: dict) -> None:
        """One route's answer, scrubbed, then written to a temporary name and renamed
        into place.

        THE RENAME IS THE WHOLE ATOMICITY MECHANISM. `load()` above only ever globs the
        final `.json` name, so a process killed mid-write leaves nothing but an orphan
        `.tmp` file that no glob matches — the route it was about to finish is simply
        asked for again.
        """
        scrubbed = scrub(entry, self.pairs)
        self.dir.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(json.dumps({"key": key, "entry": scrubbed}), "utf-8")
        tmp.rename(self.dir / name)

    def prune_others(self) -> int:
        """Delete every OTHER key's work area under `WORK_ROOT` — they belong to a
        snapshot nobody is resuming any more and hold data nobody needs (review finding:
        an old snapshot's routes, buyer names included, should not just sit there once a
        run has moved on to a current key). Returns how many were removed.

        Reads the module-level `WORK_ROOT` directly rather than `self.dir.parent`, so a
        test that points `self.dir` elsewhere (never touching the real cache) cannot
        accidentally make this prune somewhere it should not.
        """
        if not WORK_ROOT.is_dir():
            return 0
        pruned = 0
        for child in WORK_ROOT.iterdir():
            if child.is_dir() and child.name != self.key:
                shutil.rmtree(child)
                pruned += 1
        return pruned


# --------------------------------------------------------------------------- the server


class Server:
    """The capture server, spawned on its own port over the demo store and stopped after.

    NOT `make up`. That target's supervisor is the owner's live server on the main
    checkout, kept alive at login by `make launch-agent` over their real inventory —
    CLAUDE.md is explicit that it is not a session's to restart, and a recorder that
    bounced it would take their store offline to build a demo.
    """

    def __init__(self, home: Path, port: int, offline: bool = False) -> None:
        self.home = home
        self.port = port
        self.base = "http://127.0.0.1:%d" % port
        self.process: Optional[subprocess.Popen] = None
        self.offline = offline
        # THE HANG THIS ONCE WAS. `CaptureHandler.log_message` prints one line per request,
        # unconditionally, to this pipe. A `subprocess.PIPE` nobody reads deadlocks the
        # writer once the OS buffer (macOS: 64KB) fills — the child's own `print()` blocks
        # inside `write()`, and every OTHER thread's next `print()` blocks too, behind
        # CPython's stdout stream lock, not the pipe (measured on a real hung build,
        # 2026-09-26: `sample <pid>` showed one thread in `write()` and the rest of
        # `REQUEST_SLOTS` in `PyThread_acquire_lock_timed`). A full sweep prints thousands
        # of these lines, so this pipe WILL fill on every real run. `_log` is drained
        # continuously on its own thread for the process's whole life, never just once at
        # startup.
        self._log: List[bytes] = []
        self._drain_thread: Optional[threading.Thread] = None

    def _drain_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            self._log.append(line)
            if len(self._log) > 500:
                del self._log[:250]
        self.process.stdout.close()

    def __enter__(self) -> "Server":
        env = dict(os.environ)
        env["PKMNSCAN_HOME"] = str(self.home)
        env["PKMNSCAN_PORT"] = str(self.port)
        # THE RECORDER NEVER COMES BACK (D301). `server/pipeline_routes.py:
        # warm_stock_images` fires its background threads and returns at once for a LIVE
        # server on purpose — a real user's first request after a restart must never wait
        # on a disk read. This sweep reads every route exactly once and bakes whatever it
        # got into the published bundle forever, so a cold `url_for()` here is not "slow
        # once", it is permanently missing. This variable makes that one call join its own
        # threads before the server starts accepting requests.
        env["PKMNSCAN_STOCK_IMAGES_SYNC"] = "1"
        script = str(REPO_ROOT / "server" / "capture_server.py")
        argv = [sys.executable, script]
        if self.offline:
            argv = [sys.executable, "-c", OFFLINE_BOOT, script]
        self.process = subprocess.Popen(
            argv,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._drain_thread = threading.Thread(target=self._drain_stdout, daemon=True)
        self._drain_thread.start()
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.process.poll() is not None:
                out = b"".join(self._log).decode("utf-8", "replace")
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
        if self._drain_thread is not None:
            self._drain_thread.join(timeout=5)

    def post(self, path: str, payload: dict):
        """One POST, as (status, parsed body). Two uses, and neither writes the store.

        THREE ROUTES ARE WRITE-SHAPED READS. `/orders/picks`, `/orders/walk-plan` and
        `/inventory/copies` take a list too long for a query string, and each opens
        `Store().read()` and writes nothing (their own docstrings say so), so their answers are
        recorded exactly like a GET's — under `post_key`, see `sweep_coverage`.

        THE SHIPPING LANES ARE THE OTHER USE: a POST that puts the server into a state a GET
        can then be recorded from. `server/shipping_routes.py` holds
        a read export IN MEMORY — "what it costs is memory holding buyer addresses" — so
        there is no batch on disk for the seed to write and `GET /shipping/batches` answers
        404 until something has posted one. Every other write in this pipeline leaves a file
        the seed can produce directly.

        No write is recorded. The bundle carries reads; `app/src/demoServer.ts` owns what a
        write does.
        """
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base + path, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except Exception as exc:
            # LOUD, NEVER SWALLOWED. An `HTTPError` is the server answering (a 404 is data,
            # per `get`'s own docstring) — anything else is the request never completing at
            # all: a timeout, a reset, a refused connect. Treating that the same as a miss is
            # exactly the hang that once made a wedged server look like a slow one for 25
            # minutes (2026-09-26): every failed request silently recorded nothing and the
            # sweep just kept issuing the next one. Recorded evidence, not this file's own
            # guess, is `docs/debts/` — see the fix commit this paragraph landed in.
            raise SystemExit(
                "POST %s never completed: %s. This is a network failure, not a miss — "
                "the recording is stopped rather than silently skipping it." % (path, exc)
            ) from exc

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
            # LOUD, NEVER SWALLOWED — see `post`'s own paragraph, the same failure mode.
            raise SystemExit(
                "GET %s never completed: %s. This is a network failure, not a miss — "
                "the recording is stopped rather than silently skipping it." % (path, exc)
            ) from exc
        try:
            return status, json.loads(body)
        except ValueError:
            return status, None


# THE MIRROR'S SERVER HAS NO NETWORK (D295). A mirror holds every SKU the owner ever
# stocked, and `#/product`'s history route reads TCGplayer live for any SKU its archive lacks.
# Swept over thousands of SKUs, that is thousands of requests to a host the owner allows from
# a browser only (D216). So the server starts with every non-loopback `connect` refused,
# before its first import. A read that needed the network answers an error, is not a 200, and
# is not recorded. That is the "best effort" rule the invented demo already follows.
OFFLINE_BOOT = (
    "import os, runpy, socket, sys\n"
    "def _guard(real):\n"
    "    def connect(self, address):\n"
    "        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):\n"
    "            raise OSError('demo mirror recording is offline: refused %s' % (address[0],))\n"
    "        return real(self, address)\n"
    "    return connect\n"
    "socket.socket.connect = _guard(socket.socket.connect)\n"
    "socket.socket.connect_ex = _guard(socket.socket.connect_ex)\n"
    "sys.argv = sys.argv[1:]\n"
    "sys.path.insert(0, os.path.dirname(sys.argv[0]))\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


# ---------------------------------------------------------------------------- the sweep


def parameter_space(home: Path) -> Dict[str, object]:
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
    # EVERY SKU AN ORDER LINE NAMES, beside every SKU a card holds. `#/revenue` asks today's
    # price of what SOLD, and `#/orders` asks for the copies of what is OWED — both are read
    # off the ledger, not off a card, so the store's own SKU list could miss one.
    ordered = sorted(
        {
            str(line.sku)
            for record in snapshot.ledger.orders.values()
            for line in record.lines
            if line.sku
        }
    )
    return {
        "home": home,
        "boxes": boxes,
        "cards": cards,
        "games": games,
        "search": terms + skus + numbers,
        "skus": sorted(set(skus) | set(ordered)),
        "orders": sorted(snapshot.ledger.orders.keys()),
    }


# The wire keys a POST read is recorded under: the verb, the path, and the body as canonical
# JSON. `app/src/demoServer.ts:postKey` composes the same string, and the pair is the whole
# contract — keys sorted, no spaces, lists in the order given.
def post_key(path: str, payload: dict) -> str:
    return "POST %s %s" % (path, json.dumps(payload, sort_keys=True, separators=(",", ":")))


# `app/src/Home.tsx:DECK_DEPTH`. Home asks for exactly this many recent cards, and a recording
# at any other size would answer a question nobody asks.
RECENT_LIMIT = 3

# `app/src/types.ts:HoldingsRange`. `#/revenue`'s "Value my stock" asks one of these four.
HOLDINGS_RANGES = ("month", "quarter", "semiannual", "annual")

# `GET /pipeline/value` pages at the caller's `limit`, and `ValueBands.tsx` asks for many
# different limits (`min(PAGE, wanted)`). So each band is recorded WHOLE, once per box, and
# `demoServer.ts:valuePage` slices the page the screen asks for. The demo store holds 122
# cards, so one page of this size is every row; `sweep` refuses a band that did not fit.
VALUE_ALL = 5000
VALUE_BANDS = ("top", "bottom", "gaps")


def facet_combos(facets: dict) -> List[Dict[str, str]]:
    """Every filter `#/inventory`'s three facet menus can compose, as query pairs.

    D213's filter is three optional facets, and the owner ruled they combine in ANY order
    (FLT-09): Set and Rarity work before Game. So every facet is independently unset or one
    of the values its menu offers, and a value of null is spelled as the empty string — the
    server's own `keep_blank_values` reading, "filter for no claim".
    """
    games = [g.get("game") for g in facets.get("games") or []]
    sets: List[Optional[str]] = []
    for rows in (facets.get("sets") or {}).values():
        sets.extend(row.get("set") for row in rows)
    rarities: List[Optional[str]] = []
    for rows in (facets.get("rarities") or {}).values():
        rarities.extend(row.get("rarity") for row in rows)

    def choices(values: List[Optional[str]]) -> List[Optional[str]]:
        seen: List[Optional[str]] = []
        for value in values:
            text = "" if value is None else str(value)
            if text not in seen:
                seen.append(text)
        return [None] + seen  # None: the facet is not filtered at all

    out: List[Dict[str, str]] = []
    for game in choices(games):
        for set_name in choices(sets):
            for rarity in choices(rarities):
                combo = {}
                if game is not None:
                    combo["game"] = game
                if set_name is not None:
                    combo["set"] = set_name
                if rarity is not None:
                    combo["rarity"] = rarity
                if combo:
                    out.append(combo)
    return out


def sweep(server: Server, space: Dict[str, List[str]], work: "WorkArea"):
    """Every GET the client can build, against every parameter the store holds.

    The path list mirrors `request(` in `app/src/server.ts` — the GET half of it. Writes
    are deliberately absent; `demoServer.ts` owns those.

    RESUMABLE (PR 4B lane M). `recorded` starts loaded from `work`, so a route this key
    already holds an answer for is never asked for again — the loop below is unchanged,
    only `take` learned to check first. Each new 200 is written to `work` the moment it
    lands, not batched to the end: that is the whole point of a work area over a bare dict,
    since a killed process only ever loses the one route it was in the middle of.
    """
    recorded: Dict[str, dict] = dict(work.load())
    stats = {"resumed": len(recorded), "new": 0}
    if stats["resumed"]:
        try:
            where = work.dir.relative_to(REPO_ROOT)
        except ValueError:
            where = work.dir  # a self-test's own work area, outside this repo
        print("resume    %s: %d route(s) already recorded for this store, skipping them"
              % (where, stats["resumed"]))
    skipped: List[str] = []

    def take(path: str) -> None:
        if path in recorded:
            return
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
        entry = {"status": status, "body": body}
        recorded[path] = entry
        work.save(path, entry)
        stats["new"] += 1

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

    # THE WORKLIST, SCOPED EVERY WAY THE SCREEN CAN SCOPE IT. `#/pricing`'s Runs dropdown
    # asks `/pipeline/pricing?run=…&run=…`, repeated rather than comma-joined, and the bare
    # path is only the default. Recording the bare one alone left the dropdown dead.
    #
    # AND THE SINGLE-RUN FORMS ARE WHAT MAKE THE `t` HOLD WORK AT ALL. `Pricing.tsx` reads
    # `run = loaded.length === 1 ? loaded[0] : null`, because a price history is a per-RUN
    # route — so with two runs loaded there is no run to ask about and the panel opens onto
    # skeletons it can never fill. That is the app's own behaviour and not the demo's; what
    # the demo owes is that narrowing to one run actually works.
    for name in names:
        take("/pipeline/pricing?run=%s" % urllib.parse.quote(name))
    if len(names) > 1:
        both = "&".join("run=%s" % urllib.parse.quote(n) for n in names)
        take("/pipeline/pricing?%s" % both)

    # ------------------------------------------------------------------ the shipping lanes
    # D61's three lanes, over TCGplayer's own Export Shipping file. Created here rather than
    # seeded because a batch lives in the SERVER'S MEMORY and never on disk, so there is
    # nothing for `demo-seed.py` to write.
    #
    # `fixtures/orders-shipping.csv` IS ALREADY ANONYMISED — every row reads `Buyer001
    # Placeholder / 101 Example St` — which is what makes it publishable at all. A real
    # export is a list of buyers' home addresses and must never reach this bundle.
    # A MIRROR BRINGS ITS OWN, written by `demo-mirror.py:write_shipping_export` from the
    # mirror's own open orders, with every name "Jane Doe N" and every street "123 Demo Way".
    shipping = Path(str(space["home"])) / "shipping-export.csv"
    if not shipping.is_file():
        shipping = REPO_ROOT / "fixtures" / "orders-shipping.csv"
    if shipping.is_file():
        # THE UNIT IS THE POST PLUS ITS ONE DEPENDENT GET, NEVER THE POST ALONE (review
        # round 2). `_new_batch_id()` (`server/shipping_routes.py`) only means anything
        # inside the SERVER PROCESS that issued it — `_BATCHES` lives in memory there, and
        # is random by design ("what it cannot do is name one"). A resumed run's server is
        # a NEW process with an empty table, so a cached POST answer whose dependent GET
        # never landed points at a batch id nothing can ever look up again — caching the
        # POST alone would strand that GET forever. So the POST is trusted from the cache
        # ONLY once its GET is ALSO already cached (or the answer never named one to wait
        # for at all); short of that, BOTH are reissued against the live server, never the
        # POST by itself.
        def _shipping_get_key(body: dict) -> Optional[str]:
            batch = body.get("batch") if isinstance(body, dict) else None
            return "/shipping/batches/%s" % urllib.parse.quote(str(batch)) if batch else None

        cached_post = recorded.get("POST /shipping/batches")
        if cached_post is not None:
            cached_get_key = _shipping_get_key(cached_post.get("body"))
            # No batch named at all means there was never a dependent GET to strand.
            unit_complete = cached_get_key is None or cached_get_key in recorded
            if not unit_complete:
                del recorded["POST /shipping/batches"]  # a stranded half; reissue the unit
                cached_post = None

        if cached_post is not None:
            made = cached_post["body"]
        else:
            status, made = server.post(
                "/shipping/batches", {"content": shipping.read_text(encoding="utf-8")}
            )
            made = made if status == 200 and isinstance(made, dict) else None

        if isinstance(made, dict):
            get_key = _shipping_get_key(made)
            if get_key is not None:
                take(get_key)
            # THE UNIT IS COMPLETE ONCE ITS GET (IF ANY) HAS ALSO LANDED — persist the
            # POST now, never earlier than this. RECORDED UNDER THE VERB, because this one
            # read is a POST. There is no `GET /shipping/batches` at all — the server keeps
            # no list, so the only way to see a batch is the answer to the request that
            # made it. `demoServer.ts` replays this for the same POST, which is honest:
            # reading an export is a pure function of the file, and the demo is a frozen
            # store throughout.
            if (get_key is None or get_key in recorded) \
                    and "POST /shipping/batches" not in recorded:
                entry = {"status": 200, "body": made}
                recorded["POST /shipping/batches"] = entry
                work.save("POST /shipping/batches", entry)
                stats["new"] += 1

    # ---------------------------------------------------------------- price history
    # D278's reading, per SKU: hold `t` over a row on `#/pricing` and this is what appears.
    # Recorded for EVERY SKU in each run's pricing table, because the hold follows the
    # pointer and a sample would answer for the sampled rows and refuse the rest.
    #
    # THE ONE PART OF THIS SWEEP THAT TOUCHES A THIRD PARTY, and it is fetched at BUILD time
    # rather than tracked. `pipeline/pricehistory.py` reads two public mirrors and caches
    # under `<home>/.cache/market`; measured over this demo's two runs, that cache is 5.1 MB
    # across 140 files, which is more than the recording it produces and would go out of date
    # the day it was committed. Fetching here costs ~45s on a cold cache, spends nothing, and
    # gives the published page a CURRENT reading rather than a frozen one.
    #
    # BEST EFFORT, BY CONSTRUCTION. `take` records 200s only, so a mirror having a bad day
    # costs this demo its trend strip and nothing else — the screens already draw the absence
    # (the panel says the reading is unavailable). A publish must not fail because somebody
    # else's host is down.
    for name in names:
        quoted = urllib.parse.quote(name)
        skus = _run_skus(Path(str(space["home"])), name)
        for sku in skus:
            take("/pipeline/runs/%s/history?sku=%s" % (quoted, urllib.parse.quote(sku)))
        # The strip the "Load trends" button draws, over every SKU at once — one request in
        # the app, so one recording here, with the SKUs in the order the client sends them.
        if skus:
            query = "&".join("sku=%s" % urllib.parse.quote(s) for s in skus)
            take("/pipeline/runs/%s/trends?%s" % (quoted, query))
        # The run's own pricing table, which `getPricing(run)` reads for one run's page.
        take("/pipeline/runs/%s/pricing" % quoted)

    sweep_coverage(server, space, recorded, take, work, stats)
    return recorded, skipped, stats


def sweep_coverage(server: Server, space: Dict[str, object], recorded: Dict[str, dict], take,
                    work: "WorkArea", stats: Dict[str, int]) -> None:
    """The reads the first sweep never asked for, which left whole screens refusing.

    Every one of these was a screen a reviewer could not grade on the published page — the
    graveyard, the facet counts, the value bands, the order walk, the copies panel, the
    undo-capable writes' neighbours. Each is recorded here by the same rule as the rest of
    this file: every parameter the store in front of us can produce, 200s only.
    """
    # -------------------------------------------------------------- plain whole-store reads
    take("/graveyard")
    take("/inventory/recent?limit=%d" % RECENT_LIMIT)
    take("/pipeline/submissions")

    # ------------------------------------------------------------------ D213's facet filter
    # A Game pick on `#/inventory` asks `/boxes?game=…`, and until this was recorded every
    # box greyed out with no count (FLT-23). Every combination the three menus can make.
    facets = (recorded.get("/boxes", {}).get("body") or {}).get("facets") or {}
    for combo in facet_combos(facets):
        take("/boxes?%s" % urllib.parse.urlencode(sorted(combo.items())))

    # ------------------------------------------------------------ the value bands (D277)
    # Recorded WHOLE per band and box, and paged in the browser — see `VALUE_ALL`.
    boxes: List[Optional[str]] = [None] + list(space["boxes"])  # type: ignore[arg-type]
    for band in VALUE_BANDS:
        for box in boxes:
            pairs = [("band", band), ("limit", str(VALUE_ALL))]
            if box is not None:
                pairs.append(("box", box))
            path = "/pipeline/value?%s" % urllib.parse.urlencode(pairs)
            take(path)
            page = recorded.get(path, {}).get("body") or {}
            if page.get("next") is not None:
                raise SystemExit(
                    "%s did not fit in one page of %d rows. Raise VALUE_ALL — the demo pages "
                    "the band itself and would silently drop the rest." % (path, VALUE_ALL)
                )

    # ------------------------------------------------------------ `#/revenue`'s two presses
    for span in HOLDINGS_RANGES:
        take("/pipeline/holdings-value?range=%s" % span)
    # "Compare to today's market": one reading per SKU, merged in the browser for whatever
    # set the screen asks about — the trends index's own shape, one route over.
    for sku in space["skus"]:  # type: ignore[union-attr]
        take("/pipeline/price-now?sku=%s" % urllib.parse.quote(sku))

    # ------------------------------------------------------------------ `#/product` (D227)
    # BEST EFFORT, like the price histories above: archive first, then a live read of a
    # host that refuses an honest User-Agent (D216). A 200 is recorded; anything else is
    # left for `demoServer.ts` to refuse by name.
    for sku in space["skus"]:  # type: ignore[union-attr]
        take("/pipeline/products/%s/history" % urllib.parse.quote(sku))

    # ------------------------------------------------------------------ the POST-shaped reads
    def take_post(path: str, payload: dict) -> None:
        key = post_key(path, payload)
        if key in recorded:
            return
        status, body = server.post(path, payload)
        if status == 200 and body is not None:
            entry = {"status": 200, "body": body}
            recorded[key] = entry
            work.save(key, entry)
            stats["new"] += 1

    # Every copy of each SKU, one SKU at a time. The route answers a subset of the store
    # identically to the whole (`do_inventory_copies`), so `demoServer.ts` merges the
    # per-SKU answers for any set the Orders screen asks about.
    for sku in space["skus"]:  # type: ignore[union-attr]
        take_post("/inventory/copies", {"skus": [sku]})

    # Picks per order. `do_order_picks`: "resolving a subset of the ledger answers each of
    # those orders identically to resolving the whole thing", so these merge the same way.
    orders = list(space["orders"])  # type: ignore[arg-type]
    for key in orders:
        take_post("/orders/picks", {"keys": [key]})

    # TWO SCREENS TICK TWO DIFFERENT "WALK ALL" SETS, NOT ONE, AND `Orders.tsx`'S OWN SET IS
    # NOT STORE-WIDE. `Fulfillment.tsx` sends `order.open` alone. `Orders.tsx`'s "Walk all N
    # buyers" ticks `tickableKeys`, built from `shownGroups` — the default "open" tab, every
    # BUYER GROUP with at least one truly open order (`inOpenBase`, `app/src/Orders.tsx`,
    # `finished` empty on a fresh load) — and expands each ticked group through
    # `walkableOf`/`ownsAWalkableBody` (`open` OR `terminal` and still owed a copy,
    # `app/src/Orders.tsx`'s `ownsAWalkableBody`). A GROUP WHOSE ONLY ORDERS ARE TERMINAL-AND-OWING NEVER SHOWS
    # IN THE DEFAULT TAB AND IS NEVER TICKED, even though its orders individually pass
    # `ownsAWalkableBody` — a prior version of this recorder recorded the STORE-WIDE walkable
    # set (305 orders) and still refused, because the real press only asks for the 97 orders
    # belonging to the ~70 buyers who have an open order (measured on the real mirror,
    # 2026-09-27, CI run 36322624741: "97 cards to pick", not 305 and not 71). Grouping by
    # buyer mirrors `orderBuyers.ts:buyerKeyOf`/`foldName` exactly — the demo's own buyer
    # field is already the scrubbed "Jane Doe N" name, one per real buyer, so grouping by it
    # groups the same orders the real name would (`demo-mirror.py`'s own scrub, one name per
    # distinct real buyer).
    listed = (recorded.get("/orders", {}).get("body") or {}).get("orders") or []
    open_orders = sorted(
        str(entry["key"]) for entry in listed
        if isinstance(entry, dict) and entry.get("open") and entry.get("key")
    )
    body = recorded.get("/orders", {}).get("body") or {}
    screen_walkable_orders = default_view_walkable_orders(listed)
    landing_orders = default_view_walkable_orders(listed, body.get("resolution") or {})

    record_walk_plans(open_orders, screen_walkable_orders, take_post, landing_orders)


def owns_a_walkable_body(entry: dict) -> bool:
    """`app/src/Orders.tsx`'s `ownsAWalkableBody`: `open`, or `terminal` and still owed
    a copy — restated over the wire's own order dict rather than `OrderRow`."""
    if entry.get("open"):
        return True
    return bool(entry.get("terminal")) and (entry.get("wanted") or 0) > (entry.get("recorded") or 0)


def buyer_key_of(entry: dict) -> str:
    """`orderBuyers.ts:buyerKeyOf`/`foldName`, restated over the wire's own order dict. The
    demo's `buyer` field is already the scrubbed "Jane Doe N" name, one per real buyer
    (`demo-mirror.py`'s own scrub), so grouping by it groups the same orders the real name
    would."""
    buyer = entry.get("buyer")
    if isinstance(buyer, str):
        trimmed = re.sub(r"\s+", " ", buyer.strip())
        if trimmed != "":
            return "name:%s" % trimmed.casefold()
    return "order:%s" % entry.get("key")


def default_view_walkable_orders(listed: Sequence[dict], resolution: Optional[dict] = None) -> List[str]:
    """The exact set `Orders.tsx`'s "Walk all N buyers" ticks on a FRESH page load: every
    walkable order (`owns_a_walkable_body`) belonging to a buyer group that holds at least
    one truly OPEN order (`inOpenBase`, `app/src/Orders.tsx`, with `finished` empty —
    true on a fresh load, never true once a buyer has been marked done this session). A
    group whose every order is terminal-but-owing never shows in the default "open" tab and
    is never ticked, even though each of its orders individually passes
    `owns_a_walkable_body` — the gap a store-wide walkable set (this function's own first
    version) missed, measured on the real mirror as 305 orders recorded against the 97 the
    real press asked for (CI run 36322624741, 2026-09-27).

    WITH `resolution` (`GET /orders`' own `resolution`), ONLY THE PULLABLE BUYERS, the screen's
    landing since 2026-09-28 (`Orders.tsx`'s `groupPullable`: a buyer with an open order whose
    line still owes a copy that is on hand, `owed - outstanding > 0`). Without it, every buyer
    with an open order, the view with Hide unpullable off. Measured on the committed mirror:
    35 of 70 buyers, 39 orders, the set "Walk 35" sends (DEBT60)."""
    lines_of = {
        str(one.get("key")): one.get("lines") or []
        for one in ((resolution or {}).get("orders") or [])
        if isinstance(one, dict)
    }

    def pullable(bucket: List[dict]) -> bool:
        return any(
            entry.get("open")
            and any(max(0, line.get("owed", 0) - line.get("outstanding", 0)) > 0 for line in lines_of.get(str(entry["key"]), []))
            for entry in bucket
        )

    groups: Dict[str, List[dict]] = {}
    for entry in listed:
        if not isinstance(entry, dict) or not entry.get("key"):
            continue
        groups.setdefault(buyer_key_of(entry), []).append(entry)
    return sorted(
        str(entry["key"])
        for bucket in groups.values()
        if any(entry.get("open") for entry in bucket) and (resolution is None or pullable(bucket))
        for entry in bucket
        if owns_a_walkable_body(entry)
    )


def record_walk_plans(
    open_orders: Sequence[str], walkable_orders: Sequence[str], take_post, landing_orders: Sequence[str] = ()
) -> None:
    """The walk-plan subject list: every SINGLE walkable order, plus each screen's own
    full "walk all" set.

    THE WALK PLAN DOES NOT MERGE — it is a solver over the whole ticked set, so a RECORDED
    SET must be exactly the set a screen sends, never a merge of smaller ones. THE FULL
    POWERSET WAS THE BUG (the orchestrator's ruling, 2026-09-27): 2^n plans fits a 60-card
    sample and NEVER a real store — measured, 71 open orders is 2^71 sets, not 2^7. Recorded
    instead: every SINGLE walkable order (the finest grain a screen ever ticks alone — a
    superset of `open_orders`, so one loop covers both callers' singles) plus the two distinct
    "walk all" sets `Fulfillment.tsx` and `Orders.tsx` actually send (see the caller's own
    comment for why they differ). `demoServer.ts:walkPlan` already refuses ANY OTHER ticked
    combination with the demo's one honest notice (D269/TXT-46) rather than fabricate a plan
    for it — a partial selection (some, not all, not one) is the one gap this recording leaves
    on purpose, named rather than hidden. LINEAR IN THE ORDER COUNT, unlike the powerset it
    replaces: `n + 2` recordings for `n` walkable orders, whatever `n` is.
    """
    for key in walkable_orders:
        take_post("/orders/walk-plan", {"keys": [key]})
    if open_orders:
        take_post("/orders/walk-plan", {"keys": list(open_orders)})
    if walkable_orders and list(walkable_orders) != list(open_orders):
        take_post("/orders/walk-plan", {"keys": list(walkable_orders)})
    # The landing view's own "Walk N" (Hide unpullable on), a subset of the set above.
    if landing_orders and list(landing_orders) not in (list(open_orders), list(walkable_orders)):
        take_post("/orders/walk-plan", {"keys": list(landing_orders)})


HISTORIES_ROOT = REPO_ROOT / "fixtures" / "demo-price-history"


def warm_history_cache(home: Path) -> int:
    """The recorded histories, placed where the server's own `Market` looks first.

    THE OWNER'S RULING (2026-09-24): price histories are recorded once, on the owner's Mac, by
    `make demo-histories`, and never fetched from CI — the host refuses the honest User-Agent
    (D216). The server reads a history through `pipeline/pricehistory.py:Market`, which answers
    from `<home>/.cache/market/history/<product>-<range>.json` before it opens a socket. So
    the newest recorded directory is copied there, stamped now, and the run history panel, the
    trend strip and the product view all answer from real recorded data. Returns files placed.

    The cache lives in the DEMO home (`server/pipeline_routes.py:market_cache_dir`), never in a
    real store. A history the recording lacks still reaches the host, and is refused there.
    """
    if not HISTORIES_ROOT.is_dir():
        return 0
    dated = sorted(p for p in HISTORIES_ROOT.iterdir() if (p / "index.json").is_file())
    if not dated:
        return 0
    target = home / ".cache" / "market" / "history"
    target.mkdir(parents=True, exist_ok=True)
    placed = 0
    stamp = time.time()
    for source in sorted((dated[-1] / "history").glob("*.json")):
        entry = {"fetched_at": stamp, "payload": json.loads(source.read_text())}
        (target / source.name).write_text(json.dumps(entry))
        placed += 1
    return placed


def _run_skus(home: Path, run: str) -> List[str]:
    """Every SKU in one run's pricing table, in the order the table holds them."""
    table = home / "runs" / run / "pricing.json"
    if not table.is_file():
        return []
    try:
        payload = json.loads(table.read_text())
    except ValueError:
        return []
    out = []
    for entry in payload.get("skus") or []:
        if isinstance(entry, dict) and entry.get("sku"):
            out.append(str(entry["sku"]))
    return out


# -------------------------------------------------------------------------- photographs


class QrRefused(SystemExit):
    """A photograph a QR decodes out of. Raised, never logged and skipped."""


def qr_payload(path: Path) -> Optional[str]:
    """The QR payload a decoder reads off this exact file, or None.

    THE SECOND LINE OF DEFENCE, AND IT READS THE BYTES THAT GET PUBLISHED. `make demo-photos`
    (`scripts/demo-photos.py:carries_a_qr`) is the first: it decodes the owner's FULL
    resolution photograph before the downscale and refuses a code card there. This one reads
    the copy a stranger downloads, with the same decoder (`codes/qr.py`, 140/140 measured),
    so a photograph that reached `demo-assets/` by any other road — a hand copy, a future
    seed that draws from somewhere else — is still refused before it is published. A live
    code card is a bearer instrument (D70).

    UNAVAILABLE IS NOT ABSENT. A missing decoder refuses the whole recording, exactly as it
    refuses curation: publishing because the check could not run is the failure it exists
    to prevent.
    """
    from codes import qr

    try:
        read = qr.decode(path)
    except qr.QrUnavailable:
        raise QrRefused(
            "refusing: the QR decoder is unavailable, so no demo photograph can be cleared "
            "of carrying a live code. Install requirements.txt (zxing-cpp) and re-run."
        ) from None
    if read is None:
        return None
    return read.payload or "<undecoded symbol>"


def card_photos(home: Path) -> List[tuple]:
    """`(box, index, source file)` for every card whose photograph is on disk.

    READ OFF THE STORE, NEVER OFF A DIRECTORY LAYOUT. This walked `captures/cards/box*/`
    until the photographs moved under the card's own name (D172, D183 — `photos/<xx>/<sha>
    .jpg`), and from then on it copied 0 photographs and the published page drew none. The
    card record's own `photo` field is where its photograph is, relative to the home (the
    seed writes it that way, `demo-seed.py:relative_photo`) or absolute (a real capture), so
    the next move of the layout cannot strand this again.
    """
    os.environ["PKMNSCAN_HOME"] = str(home)
    from store import Store  # imported late: it reads PKMNSCAN_HOME at call time

    out = []
    for card in Store().read().inventory.cards.values():
        if not card.photo or card.photo_reclaimed_at:
            continue
        source = Path(card.photo)
        if not source.is_absolute():
            source = home / source
        if source.is_file():
            out.append((int(card.box), int(card.index), source))
    return sorted(out)


def copy_photos(home: Path, out: Optional[Path] = None) -> int:
    """Every card's photograph, into where Vite will bundle it, QR-cleared one by one.

    `photoUrl(box, index)` composes `${base}/photo/${box}/${index}` against the capture
    server; the demo build points it at this directory instead. Copied rather than served,
    because the whole object of the exercise is a build with no server behind it.

    Named by the STORE index, undecorated — `photoUrl` composes `demo/photos/3/17.jpg`, and
    a zero-padded stem would need the client to know the padding. D183: the URL names a
    photograph, and the demo keeps that exact contract.

    ALL OR NOTHING. The directory is written to a sibling and swapped in only when every
    photograph has cleared, so a refusal leaves no partial set behind for a build to publish.
    """
    target_root = PHOTO_OUT if out is None else out
    staging = target_root.with_name(target_root.name + ".partial")
    if staging.exists():
        shutil.rmtree(staging)
    written = 0
    refused: List[str] = []
    for box, index, source in card_photos(home):
        payload = qr_payload(source)
        if payload is not None:
            # The payload itself is NEVER printed: it may be a live code.
            refused.append("box %d card %d (%s)" % (box, index, source.name))
            continue
        target = staging / str(box) / ("%d.jpg" % index)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written += 1
    if refused:
        shutil.rmtree(staging, ignore_errors=True)
        raise QrRefused(
            "refusing to publish: %d demo photograph(s) carry a QR a decoder can read. A code "
            "card is a bearer instrument (D70), and nothing was written:\n  %s"
            % (len(refused), "\n  ".join(refused))
        )
    if target_root.exists():
        shutil.rmtree(target_root)
    if staging.exists():
        staging.rename(target_root)
    return written


def self_test() -> int:
    """The QR refusal, proved by committing its defect in a throwaway home.

    A store of two cards — one real demo photograph, one with a synthetic QR pasted on (its
    payload is a fixed string, never a code) — must refuse, write nothing, and name the
    card. Then the same store without the QR card must copy one photograph. A guard is only
    trusted once it has gone red on the defect it guards.
    """
    import tempfile

    from PIL import Image

    try:
        import zxingcpp
    except ImportError:
        print("self-test: zxing-cpp is not installed — `make venv`.")
        return 1

    failures = 0
    clean_source = REPO_ROOT / "demo-assets" / "photos" / "0000.jpg"
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        clean = root / "clean.jpg"
        shutil.copyfile(clean_source, clean)
        marked = root / "marked.jpg"
        symbol = zxingcpp.write_barcode(
            zxingcpp.BarcodeFormat.QRCode, "NOT-A-CODE-DEMO-SELFTEST", width=120, height=120
        )
        symbol = symbol if isinstance(symbol, Image.Image) else Image.fromarray(symbol)
        base = Image.open(clean_source).convert("RGB")
        base.paste(symbol.convert("RGB"), (200, 380))
        base.save(marked, quality=72)

        from store import Card, Store

        def seed(where: Path, marked_too: bool) -> Path:
            """A store at `where` holding the clean card, and the marked one if asked."""
            (where / "photos").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(clean, where / "photos" / "clean.jpg")
            shutil.copyfile(marked, where / "photos" / "marked.jpg")
            os.environ["PKMNSCAN_HOME"] = str(where)
            rows = [(1, "photos/clean.jpg", "c" * 64)]
            if marked_too:
                rows.append((2, "photos/marked.jpg", "d" * 64))
            with Store().write() as snapshot:
                for index, photo, cid in rows:
                    card = Card(box=1, index=index, photo=photo, cid=cid, game="riftbound",
                                capture_id="selftest-%d" % index, state="identified")
                    snapshot.inventory.cards[card.key] = card
            return where

        out = root / "out"
        try:
            copy_photos(seed(root / "dirty", True), out)
            print("FAIL  a photograph carrying a QR was copied — the refusal is gone")
            failures += 1
        except QrRefused as exc:
            named = "card 2" in str(exc) and "NOT-A-CODE" not in str(exc)
            print(("PASS" if named else "FAIL") + "  a QR photograph refuses the whole copy, "
                  "names the card and never prints the payload")
            failures += 0 if named else 1
        if out.exists() or out.with_name("out.partial").exists():
            print("FAIL  a refused copy left files behind")
            failures += 1
        else:
            print("PASS  a refused copy leaves nothing behind")

        written = copy_photos(seed(root / "clean", False), out)
        ok = written == 1 and (out / "1" / "1.jpg").is_file()
        print(("PASS" if ok else "FAIL") + "  a clean store copies its photograph to <box>/<index>.jpg")
        failures += 0 if ok else 1

    print("demo-record self-test: %s" % ("PASS" if failures == 0 else "%d FAILED" % failures))
    return 0 if failures == 0 else 1


# ------------------------------------------------------------------------------- entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=os.environ.get("PKMNSCAN_HOME", "demo"))
    parser.add_argument(
        "--self-test", action="store_true",
        help="prove the QR refusal on a throwaway store, and exit",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="refuse every non-loopback connection from the recorded server (the mirror)",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    home = Path(args.home).expanduser().resolve()
    if not (home / "inventory" / "store.sqlite").exists():
        raise SystemExit(
            "no demo store at %s — run `make demo-seed` first." % (home / "inventory")
        )

    space = parameter_space(home)
    warmed = warm_history_cache(home)
    pairs = replacements(REPO_ROOT, home)
    work = WorkArea(home, pairs)
    pruned = work.prune_others()
    if pruned:
        print("resume    pruned %d work area(s) from an earlier snapshot" % pruned)
    port = free_port()
    with Server(home, port, offline=args.offline) as server:
        recorded, skipped, stats = sweep(server, space, work)
    print("progress  recorded %d of %d route(s), skipped %d already recorded"
          % (stats["new"], len(recorded), stats["resumed"]))

    photos = copy_photos(home)
    # A STORE OF CARDS THAT PUBLISHES NO PHOTOGRAPH IS A BROKEN RECORDING, NOT AN EMPTY ONE.
    # This printed "0 photographs" for every build after D183 moved the files, and the page
    # went out with a broken image on every card. Refused now, so the next move is loud.
    if photos == 0 and space["cards"]:
        raise SystemExit(
            "refusing: %d cards and 0 photographs copied. `card_photos` found no card whose "
            "`photo` is a file under %s." % (len(space["cards"]), home)  # type: ignore[arg-type]
        )

    # `pairs` was already computed above, before the sweep — `WorkArea.save` needs it too.
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
    products = sum(1 for path in recorded if path.startswith("/pipeline/products/"))
    plans = sum(1 for path in recorded if path.startswith("POST /orders/walk-plan "))
    print("  walk    %d ticked set(s) planned; %d product histor(ies)" % (plans, products))
    print("  cache   %d recorded history file(s) placed from fixtures/demo-price-history/" % warmed)
    histories = sum(1 for path in recorded if "/history?" in path)
    trends = sum(1 for path in recorded if "/trends?" in path)
    print("  history %d SKU reading(s), %d trend strip(s)" % (histories, trends))
    if histories == 0:
        print("          NONE — the mirrors answered nothing. The demo will draw the")
        print("          'no reading' state, which is honest; re-run to try again.")
    if skipped:
        print("  %d path(s) answered no GET and were not recorded:" % len(skipped))
        shapes = sorted({"".join("N" if ch.isdigit() else ch for ch in entry) for entry in skipped})
        for shape in shapes[:8]:
            print("    %s" % shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
