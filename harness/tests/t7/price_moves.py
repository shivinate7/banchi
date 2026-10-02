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

    checks.equal(daily_path_reaches(SCRIPT.read_text()), (True, {"do_live_export"}), FENCE_LABEL)
    checks.equal(
        daily_path_reaches(SCRIPT.read_text().replace("pipeline_routes.do_live_export", "pipeline_routes.do_pipeline_export")),
        (True, {"do_pipeline_export"}),
        "the callee check reads the callee: a swapped-in paid export is seen",
    )


FENCE_LABEL = (
    "the daily job passes `do_live_export` to the note writer and reaches nothing else of "
    "`server/`, `cli/` or `identify/`: no paid read, no sweep"
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


CHECKS = (
    check_price_movers,
    check_price_refresh_note,
)
