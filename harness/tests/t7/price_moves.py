"""T7 group: price moves since listing, and the daily market read's note (DEBT69).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import ast
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from harness.tests import Checks
from harness.tests.t7.common import isolated_home
from pipeline import movers, pricerefresh
from server import pipeline_routes
from store import files
from store.pricearchive import Bucket
from store.readings import KIND_LIVE, Reading, Source
from store.session import Store

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "price-refresh-daily.py"


def _bucket(sku: str, start: str, market: str, width: int, range_: str = "month") -> Bucket:
    return Bucket(sku, 1, range_, width, start, market, 1, 1, market, market, 0)


def check_price_movers(checks: Checks) -> None:
    """A listed SKU is a mover only when its market moved MORE than ten percent, and one with no
    earlier price is counted, never dropped and never guessed.

    THE EDGES ARE THE CASES: exactly ten percent is not a mover, a week bucket that ends before
    the listing day is not a baseline, and the finest bucket covering the day wins over a wider
    one. The route half asserts the whole read changes nothing in the store.
    """
    checks.note("")
    checks.note("PRICE MOVERS — more than ten percent since listing, unmeasured counted")

    day = date(2026, 9, 10)
    points = {
        "UP": [("2026-09-10", "10.00", 1)],
        "EDGE": [("2026-09-10", "10.00", 1)],
        "DOWN": [("2026-09-10", "10.00", 1), ("2026-09-07", "99.00", 7)],
        "OLD": [("2026-08-01", "10.00", 7)],
        "NONE": [],
    }
    now = {"UP": "11.40", "EDGE": "11.00", "DOWN": "8.80", "OLD": "30.00"}
    listed = {sku: day for sku in points}
    found, unmeasured = movers.movers(listed, now, lambda sku: points[sku])
    checks.equal([m.sku for m in found], ["UP", "DOWN"], "only UP (+14%) and DOWN (-12%) moved, exactly +10% did not")
    checks.equal(
        [(m.direction, str(m.change)) for m in found],
        [("up", "0.14"), ("down", "-0.12")],
        "direction and the signed amount are the computed fraction",
    )
    checks.equal(unmeasured, 2, "OLD (bucket ended before listing) and NONE (no bucket) are counted unmeasured")
    checks.equal(
        movers.baseline_at(points["DOWN"], day), Decimal("10.00"),
        "the one-day bucket beats the week bucket that also covers the day",
    )

    with isolated_home():
        with Store().write() as writable:
            entry = writable.inventory.listing("501")
            entry.first_seen_live = "2026-09-10T08:00:00+00:00"
            writable.archive.upsert({
                "501:month:2026-09-10": _bucket("501", "2026-09-10", "10.00", 1),
                "502:month:2026-09-10": _bucket("502", "2026-09-10", "10.00", 1),
            })
            reading = lambda sku, price: Reading(price, 1, "live-x.csv", KIND_LIVE, "Card " + sku)  # noqa: E731
            writable.readings.replace_source(
                KIND_LIVE, "live-x.csv", {"501": reading("501", "12.00"), "502": reading("502", "20.00")},
                Source(KIND_LIVE, "live-x.csv", 1, 2),
            )
        # 501 has a first-seen date; 503 is NEW in the export and has none (the daily read writes no
        # `Listing`); 502 has no copy live. Only 501 and 503 are subjects.
        real = pipeline_routes._newest_live_listing
        pipeline_routes._newest_live_listing = lambda: (
            "live-x.csv", {"501": ("12.00", 2), "502": ("20.00", 0), "503": ("5.00", 1)},
        )
        try:
            before = files.home() / "inventory" / "store.sqlite"
            stamp = before.stat().st_mtime_ns if before.exists() else None
            answer = pipeline_routes.do_pipeline_movers()
        finally:
            pipeline_routes._newest_live_listing = real
        checks.equal([r["sku"] for r in answer["movers"]], ["501"], "the route names the live SKU with a baseline")
        checks.equal(
            (answer["movers"][0]["direction"], answer["movers"][0]["then"], answer["movers"][0]["now"]),
            ("up", "10.00", "12.00"),
            "the route carries direction, then and now",
        )
        checks.equal(
            (answer["listed"], answer["unmeasured"]), (2, 1),
            "a newly live SKU with no first-seen date is counted unchecked, and one with no copy live is no subject",
        )
        checks.equal(answer["refresh"], None, "no scheduled read has run, so there is no note")
        checks.equal(
            before.stat().st_mtime_ns if before.exists() else None, stamp,
            "reading the movers wrote nothing to the store",
        )


def check_price_refresh_note(checks: Checks) -> None:
    """The scheduled read writes a note either way, and a failed one is on screen's route.

    THE WRITE IS THE POINT: a run that fails and leaves nothing behind is the silent stale state
    this lane exists to end. The script's own imports are asserted too: it may reach the one live
    fetch and the note writer and nothing that spends money or sweeps the archive.
    """
    checks.note("")
    checks.note("PRICE REFRESH NOTE — a failed run is visible, the job reaches nothing paid")

    saved = os.environ.pop("TCGPLAYER_STORE_COOKIE", None)
    try:
        with isolated_home():
            checks.equal(pricerefresh.read_status(), None, "before any run there is no note")
            good = pricerefresh.run(lambda: {"live_rows": 7}, now=1000)
            checks.equal(
                (good["ok"], good["live_rows"], pricerefresh.read_status()["at"]), (True, 7, 1000),
                "a good run writes an ok note with its row count",
            )
            bad = pricerefresh.run(pipeline_routes.do_live_export, now=2000)
            noted = pricerefresh.read_status() or {}
            checks.ok(
                bad["ok"] is False and noted.get("ok") is False and noted.get("at") == 2000
                and noted.get("code") and noted.get("message"),
                "a refused fetch (no session on this machine) writes a failed note with its code and sentence",
                str(noted),
            )
            answer = pipeline_routes.do_pipeline_movers()
            checks.equal(
                (answer["refresh"] or {}).get("ok"), False,
                "the movers route hands the failed note to the screen",
            )
    finally:
        if saved is not None:
            os.environ["TCGPLAYER_STORE_COOKIE"] = saved

    checks.equal(
        daily_path_reaches(SCRIPT.read_text()), (True, {"do_prices_refresh"}), FENCE_LABEL,
    )
    checks.equal(
        daily_path_reaches(SCRIPT.read_text().replace("pipeline_routes.do_prices_refresh", "pipeline_routes.do_pipeline_export")),
        (True, {"do_pipeline_export"}),
        "the callee check reads the callee: a swapped-in paid export is seen",
    )
    checks.equal(
        preload_calls(), PRELOAD_ALLOWED,
        "the overnight preload calls the worklist and the Trends press's own route and nothing else",
    )
    checks.equal(
        preload_calls(planted_helper_source()), PRELOAD_ALLOWED | {"do_pipeline_identify"},
        "a paid read reached through a helper one level down is seen",
    )


PRELOAD_ALLOWED = {"do_pipeline_worklist", "do_pipeline_trends"}


def preload_calls(source: str = ""):
    """Every `do_*` function and `module.attr` that `do_price_trends_preload` reaches, ONE LEVEL
    DEEP: a helper it calls is opened and its calls count too, so a paid read hidden behind a
    helper is seen. The allowed callees are not opened (they are the press's own route)."""
    tree = ast.parse(source or Path(pipeline_routes.__file__).read_text())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    modules = {
        (alias.asname or alias.name).split(".")[0]
        for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for alias in n.names
    }

    def callees(fn):
        found = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    found.add(f.id)
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in modules:
                    found.add(f.value.id + "." + f.attr)
        return found

    first = callees(funcs["do_price_trends_preload"])
    reached = set(first)
    for name in first:
        if name in funcs and name not in PRELOAD_ALLOWED:
            reached |= callees(funcs[name])
    return {n for n in reached if n.startswith("do_") or "." in n}


def planted_helper_source() -> str:
    """The route module with a helper added to the preload that reaches a paid read."""
    source = Path(pipeline_routes.__file__).read_text()
    source = source.replace(
        "def do_price_trends_preload() -> dict:",
        "def _planted():\n    return do_pipeline_identify({})\n\n\ndef do_price_trends_preload() -> dict:", 1,
    )
    return source.replace("    work = do_pipeline_worklist([])", "    _planted()\n    work = do_pipeline_worklist([])", 1)


FENCE_LABEL = (
    "the daily job calls `do_prices_refresh` (the live listings, the catalog, the join, the sales history) "
    "and reaches nothing else of `server/`, `cli/` or `identify/`: no paid read, no sweep"
)


def daily_path_reaches(source: str):
    """`(imports are exactly the note writer and the server module, the `pipeline_routes`
    attributes the script touches)`. A callee other than `do_live_export` changes the second."""
    tree = ast.parse(source)
    reached = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("pipeline", "server", "cli", "identify", "store"):
            reached.update("%s.%s" % (node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.update(a.name for a in node.names if a.name.split(".")[0] in ("cli", "identify", "pipeline", "server", "store"))
    touched = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "pipeline_routes"
    }
    return reached == {"pipeline.pricerefresh", "server.pipeline_routes"}, touched


def check_price_trends_preload(checks: Checks) -> None:
    """The overnight Trends read asks what the press asks, saves each strip with its date, prunes
    what left the worklist, survives a chunk that raises anything, and counts causes honestly.

    ONLY THE WORKLIST AND THE TRENDS ROUTE ARE STUBBED: the preload's own row choice (not
    `at_cap`), door choice (the last run holding the row), chunking, pruning and note are the code
    under test, so each of those is a red case below.
    """
    checks.note("")
    checks.note("TRENDS PRELOAD — the press's rows, door and pace; saved with a date; causes counted")

    rows = [{"sku": "S%02d" % i, "at_cap": False, "in": [{"run": "old"}, {"run": "new"}]} for i in range(10)]
    rows.append({"sku": "CAPPED", "at_cap": True, "in": [{"run": "new"}]})
    asked = []
    mode = {"raise_on": None, "worklist_fails": False}
    sales = [{"range": "month", "points": ["1"]}]

    def worklist(_wanted):
        if mode["worklist_fails"]:
            raise RuntimeError("worklist unreadable")
        return {"skus": rows}

    def trends(door, skus):
        asked.append((door, list(skus)))
        if mode["raise_on"] == len(asked):
            raise RuntimeError("connection reset")
        out, refused = {}, {}
        for s_ in skus:
            if s_ == "S03":
                refused[s_] = "the mirror refused the request"
            elif s_ == "S04":
                refused[s_] = "S04 " + pricerefresh.NO_PRODUCT_LINE + ", so there is no product"
            else:
                out[s_] = {"ranges": [] if s_ == "S05" else sales}
        return {"skus": out, "refused": refused}

    real = pipeline_routes.do_pipeline_worklist, pipeline_routes.do_pipeline_trends
    pipeline_routes.do_pipeline_worklist, pipeline_routes.do_pipeline_trends = worklist, trends
    try:
        with isolated_home():
            pricerefresh.save_strips({"GONE": sales}, at=5)
            note = pricerefresh.preload(pipeline_routes.do_price_trends_preload, now=1000)
            checks.equal(
                [(d, len(c)) for d, c in asked], [("new", 8), ("new", 2)],
                "rows are read through the last run that holds them, 8 at a time, and the at-cap row is never asked",
            )
            checks.ok("CAPPED" not in sum((c for _, c in asked), []), "the at-cap row is not read")
            checks.equal(
                (note["ok"], note["asked"], note["read"], note["no_history"], note["unreadable"]),
                (True, 10, 7, 2, 1),
                "the note splits asked into read, no history and unreadable, and they add up",
            )
            saved = pipeline_routes.do_pipeline_saved_trends()
            checks.equal(
                ("GONE" in saved["skus"], saved["skus"]["S00"]["at"], "S03" in saved["skus"], len(saved["skus"])),
                (False, 1000, False, 8),
                "a SKU off the worklist is pruned at save time, strips carry their read second, a refused SKU is not saved",
            )

            asked.clear()
            mode["raise_on"] = 2
            failed = pricerefresh.preload(pipeline_routes.do_price_trends_preload, now=2000)
            after = pipeline_routes.do_pipeline_saved_trends()
            checks.ok(
                failed["ok"] is False and failed["failed"] == 1 and "connection reset" in failed["message"]
                and failed["unreadable"] >= 2,
                "a chunk that raises ANY error is counted failed, its rows unreadable, and the walk goes on", str(failed),
            )
            checks.equal(
                (after["skus"]["S00"]["at"], after["skus"]["S09"]["at"]), (2000, 1000),
                "strips read before the failed chunk are saved, and the failed chunk's keep their old date",
            )

            mode["worklist_fails"] = True
            hard = pricerefresh.preload(pipeline_routes.do_price_trends_preload, now=3000)
            checks.ok(
                hard["ok"] is False and "worklist unreadable" in hard["message"]
                and len(pipeline_routes.do_pipeline_saved_trends()["skus"]) == len(after["skus"]),
                "a worklist that cannot be read fails the note and prunes nothing", str(hard),
            )
            pricerefresh.run(lambda: {"live_rows": 1}, now=4000)
            checks.equal(
                (pricerefresh.read_status() or {}).get("trends", {}).get("ok"), False,
                "the live read's note keeps the trends note beside it",
            )
    finally:
        pipeline_routes.do_pipeline_worklist, pipeline_routes.do_pipeline_trends = real



def check_trends_press_saves(checks: Checks) -> None:
    """The Trends press writes its strips through the same save, and a refused press read never
    replaces a good saved strip."""
    from types import SimpleNamespace

    from pipeline import pricehistory, tcgcsv

    checks.note("")
    checks.note("TRENDS PRESS SAVE — the press saves what it read; a refusal keeps the good strip")

    first_range = pricehistory.DEFAULT_RANGES[0]

    class Market:
        def __init__(self, **_kw):
            pass

        def readings_for_rows(self, rows, product_ids=None):
            out, refused = {}, {}
            for row in rows:
                sku = row[tcgcsv.SKU_COLUMN]
                if sku == "A":
                    out[sku] = SimpleNamespace(product_id=1, series={first_range: 1})
                else:
                    refused[sku] = "the mirror refused the request"
            return out, refused

    real = pricehistory.Market, pricehistory.catalogued_row, pipeline_routes._history_spark
    pricehistory.Market, pricehistory.catalogued_row = Market, lambda row: True
    pipeline_routes._history_spark = lambda series: {"range": first_range, "points": ["fresh"]}
    entries = {sku: {"name": sku, "row": {tcgcsv.SKU_COLUMN: sku}} for sku in ("A", "B")}
    try:
        with isolated_home():
            pricerefresh.save_strips({"B": [{"range": first_range, "points": ["good"]}]}, at=5)
            answer = pipeline_routes._trends_for_entries(entries, ["A", "B"], {"run": "x"}, missing="{sku}", skip_at_cap=True)
            saved = pricerefresh.read_trends()
            checks.equal(sorted(answer["refused"]), ["B"], "the press answers B refused")
            checks.equal(
                (saved["A"]["ranges"][0]["points"], saved["B"]["at"], saved["B"]["ranges"][0]["points"]),
                (["fresh"], 5, ["good"]),
                "the press saved what it read, and the refused SKU kept its good strip and its old date",
            )
    finally:
        pricehistory.Market, pricehistory.catalogued_row, pipeline_routes._history_spark = real


CHECKS = (
    check_price_movers,
    check_price_refresh_note,
    check_price_trends_preload,
    check_trends_press_saves,
)
