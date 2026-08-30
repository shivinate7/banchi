"""The Pirate Ship import spreadsheet — the format, and the two things it may never carry.

Pirate Ship has NO API. Their three first-class entry points are typing an address by
hand, a marketplace connection, and a **spreadsheet import**, and the third is the only one
this project can drive: the marketplace connection is theirs to build and typing 331
addresses is not automation. So the supported path is a CSV, and this module is the format.

THE IMPORT AUTO-MAPS COLUMN HEADERS, AND THIS FILE DELIBERATELY DOES NOT RELY ON IT. Their
mapper is good and it is a guess made on their side of a seam we cannot test. Two
consequences, both of which are the reason a column exists here rather than being left to
the wizard:

  `Name` IS PRE-JOINED FROM `FirstName` + `LastName`, because we own the columns and the
  mapper does not have to work out that two of ours make one of theirs. A recipient
  addressed as a first name alone is a package that arrives at the right street with the
  wrong person on it, and the failure is invisible from this end.

  EVERY COLUMN IS WRITTEN, INCLUDING THE EMPTY ONES. A column absent from the file is a
  column the wizard cannot map and cannot show the operator; a column present and blank is
  a field they can see is blank. The two look identical in a spreadsheet and are opposite
  facts on an import screen.

WHAT THIS MODULE MAY NEVER DO, and both are refusals rather than omissions:

  IT NEVER SELECTS INSURANCE. `REFUSED_COLUMNS` names every insurance-shaped header the
  import understands and `render` refuses a row carrying one. This is D49's rule in another
  lane — `pipeline/decisions.py` states it as "nothing here is ever defaulted on your
  behalf — that is the entire point", and an insured value written into a spreadsheet is a
  charge the owner did not choose, on a per-order judgement only they can make. The guard
  is a function rather than a comment for the reason `tcgcsv.set_writable` gives: a rule
  enforced by a function cannot be forgotten by a caller.

  IT NEVER BUYS A LABEL. There is no API to buy one with, and buying one spends money.
  This module renders bytes and returns them; the owner opens Pirate Ship, reads what is
  in front of them, and presses the button.

IT NEVER DERIVES A WEIGHT, WHICH IS THE SAME RULE WEARING A THIRD HAT AND IS THE ONE MOST
LIKELY TO BE "FIXED" BY A LATER SESSION. The obvious candidate is TCGplayer's `Product
Weight`, and it is wrong in the expensive direction: `docs/specs/shipping-export.md`
measures it as a summed per-product CATALOG CONSTANT — 0.07 oz a single, 2.50 oz a sealed
product — so it counts the cardboard and not the mailer, the toploader, the team bag or the
tape. It is a LOWER BOUND on what the parcel weighs. Writing it into `Package Weight` buys
postage for less than the package weighs, which is a package returned or postage due, at
the far end, weeks later. `Parcel.weight` is therefore whatever the caller measured and
blank when they have measured nothing; Pirate Ship's own import sets one weight across
every row after the fact, which is the right place for a number that comes off a scale.

BUYER PII PASSES THROUGH AND IS NOT PERSISTED. Names and street addresses enter as function
arguments and leave as the bytes the caller asked for. Nothing here writes to the store,
nothing caches, and `render` returns bytes rather than a path so that a caller may hand the
file over without one ever touching a disk. `write_csv` exists for the caller who wants a
file and writes exactly where it is told.

BYTE FORMAT — T2's rules, and the same writer `tcgcsv.render` uses:

  - header row: UNQUOTED
  - data fields: fully quoted, every field, including empties ("")
  - line endings: CRLF, including after the final record
  - no BOM

That is the IMPORT shape. `fixtures/orders-shipping.csv` is TCGplayer's EXPORT and is
LF-terminated (`docs/specs/shipping-export.md`); the two are different files going in
different directions, and reading one is not a licence to write the other.

Real CSV library only (v1 bug 2). A street address carries commas by construction — "Apt 4,
Building C" — so `split(",")` and its write-side twin `",".join(...)` corrupt an address
silently, and the symptom is a package delivered to a different building.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

ENCODING = "utf-8"
LINE_TERMINATOR = "\r\n"

# THE COLUMN SET, AND IT IS CLOSED. Named for what Pirate Ship's importer calls them, so
# the auto-mapper has nothing to guess at and the operator recognises the preview.
NAME_COLUMN = "Name"
ADDRESS_COLUMN = "Address"
ADDRESS2_COLUMN = "Address Line 2"
CITY_COLUMN = "City"
STATE_COLUMN = "State"
ZIP_COLUMN = "Zipcode"
COUNTRY_COLUMN = "Country"
WEIGHT_COLUMN = "Package Weight"
ORDER_ID_COLUMN = "Order ID"

# THREE STAMPS BECAUSE PIRATE SHIP OFFERS THREE, and they print in the corners of the label
# itself. That is what makes them worth writing: a label carrying `Box 3 · Card 31` IS the
# pick instruction, so the person walking to the shelf reads it off the thing already in
# their hand rather than off a second screen. Nothing here decides what they say — see
# `Parcel`.
#
# THE EXAMPLE IS SPELLED IN THIS REPO'S OWN LABEL VOCABULARY ON PURPOSE, and the shorter
# form it replaces is worth naming as a class rather than as a string. Abbreviating the card
# to a bare letter-plus-digits produces exactly the shape of a code-card decision id
# (docs/CODES-DECISIONS.md), so `scripts/docs-audit.py`'s decision-id scan reads the shelf
# location as a citation of a heading that does not exist and asks about it on every run —
# permanent noise in the one check whose whole value is that its questions are worth reading.
# It is ambiguous to a person for the same reason, which is the half that would still matter
# if nothing scanned for it.
STAMP_COLUMNS: Tuple[str, ...] = ("Rubber Stamp 1", "Rubber Stamp 2", "Rubber Stamp 3")
STAMP_LIMIT = len(STAMP_COLUMNS)

COLUMNS: Tuple[str, ...] = (
    NAME_COLUMN,
    ADDRESS_COLUMN,
    ADDRESS2_COLUMN,
    CITY_COLUMN,
    STATE_COLUMN,
    ZIP_COLUMN,
    COUNTRY_COLUMN,
    WEIGHT_COLUMN,
    ORDER_ID_COLUMN,
) + STAMP_COLUMNS

# EVERY INSURANCE-SHAPED HEADER THE IMPORT UNDERSTANDS, REFUSED BY NAME. Folded and
# stripped to compare, stored verbatim to report — the same split `pipeline/join.py`
# draws between a matching form and a stored one, for the same reason: an operator who
# spelled it `insured value` needs the refusal to name what they actually wrote.
#
# It is a DENY LIST over a set that is already closed by `COLUMNS`, which reads as belt and
# braces and is not. `render` refuses any column outside `COLUMNS` on its own, so a caller
# adding `Insurance` is already stopped; what this adds is the REASON. A refusal reading
# "not a Pirate Ship column" invites the fix of adding it to `COLUMNS`, and a refusal
# naming D49 does not.
REFUSED_COLUMNS: Tuple[str, ...] = (
    "Insurance",
    "Insured Value",
    "Insurance Amount",
    "Declared Value",
    "Shipsurance",
)


class InsuranceRefused(Exception):
    """A row carrying an insurance column. The owner chooses insurance per order, in
    Pirate Ship, looking at the card — never a value this pipeline wrote for them."""


class MalformedParcel(Exception):
    """A row that is not the shape this module contracts to write."""


def _folded(name: str) -> str:
    return " ".join(str(name).split()).casefold()


_REFUSED_FOLDED = {_folded(name): name for name in REFUSED_COLUMNS}


@dataclass(frozen=True)
class Parcel:
    """One row of the import: where it goes, what it weighs, and what to pick.

    THE NAME IS ONE FIELD BECAUSE THE LABEL PRINTS ONE LINE. `from_parts` is the join, so
    the first-plus-last rule lives in one place rather than at each call site.

    `weight` IS WHATEVER THE CALLER MEASURED AND IS `None` UNTIL THEY HAVE. See the module
    header: the one number available to derive it from is a catalog constant that
    under-states the parcel, and under-stated postage is charged at the far end. `None`
    renders as an empty cell, which Pirate Ship shows as a blank the operator can fill for
    every row at once.

    `stamps` ARE OPAQUE AND THIS MODULE RENDERS NO LABEL. `Box 3 · Card 31` is a rendering of a
    physical location, and since D58 a card's number counts the cards in the box rather than
    the slots, so drawing one needs the box's whole occupancy — `pipeline/join.py:Position`
    is the only label formula in this repo and a second one here would be the
    second-renderer failure it has already recorded three times. What arrives is a string
    somebody else composed, and it is written out unchanged.

    NO LENGTH IS ENFORCED ON A STAMP, BECAUSE NOBODY HAS MEASURED ONE. Pirate Ship prints
    these in a label corner and there is certainly a practical limit; this project has not
    established it, and a truncation at an invented number would silently cut the end off a
    pick instruction — `Box 3 - C3` for `Box 3 · Card 31` is a wrong shelf rather than an
    obviously broken one. Too many stamps is a different case and refuses, because that
    one is knowable from the format: there are three columns.
    """

    name: str
    address: str
    city: str
    state: str
    zipcode: str
    country: str
    order_id: str
    address2: str = ""
    weight: Optional[str] = None
    stamps: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stamps", tuple(str(s) for s in self.stamps))
        if len(self.stamps) > STAMP_LIMIT:
            raise MalformedParcel(
                f"order {self.order_id}: {len(self.stamps)} rubber stamps, "
                f"and the label has {STAMP_LIMIT} corners for them"
            )

    @classmethod
    def from_parts(
        cls,
        first_name: str,
        last_name: str,
        **fields,
    ) -> "Parcel":
        """Build a parcel from a first and last name held in separate columns.

        THE PRE-JOIN THE MODULE HEADER ARGUES FOR, in one place. `" ".join` over the
        non-empty halves rather than an f-string, so a record carrying only one of them
        produces `Buyer001` and not `Buyer001 ` with a trailing space that survives into
        the printed label.
        """
        name = " ".join(part for part in (str(first_name).strip(), str(last_name).strip()) if part)
        return cls(name=name, **fields)


def to_row(parcel: Parcel) -> Dict[str, str]:
    """One parcel as the cells that will be written. Every column, blanks included."""
    row = {column: "" for column in COLUMNS}
    row[NAME_COLUMN] = parcel.name
    row[ADDRESS_COLUMN] = parcel.address
    row[ADDRESS2_COLUMN] = parcel.address2
    row[CITY_COLUMN] = parcel.city
    row[STATE_COLUMN] = parcel.state
    row[ZIP_COLUMN] = parcel.zipcode
    row[COUNTRY_COLUMN] = parcel.country
    row[WEIGHT_COLUMN] = "" if parcel.weight is None else str(parcel.weight)
    row[ORDER_ID_COLUMN] = parcel.order_id
    for column, stamp in zip(STAMP_COLUMNS, parcel.stamps):
        row[column] = stamp
    return row


def check_no_insurance(row: Dict[str, str]) -> None:
    """Raise if this row carries an insurance column.

    Runs on the way out of `render`, over every row, against the row's own keys — so a row
    that reached the writer by some path other than `to_row` still has to satisfy it. That
    is `tcgcsv.check_only_writable_changed`'s shape and it is the same argument: the rule
    that matters is the one the bytes have to pass, not the one the constructor happens to.
    """
    for column in row:
        original = _REFUSED_FOLDED.get(_folded(column))
        if original is not None:
            raise InsuranceRefused(
                f"{column!r} matches the refused column {original!r}: insurance is the "
                "owner's per-order choice inside Pirate Ship and is never written here"
            )


def render(parcels: Iterable[Parcel]) -> bytes:
    """Serialize to the import's byte format. Returns bytes; writes nothing.

    Bytes rather than a path so that a caller handling buyer PII may hand the file straight
    over without it landing on a disk. `write_csv` is the one that writes, and only where
    it is told.
    """
    rows = [to_row(parcel) for parcel in parcels]
    for row in rows:
        check_no_insurance(row)
        extra = set(row) - set(COLUMNS)
        if extra:
            raise MalformedParcel(f"columns not in the import format: {sorted(extra)}")

    buf = io.StringIO(newline="")
    buf.write(",".join(COLUMNS))
    buf.write(LINE_TERMINATOR)
    writer = csv.writer(
        buf,
        quoting=csv.QUOTE_ALL,
        quotechar='"',
        doublequote=True,
        lineterminator=LINE_TERMINATOR,
    )
    for row in rows:
        writer.writerow([row[column] for column in COLUMNS])
    return buf.getvalue().encode(ENCODING)


def write_csv(path, parcels: Sequence[Parcel]) -> bytes:
    """Render and write. The bytes are returned as well as written."""
    data = render(parcels)
    Path(path).write_bytes(data)
    return data
