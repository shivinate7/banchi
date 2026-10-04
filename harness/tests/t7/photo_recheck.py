"""T7 group: printings with no stock photo are asked again once a week (owner ruling), in the background, free.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Names the builder follows:

  `match.recheck_no_photo(stock, *, fetch=None, model=None, days=7) -> BuildReport`  one free look: asks again
        only the `no_photo` rows of the index whose `vec.at` is more than `days` days old (never a whole set,
        never an `ok` row), by the same fetch `build_index` uses. A row that now has a photo is fingerprinted
        (status `ok`, a vector). A row that still has none gets `at` set to now, so it waits another week.
  The same look covers `no_url` rows older than `days`: one `stock.catalog_products` read per set that holds
        any (none for a set with no due row), then fetch and fingerprint each URL that appeared. A row still
        without a URL gets `at` set to now.
  `match.index_stamp()`  also changes when a printing gains a fingerprint, so `sweep.tried()` empties and
        cards tried before are tried again. It is unchanged by a look that gained nothing.
  `pipeline_routes.recheck_stock_photos(*, stock=None, fetch=None, model=None) -> bool`  the guarded look:
        calls `match.recheck_no_photo` only under `_auto_setup_allowed`, with the runtime importable, the model
        file present and no Prepare running. True when it looked. `stock_setup_loop` calls it once per look.
  No new stored field: `vec.at` is the last-asked time.

Nothing downloads: the stock catalog, the photo fetch and the embedder are fakes.
"""

from __future__ import annotations

import io
import time
from unittest import mock

from harness.tests import Checks
from harness.tests.t7.auto_setup import HARNESS, SWITCH, _env, _runtime, _Stock
from harness.tests.t7.common import isolated_home, quiet
from identify import match, sweep
from server import pipeline_routes, ports
from store import files

DAY = 86400


def _stamp(age_days):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_days * DAY))


def _png():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), (120, 30, 30)).save(out, "PNG")
    return out.getvalue()


class _Embedder:
    def run(self, _outputs, feed):
        import numpy as np

        return [np.ones((len(feed["pixels"]), match.DIM), np.float32)]


class _Products(_Stock):
    """The catalog lists the same URLs the index holds."""

    def __init__(self, rows):
        self.rows = rows

    def catalog_products(self, _game, _set_name):
        from pipeline.stockimages import CatalogProduct

        return [CatalogProduct(pid, name, str(i), "10", url) for i, (pid, name, url, _s, _a) in enumerate(self.rows, 1)], 0


def _seed(rows, game="pokemon", set_name="Set A"):
    """rows: (product_id, name, url, status, age in days)."""
    import numpy as np

    with match.Index() as index:
        index.db.execute("insert or replace into sets values(?,?,?,?,?,?,?)", (game, set_name, "vendored", "", len(rows), 0, _stamp(30)))
        for i, (pid, name, url, status, age) in enumerate(rows, 1):
            blob = np.zeros(match.DIM, np.float32).tobytes() if status == match.S_OK else None
            index.db.execute("insert or replace into vec values(?,?,?,?,?,?,?,?,?,?)",
                             (game, set_name, pid, str(i), name, url, status, None if blob else "http_403", blob, _stamp(age)))
        index.db.commit()
    return _Products(rows)


def _row(pid):
    with match.Index() as index:
        return index.db.execute("select status, at from vec where product_id=?", (pid,)).fetchone()


def _fetcher(photo_urls):
    asked = []

    def fetch(url):
        asked.append(url)
        return (_png(), None) if url in photo_urls else (None, "http_403")

    fetch.asked = asked
    return fetch


def _model():
    path = files.home() / "fake-model.onnx"
    path.write_bytes(b"fake")
    return path


def _look(stock, fetch):
    with mock.patch.object(match, "_session", lambda *_a, **_k: _Embedder()), quiet():
        return match.recheck_no_photo(stock, fetch=fetch, model=_model())


def check_weekly_recheck_asks_only_the_old_no_photo(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — one look asks only the printings with no photo, last asked over 7 days ago")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        stock = _seed([
            ("p1", "Okay", "u1", match.S_OK, 30),
            ("p2", "Gains", "u2", match.S_NO_PHOTO, 8),
            ("p3", "Waits", "u3", match.S_NO_PHOTO, 8),
            ("p4", "Fresh", "u4", match.S_NO_PHOTO, 1),
        ])
        fetch = _fetcher({"u2", "u4"})
        _look(stock, fetch)
        checks.equal(sorted(fetch.asked), ["u2", "u3"], "only the old no-photo printings are asked: not the ok one, not the fresh one")
        checks.equal(_row("p2")[0], match.S_OK, "a printing that now has a photo is fingerprinted")
        checks.equal(_row("p3")[0], match.S_NO_PHOTO, "one that still has none stays no_photo")
        checks.equal(_row("p4")[0], match.S_NO_PHOTO, "a fresh one is left alone even with a photo up")
        checks.ok(_row("p3")[1] > _stamp(1), "and the one still without is dated now, so it waits another week")
        again = _fetcher(set())
        _look(stock, again)
        checks.equal(again.asked, [], "a second look at once asks nothing")


def check_recent_check_asks_nothing(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — checked under 7 days ago, nothing is asked")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        stock = _seed([("p1", "A", "u1", match.S_NO_PHOTO, 6), ("p2", "B", "u2", match.S_NO_PHOTO, 0)])
        fetch = _fetcher({"u1", "u2"})
        _look(stock, fetch)
        checks.equal(fetch.asked, [], "no printing checked in the last week is asked again")
        checks.equal((_row("p1")[0], _row("p2")[0]), (match.S_NO_PHOTO, match.S_NO_PHOTO), "and none changes")


def check_gained_photo_is_matchable_and_retried(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — a gained photo is matchable, the look-alike guard lets go, tried cards are tried again")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        stock = _seed([
            ("p1", "Okay", "u1", match.S_OK, 30),
            ("p2", "Gains", "u2", match.S_NO_PHOTO, 8),
            ("p3", "Waits", "u3", match.S_NO_PHOTO, 8),
        ])
        sweep.remember_tried({"1/1": "cap-1"})
        _look(stock, _fetcher(set()))
        checks.equal(sweep.tried(), {"1/1": "cap-1"}, "a look that gains nothing keeps the tried marks")
        with match.Index() as index:
            index.db.execute("update vec set at=? where status=?", (_stamp(8), match.S_NO_PHOTO))
            index.db.commit()
        _look(stock, _fetcher({"u2"}))
        with match.Index() as index:
            pool = index.pool("pokemon", ["Set A"])
        checks.ok("p2" in {r[2] for r in pool.rows}, "the gained printing is in the matchable pool")
        checks.equal(pool.blocked, {match.card_name("Waits")}, "its name leaves the look-alike guard, the other stays")
        checks.equal(sweep.tried(), {}, "a gained fingerprint changes the stamp, so cards tried before are tried again")


class _Catalog(_Stock):
    """A catalog that has grown URLs since the index was built, and counts its reads per set."""

    def __init__(self, listing):
        self.listing, self.reads = listing, []

    def catalog_products(self, _game, set_name):
        from pipeline.stockimages import CatalogProduct

        self.reads.append(set_name)
        return [CatalogProduct(pid, name, str(i), "10", url) for i, (pid, name, url) in enumerate(self.listing[set_name], 1)], 0


def check_no_url_rows_are_reread_once_per_set(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — a no_url printing: one catalog read per set, a new URL is fetched and fingerprinted")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        _seed([("a1", "Okay", "uo", match.S_OK, 30), ("a2", "Gains", "", match.S_NO_URL, 8),
               ("a3", "Waits", "", match.S_NO_URL, 8), ("a4", "AlsoWaits", "", match.S_NO_URL, 8)], set_name="Set A")
        _seed([("b1", "Gains too", "", match.S_NO_URL, 8)], set_name="Set B")
        _seed([("c1", "Fresh", "", match.S_NO_URL, 1)], set_name="Set C")
        stock = _Catalog({
            "Set A": [("a1", "Okay", "uo"), ("a2", "Gains", "ua"), ("a3", "Waits", ""), ("a4", "AlsoWaits", "")],
            "Set B": [("b1", "Gains too", "ub")],
            "Set C": [("c1", "Fresh", "uc")],
        })
        fetch = _fetcher({"ua", "ub", "uc"})
        _look(stock, fetch)
        checks.equal(sorted(stock.reads), ["Set A", "Set B"], "one catalog read per affected set, none for a set checked this week")
        checks.equal(sorted(fetch.asked), ["ua", "ub"], "only the URLs that appeared are fetched")
        checks.equal((_row("a2")[0], _row("b1")[0]), (match.S_OK, match.S_OK), "a printing whose URL appeared is fingerprinted")
        checks.equal((_row("a3")[0], _row("c1")[0]), (match.S_NO_URL, match.S_NO_URL), "one still without a URL, or checked this week, is unchanged")
        checks.ok(_row("a3")[1] > _stamp(1), "and the one still without a URL is dated now, so it waits another week")
        with match.Index() as index:
            pool = index.pool("pokemon", ["Set A"])
        checks.ok("a2" in {r[2] for r in pool.rows}, "the printing is in the matchable pool")
        checks.equal(pool.blocked, {match.card_name("Waits"), match.card_name("AlsoWaits")}, "and its name leaves the look-alike guard")
        again = _Catalog(stock.listing)
        _look(again, _fetcher(set()))
        checks.equal(again.reads, [], "a second look at once reads no catalog")


def check_recheck_holds_no_lock_across_fetches(checks: Checks) -> None:
    import sqlite3
    import threading

    checks.note("")
    checks.note("PHOTO RECHECK — a look mid-fetch does not lock the index: a write from another connection lands inside 1 s")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        stock = _seed([(f"p{i}", f"N{i}", f"u{i}", match.S_NO_PHOTO, 8) for i in range(1, 4)])
        started, release, calls, errors = threading.Event(), threading.Event(), [], []

        def fetch(_url):
            calls.append(1)
            if len(calls) == 1:
                return None, "http_403"  # the first row is answered, so a transaction may open
            started.set()
            release.wait(10)
            return None, "http_403"

        def run():
            try:
                _look(stock, fetch)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        checks.ok(started.wait(10), "the look reaches its second fetch")
        outcome = "written"
        t0 = time.monotonic()
        try:
            db = sqlite3.connect(str(match.index_path()), timeout=1)
            db.execute("insert or replace into meta values('probe','1')")
            db.commit()
            db.close()
        except sqlite3.Error as exc:
            outcome = str(exc)
        took = time.monotonic() - t0
        release.set()
        worker.join(10)
        checks.equal(outcome, "written", "a write on the same fingerprints file succeeds while the look waits on a fetch")
        checks.ok(took < 1.5, "and it does not wait out the look")
        checks.equal(errors, [], "and the look itself ends clean")


class _NoListing(_Catalog):
    def catalog_products(self, _game, set_name):
        self.reads.append(set_name)
        return None


def check_transient_failures_do_not_date_the_row(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — only 403, 404 and 410 date a row for a week; a transient failure is tried at the next look")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    causes = {"u1": "URLError", "u2": "http_503", "u3": "http_500", "u4": "http_403", "u5": "http_404", "u6": "http_410"}
    with isolated_home():
        stock = _seed([(f"p{i}", f"N{i}", f"u{i}", match.S_NO_PHOTO, 8) for i in range(1, 7)])
        before = {f"p{i}": _row(f"p{i}")[1] for i in range(1, 7)}
        _look(stock, lambda url: (None, causes[url]))
        for i in (1, 2, 3):
            checks.equal(_row(f"p{i}")[1], before[f"p{i}"], f"a {causes[f'u{i}']} answer leaves `at` alone, so the next look asks again")
        for i in (4, 5, 6):
            checks.ok(_row(f"p{i}")[1] > _stamp(1), f"a {causes[f'u{i}']} answer dates the row for a week")
    with isolated_home():
        _seed([("a1", "Lost", "", match.S_NO_URL, 8)])
        before = _row("a1")[1]
        fetch = _fetcher(set())
        _look(_NoListing({}), fetch)
        checks.equal((_row("a1")[1], fetch.asked), (before, []), "a set whose catalog read returned nothing leaves its no_url rows undated")
    with isolated_home():
        _seed([("a1", "Lost", "", match.S_NO_URL, 8)])
        _look(_Catalog({"Set A": [("a1", "Lost", "")]}), _fetcher(set()))
        checks.ok(_row("a1")[1] > _stamp(1), "control: a catalog that answers with no URL for it dates the row for a week")


def check_one_pass_is_bounded_oldest_first(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — one pass reads at most RECHECK_ROWS_PER_PASS rows, oldest `at` first")
    cap = getattr(match, "RECHECK_ROWS_PER_PASS", None)
    if getattr(match, "recheck_no_photo", None) is None or not isinstance(cap, int):
        checks.ok(False, "`match.recheck_no_photo` and `match.RECHECK_ROWS_PER_PASS` exist")
        return
    checks.ok(0 < cap < 50, "the cap is a positive int under the 50 rows the case seeds")
    if not 0 < cap < 50:
        return
    with isolated_home():
        stock = _seed([(f"p{i}", f"N{i}", f"u{i}", match.S_NO_PHOTO, 8 + i) for i in range(50)])  # p49 is the oldest
        first = _fetcher(set())
        _look(stock, first)
        checks.equal(len(first.asked), cap, "a pass asks exactly the cap of 50 stale rows")
        checks.equal(sorted(first.asked), sorted(f"u{i}" for i in range(50 - cap, 50)), "and they are the oldest")
        second = _fetcher(set())
        _look(stock, second)
        checks.equal(sorted(second.asked), sorted(f"u{i}" for i in range(max(0, 50 - 2 * cap), 50 - cap)), "the next pass takes the next oldest, so the backlog drains")


def check_transient_rows_retry_in_a_day_not_first_in_line(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — a transient failure waits a day, so the next pass reaches the rows behind it")
    cap = getattr(match, "RECHECK_ROWS_PER_PASS", None)
    if getattr(match, "recheck_no_photo", None) is None or not isinstance(cap, int):
        checks.ok(False, "`match.recheck_no_photo` and `match.RECHECK_ROWS_PER_PASS` exist")
        return
    with isolated_home():
        n = 2 * cap
        stock = _seed([(f"p{i}", f"N{i}", f"u{i}", match.S_NO_PHOTO, 60 - i) for i in range(n)])  # p0 is the oldest
        first = _fetcher(set())
        first_asked = []

        def decode_fails(url):
            first_asked.append(url)
            return (b"not an image", None) if int(url[1:]) < cap else (None, "http_403")

        _look(stock, decode_fails)
        checks.equal(sorted(first_asked), sorted(f"u{i}" for i in range(cap)), "pass 1 asks the oldest rows, and they fail to decode")
        second = _fetcher(set())
        _look(stock, second)
        checks.equal(sorted(second.asked), sorted(f"u{i}" for i in range(cap, n)), "pass 2 asks the rows behind them, not the same ones")
        with match.Index() as index:
            index.db.execute("update vec set at=? where product_id='p0'", (_stamp(2),))
            index.db.commit()
        third = _fetcher(set())
        _look(stock, third)
        checks.ok("u0" in third.asked, "a transient row is asked again once a day has passed")


def check_network_failure_ends_the_pass(checks: Checks) -> None:
    import urllib.error

    checks.note("")
    checks.note("PHOTO RECHECK — a network failure ends the pass at once")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    for label, make in (("a URLError answer", lambda url: (None, "URLError")), ("a timeout answer", lambda url: (None, "timeout")),
                        ("a raised URLError", None)):
        with isolated_home():
            stock = _seed([(f"p{i}", f"N{i}", f"u{i}", match.S_NO_PHOTO, 20 - i) for i in range(5)])
            asked = []

            def fetch(url, make=make):
                asked.append(url)
                if make is None:
                    raise urllib.error.URLError("down")
                return make(url)

            try:
                _look(stock, fetch)
            except urllib.error.URLError:
                pass
            checks.equal(len(asked), 1, f"{label} on the first row: the pass asks exactly 1 row")


def check_ok_row_is_not_overwritten(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — a row that turned ok mid-pass is kept")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    import numpy as np

    with isolated_home():
        stock = _seed([("p1", "Race", "u1", match.S_NO_PHOTO, 8)])

        def fetch(_url):
            with match.Index() as index:
                index.db.execute("update vec set status=?, vec=?, note=null where product_id='p1'", (match.S_OK, np.zeros(match.DIM, np.float32).tobytes()))
                index.db.commit()
            return None, "http_404"

        _look(stock, fetch)
        with match.Index() as index:
            row = index.db.execute("select status, vec is not null from vec where product_id='p1'").fetchone()
        checks.equal(tuple(row), (match.S_OK, 1), "a 404 for a row a Prepare just fingerprinted leaves it ok, with its vector")


def check_pass_record(checks: Checks) -> None:
    import json
    import os

    checks.note("")
    checks.note("PHOTO RECHECK — the pass holds the running record, and its closing write respects another owner")
    if getattr(match, "recheck_no_photo", None) is None:
        checks.ok(False, "`match.recheck_no_photo` exists")
        return
    with isolated_home():
        stock = _seed([("p1", "A", "u1", match.S_NO_PHOTO, 8)])
        seen = []

        def fetch(_url):
            seen.append(match.prepare_pid())
            return None, "http_403"

        _look(stock, fetch)
        checks.ok(bool(seen) and seen[0] is not None, "while the pass runs, `prepare_pid()` is not None, so the sweep's marks are building marks")
        checks.equal(match.prepare_pid(), None, "and after it ends, it is None again")
    with isolated_home():
        stock = _seed([("p1", "A", "u1", match.S_NO_PHOTO, 8)])
        other = os.getpid() + 1

        def fetch(_url):
            match.progress_path().write_text(json.dumps({"state": "running", "pid": other, "phase": "fingerprints"}))
            return None, "http_403"

        _look(stock, fetch)
        record = json.loads(match.progress_path().read_text())
        checks.equal((record.get("state"), record.get("pid")), ("running", other),
                     "a record another process took mid-pass is left alone by the pass's closing write")


def _guarded(env, *, primary=True, runtime=True, model=True, prepare=None):
    """Printings asked by `recheck_stock_photos` under the given guards."""
    with isolated_home():
        stock = _seed([("p1", "Gains", "u1", match.S_NO_PHOTO, 8)])
        fetch = _fetcher({"u1"})
        own = files.home()
        with _env(**env), _runtime(runtime), mock.patch.object(match, "model_ready", lambda *_a, **_k: model), mock.patch.object(
            match, "_session", lambda *_a, **_k: _Embedder()
        ), mock.patch.object(pipeline_routes, "_prepare_pid", lambda: prepare), mock.patch.object(
            ports, "is_primary_checkout", lambda *_a: primary
        ), mock.patch.object(ports, "REPO_ROOT", own), quiet():
            pipeline_routes.recheck_stock_photos(stock=stock, fetch=fetch, model=_model())
        return len(fetch.asked)


def check_recheck_guards(checks: Checks) -> None:
    checks.note("")
    checks.note("PHOTO RECHECK — primary checkout, own store, no harness, runtime, model, one Prepare at a time")
    if getattr(pipeline_routes, "recheck_stock_photos", None) is None:
        checks.ok(False, "`pipeline_routes.recheck_stock_photos` exists")
        return
    for label, want, kwargs in (
        ("primary checkout, own store, nothing set: it looks", 1, {"env": {}}),
        ("a linked worktree never looks", 0, {"env": {}, "primary": False}),
        ("a linked worktree looks when the switch is on", 1, {"env": {SWITCH: "on"}, "primary": False}),
        ("the harness variable set, switch unset: it never looks", 0, {"env": {HARNESS: "1"}}),
        ("CI set, switch unset: it never looks", 0, {"env": {"CI": "1"}}),
        ("runtime missing: it never looks", 0, {"env": {}, "runtime": False}),
        ("model file missing: it never looks", 0, {"env": {}, "model": False}),
        ("a Prepare running: it never looks", 0, {"env": {}, "prepare": 4242}),
    ):
        checks.equal(_guarded(**kwargs), want, label)
    with isolated_home():
        calls = []
        with _env(**{SWITCH: "on"}), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: True), mock.patch.object(
            match, "recheck_no_photo", lambda *a, **k: calls.append(1), create=True
        ), mock.patch.object(pipeline_routes, "_prepare_pid", lambda: None), mock.patch.object(
            pipeline_routes, "_ensure", lambda *_a, **_k: None
        ), quiet():
            pipeline_routes.stock_setup_loop(0.0, stock=_Stock(), sleep=lambda _s: None, max_looks=1)
        checks.equal(len(calls), 1, "one look of the background loop makes one weekly look, with no press")


CHECKS = (
    check_weekly_recheck_asks_only_the_old_no_photo,
    check_recent_check_asks_nothing,
    check_gained_photo_is_matchable_and_retried,
    check_no_url_rows_are_reread_once_per_set,
    check_recheck_holds_no_lock_across_fetches,
    check_transient_failures_do_not_date_the_row,
    check_one_pass_is_bounded_oldest_first,
    check_transient_rows_retry_in_a_day_not_first_in_line,
    check_network_failure_ends_the_pass,
    check_ok_row_is_not_overwritten,
    check_pass_record,
    check_recheck_guards,
)
