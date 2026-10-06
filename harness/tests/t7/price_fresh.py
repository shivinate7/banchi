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
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import envfile
from harness.tests import Checks
from harness.tests.t7.common import (
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    ARTICUNO_SKU,
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
from pipeline import pricehistory, pricerefresh, readings as readings_walk, tcgcsv
from server import capture_server, pipeline_routes
from store import files

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
    keys = ("PKMNSCAN_TCG_EXPORT_URL", "TCGPLAYER_STORE_COOKIE", "PKMNSCAN_TCG_USER_AGENT", envfile.FROM_FILE_ENV)
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
            os.environ["PKMNSCAN_TCG_EXPORT_URL"] = f"http://127.0.0.1:{portal.server_address[1]}/admin/pricing/downloadexportcsv"
            os.environ["TCGPLAYER_STORE_COOKIE"] = "TCGAuthTicket_Production=t7-not-a-real-session"
            os.environ.pop("PKMNSCAN_TCG_USER_AGENT", None)

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
)
