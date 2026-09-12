"""Turning a run's identifications into a join. Shared by `join` and `emit`.

`emit` re-derives the join rather than reading a serialised one. Both commands are free and
deterministic given the same export and the same identifications, so re-deriving costs
nothing and buys the one guarantee that matters: `emit` cannot write a file that disagrees
with the report `join` printed. A serialised intermediate would be a third thing to keep
correct, and the first thing to go stale when someone edits a review.

CARDS THAT NEVER REACH THE LADDER. A card with no identification, or with no position at
all, has nothing for the catalog to match — but it is still a real card in a real box, so it
gets a queue entry of its own here rather than being quietly absent from the join. That is
the same rule as everywhere else in this pipeline: unlisted is fine, unrecorded is not.

AND CARDS THAT NEVER REACH THE CATALOG, WHICH ARE A DIFFERENT THING AND HAVE THEIR OWN TYPE.
A game whose registry entry says `catalogued: False` — `misc`, permanently — is identified
like any other card and then held out of the join, because there is no export for Magic or
Yu-Gi-Oh here to match a row against. `NotJoined` is that list and it is deliberately not
`failures`: one is a card working as designed, the other is a card that needs a human, and a
reader that prints them under one heading has lost the distinction the registry spends two
flags keeping.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import (
    Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Union,
)

from cli import runs
from pipeline import games, join, orders, pricing, routing, tcgcsv, variant
from store import files, master, photos, queues
from store.session import Store


@dataclass(frozen=True)
class NotJoined:
    """A card that was identified and then correctly stopped before the catalog.

    NOT A FAILURE, AND THIS TYPE EXISTS SO IT CANNOT BE FILED AS ONE. `PreJoinFailure` below
    means something went wrong — no position, no identification — and every one of those goes
    to the main review queue for a human. This is the opposite: the game's registry entry
    says `catalogued: False`, permanently, so there is no export to match a row against and
    no price to read. `misc` is the only entry in that state and it is working exactly as
    designed. Putting these in the review queue would, in `app/src/types.ts`'s words, "put a
    red flag on 1% of the shelf forever" — and a real fault would then hide among them.

    RECORDED RATHER THAN DROPPED, because unlisted is fine and unrecorded is not. The card
    keeps its position, its photo, its identification and its operator note; the run's
    `identifications.json` holds the full model answer including the fields only the misc
    schema carries. What it never gets is a catalog row, an import line or a price.

    THE BUG THIS PREVENTS IS A CRASH, NOT A MISLISTING, AND IT WAS ALREADY LIVE.
    `join.lookup_for` calls `games.require`, which raises `NotCatalogued` for `misc` — so a
    single misc card in a run took the WHOLE join down with a traceback, after the export was
    read and before anything was written. `lookup_for`'s own docstring prescribes the remedy
    in as many words: "filter it out of the run before a catalog is built". This is that
    filter, and it is the caller's job because the caller is the only layer that knows which
    cards a run holds.
    """

    key: str
    game: str
    photo: Optional[str]
    box: int
    index: int
    read: Dict[str, object] = field(default_factory=dict)
    # D58's label coordinates for this card's box, or an empty view for a caller that has
    # no store to read — which renders in index space, exactly as this file did before.
    # Defaulted so a hand-built record (T7 builds several) reads as it always did.
    view: join.BoxView = field(default_factory=join.BoxView)

    @property
    def label(self) -> str:
        # `place_text`, not `Position.label`: a report line is one of the surfaces the
        # pooled ruling (`pipeline/games.py`'s `located` flag) forbids the label on.
        # `misc` — today's only occupant of this type — is located, so its lines are
        # byte-identical; the branch exists for the day a non-located game is also
        # uncatalogued.
        return join.place_text(self.game, self.view.at(self.box, self.index))

    @property
    def describe(self) -> str:
        name = str(self.read.get("name") or "").strip()
        return f"{self.label}  {self.game}{('  ' + name) if name else ''}"


@dataclass(frozen=True)
class PreJoinFailure:
    """A card the join never saw, and why. Always destined for the main queue."""

    key: str
    photo: Optional[str]
    reason: str
    box: Optional[int] = None
    index: Optional[int] = None
    read: Dict[str, object] = field(default_factory=dict)

    # Which game the record claims, resolved by `load` with the same three-source backfill
    # every other consumer applies. Carried so `label` below can honour the pooled ruling:
    # a failed pokemon_code card still fails, still queues, and still never renders a
    # position label. Defaulted so a hand-built failure — T7 builds them — reads as the
    # backfill would read it.
    game: str = games.DEFAULT_GAME
    # D58's label coordinates for this card's box, or an empty view for a caller that has
    # no store to read — which renders in index space, exactly as this file did before.
    # Defaulted so a hand-built record (T7 builds several) reads as it always did.
    view: join.BoxView = field(default_factory=join.BoxView)

    @property
    def label(self) -> str:
        if self.box is None or self.index is None:
            return f"{Path(self.photo).name if self.photo else self.key} (no position)"
        return join.place_text(self.game, self.view.at(self.box, self.index))

    @property
    def describe(self) -> str:
        return f"{self.label}  {self.reason}"


@dataclass(frozen=True)
class GameJoin:
    """One game's slice of a run: its export rows, its catalog, its join report.

    THE UNIT D25 CUTS A RUN INTO. Catalogs are built per game and never merged — a merged
    number index would report a cross-game collision through `colliding_keys` as though it
    were the cross-set collision that report is about — so everything downstream of the
    catalog is per-game too: the report, and the import files `emit` writes from it.
    `export` is the game's own filtered rows (what the catalog indexes); `source` describes
    the FILE those rows came from, which two games may share.
    """

    game: str
    export: tcgcsv.Export
    catalog: join.Catalog
    report: join.JoinReport
    source: Dict[str, object]


@dataclass
class Resolved:
    """Everything `join` reports and `emit` writes from.

    Per-game since D25: `joins` holds one `GameJoin` per game the run's cards claim, in
    registry order. The single-game accessors (`report`, `catalog`, `export`, `source`)
    are how every caller written before the partition still reads a one-game run — and
    they REFUSE on a multi-game run rather than answering with one game's slice, because a
    caller that has not learned about `joins` yet would silently drop every other game.
    """

    run: runs.Run
    joins: "OrderedDict[str, GameJoin]"
    failures: List[PreJoinFailure]
    rule: pricing.Rule
    basis: str
    # The D9 cut-off this resolution was partitioned against (`pipeline/corpus.py`'s
    # `policy.threshold`). Carried beside `rule` and `basis` for their reason: `join` prints
    # what it ran with, and a figure a report cannot name is a figure nobody can check.
    threshold: Decimal = pricing.THRESHOLD
    # Cards held out of the join because their game has no catalog. See `NotJoined`: these
    # are correct outcomes, not failures, and they are a separate list from `failures` so
    # that no reader can print them under one heading.
    not_joined: List[NotJoined] = field(default_factory=list)
    # position key -> capture photo. Carried so `emit` can create an inventory record for a
    # position the store has never seen — a run joined from a hand-made or recovered
    # identifications file has no capture record behind it, and a state transition that
    # silently lands nowhere is exactly what this pipeline must not do.
    photos: Dict[str, Optional[str]] = field(default_factory=dict)
    # D36 — positions this run's records were re-bound to, because the photograph they were
    # identified from has since moved slot. `old key -> new key`, empty on a healthy run.
    # Carried so the run report can SAY it happened: a silent correction to a position is
    # indistinguishable from no correction at all, and this pipeline may not move a card
    # between slots without printing that it did.
    realigned: Dict[str, str] = field(default_factory=dict)
    # D36 — records skipped because the photograph they were identified from is in this box
    # no longer: the card was deleted mid-box or retired after the run. Named in the report,
    # never dropped in silence.
    departed: List[str] = field(default_factory=list)
    # D36 — boxes whose photographs are not on disk, so their slots could not be checked at
    # all. Their records pass through as the run recorded them; the report says so rather
    # than letting an unchecked box read as a verified one.
    unverified_boxes: List[int] = field(default_factory=list)

    def _only(self) -> GameJoin:
        if len(self.joins) == 1:
            return next(iter(self.joins.values()))
        raise ValueError(
            f"this run joined {len(self.joins)} games ({', '.join(self.joins)}); "
            "read .joins per game — the single-game accessor would silently drop the rest"
        )

    @property
    def report(self) -> join.JoinReport:
        return self._only().report

    @property
    def catalog(self) -> join.Catalog:
        return self._only().catalog

    @property
    def export(self) -> tcgcsv.Export:
        return self._only().export

    @property
    def source(self) -> Dict[str, object]:
        return self._only().source

    @property
    def matches(self):
        """Every game's (sku -> SkuMatch), one mapping. SKUs are TCGplayer-global —
        one product line can never carry another's `TCGplayer Id` — so the union is
        collision-free by construction."""
        merged: "OrderedDict[str, join.SkuMatch]" = OrderedDict()
        for game_join in self.joins.values():
            merged.update(game_join.report.matches)
        return merged

    @property
    def queued_positions(self):
        """Positions this run put in a standing queue."""
        return {
            _key(q.card.position)
            for game_join in self.joins.values()
            for q in game_join.report.queued
        } | {f.key for f in self.failures}

    @property
    def matched_positions(self):
        """Positions this run resolved cleanly."""
        return {
            _key(position)
            for game_join in self.joins.values()
            for match in game_join.report.matches.values()
            for position in match.positions
        }

    @property
    def not_joined_positions(self):
        """Positions this run identified and deliberately kept out of the catalog."""
        return {n.key for n in self.not_joined}

    @property
    def processed_positions(self):
        """Every position this run had an opinion about.

        The set a queue release is allowed to act on. A run that looked at box 3 knows
        nothing about box 7, so it must not evict box 7's entries from a standing queue —
        the queues outlive runs, which is the whole reason they are standing.

        AN UNCATALOGUED CARD COUNTS AS PROCESSED, and that is the point of including it here
        rather than leaving it out as "not really joined". "This game has no catalog" is a
        settled opinion about that position, so a stale queue entry left there by an earlier
        run — one that queued it before its game was understood — is released rather than
        standing forever with nothing that will ever clear it. It is deliberately NOT in
        `queued_positions`, so it frees rather than re-parks.
        """
        return self.matched_positions | self.queued_positions | self.not_joined_positions

    @property
    def listed_skus(self):
        return {
            m.sku
            for game_join in self.joins.values()
            for m in game_join.report.matches.values()
            if m.listable
        }

    @property
    def sub_threshold_skus(self):
        return {
            sku
            for game_join in self.joins.values()
            for sku in game_join.report.below_threshold.skus
        }

    @property
    def no_market_data_skus(self):
        return {
            m.sku
            for game_join in self.joins.values()
            for m in game_join.report.no_market_data
        }


def _key(position: join.Position) -> str:
    return f"{position.box}/{position.index}"


def _detected(finish, game: str):
    """The model's `finish`, kept only if THIS GAME stocks it (D3 rung 3's whitelist).

    `variant.vocabulary` is the single home — see the call site for the bug that made this a
    function rather than a membership test written inline.

    AN UNREGISTERED GAME DROPS THE FINISH RATHER THAN RAISING, and that is deliberate: the
    caller carries an unknown game string through UNCHANGED so `join.lookup_for` can refuse
    it by name, and a crash here would pre-empt that named refusal with a stack trace. The
    card is refused either way; the difference is whether the operator is told which game
    nobody registered.
    """
    if not finish:
        return None
    try:
        stocked, _ = variant.vocabulary(game)
    except (games.UnknownGame, join.EmptyCatalog, KeyError, ValueError):
        return None
    return finish if finish in stocked else None


def _finish_claim(raw) -> Optional[Tuple[str, ...]]:
    """The run record's `metadata_finish`, shaped for `IdentifiedCard` — defensively.

    D3 rung 1's claim is a SET (amended 2026-08-23) and `IdentifiedCard` is frozen, so this
    is a tuple for the reason that dataclass's own comment gives. `_rarity_claim` below is
    the same function for the same reason and this is deliberately its twin, down to the
    order of its branches — the two claims are now one shape and reading alike is the point.

    A BARE STRING BECOMES ONE MEMBER RATHER THAN SIX LETTERS. That is D3's read-side backfill
    at the hop where it matters most: every run record written before the amendment carries a
    string, `identifications.json` files are kept and re-joined (`join` and `emit` are both
    free and re-runnable by design), and iterating one would hand the ladder a claim of
    `'n', 'o', 'r', 'm', 'a', 'l'` — six finishes of no game, which `variant._check_claim`
    would raise `UnknownFinish` on. The claim's own reader had the identical trap and
    `_check_rarity_claim` calls it "the classic bug this function exists to refuse".

    NO VOCABULARY CHECK, and no re-ordering either. Membership was `identify/sidecar.py`'s
    job at the read, which is also where the enum order was imposed; `variant._check_claim`
    normalises again anyway, and it is idempotent because both normalisers order by the same
    game's enum. What survives here is shape.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple)):
        values = [item for item in raw if isinstance(item, str)]
    else:
        return None
    cleaned = tuple(text.strip() for text in values if text and text.strip())
    return cleaned or None


def _rarity_claim(raw) -> Optional[Tuple[str, ...]]:
    """The run record's `rarity_claim`, shaped for `IdentifiedCard` — defensively.

    The normal writer is `cli/cmd_identify.py`, copying a claim `identify/sidecar.py`
    already validated, so the usual value here is a clean list or an absent key. But a run
    can be joined from a hand-made or recovered identifications file — the docstring on
    `Resolved.photos` names that case — so the same two shapes that reader defends against
    are defended here: a bare string becomes ONE rarity rather than being iterated into
    letters, and anything that is not a string or a list of strings becomes no claim at
    all. No vocabulary check: membership was `identify/sidecar.py`'s job at the read, and
    an unrecognised string surviving to the ladder costs a review tap, never a mislisting —
    `variant.resolve` filters, and a member matching no row reviews as
    `rarity_claim_mismatch`."""
    if raw is None:
        return None
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple)):
        values = [item for item in raw if isinstance(item, str)]
    else:
        return None
    cleaned = tuple(text.strip() for text in values if text and text.strip())
    return cleaned or None


def box_views(inventory: master.Inventory) -> Dict[int, join.BoxView]:
    """Every box's D58 label coordinates, read off the live store in one pass.

    THE REPORT AND THE SCREEN HAVE TO SPELL ONE ADDRESS. A card's number counts the cards on
    hand in its box, so a reporter that renders without this answers in the numbering system
    D58 replaced — and prints it beside a screen that does not, with nothing saying which is
    which. `server/capture_server.py:_Places._walk` is the other implementation of this walk
    and the two are asserted equal on a real card in T7, which is the same shape
    `make port-agreement` uses for the other pair of languages that must agree.

    THIS FIXES A DEFECT OLDER THAN D58 ON ITS WAY PAST. Every `Position` built in this file
    used to pass NO layout at all, so a box-2 queue entry was written as `Section 1 · Card
    300` where the app rendered `Section 4 · Card 48`. Two renderers, two answers, and
    nothing had ever compared them.

    A POOLED CARD IS SKIPPED BY RULING (D24) and a TERMINAL one by state (D26/D10) — the
    same two exclusions `_walk` makes, for the same two reasons: one never had a slot and
    the other has left it. A record that will not coerce degrades its whole box to index
    space rather than being skipped past, because a card nobody can place might be one of
    the cards being counted.
    """
    grouped: Dict[int, List[Tuple[int, bool]]] = {}
    broken: set = set()
    for card in inventory.cards.values():
        try:
            at = (int(card.box), int(card.index))
        except (TypeError, ValueError):
            # Which box it belonged to is exactly what could not be read, so every box
            # loses its count — `_walk`'s own store-wide degrade, for its reason.
            return {}
        game = str(getattr(card, "game", None) or games.DEFAULT_GAME)
        try:
            if not games.get(game)["located"]:
                continue
        except games.UnknownGame:
            pass  # unregistered reads as located, exactly as `join.is_located` answers
        grouped.setdefault(at[0], []).append(
            (at[1], card.state not in master.TERMINAL_STATES)
        )
    views: Dict[int, join.BoxView] = {}
    for number, rows in grouped.items():
        if number in broken:
            continue
        try:
            sections = inventory.sections_for(number)
        except master.BadSections:
            # A layout that will not validate means the section and card numbers are
            # unknown, which is `_Places.view`'s call and not a new one.
            sections = ()
        views[number] = join.BoxView(
            sections=sections,
            occupied=tuple(i for i, on_hand in sorted(rows) if on_hand),
            departed=tuple(i for i, on_hand in sorted(rows) if not on_hand),
        )
    return views


class LiveReading(NamedTuple):
    """One export's `Total Quantity` for a SKU, and WHEN that file was read (D87, amended).

    The time is the file's mtime — `cli/runs.py:describe_source` — which is the fetch time
    for a fetched export and the file's own for an upload. It is what `Listing.live_reading`
    weighs the store's own `live_as_of` against, so a reading is never carried without it.
    """

    quantity: int
    as_of: str


def _live_by_sku(
    exports: Mapping[Path, tcgcsv.Export], as_of: Mapping[Path, str]
) -> Dict[str, LiveReading]:
    """`Total Quantity` per SKU, with its time, across every export this run was handed (D59).

    Unioned across files without a per-game partition, which is safe for exactly one
    reason: a `TCGplayer Id` is unique across the marketplace, so two games' exports cannot
    collide on one. D25's partition is about which CATALOG a card is joined against, and
    nothing here joins anything. A SKU present in two files takes the NEWER file's reading,
    by `master.newer_stamp` — the same arbitration `_copies_out` then applies against the
    store, one register down.
    """
    out: Dict[str, LiveReading] = {}
    for path, export in exports.items():
        stamp = as_of[path]
        for row in export.rows:
            sku = row.get(tcgcsv.SKU_COLUMN)
            if not sku:
                continue
            try:
                reading = LiveReading(
                    tcgcsv.parse_quantity(row[tcgcsv.LIVE_QUANTITY_COLUMN]), stamp
                )
            except (ValueError, TypeError, KeyError):
                # AN UNREADABLE CELL ON A ROW THIS RUN NEVER TOUCHES MAY NOT TAKE THE JOIN
                # DOWN. `live_before` used to read this column lazily, for matched SKUs
                # only; walking every row of a 10,000-row export widens what one bad cell
                # can reach, so the widening is paid for here rather than by the operator.
                # SKIPPING IS NOT DEFAULTING TO ZERO ANY MORE, and an earlier version of
                # this comment said the two were the same: `_copies_out` used to read this
                # map with `.get(sku, 0)`. An absent SKU now keeps the STORE's reading
                # (`Listing.live_reading` with no quantity), and a zero is a reading of
                # zero at the file's time, so a row nobody could read is left out rather
                # than read as "nothing live". What is bought is the same as before and
                # worth stating plainly — an unreadable cell on a row this run never matches
                # decides nothing, where it once took the whole join down. A cell on a row
                # the run DOES match still raises, from `SkuMatch.live_before`, and that is
                # right: the cap for a SKU being joined may not be computed from a number
                # nobody could read.
                continue
            held = out.get(sku)
            if held is None or master.newer_stamp(reading.as_of, held.as_of):
                out[sku] = reading
    return out


def _copies_out(
    inventory: master.Inventory, live_by_sku: Mapping[str, LiveReading]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Per SKU: how many copies TCGplayer is holding right now, live AND pending (D59) —
    and, beside it, the `live` figure that answer was computed from.

    ONE NUMBER, TWO CONSUMERS, AND THAT IS THE WHOLE OF D59. `_committed_keys` below spends
    it on positions so a run knows which of its copies not to re-send, and
    `pipeline/join.py:SkuMatch.add_to_quantity` subtracts it from the cap. They were two
    different numbers before: the cap was measured against `live_before`, which is global,
    MINUS `len(committed_positions)`, which is whatever the box in front of the run happens
    to hold — so a SKU split across two boxes had its cap enforced once per box, and box 1's
    four pushed copies were invisible to a run over box 3.

        min(live + pushed + staged, max(live, copies not sold))

    THE FLOOR IS THE NEWEST READING OF `live`, AND IT CANNOT BE ARGUED BELOW. D8 and D11
    put the authority in `Total Quantity`, and it keeps it — for the moment the file was
    read. Where the store has read `live` LATER (a sale, a D34 release, a `reconcile
    --live` against a fresher export), the store's figure is the floor instead, and the
    older file cannot re-open the cap OR close it. `Listing.live_reading` is the one rule,
    the store's `live_as_of` is what it reads, and `live_now` carries the figure it chose
    to `SkuMatch.live_out` so no sentence downstream is printed off the reading it lost.

    Returns `(copies_out, live_now)`: the first is what the cap subtracts, the second the
    live figure it was built on, per SKU.

    THE CEILING IS PHYSICAL, AND IT IS WHAT CORRECTS A STUCK `pushed`. `Listing.held` is a
    claim this Mac made when it wrote a CSV; `cli/cmd_reconcile.py` is the only thing that
    clears it, and an operator who never exports from Staged never does. Once the import
    LANDS, the export reports those copies live and the claim double-counts them. It cannot
    be true that TCGplayer holds more copies than we sent and have not sold, so
    `copies_not_sold` is what says so — no write, no inference about what landed, and no
    second CSV. A RETIRED copy still counts as sent: see that method for why.

    `Listing.held` rather than `pushed + staged` spelled out again. That property is the
    closest thing this pipeline has to a spec for this arithmetic and it had no caller.
    """
    out: Dict[str, int] = {}
    live_now: Dict[str, int] = {}
    for sku in set(live_by_sku) | set(inventory.listings):
        entry = inventory.listings.get(sku)
        # THE STORE'S OWN `live` IS A SECOND READING, NOT A SECOND FLOOR, AND THE TWO ARE
        # TOLD APART BY TIME. `max(export, entry.live)` was tried and reverted: it closed
        # the post-reconcile hazard (pushed and staged both zero, a later under-reporting
        # export re-opening the cap) and opened its mirror, where a stale-HIGH stored value
        # outranked a fresh-LOW export and the SKU never refilled after a sale — T7's own
        # stale-export case went red. Both directions were a `max` over two readings nobody
        # had dated. `Listing.live_as_of` dates the store's, the file's mtime dates the
        # export's, and `Listing.live_reading` picks the newer: the D59 hazard ("after a
        # reconcile nothing is standing") is closed by time rather than by trusting either
        # side, and the mirror cannot come back because an older store reading loses.
        #
        # A SKU absent from every export keeps the store's figure — D87's settlement finally
        # reaches the cap for the SKUs a run's own export does not cover. A row present with
        # a BLANK cell is a reading of zero at the file's time, which is the measured defect
        # (a recorded export fetched fifteen minutes before its emit), and it now loses to
        # the newer settlement instead of overwriting it.
        reading = live_by_sku.get(sku)
        offered = reading.quantity if reading else None
        as_of = reading.as_of if reading else None
        read = (
            entry.live_reading(offered, as_of)
            if entry is not None
            else (reading.quantity if reading else 0)
        )
        read = max(0, int(read))
        # THE ESTIMATE, ARBITRATED BY THE SAME TWO RULES THE STORE WRITES BY (D115).
        # `live_reading` picks which READING to believe and `sales_pending` picks which SALES
        # survive it, so this line and `Listing.observe_live` cannot answer differently about
        # one file — the property `_copies_out` has shared with the store since D87's
        # amendment, extended to the second fact rather than abandoned for it.
        #
        # THE CAP READS THE ESTIMATE AND NOT THE READING, and `check_listing_commands` pins
        # why: once an import has landed and `join` has drawn `staged` to zero, `claim` is 0
        # and the estimate is the ONLY arm of the `max` below that can refill a SKU after a
        # sale. On the reading alone, four live and two sold gives `max(4, -2) = 4`, no room,
        # and D7's refill is silently retired.
        live = max(0, read - (entry.sales_pending(as_of) if entry is not None else 0))
        live_now[sku] = live
        claim = entry.held if entry is not None else 0
        # THE SKIP READS THE READING, SO THIS MAP'S KEY SET DOES NOT MOVE. A SKU whose reading
        # is 1 and whose estimate is 0 must be RECORDED as zero rather than dropped: absent
        # from this map, `SkuMatch.held_out` and `live_out` are None and `copies_out`/
        # `live_now` fall back to the export row's own column — the pre-D87 answer, restored
        # silently, on exactly the rows a sale just touched.
        if read <= 0 and claim <= 0:
            continue
        # THE CEILING IS THE SALES, NOT THE STAMPED COPIES, AND THAT CHANGED UNDER THIS
        # BRANCH. It was `max(live, len(copies_not_sold(sku)))`, on the premise that we
        # cannot have SENT more copies than we own and have not sold — which held only while
        # `cli/cmd_emit.py` stamped a SKU onto exactly the copies it wrote into a file. D7's
        # 2026-08-30 amendment moved that stamp to `uncommitted_positions`, correctly: the cap
        # bounds the LISTING, not the IDENTITY, and copies past the fourth were invisible to
        # every SKU-keyed surface. A stamp now means MATCHED, so counting stamped copies
        # counts backstock that was never in any import file, the ceiling stops binding, and
        # the stuck-`pushed` correction this entry exists for quietly disappears.
        #
        # What survives the change is the arithmetic that never needed a stamp. `pushed` is
        # a count of copies SENT and it has no drawdown; a SALE is the one event that proves
        # a sent copy has left TCGplayer, because a copy cannot sell without having been
        # listed. So the claim is aged by the sales rather than bounded by the shelf, and
        # `live` remains the floor D8 and D11 make it.
        # AND IT ONLY AGES A CLAIM THE EXPORT CORROBORATES. A sale reduces what TCGplayer
        # holds only if the copy was THERE, and the export's reading is the only witness this
        # Mac has to that. What CHANGED is that the reading was being asked one question when
        # it can answer two (`docs/DEBTS.md` §24, now the entry below):
        #
        #   - A reading that reports copies LIVE vouches for every sale of the SKU. Our copies
        #     reach that shelf, so a copy that sold sold from it, whenever it sold. `sold` is
        #     every sale ever, which is the arm that has always been here.
        #   - A reading of NOTHING vouches for exactly the sales it was taken AFTER. A zero
        #     read on 09-11 against a copy that sold on 09-07 is that sale's own result; it is
        #     the reading the sale PRODUCED, not evidence the copy was never listed. This is
        #     D115's rule pointed the other way — that entry clears the store's own counter
        #     where it adopts a reading taken after the sales — and it is `sales_before`.
        #
        # A SALE AFTER A ZERO READING IS STILL NOT AGED, and that is not caution, it is the
        # arithmetic: the reading said nothing of ours was live at its own time, so a copy
        # that sold later cannot be shown to have been one of the copies this claim counts.
        #
        # NEITHER ARM DOUBLE-COUNTS, AND THE COMMENT THIS REPLACED SAID IT DID. `claim` is
        # `pushed + staged`, and NOTHING anywhere decrements it on a sale — `cmd_reconcile`
        # moves copies between its two halves and `cmd_join` draws `staged` down by the RISE
        # in live quantity, both of which leave a sale untouched. So a sale the reading has
        # already absorbed is one the claim has NOT, which is exactly why it has to be
        # subtracted here. The two arms are a `max` over two independent estimates and never a
        # sum, so a sale reaching both cannot be spent twice: four pushed and live-read four,
        # two sold, gives `max(4 - 2, 4 - 2)` and not two.
        #
        # AND THE CASE THE OLD GATE WAS ACTUALLY PROTECTING KEEPS ITS ANSWER, which is the
        # reason the fix is a second arm rather than the deletion of the first.
        # `check_listing_commands`' re-emit idempotence case — four pushed, one sold, export
        # SILENT — has no reading at all: `live_as_of` is null because an emit takes no
        # reading (that case asserts it by name), so `read_at` is None, `sales_before` counts
        # nothing, the claim stands at four and no fifth row is offered. The copies are
        # sitting in Staged and a card marked sold against that state did not leave
        # TCGplayer's hands, exactly as before.
        #
        # WHAT IS LEFT UNDER IT IS ONE AMBIGUITY AND IT IS NAMED RATHER THAN PAPERED OVER: a
        # SKU whose import landed in Staged and never went live reads zero too, so a copy sold
        # by hand against THAT state ages a claim it should not. Telling it from a sold-out
        # listing needs D59's own reopener — a marker that a copy actually reached an import
        # file — and `docs/DEBTS.md` §24 is now that residue rather than this whole defect.
        #
        # AND SO DOES THE CORROBORATION GATE. "What did the export report" is a fact about the
        # FILE, and an estimate is not a file. Driven by the estimate the live arm would switch
        # off the moment the counted sales met the reading, taking the case above with it.
        #
        # `read_at` IS THE STAMP OF THE READING THAT WON, not the file's. `live_reading` may
        # have refused this export in favour of a newer settlement the store holds, and asking
        # "was this sale before the reading" of a reading that was not used is how the two
        # halves of one arbitration come apart. `Listing.reading_taken_at` is the same three
        # branches, so they cannot.
        read_at = entry.reading_taken_at(offered, as_of) if entry is not None else as_of
        sold = (
            len(inventory.positions_for_sku(sku)) - len(inventory.copies_not_sold(sku))
            if read > 0
            else inventory.sales_before(sku, read_at)
        )
        out[sku] = max(live, claim - sold)
    return out, live_now


def _oldest_first(copies: Sequence[master.Card]) -> List[master.Card]:
    """This SKU's copies in the order they were CAPTURED, oldest first.

    `Inventory.copies_on_hand` answers in box-walk order and keeps it: `pipeline/orders.py`
    hands that list to the fulfiller and the box walk is the order a hand moves through a
    drawer. This is the one caller that needs a different question answered — WHICH of these
    copies are the ones already at TCGplayer — so the re-ordering is local rather than a
    change to the store method every other reader shares.

    A COPY CAPTURED AFTER THE LAST EMIT CANNOT BE AMONG THE COPIES THAT EMIT SENT, which is
    what makes capture time the right key rather than a tidier arbitrary one. An emit walks
    the run's `uncommitted_positions`, a run covers cards photographed at a particular
    sitting, and cards photographed tonight were in no file written last week. The store
    cannot name the copy that backs a listing — D7 rules copies fungible and nothing records
    it — so this is an inference; it is the only one causality permits.

    A COPY WITH NO STAMP SORTS OLDEST, which is the conservative direction: committing it
    withholds it from this press rather than sending it, and D7's estimate errs low. It also
    makes this function identical to the box-walk slice on a store where NO record carries a
    stamp — the empty string ties every key and `(box, index)` decides — so a store written
    before the field existed behaves exactly as it did.
    """
    return sorted(copies, key=lambda c: (c.captured_at or "", c.box, c.index))


def _committed_keys(inventory: master.Inventory, copies_out: Mapping[str, int]) -> set:
    """Positions the join must treat as copies TCGplayer already holds or has pending.

    `SkuMatch.committed_positions` is per-position and the store's counts are per-SKU, so
    something has to turn one into the other. It is a COUNTING device and not an address:
    the store records how many copies of a SKU are pushed and staged, and this picks that
    many of the SKU's unsold copies, OLDEST CAPTURE FIRST.

    IT PICKED IN BOX-WALK ORDER UNTIL 2026-09-11, JUSTIFIED BY A SENTENCE THAT WAS FALSE.
    This docstring said *"the only thing the join does with them is `len()` and a set
    subtraction. Any N of them would do — that is the fungibility ruling"*. The `len()` is
    true and the set subtraction is not: `SkuMatch.uncommitted_positions` subtracts these
    keys from ONE RUN's positions, so which copies are chosen decides which run may list.
    D7's fungibility ruling is about the physical cards and is untouched — any three of
    fifteen identical copies really are the three that are live — but it says nothing about
    which run gets to send one, and this function was reading it as though it did.

    WHAT THE WRONG ORDER COST, on the operator's store, run `2026-09-11-box1-01`: box 1 is
    tonight's capture and box 3 is the backstock, box 1 sorts first, so the NEWLY captured
    copies were marked as the ones TCGplayer already holds and the older backstock — which
    no run is joining — was left uncommitted and therefore unreachable. **52 of the run's 119
    matched SKUs offered zero copies and 59 real cards were stranded**, every one of them
    reported as *"every copy in this run is already listed or has left the box"*. The
    operator read that sentence and said it was *"just not true/possible"*. 52 of the 59 are
    this defect; the other 7 are the stuck claim `_copies_out` could not age, which is
    `docs/DEBTS.md` §24 and is not fixed here — `_copies_out` aged them the next day
    (`D150`), and nothing about this ordering moved.

    PREFERRING COPIES OUTSIDE THE RUN BEING EMITTED WAS THE OTHER CANDIDATE AND IT OVER-SENDS.
    It makes the committed set a function of which run is emitting, so two runs holding one
    SKU each exclude themselves and the same claimed copies are subtracted from neither —
    a global quantity answered by a run-scoped view, which is D59's defect exactly. Measured
    on the same store: **83 copies across 61 SKUs offered past what exists to offer**, the
    same register as the 78-rows-across-61-SKUs projection D59 itself published.

    Which is why "any non-zero count commits every copy" is not the rule. Seven copies with
    two staged would commit all seven, `add_to_quantity` would clamp to zero, and the SKU
    would never refill to the D7 cap again. Counting them gives the right answer: two
    committed, room for two more, exactly what the per-position model computed before it was
    removed.

    `live` USED TO BE DELIBERATELY EXCLUDED HERE, ON A REASON THAT WAS RIGHT ABOUT THE
    ARITHMETIC AND WRONG ABOUT THE SET (D59). Adding the stored `live` count while
    `add_to_quantity` was separately subtracting `live_before` really would have subtracted
    the same copies twice — but the consequence of leaving it out was that no copy TCGplayer
    had actually LISTED was ever marked as held, so once `pushed` and `staged` reached zero
    a SKU with fewer copies than the cap had its own live copies handed straight back to the
    import file. One copy, live, nothing pending: `room = 4 - 1 - 0` offered it again.
    Measured on the owner's store, one `reconcile` away: 83 rows across 64 SKUs.

    `live` is counted ONCE now, inside `_copies_out`, and this spends that same number.
    """
    keys = set()
    for sku, out in copies_out.items():
        for card in _oldest_first(inventory.copies_on_hand(sku))[:out]:
            keys.add(card.key)
    return keys


def export_for(run: runs.Run, override: Optional[str]) -> Path:
    """The export this run joins against. `--export` sets it; the manifest remembers it."""
    if override:
        return Path(override)
    recorded = run.export_path
    if recorded is None:
        raise runs.RunError(
            "this run has no export recorded — pass --export <filtered-export.csv> "
            "(join records it in the manifest, so later commands do not need it again)"
        )
    return recorded


@dataclass(frozen=True)
class ExportPlan:
    """Which file answers for which game, decided by the files' own `Product Line` cells.

    `by_game` maps every game this run's cards claim to exactly one export file, in
    registry order. `notes` is anything worth saying that is not worth stopping for — a
    passed file that no card in the run needs is named there, because a file accepted and
    then ignored in silence is the same shape as a card silently dropped.
    """

    by_game: "OrderedDict[str, Path]"
    notes: Tuple[str, ...] = ()


def _games_needed(run: runs.Run) -> "OrderedDict[str, List[str]]":
    """game -> position labels, for every card this run will hand to a catalog.

    THE SAME RESOLUTION `load` APPLIES, source for source — the run's own record, then the
    live inventory record, then the default-game backfill — so that the pre-flight check
    and the join can never disagree about which games a run holds. Cards that never reach
    a catalog claim no export: a card with no position or no identification is a pre-join
    failure, and a game with `catalogued: False` is held out by design. An UNREGISTERED
    game string raises here exactly as it would in `load` — a typo'd game is a loud stop,
    never a quiet bucket.
    """
    # Positions are not read here beyond the box number, and `load` realigns them a moment
    # later — so this reads the payload raw rather than paying for the photo digests twice.
    payload = run.read_identifications()
    inventory = Store().read().inventory
    # D36 (amended) — BEFORE the loop reads a record out of the store at this run's keys. A
    # box whose number was deleted and reused since this run is somebody else's drawer, and
    # the `held.game` fallback below would read a foreign card's game as this card's — which
    # is how the first refusal to fire named 53 riftbound cards in a Pokemon run.
    refuse_reallocated(payload, inventory, run)
    held_cards = inventory.cards
    # The same coordinates `load` renders in, off the same store, so a refusal names cards
    # by the numbers the operator will see on the screen they go looking on (D58).
    views = box_views(inventory)
    needed: "OrderedDict[str, List[str]]" = OrderedDict()
    for key, record in sorted((payload.get("cards") or {}).items()):
        box, index = record.get("box"), record.get("index")
        if box is None or index is None or not record.get("identification"):
            continue
        held = held_cards.get(key)
        # The store rung reads a live record at this run's RAW key, and it is safe against
        # a reused box number only because `refuse_reallocated` fired above. Residual, and
        # pre-existing: a pre-D21 record with no `game` in a box that had a mid-box delete
        # reads its NEIGHBOUR's game here, since this pass deliberately skips `realign`.
        game = (
            record.get("game")
            or (held.game if held is not None else None)
            or games.DEFAULT_GAME
        )
        if not games.is_catalogued(game):
            continue
        # `place_text`, not the bare label: a refusal names cards so the operator can find
        # them, and a pooled game's cards are named by the pooled fact and their key — the
        # label is the one string the pooled ruling says may never be printed for them.
        needed.setdefault(str(game), []).append(
            join.place_text(
                str(game), views.get(int(box), join.BoxView()).at(box, index)
            )
        )
    # Registry order, so refusals and reports list games the way every picker does.
    return OrderedDict(
        (game, needed[game]) for game in games.keys() if game in needed  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
    )


def _refuse_uncovered(
    needed: "OrderedDict[str, List[str]]", covered: Sequence[str]
) -> None:
    """The game-with-no-export refusal (D25): exit 1, write nothing, name the cards."""
    missing = [game for game in needed if game not in covered]
    if not missing:
        return
    lines: List[str] = []
    for game in missing:
        positions = needed[game]
        lines.append(
            f"REFUSING: this run holds {len(positions)} {game} card(s) and no export "
            f"covers that game."
        )
        lines += [f"    {label}" for label in positions[:8]]
        if len(positions) > 8:
            lines.append(f"    ... and {len(positions) - 8} more")
    lines.append(
        "Every game in a run joins against its own Filtered CSV export — pass one "
        "--export per game; each file says which game it prices through its own "
        "Product Line column."
    )
    # The controls named are `app/src/BoxBrowse.tsx`'s `Correct claims` on a card and
    # `app/src/BoxOps.tsx`'s `Set claims` on the box operations panel; both open
    # `ClaimEditor`, whose `Game` picker is the D21 claim. The route they post to is not the
    # remedy — this used to send the operator to `PUT /inventory/<box>/<index>` by hand.
    lines.append(
        "If a card's game claim is wrong, correct it on #/inventory: open the card and "
        "press Correct claims, then pick the Game, or Set claims on the box operations "
        "panel for many cards at once. Then join again."
    )
    lines.append("Nothing was joined, nothing was written, and no queue was touched.")
    raise runs.RunError("\n".join(lines))


def games_claimed(export: tcgcsv.Export) -> Tuple[str, ...]:
    """Which registered games this file's `Product Line` cells claim, in registry order.

    THE MAPPING `exports_for` DECIDES ON, EXTRACTED SO IT HAS ONE OWNER. D25's rule is that a
    file answers for its games off its own cells and never off its filename, and this is that
    rule as four lines. It is public because a second caller arrived: `server/pipeline_routes.py`
    has to know which games a freshly fetched export answers for BEFORE it can compose the
    list `exports_for` then rules on — which of the run's previously recorded exports are
    still needed, and which this file replaces. A private copy there would be two answers to
    "which game is this file", disagreeing at exactly the moment a run joined the wrong
    catalog.

    A game whose registry entry carries `product_line: None` (D22's `misc`) can never match,
    because `None` is not a `str` — which is the whole reason that field is None rather than
    the empty string a row could actually carry.
    """
    lines = tcgcsv.product_lines(export)
    return tuple(
        game
        for game in games.keys()  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
        if isinstance(games.get(game)["product_line"], str)
        and games.get(game)["product_line"] in lines
    )


def _by_recorded_digest(run: runs.Run, missing: Path) -> Optional[Path]:
    """The file this run recorded, found by its DIGEST under `inventory/.exports/`.

    NEVER A GUESS AND NEVER A SUBSTITUTE (D166). It answers only with a file
    whose FULL sha256 equals the one the manifest recorded for this exact path, so it cannot
    quietly join a run against a newer reading — which is the whole hazard of exports moving
    into a directory several runs share. A run that finds nothing carrying its digest refuses
    exactly as before; this recovers the file, it does not choose one.

    WHAT IT IS FOR: the manifest's `path` is the only link from a run to its export now that
    the file is not inside the run, and a path is the half of that record which can go stale.
    The digest is the half that cannot.
    """
    recorded = run.manifest.get("exports")
    if not isinstance(recorded, dict):
        return None
    wanted = next(
        (
            str(source.get("sha256") or "")
            for source in recorded.values()
            if isinstance(source, dict) and Path(str(source.get("path") or "")) == missing
        ),
        "",
    )
    if len(wanted) != 64:
        return None
    root = files.inventory_dir() / files.EXPORTS_DIRNAME
    if not root.is_dir():
        return None
    for candidate in sorted(root.glob(f"*/*-{wanted[:8]}.csv")):
        if candidate.is_file() and runs.sha256_of(candidate) == wanted:
            return candidate
    return None


def exports_for(
    run: runs.Run, overrides: Optional[Sequence[str]]
) -> ExportPlan:
    """Map export files to games off their `Product Line` cells, or refuse — before any
    catalog is built.

    NEVER FROM A FILENAME (D25). Each file is read and answers for the games whose
    `product_line` its rows carry; the mapping is then inverted to game -> file, which
    must be exactly one. Three refusals, all `RunError`, all before anything is joined,
    written, or queued, and none of them a prompt:

      - a file whose `Product Line` cells match no registered game — the wrong file, and
        silently ignoring it would be a dropped input;
      - two files claiming one game — there is no rule that could pick between them that
        is not a guess;
      - a game present in the run with no export — named card by card, with the
        correction route for a mis-claimed game.

    With no `--export` at all, the manifest's recorded mapping seeds the file list (the
    scalar-era manifest reads as the default game's file), and the files are re-read
    rather than trusted: the mapping is re-derived from what the files say TODAY, which is
    the property that makes a swapped-out file fail loudly instead of joining quietly.
    """
    if overrides:
        paths = [Path(p) for p in overrides]
    else:
        recorded = run.exports_by_game
        if not recorded:
            raise runs.RunError(
                "this run has no export recorded — pass --export <filtered-export.csv> "
                "(join records it in the manifest, so later commands do not need it again)"
            )
        paths = list(recorded.values())
    # One reading per distinct file: two games may share one file, and the same path
    # passed twice is one file, not two claimants.
    distinct: List[Path] = []
    for path in paths:
        if path not in distinct:
            distinct.append(path)

    # THE RUN IS JUDGED BEFORE ITS FILES. `_games_needed` opens the store and refuses a run
    # over a box whose number was deleted and reused (D36 amended), and it does so here,
    # ahead of the file loop, on purpose: measured on `2026-08-22-box1-03`, whose recorded
    # export is gone from `~/Downloads`, `export not found` fired first and sent the
    # operator to fetch a fresh export for a drawer that no longer exists. A refusal about
    # the run itself is terminal; a refusal about its inputs asks for work, and that work is
    # wasted on a dead run. `read_identifications` refuses a run never identified the same
    # way, and that too is the run's own fault before any file's.
    needed = _games_needed(run)
    claimed_by: Dict[str, List[Path]] = {}
    lines_of: Dict[Path, Tuple[str, ...]] = {}
    for index, path in enumerate(distinct):
        if not path.is_file():
            # THE DIGEST IS WHAT SURVIVES A MOVE, AND RECORDING IT IS WHY (D166).
            # A fetched export lives in `inventory/.exports/<game>/` now rather than inside the
            # run, so the manifest's path is the only link back to it — and a shared directory
            # is exactly where a path CAN change under a run that a run-local copy never
            # could. The manifest records `sha256` beside `path` for this, and the file's own
            # NAME carries the first 32 bits of it, so the file is found by the record rather
            # than by a guess, and the full digest is verified before it is used.
            found = None if overrides else _by_recorded_digest(run, path)
            if found is not None:
                distinct[index] = path = found
            else:
                recorded = (
                    ""
                    if overrides
                    else " — this run's manifest recorded it there and it has since moved or "
                    "been deleted, and no file carrying its recorded digest is under "
                    "inventory/.exports/"
                )
                raise runs.RunError(
                    f"export not found: {path}{recorded}. Pass --export "
                    f"<filtered-export.csv> to name another file, or fetch a fresh one on "
                    f"#/runs (Fetch from TCGplayer), which writes it into "
                    f"inventory/.exports/<game>/ — kept, never swept, and shared by every "
                    f"run that joins against it.\n"
                    f"Nothing was joined, nothing was written, and no queue was touched."
                )
        export = tcgcsv.read_export(path)
        lines = tcgcsv.product_lines(export)
        lines_of[path] = lines
        matched = list(games_claimed(export))
        if not matched:
            known = sorted(
                {
                    str(games.get(game)["product_line"])
                    for game in games.keys()  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
                    if isinstance(games.get(game)["product_line"], str)
                }
            )
            raise runs.RunError(
                f"REFUSING: {path} matches no registered game. Its Product Line "
                f"cells are: {', '.join(repr(v) for v in lines) or 'none'}; the "
                f"registered product lines are: {', '.join(repr(v) for v in known)}. "
                "This is the wrong file — nothing was joined, nothing was written, and "
                "no queue was touched."
            )
        for game in matched:
            claimed_by.setdefault(game, []).append(path)

    doubled = {
        game: paths for game, paths in claimed_by.items() if len(paths) > 1
    }
    if doubled:
        lines = ["REFUSING: more than one export claims the same game."]
        for game in (g for g in games.keys() if g in doubled):  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
            line = games.get(game)["product_line"]
            lines.append(f"  {game} (Product Line {line!r}):")
            lines += [f"    {path}" for path in doubled[game]]
        lines.append(
            "One file per game: there is no rule that could choose between two "
            "catalogs for one card that is not a guess. Drop one file, or export a "
            "single file that covers the game."
        )
        lines.append("Nothing was joined, nothing was written, and no queue was touched.")
        raise runs.RunError("\n".join(lines))

    _refuse_uncovered(needed, list(claimed_by))

    by_game: "OrderedDict[str, Path]" = OrderedDict(
        (game, claimed_by[game][0]) for game in games.keys() if game in needed  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
    )
    notes = tuple(
        f"note: {path} carries only {', '.join(repr(v) for v in lines_of[path])} and "
        f"this run holds no card of a game that claims it — the file is unused"
        for path in distinct
        if path not in set(by_game.values())
    )
    return ExportPlan(by_game=by_game, notes=notes)


# --------------------------------------------------------------- D36: the slot may have moved
#
# A RUN DIRECTORY IS IMMUTABLE AND THE STORE IS NOT, AND THAT IS THE WHOLE DEFECT.
# `cli/runs.py` makes a run an immutable input on purpose — it is what lets a batch outlive
# the server that started it (D33) and what makes a run an auditable record of what was
# submitted and billed. Nothing about that is wrong. What was wrong is that the run's POSITIONS
# were then trusted as truth.
#
# D10's ruling 1 lets a junk capture be deleted from the middle of a box, sliding every higher
# card down one slot. The store does that correctly and completely: records, photographs,
# sidecars and both queue files are all remapped, and a `renumbered` history event maps every
# old index to its new one. The run directory is not remapped, because it cannot be — it is a
# record of a past event.
#
# So re-joining a box that has been edited since it was identified paired every card with its
# NEIGHBOUR's slot, photograph and label. Found 2026-08-24 on box 2: card `2/7` had been
# deleted, 537 cards shifted, and a re-join wrote all 47 queue entries one position off — a
# review screen showing one card's name over another card's photograph. The owner's reading is
# the one this fix is built to:
#
#     "It should've gone away and autocorrected all the others too... I don't see how these
#      could've been disconnected."
#
# THE FIX IS THAT THE RUN NO LONGER OWNS THE SLOT NUMBER. It owns what the model said about a
# PHOTOGRAPH; the store owns which slot that photograph is in. `photo_sha256` is the join
# between them, it is on every run record whose photograph could be read — `cmd_identify` writes
# `None` where the image raised, which is the `blind` branch below — and it is the only binding
# that survives a
# renumber — a slot number is exactly what moved.
#
# MEASURED BEFORE IT WAS CHOSEN: box 2's 543 photographs are 997 MB and hash in 0.56s, to 543
# distinct digests with no collisions. Reading the photographs is affordable per join, and it
# is strictly better than trusting the store's identification cache, which is another derived
# copy that a future defect could leave stale in the same way.
#
# AND THE READ IS GONE, BECAUSE THE STORE STOPPED HOLDING A DERIVED COPY AND STARTED HOLDING
# THE NAME ITSELF (`D183`). `cards.cid` is the sha256 of
# the photograph, indexed and UNIQUE, and `store/photos.py` makes the path a pure function of
# it — so the map this section is built on is one indexed query per box instead of 997 MB of
# reads. The paragraph above is still the argument for reading the PHOTOGRAPHS rather than the
# identification cache, and it is not retired by this: what replaced the hashing is not
# another derived copy of a position, it is the card's own name, and the photograph is still
# what decides — every row is put to `photos.find`, so a card whose photograph is not on disk
# is absent from the map exactly as it was when the map was a directory listing. That is what
# keeps a D89 reclaim reading as `departed` and a box whose files have been deleted reading as
# `unverified`.
#
# IT CORRECTS SILENTLY ONLY WHEN IT IS CERTAIN, AND REFUSES OTHERWISE. A digest that matches no
# photograph on disk, or more than one, is not a slot that moved — it is a question, and
# `CLAUDE.md` forbids guessing an identity. A run whose every record already sits at its own
# photograph returns untouched, so a healthy run joins byte-for-byte as it always did.


# Which mechanism answered for a box, reported rather than picked silently — see
# `PhotoIndex.source`. Two sources for one question is the shape that goes wrong quietly, so
# the answer says which one it came from and a caller with a `say` prints it.
DIGESTS_FROM_STORE = "store"
DIGESTS_FROM_PHOTOGRAPHS = "photographs"
DIGESTS_FROM_NOTHING = "nothing"


class PhotoIndex(NamedTuple):
    """Where each of this run's photographs is, and which mechanism said so.

    `source` is `store`, `photographs`, `nothing`, or several of those joined with `+` when
    the boxes disagreed. IT IS A FIELD RATHER THAN A LOG LINE because nothing in `realign`'s
    call path has a `say` — the join's reporter is `cli/cmd_join.py`, three returns up — and a
    function that silently chooses between two sources of truth is exactly the thing this
    repo keeps paying for. A caller that CAN speak prints it (`cli/cmd_rescue.py`), and
    `realign` puts it in every refusal it raises, which is the only sentence it gets to write.
    """

    at: Dict[str, str]
    twice: set
    source: str


def _photo_digests(
    boxes, inventory: Optional[master.Inventory] = None
) -> PhotoIndex:
    """(sha256 -> position key, digests seen more than once, which source answered).

    THE MAP IS A COLUMN NOW, NOT 997 MB OF READS. `cards.cid` IS the photograph's digest —
    frozen at the birth of the record, indexed and UNIQUE
    (`D183`) — so the question this function asks is one
    indexed query per box. It used to glob `captures/cards/box<N>/*.jpg`, `int()` each stem
    and hash every file: box 2's 543 photographs at 997 MB and 0.56 s, per box, per join. Two
    separate things retire that: after the relocation the legacy directory is EMPTY, and
    `int(photo.stem)` raises on every name in the store that replaced it.

    IT IS KEYED ON `digest_of(cid)` AND NOT ON THE CID, AND THE DIFFERENCE IS A REFUSAL. A run
    record's `photo_sha256` is the sha256 of the bytes; a card whose photograph is
    byte-identical to an earlier card's is named `<digest>-2`, so both project to one digest
    and BOTH have to be reported — which is the same `twice` refusal two photographs carrying
    one digest always produced, arriving through the name instead of through the disk. That
    population is 0 today (2,535 distinct digests, 0 duplicate groups), which is exactly why
    it has to be written down rather than discovered. A `moved:` tombstone and a `nophoto:`
    name project to None and are skipped: neither names a photograph, and a tombstone's digest
    is already on the live row the card moved to.

    EVERY ROW IS STILL PUT TO THE PHOTOGRAPH, WHICH IS WHAT KEEPS D36's VERDICTS THE ONES IT
    MEASURED. `photos.find` is one or two `stat`s — the card's name, then the legacy address
    while `photos_relocated` is unset — and a row whose file is at neither is left OUT of the
    map, exactly as a directory listing left it out. That is not tidiness: it is what makes a
    D89 reclaim read as `departed` (sold, photograph deliberately deleted, record and digest
    kept) and a box whose files have gone read as `unverified` rather than as 53 departed
    cards. Answering from the rows alone would invert both.

    THE PHOTOGRAPHS ARE THE FALLBACK, PER BOX, AND ONLY WHILE THEY CAN BE. A box the store
    names nothing for is read the old way — that is a memory-backed inventory, a home holding
    photographs and no store, and T7's own fixtures, all of which are real callers — unless
    `photos_relocated` says the legacy address is retired, in which case there is nothing
    there to read and the answer is `nothing` rather than a silent empty.

    WHAT THE STORE CANNOT SEE IS AN ORPHAN PHOTOGRAPH: a file at a slot no record claims. The
    listing found it and a column cannot. It is a defect state rather than a normal one, and
    the honest outcome changes from `moved` onto a slot holding no card to `departed`, which
    is the better of the two answers — but it is a change, and it is written here rather than
    discovered.
    """
    inventory = _digest_inventory() if inventory is None else inventory
    relocated = bool(inventory is not None and inventory.photos_relocated)
    home = files.home()

    found: Dict[str, str] = {}
    twice: set = set()

    def remember(digest: str, key: str) -> None:
        # THE FIRST SIGHTING STAYS IN `found` AND THE DIGEST GOES IN `twice`, which is the
        # glob's own behaviour kept verbatim: `realign` checks `twice` before it checks
        # `at`, so a contested digest refuses the run rather than resolving to whichever
        # row was walked first.
        if digest in found:
            twice.add(digest)
            return
        found[digest] = key

    sources: List[str] = []
    for box in sorted(boxes):
        named = _named_cards_in(inventory, box)
        if named:
            sources.append(DIGESTS_FROM_STORE)
            for key, cid, index in named:
                if photos.find(cid, box, index, relocated=relocated, home=home) is None:
                    continue
                remember(photos.digest_of(cid), key)
            continue
        if relocated:
            sources.append(DIGESTS_FROM_NOTHING)
            continue
        sources.append(DIGESTS_FROM_PHOTOGRAPHS)
        directory = photos.legacy_box_dir(box, home)
        if not directory.is_dir():
            continue
        for photo in sorted(directory.glob("*.jpg")):
            try:
                index = int(photo.stem)
            except ValueError:
                # Not a slot filename. A cid-named file is the reason this branch is now
                # load-bearing rather than defensive, and `identify/sidecar.py`'s guard is
                # the same refusal one layer out: a digest is full of digits, so anything
                # that recovers a position from one of these names invents a plausible
                # wrong answer.
                continue
            digest = hashlib.sha256(photo.read_bytes()).hexdigest()
            remember(digest, master.position_key(int(box), index))

    return PhotoIndex(found, twice, "+".join(sorted(set(sources))) or DIGESTS_FROM_NOTHING)


def _digest_inventory() -> Optional[master.Inventory]:
    """The store's own records, or None where there is no store to read.

    NONE IS A REAL ANSWER AND NOT AN ERROR TO SWALLOW: `realign` runs against a home that is
    a directory of photographs in T7's fixtures and in a hand-built payload, and it ran
    against one long before the store had a `cid` column at all. So a store that will not
    open leaves this function's caller on the photographs, which is the behaviour it had
    before the column existed — the safe direction, because the alternative is a join that
    refuses over a store the join itself never needed.
    """
    try:
        return Store().read().inventory
    except Exception:  # noqa: BLE001 — any unreadable store means "read the photographs"
        return None


def _named_cards_in(
    inventory: Optional[master.Inventory], box
) -> List[Tuple[str, str, Optional[int]]]:
    """`(position key, cid, index)` for every card in one box whose cid names a photograph.

    `select` rather than `where`: this wants two columns off each row in one box and builds no
    `Card` for any of them, which is the cost `store/rows.py` says an indexed query should be.
    The KEY is the store's own row key, so it is already the `box/index` string this map's
    consumers compare against `held_cards`.
    """
    if inventory is None:
        return []
    out: List[Tuple[str, str, Optional[int]]] = []
    for key, (cid, index) in inventory.cards.select(("cid", "idx"), box=int(box)):
        if photos.digest_of(cid) is None:
            continue
        out.append((str(key), str(cid), index))
    return out


def realign(
    payload: dict, inventory: Optional[master.Inventory] = None
) -> Tuple[dict, Dict[str, str], List[str], List[int]]:
    """Re-bind a run's records to the slots their photographs occupy now (D36).

    Returns `(payload, moved, departed, unverified_boxes)`. The first three are empty and the
    payload is the identical object when nothing has shifted, which is what keeps a healthy
    run's join byte-for-byte unchanged.

    IT IS LOAD-BEARING FOR EVERY RUN WRITTEN BEFORE THE PHOTOGRAPH MOVED OUT OF THE ADDRESS,
    AND DEAD FOR EVERY RUN WRITTEN AFTER (`D183` §0.7).
    Its whole job is re-binding a remembered `(box, index)` to the slot that record's
    `photo_sha256` sits at now; under the layout that names a photograph by the card, a run
    record's digest IS the photograph's filename and there is no binding to repair, because
    nothing bound the bytes to a position in the first place. What keeps it here is measured
    rather than assumed: **13 run directories, 3,728 records, 701 of them binding by digest to
    a different position key than the one they name**, plus 88 whose photograph is gone.
    `#/pricing?run=<n>` and "Join again" both re-read one of those old receipts against
    today's store, and a cid cannot reach backwards into an immutable file written before it
    existed — so for those 3,728 records this repair layer is the only thing that makes the
    answer right. THE CONDITION UNDER WHICH IT CAN GO is that no run directory predating the
    change is still readable. **That is not a date anybody can name, so it is not scheduled**,
    and nothing here is deprecated on a guess.

    REASONED PER BOX, BECAUSE ABSENCE OF PHOTOGRAPHS IS NOT EVIDENCE OF ABSENT CARDS. The
    first draft of this reasoned over the whole run and declared all 53 of box 1's cards
    departed — because box 1's photographs have been deleted from disk while its records live
    on. That inverts the meaning of the check: a missing photograph tells you the PHOTOGRAPH
    is missing, and only a box whose other photographs are present can tell you that one
    particular card has left it.

    So a box whose photographs are entirely absent is `unverified`: its records pass through
    untouched, exactly as before this function existed, and the report says the slots were not
    checked. A box whose photographs ARE present is checked, and there the three outcomes are
    real and distinct:

      moved      the digest is on disk at a different slot. Re-bound, and reported.
      departed   the digest is on no photograph in a box whose other photographs are there.
                 The card has left — deleted mid-box (D10 ruling 1) or retired. Skipped
                 rather than joined, because there is nothing to join it to, and NAMED in the
                 report: `CLAUDE.md` forbids dropping a card silently, not dropping one.
      ambiguous  the digest is on two photographs. That is a question, not a slot, and
                 `CLAUDE.md` forbids guessing an identity. Refuses the whole run.

    A record with no digest cannot be checked. Harmless while nothing in its box has moved,
    unresolvable once something has, so it refuses only in the second case.

    `inventory` IS AN OPTIONAL SNAPSHOT AND NOT A NEW DEPENDENCY. Since the photographs are
    named by their cards this function's map comes off `cards.cid`, which means one store READ
    where there used to be none — so a caller already holding a snapshot hands it in and pays
    for one. `load` deliberately does not: it takes its snapshot AFTER the exports are read,
    and moving that read earlier to save a connection would change the moment every figure in
    the join is measured at. A snapshot read takes no lock (WAL), so the second one is a
    connection rather than a wait.
    """
    cards = payload.get("cards") or {}
    by_box: Dict[int, Dict[str, dict]] = {}
    for key, record in cards.items():
        if isinstance(record, dict) and record.get("box") is not None:
            by_box.setdefault(int(record["box"]), {})[key] = record

    moved: Dict[str, str] = {}
    departed: List[str] = []
    ambiguous: List[str] = []
    blind: List[str] = []
    unverified: List[int] = []
    # ONE STORE READ FOR THE WHOLE RUN, not one per box. `_photo_digests` opens its own when
    # it is handed nothing, and this loop calls it once per box — which is how a 13-box run
    # would have opened thirteen connections to answer one question.
    if inventory is None and by_box:
        inventory = _digest_inventory()
    sources: List[str] = []

    for box, records in sorted(by_box.items()):
        at, twice, source = _photo_digests([box], inventory)
        sources.append(source)
        verifiable = {
            key: rec["photo_sha256"] for key, rec in records.items() if rec.get("photo_sha256")
        }
        # Nothing to compare against, or nothing that matches: the photographs are gone, not
        # the cards. Leave this box exactly as the run recorded it.
        if not at or not verifiable or not any(d in at for d in verifiable.values()):
            unverified.append(box)
            continue
        blind += sorted(set(records) - set(verifiable))
        for key, digest in sorted(verifiable.items()):
            if digest in twice:
                ambiguous.append(key)
            elif digest not in at:
                departed.append(key)
            elif at[digest] != key:
                moved[key] = at[digest]

    if not moved and not departed and not ambiguous:
        return payload, {}, [], unverified

    # TWO RECORDS THAT LAND ON ONE SLOT ARE A QUESTION, NOT A SLOT — the same rule the
    # `twice` check above applies to the DISK, applied to the PAYLOAD, and it was missing.
    # `twice` catches two photographs carrying one digest; nothing caught two RECORDS
    # carrying one digest, which resolve to the same position through `at` and then collide
    # in `rebuilt` — where the second write wins and the first card leaves the run with no
    # entry anywhere and nothing printed. Measured on a two-card payload: two cards in, one
    # card out, `departed` empty. That is a silent drop inside the function written to stop
    # one, and `CLAUDE.md` forbids it in as many words.
    gone = set(departed)
    landing: Dict[str, List[str]] = {}
    for key in cards:
        if key in gone:
            continue
        landing.setdefault(moved.get(key, key), []).append(key)
    collided = sorted(slot for slot, keys in landing.items() if len(keys) > 1)

    if ambiguous or collided or (blind and moved):
        lines = ["this run cannot be placed against the box as it stands now. Nothing was joined.", ""]
        if collided:
            lines += [
                "These slots are claimed by more than one record, so which card is at each "
                "is a question rather than a fact: " + ", ".join(collided[:8])
                + (" ..." if len(collided) > 8 else ""),
                "",
            ]
        if ambiguous:
            lines += [
                "These records' photographs appear at more than one slot, so which card they "
                "are is a question rather than a fact: " + ", ".join(ambiguous[:8])
                + (" ..." if len(ambiguous) > 8 else ""),
                "",
            ]
        if blind and moved:
            lines += [
                f"{len(moved)} card(s) have moved slot since they were identified, and these "
                "records predate the photo digest, so they cannot be checked at all: "
                + ", ".join(blind[:8]) + (" ..." if len(blind) > 8 else ""),
                "",
            ]
        lines.append("Re-identify this box and join again.")
        # WHICH SOURCE ANSWERED, ON THE ONE SENTENCE THIS FUNCTION GETS TO WRITE. A refusal
        # that does not say where its evidence came from sends the operator to re-identify a
        # box when the real answer might be that the store named nothing and the photographs
        # were read instead — two different problems with one message.
        lines.append(
            f"(slots read from: {'+'.join(sorted(set(sources))) or DIGESTS_FROM_NOTHING})"
        )
        raise runs.RunError("\n".join(lines))

    # Rebuilt rather than mutated: `read_identifications` hands back the run's own parsed
    # payload, and a caller that reads it again must not find it silently rewritten. The run
    # directory on disk is never touched — its record of what was submitted stays true.
    rebound = dict(payload)
    rebuilt = {}
    for key, record in cards.items():
        if key in gone:
            continue
        now = moved.get(key, key)
        slot = now.split("/")
        # A KEY THAT IS NOT A POSITION PASSES THROUGH UNTOUCHED, and it is not hypothetical:
        # `identify/sidecar.py` keys a capture with no position as `file:<name>`, which is
        # the documented shape for a directory of photographs with no sidecars. Such a record
        # is never in `by_box`, so it can never be in `moved` — but this loop walks EVERY
        # card, so one stray positionless key used to take the whole run down with an
        # unhandled `ValueError` the moment anything else in its box had shifted, and take
        # `join` and `emit` down with it permanently. There is nothing to re-bind here (no
        # slot moved, because it never had one), so the honest action is to leave it exactly
        # as the run recorded it.
        if len(slot) != 2 or not (slot[0].isdigit() and slot[1].isdigit()):
            rebuilt[now] = record
            continue
        box, index = slot
        moved_record = {**record, "box": int(box), "index": int(index)}
        # AND THE PHOTO PATH, WHICH IS THE FIELD THIS FIX FIRST FORGOT. `box` and `index`
        # decide the position LABEL, but `cli/resolve.py:queue_entry` carries `record["photo"]`
        # onto the queue entry verbatim and the review screen renders exactly that file. A
        # rebound record keeping its old path points at the slot's PREVIOUS occupant — so the
        # screen drew one card's name over another card's photograph, which is the identical
        # defect this whole function exists to prevent, surviving one field deeper.
        #
        # Found by looking at the screen: the entry read `Mewtwo ex` and rendered `0096.jpg`,
        # a photograph of something else. Renaming only the FILENAME, so a mirror or an
        # overridden captures root moves with it and nothing here has to know where photos live.
        #
        # AND IT RENAMES A SLOT FILENAME ONLY, WHICH IS THE OTHER HALF OF THE SAME RULE.
        # A photograph stored under the CARD's name has nothing to do with the slot: the path
        # is a pure function of `cid` (`store/photos.py`), so rewriting `6b1cf2fd….jpg` to
        # `0002.jpg` would replace a path that is correct with one that names no file at all —
        # the same defect as the one above, arriving from the other direction. The guard is
        # inert for every run this function is load-bearing for: all 3,728 records written
        # before the layout moved carry a `NNNN.jpg` name, and `identify/sidecar.py`'s
        # `_CID_STEM_RE` is the same shape refusing the same thing one layer out.
        photo = record.get("photo")
        if isinstance(photo, str) and photo:
            source = PurePosixPath(photo)
            if not photos.is_photo_cid(source.stem):
                moved_record["photo"] = str(
                    source.with_name(f"{int(index):04d}{source.suffix}")
                )
        rebuilt[now] = moved_record
    rebound["cards"] = rebuilt
    return rebound, moved, departed, unverified


def refuse_reallocated(payload: dict, inventory: master.Inventory, run: runs.Run) -> None:
    """Refuse a run over a box whose number was deleted and reused since (D36, amended).

    THE CASE `realign` CANNOT SEE, BECAUSE IT ASKS ONLY WHICH SLOT A PHOTOGRAPH IS AT AND
    NEVER WHOSE DRAWER IT IS. Box 1 was deleted on
    2026-08-25 with 53 Pokemon cards and its number was reused on 2026-08-29 for 133
    Riftbound cards — `next_box_number` allocates the lowest free integer (D20 amended) —
    and `2026-08-22-box1-03` still describes the old drawer. `realign` compares the run's
    digests against the photographs the box holds now — read off `cards.cid` and put to
    `photos.find`, since the photograph moved under the card's own name, and by hashing the
    files themselves before that: none of the run's digests are among the new box's
    photographs, so it answers `unverified` and passes the run's keys through, and
    everything after it then reads the CURRENT box's records at those keys — `held.game`
    stands in for a record with no game, `answered` adopts a foreign card's SKU and
    condition, `committed` adopts a foreign card's sold state, and `box_views` draws labels
    from the wrong box. The refusal that fired first said *"this run holds 53 riftbound
    card(s) and no export covers that game"* and sent the operator to change the game on
    live records that were never this run's.

    THE RULE IS THE STORE'S OWN RECORD, `Inventory.box_disowns_run`: the registry entry was
    made AFTER the run started AND the box's cards came from somewhere else. It is the rule
    `server/pipeline_routes.py:_box_name_for` has withheld the box's NAME on since D56,
    shared from `store/master.py:box_disowns_run` rather than copied, so the screen and the
    command decide one case one way.

    `unverified` IS DELIBERATELY NOT AN INPUT. The store's record decides this case whatever
    the photographs say: `do_delete_box` deletes a box's cards with its registry entry, so a
    box `realign` CAN verify — one holding this run's photographs — cannot satisfy the rule,
    and the honest `unverified` case (photographs missing, box unchanged) fails the time
    test or the membership test and passes through exactly as before. Coupling the two would
    make a refusal depend on which photographs happen to be on disk.

    CALLED TWICE ON ONE STORE READ EACH, AND WHICHEVER RUNS FIRST RAISES: `_games_needed`
    on the `exports_for` path, before its own store rung, and `load` right after its
    snapshot, for a caller handing a mapping straight in. One refusal, not three. Raises
    `RunError` before anything is joined, written or queued; returns None otherwise.
    """
    boxes = sorted(
        {
            int(record["box"])
            for record in (payload.get("cards") or {}).values()
            if isinstance(record, dict) and record.get("box") is not None
        }
    )
    # THE RUN'S OWN RECORD OF WHICH DRAWER IT WAS OVER, WHERE IT HAS ONE (D145).
    # A run started after that landed carries its box's true index in its scope block, which
    # settles this case rather than inferring it. Every run on the owner's machine predates
    # the field and takes the rule below unchanged — so this narrows nothing and can only
    # turn an abstention into a refusal.
    scope = run.manifest.get("scope")
    scope_bid = scope.get("bid") if isinstance(scope, dict) else None
    if not isinstance(scope_bid, int) or isinstance(scope_bid, bool):
        scope_bid = None
    for box in boxes:
        sentence = inventory.box_disowns_run(box, run.name, run.created_at, bid=scope_bid)
        if sentence is None:
            continue
        raise runs.RunError(
            f"REFUSING: {sentence}. This run describes a drawer that no longer exists and "
            f"cannot be joined.\n"
            f"Re-identify the box as it is now (`pkmnscan identify`, or Identify on #/runs) "
            f"if that is what you want joined; this run's directory is a record of the old "
            f"drawer and is left as it is.\n"
            f"Nothing was joined, nothing was written, and no queue was touched."
        )


def paperwork_for(run: runs.Run) -> List[orders.PaperworkEntry]:
    """A run's `pricing.json`, read back as SKU -> the positions those copies are at NOW.

    THE BACKUP SOURCE FOR `pipeline/orders.py`, and it lives here rather than there because
    it does the one thing a pure resolver may not: it reads a run directory off disk and it
    hashes photographs. The resolver takes the ANSWER and never the lookup.

    WHY IT GOES THROUGH `realign` AND NOT STRAIGHT AT THE FILE. `pricing.json` stores
    position keys — `cli/cmd_join.py:_pricing_table` writes `{"box": .., "index": ..}` per
    matched SKU — and positions MOVE. A mid-box delete (D10 ruling 1) slides every higher
    index in the box down one, and the run directory is immutable by design, so its own
    slot numbers are exactly the thing that goes stale. That is D36 in full, and it is not
    hypothetical: a re-join of box 2 wrote all 47 queue entries one position off, every one
    carrying the right read with its neighbour's photograph, because a run's positions were
    read as truth. Reading this file without realigning it would resurrect that defect on
    the one screen whose whole job is sending a person to a physical slot.

    So the run's own identifications are realigned first — that is what knows each record's
    `photo_sha256` and can therefore say where that photograph is today — and the mapping
    it produces is applied to the pricing table's keys. A position the realignment reports
    DEPARTED is dropped: there is no card there to walk to, and naming it would send
    somebody to the slot its successor now occupies.

    IT RAISES WHAT `realign` RAISES. An ambiguous digest or two records landing on one slot
    refuses the whole run rather than answering for part of it, which is that function's own
    contract and the right one here: paperwork nobody can place is not a weaker answer, it
    is a question.

    A RUN WITH NO PRICING TABLE ANSWERS NOTHING, WITHOUT COMPLAINT. `pricing.json` is
    written by `join` and by nothing else (D49), so a run that was identified and never
    joined legitimately has none — and the resolver's card-first pass does not need it.
    """
    table = files.read_json(run.path(runs.PRICING))
    if not isinstance(table, dict):
        return []

    # Realign the run's OWN records, then reuse the mapping. `moved` is old key -> new key
    # and `departed` names the records whose photograph is on no slot in a box whose other
    # photographs are present. A box realign could not check at all is `unverified`: its
    # records pass through as the run recorded them, which is the same answer this file
    # gave before realignment existed, and the honest one — a missing photograph tells you
    # the photograph is missing.
    try:
        payload = run.read_identifications()
    except runs.RunError:
        # No identifications to check the table against. The positions are then unverified
        # in exactly realign's sense, so they are passed through rather than discarded:
        # every consumer re-checks the card it lands on anyway.
        moved, gone = {}, set()
    else:
        _, moved, departed, _ = realign(payload)
        gone = set(departed)

    found: List[orders.PaperworkEntry] = []
    for row in table.get("skus") or []:
        if not isinstance(row, dict) or not row.get("sku"):
            continue
        places = []
        for position in row.get("positions") or []:
            if not isinstance(position, dict):
                continue
            box, index = position.get("box"), position.get("index")
            if box is None or index is None:
                continue
            key = master.position_key(int(box), int(index))
            if key in gone:
                continue
            places.append(moved.get(key, key))
        if places:
            found.append(
                orders.PaperworkEntry(
                    sku=str(row["sku"]), run=run.name, positions=tuple(places)
                )
            )
    return found


def load(
    run: runs.Run,
    exports: Union[str, Path, Mapping[str, Path]],
    *,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    review_below: str = routing.CONFIDENCE_LOW,
    live_cap: Optional[int] = None,
    threshold: Decimal = pricing.THRESHOLD,
    quantities: Optional[Mapping[str, int]] = None,
) -> Resolved:
    """Read the run, build one catalog per game, walk the ladder, route every card.

    `exports` is game -> file (an `ExportPlan.by_game`), or a single path — the shape
    every caller passed before D25, resolved through `exports_for` so the file answers for
    the games its own `Product Line` cells claim. Either way the coverage check runs
    BEFORE any catalog is built: a run that will refuse costs nothing and touches nothing.
    """
    if isinstance(exports, (str, Path)):
        mapping = exports_for(run, [str(exports)]).by_game
    else:
        mapping = OrderedDict(
            (game, Path(path)) for game, path in exports.items()
        )
    payload = run.read_identifications()
    # D36 — BEFORE anything reads a position out of this payload. A run directory is immutable
    # and the store is not, so the slot a card was identified at may not be the slot it is in
    # now. Matched by photograph, refused when uncertain, untouched when nothing has moved.
    payload, realigned, departed, unverified = realign(payload)

    # The store's settled identities, read off the live inventory. A record carries
    # `sku` + `condition` from exactly two writers — `do_review_answer` (a human chose the
    # row) and `cmd_emit`'s push (the pipeline chose it and wrote it into a file) — and in
    # both cases the identity is settled: re-walking the ladder against it can only re-raise
    # a question that already has an answer, which is how the first real run's sixteen
    # answered cards re-parked on every join. Both writers leave the card in `identified`;
    # the listing progress lives on the SKU now, which is what `_committed_keys` reads.
    # Read here rather than in the loop so the store is opened once.
    # THE EXPORTS, READ ONCE AND UP FRONT (D59). `parsed` used to fill lazily inside the join
    # loop, and `_copies_out` below needs every file's `Total Quantity` before the first card
    # is built. It costs nothing new: `exports_for` has already read each of these files to
    # map its `Product Line` cells, and `_refuse_uncovered` still runs before a single
    # catalog is cut, still touches nothing, and still refuses on the same grounds.
    parsed: Dict[Path, tcgcsv.Export] = {}
    # ONE `describe_source` PER DISTINCT FILE. It hashes the file, and it used to run once
    # per GAME, so two games sharing one export paid for it twice. Its `mtime` is the time
    # each reading of `Total Quantity` below was taken — re-read off the file here, exactly
    # as the seven-day warning reads it, rather than off the manifest's stored copy, which
    # would make a re-fetched file read as older than it is.
    sources: Dict[Path, Dict[str, object]] = {}
    for _path in mapping.values():
        if _path not in parsed:
            parsed[_path] = tcgcsv.read_export(_path)
            sources[_path] = runs.describe_source(_path)

    snapshot = Store().read()
    # D36 (amended) — the same refusal `_games_needed` raises on the `exports_for` path, as
    # the backstop for a caller handing a mapping straight in. Before `held_cards` is read:
    # every read below at this run's keys assumes the box is this run's drawer.
    refuse_reallocated(payload, snapshot.inventory, run)
    held_cards = snapshot.inventory.cards
    copies_out, live_now = _copies_out(
        snapshot.inventory,
        _live_by_sku(parsed, {p: str(src["mtime"]) for p, src in sources.items()}),
    )
    committed_keys = _committed_keys(snapshot.inventory, copies_out)
    # D58's label coordinates, off the same snapshot for the same reason — one read, and
    # every position this run renders counted against the box as it stands right now.
    views = box_views(snapshot.inventory)

    # Grouped by game as they are built: each game's cards walk their own catalog and
    # nobody else's, which is the partition D25 asks for. Within a game the payload's
    # sorted order is preserved, so a one-game run joins the identical card sequence it
    # always did.
    grouped: Dict[str, List[join.IdentifiedCard]] = {}
    failures: List[PreJoinFailure] = []
    not_joined: List[NotJoined] = []
    photos: Dict[str, Optional[str]] = {}

    for key, record in sorted((payload.get("cards") or {}).items()):
        identification = record.get("identification")
        box, index = record.get("box"), record.get("index")
        if box is not None and index is not None:
            photos[f"{int(box)}/{int(index)}"] = record.get("photo")

        held = held_cards.get(key)

        # D21's READ-SIDE BACKFILL, lifted out of the `IdentifiedCard` call below because
        # something has to branch on it before the card is built. Three sources in order:
        # what the run recorded, then the live record, then Pokemon.
        #
        # THE STORE IS THE SECOND SOURCE AND NOT THE FIRST, deliberately. A run is a
        # measurement of what the sidecars said when identify ran; the record is what the
        # card says now. Where they differ the run's own copy is the one that explains what
        # was submitted — the same reason `set_hint` comes off the run. The record covers the
        # case where the run's payload predates this field.
        #
        # RESOLVED ABOVE THE FAILURE BRANCHES, not merely above the card build, since the
        # pooled ruling reached the reports: a pre-join failure's line needs the game to
        # know whether a position label may be printed for it, and a pooled card that
        # failed identification is still a pooled card.
        #
        # The store rung is safe against a reused box number only because
        # `refuse_reallocated` fired above (D36 amended); `realign` cannot see that case.
        game = (
            record.get("game")
            or (held.game if held is not None else None)
            or games.DEFAULT_GAME
        )

        if box is None or index is None:
            failures.append(
                PreJoinFailure(
                    key=key,
                    photo=record.get("photo"),
                    reason=routing.NO_POSITION,
                    read=identification or {},
                    game=str(game),
                )
            )
            continue

        if not identification:
            failures.append(
                PreJoinFailure(
                    key=key,
                    photo=record.get("photo"),
                    reason=routing.IDENTIFICATION_FAILED,
                    box=box,
                    index=index,
                    read={"status": record.get("status"), "error": record.get("error")},
                    game=str(game),
                    view=views.get(int(box), join.BoxView()),
                )
            )
            continue

        # THE PARTITION D25 ASKS FOR, AND THE ONE `join.lookup_for` REFUSES WITHOUT. A game
        # with `catalogued: False` has no export to match against, so it is held out here —
        # identified, positioned, recorded, and never handed to a catalog. Without this a
        # single misc card raises `NotCatalogued` from inside `join_batch` and takes the whole
        # run's join down after the export has been read. See `NotJoined` for why these are
        # not filed as failures.
        #
        # AN UNREGISTERED GAME STRING IS NOT DIVERTED HERE, and that is not an oversight.
        # `games.is_catalogued` raises `UnknownGame` for it and `join.lookup_for` raises the
        # same thing by name a moment later — a loud stop on a typo'd or future game, which is
        # what `identify/sidecar.py` preserves the raw string FOR. Quietly routing it into
        # this bucket would make an unregistered game look like a settled one, which is the
        # exact collapse `pipeline/games.py` keeps `EmptyVocabulary` and `NotCatalogued` apart
        # to prevent.
        if not games.is_catalogued(game):
            not_joined.append(
                NotJoined(
                    key=key,
                    game=str(game),
                    photo=record.get("photo"),
                    box=int(box),
                    index=int(index),
                    read=dict(identification),
                )
            )
            continue

        number = (identification.get("number") or "").strip() or None
        total = (identification.get("printed_total") or "").strip() or None
        finish = identification.get("finish")
        # D3 RUNG 0 — a human's answer, and it is unchanged by any of the above. `answered`
        # reads the identity off the record and nothing else; it does not consult a state,
        # a count, or a stage, so nothing in the listing model can make an answer fall
        # through. That mattered enough to be worth restating: an answer that does not
        # outlive its question is not an answer, which is what sixteen re-parked cards cost.
        answered = held is not None and bool(held.sku) and bool(held.condition)
        # A copy TCGplayer already has, or already has pending. Sold is per-copy and stays
        # per-copy — a sold card is gone, whatever any count says — and since D26 so is
        # retired: both terminal states mean this physical copy has left inventory, and a
        # join that re-listed a retired copy would sell a card that is no longer in the
        # box. Everything else is a per-SKU quantity resolved into positions once, above.
        committed = held is not None and (
            held.state in master.TERMINAL_STATES or key in committed_keys
        )
        grouped.setdefault(str(game), []).append(
            join.IdentifiedCard(
                position=views.get(int(box), join.BoxView()).at(box, index),
                name=identification.get("name") or "",
                number=number,
                printed_total=total if number else None,
                # THROUGH A NORMALISER RATHER THAN RAW, since D3's amendment made this a
                # set: a run record carries a JSON array now and a bare string before that,
                # and `IdentifiedCard` is frozen. `_finish_claim` is `_rarity_claim`'s twin
                # a few arguments down and carries the argument for the string case.
                metadata_finish=_finish_claim(record.get("metadata_finish")),
                # Tested against THIS GAME's finishes, never against a literal tuple. The
                # enum has one home and a copy of it here cannot be kept in step with it:
                # a finish added there would fall out of a literal written here, land as
                # `None`, and route the card to review with nothing on screen saying why —
                # a silent drop, which is the one thing this pipeline may never do. The
                # test is still needed: an unknown string from the model is not a finish,
                # and `variant` raises `UnknownFinish` rather than guessing at one.
                #
                # THE HOME MOVED ON 2026-08-23 AND THIS LINE READ THE WRONG ONE. It tested
                # `variant.FINISHES`, which is Pokemon's three — so the model's `foil` on a
                # Riftbound card fell out of a whitelist that had nothing to do with that
                # game and landed as `None`, losing rung 3's cross-check for every card of
                # every non-Pokemon game. Exactly the silent drop the paragraph above
                # forbids, committed by the line the paragraph is attached to.
                detected_finish=_detected(finish, game),
                photo=record.get("photo"),
                set_hint=record.get("set_hint"),
                # Backfilled above, where the catalog partition needed it first. A GAME
                # STRING NOBODY REGISTERED IS CARRIED THROUGH UNCHANGED, not coerced:
                # `join.lookup_for` refuses it by name.
                game=game,
                # D23's stack claim, off the run record alone — no store fallback, the
                # same posture as `set_hint` and `metadata_finish` two arguments up: the
                # run is the record of what the sidecars claimed when identify ran.
                rarity_claim=_rarity_claim(record.get("rarity_claim")),
                confidence=identification.get("confidence"),
                answered_sku=held.sku if answered else None,
                answered_condition=held.condition if answered else None,
                committed=committed,
            )
        )

    # Registry order, the order every picker renders. The coverage backstop runs before
    # the first catalog is built — for a caller that came through `exports_for` it can
    # never fire, and for one that handed a mapping straight in it is the same refusal in
    # the same place.
    needed = OrderedDict(
        (game, grouped[game]) for game in games.keys() if game in grouped  # noqa: SIM118 — `games` is the pipeline.games MODULE; `.keys()` is a real function, not dict.keys()
    )
    _refuse_uncovered(
        OrderedDict(
            # `place_text` for the same reason `_games_needed` uses it: the refusal names
            # cards, and a pooled card is named by its pooled fact, never by a label.
            (game, [join.place_text(card.game, card.position) for card in game_cards])
            for game, game_cards in needed.items()
        ),
        list(mapping),
    )

    joins_out: "OrderedDict[str, GameJoin]" = OrderedDict()
    for game, game_cards in needed.items():
        path = mapping[game]
        file_export = parsed.get(path)
        if file_export is None:
            file_export = parsed[path] = tcgcsv.read_export(path)
            sources[path] = runs.describe_source(path)
        # Per game, never merged — see `GameJoin`. Two games sharing one file (pokemon
        # and pokemon_code) each cut their own catalog from the one reading.
        catalog = join.Catalog.from_export(file_export, game)
        report = join.join_batch(
            game_cards,
            catalog,
            live_cap=live_cap,
            # Per-SKU send quantities, keyed by SKU across every game (D7, amended 2026-09-11).
            quantities=quantities,
            # BOTH HALVES OF THE THRESHOLD, AND THEY ARE NOT THE SAME DECISION. The router
            # reads it to decide whether a low-confidence card is worth a human's attention
            # (D9 through `pipeline/routing.py`); the batch reads it to partition the matches
            # it keeps. One figure, two consumers, and a run priced against a threshold the
            # router did not see would queue by one cut-off and list by another.
            router=join.default_router(
                threshold=threshold, review_below=review_below
            ),
            rule=rule,
            basis=basis,
            copies_out=copies_out,
            threshold=threshold,
            live_now=live_now,
        )
        joins_out[game] = GameJoin(
            game=game,
            export=catalog.export,
            catalog=catalog,
            report=report,
            source=sources[path],
        )

    return Resolved(
        run=run,
        joins=joins_out,
        failures=failures,
        rule=pricing.Rule.parse(rule),
        basis=basis,
        threshold=pricing.check_threshold(threshold),
        not_joined=not_joined,
        photos=photos,
        realigned=realigned,
        departed=departed,
        unverified_boxes=unverified,
    )


# ------------------------------------------------------------------------ queue entries


def _candidate_rows(rows, name_matched: Sequence[str] = ()) -> List[Dict[str, object]]:
    """What the review screen shows beside the photo (D4): the rows this could be.

    `found_by` SAYS WHICH READING FOUND THE ROW, and only where that question has two
    answers. A `name_disputed` card's list holds both readings of one photograph — the rows
    the NAME found and the row the NUMBER found (`pipeline/join.py:name_alternatives`) — and
    a list of four rows with no provenance on them is a worse question than the one it
    replaced: the operator can see two cards but not which signal argued for which.

    ABSENT ON EVERY OTHER ENTRY, because a list with one provenance does not need it stated
    and stamping `number` on all of them would invite a screen to draw a badge on every row
    in the queue. `name_matched` is empty for every reason code but this one, and the key is
    omitted entirely when it is — the same rule `rarity` above follows for a blank cell.

    `rarity` is HALF OF A CONTRADICTION AND WAS NOT ON THE WIRE UNTIL 2026-09-11. The one
    reason in the whole vocabulary whose meaning is *"A contradicts B"* —
    `rarity_claim_mismatch` — could name neither A nor B, so a screen drawing 141 of them
    said the claim matched no row and left the operator to guess which word disagreed with
    which. Both halves travel now; the card's own claim is on `read` below.

    An ABSENT cell stays absent rather than becoming `""`: a row that carries no rarity is
    evidence of nothing, which is exactly how D23's filter reads it, and a screen that drew
    an empty string there would be asserting the row is unrated."""
    matched = {str(sku) for sku in name_matched}
    out: List[Dict[str, object]] = []
    for row in rows:
        entry: Dict[str, object] = {
            "sku": row[tcgcsv.SKU_COLUMN],
            "name": row[tcgcsv.NAME_COLUMN],
            "set": row.get(tcgcsv.SET_COLUMN, ""),
            "number": row[tcgcsv.NUMBER_COLUMN],
            "condition": row[tcgcsv.CONDITION_COLUMN],
            "market": row[tcgcsv.MARKET_PRICE_COLUMN],
        }
        rarity = (row.get(tcgcsv.RARITY_COLUMN) or "").strip()
        if rarity:
            entry["rarity"] = rarity
        if matched:
            entry["found_by"] = (
                "name" if str(row[tcgcsv.SKU_COLUMN]) in matched else "number"
            )
        out.append(entry)
    return out


def queue_entry(queued: join.QueuedCard) -> queues.QueueEntry:
    card = queued.card
    price = queued.destination.price
    # `place_text`, not `Position.label`: the review queue is the first surface the pooled
    # ruling names, so a pooled card's entry carries the pooled fact and its key. The
    # review screen renders whatever string arrives here, so it needs no branch of its
    # own — which is the point of composing it in one place (`pipeline/join.py`).
    return queues.QueueEntry(
        position=_key(card.position),
        box=card.position.box,
        index=card.position.index,
        label=join.place_text(card.game, card.position),
        photo=card.photo,
        read={
            "name": card.name,
            "number": card.number,
            "printed_total": card.printed_total,
            "set_hint": card.set_hint,
            # A LIST ON THE WIRE, not the tuple the frozen carrier holds. This dict is
            # written to `review.json` and read by `app/src/ReviewQueue.tsx`, so the shape
            # that matters is the JSON one — `json` would render a tuple as an array either
            # way, and spelling it out here is what keeps the entry equal to itself after a
            # round trip through the file. None stays None: no claim, and the screen says so.
            "metadata_finish": (
                None if card.metadata_finish is None else list(card.metadata_finish)
            ),
            "detected_finish": card.detected_finish,
            # THE OTHER HALF OF THE CONTRADICTION (D23 job (a)). A LIST on the wire for
            # `metadata_finish`'s reason two keys up — the frozen carrier holds a tuple and
            # this dict is written to `review.json` — and None when nobody claimed anything,
            # which the screen says in those words rather than drawing an empty chip.
            #
            # `docs/DECISIONS.md` recorded naming these as needing a schema change, on the
            # ground that `QueueEntry` carries the read and the candidates and not the
            # claim. It is a schema change: this key, and `rarity` on each candidate row.
            # Both are additive and neither moves a byte of what was already there.
            "rarity_claim": (
                None if card.rarity_claim is None else list(card.rarity_claim)
            ),
        },
        confidence=card.confidence,
        reason=queued.destination.reason,
        candidates=_candidate_rows(queued.candidates, queued.name_matched_skus),
        market=None if price is None else str(price),
    )


def failure_entry(failure: PreJoinFailure) -> queues.QueueEntry:
    """A pre-join failure as a queue entry. Box 0 means "no position" — D10 starts at 1."""
    return queues.QueueEntry(
        position=failure.key,
        box=failure.box or 0,
        index=failure.index or 0,
        label=failure.label,
        photo=failure.photo,
        read=dict(failure.read),
        confidence=None,
        reason=failure.reason,
        candidates=[],
        market=None,  # unpriced sorts last in the main queue, never parked
    )


def entries_for(resolved: Resolved):
    """(main, parked) queue entries for one run — every game's, plus the pre-join
    failures. The queues are per-position and game-agnostic; only the catalogs are
    partitioned."""
    main: List[queues.QueueEntry] = []
    parked: List[queues.QueueEntry] = []
    for game_join in resolved.joins.values():
        main += [queue_entry(q) for q in game_join.report.queue(routing.MAIN)]
        parked += [queue_entry(q) for q in game_join.report.queue(routing.PARKED)]
    main += [failure_entry(f) for f in resolved.failures]
    return main, parked


def cheapest_of(rows) -> Optional[Decimal]:
    return routing.cheapest(
        [tcgcsv.parse_price(r[tcgcsv.MARKET_PRICE_COLUMN]) for r in rows]
    )
