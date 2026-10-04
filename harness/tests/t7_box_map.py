"""T7's box map cases (D262, D264, D294): a section moves whole, and nothing it owns is lost.

Protects: Moving a section moves it whole and loses nothing it owns.
Governs: D145, D262, D264, D294

A SIBLING OF `t7_store_and_seams.py`, NOT A NEW HARNESS TEST. `t7_store_and_seams.run()` calls
every `check_*` here, so T7's verdict carries them and the harness still has ten tests. They
live in their own file because they share one fixture (a box of named sections). The other
groups live in `harness/tests/t7/`.

Every case below was observed FAILING before its fix was kept.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
from typing import List, Optional, Tuple

from harness.tests.t7_store_and_seams import (
    Checks,
    QuietHandler,
    Store,
    capture_payload,
    capture_server,
    back_of,
    error_code,
    fake_cid,
    isolated_home,
    join,
    master,
    refusal,
    resolve,
    seam_run,
)
from harness.tests.t7_store_and_seams import request as http_request


def check_box_map_safety(checks: Checks) -> None:
    """Slice 0 (D262, D264): a move keeps a paid answer and a price.

    1. A card with a live paid reading could move. The batch then writes onto the tombstone
       and the moved card stays unidentified, with the money spent.
    2. A moved card fell off its run. `realign` looked only in the run's own boxes, so the
       card read as `departed` and lost its row on Pricing (D145 measured 99 such cards).
    3. A card could move only once. The second tombstone took the first one's
       `moved:<name>`, and `cards_cid` is UNIQUE, so the commit failed.
    """
    checks.note("")
    checks.note("BOX MAP SLICE 0 — the move guard, the join follow, the second move (D262)")
    from store import submissions as claims

    cards = [
        (5, 1, "Dunsparce", "120/159", None),
        (5, 2, "Dunsparce", "120/159", "reverse_holo"),
        (5, 3, "Articuno", "161/159", "holo"),
    ]
    with isolated_home():
        run, _ = seam_run(checks, cards, join=False)
        with Store().write() as snapshot:
            for box, index, name, number, finish in cards:
                snapshot.inventory.record_identification(
                    master.position_key(box, index),
                    name=name, number=number, printed_total="159",
                    confidence="high", detected_finish=finish, run=run.name,
                )
            snapshot.submissions.entries["r-live"] = claims.Submission(
                receipt="r-live", pid=os.getpid(), started_at=master.now(),
                keys=["5/3"], state=claims.STATE_LIVE,
            )

        refusal(
            checks,
            lambda: capture_server.do_move_cards(5, {"to_box": 7, **back_of(7), "indices": [3]}),
            "card_being_read",
            "a card with a live paid reading does not move (D262, D174)",
        )
        checks.ok(
            Store().read().inventory.cards["5/3"].state != master.MOVED,
            "and nothing moved: the card is still where the paid answer will land",
        )

        capture_server.do_move_cards(5, {"to_box": 7, **back_of(7), "indices": [2]})
        loaded = resolve.load(run, {"pokemon": run.path("export.csv")})
        where = sorted(
            (p.box, p.index) for match in loaded.matches.values() for p in match.positions
        )
        checks.ok(
            (7, 1) in where and (5, 2) not in where,
            "the join follows the moved card to its new box, and it keeps its row (D262)",
            f"positions {where}",
        )

        # The second move of one card commits: its second tombstone has its own name.
        try:
            capture_server.do_move_cards(7, {"to_box": 8, **back_of(8), "indices": [1]})
            twice = True
        except Exception as caught:  # noqa: BLE001 — the failure is the assertion
            twice = f"{type(caught).__name__}: {caught}"
        checks.ok(twice is True, "a card that moved once can move again", str(twice))
        follow = getattr(resolve, "follow_moved", None)
        chain = follow(Store().read().inventory, "5/2")[0] if follow else None
        checks.equal(chain, "8/1", "and a link of two hops is followed to the card")

        # The follow is checked by NAME. A link whose card has another name is refused and
        # named, never joined.
        with Store().write() as snapshot:
            snapshot.inventory.cards["5/2"].cid = f"{master.MOVED_CID_PREFIX}{'0' * 64}"
        _, moved, departed, _ = resolve.realign(
            {"cards": {"5/2": {"box": 5, "index": 2}}}, Store().read().inventory
        )
        checks.ok(
            moved == {} and departed == ["5/2"],
            "a move link whose card has another name is refused and named, not followed",
            f"moved {moved}, departed {departed}",
        )


def _drawn(body: dict) -> dict:
    """A Map drop as the Map sends it: with the destination's `layout_token` as it stands now
    (`docs/specs/subbox-capture.md` 1.6). A body that names its own token keeps it."""
    to_box = body.get("to_box")
    if to_box is None or "layout_token" in body:
        return body
    return dict(body, layout_token=Store().read().inventory.layout_token(int(to_box)))


def _drag_range(box: int, body: dict) -> dict:
    return capture_server.do_move_range(box, _drawn(body))


def _drag_sections(box: int, body: dict) -> dict:
    return capture_server.do_move_sections(box, _drawn(body))


def _digests(boxes: List[int]) -> dict:
    """The Confirm gate's own freshness snapshot: `_layout_digest`, ONLY LAYOUT (the owner's
    ruling, 2026-09-27), not `layout_token` alone (the strict review's first finding,
    2026-09-27 — a card arriving or leaving a section changes no divider, so a token-only
    check cannot see it) and not `_box_digest` either (the re-review's finding, 2026-09-28 —
    every field of every record is too much: a note or a photo edit changes nothing a layout
    move reads, and refusing the draft over it was the defect)."""
    inv = Store().read().inventory
    return {str(b): capture_server._layout_digest(inv, b) for b in boxes}


def _shelf() -> None:
    """Two boxes of named sections, in whatever isolated home is current.

    Origins: Commons (3 cards), Uncommons (4), Rares (2). Mixed: Singles (2), Promos (2).
    Every card is named `<box letter><n>` so a walk reads as a string.
    """
    capture_server.do_create_box({"box": 1, "name": "Origins"})
    capture_server.do_create_box({"box": 2, "name": "Mixed"})
    with Store().write() as snapshot:
        inv = snapshot.inventory
        for box, letter, count in ((1, "o", 9), (2, "m", 4)):
            for index in range(1, count + 1):
                card = master.Card(box=box, index=index, cid=fake_cid(f"shelf-{box}-{index}"))
                inv.record_capture(card)
                inv.cards[master.position_key(box, index)].name = f"{letter}{index}"
        inv.set_sections(1, [1, 4, 8])
        inv.set_section_names(1, {1: "Commons", 2: "Uncommons", 3: "Rares"})
        inv.set_sections(2, [1, 3])
        inv.set_section_names(2, {1: "Singles", 2: "Promos"})


def _walk(box: int) -> List[str]:
    """The box's on-hand cards by name, in the order they stand."""
    inv = Store().read().inventory
    return [
        card.name for _, _, card in inv.records_in(box)
        if card.state not in master.TERMINAL_STATES
    ]


def _sections(box: int) -> List[Tuple[Optional[str], int]]:
    """`(name, count)` per section, as `GET /boxes` draws them."""
    row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == box)
    return [(d["name"], d["count"]) for d in row["sections_detail"]]


def _label(box: int, name: str) -> str:
    inv = Store().read().inventory
    for _, _key, card in inv.records_in(box):
        if card.name == name and card.state not in master.TERMINAL_STATES:
            return join.said_place(inv, card.box, card.index)
    return "missing"


def check_section_moves(checks: Checks) -> None:
    """The box map's write (D264, D294): a section moves whole, before any section.

    Each case below was red before `do_move_sections` existed (the route answered nothing),
    and the placement cases were red again against a first draft that appended at the back.
    """
    checks.note("")
    checks.note("BOX MAP — section moves, placement, reorder, merge, split, undo (D264, D294)")

    with isolated_home():
        _shelf()
        before_digests = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        body = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2, "before": 2})
        checks.equal(
            _walk(2), ["m1", "m2", "o4", "o5", "o6", "o7", "m3", "m4"],
            "a section lands at the chosen gap, in order: between Singles and Promos",
        )
        checks.equal(
            _sections(2), [("Singles", 2), ("Uncommons", 4), ("Promos", 2)],
            "the destination gains the divider WITH its name, and Promos becomes Section 3",
        )
        checks.equal(
            _sections(1), [("Commons", 3), ("Rares", 2)],
            "the source loses the divider, and the other names stay",
        )
        checks.equal(
            (_label(2, "o4"), _label(2, "m3"), _label(1, "o8")),
            ("Mixed, Section 2, Card 1", "Mixed, Section 3, Card 1", "Origins, Section 2, Card 1"),
            "every label counts in the box's new order: the one label formula, fed orders",
        )
        receipt = body["receipt"]
        checks.ok(
            receipt["heading"] == "Move 4 cards from Origins to Mixed."
            and "find the divider Uncommons. Its first card is o4. Its last card is o7." in receipt["steps"][0]
            and "find the divider Promos. Put them just on the far side of it" in receipt["steps"][2],
            "the receipt is the physical instruction, landmarks by name, in the owner's orientation",
            str(receipt),
        )
        checks.ok(
            "In Origins, Rares moves from Section 3 to Section 2." in receipt["renumbered"]
            and "In Mixed, Promos moves from Section 2 to Section 3." in receipt["renumbered"],
            "and it says which section numbers changed",
            str(receipt["renumbered"]),
        )

        capture_server.do_undo_section_move({"move": body["move"]})
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)},
            before_digests,
            "undo restores both boxes EXACTLY: every card record and both box records",
        )
        again = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2, "before": 1})
        checks.equal(
            _walk(2)[:4], ["o4", "o5", "o6", "o7"],
            "the same section can move again after an undo, and in front of section 1",
        )
        capture_server.do_put_box(2, {"name": "Mixed Singles"})
        refusal(
            checks, lambda: capture_server.do_undo_section_move({"move": again["move"]}),
            "box_changed_since", "undo refuses once either box has changed since the move",
        )

    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 3, "last": 3, "to_box": 1, "before": 1})
        checks.equal(
            _walk(1), ["o8", "o9", "o1", "o2", "o3", "o4", "o5", "o6", "o7"],
            "a reorder in one box moves the section to the front, and no card changes key",
        )
        checks.equal(
            _sections(1), [("Rares", 2), ("Commons", 3), ("Uncommons", 4)],
            "and every divider and name travels with its section",
        )
        inv = Store().read().inventory
        checks.equal(
            [card.index for _, _, card in inv.records_in(1)], [8, 9, 1, 2, 3, 4, 5, 6, 7],
            "the stored index never moves (D10, D58): only the order does (D294)",
        )
        status, row = capture_server.do_capture(capture_payload(1))
        checks.ok(
            _walk(1)[-1] is None and _sections(1)[-1] == ("Uncommons", 5),
            "the next capture still lands at the near end, in the last section",
            str(_sections(1)),
        )

    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 1, "last": 1, "to_box": 2})
        checks.equal(
            _sections(1), [("Uncommons", 4), ("Rares", 2)],
            "moving section 1 re-anchors the next divider at the front, name and all",
        )
        checks.equal(
            _sections(2), [("Singles", 2), ("Promos", 2), ("Commons", 3)],
            "and with no gap named, the section lands at the near end",
        )

    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 1, "last": 3, "to_box": 2})
        checks.equal(
            _sections(2),
            [("Singles", 2), ("Promos", 2), ("Commons", 3), ("Uncommons", 4), ("Rares", 2)],
            "a merge moves every section, in order, dividers and names carried",
        )
        checks.equal(_walk(1), [], "and the merged box is left empty")

    with isolated_home():
        _shelf()
        body = _drag_sections(1, {"first": 2, "last": 3, "new_box": True})
        checks.equal(
            (_sections(1), _sections(body["created"])),
            ([("Commons", 3)], [("Uncommons", 4), ("Rares", 2)]),
            "a split moves the sections from one to the last into a new box",
        )
        checks.equal(
            Store().read().inventory.box(body["created"]).name, "Box 3",
            "and a new box gets its stored default name",
        )
        capture_server.do_undo_section_move({"move": body["move"]})
        checks.ok(
            Store().read().inventory.box(body["created"]) is None,
            "undoing a split removes the box it made",
        )

    with isolated_home():
        _shelf()
        refusal(
            checks,
            lambda: _drag_sections(
                1, {"first": 2, "to_box": 3, "aim": {"count": 4, "first": "x", "last": "y"}}
            ),
            "section_changed", "a stale aim refuses, and nothing moves",
        )
        from store import submissions as claims

        with Store().write() as snapshot:
            snapshot.submissions.entries["r"] = claims.Submission(
                receipt="r", pid=os.getpid(), started_at=master.now(),
                keys=["1/6"], state=claims.STATE_LIVE,
            )
        capture_server.do_create_box({"box": 3, "name": "Spare"})
        refusal(
            checks, lambda: _drag_sections(1, {"first": 2, "to_box": 3}),
            "card_being_read", "a section holding a card with a live paid reading refuses",
        )
        checks.equal(
            _walk(1), [f"o{i}" for i in range(1, 10)],
            "and a refusal part way through writes nothing: the cards before it did not move",
        )

    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 3, "last": 3, "to_box": 1, "before": 1})
        capture_server.do_remove_card(1, 2, {"capture_id": None})
        checks.equal(
            _walk(1), ["o8", "o9", "o1", "o3", "o4", "o5", "o6", "o7"],
            "a mid-box delete in a box with an order keeps every other card in its place",
        )



def _keys(box: int) -> dict:
    """`index -> order key` for every record in the box."""
    inv = Store().read().inventory
    return {card.index: card.order for _, _, card in inv.records_in(box)}


def _changed(before: dict, after: dict) -> List[int]:
    return sorted(i for i in after if i in before and before[i] != after[i])


def check_order_key_migration(checks: Checks) -> None:
    """Schema 13 (D294, "A key on each card"): every card gets the key its index already is.

    Red before `_add_card_order` existed: the column was missing and every payload had no key.
    """
    import sqlite3

    from store import db, files

    checks.note("")
    checks.note("BOX MAP — the order key migration, schema 12 to 13 (D294)")
    with isolated_home():
        _shelf()
        labels_before = [_label(1, f"o{i}") for i in range(1, 10)]
        directory = files.inventory_dir()
        conn = sqlite3.connect(str(db.path(directory)))
        conn.execute("ALTER TABLE cards DROP COLUMN ord")
        conn.execute("UPDATE cards SET payload = json_remove(payload, '$.order')")
        conn.execute("UPDATE meta SET value = '12' WHERE key = 'schema'")
        conn.commit()
        conn.close()

        inv = Store().read().inventory
        checks.equal(
            {card.index: card.order for _, _, card in inv.records_in(1)},
            {i: float(i) for i in range(1, 10)},
            "every card's key is its index after the upgrade: today's order, unchanged",
        )
        conn = sqlite3.connect(str(db.path(directory)))
        column = conn.execute("SELECT count(*) FROM cards WHERE ord = idx").fetchone()[0]
        stamp = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0]
        conn.close()
        checks.equal((column, stamp), (13, str(db.SCHEMA_VERSION)), "the column is filled too, and the file is stamped current")
        checks.equal(
            [_label(1, f"o{i}") for i in range(1, 10)], labels_before,
            "no label moves: D58's counted numbers are exactly what they were",
        )

        # IDEMPOTENT: a key a card already has is kept when the step runs again.
        _drag_sections(1, {"first": 3, "to_box": 1, "before": 1})
        placed = _keys(1)
        conn = sqlite3.connect(str(db.path(directory)))
        conn.execute("UPDATE meta SET value = '12' WHERE key = 'schema'")
        conn.commit()
        conn.close()
        checks.equal(_keys(1), placed, "a second upgrade keeps every key a card already has")


def check_per_card_order(checks: Checks) -> None:
    """Each kind of move writes the key of each moved card, and no other card (D294)."""
    checks.note("")
    checks.note("BOX MAP — per-card order keys after each kind of move (D294)")

    with isolated_home():
        _shelf()
        src, dst = _keys(1), _keys(2)
        _drag_sections(1, {"first": 2, "to_box": 2, "before": 2})
        after_dst = _keys(2)
        checks.equal(_changed(dst, after_dst), [], "a section move into a box writes no card already there")
        checks.equal(_keys(1), src, "and no key in the box it left: the tombstones keep theirs")
        arrived = sorted(i for i in after_dst if i not in dst)
        keys = [after_dst[i] for i in arrived]
        checks.ok(
            len(arrived) == 4 and all(dst[2] < k < dst[3] for k in keys) and keys == sorted(keys),
            "the four cards that arrived take keys between Singles' last card and Promos' first, in order",
            str(after_dst),
        )

    with isolated_home():
        _shelf()
        before = _keys(1)
        _drag_sections(1, {"first": 3, "to_box": 1, "before": 2})
        checks.equal(
            _changed(before, _keys(1)), [8, 9],
            "a reorder writes the keys of the moved section's cards and of no other card",
        )
        checks.equal(
            _walk(1), ["o1", "o2", "o3", "o8", "o9", "o4", "o5", "o6", "o7"],
            "and the walk reads them where they were put",
        )

    with isolated_home():
        _shelf()
        dst = _keys(2)
        _drag_sections(1, {"first": 1, "last": 3, "to_box": 2})
        checks.equal(_changed(dst, _keys(2)), [], "a merge writes no card the destination already held")
        body = None

    with isolated_home():
        _shelf()
        body = _drag_sections(1, {"first": 2, "last": 3, "new_box": True})
        keys = _keys(body["created"])
        checks.equal(
            sorted(keys.values()), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "a split into a new box gives its cards whole-number keys from 1",
        )


def check_card_moves(checks: Checks) -> None:
    """The next slice (owner, 2026-09-25): one card or a range, before any card or at any
    section's end, in the same one write, with the same receipt and the same undo.

    Red before `do_move_range` existed: the route answered nothing.
    """
    checks.note("")
    checks.note("BOX MAP — single cards and ranges (D264, the next slice)")

    with isolated_home():
        _shelf()
        before = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        dst = _keys(2)
        body = _drag_range(
            1, {"indices": [5, 6], "to_box": 2, "before_card": 2}
        )
        checks.equal(
            _walk(2), ["m1", "o5", "o6", "m2", "m3", "m4"],
            "a range lands in front of the card named, in order",
        )
        checks.equal(_changed(dst, _keys(2)), [], "and no card already in that box is written")
        checks.equal(
            _sections(2), [("Singles", 4), ("Promos", 2)],
            "the range joins that card's section, and no divider moves",
        )
        checks.equal(_sections(1), [("Commons", 3), ("Uncommons", 2), ("Rares", 2)], "and the source keeps its dividers")
        checks.ok(
            body["receipt"]["heading"] == "Move 2 cards from Origins to Mixed."
            and "find m2. Put them just on the far side of it" in body["receipt"]["steps"][2],
            "the receipt is the physical instruction",
            str(body["receipt"]),
        )
        capture_server.do_undo_section_move({"move": body["move"]})
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}, before,
            "undo puts a card move back exactly",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
        checks.equal(_walk(1)[0], "o9", "one card moves to the far back of its own box")
        checks.equal(
            _sections(1), [("Commons", 4), ("Uncommons", 4), ("Rares", 1)],
            "and it joins section 1: the front divider moves with it",
        )
        _drag_range(1, {"indices": [2], "to_box": 1, "before_card": 4})
        checks.equal(
            _walk(1), ["o9", "o1", "o3", "o2", "o4", "o5", "o6", "o7", "o8"],
            "in front of the first card of a section, the card joins THAT section",
        )
        checks.equal(
            [n for n, _ in _sections(1)], ["Commons", "Uncommons", "Rares"],
            "and every section keeps its name",
        )
        checks.equal(_sections(1)[1], ("Uncommons", 5), "the card counts in Uncommons now")

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [1, 2], "to_box": 2, "section_end": 1})
        checks.equal(
            _walk(2), ["m1", "m2", "o1", "o2", "m3", "m4"],
            "a range dropped at a section's end lands after its last card, before the next divider",
        )
        refusal(
            checks,
            lambda: _drag_range(
                1, {"indices": [3], "to_box": 1, "section_end": 3,
                    "aim": {"count": 1, "first": "x", "last": "x"}},
            ),
            "section_changed", "a stale aim refuses a card move",
        )

    with isolated_home():
        _shelf()
        # Each press halves the same gap, in front of card 2, until it is too narrow.
        for n in range(30):
            _drag_range(1, {"indices": [8 + n % 2], "to_box": 1, "before_card": 2})
        checks.equal(
            _walk(1), ["o1", "o8", "o9", "o2", "o3", "o4", "o5", "o6", "o7"],
            "one gap split thirty times still orders the box: a re-space keeps every card in place",
        )
        checks.ok(
            bool(Store().named_events("box_respaced")),
            "and the re-space is on the record, the one write that touches cards it did not move",
        )


def check_delete_after_placement(checks: Checks) -> None:
    """R3 review, item 1 and item 5: a mid-box delete writes no key, and keeps move links.

    Red before the fix: the delete slid a key that equalled its index and left a placed key
    alone, so the two groups crossed (repro A), or two cards took one key (repro B). And a
    tombstone's `moved_to` kept naming the old index after the destination slid (item 5).
    """
    checks.note("")
    checks.note("BOX MAP R3 — a mid-box delete after a placement (D294, D10 ruling 1)")

    def distinct(box: int) -> bool:
        keys = [k for k in _keys(box).values()]
        return len(keys) == len(set(keys))

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [2], "to_box": 2, "before_card": 3})
        checks.equal(_walk(2), ["m1", "m2", "o2", "m3", "m4"], "repro A: o2 stands in front of m3")
        capture_server.do_remove_card(2, 1, {"capture_id": None})
        checks.equal(
            _walk(2), ["m2", "o2", "m3", "m4"],
            "repro A: after deleting m1, o2 still stands in front of m3",
        )
        checks.ok(distinct(2), "and no two cards share a key", str(_keys(2)))
        chain, why = resolve.follow_moved(Store().read().inventory, "1/2")
        checks.equal(
            (chain, why), ("2/4", None),
            "item 5: the move link follows the card after the destination slid (o2 is at 2/4 now)",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [5, 6], "to_box": 2, "section_end": 2})
        _drag_range(2, {"indices": [3], "to_box": 2, "before_card": 1})
        before = _walk(2)
        capture_server.do_remove_card(2, 2, {"capture_id": None})
        checks.equal(
            _walk(2), [name for name in before if name != "m2"],
            "repro B: a delete after two placements keeps every other card in its place",
        )
        checks.ok(distinct(2), "repro B: and no two cards share a key", str(_keys(2)))
        labels = [_label(2, name) for name in _walk(2)]
        checks.ok(len(labels) == len(set(labels)), "and no two cards read one label", str(labels))


def check_undo_keeps_paid_answers(checks: Checks) -> None:
    """R3 review, item 2: undo is refused while a live paid reading holds a key it removes.

    Red before the fix: the undo checked only the two boxes' hashes, deleted the transplant
    the claim holds, and the paid answer would land on the tombstone's card.
    """
    from store import submissions as claims

    checks.note("")
    checks.note("BOX MAP R3 — undo and a live paid reading (D174, D262)")
    with isolated_home():
        _shelf()
        body = _drag_sections(1, {"first": 2, "to_box": 2})
        arrived = sorted(i for i in _keys(2) if i > 4)
        with Store().write() as snapshot:
            snapshot.submissions.entries["r-undo"] = claims.Submission(
                receipt="r-undo", pid=os.getpid(), started_at=master.now(),
                keys=[master.position_key(2, arrived[0])], state=claims.STATE_LIVE,
            )
        refusal(
            checks, lambda: capture_server.do_undo_section_move({"move": body["move"]}),
            "card_being_read",
            "undo refuses while a paid reading holds a card it would take away",
        )
        checks.equal(
            len([i for i in _keys(2) if i > 4]), 4,
            "and nothing was undone: the four cards are still there",
        )


def check_front_of_box(checks: Checks) -> None:
    """R3 review, item 3: one rule for the front of a box, so a far-back placement reads.

    Red before the fix: `Position` took the front as 1 and `layout_of` as the lowest key, so
    `GET /boxes` raised IndexError (a 500) after a card was placed in front of card 1.
    """
    checks.note("")
    checks.note("BOX MAP R3 — the front of the box after a far-back placement (D294)")

    def reads() -> object:
        try:
            capture_server.do_boxes()
            return True
        except Exception as caught:  # noqa: BLE001 — the failure is the assertion
            return f"{type(caught).__name__}: {caught}"

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
        _drag_sections(1, {"first": 2, "to_box": 2})
        checks.equal(reads(), True, "a sections move after a far-back placement still reads")
        checks.equal(
            _label(1, "o9"), "Origins, Section 1, Card 1",
            "and the card at the far back is card 1 of section 1",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
        capture_server.do_put_box(1, {"sections": []})
        checks.equal(reads(), True, "clearing the dividers after a far-back placement still reads")
        checks.equal(
            (_label(1, "o9"), _label(1, "o1")),
            ("Origins, Section 1, Card 1", "Origins, Section 1, Card 2"),
            "and the box is one section, counted from the card at the far back",
        )


def check_card_move_refusals(checks: Checks) -> None:
    """R3 review, items 6 to 9: what a card move refuses, and the empty box it takes."""
    checks.note("")
    checks.note("BOX MAP R3 — card move refusals, and a move into an empty box")
    with isolated_home():
        _shelf()
        refusal(
            checks,
            lambda: _drag_range(1, {"indices": [2], "to_box": 1, "before_card": 3}),
            "before_invalid", "item 6: a card put back in front of its own next card is a no-op, refused",
        )
        refusal(
            checks,
            lambda: _drag_range(1, {"indices": [3], "to_box": 1, "section_end": 1}),
            "before_invalid", "item 6: the last card of a section put at that section's end is refused",
        )
        _drag_range(1, {"indices": [5], "to_box": 2, "section_end": 2})
        refusal(
            checks,
            lambda: _drag_range(1, {"indices": [6], "to_box": 1, "before_card": 5}),
            "before_invalid", "item 7: a tombstone is not a card to put anything in front of",
        )
        refusal(
            checks,
            lambda: _drag_range(1, {"indices": [2], "to_box": 9, "section_end": 1}),
            "box_not_found", "item 8: a box that does not exist is refused, never made",
        )
        refusal(
            checks,
            lambda: _drag_sections(1, {"first": 2, "to_box": 9}),
            "box_not_found", "item 8: and a section move to it is refused too",
        )
        checks.ok(Store().read().inventory.box(9) is None, "and no box 9 was made")
        capture_server.do_create_box({"box": 3, "name": "Empty"})
        _drag_range(1, {"indices": [2], "to_box": 3})
        checks.equal(_walk(3), ["o2"], "item 9: a card moves into an empty box")
        # NO AUTO DEFAULT (D300): a box that holds a card has more than
        # one place, so a drag that names no gap into it is refused and moves nothing.
        walks = (_walk(1), _walk(2))
        refusal(
            checks,
            lambda: _drag_range(1, {"indices": [3], "to_box": 2}),
            "section_required",
            "a drag that names no gap into a box that holds cards is refused",
        )
        checks.equal((_walk(1), _walk(2)), walks, "and no card moved")


def check_divider_editor_keys(checks: Checks) -> None:
    """R4 review, item 1: the divider editor keeps a fractional key.

    Red before the fix: `join.divider_index` cut a key to an integer, so saving the editor's
    own unchanged starts after a section move moved every fractional divider, and m2 fell into
    the moved section.
    """
    checks.note("")
    checks.note("BOX MAP R4 — the divider editor after a placement (D294)")
    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 2, "to_box": 2, "before": 2})
        before = Store().read().inventory.sections_for(2)
        labels = [_label(2, name) for name in _walk(2)]
        row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == 2)
        capture_server.do_put_box(2, {"sections": [d["start"] for d in row["sections_detail"]]})
        checks.equal(
            Store().read().inventory.sections_for(2), before,
            "saving the editor's own starts unchanged keeps every divider key",
        )
        checks.equal(
            [_label(2, name) for name in _walk(2)], labels,
            "and moves no card into another section",
        )

    with isolated_home():
        _shelf()
        _drag_sections(1, {"first": 2, "to_box": 2})
        capture_server.do_put_box(2, {"sections": [1, 5]})
        checks.equal(
            (_label(2, "m4"), _label(2, "o4"), _label(2, "o5")),
            ("Mixed, Section 1, Card 4", "Mixed, Section 2, Card 1", "Mixed, Section 2, Card 2"),
            "a divider set at a placed card starts the section at that card",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [4], "to_box": 2, "before_card": 3})
        capture_server.do_put_box(2, {"sections": [1, 3]})
        checks.equal(
            (_label(2, "m2"), _label(2, "o4"), _label(2, "m3")),
            ("Mixed, Section 1, Card 2", "Mixed, Section 2, Card 1", "Mixed, Section 2, Card 2"),
            "a divider set at a card placed between two others starts the section at THAT card",
        )


def check_delete_keeps_dividers(checks: Checks) -> None:
    """R4 review, item 2: a delete in a box nothing was placed into keeps its sections, and
    undo refuses a claim on the old key alone. Item 3: a delete clears a dead move link, and
    the renumber refusal says a tombstone moved."""
    from store import submissions as claims

    checks.note("")
    checks.note("BOX MAP R4 — dividers across a delete, the old-key claim, dead move links")
    with isolated_home():
        capture_server.do_create_box({"box": 1, "name": "Plain"})
        with Store().write() as snapshot:
            for index in range(1, 9):
                snapshot.inventory.record_capture(
                    master.Card(box=1, index=index, cid=fake_cid(f"plain-{index}"), name=f"c{index}")
                )
            snapshot.inventory.set_sections(1, [1, 5])
        capture_server.do_remove_card(1, 3, {"capture_id": None})
        checks.equal(
            (_label(1, "c5"), _label(1, "c4")),
            ("Plain, Section 2, Card 1", "Plain, Section 1, Card 3"),
            "c5 stays card 1 of section 2 after c3 is deleted: the divider stays with the card",
        )

    with isolated_home():
        _shelf()
        body = _drag_sections(1, {"first": 2, "to_box": 2})
        with Store().write() as snapshot:
            snapshot.submissions.entries["r-old"] = claims.Submission(
                receipt="r-old", pid=os.getpid(), started_at=master.now(),
                keys=["1/4"], state=claims.STATE_LIVE,
            )
        refusal(
            checks, lambda: capture_server.do_undo_section_move({"move": body["move"]}),
            "card_being_read", "undo refuses a live claim on the OLD key alone",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
        capture_server.do_remove_card(2, 5, {"capture_id": None})
        tomb = Store().read().inventory.cards["1/2"]
        checks.equal(
            tomb.moved_to, None,
            "item 3: deleting the card a tombstone points to clears the tombstone's link",
        )
        said = None
        try:
            capture_server.do_remove_card(1, 1, {"capture_id": None})
        except capture_server.BadRequest as caught:
            said = str(caught)
        checks.ok(
            said is not None and " is moved" in said and "is sold" not in said,
            "item 3: the renumber refusal says a tombstone moved, never that it sold",
            str(said),
        )


def check_merge_speed(checks: Checks) -> None:
    """R4 review, item 4: a 500-card merge into a 500-card box does linear work, not
    quadratic.

    CRIES WOLF ON WALL TIME ALONE, so wall time is no longer what this asserts (owner's
    ruling: "Trust a guard only once it goes red on the defect it guards. A guard that goes
    red when nothing is wrong is spent"; the ux-2026-09-23 review: "Timing
    guards must count work, not wall time alone"). The old `took < 1.0` failed three times
    in one day at 1.01-1.31 s under machine load 13-27, with `do_move_sections`/`_cross`/
    `_move_one` unchanged, and passed on every rerun — the machine's mood, not the merge.

    THE ASSERTION IS A ROW-READ COUNT, independent of load: `sqlite3.Connection.
    set_progress_handler` fires once per 100 SQLite VM instructions on the write's own
    connection, so counting the calls counts work SQLite actually did — proportional to
    rows scanned, not to how many statements were issued. A statement COUNT alone was
    tried and rejected here: `_positions_in`/`box_order` are one indexed `select()` call
    regardless of how many rows it returns, so a per-card destination scan that grows with
    the box shows up as almost the same statement count (+17%, measured) while it triples
    the wall time — the statement count cannot see the defect this guard exists for. The
    progress-handler tick count can: reverting `_cross`'s `slot=` reuse so `move_card`
    recomputes `next_index`/`next_key` per card (the pre-R3 defect) measured 77,355 ticks
    against a fixed 4,575 — 17x, and growing with the box, not the fixed rate below.

    Measured on the real (fixed) path, twice, to confirm linearity: 4,575 ticks for 500
    moved cards, 2,289 for 250 — ~9.15 per card either way, the R3 fix's own promise
    (`_cross`'s "next_index and next_key are read ONCE per press"). The ceiling is
    `30 * moved cards` (15,000 here): over 3x the measured linear rate, so load noise
    cannot trip it, and well under the mutation's 77,355, so a real regression does.

    Wall time stays as a LOOSE BACKSTOP ONLY, 10 s (ten times the retired 1 s bound), for a
    hang or a lock wait a tick count alone would not catch — never the assertion a reader
    should trust; the tick count is that.

    Red before R3's fix: 3.8 s, growing with the square of the box."""
    import time

    from store import db as db_module

    checks.note("")
    checks.note("BOX MAP R4 — merge speed")
    with isolated_home():
        capture_server.do_create_box({"box": 1, "name": "A"})
        capture_server.do_create_box({"box": 2, "name": "B"})
        with Store().write() as snapshot:
            for box in (1, 2):
                for i in range(1, 501):
                    snapshot.inventory.cards[master.position_key(box, i)] = master.Card(
                        box=box, index=i, cid=fake_cid(f"speed-{box}-{i}"), order=float(i),
                        state=master.CAPTURED,
                    )

        ticks = {"n": 0}
        real_connect = db_module.connect

        def counting_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)

            def _tick():
                ticks["n"] += 1
                return 0  # 0: never abort the query, only count

            conn.set_progress_handler(_tick, 100)
            return conn

        db_module.connect = counting_connect
        try:
            start = time.perf_counter()
            body = _drag_sections(1, {"first": 1, "to_box": 2})
            took = time.perf_counter() - start
        finally:
            db_module.connect = real_connect

        moved = int(body["moved"])
        ceiling = 30 * moved
        checks.ok(
            ticks["n"] < ceiling,
            "a 500-into-500 merge does linear row-read work (VM-tick count), not quadratic",
            f"{ticks['n']} ticks for {moved} moved cards, ceiling {ceiling}",
        )
        checks.ok(
            took < 10.0,
            "loose wall-clock backstop only (not what this check trusts)",
            f"{took:.2f} s",
        )


def check_r5_links_and_empty_sections(checks: Checks) -> None:
    """R5 review. Item 1: a delete that removes a moved card clears the dead move link too,
    so the next capture at that index is never taken for the moved card. Item 2: an unchanged
    editor save keeps an empty section (the plastic is still in the box) instead of refusing
    a repeat. Both were red before the fix.

    ITEM 1 HAS TWO HALVES SINCE THE UNDO SESSION (`docs/specs/undo.md` 11.8). The capture
    undo (`do_delete_card`) now refuses a moved card with `capture_built_on`, so it can no
    longer leave a dead link. Manage box's remove (`do_remove_card`) still can remove a
    moved card, and it is the route the link clearing is proved through now."""
    checks.note("")
    checks.note("BOX MAP R5 — move links on a removed card, and a save over an empty section")
    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
        moved = Store().read().inventory.cards.get("2/5")
        refusal(
            checks,
            lambda: capture_server.do_delete_card(2, 5),
            "capture_built_on",
            "the capture undo refuses a moved card, so it cannot delete it",
        )
        kept = Store().read().inventory.cards.get("2/5")
        checks.ok(
            moved is not None and kept is not None and kept.cid == moved.cid
            and Store().read().inventory.cards["1/2"].moved_to == "2/5",
            "and the moved card, its name and the link to it all stay",
        )

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
        try:
            capture_server.do_remove_card(2, 5, {"capture_id": None})
        except capture_server.BadRequest as caught:
            checks.ok(False, "Manage box's remove takes out the moved card", str(caught))
        capture_server.do_capture(capture_payload(2))
        checks.equal(
            Store().read().inventory.cards["1/2"].moved_to, None,
            "Manage box's remove clears the link, so the tombstone does not point at 2/5, "
            "which holds a new card now",
        )
        chain, _ = resolve.follow_moved(Store().read().inventory, "1/2")
        checks.equal(chain, None, "and the join does not follow it onto that new card")

    with isolated_home():
        _shelf()
        _drag_range(1, {"indices": [4, 5, 6, 7], "to_box": 2, "section_end": 2})
        before = _sections(1)
        row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == 1)
        try:
            capture_server.do_put_box(1, {"sections": [d["start"] for d in row["sections_detail"]]})
            saved = True
        except Exception as caught:  # noqa: BLE001 — the refusal is the failure
            saved = f"{type(caught).__name__}: {caught}"
        checks.equal(saved, True, "an unchanged save over an empty section is taken")
        checks.equal(
            _sections(1), before,
            "and the empty section stays, name and all: its divider is still in the box",
        )


def _layout(inv, box):
    """The box as the store draws it: on-hand cids per section, in walk order."""
    secs = inv.layout_of(box) or [dict(slots=[])]
    return [
        [inv.cards[master.position_key(box, i)].cid for i in sec["slots"]
         if inv.cards[master.position_key(box, i)].state not in master.TERMINAL_STATES]
        for sec in secs
    ]


def _labels(inv, box):
    _, view = join.box_view(inv, box)
    out = dict()
    for idx, _key, card in inv.records_in(box):
        if card.state not in master.TERMINAL_STATES:
            place = view.at(int(box), int(idx))
            out[card.cid] = (place.section, place.card)
    return out


def _where(inv, cid):
    card = next(c for c in inv.cards.where(cid=cid) if c.state not in master.TERMINAL_STATES)
    return int(card.index)


def _force_respace(box: int) -> bool:
    """Re-space `box` now, as twenty Map drags into one gap would. True when that changed
    the box's layout token, so an aim read before it must be refused."""
    with Store().write() as snapshot:
        before = snapshot.inventory.layout_token(box)
        snapshot.inventory._respace(box)
        return snapshot.inventory.layout_token(box) != before


def _fuzz_dividers(seeds, rounds, sections=False):
    """The divider proof's fuzz. A PHYSICAL MODEL of each box (sections of card names) is
    kept beside the store, every operation goes through its route, and after each one the
    store's sections and every card's section and card number must equal the model. Returns
    `(operations, failures)`. Fixed seeds, so a failure replays exactly.

    `sections=True` is the sub-box fuzz (`docs/specs/subbox-capture.md`): a capture, an S, a
    U and a move-in each aim at a random section by its divider key, and a sale and a sale
    undone join the writes. A quarter of the captures, S presses and move-ins re-space the
    box between the aim and the write (the review's first finding): each must then refuse
    with `SectionGone` when the token moved, and write nothing."""
    bad = []
    ops = 0
    for seed in seeds:
        rng = random.Random(seed)
        with isolated_home():
            phys = dict()
            for b in (1, 2, 3):
                capture_server.do_create_box(dict(box=b, name="B" + str(b)))
                phys[b] = [[]]

            state = dict(stale=False, gone=False)

            def stale(box, state=state):
                """A re-space between the aim and the write, on a quarter of the aims."""
                if state["stale"]:
                    state["gone"] = _force_respace(box)

            def capture(b, j=None, phys=phys):
                extra = aim_at(b, _divs(b)[j - 1]) if j else dict()
                if j:
                    stale(b)
                _, row = capture_server.do_capture(capture_payload(b, **extra))
                inv = Store().read().inventory
                phys[b][j - 1 if j else -1].append(
                    inv.cards[master.position_key(b, row["index"])].cid
                )

            for b in (1, 2, 3):
                for _ in range(4):
                    capture(b)
                capture_server.do_open_section(b, dict())
                phys[b].append([])
                capture(b)

            def cards(b, phys=phys):
                return [c for sec in phys[b] for c in sec]

            def drop(b, cid, phys=phys):
                for sec in phys[b]:
                    if cid in sec:
                        sec.remove(cid)

            kinds = ("capture", "S", "undo_S", "move", "range", "sections", "remove",
                     "capture_undo")
            if sections:
                kinds += ("capture", "S", "move_into", "sell", "sell_undo")
            for _ in range(rounds):
                kind = rng.choice(kinds)
                b = rng.choice((1, 2, 3))
                dst = rng.choice((1, 2, 3))
                inv = Store().read().inventory
                saved = [[list(sec) for sec in phys[x]] for x in (1, 2, 3)]
                # DRAWN ONLY IN THE SUB-BOX FUZZ, so the divider proof's seeds replay as before.
                j = rng.randrange(len(phys[b])) + 1 if sections else None
                state["stale"] = sections and rng.random() < 0.25
                state["gone"] = False
                empty_ok = not phys[b][-1]
                try:
                    if kind == "capture" and sections:
                        capture(b, j)
                    elif kind == "capture":
                        capture(b)
                    elif kind == "S" and sections:
                        # S AFTER A PICKED SECTION: the new one goes right after it (Q1).
                        empty_ok = not phys[b][j - 1]
                        aim = after_at(b, _divs(b)[j - 1])
                        stale(b)
                        capture_server.do_open_section(b, aim)
                        phys[b].insert(j, [])
                    elif kind == "undo_S" and sections:
                        if phys[b][j - 1] or j < 2:
                            continue
                        capture_server.do_close_section(b, _divs(b)[j - 1])
                        phys[b].pop(j - 1)
                    elif kind == "move_into" and b != dst and cards(b):
                        cid = rng.choice(cards(b))
                        k = rng.randrange(len(phys[dst])) + 1
                        aim = aim_at(dst, _divs(dst)[k - 1])
                        stale(dst)
                        at = _where(Store().read().inventory, cid)
                        capture_server.do_move_cards(b, dict(to_box=dst, indices=[at], **aim))
                        drop(b, cid)
                        phys[dst][k - 1].append(cid)
                    elif kind in ("sell", "sell_undo") and cards(b):
                        cid = rng.choice(cards(b))
                        at = _where(inv, cid)
                        capture_server.do_mark_sold(b, at, dict())
                        if kind == "sell_undo":
                            capture_server.do_mark_sold(b, at, dict(undo=True))
                        else:
                            drop(b, cid)
                    elif kind == "S":
                        capture_server.do_open_section(b, dict())
                        phys[b].append([])
                    elif kind == "undo_S":
                        if phys[b][-1] or len(phys[b]) < 2:
                            continue
                        # THE CAPTURE SCREEN'S U AFTER S (UN-15), through the route it calls,
                        # aimed at the empty last divider by its key.
                        last = Store().read().inventory.box(b).sections[-1]
                        capture_server.do_close_section(b, str(last))
                        phys[b].pop()
                    elif kind == "move" and b != dst and cards(b):
                        cid = rng.choice(cards(b))
                        capture_server.do_move_cards(b, dict(to_box=dst, **back_of(dst), indices=[_where(inv, cid)]))
                        drop(b, cid)
                        phys[dst][-1].append(cid)
                    elif kind == "range" and cards(b):
                        cid = rng.choice(cards(b))
                        rest = [c for c in cards(dst) if c != cid]
                        if rest:
                            target = rng.choice(rest)
                            _drag_range(b, dict(
                                indices=[_where(inv, cid)], to_box=dst,
                                before_card=_where(inv, target)))
                            drop(b, cid)
                            sec = next(x for x in phys[dst] if target in x)
                            sec.insert(sec.index(target), cid)
                        else:
                            j = rng.randrange(len(phys[dst])) + 1
                            _drag_range(b, dict(
                                indices=[_where(inv, cid)], to_box=dst, section_end=j))
                            drop(b, cid)
                            phys[dst][j - 1].append(cid)
                    elif kind == "sections" and cards(b) and b != dst:
                        first = rng.randrange(len(phys[b])) + 1
                        before = rng.randrange(len(phys[dst])) + 1
                        _drag_sections(b, dict(
                            first=first, last=first, to_box=dst, before=before))
                        moving = phys[b].pop(first - 1)
                        phys[b] = phys[b] or [[]]
                        phys[dst].insert(before - 1, moving)
                    elif kind == "remove" and cards(b):
                        cid = rng.choice(cards(b))
                        at = _where(inv, cid)
                        aim = inv.cards[master.position_key(b, at)].capture_id
                        capture_server.do_remove_card(b, at, dict(capture_id=aim))
                        drop(b, cid)
                    elif kind == "capture_undo":
                        newest = inv.next_index(b) - 1
                        card = inv.cards.get(master.position_key(b, newest))
                        if card is None or card.cid not in cards(b):
                            continue
                        capture_server.do_delete_card(b, newest)
                        drop(b, card.cid)
                    else:
                        continue
                except capture_server.BadRequest:
                    # A route's own refusal (a card already built on, a departed card in
                    # the way) is a legal answer. The model goes back to where it was.
                    for x, secs in zip((1, 2, 3), saved):
                        phys[x] = secs
                except Exception as caught:  # noqa: BLE001 — a raw store error is the failure
                    # A STORE ERROR ON A WELL-AIMED WRITE IS A FAILURE, and S over a
                    # section that holds a card is one too. A dropped front re-anchor
                    # shows only as a refused section move, so this is what sees it.
                    for x, secs in zip((1, 2, 3), saved):
                        phys[x] = secs
                    legal = (isinstance(caught, master.SectionEmpty) and empty_ok) or (
                        isinstance(caught, master.SectionGone) and state["gone"]
                    )
                    if not legal:
                        bad.append((seed, ops, kind + " raised " + type(caught).__name__,
                                    b, [len(sec) for sec in phys[b]], str(caught)[:60]))
                ops += 1
                after = Store().read().inventory
                for x in (1, 2, 3):
                    want = phys[x]
                    want_labels = dict(
                        (cid, (n_sec, n)) for n_sec, sec in enumerate(want, 1)
                        for n, cid in enumerate(sec, 1)
                    )
                    if _layout(after, x) != want or _labels(after, x) != want_labels:
                        bad.append((seed, ops, kind, x, [len(sec) for sec in want],
                                    [len(sec) for sec in _layout(after, x)]))
                        phys[x] = _layout(after, x)
    return ops, bad


def check_divider_anchor(checks: Checks) -> None:
    """The divider proof (D264, D294, D260, D58, D10): no write moves a divider off the cards
    it separates. Three named cases, one per defect the proof found, then the fuzz.

    F1: a divider left above the next card's key (`Inventory.next_key`) took the next
    capture or move-in into the section in front of it. The owner's ruling, 2026-09-25:
    "Into the empty section (Recommended)".
    F2: the capture screen's divider undo sent stored keys where `PUT /boxes/<box>` reads
    card counts, so other dividers moved. It calls `DELETE /boxes/<box>/sections` now.
    F3: the move undo's divider guard compared an order key with a stored index.
    Each case, and the fuzz, was red before the fix."""
    checks.note("")
    checks.note("BOX MAP — dividers stay with their cards (the divider proof)")

    def cap(box):
        capture_server.do_capture(capture_payload(box))

    for how in ("remove", "capture undo"):
        with isolated_home():
            capture_server.do_create_box(dict(box=1, name="A"))
            for _ in range(3):
                cap(1)
            capture_server.do_open_section(1, dict())
            if how == "remove":
                aim = Store().read().inventory.cards["1/3"].capture_id
                capture_server.do_remove_card(1, 3, dict(capture_id=aim))
            else:
                capture_server.do_delete_card(1, 3)
            cap(1)
            checks.equal(
                [n for _, n in _sections(1)], [2, 1],
                f"F1: 3 captures, S, {how} of card 3, 1 capture: the new card goes INTO the "
                "empty section, behind its divider",
            )

    with isolated_home():
        capture_server.do_create_box(dict(box=1, name="A"))
        for _ in range(3):
            cap(1)
        capture_server.do_open_section(1, dict())
        for _ in range(3):
            cap(1)
        capture_server.do_mark_sold(1, 1, dict())
        stored = list(Store().read().inventory.box(1).sections)
        made = capture_server.do_open_section(1, dict())["sections"][-1]
        capture_server.do_close_section(1, str(made))
        checks.equal(
            list(Store().read().inventory.box(1).sections), stored,
            "F2: 3 captures, S, 3 captures, sell card 1, S, U: the undo takes out only its "
            "own divider, and moves no other",
        )
        made = capture_server.do_open_section(1, dict())["sections"][-1]
        cap(1)
        refusal(
            checks, lambda: capture_server.do_close_section(1, str(made)), "divider_built_on",
            "and once a card stands behind the divider S made, the undo refuses",
        )

    with isolated_home():
        # THE STALE U (the review's first finding): S, then a dividers-editor save that
        # adds a divider behind S's, then U. The undo names S's divider, which is no longer
        # the last one, so it refuses and the editor's divider stays.
        capture_server.do_create_box(dict(box=1, name="A"))
        for _ in range(3):
            cap(1)
        made = capture_server.do_open_section(1, dict())["sections"][-1]
        capture_server.do_put_box(1, dict(sections=[1, 4, 9]))
        typed = list(Store().read().inventory.box(1).sections)
        refusal(
            checks, lambda: capture_server.do_close_section(1, str(made)), "divider_built_on",
            "a stale U after an editor save refuses: S's divider is no longer the last one",
        )
        checks.equal(
            list(Store().read().inventory.box(1).sections), typed,
            "and the editor's dividers all stay",
        )

    with isolated_home():
        # "PRESS S, THEN U. THE SECTIONS ARE AS BEFORE" (UN-15), both ways: an undeclared box
        # goes back to `[]`, and a box that stored `[1]` keeps `[1]`.
        capture_server.do_create_box(dict(box=2, name="B"))
        cap(2)
        made = capture_server.do_open_section(2, dict())["sections"][-1]
        capture_server.do_close_section(2, str(made))
        checks.equal(
            list(Store().read().inventory.box(2).sections), [],
            "U after S on an undeclared box leaves it undeclared, `[]`, as before",
        )
        capture_server.do_create_box(dict(box=1, name="A"))
        for _ in range(2):
            cap(1)
        capture_server.do_put_box(1, dict(sections=[1]))
        made = capture_server.do_open_section(1, dict())["sections"][-1]
        capture_server.do_close_section(1, str(made))
        checks.equal(
            list(Store().read().inventory.box(1).sections), [1],
            "and U after S on a box that stored `[1]` keeps `[1]`",
        )
        made = capture_server.do_open_section(1, dict())["sections"][-1]
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            for path, want, label in (
                ("/boxes/1/sections", (400, "div_required"), "no `div` is a 400"),
                ("/boxes/1/sections?div=x", (400, "div_required"), "a word for `div` is a 400"),
                ("/boxes/9/sections?div=3", (404, "box_not_found"), "an unknown box is a 404"),
                ("/boxes/1/sections?div=1", (409, "divider_built_on"),
                 "a divider that is not the last one is a 409"),
            ):
                status, body, _ = http_request(port, "DELETE", path)
                checks.equal((status, error_code(body)), want, "DELETE " + label)
            status, body, _ = http_request(port, "DELETE", f"/boxes/1/sections?div={made}")
            checks.equal(
                (status, json.loads(body).get("sections")), (200, [1]),
                "and S's own divider comes out over the wire, with the box row as the answer",
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)

    with isolated_home():
        for b in (1, 2):
            capture_server.do_create_box(dict(box=b, name="B" + str(b)))
        for _ in range(5):
            cap(1)
        cap(2)
        _drag_range(1, dict(indices=[5], to_box=1, before_card=1))
        capture_server.do_move_cards(2, dict(to_box=1, **back_of(1), indices=[1]))
        capture_server.do_open_section(1, dict())

        def unmove():
            with Store().write() as snapshot:
                snapshot.inventory.unmove_card("2/1")

        # THE STORE'S OWN GUARD, called directly: the route reads history first and
        # refuses on its own, so only this call can see the store's comparison.
        checks.raises(
            master.CardDeparted, unmove,
            "F3: the store refuses a move undo after S, in a box whose keys are below their "
            "indices: the divider's key is compared with the card's key",
        )

    ops, bad = _fuzz_dividers(range(6), 150)
    checks.ok(
        not bad,
        "no write moves a divider off its cards, or relabels a card it did not move "
        "(" + str(ops) + " random operations over six seeds)",
        "; ".join("seed %d op %d %s box %d wanted %s got %s" % v for v in bad[:5]),
    )


def _divs(box: int) -> List[str]:
    """Each section's divider key, as `GET /boxes` sends it (`sections_detail[].div`)."""
    row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == box)
    return [d["div"] for d in row["sections_detail"]]


def aim_at(box: int, div) -> dict:
    """A capture's or a move's aim at section `div` of `box`, with the box's token as it
    stands now (`docs/specs/subbox-capture.md` 1): what a screen that just read the box
    sends."""
    return {"section": div, "layout_token": Store().read().inventory.layout_token(box)}


def after_at(box: int, div) -> dict:
    """S's aim: right after section `div` of `box`, with the box's token as it stands now."""
    return {"after": div, "layout_token": Store().read().inventory.layout_token(box)}


def _attempt(fn):
    """`(answer, None)`, or `(None, the exception)`, so a broken store fails a named check
    and never ends T7 with a traceback."""
    try:
        return fn(), None
    except Exception as caught:  # noqa: BLE001 — the caller names what it wanted
        return None, caught


def _photos(home) -> int:
    return len(list(home.rglob("*.jpg")))


def _three_by_three() -> None:
    """Box 1, three sections of three cards, built at the rig: 3 captures, S, 3, S, 3."""
    capture_server.do_create_box(dict(box=1, name="A"))
    for n in range(3):
        for _ in range(3):
            capture_server.do_capture(capture_payload(1))
        if n < 2:
            capture_server.do_open_section(1, dict())


def check_capture_into_section(checks: Checks) -> None:
    """A picked section fills like a sub-box (`docs/specs/subbox-capture.md`, the owner's
    ruling of 2026-09-26). One named case per invariant I1-I15, then the fuzz.

    Each case was red against its mutation in the spec's section 4 before it was kept."""
    checks.note("")
    checks.note("SUB-BOX CAPTURE — a picked section fills in place")

    # I1: no section, and the last section, are today's capture exactly.
    homes = []
    for aim in ("none", "last"):
        with isolated_home():
            capture_server.do_create_box(dict(box=1, name="A"))
            for n in range(5):
                extra = aim_at(1, _divs(1)[-1]) if aim == "last" and n else dict()
                capture_server.do_capture(capture_payload(1, **extra))
                if n == 2:
                    capture_server.do_open_section(1, dict())
            inv = Store().read().inventory
            homes.append((_keys(1), list(inv.sections_for(1))))
    checks.equal(
        homes[1], homes[0],
        "I1: a capture into the last section writes the same keys and dividers as a capture "
        "that names no section",
    )
    checks.ok(
        all(float(k) == float(i) for i, k in homes[0][0].items()),
        "I1: and a box nothing was placed into stays the identity: every key is its index",
        repr(homes[0][0]),
    )

    # I2, I3: 3x3, capture into section 2.
    with isolated_home():
        _three_by_three()
        before_keys = _keys(1)
        before_divs = list(Store().read().inventory.sections_for(1))
        inv = Store().read().inventory
        before_labels = _labels(inv, 1)
        answer, caught = _attempt(
            lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, _divs(1)[1])))
        )
        checks.ok(caught is None, "I2: a capture into section 2 of 3 is taken", repr(caught))
        if caught is None:
            _, body = answer
            after = _keys(1)
            new = float(after[body["index"]])
            section_two = [float(before_keys[i]) for i in (4, 5, 6)]
            checks.ok(
                max(section_two) < new < float(before_divs[2]),
                "I2: its key is above every key in section 2 and below section 3's divider",
                f"key {new}, section 2 {section_two}, divider {before_divs[2]}",
            )
            checks.equal(
                (_changed(before_keys, after), list(Store().read().inventory.sections_for(1))),
                ([], before_divs),
                "I2: no other card's key, and no divider, is written",
            )
            checks.equal([n for _, n in _sections(1)], [3, 4, 3], "I3: the counts are [3, 4, 3]")
            after_labels = _labels(Store().read().inventory, 1)
            checks.equal(
                {cid: at for cid, at in after_labels.items() if cid in before_labels},
                before_labels,
                "I3: no card in sections 1 or 3, and no earlier card in section 2, changes "
                "its section or card number",
            )
            checks.equal(
                (body["section"], body["card"], body["section_div"]), (2, 4, _divs(1)[1]),
                "I3: the new card is section 2, card 4, and the answer names section 2's divider",
            )

    # I4 and I8 and I9: S after a middle section, capture into it, U.
    with isolated_home():
        _three_by_three()
        before_keys = _keys(1)
        before_divs = list(Store().read().inventory.sections_for(1))
        before_labels = _labels(Store().read().inventory, 1)
        _, caught = _attempt(lambda: capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[1]))))
        stored = list(Store().read().inventory.sections_for(1))
        added = [d for d in stored if d not in before_divs]
        checks.ok(
            caught is None and len(stored) == 4 and len(added) == 1
            and float(before_keys[6]) < float(added[0]) < float(before_divs[2]),
            "I8: S after section 2 puts exactly one divider between section 2's last card "
            "and section 3's divider",
            f"{caught!r} {before_divs} -> {stored}",
        )
        checks.equal(_changed(before_keys, _keys(1)), [], "I8: and no card key changes")
        moved_up = {
            cid: (sec + 1 if sec >= 3 else sec, n) for cid, (sec, n) in before_labels.items()
        }
        checks.equal(
            _labels(Store().read().inventory, 1), moved_up,
            "I8: the old section 3 is section 4 now, and every card number stays",
        )
        new_div = _divs(1)[2] if len(_divs(1)) == 4 else "none"
        answer, caught = _attempt(
            lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, new_div)))
        )
        if caught is None:
            _, body = answer
            checks.equal(
                (float(_keys(1)[body["index"]]), body["section"], body["card"]),
                (float(new_div), 3, 1),
                "I4: the first card into an empty middle section takes the divider's own key",
            )
            capture_server.do_delete_card(1, body["index"])
        else:
            checks.ok(False, "I4: the first card into an empty middle section is taken", repr(caught))
        _, caught = _attempt(lambda: capture_server.do_close_section(1, new_div))
        checks.equal(
            (caught, list(Store().read().inventory.sections_for(1)), _keys(1)),
            (None, before_divs, before_keys),
            "I9: U with that divider's key takes out that divider only, and moves no other",
        )
        # THE REFUSAL SHAPE IS `ux/divider-fix`'s: 409 `divider_built_on` for each.
        refusal(
            checks, lambda: capture_server.do_close_section(1, _divs(1)[1]), "divider_built_on",
            "I9: U refuses a middle divider whose section holds a card",
        )
        refusal(
            checks, lambda: capture_server.do_close_section(1, _divs(1)[0]), "divider_built_on",
            "I9: U refuses the first divider",
        )
        refusal(
            checks, lambda: capture_server.do_close_section(1, "41"), "divider_built_on",
            "I9: U refuses a divider key the box does not have",
        )
        checks.equal(
            list(Store().read().inventory.sections_for(1)), before_divs,
            "I9: and none of the three refusals took a divider out",
        )
        # THE STALE U, mid-box: S after section 2, then an editor save, then U. The newest
        # layout change is the save, not the S, so the undo is not S's any more.
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[1])))
        stale = _divs(1)[2]
        row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == 1)
        capture_server.do_put_box(1, {"sections": [d["start"] for d in row["sections_detail"]]})
        saved = list(Store().read().inventory.sections_for(1))
        refusal(
            checks, lambda: capture_server.do_close_section(1, stale), "divider_built_on",
            "I9: U after a mid-box S and then an editor save refuses",
        )
        checks.equal(
            list(Store().read().inventory.sections_for(1)), saved,
            "I9: and the saved dividers all stay",
        )
        checks.raises(
            master.SectionGone, lambda: capture_server.do_open_section(1, dict(**after_at(1, "41"))),
            "I8: S refuses an `after` the box does not have",
        )

    # I5: a planned divider keeps its card number.
    with isolated_home():
        capture_server.do_create_box(dict(box=1, name="A"))
        for _ in range(5):
            capture_server.do_capture(capture_payload(1))
        with Store().write() as snapshot:
            snapshot.inventory.set_sections(1, [1, 51])
        start = lambda: next(  # noqa: E731
            b for b in capture_server.do_boxes()["boxes"] if b["box"] == 1
        )["sections_detail"][1]["start"]
        before = start()
        _attempt(lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, _divs(1)[0]))))
        checks.equal(
            (before, start(), _keys(1).get(6)), (51, 51, 6),
            "I5: with dividers [1, 51] on 5 cards, a capture into section 1 takes key 6, and "
            "section 2 still starts at card 51",
        )

    # I6: a stale aim writes nothing.
    with isolated_home() as home:
        _three_by_three()
        inv = Store().read().inventory
        before = (inv.next_index(1), _keys(1), list(inv.sections_for(1)), _photos(home))
        checks.raises(
            master.SectionGone,
            lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, "41"))),
            "I6: a capture aimed at a divider the box does not have is refused",
        )
        inv = Store().read().inventory
        checks.equal(
            (inv.next_index(1), _keys(1), list(inv.sections_for(1)), _photos(home)), before,
            "I6: and it uses no index, writes no key or divider, and stores no photograph",
        )
        checks.raises(
            master.SectionGone,
            lambda: capture_server.do_capture(capture_payload(7, **aim_at(7, "1.5"))),
            "I6: a capture into a box that does not exist, aimed at a section, is refused",
        )
        checks.equal(
            Store().read().inventory.box(7), None, "I6: and that box is not registered",
        )
        checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_capture(capture_payload(1, section=2)),
            "I6: a section that is not a string is refused before anything is read",
        )

    # I7: a forced narrow gap re-spaces once, and keeps order and membership.
    with isolated_home():
        _three_by_three()
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[0])))
        narrow = _divs(1)[1]
        _, body = capture_server.do_capture(capture_payload(1, **aim_at(1, narrow)))
        with Store().write() as snapshot:
            snapshot.inventory.cards[master.position_key(1, body["index"])].order = 4 - 5e-4
        walk = _layout(Store().read().inventory, 1)
        answer, caught = _attempt(
            lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, narrow)))
        )
        if caught is None:
            _, body = answer
            inv = Store().read().inventory
            walk[1].append(inv.cards[master.position_key(1, body["index"])].cid)
            checks.equal(
                (_layout(inv, 1), body["section_div"], body["section_div"] != narrow),
                (walk, _divs(1)[1], True),
                "I7: a gap too narrow for the next key re-spaces the box once, every card keeps its "
                "place and section, and the answer names section 2's new divider key",
            )
        else:
            checks.ok(False, "I7: a capture into a too-narrow gap is taken", repr(caught))

    # I10: the capture undo of a mid-box card.
    with isolated_home():
        _three_by_three()
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[1])))
        empty = _divs(1)[2]
        _, body = capture_server.do_capture(capture_payload(1, **aim_at(1, empty)))
        keys = {i: k for i, k in _keys(1).items() if i != body["index"]}
        stored = list(Store().read().inventory.sections_for(1))
        _, caught = _attempt(lambda: capture_server.do_delete_card(1, body["index"]))
        checks.equal(
            (caught, _keys(1), list(Store().read().inventory.sections_for(1))),
            (None, keys, stored),
            "I10: the capture undo deletes the newest card although it is mid-box, and "
            "writes no key and no divider",
        )
        _, again = capture_server.do_capture(capture_payload(1, **aim_at(1, empty)))
        checks.equal(
            float(_keys(1)[again["index"]]), float(empty),
            "I10: the next capture into the emptied section takes the divider's key again",
        )

    # I12 (Lane C's half): a Move-to-box names its section.
    with isolated_home():
        _three_by_three()
        capture_server.do_create_box(dict(box=2, name="B"))
        for _ in range(3):
            capture_server.do_capture(capture_payload(2))
        inv = Store().read().inventory
        mover = inv.cards["2/1"]
        answer, caught = _attempt(lambda: capture_server.do_move_card(
            2, 1, dict(capture_id=mover.capture_id, to_box=1, **aim_at(1, _divs(1)[1]))))
        checks.equal(
            (caught, _labels(Store().read().inventory, 1).get(mover.cid)), (None, (2, 4)),
            "I12: a card moved into section 2 of 3 goes to the tail of section 2",
        )
        checks.equal([n for _, n in _sections(1)], [3, 4, 3], "I12: and sections 1 and 3 keep 3")
        # I13: the undo of a move into a middle section. The divider behind it was there.
        _, caught = _attempt(lambda: capture_server.do_move_card(2, 1, dict(undo=True)))
        checks.ok(
            caught is None and [n for _, n in _sections(1)] == [3, 3, 3],
            "I13: a move into section 2 of 3 can be undone: section 3's divider was already "
            "behind it",
            repr(caught),
        )
        cids = [Store().read().inventory.cards[f"2/{i}"].cid for i in (2, 3)]
        _, caught = _attempt(lambda: capture_server.do_move_cards(
            2, dict(to_box=1, indices=[2, 3], **aim_at(1, _divs(1)[0]))))
        labels = _labels(Store().read().inventory, 1)
        checks.equal(
            (caught, [labels.get(c) for c in cids]), (None, [(1, 4), (1, 5)]),
            "I12: ticked cards moved into section 1 go to its tail in the order sent",
        )
        checks.raises(
            master.SectionGone,
            lambda: capture_server.do_move_cards(1, dict(to_box=3, indices=[1], **aim_at(3, "41"))),
            "I12: a move aimed at a section the box does not have is refused",
        )
        checks.equal(
            Store().read().inventory.cards["1/1"].state, master.CAPTURED,
            "I12: and the card did not move",
        )
        # THE OWNER'S RULING: "i need to specify where it goes there no auto default".
        aim = Store().read().inventory.cards["1/1"].capture_id
        refusal(
            checks,
            lambda: capture_server.do_move_card(1, 1, dict(capture_id=aim, to_box=3)),
            "section_required",
            "I12: a Move to box that names no section is refused: a move has no default place",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_cards(1, dict(to_box=3, indices=[1])),
            "section_required",
            "I12: and so is a move of ticked cards that names no section",
        )
        checks.equal(
            Store().read().inventory.cards["1/1"].state, master.CAPTURED,
            "I12: and neither refusal moved the card",
        )

    # I15: the divider editor after a mid-box S.
    with isolated_home():
        _three_by_three()
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[0])))
        before = list(Store().read().inventory.sections_for(1))
        row = next(b for b in capture_server.do_boxes()["boxes"] if b["box"] == 1)
        _, caught = _attempt(lambda: capture_server.do_put_box(
            1, {"sections": [d["start"] for d in row["sections_detail"]]}))
        checks.equal(
            (caught, list(Store().read().inventory.sections_for(1))), (None, before),
            "I15: after a mid-box S, saving the divider editor unchanged keeps every divider",
        )

    # Plan section 4: a SKU's copies are listed in box-walk order, by key.
    with isolated_home():
        _three_by_three()
        _, body = capture_server.do_capture(capture_payload(1, **aim_at(1, _divs(1)[0])))
        with Store().write() as snapshot:
            for key in ("1/8", master.position_key(1, body["index"])):
                snapshot.inventory.cards[key].sku = "900001"
        walk = [c.index for c in Store().read().inventory.positions_for_sku("900001")]
        checks.equal(
            walk, [body["index"], 8],
            "a SKU's copies are listed in the order they stand, so a card captured mid-box "
            "is not listed as if at the back",
        )

    # THE REVIEW'S FIRST FINDING: a re-space re-uses a divider key. Dividers [1, 7, 10] over
    # sections of three cards re-space to [1, 4, 7], so "7" names section 3 afterwards. An aim
    # read before the re-space carries the old token, and it is refused.
    with isolated_home() as home:
        capture_server.do_create_box(dict(box=1, name="A"))
        with Store().write() as snapshot:
            for index, key in enumerate((1, 2, 3, 7, 8, 9, 10, 11, 12), 1):
                snapshot.inventory.record_capture(master.Card(
                    box=1, index=index, cid=fake_cid(f"reuse-{index}"), order=float(key)))
            snapshot.inventory.set_sections(1, [1, 7, 10])
        stale_capture = aim_at(1, "7")
        stale_s = after_at(1, "7")
        stale_move = aim_at(1, "7")
        capture_server.do_create_box(dict(box=2, name="B"))
        capture_server.do_capture(capture_payload(2))
        _force_respace(1)
        checks.equal(_divs(1), ["1", "4", "7"], "the re-space re-uses key 7 for section 3")
        inv = Store().read().inventory
        before = (inv.next_index(1), _keys(1), list(inv.sections_for(1)), _photos(home))
        checks.raises(
            master.SectionGone,
            lambda: capture_server.do_capture(capture_payload(1, **stale_capture)),
            "a capture aimed at section 2 before the re-space is refused, not filed in section 3",
        )
        checks.raises(
            master.SectionGone, lambda: capture_server.do_open_section(1, stale_s),
            "and so is an S after section 2 aimed before the re-space",
        )
        aim2 = Store().read().inventory.cards["2/1"].capture_id
        checks.raises(
            master.SectionGone,
            lambda: capture_server.do_move_card(
                2, 1, dict(capture_id=aim2, to_box=1, **stale_move)),
            "and so is a Move to box aimed before the re-space",
        )
        inv = Store().read().inventory
        checks.equal(
            (inv.next_index(1), _keys(1), list(inv.sections_for(1)), _photos(home),
             inv.cards["2/1"].state),
            before + (master.CAPTURED,),
            "and none of the three wrote a key, a divider, a photograph or a move",
        )
        answer, caught = _attempt(
            lambda: capture_server.do_capture(capture_payload(1, **aim_at(1, _divs(1)[1])))
        )
        checks.ok(
            caught is None and answer[1]["section"] == 2 and answer[1]["section_div"] == "4"
            and answer[1]["layout_token"] == Store().read().inventory.layout_token(1),
            "an aim read after the re-space files the card in section 2, and the answer "
            "carries the box's token",
            repr(caught or answer[1].get("section")),
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(1, section=_divs(1)[1])),
            "layout_token_required",
            "a section sent without a token is refused",
        )

    # THE RE-REVIEW'S FINDING, ROUND 2: the Map names its gap by a section NUMBER. The Map reads
    # box 1, then an S after section 2 on the rig renumbers the old section 3 to 4. A drag to
    # "the end of section 3" read before that S is refused, never dropped into the new section.
    with isolated_home():
        _three_by_three()
        capture_server.do_create_box(dict(box=2, name="B"))
        capture_server.do_capture(capture_payload(2))
        drawn = Store().read().inventory.layout_token(1)
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[1])))
        counts = [n for _, n in _sections(1)]
        refusal(
            checks,
            lambda: capture_server.do_move_range(
                2, {"indices": [1], "to_box": 1, "section_end": 3, "layout_token": drawn}),
            "section_gone",
            "a Map drag read before a mid-box S is refused, not dropped into the new section",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_sections(
                2, {"first": 1, "to_box": 1, "before": 3, "layout_token": drawn}),
            "section_gone",
            "and so is a Map section move read before it",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_range(2, {"indices": [1], "to_box": 1, "section_end": 3}),
            "layout_token_required",
            "a Map drag into a box with sections that sends no token is refused",
        )
        checks.equal(
            ([n for _, n in _sections(1)], Store().read().inventory.cards["2/1"].state),
            (counts, master.CAPTURED),
            "and none of the three moved a card",
        )

    # U AFTER A RE-SPACE: U's own proof is the resectioned line, and a re-space writes none.
    with isolated_home():
        _three_by_three()
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[0])))
        made = _divs(1)[1]
        changed = _force_respace(1)
        refusal(
            checks, lambda: capture_server.do_close_section(1, made), "divider_built_on",
            "U after S and then a re-space refuses: the layout is not the one S wrote",
        )
        checks.ok(changed, "and the re-space in that case did move the keys")

    # THE REVIEW'S FIFTH FINDING: an unreadable log is a named refusal, never a 500.
    with isolated_home():
        _three_by_three()
        s_row = capture_server.do_open_section(1, dict())
        broken = capture_server.Store.named_events

        def unreadable(self, event):
            raise sqlite3.DatabaseError("database disk image is malformed")

        capture_server.Store.named_events = unreadable
        try:
            refusal(
                checks, lambda: capture_server.do_close_section(1, str(s_row["sections"][-1])),
                "history_unreadable", "U whose log read fails is a named refusal",
            )
        finally:
            capture_server.Store.named_events = broken
        checks.equal(
            list(Store().read().inventory.sections_for(1)), list(s_row["sections"]),
            "and the divider stays",
        )

    # THE REVIEW'S THIRD FINDING: a box that ended with an empty section before the move.
    with isolated_home():
        for b in (1, 2):
            capture_server.do_create_box(dict(box=b, name="B" + str(b)))
        for _ in range(3):
            capture_server.do_capture(capture_payload(2))
        capture_server.do_open_section(2, dict())
        capture_server.do_capture(capture_payload(1))
        mover = Store().read().inventory.cards["1/1"]
        capture_server.do_move_card(
            1, 1, dict(capture_id=mover.capture_id, to_box=2, **aim_at(2, _divs(2)[0])))
        _, caught = _attempt(lambda: capture_server.do_move_card(1, 1, dict(undo=True)))
        checks.ok(
            caught is None,
            "a move into the section before an empty last section can be undone: that "
            "divider was there before the move",
            repr(caught),
        )

    with isolated_home():
        _three_by_three()
        capture_server.do_create_box(dict(box=2, name="B"))
        capture_server.do_capture(capture_payload(2))
        mover = Store().read().inventory.cards["2/1"]
        capture_server.do_move_card(
            2, 1, dict(capture_id=mover.capture_id, to_box=1, **aim_at(1, _divs(1)[1])))
        capture_server.do_open_section(1, dict(**after_at(1, _divs(1)[1])))
        refusal(
            checks, lambda: capture_server.do_move_card(2, 1, dict(undo=True)),
            "move_built_on",
            "a move whose card got a new divider behind it after the move cannot be undone",
        )

    ops, bad = _fuzz_dividers(range(6, 12), 150, sections=True)
    checks.ok(
        not bad,
        "I10-I14: captures and S into random sections, mixed with every other write, "
        "move no divider off its cards (" + str(ops) + " random operations over six seeds)",
        "; ".join("seed %d op %d %s box %d wanted %s got %s" % v for v in bad[:5]),
    )


def check_layout_batch(checks: Checks) -> None:
    """The Map's Confirm (D264, the owner's edit-mode ruling, 2026-09-26): a draft of many
    section moves applies as ONE store transaction, or none of it does (D88).

    Red before `do_move_sections_batch` existed: the route answered nothing. Proved red
    again on a `.bak` mutation of the route (see `docs/debts/` or the lane's own report):
    with the second move's failure moved to AFTER a commit-per-move loop instead of one
    transaction, this case's "nothing moved" assertion fails, because the first move lands
    on disk before the second one is even tried.
    """
    checks.note("")
    checks.note("BOX MAP — the Confirm batch, all-or-nothing, one undo (D264)")

    with isolated_home():
        _shelf()
        before = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        digests = _digests([1, 2])
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [
                    {"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2},
                    {"box": 1, "first": 1, "last": 1, "to_box": 9999},
                ],
            }),
            "box_not_found",
            "a batch whose second move names a box that does not exist refuses",
        )
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)},
            before,
            "ALL OR NOTHING: the first move's own effect did not survive the second one's failure",
        )

        body = capture_server.do_move_sections_batch({
            "digests": digests,
            "moves": [
                {"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2},
                {"box": 1, "first": 1, "last": 1, "to_box": 1},
            ],
        })
        checks.equal(
            _sections(2), [("Singles", 2), ("Uncommons", 4), ("Promos", 2)],
            "the first queued move landed",
        )
        checks.equal(
            _sections(1), [("Rares", 2), ("Commons", 3)],
            "and the second, reordering what the first left behind, landed too",
        )
        checks.equal(
            len(Store().named_events("sections_moved")), 1,
            "two section moves queued in the draft, and ONE event for the whole batch, never one per move",
        )

        capture_server.do_undo_section_move({"move": body["move"]})
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)},
            before,
            "ONE UNDO PUTS BACK THE WHOLE LAYOUT: both boxes, exactly as the draft found them",
        )

    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        _drag_sections(1, {"first": 1, "last": 1, "to_box": 2})
        walk_before = (_walk(1), _walk(2))
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 1, "before": 1}],
            }),
            "draft_stale",
            "a draft opened before a box changed is refused whole, never applied on stale ground",
        )
        checks.equal(
            (_walk(1), _walk(2)), walk_before,
            "and nothing from the stale draft moved",
        )

    with isolated_home():
        _shelf()
        body = capture_server.do_move_sections_batch({
            "digests": _digests([1, 2]),
            "moves": [{"box": 1, "first": 2, "last": 3, "new_box": True}],
        })
        created = body["created"]
        checks.equal(
            _sections(created), [("Uncommons", 4), ("Rares", 2)],
            "a split reached through the batch route lands exactly as the single-move route's does",
        )
        capture_server.do_undo_section_move({"move": body["move"]})
        checks.ok(
            Store().read().inventory.box(created) is None,
            "and undoing a batch that split a box removes the box it made",
        )

    # THE STRICT REVIEW'S FAILURE (2026-09-27): `layout_token` hashes the dividers alone, so
    # a card arriving in — or leaving — a section changes no token, and the Confirm gate read
    # only tokens. The fix is `_layout_digest`, over the box's cards too (identity, order,
    # section, state), sent as `digests`.
    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        # A card captured into the very section a queued move targets, after the draft was
        # read: the layout_token of box 1 is UNCHANGED (a capture adds no divider), but the
        # box's cards did change, and the digest must see it.
        before_token = Store().read().inventory.layout_token(1)
        capture_server.do_capture(capture_payload(1, **aim_at(1, _divs(1)[1])))
        checks.equal(
            Store().read().inventory.layout_token(1), before_token,
            "setup check: a capture into an existing section leaves the layout_token alone",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
            }),
            "draft_stale",
            "a card CAPTURED into a section the draft targets, after the draft was opened, "
            "refuses the whole batch — the token alone would have missed it",
        )
        checks.equal(
            _walk(1), [f"o{i}" for i in range(1, 8)] + [None, "o8", "o9"],
            "and nothing moved",
        )

    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        # A card sold out of the section a queued move targets, after the draft was read: the
        # layout_token of box 1 is again unchanged, and the digest must still catch it.
        capture_server.do_mark_sold(1, 4, {})
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
            }),
            "draft_stale",
            "a card SOLD out of a section the draft targets, after the draft was opened, "
            "refuses the whole batch the same way",
        )
        checks.ok(
            Store().read().inventory.cards["1/4"].state == master.SOLD,
            "and the sale itself was not touched by the refused batch",
        )

    # THE RE-REVIEW'S FINDING (2026-09-28), the owner's ruling of the same day: "Only layout
    # changes". `_box_digest` hashed every field, so a note or a photo edit refused a draft
    # over a fact no layout move reads. `_layout_digest` must NOT catch either.
    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        with Store().write() as snapshot:
            snapshot.inventory.cards["1/4"].note = "Corner ding, still gradeable"
        body = capture_server.do_move_sections_batch({
            "digests": digests,
            "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
        })
        checks.ok(
            body["move"] is not None,
            "a NOTE edit between the draft and Confirm does not refuse: it is not a layout fact",
        )

    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        with Store().write() as snapshot:
            snapshot.inventory.cards["1/4"].photo = "a-different-photo.jpg"
        body = capture_server.do_move_sections_batch({
            "digests": digests,
            "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
        })
        checks.ok(
            body["move"] is not None,
            "a PHOTO field edit between the draft and Confirm does not refuse either",
        )

    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        capture_server.do_remove_card(1, 4, {"capture_id": None})
        error = None
        try:
            capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
            })
        except capture_server.BadRequest as caught:
            error = caught
        checks.ok(
            error is not None and error.code == "draft_stale" and "cards changed" in str(error),
            "a card REMOVED between the draft and Confirm still refuses, and the message "
            "names the cards, never a layout change that did not happen",
            str(error),
        )

    with isolated_home():
        _shelf()
        digests = _digests([1, 2])
        capture_server.do_remove_card(2, 1, {"capture_id": None})
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [{"box": 1, "first": 2, "last": 2, "to_box": 2, "before": 2}],
            }),
            "draft_stale",
            "a card removed from a DIFFERENT box the draft also saw still refuses the whole batch",
        )

    # THE OWNER'S RULING (2026-09-27): card ranges rejoin edit mode, drafted and confirmed
    # the same way sections are — a mixed batch, all or nothing, one undo.
    with isolated_home():
        _shelf()
        before = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        digests = _digests([1, 2])
        body = capture_server.do_move_sections_batch({
            "digests": digests,
            "moves": [
                {"kind": "range", "box": 1, "indices": [5, 6], "to_box": 2, "before_card": 2},
                {"kind": "section", "box": 1, "first": 3, "last": 3, "to_box": 1, "before": 1},
            ],
        })
        checks.equal(
            _walk(2), ["m1", "o5", "o6", "m2", "m3", "m4"],
            "the queued range landed, in front of the card named",
        )
        checks.equal(
            _walk(1), ["o8", "o9", "o1", "o2", "o3", "o4", "o7"],
            "and the queued section reorder, over what the range left behind, landed too",
        )
        checks.equal(
            len(Store().named_events("sections_moved")), 1,
            "a mixed range-and-section draft is still ONE event for the whole batch",
        )
        capture_server.do_undo_section_move({"move": body["move"]})
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)},
            before,
            "one undo reverses a mixed batch exactly, range and section together",
        )

    with isolated_home():
        _shelf()
        before = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        digests = _digests([1, 2])
        refusal(
            checks,
            lambda: capture_server.do_move_sections_batch({
                "digests": digests,
                "moves": [
                    {"kind": "range", "box": 1, "indices": [5, 6], "to_box": 2, "before_card": 2},
                    {"kind": "range", "box": 1, "indices": [99], "to_box": 2, "before_card": 1},
                ],
            }),
            "range_invalid",
            "a mixed draft whose second range names a card not on hand refuses whole",
        )
        checks.equal(
            {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)},
            before,
            "ALL OR NOTHING over a range too: the first queued range's own effect did not survive",
        )


def check_move_receipt_lines(checks: Checks) -> None:
    """a section move's receipt says what the move owes (5.4).

    `receipt.owed` names how many moved cards open orders want. `receipt.next_capture` names
    the section the next capture joins, when the moved section was its box's last. Each is
    absent (None, empty) at zero. Both routes carry them: single move and Confirm batch.
    """
    from store import orders as order_store

    checks.note("")
    checks.note("BOX MAP — the receipt's owed and next-capture lines")

    def owe(sku: str, quantity: int, status: str = "Pending") -> None:
        with Store().write() as snapshot:
            snapshot.ledger.ingest([order_store.OrderRecord(
                source="TCGplayer", number=f"O-{sku}", status=status,
                placed_at="2026-08-28T10:00:00+00:00",
                lines=[order_store.OrderLine(sku=sku, quantity=quantity)],
            )])

    def sku_cards(box: int, indices: List[int], sku: str) -> None:
        with Store().write() as snapshot:
            for index in indices:
                snapshot.inventory.cards[master.position_key(box, index)].sku = sku

    with isolated_home():
        _shelf()
        # Origins' Uncommons are cards 4-7. Three carry SKU 111, and an order owes two.
        sku_cards(1, [4, 5, 6], "111")
        owe("111", 2)
        body = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2})
        checks.equal(
            body["receipt"]["owed"],
            "2 of these cards are owed to open orders. The orders stay as they are.",
            "OWED: three copies moved, two owed, so the receipt says two",
        )
        checks.equal(body["receipt"]["next_capture"], [], "a middle section moved: no next-capture line")

    with isolated_home():
        _shelf()
        sku_cards(1, [4], "111")
        owe("111", 1, status="Canceled")
        body = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2})
        checks.equal(body["receipt"]["owed"], None, "OWED ABSENT: a canceled order is not open, so no line")

    with isolated_home():
        _shelf()
        sku_cards(1, [8], "111")
        owe("111", 3)
        body = _drag_sections(1, {"first": 3, "last": 3, "to_box": 2})
        checks.equal(
            body["receipt"]["owed"],
            "1 of these cards is owed to an open order. The orders stay as they are.",
            "OWED: one copy moved, said in the singular",
        )
        checks.equal(
            body["receipt"]["next_capture"],
            ["The next card you capture in Origins joins Uncommons, Section 2. "
             "Press S first to start a new section."],
            "NEXT CAPTURE: Rares was Origins' last section, so the next capture joins Uncommons",
        )

    with isolated_home():
        _shelf()
        sku_cards(1, [1], "222")
        owe("222", 1)
        body = capture_server.do_move_sections_batch({
            "digests": _digests([1, 2]),
            "moves": [
                {"box": 1, "first": 3, "last": 3, "to_box": 2},
                {"box": 1, "first": 1, "last": 1, "to_box": 2},
            ],
        })
        checks.equal(
            body["receipt"]["owed"],
            "1 of these cards is owed to an open order. The orders stay as they are.",
            "BATCH OWED: the Confirm route carries the line too",
        )
        checks.equal(
            body["receipt"]["next_capture"],
            ["The next card you capture in Origins joins Uncommons, Section 1. "
             "Press S first to start a new section."],
            "BATCH NEXT CAPTURE: read off the box as the draft left it",
        )

    with isolated_home():
        _shelf()
        # A line stood down owes nothing, so its cards are not counted (`walkplan.demand`).
        # A second open line keeps the order itself open, so only the line's own `closed` can say no.
        sku_cards(1, [4, 5], "333")
        with Store().write() as snapshot:
            snapshot.ledger.ingest([order_store.OrderRecord(
                source="TCGplayer", number="O-333", status="Pending",
                placed_at="2026-08-28T10:00:00+00:00",
                lines=[order_store.OrderLine(sku="333", quantity=2),
                       order_store.OrderLine(sku="999", quantity=1)],
            )])
            snapshot.ledger.close_line(
                order_store.order_key("TCGplayer", "O-333"), "333", order_store.CLOSE_NOT_SHIPPING
            )
        body = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2})
        checks.equal(body["receipt"]["owed"], None, "STOOD DOWN: a closed line is not counted")

    with isolated_home():
        _shelf()
        # Three copies are owed and one is already pulled, so two are outstanding.
        sku_cards(1, [4, 5, 6], "444")
        owe("444", 3)
        with Store().write() as snapshot:
            snapshot.ledger.record_pull(order_store.order_key("TCGplayer", "O-444"), "444", ["PULLED-1"])
        body = _drag_sections(1, {"first": 2, "last": 2, "to_box": 2})
        checks.equal(
            body["receipt"]["owed"],
            "2 of these cards are owed to open orders. The orders stay as they are.",
            "PARTLY PICKED: only the outstanding copies count",
        )

    with isolated_home():
        _shelf()
        sku_cards(1, [4], "555")
        owe("555", 5)
        body = capture_server.do_move_sections_batch({
            "digests": _digests([1, 2]),
            "moves": [
                {"box": 1, "first": 2, "last": 2, "to_box": 2},
                {"box": 2, "first": 3, "last": 3, "to_box": 1},
            ],
        })
        checks.equal(
            body["receipt"]["owed"],
            "1 of these cards is owed to an open order. The orders stay as they are.",
            "ONE CARD MOVED TWICE IN A DRAFT counts once, never twice",
        )

    with isolated_home():
        _shelf()
        body = _drag_sections(1, {"first": 1, "last": 1, "to_box": 1})
        checks.equal(
            body["receipt"]["next_capture"],
            ["The next card you capture in Origins joins Commons, Section 3. "
             "Press S first to start a new section."],
            "SAME-BOX MOVE TO THE END: the moved section is now last, so the next capture joins it",
        )


def check_empty_section_starts(checks: Checks) -> None:
    """An empty section starts at the cards before it plus one (D58), so the capture screen's
    "next card" for it is that start plus zero. Sold cards leave gaps in the index, and a
    divider typed past the last card used to keep its INDEX minus the gaps before it, so the
    second of two trailing empty sections read card 498 where the next capture is card 497."""
    checks.note("")
    checks.note("EMPTY SECTION STARTS - an empty section starts after the last card on hand")
    sparse = (1, 2, 3, 4, 10, 11, 12, 20)  # 8 cards on hand, gaps in the index

    def spans(layout, occupied):
        return [
            (s["section"], s["start"], s["count"])
            for s in capture_server._section_spans(1, layout, len(occupied), occupied)
        ]

    checks.equal(
        spans((1, 5, 21, 30), sparse), [(1, 1, 4), (2, 5, 4), (3, 9, 0), (4, 9, 0)],
        "(a) two trailing empty sections both start at the card count plus one",
    )
    checks.equal(
        spans((1, 5, 21), sparse), [(1, 1, 4), (2, 5, 4), (3, 9, 0)],
        "(b) one trailing empty section starts at the card count plus one",
    )
    checks.equal(
        spans((1, 5, 13, 21), sparse), [(1, 1, 4), (2, 5, 3), (3, 8, 1), (4, 9, 0)],
        "(c) a middle empty section starts at the cards before it plus one",
    )
    checks.equal(
        spans((1, 5, 13, 15, 21), sparse),
        [(1, 1, 4), (2, 5, 3), (3, 8, 0), (4, 8, 1), (5, 9, 0)],
        "(c) an empty section between two filled ones starts at the cards before it plus one",
    )
    checks.equal(
        spans((1, 5, 13), sparse), [(1, 1, 4), (2, 5, 3), (3, 8, 1)],
        "(d) control: no empty section, nothing changes",
    )
    # A departed (sold or retired) record at index 21 sits right before the divider at 22.
    # `occupied` is on hand only, so 21 is not in it, and the section behind 22 is empty.
    checks.equal(
        spans((1, 5, 22), sparse), [(1, 1, 4), (2, 5, 4), (3, 9, 0)],
        "(e) a trailing empty section after a departed record starts at the cards on hand "
        "plus one, not one past it",
    )


def check_s_refuses_empty_last_section(checks: Checks) -> None:
    """S refuses while the last section holds no card ON HAND, so two empty sections in a row
    cannot exist (the owner's ruling). A departed record (sold, retired) is not in the box
    (D58, and `close_section`'s own rule), so it does not make the section non-empty. The
    store's `open_section` once counted any record's key, and a sold card behind the last
    divider let S write a second empty divider."""
    checks.note("")
    checks.note("S ON AN EMPTY LAST SECTION - refused unless a card on hand is behind the divider")

    def cap(box):
        capture_server.do_capture(capture_payload(box))

    def sections():
        return list(Store().read().inventory.box(1).sections)

    def press_s():
        try:
            capture_server.do_open_section(1, dict())
            return "opened"
        except master.SectionEmpty:
            return "SectionEmpty"

    with isolated_home():
        capture_server.do_create_box(dict(box=1, name="A"))
        for _ in range(3):
            cap(1)
        checks.equal(press_s(), "opened", "control: the last section holds a card, S opens one")
        checks.equal(press_s(), "SectionEmpty", "a divider after the last card: S refuses")
        checks.equal(sections(), [1, 4], "and writes no second divider")

    for how in ("sold", "retired"):
        with isolated_home():
            capture_server.do_create_box(dict(box=1, name="A"))
            for _ in range(3):
                cap(1)
            capture_server.do_open_section(1, dict())
            cap(1)
            if how == "sold":
                capture_server.do_mark_sold(1, 4, dict())
            else:
                capture_server.do_retire(1, 4, dict(reason="lost"))
            before = sections()
            checks.equal(
                press_s(), "SectionEmpty",
                f"the only card behind the last divider is {how}: S refuses, the section is empty",
            )
            checks.equal(sections(), before, "and writes no second divider")


CHECKS = (
    check_box_map_safety, check_section_moves, check_order_key_migration,
    check_per_card_order, check_card_moves, check_delete_after_placement,
    check_undo_keeps_paid_answers, check_front_of_box, check_card_move_refusals,
    check_divider_editor_keys, check_delete_keeps_dividers, check_merge_speed,
    check_r5_links_and_empty_sections, check_divider_anchor, check_capture_into_section,
    check_layout_batch, check_move_receipt_lines, check_empty_section_starts,
    check_s_refuses_empty_last_section,
)
