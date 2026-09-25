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
from typing import List

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
CASE_TABLE_INPUT_NEEDED = {
    16: (
        "mid-word text still matches",
        "rule 7's mid-word substring. FTS5 is a PREFIX index (`tokenchars '/-'` keeps a "
        "token's own punctuation, but there is no 'contains' operator): 'ventor' is not a "
        "prefix of the token 'inventor', so the candidate step can never surface this row, "
        "whatever `match_query` would say once it got there. store-scaling item 8 measured "
        "this exact loss ('izard' -> Charizard) and the owner took it explicitly; "
        "harness/tests/t7_store_and_seams.py:check_search_fts5 is the test that already "
        "protects it. Fixing this row would reopen that settled trade-off.",
    ),
}

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
    case_match_digit_tests_are_ascii_only,
    case_match_query_stays_fast_on_repeated_tokens,
    case_do_search_finds_a_padded_number_typed_without_its_zeros,
    case_do_search_finds_a_whole_number_second_half,
    case_do_search_finds_a_hyphenated_name,
    case_do_search_multiword_never_500s_next_to_a_widened_word,
    case_do_search_refuses_a_query_past_the_length_cap,
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
