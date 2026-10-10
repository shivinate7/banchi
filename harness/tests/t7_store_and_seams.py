"""T7 — Inventory store, capture server, and the command seams.

Protects: The store, the capture server and the command seams keep positions unique, round-trip sidecars, refuse with their own codes and read the columns they name.
Governs: D4, D10

The first test that reaches `store/`, `server/` and `cli/`. Until it existed those three
packages held about 40% of product code with nothing checking any of it, and `make harness`
went green at the end of every turn without looking at them once.

WHAT IS DIFFERENT ABOUT THIS ONE. T1-T6 check rules: how a card is priced, which condition
row it matches, which queue it lands in. This checks BOOKKEEPING AND WIRING — where a
physical card is recorded, whether a correction reaches the file that will actually be read,
which column a price is pulled from. The failure modes are different in kind. A wrong rule
produces a wrong answer you can see; a wrong position produces a card that is exactly where
the inventory says it is not, discovered weeks later by a person opening the wrong slot.

Pass: positions never collide and a replay burns none; the sidecar round-trips through the reader identify uses; every refusal answers in its own code; command seams read the columns they name, and commands refuse rather than prompt

TWO CASES HERE ARE REGRESSION TESTS, NOT NEW COVERAGE. Both were live bugs that passed
every gate in the repo on the day they shipped, and both are recorded in docs/debts/:

  the PUT that never reached the sidecar   `cli/cmd_identify.py` builds its card from the
                                           sidecar, not from `inventory.json`, so a
                                           correction stopping at the record never reaches
                                           the variant ladder. It passed its own route test
                                           while doing this.
  the `c.box == box` filter                a string-typed record was silently dropped from
                                           the high-water scan, returning an index that
                                           collided later. Coercing only the box raises
                                           inside the lock; coercing both is the fix.

Isolation is `BANCHI_HOME` pointed at a temporary directory. `store.files.home()` reads
the environment on every call rather than at import, so no module reload is needed — and
that property is itself asserted in `harness/tests/t7/`, because the whole test is built on it.

UNDO ARRIVED WITH STEP 7a AND SO DID ITS CASES, which is what the paragraph here used to
promise. `check_undo` covers what D10 settles: delete rather than tombstone, the newest
capture in a box only, refused once the card's row has been written into an import file —
and that the position leaves every store that holds it, not just `inventory.json`. That last
one is a regression test as much as coverage: the route shipped editing the card map alone
while `Store.write()` committed the queues and the answer cache back around a position that
no longer existed.

7b'S THREE ROUTES ARRIVED THE SAME WAY, on 2026-08-13, and the paragraph here used to say
they did not exist. `check_queues`, `check_review_answer` and `check_mark_sold` cover the
standing-queue read, D4's one-tap answer and D10's mark-sold with its reversal — every
refusal by code, and the two rules that are easy to state and easy to lose: an answer may
only be one of the rows the pipeline offered, and a sale is a state that keeps its record
and its position.

THREE MORE REGRESSION CASES LANDED ON 2026-08-13, from the review of 7b, and each one is a
case an existing section could not have failed on:

  the laundered sku       `do_review_answer` validated against both queue entries' candidates
                          POOLED, so a stale parked entry could authorise a SKU the review
                          entry never offered. The both-queues case here gave the two entries
                          IDENTICAL candidates and was therefore blind to it — the fixture is
                          different on both sides now.
  the sale a bad log      `do_mark_sold` reads `history.jsonl` to say what an undo would put
  blocked                 back, and `read_jsonl` refuses the whole file over one bad line —
                          which took the SALE down with the reversal.
  /status counting a      7b turned the queue counts into a sort (`len(Queue)` runs
  queue it cannot order   `open_entries`), so a queue record with a non-numeric market or a
                          string box raised out of the health route.

`check_origin_gate` IS THE ONLY SECURITY CONTROL THIS FILE WATCHES, and it is the only
section that has to use real sockets. The server answered `Access-Control-Allow-Origin: *`
on every route including `DELETE /inventory/<box>/<index>`, so any page the owner happened
to have open in another tab could spend his inventory; the fix is an origin allowlist in
`_dispatch`, ahead of every handler. It is unreachable from a `do_*` call — the gate reads a
request HEADER, and an in-process call has none — so it went untested until 2026-08-23. The
three properties easiest to break later each carry their reason at the assertion: a refusal
changes nothing, an ABSENT `Origin` still writes (`curl`, `./banchi` and this test send
none, and requiring the header kills every command-line path at once), and `GET` stays open
because `GET /photo` is loaded by an `<img>`, which sends no `Origin` either.

`check_history` LANDED ON 2026-08-13 WITH THE LINES IT ASSERTS. Three routes here write
without moving a card between states — the PUT correction, the undo and the review answer —
and until that day none of them appended anything to `history.jsonl`, which `docs/debts/`
carried as a known gap. The section asserts the part that cannot be recovered afterwards: the
value a correction replaced, the boundary between two physical cards at one reused position,
and which queue's offer a human chose from. It also asserts the two properties that make the
new lines safe in a file another route reads — that no event name is a listing state, and
that a logged event is discarded when the write it rides in raises.

THREE SECTIONS LANDED ON 2026-08-23 FOR THE MULTI-GAME FOUNDATION (D20-D25), and each was
named by the work that shipped the code rather than invented here:

  `check_capture_claim_chain`   `store/master.py:CAPTURE_CLAIM_FIELDS` against `Card`, and
                                the two hops docs/debts/ says fail SILENTLY — the reload
                                filter and the re-record upsert. Asserted over the tuple, so
                                it grows with it; naming today's claims would pass on the day
                                a fifth is added and dropped.
  `check_game_and_note_seam`    D21's `game` and D23's `note` through the same seam
                                `check_sidecar_seam` guards, plus `GET /games`. A game that
                                reaches `inventory.json` and not the sidecar is a Riftbound
                                card read by the Pokemon prompt and priced off the Pokemon
                                export.
  `check_box_routes_and_search` D20's three box routes and `GET /search`. Nothing had
                                called `do_boxes`, `do_create_box`, `do_put_box` or
                                `do_search` at all — `check_boxes_and_listings` asserts the
                                STORE beneath them, which is a different question: a rule
                                that is right behind a route nobody can reach correctly is
                                still a box counted against the wrong denominator on the one
                                screen built to repair it.

TWO MORE SECTIONS LANDED ON 2026-08-23 FOR D26'S PAIR OF ROUTES, the day the routes did.
`check_retire` mirrors `check_mark_sold` refusal for refusal — the two terminal states are
siblings, and the rules asserted on one door are asserted on the other — plus the rules
that exist only because there are two doors now: the `already_sold` <-> `card_retired`
refusal pair, the deliberate asymmetry that a retirement moves no `live` count, and the
reason that must survive a reversed retirement in the history line alone. `check_reshoot`
covers the replace-in-place: the old bytes GONE rather than archived (an archived copy
under the capture root is a paid Batch request — the same money rule `check_sidecar_seam`
asserts), the sidecar rebuilt from the RECORD so a drifted one is repaired rather than
trusted, and the `reshot` line carrying both capture ids — the only trace the first
photograph ever existed.

TWO MORE SECTIONS LANDED ON 2026-08-23, the day after their routes and seams did, for
D29's group answer and C8's code ledger:

  `check_group_answer`   POST /review/group-answer. The case that matters is
                         `group_entry_refused` writing NOTHING — validate everything,
                         then write everything, because a partial group reports a state
                         neither queue file matches. Plus the three `group_not_uniform`
                         conditions, entry failures reported before uniformity, the
                         review entry governing a both-queues member, the listing hold
                         degrading `restores_to` per member rather than the write, and
                         one member's undo through the single route leaving the rest
                         answered.
  `check_code_ledger`    `upsert_jsonl`'s replace-in-place, `_code_ledger_lines`'
                         skip-by-name roster, the record seam writing the PARSER's
                         fields (a transcribed code lands in `Card.number` unfolded,
                         `?` marks intact), both ledger files written through a real
                         `identify` run over a stub transport — the only fake in it —
                         the cached-card heal of a deleted index, and the dispute
                         lookup through `GET /search` answering a pooled place and a
                         photo. Every code string in it is invented, in a scratch
                         store; nothing code-shaped touches a tracked file.

`check_printed_code_profiles` LANDED 2026-08-23 WITH RIFTBOUND'S AND ONE PIECE'S PROMPTS,
and it is the same kind of test as the code ledger's record seam one section up: not "is
this rule right" but "does the string arrive". The seam it guards is a name.
`cli/resolve.py` reads the RAW model payload back out of `identifications.json` and never
calls `prompt.parse`, so a schema that called the identifier `printed_code` — which is
exactly what `pipeline/games.py` calls the same idea one file over — would parse cleanly,
record cleanly, and hand the join a card with no number: the entire run back as
`no_catalog_row`, blaming the export. Nothing short of the round trip against the real
riftbound and One Piece exports can see that, so that is what the section does, on pairs
where one dropped character is a different real SKU at a different real price.

WHAT IT DOES NOT SAY, and this is the sentence to keep: it says those two profiles are
WIRED. It says nothing about whether a model can read a card of either game, because this
repo holds no photograph of one. There is no eval set and no accuracy figure for either
profile, and a green T7 must never be read as one.

WHAT THIS STILL DOES NOT COVER, and it is the important sentence in this file now. These
three routes were built before Gate B, which `docs/specs/capture-app.md` scheduled them
after. Every queue entry these cases assert against is still hand-built — by the harness
in `t7/`, or by hand in a browser — so what is asserted here is that the routes behave as
`docs/DESIGN.md` describes, not that a run produces entries of that shape. Half of that
closed on 2026-08-22: Gate B put 16 real entries in front of them — the queue read
served them, the owner answered every one through the answer route, and the shape
survived contact, same keys and same candidate rows. What it did not do is widen the
range. All 16 were `metadata_detection_disagreement`, so for the other eleven reason
codes nothing has reached these routes but a fixture. A green T7
says the same thing about 7b that a green T6 says about geometry: it is self-consistent.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.tests import Checks, Result  # noqa: E402
from harness.tests.t7 import (  # noqa: E402
    emit_pricing,
    send_markdown,
    store_core,
    undo_queues,
    history_sidecar,
    inventory_routes,
    server_hardening,
    cli_identify,
    engine_pick,
    auto_setup,
    photo_recheck,
    engine_sweep,
    free_adopt,
    match_audit,
    match_claim,
    drift_homes,
    drift_homes_batch2,
    orders,
    server_lanes,
    pipeline_fetch,
    price_history,
    price_fresh,
    price_moves,
    shipping,
    value,
    undo_built_on,
    sets_stock,
    realized_prices,
    preview_crop,
    read_budget,
)
# `t7_box_map.py` imports these names from this module, so they stay reachable here (D264).
from cli import resolve  # noqa: E402, F401
from harness.tests.t7.common import (  # noqa: E402, F401
    QuietHandler,
    back_of,
    capture_payload,
    error_code,
    fake_cid,
    hermetic,
    isolated_home,
    refusal,
    request,
    seam_run,
)
from pipeline import join  # noqa: E402, F401
from server import capture_server  # noqa: E402, F401
from store import master  # noqa: E402, F401
from store.session import Store  # noqa: E402, F401

NAME = "T7"
DESCRIPTION = "Inventory store, capture server, and the command seams"
PASS_CRITERIA = (
    "positions never collide and a replay burns none; the sidecar round-trips through "
    "the reader identify uses; every refusal answers in its own code; command seams read "
    "the columns they name, and commands refuse rather than prompt"
)

# One tuple per group module, in the order the checks ran when this was one file. The order is
# load-bearing: `harness/tests/t7_box_map.py` and the timer read it, and the ok/FAIL lines of a run
# are compared against it.
CHECK_ORDER = (
    *emit_pricing.CHECKS,
    *send_markdown.CHECKS,
    *store_core.CHECKS,
    *undo_queues.CHECKS,
    *history_sidecar.CHECKS,
    *inventory_routes.CHECKS,
    *server_hardening.CHECKS,
    *cli_identify.CHECKS,
    *engine_pick.CHECKS,
    *engine_sweep.CHECKS,
    *free_adopt.CHECKS,
    *match_audit.CHECKS,
    *match_claim.CHECKS,
    *drift_homes.CHECKS,
    *drift_homes_batch2.CHECKS,
    *auto_setup.CHECKS,
    *photo_recheck.CHECKS,
    *orders.CHECKS,
    *server_lanes.CHECKS,
    *pipeline_fetch.CHECKS,
    *price_history.CHECKS,
    *price_moves.CHECKS,
    *price_fresh.CHECKS,
    *shipping.CHECKS,
    *value.CHECKS,
    *undo_built_on.CHECKS,
    *sets_stock.CHECKS,
    *realized_prices.CHECKS,
    *preview_crop.CHECKS,
    *read_budget.CHECKS,
)


def run(order=None) -> Result:
    """Run every check, in `CHECK_ORDER` then the box map's, each inside `hermetic`.

    `order` is a function from the list of checks to the list to run. The order proof passes
    one that reorders; `harness/run.py --part K` passes one that keeps this part's slice. A
    whole `make harness` passes none, so that run is the hand-ordered one.
    """
    from harness.tests import t7_box_map  # its fixtures come from this file (D264)

    checks = Checks()
    todo = list(CHECK_ORDER) + list(t7_box_map.CHECKS)
    if order is not None:
        todo = list(order(todo))
    timings = []
    for check in todo:
        began = time.perf_counter()
        with hermetic():
            check(checks)
        timings.append((time.perf_counter() - began, check.__name__))
    slowest = sorted(timings, reverse=True)[:15]
    checks.note("")
    checks.note(
        f"SLOWEST 15 OF {len(timings)} CHECKS — {sum(t for t, _ in timings):.1f}s in all"
    )
    for seconds, name in slowest:
        checks.note(f"{seconds:7.2f}s  {name}")
    return checks.result(
        "store/, server/ and cli/ — the packages no harness test reached before this one."
    )
