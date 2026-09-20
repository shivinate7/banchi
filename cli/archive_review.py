"""Route a price-history archive refusal to the standing review queue.

WHY THIS EXISTS. `pkmnscan archive sweep` (`cli/cmd_pricearchive.py`, `pipeline/pricearchive.py`)
reads every SKU this store has sold or holds against a live catalogue mirror. A SKU it
cannot resolve is an unfixed identification sitting in the `cards` table — `CLAUDE.md`'s
hard rule already names the remedy: "Never guess an identification, a variant, or a price.
Ambiguity goes to the review queue with its photo." This module is the one new hop between
a sweep's own refusal and that queue.

THE PRIMITIVE ALREADY EXISTS AND IS REUSED, NOT REBUILT (D167). `store/queues.py:Queue.upsert`
is the one function that may add a review entry: it preserves `first_seen`, and it refuses to
re-queue a position a human has already cleared. `cli/cmd_join.py` and `cli/requeue.py` are its
two existing callers; this is a third, over a different source of ambiguity. Nothing here
writes a second copy of that logic.

WHY THE MATCH IS THE CARD'S OWN FIELDS, NEVER THE SKU ALONE. A SKU can cover several physical
copies that carry different stored numbers — measured on the owner's real store, 2026-09-20:
`Exeggutor`, SKU 8936550, in `ME01: Mega Evolution`, covers 7 cards, 6 of them stored `005`
and one stored blank. `pipeline/pricearchive.py:rows_from_store` picks ONE row per SKU (the
last one `cards.select` happens to return) to test against the mirror, so only ONE of those
seven copies was ever actually asked about — the blank one, in this case. Queuing every card
that shares the SKU would put six correctly-numbered copies in front of a human for an
identification question that was never raised. So `cards_for_refusal` matches on the CARD's
own `(name, number, set_name)` against the refused row's shape, never on `sku` alone.

WHY A CARD WITH NO PHOTOGRAPH IS NEVER QUEUED. "A card reaching the queue carries its
photograph. That is what makes the queue answerable" (this task's own wording, echoing
`store/master.py`'s guard elsewhere). A sold card's photograph is reclaimed on purpose (D89),
so a terminal-state card is excluded before the photo check ever has to fire — but the photo
check stays regardless, because a terminal-state filter is a proxy for "has a photo", not a
promise of it.

WHY THE REASON IS `pipeline/variant.py:NO_CATALOG_ROW`, NOT A NEW STRING. It is the vocabulary
the real join ladder already uses for exactly this shape of failure — zero candidate rows
found in the catalogue — and `docs/decisions/`'s own rule (`building-check-primitive-first`)
is to reuse the constant the code already emits rather than mint a second word for one fact.

WHAT THIS DOES NOT DO. It does not call the network, does not read or write
`pipeline/pricearchive.py`, `pipeline/pricehistory.py` or `store/numbers.py`, and it does not
repair a single stored field. It only decides which refusals are safe to route to a human at
all (`is_identification_refusal`, below), and builds the entries `Queue.upsert` already knows
how to hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping

from pipeline import games, join, tcgcsv, variant
from store import master, queues

# The reason every entry this module writes carries — `pipeline/variant.py`'s own name for
# "the catalogue held zero rows matching this identification", which is exactly what a
# `NotResolvable` refusal off `pipeline/pricehistory.py:ProductIndex.find` means.
ARCHIVE_UNRESOLVED = variant.NO_CATALOG_ROW

# Substrings that mark a refusal as ABOUT THE NETWORK OR THE HOST, never about the card's own
# identification — `pipeline/pricehistory.py:Unreachable`'s three raise sites
# ("... answered HTTP <code>: ...", "... could not be reached: ...", "... did not answer
# JSON: ...") and `Blocked`'s own message, which always contains "answered HTTP 403" (matched
# by the broader "answered HTTP" already). BY THE TIME A REFUSAL REACHES THIS MODULE IT IS
# ALREADY A PLAIN STRING — `pipeline/pricehistory.py:Market.readings_for_rows` folds every
# `PriceHistoryError` into `str(exc)` before this layer ever sees one (D233's own note), and
# this module may not edit that file to carry the exception type further. Substring matching
# on a message this repo already writes in a fixed shape is the same discipline
# `pipeline/pricearchive.py:BLOCKED_SIGNATURE` already uses for the identical problem one
# case narrower.
_NETWORK_SIGNATURES = ("answered HTTP", "could not be reached", "did not answer JSON")


def is_identification_refusal(message: str) -> bool:
    """True for a refusal that is a fact about the CARD, never about the network right now.

    A `NotResolvable` message (`pipeline/pricehistory.py:ProductIndex.find`,
    `Market.product_id_for_row`, `Market.category_id`/`group_id`) never contains any of
    `_NETWORK_SIGNATURES` — it names the card's own name, number and set, or the category or
    group tcgcsv does not carry, and nothing about a socket or an HTTP status. A transient
    failure is excluded here rather than queued, because a card that could not be reached
    today is not a card whose STORED IDENTIFICATION is in question — re-running the sweep
    later is its own remedy, and queuing it would send a human to look at a photo for no
    reason connected to what actually failed.
    """
    text = str(message or "")
    return not any(signature in text for signature in _NETWORK_SIGNATURES)


@dataclass(frozen=True)
class _Match:
    card: master.Card
    sku: str
    reason: str


def cards_for_refusals(
    inventory: "master.Inventory",
    rows: Mapping[str, dict],
    refusals: Mapping[str, str],
) -> List[_Match]:
    """Every ON-HAND physical card whose own stored identification is EXACTLY the shape a
    refused SKU's export-shaped row named — see the module docstring for why the match is
    per-card and not per-SKU.

    `rows` is `pipeline/pricearchive.py:rows_from_store`'s own return value (or the same
    shape built by a test): `sku -> {Product Line, Set Name, Number, Product Name,
    TCGplayer Id, Condition}`, keyed by `pipeline/tcgcsv.py`'s column names. A refused SKU
    with no row in `rows` names nothing to match against and is skipped — that shape should
    not occur (every refused SKU was resolved against ITS OWN row a moment earlier), and
    skipping rather than raising keeps this function total over whatever a caller hands it.

    A TRANSIENT (NETWORK) REFUSAL NEVER REACHES THE QUEUE, per `is_identification_refusal`.

    A CARD IN A TERMINAL STATE (D26's `sold`, `retired`, `moved`) IS EXCLUDED — its
    photograph may already be reclaimed (D89), and a departed card is not a question about
    where a human should look next.
    """
    matches: List[_Match] = []
    for sku, message in refusals.items():
        if not is_identification_refusal(message):
            continue
        row = rows.get(sku)
        if row is None:
            continue
        name = str(row.get(tcgcsv.NAME_COLUMN, "") or "")
        number = str(row.get(tcgcsv.NUMBER_COLUMN, "") or "")
        set_name = str(row.get(tcgcsv.SET_COLUMN, "") or "")
        for _, values in inventory.cards.select(
            ("box", "idx", "state", "name", "number", "number_key", "set_name", "game"),
            sku=sku,
        ):
            box, idx, state, card_name, card_number, number_key, card_set, game = values
            if state in master.TERMINAL_STATES:
                continue
            if str(card_name or "") != name or str(card_set or "") != set_name:
                continue
            # The row's own Number cell prefers `number_key` over the bare `number`
            # (D234's own composition, read here rather than reimplemented) — a card
            # matches if EITHER its bare number or its composed key is the one the refused
            # row carried, since `_export_row` may have used either one.
            if number and str(card_number or "") != number and str(number_key or "") != number:
                continue
            if not number and (card_number or "") not in ("", None):
                # The refused row carried no number at all; a card that HAS one stored is a
                # different shape and was not the row this SKU's refusal was ever about.
                continue
            card = inventory.cards.get(f"{box}/{idx}")
            if card is None:
                continue
            matches.append(_Match(card=card, sku=sku, reason=ARCHIVE_UNRESOLVED))
    return matches


def queue_entries(
    matches: Iterable[_Match],
    box_views: Mapping[int, "join.BoxView"],
) -> List["queues.QueueEntry"]:
    """`cards_for_refusals`'s matches, each carrying its photograph, ready for
    `store/queues.py:Queue.upsert` — never written here, so a caller stays free to preview.

    Takes the MATCHES rather than re-deriving them, so a caller that already computed them
    (to know which boxes to build `box_views` for) never pays the walk twice.

    `box_views` is `cli/resolve.py:box_views(inventory, boxes=...)`'s own return shape — this
    module does not build one itself, so it never has to open `store/master.py`'s box
    registry a second, competing way. A box missing from it (should not happen; a caller
    builds it from every box a match names) falls back to `join.BoxView()`'s bare index
    space, D58's own precedent for "no layout to consult" rather than a raised exception.

    A CARD WITH NO PHOTOGRAPH IS SKIPPED, NEVER QUEUED WITHOUT ONE — this task's own rule,
    "a card reaching the queue carries its photograph."
    """
    entries: List["queues.QueueEntry"] = []
    seen: set = set()
    for match in sorted(matches, key=lambda m: (m.card.box, m.card.index)):
        card = match.card
        key = (card.box, card.index)
        if key in seen or not card.photo:
            continue
        seen.add(key)
        game = card.game or games.DEFAULT_GAME
        position = box_views.get(int(card.box), join.BoxView()).at(card.box, card.index)
        entries.append(
            queues.QueueEntry(
                position=f"{card.box}/{card.index}",
                box=card.box,
                index=card.index,
                label=join.place_text(game, position),
                photo=card.photo,
                read={
                    "name": card.name,
                    "number": card.number,
                    "set_hint": card.set_hint,
                },
                reason=match.reason,
                candidates=[],
            )
        )
    return entries


def apply(review: "queues.Queue", entries: Iterable["queues.QueueEntry"]) -> int:
    """Upsert every entry, and only every entry — `Queue.upsert`'s own refusal to re-queue a
    cleared position, and its own preservation of `first_seen`, are what make this
    re-runnable without duplicating anything. Returns how many were NEWLY queued."""
    return sum(1 for entry in entries if review.upsert(entry))
