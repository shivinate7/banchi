"""Pricing by suggestion: which live listings should change price, and which row needs a person.

PURE OVER PLAIN DICTS. No store, no network, no clock: the caller hands over today and the
listings. The price itself comes from `pipeline/pricing.py` (`list_price`: rule, rounding, the
owner's floor), never from a second copy of that arithmetic. The contract is pinned by
`harness/tests/t5_pricing.py` and the model is `docs/specs/pricing-suggest.md`, sections 2, 3
and 4b.

A trigger is a reason a live price may be wrong. Three fire here: the market moved, the listing
sat unsold above market, and others undercut with shipping. Selling fast and an outside signal
are evidence on a row, not triggers, so nothing here fires on them.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from pipeline import pricing

#: The owner's settings when the policy is silent (spec section 5, step 3). `pipeline/corpus.py`
#: stores them under `limit` and `value_line` and reads these as the defaults.
DEFAULT_LIMIT = Decimal("0.25")
DEFAULT_VALUE_LINE = Decimal("25")

#: Trigger edges (spec section 4b). MOVE is inclusive, PREMIUM is "more than", as the cases pin.
MOVE = Decimal("0.15")
UNSOLD_DAYS = 30
PREMIUM = Decimal("0.10")
UNDERCUT = Decimal("0.10")

MARKET_MOVED, UNSOLD, UNDERCUT_BY_OTHERS = "market_moved", "unsold", "undercut"

#: The `source` a worklist row carries when it is a suggestion (the screen's word for it).
SOURCE = "Suggested"


def check_setting(value, default: Decimal, name: str) -> Decimal:
    """A stored `limit` or `value_line` as a positive `Decimal`; `None` reads the default.

    A `limit` is a fraction, so it also may not pass 1 (25 would mean 2500%, never 25%)."""
    if value is None:
        return default
    try:
        parsed = Decimal(str(value).strip())
    except Exception as exc:
        raise ValueError("{0} {1!r} is not a number".format(name, value)) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("{0} {1!r} must be above zero".format(name, value))
    if name == "limit" and parsed > 1:
        raise ValueError("limit {0!r} is a fraction: 0.25 is 25%, so it may not pass 1".format(value))
    return parsed


def _days_unsold(listing: dict, today: date) -> Optional[int]:
    """Days since the LATER of going live and the last sale here; `None` when neither is known.

    A sale stamp may carry a time, so only its date part counts."""
    dates = [d[:10] for d in (listing.get("first_seen_live"), listing.get("last_sold_at")) if d]
    return (today - date.fromisoformat(max(dates))).days if dates else None


def fired(listing: dict, today: str) -> list:
    """The triggers that fire on one listing, in the order market_moved, unsold, undercut."""
    market, asking = listing.get("market"), listing.get("asking")
    # No market today means no move can be read. A new copy has no asking price to be wrong.
    if not listing.get("live") or not pricing.has_market_data(market) or not asking:
        return []
    out = []
    listed = listing.get("market_listed")
    if pricing.has_market_data(listed) and abs(market - listed) / listed >= MOVE:
        out.append(MARKET_MOVED)
    days = _days_unsold(listing, date.fromisoformat(today))
    if days is not None and days >= UNSOLD_DAYS and asking > market * (1 + PREMIUM):
        out.append(UNSOLD)
    low = listing.get("low_with_shipping")
    if low is not None and low <= asking * (1 - UNDERCUT):
        out.append(UNDERCUT_BY_OTHERS)
    return out


def _pct(fraction: Decimal) -> int:
    return int((abs(fraction) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _reason(listing: dict, triggers: list, today: str) -> str:
    market, asking, listed = listing["market"], listing["asking"], listing.get("market_listed")
    parts = []
    for trigger in triggers:
        if trigger == MARKET_MOVED:
            way = "up" if market > listed else "down"
            parts.append("market {0} {1}% since listed".format(way, _pct((market - listed) / listed)))
        elif trigger == UNSOLD:
            parts.append(
                "unsold {0} days, priced {1}% over market".format(
                    _days_unsold(listing, date.fromisoformat(today)), _pct((asking - market) / market)
                )
            )
        else:
            parts.append(
                "others list at {0} with shipping, {1}% under yours".format(
                    pricing.money(listing["low_with_shipping"]),
                    _pct((asking - listing["low_with_shipping"]) / asking),
                )
            )
    return "; ".join(parts)


def _row(listing: dict, source: str, price: Optional[Decimal], reason: str) -> dict:
    return {
        "sku": listing["sku"],
        "asking": listing.get("asking"),
        "price": price,
        "source": source,
        "reason": reason,
    }


def review(listings: list, policy: dict, today: str) -> dict:
    """Every listing in exactly one group: needs_you, suggested or at_rule."""
    rule = policy.get("rule") or "match"
    basis = pricing.check_basis(policy.get("basis") or "market")
    floor = pricing.check_threshold(policy.get("threshold"))
    limit = check_setting(policy.get("limit"), DEFAULT_LIMIT, "limit")
    value_line = check_setting(policy.get("value_line"), DEFAULT_VALUE_LINE, "value_line")
    out = {"needs_you": [], "suggested": [], "at_rule": []}

    for listing in listings:
        # The triggers and the "no market" test read Market; only the rule's price reads the basis.
        market = listing.get("market")
        base = listing.get("low") if basis == "low" else market
        priced = (
            pricing.list_price(base, rule, floor)
            if pricing.has_market_data(market) and pricing.has_market_data(base)
            else None
        )

        if not listing.get("live"):
            if priced is None:
                out["needs_you"].append(_row(listing, "Rule", None, "no market price"))
            elif priced >= value_line:
                out["needs_you"].append(
                    _row(listing, "Rule", priced, "at or above {0}".format(pricing.money(value_line)))
                )
            else:
                out["at_rule"].append(_row(listing, "Rule", priced, ""))
            continue

        triggers = fired(listing, today)
        # A trigger that leaves the price where it is has nothing to suggest. No asking price fires
        # no trigger. A suggestion moves in its reason's direction: only a market move UP may raise
        # a price, and a market move UP never lowers one.
        up = MARKET_MOVED in triggers and market > listing["market_listed"]
        if not triggers or priced is None or priced == listing["asking"] or (priced > listing["asking"]) != up:
            out["at_rule"].append(_row(listing, "Live", listing.get("asking"), ""))
            continue

        reason = _reason(listing, triggers, today)
        move = abs(priced - listing["asking"]) / listing["asking"]
        if move > limit:
            group, reason = "needs_you", "{0}; moves {1}% from your price".format(reason, _pct(move))
        elif priced >= value_line:
            group, reason = "needs_you", "{0}; at or above {1}".format(reason, pricing.money(value_line))
        else:
            group = "suggested"
        out[group].append(_row(listing, SOURCE, priced, reason))
    return out
