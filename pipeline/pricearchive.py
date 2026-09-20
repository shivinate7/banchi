"""The sweep `pkmnscan archive sweep` runs: read `pipeline/pricehistory.py`'s live endpoint
for every name the owner has sold or holds, and hand what came back to `store/pricearchive.py`
(D219).

TWO STEPS, KEPT APART SO THE FIRST NEEDS NO NETWORK. `rows_from_store` reads the store alone
and answers "which SKUs is this pass over, and what does the export-shaped row for each one
look like" — pure, and the whole thing a test can exercise with a throwaway store and no
`Market`. `sweep` takes those rows and a `Market` (or anything shaped like one — see below)
and does the one thing this module exists to do: ask the live endpoint for every range, and
turn what it hands back into `store/pricearchive.py:Bucket` rows keyed the way that module
argues they must be.

THE SUBJECT IS EVERY DISTINCT SKU THE `cards` TABLE NAMES. A card keeps its `sku` for as
long as it exists in the store, sold or not — D26/D134 retire a box and reclaim a sold card's
photograph, but the record and its SKU stay (`store/master.py:STATES` includes `sold` as a
state a card carries, never a deletion) — so "every name the owner has sold or holds" is
exactly "every distinct, non-empty `sku` this table has ever recorded a card against." A
card's own most recent row supplies the `Product Name`, `Number`, `Set Name`, `Condition` and
`game` an export-shaped row needs to be resolved against the catalog the same way
`pipeline/pricehistory.py:Market.product_id_for_row` already resolves a real export row —
this module invents no second resolution path.

`Market.readings_for_rows` TAKES `pipeline/tcgcsv.Row`-SHAPED DICTS, WHICH IS WHAT
`_export_row` BUILDS. A `tcgcsv.Row` is a plain dict keyed by the export's own column names
(`pipeline/tcgcsv.py:SKU_COLUMN` etc.), and every one of those columns is a fact the `cards`
table already carries per card — `Product Line` alone has no column of its own and is derived
from `pipeline/games.py:get(card.game)["product_line"]`, the same table `join.py` already
reads for every other purpose.

NEITHER FUNCTION IMPORTS `pipeline/pricehistory.py:Market` BY NAME IN ITS SIGNATURE. `sweep`
duck-types on `.readings_for_rows(rows, ranges=...)`, which is exactly `Market`'s own method
— this is so a test can hand it a stand-in with no network underneath, per `CLAUDE.md`'s "no
network call in a test" rule, without this module importing anything from `unittest.mock`.

--------------------------------------------------------------------------------------
FOUR THINGS `cli/cmd_pricearchive.py` LAYERS ON TOP OF `sweep`, ALL IN THIS FILE AS PURE,
TESTABLE FUNCTIONS SO THE CLI ITSELF STAYS A THIN DRIVER (D223,
D222):

  1. RANKED SUBJECTS. `rows_from_store` orders its answer by what the ledger says that SKU
     has actually earned, sold value first (`revenue_by_sku`, `rank_by_revenue`) — a pass
     that gets cut off partway should have spent its requests on what matters, not on
     whatever order `cards.select` happened to return.
  2. RESUME WITHOUT RE-FETCHING. `freshness_index` and `split_by_freshness` read the
     archive itself (never a second, ephemeral cache) to decide which SKUs this pass can
     skip because they were already read recently enough to trust.
  3. COMMIT-SIZED CHUNKS. `chunk_rows` splits an already-ranked subject dict into pieces a
     caller commits one at a time, so an interrupt loses at most one chunk's reads, never
     the whole pass — and it never re-sorts, because re-sorting here would silently undo
     the ranking `rows_from_store` already chose.
  4. A THROTTLE THAT KNOWS ITS OWN NAME. `classify_refusals` rewrites a 403 that follows
     earlier success in the same pass into what it actually is — the host's own rate limit,
     not `pipeline/pricehistory.py:Blocked`'s authorization message, which this pass has
     already disproved by the time it fires. `measured_pace` turns a real, measured count
     of requests-before-block into the next pace, never a guessed number; `load_pace` and
     `save_pace` carry that measurement from one press to the next.
"""

from __future__ import annotations

import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

from pipeline import games, join, tcgcsv
from store.pricearchive import RANGE_WIDTH_DAYS, Bucket, Source, _key
from store.session import Store

# How many subject SKUs one `sweep()` call and one Store commit cover — chosen so an
# interrupt between two commits loses at most this many SKUs' worth of reads, never the
# whole pass (D222). Not tuned to network throughput; `measured_pace`
# below is what answers "how fast", this only answers "how much unwritten work at once".
CHUNK_SKUS = 20

# How long a SKU's own buckets are trusted fresh enough that a RESUMED SWEEP skips it
# (D230), NEVER `pipeline/pricehistory.py:HISTORY_TTL_SECONDS` — that
# constant is one hour, argued for a different reader with a different need (the live
# `#/pricing` screen, where an hour-old figure is honest and a longer one would not be).
# `split_by_freshness` treats this pass the same way whether it is resumed a minute later
# or five hours later, and D222 measures the host throttling this client after roughly
# 800 requests — with `rank_by_revenue` now stable and deterministic (D223), a one-hour
# window sends every pass back to read the SAME top ~200 names it already read last time,
# never advancing past them. MEASURED AGAINST THE OWNER'S REAL STORE: two passes five
# hours apart, the second skipped nothing and restarted from the top of the ranked list —
# it only ever advanced by the accident of running before ranking existed. Six days is
# the owner's own ruling: a weekly press refreshes the whole archive, and any pass run
# again within the same week always advances onto ground the last one had not covered.
RESUME_TTL_SECONDS = 6 * 24 * 60 * 60

# `pipeline/pricehistory.py:COURTESY_DELAY_SECONDS`, copied rather than imported — this
# module still takes no hard dependency on `pricehistory` (the `market` argument stays
# duck-typed throughout), so the naive first guess has to live here too, for a checkout
# that has never measured a real throttle yet.
DEFAULT_COURTESY_DELAY_SECONDS = 0.15

# How much slower than the rate that just got a session blocked the next attempt goes.
# ARGUED, NOT PROVEN OPTIMAL (D222): doubling the interval a run
# demonstrably survived only PART of is a conservative first correction, not a claim about
# the host's real limit — which this module has no way to learn except by trying and is
# never going to get from a constant somebody typed.
THROTTLE_BACKOFF_FACTOR = 2.0

# The one sentence `pipeline/pricehistory.py:fetch_json` raises `Blocked` with for an HTTP
# 403 (see its own docstring). Matched by substring rather than by exception type, because
# `readings_for_rows` already folds `Blocked` into a plain string per SKU before this
# module ever sees it (see the header above) — this file may not change
# `pipeline/pricehistory.py`'s exceptions, and a fixed substring of an already-fixed
# sentence is a fact this module can rely on without a second, drifting copy of it.
BLOCKED_SIGNATURE = "answered HTTP 403"

# `app/src/Revenue.tsx:isCanceled`'s own rule, read here rather than a second copy of the
# feed: trimmed and case-folded, because the vocabulary is the marketplace's and "Canceled"
# and "canceled " are one fact about an order to a person, exactly `store/orders.py`'s own
# `TERMINAL_STATUSES` comparison one register over.
CANCELED_STATUS = "canceled"


class _MarketLike(Protocol):
    def readings_for_rows(
        self, rows: Iterable[dict], ranges: Tuple[str, ...] = ()
    ) -> Tuple[Dict[str, object], Dict[str, str]]:
        ...


def _export_row(
    sku: str, name: str, number: str, set_name: str, condition: str, game: str,
    number_key: str = "",
) -> dict:
    """One card's own last-known facts, shaped exactly like a real export row.

    `game` IS RESOLVED THROUGH `pipeline/games.py`, NEVER STORED AS `Product Line` DIRECTLY —
    `cards.game` is the operator's claim (`pokemon`, `misc`, ...), and the catalogue walk
    wants the human-facing product line string that claim maps to. A card whose claim is
    empty falls back through `games.DEFAULT_GAME` the same way every other reader in this
    repo backfills an unset `game` (`store/master.py:Card.game`'s own docstring).

    THE NUMBER CELL PREFERS THE STORE'S OWN `number_key` OVER THE BARE `number`
    (D234), AND THE PRIMITIVE ALREADY EXISTED — it was never
    called from here. `cards.number` is stored bare by design (measured: 542 of 542
    Pokemon cards with a SKU carry a number with no `/` in it), but `store/master.py`'s
    own write path (`_card_columns`, store-scaling item 8) already composes and STORES
    `join_key(card.number, card.printed_total)` as `number_key` on every write, for the
    FTS5 search index to read without re-deriving the rule. A real TCGplayer export's own
    `Number` cell carries exactly that composed `zfill(3)(number) + "/" + printedTotal`
    form, which is what `pipeline/pricehistory.py:ProductIndex` and
    `pipeline/join.py:Catalog` are both keyed from. A synthetic row built from the bare
    `number` alone is missing the one column the number index can match on, so it can
    only ever be found by NAME — and the name rung refuses on any card whose name is
    ambiguous (`ME01: Mega Evolution`'s secret rares above its own printed total:
    `Bulbasaur - 001/132` AND `Bulbasaur - 133/132` both fold to `BULBASAUR`).

    `number_key` IS EMPTY BY DESIGN FOR A GAME WITH NO DENOMINATOR (`store/master.py`'s
    own guard: `if (card.number and card.printed_total) else ""`) — Riftbound and One
    Piece print their identifier as ONE string with no `printed_total` to compose, so
    `number_key` is always `""` for them and this falls back to the bare `number`
    unchanged, which already matches the export's `Number` cell verbatim for those games.
    No `pipeline/games.py` lookup is needed here: the store already decided, per card, at
    write time.
    """
    registry = games.get(game or games.DEFAULT_GAME)
    line = registry.get("product_line")
    return {
        tcgcsv.PRODUCT_LINE_COLUMN: line if line is not None else "",
        tcgcsv.SET_COLUMN: set_name or "",
        tcgcsv.NUMBER_COLUMN: number_key or number or "",
        tcgcsv.NAME_COLUMN: name or "",
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.CONDITION_COLUMN: condition or "",
    }


class UnresolvedLedgerName(ValueError):
    """One order line's own `name` could not be parsed into an export-shaped row. Carries
    the reason as its message. Never raised past `ledger_subject_rows`, which turns every
    instance into a per-SKU refusal — `CLAUDE.md`'s both-directions rule applies to a
    ledger-only subject exactly as it does to a live fetch."""


def _longest_group_prefix(remainder: str, groups: Dict[str, dict]) -> Optional[Tuple[str, str]]:
    """The longest prefix of `remainder` that, followed by `": "`, names a real group in
    `groups` (`pipeline/pricehistory.py:Market.groups`'s own return shape — keyed by
    `join.normalize_set`) — never the first `": "`, because a group name itself carries a
    colon (`SV09: Journey Together`) and a first-split reads `SV09` alone, which resolves
    to nothing. `": "` occurrences only move forward through `remainder`, so walking them in
    order and keeping the last match found IS keeping the longest one.

    Answers `(the group's own catalog spelling, everything after "<group>: ")`, or `None`
    when no prefix of `remainder` names a known group at all.
    """
    best: Optional[Tuple[str, str]] = None
    start = 0
    while True:
        pos = remainder.find(": ", start)
        if pos == -1:
            break
        candidate = remainder[:pos]
        record = groups.get(join.normalize_set(candidate))
        if record is not None:
            real_name = str(record.get("name") or candidate).strip()
            best = (real_name, remainder[pos + 2:])
        start = pos + 1
    return best


def _split_ledger_tail(rest: str) -> Optional[Tuple[str, str, str]]:
    """`(Product Name, Number, Condition)` out of `"<Product Name>[ - #<Number>] -
    <Condition>"` — the shape left over once the product line and the group have both been
    read off the front. The condition is always the final `" - "`-delimited segment. The
    segment before it is the Number only when it is `"#"`-prefixed — a sealed line carries
    no such segment at all, which is a correct, expected shape and not a refusal (see
    `pipeline/pricehistory.py:ProductIndex`'s own docstring on a blank Number)."""
    parts = rest.split(" - ")
    if len(parts) < 2:
        return None
    condition = parts[-1].strip()
    if not condition:
        return None
    if len(parts) >= 3 and parts[-2].strip().startswith("#"):
        number = parts[-2].strip()[1:].strip()
        product_name = " - ".join(parts[:-2]).strip()
    else:
        number = ""
        product_name = " - ".join(parts[:-1]).strip()
    if not product_name:
        return None
    return product_name, number, condition


def parse_ledger_name(name: str, groups: Dict[str, dict]) -> dict:
    """One order line's own `name` -> an export-shaped row (the `TCGplayer Id` cell is left
    blank; the caller carries the SKU already), by the grammar `<Product Line> - <Group
    Name>: <Product Name>[ - #<Number>] - <Condition>`.

    A PURE FUNCTION. `groups` is `Market.groups(category_id)`'s own return shape for
    whichever category the product line resolves to — a test hands this a plain dict, no
    `Market`, no store, no network. `ledger_subject_rows` below is what actually calls
    `Market.category_id`/`Market.groups`; this function only ever reads the dict it is
    handed.

    THIS FUNCTION DOES NOT GATE THE PRODUCT LINE AGAINST `pipeline/games.py` (fixed
    2026-09-20, D231 amended). `games.py` answers "which games can this repo photograph,
    join and list" (D21, D22) — a question about THIS repo's own capture and listing
    coverage. It is the wrong authority for "does the mirror this archive reads carry a
    price history for this product line", which is the only thing this function needs.
    The caller (`ledger_subject_rows`) already asks the RIGHT authority —
    `Market.category_id`, the mirror's own category list — before it ever calls this
    function with a `groups` answer, so by the time `groups` is non-empty the product line
    is already proven to be one the mirror carries. Do not re-add a `games.py` check here:
    the fix this replaced refused three real, resolvable mirror categories (YuGiOh, Card
    Sleeves, Playmats) worth $1,094.41 of the owner's own sold history, precisely because
    it asked `games.py` a question it does not answer. Adding a game to `games.py` to
    "fix" a future refusal here would be a much larger, wrong move — it would claim this
    repo can capture and list that game, which D21/D22 govern and which this archive-only
    change does not attempt (see the deferral D231 now records).

    REFUSES RATHER THAN GUESSES, PER `CLAUDE.md`. Both remaining hops — the group boundary
    and the tail split — raise `UnresolvedLedgerName` naming itself when they cannot
    resolve, rather than falling back to a partial match.
    """
    text = str(name or "").strip()
    if not text:
        raise UnresolvedLedgerName("the line carries no name at all")
    if " - " not in text:
        raise UnresolvedLedgerName(
            f"{text!r} has no ' - ' separator marking where the product line ends"
        )
    line, _, remainder = text.partition(" - ")
    line = line.strip()
    match = _longest_group_prefix(remainder, groups)
    if match is None:
        raise UnresolvedLedgerName(
            f"no group tcgcsv lists for {line!r} prefixes {remainder!r} — either the "
            "mirror does not carry that set or this name is not shaped like a real export"
        )
    set_name, rest = match
    tail = _split_ledger_tail(rest)
    if tail is None:
        raise UnresolvedLedgerName(
            f"{rest!r} does not carry both a product name and a condition"
        )
    product_name, number, condition = tail
    return {
        tcgcsv.PRODUCT_LINE_COLUMN: line,
        tcgcsv.SET_COLUMN: set_name,
        tcgcsv.NUMBER_COLUMN: number,
        tcgcsv.NAME_COLUMN: product_name,
        tcgcsv.SKU_COLUMN: "",
        tcgcsv.CONDITION_COLUMN: condition,
    }


def _ledger_export_rows(
    ledger, skus: Iterable[str], market: _MarketLike
) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """The shared machinery behind `ledger_subject_rows` and the
    `D233` card-row fallback: for EXACTLY the SKUs named in `skus`
    (no exclusion of any kind — that is the caller's job), find the order line that priced
    each one, parse its `name` into an export-shaped row, and answer `(rows, refusals)`.

    BOTH DIRECTIONS, PER `CLAUDE.md`. `refusals` names, by SKU, every one of `skus` that
    could not be resolved and why — no name, a name that does not fit the grammar, or a
    product line/group the catalog mirror does not carry. Never dropped, never resolved on
    a partial match.

    ONE `Market.groups` CALL PER DISTINCT PRODUCT LINE SEEN, NEVER PER SKU — `Market.groups`
    is already a cached, whole-category read; asking it once per line and reusing the
    answer for every SKU under that line is the same discipline `products()`/`prices()`
    already apply to a category, not a second cache this module invents.
    """
    wanted = set(str(sku).strip() for sku in skus if str(sku or "").strip())
    candidates: Dict[str, str] = {}
    for order in getattr(ledger, "orders", {}).values():
        for line_item in getattr(order, "lines", ()) or ():
            sku = str(getattr(line_item, "sku", "") or "").strip()
            if not sku or sku not in wanted or sku in candidates:
                continue
            candidates[sku] = str(getattr(line_item, "name", "") or "").strip()

    rows: Dict[str, dict] = {}
    refusals: Dict[str, str] = {}
    groups_by_line: Dict[str, Optional[Dict[str, dict]]] = {}

    for sku, name in candidates.items():
        if not name:
            refusals[sku] = "the ledger line carries no name to parse"
            continue
        if " - " not in name:
            refusals[sku] = (
                f"{name!r} has no ' - ' separator marking where the product line ends"
            )
            continue
        product_line = name.split(" - ", 1)[0].strip()
        if product_line not in groups_by_line:
            try:
                category_id = market.category_id(product_line)
                groups_by_line[product_line] = market.groups(category_id)
            except Exception as exc:  # the mirror's own refusal shape, duck-typed (see
                # the header — this module takes no hard dependency on
                # `pipeline/pricehistory.py`'s exception types)
                groups_by_line[product_line] = None
                _ = exc
        groups = groups_by_line[product_line]
        if groups is None:
            refusals[sku] = (
                f"{product_line!r} could not be resolved against the tcgcsv category list"
            )
            continue
        try:
            row = parse_ledger_name(name, groups)
        except UnresolvedLedgerName as exc:
            refusals[sku] = str(exc)
            continue
        row[tcgcsv.SKU_COLUMN] = sku
        rows[sku] = row

    return rows, refusals


def ledger_subject_rows(
    ledger, known_skus: Iterable[str], market: _MarketLike
) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Every SKU the order ledger ever priced a line for, that `known_skus` (the `cards`
    table's own subject set) cannot already answer for, resolved into an export-shaped row
    by parsing the line's own `name` — this is the sealed-product widening D223
    names as a gap and D231 closes: sealed product has no
    `cards` row and never will, but the ledger's own `name` carries every cell an
    export-shaped row needs.

    CARDS STILL WINS, BY CONSTRUCTION. This function is never asked about a SKU
    `known_skus` already covers — `rows_from_store` only calls it with the remainder — so
    there is no row here for it to lose a conflict against.

    THIN WRAPPER OVER `_ledger_export_rows`. That function does the actual parsing; this
    one only computes which SKUs are still open — every SKU the ledger ever priced, minus
    `known_skus` — and hands that set down. `rows_from_store`'s own card-row fallback
    (`D233`) calls `_ledger_export_rows` directly, over the
    OPPOSITE set — SKUs `known_skus` already covers — because it wants a fallback row for a
    SKU that has both, not a wider subject set.
    """
    known = set(str(sku).strip() for sku in known_skus)
    all_ledger_skus = {
        str(getattr(line_item, "sku", "") or "").strip()
        for order in getattr(ledger, "orders", {}).values()
        for line_item in getattr(order, "lines", ()) or ()
    }
    wanted = {sku for sku in all_ledger_skus if sku and sku not in known}
    return _ledger_export_rows(ledger, wanted, market)


def revenue_by_sku(ledger) -> Dict[str, Decimal]:
    """Gross revenue per SKU, canceled orders excluded — `app/src/Revenue.tsx`'s own rule
    (D214), read off the ledger directly rather than a second copy of it: `unit_price *
    quantity`, summed over every line of every order whose own `status` is not
    `CANCELED_STATUS` once trimmed and case-folded.

    THIS IS THE ONLY THING A SEALED-PRODUCT SKU IS EVER WORTH TO THIS MODULE. Sealed
    product is never captured (`pipeline/games.py`'s own line for it) and so has no row in
    `cards` and never will — `store/orders.py:982` says the same of a sealed Holiday
    Calendar's fulfilment record. A sealed SKU's revenue is computed here anyway, because
    `rank_by_revenue` is handed EVERY key this function can answer for, not only the ones
    `rows_from_store`'s own subject set happens to contain — the gap between the two is
    exactly the reachability limit D223 argues
    about and does not solve.

    A LINE WITH NO READABLE `unit_price` CONTRIBUTES NOTHING AND IS NEVER AN ERROR — D9's
    reading of a blank market cell, applied to a feed cell this module does not own and
    cannot demand a shape from.
    """
    totals: Dict[str, Decimal] = {}
    for order in ledger.orders.values():
        status = str(getattr(order, "status", "") or "").strip().casefold()
        if status == CANCELED_STATUS:
            continue
        for line in getattr(order, "lines", ()) or ():
            sku = str(getattr(line, "sku", "") or "").strip()
            if not sku:
                continue
            try:
                price = Decimal(str(line.unit_price))
            except (InvalidOperation, ValueError, TypeError):
                continue
            quantity = max(0, int(getattr(line, "quantity", 0) or 0))
            if quantity == 0:
                continue
            totals[sku] = totals.get(sku, Decimal(0)) + price * quantity
    return totals


def rank_by_revenue(skus: Iterable[str], revenue: Dict[str, Decimal]) -> List[str]:
    """Every SKU in `skus`, sold value first (D223).

    A pass that gets cut off partway — D222's whole subject, and the
    NORMAL case measured 2026-09-19, not the exception — should have spent its requests on
    what the owner has actually sold, never on whatever order `cards.select` returned. A
    SKU this ledger never sold reads as zero and sorts last, among itself in SKU order —
    stable and cheap to reproduce, which is what lets `chunk_rows` and the resume logic
    both mean the same thing by "the Nth chunk" across two runs over an unchanged store.
    """
    return sorted(skus, key=lambda sku: (-(revenue.get(sku) or Decimal(0)), sku))


def rows_from_store(
    snapshot=None,
    market: Optional[_MarketLike] = None,
    refusals: Optional[Dict[str, str]] = None,
    fallback_rows: Optional[Dict[str, dict]] = None,
) -> Dict[str, dict]:
    """`sku -> export-shaped row`, one per distinct SKU this store can price a subject for,
    ORDERED BY WHAT THAT SKU HAS ACTUALLY SOLD FOR
    (`rank_by_revenue`, D223) — a plain `dict` preserves the order it
    is built in, so a caller that chunks or iterates this in order walks the highest-value
    subjects first with no second sort.

    `fallback_rows`, WHEN GIVEN AND `market` IS ALSO GIVEN, IS FILLED WITH A SECOND,
    LEDGER-DERIVED ROW FOR EVERY CARD-COVERED SKU THE LEDGER CAN ALSO ANSWER FOR
    (`D233`). `cards` still wins as the PRIMARY row for the return
    value below — that is unchanged. This is a candidate the CALLER (`sweep`) may retry
    with, and only when the primary card-derived row fails to resolve against the mirror.
    Built the same way `ledger_subject_rows` builds the ledger's second SOURCE (its own
    subject-widening use, over the opposite SKU set), by the same `_ledger_export_rows`
    machinery — a SKU with no ledger line at all simply has no entry here, silently, since
    "no fallback exists" is not itself a refusal of anything this function was asked for.

    THE SUBJECT SET IS TWO SOURCES, `cards` FIRST. A FULL-TABLE `select`, NOT `.values()` —
    `select` hands back only the six columns this needs as plain tuples, never a `Card`
    object per row (`store-scaling` item 2's own complaint about a table-wide walk, avoided
    the same way `cli/cmd_reprice.py` and `cli/resolve.py` already avoid it elsewhere in
    this package). The LAST row this loop sees for a SKU wins — `cards.select` has no
    declared order, so a SKU captured under two slightly different set-hint spellings over
    its lifetime resolves to whichever row this process happened to read last; that is a
    pre-existing ambiguity in what "the" name for a SKU is, not one this module introduces,
    and it costs nothing worse than a possibly-stale `Number`/`Set Name` pair that
    `Market.product_id_for_row` will refuse on its own if the two together no longer
    resolve.

    SEALED PRODUCT IS THE SECOND SOURCE, WHEN `market` IS GIVEN — the gap D223 named and
    left unsolved. A SKU that sold but has no `cards` row is resolved from the order
    ledger's own `name` (`ledger_subject_rows`, over `parse_ledger_name`). `market` is
    `None` by default: a caller with no `Market` in hand (this module's own tests, or a
    caller that only wants the `cards`-covered subjects) gets exactly D219's original
    behaviour, no wider and no narrower. `cards` ALWAYS WINS where both sources answer for
    the same SKU — `ledger_subject_rows` is never even asked about a SKU this loop has
    already put a row against, so there is no later merge to get backwards.
    `refusals`, when given, is filled in place with every ledger SKU this pass could not
    resolve and why — `CLAUDE.md`'s both-directions rule, carried past this function's own
    return shape rather than dropped at the boundary.
    """
    snapshot = snapshot if snapshot is not None else Store().read()
    unranked: Dict[str, dict] = {}
    columns = ("sku", "name", "number", "set_name", "condition", "game", "number_key")
    for _, values in snapshot.inventory.cards.select(columns):
        sku, name, number, set_name, condition, game, number_key = values
        sku = str(sku or "").strip()
        if not sku:
            continue
        unranked[sku] = _export_row(sku, name, number, set_name, condition, game, number_key)
    card_skus = set(unranked.keys())

    if market is not None:
        ledger_rows, ledger_refusals = ledger_subject_rows(
            snapshot.ledger, unranked.keys(), market
        )
        for sku, row in ledger_rows.items():
            unranked.setdefault(sku, row)
        if refusals is not None:
            refusals.update(ledger_refusals)
        if fallback_rows is not None and card_skus:
            card_fallback, _unused = _ledger_export_rows(
                snapshot.ledger, card_skus, market
            )
            fallback_rows.update(card_fallback)

    revenue = revenue_by_sku(snapshot.ledger)
    return {sku: unranked[sku] for sku in rank_by_revenue(unranked.keys(), revenue)}


def sweep(
    rows: Dict[str, dict],
    market: _MarketLike,
    ranges: Tuple[str, ...] = (),
    *,
    now: Optional[int] = None,
    fallback_rows: Optional[Dict[str, dict]] = None,
) -> Tuple[Dict[str, Bucket], List[Source], Dict[str, str], List[str]]:
    """Ask `market` for every SKU in `rows`, over every range in `ranges`, and answer
    `(buckets_by_key, sources_by_range, refusals_by_sku, resolved_via_fallback)`.

    `ranges` DEFAULTS TO EVERY RANGE `pipeline/pricehistory.py:RANGES` NAMES, not
    `DEFAULT_RANGES` — the screen panel `PriceHistory.tsx` draws only `month` and `annual`
    because two views is what a person can read at once, but an archive whose entire reason
    to exist is "capture it before it ages out" has no such excuse to skip `quarter` and
    `semiannual`. A caller that wants a narrower pass (an operator re-running just the
    monthly figures) still passes its own tuple; nothing here hardcodes the full set as a
    constant a caller cannot override.

    BOTH DIRECTIONS ARE REPORTED, PER `CLAUDE.md`'S HARD RULE. `refusals_by_sku` is every SKU
    `rows` named that this pass could not read anything for — not catalogued, not resolvable,
    the endpoint unreachable or blocked — carrying `Market`'s own message, never dropped.

    A CARD-DERIVED ROW THAT REFUSES RETRIES ONCE, AGAINST THE LEDGER'S OWN ROW
    (`D233`, `rows_from_store`'s `fallback_rows` out-parameter).
    `cards` stays the PREFERRED source — this only fires for a SKU `readings_for_rows`
    could not resolve on its first attempt, and only when `fallback_rows` names a
    different, ledger-derived row for that same SKU to try instead. A SKU with no fallback
    row, or one whose fallback row ALSO fails to resolve, is still a refusal, named exactly
    as it would be with no fallback at all — the retry's own reason replaces the first
    attempt's, since it is the one that actually decided the SKU's fate.
    `resolved_via_fallback` names every SKU the retry rescued, sorted, so a caller can
    report which source answered rather than silently swapping one in.
    """
    now = int(now if now is not None else time.time())
    ranges = tuple(ranges) if ranges else tuple(RANGE_WIDTH_DAYS)

    readings, refusals = market.readings_for_rows(rows.values(), ranges=ranges)

    resolved_via_fallback: List[str] = []
    if fallback_rows:
        retry_rows = {
            sku: fallback_rows[sku] for sku in refusals if sku in fallback_rows
        }
        if retry_rows:
            retry_readings, retry_refusals = market.readings_for_rows(
                retry_rows.values(), ranges=ranges
            )
            for sku in retry_rows:
                if sku in retry_readings:
                    readings[sku] = retry_readings[sku]
                    refusals.pop(sku, None)
                    resolved_via_fallback.append(sku)
                elif sku in retry_refusals:
                    # The retry's own reason replaces the card row's — it is the one that
                    # decided this SKU never resolved this pass, and printing the FIRST
                    # attempt's reason once a second, different attempt has also been made
                    # would name a hop this SKU already got past.
                    refusals[sku] = retry_refusals[sku]
            resolved_via_fallback.sort()

    buckets: Dict[str, Bucket] = {}
    answered_by_range: Dict[str, int] = {r: 0 for r in ranges}
    for sku, reading in readings.items():
        product_id = getattr(reading, "product_id", 0)
        series_by_range = getattr(reading, "series", {}) or {}
        for range_, series in series_by_range.items():
            if range_ not in RANGE_WIDTH_DAYS:
                continue
            width = RANGE_WIDTH_DAYS[range_]
            saw_bucket = False
            for candidate in getattr(series, "buckets", ()):
                if candidate.start is None:
                    continue
                saw_bucket = True
                start = candidate.start.isoformat()
                buckets[_key(sku, range_, start)] = Bucket(
                    sku=sku,
                    product_id=int(product_id),
                    range=range_,
                    width_days=width,
                    start=start,
                    market=str(candidate.market) if candidate.market is not None else None,
                    quantity=int(candidate.quantity),
                    transactions=int(candidate.transactions),
                    low=str(candidate.low) if candidate.low is not None else None,
                    high=str(candidate.high) if candidate.high is not None else None,
                    at=now,
                )
            if saw_bucket:
                answered_by_range[range_] = answered_by_range.get(range_, 0) + 1

    requested = len(rows)
    sources = [
        Source(
            range=range_,
            at=now,
            requested=requested,
            answered=answered_by_range.get(range_, 0),
            refused=len(refusals),
        )
        for range_ in ranges
    ]
    return buckets, sources, refusals, resolved_via_fallback


def format_refusals(refusals: Dict[str, str]) -> List[str]:
    """Every refusal in `refusals`, as printable lines — NEVER TRUNCATED.

    `CLAUDE.md`'s hard rule is that both directions are reported and nothing is silently
    dropped; a `"... and N more"` tail is a silent drop of exactly the part a reader needs
    to close the gap this archive exists to close (the owner's own goal, `docs/specs/`
    read: full coverage). Grouped by identical reason, largest group first, because a
    press over hundreds of SKUs usually fails the same few ways many times — reading "42
    sku(s): <reason>" once, with every SKU listed under it, is what makes the tail
    auditable rather than merely counted.
    """
    by_reason: Dict[str, List[str]] = {}
    for sku in sorted(refusals):
        by_reason.setdefault(refusals[sku], []).append(sku)
    lines: List[str] = []
    for reason in sorted(by_reason, key=lambda r: (-len(by_reason[r]), r)):
        skus = by_reason[reason]
        lines.append(f"{len(skus)} sku(s): {reason}")
        for sku in skus:
            lines.append(f"  {sku}")
    return lines


# ------------------------------------------------------------------------------ resuming


def freshness_index(existing: Iterable[Bucket]) -> Dict[str, Dict[str, int]]:
    """`sku -> {range: latest 'at' this archive holds}`, built in ONE pass over the whole
    table — never once per subject SKU. `store-scaling` item 2's own complaint about a
    full-table walk repeated per row (measured on `cli/resolve.py:_copies_out`, ~1s per
    call on the owner's real store) is exactly the mistake this function exists to avoid:
    `PriceArchive.for_sku` is a full scan of `entries`, and calling it once per subject
    across a 900-SKU pass would be 900 scans of a table this same pass keeps growing.
    """
    index: Dict[str, Dict[str, int]] = {}
    for bucket in existing:
        by_range = index.setdefault(bucket.sku, {})
        if bucket.at > by_range.get(bucket.range, -1):
            by_range[bucket.range] = bucket.at
    return index


def split_by_freshness(
    rows: Dict[str, dict],
    index: Dict[str, Dict[str, int]],
    ranges: Tuple[str, ...],
    now: int,
    ttl_seconds: int,
) -> Tuple[Dict[str, dict], List[str]]:
    """`(needs_fetch, already_fresh_skus)` (D224).

    A SKU IS FRESH ONLY WHEN EVERY RANGE THIS PASS ASKS ABOUT ALREADY HAS A BUCKET READ
    WITHIN `ttl_seconds` OF `now`. `Market.readings_for_rows` fetches every range for a
    product in one request regardless of how many of them a caller still needs, so splitting
    one SKU's own ranges between "keep" and "re-fetch" would not save a request — it would
    only give this module a second, partial code path for nothing. One stale or missing
    range sends the whole SKU back to be read.

    A SKU WITH GENUINELY NO SALES THIS PERIOD NEVER LOOKS FRESH BY THIS TEST, because an
    empty series writes no bucket row and so leaves no `at` to check — `sweep`'s own loop
    only ever creates a `Bucket` for a candidate the endpoint actually returned
    (`saw_bucket`). That is the safe direction to be wrong in: such a SKU is re-read every
    pass rather than silently skipped, which costs a request and never costs data.

    ORDER IS PRESERVED. `rows` arrives ranked by `rank_by_revenue`; both outputs walk it in
    the same order they found it in, so a caller chunking `needs_fetch` still reads the
    highest-value subjects first.
    """
    needs: Dict[str, dict] = {}
    fresh: List[str] = []
    floor = -(10 ** 12)
    for sku, row in rows.items():
        seen = index.get(sku)
        if seen and ranges and all(now - seen.get(r, floor) < ttl_seconds for r in ranges):
            fresh.append(sku)
        else:
            needs[sku] = row
    return needs, fresh


def chunk_rows(rows: Dict[str, dict], size: int) -> List[Dict[str, dict]]:
    """`rows` split into ordered pieces of at most `size`, IN THE CALLER'S OWN ORDER —
    never re-sorted here. `rows_from_store` orders by sold revenue
    (D223); re-sorting alphabetically in this function would silently
    undo that ranking, which is exactly the kind of defect `CLAUDE.md` asks to be named
    rather than reintroduced by a "helper" three lines away from the decision it defeats.
    """
    items = list(rows.items())
    return [dict(items[i:i + size]) for i in range(0, len(items), size)]


# ------------------------------------------------------------------------------- pacing


def classify_refusals(
    refusals: Dict[str, str], had_earlier_success: bool
) -> Tuple[Dict[str, str], int]:
    """Rewrite a chunk's refusal messages, and answer how many were the host BLOCKING this
    session outright (D222).

    A 403 THAT ARRIVES AFTER THIS PASS HAS ALREADY READ AT LEAST ONE SKU SUCCESSFULLY IS A
    THROTTLE, NEVER AN AUTHORIZATION PROBLEM — measured 2026-09-19: product 652771 answered
    HTTP 200 minutes into a run and HTTP 403 later in the SAME session, with the same
    working `PKMNSCAN_TCG_USER_AGENT` and nothing about the request changed but the volume
    already sent. Telling that operator to set the User-Agent again sends them to fix
    something the run itself already proved was not broken — `CLAUDE.md`'s rule that a
    refusal must name its remedy cuts both ways: naming the WRONG remedy is worse than
    naming none.

    A 403 WITH NO EARLIER SUCCESS THIS PASS IS LEFT EXACTLY AS `Blocked` PHRASED IT — this
    function has no evidence yet to call it a throttle instead of what it might genuinely
    be, an authorization problem, and `Blocked`'s own remedy (D216) is still the honest
    first guess for that case.
    """
    rewritten: Dict[str, str] = {}
    blocked = 0
    for sku, message in refusals.items():
        if BLOCKED_SIGNATURE in message:
            blocked += 1
            if had_earlier_success:
                rewritten[sku] = (
                    "the host answered HTTP 403 after this pass had already read other "
                    "SKUs successfully — a throttle, not an authorization problem. Re-run "
                    "`archive sweep --write` later; it will not re-read what this pass "
                    "already archived."
                )
                continue
        rewritten[sku] = message
    return rewritten, blocked


def measured_pace(
    requests_made: int, elapsed_seconds: float, floor: float = DEFAULT_COURTESY_DELAY_SECONDS
) -> float:
    """Seconds to wait between requests, derived from what THIS pass actually measured
    before the host cut it off — never a guessed number (D222).

    `requests_made` and `elapsed_seconds` are this pass's own count and clock up to the
    moment a throttle was first seen, so `elapsed_seconds / requests_made` is the average
    interval a real run of THIS session survived. `THROTTLE_BACKOFF_FACTOR` doubles it: the
    rate that was just measured is the rate that got this session blocked, not a rate proven
    safe, so the next attempt goes slower than what merely worked "so far".
    """
    if requests_made <= 0 or elapsed_seconds <= 0:
        return floor
    observed = elapsed_seconds / requests_made
    return max(observed * THROTTLE_BACKOFF_FACTOR, floor)


def load_pace(path: Path, default: float = DEFAULT_COURTESY_DELAY_SECONDS) -> float:
    """The courtesy delay a PAST throttle measured, or `default` if this checkout has never
    hit one. Read once at the start of a sweep so even the FIRST request of a new press
    paces itself on real evidence rather than the naive constant, once any exists.
    """
    try:
        payload = json.loads(path.read_text("utf-8"))
        value = float(payload.get("courtesy_delay_seconds"))
    except (OSError, ValueError, TypeError, KeyError):
        return default
    return value if value > 0 else default


def save_pace(
    path: Path, courtesy_delay: float, *, requests_made: int, elapsed_seconds: float, at: int
) -> None:
    """Persist a throttle measurement so the NEXT press — this one resumed, or a wholly new
    one — starts paced on it. Same-directory temp-then-`replace` (`Market._store`'s own
    pattern, not reused by import because this module may not depend on
    `pipeline/pricehistory.py`'s internals): a reader must never see a half-written file,
    and a cache that cannot be written is slower, never wrong, so any `OSError` here is
    swallowed.
    """
    payload = {
        "courtesy_delay_seconds": courtesy_delay,
        "measured_from_requests": requests_made,
        "measured_over_seconds": round(elapsed_seconds, 1),
        "at": at,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload), "utf-8")
        temporary.replace(path)
    except OSError:
        pass
