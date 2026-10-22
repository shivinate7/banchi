#!/usr/bin/env python3
"""`store/slabs.py`, the three My Slabs tables and their writes, proved against a throwaway
store: no network, no real store, no `~/.banchi`.

Protects: A slab, its daily snapshot and its sales are each stored once, written whole or not at all, and a value Card Ladder did not give stays empty.
Governs: D320, D88

BUILD PLAN STEP 2 (`docs/specs/my-slabs.md`, section 6). The interface of `store/slabs.py` that
this file tests. It follows `store/readings.py` and `store/pricearchive.py`:

    Slabs                a dataclass holding three `Rows` tables, bound into `Snapshot` as
                         `snapshot.slabs` and listed in `Snapshot.tables`, so a `Store.write()`
                         flushes all three in its one transaction (D88).
    D88 tables           `slabs`, `slab_snapshots`, `slab_sales`, each `key` + `payload` + columns.
                         `slab_snapshots` has real columns `cl_value`, `cl_confidence`,
                         `estimated_value`, `estimated_confidence`, `last_sale_price`.
    schema               `db.SCHEMA_VERSION` rises past 14 with an additive step (`_add_slabs`), so
                         the owner's store, stamped 14, gets the tables on its next open.
    GRADERS              the dict `bgs`/`bvg` -> `beckett`, `psa`, `sgc`, `cgc`. `store/` may not
                         import `pipeline/` (D63), so the one constant moves here
                         (`store/numbers.py` is the precedent) and `pipeline/cardladder.py`
                         imports it back: `pipeline.cardladder.GRADERS is store.slabs.GRADERS`.
    Every method below takes the grader as typed (`bgs`, `BGS`, `beckett`) and maps it through
    GRADERS. A cert is text: `"0012345678"` keeps its zeros. A slab is (cert, GRADERS[grader]).
    A day is `"YYYY-MM-DD"`, passed in, never read from a clock. A value is stored and returned
    exactly as given, type and all: money is text (`"238.50"`), `None` means Card Ladder gave none
    and is stored as NULL, never 0 and never filled from the other value.

    Slabs.add(cert, grader, *, profile_id, identity, subgrades, added) -> Slab
        identity: dict of 3.1's label, grade, qualifierType, autographGrade and profile fields.
        subgrades: dict (Beckett) or None. added: the day. A second add of the same slab keeps
        one row and keeps the first `added`.
    Slabs.record_snapshot(cert, grader, day, *, cl_value, cl_confidence, estimated_value,
            estimated_confidence, last_sale_price, last_sale_date, population, gem_rate,
            speed) -> SlabSnapshot
        speed: dict window -> {"velocity", "averagePrice"}, keys as 3.4 names them, kept whole.
        One row per slab per day. A second write that day REPLACES the row, every field.
    Slabs.record_sales(cert, grader, sales) -> None
        sales: list of Card Ladder sale dicts, each with an `id`. Keyed by that id alone: one row
        per sale however many slabs and reads see it. Never deletes. All sales or none: a sale
        without an `id` raises and none of the batch is kept. A sale whose `date` is not text
        (an int, a dict, or no `date` key) raises ValueError before the batch writes anything,
        so no stored row can make `sales_for` raise on its sort.
    Slabs.get(cert, grader) -> Optional[Slab]
    Slabs.list() -> List[Slab]                      same order however the slabs were added
    Slabs.snapshots_for(cert, grader) -> List[SlabSnapshot]   oldest day first; [] if none
    Slabs.sales_for(cert, grader) -> List[Sale]     newest `date` first, ties by `id` descending
                                                    (`Readings.sources_payload`'s rule); [] if none.
                                                    Reads only that slab's sales (see below).
    Slab(cert, grader, profile_id, identity, subgrades, added)
    SlabSnapshot(cert, grader, day, cl_value, cl_confidence, estimated_value,
                 estimated_confidence, last_sale_price, last_sale_date, population, gem_rate, speed)
    Sale(id, date, data)    `data` is the Card Ladder sale dict, verbatim. `date` is its `date`.
    A sale belongs to every slab that read it, so two slabs of one card both list a shared sale.

ONE SLAB'S SALES COST ONE SLAB'S SALES (case 6b). The proof is structural, never a timing: while a
fresh read answers `sales_for`, a trace on its connection logs every statement, and (a) none of
them may have an EXPLAIN QUERY PLAN row that starts with SCAN (every table is reached through a
SEARCH on an index or key; a join's alias is a SCAN too, so no table name is matched), and (b) the
store may parse no more `slab_sales` rows than the slab has sales. A link table from slab to sale id
with an index on its slab column, or any design with the same property, passes. Two controls
run the same two detectors over a full read of every sale and must fire, so a detector gone blind
(a renamed hook, a connection opened before the trace) fails loudly and never reads as green.

Every read below goes through a NEW `Store().read()`, or raw sqlite3 on the file, never the write's
own snapshot: in-memory rows look written even when a table was left out of `Snapshot.tables`.
Each case runs in its own `isolated_home()`, and asserts the store sits inside it first.

In `make check`, never in the git hook: it writes a temp store (D18).
"""

from __future__ import annotations

import gc
import json
import sqlite3
import sys
import traceback
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.tests.home import isolated_home  # noqa: E402
from store import db  # noqa: E402
from store.readings import Reading  # noqa: E402
from store.rows import Rows  # noqa: E402
from store.session import Store  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> bool:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")
    return bool(condition)


def same(label: str, got, want) -> bool:
    return ok(got == want, label, f"got  {got!r}\nwant {want!r}")


# ------------------------------------------------------------------------------ fixtures

TABLES = ("slabs", "slab_snapshots", "slab_sales", "slab_sale_links")
WINDOWS = ("twoWeekData", "oneMonthData", "oneQuarterData", "sixMonthData", "oneYearData")
SNAP_FIELDS = (
    "cl_value", "cl_confidence", "estimated_value", "estimated_confidence",
    "last_sale_price", "last_sale_date", "population", "gem_rate", "speed",
)
VALUE_COLUMNS = ("cl_value", "cl_confidence", "estimated_value", "estimated_confidence", "last_sale_price")

IDENTITY = {
    "label": "2023 Pokemon Obsidian Flames Charizard ex #125 PSA 10",
    "grade": "g10", "qualifierType": None, "autographGrade": None,
    "category": "Pokemon", "year": "2023", "set": "Obsidian Flames",
    "subject": "Charizard ex", "number": "125", "variation": "",
}
SUBGRADES = {"centering": 9.5, "corners": 9.5, "edges": 9, "surface": 9.5}


def speed(base: float) -> dict:
    return {w: {"velocity": base + i, "averagePrice": 100.25 + i} for i, w in enumerate(WINDOWS)}


# Both values differ and so do their confidences: a store that kept only one would show it.
SNAP_A = dict(
    cl_value="262.00", cl_confidence=4, estimated_value="238.50", estimated_confidence=3,
    last_sale_price="116.40", last_sale_date="2026-10-02", population=1250, gem_rate=0.75,
    speed=speed(1.0),
)
# Same day as A. Its estimate is None, so a merge that keeps the old number shows.
SNAP_B = dict(
    cl_value="270.00", cl_confidence=5, estimated_value=None, estimated_confidence=None,
    last_sale_price="120.00", last_sale_date="2026-10-03", population=1251, gem_rate=0.5,
    speed=speed(2.0),
)
SNAP_C = dict(
    cl_value="281.00", cl_confidence=4, estimated_value="250.00", estimated_confidence=4,
    last_sale_price="125.00", last_sale_date="2026-10-04", population=1252, gem_rate=0.25,
    speed=speed(3.0),
)
# A slab with no sale at its grade. Nothing in it is a legitimate 0 or "", so a 0 or "" found in
# the stored row is a value the store made up.
SNAP_NONE = dict(
    cl_value=None, cl_confidence=None, estimated_value=None, estimated_confidence=None,
    last_sale_price=None, last_sale_date=None, population=35, gem_rate=0.5,
    speed={w: {"velocity": None, "averagePrice": None} for w in WINDOWS},
)


def sale(sale_id: str, date: str, price: str = "100.00") -> dict:
    return {
        "id": sale_id, "itemId": "item-" + sale_id, "title": "Charizard ex 125 PSA 10 " + sale_id,
        "seller": "cardshop", "image": "https://img.invalid/" + sale_id + ".jpg",
        "thumbnail": "https://img.invalid/" + sale_id + "-t.jpg", "platform": "ebay",
        "listingType": "auction", "price": price, "date": date,
        "url": "https://sale.invalid/" + sale_id, "grader": "psa", "grade": "g10",
        "memberVerified": False, "cardId": "card-1001",
    }


# ------------------------------------------------------------------------------ the store

HOMES: list = []


@contextmanager
def fresh_home():
    """A temporary store, pushed on `HOMES` so `store()` can prove it is the one in use."""
    with isolated_home() as tmp:
        HOMES.append(Path(tmp).resolve())
        try:
            yield tmp
        finally:
            HOMES.pop()


def store() -> Store:
    """The only way this file opens a store: inside a temporary home, or it stops."""
    if not HOMES or not Store().directory.resolve().is_relative_to(HOMES[-1]):
        raise SystemExit(f"slabs-store-selftest: {Store().directory} is not inside a temporary home; stopping")
    return Store()


def put(fn):
    """`fn(slabs)` inside one `Store().write()` transaction."""
    with store().write() as snap:
        return fn(snap.slabs)


def slabs_now():
    """A fresh lock-free read, never the write's own snapshot."""
    return store().read().slabs


def raw(sql: str, *args):
    gc.collect()
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def counts() -> dict:
    return {t: raw(f"SELECT COUNT(*) FROM {t}")[0][0] for t in TABLES}


def snap_fields(row):
    return {name: getattr(row, name) for name in SNAP_FIELDS} if row else None


def add_psa(s, cert, profile="psa-1001", added="2026-10-01"):
    return s.add(cert, "psa", profile_id=profile, identity=IDENTITY, subgrades=None, added=added)


def scalars(value):
    """Every scalar inside a stored cell: JSON text is opened, anything else is itself."""
    if isinstance(value, str) and value[:1] in "{[":
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
    if isinstance(value, dict):
        return [x for v in value.values() for x in scalars(v)]
    if isinstance(value, list):
        return [x for v in value for x in scalars(v)]
    return [value]


# ------------------------------------------------------------------------------ cases

def case_slabs():
    """1. slabs: one row per (cert, grader), grader in Card Ladder's name"""
    cert = "81234567"
    put(lambda s: add_psa(s, cert))
    row = slabs_now().get(cert, "psa")
    same(
        "a slab stores cert, grader, profile, identity, subgrades and the date added",
        (row.cert, row.grader, row.profile_id, row.identity, row.subgrades, row.added) if row else None,
        (cert, "psa", "psa-1001", IDENTITY, None, "2026-10-01"),
    )

    put(lambda s: add_psa(s, cert, added="2026-10-09"))
    rows = slabs_now().list()
    same("the same cert and grader added again keeps one row", len(rows), 1)
    same("and keeps the first date added", rows[0].added if rows else None, "2026-10-01")

    def twice(s):
        add_psa(s, "81234999")
        add_psa(s, "81234999")
    put(twice)
    same("two adds of one slab inside one write keep one row", len(slabs_now().list()), 2)

    beckett = "0012345678"
    put(lambda s: s.add(beckett, "bgs", profile_id="beckett-2002", identity=IDENTITY,
                        subgrades=SUBGRADES, added="2026-10-02"))
    row = slabs_now().get(beckett, "beckett")
    same("bgs is stored as Card Ladder's name, beckett", row.grader if row else None, "beckett")
    same("a cert is text: leading zeros stay", row.cert if row else None, beckett)
    same("subgrades come back as given", row.subgrades if row else None, SUBGRADES)
    before = len(slabs_now().list())
    put(lambda s: s.add(beckett, "bvg", profile_id="beckett-2002", identity=IDENTITY,
                        subgrades=SUBGRADES, added="2026-10-03"))
    put(lambda s: s.add(beckett, "beckett", profile_id="beckett-2002", identity=IDENTITY,
                        subgrades=SUBGRADES, added="2026-10-04"))
    same("bgs, bvg and beckett are one slab: still one row", len(slabs_now().list()), before)
    same("and it keeps the first date added", slabs_now().get(beckett, "BGS").added, "2026-10-02")

    put(lambda s: s.add(beckett, "cgc", profile_id="cgc-3003", identity=IDENTITY,
                        subgrades=None, added="2026-10-05"))
    same("one cert under another grader is another slab", len(slabs_now().list()), before + 1)


def case_grader_home():
    """1b. the grader map has one home"""
    slabs_module = import_module("store.slabs")
    cardladder = import_module("pipeline.cardladder")
    ok(
        getattr(slabs_module, "GRADERS", None) is cardladder.GRADERS,
        "pipeline.cardladder.GRADERS is store.slabs.GRADERS, not a copy",
    )
    ok(cardladder.GRADERS.get("bgs") == "beckett" and cardladder.GRADERS.get("bvg") == "beckett",
       "the map sends bgs and bvg to beckett")


def case_snapshots():
    """2. slab_snapshots: one row per slab per day"""
    cert = "81234567"
    put(lambda s: add_psa(s, cert))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_A))
    rows = slabs_now().snapshots_for(cert, "psa")
    same("one snapshot after one write", len(rows), 1)
    same("it holds both values with their confidence, the last sale, population, gem rate and speed",
         snap_fields(rows[0] if rows else None), SNAP_A)
    same("and the day", rows[0].day if rows else None, "2026-10-05")

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_B))
    rows = slabs_now().snapshots_for(cert, "psa")
    same("a second write the same day keeps one row", len(rows), 1)
    same("and it holds the second write's values, none of the first",
         snap_fields(rows[0] if rows else None), SNAP_B)
    same("raw: one row in slab_snapshots", counts()["slab_snapshots"], 1)

    def twice(s):
        s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_A)
        s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_C)
    put(twice)
    rows = slabs_now().snapshots_for(cert, "psa")
    same("a new day adds a row; two writes inside one transaction that day add one", len(rows), 2)
    same("the later of the two writes wins", snap_fields(rows[-1] if rows else None), SNAP_C)

    put(lambda s: add_psa(s, "81234568"))
    put(lambda s: s.record_snapshot("81234568", "psa", "2026-10-05", **SNAP_C))
    same("another slab the same day has its own row", counts()["slab_snapshots"], 3)
    same("and the first slab's days are untouched", len(slabs_now().snapshots_for(cert, "psa")), 2)


def case_sales():
    """3. slab_sales: keyed by Card Ladder's sale id, never deleted"""
    cert = "81234567"
    s1, s2, s3 = sale("s-100", "2026-10-01"), sale("s-101", "2026-10-05", "130.00"), sale("s-102", "2026-09-20", "88.00")
    put(lambda s: add_psa(s, cert))
    put(lambda s: s.record_sales(cert, "psa", [s1, s2]))
    put(lambda s: s.record_sales(cert, "psa", [s1, s2]))
    same("the same sales written twice keep one row each", counts()["slab_sales"], 2)
    got = slabs_now().sales_for(cert, "psa")
    same("each comes back with its id, its date and the sale verbatim",
         [(x.id, x.date, x.data) for x in got], [("s-101", "2026-10-05", s2), ("s-100", "2026-10-01", s1)])

    put(lambda s: s.record_sales(cert, "psa", [s2, s3]))
    same("a later read that lacks s-100 leaves it: three rows", counts()["slab_sales"], 3)
    same("and the slab still lists s-100", [x.id for x in slabs_now().sales_for(cert, "psa")],
         ["s-101", "s-100", "s-102"])

    put(lambda s: s.record_sales(cert, "psa", [dict(s1, price="101.00")]))
    same("the same sale id with a changed field is still one row", counts()["slab_sales"], 3)

    other = "81234568"
    put(lambda s: add_psa(s, other))
    put(lambda s: s.record_sales(other, "psa", [sale("s-200", "2026-10-06")]))
    same("another slab's own sale is not listed under this slab",
         [x.id for x in slabs_now().sales_for(cert, "psa")], ["s-101", "s-100", "s-102"])


def case_shared_sale():
    """3b. two slabs of one card both list a sale they both read"""
    a, b = "81234567", "81234568"
    put(lambda s: (add_psa(s, a), add_psa(s, b)))
    put(lambda s: s.record_sales(a, "psa", [sale("s-1", "2026-10-01"), sale("s-2", "2026-10-02")]))
    put(lambda s: s.record_sales(b, "psa", [sale("s-2", "2026-10-02"), sale("s-3", "2026-10-03")]))
    same("a sale read by two slabs is one row", counts()["slab_sales"], 3)
    ids = lambda cert: [x.id for x in slabs_now().sales_for(cert, "psa")]  # noqa: E731
    ok("s-2" in ids(a), "the first slab still lists the shared sale after the second read it", str(ids(a)))
    ok("s-2" in ids(b), "the second slab lists the shared sale", str(ids(b)))
    ok("s-1" in ids(a) and "s-3" in ids(b), "and each keeps the sale only it read", f"{ids(a)} {ids(b)}")


def case_grader_separation():
    """2b. one cert under two graders keeps two sets of snapshots"""
    cert = "81234567"
    put(lambda s: (add_psa(s, cert), s.add(cert, "cgc", profile_id="cgc-3003", identity=IDENTITY,
                                          subgrades=None, added="2026-10-02")))
    put(lambda s: (s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_A),
                   s.record_snapshot(cert, "cgc", "2026-10-05", **SNAP_C),
                   s.record_snapshot(cert, "cgc", "2026-10-06", **SNAP_B)))
    same("raw: the same cert and day under two graders are two rows", counts()["slab_snapshots"], 3)
    psa, cgc = slabs_now().snapshots_for(cert, "psa"), slabs_now().snapshots_for(cert, "cgc")
    same("psa lists its own snapshot and not cgc's", [(x.grader, x.day) for x in psa], [("psa", "2026-10-05")])
    same("and it holds psa's own values", snap_fields(psa[0] if psa else None), SNAP_A)
    same("cgc lists its own two snapshots and not psa's", [(x.grader, x.day) for x in cgc],
         [("cgc", "2026-10-05"), ("cgc", "2026-10-06")])
    same("and the shared day holds cgc's own values", snap_fields(cgc[0] if cgc else None), SNAP_C)


def case_sale_date_text():
    """3c. a sale whose date is not text is refused before any write"""
    cert = "81234567"
    kept = sale("s-1", "2026-10-01")
    undated = sale("s-3", "2026-10-03")
    del undated["date"]
    for kind, bad in (
        ("an int date", dict(sale("s-3", "2026-10-03"), date=20261003)),
        ("a dict date", dict(sale("s-3", "2026-10-03"), date={"y": 2026, "m": 10, "d": 3})),
        ("no date", undated),
    ):
        with fresh_home():
            put(lambda s: (add_psa(s, cert), s.record_sales(cert, "psa", [kept])))
            refused, inside, left = None, None, None
            try:
                with store().write() as snap:
                    try:  # the good sale comes first: a write that began before the check would keep it
                        snap.slabs.record_sales(cert, "psa", [sale("s-2", "2026-10-02"), bad])
                    except Exception as exc:
                        refused = exc
                    try:
                        inside = [x.id for x in snap.slabs.sales_for(cert, "psa")]
                    except Exception as exc:
                        inside = exc
            except Exception as exc:
                left = exc
            ok(isinstance(refused, ValueError), f"{kind}: record_sales raises ValueError", repr(refused))
            same(f"{kind}: no sale of the refused batch is in the write, the good one included", inside, ["s-1"])
            ok(left is None, f"{kind}: the write itself commits clean", repr(left))
            same(f"{kind}: raw: only the sale stored before is a row", counts()["slab_sales"], 1)
            try:
                later = [x.id for x in slabs_now().sales_for(cert, "psa")]
            except Exception as exc:
                later = exc
            same(f"{kind}: a later read lists its sales without raising", later, ["s-1"])


@contextmanager
def watched():
    """Trace every statement a connection opened inside this block runs, and list every
    `slab_sales` row `Rows` parses. Both patches are undone on the way out."""
    statements, parsed = [], []
    connect, remember = sqlite3.connect, Rows._remember

    def traced(*args, **kwargs):
        conn = connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    def counted(self, key, text):
        if self.spec.name == "slab_sales":
            parsed.append(key)
        return remember(self, key, text)

    sqlite3.connect, Rows._remember = traced, counted
    try:
        yield statements, parsed
    finally:
        sqlite3.connect, Rows._remember = connect, remember


def read_with(ask):
    """`ask(slabs)` on a fresh read: (its answer, plan rows that scan a table, slab_sales rows parsed).
    The log starts after the read is open, so only what `ask` itself runs is judged."""
    with watched() as (statements, parsed):
        slabs = store().read().slabs
        del statements[:], parsed[:]
        answer = ask(slabs)
        ran = list(statements)
    gc.collect()
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        plans = [
            row[3] for sql in ran if sql.lstrip().upper().startswith(("SELECT", "WITH"))
            for row in conn.execute("EXPLAIN QUERY PLAN " + sql)
        ]
    finally:
        conn.close()
    return answer, [p for p in plans if p.startswith("SCAN") and "CONSTANT ROW" not in p], len(parsed)


def case_sales_read_scope():
    """6b. reading one slab's sales reads only that slab's sale rows"""
    a, b, empty = "81234567", "81234568", "81234569"
    shared = sale("s-3", "2026-10-03")
    put(lambda s: (add_psa(s, a), add_psa(s, b), add_psa(s, empty)))
    put(lambda s: s.record_sales(a, "psa", [sale("s-1", "2026-10-01"), sale("s-2", "2026-10-02"), shared]))
    put(lambda s: s.record_sales(b, "psa", [shared] + [sale(f"s-{n}", f"2026-10-0{n}") for n in (4, 5, 6)]))
    total = counts()["slab_sales"]
    same("fixture: six sales, one of them shared by two slabs", total, 6)

    every, scanned, parsed = read_with(lambda slabs: list(slabs.sales.values()))
    same("control: reading every sale parses all of them, so the parse count sees a read", parsed, total)
    ok(bool(scanned), "control: reading every sale shows as a scan in the plan, so the plan check sees a read",
       f"{len(every)} rows, plan rows {scanned}")

    for label, cert, want in (("a slab with three sales", a, 3), ("a slab with four", b, 4), ("a slab with none", empty, 0)):
        got, scanned, parsed = read_with(lambda slabs, cert=cert: slabs.sales_for(cert, "psa"))
        same(f"{label}: sales_for lists its own sales", len(got), want)
        same(f"{label}: no statement it runs scans a table", scanned, [])
        ok(parsed <= want, f"{label}: it parses no more slab_sales rows than the slab has sales ({want})",
           f"parsed {parsed} of {total}")


def landing(s):
    """One write across all four tables."""
    add_psa(s, "81299999", profile="psa-2002", added="2026-10-10")
    s.record_snapshot("81299999", "psa", "2026-10-10", **SNAP_A)
    s.record_sales("81299999", "psa", [sale("n-1", "2026-10-08"), sale("n-2", "2026-10-09")])


def inject_failure(table: str):
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        conn.execute(
            f"CREATE TRIGGER inject_failure BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    finally:
        conn.close()


def clear_failure():
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        conn.execute("DROP TRIGGER IF EXISTS inject_failure")
    finally:
        conn.close()


class Boom(Exception):
    pass


def case_one_transaction():
    """4. each write is one transaction"""
    with fresh_home():
        put(landing)
        same("control: the same write, unbroken, lands a row in all four tables",
             counts(), {"slabs": 1, "slab_snapshots": 1, "slab_sales": 2, "slab_sale_links": 2})

    with fresh_home():
        seen = {}
        try:
            with store().write() as snap:
                landing(snap.slabs)
                seen["inside"] = snap.slabs.get("81299999", "psa") is not None
                raise Boom()
        except Boom:
            pass
        ok(seen.get("inside", False), "the rows are visible inside the write before it fails")
        same("an error raised inside the write keeps no row in any table",
             counts(), {"slabs": 0, "slab_snapshots": 0, "slab_sales": 0, "slab_sale_links": 0})

    for table in TABLES:
        with fresh_home():
            put(lambda s: add_psa(s, "81200000"))
            put(lambda s: s.record_snapshot("81200000", "psa", "2026-10-01", **SNAP_A))
            before = counts()
            inject_failure(table)
            seen = {}
            try:
                with store().write() as snap:
                    landing(snap.slabs)
                    seen["inside"] = snap.slabs.get("81299999", "psa") is not None
                raised = False
            except Exception:
                raised = True
            clear_failure()
            ok(seen.get("inside", False), f"{table} fails: the rows are visible inside the write")
            ok(raised, f"{table} fails: the write raises")
            same(f"a failure in {table} midway leaves no partial row in any table", counts(), before)
            same(f"{table} fails: the slab already stored is untouched",
                 snap_fields(slabs_now().snapshots_for("81200000", "psa")[0]), SNAP_A)
            put(landing)
            same(f"{table} fails: the same write works once the failure is gone",
                 counts(), {"slabs": 2, "slab_snapshots": 2, "slab_sales": 2, "slab_sale_links": 2})

    with fresh_home():
        put(lambda s: add_psa(s, "81200000"))
        raised = False
        with store().write() as snap:
            try:
                snap.slabs.record_sales(
                    "81200000", "psa", [sale("g-1", "2026-10-01"), {"price": "5.00", "date": "2026-10-02"}]
                )
            except Exception:
                raised = True
        ok(raised, "a sale with no id raises, it is not skipped")
        same("and none of its batch is kept, the good sale included", counts()["slab_sales"], 0)


def case_no_guessed_value():
    """5. no guessed value: a missing value is NULL"""
    cert = "81234567"
    put(lambda s: add_psa(s, cert))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_NONE))
    rows = slabs_now().snapshots_for(cert, "psa")
    same("a slab with no sale reads back every value as None", snap_fields(rows[0] if rows else None), SNAP_NONE)
    ok(rows and all(getattr(rows[0], f) is None for f in ("cl_value", "estimated_value", "last_sale_price")),
       "none of the values is 0, 0.0 or an empty string")

    cells = raw(f"SELECT {', '.join(VALUE_COLUMNS)} FROM slab_snapshots")
    same("raw: every value column is NULL", cells, [(None,) * len(VALUE_COLUMNS)])
    stored = [x for row in raw("SELECT * FROM slab_snapshots") for cell in row for x in scalars(cell)]
    invented = [x for x in stored if not isinstance(x, bool) and (x == 0 or x == "")]
    same("raw: the row holds no 0 and no empty string anywhere, payload included", invented, [])
    same("a slab with no sale has no sale rows", slabs_now().sales_for(cert, "psa"), [])

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-06", **dict(SNAP_A, estimated_value=None, estimated_confidence=None)))
    row = slabs_now().snapshots_for(cert, "psa")[-1]
    same("the estimate missing, the ladder value present: the estimate stays None",
         (row.cl_value, row.estimated_value, row.estimated_confidence), ("262.00", None, None))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-07", **dict(SNAP_A, cl_value=None, cl_confidence=None)))
    row = slabs_now().snapshots_for(cert, "psa")[-1]
    same("the ladder value missing, the estimate present: the ladder value stays None",
         (row.cl_value, row.cl_confidence, row.estimated_value), (None, None, "238.50"))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-08", **dict(SNAP_A, last_sale_price=None, last_sale_date=None)))
    row = slabs_now().snapshots_for(cert, "psa")[-1]
    same("no last sale: its price and date stay None, the values stay",
         (row.last_sale_price, row.last_sale_date, row.estimated_value), (None, None, "238.50"))


def listing_order(order):
    with fresh_home():
        for cert, grader in order:
            put(lambda s, cert=cert, grader=grader: s.add(
                cert, grader, profile_id="p-" + cert, identity=IDENTITY, subgrades=None, added="2026-10-01"))
        return [(x.cert, x.grader) for x in slabs_now().list()]


def case_reading_back():
    """6. reading back: list, snapshots in date order, sales newest first"""
    same("an empty store lists no slab", slabs_now().list(), [])
    same("an unknown slab has no snapshots and no sales",
         (slabs_now().snapshots_for("1", "psa"), slabs_now().sales_for("1", "psa")), ([], []))
    ok(slabs_now().get("1", "psa") is None, "an unknown slab is None")

    keys = [("81000003", "psa"), ("81000001", "psa"), ("81000002", "cgc")]
    first = listing_order(keys)
    same("list returns every slab", sorted(first), sorted(keys))
    same("list is in the same order however the slabs were added", listing_order(keys[::-1]), first)

    cert = "81234567"
    put(lambda s: add_psa(s, cert))
    for day, snap in (("2026-10-07", SNAP_C), ("2026-10-05", SNAP_A), ("2026-10-06", SNAP_B)):
        put(lambda s, day=day, snap=snap: s.record_snapshot(cert, "psa", day, **snap))
    same("snapshots come back oldest day first, however they were written",
         [x.day for x in slabs_now().snapshots_for(cert, "psa")], ["2026-10-05", "2026-10-06", "2026-10-07"])

    sales = [
        sale("s-100", "2026-09-20"), sale("s-300", "2026-10-05"),
        sale("s-200", "2026-10-01"), sale("s-201", "2026-10-01"),
    ]
    put(lambda s: s.record_sales(cert, "psa", sales))
    same("sales come back newest first, a tied date by id descending",
         [x.id for x in slabs_now().sales_for(cert, "psa")], ["s-300", "s-201", "s-200", "s-100"])
    put(lambda s: s.record_sales(cert, "psa", sales[::-1]))
    same("and in that order after the same sales are read again in another order",
         [x.id for x in slabs_now().sales_for(cert, "psa")], ["s-300", "s-201", "s-200", "s-100"])


def case_upgrade():
    """7. a store stamped 14 gets the tables on its next open"""
    survivor = Reading(market="1.00", at=1, source="x", kind="run")
    with store().write() as snap:
        snap.readings.entries["555"] = survivor
    gc.collect()
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        for table in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '14')")
    finally:
        conn.close()
    same("the fixture really is the owner's shape: stamp 14, no slab table",
         (raw("SELECT value FROM meta WHERE key = 'schema'"),
          raw("SELECT name FROM sqlite_master WHERE name IN ('slabs', 'slab_snapshots', 'slab_sales', 'slab_sale_links')")),
         ([("14",)], []))
    ok(db.SCHEMA_VERSION > 14, "the schema version is past 14", str(db.SCHEMA_VERSION))

    store().read()
    gc.collect()
    same("opening the store creates the four tables and re-stamps it",
         (sorted(r[0] for r in raw("SELECT name FROM sqlite_master WHERE name IN ('slabs', 'slab_snapshots', 'slab_sales', 'slab_sale_links')")),
          raw("SELECT value FROM meta WHERE key = 'schema'")),
         (sorted(TABLES), [(str(db.SCHEMA_VERSION),)]))
    same("and it creates the index sales_for reads the link table through",
         raw("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'slab_sale_links_slab'"),
         [("slab_sale_links_slab",)])
    same("and the rows already there survive", store().read().readings.entries.get("555"), survivor)
    put(landing)
    same("and the upgraded store takes a slab write", counts(), {"slabs": 1, "slab_snapshots": 1, "slab_sales": 2, "slab_sale_links": 2})


CASES = (
    case_slabs, case_grader_home, case_snapshots, case_grader_separation, case_sales,
    case_shared_sale, case_sale_date_text, case_one_transaction, case_no_guessed_value,
    case_reading_back, case_sales_read_scope, case_upgrade,
)


def main() -> int:
    print("My Slabs store self-test\n")
    try:
        import_module("store.slabs")
    except ModuleNotFoundError as exc:
        if exc.name != "store.slabs":
            raise
        ok(False, "store/slabs.py exists, with the interface in this file's header", str(exc))
        print(f"\n{PASS} passed, {FAIL} failed")
        return 1

    for case in CASES:
        print(f"-- {case.__doc__} --")
        try:
            with fresh_home():  # a case that wants a second, empty store nests its own
                case()
        except Exception:
            ok(False, f"{case.__name__} ran to the end", traceback.format_exc()[-700:])

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
