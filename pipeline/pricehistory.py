"""Price history: what a SKU has actually been selling for, and how fast.

D8 makes the TCGplayer Filtered CSV the pricing source, and everything downstream of that
is a statement about RIGHT NOW — sixteen columns, four of them prices, not one carrying a
timestamp or a sample size. So the product has never been able to answer "is this rising",
which is exactly the question D49's `bullish` withhold and its `watch_above` threshold are
set against. An operator holding a card back has been doing it from memory.

THIS MODULE IS A LIBRARY AND NOT A FEATURE. Nothing calls it, no route serves it, no screen
draws it. `CLAUDE.md`'s route-is-not-a-feature rule says a capability that exists only in a
package is not done and must never be reported as done — so it is reported here as what it
is: a reader with harness coverage and no way in from the app. Surfacing it means a route, a
client function and a control, and that is a separate piece of work with a decision entry.

--------------------------------------------------------------------------------------
WHAT IS ACTUALLY PUBLIC, MEASURED RATHER THAN ASSUMED

`docs/DECISIONS.md`'s Someday entry stated twice that this data does not exist. Both
statements were false and the entry is corrected; what follows is what was measured.

  infinite-api.tcgplayer.com/price/history/<productId>/detailed?range=<r>

WAS public with no key, no cookie, no `Referer`, no session — HTTP 200 to a bare `curl` —
MEASURED 2026-08-30 (D62). THAT PREMISE ROTTED (see D216):
measured again 2026-09-19, the same honest `USER_AGENT` below now answers HTTP 403 on this
host, while a browser User-Agent still answers 200 with no cookie, no `Referer` and no
session — the request signature alone decides it. `AGENT_ENV` below is the escape hatch,
read the way `server/tcg_export.py` already reads its own copy of the same key (D64); a
checkout with no override still presents the honest string and is told by name (`Blocked`)
rather than folded into `Unreachable`, whose whole meaning is that nothing is wrong with the
run. tcgcsv.com answers either User-Agent, measured the same day, so one knob covers both
hosts.

It answers one result per skuId (variant x condition) carrying that RANGE's own totals and a
list of buckets of {marketPrice, quantitySold, lowSalePrice, highSalePrice,
transactionCount, bucketStartDate}. The totals are per range and not lifetime — measured on
Vilemaw, 642 over `month`, 1,763 over `quarter`, 2,977 over `semiannual` — and `annual`
agreeing with `semiannual` on a card released in May is the range running past the card
rather than a lifetime figure.

  range=       buckets x width      span
  month        30 x 1 day           29 days
  quarter      30 x 3 days          87 days
  semiannual   26 x 7 days          175 days
  annual       52 x 7 days          357 days

`week`, `year`, `all` and `latest` are not ranges: they answer HTTP 400 with a validation
error, which is the honest failure and is why `RANGES` is a closed tuple here rather than a
string passed through.

THIS IS AGGREGATE, NOT FILLS, AND THAT BOUNDARY IS THE WHOLE OF THE HONESTY BELOW. A bucket
says how many copies sold and the lowest and highest price among them. It does not say what
any one copy sold for. "What did the last three copies sell for" is still not answerable —
that panel on a product page is a different, credentialed endpoint, and nothing here goes
looking for it.

--------------------------------------------------------------------------------------
THE JOIN IS LOCAL AND CALLS NOTHING TCGPLAYER OWNS

The endpoint is keyed by productId. The export is keyed by SKU, and there is no SKU-keyed
history endpoint — probed, 404. A SKU is a (product, variant, condition) triple, so the walk
is sku -> product -> history, and the response then carries `skuId` on every result, which is
what makes the last hop EXACT rather than a variant-string match. That is worth stating
plainly because it is the one place this could have been fuzzy and is not: we ask about a
product and then pick our own SKU out of the answer by its own number.

`tcgcsv.com` publishes TCGplayer's own catalog as a nightly mirror — categories, groups and
products with `extendedData`. It publishes NO SKUs, so it cannot answer the last hop and
nothing here asks it to. What it answers is:

  Product Line cell -> categoryId     by NAME, against /tcgplayer/categories
  Set Name cell     -> groupId        by NAME, against /tcgplayer/<cat>/groups
  (Number, Product Name) -> productId against /tcgplayer/<cat>/<group>/products

MEASURED ACROSS ALL FOUR COMMITTED EXPORTS: 3,588 distinct products, 100% resolved, ZERO
ambiguous and ZERO missed — Riftbound 1,552, One Piece 702, the wide Pokemon export 1,136,
SV09 198. Set names matched their group names EXACTLY, 19 of 19, in all three product lines;
the fold is kept anyway, because a set name that drifts costs a whole set at once.

THE CATEGORY IS RESOLVED BY NAME RATHER THAN BY A HARDCODED INTEGER, and that is a decision
rather than a convenience. `pipeline/games.py` already authors the exact `Product Line` cell
per game, D22 audits it against the committed exports, and tcgcsv's category `name` field is
byte-identical to it for all three catalogued games (Pokemon 3, One Piece Card Game 68,
Riftbound League of Legends Trading Card Game 89 — verified). A table of integers here would
be a SECOND per-game fact in a second file, which is the drift D16 exists to catch; and it
would fail differently from the export rather than with it. A category rename upstream breaks
the `Product Line` cell too, so this way both halves fail together and the remedy is one
edit in the registry.

--------------------------------------------------------------------------------------
THE SAME MIRROR ALSO SERVES CURRENT PRICES, AND THEY ARE NOT SKU-LEVEL

  tcgcsv.com/tcgplayer/<cat>/<group>/prices

answers {productId, lowPrice, midPrice, highPrice, marketPrice, directLowPrice,
subTypeName} — 445 rows over 321 products for Riftbound/Unleashed, measured. `subTypeName`
is the PRINTING (`Normal` / `Foil`) and never the condition, so it is product-level: Vilemaw
is five export rows by condition against ONE row here. It carries no `TCGplayer Id` and no
`Total Quantity`, the two columns D11's listing path is built on, so it supplements an
export and can never replace one. `PrintingPrice` carries the full argument and the reason
D8 is not reopened by it.

--------------------------------------------------------------------------------------
THE RANGES OVERLAP AND MUST NEVER BE CONCATENATED

`annual` is not the year before `month`; it is 357 days that INCLUDE the same recent days at
a coarser width. Measured on Vilemaw, `month` spans 2026-08-01..2026-08-30 and `annual`
spans 2025-09-01..2026-08-24. Adding them double-counts the recent window and skews every
volume-weighted figure over the result, so `Reading` keeps them separate and offers nothing
that merges two series. The wider range is also the STALER one — weekly buckets are stamped
at the start of their week, so `annual` was six days behind `month` on the same card at the
same moment.

--------------------------------------------------------------------------------------
WHY THERE IS NO TRUE VWAP HERE, AND WHY THE BOUND IS NOT A RESULT

A volume-weighted average price is a mean over FILLS. We do not have fills; we have a
per-bucket market price, a count, and a low and a high. So:

  `vwap`   weights each bucket's `marketPrice` by its `quantitySold`. It is a
           volume-weighted mean of a daily aggregate — the best point estimate available,
           and the number to anchor on.
  `bound`  weights `lowSalePrice` and `highSalePrice` the same way. It is the interval
           every possible true VWAP lies inside, and it is a SANITY CHECK, never a result.

Measured on Moonfall (Unleashed 198/219, sku 9191486) over `quarter`: vwap $16.33 against a
bound of $12.54..$20.35. The bound is 48% of the point estimate wide, or 62% of its own low
end — which is why `Bound.width` states its denominator in its own name rather than leaving
"62% wide" and "48% wide" to be read as disagreeing about the same card.

If a caller ever reports the bound as the answer, or renders the two as though they were a
price and an error bar of comparable authority, that is this paragraph being ignored.

`trendingMarketPricePercentages` is on every result and came back `{}` on every card
probed. Nothing here reads it, and nothing should start without measuring it first.

--------------------------------------------------------------------------------------
THREE OPERATIONAL FACTS THAT COST TIME TO FIND

BUCKETS ARRIVE NEWEST FIRST. `buckets[0]` is today and `buckets[-1]` is the oldest.
`Series.buckets` is sorted ASCENDING at parse time and the raw order is never used, because
momentum is a subtraction between the two ends of a list and reading the list backwards
inverts its sign silently — a rising card reported as falling, with nothing to see.

BUCKET BOUNDARIES ARE PER-SKU AND DO NOT ALIGN. Vilemaw's Near Mint quarter starts
2026-06-02 and its Lightly Played quarter starts 2026-06-04, in one response. Nothing here
compares two series bucket-by-bucket, and nothing should.

TCGCSV.COM 401s THE DEFAULT `urllib` USER-AGENT. Any other string is fine; `curl` is fine.
This is worth a line because the failure LIES: a 401 on an endpoint being evaluated for
whether it needs credentials reads as "it needs credentials", which is the exact false
conclusion the corrected Someday entry was carrying. `infinite-api` does not care, and the
header is sent to both anyway.

--------------------------------------------------------------------------------------
WHAT THIS MODULE MAY NOT DO

`pipeline/` imports nothing outside itself and the stdlib — no `store`, no `cli`, no
`identify` — and this module keeps that. It therefore takes a cache DIRECTORY rather than
asking `store.files` where home is, which is also what lets the harness point it at a
temporary directory with no environment to set.

It is the first module in this package that opens a socket, and that is contained on
purpose: `fetch_json` is the only impure function, every reading and every metric below is
a pure function of a parsed payload, and `Market` takes the fetcher as an argument. The
harness asserts the join against a committed fixture and never against a live fetch.
"""

from __future__ import annotations

import contextlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pipeline import games, join, pricing, tcgcsv

# --------------------------------------------------------------------------------- hosts

CATALOG_HOST = "https://tcgcsv.com"
HISTORY_HOST = "https://infinite-api.tcgplayer.com"

# Sent to both hosts. tcgcsv refuses the `urllib` default with a 401 (see the header); this
# host is polite rather than anonymous, because a free public mirror is entitled to know who
# is hammering it and to block us by name rather than by guessing. IT IS ALSO THE VALUE
# INFINITE-API NOW ANSWERS 403 TO (D216, measured 2026-09-19)
# — kept as the DEFAULT so a checkout with no override behaves exactly as it always has and
# fails the same honest way, rather than reaching for a disguise nobody asked this module to
# wear.
USER_AGENT = "pkmnscan/1.0 (+private single-operator inventory tool)"

# THE ESCAPE HATCH'S NAME, NOT ITS VALUE — a string only, and never read from `.env` here.
# `pipeline/` imports nothing outside itself and the stdlib (see `Market`'s header below), so
# this module cannot ask `envfile` for anything; the caller that already may (D64's own
# `server/tcg_export.py`, and `server/pipeline_routes.py` beside it) resolves the value and
# hands it to `fetch_json`/`Market` the same way it already hands `Market` a cache directory
# — passed in, never discovered. Spelled here as a literal, identical to
# `server/tcg_export.py:AGENT_ENV`, ON PURPOSE: reused rather than a second knob, because it
# already means "the User-Agent to present to TCGplayer" and tcgcsv answers either value
# (measured 2026-09-19) — see D216 for the argument.
AGENT_ENV = "PKMNSCAN_TCG_USER_AGENT"

# The four the endpoint accepts. A closed tuple rather than a passed-through string: every
# other spelling answers HTTP 400, and a range that silently returned nothing would read as
# a card with no sales.
RANGES: Tuple[str, ...] = ("month", "quarter", "semiannual", "annual")

# The pair to fetch when a caller wants "the picture". Daily resolution for a decision about
# this week, weekly for a year of shape. `quarter` and `semiannual` are reachable and are
# not fetched by default, because three ranges is three times the requests for a third view
# of the same card.
DEFAULT_RANGES: Tuple[str, ...] = ("month", "annual")

REQUEST_TIMEOUT_SECONDS = 30

# Between two live requests. Not a rate limit anyone published — a courtesy, sized so a
# whole box (543 cards, two ranges) spends about three minutes of wall clock rather than
# arriving as a burst. `Market` sleeps only when it actually goes to the network, so a warm
# cache costs nothing.
COURTESY_DELAY_SECONDS = 0.15

# How long a cached answer is served before it is re-fetched.
#
# CATEGORIES, GROUPS AND PRODUCTS NEVER EXPIRE, ON THE OWNER'S OWN RULING (2026-09-20): the
# set of cards in a catalogue set does not change from pull to pull. Measured independently
# across settled Pokemon sets: recently-modified products all carry their original low
# product ids, and no new ids appear — what churn exists is field edits to an existing
# record, never an addition or removal. `float("inf")` over `_cached`'s own
# `self._now() - fetched_at > ttl` comparison is always False, so a pulled entry is served
# forever rather than re-fetched — a NIGHTLY-mirror argument for a one-week TTL used to sit
# here, and it no longer applies: membership does not drift, so there is nothing for a
# re-fetch to "self-correct". This also means the catalogue host, `tcgcsv.com`, spends its
# request budget establishing a fact once rather than re-confirming one that cannot change
# — worth stating because the OTHER host this module reaches, `infinite-api.tcgplayer.com`
# (price history), has refused this client outright after enough requests in one sitting,
# while tcgcsv has throttled nothing across many probes.
#
# THE TRADE, NAMED RATHER THAN HIDDEN: a cache that never expires trades correctness-by-
# expiry for staleness nothing will ever repair on its own, and for a directory that only
# grows. Today that trade is a clear win — roughly 900 subject SKUs across a handful of
# sets, a cache small enough that a wrong entry costs one `rm -rf` of a derived directory.
# What would force a different answer: this cache's size on disk becoming material, or the
# store covering enough sets that ONE corrupted or partial entry stops being cheap to
# notice by hand. Neither is true yet. Genuinely unmeasured, and cheap to check later: does
# the mirror ever CORRECT a collector number on an existing card — the one field
# `pipeline/join.py` actually reads off it. Two snapshots a week apart would settle that at
# no request cost. Not chased here.
#
# `Market.prices` DOES NOT SHARE THIS CONSTANT, ON PURPOSE, EVEN THOUGH IT USED TO. It
# answers a group's CURRENT prices, which move daily — a fact this docstring already flagged
# as unresolved ("it shares the catalog TTL rather than the history one... which argues for
# a shorter life") before this entry answered the CATALOGUE half of that question. Giving it
# `CATALOG_TTL_SECONDS` now would silently make daily prices permanent, which is the exact
# opposite of what the owner asked for — `PRICE_TTL_SECONDS` below is `prices`' own knob,
# unchanged in VALUE from the old shared constant, so this change touches membership caching
# only and takes no new position on how fresh a price reading should be.
#
# The history is the whole point of the module and its finest bucket is a day, so an hour is
# short enough that nobody reads a stale figure and long enough that re-running an analysis
# in one sitting costs no requests.
CATALOG_TTL_SECONDS = float("inf")
PRICE_TTL_SECONDS = 7 * 24 * 60 * 60
HISTORY_TTL_SECONDS = 60 * 60

# tcgcsv's `extendedData` field carrying the printed collector number. Named rather than
# inlined because it is the join key and `Number` is also a column name in the export — two
# different sources spelling one identity, which is `number_index_key`'s whole subject.
EXTENDED_NUMBER = "Number"

# Every ratio below is quantized to this. A Decimal division runs to 28 significant figures
# by default, and `+0.7119370979270907791279485347` is not a more precise statement about a
# card than `+0.7119` — it is the same statement with the reader's eye spent on it. Prices
# keep `pricing.round_money`, which is the repo's one money rule and is not restated here.
RATIO = Decimal("0.0001")


class PriceHistoryError(RuntimeError):
    """The reader could not answer. Every refusal below is one of these."""


class UnknownRange(PriceHistoryError):
    """A range the endpoint does not accept. See `RANGES`."""


class NotResolvable(PriceHistoryError):
    """An export row could not be walked to a productId, and says at which hop it stopped."""


class Unreachable(PriceHistoryError):
    """The network refused, timed out, or answered something that is not JSON."""


class Blocked(PriceHistoryError):
    """A host answered HTTP 403 to a request it once answered — a client refused BY NAME.

    A SIBLING OF `Unreachable`, NOT A SUBCLASS. `history_unreachable`'s whole meaning (D62)
    is that nothing is wrong with the run and a public mirror simply did not answer; that is
    the wrong sentence for a 403, which says the client presenting itself is the thing being
    declined, and the honest remedy is `AGENT_ENV` rather than "try again"
    (D216). A caller that catches `Unreachable` and not this
    is left exactly as unhandled as one that catches neither — on purpose, so the omission
    is loud.
    """


# ------------------------------------------------------------------------------- readings


def _decimal(text) -> Optional[Decimal]:
    """A price cell, or None. `""`, `None` and `"0"` are all "no price here".

    ZERO IS NOT A PRICE AND THAT IS D9's RULE, NOT A CONVENIENCE. The endpoint writes `"0"`
    into `lowSalePrice` and `highSalePrice` on every bucket that sold nothing, and it writes
    a real `marketPrice` beside them. Reading those zeros as prices drags every mean toward
    zero; reading them as absent is what `has_market_data` already says one module over.
    """
    if text is None:
        return None
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None


def _int(text) -> int:
    """A count. Every numeric field on this endpoint arrives as a STRING, including `"0"`."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return 0


def _bucket_date(text) -> Optional[date]:
    try:
        return datetime.strptime(str(text)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Bucket:
    """One day or one week of one SKU. Every field is what the endpoint said, coerced."""

    start: Optional[date]
    market: Optional[Decimal]
    quantity: int
    transactions: int
    low: Optional[Decimal]
    high: Optional[Decimal]

    @property
    def sold(self) -> bool:
        """Did anything actually change hands here?

        The predicate every weighted mean below filters on. A bucket with no sales still
        carries a `marketPrice` — TCGplayer's own standing figure — and including it would
        weight an opinion equally with a transaction.
        """
        return self.quantity > 0

    @classmethod
    def parse(cls, payload: Dict) -> "Bucket":
        return cls(
            start=_bucket_date(payload.get("bucketStartDate")),
            market=_decimal(payload.get("marketPrice")),
            quantity=_int(payload.get("quantitySold")),
            transactions=_int(payload.get("transactionCount")),
            low=_decimal(payload.get("lowSalePrice")),
            high=_decimal(payload.get("highSalePrice")),
        )


@dataclass(frozen=True)
class Bound:
    """The interval every possible true VWAP lies inside. NEVER A RESULT — see the header.

    `width_of_vwap` and `width_of_low` are the same interval over two denominators, both
    named, because one card's bound is honestly describable as "48% wide" and "62% wide" and
    a bare percentage invites the two to be read as a disagreement.
    """

    low: Decimal
    high: Decimal
    vwap: Decimal

    @property
    def width_of_vwap(self) -> Decimal:
        if not self.vwap:
            return Decimal(0)
        return ((self.high - self.low) / self.vwap).quantize(RATIO)

    @property
    def width_of_low(self) -> Decimal:
        if not self.low:
            return Decimal(0)
        return ((self.high - self.low) / self.low).quantize(RATIO)


@dataclass(frozen=True)
class Momentum:
    """Where the price went, as the difference between the two ends of the series.

    `window` is how many SOLD buckets each end is averaged over — sold, not calendar, because
    a quiet card's calendar tail is buckets carrying a standing market price and no
    transactions, and averaging those measures TCGplayer's opinion rather than the market's.

    POSITIVE IS RISING. Stated because it is the one thing a reader of a signed number has
    to be told, and because the endpoint hands its buckets over newest-first, so a sign here
    is one unsorted list away from meaning its opposite.
    """

    early: Optional[Decimal]
    late: Optional[Decimal]
    window: int

    @property
    def change(self) -> Optional[Decimal]:
        if self.early is None or self.late is None:
            return None
        return self.late - self.early

    @property
    def fraction(self) -> Optional[Decimal]:
        if self.early is None or self.late is None or self.early == 0:
            return None
        return ((self.late - self.early) / self.early).quantize(RATIO)


@dataclass(frozen=True)
class Series:
    """One SKU's history over one range, buckets ASCENDING by date.

    `total_quantity_sold` and `total_transaction_count` are the endpoint's own totals for the
    range and are NOT recomputed from the buckets. They are the more trustworthy of the two
    — the buckets are a rendering of the same underlying data at whatever width the range
    asked for — and a recomputation that disagreed would be indistinguishable from a bug.
    """

    sku: str
    product_id: int
    range: str
    variant: str
    condition: str
    language: str
    total_quantity_sold: int
    total_transaction_count: int
    buckets: Tuple[Bucket, ...]

    @classmethod
    def parse(cls, payload: Dict, product_id: int, range_: str) -> "Series":
        buckets = [Bucket.parse(b) for b in (payload.get("buckets") or ())]
        # ASCENDING, ALWAYS. The endpoint sends newest-first; `momentum` subtracts one end
        # from the other, so trusting the wire order inverts the sign of every reading with
        # no symptom. Dateless buckets sort last rather than raising: one unparseable date
        # is not a reason to lose a year of a card's history.
        buckets.sort(key=lambda b: (b.start is None, b.start or date.min))
        return cls(
            sku=str(payload.get("skuId") or ""),
            product_id=product_id,
            range=range_,
            variant=str(payload.get("variant") or ""),
            condition=str(payload.get("condition") or ""),
            language=str(payload.get("language") or ""),
            total_quantity_sold=_int(payload.get("totalQuantitySold")),
            total_transaction_count=_int(payload.get("totalTransactionCount")),
            buckets=tuple(buckets),
        )

    @property
    def sold_buckets(self) -> Tuple[Bucket, ...]:
        return tuple(b for b in self.buckets if b.sold)

    @property
    def latest_market(self) -> Optional[Decimal]:
        """The most recent bucket carrying a market price at all, sold or not.

        Deliberately not filtered to sold buckets: this is the figure to compare against the
        export's `TCG Market Price`, and that column is a standing number too.
        """
        for bucket in reversed(self.buckets):
            if bucket.market is not None:
                return bucket.market
        return None

    # ------------------------------------------------------------------------- metrics

    @property
    def vwap(self) -> Optional[Decimal]:
        """Volume-weighted mean of `marketPrice`. The number to anchor on.

        None rather than zero when nothing sold: D9 is emphatic that a missing price is an
        unknown price and not a low one, and the same rule decides this. A card with no sales
        in the range has no average sale price, and $0.00 is the reading that hands a chase
        card away at the floor.
        """
        numerator = Decimal(0)
        denominator = Decimal(0)
        for bucket in self.sold_buckets:
            if bucket.market is None:
                continue
            numerator += bucket.market * bucket.quantity
            denominator += Decimal(bucket.quantity)
        if denominator == 0:
            return None
        return pricing.round_money(numerator / denominator)

    @property
    def bound(self) -> Optional[Bound]:
        """The interval a true VWAP must lie in. A SANITY CHECK, NEVER A RESULT.

        Weighted over the buckets that carry BOTH a low and a high, which is not always every
        sold bucket — the endpoint occasionally writes a sale count with no sale prices, and
        weighting a low of zero against a real high would widen the interval toward a bound
        nothing supports.
        """
        vwap = self.vwap
        if vwap is None:
            return None
        low = Decimal(0)
        high = Decimal(0)
        denominator = Decimal(0)
        for bucket in self.sold_buckets:
            if bucket.low is None or bucket.high is None:
                continue
            low += bucket.low * bucket.quantity
            high += bucket.high * bucket.quantity
            denominator += Decimal(bucket.quantity)
        if denominator == 0:
            return None
        return Bound(
            low=pricing.round_money(low / denominator),
            high=pricing.round_money(high / denominator),
            vwap=vwap,
        )

    def momentum(self, window: int = 5) -> Momentum:
        """First `window` sold buckets against the last `window`. Positive is rising.

        Both ends are volume-weighted for the same reason `vwap` is: a five-unit day and a
        fifty-unit day are not equal evidence about what the card is worth.

        THE TWO ENDS MAY OVERLAP AND THAT IS DELIBERATE. A card with six sold buckets and a
        window of five compares buckets 1-5 against 2-6, which is a damped reading of a real
        move rather than a refusal. What it may not do is compare a window against ITSELF and
        report zero as though it were a measurement, so a series with fewer sold buckets than
        one window answers None on both ends and `change` is None with it.
        """
        if window <= 0:
            raise ValueError("window must be positive")
        sold = self.sold_buckets
        if len(sold) < window:
            return Momentum(early=None, late=None, window=window)
        return Momentum(
            early=_weighted_market(sold[:window]),
            late=_weighted_market(sold[-window:]),
            window=window,
        )

    @property
    def liquidity(self) -> int:
        """Copies sold across the range, as the endpoint reports it. How fast this moves."""
        return self.total_quantity_sold

    @property
    def units_per_transaction(self) -> Optional[Decimal]:
        """Copies per order. Above 1 means people are buying playsets rather than singles.

        Worth having beside `liquidity` because the two answer different questions about the
        same number: 1,763 copies in 1,455 orders is a card being bought one at a time by a
        lot of people, and the same 1,763 in 90 orders would be a card being bought by
        dealers. D7 caps a listing at four copies, so which of those it is decides whether
        the cap is binding.
        """
        if self.total_transaction_count <= 0:
            return None
        return (
            Decimal(self.total_quantity_sold) / Decimal(self.total_transaction_count)
        ).quantize(Decimal("0.001"))

    @property
    def dispersion(self) -> Optional[Decimal]:
        """Volume-weighted mean of (high - low) within a bucket. How wide the market is.

        A same-bucket spread, so it measures disagreement between sellers on one day rather
        than movement across the range — which is `momentum`'s job. A card whose dispersion
        approaches its own VWAP is a card where the listed price decides the sale, and that
        is the case where D9's undercut rules earn their keep.
        """
        numerator = Decimal(0)
        denominator = Decimal(0)
        for bucket in self.sold_buckets:
            if bucket.low is None or bucket.high is None:
                continue
            numerator += (bucket.high - bucket.low) * bucket.quantity
            denominator += Decimal(bucket.quantity)
        if denominator == 0:
            return None
        return pricing.round_money(numerator / denominator)


def _weighted_market(buckets: Sequence[Bucket]) -> Optional[Decimal]:
    numerator = Decimal(0)
    denominator = Decimal(0)
    for bucket in buckets:
        if bucket.market is None or bucket.quantity <= 0:
            continue
        numerator += bucket.market * bucket.quantity
        denominator += Decimal(bucket.quantity)
    if denominator == 0:
        return None
    return pricing.round_money(numerator / denominator)


def parse_history(payload: Dict, product_id: int, range_: str) -> Dict[str, Series]:
    """The endpoint's answer, as `{skuId: Series}`.

    `result` IS NULLABLE, AND "NO HISTORY" IS NOT AN ERROR ON THE WIRE. HTTP 200 with
    `{"count": 0, "result": null}` is what this endpoint answers for a product it has nothing
    to say about, so a caller that checked the status code and iterated the result raises a
    TypeError and reads it as a bug in the reader. An empty mapping is the honest answer.

    IT IS NOT THE TYPO CASE, AND FRAMING IT THAT WAY IS THE MISTAKE THIS PARAGRAPH USED TO
    MAKE. A nonexistent productId answers that way, which is easy to find and easy to
    over-generalise from; so do REAL, CATALOGUED PRODUCTS that have simply never been seen to
    sell — **477209 and 245412 both do, measured**. A reader that treated a null result as
    "bad id" would go looking for a join defect over a card that is merely illiquid, which is
    the wrong file to open and the wrong conclusion to draw about the join.
    """
    results = payload.get("result") or ()
    series = (Series.parse(entry, product_id, range_) for entry in results)
    return {s.sku: s for s in series if s.sku}


@dataclass(frozen=True)
class Reading:
    """One SKU across the ranges that were fetched. What a caller actually holds.

    `series` is keyed by range name and may be missing a range entirely — a card whose
    product resolved but which the endpoint has never seen sell answers no series at all,
    and that is a real state rather than a failure.

    THE RANGES OVERLAP. NOTHING HERE COMBINES THEM AND NOTHING MAY START. `annual` is not the
    part of the year before `month` — it is 357 days that INCLUDE the same recent days at a
    coarser width, so concatenating the two double-counts the recent window and skews every
    volume-weighted figure computed over the result. Measured on Vilemaw: `month` spans
    2026-08-01..2026-08-30 and `annual` spans 2025-09-01..2026-08-24, overlapping most of
    August. There is deliberately no function on this class that merges two series, and
    `recent` and `broad` return them SEPARATELY for that reason — the pair is two readings to
    present side by side, never two halves to add up.

    AND THE WIDER RANGE IS THE STALER ONE, which is the half nobody expects. Weekly buckets
    are stamped at the start of their week, so `annual`'s newest bucket was six days behind
    `month`'s on the same card at the same moment (2026-08-24 against 2026-08-30). Read
    `latest_market` off the FINEST range present; taking it off `broad` answers a question
    about last week.
    """

    sku: str
    product_id: int
    series: Dict[str, Series]

    def of(self, range_: str) -> Optional[Series]:
        return self.series.get(range_)

    @property
    def recent(self) -> Optional[Series]:
        """The finest-grained series present. What "is this moving right now" reads."""
        for range_ in RANGES:
            if range_ in self.series:
                return self.series[range_]
        return None

    @property
    def broad(self) -> Optional[Series]:
        """The widest series present. What "what has this been worth" reads."""
        for range_ in reversed(RANGES):
            if range_ in self.series:
                return self.series[range_]
        return None


# ----------------------------------------------------------------------------- the join


@dataclass(frozen=True)
class ProductIndex:
    """One tcgcsv group's products, indexed the two ways an export row can find one.

    NUMBER FIRST, NAME AS THE TIEBREAK AND THEN AS THE LAST RESORT — which is D35's shape,
    reached for here for D35's reason and bounded the same way. `CLAUDE.md` forbids joining
    on Product Name as the KEY because it inconsistently embeds numbers; both sides fold
    through `join.name_index_key`, so the embedded number is folded away rather than matched
    against, and the name is consulted only where the number index answered nothing or
    answered more than once.

    THE NAME RUNG IS REACHED ONLY BY ROWS WITH NO NUMBER TO USE, AND THAT WAS MEASURED
    RATHER THAN HOPED. It fires on 355 of the 3,588 products in the four committed exports,
    and ALL 355 carry a BLANK `Number` cell: not one row with a number in it ever fell
    through to the name index. So the rung is not a rescue for a number that failed to match
    — it is the blank-`Number` case the schema has always had, promos and code cards, which
    `Catalog.rows_for_blank_number_name` answers one module over for the same reason.

    That is the measurement to re-run before widening anything here, and it is the one that
    would go first: a non-blank number reaching this rung means the number index has stopped
    agreeing with the mirror, and the name would then be covering for it silently.

    AND IT IS NOT THE JOIN THAT LISTS ANYTHING, which is what makes the rung affordable here
    at all. A wrong answer costs a wrong sales chart on a screen nobody has built yet. A
    wrong answer in `pipeline/join.py` costs a card listed as a different card.

    THIS CLASS TAKES ONLY A NUMBER AND A NAME, NEVER A SKU (D254).
    A session briefly widened `find` to weigh a CARD's own read name against the number it
    found (D240's measured seam), and the owner's review reversed it: `pipeline/pricearchive.py`
    and `pipeline/productview.py:row_for_sku` now decide WHICH `(number, name)` pair this
    class is ever asked about, before it is asked — the archive's own already-verified
    productId for that SKU where one exists, else the SKU's OWN row in the store's cached
    Filtered Export (its `Product Name` and `Number`, which describe that SKU's product by
    definition and were never read off a photograph), else this class exactly as it always
    was. `find` itself is unchanged from the shape D240 found "zero ambiguous" over: it is
    handed a trustworthy pair now, so it needs no dispute check of its own.
    """

    by_number: Dict[str, Tuple[int, ...]]
    by_name: Dict[str, Tuple[int, ...]]

    @classmethod
    def build(cls, products: Iterable[Dict]) -> "ProductIndex":
        numbers: Dict[str, List[int]] = {}
        names: Dict[str, List[int]] = {}
        for product in products:
            try:
                product_id = int(product["productId"])
            except (KeyError, TypeError, ValueError):
                continue
            number = extended(product, EXTENDED_NUMBER)
            if number:
                numbers.setdefault(join.number_index_key(number), []).append(product_id)
            name = product.get("name")
            if name:
                names.setdefault(join.name_index_key(name), []).append(product_id)
        return cls(
            by_number={k: tuple(v) for k, v in numbers.items()},
            by_name={k: tuple(v) for k, v in names.items()},
        )

    def find(self, number, name) -> Optional[int]:
        """The productId for this (number, name), or None. Never a guess.

        Ambiguity answers None rather than picking the first, which is the same refusal
        `geometry.detect_card` makes and for the same reason: a "not found" a caller can act
        on beats a plausible wrong answer it cannot see. Measured at zero ambiguous across
        all four committed exports, which is a fact about those exports and not a promise
        about the next one.

        A NUMBER-KEY MISS GETS ONE REPAIR BEFORE THE NAME RUNG, THE SAME ORDER
        `pipeline/join.py:_walk` ALREADY USES FOR THE REAL LISTING JOIN
        (D234). D55's `strip_set_code` removes a set code the model glued onto the
        front of a Riftbound read (`SFD • 013/221` -> `013/221`) — the mechanism was
        never broken, it was simply never REACHED here: this accessor folded the raw
        `number` through `number_index_key` and fell straight to the ambiguity-prone name
        rung on a miss, never trying the stripped form the way `_walk`'s own `repair` step
        does before giving up on a number. Asked only on a miss, exactly like `_walk`'s own
        repair — a number that already matched is never rewritten.
        """
        key = join.number_index_key(number)
        hits = self.by_number.get(key, ()) if key else ()
        if not hits:
            repaired = join.strip_set_code(number)
            if repaired and repaired != str(number or "").strip():
                repaired_key = join.number_index_key(repaired)
                hits = self.by_number.get(repaired_key, ()) if repaired_key else hits
        if len(hits) > 1:
            narrowed = tuple(
                pid for pid in hits if pid in self.by_name.get(join.name_index_key(name), ())
            )
            hits = narrowed if len(narrowed) == 1 else hits
        if not hits:
            hits = self.by_name.get(join.name_index_key(name), ())
        return hits[0] if len(hits) == 1 else None


@dataclass(frozen=True)
class PrintingPrice:
    """One row of tcgcsv's `/prices`: current prices for a product in ONE PRINTING.

    A PRINTING IS NOT A CONDITION, AND THAT IS THE WHOLE OF WHAT THIS CAN AND CANNOT DO.
    `subTypeName` is `Normal` or `Foil` — measured across Riftbound/Unleashed, 445 rows over
    321 products, never more than TWO rows for one product. The export is one row per
    (product, printing, CONDITION): Vilemaw is five export rows — Near Mint, Lightly Played,
    Moderately Played, Heavily Played and Damaged Foil — against ONE row here. So this can
    only ever speak for the Near Mint row.

    THAT IT IS THE NEAR MINT ROW IS AN INFERENCE THE PAYLOAD DOES NOT STATE, AND IT WAS
    MEASURED RATHER THAN ASSUMED. Across 387 multi-condition Unleashed products, this
    `market` is nearest the export's Near Mint row **338 times — 87%**. The 49 that land
    elsewhere are not counter-evidence: the median gap between the two closest condition rows
    there is **$0.04**, and 41 of the 49 are under $0.25, so "nearest" is measuring the drift
    between an older export snapshot and a live figure rather than telling two rows apart.
    Where the conditions are actually distinguishable, this tracks Near Mint.

    IT IS STILL AN INFERENCE, and a caller may not use it to price a Lightly Played copy. The
    measurement says the assumption is sound, not that the payload says so.

    IT SUPPLEMENTS THE EXPORT AND CAN NEVER REPLACE IT. There is no `TCGplayer Id` and no
    `Total Quantity` in this payload, which are the two columns D11's whole listing path is
    built on — the SKU the import matches by, and the live quantity D7's cap is measured
    against. Nothing here is a substitute for downloading an export.

    SO WHAT IT ACTUALLY BUYS IS RECENCY, NOT A NEW DIMENSION, and that is worth stating flatly
    because "supplements the export" reads like it adds one. Every figure below is already a
    column in an export the operator has; what this offers is the same figure as of now rather
    than as of the last download, per printing.

    THE FIELD SETS ARE NOT ONE-TO-ONE. `midPrice` and `highPrice` have no export column at
    all, and the export's `TCG Low Price With Shipping` has no field here — so this is three
    fields of five mapping onto three columns of four, not a mirror.

    D8 IS NOT REOPENED BY THIS AND THE LINE IS WORTH DRAWING HARD, because this is the closest
    anything in the repo comes to it. That entry names the export as the pricing source and no
    external pricing API. Nothing in this module computes a listing price, writes
    `TCG Marketplace Price`, or is reached by any command that emits a row — this is a
    READING, taken next to the export rather than instead of it. The day something wants a
    listed price to depend on a figure from this host, that is a change to D8 argued on its
    own terms, and this class does not make it quietly.
    """

    product_id: int
    printing: str
    low: Optional[Decimal]
    mid: Optional[Decimal]
    high: Optional[Decimal]
    market: Optional[Decimal]
    direct_low: Optional[Decimal]

    @classmethod
    def parse(cls, payload: Dict) -> Optional["PrintingPrice"]:
        try:
            product_id = int(payload["productId"])
        except (KeyError, TypeError, ValueError):
            return None
        return cls(
            product_id=product_id,
            printing=str(payload.get("subTypeName") or ""),
            low=_decimal(payload.get("lowPrice")),
            mid=_decimal(payload.get("midPrice")),
            high=_decimal(payload.get("highPrice")),
            market=_decimal(payload.get("marketPrice")),
            direct_low=_decimal(payload.get("directLowPrice")),
        )


def parse_prices(payload: Dict) -> Dict[Tuple[int, str], PrintingPrice]:
    """A `/prices` answer, keyed by (productId, printing).

    BOTH PARTS OF THE KEY, because one product carries up to two rows and they are different
    prices for different objects — Unleashed runs 293 `Foil` rows against 152 `Normal`. A
    productId-only key would silently keep whichever row came last.
    """
    rows = (PrintingPrice.parse(row) for row in (payload.get("results") or ()))
    return {(row.product_id, row.printing): row for row in rows if row is not None}


def extended(product: Dict, field: str) -> Optional[str]:
    """A named value out of a tcgcsv product's `extendedData` list, or None."""
    for entry in product.get("extendedData") or ():
        if entry.get("name") == field:
            value = entry.get("value")
            return None if value is None else str(value)
    return None


def index_by_name(rows: Iterable[Dict], key: str = "name") -> Dict[str, object]:
    """`{normalize_set(name): entry}` for a categories or groups payload.

    Folded through `join.normalize_set` for the reason that function already gives: two
    sources spell one label differently and neither is wrong. Measured, all 19 set names in
    the committed exports match their group name EXACTLY — so this fold is currently doing
    no work, and it is kept because the failure it prevents is a whole set resolving to
    nothing at once rather than one card.
    """
    return {join.normalize_set(str(row.get(key) or "")): row for row in rows}


# -------------------------------------------------------------------------- the network


def fetch_json(
    url: str, timeout: float = REQUEST_TIMEOUT_SECONDS, user_agent: str = USER_AGENT
) -> Dict:
    """GET a URL and parse JSON. THE ONLY IMPURE FUNCTION IN THIS MODULE.

    Everything above is a pure function of a payload and everything below takes this as an
    argument, so the harness reaches all of it with a committed fixture and never a socket.

    `user_agent` DEFAULTS TO THE HONEST STRING AND IS OTHERWISE PASSED IN, NEVER DISCOVERED
    — `Market`'s own rule for `cache_dir`, applied here for the reason `AGENT_ENV` above
    gives: this module may not read `.env`. A checkout with nothing configured sends exactly
    what it always sent.

    A NON-200 IS RAISED RATHER THAN RETURNED. `Unreachable` carries the status and the first
    of the body, because both hosts explain themselves in it — the endpoint answers HTTP 400
    with a validation message for a bad range, and tcgcsv answers 401 for a User-Agent it
    does not like, which is a refusal that reads as an authentication requirement and is not.
    A 403 IS `Blocked` INSTEAD, NEVER `Unreachable` — see that class for why the two must not
    share a name, and D216 for what is now answering it.
    """
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):  # a body we cannot read is not the interesting fault
            detail = exc.read().decode("utf-8", "replace")[:200]
        if exc.code == 403:
            # NEVER THE VALUE, ONLY THE NAME OF THE KNOB — D171's rule that a refusal must
            # name its remedy, and CLAUDE.md's rule that no message here ever carries the
            # user agent string itself.
            raise Blocked(
                f"{url} answered HTTP 403. That is either an authorization change at the "
                f"host or its own defenses declining this client by its request signature — "
                f"set {AGENT_ENV} in .env to the User-Agent your browser sends and try "
                f"again."
            ) from exc
        raise Unreachable(f"{url} answered HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise Unreachable(f"{url} could not be reached: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Unreachable(f"{url} did not answer JSON: {exc}") from exc


Fetcher = Callable[[str], Dict]


def history_url(product_id: int, range_: str) -> str:
    """The endpoint's URL, or refuse. Both arguments are checked before one is composed.

    The productId is coerced rather than interpolated, which is the half that is not about
    ranges: it is the only caller-supplied value that reaches a URL path, and an `int()` is
    both the type check and the guarantee that nothing a caller holds can be appended to a
    host we did not write.
    """
    if range_ not in RANGES:
        raise UnknownRange(
            f"{range_!r} is not a range this endpoint accepts; known: {', '.join(RANGES)}. "
            "Every other spelling answers HTTP 400 — `week`, `year`, `all` and `latest` were "
            "all probed and none of them is a range."
        )
    try:
        product = int(product_id)
    except (TypeError, ValueError) as exc:
        raise NotResolvable(f"{product_id!r} is not a productId") from exc
    return f"{HISTORY_HOST}/price/history/{product}/detailed?range={range_}"


class Market:
    """The walk from an export row to a reading, with the fetches cached on disk.

    THE CACHE DIRECTORY IS PASSED IN AND NEVER DISCOVERED. `pipeline/` imports nothing
    outside itself and the stdlib, so this module may not ask `store.files` where home is —
    the caller that knows about the store supplies a path, and the harness supplies a
    temporary one with no environment to set and nothing to restore.

    `cache_dir=None` caches in memory for the life of the object, which is what a one-shot
    caller wants and what the harness uses when it is asserting the walk rather than the
    disk.

    `user_agent` IS THE SAME STORY AS `cache_dir`, ONE PARAGRAPH LATER THAN IT WAS TRUE.
    This module cannot read `.env` (see `AGENT_ENV` above), so a caller that can — today
    `server/pipeline_routes.py`, the way it already resolves a cache directory — resolves
    the value and hands it in. It reaches `fetch_json` only when no `fetcher` is given; a
    caller supplying its own fetcher (every harness test) is supplying its own transport and
    this argument does nothing for it, which is the existing rule for `courtesy_delay` too.

    NOTHING WRITES INSIDE THE REPO TODAY AND THE FIRST CALLER HAS TO THINK ABOUT THAT. There
    is no caller, so there is no directory, so there is no `.gitignore` line — and the moment
    a command passes `files.home() / <something>` the derived cache lands in the checkout and
    needs one, with D47's rule attached: no trailing slash on a path a worktree can provision,
    because a pattern ending in `/` matches directories only and a symlink is not one.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        fetcher: Optional[Fetcher] = None,
        courtesy_delay: float = COURTESY_DELAY_SECONDS,
        now: Callable[[], float] = time.time,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._fetch = fetcher if fetcher is not None else (
            lambda url: fetch_json(url, user_agent=user_agent)
        )
        self._courtesy_delay = courtesy_delay
        self._now = now
        self._memory: Dict[str, Tuple[float, Dict]] = {}
        self._indexes: Dict[Tuple[int, int], ProductIndex] = {}
        self.requests = 0

    # ------------------------------------------------------------------------ caching

    def _cache_path(self, slug: str) -> Optional[Path]:
        return None if self.cache_dir is None else self.cache_dir / f"{slug}.json"

    def _cached(self, slug: str, ttl: float) -> Optional[Dict]:
        entry = self._memory.get(slug)
        if entry is None and self.cache_dir is not None:
            path = self._cache_path(slug)
            if path is not None and path.exists():
                try:
                    stored = json.loads(path.read_text("utf-8"))
                    entry = (float(stored["fetched_at"]), stored["payload"])
                except (OSError, ValueError, KeyError, TypeError):
                    # A CORRUPT CACHE ENTRY IS A CACHE MISS, NEVER A REFUSAL. This directory
                    # is derived and deletable by construction, so the only honest response
                    # to bytes we cannot read is to go and ask again.
                    entry = None
        if entry is None:
            return None
        fetched_at, payload = entry
        if self._now() - fetched_at > ttl:
            return None
        self._memory[slug] = entry
        return payload

    def _store(self, slug: str, payload: Dict) -> None:
        entry = (self._now(), payload)
        self._memory[slug] = entry
        path = self._cache_path(slug)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Same-directory temporary plus `os.replace` is `store/files.py`'s rule and it is
            # borrowed rather than reinvented: a reader must never see a half-written file.
            # Not imported from there, because `pipeline/` may not depend on `store/`.
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"fetched_at": entry[0], "payload": payload}), "utf-8"
            )
            temporary.replace(path)
        except OSError:
            # A cache that cannot be written is slower, not wrong.
            pass

    def get(self, url: str, slug: str, ttl: float) -> Dict:
        payload = self._cached(slug, ttl)
        if payload is not None:
            return payload
        if self.requests and self._courtesy_delay:
            time.sleep(self._courtesy_delay)
        self.requests += 1
        payload = self._fetch(url)
        self._store(slug, payload)
        return payload

    # -------------------------------------------------------------------- the catalog

    def categories(self) -> Dict[str, object]:
        payload = self.get(
            f"{CATALOG_HOST}/tcgplayer/categories", "tcgcsv/categories", CATALOG_TTL_SECONDS
        )
        return index_by_name(payload.get("results") or ())

    def category_id(self, product_line: str) -> int:
        """tcgcsv's categoryId for a `Product Line` cell, by NAME. See the header."""
        row = self.categories().get(join.normalize_set(product_line))
        if row is None:
            raise NotResolvable(
                f"no tcgcsv category is named {product_line!r}. That cell is what "
                "`pipeline/games.py` authors per game and D22 audits against the committed "
                "exports, so a miss here means either the registry or the upstream catalog "
                "renamed a product line — check the export's own `Product Line` column first."
            )
        return int(row["categoryId"])  # type: ignore[index]

    def groups(self, category_id: int) -> Dict[str, object]:
        payload = self.get(
            f"{CATALOG_HOST}/tcgplayer/{int(category_id)}/groups",
            f"tcgcsv/{int(category_id)}/groups",
            CATALOG_TTL_SECONDS,
        )
        return index_by_name(payload.get("results") or ())

    def group_id(self, category_id: int, set_name: str) -> int:
        row = self.groups(category_id).get(join.normalize_set(set_name))
        if row is None:
            raise NotResolvable(
                f"no tcgcsv group in category {category_id} is named {set_name!r}. All 19 "
                "set names in the committed exports matched exactly, so this is a set the "
                "mirror has not published rather than a spelling to fold harder."
            )
        return int(row["groupId"])  # type: ignore[index]

    def products(self, category_id: int, group_id: int) -> ProductIndex:
        key = (int(category_id), int(group_id))
        if key not in self._indexes:
            payload = self.get(
                f"{CATALOG_HOST}/tcgplayer/{key[0]}/{key[1]}/products",
                f"tcgcsv/{key[0]}/{key[1]}/products",
                CATALOG_TTL_SECONDS,
            )
            self._indexes[key] = ProductIndex.build(payload.get("results") or ())
        return self._indexes[key]

    def prices(self, category_id: int, group_id: int) -> Dict[Tuple[int, str], PrintingPrice]:
        """Current prices for a whole group, keyed by (productId, printing).

        WHOLE-GROUP AND NOT PER-CARD, because that is the only shape the host offers: there is
        no per-product price route, so one request answers 321 products and asking about a
        second card in the same set is free. `PRICE_TTL_SECONDS` IS ITS OWN CONSTANT, NEVER
        `CATALOG_TTL_SECONDS`, even though the two used to be one value — a group's PRODUCTS
        are fixed once pulled (the owner's own ruling), but its PRICES move daily, and giving
        this call the catalogue's now-infinite lifetime would silently make a daily price
        permanent. A caller that needs today's figure passes a shorter `ttl` rather than this
        module guessing which reading it is for.

        There is deliberately no `prices_for_row` twin of `product_id_for_row`. A per-row
        accessor would read as SKU-level, which this is not (see `PrintingPrice`), and the
        caller that wants one card's figure already holds the productId and the printing.
        """
        payload = self.get(
            f"{CATALOG_HOST}/tcgplayer/{int(category_id)}/{int(group_id)}/prices",
            f"tcgcsv/{int(category_id)}/{int(group_id)}/prices",
            PRICE_TTL_SECONDS,
        )
        return parse_prices(payload)

    def product_id_for_row(self, row: tcgcsv.Row) -> int:
        """An export row -> a productId. Three named hops, each refusing on its own.

        Takes the ROW rather than a game key, because every value it needs is a cell the
        export already carries and the row is what a caller holds. `pipeline/games.py` is
        consulted by the caller when it wants to know whether the game is catalogued at all;
        an uncatalogued `misc` card has no `Product Line` to look up and refuses here on the
        first hop, saying so.

        THIS IS NOT THE ONLY WAY A PRODUCT IS RESOLVED (D254). A
        caller that already knows the productId — the archive's own already-verified answer
        for this SKU, `store/pricearchive.py:Bucket.product_id` — never calls this at all;
        `reading_for_row`/`readings_for_rows` below take that id directly and skip this
        whole walk. This function is what runs when neither the archive nor the caller has
        an answer in hand, over whatever `(number, name)` the row carries. The caller
        decides which row that is (`pipeline/pricearchive.py:merged_export_rows_by_sku`
        prefers the SKU's own export row over a card's stored fields); this function has no
        opinion about where the row came from.
        """
        category_id = self.category_id(row.get(tcgcsv.PRODUCT_LINE_COLUMN, ""))
        group_id = self.group_id(category_id, row.get(tcgcsv.SET_COLUMN, ""))
        product_id = self.products(category_id, group_id).find(
            row.get(tcgcsv.NUMBER_COLUMN, ""), row.get(tcgcsv.NAME_COLUMN, "")
        )
        if product_id is None:
            raise NotResolvable(
                "no single tcgcsv product matches "
                f"{row.get(tcgcsv.NAME_COLUMN, '')!r} "
                f"{row.get(tcgcsv.NUMBER_COLUMN, '')!r} in "
                f"{row.get(tcgcsv.SET_COLUMN, '')!r}. Either the mirror does not carry it or "
                "two products share the number and the name could not tell them apart — this "
                "refuses rather than picking one."
            )
        return product_id

    # -------------------------------------------------------------------- the history

    def history(self, product_id: int, range_: str) -> Dict[str, Series]:
        url = history_url(product_id, range_)
        payload = self.get(
            url, f"history/{int(product_id)}-{range_}", HISTORY_TTL_SECONDS
        )
        return parse_history(payload, int(product_id), range_)

    def reading_for_row(
        self,
        row: tcgcsv.Row,
        ranges: Sequence[str] = DEFAULT_RANGES,
        *,
        product_id: Optional[int] = None,
    ) -> Reading:
        """An export row -> everything this module can say about that SKU.

        The row's OWN `TCGplayer Id` is what is picked out of each response. That is the
        exact hop the header calls out: we ask about a product and take our own SKU out of
        the answer by its number, so no variant or condition string is ever matched.

        `product_id`, WHEN GIVEN, SKIPS `product_id_for_row` ENTIRELY
        (D254). A caller that already knows the answer — the
        archive's own already-verified productId for this SKU — passes it straight through;
        `row` is then read only for its SKU, never its name or number. Trusted as given: this
        function does not re-verify a productId it was handed.
        """
        sku = str(row.get(tcgcsv.SKU_COLUMN, "")).strip()
        if not sku:
            raise NotResolvable(
                f"the row carries no {tcgcsv.SKU_COLUMN!r}, so there is nothing to pick out "
                "of a product's answer."
            )
        resolved_id = int(product_id) if product_id else self.product_id_for_row(row)
        series: Dict[str, Series] = {}
        for range_ in ranges:
            found = self.history(resolved_id, range_).get(sku)
            if found is not None:
                series[range_] = found
        return Reading(sku=sku, product_id=resolved_id, series=series)

    def readings_for_rows(
        self,
        rows: Iterable[tcgcsv.Row],
        ranges: Sequence[str] = DEFAULT_RANGES,
        *,
        product_ids: Optional[Mapping[str, int]] = None,
    ) -> Tuple[Dict[str, Reading], Dict[str, str]]:
        """Many rows at once. Answers `(readings_by_sku, refusals_by_sku)`.

        BOTH DIRECTIONS, WHICH IS `CLAUDE.md`'s HARD RULE AND NOT A CONVENIENCE. A row this
        cannot resolve is named with the reason it could not be, never dropped — the same
        promise `JoinReport` makes about a card that finds no catalog row, applied to a
        reader that will one day be feeding a screen.

        One product's response carries every condition of that card, so rows are grouped by
        productId before anything is fetched and a card held in four conditions costs one
        request per range rather than four.

        `product_ids`, SKU -> A KNOWN PRODUCTID, SKIPS `product_id_for_row` FOR THOSE SKUS
        (D254). The caller's own already-verified answers —
        typically `store/pricearchive.py:Bucket.product_id` from a prior sweep — win over a
        fresh catalogue walk for any SKU named here; every other row still resolves through
        `product_id_for_row` exactly as before.
        """
        readings: Dict[str, Reading] = {}
        refusals: Dict[str, str] = {}
        by_product: Dict[int, List[str]] = {}
        known = product_ids or {}
        for row in rows:
            sku = str(row.get(tcgcsv.SKU_COLUMN, "")).strip()
            if not sku:
                continue
            verified = known.get(sku)
            if verified:
                by_product.setdefault(int(verified), []).append(sku)
                continue
            try:
                by_product.setdefault(self.product_id_for_row(row), []).append(sku)
            except PriceHistoryError as exc:
                refusals[sku] = str(exc)
        for product_id, skus in by_product.items():
            per_range: Dict[str, Dict[str, Series]] = {}
            for range_ in ranges:
                try:
                    per_range[range_] = self.history(product_id, range_)
                except PriceHistoryError as exc:
                    for sku in skus:
                        refusals.setdefault(sku, str(exc))
            for sku in skus:
                series: Dict[str, Series] = {}
                for range_, answers in per_range.items():
                    found = answers.get(sku)
                    if found is not None:
                        series[range_] = found
                readings[sku] = Reading(sku=sku, product_id=product_id, series=series)
        return readings, refusals


def catalogued_row(row: tcgcsv.Row) -> bool:
    """Is this row's product line one a registered, catalogued game names?

    The predicate a caller should branch on before reaching for a reading, and it is
    `games.is_catalogued` read from the export's side: `misc` carries `product_line: None`
    by construction (D22), so a misc card has no cell to look a category up by and there is
    no history to fetch for it. Checking here rather than raising inside the walk keeps the
    refusal where the caller can act on it.
    """
    line = str(row.get(tcgcsv.PRODUCT_LINE_COLUMN, "") or "").strip()
    if not line:
        return False
    folded = join.normalize_set(line)
    return any(
        join.normalize_set(str(entry["product_line"])) == folded
        for entry in games.GAMES
        if entry["catalogued"] and entry["product_line"]
    )
