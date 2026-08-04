"""TCGplayer Filtered CSV — read, write, and byte-format inspection.

Byte format, confirmed against a real SV09 export and against the 2-row file TCGplayer's
Import to Staged accepted verbatim (`fixtures/staged-import-accepted.csv`):

  - header row: UNQUOTED
  - data fields: fully quoted, every field, including empties ("")
  - line endings: CRLF, including after the final record
  - no BOM

Exactly two columns are ever written: `Add to Quantity` and `TCG Marketplace Price`.
`TCGplayer Id` is the SKU the import matches on and is never modified. `set_writable` is
the only way to change a cell in this module, and it refuses every other column — a rule
enforced by a function cannot be forgotten by a caller.

Real CSV library only (v1 bug #2): product names carry commas, apostrophes and ampersands
("Billy & O'Nare"), so `split(",")` corrupts them silently.

`scan_records` deliberately re-implements field splitting rather than calling csv.reader.
It is the independent half of T2: if the writer and the format checker shared a parser, a
bug in that parser would pass the test twice.
"""

from __future__ import annotations

import codecs
import csv
import io
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

CANONICAL_HEADER: Tuple[str, ...] = (
    "TCGplayer Id",
    "Product Line",
    "Set Name",
    "Product Name",
    "Title",
    "Number",
    "Rarity",
    "Condition",
    "TCG Market Price",
    "TCG Direct Low",
    "TCG Low Price With Shipping",
    "TCG Low Price",
    "Total Quantity",
    "Add to Quantity",
    "TCG Marketplace Price",
    "Photo URL",
)

SKU_COLUMN = "TCGplayer Id"
QUANTITY_COLUMN = "Add to Quantity"
PRICE_COLUMN = "TCG Marketplace Price"
MARKET_PRICE_COLUMN = "TCG Market Price"
LOW_PRICE_COLUMN = "TCG Low Price"  # `--basis=low`; never the threshold, which reads Market
LIVE_QUANTITY_COLUMN = "Total Quantity"
SET_COLUMN = "Set Name"
NUMBER_COLUMN = "Number"
NAME_COLUMN = "Product Name"
CONDITION_COLUMN = "Condition"

WRITABLE_COLUMNS: Tuple[str, ...] = (QUANTITY_COLUMN, PRICE_COLUMN)

LINE_TERMINATOR = "\r\n"
LINE_TERMINATOR_BYTES = b"\r\n"
ENCODING = "utf-8"

Row = Dict[str, str]


class MalformedCsv(Exception):
    """The bytes are not the format this module contracts to read or write."""


class ReadOnlyColumn(Exception):
    """An attempt to write a column that is not one of WRITABLE_COLUMNS."""


# --------------------------------------------------------------------------- reading


@dataclass(frozen=True)
class Export:
    """A parsed export. `rows` are plain str->str; nothing is coerced on read."""

    header: Tuple[str, ...]
    rows: Tuple[Row, ...]
    source: Optional[Path] = None

    def by_sku(self) -> Dict[str, Row]:
        index: Dict[str, Row] = {}
        for row in self.rows:
            sku = row[SKU_COLUMN]
            if sku in index:
                raise MalformedCsv(f"duplicate {SKU_COLUMN} in source: {sku}")
            index[sku] = row
        return index


def parse(data: bytes, source: Optional[Path] = None) -> Export:
    if data.startswith(codecs.BOM_UTF8):
        raise MalformedCsv("unexpected UTF-8 BOM; the real export has none")

    text = data.decode(ENCODING)
    reader = csv.reader(io.StringIO(text, newline=""))
    records = list(reader)
    if not records:
        raise MalformedCsv("empty file")

    header = tuple(records[0])
    rows: List[Row] = []
    for lineno, record in enumerate(records[1:], start=2):
        if len(record) != len(header):
            raise MalformedCsv(
                f"line {lineno}: {len(record)} fields, header has {len(header)}"
            )
        rows.append(dict(zip(header, record)))

    return Export(header=header, rows=tuple(rows), source=source)


def read_export(path) -> Export:
    path = Path(path)
    return parse(path.read_bytes(), source=path)


# --------------------------------------------------------------------------- writing


def _check_header(header: Sequence[str]) -> None:
    # The header is written unquoted, so a comma or quote in a name would corrupt the
    # file rather than being escaped. Fail loudly instead.
    for name in header:
        if any(ch in name for ch in ',"\r\n'):
            raise MalformedCsv(f"header field needs quoting, cannot be written raw: {name!r}")


def render(header: Sequence[str], rows: Iterable[Row]) -> bytes:
    """Serialize to the exact byte format TCGplayer accepted."""
    _check_header(header)
    columns = list(header)

    buf = io.StringIO(newline="")
    buf.write(",".join(columns))
    buf.write(LINE_TERMINATOR)

    writer = csv.writer(
        buf,
        quoting=csv.QUOTE_ALL,
        quotechar='"',
        doublequote=True,
        lineterminator=LINE_TERMINATOR,
    )
    for index, row in enumerate(rows):
        extra = set(row) - set(columns)
        if extra:
            raise MalformedCsv(f"row {index}: columns not in header: {sorted(extra)}")
        missing = [c for c in columns if c not in row]
        if missing:
            raise MalformedCsv(f"row {index}: missing columns: {missing}")
        writer.writerow([row[c] for c in columns])

    return buf.getvalue().encode(ENCODING)


def write_csv(path, header: Sequence[str], rows: Iterable[Row]) -> bytes:
    data = render(header, rows)
    Path(path).write_bytes(data)
    return data


def check_only_writable_changed(before: Row, after: Row) -> None:
    """Raise unless `after` differs from `before` only in WRITABLE_COLUMNS.

    The rule as a function rather than as a comment. `set_writable` runs it on the way
    out, and the emitter runs it again on every row it is about to write, against that
    row's catalog original — so a row that reached the file by some other path still has
    to satisfy it. `TCGplayer Id` is what the import matches on; a modified SKU does not
    fail, it lists the wrong card.
    """
    illegal = sorted(
        column
        for column in set(before) | set(after)
        if column not in WRITABLE_COLUMNS and before.get(column) != after.get(column)
    )
    if illegal:
        raise ReadOnlyColumn(
            "not writable: "
            + ", ".join(
                f"{c} {before.get(c)!r} -> {after.get(c)!r}" for c in illegal
            )
        )


def set_writable(
    row: Row,
    add_to_quantity: Optional[object] = None,
    marketplace_price: Optional[object] = None,
) -> Row:
    """Return a copy of `row` with only the two writable columns changed.

    The only supported way to modify a cell. Everything else round-trips byte-identical,
    `TCGplayer Id` above all.
    """
    updated = dict(row)
    if add_to_quantity is not None:
        updated[QUANTITY_COLUMN] = str(add_to_quantity)
    if marketplace_price is not None:
        updated[PRICE_COLUMN] = (
            marketplace_price
            if isinstance(marketplace_price, str)
            else format_price(marketplace_price)
        )
    check_only_writable_changed(row, updated)
    return updated


def format_price(value) -> str:
    """Two decimals, half-up. TCGplayer accepted "9.99"; money is never a float."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_price(value: str) -> Optional[Decimal]:
    value = (value or "").strip()
    if not value:
        return None
    return Decimal(value)


def parse_quantity(value: str) -> int:
    value = (value or "").strip()
    return int(value) if value else 0


# ------------------------------------------------------------------ format inspection


@dataclass(frozen=True)
class FormatProfile:
    has_bom: bool
    line_terminator: str  # "CRLF" | "LF" | "CR" | "mixed" | "none"
    ends_with_terminator: bool
    header_quoted: bool
    unquoted_data_fields: int
    record_count: int
    field_count: int

    @property
    def signature(self) -> Dict[str, object]:
        """The format-only attributes. Row and field counts differ between two valid
        files, so they are reported but never compared."""
        return {
            "has_bom": self.has_bom,
            "line_terminator": self.line_terminator,
            "ends_with_terminator": self.ends_with_terminator,
            "header_quoted": self.header_quoted,
            "all_data_fields_quoted": self.unquoted_data_fields == 0,
        }

    def diff(self, other: "FormatProfile") -> List[str]:
        mine, theirs = self.signature, other.signature
        return [
            f"{key}: {mine[key]!r} != {theirs[key]!r}"
            for key in mine
            if mine[key] != theirs[key]
        ]


def scan_records(data: bytes) -> Iterator[List[Tuple[bytes, bool]]]:
    """Split CSV bytes into records of (raw value, was_quoted).

    Hand-rolled on purpose — see the module docstring. Strict about separators: a bare LF
    or CR between records raises rather than being tolerated, because tolerating it is how
    a file stops being CRLF without anyone noticing.
    """
    i, n = 0, len(data)
    record: List[Tuple[bytes, bool]] = []

    while i < n:
        quoted = data[i : i + 1] == b'"'
        if quoted:
            i += 1
            chunks: List[bytes] = []
            while True:
                j = data.find(b'"', i)
                if j == -1:
                    raise MalformedCsv("unterminated quoted field")
                if data[j + 1 : j + 2] == b'"':  # escaped quote
                    chunks.append(data[i : j + 1])
                    i = j + 2
                    continue
                chunks.append(data[i:j])
                i = j + 1
                break
            value = b"".join(chunks)
        else:
            j = i
            while j < n and data[j : j + 1] not in (b",", b"\r", b"\n"):
                j += 1
            value = data[i:j]
            i = j

        record.append((value, quoted))

        if data[i : i + 1] == b",":
            i += 1
            continue
        if data[i : i + 2] == LINE_TERMINATOR_BYTES:
            i += 2
            yield record
            record = []
            continue
        if i >= n:
            break
        raise MalformedCsv(
            f"byte {i}: expected ',' or CRLF, found {data[i : i + 1]!r}"
        )

    if record:
        yield record


def inspect(data: bytes) -> FormatProfile:
    """Structural profile of a CSV payload, derived without the writer's help."""
    has_bom = data.startswith(codecs.BOM_UTF8)
    body = data[len(codecs.BOM_UTF8) :] if has_bom else data

    crlf = body.count(LINE_TERMINATOR_BYTES)
    lf = body.count(b"\n")
    cr = body.count(b"\r")
    if crlf and lf == crlf and cr == crlf:
        terminator = "CRLF"
    elif not crlf and lf:
        terminator = "LF"
    elif not crlf and cr:
        terminator = "CR"
    elif not (crlf or lf or cr):
        terminator = "none"
    else:
        terminator = "mixed"

    split = body.find(LINE_TERMINATOR_BYTES)
    if split == -1:
        raise MalformedCsv("no CRLF-terminated header row")
    header_line = body[:split]
    data_section = body[split + 2 :]

    records = list(scan_records(data_section))
    fields = [field for record in records for field in record]

    return FormatProfile(
        has_bom=has_bom,
        line_terminator=terminator,
        ends_with_terminator=body.endswith(LINE_TERMINATOR_BYTES),
        header_quoted=b'"' in header_line,
        unquoted_data_fields=sum(1 for _, was_quoted in fields if not was_quoted),
        record_count=len(records),
        field_count=len(fields),
    )
