#!/usr/bin/env python3
"""`pipeline/rosterholdings.py`, proved against fixtures built in this file (D324).

Protects: The roster value report keeps only TCG purchases, lets no counterparty field out, joins on folded set and name keys, values a line only from one unambiguous Near Mint SKU, and files every kept line in exactly one bucket.
Governs: D324, D247

NO STORE ON DISK. NO NETWORK. The roster is a CSV string behind `io.StringIO`. The store side is
a list of `SkuRow` and a `PriceArchive` built from `Bucket` objects in memory, the same way
`scripts/holdings-selftest.py` builds its archive. Every name, set and id below is invented.

THE SPEC FIXES THE ENTRY POINTS AND LEAVES THE OUTPUT SHAPES OPEN. THIS FILE PINS THEM, AND
THE BUILDER MEETS THESE NAMES, NOT A GUESS. Only what the cases below read is pinned:

  read_roster(fileobj)              -> a roster object. It is the `lines` argument of
                                       `build_roster_report` and carries both of:
      .lines                          the kept lines, in file order. Each has `.product_id`,
                                       `.quantity` (int-like) and `.paid` (money-like).
      .excluded                       a mapping, reason -> row count. Reasons: `sale`,
                                       `not_tcg`, `canceled`.
  build_roster_report(lines, skus, archive, product_ids_priced) -> RosterReport.
      `skus` is a list of `SkuRow` (the roster module's own, six fields). `condition` holds the
      whole store cell (`Near Mint Holofoil`) and `printing` its suffix, or `None` for plain
      Near Mint. `product_ids_priced` is a set of ints, because `Bucket.product_id` is an int.
      The roster's id is a CSV string, so the conversion is part of what case 6 pins.
  RosterReport
      .excluded                       the roster's `excluded` mapping, carried through.
      .base_lines                     the count of kept lines (the coverage denominator).
      .priced                         one row per priced product id: `.product_id`, `.lines`,
                                       `.units`, `.paid`, `.market_each`, `.market_total`.
      .unpriced                       a mapping, reason -> line count. Reasons: `no_price`,
                                       `printing`.
      .ambiguous                      one row per product id: `.product_id`, `.lines`.
      .unmatched                      one row per product id: `.product_id`, `.lines`, `.units`.
      .store_side                     the product ids (a collection) of unmatched or ambiguous
                                       lines whose id is in `product_ids_priced`.
      .price_date                     the newest bucket start used, `str()` of it `YYYY-MM-DD`.
      .render()                       the report text. The spec names no renderer; this is the
                                       one method, and `str(report)` is not pinned.
  `read_roster` raises `ValueError`, naming the row, on a kept row whose `Total Amount` is
  blank, whose `Quantity` is zero or negative, or that is too short to hold its columns. An
  excluded row is never parsed for either. A product whose SKUs are all `Unopened` is priced
  from its `Unopened` SKU's month market, for any finish.
  Not pinned: `gain` (the spec does not say dollars or percent), the order and wording of
  report sections 2 to 9, and the `(P%)` format. Money compares as `Decimal(str(value))`, ids
  as `str(value)`, so `Decimal` against `str` and `int` against `str` both pass.

TWO MUTATION ARMS ARE INCLUDED, ON `CLAUDE.md`'s OWN RULE: A GUARD IS TRUSTED ONLY ONCE IT HAS
BEEN SEEN TO FAIL ON THE DEFECT IT GUARDS. Each one defeats the guard by rebinding the one name
that matters in `pipeline.rosterholdings` (the two folds, then the finish pick), reruns a case's
input and requires the defeat to show. If a mutant does not change the answer, the arm's `ok`
fails and this script exits non-zero.

PATH GATED (D247): `make rosterholdings-selftest`, wired into `make check` and `make ci-check`
through `scripts/guard-scope.py`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
import types
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import cmd_holdingsroster  # noqa: E402
from harness.tests.home import isolated_home, run_folder  # noqa: E402
from pipeline import rosterholdings  # noqa: E402
from pipeline.rosterholdings import (  # noqa: E402
    RosterReport,
    SkuRow,
    build_roster_report,
    read_roster,
)
from store.pricearchive import RANGE_WIDTH_DAYS, Bucket, PriceArchive  # noqa: E402
from store.session import Store  # noqa: E402
from store.skus import SkuRow as StoreSkuRow  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            print(f"         {detail}")


# --------------------------------------------------------------------------- the roster side

HEADER = [
    "Type", "Vendor", "Shipping Status", "Vendor Product Id", "Set Name", "Product Name",
    "Condition", "Finish", "Quantity", "Total Amount",
    "Party", "Account", "Order Id", "Url",
]
# Four columns the report must never carry. Every row of every roster below holds all four.
MARKERS = ("PARTYMARK", "ACCTMARK", "ORDMARK", "URLMARK")

SET_FROST = "Frostmere Rift: Tide Edition"
SET_CINDER = "Cinder Hollow"

EMBER = {"pid": 9001, "set": SET_FROST, "name": "Ember Wisp"}
FOX = {"pid": 9002, "set": SET_CINDER, "name": "Brindle Fox, Elder"}  # a quoted comma in the CSV
WREN = {"pid": 9004, "set": SET_CINDER, "name": "Wren Archivist"}  # two products under one key
LANTERN = {"pid": 9005, "set": SET_CINDER, "name": "Ashen Lantern"}  # no Near Mint month price
SPRITE = {"pid": 9006, "set": SET_CINDER, "name": "Tide Sprite"}  # two priced Near Mint foils
COURIER = {"pid": 9007, "set": SET_CINDER, "name": "Moss Courier"}  # one priced of two foils
HERALD = {"pid": 9008, "set": SET_CINDER, "name": "Gale Herald"}  # holo printings, not for non-foil
PHANTOM = {"pid": 9100, "set": SET_CINDER, "name": "Phantom Quill"}  # not in the store
ALMANAC = {"pid": 9101, "set": SET_CINDER, "name": "Lost Almanac"}  # not in the store
NEARMISS = {"pid": 9102, "set": SET_FROST, "name": "Ember Wisps"}  # one letter off EMBER
SEALED = {"pid": 9009, "set": SET_CINDER, "name": "Cinder Hollow Booster Box"}  # only an Unopened SKU
GHOST = {"pid": 9014, "set": SET_CINDER, "name": "Ghost Page"}  # not in the store, id priced by it

# The roster spells the same two products differently from the store: case, runs of space,
# punctuation in the set label, and a trailing " - 012/100"-style number on the name.
EMBER_SPELLED = {**EMBER, "set": "frostmere rift - tide edition", "name": "  ember   WISP - 012/100"}
FOX_SPELLED = {**FOX, "set": "Cinder  Hollow", "name": "brindle fox,  elder - 7/50"}

ALL_NAMES = ("Ember Wisp", "Brindle Fox", "Wren Archivist", "Ashen Lantern", "Tide Sprite",
             "Moss Courier", "Gale Herald", "Phantom Quill", "Lost Almanac", "Ghost Page",
             "Frostmere", "Cinder Hollow")


def line(product, *, finish="non-foil", qty=1, total="1.00", **over) -> dict:
    """One roster row. Defaults make it a kept row: a TCG purchase that is not canceled."""
    row = {
        "Type": "purchase", "Vendor": "TCG", "Shipping Status": "delivered",
        "Vendor Product Id": str(product["pid"]), "Set Name": product["set"],
        "Product Name": product["name"], "Condition": "Near Mint", "Finish": finish,
        "Quantity": str(qty), "Total Amount": total,
        "Party": "PARTYMARK-Aldous Quill", "Account": "ACCTMARK-4471",
        "Order Id": "ORDMARK-0001-Z", "Url": "https://shop.invalid/URLMARK/o/1",
    }
    row.update(over)
    return row


def roster_csv(*rows: dict) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def read(*rows: dict):
    return read_roster(io.StringIO(roster_csv(*rows)))


# ---------------------------------------------------------------------------- the store side


def _bucket(sku: str, pid: int, range_: str, start: str, market) -> Bucket:
    return Bucket(
        sku=sku, product_id=pid, range=range_, width_days=RANGE_WIDTH_DAYS[range_],
        start=start, market=market, quantity=1, transactions=1, low=market, high=market, at=0,
    )


def world():
    """The store: `(skus, archive)`. Each product below is built for one case.

    EMBER has a Near Mint non-foil with an older and a newer `month` bucket and a still newer
    `quarter` bucket (the range filter), a Near Mint Foil, and a Lightly Played with a market
    (the condition filter). WREN is two products (different `number`) under one key, both
    priced. LANTERN's only Near Mint SKU has no `month` bucket at all. SPRITE has two priced
    Near Mint foils; COURIER has two, one of them priced. Both are spelled with a capital-F
    `Foil`, so no reading of "keeps a SKU with Foil" can split them. HERALD has a plain Near
    Mint SKU and two holofoil printings, all priced: the spec says non-foil drops the
    `Holofoil` and `Reverse Holofoil` printings."""
    skus, buckets = [], {}

    def add(key, product, number, condition, printing, pid, *marks):
        skus.append(SkuRow(key, product["set"], product["name"], number, condition, printing))
        for range_, start, market in marks:
            buckets[f"{key}:{range_}:{start}"] = _bucket(key, pid, range_, start, market)

    add("EMBER-NM", EMBER, "012/100", "Near Mint", None, 9001,
        ("month", "2026-08-01", "4.00"), ("month", "2026-08-02", "5.00"),
        ("quarter", "2026-08-09", "99.00"))
    add("EMBER-NMF", EMBER, "012/100", "Near Mint Foil", "Foil", 9001,
        ("month", "2026-08-02", "20.00"))
    add("EMBER-LP", EMBER, "012/100", "Lightly Played", None, 9001,
        ("month", "2026-08-02", "3.00"))
    add("FOX-NM", FOX, "007/050", "Near Mint", None, 9002, ("month", "2026-08-02", "2.50"))
    add("WREN-A-NM", WREN, "021/050", "Near Mint", None, 9014, ("month", "2026-08-02", "1.10"))
    add("WREN-B-NM", WREN, "071/050", "Near Mint", None, 9015, ("month", "2026-08-02", "30.00"))
    add("LANTERN-NM", LANTERN, "030/050", "Near Mint", None, 9005,
        ("quarter", "2026-08-09", "9.99"))
    add("LANTERN-LP", LANTERN, "030/050", "Lightly Played", None, 9005,
        ("month", "2026-08-02", "1.00"))
    add("SPRITE-NMF", SPRITE, "040/050", "Near Mint Foil", "Foil", 9006,
        ("month", "2026-08-02", "6.00"))
    add("SPRITE-NMF1", SPRITE, "040/050", "Near Mint 1st Edition Foil", "1st Edition Foil", 9006,
        ("month", "2026-08-02", "8.00"))
    add("COURIER-NMF", COURIER, "050/050", "Near Mint Foil", "Foil", 9007,
        ("month", "2026-08-02", "6.00"))
    add("COURIER-NMF1", COURIER, "050/050", "Near Mint 1st Edition Foil", "1st Edition Foil", 9007)
    add("HERALD-NM", HERALD, "060/050", "Near Mint", None, 9008, ("month", "2026-08-02", "2.00"))
    add("HERALD-NMH", HERALD, "060/050", "Near Mint Holofoil", "Holofoil", 9008,
        ("month", "2026-08-02", "9.00"))
    add("HERALD-NMR", HERALD, "060/050", "Near Mint Reverse Holofoil", "Reverse Holofoil", 9008,
        ("month", "2026-08-02", "11.00"))
    add("BOX-U", SEALED, "", "Unopened", None, 9009, ("month", "2026-08-02", "45.00"))

    archive = PriceArchive()
    archive.upsert(buckets)
    return skus, archive


def report_for(*rows: dict, ids=()):
    """`(roster, report)` for a roster of `rows` against the shared store fixture."""
    skus, archive = world()
    roster = read(*rows)
    return roster, build_roster_report(roster, skus, archive, set(ids))


# ------------------------------------------------------------------------------- readers


def D(value) -> Decimal:
    return Decimal(str(value))


def by_pid(rows) -> dict:
    return {str(r.product_id): r for r in rows}


def pids(rows) -> set:
    return {str(r.product_id) for r in rows}


def texts(obj, _depth=0):
    """Every string reachable from `obj`, plus its `repr` at each level, so a counterparty
    value cannot hide in a nested field whatever the builder names it."""
    if _depth > 6:
        return
    if isinstance(obj, str):
        yield obj
        return
    yield repr(obj)
    if isinstance(obj, dict):
        children = [*obj.keys(), *obj.values()]
    elif isinstance(obj, (list, tuple, set, frozenset)):
        children = list(obj)
    elif hasattr(obj, "__dict__"):
        children = list(vars(obj).values())
    else:
        children = []
    for child in children:
        yield from texts(child, _depth + 1)


# --------------------------------------------------------------------------------- cases


def test_read_keeps_tcg_purchases_only() -> None:
    canceled = {"Shipping Status": "canceled"}
    roster = read(
        line(EMBER, qty=3, total="12.00"),
        line(FOX, qty=2, total="7.50"),  # a quoted comma: `split(",")` shifts every column
        line(SPRITE, qty=1, total="3.00", **{"Shipping Status": "shipped"}),
        line(WREN, Type="sale"),
        line(LANTERN, Type="sale"),
        line(COURIER, Vendor="Other Shop"),
        line(PHANTOM, **canceled),
        line(ALMANAC, **canceled),
        line(NEARMISS, **canceled),
    )
    kept = roster.lines
    ok(len(kept) == 3, "only the three TCG purchases that are not canceled are kept", str(len(kept)))
    ok([str(k.product_id) for k in kept] == ["9001", "9002", "9006"],
       "kept lines hold the product ids, in file order", str([k.product_id for k in kept]))
    ok([int(k.quantity) for k in kept] == [3, 2, 1], "kept quantities are right, comma row included",
       str([k.quantity for k in kept]))
    ok([D(k.paid) for k in kept] == [D("12.00"), D("7.50"), D("3.00")],
       "kept paid amounts are right, comma row included", str([k.paid for k in kept]))
    ok(roster.excluded.get("sale") == 2, "two sale rows counted as sale", str(roster.excluded))
    ok(roster.excluded.get("not_tcg") == 1, "one other-vendor row counted as not_tcg",
       str(roster.excluded))
    ok(roster.excluded.get("canceled") == 3, "three canceled rows counted as canceled",
       str(roster.excluded))
    _roster, report = report_for(line(EMBER), line(WREN, Type="sale"))
    ok(isinstance(report, RosterReport), "build_roster_report returns a RosterReport")
    ok(report.excluded.get("sale") == 1, "the report carries the read's excluded counts",
       str(report.excluded))


def raised(text: str):
    """The exception `read_roster` raises on a roster text, or `None`."""
    try:
        read_roster(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001 - the cases compare the class
        return exc
    return None


def test_read_refuses_unreadable_kept_rows() -> None:
    for label, row in (
        ("a blank Total Amount", line(EMBER, total="")),
        ("a zero Quantity", line(EMBER, qty=0)),
        ("a negative Quantity", line(EMBER, qty=-2)),
    ):
        exc = raised(roster_csv(row))
        ok(isinstance(exc, ValueError), f"a kept row with {label} raises ValueError, never a default",
           repr(exc))
    exc = raised(roster_csv(
        line(WREN, Type="sale", total="", qty=0),
        line(LANTERN, total="", qty=0, **{"Shipping Status": "canceled"}),
        line(COURIER, Vendor="Other Shop", total="", qty=-1)))
    ok(exc is None, "an excluded row is never parsed for amount or quantity, so a blank one is no error",
       repr(exc))
    # Ten good rows first, so the short row's file line (12) and row number (11) are not
    # numbers an error message carries by accident.
    exc = raised(roster_csv(*[line(EMBER)] * 10) + "purchase,TCG,delivered,9777\n")
    ok(isinstance(exc, ValueError), "a short kept row raises ValueError, not AttributeError", repr(exc))
    ok(exc is not None and any(token in str(exc) for token in ("9777", "11", "12")),
       "the error names the short row: its file line, its row number or its product id", str(exc))


def test_privacy() -> None:
    rows = [
        line(EMBER, qty=2, total="6.00"), line(FOX, qty=1, total="2.00"),
        line(PHANTOM, qty=1, total="1.00"), line(WREN, qty=1, total="1.00"),
        line(LANTERN, Type="sale"), line(SPRITE, **{"Shipping Status": "canceled"}),
        line(COURIER, Vendor="Other Shop"),
    ]
    ok(all(m in roster_csv(*rows) for m in MARKERS), "fixture: every marker is in the CSV")
    roster, report = report_for(*rows, ids={9101})
    ok(len(roster.lines) > 0, "fixture: the privacy roster keeps lines, so the checks are not vacuous")
    for name, subject in (("a kept line", roster.lines), ("the read result", roster),
                          ("the report", report), ("the report text", report.render())):
        blob = "\n".join(texts(subject))
        leaked = [m for m in MARKERS if m in blob]
        ok(not leaked, f"no seller, account, order id or url value reaches {name}", str(leaked))
    text = report.render().lower()
    named = [n for n in ALL_NAMES if n.lower() in text]
    ok(not named, "the report text names no product or set (ids, counts and money only)", str(named))


def test_name_fold() -> None:
    _roster, report = report_for(
        line(EMBER_SPELLED, qty=1, total="4.00"), line(FOX_SPELLED, qty=1, total="2.00"))
    priced = by_pid(report.priced)
    ok({"9001", "9002"} <= set(priced),
       "case, spacing, punctuation and a trailing number do not stop a match", str(sorted(priced)))
    ok(len(report.unmatched) == 0 and len(report.ambiguous) == 0,
       "a folded match is neither unmatched nor ambiguous",
       f"{len(report.unmatched)} unmatched, {len(report.ambiguous)} ambiguous")


def test_ambiguous() -> None:
    _roster, report = report_for(line(WREN, qty=2, total="4.00"))
    ok(pids(report.ambiguous) == {"9004"}, "two products under one key are ambiguous, listed by id",
       str(pids(report.ambiguous)))
    row = by_pid(report.ambiguous).get("9004")
    ok(row is not None and row.lines == 1, "the ambiguous row counts its line")
    ok(len(report.priced) == 0, "an ambiguous line is never valued, though both products have prices",
       str(pids(report.priced)))
    ok(len(report.unmatched) == 0 and sum(report.unpriced.values()) == 0,
       "an ambiguous line is in no other bucket")


def test_unmatched_roster_side() -> None:
    _roster, report = report_for(
        line(PHANTOM, qty=2, total="5.00"), line(PHANTOM, qty=3, total="6.00"),
        line(NEARMISS, qty=1, total="1.00"))
    rows = by_pid(report.unmatched)
    ok(set(rows) == {"9100", "9102"},
       "a product the store lacks, and a name one letter off, are unmatched by id", str(sorted(rows)))
    row = rows.get("9100")
    ok(row is not None and row.lines == 2 and int(row.units) == 5,
       "the unmatched row sums its lines and its units",
       str(row and (row.lines, row.units)))
    ok(len(report.priced) == 0, "an unmatched line is never valued")


def test_unmatched_store_side() -> None:
    _roster, report = report_for(
        line(ALMANAC), line(PHANTOM), line(WREN), line(EMBER),
        ids={9101, 9004, 9001})  # ints: `Bucket.product_id` is an int, the CSV cell a string
    listed = {str(p) for p in report.store_side}
    ok("9101" in listed, "an unmatched line whose id the store prices is listed store-side",
       str(sorted(listed)))
    ok("9004" in listed, "an ambiguous line whose id the store prices is listed store-side",
       str(sorted(listed)))
    ok("9100" not in listed, "an unmatched line whose id the store does not price is not listed",
       str(sorted(listed)))
    ok("9001" not in listed, "a matched line is never listed store-side", str(sorted(listed)))
    ok("9101" in pids(report.unmatched), "the store-side line is still an unmatched line")


def test_printing_pick() -> None:
    _roster, report = report_for(line(EMBER, qty=2, total="6.00"), line(EMBER, qty=1, total="2.50"))
    row = by_pid(report.priced).get("9001")
    ok(row is not None, "a non-foil line on a matched product is priced")
    if row is not None:
        ok(D(row.market_each) == D("5.00"),
           "non-foil takes the Near Mint non-foil SKU's newest month market, not an older bucket, "
           "a newer quarter bucket, Lightly Played or the foil", str(row.market_each))
        ok(row.lines == 2 and int(row.units) == 3, "two lines of one id make one row of 3 units",
           f"{row.lines} lines, {row.units} units")
        ok(D(row.paid) == D("8.50"), "paid is the sum of the lines", str(row.paid))
        ok(D(row.market_total) == D("15.00"), "market total is market each times units",
           str(row.market_total))
    ok(str(report.price_date) == "2026-08-02", "the price date is the newest bucket start used",
       str(report.price_date))
    ok(sum(report.unpriced.values()) == 0, "a priced line is not also unpriced")

    _roster, report = report_for(line(EMBER, finish="foil", qty=1, total="9.00"))
    row = by_pid(report.priced).get("9001")
    ok(row is not None and D(row.market_each) == D("20.00"),
       "foil takes the Near Mint Foil SKU's market", str(row and row.market_each))

    _roster, report = report_for(line(HERALD, qty=1, total="1.50"))
    row = by_pid(report.priced).get("9008")
    ok(row is not None and D(row.market_each) == D("2.00"),
       "non-foil drops the Holofoil and Reverse Holofoil printings, so the plain SKU prices alone",
       str(row and row.market_each) + " " + str(dict(report.unpriced)))

    _roster, report = report_for(line(COURIER, finish="holofoil", qty=2, total="9.00"))
    row = by_pid(report.priced).get("9007")
    ok(row is not None and D(row.market_each) == D("6.00"),
       "any other finish keeps the foil SKUs, and the one with a market sets the price",
       str(row and row.market_each))

    _roster, report = report_for(line(LANTERN))
    ok(report.unpriced.get("no_price") == 1 and len(report.priced) == 0,
       "no Near Mint SKU with a month market: unpriced, no_price", str(dict(report.unpriced)))

    _roster, report = report_for(line(SPRITE, finish="foil"))
    ok(report.unpriced.get("printing") == 1 and len(report.priced) == 0,
       "two kept SKUs with a market: unpriced, printing", str(dict(report.unpriced)))


def test_sealed_product_prices_from_its_unopened_sku() -> None:
    """A product whose SKUs are all Unopened has no Near Mint SKU, and the finish means nothing
    to it. Its one Unopened SKU with a month market prices the line, for any finish."""
    for finish in ("non-foil", "foil", ""):
        _roster, report = report_for(line(SEALED, finish=finish, qty=2, total="80.00"))
        row = by_pid(report.priced).get("9009")
        ok(row is not None and D(row.market_each) == D("45.00") and D(row.market_total) == D("90.00"),
           f"a sealed line with finish {finish!r} is priced at its Unopened SKU's month market",
           str(dict(report.unpriced)) if row is None else f"{row.market_each} each, {row.market_total} total")
        ok(sum(report.unpriced.values()) == 0, f"a sealed line with finish {finish!r} is not unpriced",
           str(dict(report.unpriced)))


def fingerprint(db_path: Path) -> dict:
    """Size, mtime and SHA-256 of the store file and of its WAL when the WAL holds anything.
    SQLite makes an empty WAL on a read-only open of a WAL store; that is no write."""
    found = {}
    for suffix in ("", "-wal"):
        path = Path(str(db_path) + suffix)
        if path.exists() and (not suffix or path.stat().st_size):
            stat = path.stat()
            found[suffix] = (stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
    return found


def test_verb_reads_a_store_and_writes_nothing() -> None:
    """`cli.cmd_holdingsroster.run` over a real store file, on a throwaway home. The store holds
    `world()`'s SKUs and buckets, so the verb's text must equal the in-memory report's."""
    skus, archive = world()
    ids = {bucket.product_id for bucket in archive.entries.values()}
    rows = (line(EMBER, qty=2, total="6.00"), line(FOX), line(WREN),
            line(PHANTOM, qty=2, total="5.00"), line(GHOST))
    _roster, report = report_for(*rows, ids=ids)
    with run_folder() as folder, isolated_home(folder) as home:
        store = Store()
        with store.write() as snapshot:
            for sku in skus:
                snapshot.skus.fold(sku.key, StoreSkuRow(
                    product_line="synthetic", set_name=sku.set_name, product_name=sku.product_name,
                    number=sku.number, rarity="", condition=sku.condition, grade=None,
                    printing=sku.printing, first_seen=1, last_seen=1, source="selftest", raw={}))
            snapshot.archive.upsert(dict(archive.entries))
        roster_path = home / "roster.csv"
        roster_path.write_text(roster_csv(*rows), encoding="utf-8")
        before = fingerprint(store.db_path)
        said: list = []
        code = cmd_holdingsroster.run(
            types.SimpleNamespace(csv=str(roster_path), store=str(store.db_path)), said.append)
        after = fingerprint(store.db_path)
    text = "\n".join(said)
    ok(code == 0, "the verb exits 0 on a readable roster and a store", str(code))
    ok(text.splitlines()[:2] == ["units received unknown", "units sold unknown"],
       "the verb's output opens with the two unknowns", text[:120])
    ok(text == report.render(), "the verb reads the store's SKUs, buckets and priced ids as the "
       "in-memory report does", text[:600])
    ok(bool(before) and before == after, "the verb leaves the store file's bytes and mtime unchanged",
       f"{before} -> {after}")


def roster_of_every_bucket() -> tuple:
    """Seven kept lines: two priced, two unpriced, one ambiguous, two unmatched. Two more rows
    (a sale, a canceled purchase) are excluded and must not move any count."""
    return report_for(
        line(EMBER, qty=1, total="4.00"), line(FOX, qty=1, total="2.00"),
        line(WREN), line(LANTERN), line(SPRITE, finish="foil"),
        line(PHANTOM, qty=2, total="5.00"), line(PHANTOM, qty=3, total="6.00"),
        line(COURIER, Type="sale"), line(ALMANAC, **{"Shipping Status": "canceled"}),
    )


def test_every_line_in_one_bucket() -> None:
    roster, report = roster_of_every_bucket()
    kept = len(roster.lines)
    priced = sum(r.lines for r in report.priced)
    unpriced = sum(report.unpriced.values())
    ambiguous = sum(r.lines for r in report.ambiguous)
    unmatched = sum(r.lines for r in report.unmatched)
    ok(kept == 7, "fixture: seven lines kept", str(kept))
    ok(report.base_lines == kept, "base_lines is the kept line count", str(report.base_lines))
    ok((priced, unpriced, ambiguous, unmatched) == (2, 2, 1, 2),
       "lines fall into priced, unpriced, ambiguous, unmatched as built",
       str((priced, unpriced, ambiguous, unmatched)))
    ok(priced + unpriced + ambiguous + unmatched == kept,
       "priced + unpriced + ambiguous + unmatched equals the kept lines, none dropped, none twice")
    ok(not (pids(report.priced) & pids(report.ambiguous))
       and not (pids(report.priced) & pids(report.unmatched))
       and not (pids(report.ambiguous) & pids(report.unmatched)),
       "no product id is in two buckets")


def test_report_text() -> None:
    _roster, report = roster_of_every_bucket()
    lines = report.render().splitlines()
    ok(lines[:2] == ["units received unknown", "units sold unknown"],
       "the first two lines are the two unknowns, exactly", str(lines[:2]))
    ok("priced 2 of 7 lines" in report.render(), "the coverage line names the priced and base counts",
       report.render())


def mutation_fold_bypassed() -> None:
    """Raw names instead of the folds: a roster spelling the product differently matches nothing."""
    saved = rosterholdings.normalize_set, rosterholdings.name_index_key
    rosterholdings.normalize_set = rosterholdings.name_index_key = lambda text: str(text)
    try:
        _roster, report = report_for(
            line(EMBER_SPELLED, qty=1, total="4.00"), line(FOX_SPELLED, qty=1, total="2.00"))
        ok(not {"9001", "9002"} <= pids(report.priced) and len(report.unmatched) == 2,
           "MUTATION: raw names defeat the folded match, as expected")
    finally:
        rosterholdings.normalize_set, rosterholdings.name_index_key = saved


def mutation_printing_pick_skipped() -> None:
    """Every SKU agrees with every finish: EMBER has two priced Near Mint SKUs, so unpriced `printing`."""
    saved = rosterholdings._finish_agrees
    rosterholdings._finish_agrees = lambda finish, condition, printing: True
    try:
        _roster, report = report_for(line(EMBER, qty=2, total="6.00"))
        ok(by_pid(report.priced).get("9001") is None and report.unpriced.get("printing") == 1,
           "MUTATION: skipping the printing pick defeats the price, as expected")
    finally:
        rosterholdings._finish_agrees = saved


def main() -> int:
    print("pipeline/rosterholdings.py:")
    for case in (
        test_read_keeps_tcg_purchases_only, test_read_refuses_unreadable_kept_rows,
        test_privacy, test_name_fold, test_ambiguous,
        test_unmatched_roster_side, test_unmatched_store_side, test_printing_pick,
        test_sealed_product_prices_from_its_unopened_sku, test_verb_reads_a_store_and_writes_nothing,
        test_every_line_in_one_bucket, test_report_text,
    ):
        try:
            case()
        except Exception as exc:  # noqa: BLE001 - one broken case must not hide the rest
            ok(False, f"{case.__name__} raised", repr(exc))
    print("mutation arms (each proves the real guard above would have caught it):")
    mutation_fold_bypassed()
    mutation_printing_pick_skipped()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
