"""Reconcile the whole store against one live TCGplayer export (D87).

WHY THIS IS NOT `cli/cmd_reconcile.py`'s EXISTING JOB. That command takes a run directory and
an Export From Staged, and scopes its diff to `run_dir.emitted_skus` — one import, one moment.
The thing it diffs AGAINST has never been run-scoped: `store/master.py:Listing` holds
`pushed`/`staged`/`live` per SKU across every box and run, and D7 amended says so in as many
words — *"quantities held against a SKU rather than states a card wears"*. The per-run scoping
is a property of the command, not of the data.

WHAT THAT COST, MEASURED ON THE OWNER'S STORE 2026-09-01. Reconcile had effectively never run:
405 of 443 SKUs read `live: 0` while carrying pushed copies, and `staged` was 0 everywhere. So
the cap arithmetic in `pipeline/join.py` was working off `Total Quantity` from whatever export
a run happened to hold, with the store's own claim contributing nothing. Two SKUs had reached
`pushed: 6` against a cap of 4 and **nothing in the product could see it**.

BOTH DIRECTIONS, ALWAYS — the existing command's rule, and the half you cannot get per run.
Its header records why: *"v1 matched by box+position, silently skipped identified cards, and
reported nothing for unmatched rows — a one-directional check passes on that bug."* A live
export is the only document that can answer the other direction, because it is the only one
that lists what TCGplayer holds rather than what one import sent.

IT MOVES QUANTITIES AND NEVER CARDS (D7). What sold is a quantity per SKU; WHICH physical copy
sold is deliberately unrecorded, because every unsold copy is equally sellable and this
document could not say anyway. So this reports that `n` copies of a SKU left and never marks a
card `sold` — that is the operator's act on `#/inventory` or `#/orders`, and a command that
did it from a quantity would be inventing an address D7 refuses to invent.

WHAT IT WRITES IS `live`, AND ONLY `live`. That is a smaller change than it first looks and it
is the right one. `pushed` is the CUMULATIVE count of copies this pipeline has written into
import files; it is drawn down by the per-run reconcile and by nothing else, so on a store that
never reconciled it is a running total rather than an outstanding balance. Rewriting it here
would destroy the only cumulative record there is.

`cli/resolve.py:_copies_out` ALREADY CORRECTS A STUCK `pushed` AND SAYS SO: *"THE CEILING IS
PHYSICAL, AND IT IS WHAT CORRECTS A STUCK `pushed` ... it cannot be true that TCGplayer holds
more copies than we sent and have not sold, so `copies_not_sold` is what says so."* What that
arithmetic was missing is a real `live`, which **nothing in this repo has ever written** — 405
of 443 SKUs read zero while carrying pushed copies. Populating it is the whole fix.

SO THE RESIDUAL IS REPORTED AND NEVER CLEARED. A copy this pipeline pushed that TCGplayer does
not hold and no card is marked sold for is genuinely ambiguous — sold and unmarked, pulled by
hand, or a row the portal rejected. It is a sentence for the operator, not a number to adjust.

AND THE LEDGER'S OWN `live` IS NOT BELIEF, IT IS A STALE OBSERVATION. Measured on the owner's
store: 32 of the 38 SKUs carrying a legacy `live` would claim more copies than were ever
captured if it were added to `pushed`. The two describe the same copies at different moments,
so the export supersedes it rather than adding to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

from pipeline import tcgcsv


@dataclass
class Row:
    """One SKU, as the two documents describe it."""

    sku: str
    live: int
    pushed: int
    staged: int
    sold: int
    on_hand: int
    name: str = ""
    line: str = ""
    condition: str = ""
    market: str = ""

    #: What the ledger recorded as LIVE before this ran. Reported, never added to `claim` —
    #: see the module header on why it is an observation rather than a second belief.
    ledger_live: int = 0

    @property
    def claim(self) -> int:
        """Copies this pipeline has ever written into an import file for this SKU.

        CUMULATIVE, NOT OUTSTANDING, and that is what `pushed` actually is on a store the
        per-run reconcile has not walked. It is the only cumulative record of what was sent —
        an import file holds the last delta only (D54) — so this reads it and never rewrites
        it.
        """
        return self.pushed + self.staged

    @property
    def accounted(self) -> int:
        """Copies whose fate is known: still live, or marked sold in the store."""
        return self.live + self.sold

    @property
    def unexplained(self) -> int:
        """Copies pushed that are neither live nor marked sold. The residual."""
        return max(0, self.claim - self.accounted)

    @property
    def moved(self) -> int:
        """Copies whose live quantity this reconcile is about to correct."""
        return abs(self.live - self.ledger_live)


@dataclass
class Report:
    """Both directions, plus what a write would do."""

    #: SKUs the store pushed and the export accounts for entirely. Nothing to say.
    agreed: List[Row] = field(default_factory=list)
    #: Pushed copies TCGplayer does not hold and the store has not marked sold.
    unexplained: List[Row] = field(default_factory=list)
    #: TCGplayer holds MORE than this pipeline ever sent — a listing made elsewhere, or a
    #: quantity added by hand. Never touched: this pipeline did not put it there.
    beyond: List[Row] = field(default_factory=list)
    #: Live at TCGplayer, and this store has never seen the SKU at all.
    unknown: List[Row] = field(default_factory=list)
    #: In the ledger, absent from the export entirely — not even a zero-quantity row.
    absent: List[Row] = field(default_factory=list)

    @property
    def unexplained_copies(self) -> int:
        return sum(row.unexplained for row in self.unexplained)

    @property
    def corrected(self) -> int:
        """Copies whose `live` quantity a write would correct."""
        return sum(row.moved for row in self.agreed + self.unexplained + self.beyond)


def _int(value) -> int:
    try:
        return int(str(value).strip() or 0)
    except ValueError:
        return 0


def compare(
    export_rows: Sequence[Mapping[str, str]],
    listings: Mapping[str, object],
    sold: Mapping[str, int],
    on_hand: Mapping[str, int],
    seen: Optional[Sequence[str]] = None,
) -> Report:
    """Diff the export against the ledger. Reads nothing, writes nothing.

    `listings` is `store/master.py:Inventory.listings` — anything with `.pushed`, `.staged`
    and `.live`. `sold` and `on_hand` are per-SKU card counts out of the same inventory;
    they are passed in rather than derived so this module never learns the card schema.

    `seen` is every SKU the store has ever attached to a card, which is WIDER than `listings`:
    a card can carry a SKU that was never pushed — withheld, sub-threshold, or simply never
    emitted. Without it, every such card's SKU would be reported as "listed outside pkmnscan"
    the moment it appeared in the export, which is the false accusation this parameter exists
    to prevent.
    """
    known = set(seen or ()) | set(listings)
    report = Report()

    by_sku: Dict[str, Mapping[str, str]] = {}
    for raw in export_rows:
        sku = str(raw.get(tcgcsv.SKU_COLUMN, "")).strip()
        if sku:
            by_sku[sku] = raw

    for sku, raw in by_sku.items():
        live = _int(raw.get(tcgcsv.LIVE_QUANTITY_COLUMN))
        entry = listings.get(sku)
        row = Row(
            sku=sku,
            live=live,
            pushed=getattr(entry, "pushed", 0) if entry else 0,
            staged=getattr(entry, "staged", 0) if entry else 0,
            ledger_live=getattr(entry, "live", 0) if entry else 0,
            sold=sold.get(sku, 0),
            on_hand=on_hand.get(sku, 0),
            name=str(raw.get(tcgcsv.NAME_COLUMN, "")),
            line=str(raw.get("Product Line", "")),
            condition=str(raw.get(tcgcsv.CONDITION_COLUMN, "")),
            market=str(raw.get(tcgcsv.MARKET_PRICE_COLUMN, "")),
        )
        if sku not in known:
            # NOT AN ERROR AND NOT THIS PIPELINE'S BUSINESS. Sealed product, a single listed
            # by hand, anything from before pkmnscan. Reported at zero quantity too would be
            # noise, so only a live one is worth a line.
            if live > 0:
                report.unknown.append(row)
            continue
        if row.claim == 0:
            # The store knows the SKU but never pushed it — withheld, sub-threshold, not yet
            # emitted, or listed by hand and recorded by D109. Its quantity came from
            # somewhere this pipeline cannot see, in EITHER direction.
            #
            # `ledger_live` IS THE HALF THAT WAS MISSING, and its absence was a trap D109
            # armed rather than sprang. A row at `claim == 0` and quantity 0 fell through to
            # no bucket at all — not `agreed`, not `beyond`, not `unknown`, not `absent` — so
            # `settling` never held it and `observe_live` was never called for it. Every
            # record D109 creates has `pushed = 0` by design, so the first `--write` over the
            # owner's export made 43 of them: the day any one sold out, its stored `live`
            # became unsettleable and every later reconcile skipped it in silence.
            #
            # THE STORE HAVING A READING IS WHAT MAKES IT WORTH SETTLING. A SKU nobody has
            # ever recorded, reading zero, is genuinely nothing to say — that is the `continue`
            # below, and it is why this is not simply `if True`.
            if live > 0 or row.ledger_live > 0:
                report.beyond.append(row)
            continue
        if live > row.claim + row.sold:
            report.beyond.append(row)
        elif row.unexplained > 0:
            report.unexplained.append(row)
        else:
            report.agreed.append(row)

    for sku, entry in listings.items():
        if sku in by_sku:
            continue
        claim = getattr(entry, "pushed", 0) + getattr(entry, "staged", 0)
        if claim or getattr(entry, "live", 0):
            report.absent.append(
                Row(
                    sku=sku,
                    live=0,
                    pushed=getattr(entry, "pushed", 0),
                    staged=getattr(entry, "staged", 0),
                    ledger_live=getattr(entry, "live", 0),
                    sold=sold.get(sku, 0),
                    on_hand=on_hand.get(sku, 0),
                    condition=getattr(entry, "condition", "") or "",
                )
            )

    for bucket in (report.unexplained, report.beyond, report.unknown, report.absent):
        bucket.sort(key=lambda r: (-r.unexplained, -r.live, r.sku))
    return report
