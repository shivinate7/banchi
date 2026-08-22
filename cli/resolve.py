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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from cli import runs
from pipeline import join, pricing, routing, tcgcsv
from store import master, queues
from store.session import Store


@dataclass(frozen=True)
class PreJoinFailure:
    """A card the join never saw, and why. Always destined for the main queue."""

    key: str
    photo: Optional[str]
    reason: str
    box: Optional[int] = None
    index: Optional[int] = None
    read: Dict[str, object] = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.box is None or self.index is None:
            return f"{Path(self.photo).name if self.photo else self.key} (no position)"
        return join.Position(self.box, self.index).label

    @property
    def describe(self) -> str:
        return f"{self.label}  {self.reason}"


@dataclass
class Resolved:
    """Everything `join` reports and `emit` writes from."""

    run: runs.Run
    export: tcgcsv.Export
    catalog: join.Catalog
    report: join.JoinReport
    failures: List[PreJoinFailure]
    source: Dict[str, object]
    rule: pricing.Rule
    basis: str
    # position key -> capture photo. Carried so `emit` can create an inventory record for a
    # position the store has never seen — a run joined from a hand-made or recovered
    # identifications file has no capture record behind it, and a state transition that
    # silently lands nowhere is exactly what this pipeline must not do.
    photos: Dict[str, Optional[str]] = field(default_factory=dict)

    @property
    def queued_positions(self):
        """Positions this run put in a standing queue."""
        return {_key(q.card.position) for q in self.report.queued} | {
            f.key for f in self.failures
        }

    @property
    def matched_positions(self):
        """Positions this run resolved cleanly."""
        return {
            _key(position)
            for match in self.report.matches.values()
            for position in match.positions
        }

    @property
    def processed_positions(self):
        """Every position this run had an opinion about.

        The set a queue release is allowed to act on. A run that looked at box 3 knows
        nothing about box 7, so it must not evict box 7's entries from a standing queue —
        the queues outlive runs, which is the whole reason they are standing.
        """
        return self.matched_positions | self.queued_positions

    @property
    def listed_skus(self):
        return {m.sku for m in self.report.matches.values() if m.listable}

    @property
    def sub_threshold_skus(self):
        return set(self.report.below_threshold.skus)

    @property
    def no_market_data_skus(self):
        return {m.sku for m in self.report.no_market_data}


def _key(position: join.Position) -> str:
    return f"{position.box}/{position.index}"


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


def load(
    run: runs.Run,
    export_path: Path,
    *,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    review_below: str = routing.CONFIDENCE_LOW,
    live_cap: int = join.LIVE_QUANTITY_CAP,
) -> Resolved:
    """Read the run, build the catalog, walk the ladder, route every card."""
    payload = run.read_identifications()
    export = tcgcsv.read_export(export_path)
    catalog = join.Catalog(export)

    # The store's settled identities, read off the live inventory. A record carries
    # `sku` + `condition` from exactly two writers — `do_review_answer` (a human chose the
    # row, state still `identified`) and `cmd_emit`'s push (the pipeline chose it and
    # committed to it) — and in both cases the identity is settled: re-walking the ladder
    # against it can only re-raise a question that already has an answer, which is how the
    # first real run's sixteen answered cards re-parked on every join. Read here rather
    # than in the loop so the store is opened once.
    held_cards = Store().read().inventory.cards

    cards: List[join.IdentifiedCard] = []
    failures: List[PreJoinFailure] = []
    photos: Dict[str, Optional[str]] = {}

    for key, record in sorted((payload.get("cards") or {}).items()):
        identification = record.get("identification")
        box, index = record.get("box"), record.get("index")
        if box is not None and index is not None:
            photos[f"{int(box)}/{int(index)}"] = record.get("photo")

        if box is None or index is None:
            failures.append(
                PreJoinFailure(
                    key=key,
                    photo=record.get("photo"),
                    reason=routing.NO_POSITION,
                    read=identification or {},
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
                )
            )
            continue

        number = (identification.get("number") or "").strip() or None
        total = (identification.get("printed_total") or "").strip() or None
        finish = identification.get("finish")
        held = held_cards.get(key)
        answered = held is not None and bool(held.sku) and bool(held.condition)
        committed = held is not None and held.state in (
            master.STAGED,
            master.LIVE,
            master.SOLD,
        )
        cards.append(
            join.IdentifiedCard(
                position=join.Position(box=int(box), index=int(index)),
                name=identification.get("name") or "",
                number=number,
                printed_total=total if number else None,
                metadata_finish=record.get("metadata_finish"),
                detected_finish=finish if finish in ("normal", "holo", "reverse_holo") else None,
                photo=record.get("photo"),
                set_hint=record.get("set_hint"),
                confidence=identification.get("confidence"),
                answered_sku=held.sku if answered else None,
                answered_condition=held.condition if answered else None,
                committed=committed,
            )
        )

    report = join.join_batch(
        cards,
        catalog,
        live_cap=live_cap,
        router=join.default_router(review_below=review_below),
        rule=rule,
        basis=basis,
    )

    return Resolved(
        run=run,
        export=export,
        catalog=catalog,
        report=report,
        failures=failures,
        source=runs.describe_source(export_path),
        rule=pricing.Rule.parse(rule),
        basis=basis,
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
    return queues.QueueEntry(
        position=_key(card.position),
        box=card.position.box,
        index=card.position.index,
        label=card.position.label,
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
    """(main, parked) queue entries for one run."""
    main = [queue_entry(q) for q in resolved.report.queue(routing.MAIN)]
    main += [failure_entry(f) for f in resolved.failures]
    parked = [queue_entry(q) for q in resolved.report.queue(routing.PARKED)]
    return main, parked


def cheapest_of(rows) -> Optional[Decimal]:
    return routing.cheapest(
        [tcgcsv.parse_price(r[tcgcsv.MARKET_PRICE_COLUMN]) for r in rows]
    )
