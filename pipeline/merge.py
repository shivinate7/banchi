"""One import file over several runs — the cap computed once, the answers still per run (D86).

WHY THIS MODULE EXISTS, AND WHY IT IS NOT A CONCATENATION. The owner asked for one CSV rather
than one per run per game per bucket. The obvious implementation — read the files `emit`
already wrote and staple them together — is wrong, and measurably so on this machine:

    `pipeline/join.py:SkuMatch.add_to_quantity` spends `live_cap - copies_out` PER RUN
    against a cap that is GLOBAL.

So two runs joined before either emitted each believe the whole cap is theirs. The 2026-09-01
cart joined boxes 3, 4 and 5 in the same second; five SKUs' per-run claims summed past four,
and two of them reached `pushed: 6` in `inventory/inventory.json` against a cap of 4:

    Void Assault (9197754):  pushed: 6, live: 1
    Deathgrip    (9038187):  pushed: 6, live: 1

That is D59's defect one register up. D59 fixed per-BOX capping inside one join — *"a SKU
split across two boxes was capped once per box"* — and the same arithmetic survived per RUN
across joins that never saw each other. A merged file has to re-derive the figure over the
union or it writes that over-push into a CSV.

WHAT MERGES AND WHAT DOES NOT. The COPIES merge: a SKU's positions across every run are one
set of cardboard, deduped on `(box, index)`, and the cap is spent against that set once. The
ANSWER does not need to — there is only one. D86's amendment moved the per-SKU answer out of
the run directory into `pipeline/corpus.py`, so a card has one price by construction and this
module receives one `Decisions` for the whole send.

THE FIRST BUILD OF THIS FILE PRICED EACH RUN SEPARATELY AND COMPARED THEM, and that is worth
recording because it is what the owner's question retired. It carried a `PriceDisagreement`
for a shared SKU answered two ways and, run against three real runs, refused on 66 of them —
almost every one of which was not a disagreement at all but the market having moved between
two joins. Machinery to reconcile a duplication is worse than not duplicating; the whole class
is gone.

NOTHING HERE WRITES. `plan()` reads resolved runs and returns rows plus an apportionment;
`cli/cmd_emit.py` owns the file and the store, as it always has.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Set

from pipeline import decisions as decisions_mod, join, tcgcsv


@dataclass
class Leg:
    """One run's own view of a SKU: its match and what its document priced it at."""

    run: str
    game: str
    match: join.SkuMatch
    # KEPT AS `None`: the price is derived ONCE from the merged match, because two runs joined
    # against two exports read two market prices for one card and neither is that card's
    # answer. See `_agree_per_sku`.
    price: Optional[Decimal] = None


@dataclass
class MergedSku:
    """One card across every run in the send.

    `match` is a synthetic `SkuMatch` holding the UNION of the legs' positions, so
    `add_to_quantity` — the property that was wrong per run — is computed once over every copy
    that exists. `legs` keeps each run's own match, because the store write is per run: a
    position belongs to exactly one run and `set_state` stamps it with that run's name.
    """

    sku: str
    game: str
    price: Decimal
    match: join.SkuMatch
    legs: List[Leg]
    sub_threshold: bool

    @property
    def claimed(self) -> int:
        """What the runs SEPARATELY believe they may add — the figure this module corrects."""
        return sum(leg.match.add_to_quantity for leg in self.legs)

    @property
    def over_cap(self) -> bool:
        return self.claimed > self.match.add_to_quantity


@dataclass
class Plan:
    """What one merged emit would write, and how its copies divide between the runs."""

    skus: List[MergedSku] = field(default_factory=list)
    # sku -> the positions that reach the FILE, in the order the cap was spent on them.
    # `cli/cmd_emit.py` reads this to decide which copies raise `pushed`.
    live_keys: Dict[str, Set[str]] = field(default_factory=dict)
    # Every SKU a run matched and this plan writes no row for, with the reason. Never silent:
    # `CLAUDE.md` forbids dropping a card without saying so.
    dropped: "OrderedDict[str, str]" = field(default_factory=OrderedDict)

    def rows(self, *, listed_only: bool = False) -> List[MergedSku]:
        """The SKUs a file would carry, in the order they were merged.

        `listed_only` peels off the sub-threshold rows, which is the owner's checkbox: one file
        by default, and the valuable cards alone when they want to stage those first. It is a
        FILTER over one plan rather than a second plan, so the cap arithmetic cannot differ
        between the two answers.
        """
        out = [row for row in self.skus if row.match.add_to_quantity > 0]
        if listed_only:
            out = [row for row in out if not row.sub_threshold]
        return out


def _key(position: join.Position) -> str:
    return f"{position.box}/{position.index}"


def _union(legs: Sequence[Leg], read) -> List[join.Position]:
    """One list of positions across the legs, deduped on `(box, index)`, legs in order.

    THE DEDUPE IS THE COUNT AND NOT A SAFETY NET. Box 3 has been joined three times on this
    machine, so its cards appear in three runs; a concatenation would make Void Assault twelve
    copies of a card there are seven of, and the cap would then be spent against a number no
    shelf could satisfy.

    LEG ORDER IS RUN ORDER, WHICH IS OLDEST FIRST. `add_to_quantity` slices the front of this
    list, so the copies that reach the file are the ones from the run that has been waiting
    longest — the same first-come rule `uncommitted_positions` already applies inside a run,
    applied across them.
    """
    seen: Set[str] = set()
    out: List[join.Position] = []
    for leg in legs:
        for position in read(leg.match):
            key = _key(position)
            if key in seen:
                continue
            seen.add(key)
            out.append(position)
    return out


def _merged_match(sku: str, legs: Sequence[Leg]) -> join.SkuMatch:
    """The synthetic match the cap is computed against.

    THE ROW IS THE NEWEST LEG'S. Two runs joined against two exports carry two readings of the
    same card; the newer one read the newer export, and D8 makes the export the authority on
    price. Taking the newest row whole keeps every cell one reading rather than a blend.

    `held_out` IS THE LARGEST THE LEGS SAW, WHICH IS THE ONLY SAFE DIRECTION. It is
    `cli/resolve.py:_copies_out` — what TCGplayer holds, live and pending — and that docstring
    makes the export a FLOOR that *"cannot be argued below"*. Two legs reading it at different
    moments can differ; taking the smaller would re-open the cap on the strength of the staler
    read, which is exactly the refill bug D59 closed.
    """
    newest = legs[-1]
    return join.SkuMatch(
        sku=sku,
        row=newest.match.row,
        positions=_union(legs, lambda m: m.positions),
        stages=list(newest.match.stages),
        live_cap=max(leg.match.live_cap for leg in legs),
        rule=newest.match.rule,
        basis=newest.match.basis,
        # THE NEWEST LEG'S, LIKE THE ROW AND THE RULE. `_agree_policy` has already refused a
        # send whose runs carry different `threshold` overrides, so every leg agrees here —
        # carrying it explicitly is what keeps `MergedSku.match.listable` from quietly
        # answering with the module constant instead of the operator's figure.
        threshold=newest.match.threshold,
        committed_positions=_union(legs, lambda m: m.committed_positions),
        held_out=(
            None
            if all(leg.match.held_out is None for leg in legs)
            else max(leg.match.held_out or 0 for leg in legs)
        ),
    )


class Disagreement(Exception):
    """The runs in a send do not share a pricing policy, and this module may not choose.

    THE ONLY DISAGREEMENT LEFT, AND IT IS THE D48 REMNANT. Per-SKU answers cannot disagree any
    more: they live in one corpus keyed by SKU (D86, amended), so a card has one answer by
    construction and the class of conflict this module was first written to detect no longer
    exists. What can still differ is a per-run POLICY OVERRIDE — a lot of commons wanting a
    different `sub_threshold` from a lot of hits, which is D48's argument and survives it — and
    one file needs one answer to that.
    """


@dataclass
class _Shim:
    """The two attributes `join.prices_for` reads off a report, over the MERGED matches.

    A SHIM AND NOT A SYNTHETIC `JoinReport`, because a real one would have to be built from
    catalogs and cards this module does not have and does not need. `prices_for` reads
    `report.matches` and, only to compose a refusal, `below_threshold`. Passing the ladder a
    narrower object is honest; re-implementing the ladder is what D49 forbids, and this exists
    so nothing has to.
    """

    matches: "OrderedDict[str, join.SkuMatch]"
    below_threshold: object = None


class _Below:
    """The sub-threshold rows, for the one refusal `prices_for` can still raise here."""

    def __init__(self, skus: Sequence[str] = ()):
        self.skus = tuple(skus)

    def report(self) -> str:
        return "\n".join(f"    {sku}" for sku in self.skus)


def _agree_policy(policies: Mapping[str, Mapping[str, object]]) -> None:
    """Every run in the send must be priced by the same policy, or nothing is written.

    ONE FILE NEEDS ONE ANSWER FOR A SHARED SUB-THRESHOLD CARD, and picking the newest would
    silently reprice a lot somebody set deliberately. Since D86's amendment the policy is the
    corpus's and a per-run override is the exception rather than the rule, so this refuses
    almost never — and when it does, the fix is to drop the override or send the runs apart.
    """
    if len(policies) < 2:
        return
    for label in ("rule", "basis", "sub_threshold", "threshold"):
        seen: "OrderedDict[str, List[str]]" = OrderedDict()
        for name, policy in policies.items():
            seen.setdefault(_token(policy.get(label)), []).append(name)
        if len(seen) > 1:
            lines = [
                f"the runs in this send are priced by different `{label}` values, and one "
                f"file needs one answer. Drop the per-run override, or emit them separately:"
            ]
            for value, names in seen.items():
                lines.append(f"  - {value}: {', '.join(names)}")
            raise Disagreement("\n".join(lines))


def _token(value: object) -> str:
    """A policy value as a comparable string. `0.50` and `0.5` are ONE answer.

    Measured: box 3's two runs carried exactly that pair, written in two sittings, and
    comparing the `repr` reported them as a disagreement about money.
    """
    if value is None:
        return "unset"
    if hasattr(value, "kind"):
        if value.kind == decisions_mod.pricing.FLAT_FLOOR:
            return "floor"
        return f"${value.price.normalize()}"
    return str(value)


def plan(
    resolved_by_run: Mapping[str, object],
    choice: decisions_mod.Decisions,
    policies: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Plan:
    """Merge resolved runs into one emit.

    `resolved_by_run` is run name -> `cli/resolve.Resolved`, in the order the copies should be
    spent — oldest run first. Typed loosely because `cli/` imports `pipeline/` and not the
    other way round; this module may not import the CLI package.

    `choice` IS ONE DOCUMENT FOR THE WHOLE SEND, which is the amendment to D86 and the reason
    this function is a third of its first length. It was written against per-run answer files
    and therefore had to price each run separately, compare every shared SKU, and refuse on a
    disagreement — machinery whose only job was to reconcile a duplication. The corpus holds
    one answer per card, so there is one document, one price per SKU, and nothing to reconcile.

    WHAT IT STILL DOES, AND IT IS THE PART THAT WAS ALWAYS THE POINT: the copies merge and the
    cap is spent ONCE over the union. `join.SkuMatch.add_to_quantity` computes
    `live_cap - copies_out` per RUN against a cap that is global, so runs joined before either
    emitted each believe the whole cap is theirs — measured, five SKUs' claims summed past four
    and two reached `pushed: 6` against a cap of 4. Centralising the answers does not touch
    that; only re-deriving the figure over the union does.
    """
    _agree_policy(policies or {})

    legs_by_sku: "OrderedDict[str, List[Leg]]" = OrderedDict()
    sub_by_sku: Dict[str, bool] = {}

    for name, resolved in resolved_by_run.items():
        for game, game_join in resolved.joins.items():  # type: ignore[attr-defined]
            report = game_join.report
            below = set(report.below_threshold.skus)
            for sku, match in report.matches.items():
                legs_by_sku.setdefault(sku, []).append(
                    Leg(run=name, game=game, match=match)
                )
                # THE BUCKET IS THE NEWEST RUN'S, for `_merged_match`'s reason: it is decided
                # by the Market cell alone (`prices_for`), so it belongs to the same reading
                # as the row.
                sub_by_sku[sku] = sku in below

    merged: "OrderedDict[str, join.SkuMatch]" = OrderedDict(
        (sku, _merged_match(sku, legs)) for sku, legs in legs_by_sku.items()
    )
    priced = join.prices_for(
        _Shim(
            matches=merged,
            below_threshold=_Below(sku for sku, sub in sub_by_sku.items() if sub),
        ),
        sub_threshold=choice.sub_threshold,
        sku_dispositions={
            sku: d for sku, d in choice.dispositions().items() if sku in merged
        },
        no_market_data={
            sku: v for sku, v in choice.no_market_data.items() if sku in merged
        },
        withheld=set(choice.withheld()),
    )

    out = Plan()
    for sku, legs in legs_by_sku.items():
        match = merged[sku]
        if sku not in priced:
            # WITHHELD, or answered `unlisted` — `prices_for` leaves both out of the mapping
            # and a row is not written for either. Named rather than dropped: `CLAUDE.md`
            # forbids losing a card without saying so.
            out.dropped[sku] = "held back or answered unlisted"
            continue
        out.skus.append(
            MergedSku(
                sku=sku,
                game=legs[-1].game,
                price=priced[sku],
                match=match,
                legs=legs,
                sub_threshold=sub_by_sku.get(sku, False),
            )
        )
        # WHICH COPIES REACH THE FILE, decided ONCE over the merged list. `live_positions` is
        # `uncommitted_positions[:add_to_quantity]` inside one run; here the slice is over
        # every run's copies together, so the same copy cannot be counted twice and the
        # backstock stays backstock. `cli/cmd_emit.py` reads these keys to decide which
        # positions raise `pushed`.
        out.live_keys[sku] = {
            _key(position)
            for position in match.uncommitted_positions[: match.add_to_quantity]
        }
        if match.add_to_quantity == 0:
            out.dropped[sku] = match.nothing_to_add or "nothing to add"
    return out


def import_rows(rows: Sequence[MergedSku]) -> List[tcgcsv.Row]:
    """The CSV rows for a merged plan — one per SKU, no duplicates possible by construction.

    THE NO-DUPLICATE-SKU RULE MOVES FROM AN ASSERTION TO A PROPERTY. `CLAUDE.md` calls two rows
    with one `TCGplayer Id` in one import file undefined behaviour, and per-file-per-run that
    was a rule each writer had to keep. Here the plan is keyed by SKU, so a card in four runs is
    one row carrying the summed quantity and there is no shape in which it could be two.
    `cli/cmd_emit.py` still asserts it, because a property nothing checks is a comment.
    """
    out: List[tcgcsv.Row] = []
    for row in rows:
        written = tcgcsv.set_writable(
            row.match.row,
            add_to_quantity=row.match.add_to_quantity,
            marketplace_price=row.price,
        )
        # Against the catalog original, exactly as `join.import_rows` does: a row reaches the
        # file only if the single-writable-column rule holds for it.
        tcgcsv.check_only_writable_changed(row.match.row, written)
        out.append(written)
    return out


def games_in(rows: Sequence[MergedSku]) -> List[str]:
    """The games a merged plan spans, in first-appearance order.

    THE CALLER DECIDES WHETHER TO SPLIT ON THIS, AND THE QUESTION IS GENUINELY OPEN.
    `cli/runs.py:import_listed_name` has said since it was written that nobody has established
    whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s, and
    `fixtures/staged-import-accepted.csv` proves it for one line only. The owner asked for one
    file and said they would test it; `--split-games` is the one-flag way back if the portal
    refuses.
    """
    seen: List[str] = []
    for row in rows:
        if row.game not in seen:
            seen.append(row.game)
    return seen
