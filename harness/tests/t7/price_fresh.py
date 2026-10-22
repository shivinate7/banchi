"""T7 group: Pricing opens on fresh prices (`docs/specs/stale-listings.md`, section 7b).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them. Spec 7b's numbered checks that live on the server are
numbered in each label: 1 to 8, 10 to 13 and the server half of 21. Item 9 (no market request
on a visit) is here too. 14 to 20 are screen checks in `app/tests/`.

EVERY CHECK ASKS FOR A THING THAT MAY NOT EXIST YET, and a missing function must read as a
failed assertion with its own sentence, never as a traceback that hides the rest of the group.
`attempt` is that rule. Nothing here names a private helper of the build: the calls are the
ones the spec names (`do_prices_refresh`, the two new routes) and the files it names.

THE FAKE PORTAL IS ONE SOCKET AND IT COUNTS. Every outcome of a refresh (the file kept, the
table joined) is the same whether the portal was asked once or three times, so each case that
is about work done counts requests, as `pipeline_fetch` does for the reuse arm.
"""

from __future__ import annotations

import ast
import contextlib
import http.server
import json
import io
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs

import envfile
from harness.tests import Checks
from harness.tests.t7.common import (
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    ARTICUNO_SKU,
    REPO_ROOT,
    RIFTBOUND_EXPORT,
    QuietHandler,
    _live_export_bytes,
    _spawn_server,
    command,
    hermetic,
    isolated_home,
    request,
    seam_run,
    write_export,
)
from harness.tests.t7.send_markdown import _markdown_dir, send_portal, synced_home
from pipeline import pricehistory, pricerefresh, readings as readings_walk, reprice, tcgcsv
from server import capture_server, pipeline_routes, send_routes
from store import files
from store.readings import KIND_RUN, Reading, Source, _source_key
from store.session import Store

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "price-refresh-daily.py"

#: The real-world case from the spec: a waiting card's batch Market against its current reading.
THEN, NOW = "10.37", "16.25"
ARTICUNO_THEN, ARTICUNO_NOW = "20.00", "30.00"

#: What a refresh may ask the portal for. Reading, never writing: a catalog export (POST that
#: answers a CSV), its filter vocabulary and the live listings download.
READ_ONLY = {("POST", "downloadexportcsv"), ("GET", "getjsonfilters"), ("GET", "downloadmyexportcsv")}


def attempt(checks: Checks, label: str, fn):
    """`fn()`'s answer, or `None` after one failed check that carries the exception."""
    try:
        return fn()
    except Exception as caught:  # noqa: BLE001 - any failure is the red this exists to show
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
        return None


def second_of(value):
    """An epoch second out of an int, a float or an ISO string. `None` for anything else."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    return None


@contextmanager
def world(checks: Checks, *, extra_runs: int = 0, disjoint: bool = False):
    """A store with open Pokemon runs holding a stale Market, and a portal that serves a new one.

    Run one holds Dunsparce at the batch Market `THEN` and Articuno. `extra_runs` more runs of
    the same game follow, each in its own box. The portal's catalog answer has Dunsparce at `NOW`.
    The capture server listens on its own port; the portal on another. Both are torn down.
    """
    keys = ("BANCHI_TCG_EXPORT_URL", "TCGPLAYER_STORE_COOKIE", "BANCHI_TCG_USER_AGENT", envfile.FROM_FILE_ENV)
    previous = {name: os.environ.get(name) for name in keys}
    stub = {
        "mode": "csv", "body": b"", "live_body": b"", "requests": [], "asked_sets": [], "asked_categories": [],
        "catalog_gate": None, "catalog_reached": threading.Event(), "by_category": {}, "gate": None, "reached": threading.Event(),
        "filters": {
            "Sets": [
                {"Text": "All Set Names", "Value": "0"},
                {"Text": "SV09: Journey Together", "Value": "4242"},
                {"Text": "SV08: Surging Sparks", "Value": "4343"},
            ],
            "Rarities": [{"Text": "All Rarities", "Value": "0"}],
            "Conditions": [{"Text": "All Conditions", "Value": "0"}],
            "Printings": [{"Text": "All Printings", "Value": "0"}],
        },
    }

    class Portal(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def _record(self):
            leaf = self.path.split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
            stub["requests"].append((self.command, leaf))
            return leaf

        def _send(self, status, body, kind="text/csv"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            leaf = self._record()
            if leaf == "getjsonfilters":
                return self._send(200, json.dumps(stub["filters"]).encode(), "application/json")
            if leaf == "downloadmyexportcsv":
                stub["reached"].set()
                if stub["gate"] is not None:
                    stub["gate"].wait(30)
                return self._send(200, stub["live_body"])
            return self._send(404, b"")

        def do_POST(self):  # noqa: N802
            sent = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self._record()
            model = json.loads((parse_qs(sent.decode()).get("model") or ["{}"])[0])  # `model=<json>`, form-encoded
            stub["asked_categories"].append(str(model.get("CategoryId")))
            if stub.get("catalog_gate") is not None:
                stub["catalog_reached"].set()
                stub["catalog_gate"].wait(30)
            if stub["mode"] == "waf":
                return self._send(403, b"")
            if str(model.get("CategoryId")) in stub.get("by_category", {}):
                return self._send(200, stub["by_category"][str(model.get("CategoryId"))])
            if stub.get("by_set"):  # the portal answers only the sets the request names
                wanted = model.get("SetNameIds") or []
                stub["asked_sets"].append(list(wanted))
                rows = [row for set_id, held in stub["by_set"].items() if set_id in wanted for row in held]
                scratch = Path(tempfile.mkdtemp()) / "scoped.csv"
                tcgcsv.write_csv(scratch, stub["header"], rows)
                return self._send(200, scratch.read_bytes())
            return self._send(200, stub["body"])

    portal = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Portal)  # a gated request must not block the next caller
    portal.daemon_threads = True
    _spawn_server(portal)
    try:
        with isolated_home() as home, hermetic():
            os.environ.pop(envfile.FROM_FILE_ENV, None)
            envfile._from_file.clear()
            os.environ["BANCHI_TCG_EXPORT_URL"] = f"http://127.0.0.1:{portal.server_address[1]}/admin/pricing/downloadexportcsv"
            os.environ["TCGPLAYER_STORE_COOKIE"] = "TCGAuthTicket_Production=t7-not-a-real-session"
            os.environ.pop("BANCHI_TCG_USER_AGENT", None)

            made = []
            cards = [(3, 1, "Dunsparce", "120/159", "normal"), (3, 2, "Articuno", "161", None)]
            if disjoint:
                cards = cards[:1]
            first, _ = seam_run(checks, cards, market={DUNSPARCE_SKU: THEN})
            made.append(first)
            for at in range(extra_runs):
                more, _ = seam_run(checks, [(4 + at, 1, "Dunsparce", "120/159", "normal")], market={DUNSPARCE_SKU: THEN})
                made.append(more)
            for run in made:  # a Pokemon run names its sets, as the owner's store does
                path = run.directory / pipeline_routes.run_files.IDENTIFICATIONS
                payload = json.loads(path.read_text())
                for card in payload["cards"].values():
                    card["set_hint"] = "SV09"
                path.write_text(json.dumps(payload))

            if disjoint:  # a second run of the same game, on a different resolvable set
                other, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)], market={ARTICUNO_SKU: ARTICUNO_THEN})
                path = other.directory / pipeline_routes.run_files.IDENTIFICATIONS
                payload = json.loads(path.read_text())
                for card in payload["cards"].values():
                    card["set_hint"] = "SV08"
                path.write_text(json.dumps(payload))
                made.append(other)
                fresh = tcgcsv.read_export(write_export(home / "both-sets.csv", market={DUNSPARCE_SKU: NOW, ARTICUNO_SKU: ARTICUNO_NOW}))
                stub["header"] = fresh.header
                stub["by_set"] = {
                    "4242": [r for r in fresh.rows if r[tcgcsv.SKU_COLUMN] != ARTICUNO_SKU],
                    "4343": [dict(r, **{"Set Name": "SV08: Surging Sparks"}) for r in fresh.rows if r[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU],
                }
            stub["body"] = write_export(home / "new-catalog.csv", market={DUNSPARCE_SKU: NOW}).read_bytes()
            stub["live_body"] = _live_export_bytes({DUNSPARCE_SKU: 0})
            httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
            _spawn_server(httpd)
            try:
                yield SimpleNamespace(
                    home=home, runs=made, stub=stub, port=httpd.server_address[1],
                    names=[run.directory.name for run in made],
                )
            finally:
                httpd.shutdown()
                httpd.server_close()
    finally:
        portal.shutdown()
        portal.server_close()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def refuse_history(checks=None):
    """Step 4 asks the market host for nothing: every SKU is refused, and the count is kept."""
    asked = {"built": 0}

    class Market:
        def __init__(self, **_kw):
            asked["built"] += 1

        def readings_for_rows(self, rows, product_ids=None):
            return {}, {row[tcgcsv.SKU_COLUMN]: "the mirror refused the request" for row in rows}

    real = pricehistory.Market, pricehistory.catalogued_row
    pricehistory.Market, pricehistory.catalogued_row = Market, lambda row: True
    return asked, lambda: setattr(pricehistory, "Market", real[0]) or setattr(pricehistory, "catalogued_row", real[1])


def row_of(sku: str, worklist: dict):
    return next((row for row in worklist["skus"] if row["sku"] == sku), None)


def table_of(run) -> dict:
    return json.loads((run.directory / "pricing.json").read_text())


def table_row(run, sku: str) -> dict:
    """The table row for a SKU, or an empty one: a card the join dropped is a failed assertion, not a crash."""
    empty = {"snap": {}, "rule_price": None, "bucket": None, "presets": {}}
    return next((row for row in table_of(run)["skus"] if row["sku"] == sku), empty)


def sent_price(run_dir: Path, sku: str):
    """The `TCG Marketplace Price` an `emit` over one run wrote for one SKU, or `None`."""
    for path in sorted(run_dir.glob("import*.csv")):
        for row in tcgcsv.read_export(path).rows:
            if row.get(tcgcsv.SKU_COLUMN) == sku and row.get(tcgcsv.PRICE_COLUMN):
                return row[tcgcsv.PRICE_COLUMN]
    return None


def decimal_of(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------- Item 1, 2, 3, 7, 8


def check_refresh_rewrites_the_waiting_row(checks: Checks) -> None:
    """Item 1, 2, 3, 7 and 8, on one refresh of three open runs of one game.

    THE REAL-WORLD CASE IS THE FIXTURE: a waiting card whose run-time Market is $10.37 while the
    current reading is $16.25. After the job the run table, the worklist and the send all say
    $16.25, and the row carries the time the catalog was read. A typed price for Articuno sits in
    `prices.json` the whole time and is compared byte for byte.
    """
    checks.note("")
    checks.note("PRICES REFRESH — the morning job re-reads the catalog and re-joins every open run")

    with world(checks, extra_runs=2) as w:
        first = w.runs[0]
        before_row = table_row(first, DUNSPARCE_SKU)
        checks.equal(before_row["snap"]["market"], THEN, "the fixture starts stale: the batch Market is $10.37")

        typed = files.prices_path()
        typed.write_text(json.dumps({
            "version": 1,
            "policy": {"rule": "match", "basis": "market"},
            "skus": {ARTICUNO_SKU: {"value": "12.34"}},
        }, indent=2))
        typed_bytes = typed.read_bytes()

        asked, undo = refuse_history()
        started = int(time.time())
        try:
            answer = attempt(
                checks, "1. `pipeline_routes.do_prices_refresh` exists and runs over the open runs",
                lambda: pipeline_routes.do_prices_refresh(),
            )
        finally:
            undo()
        checks.ok(answer is not None, "1. the refresh ran to its end", "no answer: see the line above")

        for run in w.runs:
            row = table_row(run, DUNSPARCE_SKU)
            checks.equal(
                (row["snap"]["market"], row["rule_price"], row["bucket"], row["presets"]["market_match"]),
                (NOW, NOW, "listable", NOW),
                f"1. {run.directory.name}: the run table carries the new Market, the bucket and the rule price",
            )

        worklist = pipeline_routes.do_pipeline_worklist([])
        waiting = row_of(DUNSPARCE_SKU, worklist) or {}
        checks.equal(
            (waiting.get("snap") or {}).get("market"), NOW,
            "1. real-world case: a waiting card at $10.37 in its batch shows $16.25 after the job",
        )
        kept = sorted((w.home / "inventory" / files.EXPORTS_DIRNAME / "pokemon").glob("*.csv"))
        stamped = second_of(waiting.get("snap_at"))
        checks.ok(
            stamped is not None and kept and abs(stamped - int(kept[-1].stat().st_mtime)) <= 2 and stamped >= started - 2,
            "1. and its row carries `snap_at`, the fetch time of the export it was joined against",
            f"snap_at={waiting.get('snap_at')!r} export mtimes={[int(p.stat().st_mtime) for p in kept]}",
        )

        command(checks, "emit", str(first.directory))
        sent = sent_price(first.directory, DUNSPARCE_SKU)
        checks.equal(
            (sent, waiting.get("rule_price")), (NOW, NOW),
            "2. the send writes the price the worklist row proposes: $16.25, not the stale $10.37",
        )

        checks.equal(typed.read_bytes(), typed_bytes, "3. a typed answer survives: `prices.json` is byte-equal")
        checks.equal(
            sent_price(first.directory, ARTICUNO_SKU), "12.34",
            "3. and the send still lists the typed card at the typed price",
        )

        posts = sum(1 for method, leaf in w.stub["requests"] if (method, leaf) == ("POST", "downloadexportcsv"))
        checks.equal(posts, 1, "7. three open runs of one game cost one catalog request")

        wrote = {(m, leaf) for m, leaf in w.stub["requests"]} - READ_ONLY
        checks.equal(wrote, set(), "8. the refresh asked the portal for nothing it could write with")
        checks.equal(asked["built"] >= 0, True, "(the history stub was reached or not: either is fine for this arm)")


def check_disjoint_scopes_share_one_request(checks: Checks) -> None:
    """Two open runs of one game on different sets both get current prices from one request.

    THE PORTAL ANSWERS ONLY THE SETS THE REQUEST NAMES, because a stub that serves every row to
    every scope cannot tell a request for the union from a request for the first run's sets.
    A catalog fetch that kept the first run's scope would serve run two's Articuno nothing.
    """
    checks.note("")
    checks.note("PRICES REFRESH — disjoint set hints, one request for the union")
    with world(checks, disjoint=True) as w:
        asked, undo = refuse_history()
        try:
            attempt(checks, "two runs of one game: the refresh runs", lambda: pipeline_routes.do_prices_refresh())
        finally:
            undo()
        posts = sum(1 for call in w.stub["requests"] if call == ("POST", "downloadexportcsv"))
        checks.equal(posts, 1, "disjoint hints: exactly one catalog request for the game")
        checks.equal(
            sorted(set(sum(w.stub["asked_sets"], []))), ["4242", "4343"],
            "and that request names both runs' sets",
        )
        checks.equal(
            (table_row(w.runs[0], DUNSPARCE_SKU)["snap"].get("market"), table_row(w.runs[1], ARTICUNO_SKU)["snap"].get("market")),
            (NOW, ARTICUNO_NOW),
            "and both runs' tables hold the new Market",
        )


def check_join_is_idempotent(checks: Checks) -> None:
    """Item 4. Joining twice against one export leaves `pricing.json` identical."""
    checks.note("")
    checks.note("RE-JOIN — idempotent")
    with world(checks) as w:
        first = w.runs[0]
        fetched = attempt(
            checks, "4. the catalog export can be fetched for a run",
            lambda: pipeline_routes.do_pipeline_export(w.names[0], {"refresh": True}),
        )
        if fetched is None:
            return
        pipeline_routes.do_pipeline_step(w.names[0], "join", {"fetched": [fetched["file"]]})
        once = (first.directory / "pricing.json").read_bytes()
        pipeline_routes.do_pipeline_step(w.names[0], "join", {"fetched": [fetched["file"]]})
        twice = (first.directory / "pricing.json").read_bytes()
        checks.equal(twice == once, True, "4. a second join against the same export gives byte-identical `pricing.json`")


# ------------------------------------------------------------------------- Item 5 and 6


def check_refresh_order_and_failure(checks: Checks) -> None:
    """Item 5 and 6. Order of the steps; a failed history keeps 1 to 3; a refused catalog keeps the tables."""
    checks.note("")
    checks.note("PRICES REFRESH — order, and a failure keeps the last good figures")

    with world(checks) as w:
        order = []
        real = {}
        for name in ("do_live_export", "do_pipeline_export", "do_pipeline_step", "do_price_trends_preload"):
            real[name] = getattr(pipeline_routes, name)

            def wrapped(*args, __name=name, **kw):
                if __name in ("do_pipeline_step",) and args[1:2] != ("join",):
                    return real[__name](*args, **kw)
                order.append(__name)
                if __name == "do_price_trends_preload":
                    raise RuntimeError("the market host is down")
                return real[__name](*args, **kw)

            setattr(pipeline_routes, name, wrapped)
        try:
            attempt(checks, "5. the refresh survives a history step that throws", lambda: pipeline_routes.do_prices_refresh())
        finally:
            for name, fn in real.items():
                setattr(pipeline_routes, name, fn)

        collapsed = [name for at, name in enumerate(order) if at == 0 or order[at - 1] != name]
        checks.equal(
            collapsed,
            ["do_live_export", "do_pipeline_export", "do_pipeline_step", "do_price_trends_preload"],
            "5. the steps run listings, catalog, join, history",
        )
        note = pricerefresh.read_status() or {}
        steps = note.get("steps") or {}
        done = list(steps.values())
        checks.ok(
            len(done) >= 4 and all(s.get("ok") is True and s.get("at") for s in done[:3]) and done[3].get("ok") is False,
            "5. steps 1 to 3 are recorded ok with their time, and the history step is recorded failed",
            json.dumps(note)[:400],
        )
        checks.equal(
            table_row(w.runs[0], DUNSPARCE_SKU)["snap"]["market"], NOW,
            "5. and the join before the failed history still stands: the header time and the figure are set",
        )

    with world(checks) as w:
        before = (w.runs[0].directory / "pricing.json").read_bytes()
        w.stub["mode"] = "waf"
        asked, undo = refuse_history()
        try:
            attempt(checks, "6. a refused catalog fetch does not raise out of the refresh", lambda: pipeline_routes.do_prices_refresh())
        finally:
            undo()
        checks.equal(
            (w.runs[0].directory / "pricing.json").read_bytes() == before, True,
            "6. a refused catalog fetch changes no run table",
        )
        steps = (pricerefresh.read_status() or {}).get("steps") or {}
        failed = [s for s in steps.values() if s.get("ok") is False]
        checks.ok(
            bool(failed) and all(s.get("message") or s.get("code") for s in failed),
            "6. and records its own sentence in `price-refresh.json`",
            json.dumps(pricerefresh.read_status())[:400],
        )


# ------------------------------------------------------------- the reading, and the daily job


def check_reading_is_one_whole_row(checks: Checks) -> None:
    """Item 10. A run table and a newer live row give one whole reading, never a mix."""
    checks.note("")
    checks.note("ONE HOME — a reading keeps all four cells from one source and one second")
    with isolated_home(), hermetic():
        run, _ = seam_run(checks, [(3, 1, "Dunsparce", "120/159", "normal")])
        older = table_row(run, DUNSPARCE_SKU)
        checks.equal(
            (older["snap"]["low"], older["snap"]["low_with_shipping"]), ("1.48", "2.97"),
            "10. the run table carries a Lowest of 1.48 and 2.97 with shipping",
        )
        live = files.inventory_dir() / pipeline_routes.LIVE_DIR
        live.mkdir(parents=True, exist_ok=True)
        source = tcgcsv.read_export(write_export(live / "scratch.csv"))
        row = dict(next(r for r in source.rows if r[tcgcsv.SKU_COLUMN] == DUNSPARCE_SKU))
        row[tcgcsv.MARKET_PRICE_COLUMN] = NOW
        row["TCG Low Price"] = ""  # blank on the newer row: a mix would borrow 1.48 from the older one
        row["TCG Low Price With Shipping"] = "17.0000"
        newer = live / (files.LIVE_PREFIX + "20991231-000000.csv")
        tcgcsv.write_csv(newer, source.header, [row])
        (live / "scratch.csv").unlink()

        found, _sources = readings_walk.collect()
        got = found.get(DUNSPARCE_SKU)
        checks.ok(got is not None and got.market == NOW, "10. the newest source wins the Market", str(got))
        fields = [getattr(got, name, "absent") for name in ("low", "low_with_shipping", "direct_low")]
        checks.ok(
            "absent" not in fields,
            "10. `Reading` carries `low`, `low_with_shipping` and `direct_low`",
            f"missing on {got!r}",
        )
        if "absent" not in fields:
            checks.ok(
                not fields[0] and decimal_of(fields[1]) == Decimal("17.00"),
                "10. one whole row: the blank Lowest of the newer row is not filled from the older run table",
                f"low={fields[0]!r} low_with_shipping={fields[1]!r}",
            )


def check_daily_job_reaches_only_the_refresh(checks: Checks) -> None:
    """Item 8's static half. `do_prices_refresh` reaches no write. The job script's own fence is re-pointed in `price_moves`."""
    checks.note("")
    checks.note("DAILY JOB — one function, and nothing in it writes at TCGplayer")
    tree = ast.parse(Path(pipeline_routes.__file__).read_text())
    body = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "do_prices_refresh"), None)
    checks.ok(body is not None, "8. `do_prices_refresh` is defined in `server/pipeline_routes.py`")
    if body is not None:
        called = {
            (n.func.id if isinstance(n.func, ast.Name) else n.func.attr)
            for n in ast.walk(body) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
        }
        writers = sorted(c for c in called if re.search(r"send|publish|upload|push|apply|emit|take_back|identify|sweep", c))
        checks.equal(writers, [], "8. it calls no send, upload, emit, paid read or sweep")


# --------------------------------------------------------------------- the routes, 9 and 11


def check_refresh_route(checks: Checks) -> None:
    """Item 11. 202 on a press, `running` on a second, a refusal inside the reuse window, `force` overrides."""
    checks.note("")
    checks.note("POST /pipeline/prices/refresh — one at a time, and not twice in a row")
    with world(checks) as w:
        asked, undo = refuse_history()
        try:
            w.stub["gate"] = threading.Event()
            status, raw, _ = request(w.port, "POST", "/pipeline/prices/refresh", payload={})
            checks.equal(status, 202, "11. a press answers 202 and starts the work")
            if status == 202:
                w.stub["reached"].wait(15)
                status2, raw2, _ = request(w.port, "POST", "/pipeline/prices/refresh", payload={})
                checks.ok(
                    b"running" in raw2 and w.stub["requests"].count(("GET", "downloadmyexportcsv")) == 1,
                    "11. a second press while one runs answers `running` and starts nothing",
                    f"{status2} {raw2[:200]!r}",
                )
            w.stub["gate"].set()
            ended = {}
            deadline = time.time() + 60
            while time.time() < deadline:
                state, body, _ = request(w.port, "GET", "/pipeline/prices/refresh")
                ended = json.loads(body or b"{}") if state == 200 else {}
                if ended.get("state") not in ("running", "starting"):
                    break
                time.sleep(0.1)
            checks.ok(
                ended.get("state") not in (None, "running", "starting"),
                "11. `GET /pipeline/prices/refresh` reports `{state, step, done, total, note}` and the run ends",
                str(ended),
            )
            if status == 202:
                again, _raw, _ = request(w.port, "POST", "/pipeline/prices/refresh", payload={})
                checks.ok(400 <= again < 500, "11. a press inside `EXPORT_REUSE_S` of a finished run is refused", str(again))
                forced, _raw, _ = request(w.port, "POST", "/pipeline/prices/refresh", payload={"force": True})
                checks.equal(forced, 202, "11. and `force` presses anyway")
                time.sleep(0.2)
        finally:
            w.stub["gate"].set()
            undo()
            # let a forced run finish before the store goes away
            deadline = time.time() + 60
            while time.time() < deadline:
                state, body, _ = request(w.port, "GET", "/pipeline/prices/refresh")
                if state != 200 or json.loads(body or b"{}").get("state") not in ("running", "starting"):
                    break
                time.sleep(0.1)


def check_visit_asks_no_market_host(checks: Checks) -> None:
    """Item 9. Reading the worklist, the saved strips and a product's facts opens no market request."""
    checks.note("")
    checks.note("A VISIT AND A PRESS OF T — no request at any market host")
    with world(checks) as w:
        asked = {"built": 0, "fetched": 0}

        class Market:
            def __init__(self, **_kw):
                asked["built"] += 1

        real_market, real_fetch = pricehistory.Market, pricehistory.fetch_json
        pricehistory.Market = Market
        pricehistory.fetch_json = lambda *a, **k: asked.__setitem__("fetched", asked["fetched"] + 1) or {}
        try:
            seen = {}
            for path in (
                "/pipeline/pricing", "/pipeline/trends-saved", "/pipeline/movers",
                f"/pipeline/price-facts?sku={DUNSPARCE_SKU}",
            ):
                seen[path.split("?")[0]] = request(w.port, "GET", path)[0]
        finally:
            pricehistory.Market, pricehistory.fetch_json = real_market, real_fetch
        checks.equal((asked["built"], asked["fetched"]), (0, 0), "9. none of the four local reads touched a market host")
        checks.equal(
            seen.get("/pipeline/price-facts"), 200,
            "9. and the read a press of T makes (`GET /pipeline/price-facts?sku=`) is a local one that answers",
        )
        checks.equal(w.stub["requests"], [], "9. nor did any of them open the portal")


# ----------------------------------------------------------------------- 12 and 13


def _series(quantities, *, product_id=1):
    """A `Series` of daily buckets, ascending, ending on 2026-09-30. Each entry is
    `(units, low, high, market)`; market is the day's standing price."""
    buckets = []
    start = 30 - len(quantities) + 1
    for at, (units, low, high, market) in enumerate(quantities):
        buckets.append({
            "bucketStartDate": f"2026-09-{start + at:02d}", "marketPrice": market, "quantitySold": units,
            "transactionCount": 1 if units else 0, "lowSalePrice": low, "highSalePrice": high,
        })
    payload = {"skuId": "1", "variant": "", "condition": "", "language": "", "totalQuantitySold": sum(q[0] for q in quantities),
               "totalTransactionCount": sum(1 for q in quantities if q[0]), "buckets": buckets}
    return pricehistory.Series.parse(payload, product_id, "month")


def _get(thing, *names):
    for name in names:
        if isinstance(thing, dict) and name in thing:
            return thing[name]
        if hasattr(thing, name):
            return getattr(thing, name)
    return "absent"


def check_series_window(checks: Checks) -> None:
    """Item 12. `Series.window(days)` is the one function for the row's and the panel's figures."""
    checks.note("")
    checks.note("SERIES WINDOW — units, average and range over the newest days")
    series = _series([
        (9, "1.00", "2.00", "1.50"), (9, "1.00", "2.00", "1.50"),  # outside the window
        (2, "9.00", "11.00", "10.00"), (0, None, None, "10.50"), (4, "10.00", "14.00", "12.00"),
    ])
    got = attempt(checks, "12. `Series.window` exists", lambda: series.window(3))
    if got is None:
        return
    units, low, high = _get(got, "units", "units_sold", "quantity"), _get(got, "low"), _get(got, "high")
    average = _get(got, "average", "avg", "vwap", "average_price")
    checks.equal((units, decimal_of(low), decimal_of(high)), (6, Decimal("9.00"), Decimal("14.00")), "12. the newest 3 days: 6 units, low 9, high 14")
    checks.ok(
        decimal_of(average) is not None and abs(decimal_of(average) - Decimal("11.3333")) < Decimal("0.02"),
        "12. the average is the volume-weighted price, 11.33",
        f"average={average!r}",
    )
    idle = _series([(0, None, None, "5.00"), (0, None, None, "5.00"), (0, None, None, "5.00")])
    quiet = attempt(checks, "12. a window with no sales answers", lambda: idle.window(3))
    if quiet is not None:
        checks.equal(
            (_get(quiet, "units", "units_sold", "quantity"), _get(quiet, "average", "avg", "vwap", "average_price")),
            (0, None),
            "12. a window with no sales gives an average of none, never zero",
        )


def check_saved_file_and_routes(checks: Checks) -> None:
    """Item 13. The preload writes `facts`, `days` and `through`; `trends-saved` omits `days`; `price-facts` serves them."""
    checks.note("")
    checks.note("SAVED FILE — facts, days and through; the first paint stays small")
    with world(checks) as w:
        series = _series([(1, "9.00", "11.00", "10.00"), (0, None, None, "10.00"), (3, "10.00", "14.00", "12.00")])
        first_range = pricehistory.DEFAULT_RANGES[0]

        class Market:
            def __init__(self, **_kw):
                pass

            def readings_for_rows(self, rows, product_ids=None):
                return {row[tcgcsv.SKU_COLUMN]: SimpleNamespace(product_id=1, series={first_range: series}) for row in rows}, {}

        real = pricehistory.Market, pricehistory.catalogued_row
        pricehistory.Market, pricehistory.catalogued_row = Market, lambda row: True
        try:
            attempt(checks, "13. the preload runs", lambda: pipeline_routes.do_price_trends_preload())
        finally:
            pricehistory.Market, pricehistory.catalogued_row = real
        saved = pricerefresh.read_trends().get(DUNSPARCE_SKU) or {}
        checks.ok(
            {"facts", "days", "through"} <= set(saved),
            "13. the saved entry for a SKU carries `facts`, `days` and `through` beside `ranges`",
            f"keys={sorted(saved)}",
        )
        checks.equal(saved.get("through"), "2026-09-30", "13. `through` is the date of the newest bucket")
        checks.equal(len(saved.get("days") or []), 3, "13. `days` holds one tuple per bucket the history gave")

        status, raw, _ = request(w.port, "GET", "/pipeline/trends-saved")
        entry = (json.loads(raw or b"{}").get("skus") or {}).get(DUNSPARCE_SKU, {})
        checks.ok(
            status == 200 and "facts" in entry and "ranges" in entry and "days" not in entry,
            "13. `trends-saved` serves `ranges` and `facts` and leaves out `days`",
            f"{status} keys={sorted(entry)}",
        )
        status, raw, _ = request(w.port, "GET", f"/pipeline/price-facts?sku={DUNSPARCE_SKU}")
        body = json.loads(raw or b"{}") if status == 200 else {}
        checks.ok(
            status == 200 and len(body.get("days") or []) == 3,
            "13. `GET /pipeline/price-facts?sku=` serves the days of one SKU",
            f"{status} {raw[:200]!r}",
        )


# ------------------------------------------------------------------------------ 21


def check_live_read_rejoins(checks: Checks) -> None:
    """Item 21, server half. The route a Live tab "read again" calls ends with the open runs re-joined,
    and the row's `snap_at` equals the read time `price-facts` serves."""
    checks.note("")
    checks.note("LIVE READ AGAIN — ends in steps 2 and 3, one time per card")
    with world(checks) as w:
        before = table_row(w.runs[0], DUNSPARCE_SKU)["snap"]["market"]
        status, raw, _ = request(w.port, "POST", "/pipeline/live-export", payload={})
        checks.equal(status, 202, "21. the live press answers 202 and the work runs in the background worker")
        ended = {}
        deadline = time.time() + 60
        while time.time() < deadline:
            state, body, _ = request(w.port, "GET", "/pipeline/prices/refresh")
            ended = json.loads(body or b"{}") if state == 200 else {}
            if ended.get("state") not in ("running", "starting"):
                break
            time.sleep(0.1)
        checks.equal(ended.get("state"), "done", "21. `GET /pipeline/prices/refresh` reaches done")
        checks.equal(
            (before, table_row(w.runs[0], DUNSPARCE_SKU)["snap"]["market"]), (THEN, NOW),
            "21. and it ends with the open runs re-joined: $10.37 became $16.25",
        )
        steps = (pricerefresh.read_status() or {}).get("steps") or {}
        checks.ok(len(steps) >= 3, "21. it records the same `steps.<name>` notes as a refresh", json.dumps(steps)[:300])
        row = row_of(DUNSPARCE_SKU, pipeline_routes.do_pipeline_worklist([])) or {}
        status, raw, _ = request(w.port, "GET", f"/pipeline/price-facts?sku={DUNSPARCE_SKU}")
        facts = json.loads(raw or b"{}") if status == 200 else {}
        read_at = second_of(facts.get("at") or (facts.get("prices") or {}).get("at") or facts.get("read_at"))
        checks.ok(
            read_at is not None and read_at == second_of(row.get("snap_at")),
            "21. the row's `snap_at` and the T panel's read time are equal afterward",
            f"snap_at={row.get('snap_at')!r} facts keys={sorted(facts)}",
        )


# ------------------------------------------------------------ the PR #749 review defects


def check_live_press_returns_at_once(checks: Checks) -> None:
    """Review defect 1. The Live tab's "read again" goes through the background worker, so the POST
    holds no request slot through the catalog fetch and the joins."""
    checks.note("")
    checks.note("LIVE READ AGAIN — the POST returns at once, the work runs behind it")
    with world(checks) as w:
        asked, undo = refuse_history()
        w.stub["catalog_gate"] = threading.Event()  # the catalog request stays open until released
        done = {}

        def press():
            began = time.time()
            done["answer"] = request(w.port, "POST", "/pipeline/live-export", payload={})
            done["seconds"] = time.time() - began

        thread = threading.Thread(target=press, daemon=True)
        try:
            thread.start()
            thread.join(6)
            checks.ok(
                not thread.is_alive() and done.get("seconds", 99) < 5,
                "1. `POST /pipeline/live-export` answers while the catalog request is still open",
                f"still waiting after 6 s with the catalog gated; answer={done.get('answer')!r}",
            )
            status, body, _ = request(w.port, "GET", "/pipeline/prices/refresh")
            state = json.loads(body or b"{}").get("state") if status == 200 else None
            checks.equal(state, "running", "1. and the work is running behind it, as Refresh now's state shows")
        finally:
            w.stub["catalog_gate"].set()
            thread.join(30)
            deadline = time.time() + 60
            while time.time() < deadline:
                status, body, _ = request(w.port, "GET", "/pipeline/prices/refresh")
                if status != 200 or json.loads(body or b"{}").get("state") not in ("running", "starting"):
                    break
                time.sleep(0.1)
            undo()


def check_two_game_run_is_refreshed_for_both(checks: Checks) -> None:
    """Review defect 2. An open run holding two games is refreshed for both: one request per game,
    no `game_required`, and the job's steps 1 to 3 are ok (so the daily job exits 0)."""
    checks.note("")
    checks.note("PRICES REFRESH — one open run, two games")
    with world(checks) as w:
        first = w.runs[0]
        path = first.directory / pipeline_routes.run_files.IDENTIFICATIONS
        payload = json.loads(path.read_text())
        key = sorted(payload["cards"])[-1]
        payload["cards"][key]["game"] = "riftbound"
        payload["cards"][key]["set_hint"] = None
        payload["cards"][key]["identification"].update(name="Acceptable Losses", number="179/298")
        path.write_text(json.dumps(payload))
        w.stub["by_category"] = {"89": (Path(tcgcsv.__file__).resolve().parents[1] / "fixtures" / "riftbound_export_untouched.csv").read_bytes()}
        asked, undo = refuse_history()
        try:
            answer = attempt(checks, "2. the refresh does not raise over a two-game run", lambda: pipeline_routes.do_prices_refresh())
        finally:
            undo()
        catalog = ((pricerefresh.read_status() or {}).get("steps") or {}).get("catalog") or {}
        checks.ok(
            catalog.get("ok") is True and "more than one game" not in str(catalog.get("message")),
            "2. the catalog step is ok, and never says `game_required`",
            json.dumps(catalog)[:300],
        )
        checks.equal(sorted(set(w.stub["asked_categories"])), ["3", "89"], "2. each game of the run is asked for, one category each")
        checks.equal(
            table_row(first, DUNSPARCE_SKU)["snap"].get("market"), NOW,
            "2. and the run's Pokemon card is current",
        )
        checks.equal((answer or {}).get("ok"), True, "2. steps 1 to 3 are ok, so the daily job exits 0")


def check_live_rows_get_saved_strips(checks: Checks) -> None:
    """Review defect 3. A listed SKU that no open run holds is read by the morning job too."""
    checks.note("")
    checks.note("MORNING JOB — Live-tab rows get saved strips")
    with world(checks) as w:
        w.stub["live_body"] = _live_export_bytes({DUNSPARCE_SKU: 0, DUNSPARCE_REVERSE_SKU: 1})
        series = _series([(1, "9.00", "11.00", "10.00"), (3, "10.00", "14.00", "12.00")])
        first_range = pricehistory.DEFAULT_RANGES[0]

        class Market:
            def __init__(self, **_kw):
                pass

            def readings_for_rows(self, rows, product_ids=None):
                return {row[tcgcsv.SKU_COLUMN]: SimpleNamespace(product_id=1, series={first_range: series}) for row in rows}, {}

        real = pricehistory.Market, pricehistory.catalogued_row
        pricehistory.Market, pricehistory.catalogued_row = Market, lambda row: True
        try:
            attempt(checks, "3. the live listings are read", lambda: pipeline_routes.do_live_export())
            attempt(checks, "3. the strips are read", lambda: pipeline_routes.do_price_trends_preload())
        finally:
            pricehistory.Market, pricehistory.catalogued_row = real
        saved = pricerefresh.read_trends()
        checks.ok(DUNSPARCE_SKU in saved, "3. a worklist card has its saved strip (control)", f"saved={sorted(saved)}")
        checks.ok(
            DUNSPARCE_REVERSE_SKU in saved,
            "3. a listed SKU no open run holds has its saved strip too, so the Live tab draws it with no press",
            f"saved={sorted(saved)}",
        )


def check_one_refresh_across_processes(checks: Checks) -> None:
    """Review defect 4. One refresh at a time across processes; a second caller makes no fetch and
    says so; step notes are never lost."""
    checks.note("")
    checks.note("PRICES REFRESH — one at a time, across processes")
    with world(checks) as w:
        asked, undo = refuse_history()
        w.stub["gate"] = threading.Event()  # the first caller sits at the live download
        first = threading.Thread(target=lambda: attempt(checks, "4. the first refresh runs", pipeline_routes.do_prices_refresh), daemon=True)
        try:
            first.start()
            w.stub["reached"].wait(20)
            before = len(w.stub["requests"])
            program = (
                "import json, sys; sys.path.insert(0, %r)\n"
                "from server import pipeline_routes as r\n"
                "try:\n"
                "    print(json.dumps({'answer': r.do_prices_refresh()}, default=str))\n"
                "except Exception as caught:\n"
                "    print(json.dumps({'raised': str(caught), 'code': getattr(caught, 'code', '')}))\n"
            ) % str(Path(__file__).resolve().parents[3])
            try:
                ran = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, timeout=15, env=dict(os.environ), cwd=str(Path(__file__).resolve().parents[3]))
                said = ran.stdout.strip().splitlines()[-1] if ran.stdout.strip() else ""
                stderr = ran.stderr[-200:]
            except subprocess.TimeoutExpired:
                said, stderr = "", "the second process was still refreshing after 15 s: it did not give way"
            checks.ok(
                "running" in said.lower() or "already" in said.lower(),
                "4. a second process answers that a refresh is already running",
                f"stdout={said[:300]!r} stderr={stderr!r}",
            )
            checks.equal(len(w.stub["requests"]), before, "4. and the second process fetched nothing")
        finally:
            w.stub["gate"].set()
            first.join(60)
            undo()
        steps = (pricerefresh.read_status() or {}).get("steps") or {}
        checks.ok(
            all((steps.get(name) or {}).get("ok") for name in ("listings", "catalog", "join")),
            "4. the first refresh's step notes are all there, none lost to the second caller",
            json.dumps(steps)[:300],
        )

    with isolated_home():
        names = [f"s{at}" for at in range(120)]

        def write(part):
            for name in part:
                # a writer that lost the race to the shared temp file is one more lost note
                with contextlib.suppress(OSError):
                    pricerefresh.note_step(name, True)

        halves = [threading.Thread(target=write, args=(names[at::2],)) for at in (0, 1)]
        for thread in halves:
            thread.start()
        for thread in halves:
            thread.join()
        kept = ((pricerefresh.read_status() or {}).get("steps") or {})
        checks.equal(len(kept), len(names), "4. two writers of step notes lose none of them")


# ------------------------------------------------------------ the PR #749 re-review defects


def _wait_idle(port, seconds=60):
    deadline = time.time() + seconds
    ended = {}
    while time.time() < deadline:
        state, body, _ = request(port, "GET", "/pipeline/prices/refresh")
        ended = json.loads(body or b"{}") if state == 200 else {}
        if ended.get("state") not in ("running", "starting"):
            break
        time.sleep(0.1)
    return ended


def check_held_lock_is_a_recorded_skip(checks: Checks) -> None:
    """Re-review defect 1. While another process holds the refresh lock, the Live press and Refresh now
    end in a recorded "skipped: another refresh is running" state, and never read as a finished run."""
    checks.note("")
    checks.note("PRICES REFRESH — the lock is held by another process")
    with world(checks) as w:
        asked, undo = refuse_history()
        try:
            attempt(checks, "a first refresh runs, so a previous run's file exists", pipeline_routes.do_prices_refresh)
        finally:
            undo()
        for press, path, payload in (
            ("the Live press", "/pipeline/live-export", {}),
            ("Refresh now", "/pipeline/prices/refresh", {"force": True}),
        ):
            before = len(w.stub["requests"])
            with pricerefresh.refresh_lock() as held:  # another process holds it, as far as this call can tell
                checks.ok(held, f"{press}: the probe holds the lock")
                status, _raw, _ = request(w.port, "POST", path, payload=payload)
                ended = _wait_idle(w.port)
            noted = json.dumps(pricerefresh.read_status() or {})
            checks.ok(status in (200, 202, 409), f"{press}: the press is answered", str(status))
            checks.ok(
                "another refresh is running" in noted and "skipped" in noted.lower(),
                f"{press}: a held lock is recorded as `skipped: another refresh is running`",
                noted[:300],
            )
            checks.ok(
                ended.get("state") not in ("done", "running"),
                f"{press}: the state is not `done`, so the screen never takes the previous run's file as fresh",
                json.dumps({k: ended.get(k) for k in ("state", "step")}),
            )
            checks.equal(len(w.stub["requests"]), before, f"{press}: and it fetched nothing")
            checks.ok(
                ((ended.get("note") or {}).get("steps") or {}).get("listings", {}).get("fetched") in (None, "")
                or "skipped" in noted.lower(),
                f"{press}: no listings file is offered as this press's own",
            )


def check_single_game_wrong_rows_keep_no_file(checks: Checks) -> None:
    """Re-review defect 2. `partial` is for a run that holds more than one game. A single-game run whose
    portal answers another game's rows (Product Line "Magic") keeps no file, and says so."""
    checks.note("")
    checks.note("PRICES REFRESH — a single-game run, the portal answers another game")
    with world(checks) as w:
        source = tcgcsv.read_export(write_export(w.home / "magic.csv", market={DUNSPARCE_SKU: NOW}))
        rows = [dict(row, **{"Product Line": "Magic"}) for row in source.rows]
        wrong = w.home / "magic-out.csv"
        tcgcsv.write_csv(wrong, source.header, rows)
        w.stub["body"] = wrong.read_bytes()
        before = (w.runs[0].directory / "pricing.json").read_bytes()
        asked, undo = refuse_history()
        try:
            attempt(checks, "the refresh does not raise over wrong rows", pipeline_routes.do_prices_refresh)
        finally:
            undo()
        kept = sorted((w.home / "inventory" / files.EXPORTS_DIRNAME / "pokemon").glob("*.csv"))
        checks.equal([p.name for p in kept], [], "a single-game run keeps no file of another game's rows")
        catalog = ((pricerefresh.read_status() or {}).get("steps") or {}).get("catalog") or {}
        checks.ok(
            catalog.get("ok") is False and ("Magic" in str(catalog.get("message")) or "carries" in str(catalog.get("message"))),
            "and the catalog step says so, naming what came back",
            json.dumps(catalog)[:300],
        )
        checks.equal((w.runs[0].directory / "pricing.json").read_bytes() == before, True, "and no run table moved")


def check_refresh_reaches_store_backed_runs(checks: Checks) -> None:
    """A store-backed run (`selection.keys`, a cards map, NO `identifications.json`) is scoped and
    priced like any other: refresh, the scope preview and the export press count its cards from
    the store. Red on main: `_scope_counts` reads the file itself and refuses `export_refused`,
    "Nothing has been identified for this run yet". Caller chain: `do_prices_refresh` ->
    `_run_games` (swallows it) -> `_game_catalog` -> `do_pipeline_export` -> `_scope_for_run` ->
    `_scope_counts`. `_record_written`, the other direct file check, only gates a child's liveness
    (`_live_pid`) and a store-backed run has no child, so it needs no case."""
    from harness.tests.t7.send_markdown import _store_backed_run

    checks.note("")
    checks.note("PRICES REFRESH — an open store-backed run")
    with world(checks) as w:
        run = _store_backed_run(checks, w.home, [(5, 1, "Dunsparce", "120/159", "normal")])
        from store.session import Store
        with Store().write() as snapshot:  # a Pokemon run names its sets (D170), as `world()` does
            for key in run.manifest["selection"]["keys"]:
                snapshot.inventory.cards[key].set_hint = "SV09"
        checks.equal(
            (run.manifest.get("selection") or {}).get("keys") and not (run.directory / "identifications.json").exists(),
            True, "fixture: the run has selection.keys and no identifications.json",
        )

        # 2. the scope preview and the export press
        try:
            scope = pipeline_routes.do_pipeline_scope(run.name, {})
            counted = [g["cards"] for g in scope["games"]]
            seen = f"counted {counted}"
        except pipeline_routes.PipelineRefusal as refused:
            counted, seen = None, f"refused {refused.code}: {refused}"
        checks.equal(counted, [1], "2. GET scope counts the store-backed run's 1 card from the store: " + seen)
        try:
            pipeline_routes.do_pipeline_export(run.name, {"scope": "category"})
            pressed = "ok"
        except pipeline_routes.PipelineRefusal as refused:
            pressed = f"refused {refused.code}: {refused}"
        checks.equal(pressed, "ok", "2. the export press for the store-backed run does not refuse")

        # 1. the refresh
        asked, undo = refuse_history()
        try:
            answer = attempt(checks, "1. the refresh runs over a store-backed run", lambda: pipeline_routes.do_prices_refresh())
        finally:
            undo()
        catalog = ((pricerefresh.read_status() or {}).get("steps") or {}).get("catalog") or {}
        checks.equal((answer or {}).get("ok"), True, "1. the refresh reaches done: " + json.dumps(catalog)[:200])
        checks.equal(
            table_row(run, DUNSPARCE_SKU)["snap"].get("market"), NOW,
            "1. the store-backed run's card is priced at the new Market, like any other run's",
        )


def check_trends_facts_need_no_month_series(checks: Checks) -> None:
    """A SKU the `month` range does not list is a read, not a `KeyError` (the second cause).

    The endpoint leaves a SKU out of a range it has no sales in, so `Reading.series` can hold
    `annual` alone. `_trends_for_entries` then indexes `series[DEFAULT_RANGES[0]]` with no
    guard. The facts raise, `files.log_cause` writes `trends facts: KeyError: 'month'`, and the
    SKU loses its facts. Real history holds such SKUs, so this fires with no 403 at all.

    THE WIRE SHAPE IS REAL: `month` answers `result: null`, which `parse_history` reads as
    "no history" and not as an error, and `annual` lists the SKU. The catalog hops are seeded
    into the cache, as `check_history_blocked_route` does. The history hops are not, and
    `urllib.request.urlopen` answers them in-process, so `fetch_json` runs for real.
    """
    checks.note("")
    checks.note("MONTH MISSING, ANNUAL PRESENT — the facts read, with no `KeyError`")
    sku = "9189317"
    row = next(r for r in tcgcsv.read_export(RIFTBOUND_EXPORT).rows if r.get(tcgcsv.SKU_COLUMN) == sku)
    annual = {
        "count": 1,
        "result": [{
            "skuId": sku, "variant": "Foil", "condition": "Near Mint Foil", "language": "English",
            "totalQuantitySold": "5", "totalTransactionCount": "5",
            "buckets": [
                {"bucketStartDate": "2026-08-03", "marketPrice": "23.14", "quantitySold": "5",
                 "transactionCount": "5", "lowSalePrice": "22.00", "highSalePrice": "24.00"},
                {"bucketStartDate": "2026-08-10", "marketPrice": "23.50", "quantitySold": "1",
                 "transactionCount": "1", "lowSalePrice": "23.50", "highSalePrice": "23.50"},
            ],
        }],
    }

    def history_urlopen(request, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        url = request.full_url
        if "infinite-api" not in url:
            # An unseeded catalog hop. Refused without a socket, so a miss reads as a miss.
            raise urllib.error.URLError(f"harness: no socket for {url}")
        payload = {"count": 0, "result": None} if "range=month" in url else annual
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    with isolated_home():
        directory = pipeline_routes.market_cache_dir()
        at = time.time()
        catalog = (REPO_ROOT / "fixtures" / "tcgcsv_riftbound_unleashed_products.json").read_text("utf-8")
        for slug, payload in (
            ("tcgcsv/categories", {"results": [{"categoryId": 89,
                                                "name": "Riftbound League of Legends Trading Card Game"}]}),
            ("tcgcsv/89/groups", {"results": [{"groupId": 24560, "name": "Unleashed"}]}),
            ("tcgcsv/89/24560/products", json.loads(catalog)),
        ):
            path = directory / f"{slug}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched_at": at, "payload": payload}), "utf-8")

        causes: list = []
        real_urlopen = urllib.request.urlopen
        urllib.request.urlopen = history_urlopen
        try:
            with mock.patch.object(files, "log_cause", lambda what, exc: causes.append((what, exc))):
                answer = pipeline_routes._trends_for_entries(
                    {sku: {"row": row, "name": "Vilemaw"}}, [sku], {},
                    missing="{sku} is not in this run", skip_at_cap=False,
                )
        finally:
            urllib.request.urlopen = real_urlopen
        saved = pricerefresh.read_trends().get(sku) or {}

    failures = [repr(exc) for what, exc in causes if what == "trends facts"]
    checks.equal(
        failures, [],
        "a SKU with no month series is read, and its facts raise nothing: no 'trends facts' failure is logged",
    )
    strip = ((answer.get("skus") or {}).get(sku) or {}).get("ranges") or []
    checks.equal(
        [entry.get("range") for entry in strip], ["annual"],
        "...and its annual strip is still returned",
    )
    checks.ok(
        "facts" not in saved,
        "...and the saved entry carries NO facts for a SKU the month range does not list",
        repr(sorted(saved)),
    )


# ------------------------------------------------------- the send gate (`refresh_before_send`)
#
# A send never prices from an export older than today (US Central). These cases go through the two
# real doors, `send_routes.do_send` (the runs sheet, `#/pricing`) and `cli/cmd_emit.run` (the CLI),
# against `send_markdown.send_portal`, which serves the live read, the catalog export and the pricing
# upload. On `main` there is no gate, so each case is red by its own sentence. `_refresh_spy` says
# whether a refresh was asked and what receipts existed when it was.

PUSH_CALLS = ("initializeexportcsv", "uploadexportcsv", "finalizeexportcsv", "movetolive")
DAY = 86400


def _outcome(fn):
    """What `fn` did: `("answer", value)`, `("refused", code, message)`, or `("raised", text)`."""
    try:
        return ("answer", fn())
    except pipeline_routes.PipelineRefusal as caught:
        return ("refused", caught.code, str(caught))
    except Exception as caught:  # noqa: BLE001 - a missing function reads as a failed case, not a crash
        return ("raised", f"{type(caught).__name__}: {caught}")


def _refused(outcome) -> tuple:
    """`(code, message)` when `outcome` refused, else `(None, "")`."""
    return (outcome[1], outcome[2]) if outcome[0] == "refused" else (None, "")


def _send_now(run):
    return _outcome(lambda: send_routes.do_send({"runs": [run.directory.name], "confirm": True}))


def _receipt_dirs() -> list:
    root = send_routes.sends_dir()
    return sorted(path.name for path in root.iterdir()) if root.is_dir() else []


@contextmanager
def _refresh_spy():
    """Each call to `pipeline_routes.do_prices_refresh`: the receipts that existed then, and its answer.

    It forwards every argument, because main's refresh takes no `also`. `refresh_before_send` reads
    the function as a module global, so one patch covers `do_send` and `cli/cmd_emit`."""
    real = pipeline_routes.do_prices_refresh
    calls = []

    def spy(*args, **kwargs):
        call = {"receipts": _receipt_dirs(), "answer": None}
        calls.append(call)
        call["answer"] = real(*args, **kwargs)
        return call["answer"]

    pipeline_routes.do_prices_refresh = spy
    try:
        yield calls
    finally:
        pipeline_routes.do_prices_refresh = real


def _age(path, days: int) -> int:
    """Set `path`'s mtime `days` back, to a whole second. Returns that stamp."""
    stamp = int(time.time()) - days * DAY
    os.utime(path, (stamp, stamp))
    return stamp


def _name_sets(run, set_id: str = "SV09") -> None:
    """A Pokemon run names its set (D170), as `world` does. Without one, a refresh cannot fetch it."""
    path = run.directory / pipeline_routes.run_files.IDENTIFICATIONS
    payload = json.loads(path.read_text())
    for card in payload["cards"].values():
        card["set_hint"] = set_id
    path.write_text(json.dumps(payload))


def _stale_run(checks: Checks, portal: dict, home: Path, cards):
    """A joined Pokemon run priced at `THEN`, its export two days old. The portal's catalog says `NOW`."""
    run, _ = seam_run(checks, cards, market={DUNSPARCE_SKU: THEN, ARTICUNO_SKU: ARTICUNO_THEN})
    _name_sets(run)
    _age(run.directory / "export.csv", 2)
    portal["catalog"] = write_export(home / "catalog-now.csv", market={DUNSPARCE_SKU: NOW, ARTICUNO_SKU: ARTICUNO_NOW}).read_bytes()
    return run


def _waiting_run(checks: Checks, cards):
    """A run read and collected but not joined: phase `join` (`_phase`), the mark `cmd_match` writes."""
    run, _ = seam_run(checks, cards, join=False)
    run.set(collected=True)
    return run


def _pushed(portal) -> list:
    """The pricing-upload calls the portal received. Empty when no upload reached TCGplayer."""
    return [name for kind, name in portal["calls"] if kind == "POST" and name in PUSH_CALLS]


def _uploaded(portal) -> dict:
    """`{TCGplayer Id: MyPrice}` for every row the portal kept."""
    return {row["ProductConditionId"]: row["MyPrice"] for row in portal["rows"]}


def check_send_refreshes_a_stale_export_first(checks: Checks) -> None:
    """Case 1. An export from an earlier day is refreshed before the send, and the send carries the new price.

    The refresh runs before any receipt exists. The pricing upload carries $16.25, not $10.37.
    """
    checks.note("")
    checks.note("SEND GATE — an export from an earlier day is refreshed before the send")
    with send_portal() as portal, synced_home() as home:
        run = _stale_run(checks, portal, home, [(3, 1, "Dunsparce", "120/159", "normal")])
        with _refresh_spy() as calls:
            outcome = _send_now(run)
        checks.equal(len(calls), 1, "1. a stale export makes the send run the refresh once")
        checks.equal(
            calls[0]["receipts"] if calls else None, [],
            "1. and no receipt exists when the refresh runs: the gate sits before the receipt",
        )
        checks.ok(outcome[0] == "answer", "1. the send goes after the refresh", repr(outcome[1:])[:300])
        checks.equal(attempt(checks, "1. the run's table", lambda: table_row(run, DUNSPARCE_SKU)["snap"].get("market")), NOW,
                     "1. the run's own table carries the refreshed Market")
        checks.equal(_uploaded(portal).get(DUNSPARCE_SKU), NOW,
                     "1. the pricing upload sends $16.25, not the stale $10.37")


def check_refused_refresh_sends_nothing(checks: Checks) -> None:
    """Case 2. A refresh that cannot bring the prices current refuses the send, names the cause, and sends nothing."""
    checks.note("")
    checks.note("SEND GATE — a refresh that cannot run refuses the send, with its cause, and sends nothing")
    with send_portal() as portal, synced_home() as home:
        run = _stale_run(checks, portal, home, [(3, 1, "Dunsparce", "120/159", "normal")])
        saved = os.environ.pop("TCGPLAYER_STORE_COOKIE", None)
        try:
            with _refresh_spy() as calls:
                outcome = _send_now(run)
        finally:
            if saved is not None:
                os.environ["TCGPLAYER_STORE_COOKIE"] = saved
        code, text = _refused(outcome)
        checks.equal(code, "prices_stale", "2a. with no cookie the refresh cannot run: the send refuses with `prices_stale`")
        checks.ok(text.startswith("Nothing was sent"), "2a. the refusal opens `Nothing was sent`", text[:300])
        checks.equal(len(calls), 1, "2a. the refresh was asked once")
        checks.equal(_pushed(portal), [], "2a. and no pricing upload reached TCGplayer")
        checks.equal(_receipt_dirs(), [], "2a. and no receipt was written")

        with pricerefresh.refresh_lock() as held:
            checks.ok(held, "2b. the probe holds the refresh lock, as another process would")
            with _refresh_spy() as calls:
                outcome = _send_now(run)
        code, text = _refused(outcome)
        checks.equal(code, "prices_stale", "2b. another refresh running: the send refuses with `prices_stale`")
        checks.ok(
            text.startswith("Nothing was sent") and "another refresh is running" in text,
            "2b. the refusal opens `Nothing was sent` and names the running refresh", text[:300],
        )
        checks.equal(_pushed(portal), [], "2b. and no pricing upload reached TCGplayer")
        checks.equal(_receipt_dirs(), [], "2b. and no receipt was written")


def check_same_day_export_asks_no_refresh(checks: Checks) -> None:
    """Case 3. An export from today asks no refresh, and the send goes as before."""
    checks.note("")
    checks.note("SEND GATE — a same-day export is sent without a refresh")
    with send_portal(), synced_home():
        run, _ = seam_run(checks, [(3, 1, "Dunsparce", "120/159", "normal")], market={DUNSPARCE_SKU: THEN})
        _name_sets(run)
        with _refresh_spy() as calls:
            outcome = _send_now(run)
        checks.equal(len(calls), 0, "3. an export from today asks no refresh")
        checks.ok(outcome[0] == "answer", "3. and the send goes", repr(outcome[1:])[:300])


def check_waiting_run_is_joined_and_send_stays_narrow(checks: Checks) -> None:
    """Case 4. The refresh joins a run waiting at phase join, and a run that cannot join is named and does not block the send.

    The pressed run holds Dunsparce. A waiting run holds Articuno and joins. A second waiting run has
    no set hint, so its join fails. The pressed send must carry Dunsparce alone.
    """
    checks.note("")
    checks.note("SEND GATE — a waiting run is joined by the refresh, a failed join is named, the send is not widened")
    with send_portal() as portal, synced_home() as home:
        pressed = _stale_run(checks, portal, home, [(3, 1, "Dunsparce", "120/159", "normal")])
        waiting = _waiting_run(checks, [(4, 1, "Articuno", "161", None)])
        _name_sets(waiting)
        broken = _waiting_run(checks, [(5, 1, "Articuno", "161", None)])
        with _refresh_spy() as calls:
            outcome = _send_now(pressed)
        checks.equal(len(calls), 1, "4. the refresh runs once, for the stale pressed run")
        worklist = attempt(checks, "4. `do_pipeline_worklist` answers", lambda: pipeline_routes.do_pipeline_worklist([]))
        row = row_of(ARTICUNO_SKU, worklist) if worklist else None
        checks.ok(row is not None, "4. the waiting run is joined by the refresh and lands on the worklist",
                  json.dumps([r.get("sku") for r in (worklist or {}).get("skus", [])])[:300])
        steps = (calls[0]["answer"] or {}).get("steps") or {} if calls else {}
        join_said = (steps.get("join") or {}).get("message") or ""
        checks.ok(broken.directory.name in join_said, "4. the run that cannot join is named by the refresh's join step",
                  repr(steps.get("join"))[:300])
        checks.ok(outcome[0] == "answer", "4. a failed join does not block the send", repr(outcome[1:])[:300])
        checks.equal(set(_uploaded(portal)), {DUNSPARCE_SKU},
                     "4. the pressed send is not widened: only its own SKU is uploaded")


def check_readings_keep_the_newest_reading(checks: Checks) -> None:
    """Case 5a. `replace_source` keeps the row dated later. A tie takes the new reading."""
    checks.note("")
    checks.note("READINGS — a newer reading is kept over an older one, from any source")
    with isolated_home():

        def put(source: str, price: str, at: int) -> None:
            with Store().write() as writable:
                writable.readings.replace_source(
                    KIND_RUN, source, {"501": Reading(price, at, source, KIND_RUN, "Card")},
                    Source(KIND_RUN, source, at, 1),
                )

        def held() -> str:
            return Store().read().readings.entries["501"].market

        attempt(checks, "5a. run-a is written", lambda: put("run-a", "12.00", 2000))
        attempt(checks, "5a. run-b, an older reading from another source, is written", lambda: put("run-b", "9.00", 1000))
        checks.equal(attempt(checks, "5a. the table is read", held), "12.00",
                     "5a. an older reading from another source does not replace a newer row")
        attempt(checks, "5a. run-a re-joins with an older reading", lambda: put("run-a", "8.00", 1500))
        checks.equal(attempt(checks, "5a. the table is read", held), "12.00",
                     "5a. nor does an older re-join of the same source replace its own newer row")
        checks.equal(
            attempt(checks, "5a. the source row is read", lambda: Store().read().readings.sources[_source_key(KIND_RUN, "run-a")]),
            Source(KIND_RUN, "run-a", 2000, 1),
            "5a. and its source row still says 2000: an older re-join of the same run changes no source row",
        )
        attempt(checks, "5a. run-b writes a tie", lambda: put("run-b", "7.00", 2000))
        checks.equal(attempt(checks, "5a. the table is read", held), "7.00",
                     "5a. a tie replaces: the new reading takes the row")


def check_join_dates_pricing_to_its_export(checks: Checks) -> None:
    """Case 5b. `join` stamps pricing.json with the export's own time, and `readings adopt` recomputes the same `at`."""
    checks.note("")
    checks.note("READINGS — a join is dated to the export it priced from, never to now")
    with isolated_home():
        run, _ = seam_run(checks, [(3, 1, "Dunsparce", "120/159", "normal")], market={DUNSPARCE_SKU: THEN}, join=False)
        export = run.directory / "export.csv"
        stamp = _age(export, 2)
        command(checks, "join", str(run.directory), "--export", str(export))
        pricing = run.directory / pipeline_routes.run_files.PRICING
        checks.equal(int(pricing.stat().st_mtime), stamp, "5b. `join` dates pricing.json to the export it joined, not to now")

        def reading_at() -> int:
            return Store().read().readings.entries[DUNSPARCE_SKU].at

        checks.equal(attempt(checks, "5b. the reading is read", reading_at), stamp,
                     "5b. the reading carries that same time")
        command(checks, "readings", "adopt", "--write")
        checks.equal(attempt(checks, "5b. the reading is read again", reading_at), stamp,
                     "5b. `readings adopt` recomputes the same `at`")


def check_cli_emit_is_gated(checks: Checks) -> None:
    """Case 6. `emit` with a stale `--export` is refused, and a multi-run emit is gated by the same refresh."""
    checks.note("")
    checks.note("SEND GATE — the CLI `emit` is refused on stale prices, one run or several")
    with send_portal() as portal, synced_home() as home:
        run, _ = seam_run(checks, [(3, 1, "Dunsparce", "120/159", "normal")], market={DUNSPARCE_SKU: THEN})
        stale = write_export(home / "stale-export.csv", market={DUNSPARCE_SKU: THEN})
        _age(stale, 2)
        with _refresh_spy() as calls:
            text = command(checks, "emit", str(run.directory), "--export", str(stale), exits=1)
        checks.ok("Nothing was sent" in text, "6a. a stale `--export` is refused with `Nothing was sent`", text[-300:])
        checks.equal(len(calls), 0, "6a. a named file is the owner's choice, so it is refused without a refresh")
        checks.equal(sorted(run.directory.glob("import*.csv")), [], "6a. and no import file was written")

        second, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)], market={ARTICUNO_SKU: ARTICUNO_THEN})
        _age(run.directory / "export.csv", 2)
        _age(second.directory / "export.csv", 2)
        with pricerefresh.refresh_lock() as held:
            checks.ok(held, "6b. the probe holds the refresh lock, as another process would")
            with _refresh_spy() as calls:
                text = command(checks, "emit", str(run.directory), str(second.directory), exits=1)
        checks.ok(
            "Nothing was sent" in text and "another refresh is running" in text,
            "6b. a multi-run emit over stale runs is refused with the running refresh named", text[-300:],
        )
        checks.equal(len(calls), 1, "6b. a multi-run emit asks the refresh once")


# ------------------------------------------------------------------ round 2: the day, the problem, the receipt


def _central(*parts) -> datetime:
    return datetime(*parts, tzinfo=ZoneInfo("America/Chicago"))


def check_standing_problem_is_not_refetched(checks: Checks) -> None:
    """Round 2, item 1. A waiting run whose last join left a problem is not fetched again by the refresh.

    `do_run_match` answers `problem_stands` before it fetches anything. The refresh names the standing
    sentence in its join step, and the run's own problem record is left as it was. The spy records every
    export the refresh asks for, by run name.
    """
    checks.note("")
    checks.note("SEND GATE — a waiting run with a standing join problem is named, not fetched again")
    problem = "Pokemon run needs its sets named before it can be matched."
    with send_portal() as portal, synced_home() as home:
        pressed = _stale_run(checks, portal, home, [(3, 1, "Dunsparce", "120/159", "normal")])
        stuck = _waiting_run(checks, [(4, 1, "Articuno", "161", None)])
        attempt(
            checks, "1. the waiting run carries a standing join problem",
            lambda: pipeline_routes._write_match(
                stuck.directory,
                {"at": datetime.now(timezone.utc).isoformat(), "problem": {"code": "match_refused", "message": problem, "step": "join"}},
            ),
        )
        fetched = []
        real_export = pipeline_routes.do_pipeline_export

        def spy_export(*args, **kwargs):
            fetched.append(args[0] if args else kwargs.get("name"))
            return real_export(*args, **kwargs)

        with _refresh_spy() as calls:
            pipeline_routes.do_pipeline_export = spy_export
            try:
                outcome = _send_now(pressed)
            finally:
                pipeline_routes.do_pipeline_export = real_export
        steps = ((calls[0]["answer"] or {}).get("steps") or {}) if calls else {}
        join_said = (steps.get("join") or {}).get("message") or ""
        checks.equal(
            [name for name in fetched if name == stuck.directory.name], [],
            "1. the refresh asks TCGplayer for nothing for the run with a standing problem",
        )
        checks.ok(
            stuck.directory.name in join_said and problem in join_said,
            "1. the refresh's join step names that run and its standing sentence",
            repr(steps.get("join"))[:300],
        )
        checks.ok(outcome[0] == "answer", "1. and the send of the pressed run still goes", repr(outcome[1:])[:300])
        still = attempt(checks, "1. the run's problem record is read back", lambda: pipeline_routes._read_match(stuck.directory))
        checks.equal(
            ((still or {}).get("problem") or {}).get("message"), problem,
            "1. and the standing problem is unchanged: the refresh wrote nothing to the run",
        )


def check_a_read_is_from_today_central(checks: Checks) -> None:
    """Round 2, item 2. A read is fresh when it began on today's US Central day. `fresh_for_s` counts real seconds.

    Fixed instants either side of midnight, and on both 2026 daylight-saving shifts: 8 March (a 23 hour
    day) and 1 November (a 25 hour day). A rule that counts 24 hours gets each of these wrong.
    """
    checks.note("")
    checks.note("READ FRESHNESS — a read is fresh from the Central day it began on, and `fresh_for_s` counts real seconds")

    def fresh(read: datetime, now: datetime) -> bool:
        return reprice.read_is_fresh(read.isoformat(), now)

    checks.equal(
        [
            fresh(_central(2026, 9, 26, 0, 0), _central(2026, 9, 26, 23, 59)),
            fresh(_central(2026, 9, 25, 23, 59, 59), _central(2026, 9, 26, 0, 0, 1)),
            fresh(_central(2026, 9, 25, 23, 59, 59), _central(2026, 9, 26, 23, 59)),
            fresh(_central(2026, 3, 7, 23, 59, 59), _central(2026, 3, 8, 0, 0, 1)),
            fresh(_central(2026, 3, 8, 0, 0), _central(2026, 3, 8, 23, 59, 59)),
            fresh(_central(2026, 3, 8, 0, 0), _central(2026, 3, 9, 0, 0)),
            fresh(_central(2026, 10, 31, 23, 59, 59), _central(2026, 11, 1, 0, 0)),
            fresh(_central(2026, 11, 1, 0, 0), _central(2026, 11, 1, 23, 59, 59)),
            fresh(_central(2026, 11, 1, 0, 0), _central(2026, 11, 2, 0, 0)),
        ],
        [True, False, False, False, True, False, False, True, False],
        "A READ IS FRESH FROM THE CENTRAL DAY IT BEGAN ON: midnight, a second either side, and both DST shifts",
    )
    checks.equal(
        [
            attempt(checks, "2. `fresh_for_s` at noon, 8 March", lambda: reprice.fresh_for_s(_central(2026, 3, 8, 12, 0))),
            attempt(checks, "2. `fresh_for_s` at 23:59:59, 8 March", lambda: reprice.fresh_for_s(_central(2026, 3, 8, 23, 59, 59))),
            attempt(checks, "2. `fresh_for_s` at noon, 1 November", lambda: reprice.fresh_for_s(_central(2026, 11, 1, 12, 0))),
            attempt(checks, "2. `fresh_for_s` at 23:59:59, 1 November", lambda: reprice.fresh_for_s(_central(2026, 11, 1, 23, 59, 59))),
        ],
        [39600, 82799, 46800, 89999],
        "2. `fresh_for_s` counts real seconds: a 23 hour day ends at 82799 and a 25 hour day at 89999",
    )


def check_markdown_send_refuses_an_earlier_day(checks: Checks) -> None:
    """Round 2, item 2. A mark-down from yesterday's read is refused `read_stale`. A mark-down from today's read goes."""
    checks.note("")
    checks.note("MARK-DOWN — a read from an earlier Central day is refused, a read from today goes")
    central_now = datetime.now(ZoneInfo("America/Chicago"))
    yesterday = (central_now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    with send_portal() as portal, synced_home() as home:
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})
        old = _markdown_dir(home, "20261021-120000", at=yesterday.isoformat())
        outcome = _outcome(lambda: send_routes.do_markdown_send(old.name, {"confirm": True}))
        code, _text = _refused(outcome)
        checks.equal(code, "read_stale", "2. a mark-down from yesterday's read is refused `read_stale`")
        checks.equal(_pushed(portal), [], "2. and nothing reached TCGplayer's upload")
        today = _markdown_dir(home, "20261022-120000", at=datetime.now(timezone.utc).isoformat())
        outcome = _outcome(lambda: send_routes.do_markdown_send(today.name, {"confirm": True}))
        checks.ok(outcome[0] == "answer", "2. a mark-down from today's read goes", repr(outcome[1:])[:300])


def check_send_says_whether_it_refreshed(checks: Checks) -> None:
    """Round 2, item 3. The send's answer, its receipt and the summary carry `refresh`. The CLI prints the refresh line."""
    checks.note("")
    checks.note("SEND RECEIPT — a send says whether its prices were refreshed, and from which day")
    central = ZoneInfo("America/Chicago")
    with send_portal() as portal, synced_home() as home:
        stale = _stale_run(checks, portal, home, [(3, 1, "Dunsparce", "120/159", "normal")])
        was = datetime.fromtimestamp((stale.directory / "export.csv").stat().st_mtime, central).date().isoformat()
        today = datetime.now(central).date().isoformat()
        expected = {"ran": True, "ok": True, "was": was, "export_day": today}
        outcome = _send_now(stale)
        send = outcome[1].get("send") or {} if outcome[0] == "answer" else {}
        checks.equal(send.get("refresh"), expected,
                     "3. a stale export: the answer's summary says it ran, from `was`, and now `export_day`")
        receipts = attempt(checks, "3. the receipts are read", send_routes._receipts) or []
        checks.equal([record.get("refresh") for _, record in receipts], [expected],
                     "3. and the receipt on disk carries the same refresh")

        same, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)], market={ARTICUNO_SKU: ARTICUNO_THEN})
        _name_sets(same)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        outcome = _send_now(same)
        send = outcome[1].get("send") or {} if outcome[0] == "answer" else {}
        checks.equal(send.get("refresh"), {"ran": False, "export_day": today},
                     "3. a same-day export: the summary says the refresh did not run")

        cli = _stale_run(checks, portal, home, [(6, 1, "Articuno", "161", None)])
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        cli_was = datetime.fromtimestamp((cli.directory / "export.csv").stat().st_mtime, central).date().isoformat()
        text = command(checks, "emit", str(cli.directory))
        checks.ok(
            f"refreshed before this send: export of {cli_was}, now {today}" in text,
            "3. the CLI prints the refresh line, from which day and to which", text[-300:],
        )


CHECKS = (
    check_refresh_reaches_store_backed_runs,
    check_held_lock_is_a_recorded_skip,
    check_single_game_wrong_rows_keep_no_file,
    check_live_press_returns_at_once,
    check_two_game_run_is_refreshed_for_both,
    check_live_rows_get_saved_strips,
    check_one_refresh_across_processes,
    check_refresh_rewrites_the_waiting_row,
    check_disjoint_scopes_share_one_request,
    check_join_is_idempotent,
    check_refresh_order_and_failure,
    check_reading_is_one_whole_row,
    check_daily_job_reaches_only_the_refresh,
    check_refresh_route,
    check_visit_asks_no_market_host,
    check_series_window,
    check_saved_file_and_routes,
    check_live_read_rejoins,
    check_trends_facts_need_no_month_series,
    check_send_refreshes_a_stale_export_first,
    check_refused_refresh_sends_nothing,
    check_same_day_export_asks_no_refresh,
    check_waiting_run_is_joined_and_send_stays_narrow,
    check_readings_keep_the_newest_reading,
    check_join_dates_pricing_to_its_export,
    check_cli_emit_is_gated,
    check_standing_problem_is_not_refetched,
    check_a_read_is_from_today_central,
    check_markdown_send_refuses_an_earlier_day,
    check_send_says_whether_it_refreshed,
)
