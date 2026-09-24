#!/usr/bin/env python3
"""`pipeline/identity_binding.py` — the migration's classifier and the merged D242/D255
report (`docs/specs/identity-follows-sku.md` §5.5, §7, lane 2) — proved against literal
fixtures. No store, no network, no `Store()` — every function under test is pure, over plain
`store.master.Card`/`store.skus.SkuRow` objects built in memory.

WHAT THIS PROVES, in the lane's own words (§11's "done when" line): "every class and its
order, the human-bound exclusion, and both report halves."

  EVERY CLASS, IN ORDER   one arm per T1/T2/T3/T4s/T4u/T5/T6/`sku_unknown`, plus one arm
                          proving T3 is tested BEFORE T5 — a human act on a disputing read
                          must derive, never hold, because ordering is the whole of §7.2's
                          table.
  THE HUMAN-BOUND          §5.5's own exclusion: `audit()`'s name half/number half must
  EXCLUSION                 never flag a card `bound_by` an `answer`/`group_answer`/
                          `correction`/`confirm` act, even when its read genuinely disputes
                          its row — "a human who chose that SKU off the photograph has
                          already answered the report's question."
  BOTH REPORT HALVES       §4.3's three audit failures (identity drift, SKU absent from the
                          table, rarity disagreement) AND §5.5's name half/number half —
                          proved to fire and proved to stay silent when nothing is wrong
                          (`verification-cry-wolf-guard-is-spent`'s own worry).

Every arm is a MEASUREMENT or a REFUSAL over a fixture built to need it, never a
restatement of the code — `scripts/identity-store-selftest.py`'s own rule, carried over.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import identity_binding as ib  # noqa: E402
from store.master import (  # noqa: E402
    IDENTIFIED,
    IDENTITY_SKU,
    Card,
)
from store.skus import SkuRow  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: object = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail != "":
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


# ------------------------------------------------------------------------------ the fixtures


def sku_row(
    sku: str, name: str, number: str, *, line: str = "Pokemon", set_name: str = "Sword & Shield",
    rarity: str = "Common", market: str = "1.00",
) -> SkuRow:
    """One `SkuRow`, the six fact cells and a `raw` shaped exactly as `pipeline/skus.py:
    row_from_csv` builds it, so `held_review_candidates`'s own reads off `.raw` (the SKU,
    the market price) have something real to find."""
    return SkuRow(
        product_line=line, set_name=set_name, product_name=name, number=number,
        rarity=rarity, condition="Near Mint", grade="Near Mint", printing=None,
        first_seen=1, last_seen=1, source="fixture.csv", raw={
            "TCGplayer Id": sku, "Product Line": line, "Set Name": set_name,
            "Product Name": name, "Number": number, "Rarity": rarity,
            "Condition": "Near Mint", "TCG Market Price": market,
        },
    )


def card(
    key_suffix: int, *, sku: Optional[str], game: str = "pokemon", state: str = IDENTIFIED,
    name: Optional[str] = None, number: Optional[str] = None, printed_total: Optional[str] = None,
    cid: Optional[str] = None, captured_at: str = "2026-01-01T00:00:00+00:00",
    identity_source: Optional[str] = None, bound_by: Optional[str] = None,
    read_name: Optional[str] = None, read_number: Optional[str] = None,
    read_printed_total: Optional[str] = None,
) -> Card:
    return Card(
        box=1, index=key_suffix, sku=sku, game=game, state=state, captured_at=captured_at,
        name=name, number=number, printed_total=printed_total, cid=cid,
        identity_source=identity_source, bound_by=bound_by, read_name=read_name,
        read_number=read_number, read_printed_total=read_printed_total,
    )


def main() -> int:
    # ------------------------------------------------------------------ number_agrees (§6)
    print("number_agrees (§6, 'equal or blank')")
    ok(ib.number_agrees("number_and_printed_total", "24", "132", "024/132"),
       "Pokemon: zero-padded read composes to the row's own cell")
    ok(ib.number_agrees("number_and_printed_total", None, None, "024/132"),
       "Pokemon: blank read is no evidence — agrees")
    ok(ib.number_agrees("number_and_printed_total", "24", None, "024/132"),
       "Pokemon: half a pair (no denominator) is blank too — agrees")
    ok(not ib.number_agrees("number_and_printed_total", "61", "298", "276/298"),
       "Pokemon: a genuinely different number disagrees")
    ok(ib.number_agrees("printed_code", "179/298", None, "179/298"),
       "Riftbound: verbatim match agrees")
    ok(ib.number_agrees("printed_code", "UNL - 150/219", None, "150/219"),
       "Riftbound: a glued set code strips (D55/D67) and then agrees")
    ok(ib.number_agrees("printed_code", None, None, "150/219"),
       "Riftbound: blank read agrees")
    ok(not ib.number_agrees("printed_code", "179/298", None, "066a/298"),
       "Riftbound: a genuinely different identifier disagrees")

    # ------------------------------------------------------------------- name_fold_matches
    print("\nname_fold_matches (T1's own test)")
    ok(ib.name_fold_matches("Pikachu", "Pikachu"), "byte-identical folds equal")
    ok(ib.name_fold_matches("pikachu", "Pikachu"), "case is folded")
    ok(ib.name_fold_matches("Stufful - 111/132", "Stufful"),
       "an embedded collector number is folded away on the read side too")
    ok(ib.name_fold_matches("Rengar, Unseen", "Rengar, Unseen (Alternate Art)"),
       "a catalog qualifier is folded away — this is the FOLD test, not the uniqueness one")
    ok(not ib.name_fold_matches("Corfish", "Corphish"), "a near miss is NOT an exact fold")
    ok(not ib.name_fold_matches("", "Pikachu"), "a blank read matches nothing")

    # --------------------------------------------------------- product ambiguity (D162)
    print("\ndistinct_products_by_line / matching_products (D162, T4s vs T4u)")
    unique_skus: Dict[str, SkuRow] = {
        "300": sku_row("300", "Aspirant's Climb", "276/298"),
    }
    by_line = ib.distinct_products_by_line(unique_skus)
    unique_products = ib.matching_products("Aspirant's Climb", by_line["Pokemon"])
    ok(len(unique_products) == 1, "one product named 'Aspirant's Climb' -> unique (T4u)",
       unique_products)

    ambiguous_skus: Dict[str, SkuRow] = {
        "301": sku_row("301", "Swain, Visionary", "065/100"),
        "302": sku_row("302", "Swain, Visionary", "065/166"),
    }
    by_line2 = ib.distinct_products_by_line(ambiguous_skus)
    ambiguous_products = ib.matching_products("Swain, Visionary", by_line2["Pokemon"])
    ok(len(ambiguous_products) == 2,
       "two products share 'Swain, Visionary' -> ambiguous (T4s)", ambiguous_products)

    two_conditions: Dict[str, SkuRow] = {
        "303": sku_row("303", "Pikachu", "025/202"),
        "304": sku_row("304", "Pikachu", "025/202", rarity="Common"),
    }
    dedup_line = ib.distinct_products_by_line(two_conditions)
    ok(len(dedup_line["Pokemon"]) == 1,
       "two SKUs, same (set, name, number) — one PRODUCT, conditions collapsed",
       dedup_line["Pokemon"])

    # ------------------------------------------------------------- newest_human_sku (§3.1)
    print("\nnewest_human_sku (§3.1's '6/53' finding, the replay's own newest-human-act check)")
    events = [
        {"at": "2026-01-01T00:00:00+00:00", "event": "answered", "position": "1/1",
         "sku": "111"},
    ]
    ok(ib.newest_human_sku(events, "1/1", "2026-01-01T00:00:00+00:00") == "111",
       "one qualifying answered event is found")
    ok(ib.newest_human_sku(events, "1/2", "2026-01-01T00:00:00+00:00") is None,
       "a different position finds nothing")
    ok(ib.newest_human_sku([], "1/1", "2026-01-01T00:00:00+00:00") is None,
       "no events at all -> None, never a guess")

    reused_position = [
        {"at": "2026-01-01T00:00:00+00:00", "event": "answered", "position": "1/1",
         "sku": "OLD-SKU"},
    ]
    ok(ib.newest_human_sku(reused_position, "1/1", "2026-02-01T00:00:00+00:00") is None,
       "an answer BEFORE this card's own captured_at belongs to the card that used to sit "
       "at this position (the '6/53' finding) — never credited to this one")

    newest_wins = [
        {"at": "2026-01-01T00:00:00+00:00", "event": "answered", "position": "1/1",
         "sku": "111"},
        {"at": "2026-01-02T00:00:00+00:00", "event": "sku_corrected", "position": "1/1",
         "sku": "222"},
    ]
    ok(ib.newest_human_sku(newest_wins, "1/1", "2026-01-01T00:00:00+00:00") == "222",
       "the NEWEST human act wins — a correction overrides its own earlier answer")

    # ---------------------------------------------------------------- backfill_read (§3.4)
    print("\nbackfill_read (§3.4, keyed by photograph digest)")
    identifications = {
        "digest-a": {"identification": {"name": "Read Name", "number": "1",
                                         "printed_total": "236"}},
    }
    ok(ib.backfill_read("digest-a", identifications, "Old", "0", "0")
       == ("Read Name", "1", "236"),
       "a matching digest wins over the card's current fields")
    ok(ib.backfill_read("digest-missing", identifications, "Old", "0", "0")
       == ("Old", "0", "0"),
       "no matching digest falls back to the card's current fields")
    ok(ib.backfill_read(None, identifications, "Old", "0", "0") == ("Old", "0", "0"),
       "no cid at all falls back too — never a KeyError")

    # ------------------------------------------------------------------- classify_card
    print("\nclassify_card — every class, tested in §7.2's own order")

    pokemon_row = sku_row("400", "Pikachu", "025/202")
    products = {"Pokemon": [pokemon_row]}

    t1 = ib.classify_card(
        sku="400", game="pokemon", row=pokemon_row, read_name="Pikachu",
        read_number="25", read_printed_total="202", human_sku=None,
        products_by_line=products,
    )
    ok(t1.cls == ib.T1 and t1.new_name == "Pikachu" and t1.new_number == "025",
       "T1: exact fold match, number agrees — derives", t1)

    t2 = ib.classify_card(
        sku="400", game="pokemon", row=pokemon_row, read_name="Pikcahu",
        read_number="25", read_printed_total="202", human_sku=None,
        products_by_line=products,
    )
    ok(t2.cls == ib.T2, "T2: a near miss, not disputed, number agrees — derives", t2)

    t3 = ib.classify_card(
        sku="400", game="pokemon", row=pokemon_row, read_name="totally wrong reading",
        read_number="999", read_printed_total="999", human_sku="400",
        products_by_line=products,
    )
    ok(t3.cls == ib.T3 and t3.new_name == "Pikachu",
       "T3: a human act chose this exact SKU — derives, EVEN THOUGH the read disputes it "
       "on both name and number (ordering: T3 is tested before T5)", t3)

    t4u_row = sku_row("401", "Aspirant's Climb", "276/298")
    t4u = ib.classify_card(
        sku="401", game="pokemon", row=t4u_row, read_name="Aspirant's Climb",
        read_number="61", read_printed_total="298", human_sku=None,
        products_by_line={"Pokemon": [t4u_row]},
    )
    ok(t4u.cls == ib.T4U and t4u.new_number == "276",
       "T4u: number disagrees, name names exactly one product (D162) — derives", t4u)

    swain_a = sku_row("402", "Swain, Visionary", "065/100")
    swain_b = sku_row("403", "Swain, Visionary", "065/166")
    t4s = ib.classify_card(
        sku="402", game="pokemon", row=swain_a, read_name="Swain, Visionary",
        read_number="065", read_printed_total="166", human_sku=None,
        products_by_line={"Pokemon": [swain_a, swain_b]},
    )
    ok(t4s.cls == ib.T4S,
       "T4s: number disagrees, name names two products — HELD, never derives", t4s)

    t5 = ib.classify_card(
        sku="400", game="pokemon", row=pokemon_row, read_name="Something else entirely",
        read_number="25", read_printed_total="202", human_sku=None,
        products_by_line=products,
    )
    ok(t5.cls == ib.T5, "T5: read name disputes the row, no human act — HELD", t5)

    t5_blank = ib.classify_card(
        sku="400", game="pokemon", row=pokemon_row, read_name=None,
        read_number="25", read_printed_total="202", human_sku=None,
        products_by_line=products,
    )
    ok(t5_blank.cls == ib.T5, "T5: a blank read name — HELD, never a guessed agreement",
       t5_blank)

    t6 = ib.classify_card(
        sku=None, game="pokemon", row=None, read_name="Bulbasaur", read_number="1",
        read_printed_total="202", human_sku=None, products_by_line=products,
    )
    ok(t6.cls == ib.T6, "T6: no SKU at all — nothing to derive", t6)

    unknown = ib.classify_card(
        sku="999999", game="pokemon", row=None, read_name="Mystery", read_number="1",
        read_printed_total="1", human_sku=None, products_by_line=products,
    )
    ok(unknown.cls == ib.SKU_UNKNOWN,
       "a SKU absent from the table — sku_unknown, bind_sku would refuse it too", unknown)

    ok(ib.derives(ib.T1) and ib.derives(ib.T2) and ib.derives(ib.T3) and ib.derives(ib.T4U),
       "derives() is exactly T1/T2/T3/T4u")
    ok(ib.held(ib.T4S) and ib.held(ib.T5) and not ib.held(ib.T1),
       "held() is exactly T4s/T5")
    ok(not (set(ib.DERIVING_CLASSES) & set(ib.HELD_CLASSES)),
       "no class is ever both — the ladder's own invariant")

    # ------------------------------------------------------------------- audit() — §4.3
    print("\naudit() — §4.3's three failures, silent when nothing is wrong")
    clean_row = sku_row("500", "Charmander", "004/202")
    clean_card = card(
        1, sku="500", identity_source=IDENTITY_SKU, bound_by="migration",
        name="Charmander", number="004", printed_total="202",
    )
    clean_card.rarity = clean_row.rarity
    clean_card.set_name = clean_row.set_name
    clean_card.condition = clean_row.condition
    findings = ib.audit([clean_card], {"500": clean_row}, set())
    ok(not findings.identity_drift and not findings.sku_not_in_table
       and not findings.rarity_disagreement,
       "a correctly-bound card, alone, raises NOTHING — a guard silent when it should be",
       findings)

    drifted_row = sku_row("501", "Squirtle (reprint)", "007/202")
    drifted_card = card(
        2, sku="501", identity_source=IDENTITY_SKU, bound_by="migration",
        name="Squirtle", number="007", printed_total="202",
    )
    findings2 = ib.audit([drifted_card], {"501": drifted_row}, set())
    ok(findings2.identity_drift == [(drifted_card.key, "501")],
       "a bound card whose stored identity no longer equals its SKU row — CAUGHT",
       findings2.identity_drift)

    missing_card = card(3, sku="502")
    findings3 = ib.audit([missing_card], {}, {"777"})
    ok((missing_card.key, "502") in findings3.sku_not_in_table,
       "a card whose SKU is absent from the table — CAUGHT")
    ok(("listings", "777") in findings3.sku_not_in_table,
       "a `listings` SKU absent from the table — CAUGHT too (§4.3's second bullet)")

    disagreeing = {
        "503": sku_row("503", "Charmander", "004/202", rarity="Common"),
        "504": sku_row("504", "Charmander", "004/202", rarity="Rare"),
    }
    findings4 = ib.audit([], disagreeing, set())
    ok(len(findings4.rarity_disagreement) == 1,
       "one product whose SKUs disagree on rarity — CAUGHT (§4.3's third bullet)",
       findings4.rarity_disagreement)

    # --------------------------------------------------- the human-bound exclusion (§5.5)
    print("\nthe human-bound exclusion (§5.5, D242/D255's replacement)")
    disputing_row = sku_row("600", "Rell, Magnetic Storm", "100/298")
    automatic_card = card(
        4, sku="600", identity_source=IDENTITY_SKU, bound_by="join",
        read_name="Rell, Noxus", read_number="100", read_printed_total="298",
    )
    automatic_card.name = disputing_row.product_name
    automatic_card.number = "100"
    automatic_card.printed_total = "298"
    automatic_card.rarity = disputing_row.rarity
    automatic_card.set_name = disputing_row.set_name
    automatic_card.condition = disputing_row.condition
    findings5 = ib.audit([automatic_card], {"600": disputing_row}, set())
    ok(automatic_card.key in findings5.name_half,
       "an AUTOMATICALLY bound card (bound_by=join) whose read disputes its row — CAUGHT "
       "in the name half", findings5.name_half)

    confirmed_card = card(
        5, sku="600", identity_source=IDENTITY_SKU, bound_by="confirm",
        read_name="Rell, Noxus", read_number="100", read_printed_total="298",
    )
    confirmed_card.name = disputing_row.product_name
    confirmed_card.number = "100"
    confirmed_card.printed_total = "298"
    confirmed_card.rarity = disputing_row.rarity
    confirmed_card.set_name = disputing_row.set_name
    confirmed_card.condition = disputing_row.condition
    findings6 = ib.audit([confirmed_card], {"600": disputing_row}, set())
    ok(confirmed_card.key not in findings6.name_half,
       "the IDENTICAL dispute, but bound_by=confirm — SILENT. A human already answered "
       "this report's question (§5.5's own words), and a guard that goes red on an "
       "answered question is spent", findings6.name_half)
    for act in ("answer", "group_answer", "correction"):
        excluded = card(
            6, sku="600", identity_source=IDENTITY_SKU, bound_by=act,
            read_name="Rell, Noxus", read_number="100", read_printed_total="298",
        )
        excluded.name = disputing_row.product_name
        excluded.number = "100"
        excluded.printed_total = "298"
        findings_act = ib.audit([excluded], {"600": disputing_row}, set())
        ok(excluded.key not in findings_act.name_half,
           f"bound_by={act!r} is excluded too — every member of HUMAN_BOUND_BY")

    number_disputing = card(
        7, sku="600", identity_source=IDENTITY_SKU, bound_by="join",
        read_name="Rell, Magnetic Storm", read_number="999", read_printed_total="298",
    )
    number_disputing.name = disputing_row.product_name
    number_disputing.number = "100"
    number_disputing.printed_total = "298"
    findings7 = ib.audit([number_disputing], {"600": disputing_row}, set())
    ok(number_disputing.key in findings7.number_half,
       "the number half fires independently of the name half", findings7.number_half)

    # ------------------------------------------------------- held_review_candidates (§7.3)
    print("\nheld_review_candidates — D253's two sets plus the SKU's own row")
    candidates = ib.held_review_candidates(
        swain_a, "pokemon", "Swain, Visionary", "065", "166",
        {"Pokemon": [swain_a, swain_b]},
    )
    tags = {c["sku"]: c.get("found_by") for c in candidates}
    ok(tags.get("402") == "listing", "the card's own bound SKU is tagged `listing`", tags)
    ok(tags.get("403") == "name",
       "the OTHER product this name also names is tagged `name` (D253's name set)", tags)
    ok(len(candidates) == 2, "no product is listed twice", candidates)

    entry = ib.held_review_entry(
        card(8, sku="402", state=IDENTIFIED, read_name="Swain, Visionary",
             read_number="065", read_printed_total="166"),
        swain_a, ib.MigrationPlan(plans=[], products_by_line={"Pokemon": [swain_a, swain_b]}),
    )
    ok(entry.reason == "listing_disputed", "the review entry's reason is +listing_disputed",
       entry.reason)
    ok(entry.candidates and entry.candidates[0]["sku"] == "402",
       "the entry's own candidates lead with the bound SKU's row", entry.candidates)

    # -------------------------------------------------------------------- plan_migration
    print("\nplan_migration / class_counts — the whole pass, end to end")
    cards = [
        card(10, sku="400", cid="digest-1", state=IDENTIFIED),
        card(11, sku=None, state=IDENTIFIED),
    ]
    identifications_by_digest = {
        "digest-1": {"identification": {"name": "Pikachu", "number": "25",
                                         "printed_total": "202"}},
    }
    plan = ib.plan_migration(cards, {"400": pokemon_row}, [], identifications_by_digest)
    counts = plan.counts
    ok(counts[ib.T1] == 1 and counts[ib.T6] == 1,
       "one T1 (backfilled from the identifications digest), one T6 (no SKU)", counts)
    ok(sum(counts.values()) == len(cards), "every card lands in exactly one class")

    print("\nidentity-binding self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
