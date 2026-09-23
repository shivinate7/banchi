"""One SKU, two stored names — the sibling `D242` cannot see, because its own class needs
the STORED NUMBERS to disagree. Here they agree (one SKU, one number) and the NAME does not:
the card's own stored `name` and the catalogue's own `Product Name` for the SKU the store
currently has it under.

REUSES `pipeline.join.name_disputes`, NEVER A SECOND SIMILARITY RULE. That function is D146's
own name-agreement test — containment first, then a `SequenceMatcher` ratio against
`NAME_DISPUTE_SIMILARITY` — and it is being fitted by a sibling session on `pipeline/join.py`,
which this module never touches and never restates. A card the fold cannot fault (a blank
read, a contained substring, a close-enough ratio) is NOT a finding, exactly as D240's own
measurement narrowed 379 raw disagreements down to 134 by the same tolerance.

MEASURED READ-ONLY ON THE OWNER'S STORE, against the newest cached export per game
(`inventory/.exports/<game>/*.csv`): 62 identified cards and 6 sold cards disagree. Examples:
`4/176` "Daisy!" under the "Lilting Lullaby" SKU; `1/75` "Tideturner" under "Kog'Maw,
Caustic"; `1/499` "Diana, Mount Targon" under "Diana, Lunari" — which may be a legitimate
variant (D240's own worked example of the same pair, the other direction). **THIS MODULE
REPORTS. IT NEVER DECIDES.** No card is guessed, no queue is touched, no network is opened —
the export is already on disk or the card is `not known`.

THREE HONEST VERDICTS, `cards audit`'s own shape (D172): a card with a stored SKU, a stored
name, an export for its game, and that SKU present in the export is CHECKED — agreeing or
disputing. Anything short of that is `not_known`, named by which fact was missing, never a
silent pass. A card with no SKU at all is not a subject of this check (there is no product
claim yet to disagree with) and is not counted either way.

UNLIKE `cards audit`'s OWN PRECEDENT, one card's `not_known` never suppresses another card's
real `dispute`. `cards audit` folds every doubt into one whole-store verdict because its
subject is a single binary fact (does the name resolve to the photo) asked of the whole
store at once. This check's subject is per-card and the per-card facts are independent — a
blank name on one card says nothing about whether SKU 4576213 disagrees with its own name —
so `not_known` here is a per-card count, reported honestly, and the OVERALL verdict answers
"was anything at all checked, and did any checked card disagree" rather than "is the whole
store's answer trustworthy." See `Report.verdict`.

RANKING THE ALTERNATIVES IS A TIE-BREAK, NOT A SECOND FOLD. For a disputed card, the export
rows whose `Product Name` folds (`pipeline.join.name_index_key`) EXACTLY to the card's own
stored name are the likely right SKU — no fuzzy match here, the fold is the same equality
`Catalog.rows_for_name` already uses. Where more than one such row exists, `rank_candidates`
breaks the tie using only the capture-time claims the card already carries —
`set_hint` (`pipeline.setnames.resolve`), `rarity_claim`, `metadata_finish`
(`pipeline.variant`'s own condition map) — never a new comparison invented for this module.
A claim the card does not carry contributes nothing, never a penalty, so a card with no
claims at all sorts stably in the export's own order.

PURE FUNCTIONS OVER PLAIN DATA — `Catalog.from_export` here is a small, local structure (NOT
`pipeline.join.Catalog`, which filters by game/rarity/Near-Mint-condition for the listing
path's own reasons this report has no need of: the SKU's own row can be ANY condition, and
reading it through the join's Near-Mint narrowing could silently make a real SKU disappear
from a diagnostic report). `cli/cmd_sku_name_contradictions.py` is the one caller that reads
the real store and the real exports and hands them to this module shaped this way; this
module never opens a database, a socket, or a file, and is exercised in tests with nothing
but literal `tcgcsv.Row` dicts.

Cites D146 (name agreement as a release signal), D239 (the four approved stored-data checks
this is a fifth, sibling check to, on `D242`'s own precedent of being kept apart),
D240 (the join-time measurement that found the same class of defect from the number-matched
side and named the tolerance this module reuses rather than re-derives), D242 (the sibling
this module's whole shape — read-only door, three verdicts, ranked-never-picked report — is
modelled on).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from pipeline import tcgcsv
from pipeline.join import name_disputes, name_index_key


@dataclass(frozen=True)
class CardRecord:
    """The stored fields this check reads. `key` is whatever the caller uses to name a
    position. `metadata_finish` and `rarity_claim` are already folded to a tuple by the
    caller — `store/master.py:Card.metadata_finish` is a `Union[str, List[str], None]` and
    this module takes no stance on that shape, exactly as `pipeline.variant._check_claim`
    does not belong here either; the CLI door folds it once, the same way it is folded
    before reaching the variant ladder.
    """

    key: str
    state: str
    sku: Optional[str] = None
    name: Optional[str] = None
    game: Optional[str] = None
    set_hint: Optional[str] = None
    metadata_finish: Tuple[str, ...] = ()
    rarity_claim: Tuple[str, ...] = ()


@dataclass(frozen=True)
class NotKnown:
    """One card this check could not evaluate, and the one of three named reasons why."""

    card: CardRecord
    reason: str


@dataclass(frozen=True)
class Dispute:
    """One card whose stored name `name_disputes` its own SKU's product name. `sku_row` is
    the export's own row for the SKU the card is CURRENTLY under — its Name/Number/Condition
    are what the SKU presently claims. `alternatives` are the export rows whose Product Name
    folds exactly to the card's own stored name — the likely right SKU(s), RANKED, NEVER
    PICKED. Empty when nothing in the export is named what this card is.
    """

    card: CardRecord
    sku_row: tcgcsv.Row
    alternatives: Tuple[tcgcsv.Row, ...] = ()


@dataclass(frozen=True)
class Report:
    """Every disputed and not-known card this pass found, split the way the screen wants it:
    identified first, sold in its own section — the two states D242's own measurement was
    run over. `skipped_no_sku` is counted and printed but is not a subject of this check at
    all — there is no product claim yet to disagree with.
    """

    identified: Tuple[Dispute, ...] = ()
    sold: Tuple[Dispute, ...] = ()
    not_known: Tuple[NotKnown, ...] = ()
    checked: int = 0
    skipped_no_sku: int = 0

    @property
    def disputes(self) -> Tuple[Dispute, ...]:
        return self.identified + self.sold

    @property
    def verdict(self) -> str:
        """`pass`, `fail`, or `not_known` — never a silent pass over zero rows.

        `not_known` fires only when NOTHING was checked at all (see the module docstring for
        why one card's own doubt never suppresses another card's real finding). `fail` fires
        on any disputed card, `pass` otherwise.
        """
        if self.checked == 0:
            return "not_known"
        if self.disputes:
            return "fail"
        return "pass"


class Catalog:
    """One game's cached export, indexed for this check alone. Deliberately NOT
    `pipeline.join.Catalog` — that class narrows to the game's Near-Mint (plus sealed)
    conditions for the LISTING path's own reason (D137), which this diagnostic has no use
    for: the SKU's own row can be any condition, and narrowing it away here would make a
    real, currently-listed SKU silently vanish from a report about it.
    """

    def __init__(self, export: tcgcsv.Export):
        self.export = export
        self._by_sku: Dict[str, tcgcsv.Row] = {}
        self._by_name: Dict[str, List[tcgcsv.Row]] = {}
        for row in export.rows:
            sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
            if sku:
                self._by_sku.setdefault(sku, row)
            name_key = name_index_key(row.get(tcgcsv.NAME_COLUMN))
            if name_key:
                self._by_name.setdefault(name_key, []).append(row)

    @classmethod
    def from_export(cls, export: tcgcsv.Export) -> "Catalog":
        return cls(export)

    def row_for_sku(self, sku: str) -> Optional[tcgcsv.Row]:
        return self._by_sku.get(sku)

    def rows_for_name(self, name: str) -> Tuple[tcgcsv.Row, ...]:
        return tuple(self._by_name.get(name_index_key(name), ()))


def rank_candidates(rows: Sequence[tcgcsv.Row], card: CardRecord) -> Tuple[tcgcsv.Row, ...]:
    """Break a tie among name-matched candidate rows using only the capture-time claims
    `card` already carries. NEVER A SECOND SIMILARITY RULE over the name itself — the rows
    already agree on the name exactly; this only orders them.

    Each claim scores independently and additively, and a claim the card does not carry
    contributes nothing — never a penalty — so a card with no claims at all sorts stably in
    the rows' own order (ties broken by SKU, for a report that reads the same way twice).
    """
    if len(rows) <= 1:
        return tuple(rows)

    resolved_set: Optional[str] = None
    if card.set_hint:
        from pipeline import setnames

        distinct_sets = sorted({row.get(tcgcsv.SET_COLUMN) or "" for row in rows})
        resolved_set = setnames.resolve(card.set_hint, distinct_sets)

    wanted_conditions: Optional[set] = None
    if card.metadata_finish:
        from pipeline import variant

        try:
            _, condition_by_finish = variant.vocabulary(card.game)
            wanted_conditions = {
                condition_by_finish[finish]
                for finish in card.metadata_finish
                if finish in condition_by_finish
            }
        except (KeyError, variant.UnknownFinish):
            wanted_conditions = None

    def score(row: tcgcsv.Row) -> int:
        points = 0
        if resolved_set is not None and (row.get(tcgcsv.SET_COLUMN) or "") == resolved_set:
            points += 1
        if wanted_conditions and (row.get(tcgcsv.CONDITION_COLUMN) or "") in wanted_conditions:
            points += 1
        if card.rarity_claim and (row.get(tcgcsv.RARITY_COLUMN) or "").strip() in card.rarity_claim:
            points += 1
        return points

    order = list(enumerate(rows))
    order.sort(key=lambda pair: (-score(pair[1]), str(pair[1].get(tcgcsv.SKU_COLUMN) or ""), pair[0]))
    return tuple(row for _index, row in order)


def check_card(
    card: CardRecord, catalogs: Dict[str, Catalog]
) -> Tuple[Optional[Dispute], Optional[NotKnown]]:
    """One card, three honest outcomes: agrees (both `None`), disputes (`Dispute`), or
    cannot be checked (`NotKnown`) — never a silent pass. A card with no SKU is a fourth,
    prior case the caller counts separately: there is no product claim yet to compare.
    """
    if not (card.name or "").strip():
        return None, NotKnown(card, "the card carries no stored name to compare")

    catalog = catalogs.get(card.game or "")
    if catalog is None:
        return None, NotKnown(
            card, f"no cached export for game {card.game!r} — nothing to check this SKU against"
        )

    row = catalog.row_for_sku(card.sku)
    if row is None:
        return None, NotKnown(
            card, f"SKU {card.sku!r} is absent from the newest cached {card.game} export"
        )

    product_name = row.get(tcgcsv.NAME_COLUMN)
    if not name_disputes(card.name, [{tcgcsv.NAME_COLUMN: product_name}]):
        return None, None

    alternatives = rank_candidates(catalog.rows_for_name(card.name), card)
    return Dispute(card=card, sku_row=row, alternatives=alternatives), None


def find_contradictions(
    cards: Sequence[CardRecord], catalogs: Dict[str, Catalog]
) -> Report:
    """Walk every card once. `catalogs` is `game -> Catalog`, built by the caller from
    whichever export file it chose as "newest" — a filesystem question this module never
    asks. See the module docstring for the verdict's own precedent and its one amendment
    over `cards audit`.
    """
    identified: List[Dispute] = []
    sold: List[Dispute] = []
    not_known: List[NotKnown] = []
    checked = 0
    skipped_no_sku = 0

    for card in cards:
        if not (card.sku or "").strip():
            skipped_no_sku += 1
            continue
        dispute, unknown = check_card(card, catalogs)
        if unknown is not None:
            not_known.append(unknown)
            continue
        checked += 1
        if dispute is not None:
            if card.state == "sold":
                sold.append(dispute)
            else:
                identified.append(dispute)

    return Report(
        identified=tuple(identified),
        sold=tuple(sold),
        not_known=tuple(not_known),
        checked=checked,
        skipped_no_sku=skipped_no_sku,
    )
