"""T5 — Pricing rules.

Protects: Every pricing rule prices exactly, the floor clamps after rounding, the threshold reads market, and a card with no market data is never auto-priced.
Governs: D9

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

Suggestions (`_suggest_checks`) pin `pipeline/suggest.py` before its build: each trigger at its
edge, the cap and the value line, the floor clamp and the no-market refusal. They sit under T5
and do not change T5's published Pass line.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from pipeline import corpus, decisions, join, pricing, tcgcsv

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


# --- suggestions: `pipeline/suggest.py` (docs/specs/pricing-suggest.md, sections 2, 3, 4b, 5 step 3)
#
# THE CONTRACT, PINNED BEFORE THE BUILD. The engine is pure over plain dicts: no DB, no network.
#
#   fired(listing, today)            -> list of trigger names that fire, in this order:
#                                       "market_moved", "unsold", "undercut". Selling fast and
#                                       an outside signal are not names here.
#   review(listings, policy, today)  -> {"needs_you": rows, "suggested": rows, "at_rule": rows}
#                                       a row is {"sku", "asking", "price", "source", "reason"}.
#                                       `source` is "Suggested" for a live suggestion, "Live" for a
#                                       live listing kept at its asking price, and "Rule" for a new
#                                       copy at the rule. `price` is the store rule's price at
#                                       today's market, clamped to the floor, and None with no
#                                       market. `reason` is plain words, "" when nothing fired.
#   Needs you holds only rows that would send something a person must decide: a new copy with no
#   market, a new copy at or above the value line, or a live suggestion past the cap or at or
#   above the value line. A live listing with no trigger, or with no market, stays in at_rule at
#   its asking price, even at or above the value line.
#
# `today` is an ISO date string. A listing holds "sku", "live" (False for a new copy, whose
# "asking" is None), "asking", "market_listed", "market", "low" (TCGplayer Low Price, which a policy
# basis of "low" prices from), "low_with_shipping", "first_seen_live" (ISO date), "last_sold_at"
# (an ISO date or datetime from a `sold` event, None if never sold), "units_sold_30d" and
# "outside_signal". Money is Decimal, and None means unknown. Unsold days are today minus the LATER
# of first_seen_live and last_sold_at, and a listing with neither is never unsold. The engine reads
# no ledger, and it never reads `sold_here`, which resets at each live reading.
#
# A policy holds "rule", "basis" ("market" or "low": the price the RULE reads, never the triggers
# or the floor, which read Market), "threshold" (the floor), "limit" (a Decimal fraction: 0.25 is
# 25%) and "value_line" (Decimal dollars). A missing `rule` means match, a missing `basis` means
# market, a missing `limit` means 0.25, and a missing `value_line` means 25. A bad `limit` or
# `value_line` raises ValueError.
#
# Only a market move UP may raise a live price. Undercut, unsold and market down may only lower it.
# A live row whose trigger would raise its price stays at_rule at its asking price, source Live.

TODAY = "2026-10-27"


def _ago(days: int) -> str:
    """The ISO date `days` before TODAY."""
    return (date.fromisoformat(TODAY) - timedelta(days=days)).isoformat()


def _listing(**over) -> dict:
    """The one fixture for a live listing. Each case overrides only the field it is about."""
    base = {
        "sku": "SUG-1",
        "live": True,
        "asking": Decimal("10.00"),
        "market_listed": Decimal("10.00"),
        "market": Decimal("10.00"),
        "low": None,
        "low_with_shipping": None,
        "first_seen_live": TODAY,
        "last_sold_at": None,
        "units_sold_30d": 0,
        "outside_signal": None,
    }
    base.update(over)
    return base


def _policy(**over) -> dict:
    """The store's policy, as `corpus.Corpus` hands it over. Each case overrides one key."""
    base = {
        "rule": "match",
        "threshold": Decimal("0.40"),
        "limit": Decimal("0.25"),
        "value_line": Decimal("25"),
    }
    base.update(over)
    return base


def _suggest_checks(c: Checks) -> None:
    try:
        from pipeline import suggest
    except ImportError as exc:
        # A local import, so a missing engine fails these cases and no others: the rest of T5
        # still runs and its verdict still counts.
        c.ok(False, "pipeline/suggest.py imports", f"{type(exc).__name__}: {exc}")
        return

    def fired(**over):
        return suggest.fired(_listing(**over), TODAY)

    def review(*listings, **policy):
        return suggest.review(list(listings), _policy(**policy), TODAY)

    def groups(out, sku):
        return sorted(g for g, rows in out.items() for r in rows if r["sku"] == sku)

    def field(out, sku, key):
        hit = next((r for rows in out.values() for r in rows if r["sku"] == sku), None)
        return None if hit is None else hit.get(key)

    def says(out, sku, words):
        return words in str(field(out, sku, "reason") or "").lower()

    def attempt(call):
        """The call's value and "", or None and the error it raised: one crash fails one check."""
        try:
            return call(), ""
        except Exception as exc:
            return None, f"raised {type(exc).__name__}: {exc}"

    # --- triggers at their edges (4b) -----------------------------------------------------
    c.equal(
        fired(market=Decimal("11.50")),
        ["market_moved"],
        "market up exactly 15% since listed fires: the edge is inclusive",
    )
    c.equal(fired(market=Decimal("11.49")), [], "market up 14.9% does not fire")
    c.equal(fired(market=Decimal("8.50")), ["market_moved"], "market down exactly 15% fires too")
    c.equal(fired(market=Decimal("8.51")), [], "market down 14.9% does not fire")

    c.equal(
        fired(first_seen_live=_ago(30), asking=Decimal("11.01")),
        ["unsold"],
        "unsold 30 days with the asking price 10.1% over market fires",
    )
    c.equal(
        fired(first_seen_live=_ago(29), asking=Decimal("11.01")),
        [],
        "29 days does not fire, whatever the premium",
    )
    c.equal(
        fired(first_seen_live=_ago(30), asking=Decimal("11.00")),
        [],
        "an asking price exactly 10% over market does not fire: the bar is MORE than 10%",
    )
    c.equal(
        fired(first_seen_live=_ago(90)),
        [],
        "age alone never fires: 90 days since listing, asking at market",
    )
    c.equal(
        fired(first_seen_live=_ago(60), last_sold_at=_ago(10), asking=Decimal("11.50")),
        [],
        "a sale 10 days ago restarts the count: 10 unsold days, 15% over market, does not fire",
    )
    c.equal(
        fired(first_seen_live=_ago(60), last_sold_at=_ago(40), asking=Decimal("11.50")),
        ["unsold"],
        "unsold counts from the LATER of listing and last sale: 40 days after a sale, fires",
    )

    c.equal(
        fired(low_with_shipping=Decimal("9.00")),
        ["undercut"],
        "Low With Shipping exactly 10% under our ask fires",
    )
    c.equal(fired(low_with_shipping=Decimal("9.01")), [], "9.9% under does not fire")

    c.equal(
        fired(units_sold_30d=40),
        [],
        "selling fast is not a trigger: 40 units sold market-wide moves nothing",
    )
    c.equal(
        fired(outside_signal="meta: played in a winning deck"),
        [],
        "an outside signal is a reason slot, and nothing fires it",
    )
    c.equal(fired(market=None), [], "no market today: no move can be read, nothing fires")
    c.equal(
        fired(market=None, low_with_shipping=Decimal("9.00")),
        [],
        "a live listing with no market fires nothing, not even Low With Shipping 10% under ours",
    )
    c.equal(
        fired(market_listed=None, market=Decimal("12.00")),
        [],
        "no market on listing day: market moved cannot fire, and nothing crashes",
    )

    # --- dates: no listing date and no sale, and a sale stamped with a time (sections 4 and 4b) ---
    undated = _listing(sku="ND", first_seen_live=None, last_sold_at=None, asking=Decimal("11.50"))
    hit, crash = attempt(lambda: suggest.fired(undated, TODAY))
    c.ok(
        crash == "" and hit == [],
        "a live listing with no listing date and no sale: unsold does not fire, and nothing crashes",
        crash or f"fired: {hit!r}",
    )
    out, crash = attempt(lambda: suggest.review([undated], _policy(), TODAY))
    c.ok(
        crash == "" and groups(out, "ND") == ["at_rule"] and field(out, "ND", "source") == "Live",
        "and review keeps it Going at the rule, source Live, and does not crash",
        crash or f"review: {out!r}",
    )
    hit, crash = attempt(
        lambda: suggest.fired(
            _listing(
                first_seen_live=_ago(60),
                last_sold_at=_ago(40) + "T12:00:00+00:00",
                asking=Decimal("11.50"),
            ),
            TODAY,
        )
    )
    c.ok(
        crash == "" and hit == ["unsold"],
        "a sale stamped with a time counts by its date: 40 days since the sale, unsold fires",
        crash or f"fired: {hit!r}",
    )

    # --- groups and prices (sections 2 and 3) ------------------------------------------------
    up = review(_listing(sku="UP", market=Decimal("11.80")))
    c.equal(groups(up, "UP"), ["suggested"], "market up 18% is a suggestion, inside the cap")
    c.equal(
        field(up, "UP", "price"),
        Decimal("11.80"),
        "a raise is allowed: 10.00 to 11.80, the match rule at today's market",
    )
    c.ok(
        says(up, "UP", "market up 18% since listed"),
        "and the reason says why, in plain words",
        str(field(up, "UP", "reason")),
    )

    down = review(_listing(sku="DN", market=Decimal("8.50")))
    c.equal(groups(down, "DN"), ["suggested"], "market down 15% is a lowering suggestion, inside the cap")
    c.equal(field(down, "DN", "price"), Decimal("8.50"), "priced at today's market, lower")
    c.ok(
        says(down, "DN", "market down 15% since listed"),
        "and its reason says the market went down",
        str(field(down, "DN", "reason")),
    )

    inside = review(_listing(sku="IN", market=Decimal("12.50")))
    past = review(_listing(sku="OUT", market=Decimal("12.51")))
    c.equal(groups(inside, "IN"), ["suggested"], "a move of exactly 25%, the default cap, is inside it")
    c.equal(
        groups(past, "OUT"),
        ["needs_you"],
        "25.1% is past the cap: Needs you, not the one-press batch",
    )
    c.equal(
        field(past, "OUT", "price"),
        Decimal("12.51"),
        "the Needs you row still carries its proposed price, so the owner can tick it",
    )

    under = review(
        _listing(sku="V1", asking=Decimal("20.00"), market_listed=Decimal("20.00"), market=Decimal("24.99"))
    )
    at = review(
        _listing(sku="V2", asking=Decimal("20.00"), market_listed=Decimal("20.00"), market=Decimal("25.00"))
    )
    c.equal(
        groups(under, "V1"),
        ["suggested"],
        "a card at $24.99 is under the $25 value line, so a move inside the cap is a suggestion",
    )
    c.equal(
        groups(at, "V2"),
        ["needs_you"],
        "a suggestion at exactly $25.00 is Needs you, even at 25% and inside the cap",
    )
    still = review(
        _listing(sku="V3", asking=Decimal("25.00"), market_listed=Decimal("25.00"), market=Decimal("25.00"))
    )
    c.equal(
        groups(still, "V3"),
        ["at_rule"],
        "a live listing at the value line with no trigger stays in Going at the rule",
    )
    c.equal(field(still, "V3", "price"), Decimal("25.00"), "and keeps its asking price")
    c.equal(field(still, "V3", "source"), "Live", "and its source says Live")

    blank = review(_listing(sku="NM", market=None))
    c.equal(groups(blank, "NM"), ["at_rule"], "a live listing with no market fires nothing: Going at the rule")
    c.equal(field(blank, "NM", "price"), Decimal("10.00"), "and keeps its asking price")
    c.equal(field(blank, "NM", "source"), "Live", "and its source says Live")

    new_blank = review(_listing(sku="NC", live=False, asking=None, market=None))
    c.equal(groups(new_blank, "NC"), ["needs_you"], "a new copy with no market goes to Needs you")
    c.equal(field(new_blank, "NC", "price"), None, "and with no market there is no proposed price")
    c.ok(
        says(new_blank, "NC", "no market price"),
        "and the reason says there is no market price",
        str(field(new_blank, "NC", "reason")),
    )

    new_high = review(_listing(sku="NH", live=False, asking=None, market=Decimal("25.00")))
    c.equal(
        groups(new_high, "NH"),
        ["needs_you"],
        "a new copy at the $25 value line goes to Needs you, with no trigger needed",
    )
    c.equal(field(new_high, "NH", "price"), Decimal("25.00"), "its rule price is the proposed price")

    new_low = review(_listing(sku="NL", live=False, asking=None, market=Decimal("24.99")))
    c.equal(groups(new_low, "NL"), ["at_rule"], "a new copy under the value line is Going at the rule")
    c.equal(field(new_low, "NL", "source"), "Rule", "and its source says Rule")

    # --- the floor clamps the rule's price (section 2) ---------------------------------------
    floored = review(
        _listing(sku="FL", asking=Decimal("0.60"), market_listed=Decimal("0.80"), market=Decimal("0.20")),
        threshold=Decimal("0.50"),
    )
    c.equal(
        field(floored, "FL", "price"),
        Decimal("0.50"),
        "a market at $0.20 clamps to the owner's $0.50 floor: the floor wins over the rule",
    )
    c.equal(
        groups(floored, "FL"),
        ["suggested"],
        "and the clamped move, 0.60 to 0.50, is inside the cap",
    )

    priced = review(
        _listing(sku="RL", asking=Decimal("25.00"), market_listed=Decimal("18.00"), market=Decimal("22.03")),
        rule="undercut:5",
    )
    c.equal(
        field(priced, "RL", "price"),
        Decimal("20.93"),
        "the store's rule prices the suggestion at today's market: undercut:5 on $22.03 is $20.93",
    )
    c.equal(groups(priced, "RL"), ["suggested"], "a 16% cut from a $25.00 ask is inside the cap")

    # --- the other two triggers, through review -----------------------------------------------
    cut = review(_listing(sku="UC", low_with_shipping=Decimal("9.00"), market=Decimal("9.50")))
    c.equal(
        groups(cut, "UC"),
        ["suggested"],
        "Low With Shipping 10% under our ask fires, and the 5% move to market is inside the cap",
    )
    c.ok(
        says(cut, "UC", "shipping"),
        "and the reason says the lower price includes shipping",
        str(field(cut, "UC", "reason")),
    )

    stale = review(_listing(sku="ST", asking=Decimal("11.50"), first_seen_live=_ago(30)))
    c.equal(
        field(stale, "ST", "price"),
        Decimal("10.00"),
        "unsold 30 days at 15% over market: the suggestion is the market, $10.00",
    )
    c.ok(
        says(stale, "ST", "unsold 30 days"),
        "and the reason names the age",
        str(field(stale, "ST", "reason")),
    )

    # --- a trigger never moves the price against its direction (sections 2 and 3) ----------------
    # Only a market move UP may raise a live price. Undercut, unsold and market down may only lower it.
    lowball = review(
        _listing(
            sku="UD",
            market=Decimal("12.00"),
            market_listed=Decimal("12.00"),
            low_with_shipping=Decimal("8.00"),
        )
    )
    c.equal(
        groups(lowball, "UD"),
        ["at_rule"],
        "undercut fires, but the match rule would raise 10.00 to 12.00: Going at the rule, not a suggestion",
    )
    c.equal(field(lowball, "UD", "source"), "Live", "and its source says Live")
    c.equal(field(lowball, "UD", "price"), Decimal("10.00"), "and it keeps its asking price")

    far = review(
        _listing(
            sku="UF",
            market=Decimal("14.00"),
            market_listed=Decimal("14.00"),
            low_with_shipping=Decimal("8.00"),
        )
    )
    c.equal(groups(far, "UF"), ["at_rule"], "the same raise past the cap is Going at the rule, not Needs you")

    marked = review(_listing(sku="UM", asking=Decimal("11.50"), first_seen_live=_ago(30)), rule="markup:20")
    c.equal(
        groups(marked, "UM"),
        ["at_rule"],
        "unsold 30 days over market, but the rule marks up to $12.00: Going at the rule, not a raise",
    )
    c.equal(field(marked, "UM", "price"), Decimal("11.50"), "and it keeps its asking price")

    sank = review(_listing(sku="DR", asking=Decimal("9.00"), market_listed=Decimal("12.00"), market=Decimal("10.00")))
    c.equal(
        groups(sank, "DR"),
        ["at_rule"],
        "market down 17% would raise 9.00 to 10.00: Going at the rule, not a suggestion",
    )
    c.equal(field(sank, "DR", "price"), Decimal("9.00"), "and it keeps its asking price")

    both = review(_listing(sku="BO", market=Decimal("11.80"), low_with_shipping=Decimal("8.00")))
    c.equal(
        groups(both, "BO"),
        ["suggested"],
        "market up 18% with an undercut also firing still raises: the market move is the raise",
    )
    c.equal(field(both, "BO", "price"), Decimal("11.80"), "to today's market")

    # --- no trigger, no suggestion: Going at the rule (4b) -----------------------------------
    ar = review(_listing(sku="AR", market=Decimal("11.00")))
    c.equal(groups(ar, "AR"), ["at_rule"], "a 10% move with no trigger stays Going at the rule")
    c.equal(field(ar, "AR", "price"), Decimal("10.00"), "at its asking price, not the market")
    c.equal(field(ar, "AR", "source"), "Live", "and its source says Live")
    c.equal(
        groups(review(_listing(sku="AG", first_seen_live=_ago(90))), "AG"),
        ["at_rule"],
        "age alone leaves the listing Going at the rule",
    )
    c.equal(
        groups(review(_listing(sku="SF", units_sold_30d=40)), "SF"),
        ["at_rule"],
        "selling fast alone leaves the listing Going at the rule",
    )
    c.equal(
        groups(review(_listing(sku="OS", outside_signal="meta: played in a winning deck")), "OS"),
        ["at_rule"],
        "an outside signal alone leaves the listing Going at the rule",
    )

    # --- the cap and the value line are owner settings with defaults (section 5, step 3) -----
    eighteen = _listing(sku="CAP", market=Decimal("11.80"))
    no_cap = {k: v for k, v in _policy().items() if k != "limit"}
    c.equal(
        groups(suggest.review([eighteen], no_cap, TODAY), "CAP"),
        ["suggested"],
        "with no cap in the policy, the default 25% applies: an 18% move is a suggestion",
    )
    c.equal(
        groups(review(eighteen, limit=Decimal("0.10")), "CAP"),
        ["needs_you"],
        "the owner lowers the cap to 10%: the same 18% move goes to Needs you",
    )
    valued = _listing(
        sku="VD", asking=Decimal("20.00"), market_listed=Decimal("20.00"), market=Decimal("25.00")
    )
    no_value_line = {k: v for k, v in _policy().items() if k != "value_line"}
    c.equal(
        groups(suggest.review([valued], no_value_line, TODAY), "VD"),
        ["needs_you"],
        "with no value line in the policy, the default $25 applies",
    )
    c.equal(
        groups(review(valued, value_line=Decimal("30")), "VD"),
        ["suggested"],
        "the owner moves the value line to $30: the same card is a suggestion",
    )

    # --- a bad setting is refused by name, never read as the default (section 5, step 3) ---------
    for bad in ("25", 25, "1.5", "0", "-0.25", "nan", "text"):
        c.raises(
            ValueError,
            lambda bad=bad: review(_listing(), limit=bad),
            "review refuses a limit of {0!r}".format(bad),
        )
    for bad in ("0", "-5", "nan", "text"):
        c.raises(
            ValueError,
            lambda bad=bad: review(_listing(), value_line=bad),
            "review refuses a value line of {0!r}".format(bad),
        )

    # --- the stored settings reach the engine through the corpus's policy (section 5, step 3) -----
    stored = corpus.Corpus.parse({"version": 1, "policy": {"limit": "0.30", "value_line": "30"}})
    saved = suggest.review(
        [
            _listing(sku="LA", asking=Decimal("10.00"), market_listed=Decimal("10.00"), market=Decimal("12.80")),
            _listing(sku="LB", asking=Decimal("22.00"), market_listed=Decimal("22.00"), market=Decimal("26.00")),
        ],
        stored.policy_for(),
        TODAY,
    )
    c.equal(groups(saved, "LA"), ["suggested"], "a stored limit of 0.30 reaches review: a 28% move is a suggestion")
    c.equal(groups(saved, "LB"), ["suggested"], "a stored value line of $30 reaches review: a $26.00 price is a suggestion")

    # --- the stored basis reaches the rule and never the triggers (D9, section 5, step 3) ---------
    lows = _listing(sku="BL", market=Decimal("12.00"), low=Decimal("11.00"))
    c.equal(field(review(lows), "BL", "price"), Decimal("12.00"), "on the market basis the rule prices at market")
    c.equal(
        field(review(lows, basis="low"), "BL", "price"),
        Decimal("11.00"),
        "on the low basis the rule prices from Low, $11.00",
    )
    fresh = review(
        _listing(sku="BN", live=False, asking=None, market=Decimal("12.00"), low=Decimal("11.00")),
        basis="low",
    )
    c.equal(field(fresh, "BN", "price"), Decimal("11.00"), "a new copy on the low basis is priced from Low too")
    quiet = review(_listing(sku="BQ", low=Decimal("8.50")), basis="low")
    c.equal(
        groups(quiet, "BQ"),
        ["at_rule"],
        "on the low basis the triggers still read Market: Low 15% under moves nothing",
    )

    # --- every listing lands in exactly one group --------------------------------------------
    mixed = review(
        _listing(sku="A"),
        _listing(sku="B", market=Decimal("11.80")),
        _listing(sku="C", live=False, asking=None, market=None),
        _listing(sku="D", market=Decimal("12.51")),
    )
    c.equal(
        sum(len(rows) for rows in mixed.values()),
        4,
        "four listings in, four rows out, across the three groups",
    )

def _suggest_policy_checks(c: Checks) -> None:
    # The two settings are corpus policy fields. This needs no engine, so it reports on its own
    # even while the engine's import fails.
    stored = corpus.Corpus.parse({"version": 1, "policy": {"limit": "0.30", "value_line": "30.00"}})
    kept = stored.to_payload()["policy"]
    c.ok(
        kept.get("limit") is not None and Decimal(str(kept["limit"])) == Decimal("0.30"),
        "the suggestion limit is a corpus policy setting, and it survives a save",
        str(kept),
    )
    c.ok(
        kept.get("value_line") is not None and Decimal(str(kept["value_line"])) == Decimal("30"),
        "and so is the value line",
        str(kept),
    )

    # --- a bad setting is refused where it is read, not later (section 5, step 3) ------------------
    for bad in ("25", 25, "1.5", "0", "-0.25", "nan", "text"):
        c.raises(
            ValueError,
            lambda bad=bad: corpus.Corpus.parse({"version": 1, "policy": {"limit": bad}}),
            "Corpus.parse refuses a limit of {0!r}".format(bad),
        )
    for bad in ("0", "-5", "nan", "text"):
        c.raises(
            ValueError,
            lambda bad=bad: corpus.Corpus.parse({"version": 1, "policy": {"value_line": bad}}),
            "Corpus.parse refuses a value line of {0!r}".format(bad),
        )

    # --- an old store with neither key reads the defaults (section 5, step 3) ---------------------
    legacy = corpus.Corpus.parse({"version": 1, "policy": {"rule": "match", "threshold": "0.49"}})
    legacy_kept = legacy.to_payload()["policy"]
    c.ok(
        legacy_kept.get("limit") is not None
        and legacy_kept.get("value_line") is not None
        and Decimal(str(legacy_kept["limit"])) == Decimal("0.25")
        and Decimal(str(legacy_kept["value_line"])) == Decimal("25"),
        "an old store with no limit or value line reads the defaults, 0.25 and 25",
        str(legacy_kept),
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
        "a legacy `floor` disposition resolves at the store's cut-off too — D9 retired it as "
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

    # --- a held SKU with no market price, as `#/pricing` stores it ---------------------------
    #
    # THE SCREEN'S OWN SHAPE, THROUGH THE CORPUS. A hold is one answer on the `price` channel on
    # every row, and it carries the answer it replaced in `before` (the owner's ruling, "Bring
    # back $5.16"). `join.prices_for` must skip the held SKU before it reads `no_market_data`,
    # and still list the control. A release writes `before` back, and the SKU lists again.
    def _through_corpus(answers):
        book = corpus.Corpus.parse({"version": 1, "skus": answers})
        choice = book._decisions(None, [ARTICUNO, ACCELGOR], [ARTICUNO, ACCELGOR])
        return join.prices_for(
            report,
            sub_threshold=pricing.flat_floor(),
            sku_dispositions=choice.dispositions(),
            no_market_data=choice.no_market_data,
            withheld=set(choice.withheld()),
        )

    # NO `leave_unanswered`: an unanswered no-price SKU refuses here, so a held one passing
    # proves the hold is what answered it, not the send's leave-out rule.
    hold = {"withheld": "bullish", "note": "rotation", "before": {"value": "22.00", "channel": "price"}}
    on_hold = _through_corpus({ARTICUNO: {"value": hold}, ACCELGOR: {"value": "4.00"}})
    c.ok(
        ARTICUNO not in on_hold,
        "a held SKU with no market price is withheld, and its `before` field is not read as a price",
    )
    c.equal(on_hold.get(ACCELGOR), Decimal("4.00"), "the control, a typed price with no market price, still lists")
    released = _through_corpus({ARTICUNO: {"value": "22.00"}, ACCELGOR: {"value": "4.00"}})
    c.equal(released.get(ARTICUNO), Decimal("22.00"), "a release writes `before` back, and the SKU lists at it")

    # --- a release keeps the first date (the owner's ruling, "Keep the first date") ----------
    #
    # `corpus.stamp_answers` dates every NEW price answer, because D100's markdown ratchet reads
    # `at`. A price returning from a hold is not new: the hold kept it in `before`, date and all,
    # and a release sends that same answer back with that same date. Only an exact return keeps
    # the date. A new price, or the same price with no matching date, is dated today.
    first, now = "2026-09-01T10:00:00+00:00", "2026-09-26T12:00:00+00:00"
    held_book = corpus.Corpus.parse({"version": 1, "skus": {
        ARTICUNO: {"value": {"withheld": "bullish", "before": {"value": "22.00", "channel": "price", "at": first}}},
    }})

    def _stamped(value, at=None):
        after = corpus.Corpus.parse({"version": 1, "skus": {ARTICUNO: {"value": value, **({"at": at} if at else {})}}})
        corpus.stamp_answers(held_book, after, now)
        return after.answers[ARTICUNO].at

    c.equal(_stamped("22.00", first), first, "a release that sends back the hold's own answer and date keeps the first date")
    c.equal(_stamped("22.0", first), first, "the value folds as the ratchet folds it: 22.0 is 22.00")
    c.equal(_stamped("23.00", first), now, "a new price after a hold dates today, whatever date it carries")
    c.equal(_stamped("22.00"), now, "the same price with no date is a new typing, and dates today")
    c.equal(_stamped("22.00", "2026-09-20T00:00:00+00:00"), now, "a date that is not the hold's own is not kept")
    fresh = corpus.Corpus.parse({"version": 1, "skus": {ARTICUNO: {"value": "22.00", "at": first}}})
    corpus.stamp_answers(corpus.Corpus(), fresh, now)
    c.equal(fresh.answers[ARTICUNO].at, now, "a price with no hold before it dates today, as it always has")

    # THE SERVER SETS A HOLD'S `before.at`, NEVER THE CLIENT (the Opus review, HIGH). A screen
    # can hold a stale date for a price typed this visit. A forged date must not be kept.
    forged = "2026-01-01T00:00:00+00:00"

    def _held_date(stored, sent_before):
        prior = corpus.Corpus.parse({"version": 1, "skus": {ARTICUNO: stored}})
        after = corpus.Corpus.parse({"version": 1, "skus": {ARTICUNO: {"value": {"withheld": "bullish", "before": sent_before}}}})
        corpus.stamp_answers(prior, after, now)
        return after.answers[ARTICUNO].value["before"].get("at")

    c.equal(
        _held_date({"value": "22.00", "at": first}, {"value": "22.00", "channel": "price", "at": forged}),
        first,
        "a hold takes `before.at` from the stored answer it replaces, and a forged date is dropped",
    )
    c.equal(
        _held_date({"value": "23.00", "at": first}, {"value": "22.00", "channel": "price", "at": forged}),
        None,
        "a `before` that is not the stored answer keeps no date, so its release dates today",
    )
    c.equal(
        _held_date(
            {"value": {"withheld": "bullish", "before": {"value": "22.00", "channel": "price", "at": first}}},
            {"value": "22.00", "channel": "price", "at": forged},
        ),
        first,
        "a hold saved again keeps the date the server gave it the first time, never the client's",
    )

    # --- withholding: an answer that is not a price (D86) ------------------------------------
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

    _suggest_policy_checks(c)
    _suggest_checks(c)

    return c.result()
