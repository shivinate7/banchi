"""T7 group: printings with no stock photo are asked again once a week (owner ruling), in the background, free.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Names the builder follows:

  `match.recheck_no_photo(stock, *, fetch=None, model=None, days=7) -> BuildReport`  one free look: asks again
        only the `no_photo` rows of the index whose `vec.at` is more than `days` days old (never a whole set,
        never an `ok` row), by the same fetch `build_index` uses. A row that now has a photo is fingerprinted
        (status `ok`, a vector). A row that still has none gets `at` set to now, so it waits another week.
  `match.index_stamp()`  also changes when a printing gains a fingerprint, so `sweep.tried()` empties and
        cards tried before are tried again. It is unchanged by a look that gained nothing.
  `pipeline_routes.recheck_stock_photos(*, stock=None, fetch=None, model=None) -> bool`  the guarded look:
        calls `match.recheck_no_photo` only under `_auto_setup_allowed`, with the runtime importable, the model
        file present and no Prepare running. True when it looked. `stock_setup_loop` calls it once per look.
  No new stored field: `vec.at` is the last-asked time.

Nothing downloads: the stock catalogue, the photo fetch and the embedder are fakes.
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
    """The catalogue lists the same URLs the index holds."""

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
    check_recheck_guards,
)
