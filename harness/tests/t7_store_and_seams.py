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

WHAT THIS DELIBERATELY DOES NOT COVER. Undo, mark-sold and the pull routes do not exist
yet; they arrive with build-order step 7 and their assertions arrive with them. D10 already
settles what undo must do — delete rather than tombstone, newest capture in a box only,
refused once the card's row has been written into an import file — so those cases are
writable the day the route is.
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
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.tests import Checks, Result  # noqa: E402

from cli import resolve, runs  # noqa: E402
from identify import sidecar  # noqa: E402
from pipeline import join, tcgcsv, variant  # noqa: E402
from server import capture_server  # noqa: E402
from store import files, master  # noqa: E402
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
    check_sidecar_seam(checks)
    check_concurrency(checks)
    check_cli_seams(checks)
    check_cli_refusals(checks)
    return checks.result(
        "store/, server/ and cli/ — the packages no harness test reached before this one."
    )
