"""One SKU as `#/pricing` draws it — the row `pricing.json` carries, built in ONE place.

WHY IT LEFT `cli/cmd_join.py`. That module's `_pricing_table` built this dict inline and was
its only writer, which was true and sufficient for as long as a join was the only thing that
could produce a priceable row. It stopped being: a review answer stamps a SKU onto a card
(`server/capture_server.py:do_review_answer`), and where no joined run's table already names
that SKU there is no row for `server/pipeline_routes.py:_unsent_ledger` to count the copy
onto — so the card the operator just identified by hand reached `#/pricing` nowhere at all
until somebody pressed Join again on another screen. Measured on the owner's store
2026-09-12: **31 copies across 17 SKUs**, against 458 that folded through because a sibling
copy had happened to resolve at join time.

The route needs the same row for a SKU it found itself. Writing a second copy of this dict
there is the one thing that must not happen — twenty fields, four of them arithmetic, drifting
silently the first time either side gained one. `over_cap` and `claimed_add` exist a few
functions away precisely because two descriptions of one send disagreed once already.

SO THE SHAPE IS DECLARED HERE AND NOTHING ELSE DECLARES IT. `_pricing_table` composes the
`SkuMatch`es a join produced and calls this per match; the route composes a `SkuMatch` for a
SKU the store carries and no table names, and calls this. **The key ORDER is load-bearing and
is asserted**: `pricing.json` is written with `json.dumps(..., indent=2)`, `make demo-seed` is
deterministic from one seeded RNG so that an unchanged tree rebuilds byte-identically, and a
reordered dict would churn the repo on every CI run without changing a value.

IT COMPUTES NO PRICE AND SPENDS NO CAP. Every figure here is read off the `SkuMatch` it is
handed or off the export row that match carries; `pipeline/pricing.py` owns the arithmetic and
`server/pipeline_routes.py` overwrites the four supply fields against the live store (D156).
This is a projection, not a decision.
"""

from __future__ import annotations

from typing import Optional

from pipeline import pricing, tcgcsv

# The three buckets a row can land in, and the names the screen switches on. Re-exported
# rather than restated by callers: `app/src/types.ts:PricingSku.bucket` is the same three.
LISTABLE = "listable"
SUB_THRESHOLD = "sub_threshold"
NO_MARKET_DATA = "no_market_data"

BUCKETS = (LISTABLE, SUB_THRESHOLD, NO_MARKET_DATA)


def cell(row, column):
    """One export cell as a rendered price, or `None` where it is blank.

    Rendered through `tcgcsv.format_price` rather than passed raw, because three of the four
    price columns are FOUR-decimal in every populated cell and two are two — so a screen
    drawing them side by side without this reads `$0.0100` beside `$0.07` and loses the
    decimal column. The raw string travels too (`row`), so nothing is lost.
    """
    value = tcgcsv.parse_price(row.get(column, ""))
    return None if value is None else tcgcsv.format_price(value)


def bucket_for(match, *, below: bool, unpriced: bool) -> str:
    """Which of the three sections this row sits under.

    ASKED OF THE REPORT RATHER THAN RE-DERIVED, where a report exists. A join has already
    partitioned its matches — `report.below_threshold.skus` and `report.no_market_data` — and
    reading those sets is what keeps this projection from being a second opinion about the
    cut-off. A caller with no report (the route, for one SKU it found itself) answers the two
    questions off the match, which is where the report got them.
    """
    if unpriced:
        return NO_MARKET_DATA
    return SUB_THRESHOLD if below else LISTABLE


def sku_row(match, game: str, bucket: str, listing: Optional[dict]) -> dict:
    """One SKU as the pricing table and the pricing worklist both carry it.

    `listing` is the store's own four counters or `None` where the SKU has no listing record.
    THE FOURTH KEY IS NOT OPTIONAL (D115): `live` is the export's READING and the screen draws
    the ESTIMATE, so a payload carrying the reading alone would over-report by exactly the
    copies sold since — on the screen where the operator decides money. A derived value never
    rides a payload; the two numbers travel and the reader subtracts.
    """
    return {
        "sku": match.sku,
        "game": game,
        # VERBATIM, every cell, unmodified. D49's whole premise is the owner's
        # "I want all the data from the CSV shown when I make the decision".
        "row": dict(match.row),
        "bucket": bucket,
        "copies": match.copies,
        "add_to_quantity": match.add_to_quantity,
        "backstock": match.backstock,
        "live_before": match.live_before,
        # THE LIVE FIGURE THE CAP WAS COMPUTED FROM: the newer of the store's
        # reading and this export's (D87, amended). `live_before` beside it is
        # the export's column alone, kept because it is what the CSV says.
        "live_now": match.live_now,
        "committed": len(match.committed_positions),
        # WHAT TCGPLAYER ACTUALLY HOLDS, AND WHY `live_before` BESIDE IT IS NOT
        # THAT NUMBER. `live_before` is the export's live column alone, which
        # reads 0 for every copy sitting on an import nobody has reconciled —
        # measured at 167 pushed copies across 72 SKUs of the owner's store,
        # zero of them live, so a screen drawing it said TCGplayer holds
        # nothing about SKUs it holds several of. `copies_out` is live plus
        # pending, per SKU and across every box. All three ship: the screen
        # names the export's own figure where it means the export, `live_now`
        # where it means what was believed, and this one where it means the
        # shelf (D59).
        "copies_out": match.copies_out,
        "at_cap": match.add_to_quantity == 0,
        # The SENTENCE, composed where the numbers are, never re-derived from
        # the three fields above. `at_cap` says a row was not written and
        # cannot say why — at the cap, or held out by an unreconciled push, or
        # every copy in this run already gone. A screen reassembling that from
        # parts is a second copy of `SkuMatch.nothing_to_add`'s reasoning with
        # nothing auditing the two against each other.
        "nothing_to_add": match.nothing_to_add,
        "condition": match.condition,
        "set_name": match.set_name,
        "name": match.name,
        "snap": {
            "market": cell(match.row, tcgcsv.MARKET_PRICE_COLUMN),
            "direct_low": cell(match.row, tcgcsv.DIRECT_LOW_COLUMN),
            "low": cell(match.row, tcgcsv.LOW_PRICE_COLUMN),
            "low_with_shipping": cell(match.row, tcgcsv.LOW_WITH_SHIPPING_COLUMN),
            "now": cell(match.row, tcgcsv.PRICE_COLUMN),
        },
        "presets": pricing.preset_prices(match.row),
        "rule_price": None if match.list_price is None else str(match.list_price),
        # The first copy in box-walk order and how many there are — the
        # representative photograph, named rather than picked silently, and
        # steppable on the screen. `positions` is already sorted.
        "positions": [
            {"box": pos.box, "index": pos.index, "label": pos.label}
            for pos in match.positions
        ],
        "listing": None if listing is None else dict(listing),
    }
