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
    Slabs.remove(cert, grader) -> Optional[Slab]
        The owner's remove (build plan step 3): the slab row and its sale links go, in the one
        write it is called in. Its snapshots and every sale stay, so adding the slab again brings
        the snapshots back, and a sale the next read omits stays in the table, unlinked. A sale
        another slab also read stays linked to that slab. Answers the removed Slab, or None (and
        writes nothing) when there is none; an unknown grader raises ValueError as everywhere.
        The `added` of a slab added again after a remove is pinned at the route (the routes
        selftest's restore cases), not here: the snapshots this file keeps are what it reads.
        NOT PINNED: what a sale row's own list of slabs says after one of them is removed.
    Slabs.get(cert, grader) -> Optional[Slab]
    Slabs.list() -> List[Slab]                      same order however the slabs were added
    Slabs.snapshots_for(cert, grader) -> List[SlabSnapshot]   oldest day first; [] if none
    Slabs.sales_for(cert, grader) -> List[Sale]     newest `date` first, ties by `id` descending
                                                    (`Readings.sources_payload`'s rule); [] if none.
                                                    Reads only that slab's sales (see below).
    Slab(cert, grader, profile_id, identity, subgrades, added, latest=None)
    Slab.latest           the slab row's copy of its NEWEST snapshot, the one with the greatest `day`: a
                          SlabSnapshot equal to `snapshots_for(...)[-1]`, or None until one is recorded.
                          `GET /slabs` reads `slabs` once and never `slab_snapshots`, which gains a row per
                          slab per day (spec section 6). `record_snapshot` is the one method that writes a
                          snapshot, and it updates this copy in the same write (case 8):
                            - a snapshot on a newer day, or the same day again, makes it the copy;
                            - a snapshot on an older day is stored but never replaces a newer copy;
                            - a snapshot for a slab with no row raises ValueError and writes nothing;
                            - a failed write keeps the old copy with the old snapshots, never one without the other.
                          `add` of a slab already there keeps its copy. `add` of a slab that was removed
                          seeds its copy from the newest snapshot it left, so the copy equals
                          `snapshots_for(...)[-1]` before any new snapshot (case 9).
                          No code but `Slabs.record_snapshot` writes `slab_snapshots` and none but
                          `Slabs` (and `_parse_slab`, which decodes a stored row) sets `latest`: a
                          source scan of `store/`, `server/`, `pipeline/` and `cli/` proves it (case 10).
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

import ast
import gc
import json
import sqlite3
import sys
import tempfile
import traceback
from collections.abc import Mapping, MutableMapping
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


def inject_delete_failure(table: str):
    conn = sqlite3.connect(store().db_path, isolation_level=None)
    try:
        conn.execute(
            f"CREATE TRIGGER inject_failure BEFORE DELETE ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    finally:
        conn.close()


def removal_seed(s):
    """Two PSA slabs that share a sale, and the same cert at CGC. The first has two days of snapshots."""
    a, b = "81234567", "81234568"
    s1, s2, s3 = sale("s-100", "2026-10-01"), sale("s-101", "2026-10-05", "130.00"), sale("s-102", "2026-09-20", "88.00")
    add_psa(s, a)
    add_psa(s, b)
    s.add(a, "cgc", profile_id="cgc-3003", identity=IDENTITY, subgrades=None, added="2026-10-02")
    s.record_snapshot(a, "psa", "2026-10-05", **SNAP_A)
    s.record_snapshot(a, "psa", "2026-10-06", **SNAP_C)
    s.record_snapshot(b, "psa", "2026-10-05", **SNAP_B)
    s.record_snapshot(a, "cgc", "2026-10-05", **SNAP_C)
    s.record_sales(a, "psa", [s1, s2])
    s.record_sales(b, "psa", [s2, s3])
    s.record_sales(a, "cgc", [sale("s-103", "2026-10-02")])


def case_remove():
    """3d. remove: the slab and its sale links go in one write; its snapshots and sales stay; a slab added again gets them back"""
    from store.slabs import Slabs

    if not ok(callable(getattr(Slabs, "remove", None)), "Slabs.remove exists"):
        return
    a, b = "81234567", "81234568"
    put(removal_seed)
    before = counts()
    same("control: three slabs, four snapshots, four sales, five links", before,
         {"slabs": 3, "slab_snapshots": 4, "slab_sales": 4, "slab_sale_links": 5})
    sales_before = {x.id: x.data for x in slabs_now().sales_for(b, "psa")}

    got = put(lambda s: s.remove(a, "psa"))
    same("remove answers the slab it took out", (got.cert, got.grader, got.identity) if got else None, (a, "psa", IDENTITY))
    s = slabs_now()
    same("the slab is gone", s.get(a, "psa"), None)
    same("the list holds the other two", sorted((x.cert, x.grader) for x in s.list()), sorted([(b, "psa"), (a, "cgc")]))
    same("every snapshot stays in the table", counts()["slab_snapshots"], 4)
    same("and every sale", counts()["slab_sales"], 4)
    same("its two links went, the other three stay", counts()["slab_sale_links"], 3)
    same("it lists no sale", s.sales_for(a, "psa"), [])
    same("its snapshots still read back whole",
         [(x.day, snap_fields(x)) for x in s.snapshots_for(a, "psa")],
         [("2026-10-05", SNAP_A), ("2026-10-06", SNAP_C)])
    same("a slab that read a shared sale still lists it", [x.id for x in s.sales_for(b, "psa")], ["s-101", "s-102"])
    same("with the sale whole", {x.id: x.data for x in s.sales_for(b, "psa")}, sales_before)
    same("the same cert at another grader is untouched",
         ([x.id for x in s.sales_for(a, "cgc")], [x.day for x in s.snapshots_for(a, "cgc")]), (["s-103"], ["2026-10-05"]))

    again = put(lambda s: s.remove(a, "psa"))
    same("a second remove finds nothing and answers None", again, None)
    same("and writes nothing", counts()["slab_sale_links"], 3)
    same("so does a cert nobody added", put(lambda s: s.remove("99999999", "psa")), None)
    refused = False
    try:
        put(lambda s: s.remove(a, "pokemon"))
    except ValueError:
        refused = True
    ok(refused, "an unknown grader raises ValueError, as every other method does")

    # The way back: add it again, and what it stored comes back.
    put(lambda s: add_psa(s, a, added="2026-10-09"))
    s = slabs_now()
    same("added again, its snapshots are back", [x.day for x in s.snapshots_for(a, "psa")], ["2026-10-05", "2026-10-06"])
    same("with no sale linked yet", s.sales_for(a, "psa"), [])
    put(lambda s: s.record_sales(a, "psa", [sale("s-101", "2026-10-05", "130.00"), sale("s-104", "2026-10-03")]))
    s = slabs_now()
    same("a read that lists two sales links those two", [x.id for x in s.sales_for(a, "psa")], ["s-101", "s-104"])
    ok("s-100" in s.sales, "the sale that read omits stays in the table")
    same("unlinked: this slab does not list it", "s-100" in [x.id for x in s.sales_for(a, "psa")], False)
    same("five links (its two and the others' three) and five sales",
         (counts()["slab_sale_links"], counts()["slab_sales"]), (5, 5))

    put(lambda s: s.add("0012345678", "bgs", profile_id="beckett-77", identity=IDENTITY, subgrades=SUBGRADES, added="2026-10-01"))
    got = put(lambda s: s.remove("0012345678", "BVG"))
    same("a grader typed in another form is the same grader: bvg removes the slab added under bgs, keeping its zeros",
         (got.cert, got.grader) if got else None, ("0012345678", "beckett"))

    for table in ("slabs", "slab_sale_links"):
        with fresh_home():
            put(removal_seed)
            before = counts()
            inject_delete_failure(table)
            raised = False
            try:
                put(lambda s: s.remove(a, "psa"))
            except Exception:
                raised = True
            clear_failure()
            ok(raised, f"a delete that fails in {table} fails the remove")
            same(f"and leaves no table changed ({table})", counts(), before)
            ok(slabs_now().get(a, "psa") is not None and len(slabs_now().sales_for(a, "psa")) == 2,
               f"the slab and its two sales are still there ({table})")
            put(lambda s: s.remove(a, "psa"))
            same(f"the same remove works once the failure is gone ({table})", counts()["slab_sale_links"], 3)


def latest_of(cert, grader="psa"):
    """The slab row's copy of its newest snapshot, from a fresh read. None when there is no row or no copy."""
    row = slabs_now().get(cert, grader)
    return getattr(row, "latest", None) if row else None


def newest_stored(cert, grader="psa"):
    rows = slabs_now().snapshots_for(cert, grader)
    return rows[-1] if rows else None


def day_and_fields(row):
    return (row.day, snap_fields(row)) if row else None


def case_latest():
    """8. the slab row keeps its newest snapshot, updated by record_snapshot in the same write"""
    cert = "81234567"
    put(lambda s: add_psa(s, cert))
    same("a slab with no snapshot has no copy", latest_of(cert), None)

    answered = put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_A))
    row = latest_of(cert)
    same("after a snapshot the slab row holds that day and every value", day_and_fields(row), ("2026-10-05", SNAP_A))
    same("the copy is the stored snapshot, whole", row, newest_stored(cert))
    same("and the one record_snapshot answered", row, answered)

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_B))
    row = latest_of(cert)
    same("a second write that day replaces the copy whole: SNAP_B's values, none of SNAP_A's",
         day_and_fields(row), ("2026-10-05", SNAP_B))
    same("and it is still the stored snapshot", row, newest_stored(cert))

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-07", **SNAP_C))
    same("a newer day moves the copy to that day", day_and_fields(latest_of(cert)), ("2026-10-07", SNAP_C))

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_A))
    row = latest_of(cert)
    same("an older day written after a newer one leaves the copy on the newer", day_and_fields(row), ("2026-10-07", SNAP_C))
    same("the older snapshot is still stored", [x.day for x in slabs_now().snapshots_for(cert, "psa")],
         ["2026-10-05", "2026-10-06", "2026-10-07"])
    same("and the copy is still the newest stored snapshot", row, newest_stored(cert))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_B))
    same("replacing that older day again leaves the copy alone", latest_of(cert), row)

    put(lambda s: add_psa(s, cert, added="2026-10-20"))
    same("adding a slab that is already there keeps its copy", latest_of(cert), row)

    newer_first, older_first = "81234568", "81234569"
    put(lambda s: (add_psa(s, newer_first), add_psa(s, older_first)))

    def both_ways(s):
        s.record_snapshot(newer_first, "psa", "2026-10-09", **SNAP_C)
        s.record_snapshot(newer_first, "psa", "2026-10-08", **SNAP_A)
        s.record_snapshot(older_first, "psa", "2026-10-08", **SNAP_A)
        s.record_snapshot(older_first, "psa", "2026-10-09", **SNAP_C)
    put(both_ways)
    same("two writes in one transaction, newer day first: the copy is the newer",
         day_and_fields(latest_of(newer_first)), ("2026-10-09", SNAP_C))
    same("two writes in one transaction, older day first: the copy is the newer",
         day_and_fields(latest_of(older_first)), ("2026-10-09", SNAP_C))

    put(lambda s: s.add(cert, "cgc", profile_id="cgc-3003", identity=IDENTITY, subgrades=None, added="2026-10-02"))
    put(lambda s: s.record_snapshot(cert, "cgc", "2026-10-04", **SNAP_B))
    same("one cert under another grader keeps its own copy", day_and_fields(latest_of(cert, "cgc")), ("2026-10-04", SNAP_B))
    same("and the first grader's copy is untouched", latest_of(cert), row)

    before = counts()
    refused = False
    try:
        put(lambda s: s.record_snapshot("99999999", "psa", "2026-10-05", **SNAP_A))
    except ValueError:
        refused = True
    ok(refused, "a snapshot for a slab with no row raises ValueError")
    same("and it writes nothing: no snapshot row, no slab row", counts(), before)

    for table in ("slabs", "slab_snapshots"):
        with fresh_home():
            put(lambda s: add_psa(s, cert))
            put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_A))
            held, before = latest_of(cert), counts()
            ok(held is not None, f"{table} fails: control, the slab row holds a copy before the write")
            inject_failure(table)
            raised = False
            try:
                put(lambda s: s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_C))
            except Exception:
                raised = True
            clear_failure()
            ok(raised, f"{table} fails: the snapshot write raises")
            same(f"{table} fails: no snapshot row lands without its copy", counts(), before)
            same(f"{table} fails: the slab row keeps the old copy", latest_of(cert), held)


def case_latest_after_remove():
    """9. a slab added again after a remove has its copy back, and an older-day snapshot cannot undo it"""
    cert = "81234570"
    put(lambda s: add_psa(s, cert))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-05", **SNAP_A))
    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-07", **SNAP_C))
    ok(len(slabs_now().snapshots_for(cert, "psa")) == 2, "control: two days are stored")
    same("control: the copy is the newer day", day_and_fields(latest_of(cert)), ("2026-10-07", SNAP_C))

    put(lambda s: s.remove(cert, "psa"))
    same("removed: no slab row, and both snapshots stay",
         (slabs_now().get(cert, "psa"), len(slabs_now().snapshots_for(cert, "psa"))), (None, 2))

    put(lambda s: add_psa(s, cert, added="2026-10-09"))
    newest = newest_stored(cert)
    ok(newest is not None and newest.day == "2026-10-07", "control: the newest stored snapshot is the 10-07 one")
    same("re-added with no new snapshot in that write: the copy is the newest stored snapshot", latest_of(cert), newest)
    same("and it holds the newer day's values", day_and_fields(latest_of(cert)), ("2026-10-07", SNAP_C))

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-06", **SNAP_B))
    same("an older day recorded after the re-add is stored", [x.day for x in slabs_now().snapshots_for(cert, "psa")],
         ["2026-10-05", "2026-10-06", "2026-10-07"])
    same("and leaves the copy on the newest stored snapshot", latest_of(cert), newest_stored(cert))
    same("which is still the 10-07 one", day_and_fields(latest_of(cert)), ("2026-10-07", SNAP_C))

    put(lambda s: s.record_snapshot(cert, "psa", "2026-10-08", **SNAP_A))
    same("a newer day after the re-add moves the copy", (latest_of(cert), day_and_fields(latest_of(cert))),
         (newest_stored(cert), ("2026-10-08", SNAP_A)))


# ------------------------------------------------------------------------ who writes a snapshot

SCAN_DIRS = ("store", "server", "pipeline", "cli")
# The verbs that change a `Rows`: what `MutableMapping` adds to `Mapping` (pop, popitem, clear, update,
# setdefault, and the two dunders), `Rows`' own `flushed` and `_remember`, and `add`/`put`, which no
# `Rows` has yet but a writer might assume. `x.snapshots[k] = v` and `del x.snapshots[k]` are checked apart.
WRITE_VERBS = {n for n in dir(MutableMapping) if not hasattr(Mapping, n)} | {"flushed", "_remember", "add", "put"}


def _in(qual: str, owner: str) -> bool:
    return qual == owner or qual.startswith(owner + ".")


def may_write_snapshot(rel: str, qual: str) -> bool:
    """The one writer of `slab_snapshots`."""
    return rel == "store/slabs.py" and _in(qual, "Slabs.record_snapshot")


def may_set_latest(rel: str, qual: str) -> bool:
    """`Slabs`, and `_parse_slab`, which rebuilds a `Slab` from its stored payload and decides nothing."""
    return rel == "store/slabs.py" and (_in(qual, "Slabs") or _in(qual, "_parse_slab"))


class Scan(ast.NodeVisitor):
    """What `ast` sees, so a string, a comment or a docstring holding the same text is never code.
    Finds a write to the snapshots table (a subscript assignment or `del`, or a `Rows` write verb, on an
    attribute named `snapshots`, a private field of one, or a local bound to one) and a write of `Slab.latest`
    (an attribute assignment, a `latest=` keyword, `setattr(.., "latest", ..)`, or a `Slab(..)` call with
    its seventh positional argument or a `*`/`**` splat). One alias hop; a table reached by `getattr`,
    a tuple unpack or a call is not followed."""

    def __init__(self, rel: str):
        self.rel, self.scope, self.aliases, self.found = rel, [], [set()], []

    def _scoped(self, node):
        self.scope.append(node.name)
        self.aliases.append(set())
        self.generic_visit(node)
        self.scope.pop()
        self.aliases.pop()

    visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _scoped

    def hit(self, node, kind: str, what: str):
        qual = ".".join(self.scope)
        if not (may_write_snapshot if kind == "snapshots" else may_set_latest)(self.rel, qual):
            self.found.append((self.rel, node.lineno, what))

    def table(self, node) -> bool:
        if isinstance(node, ast.Attribute):
            return node.attr == "snapshots" or self.table(node.value)
        return isinstance(node, ast.Name) and node.id in self.aliases[-1]

    def target(self, node):
        if isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                self.target(item)
        elif isinstance(node, ast.Subscript) and self.table(node.value):
            self.hit(node, "snapshots", "a write into the snapshots table")
        elif isinstance(node, ast.Attribute) and node.attr == "latest":
            self.hit(node, "latest", "an assignment to .latest")

    def visit_Assign(self, node):
        for target in node.targets:
            self.target(target)
            if isinstance(target, ast.Name) and self.table(node.value):
                self.aliases[-1].add(target.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.target(node.target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self.target(node.target)
        self.generic_visit(node)

    def visit_Delete(self, node):
        for target in node.targets:
            self.target(target)
        self.generic_visit(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in WRITE_VERBS and self.table(func.value):
            self.hit(node, "snapshots", "a Rows write verb on the snapshots table")
        if any(k.arg == "latest" for k in node.keywords):
            self.hit(node, "latest", "a latest= keyword")
        if (isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant) and node.args[1].value == "latest"):
            self.hit(node, "latest", "setattr(.., 'latest', ..)")
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name == "Slab" and (len(node.args) > 6 or any(isinstance(a, ast.Starred) for a in node.args)
                               or any(k.arg is None for k in node.keywords)):
            self.hit(node, "latest", "a Slab(..) call that sets latest")
        self.generic_visit(node)


def scan_source(text: str, rel: str) -> list:
    """(rel, line, what) for each write `rel` may not make. A file that will not parse is a finding: the scan is blind to it."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [(rel, exc.lineno or 0, "does not parse")]
    scan = Scan(rel)
    scan.visit(tree)
    return scan.found


def scan_tree(root: Path) -> list:
    found = []
    for name in SCAN_DIRS:
        for path in sorted((root / name).rglob("*.py")):
            found += scan_source(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
    return found


def lines_of(text: str, rel: str = "server/sweep.py") -> list:
    return [line for _, line, _ in scan_source(text, rel)]


def case_snapshot_writers():
    """10. nothing but Slabs.record_snapshot writes a snapshot, and nothing but Slabs sets latest: a scan of the source"""
    ok(hasattr(Rows, "flushed") and hasattr(Rows, "_remember"), "control: Rows still has the two own write verbs the scan names")
    ok({"pop", "update", "setdefault", "clear", "popitem", "__setitem__", "__delitem__"} <= WRITE_VERBS,
       "control: the verb set holds every MutableMapping write")

    # The real tree. The planted cases below prove this answer is not blindness.
    same("no code outside Slabs.record_snapshot writes slab_snapshots, none outside Slabs sets .latest",
         scan_tree(ROOT), [])

    # A planted offender is found, whatever form it takes. Each sits on line 2 of a function (line 3 when it has two lines).
    for label, src in (
        ("a subscript assignment", 't.snapshots["k"] = row'),
        ("a nested attribute", 'self.slabs.snapshots[key] = row'),
        ("an augmented assignment", 't.snapshots["k"] += 1'),
        ("a del", 'del t.snapshots["k"]'),
        ("update", 't.snapshots.update({"k": row})'),
        ("pop", 't.snapshots.pop("k")'),
        ("popitem", 't.snapshots.popitem()'),
        ("clear", 't.snapshots.clear()'),
        ("setdefault", 't.snapshots.setdefault("k", row)'),
        ("add", 't.snapshots.add(row)'),
        ("put", 't.snapshots.put("k", row)'),
        ("flushed", 't.snapshots.flushed([])'),
        ("__setitem__", 't.snapshots.__setitem__("k", row)'),
        ("a private field", 't.snapshots._loaded["k"] = row'),
        ("a local bound to the table", 'snaps = t.snapshots\nsnaps["k"] = row'),
        ("a tuple target", 'a, t.snapshots["k"] = 1, row'),
        ("a latest= keyword", 's.slabs[k] = slab._replace(latest=row)'),
        ("an attribute assignment to latest", 'slab.latest = row'),
        ("setattr latest", 'setattr(slab, "latest", row)'),
        ("a Slab with a seventh argument", 'Slab(1, 2, 3, 4, 5, 6, row)'),
        ("a Slab with a ** splat", 'Slab(**fields)'),
        ("a Slab with a * splat", 'Slab(*fields)'),
    ):
        body = "\n".join("    " + line for line in src.split("\n"))
        same(f"found: {label}", lines_of(f"def sweep(t, slab, row, fields):\n{body}\n"), [3 if "\n" in src else 2])

    # The same text that is not code is not found.
    for label, src in (
        ("a string", 'x = \'t.snapshots["k"] = row\'\ny = "Slab(**fields)"'),
        ("a comment", '# t.snapshots["k"] = row\n# slab.latest = row  // /* #'),
        ("a docstring", 'def f():\n    """t.snapshots.update({})\n    slab.latest = row\n    """\n'),
        ("a multi-line string", 'text = """\nt.snapshots["fake"] = row  # inside the string\n/* // */\nslab.latest = x\n"""\n'),
        ("a lone quote in a comment", "# it's t.snapshots['k'] = row\n"),
        ("reads", 'a = t.snapshots["k"]\nb = t.snapshots.where(cert="1")\nc = t.snapshots_for(1, 2)\nd = slab.latest.day\n'
                  'e = Slab(1, 2, 3, 4, 5, 6)\nf = slab._replace(added=1)\nlatest = 4\n'),
    ):
        same(f"not found: {label}", lines_of(src), [])

    # A comment opener or a lone quote in a string or comment does not hide the real write after it.
    for label, src, want in (
        ("a # inside a string", 'note = "see # here // and /* there"; t.snapshots["k"] = row', [1]),
        ("a multi-line string above", 'text = """\nt.snapshots["fake"] = row  # fake\n/* // */\n"""\nt.snapshots["real"] = row\n', [5]),
        ("a lone quote in a comment above", "# don't\nt.snapshots['k'] = row\n", [2]),
        ("a lone quote in a string above", "note = \"it's\"\nt.snapshots['k'] = row\n", [2]),
        ("a lone quote in a docstring above", 'def f(t):\n    """Don\'t."""\n    t.snapshots["k"] = row\n', [3]),
    ):
        same(f"found after {label}", lines_of(src), want)

    # The allow list is by file and by method.
    def in_slabs(src):
        return lines_of(src, "store/slabs.py")

    same("allowed: Slabs.record_snapshot writes the table and sets latest",
         in_slabs('class Slabs:\n    def record_snapshot(self):\n        self.snapshots["k"] = 1\n        self.slabs[k] = s._replace(latest=1)\n'), [])
    same("allowed: a helper nested in record_snapshot",
         in_slabs('class Slabs:\n    def record_snapshot(self):\n        def put():\n            self.snapshots["k"] = 1\n'), [])
    same("not allowed: another Slabs method writes the table",
         in_slabs('class Slabs:\n    def sweep(self):\n        self.snapshots["k"] = 1\n'), [3])
    same("not allowed: another class with that method name",
         in_slabs('class Other:\n    def record_snapshot(self):\n        self.snapshots["k"] = 1\n'), [3])
    same("not allowed: a module function with that name", in_slabs('def record_snapshot(self):\n    self.snapshots["k"] = 1\n'), [2])
    same("not allowed: the same method in another file",
         lines_of('class Slabs:\n    def record_snapshot(self):\n        self.snapshots["k"] = 1\n', "server/slabs.py"), [3])
    same("allowed: Slabs sets latest in any method",
         in_slabs('class Slabs:\n    def add(self):\n        return Slab(1, 2, 3, 4, 5, 6, history[-1])\n'), [])
    same("allowed: _parse_slab decodes a stored row", in_slabs('def _parse_slab(key, record):\n    return Slab(**row)\n'), [])
    same("not allowed: another store/slabs.py function sets latest", in_slabs('def other(row):\n    return Slab(**row)\n'), [2])
    same("not allowed: _parse_slab in another file",
         lines_of('def _parse_slab(key, record):\n    return Slab(**row)\n', "server/x.py"), [2])
    same("a file that will not parse is a finding", [what for _, _, what in scan_source("def (:\n", "pipeline/broken.py")],
         ["does not parse"])

    # The tree walk: a planted file is found where it sits; a quiet one, the allowed one and one outside the four folders are not.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, src in (
            ("server/planted.py", 'def sweep(t, row):\n    t.snapshots["k"] = row\n'),
            ("pipeline/quiet.py", '"""t.snapshots["k"] = row"""\n# slab.latest = row\n'),
            ("cli/sub/deep.py", 'def f(s):\n    s.slabs.snapshots.update({})\n'),
            ("scripts/outside.py", 'def f(s):\n    s.snapshots["k"] = 1\n'),
            ("store/slabs.py", 'class Slabs:\n    def record_snapshot(self):\n        self.snapshots["k"] = 1\n'),
        ):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(src, encoding="utf-8")
        same("a planted file is found where it sits",
             sorted((rel, line) for rel, line, _ in scan_tree(root)), [("cli/sub/deep.py", 2), ("server/planted.py", 2)])


CASES = (
    case_slabs, case_grader_home, case_snapshots, case_grader_separation, case_sales,
    case_shared_sale, case_sale_date_text, case_one_transaction, case_no_guessed_value,
    case_reading_back, case_sales_read_scope, case_upgrade, case_remove, case_latest,
    case_latest_after_remove, case_snapshot_writers,
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
