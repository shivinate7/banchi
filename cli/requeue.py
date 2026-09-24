"""Re-resolve every OPEN queue entry against a current export — store-wide, run-free.

WHY THIS EXISTS: `store/queues.py:upsert` refreshes an entry perfectly and is reached from
exactly one place — `queues.apply_run`, from `cli/cmd_join.py`. A join is scoped to a run and
a run is scoped to a box, so an entry whose box holds no live run can never be rewritten
again. Measured on the owner's store 2026-09-12, grouped by `first_seen`:

    entries first seen   carry `rarity`   conditions filtered to Near Mint
    2026-09-12           70 of 70         yes
    2026-09-11            1 of 283        no
    2026-08-24…09-02      0 of 230        mixed

Two fixes landed on 2026-09-11 — `cli/resolve.py:_candidate_rows` putting `rarity` on every
candidate, and D137's Near Mint rule on the candidate path. Both are correct in the CODE and
**513 of the 565 stored entries will never see them**, because no run alive covers their
positions. Proved rather than inferred: the `Calm Rune` entry is position `4/357`, and all six
runs over box 4 re-joined with a freshly fetched export each reported `+0 main, +0 parked, -0
resolved`. The operator works a queue that is part current and part frozen with no way to tell
which by looking, and every later improvement to the ladder or to the candidate rows lands the
same way.

THE PRECEDENT IS EXACT AND IS `reconcile --live` (D87). That command is store-wide *because*
a run-scoped reconcile could not reach everything — "the scoping was a property of the
command, not of the data" — and the same sentence is true here twice over: `Queue` is keyed by
position across every box, and `upsert` was written to refresh.

IT IS THE LADDER AND NOT A SECOND READING OF IT. Every entry is rebuilt into the
`join.IdentifiedCard` `cli/resolve.py:load` would have built, handed to `join.join_batch` with
`join.default_router`, and turned back into a `queues.QueueEntry` by `cli/resolve.py:queue_entry`
— the same three functions a join runs, in the same order. So a later improvement to the
ladder, to the candidate rows or to the router reaches this path the day it lands, with nothing
here to keep in step. That is the whole point: the defect above is that improvements did not
travel, and a refresh that restated the ladder would be a second thing to keep current.

WHAT IT NEEDS THAT A RUN HAD: the model's reading, and the STORE HOLDS IT — that is what
makes a refresh run-free and therefore store-wide.
`store/master.py:record_identification` writes `read_name`, `read_number`,
`read_printed_total` and `confidence` onto the card (docs/specs/identity-follows-sku.md
§3.4, lane 1 — the evidence group, never overwritten by a later binding), and `game`,
`set_hint`, `metadata_finish` and `rarity_claim` are capture claims that live there too.
**The fifth field, `detected_finish`, was missing and is added by this change** — see
`Card.detected_finish` for the argument. Taking it off the queue entry instead looked free
and is not: an entry may have been written by an OLDER identification of the same
photograph, and a refresh reading four fields off the card and one off the entry gave the
ladder two readings of one card. Measured: it queued six of box 4's cards that a join listed.

**LANE 4 (identity-follows-sku.md §5.1): THIS FUNCTION READS `read_name`/`read_number`/
`read_printed_total`, NEVER `card.name`/`card.number`/`card.printed_total`.** The identity
fields now equal the SKU table's row (`store/master.py:Inventory.bind_sku`), so a refresh
that compared a bound card's identity against itself would agree with itself on every card
and D253's join-time dispute check would never fire — a disputed card would be silently
released from the review queue the first time this module touched it. The evidence fields
are the model's actual reading and are what `join.name_disputes` must compare against the
catalog, unchanged by any binding.

NO QUANTITY ARITHMETIC RUNS HERE. `join_batch` is handed no `copies_out` and no `live_now`:
routing reads the resolution, the confidence and the cheapest candidate price, and none of
those is a quantity. `cli/resolve.py:_copies_out` is a full pass over every listing with two
queries each — ~1s on the owner's store — and a refresh that spent it would pay seconds to
compute figures it then throws away. What this writes is a QUESTION, never a price and never a
copy.

THE TWO REFUSALS THIS MODULE DOES NOT IMPLEMENT ARE THE TWO IT MOST DEPENDS ON, and both come
free from `queues.apply_run`: `upsert` refuses to re-queue a `cleared_by_human` entry, and
`release` refuses to drop one. D28's undo window is the only door back out of an answer and it
stays the only one. Reusing that function rather than writing the pair of loops here is
deliberate — it is the seam T7 already tests, and it is what keeps the two queues from being
released in ignorance of each other (its own docstring carries that history).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pipeline import corpus as corpus_mod
from pipeline import games, join, pricing, routing, tcgcsv
from store import master, queues

from cli import resolve as run_resolve

# Why an entry could not be re-resolved. Named rather than counted: a refresh that silently
# left cards alone would be the same shape as the defect it exists to fix.
NO_CARD = "no_card"
NO_GAME = "no_game"
NO_EXPORT = "no_export"
NO_READING = "no_reading"
UNJOINABLE = "unjoinable"
DEPARTED = "departed"

SKIP_REASONS = (NO_CARD, NO_GAME, NO_EXPORT, NO_READING, UNJOINABLE, DEPARTED)

SKIP_SENTENCES = {
    NO_CARD: "no card is stored at this position any more",
    NO_GAME: "the card names a game this build does not register",
    NO_EXPORT: "no export was supplied for this card's game",
    NO_READING: "the card carries no name and no number to resolve",
    UNJOINABLE: "this game has no lookup strategy",
    DEPARTED: "the card has left the box — sold, retired or moved",
}


@dataclass(frozen=True)
class Skipped:
    """One entry this pass could not re-resolve, and why. Never a silent drop."""

    position: str
    queue: str
    reason: str
    game: Optional[str] = None

    @property
    def describe(self) -> str:
        return f"{self.position:>10}  {self.queue:<7} {SKIP_SENTENCES.get(self.reason, self.reason)}"


@dataclass(frozen=True)
class Change:
    """What re-resolving one position did to it.

    `before` and `after` are the stored entry and the entry this pass would write. `after`
    is None where the card now resolves outright and the entry leaves the queue.
    """

    position: str
    before: queues.QueueEntry
    after: Optional[queues.QueueEntry]

    @property
    def resolved(self) -> bool:
        """The ladder settled it: the card lists, and the question goes."""
        return self.after is None

    @property
    def gained_rarity(self) -> int:
        """Candidate rows that carry a `Rarity` now and did not before (2026-09-11)."""
        was = sum(1 for row in self.before.candidates if row.get("rarity"))
        now = 0 if self.after is None else sum(
            1 for row in self.after.candidates if row.get("rarity")
        )
        return max(0, now - was)

    @property
    def dropped_off_condition(self) -> int:
        """Candidate rows this pass stopped offering because they are not Near Mint (D137)."""
        def off(entry: Optional[queues.QueueEntry]) -> int:
            if entry is None:
                return 0
            return sum(
                1
                for row in entry.candidates
                if not str(row.get("condition") or "").startswith("Near Mint")
            )

        return max(0, off(self.before) - off(self.after))

    @property
    def narrowed_to_one(self) -> bool:
        """Was ambiguous, now offers exactly one row — answerable in one tap."""
        return (
            self.after is not None
            and len(self.before.candidates) > 1
            and len(self.after.candidates) == 1
        )

    @property
    def changed(self) -> bool:
        """Anything a person would see on the review screen is different."""
        if self.after is None:
            return True
        return (
            self.after.candidates != self.before.candidates
            or self.after.reason != self.before.reason
            or self.after.market != self.before.market
            or self.after.label != self.before.label
            or self.after.read != self.before.read
        )

    @property
    def describe(self) -> str:
        if self.after is None:
            return f"{self.position:>10}  resolves now — leaves the queue"
        bits = []
        if self.after.reason != self.before.reason:
            bits.append(f"{self.before.reason} -> {self.after.reason}")
        if self.gained_rarity:
            bits.append(f"+{self.gained_rarity} rarity")
        if self.dropped_off_condition:
            bits.append(f"-{self.dropped_off_condition} off-condition")
        if len(self.after.candidates) != len(self.before.candidates):
            bits.append(
                f"{len(self.before.candidates)} -> {len(self.after.candidates)} row(s)"
            )
        if self.narrowed_to_one:
            bits.append("one row — answerable")
        return f"{self.position:>10}  " + (", ".join(bits) if bits else "refreshed")


@dataclass
class RefreshPlan:
    """What a store-wide refresh would do, computed before anything is written.

    Previews by default, exactly as `join`, `reconcile` and `reprice list` do. `apply` is
    the only thing here that touches a queue, and it takes a writable snapshot.
    """

    main: List[queues.QueueEntry] = field(default_factory=list)
    parked: List[queues.QueueEntry] = field(default_factory=list)
    freed: set = field(default_factory=set)
    changes: List[Change] = field(default_factory=list)
    skipped: List[Skipped] = field(default_factory=list)
    #: positions that were open and are still open and identical — counted, never listed
    unchanged: int = 0
    #: entries `cleared_by_human`, never touched and never re-queued (D28 is the only door)
    cleared: int = 0
    #: entries naming a different photograph than the card now standing at their key — the
    #: question is rebuilt from the card that is THERE (D36's rule, one register down)
    photo_moved: int = 0
    games_seen: Dict[str, int] = field(default_factory=dict)

    @property
    def examined(self) -> int:
        return len(self.changes) + self.unchanged + len(self.skipped)

    @property
    def resolved(self) -> List[Change]:
        return [c for c in self.changes if c.resolved]

    @property
    def refreshed(self) -> List[Change]:
        return [c for c in self.changes if not c.resolved]

    @property
    def answerable(self) -> List[Change]:
        """Refreshed entries now offering exactly one row.

        NAMED RATHER THAN ACTED ON. Whether one candidate is enough to LIST a card without a
        human is the ladder's call and PR #300's rule decides it — this pass runs that ladder
        and reports what it did. An entry that is still here after it offered one row is one
        the ladder deliberately left for a person.
        """
        return [c for c in self.refreshed if c.narrowed_to_one]

    @property
    def touched(self) -> int:
        return len(self.changes)

    def apply(self, review: queues.Queue, parked: queues.Queue) -> Tuple[int, int, List[str]]:
        """Write the plan. `queues.apply_run`'s two refusals are why this is one line.

        `upsert` will not re-queue a position a human cleared and `release` will not drop
        one, so an answer outlives this pass by construction rather than by a test. The
        function is named for a run and is not about one: its docstring calls it "one run's
        verdict on the standing queues, applied as a unit", and a store-wide verdict is
        applied by the same unit for the same reason — the two queues must never be released
        in ignorance of each other.
        """
        return queues.apply_run(review, parked, self.main, self.parked, self.freed)


def identified(
    card: master.Card, views: Dict[int, join.BoxView]
) -> Optional[join.IdentifiedCard]:
    """The `IdentifiedCard` `cli/resolve.py:load` would have built, from the store instead.

    THE STORE IS THE READING, AND IT IS THE WHOLE READING. `load` takes the model's answer
    out of the run's `identifications.json`; this takes it off the card, where
    `store/master.py:record_identification` wrote the same values at identify time —
    `read_name`, `read_number`, `read_printed_total`, `confidence` and, since this module
    arrived, `detected_finish`. The capture claims — `set_hint`, `metadata_finish`,
    `rarity_claim`, `game` — are the store's in both readers, because `CAPTURE_CLAIM_FIELDS`
    is where they live.

    **READS `read_name`/`read_number`/`read_printed_total`, NEVER `card.name`/`card.number`/
    `card.printed_total`** (identity-follows-sku.md §5.1, lane 4). `name`/`number`/
    `printed_total` are the IDENTITY group now — equal to the bound SKU's own row once
    `Inventory.bind_sku` has run, never the model's reading — so a builder that read them
    here would hand `join.name_disputes` the catalog's own name to compare against the
    catalog and see no dispute on any bound card, ever. This function is one of the two
    §5.1 names as a builder that must move.

    THE QUEUE ENTRY IS NOT CONSULTED, AND THAT IS THE POINT OF THE FIELD `detected_finish`
    ADDED TO `Card`. The entry's `read` carries a complete reading, so taking one field from
    it looked free; it is not, because the entry may have been written by an OLDER
    identification of the same photograph. Measured on the owner's store: six of box 4's
    cards were re-identified on 2026-09-12 with `finish: null`, their 2026-09-11 queue
    entries still said `foil`, and a refresh that read name and number off the card and the
    finish off the entry gave the ladder two different readings of one card — it queued six
    cards the join listed. The entry decides WHICH positions this pass examines and nothing
    about what they are. One reading in, one verdict out.

    A CARD THE STORE HAS NO READING FOR IS REFUSED RATHER THAN GUESSED AT — the caller files
    it as `no_reading` and names it. Falling back to the entry's `read` would be the same
    mixing one layer down, and a card whose only reading is the one already on screen has
    nothing for this pass to re-resolve anyway.

    `answered_sku` IS DELIBERATELY NOT READ. It is `None` on every card this function is
    called for, because a card carrying an answer has a `cleared_by_human` entry and this
    module never looks at one. Passing it would be harmless and stating that it is not passed
    is not: rung 0 must never be what releases a card from a refresh, or a pass over the
    queue would quietly re-list every answer the operator has ever given.
    """
    game = card.game or games.DEFAULT_GAME
    # `load`'s OWN NORMALISATION, CHARACTER FOR CHARACTER:
    #     number = (identification.get("number") or "").strip() or None
    #     total  = (identification.get("printed_total") or "").strip() or None
    #     ... printed_total=total if number else None
    # AN EMPTY STRING IS NOT A NUMBER AND THE TWO ROUTE DIFFERENTLY. `_key_number_and_printed_total`
    # answers None for a card with no number, which sends it down the blank-`Number` name
    # branch; `""` is a value, walks the number key, misses, and lands on D35's
    # last-resort name rung as `number_unread_name_matched`. Measured before this line
    # existed: 6 of 183 positions where the join listed a card and this module queued it,
    # every one of them a record carrying `""` in `number` or `printed_total` — box 4's
    # `Renata Glasc, Mastermind` and `Arcane Shift` among them. The store keeps `""` where a
    # run record keeps it, so the normalisation has to happen on this side too.
    name = card.read_name or ""
    number = (card.read_number or "").strip() or None
    total = (card.read_printed_total or "").strip() or None
    if not name and not number:
        return None
    return join.IdentifiedCard(
        position=views.get(int(card.box), join.BoxView()).at(card.box, card.index),
        name=name,
        number=number,
        printed_total=total if number else None,
        metadata_finish=run_resolve._finish_claim(card.metadata_finish),
        detected_finish=run_resolve._detected(card.detected_finish, game),
        photo=card.photo,
        set_hint=card.set_hint,
        game=game,
        rarity_claim=run_resolve._rarity_claim(card.rarity_claim),
        # OFF THE CARD, WITH NO FALLBACK — the docstring's rule applied to the fifth field.
        # This read `card.confidence or entry.confidence`, which is the mixing two paragraphs
        # up forbidden in as many words AND a `NameError`: `entry` is not a parameter of this
        # function, so every card whose stored confidence was falsy crashed the whole pass
        # rather than resolving. `None` is the honest reading of a card the store has no
        # confidence for, and `routing` already has a branch for it.
        confidence=card.confidence,
        # Never rung 0 — see the docstring. A cleared entry does not reach this function.
        answered_sku=None,
        answered_condition=None,
        committed=card.state in master.TERMINAL_STATES,
    )


def _open_by_position(
    review: queues.Queue, parked: queues.Queue
) -> "List[Tuple[str, str, queues.QueueEntry]]":
    """Every OPEN entry once, review before parked, as (position, queue name, entry).

    A POSITION CAN SIT IN BOTH QUEUES AND MUST BE RESOLVED ONCE. `queues.apply_run` already
    handles the write — it releases the entry a re-routed position leaves behind in the queue
    it moved OUT of — but the LADDER must not run twice for one card, or the second pass
    would route a card the first has already placed and the two answers would race. Review
    governs, which is `server/capture_server.py:_answer_target`'s rule for the same pair
    ("main queue governs when the position is in both") and is the only ordering under which
    the more expensive question wins.
    """
    seen: Dict[str, None] = {}
    out: List[Tuple[str, str, queues.QueueEntry]] = []
    for queue in (review, parked):
        for entry in queue.open_entries:
            if entry.position in seen:
                continue
            seen[entry.position] = None
            out.append((entry.position, queue.name, entry))
    return out


def plan(
    inventory: master.Inventory,
    review: queues.Queue,
    parked: queues.Queue,
    catalogs: Dict[str, join.Catalog],
    *,
    threshold: Decimal = pricing.THRESHOLD,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    review_below: str = routing.CONFIDENCE_LOW,
) -> RefreshPlan:
    """Re-resolve every open entry against `catalogs`, and say what that would change.

    WRITES NOTHING. `RefreshPlan.apply` is the only writer and it takes the queues.

    ONE `join_batch` PER GAME, which is the partition D25 already makes and the reason
    `catalogs` is keyed by game rather than being one merged file. A game with no catalog
    supplied is SKIPPED BY NAME rather than resolved against somebody else's rows.
    """
    out = RefreshPlan()
    out.cleared = sum(
        1
        for queue in (review, parked)
        for entry in queue.entries.values()
        if entry.cleared_by_human
    )
    views = run_resolve.box_views(inventory)

    stored: Dict[str, queues.QueueEntry] = {}
    per_game: "Dict[str, List[join.IdentifiedCard]]" = {}
    for position, queue_name, entry in _open_by_position(review, parked):
        stored[position] = entry
        card = inventory.cards.get(position)
        if card is None:
            out.skipped.append(Skipped(position, queue_name, NO_CARD))
            continue
        # A CARD THAT HAS LEFT THE BOX IS NOT RE-ASKED ABOUT (D26, D83). Sold, retired and
        # moved are terminal: the physical copy is gone, so the question is moot and putting
        # a refreshed version of it back on the review screen would spend a person's
        # attention on a card they cannot look at. `cli/cmd_join.py` already draws this line
        # — "skipped: N card(s) in this run are no longer in the box" — and this is the same
        # line for the store-wide pass.
        #
        # SKIPPED RATHER THAN RELEASED, which is the conservative half. The entry is left
        # exactly as it stands: this pass has no opinion about a card it will not resolve,
        # and releasing on a state change would make a refresh a queue-cleaner, which is a
        # different command than the one argued for. Found by a reconstruction of the
        # owner's store: six of box 4's entries sat over `sold` cards, and without this the
        # refresh re-queued every one of them.
        if card.state in master.TERMINAL_STATES:
            out.skipped.append(Skipped(position, queue_name, DEPARTED, card.game))
            continue
        game = card.game or games.DEFAULT_GAME
        if games.get(game) is None:
            out.skipped.append(Skipped(position, queue_name, NO_GAME, game))
            continue
        catalog = catalogs.get(game)
        if catalog is None:
            out.skipped.append(Skipped(position, queue_name, NO_EXPORT, game))
            continue
        built = identified(card, views)
        if built is None:
            out.skipped.append(Skipped(position, queue_name, NO_READING, game))
            continue
        # THE QUESTION IS RE-BOUND TO THE CARD THAT IS THERE, and this counts the times that
        # is a different card than the entry was written about. A mid-box delete slides every
        # higher card down one (D10 ruling 1) and the entry left behind goes on describing its
        # predecessor: measured at 46 of 565 on the owner's store, `2/14`'s entry naming
        # `0015.jpg` against the card's `0014.jpg`, a whole box off by one behind a deletion.
        # Reported rather than refused — the store is what says which slot a card is in (D36),
        # so rebuilding from it is the correction, not the hazard.
        if not card.photo or card.photo != entry.photo:
            out.photo_moved += 1
        try:
            join.lookup_for(game)
        except join.NotJoinable:
            out.skipped.append(Skipped(position, queue_name, UNJOINABLE, game))
            continue
        per_game.setdefault(game, []).append(built)
        out.games_seen[game] = out.games_seen.get(game, 0) + 1

    processed: set = set()
    queued_now: set = set()
    for game, cards in per_game.items():
        report = join.join_batch(
            cards,
            catalogs[game],
            router=join.default_router(threshold=threshold, review_below=review_below),
            rule=rule,
            basis=basis,
            threshold=threshold,
        )
        processed |= {run_resolve._key(card.position) for card in cards}
        for name, bucket in (
            (routing.MAIN, out.main),
            (routing.PARKED, out.parked),
        ):
            for queued in report.queue(name):
                fresh = run_resolve.queue_entry(queued)
                bucket.append(fresh)
                queued_now.add(fresh.position)

    fresh_by_position = {e.position: e for e in (*out.main, *out.parked)}
    for position in sorted(processed, key=lambda k: (int(k.split("/")[0]), int(k.split("/")[1]))):
        before = stored[position]
        after = fresh_by_position.get(position)
        change = Change(position=position, before=before, after=after)
        if change.changed:
            out.changes.append(change)
        else:
            out.unchanged += 1

    # A CARD THAT NOW RESOLVES LEAVES THE QUEUE, and `freed` is scoped to what this pass
    # actually re-resolved. Everything else — an entry skipped for want of an export, an
    # entry in a queue this pass never opened — is outside the set and `apply_run` keeps it.
    # That scoping is `cli/cmd_join.py`'s own (`resolved.processed_positions -
    # resolved.queued_positions`), for its reason: a release computed from anything wider
    # would evict entries this pass has no opinion about.
    out.freed = processed - queued_now
    return out


def catalogs_from(
    paths: Sequence[Path],
) -> "Tuple[Dict[str, join.Catalog], Dict[str, Path], List[Tuple[Path, str]]]":
    """Read export files into a catalog per game — `(catalogs, source, unreadable)`.

    A FILE ANSWERS FOR ITS GAMES OFF ITS OWN CELLS AND NEVER OFF ITS FILENAME, which is D25's
    rule and `cli/resolve.py:games_claimed`'s job. One file may answer for two games (pokemon
    and pokemon_code share a `Product Line`) and each cuts its own catalog from the one
    reading, exactly as `load` does.

    LAST FILE WINS for a game two files both claim. The caller passes the newest last — the
    command below sorts the runs' recorded exports by mtime — so the freshest reading of a
    game is the one that answers. A tie is not arbitrated here because there is nothing to
    arbitrate with: two files claiming one game at one moment are the same catalogue.
    """
    catalogs: Dict[str, join.Catalog] = {}
    source: Dict[str, Path] = {}
    unreadable: List[Tuple[Path, str]] = []
    for path in paths:
        try:
            export = tcgcsv.read_export(path)
        except (OSError, ValueError, KeyError) as exc:
            unreadable.append((path, str(exc)))
            continue
        claimed = run_resolve.games_claimed(export)
        if not claimed:
            unreadable.append((path, "names no registered game in its Product Line column"))
            continue
        for game in claimed:
            try:
                catalogs[game] = join.Catalog.from_export(export, game)
            except join.EmptyCatalog as exc:
                unreadable.append((path, f"{game}: {exc}"))
                continue
            source[game] = path
    return catalogs, source, unreadable


def policy_of(book: "corpus_mod.Corpus") -> "Tuple[Decimal, pricing.Rule, str]":
    """The store's standing cut-off, rule and basis — the figures a join would use.

    THE STORE'S POLICY AND NOT THIS MODULE'S CONSTANTS (D9, amended 2026-09-09), because the
    router reads the cut-off to decide whether a low-confidence card is worth a human's
    attention. A refresh that routed against `pricing.THRESHOLD` while the operator's store
    said something else would re-queue by one figure the cards a join queued by another.
    """
    policy = book.policy_for()
    return (
        pricing.check_threshold(policy.get("threshold")),
        pricing.Rule.parse(str(policy.get("rule", "match"))),
        str(policy.get("basis", "market")),
    )
