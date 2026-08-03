"""T3 — Join coverage.

For a batch of identified cards, every card matches exactly one fixture row for its
resolved condition string. Report unmatched in BOTH directions before any output is
written.

Pass: zero unmatched, or unmatched reported and output suppressed.

Required cases (docs/GATES.md):
  - Secret rares where the number exceeds the denominator (161/159)
  - Blank-`Number` rows (name-matching fallback)
  - Names with apostrophes and ampersands (Billy & O'Nare)
  - 7 identical cards -> one row, `Add to Quantity` = 4, 3 recorded as backstock

To implement:
  - Join key is zfill(3)(number) + "/" + printedTotal, from pokemontcg.io data. Never
    join on Product Name — it inconsistently embeds numbers.
  - Duplicates aggregate by SKU at join time (D7). Live quantity caps at 4 per SKU;
    excess is backstock at known positions.
  - Never emit duplicate SKU rows in an import file — undefined behavior.
  - Never silently drop a card. Ambiguity goes to the review queue with its photo.

Guards v1 bug #5: CSV import matched by box+position, silently skipped identified cards,
and reported nothing for unmatched rows. Bidirectional reporting is the whole point of
this test — a one-directional check would have passed on that bug.
"""

from harness.tests import NotImplementedYet, Result

NAME = "T3"
DESCRIPTION = "Catalog join covers every card, unmatched reported both ways"
PASS_CRITERIA = "zero unmatched, or unmatched reported and output suppressed"

LIVE_QUANTITY_CAP = 4


def run() -> Result:
    raise NotImplementedYet(
        "NOT_IMPLEMENTED: no catalog join yet (build-order step 5)"
    )
