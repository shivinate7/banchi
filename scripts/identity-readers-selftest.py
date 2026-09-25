#!/usr/bin/env python3
"""The evidence readers (docs/specs/identity-follows-sku.md §5.1, lane 4) — proved against
the exact defect a review found in `c8cbb8a1`, HIGH, 2026-09-24.

THE DEFECT. Lane 4's first draft read `card.read_name`/`card.read_number`/
`card.read_printed_total` unconditionally in both `cli/requeue.py:identified` and
`cli/resolve.py:store_payload`. MEASURED on a copy of the owner's real store: every existing
card carries `read_name is None` — nothing has ever backfilled it — so `identified()`
answered `None` for every open entry (`queue refresh` became a silent, store-wide no-op with
a false reason) and `store_payload()` built `{"name": None, "number": None}` for a card that
had plainly been identified, filing it into review as if it had never been read at all.

THE RULE, in `cli/resolve.py:card_reading` (the one helper both builders call — see its own
docstring). `card.identity_source != IDENTITY_SKU` (the card is not SKU-bound):
`record_identification` has ALWAYS written the reading into `name`/`number` too (`store/
master.py`'s own "on a card with no SKU the identity follows the read"), so the reading is
`read_*` where it is set, else `name`/`number` — the same reading, carried by whichever
field the card's OWN identification actually wrote to. `card.identity_source ==
IDENTITY_SKU` (the card IS bound): `name`/`number`/`printed_total` are the bound SKU's own
catalog row, never a reading, so only `read_*` may answer — and where `read_*` was never
recorded (bound by a migration, or bound before this call ever wired `record_identification`
to a live identification), THERE IS NO READING, and the card is refused loudly rather than
silently compared against itself.

THREE FIXTURES, never a synthetic shape neither builder will ever actually see:

- `UNBOUND_OLD` — never bound, `read_*` is `None` (a card identified before lane 1 existed).
  Its identity fields ARE its only recorded reading. Both builders must carry it.
- `BOUND_DISPUTED` — bound to a SKU, identity fields hold the SKU's own catalog row,
  `read_*` holds a DIFFERENT name — a real dispute (D253's own subject). Both builders must
  carry the READ name, never the catalog's.
- `BOUND_NO_EVIDENCE` — bound to a SKU, `read_*` is `None`. Neither builder may echo the
  catalog identity or file a blank success; both must refuse loudly and name why —
  `cli/requeue.py:NoEvidenceRecorded` there, `identification: None` with `status:
  "no_reading"` here.

THREE MUTATIONS, each its own `--mutate-*` invocation (`price-postings-selftest`'s own
two-process shape, `scripts/price-postings-selftest.py`, extended to three), each isolated
to ONE `cli/resolve.py:card_reading` body, `.bak`-COPY PROTECTED (never `git checkout` — the
lesson `scripts/docs-audit.py`'s own `derived numbers` row already paid for). Each is RED on
exactly the case(s) it breaks and GREEN everywhere else, proving the assertions actually
exercise the code rather than a fixture that always agrees:

1. `--mutate-identity-fields` — REVERTED TO `card.name` (the ORIGINAL pre-lane-4 shape,
   before `read_*` existed at all): breaks `BOUND_DISPUTED` (answers the catalog name, the
   dispute vanishes) and `BOUND_NO_EVIDENCE` (never refuses — the exact "compare the SKU
   against itself" hole). `UNBOUND_OLD` still passes, because its identity fields are its
   reading either way.
2. `--mutate-no-fallback` — THE FALLBACK REMOVED (`read_*` read unconditionally, lane 4's
   FIRST draft, the bug this file exists to catch): breaks `UNBOUND_OLD` (answers a blank
   reading for a plainly identified card) and `BOUND_NO_EVIDENCE` (answers `READING_NONE`,
   the wrong REASON, not `READING_UNAVAILABLE` — a silent generic skip standing in for a
   named refusal). `BOUND_DISPUTED` still passes, because its `read_*` was always populated.
3. `--mutate-no-refusal` — THE REFUSAL LINE ALONE REMOVED (`if bound and not touched: return
   CardReading(READING_UNAVAILABLE)` deleted, everything else intact) — the single most
   targeted proof of "a card must be refused loudly, never silently compared against
   itself": breaks ONLY `BOUND_NO_EVIDENCE`, which then falls through to the identity
   fields exactly as mutation 1 does. `UNBOUND_OLD` and `BOUND_DISPUTED` are both
   unaffected by this one line and stay green.

Each `--mutate-*` run is its OWN PROCESS (the Makefile recipe runs this file four times),
so a mutated `cli/resolve.py` is read fresh by that process's own `import` and never leaks
into any other invocation — no `importlib.reload` anywhere in this file. The `finally`
block restores the `.bak` copy before the process exits either way, so a crash mid-mutation
still leaves `cli/resolve.py` exactly as it was.

IN `make check`, NEVER IN THE GIT HOOK — no store, no `mktemp`, `Inventory`/`Card` built
in memory the way `scripts/identity-store-selftest.py` already does, that self-test's own
precedent applied to lane 4's own two callers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import master  # noqa: E402

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


# ------------------------------------------------------------------------------ the fixtures

UNBOUND_OLD = "4/10"
BOUND_DISPUTED = "4/17"
BOUND_NO_EVIDENCE = "4/23"


def build_inventory() -> master.Inventory:
    inventory = master.Inventory()
    inventory.cards[UNBOUND_OLD] = master.Card(
        box=4, index=10,
        name="Old Reading Name", number="5/10", printed_total="10",
        game="pokemon", confidence="high",
        # NEVER BOUND, NEVER TOUCHED BY THE NEW WRITE PATH — every `read_*` field is the
        # Python default `None`, exactly what a card identified before lane 1 existed
        # carries forever, absent a backfill.
    )
    inventory.cards[BOUND_DISPUTED] = master.Card(
        box=4, index=17,
        # THE SKU'S OWN CATALOG ROW — what `Inventory.bind_sku` would have stamped.
        name="Catalog Name (the SKU's own row)", number="017/198", printed_total="198",
        # THE MODEL'S ACTUAL READING — different from the catalog's, a real dispute.
        read_name="Misread Evidence Name", read_number="017/198", read_printed_total="198",
        game="pokemon", confidence="high",
        sku="123456", bound_by="join", identity_source=master.IDENTITY_SKU,
        read_disputes=True,
    )
    inventory.cards[BOUND_NO_EVIDENCE] = master.Card(
        box=4, index=23,
        name="Catalog Name, No Evidence Recorded", number="020/198", printed_total="198",
        # `read_*` all default to `None` — bound by a migration, or bound before this
        # call was ever wired to record a live identification's evidence.
        game="pokemon", confidence="high",
        sku="999999", bound_by="migration", identity_source=master.IDENTITY_SKU,
    )
    return inventory


# ------------------------------------------------------------------------------- one pass


def run_suite(requeue_module, resolve_module) -> None:
    inventory = build_inventory()
    views: Dict[int, object] = {}

    # ------------------------------------------------------------- UNBOUND_OLD
    card = inventory.cards[UNBOUND_OLD]
    built = requeue_module.identified(card, views)
    ok(built is not None and built.name == "Old Reading Name" and built.number == "5/10"
       and built.printed_total == "10",
       "requeue.identified carries an old, unbound card's identity fields as its reading "
       "(read_* was never touched, so the identity fields ARE the reading)",
       built)

    payload = resolve_module.store_payload([UNBOUND_OLD], inventory)
    record = payload["cards"][UNBOUND_OLD]
    ok(record["status"] == "succeeded"
       and record["identification"] is not None
       and record["identification"]["name"] == "Old Reading Name"
       and record["identification"]["number"] == "5/10",
       "resolve.store_payload carries the same old reading, never {'name': None, "
       "'number': None} for a plainly-identified card",
       record)

    # ---------------------------------------------------------- BOUND_DISPUTED
    card = inventory.cards[BOUND_DISPUTED]
    built = requeue_module.identified(card, views)
    ok(built is not None and built.name == "Misread Evidence Name"
       and built.number == "017/198",
       "requeue.identified carries the DISPUTED read name on a bound card, never the "
       "catalog's own name — the D253 comparison this lane exists to keep alive",
       built)

    payload = resolve_module.store_payload([BOUND_DISPUTED], inventory)
    record = payload["cards"][BOUND_DISPUTED]
    ok(record["status"] == "succeeded"
       and record["identification"] is not None
       and record["identification"]["name"] == "Misread Evidence Name",
       "resolve.store_payload carries the same disputed read name, never the catalog's",
       record)

    # ------------------------------------------------------- BOUND_NO_EVIDENCE
    card = inventory.cards[BOUND_NO_EVIDENCE]
    raised = None
    try:
        requeue_module.identified(card, views)
    except requeue_module.NoEvidenceRecorded as exc:
        raised = exc
    ok(raised is not None,
       "requeue.identified REFUSES a bound card with no recorded evidence — "
       "NoEvidenceRecorded, never a silent fall-through to the catalog identity",
       raised)

    payload = resolve_module.store_payload([BOUND_NO_EVIDENCE], inventory)
    record = payload["cards"][BOUND_NO_EVIDENCE]
    ok(record["identification"] is None
       and record["status"] != "succeeded"
       and bool(record["error"]),
       "resolve.store_payload REFUSES the same card — identification: None, a named "
       "status and a named error, never a blank or catalog-echoing success",
       record)


# --------------------------------------------------------------------------- the mutations
#
# EACH VALUE IS `(label, before, after)`, text substituted once in `cli/resolve.py`'s own
# source, verbatim — see `card_reading`'s definition there for the anchor.

_ORIGINAL_BODY = (
    'bound = card.identity_source == master.IDENTITY_SKU\n'
    '    touched = card.read_name is not None\n'
    '    if bound and not touched:\n'
    '        return CardReading(READING_UNAVAILABLE)\n'
    '    if touched:\n'
    '        name = card.read_name or ""\n'
    '        number = (card.read_number or "").strip() or None\n'
    '        total = (card.read_printed_total or "").strip() or None\n'
    '    else:\n'
    '        # UNBOUND, NEVER TOUCHED BY THE NEW WRITE PATH — a card identified before lane 1\n'
    '        # existed. Its identity fields are the only reading this store has ever recorded\n'
    '        # for it (`record_identification`\'s own "identity follows the read" rule, run\n'
    '        # every time under the OLD code this card was last identified under).\n'
    '        name = card.name or ""\n'
    '        number = (card.number or "").strip() or None\n'
    '        total = (card.printed_total or "").strip() or None\n'
    '    if not name and not number:\n'
    '        return CardReading(READING_NONE)\n'
    '    return CardReading(READING_OK, name, number, total if number else None)'
)

_TAIL = (
    'if not name and not number:\n'
    '        return CardReading(READING_NONE)\n'
    '    return CardReading(READING_OK, name, number, total if number else None)'
)

MUTATIONS: Dict[str, "tuple[str, str, str]"] = {
    "identity-fields": (
        "reverted to card.name (the original pre-lane-4 shape)",
        _ORIGINAL_BODY,
        'name = card.name or ""\n'
        '    number = (card.number or "").strip() or None\n'
        '    total = (card.printed_total or "").strip() or None\n'
        '    ' + _TAIL,
    ),
    "no-fallback": (
        "the read_* fallback removed (lane 4's first, broken draft)",
        _ORIGINAL_BODY,
        'name = card.read_name or ""\n'
        '    number = (card.read_number or "").strip() or None\n'
        '    total = (card.read_printed_total or "").strip() or None\n'
        '    ' + _TAIL,
    ),
    "no-refusal": (
        "the refusal line alone removed",
        '    if bound and not touched:\n'
        '        return CardReading(READING_UNAVAILABLE)\n'
        '    if touched:\n',
        '    if touched:\n',
    ),
}


def run_mutated(key: str) -> int:
    label, before, after = MUTATIONS[key]
    resolve_path = ROOT / "cli" / "resolve.py"
    original = resolve_path.read_text(encoding="utf-8")
    if before not in original:
        print(f"MUTATION SETUP FAILED: the anchor text for {label!r} is not present — "
              "card_reading's source moved; update this self-test's anchor")
        return 1
    bak_path = resolve_path.with_suffix(".py.bak")
    bak_path.write_text(original, encoding="utf-8")
    try:
        mutated = original.replace(before, after, 1)
        if mutated == original:
            print(f"MUTATION SETUP FAILED: {label!r} did not change the file")
            return 1
        resolve_path.write_text(mutated, encoding="utf-8")
        import cli.resolve as resolve_module  # imported fresh, AFTER the write
        import cli.requeue as requeue_module
        try:
            run_suite(requeue_module, resolve_module)
        except Exception as exc:  # noqa: BLE001 — a crash under mutation IS a failure
            import traceback
            traceback.print_exc()
            global FAIL
            FAIL += 1
            print(f"  FAIL   suite raised {exc!r} — counted as a failure, not swallowed")
    finally:
        resolve_path.write_text(original, encoding="utf-8")
        bak_path.unlink()

    print(f"\nidentity-readers self-test [MUTATED: {label}]: {PASS} passed"
          + (f", {FAIL} FAILED" if FAIL else ""))
    if FAIL == 0:
        print(f"MUTATION SURVIVED — {label!r} did not turn any assertion above red. "
              "This case is not actually being tested.")
        return 1
    print(f"mutation caught: {label!r} turns the suite red, exactly as it must.")
    return 0


def main() -> int:
    mutate_flags = {
        "--mutate-identity-fields": "identity-fields",
        "--mutate-no-fallback": "no-fallback",
        "--mutate-no-refusal": "no-refusal",
    }
    mutate = None
    for flag, key in mutate_flags.items():
        if flag in sys.argv[1:]:
            mutate = key
            break

    if mutate is not None:
        return run_mutated(mutate)

    import cli.resolve as resolve_module
    import cli.requeue as requeue_module
    run_suite(requeue_module, resolve_module)
    print("\nidentity-readers self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
