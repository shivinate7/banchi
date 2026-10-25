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
        (Red before the fix: `unread_targets` compared set NAMES only.) A new printing with no photo (no URL, or a
        404) is work once and not after one Prepare, which keeps a row for it. A held set whose list raises is no work
        and hides no other set's work.

Nothing downloads: the stock catalog, the photo fetch and the embedder are fakes.
"""

from __future__ import annotations

from unittest import mock

from harness.tests import Checks
from harness.tests.t7.auto_setup import SWITCH, _Child, _env, _Popen, _runtime, _Stock
from harness.tests.t7.common import isolated_home, quiet
from harness.tests.t7.photo_recheck import _Embedder, _model, _png, _stamp
from identify import match
from pipeline import games, pricehistory, stockimages
from pipeline.stockimages import CatalogProduct
from server import pipeline_routes

GAME, SET = "riftbound", "Radiance"


class _Listing(_Stock):
    """A tcgcsv-shaped stock whose Riftbound sets list `count` printings (`extra`: other sets, name -> count); `count`
    can grow between looks. `urls` replaces printing `i`'s URL ("" is a listing with no image). A set named in
    `broken` raises when its list is read."""

    def __init__(self, count, extra=None, urls=None, broken=()):
        self.count, self.extra, self.urls, self.broken = count, extra or {}, urls or {}, set(broken)

    def _sizes(self):
        return {SET: self.count, **self.extra}

    def catalog_sets(self, game):
        return [(name, 7 + i) for i, name in enumerate(self._sizes())] if game == GAME else []

    def catalog_products(self, game, set_name):
        if game != GAME or set_name not in self._sizes():
            return None
        if set_name in self.broken:
            raise RuntimeError("the catalogue list could not be read")
        tag = "" if set_name == SET else f"{set_name}-"
        return [CatalogProduct(f"{tag}p{i}", f"Card {i}", f"{i:03d}", "", self.urls.get(i, f"{tag}u{i}"))
                for i in range(1, self._sizes()[set_name] + 1)], 0


def _missing(*gone):
    """A photo fetch that answers 404 for the URLs in `gone` and a picture for every other."""
    asked = []

    def fetch(url):
        asked.append(url)
        return (None, "http_404") if url in gone else (_png(), None)

    fetch.asked = asked
    return fetch


def _build(stock, fetch=None):
    """One Prepare's index build over the stock's own targets, with the embedder and the photo fetch faked."""
    fetch = fetch or _missing()
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


def check_new_printing_with_no_photo_is_work_once(checks: Checks) -> None:
    checks.note("")
    checks.note("NEW PRINTINGS — a new printing with no photo is work once, and a Prepare that finds none ends it")
    with isolated_home():
        stock = _Listing(4)
        _build(stock)
        stock.count, stock.urls = 6, {5: "", 6: "u6"}  # one listed with no image, one whose URL answers 404
        checks.equal(match.unread_targets(stock, []), [(GAME, SET)], "two new printings, neither with a photo: the set is work")
        report, asked = _build(stock, _missing("u6"))
        checks.equal((report.embedded, report.no_image, asked), (0, 2, ["u6"]), "the Prepare reads neither and asks the CDN for the 404 one only")
        rows = _rows()
        checks.equal((rows["p5"][0], rows["p6"][0]), (match.S_NO_URL, match.S_NO_PHOTO), "and keeps a row for each, so the guard reads their names")
        checks.equal(match.unread_targets(stock, []), [], "after that one Prepare the set is no work")
        checks.equal(_spawned(stock), 0, "so the background look does not start another")


def check_one_unreadable_list_does_not_hide_the_rest(checks: Checks) -> None:
    checks.note("")
    checks.note("NEW PRINTINGS — a held set whose product list cannot be read does not hide another set's work")
    with isolated_home():
        stock = _Listing(4, extra={"Origins": 2})
        _build(stock)
        stock.extra, stock.broken = {"Origins": 3}, {SET}
        try:
            got = match.unread_targets(stock, [])
        except Exception as exc:  # noqa: BLE001
            got = f"raised {type(exc).__name__}"
        checks.equal(got, [(GAME, "Origins")], "Origins gained a printing and Radiance's list raises: only Origins is work")
        checks.equal(_spawned(stock), 1, "and the background look still starts a Prepare")


CHECKS = (
    check_build_reads_only_the_new_printings,
    check_product_list_is_not_cached_forever,
    check_auto_start_counts_new_printings_as_work,
    check_new_printing_with_no_photo_is_work_once,
    check_one_unreadable_list_does_not_hide_the_rest,
)
