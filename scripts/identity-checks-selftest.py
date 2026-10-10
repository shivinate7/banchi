#!/usr/bin/env python3
"""`pipeline/identity_checks.py`, proved against literal fixtures, and `cli/cmd_cards.py`'s
`identity`, `photos` and `checks` subcommands, proved against a temp store (D239).

Protects: Each stored-data identity check goes red on its own named defect and stays quiet on clean data.
Governs: D239, D247

EACH CHECK IS PROVED THE WAY `CLAUDE.md` DEMANDS: shown to catch its own named defect, and
shown NOT to fire on the clean data beside it. A guard that has never gone red on the thing
it guards is not trusted here. Four positive arms (one per check, each built from the exact
subject the cited decision entry measured — `102/166` in a 298-card `Origins`, `0934` in a
132-card `ME01: Mega Evolution`, `Shadbow Temple` beside `Shadow Temple`, the 152-character
rules-text name) and four negative arms (the same shape, with the defect removed, proving
the check goes quiet). A ninth arm mutates `flag_denominator_outliers` to compare against
the FIRST denominator seen rather than the DOMINANT one, and shows the mutant flags the
common case instead of the rare one — the argument for "dominant, not first" is not free
without this.

PATH GATED, THE NINETEENTH (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make identity-checks-selftest`, wired into
`make check` and `make ci-check` through `scripts/guard-scope.py`. The sentence that used to
sit here ("already covered by T7's harness sweep over the CLI surface") had gone stale for a
second, independent reason beyond the dead precedent it cited: `grep -rl identity_checks
harness/` names nothing — `harness/tests/t7_store_and_seams.py` drives `cli/cmd_cards.py`
through `cards_action = "variants"` and `"identity"` alone, never `"checks"`. The CLI cases
below now reach `cards checks`, `cards identity` and `cards photos` through `cmd_cards.run`.

THE CLI CASES NEED A STORE, THE FOUR CLASSES DO NOT. Each CLI case gets a fresh `BANCHI_HOME`
and removes it afterwards. The operator's store is never opened.

KNOWN DEFECTS ARE MARKED, NOT HIDDEN. A case the code does not yet meet prints `KNOWN` and
does not fail the run, so the open defect stays visible in every run. Once the defect is
fixed the marker reads `FAIL` until its `known_defect` line is removed.

`--mutant merge-identities` IS THE RED PROOF FOR THE IDENTITY CASE. It wraps
`master.Inventory.bind_sku` so every card binds to the first SKU seen. The distinct-identity
assertion must then go red. Run it through `verdict`, and without the flag to see green.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.identity_checks import (  # noqa: E402
    CardRecord,
    flag_denominator_outliers,
    flag_digit_count_outliers,
    flag_long_names,
    flag_near_duplicate_names,
)

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


def keys(flags) -> set:
    return {f.key for f in flags}


# ------------------------------------------------------------- class 1: long name


def test_long_name():
    print("class 1 — a name too long to be a card name")
    rules_text = (
        "While you control this battlefield, when you play a spell, if you spent 4 or "
        "more, PREDICT: (Look at the top card of your Main Deck. You may replace it.)"
    )
    cards = [
        CardRecord(key="box3/1", name=rules_text, set_name="Unleashed"),
        CardRecord(key="box3/2", name="Illaoi, Prophet of the Great Kraken", set_name="Unleashed"),
    ]
    flags = flag_long_names(cards)
    ok(keys(flags) == {"box3/1"}, "flags the rules-text name and only it", str(keys(flags)))

    clean = [CardRecord(key="box3/2", name="Illaoi, Prophet of the Great Kraken", set_name="Unleashed")]
    ok(flag_long_names(clean) == [], "quiet on a real, merely-long name")


# ------------------------------------------------------- class 2: denominator outlier


def test_denominator_outlier():
    print("class 2 — a denominator that disagrees with its set")
    # Origins: 298 is dominant (measured 291 of the real store; a handful here stands in),
    # one card reads 166.
    cards = (
        [CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)]
        + [CardRecord(key="origins/bad", number="102/166", set_name="Origins")]
    )
    flags = flag_denominator_outliers(cards)
    ok(keys(flags) == {"origins/bad"}, "flags only the disagreeing denominator", str(keys(flags)))

    clean = [CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)]
    ok(flag_denominator_outliers(clean) == [], "quiet when every denominator agrees")

    # A genuinely rare-but-real print carrying a different denominator (a special edition,
    # a promo reprint) is flagged exactly the same as a misread — this check cannot and does
    # not try to tell the two apart from stored data alone (D234's own boundary: one
    # disagreeing signal never resolves a claim on its own). It is a signal, never a verdict.
    rare_reprint = clean + [CardRecord(key="origins/reprint", number="1/300", set_name="Origins")]
    ok(
        "origins/reprint" in keys(flag_denominator_outliers(rare_reprint)),
        "a rare-but-real different denominator is flagged too — a signal, not a verdict",
    )


def test_denominator_outlier_mutation():
    print("class 2 mutation — dominant, not first-seen")

    def mutant_flag_denominator_outliers(cards):
        """The wrong fix: compare every denominator against the FIRST one this loop saw,
        instead of the one the majority of the set actually carries. Proves the real
        function's choice of `max(..., key=count)` is load-bearing rather than incidental.
        """
        from store.numbers import strip_set_code
        from pipeline.identity_checks import Flag, _CLEAN_NUMBER, _numbers_by_set

        out = []
        for _set_name, in_set in _numbers_by_set(cards).items():
            first_denom = None
            for card in in_set:
                match = _CLEAN_NUMBER.match(strip_set_code(card.number))
                if not match or not match.group(2):
                    continue
                if first_denom is None:
                    first_denom = match.group(2)
                elif match.group(2) != first_denom:
                    out.append(Flag(card.key, "denominator_outlier", "mutant"))
        return out

    # The one disagreeing card happens to be captured FIRST — the mutant then blames the
    # 298 majority instead of the 166 minority.
    cards = [CardRecord(key="origins/bad", number="102/166", set_name="Origins")] + [
        CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)
    ]
    mutant_flags = mutant_flag_denominator_outliers(cards)
    real_flags = flag_denominator_outliers(cards)
    ok(
        keys(mutant_flags) != {"origins/bad"} and keys(real_flags) == {"origins/bad"},
        "the mutant blames the majority; the real check still finds the minority",
        f"mutant={keys(mutant_flags)} real={keys(real_flags)}",
    )


# ------------------------------------------------------ class 3: digit count outlier


def test_digit_count_outlier():
    print("class 3 — more digits than the set has cards")
    cards = (
        [CardRecord(key=f"me01/{i}", number=f"{i:03d}", set_name="ME01: Mega Evolution") for i in range(1, 6)]
        + [CardRecord(key="me01/bad", number="0934", set_name="ME01: Mega Evolution")]
    )
    flags = flag_digit_count_outliers(cards)
    ok(keys(flags) == {"me01/bad"}, "flags only the 4-digit read in a 3-digit set", str(keys(flags)))

    clean = [CardRecord(key=f"me01/{i}", number=f"{i:03d}", set_name="ME01: Mega Evolution") for i in range(1, 6)]
    ok(flag_digit_count_outliers(clean) == [], "quiet when every digit count agrees")

    # Fewer digits than the dominant count is a different defect and is never flagged here.
    short = clean + [CardRecord(key="me01/short", number="5", set_name="ME01: Mega Evolution")]
    ok(
        "me01/short" not in keys(flag_digit_count_outliers(short)),
        "a SHORTER read is not this check's subject",
    )


# ---------------------------------------------------- class 4: near-duplicate name


def test_near_duplicate_name():
    print("class 4 — a name one edit from a sibling in the same set")
    cards = [
        CardRecord(key="vendetta/1", name="Shadow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/2", name="Shadbow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/3", name="Unrelated Card", set_name="Vendetta"),
    ]
    flags = flag_near_duplicate_names(cards)
    # Symmetric: both spellings are "one edit from a different name this store holds."
    ok(
        keys(flags) == {"vendetta/1", "vendetta/2"},
        "flags both sides of the glued misread, and only those",
        str(keys(flags)),
    )

    clean = [
        CardRecord(key="vendetta/1", name="Shadow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/3", name="Unrelated Card", set_name="Vendetta"),
    ]
    ok(flag_near_duplicate_names(clean) == [], "quiet with no sibling to be close to")

    # A different set's identical near-miss must never cross the boundary.
    cross_set = clean + [CardRecord(key="origins/x", name="Shadbow Temple", set_name="Origins")]
    ok(
        flag_near_duplicate_names(cross_set) == [],
        "a same-name near-miss in a DIFFERENT set is never flagged",
    )


def test_near_duplicate_name_measured_case():
    print("class 4 — the doc's own resolved-fine case is flagged too, honestly")
    # D239 names this pair as a real catch, and separately notes
    # the short title "resolved fine" on its own two other copies — the check cannot tell
    # the two apart from stored data alone, which is exactly why it routes to a human.
    cards = [
        CardRecord(key="sf/1", name="Draven, Glorious Executioner", set_name="Spiritforged"),
        CardRecord(key="sf/2", name="Draven, Glorious Executioner", set_name="Spiritforged"),
        CardRecord(key="sf/bad", name="Glorious Executioner", set_name="Spiritforged"),
    ]
    flags = flag_near_duplicate_names(cards)
    ok("sf/bad" in keys(flags), "the short title is flagged against its own full name")


# ----------------------------------------- the cards CLI (cli/cmd_cards.py), against a temp store

KNOWN = 0
MADE: List[Path] = []
PRODUCT_LINE = "Riftbound League of Legends Trading Card Game"


def _mutant_name() -> Optional[str]:
    if "--mutant" not in sys.argv:
        return None
    position = sys.argv.index("--mutant")
    return sys.argv[position + 1] if position + 1 < len(sys.argv) else None


MUTANT = _mutant_name()


def known_defect(condition: bool, label: str, defect: str, detail: str = "") -> None:
    """A case the code does not yet meet. Prints `KNOWN` and never fails the run, so the open
    defect shows in every run. A FIXED defect reads FAIL here, so its marker is removed with
    the fix instead of lingering."""
    global KNOWN, FAIL
    if condition:
        FAIL += 1
        print(f"  FAIL   {label}  {defect} is fixed: remove this known_defect marker")
    else:
        KNOWN += 1
        print(f"  KNOWN  {label}  open defect: {defect}  {detail}")


def fresh_home() -> Path:
    """A throwaway `BANCHI_HOME` for one case, so a row left by the last case can never be
    what a later assertion reads."""
    where = Path(tempfile.mkdtemp(prefix="banchi-idcheck."))
    MADE.append(where)
    os.environ["BANCHI_HOME"] = str(where)
    (where / "inventory").mkdir(parents=True, exist_ok=True)
    return where


def store_dump(home: Path) -> Tuple[Dict[str, list], Tuple[int, int]]:
    """Every row of every table, and the sizes of the database and its WAL. A press that
    changes ANY byte of the store shows here, not only in its census text."""
    from store import db

    path = db.path(home / "inventory")
    wal = path.with_name(path.name + "-wal")
    conn = sqlite3.connect(str(path))
    try:
        # A VIRTUAL TABLE (the FTS index) is left out: it is derived from `cards`, and reading
        # it as a plain table fails. Rows are compared sorted, so no table's order can hide or
        # fake a change. WITHOUT ROWID tables are read the same way.
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND sql NOT LIKE 'CREATE VIRTUAL%' ORDER BY name")]
        rows = {name: sorted(repr(row) for row in conn.execute(f'SELECT * FROM "{name}"'))
                for name in tables}
    finally:
        conn.close()
    return rows, (path.stat().st_size, wal.stat().st_size if wal.exists() else 0)


def run_cards(action: str, **options) -> Tuple[int, List[str]]:
    from cli import cmd_cards

    lines: List[str] = []
    args = types.SimpleNamespace(cards_action=action, **options)
    code = cmd_cards.run(args, lines.append)
    return code, lines


def sku_row(name: str, number: str, set_name: str):
    from store.skus import SkuRow

    return SkuRow(product_line=PRODUCT_LINE, set_name=set_name, product_name=name,
                  number=number, rarity="Common", condition="Near Mint", grade=None,
                  printing=None, first_seen=1, last_seen=1, source="selftest", raw={})


def seed_store(skus: dict, cards: list, *, identified: bool = True) -> Dict[str, str]:
    """`skus`: {sku: (name, number, set_name)}. `cards`: [(seed, sku, name, number,
    set_name)]. Each card is named by `sha256(seed)`, a photograph-shaped name with no file
    behind it. Returns {seed: card key}."""
    from store import master
    from store.session import Store

    keys: Dict[str, str] = {}
    with Store().write() as snapshot:
        for sku, (name, number, set_name) in skus.items():
            snapshot.skus.fold(sku, sku_row(name, number, set_name))
        for seed, sku, name, number, set_name in cards:
            card, _ = snapshot.inventory.allocate_capture(
                1, game="riftbound", cid=hashlib.sha256(seed.encode()).hexdigest())
            card.name, card.number, card.set_name, card.sku = name, number, set_name, sku
            if identified:
                card.state = master.IDENTIFIED
            keys[seed] = card.key
    return keys


MIND_RUNE_SKUS = {
    "CR-VEN-001": ("Mind Rune", "R03a", "Vendetta"),
    "CR-VEN-002": ("Mind Rune", "R03b", "Vendetta"),
}
MIND_RUNE_CARDS = [
    ("first", "CR-VEN-001", "Mind Rune", "R03a", "Vendetta"),
    ("second", "CR-VEN-002", "Mind Rune", "R03b", "Vendetta"),
]


def install_merge_mutant():
    """`--mutant merge-identities`: every `bind_sku` call binds the FIRST SKU this run saw.
    The patch lives in this process only, so no product file is touched. Returns the undo."""
    from store import master

    real = master.Inventory.bind_sku
    first: Dict[str, str] = {}

    def merged(self, key, sku, **kwargs):
        first.setdefault("sku", sku)
        return real(self, key, first["sku"], **kwargs)

    master.Inventory.bind_sku = merged
    return lambda: setattr(master.Inventory, "bind_sku", real)


def case_same_name_different_numbers_keep_distinct_identities() -> None:
    print("cards identity --write — two cards named alike, numbered apart, stay two identities")
    fresh_home()
    keys = seed_store(MIND_RUNE_SKUS, MIND_RUNE_CARDS)
    undo = install_merge_mutant() if MUTANT == "merge-identities" else None
    try:
        code, _lines = run_cards("identity", write=True)
    finally:
        if undo is not None:
            undo()

    from store import master
    from store.session import Store

    cards = Store().read().inventory.cards
    first, second = cards[keys["first"]], cards[keys["second"]]
    ok(code == 0, "the write exits 0", f"exit {code}")
    ok(
        (first.sku, second.sku) == ("CR-VEN-001", "CR-VEN-002"),
        "each card keeps its own SKU",
        f"first {first.sku}, second {second.sku}",
    )
    ok(
        (first.number, second.number) == ("R03a", "R03b"),
        "and its own number, so the same name does not merge them",
        f"first {first.number}, second {second.number}",
    )
    ok(
        first.identity_source == second.identity_source == master.IDENTITY_SKU,
        "both are bound by SKU (identity_source), not left on the read",
        f"{first.identity_source}, {second.identity_source}",
    )


def case_second_identity_write_changes_nothing() -> None:
    print("cards identity --write, twice — the second press is a no-op")
    home = fresh_home()
    seed_store(MIND_RUNE_SKUS, MIND_RUNE_CARDS)
    _code, first = run_cards("identity", write=True)
    ok(
        any("bound (T1/T2/T3/T4u, bound_by=migration): 2" in line for line in first),
        "the first press binds both cards, so the second has something to repeat",
        "; ".join(line for line in first if "bound" in line),
    )
    before, sizes_before = store_dump(home)
    _code, second = run_cards("identity", write=True)
    ok(
        any("bound (T1/T2/T3/T4u, bound_by=migration): 0" in line for line in second),
        "the second press binds nothing",
    )
    ok(
        any("already correctly bound, skipped: 2" in line for line in second),
        "and skips both cards as already correct",
    )
    after, sizes_after = store_dump(home)
    changed = sorted(
        name for name in set(before) | set(after) if before.get(name) != after.get(name)
    )
    ok(not changed, "no table changes on the second press", f"changed: {changed}")
    ok(sizes_before == sizes_after, "and the database and its WAL keep their sizes",
       f"{sizes_before} -> {sizes_after}")


def case_identity_preview_writes_nothing() -> None:
    print("cards identity, no --write — the preview writes nothing")
    home = fresh_home()
    seed_store(MIND_RUNE_SKUS, MIND_RUNE_CARDS)
    before = store_dump(home)
    code, lines = run_cards("identity", write=False)
    ok(
        any(" 2 derive, 0 held" in line for line in lines),
        "the preview finds both cards derivable, so the case can fail",
        "; ".join(line for line in lines if "derive" in line),
    )
    ok(code == 0 and any("Nothing was written" in line for line in lines),
       "and says it wrote nothing")
    ok(store_dump(home) == before, "every table and both file sizes are unchanged")


def seed_legacy_photographs(count: int) -> List[Tuple[str, int, int, bytes]]:
    """`count` photographs at the LEGACY `(box, index)` address, each named by its own digest,
    the way a store looks before `cards photos` has moved it. Returns (cid, box, index, bytes)."""
    from store import photos
    from store.session import Store

    blobs = [b"\xff\xd8" + hashlib.sha256(f"photo-{n}".encode()).digest() * 4
             for n in range(1, count + 1)]
    placed = []
    with Store().write() as snapshot:
        for blob in blobs:
            cid = hashlib.sha256(blob).hexdigest()
            card, _ = snapshot.inventory.allocate_capture(3, game="pokemon", cid=cid)
            placed.append((cid, card.box, card.index, blob))
    home = Path(os.environ["BANCHI_HOME"])
    for _cid, box, index, blob in placed:
        target = photos.legacy_path(box, index, home)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    return placed


def case_photos_limit_touches_at_most_n() -> None:
    print("cards photos --limit 2 — moves at most two photographs, and says so")
    home = fresh_home()
    from store import db, photos

    placed = seed_legacy_photographs(5)
    code, preview = run_cards("photos", write=False, limit=2)
    ok(
        code == 0 and any("moved=2" in line for line in preview),
        "the preview stops at two, so the case can fail",
        "; ".join(line for line in preview if "moved" in line),
    )
    ok(
        all(photos.legacy_path(box, index, home).is_file() for _c, box, index, _b in placed),
        "and the preview moves none of the five",
    )

    code, _lines = run_cards("photos", write=True, limit=2)
    moved = [(cid, box, index) for cid, box, index, _b in placed
             if photos.path(cid, home).is_file()]
    unmoved = [(cid, box, index) for cid, box, index, _b in placed
               if (cid, box, index) not in moved]
    ok(len(moved) <= 2, "at most two photographs reach their own name", f"{len(moved)} did")
    ok(len(moved) == 2, "and exactly two, the limit", f"{len(moved)} did")

    conn = sqlite3.connect(str(db.path(home / "inventory")))
    try:
        stamped = conn.execute(
            "SELECT count(*) FROM meta WHERE key = ?", (db.PHOTOS_RELOCATED,)
        ).fetchone()[0] == 1
    finally:
        conn.close()
    reachable = [photos.find(cid, box, index, relocated=stamped, home=home) is not None
                 for cid, box, index in unmoved]
    known_defect(
        all(reachable),
        "the three photographs not yet moved are still found after a partial write",
        "a --limit pass stamps photos_relocated, so the legacy address is never read again",
        f"stamped={stamped}, found {sum(reachable)} of {len(unmoved)}",
    )


def case_photos_limit_zero_moves_nothing() -> None:
    print("cards photos --limit 0 — previews no photographs")
    fresh_home()
    seed_legacy_photographs(3)
    _code, lines = run_cards("photos", write=False, limit=0)
    known_defect(
        any("moved=0" in line for line in lines),
        "`--limit 0` names zero photographs",
        "`if limit and` reads 0 as no limit, so it names all three",
        "; ".join(line for line in lines if "moved" in line),
    )


def case_cards_checks_reaches_the_cli() -> None:
    print("cards checks — a denominator outlier is flagged through the CLI, by key")
    fresh_home()
    keys = seed_store(
        {},
        [(f"origins-{n}", None, "Origins card", f"{n:03d}/298", "Origins")
         for n in range(1, 6)]
        + [("origins-bad", None, "Origins card", "102/166", "Origins")],
        identified=False,
    )
    code, lines = run_cards("checks", verbose=True)
    ok(code == 0, "the checks exit 0 on a store that has cards")
    ok(
        any(line.strip().startswith(f"{keys['origins-bad']}  ") for line in lines),
        "the minority denominator is listed under its own key",
        "; ".join(line for line in lines if "denominator" in line or "flag" in line),
    )
    ok(any("VERDICT: 1 flag(s)" in line for line in lines), "and the verdict counts one flag")


TESTS = [
    test_long_name,
    test_denominator_outlier,
    test_denominator_outlier_mutation,
    test_digit_count_outlier,
    test_near_duplicate_name,
    test_near_duplicate_name_measured_case,
    case_same_name_different_numbers_keep_distinct_identities,
    case_second_identity_write_changes_nothing,
    case_identity_preview_writes_nothing,
    case_photos_limit_touches_at_most_n,
    case_photos_limit_zero_moves_nothing,
    case_cards_checks_reaches_the_cli,
]


def main() -> int:
    saved = os.environ.get("BANCHI_HOME")
    try:
        for test in TESTS:
            test()
    finally:
        if saved is None:
            os.environ.pop("BANCHI_HOME", None)
        else:
            os.environ["BANCHI_HOME"] = saved
        for where in MADE:
            shutil.rmtree(where, ignore_errors=True)
    print()
    print(f"{PASS} passed, {FAIL} failed, {KNOWN} known defect(s) open")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
