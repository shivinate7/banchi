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

`check_history` LANDED ON 2026-08-13 WITH THE LINES IT ASSERTS. Three routes here write
without moving a card between states — the PUT correction, the undo and the review answer —
and until that day none of them appended anything to `history.jsonl`, which `docs/DEBTS.md`
carried as a known gap. The section asserts the part that cannot be recovered afterwards: the
value a correction replaced, the boundary between two physical cards at one reused position,
and which queue's offer a human chose from. It also asserts the two properties that make the
new lines safe in a file another route reads — that no event name is a listing state, and
that a logged event is discarded when the write it rides in raises.

WHAT THIS STILL DOES NOT COVER, and it is the important sentence in this file now. These
three routes were built before Gate B, which `docs/specs/capture-app.md` scheduled them
after. Every queue entry they have ever been handed was hand-built — by the harness below,
or by hand in a browser — so what is asserted here is that the routes behave as
`docs/DESIGN.md` describes, NOT that a real run produces entries of this shape. A green T7
says the same thing about 7b that a green T6 says about geometry: it is self-consistent.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.tests import Checks, Result  # noqa: E402

from cli import resolve, runs  # noqa: E402
from identify import sidecar  # noqa: E402
from pipeline import join, tcgcsv, variant  # noqa: E402
from server import capture_server  # noqa: E402
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

# Two rows the pipeline would have offered for one collector number, built through
# `cli/resolve.py:_candidate_rows`'s six keys rather than by hand, so the shape 7b's routes
# read cannot drift from the shape `join` writes. The pair differs only by finish, which is
# the case D3 rung 4 sends to review and the case the review screen exists for.
#
# HAND-BUILT, AND THAT IS THE LIMIT OF WHAT THESE CASES PROVE. No run has ever produced a
# queue entry — Gate B is where the first one comes from — so these assert the routes against
# `docs/DESIGN.md`, not against reality. Recorded here rather than only in the module
# docstring because this literal is where the assumption physically lives.
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

    `allocate_capture` is the one piece of step-5 logic Gate B exercises twenty times in a
    row, and it is the only place in the project that decides where a physical card is.
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
        not master.Inventory().set_state("99/99", master.PUSHED),
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
        checks.equal(
            capture_server.do_photo(3, 1), JPEG, "GET /photo returns the stored bytes"
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
            ("set_hint", "variant"),
            "and the settable set is exactly set_hint and variant",
        )

        # Three captures reached this box, not four: the replay above returned the third
        # card rather than creating one. Counting it here is the mistake the retry guard
        # exists to prevent, so the count is the assertion.
        report = capture_server.do_status()
        checks.equal(report["cards"], 3, "GET /status counts every card, and a replay is not one")
        checks.equal(report["next_index"]["3"], 4, "and reports the next index per box")
        checks.ok("problem" not in report, "and reports no problem on a healthy store")

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
            "D10's 25-cards-per-section rule living in the app",
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
        checks.equal(
            broken_inventory["cards"]["3/2"]["label"],
            join.Position(3, 2).label,
            "and one bad record does not take the route down: every other row keeps its "
            "label, on the route the app polls",
        )


# ------------------------------------------------------------------------------------ undo


def check_undo(checks: Checks) -> None:
    """DELETE /inventory/<box>/<index> — the one route the capture app added.

    THE ONLY ROUTE IN THIS SERVER THAT DESTROYS ANYTHING, which is why it gets a section of
    its own rather than a few more lines beside the other refusals. Every other write here
    adds a record or corrects a field, and the worst a bug in one of them does is record
    something wrong. A bug in this one deletes a photograph of a card that is back in the
    box by the time anybody notices.

    The three rules are D10's and they are asserted as rules, not as one happy path: what
    it deletes, that it deletes only the newest, and that it stops once `emit` has written
    the card's row into an import file.
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

        # Allowed at `identified`: the model has answered, money is already spent, and
        # nothing outside this Mac knows the card exists. Deleting it costs the fee, which
        # is the trade D10 names.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.IDENTIFIED)
        capture_server.do_delete_card(3, 3)
        checks.ok(
            Store().read().inventory.get("3/3") is None,
            "undo at `identified` is ALLOWED — only the identification fee is lost",
        )

        # Refused at `pushed`: `emit` has written the card's row into an import file, and a
        # file on disk would now disagree with the inventory.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/2", master.PUSHED)
        refusal(
            checks,
            lambda: capture_server.do_delete_card(3, 2),
            "undo_too_late",
            "undo at `pushed` refuses: its row is already in an import file",
        )
        checks.ok(
            Store().read().inventory.get("3/2") is not None
            and capture_server.photo_path(3, 2).is_file(),
            "and the refusal reached neither the record nor the photo",
        )

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
            (master.CAPTURED, master.IDENTIFIED),
            "undo is allowed at exactly captured and identified, named as an allowlist so a "
            "new state is refused by default",
        )

        # EVERYTHING KEYED BY THE POSITION GOES, not the card record alone. The snapshot
        # carries the two standing queues and the identification cache as well, and
        # `Store.write()` writes all four files back on the way out — so a route that edits
        # only `inventory.cards` does not leave the others alone, it commits them unchanged
        # around a position that no longer exists.
        #
        # This is not a corner case, which is why it is set up in full rather than asserted
        # on a bare card. `cli/cmd_emit.py` marks only MATCHED positions `pushed`, so a card
        # that went to a queue stays `identified` — and `identified` is inside
        # UNDOABLE_STATES. The undoable set and the queued set overlap by construction, and
        # a queued card is precisely the one carrying a paid answer and a photo path.
        _, queued = capture_server.do_capture(capture_payload(3))
        queued_key = queued["key"]
        with Store().write() as snapshot:
            snapshot.inventory.set_state(queued_key, master.IDENTIFIED)
            snapshot.review.upsert(
                queues.QueueEntry(
                    position=queued_key,
                    box=queued["box"],
                    index=queued["index"],
                    label=queued["label"],
                    photo=str(capture_server.photo_path(queued["box"], queued["index"])),
                    reason="low_confidence",
                    market="12.00",
                )
            )
            snapshot.parked.upsert(
                queues.QueueEntry(
                    position=queued_key,
                    box=queued["box"],
                    index=queued["index"],
                    label=queued["label"],
                    reason="no_market_data",
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
    methods = dict(capture_server.CORS_HEADERS)["Access-Control-Allow-Methods"]
    checks.ok(
        "DELETE" in methods,
        "CORS advertises DELETE — a preflight that omits it refuses the undo at the browser",
        f"methods: {methods}",
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


# ------------------------------------------------------------------------------ mark sold


def check_mark_sold(checks: Checks) -> None:
    """POST /inventory/<box>/<index>/sold — D10's sale, and the server half of undo.

    TWO RULES, AND THEY PULL IN OPPOSITE DIRECTIONS. A sale must not remove anything — the
    record and the position both survive, permanently — while the undo `docs/DESIGN.md`
    requires on every mark-sold must put back the exact state the card came from, which for a
    real order pull is as likely to be `pushed` or `staged` as `live`.
    """
    checks.note("")
    checks.note("MARK SOLD — POST /inventory/<box>/<index>/sold")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            for state in (master.PUSHED, master.STAGED, master.LIVE):
                snapshot.inventory.set_state("3/1", state)
            snapshot.inventory.set_state("3/2", master.PUSHED)

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
        checks.equal(sold["previous_state"], master.LIVE, "naming the state it came from")
        checks.equal(
            sold["restores_to"],
            master.LIVE,
            "and what an undo would put back, so the control can be offered — or not — at "
            "the moment of the sale rather than at the tap that would have failed",
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
        checks.equal(back["state"], master.LIVE, "and puts the card back where it was")
        checks.equal(back["previous_state"], master.SOLD, "from sold")
        checks.equal(
            back["restores_to"], None, "with nothing left to reverse"
        )
        checks.equal(
            Store().read().inventory.get("3/1").state,
            master.LIVE,
            "and the store agrees",
        )
        checks.equal(
            [e.get("event") for e in events_for("3/1")],
            [master.CAPTURED, master.PUSHED, master.STAGED, master.LIVE, master.SOLD, master.LIVE],
            "history reads `live, sold, live` — a reversal is two real transitions and needs "
            "no event of its own, which is why this route added none when the three writes "
            "beside it did (see `check_history`)",
        )

        refusal(
            checks,
            lambda: capture_server.do_mark_sold(3, 1, {"undo": True}),
            "not_sold",
            "and reversing a card that is not sold refuses in its own code",
        )

        # THE REASON THE PRIOR STATE IS READ AND NOT ASSUMED. An order pull before any
        # Export From Staged has been run touches cards at `pushed`; restoring one of those
        # to `live` would claim TCGplayer is showing quantity against a SKU it has never
        # been told about.
        pushed = capture_server.do_mark_sold(3, 2, {})
        checks.equal(
            pushed["restores_to"],
            master.PUSHED,
            "a card sold out of `pushed` restores to PUSHED, not to live — the reversal is "
            "exact rather than assuming the card was listed",
        )
        checks.equal(
            capture_server.do_mark_sold(3, 2, {"undo": True})["state"],
            master.PUSHED,
            "and the reversal actually puts that state back",
        )

        # ASSUMPTION, asserted so a later change to it is visible rather than silent.
        # Neither docs/DESIGN.md nor D10 says which states may be sold from, and the route
        # is permissive: refusing a card that was never pushed would leave a person holding
        # a card he has genuinely sold with no way to record it. Gate B settles it.
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
    methods = dict(capture_server.CORS_HEADERS)["Access-Control-Allow-Methods"]
    checks.ok(
        "POST" in methods,
        "CORS advertises POST, which both 7b writes travel on",
        f"methods: {methods}",
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
        checks.equal(
            corrected.get("changed"),
            {"metadata_finish": {"from": "holo", "to": "reverse_holo"}},
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

        with Store().write() as snapshot:
            snapshot.inventory.set_state("4/2", master.IDENTIFIED, sku="8608860")
            snapshot.cache.put("4/2", {"name": "Rhyhorn"}, "sha-of-photo", "prompt-1")
        capture_server.do_delete_card(4, 2)
        paid = last_event("4/2")
        checks.equal(
            paid.get("state"),
            master.IDENTIFIED,
            "undoing an IDENTIFIED card records that state, which is the one that cost money",
        )
        checks.ok(
            paid.get("cache_deleted") is True and paid.get("sku") == "8608860",
            "and records that the paid answer went with it, and what it had said",
            f"event was: {paid!r}",
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

        # ----------------------------------------------- and none of them is a state
        checks.equal(
            sorted(set(capture_server.SERVER_EVENTS) & set(master.STATES)),
            [],
            "no server event shares a name with a listing state — _state_before_sale scans "
            "this file for the last event naming a state, so a collision would restore a "
            "reversed sale to `corrected`",
        )

        # THE PATH THAT COLLISION WOULD BREAK, walked end to end rather than argued. A card
        # corrected after it went live has a `corrected` line sitting directly under its
        # `sold` line, which is exactly where the backwards scan starts looking.
        capture_server.do_capture(capture_payload(6))
        with Store().write() as snapshot:
            for state in (master.PUSHED, master.STAGED, master.LIVE):
                snapshot.inventory.set_state("6/1", state)
        capture_server.do_put_card(6, 1, {"set_hint": "sv9"})
        sold = capture_server.do_mark_sold(6, 1, {})
        checks.equal(
            sold["restores_to"],
            master.LIVE,
            "a card corrected between going live and being sold still restores to LIVE — "
            "the scan skips every non-state event, which is what makes the new lines safe "
            "to add to a file another route reads",
        )
        checks.equal(
            capture_server.do_mark_sold(6, 1, {"undo": True})["state"],
            master.LIVE,
            "and the reversal actually puts that state back, past the correction",
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
        checks.equal(
            first.metadata_finish, "reverse_holo", "and so does the capture-time variant"
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
            "holo",
            "a PUT correction reaches the SIDECAR, which is what identify reads",
        )

        capture_server.do_put_card(3, 1, {"set_hint": "sv3pt5"})
        after = sidecar.scan(capture_server.captures_root())[0]
        checks.equal(after.set_hint, "sv3pt5", "a hint-only PUT updates the hint")
        checks.equal(
            after.metadata_finish,
            "reverse_holo",
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


# ------------------------------------------------------------------------- command seams


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

    # `cli/resolve.py:load` whitelists the detected finish against a literal tuple rather
    # than against the enum. If the two drift, a valid finish is dropped on the floor and
    # D3 rung 3 never fires — the cross-check that catches a mis-sorted card.
    source = (Path(__file__).resolve().parents[2] / "cli" / "resolve.py").read_text("utf-8")
    checks.ok(
        all(f'"{finish}"' in source for finish in variant.FINISHES),
        "resolve.py's finish whitelist still covers every value in variant.FINISHES",
        f"FINISHES is {variant.FINISHES}",
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


# ------------------------------------------------------------------------------------ run


def run() -> Result:
    checks = Checks()
    check_allocator(checks)
    check_store(checks)
    check_server_routes(checks)
    check_undo(checks)
    check_queues(checks)
    check_queue_supersede(checks)
    check_review_answer(checks)
    check_mark_sold(checks)
    check_history(checks)
    check_sidecar_seam(checks)
    check_concurrency(checks)
    check_cli_seams(checks)
    check_cli_refusals(checks)
    return checks.result(
        "store/, server/ and cli/ — the packages no harness test reached before this one."
    )
