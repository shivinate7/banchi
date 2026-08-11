"""T2 — Fixture round-trip.

Load fixtures/sv09_export_untouched.csv, fill `Add to Quantity` and `TCG Marketplace Price`
on sample rows, write, re-parse.

Pass: exactly 2 fields differ; unquoted header, quoted data fields, CRLF.

Those three format properties are the whole of what "the byte format is preserved" means
here — an unquoted header row, fully quoted data fields, CRLF line endings. There is no
fourth thing implied by the phrase.

fixtures/staged-import-accepted.csv is the oracle, and it is a stronger one than it looks:
its two rows are byte-for-byte the corresponding rows of sv09_export_untouched.csv with
only the two writable columns changed (`Add to Quantity` 0 -> 1, `TCG Marketplace Price`
'' -> 9.99). So the test does not merely check that the writer's output *looks like* the
accepted format — it reproduces the exact file TCGplayer's Import to Staged accepted, from
the export, through the pipeline writer. Any drift in quoting, line endings, decimal
formatting or column order fails on a byte compare.

The format profile is also measured independently, by a hand-rolled scanner that does not
call the writer (pipeline/tcgcsv.scan_records) — if the writer and the checker shared a
parser, a bug in it would pass twice.

After any real import, use TCGplayer's Export From Staged button and diff it against the
pipeline's intended output — a machine-checkable round trip against the real system, and
the highest-value finding from Gate A.
"""

from __future__ import annotations

import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from pipeline import tcgcsv

NAME = "T2"
DESCRIPTION = "Fixture round-trip preserves byte format"
PASS_CRITERIA = "exactly 2 fields differ; unquoted header, quoted data fields, CRLF"

SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"
ACCEPTED_FIXTURE = "fixtures/staged-import-accepted.csv"
WRITABLE_COLUMNS = ("Add to Quantity", "TCG Marketplace Price")
LINE_TERMINATOR = "\r\n"

REPO_ROOT = Path(__file__).resolve().parents[2]

# The two SKUs in the accepted file, and what TCGplayer accepted for them.
ACCEPTED_SKUS = ("8607749", "8607759")
ACCEPTED_QUANTITY = 1
ACCEPTED_PRICE = "9.99"

# Sample rows to fill, chosen for the things that break naive writers:
#   8608674  "Billy & O'Nare"      apostrophe and ampersand in the product name
#   8608679  "Billy & O'Nare"      the reverse-holo SKU of the same card
#   8608859  "Articuno - 161/159"  secret rare; the only sample with a pre-existing
#                                  TCG Marketplace Price (25.9900), so the test covers
#                                  overwriting a populated cell, not just an empty one
#   8607459  "Accelgor"            an ordinary row with every optional field empty
SAMPLES = {
    "8608674": (2, Decimal("0.40")),
    "8608679": (4, Decimal("0.40")),
    "8608859": (1, Decimal("22.03")),
    "8607459": (3, Decimal("0.40")),
}


def _first_difference(actual: bytes, expected: bytes) -> str:
    for offset, (a, b) in enumerate(zip(actual, expected)):
        if a != b:
            lo = max(0, offset - 40)
            return (
                f"first difference at byte {offset}\n"
                f"  expected: ...{expected[lo:offset + 40]!r}\n"
                f"  actual:   ...{actual[lo:offset + 40]!r}"
            )
    return f"identical for {min(len(actual), len(expected))} bytes, lengths differ: " \
           f"actual {len(actual)}, expected {len(expected)}"


def run() -> Result:
    c = Checks()

    source_path = REPO_ROOT / SOURCE_FIXTURE
    accepted_path = REPO_ROOT / ACCEPTED_FIXTURE
    source_bytes = source_path.read_bytes()
    accepted_bytes = accepted_path.read_bytes()
    digests_before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (source_path, accepted_path)
    }

    # --- the oracle's own byte format, measured rather than assumed -------------------
    oracle = tcgcsv.inspect(accepted_bytes)
    c.note(f"oracle {ACCEPTED_FIXTURE}: {oracle.signature}")
    c.ok(not oracle.header_quoted, "oracle: header row unquoted")
    c.equal(oracle.unquoted_data_fields, 0, "oracle: every data field quoted, incl. empties")
    c.equal(oracle.line_terminator, "CRLF", "oracle: CRLF line endings")
    c.ok(oracle.ends_with_terminator, "oracle: final record CRLF-terminated")
    c.ok(not oracle.has_bom, "oracle: no BOM")

    # --- the export parses, and the header is the documented one ---------------------
    export = tcgcsv.parse(source_bytes, source=source_path)
    c.equal(export.header, tcgcsv.CANONICAL_HEADER, "export header matches the schema")
    c.equal(len(export.rows), 341, "export row count")

    # --- no-op round trip: read 341 rows, write them back, expect the same bytes ------
    rewritten = tcgcsv.render(export.header, export.rows)
    c.ok(
        rewritten == source_bytes,
        "untouched export round-trips byte-identical (341 rows)",
        _first_difference(rewritten, source_bytes),
    )

    # --- reproduce the accepted import file, byte for byte ---------------------------
    by_sku = export.by_sku()
    produced = tcgcsv.render(
        export.header,
        [
            tcgcsv.set_writable(
                by_sku[sku],
                add_to_quantity=ACCEPTED_QUANTITY,
                marketplace_price=ACCEPTED_PRICE,
            )
            for sku in ACCEPTED_SKUS
        ],
    )
    c.ok(
        produced == accepted_bytes,
        f"pipeline reproduces {ACCEPTED_FIXTURE} byte-for-byte from the export",
        _first_difference(produced, accepted_bytes),
    )

    # --- fill sample rows, write, re-parse -------------------------------------------
    filled = [
        tcgcsv.set_writable(row, *SAMPLES[row[tcgcsv.SKU_COLUMN]])
        if row[tcgcsv.SKU_COLUMN] in SAMPLES
        else row
        for row in export.rows
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "sv09_filled.csv"
        written = tcgcsv.write_csv(out_path, export.header, filled)
        reparsed = tcgcsv.read_export(out_path)

    c.equal(reparsed.header, export.header, "re-parsed header unchanged")
    c.equal(len(reparsed.rows), len(export.rows), "re-parsed row count unchanged")

    # Every row, every column, against the original parse.
    changed_columns = set()
    changed_skus = set()
    sku_column_touched = False
    for before, after in zip(export.rows, reparsed.rows):
        if before[tcgcsv.SKU_COLUMN] != after[tcgcsv.SKU_COLUMN]:
            sku_column_touched = True
        for column in export.header:
            if before[column] != after[column]:
                changed_columns.add(column)
                changed_skus.add(before[tcgcsv.SKU_COLUMN])

    c.equal(changed_columns, set(WRITABLE_COLUMNS), "exactly the two writable columns differ")
    c.equal(changed_skus, set(SAMPLES), "exactly the sample rows differ")
    c.ok(not sku_column_touched, "TCGplayer Id never modified")

    for sku, (quantity, price) in sorted(SAMPLES.items()):
        row = reparsed.by_sku()[sku]
        c.equal(
            (row[tcgcsv.QUANTITY_COLUMN], row[tcgcsv.PRICE_COLUMN]),
            (str(quantity), tcgcsv.format_price(price)),
            f"{sku} {row[tcgcsv.NAME_COLUMN]!r} carries the written values",
        )

    # --- the written file's format matches the oracle's ------------------------------
    profile = tcgcsv.inspect(written)
    c.note(f"output: {profile.signature}")
    c.ok(
        not profile.diff(oracle),
        "written file's byte-format signature matches the oracle's",
        "\n".join(profile.diff(oracle)),
    )
    c.equal(profile.record_count, 341, "written file: 341 data records")
    c.equal(profile.field_count, 341 * 16, "written file: every row has 16 quoted fields")

    # --- the writable-column rule is enforced by the writer, not by discipline --------
    original = export.rows[0]
    c.raises(
        tcgcsv.ReadOnlyColumn,
        lambda: tcgcsv.check_only_writable_changed(
            original, dict(original, **{tcgcsv.SKU_COLUMN: "9999999"})
        ),
        "a tampered TCGplayer Id is refused",
    )
    c.raises(
        tcgcsv.ReadOnlyColumn,
        lambda: tcgcsv.check_only_writable_changed(
            original, dict(original, **{tcgcsv.MARKET_PRICE_COLUMN: "0.01"})
        ),
        "a tampered read-only column is refused",
    )
    c.ok(
        tcgcsv.check_only_writable_changed(
            original, tcgcsv.set_writable(original, 4, Decimal("0.40"))
        )
        is None,
        "the two writable columns are allowed to change",
    )
    c.raises(
        tcgcsv.MalformedCsv,
        lambda: tcgcsv.render(("A,B", "C"), []),
        "writer refuses a header field that would need quoting",
    )

    # --- fixtures are ground truth: unchanged on disk --------------------------------
    c.ok(
        all(
            hashlib.sha256(p.read_bytes()).hexdigest() == digest
            for p, digest in digests_before.items()
        ),
        "fixtures unmodified on disk",
    )

    return c.result()
