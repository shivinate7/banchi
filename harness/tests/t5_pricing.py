"""T5 — Pricing rules.

New with batch script v2. A wrong price is a distinct failure from a wrong match: the join
can be perfect and the money still wrong, and the two have different causes, different
symptoms and different fixes. So it gets its own failing test name.

Pass: every rule x basis combination prices exactly, the floor clamp cannot be rounded
under, and a `no_market_data` SKU is never auto-priced.

Four things are checked, in the order they can hurt you:

  ORDER OF OPERATIONS   price = clamp_floor(round_2dp_half_up(rule(basis))). Rounding
                        BEFORE the clamp. Asserted against a deliberately non-2dp floor,
                        because at the real $0.40 floor both orders agree and a test that
                        cannot tell them apart is not testing the rule.

  HALF UP, NOT HALF EVEN  Python's default is half-even, so `Decimal("1.005")` rounds to
                        1.00 unless someone asked for half-up. One cent per card, in the
                        house's favour, silently.

  BASIS vs THRESHOLD    `--basis=low` changes what the RULE reads. It never changes what
                        the THRESHOLD reads, which is always TCG Market Price — D9 is a
                        statement about a card's value, not about this run's strategy. A
                        card with a $5 market and a $0.01 low is listable and prices at
                        $0.40; getting this backwards delists half a box.

  NO MARKET DATA        blank and "0.00" are UNKNOWN prices, not low ones. Never listable,
                        never in the sub-threshold bucket, never auto-priced, and `emit`
                        refuses until a human answers. The failure this prevents is handing
                        away a chase card at the floor because a cell was empty.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from pipeline import decisions, join, pricing, tcgcsv

NAME = "T5"
DESCRIPTION = "Pricing rules, rounding, floor clamp, and the no-market-data refusal"
PASS_CRITERIA = (
    "every rule x basis prices exactly; floor clamp applied after rounding; "
    "threshold always reads market; no_market_data never auto-priced"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"

# Real rows. 8608859 Articuno 161/159: market 22.03, low 21.9800 — the two differ, which
# is what makes them usable as a basis test at all.
ARTICUNO = "8608859"
# 8607459 Accelgor 013/159: market 0.07, low 0.0100 — sub-threshold on either basis.
ACCELGOR = "8607459"

BOX = 5


def _card(index, name, number, total="159", metadata=None, confidence="high"):
    return join.IdentifiedCard(
        position=join.Position(box=BOX, index=index),
        name=name,
        number=number,
        printed_total=total,
        metadata_finish=metadata,
        confidence=confidence,
        photo=f"captures/box{BOX}/{index:04d}.jpg",
    )


def run() -> Result:
    c = Checks()

    export = tcgcsv.read_export(REPO_ROOT / SOURCE_FIXTURE)
    catalog = join.Catalog(export)
    by_sku = export.by_sku()

    # --- rule parsing: never coerced -----------------------------------------------------
    c.equal(str(pricing.Rule.parse("match")), "match", "`match` parses")
    c.equal(
        (pricing.Rule.parse("undercut:5").kind, pricing.Rule.parse("undercut:5").percent),
        (pricing.RULE_UNDERCUT, Decimal("5")),
        "`undercut:5` parses to a kind and a percentage",
    )
    c.equal(
        pricing.Rule.parse("markup:12.5").percent,
        Decimal("12.5"),
        "a fractional percentage survives as a Decimal",
    )
    c.equal(
        pricing.Rule.parse(pricing.Rule.parse("markup:3")).percent,
        Decimal("3"),
        "parsing an already-parsed rule is a no-op",
    )
    for bad, why in [
        ("undercut", "a percentage-taking rule with no percentage"),
        ("match:5", "`match` with a percentage"),
        ("undercut:100", "an undercut that prices at or below zero"),
        ("markup:-5", "a negative percentage, which inverts the rule"),
        ("holofoil", "a rule outside the enum"),
        ("undercut:abc", "a percentage that is not a number"),
    ]:
        c.raises(
            pricing.UnknownRule,
            lambda bad=bad: pricing.Rule.parse(bad),
            f"refuses {bad!r}: {why}",
        )
    c.raises(
        pricing.UnknownBasis,
        lambda: pricing.check_basis("median"),
        "refuses a basis outside market | low",
    )

    # --- the rules themselves -------------------------------------------------------------
    market = Decimal("2.00")
    c.equal(pricing.Rule.parse("match").apply(market), market, "match returns the basis")
    c.equal(
        pricing.Rule.parse("undercut:5").apply(market),
        Decimal("1.9000"),
        "undercut:5 on $2.00 is $1.90",
    )
    c.equal(
        pricing.Rule.parse("markup:10").apply(market),
        Decimal("2.2000"),
        "markup:10 on $2.00 is $2.20",
    )

    # --- rounding is HALF UP, not Python's default half-even -------------------------------
    c.equal(pricing.round_money(Decimal("1.005")), Decimal("1.01"), "1.005 rounds up to 1.01")
    c.equal(pricing.round_money(Decimal("1.015")), Decimal("1.02"), "1.015 rounds up to 1.02")
    c.equal(pricing.round_money(Decimal("2.345")), Decimal("2.35"), "2.345 rounds up to 2.35")
    c.ok(
        pricing.round_money(Decimal("1.005")) != Decimal("1.00"),
        "half-even would have said 1.00 — one cent per card, silently, in the house's favour",
    )

    # --- order of operations: round, THEN clamp -------------------------------------------
    # At the real $0.40 floor both orders agree, so the discriminator uses a non-2dp floor.
    odd_floor = Decimal("0.375")
    basis = Decimal("0.3749")
    documented = pricing.clamp_floor(pricing.round_money(basis), odd_floor)
    reversed_order = pricing.round_money(pricing.clamp_floor(basis, odd_floor))
    c.equal(
        pricing.list_price(basis, rule="match", floor=odd_floor),
        documented,
        "list_price is clamp_floor(round(rule(basis))), in that order",
    )
    c.ok(
        documented != reversed_order,
        f"the two orders are distinguishable here ({documented} vs {reversed_order}), "
        f"so this assertion has teeth",
    )

    # And the property that actually protects the money, swept across every rule.
    never_under = True
    always_two_dp = True
    for rule in ("match", "undercut:5", "undercut:25", "undercut:99", "markup:10"):
        for cents in range(1, 400, 7):
            price = pricing.list_price(Decimal(cents) / 100, rule=rule)
            if price < pricing.FLOOR:
                never_under = False
                c.note(f"{rule} on ${Decimal(cents) / 100} -> {price}, under the floor")
            if price != price.quantize(Decimal("0.01")):
                always_two_dp = False
    c.ok(never_under, f"no rule can price under the ${pricing.FLOOR} floor (swept 3 rules x 57 prices)")
    c.ok(always_two_dp, "every priced output is exactly two decimals")

    c.equal(
        pricing.list_price(Decimal("22.03"), rule="undercut:5"),
        Decimal("20.93"),
        "undercut:5 on $22.03 rounds to $20.93",
    )
    c.equal(
        pricing.list_price(Decimal("22.03"), rule="markup:10"),
        Decimal("24.23"),
        "markup:10 on $22.03 rounds to $24.23",
    )
    c.equal(
        pricing.list_price(Decimal("0.41"), rule="undercut:50"),
        pricing.FLOOR,
        f"a collapsing market clamps to the ${pricing.FLOOR} floor, not to $0.21",
    )

    # --- basis picks the column; the threshold never does ----------------------------------
    articuno = by_sku[ARTICUNO]
    c.equal(
        pricing.basis_price(articuno, pricing.BASIS_MARKET),
        Decimal("22.03"),
        "basis=market reads TCG Market Price",
    )
    c.equal(
        pricing.basis_price(articuno, pricing.BASIS_LOW),
        Decimal("21.9800"),
        "basis=low reads TCG Low Price",
    )
    c.ok(
        pricing.basis_price(articuno, pricing.BASIS_LOW)
        != pricing.basis_price(articuno, pricing.BASIS_MARKET),
        "the two bases really do read different columns on this row",
    )

    # A card whose LOW price is under the threshold but whose MARKET is well over it. If the
    # threshold ever followed the basis, this card would be delisted by a flag that was only
    # supposed to change its price.
    cheap_low = dict(articuno, **{tcgcsv.LOW_PRICE_COLUMN: "0.0100"})
    low_match = join.SkuMatch(
        sku=ARTICUNO,
        row=cheap_low,
        positions=[join.Position(BOX, 1)],
        basis=pricing.BASIS_LOW,
    )
    c.ok(low_match.listable, "--basis=low does not delist a card with a healthy market price")
    c.equal(
        low_match.list_price,
        pricing.FLOOR,
        f"...and prices it from the low column, clamped to the ${pricing.FLOOR} floor",
    )
    c.equal(
        low_match.market_price,
        Decimal("22.03"),
        "market_price stays the threshold's number whatever the basis is",
    )

    market_match = join.SkuMatch(
        sku=ARTICUNO,
        row=articuno,
        positions=[join.Position(BOX, 1)],
        rule=pricing.Rule.parse("undercut:5"),
    )
    c.equal(
        market_match.list_price,
        Decimal("20.93"),
        "a SkuMatch carries the run's rule into its own price",
    )

    # --- no market data is UNKNOWN, not cheap ----------------------------------------------
    c.ok(not pricing.has_market_data(None), "a blank market cell is not market data")
    c.ok(not pricing.has_market_data(Decimal("0.00")), "$0.00 is not market data either")
    c.ok(pricing.has_market_data(Decimal("0.01")), "one cent IS market data")
    c.ok(not pricing.is_listable(None), "an unpriced row is not listable")

    blank = dict(by_sku[ARTICUNO], **{tcgcsv.MARKET_PRICE_COLUMN: ""})
    zeroed = dict(by_sku[ACCELGOR], **{tcgcsv.MARKET_PRICE_COLUMN: "0.00"})
    catalog_rows = list(export.rows)
    for index, row in enumerate(catalog_rows):
        if row[tcgcsv.SKU_COLUMN] == ARTICUNO:
            catalog_rows[index] = blank
        elif row[tcgcsv.SKU_COLUMN] == ACCELGOR:
            catalog_rows[index] = zeroed
    unpriced_catalog = join.Catalog(
        tcgcsv.Export(header=export.header, rows=tuple(catalog_rows))
    )

    report = join.join_batch(
        [_card(1, "Articuno", "161"), _card(2, "Accelgor", "013", metadata="normal")],
        unpriced_catalog,
    )
    c.note(report.report())
    c.equal(
        sorted(m.sku for m in report.no_market_data),
        sorted([ARTICUNO, ACCELGOR]),
        "blank and $0.00 rows both land in no_market_data",
    )
    c.equal(
        report.below_threshold.skus,
        [],
        "and NEITHER is swept into the sub-threshold bucket (D9)",
    )

    c.raises(
        join.Undecided,
        lambda: join.prices_for(report, sub_threshold=pricing.flat_floor()),
        "a run-wide sub-threshold choice does not answer for an unpriced SKU",
    )
    priced = join.prices_for(
        report,
        sub_threshold=pricing.flat_floor(),
        no_market_data={ARTICUNO: Decimal("22.00"), ACCELGOR: pricing.UNLISTED},
    )
    c.equal(priced.get(ARTICUNO), Decimal("22.00"), "a hand-entered price is honoured")
    c.ok(
        ACCELGOR not in priced,
        f"{pricing.UNLISTED!r} is a real answer: the SKU is left out of the file, not floored",
    )
    rows = join.import_rows(
        report,
        sub_threshold=pricing.flat_floor(),
        no_market_data={ARTICUNO: Decimal("22.00"), ACCELGOR: pricing.UNLISTED},
    )
    c.equal(
        [r[tcgcsv.SKU_COLUMN] for r in rows],
        [ARTICUNO],
        "an unlisted SKU never reaches the import file",
    )

    # --- decisions.json is the contract, and it refuses rather than defaulting --------------
    choice = decisions.Decisions.parse(
        {"rule": "undercut:5", "basis": "low", "sub_threshold": None,
         "overrides": {ARTICUNO: "9.99"}, "no_market_data": {ACCELGOR: None}}
    )
    c.equal(str(choice.rule), "undercut:5", "decisions.json carries the rule")
    c.equal(choice.basis, "low", "decisions.json carries the basis")
    c.equal(choice.unanswered, [ACCELGOR], "a null no_market_data entry is unanswered")
    c.equal(
        len(choice.blocking([ARTICUNO])),
        2,
        "an unset sub_threshold and an unanswered SKU both block emit",
    )
    c.equal(
        len(decisions.Decisions.parse(
            {"sub_threshold": "floor", "no_market_data": {ACCELGOR: "unlisted"}}
        ).blocking([ARTICUNO])),
        0,
        "both answered, including 'unlisted' — nothing blocks",
    )
    c.equal(
        decisions.Decisions.parse({"sub_threshold": {"flat": "0.25"}}).sub_threshold.price,
        Decimal("0.25"),
        "a sub-floor flat price is honoured — writing it in the file IS the deliberate act",
    )
    c.raises(
        decisions.MalformedDecisions,
        lambda: decisions.Decisions.parse({"sub_threshold": "cheap"}),
        "an unrecognised sub_threshold is refused, never guessed at",
    )

    # Merge, never clobber — `join` is re-runnable, and a re-run must not discard a decision.
    kept = decisions.Decisions.parse(
        {"sub_threshold": "floor", "no_market_data": {ACCELGOR: "1.50"}}
    )
    added = kept.add_unpriced([ACCELGOR, ARTICUNO])
    c.equal(added, [ARTICUNO], "re-running adds only the SKUs that are new")
    c.equal(
        kept.no_market_data[ACCELGOR],
        Decimal("1.50"),
        "an answer already given is preserved across a re-run",
    )
    # Pruned against a run that contains neither: the unanswered one goes, the answered
    # one stays. A card that failed to identify this run will identify next run, and
    # re-asking a question you already answered is the merge failure this guards.
    c.equal(
        kept.prune({"9999999"}),
        [ARTICUNO],
        "an UNANSWERED entry for a SKU no longer in the run is dropped",
    )
    c.equal(
        kept.no_market_data.get(ACCELGOR),
        Decimal("1.50"),
        "an ANSWERED entry survives pruning — re-asking an answered question is the bug",
    )

    # --- the catalog is still the thing being priced ----------------------------------------
    priced_report = join.join_batch(
        [_card(1, "Articuno", "161")],
        catalog,
        rule=pricing.Rule.parse("undercut:5"),
        basis=pricing.BASIS_MARKET,
    )
    c.equal(
        join.prices_for(priced_report)[ARTICUNO],
        Decimal("20.93"),
        "the run's rule reaches the emitted price through join_batch",
    )

    return c.result()
