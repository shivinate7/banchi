"""Reading a directory of code-card photographs into ledger entries.

THE CORE, SHARED BY THE CLI AND THE ROUTE, and it is factored out rather than duplicated
because CLAUDE.md's hard rule makes both mandatory: a capability that exists only in
`server/` is not done, and one that exists only in `cli/` cannot be reached from a screen.
Two callers, one implementation, so the Codes screen and `pkmnscan scan` can never come to
disagree about what a scan did.

NOTHING HERE WRITES. `read_directory` is pure with respect to the store — it opens
photographs and returns what it found. `apply` is the only writer and takes an already-open
writable session, so the caller decides the lock's extent. That split is what lets the CLI
offer `--dry-run` and the route offer a preview with the same code underneath.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from codes import ledger, products, qr
from identify import sidecar

# The one game this track reads. Imported rather than restated — `codes/products.py:GAME`
# is the single place it is written, and the capture screen learns it from the same value
# over the wire.
CODE_GAME = products.GAME


@dataclass
class Reading:
    """What one pass over a capture directory found."""

    entries: List[ledger.Entry]
    problems: List[str]
    photographs: int
    code_cards: int

    @property
    def other_games(self) -> int:
        return self.photographs - self.code_cards

    @property
    def malformed(self) -> List[ledger.Entry]:
        return [e for e in self.entries if not ledger.well_formed(e.code)]


def read_one(capture) -> Tuple[Optional[ledger.Entry], Optional[str]]:
    """(entry, problem). Exactly one of the two is None.

    `qr.QrUnavailable` IS DELIBERATELY NOT CAUGHT. It means no decoder is installed, which is
    a fact about the machine rather than about this card — and a run that reported every card
    unreadable when the truth is one missing wheel is a run that gets believed once and acted
    on wrongly. It propagates to the caller, which names it once.
    """
    if not capture.has_position:
        return None, f"{capture.photo.name}: no position, so no ledger line can be keyed"
    try:
        read = qr.decode(capture.photo)
    except qr.QrUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        return None, f"{capture.key}: {capture.photo.name} could not be opened — {exc}"
    if read is None:
        return None, (
            f"{capture.key}: no QR found in {capture.photo.name} — "
            "send it to the paid vision read, or re-shoot it"
        )
    if not read.code:
        return None, (
            f"{capture.key}: {capture.photo.name} decoded a QR carrying no redemption code "
            f"— payload begins {read.payload[:40]!r}"
        )
    return (
        ledger.Entry(
            code=read.code,
            box=capture.box,
            index=capture.index,
            photo=str(capture.photo),
            set_hint=capture.set_hint,
            product=capture.product,
            source=ledger.SOURCE_QR,
            rung=read.rung,
            scanned_at=ledger.now(),
        ),
        None,
    )


def read_directory(directory, box: Optional[int] = None) -> Reading:
    """Every code card in one capture directory. Reads photographs; writes nothing.

    A PHOTO WHOSE GAME CLAIM IS NOT `pokemon_code` IS LEFT ENTIRELY ALONE, not reported as a
    problem. Mixed boxes are legal (D21), so a Pokemon single sitting in a code-card box is
    an ordinary thing and not a fault — and calling it one would train the operator to
    ignore this command's warnings.
    """
    captures = sidecar.scan(Path(directory), box=box)
    mine = [c for c in captures if c.game_or_default == CODE_GAME]
    entries: List[ledger.Entry] = []
    problems: List[str] = []
    for capture in mine:
        entry, problem = read_one(capture)
        if entry is not None:
            entries.append(entry)
        else:
            problems.append(problem or "unknown problem")
    return Reading(
        entries=entries,
        problems=problems,
        photographs=len(captures),
        code_cards=len(mine),
    )


def apply(writable, entries) -> Tuple[List[ledger.Entry], dict, int]:
    """Merge into the ledger and stamp each code onto its card. Returns (merged, counts, n).

    THE CALLER HOLDS THE LOCK. `writable` is an already-open session, so the ledger write and
    the record writes land in one transaction — a ledger naming a code whose card record does
    not carry it would make C8's dispute lookup silently miss.

    STAMPING THE CODE ONTO `number` IS C8's LOOKUP AND IS NOT REDUNDANT WITH THE LEDGER.
    `GET /search` substring-matches and ranks exact on `number`, so this is what makes "type
    the code, get the card, tap its photograph" work through the search that already exists,
    with no new screen. It is free for this game: `pokemon_code` joins by name, so nothing
    ever composes a `number/printed_total` key out of these fields.
    """
    merged, counts = ledger.merge(ledger.read(), entries)
    ledger.write(merged)
    stamped = 0
    for entry in entries:
        key = f"{entry.box}/{entry.index}"
        if writable.inventory.get(key) is not None:
            writable.inventory.record_identification(
                key,
                name=products.display(entry.product) if entry.product else "",
                number=entry.code,
                printed_total="",
                confidence="high",
                run=None,
            )
            stamped += 1
    return merged, counts, stamped
