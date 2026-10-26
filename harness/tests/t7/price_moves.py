"""T7 group: price moves since listing, and the daily market read's note (DEBT69).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from cli import cmd_pricearchive
from harness.tests import Checks
from harness.tests.t7.common import isolated_home
from pipeline import movers, pricearchive as archive_walk, pricehistory, pricerefresh
from pipeline.pricehistory import Bucket as HistoryBucket, Reading as HistoryReading, Series
from server import pipeline_routes
from store import files
from store.master import Card
from store.pricearchive import Bucket
from store.readings import KIND_LIVE, KIND_RUN, Reading, Source
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
    fetch, the note writer and the one archive sweep press (`cli.cmd_pricearchive`, scheduled by the
    owner's word, DEBT32), and nothing that spends money.
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
    # The scanner reads the syntax tree, so an import-looking line inside a string, a multi-line
    # string or a comment (with comment openers and a lone quote in it) is text, never an import.
    hidden = (
        "\nTEXT = 'from cli.cmd_identify import run'\n"
        'BLOCK = """\nfrom cli.cmd_identify import run  # /* // don\'t\n"""\n'
        "# don't: import cli.cmd_identify\n"
    )
    checks.equal(
        daily_path_reaches(SCRIPT.read_text() + hidden), (True, {"do_prices_refresh"}),
        "an import inside a string, a multi-line string or a comment with a lone quote is not reached",
    )
    checks.equal(
        daily_path_reaches(SCRIPT.read_text() + "\nfrom cli.cmd_identify import run\n")[0], False,
        "a dotted `from cli.cmd_identify import run` is seen: the fence matches the package, not only the bare name",
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


# ------------------------------------------------------------------ the nightly archive sweep
#
# The owner's word is "Nightly, on the Mac" (DEBT32). The daily job runs `archive sweep --write`
# after its refresh, in the same process, at the pace D222 saved, and stops where D222 stops.
# THE SEAM IS `job.run()` PLUS TWO STUBS: `do_prices_refresh` (the refresh) and `pricehistory.Market`
# (the host). The job's `say` goes to its log. Every case reads the store, the log and what the
# stubbed host was asked, never the job's wording beyond the few words each case names.

SWEEP_SKUS = ["70%02d" % n for n in range(1, 9)]
REFRESH_OK = {"ok": True, "steps": {"history": {"ok": True}}}
REFRESH_FAILED = {"ok": False, "steps": {}}
REFRESH_HISTORY_FAILED = {"ok": True, "steps": {"history": {"ok": False}}}


class _Host:
    """What the stubbed host saw. `refuse_after` is how many SKUs it answers before it answers HTTP
    403 to every later one (None: never; 0: from the very first, with no earlier success). `empty`
    answers every SKU with a strip that holds no bucket. The counters live here, not on a Market,
    because the backoff builds a second Market."""

    def __init__(self, refuse_after=None, empty=False):
        self.refuse_after = refuse_after
        self.empty = empty
        self.asked = []
        self.built = []

    def market(self):
        host = self

        class StubMarket:
            def __init__(self, cache_dir=None, fetcher=None, courtesy_delay=0.0, now=None, user_agent=""):
                host.built.append(courtesy_delay)
                self.requests = 0

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
                readings, refusals = {}, {}
                for row in rows:
                    sku = row.get("TCGplayer Id", "")
                    host.asked.append(sku)
                    self.requests += len(ranges)
                    if host.refuse_after is not None and len(host.asked) > host.refuse_after:
                        refusals[sku] = (
                            "https://infinite-api.tcgplayer.com/price/history/42/detailed?range=month "
                            + archive_walk.BLOCKED_SIGNATURE + ". Set BANCHI_TCG_USER_AGENT."
                        )
                        continue
                    readings[sku] = HistoryReading(sku=sku, product_id=42, series={
                        r: Series(
                            sku=sku, product_id=42, range=r, variant="Normal", condition="Near Mint",
                            language="English", total_quantity_sold=1, total_transaction_count=1,
                            buckets=() if host.empty else (HistoryBucket(
                                start=date(2026, 9, 1), market=Decimal("1.00"), quantity=1, transactions=1,
                                low=Decimal("1.00"), high=Decimal("1.00"),
                            ),),
                        )
                        for r in ranges
                    })
                return readings, refusals

        return StubMarket


def _seed_sweep_store(skus) -> None:
    """The cards the sweep walks, and one bucket from an earlier pass for a SKU no card carries
    (D219: a pass never deletes a bucket it did not mention)."""
    with Store().write() as writable:
        for n, sku in enumerate(skus, start=1):
            writable.inventory.cards["1:%d" % n] = Card(
                box=1, index=n, sku=sku, name="Card " + sku, number="%03d" % n, printed_total="132",
                set_name="ME01: Mega Evolution", game="pokemon", condition="Near Mint",
            )
        writable.archive.upsert({"OLD1:month:2025-01-01": _bucket("OLD1", "2025-01-01", "3.00", 1)})


@contextmanager
def _daily_job(home: Path):
    """The job script, loaded with HOME in the throwaway home so its log (`~/.banchi`) is never the
    owner's. A log outside `home` is a failed case, not a write to the owner's file."""
    with mock.patch.dict(os.environ, {"HOME": str(home)}):
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            spec = importlib.util.spec_from_file_location("price_refresh_daily_under_test", SCRIPT)
            job = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(job)
        finally:
            sys.path.remove(str(SCRIPT.parent))
        yield job


def _run_daily(home: Path, refresh: dict, host: _Host, chunk: int = 2):
    """One run of the job: `(exit code, log lines, error)`. Chunks of `chunk` SKUs so a few SKUs
    make several commits (D224). `fetch_json` raises: a path past the stubbed market fails loudly."""
    with _daily_job(home) as job:
        log = Path(job.LOG)
        if home.resolve() not in log.resolve().parents:
            return None, [], "the job's log is outside the throwaway home: " + str(log)
        code = error = None
        with mock.patch.object(pipeline_routes, "do_prices_refresh", return_value=refresh), \
                mock.patch.object(pricehistory, "Market", host.market()), \
                mock.patch.object(pricehistory, "fetch_json", side_effect=AssertionError("network past the stub")), \
                mock.patch.object(archive_walk, "CHUNK_SKUS", chunk):
            try:
                code = job.run()
            except Exception as exc:  # noqa: BLE001 a crash is a failed case with its own sentence
                error = "%s: %s" % (type(exc).__name__, exc)
        return code, (log.read_text().splitlines() if log.exists() else []), error


def _said(lines, *words) -> bool:
    return any(all(w in line.lower() for w in words) for line in lines)


def _archived_skus() -> list:
    return sorted({b.sku for b in Store().read().archive.entries.values()})


def _archive_note() -> dict:
    """The `archive` step of the `#/pricing` note the job left, `{}` when it left none."""
    return ((pricerefresh.read_status() or {}).get("steps") or {}).get("archive") or {}


def check_daily_job_sweeps_after_refresh(checks: Checks) -> None:
    """After a good refresh the job runs `archive sweep --write`, starting at the pace D222 saved.

    WRITE ON IS READ OFF THE STORE: a preview makes no request and writes nothing (D224), so
    buckets in the archive for every subject mean the walk ran and committed.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a good refresh is followed by `archive sweep --write` at the saved pace")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        archive_walk.save_pace(
            cmd_pricearchive.market_cache_dir() / "throttle-pace.json", 0.37,
            requests_made=800, elapsed_seconds=80, at=1,
        )
        host = _Host()
        code, lines, error = _run_daily(home, REFRESH_OK, host)
        checks.equal(error, None, "the job ran to its end")
        checks.equal(code, 0, "a good refresh and a whole sweep end the job with exit 0")
        checks.equal(sorted(host.asked), SWEEP_SKUS[:3], "the host was asked once for every card's SKU")
        checks.equal(host.built, [0.37], "the one Market was built at the pace the last throttle saved (D222)")
        checks.equal(
            _archived_skus(), sorted(["OLD1"] + SWEEP_SKUS[:3]),
            "write is on: every subject's buckets are committed, and the earlier bucket stays (D219)",
        )
        checks.equal(
            len(Store().read().archive.entries), 1 + 3 * len(pricehistory.RANGES),
            "one bucket per subject per range",
        )
        checks.ok(_said(lines, "archive sweep"), "the log has an `archive sweep` line", "\n".join(lines)[-400:])


def check_daily_job_failed_refresh_skips_sweep(checks: Checks) -> None:
    """A refresh that failed skips the sweep, asks the host nothing, and the log says why.

    THE FAILED REFRESH'S OWN VERDICT STANDS: the job still ends with exit 1, so the sweep's
    absence is not a quiet success. Two failures: the refresh itself, and its sales-history step
    (the job's existing definition of a good run).
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a failed refresh skips the sweep, and the log says so")
    for label, refresh in (("refresh failed", REFRESH_FAILED), ("sales-history step failed", REFRESH_HISTORY_FAILED)):
        with isolated_home() as home:
            _seed_sweep_store(SWEEP_SKUS[:3])
            host = _Host()
            code, lines, error = _run_daily(home, refresh, host)
            checks.equal(error, None, "%s: the job ran to its end" % label)
            checks.equal(code, 1, "%s: the job still ends with exit 1" % label)
            checks.equal((host.built, host.asked), ([], []), "%s: no Market is built and the host is asked nothing" % label)
            checks.equal(_archived_skus(), ["OLD1"], "%s: nothing new is archived" % label)
            checks.ok(
                _said(lines, "archive sweep", "skipped", "refresh"),
                "%s: the log says the archive sweep was skipped because of the refresh" % label,
                "\n".join(lines)[-400:],
            )


def check_daily_job_sweep_stops_on_second_throttle(checks: Checks) -> None:
    """Two throttle answers in a row stop the sweep. What it already committed stays (D222, D224).

    EIGHT SKUS IN CHUNKS OF TWO: chunk 1 is answered, chunk 2 is refused (the one backoff), chunk 3
    is refused again (the stop). Chunk 4 is never asked for, and the job does not re-run the sweep
    to try again. The second pace is not asserted: with no time passing it is the floor.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a second throttle stops it, committed buckets stay")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS)
        host = _Host(refuse_after=2)
        code, lines, error = _run_daily(home, REFRESH_OK, host)
        checks.equal(error, None, "the job ran to its end")
        checks.equal(len(host.asked), 6, "the host was asked for chunks 1 to 3 and never for chunk 4")
        checks.equal(len(set(host.asked)), 6, "no SKU was asked twice: the job does not retry a stopped sweep")
        checks.equal(len(host.built), 2, "one Market at the start and one after the single backoff")
        archived = _archived_skus()
        checks.equal(len(archived), 3, "the archive holds chunk 1's two SKUs and the earlier bucket's SKU, nothing else")
        checks.equal(
            archived, sorted(["OLD1"] + host.asked[:2]),
            "chunk 1's buckets stay in the archive, nothing from the refused chunks, and the earlier bucket stays",
        )
        saved = {}
        pace_file = cmd_pricearchive.market_cache_dir() / "throttle-pace.json"
        if pace_file.exists():
            saved = json.loads(pace_file.read_text("utf-8"))
        checks.ok(
            saved.get("measured_from_requests", 0) > 0,
            "the throttle's measured pace is saved for the next night (D222)", str(saved),
        )
        checks.ok(
            _said(lines, "archive sweep", "throttl"),
            "the log says the archive sweep met a throttle and stopped", "\n".join(lines)[-400:],
        )


def check_daily_job_sweep_stops_on_first_refusal(checks: Checks) -> None:
    """A host that answers HTTP 403 from the very first SKU, with no earlier success, stops the
    sweep, and the job records `archive` as not ok (D222, D224).

    NO EARLIER SUCCESS IS THE CASE `classify_refusals` leaves as an authorization guess, so the
    sweep's throttle test (which needs a prior answer) never fires on it: every chunk is asked
    for, 0 buckets are written, and the note used to say "Price archive swept.". EIGHT SKUS IN
    CHUNKS OF TWO, so a sweep that never stops asks for all eight.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a 403 from the first SKU stops it, and the note says it failed")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS)
        host = _Host(refuse_after=0)
        code, lines, error = _run_daily(home, REFRESH_OK, host)
        note = _archive_note()
        checks.equal(error, None, "the job ran to its end")
        checks.ok(
            0 < len(host.asked) < len(SWEEP_SKUS),
            "the sweep stops: the host is asked, and never for every chunk",
            "asked %d of %d: %s" % (len(host.asked), len(SWEEP_SKUS), host.asked),
        )
        checks.equal(_archived_skus(), ["OLD1"], "nothing new is archived, and the earlier bucket stays (D219)")
        checks.equal(note.get("ok"), False, "the `archive` step of the note is not ok")
        checks.ok(
            note.get("message") != "Price archive swept.",
            "the note does not say the price archive was swept", str(note),
        )


def check_daily_job_empty_sweep_is_not_ok(checks: Checks) -> None:
    """A sweep that was asked for cards and wrote 0 buckets is not ok, whatever the host said.

    THE HOST ANSWERS EVERY SKU WITH AN EMPTY STRIP: no refusal, no throttle, and nothing to write.
    The note must not claim a sweep that archived nothing. An all-fresh night (nothing left to read)
    is a different case and is not asserted here.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a sweep that wrote 0 buckets is not ok")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        host = _Host(empty=True)
        code, lines, error = _run_daily(home, REFRESH_OK, host)
        note = _archive_note()
        checks.equal(error, None, "the job ran to its end")
        checks.equal(sorted(host.asked), SWEEP_SKUS[:3], "the host was asked for every card")
        checks.equal(_archived_skus(), ["OLD1"], "0 buckets are written, and the earlier bucket stays (D219)")
        checks.equal(note.get("ok"), False, "the `archive` step of the note is not ok")
        checks.ok(
            note.get("message") != "Price archive swept.",
            "the note does not say the price archive was swept", str(note),
        )


FENCE_LABEL = (
    "the daily job calls `do_prices_refresh` (the live listings, the catalog, the join, the sales history) "
    "and the one archive sweep press (`cli.cmd_pricearchive`, D224 and DEBT32), and reaches nothing else of "
    "`server/`, `cli/` or `identify/`: no paid read"
)

_PACKAGES = ("cli", "identify", "pipeline", "server", "store")


def daily_path_reaches(source: str):
    """`(imports are exactly the note writer, the server module and the archive sweep press, the
    `pipeline_routes` attributes the script touches)`. A callee other than `do_prices_refresh`
    changes the second. A dotted `from cli.x import y` counts as `cli.x`, as `from cli import x` does."""
    tree = ast.parse(source)
    reached = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _PACKAGES:
            reached.update("%s.%s" % (node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _PACKAGES:
            reached.add(node.module)
        elif isinstance(node, ast.Import):
            reached.update(a.name for a in node.names if a.name.split(".")[0] in _PACKAGES)
    touched = {
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "pipeline_routes"
    }
    return reached == {"pipeline.pricerefresh", "server.pipeline_routes", "cli.cmd_pricearchive"}, touched


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


def check_older_rejoin_keeps_newer_rows(checks: Checks) -> None:
    """A re-join against an OLDER export of a run writes the SKUs only that export has, keeps the row a
    newer reading already holds on a shared SKU, and leaves the run's source row at the newer time.

    Before the fix the whole re-join was dropped, so a SKU only the older export carried never
    reached the table. The reads are fresh `Store().read()` calls, not the writer's own view.
    """
    checks.note("")
    checks.note("OLDER RE-JOIN — adds what only the older export has, keeps the newer rows")
    with isolated_home():
        with Store().write() as writable:
            writable.readings.replace_source(
                KIND_RUN, "run-x", {"501": Reading("12.00", 2000, "run-x", KIND_RUN)},
                Source(KIND_RUN, "run-x", 2000, 1),
            )
        with Store().write() as writable:
            writable.readings.replace_source(
                KIND_RUN, "run-x",
                {"501": Reading("9.00", 1000, "run-x", KIND_RUN), "502": Reading("5.00", 1000, "run-x", KIND_RUN)},
                Source(KIND_RUN, "run-x", 1000, 2),
            )
        readings = Store().read().readings
        shared, only_older = readings.entries.get("501"), readings.entries.get("502")
        checks.equal(
            (getattr(shared, "market", None), getattr(shared, "at", None)),
            ("12.00", 2000),
            "a SKU both exports carry keeps the newer row, its price and its time",
        )
        checks.equal(
            getattr(only_older, "market", None), "5.00",
            "a SKU only the older export carries is written",
        )
        checks.equal(
            [source["at"] for source in readings.sources_payload() if source["name"] == "run-x"], [2000],
            "the run's source row keeps the newer export's time",
        )


CHECKS = (
    check_price_movers,
    check_price_refresh_note,
    check_daily_job_sweeps_after_refresh,
    check_daily_job_failed_refresh_skips_sweep,
    check_daily_job_sweep_stops_on_second_throttle,
    check_daily_job_sweep_stops_on_first_refusal,
    check_daily_job_empty_sweep_is_not_ok,
    check_price_trends_preload,
    check_trends_press_saves,
    check_older_rejoin_keeps_newer_rows,
)
