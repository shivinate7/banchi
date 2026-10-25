"""T7 group: a set the catalogue lists MORE printings of than the index holds gets the new ones read.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Measured on the owner's store: 84 Radiance
(Riftbound) photos held, 245 listed today, and a `match prepare` refresh read 0 new. The set was read once; the
printings added since never entered the pool.

What the cases pin (no name is the builder's to follow; each reads only `match.build_index`,
`match.unread_targets` and `pipeline_routes.ensure_stock_setup`, which exist):

  `match.build_index`  a set that lists N printings, then N+M: the second look reads exactly the M new ones, asks the
        CDN for none of the N, and rewrites none of the N rows. (Green on main: the builder already does this.)
  `pipeline.stockimages.StockImages.catalog_products`  re-reads its product list once `TCGCSV_TTL_SECONDS` has
        passed, so the list is not cached forever. (Green on main: the list lives one hour.)
  `match.unread_targets` / `pipeline_routes.ensure_stock_setup`  a set the index holds but the catalogue now lists
        more of counts as work, so the background check starts a Prepare. A set whose catalogue count matches what
        the index holds is no work, and one Prepare that reads the new printings leaves nothing for the next look.
        (Red on main: `unread_targets` compares set NAMES only.)

Nothing downloads: the stock catalog, the photo fetch and the embedder are fakes.
"""

from __future__ import annotations

from unittest import mock

from harness.tests import Checks
from harness.tests.t7.auto_setup import SWITCH, _Child, _env, _Popen, _runtime, _Stock
from harness.tests.t7.common import isolated_home, quiet
from harness.tests.t7.photo_recheck import _Embedder, _fetcher, _model, _stamp
from identify import match
from pipeline import games, pricehistory, stockimages
from pipeline.stockimages import CatalogProduct
from server import pipeline_routes

GAME, SET = "riftbound", "Radiance"


class _Listing(_Stock):
    """A tcgcsv-shaped stock whose one Riftbound set lists `count` printings; `count` can grow between looks."""

    def __init__(self, count):
        self.count = count

    def catalog_sets(self, game):
        return [(SET, 7)] if game == GAME else []

    def catalog_products(self, game, set_name):
        if (game, set_name) != (GAME, SET):
            return None
        return [CatalogProduct(f"p{i}", f"Card {i}", f"{i:03d}", "", f"u{i}") for i in range(1, self.count + 1)], 0


def _build(stock, fetch=None):
    """One Prepare's index build over the stock's own targets, with the embedder and the photo fetch faked."""
    fetch = fetch or _fetcher({f"u{i}" for i in range(1, 1000)})
    with mock.patch.object(match, "_session", lambda *_a, **_k: _Embedder()), quiet(), match.Index() as index:
        report = match.build_index(index, match.targets_for(stock, []), stock, model=_model(), fetch=fetch)
    return report, fetch.asked


def _rows():
    with match.Index() as index:
        return {r[0]: r[1:] for r in index.db.execute("select product_id, status, at, vec from vec order by product_id")}


def _age_rows():
    """Date every held row 30 days back, so a rewrite shows as a new `at`."""
    with match.Index() as index:
        index.db.execute("update vec set at=?", (_stamp(30),))
        index.db.commit()


def check_build_reads_only_the_new_printings(checks: Checks) -> None:
    checks.note("")
    checks.note("NEW PRINTINGS — a set that grows from 4 to 6 printings: the second look reads the 2 new ones only")
    with isolated_home():
        stock = _Listing(4)
        first, asked = _build(stock)
        checks.equal((first.embedded, first.skipped, sorted(asked)), (4, 0, ["u1", "u2", "u3", "u4"]), "first look reads all 4")
        _age_rows()
        before = _rows()
        stock.count = 6
        second, asked = _build(stock)
        checks.equal((second.embedded, second.skipped, sorted(asked)), (2, 4, ["u5", "u6"]),
                     "the second look reads exactly the 2 new printings and skips the 4 held")
        after = _rows()
        checks.equal(sorted(after), [f"p{i}" for i in range(1, 7)], "and the index holds all 6")
        checks.ok(all(after[p] == before[p] for p in before), "and none of the 4 held rows is rewritten (status, date, vector)")
        with match.Index() as index:
            checks.equal(index.db.execute("select numbered from sets where game=? and set_name=?", (GAME, SET)).fetchone()[0], 6,
                         "and the set row counts the 6 printings")


def check_product_list_is_not_cached_forever(checks: Checks) -> None:
    checks.note("")
    checks.note("NEW PRINTINGS — the real product list is re-read once its hour is up")
    listed = [3]

    def mirror(url):
        if url.endswith("/categories"):
            return {"results": [{"categoryId": 89, "name": games.get(GAME)["product_line"]}]}
        if url.endswith("/89/groups"):
            return {"results": [{"groupId": 7, "name": SET}]}
        return {"results": [
            {"productId": i, "name": f"Card {i}", "imageUrl": f"u{i}", "extendedData": [{"name": "Number", "value": f"{i:03d}"}]}
            for i in range(1, listed[0] + 1)
        ]}

    with isolated_home():
        cache = match.index_path().parent / "market"

        def read(count_at):
            market = pricehistory.Market(cache_dir=cache, fetcher=mirror, courtesy_delay=0, now=lambda: count_at)
            return len(stockimages.StockImages(market=market).catalog_products(GAME, SET)[0])

        start = 1_000_000.0
        checks.equal(read(start), 3, "first read lists 3")
        listed[0] = 5
        checks.equal(read(start + stockimages.TCGCSV_TTL_SECONDS - 60), 3, "control: inside the hour the cached 3 are served")
        checks.equal(read(start + stockimages.TCGCSV_TTL_SECONDS + 60), 5, "past the hour the list is read again and shows 5")


def _spawned(stock) -> int:
    """How many Prepares one background look starts, with the model present and Popen faked."""
    _Popen.calls = []
    with _env(**{SWITCH: "on"}), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: True), mock.patch.object(
        pipeline_routes.subprocess, "Popen", lambda argv, *_a, **_k: (_Popen.calls.append(list(argv)), _Child(999_999))[1]
    ), mock.patch.object(pipeline_routes, "_prepare_pid", lambda: None), quiet():
        pipeline_routes.ensure_stock_setup(stock=stock)
    return len(_Popen.calls)


def check_auto_start_counts_new_printings_as_work(checks: Checks) -> None:
    checks.note("")
    checks.note("NEW PRINTINGS — a held set that gained printings is work for the background check")
    with isolated_home():
        stock = _Listing(4)
        _build(stock)
        checks.equal(match.unread_targets(stock, []), [], "control: a held set that lists what the index holds is no work")
        checks.equal(_spawned(stock), 0, "control: so the background look starts no Prepare")
        stock.count = 6
        checks.equal(match.unread_targets(stock, []), [(GAME, SET)], "the catalogue lists 6 and the index holds 4: the set is a target")
        checks.equal(_spawned(stock), 1, "and the background look starts one Prepare")
        _build(stock)
        checks.equal(match.unread_targets(stock, []), [], "once that Prepare has read the 2, the set is no work again")
        checks.equal(_spawned(stock), 0, "and the next look starts none")


CHECKS = (
    check_build_reads_only_the_new_printings,
    check_product_list_is_not_cached_forever,
    check_auto_start_counts_new_printings_as_work,
)
