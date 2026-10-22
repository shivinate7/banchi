"""T7 group: the server read budget, per route (D173, a rule that can be enforced is).

INCIDENT: `GET /capture/sitting` took up to 71.6 s on the owner's store, because it walked a
box once per card. PR #711 fixed it. Nothing in the suite counted work per request, so the
same shape could return in any other read route unseen. This check counts WORK, never wall time.

WHAT IT DOES. One fixture store is built at two sizes, S and 2S (the box count stays fixed,
the card, order and queue counts double). Every GET route of `CaptureHandler.do_GET`, plus the
read-only POSTs in `POST_READS`, is called once per size through a real in-process server.
`COUNTERS` are read per request: SQL statements (sqlite's trace callback on every connection
`store/db` opens), `json.loads` calls in `store/rows`, `records_in`, `layout_of`,
`_Places.__init__`, `Store.read`, `Store.write`, `read_sidecar` and `read_export`. Two more are read
only for the routes in `PHOTO_WALK_FREE`: `scan` (calls to `sidecar.scan`) and `walk` (directory
entries listed under the photograph roots, `captures/` and `photos/`).

Seven rules:
1. EXACT BUDGET. `BUDGET[route]` holds each counter's value at size S. Over it fails. Under it
   fails with "lower to N" (the `UNSCOPED_WALK_EXPECTED` ratchet in `scripts/docs_audit/core.py`).
2. GROWTH. `CONSTANT` counters must be equal at S and 2S. `json_loads` and `read_sidecar` may
   grow with the rows returned. A growing constant counter fails, unless `KNOWN_OVER` holds
   it. `KNOWN_OVER[(route, counter)] = (at S, at 2S)` must match exactly. It only shrinks: a
   counter that is now constant, or lower, fails with "remove" or "lower to".
3. ROUTES. A route `do_GET` serves with no `ROUTE_URLS` or `EXEMPT` row fails by name. So does a
   row for a route that is gone.
   Some routes are budgeted on their miss path only: DEBT85.
4. INDEX. EXPLAIN QUERY PLAN runs on every SELECT a route made. A `SCAN <table>` not in
   `SCAN_ALLOWED` fails. A stale `SCAN_ALLOWED` entry fails. The list only shrinks.
5. PHOTO WALK. A route in `PHOTO_WALK_FREE` answers from the store and a few named photographs. It
   calls `sidecar.scan` zero times and lists zero directory entries under the photograph roots, at
   S and 2S. INCIDENT: `POST /pipeline/waiting` with `{"state": "captured"}` took up to 132 s on the
   owner's store, because a state selection fell back to a scan of every photograph (rglob, is_file,
   one JSON read each) to keep a few cards. `read_sidecar` alone cannot see a walk that reads none.
   The rows are the three selections the store can answer alone: `state`, `since`, and `state` with `box`.

6. JSON FLAT. A route in `JSON_FLAT` parses the same number of rows at S and 2S, so its work follows the rows it
   answers and never the store. INCIDENT: `GET /boxes` took up to 35 s, `GET /search` up to 28 s and
   `GET /capture/sitting` up to 72 s on the owner's store, because `_Places` walked each box it touched through
   `Inventory.records_in`, which parses a whole `Card` per record, to read an index, a name, a state, a game and an
   order that are all indexed columns. `check_box_walk_json_flat` holds the rule on a fixture of its own. The shared
   fixture cannot: the sitting and the search hits there grow with the store, and a card already parsed as a hit hides
   its box from the walk. Here each answer is three rows at every size, in boxes that grow.

7. QUEUE FLAT. `GET /queues` makes the same number of SQL statements at S and 2S while its queued entries double, each on a
   position of its own. The answer grows by design (a row per entry), so unlike rule 6 the rows answered are held to the
   queued count and `json_loads` may follow them; the statements may not. The shared fixture queues the same three positions
   at every size (`entry(4, 1 + n % 3)`), so a statement per queued card is a constant there and only
   `check_queue_read_flat`, on a fixture of its own, can see it grow.

Two checks hold the answer of those selections to the full scan (`sidecar.scan` over every photograph,
then `narrow`):
- `check_selection_scan_equivalence`: the answer equals the scan key for key, in the same order, for a
  store where every photograph that claims a chosen key belongs to a chosen card.
- `check_selection_drops_strays`: the one place the answer differs from the scan. A photograph whose
  sidecar claims a chosen key but belongs to an unchosen card, or to no card, is not returned. A chosen
  card's own photograph always is.
- `check_selection_reads_under_the_given_home`: `resolve` finds the chosen cards' photographs under the `home` it is
  given when that is not `files.home()`, for a state and for a keys selection, and reads only those.

One check holds the answers of the three `JSON_FLAT` reads to `PINS`:
- `check_box_walk_equivalence`: the box rows, the positions with their neighbours, and the order the sitting and the
  search answer in, for a small world that holds every shape the walk reads (`PIN_WORLD`). `PINS` holds those rows.
"""

from __future__ import annotations

import ast
import os
import re
import sqlite3
from pathlib import Path

from harness.tests import Checks
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    capture_payload,
    entry,
    fake_cid,
    isolated_home,
    photograph,
    request,
    seam_run,
)
from identify import sidecar
from pipeline import selection as selection_mod, tcgcsv
from server import capture_server, pipeline_routes
from store import db, files, master, orders as order_store, photos, rows
from store.readings import Reading
from store.session import Store
from store.skus import SkuRow

TABLE_STAMP = "20260102-000000"  # the one markdown the table route reads; the other markdown routes keep their 404 stamp
SIZES = (150, 300)  # S and 2S: cards, orders and queue entries
BOXES = (1, 2, 3)

COUNTERS = (
    "sql", "json_loads", "records_in", "layout_of", "places",
    "store_read", "store_write", "read_sidecar", "read_export",
)
CONSTANT = ("sql", "records_in", "layout_of", "places", "store_read", "store_write", "read_export")
# Counted on every request, budgeted only for `PHOTO_WALK_FREE`: a whole-store selection walks the disk by design.
WALK_COUNTERS = ("scan", "walk")

# Routes `do_GET` serves that this check does not call, each with the reason. A route listed
# here is named, never silent; "no budget row" for any other route fails.
EXEMPT = {
    "/tcg/sets": "opens a socket to TCGplayer",
}

# One concrete URL per route key. A key is a literal path, or the name of the module's regex.
# `{run}`, `{cid}` are filled from the fixture.
ROUTE_URLS = {
    "/status": "/status",
    "/inventory": "/inventory",
    "_INVENTORY_BOX_RE": "/inventory/1",
    "/inventory/recent": "/inventory/recent?limit=3",
    "/inventory/history": "/inventory/history",
    "/queues": "/queues",
    "/capture/sitting": "/capture/sitting",
    "/boxes": "/boxes",
    "/graveyard": "/graveyard",
    "/games": "/games",
    "/orders": "/orders",
    "/codes": "/codes",
    "/codes/lots": "/codes/lots",
    "/search": "/search?q=SKU",
    "/skus/photos": "/skus/photos?sku=SKU1",
    "_REVIEW_CATALOG_RE": "/review/4/1/catalog?q=a",
    "_BOX_LISTINGS_RE": "/boxes/1/listings",
    "_BOX_PHOTOS_RE": "/boxes/1/photos",
    "_BOXES_ITEM_RE": "/boxes/1",
    "_PHOTO_BY_CARD_RE": "/photo/by-card/{cid}",
    "_PHOTO_RE": "/photo/4/1",
    "/pricing": "/pricing",
    "/pipeline/pricing": "/pipeline/pricing",
    "/pipeline/value": "/pipeline/value",
    "/pipeline/sets": "/pipeline/sets",
    "/pipeline/price-now": "/pipeline/price-now?sku=SKU1",
    "/pipeline/trends-saved": "/pipeline/trends-saved",
    "/pipeline/movers": "/pipeline/movers",
    "/pipeline/price-facts": "/pipeline/price-facts?sku=SKU1",
    "/pipeline/prices/refresh": "/pipeline/prices/refresh",
    "/pipeline/holdings-value": "/pipeline/holdings-value",
    "/pipeline/submissions": "/pipeline/submissions",
    "/pipeline/match": "/pipeline/match",
    "/pipeline/match/sweep": "/pipeline/match/sweep",
    "/pipeline/runs": "/pipeline/runs",
    "/pipeline/markdowns": "/pipeline/markdowns",
    "/pipeline/sends": "/pipeline/sends",
    "_MARKDOWN_TABLE_RE": "/pipeline/markdowns/{table_stamp}/table",
    "_MARKDOWN_HISTORY_RE": "/pipeline/markdowns/20260101-000000/history?sku=SKU1",
    "_MARKDOWN_TRENDS_RE": "/pipeline/markdowns/20260101-000000/trends?sku=SKU1",
    "_SEND_FILE_RE": "/pipeline/sends/20260101-000000/file?name=import.csv",
    "_MARKDOWN_FILE_RE": "/pipeline/markdowns/20260101-000000/file?name=a.csv",
    "_RUN_FILE_RE": "/pipeline/runs/{run}/file?name=export.csv",
    "_RUN_PRICING_RE": "/pipeline/runs/{run}/pricing",
    "_RUN_HISTORY_RE": "/pipeline/runs/{run}/history?sku=SKU1",
    "_RUN_TRENDS_RE": "/pipeline/runs/{run}/trends?sku=SKU1",
    "_PRODUCT_REALIZED_RE": "/pipeline/products/SKU1/realized",
    "_PRODUCT_HISTORY_RE": "/pipeline/products/SKU1/history",
    "_RUN_SCOPE_RE": "/pipeline/runs/{run}/scope",
    "_RUN_ITEM_RE": "/pipeline/runs/{run}",
    "_SHIPPING_FILE_RE": "/shipping/batches/abc/file",
    "/stock/mix": "/stock/mix",
}

# The POST reads whose answer is a few cards chosen by the store: a card state, a capture time, a state in one box.
# Their fixture adds a prep (`_waiting_prep`).
STATE_ROW = "POST /pipeline/waiting state"
SINCE_ROW = "POST /pipeline/waiting since"
STATE_BOX_ROW = "POST /pipeline/waiting state box"
WAITING_ROWS = (STATE_ROW, SINCE_ROW, STATE_BOX_ROW)

# `_build` stamps its cards with the clock, so the `since` row cuts at a date no run can pass, and the box 9 cards are
# moved before it (`_waiting_prep`).
LONG_AGO = "2019-01-01T00:00:00+00:00"
WAITING_SINCE = "2020-01-01"

# Read-only POSTs, named by hand: `do_GET` cannot list them.
POST_READS = {
    "POST /pipeline/waiting": ("/pipeline/waiting", {}),
    "POST /inventory/copies": ("/inventory/copies", {"skus": ["SKU1", "SKU2"]}),
    "POST /pipeline/preflight": ("/pipeline/preflight", {}),
    "POST /pipeline/preflight keys": ("/pipeline/preflight", {"keys": ["4/1", "4/2"]}),
    "POST /orders/walk-plan": ("/orders/walk-plan", {"keys": ["tcgplayer:o-1", "tcgplayer:o-2"]}),
    # What `RunsComposer.selectionOf` sends for the "needed" start. The answer is the captured cards that have a photograph.
    STATE_ROW: ("/pipeline/waiting", {"state": "captured"}),
    SINCE_ROW: ("/pipeline/waiting", {"since": WAITING_SINCE}),
    STATE_BOX_ROW: ("/pipeline/waiting", {"state": "captured", "box": [4]}),
}

# Cards that are photographed in the fixture, and captured after `_waiting_prep`: 4/1, 4/2 and 4/3. It is the whole
# answer of each row in `WAITING_ROWS`, and it must be equal at S and 2S or the row could never be flat.
WAITING_ANSWER = 3

# The one route whose fixture adds cards of its own, after every other route has been measured, so
# their counts do not move: sold, unlisted, retired and moved cards, which is the hit path of
# `GET /stock/mix` and not only its empty path (DEBT85). Cards scale with the size, SKUs do not.
MIX_ROUTE = "/stock/mix"


def _mix_prep(size: int) -> None:
    from datetime import datetime, timedelta, timezone

    stamp = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for k in range(12):
            snapshot.skus.entries[f"SKU{k}"] = SkuRow(
                product_line="Riftbound League of Legends Trading Card Game", set_name="Origins",
                product_name=f"Card {k}", number=str(k), rarity="Rare", condition="Near Mint", grade=None,
                printing=None, first_seen=1_700_000_000, last_seen=1_700_000_000, source="t7-fixture", raw={},
            )
            snapshot.readings.entries[f"SKU{k}"] = Reading(market="1.25", at=1_700_000_000, source="t7", kind="run")
        for n in range(size // 3):
            card, _ = inv.allocate_capture(BOXES[n % len(BOXES)], cid=fake_cid(f"mix-{n}"))
            kind = n % 4
            if kind == 0:
                card.sku, card.state, card.state_at = f"SKU{n % 12}", master.SOLD, stamp
            elif kind == 1:
                card.sku, card.state, card.rarity_claim, card.set_hint = None, master.CAPTURED, ["Rare"], "Origins"
            elif kind == 2:
                card.sku, card.state = f"SKU{n % 12}", master.RETIRED
            else:
                card.sku, card.state = f"SKU{n % 12}", master.MOVED


def _waiting_prep(checks: Checks, size: int) -> None:
    """Freezes the answer of every row in `WAITING_ROWS` at `WAITING_ANSWER` cards for every size.

    `seam_run` photographs one more box 9 card for every 50 of the size, and all of them are `captured` and stamped with
    the clock, so the photographed cards a selection keeps would be 6 at S and 9 at 2S: a read of exactly those sidecars
    would look like growth. The box 9 cards leave `captured` and move to `LONG_AGO` here, as a joined run's cards leave
    `captured`. They keep their photographs, so a read of the sidecar of every photographed card still grows, and fails."""
    with Store().write() as snapshot:
        for card in snapshot.inventory.cards.values():
            if card.box == 9:
                card.state, card.captured_at = master.IDENTIFIED, LONG_AGO
    inventory = Store().read().inventory
    photographed = [
        card for card in inventory.cards.values()
        if photos.find(card.cid, card.box, card.index, relocated=False) is not None
    ]
    by_state = [card for card in photographed if card.state == master.CAPTURED]
    by_time = [card for card in photographed if (card.captured_at or "") >= WAITING_SINCE]
    for what, kept in (("captured", by_state), ("captured since the cut", by_time)):
        checks.equal(len(kept), WAITING_ANSWER, f"7. the waiting rows' fixture holds {WAITING_ANSWER} photographed cards {what} at size {size}")


# Routes that would shell out: the child is replaced by a fake that exits 0, so the in-process half
# is what is counted. route -> (module, name, replacement).
STUBS = {
    "POST /pipeline/preflight": (pipeline_routes, "_run_sync", lambda argv, timeout: (0, "")),
    "POST /pipeline/preflight keys": (pipeline_routes, "_run_sync", lambda argv, timeout: (0, "")),
}

# route -> {"status": the HTTP status the fixture must get, counter: value at size S}. A counter
# at 0 is omitted. A route whose status changes fails, so a hit path never turns into a 404 unseen.
BUDGET = {
    '/status': {"status": 200, 'sql': 25, 'json_loads': 3, 'store_read': 1},
    '/inventory': {"status": 200, 'sql': 46, 'json_loads': 161, 'places': 1, 'store_read': 1},
    '_INVENTORY_BOX_RE': {"status": 200, 'sql': 29, 'json_loads': 51, 'records_in': 1, 'places': 1, 'store_read': 1},
    '/inventory/recent': {"status": 200, 'sql': 26, 'json_loads': 15, 'places': 1, 'store_read': 1},
    '/inventory/history': {"status": 200, 'sql': 12, 'store_read': 1},
    # sql 23: 20 statements that do not depend on the queued entries (the store open, both queues, the queued cards' states,
    # box 4's name, positions, columns and order) and 3 that read the queued claims in one pass: `_Places.read_claims` plucks
    # `game`, `cid` and `capture_id` for every queued position, one statement per column. `game_entry` and `_queue_row` answer
    # from that read, so no card is fetched or parsed per queued position. The fixture queues the same 3 positions at every
    # size (`entry(4, 1 + n % 3)`), so this row cannot show a per-card read come back: `check_queue_read_flat` holds it.
    '/queues': {"status": 200, 'sql': 23, 'json_loads': 4, 'places': 1, 'store_read': 1},
    '/capture/sitting': {"status": 200, 'sql': 208, 'json_loads': 86, 'places': 1, 'store_read': 1},
    '/boxes': {"status": 200, 'sql': 79, 'json_loads': 5, 'places': 1, 'store_read': 1},
    '/graveyard': {"status": 200, 'sql': 20, 'store_read': 1},
    '/games': {"status": 200},
    '/orders': {"status": 200, 'sql': 186, 'json_loads': 300, 'store_read': 1},
    '/codes': {"status": 200},
    '/codes/lots': {"status": 200},
    '/search': {"status": 200, 'sql': 175, 'json_loads': 150, 'places': 1, 'store_read': 1},
    '/skus/photos': {"status": 200, 'sql': 13, 'json_loads': 163, 'store_read': 1},
    '_REVIEW_CATALOG_RE': {"status": 409, 'sql': 12, 'json_loads': 2, 'store_read': 1},
    '_BOX_LISTINGS_RE': {"status": 200, 'sql': 20, 'json_loads': 1, 'store_read': 1},
    '_BOX_PHOTOS_RE': {"status": 200, 'sql': 19, 'json_loads': 51, 'records_in': 2, 'store_read': 1},
    '_BOXES_ITEM_RE': {"status": 404},
    '_PHOTO_BY_CARD_RE': {"status": 200},
    '_PHOTO_RE': {"status": 200, 'sql': 11, 'json_loads': 1, 'store_read': 1},
    '/pricing': {"status": 200},
    '/pipeline/pricing': {"status": 200, 'sql': 50, 'json_loads': 13, 'store_read': 2, 'read_export': 3},
    '/pipeline/value': {"status": 200, 'sql': 218, 'json_loads': 170, 'store_read': 3},
    '/pipeline/sets': {"status": 200, 'sql': 11, 'store_read': 1},
    '/pipeline/price-now': {"status": 200, 'sql': 23, 'json_loads': 4, 'store_read': 2},
    '/pipeline/trends-saved': {"status": 200},
    '/pipeline/movers': {"status": 200, 'sql': 11, 'json_loads': 1, 'store_read': 1},
    '/pipeline/price-facts': {"status": 200, 'sql': 12, 'json_loads': 13, 'store_read': 1},
    '/pipeline/prices/refresh': {"status": 200},
    '/pipeline/holdings-value': {"status": 200, 'sql': 26, 'json_loads': 150, 'store_read': 1},
    '/pipeline/submissions': {"status": 200, 'sql': 11, 'store_read': 1},
    '/pipeline/match': {"status": 200, 'sql': 2},
    '/pipeline/match/sweep': {"status": 200, 'sql': 10},
    '/pipeline/runs': {"status": 200, 'sql': 16, 'json_loads': 5, 'store_read': 1},
    '/pipeline/markdowns': {"status": 200},
    '/pipeline/sends': {"status": 200, 'sql': 44, 'store_read': 4},
    # THE MIX ROW: one `cards` statement joined to `skus`, `readings` and `boxes` (docs/specs/sales-screen.md,
    # Mix, "Route"). `sql` is the store open's own statements plus that one, equal at S and 2S.
    '/stock/mix': {"status": 200, 'sql': 11, 'store_read': 1},
    # One store open (11 statements) and one `Store.read`, equal at S and 2S: the on_hand count must come from that one read, never a query per row.
    '_MARKDOWN_TABLE_RE': {"status": 200, 'sql': 11, 'json_loads': 0, 'store_read': 1},
    '_MARKDOWN_HISTORY_RE': {"status": 404},
    '_MARKDOWN_TRENDS_RE': {"status": 404},
    '_SEND_FILE_RE': {"status": 404},
    '_MARKDOWN_FILE_RE': {"status": 404},
    '_RUN_FILE_RE': {"status": 200},
    '_RUN_PRICING_RE': {"status": 200, 'sql': 27, 'json_loads': 3, 'store_read': 2},
    '_RUN_HISTORY_RE': {"status": 404},
    '_RUN_TRENDS_RE': {"status": 200, 'sql': 10, 'store_read': 1},
    '_PRODUCT_REALIZED_RE': {"status": 200},
    '_PRODUCT_HISTORY_RE': {"status": 409, 'sql': 14, 'json_loads': 153, 'store_read': 1},
    '_RUN_SCOPE_RE': {"status": 200},
    '_RUN_ITEM_RE': {"status": 200, 'sql': 16, 'json_loads': 5, 'store_read': 1},
    '_SHIPPING_FILE_RE': {"status": 400},
    'POST /pipeline/waiting': {"status": 200, 'sql': 11, 'store_read': 1, 'read_sidecar': 21},
    'POST /inventory/copies': {"status": 200, 'sql': 53, 'json_loads': 28, 'places': 1, 'store_read': 1},
    'POST /pipeline/preflight': {"status": 200, 'sql': 21, 'store_read': 2, 'read_sidecar': 21},
    'POST /pipeline/preflight keys': {"status": 200, 'sql': 34, 'json_loads': 3, 'store_read': 3, 'read_sidecar': 2},
    'POST /orders/walk-plan': {"status": 200, 'sql': 44, 'json_loads': 30, 'places': 1, 'store_read': 1},
    # Two store opens (the selection's and the claims'), 11 statements each. `read_sidecar` is the WAITING_ANSWER cards' own sidecars and nothing else.
    STATE_ROW: {"status": 200, 'sql': 22, 'store_read': 2, 'read_sidecar': WAITING_ANSWER},
    SINCE_ROW: {"status": 200, 'sql': 22, 'store_read': 2, 'read_sidecar': WAITING_ANSWER},
    STATE_BOX_ROW: {"status": 200, 'sql': 22, 'store_read': 2, 'read_sidecar': WAITING_ANSWER},
}

# Keyed routes: `read_sidecar` reads only the named cards' own sidecars, so it is constant too.
# A selection by state or time is the same shape once it is answered from the store: only the chosen cards' sidecars.
SIDECAR_FLAT = ("POST /pipeline/preflight keys", *WAITING_ROWS)

# Routes that must not walk the photograph roots: no `sidecar.scan`, no directory entries listed under `captures/` or `photos/`.
PHOTO_WALK_FREE = WAITING_ROWS

# (route, counter) -> (value at S, value at 2S): a constant counter that still grows. Only shrinks.
KNOWN_OVER = {
    ('/capture/sitting', 'sql'): (208, 364),
    ('/orders', 'sql'): (186, 336),
    ('/search', 'sql'): (175, 325),
    ('/pipeline/pricing', 'sql'): (50, 62),
    ('/pipeline/pricing', 'read_export'): (3, 6),
    ('/pipeline/value', 'sql'): (218, 371),
    ('POST /inventory/copies', 'sql'): (53, 77),
}

# EXPLAIN QUERY PLAN `SCAN` allowed today, as `table` (no WHERE) or `table.column` (the WHERE
# column has no index, so the statement walks the table). Only shrinks.
SCAN_ALLOWED = frozenset({
    'boxes',
    'cards',
    'identifications.json_extract',
    'listings',
    'orders',
    'readings',
    'readings_sources',
    'skus',
})


# --------------------------------------------------------------------------- the routes

def get_routes(method: str = "do_GET") -> list:
    """The route keys `method` (`do_GET` or `do_POST`) serves: a `path == "..."` literal, or a `_NAME_RE.match(path)`."""
    source = Path(capture_server.__file__).read_text("utf-8")
    tree = ast.parse(source)
    handler = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "CaptureHandler"
    )
    do_get = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == method)
    keys: list = []
    for node in ast.walk(do_get):
        if (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name) and node.left.id == "path"
            and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)
            and isinstance(node.comparators[0], ast.Constant)
        ):
            keys.append(node.comparators[0].value)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "match"
            and isinstance(node.func.value, ast.Name) and node.func.value.id.endswith("_RE")
        ):
            keys.append(node.func.value.id)
    return sorted(set(keys), key=keys.index)


# --------------------------------------------------------------------------- the counters

class _Proxy:
    """A module stand-in: `overrides` by name, every other attribute from the real module."""

    def __init__(self, real, **overrides) -> None:
        self.__dict__["_real"] = real
        self.__dict__.update(overrides)

    def __getattr__(self, name):
        return getattr(self.__dict__["_real"], name)


class _Listing:
    """An `os.scandir` iterator that counts each entry it yields, and is a context manager as `os.scandir`'s is."""

    def __init__(self, inner, bump) -> None:
        self._inner, self._bump = inner, bump

    def __iter__(self):
        return self

    def __next__(self):
        entry = next(self._inner)
        self._bump(1)
        return entry

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)

    def close(self) -> None:
        self._inner.close()


class _Meter:
    """Patches the seams, counts, and puts them back. One request at a time."""

    def __init__(self) -> None:
        self.counts = dict.fromkeys(COUNTERS + WALK_COUNTERS, 0)
        self.selects: set = set()
        self._undo: list = []

    def _wrap(self, owner, name, counter, *, ctx=False):
        real = getattr(owner, name)
        meter = self

        def counted(*args, **kwargs):
            meter.counts[counter] += 1
            return real(*args, **kwargs)

        def counted_ctx(*args, **kwargs):
            meter.counts[counter] += 1
            return real(*args, **kwargs)

        setattr(owner, name, counted_ctx if ctx else counted)
        self._undo.append(lambda: setattr(owner, name, real))

    def __enter__(self):
        meter = self
        real_connect = sqlite3.connect

        def connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)

            def trace(statement):
                meter.counts["sql"] += 1
                if statement.lstrip()[:6].upper() == "SELECT":
                    meter.selects.add(statement)

            conn.set_trace_callback(trace)
            return conn

        sqlite3.connect = connect  # every module's connection, not only `store/db.connect`
        self._undo.append(lambda: setattr(sqlite3, "connect", real_connect))

        real_json = rows.json

        def loads(*args, **kwargs):
            meter.counts["json_loads"] += 1
            return real_json.loads(*args, **kwargs)

        rows.json = _Proxy(real_json, loads=loads)
        self._undo.append(lambda: setattr(rows, "json", real_json))

        self._wrap(master.Inventory, "records_in", "records_in")
        self._wrap(master.Inventory, "layout_of", "layout_of")
        real_init = capture_server._Places.__init__

        def init(this, *args, **kwargs):
            meter.counts["places"] += 1
            return real_init(this, *args, **kwargs)

        capture_server._Places.__init__ = init
        self._undo.append(lambda: setattr(capture_server._Places, "__init__", real_init))
        self._wrap(Store, "read", "store_read")
        self._wrap(Store, "write", "store_write", ctx=True)
        self._wrap(sidecar, "read_sidecar", "read_sidecar")
        self._wrap(tcgcsv, "read_export", "read_export")
        self._wrap(sidecar, "scan", "scan")
        self._watch_photo_roots()
        return self

    def _watch_photo_roots(self) -> None:
        """Counts the entries any directory listing returns under `captures/` and `photos/`. `rglob`, `glob`, `iterdir`
        and `os.walk` all list through `os.scandir` or `os.listdir` (Python 3.12, which CI pins), so a walk written inside
        a route is counted as well as the one in `sidecar.scan`. A path built for one card (`is_file`) lists nothing."""
        roots = (str(files.home() / "captures"), str(photos.root()))
        real_scandir, real_listdir = os.scandir, os.listdir

        def bump(n: int) -> None:
            self.counts["walk"] += n

        def watched(args, kwargs) -> bool:
            target = args[0] if args else kwargs.get("path")
            try:
                return os.fspath(target).startswith(roots)
            except TypeError:  # a descriptor, bytes or no path: not one of ours
                return False

        def scandir(*args, **kwargs):
            inner = real_scandir(*args, **kwargs)
            return _Listing(inner, bump) if watched(args, kwargs) else inner

        def listdir(*args, **kwargs):
            names = real_listdir(*args, **kwargs)
            if watched(args, kwargs):
                bump(len(names))
            return names

        os.scandir, os.listdir = scandir, listdir
        self._undo.append(lambda: setattr(os, "scandir", real_scandir))
        self._undo.append(lambda: setattr(os, "listdir", real_listdir))

    def __exit__(self, *exc):
        for undo in reversed(self._undo):
            undo()
        self._undo.clear()


# --------------------------------------------------------------------------- the fixture

def _build(checks: Checks, size: int) -> dict:
    """The store at one size. Box count is fixed; cards, orders and queue entries scale."""
    from datetime import datetime, timedelta, timezone

    runs_made = [
        seam_run(checks, [(9, k, "Articuno", "161", None)])[0] for k in range(1, size // 50 + 1)
    ]
    run = runs_made[0]
    for _ in range(3):  # three real photographs in box 4, for the photo routes
        capture_server.do_capture(capture_payload(4))
    shelf = files.home().joinpath("captures", "cards", "box6")  # unfiled photographs that scale the full scan
    shelf.mkdir(parents=True, exist_ok=True)
    for n in range(size // 10):
        (shelf / f"p{n}.jpg").write_bytes(b"x")
        (shelf / f"p{n}.json").write_text('{"box": 6, "index": %d}' % (n + 1))
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for n in range(size):
            card, _ = inv.allocate_capture(BOXES[n % len(BOXES)], cid=fake_cid(f"rb-{n}"))
            card.sku = f"SKU{n % 12}"
            if n % 2:
                card.captured_at = stale
        for n in range(size // 3):
            snapshot.review.upsert(entry(4, 1 + n % 3, market="1.00"))
        snapshot.ledger.ingest([
        order_store.OrderRecord(
            source="TCGplayer", number=f"O-{n}",
            placed_at=(datetime.now(timezone.utc) - timedelta(days=n % 28)).isoformat(),
            lines=[order_store.OrderLine(sku=f"SKU{n % 12}", quantity=1)],
        )
        for n in range(size)
        ])
    cid = Store().read().inventory.cards[master.position_key(4, 1)].cid
    _write_survey(size)
    return {"run": run.directory.name, "cid": cid, "table_stamp": TABLE_STAMP}


def _write_survey(size: int, skus: tuple = ()) -> None:
    """One markdown whose survey holds `size` live rows (SKU0..), or exactly `skus`, so the table route's work per row shows as growth."""
    import json

    from cli import cmd_reprice

    directory = files.inventory_dir() / cmd_reprice.DIRNAME / TABLE_STAMP
    directory.mkdir(parents=True, exist_ok=True)
    named = skus or tuple(f"SKU{n}" for n in range(size))
    rows_ = [{"sku": sku, "standing": "offered", "skip": None, "name": sku, "market": "1.00", "row": {}} for sku in named]
    (directory / cmd_reprice.SURVEY).write_text(json.dumps({"at": None, "asked": {}, "counts": {}, "source": {}, "skus": rows_}), "utf-8")


# --------------------------------------------------------------------------- the run

def measure(checks: Checks, size: int) -> tuple:
    """`({route: {counter: n}}, {table: routes that SCAN it}, {route: status})` at one size."""
    out, selects, statuses, found = {}, {}, {}, {}
    with isolated_home():
        names = _build(checks, size)
        Store().read()
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            calls = {key: ("GET", url.format(**names), None) for key, url in ROUTE_URLS.items() if key != MIX_ROUTE}
            calls.update({key: ("POST", url, body) for key, (url, body) in POST_READS.items()})
            if MIX_ROUTE in ROUTE_URLS:
                calls[MIX_ROUTE] = ("GET", ROUTE_URLS[MIX_ROUTE], None)  # last: its fixture adds cards
            origin = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
            for key, (method, url, body) in calls.items():
                if key == MIX_ROUTE:
                    _mix_prep(size)
                if key in WAITING_ROWS:
                    _waiting_prep(checks, size)
                stub = STUBS.get(key)
                real = getattr(stub[0], stub[1]) if stub else None
                if stub:
                    setattr(stub[0], stub[1], stub[2])
                try:
                    with _Meter() as meter:
                        status, _, _ = request(port, method, url, origin=origin, payload=body)
                finally:
                    if stub:
                        setattr(stub[0], stub[1], real)
                out[key] = dict(meter.counts)
                selects[key] = set(meter.selects)
                statuses[key] = status
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
        found = scans(selects, checks)
    return out, found, statuses


def scans(selects: dict, checks: Checks) -> dict:
    """`{key: {routes}}` for every non-covering `SCAN <table>` in an EXPLAIN QUERY PLAN of a counted
    SELECT. The key is `table.column` for the statement's first WHERE column, else `table`."""
    found: dict = {}
    conn = sqlite3.connect(str(db.path(files.inventory_dir())))
    try:
        for route, statements in selects.items():
            for statement in statements:
                try:
                    plan = conn.execute("EXPLAIN QUERY PLAN " + statement).fetchall()
                except sqlite3.Error as exc:
                    checks.note(f"  EXPLAIN failed for {route}: {exc}: {' '.join(statement.split())[:120]}")
                    continue
                where = re.search(r"\bWHERE\s+\(?(\w+)", statement, re.IGNORECASE)
                for *_, detail in plan:
                    match = re.match(r"SCAN (\w+)(?!.*COVERING)", detail)
                    if match and not match.group(1).startswith("sqlite_"):
                        key = match.group(1) + (f".{where.group(1)}" if where else "")
                        found.setdefault(key, set()).add(route)
    finally:
        conn.close()
    return found


def check_server_read_budget(checks: Checks) -> None:
    checks.note("")
    checks.note("SERVER READ BUDGET — work per route, at S and 2S")
    problems: list = []
    served = get_routes()
    known = set(ROUTE_URLS) | set(EXEMPT)
    for route in served:
        if route not in known:
            problems.append(f"route {route!r} has no ROUTE_URLS row and no EXEMPT reason")
    for route in sorted(k for k in known - set(served) if not k.startswith("POST ")):
        problems.append(f"stale row {route!r}: do_GET no longer serves it")
    posted = {f"POST {key}" for key in get_routes("do_POST") if isinstance(key, str) and key.startswith("/")}
    for route, (url, _) in POST_READS.items():
        if f"POST {url}" not in posted:
            problems.append(f"stale row {route!r}: do_POST no longer serves {url}")
    for route in sorted(k for k in set(BUDGET) | set(EXEMPT) if k.startswith("POST ")):
        if route not in POST_READS and route not in EXEMPT:
            problems.append(f"stale row {route!r}: no POST_READS entry")
    small, found, statuses = measure(checks, SIZES[0])
    big, _, _ = measure(checks, SIZES[1])
    for route, status in statuses.items():
        if status >= 500:
            problems.append(f"{route} failed with a server error ({status})")
        elif route in BUDGET and BUDGET[route].get("status") != status:
            problems.append(f"{route} status {status}, budget says {BUDGET[route].get('status')}")

    for route in small:
        want = BUDGET.get(route)
        if want is None:
            problems.append(f"{route} has no BUDGET row: {_row(small[route])}")
            continue
        for counter in COUNTERS:
            got, budget = small[route][counter], want.get(counter, 0)
            if got > budget:
                problems.append(f"{route} {counter}: {got} over budget {budget}")
            elif got < budget:
                problems.append(f"{route} {counter}: {got} under budget {budget}, lower to {got}")
        for counter in CONSTANT + (('read_sidecar',) if route in SIDECAR_FLAT else ()):
            now = (small[route][counter], big[route][counter])
            over = KNOWN_OVER.get((route, counter))
            if now[0] == now[1]:
                if over is not None:
                    problems.append(f"{route} {counter} is constant now ({now[0]}): remove its KNOWN_OVER entry")
            elif over is None:
                problems.append(f"{route} {counter} grows with the store: {now[0]} at S, {now[1]} at 2S")
            elif now != over:
                problems.append(
                    f"{route} {counter} KNOWN_OVER {over} measured {now}: "
                    + ", ".join(
                        f"{label} {got} " + (f"over {had}" if got > had else f"under {had}, lower to {got}")
                        for label, got, had in zip(("S", "2S"), now, over)
                        if got != had
                    )
                )
    for route, _counter in sorted(KNOWN_OVER):
        if route not in small:
            problems.append(f"KNOWN_OVER names {route!r}, which is not a route")

    for route in PHOTO_WALK_FREE:
        if route not in small:
            problems.append(f"PHOTO_WALK_FREE names {route!r}, which is not a route")
            continue
        for counter, what in (("scan", "calls to sidecar.scan"), ("walk", "directory entries listed under the photograph roots")):
            now = (small[route][counter], big[route][counter])
            if any(now):
                problems.append(
                    f"{route} makes {what}: {now[0]} at S, {now[1]} at 2S"
                    + (" (grows with the store)" if now[0] != now[1] else "")
                    + ". It must answer from the store and the chosen cards' own photographs, never a scan of every photograph"
                )

    for table, routes in sorted(found.items()):
        if table not in SCAN_ALLOWED:
            problems.append(f"SCAN {table} (routes: {sorted(routes)[:4]}) is not in SCAN_ALLOWED")
    for table in sorted(SCAN_ALLOWED - set(found)):
        problems.append(f"SCAN_ALLOWED names {table}, which no route scans now: remove it")
    for problem in problems:
        checks.ok(False, problem)
    checks.ok(
        not problems,
        f"{len(small)} routes inside their read budget, constant counters equal at S and 2S",
    )


def _row(counts: dict) -> str:
    return "{" + ", ".join(f"{k!r}: {v}" for k, v in counts.items() if v) + "}"


# `detail=paid` over three keys, measured on the build: equal at S and 2S.
DETAIL_PAID_SQL = 7


def _detail_read(checks: Checks, size: int) -> tuple:
    """`(status, has_cards, counts, lock_probes)` for one `detail=paid` read over a fixed scope, at one store size."""
    from unittest import mock

    from identify import sweep

    with isolated_home():
        _build(checks, size)
        inv = Store().read().inventory
        keys = [master.position_key(4, n) for n in (1, 2, 3)]  # the fixed scope: three paid cards, whatever the store holds
        for n in (1, 2, 3):
            capture_server.do_put_card(4, n, {"set_hint": "sv9"})
        inv = Store().read().inventory
        sweep.remember_tried({key: inv.cards[key].capture_id or "" for key in keys})
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        probes = []
        try:
            url = "/pipeline/match/sweep?keys=" + ",".join(keys) + "&detail=paid"
            with mock.patch.object(sweep, "acquire_lock", lambda: probes.append(1)), mock.patch.object(
                sweep, "running", lambda: probes.append(1) or False
            ), _Meter() as meter:
                status, body, _ = request(port, "GET", url, origin=capture_server.DEFAULT_ALLOWED_ORIGINS[0])
            import json

            has = status == 200 and "cards" in json.loads(body)
            return status, has, dict(meter.counts), len(probes), url
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def check_detail_read_budget(checks: Checks) -> None:
    """BAND SHEETS 7 (`identify-engine-pick.md`, 10.5): `GET /pipeline/match/sweep?keys=..&detail=paid` is a photo-lane read
    that takes no lock, opens the store read-only (no `Store.read`, no write), and does the same work at S and 2S for a fixed
    scope. It answers `cards`. The pin is measured on the build: this check holds the shape, `BUDGET` the number."""
    checks.note("")
    checks.note("DETAIL READ BUDGET — the sheet's one read, at S and 2S")
    small = _detail_read(checks, SIZES[0])
    big = _detail_read(checks, SIZES[1])
    checks.equal(small[0], 200, "7. the detail read answers")
    checks.ok(small[1] and big[1], "7. it answers `cards`")
    checks.ok(capture_server.photo_lane_path(small[4]), "7. it rides the photo lane")
    checks.equal(small[3] + big[3], 0, "7. it takes no lock (no sweep.running, no sweep.acquire_lock)")
    for counter in ("store_read", "store_write"):
        checks.equal((small[2][counter], big[2][counter]), (0, 0), f"7. it makes no {counter} (the store is opened read-only)")
    for counter in ("sql", "records_in", "layout_of", "places"):
        checks.equal(small[2][counter], big[2][counter], f"7. {counter} is equal at S and 2S for a fixed scope")
    checks.equal(small[2]["sql"], DETAIL_PAID_SQL, "7. detail=paid makes its measured SQL statements (cards and boxes, chunked by key count)")


def check_markdown_table_on_hand(checks: Checks) -> None:
    """7b-29: the markdown table route sends `on_hand` per row, the copies still in a box. A SKU whose copies all
    sold reads 0, a SKU with copies on hand reads n, and a SKU the store never held reads 0."""
    checks.note("")
    checks.note("MARKDOWN TABLE on_hand (7b-29)")
    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            for n, (sku, state) in enumerate(
                [("SOLD1", master.SOLD), ("SOLD1", master.SOLD), ("HELD3", None), ("HELD3", None), ("HELD3", master.SOLD), ("HELD3", None)]
            ):
                card, _ = inv.allocate_capture(1, cid=fake_cid(f"oh-{n}"))
                card.sku = sku
                if state:
                    card.state = state
        _write_survey(0, ("SOLD1", "HELD3", "NEVER"))
        got = {row["sku"]: row.get("on_hand") for row in pipeline_routes.do_markdown_table(TABLE_STAMP)["skus"]}
    checks.equal(got, {"SOLD1": 0, "HELD3": 3, "NEVER": 0}, "7b-29. the table sends on_hand: 0 when every copy sold, n when n are in a box")


# --------------------------------------------------------------------------- the selection equivalence

OLD, NEW, SINCE = "2026-03-01T10:00:00+00:00", "2026-05-01T10:00:00+00:00", "2026-04-01"

# `(payload, the position keys the full scan keeps, in order)`, for the world `_equivalence_world` builds. Two keys
# repeat on purpose: `4/1` is the key of two photographs. Why each answer is what it is:
#   scan order is the `captures/cards` root first (path order), then the `photos` root (digest order, 9 a b c d e f).
#   7/1 is a legacy-address photograph. 3/1 is card 2/1's photograph, whose sidecar says box 3.
#   4/1 twice is card 4/4's photograph (its sidecar says 4/1) and card 4/1's own.
#   Every photograph kept belongs to a card the state and since terms choose, so an answer built from the chosen cards'
#   own photographs can equal the scan here. A photograph that claims a chosen key and belongs to no chosen card is
#   `check_selection_drops_strays`'s case, and the scan and the answer differ on it by ruling.
#   4/7 (card 4/3's sidecar), 4/9 and 6/1 (photographs no card is at) and 5/1, 5/2 (cards with no photograph) are never kept.
EQUIVALENCE_CASES = (
    ({"state": "captured"}, ["7/1", "3/1", "4/1", "4/2", "4/1"]),
    ({"state": "captured", "since": SINCE}, ["7/1", "3/1", "4/1", "4/1"]),
    ({"since": SINCE}, ["7/1", "3/1", "8/1", "4/1", "4/1"]),
    ({"state": "captured", "box": [4]}, ["4/1", "4/2", "4/1"]),
    ({"state": "captured", "box": [3]}, ["3/1"]),
    ({"state": "captured", "box": [5]}, []),
    ({"state": "captured", "box": [7]}, ["7/1"]),
    ({"state": "identified"}, ["8/1"]),
)


def _digest(char: str) -> str:
    """A photograph name chosen by hand: 64 hex digits sort by their first, so the order the files lie in is set here."""
    return char * 64


def _equivalence_world(relocated: bool) -> None:
    """The store and the disk the equivalence cases read. Every shape the full scan answers that a store-driven answer could get wrong:

    - content-store photographs whose names sort the opposite way to their positions (order);
    - 4/3 whose sidecar claims 4/7, a position no card holds, and 4/4 whose sidecar claims 4/1, another captured card's;
    - 2/1 whose sidecar claims box 3, where a captured card with no photograph, 3/1, sits (the `box` term reads what the sidecar recorded);
    - 5/1, 5/2 and 3/1: captured cards with no photograph; 8/1: an identified card with one;
    - 7/1: a captured card whose only photograph is at the legacy `(box, index)` address;
    - two photographs no card is at: 4/9 in the content store and 6/1 at the legacy address.
    `relocated` stamps `meta.photos_relocated`, after which `store/photos.find` no longer looks at the legacy address."""
    filed = (  # (box, index, digest char, the position the sidecar claims, state, captured_at)
        (4, 1, "f", (4, 1), master.CAPTURED, NEW),
        (4, 2, "e", (4, 2), master.CAPTURED, OLD),
        (4, 3, "d", (4, 7), master.CAPTURED, NEW),
        (4, 4, "c", (4, 1), master.CAPTURED, NEW),
        (8, 1, "b", (8, 1), master.IDENTIFIED, NEW),
        (2, 1, "9", (3, 1), master.CAPTURED, NEW),
    )
    bare = ((5, 1), (5, 2), (3, 1), (7, 1))  # captured, NEW, no photograph at the card's own name
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for box, index, char, _, state, at in filed:
            card, _ = inv.allocate_capture(box, cid=_digest(char))
            card.state, card.captured_at = state, at
            if card.index != index:
                raise AssertionError(f"the equivalence fixture put {box}/{card.index} where it meant {box}/{index}")
        for box, index in bare:
            card, _ = inv.allocate_capture(box, cid=fake_cid(f"eq-{box}/{index}"))
            card.state, card.captured_at = master.CAPTURED, NEW
            if card.index != index:
                raise AssertionError(f"the equivalence fixture put {box}/{card.index} where it meant {box}/{index}")
    for _, _, char, (box, index), _, _ in filed:
        photos.write(_digest(char), photograph())
        photos.write_sidecar(_digest(char), photos.claims_payload(box, index, {}))
    photos.write(_digest("a"), photograph())  # in the content store, and no card is at 4/9
    photos.write_sidecar(_digest("a"), photos.claims_payload(4, 9, {}))
    for box, index in ((7, 1), (6, 1)):  # 7/1 is a card, 6/1 is not
        _write_legacy(box, index, (box, index))
    if relocated:
        _mark_relocated()


def _write_legacy(box: int, index: int, claims: tuple, home: Path | None = None) -> None:
    """A photograph at the legacy `(box, index)` address under `home` (the store's own when None), whose sidecar claims the position `claims`."""
    import json

    target = photos.legacy_path(box, index, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(photograph())
    target.with_suffix(".json").write_text(json.dumps({"box": claims[0], "index": claims[1]}), "utf-8")


def _mark_relocated() -> None:
    """Stamps `meta.photos_relocated`, as the move of every photograph to the content store does."""
    conn = db.connect(files.inventory_dir())
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (db.PHOTOS_RELOCATED, NEW))
        conn.execute("COMMIT")
    finally:
        conn.close()


def _view(captures, home: Path) -> list:
    """What the equivalence compares: each capture's position key and its photograph, so a swapped or doubled photograph shows."""
    return [(capture.key, str(capture.photo.relative_to(home)) if home in capture.photo.parents else str(capture.photo)) for capture in captures]


def _full_scan(selection, home: Path) -> list:
    """The reference: `sidecar.scan` over every photograph under both roots, then `narrow`. Written out here and not read
    from `selection_mod.resolve`, so the reference is the scan itself and never the code under test."""
    found: list = []
    for root in (home / "captures" / "cards", photos.root(home)):
        if root.is_dir():
            found += sidecar.scan(root)
    return _view(selection_mod.narrow(selection, found, inventory=Store().read().inventory), home)


def check_selection_scan_equivalence(checks: Checks) -> None:
    """A state or `since` selection resolves to the same captures, in the same order, as scanning every photograph and
    narrowing: through `selection_mod.resolve` and through the answer of `POST /pipeline/waiting`. The world holds no stray
    (no photograph claims a chosen key for a card the terms do not choose), so the scan and the answer have no reason to
    differ. A card dropped, a card added, a photograph at the legacy address missed (the store says relocated or not), or
    the order changed fails here by case."""
    checks.note("")
    checks.note("SELECTION EQUIVALENCE — state and since answers equal the full scan plus narrow")
    for relocated in (False, True):
        setting = "relocated" if relocated else "legacy address still read"
        with isolated_home():
            home = files.home()  # resolved, as every caller passes it: on macOS the temporary directory's own spelling differs
            _equivalence_world(relocated)
            checks.equal(bool(Store().read().inventory.photos_relocated), relocated, f"8. the fixture is {setting}")
            for payload, want in EQUIVALENCE_CASES:
                label = f"{payload} ({setting})"
                selection = selection_mod.parse(dict(payload))
                reference = _full_scan(selection, home)
                checks.equal([key for key, _ in reference], want, f"8. the fixture: the full scan keeps these positions for {label}")
                got, _ = selection_mod.resolve(selection, home, read_inventory=lambda: Store().read().inventory)
                checks.equal(_view(got, home), reference, f"8. resolve answers {label} as the full scan does")
                routed = pipeline_routes.do_pipeline_waiting(dict(payload))
                checks.equal(routed, {"keys": sorted(set(want)), "claimed": 0}, f"8. the waiting route answers {label} with the full scan's cards")


# --------------------------------------------------------------------------- the stray ruling

# A STRAY IS A PHOTOGRAPH WHOSE SIDECAR CLAIMS A CHOSEN KEY BUT WHICH BELONGS TO AN UNCHOSEN CARD OR TO NO CARD. The
# full scan keeps it, because it judges by the key each sidecar recorded. A state or `since` term asks which cards the
# store holds, so the answer is the chosen cards' own photographs and a stray is dropped. No chosen card is dropped:
# its own photograph is returned at the content store or the legacy address.
#
# Cards, `(box, index, digest char of its own photograph or None, state, captured_at, the position that photograph claims)`:
STRAY_CARDS = (
    (4, 1, "f", master.CAPTURED, NEW, (4, 1)),    # chosen by state and by time; its photograph is X below
    (4, 2, "e", master.IDENTIFIED, OLD, (5, 1)),  # chosen by neither; its photograph claims 5/1
    (5, 1, None, master.CAPTURED, NEW, None),     # chosen, no photograph: only a stray can put 5/1 in the route's answer
    (5, 2, None, master.CAPTURED, NEW, None),     # the same
    (7, 1, None, master.CAPTURED, NEW, None),     # chosen; its photograph is at the legacy address (L below)
    (8, 1, "b", master.IDENTIFIED, NEW, (8, 1)),  # chosen by time only; its photograph is Z below
)
# Photographs no card owns: two in the content store and one at the legacy address (None), `(digest char, position claimed)`.
STRAY_ORPHANS = (("d", (4, 1)), ("c", (5, 2)), (None, (4, 1)))
# `(payload, the chosen cards' own photographs in scan order, strays the full scan keeps and the answer must not)`.
STRAY_CASES = (
    ({"state": "captured"}, ("L", "X"), 4),
    ({"since": SINCE}, ("L", "Z", "X"), 4),
    ({"state": "captured", "since": SINCE}, ("L", "X"), 4),
    ({"state": "captured", "box": [4]}, ("X",), 2),  # the box term drops the strays that claim box 5
)


def _stray_world(relocated: bool) -> None:
    """The store and the disk of `STRAY_CARDS` and `STRAY_ORPHANS`: strays beside a chosen photograph that claim its key
    (orphans claiming 4/1), strays for chosen cards with no photograph (the unchosen card 4/2 claiming 5/1, an orphan
    claiming 5/2), and a stray at the legacy address (6/1, claiming 4/1)."""
    with Store().write() as snapshot:
        for box, index, char, state, at, _ in STRAY_CARDS:
            card, _ = snapshot.inventory.allocate_capture(box, cid=_digest(char) if char else fake_cid(f"stray-{box}/{index}"))
            card.state, card.captured_at = state, at
            if card.index != index:
                raise AssertionError(f"the stray fixture put {box}/{card.index} where it meant {box}/{index}")
    for char, claims in [(c, p) for _, _, c, _, _, p in STRAY_CARDS if c] + [(c, p) for c, p in STRAY_ORPHANS if c]:
        photos.write(_digest(char), photograph())
        photos.write_sidecar(_digest(char), photos.claims_payload(*claims, {}))
    _write_legacy(7, 1, (7, 1))
    _write_legacy(6, 1, next(p for c, p in STRAY_ORPHANS if c is None))
    if relocated:
        _mark_relocated()


def check_selection_drops_strays(checks: Checks) -> None:
    """A state or `since` selection returns the chosen cards' own photographs and no stray, through `selection_mod.resolve`
    and through the answer of `POST /pipeline/waiting`. Each case checks the stray and the dropped card apart, so a failure
    says which one it is. The fixture check says the full scan does keep the strays, so the cases cannot pass for want of one."""
    checks.note("")
    checks.note("STRAY PHOTOGRAPHS — a state or since selection drops a photograph that claims a chosen key for a card it does not choose")
    for relocated in (False, True):
        setting = "relocated" if relocated else "legacy address still read"
        with isolated_home():
            home = files.home()
            _stray_world(relocated)
            checks.equal(bool(Store().read().inventory.photos_relocated), relocated, f"9. the fixture is {setting}")
            own = {
                "X": (photos.path(_digest("f")), "4/1"),
                "Z": (photos.path(_digest("b")), "8/1"),
                "L": (photos.legacy_path(7, 1), "7/1"),
            }
            for payload, names, strays in STRAY_CASES:
                label = f"{payload} ({setting})"
                want = [(own[name][1], str(own[name][0].relative_to(home))) for name in names]
                selection = selection_mod.parse(dict(payload))
                scanned = _full_scan(selection, home)
                checks.equal(len([view for view in scanned if view not in want]), strays, f"9. the fixture: the full scan keeps {strays} strays for {label}")
                got, _ = selection_mod.resolve(selection, home, read_inventory=lambda: Store().read().inventory)
                seen = _view(got, home)
                checks.equal([view for view in seen if view not in want], [], f"9. {label}: no stray is returned")
                checks.equal([view for view in want if view not in seen], [], f"9. {label}: every chosen card's own photograph is returned")
                routed = pipeline_routes.do_pipeline_waiting(dict(payload))
                checks.equal(routed, {"keys": sorted({key for key, _ in want}), "claimed": 0}, f"9. the waiting route answers {label} with the chosen cards' keys only")


# --------------------------------------------------------------------------- the home passthrough

def check_selection_reads_under_the_given_home(checks: Checks) -> None:
    """`resolve(selection, home)` finds the chosen cards' photographs under `home`, where `home` is not `files.home()`.

    The store (the cards, their names and states) is read through `read_inventory` and sits in the process's own home; the
    photographs sit only under another directory, `other`, in both layouts (content store and legacy address). A state
    selection and a keys selection must each return the chosen cards' photographs from `other`, and read only those
    (`scanned` is the count of photographs read, so a fall-back to scanning `other` would count all three). The last case
    runs the same two selections with `home` dropped on the way into `_keyed` and requires a different answer, so the
    fixture can tell the defect from the fix."""
    import tempfile

    checks.note("")
    checks.note("HOME PASSTHROUGH — resolve reads the chosen cards' photographs under the home it is given")
    with isolated_home():
        own = files.home()
        with Store().write() as snapshot:
            inv = snapshot.inventory
            for box, char, state in ((4, "f", master.CAPTURED), (8, "b", master.IDENTIFIED)):
                card, _ = inv.allocate_capture(box, cid=_digest(char))
                card.state, card.captured_at = state, NEW
            card, _ = inv.allocate_capture(6, cid=fake_cid("home-legacy"))  # captured, its photograph is at the legacy address
            card.state, card.captured_at = master.CAPTURED, NEW
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp).resolve()
            for box, char in ((4, "f"), (8, "b")):
                photos.write(_digest(char), photograph(), other)
                photos.write_sidecar(_digest(char), photos.claims_payload(box, 1, {}), other)
            _write_legacy(6, 1, (6, 1), other)
            checks.equal(
                [p for p in (own / "photos", own / "captures") if p.exists()], [],
                "10. the fixture: no photograph is under the process's own home, so only `other` can answer",
            )
            read_inventory = lambda: Store().read().inventory  # noqa: E731
            wanted_state = [("4/1", f"photos/{_digest('f')[:2]}/{_digest('f')}.jpg"), ("6/1", "captures/cards/box6/0001.jpg")]
            wanted_keys = [("8/1", f"photos/{_digest('b')[:2]}/{_digest('b')}.jpg")]

            def answer(payload):
                got, scanned = selection_mod.resolve(selection_mod.parse(dict(payload)), other, read_inventory=read_inventory)
                return sorted(_view(got, other)), scanned

            checks.equal(answer({"state": "captured"}), (sorted(wanted_state), 2), "10. a state selection returns the chosen cards' photographs from `other`, and reads only those two")
            checks.equal(answer({"keys": ["8/1"]}), (wanted_keys, 1), "10. a keys selection returns the chosen card's photograph from `other`, and reads only that one")

            real_keyed = selection_mod._keyed
            selection_mod._keyed = lambda selection, home, *rest: real_keyed(selection, files.home(), *rest)
            try:
                dropped = (answer({"state": "captured"}), answer({"keys": ["8/1"]}))
            finally:
                selection_mod._keyed = real_keyed
            checks.ok(
                dropped[0] != (sorted(wanted_state), 2) and dropped[1] != (wanted_keys, 1),
                "10. the fixture can tell: with `home` dropped on the way into `_keyed`, both answers change",
                f"{dropped}",
            )


# --------------------------------------------------------------------------- the box walk, parsed rows

# `{route: url}`: the three reads that reach `_Places` for every card they answer. `/boxes` answers a row per box,
# `/capture/sitting` a row per card of the sitting, and `/search` a copy per card of the group the query finds.
FIND_NAME = "Quillfeather"
FIND_SKU = "SKUFIND"
JSON_FLAT = {
    "/boxes": "/boxes",
    "/capture/sitting": "/capture/sitting",
    "/search": f"/search?q={FIND_NAME}",
}
# Each answer holds this many rows at every size: the three boxes, the three cards stamped now, the three copies of FIND_SKU.
JSON_FLAT_ANSWER = 3


def _walk_world(size: int) -> int:
    """The store the JSON FLAT rule reads: `size` cards in `BOXES`, all stamped `LONG_AGO` and named, then `JSON_FLAT_ANSWER`
    more half way along, one per box. Those alone are stamped now (so the sitting is exactly them), and alone carry
    `FIND_NAME` and `FIND_SKU` (so the search group is exactly them). Their boxes hold `size / 3` records each and grow with
    `size`. Returns how many records the store holds."""
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for n in range(size):
            card, _ = inv.allocate_capture(BOXES[n % len(BOXES)], cid=fake_cid(f"bw-{n}"))
            card.name, card.captured_at = f"Filler {n}", LONG_AGO
            if n == size // 2:
                for box in BOXES:
                    found, _ = inv.allocate_capture(box, cid=fake_cid(f"bw-find-{box}"))
                    found.name, found.sku = FIND_NAME, FIND_SKU
    return len(Store().read().inventory.cards)


def _answer_rows(route: str, body: bytes) -> int:
    """How many rows the route's answer holds: boxes, sitting cards, or copies across every group."""
    import json

    answer = json.loads(body)
    if route == "/boxes":
        return len(answer["boxes"])
    if route == "/capture/sitting":
        return len(answer["cards"])
    return sum(len(group["copies"]) for group in answer["groups"])


def _walk_read(size: int) -> tuple:
    """`(cards in the store, {route: (status, rows answered, json_loads)})` for the `JSON_FLAT` reads at one store size."""
    out: dict = {}
    with isolated_home():
        held = _walk_world(size)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            for route, url in JSON_FLAT.items():
                with _Meter() as meter:
                    status, body, _ = request(port, "GET", url, origin=capture_server.DEFAULT_ALLOWED_ORIGINS[0])
                out[route] = (status, _answer_rows(route, body) if status == 200 else None, meter.counts["json_loads"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
    return held, out


def check_box_walk_json_flat(checks: Checks) -> None:
    """Rule 6. Each `JSON_FLAT` read answers `JSON_FLAT_ANSWER` rows at S and at 2S, and parses the same number of rows both times.
    A fixture that answered nothing, or a different number of rows, could not tell a flat read from a broken one: that
    fails by route and size before the counts are compared. A meter that sees no parse at all fails as well, so a store
    that moved off `rows.json` cannot turn every count into a quiet 0 == 0."""
    checks.note("")
    checks.note("BOX WALK JSON FLAT — rows parsed per request, at S and 2S")
    problems: list = []
    (held_small, small), (held_big, big) = _walk_read(SIZES[0]), _walk_read(SIZES[1])
    if held_big <= held_small:
        problems.append(f"the fixture's boxes do not grow: {held_small} records at S, {held_big} at 2S")
    for route in JSON_FLAT:
        for label, got in (("S", small[route]), ("2S", big[route])):
            if got[0] != 200:
                problems.append(f"{route} answered {got[0]} at {label}")
            elif got[1] != JSON_FLAT_ANSWER:
                problems.append(f"{route} answers {got[1]} rows at {label}, the fixture holds it at {JSON_FLAT_ANSWER}")
            elif not got[2]:
                problems.append(f"{route} parsed no row at {label}: the meter no longer sees the store's parse")
        if small[route][2] != big[route][2]:
            problems.append(f"{route} json_loads grows with the store: {small[route][2]} at S, {big[route][2]} at 2S")
    for problem in problems:
        checks.ok(False, problem)
    checks.ok(not problems, f"11. {len(JSON_FLAT)} reads parse the same rows at S and 2S, and answer {JSON_FLAT_ANSWER} rows each")


# --------------------------------------------------------------------------- the queue read, statements

def _queue_world(size: int) -> int:
    """`size` cards in `BOXES`, the first `size // 3` of them queued for review, each at a position of its own. The
    positions span every box and double with `size`. Returns how many entries are queued."""
    queued = size // 3
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for n in range(size):
            card, _ = inv.allocate_capture(BOXES[n % len(BOXES)], cid=fake_cid(f"qf-{n}"))
            card.name = f"Filler {n}"
            if n < queued:
                snapshot.review.upsert(entry(card.box, card.index, market="1.00"))
    return queued


def _queue_read(size: int) -> dict:
    """What `GET /queues` answered and cost at one store size: status, rows, distinct positions, queued, statements."""
    import json

    with isolated_home():
        queued = _queue_world(size)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            with _Meter() as meter:
                status, body, _ = request(port, "GET", "/queues", origin=capture_server.DEFAULT_ALLOWED_ORIGINS[0])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
    answer = json.loads(body) if status == 200 else {"review": [], "parked": []}
    rows = answer["review"] + answer["parked"]
    return {
        "status": status, "rows": len(rows), "distinct": len({(row["box"], row["index"]) for row in rows}),
        "queued": queued, "sql": meter.counts["sql"],
    }


def check_queue_read_flat(checks: Checks) -> None:
    """Rule 7. `GET /queues` answers one row per queued entry, each on its own position, and makes the same number of SQL
    statements at S and at 2S. The answer is held to the queued count at both sizes first: a fixture that queued the same
    few positions, or answered nothing, could not tell a flat read from one that fetches a card per entry. A meter that
    sees no statement fails as well. The rows grow here, so the rule is on the statements and not on the rows."""
    checks.note("")
    checks.note("QUEUE READ FLAT — statements per request, at S and 2S")
    problems: list = []
    small, big = _queue_read(SIZES[0]), _queue_read(SIZES[1])
    for label, got in (("S", small), ("2S", big)):
        if got["status"] != 200:
            problems.append(f"/queues answered {got['status']} at {label}")
        elif not got["rows"] == got["distinct"] == got["queued"]:
            problems.append(
                f"/queues answers {got['rows']} rows on {got['distinct']} distinct positions at {label}, the fixture queues {got['queued']}"
            )
        elif not got["sql"]:
            problems.append(f"/queues made no statement at {label}: the meter no longer sees the store")
    if not problems and big["queued"] <= small["queued"]:
        problems.append(f"the fixture's queue does not grow: {small['queued']} entries at S, {big['queued']} at 2S")
    if not problems and small["sql"] != big["sql"]:
        problems.append(
            f"/queues sql grows with the queued entries: {small['sql']} statements for {small['queued']} entries at S, "
            f"{big['sql']} for {big['queued']} at 2S. It must read the queued cards in a fixed number of statements"
        )
    for problem in problems:
        checks.ok(False, problem)
    checks.ok(not problems, "13. /queues makes the same number of statements at S and 2S, while its queued entries double")


# --------------------------------------------------------------------------- the box walk, answers

# What the three reads answer for `PIN_WORLD`. Every fact the
# walk reads is here: a name set, empty and absent, a sold, a retired and a moved record, a pooled game and an unregistered
# one, a card placed mid-box, a box of more than nine records, declared sections, a named section, and a box nothing is
# left in. The card is `(name, state, game, order, sku)` and the cards of a box are indexes 1, 2, 3 ... in this order.
_CAP, _SOLD, _GONE, _MOVED = master.CAPTURED, master.SOLD, master.RETIRED, master.MOVED
PIN_FIND = "Pikachu"
PIN_WORLD = {
    1: (
        (PIN_FIND, _CAP, None, None, "SKUPK"),
        (None, _CAP, None, None, None),
        ("", _CAP, None, None, None),
        (PIN_FIND, _SOLD, None, None, "SKUPK"),
        ("Cy", _CAP, None, None, None),
        (PIN_FIND, _CAP, "pokemon_code", None, "SKUPK"),
        ("Eve", _GONE, None, None, None),
        ("Flo", _MOVED, None, None, None),
        (None, _CAP, None, None, None),
        (None, _CAP, None, None, None),
        ("Gus", _CAP, "no_such_game", None, None),
        (PIN_FIND, _CAP, None, None, "SKUPK"),
    ),
    2: (
        (None, _CAP, None, None, None),
        (PIN_FIND, _CAP, None, None, "SKUPK"),
        ("Ivy", _SOLD, None, None, None),
        (None, _CAP, None, None, None),
        (PIN_FIND, _CAP, None, None, None),
        ("Jo", _CAP, None, 2.5, None),
    ),
    3: (
        (None, _CAP, None, None, None),
        (PIN_FIND, _CAP, None, None, "SKUPK"),
        (None, _CAP, None, None, None),
        (None, _GONE, None, None, None),
    ),
    4: (
        ("Zed", _SOLD, None, None, None),
        (None, _GONE, None, None, None),
    ),
}
PIN_BOX_NAMES = {1: "Alpha", 2: "Shelf"}
PIN_SECTIONS = {1: [1, 5, 9], 3: [1, 3]}
PIN_SECTION_NAMES = {1: {2: "Bulk"}}


def _pin_world() -> None:
    """`PIN_WORLD` in the store. Each card is stamped a second after the last, all within the sitting, so the sitting's
    order is the order they were made in. Nothing a pin reads comes from a clock."""
    from datetime import datetime, timedelta, timezone

    first = datetime.now(timezone.utc) - timedelta(minutes=10)
    with Store().write() as snapshot:
        inv = snapshot.inventory
        made = 0
        for box, cards in PIN_WORLD.items():
            inv.ensure_box(box, name=PIN_BOX_NAMES.get(box))
            for name, state, game, order, sku in cards:
                card, _ = inv.allocate_capture(box, cid=fake_cid(f"pin-{box}-{made}"))
                card.name, card.state, card.game, card.order, card.sku = name, state, game, order, sku
                card.captured_at = (first + timedelta(seconds=made)).isoformat()
                made += 1
        for box, layout in PIN_SECTIONS.items():
            inv.set_sections(box, layout)
        for box, names in PIN_SECTION_NAMES.items():
            inv.set_section_names(box, names)


def _pin_place(place: dict) -> tuple:
    """The `place` block as the walk shapes it: the numbers, the section bounds and the neighbours' index, slot, name and run."""
    near = place["neighbors"]

    def side(one):
        return None if one is None else (one["index"], one["slot"], one["name"], one["unread"])

    return (
        place["located"], place["label"], place.get("order"), place["slot"], place["section"], place["card"],
        place["section_start"], place["section_end"], place["box_total"], place["fraction"], place["section_gaps"],
        None if near is None else (side(near["prev"]), side(near["next"])),
    )


def _pin_boxes() -> list:
    return [
        (
            row["box"], row["name"], row["cards"], row["on_hand"], row["sold"], row["retired"], row["moved"],
            row["fill"], row["next_index"], [tuple(span[k] for k in ("section", "start", "end", "count", "name")) for span in row["sections_detail"]],
        )
        for row in capture_server.do_boxes()["boxes"]
    ]


def _pin_sitting() -> list:
    return [
        (row["key"], row["state"], row["label"], row["section"], row["card"], _pin_place(row["place"]))
        for row in capture_server.do_capture_sitting()["cards"]
    ]


def _pin_search() -> list:
    return [
        (group["sku"], group["on_hand"], [(copy["key"], copy["state"], _pin_place(copy["place"])) for copy in group["copies"]])
        for group in capture_server.do_search(PIN_FIND)["groups"]
    ]


def _pins() -> dict:
    """`{route: pins}` for `PIN_WORLD`: the box rows, the sitting rows in the order served, and the search groups with each copy.
    A read that raises answers the raise, so a rewrite that breaks one route fails that route and not the whole run."""
    out: dict = {}
    for route, read in (("boxes", _pin_boxes), ("sitting", _pin_sitting), ("search", _pin_search)):
        try:
            out[route] = read()
        except Exception as exc:  # noqa: BLE001
            out[route] = [f"raised {type(exc).__name__}: {exc}"]
    return out


# `_pins()` for `PIN_WORLD`, one row each. Boxes: `(box, name, cards, on_hand, sold, retired, moved, fill, next_index, [(section, start, end, count, name)])`.
# Sitting: `(key, state, label, section, card, place)`. Search: `(sku, on_hand, [(key, state, place)])`. Place: `(located, label, order, slot,
# section, card, section_start, section_end, box_total, fraction, section_gaps, (prev, next))`, a neighbour `(index, slot, name, unread)`.
PINS = {
    "boxes": [
        (1, 'Alpha', 12, 8, 1, 1, 1, 12, 13, [(1, 1, 3, 3, None), (2, 4, 4, 1, 'Bulk'), (3, 5, 8, 4, None)]),
        (2, 'Shelf', 6, 5, 1, 0, 0, 6, 7, [(1, 1, 5, 5, None)]),
        (3, 'Box 3', 4, 3, 0, 1, 0, 4, 5, [(1, 1, 2, 2, None), (2, 3, 3, 1, None)]),
        (4, 'Box 4', 2, 0, 1, 1, 0, 2, 3, [(1, 1, None, 0, None)]),
    ],
    "sitting": [
        ('1/1', 'captured', 'Alpha, Section 1, Card 1', 1, 1, (True, 'Alpha, Section 1, Card 1', 1, 1, 1, 1, 1, 3, 8, 0.0, 0, (None, (2, 2, None, 2)))),
        ('1/2', 'captured', 'Alpha, Section 1, Card 2', 1, 2, (True, 'Alpha, Section 1, Card 2', 2, 2, 1, 2, 1, 3, 8, 0.125, 0, ((1, 1, 'Pikachu', 0), (3, 3, None, 1)))),
        ('1/3', 'captured', 'Alpha, Section 1, Card 3', 1, 3, (True, 'Alpha, Section 1, Card 3', 3, 3, 1, 3, 1, 3, 8, 0.25, 0, ((2, 2, None, 1), (5, 4, 'Cy', 0)))),
        ('1/4', 'sold', 'Alpha, Section 1, Card 4', 1, None, (True, 'Alpha, Section 1, Card 4', 4, None, 1, None, 1, 3, 8, None, 0, ((3, 3, None, 2), (5, 4, 'Cy', 0)))),
        ('1/5', 'captured', 'Alpha, Section 2, Card 1', 2, 1, (True, 'Alpha, Section 2, Card 1', 5, 4, 2, 1, 4, 4, 8, 0.375, 0, ((3, 3, None, 2), (9, 5, None, 2)))),
        ('1/6', 'captured', 'Pokémon code cards \u00b7 pooled', None, None, (False, None, None, None, None, None, None, None, 0, None, None, None)),
        ('1/7', 'retired', 'Alpha, Section 2, Card 2', 2, None, (True, 'Alpha, Section 2, Card 2', 7, None, 2, None, 4, 4, 8, None, 0, ((5, 4, 'Cy', 0), (9, 5, None, 2)))),
        ('1/9', 'captured', 'Alpha, Section 3, Card 1', 3, 1, (True, 'Alpha, Section 3, Card 1', 9, 5, 3, 1, 5, 8, 8, 0.5, 0, ((5, 4, 'Cy', 0), (10, 6, None, 1)))),
        ('1/10', 'captured', 'Alpha, Section 3, Card 2', 3, 2, (True, 'Alpha, Section 3, Card 2', 10, 6, 3, 2, 5, 8, 8, 0.625, 0, ((9, 5, None, 1), (11, 7, 'Gus', 0)))),
        ('1/11', 'captured', 'Alpha, Section 3, Card 3', 3, 3, (True, 'Alpha, Section 3, Card 3', 11, 7, 3, 3, 5, 8, 8, 0.75, 0, ((10, 6, None, 2), (12, 8, 'Pikachu', 0)))),
        ('1/12', 'captured', 'Alpha, Section 3, Card 4', 3, 4, (True, 'Alpha, Section 3, Card 4', 12, 8, 3, 4, 5, 8, 8, 0.875, 0, ((11, 7, 'Gus', 0), None))),
        ('2/1', 'captured', 'Shelf, Section 1, Card 1', 1, 1, (True, 'Shelf, Section 1, Card 1', 1, 1, 1, 1, 1, 5, 5, 0.0, 1, (None, (2, 2, 'Pikachu', 0)))),
        ('2/2', 'captured', 'Shelf, Section 1, Card 2', 1, 2, (True, 'Shelf, Section 1, Card 2', 2, 2, 1, 2, 1, 5, 5, 0.2, 1, ((1, 1, None, 1), (6, 3, 'Jo', 0)))),
        ('2/3', 'sold', 'Shelf, Section 1, Card 4', 1, None, (True, 'Shelf, Section 1, Card 4', 3, None, 1, None, 1, 5, 5, None, 1, ((6, 3, 'Jo', 0), (4, 4, None, 1)))),
        ('2/4', 'captured', 'Shelf, Section 1, Card 4', 1, 4, (True, 'Shelf, Section 1, Card 4', 4, 4, 1, 4, 1, 5, 5, 0.6, 1, ((6, 3, 'Jo', 0), (5, 5, 'Pikachu', 0)))),
        ('2/5', 'captured', 'Shelf, Section 1, Card 5', 1, 5, (True, 'Shelf, Section 1, Card 5', 5, 5, 1, 5, 1, 5, 5, 0.8, 1, ((4, 4, None, 1), None))),
        ('2/6', 'captured', 'Shelf, Section 1, Card 3', 1, 3, (True, 'Shelf, Section 1, Card 3', 2.5, 3, 1, 3, 1, 5, 5, 0.4, 1, ((2, 2, 'Pikachu', 0), (4, 4, None, 1)))),
        ('3/1', 'captured', 'Box 3, Section 1, Card 1', 1, 1, (True, 'Box 3, Section 1, Card 1', 1, 1, 1, 1, 1, 2, 3, 0.0, 0, (None, (2, 2, 'Pikachu', 0)))),
        ('3/2', 'captured', 'Box 3, Section 1, Card 2', 1, 2, (True, 'Box 3, Section 1, Card 2', 2, 2, 1, 2, 1, 2, 3, 0.3333333333333333, 0, ((1, 1, None, 1), (3, 3, None, 1)))),
        ('3/3', 'captured', 'Box 3, Section 2, Card 1', 2, 1, (True, 'Box 3, Section 2, Card 1', 3, 3, 2, 1, 3, 3, 3, 0.6666666666666666, 0, ((2, 2, 'Pikachu', 0), None))),
        ('3/4', 'retired', 'Box 3, Section 2, Card 2', 2, None, (True, 'Box 3, Section 2, Card 2', 4, None, 2, None, 3, 3, 3, None, 0, ((3, 3, None, 1), None))),
        ('4/1', 'sold', 'Box 4, Section 1, Card 1', 1, None, (True, 'Box 4, Section 1, Card 1', 1, None, 1, None, 1, None, 0, None, 2, (None, None))),
        ('4/2', 'retired', 'Box 4, Section 1, Card 1', 1, None, (True, 'Box 4, Section 1, Card 1', 2, None, 1, None, 1, None, 0, None, 1, (None, None))),
    ],
    "search": [
        ('SKUPK', 5, [('1/1', 'captured', (True, 'Alpha, Section 1, Card 1', 1, 1, 1, 1, 1, 3, 8, 0.0, 0, (None, (2, 2, None, 2)))), ('1/4', 'sold', (True, 'Alpha, Section 1, Card 4', 4, None, 1, None, 1, 3, 8, None, 0, ((3, 3, None, 2), (5, 4, 'Cy', 0)))), ('1/6', 'captured', (False, None, None, None, None, None, None, None, 0, None, None, None)), ('1/12', 'captured', (True, 'Alpha, Section 3, Card 4', 12, 8, 3, 4, 5, 8, 8, 0.875, 0, ((11, 7, 'Gus', 0), None))), ('2/2', 'captured', (True, 'Shelf, Section 1, Card 2', 2, 2, 1, 2, 1, 5, 5, 0.2, 1, ((1, 1, None, 1), (6, 3, 'Jo', 0)))), ('3/2', 'captured', (True, 'Box 3, Section 1, Card 2', 2, 2, 1, 2, 1, 2, 3, 0.3333333333333333, 0, ((1, 1, None, 1), (3, 3, None, 1))))]),
        (None, 1, [('2/5', 'captured', (True, 'Shelf, Section 1, Card 5', 5, 5, 1, 5, 1, 5, 5, 0.8, 1, ((4, 4, None, 1), None)))]),
    ],
}


def check_box_walk_equivalence(checks: Checks) -> None:
    """The three reads answer `PINS` for `PIN_WORLD`: the same box rows, the same positions and neighbours, the same order.
    A row that moved, a position number, a name, a state, a neighbour or a run of unread cards that changed fails by route,
    and the first rows that differ are printed beside what was pinned."""
    checks.note("")
    checks.note("BOX WALK EQUIVALENCE — the box rows and positions the three reads answer")
    with isolated_home():
        _pin_world()
        got = _pins()
    checks.equal(sorted(got), sorted(PINS), "12. every read the world answers has its pins")
    for route, rows_ in got.items():
        want = PINS.get(route, [])
        diffs = [f"row {i}: answered {a!r}, pinned {b!r}" for i, (a, b) in enumerate(zip(rows_, want)) if a != b]
        if len(rows_) != len(want):
            diffs.append(f"{len(rows_)} rows answered, {len(want)} pinned")
        checks.ok(not diffs, f"12. {route} answers the pinned rows and positions", "\n".join(diffs[:4]))


CHECKS = (
    check_server_read_budget,
    check_detail_read_budget,
    check_markdown_table_on_hand,
    check_selection_scan_equivalence,
    check_selection_drops_strays,
    check_selection_reads_under_the_given_home,
    check_box_walk_json_flat,
    check_box_walk_equivalence,
    check_queue_read_flat,
)


if __name__ == "__main__":  # `python -m harness.tests.t7.read_budget`: print the measured tables
    from harness.tests.t7.common import hermetic

    c = Checks()
    with hermetic():
        s, sel, st = measure(c, SIZES[0])
        b, _, _ = measure(c, SIZES[1])
        for route in s:
            print(f"{route!r}: {_row(s[route])},  # {st[route]}")
        print("--- growth")
        for route in s:
            for k in CONSTANT:
                if s[route][k] != b[route][k]:
                    print(f"({route!r}, {k!r}): ({s[route][k]}, {b[route][k]}),")
        print("--- scans", {t: sorted(r) for t, r in sel.items()})
