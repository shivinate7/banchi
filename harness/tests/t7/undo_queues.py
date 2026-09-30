"""T7 group: undo, removal, queues, review answers, sold, retire, reshoot.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import base64
import json
import hashlib

from datetime import datetime, timedelta, timezone
from typing import Optional
from harness.tests import Checks
from cli import requeue, resolve
from pipeline import corpus, join, tcgcsv
from server import capture_server
from store import files, master, photos, queues
# `orders` is already `pipeline.orders` above. The store's ledger is a DIFFERENT module
# — the resolver computes and stores nothing, this one persists — so it takes an alias
# rather than shadowing the name half this file's order cases are written against.
from store import orders as order_store
from store.session import Store
from harness.tests.t7.common import (
    CANDIDATES,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    NEVER_BOUND_IDENTITY_SNAPSHOT,
    _bind,
    _seed_sku_table,
    answers,
    append_history,
    back_of,
    capture_named,
    capture_payload,
    corrupt_history,
    entry,
    events_for,
    isolated_home,
    last_event,
    photo_of,
    refusal,
    run_photo,
    seam_run,
    sent_image,
    stored_captures,
    stored_label,
    stored_payloads,
    write_export,
)

# A second, distinguishable blob for the re-shoot cases: same magic, different bytes, so
# "the old photo is GONE" (D26: replaced, not archived) is a comparison this file can lose.
JPEG_RESHOT = b"\xff\xd8\xff" + b"\x11" * 64

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

        photo = photo_of(3, 3)
        sidecar_file = capture_server.sidecar_path(photo)
        checks.ok(
            photo.is_file() and sidecar_file.is_file(),
            "three captures into box 3, and the newest has both a photo and a sidecar",
        )

        def on_hand_in(box: int) -> int:
            """Box `box`'s on-hand cards, counted off the store itself (F5, the PR 2
            integration review): every record in the box that has not left it."""
            return sum(
                1
                for card in Store().read().inventory.cards.values()
                if card.box == box and card.state not in master.TERMINAL_STATES
            )

        body = capture_server.do_delete_card(3, 3)
        checks.equal(body["deleted"], "3/3", "undo answers with the position it removed")
        checks.equal(
            body["on_hand"],
            on_hand_in(3),
            "and its on_hand is the box's own count after the undo (D58, R1d): the capture "
            "screen writes this number straight onto the box row",
        )
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
            len(stored_captures()),
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
            (body["on_hand"] - second["on_hand"], second["on_hand"]),
            (1, on_hand_in(3)),
            "and on_hand steps down by exactly the one card that left",
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
            undoable = capture_server.do_inventory()["cards"]["3/3"].get("label")
            checks.ok(
                bool(undoable) and str(undoable) in str(caught),
                "and the refusal NAMES the position that is undoable — otherwise the app "
                "has to ask again to find out. It names it the way the card row does: the "
                "box's name, the section and the card in the section, never the number",
                f"message was: {caught}; label: {undoable}",
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
                all(word in str(caught) for word in ("re-shoot", "retire", "delete")),
                "and the refusal names all three remedies: re-shoot, retire, and the "
                "mid-box remove — which one is right depends on what is wrong with the "
                "card, and only the operator knows that",
                f"message was: {caught}",
            )
        checks.ok(
            Store().read().inventory.get("3/3") is not None
            and photo_of(3, 3).is_file(),
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
        checks.equal(
            gone["on_hand"],
            on_hand_in(3),
            "remove answers the box's own on_hand count after the card left (D58, R1d)",
        )
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
            snapshot.inventory.set_state("3/2", master.IDENTIFIED)
            _bind(snapshot, "3/2", "8608859", condition="Near Mint Holofoil")
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
            and photo_of(3, 2).is_file(),
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
                    # The capture's own answer, which is where the path came from in the
                    # first place — no second derivation, and no store read inside a write.
                    photo=queued["photo"],
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

# A DATE OUT OF THE COHORT THIS MODULE WAS BUILT FOR, not an invented one. `cli/requeue.py`'s
# own measurement groups the owner's store by `first_seen` and the 230 entries in the
# 2026-08-24…09-02 band are the frozen ones — none carries `rarity`, none was filtered to Near
# Mint, and no live run covers their boxes. An entry seeded with today's date could not fail
# the case below, because `Queue.upsert` writes today's date when it finds none.
FROZEN_SEEN = "2026-08-24"

def check_queue_refresh(checks: Checks) -> None:
    """`cli/requeue.py` — every OPEN entry re-resolved against a current export, store-wide.

    WHY THE MODULE EXISTS IS A MEASUREMENT AND NOT AN ARGUMENT. `queues.upsert` is the only
    thing that ever refreshes an entry and it is reachable from one place — a join, which is
    scoped to a run, which is scoped to a box. 513 of the owner's 565 stored entries sit over
    boxes no live run covers, so the two fixes of 2026-09-11 (`rarity` on every candidate row,
    D137's Near Mint rule) are correct in the code and will never reach them.

    SO WHAT THIS SECTION WORKS HARDEST IS WHAT THE PASS LEAVES ALONE, not what it rewrites. A
    refresh pointed at a whole store is one command away from every answer the operator has
    ever given, and three of the four cases here are about something that must NOT move: a
    cleared entry, a departed card's question, and how long an entry has been waiting.

    THE CLEARED ENTRY IS THE NON-NEGOTIABLE (D28), AND ITS GUARD IS NOT IN THIS MODULE. The
    two refusals live in `Queue.upsert` and `Queue.release`, which is why `RefreshPlan.apply`
    is one line — so the assertion below is over the SEAM rather than over a branch, and it
    compares the STORED PAYLOAD before against after rather than reading the flag back. A pass
    that re-queued an answer and a pass that merely refreshed one are the same shape from
    everywhere except the bytes.

    IDEMPOTENCE IS THE OTHER HALF, and it is the property D87 names as the one that separates
    the two designs: if a second pass over the written store reports work to do, then either
    the pass is not writing what it planned or it is planning off something that moves. Both
    are silent, and both are fatal to a command that is meant to be re-runnable and free.
    """
    checks.note("")
    checks.note("QUEUE REFRESH — cli/requeue.py, store-wide")

    # Six positions, one per shape the pass has to tell apart. Dunsparce 120/159 carries two
    # condition rows so the catalog cannot settle it alone (ambiguous — stays queued);
    # Articuno 161/159 is holofoil-only, so the catalog settles it on its own (D3 rung 2) and
    # the entry LEAVES. The last three are the three terminal states.
    READINGS = {
        1: ("Dunsparce", "120"),  # refreshes in place
        2: ("Articuno", "161"),   # resolves — leaves the queue
        3: ("Dunsparce", "120"),  # answered by a human
        4: ("Dunsparce", "120"),  # sold
        5: ("Dunsparce", "120"),  # retired
        6: ("Dunsparce", "120"),  # moved
    }

    with isolated_home() as home:
        for _ in READINGS:
            capture_server.do_capture(capture_payload(1))

        export = write_export(home / "refresh-export.csv")
        catalogs, _, unreadable = requeue.catalogs_from([export])
        checks.equal(
            sorted(catalogs),
            ["pokemon"],
            "the export answers for the game its CELLS carry and never for its filename "
            "(D25). It claims `pokemon_code` out of the same `Product Line` column and "
            "holds no Code Card row, so that game gets no catalogue and its cards would "
            "be skipped as `no_export` rather than resolved against somebody else's rows",
        )
        checks.equal(
            [why.split(":")[0] for _, why in unreadable],
            ["pokemon_code"],
            "and the game it could not cut a catalogue for is NAMED, not dropped",
        )
        # The STORE's cut-off and rule, which is what `cli/cmd_queue.py` hands in: a refresh
        # routing against `pricing.THRESHOLD` while the operator's store said something else
        # would re-queue by one figure the cards a join queued by another (D9).
        threshold, rule, basis = requeue.policy_of(corpus.Corpus.read())

        with Store().write() as snapshot:
            for index, (name, number) in READINGS.items():
                snapshot.inventory.record_identification(
                    master.position_key(1, index),
                    name=name,
                    number=number,
                    printed_total="159",
                    confidence="high",
                )
            # EACH TERMINAL STATE THROUGH THE DOOR THAT SETS IT, never by assigning `state`:
            # `move_card` writes `moved_to` and leaves a live record in box 2, and `retire`
            # writes `retire_reason`. A hand-set state would be a card no route could produce.
            snapshot.inventory.set_state("1/4", master.SOLD)
            _bind(snapshot, "1/4", DUNSPARCE_SKU, condition="Near Mint")
            snapshot.inventory.retire("1/5", "damaged")
            snapshot.inventory.move_card("1/6", 2)

            # STALE ENTRIES, which is the state the 513 are in: `entry()`'s three candidate
            # rows and a reason no current join would write for these readings, so a refresh
            # that reaches a position is visible and one that does not is visible too.
            # AND ONE OFF-CONDITION CANDIDATE, which is the OTHER 2026-09-11 fix the frozen
            # entries cannot see (D137 — this lists Near Mint). Seeded here rather than in
            # the module's shared `CANDIDATES`, which several other checks pin: this row
            # belongs to the BEFORE side of one fixture, and the refresh's own candidate rows
            # come from the catalogue, so nothing else moves.
            stale_off_condition = {
                "sku": "8608861",
                "name": "Articuno",
                "set": "SV09",
                "number": "161/159",
                "condition": "Lightly Played Holofoil",
                "market": "9.10",
            }
            for index in READINGS:
                snapshot.review.upsert(
                    entry(
                        1,
                        index,
                        candidates=[
                            *(dict(row) for row in CANDIDATES),
                            dict(stale_off_condition),
                        ],
                    )
                )
                # AFTER the upsert, because `upsert` stamps today's date when it finds no
                # existing entry — seeding `first_seen` through `entry()` would be overwritten
                # by the very function the case below is about.
                snapshot.review.entries[master.position_key(1, index)].first_seen = FROZEN_SEEN
            snapshot.review.entries["1/3"].cleared_by_human = True

        stored_before = stored_payloads("queues", {"queue": queues.MAIN})
        untouchable = {
            key: json.dumps(stored_before[key], sort_keys=True)
            for key in ("1/3", "1/4", "1/5", "1/6")
        }

        snapshot = Store().read()
        plan = requeue.plan(
            snapshot.inventory,
            snapshot.review,
            snapshot.parked,
            catalogs,
            threshold=threshold,
            rule=rule,
            basis=basis,
        )

        # ------------------------------------------------------------------- the preview
        checks.equal(
            plan.cleared,
            1,
            "the pass COUNTS the answered entry and never opens it — `_open_by_position` "
            "walks `open_entries`, which hides a cleared one, so it is reported as left "
            "alone rather than examined and passed over",
        )
        checks.equal(
            plan.examined,
            5,
            "five open entries examined: the answered one is not among them",
        )
        checks.equal(
            sorted((skip.position, skip.reason) for skip in plan.skipped),
            [
                ("1/4", requeue.DEPARTED),
                ("1/5", requeue.DEPARTED),
                ("1/6", requeue.DEPARTED),
            ],
            "A DEPARTED CARD IS SKIPPED BY NAME, one reason per state (D26, D83). Sold, "
            "retired and moved are all `TERMINAL_STATES`: the physical copy is gone, so a "
            "refreshed question about it would spend a person's attention on a card they "
            "cannot look at",
        )
        queued_now = {e.position for e in (*plan.main, *plan.parked)}
        checks.ok(
            not queued_now & {"1/4", "1/5", "1/6"},
            "and it is NOT RE-QUEUED: a skipped position is in neither bucket, so `apply` "
            "has nothing to write over it. Measured on a reconstruction of the owner's "
            "store: six of box 4's entries sit over sold cards, and without the state test "
            "the refresh re-queued every one",
        )
        checks.ok(
            not plan.freed & {"1/4", "1/5", "1/6"},
            "and NOT RELEASED either, which is the conservative half: a refresh has no "
            "opinion about a card it will not resolve, and releasing on a state change "
            "would make it a queue-cleaner rather than the command that was argued for",
        )
        checks.equal(
            [e.position for e in plan.main],
            ["1/1"],
            "the ambiguous card is re-queued to main against the current catalogue",
        )
        checks.equal(plan.parked, [], "and nothing parks: both seam rows are above the cut-off")
        checks.equal(
            plan.freed,
            {"1/2"},
            "the card the catalog settles is FREED — `processed - queued_now`, scoped to "
            "what this pass actually re-resolved (cli/cmd_join.py's own scoping)",
        )
        checks.equal(
            plan.photo_moved,
            0,
            "and no position is re-bound: every entry names the photograph the card at its "
            "key still holds, so this fixture is not quietly exercising D10's slide",
        )

        # ------------------------------------------------- the REPAIR COUNT, not the outcome
        #
        # WHAT THE COMMAND REPORTS, ASSERTED AS A NUMBER. Everything above is an OUTCOME —
        # which entries end up queued, with which rows, released or left alone — and an
        # outcome assertion cannot see a saving or a miscount. `Change.changed` decides how
        # many entries this pass says it repaired, and `cli/cmd_queue.py` prints those
        # figures and SKIPS THE WRITE ENTIRELY when they are zero. So a `changed` that always
        # answered False would leave every assertion above green (they read `plan.main`,
        # `plan.freed` and the written store, none of which consult it), report "nothing to
        # write", and silently do nothing on the operator's real store.
        #
        # The decision entry publishes these as the repair — 340 resolve and 97 refresh over
        # the owner's 513 frozen entries — so the classification is a claim in its own right
        # and is checked as one here.
        checks.equal(
            (plan.touched, len(plan.refreshed), len(plan.resolved), plan.unchanged),
            (2, 1, 1, 0),
            "THE COUNTS THE COMMAND PRINTS: two entries change, one refreshed in place and "
            "one resolved away, and nothing is left unchanged. A classification that said "
            "zero would skip the write and report success",
        )
        checks.equal(
            [c.position for c in plan.refreshed],
            ["1/1"],
            "and the refreshed one is named, so the count cannot be right for the wrong entry",
        )
        checks.equal(
            [c.position for c in plan.resolved],
            ["1/2"],
            "as is the resolved one",
        )
        checks.equal(
            sum(c.dropped_off_condition for c in plan.refreshed),
            1,
            "and the off-condition row this pass stopped offering is COUNTED: the stale "
            "entry carried a Lightly Played candidate that D137's rule drops, which is one "
            "of the two 2026-09-11 fixes the 513 frozen entries could never see. Summed "
            "over the REFRESHED changes alone — a resolved entry has no `after`, so every "
            "row it used to offer counts as dropped and would make this figure say two",
        )
        checks.equal(
            sum(c.gained_rarity for c in plan.refreshed),
            2,
            "and the rarity cells the candidate rows GAIN are counted too — the other "
            "2026-09-11 fix, and the one 513 of 565 stored entries are missing: both of "
            "this catalogue's Dunsparce rows carry a `Rarity` the stale entry had none of",
        )

        # -------------------------------------------------------------------- the write
        with Store().write() as writable:
            added_main, added_parked, released = plan.apply(writable.review, writable.parked)
        checks.equal(
            (added_main, added_parked, released),
            (0, 0, ["1/2"]),
            "the write adds NO new position — every position it walked was already queued — "
            "and releases exactly the one that resolved",
        )

        after = Store().read()
        refreshed = after.review.entries.get("1/1")
        checks.equal(
            refreshed.reason,
            "ambiguous_no_signal",
            "the refreshed entry carries the reason the CURRENT ladder wrote, not the one "
            "the stale fixture held",
        )
        checks.equal(
            [row["sku"] for row in refreshed.candidates],
            [DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU],
            "and the candidate rows are this catalogue's, through `_candidate_rows` — the "
            "function whose 2026-09-11 fix the 513 frozen entries could never see",
        )
        checks.equal(refreshed.market, "2.06", "with the price the export carries now")
        checks.equal(
            refreshed.first_seen,
            FROZEN_SEEN,
            "FIRST_SEEN SURVIVES THE REFRESH. `upsert` preserves it, and it has to: the "
            "entry is the standing record of how long this card has been waiting, and "
            "`QueueEntry.sort_key`'s starvation tier is the only thing that ever surfaces "
            "an unpriced one. A refresh that restamped it would reset every frozen entry's "
            "age to today and empty that tier",
        )
        checks.ok("1/2" not in after.review.entries, "the resolved card's question is gone")

        # ---------------------------------------------------- what may never have moved
        stored_after = stored_payloads("queues", {"queue": queues.MAIN})
        checks.ok(
            "1/3" in stored_after and after.review.entries["1/3"].cleared_by_human,
            "THE ANSWERED ENTRY IS STILL THERE AND STILL CLEARED — neither re-queued by "
            "`upsert` nor dropped by `release`, which is D28's rule and the reason `apply` "
            "reuses `queues.apply_run` rather than writing the pair of loops itself",
        )
        checks.equal(
            {key: json.dumps(stored_after.get(key), sort_keys=True) for key in untouchable},
            untouchable,
            "AND ITS STORED PAYLOAD IS BYTE-IDENTICAL, as are the three departed cards' — "
            "the assertion the flag alone cannot make. A pass that re-queued an answer with "
            "the same verdict would leave `cleared_by_human` true and rewrite the "
            "candidates under it, which is the answer being taken back in everything but "
            "name",
        )

        # ------------------------------------------------------------------ idempotence
        again = requeue.plan(
            after.inventory,
            after.review,
            after.parked,
            catalogs,
            threshold=threshold,
            rule=rule,
            basis=basis,
        )
        checks.equal(
            (again.touched, again.changes),
            (0, []),
            "IDEMPOTENCE — the test D87 calls the one that separates the two designs. A "
            "second pass over the written store reports nothing to do, so `--write` wrote "
            "what the preview planned and the preview is not computed off something that "
            "moves",
        )
        checks.equal(
            (again.unchanged, len(again.skipped), again.cleared),
            (1, 3, 1),
            "and it accounts for every entry the same way twice: one unchanged, three "
            "skipped, one answered and left alone",
        )
        checks.equal(
            again.freed,
            set(),
            "with nothing released a second time — `freed` is what this pass re-resolved "
            "and did not re-queue, and the resolved entry is no longer there to re-resolve",
        )

    # ------------------------------------- the read-then-write window, and it is a real one
    #
    # THE TWO REFUSALS THIS MODULE LEANS ON ARE UNREACHABLE FROM THE CASE ABOVE, and that was
    # found by breaking them: delete `Queue.upsert`'s cleared refusal, delete `Queue.release`'s
    # cleared protection, and every assertion above stays green. `_open_by_position` walks
    # `open_entries`, so a cleared position never becomes an entry this pass would WRITE, and
    # `apply_run`'s `keep` set starts from everything already in the queue, so it never becomes
    # one this pass would DROP. The answer above is protected by the filter alone. That is fine
    # until the filter moves, and a guard no test reaches is a guard that has already gone.
    #
    # SO THE CASE IS THE COMMAND'S OWN WINDOW, not a contrivance to reach a branch.
    # `queue refresh` previews by default and is MEANT to be read before `--write` — that is
    # the whole posture `cli/cmd_queue.py` argues for — which leaves the operator free to
    # answer a card on `#/review` in between. The plan then names a position the store has
    # since settled, once as an entry to rewrite and once as a position to release. Both have
    # to lose to the answer, and this is where the two refusals are the only thing that says so.
    with isolated_home() as home:
        for _ in range(2):
            capture_server.do_capture(capture_payload(1))
        export = write_export(home / "race-export.csv")
        catalogs, _, _ = requeue.catalogs_from([export])

        with Store().write() as snapshot:
            snapshot.inventory.record_identification(
                "1/1", name="Dunsparce", number="120", printed_total="159", confidence="high"
            )
            snapshot.inventory.record_identification(
                "1/2", name="Articuno", number="161", printed_total="159", confidence="high"
            )
            snapshot.review.upsert(entry(1, 1))
            snapshot.review.upsert(entry(1, 2))

        staged = Store().read()
        plan = requeue.plan(staged.inventory, staged.review, staged.parked, catalogs)
        checks.equal(
            ([e.position for e in plan.main], plan.freed),
            (["1/1"], {"1/2"}),
            "the preview names one position to REWRITE and one to RELEASE, so both refusals "
            "have something aimed at them",
        )

        # The operator answers both cards while the preview is still on screen.
        with Store().write() as snapshot:
            snapshot.review.entries["1/1"].cleared_by_human = True
            snapshot.review.entries["1/2"].cleared_by_human = True
        answered = stored_payloads("queues", {"queue": queues.MAIN})

        with Store().write() as writable:
            plan.apply(writable.review, writable.parked)

        settled = Store().read()
        written = stored_payloads("queues", {"queue": queues.MAIN})
        checks.ok(
            settled.review.entries.get("1/1") is not None
            and settled.review.entries["1/1"].cleared_by_human,
            "AN ANSWER GIVEN AFTER THE PREVIEW IS NOT RE-QUEUED BY THE WRITE. `Queue.upsert` "
            "refuses a position a human has cleared, and this is the case that reaches that "
            "refusal — which is the whole reason `RefreshPlan.apply` reuses `queues.apply_run` "
            "instead of writing the pair of loops itself",
        )
        checks.equal(
            json.dumps(written.get("1/1"), sort_keys=True),
            json.dumps(answered["1/1"], sort_keys=True),
            "payload for payload, so a refresh landing UNDERNEATH the flag is caught too: "
            "rewriting the candidates while leaving `cleared_by_human` true is the answer "
            "being taken back in everything except the field that records it",
        )
        checks.ok(
            settled.review.entries.get("1/2") is not None
            and settled.review.entries["1/2"].cleared_by_human,
            "AND IT IS NOT RELEASED. The plan holds this position in `freed` — the catalogue "
            "settles the card, so the pass wants the question gone — and `Queue.release` "
            "protects a cleared entry anyway. D28's undo window is the only door back out of "
            "an answer, and a store-wide pass does not get to be a second one",
        )
        checks.equal(
            json.dumps(written.get("1/2"), sort_keys=True),
            json.dumps(answered["1/2"], sort_keys=True),
            "byte for byte there too",
        )

def check_queue_refresh_agreement(checks: Checks) -> None:
    """The refresh and the JOIN must produce the same entry for the same card.

    THIS IS THE LOAD-BEARING CASE, because it is the whole premise of the module: the refresh
    IS the ladder rather than a second reading of it. Every entry is rebuilt into the
    `join.IdentifiedCard` `cli/resolve.py:load` would have built, handed to `join.join_batch`
    with `join.default_router`, and turned back into a `queues.QueueEntry` by
    `cli/resolve.py:queue_entry` — the same three functions in the same order. If that holds,
    every later improvement to the ladder, to the candidate rows or to the router reaches the
    frozen entries the day it lands, with nothing here to keep in step. If it does not, the
    command quietly rewrites 565 entries into answers no join would give.

    THE JOIN'S SIDE COMES FROM THE REAL `pkmnscan join`, NOT FROM A SECOND CALL TO
    `join_batch` HERE. `seam_run` runs the command through `cli/__main__.py`, so `load`,
    `entries_for` and `queues.apply_run` all run for real and the store's two queues ARE the
    join's verdict — which is the first of the two shapes available and the stronger one: a
    re-call of `join_batch` from this file would share the arguments this file chose, and the
    defect to catch is precisely a refresh choosing different ones. What the store holds
    afterwards was written by the command a human runs.

    `first_seen` IS THE ONE FIELD EXCLUDED, and it is excluded rather than asserted equal
    because the plan's entries have not been through `upsert` yet — that is where the stamp is
    applied, and `check_queue_refresh` above is where it is checked.

    ONE CARD PARKS AND ONE GOES TO MAIN, which is what makes "same queue" a real assertion
    rather than a vacuous one: a comparison over a review-only fixture would pass for a pass
    that put everything in main.
    """
    checks.note("")
    checks.note("QUEUE REFRESH AGREES WITH THE JOIN — one fixture, two readers")

    cards = [
        (1, 1, "Dunsparce", "120", None),    # ambiguous, and cheap -> parked
        (1, 2, "Nosuchcard", "999", None),   # no catalog row, unpriced -> main
        (1, 3, "Articuno", "161", None),     # holofoil-only -> listed, never queued
    ]

    with isolated_home():
        # Both Dunsparce rows marked down below the cut-off, by rewriting the EXPORT rather
        # than by writing the number the test expects to read back — `write_export`'s rule,
        # for its reason: the price is read from the file both readers are handed.
        run_dir, _ = seam_run(
            checks, cards, market={DUNSPARCE_SKU: "0.05", DUNSPARCE_REVERSE_SKU: "0.06"}
        )
        joined = Store().read()
        checks.equal(
            (sorted(joined.review.entries), sorted(joined.parked.entries)),
            (["1/2"], ["1/1"]),
            "the join put one card in each queue and listed the third — the fixture can "
            "tell a wrong queue from a right one",
        )

        # THE READING MIRRORED ONTO THE CARDS, which is what `cli/cmd_identify.py` does at
        # identify time and what `seam_run` deliberately does not: it writes the run's
        # `identifications.json` and joins, leaving the store's cards unread. The refresh
        # takes its reading off the card, so the store has to hold the same one.
        with Store().write() as snapshot:
            for box, index, name, number, finish in cards:
                snapshot.inventory.record_identification(
                    master.position_key(box, index),
                    name=name,
                    number=number,
                    printed_total="159",
                    confidence="high",
                    detected_finish=finish,
                )

        catalogs, _, _ = requeue.catalogs_from([run_dir.path("export.csv")])
        threshold, rule, basis = requeue.policy_of(corpus.Corpus.read())
        snapshot = Store().read()
        plan = requeue.plan(
            snapshot.inventory,
            snapshot.review,
            snapshot.parked,
            catalogs,
            threshold=threshold,
            rule=rule,
            basis=basis,
        )

        def shape(queue_entry: queues.QueueEntry) -> dict:
            """Everything a person or a screen reads off an entry, `first_seen` aside."""
            return {
                "position": queue_entry.position,
                "box": queue_entry.box,
                "index": queue_entry.index,
                "label": queue_entry.label,
                "photo": queue_entry.photo,
                "read": queue_entry.read,
                "confidence": queue_entry.confidence,
                "reason": queue_entry.reason,
                "candidates": queue_entry.candidates,
                "market": queue_entry.market,
                "cleared_by_human": queue_entry.cleared_by_human,
            }

        checks.equal(
            [e.position for e in plan.main],
            sorted(joined.review.entries),
            "SAME QUEUE — the refresh routes to main exactly what the join queued to main",
        )
        checks.equal(
            [e.position for e in plan.parked],
            sorted(joined.parked.entries),
            "and to parked exactly what the join parked: the router is the same object, "
            "built by `join.default_router` off the same cut-off",
        )
        checks.equal(
            {
                queues.MAIN: {e.position: shape(e) for e in plan.main},
                queues.PARKED: {e.position: shape(e) for e in plan.parked},
            },
            {
                queues.MAIN: {k: shape(v) for k, v in joined.review.entries.items()},
                queues.PARKED: {k: shape(v) for k, v in joined.parked.entries.items()},
            },
            "SAME ENTRY, FIELD FOR FIELD — reason, candidates, market, label and the read. "
            "The two paths share `join_batch` and `queue_entry`, so a disagreement here is "
            "the refresh handing the ladder a different card than `load` would have built",
        )
        checks.equal(
            plan.touched,
            0,
            "so a refresh run immediately after a join reports NOTHING to change, which is "
            "the same statement from the other end: the frozen entries are frozen because "
            "no run covers them, never because a join and a refresh disagree",
        )

def check_queue_refresh_reading(checks: Checks) -> None:
    """`requeue.identified` — the reading is the CARD's, and it is the whole reading.

    TWO DEFECTS WERE FOUND HERE AND BOTH WERE SILENT IN THE SAME WAY: the refresh took four
    fields off the card and a fifth from somewhere else, and the result was a card resolved
    against a reading no single identification ever produced. Neither is visible in a report
    — the pass says "refreshed", and what it refreshed it to is wrong.

    THE EMPTY STRING IS THE FIRST. `cli/resolve.py:load` normalises a run record with
    `(x or "").strip() or None` and then `printed_total=total if number else None`, and the
    store keeps `""` exactly where a run record keeps it. An empty string is not a number and
    the two route DIFFERENTLY: `None` sends the card down the blank-`Number` name branch, while
    `""` walks the number key, misses, and lands on D35's last-resort rung as
    `number_unread_name_matched`. Measured before the normalisation was copied to this side: 6
    of 183 positions where the join listed a card and the refresh queued it, every one a record
    carrying `""`.

    `detected_finish` IS THE SECOND, and it is the reason `store/master.py:Card` grew the
    field. The queue entry's `read` carries a complete reading, so taking one field off it
    looked free; an entry may have been written by an OLDER identification of the same
    photograph, and six of box 4's cards read `finish: null` on 2026-09-12 while their
    2026-09-11 entries still said `foil`.

    THE CONFIDENCE WAS THE THIRD AND IT WAS FOUND BY THIS SECTION. `identified` read
    `card.confidence or entry.confidence` — the same mixing, and a `NameError` besides, since
    `entry` is not a parameter of that function. Every card whose stored confidence was falsy
    took the whole pass down with it rather than resolving.
    """
    checks.note("")
    checks.note("QUEUE REFRESH READS THE CARD — requeue.identified")

    with isolated_home() as home:
        for _ in range(4):
            capture_server.do_capture(capture_payload(1))

        def reading(index: int, **fields) -> Optional[join.IdentifiedCard]:
            """Write one reading onto a card and build the `IdentifiedCard` from it."""
            with Store().write() as snapshot:
                snapshot.inventory.record_identification(
                    master.position_key(1, index),
                    **{
                        "name": "Dunsparce",
                        "number": "120",
                        "printed_total": "159",
                        "confidence": "high",
                        **fields,
                    },
                )
            snapshot = Store().read()
            return requeue.identified(
                snapshot.inventory.cards[master.position_key(1, index)],
                resolve.box_views(snapshot.inventory),
            )

        # ----------------------------------------------- an empty string is not a number
        blank = reading(1, number="", printed_total="")
        checks.equal(
            (blank.number, blank.printed_total),
            (None, None),
            "A STORED `\"\"` BECOMES `None`, NEVER `\"\"` — `load`'s own normalisation, "
            "character for character. The store keeps an empty string where a run record "
            "keeps one, so the normalisation has to happen on this side too",
        )
        half = reading(2, number="", printed_total="159")
        checks.equal(
            (half.number, half.printed_total),
            (None, None),
            "and a printed total with no number in front of it is dropped with it — "
            "`printed_total=total if number else None`, which is the composition key's "
            "denominator being meaningless without its numerator",
        )
        absent = reading(3, number=None, printed_total=None)
        checks.equal(
            (blank.name, blank.number, blank.printed_total),
            (absent.name, absent.number, absent.printed_total),
            "so the `\"\"` card and the `None` card are ONE reading: the whole point of the "
            "normalisation is that the ladder cannot tell them apart, and a card whose "
            "number is unread walks the blank-`Number` name branch rather than D35's "
            "last-resort rung",
        )

        # ------------------------------------ the finish is the card's, not the entry's
        with Store().write() as snapshot:
            snapshot.review.upsert(
                entry(1, 4, read={"name": "Dunsparce", "detected_finish": "reverse_holo"})
            )
        finish = reading(4, detected_finish="holo")
        checks.equal(
            finish.detected_finish,
            "holo",
            "THE FINISH COMES OFF THE CARD while the open queue entry at the same position "
            "says `reverse_holo` — the entry decides WHICH positions the pass examines and "
            "nothing about what they are. An entry may be an OLDER identification of the "
            "same photograph, and reading four fields off the card and one off the entry "
            "hands the ladder two readings of one card",
        )
        checks.equal(
            Store().read().review.entries["1/4"].read.get("detected_finish"),
            "reverse_holo",
            "and the stale entry is still on record saying otherwise, so this case can fail: "
            "a fixture whose entry agreed with its card would pass either way",
        )

        # ------------------------------------------- a card the store has no reading for
        unread = reading(1, name=None, number=None, printed_total=None)
        checks.ok(
            unread is None,
            "a card with no name and no number is REFUSED rather than guessed at — the "
            "caller files it as `no_reading` and names it, and falling back to the entry's "
            "`read` would be the same mixing one layer down",
        )
        checks.ok(
            requeue.NO_READING in requeue.SKIP_REASONS
            and requeue.NO_READING in requeue.SKIP_SENTENCES,
            "and the reason it is filed under has a sentence to print: a refresh that "
            "silently left cards alone would be the same shape as the defect it fixes",
        )

        # ------------------------------------------------- a card with no confidence at all
        # THROUGH `answers` RATHER THAN READ DIRECTLY, because the defect this case was
        # written for is a RAISE: `card.confidence or entry.confidence` is a `NameError`, and
        # letting it propagate takes the whole of T7 down as one crash instead of leaving a
        # red line that says which rule broke.
        quiet_card = answers(
            checks,
            lambda: reading(2, confidence=None),
            "A CARD THE STORE HAS NO CONFIDENCE FOR DOES NOT RAISE. This read "
            "`card.confidence or entry.confidence` — the same mixing the docstring forbids, "
            "and a `NameError` besides, since `entry` is no parameter of that function — so "
            "one falsy field took the whole store-wide pass down with it",
        )
        checks.ok(
            quiet_card is not None and quiet_card.confidence is None,
            "and it carries `None`, which is the honest reading of a confidence the store "
            "does not have. `pipeline/routing.py` already has a branch for it; a value "
            "borrowed from the entry would be another reading's answer wearing this one's name",
        )

        # The pass survives such a card end to end, not just the one function: a raise here
        # is a command that cannot run at all on a store holding one.
        export = write_export(home / "reading-export.csv")
        catalogs, _, _ = requeue.catalogs_from([export])
        with Store().write() as snapshot:
            snapshot.review.upsert(entry(1, 2))
        snapshot = Store().read()
        survived = answers(
            checks,
            lambda: requeue.plan(
                snapshot.inventory, snapshot.review, snapshot.parked, catalogs
            ),
            "and `plan` walks a store holding one of those cards without raising",
        )
        if survived is not None:
            checks.ok(
                not [s for s in survived.skipped if s.reason == requeue.NO_READING],
                "resolving it rather than filing it as unreadable — a name is a reading "
                "even when nothing else on the card is",
            )
            # AND THE SAME FINISH RULE THROUGH THE WHOLE PASS, not just through the one
            # function: the ENTRY the refresh would write has to carry the card's reading,
            # because that is the entry a person reads off the review screen.
            fresh = {e.position: e for e in (*survived.main, *survived.parked)}
            checks.ok(
                "1/4" in fresh,
                "the card whose finish no row stocks is still a question after the refresh",
                f"fresh entries: {sorted(fresh)}",
            )
            if "1/4" in fresh:
                checks.equal(
                    (fresh["1/4"].reason, fresh["1/4"].read.get("detected_finish")),
                    ("detected_finish_not_stocked", "holo"),
                    "and the entry it would WRITE names the card's `holo` as the finish no "
                    "Dunsparce row stocks — the contradiction the reason exists to state. "
                    "Read off the stale entry instead it would say `reverse_holo`, which "
                    "IS stocked, and the card would resolve to the wrong SKU",
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
                    position="3/5", box=3, index=5, label=stored_label(3, 5),
                    photo=str(photo_of(3, 5)),
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
                "Section 1, Card 4 is retired: damaged" in str(caught)
                and "card 4 is retired" not in str(caught),
                "and the refusal NAMES the blocker with its reason, in the SAME SHAPE a "
                "card row reads — Section n, Card m, never the bare store index "
                "(D259)",
                f"message was: {caught}",
            )
            # THE LISTED CARD'S TEXT MATCHES ITS OWN LABEL. Box 3 got no typed name, so it
            # carries the stored default — `said_place` (a second code path through
            # `join.box_view`) answers the same "Section 1, Card 4" for this departed card,
            # cross-checking `place_within_box`, the one the list actually calls.
            expected_label = join.said_place(Store().read().inventory, 3, 4)
            checks.ok(
                expected_label.endswith("Section 1, Card 4")
                and "Section 1, Card 4" in str(caught),
                "the list's own text for card 4 matches `said_place`'s label for the same "
                "index, minus the box name already said once in the sentence",
                f"said_place: {expected_label!r}; message: {caught}",
            )
        refusal(
            checks,
            lambda: capture_server.do_remove_card(3, 4, {"capture_id": "r4"}),
            "card_retired",
            "and the retired card itself refuses removal — departures keep their records",
        )
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/4", master.IDENTIFIED)

        # A listed SKU above blocks it too — its row is already in a file. DIRECT FIELD
        # WRITE, NOT `_bind`: this card's own name ("N3", from the fixture's earlier
        # identification loop) must survive untouched — `bind_sku` always overwrites it
        # from the row, which is not this refusal's own subject.
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/3", master.IDENTIFIED)
            snapshot.inventory.cards["3/3"].sku = "8608859"
            snapshot.inventory.listing("8608859").bump(master.PUSHED, 1)
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_remove_card(3, 2, {"capture_id": "r2"}),
            "a listed SKU above the target refuses the shift",
        )
        if caught is not None:
            checks.equal(getattr(caught, "code", None), "renumber_blocked", "renumber_blocked")
            checks.ok(
                "Section 1, Card 3 is one copy of SKU 8608859" in str(caught)
                and "1 pushed" in str(caught)
                and "card 3 is one copy" not in str(caught),
                "naming the SKU and the stage that holds it, against the card's Section n, "
                "Card m label — never the bare store index",
                f"message was: {caught}",
            )
        with Store().write() as snapshot:
            snapshot.inventory.listing("8608859").set(master.PUSHED, 0)

        # ------------------------------------------------------- the successful shift
        # WHAT THE CONTENT STORE HOLDS BEFORE THE SHIFT, AND UNDER WHICH NAMES (D172). The
        # payoff of filing a photograph under its card's own name is that a renumber renames
        # NOTHING, so the way to assert it is as an absence — afterwards the store holds
        # exactly this set less the one card that was deleted. Read here rather than composed
        # afterwards, because a set computed from the post-shift store could not fail.
        before_names = set(photos.stored_names())
        target_cid = Store().read().inventory.get("3/2").cid
        # And the path the queue entry names, before anything is touched. It has to come out
        # the other side byte-identical: the entry follows the card, and the card's
        # photograph has not been anywhere.
        entry_photo_before = Store().read().review.entries["3/5"].photo

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
        checks.equal(
            sorted(photos.stored_names()),
            sorted(before_names - {target_cid}),
            "NOT ONE PHOTOGRAPH WAS RENAMED, and that absence is what D172 bought. The four "
            "cards that slid down an index are filed under their own names, which did not "
            "move, so only the deleted card's file left the content store. The loop this "
            "replaces renamed N-k photographs and rewrote N-k sidecars for a deletion at "
            "index k — 537 of each on the owner's box 2, to remove one junk capture",
        )
        checks.ok(
            all(
                photo_of(3, idx).read_bytes()[3:4] == bytes([byte])
                for idx, byte in ((2, 3), (3, 4), (4, 5))
            ),
            "and every card still reads ITS OWN bytes through its new position — a "
            "photograph attributed to the wrong record is the failure a position label may "
            "never cause, and the lookup is what has to follow the card now that the "
            "filename cannot",
        )
        sidecar_now = json.loads(
            capture_server.sidecar_path(photo_of(3, 4)).read_text("utf-8")
        )
        checks.equal(
            sidecar_now.get("index"), 5,
            "AND THE SIDECAR STILL CLAIMS THE INDEX ITS CAPTURE CLAIMED, which is the reverse "
            "of what this case asserted while the filename WAS the index. The claims file "
            "travels with the photograph, and its `index` is a historical fact about one "
            "capture rather than an address: the index a run reads is materialised from the "
            "store when the scope directory is built (`server/pipeline_routes.py` §0.4), so "
            "there is nothing left on disk for a shift to correct",
        )
        moved_entry = after.review.entries.get("3/4")
        checks.ok(
            moved_entry is not None
            and after.review.entries.get("3/5") is None
            and moved_entry.index == 4
            and moved_entry.photo == entry_photo_before
            and moved_entry.photo == str(photo_of(3, 4)),
            "the queue entry is re-keyed — position, box and index — while THE PHOTO PATH IT "
            "NAMES DOES NOT MOVE, which is the same absence one register out: the entry "
            "followed the card, and the card's photograph never went anywhere. It is still "
            "this card's own path, asserted both ways so a re-point to some other card's "
            "file could not pass as 'unchanged'",
            f"entry was: {moved_entry!r}",
        )
        checks.ok(
            moved_entry is not None and moved_entry.label == stored_label(3, 5),
            "AND ITS STORED LABEL IS NOT REWRITTEN, which is D92 and is the reverse of what "
            "this case asserted until then. The re-key composed one with `join.Position` and "
            "no `occupied`, so it was in INDEX space while every route serves a label "
            "`_queue_row` re-renders in COUNT space — a plausible wrong rendering in the same "
            "field as the correct ones `cli/resolve.py` writes, one forgotten `places` "
            "argument from reaching a screen. It keeps the string it arrived with (D56: a "
            "rendering nobody can correct is joined at read time, not stored), and the "
            "assertion is written against the OLD position on purpose — that is what a stale "
            "stored label looks like, and no route may serve it",
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
            "replaying the remove refuses — the neighbor that slid in is not the card "
            "the request describes",
        )

        # -------------------------------------------------------- the whole-box delete
        refusal(
            checks,
            lambda: capture_server.do_delete_box(9),
            "box_not_found",
            "deleting a box nothing has heard of refuses",
        )

        # D134: box 3 holds 3/1 (never identified, on hand), 3/2 (N3), 3/3 (N4), 3/4 (N5).
        # One of each terminal door, plus an on-hand card carrying a listing hold, so the
        # refusal and the burial are both exercised in one setup.
        blob_3 = base64.b64decode(blob(3))
        blob_5 = base64.b64decode(blob(5))
        with Store().write() as snapshot:
            # 3/2 is r3 (originally 3/3), which the remove test above assigned SKU
            # "8608859" to and then released — that leftover claim is cleared here so
            # this sold card's burial line is asserted against a clean sku=None.
            snapshot.inventory.cards["3/2"].sku = None
            snapshot.inventory.set_state("3/2", master.SOLD)
            snapshot.inventory.retire("3/4", "damaged")
        move_result = capture_server.do_move_card(3, 3, {"capture_id": "r4", "to_box": 9, **back_of(9)})
        moved_to = move_result["to"]
        with Store().write() as snapshot:
            snapshot.inventory.set_state("3/1", master.IDENTIFIED)
            _bind(snapshot, "3/1", "8608859")
            snapshot.inventory.listing("8608859", condition="Near Mint").set(
                master.PUSHED, 1
            )

        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_delete_box(3),
            "an on-hand card holding a listing still refuses deletion — that copy is a "
            "commitment TCGplayer already knows about (D10, ruling 3)",
        )
        if caught is not None:
            checks.equal(
                getattr(caught, "code", None),
                "box_not_empty_of_commitments",
                "in its own code",
            )
            checks.ok(
                "Section 1, Card 1 is one copy of SKU 8608859" in str(caught)
                and "1 pushed" in str(caught)
                and "card 1 is one copy" not in str(caught)
                and "is sold" not in str(caught) and "is retired" not in str(caught)
                and "was moved" not in str(caught),
                "and the refusal names only the listed copy, in the SAME SHAPE a card "
                "row reads — Section n, Card m, never the bare store index "
                "(D259) — the sold, retired and moved records "
                "no longer stand in the way (D134)",
                f"message was: {caught}",
            )
            checks.equal(
                join.said_place(Store().read().inventory, 3, 1),
                "Box 1, Section 1, Card 1",
                "cross-checked against `said_place` for the same index",
            )
        checks.equal(
            len(Store().read().inventory.cards), 5,
            "and the refusal deleted nothing — not the departed records it did not name "
            "either, box 3 plus the moved card's fresh home in box 9",
        )
        with Store().write() as snapshot:
            snapshot.inventory.listing("8608859").set(master.PUSHED, 0)

        body = capture_server.do_delete_box(3)
        checks.equal(
            (body["cards"], body["buried"], body["photos"], body["sidecars"]),
            (4, 3, 3, 3),
            "the delete reports what it removed — 4 records, 3 of them departed and "
            "buried rather than counted as ordinary deletions. The moved tombstone's "
            "photo and sidecar already relocated with the transplant, so only 3 of the "
            "4 records still had files at this box for the delete to unlink",
        )
        checks.ok(
            body["review_deleted"] == 1 and body["cache_deleted"] == 1,
            "the queue entry and the paid answer that were re-keyed onto 3/4 by the "
            "earlier remove are dropped along with the RETIRED record they now belong "
            "to — a buried record is cleared from every other store exactly as an "
            "ordinary deletion is",
            f"body was: {body}",
        )
        checks.ok(
            body["registry_deleted"] and not body["directory_removed"],
            "and the registry entry went with it. `directory_removed` is FALSE, and that is "
            "the honest answer rather than a regression: it reports on `captures/cards/box3`, "
            "which a store written since D172 never creates — every photograph is filed by "
            "its card's name under one sharded root. The field is kept because a store part "
            "way through the relocation still has those directories to leave behind",
            f"body was: {body}",
        )
        after = Store().read()
        transplant = after.inventory.get(moved_to)
        checks.ok(
            not after.inventory.records_in(3)
            and after.inventory.boxes.get("3") is None
            and photos.stored_names() == [transplant.cid],
            "a deleted box is a box the store has never heard of, and the one photograph "
            "left in the content store is the one belonging to the card that moved out "
            "before the delete — box 9 is untouched. Asserted over the store's own names "
            "rather than over a box directory, because there is no longer any such thing",
            f"names left: {photos.stored_names()}",
        )
        checks.ok(
            any(
                e.get("event") == "box_deleted" and e.get("cards") == 4
                and e.get("buried") == 3 and "position" not in e
                for e in Store().history()
            ),
            "one `box_deleted` line carries the box, the card count and the buried "
            "count, with no `position` key — a box is not at a position",
        )

        buried = Store().buried()
        by_key = {e.get("position"): e for e in buried}
        checks.equal(
            sorted(by_key), ["3/2", "3/3", "3/4"],
            "one `buried` line per departed record, keyed like every other position line",
        )
        checks.ok(
            by_key["3/2"].get("state") == master.SOLD
            and by_key["3/2"].get("name") == "N3"
            and by_key["3/2"].get("sku") is None
            and by_key["3/2"].get("box") == 3
            and by_key["3/2"].get("index") == 2
            # A BOX CREATED WITH NO NAME CARRIES ITS STORED DEFAULT (D259).
            and by_key["3/2"].get("box_name") == "Box 1"
            and by_key["3/2"].get("capture_id") == "r3"
            and by_key["3/2"].get("order") is None
            and by_key["3/2"].get("photo_sha256")
            == hashlib.sha256(blob_3).hexdigest(),
            "the sold line carries the record whole, including a photograph digest "
            "computed from the bytes in the moment before they were deleted — this "
            "card's photo_sha256 was never set by a reclaim",
            f"line was: {by_key['3/2']!r}",
        )
        checks.ok(
            by_key["3/3"].get("state") == master.MOVED
            and by_key["3/3"].get("moved_to") == moved_to
            and by_key["3/3"].get("capture_id") is None
            and by_key["3/3"].get("photo_sha256") is None,
            "the moved tombstone's line names where the card went, and carries no "
            "capture_id or digest — `move_card` clears the first and the file the "
            "second would be computed from already relocated with the transplant",
            f"line was: {by_key['3/3']!r}",
        )
        checks.ok(
            by_key["3/4"].get("state") == master.RETIRED
            and by_key["3/4"].get("retire_reason") == "damaged"
            and by_key["3/4"].get("name") == "N5"
            and by_key["3/4"].get("capture_id") == "r5"
            and by_key["3/4"].get("photo_sha256")
            == hashlib.sha256(blob_5).hexdigest(),
            "the retired line names why it left, alongside the same digest and record "
            "detail the sold line carries",
            f"line was: {by_key['3/4']!r}",
        )

        _, fresh = capture_server.do_capture(
            {"box": 3, "capture_id": "fresh", "image": blob(9)}
        )
        checks.equal(
            fresh["index"], 1,
            "and recreating the number starts from nothing, like a box never used",
        )

def check_graveyard(checks: Checks) -> None:
    """GET /graveyard — D134's merge of two sources into one screen.

    A DEPARTED CARD READS THE SAME WAY WHETHER ITS BOX STILL EXISTS OR NOT, which is the
    whole reason this route is a merge rather than a pass-through of `do_boxes` or
    `Store().buried()` alone. This walks a card through both: sold and standing, then
    sold and buried once its box is deleted — the same record, the same shape, and the
    count never doubles or drops it along the way.
    """
    checks.note("")
    checks.note("GRAVEYARD — D134's two-source merge")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        checks.equal(
            capture_server.do_graveyard(), {"departed": []},
            "an empty store has nothing departed",
        )

        # ---------------------------------------------- source 1: standing in a box
        capture_server.do_capture({"box": 1, "capture_id": "g1", "image": blob(1)})
        capture_server.do_capture({"box": 1, "capture_id": "g2", "image": blob(2)})
        with Store().write() as snapshot:
            snapshot.inventory.record_identification(
                "1/1", name="Alpha", number="001", printed_total="100", confidence="high",
            )
        capture_server.do_mark_sold(1, 1, {})

        body = capture_server.do_graveyard()
        checks.equal(
            len(body["departed"]), 1,
            "the sold card is the one departed row — the on-hand card beside it in the "
            "same box is not",
        )
        row = body["departed"][0]
        checks.ok(
            row["how"] == "sold" and row["buried"] is False and row["buried_at"] is None
            and row["box"] == 1 and row["index"] == 1 and row["name"] == "Alpha",
            "read straight off the standing record — no burial needed for a card whose "
            "box still exists",
            f"row was: {row!r}",
        )

        # A second box, a second departure, standing too — proves the merge is not
        # scoped to one box, and gives the ordering assertion below something real to
        # order.
        capture_server.do_capture({"box": 2, "capture_id": "g3", "image": blob(3)})
        with Store().write() as snapshot:
            snapshot.inventory.record_identification(
                "2/1", name="Beta", number="002", printed_total="100", confidence="high",
            )
        capture_server.do_retire(2, 1, {"reason": "lost"})

        rows = capture_server.do_graveyard()["departed"]
        checks.equal(len(rows), 2, "two standing departures, from two different boxes")
        checks.ok(
            [r["how"] for r in rows] == ["retired", "sold"],
            "newest departure first — the retirement happened after the sale",
            f"rows were: {rows!r}",
        )

        # ---------------------------------------------------- source 2: buried
        capture_server.do_delete_box(1)
        rows = capture_server.do_graveyard()["departed"]
        checks.equal(
            len(rows), 2,
            "still two — the sold card moved from one source to the other, never "
            "doubled and never dropped",
        )
        by_how = {r["how"]: r for r in rows}
        checks.ok(
            by_how["sold"]["buried"] is True
            and by_how["sold"]["buried_at"] is not None
            and by_how["sold"]["box"] == 1
            and by_how["sold"]["name"] == "Alpha"
            and by_how["retired"]["buried"] is False,
            "the deleted box's departure now reads `buried: true` with a `buried_at` "
            "stamp; the standing one still reads `buried: false`",
            f"rows were: {rows!r}",
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

    with isolated_home():
        # SHARED: box 4 holds 2 of 5 staged; box 6 holds 3. OWNED: box 4 holds both.
        # SOLDCOPY: box 4 holds 1 unsold and 1 sold against 2 staged.
        layout = (
            (4, 1, "SHARED"), (4, 2, "SHARED"), (6, 1, "SHARED"), (6, 2, "SHARED"),
            (6, 3, "SHARED"), (4, 3, "OWNED"), (4, 4, "OWNED"),
            (4, 5, "SOLDCOPY"), (4, 6, "SOLDCOPY"),
        )
        # THROUGH `capture_payload`, WHICH MINTS A PHOTOGRAPH PER CALL. A local helper here
        # keyed its bytes on the INDEX, so box 4's card 1 and box 6's card 1 sent the same
        # blob — two cards with one name, which `cards_cid` refuses outright since D172.
        # Nothing in this section reads a card out of its bytes; what it needs is that no
        # two of the nine are the same, which is exactly what the shared fixture promises.
        for box, index, _ in layout:
            capture_server.do_capture(capture_payload(box, capture_id=f"L{box}{index}"))
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
        refusal(
            checks,
            lambda: capture_server.do_release_box_listings(4, {"confirm": True}),
            "nothing_to_release",
            "and with every stage at zero a replay refuses rather than answering a cheerful "
            "200 — what keeps a stale screen distinguishable from a release that worked",
        )

        # D134: every listing hold on box 4 is now clear, and the SOLD card at 4/6 no
        # longer stands on its own — it is buried rather than blocking. The delete D34
        # was built to unblock (`_listing_hold` is what remains of the gate) succeeds.
        body = capture_server.do_delete_box(4)
        checks.equal(
            (body["cards"], body["buried"]),
            (6, 1),
            "all 6 records go — the 5 on-hand cards as ordinary deletions, the one SOLD "
            "record buried rather than counted among the blockers a listing hold answers",
        )
        buried = {e.get("position"): e for e in Store().buried() if e.get("box") == 4}
        checks.ok(
            "4/6" in buried and buried["4/6"].get("state") == master.SOLD,
            "the sold card's departure survives the box as a `buried` line rather than "
            "as the box's own permanent refusal",
            f"buried lines were: {buried!r}",
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
                "capture_id",
                "cid",
                "cleared_by_human",
                "confidence",
                "first_seen",
                "index",
                "label",
                "market",
                "photo",
                "place",
                "position",
                "read",
                "reason",
            ],
            "a queue row is the whole QueueEntry record plus age_days, the card's place block "
            "its stable name (the review pill opens THIS card, LOC-12) and the photograph's version (`photoUrl`'s `?v=`) — not a projection "
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
            run_photo(3, 3),
            "photo is the path on the Mac, exactly as Card.photo is — GET /photo is D6's "
            "route and the only way a browser sees it",
        )
        checks.equal(
            row["age_days"], 0, "and age_days is computed here rather than in the app"
        )
        checks.equal(
            row["label"],
            stored_label(3, 3),
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
        for label, damage in (
            ("a market that is not a number", {"market": "twelve"}),
            ("a box that arrived as a string", {"box": "3"}),
        ):
            # Written through a session, which stores whatever the record holds — the
            # damage a hand edit of the old file used to seed, reached the one way a row
            # is written now.
            with Store().write() as snapshot:
                for name, value in damage.items():
                    setattr(snapshot.review.entries["3/3"], name, value)
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
                    "review" in report.get("problem", ""),
                    f"{label}: and the problem names the queue to go and fix",
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
            snapshot.review.entries["3/3"].market = "twelve"
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
                "review queue" in both_wrong.get("problem", "")
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
            _seed_sku_table(snapshot, [*CANDIDATES, STALE_CANDIDATE])

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
                "no candidate cards" in str(caught),
                "and the refusal says the card has nothing to choose from, since that is what says "
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
            stored_label(3, 1),
            "the returned card is a decorated inventory row — the same shape GET "
            "/inventory answers with, so the app needs no second vocabulary for a card",
        )
        checks.equal(
            body["restores_to"],
            {"sku": None, "condition": None, "set_name": None, "rarity": None},
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
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            "and the `answered` HISTORY line carries the FULL snapshot — THE BLOCKER'S "
            "REGRESSION: the line used to log only what the route WROTE, never what it "
            "overwrote, so nothing anywhere could say what an undo should put back — "
            "widened past the wire's own four fields on review (D28: undo must be exact, "
            "over every field bind_sku can touch, not only the pair a screen draws)",
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
                "no candidate cards" in str(caught) and "re-shoot" in str(caught),
                "saying there is nothing to choose from and offering the re-shoot",
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

    prior = {"sku": DUNSPARCE_SKU, "condition": "Near Mint", "set_name": None, "rarity": None}

    with isolated_home():
        for _ in range(6):
            capture_server.do_capture(capture_payload(3))

        with Store().write() as snapshot:
            # 3/1 CARRIED A REAL PAIR BEFORE THE ANSWER — the case the null-pair answer
            # above cannot cover — and sits in BOTH files, so its undo has two entries to
            # reopen. first_seen is seeded to a fixed day on both, because "the undo does
            # not reset how long the card has been waiting" is unfalsifiable against
            # today().
            # DIRECT FIELD WRITE, NOT `_bind`/`bind_sku`: the whole point of this fixture is
            # a card whose `sku`/`condition` are set and whose `set_name`/`rarity` are NOT —
            # exactly `do_review_answer`'s own narrow, four-field `restores_to` shape below
            # (D213: "an undo puts the card back to carrying no answer, set and rarity
            # included"). `bind_sku` always derives all five together, so it cannot build
            # this state; `harness/` sits outside the `identity writers` row's scope for
            # this reason.
            snapshot.inventory.set_state("3/1", master.IDENTIFIED)
            snapshot.inventory.cards["3/1"].sku = prior["sku"]
            snapshot.inventory.cards["3/1"].condition = prior["condition"]
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
            # SAME REASON, direct field write: `set_name`/`rarity` stay unset.
            snapshot.inventory.set_state("3/2", master.IDENTIFIED)
            snapshot.inventory.cards["3/2"].sku = DUNSPARCE_REVERSE_SKU
            snapshot.inventory.cards["3/2"].condition = "Near Mint Reverse Holofoil"
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
            _seed_sku_table(snapshot, [*CANDIDATES, STALE_CANDIDATE])

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
        before_overwrite = Store().read().inventory.identity_snapshot("3/1")
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
            before_overwrite,
            "and the `answered` line carries the same real pair, as a FULL snapshot — the "
            "other half of the blocker's regression: the null-pair line above cannot tell "
            "`logged the prior pair` from `logged a default`",
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
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            "while the `answered` history line still records the FULL snapshot — the two "
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
        # Corrupted IN BOX 3, the box the reversal below reads from: `_answer_origin` now
        # scopes its read to that box (`Store.history_at`), so a corrupt row filed under a
        # different box would be invisible to it and this case would prove nothing.
        corrupt_history(position="3/1")
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
                "history" in str(caught) and "could not be read" in str(caught),
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
        for _ in range(13):
            capture_server.do_capture(capture_payload(4))
        with Store().write() as snapshot:
            for i in range(1, 14):
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
            # SEALED, AND THE ONLY ENTRY HERE THAT IS NOT NEAR MINT. Since 2026-09-12 the
            # group clusters on the condition's GRADE rather than its full string, so
            # `Near Mint` and `Near Mint Holofoil` group together; this one must still
            # refuse, because `Unopened` is a different grade rather than a different
            # finish of one.
            #
            # `Unopened` AND NOT A PLAY GRADE, AND FINDING THAT OUT IS WHY THIS ENTRY EXISTS
            # IN THIS SHAPE. The obvious case — a `Lightly Played Holofoil` row from one of
            # the 513 entries on the owner's store written before D137 — CANNOT REACH the
            # uniformity check at all: `_answer_target` refuses it first as
            # `condition_not_listed`, per member, with a sentence naming the re-join that
            # fixes it. That is the better guard and it is upstream, so the grade rule's
            # whole remaining job is keeping sealed product out of a group of singles, and
            # this is the row that proves it does.
            snapshot.review.upsert(
                entry(
                    4,
                    12,
                    candidates=[
                        dict(CANDIDATES[0], sku="9112", condition=tcgcsv.SEALED_CONDITION)
                    ],
                )
            )
            # The mixed-FINISH pair's second half — `Near Mint Holofoil` against 4/9's
            # `Near Mint`. Its own entry rather than one of the happy group's, because the
            # assertion below ANSWERS it and a consumed member would make the happy path
            # refuse as `already_answered` for a reason that has nothing to do with it.
            snapshot.review.upsert(entry(4, 13, candidates=[own_row("9113")]))
            # The listing-hold pair.
            snapshot.review.upsert(entry(4, 10, candidates=[own_row("9110")]))
            snapshot.review.upsert(entry(4, 11, candidates=[own_row("9111")]))
            _seed_sku_table(
                snapshot,
                [
                    own_row("9101"), own_row("9102"), own_row("9103"), own_row("9104"),
                    dict(STALE_CANDIDATE), own_row("9105"), own_row("9107"), own_row("9108"),
                    dict(CANDIDATES[1], sku="9218"), dict(STALE_CANDIDATE, sku="9109"),
                    dict(CANDIDATES[0], sku="9112", condition=tcgcsv.SEALED_CONDITION),
                    own_row("9113"), own_row("9110"), own_row("9111"),
                ],
            )

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
                # D196 (UX-208's carried refusal-leak item): the raw store key ("4/1")
                # used to ride the message. `said_place` names the same position now.
                "Section 1, Card 1" in str(caught) and "4/1" not in str(caught),
                "and the message names the repeated position, said the way the screens say it",
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
                # D196: same fix — the raw key is gone, the said place is not.
                "Section 1, Card 6" in str(caught) and "4/6" not in str(caught) and "not_in_queue" not in str(caught),
                "and the failing position is named in plain words, so one 409 still "
                "reports per position, said the way the screens say it",
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

        # A MEMBER THAT IS NOT IN ITS BOX IS COUNTED, NEVER NAMED BY INDEX (the PR 2 integration
        # review). `place_within_box` fell back to "card 99998" for it: the raw store index.
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_review_group_answer(
                {"answers": [member(1, "9101"), member(99998, "9199")]}
            ),
            "a group naming a card its box does not hold refuses whole",
        )
        if caught is not None:
            checks.ok(
                "1 of the cards you named is not in" in str(caught) and "99998" not in str(caught),
                "and that card is counted plainly, with no raw index in the message",
                f"message was: {caught}",
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
        # TWO CONDITIONS OF ONE GRADE NOW ANSWER, AND THIS ASSERTION IS REVERSED ON PURPOSE
        # (D162). It read "two condition strings across the group
        # refuse the same way" until 2026-09-12. `Near Mint Holofoil` and `Near Mint` are one
        # grade and two finishes; D137 fixes the grade by rule, so refusing here split every
        # real queue in two and asked the operator to confirm a word they never chose.
        # Measured on the owner's store that day: of 52 entries, 40 offered exactly one row
        # and every one was Near Mint — 21 plain, 19 foil — so the old rule's entire effect
        # was to double the number of presses. Their words: *"i also somehow had to still
        # claim items in bulk that they're near mint rather than it being default."*
        #
        # The finish is not what the group decides: each member is answered with its own row,
        # whose finish the ladder chose from that card's own claim before this route was
        # reached. Asserted as an ANSWER rather than as the absence of a refusal, because a
        # route that stopped refusing and also stopped writing would satisfy the weaker form.
        mixed = capture_server.do_review_group_answer(
            {
                "answers": [
                    member(13, "9113"),
                    member(9, "9109", STALE_CANDIDATE["condition"]),
                ]
            }
        )
        checks.equal(
            mixed.get("count"),
            2,
            "TWO FINISHES OF ONE GRADE ANSWER AS ONE GROUP — `Near Mint Holofoil` beside "
            "`Near Mint`, which is the split that doubled every press on the owner's queue",
        )
        checks.equal(
            mixed.get("grade"),
            "near mint",
            "and the shared fact reported at the top is the GRADE, not a condition string "
            "— the members no longer share one, so reporting `condition` would have been a "
            "true statement about half of them",
        )
        settled = Store().read()
        checks.equal(
            [
                (settled.inventory.get("4/13").sku, settled.inventory.get("4/13").condition),
                (settled.inventory.get("4/9").sku, settled.inventory.get("4/9").condition),
            ],
            [("9113", cond), ("9109", STALE_CANDIDATE["condition"])],
            "AND EACH CARD KEPT ITS OWN CONDITION. This is the assertion the feature turns "
            "on: grouping folds the finish away for the QUESTION and never for the ANSWER, "
            "so a shared grade must not write one shared condition onto both cards",
        )

        refusal(
            checks,
            lambda: capture_server.do_review_group_answer(
                {
                    "answers": [
                        member(1, "9101"),
                        member(12, "9112", tcgcsv.SEALED_CONDITION),
                    ]
                }
            ),
            "group_not_uniform",
            "but two GRADES across the group still refuse — sealed product swept into a "
            "group of singles is what folding the finish away must not make reachable, and "
            "it is the one non-Near-Mint condition this catalogue still carries",
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
                [body["reason"], body["grade"]],
                ["metadata_detection_disagreement", "near mint"],
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
                [{"sku": None, "condition": None, "set_name": None, "rarity": None}] * 3,
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
            [NEVER_BOUND_IDENTITY_SNAPSHOT] * 3,
            "and each line carries its own FULL restores_to, exactly as a single answer "
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
                [None, {"sku": None, "condition": None, "set_name": None, "rarity": None}],
                "the held member answers restores_to NULL while its partner keeps the "
                "pair — per position, because a group control that reverses eleven of "
                "sixteen on its best day is SaleResult's recorded defect at scale",
            )
        held_lines = [last_event("4/10"), last_event("4/11")]
        checks.equal(
            [line.get("restores_to") for line in held_lines],
            [NEVER_BOUND_IDENTITY_SNAPSHOT] * 2,
            "while BOTH history lines still record the FULL snapshot — the log states "
            "what is true, the field answers whether to draw a button, and the two "
            "deliberately disagree",
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
            # DIRECT FIELD WRITE, NOT `_bind`: `bind_sku` logs its own `sku_bound` history
            # line, which would put a fifth line in the four-line sequence this function's
            # own history assertion checks below — fields set BEFORE `set_state` so its one
            # logged line already carries them, exactly as the retired `sku=`/`condition=`
            # parameters did in one call.
            card = snapshot.inventory.cards["3/1"]
            card.sku, card.condition = "8608859", "Near Mint Holofoil"
            snapshot.inventory.set_state("3/1", master.IDENTIFIED)
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
        sold_record = Store().read().inventory.listing_for("8608859")
        checks.equal(
            sold_record.live_estimate,
            0,
            "AND THE SKU'S COUNT FALLS BY ONE, ON THIS REQUEST — D7's ordering, which D115 "
            "kept: the app must not disagree with the shelf the operator is standing at. "
            "What changed is that it falls by DERIVATION rather than by editing the reading",
        )
        checks.equal(
            (sold_record.live, sold_record.sold_here),
            (1, 1),
            "and the READING is untouched at 1 — this store did not read an export, so it "
            "may not claim one. The sale is counted beside it, which is what stops "
            "`reconcile --live` and this route subtracting the same copy twice",
        )
        checks.equal(
            ((sold["listing"] or {}).get("live"), (sold["listing"] or {}).get("sold_here")),
            (1, 1),
            "and the response carries BOTH, because a Fulfiller pulling the third of four "
            "wants to see what is still live without a second request — and a derived "
            "figure never rides `asdict`, so the two numbers travel and the reader subtracts",
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
            photo_of(3, 1).is_file(),
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
        # Corrupted IN BOX 3, the box the sale below reads from — `_sale_origin` now scopes
        # its read to that box (`Store.history_at`), so this has to land where it can see it.
        corrupt_history(position="3/3")
        degraded = answers(
            checks,
            lambda: capture_server.do_mark_sold(3, 3, {}),
            "one malformed row in the history does not stop the sale being recorded",
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
                "history" in str(caught) and "could not be read" in str(caught),
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
        ("undo", "still_here"),
        "and mark-sold's whole body is two flags, the undo and its \"still here\" form "
        "(UN-7): the position is in the path and the state is a constant",
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

# ------------------------------------------------------ mark sold reverses the order ledger


def check_mark_sold_releases_ledger(checks: Checks) -> None:
    """The sale undo's ledger half — `docs/specs/undo.md` §4.

    A MUTATION-TESTED GUARD. Comment out the `holder`/`forget_pull` block in `do_mark_sold`
    (or move it into `_sell`, which would reverse `do_order_pull`'s own ledger write a
    second time) and this must fail — not "some check somewhere", THIS one, on the
    `checks.equal(after.fulfilled, 0, ...)` below.
    """
    checks.note("")
    checks.note("MARK SOLD UNDO — reverses the order ledger where it holds the copy")

    with isolated_home():
        # `capture_id` — the ledger's own identity for a physical copy — is the app's own
        # id, sent on the capture, never derived from the digest `cid` names it by (D172,
        # D183). It has to be on the fixture explicitly, the way the real camera always
        # sends one; `Ledger.record_pull`'s `CopyNotIdentifiable` refuses a card with none.
        capture_server.do_capture(capture_payload(4, capture_id="u1-copy"))
        with Store().write() as snapshot:
            snapshot.inventory.set_state("4/1", master.IDENTIFIED)
            _bind(snapshot, "4/1", "9191486")
            capture_id = str(snapshot.inventory.cards["4/1"].capture_id)
            checks.equal(capture_id, "u1-copy", "the fixture's capture id round-trips")
            snapshot.ledger.ingest([
                order_store.OrderRecord(
                    source="TCGplayer",
                    number="U-1",
                    placed_at="2026-08-28T10:00:00.000+00:00",
                    lines=[order_store.OrderLine(sku="9191486", quantity=1)],
                )
            ])
        key = order_store.order_key("TCGplayer", "U-1")

        with Store().write() as snapshot:
            newly = snapshot.ledger.record_pull(key, "9191486", [capture_id])
        checks.equal(newly, 1, "the pull records the physical copy against the line")
        checks.equal(
            Store().read().ledger.recorded(key, "9191486").fulfilled,
            1,
            "and the line now counts it fulfilled — the walk's own state before the sale",
        )

        # ---------------------------------------------------- the sale, from #/inventory
        sold = capture_server.do_mark_sold(4, 1, {})
        checks.equal(sold["state"], master.SOLD, "the card is sold, same as any other")
        checks.equal(
            sold.get("order_released"),
            None,
            "a plain sale releases nothing — that is `POST /orders/pull`'s job, already "
            "done before this card was ever marked sold",
        )
        checks.equal(
            sold.get("order_effect"),
            "none",
            "the Opus review round's finding #4: a plain sale (never a reversal) also "
            "answers 'none', so no screen may read this field as a claim about undo alone",
        )
        checks.equal(
            Store().read().ledger.recorded(key, "9191486").fulfilled,
            1,
            "and the ledger is untouched by the sale itself — only the undo direction reads it",
        )

        # ---------------------------------------------------- the reversal, from the same row
        back = capture_server.do_mark_sold(4, 1, {"undo": True})
        checks.equal(back["state"], master.IDENTIFIED, "the sale reverses as it always did")
        checks.equal(
            back.get("order_released"),
            {"key": key, "sku": "9191486"},
            "and the response NAMES the line it released, so a screen can say the order "
            "moved without a second request",
        )
        checks.equal(
            back.get("order_effect"),
            "released",
            "finding #4: an OPEN order's own reversal answers 'released', never the "
            "'filled_by_hand' a SHIPPED order's reversal answers — the two claims are "
            "opposites and a screen must not read one when the field says the other",
        )

        after = Store().read().ledger.recorded(key, "9191486")
        checks.equal(
            after.fulfilled,
            0,
            "THE DIVERGENCE ITSELF: the line no longer counts this copy fulfilled",
        )
        checks.ok(
            capture_id not in after.copies,
            "and the copy is off the line's own list, not just off its count",
        )
        checks.equal(
            Store().read().ledger.holder_of(capture_id),
            None,
            "and the reverse index agrees: nothing holds this copy any more",
        )

        # ------------------------------------------------- a sale with no holder releases none
        unheld = capture_server.do_mark_sold(4, 1, {})
        checks.equal(
            unheld.get("order_released"), None, "selling it again has nothing to release"
        )
        back_again = capture_server.do_mark_sold(4, 1, {"undo": True})
        checks.equal(
            back_again.get("order_released"),
            None,
            "and reversing THAT sale releases nothing either — the ledger has already let "
            "this copy go, and a second release would be a fabricated write",
        )

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
            # DIRECT FIELD WRITE, NOT `_bind`: same reason as `check_mark_sold` — `bind_sku`
            # would add a `sku_bound` line to the exact history sequence this function
            # checks below.
            card = snapshot.inventory.cards["3/1"]
            card.sku, card.condition = "8608859", "Near Mint Holofoil"
            snapshot.inventory.set_state("3/1", master.IDENTIFIED)
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

        # THE ASYMMETRY SURVIVES AND ITS TERMS CHANGED (D115). This asserted `live` alone,
        # which distinguished the two doors while a sale edited the reading down. Neither
        # door touches the reading now, so `live == 1` no longer says anything about
        # retirement at all — it is the COUNTER that separates them, and asserting the
        # reading by itself would be a green check over a distinction that had disappeared.
        retired_record = after.inventory.listing_for("8608859")
        checks.equal(
            (retired_record.live, retired_record.sold_here, retired_record.live_estimate),
            (1, 0, 1),
            "AND A RETIREMENT MOVES NEITHER THE READING NOR THE COUNTER — the deliberate "
            "asymmetry with the sale: `live` is TCGplayer's own quantity and TCGplayer never "
            "saw a retirement, and `sold_here` counts copies that LEFT TCGPLAYER, which a "
            "retired card did not. The listing is still up with one fewer copy behind it, "
            "and pulling it down is a TCGplayer action the next join observes (D8, D11). A "
            "sale in the same place would read (1, 1, 0)",
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
            photo_of(3, 1).is_file(),
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
                "undo the retirement" in str(caught),
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
                "undo it on the card itself" in str(caught).lower() and "retirement" in str(caught),
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
                "undo it first" in str(caught) and "sale was a mistake" in str(caught),
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
        append_history(
            {"at": master.now(), "event": event, "position": "7/1", **extra}
            for event, extra in (
                (master.CAPTURED, {}),
                (master.RETIRED, {"reason": "lost"}),
                (master.SOLD, {}),
            )
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
        append_history(
            {"at": master.now(), "event": event, "position": "7/2"}
            for event in (master.CAPTURED, master.SOLD, master.RETIRED)
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
        (master.SOLD, master.RETIRED, master.MOVED),
        "and the three doors out are exactly the three terminal states — `copies_on_hand` "
        "filters on this tuple, so a fourth door added without joining it would be "
        "counted as still in the box. `moved` (D83) joined it deliberately: a moved "
        "card is gone from THIS position exactly as a sold or retired one is, even "
        "though — unlike its two siblings — the card itself is still on hand, just "
        "under a different key",
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
        # HELD FOR THE SAME REASON `check_server_routes` HOLDS ITS FIRST BODY: the bytes are
        # what this section compares, and a card is named by the sha256 of its own
        # photograph (D172), so there is no shared constant to compare against any more.
        shot_one = capture_payload(
            3, set_hint="sv9", variant="holo", capture_id="t7-shot-one"
        )
        capture_server.do_capture(shot_one)
        shot_two = capture_payload(3, capture_id="t7-shot-two")
        capture_server.do_capture(shot_two)

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
        photo = photo_of(3, 1)
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
            capture_named("3/1").metadata_finish,
            ("normal",),
            "the seeded drift is REAL — the reader believes the drifted sidecar, which "
            "is what makes the repair below a repair and not a restatement",
        )

        before = Store().read().inventory.get("3/1")
        captured_at = before.captured_at
        checks.equal(before.capture_id, "t7-shot-one", "and the record still names shot one")
        checks.equal(
            photo.read_bytes(), sent_image(shot_one), "and the first photograph is on disk"
        )

        body = capture_server.do_reshoot(3, 1, dict(reshoot_payload))

        checks.equal(
            photo.read_bytes(),
            JPEG_RESHOT,
            "THE BYTES ON DISK ARE THE NEW PHOTOGRAPH'S — same path, same position, "
            "allocator never involved. The path is the same because `cid` is FROZEN at issue "
            "(D172): a re-shoot replaces the bytes behind a name that does not move, which "
            "is also the one place a card's name and its photograph's digest may differ",
        )
        checks.equal(
            sorted(photos.stored_names()),
            sorted({photo.stem, photo_of(3, 2).stem}),
            "and the OLD PHOTO IS GONE — replaced, not archived (D26): an archived copy "
            "would be scanned as a third capture and billed as one. Asserted over the whole "
            "content store rather than one directory's listing, because two cards' shards "
            "are only the same directory by coincidence of their first two hex",
        )
        checks.equal(
            len(stored_captures()),
            2,
            "scan() still finds exactly two captures, so the re-shoot costs one "
            "identification, not two",
        )

        repaired = capture_named("3/1")
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
                "undo it first" in str(caught) and "sold" in str(caught),
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
                "undo the retirement" in str(caught),
                "naming the retirement's reversal as its way back — two codes, because "
                "the remedies differ",
                f"message was: {caught}",
            )
        checks.equal(
            photo_of(3, 2).read_bytes(),
            sent_image(shot_two),
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


CHECKS = (
    check_undo,
    check_remove_and_box_delete,
    check_graveyard,
    check_queues,
    check_queue_starvation,
    check_listing_release,
    check_queue_supersede,
    check_queue_refresh,
    check_queue_refresh_agreement,
    check_queue_refresh_reading,
    check_review_answer,
    check_group_answer,
    check_mark_sold,
    check_mark_sold_releases_ledger,
    check_retire,
    check_reshoot,
)
