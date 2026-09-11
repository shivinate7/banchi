"""What a run's tokens cost — the price sheet, and the one place it is applied.

THREE READERS, ONE IMPLEMENTATION, WHICH IS THE WHOLE REASON THIS IS A MODULE. The preflight
estimates before a send (`cli/cmd_identify.py:_estimate`), the collect records what the send
actually used, and `server/pipeline_routes.py:_usage` fills the figure in for a run written
before the field existed. `_parse_preflight` states the rule this file exists to keep: "A
second implementation of the cost model here would be a number that can disagree with the one
in the log, and the operator would have no way to tell which had drifted."

DEPENDENCY-FREE ON PURPOSE. `server/pipeline_routes.py` imports this at module scope and that
module's own rule is stdlib-only there — verified under bare /usr/bin/python3. `decimal` is
all this reaches, and `identify/__init__.py` is a docstring with no imports in it, so the
server pays nothing for the package either.

AND NOT LIFTED FROM THE LOG, WHICH IS WHAT THE PREFLIGHT DOES. The preflight's figure is read
back out of the command's own stdout because the whole stdout is on the wire. A finished run's
console is a 20,000-byte TAIL (`_console_tail`), and the report prints its token counts BEFORE
the per-card refusal lists — so a 544-card run with a few hundred refusals pushes the line out
of the window. The manifest is the only durable store, and this is what writes it.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Claude Haiku 4.5, halved for the Batch API's 50% discount (confirmed 2026-08-03):
#
#     base input  $1 / MTok  ->  $0.50
#     output      $5 / MTok  ->  $2.50
#
# The arithmetic is written out because the halving is the part that looks like a typo. Two
# columns of the price sheet are deliberately unused: prompt caching is not wired here, so
# no request pays a cache-write rate and none gets a cache-hit rate. The system prompt IS
# identical across every request in a batch and could in principle be cached — but images
# dominate the input (a 1568px card is several times the system prompt), so the saving is
# small and the complexity is not free. Recorded so a later session sees a decision rather
# than an oversight.
INPUT_PER_MTOK = Decimal("0.50")
OUTPUT_PER_MTOK = Decimal("2.50")

MILLION = Decimal(1_000_000)

# SIX PLACES, WHICH IS FINER THAN A CENT ON PURPOSE. A run that spent a third of a cent is a
# real run and `0.00` is not the honest rendering of it, so nothing here rounds to money's own
# unit: the screen decides how to SAY a figure and this decides what the figure IS. Six is
# enough to make the float land clean through JSON and coarse enough that it never carries
# arithmetic noise.
PLACES = Decimal("0.000001")


def usd(input_tokens: int, output_tokens: int) -> Decimal:
    """What those tokens cost at the rates above. Exact; the caller quantizes for its use."""
    return (
        Decimal(int(input_tokens)) * INPUT_PER_MTOK
        + Decimal(int(output_tokens)) * OUTPUT_PER_MTOK
    ) / MILLION


def recorded(input_tokens: int, output_tokens: int) -> float:
    """The figure as a manifest holds it and a screen reads it.

    ONE FUNCTION FOR THE WRITE AND FOR THE BACKFILL, so a run whose figure the server filled
    in is byte-identical to what that run would have written for itself. Two call sites that
    each did their own quantize-and-float would agree today and be one edit from not.

    A FLOAT AND NOT A `Decimal`, because `store/files.py:write_json` is a bare `json.dumps`
    with no `default=` — a `Decimal` raises `TypeError` at the flush.
    """
    return float(usd(input_tokens, output_tokens).quantize(PLACES, rounding=ROUND_HALF_UP))
