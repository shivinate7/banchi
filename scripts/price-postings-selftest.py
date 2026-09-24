#!/usr/bin/env python3
"""`store/postings.py` and `store/db.py`'s `price_postings` table, proved against a throwaway
store (D243).

THE ARM THIS FILE EXISTS FOR is the append-only property itself — the whole value of this
feature and the one way it silently becomes useless (the task brief's own words). It is proved
two ways:

  1. Posting the SAME SKU twice lands TWO rows, never one, and both keep their own price.
  2. `--mutate-to-upsert` re-runs the same suite against a COPY of `store/db.py` whose
     `append_postings` has been rewritten, by one literal string replacement, from a plain
     `INSERT` into an `INSERT OR REPLACE ... ON CONFLICT(sku) DO UPDATE` keyed on `sku` — the
     shape this table must never take. That copy is imported in place of the real module and
     the whole suite is run against it. The mutated run MUST fail: a suite that stays green
     under this mutation is not testing the property it claims to.

NO NETWORK. `emit` and `reprice apply` are `store/postings.py:Postings.record()`'s only two
callers today, both real presses (`./pkmnscan emit`, `./pkmnscan reprice apply`) — the sentence
that used to sit here ("no caller a screen reaches yet") described the table's READ side,
never the write side this file proves, and had gone stale for the write side regardless.
NOTHING READS `price_postings` BACK ONTO A SCREEN YET (D244 — "shelved until there is a
history to draw"); that is a separate fact from whether a press writes it, and this file
proves only the write.

PATH GATED, THE TWENTIETH (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make price-postings-selftest`, wired into
`make check` and `make ci-check` through `scripts/guard-scope.py`. This file is no longer
the exception it was when written — the "own precedent" it used to cite was
`pricearchive-selftest.py`'s OWN prior exemption, and that exemption is gone: once it's
done, it only needs to be tested when touched.

`store.db` and `store.session` ARE LOADED BY NAME (`importlib.import_module`, further
down), purging `sys.modules` first — the only way to swap in a mutated copy of
`store/db.py` for the mutation arm without a stale, pre-mutation module staying bound.
That call's own STRING LITERAL is what `scripts/guard-scope.py:derive_subjects`'s AST walk
reads directly: `_PathCollector.visit_Call` resolves an `importlib.import_module("<dotted
name>")` argument the same way `visit_ImportFrom` resolves a static import, so
`store/postings.py` and `store/session.py` are derived subjects with no decoy import here
and nothing hand-typed beside it.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import files  # noqa: E402

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
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


def _fresh_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="price-postings-selftest-"))
    (home / "inventory").mkdir(parents=True, exist_ok=True)
    return home


def run_suite(db_module, session_module, postings_module) -> None:
    """The whole proof, over whichever `store.db` module is handed in — the real one, or a
    mutated copy. Never imports `store.db`/`store.session`/`store.postings` at module
    scope, so this function can be run twice in one process against two different
    implementations.
    """
    Store = session_module.Store

    # ------------------------------------------------------------ 1. a posted price lands
    with Store().write() as writable:
        ok(isinstance(writable.postings, postings_module.Postings),
           "`Store.write()` hands the caller `store/postings.py`'s own `Postings`, "
           "not a stand-in — proves `store/session.py`'s `postings=Postings()` wiring "
           "reaches the real class, in whichever `store/` copy this run loaded",
           type(writable.postings))
        writable.postings.record(sku="9999001", price="4.99", source="emit", run="run-a")
    rows = db_module.postings_for_sku(_conn(db_module), "9999001")
    ok(len(rows) == 1, "one posting lands one row", rows)
    ok(rows and rows[0]["price"] == "4.99", "the row carries the price that was posted", rows)
    ok(rows and rows[0]["source"] == "emit" and rows[0]["run"] == "run-a",
       "the row carries which press wrote it and which run", rows)
    ok(rows and rows[0]["replaced"] is None,
       "no `replaced` was given, so none is stored — never a guess", rows)

    # ------------------------------------------------------- 2. a SECOND posting is a SECOND row
    with Store().write() as writable:
        writable.postings.record(
            sku="9999001", price="3.49", source="reprice", run="2026-09-20-markdown",
            replaced="4.99",
        )
    rows = db_module.postings_for_sku(_conn(db_module), "9999001")
    ok(len(rows) == 2, "a second posting of the SAME sku lands a SECOND row", rows)
    ok({r["price"] for r in rows} == {"4.99", "3.49"},
       "both postings keep their own price — the first is not overwritten", rows)
    ok(rows[0]["id"] != rows[1]["id"], "the two rows have distinct ids", rows)
    ok(rows[1]["replaced"] == "4.99",
       "the second row names what it replaced, from the caller's own hand", rows)

    # -------------------------------------------------------- 3. a THIRD and FOURTH posting
    with Store().write() as writable:
        writable.postings.record(sku="9999001", price="3.00", source="reprice", run="m2")
        writable.postings.record(sku="9999001", price="2.75", source="reprice", run="m3")
    rows = db_module.postings_for_sku(_conn(db_module), "9999001")
    ok(len(rows) == 4,
       "the round the owner asked about — a SKU priced a second, third and fourth time — "
       "keeps every row", rows)
    ok([r["price"] for r in rows] == ["4.99", "3.49", "3.00", "2.75"],
       "postings read back oldest first, in the order they were made", rows)

    # ---------------------------------------------------------------- 4. never deleted
    total_before = db_module.postings_count(_conn(db_module))
    with Store().write() as writable:
        writable.postings.record(sku="8888002", price="1.00", source="emit", run="run-b")
    total_after = db_module.postings_count(_conn(db_module))
    ok(total_after == total_before + 1,
       "the total only ever grows — one more posting, one more row, nothing else moved",
       (total_before, total_after))
    # Nothing in this module ever runs a DELETE or an UPDATE against price_postings, and
    # the table has no such call anywhere in this repo — the guard `store/postings.py`'s
    # docstring argues for is a structural one (no update/delete statement to call), and this
    # is the behavioural proof that a normal session of writes never shrinks the table.

    # ------------------------------------------------------ 5. a PROPOSAL alone records nothing
    # `store/postings.py` is never even reached by a preview — a `--write`-gated caller (both
    # real ones, `emit` and `reprice apply`) simply never calls `.record()` before that gate,
    # so the honest way to prove "a proposal that is never posted records nothing" is to open
    # a write session, decide NOT to record (exactly what a refused emit or a dry-run reprice
    # does), and show the table is unchanged.
    before_count = db_module.postings_count(_conn(db_module))
    with Store().write() as writable:
        pass  # a run that refused before writing a file calls `.record()` zero times
    after_count = db_module.postings_count(_conn(db_module))
    ok(after_count == before_count,
       "a session that never calls `.record()` — a proposal, a refusal, a dry run — "
       "posts nothing", (before_count, after_count))

    # ------------------------------------------------------------- 6. across store re-opens
    # A fresh `Store().read()` sees exactly the same rows a fresh `Store().write()` wrote —
    # this is what proves the ledger is really durable in `store.sqlite` and not an artifact
    # of one process's memory.
    fresh_rows = db_module.postings_for_sku(_conn(db_module), "9999001")
    ok(len(fresh_rows) == 4, "a fresh connection reads back every row a prior session wrote",
       fresh_rows)


def _conn(db_module):
    """One throwaway connection for read-only queries, against the current PKMNSCAN_HOME."""
    return db_module.connect(files.inventory_dir())


def _mutate_to_upsert(src: str) -> str:
    """Rewrite `append_postings`'s plain `INSERT` into an upsert keyed on `sku` — the exact
    shape `store/postings.py`'s docstring says this table must never take. One literal string
    replacement, same shape `scripts/mutate-guards.py` uses for its own guards.
    """
    anchor = (
        '            "INSERT INTO price_postings (at, sku, price, source, run, replaced) "\n'
        '            "VALUES (?, ?, ?, ?, ?, ?)",'
    )
    if src.count(anchor) != 1:
        raise SystemExit(
            "MUTATION ANCHOR NOT FOUND EXACTLY ONCE — store/db.py's append_postings moved "
            "and this mutation proves nothing until the anchor is updated to match it."
        )
    replacement = (
        '            "INSERT INTO price_postings (at, sku, price, source, run, replaced) "\n'
        '            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(sku) DO UPDATE SET "\n'
        '            "price=excluded.price, at=excluded.at, source=excluded.source, "\n'
        '            "run=excluded.run, replaced=excluded.replaced",'
    )
    mutated = src.replace(anchor, replacement)
    # An upsert needs something to conflict ON — add a UNIQUE(sku) the real DDL never has,
    # so the mutated copy is a self-consistent (if wrong) schema and the failure this proves
    # is the row-loss the real schema's own shape prevents, not a SQL error from a missing
    # constraint.
    ddl_anchor = (
        '"CREATE TABLE IF NOT EXISTS price_postings (id INTEGER PRIMARY KEY AUTOINCREMENT, "\n'
        '    "at INTEGER NOT NULL, sku TEXT NOT NULL, price TEXT NOT NULL, source TEXT NOT NULL, "\n'
        '    "run TEXT, replaced TEXT)"'
    )
    if ddl_anchor not in mutated:
        raise SystemExit(
            "MUTATION ANCHOR (DDL) NOT FOUND — store/db.py's _PRICE_POSTINGS_DDL moved and "
            "this mutation proves nothing until the anchor is updated to match it."
        )
    mutated = mutated.replace(
        ddl_anchor, ddl_anchor.replace('"run TEXT, replaced TEXT)"', '"run TEXT, replaced TEXT, UNIQUE(sku))"')
    )
    return mutated


def _run_against(home: Path, mutate: bool) -> int:
    global PASS, FAIL
    PASS = FAIL = 0
    previous = os.environ.get(files.HOME_ENV)
    os.environ[files.HOME_ENV] = str(home)
    tmp_module_dir = None
    try:
        if mutate:
            real_db_path = ROOT / "store" / "db.py"
            mutated_src = _mutate_to_upsert(real_db_path.read_text(encoding="utf-8"))
            tmp_module_dir = Path(tempfile.mkdtemp(prefix="price-postings-mutant-"))
            # A full copy of `store/`, so the mutated `db.py` still finds its package
            # siblings (`files.py`, `master.py`, ...) via ordinary relative imports.
            shutil.copytree(ROOT / "store", tmp_module_dir / "store")
            (tmp_module_dir / "store" / "db.py").write_text(mutated_src, encoding="utf-8")
            sys.path.insert(0, str(tmp_module_dir))
            for name in list(sys.modules):
                if name == "store" or name.startswith("store."):
                    del sys.modules[name]
            db_module = importlib.import_module("store.db")
            session_module = importlib.import_module("store.session")
            postings_module = importlib.import_module("store.postings")
        else:
            for name in list(sys.modules):
                if name == "store" or name.startswith("store."):
                    del sys.modules[name]
            db_module = importlib.import_module("store.db")
            session_module = importlib.import_module("store.session")
            postings_module = importlib.import_module("store.postings")

        try:
            run_suite(db_module, session_module, postings_module)
        except Exception as exc:  # noqa: BLE001 — a crash under mutation IS a failure, not a hang
            import traceback
            traceback.print_exc()
            FAIL += 1
            print(f"  FAIL   suite raised {exc!r} — counted as a failure, not swallowed")
    finally:
        if tmp_module_dir is not None:
            sys.path.remove(str(tmp_module_dir))
            shutil.rmtree(tmp_module_dir, ignore_errors=True)
        for name in list(sys.modules):
            if name == "store" or name.startswith("store."):
                del sys.modules[name]
        if previous is None:
            os.environ.pop(files.HOME_ENV, None)
        else:
            os.environ[files.HOME_ENV] = previous
    return FAIL


def main() -> int:
    mutate = "--mutate-to-upsert" in sys.argv[1:]
    home = _fresh_home()
    try:
        _run_against(home, mutate=mutate)
    finally:
        shutil.rmtree(home, ignore_errors=True)

    label = "MUTATED (append_postings rewritten as an upsert)" if mutate else "real"
    print(f"\nprice-postings self-test [{label}]: {PASS} passed"
          + (f", {FAIL} FAILED" if FAIL else ""))

    if mutate:
        # THE MUTATED RUN MUST FAIL. A green run here means the suite above does not actually
        # exercise the append-only property, which is the whole point of this file.
        if FAIL == 0:
            print("MUTATION SURVIVED — the suite passed even with `append_postings` "
                  "rewritten as an upsert. The append-only property is not being tested.")
            return 1
        print("mutation caught: the suite goes red when the write becomes an upsert, "
              "exactly as it must.")
        return 0
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
