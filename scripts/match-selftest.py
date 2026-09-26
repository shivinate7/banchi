#!/usr/bin/env python3
"""`make match-selftest` — the one forgiving matcher, proved against the shared case table.

WHY THIS EXISTS. FLT-06/04 (the owner's ruling, 2026-09-23) is one matcher everywhere. The
filtering lane wrote `app/src/kit/match.ts` and the case table that proves it,
`app/src/kit/match.cases.json`. `server/match.py` is a same-behaviour Python port
(UX-173) — this script is what proves the two agree, and what proves the SERVER'S OWN
search (`_match_rank`, `_fts_query`) actually reaches the fix rather than merely having a
correct module sitting unused beside it.

THREE GROUPS OF CASES, in the order this file was built:

  1. `case_match_py_agrees_with_every_row` — every row of `match.cases.json` through
     `server/match.py:match_query` directly. This is "the Python matcher passes every row
     of app/src/kit/match.cases.json" from the lane brief, literally.
  2. `case_match_rank_*` — `capture_server._match_rank`, called directly against
     constructed `store.master.Card` rows, for the three defects that live IN THE RANK
     STEP: a bare `54` wrongly matching the longer number `154/200` (rule 4, "never a
     substring"), a hyphen standing for the slash (`054-132`), and an accented name found
     by its unaccented spelling (`flabebe` finding `Flabébé`) once the candidate step has
     already surfaced the row.
  3. `case_do_search_*` — `capture_server.do_search`, end to end, against a real temporary
     store (`PKMNSCAN_HOME`). This is the group that reproduces UX-173's own headline
     defect, "`54/132` finds nothing": `_match_rank` alone was never the bug there (a
     zero-padded number field always contains its own unpadded form as a Python
     substring), the FTS5 CANDIDATE step was — a bare `54/132` or a hyphenated
     `054-132`/`heimerdinger-inventor` never reached `_match_rank` at all, because no
     token the index holds starts with either spelling. Only a real SQLite FTS5 index can
     show that, which is why this group needs a store and the other two do not.
  4. `case_do_search_runs_the_shared_case_table` — S2, the Opus review, 2026-09-25.
     GROUP 1 PROVES `match.py` AGAINST THE TABLE; IT NEVER PROVES `do_search` READS
     `match.py` AT ALL. Before this fix `do_search` computed its own candidate/rank
     answer through `_fts_query`/`_match_rank` alone and never called `match_query` —
     so a case only group 1 could see (the pair-matched `swsh 050`, a `#`/`/`-led
     number, a hyphen or apostrophe folded to one glued word) could pass group 1 and
     still find nothing through the real route a screen calls. This group runs every
     row of `match.cases.json` THROUGH `do_search`, against a real store, one card per
     row built from the row's own `fields`. Three shapes in the table are not a claim
     about `do_search` at all and are read, never asserted: a `boxes` row (do_search
     never searches a box by name — that is the client's own `useSearch`), a
     multi-`text` row (the store's own `condition` field, likewise client-only), and a
     blank-query row (`do_search` refuses an empty `q` by contract, `_require_query`).
     `ventor` (rule 7's mid-word substring, `"izard"` finding `"Charizard"` in T7's own
     words) is read and reported, never asserted, because store-scaling item 8 measured
     that loss and the owner took it explicitly — `check_search_fts5` in
     `harness/tests/t7_store_and_seams.py` is the test that already protects it, and
     "fixing" `do_search` to find `ventor` would break that settled trade-off, not close
     a bug. See `scripts/match-selftest.py:CASE_TABLE_INPUT_NEEDED`.

MUTATION-PROOF, THE WAY THIS REPO PROVES A GUARD: run `git show <pre-fix>:server/
capture_server.py > /tmp/old.py`, swap it in over `server/capture_server.py`, run this
script and watch group 2 and group 3 go red, then restore the fixed file and watch them go
green. That is a one-time verification a session performs and reports (BUILD-BRIEF's own
"show it with a .bak copy" instruction); it is not a step this file repeats on every run,
which is why there is no `.bak` file read here — this script tests the code AS IT STANDS.

STDLIB PLUS THE PROJECT'S OWN PACKAGES ONLY. `PKMNSCAN_HOME` is a fresh temp directory per
case (`fresh_home`, the exact idiom `scripts/cid-selftest.py` established), so the real
store is never opened for reading or for writing.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CASES_PATH = REPO / "app" / "src" / "kit" / "match.cases.json"

PASS = 0
FAIL = 0
MADE: List[Path] = []


def ok(what: str) -> None:
    global PASS
    PASS += 1
    print(f"  ok     {what}")


def bad(what: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL   {what}")


def check(condition: bool, what: str) -> bool:
    (ok if condition else bad)(what)
    return bool(condition)


def equal(got, want, what: str) -> bool:
    if got == want:
        return ok(what) or True
    bad(f"{what}\n           got  {got!r}\n           want {want!r}")
    return False


def fresh_home() -> Path:
    """A throwaway `PKMNSCAN_HOME`, one per case — `scripts/cid-selftest.py:fresh_home`'s
    own idiom, so a leftover from a previous case can never make the next one unreadable."""
    where = Path(tempfile.mkdtemp(prefix="pkmnscan-match."))
    MADE.append(where)
    os.environ["PKMNSCAN_HOME"] = str(where)
    (where / "inventory").mkdir(parents=True, exist_ok=True)
    return where


def cleanup() -> None:
    for where in MADE:
        shutil.rmtree(where, ignore_errors=True)


# --------------------------------------------------------------------- group 1: match.py


def case_match_py_agrees_with_every_row() -> None:
    """`server/match.py` against every row of the case table the filtering lane wrote —
    "the Python matcher passes every row of app/src/kit/match.cases.json"."""
    from server import match

    cases = json.loads(CASES_PATH.read_text("utf-8"))
    check(len(cases) > 0, f"the case table has rows ({CASES_PATH})")
    for i, case in enumerate(cases):
        got = match.match_query(case["query"], case["fields"])
        equal(
            got, case["match"],
            f"case {i} ({case['note']}): query={case['query']!r}",
        )


# ------------------------------------------------------------------ group 2: _match_rank


def _card(**fields):
    from store import master

    return master.Card(box=1, index=1, **fields)


def case_match_rank_never_treats_a_number_as_a_bare_substring() -> None:
    """Rule 4: "never a substring: `54` does not find `154/200`". A raw `.lower()`/`in`
    comparison over the `number` field finds it anyway, because `"54" in "154"` is true in
    Python — this is the false positive UX-173's own case table exists to catch."""
    from server import capture_server as cs

    card = _card(name="X", number="154", printed_total="200")
    equal(
        cs._match_rank(card, "54"), None,
        "'54' does not match a card whose number is 154/200",
    )
    equal(
        cs._match_rank(card, "154/200"), cs._RANK_EXACT_NUMBER,
        "and the card's own number, typed in full, still matches exactly",
    )


def case_match_rank_folds_a_hyphen_standing_for_the_slash() -> None:
    """`054-132` reads the same as `054/132` — rule 4's hyphen rule, ported to the rank
    step's own number comparison."""
    from server import capture_server as cs

    card = _card(name="Abra", number="054", printed_total="132")
    equal(
        cs._match_rank(card, "054-132"), cs._RANK_EXACT_NUMBER,
        "a hyphen between two digits stands for the collector-number slash",
    )


def case_match_rank_folds_accents() -> None:
    """`flabebe` (typed without the accent) finds `Flabébé` — the accent-fold bug UX-173
    names as living in the rank step, once the FTS5 candidate step has already folded the
    same way and surfaced the row."""
    from server import capture_server as cs

    card = _card(name="Flabébé")
    rank = cs._match_rank(card, "flabebe")
    check(rank is not None, "'flabebe' matches a card named Flabébé")


def case_match_fold_text_strips_every_mark_by_category() -> None:
    """F7, round-3 Opus review, 2026-09-25, correcting D271's own earlier note. A "ccc-0"
    mark — canonical combining class zero, a SPACING mark such as Devanagari's own vowel
    signs (U+093E, category Mc) — is still a Unicode MARK, and `kit/match.ts:foldText`
    deletes every mark outright (`\\p{M}`, which covers Mn/Mc/Me alike). The old
    `unicodedata.combining(ch) != 0` test answered a narrower question (a character's
    canonical combining class) and left a ccc-0 mark in the string, where it became a
    WORD BREAK instead of vanishing: `fold_text('a\\u093eb')` was `'a b'`, two words,
    where the browser folds the identical string to `'ab'`, one.
    """
    from server import match

    value = "aाb"
    equal(
        match.fold_text(value), "ab",
        "a ccc-0 spacing mark (U+093E, category Mc) is stripped, not turned into a space",
    )


def case_match_query_stays_fast_on_repeated_tokens() -> None:
    """F1, BLOCKING (round-3 Opus review, 2026-09-25). `_cover` tried both the
    single-token and the pair branch at every position, and each branch recursed into
    the rest of the tokens — the same `at` got solved again from scratch by every path
    that reached it, growing like Fibonacci. `("132 " * 27 + "/132 /999")` against a
    card whose number is `132/132` measured at 3.9s (the review's own number); this
    machine measured 7.8s before the memoization fix. Asserted against a bound generous
    enough to survive a slower CI runner but nowhere near the un-memoized cost, so a
    regression here fails LOUD rather than merely slow.
    """
    from server import match

    fields = {"numbers": ["132/132"]}
    query = "132 " * 27 + "/132 /999"
    start = time.monotonic()
    result = match.match_query(query, fields)
    took = time.monotonic() - start
    equal(result, False, "27 repeated '132' tokens plus two unmatched ones do not cover")
    check(
        took < 1.0,
        f"match_query on 26 terms took {took:.3f}s, under the 1.0s bound "
        "(un-memoized: 3.9-7.8s measured)",
    )


def case_match_digit_tests_are_ascii_only() -> None:
    """S4, the Opus review, 2026-09-25. `kit/match.ts`'s `\\d` is JS syntax, and JS's `\\d`
    is always `[0-9]` — the `u` flag on its own regexes widens `\\p{L}`, never `\\d`. Python's
    bare `\\d` and `str.isdigit()` are Unicode-aware, so a real Unicode decimal digit outside
    ASCII (`５` folds to `5` via NFKC before either side sees it; a Devanagari digit does
    not) would count as a digit on the server and stay inert text in the browser — the one
    place this repo's own two-implementation contract could silently disagree.
    """
    from server import match

    devanagari_five = "५"  # DEVANAGARI DIGIT FIVE — real Unicode digit, NFKC leaves it
    equal(
        match._has_digit(devanagari_five), False,
        "a Unicode digit outside ASCII does not count as a digit",
    )
    equal(
        match._has_digit("5"), True,
        "and an ASCII digit still does",
    )
    check(
        match._DIGITS_ONLY.match(devanagari_five) is None,
        "and `_DIGITS_ONLY` refuses it the same way",
    )


# -------------------------------------------------------------------- group 3: do_search


def case_do_search_finds_a_padded_number_typed_without_its_zeros() -> None:
    """UX-173's own headline defect, reproduced end to end against a real FTS5 index:
    `54/132` found nothing for a card stored as `054/132`, because the CANDIDATE step
    never surfaced it — `_match_rank` was never reached. Only a real store shows this;
    `_match_rank` in isolation already handles it (a zero-padded number always contains
    its own unpadded form as a Python substring), which is why group 2 above cannot."""
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Abra", number="054", printed_total="132", sku="9999")
        snapshot.inventory.cards["1/1"] = card

    for query in ("54/132", "054/132", "54", "054-132"):
        skus = [g["sku"] for g in cs.do_search(query)["groups"]]
        check("9999" in skus, f"do_search({query!r}) finds the card stored as 054/132")


def case_do_search_finds_a_number_with_more_leading_zeros_than_typed() -> None:
    """F8, round-3 Opus review, 2026-09-25: "card numbers with or without leading zeros"
    (the owner's own ruling). `_zero_padded_variant`'s FTS widening only covers a term of
    1 or 2 digits — it pads to `zfill(3)`, the width `store/numbers.py:join_key` always
    composes — so a 3+ digit query got no widening at all. `q=934` found nothing for a
    card whose number is the WIDER `0934`, a real printed number on some games rather
    than a `zfill(3)` artifact. Symmetric: `q=0934` must also find a card stored as the
    bare `934`, and `q=934` must still refuse an unrelated card stored as `1934` — never
    a substring, the same rule 4 the padded-number case above already protects.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Big Number Card", number="0934", sku="7700")
        decoy = master.Card(box=1, index=2, name="Unrelated", number="1934", sku="9001")
        snapshot.inventory.cards["1/1"] = card
        snapshot.inventory.cards["1/2"] = decoy

    for query in ("934", "0934"):
        skus = [g["sku"] for g in cs.do_search(query)["groups"]]
        check("7700" in skus, f"do_search({query!r}) finds the card stored as 0934")
        check(
            "9001" not in skus,
            f"do_search({query!r}) does not find the unrelated card stored as 1934",
        )

    # AN EQUALITY CHECK, NEVER A PREFIX ONE (R1, round-4 Opus review, 2026-09-25;
    # regression-checked again, round-5). `LTRIM(col, '0') LIKE '1%'` (the original bug,
    # for a query of `001`) matched nearly every numbered card in the store — any stored
    # number starting with `1` once its own zeros are stripped, not only the one the
    # query names. Checked directly against the CANDIDATE function, not through
    # `do_search`'s own decisive `match.match_query` check, which already refuses this
    # false positive downstream either way (see `case_do_search_hostile_repeated_terms_
    # stay_fast_on_real_names`'s own `("001 " * 50)` timing case for what an over-broad
    # candidate set actually costs — extra work, not a wrong final answer).
    with Store().write() as snapshot:
        decoy154 = master.Card(box=1, index=3, name="Decoy 154", number="154", sku="9002")
        snapshot.inventory.cards["1/3"] = decoy154
    from store import db, files

    conn = db.connect(files.inventory_dir())
    try:
        cands = dict(cs._fts_supplemental_candidates(conn, "001"))
    finally:
        conn.close()
    check(
        "1/3" not in cands,
        "the zero-pad widening does not offer a card numbered 154 as a candidate for "
        "'001' (bare('154')='154', never equal to bare('001')='1' — a prefix check "
        "would wrongly offer it, since '154' starts with '1')",
    )


def case_do_search_finds_a_whole_number_second_half() -> None:
    """F2, round-3 Opus review, 2026-09-25. `_fts_slash_candidates` scanned only
    `cards.number_key`, which is EMPTY when either half is missing —
    `join_key(number, printed_total)` refuses to compose without both. Riftbound keeps
    its whole printed identifier in `number` alone with no separate denominator
    (CLAUDE.md: "One Piece and Riftbound match the printed identifier verbatim... Both
    carry denominator-less rows"), so a card stored as `023/221` has `number == "023/221"`
    and `number_key == ""`. `q=/221` found nothing for it, while `match.match_query`
    itself already accepted the row once given the chance — the candidate step, not the
    matcher, was the gap. The PADDED-NUMBER case above always splits `number`/
    `printed_total` apart, so its own green proved only that shape.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(
            box=1, index=1, name="A Riftbound Card", number="023/221", sku="8800",
            game="riftbound",
        )
        snapshot.inventory.cards["1/1"] = card

    skus = [g["sku"] for g in cs.do_search("/221")["groups"]]
    check("8800" in skus, "do_search('/221') finds a card whose whole number is 023/221")


def case_do_search_never_returns_a_row_the_shared_matcher_rejects() -> None:
    """F3, round-3 Opus review, 2026-09-25. `q=#8926367` returned an unrelated card
    whose SKU is exactly `8926367`, and `match.match_query('#8926367', ...)` says
    False for that same card — 95 `#`-prefixed queries did this against the owner's
    store. `_fts_query_variants` strips a leading `#` to widen the FTS5 candidate
    step (S2's own fix for `#54`), and `_match_rank`'s SUBSTRING pass folds `#8926367`
    to `8926367` too and finds it inside the SKU field as a bare substring — but
    `match.py:_sku_match` requires the RAW token to be `_SKU_SHAPE` (`^[0-9]{3,}$`),
    which `#8926367` is not, so the shared matcher correctly refuses it.
    `_match_rank`'s substring/prefix ranks are no longer enough to accept a row on
    their own; only its literal EXACT-NUMBER check still can, for the one shape
    `match.py` structurally cannot express (a code card's own redemption code).
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(
            box=1, index=1, name="Heimerdinger, Inventor", number="3", printed_total="25",
            sku="8926367",
        )
        snapshot.inventory.cards["1/1"] = card

    skus = [g["sku"] for g in cs.do_search("#8926367")["groups"]]
    check(
        "8926367" not in skus,
        "do_search('#8926367') does not find a card whose SKU merely CONTAINS "
        "8926367 once the # is folded away — match_query itself refuses this row",
    )


def case_do_search_midword_agrees_with_match_query() -> None:
    """R4, round-4 Opus review, 2026-09-25. `_fts_substring_candidates_for_term`'s first
    version compared a Python-folded QUERY against a RAW, unfolded `name` column — so an
    accented, apostrophed or hyphenated name never surfaced as a candidate no matter what
    `match.match_query` itself would say. A fuzz found 167 misses; these six are the ones
    the review named. Folding the COLUMN side too (in Python, since SQLite has no
    `unicodedata`) closes the gap — see the function's own docstring for the fix and why
    it needs BOTH the spaced fold and the compact fallback, matching `match.py:
    _text_match`'s own two paths.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    cases = [
        ("Flabébé", "abebe"),
        ("Farfetch'd", "etchd"),
        ("Ho-Oh ex", "ooh"),
        ("Porygon-Z", "gonz"),
        ("Charizard ex", "zardex"),
        ("Akali, Deadly Duelist", "adlyduel"),
    ]
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for i, (name, _) in enumerate(cases):
            card = master.Card(box=1, index=i + 1, name=name, sku=str(720000 + i))
            inv.cards[f"1/{i + 1}"] = card

    for i, (name, query) in enumerate(cases):
        sku = str(720000 + i)
        found = [g["sku"] for g in cs.do_search(query)["groups"]]
        check(sku in found, f"do_search({query!r}) finds {name!r}")


def case_do_search_short_midword_terms_never_full_scan() -> None:
    """R3, round-4 Opus review, 2026-09-25 — the owner's own MID-WORD ruling qualified:
    "only if a measurement... says search stays fast". `q=a` measured a 582ms full-table
    scan at 3,000 cards: a 1-2 character fragment matches almost every row, buying nothing
    but cost. The mid-word SUBSTRING rule still refuses anything under 3 characters
    (F6-2, round-7 Opus delta review, 2026-09-25, only widened the SEPARATE number-shaped
    rule's own floor to 2 — never this one, which is genuinely about free TEXT).

    Checked functionally, against `_fts_supplemental_candidates` — the four widenings
    merged into one row walk in round 7 (F6-3), so no single function is left to call
    with `conn=None` and prove a length gate returns before any query runs. A card whose
    name contains `ab` MID-WORD, but does not START with it (so the fold-prefix rule,
    which has no length floor, does not also match it) proves the substring rule's own
    floor still holds: the card is never offered as a candidate for `ab`.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Xabcdef", sku="7100")
        snapshot.inventory.cards["1/1"] = card

    from store import db, files

    conn = db.connect(files.inventory_dir())
    try:
        candidates = dict(cs._fts_supplemental_candidates(conn, "ab"))
    finally:
        conn.close()
    check(
        "1/1" not in candidates,
        "a 2-character term ('ab') never reaches the mid-word substring rule, even "
        "though 'Xabcdef' contains it mid-word — the 3-character floor still holds",
    )


def case_do_search_finds_a_hyphenated_name() -> None:
    """`heimerdinger-inventor` found nothing against `Heimerdinger, Inventor`, because the
    literal hyphenated token is not one the FTS5 index holds — the comma splits the field
    into two separate words at index time."""
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Heimerdinger, Inventor", sku="7000")
        snapshot.inventory.cards["1/1"] = card

    skus = [g["sku"] for g in cs.do_search("heimerdinger-inventor")["groups"]]
    check("7000" in skus, "do_search('heimerdinger-inventor') finds 'Heimerdinger, Inventor'")


# A query this repo has ALREADY, KNOWINGLY, decided `do_search` will not answer — never a
# silent skip. Each entry names the case index in `match.cases.json` and the reason,
# checked at run time against the row it is read against so a re-ordered table cannot let
# a stale reason cover the wrong row.
# EMPTY AS OF MID-WORD (the owner's ruling, 2026-09-25). Case 16 ("mid-word text still
# matches", `ventor` finding `Inventor`) used to sit here: FTS5's prefix-only candidate
# step could never surface a mid-word fragment, and store-scaling item 8's own trade-off
# said not to chase it. The owner reversed that trade-off ("Add mid-word search").
# `_fts_substring_candidates` gets the candidate there now, measured first on a synthetic
# 2,500-card store (`docs/decisions/D271-one-forgiving-search-matcher.md` carries the
# numbers) — case 16 is asserted like every other row below. Kept as an empty dict, not
# deleted, so a future row needing this same escape hatch has the shape ready.
CASE_TABLE_INPUT_NEEDED: Dict[int, Tuple[str, str]] = {}

# Rows the shared table carries for OTHER screens' own client-side matcher — Orders'
# `useSearch`, over an order label — never `do_search`'s. Read, never asserted, the same
# way a `boxes` row is: `do_search` has no order-label field at all, so passing or failing
# it would be an accident of the NAME column's own FTS shape, never a claim about the
# route. Rows built off the SAME literal (`Order 112`) but stating a GENERIC digit-word
# rule (25, 29) are NOT here — they are ordinary name-field cases and stay asserted.
CASE_TABLE_NOT_APPLICABLE = {
    26: "the same digit narrows an order label as it is typed",
    27: "a query typed with its own leading zeros stays literal until they resolve",
    28: "a run of zeros alone never empties the list; it is the order label's own first key",
    30: "a full order label, hyphen and all",
    31: "a partial order label still narrows",
    32: "the wrong day does not match",
}


def case_do_search_runs_the_shared_case_table() -> None:
    """S2, the Opus review, 2026-09-25. Every row of `match.cases.json` through
    `do_search`, one card per row built from the row's own `fields` — see the module
    docstring's group-4 entry for what this proves and why three shapes are read, never
    asserted, and `CASE_TABLE_INPUT_NEEDED` for the one row this repo has decided not to
    chase.
    """
    from store import Store, master
    from server import capture_server as cs

    cases = json.loads(CASES_PATH.read_text("utf-8"))
    for i, case in enumerate(cases):
        fields = case["fields"]
        query, want = case["query"], case["match"]
        note = case["note"]

        if i in CASE_TABLE_INPUT_NEEDED:
            expected_note, reason = CASE_TABLE_INPUT_NEEDED[i]
            if not check(
                note == expected_note,
                f"case {i}'s own note is still {expected_note!r} — "
                "CASE_TABLE_INPUT_NEEDED's row index still points at the right case",
            ):
                continue
            ok(f"case {i} ({note}): INPUT NEEDED, not asserted — {reason}")
            continue

        if i in CASE_TABLE_NOT_APPLICABLE:
            if not check(
                note == CASE_TABLE_NOT_APPLICABLE[i],
                f"case {i}'s own note still matches CASE_TABLE_NOT_APPLICABLE's entry",
            ):
                continue
            ok(f"case {i} ({note}): read, not asserted — an order-label row, "
               "the Orders screen's own client-side matcher, not a `do_search` field")
            continue

        if "boxes" in fields:
            ok(f"case {i} ({note}): read, not asserted — do_search never searches a box "
               "by name (that is the client's own useSearch, not this route)")
            continue
        text = fields.get("text") or []
        if len(text) > 1:
            ok(f"case {i} ({note}): read, not asserted — a multi-`text` row is the "
               "store's own `condition` field beside a name, and `do_search` never "
               "ranks on condition (client-only, like a box name)")
            continue
        if not query.strip().replace(",", ""):
            ok(f"case {i} ({note}): read, not asserted — `do_search` refuses a blank "
               "`q` by contract (`_require_query`), so an empty-query row is not a "
               "claim about what it finds")
            continue

        fresh_home()
        numbers = fields.get("numbers") or []
        skus = fields.get("skus") or []
        number, printed_total = None, None
        if numbers:
            raw = str(numbers[0])
            if "/" in raw:
                number, printed_total = raw.split("/", 1)
            else:
                number = raw
        sku = str(skus[0]) if skus else "TESTSKU00001"
        card = master.Card(
            box=1, index=1, name=(text[0] if text else None),
            number=number, printed_total=printed_total, sku=sku,
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["1/1"] = card

        got_skus = [g["sku"] for g in cs.do_search(query)["groups"]]
        equal(
            sku in got_skus, want,
            f"case {i} ({note}): do_search({query!r}) finds sku={sku!r}: {want}",
        )


def case_do_search_multiword_never_500s_next_to_a_widened_word() -> None:
    """S1, blocking (the Opus review, 2026-09-25). A multi-word query where ANY word gets
    alternatives (a 1-2 digit number, or a hyphen) 500'd with `fts5: syntax error`, because
    FTS5 refuses an implicit AND the moment either side of a bareword join is a
    parenthesized OR-group — measured directly against `sqlite3`'s own fts5 module, both
    orders. `_fts_query`'s old `" ".join(clauses)` was exactly that implicit join; the fix
    writes `AND` explicitly. Every failing shape the review named, reproduced against a
    real card so each one is also a genuine end-to-end request, not just a syntax probe.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(
            box=1, index=1, name="Porygon-Z V", number="054", printed_total="132", sku="9001",
        )
        snapshot.inventory.cards["1/2"] = master.Card(
            box=1, index=2, name="Ho-Oh ex", number="4", printed_total="102", sku="9002",
        )
        snapshot.inventory.cards["1/3"] = master.Card(
            box=1, index=3, name="Pikachu", number="25", printed_total="102", sku="9003",
        )

    for query in (
        "54 132", "4 102", "Ho-Oh ex", "ex ho-oh", "pikachu 54", "25 pikachu",
        "porygon-z v", "x 1-2",
    ):
        try:
            cs.do_search(query)
            ok(f"do_search({query!r}) does not 500")
        except Exception as exc:  # noqa: BLE001 — a raising case IS the failing case
            bad(f"do_search({query!r}) raised {type(exc).__name__}: {exc}")


def case_do_search_refuses_a_query_past_the_length_cap() -> None:
    """F1, BLOCKING. A length cap on top of the memoization fix: `do_search` still runs
    one real SQL scan per term for the slash-suffix and punctuation-fold candidate
    widenings, so a query with thousands of terms is still costly even once `_cover`
    itself is O(tokens). `_require_query` refuses anything over
    `capture_server._QUERY_LENGTH_CAP` characters, named rather than truncated, so a
    caller can tell a refusal from a search that found nothing.
    """
    fresh_home()
    from server import capture_server as cs

    caught = None
    try:
        cs.do_search("x" * (cs._QUERY_LENGTH_CAP + 1))
    except cs.BadRequest as exc:  # noqa: BLE001 — the refusal IS the assertion
        caught = exc
    check(caught is not None, "a query past the length cap refuses rather than running")
    if caught is not None:
        equal(caught.code, "query_too_long", "and the refusal names itself")
    check(
        bool(cs.do_search("x" * cs._QUERY_LENGTH_CAP)),
        "and a query AT the cap still runs — the refusal is strictly OVER it",
    )


def case_do_search_measures_the_length_cap_after_nfkc() -> None:
    """R2, round-4 Opus review, 2026-09-25. A single codepoint can expand under NFKC —
    `"\\ufdfa"` (a compatibility ligature) becomes about 18 characters — so 200 copies of
    it were 200 characters when `_require_query` used to check length, and about 3,600
    once normalized. Checking length BEFORE normalizing let the cap be typed around
    entirely. `_require_query` now normalizes first.
    """
    fresh_home()
    from server import capture_server as cs

    q = "ﷺ" * 200
    check(len(q) == 200, "the raw query is exactly at the OLD, bypassed cap")
    caught = None
    try:
        cs.do_search(q)
    except cs.BadRequest as exc:  # noqa: BLE001 — the refusal IS the assertion
        caught = exc
    check(
        caught is not None,
        "a query that expands past the cap under NFKC refuses, even though its raw "
        "length is at the cap",
    )
    if caught is not None:
        equal(caught.code, "query_too_long", "and the refusal names itself")


def case_do_search_hostile_multiterm_query_stays_fast() -> None:
    """R1, BLOCKING, round-4 Opus review, 2026-09-25. `("a " * 100).strip()` measured
    5.8s at 3,000 cards, and `("001 " * 50).strip()` 1.5s — each of the (undeduplicated)
    terms ran its own O(store) scan, unioned rather than intersected. Both are at or under
    `_QUERY_LENGTH_CAP` (199 characters each), so the length cap alone never bounded this.

    ASSERTED ON WORK DONE (rows_walked), NOT WALL TIME ALONE (F6-6, round-7 Opus delta
    review, 2026-09-25 — see `case_do_search_hostile_repeated_terms_stay_fast_on_real_
    names`'s own docstring for the "cry wolf" finding this answers). A generous wall-time
    backstop stays, nowhere near the unbounded cost, on a store this case builds itself —
    3,200 cards, never the owner's own.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        inv = snapshot.inventory
        for i in range(3200):
            box = 1 + i // 400
            idx = 1 + i % 400
            card = master.Card(
                box=box, index=idx, name=f"Bench Card {i}",
                number=str(i % 300).zfill(3), sku=str(910000 + i),
            )
            inv.cards[f"{box}/{idx}"] = card

    for label, query in (
        ("100 repeated 'a' terms", ("a " * 100).strip()),
        ("50 repeated '001' terms", ("001 " * 50).strip()),
    ):
        cs._reset_search_work_counters()
        start = time.monotonic()
        cs.do_search(query)
        took = time.monotonic() - start
        walked = cs._SEARCH_WORK_COUNTERS["rows_walked"]
        check(
            walked in (0, 1),
            f"{label}: rows_walked={walked} SQL scans against `cards` — 0 or 1, never "
            "a count that grows with the term count",
        )
        check(
            took < 5.0,
            f"do_search over {label} took {took:.3f}s on a 3,200-card store, under the "
            "5.0s backstop (unbounded: 5.8s and 1.5s measured by the review; the "
            "rows_walked check above is this case's real assertion)",
        )


_POKEMON_NAMES = [
    "Pikachu", "Eevee", "Charizard", "Blastoise", "Venusaur", "Gengar",
    "Snorlax", "Gyarados", "Dragonite", "Mewtwo", "Espeon", "Umbreon",
    "Flareon", "Sylveon", "Ho-Oh", "Lugia", "Rayquaza", "Garchomp",
    "Lucario", "Porygon-Z", "Farfetch'd", "Rengar",
]
_SUFFIXES = ["", "ex", "V", "VMAX", "VSTAR"]
_SET_NAMES = ["Base Set", "Obsidian Flames", "Origins", "Jungle", "Fossil", ""]
_SET_TOTALS = [102, 166, 198, 219, 221, 64]  # a SMALL, real-shaped set of totals


def _build_pokemon_store(n: int) -> None:
    """A synthetic store shaped like the owner's real one (F1/F2, round-5 Opus delta
    review, 2026-09-25) — real Pokemon-shaped names with a suffix (`ex`, `V`, `VMAX`,
    `VSTAR`), a real set name, and a SKU where ONE DIGIT PREFIXES MOST of them (`9`, the
    rest `4`), never the placeholder `f"Bench Card {i}"` fixture round 4's own tests
    used.

    SIX NUMBER SHAPES, SEEDED (round-7 Opus delta review, 2026-09-25, F6-4 — this file's
    own fixture was "too easy": a single named card carried each real-store defect, so a
    mutation reverting the fix it existed for could still pass the PERMANENT FUZZ, which
    never happened to query that one card). `random.Random(7)`, matching the reviewer's
    own fuzz harness (`fz.py`) exactly, so both tools measure the SAME store:
      0,1,2  a COMPOSED number, `NNN/MMM`, `printed_total=None` (empty `number_key` —
             R5-2's own real-store shape, most of the owner's 3,510 cards).
      3      a bare number with its own `printed_total` (the old, easy shape).
      4      a LETTER-SHAPED number: `NNNa/MMM`, `RNNa`, `TGNN` or `SWSHNNN` —
             `printed_total=None`. `R01a`-`R06a`/`TG05`/`SWSH022`/`SWSH045`-style, F6-1's
             own real-store finding.
      5      a bare number, `printed_total=None` — no printed total to fall back on.
    `_SET_TOTALS`'s SIX VALUES (matching real Pokemon printed totals) are also what
    R5-1's own `/166 /198 /219 /221` hostile shapes need: with only six distinct totals
    cycling across the WHOLE store, a `/NNN` term for one of them is a real, broad
    candidate — the same shape the owner's own `/132 /298 /166 /198 /219 /221 /1 /2`
    query hit at 552-578ms before R5-1 (F6-5). A UNIFORM total (this file's own earlier
    defect, round 6) made every `/NNN` term match nearly nothing distinctly; a single
    real total shared by 1/6 of the store is what a hostile query needs to be hostile.

    FOUR NAMED CARDS, for the R4/R5/R6 case tables: `Charizard ex` (number `100`, set
    Obsidian Flames — `izard 100` and R5-3's `ex EX Ex eX ob OB fl FL izard` both use
    this card, the second through its own set name), `Ho-Oh ex` (for `ooh ex`),
    `Flabébé V` (for `abebe v`) and a bare `Charizard` (so a query naming `ex` alone
    excludes it)."""
    import random

    from store import Store, master

    rng = random.Random(7)
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for i in range(n):
            box = 1 + i // 400
            index = 1 + i % 400
            name = f"{_POKEMON_NAMES[i % len(_POKEMON_NAMES)]} {_SUFFIXES[i % len(_SUFFIXES)]}".strip()
            shape = i % 6
            n1 = 1 + rng.randrange(299)
            tot = str(rng.choice(_SET_TOTALS))
            p3 = str(n1).zfill(3)
            if shape in (0, 1, 2):
                number, printed_total = p3 + "/" + tot, None
            elif shape == 3:
                number, printed_total = p3, tot
            elif shape == 4:
                number, printed_total = rng.choice([
                    p3 + "a/" + tot,
                    "R" + str(n1 % 9).zfill(2) + "a",
                    "TG" + str(n1 % 30).zfill(2),
                    "SWSH" + p3,
                ]), None
            else:
                number, printed_total = p3, None
            set_hint = rng.choice(_SET_NAMES)
            sku = f"{'9' if i % 7 else '4'}{100000 + i}"
            inv.cards[f"{box}/{index}"] = master.Card(
                box=box, index=index, name=name, number=number,
                printed_total=printed_total, set_hint=set_hint, sku=sku,
            )
        extra = [
            ("Charizard ex", "100", "197", "9500000"),
            ("Ho-Oh ex", "007", "197", "9500001"),
            ("Flabébé V", "013", "197", "9500002"),
            ("Charizard", "050", "197", "9500003"),
            # A LETTER-PREFIXED NUMBER, NAMED (F6-1/M4, round-7 Opus delta review,
            # 2026-09-25). The random shape-4 cards above cover this shape too, but a
            # STANDALONE fixed card guarantees the permanent fuzz always tests the
            # STRIPPED `bare` form of it, deterministically — a randomly drawn shape-4
            # card's own "bare" query is only isolated (not paired with a name term
            # that could surface the row through a DIFFERENT widening instead) when the
            # seeded RNG happens to land there, which round-7's own fixed seed does not
            # reliably do.
            ("Trainer Gallery Card", "TG03", None, "9500004"),
        ]
        for j, (name, number, printed_total, sku) in enumerate(extra):
            box = 1 + n // 400 + 1
            index = j + 1
            inv.cards[f"{box}/{index}"] = master.Card(
                box=box, index=index, name=name, number=number,
                printed_total=printed_total, set_hint="Obsidian Flames", sku=sku,
            )


def _brute_force_matches(text: str) -> set:
    """Every SKU `match.match_query` accepts, read directly off the live snapshot —
    the ground truth `do_search`'s own candidate steps (FTS5 plus the four widenings)
    are only ever narrowing toward. Cards with no SKU are excluded, matching `do_search`'s
    own SKU-grouped answer shape."""
    from store import Store
    from server import capture_server as cs, match

    inventory = Store().read().inventory
    found = set()
    for card in inventory.cards.values():
        if card.sku and match.match_query(text, cs._card_match_fields(card)):
            found.add(str(card.sku).strip())
    return found


def case_deduped_capped_terms_dedupes_and_caps() -> None:
    """F1, round-5 Opus delta review, 2026-09-25. `_deduped_capped_terms` is the ONE
    shared place both `_fts_supplemental_candidates` and `do_search`'s rank loop get their
    term list from — a direct, deterministic check on the function itself, rather than
    only a timing bound on its callers, so a mutation that removes the dedupe or the cap
    is caught exactly, not just "sometimes, on a slow enough case".
    """
    fresh_home()
    from server import capture_server as cs

    equal(
        cs._deduped_capped_terms("a a a b b c"), ["a", "b", "c"],
        "a repeated term is scanned once, first-seen order kept",
    )
    nine = " ".join(f"w{i}" for i in range(9))
    equal(
        cs._deduped_capped_terms(nine), [f"w{i}" for i in range(8)],
        "9 distinct terms cap at 8 (_SUPPLEMENTAL_TERM_CAP), the 9th dropped",
    )
    equal(
        cs._deduped_capped_terms("Ex EX ex", lower=True), ["ex"],
        "lower=True (the rank loop's own case) folds case before deduping",
    )
    equal(
        cs._deduped_capped_terms("Ex EX ex", lower=False), ["Ex", "EX", "ex"],
        "lower=False (the widening step's own case, unchanged by this fix) keeps case, "
        "so 3 differently-cased spellings of the same word are 3 distinct terms here — "
        "each source function folds case itself",
    )


def case_do_search_hostile_repeated_terms_stay_fast_on_real_names() -> None:
    """F1, BLOCKING, round-5 Opus delta review, 2026-09-25, on 65b8f39d — R5-1, round-6,
    on ce5a6168. The rank loop in `do_search` used to compute `term_ranks` (up to 8
    `_match_rank` calls) for EVERY candidate, for every REPEATED term, whether or not
    `match.match_query` had already decided the candidate was real. Measured on a
    real-name fixture (round-4's `f"Bench Card {i}"` fixture never hit this path, and
    round-5's own uniform fixture never made a `/NNN` term broad): `("1 " * 100)` took
    5.6-12.4s at 3,000 cards; the owner's OWN `/132 /298 /166 /198 /219 /221 /1 /2`, on a
    read-only copy of the real store, took 552-578ms for a 63-byte body.

    ASSERTED ON WORK DONE, NOT WALL TIME (F6-6, round-7 Opus delta review, 2026-09-25:
    "a guard that goes red when nothing is wrong is spent"). The wall-time-only version
    of this case went red at load average 16 with no code defect at all — a shared CI
    runner answers "how busy is the machine", never "how much work did this query do".
    `_SEARCH_WORK_COUNTERS`, reset before each query:
      `rows_walked`      COUNTS SQL SCANS, NOT ROWS, via `conn.set_trace_callback` on the
                         connection (round-8, correcting round-7's own version — see
                         `_count_cards_scan`'s docstring for why: a counter incremented
                         inside ONE function's own loop only proves that loop ran, and
                         loading round-6's four separate per-term SQL sources back in
                         stayed green at `rows_walked=0`, because that counter never SAW
                         a different code path's own scans). A connection-level trace
                         counts a `cards` table scan no matter which code issues it, so
                         this is 0 (no widening needed) or 1 (one combined walk) — NEVER
                         a count that grows with the term count, which is F6-3's own
                         claim, now checked against something that can see it break.
      `match_rank_calls` proves R5-1's own fix, counted INSIDE `_match_rank` itself
                         (round-8, correcting round-7's own call-site counter, which a
                         caller-side mutation could defeat without changing how often
                         `_match_rank` actually runs). Mutated (`if True:` in place of
                         `if matched or token_count == 1:`) this measured 11,416 calls
                         for the `/NNN` query alone, against 0 fixed.
      `match_query_calls` bounded at 2x the store's own card count — generous against
                         every legitimate shape measured (at most 1,427), nowhere near
                         what an unbounded per-term blowup would produce.
    Wall time stays as a generous BACKSTOP (5s, over 6x every number either review ever
    measured even unfixed), which still catches a genuine algorithmic regression outright
    — it just never cries wolf over a busy machine alone.
    """
    fresh_home()
    _build_pokemon_store(3000)
    from store import Store
    from server import capture_server as cs

    n_cards = len(Store().read().inventory.cards)
    query_bound = n_cards * 2

    for label, query, rank_bound in (
        ("100 repeated '1' terms", ("1 " * 100).strip(), 200),
        ("100 repeated 'e' terms", ("e " * 100).strip(), n_cards * 2),
        ("66 repeated 'ex' terms", ("ex " * 66).strip(), n_cards * 2),
        # ALSO CATCHES THE ZERO-PAD PREFIX REGRESSION (R1, round-4; re-checked round-5):
        # `_fts_zero_pad_candidates_for_term`'s comparison must be an EQUALITY, never a
        # `LIKE` prefix. A 3+ digit repeated term is what reaches that rule at all.
        ("50 repeated '001' terms", ("001 " * 50).strip(), 200),
        ("8 distinct '/NNN' terms", "/132 /298 /166 /198 /219 /221 /1 /2", n_cards * 2),
        ("a mixed digit/text hostile query", "/198 001 hooh izard ard eon ex v", n_cards * 2),
        # F6-3's OWN SUBJECT, ROUND-8: 8 distinct 3+ letter mid-word terms measured
        # 450-536ms p50, up to 860ms p95 on the real store, before the four widening
        # sources merged into one walk.
        ("8 distinct mid-word terms", "engar ion ard ing ter eon lex ade", n_cards * 2),
    ):
        cs._reset_search_work_counters()
        start = time.monotonic()
        cs.do_search(query)
        took = time.monotonic() - start
        counters = dict(cs._SEARCH_WORK_COUNTERS)
        check(
            counters["rows_walked"] in (0, 1),
            f"{label}: rows_walked={counters['rows_walked']} SQL scans against `cards` "
            "— 0 (no widening needed) or 1 (one combined walk), never a count that "
            "grows with the term count (F6-3)",
        )
        check(
            counters["match_rank_calls"] <= rank_bound,
            f"{label}: match_rank_calls={counters['match_rank_calls']}, at or under "
            f"{rank_bound} (R5-1: the rank loop only ranks a matched row, or a "
            "single-term query)",
        )
        check(
            counters["match_query_calls"] <= query_bound,
            f"{label}: match_query_calls={counters['match_query_calls']}, at or under "
            f"{query_bound} (2x the store's own card count)",
        )
        check(
            took < 5.0,
            f"{label} took {took:.3f}s, under the 5.0s backstop (a generous wall-clock "
            "ceiling — the work-counter checks above are this case's real assertion)",
        )


def case_do_search_rows_walked_is_exactly_one_when_widening_is_needed() -> None:
    """F2, BLOCKING, round-9 Opus delta review, 2026-09-25, on 28d233b2. The hostile
    timing case's own `rows_walked in (0, 1)` check never FORCES the widening branch —
    a query needing zero widening also passes it, so a DISCONNECTED counter (the trace
    removed, or a widening scan moved to a second, untraced connection) could still read
    0 and pass every existing case. This case names a query that MUST widen — a
    mid-word fragment, never reachable through the base FTS index — and asserts
    `rows_walked == 1` exactly, not merely "0 or 1". Removing `_count_cards_scan`'s own
    trace, or moving the widening scan to an untraced `db.connect(...)`, now reads 0
    here and fails.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(box=1, index=1, name="Charizard ex", sku="7900")

    cs._reset_search_work_counters()
    result = cs.do_search("izard")  # mid-word only — base FTS cannot reach it at all
    check("7900" in {g["sku"] for g in result["groups"]}, "the query actually widens and finds the card")
    walked = cs._SEARCH_WORK_COUNTERS["rows_walked"]
    check(
        walked == 1,
        f"rows_walked={walked}, exactly 1 for a query that MUST widen — a disconnected "
        "trace, or a widening scan on an untraced connection, reads 0 here",
    )


def case_do_search_match_rank_calls_has_a_known_floor() -> None:
    """F3, BLOCKING, round-9 Opus delta review, 2026-09-25, on 28d233b2. Every existing
    case asserted only an UPPER bound on `match_rank_calls`, so deleting the counter's
    own increment inside `_match_rank` (round-8's own fix, F6-6 item 3) stayed green at
    183/183 — 0 calls is always at or under any upper bound. A single-term query that
    MATCHES calls `_match_rank` once (`len(terms) == 1`, and the rank loop runs whenever
    `matched or token_count == 1`), giving a known, real, non-zero floor.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(box=1, index=1, name="Gengar", sku="7901")

    cs._reset_search_work_counters()
    result = cs.do_search("gengar")
    check("7901" in {g["sku"] for g in result["groups"]}, "the query actually matches the card")
    calls = cs._SEARCH_WORK_COUNTERS["match_rank_calls"]
    check(calls >= 1, f"match_rank_calls={calls}, at least 1 — a deleted increment reads 0 here")


def case_do_search_match_query_calls_has_a_known_floor() -> None:
    """F3, BLOCKING, round-9 Opus delta review, 2026-09-25, on 28d233b2. Deleting
    `match_query_calls`'s own increment in `do_search`'s rank loop stayed green at
    183/183 — every existing case asserted only an upper bound. Any query that reaches
    the rank loop at all (any base FTS or supplemental hit) calls `match.match_query`
    once per candidate, unconditionally — a known, real, non-zero floor for any query
    with at least one real match.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(box=1, index=1, name="Umbreon", sku="7902")

    cs._reset_search_work_counters()
    result = cs.do_search("umbreon")
    check("7902" in {g["sku"] for g in result["groups"]}, "the query actually matches the card")
    calls = cs._SEARCH_WORK_COUNTERS["match_query_calls"]
    check(calls >= 1, f"match_query_calls={calls}, at least 1 — a deleted increment reads 0 here")


def case_do_search_union_never_drops_a_row_a_single_term_widens() -> None:
    """F2, REGRESSION, round-5 Opus delta review, 2026-09-25, on 65b8f39d.
    `_fts_supplemental_candidates`'s first version INTERSECTED across terms: a query of two
    or more terms required the store's own candidate for EVERY term to agree before either
    term's widening contributed a row. That is wrong whenever only ONE term needs a
    widening — `izard ex` found 20 rows before the intersection existed, 0 after, because
    `izard` (a mid-word fragment) has a supplemental candidate but `ex` (an ordinary token
    the base FTS query already covers on its own) never needs one, so the intersection of
    "what `izard` widened" with "nothing, because `ex` needed no widening" is empty. A
    fuzz found 64 of 300 two-term queries dropped this way. Fixed by a UNION of what each
    term's widenings separately find — the base FTS `hits` dict already carries the real
    AND across terms via one combined `MATCH` expression, so this function only ever adds
    rows, never removes one the base query already found.

    Checked against the BRUTE-FORCE answer (`_brute_force_matches`, every SKU
    `match.match_query` itself accepts), not only against one named SKU — the review's own
    complaint was about DROPPED rows, and a case naming only the SKU it expects would not
    have caught the other 63 the fuzz found either.
    """
    fresh_home()
    _build_pokemon_store(3000)
    from server import capture_server as cs

    for query in ("izard ex", "ex izard", "ooh ex", "abebe v", "izard 100"):
        expected = _brute_force_matches(query)
        got = {g["sku"] for g in cs.do_search(query)["groups"]}
        equal(
            got, expected,
            f"do_search({query!r}) returns every SKU match_query accepts, and no other",
        )
        check(len(expected) > 0, f"{query!r} has at least one real match to prove the case means something")


def case_do_search_zero_pad_matches_a_composed_number() -> None:
    """R5-2, round-6 Opus delta review, 2026-09-25. `_fts_zero_pad_candidates_for_term`
    compared `LTRIM(col, '0') = ?` against the WHOLE column — never matching a card whose
    `number` column holds the COMPOSED form (`027/166`), because `LTRIM` only strips the
    front of that whole string (`27/166`), never equal to a bare `27`. 2,919 of the
    owner's 3,510 real cards keep `number` this way with an empty `number_key`. Measured:
    `q=0027` dropped 3 of 4 real matches, `0217` 5 of 5, `0190` 3 of 3. Fixed by ALSO
    matching `LTRIM(col, '0') LIKE bare || '/%'`.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Compound Number Card", number="027/166", sku="8800")
        snapshot.inventory.cards["1/1"] = card

    expected = _brute_force_matches("0027")
    got = {g["sku"] for g in cs.do_search("0027")["groups"]}
    equal(got, expected, "do_search('0027') finds every SKU match_query accepts, including the composed '027/166'")
    check("8800" in got, "specifically, the composed-number card is found")


def case_do_search_zero_pad_widens_a_digit_plus_letter_term() -> None:
    """R5-5, round-6 Opus delta review, 2026-09-25. `_fts_zero_pad_candidates_for_term`
    floored at `_DIGITS_ONLY` — refusing a term with a trailing letter outright, before
    the function ever ran. `24a` dropped all 8 real matches for a card numbered
    `024a/219` (Rengar). `_ZERO_PAD_SHAPE` (digits, then 0-2 letters) replaces the gate.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Rengar", number="024a/219", sku="9900")
        snapshot.inventory.cards["1/1"] = card

    expected = _brute_force_matches("24a")
    got = {g["sku"] for g in cs.do_search("24a")["groups"]}
    equal(got, expected, "do_search('24a') finds every SKU match_query accepts")
    check("9900" in got, "specifically, the digit-plus-letter number card is found")


def case_do_search_substring_widens_a_two_char_digit_term() -> None:
    """F6-2, STILL OPEN ON THE REAL COPY, round-8 Opus delta review, 2026-09-25 (on
    f2d13ae7 — round 7 lowered only the ZERO-PAD rule's floor, never the SUBSTRING
    rule's). `6a` missed "Order Rune (R06a)" on the real store (2 SKUs), and `1a`
    through `6a` missed 40 real cards combined. `match.match_query` accepts `6a` by
    rule 7's own substring check, which has NO floor at all — the candidate step's own
    3-character floor (borrowed whole from R3, which is about mid-word TEXT) is what
    refused it, even though `_is_floor_query` already treats a digit-bearing 2-character
    term as NOT a floor term. The floor now agrees with that.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="Order Rune (R06a)", sku="9800")
        snapshot.inventory.cards["1/1"] = card

    expected = _brute_force_matches("6a")
    got = {g["sku"] for g in cs.do_search("6a")["groups"]}
    equal(got, expected, "do_search('6a') finds every SKU match_query accepts")
    check("9800" in got, "specifically, 'Order Rune (R06a)' is found")


def case_do_search_number_widening_mirrors_canonical_number() -> None:
    """F1, BLOCKING, round-9 Opus delta review, 2026-09-25, on 28d233b2 — the round-8
    review's OWN CONTRADICTED claim: D271 round-8 item 5 said these shapes checked clean
    ("0 missed", "neither reproduced"). They did not — the builder tested neighbours of
    the reported inputs (`0024a`, a bare `4`), never the exact ones. Re-tested here
    against the exact reported inputs, on the real store: EVERY sampled query of each
    shape missed (bare-letter composed 11/11, extra-zero letter composed 11/11,
    extra-zero plain composed 300/300, zero-padded digit word 1/1).

    THE CAUSE, IN NUMBER NORMALIZATION: the old widening gate,
    `match._number_shape_ok(term)`, checks ONE side of a number only — a term
    containing `/` (`24a/219`, `0027/166`) fails it outright, so no COMPOSED query term
    ever reached any number widening at all. `match._number_match` (the DECISIVE step)
    never had this bug: it already splits on `/` via `match.canonical_number`. Fixed:
    `_number_candidate_forms` computes the SAME canonical forms `match._number_match`
    itself would accept, so the widening step and the decisive step agree.

    THE DIGIT-WORD SHAPE IS A SEPARATE GAP: `004` (or a bare digit like `4`) is
    NUMBER-shaped, so it always reached the zero-pad widening — but that widening only
    ever checked `number_key`/`number`/`number_display`, never `name`/`set_hint`/
    `note`, even though `match_query`'s own rule 7 accepts a digit word in TEXT too.
    Fixed: `_text_digit_word_matches` mirrors `match._digit_word_match` against the
    same three text fields the substring rule already reads.

    THE `#`-PREFIXED COMPOSED SHAPE (round-8's own disclosed gap,
    `case_do_search_known_gap_hash_prefixed_composed_letter_number`, formerly here)
    closes as a SIDE EFFECT of the same fix — `#24a` and `24a/219` now share the one
    canonical-form comparison, so there is nothing left to disclose as a gap. This case
    replaces that one.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    cases = [
        ("Rengar, Unseen", "024a/219", "8801", "24a/219"),
        ("Rengar, Unseen (hash)", "024a/219", "8802", "#24a"),
        ("Hand Hammer", "027/166", "8803", "0027/166"),
    ]
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for i, (name, number, sku, _query) in enumerate(cases):
            inv.cards[f"1/{i + 1}"] = master.Card(box=1, index=i + 1, name=name, number=number, sku=sku)
        # A DIGIT WORD IN NAME TEXT — the card has no useful number of its own, so only
        # the digit-word-in-text widening can ever surface it.
        inv.cards["1/4"] = master.Card(
            box=1, index=4,
            name="While you control this battlefield, when you play a spell, if you spent 4 or more, PREDICT",
            sku="8804",
        )

    for name, number, sku, query in cases:
        found = [g["sku"] for g in cs.do_search(query)["groups"]]
        check(sku in found, f"do_search({query!r}) finds {name!r} ({number!r})")

    found = [g["sku"] for g in cs.do_search("004")["groups"]]
    check("8804" in found, "do_search('004') finds the digit word 'spent 4' in name text")


def case_do_search_comma_and_edge_punctuation_terms_widen() -> None:
    """N1, BLOCKING, round-10 Opus delta review, 2026-09-25, on fdc84825 — the SAME CLASS
    OF BUG as F1, one level up. F1 (round 9) fixed `_number_candidate_forms` to agree
    with `match._number_match`'s own NUMBER comparison. This closes the gap one step
    earlier: `_deduped_capped_terms` split on bare whitespace, but `match.query_tokens`
    (what `match_query`, the decisive step, has always tokenized with) ALSO turns a
    comma into a space and strips edge punctuation per token. `rengar,24a/219` was ONE
    whitespace token the widening step never split, so it could never widen `24a/219`
    out of it — however correct `_number_candidate_forms`'s own comparison already was,
    it was never handed the term.

    MEASURED ON THE REAL STORE (the reviewer's own count, reproduced here with a fixed
    fixture): `rengar,24a/219` and `repel,126/132` missed 60 of 60 sampled; `/221,`
    missed 60 of 60; `/166,` missed all 193 real matches; `004,`, `(004)`, `004.` and
    `unseen,rengar` all missed too. Fixed: `_deduped_capped_terms` (and the rank loop's
    own `token_count`) now tokenize via `match.query_tokens`, the ONE tokenizer the
    decisive step itself uses.

    `_fts_query` (the base FTS5 query) was CHECKED and does NOT need the same change —
    the widening step's own candidates are UNIONED with the base FTS hits before
    `match.match_query` (already correctly tokenized) runs, so a candidate the widening
    step now supplies correctly reaches the decisive check regardless of what the base
    FTS query itself found for a malformed comma-joined string.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        inv = snapshot.inventory
        inv.cards["1/1"] = master.Card(box=1, index=1, name="Rengar, Unseen", number="024a/219", sku="8901")
        inv.cards["1/2"] = master.Card(box=1, index=2, name="Hand Hammer", number="027/166", sku="8902")

    found = [g["sku"] for g in cs.do_search("rengar,24a/219")["groups"]]
    check("8901" in found, "do_search('rengar,24a/219') finds Rengar, Unseen through the comma-split terms")

    found = [g["sku"] for g in cs.do_search("/166,")["groups"]]
    check("8902" in found, "do_search('/166,') finds Hand Hammer through the trailing-comma stripped term")


def case_do_search_hyphen_fold_finds_a_composed_number() -> None:
    """N2, MEDIUM, round-10 Opus delta review, 2026-09-25, on fdc84825. Nothing guarded
    `_number_candidate_forms`'s own hyphen fold (`match._hyphen_to_slash(bare)`, in its
    `forms` set) — removing that one term from the set keeps 192 of 192 `match-selftest`
    cases green, yet `0027-166` (a hyphen standing for the collector-number slash) then
    misses Hand Hammer `027/166`. This case makes that term load-bearing.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(box=1, index=1, name="Hand Hammer", number="027/166", sku="8903")

    found = [g["sku"] for g in cs.do_search("0027-166")["groups"]]
    check("8903" in found, "do_search('0027-166') finds Hand Hammer through the hyphen-to-slash fold")


def case_do_search_fold_deletion_narrowed_bf_to_the_accepted_floor() -> None:
    """F4, round-9 Opus delta review, 2026-09-25, on 28d233b2. Round 8 (item 7) claimed
    the deleted fold-prefix rule's own job was a "strict SUPERSET" of the SUBSTRING
    rule's compact-containment check — false. A DIFFERENTIAL over the real store found
    one real disagreement: `bf` found "B.F. Sword" (`161/221`) through the fold rule
    (which stripped ALL punctuation, including periods, before comparing), and finds
    nothing without it, because `bf` is a 2-character term with no digit — the SAME
    accepted 1-2 character TEXT floor (`_is_floor_query`) every other short text term
    already lives inside. This is that gap, not a new one, and it stays as it is: the
    fold rule's own NO-FLOOR design was the part correctly identified as dead weight,
    never a guarantee that every query it once answered stays answered.
    """
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        snapshot.inventory.cards["1/1"] = master.Card(box=1, index=1, name="B.F. Sword", number="161/221", sku="7903")

    found = [g["sku"] for g in cs.do_search("bf")["groups"]]
    check(
        "7903" not in found,
        "'bf' does not find 'B.F. Sword' — inside the accepted 1-2 character text "
        "floor, unchanged by the fold-prefix rule's own deletion",
    )


def case_do_search_widening_dedupes_case_variants() -> None:
    """R5-3, round-6 Opus delta review, 2026-09-25. `_fts_supplemental_candidates`
    deduped terms CASE-SENSITIVELY: `ex`, `EX`, `Ex` and `eX` counted as 4 distinct terms,
    burning 4 of `_SUPPLEMENTAL_TERM_CAP`'s 8 slots on the SAME word, spelled 4 ways —
    every source function folds case internally anyway, so this never widened anything a
    single lower-cased `ex` would not have. `ex EX Ex eX ob OB fl FL izard` — 8 raw
    spellings of 4 distinct words, plus a 9th distinct word — returned 0 of 15 real
    matches before this fix (the 8-slot cap filled on case variants alone, so `izard`,
    the mid-word term the Charizard ex card needs, never got scanned). Fixed: dedupe on
    the FOLDED (lower-cased) form.
    """
    fresh_home()
    _build_pokemon_store(3000)
    from server import capture_server as cs

    query = "ex EX Ex eX ob OB fl FL izard"
    expected = _brute_force_matches(query)
    got = {g["sku"] for g in cs.do_search(query)["groups"]}
    equal(got, expected, f"do_search({query!r}) finds every SKU match_query accepts")
    check(len(expected) > 0, "the query has at least one real match to prove the case means something")


_FUZZ_HAND_PICKED = [
    "izard", "abebe", "ooh", "gonz", "zardex", "adlyduel", "etchd",
    "izard ex", "ex izard", "ooh ex", "abebe v", "izard 100",
    "charizard", "charizard ex", "pikachu", "eevee v", "gengar vmax",
    "porygon z", "porygonz", "farfetchd", "farfetch'd", "ho oh", "hooh",
    "flabebe", "flabébé", "flabébé v",
    "100", "007", "0007", "013", "0013", "050", "0050", "054", "0054",
    "24a", "024a", "0024a",
    "/100", "/007", "/013", "/050",
    "100/197", "007/197", "013/197",
    "9500000", "9500001", "9500002", "9500003", "950",
    "obsidian", "flames", "obsidian flames", "base set", "jungle",
    "fossil", "team rocket", "neo genesis",
    "ex ex ex", "EX Ex eX", "IZARD", "Izard", "iZaRd",
    "izard v", "izard vmax", "izard vstar",
    "pika", "eve", "gar", "ryu", "dra", "mew", "esp", "umb",
    "1 1", "e e e", "001 001", "a b c d",
    "not a real query at all zzzz",
    "zzzzzzzzz",
    "132/198", "166/198", "219/197", "221/197",
    "9 ex", "izard 9", "izard ex 100",
    "charizard ex obsidian flames", "obsidian flames ex",
    "ex EX Ex eX ob OB fl FL izard",
    "/132 /298 /166 /198 /219 /221 /1 /2",
    "/198 001 hooh izard ard eon ex v",
    # F6-1/M4: a letter-prefixed number (the fixed `TG03` extra card, above), its
    # zeros stripped AFTER the letter (`match._drop_leading_zeros`, never a plain
    # front-only strip). Standalone, so nothing else in the query could surface the
    # row through a different widening.
    "tg3", "TG3",
]
_FUZZ_FLOOR = ["a", "e", "1", "0", "sc", "fl", "ob", "ex", "hi", "on"]  # the 1-2 char floor
_FUZZ_CASE_35 = [",", "  ", " , "]  # case 35's own shape


def _generate_fuzz_queries() -> List[str]:
    """~300 SEEDED query shapes for the permanent fuzz (round-6 Opus delta review,
    2026-09-25). Deterministic (`random.Random(20260925)`), so this list is the SAME
    every run — a fuzz that reshuffles itself on every CI run cannot be reproduced when
    it finds something. Mixes: every Pokemon name's own prefix and a mid-word fragment
    (3-6 characters, reaching `_fts_substring_candidates_for_term`'s own floor), every
    name with every suffix, case-scrambled spellings of a third of those (the exact shape
    R5-3 found — several case variants of the same word), a number sweep (bare,
    zero-padded, slash-prefixed, over every number 1-300 the fixture's own cards carry),
    and two-term combinations pairing a name fragment with a suffix or a number.
    """
    import random

    rng = random.Random(20260925)
    out: List[str] = list(_FUZZ_HAND_PICKED) + list(_FUZZ_FLOOR) + list(_FUZZ_CASE_35)

    for name in _POKEMON_NAMES:
        folded = "".join(ch for ch in name.lower() if ch.isalpha())
        out.append(folded[:4])
        if len(folded) >= 6:
            out.append(folded[1:6])
        for suffix in _SUFFIXES:
            if suffix:
                out.append(f"{name} {suffix}")

    def scramble(word: str) -> str:
        return "".join(ch.upper() if rng.random() < 0.5 else ch.lower() for ch in word)

    for name in _POKEMON_NAMES[:14]:
        folded = "".join(ch for ch in name.lower() if ch.isalpha())
        out.append(scramble(folded[:5]))

    for n in range(1, 301, 12):
        bare = str(n)
        padded = bare.zfill(3)
        out.append(bare)
        out.append(padded)
        out.append(f"/{padded}")
        # COMMA AND EDGE-PUNCTUATION SHAPES (N1, round-10 Opus delta review, 2026-09-25) —
        # `match.query_tokens` strips these, so the widening step must see the same
        # shape the decisive step would.
        out.append(f"{bare},")
        out.append(f"({padded})")
        out.append(f"{padded}.")

    fragments = [name.lower()[:4] for name in _POKEMON_NAMES]
    extras = ["ex", "v", "vmax", "vstar", "100", "013", "050"]
    for _ in range(20):
        out.append(f"{rng.choice(fragments)} {rng.choice(extras)}")
        out.append(f"{rng.choice(fragments)},{rng.choice(extras)}")

    return out


_FUZZ_QUERIES = _generate_fuzz_queries()

# CARD-SAMPLED QUERIES, F6-4 (round-7 Opus delta review, 2026-09-25). The static list
# above is built from `_POKEMON_NAMES`/a number sweep — it never reads what the SEEDED
# fixture actually put on any one card, so it cannot exercise a shape that only exists on
# a randomly-placed card (a letter-PREFIXED number, `R01a`/`TG05`/`SWSH045` — F6-1's own
# finding). M2 and M4 (reverting R5-2's `/%` widening and F6-1's letter-prefix widening)
# turned only the single hand-written cases red, never this fuzz, because nothing in it
# ever asked for THOSE specific cards. `_CUT_POINTS` mirrors the reviewer's own fuzz
# harness (`fz.py`, in the scratchpad) query-shape distribution, sampling a RANDOM CARD
# and building a query from ITS OWN number/name/SKU fields — number as typed, zero-bare,
# re-zero-padded, `#`-prefixed, second-half-only, hyphenated, canonicalized (upper and
# lower), a name substring or prefix, a SKU prefix, a repeated-token stress shape, a
# set-hint-plus-number combination, and a case-scrambled name — so a shape unique to one
# seeded card is queried by number, not by name.
_CUT_POINTS = [
    .10, .17, .22, .26, .30, .33, .36, .39, .42, .45, .52, .56, .60, .65, .68, .71, .74,
    .77, .80, .84, .88, .92, .95,
]


def _generate_card_sampled_queries(cards: list, k: int, seed: int) -> List[str]:
    import bisect
    import random

    from server import match

    rng = random.Random(seed)
    out: List[str] = []
    for _ in range(k):
        card = rng.choice(cards)
        num = str(card.number or "001")
        parts = num.split("/")
        first = parts[0]
        second = parts[1] if len(parts) == 2 else ""
        # LETTER-AWARE, MATCHING `match._drop_leading_zeros` (round-7 Opus delta review,
        # 2026-09-25, F6-4 — a plain `.lstrip("0")` never strips a zero AFTER a leading
        # letter, so it could never build a query exercising F6-1's own widening: `"R03a"
        # .lstrip("0")` is `"R03a"` unchanged, never `"R3a"`. Without this, M4 (reverting
        # F6-1's letter-prefix widening) passed this fuzz — the fuzz itself never asked
        # the right question).
        bare = match._drop_leading_zeros(first) or "0"
        nm = match.compact_text(card.name or "x") or "x"
        kind = bisect.bisect(_CUT_POINTS, rng.random())
        if kind in (4, 5, 6, 7, 20, 21, 22) and not second:
            kind = 0
        i3 = rng.randrange(max(1, len(nm) - 2))
        i1 = rng.randrange(max(1, len(nm) - 1))
        shapes = [
            first, bare, "0" + first, "#" + first, "/" + second, bare + "/" + second,
            first + "-" + second, bare + " " + second, match.canonical_number(first),
            match.canonical_number(first).upper(), nm[i3:i3 + rng.randint(3, 6)],
            nm[i1:i1 + rng.randint(1, 2)], (card.name or "x")[:rng.randint(2, 7)],
            nm[i3:i3 + 4] + " " + rng.choice([first, bare, "ex", "v", "a", "sc"]),
            str(card.sku or "123")[:rng.randint(3, 7)],
            " ".join(rng.choice(["ex", "EX", "Ex", "v", "V", "ru", "rune", "e", "a"]) for _ in range(rng.randint(2, 10))),
            (card.set_hint or "base")[1:6] + " " + first,
            " ".join(match.fold_text(card.name or "x").split()[:rng.randint(1, 3)]) + " " + bare,
            "".join(ch.upper() if rng.random() < 0.5 else ch for ch in nm[:5]),
            " ".join(
                rng.choice(["/" + str(rng.randint(1, 300)), str(rng.randint(1, 300)), "ex", nm[1:5]])
                for _ in range(rng.randint(2, 11))
            ),
            # COMMA AND EDGE-PUNCTUATION SHAPES (N1, round-10 Opus delta review,
            # 2026-09-25) — `match.query_tokens` splits a comma into a space and strips
            # edge punctuation per token; the widening step must agree.
            nm[i3:i3 + rng.randint(3, 6)] + "," + bare + "/" + second,
            "/" + second + ",",
            bare + "-" + second,
            "(" + first + ")",
        ][kind].strip()
        if shapes:
            out.append(shapes)
    return out
# A FLOOR QUERY IS DETECTED, NOT LISTED (round-7 Opus delta review, 2026-09-25). Round
# 6's version excused a fixed SET of literal strings — fine for a static query list, but
# the card-sampled generator (F6-4) produces a different 1-2 character substring on
# almost every run (`nm[i1:i1+1]`/`nm[i1:i1+2]`, kind 11), so a fixed set can never keep
# up. Mirrors the reviewer's own `fz.py:floor_term` exactly: ANY token in the query that
# is 1-2 characters and carries no digit is the SAME accepted gap `_FUZZ_FLOOR`'s own
# entries name — a single such token already misses `match_query`'s own no-floor
# SUBSTRING rule (rule 7), or a zero-pad rule no candidate source widens this short, and
# a query built entirely or partly from repeats of one inherits the identical gap.
_FUZZ_CASE_35_STRIPPED = {q.strip() for q in _FUZZ_CASE_35}


# A REPEATED SHORT DIGIT TERM CAN PAIR-MATCH A ZERO-PADDED NUMBER NO SOURCE WIDENS
# (round-6, still true here — `match_query`'s own PAIR rule joins two adjacent short
# digit tokens into one canonical number, `"1 1"` reading as `"11"`, which can equal a
# stored `"011"` once its zeros are stripped; no candidate source widens a term this
# short to surface it). `fz.py:floor_term` excuses only a NON-digit 1-2 character token,
# so this is a second, narrower gap it would not catch either — named here explicitly,
# never folded into the general floor check.
_FUZZ_ALLOW_LITERAL = {"1 1"}


def _is_floor_query(query: str) -> bool:
    from server import match

    if query.strip() in _FUZZ_CASE_35_STRIPPED or query in _FUZZ_ALLOW_LITERAL:
        return True
    return any(
        len(token) in (1, 2) and not match._has_digit(token)
        for token in match.query_tokens(query)
    )


def case_do_search_permanent_fuzz_agrees_with_match_query() -> None:
    """PERMANENT FUZZ, round-6 Opus delta review, 2026-09-25. Every prior round's own
    hand-picked cases proved only the ONE query shape each round happened to name — round
    4's fixture hid R1/F2, round 5's fixture hid R5-1/R5-2/R5-3/R5-5. This case runs
    `_generate_fuzz_queries`'s ~300 fixed, seeded query shapes (a mix of every kind the
    case table above already covers, plus their case variants, number variants and
    combinations) against a 400-card store, comparing `do_search`'s own answer to
    `_brute_force_matches` (`match.match_query`, the decisive matcher, run directly
    against every card) for EACH ONE. A smaller store than the timing cases use — this
    case's own subject is CORRECTNESS, not speed, and 300 brute-force passes at 3,000
    cards would cost minutes rather than tens of seconds.

    Zero false positives are ever allowed. A missed row is allowed ONLY for a query in
    `_FUZZ_ALLOW`: the 1-2 character floor terms (`_fts_substring_candidates_for_term`'s
    own 3-character floor, the owner's accepted condition — R3, round 4) and case 35's
    own shape (a bare comma or blank, which `do_search` refuses outright, matching
    nothing by contract rather than by the matcher's own rules). Any other missed row, or
    any false positive at all, fails the query and names it.
    """
    fresh_home()
    _build_pokemon_store(400)
    from store import Store
    from server import capture_server as cs

    cards = list(Store().read().inventory.cards.values())
    all_queries = _FUZZ_QUERIES + _generate_card_sampled_queries(cards, 200, 20261001)

    false_positive_queries: List[str] = []
    missed_queries: List[str] = []
    for query in all_queries:
        stripped = query.strip()
        if not stripped:
            continue  # `do_search` refuses a blank query by contract — not this case's subject.
        expected = _brute_force_matches(query)
        got = {g["sku"] for g in cs.do_search(query)["groups"]}
        false_positives = got - expected
        missed = expected - got
        if false_positives:
            false_positive_queries.append(f"{query!r}: {sorted(false_positives)}")
        if missed and not _is_floor_query(query):
            missed_queries.append(f"{query!r}: missed {sorted(missed)}")
    check(
        not false_positive_queries,
        f"0 false positives over {len(all_queries)} seeded queries: {false_positive_queries[:5]}",
    )
    check(
        not missed_queries,
        f"0 missed rows outside the allow set over {len(all_queries)} seeded queries: "
        f"{missed_queries[:5]}",
    )


def case_do_search_still_refuses_an_unrelated_number() -> None:
    """The widened FTS5 candidate query must not turn into a false positive end to end —
    the same rule 4 guarantee as group 2, proved through the real index this time."""
    fresh_home()
    from store import Store, master
    from server import capture_server as cs

    with Store().write() as snapshot:
        card = master.Card(box=1, index=1, name="X", number="154", printed_total="200", sku="1010")
        snapshot.inventory.cards["1/1"] = card

    skus = [g["sku"] for g in cs.do_search("54")["groups"]]
    check("1010" not in skus, "do_search('54') does not find a card whose number is 154/200")


CASES = [
    case_match_py_agrees_with_every_row,
    case_match_rank_never_treats_a_number_as_a_bare_substring,
    case_match_rank_folds_a_hyphen_standing_for_the_slash,
    case_match_rank_folds_accents,
    case_match_fold_text_strips_every_mark_by_category,
    case_match_digit_tests_are_ascii_only,
    case_match_query_stays_fast_on_repeated_tokens,
    case_do_search_finds_a_padded_number_typed_without_its_zeros,
    case_do_search_finds_a_whole_number_second_half,
    case_do_search_finds_a_number_with_more_leading_zeros_than_typed,
    case_do_search_never_returns_a_row_the_shared_matcher_rejects,
    case_do_search_midword_agrees_with_match_query,
    case_do_search_short_midword_terms_never_full_scan,
    case_do_search_finds_a_hyphenated_name,
    case_do_search_multiword_never_500s_next_to_a_widened_word,
    case_do_search_refuses_a_query_past_the_length_cap,
    case_do_search_measures_the_length_cap_after_nfkc,
    case_do_search_hostile_multiterm_query_stays_fast,
    case_deduped_capped_terms_dedupes_and_caps,
    case_do_search_hostile_repeated_terms_stay_fast_on_real_names,
    case_do_search_rows_walked_is_exactly_one_when_widening_is_needed,
    case_do_search_match_rank_calls_has_a_known_floor,
    case_do_search_match_query_calls_has_a_known_floor,
    case_do_search_union_never_drops_a_row_a_single_term_widens,
    case_do_search_zero_pad_matches_a_composed_number,
    case_do_search_zero_pad_widens_a_digit_plus_letter_term,
    case_do_search_substring_widens_a_two_char_digit_term,
    case_do_search_number_widening_mirrors_canonical_number,
    case_do_search_comma_and_edge_punctuation_terms_widen,
    case_do_search_hyphen_fold_finds_a_composed_number,
    case_do_search_fold_deletion_narrowed_bf_to_the_accepted_floor,
    case_do_search_widening_dedupes_case_variants,
    case_do_search_permanent_fuzz_agrees_with_match_query,
    case_do_search_still_refuses_an_unrelated_number,
    case_do_search_runs_the_shared_case_table,
]


def main() -> int:
    print("match-selftest — the one forgiving matcher, server side (FLT-06/04, UX-173)")
    try:
        for case in CASES:
            print(f"\n{case.__name__}")
            try:
                case()
            except Exception as exc:  # noqa: BLE001 — a raising case is a failing case
                import traceback

                bad(f"{case.__name__} raised {type(exc).__name__}: {exc}")
                traceback.print_exc()
    finally:
        cleanup()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
