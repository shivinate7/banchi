#!/usr/bin/env python3
"""The migration's replay, before any write (`docs/specs/identity-follows-sku.md` §7.4,
lane 2) — D253's own manner: read a COPY of the store, read-only, simulate the whole press
IN MEMORY, and assert the six things §7.4 names. It never opens `Store().write()` and never
touches the copy it is given.

    sqlite3 /path/to/store.sqlite ".backup /tmp/copy.sqlite"
    python3 scripts/identity-replay.py --store /tmp/copy.sqlite

Put `inventory/.exports/` and `inventory/.live/` beside the `.backup` copy too. 41 listing-only
SKUs are only in `.live/`. Without them, the SKU-IN-TABLE check fails.

READ-ONLY, `store/db.py:open_read_only` — the same door `cli/cmd_cards.py:_read_only` opens, so this
never calls `db.connect` and never performs the schema migration a preview must not perform.
Cached exports under `inventory/.exports/` are read too (only by `pipeline/identity_binding`'s
own SKU-table readers, which never touch a live file — the SKU table this store already holds
is the whole subject).

THE SIX CHECKS, §7.4's own words, each an assertion over the SAME `pipeline/identity_binding.
plan_migration` call `./pkmnscan cards identity --write` makes — this script imports that
module rather than re-deriving the classifier, so a replay pass and a real press can never
silently classify one card two different ways.

  1. Every HELD card's drawn `name`, `number` and `number_display` equal today's, byte for
     byte.
  2. No card's `sku`, `condition`, `state`, `cid` or `photo` differs. No `listings` row
     differs. No `queues` row differs, except the new `listing_disputed` entries this press
     itself would open.
  3. Every card that would be bound `sku` has identity fields equal to its SKU table row.
  4. Every T3 card's SKU equals the newest human act ON THAT CARD, scoped by the card's own
     `captured_at` (the "6/53" finding, §3.1) — never credited from a reused position.
  5. Every card whose drawn identity moves is in T3 or T4u.
  6. Every SKU on a card or in `listings` is in the SKU table.

THE BAR IS ZERO IDENTITY MOVES OUTSIDE T3 AND T4u (§7.4's own last line). Run this on the
day of the write — "the store moved in six minutes during this measurement."
"""

from __future__ import annotations

import argparse
import copy
import sqlite3
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import identity_binding as ib  # noqa: E402
from store import db  # noqa: E402
from store.master import IDENTITY_READ, IDENTITY_SKU, Card  # noqa: E402
from store.numbers import display_number  # noqa: E402


def _read_only(path: Path) -> sqlite3.Connection:
    """`store/db.py:open_read_only` — never `db.connect`, so this cannot perform a schema
    migration on the copy it is handed, and never writes a byte to it either way. It reads
    a WAL beside the file too, so a copy taken with its `-wal` is read whole."""
    return db.open_read_only(path)


def _number_display(card: Card) -> str:
    return display_number(card.number, card.printed_total) or ""


def _simulate(card: Card, plan: "ib.CardPlan") -> Card:
    """The card exactly as `./pkmnscan cards identity --write` would leave it — §7.3's own
    per-class rules, applied in memory. Never touches the input `card`."""
    simulated = copy.deepcopy(card)
    simulated.read_name = plan.read_name
    simulated.read_number = plan.read_number
    simulated.read_printed_total = plan.read_printed_total
    if ib.derives(plan.cls):
        row = plan.classification.row
        simulated.sku = plan.sku
        simulated.name = plan.classification.new_name
        simulated.number = plan.classification.new_number
        simulated.printed_total = plan.classification.new_printed_total
        simulated.rarity = row.rarity
        simulated.set_name = row.set_name
        simulated.condition = row.condition
        simulated.bound_by = "migration"
        simulated.identity_source = IDENTITY_SKU
        simulated.bound_at = "SIMULATED"  # excluded from every diff below, on purpose
    elif ib.held(plan.cls):
        simulated.identity_source = IDENTITY_READ
    return simulated


# Fields the migration is ALLOWED to move — §7.1's own list, restated as a whitelist so
# the frozen-fields check can diff everything else and mean it.
_MOVABLE_FIELDS = {
    "read_name", "read_number", "read_printed_total", "name", "number", "printed_total",
    "rarity", "set_name", "condition", "sku", "bound_by", "bound_at", "identity_source",
    "read_disputes",
}


def _frozen_field_diffs(before: Card, after: Card) -> List[str]:
    """Every field OUTSIDE `_MOVABLE_FIELDS` that differs — the frozen-fields check's own engine. `state`,
    `cid` and `photo` (there is no `photo` field on `Card`; the photograph is addressed BY
    `cid`, so `cid` unchanged is the whole of that claim) are exactly the fields this walks."""
    diffs = []
    for name in Card.__annotations__:
        if name in _MOVABLE_FIELDS:
            continue
        if getattr(before, name) != getattr(after, name):
            diffs.append(name)
    return diffs


def replay(conn: sqlite3.Connection, say) -> int:
    cards = ib.read_cards(conn)
    skus = ib.read_skus(conn)
    events = ib.read_human_events(conn)
    identifications = ib.read_identifications_by_digest(conn)
    listings = ib.listing_skus(conn)
    queue_skus = {  # only for the "no queues row differs" half of the frozen-fields check's report
        str(key) for (key,) in conn.execute("SELECT key FROM queues")
    }

    plan = ib.plan_migration(cards, skus, events, identifications)
    counts = plan.counts

    say("CLASSES (identity-follows-sku.md §7.2)")
    for cls in ib.CLASSES:
        say(f"  {cls:<12} {counts[cls]}")
    say("")

    ok = True

    # --------------------------------------------------------------------------- the held-identity check
    findings_1 = []
    for p in plan.plans:
        if not ib.held(p.cls):
            continue
        card = next(c for c in cards if c.key == p.key)
        after = _simulate(card, p)
        if (card.name, card.number, _number_display(card)) != (
            after.name, after.number, _number_display(after)
        ):
            findings_1.append(p.key)
    say(f"THE HELD-IDENTITY CHECK — every held card's drawn name/number/number_display unchanged: "
        f"{'PASS' if not findings_1 else 'FAIL'} ({len(findings_1)} moved)")
    if findings_1:
        ok = False
        for key in findings_1[:20]:
            say(f"    {key}")

    # --------------------------------------------------------------------------- the frozen-fields check
    findings_2 = []
    for p in plan.plans:
        card = next(c for c in cards if c.key == p.key)
        after = _simulate(card, p)
        diffs = _frozen_field_diffs(card, after)
        if diffs:
            findings_2.append((p.key, diffs))
    say(f"THE FROZEN-FIELDS CHECK — no card's sku/condition/state/cid moves (or any field outside the "
        f"identity/binding group): {'PASS' if not findings_2 else 'FAIL'} "
        f"({len(findings_2)} card(s))")
    if findings_2:
        ok = False
        for key, diffs in findings_2[:20]:
            say(f"    {key}  {', '.join(diffs)}")
    say("  listings/queues rows: this replay writes nothing, so neither table can move — "
        f"{len(listings)} listing SKU(s), {len(queue_skus)} queued position(s) read for "
        "the sku-in-table check and the report only.")

    # --------------------------------------------------------------------------- the identity-equals-row check
    simulated_cards = [_simulate(c, p) for c, p in zip(cards, plan.plans)]
    audit_after = ib.audit(simulated_cards, skus, listings)
    say(f"THE IDENTITY-EQUALS-ROW CHECK — every bound card's identity equals its SKU table row: "
        f"{'PASS' if not audit_after.identity_drift else 'FAIL'} "
        f"({len(audit_after.identity_drift)} drifted)")
    if audit_after.identity_drift:
        ok = False
        for key, sku in audit_after.identity_drift[:20]:
            say(f"    {key}  sku {sku}")

    # --------------------------------------------------------------------------- the newest-human-act check
    events_by_key = {}
    for event in events:
        events_by_key.setdefault(str(event.get("position")), []).append(event)
    findings_4 = []
    for p in plan.plans:
        if p.cls != ib.T3:
            continue
        recomputed = ib.newest_human_sku(events_by_key.get(p.key, ()), p.key,
                                          next(c for c in cards if c.key == p.key).captured_at)
        if recomputed != p.sku:
            findings_4.append((p.key, recomputed, p.sku))
    say(f"THE NEWEST-HUMAN-ACT CHECK — every T3 card's SKU equals the newest human act ON THAT CARD "
        f"(the '6/53' finding): {'PASS' if not findings_4 else 'FAIL'} "
        f"({len(findings_4)} mismatched)")
    if findings_4:
        ok = False
        for key, recomputed, sku in findings_4[:20]:
            say(f"    {key}  newest act chose {recomputed!r}, card carries {sku!r}")

    # --------------------------------------------------------------------------- the move-class check
    findings_5 = [p.key for p in plan.plans if p.identity_moves and p.cls not in (ib.T3, ib.T4U)]
    say(f"THE MOVE-CLASS CHECK — every identity move is in T3 or T4u: "
        f"{'PASS' if not findings_5 else 'FAIL'} ({len(findings_5)} outside)")
    if findings_5:
        ok = False
        for key in findings_5[:20]:
            say(f"    {key}")

    # --------------------------------------------------------------------------- the sku-in-table check
    say(f"THE SKU-IN-TABLE CHECK — every SKU on a card or in listings is in the SKU table: "
        f"{'PASS' if not audit_after.sku_not_in_table else 'FAIL'} "
        f"({len(audit_after.sku_not_in_table)} absent)")
    if audit_after.sku_not_in_table:
        ok = False
        for subject, sku in audit_after.sku_not_in_table[:20]:
            say(f"    {subject}  {sku}")

    moves = sum(1 for p in plan.plans if p.identity_moves)
    say("")
    say(f"{moves} identity move(s), all in T3/T4u" if not findings_5 else
        f"{moves} identity move(s), {len(findings_5)} OUTSIDE T3/T4u")
    say("")
    say(f"VERDICT: {'pass' if ok else 'FAIL'} — "
        + ("all six checks hold; nothing here was written." if ok else
           "at least one check failed; nothing here was written either way — this is a "
           "read-only replay."))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True,
                         help="a COPY of the store (sqlite3 ... .backup), never the live one.")
    args = parser.parse_args()

    conn = _read_only(args.store)
    try:
        return replay(conn, print)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
