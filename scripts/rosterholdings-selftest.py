#!/usr/bin/env python3
"""`pipeline/rosterholdings.py`, proved against fixtures built in this file (D324).

Protects: The roster value report keeps only TCG purchases, lets no counterparty field out, joins a line to its product by the roster's product id against the price archive's, reports what the folded set and name cross-check prices that the id join does not, values a line only from one Near Mint SKU, and files every kept line in exactly one bucket.
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
  build_roster_report(lines, skus, archive) -> RosterReport. Three parameters, no more.
      `skus` is a list of `SkuRow` (the roster module's own, six fields). `condition` holds the
      whole store cell (`Near Mint Holofoil`) and `printing` its suffix, or `None` for plain
      Near Mint. The crosswalk comes from `archive` alone: each `price_history` row's
      `product_id` (an int) maps to its `sku`. The roster's id is a CSV string, so the
      conversion is the builder's. Id `0` is never a key. An id no archive row carries, or one
      that is blank or not a number, is `unmatched`. An archive SKU with no `skus` row is
      `unpriced`, reason `no_sku_row`. There is no ambiguous bucket.
  RosterReport
      .excluded                       the roster's `excluded` mapping, carried through.
      .base_lines                     the count of kept lines (the coverage denominator).
      .priced                         one row per priced product id: `.product_id`, `.lines`,
                                       `.units`, `.paid`, `.market_each`, `.market_total`.
      .unpriced                       a mapping, reason -> line count. Reasons: `no_price`,
                                       `printing`, `no_sku_row`.
      .unmatched                      one row per product id: `.product_id`, `.lines`, `.units`.
      .store_side                     the roster product ids (a collection) of lines the
                                       folded set and name join prices that the id join leaves
                                       unmatched or unpriced. A line the id join prices is
                                       never in it.
      .price_date                     the newest bucket start used, `str()` of it `YYYY-MM-DD`.
      .render()                       the report text. The spec names no renderer; this is the
                                       one method, and `str(report)` is not pinned.
  `read_roster` raises `ValueError`, naming the row, on a kept row whose `Total Amount` is
  blank, whose `Quantity` is zero or negative, or that is too short to hold its columns. An
  excluded row is never parsed for either. A product whose SKUs are all `Unopened` is priced
  from its `Unopened` SKU's month market, for any finish.
  Not pinned: `gain` (the spec does not say dollars or percent), the order and wording of
  the report sections, and the `(P%)` format. Also not pinned: an id whose archive SKUs are
  only partly in `skus`, and the cross-check on a name key that two products share. Money
  compares as `Decimal(str(value))`, ids as `str(value)`, so `Decimal` against `str` and `int`
  against `str` both pass.

TWO MUTATION ARMS ARE INCLUDED, ON `CLAUDE.md`'s OWN RULE: A GUARD IS TRUSTED ONLY ONCE IT HAS
BEEN SEEN TO FAIL ON THE DEFECT IT GUARDS. Each one defeats the guard by rebinding the one name
that matters in `pipeline.rosterholdings` (the two folds of the cross-check, then the finish pick), reruns a case's
input and requires the defeat to show. If a mutant does not change the answer, the arm's `ok`
fails and this script exits non-zero.

PATH GATED (D247): `make rosterholdings-selftest`, wired into `make check` and `make ci-check`
through `scripts/guard-scope.py`.
"""

from __future__ import annotations

import csv
import hashlib
import inspect
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
WREN = {"pid": 9004, "set": SET_CINDER, "name": "Wren Archivist"}  # two products under one name key
WREN_TWIN = {**WREN, "pid": 9003}  # the other product under that name key, with its own id
LANTERN = {"pid": 9005, "set": SET_CINDER, "name": "Ashen Lantern"}  # no Near Mint month price
SPRITE = {"pid": 9006, "set": SET_CINDER, "name": "Tide Sprite"}  # two priced Near Mint foils
COURIER = {"pid": 9007, "set": SET_CINDER, "name": "Moss Courier"}  # one priced of two foils
HERALD = {"pid": 9008, "set": SET_CINDER, "name": "Gale Herald"}  # holo printings, not for non-foil
PHANTOM = {"pid": 9100, "set": SET_CINDER, "name": "Phantom Quill"}  # no archive row, no SKU
ALMANAC = {"pid": 9101, "set": SET_CINDER, "name": "Lost Almanac"}  # archive row, no `skus` row
NEARMISS = {"pid": 9102, "set": SET_FROST, "name": "Ember Wisps"}  # one letter off EMBER, no archive row
SEALED = {"pid": 9009, "set": SET_CINDER, "name": "Cinder Hollow Booster Box"}  # only an Unopened SKU
# The roster names this product one way and the store another, under the same id: the id join
# prices it and the name join cannot.
GHOST = {"pid": 9014, "set": SET_CINDER, "name": "Ghost Page"}
GHOST_STORE = {**GHOST, "name": "Spectral Folio"}
# The reverse: set and name agree with a SKU, the id does not. The archive carries the product
# under id 9201, so the name join prices the line and the id join finds no archive row.
DRIFT = {"pid": 9200, "set": SET_CINDER, "name": "Drift Warden"}
# The id is in the archive but only on a SKU with no `skus` row, while the set and name agree
# with another SKU (id 9301) that is priced: the id join leaves it unpriced, the name join prices it.
STRAY = {"pid": 9300, "set": SET_CINDER, "name": "Stray Cantor"}
# A SKU the archive files under id 0 (a row that had no product id). Its name agrees with the
# roster line, so a join that let 0 be a key would price the line.
NULLID = {"pid": 0, "set": SET_CINDER, "name": "Null Sigil"}
# Only a quarter bucket carries this id, and the roster's name folds to nothing in the store.
QUARTER = {"pid": 9400, "set": SET_CINDER, "name": "Faint Ledger"}
QUARTER_STORE = {**QUARTER, "name": "Quarterly Tome"}

# The roster spells the same products differently from the store: case, runs of space,
# punctuation in the set label, and a trailing " - 012/100"-style number on the name.
EMBER_SPELLED = {**EMBER, "set": "frostmere rift - tide edition", "name": "  ember   WISP - 012/100"}
FOX_SPELLED = {**FOX, "set": "Cinder  Hollow", "name": "brindle fox,  elder - 7/50"}
DRIFT_SPELLED = {**DRIFT, "set": "cinder   hollow", "name": "  DRIFT   warden - 80/50"}

ALL_NAMES = ("Ember Wisp", "Brindle Fox", "Wren Archivist", "Ashen Lantern", "Tide Sprite",
             "Moss Courier", "Gale Herald", "Phantom Quill", "Lost Almanac", "Ghost Page",
             "Spectral Folio", "Drift Warden", "Stray Cantor", "Null Sigil", "Faint Ledger",
             "Quarterly Tome", "Frostmere", "Cinder Hollow")


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
    (the condition filter). WREN and WREN_TWIN are two products (different `number`, different
    id) under one name key, both priced. LANTERN's only Near Mint SKU has no `month` bucket at
    all. SPRITE has two priced Near Mint foils; COURIER has two, one of them priced. Both are
    spelled with a capital-F `Foil`, so no reading of "keeps a SKU with Foil" can split them.
    HERALD has a plain Near Mint SKU and two holofoil printings, all priced: the spec says
    non-foil drops the `Holofoil` and `Reverse Holofoil` printings.

    The id join's cases: GHOST_STORE is the store's own name for the id GHOST carries. ALMANAC
    and STRAY's id 9300 are archive rows with no `skus` row (`row=False`). DRIFT is archived
    under 9201 and STRAY's named SKU under 9301, so the roster's ids 9200 and 9300 differ from
    the id the name join would find. NULLID is archived under id 0. QUARTER_STORE has a
    `quarter` bucket only. PHANTOM and NEARMISS are in neither table."""
    skus, buckets = [], {}

    def add(key, product, number, condition, printing, pid, *marks, row=True):
        if row:
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
    add("WREN-A-NM", WREN, "021/050", "Near Mint", None, 9004, ("month", "2026-08-02", "1.10"))
    add("WREN-B-NM", WREN_TWIN, "071/050", "Near Mint", None, 9003, ("month", "2026-08-02", "30.00"))
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
    add("GHOST-NM", GHOST_STORE, "070/050", "Near Mint", None, 9014, ("month", "2026-08-02", "3.75"))
    add("ALMANAC-NM", ALMANAC, "", "Near Mint", None, 9101, ("month", "2026-08-02", "8.00"),
        row=False)
    add("DRIFT-NM", DRIFT, "080/050", "Near Mint", None, 9201, ("month", "2026-08-02", "3.00"))
    add("STRAY-NM", STRAY, "090/050", "Near Mint", None, 9301, ("month", "2026-08-02", "7.00"))
    add("STRAY-X", STRAY, "", "Near Mint", None, 9300, ("month", "2026-08-02", "5.00"), row=False)
    add("NULL-NM", NULLID, "100/050", "Near Mint", None, 0, ("month", "2026-08-02", "2.00"))
    add("QUARTER-NM", QUARTER_STORE, "110/050", "Near Mint", None, 9400,
        ("quarter", "2026-08-09", "6.00"))

    archive = PriceArchive()
    archive.upsert(buckets)
    return skus, archive


def report_for(*rows: dict):
    """`(roster, report)` for a roster of `rows` against the shared store fixture."""
    skus, archive = world()
    roster = read(*rows)
    return roster, build_roster_report(roster, skus, archive)


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


def test_read_names_the_file_line() -> None:
    for label, total in (("a lone $", "$"), ("a lone comma", ","), ("a negative", "-1.00"),
                         ("a negative in dollars", "$-2.50"), ("NaN", "NaN")):
        exc = raised(roster_csv(line(EMBER, total=total)))
        ok(isinstance(exc, ValueError) and str(exc).startswith("roster line 2:"),
           f"an amount of {label} is refused at file line 2", repr(exc))
    # A quoted name that holds a newline makes the first row span file lines 2 and 3.
    exc = raised(roster_csv(line({**EMBER, "name": "Ember\nWisp"}), line(FOX, total="")))
    ok(isinstance(exc, ValueError) and str(exc).startswith("roster line 4:"),
       "the file line is counted across a quoted newline", repr(exc))


def test_verb_refuses_an_unreadable_roster() -> None:
    """The roster is read before the store is opened, so an empty file stands in for the store."""
    with run_folder() as folder:
        roster_path = folder / "roster.csv"
        roster_path.write_text(roster_csv(line(EMBER, total="$")), encoding="utf-8")
        store_path = folder / "store.sqlite"
        store_path.write_bytes(b"")
        said: list = []
        try:
            code = cmd_holdingsroster.run(
                types.SimpleNamespace(csv=str(roster_path), store=str(store_path)), said.append)
        except Exception as exc:  # noqa: BLE001 - a traceback is a failed case, not the end of the run
            code = repr(exc)
    ok(code == 1 and len(said) == 1 and said[0].startswith("roster line 2:"),
       "the verb says one message that starts with the file line, and returns 1", f"{code} {said}")


def test_privacy() -> None:
    rows = [
        line(EMBER, qty=2, total="6.00"), line(FOX, qty=1, total="2.00"),
        line(PHANTOM, qty=1, total="1.00"), line(WREN, qty=1, total="1.00"),
        line(LANTERN, Type="sale"), line(SPRITE, **{"Shipping Status": "canceled"}),
        line(COURIER, Vendor="Other Shop"),
        line(DRIFT), line(STRAY), line(ALMANAC), line(GHOST),  # fill the store-side and no_sku_row lines
    ]
    ok(all(m in roster_csv(*rows) for m in MARKERS), "fixture: every marker is in the CSV")
    roster, report = report_for(*rows)
    ok(len(roster.lines) > 0, "fixture: the privacy roster keeps lines, so the checks are not vacuous")
    for name, subject in (("a kept line", roster.lines), ("the read result", roster),
                          ("the report", report), ("the report text", report.render())):
        blob = "\n".join(texts(subject))
        leaked = [m for m in MARKERS if m in blob]
        ok(not leaked, f"no seller, account, order id or url value reaches {name}", str(leaked))
    text = report.render().lower()
    named = [n for n in ALL_NAMES if n.lower() in text]
    ok(not named, "the report text names no product or set (ids, counts and money only)", str(named))


def test_signature() -> None:
    """The crosswalk comes from the archive, so the report needs no id set of its own."""
    params = list(inspect.signature(build_roster_report).parameters)
    ok(len(params) == 3, "build_roster_report takes the roster, the SKUs and the archive, and nothing else",
       str(params))


def test_name_fold() -> None:
    """Re-pointed: the folded set and name join is the cross-check now, not the join. A line is
    priced by its id whatever its spelling; the fold decides only what the store side lists."""
    _roster, report = report_for(
        line(EMBER_SPELLED, qty=1, total="4.00"), line(FOX_SPELLED, qty=1, total="2.00"),
        line(DRIFT_SPELLED, qty=1, total="3.00"))
    priced = by_pid(report.priced)
    ok({"9001", "9002"} <= set(priced),
       "case, spacing, punctuation and a trailing number do not stop an id match", str(sorted(priced)))
    ok(pids(report.unmatched) == {"9200"}, "only the line whose id the archive lacks is unmatched",
       str(pids(report.unmatched)))
    listed = {str(p) for p in report.store_side}
    ok(listed == {"9200"},
       "the cross-check folds the roster's spelling like the SKU side: the spelled line with an "
       "unknown id is listed store-side, the two the id join prices are not", str(sorted(listed)))


def test_same_name_two_ids_price_by_id() -> None:
    """Re-pointed from the ambiguous case: one product id is one product, so two products that
    share a name key are two priced rows, each at its own price."""
    _roster, report = report_for(line(WREN, qty=2, total="4.00"), line(WREN_TWIN, qty=1, total="25.00"))
    priced = by_pid(report.priced)
    ok(set(priced) == {"9003", "9004"}, "both products under one name key are priced, each by its id",
       str(sorted(priced)))
    a, b = priced.get("9004"), priced.get("9003")
    ok(a is not None and D(a.market_each) == D("1.10") and D(a.market_total) == D("2.20"),
       "the first product is valued at its own SKU's market", str(a and (a.market_each, a.market_total)))
    ok(b is not None and D(b.market_each) == D("30.00") and D(b.market_total) == D("30.00"),
       "the second product is valued at its own SKU's market", str(b and (b.market_each, b.market_total)))
    ok(len(report.unmatched) == 0 and sum(report.unpriced.values()) == 0,
       "neither line is in another bucket")


def test_no_ambiguous_section() -> None:
    """One product id is one product, so the report has nothing to call ambiguous."""
    _roster, report = report_for(line(WREN), line(WREN_TWIN), line(DRIFT), line(PHANTOM))
    text = report.render()
    ok("ambiguous" not in text.lower(), "the report text has no Ambiguous section or mention", text)
    ok(not hasattr(report, "ambiguous"), "the report has no ambiguous bucket")


def test_id_join_prices_a_renamed_product() -> None:
    """The roster's set and name fold to no SKU; the archive holds the id on a SKU the store names
    differently. The id join prices the line, and it is not store-side (the name join cannot)."""
    _roster, report = report_for(line(GHOST, qty=2, total="6.00"))
    row = by_pid(report.priced).get("9014")
    ok(row is not None and D(row.market_each) == D("3.75") and D(row.market_total) == D("7.50"),
       "a line whose set and name match no SKU is priced by its product id",
       str(row and (row.market_each, row.market_total)))
    ok(len(report.unmatched) == 0 and sum(report.unpriced.values()) == 0,
       "the renamed product's line is in no other bucket")
    ok(len(report.store_side) == 0, "a line the id join prices is never listed store-side",
       str(list(report.store_side)))


def test_archive_sku_without_a_skus_row() -> None:
    """The archive carries the id, on a SKU the `skus` table lacks: the line is unpriced, with its own
    reason, and not unmatched."""
    _roster, report = report_for(line(ALMANAC, qty=2, total="9.00"))
    ok(report.unpriced.get("no_sku_row") == 1, "an archive SKU with no skus row is unpriced, no_sku_row",
       str(dict(report.unpriced)))
    ok(sum(report.unpriced.values()) == 1, "the line is counted once in the unpriced reasons",
       str(dict(report.unpriced)))
    ok(len(report.unmatched) == 0 and len(report.priced) == 0,
       "a no_sku_row line is neither unmatched nor priced", f"{pids(report.unmatched)} {pids(report.priced)}")


def test_crosswalk_reads_every_range() -> None:
    """The id maps to the SKU keys of every archive row that carries it, any range. A product
    with a quarter bucket only has its SKU, no month market: unpriced no_price, not unmatched."""
    _roster, report = report_for(line(QUARTER))
    ok(report.unpriced.get("no_price") == 1 and len(report.unmatched) == 0 and len(report.priced) == 0,
       "an id carried by a quarter bucket only reaches its SKU: unpriced, no_price",
       f"{dict(report.unpriced)} unmatched {pids(report.unmatched)}")


def test_unmatched_roster_side() -> None:
    """Re-pointed: unmatched is now 'no archive row carries the id', whatever the set and name say.
    DRIFT's set and name fold to a priced SKU, which the old name join would have priced."""
    _roster, report = report_for(
        line(PHANTOM, qty=2, total="5.00"), line(PHANTOM, qty=3, total="6.00"),
        line(NEARMISS, qty=1, total="1.00"), line(DRIFT, qty=4, total="9.00"))
    rows = by_pid(report.unmatched)
    ok(set(rows) == {"9100", "9102", "9200"},
       "an id no archive row carries is unmatched, whether or not its set and name match a stocked product",
       str(sorted(rows)))
    row = rows.get("9100")
    ok(row is not None and row.lines == 2 and int(row.units) == 5,
       "the unmatched row sums its lines and its units",
       str(row and (row.lines, row.units)))
    drift = rows.get("9200")
    ok(drift is not None and drift.lines == 1 and int(drift.units) == 4,
       "the line a name join would price counts under its roster id", str(drift and (drift.lines, drift.units)))
    ok(len(report.priced) == 0, "an unmatched line is never valued", str(pids(report.priced)))
    # A blank or non-numeric id cannot be a key. Both stay in the report, filed unmatched.
    _roster, report = report_for(
        line({**EMBER, "pid": ""}), line({**EMBER, "pid": "n/a"}, qty=2, total="2.00"))
    ok(sum(r.lines for r in report.unmatched) == 2 and len(report.priced) == 0,
       "a blank id and a non-numeric id are unmatched, never an error and never priced by name",
       f"{[(r.product_id, r.lines) for r in report.unmatched]} priced {pids(report.priced)}")


def test_id_zero_is_never_a_key() -> None:
    """The archive files a row it had no product id for under 0. NULLID's SKU is in `skus`, priced,
    and its name matches the roster line, so a join that let 0 be a key would price this line."""
    _roster, report = report_for(line(NULLID, qty=2, total="4.00"))
    ok(pids(report.unmatched) == {"0"}, "a roster line with id 0 is unmatched", str(pids(report.unmatched)))
    ok(len(report.priced) == 0 and sum(report.unpriced.values()) == 0,
       "id 0 reaches no SKU, so the line is neither priced nor unpriced",
       f"{pids(report.priced)} {dict(report.unpriced)}")


def test_unmatched_store_side() -> None:
    """Re-pointed: store side was 'unmatched or ambiguous lines whose id the store prices' (an id set
    the caller passed). It is now the lines the name join prices that the id join leaves unmatched
    or unpriced. DRIFT: the archive has no row for the roster's id. STRAY: the archive has the id,
    on a SKU with no skus row."""
    _roster, report = report_for(
        line(DRIFT), line(STRAY), line(EMBER), line(PHANTOM), line(ALMANAC), line(NEARMISS))
    listed = {str(p) for p in report.store_side}
    ok("9200" in listed, "a line the name join prices and the id join leaves unmatched is listed",
       str(sorted(listed)))
    ok("9300" in listed, "a line the name join prices and the id join leaves unpriced is listed",
       str(sorted(listed)))
    ok(listed == {"9200", "9300"},
       "nothing else is listed: not the line both joins price, nor a line the name join cannot price",
       str(sorted(listed)))
    ok("9200" in pids(report.unmatched), "the store-side unmatched line is still an unmatched line")
    ok(report.unpriced.get("no_sku_row") == 2,
       "the store-side unpriced line is still an unpriced line (STRAY and ALMANAC)",
       str(dict(report.unpriced)))


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
    # DRIFT (store side), ALMANAC (no_sku_row) and GHOST (priced by id alone) make the verb's text
    # depend on the archive's product ids, so the text can only match if the verb reads them.
    rows = (line(EMBER, qty=2, total="6.00"), line(FOX), line(WREN),
            line(PHANTOM, qty=2, total="5.00"), line(GHOST), line(DRIFT), line(ALMANAC))
    _roster, report = report_for(*rows)
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
    ok(text == report.render(), "the verb reads the store's SKUs and the archive's buckets and product ids "
       "as the in-memory report does", text[:600])
    ok(bool(before) and before == after, "the verb leaves the store file's bytes and mtime unchanged",
       f"{before} -> {after}")


def roster_of_every_bucket() -> tuple:
    """Ten kept lines: four priced (EMBER, FOX, WREN, GHOST), three unpriced (LANTERN no_price,
    SPRITE printing, ALMANAC no_sku_row), three unmatched (PHANTOM twice, DRIFT). Two more rows (a
    sale, a canceled purchase) are excluded and must not move any count. The name join alone
    would price EMBER, FOX and DRIFT: three, not four, and not the same three."""
    return report_for(
        line(EMBER, qty=1, total="4.00"), line(FOX, qty=1, total="2.00"),
        line(WREN), line(GHOST), line(LANTERN), line(SPRITE, finish="foil"), line(ALMANAC),
        line(PHANTOM, qty=2, total="5.00"), line(PHANTOM, qty=3, total="6.00"), line(DRIFT),
        line(COURIER, Type="sale"), line(ALMANAC, **{"Shipping Status": "canceled"}),
    )


def test_every_line_in_one_bucket() -> None:
    """Re-pointed: three buckets (priced, unpriced, unmatched). The ambiguous one is gone."""
    roster, report = roster_of_every_bucket()
    kept = len(roster.lines)
    priced = sum(r.lines for r in report.priced)
    unpriced = sum(report.unpriced.values())
    unmatched = sum(r.lines for r in report.unmatched)
    ok(kept == 10, "fixture: ten lines kept", str(kept))
    ok(report.base_lines == kept, "base_lines is the kept line count", str(report.base_lines))
    ok((priced, unpriced, unmatched) == (4, 3, 3),
       "lines fall into priced, unpriced, unmatched as built", str((priced, unpriced, unmatched)))
    ok(priced + unpriced + unmatched == kept,
       "priced + unpriced + unmatched equals the kept lines, none dropped, none twice")
    ok(not (pids(report.priced) & pids(report.unmatched)), "no product id is in two buckets")


def test_report_text() -> None:
    _roster, report = roster_of_every_bucket()
    lines = report.render().splitlines()
    ok(lines[:2] == ["units received unknown", "units sold unknown"],
       "the first two lines are the two unknowns, exactly", str(lines[:2]))
    ok("priced 4 of 10 lines" in report.render(),
       "the coverage line names the lines the id join priced and the base count", report.render())


def mutation_fold_bypassed() -> None:
    """Raw names instead of the folds: the cross-check no longer reads a differently spelled roster
    line as the stocked product, so the spelled line leaves the store side. The id join is untouched."""
    saved = rosterholdings.normalize_set, rosterholdings.name_index_key
    rosterholdings.normalize_set = rosterholdings.name_index_key = lambda text: str(text)
    try:
        _roster, report = report_for(
            line(EMBER_SPELLED, qty=1, total="4.00"), line(FOX_SPELLED, qty=1, total="2.00"),
            line(DRIFT_SPELLED, qty=1, total="3.00"))
        ok(len(report.store_side) == 0 and {"9001", "9002"} <= pids(report.priced),
           "MUTATION: raw names defeat the folded cross-check and leave the id join alone, as expected",
           str(list(report.store_side)))
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
        test_read_names_the_file_line, test_verb_refuses_an_unreadable_roster,
        test_privacy, test_signature, test_name_fold, test_same_name_two_ids_price_by_id,
        test_no_ambiguous_section, test_id_join_prices_a_renamed_product,
        test_archive_sku_without_a_skus_row, test_crosswalk_reads_every_range,
        test_unmatched_roster_side, test_id_zero_is_never_a_key, test_unmatched_store_side,
        test_printing_pick,
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
