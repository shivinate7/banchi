"""T7 — Inventory store, capture server, and the command seams.

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
every gate in the repo on the day they shipped, and both are recorded in docs/DEBTS.md:

  the PUT that never reached the sidecar   `cli/cmd_identify.py` builds its card from the
                                           sidecar, not from `inventory.json`, so a
                                           correction stopping at the record never reaches
                                           the variant ladder. It passed its own route test
                                           while doing this.
  the `c.box == box` filter                a string-typed record was silently dropped from
                                           the high-water scan, returning an index that
                                           collided later. Coercing only the box raises
                                           inside the lock; coercing both is the fix.

Isolation is `PKMNSCAN_HOME` pointed at a temporary directory. `store.files.home()` reads
the environment on every call rather than at import, so no module reload is needed — and
that property is itself asserted below, because the whole test is built on it.

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
changes nothing, an ABSENT `Origin` still writes (`curl`, `./pkmnscan` and this test send
none, and requiring the header kills every command-line path at once), and `GET` stays open
because `GET /photo` is loaded by an `<img>`, which sends no `Origin` either.

`check_history` LANDED ON 2026-08-13 WITH THE LINES IT ASSERTS. Three routes here write
without moving a card between states — the PUT correction, the undo and the review answer —
and until that day none of them appended anything to `history.jsonl`, which `docs/DEBTS.md`
carried as a known gap. The section asserts the part that cannot be recovered afterwards: the
value a correction replaced, the boundary between two physical cards at one reused position,
and which queue's offer a human chose from. It also asserts the two properties that make the
new lines safe in a file another route reads — that no event name is a listing state, and
that a logged event is discarded when the write it rides in raises.

THREE SECTIONS LANDED ON 2026-08-23 FOR THE MULTI-GAME FOUNDATION (D20-D25), and each was
named by the work that shipped the code rather than invented here:

  `check_capture_claim_chain`   `store/master.py:CAPTURE_CLAIM_FIELDS` against `Card`, and
                                the two hops docs/DEBTS.md says fail SILENTLY — the reload
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
below, or by hand in a browser — so what is asserted here is that the routes behave as
`docs/DESIGN.md` describes, not that a run produces entries of that shape. Half of that
closed on 2026-08-22: Gate B put 16 real entries in front of them — the queue read
served them, the owner answered every one through the answer route, and the shape
survived contact, same keys and same candidate rows. What it did not do is widen the
range. All 16 were `metadata_detection_disagreement`, so for the other eleven reason
codes nothing has reached these routes but a fixture. A green T7
says the same thing about 7b that a green T6 says about geometry: it is self-consistent.
"""

from __future__ import annotations

import base64
import io
import json
import hashlib
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.tests import Checks, Result  # noqa: E402

from cli import resolve, runs  # noqa: E402
from identify import batch, prompt, sidecar  # noqa: E402
from pipeline import games, join, tcgcsv, variant  # noqa: E402
from server import capture_server, pipeline_routes, ports  # noqa: E402
from store import files, master, queues  # noqa: E402
from store.session import Store  # noqa: E402

NAME = "T7"
DESCRIPTION = "Inventory store, capture server, and the command seams"
PASS_CRITERIA = (
    "positions never collide and a replay burns none; the sidecar round-trips through "
    "the reader identify uses; every refusal answers in its own code; command seams read "
    "the columns they name, and commands refuse rather than prompt"
)

# Enough to satisfy the server's magic-number check. It verifies rather than decodes — see
# the JPEG_MAGIC comment there — so a real image would only make this test slower.
JPEG = b"\xff\xd8\xff" + b"\x00" * 64

# A second, distinguishable blob for the re-shoot cases: same magic, different bytes, so
# "the old photo is GONE" (D26: replaced, not archived) is a comparison this file can lose.
JPEG_RESHOT = b"\xff\xd8\xff" + b"\x11" * 64

# Two rows the pipeline would have offered for one collector number, built through
# `cli/resolve.py:_candidate_rows`'s six keys rather than by hand, so the shape 7b's routes
# read cannot drift from the shape `join` writes. The pair differs only by finish, which is
# the case D3 rung 4 sends to review and the case the review screen exists for.
#
# HAND-BUILT, AND THAT IS THE LIMIT OF WHAT THESE CASES PROVE. They assert the routes
# against `docs/DESIGN.md`, not against reality. Recorded here rather than only in the
# module docstring because this literal is where the assumption physically lives.
#
# Gate B produced the first real entries on 2026-08-22 — 16 of them — and the shape above
# survived contact: same keys, same candidate rows. What it did NOT do is widen the range.
# All 16 were `metadata_detection_disagreement`; the other eleven reason codes have still
# never been produced by a run, so this literal remains an assumption about them.
CANDIDATES = [
    {
        "sku": "8608859",
        "name": "Articuno",
        "set": "SV09",
        "number": "161/159",
        "condition": "Near Mint Holofoil",
        "market": "12.00",
    },
    {
        "sku": "8608860",
        "name": "Articuno",
        "set": "SV09",
        "number": "161/159",
        "condition": "Near Mint Reverse Holofoil",
        "market": "4.20",
    },
]

# A row NO REVIEW ENTRY EVER OFFERS, and the only reason it exists. A position can sit in
# both queue files at once, and until 2026-08-13 the answer route validated against the two
# entries' candidates POOLED — so a stale parked entry could hand a screen the authority to
# write a SKU nothing had proposed for the row being answered.
#
# THE CASE COULD NOT FAIL BEFORE THIS LITERAL. `check_review_answer` already put a card in
# both files, but built both entries from `entry()`, so the two candidate lists were
# IDENTICAL and their union was indistinguishable from either one. A test that cannot fail
# on the bug it covers is the thing this repo cares most about, so the fixture is different
# on both sides now: a different set, a different number, a different condition string.
STALE_CANDIDATE = {
    "sku": "8608861",
    "name": "Articuno",
    "set": "SV08",
    "number": "071/167",
    "condition": "Near Mint",
    "market": "0.05",
}


def entry(box: int, index: int, **extra) -> queues.QueueEntry:
    """A queue entry for a captured position, with the fields a review row is drawn from.

    `label` comes from `join.Position` and never from a literal, for the same reason
    `check_server_routes` asserts the server's labels that way: one renderer draws a
    position, and a literal here would go on passing while the app and the pipeline
    disagreed about where a card is.
    """
    fields = {
        "position": master.position_key(box, index),
        "box": box,
        "index": index,
        "label": join.Position(box, index).label,
        "photo": str(capture_server.photo_path(box, index)),
        "reason": "metadata_detection_disagreement",
        "candidates": [dict(row) for row in CANDIDATES],
    }
    fields.update(extra)
    return queues.QueueEntry(**fields)


@contextmanager
def isolated_home():
    """A whole store in a temporary directory, restored on the way out.

    Restores the previous value rather than deleting the key, because the harness runs six
    other tests in this process and leaking a home would point them somewhere unexpected.
    """
    previous = os.environ.get(files.HOME_ENV)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ[files.HOME_ENV] = tmp
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous


@contextmanager
def quiet():
    """Capture what the code under test prints, and yield the buffer.

    The commands print their refusals and argparse prints usage — both correct, and both
    noise in a suite that runs at the end of every turn. Captured rather than discarded,
    because a refusal that explains nothing is its own defect and is asserted below.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        yield buffer


class QuietHandler(capture_server.CaptureHandler):
    """The real handler with its request log silenced.

    Overriding `log_message` rather than redirecting stdout: the server answers on its own
    threads, and swapping a process-global stream underneath them to hide a log line is a
    great deal of leverage for a cosmetic problem.
    """

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - BaseHTTPRequestHandler's name
        pass


def capture_payload(box: int, **extra) -> dict:
    payload = {"box": box, "image": base64.b64encode(JPEG).decode("ascii")}
    payload.update(extra)
    return payload


# --------------------------------------------------------------- the command-seam fixture
#
# REAL ROWS FROM THE COMMITTED EXPORT, cut down to three. The join matches on `TCGplayer Id`
# and the routing turns on the prices, so an invented row would be testing the fixture. Three
# because that is the smallest set that carries both shapes the ladder needs: a number with
# two condition rows, which the capture toggle decides (D3 rung 1), and a holofoil-only
# number, which the catalog decides on its own (rung 2).
FIXTURE_EXPORT = Path(__file__).resolve().parents[2] / "fixtures" / "sv09_export_untouched.csv"

DUNSPARCE_SKU = "8608459"  # 120/159 Near Mint, market 2.06
DUNSPARCE_REVERSE_SKU = "8608464"  # 120/159 Near Mint Reverse Holofoil, market 2.60
ARTICUNO_SKU = "8608859"  # 161/159 Near Mint Holofoil, market 22.03 — one row, no toggle
SEAM_SKUS = (DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU, ARTICUNO_SKU)


def write_export(path, *, live=None):
    """A Filtered Export holding the three seam rows. `live` overrides `Total Quantity`.

    That column is the one D8 and D11 make authoritative and the one `./pkmnscan join` reads
    a SKU's `live` count from, so every case below that moves `live` moves it by rewriting
    this file rather than by writing the number it expects to read back.
    """
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = []
    for sku in SEAM_SKUS:
        row = dict(by_sku[sku])
        if live is not None and sku in live:
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = str(live[sku])
        rows.append(row)
    tcgcsv.write_csv(path, source.header, rows)
    return Path(path)


def write_staged(path, quantities):
    """An Export From Staged: the seam rows, with `Add to Quantity` set per SKU.

    `Add to Quantity` is the column `emit` wrote and the only one that can carry a STAGED
    quantity. `Total Quantity` is deliberately set to a DIFFERENT number by every caller
    below, so a command reading the wrong column cannot pass.
    """
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = []
    for sku, quantity in quantities.items():
        rows.append(
            dict(
                by_sku[sku],
                **{
                    tcgcsv.QUANTITY_COLUMN: str(quantity),
                    tcgcsv.LIVE_QUANTITY_COLUMN: "97",
                },
            )
        )
    tcgcsv.write_csv(path, source.header, rows)
    return Path(path)


def identifications_for(cards) -> dict:
    """An `identifications.json` payload, shaped as `cli/cmd_identify.py` writes it.

    Field for field, because `cli/resolve.py` reads it back key by key: a hand-made payload
    that drifted from that shape would test the fixture instead of the seam. Each entry is
    `(box, index, name, number, finish)`; a null finish is a card with no capture toggle,
    which is what sends the ladder to rung 2.
    """
    return {
        "prompt_fingerprint": "t7-seam",
        "cards": {
            master.position_key(box, index): {
                "photo": str(capture_server.photo_path(box, index)),
                "box": box,
                "index": index,
                "set_hint": None,
                "metadata_finish": finish,
                "status": "ok",
                "error": None,
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": finish,
                },
            }
            for box, index, name, number, finish in cards
        },
    }


def seam_run(checks: Checks, cards, *, live=None):
    """A joined run over `cards`, in whatever isolated home is current. Returns the run.

    Captures a photo per card through the real route first, so the store holds the same
    positions the identifications name — the ordinary case. The one case that deliberately
    skips this is the position `emit` has never seen, which builds its payload by hand.
    """
    for box, index, *_ in cards:
        while Store().read().inventory.next_index(box) <= index:
            capture_server.do_capture(capture_payload(box))
    run_dir = runs.create("t7-seam")
    run_dir.write_identifications(identifications_for(cards))
    export = write_export(run_dir.path("export.csv"), live=live)
    said = command(checks, "join", str(run_dir.directory), "--export", str(export))
    return runs.open_run(run_dir.directory), said


def command(checks: Checks, *argv):
    """Run one `./pkmnscan` subcommand and return what it printed. Exit 0 or a failure.

    Through `cli/__main__.py:main` rather than by importing the command module, because the
    dispatch and the argument defaults are part of the seam: a flag whose default moved would
    otherwise be invisible here.
    """
    from cli import __main__ as entry

    with quiet() as said:
        code = entry.main(list(argv))
    text = said.getvalue()
    checks.ok(code == 0, f"`pkmnscan {argv[0]}` exits 0", f"exit {code}\n{text}")
    return text


def refusal(checks: Checks, fn, code: str, label: str) -> None:
    """Assert a route refuses with one specific code.

    The code and not just the status: `docs/specs/capture-server.md` requires every
    anticipated condition to carry its own, because step 7 surfaces these strings to a
    human and `docs/DESIGN.md`'s copy rule reaches them. Two conditions collapsing onto
    one code is a message that cannot say what to do next.
    """
    try:
        fn()
    except capture_server.BadRequest as caught:
        checks.equal(caught.code, code, label)
    except Exception as caught:  # noqa: BLE001 — any other exception is the failure
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
    else:
        checks.ok(False, label, "did not refuse")


def answers(checks: Checks, fn, label: str):
    """Assert a route ANSWERS at all, and hand back what it said. `refusal`'s mirror.

    For the routes whose contract is that they survive data they cannot make sense of —
    `/status` on a corrupt store, a sale against an unreadable history. Written as a helper
    for the same reason `Checks` collects failures rather than stopping at the first: an
    exception escaping one of those is the regression itself, and letting it propagate turns
    a red line into a crash that hides every check behind it. Returns None on a raise, so the
    caller guards the assertions that read the answer.
    """
    try:
        answer = fn()
    except Exception as caught:  # noqa: BLE001 — raising IS the failure under test
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
        return None
    checks.ok(True, label)
    return answer


# --------------------------------------------------------------------------- the allocator


def check_allocator(checks: Checks) -> None:
    """The seventeen cases `docs/DEBTS.md` enumerates, plus the coercion that caused them.

    `allocate_capture` is the one piece of step-5 logic Gate B exercised 53 times in a
    row on 2026-08-22, and it is the only place in the project that decides where a physical
    card is.
    """
    checks.note("")
    checks.note("ALLOCATOR — store/master.py")

    inventory = master.Inventory()
    checks.equal(inventory.next_index(3), 1, "an empty box starts at index 1")

    first, created = inventory.allocate_capture(3)
    checks.ok(created, "the first allocation into an unseen box creates it implicitly")
    checks.equal(first.key, "3/1", "first card is keyed 3/1")

    second, _ = inventory.allocate_capture(3)
    checks.equal(second.key, "3/2", "allocation is sequential")

    other, _ = inventory.allocate_capture(7)
    checks.equal(other.key, "7/1", "boxes are independent — box 7 starts over at 1")
    checks.equal(inventory.next_index(3), 3, "and allocating into 7 left box 3 untouched")

    # D10: sold cards leave permanent gaps. The high-water mark counts every state, so a
    # sale does not hand its slot to the next card — which is what makes a printed position
    # label worth trusting a year later.
    checks.ok(
        inventory.set_state("3/2", master.SOLD),
        "a card can be marked sold",
    )
    checks.equal(
        inventory.next_index(3),
        3,
        "D10: a sold card keeps its position — the next index steps past it, not into it",
    )
    checks.ok(
        inventory.get("3/2") is not None,
        "and the sold card keeps its record: sold is a state, never a removal",
    )

    # The behaviour undo inherits (D10, settled 2026-08-12). Deleting the newest record
    # releases its index; this is asserted because step 7's undo is built on it, and a
    # refactor that changed it would silently change what undo does.
    scratch = master.Inventory()
    scratch.allocate_capture(1)
    newest, _ = scratch.allocate_capture(1)
    checks.equal(scratch.next_index(1), 3, "two cards in box 1, next index is 3")
    del scratch.cards[newest.key]
    checks.equal(
        scratch.next_index(1),
        2,
        "deleting the NEWEST record releases its index — what undo inherits (D10)",
    )

    # The measured bug. A record whose box and index arrived as JSON strings must be
    # COUNTED, not skipped: skipping it returns an index that collides later, and the
    # collision surfaces as one physical card overwriting another.
    stringy = master.Inventory()
    stringy.cards["4/1"] = master.Card(box="4", index="1")
    checks.equal(
        stringy.next_index(4),
        2,
        "a string-typed record is counted, not silently skipped past",
    )
    checks.equal(
        stringy.next_index("4"),
        2,
        "and a string-typed box argument coerces the same way",
    )

    unparsable = master.Inventory()
    unparsable.cards["5/1"] = master.Card(box="five", index=1)
    caught = checks.raises(
        master.BadPosition,
        lambda: unparsable.next_index(5),
        "an unparsable box refuses rather than guessing",
    )
    if caught is not None:
        checks.ok(
            "5/1" in str(caught),
            "and the refusal names the offending card",
            f"message was: {caught}",
        )

    # The retry guard. A response lost between commit and client makes the app repost; the
    # capture_id is what stops that from burning a second index for one physical card.
    replay = master.Inventory()
    original, first_created = replay.allocate_capture(2, capture_id="abc")
    again, second_created = replay.allocate_capture(2, capture_id="abc")
    checks.ok(first_created and not second_created, "a replayed capture_id reports created=False")
    checks.equal(again.key, original.key, "and returns the original card")
    checks.equal(replay.next_index(2), 2, "and burns no second index")

    duplicated = master.Inventory()
    duplicated.cards["1/1"] = master.Card(box=1, index=1, capture_id="dup")
    duplicated.cards["1/2"] = master.Card(box=1, index=2, capture_id="dup")
    caught = checks.raises(
        master.DuplicateCaptureId,
        lambda: duplicated.card_by_capture_id("dup"),
        "one capture_id on two cards refuses rather than picking one",
    )
    if caught is not None:
        checks.ok(
            "1/1" in str(caught) and "1/2" in str(caught),
            "and the refusal names both positions",
            f"message was: {caught}",
        )

    # A field not declared on Card is dropped by `parse`, which is why the retry guard could
    # not live in the sidecar alone. Asserted so that stays true.
    round_trip = master.Inventory.parse(replay.to_payload())
    checks.equal(
        round_trip.cards[original.key].capture_id,
        "abc",
        "capture_id survives a JSON round trip through to_payload and parse",
    )

    events = master.Inventory()
    events.allocate_capture(9)
    captured = [e for e in events.events if e.get("event") == master.CAPTURED]
    checks.equal(len(captured), 1, "allocation logs exactly one captured event")
    checks.equal(captured[0].get("position"), "9/1", "and the event carries the position")

    checks.equal(
        master.position_key(3, 17), "3/17", "position_key renders box/index"
    )
    checks.raises(
        master.UnknownState,
        lambda: master.check_state("nearly-sold"),
        "a state outside the enum is refused, never coerced",
    )
    checks.ok(
        not master.Inventory().set_state("99/99", master.IDENTIFIED),
        "set_state on an unknown position returns False rather than pretending (v1 bug 5)",
    )


# ------------------------------------------------------------------------------- the store


def check_store(checks: Checks) -> None:
    """The session: isolation, the re-read inside the lock, and nothing written on error."""
    checks.note("")
    checks.note("STORE SESSION — store/files.py, store/session.py")

    with isolated_home() as home:
        checks.equal(
            files.home(),
            home.resolve(),
            "files.home() reads PKMNSCAN_HOME per call — the whole test rests on this",
        )

        with Store().write() as snapshot:
            snapshot.inventory.allocate_capture(3)
        checks.equal(
            Store().read().inventory.next_index(3), 2, "a committed write is visible to a later read"
        )

        # Nothing is written when an exception escapes the block. The writes happen after
        # the yield, so a crash halfway through a transition leaves the store as it was.
        try:
            with Store().write() as snapshot:
                snapshot.inventory.allocate_capture(3)
                raise RuntimeError("deliberate")
        except RuntimeError:
            pass
        checks.equal(
            Store().read().inventory.next_index(3),
            2,
            "an exception inside write() commits nothing — the store is as it was",
        )

        history = Store().history()
        checks.equal(
            len([e for e in history if e.get("event") == master.CAPTURED]),
            1,
            "and the abandoned capture left no history event either",
        )

        checks.ok(
            not list(Store().directory.glob(".*.tmp")),
            "the atomic replace leaves no temp file behind",
        )


# ------------------------------------------------------------------- the server, in-process


def check_server_routes(checks: Checks) -> None:
    """The route surface and every refusal, called directly rather than over a socket.

    In-process because the handler is a thin dispatch over these functions: what is worth
    asserting is that each anticipated condition answers in its own code, and a socket adds
    nothing to that. Concurrency is the exception and gets a real server below.
    """
    checks.note("")
    checks.note("SERVER ROUTES — server/capture_server.py")

    with isolated_home():
        status, body = capture_server.do_capture(capture_payload(3))
        checks.equal(status, HTTPStatus.CREATED, "a first capture answers 201")
        checks.equal(body["key"], "3/1", "and reports the position it allocated")
        checks.ok(body["new_box"], "and flags the box as new")
        checks.equal(
            body["label"],
            join.Position(3, 1).label,
            "the rendered label matches pipeline/join.py's — one renderer, not two",
        )

        _, second = capture_server.do_capture(capture_payload(3))
        checks.equal(second["key"], "3/2", "captures into one box are contiguous")
        checks.ok(not second["new_box"], "and only the first is flagged new_box")

        status, replayed = capture_server.do_capture(
            capture_payload(3, capture_id="retry-1")
        )
        status_again, replayed_again = capture_server.do_capture(
            capture_payload(3, capture_id="retry-1")
        )
        checks.equal(status_again, HTTPStatus.OK, "a replayed capture answers 200, not 201")
        checks.ok(not replayed_again["created"], "and reports created=False")
        checks.equal(
            replayed_again["key"], replayed["key"], "and returns the original position"
        )

        photo = capture_server.photo_path(3, 1)
        checks.ok(photo.is_file(), "the photo is on disk at its position-derived path")
        served, tag = capture_server.do_photo(3, 1)
        checks.equal(served, JPEG, "GET /photo returns the stored bytes")
        checks.ok(
            tag.startswith('"') and tag.endswith('"') and len(tag) == 34,
            "and a quoted strong ETag beside them — the validator that lets a browser find "
            "out a slot's occupant changed under a URL that did not",
        )

        refusal(
            checks, lambda: capture_server.do_photo(3, 99), "photo_not_found",
            "an absent photo refuses as photo_not_found",
        )
        refusal(
            checks, lambda: capture_server.do_capture({"image": "x"}), "box_required",
            "a capture with no box refuses as box_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(0)), "box_invalid",
            "box 0 refuses as box_invalid — boxes start at 1",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture({"box": "three", "image": "x"}),
            "box_invalid",
            "a non-numeric box refuses as box_invalid",
        )
        refusal(
            checks, lambda: capture_server.do_capture({"box": 3}), "image_required",
            "a capture with no image refuses as image_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture({"box": 3, "image": "not base64!"}),
            "image_invalid",
            "a non-base64 image refuses as image_invalid",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(
                {"box": 3, "image": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")}
            ),
            "image_not_jpeg",
            "a PNG is REFUSED, never silently converted",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant="foil")),
            "variant_invalid",
            "a finish outside the enum refuses as variant_invalid",
        )
        # D3 rung 1's claim is a SET (amended 2026-08-23), and these are the route's half of
        # it. `variant="foil"` above is unchanged and stays first: the bare string is what
        # every client in the tree sends and what all 682 live records carry, so the wire
        # keeps accepting one forever — the read-side backfill, not a deprecation.
        refusal(
            checks,
            lambda: capture_server.do_capture(
                capture_payload(3, variant=["normal", "foil"])
            ),
            "variant_invalid",
            "ONE bad member refuses the WHOLE claim, in the same code and with no new one — "
            "a silently shortened claim is a claim the operator did not make, and a "
            "two-member claim quietly cut to one stops filtering and starts DETERMINING",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant=["normal", 7])),
            "variant_invalid",
            "and a member that is not a string refuses on shape, before any vocabulary is "
            "consulted — the split `_variant_shape`/`_check_variant_members` exists for",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant={"a": 1})),
            "variant_invalid",
            "as does a claim that is neither a string nor a list — it used to be COERCED, "
            "`str(raw).strip()`, which is how a JSON list became the literal \"['normal', "
            "'holo']\" and made a set-valued claim unmakeable over this wire",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(
                capture_payload(3, game="misc", variant=["normal"])
            ),
            "variant_invalid",
            "and the vocabulary is THIS GAME's: `misc` authors no finishes, so every member "
            "refuses — the capture screen draws no Finish field for it, so a finish arriving "
            "under one did not come from the control",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_card(9, 9, {"set_hint": "sv9"}),
            "card_not_found",
            "a PUT naming an absent position refuses — this route corrects, never creates",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_card(3, 1, {"state": "sold"}),
            "field_not_settable",
            "a PUT naming `state` is refused: listing transitions are not settable here",
        )

        checks.equal(
            capture_server.PUT_FIELDS,
            ("set_hint", "variant", "game", "rarity_claim", "note"),
            "and the settable set is every capture claim, in the order the store names them",
        )

        # Three captures reached this box, not four: the replay above returned the third
        # card rather than creating one. Counting it here is the mistake the retry guard
        # exists to prevent, so the count is the assertion.
        report = capture_server.do_status()
        checks.equal(report["cards"], 3, "GET /status counts every card, and a replay is not one")
        checks.equal(report["next_index"]["3"], 4, "and reports the next index per box")
        checks.ok("problem" not in report, "and reports no problem on a healthy store")

        # WHICH PROCESS IS ANSWERING. `scripts/serve.py` restarts this server whenever a
        # watched Python file changes, and the app tells a restart from a reload by watching
        # this value — the failure it exists for is docs/GATES.md's box 95, where whole-second
        # timestamps were written two hours after the millisecond fix landed because the
        # process predated it and nothing on any screen could say so.
        checks.ok(
            isinstance(report.get("boot_id"), str) and report["boot_id"],
            "GET /status names the process answering it, so a stale server can be seen",
        )
        checks.equal(
            report["boot_id"],
            capture_server.BOOT_ID,
            "and it is this process's own id rather than a value recomputed per request",
        )

        # GET /inventory decorates every row with its rendered position. Asserted against
        # `join.Position` itself and never against a literal string: the whole point of the
        # decoration is that ONE renderer draws a position label, and a literal here would
        # go on passing while the app and the pipeline disagreed about where a card is.
        inventory = capture_server.do_inventory()
        checks.equal(
            sorted(inventory["cards"]),
            ["3/1", "3/2", "3/3"],
            "GET /inventory returns every card, keyed by position",
        )
        row = inventory["cards"]["3/2"]
        checks.equal(
            row["label"],
            join.Position(3, 2).label,
            "and each row carries the label pipeline/join.py renders — not a second copy of "
            "D10's divider rule living in the app",
        )
        checks.equal(
            row["section"], join.Position(3, 2).section, "with the section it sits in"
        )
        checks.equal(
            row["card"], join.Position(3, 2).card, "and its card within that section"
        )

        # WIRE-ONLY, which is the constraint that makes the decoration safe. `inventory.json`
        # is the on-disk format and `Inventory.parse` filters on `Card.__annotations__`, so a
        # label written into it would be silently dropped on the next reload — a field that
        # exists only until something re-reads it is worse than no field at all.
        on_disk = json.loads(Store().inventory_path.read_text("utf-8"))
        checks.ok(
            all("label" not in record for record in on_disk["cards"].values()),
            "and the decoration never reaches inventory.json — to_payload is untouched",
        )

        # A corrupt record must not take down the one route you reach for when something is
        # wrong. It reports the finding instead.
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/1"].box = "three"
        broken = capture_server.do_status()
        checks.ok(broken["next_index"] is None, "a corrupt record leaves next_index null")
        checks.ok(
            "problem" in broken,
            "and /status still answers, reporting the problem rather than raising",
        )

        broken_inventory = capture_server.do_inventory()
        checks.ok(
            "label" not in broken_inventory["cards"]["3/1"],
            "a record whose box will not coerce is left UNLABELLED — a placeholder label "
            "names a position that does not exist, which is the one thing a label may never "
            "do (D10)",
        )
        # THIS CASE SAID THE OPPOSITE UNTIL D58 AND THE REVERSAL IS THE POINT. It read
        # "one bad record does not take the route down: every other row keeps its label",
        # on the stated ground that "a label needs only this record's own two integers and
        # the box's layout". That ground is exactly what D58 removed: a card's number is
        # now its place among the cards ON HAND in its box, so rendering one means counting
        # the whole box, and a record nobody can place might be in this box and might be on
        # hand. Answering the old index-space label instead would put a SECOND NUMBERING
        # SYSTEM on the screen with nothing saying which one it is — a person sent to
        # `Card 40` in a box that has sold three would open the wrong slot and see nothing
        # wrong. No label is the honest answer, and it is the same call `view` already
        # makes for a layout that will not validate.
        #
        # WHAT IT COSTS IS REAL AND IS RECORDED RATHER THAN DESIGNED AWAY: the walk
        # degrades store-wide, so one unreadable record now blanks every label in the
        # inventory rather than only the decoration. Narrowing it per box is the fix to
        # reach for if that ever bites — a record whose INDEX will not read could be
        # attributed to its box and poison only that one, where a record whose BOX will
        # not read could be in any of them. Not done here, because it would be an
        # untested branch added to make a case go green.
        checks.ok(
            "label" not in broken_inventory["cards"]["3/2"],
            "and its NEIGHBOURS lose their labels too, because the number is a count of "
            "the cards in the box and one of them cannot be counted (D58) — a card that "
            "cannot be placed might be in this box and might be on hand",
        )
        checks.equal(
            broken_inventory["cards"]["3/2"]["place"]["box_total"],
            0,
            "and the denominator goes with it rather than standing alone: the count and "
            "the numbers drawn against it come off one walk",
        )


# ------------------------------------------------------------------------------------ undo


def check_undo(checks: Checks) -> None:
    """DELETE /inventory/<box>/<index> — the one route the capture app added.

    THE ONLY ROUTE IN THIS SERVER THAT DESTROYS ANYTHING, which is why it gets a section of
    its own rather than a few more lines beside the other refusals. Every other write here
    adds a record or corrects a field, and the worst a bug in one of them does is record
    something wrong. A bug in this one deletes a photograph of a card that is back in the
    box by the time anybody notices.

    The rules are D10's and they are asserted as rules, not as one happy path: what it
    deletes, that it deletes only the newest, that it stops at `captured` — ruling 2 of
    2026-08-23 reversed the old undo-at-`identified` allowance, and the case that asserted
    the allowance now asserts the refusal AND exercises the three remedies it names — and
    that it stops once `emit` has written the card's row into an import file.
    """
    checks.note("")
    checks.note("UNDO — DELETE /inventory/<box>/<index>")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(3, set_hint="sv9", variant="holo"))

        photo = capture_server.photo_path(3, 3)
        sidecar_file = capture_server.sidecar_path(photo)
        checks.ok(
            photo.is_file() and sidecar_file.is_file(),
            "three captures into box 3, and the newest has both a photo and a sidecar",
        )

        body = capture_server.do_delete_card(3, 3)
        checks.equal(body["deleted"], "3/3", "undo answers with the position it removed")
        checks.ok(
            Store().read().inventory.get("3/3") is None,
            "the RECORD is deleted, not tombstoned — there is no state between captured "
            "and absent (D10)",
        )
        checks.ok(
            not photo.is_file(),
            "the PHOTO is deleted: an orphan is a paid Batch request for a card that no "
            "longer exists",
        )
        checks.ok(
            not sidecar_file.is_file(),
            "and so is the sidecar, which is what carried the set hint and the toggle",
        )
        checks.equal(
            len(sidecar.scan(capture_server.captures_root())),
            2,
            "so scan() now finds two captures — the undone card costs nothing to identify",
        )
        checks.ok(
            not body["review_deleted"]
            and not body["parked_deleted"]
            and not body["cache_deleted"],
            "and it reports nothing else removed for a card that was never queued or read",
        )

        # The index is released. Asserted through the server rather than only through the
        # allocator above, because the release is what makes an undo followed by a re-shoot
        # land in the same slot, and that is the whole reason an operator presses it.
        checks.equal(
            Store().read().inventory.next_index(3),
            3,
            "the index is released — next_index steps back to it",
        )
        checks.equal(body["next_index"], 3, "and the response says so, so the app need not count")

        second = capture_server.do_delete_card(3, 2)
        checks.equal(
            second["deleted"], "3/2", "a second undo walks back one more card, with no extra state"
        )
        checks.equal(
            Store().read().inventory.next_index(3), 2, "and releases that index too"
        )

        _, retaken = capture_server.do_capture(capture_payload(3))
        checks.equal(
            retaken["key"],
            "3/2",
            "the next capture takes the released position: a retaken photo lands where the "
            "bad one was",
        )

        capture_server.do_capture(capture_payload(3))  # 3/3 again, so 3/1 is not the newest
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_card(3, 1),
            "undo of a card that is NOT the newest refuses — a mid-box gap is permanent",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "undo_not_newest",
                "and it refuses in its own code, not card_not_found",
            )
            checks.ok(
                "box 3, card 3" in str(caught),
                "and the refusal NAMES the position that is undoable — otherwise the app "
                "has to ask again to find out",
                f"message was: {caught}",
            )
        checks.ok(
            Store().read().inventory.get("3/1") is not None,
            "and the card it refused is still there: a refusal deletes nothing",
        )

        # REFUSED at `identified`, since the owner's ruling of 2026-08-23 (D10, ruling 2).
        # This case asserted the opposite for as long as the route existed — "the model has
        # answered, money is already spent, and nothing outside this Mac knows the card" —
        # and the ruling reverses it: once identified, a card has made it into inventory
        # proper, and the capture screen's rapid-fire undo may not reach it. The refusal
        # must name the three remedies built for an identified card, and each is then
        # exercised here on this very card, so "the message points somewhere real" is a
        # fact this file has checked rather than prose.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.IDENTIFIED)
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_card(3, 3),
            "undo at `identified` REFUSES — D10 ruling 2 reversed the old allowance",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "undo_too_late",
                "in the same code the terminal states get — one code, remedy named per state",
            )
            checks.ok(
                all(
                    f"/inventory/3/3/{route}" in str(caught)
                    for route in ("photo", "retire", "remove")
                ),
                "and the refusal names all three remedies: re-shoot, retire, and the "
                "mid-box remove — which one is right depends on what is wrong with the "
                "card, and only the operator knows that",
                f"message was: {caught}",
            )
        checks.ok(
            Store().read().inventory.get("3/3") is not None
            and capture_server.photo_path(3, 3).is_file(),
            "and the refusal reached neither the record nor the photo",
        )

        # Remedy one, re-shoot: reaches an identified card, replaces the photo in place.
        reshot = capture_server.do_reshoot(
            3, 3, {"capture_id": "undo-remedy-reshoot", "image": base64.b64encode(JPEG_RESHOT).decode("ascii")}
        )
        checks.equal(
            reshot["key"], "3/3", "remedy 1, re-shoot: an identified card's photo is replaceable in place"
        )
        # Remedy two, retire and reverse: reaches an identified card both ways.
        capture_server.do_retire(3, 3, {"reason": "damaged"})
        put_back = capture_server.do_retire(3, 3, {"undo": True})
        checks.equal(
            put_back["state"],
            master.IDENTIFIED,
            "remedy 2, retire: an identified card retires, and the reversal restores its own state",
        )
        # Remedy three, the mid-box remove: deletes the identified card undo may not touch.
        # 3/3 is the top of its box, so the shift is empty — the remove route's floor case.
        gone = capture_server.do_remove_card(3, 3, {"capture_id": "undo-remedy-reshoot"})
        checks.ok(
            gone["deleted"] == "3/3"
            and gone["shifted"] == 0
            and Store().read().inventory.get("3/3") is None,
            "remedy 3, remove: deletes the identified card, zero cards shifted at the top "
            "of the box, and the index is released exactly as undo releases one",
        )

        # An emitted card refuses on TWO grounds now, and this block asserts both. `pushed`
        # is a count on the SKU's `Listing` and no longer a state a card wears (D7 amended),
        # and under D10 ruling 2 the card's `identified` state alone already stops the undo
        # — so `_listing_hold` is the guard BEHIND the state check there, nearly
        # unreachable, and the place where the hold does its visible work is the REMOVE
        # route, which identified cards CAN reach. The SKU-naming refusal is asserted
        # there, where the operator will actually read it.
        checks.raises(
            master.UnknownState,
            lambda: Store().read().inventory.set_state("3/2", master.PUSHED),
            "`pushed` is not a card state any more — set_state refuses it, so the old guard "
            "cannot be reached for by accident",
        )
        with Store().write() as snapshot:
            snapshot.inventory.set_state(
                "3/2", master.IDENTIFIED, sku="8608859", condition="Near Mint Holofoil"
            )
            snapshot.inventory.listing("8608859", condition="Near Mint Holofoil").bump(
                master.PUSHED, 1
            )
        checks.ok(
            Store().read().inventory.get("3/2").state
            not in capture_server.UNDOABLE_STATES,
            "a pushed copy reads `identified`, which ruling 2 took OFF the undo allowlist — "
            "the state check now stops it one guard earlier than the listing hold",
        )
        refusal(
            checks,
            lambda: capture_server.do_delete_card(3, 2),
            "undo_too_late",
            "and undo refuses it: identified, and its SKU's row is in an import file — "
            "either fact alone is enough (D10 ruling 2; D7 amended)",
        )
        checks.ok(
            Store().read().inventory.get("3/2") is not None
            and capture_server.photo_path(3, 2).is_file(),
            "and the refusal reached neither the record nor the photo",
        )
        # The hold's own refusal, on the route that reaches identified cards: the remove
        # route names the SKU and the count, because a refusal that does not say what is
        # holding the card costs a round trip.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": None}),
            "the mid-box remove refuses a listing-held TARGET in its own code",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "card_listed", "card_listed")
            checks.ok(
                "8608859" in str(caught) and "1 pushed" in str(caught),
                "and it names the SKU and how many copies are out of this Mac",
                f"message was: {caught}",
            )

        # The other two stages hold just as hard: `pushed` is where D10 draws the line,
        # and everything past it is further out of reach, not less. Asserted on both
        # doors: the undo refuses (state, since ruling 2), and the remove names the stage.
        for stage in (master.STAGED, master.LIVE):
            with Store().write() as snapshot:
                entry = snapshot.inventory.listing("8608859")
                entry.set(master.PUSHED, 0)
                entry.set(stage, 1)
            refusal(
                checks,
                lambda: capture_server.do_delete_card(3, 2),
                "undo_too_late",
                f"a SKU sitting at `{stage}` still cannot be undone away",
            )
            refusal(
                checks,
                lambda: capture_server.do_remove_card(3, 2, {"capture_id": None}),
                "card_listed",
                f"and the remove route refuses it too, at `{stage}` — D10's line is "
                f"`emit`, and every stage past it is further out of reach",
            )
        with Store().write() as snapshot:
            snapshot.inventory.listing("8608859").set(master.LIVE, 0)

        # State is read before position. This card is neither the newest nor undoable, and
        # the answer that matters is the second one: the other order would send the
        # operator to delete a good capture on the way to a card it could never remove.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/1", master.SOLD)
        refusal(
            checks,
            lambda: capture_server.do_delete_card(3, 1),
            "undo_too_late",
            "a sold card refuses as too late rather than as not-newest — state is checked "
            "first, so the answer is the one that cannot change (D10)",
        )

        refusal(
            checks,
            lambda: capture_server.do_delete_card(9, 9),
            "card_not_found",
            "undo of a position that holds no card refuses — there is nothing to delete",
        )

        checks.equal(
            capture_server.UNDOABLE_STATES,
            (master.CAPTURED,),
            "undo is allowed at exactly `captured` (D10 ruling 2, 2026-08-23), named as an "
            "allowlist so a new state is refused by default",
        )

        # EVERYTHING KEYED BY THE POSITION GOES, not the card record alone. The snapshot
        # carries the two standing queues and the identification cache as well, and
        # `Store.write()` writes all four files back on the way out — so a route that edits
        # only `inventory.cards` does not leave the others alone, it commits them unchanged
        # around a position that no longer exists.
        #
        # This is not a corner case, which is why it is set up in full rather than asserted
        # on a bare card. Ruling 2 NARROWED the overlap between the undoable set and the
        # queued set without closing it: a queued card is usually `identified` (out of
        # undo's reach now, and the remove route's problem), but a card whose
        # identification FAILED — `identification_failed`, `card_not_detected` — queues
        # while still `captured`, and that junk capture is exactly what undo exists to
        # walk back. The card here stays `captured` for that reason; the cache entry
        # beside it is legal store state all the same (the commit is per file, and the
        # route must clear whatever is keyed by the position, not what a tidy history
        # would predict).
        _, queued = capture_server.do_capture(capture_payload(3))
        queued_key = queued["key"]
        with Store().write() as snapshot:
            snapshot.review.upsert(
                queues.QueueEntry(
                    position=queued_key,
                    box=queued["box"],
                    index=queued["index"],
                    label=queued["label"],
                    photo=str(capture_server.photo_path(queued["box"], queued["index"])),
                    reason="identification_failed",
                    market="12.00",
                )
            )
            snapshot.parked.upsert(
                queues.QueueEntry(
                    position=queued_key,
                    box=queued["box"],
                    index=queued["index"],
                    label=queued["label"],
                    reason="card_not_detected",
                    # Cleared by a human, which is the one case `Queue.release` refuses to
                    # drop — on the grounds that an answer should outlive its question. Undo
                    # must drop it anyway, and that is asserted below rather than assumed:
                    # the index is released, so the next capture into this box takes this
                    # very position, and a preserved answer would be a human's ruling about
                    # one physical card attached to a different one.
                    cleared_by_human=True,
                )
            )
            snapshot.cache.put(queued_key, {"name": "Rhyhorn"}, "sha-of-photo", "prompt-1")

        removed = capture_server.do_delete_card(queued["box"], queued["index"])
        after = Store().read()
        checks.ok(
            after.review.entries.get(queued_key) is None,
            "undo drops the REVIEW entry — otherwise it names the photo this route just "
            "deleted, and nothing clears a queue entry before 7b's review screen",
        )
        checks.ok(
            after.parked.entries.get(queued_key) is None,
            "and the PARKED entry, even one a human had cleared: the card, the question and "
            "the photograph are all gone, and the position is about to be reused",
        )
        checks.ok(
            after.cache.get(queued_key) is None,
            "and the paid IDENTIFICATION — a cached answer keyed to a position the next "
            "capture will fill is an answer about the wrong physical card",
        )
        checks.ok(
            removed["review_deleted"]
            and removed["parked_deleted"]
            and removed["cache_deleted"],
            "and the response says what it removed, the way photo_deleted already does",
        )
        counted = capture_server.do_status()["queues"]
        checks.equal(
            counted,
            {"review": 0, "parked": 0},
            "so GET /status stops counting the phantom — the number the owner works from",
        )

    # Wiring, asserted because it is invisible from Python and fatal from a browser: without
    # DELETE in the preflight answer the request is refused before the server ever sees it.
    # Read off `ALL_METHODS` rather than the single `CORS_HEADERS` tuple this used to name —
    # the header is built per request now, and the constant is what an ALLOWED origin is told.
    checks.ok(
        "DELETE" in capture_server.ALL_METHODS,
        "CORS advertises DELETE — a preflight that omits it refuses the undo at the browser",
        f"methods: {capture_server.ALL_METHODS}",
    )
    checks.ok(
        "DELETE" not in capture_server.SAFE_METHODS,
        "and an origin this server does not know is told GET and OPTIONS only, so the one "
        "route that destroys anything cannot be preflighted from a page the owner never "
        "opened",
        f"safe methods: {capture_server.SAFE_METHODS}",
    )
    checks.ok(
        hasattr(capture_server.CaptureHandler, "do_DELETE"),
        "and the handler answers the verb at all",
    )


# --------------------------------------------------------------------- the standing queues


def check_queue_supersede(checks: Checks) -> None:
    """`queues.apply_run` — a run's verdict applied to both queues as one unit.

    THE RE-ROUTE CASE IS A REGRESSION, NOT NEW COVERAGE. It shipped as a live bug and was
    caught by the first real run: the garbage identifications of 2026-08-22 put 45 entries
    in review, the corrected re-identification parked 16 of the same positions, and every
    one kept its stale review entry beside the live parked one — same physical card, two
    open questions, one describing an identification that no longer existed. The two
    release calls in `cli/cmd_join.py` were each computed from their own queue's entries
    alone, so neither could see what the other had just been given. Re-introduced
    deliberately (the two `- parked_now` / `- main_now` terms removed) to confirm this
    case fails against the old math before it was committed.
    """
    checks.note("")
    checks.note("QUEUE SUPERSEDE — queues.apply_run")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(5))

        with Store().write() as snapshot:
            # Run one's verdict: three open review entries.
            snapshot.review.upsert(entry(5, 1, market="12.00"))
            snapshot.review.upsert(entry(5, 2, market="0.75"))
            snapshot.review.upsert(entry(5, 3, market="0.10"))
            # The human answers 5/2 — the entry stays, cleared. An answer outlives the
            # question, and the case below proves it outlives a re-route too.
            snapshot.review.entries["5/2"].cleared_by_human = True

        with Store().write() as snapshot:
            # Run two re-identifies the same box: 5/1 resolves outright (freed), and 5/2
            # and 5/3 now route to parked — the review->parked re-route the bug leaked on.
            added_main, added_parked, released = queues.apply_run(
                snapshot.review,
                snapshot.parked,
                [],
                [
                    entry(5, 2, market="0.05", reason="metadata_detection_disagreement"),
                    entry(5, 3, market="0.05", reason="metadata_detection_disagreement"),
                ],
                freed={"5/1"},
            )

        after = Store().read()
        checks.equal(added_main, 0, "run two queued nothing to main")
        checks.equal(added_parked, 2, "and two cards to parked")
        checks.equal(
            sorted(after.parked.entries),
            ["5/2", "5/3"],
            "both re-routed positions hold live parked entries",
        )
        checks.ok(
            "5/3" not in after.review.entries,
            "the re-routed position's stale review entry is RELEASED — the regression: "
            "each queue's release used to be computed from its own entries alone, so a "
            "review->parked move left the same card open in both files",
        )
        checks.ok(
            "5/1" not in after.review.entries,
            "a freed position leaves review exactly as before",
        )
        checks.ok(
            "5/2" in after.review.entries and after.review.entries["5/2"].cleared_by_human,
            "and the human-cleared entry survives its own re-route: Queue.release protects "
            "cleared_by_human, so the answer outlives the question across queues too",
        )


def check_remove_and_box_delete(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/remove and DELETE /boxes/<box> — D10's rulings 1 and 3.

    THE TWO OPERATIONS THAT DID NOT EXIST BEFORE 2026-08-23, and the two most destructive
    things the server can be asked to do. Ruling 1 overrules "nothing that renumbers may
    exist" for exactly one bounded case, so the boundary is what this section works
    hardest: every refusal in its own code, nothing changed by a refused call, and the
    successful shift moving EVERYTHING keyed by a position — record, photo, sidecar, queue
    entry, cache entry, and the history lines that keep the log true across the move.

    THE PHOTOS CARRY DISTINGUISHABLE BYTES, one byte per card, because "the photo was
    renamed" is only worth asserting if the test can catch the failure that matters: a
    photograph attributed to the wrong record. A shared JPEG blob would pass that by
    construction.
    """
    checks.note("")
    checks.note("MID-BOX REMOVE AND BOX DELETE — D10's owner rulings 1 and 3")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        for i in range(1, 6):
            capture_server.do_capture(
                {"box": 3, "capture_id": f"r{i}", "image": blob(i), "set_hint": "sv9"}
            )
        with Store().write() as snapshot:
            for i in range(2, 6):
                snapshot.inventory.record_identification(
                    f"3/{i}", name=f"N{i}", number=f"{i:03d}", printed_total="102",
                    confidence="high",
                )
            snapshot.cache.put("3/5", {"name": "N5"}, "sha-5", "p1")
            snapshot.review.upsert(
                queues.QueueEntry(
                    position="3/5", box=3, index=5, label=join.Position(3, 5).label,
                    photo=str(capture_server.photo_path(3, 5)),
                    reason="metadata_detection_disagreement", market="2.00",
                )
            )

        # ------------------------------------------------------------- the refusals
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 2, {}),
            "capture_id_required",
            "a remove without the target's capture_id refuses — the aim check is what "
            "stops a replay from deleting the card that slid in",
        )
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r2", "shift": 1}),
            "field_not_settable",
            "and an unknown field refuses before anything is looked up",
        )
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 9, {"capture_id": "r9"}),
            "card_not_found",
            "a position holding no card refuses — there is nothing to shift onto",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r3"}),
            "a WRONG capture_id refuses — a stale read of the box must not delete the "
            "card that now sits at this index",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "capture_id_mismatch", "in its own code")
        checks.equal(
            len(Store().read().inventory.cards), 5, "and a refused aim deleted nothing"
        )

        # A sold or retired gap ABOVE the target blocks the shift, by name; the target
        # itself being terminal refuses by its own door.
        with Store().write() as snapshot:
            snapshot.inventory.retire("3/4", "damaged")
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r2"}),
            "a retired gap above the target refuses the shift — closing it would erase "
            "what the gap means (D10, ruling 1)",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "renumber_blocked", "renumber_blocked")
            checks.ok(
                "card 4 is retired: damaged" in str(caught),
                "and the refusal NAMES the blocker with its reason",
                f"message was: {caught}",
            )
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 4, {"capture_id": "r4"}),
            "card_retired",
            "and the retired card itself refuses removal — departures keep their records",
        )
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/4", master.IDENTIFIED)

        # A listed SKU above blocks it too — its row is already in a file.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.IDENTIFIED, sku="8608859")
            snapshot.inventory.listing("8608859").bump(master.PUSHED, 1)
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r2"}),
            "a listed SKU above the target refuses the shift",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "renumber_blocked", "renumber_blocked")
            checks.ok(
                "8608859" in str(caught) and "1 pushed" in str(caught),
                "naming the SKU and the stage that holds it",
                f"message was: {caught}",
            )
        with Store().write() as snapshot:
            snapshot.inventory.listing("8608859").set(master.PUSHED, 0)

        # ------------------------------------------------------- the successful shift
        body = capture_server.do_remove_card(3, 2, {"capture_id": "r2"})
        checks.equal(body["deleted"], "3/2", "the remove answers with the position it deleted")
        checks.equal(body["shifted"], 3, "and how many records slid down one index")
        checks.equal(body["next_index"], 5, "and the released high-water mark")

        after = Store().read()
        checks.equal(
            {k: after.inventory.cards[k].name for k in sorted(after.inventory.cards)},
            {"3/1": None, "3/2": "N3", "3/3": "N4", "3/4": "N5"},
            "every higher record slid down one index, names intact",
        )
        checks.equal(
            [after.inventory.cards[f"3/{i}"].capture_id for i in (2, 3, 4)],
            ["r3", "r4", "r5"],
            "capture_ids ride along untouched — they name photographs, and no photograph changed",
        )
        photos = sorted(
            p.name for p in capture_server.photo_path(3, 1).parent.glob("*.jpg")
        )
        checks.equal(
            photos,
            ["0001.jpg", "0002.jpg", "0003.jpg", "0004.jpg"],
            "the photos were renamed down with their records — no file left at the top slot",
        )
        checks.ok(
            all(
                capture_server.photo_path(3, idx).read_bytes()[3:4] == bytes([byte])
                for idx, byte in ((2, 3), (3, 4), (4, 5))
            ),
            "and each renamed photo still holds ITS OWN card's bytes — a photograph "
            "attributed to the wrong record is the failure a position label may never cause",
        )
        sidecar_now = json.loads(
            capture_server.sidecar_path(capture_server.photo_path(3, 4)).read_text("utf-8")
        )
        checks.equal(
            sidecar_now.get("index"), 4,
            "the sidecar is regenerated at the new index — the reader can never find one "
            "whose `index` disagrees with its filename",
        )
        moved_entry = after.review.entries.get("3/4")
        checks.ok(
            moved_entry is not None
            and after.review.entries.get("3/5") is None
            and moved_entry.index == 4
            and moved_entry.label == join.Position(3, 4).label
            and moved_entry.photo == str(capture_server.photo_path(3, 4)),
            "the queue entry is re-keyed whole: position, box, index, rendered label, and "
            "the photo path it names",
            f"entry was: {moved_entry!r}",
        )
        checks.ok(
            after.cache.get("3/4") is not None and after.cache.get("3/5") is None,
            "and the paid answer moves with its card",
        )

        events = Store().history()
        renumbered = [e for e in events if e.get("event") == "renumbered"]
        checks.ok(
            len(renumbered) == 1
            and renumbered[0].get("from") == 2
            and renumbered[0].get("count") == 3
            and renumbered[0].get("box") == 3,
            "one `renumbered` line carries the whole mapping — minus-one for every index "
            "above `from`, `count` of them",
            f"events were: {renumbered!r}",
        )
        roll_call = [e for e in events if "renumbered_from" in e]
        checks.equal(
            [(e.get("position"), e.get("event"), e.get("renumbered_from")) for e in roll_call],
            [
                ("3/2", master.IDENTIFIED, "3/3"),
                ("3/3", master.IDENTIFIED, "3/4"),
                ("3/4", master.IDENTIFIED, "3/5"),
            ],
            "and one state line per shifted card at its NEW position — what keeps "
            "_state_before_sale and _state_before_retirement reading the right card's "
            "history after the move",
        )

        # The regression the first HTTP run of this route caught, asserted so it cannot
        # come back: a departure at a SHIFTED position must restore the card's OWN state,
        # not the previous occupant's.
        capture_server.do_retire(3, 2, {"reason": "damaged"})
        put_back = capture_server.do_retire(3, 2, {"undo": True})
        checks.equal(
            put_back["state"],
            master.IDENTIFIED,
            "a retirement reversed at a shifted position restores the card that is THERE "
            "— without the roll-call line it restored the previous occupant's state",
        )

        # The replay of the successful remove: a different card sits at 3/2 now, and the
        # aim check is what notices.
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r2"}),
            "capture_id_mismatch",
            "replaying the remove refuses — the neighbour that slid in is not the card "
            "the request describes",
        )

        # -------------------------------------------------------- the whole-box delete
        refusal(
            checks,
            lambda: capture_server.do_delete_box(9),
            "box_not_found",
            "deleting a box nothing has heard of refuses",
        )
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.SOLD)
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_box(3),
            "a box holding a sold card refuses deletion — those records are history and "
            "commitments, not clutter (D10, ruling 3)",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "box_not_empty_of_commitments",
                "in its own code",
            )
            checks.ok(
                "card 3 is sold" in str(caught),
                "and the refusal names what stands in the way",
                f"message was: {caught}",
            )
        checks.equal(
            len(Store().read().inventory.cards), 4, "and the refusal deleted nothing"
        )
        capture_server.do_mark_sold(3, 3, {"undo": True})

        body = capture_server.do_delete_box(3)
        checks.equal(
            (body["cards"], body["photos"], body["sidecars"]),
            (4, 4, 4),
            "the delete reports what it removed, counted per kind",
        )
        checks.ok(
            body["review_deleted"] == 1 and body["cache_deleted"] == 1,
            "including the queue entry and the paid answer",
            f"body was: {body}",
        )
        checks.ok(
            body["registry_deleted"] and body["directory_removed"],
            "and the registry entry and the emptied photo directory went with it",
        )
        after = Store().read()
        checks.ok(
            not after.inventory.cards
            and after.inventory.boxes.get("3") is None
            and not capture_server.photo_path(3, 1).parent.exists(),
            "a deleted box is a box the store has never heard of",
        )
        checks.ok(
            any(
                e.get("event") == "box_deleted" and e.get("cards") == 4
                and "position" not in e
                for e in Store().history()
            ),
            "one `box_deleted` line carries the box and the card count, with no "
            "`position` key — a box is not at a position",
        )
        _, fresh = capture_server.do_capture(
            {"box": 3, "capture_id": "fresh", "image": blob(9)}
        )
        checks.equal(
            fresh["index"], 1,
            "and recreating the number starts from nothing, like a box never used",
        )


def check_listing_release(checks: Checks) -> None:
    """GET /boxes/<box>/listings and its release — D34, the door the delete gate lacked.

    THE GAP THIS CLOSES WAS FOUND BY A BOX THAT COULD NOT BE DELETED, AND THE MECHANISM IS
    WORTH RESTATING WHERE THE TEST IS. `_listing_hold` blocks a whole-box delete while any
    card's SKU carries a stage, which is right — deleting a copy TCGplayer is holding would
    leave the counts claiming a card that is no longer in the building. But `staged` is drawn
    down in exactly one place, `cli/cmd_join.py`, by the RISE in live quantity a fresh Filtered
    Export reports. An import that never lands never raises live, so the drawdown never runs
    and the count stands forever. On 2026-08-24 that was box 1: 53 Gate B cards behind 45
    records claiming 53 staged copies TCGplayer had not held for two days.

    THE BUDGET IS THE SUBJECT OF MOST OF THIS BLOCK, and it is the owner's ruling of the same
    day. The first build zeroed each SKU outright; a release reached from box 1 could therefore
    give up commitments only box 3's copies could ever have backed. Each SKU now gives up at
    most the UNSOLD copies the calling box holds, which makes that impossible structurally
    rather than by care — and leaves a remainder wherever a SKU is shared, so the box stays
    refused. **That remainder is the intended behaviour**, confirmed by the owner, and it is
    asserted here in both directions: what is given up, and what is deliberately kept.

    ITS OWN `isolated_home`, and this file has now recorded that lesson three times — the
    mass-select cases, then the starvation tier. This block writes LISTINGS, which
    `check_boxes_and_listings` counts and `check_cli_seams` reads through `emit`.
    """
    checks.note("")
    checks.note("LISTING RELEASE — D34, the missing door out of `staged`")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        # SHARED: box 4 holds 2 of 5 staged; box 6 holds 3. OWNED: box 4 holds both.
        # SOLDCOPY: box 4 holds 1 unsold and 1 sold against 2 staged.
        layout = (
            (4, 1, "SHARED"), (4, 2, "SHARED"), (6, 1, "SHARED"), (6, 2, "SHARED"),
            (6, 3, "SHARED"), (4, 3, "OWNED"), (4, 4, "OWNED"),
            (4, 5, "SOLDCOPY"), (4, 6, "SOLDCOPY"),
        )
        for box, index, _ in layout:
            capture_server.do_capture(
                {"box": box, "capture_id": f"L{box}{index}", "image": blob(index)}
            )
        with Store().write() as snapshot:
            inventory = snapshot.inventory
            for box, index, sku in layout:
                key = f"{box}/{index}"
                inventory.record_identification(
                    key, name="N", number="001", printed_total="102", confidence="high",
                )
                inventory.cards[key].sku = sku
            inventory.set_state("4/6", master.SOLD)
            inventory.listing("SHARED", condition="Near Mint").set(master.STAGED, 5)
            inventory.listing("OWNED", condition="Near Mint").set(master.STAGED, 2)
            inventory.listing("SOLDCOPY", condition="Near Mint").set(master.STAGED, 2)

        # ------------------------------------------------------- the free preflight first
        plan = answers(
            checks,
            lambda: capture_server.do_box_listings(4),
            "the preflight answers without a confirm and without writing — D33's shape one "
            "register down, and the step the release control may not be drawn before",
        )
        if plan is not None:
            rows = {row["sku"]: row for row in plan["listings"]}
            checks.equal(
                sorted(rows), ["OWNED", "SHARED", "SOLDCOPY"], "every held SKU is named"
            )
            checks.equal(
                (rows["SHARED"]["copies_here"], rows["SHARED"]["releases"],
                 rows["SHARED"]["after"]),
                (2, {"staged": 2}, {"staged": 3}),
                "a SHARED SKU gives up only what THIS box's copies could account for — the "
                "owner's ruling: a release reached from box 4 may never give up box 6's three",
            )
            checks.ok(
                rows["SHARED"]["still_held"]
                and rows["SHARED"]["also_in_boxes"] == [{"box": 6, "copies": 3}],
                "and it says so before the press, naming the other box and its copies — the "
                "blast radius the first build reported only in the receipt",
                f"row was: {rows['SHARED']!r}",
            )
            checks.equal(
                (rows["OWNED"]["releases"], rows["OWNED"]["after"], rows["OWNED"]["still_held"]),
                ({"staged": 2}, {}, False),
                "a SKU this box holds every copy of goes to zero, which is the ordinary case",
            )
            checks.equal(
                (rows["SOLDCOPY"]["copies_here"], rows["SOLDCOPY"]["releases"]),
                (1, {"staged": 1}),
                "a SOLD copy does not count toward the budget — it has already left, and it "
                "is not one of the copies a remaining commitment could be backed by",
            )
            checks.ok(
                plan["frees_box"] is False and plan["still_held"] == ["SHARED", "SOLDCOPY"],
                "and `frees_box` states up front that the box will STILL be refused — the "
                "one outcome a person would otherwise read as a bug",
                f"summary was: {plan!r}",
            )
        checks.equal(
            Store().read().inventory.listing_counts(),
            {"pushed": 0, "staged": 9, "live": 0},
            "and the preflight moved nothing: it is a read",
        )

        # --------------------------------------------------------------- the refusals
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(4, {}),
            "confirm_required",
            "a release without an explicit confirm refuses — this route's whole content is "
            "a claim about a system the process cannot see, so it may not be made by accident",
        )
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(4, {"confirm": "true"}),
            "confirm_required",
            "and a STRINGIFIED confirm refuses too — `\"false\"` is truthy in Python, so a "
            "flag whose two values are do-it and do-not is the last place to coerce",
        )
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(4, {"confirm": True, "skus": []}),
            "field_not_settable",
            "an unknown field refuses before the box is looked up",
        )
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(9, {"confirm": True}),
            "box_not_found",
            "a box nothing has heard of refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_box_listings(9),
            "box_not_found",
            "and so does the preflight, in the same code",
        )
        checks.equal(
            Store().read().inventory.listing_counts(),
            {"pushed": 0, "staged": 9, "live": 0},
            "and not one refusal moved a count",
        )

        # ------------------------------------------------------- the delete it unblocks
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_box(4),
            "the box refuses deletion first — this is the state D34 was built for",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "box_not_empty_of_commitments", "in its own code"
            )

        body = capture_server.do_release_box_listings(4, {"confirm": True})
        checks.equal(
            (body["released"], body["given_up"]),
            (3, {"staged": 5}),
            "the release gives up 2 + 2 + 1 — every SKU budgeted by this box's unsold copies, "
            "never the whole count",
        )
        checks.ok(
            body["frees_box"] is False and body["still_held"] == ["SHARED", "SOLDCOPY"],
            "and the receipt repeats that the box is still held rather than implying success",
            f"body was: {body}",
        )
        checks.equal(body["also_in_boxes"], [6], "naming the box whose copies remain")

        after = Store().read().inventory
        checks.equal(
            (after.listings["SHARED"].staged, after.listings["OWNED"].staged,
             after.listings["SOLDCOPY"].staged),
            (3, 0, 1),
            "BOX 6'S THREE STAGED COPIES SURVIVE UNTOUCHED — the whole point of the budget, "
            "and what the first build could not promise",
        )
        checks.ok(
            after.listings["OWNED"].staged_at is None
            and after.listings["SHARED"].staged_at is not None,
            "`staged_at` clears only where staged reached zero: a record with copies REMAINING "
            "really has been staged since that date, which is what the stale warning looks for",
        )
        checks.ok(
            after.listings.get("OWNED") is not None
            and after.listings["OWNED"].condition == "Near Mint",
            "the record survives at zeros rather than being popped — `_listing_hold` already "
            "reads all-zeros as not held, and the condition is worth keeping",
        )
        checks.ok(
            any(
                e.get("event") == "listings_released"
                and e.get("box") == 4
                and e.get("skus") == 3
                and e.get("copies") == {"staged": 5}
                and e.get("still_held") == ["SHARED", "SOLDCOPY"]
                and "position" not in e
                for e in Store().history()
            ),
            "one `listings_released` line carries the box, the SKU count, the copies AND what "
            "stayed held — without the last, the log would say a release happened and not "
            "that it was partial",
            f"history was: {[e for e in Store().history() if e.get('event') == 'listings_released']!r}",
        )
        checks.ok(
            capture_server.LISTINGS_RELEASED not in master.STATES,
            "and the event name is not a state — `_state_before_sale` filters against "
            "`master.STATES`, so a collision would restore a reversed sale to it",
        )

        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_box(4),
            "THE BOX IS STILL REFUSED, exactly as the plan said — a shared SKU keeps copies "
            "this box could not account for, and the owner ruled that remainder in",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "box_not_empty_of_commitments", "in its own code"
            )

        # A second release gives up the rest of what box 4's copies can account for. The
        # SOLDCOPY remainder is beyond it: one unsold copy already spent its budget.
        capture_server.do_release_box_listings(4, {"confirm": True})
        checks.equal(
            Store().read().inventory.listings["SHARED"].staged,
            1,
            "a second release spends the budget again — each press is its own assertion, and "
            "the cap is per press rather than a memory of what box 4 has ever released",
        )

        # ----------------------------------------- the boundary: it frees listings ONLY
        with Store().write() as snapshot:
            for sku in ("SHARED", "SOLDCOPY"):
                snapshot.inventory.listings[sku].release(99)
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_box(4),
            "a box held open by a SOLD card still refuses once every listing in it is clear "
            "— the release answers one of the three grounds and must not reach the others",
        )
        if caught is not None:
            checks.ok(
                "is sold" in str(caught),
                "and it refuses for the sale, naming it",
                f"message was: {caught}",
            )
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(4, {"confirm": True}),
            "nothing_to_release",
            "and with every stage at zero a replay refuses rather than answering a cheerful "
            "200 — what keeps a stale screen distinguishable from a release that worked",
        )


def check_queue_starvation(checks: Checks) -> None:
    """The starvation tier, in its own home because it writes a queue the other blocks count.

    ITS OWN `isolated_home` IS THE POINT, and it is this file's own recorded lesson: the mass-
    select cases were first written inside a block that counts history lines over a box it
    builds card by card, and they failed on the fixture rather than on the code. The first
    draft of THIS block did exactly the same thing — six entries added to `check_queues`'s
    store, and four of that block's own assertions went red because they count what is open.

    `upsert` OVERWRITES `first_seen` WITH TODAY on insert; it preserves only an EXISTING
    stamp. That is right for the store — a card is first seen when it is first queued — and
    it means a test cannot age an entry by passing the field in. The stamp is written after
    the upsert, inside the same session, which is also the only way a real entry ever gets
    old.
    """
    with isolated_home():
        stamp = lambda days: (  # noqa: E731
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        with Store().write() as snapshot:
            snapshot.review.upsert(entry(1, 1, market="12.00"))
            snapshot.review.upsert(entry(1, 2, market="0.75"))
            snapshot.review.upsert(entry(1, 3, market=None))
            snapshot.review.upsert(entry(2, 1, market=None))
            snapshot.review.upsert(entry(2, 2, market=None))
            # Aged after the fact, per the docstring.
            snapshot.review.entries["2/1"].first_seen = stamp(queues.STARVATION_DAYS + 5)
            snapshot.review.entries["2/2"].first_seen = stamp(queues.STARVATION_DAYS + 40)
            snapshot.review.entries["1/3"].first_seen = stamp(queues.STARVATION_DAYS - 5)

        positions = [e.position for e in Store().read().review.open_entries]
        checks.equal(
            positions,
            ["2/2", "2/1", "1/1", "1/2", "1/3"],
            "starved first and OLDEST-first inside the tier, then docs/DESIGN.md's "
            "expensive-first order untouched, then the unpriced card that has not yet "
            "starved — the tier promotes, it does not re-score (store/queues.py:sort_key)",
        )

        one_day_short = queues.QueueEntry(
            position="9/9",
            box=9,
            index=9,
            label="x",
            photo="p",
            reason="r",
            candidates=[],
            first_seen=stamp(queues.STARVATION_DAYS - 1),
        )
        checks.equal(
            one_day_short.sort_key[0],
            2,
            "the threshold is a real boundary: one day short of it, an unpriced card is "
            "still last and has not been quietly promoted",
        )
        checks.equal(
            queues.QueueEntry(
                position="9/9", box=9, index=9, label="x", photo="p", reason="r", candidates=[]
            ).sort_key[0],
            2,
            "and an entry with NO first_seen can never starve at all: an unmeasurable wait "
            "must not outrank a known price (store/queues.py:_age_days returns None)",
        )


def check_queues(checks: Checks) -> None:
    """GET /queues — the two standing queues, in the order they are meant to be worked.

    THE ORDER IS THE ONLY THING THIS ROUTE ADDS, so it is what is asserted. `docs/DESIGN.md`
    calls the expensive-first sort "built and runs today" and says the screen's job is to
    make it visible; a route that quietly re-sorted, or an app that did, would throw away a
    ranking the run report has already printed and the owner has already read.
    """
    checks.note("")
    checks.note("QUEUES — GET /queues")

    with isolated_home():
        empty = capture_server.do_queues()
        checks.equal(
            empty,
            {"review": [], "parked": []},
            "an empty store answers with two empty lists, never a null or a 404",
        )

        for _ in range(3):
            capture_server.do_capture(capture_payload(3))
        capture_server.do_capture(capture_payload(4))

        with Store().write() as snapshot:
            # Prices chosen so every leg of `QueueEntry.sort_key` is exercised by one list:
            # two cards at the same price to force the box-walk tiebreak, one cheaper, one
            # unpriced. An `open_entries` that sorted by insertion, by position, or by price
            # ascending all give different answers to this.
            snapshot.review.upsert(entry(3, 1, market="0.75"))
            snapshot.review.upsert(entry(3, 2, market=None))
            snapshot.review.upsert(entry(3, 3, market="12.00"))
            snapshot.review.upsert(entry(4, 1, market="12.00"))
            snapshot.parked.upsert(entry(3, 2, market="0.02", reason="no_market_data"))

        body = capture_server.do_queues()
        checks.equal(
            [row["position"] for row in body["review"]],
            ["3/3", "4/1", "3/1", "3/2"],
            "priced first and DESCENDING, ties broken by box-walk order, unpriced last "
            "(docs/DESIGN.md: worked expensive-first, and that ordering has to be visible)",
        )
        checks.equal(
            [row["position"] for row in body["review"]],
            [e.position for e in Store().read().review.open_entries],
            "and the route hands over Queue.open_entries' own order — one sort, not a "
            "second copy of QueueEntry.sort_key living in the server",
        )
        checks.equal(
            [row["position"] for row in body["parked"]],
            ["3/2"],
            "parked is a SEPARATE list: main is work, parked is the low-value queue, and "
            "merging them here is how the $12 cards get missed (store/queues.py)",
        )

        row = body["review"][0]
        checks.equal(
            sorted(row),
            [
                "age_days",
                "box",
                "candidates",
                "cleared_by_human",
                "confidence",
                "first_seen",
                "index",
                "label",
                "market",
                "photo",
                "position",
                "read",
                "reason",
            ],
            "a queue row is the whole QueueEntry record plus age_days — not a projection "
            "the app has to hold against review.json field by field",
        )
        checks.equal(
            row["candidates"],
            CANDIDATES,
            "the candidate rows ride along: they are what the review screen offers, and a "
            "second call to fetch them would be a screen that can draw before it can answer",
        )
        checks.equal(row["market"], "12.00", "with the price the sort was made on")
        checks.equal(row["reason"], "metadata_detection_disagreement", "and the reason code")
        checks.equal(
            row["photo"],
            str(capture_server.photo_path(3, 3)),
            "photo is the path on the Mac, exactly as Card.photo is — GET /photo is D6's "
            "route and the only way a browser sees it",
        )
        checks.equal(
            row["age_days"], 0, "and age_days is computed here rather than in the app"
        )
        checks.equal(
            row["label"],
            join.Position(3, 3).label,
            "the label is pipeline/join.py's, the same one every other route answers with",
        )

        # A cleared entry is not work. It stays in the file — `Queue.release` preserves it so
        # a human's answer outlives the question — and this route answers "what is left".
        with Store().write() as snapshot:
            snapshot.review.entries["3/1"].cleared_by_human = True
        after = capture_server.do_queues()
        checks.equal(
            [row["position"] for row in after["review"]],
            ["3/3", "4/1", "3/2"],
            "a cleared entry disappears from the queue payload",
        )
        checks.ok(
            Store().read().review.entries.get("3/1") is not None,
            "but stays in review.json: the answer outlives the question (store/queues.py)",
        )
        checks.equal(
            capture_server.do_status()["queues"],
            {"review": 3, "parked": 1},
            "and GET /status counts OPEN entries, not every record in the file — the two "
            "were indistinguishable until something set cleared_by_human, and this is the "
            "number the owner reads to decide whether there is work left",
        )

        # AND THAT COUNT IS A SORT, which is what made the health route breakable. `len(Queue)`
        # runs `open_entries`, so a `market` that is not a number raises InvalidOperation and a
        # `box` that arrived as a JSON string raises TypeError on the tuple compare — both
        # measured escaping /status as a 500 once 7b put these counts in it. It is the one
        # route you reach for when something is wrong, and it already refuses to be taken down
        # by a bad inventory record; the queues are held to the same rule.
        raw = Store().queue_path(queues.MAIN)
        healthy = raw.read_text("utf-8")
        for label, damage in (
            ("a market that is not a number", {"market": "twelve"}),
            ("a box that arrived as a string", {"box": "3"}),
        ):
            broken = json.loads(healthy)
            broken["3/3"].update(damage)
            raw.write_text(json.dumps(broken), encoding="utf-8")
            report = answers(
                checks,
                capture_server.do_status,
                f"{label}: /status still ANSWERS rather than raising",
            )
            if report is not None:
                checks.ok(
                    report["queues"]["review"] is None,
                    f"{label}: with the count it cannot make left null",
                )
                checks.equal(
                    report["queues"]["parked"],
                    1,
                    f"{label}: and parked is still counted — one corrupt file does not hide "
                    f"what is waiting in the other",
                )
                checks.ok(
                    "review.json" in report.get("problem", ""),
                    f"{label}: and the problem names the file to go and fix",
                    f"problem was: {report.get('problem')!r}",
                )

        # NOT the record count as a substitute. `len(queue.entries)` would answer 4 here and
        # is the number this route deliberately stopped publishing: it counts cleared entries,
        # so it says there is work left after the last card has been answered. Wrong in the
        # direction of "more to do" is worse than silent on a number the owner works from.
        checks.equal(
            len(Store().read().review.entries),
            4,
            "the null is a REFUSAL to count, not an empty queue — the file still holds its "
            "four records",
        )

        # Two findings at once, which only became reachable when the queues joined the
        # inventory in here. They are joined into the one `problem` string every client
        # already reads: with a single finding it is byte-identical to what this route has
        # always answered, which is what made joining cheaper than a new shape.
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/1"].box = "three"
        broken = json.loads(healthy)
        broken["3/3"]["market"] = "twelve"
        raw.write_text(json.dumps(broken), encoding="utf-8")
        both_wrong = answers(
            checks,
            capture_server.do_status,
            "a corrupt inventory record AND a corrupt queue record at once: /status answers",
        )
        if both_wrong is not None:
            checks.ok(
                both_wrong["next_index"] is None
                and both_wrong["queues"]["review"] is None,
                "with each finding nulling its own field and neither taking the route down",
            )
            checks.ok(
                "review.json" in both_wrong.get("problem", "")
                and "the inventory holds a card" in both_wrong.get("problem", ""),
                "and both sentences travel in the one `problem` string, so neither is the "
                "one that got dropped",
                f"problem was: {both_wrong.get('problem')!r}",
            )


# ------------------------------------------------------------------------ the review answer


def check_review_answer(checks: Checks) -> None:
    """POST /review/<box>/<index>/answer — D4's one-tap choice.

    THE REFUSAL THAT MATTERS IS `sku_not_a_candidate`. `CLAUDE.md`'s hard rule — never guess
    an identification, ambiguity goes to the review queue with its photo — is a rule about
    the pipeline, and a screen that could write an arbitrary SKU onto a card would be that
    same rule broken by hand: an answer nothing ever proposed, indistinguishable afterwards
    from one that was, on the card the pipeline was least sure about.

    AND IT IS CHECKED AGAINST ONE ENTRY'S ROWS, which is where that refusal was quietly
    escapable. Two positions here sit in both queue files with DIFFERENT offers on each side
    — 3/4 with rows in both, 3/6 with an empty offer in the one that governs — because a
    fixture that gives both entries the same candidates cannot tell a union apart from either
    list, and that is exactly the fixture this section shipped with.
    """
    checks.note("")
    checks.note("REVIEW ANSWER — POST /review/<box>/<index>/answer")

    holo = CANDIDATES[0]
    reverse = CANDIDATES[1]

    with isolated_home():
        for _ in range(6):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            for key in ("3/1", "3/2", "3/3", "3/4", "3/5", "3/6"):
                snapshot.inventory.set_state(key, master.IDENTIFIED)
            snapshot.review.upsert(entry(3, 1, market="12.00"))
            # No candidates at all — `cli/resolve.py:failure_entry`'s shape, for a card whose
            # identification failed outright. There is nothing to choose between.
            snapshot.review.upsert(
                entry(3, 3, candidates=[], reason="identification_failed")
            )
            # In BOTH files at once, which nothing in store/queues.py prevents — and the two
            # entries OFFER DIFFERENT ROWS, which is the whole point of the pair. Identical
            # candidates on both sides is what made this case blind to the union bug.
            snapshot.review.upsert(entry(3, 4, market="12.00"))
            snapshot.parked.upsert(
                entry(3, 4, market="0.05", candidates=[dict(STALE_CANDIDATE)])
            )
            # Parked only, so the parked path is answerable on its own.
            snapshot.parked.upsert(entry(3, 5, market="0.05"))
            # In both, with the EMPTY offer in the queue that governs. Answerable under a
            # union — parked's rows would fill the gap — and refused when one entry decides.
            snapshot.review.upsert(entry(3, 6, candidates=[], reason="card_not_detected"))
            snapshot.parked.upsert(entry(3, 6, market="0.05"))
            # 3/2 is captured and identified and in no queue at all.

        good = {"sku": reverse["sku"], "condition": reverse["condition"]}

        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, dict(good, state="sold")),
            "field_not_settable",
            "an answer naming `state` is refused: listing transitions are not settable here",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"condition": reverse["condition"]}),
            "sku_required",
            "an answer with no sku refuses as sku_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"sku": reverse["sku"]}),
            "condition_required",
            "and one with no condition refuses as condition_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(9, 9, good),
            "card_not_found",
            "an answer for a position that holds no card refuses — this route answers a "
            "card that exists and never creates one",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 2, good),
            "not_in_queue",
            "a card that is not waiting in either queue refuses in its OWN code, not as "
            "card_not_found — the position is real and the client is asking about the "
            "wrong card",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(3, 3, good),
            "an entry recording no candidate rows refuses rather than accepting a free "
            "answer into the one field the hard rule protects",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "no_candidates",
                "and it refuses as no_candidates",
            )
            checks.ok(
                "identification_failed" in str(caught),
                "and the refusal names why the card is queued, since that is what says "
                "whether it needs a re-shoot or a re-identify",
                f"message was: {caught}",
            )

        # THE ONE THIS SECTION EXISTS FOR.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(
                3, 1, {"sku": "9999999", "condition": holo["condition"]}
            ),
            "a sku the pipeline never offered is REFUSED — never guess an identification "
            "(CLAUDE.md), and a screen that could write one is that rule broken by hand",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "sku_not_a_candidate",
                "and it refuses in its own code",
            )
            checks.ok(
                holo["sku"] in str(caught) and reverse["sku"] in str(caught),
                "and the refusal names the rows that WERE offered, so the next request is "
                "the right one rather than another guess",
                f"message was: {caught}",
            )

        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                3, 1, {"sku": reverse["sku"], "condition": holo["condition"]}
            ),
            "condition_mismatch",
            "a real sku with the WRONG condition refuses: the pair is redundant on the "
            "wire precisely so a screen drawn from a re-joined queue file cannot answer "
            "one row while believing it answered another",
        )

        checks.ok(
            Store().read().inventory.get("3/1").sku is None,
            "and not one of those refusals wrote a sku onto the card",
        )

        # ------------------------------------------------------------------ the answer
        body = capture_server.do_review_answer(3, 1, good)
        checks.equal(body["answered"], "3/1", "an answer reports the position it answered")
        checks.equal(body["sku"], reverse["sku"], "and the sku it wrote")
        checks.equal(
            body["condition"],
            reverse["condition"],
            "and the condition, taken from the candidate row rather than echoed back",
        )
        checks.ok(
            body["review_cleared"] and not body["parked_cleared"],
            "and says which queue it cleared, the way undo says what it removed",
        )
        checks.equal(
            body["card"]["label"],
            join.Position(3, 1).label,
            "the returned card is a decorated inventory row — the same shape GET "
            "/inventory answers with, so the app needs no second vocabulary for a card",
        )
        checks.equal(
            body["restores_to"],
            {"sku": None, "condition": None},
            "and what an undo would put back: the pair of NULLS a never-identified card "
            "held, which is the NORMAL case and not an empty one — a card is in a review "
            "queue precisely because it has never carried a SKU, and the reversal returns "
            "it to carrying none (D28)",
        )
        checks.ok(
            body.get("undone") is False,
            "and which direction the call went, false rather than absent, the way the "
            "sale route says it",
            f"undone was: {body.get('undone')!r}",
        )
        checks.equal(
            last_event("3/1").get("restores_to"),
            {"sku": None, "condition": None},
            "and the `answered` HISTORY line carries the same pair — THE BLOCKER'S "
            "REGRESSION: the line used to log only what the route WROTE, never what it "
            "overwrote, so nothing anywhere could say what an undo should put back",
        )

        answered = Store().read()
        checks.equal(answered.inventory.get("3/1").sku, reverse["sku"], "the sku reaches the card")
        checks.equal(
            answered.inventory.get("3/1").condition,
            reverse["condition"],
            "and so does the condition",
        )
        checks.equal(
            answered.inventory.get("3/1").state,
            master.IDENTIFIED,
            "and the card's STATE is untouched: emit owns the move to pushed, and the app "
            "reads state rather than setting it",
        )

        checks.ok(
            answered.review.entries["3/1"].cleared_by_human,
            "the entry is CLEARED, not deleted — cleared_by_human is the flag "
            "store/queues.py was built around and nothing had ever written",
        )
        checks.equal(
            [row["position"] for row in capture_server.do_queues()["review"]],
            ["3/4", "3/3", "3/6"],
            "so it leaves the queue payload, and the ones still waiting keep their order — "
            "priced 3/4 ahead of the unpriced pair, which fall back to box-walk order",
        )

        # The reason clearing beats deleting: a later `./pkmnscan join` re-queues every card
        # it could not resolve, and this card is still unresolved as far as the pipeline is
        # concerned. Popping the entry would let it ask the same question again.
        with Store().write() as snapshot:
            requeued = snapshot.review.upsert(entry(3, 1, market="12.00"))
        checks.ok(
            not requeued,
            "and a later join CANNOT re-ask it: Queue.upsert refuses to re-queue a cleared "
            "position, which is what a deletion here would have thrown away",
        )
        checks.ok(
            Store().read().review.entries["3/1"].cleared_by_human,
            "and the re-queue left the answer alone",
        )

        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, good),
            "already_answered",
            "answering it twice refuses in its own code — the two-device case (D5, D13), "
            "where the remedy is to reload rather than to retry",
        )

        # THE LAUNDERING CASE — the one this section gained on 2026-08-13, and the reason the
        # offer is ONE entry's. 3/4 sits in both files: review offers the two rows above,
        # parked offers a row review never did. Pooling them, which is what this route did,
        # let a stale parked entry authorise a SKU nothing had proposed for the row being
        # answered — and afterwards the card carries a real catalog SKU with nothing on it to
        # say it was never offered. Measured before the fix: accepted, written to the card,
        # and both queues cleared behind it.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(
                3,
                4,
                {
                    "sku": STALE_CANDIDATE["sku"],
                    "condition": STALE_CANDIDATE["condition"],
                },
            ),
            "a sku only the PARKED entry offered is refused for a card sitting in both — "
            "the offer is one entry's rows, never the union of two files",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "sku_not_a_candidate",
                "and it refuses in the same code an invented sku gets, because it IS one: "
                "no screen ever showed that row for the entry being answered",
            )
            checks.ok(
                "review" in str(caught) and holo["sku"] in str(caught),
                "and the refusal NAMES the queue whose rows govern — the other row is on "
                "screen too, so `not offered` reads as a bug without it",
                f"message was: {caught}",
            )
        unlaundered = Store().read()
        checks.ok(
            unlaundered.inventory.get("3/4").sku is None,
            "and the refusal reached neither the card...",
        )
        checks.ok(
            not unlaundered.review.entries["3/4"].cleared_by_human
            and not unlaundered.parked.entries["3/4"].cleared_by_human,
            "...nor either queue entry: a refused answer clears nothing, so the card is "
            "still on screen to be answered properly",
        )

        # Wrapped, unlike the answers above it, because the refusal that must precede it is
        # the whole point: a route that accepted the laundered sku has already cleared this
        # card, and the legitimate answer then refuses `already_answered`. That is a red line
        # about the case above, not a crash that hides the rest of the section.
        both = answers(
            checks,
            lambda: capture_server.do_review_answer(3, 4, good),
            "and the row the governing entry DID offer is still accepted — one entry decides "
            "what may be answered, it does not make the card unanswerable",
        )
        if both is not None:
            checks.ok(
                both["review_cleared"] and both["parked_cleared"],
                "a position sitting in BOTH files is cleared in both — clearing one would "
                "leave the screen showing a card whose answer is already written",
            )
            checks.equal(
                Store().read().inventory.get("3/4").sku,
                reverse["sku"],
                "and the sku written is the one review offered",
            )

        # The same rule from the other side. Review holds 3/6 with no candidates while parked
        # holds it with two — under a union the parked rows fill the gap and the answer is
        # accepted, which is precisely the laundering above wearing a different shape.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(3, 6, good),
            "an EMPTY offer in the governing queue is not an opening for the other file's "
            "rows — it refuses",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "no_candidates",
                "and it refuses as no_candidates: the card needs a re-shoot or a "
                "re-identify, not an answer borrowed from the parked entry",
            )
            checks.ok(
                "review" in str(caught) and "card_not_detected" in str(caught),
                "naming the queue it read the offer from and why that card is queued",
                f"message was: {caught}",
            )

        parked_only = capture_server.do_review_answer(3, 5, good)
        checks.ok(
            parked_only["parked_cleared"] and not parked_only["review_cleared"],
            "and a parked-only card is answerable on its own",
        )
        checks.ok(
            "review_cleared" in parked_only and "parked_cleared" in parked_only,
            "both flags are on every answer, false rather than absent — the client drops "
            "both rows from one response and never has to tell `not cleared` from `the "
            "server did not say`",
            f"body keys: {sorted(parked_only)}",
        )
        checks.equal(
            capture_server.do_status()["queues"],
            {"review": 2, "parked": 1},
            "GET /status follows the answers down — what is left open is exactly the two "
            "cards no valid answer was offered for (3/3 and 3/6, the latter still parked)",
        )

        # Nothing outside inventory.json and the queues moved. The paid answer in particular
        # is left exactly as it was: see the route's own comment for why marking it
        # human-cleared claims more than the human actually said.
        checks.ok(
            not Store().read().cache.entries,
            "and identifications.json is untouched — this route records which ROW was "
            "chosen, not that the model's read was vouched for",
        )

    # ------------------------------------------------------------- the reversal (D28)
    # {"undo": true} on the same route, in its own home: the last two cases corrupt the
    # history log, and everything above reads a store whose log is intact.
    checks.note("")
    checks.note("REVIEW ANSWER UNDO — the same route, reversed (D28)")

    prior = {"sku": DUNSPARCE_SKU, "condition": "Near Mint"}

    with isolated_home():
        for _ in range(6):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            # 3/1 CARRIED A REAL PAIR BEFORE THE ANSWER — the case the null-pair answer
            # above cannot cover — and sits in BOTH files, so its undo has two entries to
            # reopen. first_seen is seeded to a fixed day on both, because "the undo does
            # not reset how long the card has been waiting" is unfalsifiable against
            # today().
            snapshot.inventory.set_state(
                "3/1", master.IDENTIFIED, sku=prior["sku"], condition=prior["condition"]
            )
            snapshot.review.upsert(entry(3, 1, market="12.00"))
            snapshot.parked.upsert(
                entry(3, 1, market="0.05", candidates=[dict(STALE_CANDIDATE)])
            )
            snapshot.review.entries["3/1"].first_seen = "2026-08-01"
            snapshot.parked.entries["3/1"].first_seen = "2026-08-01"
            # 3/2 WAS ANSWERED BY A SERVER OLDER THAN `restores_to` — the entry is cleared
            # and the card carries a SKU, but its `answered` line records only what was
            # written. Hand-built inside the store's own write, because no current route
            # can produce this line any more; that is the point of the case.
            snapshot.inventory.set_state(
                "3/2",
                master.IDENTIFIED,
                sku=DUNSPARCE_REVERSE_SKU,
                condition="Near Mint Reverse Holofoil",
            )
            snapshot.review.upsert(entry(3, 2, market="12.00"))
            snapshot.review.entries["3/2"].cleared_by_human = True
            capture_server._history(
                snapshot.inventory,
                capture_server.ANSWERED,
                "3/2",
                sku=DUNSPARCE_REVERSE_SKU,
                condition="Near Mint Reverse Holofoil",
                queue=queues.MAIN,
                reason="metadata_detection_disagreement",
            )
            # 3/3 is captured and in no queue at all. 3/4 waits OPEN in review. 3/5 and
            # 3/6 are the two listing-hold cases below.
            snapshot.review.upsert(entry(3, 4, market="12.00"))
            snapshot.review.upsert(entry(3, 5, market="12.00"))
            snapshot.review.upsert(entry(3, 6, market="12.00"))

        # The refusals that need no answer standing, first.
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"undo": True, "sku": "123"}),
            "field_not_settable",
            "an undo CARRYING A SKU is refused rather than obeyed with the sku silently "
            "ignored — the two directions accept different fields, and a body claiming "
            "both at once is a client that does not know which call it is making",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"undo": "true"}),
            "undo_invalid",
            "and `undo` must be a JSON boolean — the string \"true\" refuses, the same "
            "rule the sale's flag was shaped by, because a string is not a boolean and "
            "this flag's two readings are do-it and undo-it",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(9, 9, {"undo": True}),
            "card_not_found",
            "an undo against a position holding no card refuses as card_not_found — a "
            "position with no record has nothing to reverse ONTO",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 3, {"undo": True}),
            "not_in_queue",
            "a card in NEITHER queue file refuses in its own code: the question is gone "
            "entirely, and the remedy is another card, not a retry",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 4, {"undo": True}),
            "not_answered",
            "and an OPEN entry refuses in a third — nothing cleared it, so there is no "
            "answer standing to take back",
        )

        # ------------------------------------------------ the pair the answer overwrote
        overwrote = capture_server.do_review_answer(3, 1, good)
        checks.equal(
            overwrote["restores_to"],
            dict(prior),
            "an answer over a card that already carried a SKU reports the REAL pair it "
            "overwrote, not nulls — read off the card inside the lock, the last moment "
            "anything knows it",
        )
        checks.equal(
            last_event("3/1").get("restores_to"),
            dict(prior),
            "and the `answered` line carries the same real pair — the other half of the "
            "blocker's regression: the null-pair line above cannot tell `logged the prior "
            "pair` from `logged a default`",
        )

        # THE D28 BOUNDARY, FIRST SIDE: while the answer stands, store/queues.py holds the
        # door shut exactly as it did before reopen existed.
        with Store().write() as snapshot:
            requeued = snapshot.review.upsert(entry(3, 1, market="99.00"))
            kept = snapshot.review.release(["3/2", "3/4", "3/5", "3/6"])
        # `.get`, not a subscript, here and below: an entry these cases can lose IS the
        # failure under test, and last_event's rule applies — a bare ["3/1"] turns that
        # red line into a KeyError that hides every check behind it.
        shut = Store().read().review.entries.get("3/1")
        checks.ok(
            not requeued
            and shut is not None
            and shut.cleared_by_human
            and shut.market == "12.00",
            "while the answer stands, Queue.upsert refuses to re-queue the position — "
            "the entry is untouched, still cleared, still carrying its old fields",
            f"requeued={requeued!r} entry={shut!r}",
        )
        checks.ok(
            kept == [] and shut is not None,
            "and Queue.release keeps the cleared entry even when a run stops naming it — "
            "the answer outlives the question (D28's boundary, first side)",
            f"released: {kept!r}",
        )

        # --------------------------------------------------------- the successful undo
        # Wrapped, because a refusal here is the plausible regression: every guard this
        # route runs sits in front of the one write the case is about, and an exception
        # escaping would hide the store-side assertions below it.
        undone = answers(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"undo": True}),
            "an undo inside the window goes through — the window is the screen's, so the "
            "server's only question is whether an answer is standing",
        )
        if undone is not None:
            checks.ok(undone["undone"], "and it reports itself as a reversal")
            checks.equal(
                undone["sku"],
                prior["sku"],
                "and the pair the answer overwrote is back on the card — the sku",
            )
            checks.equal(
                undone["condition"], prior["condition"], "and the condition with it"
            )
            checks.equal(
                undone["restores_to"],
                None,
                "restores_to is null on the reversal — nothing left to reverse, never an "
                "offer of a second undo",
            )
            checks.ok(
                undone["review_reopened"] and undone["parked_reopened"],
                "and BOTH files got their entries back for a position held by both — "
                "reopening one would leave the card half-answered, waiting on one screen "
                "and cleared on the other",
            )
        reopened = Store().read()
        checks.equal(
            reopened.inventory.get("3/1").sku, prior["sku"], "the store agrees on the sku"
        )
        checks.equal(
            reopened.inventory.get("3/1").condition,
            prior["condition"],
            "and on the condition",
        )
        checks.equal(
            reopened.inventory.get("3/1").state,
            master.IDENTIFIED,
            "and the card's STATE never moved — the answer set no state, so its reversal "
            "sets none back",
        )
        in_review = reopened.review.entries.get("3/1")
        in_parked = reopened.parked.entries.get("3/1")
        checks.ok(
            in_review is not None
            and in_parked is not None
            and not in_review.cleared_by_human
            and not in_parked.cleared_by_human,
            "the entries are open again in both files, waiting exactly as before",
        )
        checks.ok(
            in_review is not None
            and in_parked is not None
            and in_review.first_seen == "2026-08-01"
            and in_parked.first_seen == "2026-08-01",
            "and first_seen is untouched on both — the card has been waiting since it "
            "was first queued, and an answer that stood for twenty seconds does not "
            "reset that",
            f"first_seen: {in_review and in_review.first_seen!r}",
        )

        # THE D28 BOUNDARY, SECOND SIDE: after reopen there is no answer left to guard.
        with Store().write() as snapshot:
            snapshot.review.upsert(
                entry(3, 1, market="99.00", candidates=[dict(STALE_CANDIDATE)])
            )
        requeued_entry = Store().read().review.entries.get("3/1")
        checks.ok(
            requeued_entry is not None
            and requeued_entry.market == "99.00"
            and not requeued_entry.cleared_by_human,
            "after reopen, Queue.upsert MAY re-queue the position — the refusal above "
            "guarded an answer, and there is no answer left to guard",
            f"entry={requeued_entry!r}",
        )
        checks.ok(
            requeued_entry is not None and requeued_entry.first_seen == "2026-08-01",
            "and even the re-queue keeps first_seen: upsert preserves it on an existing "
            "entry",
            f"first_seen: {requeued_entry and requeued_entry.first_seen!r}",
        )

        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 1, {"undo": True}),
            "not_answered",
            "a SECOND undo of one answer refuses as not_answered — the reopened entry IS "
            "the guard against a double reversal; nothing has to remember the first one "
            "happened",
        )

        # ------------------------------------------------------------ the listing hold
        capture_server.do_review_answer(
            3, 5, {"sku": holo["sku"], "condition": holo["condition"]}
        )
        with Store().write() as snapshot:
            snapshot.inventory.listing(holo["sku"], condition=holo["condition"]).set(
                master.STAGED, 2
            )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 5, {"undo": True}),
            "undo_too_late",
            "an undo of a card whose SKU has a non-zero listing stage refuses — undo "
            "stops at emit, or an import file and then TCGplayer would be left holding a "
            "listing the inventory no longer claims",
        )
        late = Store().read()
        late_entry = late.review.entries.get("3/5")
        checks.ok(
            late.inventory.get("3/5").sku == holo["sku"]
            and late_entry is not None
            and late_entry.cleared_by_human,
            "and the answer still STANDS afterwards — a refusal changes nothing, on the "
            "card or in the queue",
            f"sku={late.inventory.get('3/5').sku!r}",
        )

        # The same hold, met at ANSWER time instead of at the tap that would have failed.
        with Store().write() as snapshot:
            snapshot.inventory.listing(
                reverse["sku"], condition=reverse["condition"]
            ).set(master.PUSHED, 1)
        held_body = capture_server.do_review_answer(3, 6, good)
        checks.equal(
            held_body["restores_to"],
            None,
            "an answer whose SKU already has a listing hold reports restores_to NULL — "
            "the undo it would announce has already been decided against, and a control "
            "offered for a refused reversal has exactly one behaviour",
        )
        checks.equal(
            last_event("3/6").get("restores_to"),
            {"sku": None, "condition": None},
            "while the `answered` history line still records the pair — the two "
            "deliberately disagree: the log states what is true, the field answers "
            "whether to draw a button",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(3, 6, {"undo": True}),
            "undo_too_late",
            "and the null kept its promise: the undo is refused",
        )

        # ------------------------------------------------- when history cannot answer
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(3, 2, {"undo": True}),
            "an answer whose newest `answered` line has no restores_to refuses — a log "
            "written by a server that predates the field cannot say what to put back, "
            "and nothing here guesses",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "answer_origin_unknown",
                "in sold_origin_unknown's twin code",
            )
            checks.ok(
                "records no answer" in str(caught),
                "and the message says the LINE is what is missing, since the other cause "
                "of this code is a file to go and repair",
                f"message was: {caught}",
            )
        stale = Store().read()
        stale_entry = stale.review.entries.get("3/2")
        checks.ok(
            stale.inventory.get("3/2").sku == DUNSPARCE_REVERSE_SKU
            and stale_entry is not None
            and stale_entry.cleared_by_human,
            "and the refusal changed nothing: the answer stands and the entry stays "
            "cleared",
        )

        # A LOG THAT WILL NOT PARSE COSTS THE REVERSAL AND NOTHING ELSE — the answer
        # direction never reads history, only appends to it, which is the asymmetry
        # `_answer_origin`'s docstring claims and this pair of cases holds it to.
        with open(Store().history_path, "a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        blind = answers(
            checks,
            lambda: capture_server.do_review_answer(
                3,
                1,
                {
                    "sku": STALE_CANDIDATE["sku"],
                    "condition": STALE_CANDIDATE["condition"],
                },
            ),
            "the ANSWER direction still writes through a corrupt log",
        )
        if blind is not None:
            checks.equal(
                Store().read().inventory.get("3/1").sku,
                STALE_CANDIDATE["sku"],
                "and the sku reached the card",
            )
            checks.equal(
                blind["restores_to"],
                dict(prior),
                "and it still reports restores_to — the pair is read off the CARD inside "
                "the lock, never out of the log",
            )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_answer(3, 1, {"undo": True}),
            "the REVERSAL is what the corrupt line costs, and it refuses rather than "
            "guessing a pair back",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "answer_origin_unknown",
                "in the same code the missing line gets — one refusal, one condition: "
                "history cannot say",
            )
            checks.ok(
                "history.jsonl" in str(caught) and "could not be read" in str(caught),
                "but the message names the file to repair",
                f"message was: {caught}",
            )
        checks.equal(
            Store().read().inventory.get("3/1").sku,
            STALE_CANDIDATE["sku"],
            "and the failed reversal changed nothing",
        )


# ------------------------------------------------------------------------ the group answer


def check_group_answer(checks: Checks) -> None:
    """POST /review/group-answer — D29's one press over a homogeneous queue.

    THE ROUTE ENFORCES THE RULING'S NARROWNESS, AND THAT IS WHAT THIS SECTION HOLDS IT TO.
    Without `group_not_uniform` this is a general bulk write any client can reach with a
    loop — the exact thing D4 exists to prevent and D29 reopens only under two conditions:
    one shared reason code, and every entry offering exactly ONE candidate — its own —
    under one condition string. A shared SKU is deliberately NOT required and could not
    be: sixteen cards are sixteen catalog rows, and card A answered with card B's SKU is
    corruption wearing a reading.

    THE CASE THAT MATTERS IS `group_entry_refused` WRITING NOTHING. Validate everything,
    then write everything: a partial group reports a state neither queue file matches, and
    "eleven of sixteen landed" hands the operator a question — which eleven? — that
    nothing on his screen can answer. So one refused member must leave the PASSING members
    untouched: no sku on any card, no cleared flag, no `answered` history line.

    EVERY ENTRY HERE IS HAND-BUILT, the standing limit of all the queue sections, worth
    restating because this one leans hardest on it: Gate B's sixteen-identical-taps queue
    is the evidence D29 stands on, and no run has yet produced a queue this route answered.
    """
    checks.note("")
    checks.note("GROUP ANSWER — POST /review/group-answer")

    cond = CANDIDATES[0]["condition"]

    def own_row(sku: str) -> dict:
        # ONE candidate per entry — its own row, never a shared one. D29's reading is that
        # the SHAPE of each answer is identical, not its row, so every entry below offers
        # a different SKU under the one shared condition.
        return dict(CANDIDATES[0], sku=sku)

    def member(index: int, sku: str, condition: str = cond) -> dict:
        return {"box": 4, "index": index, "sku": sku, "condition": condition}

    with isolated_home():
        for _ in range(11):
            capture_server.do_capture(capture_payload(4))
        with Store().write() as snapshot:
            for i in range(1, 12):
                snapshot.inventory.set_state(f"4/{i}", master.IDENTIFIED)
            # The happy group: one shared reason, one row each, one condition.
            for i, sku in ((1, "9101"), (2, "9102"), (3, "9103")):
                snapshot.review.upsert(entry(4, i, candidates=[own_row(sku)]))
            # In BOTH files, with the parked entry DISAGREEING on reason and rows — if the
            # parked entry governed, this member would fail twice over (a sku it never
            # offered, a reason outside the group's). Review governing is what makes it
            # answerable at all, exactly as the single route rules it.
            snapshot.review.upsert(entry(4, 4, candidates=[own_row("9104")]))
            snapshot.parked.upsert(
                entry(4, 4, reason="low_confidence", candidates=[dict(STALE_CANDIDATE)])
            )
            snapshot.review.upsert(entry(4, 5, candidates=[own_row("9105")]))
            # 4/6 is captured, identified, and in NO queue — the entry failure.
            # The three uniformity violations, one condition each:
            snapshot.review.upsert(
                entry(4, 7, reason="low_confidence", candidates=[own_row("9107")])
            )
            snapshot.review.upsert(
                entry(4, 8, candidates=[own_row("9108"), dict(CANDIDATES[1], sku="9218")])
            )
            snapshot.review.upsert(
                entry(4, 9, candidates=[dict(STALE_CANDIDATE, sku="9109")])
            )
            # The listing-hold pair.
            snapshot.review.upsert(entry(4, 10, candidates=[own_row("9110")]))
            snapshot.review.upsert(entry(4, 11, candidates=[own_row("9111")]))

        # ------------------------------------------------------------- the body's shape
        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101")], "undo": True}
            ),
            "field_not_settable",
            "a top-level `undo` refuses as field_not_settable — this route has no reverse "
            "gear, by design: the write is all-or-nothing and the reversal is per card",
        )
        for empty, label in (
            ({}, "a body with no `answers` at all"),
            ({"answers": []}, "an empty answers list"),
            ({"answers": "4/1"}, "a non-list answers"),
        ):
            refusal(
                checks,
                lambda payload=empty: capture_server.do_review_group_answer(payload),
                "answers_required",
                f"{label} refuses as answers_required",
            )
        refusal(
            checks,
            lambda: capture_server.do_review_group_answer({"answers": ["4/1"]}),
            "answer_invalid",
            "an element that is not an object refuses as answer_invalid",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [dict(member(1, "9101"), undo=True)]}
            ),
            "an `undo` INSIDE an element is refused — a flag that could reverse one "
            "member mid-write would put both directions in one body",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "answer_invalid", "in answer_invalid"
            )
            checks.ok(
                "undo" in str(caught) and "per card" in str(caught),
                "and the message names the per-card route the undo lives on instead",
                f"message was: {caught}",
            )
        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [{"box": True, "index": 1, "sku": "9101", "condition": cond}]}
            ),
            "answer_invalid",
            "a boolean box is refused BY NAME — positions come from the body here rather "
            "than from a digits-only path regex, and True is an int to isinstance",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [{"box": 4, "index": 1, "condition": cond}]}
            ),
            "answer_invalid",
            "and an element with no sku refuses the same way",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(1, "9101")]}
            ),
            "a duplicate position is REFUSED, never deduplicated — the second write's "
            "restores_to would record the FIRST answer as what it replaced, and an undo "
            "would put back a sku the operator never meant the card to keep",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "duplicate_position", "in its own code"
            )
            checks.ok(
                "4/1" in str(caught),
                "and the message names the repeated position",
                f"message was: {caught}",
            )

        # ------------------------------------- one refused member refuses the group whole
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(2, "9102"), member(6, "9106")]}
            ),
            "one member that fails the single answer's own checks refuses the WHOLE group",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "group_entry_refused",
                "as group_entry_refused",
            )
            checks.ok(
                "4/6" in str(caught) and "not_in_queue" in str(caught),
                "and the failing position is named WITH ITS OWN CODE, so one 409 still "
                "reports per position",
                f"message was: {caught}",
            )
        untouched = Store().read()
        checks.equal(
            [untouched.inventory.get(k).sku for k in ("4/1", "4/2")],
            [None, None],
            "AND THE PASSING MEMBERS ARE UNTOUCHED — no sku reached either card",
        )
        checks.ok(
            not untouched.review.entries["4/1"].cleared_by_human
            and not untouched.review.entries["4/2"].cleared_by_human,
            "no entry was cleared",
        )
        checks.equal(
            [e for e in events_for("4/1") if e.get("event") == "answered"],
            [],
            "and no `answered` history line exists: validate everything, then write "
            "everything — a refused group leaves the store as if the call never arrived",
        )

        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(7, "9107"), member(6, "9106")]}
            ),
            "group_entry_refused",
            "entry failures are reported BEFORE uniformity: a group that is both non-"
            "uniform and stale refuses on the stale member — its remedy is a reload, and "
            "`not uniform` would send the operator to un-filter a queue that simply "
            "needs re-reading",
        )

        # -------------------------------------------------- the three uniformity refusals
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(7, "9107")]}
            ),
            "two reason codes in one group refuse — those cards are answered one at a "
            "time, each beside its own photograph, which is D4 unchanged",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "group_not_uniform", "as group_not_uniform"
            )
            checks.ok(
                "reasons" in str(caught)
                and "low_confidence" in str(caught)
                and "metadata_detection_disagreement" in str(caught),
                "naming both reasons, so the screen re-filters rather than guesses",
                f"message was: {caught}",
            )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(8, "9108")]}
            ),
            "an entry offering MORE than one row refuses — that card has a real choice, "
            "which is exactly the card the review screen exists for",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "group_not_uniform", "same code")
            checks.ok(
                "4/8" in str(caught) and "2 rows" in str(caught),
                "and the entry is named with its row count",
                f"message was: {caught}",
            )
        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {
                    "answers": [
                        member(1, "9101"),
                        member(9, "9109", STALE_CANDIDATE["condition"]),
                    ]
                }
            ),
            "group_not_uniform",
            "and two condition strings across the group refuse the same way",
        )
        checks.ok(
            Store().read().inventory.get("4/1").sku is None,
            "and not one of those refusals wrote anything onto the member that was valid "
            "in all of them",
        )

        # --------------------------------------------------------------- the happy path
        body = answers(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(2, "9102"), member(3, "9103")]}
            ),
            "a homogeneous group ANSWERS — one shared reason, one row per entry, one "
            "condition",
        )
        if body is not None:
            checks.equal(
                body["answered"],
                ["4/1", "4/2", "4/3"],
                "every position is written in the one call, in request order",
            )
            checks.equal(body["count"], 3, "and counted")
            checks.equal(
                [body["reason"], body["condition"]],
                ["metadata_detection_disagreement", cond],
                "the shared facts are stated once at the top — the route just proved "
                "they are shared",
            )
            checks.equal(
                [(r["position"], r["sku"]) for r in body["results"]],
                [("4/1", "9101"), ("4/2", "9102"), ("4/3", "9103")],
                "and each card is answered with ITS OWN lone candidate — never a shared "
                "sku, which is not a reading of D29 but corruption wearing one",
            )
            checks.ok(
                all(
                    r["review_cleared"] and not r["parked_cleared"]
                    for r in body["results"]
                ),
                "each result carries both cleared flags, per position",
            )
            checks.equal(
                [r["restores_to"] for r in body["results"]],
                [{"sku": None, "condition": None}] * 3,
                "and its own restores_to — the pair of nulls a never-identified card "
                "held, per member, under the single answer's contract",
            )
        after = Store().read()
        checks.equal(
            [after.inventory.get(k).sku for k in ("4/1", "4/2", "4/3")],
            ["9101", "9102", "9103"],
            "the skus reach the cards",
        )
        answered_lines = [last_event(k) for k in ("4/1", "4/2", "4/3")]
        checks.ok(
            all(line.get("event") == "answered" for line in answered_lines),
            "each position gets its own `answered` history line",
        )
        checks.equal(
            [line.get("group") for line in answered_lines],
            [3, 3, 3],
            "tagged `group: N`, so a reader of history.jsonl can tell one press from "
            "sixteen — the lines are identical in every other respect, which is exactly "
            "why the log has to say so",
        )
        checks.equal(
            [line.get("restores_to") for line in answered_lines],
            [{"sku": None, "condition": None}] * 3,
            "and each line carries its own restores_to, exactly as a single answer "
            "writes it — which is what makes the per-card undo below possible at all",
        )

        # -------------------------------------------- one member undone, per D29's shape
        undone = answers(
            checks,
            lambda: capture_server.do_review_answer(4, 2, {"undo": True}),
            "ONE group member reverses through the single route, as if it had been "
            "answered alone — the write is all-or-nothing, the reversal is per card",
        )
        if undone is not None:
            checks.ok(undone.get("undone") is True, "and says so")
        walked_back = Store().read()
        checks.ok(
            walked_back.inventory.get("4/2").sku is None
            and not walked_back.review.entries["4/2"].cleared_by_human,
            "the undone member is waiting again with no sku",
        )
        checks.equal(
            [walked_back.inventory.get(k).sku for k in ("4/1", "4/3")],
            ["9101", "9103"],
            "AND THE OTHERS STAY ANSWERED — one card's reversal is not the group's",
        )
        checks.ok(
            walked_back.review.entries["4/1"].cleared_by_human
            and walked_back.review.entries["4/3"].cleared_by_human,
            "their entries still cleared",
        )

        # -------------------------------------------------- both queues, review governs
        body = answers(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(4, "9104"), member(5, "9105")]}
            ),
            "a member sitting in BOTH queues is governed by its REVIEW entry: the parked "
            "entry here disagrees on reason and rows, and if it governed, this group "
            "would be refused twice over",
        )
        if body is not None:
            checks.ok(
                body["results"][0]["review_cleared"]
                and body["results"][0]["parked_cleared"],
                "and the member clears BOTH flags — one answer, or the screen goes on "
                "showing a card whose answer is already written",
            )
            checks.ok(
                body["results"][1]["review_cleared"]
                and not body["results"][1]["parked_cleared"],
                "while its review-only partner clears one",
            )
        both_read = Store().read()
        checks.ok(
            both_read.review.entries["4/4"].cleared_by_human
            and both_read.parked.entries["4/4"].cleared_by_human,
            "and both entries carry the flag in their files",
        )

        # ----------------------------------------------- the hold degrades a FIELD only
        with Store().write() as snapshot:
            snapshot.inventory.listing("9110", condition=cond).set(master.STAGED, 1)
        body = answers(
            checks,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(10, "9110"), member(11, "9111")]}
            ),
            "a listing hold on one member's sku does not refuse the group — the FIELD "
            "degrades, not the write",
        )
        if body is not None:
            checks.equal(
                [r["restores_to"] for r in body["results"]],
                [None, {"sku": None, "condition": None}],
                "the held member answers restores_to NULL while its partner keeps the "
                "pair — per position, because a group control that reverses eleven of "
                "sixteen on its best day is SaleResult's recorded defect at scale",
            )
        held_lines = [last_event("4/10"), last_event("4/11")]
        checks.equal(
            [line.get("restores_to") for line in held_lines],
            [{"sku": None, "condition": None}] * 2,
            "while BOTH history lines still record the pair — the log states what is "
            "true, the field answers whether to draw a button, and the two deliberately "
            "disagree",
        )
        checks.equal(
            [line.get("group") for line in held_lines],
            [2, 2],
            "both tagged with this group's own size",
        )
        checks.equal(
            Store().read().inventory.get("4/10").sku,
            "9110",
            "and the held member's write landed like any other",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(4, 10, {"undo": True}),
            "undo_too_late",
            "and the null kept its promise: that member's undo is refused",
        )


# ------------------------------------------------------------------------------ mark sold


def check_mark_sold(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/sold — D10's sale, and the server half of undo.

    TWO RULES, AND THEY PULL IN OPPOSITE DIRECTIONS. A sale must not remove anything — the
    record and the position both survive, permanently — while the undo `docs/DESIGN.md`
    requires on every mark-sold must put back the exact state the card came from.

    WHAT v2 CHANGED HERE. The states a card can be sold out of are `captured` and
    `identified` and nothing else: `pushed`, `staged` and `live` are quantities on the SKU's
    `Listing` (D7 amended), so a listed card still reads `identified` and the reversal has to
    read the CARD rather than the listing. That is asserted below against a SKU whose listing
    is fully live — the case that would have restored to `live` under the old model, and the
    reason this section was rewritten rather than re-pointed.
    """
    checks.note("")
    checks.note("MARK SOLD — POST /inventory/<box>/<index>/sold")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            snapshot.inventory.set_state(
                "3/1", master.IDENTIFIED, sku="8608859", condition="Near Mint Holofoil"
            )
            # The SKU is out on TCGplayer, and 3/1 is one of its copies. Under the
            # per-position model this card would have WORN `live`; here the quantity sits on
            # the listing and the card's own state is what the reversal must read.
            snapshot.inventory.listing("8608859", condition="Near Mint Holofoil").set(
                master.LIVE, 1
            )

        refusal(
            checks,
            lambda: capture_server.do_mark_sold(9, 9, {}),
            "card_not_found",
            "a sale against a position that holds no card refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_mark_sold(3, 1, {"state": "sold"}),
            "field_not_settable",
            "and a body naming a field this route does not set refuses before anything else",
        )
        refusal(
            checks,
            lambda: capture_server.do_mark_sold(3, 1, {"undo": "yes"}),
            "undo_invalid",
            "`undo` must be a JSON boolean: the string \"false\" is truthy in Python, and a "
            "flag whose two values are do-it and undo-it is the last place to guess",
        )

        # ----------------------------------------------------------------- the sale
        sold = capture_server.do_mark_sold(3, 1, {})
        checks.equal(sold["state"], master.SOLD, "a sale moves the card to `sold`")
        checks.ok(not sold["undone"], "and reports that it was a sale, not a reversal")
        checks.equal(
            sold["previous_state"], master.IDENTIFIED, "naming the state it came from"
        )
        checks.equal(
            sold["restores_to"],
            master.IDENTIFIED,
            "and what an undo would put back, so the control can be offered — or not — at "
            "the moment of the sale rather than at the tap that would have failed",
        )
        checks.equal(
            Store().read().inventory.listing_for("8608859").live,
            0,
            "AND THE SKU'S `live` COUNT FALLS BY ONE — the half of a sale that used to be "
            "free. A sold copy simply stopped wearing `live` before v2; the number is a "
            "quantity now, and nothing decrements it unless this route does",
        )
        checks.equal(
            (sold["listing"] or {}).get("live"),
            0,
            "and the response says so, because a Fulfiller pulling the third of four wants "
            "to see what is still live without a second request",
        )

        after = Store().read()
        checks.ok(
            after.inventory.get("3/1") is not None,
            "SOLD IS A STATE, NEVER A REMOVAL (D10): the record survives the sale",
        )
        checks.equal(
            after.inventory.next_index(3),
            4,
            "and the position is a PERMANENT GAP — the next capture steps past it, not "
            "into it, which is what makes a printed label true a year later",
        )
        checks.ok(
            capture_server.photo_path(3, 1).is_file(),
            "and the capture photo survives too: a sold card is what the pull preview "
            "shows (D6), and what makes a dispute answerable afterwards",
        )
        checks.equal(
            capture_server.do_status()["states"][master.SOLD], 1, "GET /status counts it sold"
        )

        refusal(
            checks,
            lambda: capture_server.do_mark_sold(3, 1, {}),
            "already_sold",
            "selling it twice refuses — one physical card, one sale",
        )

        # -------------------------------------------------------------- the reversal
        back = capture_server.do_mark_sold(3, 1, {"undo": True})
        checks.ok(back["undone"], "an undo reports itself as a reversal")
        checks.equal(back["state"], master.IDENTIFIED, "and puts the card back where it was")
        checks.equal(back["previous_state"], master.SOLD, "from sold")
        checks.equal(
            back["restores_to"], None, "with nothing left to reverse"
        )
        checks.equal(
            Store().read().inventory.get("3/1").state,
            master.IDENTIFIED,
            "and the store agrees",
        )
        checks.equal(
            Store().read().inventory.listing_for("8608859").live,
            1,
            "and the SKU's `live` count goes back up with it — the reversal is exact on "
            "both halves of what the sale moved",
        )
        checks.equal(
            [e.get("event") for e in events_for("3/1")],
            [master.CAPTURED, master.IDENTIFIED, master.SOLD, master.IDENTIFIED],
            "history reads `identified, sold, identified` — a reversal is two real "
            "transitions and needs no event of its own, which is why this route added none "
            "when the three writes beside it did (see `check_history`). Three lines shorter "
            "than it was: the listing stages are quantities on a SKU now, and a quantity "
            "moving is not a transition of this card",
        )

        refusal(
            checks,
            lambda: capture_server.do_mark_sold(3, 1, {"undo": True}),
            "not_sold",
            "and reversing a card that is not sold refuses in its own code",
        )

        # THE REASON THE PRIOR STATE IS READ AND NOT ASSUMED. This case used to sell a card
        # out of `pushed`, on the grounds that an order pull before any Export From Staged
        # touches cards at that stage. `pushed` is a quantity on the SKU now (D7 amended), so
        # the same point is made one state lower down: a card that never left `captured` must
        # come back to `captured`, and the route must not decide from the outside that
        # anything it sold had been listed.
        unlisted = capture_server.do_mark_sold(3, 2, {})
        checks.equal(
            unlisted["restores_to"],
            master.CAPTURED,
            "a card sold out of `captured` restores to CAPTURED — the reversal is exact "
            "rather than assuming the card was listed",
        )
        checks.equal(
            capture_server.do_mark_sold(3, 2, {"undo": True})["state"],
            master.CAPTURED,
            "and the reversal actually puts that state back",
        )
        checks.equal(
            unlisted["listing"],
            None,
            "and a card with no SKU moves no listing count — `Inventory.listing()` creates "
            "on read, so this route peeks instead: a sale of a never-emitted card would "
            "otherwise invent a listing of zeros, and its reversal would then bump `live` "
            "to 1 for a copy nothing ever pushed",
        )

        # ASSUMPTION, asserted so a later change to it is visible rather than silent.
        # Neither docs/DESIGN.md nor D10 says which states may be sold from, and the route
        # is permissive: refusing a card that was never pushed would leave a person holding
                # a card he has genuinely sold with no way to record it. Gate B was supposed to
        # settle it and did not — it passed 2026-08-22 with no order pulled and nothing
        # ever marked sold, so the assumption stands. The first real order pull settles it.
        never_listed = capture_server.do_mark_sold(3, 3, {})
        checks.equal(
            never_listed["restores_to"],
            master.CAPTURED,
            "a card that was never listed can still be marked sold, restoring to `captured` "
            "— ASSUMPTION, permissive by choice; see the route's comment",
        )
        capture_server.do_mark_sold(3, 3, {"undo": True})

        # A record whose history the store does not hold. Reachable for a store whose
        # history.jsonl was truncated or hand-edited, and the point is that it refuses.
        with Store().write() as snapshot:
            snapshot.inventory.cards["5/1"] = master.Card(
                box=5, index=1, state=master.SOLD
            )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_mark_sold(5, 1, {"undo": True}),
            "a sold card with no earlier state in history REFUSES rather than guessing",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "sold_origin_unknown",
                "and it refuses in its own code — defaulting to `live` is the obvious guess "
                "and is exactly what would make the reversal wrong",
            )
        checks.equal(
            Store().read().inventory.get("5/1").state,
            master.SOLD,
            "and the refusal changed nothing",
        )

        # A HISTORY THAT WILL NOT PARSE MUST NOT BLOCK THE SALE, and it did. `read_jsonl`
        # refuses the whole file over one bad line and this route reads it before either
        # branch, so a single corrupt line answered the Fulfiller's tap with
        # `store_unavailable` and left a card he had physically sold recorded as unsold.
        # Measured that way before `_sale_origin` existed. A sale is the one event here that
        # has already happened in the world: unlisted is fine, unrecorded is not (CLAUDE.md).
        with open(Store().history_path, "a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        degraded = answers(
            checks,
            lambda: capture_server.do_mark_sold(3, 3, {}),
            "one malformed line in history.jsonl does not stop the sale being recorded",
        )
        if degraded is not None:
            checks.equal(degraded["state"], master.SOLD, "the card is sold")
            checks.equal(
                degraded["restores_to"],
                None,
                "and it degrades to `origin unknown` instead — null is already the app's "
                "signal not to offer undo, so what is lost is the control, never the record",
            )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_mark_sold(3, 3, {"undo": True}),
            "the REVERSAL is what loses, and it refuses rather than guessing a state back",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "sold_origin_unknown",
                "in the same code a truncated history gets — one refusal, because there is "
                "one condition: history cannot say",
            )
            checks.ok(
                "history.jsonl" in str(caught) and "could not be read" in str(caught),
                "but the message says WHICH of the two it is, since one of them is a file "
                "to go and repair",
                f"message was: {caught}",
            )
        checks.equal(
            Store().read().inventory.get("3/3").state,
            master.SOLD,
            "and the card stays sold: the failed reversal changed nothing",
        )

    # Wiring, invisible from Python and fatal from a browser: a preflight that does not
    # advertise POST refuses both of 7b's writes before the server ever sees them.
    checks.ok(
        "POST" in capture_server.ALL_METHODS,
        "CORS advertises POST, which both 7b writes travel on",
        f"methods: {capture_server.ALL_METHODS}",
    )
    checks.ok(
        "POST" not in capture_server.SAFE_METHODS,
        "and not to an origin this server does not know — a page the owner never opened "
        "cannot preflight a sale",
        f"safe methods: {capture_server.SAFE_METHODS}",
    )
    checks.equal(
        capture_server.SOLD_FIELDS,
        ("undo",),
        "and mark-sold's whole body is the undo flag: the position is in the path and the "
        "state is a constant",
    )

    # ROUTING, and specifically that the sale does not shadow the two verbs already living
    # under /inventory/<box>/<index>. Asserted here rather than by standing a server up:
    # everything above calls the route functions directly, so a regex that matched the wrong
    # path would leave every one of those assertions green while the app got a 404 — or,
    # worse, while a PUT correction was read as a sale.
    checks.ok(
        capture_server._SOLD_RE.match("/inventory/3/17/sold") is not None
        and capture_server._SOLD_RE.match("/inventory/3/17") is None,
        "the sale matches /inventory/<box>/<index>/sold and nothing shorter",
    )
    checks.ok(
        capture_server._INVENTORY_ITEM_RE.match("/inventory/3/17/sold") is None,
        "and the PUT/DELETE path is anchored, so a sale can never be read as a correction "
        "or as an undo of the capture",
    )
    checks.ok(
        capture_server._REVIEW_ANSWER_RE.match("/review/3/17/answer") is not None
        and capture_server._REVIEW_ANSWER_RE.match("/review/3/17") is None,
        "and the answer matches /review/<box>/<index>/answer and nothing shorter",
    )


# ---------------------------------------------------------------------------------- history


def events_for(key: str) -> list:
    """Every `history.jsonl` line for one position, in the order they were appended."""
    return [event for event in Store().history() if event.get("position") == key]


def last_event(key: str) -> dict:
    """The newest line for one position, or an empty dict when there is none.

    NEVER INDEXES OFF THE END AND NEVER SUBSCRIPTS A KEY, and the reason is `answers`' reason
    one section up: a missing event IS the failure under test here, so a bare `[-1]` or
    `event["changed"]` turns one red line into a traceback that hides every check behind it.
    Measured — the first draft of this section did exactly that under four of the ten
    mutations it was checked against, reporting a KeyError instead of the assertion that was
    supposed to catch them.
    """
    events = events_for(key)
    return events[-1] if events else {}


# --------------------------------------------------------------------------------- retire


def check_retire(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/retire — D26's departure without a sale.

    `sold`'s SIBLING, AND THE SECTION MIRRORS `check_mark_sold` DELIBERATELY, refusal for
    refusal: a terminal state, a kept record, a permanent gap, one route in both directions.
    What is asserted beyond the mirror is exactly what makes it a second door rather than a
    copy of the first: the REASON, which travels onto the record, into the history line and
    back in the response, and must survive the reversal in the history line ALONE; the
    `already_sold` <-> `card_retired` pair, each naming the other's reversal route; and the
    deliberate asymmetry that a retirement moves no `live` count — `live` estimates
    TCGplayer, which never saw a retirement — while `copies_on_hand` shrinks, which is what
    keeps a departed copy out of D7's refill arithmetic.
    """
    checks.note("")
    checks.note("RETIRE — POST /inventory/<box>/<index>/retire")

    with isolated_home():
        for _ in range(4):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            snapshot.inventory.set_state(
                "3/1", master.IDENTIFIED, sku="8608859", condition="Near Mint Holofoil"
            )
            # The SKU is out on TCGplayer with one live copy — the shape that makes the
            # no-decrement assertion below able to fail in either direction.
            snapshot.inventory.listing("8608859", condition="Near Mint Holofoil").set(
                master.LIVE, 1
            )

        # ----------------------------------------------------------------- the refusals
        refusal(
            checks,
            lambda: capture_server.do_retire(9, 9, {"reason": "damaged"}),
            "card_not_found",
            "a retirement against a position that holds no card refuses — this route "
            "never creates one",
        )
        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {}),
            "retire_reason_invalid",
            "a retirement with no reason refuses: the reason is the one fact about the "
            "departure the record cannot re-derive later",
        )
        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {"reason": "ate_it"}),
            "retire_reason_invalid",
            "and one outside RETIRE_REASONS refuses in the same code — the vocabulary is "
            "closed so the history stays greppable; free text would be a second `note`",
        )
        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {"state": "retired"}),
            "field_not_settable",
            "a body naming a field this route does not set refuses before anything else",
        )
        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {"undo": True, "reason": "damaged"}),
            "field_not_settable",
            "and a body carrying BOTH `undo` and a reason refuses — a client that has "
            "confused the two directions, whose reason would otherwise be silently ignored",
        )
        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {"undo": "yes"}),
            "undo_invalid",
            "`undo` must be a JSON boolean, exactly as on the sale",
        )

        checks.equal(
            len(Store().read().inventory.copies_on_hand("8608859")),
            1,
            "before the retirement the copy is on hand — the baseline the shrink below "
            "is measured against",
        )

        # --------------------------------------------------------------- the retirement
        gone = capture_server.do_retire(3, 1, {"reason": "damaged"})
        checks.equal(gone["state"], master.RETIRED, "a retirement moves the card to `retired`")
        checks.ok(not gone["undone"], "and reports that it was a retirement, not a reversal")
        checks.equal(
            gone["previous_state"], master.IDENTIFIED, "naming the state it came from"
        )
        checks.equal(
            gone["restores_to"],
            master.IDENTIFIED,
            "and what an undo would put back, known at the moment of the write rather "
            "than at the tap that would have failed",
        )
        checks.equal(gone["reason"], "damaged", "the response carries the reason")

        after = Store().read()
        checks.equal(
            after.inventory.get("3/1").retire_reason,
            "damaged",
            "THE REASON LANDS ON THE RECORD — a `retired` state with no reason answers "
            "none of the questions the state exists for",
        )
        retired_line = last_event("3/1")
        checks.equal(
            retired_line.get("event"), master.RETIRED, "the history line is the state's own"
        )
        checks.equal(
            retired_line.get("reason"),
            "damaged",
            "AND THE REASON IS ON THE HISTORY LINE — the one-or-neither rule "
            "Inventory.retire exists to hold together, and the only record of WHY once "
            "the reversal below clears the field",
        )
        checks.equal(
            retired_line.get("sku"),
            "8608859",
            "with the SKU it left as, the way a sale's line carries it",
        )

        checks.equal(
            after.inventory.listing_for("8608859").live,
            1,
            "AND `live` DOES NOT MOVE — the deliberate asymmetry with the sale: `live` "
            "estimates TCGplayer's own quantity, and TCGplayer never saw a retirement. "
            "The listing is still up with one fewer copy behind it, and pulling it down "
            "is a TCGplayer action the next join observes (D8, D11)",
        )
        checks.equal(
            after.inventory.copies_on_hand("8608859"),
            [],
            "what shrinks is `copies_on_hand` — a retired copy has left the box, and "
            "counting it would put it back into D7's refill arithmetic",
        )

        checks.ok(
            after.inventory.get("3/1") is not None,
            "RETIRED IS A STATE, NEVER A REMOVAL (D26, same shape as D10's sale): the "
            "record survives",
        )
        checks.equal(
            after.inventory.next_index(3),
            5,
            "and the position is a permanent gap — the next capture steps past it",
        )
        checks.ok(
            capture_server.photo_path(3, 1).is_file(),
            "and the capture photo survives, which is what lets the retirement be "
            "questioned later",
        )
        checks.equal(
            capture_server.do_status()["states"][master.RETIRED],
            1,
            "GET /status counts it retired",
        )

        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_retire(3, 1, {"reason": "lost"}),
            "retiring it twice refuses — one physical card, one departure",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "already_retired",
                "in its own code",
            )
            checks.ok(
                "damaged" in str(caught),
                "and the refusal ECHOES THE STANDING REASON — the second operator learns "
                "why it already left instead of just that it did",
                f"message was: {caught}",
            )

        # -------------------------------------------- the pair, and the capture-undo
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_mark_sold(3, 1, {}),
            "SELLING A RETIRED CARD REFUSES — a sale recorded over a retirement would "
            "replace the record of a departure with a transaction that did not happen",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "card_retired", "in its own code")
            checks.ok(
                "/inventory/3/1/retire" in str(caught),
                "and it names the RETIRE route as the way back — a retired card that "
                "genuinely sells is two honest steps, reverse then sell",
                f"message was: {caught}",
            )

        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_card(3, 1),
            "capture-undo still refuses a retired card — UNDOABLE_STATES is an allowlist "
            "and `retired` is not on it, so a departure is never erased by deleting the "
            "record of it",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "undo_too_late",
                "in the same code a sold card gets — one code, two remedies",
            )
            checks.ok(
                "/inventory/3/1/retire" in str(caught),
                "and the message names the RETIRE route, not the sale's — 'reverse the "
                "sale' on a retired card sends the operator to a route that will refuse",
                f"message was: {caught}",
            )

        # ------------------------------------------------------------------ the reversal
        back = capture_server.do_retire(3, 1, {"undo": True})
        checks.ok(back["undone"], "an undo reports itself as a reversal")
        checks.equal(back["state"], master.IDENTIFIED, "and puts the card back where it was")
        checks.equal(back["previous_state"], master.RETIRED, "from retired")
        checks.equal(back["restores_to"], None, "with nothing left to reverse")
        checks.equal(back["reason"], None, "and no reason on the response any more")

        restored = Store().read()
        checks.equal(
            restored.inventory.get("3/1").state, master.IDENTIFIED, "the store agrees"
        )
        checks.equal(
            restored.inventory.get("3/1").retire_reason,
            None,
            "THE REVERSAL CLEARS `retire_reason` — a captured or identified card carrying "
            "one would read as a fifth state nothing defines",
        )
        history_reasons = [
            e.get("reason") for e in events_for("3/1") if e.get("event") == master.RETIRED
        ]
        checks.equal(
            history_reasons,
            ["damaged"],
            "WHILE THE HISTORY LINE KEEPS IT — that line is where a reversed "
            "retirement's reason survives, exactly as `unanswered` leaves the "
            "`answered` line standing",
        )
        checks.equal(
            [e.get("event") for e in events_for("3/1")],
            [master.CAPTURED, master.IDENTIFIED, master.RETIRED, master.IDENTIFIED],
            "history reads `identified, retired, identified` — a reversal is two real "
            "transitions and needs no event of its own, the same shape as the sale's",
        )
        checks.equal(
            restored.inventory.listing_for("8608859").live,
            1,
            "and `live` still has not moved in either direction — the asymmetry holds "
            "on the way back too",
        )
        checks.equal(
            len(restored.inventory.copies_on_hand("8608859")),
            1,
            "while the copy is back on hand",
        )

        refusal(
            checks,
            lambda: capture_server.do_retire(3, 1, {"undo": True}),
            "not_retired",
            "and reversing a card that is not retired refuses in its own code",
        )

        # The pair's other direction: a sold card left by the other door.
        capture_server.do_mark_sold(3, 2, {})
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_retire(3, 2, {"reason": "lost"}),
            "RETIRING A SOLD CARD REFUSES the mirror way — it would overwrite the record "
            "of a real sale",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "already_sold", "in its own code")
            checks.ok(
                "/inventory/3/2/sold" in str(caught),
                "naming the SALE's reversal route — the pair is what keeps each terminal "
                "state's history clean enough for the other's reversal to read",
                f"message was: {caught}",
            )

        # ------------------------------------------------- the reader guard, both ways
        # A card that was retired, un-retired, listed and sold. The `retired` line is in
        # its history, and the sale's reversal must restore the true prior state — never
        # `retired`: leaving `retired` logged the restored state on top, so the backwards
        # scan meets that first.
        capture_server.do_retire(3, 3, {"reason": "pulled"})
        capture_server.do_retire(3, 3, {"undo": True})
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.IDENTIFIED)
        sold = capture_server.do_mark_sold(3, 3, {})
        checks.equal(
            sold["restores_to"],
            master.IDENTIFIED,
            "a sale on a card whose history carries a `retired` line still restores to "
            "IDENTIFIED — the reversed retirement logged the restored state on top, so "
            "the scan never reaches the `retired` line",
        )
        checks.equal(
            capture_server.do_mark_sold(3, 3, {"undo": True})["state"],
            master.IDENTIFIED,
            "and the reversal actually puts that state back — never `retired`",
        )

        # A HAND-BUILT HISTORY WHERE THE SCAN MEETS `retired` DIRECTLY UNDER `sold`.
        # Unreachable through the routes — `card_retired` refuses the sale of a retired
        # card — so it means the file was edited by hand, and the scan must refuse rather
        # than choose either wrong answer: returning `retired` resurrects a departed card
        # under a live listing, and scanning past it silently erases the retirement.
        with Store().write() as snapshot:
            snapshot.inventory.cards["7/1"] = master.Card(
                box=7, index=1, state=master.SOLD
            )
        with open(Store().history_path, "a", encoding="utf-8") as handle:
            for event, extra in (
                (master.CAPTURED, {}),
                (master.RETIRED, {"reason": "lost"}),
                (master.SOLD, {}),
            ):
                handle.write(
                    json.dumps(
                        {"at": master.now(), "event": event, "position": "7/1", **extra}
                    )
                    + "\n"
                )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_mark_sold(7, 1, {"undo": True}),
            "a `retired` line directly under the `sold` line REFUSES the sale's reversal "
            "— neither resurrected nor skipped",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "sold_origin_unknown",
                "in the code that names a file to go and look at",
            )
        checks.equal(
            Store().read().inventory.get("7/1").state,
            master.SOLD,
            "and the refusal changed nothing",
        )

        # The mirror: a `sold` line directly under a `retired` one is the same hand-edit
        # seen from the other door, and restoring to it would fabricate a sale this store
        # never recorded.
        with Store().write() as snapshot:
            snapshot.inventory.cards["7/2"] = master.Card(
                box=7, index=2, state=master.RETIRED, retire_reason="lost"
            )
        with open(Store().history_path, "a", encoding="utf-8") as handle:
            for event in (master.CAPTURED, master.SOLD, master.RETIRED):
                handle.write(
                    json.dumps({"at": master.now(), "event": event, "position": "7/2"})
                    + "\n"
                )
        refusal(
            checks,
            lambda: capture_server.do_retire(7, 2, {"undo": True}),
            "retired_origin_unknown",
            "and a `sold` line directly under a `retired` one refuses the retirement's "
            "reversal the mirror way — restoring to it would fabricate a sale",
        )

        # ------------------------------------- origin unknown: null means no undo offered
        # A record the store holds with no history at all — a truncated or hand-edited
        # log. The retirement itself is never blocked (the card really has left the box;
        # unrecorded is worse than unreversible), but `restores_to` is null, and null is
        # the app's signal not to offer undo. The reversal attempted anyway refuses.
        with Store().write() as snapshot:
            snapshot.inventory.cards["8/1"] = master.Card(
                box=8, index=1, state=master.CAPTURED
            )
        orphan = capture_server.do_retire(8, 1, {"reason": "given_away"})
        checks.equal(
            orphan["restores_to"],
            None,
            "a retirement with no earlier state in history still records — degrading to "
            "`origin unknown`, so what is lost is the undo control, never the record",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_retire(8, 1, {"undo": True}),
            "and `restores_to: null` means exactly what it says: the reversal refuses "
            "rather than guessing a state back",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "retired_origin_unknown",
                "in its own code — `sold_origin_unknown`'s twin, for the twin operation",
            )
        checks.equal(
            Store().read().inventory.get("8/1").retire_reason,
            "given_away",
            "and the failed reversal left the reason standing — nothing was half-cleared",
        )

    # Wiring, mirrored from the sale's block for the mirror route.
    checks.equal(
        capture_server.RETIRE_FIELDS,
        ("reason", "undo"),
        "the retirement's whole body is the reason and the undo flag — the position is "
        "in the path and the state is a constant",
    )
    checks.equal(
        master.RETIRE_REASONS,
        ("pulled", "damaged", "lost", "given_away"),
        "the reasons are a closed vocabulary, named as an allowlist so a fifth is "
        "refused by default until it is argued for",
    )
    checks.equal(
        master.TERMINAL_STATES,
        (master.SOLD, master.RETIRED),
        "and the two doors out are exactly the two terminal states — `copies_on_hand` "
        "filters on this tuple, so a third door added without joining it would be "
        "counted as still in the box",
    )
    checks.ok(
        capture_server._RETIRE_RE.match("/inventory/3/17/retire") is not None
        and capture_server._RETIRE_RE.match("/inventory/3/17") is None,
        "the retirement matches /inventory/<box>/<index>/retire and nothing shorter",
    )
    checks.ok(
        capture_server._INVENTORY_ITEM_RE.match("/inventory/3/17/retire") is None,
        "and the PUT/DELETE path is anchored, so a retirement can never be read as a "
        "correction or as an undo of the capture",
    )


# -------------------------------------------------------------------------------- re-shoot


def check_reshoot(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/photo — D26's replace-in-place.

    NOT A DELETE, NOT A CAPTURE. The photo and sidecar are replaced at an existing
    position — record untouched, position label unchanged, allocator never involved — which
    is the remedy D10's undo cannot be: undo reaches only the newest capture, and a bad
    photograph is usually discovered later than that.

    THE THREE RULES ASSERTED HARDEST: the old bytes are GONE, because D26 says replaced
    rather than archived and an archived copy under the capture root is a paid Batch
    request for a card that does not exist twice; the sidecar is rebuilt from the RECORD,
    never from the request, so a drifted sidecar is repaired rather than trusted and a
    re-shoot cannot smuggle in a correction; and the `reshot` history line carries BOTH
    capture ids, because it is the only trace the first photograph ever existed.
    """
    checks.note("")
    checks.note("RE-SHOOT — POST /inventory/<box>/<index>/photo")

    reshoot_payload = {
        "image": base64.b64encode(JPEG_RESHOT).decode("ascii"),
        "capture_id": "t7-shot-three",
    }

    with isolated_home():
        capture_server.do_capture(
            capture_payload(3, set_hint="sv9", variant="holo", capture_id="t7-shot-one")
        )
        capture_server.do_capture(capture_payload(3, capture_id="t7-shot-two"))

        # ----------------------------------------------------------------- the refusals
        refusal(
            checks,
            lambda: capture_server.do_reshoot(9, 9, dict(reshoot_payload)),
            "card_not_found",
            "a re-shoot of a position that holds no card refuses — a new card is a "
            "capture, POST /capture",
        )
        refusal(
            checks,
            lambda: capture_server.do_reshoot(
                3, 1, dict(reshoot_payload, variant="normal")
            ),
            "field_not_settable",
            "a body smuggling a claim refuses — changing what the operator SAID is the "
            "PUT route's job, with its `corrected` history line",
        )
        refusal(
            checks,
            lambda: capture_server.do_reshoot(
                3, 1, {"image": base64.b64encode(JPEG_RESHOT).decode("ascii")}
            ),
            "capture_id_required",
            "a re-shoot with no capture_id refuses — one id per photograph, exactly as "
            "at capture, and it is what makes the replay below detectable",
        )
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_reshoot(
                3, 1, dict(reshoot_payload, capture_id="t7-shot-two")
            ),
            "an id another card already holds refuses — writing it would poison the "
            "replay lookup with a DuplicateCaptureId for every later capture",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "capture_id_in_use", "in its own code"
            )
            checks.ok(
                "3/2" in str(caught),
                "and the refusal names the card holding it",
                f"message was: {caught}",
            )

        # -------------------------------------------------------- the drift, then the fix
        # A sidecar that disagrees with the record — the drift this route must repair
        # rather than preserve. Written directly, because nothing in the product can
        # produce it: the seed is the hazard, not a path.
        photo = capture_server.photo_path(3, 1)
        drifted = capture_server.sidecar_path(photo)
        files.write_json(
            drifted, {"box": 3, "index": 1, "variant": "normal", "set_hint": "swsh1"}
        )
        # The seed stays a BARE STRING and the expectation moves to the one-member tuple.
        # It used to assert `"normal"` back, which was the same value in and out and could
        # not tell a reader that backfills from one that never heard of a set (D3 rung 1,
        # amended 2026-08-23). This says both things at once: the drift is real, AND a
        # hand-written sidecar in the old shape is still read — which is the whole reason
        # there is no migration.
        checks.equal(
            sidecar.scan(capture_server.captures_root())[0].metadata_finish,
            ("normal",),
            "the seeded drift is REAL — the reader believes the drifted sidecar, which "
            "is what makes the repair below a repair and not a restatement",
        )

        before = Store().read().inventory.get("3/1")
        captured_at = before.captured_at
        checks.equal(before.capture_id, "t7-shot-one", "and the record still names shot one")
        checks.equal(photo.read_bytes(), JPEG, "and the first photograph is on disk")

        body = capture_server.do_reshoot(3, 1, dict(reshoot_payload))

        checks.equal(
            photo.read_bytes(),
            JPEG_RESHOT,
            "THE BYTES ON DISK ARE THE NEW PHOTOGRAPH'S — same path, same position, "
            "allocator never involved",
        )
        jpgs = sorted(
            p.name for p in photo.parent.iterdir() if p.suffix == capture_server.PHOTO_SUFFIX
        )
        checks.equal(
            jpgs,
            sorted({photo.name, capture_server.photo_path(3, 2).name}),
            "and the OLD PHOTO IS GONE — replaced, not archived (D26): an archived copy "
            "under the capture root would be scanned as a third capture and billed as one",
        )
        checks.equal(
            len(sidecar.scan(capture_server.captures_root())),
            2,
            "scan() still finds exactly two captures, so the re-shoot costs one "
            "identification, not two",
        )

        repaired = sidecar.scan(capture_server.captures_root())[0]
        checks.equal(
            repaired.set_hint,
            "sv9",
            "THE SIDECAR IS REBUILT FROM THE RECORD: the drifted hint is repaired...",
        )
        checks.equal(
            repaired.metadata_finish,
            ("holo",),
            "...and the drifted finish with it — a sidecar the reader cannot trust to "
            "match the record would send D3 rung 1 a claim nobody made",
        )
        checks.equal(
            body.get("sidecar"),
            str(drifted),
            "and the response names the sidecar it rebuilt",
        )

        after = Store().read().inventory.get("3/1")
        checks.equal(
            after.capture_id,
            "t7-shot-three",
            "the record's capture_id is the NEW photograph's — it names the photograph "
            "stored at the position, and that is now this one",
        )
        checks.equal(body.get("capture_id"), "t7-shot-three", "and the response agrees")
        checks.equal(
            after.captured_at,
            captured_at,
            "while `captured_at` is UNTOUCHED — it describes the capture session, not "
            "the picture, and Gate C's cadence measurements read it",
        )
        checks.equal(after.state, master.CAPTURED, "and the state has not moved")

        reshot_line = last_event("3/1")
        checks.equal(
            reshot_line.get("event"),
            capture_server.RESHOT,
            "the history line is `reshot` — an event, never a state",
        )
        checks.equal(
            reshot_line.get("capture_id"),
            "t7-shot-three",
            "carrying the new photograph's id...",
        )
        checks.equal(
            reshot_line.get("replaced_capture_id"),
            "t7-shot-one",
            "...AND the id it replaced — this line is the only trace the first "
            "photograph ever existed, the boundary between two pictures the way "
            "`removed` is the boundary between two cards at one reused index",
        )
        checks.equal(
            [e.get("event") for e in events_for("3/1")],
            [master.CAPTURED, capture_server.RESHOT],
            "and the card's history reads `captured, reshot` — the record was untouched, "
            "so no state transition was logged",
        )

        # ------------------------------------------------------------------- the replay
        # The lost-response retry: the same request re-sent finds its own id already on
        # this card and rewrites the same bytes, burning nothing.
        replay = answers(
            checks,
            lambda: capture_server.do_reshoot(3, 1, dict(reshoot_payload)),
            "a replay of the same re-shoot, with its own id, ANSWERS rather than refusing",
        )
        if replay is not None:
            checks.equal(
                replay.get("capture_id"), "t7-shot-three", "with the same id on the record"
            )
        replayed = Store().read().inventory
        checks.equal(
            photo.read_bytes(), JPEG_RESHOT, "the same bytes are on disk"
        )
        checks.equal(
            len(replayed.cards),
            2,
            "no record was created",
        )
        checks.equal(
            replayed.next_index(3),
            3,
            "and no position was burned — the retry costs nothing, exactly as a "
            "capture replay costs nothing",
        )

        # ------------------------------------------------------- the two closed doors
        capture_server.do_mark_sold(3, 2, {})
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_reshoot(3, 2, dict(reshoot_payload, capture_id="t7-shot-four")),
            "a SOLD card refuses — its stored photo is the record of what was sold, and "
            "replacing it would swap the evidence a dispute is answered with",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "card_sold", "in its own code")
            checks.ok(
                "/inventory/3/2/sold" in str(caught),
                "naming the sale's reversal as the way back",
                f"message was: {caught}",
            )
        capture_server.do_mark_sold(3, 2, {"undo": True})
        capture_server.do_retire(3, 2, {"reason": "damaged"})
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_reshoot(3, 2, dict(reshoot_payload, capture_id="t7-shot-four")),
            "and a RETIRED card refuses — a photo of a card that left is a photo of "
            "nothing",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "card_retired", "in its own code")
            checks.ok(
                "/inventory/3/2/retire" in str(caught),
                "naming the retirement's reversal as its way back — two codes, because "
                "the remedies differ",
                f"message was: {caught}",
            )
        checks.equal(
            capture_server.photo_path(3, 2).read_bytes(),
            JPEG,
            "and neither refusal touched the photograph",
        )

    # Wiring, mirrored from the sale's block.
    checks.equal(
        capture_server.RESHOOT_FIELDS,
        ("image", "capture_id"),
        "the re-shoot's whole body is the photograph and its id — no claims, so a "
        "re-shoot cannot smuggle in a correction",
    )
    checks.ok(
        capture_server._RESHOOT_RE.match("/inventory/3/17/photo") is not None
        and capture_server._RESHOOT_RE.match("/inventory/3/17") is None,
        "the re-shoot matches /inventory/<box>/<index>/photo and nothing shorter",
    )
    checks.ok(
        capture_server._INVENTORY_ITEM_RE.match("/inventory/3/17/photo") is None,
        "and the PUT/DELETE path is anchored, so a re-shoot can never be read as a "
        "correction or an undo",
    )
    checks.ok(
        capture_server._RESHOOT_RE.match("/photo/3/17") is None
        and capture_server._PHOTO_RE.match("/inventory/3/17/photo") is None,
        "and it shares no path with D6's GET /photo — a browser prefetch can never "
        "become a write, nor a re-shoot a read",
    )


def check_history(checks: Checks) -> None:
    """The three routes that write without moving a card between states.

    THE ONLY APPEND-ONLY FILE IN THE STORE, which is what makes this worth a section. Every
    other file here is replaced whole on every write, so each of them answers "what does this
    card say now" and none of them can answer "what did it say in August". `docs/DEBTS.md`
    carried the omission for two months on the grounds that the store logs state transitions
    and a correction, a deletion and an answer are none of them — true about the store's
    vocabulary, and never an argument about the audit trail.

    WHAT IS ASSERTED IS THE PART THAT CANNOT BE RECOVERED. Each of these three routes
    overwrites or destroys the only copy of something: the correction rewrites the record and
    the sidecar in place, the undo deletes a record whose position is handed straight to the
    next capture, and the answer writes a SKU that a later run may overwrite. So the
    assertions below are about the PRIOR value, the BOUNDARY between two physical cards at
    one key, and WHICH OFFER a human chose from — not about the routes' happy paths, which
    have their own sections above.

    AND THE ONE WAY THESE LINES COULD BREAK SOMETHING. `_state_before_sale` reads this file
    backwards to find the state a sale should reverse to, so an event name that collided with
    `master.STATES` would restore a sold card to `corrected`. Both the disjointness and the
    reversal path are asserted at the end.
    """
    checks.note("")
    checks.note("HISTORY — the three writes that are not state transitions")

    def parses(stamp) -> bool:
        try:
            datetime.fromisoformat(str(stamp))
        except (TypeError, ValueError):
            return False
        return True

    with isolated_home():
        # ---------------------------------------------------------- the PUT correction
        capture_server.do_capture(capture_payload(3, set_hint="sv9", variant="holo"))
        capture_server.do_capture(capture_payload(3))

        capture_server.do_put_card(3, 1, {"variant": "reverse_holo"})
        corrections = events_for("3/1")
        checks.equal(
            [e.get("event") for e in corrections],
            [master.CAPTURED, capture_server.CORRECTED],
            "a PUT correction appends one event — the gap docs/DEBTS.md recorded from "
            "2026-06 to 2026-08-13",
        )

        corrected = last_event("3/1")
        # BOTH SIDES ARE LISTS because both were written by this route since D3's amendment
        # of 2026-08-23 — the capture above sent a bare `"holo"` and the route canonicalised
        # it to `["holo"]` on the way to the record, so `from` is what the record actually
        # held. `from` is the RAW stored value, not a canonical rendering of it: the block
        # below adds the legacy case, where a record predating the amendment still holds the
        # bare string and this line has to say so.
        checks.equal(
            corrected.get("changed"),
            {"metadata_finish": {"from": ["holo"], "to": ["reverse_holo"]}},
            "and it carries the value it REPLACED: the record and the sidecar are both "
            "overwritten in place, so this line is the only thing left that says the card "
            "was ever toggled holo (D3 rung 1 — the toggle is a claim, and the claim is "
            "what the ladder prices against)",
        )
        checks.ok(
            "metadata_finish" in (corrected.get("changed") or {}),
            "keyed by the RECORD's field name, not the wire's `variant` — a history line is "
            "read while holding inventory.json open",
            f"changed was: {corrected.get('changed')!r}",
        )

        # The shape, asserted against a line the STORE wrote rather than against a literal.
        # `_history` rebuilds `Inventory._log`'s record instead of calling it, and this is
        # what stops the two from drifting into two vocabularies for one file.
        captured_event = corrections[0] if corrections else {}
        checks.equal(
            sorted(set(corrected) & set(captured_event)),
            ["at", "event", "position"],
            "and it shares exactly the three keys store/master.py:_log writes — the server "
            "builds the record itself, so the shapes are held together here",
        )
        checks.ok(
            parses(corrected.get("at")),
            "with a timestamp in the same ISO form master.now() produces",
            f"at was: {corrected.get('at')!r}",
        )

        capture_server.do_put_card(3, 1, {"variant": "reverse_holo"})
        capture_server.do_put_card(3, 1, {})
        checks.equal(
            len(events_for("3/1")),
            2,
            "a PUT that restates the current claim logs NOTHING, and neither does one "
            "naming no settable field — the question this event answers is when the claim "
            "CHANGED, and a re-save has no answer to contribute",
        )

        # THE SAME PROMISE ACROSS D3's TWO SPELLINGS OF ONE CLAIM (amended 2026-08-23), and
        # the case above cannot make it: both its values were written by this route, so both
        # are lists and a raw `!=` would have passed. These are the two ways the amendment
        # can break it.
        #
        # 1. A LEGACY RECORD. All 682 records written before the amendment hold a bare
        #    string, there is no migration, and every client now sends a list — so the FIRST
        #    PUT that so much as mentions the finish would log a `corrected` event and
        #    rewrite a sidecar for a claim that did not move. Written straight onto the
        #    record because nothing in the product can produce it any more; the seed is the
        #    hazard, exactly as the drifted sidecar above is.
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/1"].metadata_finish = "reverse_holo"
        capture_server.do_put_card(3, 1, {"variant": ["reverse_holo"]})
        checks.equal(
            len(events_for("3/1")),
            2,
            "a list restating what a PRE-AMENDMENT record holds as a bare string logs "
            "nothing either — one member and one string are one claim (D3: a bare string "
            "reads as a one-member set), and the diff has to compare claims rather than "
            "representations or every legacy card logs a correction that corrected nothing",
        )

        # 2. TAP ORDER. `["reverse_holo", "normal"]` and `["normal", "reverse_holo"]` are
        #    one claim, and stay one value only because the route canonicalises to the
        #    GAME's enum order. Without that they diff as a change forever, in both
        #    directions, on every save.
        capture_server.do_put_card(3, 1, {"variant": ["normal", "reverse_holo"]})
        checks.equal(
            len(events_for("3/1")),
            3,
            "a genuinely different claim still logs — the guard above narrows the diff, it "
            "does not switch it off",
        )
        checks.equal(
            Store().read().inventory.cards["3/1"].metadata_finish,
            ["normal", "reverse_holo"],
            "...and lands in the game's enum order, not the order it was sent",
        )
        capture_server.do_put_card(3, 1, {"variant": ["reverse_holo", "normal"]})
        checks.equal(
            len(events_for("3/1")),
            3,
            "so the SAME claim sent in the other tap order logs nothing — the canonical "
            "form is what makes a no-op PUT a no-op, and it is the same form "
            "`variant._check_claim` and `sidecar._check_variant` produce",
        )

        capture_server.do_put_card(3, 1, {"set_hint": None})
        cleared = last_event("3/1")
        checks.equal(
            cleared.get("changed"),
            {"set_hint": {"from": "sv9", "to": None}},
            "clearing a hint back to no claim is a change and is logged as one",
        )

        capture_server.do_put_card(3, 2, {"set_hint": "sv9"})
        first_claim = last_event("3/2")
        checks.ok(
            "from" in first_claim.get("changed", {}).get("set_hint", {})
            and first_claim["changed"]["set_hint"]["from"] is None,
            "and a first claim on a card that had none keeps its `from: null` — the nesting "
            "is what protects it, since _history drops a None EXTRA and a dropped `from` "
            "would read as a field nobody touched",
            f"changed was: {first_claim.get('changed')!r}",
        )

        before = len(Store().history())
        refusal(
            checks,
            lambda: capture_server.do_put_card(3, 1, {"state": "sold"}),
            "field_not_settable",
            "a PUT naming an unsettable field still refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_card(9, 9, {"set_hint": "sv9"}),
            "card_not_found",
            "and one naming an absent position still refuses",
        )
        checks.equal(
            len(Store().history()),
            before,
            "and neither refusal appended a line: nothing changed, so nothing is recorded",
        )

        # THE SEAM ITSELF, asserted directly rather than left to follow from the routes.
        # `_history` appends to `Inventory.events` so that `Store.write()` flushes the line
        # with the change it describes — and the tempting simplification is to call
        # `files.append_jsonl` and be done. Measured: with that substitution every other check
        # in this section still passed, because the routes only log on paths that go on to
        # commit. What it costs is invisible until something raises between the log and the
        # commit, at which point history claims a correction the store never took.
        before = len(Store().history())
        try:
            with Store().write() as snapshot:
                capture_server._history(
                    snapshot.inventory,
                    capture_server.CORRECTED,
                    "3/1",
                    changed={"set_hint": {"from": "sv9", "to": "sv8"}},
                )
                raise RuntimeError("deliberate")
        except RuntimeError:
            pass
        checks.equal(
            len(Store().history()),
            before,
            "a logged event is DISCARDED when the write it rides in raises — the line and "
            "the change commit together or not at all, which is the whole reason this "
            "appends to the snapshot rather than to the file",
        )

        # ------------------------------------------------------------------- the undo
        capture_server.do_capture(capture_payload(4))
        capture_server.do_capture(capture_payload(4))
        capture_server.do_delete_card(4, 2)

        removed = last_event("4/2")
        checks.equal(
            removed.get("event"),
            capture_server.REMOVED,
            "undo appends a `removed` event — named for what happened to the record, not "
            "for the button that did it",
        )
        checks.equal(
            removed.get("state"),
            master.CAPTURED,
            "carrying the state it was in, which is what says whether an identification fee "
            "was spent on the photograph that was just deleted",
        )
        checks.ok(
            removed.get("cache_deleted") is False and "sku" not in removed,
            "with no paid answer discarded and no sku to record — a None extra is dropped, "
            "so an absent key reads as a fact nobody recorded rather than as a null",
            f"event was: {removed!r}",
        )

        capture_server.do_capture(capture_payload(4))
        checks.equal(
            [e.get("event") for e in events_for("4/2")],
            [master.CAPTURED, capture_server.REMOVED, master.CAPTURED],
            "THE ONE THIS EVENT EXISTS FOR: undo releases the index (D10), so the next "
            "capture takes the same key — and without the middle line the log reads as one "
            "position captured twice, with nothing to say a different physical card is in "
            "that slot now",
        )

        # Through the REMOVE route, because ruling 2 (2026-08-23) took `identified` off
        # the undo allowlist — the mid-box remove is the door that still deletes one, and
        # it appends the same `removed` line for the same reason. 4/2 is the top of its
        # box, so this is the empty-shift case and no `renumbered` line accompanies it.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("4/2", master.IDENTIFIED, sku="8608860")
            snapshot.cache.put("4/2", {"name": "Rhyhorn"}, "sha-of-photo", "prompt-1")
        capture_server.do_remove_card(4, 2, {"capture_id": None})
        paid = last_event("4/2")
        checks.equal(
            paid.get("state"),
            master.IDENTIFIED,
            "removing an IDENTIFIED card records that state, which is the one that cost "
            "money — the same `removed` line undo writes, from the route that may still "
            "delete one (D10 ruling 2)",
        )
        checks.ok(
            paid.get("cache_deleted") is True and paid.get("sku") == "8608860",
            "and records that the paid answer went with it, and what it had said",
            f"event was: {paid!r}",
        )
        checks.ok(
            not any(
                e.get("event") == capture_server.RENUMBERED for e in events_for("4/2")
            ),
            "and a remove at the top of a box appends NO `renumbered` line — an event "
            "describing zero renumbers would mark nothing",
        )

        # A third capture into box 4, so that 4/1 is not the newest — the two undos above
        # took 4/2 back off, and a refusal has to be set up rather than assumed.
        capture_server.do_capture(capture_payload(4))
        before = len(Store().history())
        refusal(
            checks,
            lambda: capture_server.do_delete_card(4, 1),
            "undo_not_newest",
            "a refused undo still refuses",
        )
        checks.equal(
            len(Store().history()),
            before,
            "and appends nothing — a refusal destroyed nothing to record",
        )

        # ---------------------------------------------------------- the review answer
        reverse = CANDIDATES[1]
        capture_server.do_capture(capture_payload(5))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("5/1", master.IDENTIFIED)
            snapshot.review.upsert(entry(5, 1, market="12.00"))

        before = len(Store().history())
        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                5, 1, {"sku": "9999999", "condition": reverse["condition"]}
            ),
            "sku_not_a_candidate",
            "an answer naming a row nothing offered still refuses",
        )
        checks.equal(
            len(Store().history()),
            before,
            "and writes no history: the card was not answered, so nothing claims it was",
        )

        capture_server.do_review_answer(
            5, 1, {"sku": reverse["sku"], "condition": reverse["condition"]}
        )
        answered = last_event("5/1")
        checks.equal(
            answered.get("event"),
            capture_server.ANSWERED,
            "an answer appends its own event",
        )
        checks.equal(
            answered.get("sku"),
            reverse["sku"],
            "carrying WHAT the human chose — the card record is the only other place it "
            "lands, and set_state and emit can both overwrite that while review.json goes "
            "on saying a human answered",
        )
        checks.equal(
            answered.get("condition"),
            reverse["condition"],
            "and the condition of the row he chose, taken from the candidate rather than "
            "from the request",
        )
        checks.equal(
            answered.get("queue"),
            queues.MAIN,
            "and WHICH queue's offer governed the choice — the file to check the answer "
            "against afterwards, and the thing the laundering refusal turns on",
        )
        checks.equal(
            answered.get("reason"),
            "metadata_detection_disagreement",
            "and the machine reason string, identical to the one on screen, in the run "
            "report and in review.json — docs/DESIGN.md keeps that one string greppable, "
            "and this is the fourth place it reads the same",
        )
        checks.equal(
            answered.get("restores_to"),
            {"sku": None, "condition": None},
            "and the pair the answer REPLACED — the blocker's regression (D28): this "
            "line used to log only what was written, so the log held everything needed "
            "to audit an answer and nothing needed to reverse one",
        )

        # ------------------------------------------------- the answer's reversal (D28)
        # Wrapped for `answers`' reason: the reversal refusing IS a failure mode of the
        # lines under test, and an escape here would hide the hazard walk at the end of
        # this section — the one case in this file that guards a live-bug shape.
        answers(
            checks,
            lambda: capture_server.do_review_answer(5, 1, {"undo": True}),
            "the answer can be taken back",
        )
        unanswered = last_event("5/1")
        checks.equal(
            unanswered.get("event"),
            capture_server.UNANSWERED,
            "an undo of the answer appends `unanswered` — without it the log says a SKU "
            "went onto this card and never says it came off",
        )
        checks.equal(
            unanswered.get("withdrew"),
            {"sku": reverse["sku"], "condition": reverse["condition"]},
            "carrying what came OFF the card...",
        )
        checks.equal(
            unanswered.get("restored"),
            {"sku": None, "condition": None},
            "...and what went back on — both pairs, because neither is derivable from "
            "the other once the card has moved on again",
        )
        checks.equal(
            unanswered.get("queues"),
            queues.MAIN,
            "and which files got their entries back",
        )
        before = len(Store().history())
        refusal(
            checks,
            lambda: capture_server.do_review_answer(5, 1, {"undo": True}),
            "not_answered",
            "a refused undo still refuses",
        )
        checks.equal(
            len(Store().history()),
            before,
            "and appends nothing — the line rides the route's own Store.write(), so a "
            "route that raises commits no history: nothing was withdrawn, and nothing "
            "claims it was",
        )

        # ----------------------------------------------- and none of them is a state
        checks.equal(
            sorted(set(capture_server.SERVER_EVENTS) & set(master.STATES)),
            [],
            "no server event shares a name with a listing state — _state_before_sale scans "
            "this file for the last event naming a state, so a collision would restore a "
            "reversed sale to `corrected`",
        )
        checks.ok(
            capture_server.UNANSWERED in capture_server.SERVER_EVENTS,
            "and `unanswered` is IN the tuple that check runs over — the disjointness "
            "above covers it only for as long as it is a member",
            f"SERVER_EVENTS: {capture_server.SERVER_EVENTS}",
        )
        checks.ok(
            capture_server.RESHOT in capture_server.SERVER_EVENTS,
            "and so is `reshot` — D26's fifth route-written event, an event and never a "
            "state: the card is the same card in the same state, only its picture changed",
            f"SERVER_EVENTS: {capture_server.SERVER_EVENTS}",
        )
        checks.ok(
            master.RETIRED in master.STATES
            and master.RETIRED not in capture_server.SERVER_EVENTS,
            "while `retired` sits on the OTHER side of the line and only there — it IS a "
            "state, logged by Inventory.retire through the store's own _log, and putting "
            "it in SERVER_EVENTS too would be the exact name collision D26 renamed the "
            "state (from `removed`) to avoid",
            f"STATES: {master.STATES}; SERVER_EVENTS: {capture_server.SERVER_EVENTS}",
        )

        # THE PATH THAT COLLISION WOULD BREAK, walked end to end rather than argued. A card
        # corrected after it went live has a `corrected` line sitting directly under its
        # `sold` line, which is exactly where the backwards scan starts looking.
        capture_server.do_capture(capture_payload(6))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("6/1", master.IDENTIFIED)
        capture_server.do_put_card(6, 1, {"set_hint": "sv9"})
        sold = capture_server.do_mark_sold(6, 1, {})
        checks.equal(
            sold["restores_to"],
            master.IDENTIFIED,
            "a card corrected between being identified and being sold still restores to "
            "IDENTIFIED — the scan skips every non-state event, which is what makes the new "
            "lines safe to add to a file another route reads",
        )
        checks.equal(
            capture_server.do_mark_sold(6, 1, {"undo": True})["state"],
            master.IDENTIFIED,
            "and the reversal actually puts that state back, past the correction",
        )

        # THE SAME HAZARD, ONE EVENT NEWER (D28). 5/1's history now reads captured,
        # identified, answered, unanswered — so the `unanswered` line sits directly under
        # the `sold` line this sale appends, which is exactly where the backwards scan
        # starts looking. A scan that did not skip it would either restore a reversed
        # sale to `unanswered` or refuse a reversal it owes.
        hazard = capture_server.do_mark_sold(5, 1, {})
        checks.equal(
            hazard["restores_to"],
            master.IDENTIFIED,
            "a card sold with an `unanswered` line under the sale still restores to "
            "IDENTIFIED — _state_before_sale skips it the way it skips `corrected` and "
            "`resectioned`, and never hands it to set_state as a state",
        )
        checks.equal(
            capture_server.do_mark_sold(5, 1, {"undo": True})["state"],
            master.IDENTIFIED,
            "and the reversal actually puts that state back, past the withdrawn answer",
        )


# ------------------------------------------------------------------------- the sidecar seam


def check_sidecar_seam(checks: Checks) -> None:
    """What the server writes, read back through the reader `identify` actually uses.

    THE ONE THAT CAN FAIL SILENTLY AND COSTS MONEY WHEN IT DOES. `cli/cmd_identify.py`
    builds its card from `identify.sidecar`, never from `inventory.json`. A capture or a
    correction that does not reach the sidecar is invisible here and shows up as a variant
    ladder that takes D3 rung 2 or 3 as though no toggle was ever set.
    """
    checks.note("")
    checks.note("SIDECAR SEAM — server writes, identify.sidecar reads")

    with isolated_home():
        capture_server.do_capture(capture_payload(3, set_hint="sv9", variant="reverse_holo"))
        capture_server.do_capture(capture_payload(3))
        capture_server.do_capture(capture_payload(4, variant="holo"))

        captures = sidecar.scan(capture_server.captures_root())
        checks.equal(len(captures), 3, "every stored capture is found by scan()")
        checks.ok(
            all(c.has_position for c in captures),
            "every capture is positioned from its sidecar",
        )
        checks.ok(
            all(c.source == sidecar.FROM_SIDECAR for c in captures),
            "and reports its position came from the sidecar, not the filename",
        )
        checks.ok(
            all(c.problem is None for c in captures),
            "with no problem recorded on any of them",
        )

        keys = [c.key for c in captures]
        checks.equal(
            keys,
            ["3/1", "3/2", "4/1"],
            "scan order is position order, and keys equal store.master.position_key",
        )

        first = captures[0]
        checks.equal(first.set_hint, "sv9", "the set hint reaches the sidecar")
        # A ONE-MEMBER TUPLE, not the bare string this asserted before D3's amendment of
        # 2026-08-23. The capture that produced it still sends a bare `variant="holo"` on
        # the wire (see `capture_payload` above), so this asserts the whole hop the way the
        # product actually walks it: string in from a client that has always sent one, set
        # out to the ladder. That is strictly more than the old assertion, which could not
        # tell the two shapes apart because they were the same shape.
        checks.equal(
            first.metadata_finish,
            ("reverse_holo",),
            "and so does the capture-time variant",
        )
        checks.ok(
            captures[1].metadata_finish is None,
            "a card captured with no toggle records no claim — absent, not null (D3 rung 1)",
        )

        # THE REGRESSION. A correction that stops at inventory.json never reaches the
        # variant ladder. This was broken while passing its own route test.
        capture_server.do_put_card(3, 2, {"variant": "holo"})
        corrected = sidecar.scan(capture_server.captures_root())[1]
        checks.equal(
            corrected.metadata_finish,
            ("holo",),
            "a PUT correction reaches the SIDECAR, which is what identify reads",
        )

        capture_server.do_put_card(3, 1, {"set_hint": "sv3pt5"})
        after = sidecar.scan(capture_server.captures_root())[0]
        checks.equal(after.set_hint, "sv3pt5", "a hint-only PUT updates the hint")
        checks.equal(
            after.metadata_finish,
            ("reverse_holo",),
            "and leaves an already-recorded finish alone",
        )

        # The money rule, both directions. `scan()` counts photos, and every photo it finds
        # is a paid Batch request. The capture root is captures/cards/ and not captures/ so
        # that screenshot renders under captures/ui/ are never scanned as paid captures.
        stray = capture_server.captures_root() / "box3" / "stray.png"
        stray.write_bytes(b"\x89PNG\r\n\x1a\n")
        checks.equal(
            len(sidecar.scan(capture_server.captures_root())),
            4,
            "a stray .png under the capture root WOULD be scanned — 4 paid requests, not 3",
        )
        stray.unlink()

        render = files.home() / "captures" / "ui" / "pull-confirm.png"
        render.parent.mkdir(parents=True, exist_ok=True)
        render.write_bytes(b"\x89PNG\r\n\x1a\n")
        checks.equal(
            len(sidecar.scan(capture_server.captures_root())),
            3,
            "but a render under captures/ui/ is outside the root and costs nothing",
        )

        # ------------------------------------- a SET-VALUED claim, wire to record to reader
        # D3 rung 1, amended 2026-08-23. This is the hop the amendment exists for and the
        # one nothing could exercise before it: a stack that genuinely holds two finishes
        # had no honest claim available, because the wire took one string and the reader
        # reduced a list to its first member.
        capture_server.do_capture(
            capture_payload(3, variant=["reverse_holo", "normal", "normal"])
        )
        capture_server.do_capture(capture_payload(3, variant=[]))

        record = Store().read().inventory.cards["3/3"]
        checks.equal(
            record.metadata_finish,
            ["normal", "reverse_holo"],
            "a two-member claim reaches the RECORD as a list — deduped, and in the GAME's "
            "own enum order rather than the order it was sent, so one claim is one value "
            "however it was tapped (the same canonical form `variant._check_claim` and "
            "`sidecar._check_variant` produce, which is what makes re-normalising harmless)",
        )
        checks.ok(
            Store().read().inventory.cards["3/4"].metadata_finish is None,
            "and an EMPTY claim is no claim: None on the record, never `[]`. D3 makes the "
            "empty set identical to the null this field has always allowed, and `[]` "
            "reaching `record_capture` would overwrite a real claim on the next re-record",
        )

        raw = json.loads(
            capture_server.sidecar_path(
                capture_server.photo_path(3, 3)
            ).read_text("utf-8")
        )
        checks.equal(
            raw.get("variant"),
            ["normal", "reverse_holo"],
            "and the SIDECAR carries the same list — this is the file identify reads, so a "
            "set that stopped at inventory.json would reach the ladder as no claim at all",
        )
        empty_raw = json.loads(
            capture_server.sidecar_path(
                capture_server.photo_path(3, 4)
            ).read_text("utf-8")
        )
        checks.ok(
            "variant" not in empty_raw,
            "while an empty claim writes NO KEY — absent, not null and not `[]`; the file "
            "stays a record of claims actually made (D3 rung 1)",
            f"sidecar was: {empty_raw}",
        )

        both = {c.key: c for c in sidecar.scan(capture_server.captures_root())}
        checks.equal(
            both["3/3"].metadata_finish,
            ("normal", "reverse_holo"),
            "and the reader hands the ladder BOTH members — the assertion that would have "
            "caught the interim reduction (`kept[0]`), which nothing looked at and which "
            "would have collapsed every two-member claim in silence, resolving rather than "
            "reviewing",
        )
        checks.ok(
            both["3/4"].metadata_finish is None,
            "...and no claim stays None across the whole hop, so rungs 2 and 3 stay live",
        )

        # The money rule, both directions. `scan()` counts photos, and every photo it finds
        # is a paid Batch request. The capture root is captures/cards/ and not captures/ so
        # that screenshot renders under captures/ui/ are never scanned as paid captures.
        stray = capture_server.captures_root() / "box3" / "stray.png"
        stray.write_bytes(b"\x89PNG\r\n\x1a\n")


# ------------------------------------------------------------------ the capture-claim chain


def check_capture_claim_chain(checks: Checks) -> None:
    """`store/master.py:CAPTURE_CLAIM_FIELDS` — the tuple, and the two silences it closed.

    `docs/DEBTS.md` names ten hops between the control on the capture screen and the
    consumer that finally reads a claim, and says TWO OF THEM FAIL SILENTLY. Both are here,
    because both are the same shape: the value is written, the response is correct, the file
    on disk carries it, and something later hands back a card that never had it.

      `Inventory.parse` filters on `Card.__annotations__`. A claim the dataclass does not
      declare is dropped on reload. The filter is right — it is why `capture_id` could not
      live in the sidecar alone — and the silence is the debt.

      `record_capture` upserts the claim list onto an incumbent. It used to be a literal
      three-name tuple, so a fourth claim would survive a first capture and be discarded by
      every RE-RECORD, which is the harder failure to see: it works until the operator
      corrects a card.

    ASSERTED OVER THE TUPLE RATHER THAN OVER TODAY'S FOUR NAMES, which is the only version
    of this test worth having. Naming `game` and `note` here would pass on the day a fifth
    claim is added and dropped — the exact failure the tuple exists to stop. Every case below
    iterates the tuple, so it grows with it.
    """
    checks.note("")
    checks.note("CAPTURE CLAIM CHAIN — store/master.py:CAPTURE_CLAIM_FIELDS")

    undeclared = [
        name
        for name in master.CAPTURE_CLAIM_FIELDS
        if name not in master.Card.__annotations__
    ]
    checks.equal(
        undeclared,
        [],
        "every capture claim is declared on `Card` — an undeclared one is written, "
        "answered, stored, and dropped by the next reload with nothing said",
    )

    unbound = [
        name
        for name in master.CAPTURE_CLAIM_FIELDS
        if name not in capture_server.CLAIM_WIRE_NAMES
        and name not in capture_server.DERIVED_CLAIMS
    ]
    checks.equal(
        unbound,
        [],
        "and every one has a wire name or is declared derived — a claim with neither "
        "reaches inventory.json and never the sidecar, which is what identify reads",
    )

    # The behavioural half of the annotation filter. A tuple that agrees with the dataclass
    # proves the two lists match; only a round trip proves the claim is still there.
    marks = {name: f"mark-{name}" for name in master.CAPTURE_CLAIM_FIELDS}
    inventory = master.Inventory()
    inventory.record_capture(master.Card(box=7, index=1, **marks))
    reloaded = master.Inventory.parse(inventory.to_payload())
    checks.equal(
        {name: getattr(reloaded.cards["7/1"], name) for name in marks},
        marks,
        "and every claim survives the JSON round trip `Inventory.parse` filters — the "
        "first of the two silent hops, asserted as a value rather than as a name",
    )

    # THE RE-RECORD, which is the hop that worked until the operator corrected a card. A
    # second `record_capture` at the same position takes the existing-record branch and
    # copies the claims over the incumbent; a list of three would leave the fourth behind.
    inventory.record_capture(
        master.Card(box=7, index=1, **{name: f"re-{name}" for name in marks})
    )
    checks.equal(
        {name: getattr(inventory.cards["7/1"], name) for name in marks},
        {name: f"re-{name}" for name in marks},
        "and a RE-RECORD carries every claim onto the incumbent, not the three the loop "
        "used to name by hand",
    )

    # AN EMPTY CLAIM CARRIES NO FURTHER THAN A MISSING ONE — and this is the only thing in
    # `store/master.py` that this change can actually assert. The annotation on
    # `Card.metadata_finish` is documentation and nothing else: `Inventory.parse` filters on
    # the KEY NAME (`Card.__annotations__`), dataclasses do no runtime type checking, and
    # `scripts/docs-audit.py` does not read this file — so widening it to a set is a silent
    # no-op that LOOKS like the feature landed. The `if value:` guard in `record_capture` is
    # the behavioural half, and it is a NEW hazard rather than an old bug.
    #
    # D3 says an empty set is "identical to the null this field has always allowed". Under
    # the old test — `if value is not None` — `[]` is not None, so an incoming empty claim
    # OVERWROTE a real one, and unrecoverably: a later re-record carrying None does not
    # carry, so nothing puts it back. It could not happen while the finish was a string
    # (`_variant_shape` mapped `""` to None before the store saw it); it can now.
    # `rarity_claim` has carried the identical hole since it shipped, saved only by the
    # server normalising `cleaned or None` on the way in — the store depending on a
    # normalisation it does not enforce. One guard closes it for every claim in the tuple.
    #
    # Driven by the tuple and by both falsy spellings, never by a list of which claims are
    # set-valued today: naming them is exactly the failure this test's docstring argues
    # against, and the guard is truthiness, which has no per-field cases.
    for empty in ([], ""):
        inventory.record_capture(
            master.Card(box=7, index=1, **{name: empty for name in marks})
        )
        checks.equal(
            {name: getattr(inventory.cards["7/1"], name) for name in marks},
            {name: f"re-{name}" for name in marks},
            f"and an EMPTY claim ({empty!r}) leaves the incumbent alone, exactly as None "
            "does — D3 makes an empty set no claim at all, so a re-record carrying one may "
            "not erase a claim that was really made",
        )

    # A misspelled claim refuses BY NAME and burns no index, which is what the tuple buys
    # over four named keyword arguments — `TypeError` from a `Card` constructor two frames
    # down would name neither the claim nor the position it cost.
    with isolated_home():
        with Store().write() as snapshot:
            checks.raises(
                master.UnknownClaim,
                lambda: snapshot.inventory.allocate_capture(7, set_hnit="sv9"),
                "an unrecognised claim refuses as UnknownClaim rather than raising from a "
                "constructor two frames down",
            )
            checks.equal(
                snapshot.inventory.next_index(7),
                1,
                "and the refusal burned no index — it is checked before one is allocated",
            )


# ----------------------------------------------------------------- game and note claims


def check_game_and_note_seam(checks: Checks) -> None:
    """D21's `game` and D23's `note`, from the request body to `identify.sidecar`.

    THE SAME SEAM `check_sidecar_seam` GUARDS, FOR THE TWO CLAIMS THAT ARRIVE DIFFERENTLY.
    `game` is set at capture and decides which export a card is ever joined against, so a
    game that reaches `inventory.json` and not the sidecar is a Riftbound card identified by
    the Pokemon prompt and priced off the Pokemon export. `note` is deliberately NOT a
    capture field — the feeder emits a card every ~660 ms and free text before the shutter
    would put a keyboard on the critical path — so it arrives only as a correction, and the
    thing worth asserting about it is that a correction rewrites the sidecar WHOLE.

    ABSENT IS NOT NULL, AND THAT IS D21's DISTINCTION RATHER THAN A FILE-FORMAT PREFERENCE.
    A sidecar with no `game` key is one written before the field existed, and
    `Capture.game_or_default` backfills it to Pokemon at the READ. A sidecar carrying
    `"game": null` would be a write-side default wearing a claim's clothes: "the operator
    said Pokemon" and "nobody was asked" become the same bytes on disk. Asserted on the raw
    JSON, because the reader treats the two identically and cannot tell them apart.
    """
    checks.note("")
    checks.note("GAME AND NOTE — server/capture_server.py, identify/sidecar.py")

    def raw_sidecar(box: int, index: int) -> dict:
        return json.loads(
            capture_server.sidecar_path(capture_server.photo_path(box, index)).read_text(
                "utf-8"
            )
        )

    with isolated_home():
        capture_server.do_capture(capture_payload(6, game="riftbound", set_hint="ogn"))
        capture_server.do_capture(capture_payload(6))

        checks.equal(
            raw_sidecar(6, 1).get("game"),
            "riftbound",
            "a captured game reaches the sidecar under its own key",
        )
        checks.ok(
            "game" not in raw_sidecar(6, 2),
            "and a capture sending NO game writes NO KEY AT ALL — absent, never null, so a "
            "backfilled Pokemon can never be mistaken for a claimed one (D21)",
        )
        checks.ok(
            "note" not in raw_sidecar(6, 1),
            "a note is not a capture field: nothing about a capture waits for a keyboard",
        )

        claimed, unclaimed = sidecar.scan(capture_server.captures_root())[:2]
        checks.equal(claimed.game, "riftbound", "the reader identify uses reads it back")
        checks.ok(
            unclaimed.game is None,
            "and reads the raw claim as None when the file names none",
        )
        checks.equal(
            unclaimed.game_or_default,
            games.DEFAULT_GAME,
            "with the substitution happening at the READ, where it is visible — D21's "
            "read-side backfill, never a default written into the file",
        )
        checks.ok(
            all(capture.problem is None for capture in (claimed, unclaimed)),
            "and neither is a problem: a missing game is a file older than the field",
        )

        # THE CORRECTION ROUTE IS THE ONLY WAY A NOTE ARRIVES, and it rewrites the sidecar
        # from the RECORD rather than from the request body — so a PUT naming one claim must
        # leave the others standing. That is the failure `docs/DEBTS.md` calls the harder one
        # to see: it works until the operator corrects a card.
        capture_server.do_put_card(6, 1, {"note": "  bent corner, top left  "})
        checks.equal(
            raw_sidecar(6, 1).get("note"),
            "bent corner, top left",
            "a note reaches the sidecar by PUT, trimmed",
        )
        checks.equal(
            raw_sidecar(6, 1).get("game"),
            "riftbound",
            "and the re-record leaves the game standing — the sidecar is composed from the "
            "record, not from the body that touched one field",
        )

        capture_server.do_put_card(6, 1, {"game": "one_piece"})
        after = raw_sidecar(6, 1)
        checks.equal(
            [after.get("game"), after.get("note"), after.get("set_hint")],
            ["one_piece", "bent corner, top left", "ogn"],
            "and a game correction preserves both of the others: every claim is rewritten "
            "from the record, so nothing the body did not mention is dropped",
        )
        checks.equal(
            sidecar.scan(capture_server.captures_root())[0].note,
            "bent corner, top left",
            "with the note readable by identify — a note is what a misc card is described "
            "by, and nothing else in the pipeline will ever name it",
        )

        # --- the two refusals, which mean different things and have different remedies ---
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(6, game="pokemonn")),
            "game_invalid",
            "a game outside the registry refuses as game_invalid — a typo, or a client "
            "written against a registry this server does not have",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(6, game="magic")),
            "game_invalid",
            "and so does a real trading card game nobody has registered here",
        )

        # `game_unverified` HAS NO ENTRY TO FIRE ON. Every registered game has an export as
        # of 2026-08-23 — `riftbound` and `one_piece` carried the flag until theirs arrived
        # — and the branch stays because the flag is what an entry is BORN with. Flipped
        # here and restored in a `finally`, the same way T4 widens `variant.FINISHES`: a
        # branch nothing can reach is a branch nothing is testing.
        entry = games.get("riftbound")
        try:
            entry["unverified"] = True
            refusal(
                checks,
                lambda: capture_server.do_capture(capture_payload(6, game="riftbound")),
                "game_unverified",
                "a REGISTERED game with no export yet refuses as game_unverified, in its "
                "own code — capturing into one writes records no join could ever resolve",
            )
        finally:
            entry["unverified"] = False
        checks.ok(
            not games.get("riftbound")["unverified"],
            "and the registry is left exactly as it was found",
        )

        # `catalogued` IS DELIBERATELY NOT THE TEST, and getting it backwards would break
        # the commoner case: `misc` is uncatalogued forever by the owner's ruling and is a
        # perfectly good thing to photograph. A route refusing on `games.require` would make
        # every misc capture fail, and the one settled, correct state in the registry would
        # read as an error on screen for good.
        status, body = capture_server.do_capture(capture_payload(6, game="misc"))
        checks.equal(status, HTTPStatus.CREATED, "a `misc` capture is ACCEPTED")
        checks.ok(
            not games.is_catalogued("misc"),
            "even though it is permanently uncatalogued — captured, located and noted is "
            "the whole of what it asks for",
        )
        checks.equal(raw_sidecar(6, body["index"]).get("game"), "misc", "and it is recorded")

    # --- GET /games: the app's only source for the vocabulary ---------------------------
    # No `isolated_home` — this route reads no store at all, which is itself the property
    # being asserted: the picker can be drawn before a single card exists.
    served = capture_server.do_games()
    checks.equal(
        [entry["key"] for entry in served["games"]],
        list(games.keys()),
        "GET /games serves every registry entry, in registry order — which is the order a "
        "picker renders, and the app's ONLY copy of the vocabulary",
    )
    checks.equal(
        served["default"],
        games.DEFAULT_GAME,
        "with a `default` published rather than guessed at: the alternative is the app "
        "hardcoding `pokemon` and silently disagreeing the day the registry is reordered",
    )
    checks.ok(
        all(
            set(served_entry) == set(authored)
            for served_entry, authored in zip(served["games"], games.GAMES)
        ),
        "served as AUTHORED and not projected — every field goes out, including the ones "
        "no screen reads today, so a new screen needs no route change to get one",
    )
    served["games"][0]["display"] = "mutated"
    checks.ok(
        games.GAMES[0]["display"] != "mutated",
        "and the response is a copy: a caller editing what it was handed cannot reach the "
        "registry every other consumer in this process reads",
    )


# ---------------------------------------------------------------- box routes and search


def check_box_routes_and_search(checks: Checks) -> None:
    """D20's four routes — the three that own a box, and the read that finds a card.

    `check_boxes_and_listings` ABOVE ASSERTS THE STORE; THIS ASSERTS THE ROUTES. They are
    different questions and the difference is T7's whole subject: `close_box` freezing
    capacity is a rule, and `PUT /boxes/<box>` refusing to be handed one is wiring. A rule
    that is right behind a route nobody can reach correctly is still a box counted against
    the wrong denominator on the only screen that could repair it.

    THE UNREGISTERED BOX IS THE CASE TO KEEP. Until D20 a box existed only because a card
    named one, so every box captured before the registry has no entry — and a read that
    listed the registry alone would hide exactly those, on the screen built to fix them.
    """
    checks.note("")
    checks.note("BOX ROUTES AND SEARCH — server/capture_server.py")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(8))
        # A box that holds cards and has NO registry entry. `allocate_capture` calls
        # `ensure_box`, so this shape cannot be reached through the front door any more —
        # which is precisely why it is built by hand: every box filled before D20 is in it,
        # and there is no other way left to produce one.
        with Store().write() as snapshot:
            del snapshot.inventory.boxes["8"]

        listed = {row["box"]: row for row in capture_server.do_boxes()["boxes"]}
        # Guarded, for the reason `Checks` collects failures instead of stopping at the
        # first: a missing row here would take the twenty checks behind it down with a
        # KeyError, and the state of everything behind a failure is what a harness is for.
        if checks.ok(
            8 in listed,
            "GET /boxes lists a box that holds cards but has no registry entry — the union, "
            "not the registry, so no box captured before D20 is invisible",
        ):
            checks.equal(
                [listed[8]["state"], listed[8]["capacity"], listed[8]["sections"]],
                [master.BOX_OPEN, None, []],
                "and it renders as open, uncapped and undeclared, which is what it is",
            )
            checks.equal(
                [listed[8]["cards"], listed[8]["fill"], listed[8]["next_index"]],
                [3, 3, 4],
                "with its fill and next index read the same way every other box's are",
            )

        # --- POST creates, and refuses to be an upsert -----------------------------------
        status, created = capture_server.do_create_box(
            {"box": 9, "name": "ME01 commons", "sections": [1, 31]}
        )
        checks.equal(status, HTTPStatus.CREATED, "POST /boxes answers 201")
        checks.equal(
            [created["box"], created["name"], created["cards"]],
            [9, "ME01 commons", 0],
            "and a box can be created EMPTY — D20's whole reason for existing, since a "
            "mistyped box number was previously caught only by `new_box` after a photo "
            "had already been written into it",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({"box": 9}),
            "box_exists",
            "and a second POST refuses as box_exists rather than upserting — a quiet "
            "success here would rename box 9 while the operator believed they were adding one",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({"box": 10, "capacity": 250}),
            "field_not_settable",
            "capacity is not a creation field: nobody knows a box's capacity when they "
            "start filling it, and a guess accepted here is inherited by every fraction "
            "drawn from that box (D20)",
        )

        # --- PUT changes the three things a human decides, and nothing else --------------
        refusal(
            checks,
            lambda: capture_server.do_put_box(9, {"capacity": 250}),
            "field_not_settable",
            "and PUT refuses `capacity` for the same reason — it is FROZEN at the seal, "
            "never typed",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box(9, {"box": 11}),
            "field_not_settable",
            "and refuses `box`: a body that could change a box NUMBER would be a renumber, "
            "which D10 forbids outright",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box(9, {"state": "sealed"}),
            "box_state_invalid",
            "a state outside open/closed refuses in its OWN code, not as field_not_settable "
            "— the field is settable and the value is not one of the two",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box(99, {"name": "nowhere"}),
            "box_not_found",
            "and a box number nothing in this store has ever seen refuses as box_not_found",
        )
        adopted = capture_server.do_put_box(8, {"name": "pre-registry"})
        checks.equal(
            adopted["name"],
            "pre-registry",
            "but the unregistered box is ADOPTED rather than refused: GET /boxes lists it, "
            "so refusing here would put a dead rename control on a live row",
        )

        # --- sealing freezes capacity at the fill ---------------------------------------
        sealed = capture_server.do_put_box(9, {"state": master.BOX_CLOSED})
        checks.equal(
            [sealed["capacity"], sealed["fill"], sealed["state"]],
            [0, 0, master.BOX_CLOSED],
            "sealing an empty box freezes capacity at its fill, which is zero",
        )
        reopened = capture_server.do_put_box(9, {"state": master.BOX_OPEN})
        checks.equal(
            reopened["capacity"],
            None,
            "and re-opening drops capacity rather than leaving a stale number standing",
        )
        filled = capture_server.do_put_box(8, {"state": master.BOX_CLOSED})
        checks.equal(
            [filled["capacity"], filled["fill"]],
            [3, 3],
            "sealing a filled box freezes capacity at the cards it holds — the difference "
            "between D20's '#40 of 250 · 16% in' and a denominator that keeps growing",
        )
        # BOTH SEALED-BOX REFUSALS GO OVER A SOCKET, and they are the only cases in this
        # section that have to. `store/master.py` raises `BoxClosed` and `_dispatch` is what
        # turns it into a code, so an in-process call asserts the store's exception and
        # proves nothing about what a client is told — which is the half that reaches a
        # screen. Asserted here as well, since a route that stopped raising would answer 500.
        checks.raises(
            master.BoxClosed,
            lambda: capture_server.do_put_box(8, {"state": master.BOX_CLOSED}),
            "sealing a sealed box raises rather than restamping it — the alternative "
            "reading is that the call re-froze capacity at a new fill",
        )
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            status, body, _ = request(
                port, "PUT", "/boxes/8", payload={"state": master.BOX_CLOSED}
            )
            checks.equal(status, 409, "and on the wire a second seal is a 409, not a 500")
            checks.equal(
                error_code(body),
                "box_closed",
                "answering in its own code: the request was well-formed and lost a race "
                "with the lid",
            )

            status, body, _ = request(port, "POST", "/capture", payload=capture_payload(8))
            checks.equal(status, 409, "a capture into a sealed box is refused the same way")
            checks.equal(
                error_code(body),
                "box_closed",
                "and in the same code — one more card would falsify every fraction already "
                "printed off that box",
            )
            after = {row["box"]: row for row in capture_server.do_boxes()["boxes"]}
            checks.equal(
                [
                    after.get(8, {}).get("capacity"),
                    after.get(8, {}).get("fill"),
                    after.get(9, {}).get("capacity", "missing"),
                ],
                [3, 3, None],
                "AND NEITHER REFUSAL CHANGED ANYTHING: box 8 is still sealed at 3 with no "
                "index burned, and box 9 is still uncapped",
            )
        finally:
            httpd.shutdown()
            httpd.server_close()

    # --- GET /search: D7's SKU -> positions map, finally served to a screen -------------
    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(8, set_hint="me01"))
        capture_server.do_capture(capture_payload(8, game="misc"))
        capture_server.do_put_card(8, 4, {"note": "blue-eyes, japanese"})
        with Store().write() as snapshot:
            for key in ("8/1", "8/2", "8/3"):
                card = snapshot.inventory.cards[key]
                card.sku = "555"
                card.name = "Eiscue"
                card.number = "044"
                card.printed_total = "167"
                card.condition = "Near Mint"
            snapshot.inventory.listing("555", condition="Near Mint").live = 2
            snapshot.inventory.set_state("8/3", master.SOLD)

        for blank in ("", "   ", "\t\n"):
            refusal(
                checks,
                lambda q=blank: capture_server.do_search(q),
                "query_required",
                f"a search for {blank!r} refuses as query_required — clearing the box is "
                "not a request for every card in the store",
            )

        found = capture_server.do_search("eiscue")["groups"]
        if checks.equal(
            [group["sku"] for group in found],
            ["555"],
            "a name finds the SKU, and the answer is the SKU rather than the card — D7's "
            "map, which has existed in the store since the store did and reached no screen",
        ):
            group = found[0]
            checks.equal(
                [copy["key"] for copy in group["copies"]],
                ["8/1", "8/2", "8/3"],
                "with every copy at its own position, in box-walk order, the sold one "
                "included",
            )
            checks.equal(
                group["on_hand"],
                2,
                "and `on_hand` EXCLUDES the sold copy while `copies` still lists it: a sale "
                "leaves a permanent gap that the operator still needs to see (D10)",
            )
            checks.equal(
                group["cap"],
                join.LIVE_QUANTITY_CAP,
                "and `cap` is pipeline/join.py's playset imported, never the literal 4 — "
                "the screen's '2 of 4 live' moves the day D7's cap does",
            )
            # D7: "listed quantity is min(cap, on hand)". THE SHELF BINDS HERE, WHICH IS THE
            # WHOLE POINT OF THE FIELD: two copies on hand against a cap of four, so the most
            # this SKU can ever have live is two. The screen drew the bare `cap` as the
            # denominator of `listed N of ...` until 2026-08-25, so a card the owner had one of
            # read `listed 0 of 4` — three copies of headroom that do not exist. Asserted
            # against the arithmetic rather than the literal 2, so it moves with the cap.
            checks.equal(
                group["listable"],
                min(join.LIVE_QUANTITY_CAP, 2),
                "and `listable` is what that cap COMES TO for this SKU — min(cap, on hand), "
                "so the shelf binds it to 2 and the screen cannot promise a playset the "
                "boxes do not hold",
            )
            checks.equal(
                group["listed"],
                {
                    stage: (2 if stage == master.LIVE else 0)
                    for stage in master.LISTING_STAGES
                },
                "listing counts come out as zeros rather than nulls for the stages nothing "
                "has reached: 'nothing was emitted' is a fact, not an absence",
            )

        by_note = capture_server.do_search("japanese")["groups"]
        checks.equal(
            [copy["key"] for group in by_note for copy in group["copies"]],
            ["8/4"],
            "a card the pipeline never identified is found BY ITS NOTE — it has no name, "
            "no number and no SKU, so the note is the only thing it can be found by, and "
            "leaving it out of the search would make the field write-only",
        )
        checks.equal(
            [group["sku"] for group in by_note],
            [None],
            "and it groups under a null SKU, which sorts last: a bag of cards, not a product",
        )
        checks.equal(
            [group["sku"] for group in capture_server.do_search("044/167")["groups"]],
            ["555"],
            "and the join key itself is searchable — it is the string the run report and "
            "the queue file both print, so it is what gets pasted into a search box",
        )


# -------------------------------------------------------------------------- place block


def check_box_names(checks: Checks) -> None:
    """A name is how a box is ADDRESSED now, so it is unique, it is logged, and it can stand
    in for a number nobody wants to type.

    ITS OWN `isolated_home`, this file's own repeated lesson. Every case here writes boxes,
    and `check_box_routes_and_search` counts them; the mass-select block and the starvation
    block were both first written into somebody else's fixture and both failed on the
    fixture rather than on the code.

    WHAT CHANGED AND WHY IT NEEDED COVERAGE. `Box.name` existed from D20 and nothing checked
    it — right while the NUMBER was the identifier, because a duplicate name cost a confusing
    row and nothing else. The capture screen now finds a box by name, which makes a second
    "commons" an ambiguous physical address, and makes a rename relabel every card in the box
    the way a moved divider relabels every card behind it. `server/capture_server.py` had
    recorded the missing event as a known gap in `do_put_box`'s own docstring, with the right
    reason for leaving it — "a name is a label, not a claim the pipeline spends money
    against". That sentence is what stopped being true.
    """
    checks.note("")
    checks.note("BOX NAMES — store/master.py, server/capture_server.py")

    with isolated_home():
        # --- a name alone is a complete creation -----------------------------------------
        named = capture_server.do_create_box({"name": "ME01 commons"})[1]
        checks.equal(
            [named["box"], named["name"]],
            [1, "ME01 commons"],
            "POST /boxes with a NAME and no number takes the lowest free number — the "
            "owner's ask, in their words: the primary key is something they do not care "
            "about, and the label is what they work in",
        )
        second = capture_server.do_create_box({"name": "mega pulls"})[1]
        checks.equal(
            second["box"],
            2,
            "and the next one takes the next free number rather than a high-water mark: a "
            "box number names a physical object nobody types any more, so there is no gap "
            "for a mark to protect",
        )
        refusal(
            checks,
            lambda: capture_server.do_create_box({}),
            "box_or_name_required",
            "a body with neither refuses: it does not describe a box, and inventing both "
            "halves of an object nobody named is how a registry fills with rows no one meant",
        )

        # --- uniqueness, folded and stripped ---------------------------------------------
        # THE STORE'S EXCEPTION, NOT THE ROUTE'S CODE, and the difference is the one this
        # file already draws for `BoxClosed`: `store/master.py` raises and `_dispatch` is
        # what turns it into `name_taken`, so an in-process call asserts the rule while the
        # socket case asserts what a client is told. The rule is the half that protects the
        # data, and it is the half that would be lost if the check moved into the route.
        checks.raises(
            master.BoxNameTaken,
            lambda: capture_server.do_create_box({"name": "  ME01 Commons "}),
            "a duplicate name refuses even folded and padded — `Commons` and `commons ` are "
            "one box to a person at a shelf, and a store that took both would enforce a "
            "rule nobody can see",
        )
        checks.equal(
            len(capture_server.do_boxes()["boxes"]),
            2,
            "and the refusal wrote nothing: two boxes, not three",
        )

        # --- a rename logs both names ----------------------------------------------------
        before = len(Store().history())
        capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})
        renamed = [e for e in Store().history() if e["event"] == "box_renamed"]
        checks.equal(
            [len(renamed), renamed[-1]["name_from"], renamed[-1]["name_to"]],
            [1, "ME01 commons", "ME01 commons, tray 2"],
            "a rename appends `box_renamed` carrying BOTH names — `resectioned`'s sibling "
            "one scale up, because the label a rename moves is every card in the box",
        )
        checks.equal(
            len(Store().history()) - before,
            1,
            "and exactly one event: the rename, not a rename plus a box_created from the "
            "`ensure_box` the route calls on its way to it",
        )

        # --- a no-op rename is not a rename ----------------------------------------------
        steady = len(Store().history())
        capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})
        checks.equal(
            len(Store().history()),
            steady,
            "re-sending a box its own name writes NO event — a log line for a request that "
            "changed nothing is a rename that never happened, and history is read as the "
            "record of what did",
        )
        checks.equal(
            capture_server.do_put_box(1, {"name": "ME01 commons, tray 2"})["name"],
            "ME01 commons, tray 2",
            "and it does not conflict with ITSELF: the uniqueness check skips the box being "
            "written, which is the shape a screen that PUTs its whole form back produces",
        )

        # --- clearing puts it back to unnamed --------------------------------------------
        cleared = capture_server.do_put_box(1, {"name": None})
        checks.equal(
            cleared["name"],
            None,
            "`{name: null}` clears the name — the shape a cleared text field sends, and a "
            "legitimate edit rather than a refusal",
        )
        cleared_event = [e for e in Store().history() if e["event"] == "box_renamed"][-1]
        checks.equal(
            [cleared_event["name_from"], "name_to" in cleared_event],
            ["ME01 commons, tray 2", False],
            "and the clear is logged like any other rename, with `name_to` ABSENT rather "
            "than null — `_log` drops None by construction, the same convention that keeps "
            "a box-level event from carrying a null `position`. Asserted rather than worked "
            "around: after this write there is no other evidence the box was ever called "
            "anything, so what the line does and does not carry is the whole record",
        )
        freed = capture_server.do_create_box({"name": "ME01 commons, tray 2"})[1]
        checks.equal(
            freed["box"],
            3,
            "and the freed name is claimable again — uniqueness is over what is CURRENTLY "
            "held, not over every name a store has ever seen",
        )

        # --- the allocator sees cards, not just the registry -----------------------------
        with Store().write() as snapshot:
            checks.equal(
                snapshot.inventory.next_box_number(),
                4,
                "next_box_number skips every number the registry holds",
            )
        for _ in range(2):
            capture_server.do_capture(capture_payload(7))
        with Store().write() as snapshot:
            # The pre-D20 shape: a box that holds cards and has no registry entry. It cannot
            # be reached through the front door any more, which is exactly why it is built by
            # hand — every box filled before the registry existed is in it.
            del snapshot.inventory.boxes["7"]
        with Store().write() as snapshot:
            taken = snapshot.inventory.next_box_number()
        checks.equal(
            taken,
            4,
            "and it skips a number held by CARDS with no registry entry — handing that one "
            "out again would put two boxes' photographs in one directory",
        )


def check_box_claims(checks: Checks) -> None:
    """PUT /inventory/<box> — the box-level claim apply, the owner's ask of 2026-08-23.

    THE CARD ROUTE ONE SEGMENT BROADER: same `PUT_FIELDS` vocabulary, same decoders, same
    per-game validators, same `corrected` line — applied to every eligible card in a box,
    all-or-nothing (D29's group shape). What this section works hardest is the boundary:
    a refused call changes NOTHING, terminal records are skipped and named, and a mixed
    box (legal, D21) is judged per card against each card's own game unless this call
    sets one.
    """
    checks.note("")
    checks.note("BOX-LEVEL CLAIMS — PUT /inventory/<box>")

    with isolated_home():
        for i in range(1, 6):
            capture_server.do_capture(capture_payload(6))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("6/2", master.IDENTIFIED)
            snapshot.inventory.set_state("6/4", master.SOLD)
            snapshot.inventory.retire("6/5", "damaged")
            # A mixed box, which D21 makes legal — the case the per-game judging exists for.
            snapshot.inventory.cards["6/3"].game = "riftbound"

        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {}),
            "nothing_to_apply",
            "a bulk apply carrying no claim refuses — an empty sweep over a box is a "
            "client error, not a no-op success",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {"state": "sold"}),
            "field_not_settable",
            "claims ONLY: state has its own routes and its own rulings, and the "
            "vocabulary check keeps it out of this body",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(99, {"set_hint": "sv9"}),
            "box_not_found",
            "an unknown box refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(6, {"game": "yugioh"}),
            "game_invalid",
            "and an unregistered game refuses through the same decoder the card route uses",
        )

        # The mixed-box refusal: `reverse_holo` is Pokemon's cell and not Riftbound's, the
        # body names no game, so the claim is judged against EACH card's own game — and
        # one rejection refuses the WHOLE call, naming the card.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_put_box_claims(6, {"variant": "reverse_holo"}),
            "a claim one card's game does not stock refuses the whole call — a sweep that "
            "corrected only the cards that fit leaves a box nobody asked for",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None), "claim_not_stocked_by_game", "in its own code"
            )
            checks.ok(
                "card 3" in str(caught),
                "naming the card whose game rejected it",
                f"message was: {caught}",
            )
        checks.ok(
            all(
                c.metadata_finish is None
                for c in Store().read().inventory.cards.values()
            ),
            "and the refusal changed nothing on any card",
        )

        # The same claim WITH the game set: judged once against the game THIS call sets
        # (`do_put_card`'s judged_against rule at box scale), applied to every eligible
        # card, terminal records skipped and named.
        body = capture_server.do_put_box_claims(
            6, {"game": "pokemon", "variant": "reverse_holo", "set_hint": "sv9"}
        )
        checks.equal(
            (body["eligible"], body["applied"], body["skipped_terminal"]),
            (3, 3, 2),
            "the receipt counts what was eligible, what moved, and what was left alone",
        )
        checks.equal(
            body["skipped"],
            [{"index": 4, "state": "sold"}, {"index": 5, "state": "retired"}],
            "and NAMES the skipped terminal records — their record is history (D10, D26), "
            "and a bulk sweep is exactly the indiscriminate write they deserve protection "
            "from; the card route stays the deliberate one-position door",
        )
        after = Store().read().inventory
        # A LIST ON THE RECORD, and the list is the point rather than a spelling change.
        # `store/master.py:Card.metadata_finish` is a list because `to_payload` calls
        # `asdict` and JSON has to round-trip it unchanged; the two frozen carriers
        # downstream (`sidecar.Capture`, `join.IdentifiedCard`) hold tuples for the opposite
        # reason, and this test asserts both shapes in their own places on purpose.
        checks.ok(
            all(
                (after.cards[f"6/{i}"].game, after.cards[f"6/{i}"].metadata_finish)
                == ("pokemon", ["reverse_holo"])
                for i in (1, 2, 3)
            ),
            "every eligible card carries the claims now — including the one whose game "
            "this same call corrected, judged against the game as set",
        )
        checks.ok(
            after.cards["6/4"].metadata_finish is None
            and after.cards["6/5"].metadata_finish is None,
            "and the sold and retired records are untouched",
        )
        sidecar_now = json.loads(
            capture_server.sidecar_path(capture_server.photo_path(6, 1)).read_text("utf-8")
        )
        checks.ok(
            sidecar_now.get("variant") == ["reverse_holo"]
            and sidecar_now.get("game") == "pokemon",
            "the sidecar is rewritten for a changed card — the correction has to reach "
            "the file `identify` actually reads, or D3 rung 1 never hears it",
            f"sidecar was: {sidecar_now}",
        )
        bulk_lines = [
            e
            for e in Store().history()
            if e.get("event") == capture_server.CORRECTED and "bulk" in e
        ]
        checks.ok(
            len(bulk_lines) == 3
            and all(e.get("bulk") == 3 and "changed" in e for e in bulk_lines),
            "one `corrected` line per changed position, tagged `bulk` with the sweep's "
            "size — D29's group tag, so the log tells one sweep from three hand edits",
            f"lines were: {bulk_lines!r}",
        )
        second = capture_server.do_put_box_claims(
            6, {"game": "pokemon", "variant": "reverse_holo", "set_hint": "sv9"}
        )
        checks.ok(
            second["applied"] == 0 and second["unchanged"] == 3,
            "restating the same claims applies nothing — a no-op writes no history and "
            "churns no sidecars",
        )
        checks.equal(
            len(
                [
                    e
                    for e in Store().history()
                    if e.get("event") == capture_server.CORRECTED and "bulk" in e
                ]
            ),
            3,
            "and the log gained no new lines for it",
        )
        checks.ok(
            after.cards["6/2"].state == master.IDENTIFIED
            and after.cards["6/4"].state == master.SOLD,
            "no card moved state — this route corrects claims and nothing else",
        )

    # --- `indices`: the owner's mass-select, 2026-08-23 ------------------------------------
    # ITS OWN HOME, deliberately. The block above counts history lines over a box it built
    # card by card, so a sweep run against that same fixture moves numbers it asserts —
    # which is how this section first failed. A selection test needs its own box more than
    # it needs the mixed-game one above.
    #
    # ON THE ROUTE RATHER THAN AS N CARD CALLS. A client loop over `PUT /inventory/<box>/
    # <index>` would be N requests with N chances to half-apply — the seventh refusing on a
    # per-game vocabulary while the first six are already written, which is exactly the
    # partial sweep this route's all-or-nothing exists to prevent.
    with isolated_home():
        for _ in range(5):
            capture_server.do_capture(capture_payload(8))

        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": [], "set_hint": "x"}),
            "indices_invalid",
            "AN EMPTY SELECTION REFUSES RATHER THAN MEANING THE WHOLE BOX — the two read "
            "alike and are opposite intents, and an emptied selection widening to every "
            "card in the box is the accident worth a refusal of its own",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": 3, "set_hint": "x"}),
            "indices_invalid",
            "and a bare number is not a selection",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(8, {"indices": [1, 0], "set_hint": "x"}),
            "indices_invalid",
            "and neither is a card number below one",
        )

        hints = lambda: [
            Store().read().inventory.cards[f"8/{i}"].set_hint for i in range(1, 6)
        ]
        before = hints()
        refusal(
            checks,
            lambda: capture_server.do_put_box_claims(
                8, {"indices": [1, 99], "set_hint": "swept"}
            ),
            "card_not_found",
            "a selection naming a card the box does not hold refuses the WHOLE call — a "
            "selection is a statement about a set, and an operator wrong about one member "
            "may be wrong about which box they are looking at",
        )
        checks.equal(
            hints(),
            before,
            "and it wrote NOTHING on the way to that refusal — card 1 was a valid member "
            "and is untouched, which is the all-or-nothing this route promises everywhere",
        )

        narrowed = capture_server.do_put_box_claims(
            8, {"indices": [1, 3], "set_hint": "picked"}
        )
        narrowed = narrowed[-1] if isinstance(narrowed, tuple) else narrowed
        checks.equal(
            [narrowed["eligible"], narrowed["applied"]],
            [2, 2],
            "a selection narrows the sweep to exactly its members — two of the box's five "
            "cards, not the box",
        )
        checks.equal(
            hints(),
            ["picked", None, "picked", None, None],
            "and card 2 — eligible, in the box, simply NOT SELECTED — is untouched, which "
            "is the whole difference between a mass-select and a bulk apply",
        )

        whole = capture_server.do_put_box_claims(8, {"set_hint": "everything"})
        whole = whole[-1] if isinstance(whole, tuple) else whole
        checks.equal(
            whole["eligible"],
            5,
            "OMITTING `indices` still means the whole box — the compatibility guarantee "
            "that makes the selection strictly additive to the route that shipped without it",
        )


def check_place_neighbors(checks: Checks) -> None:
    """D30's digital half on the wire: `neighbors` and `section_gaps` in the place block.

    `Card 17` IS THE SEVENTEENTH SLOT, NOT THE SEVENTEENTH CARD YOU CAN COUNT. Every sale
    and every retirement leaves a permanent gap (D10), and once a section has one, those
    two numbers diverge for every label behind it. D30's ruling is that a located place
    block also carries what makes the label countable by hand again: the nearest
    NON-TERMINAL records on either side, and how many permanent holes this card's own
    section holds. Asserted on `GET /inventory`'s rows — the route the app polls — because
    the block is wire-only and the wire is the only place the claim exists.

    THE CONSTRUCTION UNDER TEST IS "RECORDS, NOT INDICES", read from three sides. A
    terminal record is skipped as a landmark and counted as a hole — one ruling, two
    directions. An unallocated index is neither: no record means no card was ever there,
    so a declared section running past the fill adds nothing to the count. And a pooled
    record is skipped BY RULING rather than by state (D24) — it has no slot to leave a
    hole in, whatever state it is in.

    THE DEGRADE CASE IS THE ONE THAT MATTERS, and it is this section's half of the
    corrupt-record case `check_server_routes` arms. "Between Mantine and Thievul" is a
    position claim somebody counts slots against, so a walk that skipped an unreadable
    record would keep the sentence rendering while possibly naming the wrong neighbour —
    the exact failure a position label may never cause, one hop removed. The decoration
    therefore degrades WHOLE and STORE-WIDE, and costs nobody their label.
    """
    checks.note("")
    checks.note("PLACE BLOCK — neighbours and section gaps (D30), server/capture_server.py")

    with isolated_home():
        # --- a gapped box tells the truth ------------------------------------------------
        # Five captures, then a sale at 2 and a retirement at 4 — both through their own
        # routes, so the states are the ones the store writes and not hand-set strings.
        # Card 1 gets a name on the store directly: `name` is an identification result,
        # not a capture claim — it is deliberately absent from `PUT_FIELDS` — so there is
        # no route that sets it by hand, and the join that would is not in this fixture.
        for _ in range(5):
            capture_server.do_capture(capture_payload(4))
        with Store().write() as snapshot:
            snapshot.inventory.cards["4/1"].name = "Mantine"
        capture_server.do_mark_sold(4, 2, {})
        capture_server.do_retire(4, 4, {"reason": "damaged"})

        rows = capture_server.do_inventory()["cards"]
        checks.equal(
            rows["4/3"]["place"]["neighbors"],
            {"prev": {"index": 1, "name": "Mantine"}, "next": {"index": 5, "name": None}},
            "a card between two gaps names the nearest NON-TERMINAL records — the sold "
            "card at 2 and the retired card at 4 are skipped as landmarks, never named: "
            "a departed card cannot be the thing you count from (D30)",
        )
        checks.equal(
            rows["4/3"]["place"]["section_gaps"],
            2,
            "and the same two records are COUNTED as this section's holes — skipped as a "
            "landmark and counted as a gap are one ruling read from two sides",
        )
        checks.equal(
            rows["4/1"]["place"]["neighbors"]["prev"],
            None,
            "the first card in a box answers `prev: null` — the box's edge, never a guess "
            "past it",
        )
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["next"],
            None,
            "and the newest answers `next: null` the same way",
        )
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["prev"],
            {"index": 3, "name": None},
            "a neighbour nothing has identified degrades to its index: `name` is null ON "
            "THE WIRE, and the null is the wire's whole job — the `#3` a screen shows for "
            "it is the app's rendering, and a placeholder string minted here would be a "
            "second vocabulary nothing audits",
        )

        # --- an unallocated tail is not a gap --------------------------------------------
        # A declared divider far past the fill: section 1 of box 5 runs to index 50 while
        # the box holds five cards. `section_gaps` counts terminal RECORDS, not unoccupied
        # indices — that an empty tail adds nothing is the CONSTRUCTION, not a bounds
        # check, and this is the box that would catch the bounds check creeping back in.
        capture_server.do_create_box({"box": 5, "sections": [1, 51]})
        for _ in range(5):
            capture_server.do_capture(capture_payload(5))
        capture_server.do_mark_sold(5, 2, {})
        place = capture_server.do_inventory()["cards"]["5/3"]["place"]
        # 50 UNTIL D58 AND 49 SINCE, WHICH IS ONE DEPARTED CARD AND NOT A LOST PLAN. The
        # divider is declared at index 51 and the box has sold one card, so it now stands
        # in front of the FIFTIETH card rather than the fifty-first slot; section 1 runs to
        # the forty-ninth. `Position._divider` is what keeps the other 45 slots — the ones
        # the box has not grown into — counting for one card each, so a layout typed in
        # before the box was filled still says what was typed.
        checks.equal(
            place["section_end"],
            49,
            "a declared divider past the fill still carries its unfilled slots — the "
            "block says the section ends at 49, one short of the declared 50, because "
            "one card has left the box in front of it (D58)",
        )
        checks.equal(
            place["section_gaps"],
            1,
            "and the 45 unallocated indices behind it add NOTHING to the gap count: an "
            "index with no record is a card that was never captured, not a hole where one "
            "used to be — only the sold record at 2 is a gap",
        )

        # --- pooled: no section is not "no holes" ----------------------------------------
        # A code card captured into the same box burns index 6 as a KEY — the photo and
        # sidecar are named after it — but it has no slot, so its block carries the pooled
        # nulls and the located cards' sentences never mention it.
        capture_server.do_capture(capture_payload(4, game="pokemon_code"))
        pooled = capture_server.do_inventory()["cards"]["4/6"]["place"]
        checks.ok(
            not pooled["located"],
            "a pokemon_code card's place block answers located: false (D24)",
        )
        checks.equal(
            [pooled["neighbors"], pooled["section_gaps"]],
            [None, None],
            "and its `neighbors` and `section_gaps` are both null — NULL AND NOT ZERO, "
            "because zero would claim a countable section with no holes, and 'no section "
            "at all' is a different fact from 'no holes in it'",
        )
        # Retired, so that being skipped by RULING is distinguishable from being skipped
        # by state: a terminal pooled record is what a state-only walk would count.
        capture_server.do_retire(4, 6, {"reason": "given_away"})
        rows = capture_server.do_inventory()["cards"]
        checks.equal(
            rows["4/5"]["place"]["neighbors"]["next"],
            None,
            "a pooled record is never named as anyone's neighbour — card 5's `next` is "
            "still the box's edge, not the code card whose index happens to be 6",
        )
        checks.equal(
            rows["4/3"]["place"]["section_gaps"],
            2,
            "and never counted as anyone's gap, even retired: it is skipped by RULING, "
            "not by state — a card with no slot cannot leave a hole in one (D24)",
        )

        # --- the degrade rule: whole, store-wide, and never a guess ----------------------
        # The other half of the corrupt-record case `check_server_routes` arms. The walk
        # reads every record's own `box` and `index`, so it is armed here in a THIRD box —
        # the store-wide claim is the claim, and a same-box corruption could not test it.
        capture_server.do_capture(capture_payload(7))
        intact = capture_server.do_inventory()["cards"]["4/3"]["place"]
        with Store().write() as snapshot:
            snapshot.inventory.cards["7/1"].box = "seven"
        rows = capture_server.do_inventory()["cards"]
        degraded = rows["4/3"]["place"]
        checks.equal(
            [degraded["neighbors"], degraded["section_gaps"]],
            [None, None],
            "one record whose box will not coerce nulls the decoration for a card in a "
            "DIFFERENT box: skipping the unreadable record would keep the sentence "
            "rendering while possibly naming the wrong neighbour, and 'between X and Y' "
            "is a position claim somebody counts slots against",
        )
        checks.equal(
            [rows["5/3"]["place"]["neighbors"], rows["5/3"]["place"]["section_gaps"]],
            [None, None],
            "and the degrade is STORE-WIDE, not per-box — box 5 loses its sentences to "
            "box 7's record too, because a walk that cannot read one record cannot vouch "
            "for any neighbour it names anywhere",
        )
        # THE LABEL NOW DEGRADES WITH THE DECORATION AND IT USED NOT TO, which is the one
        # place D58 is visible in this file's degrade story and the reversal of what this
        # case asserted. It required the label, section, card and section_start to survive
        # a corrupt record in a DIFFERENT box, on the ground that "a label needs only this
        # record's own two integers and the layout". Both halves of that ground are gone:
        # the number is now a count of the cards on hand in this box, so it needs the walk,
        # and the walk is what the corrupt record broke. `located` is the one field that
        # survives, because whether this game has slots at all is a registry question and
        # not a counting one.
        checks.equal(
            [
                degraded["located"],
                degraded["label"],
                degraded["section"],
                degraded["card"],
                degraded["section_start"],
            ],
            [True, None, None, None, None],
            "the label and every number drawn from it degrade WITH the walk (D58): they "
            "count the cards in the box, and one record in the store could not be counted",
        )
        checks.ok(
            intact["label"] is not None and intact["card"] is not None,
            "where the intact read a moment earlier answered all of them — so this is the "
            "walk failing, not the box being unlabellable",
        )
        # `section_end` WAS IN THAT LIST AND CAME OUT ON 2026-08-29, which is the one place
        # deleting the 25-card default is visible in this file's degrade story. Box 4
        # declares no layout, so it used to get a 25-card window that needed no count at all
        # and survived anything; it is ONE section now, and one section's end IS the box's
        # end — `_denominator`, the number that degrades. So this field follows the count and
        # the four above do not, and that split is the assertion rather than a caveat on it:
        # a label is built from this record's own two integers and the layout, and a number
        # derived from a whole-store scan cannot honestly outlive the scan.
        checks.equal(
            [degraded["section_end"], degraded["box_total"]],
            [None, 0],
            "and `section_end` degrades WITH the denominator, because an undeclared box's "
            "one section ends where the box does — the same degrade `fraction` takes, and "
            "not the label's",
        )
        # [6, 6] UNTIL D58 AND [3, 3] SINCE. Box 4 holds six records: two terminal (the two
        # this section already counts as its gaps), one pooled code card that never had a
        # slot at all (D24), and three cards. The fill was the denominator and the cards on
        # hand are — which is D58's arithmetic seen from the box rather than from a card,
        # and it counts BOTH exclusions because both are answers to "what would a person
        # opening this box count".
        checks.equal(
            [intact["section_end"], intact["box_total"]],
            [3, 3],
            "where an intact read says that section ends at the CARDS ON HAND: no divider "
            "is invented past the cards that exist (D10, amended), and no slot is counted "
            "for a card that has left (D58)",
        )
        checks.ok(
            "label" not in rows["4/3"],
            "and the flat label on the row degrades with the block rather than falling "
            "back to an index-space one — omitted exactly as a record whose box will not "
            "coerce has always been, so `positionLabel` answers null and no screen is "
            "handed a number from the numbering system this change replaced",
        )


# ---------------------------------------------------- D58: the numbers count the cards


def check_consolidated_numbering(checks: Checks) -> None:
    """A card's number is its place among the cards IN the box, not among the slots. D58.

    THE PROPERTY, AND IT IS ONE SENTENCE: sell card 17 and the card behind it becomes card
    17. `docs/specs/order-flow.md` §10.4 spells out what that replaces — *"`Card 17` is the
    seventeenth slot, not the seventeenth card you can count"* — and D30 has been waiting
    since 2026-08-23 for a physical marker to explain the difference to whoever is holding
    the box. There is nothing left to explain.

    THE STORED INDEX NEVER MOVES AND THAT IS ASSERTED HERE TOO. This is a rendering change:
    no photograph is renamed, no queue entry re-keyed, no history line changes subject, and
    `next_index` is the high-water mark it has always been. D10's permanent gap survives
    intact in the one place it was ever load-bearing — the allocator — which is why the two
    hardest cases in this file (`check_allocator`'s and `check_mark_sold`'s) are untouched
    by all of this.

    THE SECTION HALF IS THE HALF THAT IS EASY TO GET WRONG, so it is asserted from both
    sides: a sale in an EARLIER section must leave a later section's card numbers alone,
    and a sale in the SAME section in front of a card must move it by one. Mapping only the
    cards and not the dividers would pass the second and fail the first, and a build that
    mapped neither would pass the first and fail the second.
    """
    checks.note("")
    checks.note("D58 — THE NUMBER COUNTS THE CARDS IN THE BOX")

    with isolated_home():
        # Two sections, six cards each: [1, 7] over twelve.
        capture_server.do_create_box({"box": 3, "sections": [1, 7]})
        for _ in range(12):
            capture_server.do_capture(capture_payload(3))

        def label(index: int) -> object:
            return capture_server.do_inventory()["cards"][f"3/{index}"].get("label")

        def place(index: int) -> dict:
            return capture_server.do_inventory()["cards"][f"3/{index}"]["place"]

        checks.equal(
            [label(1), label(7), label(12)],
            [
                "Box 3 · Section 1 · Card 1",
                "Box 3 · Section 2 · Card 1",
                "Box 3 · Section 2 · Card 6",
            ],
            "a box nothing has left renders exactly as it did before D58 — the two spaces "
            "coincide until the first departure, which is what makes this additive",
        )

        # --- a departure in section 1 -----------------------------------------------------
        capture_server.do_mark_sold(3, 3, {})
        checks.equal(
            label(4),
            "Box 3 · Section 1 · Card 3",
            "SELL CARD 3 AND THE CARD BEHIND IT BECOMES CARD 3 — the whole of D58 in one "
            "assertion, and the sentence `docs/specs/order-flow.md` §10.4 says could not "
            "be true while a label named a slot",
        )
        checks.equal(
            label(7),
            "Box 3 · Section 2 · Card 1",
            "AND SECTION 2 IS UNDISTURBED: a sale in an earlier section moves the divider "
            "and the cards behind it by the same one, so the number WITHIN a section is "
            "the difference between two things that both moved. Mapping the cards and not "
            "the dividers would read `Card 2` here",
        )
        checks.equal(
            [place(4)["slot"], place(4)["index"], place(7)["slot"], place(7)["index"]],
            [3, 4, 6, 7],
            "and `slot` and `index` are both on the wire and both true: the number a "
            "person counts to, and the store key every write still aims by",
        )
        checks.equal(
            capture_server.do_inventory()["cards"]["3/3"].get("label"),
            "Box 3 · departed",
            "the DEPARTED card does not keep the number it held — that number belongs to "
            "the card that closed up behind it, and answering it would send someone to the "
            "wrong slot. It says where the record belongs and that there is no slot, which "
            "is the same shape a pooled card's line takes for the same reason (D24)",
        )
        checks.equal(
            place(3)["label"],
            join.departed_label(3),
            "and its block says so in the one composer that owns that string, beside "
            "`pooled_label` — a card with no slot, said the same way both times it happens",
        )
        checks.equal(
            [place(3)["slot"], place(3)["card"], place(3)["fraction"]],
            [None, None, None],
            "with every number that would have counted it null rather than stale",
        )

        # --- a departure in the SAME section, in front ------------------------------------
        capture_server.do_mark_sold(3, 8, {})
        checks.equal(
            label(9),
            "Box 3 · Section 2 · Card 2",
            "a sale in this card's OWN section and in front of it moves it by one — the "
            "other half of the pair, and the half a build that mapped nothing would pass",
        )
        checks.equal(
            label(4),
            "Box 3 · Section 1 · Card 3",
            "while section 1 is untouched by a sale behind it: the map runs one way",
        )

        # --- the index never moved --------------------------------------------------------
        inventory = Store().read().inventory
        checks.equal(
            inventory.next_index(3),
            13,
            "AND NOT ONE INDEX MOVED. `next_index` is the high-water mark it always was, "
            "so D10's permanent gap is intact where it was ever load-bearing — this is a "
            "rendering, and the allocator never heard about it",
        )
        checks.ok(
            capture_server.photo_path(3, 4).is_file()
            and inventory.get("3/4") is not None
            and inventory.get("3/3") is not None,
            "the photograph is at the slot it was written to, and both records survive: "
            "no rename, no re-key, no migration",
        )

        # --- retired counts the same as sold ----------------------------------------------
        capture_server.do_retire(3, 5, {"reason": "damaged"})
        checks.equal(
            label(6),
            "Box 3 · Section 1 · Card 4",
            "a RETIRED card is counted out exactly as a sold one is — `master.TERMINAL_"
            "STATES` is the pair, and both mean the card is not in the box any more",
        )

        # --- the box's own numbers follow -------------------------------------------------
        row = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            [row["on_hand"], row["cards"], row["fill"], row["next_index"]],
            [9, 12, 12, 13],
            "`on_hand` is what the box HOLDS and the three beside it are unchanged: "
            "`cards` counts records, `fill` is the high-water mark, and `BoxOps` still "
            "greps those two to `inventory.json`",
        )
        checks.equal(
            place(12)["box_total"],
            row["on_hand"],
            "and the denominator on a card's block is the same number as the box row's — "
            "one walk, two renderers, which is what `_denominator` used to buy by being "
            "one function",
        )
        checks.equal(
            [(d["section"], d["start"], d["end"], d["count"]) for d in row["sections_detail"]],
            [(1, 1, 4, 4), (2, 5, 9, 5)],
            "and `sections_detail` is in the same space as the labels, so the dividers "
            "editor seeds with the numbers the screen is showing",
        )

        # --- the editor round-trips through the inverse -----------------------------------
        # What the field would show, sent straight back: the store must be unchanged, which
        # is the only property that makes a count-space editor safe over an index-space
        # store. Mutation-tested by sending the RAW `sections` instead, which moves it.
        before = list(Store().read().inventory.sections_for(3))
        capture_server.do_put_box(3, {"sections": [d["start"] for d in row["sections_detail"]]})
        checks.equal(
            list(Store().read().inventory.sections_for(3)),
            before,
            "the layout the editor was seeded with, sent back unchanged, leaves the STORE "
            "unchanged — `join.divider_index` is `Position._divider` run backwards and the "
            "round trip is exact",
        )

        # Moving a divider one card later lands one index later, not one card later.
        capture_server.do_put_box(3, {"sections": [1, 6]})
        checks.equal(
            list(Store().read().inventory.sections_for(3)),
            [1, 9],
            "and a divider moved to the 6th CARD is stored at the INDEX THAT CARD SITS AT "
            "— 9, not 6, because three cards in front of it have left. That is the index "
            "`open_section` would have written had the operator pressed `S` there, so a "
            "divider typed in and a divider put in at the feeder are the same number",
        )
        capture_server.do_put_box(3, {"sections": before})

        # --- an emptied section keeps its number ------------------------------------------
        for index in (7, 9, 10, 11, 12):
            if Store().read().inventory.get(f"3/{index}").state == master.CAPTURED:
                capture_server.do_mark_sold(3, index, {})
        row = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            [(d["section"], d["count"]) for d in row["sections_detail"]],
            [(1, 4), (2, 0)],
            "a section every card has left keeps its NUMBER and reports zero: the divider "
            "is still in the plastic, and renumbering the sections behind it would send "
            "someone to the wrong one",
        )

        # --- the report and the screen spell one address ----------------------------------
        # THE LOAD-BEARING CASE. `cli/resolve.py:box_views` and `_Places._walk` are two
        # implementations of one walk, in one language but in two modules that cannot import
        # each other's caching, and a card's number is now a property of the whole box — so
        # a reporter that renders without the walk answers in the numbering system D58
        # replaced and prints it beside a screen that does not. Same shape `make
        # port-agreement` uses for the other pair that must agree.
        #
        # It also fixes a defect OLDER than D58, which is why the box here declares a layout:
        # every `Position` built in `cli/resolve.py` used to pass no layout at all, so a
        # box-2 queue entry read `Section 1 · Card 300` where the app read `Section 4 · Card
        # 48`. Nothing had ever compared the two.
        views = resolve.box_views(Store().read().inventory)
        checks.equal(
            [views[3].at(3, i).label for i in (4, 6)],
            [label(4), label(6)],
            "THE RUN REPORT AND THE SCREEN RENDER ONE ADDRESS — two walks, in two modules, "
            "asserted equal on real cards rather than trusted",
        )
        checks.equal(
            views[3].at(3, 3).label,
            place(3)["label"],
            "including for a departed card, where the two could most easily disagree",
        )
        checks.equal(
            views[3].on_hand,
            row["on_hand"],
            "and they count the same cards on hand — the denominator is the same walk",
        )


# -------------------------------------------------------------------------- concurrency


def check_concurrency(checks: Checks) -> None:
    """Simultaneous captures into one box over real sockets.

    Small N on purpose. D5 has two devices, so two and four concurrent writers is the real
    shape; the twenty-way case that found the listen backlog proved something about a socket
    option, and paying for it at the end of every turn buys nothing that this does not.

    Sockets rather than in-process calls because the lock is an flock on a fresh handle per
    call — two threads contend exactly as two processes do — and the thing worth proving is
    that no two captures ever receive the same index.
    """
    checks.note("")
    checks.note("CONCURRENCY — real sockets, small N")

    with isolated_home():
        capture_server.captures_root().mkdir(parents=True, exist_ok=True)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            for count in (2, 4):
                results: list = []
                errors: list = []

                def one(box=count):
                    try:
                        request = urllib.request.Request(
                            f"http://127.0.0.1:{port}/capture",
                            data=json.dumps(capture_payload(box)).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(request, timeout=30) as response:
                            results.append(json.loads(response.read()))
                    except Exception as exc:  # noqa: BLE001
                        errors.append(exc)

                workers = [threading.Thread(target=one) for _ in range(count)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=60)

                checks.equal(errors, [], f"{count} simultaneous captures: none errored")
                checks.equal(
                    len(results), count, f"{count} simultaneous captures: all were served"
                )
                indices = sorted(r["index"] for r in results)
                checks.equal(
                    indices,
                    list(range(1, count + 1)),
                    f"{count} simultaneous captures: indices are contiguous and unique",
                )
                photos = sorted(capture_server.captures_root().glob(f"box{count}/*.jpg"))
                checks.equal(
                    len(photos), count, f"{count} simultaneous captures: one photo each"
                )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)


# ----------------------------------------------------------------------- the origin gate


@contextmanager
def allowed_origins_env(value):
    """Set (or clear) `PKMNSCAN_ALLOWED_ORIGINS`, restoring it on the way out.

    Restored rather than deleted for the reason `isolated_home` gives: six other tests share
    this process, and an origin list leaking out of here would be invisible until one of them
    made a request.
    """
    previous = os.environ.get(capture_server.ORIGINS_ENV)
    if value is None:
        os.environ.pop(capture_server.ORIGINS_ENV, None)
    else:
        os.environ[capture_server.ORIGINS_ENV] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(capture_server.ORIGINS_ENV, None)
        else:
            os.environ[capture_server.ORIGINS_ENV] = previous


def request(port, method, path, *, origin=None, payload=None, extra_headers=None):
    """One request against the running server. Returns `(status, body, headers)`.

    Both outcomes are collapsed here rather than one of them raising: an origin refusal is a
    403 carrying a code and a message this test asserts on, which is a result and not an
    accident. `Connection: close` because a refusal is answered BEFORE the body is read —
    the point of putting the gate there — so the bytes this client already sent are still in
    the socket, and reusing that connection would parse them as the next request line.
    """
    headers = {"Content-Type": "application/json", "Connection": "close"}
    if origin is not None:
        headers["Origin"] = origin
    # `extra_headers` exists for the conditional GET on /photo, which is the one route in
    # this server whose answer depends on a request header other than Origin.
    headers.update(extra_headers or {})
    outgoing = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(outgoing, timeout=30) as response:
            return int(response.status), response.read(), dict(response.headers)
    except urllib.error.HTTPError as refused:
        return int(refused.code), refused.read(), dict(refused.headers)


def error_code(body):
    try:
        return (json.loads(body or b"{}").get("error") or {}).get("code")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None


def check_origin_gate(checks: Checks) -> None:
    """The CSRF gate on the three mutating verbs, over real sockets.

    THIS IS THE ONLY SECURITY CONTROL IN THE REPO, and it is the only thing between a page
    the owner happens to have open in another tab and `DELETE /inventory/<box>/<index>` —
    D10's hard delete of the record, the sidecar and the photo, with no backup. Until this
    section existed it was a control nobody had watched fail.

    SOCKETS, NOT THE `do_*` FUNCTIONS. Every other server case in this file calls the route
    function directly, and not one of them can reach this: the gate lives in `_dispatch`,
    ahead of the handler, and reads a request HEADER. An in-process call has no headers, so
    the whole control is invisible from where the rest of this test stands.

    THE THREE CASES IT WOULD BE EASIEST TO GET WRONG LATER, each asserted with its reason:

      a refusal must change    the existing undo cases assert this about `undo_too_late` and
      NOTHING                  it matters more here, because the request that is refused is
                               the one a hostile page sent on purpose.
      an ABSENT `Origin`       `curl`, `./pkmnscan` and this test send none, and a browser
      must still write         page cannot omit one. Tightening this to require the header
                               kills every command-line path in the project at once, and it
                               is exactly the change that looks like hardening.
      `GET` must stay open     `GET /photo` is D6's route and both the review queue and the
                               pull preview load it as an `<img>`, which sends no `Origin`
                               at all. Narrowing the read side breaks the two screens the
                               photo service exists for and protects nothing: a read of a
                               photo of a card is not a write.
    """
    checks.note("")
    checks.note("ORIGIN GATE — CSRF allowlist on POST, PUT and DELETE")

    unknown = "http://evil.example"
    allowed = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
    second = capture_server.DEFAULT_ALLOWED_ORIGINS[1]

    checks.equal(
        capture_server.ORIGINS_ENV,
        "PKMNSCAN_ALLOWED_ORIGINS",
        "the env var is spelled PKMNSCAN_ALLOWED_ORIGINS — pinned here because the docs "
        "audit reconciles documented environment variables against real ones, and a rename "
        "would otherwise fail that check somewhere far from the code that caused it",
    )
    checks.equal(
        sorted(capture_server.DEFAULT_ALLOWED_ORIGINS),
        [
            f"http://127.0.0.1:{ports.dev_port()}",
            f"http://localhost:{ports.dev_port()}",
        ],
        "BOTH spellings of this machine are allowed by default — a browser's Origin is the "
        "literal string in the address bar, so localhost and 127.0.0.1 are the same host "
        "and not the same origin, and the owner types both — AT THE PORT THIS CHECKOUT'S "
        "APP IS ACTUALLY SERVED ON, which is the whole of D43's amendment: the list was the "
        "constant 5173 while D43 made the dev port per-checkout, so a linked worktree "
        "served an app whose every write its own server then refused",
    )
    with tempfile.TemporaryDirectory() as plain:
        checks.equal(
            ports.dev_port(Path(plain)),
            5173,
            "AND THE MAIN TREE IS UNMOVED: a root that is not a linked worktree still "
            "derives 5173, so this list is byte-identical to the constant it replaced "
            "wherever the owner actually works, and every doc naming that number stays true",
        )
    if ports.is_linked_worktree(ports.REPO_ROOT):
        checks.ok(
            "5173" not in "".join(capture_server.DEFAULT_ALLOWED_ORIGINS),
            "and a WORKTREE allows its own origin and not the main tree's — letting a page "
            "served by the main checkout write into a branch's store is the cross-tree "
            "write D43 exists to prevent, arriving through the one control meant to stop "
            "it. Pointing one tree's app at another's is already deliberate "
            "(VITE_CAPTURE_SERVER) and takes the deliberate answer: name the origin in "
            "PKMNSCAN_ALLOWED_ORIGINS",
        )
    else:
        checks.note(
            "        (the worktree case is not exercised here: this IS the main checkout, "
            "and 5173 being correct in it is exactly how the defect stayed hidden)"
        )

    with isolated_home(), allowed_origins_env(None):
        capture_server.captures_root().mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            # --- a mutating verb from an origin this server does not know ---------------
            status, body, _ = request(
                port, "POST", "/capture", origin=unknown, payload=capture_payload(3)
            )
            checks.equal(status, 403, "POST from an unknown origin is refused")
            checks.equal(
                error_code(body),
                "origin_not_allowed",
                "and it refuses in its own code, not as a routing or validation failure",
            )
            checks.ok(
                capture_server.ORIGINS_ENV in body.decode("utf-8", "replace"),
                "and the refusal names the env var to add a real app to, which is this "
                "server's copy rule reaching a message a person will read",
                body.decode("utf-8", "replace"),
            )
            checks.equal(
                Store().read().inventory.next_index(3),
                4,
                "AND THE REFUSAL CHANGED NOTHING: no index was burned",
            )
            checks.ok(
                not capture_server.photo_path(3, 4).is_file(),
                "and no photo was written — the gate runs before the body is read, so the "
                "24 MB buffer for the image was never allocated either",
            )

            status, body, _ = request(
                port,
                "PUT",
                "/inventory/3/1",
                origin=unknown,
                payload={"set_hint": "sv9"},
            )
            checks.equal(status, 403, "PUT from an unknown origin is refused")
            checks.equal(error_code(body), "origin_not_allowed", "in the same code")
            checks.ok(
                Store().read().inventory.get("3/1").set_hint is None,
                "and the recorded claim is untouched — a correction is a write, and this "
                "one never happened",
            )

            status, body, _ = request(port, "DELETE", "/inventory/3/3", origin=unknown)
            checks.equal(
                status,
                403,
                "DELETE from an unknown origin is refused — THE ONE THIS CONTROL EXISTS "
                "FOR, because the route behind it destroys a record, a sidecar and a "
                "photograph with no backup (D10)",
            )
            checks.equal(error_code(body), "origin_not_allowed", "in the same code again")
            checks.ok(
                Store().read().inventory.get("3/3") is not None
                and capture_server.photo_path(3, 3).is_file(),
                "and the card, its position and its photograph are all still there",
            )

            # --- the same verb from the capture app ------------------------------------
            status, _, _ = request(port, "DELETE", "/inventory/3/3", origin=allowed)
            checks.equal(
                status, 200, "the SAME DELETE from an allowed origin is served"
            )
            checks.ok(
                Store().read().inventory.get("3/3") is None
                and not capture_server.photo_path(3, 3).is_file(),
                "and it really did the work — so the case above is the gate refusing, not "
                "the route failing for some other reason",
            )

            # --- no `Origin` at all -----------------------------------------------------
            status, body, _ = request(port, "POST", "/capture", payload=capture_payload(3))
            checks.equal(
                status,
                201,
                "A REQUEST WITH NO `Origin` STILL WRITES. `curl`, `./pkmnscan` and this "
                "test send none, and a browser page cannot omit one — so requiring the "
                "header would kill every command-line path in this project at once while "
                "stopping nothing a page could do. Anything holding a shell here can open "
                "inventory.json with an editor anyway",
            )
            # `.get`, so a refused write is REPORTED by the line above rather than raising a
            # KeyError here that would hide every check behind it. Same rule as the label
            # read in `check_server_routes`: `Checks` exists to report every failure.
            checks.equal(
                json.loads(body or b"{}").get("key"),
                "3/3",
                "and it took the index the undo above released, which is the ordinary "
                "capture path running unchanged through the gate",
            )

            status, body, _ = request(
                port, "POST", "/capture", origin=second, payload=capture_payload(3)
            )
            checks.equal(
                status,
                201,
                "and the second spelling of this machine writes too — 127.0.0.1 and "
                "localhost are both in the default list for that reason",
            )

            # --- reads stay open --------------------------------------------------------
            status, _, headers = request(port, "GET", "/status", origin=unknown)
            checks.equal(status, 200, "GET is served to ANY origin — a read is not a write")
            status, _, headers = request(port, "GET", "/photo/3/1", origin=unknown)
            checks.equal(
                status,
                200,
                "including GET /photo, which D6's review queue and pull preview load as an "
                "`<img>` — and an `<img>` sends no Origin at all",
            )
            checks.equal(
                headers.get("Access-Control-Allow-Origin"),
                "*",
                "and it stays embeddable: an unknown origin is still answered `*` on the "
                "read side",
            )

            # --- the preflight ----------------------------------------------------------
            # The belt to the dispatcher's braces, and the half that produces a legible
            # console error rather than a 403 nobody sees: a browser told GET and OPTIONS
            # only never sends the DELETE at all.
            status, _, headers = request(port, "OPTIONS", "/inventory/3/1", origin=unknown)
            checks.equal(status, 204, "the preflight answers for any path, by design")
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.SAFE_METHODS),
                "and advertises GET and OPTIONS ONLY to an unknown origin, so the browser "
                "refuses the request that would have followed rather than sending it",
            )
            checks.equal(
                headers.get("Vary"),
                "Origin",
                "with Vary: Origin, because the answer now depends on a request header and "
                "a cache that did not know would hand one origin's answer to another",
            )

            status, _, headers = request(port, "OPTIONS", "/inventory/3/1", origin=allowed)
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.ALL_METHODS),
                "an ALLOWED origin is told every verb, including the three that write",
            )
            checks.equal(
                headers.get("Access-Control-Allow-Origin"),
                allowed,
                "and is ECHOED rather than answered `*` — `*` and credentials do not mix, "
                "and echoing is what makes the browser's own check agree with this server's",
            )
            status, _, headers = request(port, "OPTIONS", "/inventory/3/1")
            checks.equal(
                headers.get("Access-Control-Allow-Methods"),
                ", ".join(capture_server.ALL_METHODS),
                "and a preflight with no Origin is told every verb too, for the same reason "
                "the write above is served",
            )

            # --- the env var EXTENDS, and cannot re-open the door ------------------------
            lan = "http://the-mac.local:5173"
            with allowed_origins_env(f"  {lan.upper()}/  "):
                checks.equal(
                    sorted(capture_server.allowed_origins()),
                    sorted(capture_server.DEFAULT_ALLOWED_ORIGINS + (lan,)),
                    "PKMNSCAN_ALLOWED_ORIGINS EXTENDS the defaults rather than replacing "
                    "them — rebuilding the whole list from an env var would let a typo "
                    "switch the protection off while looking like configuration. Case and "
                    "a trailing slash are folded, because that is what a human types",
                )
                status, _, _ = request(
                    port, "DELETE", "/inventory/3/4", origin=lan.upper() + "/"
                )
                checks.equal(
                    status,
                    200,
                    "the added origin can write, with no restart: the list is read on every "
                    "request, and a `make server` the owner started once is the reason",
                )
                status, _, _ = request(
                    port, "POST", "/capture", origin=allowed, payload=capture_payload(3)
                )
                checks.equal(
                    status,
                    201,
                    "and the DEFAULTS still write while it is set — extended, never replaced",
                )

            with allowed_origins_env("*"):
                checks.ok(
                    unknown not in capture_server.allowed_origins(),
                    "a `*` in the env var is one more literal string in an exact-match "
                    "list, never a wildcard — nothing at all becomes allowed by it",
                    f"allowed: {capture_server.allowed_origins()}",
                )
                status, body, _ = request(
                    port, "POST", "/capture", origin=unknown, payload=capture_payload(3)
                )
                checks.equal(
                    status,
                    403,
                    "AND `*` CANNOT RE-ENABLE THE HOLE. The list is compared by exact "
                    "string, so a wildcard is one more origin nobody is ever called — a "
                    "value that silently switched this control off is the one way the env "
                    "var could undo everything above it",
                )
                checks.equal(
                    error_code(body), "origin_not_allowed", "refused in the same code"
                )

            # THREE POSTs WERE SERVED AND TWO REFUSED, and two DELETEs were served against
            # three attempted. Asserted as the positions themselves rather than as a count,
            # because a count is the one shape that can come out right for the wrong reason.
            checks.equal(
                sorted(Store().read().inventory.cards),
                ["3/1", "3/2", "3/3", "3/4"],
                "and across the whole section the box holds exactly what the SERVED "
                "requests put there — every refusal above reached neither the allocator "
                "nor the disk",
            )
            checks.equal(
                Store().read().inventory.next_index(3),
                5,
                "with the high-water mark to match: a refused capture burns no index (D10)",
            )
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)


# ------------------------------------------------------------------------- command seams


def check_photo_cache(checks: Checks) -> None:
    """`GET /photo` is a conditional request, because its URL names a SLOT, not a card.

    THE DEFECT THIS EXISTS FOR WAS FOUND FROM THE FAR END, by the owner reporting that a
    mid-box delete on `#/inventory` "doesn't kick in super quickly ... it makes you think
    you need to delete more". Measured against a copy of their real store on 2026-08-29:
    the delete answered in 288 ms and the walk redrew in 500 ms, and the screen went on
    drawing the photograph of the deleted card over the facts of its replacement. Nothing
    was slow. The response carried no `ETag`, no `Last-Modified` and no `Cache-Control`, so
    the browser reused what it had for a URL whose bytes had moved underneath it.

    THE READING THAT MAKES IT DANGEROUS RATHER THAN UNTIDY: the operator sees the same
    picture at the same position label and presses again — and the second press aims at the
    card that slid in, which is a real capture with a real photograph, and is not refused,
    because the aim check is satisfied by the freshly re-read record.

    SOCKETS, NOT THE `do_*` FUNCTION, and for `check_origin_gate`'s exact reason: the whole
    behaviour is a request header, a status code and two response headers, none of which an
    in-process call has. The in-process case up in `check_store` asserts only that a
    validator comes back at all.

    THE PHOTOS CARRY DISTINGUISHABLE BYTES, `check_remove_and_delete`'s rule, and here it is
    the entire assertion: "the browser is told the bytes changed" is only worth checking if
    the test can tell two photographs apart.
    """
    checks.note("")
    checks.note("GET /photo — the validator that survives a renumber")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        for i in (1, 2):
            capture_server.do_capture(
                {"box": 3, "capture_id": f"p{i}", "image": blob(i), "set_hint": "sv9"}
            )
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            status, body, headers = request(port, "GET", "/photo/3/1")
            first = headers.get("ETag")
            checks.equal(status, 200, "a photo answers 200 with its bytes")
            checks.equal(
                body, b"\xff\xd8\xff" + bytes([1]) * 64, "and the bytes are card 1's"
            )
            checks.ok(
                first is not None and first.startswith('"') and first.endswith('"'),
                "and a quoted strong ETag — without one a browser has nothing to ask about "
                "and reuses a slot's previous occupant",
            )
            checks.equal(
                headers.get("Cache-Control"),
                "no-cache",
                "`no-cache` and not `no-store`: keep the bytes, ask before reusing them. "
                "`no-store` would re-send 1.9 MB per arrow key on the Fulfiller's LAN",
            )

            status, body, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": first}
            )
            checks.equal(status, 304, "an unchanged photo revalidates to 304")
            checks.equal(body, b"", "and carries no body — that is what makes it cheap")

            status, _, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": f"W/{first}"}
            )
            checks.equal(
                status, 304, "the comparison is weak, as RFC 9110 requires of If-None-Match"
            )
            status, _, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": "*"}
            )
            checks.equal(status, 304, "and `*` matches any existing resource, not a tag")

            status, body, _ = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": '"stale"'}
            )
            checks.equal(status, 200, "a tag we never issued gets the bytes")
            checks.equal(len(body), 67, "all of them")

            # ------------------------------------------------------ the renumber itself
            # D10 ruling 1: deleting card 1 slides card 2 down into slot 1. The URL does not
            # change and its bytes do, which is the whole case.
            capture_server.do_remove_card(3, 1, {"capture_id": "p1"})

            status, body, headers = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": first}
            )
            checks.equal(
                status,
                200,
                "AFTER THE SHIFT THE SAME URL WITH THE SAME TAG ANSWERS 200, NOT 304 — the "
                "browser is told the slot's occupant changed, which is the defect",
            )
            checks.equal(
                body,
                b"\xff\xd8\xff" + bytes([2]) * 64,
                "and the bytes are card 2's, which slid down into slot 1",
            )
            checks.ok(
                headers.get("ETag") not in (None, first),
                "under a new ETag, so the next request revalidates against the right "
                "photograph rather than the one that was deleted",
            )
        finally:
            httpd.shutdown()
            httpd.server_close()


def check_cli_seams(checks: Checks) -> None:
    """The wiring that feeds rules T3-T5 already check.

    `pipeline/` owns the decisions and is tested. What lives in `cli/` is which column a
    value is pulled from and how a record becomes an argument — and a wrong-but-valid input
    passes every existing test while changing every answer.
    """
    checks.note("")
    checks.note("COMMAND SEAMS — cli/resolve.py")

    # THE ONE WORTH THE WHOLE SECTION. routing.cheapest is checked by T4; what is checked
    # here is that the value handed to it comes from TCG Market Price. Reading Marketplace
    # or Low instead parses cleanly, passes T4, and routes every card in every run on a
    # number that is not the card's market price.
    rows = [
        {
            tcgcsv.MARKET_PRICE_COLUMN: "2.00",
            tcgcsv.LOW_PRICE_COLUMN: "0.01",
            tcgcsv.PRICE_COLUMN: "9.99",
        },
        {
            tcgcsv.MARKET_PRICE_COLUMN: "0.75",
            tcgcsv.LOW_PRICE_COLUMN: "0.02",
            tcgcsv.PRICE_COLUMN: "8.88",
        },
    ]
    checks.equal(
        resolve.cheapest_of(rows),
        Decimal("0.75"),
        "cheapest_of reads TCG Market Price — not Marketplace, not Low (D9)",
    )

    blank = [{tcgcsv.MARKET_PRICE_COLUMN: "", tcgcsv.LOW_PRICE_COLUMN: "1.00"}]
    checks.ok(
        resolve.cheapest_of(blank) is None,
        "a blank market cell yields no price rather than zero (D9 no_market_data)",
    )

    # The candidate rows the review screen shows beside the photo (D4). Every key here is
    # read by a screen that does not exist yet, so the columns are the contract.
    candidate = resolve._candidate_rows(
        [
            {
                tcgcsv.SKU_COLUMN: "8608859",
                tcgcsv.NAME_COLUMN: "Articuno",
                tcgcsv.SET_COLUMN: "SV09",
                tcgcsv.NUMBER_COLUMN: "161/159",
                tcgcsv.CONDITION_COLUMN: "Near Mint Holofoil",
                tcgcsv.MARKET_PRICE_COLUMN: "4.20",
            }
        ]
    )
    checks.equal(
        sorted(candidate[0]),
        ["condition", "market", "name", "number", "set", "sku"],
        "a candidate row carries exactly the six fields the review screen reads",
    )
    checks.equal(candidate[0]["sku"], "8608859", "and the sku comes from TCGplayer Id")
    checks.equal(
        candidate[0]["market"], "4.20", "and market comes from TCG Market Price"
    )

    # `cli/resolve.py:load` whitelists the detected finish before handing it to the ladder.
    # If that whitelist and the enum drift, a valid finish is dropped on the floor and D3
    # rung 3 never fires — the cross-check that catches a mis-sorted card.
    #
    # THE CHECK HAS CHANGED SHAPE TWICE, BECAUSE THE DEFECT DID. It first looked for each
    # finish as a LITERAL in the source, which was right while `resolve.py` held its own copy
    # of the tuple. That copy went and the check became `finish in variant.FINISHES`.
    #
    # THEN THE ENUM STOPPED HAVING ONE HOME AND STARTED HAVING ONE PER GAME (2026-08-23), and
    # `variant.FINISHES` — Pokemon's three — became the WRONG thing for this seam to consult:
    # the model's `foil` on a Riftbound card fell out of a whitelist belonging to another
    # game and landed as `None`, losing rung 3's cross-check for every non-Pokemon card. The
    # silent drop this case exists to prevent, committed by the expression this case was
    # asserting. So the named single source is now `variant.vocabulary`, which reads the
    # game's own entry out of `pipeline/games.py`.
    #
    # What is asserted is unchanged in substance: the enum is NAMED rather than copied, and
    # no finish is spelled out beside it. T4 asserts the behaviour end to end against a
    # finish added to the registry at runtime, which is the half a source scan can never
    # reach.
    source = (Path(__file__).resolve().parents[2] / "cli" / "resolve.py").read_text("utf-8")
    checks.ok(
        "variant.vocabulary(game)" in source,
        "resolve.py tests the detected finish against THIS GAME's vocabulary, read from the "
        "registry, not against a second copy of the enum that nothing keeps in step",
        f"pokemon finishes are {variant.FINISHES}",
    )
    checks.ok(
        "finish in variant.FINISHES" not in source,
        "and the defective EXPRESSION is gone — it consulted Pokemon's enum for every game, "
        "which is the bug that lost rung 3 for Riftbound and One Piece. The token itself is "
        "allowed to survive in prose: the comment at that seam names the old test to explain "
        "what went wrong, and a check that forbade the words would forbid the explanation",
    )
    hardcoded = sorted(f for f in variant.FINISHES if f'"{f}"' in source or f"'{f}'" in source)
    checks.equal(
        hardcoded,
        [],
        "and no finish is spelled out in it at all — a literal is how the two drifted apart "
        "the first time",
    )

    # Which export a run joins against. The manifest remembers it so later commands do not
    # need it again; with neither flag nor memory the command refuses and says what to pass.
    with tempfile.TemporaryDirectory() as tmp:
        recorded = runs.Run(
            directory=Path(tmp), manifest={"export": {"path": f"{tmp}/sv09.csv"}}
        )
        checks.equal(
            resolve.export_for(recorded, None),
            Path(f"{tmp}/sv09.csv"),
            "export_for falls back to the export the manifest recorded",
        )
        checks.equal(
            resolve.export_for(recorded, f"{tmp}/other.csv"),
            Path(f"{tmp}/other.csv"),
            "and an explicit --export overrides it",
        )
        caught = checks.raises(
            runs.RunError,
            lambda: resolve.export_for(runs.Run(directory=Path(tmp), manifest={}), None),
            "a run with no export recorded and no flag REFUSES rather than guessing",
        )
        if caught is not None:
            checks.ok(
                "--export" in str(caught),
                "and the refusal names the flag to pass",
                f"message was: {caught}",
            )


# ------------------------------------------------------------------- the code ledger (C8)


def check_code_ledger(checks: Checks) -> None:
    """C8's dispute flow: the transcribed code beside the photograph it was read from.

    A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS, and every string below is
    an INVENTED code shape in a scratch store — nothing here touches a real card, a real
    ledger, or a tracked file. Three seams, each asserted where it lives:
    `store/files.py:upsert_jsonl`, which keeps "one line per code card" literally true
    across re-identifications; `cli/cmd_identify.py:_code_ledger_lines`, which decides what
    earns a line and what is skipped BY NAME; and the record seam in `run`, which writes
    the PARSER's fields onto the card rather than the raw payload's keys — for a code card
    that is C8's whole mechanism, because the code lands in `number`, `number` is a column
    `GET /search` matches, and the dispute lookup is therefore the existing search.

    THE TRANSPORT IS A FAKE AND IT IS THE ONLY FAKE. `identify` is the one command that
    costs money, so `batch.run_batch` is swapped for a stub that answers each request under
    its own strategy — everything on either side of that seam is the real code: the sidecar
    scan, the cache, the record write, the ledger upsert. Nothing here submits anything.
    """
    checks.note("")
    checks.note("CODE LEDGER — store/files.py, cli/cmd_identify.py, GET /search")

    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import images as identify_images

    # 3-4-3-3, with a `?` for a character the model could not read and a lowercase letter
    # that `normalize_number` would have folded — the two properties the parser must keep.
    code = "GXR-7Q?d-K3M-9TT"

    # ------------------------------------------------------ upsert_jsonl, the index shape
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "codes.jsonl"
        first = [
            {"box": 9, "index": 1, "code": "AAA-1111-AAA-111"},
            {"box": 9, "index": 2, "code": "BBB-2222-BBB-222"},
            {"box": 10, "index": 1, "code": "CCC-3333-CCC-333"},
        ]
        files.upsert_jsonl(path, first, ("box", "index"))
        checks.equal(
            files.read_jsonl(path),
            first,
            "upsert_jsonl writes new keys in the order given",
        )
        corrected = {"box": 9, "index": 2, "code": "BBB-2222-BBB-999", "run": "second"}
        appended = {"box": 11, "index": 1, "code": "DDD-4444-DDD-444"}
        files.upsert_jsonl(path, [corrected, appended], ("box", "index"))
        checks.equal(
            files.read_jsonl(path),
            [first[0], corrected, first[2], appended],
            "a re-identified card REPLACES its own line IN PLACE — order kept, new keys "
            "appended — so `one line per code card` stays literally true and a lookup "
            "needs no last-line-wins rule",
        )
        checks.equal(
            len(path.read_text("utf-8").splitlines()),
            4,
            "four keys, four lines: the file is an INDEX, not a log",
        )
        before = path.read_bytes()
        files.upsert_jsonl(path, [corrected], ("box", "index"))
        checks.equal(
            path.read_bytes(), before, "and re-upserting the same line is idempotent"
        )

    # ------------------------------------------- _code_ledger_lines: what earns a line
    def code_item(photo: str, box, index, raw, *, parsed: bool) -> cmd_identify.Item:
        capture = sidecar.Capture(
            photo=Path(photo), box=box, index=index, set_hint="JTG", game="pokemon_code"
        )
        item = cmd_identify.Item(capture=capture, identification=raw)
        cmd_identify._attach_registry(item)
        if parsed and raw is not None:
            item.parsed = prompt.parse(dict(raw), item.strategy)
        return item

    fresh = code_item(
        "/caps/5-001.jpg",
        5,
        1,
        {"code": code, "name": "Journey Together", "confidence": "high"},
        parsed=True,
    )
    # `parsed` stays None on a cache hit — the payload was parsed on the run that paid for
    # it — so the cached card is the branch that re-parses under the card's own strategy.
    cached = code_item(
        "/caps/5-002.jpg",
        5,
        2,
        {"code": "MMM-5555-MMM-555", "name": "Surging Sparks", "confidence": "medium"},
        parsed=False,
    )
    broken = code_item(
        "/caps/5-003.jpg", 5, 3, {"code": "NNN-6666-NNN-666"}, parsed=False
    )
    blank = code_item(
        "/caps/5-004.jpg",
        5,
        4,
        {"code": "", "name": "Journey Together", "confidence": "low"},
        parsed=True,
    )
    homeless = code_item(
        "/caps/loose.jpg",
        None,
        None,
        {"code": "PPP-7777-PPP-777", "name": "", "confidence": "high"},
        parsed=True,
    )
    pokemon_item = cmd_identify.Item(
        capture=sidecar.Capture(photo=Path("/caps/5-006.jpg"), box=5, index=6),
        identification={"name": "Eiscue", "number": "044", "printed_total": "167"},
    )
    cmd_identify._attach_registry(pokemon_item)

    stamps = {"5/1": "2026-08-23T10:00:00.000Z", "5/2": "2026-08-23T10:00:01.000Z"}
    lines, skipped = cmd_identify._code_ledger_lines(
        [fresh, cached, broken, blank, homeless, pokemon_item],
        "run-t7",
        lambda key: stamps.get(key),
    )
    checks.equal(
        [(line["box"], line["index"], line["code"]) for line in lines],
        [(5, 1, code), (5, 2, "MMM-5555-MMM-555")],
        "a line per code the run holds: the fresh read AND the cached one — a cached "
        "card's answer was already paid for, and re-upserting its line is what heals a "
        "ledger file that was lost, since inventory/ is never in git and nothing else "
        "would re-create it",
    )
    if lines:
        checks.equal(
            lines[0],
            {
                "box": 5,
                "index": 1,
                "code": code,
                "name": "Journey Together",
                "photo": "/caps/5-001.jpg",
                "set_hint": "JTG",
                "captured_at": "2026-08-23T10:00:00.000Z",
                "confidence": "high",
                "run": "run-t7",
            },
            "and the line is the dispute flow's whole index entry — code text beside the "
            "position its photograph is keyed by, the `?` the model wrote for a doubtful "
            "character SURVIVING to the ledger, where it says exactly which character the "
            "owner's re-read should doubt",
        )
    checks.equal(len(skipped), 3, "three cards earn no line, each skipped BY NAME")
    for needle, why in (
        (
            "loose.jpg: no position",
            "a positionless card has no key to file a line under — and it is not "
            "silently dropped: it is already loudly queued as no_position, the stronger "
            "guarantee",
        ),
        (
            "5/4: the model read no code",
            "an empty transcription has nothing to look a dispute up by",
        ),
        (
            "5/3: cached answer does not parse",
            "a cached payload the profile's schema has moved under is named, never "
            "guessed at — re-identifying it is the remedy",
        ),
    ):
        checks.ok(any(needle in line for line in skipped), why, f"skipped: {skipped!r}")
    checks.ok(
        all("5/6" not in line for line in skipped),
        "and the Pokemon card is in NEITHER list — the ledger is pokemon_code's alone",
        f"skipped: {skipped!r}",
    )

    # --------------------------- the record seam and both ledger files, through `run`
    with isolated_home() as home:
        caps = Path(home) / "code-caps"
        caps.mkdir()
        for name in ("6-001.jpg", "6-002.jpg"):
            identify_images.Image.new("RGB", (64, 89), (200, 40, 40)).save(
                caps / name, "JPEG"
            )
        (caps / "6-001.json").write_text(
            json.dumps(
                {"box": 6, "position": 1, "game": "pokemon_code", "set_hint": "JTG"}
            ),
            "utf-8",
        )
        (caps / "6-002.json").write_text(
            json.dumps({"box": 6, "position": 2, "game": "misc"}), "utf-8"
        )

        payload_by_strategy = {
            "pokemon_code_v1": {
                "code": code,
                "name": "Journey Together",
                "confidence": "high",
            },
            "misc_card_v1": {
                "name": "Dark Magician",
                "printed_id": "sdy-006",
                "detected_game": "yugioh",
                "language": "English",
                "confidence": "high",
            },
        }
        transported: list = []

        def fake_run_batch(requests, log=None, on_submit=None):
            outcomes = {}
            for request in requests:
                transported.append(request.custom_id)
                raw = dict(payload_by_strategy[request.strategy])
                outcomes[request.custom_id] = batch.Outcome(
                    request.custom_id,
                    batch.SUCCEEDED,
                    identification=prompt.parse(raw, request.strategy),
                )
            return batch.BatchRun(outcomes=outcomes)

        real_run_batch = cmd_identify.batch.run_batch
        cmd_identify.batch.run_batch = fake_run_batch
        try:
            with quiet():
                exit_code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(["identify", str(caps)]),
                    lambda *a: None,
                )
            checks.equal(exit_code, 0, "`pkmnscan identify` exits 0 over the stub transport")
            checks.equal(
                len(transported), 2, "which was asked for exactly the two photographs"
            )

            recorded = Store().read().inventory
            checks.equal(
                recorded.get("6/1").number,
                code,
                "THE RECORD SEAM WRITES THE PARSER'S FIELDS: a pokemon_code payload has "
                "no `number` key at all, and the transcribed `code` lands in Card.number "
                "with its `?` and its case exactly as transcribed — never "
                "normalize_number-folded, because there is no catalog key here and "
                "`exactly as printed` is the whole instruction the field was authored "
                "under",
            )
            checks.equal(
                recorded.get("6/1").printed_total,
                "",
                "and printed_total stays empty: no join key CAN be built from a "
                "redemption code, so has_number stays honestly False",
            )
            checks.equal(
                recorded.get("6/2").number,
                "sdy-006",
                "a misc payload lands its `printed_id` through the same seam, case kept "
                "— reading .get('number') off the raw payload instead would write a "
                "record only Pokemon's profile could ever fill",
            )

            standing = files.read_jsonl(files.codes_ledger_path())
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in standing],
                [(6, 1, code)],
                "the standing index holds ONE line — the code card's; the misc card is "
                "not the ledger's business",
            )
            run_dirs = [d for d in sorted(files.runs_dir().iterdir()) if d.is_dir()]
            run_copy = (
                files.read_jsonl(run_dirs[0] / files.CODES_LEDGER_NAME) if run_dirs else []
            )
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in run_copy],
                [(6, 1, code)],
                "and the run directory carries its own deletable copy — runs/ is "
                "derived, inventory/ is the master",
            )

            # The heal: C8's argument for including a cached card, run for real.
            files.codes_ledger_path().unlink()
            sent_before = len(transported)
            with quiet():
                exit_code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(["identify", str(caps)]),
                    lambda *a: None,
                )
            checks.equal(exit_code, 0, "a second identify over the same directory exits 0")
            checks.equal(
                len(transported),
                sent_before,
                "and pays for NOTHING — every answer is a cache hit, so the transport is "
                "never called again",
            )
            healed = files.read_jsonl(files.codes_ledger_path())
            checks.equal(
                [(line["box"], line["index"], line["code"]) for line in healed],
                [(6, 1, code)],
                "yet the DELETED standing index is re-created whole from the cached "
                "answer, parsed again under the card's own strategy — the heal is why a "
                "cached code card is included at all",
            )
        finally:
            cmd_identify.batch.run_batch = real_run_batch

    # ------------------------------------------- the dispute lookup is GET /search
    with isolated_home():
        capture_server.do_capture(
            capture_payload(7, game="pokemon_code", set_hint="JTG")
        )
        capture_server.do_capture(capture_payload(7))
        with Store().write() as snapshot:
            pooled = snapshot.inventory.cards["7/1"]
            pooled.name = "Journey Together"
            pooled.number = code
            pooled.sku = "424242"
            # The recorded field nulled while the FILE stays on disk — the shape a record
            # written by `emit` rather than a capture has, and the case that tells the
            # stat apart from `bool(card.photo)`. With both set, a field-reading mutant
            # answers True for the wrong reason and the assertion below proves nothing.
            pooled.photo = None
            decoy = snapshot.inventory.cards["7/2"]
            decoy.sku = "555"
            decoy.name = "Eiscue"
            decoy.note = f"traded beside {code}"

        found = capture_server.do_search(code)["groups"]
        checks.equal(
            [group["sku"] for group in found],
            ["424242", "555"],
            "the exact code string RANKS ITS CARD FIRST — C8's lookup is the existing "
            "search with zero new UI, and exact-on-number outranks the substring match a "
            "chatty note also earns",
        )
        if len(found) == 2:
            group = found[0]
            checks.equal(
                group["number"],
                code,
                "the group answers the code as its number, `?` and case intact",
            )
            copy = group["copies"][0] if group["copies"] else {}
            checks.equal(copy.get("key"), "7/1", "with the code card as its one copy")
            checks.ok(
                copy.get("has_photo") is True,
                "which answers has_photo — the STAT, against a record whose photo field "
                "is null while the file is on disk, so the screen requests GET /photo "
                "and the owner is two taps from the re-read C8 exists for",
            )
            place = copy.get("place") or {}
            checks.ok(
                place.get("located") is False
                and place.get("label") is None
                and place.get("neighbors") is None
                and place.get("section_gaps") is None,
                "and a POOLED place — D24's ruling: a code card is a count, not a slot, "
                "so no label, no neighbours, no gaps, and null rather than zero for the "
                "gap count because `no section at all` is a different fact from `a "
                "countable section with no holes`",
                f"place: {place!r}",
            )
            checks.equal(
                place.get("game"),
                "pokemon_code",
                "stamped with its game, so the screen knows why there is no label",
            )


# -------------------------------------------------- the printed-code profiles (D21, D25)


RIFTBOUND_EXPORT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "riftbound_export_untouched.csv"
)
ONE_PIECE_EXPORT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "onepiece_export_untouched.csv"
)


# --------------------------------------------------------------- the review catalog lookup


def check_review_catalog(checks: Checks) -> None:
    """GET /review/<box>/<index>/catalog and D46's answer path — the card with no rows.

    ITS OWN ISOLATED HOME, this file's standing lesson: it answers a card, which clears queue
    entries and writes history lines the blocks around it count over stores they build by hand.

    THE DEAD END THIS CLOSES. A queue entry with no candidates could not be answered at all —
    `do_review_answer` refuses it as `no_candidates` — so the only moves were skip, which
    writes nothing and asks again next session, and D37's stand-down, which closes the question
    rather than answering it. The row was usually in the export the whole time: box 1's
    `Master Yi, Wuju Master` was read as `Wuju Master`, dropping the champion, so no exact
    match could find it and the photograph was perfectly good.

    THE GUARD IS NARROWED, NOT REMOVED, AND THAT IS WHAT MOST OF THIS BLOCK ASSERTS. A bare
    SKU still refuses. The flag only reaches an entry with NO candidates. The SKU is re-read
    out of THIS CARD'S OWN export inside the write lock, so an unknown one refuses and a
    condition the client invented is discarded rather than believed.
    """
    checks.note("")
    checks.note("REVIEW CATALOG — GET /review/<box>/<index>/catalog, and D46's answer")

    with isolated_home() as home:
        # A run holding the riftbound export, exactly as an app-driven join leaves it: the
        # bytes INSIDE the run, and the manifest naming that copy.
        run_dir = home / "runs" / "2026-08-29-box1-01"
        run_dir.mkdir(parents=True)
        shutil.copy(RIFTBOUND_EXPORT, run_dir / "export.csv")
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": "2026-08-29T22:37:47+00:00",
                    "joined": True,
                    "exports": {"riftbound": {"path": str(run_dir / "export.csv")}},
                }
            )
        )

        for _ in range(3):
            capture_server.do_capture(capture_payload(1, game="riftbound"))
        with Store().write() as snapshot:
            for key in ("1/1", "1/2", "1/3"):
                snapshot.inventory.set_state(key, master.IDENTIFIED)
                snapshot.inventory.cards[key].game = "riftbound"
            # The live case: the champion dropped, no number read, no candidate rows.
            snapshot.inventory.cards["1/1"].run = "2026-08-29-box1-01"
            snapshot.review.upsert(
                entry(
                    1,
                    1,
                    candidates=[],
                    reason="no_catalog_row",
                    read={"name": "Wuju Master", "number": None},
                )
            )
            # Records no run at all — a card identified before `run` was written.
            snapshot.review.upsert(entry(1, 2, candidates=[], reason="no_catalog_row"))
            # Has candidates of its own, so the catalog path must never reach it.
            snapshot.inventory.cards["1/3"].run = "2026-08-29-box1-01"
            snapshot.review.upsert(entry(1, 3, market="12.00"))

        # --- the lookup ---

        found = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, ""),
            "an empty query suggests from the card's own read, which is the arriving case",
        )
        if found is not None:
            names = [str(row["name"]) for row in found["rows"]]
            checks.ok(
                "Master Yi, Wuju Master" in names,
                "D46: the row the pipeline could not find is offered — the read dropped the "
                "champion, so only a substring match recovers it",
            )
            checks.equal(
                found["game"],
                "riftbound",
                "D46: and it is looked up as the game the CARD records, not the default",
            )

        typed = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, "191/219"),
            "a typed collector number searches the same export",
        )
        if typed is not None:
            checks.ok(
                any(str(row["number"]) == "191/219" for row in typed["rows"]),
                "D46: a number finds its row",
            )

        empty = answers(
            checks,
            lambda: capture_server.do_review_catalog(1, 1, "zzz not a card"),
            "a query matching nothing answers with no rows",
        )
        if empty is not None:
            checks.equal(
                (len(empty["rows"]), empty["found"]),
                (0, 0),
                "D46: and it does NOT guess — an empty result is an empty result",
            )

        refusal(
            checks,
            lambda: capture_server.do_review_catalog(9, 99, ""),
            "card_not_found",
            "a lookup for a card that does not exist refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_catalog(1, 2, ""),
            "no_run_recorded",
            "a card with no run has no export to look in, and says so rather than guessing "
            "which run on disk might have been the one",
        )

        # --- the answer, and the guard that stays standing ---

        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1, 1, {"sku": "9192027", "condition": "Near Mint Foil"}
            ),
            "no_candidates",
            "WITHOUT the flag a zero-candidate entry still refuses — D46 narrows this guard "
            "and does not remove it",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                1,
                {"sku": "0000000", "condition": "Near Mint Foil", "from_catalog": True},
            ),
            "sku_not_in_catalog",
            "a SKU the export does not carry refuses even WITH the flag — the row is re-read "
            "server-side, so this is never a free-text write",
        )

        before = Store().read().inventory.cards["1/1"].sku
        checks.ok(before is None, "and neither refusal wrote anything")

        answered = answers(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                1,
                # A DELIBERATELY WRONG CONDITION. The server takes the row's own, so this is
                # discarded rather than validated — a client that sends the wrong one gets the
                # right one, which is what makes the SKU the only thing the request decides.
                {"sku": "9192027", "condition": "TOTAL NONSENSE", "from_catalog": True},
            ),
            "a catalog-verified row answers the card",
        )
        if answered is not None:
            checks.equal(
                answered["condition"],
                "Near Mint Foil",
                "D46: and the CONDITION comes off the export row, never off the request",
            )

        stored = Store().read()
        card = stored.inventory.cards["1/1"]
        checks.equal(
            (card.sku, card.condition),
            ("9192027", "Near Mint Foil"),
            "the pair lands on the card, which is what a later join reads back as D3 rung 0",
        )
        checks.ok(
            stored.review.entries["1/1"].cleared_by_human,
            "and the queue entry is cleared, so the question stops being asked",
        )
        line = [
            event
            for event in Store().history()
            if event.get("event") == "answered" and event.get("position") == "1/1"
        ]
        checks.ok(
            bool(line) and line[-1].get("from_catalog") is True,
            "D46: the history line records that a HUMAN found this row rather than the "
            "pipeline — after the write there is no other evidence which happened",
        )

        # --- the flag reaches nothing it should not ---

        refusal(
            checks,
            lambda: capture_server.do_review_answer(
                1,
                3,
                {"sku": "9192027", "condition": "Near Mint Foil", "from_catalog": True},
            ),
            "sku_not_a_candidate",
            "an entry WITH candidates is unaffected by the flag: it still answers only from "
            "the rows it was offered, which is the laundering guard D46 must not reach",
        )


def check_review_stand_down(checks: Checks) -> None:
    """POST /review/<box>/<index>/stand-down — D37, closing a question without answering it.

    ITS OWN ISOLATED HOME, this file's standing lesson: it clears queue entries, and the
    blocks around it count entries and history lines over stores they build by hand.

    THE CONTROL docs/DESIGN.md ASKED FOR BY NAME. That file has carried Skip as an OPEN
    QUESTION since the review screen was built — *"the screen needs a real defer that records
    a reason, and that is a decision entry rather than a button"* — and the owner pulled the
    trigger on 2026-08-25 asking for a stand-down on a wasted position.

    THE ASSERTION THAT CARRIES THE FEATURE IS THAT THE CARD IS UNTOUCHED. An answer writes a
    SKU and a condition; a retirement writes a terminal state; this writes NEITHER, and if it
    ever does it has silently become one of the other two.
    """
    checks.note("")
    checks.note("STAND DOWN — POST /review/<box>/<index>/stand-down")

    with isolated_home():
        for _ in range(4):
            capture_server.do_capture(capture_payload(3))
        with Store().write() as snapshot:
            for key in ("3/1", "3/2", "3/3", "3/4"):
                snapshot.inventory.set_state(key, master.IDENTIFIED)
            snapshot.review.upsert(entry(3, 1, market="12.00"))
            # No candidates — the case that CANNOT be answered at all, and the one the owner
            # was looking at: a black frame, a hallucinated read, no catalog row.
            snapshot.review.upsert(
                entry(3, 2, candidates=[], reason="no_catalog_row")
            )
            # In both files, so the both-queues clearing is exercised.
            snapshot.review.upsert(entry(3, 3, market="12.00"))
            snapshot.parked.upsert(entry(3, 3, market="0.05"))
            # 3/4 is identified and in no queue at all.

        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 1, {}),
            "reason_required",
            "a stand-down with no reason refuses — docs/DESIGN.md asked for a defer that "
            "RECORDS a reason, so a reasonless one is not the feature",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 1, {"reason": "because"}),
            "stand_down_reason_invalid",
            "a reason outside the vocabulary refuses rather than being recorded verbatim",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(
                3, 1, {"reason": "pulled"}
            ),
            "stand_down_reason_invalid",
            "and a RETIRE reason is refused here — those four say the card left inventory, "
            "which is the one thing a stand-down must never be recorded as",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(
                3, 1, {"reason": "wasted_position", "undo": True}
            ),
            "field_not_settable",
            "a reversal carrying a reason refuses rather than obeying with the reason ignored",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 4, {"reason": "not_listing"}),
            "not_in_queue",
            "a card in no queue has no question to stand down from",
        )

        # --- the write itself, on the card that cannot be answered --------------------
        before = Store().read().inventory.cards["3/2"]
        was = (before.state, before.sku, before.condition)

        body = capture_server.do_review_stand_down(3, 2, {"reason": "wasted_position"})
        checks.equal(body["stood_down"], True, "the stand-down reports itself")
        checks.equal(body["undone"], False, "and which direction it went")
        checks.equal(body["reason"], "wasted_position", "and echoes the reason recorded")
        checks.equal(
            body["queue_reason"],
            "no_catalog_row",
            "and the QUEUE's own reason beside the operator's — two different strings that "
            "both matter, and the pair is what makes the log answerable to 'which questions "
            "get waved off, and why'",
        )

        snapshot = Store().read()
        checks.ok(
            snapshot.review.entries["3/2"].cleared_by_human,
            "the entry is cleared, so `Queue.upsert` will not re-ask on any later run",
        )
        after = snapshot.inventory.cards["3/2"]
        checks.equal(
            (after.state, after.sku, after.condition),
            was,
            "AND THE CARD IS UNTOUCHED — no sku, no condition, no state. This is the whole "
            "feature: if this ever fails, a stand-down has quietly become an answer or a "
            "retirement",
        )
        checks.ok(
            any(
                event.get("event") == "stood_down" and event.get("position") == "3/2"
                for event in Store().history()
            ),
            "and a `stood_down` line is on the log — the only place the reason survives",
        )
        checks.ok(
            "stood_down" not in master.STATES,
            "`stood_down` is an event and never a state, which T7 asserts for every event "
            "name here: a state would make months of these parse as card states",
        )

        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 2, {"reason": "not_listing"}),
            "already_cleared",
            "a second stand-down refuses rather than re-writing a settled question",
        )

        # --- both queues, one press ---------------------------------------------------
        capture_server.do_review_stand_down(3, 3, {"reason": "cannot_settle"})
        both = Store().read()
        checks.ok(
            both.review.entries["3/3"].cleared_by_human
            and both.parked.entries["3/3"].cleared_by_human,
            "a position held in BOTH files is cleared in both — clearing one would leave the "
            "screen still showing a card whose question is closed",
        )

        # --- the reversal --------------------------------------------------------------
        back = capture_server.do_review_stand_down(3, 2, {"undo": True})
        checks.equal(back["undone"], True, "the reversal reports itself")
        checks.ok(
            not Store().read().review.entries["3/2"].cleared_by_human,
            "and the entry is waiting again",
        )
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 2, {"undo": True}),
            "not_stood_down",
            "a second reversal refuses — the first reopened the entry, so nothing has to "
            "remember that a reversal happened",
        )

        # --- THE GUARD THAT MATTERS MOST -----------------------------------------------
        # An ANSWERED card must not be reopened through this control. Observed failing
        # against a draft whose reversal only checked `cleared_by_human`.
        answered = {"sku": CANDIDATES[1]["sku"], "condition": CANDIDATES[1]["condition"]}
        capture_server.do_review_answer(3, 1, answered)
        refusal(
            checks,
            lambda: capture_server.do_review_stand_down(3, 1, {"undo": True}),
            "not_stood_down",
            "a card closed by an ANSWER refuses this reversal — taking back a real "
            "identification through the un-dismiss control is the one thing it must not do",
        )
        still = Store().read().inventory.cards["3/1"]
        checks.equal(
            still.sku,
            answered["sku"],
            "and the answer is still on the card after that refusal",
        )


def check_run_realignment(checks: Checks) -> None:
    """D36 — a run's slot numbers are re-bound to the photographs they were taken from.

    ITS OWN ISOLATED HOME, which is this file's own lesson for the fourth time: this block
    writes photographs into a box, and the blocks above count records and history lines over
    boxes they build card by card.

    THE DEFECT: a run directory is immutable (`cli/runs.py`) and the store is not. D10 ruling 1
    lets a junk capture be deleted from the middle of a box, sliding every higher card down one
    slot; the store remaps records, photographs, sidecars and both queue files and writes a
    `renumbered` event. The run cannot be remapped — it is a record of a past event — so
    re-joining a box edited since it was identified paired every card with its NEIGHBOUR's
    slot, photograph and label. Measured on box 2, 2026-08-24: card `2/7` deleted, 537 cards
    shifted, and a re-join wrote all 47 queue entries one position off.

    Every case below was observed FAILING against the unguarded loader before it was kept.
    """
    def build(bodies, names):
        return {
            "cards": {
                f"2/{i}": {
                    "box": 2,
                    "index": i,
                    "photo": f"captures/cards/box2/{i:04d}.jpg",
                    "photo_sha256": hashlib.sha256(body).hexdigest(),
                    "identification": {"name": names[i], "confidence": "high"},
                }
                for i, body in bodies.items()
            }
        }

    with isolated_home() as home:
        box = home / "captures" / "cards" / "box2"
        box.mkdir(parents=True)
        bodies = {i: f"photo-of-card-{i}".encode() for i in (1, 2, 3, 4)}
        names = {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta"}
        for i, body in bodies.items():
            (box / f"{i:04d}.jpg").write_bytes(body)
        original = build(bodies, names)

        # 1. Nothing has moved: the payload comes back as the SAME OBJECT, which is what keeps
        #    a healthy run's join byte-for-byte identical.
        same, moved, departed, unverified = resolve.realign(original)
        checks.ok(same is original, "D36: an unmoved run's payload is returned untouched")
        checks.equal(moved, {}, "D36: and nothing is reported as moved")
        checks.equal(departed, [], "D36: and nothing as departed")
        checks.equal(unverified, [], "D36: and the box counts as verified")

        # 2. Card 2 is deleted mid-box and 3, 4 slide down — exactly D10 ruling 1.
        (box / "0002.jpg").write_bytes(bodies[3])
        (box / "0003.jpg").write_bytes(bodies[4])
        (box / "0004.jpg").unlink()
        rebound, moved, departed, unverified = resolve.realign(original)
        checks.equal(
            moved,
            {"2/3": "2/2", "2/4": "2/3"},
            "D36: cards behind a mid-box delete re-bind to the slot their photograph is in now",
        )
        checks.equal(
            departed, ["2/2"], "D36: and the deleted card is reported departed, not joined"
        )
        checks.equal(
            sorted(rebound["cards"]),
            ["2/1", "2/2", "2/3"],
            "D36: the rebound payload holds the surviving cards at their new slots",
        )
        checks.equal(
            rebound["cards"]["2/2"]["identification"]["name"],
            "Gamma",
            "D36: and the READ travels with its photograph — the whole point, since the old "
            "loader left Gamma's name on Beta's slot and Beta's photograph",
        )
        checks.equal(
            rebound["cards"]["2/2"]["index"],
            2,
            "D36: `index` is rewritten too, not only the key — the position label is built from it",
        )
        # OBSERVED FAILING FIRST, and found on the screen rather than here: the entry read
        # `Mewtwo ex` and rendered `0096.jpg`, a photograph of a different card. `queue_entry`
        # carries this path onto the queue entry verbatim and the review screen renders exactly
        # it, so a rebound record keeping its old path shows the slot's PREVIOUS occupant —
        # this function's own defect, surviving one field deeper.
        checks.equal(
            rebound["cards"]["2/2"]["photo"],
            "captures/cards/box2/0002.jpg",
            "D36: and so is `photo` — the review screen renders that path verbatim",
        )
        checks.equal(
            original["cards"]["2/3"]["index"], 3, "D36: and the run's own payload is not mutated"
        )

        # 3. One photograph at two slots is a question, not an answer.
        (box / "0004.jpg").write_bytes(bodies[3])
        try:
            resolve.realign(original)
            checks.ok(False, "D36: a duplicated photograph must refuse")
        except runs.RunError as refusal:
            checks.ok(
                "more than one slot" in str(refusal),
                "D36: a photograph at two slots refuses rather than picking one",
            )
        (box / "0004.jpg").unlink()

        # 4. A BOX WITH NO PHOTOGRAPHS IS UNVERIFIED, NOT EMPTIED. The first draft of this
        #    declared all 53 of box 1's cards departed, because box 1's photographs had been
        #    deleted while its records lived on — which inverts what the check means. Absence
        #    of photographs is absence of evidence, not evidence of absent cards.
        for photo in box.glob("*.jpg"):
            photo.unlink()
        blind, moved, departed, unverified = resolve.realign(original)
        checks.ok(
            blind is original, "D36: a box with no photographs on disk passes through untouched"
        )
        checks.equal(departed, [], "D36: and NONE of its cards are called departed")
        checks.equal(unverified, [2], "D36: the box is reported unverified instead")

        # 5. TWO RECORDS ON ONE SLOT REFUSE, and this is the disk check's missing twin.
        #    Case 3 above catches one PHOTOGRAPH at two slots. Nothing caught two RECORDS
        #    carrying one digest: both resolve through `at` to the same position and then
        #    collide in the rebuilt payload, where the second write wins.
        #
        #    OBSERVED FAILING FIRST, on exactly this fixture: two cards in, ONE card out,
        #    `departed` empty and nothing printed. A silent drop, inside the function written
        #    to prevent one, which `CLAUDE.md` forbids outright.
        #    A FRESH BOX inside the same home: box 2's photographs were deleted by case 4
        #    above, and re-creating them would re-open assertions already made over them.
        nine = home / "captures" / "cards" / "box9"
        nine.mkdir(parents=True)
        (nine / "0002.jpg").write_bytes(b"one-photo")
        digest = hashlib.sha256(b"one-photo").hexdigest()
        twins = {
            "cards": {
                "9/1": {"box": 9, "index": 1, "photo_sha256": digest, "photo": "a.jpg"},
                "9/3": {"box": 9, "index": 3, "photo_sha256": digest, "photo": "b.jpg"},
            }
        }
        try:
            resolve.realign(twins)
            checks.ok(False, "D36: two records landing on one slot must refuse")
        except runs.RunError as refusal:
            checks.ok(
                "more than one record" in str(refusal),
                "D36: two records claiming one slot refuse rather than one being dropped",
            )
            checks.ok("9/2" in str(refusal), "D36: and the contested slot is named")

        # 6. A POSITIONLESS KEY SURVIVES A REALIGN INSTEAD OF CRASHING IT.
        #    `identify/sidecar.py` keys a capture with no position as `file:<name>` — the
        #    documented shape for a directory of photographs with no sidecars. It is never
        #    in `by_box`, so it can never move, but the rebuild walks EVERY card: one
        #    stray key used to raise an unhandled ValueError the moment anything else in
        #    its box shifted, taking `join` and `emit` down for that run permanently.
        #    OBSERVED FAILING FIRST: `ValueError: not enough values to unpack`.
        stray = {
            "cards": {
                "file:stray.jpg": {"name": "Stray", "photo": "stray.jpg"},
                "9/1": {"box": 9, "index": 1, "photo_sha256": digest, "photo": "a.jpg"},
            }
        }
        out, moved, departed, unverified = resolve.realign(stray)
        checks.ok(
            "file:stray.jpg" in out["cards"],
            "D36: a positionless key passes through a realign untouched",
        )
        checks.equal(
            moved, {"9/1": "9/2"}, "D36: and the card that really moved is still re-bound"
        )


def check_printed_code_profiles(checks: Checks) -> None:
    """`riftbound_card_v1` and `one_piece_card_v1`: the wiring, and the one seam that lies.

    WHAT THIS ASSERTS AND WHAT IT CANNOT. It asserts that a model answer shaped like these
    two profiles' schemas survives every hop between the API and a catalog row — the
    parser, the raw payload written into `identifications.json`, `cli/resolve.py`'s read of
    that payload, the per-game join key, and the fold on both sides of the match. It says
    NOTHING about whether a model can read a Riftbound or One Piece card, because this
    repo holds no photograph of either: there is no eval set, no T1 score, and no accuracy
    figure for either profile. Same standing as T6's synthetic composites — self-consistent
    over a wider range than the evidence covers.

    THE SEAM THAT LIES IS THE FIELD NAME, and it is why this section reaches all the way to
    a real export instead of stopping at `parse`. `cli/resolve.py` reads the RAW model
    payload back out of the run — `identification.get("number")` — and never calls
    `prompt.parse`. So a schema that called this field `printed_code`, or copied misc's
    `printed_id`, would parse perfectly, write a perfectly good record, and then hand the
    join a card with no number at all: every card in the run back as `no_catalog_row`,
    blaming the export. Nothing short of the round trip below can see that, and the
    temptation to rename the field is permanent, because `printed_code` is what the
    registry's `join_key` calls the same idea one file over.

    THE EXPORTS ARE THE REAL ONES AND THE PRICES ARE WHY. Every identifier below is a cell
    that exists, and the pairs are chosen so that dropping a single character lands on a
    different real SKU at a different real price: `066a/298` ($8.89) against `066/298`,
    `303*/298` ($3,420.28) against `303/298` ($384.31). An invented fixture would assert
    that this code is consistent with itself.
    """
    checks.note("")
    checks.note("PRINTED-CODE PROFILES — identify/prompt.py, cli/resolve.py, the join key")

    # ------------------------------------------------- the registry <-> profile seam
    #
    # BOTH DIRECTIONS, because the two files are reconciled at import in one direction only
    # (a registry name with no profile stops the process; a profile no entry names does
    # not). The half that is not checked at import is the half asserted here: the entry
    # still names the profile that was written FOR it.
    for game, strategy in (
        ("riftbound", "riftbound_card_v1"),
        ("one_piece", "one_piece_card_v1"),
    ):
        entry = games.get(game)
        checks.equal(
            entry["prompt"],
            strategy,
            f"the {game} registry entry names {strategy} — it said `unwritten` until "
            "2026-08-23, and asking for it refused rather than reading the card with "
            "another game's prompt",
        )
        chosen = prompt.profile(strategy)

        # D3 rung 3's enum, PER GAME. `variant.FINISHES` is Pokemon's three, and reading it
        # for another game was a real bug fixed in four places on 2026-08-23. Asserted as an
        # exact set rather than by naming `normal`/`foil`, so that widening the registry
        # entry widens this without anyone remembering to.
        offered = chosen.schema["properties"]["finish"]["enum"]
        checks.equal(
            sorted(offered),
            sorted(set(entry["finishes"]) | {prompt.UNKNOWN_FINISH}),
            f"{strategy}'s finish enum is exactly {game}'s own finishes plus `unknown` — "
            "read from the registry entry, never from variant.FINISHES",
        )
        checks.ok(
            not ({"holo", "reverse_holo"} & set(offered)),
            "and it offers no Pokemon-only finish: a `reverse_holo` here would be a "
            "condition string neither game's export carries",
            f"enum was {offered!r}",
        )
        # The prompt text and the schema enum are two statements of one fact, and only the
        # schema is machine-read. A finish the model is allowed to return but is never told
        # about is a member nothing will ever produce.
        for finish in entry["finishes"]:
            checks.ok(
                f"\n  {finish}" in chosen.system,
                f"and {game}'s `{finish}` is described in the system prompt as well as "
                "allowed by the schema — an enum member the prompt never mentions is a "
                "member the model has no reason to choose",
                f"not found in {strategy}'s system prompt",
            )

        # THE FIELD NAME, asserted at the schema before the round trip asserts it in anger.
        checks.equal(
            sorted(chosen.schema["required"]),
            ["confidence", "finish", "name", "number"],
            f"{strategy} asks for FOUR fields and calls the identifier `number` — the key "
            "cli/resolve.py reads off the raw payload",
        )
        checks.ok(
            "printed_total" not in chosen.schema["properties"],
            "and `printed_total` is absent rather than blank: a game keyed by "
            "printed_code has no denominator half, and _key_printed_code never reads "
            "one in either direction",
            f"properties were {sorted(chosen.schema['properties'])!r}",
        )

        # D23's clause lost its A/B on Pokemon for $0.17 and is off in production; shipping
        # it new on a game with no eval set would be unmeasurable by construction. Asserted
        # through `user_text` rather than only on the field, because the field is only half
        # the promise — the other half is that a claim supplied anyway renders nothing.
        checks.equal(chosen.rarity_clause, "", f"{strategy} carries no rarity clause")
        checks.equal(
            prompt.user_text(rarity_claim=("Common", "Rare"), strategy=strategy),
            chosen.user,
            "and a rarity claim supplied anyway renders NOTHING — the turn is byte-for-"
            "byte the unclaimed one",
        )
        # `crop_bands: ()` — nobody has measured where either game puts a title or a
        # number, so the retry turn must not name a band the cropper will never cut.
        checks.equal(tuple(entry["crop_bands"]), (), f"{game} claims no crop bands")
        for band in ("title band", "collector number", "number is printed"):
            checks.ok(
                band not in chosen.user_with_crops,
                f"and {strategy}'s crop-retry turn does not name a `{band}` it cannot "
                "be sent — it describes enlarged views of the same card and nothing more",
                f"turn was: {chosen.user_with_crops!r}",
            )

    # `unwritten` NAMES NOBODY NOW AND STILL REFUSES. This is the case that stops a later
    # session deleting the strategy as dead: it is what the NEXT game registered here lands
    # on, and its refusal is the only thing between that game and Pokemon's contract.
    checks.ok(
        all(entry["prompt"] != prompt.UNWRITTEN for entry in games.GAMES),
        "no registry entry names `unwritten` any more",
        f"still named by: {[e['key'] for e in games.GAMES if e['prompt'] == prompt.UNWRITTEN]!r}",
    )
    checks.equal(
        prompt.PROFILES.get(prompt.UNWRITTEN, "missing"),
        None,
        "and it is kept anyway, mapped to None — the honest value for the next game, "
        "unlike `operator_note`, which named a state the product does not have and was "
        "deleted",
    )
    refusal = checks.raises(
        prompt.UnwrittenPrompt,
        lambda: prompt.profile(prompt.UNWRITTEN),
        "asking for it still refuses BY NAME rather than falling through",
    )
    if refusal is not None:
        checks.ok(
            "do not read this game with another game's prompt" in str(refusal),
            "and the refusal still says what the alternative would cost",
            f"message was: {refusal}",
        )

    # ------------------------------------------------------ the parsers, field by field
    #
    # `066a/298` and `T02 // T03` are the two shapes a fold or a tidy-up would break, and
    # both are asserted through `parse` rather than by reading the schema: the parser is
    # where a later session would reach for `normalize_number`, which upper-cases and
    # strips a leading `#`.
    riftbound_read = prompt.parse(
        {
            "name": "Ahri, Alluring",
            "number": "066a/298",
            "finish": "foil",
            "confidence": "high",
        },
        "riftbound_card_v1",
    )
    checks.equal(
        [riftbound_read.name, riftbound_read.number, riftbound_read.printed_total],
        ["Ahri, Alluring", "066a/298", ""],
        "the identifier lands WHOLE in `number`, case and letter suffix untouched, and "
        "`printed_total` is empty — a half this game does not have rather than one we "
        "failed to read",
    )
    checks.equal(
        riftbound_read.detected_finish,
        "foil",
        "and `foil` survives the parser's whitelist, which is this game's enum and not "
        "Pokemon's",
    )
    checks.equal(
        riftbound_read.has_number,
        False,
        "has_number is False, which is the honest answer to the question it asks: no "
        "number/total key CAN be built for a printed_code game",
    )
    checks.equal(
        prompt.parse(
            {
                "name": "Bird // Buff",
                "number": "T02 // T03",
                "finish": "unknown",
                "confidence": "medium",
            },
            "riftbound_card_v1",
        ).number,
        "T02 // T03",
        "a double-sided token keeps the SPACES around its `//` — number_index_key folds "
        "zeros and case and nothing else, so `T02//T03` would fold to `T2//T3` and match "
        "nothing",
    )
    checks.equal(
        prompt.parse(
            {"name": "x", "number": "y", "finish": "unknown", "confidence": "low"},
            "one_piece_card_v1",
        ).detected_finish,
        None,
        "`unknown` maps to None — D3's no-signal case, not a manufactured disagreement",
    )
    checks.equal(
        prompt.parse(
            {
                "name": "Monkey.D.Luffy",
                "number": "ST26-005",
                "finish": "foil",
                "confidence": "high",
            },
            "one_piece_card_v1",
        ).name,
        "Monkey.D.Luffy",
        "and a dotted, unspaced One Piece name survives verbatim — normalize_name folds "
        "case, accents, apostrophes and dashes and does NOT fold a full stop, so a "
        "respaced `Monkey D. Luffy` would never compare equal to what the card prints",
    )
    for strategy in ("riftbound_card_v1", "one_piece_card_v1"):
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {
                    "name": "x",
                    "number": "y",
                    "finish": "reverse_holo",
                    "confidence": "high",
                },
                s,
            ),
            f"{strategy} REFUSES a Pokemon finish rather than dropping it to None — a "
            "silent drop here would lose rung 3's cross-check with nothing on screen",
        )
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {"name": "x", "number": "y", "finish": "normal", "confidence": "sure"}, s
            ),
            "and an out-of-enum confidence too — routing reads that field",
        )
        checks.raises(
            prompt.MalformedIdentification,
            lambda s=strategy: prompt.parse(
                {"name": "x", "printed_code": "y", "finish": "normal", "confidence": "high"},
                s,
            ),
            "and a payload naming the identifier `printed_code` is a MISSING KEY, loudly "
            "— never a card read with an empty number",
        )

    # ------------------------------ the round trip: raw payload -> resolve -> a real row
    #
    # THE CASE THIS SECTION EXISTS FOR. The payload written into `identifications.json` is
    # `Identification.raw` — the model's own keys — and `cli/resolve.py` reads them back
    # without parsing. Every pair below is chosen so that one dropped character lands on a
    # different real SKU: the fold forgives zero padding and case and forgives nothing else.
    plans = (
        (
            "riftbound",
            RIFTBOUND_EXPORT,
            (
                ("066a/298", "Ahri, Alluring", "foil"),
                # The same card written unpadded. number_index_key strips leading zeros
                # from every digit run on BOTH sides, so this must aggregate onto the SKU
                # above rather than miss — which is why neither prompt demands padding.
                ("66a/298", "Ahri, Alluring", "foil"),
                ("303*/298", "Ahri, Nine-Tailed Fox", "foil"),
            ),
            {
                "8926002": ("066a/298", "Near Mint Foil", 2),
                "8927897": ("303*/298", "Near Mint Foil", 1),
            },
        ),
        (
            "one_piece",
            ONE_PIECE_EXPORT,
            (
                ("OP15-079", "Absalom", "normal"),
                ("op15-79", "Absalom", "normal"),
                ("P-105", "Sabo", "foil"),
            ),
            {
                "9196764": ("OP15-079", "Near Mint", 2),
                "9194101": ("P-105", "Near Mint Foil", 1),
            },
        ),
    )
    for game, export, reads, expected in plans:
        strategy = str(games.get(game)["prompt"])
        with isolated_home() as home:
            run = runs.Run(directory=home, manifest={})
            cards = {}
            for index, (number, name, finish) in enumerate(reads, start=1):
                parsed = prompt.parse(
                    {
                        "name": name,
                        "number": number,
                        "finish": finish,
                        "confidence": "high",
                    },
                    strategy,
                )
                cards[f"7/{index}"] = {
                    "box": 7,
                    "index": index,
                    "game": game,
                    "photo": f"captures/box7/{index:04d}.jpg",
                    # RAW, exactly as `cli/cmd_identify.py` writes it: `item.identification
                    # = dict(outcome.identification.raw)`. Writing the parsed fields here
                    # instead would test a seam the pipeline does not have.
                    "identification": dict(parsed.raw),
                }
            run.write_identifications({"cards": cards})
            report = resolve.load(run, {game: Path(export)}).joins[game].report

        checks.equal(
            report.cards_in, len(reads), f"{game}: every card reached the {game} catalog"
        )
        checks.equal(
            {
                sku: (
                    match.row[tcgcsv.NUMBER_COLUMN],
                    match.condition,
                    len(match.positions),
                )
                for sku, match in report.matches.items()
            },
            expected,
            f"{game}: the model's raw `number` reached a REAL export row through "
            "cli/resolve.py without being parsed on the way — the seam that would have "
            "silently returned no_catalog_row for the whole run if this field were named "
            "`printed_code`",
        )

    # The negative that gives the round trip its meaning: one character dropped is a
    # different card at a different price, and the pipeline does not smooth it over.
    with isolated_home() as home:
        run = runs.Run(directory=home, manifest={})
        run.write_identifications(
            {
                "cards": {
                    f"8/{index}": {
                        "box": 8,
                        "index": index,
                        "game": "riftbound",
                        "photo": f"captures/box8/{index:04d}.jpg",
                        "identification": dict(
                            prompt.parse(
                                {
                                    "name": "Ahri, Nine-Tailed Fox",
                                    "number": number,
                                    "finish": "foil",
                                    "confidence": "high",
                                },
                                "riftbound_card_v1",
                            ).raw
                        ),
                    }
                    for index, number in enumerate(("303*/298", "303/298"), start=1)
                }
            }
        )
        starred = resolve.load(run, {"riftbound": RIFTBOUND_EXPORT}).joins["riftbound"]
    prices = {
        match.row[tcgcsv.NUMBER_COLUMN]: match.market_price
        for match in starred.report.matches.values()
    }
    checks.equal(
        sorted(prices),
        ["303*/298", "303/298"],
        "the asterisk is not decoration: `303*/298` and `303/298` are two different real "
        "SKUs and both are found",
    )
    checks.ok(
        prices.get("303*/298") != prices.get("303/298"),
        "and they are not the same card — a model that reads the asterisk as a footnote "
        "mark lands on a real row for a real card that is not the one in its hand",
        f"prices were {prices!r}",
    )


# ---------------------------------------------------------------------- command refusals


def check_cli_refusals(checks: Checks) -> None:
    """Commands refuse and say what to edit. They never ask.

    `cli/__main__.py` opens with the rule: the pipeline runs unattended, so a command that
    cannot proceed refuses rather than prompting. A prompt in this process is not a bad
    user experience, it is a batch run stopped forever with nobody watching.
    """
    checks.note("")
    checks.note("COMMAND REFUSALS — cli/__main__.py")

    from cli import __main__ as entry

    checks.equal(
        sorted(entry.COMMANDS),
        ["emit", "identify", "join", "reconcile"],
        "four commands are registered, and only four",
    )

    # No command may read stdin. Asserted against the source of every module the dispatch
    # can reach, because the failure is not visible until an unattended run hangs.
    root = Path(__file__).resolve().parents[2]
    prompting = []
    for module in sorted((root / "cli").glob("*.py")):
        text = module.read_text("utf-8")
        for needle in ("input(", "getpass", "sys.stdin.read"):
            if needle in text:
                prompting.append(f"{module.name}: {needle}")
    checks.equal(prompting, [], "no command reads from stdin — NO INTERACTIVE PROMPTS, ever")

    with isolated_home():
        missing = Path(files.home()) / "no-such-run"
        for argv, label in (
            (["join", str(missing)], "join"),
            (["emit", str(missing)], "emit"),
            (["reconcile", str(missing), str(missing / "staged.csv")], "reconcile"),
        ):
            with quiet() as said:
                code = entry.main(argv)
            checks.equal(code, 1, f"{label} on an absent run directory exits 1, never raises")
            checks.ok(
                str(missing) in said.getvalue(),
                f"and {label} names the path it could not use",
                f"said: {said.getvalue().strip()!r}",
            )

    # argparse exits 2 on a usage error, and that is the right code — it is a different
    # failure from a run that could not proceed, and a caller scripting these needs to tell
    # them apart.
    for argv, label in (
        ([], "no subcommand"),
        (["identify"], "identify with no capture directory"),
        (["join", "run", "--basis", "nonsense"], "an invalid --basis choice"),
    ):
        try:
            with quiet():
                entry.build_parser().parse_args(argv)
            checks.ok(False, f"{label} is refused by the parser", "parsed without error")
        except SystemExit as caught:
            checks.equal(caught.code, 2, f"{label} exits 2 (usage), not 1")


# --------------------------------------------------- emit, reconcile and join as quantities


def _stages(inventory) -> str:
    """The `listings` line the three commands print, rebuilt from `listing_counts()`.

    Built here rather than written out as a literal, so the assertion is that the commands
    print THIS number — not that they print some number that happens to match today.
    """
    return ", ".join(f"{k} {v}" for k, v in inventory.listing_counts().items() if v)


def check_emit_bypass(checks: Checks) -> None:
    """`emit` re-derives the run, so every input to that derivation comes from the run.

    THE DEFECT, FOUND BY THE OWNER PRESSING `Write the import files` ON A BOX THEY HAD JOINED.
    `cli/cmd_emit.py` called `resolve.load` without `trust_claim`, so it walked the ladder with
    D3 rung 3 LIVE over a run joined with `--bypass` — inventing a queued position for every
    bypassed card, finding none of them in either queue file (join deliberately never wrote
    them), and refusing with *"Run `pkmnscan join` first"* at an operator who had. Re-running
    join could not clear it, because join was right.

    Measured on the owner's box 1 before the fix: `bypassed: 39` in the manifest, 39 positions
    invented, 39 absent from disk, and the refusal's first ten positions matched what the screen
    printed character for character.

    THE REFUSAL WAS THE SECOND-WORST OUTCOME, which is why the case asserts the OUTPUT and not
    just the exit code. That same resolution is what writes the import files, so had the check
    passed, those cards would have been routed to review and left out of the CSV — the bypass
    silently void at the one step that produces output. So this asserts the bypassed card is IN
    the file, at the SKU its claim names.

    Its own isolated home, this file's own lesson yet again: it emits, which writes `pushed`
    counts that `check_listing_commands` and `check_cli_seams` assert over their own fixtures.
    """
    checks.note("")
    checks.note("EMIT BYPASS — the run's own resolution decides, not this command's defaults")

    # Dunsparce 120/159 stocks two condition rows, so a claim of `normal` is a claim the
    # catalog cannot settle on its own and detection is what contradicts it — D3 rung 3, the
    # exact rung `--bypass` switches off. A holofoil-only number could not produce the case.
    cards = [(3, 1, "Dunsparce", "120", "normal")]

    with isolated_home():
        for box, index, *_ in cards:
            while Store().read().inventory.next_index(box) <= index:
                capture_server.do_capture(capture_payload(box))

        run_dir = runs.create("t7-bypass")
        payload = identifications_for(cards)
        # THE CLAIM AND THE DETECTION MUST DISAGREE, and `identifications_for` sets both from
        # one field by design — a null finish is its rung-2 case. Patched here rather than by
        # widening that helper, because every other block in this file wants the agreeing shape.
        payload["cards"][master.position_key(3, 1)]["identification"]["finish"] = "reverse_holo"
        run_dir.write_identifications(payload)
        export = write_export(run_dir.path("export.csv"))

        said = command(
            checks, "join", str(run_dir.directory), "--export", str(export), "--bypass"
        )
        run_dir = runs.open_run(run_dir.directory)

        checks.ok(
            run_dir.manifest.get("bypass_detection") is True,
            "the run RECORDS that it was joined with --bypass. Without this on the manifest "
            "there is nothing for a later command to read, and every later command re-derives",
        )
        checks.equal(
            run_dir.manifest.get("bypassed"),
            1,
            "and records how many cards it cleared, so the count is reported rather than "
            "inferred from a smaller queue (D3)",
        )

        snapshot = Store().read()
        checks.equal(
            (len(snapshot.review.entries), len(snapshot.parked.entries)),
            (0, 0),
            "A BYPASSED CARD IS QUEUED NOWHERE, which is the whole point of the flag and the "
            "fact that made emit refuse: the position emit invented could not be on disk",
        )

        said = command(checks, "emit", str(run_dir.directory))
        checks.ok(
            "REFUSING to write" not in said,
            "`emit` DOES NOT REFUSE a run joined with --bypass. It read the flag off the "
            "manifest exactly as it already read `review_below_confidence`, rather than "
            "defaulting rung 3 back on and re-deriving a run that is not the one on disk",
        )

        # GUARDED, because the failure this case exists for is a REFUSAL — and a refusal
        # writes no file, so reading one unconditionally turns a clean red line into a
        # traceback that hides every check behind it. `answers()` above states the same rule.
        listed = run_dir.path(runs.import_listed_name("pokemon"))
        written = (
            {row[tcgcsv.SKU_COLUMN] for row in tcgcsv.read_export(listed).rows}
            if listed.is_file()
            else set()
        )
        checks.ok(
            listed.is_file(),
            "an import file EXISTS at all — the refusal wrote nothing, so this is what a "
            "regression looks like before any SKU can be asserted about",
        )
        checks.ok(
            DUNSPARCE_SKU in written,
            "AND THE CARD IS IN THE FILE AT THE SKU ITS CLAIM NAMES. This is the assertion "
            "that matters: the refusal was the second-worst outcome, and a fix that only "
            "silenced it would have left the card routed to review and out of the CSV — the "
            "bypass void at the one step that writes",
        )
        checks.ok(
            DUNSPARCE_REVERSE_SKU not in written,
            "and NOT at the finish detection claimed. `--bypass` is one rule — detection may "
            "not contradict a claim — so the claim decides, and rung 3's other job is untouched",
        )


def check_pricing_authority(checks: Checks) -> None:
    """`decisions.json` decides the price, and `join` may not take that decision back.

    TWO BUGS IN ONE SEAM, BOTH FOUND BY READING THE COMMANDS RATHER THAN THE TESTS, AND BOTH
    INVISIBLE TO EVERY CHECK IN THIS REPO ON THE DAY THEY WERE FOUND.

    The first: `cli/cmd_emit.py` resolved with `run_dir.manifest.get("rule")` and then printed
    `choice.describe` off `decisions.json`, so an operator who set `"rule": "undercut:5"` in the
    file got a run that PRINTED `rule=undercut:5` and priced every row at market. `pipeline/
    decisions.py`'s own docstring calls that file *"the pricing decision, as a file rather than
    as a flag"*, and it was the one thing in it that decided nothing.

    The second is worse because it destroys work: `cli/cmd_join.py` assigned `choice.rule` and
    `choice.basis` back from the run immediately after printing *"merging into existing
    decisions.json — your edits are kept"*. `join` is free and re-runnable and is re-run
    routinely, so an edited rule survived until the next join and then silently was not there.

    T5 asserts `decisions.json` CARRIES a rule (`:305-306`) and passed throughout — carrying it
    was never the question. These cases assert that it REACHES A PRICE, which is a fact about
    the command seam and belongs here.

    Its own isolated home, which is this file's own lesson three times over: these cases emit,
    which writes `pushed` counts that `check_listing_commands` and `check_cli_seams` both
    assert over their own fixtures.
    """
    checks.note("")
    checks.note("PRICING AUTHORITY — decisions.json decides, join records")

    cards = [(3, 1, "Articuno", "161", None)]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = run_dir.path(runs.DECISIONS)
        seeded = json.loads(path.read_text())
        checks.equal(
            (seeded["rule"], seeded["basis"]),
            ("match", "market"),
            "a first join SEEDS the file from the run's own flags — `--rule` is how a run's "
            "pricing starts, and a file with no rule in it would be a document that cannot "
            "answer the question it exists to ask",
        )

        # The market price this SKU is about to be priced from, read off the run's own export
        # rather than written here: a literal would go on passing if the fixture moved.
        export = tcgcsv.read_export(run_dir.path("export.csv"))
        market = export.by_sku()[ARTICUNO_SKU][tcgcsv.MARKET_PRICE_COLUMN]

        seeded["rule"] = "markup:100"
        seeded["sub_threshold"] = "floor"
        path.write_text(json.dumps(seeded))

        said = command(checks, "emit", str(run_dir.directory))
        written = {
            row[tcgcsv.SKU_COLUMN]: row[tcgcsv.PRICE_COLUMN]
            for row in tcgcsv.read_export(run_dir.path(runs.import_listed_name("pokemon"))).rows
        }
        checks.equal(
            written.get(ARTICUNO_SKU),
            tcgcsv.format_price(Decimal(market) * 2),
            "A RULE SET IN `decisions.json` REACHES THE EMITTED PRICE. `markup:100` doubles "
            "the market price into the import file — the whole content of the first bug, "
            "which priced at market while printing the rule it had been given",
        )
        checks.ok(
            "rule=markup:100" in said,
            "and the `pricing` line names the rule that was actually applied, which it did "
            "before this too — printing the file and pricing from the manifest is exactly how "
            "a wrong number stays invisible",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = run_dir.path(runs.DECISIONS)
        edited = json.loads(path.read_text())
        edited["rule"] = "undercut:5"
        edited["basis"] = "low"
        edited["sub_threshold"] = "floor"
        path.write_text(json.dumps(edited))

        said = command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        after = json.loads(path.read_text())
        checks.equal(
            (after["rule"], after["basis"], after["sub_threshold"]),
            ("undercut:5", "low", "floor"),
            "A RE-JOIN KEEPS THE EDITED RULE, which is what the sentence it prints has always "
            "promised. Two assignments used to run immediately after that sentence and reset "
            "exactly the two fields most likely to have been edited — measured, `markup:100` "
            "on `low` went back to `match` on `market` while `sub_threshold` beside it "
            "survived, so the file looked merged and was not",
        )
        checks.ok(
            "your edits are kept" in said,
            "and it still says so — the sentence was not the bug, the two lines under it were",
        )
        checks.equal(
            run_dir.manifest.get("rule"),
            "match",
            "THE MANIFEST STILL RECORDS WHAT THE JOIN RAN WITH, and it is deliberately NOT the "
            "edited value: a record of what happened is a different thing from the answer, "
            "`report.txt` prints this one, and only one of the two may be authoritative",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = run_dir.path(runs.DECISIONS)
        path.write_text(json.dumps({"rule": "undercut:not-a-number", "sub_threshold": "floor"}))
        from cli import __main__ as entry

        for argv, label in (
            (
                ["emit", str(run_dir.directory)],
                "emit refuses a rule outside the enum with a SENTENCE rather than a traceback",
            ),
            (
                [
                    "join",
                    str(run_dir.directory),
                    "--export",
                    str(run_dir.path("export.csv")),
                ],
                "and so does join — `UnknownRule` is a ValueError and NOT a "
                "`MalformedDecisions`, nothing above `cli/__main__.py` caught it, and `PUT "
                "/pipeline/runs/<name>/decisions` writes this document with no validation at "
                "all, so a screen can reach every one of these states",
            ),
        ):
            with quiet() as said:
                code = entry.main(argv)
            checks.equal(
                (code, "is unusable" in said.getvalue()),
                (1, True),
                label,
            )


def check_pricing_route(checks: Checks) -> None:
    """`GET /pipeline/runs/<name>/pricing` — free, read-only, two files from one moment.

    THE ONE THING WORTH ASSERTING HARDEST IS A SHAPE THAT LOOKS LIKE AN ACCIDENT AND IS NOT:
    `_RUN_STEP_RE` matches `^/pipeline/runs/<name>/([a-z]+)$`, so a **POST** to this same
    path reaches `do_pipeline_step` with `step="pricing"` and is refused against `FREE_STEPS`.
    That refusal is correct — pricing is a read and has no step — and it is asserted rather
    than left to be discovered by whoever next wonders why a POST here 404s.
    """
    checks.note("")
    checks.note("PRICING ROUTE — the table and the answers, in one read")

    cards = [(3, 1, "Articuno", "161", None)]

    with isolated_home():
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            bare = runs.create("unjoined")
            bare.set(capture_dir="/tmp/nowhere")
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{bare.directory.name}/pricing"
            )
            checks.equal(
                (status, error_code(body)),
                (409, "pricing_not_written"),
                "a run that has not been joined refuses IN ITS OWN CODE and names the "
                "command that writes the file — every run made before D49 is in this state, "
                "so the screen has to be able to say `re-join this run` rather than break",
            )

            run_dir, _ = seam_run(checks, cards)
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{run_dir.directory.name}/pricing"
            )
            payload = json.loads(body)
            checks.equal(
                (
                    status,
                    payload["run"],
                    [s["sku"] for s in payload["pricing"]["skus"]],
                    payload["decisions"]["rule"],
                ),
                (200, run_dir.directory.name, [ARTICUNO_SKU], "match"),
                "and a joined run answers with the table AND this run's answers together — "
                "two fetches could straddle a re-join, and a table describing one join "
                "beside answers written against another is a screen pricing the wrong cards",
            )
            checks.equal(
                len(payload["pricing"]["skus"][0]["row"]),
                len(tcgcsv.CANONICAL_HEADER),
                "every export cell travels VERBATIM — the owner asked for all the data from "
                "the CSV in front of them while they price, and a subset chosen here is a "
                "decision about what matters taken by the wrong file",
            )
            checks.equal(
                payload["remembered_sub_threshold"],
                None,
                "with no earlier run there is nothing to remember, and the answer is null "
                "rather than a guess — D9 forbids a default and this is a LABEL, not one",
            )
            # WHEN THE TABLE WAS WRITTEN, WHICH IS THE ONLY AGE A PRICE CAN HONESTLY CARRY.
            # `#/inventory`'s card panel draws `$5.47 · read 2 days ago` off this, and the
            # second half is not decoration: `join` is free, re-runnable and routinely pointed
            # at a REFRESHED export, so two cards on one shelf can carry prices read a week
            # apart and a bare figure claims a currency the file cannot support.
            #
            # BACKDATED FIRST, AND THAT IS THE WHOLE OF THE CASE. Asserting the field against
            # the file's live mtime is VACUOUS here: `seam_run` joins immediately before the
            # request, so a route that stamped `time.time()` instead would answer the same
            # integer and pass. That version was written, mutated to a clock, and observed
            # PASSING — which is the shape this repo has paid for before at the multi-game
            # prompt seam. Backdating the file by a week separates the two answers, so what is
            # checked is that the number describes THIS TABLE rather than THIS REQUEST.
            #
            # The failure it forbids is invisible from the screen: a price whose age resets to
            # `read today` every time the panel is opened is a stale figure wearing a fresh
            # stamp, which is worse than no stamp at all.
            table_file = run_dir.path(runs.PRICING)
            backdated = int(table_file.stat().st_mtime) - 7 * 86400
            os.utime(table_file, (backdated, backdated))
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{run_dir.directory.name}/pricing"
            )
            checks.equal(
                (status, json.loads(body).get("written_at")),
                (200, backdated),
                "and it says WHEN the table was written, off that file's own mtime — a week-old "
                "table reads a week old, where a clock read at request time would call every "
                "price fresh forever",
            )

            # A second run whose answer is on disk, so the label has something to find.
            answered = run_dir.path(runs.DECISIONS)
            payload_doc = json.loads(answered.read_text())
            payload_doc["sub_threshold"] = "floor"
            answered.write_text(json.dumps(payload_doc))
            later, _ = seam_run(checks, cards)
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{later.directory.name}/pricing"
            )
            remembered = json.loads(body)["remembered_sub_threshold"]
            checks.equal(
                (remembered or {}).get("answer"),
                "floor",
                "and a LATER run reads the last answer off the newest OTHER run — "
                "'remember that I said so' with no new storage, no migration and no file "
                "that can disagree with the runs it claims to summarise",
            )

            status, body, _ = request(
                port,
                "POST",
                f"/pipeline/runs/{run_dir.directory.name}/pricing",
                payload={},
            )
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_step"),
                "a POST to the same path is refused as a STEP rather than reaching this "
                "handler — the step pattern admits any lowercase word, so `pricing` matches "
                "it and is turned away by the free-steps list, which is correct and is the "
                "kind of overlap that is only obvious once somebody has asserted it",
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def check_withholding(checks: Checks) -> None:
    """A withheld SKU writes no row, moves no count, and is still FINDABLE (D49).

    THE OWNER ASKED THE QUESTION THIS SECTION ANSWERS. Shown that a held card would keep
    `state: captured` and carry no `sku`, they said: "Wait i want to be able to find it, why
    can't it be emitted?" It can. `cli/cmd_emit.py` had one `continue` doing two jobs —
    skipping the identity write and the `pushed` bump together — which was correct only while
    "reached a file" and "we know what this is" meant the same thing. A withhold is the first
    thing that splits them.

    So the three facts below are asserted together, because the value of each depends on the
    other two: no import row, no `pushed`, and the card knows what it is.
    """
    checks.note("")
    checks.note("WITHHOLDING — no row, no count, still findable")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Articuno", "161", None),
    ]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = run_dir.path(runs.DECISIONS)
        answers = json.loads(path.read_text())
        answers["sub_threshold"] = "floor"
        answers["overrides"] = {
            ARTICUNO_SKU: {
                "withheld": "bullish",
                "watch_above": "30.00",
                "note": "holding for rotation",
            }
        }
        path.write_text(json.dumps(answers))

        said = command(checks, "emit", str(run_dir.directory))
        listed = tcgcsv.read_export(run_dir.path(runs.import_listed_name("pokemon")))
        checks.equal(
            [row[tcgcsv.SKU_COLUMN] for row in listed.rows],
            [DUNSPARCE_SKU],
            "A WITHHELD SKU WRITES NO IMPORT ROW, and the SKU beside it still does — a hold "
            "that emptied the file would be a hold nobody could tell from a broken emit",
        )

        inventory = Store().read().inventory
        held_card = inventory.get(f"3/2")
        checks.equal(
            (held_card.state, held_card.sku, held_card.condition),
            (master.IDENTIFIED, ARTICUNO_SKU, "Near Mint Holofoil"),
            "AND ITS CARD STILL KNOWS WHAT IT IS. The identity is a fact about the physical "
            "object that the join established; nothing about withholding it makes that fact "
            "less true, and a card carrying no `sku` is invisible to GET /search and every "
            "SKU-keyed surface in the product",
        )
        checks.equal(
            inventory.listings.get(ARTICUNO_SKU),
            None,
            "AND NO COUNT MOVED — not even an empty record. `pushed` means a CSV was written "
            "and none was; `cli/resolve.py:_committed_keys` reads `pushed + staged` back as "
            "`committed`, so a count moved here would make the next run treat a card it never "
            "listed as already spoken for",
        )
        checks.ok(
            "withheld" in said and ARTICUNO_SKU in said,
            "and `emit` NAMES the hold as it commits the file — the moment a person can "
            "still change their mind is the moment it is worth saying, which is why this is "
            "a warning rather than a refusal",
        )

        # --- the watch, on the next join -------------------------------------------------
        said = command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        checks.ok(
            "WATCH" not in said,
            "a watch set ABOVE the market says nothing — an alert that fires on every join "
            "is an alert nobody reads",
        )

        answers = json.loads(path.read_text())
        answers["overrides"][ARTICUNO_SKU]["watch_above"] = "1.00"
        path.write_text(json.dumps(answers))
        said = command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        checks.ok(
            "WATCH" in said and "Articuno" in said and "$1.00" in said,
            "and one the market has passed is reported BY NAME on the run — `join` is free, "
            "re-runnable and pointed at a refreshed export, which is the only moment a price "
            "has moved and the only moment a watch has anything to say",
        )

        after = json.loads(path.read_text())
        checks.equal(
            after["overrides"][ARTICUNO_SKU],
            {"withheld": "bullish", "watch_above": "1.00", "note": "holding for rotation"},
            "and the hold ROUND-TRIPS through the re-join unchanged — reason, watch and note. "
            "`join` rewrites this file on every run, so a hold that lost its note would lose "
            "it on the first free command the operator pressed",
        )

        # --- a re-emit that HAS something new to say (D54) --------------------------------
        #
        # THE CASE THAT STOPS THE FIX BEING "EMIT ONCE, EVER". The block above proves a
        # no-op re-emit leaves the file alone; on its own, that assertion is satisfied just
        # as well by an emitter that refuses every second press. Lifting a hold is the
        # ordinary reason to emit again, and what must then be written is the DELTA — the
        # copies not already sent — because TCGplayer's Import to Staged ADDS quantity, so a
        # file repeating already-imported rows double-stages them. That is Gate B's recorded
        # 37-copy defect, and it is why a re-emit may not simply rewrite the whole file.
        answers = json.loads(path.read_text())
        del answers["overrides"][ARTICUNO_SKU]
        path.write_text(json.dumps(answers))
        command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        freed = command(checks, "emit", str(run_dir.directory))

        delta = tcgcsv.read_export(run_dir.path(runs.import_listed_name("pokemon")))
        checks.equal(
            [row[tcgcsv.SKU_COLUMN] for row in delta.rows],
            [ARTICUNO_SKU],
            "A RE-EMIT WRITES WHAT HAS NOT BEEN SENT, AND ONLY THAT. Dunsparce went in the "
            "first emit and its copies are at `pushed`; re-writing its row would import "
            "three copies a second time",
        )
        checks.equal(
            sorted(runs.open_run(run_dir.directory).emitted_skus),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "AND THE RECORD IS THE UNION ACROSS BOTH EMITS, not the last delta. `reconcile` "
            "reports in BOTH directions against this list, so a record holding only the "
            "second emit would put Dunsparce in `rows_without_cards` — reconcile accusing "
            "something else of writing a row it wrote itself",
        )
        checks.equal(
            runs.open_run(run_dir.directory).emitted["emits"],
            2,
            "and the record counts the emits that wrote a row, so a later reader can tell a "
            "run that was emitted once from one that was worked over several sittings",
        )
        checks.ok(
            "next: import" in freed,
            "and THIS re-emit does tell the operator to import, because this one wrote "
            "something — the no-op branch is the one that stays quiet",
            freed,
        )


def check_crop_preview(checks: Checks) -> None:
    """D32 — `POST /pipeline/crop-preview`: what a reading sends, before it is paid for.

    ITS OWN ISOLATED HOME, this file's own lesson yet again: the block writes photographs
    into a box, and the blocks above count records over boxes they build card by card.

    WHAT IT IS FOR. D32's amendment gave the crop three named pairs and a sentence each,
    because the owner could not read the control: *"walk me through how im supposed to
    understand crop with just this dialog box"*. The sentences are prose about pixels. This
    route answers the same question as a picture — the cut, and the collector-number strip at
    the resolution the reading delivers — and it has to be free, because it is pressed while
    the reading is being CHOSEN, before the preflight and long before the confirm.

    THE PROPERTY WORTH ASSERTING MOST IS A NEGATIVE ONE: it writes nothing. It sits in the one
    module of this server that can spend money, one route above the one that does, so
    "creates no run directory, no scope directory, no store write" is not a detail — it is
    what makes it safe to fire on every chip press.
    """
    try:
        from PIL import Image, ImageDraw  # noqa: F401
    except ImportError:
        checks.note("crop preview: Pillow absent, the route's own refusal path is all that runs")

    from server import pipeline_routes

    def photograph(path, *, card=True):
        """A bright card on a dark ground — the one premise `geometry.detect_card` needs."""
        from PIL import Image, ImageDraw

        # BIG ENOUGH THAT THE MAX EDGE BINDS, which the first draft was not: a 900x1600 frame
        # holding a 420x586 card crops to ~470x655, and `downscale` never upscales — so 1200
        # and 900 both sent it untouched and the band came back the same size at both. The
        # test was right and the fixture was wrong. A cropped long edge of ~1500 means both
        # readings actually resize, which is the condition the rig's 2160x3840 frames meet.
        frame = Image.new("RGB", (1500, 2600), (26, 28, 32))
        if card:
            draw = ImageDraw.Draw(frame)
            # 1000x1396 is CARD_ASPECT — 63:88, 0.716. An earlier draft drew 420x786 and the
            # detector correctly refused every frame: the shape gates are what stop it
            # cropping a guess, so a fixture that is not card-shaped tests the refusal path.
            draw.rectangle((300, 500, 1300, 1896), fill=(238, 232, 214))
            # A dark strip where a collector number prints, so the band is not blank paper.
            draw.rectangle((350, 1780, 700, 1840), fill=(40, 40, 40))
        frame.save(path, format="JPEG", quality=92)

    with isolated_home() as home:
        box = home / "captures" / "cards" / "box3"
        box.mkdir(parents=True)
        for index in (1, 2, 3, 4, 5, 6):
            photograph(box / f"{index:04d}.jpg")
            (box / f"{index:04d}.json").write_text(
                json.dumps({"box": 3, "index": index, "game": "pokemon"}), "utf-8"
            )

        runs_before = sorted(p.name for p in files.runs_dir().iterdir()) if files.runs_dir().is_dir() else []

        # --- the refusals, each in its own code ------------------------------------------
        for payload, code, why in (
            ({}, "box_required", "no box at all"),
            ({"box": 0}, "box_required", "a box that is not a positive integer"),
            ({"box": 99}, "box_has_no_captures", "a box nothing has been photographed into"),
            ({"box": 3, "indices": []}, "indices_invalid", "an empty selection"),
            ({"box": 3, "max_edge": 40}, "max_edge_invalid", "a max edge below the floor"),
            ({"box": 3, "max_edge": "1200"}, "max_edge_invalid", "a max edge that is a string"),
            ({"box": 3, "offset": -1}, "offset_invalid", "a negative offset"),
        ):
            try:
                pipeline_routes.do_pipeline_crop_preview(payload)
                checks.ok(False, f"crop preview refuses {why}", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(refusal.code, code, f"crop preview refuses {why} as `{code}`")

        # `max_edge` is validated by the SAME function the preflight uses, so a reading the
        # preview accepts is a reading `identify` will accept. A second range check beside the
        # second caller is a refusal that can disagree with the one the run actually gets.
        try:
            pipeline_routes._identify_flags({"max_edge": 40})
            checks.ok(False, "and the preflight refuses the same value", "it accepted it")
        except pipeline_routes.PipelineRefusal as refusal:
            checks.equal(
                refusal.code,
                "max_edge_invalid",
                "and the preflight refuses the same value through the same validator",
            )

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return

        # --- the cut, and the seam it shares with the run --------------------------------
        #
        # `geometry` IS DELIBERATELY NOT IMPORTED HERE, and the reason is a check in
        # `scripts/docs-audit.py`'s own self-test rather than taste: it proves the `tested_by
        # reach` row does not follow imports transitively by asserting that T7 reaches `store`
        # directly and does NOT reach `geometry` through `cli`. A direct import here would make
        # that fixture unable to tell a transitive follow from a real one, and it went red the
        # first time this block was written.
        #
        # Nothing is lost. The identity — that the rectangle the screen draws is the one
        # `card_crop` cuts — is T6's, asserted there against the detector and observed failing
        # against a `card_crop` that had stopped using `crop_rect`. What belongs HERE is the
        # route's own contract: that it reports a rectangle at all, that the rectangle is a
        # card, and that it lands inside the photograph the screen will draw it over.
        cropped = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(cropped["total"], 6, "the preview counts the photographs in scope")
        checks.equal(
            cropped["sample"]["index"], 1, "and shows ONE card, the one the offset names"
        )
        first = cropped["sample"]
        checks.ok(first["rect"] is not None, "a cropping reading reports where the cut falls")
        if first["rect"] is not None:
            left, top, right, bottom = first["rect"]
            width, height = first["frame"]
            checks.ok(
                0 <= left < right <= width and 0 <= top < bottom <= height,
                "and it lands inside the photograph the screen draws it over — the overlay is "
                "positioned as a percentage of the frame, so a cut that ran off the picture "
                "would be drawn outside it",
                f"{first['rect']} against {first['frame']}",
            )
            aspect = (right - left) / (bottom - top)
            checks.ok(
                abs(aspect - 0.716) < 0.05,
                "and it is CARD-SHAPED, which is the aspect correction reaching the screen: a "
                "flat pad over a box short for its width is what cut 38 collector numbers off "
                "box 2, and the preview would have drawn that crop as though it were fine",
                f"aspect {aspect:.3f}",
            )

        # --- the walk: one card, `offset`, and it WRAPS ----------------------------------
        #
        # Three evenly spaced cards for a few hours, on the argument that cards move on the
        # tray so the front of a box does not stand for it. The owner overruled it on the only
        # ground that decides whether a picture works: three abreast are three small pictures.
        # The spread is reached by walking now, which is also the only version of it that lets
        # you look at a card you actually suspect.
        walked = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200, "offset": 2}
        )
        checks.equal(walked["sample"]["index"], 3, "the offset walks the box one card at a time")
        wrapped = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200, "offset": 6}
        )
        checks.equal(
            wrapped["sample"]["index"],
            1,
            "and it WRAPS rather than clamping — a stepper that stops at the end of a 543-card "
            "box leaves the operator pressing a key that does nothing",
        )
        checks.equal(wrapped["offset"], 0, "and the answer reports the offset it actually used")

        # --- the whole-frame reading, and the two ways `rect` can be null ----------------
        whole = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": False, "max_edge": 1568}
        )
        checks.ok(
            whole["sample"]["rect"] is None,
            "the whole-frame reading reports no cut, because there is none",
        )
        checks.ok(
            whole["sample"]["method"] is not None,
            "but it still reports the detector's answer — `rect: null` because the crop is "
            "OFF and `rect: null` because detection REFUSED are opposite facts to an "
            "operator, and `method` is the only thing that tells them apart",
        )
        checks.ok(
            whole["sample"]["sent"] != cropped["sample"]["sent"],
            "and the two readings send different bytes, which is the whole subject",
        )

        # --- the band: the half that moves when the max edge moves -----------------------
        cheap = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 900}
        )
        checks.equal(
            cheap["sample"]["rect"],
            cropped["sample"]["rect"],
            "THE RECTANGLE IS IDENTICAL AT 1200 AND AT 900 — the crop decides framing and the "
            "max edge decides resolution, which is why the band exists at all",
        )
        checks.ok(
            cheap["sample"]["band_px"][0] < cropped["sample"]["band_px"][0],
            "and the collector number occupies FEWER PIXELS at 900 — the only half of the "
            "preview that can tell the two cropping readings apart",
            f"{cheap['sample']['band_px']} against {cropped['sample']['band_px']}",
        )

        # --- THE PICTURE IS THE PAYLOAD, WHICH IS WHAT MAKES ANY OF IT VISIBLE -----------
        #
        # The owner: "the crop preview should also show the depixelation reflected as you
        # change the options". The frame drew `GET /photo` — the same bytes at every reading —
        # so the one thing being changed was the one thing the picture could not show.
        checks.ok(
            str(cropped["sample"]["sent_image"]).startswith("data:image/jpeg;base64,"),
            "the sample carries the BYTES THAT WILL BE SENT, not the file on disk",
        )
        checks.ok(
            cropped["sample"]["sent_image"] != cheap["sample"]["sent_image"],
            "and they are different bytes at 1200 and at 900 — which is the whole of what the "
            "operator was asking to see",
        )
        checks.ok(
            cropped["sample"]["band_rect"] is not None
            and cropped["sample"]["band_rect"][2] <= cropped["sample"]["sent"][0]
            and cropped["sample"]["band_rect"][3] <= cropped["sample"]["sent"][1],
            "the band is a RECTANGLE INTO those bytes rather than a second image, so the 1:1 "
            "view and the frame cannot disagree about what is being sent — there is no second "
            "file to disagree with",
            f"{cropped['sample']['band_rect']} in {cropped['sample']['sent']}",
        )

        # --- THE BAND IS THE REGISTRY'S TO GRANT, PER CARD -------------------------------
        #
        # THE DEFECT THIS ROUTE SHIPPED WITH, found by the owner on box 1. It cut
        # `geometry/crop.py`'s number band over every game, and `pipeline/games.py` refuses
        # that in writing: "the bands are fractions measured on a Pokemon card. Nothing has
        # measured where a Riftbound card puts its title or its number, and a band claimed
        # without that measurement is cut over the wrong pixels." Box 1 is Riftbound, and the
        # strip drew its RULES TEXT as though it were a collector number.
        (box / "0001.json").write_text(
            json.dumps({"box": 3, "index": 1, "game": "riftbound"}), "utf-8"
        )
        rift = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(rift["sample"]["game"], "riftbound", "the sample carries the card's game")
        checks.equal(
            rift["sample"]["band_rect"],
            None,
            "a game whose `crop_bands` claims no number band gets NO RESTING AIM — the same "
            "refusal `crop_regions` makes, reached through the same registry field",
        )
        checks.ok(
            rift["sample"]["band_absent"] is not None
            and "riftbound" in rift["sample"]["band_absent"],
            "and the screen is told WHY, in the registry's own terms — and the 1:1 view still "
            "works, because the operator can point at the identifier themselves",
        )
        checks.ok(
            rift["sample"]["rect"] is not None,
            "while the CUT is unaffected — a card is 63x88mm whatever is printed on it, so "
            "the crop is right for every game even where no band has been measured",
        )
        (box / "0001.json").write_text(
            json.dumps({"box": 3, "index": 1, "game": "pokemon"}), "utf-8"
        )

        # --- a photograph with no card in it ---------------------------------------------
        photograph(box / "0001.jpg", card=False)
        refused = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(
            refused["sample"]["method"],
            None,
            "a frame the detector cannot find a card in reports no method, so the screen can "
            "say the card is going at whole-frame cost rather than leaving it inferred from a "
            "missing rectangle",
        )

        # --- and it wrote nothing ---------------------------------------------------------
        runs_after = sorted(p.name for p in files.runs_dir().iterdir()) if files.runs_dir().is_dir() else []
        checks.equal(
            runs_after,
            runs_before,
            "EIGHT PREVIEWS CREATED NO RUN DIRECTORY. It lives in the module that can spend, "
            "one route above the one that does, and it is fired on every chip press and every "
            "press of an arrow key",
        )
        checks.ok(
            not (home / ".scopes").exists(),
            "and no scope directory either — a whole-box preview symlinks nothing",
        )


def check_listing_commands(checks: Checks) -> None:
    """`emit`, `reconcile` and `join` moving SKU QUANTITIES rather than card states (D7).

    THE WHOLE SECTION EXISTS BECAUSE THE FACT MOVED. `pushed`, `staged` and `live` used to be
    states a card wore, so "has this copy been listed" was answerable from the card and every
    command wrote it there. The owner's ruling is that copies of one SKU are fungible — "if i
    have 15 of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations are
    live" — so the three are counts on the SKU's `Listing` now, and each command moves a
    number instead of flagging a position.

    What that makes newly breakable, and what is therefore asserted below: a count can be
    double-added where a state could only be re-set, it can be moved by reading the wrong
    column, and it can go negative. None of those three failures exists in a state machine.
    Every case runs the real subcommand through `cli/__main__.py`, because the command is the
    only place these three writes happen.
    """
    checks.note("")
    checks.note("LISTING COMMANDS — emit, reconcile and join as quantities")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "normal"),
        (3, 3, "Dunsparce", "120", "normal"),
        (3, 4, "Articuno", "161", None),
    ]

    # --- emit: identity onto the card, count onto the SKU --------------------------------
    with isolated_home():
        run_dir, joined = seam_run(checks, cards)
        checks.equal(
            Store().read().inventory.listings,
            {},
            "JOIN CREATES NO LISTING for a matched SKU with no live quantity and no record "
            "— `Inventory.listing` creates on read, and a run that merely matched a thousand "
            "SKUs would otherwise leave a thousand empty records for `staged_stale` and "
            "`listing_counts` to walk on every call",
        )

        emitted = command(checks, "emit", str(run_dir.directory))
        inventory = Store().read().inventory

        checks.equal(
            [
                (c.state, c.sku, c.condition, c.run)
                for c in (inventory.get(f"3/{i}") for i in (1, 4))
            ],
            [
                (master.IDENTIFIED, DUNSPARCE_SKU, "Near Mint", run_dir.name),
                (master.IDENTIFIED, ARTICUNO_SKU, "Near Mint Holofoil", run_dir.name),
            ],
            "emit writes the IDENTITY onto each copy — sku, condition and the run that "
            "decided them — and leaves the card at `identified`, which is where it stays: "
            "the stage it reached is not a fact about this piece of cardboard",
        )
        listing = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.pushed, listing.staged, listing.live, listing.condition),
            (3, 0, 0, "Near Mint"),
            "and the COUNT onto the SKU: three copies pushed, nothing further, at the "
            "condition the ladder resolved",
        )
        checks.ok(listing.at, "stamped, so `join`'s stale warning has something to read")
        checks.equal(
            inventory.listing_counts(),
            {master.PUSHED: 4, master.STAGED: 0, master.LIVE: 0},
            "and listing_counts() sums the stages across every SKU",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in emitted,
            "which is exactly the line `emit` prints — the run report's listing totals are "
            "that function and not a second count kept beside it",
            emitted,
        )
        rows = tcgcsv.read_export(run_dir.path(runs.IMPORT_LISTED)).by_sku()
        checks.equal(
            [rows[DUNSPARCE_SKU][tcgcsv.QUANTITY_COLUMN], rows[ARTICUNO_SKU][tcgcsv.QUANTITY_COLUMN]],
            ["3", "1"],
            "and the file carries one row per SKU with the copy count, never one row per copy",
        )

        # --- the re-emit that produced the Gate B defect ---------------------------------
        # A second `join` then `emit` over the same run, which is the ordinary thing to do
        # after editing a review. `cli/resolve.py` reads the counts back as `committed`, so
        # every copy is already spoken for and the file gets nothing.
        #
        # CAPTURED BEFORE THE SECOND EMIT, because the assertion below is about the file NOT
        # being touched, and that cannot be checked against a file this block wrote itself.
        before_bytes = run_dir.path(runs.IMPORT_LISTED).read_bytes()
        command(checks, "join", str(run_dir.directory))
        again = command(checks, "emit", str(run_dir.directory))
        re_inventory = Store().read().inventory
        checks.equal(
            re_inventory.listing_counts(),
            {master.PUSHED: 4, master.STAGED: 0, master.LIVE: 0},
            "A RE-EMIT ADDS NOTHING TO `pushed`. The first real post-import re-emit "
            "(2026-08-22) re-counted 37 copies into the files; a count that is incremented "
            "rather than set is the one thing that can be double-added, so this is the case "
            "that has to be re-asserted against every change to the push loop",
        )
        checks.equal(
            [c.state for c in re_inventory.copies_on_hand(DUNSPARCE_SKU)],
            [master.IDENTIFIED] * 3,
            "and no copy is walked backwards to an earlier state — the other half of the "
            "same defect, which regressed staged copies to `pushed`",
        )
        checks.ok(
            "at cap           2 SKU(s)" in again,
            "the SKUs are REPORTED as already at the cap, because they are real cards at "
            "real positions and a run that silently omitted them would look identical to a "
            "run that lost them",
            again,
        )
        # A RE-EMIT WITH NOTHING NEW TO WRITE DOES NOT OPEN THE FILE.
        #
        # This replaced `len(rows) == 0`, which was blind: "the file holds no rows" is
        # satisfied IDENTICALLY by the emitter correctly omitting a zero-quantity row and by
        # the emitter overwriting two good rows with a bare header. A pass condition met
        # equally by a behaviour and by that behaviour's catastrophic opposite is not testing
        # the behaviour, and the destruction lived behind it.
        #
        # BYTE equality and not row equality, deliberately: `tcgcsv.render` writes the header
        # before it iterates, so a file rewritten with no rows is a valid CSV of nothing and
        # the row count cannot tell that from the rows never having existed.
        checks.equal(
            run_dir.path(runs.IMPORT_LISTED).read_bytes(),
            before_bytes,
            "A RE-EMIT THAT HAS NOTHING NEW TO WRITE DOES NOT TOUCH THE FILE. Rewriting it "
            "with a header and no rows destroys the output the operator was told to import, "
            "and leaves a valid CSV of nothing in its place",
        )
        # LOOKED UP DEFENSIVELY, because the failure this case exists to catch empties the
        # file — and a KeyError here would abort the block before the manifest and round-trip
        # assertions below ever ran, reporting one crash instead of four findings.
        surviving = tcgcsv.read_export(run_dir.path(runs.IMPORT_LISTED))
        by_sku = surviving.by_sku()
        checks.equal(
            [
                by_sku.get(DUNSPARCE_SKU, {}).get(tcgcsv.QUANTITY_COLUMN),
                by_sku.get(ARTICUNO_SKU, {}).get(tcgcsv.QUANTITY_COLUMN),
            ],
            ["3", "1"],
            "and the first emit's content is still there to be imported",
        )
        checks.ok(
            "0" not in [row[tcgcsv.QUANTITY_COLUMN] for row in surviving.rows],
            "and no row carries `Add to Quantity` of 0, which TCGplayer would accept and act "
            "on — the claim the assertion this replaced was written to make, asserted where "
            "it is actually observable",
        )
        checks.equal(
            sorted(runs.open_run(run_dir.directory).manifest["emitted"]["listed"]),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "AND THE MANIFEST STILL NAMES WHAT WAS SENT. Nothing asserted this record after a "
            "second emit, which is why the destruction survived: every assertion in this "
            "block was about the store, and the store side was already safe. `reconcile` "
            "reads exactly this list, and an empty one makes it refuse a run that emitted",
        )
        checks.ok(
            "next: import" not in again,
            "and a re-emit that wrote nothing does not tell the operator to go and import it",
            again,
        )

        # AND THE ROUND TRIP STILL CLOSES AFTER TWO EMITS.
        #
        # THE ASSERTION THAT WOULD HAVE CAUGHT THIS IN ONE LINE, and the only one in this
        # block that spans two commands. `cli/cmd_reconcile.py` reads `emitted.listed +
        # emitted.sub_threshold` and refuses "this run has emitted nothing" when it is empty
        # — so a second emit that blanked the manifest made a run that had emitted perfectly
        # an hour ago unreconcilable, with its CSV already imported to TCGplayer. `command`
        # asserts exit 0, so the refusal fails here rather than needing its own check.
        staged = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 1}
        )
        command(checks, "reconcile", str(run_dir.directory), str(staged))
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).staged,
            3,
            "and the copies reach `staged`, which is the whole point of the round trip: a "
            "run whose emit record was destroyed cannot move a single copy off `pushed`, "
            "and nothing else in the product ever takes them off it",
        )

    # --- emit against a position the store has never seen ---------------------------------
    # A run joined from a recovered or hand-made identifications file. The push loop upserts
    # before it writes, because `set_state` returns False for an unknown position and a
    # transition reported as having happened that did not is v1 bug 5 exactly.
    with isolated_home():
        run_dir = runs.create("t7-unseen")
        run_dir.write_identifications(identifications_for([(7, 1, "Articuno", "161", None)]))
        export = write_export(run_dir.path("export.csv"))
        command(checks, "join", str(run_dir.directory), "--export", str(export))
        checks.ok(
            Store().read().inventory.get("7/1") is None,
            "the store has never seen this position, and `join` does not invent it",
        )
        said = command(checks, "emit", str(run_dir.directory))
        landed = Store().read().inventory
        checks.equal(
            (landed.get("7/1").state, landed.get("7/1").sku),
            (master.IDENTIFIED, ARTICUNO_SKU),
            "emit UPSERTS the position first, so the identity write lands somewhere",
        )
        checks.equal(
            landed.listing_for(ARTICUNO_SKU).pushed,
            1,
            "and the copy is counted exactly once against the SKU",
        )
        checks.ok(
            "pushed           1 copy(ies) across 1 SKU(s)" in said,
            "and what the command reports is what landed — nothing counted that did not",
            said,
        )

    # --- reconcile: pushed -> staged, as counts -------------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))
        before = [c.state for c in Store().read().inventory.cards.values()]

        staged_export = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 1}
        )
        moved = command(
            checks, "reconcile", str(run_dir.directory), str(staged_export)
        )
        inventory = Store().read().inventory
        listing = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.pushed, listing.staged),
            (0, 3),
            "reconcile MOVES A COUNT: three copies leave `pushed` and arrive at `staged`, "
            "and which physical copies they are is deliberately not recorded",
        )
        checks.ok(
            listing.staged_at,
            "and `staged_at` is stamped, which is the whole of what `staged_stale` reads — "
            "an import that staged and never moved live is invisible without it",
        )
        checks.equal(
            [c.state for c in inventory.cards.values()],
            before,
            "and NO CARD MOVED. A sale changes a card; a stage changes a quantity, and the "
            "cards are exactly where emit left them",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in moved,
            "and `reconcile` prints listing_counts() too, so the same number reads the same "
            "on all three commands",
            moved,
        )

        # Re-running it moves nothing more. `pushed` is now zero, so there is no count left
        # to take — the idempotence is the cap below doing its job at the boundary.
        command(checks, "reconcile", str(run_dir.directory), str(staged_export))
        checks.equal(
            Store().read().inventory.listing_counts(),
            {master.PUSHED: 0, master.STAGED: 4, master.LIVE: 0},
            "and a second reconcile stages nothing twice — there is no pushed count left",
        )

    # --- reconcile reads `Add to Quantity`, never `Total Quantity` -------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))

        # The two columns disagree on purpose: `write_staged` sets `Total Quantity` to 97 on
        # every row. A command reading the live column would stage 97 copies of each.
        disagreeing = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 1, ARTICUNO_SKU: 9}
        )
        command(checks, "reconcile", str(run_dir.directory), str(disagreeing))
        inventory = Store().read().inventory
        dunsparce = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (dunsparce.pushed, dunsparce.staged),
            (2, 1),
            "reconcile reads `Add to Quantity`, the column `emit` wrote — `Total Quantity` "
            "is the LIVE number (D8, D11) and staging on it would move copies TCGplayer "
            "never said it had staged",
        )
        articuno = inventory.listing_for(ARTICUNO_SKU)
        checks.equal(
            (articuno.pushed, articuno.staged),
            (0, 1),
            "and the move is CAPPED at what this pipeline pushed: a reported 9 against 1 "
            "pushed stages 1 and floors `pushed` at zero rather than going negative",
        )

        # A blank cell is an UNKNOWN quantity, not a zero one — D9's reading of a blank
        # market cell, applied to a quantity. The SKU is in the export, so TCGplayer has it.
        # Both SKUs, because `reconcile` reports in both directions and an export missing
        # one of them is a different finding from the one under test here.
        blank = write_staged(
            run_dir.path("blank.csv"), {DUNSPARCE_SKU: "", ARTICUNO_SKU: ""}
        )
        assumed = command(checks, "reconcile", str(run_dir.directory), str(blank))
        dunsparce = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (dunsparce.pushed, dunsparce.staged),
            (0, 3),
            "a blank quantity falls back to this pipeline's own `pushed` count rather than "
            "stranding every pushed copy at `pushed` forever and making `staged_stale` warn "
            "about an import that in fact landed",
        )
        checks.ok(
            DUNSPARCE_SKU in assumed and "reported no quantity" in assumed,
            "and the assumption is NAMED with its SKU, never made silently",
            assumed,
        )

    # --- reconcile on a landed SKU this pipeline never pushed ------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))
        with Store().write() as snapshot:
            del snapshot.inventory.listings[ARTICUNO_SKU]

        landed = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 4}
        )
        command(checks, "reconcile", str(run_dir.directory), str(landed))
        checks.ok(
            Store().read().inventory.listing_for(ARTICUNO_SKU) is None,
            "a matched row whose SKU has no listing record CREATES NOTHING — the row is "
            "reported either way, and inventing a count here would stage copies nothing "
            "ever wrote into a file",
        )

    # --- join sets `live` from the export, absolutely ---------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))

        # Hand-set, because what is under test is the direction of the write and not how the
        # numbers got there. Dunsparce is the rise case, Articuno the no-change case.
        with Store().write() as snapshot:
            dunsparce = snapshot.inventory.listing(DUNSPARCE_SKU)
            dunsparce.set(master.PUSHED, 0)
            dunsparce.set(master.STAGED, 2)
            dunsparce.set(master.LIVE, 0)
            articuno = snapshot.inventory.listing(ARTICUNO_SKU)
            articuno.set(master.PUSHED, 0)
            articuno.set(master.STAGED, 2)
            articuno.set(master.LIVE, 4)

        rose = write_export(
            run_dir.path("export.csv"), live={DUNSPARCE_SKU: 2, ARTICUNO_SKU: 4}
        )
        said = command(checks, "join", str(run_dir.directory), "--export", str(rose))
        inventory = Store().read().inventory
        checks.equal(
            (inventory.listing_for(DUNSPARCE_SKU).live, inventory.listing_for(DUNSPARCE_SKU).staged),
            (2, 0),
            "join reads `live` off the export and DRAWS `staged` DOWN BY THE RISE: two "
            "copies went live, so two stop being staged — otherwise the stale warning names "
            "every SKU that has ever staged, forever",
        )
        checks.equal(
            (inventory.listing_for(ARTICUNO_SKU).live, inventory.listing_for(ARTICUNO_SKU).staged),
            (4, 2),
            "and by the RISE and not the absolute reading: a SKU whose live quantity did not "
            "move keeps its staged copies, which are exactly the ones the warning exists to "
            "find",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in said,
            "and `join` prints listing_counts() as well — the third of the three commands",
            said,
        )

        # DOWNWARD TOO. The export is the authority (D8, D11) and the stored number is an
        # optimistic local estimate, so a join that only ever raised it would let a sale on
        # TCGplayer leave this Mac permanently overstating what is for sale.
        with Store().write() as snapshot:
            snapshot.inventory.listing(DUNSPARCE_SKU).set(master.LIVE, 9)
        fell = write_export(run_dir.path("export.csv"), live={DUNSPARCE_SKU: 2})
        command(checks, "join", str(run_dir.directory), "--export", str(fell))
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).live,
            2,
            "a stored 9 against an export that says 2 becomes 2 — set from the export, never "
            "nudged toward it",
        )

    # --- the v1 -> v2 migration, through a real store session ------------------------------
    # `check_boxes_and_listings` drives `Inventory.parse` directly. This is the other half:
    # that the migration survives a read and a commit through `store/session.py`, which is
    # the only path a running system ever takes.
    with isolated_home():
        files.write_json(
            Store().inventory_path,
            {
                "version": 1,
                "cards": {
                    "4/1": {
                        "box": 4, "index": 1, "sku": DUNSPARCE_SKU,
                        "condition": "Near Mint", "state": "pushed",
                        "state_at": "2026-08-01T00:00:00+00:00",
                    },
                    "4/2": {
                        "box": 4, "index": 2, "sku": DUNSPARCE_SKU,
                        "condition": "Near Mint", "state": "live",
                        "state_at": "2026-08-01T00:00:00+00:00",
                    },
                },
            },
        )
        with Store().write():
            pass  # read, migrate, commit — the shape every request has

        on_disk = json.loads(Store().inventory_path.read_text("utf-8"))
        checks.equal(on_disk["version"], master.VERSION, "the committed file is v2")
        checks.equal(
            [record["state"] for record in on_disk["cards"].values()],
            [master.IDENTIFIED, master.IDENTIFIED],
            "and no card on disk wears a listing stage any more — a v2 file that did would "
            "fail `check_state` loudly on the next write rather than being repaired forever",
        )
        checks.equal(
            {
                stage: on_disk["listings"][DUNSPARCE_SKU][stage]
                for stage in master.LISTING_STAGES
            },
            {master.PUSHED: 1, master.STAGED: 0, master.LIVE: 1},
            "and each stage arrived on the SKU as a count, through the session rather than "
            "only through `Inventory.parse`",
        )
        checks.equal(
            Store().read().inventory.listing_counts(),
            {master.PUSHED: 1, master.STAGED: 0, master.LIVE: 1},
            "which a second session reads back unchanged — a v2 payload is not re-migrated",
        )


# ------------------------------------------------------------- boxes, listings, migration


def check_boxes_and_listings(checks: Checks) -> None:
    """D20's box object, D7's fungible copies, and the v1 -> v2 migration between them.

    THE MIGRATION CASE IS THE LOAD-BEARING ONE. Every label this repo rendered before D20 was
    computed from a global `CARDS_PER_SECTION`; sections became per-box, and on 2026-08-29 that
    global was deleted outright. If the migration gets this wrong, every position label in a
    real inventory shifts at once and the only symptom is a person opening the wrong slot weeks
    later. So it is asserted against the literal strings, not against the formula that produced
    them — and the strings it pins moved once, deliberately, which the case itself explains.
    """
    checks.note("")
    checks.note("BOXES AND LISTINGS — store/master.py")

    # --- the v1 -> v2 migration ------------------------------------------------------
    legacy = {
        "version": 1,
        "cards": {
            "1/1": {"box": 1, "index": 1, "sku": "888", "condition": "Near Mint",
                    "state": "staged", "state_at": "2026-08-01T00:00:00+00:00"},
            "1/26": {"box": 1, "index": 26, "sku": "888", "condition": "Near Mint",
                     "state": "live", "state_at": "2026-08-01T00:00:00+00:00"},
            "1/53": {"box": 1, "index": 53, "sku": "999", "condition": "Near Mint",
                     "state": "sold", "state_at": "2026-08-01T00:00:00+00:00"},
            "2/4": {"box": 2, "index": 4, "state": "captured"},
        },
    }
    migrated = master.Inventory.parse(legacy)

    checks.equal(
        [migrated.cards[k].state for k in ("1/1", "1/26", "1/53", "2/4")],
        ["identified", "identified", "sold", "captured"],
        "a card wearing a listing stage migrates to `identified`; sold and captured stand",
    )
    checks.equal(
        (migrated.listings["888"].staged, migrated.listings["888"].live),
        (1, 1),
        "and hands its stage to the SKU as a count (D7 amended)",
    )
    checks.ok(
        "999" not in migrated.listings,
        "a sold card starts no listing — it left inventory, it was never a quantity",
    )
    checks.equal(
        sorted(migrated.boxes), ["1", "2"],
        "every box a card names gets a registry entry",
    )
    checks.equal(
        migrated.boxes["1"].sections, [],
        "MIGRATED BOXES DECLARE NO LAYOUT — which is what preserves every existing label",
    )
    checks.equal(
        migrated.boxes["1"].capacity, None,
        "and no capacity: it is retroactive, and this box was never sealed (D20)",
    )

    # THE LABELS THEMSELVES. Literal strings, because a formula asserted against itself
    # proves nothing about the cards already on a shelf.
    #
    # THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-29 AND THE REVERSAL IS THE POINT. It
    # read "a migrated box renders every label byte-identical to before the migration", and
    # the labels it pinned were `Section 2 · Card 1` at index 26 and `Section 3 · Card 3` at
    # index 53 — dividers `CARDS_PER_SECTION = 25` cut into a box nobody had divided. The
    # owner's instruction was to delete automatic sectioning, so those labels are exactly
    # what had to move, and a test that pinned them is the test that had to change.
    #
    # WHAT IT IS STILL FOR is what its docstring says: the migration is load-bearing because
    # a wrong one shifts every position label in a real inventory at once, and the only
    # symptom is somebody opening the wrong slot weeks later. That risk did not go away — it
    # was REALISED, deliberately and once, and box 1 of the owner's own store is the
    # measurement (133 cards that read as six sections and are now the one section the box
    # physically is). Pinning the new strings is what keeps the next shift accidental.
    checks.equal(
        [join.Position(1, i, migrated.sections_for(1)).label for i in (1, 25, 26, 53)],
        [
            "Box 1 · Section 1 · Card 1",
            "Box 1 · Section 1 · Card 25",
            "Box 1 · Section 1 · Card 26",
            "Box 1 · Section 1 · Card 53",
        ],
        "AN UNDECLARED BOX IS ONE SECTION, and `card` is the index: no divider exists "
        "until somebody puts one in (D10, amended 2026-08-29)",
    )
    checks.equal(
        [
            join.Position(1, 53, migrated.sections_for(1)).section_start,
            join.Position(1, 53, migrated.sections_for(1)).section_end,
        ],
        [1, None],
        "its one section starts at card 1 and has no end of its own — it runs to wherever "
        "the box stops, which is D20's answer for a final section and not a new rule",
    )

    # --- declared layouts --------------------------------------------------------------
    inventory = master.Inventory()
    inventory.ensure_box(1, name="ME01 commons")
    checks.equal(inventory.box(1).name, "ME01 commons", "a box can be created and named")
    checks.equal(inventory.box(1).state, master.BOX_OPEN, "and starts open")

    inventory.set_sections(1, [1, 31, 56])
    checks.equal(
        [join.Position(1, i, inventory.sections_for(1)).label for i in (30, 31, 55, 56)],
        [
            "Box 1 · Section 1 · Card 30",
            "Box 1 · Section 2 · Card 1",
            "Box 1 · Section 2 · Card 25",
            "Box 1 · Section 3 · Card 1",
        ],
        "a declared layout puts the divider exactly where it was declared",
    )
    checks.equal(
        join.Position(1, 90, inventory.sections_for(1)).section_end,
        None,
        "the FINAL section has no end until a capacity says where the box stops (D20)",
    )

    # A boundary edit relabels what is behind it and touches no index. D10 (amended)
    # accepts this deliberately, so it is asserted rather than guarded against.
    before = join.Position(1, 40, inventory.sections_for(1)).label
    inventory.set_sections(1, [1, 41, 56])
    after = join.Position(1, 40, inventory.sections_for(1)).label
    checks.equal(
        (before, after),
        ("Box 1 · Section 2 · Card 10", "Box 1 · Section 1 · Card 40"),
        "moving a divider RELABELS the cards behind it — the label is a view (D10 amended)",
    )
    checks.ok(
        any(e.get("event") == "resectioned" for e in inventory.events),
        "and it leaves a `resectioned` event, which is the whole mitigation",
    )
    checks.equal(
        [e for e in inventory.events if e.get("event") == "resectioned"][-1]["sections_to"],
        [1, 41, 56],
        "carrying the layout it moved to, so the change is reconstructable",
    )
    checks.ok(
        "position" not in [e for e in inventory.events if e.get("event") == "resectioned"][-1],
        "and no position: a box is not at one, and a null would read as a lost card",
    )

    for bad, why in (
        ([2, 30], "a layout not starting at index 1"),
        ([1, 30, 20], "an unsorted layout"),
        ([1, 30, 30], "two dividers in one slot"),
        (["x"], "a layout that is not integers"),
    ):
        checks.raises(
            master.BadSections,
            lambda bad=bad: inventory.set_sections(1, bad),
            f"{why} is REFUSED, never quietly repaired",
        )

    # --- the lifecycle -----------------------------------------------------------------
    with isolated_home():
        for _ in range(4):
            capture_server.do_capture(capture_payload(5))
        with Store().write() as snapshot:
            checks.equal(snapshot.inventory.box_fill(5), 4, "fill is the high-water mark")
            snapshot.inventory.close_box(5)
            box = snapshot.inventory.box(5)
            checks.equal(box.capacity, 4, "SEALING FREEZES CAPACITY at the final fill (D20)")
            checks.ok(box.closed, "and the box reads closed")
            checks.raises(
                master.BoxClosed,
                lambda: snapshot.inventory.close_box(5),
                "sealing a sealed box refuses rather than restamping it",
            )
            checks.raises(
                master.BoxClosed,
                lambda: snapshot.inventory.allocate_capture(5),
                "A SEALED BOX TAKES NO MORE CARDS — one more would falsify every fraction",
            )
            checks.equal(
                snapshot.inventory.next_index(5), 5,
                "and the refusal burned no index: it is checked before one is computed",
            )
            snapshot.inventory.reopen_box(5)
            checks.equal(
                snapshot.inventory.box(5).capacity, None,
                "re-opening drops capacity rather than leaving a stale number standing",
            )
            card, created = snapshot.inventory.allocate_capture(5)
            checks.ok(created and card.index == 5, "and the box takes cards again")

    # --- listings are quantities, never addresses --------------------------------------
    inventory = master.Inventory()
    for index in range(1, 8):
        inventory.record_capture(master.Card(box=9, index=index, sku="777"))
    listing = inventory.listing("777", condition="Near Mint")
    listing.live = 4

    checks.equal(
        len(inventory.copies_on_hand("777")), 7,
        "EVERY unsold copy is on hand — none is designated backstock (D7 amended)",
    )
    inventory.set_state("9/3", master.SOLD)
    checks.equal(
        len(inventory.copies_on_hand("777")), 6,
        "and a sale takes exactly one copy out of the sellable set",
    )
    checks.equal(
        [c.key for c in inventory.copies_on_hand("777")],
        ["9/1", "9/2", "9/4", "9/5", "9/6", "9/7"],
        "in box-walk order, with the sold position left as a permanent gap (D10)",
    )
    checks.equal(listing.bump(master.LIVE, -1), 3, "a sale decrements the SKU's live count")
    checks.equal(
        [listing.bump(master.LIVE, -9), listing.live], [0, 0],
        "which floors at zero rather than going negative",
    )
    checks.raises(
        master.UnknownState,
        lambda: listing.bump("captured"),
        "and a position state is not a listing stage — bump refuses it",
    )
    checks.raises(
        master.UnknownState,
        lambda: master.check_state(master.LIVE),
        "`live` IS NOT A CARD STATE any more — check_state refuses it, which is the guard "
        "that stops a caller reaching for the old per-position flag",
    )

    # --- the round trip ----------------------------------------------------------------
    inventory.ensure_box(9, name="round trip")
    inventory.set_sections(9, [1, 4])
    reloaded = master.Inventory.parse(inventory.to_payload())
    checks.equal(reloaded.to_payload()["version"], master.VERSION, "to_payload stamps v2")
    checks.equal(
        reloaded.boxes["9"].sections, [1, 4], "boxes survive a JSON round trip"
    )
    checks.equal(
        (reloaded.listings["777"].sku, reloaded.listings["777"].live),
        ("777", 0),
        "and so do listings",
    )
    checks.equal(
        [c.state for c in reloaded.copies_on_hand("777")],
        ["captured"] * 6,
        "and a v2 payload is NOT re-migrated on read — the stages stay where they are",
    )


# ------------------------------------------------------------------------------------ run


def check_pipeline_routes(checks: Checks) -> None:
    """The pipeline seam — and every refusal that stands between a screen and an invoice.

    THE ONE ROUTE IN THIS SERVER THAT CAN SPEND MONEY IS `POST /pipeline/identify`, and the
    cases below never let it succeed. That is deliberate rather than a gap: a test that
    proved the happy path would have to submit a real Batch, and `harness/run.py` runs at
    the end of every turn. What IS provable without spending is the whole guard rail — that
    it refuses without an explicit confirm, that it refuses a scope that names nothing, and
    that the free preflight beside it computes the same numbers while creating no run — and
    that is what this section holds.

    Everything else here is free by construction: reading a run reads a directory, and
    `join --dry-run` walks the ladder and writes nothing. Both are exercised over real
    sockets against a real store in a temporary home.
    """
    with isolated_home() as home:
        # A capture directory with two real photographs, so a scope can be built from it and
        # `sidecar.scan` has something to find. The bytes are the same tiny JPEG every other
        # section captures with — nothing here reads a card out of them.
        box_dir = home / "captures" / "cards" / "box3"
        box_dir.mkdir(parents=True)
        for index in (1, 2):
            (box_dir / f"{index:04d}.jpg").write_bytes(JPEG)
            (box_dir / f"{index:04d}.json").write_text(
                json.dumps({"box": 3, "index": index, "game": "pokemon", "variant": "normal"})
            )
        # A SECOND BOX, because half of what a cart has to be checked for is that two legs
        # stay two: their own readings, their own runs, and a refusal on one taking the
        # whole send down rather than leaving the other half spawned.
        other_dir = home / "captures" / "cards" / "box7"
        other_dir.mkdir(parents=True)
        for index in (1, 2):
            (other_dir / f"{index:04d}.jpg").write_bytes(JPEG)
            (other_dir / f"{index:04d}.json").write_text(
                json.dumps({"box": 7, "index": index, "game": "pokemon", "variant": "normal"})
            )

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            # ---------------------------------------------------------- the money gate
            status, body, _ = request(
                port, "POST", "/pipeline/identify", payload={"box": 3}
            )
            checks.equal(
                (status, error_code(body)),
                (400, "confirm_required"),
                "the spending route refuses a well-formed request that did not say confirm "
                "— the gate is a field a stray request does not carry, not a typed string, "
                "because the owner ruled against typing on this control",
            )
            status, body, _ = request(
                port, "POST", "/pipeline/identify", payload={"confirm": True}
            )
            checks.equal(
                (status, error_code(body)),
                (400, "box_required"),
                "and confirm alone buys nothing: a run is always scoped to one box, so a "
                "confirm with no scope is refused rather than read as every box",
            )
            checks.equal(
                sorted(p.name for p in (home / "runs").iterdir())
                if (home / "runs").is_dir()
                else [],
                [],
                "and NEITHER refusal created a run directory — a refused request that left "
                "a run behind would put an empty row on the screen for every mis-tap",
            )

            # ------------------------------------------------------------- scope refusals
            for payload, expected_status, expected, label in (
                (
                    {"box": 3, "indices": []},
                    400,
                    "indices_invalid",
                    "an EMPTY selection is refused rather than read as the whole box — the "
                    "same refusal PUT /inventory/<box> makes, and for the harder reason "
                    "here: a selection that failed to send would become a run over 544 cards",
                ),
                (
                    {"box": 3, "indices": [1, "two"]},
                    400,
                    "indices_invalid",
                    "one bad member refuses the whole selection rather than being dropped "
                    "from it, which is the rule the finish claim already follows",
                ),
                (
                    {"box": 404},
                    404,
                    "box_has_no_captures",
                    "a box nothing was photographed into is refused by name, so a mistyped "
                    "box number cannot silently identify nothing and report success",
                ),
                (
                    {"box": 3, "indices": [90001]},
                    404,
                    "no_photos_in_scope",
                    "and a selection whose cards have no photographs on disk refuses too — "
                    "the scope directory is torn down rather than left empty behind it",
                ),
                (
                    {"box": 3, "max_edge": 99},
                    400,
                    "max_edge_invalid",
                    "max_edge is bounded: the flag reaches the child's argv, and a route "
                    "that passed any integer through would be an argv a request controls",
                ),
                (
                    {"box": 3, "retry_budget": 9},
                    400,
                    "retry_budget_invalid",
                    "as is retry_budget, which multiplies what a run submits",
                ),
            ):
                status, body, _ = request(
                    port, "POST", "/pipeline/preflight", payload=payload
                )
                checks.equal(
                    (status, error_code(body)), (expected_status, expected), label
                )

            checks.equal(
                sorted(entry.name for entry in (home / ".scopes").iterdir())
                if (home / ".scopes").is_dir()
                else [],
                [],
                "no scope directory survives a refusal, and none is under captures/cards/ "
                "in the first place — a directory of symlinks there would be walked by the "
                "next run pointed at the box above it and every card submitted twice",
            )

            # ------------------------------------------------- a send of several boxes
            #
            # THE CART, AND THE HALF THAT IS WORTH TESTING IS THE REFUSALS. A send that
            # spends is not reachable from here for the reason this section opens with, so
            # what these cases hold is the shape of the answer and every gate that stands
            # between a cart and an invoice.
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            single = json.loads(body)
            checks.equal(
                (status, len(single["scopes"]), single["scopes"][0]["scope"]["box"],
                 single["total"]["boxes"]),
                (200, 1, 3, 1),
                "a bare `box` answers as a CART OF ONE — the same read-side widening D3's "
                "amendment gives the finish claim, so every request written before the cart "
                "existed resolves down the identical path and no reader has to ask which "
                "response shape it got before it can ask anything else",
            )
            checks.equal(
                (single["total"]["photographs"], single["scopes"][0]["photographs"]),
                (2, 2),
                "and the total of one leg is that leg, computed on the SERVER — the figure "
                "the confirm is gated on is the one the operator agrees to spend, and a sum "
                "written in TypeScript would be a second cost model beside the printed one",
            )

            status, body, _ = request(
                port,
                "POST",
                "/pipeline/preflight",
                payload={
                    "scopes": [
                        {"box": 3, "crop": True, "max_edge": 1200},
                        {"box": 7, "crop": False, "max_edge": 1568},
                    ]
                },
            )
            cart = json.loads(body)
            checks.equal(
                (status, [leg["scope"]["box"] for leg in cart["scopes"]],
                 cart["total"]["boxes"], cart["total"]["photographs"]),
                (200, [3, 7], 2, 4),
                "two boxes answer as two legs IN THE ORDER SENT, each with its own console "
                "and figures, and the total sums them — the reading is per leg because "
                "which end of D32's frontier is right depends on what is in the drawer",
            )
            checks.ok(
                "\ncrop " in cart["scopes"][0]["console"]
                and "\ncrop " not in cart["scopes"][1]["console"],
                "and the per-leg reading REACHES THE CHILD: box 3's preflight printed its "
                "own crop line and box 7's did not, in one request — a cart that quietly "
                "applied one reading to every box would be a convenience bought with "
                "accuracy, and the line is the command's own rather than this route's",
            )

            for payload, expected, label in (
                (
                    {"scopes": []},
                    "scopes_invalid",
                    "an empty cart is refused rather than read as every box — the same "
                    "refusal an empty `indices` earns, for the same reason one register up",
                ),
                (
                    {"scopes": [{"box": 3}, "box seven"]},
                    "scopes_invalid",
                    "one member that is not an object refuses the whole cart rather than "
                    "being dropped from it, which is the rule the finish claim already "
                    "follows for a bad member",
                ),
                (
                    {"scopes": [{"box": 3}, {"box": 3}]},
                    "box_repeated",
                    "and a box named twice in one send is refused BEFORE anything spawns — "
                    "two legs over one box is two invoices for one answer, which is the "
                    "refusal a live run earns after the fact and this one earns before it",
                ),
                (
                    {"scopes": [{"box": 3} for _ in range(pipeline_routes.MAX_LEGS + 1)]},
                    "too_many_scopes",
                    "and a cart longer than the bound refuses rather than spawning a "
                    "process per element: the guard is against a malformed client, not "
                    "against an operator with a lot of boxes",
                ),
            ):
                status, body, _ = request(
                    port, "POST", "/pipeline/preflight", payload=payload
                )
                checks.equal((status, error_code(body)), (400, expected), label)

            status, body, _ = request(
                port,
                "POST",
                "/pipeline/preflight",
                payload={"scopes": [{"box": 3, "indices": [1]}, {"box": 7, "max_edge": 9}]},
            )
            checks.equal(
                (status, error_code(body)),
                (400, "max_edge_invalid"),
                "a bad flag in the SECOND leg refuses the whole send — every leg is "
                "resolved before any is acted on, because a loop that validated as it went "
                "would leave two boxes identifying and a third refused",
            )
            checks.equal(
                sorted(entry.name for entry in (home / ".scopes").iterdir())
                if (home / ".scopes").is_dir()
                else [],
                [],
                "and the scope directory the FIRST leg had already built is torn down with "
                "it — a refusal that left symlink directories behind would accumulate one "
                "per mis-typed cart, in the one directory identify walks recursively",
            )

            # ---------------------------------- a TICKED SELECTION reports its own scope
            #
            # THE SUBSET SCOPE WAS BUILT FIVE TIMES IN THIS FILE AND READ BACK ZERO. Every
            # other `indices` payload here refuses — an empty array, a bad member, a card with
            # no photograph, and the cart case directly above, which exists to prove leg two's
            # bad flag tears down leg one. So `_resolve_scope`'s selection branch returned a
            # dict nothing ever looked at: nulling its `box` left `make harness` at 7 of 7 and
            # `npx playwright test` at 224 passed. Measured, not supposed.
            #
            # WHAT IT WOULD COST IS NOT THE DOUBLE-CLICK GUARD, which is the tempting guess
            # and is wrong. `_run_box` reads the scope block FIRST and falls back to the
            # capture directory's name, and a scope directory is called `box3-1-<stamp>` — so
            # `^box(\d+)` still answers 3 and the guard below still fires. `_summary`'s `box`
            # and `box_name` (D56) go through `_run_box` too.
            #
            # WHAT IT COSTS IS THE MONEY SCREEN, which reads this block with no fallback at
            # all: `RunPanel.tsx` draws the per-box row of the cost breakdown from
            # `leg.scope.box`, keys each leg on it, labels each console with it, and
            # `_preflight_total` builds the `busy` list from it. D33 makes that the one screen
            # whose numbers must be unmissable, so a term that renders empty there is worth a
            # case.
            status, body, _ = request(
                port,
                "POST",
                "/pipeline/preflight",
                payload={"scopes": [{"box": 3, "indices": [1]}]},
            )
            answer = json.loads(body)
            checks.equal(
                (status, answer["scopes"][0]["scope"]),
                (200, {"box": 3, "whole_box": False, "cards": 1}),
                "a preflight over a TICKED SELECTION reports the box it is over, that it is "
                "not the whole box, and how many cards were ticked — the three facts the run "
                "panel draws per leg above the control that spends, and the three the "
                "manifest records for a run started this way",
            )
            checks.equal(
                answer["total"]["boxes"],
                1,
                "and one leg is one box, so a cart of selections cannot report a count that "
                "disagrees with the rows beneath it",
            )
            # THE COUNT IS OF TICKED CARDS AND NOT OF WHAT IS ON DISK, which is the half a
            # `whole_box` assertion alone would miss: this box holds two photographs and one
            # was ticked, so a `cards` that reported the directory's contents would read 2.
            checks.equal(
                len(list((home / "captures" / "cards" / "box3").glob("*.jpg"))),
                2,
                "— asserted against a box that holds MORE photographs than were ticked, so "
                "`cards: 1` is a statement about the selection rather than about the box",
            )
            # The scope directory this one built is swept with the others below; it is
            # symlinks, and `_sweep_scopes` is what `_scope_dir` calls on every press.

            # ------------------------------------------- the double-click guard, by BOX
            #
            # IT USED TO COMPARE CAPTURE-DIRECTORY PATHS, which works for a whole box and
            # cannot work for a ticked selection: `_scope_dir` builds a fresh
            # `.scopes/box3-<n>-<timestamp>` on every press, so two presses over one
            # selection were two paths and neither saw the other. The subset path had no
            # double-click guard at all.
            live = runs.create("box3")
            live.set(
                capture_dir=str(home / ".scopes" / "box3-1-1700000000"),
                scope={"box": 3, "whole_box": False, "cards": 1},
            )
            # This process, which is alive by construction — `_live_pid` checks with signal
            # 0 rather than trusting the file, so a pid belonging to nobody cannot make the
            # guard into a permanent lock.
            (live.directory / "running.pid").write_text(f"{os.getpid()}\n")
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            checks.equal(
                (json.loads(body)["scopes"][0]["busy_run"],
                 json.loads(body)["total"]["busy"]),
                (live.directory.name, [{"box": 3, "run": live.directory.name}]),
                "a live run over a SELECTION inside box 3 is found by a whole-box preflight "
                "for box 3 — the guard compares boxes now, and under the old path compare "
                "these two directories share no name at all",
            )
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 7})
            checks.equal(
                (json.loads(body)["scopes"][0]["busy_run"], json.loads(body)["total"]["busy"]),
                (None, []),
                "and box 7 is untouched by it — two runs over DIFFERENT boxes are fine and "
                "are not blocked, which is the whole reason a cart is one send rather than "
                "a queue",
            )
            status, body, _ = request(
                port,
                "POST",
                "/pipeline/identify",
                payload={"confirm": True, "scopes": [{"box": 7}, {"box": 3}]},
            )
            checks.equal(
                (status, error_code(body)),
                (409, "run_already_live"),
                "and a cart whose SECOND box is busy refuses whole — the live-run guard "
                "runs over every leg before the first child starts, so a busy box in the "
                "middle cannot leave the boxes before it spawned and paid for",
            )
            checks.equal(
                sorted(entry.name for entry in (home / "runs").iterdir()),
                [live.directory.name],
                "and NOTHING was spawned by it: the only run directory on disk is the one "
                "this case created by hand, so the refusal cost no invoice and left no row",
            )

            # A run started in a TERMINAL carries a capture directory and NO scope — `scope`
            # is written by the route and by nothing else — so the guard has to read the box
            # out of the path as well, or the screen could start a second batch over a box
            # an agent is already identifying.
            (live.directory / "running.pid").unlink()
            terminal = runs.create("box7")
            terminal.set(capture_dir=str(other_dir))
            (terminal.directory / "running.pid").write_text(f"{os.getpid()}\n")
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 7})
            checks.equal(
                json.loads(body)["scopes"][0]["busy_run"],
                terminal.directory.name,
                "a run started from a terminal — capture directory, no scope — still blocks "
                "the screen, because the box is read from the manifest's scope FIRST and "
                "from the directory name second, and only the second can see that run",
            )
            (terminal.directory / "running.pid").unlink()
            for stale in (live.directory, terminal.directory):
                shutil.rmtree(stale)

            # -------------------------------------------------- reading runs, and refusals
            status, body, _ = request(port, "GET", "/pipeline/runs")
            checks.equal(
                (status, json.loads(body)["runs"]),
                (200, []),
                "the run list answers an empty store with an empty list rather than a 404 "
                "— a screen that has done nothing yet is not an error",
            )
            status, body, _ = request(port, "GET", "/pipeline/runs/nope-01")
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_run"),
                "a run that does not exist answers in its own code",
            )
            status, body, _ = request(port, "GET", "/pipeline/runs/..")
            checks.equal(
                status,
                404,
                "and a name that is not a run name never reaches the filesystem at all — "
                "the route pattern admits no separator and no dot-dot",
            )

            # ------------------------------------------------- a real run directory, read
            made = runs.create("box3")
            made.set(capture_dir=str(box_dir), scope={"box": 3, "whole_box": True})
            (made.directory / "console.log").write_text("$ pkmnscan identify\nphotographs 2\n")
            (made.directory / "import-listed.csv").write_text("TCGplayer Id,Add to Quantity\n1,2\n")

            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            payload = json.loads(body)
            checks.equal(
                (status, payload["phase"], payload["live"]),
                (200, "ready", False),
                "a run with a manifest and no batch ids reads as `ready` and not live — the "
                "phase is DERIVED from the directory on every read, because cli/runs.py "
                "makes a run an immutable input and a phase held anywhere else would be a "
                "second answer to a question the files already answer",
            )
            checks.ok(
                "photographs 2" in payload["console"],
                "the console tail is served from the child's own log, so a screen polling "
                "this route reads exactly what the command printed",
            )
            checks.equal(
                sorted(row["name"] for row in payload["files"]),
                ["console.log", "import-listed.csv", "manifest.json"],
                "artefacts are listed off the DIRECTORY rather than off a table of names "
                "here — runs.import_listed_name makes the import files per-game, and a "
                "hard-coded list would stop offering them for every game added later",
            )
            checks.equal(
                [row["is_import"] for row in payload["files"] if row["name"].endswith(".csv")],
                [True],
                "and the import file is flagged as one, which is what lets the screen offer "
                "the download the owner actually came for",
            )

            # ------------------------------------------------- which drawer, and its name
            #
            # D56. The screens that list runs drew a box NUMBER and nothing else, on a store
            # whose boxes have been named since D20 — `#/pricing`'s picker offered
            # `2026-08-30-box3-01` over `15 SKUs` while the registry held `RB Epics`. The join
            # is the server's because the name lives in the store, which no screen drawing a
            # run list had read.
            checks.equal(
                (payload["box"], payload["box_name"]),
                (3, None),
                "a run reports the box it is over, and a box the registry has never heard "
                "of reports no name rather than an invented one — D20 leaves a name optional, "
                "so unnamed is an ordinary box and not a fault to mark",
            )

            capture_server.do_create_box({"box": 3, "name": "RB Epics"})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "RB Epics",
                "naming the box names the run, WITHOUT the run being touched — the join runs "
                "at read time against the registry, so nothing had to be written into a "
                "manifest that `cli/runs.py` makes an immutable input",
            )

            # THE ASSERTION THAT MAKES THE READ-TIME JOIN LOAD-BEARING, and the one a stored
            # name would fail. D20 makes a rename a live edit that relabels every card in the
            # box on every screen that draws one; a name copied into a run directory when the
            # run was created would go on saying `RB Epics` here forever.
            capture_server.do_put_box(3, {"name": "Riftbound epics"})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "Riftbound epics",
                "and a RENAME reaches the run on the next read, which is the property a name "
                "stored on the run could not have",
            )

            # A RUN WITH NO SCOPE BLOCK, which is what `pkmnscan identify captures/cards/box3`
            # leaves behind and what two of the four runs on the owner's own machine are.
            # `_run_box` reads the capture directory's own name for exactly this case, and the
            # name follows the number wherever the number came from.
            legacy = runs.create("box3")
            legacy.set(capture_dir=str(box_dir))
            status, body, _ = request(port, "GET", "/pipeline/runs")
            listed = {row["run"]: row for row in json.loads(body)["runs"]}
            checks.equal(
                (
                    listed[legacy.directory.name]["scope"],
                    listed[legacy.directory.name]["box"],
                    listed[legacy.directory.name]["box_name"],
                ),
                (None, 3, "Riftbound epics"),
                "a run started from a TERMINAL carries no scope block at all, and is still "
                "placed and named — the box comes off the capture directory's own name, "
                "which is the only thing that can see such a run",
            )
            checks.equal(
                listed[made.directory.name]["box_name"],
                "Riftbound epics",
                "and the LIST carries it as well as the single-run route, off one registry "
                "read for the whole list — this is the polled route, at 4s while anything is "
                "live, so a read per row would be a read per run per poll",
            )
            shutil.rmtree(legacy.directory)

            # ----------------------------------------------------------- the file download
            status, body, headers = request(
                port,
                "GET",
                f"/pipeline/runs/{made.directory.name}/file?name=import-listed.csv",
            )
            checks.equal(
                (status, headers.get("Content-Type")),
                (200, "text/csv"),
                "an import file downloads as CSV, which is the whole point of the route: "
                "before it, an emitted file existed only as a filename in terminal output "
                "the owner never saw when somebody else was driving the commands",
            )
            for name, expected in (
                ("../../etc/passwd", "file_name_invalid"),
                ("no-such-file.csv", "no_such_file"),
            ):
                status, body, _ = request(
                    port,
                    "GET",
                    f"/pipeline/runs/{made.directory.name}/file?name="
                    + urllib.parse.quote(name),
                )
                checks.equal(
                    error_code(body),
                    expected,
                    f"and {name!r} is refused as {expected} — matched by shape and THEN by "
                    f"membership of what this run lists, so a pattern loosened later still "
                    f"cannot reach outside the run directory",
                )

            # ----------------------------------------------------------- the free steps
            status, body, _ = request(
                port,
                "POST",
                f"/pipeline/runs/{made.directory.name}/identify",
                payload={},
            )
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_step"),
                "identify is NOT reachable as a step on a run — it costs money, so it has "
                "its own route and its own confirm rather than hiding among three free ones",
            )
            for payload, expected, label in (
                (
                    {"rule": "undercut:oops"},
                    "rule_invalid",
                    "a pricing rule is validated before it reaches argv",
                ),
                (
                    {"basis": "vibes"},
                    "basis_invalid",
                    "as is the basis",
                ),
                (
                    {"exports": []},
                    "exports_invalid",
                    "an empty exports array is refused rather than read as `re-use what the "
                    "manifest recorded` — absent means that, and the two must not collapse",
                ),
                (
                    {"exports": [{"name": "x.csv", "content": "not a spreadsheet"}]},
                    "export_not_csv",
                    "and a file with no comma on its first line is refused HERE rather than "
                    "several seconds later by an empty-catalog message about product lines",
                ),
            ):
                status, body, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{made.directory.name}/join",
                    payload=payload,
                )
                checks.equal((status, error_code(body)), (400, expected), label)

            # ------------------------------------------------------------- the decisions PUT
            status, body, _ = request(
                port,
                "PUT",
                f"/pipeline/runs/{made.directory.name}/decisions",
                payload={"decisions": {"rule": "match"}},
            )
            checks.equal(
                (status, error_code(body)),
                (409, "decisions_not_written"),
                "the pricing answer refuses a run that has not been joined — `join` is what "
                "writes decisions.json with every SKU that needs an answer already in it, "
                "and a route that created the file would invent the question as well",
            )
            (made.directory / runs.DECISIONS).write_text('{"rule": "match"}\n')
            status, body, _ = request(
                port,
                "PUT",
                f"/pipeline/runs/{made.directory.name}/decisions",
                payload={"decisions": {"rule": "undercut:5", "sub_threshold": "floor"}},
            )
            checks.equal(
                (status, json.loads((made.directory / runs.DECISIONS).read_text())),
                (200, {"rule": "undercut:5", "sub_threshold": "floor"}),
                "and once it exists the route replaces it wholesale — one document the "
                "operator is editing, and a merge would need this route to understand a "
                "schema it deliberately does not own",
            )
            status, body, _ = request(
                port,
                "PUT",
                f"/pipeline/runs/{made.directory.name}/decisions",
                payload={"decisions": "floor"},
            )
            checks.equal(
                (status, error_code(body)),
                (400, "decisions_invalid"),
                "a non-object answer is refused rather than written — emit owns what a "
                "disposition MEANS, but this route still owns what a document IS",
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def check_open_section(checks: Checks) -> None:
    """`POST /boxes/<box>/sections` — D10's divider, opened one at a time at the rig.

    THE ROUTE THE DECISION ENTRY HAD ALREADY DESCRIBED. D10 has said since 2026-08-23 that a
    box's dividers are "set by a **New section** control on the capture screen at the moment
    the real divider goes in", and until 2026-08-29 the only way to declare one was to type a
    whole layout into a field on `#/inventory`. This is that control's half of the wire.

    THE INDEX IS THE THING TO TEST, because it is the only thing the route decides. There is
    no index in the request — the store reads its own high-water mark inside the lock — so
    the case that matters is a box with a GAP in it, where a count and a high-water mark give
    different answers and only one of them is where the operator's hand will put the next
    card.

    ITS OWN ISOLATED HOME, which is this file's own repeated lesson: `check_boxes_and_listings`
    counts history lines over boxes it builds card by card, and a `resectioned` event written
    into its store would fail that section on this section's fixture.
    """
    checks.note("")
    checks.note("OPEN SECTION — server/capture_server.py, store/master.py (D10 amended)")

    with isolated_home():
        capture_server.do_create_box({"box": 4, "name": "S key"})
        with Store().write() as snapshot:
            for index in range(1, 41):
                snapshot.inventory.record_capture(master.Card(box=4, index=index))

        before = capture_server.do_boxes()["boxes"][0]
        checks.equal(
            before["sections"],
            [],
            "the box starts undeclared — no divider exists because nobody has put one in",
        )
        checks.equal(
            [(d["section"], d["start"], d["end"], d["count"]) for d in before["sections_detail"]],
            [(1, 1, 40, 40)],
            "and it renders as ONE section holding all forty cards, not as two of 25 "
            "(D10, amended 2026-08-29 — the 25-card default is deleted)",
        )

        row = capture_server.do_open_section(4, {})
        checks.equal(
            row["sections"],
            [1, 41],
            "one press puts a divider in front of the NEXT card — and materialises the "
            "implicit first one, because `check_sections` requires a layout to start at 1 "
            "and there is no card before the front of a box",
        )
        checks.equal(
            [(d["section"], d["start"], d["count"]) for d in row["sections_detail"]],
            [(1, 1, 40), (2, 41, 0)],
            "the answer carries the SERVER's own spans, which is what the receipt on the "
            "capture screen reads — the app does no section arithmetic",
        )
        checks.equal(
            join.Position(4, 41, (1, 41)).label,
            "Box 4 · Section 2 · Card 1",
            "so the next card captured is card 1 of section 2",
        )

        # THE HIGH-WATER MARK, WHICH IS THE WHOLE REASON THE ROUTE TAKES NO INDEX. Box 6
        # holds four records at 1, 2, 3 and 7 — a shape D10 makes ordinary, since every sale
        # and every retirement leaves a permanent gap. A count says the next card is 5. The
        # allocator says 8, and the allocator is the one that is right about where the hand
        # will put it, so a divider anywhere else would sit in front of a card that never
        # arrives. Observed failing against a count before this case was kept.
        with Store().write() as snapshot:
            for index in (1, 2, 3, 7):
                snapshot.inventory.record_capture(master.Card(box=6, index=index))
        checks.equal(
            capture_server.do_open_section(6, {})["sections"],
            [1, 8],
            "THE DIVIDER GOES AT `next_index`, NOT AT COUNT + 1 — a box with gaps in it "
            "would otherwise be divided in front of a card that will never be captured",
        )

        # THE STORE RAISES AND `_dispatch` NAMES THE CODE, so each refusal is asserted
        # twice: the exception here, and the string a client is actually told, on a socket
        # at the bottom of this section. That is the split `check_box_routes_and_search`
        # already draws for the sealed box, and it exists because an in-process call proves
        # nothing about the half that reaches a screen.
        checks.raises(
            master.SectionEmpty,
            lambda: capture_server.do_open_section(4, {}),
            "a second press with nothing captured between refuses: the section you just "
            "opened is still empty, so the divider asked for is already there",
        )
        checks.equal(
            capture_server.do_boxes()["boxes"][0]["sections"],
            [1, 41],
            "and the refusal moved nothing — no second divider, no rewritten layout",
        )

        refusal(
            checks,
            lambda: capture_server.do_open_section(4, {"at": 41}),
            "field_not_settable",
            "a body naming an index is refused rather than obeyed: the index is the "
            "store's to read, and a client that could send one could send a stale one",
        )

        # A DECLARED DIVIDER PAST THE FILL is legal (`_section_spans` renders it with a
        # count of zero) and is the one layout this route cannot append to, because the
        # divider it would add belongs BEHIND one that already exists.
        with Store().write() as snapshot:
            snapshot.inventory.record_capture(master.Card(box=5, index=1))
        capture_server.do_put_box(5, {"sections": [1, 51]})
        checks.raises(
            master.SectionAhead,
            lambda: capture_server.do_open_section(5, {}),
            "a divider already declared past the next card refuses, naming it — appending "
            "would make the layout unsorted, and `check_sections` would say so in a "
            "sentence about a list rather than about this box",
        )

        capture_server.do_put_box(4, {"state": "closed"})
        checks.raises(
            master.BoxClosed,
            lambda: capture_server.do_open_section(4, {}),
            "A SEALED BOX TAKES NO DIVIDER, for the reason it takes no card: there are no "
            "more cards to come, so the section would hold nothing, ever",
        )
        refusal(
            checks,
            lambda: capture_server.do_open_section(77, {}),
            "box_not_found",
            "and a box nothing in this store has ever seen is not divided into existence",
        )

        # ONE EVENT NAME, NOT TWO. `set_sections` already logs `resectioned` with both
        # layouts, which is everything a reader wants, and this store has been bitten by a
        # new name before: D26 records the day a state and a history event sharing a word
        # made months-old undo lines parse as states.
        events = [e for e in Store().history() if e.get("event") == "resectioned"]
        checks.equal(
            [(e.get("box"), e.get("sections_from"), e.get("sections_to")) for e in events],
            [(4, [], [1, 41]), (6, [], [1, 8]), (5, [], [1, 51])],
            "every press appends `resectioned` carrying both layouts — the same line the "
            "dividers editor writes, so history has one vocabulary for one fact",
        )
        checks.ok(
            all(e.get("event") not in master.STATES for e in events),
            "and the event name is not a card state, which is the trap D26 fell into",
        )
        checks.ok(
            all("position" not in e for e in events),
            "and carries no position: a divider is not at one, and a null there would read "
            "as a lost card",
        )

        # ------------------------------------------------------------------ on the wire
        #
        # THE PATH AND THE CODES, which are the whole of what a client sees. `do_*` calls
        # above prove the behaviour; only a socket proves that `POST /boxes/6/sections`
        # reaches it and that the store's three exceptions arrive as three distinct strings
        # rather than as one 500. `app/src/server.ts:openSection` branches on all three.
        # Card 8 of box 6, so the section opened at 8 above holds something and the wire
        # press below is a real one rather than the replay refusal.
        capture_server.do_capture(capture_payload(6))

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            status, body, _ = request(port, "POST", "/boxes/6/sections", payload={})
            checks.equal(
                (status, json.loads(body)["sections"]),
                (200, [1, 8, 9]),
                "the route is reachable at the path the client uses, and answers with the "
                "box row so the capture screen can redraw the box it is shooting",
            )
            for box, code, label in (
                (6, "section_empty", "a replayed press is a 409 `section_empty`"),
                (5, "section_ahead", "a divider ahead of the next card is 409 `section_ahead`"),
                (4, "box_closed", "and a sealed box is 409 `box_closed`, not a 500"),
            ):
                status, body, _ = request(port, "POST", f"/boxes/{box}/sections", payload={})
                checks.equal(
                    (status, error_code(body)),
                    (409, code),
                    label + " — each in its own code, because these strings reach a screen",
                )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def check_drain(checks: Checks) -> None:
    """The shutdown seam `scripts/serve.py` restarts through.

    Its own block and not part of `check_server_routes`, because it asserts nothing about a
    route: it is about what happens to a request that is ALREADY RUNNING when the process is
    told to stop. `store/session.py:Store.write()` replaces four JSON files in sequence — each
    atomic alone, none atomic as a set — so a kill landing between them leaves a torn store.
    That risk exists at Ctrl-C frequency today and the supervisor multiplies it, which is what
    makes this seam worth an assertion rather than a comment.

    THE OBVIOUS IMPLEMENTATION CANNOT WORK AND THAT IS WHY THIS IS TESTED. `ThreadingHTTPServer`
    sets `daemon_threads = True`, and `socketserver._Threads.append` discards a daemon thread —
    so the join inside `server_close()` is already a no-op and looks exactly like a drain that
    works. A version that counted threads would pass a smoke test and lose requests in
    production.
    """
    checks.note("")
    checks.note("GRACEFUL DRAIN — server/capture_server.py")

    checks.equal(capture_server.inflight(), 0, "nothing is in flight at rest")
    checks.ok(capture_server.drain(0.2), "and a drain over an idle server returns at once")

    # DERIVED, NOT A LITERAL. A capture posted while `./pkmnscan identify` holds the store lock
    # legitimately waits `LOCK_TIMEOUT_SECONDS` before answering `store_busy`, so a drain
    # shorter than that would cut a request that was behaving correctly. Asserting the
    # arithmetic rather than the number means it moves the day the lock timeout does.
    checks.equal(
        capture_server.DRAIN_SECONDS,
        files.LOCK_TIMEOUT_SECONDS + 5,
        "the drain outlasts the store lock, so a legitimate store_busy is never cut short",
    )

    entered = threading.Event()
    release = threading.Event()

    def occupy() -> None:
        capture_server._inflight_enter()
        entered.set()
        release.wait(10)
        capture_server._inflight_leave()

    worker = threading.Thread(target=occupy, daemon=True)
    worker.start()
    entered.wait(5)

    checks.equal(capture_server.inflight(), 1, "a request in flight is counted")
    checks.ok(
        not capture_server.drain(0.3),
        "and a drain REFUSES to return while it is still running — the whole point",
    )

    release.set()
    worker.join(5)
    checks.equal(capture_server.inflight(), 0, "the counter falls when the request finishes")
    checks.ok(capture_server.drain(0.5), "and the drain then returns true")


def run() -> Result:
    checks = Checks()
    check_pipeline_routes(checks)
    check_emit_bypass(checks)
    check_pricing_authority(checks)
    check_withholding(checks)
    check_pricing_route(checks)
    check_allocator(checks)
    check_boxes_and_listings(checks)
    check_store(checks)
    check_server_routes(checks)
    check_drain(checks)
    check_undo(checks)
    check_remove_and_box_delete(checks)
    check_queues(checks)
    check_queue_starvation(checks)
    check_listing_release(checks)
    check_queue_supersede(checks)
    check_review_answer(checks)
    check_group_answer(checks)
    check_mark_sold(checks)
    check_retire(checks)
    check_reshoot(checks)
    check_history(checks)
    check_sidecar_seam(checks)
    check_capture_claim_chain(checks)
    check_game_and_note_seam(checks)
    check_box_routes_and_search(checks)
    check_box_names(checks)
    check_box_claims(checks)
    check_place_neighbors(checks)
    check_open_section(checks)
    check_consolidated_numbering(checks)
    check_concurrency(checks)
    check_origin_gate(checks)
    check_photo_cache(checks)
    check_cli_seams(checks)
    check_code_ledger(checks)
    check_review_stand_down(checks)
    check_review_catalog(checks)
    check_run_realignment(checks)
    check_printed_code_profiles(checks)
    check_cli_refusals(checks)
    check_listing_commands(checks)
    check_crop_preview(checks)
    return checks.result(
        "store/, server/ and cli/ — the packages no harness test reached before this one."
    )
