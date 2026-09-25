"""A card's number, in the four forms this repo has ever needed: composed, screen-drawn,
stripped of a glued set code, and decomposed. No imports beyond the stdlib, on purpose (D63).

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
from typing import Optional, Tuple

# THREE BOUNDS DO THE WORK AND EACH ONE IS LOAD-BEARING (D55, D67):
#   letters only   `T02 // T03` starts with a token carrying digits, so the 13 double-sided
#                  cells are untouched — and they are what a slash rule would otherwise have to
#                  reason about. `SP3/006` is excluded for the same reason.
#   at least two   One Piece prints 16 cells of the form `P-044`: ONE letter, a hyphen, digits.
#                  A lower bound of one would strip every one of them down to `044`. This is the
#                  bound that keeps a per-game rule from being necessary.
#   at most five   Nothing measured needs more, and an unbounded run of letters would start
#                  eating names the day something hands this a title by mistake.
#
# A FOURTH SHAPE, ADDED BY D234: the separator can be a plain space
# with no punctuation at all (`SPD 208/221`), which the original three bounds did not cover
# because they required one of `•·/-` between the letters and the digits. The
# space-only branch requires an actual space (`\s+`, never `\s*`) immediately before a
# digit, which is what keeps it from also matching a real printed-code cell that has NO
# separator at all — `OP15-079`, `EB04-042` — where the digit follows the letters directly.
# MEASURED, THE SAME WAY D67 LICENSED THE ORIGINAL THREE: over the same 2,607 distinct
# `Number` cells across all four committed exports (190 SV09, 786 wide Pokemon, 1,236
# Riftbound, 395 One Piece), the widened regex matches ZERO that the original did not —
# same zero the original scored. Against the owner's own store, read-only, 2026-09-20: of
# 3,299 numbered records, the original regex changes 163; the widened one changes 205 — 41
# newly caught, all of them a letters-space-digits shape (`SFD 007/221`, `SPD 208/221`,
# `UNL 029/219`, `OGN 019/298`, ...), none of them a real printed code losing a character.
_SET_CODE_PREFIX = re.compile(r"^[A-Za-z]{2,5}(?:\s*[•·/-]\s*|\s+(?=\d))")


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
    the owner's own 676 numbered records (at that measurement) it changed exactly **10**, and
    all ten were the glued reads it exists to remove.

    D234 WIDENS THE SEPARATOR TO ALSO ACCEPT A BARE SPACE
    (`SPD 208/221`), re-measured the same way: still ZERO across the four committed exports,
    and 41 additional real cases on the owner's own store (3,299 numbered records as of
    2026-09-20), none of them a real printed code — see `_SET_CODE_PREFIX`'s own comment for
    the exact counts and why the space branch cannot eat `OP15-079`.

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


def split_catalog_number(text) -> Tuple[Optional[str], Optional[str]]:
    """The reverse of `join_key`: a catalog row's own `Number` cell, taken apart into the
    pair a card record stores.

    BUILT FOR D252'S AMENDMENT, THE FOURTH FORM THIS MODULE'S DOCSTRING NAMES.
    Every other writer of `card.number`/`card.printed_total` reads them off a MODEL
    identification, which already returns the two as separate fields — `cli/resolve.py`'s
    `identification.get("number")` / `identification.get("printed_total")`. A catalog row
    carries no such split: `_catalog_row`'s own `"number"` key is `row[tcgcsv.NUMBER_COLUMN]`,
    the whole composed cell — `"074/219"`, already zero-padded, because that column is
    `join_key`'s own OUTPUT shape (`join_key`'s docstring: "Built from pokemontcg.io data,
    matched against the Number column"). `POST /inventory/<box>/<index>/correct` (D252,
    amended) is the first writer that ever needed to go the other way: a human chose the
    ROW, and the row's number becomes the stored fact, but the store still wants it in the
    two-field shape `number_key`/`number_display` are built from (`store/master.py:
    _card_columns`, `server/capture_server.py:_card_number_key`) — both guarded on
    `card.number AND card.printed_total` being truthy. Storing the composed cell whole in
    `card.number` and leaving `card.printed_total` untouched (or stale from the WRONG catalog
    row this is correcting away from) would either double the denominator
    (`join_key("074/219", "219")` -> `"074/219/219"`) or carry forward a denominator that
    belongs to the card this correction is replacing.

    SPLIT ON THE LAST `/`, NEVER THE FIRST. Every fixture's `Number` cell (SV09, wide
    Pokemon, Riftbound, One Piece) puts the denominator after the one slash the cell
    contains, and a secret rare's own numerator can itself look like `302*` — no slash of
    its own — so there is never a second one to prefer the first over.

    A CELL WITH NO `/` IS A DENOMINATOR-LESS GAME'S OWN IDENTIFIER, whole
    (`"OP15-054"`, `"EB03-018"`) — `printed_total` comes back `None`, and the guard above
    then leaves `number_key` empty for it, which `pipeline/pricearchive.py`'s own comment
    already documents as the designed state for a game with no denominator: "`number_key`
    IS EMPTY BY DESIGN FOR A GAME WITH NO DENOMINATOR ... this falls back to the bare
    `number`" — and the bare `number` this leaves behind IS the whole identifier, so that
    fallback still reads correctly.

    A BLANK CELL RETURNS `(None, None)`, matching `_catalog_row`'s own `""` for a blank
    `Number` — nothing to compose from nothing.

    ROUND-TRIPS THROUGH `join_key` FOR EVERY CASE MEASURED: `join_key(*split_catalog_number(
    "074/219"))` == `"074/219"`, and the same for `"145a/219"`, `"302*/298"` and
    `"161/159"` (a secret rare, `join_key`'s own worked example — exceeding the denominator
    is not treated as invalid here either, because nothing here reasons about the two parts'
    relative size).
    """
    raw = str(text or "").strip()
    if not raw:
        return None, None
    if "/" not in raw:
        return raw, None
    number, _, total = raw.rpartition("/")
    number = number.strip()
    total = total.strip()
    if not number:
        return raw, None
    return number, (total or None)


def box_title(name: Optional[str], number: int) -> str:
    """A box's name for a label or a sentence: the stored name, or `Box <number>` without one.

    THE FALLBACK IS THE DEFAULT NAME THE STORE WRITES, NOT A SECOND VOCABULARY. The owner's
    ruling, 2026-09-23 (D-a-box-is-shown-by-its-name): an unnamed box gets the stored name
    `Box <count+1>` at creation, a cleared name stores the same default, and every box that
    had no name was backfilled `Box <number>` (`store/master.py:Inventory.default_box_name`,
    `Inventory.backfill_box_names`). So no registered box reaches this fallback after the
    backfill. A caller with no registry to ask (T3, T4 and T5 build a bare
    `Position(box, index)`) still gets the string the backfill stored for that box.

    A LEAF HERE, NOT IN `pipeline/join.py`, for this module's own reason: `store/master.py`
    names a box in its refusals and may not import `pipeline/` (D63). `pipeline/join.py`
    imports it back under the same name.
    """
    text = (name or "").strip()
    return text if text else f"Box {int(number)}"
