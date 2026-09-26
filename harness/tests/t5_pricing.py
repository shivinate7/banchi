"""T5 — Pricing rules.

New with batch script v2. A wrong price is a distinct failure from a wrong match: the join
can be perfect and the money still wrong, and the two have different causes, different
symptoms and different fixes. So it gets its own failing test name.

Pass: every rule x basis prices exactly; floor clamp applied after rounding; threshold
always reads market; no_market_data never auto-priced.

"Applied after rounding" is also the statement that the price cannot be rounded *under*
the floor: clamping first would let the rounding step drop it back below.

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

    # --- the threshold is a stored figure, and it is validated like money ------------------
    #
    # D9 HAS ALWAYS SAID "BOTH CONFIGURABLE" AND NOTHING COULD CONFIGURE IT. The cut-off is
    # `pipeline/corpus.py`'s `policy.threshold` now — one figure for the store, set on
    # `#/pricing` — and `THRESHOLD` is what a store that has never set one reads.
    c.equal(
        pricing.check_threshold(None),
        pricing.THRESHOLD,
        "an unset threshold IS the constant, so a store that never touched it partitions "
        "exactly as it did before the field existed",
    )
    c.equal(
        pricing.check_threshold(" 1.25 "),
        Decimal("1.25"),
        "and a stored one comes back as the money it was typed as, whitespace and all",
    )
    for bad, why in [
        ("", "an empty cell"),
        ("free", "a word"),
        ("0", "zero, which would list a $0.00 card"),
        ("-1", "a negative cut-off"),
        ("NaN", "a Decimal that is not a number"),
    ]:
        caught = c.raises(
            pricing.InvalidThreshold,
            lambda bad=bad: pricing.check_threshold(bad),
            f"refuses {bad!r}: {why}",
        )
        if caught is not None:
            c.ok(
                repr(bad.strip()) in str(caught),
                "and the refusal NAMES the value — a threshold nobody can see written down "
                "is a threshold nobody can correct",
                str(caught),
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

    # --- the floor in force is the STORE'S cut-off (D9, amended 2026-09-09) -----------------
    #
    # THE DEFECT THIS PINS, MEASURED ON THE OWNER'S REAL STORE. `policy.threshold` said $0.29
    # for a week while every clamp in the pipeline read this module's $0.40: 293 live listings
    # hand-priced down to the cut-off were refused `below_floor` on the way to the upload, and
    # in the other direction a card the operator's own cut-off calls listable was priced ABOVE
    # its market. D9 said "both configurable" and only the threshold ever was.
    #
    # THE DISCRIMINATING CASE IS A MARKET BETWEEN THE TWO FIGURES. At $0.32 the two answers are
    # $0.32 and $0.40, so a `SkuMatch` that went back to reading the constant fails here rather
    # than agreeing with itself.
    between = dict(by_sku[ARTICUNO], **{tcgcsv.MARKET_PRICE_COLUMN: "0.32"})
    cheap_store = join.SkuMatch(sku=ARTICUNO, row=between, threshold=Decimal("0.29"))
    default_store = join.SkuMatch(sku=ARTICUNO, row=between)
    c.ok(cheap_store.listable, "a $0.32 card is listable at a stored cut-off of $0.29")
    c.equal(
        cheap_store.list_price,
        Decimal("0.32"),
        "and it lists AT its own market — the clamp is the store's $0.29, so nothing raises it",
    )
    c.equal(
        default_store.list_price,
        pricing.FLOOR,
        f"the same row at the ${pricing.THRESHOLD} default clamps to ${pricing.FLOOR}, which "
        f"is what makes the assertion above discriminating rather than decorative",
    )
    c.ok(
        not default_store.listable,
        "and at that cut-off the row is not even listable — a floor ABOVE the cut-off prices a "
        "card the partition already called listable above its own market, and no field can "
        "express that arrangement any more",
    )
    c.equal(
        pricing.flat_floor().resolve(cheap_store.threshold),
        Decimal("0.29"),
        "a legacy `floor` disposition resolves at the store's cut-off too — D98 retired it as "
        "an answer anybody may CHOOSE, and while it resolved at the constant a store set below "
        "$0.40 sent its cheapest cards out dearer than its mid ones",
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

    # --- and the cut-off moves the boundary, in both directions ---------------------------
    #
    # ACCELGOR IS $0.07 MARKET, which is sub-threshold at $0.40 and listable at $0.05. The
    # same row, the same reading, two partitions — which is the whole of what making the
    # threshold a stored policy buys, and the thing that would silently stop working if
    # `SkuMatch.listable` went back to reading the module constant.
    accelgor_row = by_sku[ACCELGOR]
    c.ok(
        not join.SkuMatch(
            sku=ACCELGOR, row=accelgor_row, positions=[join.Position(BOX, 1)]
        ).listable,
        "a $0.07 card is sub-threshold under the default $0.40",
    )
    c.ok(
        join.SkuMatch(
            sku=ACCELGOR,
            row=accelgor_row,
            positions=[join.Position(BOX, 1)],
            threshold=Decimal("0.05"),
        ).listable,
        "and listable under a stored cut-off of $0.05 — the operator's figure, not the "
        "module's",
    )
    c.ok(
        not join.SkuMatch(
            sku=ARTICUNO,
            row=articuno,
            positions=[join.Position(BOX, 1)],
            threshold=Decimal("50.00"),
        ).listable,
        "and it moves the other way too: a $22.03 card is sub-threshold at $50.00, which "
        "is what an operator raising the bar on a bulk box is asking for",
    )
    lowered = join.join_batch(
        [_card(2, "Accelgor", "013", metadata="normal")],
        catalog,
        threshold=Decimal("0.05"),
    )
    c.equal(
        (list(lowered.matches), lowered.below_threshold.skus),
        ([ACCELGOR], []),
        "THE FIGURE REACHES THE PARTITION AND NOT ONLY THE ROW. `join_batch` builds the "
        "sub-threshold bucket from `listable`, so a threshold that stopped at the match "
        "would price the card one way and file it the other",
    )
    c.equal(
        lowered.below_threshold.threshold,
        Decimal("0.05"),
        "and the bucket's bands are cut as fractions of the SAME figure, so they follow it",
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
    left = join.prices_for(report, sub_threshold=pricing.flat_floor(), leave_unanswered=True)
    c.ok(
        ARTICUNO not in left and ACCELGOR not in left,
        "a SEND leaves an unanswered no-price SKU out rather than refusing (D277 Q3) — and "
        "never prices it at a guess: it is absent, not floored",
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

    # --- withholding: an answer that is not a price (D49) ------------------------------------
    #
    # THE MIRROR OF THE `no_market_data` CASE ABOVE, ONE CHANNEL OVER. That field has accepted
    # `unlisted` since D9; `overrides` demanded a price, so a card WITH a market price had no
    # way to be held back. The owner: "say i'm bullish on the price going up, and don't want to
    # list any right now."
    held = decisions.Decisions.parse(
        {
            "sub_threshold": "floor",
            "overrides": {
                ARTICUNO: {"withheld": "bullish", "watch_above": "30.00", "note": "rotation"},
                ACCELGOR: "unlisted",
            },
        }
    )
    c.equal(
        sorted(held.withheld()),
        sorted([ARTICUNO, ACCELGOR]),
        "both spellings of a withhold parse to one answer — the OBJECT the screen writes and "
        "the bare string a terminal user types, which is the spelling `no_market_data` has "
        "accepted since D9 and a second word for one idea is the drift D16 exists to catch",
    )
    c.equal(
        held.dispositions(),
        {},
        "AND NEITHER REACHES `dispositions()`, WHICH IS LOAD-BEARING RATHER THAN TIDY: `emit` "
        "refuses the whole run when that mapping names a SKU the batch does not hold, and a "
        "withheld SKU is precisely the one most likely to fall out of a later run — it was "
        "withheld BECAUSE it is not being listed",
    )
    c.equal(
        held.to_payload()["overrides"][ACCELGOR],
        pricing.UNLISTED,
        "the bare form round-trips byte-identically through `to_payload`, the shape "
        "`GET .../pricing` serves — a hold typed by hand as a string must not come back as "
        "an object",
    )
    c.equal(
        held.to_payload()["overrides"][ARTICUNO],
        {"withheld": "bullish", "watch_above": "30.00", "note": "rotation"},
        "and the object round-trips whole, reason, watch and note",
    )
    c.equal(
        decisions.Decisions.parse(
            {"overrides": {ARTICUNO: {"withheld": "bullish"}}}
        ).to_payload()["overrides"][ARTICUNO],
        {"withheld": "bullish"},
        "an EMPTY note is omitted rather than written — the corpus is rewritten on every "
        "save, so a written empty would accrete on every held SKU forever",
    )
    c.ok(
        any("withheld" in w for w in held.warnings),
        "holds are NAMED in the warnings, at the moment `emit` commits a file and a person "
        "can still change their mind — a warning and not a blocker, because `blocking` "
        "refuses on the ABSENCE of an answer and a withhold is an answer",
    )
    c.equal(
        held.blocking([]),
        [],
        "and a withhold blocks nothing on its own",
    )
    for bad, why in (
        ({ARTICUNO: {"withheld": "greedy"}}, "a reason outside the authored vocabulary"),
        ({ARTICUNO: {"withheld": "bullish", "note": 5}}, "a note that is not a string"),
        ({ARTICUNO: {"withheld": "bullish", "watch_above": "soon"}}, "a watch that is not a price"),
    ):
        c.raises(
            decisions.MalformedDecisions,
            lambda payload=bad: decisions.Decisions.parse({"overrides": payload}),
            f"{why} is refused by name rather than written",
        )

    # `warnings` compares every override against the floor, and did it over EVERY value — so
    # the first re-join after a hold was set raised TypeError out of a property, from inside
    # the free command an operator presses without thinking. This is that crash, asserted.
    c.equal(
        decisions.Decisions.parse(
            {"overrides": {ARTICUNO: "0.10", ACCELGOR: "unlisted"}}
        ).warnings[0].startswith("1 per-SKU override"),
        True,
        "a sub-floor price beside a hold still reports the price and does not crash on the "
        "hold — the floor comparison is guarded on the value being a Decimal",
    )

    # --- the parsed decision is the contract, and the parser refuses rather than defaulting ---
    choice = decisions.Decisions.parse(
        {"rule": "undercut:5", "basis": "low", "sub_threshold": None,
         "overrides": {ARTICUNO: "9.99"}, "no_market_data": {ACCELGOR: None}}
    )
    c.equal(str(choice.rule), "undercut:5", "the parsed decision carries the rule")
    c.equal(choice.basis, "low", "the parsed decision carries the basis")
    c.equal(choice.unanswered, [ACCELGOR], "a null no_market_data entry is unanswered")
    c.equal(
        len(choice.blocking([ARTICUNO])),
        1,
        "an unset sub_threshold blocks emit, and an unanswered no-price SKU does NOT any more "
        "(D277 Q3): the send leaves it out and sends every other ready copy",
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
