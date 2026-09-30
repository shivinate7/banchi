"""T7 group: history reads, the sidecar seam, capture claims.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import json

from datetime import datetime
from http import HTTPStatus
from harness.tests import Checks
from identify import sidecar
from pipeline import games
from server import capture_server
from store import db, files, master, photos, queues
from store.session import Store
from harness.tests.t7.common import (
    CANDIDATES,
    NEVER_BOUND_IDENTITY_SNAPSHOT,
    _bind,
    _seed_sku_table,
    answers,
    capture_named,
    capture_payload,
    entry,
    events_for,
    fake_cid,
    isolated_home,
    last_event,
    photo_of,
    refusal,
    stored_captures,
)


def check_history(checks: Checks) -> None:
    """The three routes that write without moving a card between states.

    THE ONLY APPEND-ONLY FILE IN THE STORE, which is what makes this worth a section. Every
    other file here is replaced whole on every write, so each of them answers "what does this
    card say now" and none of them can answer "what did it say in August". `docs/debts/`
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
            "a PUT correction appends one event — the gap docs/debts/ recorded from "
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
            snapshot.inventory.set_state("4/2", master.IDENTIFIED)
            _bind(snapshot, "4/2", "8608860")
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
            _seed_sku_table(snapshot, CANDIDATES)

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
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            "and the FULL snapshot the answer REPLACED — the blocker's regression (D28):"
            " this line used to log only what was written, so the log held everything "
            "needed to audit an answer and nothing needed to reverse one — widened past "
            "the wire's own four fields on review (D28: undo must be exact, over every "
            "field bind_sku can touch: identity_source/bound_by/bound_at/read_disputes "
            "too, not only sku/condition/set_name/rarity)",
        )

        # ------------------------------------------------- the answer's reversal (D28)
        # Wrapped for `answers`' reason: the reversal refusing IS a failure mode of the
        # lines under test, and an escape here would hide the hazard walk at the end of
        # this section — the one case in this file that guards a live-bug shape.
        #
        # READ BEFORE THE UNDO, so `withdrew`'s own expectation is the card's REAL state
        # at that instant rather than a hand-typed guess at `bound_at`'s timestamp — the
        # one field `Inventory.restore_identity` re-stamps rather than restores verbatim
        # (its own docstring, `unbind_sku`'s precedent), so it cannot be predicted, only
        # read.
        before_undo_snapshot = Store().read().inventory.identity_snapshot("5/1")
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
            before_undo_snapshot,
            "carrying what came OFF the card — the FULL identity and its binding "
            "bookkeeping, not only sku/condition, so the log states the complete fact",
        )
        checks.equal(
            unanswered.get("restored"),
            NEVER_BOUND_IDENTITY_SNAPSHOT,
            "...and what went back on — both are FULL snapshots now, because neither is "
            "derivable from the other once the card has moved on again",
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


def check_history_scoped_read(checks: Checks) -> None:
    """`db.events_at` is a scope, not a rewrite: at any key, it must equal the box-filtered
    slice of the full log a reversal reader already gets today, one row at a time, filtered
    in Python. The one thing worth proving on purpose is the `renumbered` case (D10 ruling
    1) — the line that sits at the DELETED card's key, not any mover's, and that a
    box-narrower scope (bare `position = key`) would have dropped silently.
    """
    checks.note("")
    checks.note("HISTORY — events_at is scoped to the box, not the position")

    with isolated_home():
        for _ in range(3):
            capture_server.do_capture(capture_payload(3))
        for _ in range(2):
            capture_server.do_capture(capture_payload(7))  # a second box, for cross-box isolation

        # A correction and an answer at 3/1, so the box has more than one event kind.
        capture_server.do_put_card(3, 1, {"variant": "reverse_holo"})

        # A mid-box delete of 3/1 renumbers 3/2 and 3/3 down by one and logs `renumbered` at
        # position "3/1" — the DELETED key, per server/capture_server.py:do_remove_card.
        # `capture_id` is required by that route (an aim check against a replayed request);
        # none of the captures above sent one, so the stored record's own is None.
        capture_server.do_remove_card(3, 1, {"capture_id": None})

        full = Store().history()

        conn = db.connect(files.inventory_dir())
        try:
            scoped = db.events_at(conn, master.position_key(3, 1))
        finally:
            conn.close()

        expected = [
            e for e in full
            if str(e.get("position", "")).split("/", 1)[0] == "3"
        ]
        checks.equal(
            scoped, expected,
            "events_at(3/1) equals the box-3 slice of the full history, byte for byte",
        )

        renumbered = [e for e in scoped if e.get("event") == capture_server.RENUMBERED]
        checks.ok(
            len(renumbered) == 1,
            "and the renumbered marker — filed at the DELETED key, not any mover's — is "
            "still visible: a position-only scope would have dropped it",
            f"scoped renumbered events: {renumbered!r}",
        )

        cross_box = [e for e in scoped if str(e.get("position", "")).split("/", 1)[0] == "7"]
        checks.equal(
            cross_box, [],
            "and box 7's events are absent: the scope is one box, never the whole store",
        )

        # The reversal itself still works end to end through the new path.
        conn = db.connect(files.inventory_dir())
        try:
            scoped_32 = db.events_at(conn, "3/2")
        finally:
            conn.close()
        checks.equal(
            capture_server._state_before_sale(scoped_32, "3/2"),
            capture_server._state_before_sale(Store().history(), "3/2"),
            "and the reader that actually decides an undo agrees, scoped or not",
        )


def check_history_scoped_uses_index(checks: Checks) -> None:
    """`events_at`'s scope is provable in code, but a session six months from now could
    "simplify" the WHERE clause back into a full scan and every functional test above would
    still pass — the box-3 slice of an unscoped read is still the box-3 slice. This is the
    row that would catch that: it asserts the query plan, not the query's output.
    """
    checks.note("")
    checks.note("HISTORY — events_at reads the index, not the table")

    with isolated_home():
        capture_server.do_capture(capture_payload(3))
        conn = db.connect(files.inventory_dir())
        try:
            plan = conn.execute(
                "EXPLAIN QUERY PLAN SELECT id, payload FROM events WHERE position GLOB ? "
                "ORDER BY id",
                ("3/*",),
            ).fetchall()
        finally:
            conn.close()
        plan_text = " | ".join(str(row) for row in plan)
        checks.ok(
            "USING INDEX events_position" in plan_text,
            "the scoped query plan names the events_position index",
            plan_text,
        )
        checks.ok(
            "SCAN events" not in plan_text,
            "and never falls back to a full table scan",
            plan_text,
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

        captures = stored_captures()
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

        keys = sorted(c.key for c in captures)
        checks.equal(
            keys,
            ["3/1", "3/2", "4/1"],
            "every capture's key equals store.master.position_key. SORTED, BECAUSE SCAN "
            "ORDER IS NO LONGER POSITION ORDER (D172): `scan` walks its root in filename "
            "order and a filename is now a digest, so the sequence is whichever card hashed "
            "low. Nothing downstream depends on it — `cmd_identify` keys every request by "
            "`Capture.key` — and a case that reached for `[0]` now names the position it "
            "meant, through `capture_named`",
        )

        first = capture_named("3/1")
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
            capture_named("3/2").metadata_finish is None,
            "a card captured with no toggle records no claim — absent, not null (D3 rung 1)",
        )

        # THE REGRESSION. A correction that stops at inventory.json never reaches the
        # variant ladder. This was broken while passing its own route test.
        capture_server.do_put_card(3, 2, {"variant": "holo"})
        corrected = capture_named("3/2")
        checks.equal(
            corrected.metadata_finish,
            ("holo",),
            "a PUT correction reaches the SIDECAR, which is what identify reads",
        )

        capture_server.do_put_card(3, 1, {"set_hint": "sv3pt5"})
        after = capture_named("3/1")
        checks.equal(after.set_hint, "sv3pt5", "a hint-only PUT updates the hint")
        checks.equal(
            after.metadata_finish,
            ("reverse_holo",),
            "and leaves an already-recorded finish alone",
        )

        # The money rule, both directions. `scan()` counts photos, and every photo it finds
        # is a paid Batch request. The root it walks is the CONTENT STORE now (D172), and
        # `store/photos.py` argues at length why that store is a SIBLING of `captures/`
        # rather than a directory inside it: one under `captures/cards/` would be swept by
        # any run pointed at the directory above it, and every card in it billed twice.
        stray = photos.root() / "aa" / "stray.png"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_bytes(b"\x89PNG\r\n\x1a\n")
        checks.equal(
            len(stored_captures()),
            4,
            "a stray .png under the content store WOULD be scanned — 4 paid requests, not 3",
        )
        stray.unlink()

        render = files.home() / "captures" / "ui" / "pull-confirm.png"
        render.parent.mkdir(parents=True, exist_ok=True)
        render.write_bytes(b"\x89PNG\r\n\x1a\n")
        checks.equal(
            len(stored_captures()),
            3,
            "but a render under captures/ui/ is outside the root and costs nothing — and so "
            "is every photograph, now that the two roots are siblings",
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
                photo_of(3, 3)
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
                photo_of(3, 4)
            ).read_text("utf-8")
        )
        checks.ok(
            "variant" not in empty_raw,
            "while an empty claim writes NO KEY — absent, not null and not `[]`; the file "
            "stays a record of claims actually made (D3 rung 1)",
            f"sidecar was: {empty_raw}",
        )

        both = {c.key: c for c in stored_captures()}
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

        # A SECOND COPY OF THE MONEY-RULE BLOCK STOOD HERE AND ASSERTED NOTHING: it wrote a
        # stray `.png` into the capture root and ended the function, with no `checks` call
        # after it and no `unlink`. The live copy is forty lines up and now reads the content
        # store, which is the root that costs money. Deleted rather than repointed, because
        # two identical seeds and one assertion is the shape that made it invisible.


# ------------------------------------------------------------------ the capture-claim chain


def check_capture_claim_chain(checks: Checks) -> None:
    """`store/master.py:CAPTURE_CLAIM_FIELDS` — the tuple, and the two silences it closed.

    `docs/debts/` names ten hops between the control on the capture screen and the
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
    inventory.record_capture(master.Card(box=7, index=1, cid=fake_cid("claims-7-1"), **marks))
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
    #
    # NO `cid` HERE, AND THE ABSENCE IS THE POINT (D172). The name is issued once, at the
    # birth of the record, so the existing-record branch never looks at it — passing one
    # would be describing a re-record as a naming, which is the one thing a re-record must
    # not be able to do. The card created above keeps the name it was born with.
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
    with isolated_home(), Store().write() as snapshot:
        checks.raises(
            master.UnknownClaim,
            # DELIBERATELY NAMELESS, AND THE ORDER IN `allocate_capture` IS WHY (D172). The
            # claim check runs before the index is computed and therefore long before
            # `record_capture`'s refusal for a nameless card, so this case still hears
            # `UnknownClaim` — which is the refusal it is about. Passing a `cid` would make
            # the case pass for a reason it is not testing, and would hide a reordering that
            # made a typo answer `UnnamedCard` instead.
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
            capture_server.sidecar_path(photo_of(box, index)).read_text(
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

        claimed, unclaimed = capture_named("6/1"), capture_named("6/2")
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
        # leave the others standing. That is the failure `docs/debts/` calls the harder one
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
            capture_named("6/1").note,
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


CHECKS = (
    check_history,
    check_history_scoped_read,
    check_history_scoped_uses_index,
    check_sidecar_seam,
    check_capture_claim_chain,
    check_game_and_note_seam,
)
