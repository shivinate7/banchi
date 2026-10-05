"""T7 group: the server read budget, per route (D173, a rule that can be enforced is).

INCIDENT: `GET /capture/sitting` took up to 71.6 s on the owner's store, because it walked a
box once per card. PR #711 fixed it. Nothing in the suite counted work per request, so the
same shape could return in any other read route unseen. This check counts WORK, never wall time.

WHAT IT DOES. One fixture store is built at two sizes, S and 2S (the box count stays fixed,
the card, order and queue counts double). Every GET route of `CaptureHandler.do_GET`, plus the
read-only POSTs in `POST_READS`, is called once per size through a real in-process server.
`COUNTERS` are read per request: SQL statements (sqlite's trace callback on every connection
`store/db` opens), `json.loads` calls in `store/rows`, `records_in`, `layout_of`,
`_Places.__init__`, `Store.read`, `Store.write`, `read_sidecar` and `read_export`.

Four rules:
1. EXACT BUDGET. `BUDGET[route]` holds each counter's value at size S. Over it fails. Under it
   fails with "lower to N" (the `UNSCOPED_WALK_EXPECTED` ratchet in `scripts/docs_audit/core.py`).
2. GROWTH. `CONSTANT` counters must be equal at S and 2S. `json_loads` and `read_sidecar` may
   grow with the rows returned. A growing constant counter fails, unless `KNOWN_OVER` holds
   it. `KNOWN_OVER[(route, counter)] = (at S, at 2S)` must match exactly. It only shrinks: a
   counter that is now constant, or lower, fails with "remove" or "lower to".
3. ROUTES. A route `do_GET` serves with no `ROUTE_URLS` or `EXEMPT` row fails by name. So does a
   row for a route that is gone.
4. INDEX. EXPLAIN QUERY PLAN runs on every SELECT a route made. A `SCAN <table>` not in
   `SCAN_ALLOWED` fails. A stale `SCAN_ALLOWED` entry fails. The list only shrinks.
"""

from __future__ import annotations

import ast
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
    request,
    seam_run,
)
from identify import sidecar
from pipeline import tcgcsv
from server import capture_server
from store import db, files, master, orders as order_store, rows
from store.session import Store

SIZES = (150, 300)  # S and 2S: cards, orders and queue entries
BOXES = (1, 2, 3)

COUNTERS = (
    "sql", "json_loads", "records_in", "layout_of", "places",
    "store_read", "store_write", "read_sidecar", "read_export",
)
CONSTANT = ("sql", "records_in", "layout_of", "places", "store_read", "store_write", "read_export")

# Routes `do_GET` serves that this check does not call, each with the reason. A route listed
# here is named, never silent; "no budget row" for any other route fails.
EXEMPT = {
    "/tcg/sets": "opens a socket to TCGplayer",
    "POST /pipeline/preflight": "shells out; its in-process half is not a route of its own",
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
    "/pipeline/holdings-value": "/pipeline/holdings-value",
    "/pipeline/submissions": "/pipeline/submissions",
    "/pipeline/match": "/pipeline/match",
    "/pipeline/match/sweep": "/pipeline/match/sweep",
    "/pipeline/runs": "/pipeline/runs",
    "/pipeline/markdowns": "/pipeline/markdowns",
    "/pipeline/sends": "/pipeline/sends",
    "_MARKDOWN_TABLE_RE": "/pipeline/markdowns/20260101-000000",
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
}

# Read-only POSTs, named by hand: `do_GET` cannot list them.
POST_READS = {
    "POST /pipeline/waiting": ("/pipeline/waiting", {"selection": {"all": True}}),
    "POST /inventory/copies": ("/inventory/copies", {"skus": ["SKU1", "SKU2"]}),
    "POST /orders/walk-plan": ("/orders/walk-plan", {"keys": ["tcgplayer:o-1", "tcgplayer:o-2"]}),
}

# route -> {counter: value at size S}. A counter at 0 is omitted.
BUDGET = {
    '/status': {'sql': 25, 'json_loads': 3, 'store_read': 1},
    '/inventory': {'sql': 46, 'json_loads': 159, 'records_in': 5, 'places': 1, 'store_read': 1},
    '_INVENTORY_BOX_RE': {'sql': 75, 'json_loads': 51, 'records_in': 2, 'places': 1, 'store_read': 1},
    '/inventory/recent': {'sql': 26, 'json_loads': 15, 'places': 1, 'store_read': 1},
    '/inventory/history': {'sql': 12, 'store_read': 1},
    '/queues': {'sql': 22, 'json_loads': 7, 'records_in': 1, 'places': 1, 'store_read': 1},
    '/capture/sitting': {'sql': 204, 'json_loads': 159, 'records_in': 5, 'places': 1, 'store_read': 1},
    '/boxes': {'sql': 233, 'json_loads': 159, 'records_in': 5, 'places': 1, 'store_read': 1},
    '/graveyard': {'sql': 20, 'store_read': 1},
    '/games': {},
    '/orders': {'sql': 1824, 'json_loads': 300, 'store_read': 1},
    '/codes': {},
    '/codes/lots': {},
    '/search': {'sql': 175, 'json_loads': 150, 'places': 1, 'store_read': 1},
    '/skus/photos': {'sql': 13, 'json_loads': 163, 'store_read': 1},
    '_REVIEW_CATALOG_RE': {'sql': 12, 'json_loads': 2, 'store_read': 1},
    '_BOX_LISTINGS_RE': {'sql': 20, 'json_loads': 1, 'store_read': 1},
    '_BOX_PHOTOS_RE': {'sql': 19, 'json_loads': 51, 'records_in': 2, 'store_read': 1},
    '_BOXES_ITEM_RE': {},
    '_PHOTO_BY_CARD_RE': {},
    '_PHOTO_RE': {'sql': 11, 'json_loads': 1, 'store_read': 1},
    '/pricing': {},
    '/pipeline/pricing': {'sql': 65, 'json_loads': 16, 'store_read': 4, 'read_export': 1},
    '/pipeline/value': {'sql': 354, 'json_loads': 166, 'store_read': 3},
    '/pipeline/sets': {'sql': 11, 'store_read': 1},
    '/pipeline/price-now': {'sql': 23, 'json_loads': 2, 'store_read': 2},
    '/pipeline/trends-saved': {},
    '/pipeline/movers': {'sql': 11, 'json_loads': 1, 'store_read': 1},
    '/pipeline/holdings-value': {'sql': 26, 'json_loads': 150, 'store_read': 1},
    '/pipeline/submissions': {'sql': 11, 'store_read': 1},
    '/pipeline/match': {'sql': 2},
    '/pipeline/match/sweep': {'sql': 10},
    '/pipeline/runs': {'sql': 16, 'json_loads': 5, 'store_read': 1},
    '/pipeline/markdowns': {},
    '/pipeline/sends': {'sql': 44, 'store_read': 4},
    '_MARKDOWN_TABLE_RE': {},
    '_MARKDOWN_HISTORY_RE': {},
    '_MARKDOWN_TRENDS_RE': {},
    '_SEND_FILE_RE': {},
    '_MARKDOWN_FILE_RE': {},
    '_RUN_FILE_RE': {},
    '_RUN_PRICING_RE': {'sql': 27, 'json_loads': 3, 'store_read': 2},
    '_RUN_HISTORY_RE': {},
    '_RUN_TRENDS_RE': {'sql': 10, 'store_read': 1},
    '_PRODUCT_REALIZED_RE': {},
    '_PRODUCT_HISTORY_RE': {'sql': 24, 'json_loads': 153, 'store_read': 2},
    '_RUN_SCOPE_RE': {},
    '_RUN_ITEM_RE': {'sql': 16, 'json_loads': 5, 'store_read': 1},
    '_SHIPPING_FILE_RE': {},
    'POST /pipeline/waiting': {'sql': 11, 'store_read': 1, 'read_sidecar': 4},
    'POST /inventory/copies': {'sql': 53, 'json_loads': 28, 'places': 1, 'store_read': 1},
    'POST /orders/walk-plan': {'sql': 50, 'json_loads': 104, 'records_in': 2, 'places': 1, 'store_read': 1},
}

# (route, counter) -> (value at S, value at 2S): a constant counter that still grows. Only shrinks.
KNOWN_OVER = {
    ('_INVENTORY_BOX_RE', 'sql'): (75, 125),
    ('/capture/sitting', 'sql'): (204, 354),
    ('/boxes', 'sql'): (233, 383),
    ('/orders', 'sql'): (1824, 3624),
    ('/search', 'sql'): (175, 325),
    ('/pipeline/value', 'sql'): (354, 654),
    ('POST /inventory/copies', 'sql'): (53, 77),
}

# EXPLAIN QUERY PLAN `SCAN` allowed today, as `table` (no WHERE) or `table.column` (the WHERE
# column has no index, so the statement walks the table). `cards.run` is the known gap. Only shrinks.
SCAN_ALLOWED = frozenset({
    'boxes',
    'cards',
    'cards.run',
    'events.event',
    'identifications.json_extract',
    'listings',
    'orders',
    'readings',
    'readings_sources',
    'skus',
})


# --------------------------------------------------------------------------- the routes

def get_routes() -> list:
    """The GET route keys `do_GET` serves: a `path == "..."` literal, or a `_NAME_RE.match(path)`."""
    source = Path(capture_server.__file__).read_text("utf-8")
    tree = ast.parse(source)
    handler = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "CaptureHandler"
    )
    do_get = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == "do_GET")
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


class _Meter:
    """Patches the seams, counts, and puts them back. One request at a time."""

    def __init__(self) -> None:
        self.counts = dict.fromkeys(COUNTERS, 0)
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

        db_sqlite = db.sqlite3
        db.sqlite3 = _Proxy(db_sqlite, connect=connect)
        self._undo.append(lambda: setattr(db, "sqlite3", db_sqlite))

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
        return self

    def __exit__(self, *exc):
        for undo in reversed(self._undo):
            undo()
        self._undo.clear()


# --------------------------------------------------------------------------- the fixture

def _build(checks: Checks, size: int) -> dict:
    """The store at one size. Box count is fixed; cards, orders and queue entries scale."""
    from datetime import datetime, timedelta, timezone

    run, _ = seam_run(checks, [(9, 1, "Articuno", "161", None)])
    for _ in range(3):  # three real photographs in box 4, for the photo routes
        capture_server.do_capture(capture_payload(4))
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
            placed_at=f"2026-08-{1 + n % 28:02d}T10:00:00+00:00",
            lines=[order_store.OrderLine(sku=f"SKU{n % 12}", quantity=1)],
        )
        for n in range(size)
        ])
    cid = Store().read().inventory.cards[master.position_key(4, 1)].cid
    return {"run": run.directory.name, "cid": cid}


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
            calls = {key: ("GET", url.format(**names), None) for key, url in ROUTE_URLS.items()}
            calls.update({key: ("POST", url, body) for key, (url, body) in POST_READS.items()})
            origin = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
            for key, (method, url, body) in calls.items():
                with _Meter() as meter:
                    status, _, _ = request(port, method, url, origin=origin, payload=body)
                out[key] = dict(meter.counts)
                selects[key] = set(meter.selects)
                statuses[key] = status
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
        found = scans(selects)
    return out, found, statuses


def scans(selects: dict) -> dict:
    """`{key: {routes}}` for every non-covering `SCAN <table>` in an EXPLAIN QUERY PLAN of a counted
    SELECT. The key is `table.column` for the statement's first WHERE column, else `table`."""
    found: dict = {}
    conn = sqlite3.connect(str(db.path(files.inventory_dir())))
    try:
        for route, statements in selects.items():
            for statement in statements:
                try:
                    plan = conn.execute("EXPLAIN QUERY PLAN " + statement).fetchall()
                except sqlite3.Error:
                    continue  # ponytail: a statement that needs a temp table is skipped, not guessed
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
    small, found, statuses = measure(checks, SIZES[0])
    big, _, _ = measure(checks, SIZES[1])
    for route, status in statuses.items():
        if status >= 500:
            problems.append(f"{route} failed with a server error ({status})")

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
        for counter in CONSTANT:
            now = (small[route][counter], big[route][counter])
            over = KNOWN_OVER.get((route, counter))
            if now[0] == now[1]:
                if over is not None:
                    problems.append(f"{route} {counter} is constant now ({now[0]}): remove its KNOWN_OVER entry")
            elif over is None:
                problems.append(f"{route} {counter} grows with the store: {now[0]} at S, {now[1]} at 2S")
            elif now != over:
                problems.append(
                    f"{route} {counter} KNOWN_OVER {over} measured {now}"
                    + (f", lower to {now}" if now < over else ", over")
                )
    for route, _counter in sorted(KNOWN_OVER):
        if route not in small:
            problems.append(f"KNOWN_OVER names {route!r}, which is not a route")

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


CHECKS = (check_server_read_budget,)


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
