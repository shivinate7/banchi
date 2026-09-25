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
    case_do_search_finds_a_padded_number_typed_without_its_zeros,
    case_do_search_finds_a_hyphenated_name,
    case_do_search_still_refuses_an_unrelated_number,
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
