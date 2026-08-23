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

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

from cli import runs
from pipeline import games, join, pricing, routing, tcgcsv, variant
from store import master, queues
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

    @property
    def label(self) -> str:
        # `place_text`, not `Position.label`: a report line is one of the surfaces the
        # pooled ruling (`pipeline/games.py`'s `located` flag) forbids the label on.
        # `misc` — today's only occupant of this type — is located, so its lines are
        # byte-identical; the branch exists for the day a non-located game is also
        # uncatalogued.
        return join.place_text(self.game, join.Position(self.box, self.index))

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

    @property
    def label(self) -> str:
        if self.box is None or self.index is None:
            return f"{Path(self.photo).name if self.photo else self.key} (no position)"
        return join.place_text(self.game, join.Position(self.box, self.index))

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
    # Cards held out of the join because their game has no catalog. See `NotJoined`: these
    # are correct outcomes, not failures, and they are a separate list from `failures` so
    # that no reader can print them under one heading.
    not_joined: List[NotJoined] = field(default_factory=list)
    # position key -> capture photo. Carried so `emit` can create an inventory record for a
    # position the store has never seen — a run joined from a hand-made or recovered
    # identifications file has no capture record behind it, and a state transition that
    # silently lands nowhere is exactly what this pipeline must not do.
    photos: Dict[str, Optional[str]] = field(default_factory=dict)

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


def _committed_keys(inventory: master.Inventory) -> set:
    """Positions the join must treat as copies TCGplayer already holds or has pending.

    `SkuMatch.committed_positions` is per-position and the store's counts are per-SKU, so
    something has to turn one into the other. It is a COUNTING device and not an address:
    the store records how many copies of a SKU are pushed and staged, this picks that many
    of the SKU's unsold copies in box-walk order, and the only thing the join does with them
    is `len()` and a set subtraction. Any N of them would do — that is the fungibility
    ruling — so the choice is made deterministically and nothing is written back.

    Which is why "any non-zero count commits every copy" is not the rule. Seven copies with
    two staged would commit all seven, `add_to_quantity` would clamp to zero, and the SKU
    would never refill to the D7 cap again. Counting them gives the right answer: two
    committed, room for two more, exactly what the per-position model computed before it was
    removed.

    `live` IS DELIBERATELY NOT COUNTED HERE, and this is the one place the old model was
    wrong rather than merely address-shaped. `SkuMatch.add_to_quantity` already subtracts
    `live_before` — the export's `Total Quantity`, which D8 and D11 make authoritative —
    so adding the stored `live` count would subtract the same copies twice and under-list
    every SKU that has ever been live. `pushed` and `staged` are the two TCGplayer holds
    that its live quantity does not report.
    """
    keys = set()
    for entry in inventory.listings.values():
        held = max(0, entry.pushed) + max(0, entry.staged)
        if held <= 0:
            continue
        for card in inventory.copies_on_hand(entry.sku)[:held]:
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
    payload = run.read_identifications()
    held_cards = Store().read().inventory.cards
    needed: "OrderedDict[str, List[str]]" = OrderedDict()
    for key, record in sorted((payload.get("cards") or {}).items()):
        box, index = record.get("box"), record.get("index")
        if box is None or index is None or not record.get("identification"):
            continue
        held = held_cards.get(key)
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
            join.place_text(str(game), join.Position(box=int(box), index=int(index)))
        )
    # Registry order, so refusals and reports list games the way every picker does.
    return OrderedDict(
        (game, needed[game]) for game in games.keys() if game in needed
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
    lines.append(
        "If a card's game claim is wrong, correct it first with the capture server's "
        "PUT /inventory/<box>/<index> route (field: game), then join again."
    )
    lines.append("Nothing was joined, nothing was written, and no queue was touched.")
    raise runs.RunError("\n".join(lines))


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

    claimed_by: Dict[str, List[Path]] = {}
    lines_of: Dict[Path, Tuple[str, ...]] = {}
    for path in distinct:
        if not path.is_file():
            raise runs.RunError(f"export not found: {path}")
        lines = tcgcsv.product_lines(tcgcsv.read_export(path))
        lines_of[path] = lines
        matched = [
            game
            for game in games.keys()
            if isinstance(games.get(game)["product_line"], str)
            and games.get(game)["product_line"] in lines
        ]
        if not matched:
            known = sorted(
                {
                    str(games.get(game)["product_line"])
                    for game in games.keys()
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
        for game in (g for g in games.keys() if g in doubled):
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

    needed = _games_needed(run)
    _refuse_uncovered(needed, list(claimed_by))

    by_game: "OrderedDict[str, Path]" = OrderedDict(
        (game, claimed_by[game][0]) for game in games.keys() if game in needed
    )
    notes = tuple(
        f"note: {path} carries only {', '.join(repr(v) for v in lines_of[path])} and "
        f"this run holds no card of a game that claims it — the file is unused"
        for path in distinct
        if path not in set(by_game.values())
    )
    return ExportPlan(by_game=by_game, notes=notes)


def load(
    run: runs.Run,
    exports: Union[str, Path, Mapping[str, Path]],
    *,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    review_below: str = routing.CONFIDENCE_LOW,
    live_cap: int = join.LIVE_QUANTITY_CAP,
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

    # The store's settled identities, read off the live inventory. A record carries
    # `sku` + `condition` from exactly two writers — `do_review_answer` (a human chose the
    # row) and `cmd_emit`'s push (the pipeline chose it and wrote it into a file) — and in
    # both cases the identity is settled: re-walking the ladder against it can only re-raise
    # a question that already has an answer, which is how the first real run's sixteen
    # answered cards re-parked on every join. Both writers leave the card in `identified`;
    # the listing progress lives on the SKU now, which is what `_committed_keys` reads.
    # Read here rather than in the loop so the store is opened once.
    snapshot = Store().read()
    held_cards = snapshot.inventory.cards
    committed_keys = _committed_keys(snapshot.inventory)

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
                position=join.Position(box=int(box), index=int(index)),
                name=identification.get("name") or "",
                number=number,
                printed_total=total if number else None,
                metadata_finish=record.get("metadata_finish"),
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
        (game, grouped[game]) for game in games.keys() if game in grouped
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

    parsed: Dict[Path, tcgcsv.Export] = {}
    joins_out: "OrderedDict[str, GameJoin]" = OrderedDict()
    for game, game_cards in needed.items():
        path = mapping[game]
        file_export = parsed.get(path)
        if file_export is None:
            file_export = parsed[path] = tcgcsv.read_export(path)
        # Per game, never merged — see `GameJoin`. Two games sharing one file (pokemon
        # and pokemon_code) each cut their own catalog from the one reading.
        catalog = join.Catalog.from_export(file_export, game)
        report = join.join_batch(
            game_cards,
            catalog,
            live_cap=live_cap,
            router=join.default_router(review_below=review_below),
            rule=rule,
            basis=basis,
        )
        joins_out[game] = GameJoin(
            game=game,
            export=catalog.export,
            catalog=catalog,
            report=report,
            source=runs.describe_source(path),
        )

    return Resolved(
        run=run,
        joins=joins_out,
        failures=failures,
        rule=pricing.Rule.parse(rule),
        basis=basis,
        not_joined=not_joined,
        photos=photos,
    )


# ------------------------------------------------------------------------ queue entries


def _candidate_rows(rows) -> List[Dict[str, object]]:
    """What the review screen shows beside the photo (D4): the rows this could be."""
    return [
        {
            "sku": row[tcgcsv.SKU_COLUMN],
            "name": row[tcgcsv.NAME_COLUMN],
            "set": row.get(tcgcsv.SET_COLUMN, ""),
            "number": row[tcgcsv.NUMBER_COLUMN],
            "condition": row[tcgcsv.CONDITION_COLUMN],
            "market": row[tcgcsv.MARKET_PRICE_COLUMN],
        }
        for row in rows
    ]


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
            "metadata_finish": card.metadata_finish,
            "detected_finish": card.detected_finish,
        },
        confidence=card.confidence,
        reason=queued.destination.reason,
        candidates=_candidate_rows(queued.candidates),
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
