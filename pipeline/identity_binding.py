"""The migration's own classifier (`docs/specs/identity-follows-sku.md` §7, lane 2): which
class a card lands in, whether that class derives or holds, and the three audit checks §4.3
asks the merged report to run.

READ-ONLY AND STORE-AGNOSTIC ON PURPOSE. Every function here takes plain data — a
`store.master.Card`, a `store.skus.SkuRow`, a list of raw event dicts — and returns an
answer, never a write. `./pkmnscan cards identity` (`cli/cmd_cards.py`) and
`scripts/identity-replay.py` are the two callers: one reads a live `Store().write()`
snapshot and then performs the binds this module recommends, the other reads a read-only
copy and asserts against what this module recommends without writing anything. Splitting the
classifier out is what lets the replay prove the press's OWN logic rather than a second copy
of it — the replay imports this module and calls the identical `classify_card`/`plan` the
press calls.

THE SEVEN CLASSES, §7.2's OWN TABLE, TESTED IN THIS ORDER:

    T3    a human act (an `answered` or `sku_corrected` event, after the card's own
          `captured_at`) chose the card's current SKU. Derives (owner's ruling 2, §12).
    T5    the read name disputes the SKU's row, or is blank, and no human act governs.
          Held.
    T4s   the read name agrees and the number does not, and the name names more than one
          product in the game's SKU table. Held.
    T4u   the same, but the name names exactly one product (D162). Derives (ruling 1).
    T1    the read name equals the row's after the fold, and the number agrees or is
          blank. Derives — spelling only.
    T2    the read name is a near miss, not disputed, and the number agrees or is blank.
          Derives — spelling only.
    T6    no SKU at all. Nothing to derive.

A CARD WHOSE SKU IS NOT IN THE TABLE (§3.2's escape hatch) is `SKU_UNKNOWN`, reported and
left exactly as it is — `bind_sku` would refuse it, so this module never proposes it.

`derives(cls)` and `held(cls)` are the two predicates every caller needs; a class is never
both.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pipeline import games as games_module
from pipeline import tcgcsv
from pipeline.join import _name_compare_key, name_disputes, number_index_key
from store.master import IDENTITY_SKU, Card

if TYPE_CHECKING:
    # `held_review_entry`'s own return type only — its BODY imports `QueueEntry` locally
    # (see that function's docstring for why), so this is the one place the name needs to
    # resolve for the type checker without pulling `store.queues` in at module scope.
    from store.queues import QueueEntry
from store.numbers import (
    NUMBER_AND_PRINTED_TOTAL,
    catalog_number_fields,
    join_key,
    strip_name_suffix,
    strip_set_code,
)
from store.skus import SkuRow, _parse_sku

# ------------------------------------------------------------------------------ the classes

T3 = "T3"
T5 = "T5"
T4S = "T4s"
T4U = "T4u"
T1 = "T1"
T2 = "T2"
T6 = "T6"
SKU_UNKNOWN = "sku_unknown"

CLASSES = (T3, T5, T4S, T4U, T1, T2, T6, SKU_UNKNOWN)
DERIVING_CLASSES = (T1, T2, T3, T4U)
HELD_CLASSES = (T4S, T5)

# The two events that count as a human choosing a SKU (§7.2's own words: "answer or
# correction"). `group_answer` shares the `answered` event name — `do_review_group_answer`
# writes one ordinary `answered` line per card (`server/capture_server.py`, its own
# docstring: "Each position gets its own `answered` history line ... exactly as a single
# answer writes it") — so there is no third event name to add.
HUMAN_ACT_EVENTS = ("answered", "sku_corrected")


def derives(cls: str) -> bool:
    return cls in DERIVING_CLASSES


def held(cls: str) -> bool:
    return cls in HELD_CLASSES


# --------------------------------------------------------------------- number agreement (§6)


def number_agrees(strategy: str, read_number, read_printed_total, row_number: str) -> bool:
    """§6's own test, "equal or blank": a blank read is no evidence and never disputes: the
    same rule `pipeline/join.name_disputes` and `name_corroborates` already apply to a blank
    name, carried over to the number here. A present read must fold-equal the row's own
    cell.

    Pokemon (`store/numbers.NUMBER_AND_PRINTED_TOTAL`): `store/numbers.join_key` of the
    read pair, then `pipeline/join.number_index_key` on both sides — the SAME fold
    `Catalog.rows_for_key` already applies, so a card that would join to this exact row
    agrees here too. Both halves or nothing: a number with no denominator cannot compose the
    key the row is indexed by (`pipeline/join.py:_key_number_and_printed_total`'s own rule),
    so a partial read counts as blank rather than as a guessed disagreement.

    Every other strategy: `store/numbers.strip_set_code` of the read (D55/D67 — a model that
    glued a set code onto the front), then the same `number_index_key` fold.
    """
    key = _read_number_key(strategy, read_number, read_printed_total)
    return key is None or key == number_index_key(row_number)


def _read_number_key(strategy: str, read_number, read_printed_total) -> Optional[str]:
    """The read pair, folded to the same key `number_agrees` compares the row against, or
    `None` for "no evidence" (blank, or half a Pokemon pair) — the one place both
    `number_agrees` and the review-candidate builder derive it, so the two can never fold
    the read two different ways."""
    if strategy == NUMBER_AND_PRINTED_TOTAL:
        if not read_number or not read_printed_total:
            return None
        composed = join_key(read_number, read_printed_total)
    else:
        if not read_number:
            return None
        composed = strip_set_code(read_number)
    return number_index_key(composed)


# ------------------------------------------------------------------------- name agreement


def _row_dict(row: SkuRow) -> tcgcsv.Row:
    """A `SkuRow` reshaped as the one-column dict `pipeline/join.name_disputes` reads —
    `Product Name` is the only cell that test consults."""
    return {tcgcsv.NAME_COLUMN: row.product_name}


def name_fold_matches(read_name: Optional[str], row_product_name: str) -> bool:
    """T1's own test: the read name EQUALS the row's after the fold both
    `name_disputes`/`name_corroborates` already apply on the catalog side —
    `pipeline.join._name_compare_key`, reused rather than re-derived (the fence's own
    instruction: reuse `pipeline/join.name_disputes`, write no second rule — this is the
    exact fold that function already carries, imported rather than restated).
    """
    if not (read_name or "").strip():
        return False
    return _name_compare_key(read_name) == _name_compare_key(row_product_name, catalog_side=True)


# ------------------------------------------------------------- product ambiguity (D162, T4s/T4u)


def distinct_products_by_line(skus: Mapping[str, SkuRow]) -> Dict[str, List[SkuRow]]:
    """One representative `SkuRow` per (set, name, number) — a "product" in §3.2's own
    words, the `sku_products` view's grouping — bucketed by `product_line`. Built once per
    plan rather than per card: `matching_products` below only ever reads this.
    """
    seen: Dict[str, Set[Tuple[str, str, str]]] = {}
    out: Dict[str, List[SkuRow]] = {}
    for row in skus.values():
        product = (row.set_name, row.product_name, row.number)
        line_seen = seen.setdefault(row.product_line, set())
        if product in line_seen:
            continue
        line_seen.add(product)
        out.setdefault(row.product_line, []).append(row)
    return out


def matching_products(
    read_name: Optional[str], products: Sequence[SkuRow]
) -> List[Tuple[str, str]]:
    """The distinct `(set_name, number)` products, among `products`, this read NAMES —
    D162's own uniqueness question, "how many products does this name name", answered the
    same way `pipeline/join.py:Catalog.rows_for_name`/`_by_name` already answer it: an EXACT
    fold-bucket lookup (`_name_compare_key`, catalog side folded, read side not), never
    `name_disputes`'s lenient near-miss threshold. The two tests answer different questions
    — `name_disputes` asks "does this read disagree with ONE specific row" (T5's gate,
    deliberately lenient so a typo does not read as a different card); this asks "which
    products, exactly, does this spelling identify" (a lookup, and D162's own worked
    example — `Aspirant's Climb` — is an exact match on both sides). Reusing the lenient
    test here over-counted: measured on the owner's store, it moved 6 cards from T4u into
    T4s that the exact fold correctly keeps unique.
    """
    key = _name_compare_key(read_name)
    if not key:
        return []
    out: List[Tuple[str, str]] = []
    for row in products:
        if _name_compare_key(row.product_name, catalog_side=True) == key:
            out.append((row.set_name, row.number))
    return out


# ------------------------------------------------------------- the newest human act (§3.1, §7.4)


def newest_human_sku(
    events: Sequence[Mapping[str, object]], key: str, captured_at: Optional[str]
) -> Optional[str]:
    """The SKU the newest `answered`/`sku_corrected` line at this position chose, scoped to
    AFTER the card's own `captured_at` (§3.1's "6/53" finding: a position reused by a later
    physical card must not be credited with the earlier card's answer; the replay's own
    newest-human-act check restates
    it as the replay's own bar). `events` must already be in ascending `id` order (oldest
    first — `store/db.py:events_at`'s own contract), so the last qualifying line IS the
    newest: no timestamp comparison needed, and none is attempted, because a stamp typed
    from a stalled clock (D81's own worry) would sort no worse than one typed correctly.

    None when nothing qualifies — no human ever answered this card, or the newest human line
    predates its own capture (the reused-position case) and so belongs to whatever card sat
    here before.
    """
    result: Optional[str] = None
    for event in events:
        if event.get("position") != key or event.get("event") not in HUMAN_ACT_EVENTS:
            continue
        at = event.get("at")
        if captured_at and isinstance(at, str) and at < captured_at:
            continue
        result = event.get("sku")
    return str(result) if result else None


# --------------------------------------------------------------- the read backfill (§3.4, §7.3.1)


def backfill_read(
    cid: Optional[str],
    identifications_by_digest: Mapping[str, Mapping[str, object]],
    fallback_name: Optional[str],
    fallback_number: Optional[str],
    fallback_printed_total: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """`(read_name, read_number, read_printed_total)` for one card: the `identifications`
    entry whose `photo_sha256` equals this card's `cid` (§3.4: "the store's `identifications`
    table (keyed by photograph digest)" — the table is keyed by POSITION on disk, so the
    caller builds `identifications_by_digest` as the reverse index over every entry's own
    `photo_sha256`, which is what makes this robust to a reused position — §3.1's "6/53"
    case again). Falls back to the card's own CURRENT fields where no entry matches (§7.2:
    "0 cards today").
    """
    entry = identifications_by_digest.get(cid) if cid else None
    if entry is None:
        return fallback_name, fallback_number, fallback_printed_total
    identification = entry.get("identification")
    if not isinstance(identification, dict):
        return fallback_name, fallback_number, fallback_printed_total
    name = identification.get("name")
    number = identification.get("number")
    printed_total = identification.get("printed_total")
    if name is None and number is None and printed_total is None:
        return fallback_name, fallback_number, fallback_printed_total
    return name, number, printed_total


# ------------------------------------------------------------------------------ classification


@dataclass(frozen=True)
class Classification:
    """One card's class, and the identity it would carry after the migration.

    `new_name`/`new_number`/`new_printed_total` are set only when `derives(cls)` — the
    composed identity `bind_sku` would write, computed the SAME way `bind_sku` composes it
    (`store/numbers.strip_name_suffix`, `store/numbers.catalog_number_fields`) so a preview
    can never predict something the press would not actually write.
    """

    cls: str
    row: Optional[SkuRow]
    new_name: Optional[str] = None
    new_number: Optional[str] = None
    new_printed_total: Optional[str] = None


def classify_card(
    *,
    sku: Optional[str],
    game: str,
    row: Optional[SkuRow],
    read_name: Optional[str],
    read_number: Optional[str],
    read_printed_total: Optional[str],
    human_sku: Optional[str],
    products_by_line: Mapping[str, Sequence[SkuRow]],
) -> Classification:
    """§7.2's ladder, tested in the table's own order."""
    if not sku:
        return Classification(cls=T6, row=None)
    if row is None:
        return Classification(cls=SKU_UNKNOWN, row=None)

    strategy = games_module.get(game)["join_key"]

    def derived_identity() -> Tuple[str, Optional[str], Optional[str]]:
        number, printed_total = catalog_number_fields(strategy, row.number)
        return strip_name_suffix(row.product_name), number, printed_total

    if human_sku is not None and human_sku == sku:
        name, number, printed_total = derived_identity()
        return Classification(cls=T3, row=row, new_name=name, new_number=number,
                               new_printed_total=printed_total)

    disputed = name_disputes(read_name, [_row_dict(row)])
    blank_name = not (read_name or "").strip()
    if disputed or blank_name:
        return Classification(cls=T5, row=row)

    if not number_agrees(strategy, read_number, read_printed_total, row.number):
        products = matching_products(read_name, products_by_line.get(row.product_line, ()))
        if len(products) > 1:
            return Classification(cls=T4S, row=row)
        name, number, printed_total = derived_identity()
        return Classification(cls=T4U, row=row, new_name=name, new_number=number,
                               new_printed_total=printed_total)

    name, number, printed_total = derived_identity()
    cls = T1 if name_fold_matches(read_name, row.product_name) else T2
    return Classification(cls=cls, row=row, new_name=name, new_number=number,
                           new_printed_total=printed_total)


# ------------------------------------------------------------------------------- reading rows


def read_skus(conn: sqlite3.Connection) -> Dict[str, SkuRow]:
    """Every `skus` row, parsed through the table's own `_parse_sku` (reused, not
    re-derived) — the read-only door: a plain `SELECT`, never `db.connect`."""
    out: Dict[str, SkuRow] = {}
    for key, payload in conn.execute("SELECT key, payload FROM skus"):
        try:
            record = json.loads(payload)
        except (TypeError, ValueError):
            continue
        row = _parse_sku(str(key), record)
        if row is not None:
            out[str(key)] = row
    return out


def read_cards(conn: sqlite3.Connection) -> List[Card]:
    """Every card, as a plain `store.master.Card` — the same `Card(**known)` construction
    `store/master.py:Inventory.CARDS`'s own `parse` uses, reached here without
    `db.connect` (`payload` already carries the whole `asdict`, §-scoped read in `cli/
    cmd_cards.py`'s own `_cards` helper)."""
    known = set(Card.__annotations__)
    out: List[Card] = []
    for (payload,) in conn.execute("SELECT payload FROM cards"):
        try:
            record = json.loads(payload)
        except (TypeError, ValueError):
            continue
        out.append(Card(**{k: v for k, v in record.items() if k in known}))
    return out


def read_identifications_by_digest(conn: sqlite3.Connection) -> Dict[str, dict]:
    """The `identifications` table, re-keyed by `photo_sha256` rather than by position —
    `backfill_read`'s own index (§3.4). The LAST entry wins per digest, which is never
    observed to matter (0 collisions measured, §3.2's sibling measurement) and is the same
    "newest wins" default every other fold in this repo uses when it must pick one."""
    out: Dict[str, dict] = {}
    for (payload,) in conn.execute("SELECT payload FROM identifications"):
        try:
            record = json.loads(payload)
        except (TypeError, ValueError):
            continue
        digest = record.get("photo_sha256")
        if isinstance(digest, str) and digest:
            out[digest] = record
    return out


def read_human_events(conn: sqlite3.Connection) -> List[dict]:
    """Every `answered`/`sku_corrected` event, oldest first (`ORDER BY id`, `store/
    db.py:events_at`'s own ordering) — `newest_human_sku`'s whole input."""
    placeholders = ",".join("?" for _ in HUMAN_ACT_EVENTS)
    out: List[dict] = []
    for (payload,) in conn.execute(
        f"SELECT payload FROM events WHERE event IN ({placeholders}) ORDER BY id",
        HUMAN_ACT_EVENTS,
    ):
        try:
            record = json.loads(payload)
        except (TypeError, ValueError):
            continue
        out.append(record)
    return out


def listing_skus(conn: sqlite3.Connection) -> Set[str]:
    """Every SKU `listings` names — §4.3's second audit reads cards AND listings."""
    out: Set[str] = set()
    for (key,) in conn.execute("SELECT key FROM listings"):
        if key:
            out.add(str(key))
    return out


# ------------------------------------------------------------------------------------ the plan


@dataclass(frozen=True)
class CardPlan:
    key: str
    sku: Optional[str]
    game: str
    state: str
    cid: Optional[str]
    classification: Classification
    read_name: Optional[str]
    read_number: Optional[str]
    read_printed_total: Optional[str]
    old_name: Optional[str]
    old_number: Optional[str]
    old_printed_total: Optional[str]

    @property
    def cls(self) -> str:
        return self.classification.cls

    @property
    def identity_moves(self) -> bool:
        """Does the DRAWN identity move to a different card (§7.1) — the read name moves to
        one the read disputes, or the read number moves to one the fold disagrees with.
        Never true for a spelling-only change (case, accent, qualifier, D146's own
        tolerance)."""
        if not derives(self.cls):
            return False
        name_moves = (self.old_name or "").strip().upper() != (
            self.classification.new_name or ""
        ).strip().upper() and self.cls not in (T1, T2)
        # T1/T2 change spelling only, by the ladder's own construction — the number test at
        # T4u is what can genuinely move a number, and T3 is a human act and never "moves"
        # anything by this test's own definition (§7.1: "a wrong human answer" is a
        # different, unmeasured risk, not an identity move this table counts).
        number_moves = self.cls == T4U
        return name_moves or number_moves


# --------------------------------------------------------------- the held review entry (§7.3)


def _candidate_dict(row: SkuRow, found_by: Optional[str]) -> Dict[str, object]:
    """One SKU row shaped as the wire dict `#/review` already draws — `cli/
    resolve.py:_candidate_rows`' own fields, built off `row.raw` rather than a re-fetched
    export row, because the SKU table's `raw` already carries the whole CSV row verbatim
    (§3.2's own words: "payload... for any column not promoted")."""
    entry: Dict[str, object] = {
        "sku": row.raw.get(tcgcsv.SKU_COLUMN, ""),
        "name": row.product_name,
        "set": row.set_name,
        "number": row.number,
        "condition": row.condition,
        "market": row.raw.get(tcgcsv.MARKET_PRICE_COLUMN, ""),
    }
    if row.rarity:
        entry["rarity"] = row.rarity
    if found_by:
        entry["found_by"] = found_by
    return entry


def held_review_candidates(
    row: SkuRow,
    game: str,
    read_name: Optional[str],
    read_number: Optional[str],
    read_printed_total: Optional[str],
    products_by_line: Mapping[str, Sequence[SkuRow]],
) -> List[Dict[str, object]]:
    """§7.3's third thing a held-and-identified card's review entry carries: "the SKU's own
    row, and D253's two candidate sets — the rows the read name finds and the rows the read
    number finds". One list, `found_by` tagging which test found each product first —
    `listing` for the card's own bound row (ahead of the other two, so it is never shown
    twice under a different tag), `name`, then `number`. A product already tagged keeps its
    first tag, `cli/resolve.py:_candidate_rows`'s own "found_by... only where that question
    has two answers" restated over three rather than two.
    """
    line = row.product_line
    tagged: Dict[Tuple[str, str], str] = {(row.set_name, row.number): "listing"}
    ordered: List[SkuRow] = [row]
    for candidate in products_by_line.get(line, ()):
        product = (candidate.set_name, candidate.number)
        if product in tagged:
            continue
        if not name_disputes(read_name, [_row_dict(candidate)]):
            tagged[product] = "name"
            ordered.append(candidate)
    strategy = games_module.get(game)["join_key"]
    read_key = _read_number_key(strategy, read_number, read_printed_total)
    if read_key is not None:
        for candidate in products_by_line.get(line, ()):
            product = (candidate.set_name, candidate.number)
            if product in tagged:
                continue
            if number_index_key(candidate.number) == read_key:
                tagged[product] = "number"
                ordered.append(candidate)
    return [_candidate_dict(r, tagged[(r.set_name, r.number)]) for r in ordered]


def held_review_entry(card: Card, row: SkuRow, plan: "MigrationPlan") -> "QueueEntry":
    """The review entry §7.3 opens for a held, IDENTIFIED card — `+listing_disputed`
    (`pipeline/routing.py`), "Is the listing the right card?" (`app/src/ReviewQueue.tsx`).

    `Queue.upsert` (`store/queues.py`) accepts it: a held card has no answered entry, so the
    refusal that protects an already-cleared position never fires. Local imports — `store.
    queues`/`pipeline.join` both sit ABOVE this module in a caller's own import, and pulling
    them in at module scope here would risk the cycle `store/`'s D63 rule exists to name;
    neither module imports this one, so the risk is theoretical, but the cost of a local
    import is one line and the cost of getting that judgement call wrong is a broken
    `./pkmnscan cards identity --write`.
    """
    from pipeline.join import Position, place_text
    from pipeline.routing import LISTING_DISPUTED
    from store.queues import QueueEntry

    position = Position(box=card.box, index=card.index)
    candidates = held_review_candidates(
        row, card.game or games_module.DEFAULT_GAME, card.read_name, card.read_number,
        card.read_printed_total, plan.products_by_line,
    )
    return QueueEntry(
        position=card.key,
        box=card.box,
        index=card.index,
        label=place_text(card.game or games_module.DEFAULT_GAME, position),
        photo=card.photo,
        read={
            "name": card.read_name,
            "number": card.read_number,
            "printed_total": card.read_printed_total,
            "set_hint": card.set_hint,
        },
        confidence=card.confidence,
        reason=LISTING_DISPUTED,
        candidates=candidates,
        market=None,
    )


# §5.5: D242 (`cards contradictions`) and D255 (`cards sku-names`) retire into this report's
# name half and number half. Both exclude a card a human has already answered — "a human who
# chose that SKU off the photograph has already answered the report's question", and a guard
# that goes red on an answered question is spent (§5.5's own words).
HUMAN_BOUND_BY = ("answer", "group_answer", "correction", "confirm")


@dataclass(frozen=True)
class AuditFindings:
    """§4.3 point 2 and §5.5, the merged report's own two halves.

    `identity_drift`/`sku_not_in_table`/`rarity_disagreement` are §4.3's three audit
    failures. `name_half`/`number_half` are D242/D255's replacement (§5.5): every
    SKU-bound, non-human-bound card whose READ still disputes the row it is bound to — a
    property that can change after the bind, when a newer export changes the row's own
    facts (§3.2's `sku_facts_changed`)."""

    identity_drift: List[Tuple[str, str]] = field(default_factory=list)
    sku_not_in_table: List[Tuple[str, str]] = field(default_factory=list)
    rarity_disagreement: List[Tuple[Tuple[str, str, str], List[str]]] = field(
        default_factory=list
    )
    name_half: List[str] = field(default_factory=list)
    number_half: List[str] = field(default_factory=list)


def audit(cards: Sequence[Card], skus: Mapping[str, SkuRow], listings: Set[str]) -> AuditFindings:
    """§4.3's three checks, over the CURRENT store (whatever bindings already exist —
    zero, on a store lane 2 has not yet written to)."""
    identity_drift: List[Tuple[str, str]] = []
    sku_not_in_table: List[Tuple[str, str]] = []
    name_half: List[str] = []
    number_half: List[str] = []
    for card in cards:
        if not card.sku:
            continue
        row = skus.get(str(card.sku))
        if row is None:
            sku_not_in_table.append((card.key, str(card.sku)))
            continue
        if getattr(card, "identity_source", None) != IDENTITY_SKU:
            continue
        strategy = games_module.get(card.game or games_module.DEFAULT_GAME)["join_key"]
        number, printed_total = catalog_number_fields(strategy, row.number)
        expected = (
            strip_name_suffix(row.product_name), number, printed_total, row.rarity,
            row.set_name, row.condition,
        )
        actual = (
            card.name, card.number, card.printed_total, card.rarity, card.set_name,
            card.condition,
        )
        if expected != actual:
            identity_drift.append((card.key, str(card.sku)))
        if card.bound_by in HUMAN_BOUND_BY:
            continue
        if name_disputes(card.read_name, [_row_dict(row)]):
            name_half.append(card.key)
        if not number_agrees(strategy, card.read_number, card.read_printed_total, row.number):
            number_half.append(card.key)
    for sku in listings:
        if sku not in skus:
            sku_not_in_table.append(("listings", sku))

    products: Dict[Tuple[str, str, str], Set[str]] = {}
    for row in skus.values():
        product = (row.product_line, row.set_name, row.product_name)
        products.setdefault(product, set()).add(row.rarity)
    rarity_disagreement = [
        (product, sorted(rarities))
        for product, rarities in products.items()
        if len(rarities) > 1
    ]
    return AuditFindings(
        identity_drift=identity_drift,
        sku_not_in_table=sku_not_in_table,
        rarity_disagreement=rarity_disagreement,
        name_half=name_half,
        number_half=number_half,
    )


def class_counts(plans: Sequence[CardPlan]) -> Dict[str, int]:
    counts = {cls: 0 for cls in CLASSES}
    for plan in plans:
        counts[plan.cls] += 1
    return counts


@dataclass(frozen=True)
class MigrationPlan:
    """§7.3's whole pass, bundled: every card's classification, and the per-product-line
    map the classifier built to answer D162's uniqueness question — handed back so a caller
    building held-review entries (`held_review_candidates`) never rebuilds it."""

    plans: List[CardPlan]
    products_by_line: Dict[str, List[SkuRow]]

    @property
    def counts(self) -> Dict[str, int]:
        return class_counts(self.plans)


def plan_migration(
    cards: Sequence[Card],
    skus: Mapping[str, SkuRow],
    events: Sequence[dict],
    identifications_by_digest: Mapping[str, dict],
) -> MigrationPlan:
    """One `CardPlan` per card — §7.3's whole classification pass, over data the caller has
    already read (a read-only connection, or a live snapshot's tables)."""
    products_by_line = distinct_products_by_line(skus)
    events_by_key: Dict[str, List[dict]] = {}
    for event in events:
        events_by_key.setdefault(str(event.get("position")), []).append(event)

    plans: List[CardPlan] = []
    for card in cards:
        key = card.key
        game = card.game or games_module.DEFAULT_GAME
        row = skus.get(str(card.sku)) if card.sku else None
        read_name, read_number, read_printed_total = backfill_read(
            card.cid, identifications_by_digest, card.name, card.number, card.printed_total,
        )
        human_sku = newest_human_sku(events_by_key.get(key, ()), key, card.captured_at)
        classification = classify_card(
            sku=card.sku, game=game, row=row, read_name=read_name, read_number=read_number,
            read_printed_total=read_printed_total, human_sku=human_sku,
            products_by_line=products_by_line,
        )
        plans.append(CardPlan(
            key=key, sku=card.sku, game=game, state=card.state, cid=card.cid,
            classification=classification, read_name=read_name, read_number=read_number,
            read_printed_total=read_printed_total, old_name=card.name, old_number=card.number,
            old_printed_total=card.printed_total,
        ))
    return MigrationPlan(plans=plans, products_by_line=products_by_line)
