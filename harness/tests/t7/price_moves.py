"""T7 group: price moves since listing, and the daily market read's note (DEBT69).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import plistlib
import shlex
import subprocess
import sys
import types
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from cli import cmd_pricearchive
from harness.tests import Checks
from harness.tests.t7.common import isolated_home
from pipeline import movers, pricearchive as archive_walk, pricehistory, pricerefresh
from pipeline.pricehistory import Bucket as HistoryBucket, Reading as HistoryReading, Series
from server import pipeline_routes
from store import clock, files
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
    fetch, the note writer, the one archive sweep press (`cli.cmd_pricearchive`, scheduled by the
    owner's word, DEBT32) and the daily TCGCSV read (`pipeline.dailyprices`, free), and nothing that
    spends money.
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
        daily_path_reaches(SCRIPT.read_text().replace("pipeline_routes.do_prices_refresh", "pipeline_routes.do_pipeline_export"))[1],
        {"do_pipeline_export"},
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
        daily_path_reaches(SCRIPT.read_text() + hidden), daily_path_reaches(SCRIPT.read_text()),
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
#: What `pipeline.dailyprices.run_pass` answers when its day is already finished.
DAILY_PASS_SKIPPED = {"day": "2026-10-27", "skipped": True, "rows": 0, "failed": {}}


@contextmanager
def _daily_prices_stand_in(read=None):
    """`pipeline.dailyprices.run_pass` replaced by `read` (a Mock a case counts) or, with none, by one that
    answers "this day is finished". Yields the Mock.

    A STAND-IN MODULE, NEVER A PATCH ON THE REAL ONE: it holds whether or not `pipeline/dailyprices.py` exists,
    and it keeps the TCGCSV read out of every case that is about the refresh or the sweep (their stubbed `Market`
    has no `groups`, and they count the Markets built). So the job reaches the read only as
    `from pipeline import dailyprices` and `dailyprices.run_pass(...)`, looked up when it runs, and builds no
    `Market` for it in the script itself.
    """
    read = read if read is not None else mock.Mock(return_value=DAILY_PASS_SKIPPED)
    stand_in = types.SimpleNamespace(run_pass=read)
    import pipeline
    # ONE KEY IS PUT BACK, NEVER THE WHOLE `sys.modules`: `_run_main` execs the job script in here, and a module
    # first imported inside (`launchagent`, a lazy `server.tcg_export`) must stay, or a later import would make a
    # second copy that a patch on the first never reaches.
    key, absent = "pipeline.dailyprices", object()
    saved = sys.modules.get(key, absent)
    sys.modules[key] = stand_in
    try:
        with mock.patch.object(pipeline, "dailyprices", stand_in, create=True):
            yield read
    finally:
        if saved is absent:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = saved


class _Host:
    """What the stubbed host saw. `refuse_after` is how many SKUs it answers before it answers HTTP
    403 to every later one (None: never; 0: from the very first, with no earlier success). `empty`
    answers every SKU with a strip that holds no bucket. `during` is called each time the sweep asks
    the host, so a case can look at the world mid-sweep. The counters live here, not on a Market,
    because the backoff builds a second Market."""

    def __init__(self, refuse_after=None, empty=False, during=None):
        self.refuse_after = refuse_after
        self.empty = empty
        self.during = during
        self.asked = []
        self.built = []

    def market(self):
        host = self

        class StubMarket:
            def __init__(self, cache_dir=None, fetcher=None, courtesy_delay=0.0, now=None, user_agent=""):
                host.built.append(courtesy_delay)
                self.requests = 0

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
                if host.during:
                    host.during()
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


def _refresh_patch(refresh):
    """`do_prices_refresh` stubbed: a dict is its answer, a callable is its body. The patch counts the calls."""
    kind = {"side_effect": refresh} if callable(refresh) else {"return_value": refresh}
    return mock.patch.object(pipeline_routes, "do_prices_refresh", **kind)


def _refresh_stub(ok: bool = True):
    """A refresh that leaves the notes the real one leaves (`_prices_refresh_steps` writes the top-level
    note through `pricerefresh.run`, then one step note as each step ends). A once-per-day guard reads
    those notes, and a bare answer leaves none."""
    def fetch() -> dict:
        if not ok:
            raise RuntimeError("the refresh stub failed")
        return {"live_rows": 1}

    def refresh(*_args, **_kwargs):
        pricerefresh.run(fetch)
        for step in ("listings", "catalog", "join", "history"):
            pricerefresh.note_step(step, ok)
        return {"ok": ok, "steps": pricerefresh.read_status()["steps"], "live": {}}

    return refresh


def _run_daily(home: Path, refresh: dict, host: _Host, chunk: int = 2, daily=None):
    """One run of the job: `(exit code, log lines, error)`. Chunks of `chunk` SKUs so a few SKUs
    make several commits (D224). `fetch_json` raises: a path past the stubbed market fails loudly. `daily` is the
    Mock standing in for the daily TCGCSV read (`_daily_prices_stand_in`); none means one that says its day is finished."""
    with _daily_job(home) as job:
        log = Path(job.LOG)
        if home.resolve() not in log.resolve().parents:
            return None, [], "the job's log is outside the throwaway home: " + str(log)
        code = error = None
        with _refresh_patch(refresh), _daily_prices_stand_in(daily), \
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
        checks.equal(_archive_note().get("ok"), False, "a sweep that stopped is not ok in the `archive` step of the note")


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
            "price archive swept" not in str(note.get("message")).lower(),
            "the note does not say the price archive was swept", str(note),
        )


def check_daily_job_empty_sweep_is_ok(checks: Checks) -> None:
    """A sweep whose every SKU answered with no sale is ok, and is not asked again that day.

    THE HOST ANSWERS EVERY SKU WITH AN EMPTY STRIP: no refusal, no throttle, nothing to write. A card
    that never sold has no bucket, so it never looks fresh (freshness is read off buckets) and every
    sweep asks for it again. A rule that called this a failure made the note red every night and sent
    the next run back to the host. NOT OK IS A PASS THAT STOPPED: a refusal or a throttle that ended
    it (the two cases below this one) or an unreadable store. THE STORE'S OWN PASS RECORD PROVES THE
    FIXTURE: every card requested, none refused. An empty strip is not counted as answered there.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — every SKU answered, no sales: ok, and not asked twice in a day")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        host = _Host(empty=True)
        code, lines, error = _run_daily(home, REFRESH_OK, host)
        note = _archive_note()
        checks.equal(error, None, "the job ran to its end")
        checks.equal(sorted(host.asked), SWEEP_SKUS[:3], "the host was asked for every card")
        checks.equal(
            {(row["requested"], row["refused"]) for row in Store().read().archive.sources_payload()}, {(3, 0)},
            "the store's pass record: 3 cards requested and none refused, so this is no refusal's case",
        )
        checks.equal(_archived_skus(), ["OLD1"], "0 buckets are written, and the earlier bucket stays (D219)")
        checks.equal(note.get("ok"), True, "the `archive` step of the note is ok")
        again = _Host()
        _run_daily(home, REFRESH_OK, again)
        checks.equal(
            (again.built, again.asked), ([], []),
            "the next run that day builds no Market and asks the host nothing: ok is what ends the day's sweep",
        )


def check_daily_job_reads_daily_prices_after_a_good_refresh(checks: Checks) -> None:
    """The daily TCGCSV read (`pipeline.dailyprices.run_pass`) follows a good refresh and never a failed one,
    and a sweep that stops early does not stop it.

    THE READ IS A STAND-IN HERE (`_daily_prices_stand_in`): its own cases, the day guard included, are
    `scripts/dailyprices-selftest.py`. What is proved is WHEN the job calls it, and that it is handed the
    User-Agent knob's value (`pricehistory.AGENT_ENV`, the one knob, never a second). The job does not guard
    the day itself: the read does, so every start calls it. Two failed refreshes (the refresh itself, and its
    sales-history step) are the job's own definition of a failed run. THE STOPPED SWEEP IS A REAL ONE: eight
    SKUs and a host that refuses from the first, as `check_daily_job_sweep_stops_on_first_refusal` builds it.
    """
    checks.note("")
    checks.note("DAILY JOB DAILY PRICES — after a good refresh, even over a stopped sweep; never after a failed one")
    arms = (
        ("good refresh", REFRESH_OK, _Host(), 1),
        ("good refresh, the sweep stopped early", REFRESH_OK, _Host(refuse_after=0), 1),
        ("refresh failed", REFRESH_FAILED, _Host(), 0),
        ("sales-history step failed", REFRESH_HISTORY_FAILED, _Host(), 0),
    )
    for label, refresh, host, calls in arms:
        with isolated_home() as home, mock.patch.dict(os.environ, {pricehistory.AGENT_ENV: "job-agent/1.0"}):
            _seed_sweep_store(SWEEP_SKUS)
            read = mock.Mock(return_value=DAILY_PASS_SKIPPED)
            code, lines, error = _run_daily(home, refresh, host, daily=read)
            checks.equal(error, None, "%s: the job ran to its end" % label)
            checks.equal(read.call_count, calls, "%s: the daily read is called %d time(s)" % (label, calls))
            if calls:
                checks.equal(
                    (read.call_args.kwargs if read.call_args else {}).get("user_agent"), "job-agent/1.0",
                    "%s: the read is handed the User-Agent knob's value" % label,
                )
            if label.endswith("stopped early"):
                checks.ok(
                    _said(lines, "archive sweep", "stopped early"),
                    "%s: the sweep did stop, so this arm is the independence case" % label, "\n".join(lines)[-400:],
                )
            if not calls:
                checks.equal(
                    (host.built, host.asked), ([], []),
                    "%s: no Market is built and the host is asked nothing" % label,
                )


def check_daily_job_second_run_same_day_skips_sweep(checks: Checks) -> None:
    """Once today's sweep finished, a second job run on the same US Central day sweeps nothing.

    `hermetic` pins the Central day for the whole check, so both runs are on one day however long
    they take. The refresh here is a bare stub that leaves no step notes, so only the sweep's own
    guard is under test; the refresh's guard is `check_daily_job_login_run_does_the_day_once`. A
    sweep that STOPPED is not finished: the next run that day resumes it, so "skip" is not "skip
    after any earlier try".
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a finished sweep is not run twice in one US Central day")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        first, second = _Host(), _Host()
        code1, _, error1 = _run_daily(home, REFRESH_OK, first)
        code2, lines2, error2 = _run_daily(home, REFRESH_OK, second)
        checks.equal((error1, code1, sorted(first.asked)), (None, 0, SWEEP_SKUS[:3]), "the first run sweeps every card")
        checks.equal((error2, code2), (None, 0), "the second run ends with exit 0")
        checks.equal((second.built, second.asked), ([], []), "the second run builds no Market and asks the host nothing")
        checks.ok(
            _said(lines2, "archive sweep", "skipped", "today"),
            "the second run's log says the sweep was skipped because today's finished", "\n".join(lines2)[-400:],
        )
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS)
        stopped, resumed = _Host(refuse_after=2), _Host()
        _run_daily(home, REFRESH_OK, stopped)
        _, lines, error = _run_daily(home, REFRESH_OK, resumed)
        checks.equal(error, None, "the run after a stopped sweep ran to its end")
        checks.ok(bool(resumed.asked), "a stopped sweep is not finished: the next run that day asks the host again", "\n".join(lines)[-400:])
        checks.equal(
            _archived_skus(), sorted(["OLD1"] + SWEEP_SKUS),
            "the resumed run completes the archive for every card, and the earlier bucket stays (D219)",
        )


# What `launchagent.agent` on main puts in the installed job's argv after the script: nothing. An
# owner's plist that is already loaded runs `price-refresh-daily.py` with no flag, and "nightly, on
# the Mac" must not need a reinstall to start working.
INSTALLED_JOB_ARGV: list = []


def _make_price_refresh_argv():
    """`(script arguments, environment words before the interpreter)` as `make price-refresh` runs
    the script, read off `make -n` so a Makefile edit is seen. `None` when the recipe does not run
    the daily script at all."""
    shown = subprocess.run(
        ["make", "-n", "-C", str(SCRIPT.parent.parent), "price-refresh", "ARGS="],
        capture_output=True, text=True, check=False,
    ).stdout
    for line in shown.splitlines():
        try:
            words = shlex.split(line)
        except ValueError:
            continue
        for at, word in enumerate(words):
            if word.endswith(SCRIPT.name):
                env = dict(w.split("=", 1) for w in words[:at] if "=" in w and w.split("=", 1)[0].isidentifier())
                return words[at + 1:], env
    return None


def _run_main(home: Path, argv: list, host: _Host, env: dict = None, chunk: int = 2, refresh=REFRESH_OK, daily=None):
    """The job script run as `python scripts/price-refresh-daily.py <argv>`, its `__main__` block
    (argument parser and run lock) included: `(exit code, error, refresh calls)`. The log and the
    lock handle are checked to be in the throwaway home. `--agent` would install a launchd job, so
    it is refused here before anything runs. `refresh` is `_refresh_patch`'s. `daily` is `_run_daily`'s."""
    assert "--agent" not in argv, "a check never installs the owner's launchd job"
    namespace = {"__name__": "__main__", "__file__": str(SCRIPT)}
    code = error = None
    with mock.patch.dict(os.environ, {"HOME": str(home), **(env or {})}), mock.patch.object(sys, "argv", [str(SCRIPT), *argv]), \
            _refresh_patch(refresh) as called, _daily_prices_stand_in(daily), \
            mock.patch.object(pricehistory, "Market", host.market()), \
            mock.patch.object(pricehistory, "fetch_json", side_effect=AssertionError("network past the stub")), \
            mock.patch.object(archive_walk, "CHUNK_SKUS", chunk):
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), namespace)  # noqa: S102 the repo's own script
        except SystemExit as stop:
            code = stop.code or 0
        except Exception as exc:  # noqa: BLE001 a crash is a failed case with its own sentence
            error = "%s: %s" % (type(exc).__name__, exc)
        finally:
            sys.path.remove(str(SCRIPT.parent))
            if namespace.get("lock"):
                namespace["lock"].close()
        log = Path(namespace["LOG"]) if "LOG" in namespace else None
        if log is not None and home.resolve() not in log.resolve().parents:
            error = "the job's log is outside the throwaway home: " + str(log)
    return code, error, called.call_count


def check_installed_job_sweeps_without_reinstall(checks: Checks) -> None:
    """The job already loaded in launchd (no flag after the script) sweeps; `make price-refresh` does not.

    THE INSTALLED PLIST CANNOT BE CHANGED FROM HERE: an owner who does not reinstall keeps the argv
    `launchagent.agent` wrote before (`INSTALLED_JOB_ARGV`). So the script's default run is the
    nightly run. The manual press is the other way round: a read now, over this store, that starts
    no sweep unless asked. Both go through the script's `__main__`, the way each real caller does.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — the installed job sweeps with no reinstall, the manual press does not")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        host = _Host()
        code, error, refreshed = _run_main(home, INSTALLED_JOB_ARGV, host)
        checks.equal((error, code, refreshed), (None, 0, 1), "an installed job (no flag) refreshes once and ends with exit 0")
        checks.equal(sorted(host.asked), SWEEP_SKUS[:3], "an installed job (no flag) sweeps: the host is asked for every card")
        checks.equal(
            _archived_skus(), sorted(["OLD1"] + SWEEP_SKUS[:3]),
            "an installed job (no flag) commits the buckets, and the earlier bucket stays (D219)",
        )
    manual = _make_price_refresh_argv()
    checks.ok(manual is not None, "`make price-refresh` runs the daily job script, the argv this check reads", str(manual))
    if manual is None:
        return
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        host = _Host()
        code, error, refreshed = _run_main(home, manual[0], host, manual[1])
        checks.equal((error, code, refreshed), (None, 0, 1), "`make price-refresh` refreshes once and ends with exit 0")
        checks.equal((host.built, host.asked), ([], []), "`make price-refresh` starts no sweep: no Market is built, the host is asked nothing")
        checks.equal(_archived_skus(), ["OLD1"], "`make price-refresh` archives nothing new")


def check_daily_job_sweep_holds_the_refresh_lock(checks: Checks) -> None:
    """While the sweep reads from the host, a refresh that starts is turned away: the sweep holds `refresh_lock`.

    The "Refresh now" press on `#/pricing` shares that lock with the job. A refresh mid-sweep would be
    a second caller on the host the sweep paces itself against. THE PROBE IS THE LOCK'S OWN
    NON-BLOCKING TRY, made each time the host is asked: `False` is what a refresh that waits and a
    refresh that is refused both get. `do_prices_refresh` itself is not called here: with the lock
    free it would fetch. The job runs through its `__main__`, the way launchd runs it.
    """
    checks.note("")
    checks.note("DAILY JOB SWEEP — a refresh that starts mid-sweep gets no lock, and the lock is free after")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        probes = []

        def probe() -> None:
            with pricerefresh.refresh_lock() as held:
                probes.append(held)

        host = _Host(during=probe)
        code, error, _ = _run_main(home, INSTALLED_JOB_ARGV, host)
        checks.equal((error, code), (None, 0), "the job ran to its end with exit 0")
        checks.equal(sorted(host.asked), SWEEP_SKUS[:3], "the host was asked for every card")
        checks.ok(
            bool(probes) and not any(probes),
            "every refresh that tried to start while the sweep read got no lock", "tries, lock got: %s" % probes,
        )
        with pricerefresh.refresh_lock() as held:
            checks.ok(held, "the lock is free again once the job has ended")


def check_installed_job_runs_at_login(checks: Checks) -> None:
    """The installed launchd job carries `RunAtLoad`, so a Mac that was off at 05:15 runs it at login.

    THE OWNER'S WORD: "if the day is a new day when my mac is on, just get it done then". The plist
    is what the job's own `agent(False)` writes, into the throwaway home, with `launchctl` a
    recorder: the owner's loaded job is never touched. The case stops before installing if the
    home is not the throwaway one. A linked worktree's `.git` is a file and makes the installer
    refuse, so the root is a folder in the throwaway home.
    """
    checks.note("")
    checks.note("DAILY JOB — the installed plist runs the job at login as well as at 05:15")
    with isolated_home() as home, _daily_job(home) as job:
        if not checks.equal(Path.home().resolve(), home.resolve(), "the plist goes to the throwaway home, never the owner's LaunchAgents"):
            return
        root = home / "main-checkout"
        root.mkdir()
        launchctl = mock.Mock(return_value=mock.Mock(returncode=0, stderr=""))
        with mock.patch.object(job, "ROOT", root), mock.patch.object(job.launchagent.subprocess, "run", launchctl):
            code = job.agent(False)
        path = home / "Library" / "LaunchAgents" / (job.LABEL + ".plist")
        plist = plistlib.loads(path.read_bytes()) if path.exists() else {}
        checks.equal(code, 0, "the install ends with exit 0")
        checks.ok(bool(plist), "the plist was written into the throwaway home", str(path))
        checks.equal(plist.get("RunAtLoad"), True, "the plist runs the job at login (RunAtLoad)")
        checks.ok("StartCalendarInterval" in plist, "the plist keeps its daily time")
        checks.equal(plist.get("ProgramArguments", [])[2:], INSTALLED_JOB_ARGV, "the plist passes the flags the sweeping job is read with")
        checks.ok(
            bool(launchctl.call_args_list) and all(call.args[0][0] == "launchctl" for call in launchctl.call_args_list),
            "the only commands the install ran were launchctl, and the recorder took them",
        )


def check_daily_job_login_run_does_the_day_once(checks: Checks) -> None:
    """A run at login on a day whose refresh and sweep finished does nothing; a new day does both again.

    THE OWNER'S WORD: "if the day is a new day when my mac is on, just get it done then". With
    `RunAtLoad` the job can start many times a day, and each start that reached the host would be
    a second live fetch from the seller portal and a second sweep. THE GUARD IS "FINISHED TODAY",
    never "tried today": a failed refresh and a stopped sweep are run again by the next start.
    The refresh and the sweep are two guards: a finished refresh is not repeated when only the sweep
    is left, and a refresh skipped as done must not skip the sweep. The stub refresh leaves the
    step notes the real one leaves. The day is `store/clock`'s (US Central), moved two days on for
    the new day, so a 25-hour day or a run across midnight cannot make it flaky. Every start is
    the installed job's own argv through the script's `__main__`.
    """
    checks.note("")
    checks.note("DAILY JOB — a login run does the day's refresh and sweep once, and a new day again")
    argv = INSTALLED_JOB_ARGV
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        first, login = _Host(), _Host()
        c1, e1, r1 = _run_main(home, argv, first, refresh=_refresh_stub())
        c2, e2, r2 = _run_main(home, argv, login, refresh=_refresh_stub())
        checks.equal((e1, c1, r1, sorted(first.asked)), (None, 0, 1, SWEEP_SKUS[:3]), "the first run of the day refreshes once and sweeps every card")
        checks.equal((e2, c2, r2), (None, 0, 0), "a run at login on that day ends with exit 0 and asks for no refresh")
        checks.equal((login.built, login.asked), ([], []), "it builds no Market and asks the host nothing for the sweep")
        _seed_sweep_store(SWEEP_SKUS[:4])  # one card arrived since; the other three are still fresh
        tomorrow = clock._current() + timedelta(days=2)
        later = _Host()
        with mock.patch.object(clock, "_current", lambda: tomorrow):
            c3, e3, r3 = _run_main(home, argv, later, refresh=_refresh_stub())
        checks.equal(
            (e3, c3, r3, later.asked), (None, 0, 1, [SWEEP_SKUS[3]]),
            "on the next US Central day the job refreshes again and sweeps the card it has not read",
        )
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS)
        stopped, login = _Host(refuse_after=2), _Host()
        _run_main(home, argv, stopped, refresh=_refresh_stub())
        c2, e2, r2 = _run_main(home, argv, login, refresh=_refresh_stub())
        checks.equal((e2, c2, r2), (None, 0, 0), "refresh finished and sweep stopped: the login run asks for no new refresh")
        checks.ok(bool(login.asked), "it still resumes the sweep that stopped: the host is asked again")
        checks.equal(_archived_skus(), sorted(["OLD1"] + SWEEP_SKUS), "and the resumed sweep completes the archive")
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        c1, e1, r1 = _run_main(home, argv, _Host(), refresh=_refresh_stub(ok=False))
        c2, e2, r2 = _run_main(home, argv, _Host(), refresh=_refresh_stub())
        checks.equal((e1, c1, r1), (None, 1, 1), "a refresh that failed ends its run with exit 1")
        checks.equal((e2, c2, r2), (None, 0, 1), "the next run that day refreshes again: a failed refresh is not a finished one")


def check_manual_price_refresh_still_refreshes_after_the_day_finished(checks: Checks) -> None:
    """`make price-refresh` downloads now, even on a day the installed job finished.

    BEYOND THE OWNER'S LOGIN RULING, FROM THE COMMAND'S OWN DEFINITION: `CLAUDE.md`'s Commands block
    says it is "ONE free download of the live listings now". The once-per-day guard is for the
    unattended start. A guard in front of the manual press would make it log "skipped" and download
    nothing. The argv is read off `make -n`, as `check_installed_job_sweeps_without_reinstall` reads it.
    """
    checks.note("")
    checks.note("DAILY JOB — the manual press refreshes now, whatever the installed job did today")
    manual = _make_price_refresh_argv()
    checks.ok(manual is not None, "`make price-refresh` runs the daily job script, the argv this check reads", str(manual))
    if manual is None:
        return
    with isolated_home() as home:
        _seed_sweep_store(SWEEP_SKUS[:3])
        c1, e1, r1 = _run_main(home, INSTALLED_JOB_ARGV, _Host(), refresh=_refresh_stub())
        checks.equal((e1, c1, r1), (None, 0, 1), "the installed job finishes the day's refresh and sweep")
        c2, e2, r2 = _run_main(home, manual[0], _Host(), manual[1], refresh=_refresh_stub())
        checks.equal((e2, c2, r2), (None, 0, 1), "`make price-refresh` after that refreshes once more")


FENCE_LABEL = (
    "the daily job calls `do_prices_refresh` (the live listings, the catalog, the join, the sales history), "
    "the one archive sweep press (`cli.cmd_pricearchive`, D224 and DEBT32) and the daily TCGCSV read "
    "(`pipeline.dailyprices`, a free public mirror), and reaches nothing else of `server/`, `cli/` or `identify/`: no paid read"
)

_PACKAGES = ("cli", "identify", "pipeline", "server", "store")


def daily_path_reaches(source: str):
    """`(imports are exactly the note writer, the server module, the archive sweep press and the daily
    TCGCSV read, the `pipeline_routes` attributes the script touches)`. A callee other than `do_prices_refresh`
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
    return reached == {
        "pipeline.pricerefresh", "server.pipeline_routes", "cli.cmd_pricearchive", "pipeline.dailyprices",
    }, touched


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
    check_daily_job_empty_sweep_is_ok,
    check_daily_job_reads_daily_prices_after_a_good_refresh,
    check_daily_job_second_run_same_day_skips_sweep,
    check_installed_job_sweeps_without_reinstall,
    check_daily_job_sweep_holds_the_refresh_lock,
    check_installed_job_runs_at_login,
    check_daily_job_login_run_does_the_day_once,
    check_manual_price_refresh_still_refreshes_after_the_day_finished,
    check_price_trends_preload,
    check_trends_press_saves,
    check_older_rejoin_keeps_newer_rows,
)
