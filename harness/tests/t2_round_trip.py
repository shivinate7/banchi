"""T2 — Fixture round-trip.

Load fixtures/sv09_export_untouched.csv, fill `Add to Quantity` and `TCG Marketplace Price`
on sample rows, write, re-parse.

Pass: exactly those two fields differ, and the byte format is preserved —
  - unquoted header row
  - fully quoted data fields
  - CRLF line endings

Assert against fixtures/staged-import-accepted.csv, which TCGplayer accepted verbatim.

To implement:
  - Python `csv` module. Never split(",") — v1 bug #2.
  - `TCGplayer Id` is never modified. Every column other than the two above must
    round-trip byte-identical.
  - Fixtures are read-only: copy to a temp path, never write in place. Enforced by
    scripts/guard-opsec.sh and by the settings.json deny rules.
  - Schema details (Condition strings, blank-Number rows, apostrophes in names) live in
    the `tcgplayer-csv` skill. Load it before writing this.

After any real import, use TCGplayer's Export From Staged button and diff it against the
pipeline's intended output — a machine-checkable round trip against the real system, and
the highest-value finding from Gate A.
"""

from harness.tests import NotImplementedYet, Result

NAME = "T2"
DESCRIPTION = "Fixture round-trip preserves byte format"
PASS_CRITERIA = "exactly 2 fields differ; unquoted header, quoted data fields, CRLF"

SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"
ACCEPTED_FIXTURE = "fixtures/staged-import-accepted.csv"
WRITABLE_COLUMNS = ("Add to Quantity", "TCG Marketplace Price")
LINE_TERMINATOR = "\r\n"


def run() -> Result:
    raise NotImplementedYet(
        "NOT_IMPLEMENTED: no CSV writer yet (build-order step 5)"
    )
