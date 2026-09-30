"""Shared helpers for the T7 group modules: one store, one server, one set of fixtures.

The group modules (`harness/tests/t7/*.py`) each export a `CHECKS` tuple; `t7_store_and_seams.py` is
still the one registered T7 and concatenates them in its `CHECK_ORDER`. A helper lives here when two
groups use it, or when `t7_box_map.py` imports it through `t7_store_and_seams`. A helper one group
uses lives in that group's module.

`_MINTED_PHOTOGRAPHS` is load-bearing (D172): a counter that must never repeat, so it has one home.
"""

from __future__ import annotations

import base64
import io
import json
import hashlib
import itertools
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, Optional, Tuple
from harness.tests import Checks
from harness.tests.home import isolated_home, no_env_file  # noqa: F401  (isolated_home re-exported)
from cli import runs
from identify import sidecar
from pipeline import join, tcgcsv
# `pipeline.skus`, aliased — this module's own `skus` name would collide with
# `store.skus`'s `Skus`/`SkuRow` classes imported right below, and both are used by
# `_seed_sku_table` (identity-follows-sku.md §4.2's review round: a review answer now
# refuses a SKU the `skus` table does not already hold, so fixtures that answer a
# hand-built candidate seed the table first, through the real fold).
from pipeline import skus as sku_pipeline
from store.skus import SkuRow
from server import capture_server, pipeline_routes, send_routes, shipping_routes
from store import db, files, master, photos, queues
from store.session import Store

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# The repository root: three levels up from this file (t7/, tests/, harness/).
REPO_ROOT = Path(__file__).resolve().parents[3]
_SERVE_ROOT = REPO_ROOT


# Enough to satisfy the server's magic-number check. It verifies rather than decodes — see
# the JPEG_MAGIC comment there — so a real image would only make this test slower.
JPEG = b"\xff\xd8\xff" + b"\x00" * 64

# Two rows the pipeline would have offered for one collector number, built through
# `cli/resolve.py:_candidate_rows`'s six keys rather than by hand, so the shape 7b's routes
# read cannot drift from the shape `join` writes. The pair differs only by finish, which is
# the case D3 rung 4 sends to review and the case the review screen exists for.
#
# HAND-BUILT, AND THAT IS THE LIMIT OF WHAT THESE CASES PROVE. They assert the routes
# against `docs/DESIGN.md`, not against reality. Recorded here rather than only in the
# module docstring because this literal is where the assumption physically lives.
#
# Gate B produced the first real entries on 2026-08-22 — 16 of them — and the shape above
# survived contact: same keys, same candidate rows. What it did NOT do is widen the range.
# All 16 were `metadata_detection_disagreement`; the other eleven reason codes have still
# never been produced by a run, so this literal remains an assumption about them.
CANDIDATES = [
    {
        "sku": "8608859",
        "name": "Articuno",
        "set": "SV09",
        "number": "161/159",
        "condition": "Near Mint Holofoil",
        "market": "12.00",
    },
    {
        "sku": "8608860",
        "name": "Articuno",
        "set": "SV09",
        "number": "161/159",
        "condition": "Near Mint Reverse Holofoil",
        "market": "4.20",
    },
]

# identity-follows-sku.md §8, lane 3a review round: what `Inventory.identity_snapshot`
# reads off a card that was captured, identified and never bound — the full eleven-field
# shape every forward writer's HISTORY EVENT now carries in `restores_to` (D28: undo must
# be exact), replacing the four-field `{sku, condition, set_name, rarity}` literal this
# file used before that review round. The WIRE RESPONSE's own `restores_to` (what a screen
# reads to decide whether to draw an undo control) is UNCHANGED and stays the narrow
# four-field shape — only the history line widened.
NEVER_BOUND_IDENTITY_SNAPSHOT = {
    "sku": None,
    "condition": None,
    "name": None,
    "number": None,
    "printed_total": None,
    "set_name": None,
    "rarity": None,
    "identity_source": None,
    "bound_by": None,
    "bound_at": None,
    "read_disputes": False,
}


def stored_label(box: int, index: int) -> str:
    """`Position.label` for a card, against the box's STORED name (D259).

    A box created with no name carries its stored default (`Inventory.default_box_name`), so a
    bare `join.Position(box, index).label` (the `Box <number>` fallback for a caller with no
    registry) is not what a route answers. This is the one formula with the registry's name.
    """
    entry = Store().read().inventory.box(box)
    return join.Position(box, index, box_name=entry.name if entry else None).label


def entry(box: int, index: int, **extra) -> queues.QueueEntry:
    """A queue entry for a captured position, with the fields a review row is drawn from.

    `label` comes from `join.Position` and never from a literal, for the same reason
    `check_server_routes` asserts the server's labels that way: one renderer draws a
    position, and a literal here would go on passing while the app and the pipeline
    disagreed about where a card is.
    """
    fields = {
        "position": master.position_key(box, index),
        "box": box,
        "index": index,
        "label": join.Position(box, index).label,
        # `run_photo`'s string, not a composed one, for the reason it gives: this field is
        # carried onto the entry from the run's `identifications.json` verbatim
        # (`cli/resolve.py:queue_entry`), and the review screen renders exactly that file.
        #
        # SHORT-CIRCUITED WHEN THE CALLER NAMES ONE, because `run_photo` READS THE STORE and
        # one caller is seeding a legacy JSON store on disk — whose first read would migrate
        # it, out from under the case that exists to watch the migration happen.
        "photo": extra.get("photo") or run_photo(box, index),
        # RETIRED as a reason the pipeline emits (D3, amended 2026-09-02), and kept here on
        # purpose: the owner's store holds 16 history events carrying this string, the
        # routes validate only `STAND_DOWN_REASONS`, and a fixture wearing the code a real
        # queue once wore is a truer seed than one rewritten to a code that never fired.
        "reason": "metadata_detection_disagreement",
        "candidates": [dict(row) for row in CANDIDATES],
    }
    fields.update(extra)
    return queues.QueueEntry(**fields)


def _seed_sku_table(snapshot, candidates, *, product_line: str = "Pokemon") -> None:
    """Fold candidate-shaped fixture rows into the store's `skus` table directly, through
    the real `pipeline/skus.py:apply_rows` fold — identity-follows-sku.md §4.2's review
    round, the fixture-setup half of "no partial upsert into skus": a review answer now
    REFUSES a SKU the table does not already hold (`sku_unknown`), so any section below
    that answers a hand-built candidate seeds it here first, exactly as a real fetch or
    `pkmnscan skus adopt` would have — never a shortcut that skips the fold.

    `candidates` IS THE SAME NORMALIZED SHAPE `entry()`'s own `candidates` FIELD CARRIES
    (`sku`, `name`, `set`, `number`, `condition`, optional `rarity`) — the literal already
    used to build the queue entry, so a section's seed and its offer are the same data,
    never two hand-typed copies that can drift apart. `product_line` defaults to `"Pokemon"`
    because `CANDIDATES`/`STALE_CANDIDATE` (this file's own default candidates) carry
    Pokemon-shaped sets (`SV09`/`SV08`); a section using its own Riftbound-shaped literals
    passes its own.
    """
    rows = [
        {
            tcgcsv.SKU_COLUMN: str(c["sku"]),
            tcgcsv.PRODUCT_LINE_COLUMN: product_line,
            tcgcsv.SET_COLUMN: str(c.get("set") or ""),
            tcgcsv.NAME_COLUMN: str(c.get("name") or ""),
            tcgcsv.NUMBER_COLUMN: str(c.get("number") or ""),
            tcgcsv.RARITY_COLUMN: str(c.get("rarity") or ""),
            tcgcsv.CONDITION_COLUMN: str(c.get("condition") or ""),
        }
        for c in candidates
    ]
    sku_pipeline.apply_rows(
        rows, at=int(time.time()), source="t7-fixture", skus=snapshot.skus,
        events=snapshot.inventory.events,
    )


@contextmanager
def hermetic():
    """One check's process-global state, put back on the way out, and the owner's `.env`
    kept out of it.

    Three things leaked across checks and each is restored here:
    - `os.environ`. `check_history_route` ran a CLI `join`, which `envfile.load`ed the
      owner's `.env` (API keys, the store cookie) into the process for every later check.
    - `envfile`'s own state (`ENV_FILE`, `_loaded`, `_from_file`).
    - the server modules' caches (`_SETS_CACHE`, `_NEWEST_LIVE`, `_HOLDER`, `_BATCHES`,
      `_CHILDREN`, `_SEARCH_WORK_COUNTERS`), which a later check could read warm.

    `ENV_FILE` points at a file that does not exist for the check's whole run, so no check
    reads a real `.env` and a check needs no `.env` to pass, as on a fresh clone. A check
    that needs a settings file points `ENV_FILE` at its own and restores it, as before.
    `_MINTED_PHOTOGRAPHS` is left alone on purpose: it is a counter that must never repeat
    (D172).
    """
    caches = (
        pipeline_routes._SETS_CACHE, pipeline_routes._NEWEST_LIVE, pipeline_routes._CHILDREN,
        send_routes._HOLDER, shipping_routes._BATCHES, capture_server._SEARCH_WORK_COUNTERS,
    )
    saved = [dict(cache) for cache in caches]
    environ = dict(os.environ)
    try:
        with no_env_file():
            yield
    finally:
        os.environ.clear()
        os.environ.update(environ)
        for cache, before in zip(caches, saved):
            cache.clear()
            cache.update(before)


def store_tables() -> dict:
    """Every table of the isolated store, as ordered rows. What is compared where a case
    used to compare a file's bytes (D88): 'byte-identical' on a document becomes
    'row-identical' on a table, and the argument for it is unchanged."""
    conn = db.connect(files.inventory_dir())
    try:
        return db.dump_tables(conn)
    finally:
        conn.close()


def stored_payloads(table: str, fixed: Optional[dict] = None) -> dict:
    """key -> stored payload dict for one table, straight off the database rather than
    through a snapshot — the on-disk shape, which is what a wire-only decoration must
    never reach."""
    conn = db.connect(files.inventory_dir())
    try:
        src = db.source(conn, table, fixed)
        return {key: json.loads(text) for key, text in src.all()}
    finally:
        conn.close()


def append_history(events) -> None:
    """Hand-write history rows, bypassing every route — the seed for the cases that need a
    log no route can produce. `history.jsonl` used to be appended to directly here."""
    conn = db.connect(files.inventory_dir())
    try:
        conn.execute("BEGIN IMMEDIATE")
        db.append_events(conn, events)
        conn.execute("COMMIT")
    finally:
        conn.close()


def corrupt_history(position: Optional[str] = None) -> None:
    """One history row whose payload is not JSON — the hand-edit `_sale_origin` degrades
    on. It used to be a `{not json` line appended to `history.jsonl`.

    `position` defaults to `None` — a corrupt row this store cannot even say which box it
    was about, the worst case. Since `db.events_at` scopes by the `position` column (this
    item's own fix), a `None`-position row is invisible to a box-scoped read: `WHERE
    position GLOB '<box>/*'` cannot match a NULL. A caller proving that a box-scoped
    reversal still refuses on a corrupt log must corrupt a row THAT SAME BOX would see —
    pass this box's own key (or any string sharing its box prefix).
    """
    conn = db.connect(files.inventory_dir())
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO events (at, event, position, payload) VALUES (?, ?, ?, ?)",
            (master.now(), None, position, "{not json"),
        )
        conn.execute("COMMIT")
    finally:
        conn.close()


@contextmanager
def quiet():
    """Capture what the code under test prints, and yield the buffer.

    The commands print their refusals and argparse prints usage — both correct, and both
    noise in a suite that runs at the end of every turn. Captured rather than discarded,
    because a refusal that explains nothing is its own defect and is asserted below.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        yield buffer


class QuietHandler(capture_server.CaptureHandler):
    """The real handler with its request log silenced.

    Overriding `log_message` rather than redirecting stdout: the server answers on its own
    threads, and swapping a process-global stream underneath them to hide a log line is a
    great deal of leverage for a cosmetic problem.
    """

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - BaseHTTPRequestHandler's name
        pass


def _spawn_server(httpd) -> threading.Thread:
    """Start `httpd.serve_forever` on a daemon thread with a short poll, and return it.

    Every throwaway server in this file used the 0.5s default `poll_interval`. `shutdown()`
    only sets a flag — the `serve_forever` loop notices it on its NEXT poll tick, so each of
    the two dozen servers here idled up to half a second on teardown for zero coverage. That
    idle time was 30s of T7's own 99.9s wall clock, measured before this helper existed
    (S1 of the test-audit plan). One helper, one short poll, so a
    `shutdown()` call anywhere in this file is answered almost at once.
    """
    thread = threading.Thread(target=httpd.serve_forever, args=(0.02,), daemon=True)
    thread.start()
    return thread

# EVERY CAPTURE THIS FILE MAKES CARRIES BYTES OF ITS OWN, AND SINCE D172 THAT IS THE STORE'S
# REQUIREMENT RATHER THAN A CASE'S PREFERENCE. A card is NAMED by the sha256 of its photograph
# and `cards_cid` holds that name UNIQUE, so two captures of one blob are two rows carrying one
# name and the second one raises. `check_remove_and_box_delete` and `check_photo_cache` already
# minted a byte per card for their own reason — "a photograph attributed to the wrong record is
# the failure a position label may never cause" — and the store has now made that rule the
# whole file's.
_MINTED_PHOTOGRAPHS = itertools.count(1)


def photograph() -> bytes:
    """JPEG-shaped bytes nothing else in this run will produce. One per capture.

    A COUNTER RATHER THAN A FUNCTION OF THE POSITION, because the caller does not know which
    index it is about to be handed — the allocator decides that inside the store lock, which
    is the whole subject of `check_allocator`. A case that needs to compare what came back out
    of the store keeps the payload it sent and decodes its `image` field; nothing here can
    recover a blob from a position, and that is correct rather than awkward.

    67 bytes, like the `JPEG` constant it replaces at the shutter: enough for the magic-number
    check, and small enough that a few hundred captures cost nothing.
    """
    seed = f"t7-photograph-{next(_MINTED_PHOTOGRAPHS)}".encode()
    return b"\xff\xd8\xff" + hashlib.sha256(seed).digest() * 2


def capture_payload(box: int, **extra) -> dict:
    payload = {"box": box, "image": base64.b64encode(photograph()).decode("ascii")}
    payload.update(extra)
    return payload


def sent_image(payload: dict) -> bytes:
    """The photograph a capture body carries, decoded — what the store should hold afterwards.

    The cases that compare stored bytes against sent bytes used to name the `JPEG` constant on
    both sides, which stopped being possible when every capture began carrying its own.
    """
    return base64.b64decode(payload["image"])


def back_of(box: int) -> dict:
    """The aim at `box`'s last section, key and token: where a Move to box went before it
    had to name a section (`docs/specs/subbox-capture.md` 1.5). A test that meant "the back
    of the box" says so with this. Splat it into a body: `{"to_box": 7, **back_of(7)}`."""
    inventory = Store().read().inventory
    return {
        "section": master.divider_key(inventory.dividers_of(box)[-1]),
        "layout_token": inventory.layout_token(box),
    }


def fake_cid(seed) -> str:
    """A distinct, deterministic 64-hex name for a card a test invents (D172).

    A TEST'S CARD HAS NO PHOTOGRAPH, so it has no digest to be named by — and
    `record_capture` refuses a nameless row, because the one caller that cannot supply a
    name is a caller that forgot. This is the fixture's way of saying "this card exists and
    is distinct", and it is a real sha256 of the seed rather than a padded constant so that
    `cards_cid`'s UNIQUE index is actually exercised: N cards built from N seeds collide
    under a constant and do not collide here.

    THE SEED HAS TO BE DISTINCT WITHIN ONE STORE AND NOWHERE WIDER. Every case below builds
    its own `Inventory` or its own `isolated_home`, so two functions reusing the seed `1`
    are two stores each holding one card; two cards in ONE store sharing a seed would hit
    `cards_cid` — which is a real refusal from the database rather than a fixture accident,
    and is exactly the property this helper exists to leave intact. Where a case creates
    cards in a loop the seed carries the loop variable, and where it creates them across
    boxes it carries the box too, for that reason.

    IT IS NOT WHAT THE SHUTTER DOES, AND MUST NOT BE MISTAKEN FOR IT.
    `capture_server.do_capture` names a card by hashing the photograph itself
    (`photos.sha256_of_bytes`), which is the only naming this product ships; the cases that
    go through the route get their names that way and never through here. This is for the
    cases that reach `allocate_capture` and `record_capture` directly, which is where a
    store's bookkeeping is checked without a camera in the way.
    """
    return hashlib.sha256(str(seed).encode()).hexdigest()


def photo_of(box: int, index: int) -> Path:
    """Where the card at this position files its photograph, on disk or not (D172).

    THE FIRST OF THE THREE QUESTIONS `capture_server.photo_path` USED TO ANSWER AT ONCE, and
    the one nearly every case here is asking: *where is THIS CARD's photograph*. The
    photograph is filed under the card's own name, so answering it means reading the store —
    a position is a lookup in FRONT of the path now, and never the path itself.

    DERIVED (`photo_target`) RATHER THAN FOUND (`photo_at`), which is the choice worth
    stating. A great many assertions below are that a photograph is NOT on disk, and
    `photo_at` answers None for "no file" and "no card" alike, collapsing two failures this
    file exists to tell apart. D89's reclaim needs the derivation for a second reason: it
    deletes the photograph and KEEPS the claims file beside it, so there is a sidecar at a
    path no `find` will ever return.

    The other two questions have their own spellings and a case may not borrow this one for
    them: `photo_named_by` is *where WOULD this capture land*, for a case with no record to
    look up, and `capture_server.legacy_photo_path` is the address the store is moving away
    from, for the cases that are about the move itself.
    """
    key = master.position_key(box, index)
    card = Store().read().inventory.get(key)
    if card is None:
        # Loud, because the alternative is a path composed out of nothing that then fails an
        # `is_file()` for a reason that reads exactly like the behaviour under test.
        raise AssertionError(
            f"`photo_of` was asked about {key}, which holds no record. It answers for a card "
            f"that exists; a case with no record wants `photo_named_by` or "
            f"`capture_server.legacy_photo_path`."
        )
    return capture_server.photo_target(card)


def stored_captures():
    """Every capture `identify` would read out of this store, in the order `scan` returns.

    THE ROOT MOVED AND THE ORDER STOPPED MEANING ANYTHING (D172). These cases all scanned
    `capture_server.captures_root()`, where a photograph's filename WAS its index — so
    filename order was position order and `[0]` was box 3's first card. Photographs are filed
    under their cards' names now, and the same sort is DIGEST order: `[0]` is whichever card
    happened to hash low. Reach one by position with `capture_named` and keep this for
    COUNTING, which is what the money rule needs — every photograph `scan` finds is a paid
    Batch request, and the count is the whole assertion.

    `store/photos.py` explains why the root it scans is a sibling of `captures/` rather than
    a directory inside it: a content store under `captures/cards/` would be swept by any run
    pointed at the directory above it, and every card in it billed twice.
    """
    return sidecar.scan(photos.root())


def capture_named(key: str):
    """The stored capture whose sidecar claims this position — `stored_captures`' index.

    By the position the sidecar claims rather than by the filename, because the filename is a
    digest now and says nothing about where the card is.
    """
    found = [capture for capture in stored_captures() if capture.key == key]
    if len(found) != 1:
        raise AssertionError(
            f"{len(found)} stored captures claim {key!r}; `capture_named` answers for one. "
            f"Keys on disk: {sorted(capture.key for capture in stored_captures())}"
        )
    return found[0]


def run_photo(box: int, index: int) -> str:
    """The `photo` an `identifications.json` records for this position (D172).

    IT COMES OUT OF THE STORE, because that is where the name is. `identify` reads a capture
    directory and writes down the file it actually read; under this layout that file is the
    card's own name, so a payload composing `captures/cards/box3/0017.jpg` from a position
    would be a fixture asserting against a layout the product no longer has — and
    `cli/resolve.py:realign` now watches for exactly that string, refusing to rewrite a
    cid-named path into a slot-named one.

    A CARD WITH NO NAME TO FILE A PHOTOGRAPH UNDER FALLS BACK TO THE LEGACY ADDRESS, and that
    is the third question rather than a default. Two shapes reach it: a position the store has
    never seen — `check_listing_commands` joins a run over one, a recovered or hand-made file,
    which `cli/resolve.py` names as a supported case — and a record whose `cid` names no
    photograph at all, a `moved:` tombstone or a `nophoto:` card out of a migrated store. The
    only address either can honestly carry is the one that predates the naming.
    """
    card = Store().read().inventory.get(master.position_key(box, index))
    if card is None or not photos.is_photo_cid(card.cid):
        return str(capture_server.legacy_photo_path(box, index))
    return str(capture_server.photo_target(card))

# --------------------------------------------------------------- the command-seam fixture
#
# REAL ROWS FROM THE COMMITTED EXPORT, cut down to three. The join matches on `TCGplayer Id`
# and the routing turns on the prices, so an invented row would be testing the fixture. Three
# because that is the smallest set that carries both shapes the ladder needs: a number with
# two condition rows, which the capture toggle decides (D3 rung 1), and a holofoil-only
# number, which the catalog decides on its own (rung 2).
FIXTURE_EXPORT = REPO_ROOT / "fixtures" / "sv09_export_untouched.csv"

DUNSPARCE_SKU = "8608459"  # 120/159 Near Mint, market 2.06

DUNSPARCE_REVERSE_SKU = "8608464"  # 120/159 Near Mint Reverse Holofoil, market 2.60

ARTICUNO_SKU = "8608859"  # 161/159 Near Mint Holofoil, market 22.03 — one row, no toggle

SEAM_SKUS = (DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU, ARTICUNO_SKU)


def write_export(path, *, live=None, market=None):
    """A Filtered Export holding the three seam rows. `live` overrides `Total Quantity`.

    That column is the one D8 and D11 make authoritative and the one `./pkmnscan join` reads
    a SKU's `live` count from, so every case below that moves `live` moves it by rewriting
    this file rather than by writing the number it expects to read back.

    `market` overrides `TCG Market Price` the same way, because all three seam rows sit above
    the $0.40 threshold in the fixture and a case about the sub-threshold disposition needs one
    that does not — moved by rewriting the export, which is where `prices_for` reads it from.
    """
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = []
    for sku in SEAM_SKUS:
        row = dict(by_sku[sku])
        if live is not None and sku in live:
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = str(live[sku])
        if market is not None and sku in market:
            row[tcgcsv.MARKET_PRICE_COLUMN] = str(market[sku])
        rows.append(row)
    tcgcsv.write_csv(path, source.header, rows)
    return Path(path)


def identifications_for(cards) -> dict:
    """An `identifications.json` payload, shaped as `cli/cmd_identify.py` writes it.

    Field for field, because `cli/resolve.py` reads it back key by key: a hand-made payload
    that drifted from that shape would test the fixture instead of the seam. Each entry is
    `(box, index, name, number, finish)`; a null finish is a card with no capture toggle,
    which is what sends the ladder to rung 2.
    """
    return {
        "prompt_fingerprint": "t7-seam",
        "cards": {
            master.position_key(box, index): {
                "photo": run_photo(box, index),
                "box": box,
                "index": index,
                "set_hint": None,
                "metadata_finish": finish,
                "status": "ok",
                "error": None,
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": finish,
                },
            }
            for box, index, name, number, finish in cards
        },
    }


def seam_run(checks: Checks, cards, *, live=None, market=None, join=True, sections=None):
    """A joined run over `cards`, in whatever isolated home is current. Returns the run.

    Captures a photo per card through the real route first, so the store holds the same
    positions the identifications name — the ordinary case. The one case that deliberately
    skips this is the position `emit` has never seen, which builds its payload by hand.

    `join=False` stops before the join and returns the run with an empty report, for the
    cases that need to put something in the run directory FIRST and watch the join refuse.

    `sections` maps a box to its dividers, declared after the captures and before the join:
    a divider typed ahead of the fill would take the captures (D10).
    """
    for box, index, *_ in cards:
        while Store().read().inventory.next_index(box) <= index:
            capture_server.do_capture(capture_payload(box))
    for box, layout in (sections or {}).items():
        capture_server.do_put_box(box, {"sections": layout})
    run_dir = runs.create("t7-seam")
    run_dir.write_identifications(identifications_for(cards))
    export = write_export(run_dir.path("export.csv"), live=live, market=market)
    if not join:
        return runs.open_run(run_dir.directory), ""
    said = command(checks, "join", str(run_dir.directory), "--export", str(export))
    return runs.open_run(run_dir.directory), said


def command(checks: Checks, *argv, exits: int = 0):
    """Run one `./pkmnscan` subcommand and return what it printed. Exit 0 or a failure.

    Through `cli/__main__.py:main` rather than by importing the command module, because the
    dispatch and the argument defaults are part of the seam: a flag whose default moved would
    otherwise be invisible here. `exits=1` is for an emit that adds nothing, which is
    refused on both paths.
    """
    from cli import __main__ as entry

    with quiet() as said:
        code = entry.main(list(argv))
    text = said.getvalue()
    checks.ok(code == exits, f"`pkmnscan {argv[0]}` exits {exits}", f"exit {code}\n{text}")
    return text


def refusal(checks: Checks, fn, code: str, label: str) -> None:
    """Assert a route refuses with one specific code.

    The code and not just the status: `docs/specs/capture-server.md` requires every
    anticipated condition to carry its own, because step 7 surfaces these strings to a
    human and `docs/DESIGN.md`'s copy rule reaches them. Two conditions collapsing onto
    one code is a message that cannot say what to do next.
    """
    try:
        fn()
    except capture_server.BadRequest as caught:
        checks.equal(caught.code, code, label)
    except Exception as caught:  # noqa: BLE001 — any other exception is the failure
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
    else:
        checks.ok(False, label, "did not refuse")

_STRATEGY_BY_GAME = {"pokemon": "number_and_printed_total", "riftbound": "printed_code"}

_PRODUCT_LINE_BY_GAME = {
    "pokemon": "Pokemon",
    "riftbound": "Riftbound League of Legends Trading Card Game",
}


def _bind(
    snapshot,
    key: str,
    sku: str,
    *,
    condition: str = "Near Mint",
    game: str = "pokemon",
    set_name: str = "T7 Fixture Set",
    product_name: str = "T7 Fixture Card",
    number: str = "001/999",
    rarity: str = "Common",
    bound_by: str = "answer",
):
    """The sanctioned writer, in place of `set_state`'s retired `sku=`/`condition=`
    shortcut — D258's "six writers are sanctioned" as of `66442b32`, which closed the
    entry's own former "`set_state` is a flagged, temporary deviation" line. Builds a
    one-row `Skus` table naming `sku` and binds through it — `scripts/
    identity-store-selftest.py`'s own recipe, narrowed to what a fixture that only needs
    `card.sku`/`card.condition` set needs. Call `inventory.set_state(key, state)` first for
    the state transition; this never touches `state`, exactly as `bind_sku` itself does not.
    """
    snapshot.skus.entries[sku] = SkuRow(
        product_line=_PRODUCT_LINE_BY_GAME[game],
        set_name=set_name,
        product_name=product_name,
        number=number,
        rarity=rarity,
        condition=condition,
        grade=condition,
        printing=None,
        first_seen=1_700_000_000,
        last_seen=1_700_000_000,
        source="t7-fixture",
        raw={},
    )
    return snapshot.inventory.bind_sku(
        key, sku, bound_by=bound_by, skus=snapshot.skus,
        number_strategy=_STRATEGY_BY_GAME[game],
    )


def _refusal_text(fn) -> Optional[Tuple[str, str]]:
    """`(code, message)` off the refusal `fn` raised, or None if it did not refuse.

    `refusal` asserts the CODE and is the right helper almost everywhere. This one exists for
    the handful of cases where the message itself is the contract — the ingest refusal that
    must NAME the field it would not store, and the pull refusals that must name the holding
    order and each refused position with its own code. A refusal that will not say what to do
    next costs a round trip, which is why `docs/DESIGN.md`'s copy rule reaches these strings.
    """
    try:
        fn()
    except capture_server.BadRequest as caught:
        return (caught.code, str(caught))
    except Exception:  # noqa: BLE001 — the caller asserts on None and reports it
        return None
    return None


def answers(checks: Checks, fn, label: str):
    """Assert a route ANSWERS at all, and hand back what it said. `refusal`'s mirror.

    For the routes whose contract is that they survive data they cannot make sense of —
    `/status` on a corrupt store, a sale against an unreadable history. Written as a helper
    for the same reason `Checks` collects failures rather than stopping at the first: an
    exception escaping one of those is the regression itself, and letting it propagate turns
    a red line into a crash that hides every check behind it. Returns None on a raise, so the
    caller guards the assertions that read the answer.
    """
    try:
        answer = fn()
    except Exception as caught:  # noqa: BLE001 — raising IS the failure under test
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
        return None
    checks.ok(True, label)
    return answer

# ---------------------------------------------------------------------------------- history


def events_for(key: str) -> list:
    """Every `history.jsonl` line for one position, in the order they were appended."""
    return [event for event in Store().history() if event.get("position") == key]


def last_event(key: str) -> dict:
    """The newest line for one position, or an empty dict when there is none.

    NEVER INDEXES OFF THE END AND NEVER SUBSCRIPTS A KEY, and the reason is `answers`' reason
    one section up: a missing event IS the failure under test here, so a bare `[-1]` or
    `event["changed"]` turns one red line into a traceback that hides every check behind it.
    Measured — the first draft of this section did exactly that under four of the ten
    mutations it was checked against, reporting a KeyError instead of the assertion that was
    supposed to catch them.
    """
    events = events_for(key)
    return events[-1] if events else {}


def request(port, method, path, *, origin=None, payload=None, extra_headers=None):
    """One request against the running server. Returns `(status, body, headers)`.

    Both outcomes are collapsed here rather than one of them raising: an origin refusal is a
    403 carrying a code and a message this test asserts on, which is a result and not an
    accident. `Connection: close` because a refusal is answered BEFORE the body is read —
    the point of putting the gate there — so the bytes this client already sent are still in
    the socket, and reusing that connection would parse them as the next request line.
    """
    headers = {"Content-Type": "application/json", "Connection": "close"}
    if origin is not None:
        headers["Origin"] = origin
    # `extra_headers` exists for the conditional GET on /photo, which is the one route in
    # this server whose answer depends on a request header other than Origin.
    headers.update(extra_headers or {})
    outgoing = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(outgoing, timeout=30) as response:
            return int(response.status), response.read(), dict(response.headers)
    except urllib.error.HTTPError as refused:
        return int(refused.code), refused.read(), dict(refused.headers)


def error_code(body):
    try:
        return (json.loads(body or b"{}").get("error") or {}).get("code")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None


def error_message(body) -> str:
    """`error_code`'s other half — the sentence a person reads, for the cases that assert on it."""
    try:
        return str((json.loads(body or b"{}").get("error") or {}).get("message") or "")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return ""

# -------------------------------------------------- the printed-code profiles (D21, D25)


RIFTBOUND_EXPORT = (
    REPO_ROOT / "fixtures" / "riftbound_export_untouched.csv"
)


def _live_export_bytes(quantities: Dict[str, int]) -> bytes:
    """A live export (My Pricing shape) holding the seam rows at these `Total Quantity`s.

    EACH ROW ASKS ITS OWN MARKET PRICE (round 8). The fixture's catalogue row carries
    Articuno at 25.9900, the join's own figure, and a live row at a price the plan does not list
    at is a move of live copies the button must name (`pipeline/sendguard.py:live_moves`). A
    blank price is a move too (R7-4). The seam run lists at market, so a case about quantities
    moves nothing; a case about prices uses `_live_export_priced`."""
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = [
        dict(
            by_sku[sku],
            **{
                tcgcsv.LIVE_QUANTITY_COLUMN: str(quantity),
                tcgcsv.PRICE_COLUMN: str(by_sku[sku].get(tcgcsv.MARKET_PRICE_COLUMN) or ""),
            },
        )
        for sku, quantity in quantities.items()
    ]
    path = Path(tempfile.mkdtemp()) / "live.csv"
    tcgcsv.write_csv(path, source.header, rows)
    return path.read_bytes()

_M_PRICE_LIVE1 = "nothing to send: 1 card needs a price first, and TCGplayer already holds every copy of 1 card"
