#!/usr/bin/env python3
"""`pipeline/sku_name_contradictions.py`, proved against literal fixtures — no store, no
network. D242's own sibling, the mirror image: fixed number, disagreeing SKU there;
fixed SKU, disagreeing name here.

REUSES `pipeline.join.name_disputes` RATHER THAN A SECOND SIMILARITY RULE, and the mutation
arm below is what proves that matters: a naive EXACT-EQUALITY resolver (this module's
tempting first shape) would flag a genuine near-miss — a champion's short title beside its
own full name, the exact case `name_disputes`'s own docstring and D240's measurement both
name — as a contradiction it is not. `name_disputes` is not re-implemented here; the mutant
below stands in its place to prove the difference is real, not asserted.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import tcgcsv  # noqa: E402
from pipeline.sku_name_contradictions import (  # noqa: E402
    CardRecord,
    Catalog,
    find_contradictions,
    rank_candidates,
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


HEADER = list(tcgcsv.CANONICAL_HEADER)


def row(sku, name, number, condition="Near Mint", rarity="", set_name="Vendetta"):
    base = {c: "" for c in HEADER}
    base.update({
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.NAME_COLUMN: name,
        tcgcsv.NUMBER_COLUMN: number,
        tcgcsv.CONDITION_COLUMN: condition,
        tcgcsv.SET_COLUMN: set_name,
        tcgcsv.RARITY_COLUMN: rarity,
    })
    return base


def export(rows):
    return tcgcsv.Export(header=tuple(HEADER), rows=tuple(rows), source=None)


def card(key, state="identified", sku=None, name=None, game="riftbound", **kw):
    return CardRecord(key=key, state=state, sku=sku, name=name, game=game, **kw)


def test_agrees_no_finding():
    print("stored name agrees with its SKU's product name — no finding")
    cat = Catalog.from_export(export([row("SKU1", "Grumpy Rockbear", "84/166")]))
    c = card("a", sku="SKU1", name="Grumpy Rockbear")
    report = find_contradictions([c], {"riftbound": cat})
    ok(report.checked == 1, "the card was checked")
    ok(not report.disputes, "no dispute", str(report.disputes))
    ok(report.verdict == "pass", "verdict is pass", report.verdict)


def test_disputes_and_proposes_alternative():
    print("stored name disagrees — reported, and the real SKU proposed, never picked")
    cat = Catalog.from_export(export([
        row("SKU1", "Grumpy Rockbear", "39/166"),   # what SKU1 is currently claimed as
        row("SKU5", "Twilight Reveler", "10/166"),  # what the card's OWN name resolves to
    ]))
    c = card("a", sku="SKU1", name="Twilight Reveler")
    report = find_contradictions([c], {"riftbound": cat})
    ok(len(report.identified) == 1, "one identified dispute", str(report.identified))
    dispute = report.identified[0]
    ok(dispute.sku_row[tcgcsv.NAME_COLUMN] == "Grumpy Rockbear",
       "the SKU's own current product name is reported")
    ok(len(dispute.alternatives) == 1 and
       dispute.alternatives[0][tcgcsv.SKU_COLUMN] == "SKU5",
       "the export row actually named what the card reads is proposed",
       str(dispute.alternatives))
    ok(report.verdict == "fail", "verdict is fail", report.verdict)


def test_sold_card_own_section():
    print("a sold card's dispute lands in its own section, not identified's")
    cat = Catalog.from_export(export([row("SKU1", "Grumpy Rockbear", "39/166")]))
    c = card("a", state="sold", sku="SKU1", name="Twilight Reveler")
    report = find_contradictions([c], {"riftbound": cat})
    ok(len(report.sold) == 1 and not report.identified,
       "the dispute is in `sold`, not `identified`",
       f"sold={report.sold} identified={report.identified}")


def test_no_sku_not_a_subject():
    print("a card with no SKU is skipped, never counted as checked or not-known")
    c = card("a", sku=None, name="Whatever")
    report = find_contradictions([c], {})
    ok(report.checked == 0, "nothing checked")
    ok(not report.not_known, "not counted as not-known either", str(report.not_known))
    ok(report.skipped_no_sku == 1, "counted separately, as skipped")


def test_blank_name_not_known():
    print("a SKU with no stored name at all is `not known`, never a silent pass")
    cat = Catalog.from_export(export([row("SKU1", "Grumpy Rockbear", "39/166")]))
    c = card("a", sku="SKU1", name="   ")
    report = find_contradictions([c], {"riftbound": cat})
    ok(len(report.not_known) == 1, "one not-known", str(report.not_known))
    ok("no stored name" in report.not_known[0].reason, "reason names the blank name",
       report.not_known[0].reason)
    ok(report.checked == 0, "not counted as checked")


def test_no_export_for_game_not_known():
    print("no cached export for the card's game — `not known`, named")
    c = card("a", sku="SKU1", name="Twilight Reveler", game="pokemon")
    report = find_contradictions([c], {"riftbound": Catalog.from_export(export([]))})
    ok(len(report.not_known) == 1, "one not-known")
    ok("no cached export" in report.not_known[0].reason, "reason names the missing export",
       report.not_known[0].reason)


def test_sku_absent_from_export_not_known():
    print("the SKU is not in the export at all — `not known`, named")
    cat = Catalog.from_export(export([row("SKU9", "Someone Else", "1/166")]))
    c = card("a", sku="SKU1", name="Twilight Reveler")
    report = find_contradictions([c], {"riftbound": cat})
    ok(len(report.not_known) == 1, "one not-known")
    ok("absent from" in report.not_known[0].reason, "reason names the absence",
       report.not_known[0].reason)


def test_one_bad_card_never_hides_another_real_finding():
    print("a not-known card never suppresses a real dispute found on a different card — the "
          "one place this check's verdict amends `cards audit`'s own precedent")
    cat = Catalog.from_export(export([
        row("SKU1", "Grumpy Rockbear", "39/166"),
        row("SKU5", "Twilight Reveler", "10/166"),
    ]))
    cards = [
        card("a", sku="SKU1", name="Twilight Reveler"),  # a real dispute
        card("b", sku="SKU7", name="Whatever"),  # SKU7 absent -> not known
    ]
    report = find_contradictions(cards, {"riftbound": cat})
    ok(report.verdict == "fail", "the real dispute still fails the verdict, despite the "
       "other card being not-known", report.verdict)
    ok(len(report.not_known) == 1 and len(report.disputes) == 1,
       "both are reported, neither swallows the other")


def test_verdict_not_known_when_nothing_checked():
    print("verdict is `not known`, never a silent pass, when nothing at all could be checked")
    c = card("a", sku="SKU1", name="Twilight Reveler")
    report = find_contradictions([c], {})  # no catalogue for any game
    ok(report.checked == 0, "nothing was checked")
    ok(report.verdict == "not_known", "verdict is not_known, not pass", report.verdict)


def test_catalog_finds_any_condition_not_just_near_mint():
    print("the SKU's own row is found whatever its condition — this is not the listing "
          "path's Near-Mint-narrowed catalog")
    cat = Catalog.from_export(export([
        row("SKU1", "Grumpy Rockbear", "39/166", condition="Lightly Played"),
    ]))
    found = cat.row_for_sku("SKU1")
    ok(found is not None and found[tcgcsv.CONDITION_COLUMN] == "Lightly Played",
       "a non-Near-Mint row is still findable by SKU", str(found))


def test_rank_candidates_uses_set_hint():
    print("rank_candidates breaks a tie using the card's own set_hint claim")
    rows = [
        row("SKU5", "Twilight Reveler", "10/300", set_name="Origins"),
        row("SKU6", "Twilight Reveler", "10/166", set_name="Vendetta"),
    ]
    c = card("a", sku="SKU1", name="Twilight Reveler", set_hint="Vendetta")
    ranked = rank_candidates(rows, c)
    ok(ranked[0][tcgcsv.SKU_COLUMN] == "SKU6",
       "the row in the hinted set is ranked first", str(ranked))


def test_rank_candidates_no_claims_is_stable():
    print("with no capture claims at all, ranking is stable (ties broken by SKU)")
    rows = [
        row("SKU9", "Twilight Reveler", "10/300", set_name="Origins"),
        row("SKU6", "Twilight Reveler", "10/166", set_name="Vendetta"),
    ]
    c = card("a", sku="SKU1", name="Twilight Reveler")
    ranked = rank_candidates(rows, c)
    ok([r[tcgcsv.SKU_COLUMN] for r in ranked] == ["SKU6", "SKU9"],
       "no claims -> ties broken by SKU alone, deterministic", str(ranked))


def test_mutation_exact_equality_overflags_a_legitimate_near_miss():
    print("mutation — an EXACT-EQUALITY resolver wrongly flags a legitimate short-title "
          "variant that `name_disputes` correctly lets through")

    def mutant_disputes(card_name, product_name):
        """The tempting, wrong first shape: exact string equality instead of
        `pipeline.join.name_disputes`'s containment-then-ratio tolerance."""
        return (card_name or "").strip() != (product_name or "").strip()

    # `Repair Specialist` — a champion's short title — beside its own full name, exactly
    # `pipeline.join.name_disputes`'s own docstring's example shape.
    cat = Catalog.from_export(export([row("SKU1", "Zaun, Repair Specialist", "39/166")]))
    c = card("a", sku="SKU1", name="Repair Specialist")
    report = find_contradictions([c], {"riftbound": cat})
    mutant_flags_it = mutant_disputes(c.name, "Zaun, Repair Specialist")
    ok(not report.disputes and mutant_flags_it,
       "the real check lets the short title through; the mutant wrongly flags it",
       f"real_disputes={bool(report.disputes)} mutant_flags={mutant_flags_it}")


TESTS = [
    test_agrees_no_finding,
    test_disputes_and_proposes_alternative,
    test_sold_card_own_section,
    test_no_sku_not_a_subject,
    test_blank_name_not_known,
    test_no_export_for_game_not_known,
    test_sku_absent_from_export_not_known,
    test_one_bad_card_never_hides_another_real_finding,
    test_verdict_not_known_when_nothing_checked,
    test_catalog_finds_any_condition_not_just_near_mint,
    test_rank_candidates_uses_set_hint,
    test_rank_candidates_no_claims_is_stable,
    test_mutation_exact_equality_overflags_a_legitimate_near_miss,
]


def main() -> int:
    for test in TESTS:
        test()
    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
