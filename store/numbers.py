"""A card's number, in the three forms this repo has ever needed: composed, screen-drawn,
and stripped of a glued set code. No imports beyond the stdlib, on purpose (D63).

WHY THIS IS A LEAF MODULE UNDER `store/` AND NOT LEFT IN `pipeline/join.py`. `store/` may
not import `pipeline/` — D63's own argument (`docs/decisions/D063-…md`, and
`docs/map.py`'s `pipeline/orders.py` entry: "store/ imports nothing from pipeline/, so
there is no cycle") — because the arrow runs the other way: `pipeline/orders.py`,
`pipeline/readings.py` and `pipeline/selection.py` all import `store`, and a cycle through
`store -> pipeline -> store` would be exactly the shape that rule exists to forbid.
`store/master.py:_card_columns` and `store/db.py:_add_search_index` (store-scaling item 8)
both need `join_key`/`display_number` to populate the `number_key`/`number_display`
columns without re-deriving the zfill/set-code-strip rules a third time — CLAUDE.md's "one
fold, both sides" (D55/D67) — so the fold itself moves to where both sides can reach it
without crossing the one edge this repo does not allow.

`pipeline/join.py` imports these three names back and re-exports them under the same
spelling (`from store.numbers import join_key, display_number, strip_set_code`), so every
existing caller of `join.join_key` / `join.display_number` / `join.strip_set_code` —
`server/capture_server.py`, `identify/prompt.py`, `harness/tests/t1_id_eval.py`,
`harness/tests/t3_join_coverage.py` — is unchanged. `number_index_key` (the CATALOG-MATCH
form, never confused with the composition form here) stays in `pipeline/join.py`: it folds
against `pipeline/games.py`'s per-game rules and has no reason to be a leaf.
"""

from __future__ import annotations

import re
from typing import Optional

# THREE BOUNDS DO THE WORK AND EACH ONE IS LOAD-BEARING (D55, D67):
#   letters only   `T02 // T03` starts with a token carrying digits, so the 13 double-sided
#                  cells are untouched — and they are what a slash rule would otherwise have to
#                  reason about. `SP3/006` is excluded for the same reason.
#   at least two   One Piece prints 16 cells of the form `P-044`: ONE letter, a hyphen, digits.
#                  A lower bound of one would strip every one of them down to `044`. This is the
#                  bound that keeps a per-game rule from being necessary.
#   at most five   Nothing measured needs more, and an unbounded run of letters would start
#                  eating names the day something hands this a title by mistake.
_SET_CODE_PREFIX = re.compile(r"^[A-Za-z]{2,5}\s*[•·/-]\s*")


def join_key(number, printed_total) -> str:
    """zfill(3)(number) + "/" + printedTotal. `161/159` is a secret rare, not an error.

    THE COMPOSITION FORM, WHICH IS NOT THE COMPARISON FORM. This builds the key a human
    reads and a report prints, in the shape `CLAUDE.md` documents. Matching against the
    export goes through `pipeline/join.py:number_index_key`, on BOTH sides, and that is the
    function that decides whether two spellings are the same card. Same split
    `pipeline/join.py:normalize_set` already makes a few lines down from its own copy of
    this docstring: a label to show, and a fold to compare.
    """
    return f"{str(number).strip().zfill(3)}/{str(printed_total).strip()}"


def display_number(number, printed_total=None) -> Optional[str]:
    """The number a SCREEN draws: unpadded, blank-safe, and with a glued set code removed.

    THE THIRD MEMBER OF A FAMILY THE TWO OTHERS ALREADY DESCRIBE. `join_key` is the
    composition form a report prints and a lookup is built from; `number_index_key`
    (`pipeline/join.py`) is the comparison form that decides whether two spellings are one
    card; this is the form an eye reads. Three strings, three jobs, one fold — and this one
    exists because it was previously written three times in TypeScript and each copy was
    different.

    NO `zfill`, for `ReviewQueue.tsx`'s own reason, kept here now that the composition is the
    server's: padding would put a string on screen that nothing in the run ever said.

    BLANK IS ABSENT, ON BOTH HALVES, WHICH IS THE DEFECT D67 OPENED ON. The two client copies
    tested `printed_total === null` one line below a test of `number` for null OR blank, and
    the store writes `""` on **174 of 676 numbered records** — every Riftbound card, which
    prints one identifier and has no denominator. Those took the else branch and rendered
    `198/219/`: a separator with nothing behind it, on a quarter of the store. One emptiness
    test for both halves, written once, is the whole of the repair.

    NULL RATHER THAN A PLACEHOLDER when there is no number at all. The caller decides what an
    absent number looks like — `none` in a fact row, nothing in a list — and a formatter that
    chose for them would put that word into a table cell that wanted a blank.
    """
    left = strip_set_code(number)
    if not left:
        return None
    right = str(printed_total or "").strip()
    return f"{left}/{right}" if right else left


def strip_set_code(text) -> str:
    """`UNL - 150/219` -> `150/219`, and everything else back unchanged. D55's shape, published.

    THE SHAPE IS D55'S AND IS NOT RE-ARGUED HERE; what D67 adds is a second reader. That entry
    bounded the rule to two-to-five letters, no digits, then one separator, and licensed it by
    measuring: over every distinct `Number` cell in all four committed exports — 190 SV09, 786
    wide Pokemon, 1,236 Riftbound, 395 One Piece, **2,607 between them** — it matches ZERO. Over
    the owner's own 676 numbered records it changes exactly **10**, and all ten are the glued
    reads it exists to remove.

    UNCONDITIONAL, WHERE `pipeline/join.py:_repair_set_code` FIRES ONLY ON A MISS, and the
    difference is not a weakening of D55's second safety. That safety is about a JOIN: an
    identifier that already matched a catalog row is never handed to the repair, so no
    repair can move a card that was listing correctly. A screen has no catalog and therefore
    no miss to gate on — the gate is the shape alone — and the worst a wrong strip can do
    here is draw a shorter string than the model returned. The record still holds the raw
    read, `identifications.json` still holds it, and the run report still counts the repair
    as `code~:`, which is the rate D55 says to watch.

    NOT A REPAIR OF THE STORE, and that is the option D67 rejected rather than missed.
    Normalising at capture would rewrite what the model said into the record, and D36 makes the
    photograph and the read the durable facts — a store that has been tidied cannot tell you the
    prompt is being ignored 1.5% of the time.
    """
    return _SET_CODE_PREFIX.sub("", str(text or "").strip()).strip()
