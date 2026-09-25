"""`send_claims` — the cards a press to TCGplayer is sending, held until its outcome is known.

D174'S SHAPE, OVER A DIFFERENT PURCHASE. `store/submissions.py` holds the cards a press is
about to pay Anthropic to read; this table holds the copies a press is about to list at
TCGplayer, or the prices it is about to change there (`D-one-press-sends-and-makes-live`).
The rule is the same one: a press claims what it is about to send IN THE TRANSACTION THAT
DECIDES IT, and a second press over the same cards is refused by name — by the claim's
stamp, its time and the cards the two share.

WHY A TABLE AND NOT A LOCK IN THE SERVER. The capture server runs four request slots, so two
presses can run at once, and a hand `pkmnscan emit` is a second process the server cannot see.
The only thing both can see is the store, and the only moment that cannot race is the store
write that decides what is being sent (`cli/cmd_emit.py`). A lock in memory is also what a
restart forgets; a row survives it, and that is the point of the second job below.

THE SECOND JOB IS THE HOLD, AND IT IS WHY A ROW DOES NOT SELF-HEAL. A send whose outcome is
UNKNOWN — TCGplayer answered 500 to the publish, or never answered, or refused the rollback
of an upload that now waits in its Staged list — keeps its claim. Every later send is refused
over those cards until a live check past the wait says what happened. A dead holder is
REPORTED (`submissions.holder_alive`, the same comparison), never acted on: a press whose
server died mid-publish is exactly the case whose copies may already be live.

A CLAIM IS KEYED BY SKU, NOT BY POSITION. A listing at TCGplayer is a quantity per SKU (D7,
amended) and the copies are fungible, so two presses doubling a SKU is the hazard whatever
drawers the copies sit in. `skus` maps each SKU to the copies the press adds (0 for a price
file, which adds none).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from store.rows import Rows, TableSpec
from store.submissions import holder_alive, proc_start

STATE_LIVE = "live"
STATE_RELEASED = "released"
STATES = (STATE_LIVE, STATE_RELEASED)

KIND_LISTING = "listing"
KIND_MARKDOWN = "markdown"
KINDS = (KIND_LISTING, KIND_MARKDOWN)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SendClaim:
    """One press's hold on the SKUs it is sending."""

    stamp: str
    kind: str
    pid: int
    started_at: str
    skus: Dict[str, int] = field(default_factory=dict)
    state: str = STATE_LIVE
    proc_start: Optional[str] = None
    released_at: Optional[str] = None
    released_by: Optional[str] = None

    @property
    def live(self) -> bool:
        return self.state == STATE_LIVE


def _parse(key: str, record: dict) -> Optional[SendClaim]:
    """One claim from its stored row, or None for a shape that will not construct.

    `store/submissions.py:_parse`'s trade, for its reason: a row that will not parse is skipped
    rather than raised on, because the alternative is a store that cannot be opened.
    """
    if str(key).startswith("_"):
        return None
    known = {k: v for k, v in record.items() if k in SendClaim.__annotations__}
    known["stamp"] = str(key)
    skus = known.get("skus")
    known["skus"] = (
        {str(sku): int(count or 0) for sku, count in skus.items()} if isinstance(skus, dict) else {}
    )
    try:
        built = SendClaim(**known)
    except (TypeError, ValueError):
        return None
    if built.state not in STATES or built.kind not in KINDS:
        return None
    if not isinstance(built.pid, int) or isinstance(built.pid, bool):
        return None
    return built


@dataclass
class SendClaims:
    entries: "Rows" = field(default_factory=lambda: Rows(SendClaims.ENTRIES))

    ENTRIES = TableSpec(
        "send_claims",
        parse=_parse,
        dump=asdict,
        columns=lambda claim: {
            "pid": claim.pid,
            "state": claim.state,
            "started_at": claim.started_at,
            "kind": claim.kind,
        },
        column_names=("pid", "state", "started_at", "kind"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(SendClaims.ENTRIES, objects=dict(self.entries))

    def live(self) -> List[SendClaim]:
        """Every claim still holding SKUs, oldest first. One indexed read on `state`."""
        found = self.entries.where(state=STATE_LIVE)
        return sorted(found, key=lambda claim: (claim.started_at or "", claim.stamp))

    def get(self, stamp: str) -> Optional[SendClaim]:
        return self.entries.get(str(stamp))

    def overlap(
        self, skus: Iterable[str], excluding: Optional[str] = None
    ) -> List[Tuple[SendClaim, List[str]]]:
        """Every live claim holding any of `skus`, with the SKUs it and this press share."""
        wanted = {str(sku) for sku in skus}
        found: List[Tuple[SendClaim, List[str]]] = []
        for claim in self.live():
            if excluding is not None and claim.stamp == str(excluding):
                continue
            shared = sorted(wanted & set(claim.skus))
            if shared:
                found.append((claim, shared))
        return found

    def claim(
        self,
        stamp: str,
        kind: str,
        skus: Dict[str, int],
        *,
        pid: Optional[int] = None,
    ) -> SendClaim:
        """Write a live claim. The caller has already checked `overlap` in this transaction."""
        if kind not in KINDS:
            raise ValueError(f"unknown send claim kind {kind!r}")
        holder = int(pid if pid is not None else os.getpid())
        claim = SendClaim(
            stamp=str(stamp),
            kind=kind,
            pid=holder,
            started_at=now(),
            skus={str(sku): int(count) for sku, count in skus.items()},
            state=STATE_LIVE,
            proc_start=proc_start(holder),
        )
        self.entries[claim.stamp] = claim
        return claim

    def release(self, stamp: str, by: str) -> Optional[SendClaim]:
        """Give up a claim's hold. The row stays, as a tombstone; twice is not an error."""
        claim = self.get(stamp)
        if claim is None or not claim.live:
            return claim
        claim.state = STATE_RELEASED
        claim.released_at = now()
        claim.released_by = str(by)
        # Reassigned, not mutated in place (D192): `where` trusts the source's own index for a
        # key this session has not written through `__setitem__`.
        self.entries[claim.stamp] = claim
        return claim


def alive(claim: SendClaim) -> bool:
    """Is the process that holds this claim still running? `submissions.holder_alive`'s rule."""
    return holder_alive(claim)  # type: ignore[arg-type]
