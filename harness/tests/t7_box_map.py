"""T7's box map cases (D262, D264, D265): a section moves whole, and nothing it owns is lost.

A SIBLING OF `t7_store_and_seams.py`, NOT A NEW HARNESS TEST. `t7_store_and_seams.run()` calls
every `check_*` here, so T7's verdict carries them and the harness still has ten tests. They
live in their own file because they share one fixture (a box of named sections) and the
parent file is already 36,000 lines.

Every case below was observed FAILING before its fix was kept.
"""
from __future__ import annotations

import json
import os
import random
import threading
from typing import List, Optional, Tuple

from harness.tests.t7_store_and_seams import (
    Checks,
    QuietHandler,
    Store,
    capture_payload,
    capture_server,
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
       card read as `departed` and lost its row on Pricing (D165 measured 99 such cards).
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
            lambda: capture_server.do_move_cards(5, {"to_box": 7, "indices": [3]}),
            "card_being_read",
            "a card with a live paid reading does not move (D262, D174)",
        )
        checks.ok(
            Store().read().inventory.cards["5/3"].state != master.MOVED,
            "and nothing moved: the card is still where the paid answer will land",
        )

        capture_server.do_move_cards(5, {"to_box": 7, "indices": [2]})
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
            capture_server.do_move_cards(7, {"to_box": 8, "indices": [1]})
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
    """The box map's write (D264, D265): a section moves whole, before any section.

    Each case below was red before `do_move_sections` existed (the route answered nothing),
    and the placement cases were red again against a first draft that appended at the back.
    """
    checks.note("")
    checks.note("BOX MAP — section moves, placement, reorder, merge, split, undo (D264, D265)")

    with isolated_home():
        _shelf()
        before_digests = {b: capture_server._box_digest(Store().read().inventory, b) for b in (1, 2)}
        body = capture_server.do_move_sections(1, {"first": 2, "last": 2, "to_box": 2, "before": 2})
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
        again = capture_server.do_move_sections(1, {"first": 2, "last": 2, "to_box": 2, "before": 1})
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
        capture_server.do_move_sections(1, {"first": 3, "last": 3, "to_box": 1, "before": 1})
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
            "the stored index never moves (D10, D58): only the order does (D265)",
        )
        status, row = capture_server.do_capture(capture_payload(1))
        checks.ok(
            _walk(1)[-1] is None and _sections(1)[-1] == ("Uncommons", 5),
            "the next capture still lands at the near end, in the last section",
            str(_sections(1)),
        )

    with isolated_home():
        _shelf()
        capture_server.do_move_sections(1, {"first": 1, "last": 1, "to_box": 2})
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
        capture_server.do_move_sections(1, {"first": 1, "last": 3, "to_box": 2})
        checks.equal(
            _sections(2),
            [("Singles", 2), ("Promos", 2), ("Commons", 3), ("Uncommons", 4), ("Rares", 2)],
            "a merge moves every section, in order, dividers and names carried",
        )
        checks.equal(_walk(1), [], "and the merged box is left empty")

    with isolated_home():
        _shelf()
        body = capture_server.do_move_sections(1, {"first": 2, "last": 3, "new_box": True})
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
            lambda: capture_server.do_move_sections(
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
            checks, lambda: capture_server.do_move_sections(1, {"first": 2, "to_box": 3}),
            "card_being_read", "a section holding a card with a live paid reading refuses",
        )
        checks.equal(
            _walk(1), [f"o{i}" for i in range(1, 10)],
            "and a refusal part way through writes nothing: the cards before it did not move",
        )

    with isolated_home():
        _shelf()
        capture_server.do_move_sections(1, {"first": 3, "last": 3, "to_box": 1, "before": 1})
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
    """Schema 13 (D265, "A key on each card"): every card gets the key its index already is.

    Red before `_add_card_order` existed: the column was missing and every payload had no key.
    """
    import sqlite3

    from store import db, files

    checks.note("")
    checks.note("BOX MAP — the order key migration, schema 12 to 13 (D265)")
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
        checks.equal((column, stamp), (13, "13"), "the column is filled too, and the file is stamped 13")
        checks.equal(
            [_label(1, f"o{i}") for i in range(1, 10)], labels_before,
            "no label moves: D58's counted numbers are exactly what they were",
        )

        # IDEMPOTENT: a key a card already has is kept when the step runs again.
        capture_server.do_move_sections(1, {"first": 3, "to_box": 1, "before": 1})
        placed = _keys(1)
        conn = sqlite3.connect(str(db.path(directory)))
        conn.execute("UPDATE meta SET value = '12' WHERE key = 'schema'")
        conn.commit()
        conn.close()
        checks.equal(_keys(1), placed, "a second upgrade keeps every key a card already has")


def check_per_card_order(checks: Checks) -> None:
    """Each kind of move writes the key of each moved card, and no other card (D265)."""
    checks.note("")
    checks.note("BOX MAP — per-card order keys after each kind of move (D265)")

    with isolated_home():
        _shelf()
        src, dst = _keys(1), _keys(2)
        capture_server.do_move_sections(1, {"first": 2, "to_box": 2, "before": 2})
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
        capture_server.do_move_sections(1, {"first": 3, "to_box": 1, "before": 2})
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
        capture_server.do_move_sections(1, {"first": 1, "last": 3, "to_box": 2})
        checks.equal(_changed(dst, _keys(2)), [], "a merge writes no card the destination already held")
        body = None

    with isolated_home():
        _shelf()
        body = capture_server.do_move_sections(1, {"first": 2, "last": 3, "new_box": True})
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
        body = capture_server.do_move_range(
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
        capture_server.do_move_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
        checks.equal(_walk(1)[0], "o9", "one card moves to the far back of its own box")
        checks.equal(
            _sections(1), [("Commons", 4), ("Uncommons", 4), ("Rares", 1)],
            "and it joins section 1: the front divider moves with it",
        )
        capture_server.do_move_range(1, {"indices": [2], "to_box": 1, "before_card": 4})
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
        capture_server.do_move_range(1, {"indices": [1, 2], "to_box": 2, "section_end": 1})
        checks.equal(
            _walk(2), ["m1", "m2", "o1", "o2", "m3", "m4"],
            "a range dropped at a section's end lands after its last card, before the next divider",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_range(
                1, {"indices": [3], "to_box": 1, "section_end": 3,
                    "aim": {"count": 1, "first": "x", "last": "x"}},
            ),
            "section_changed", "a stale aim refuses a card move",
        )

    with isolated_home():
        _shelf()
        # Each press halves the same gap, in front of card 2, until it is too narrow.
        for n in range(30):
            capture_server.do_move_range(1, {"indices": [8 + n % 2], "to_box": 1, "before_card": 2})
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
    checks.note("BOX MAP R3 — a mid-box delete after a placement (D265, D10 ruling 1)")

    def distinct(box: int) -> bool:
        keys = [k for k in _keys(box).values()]
        return len(keys) == len(set(keys))

    with isolated_home():
        _shelf()
        capture_server.do_move_range(1, {"indices": [2], "to_box": 2, "before_card": 3})
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
        capture_server.do_move_range(1, {"indices": [5, 6], "to_box": 2, "section_end": 2})
        capture_server.do_move_range(2, {"indices": [3], "to_box": 2, "before_card": 1})
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
        body = capture_server.do_move_sections(1, {"first": 2, "to_box": 2})
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
    checks.note("BOX MAP R3 — the front of the box after a far-back placement (D265)")

    def reads() -> object:
        try:
            capture_server.do_boxes()
            return True
        except Exception as caught:  # noqa: BLE001 — the failure is the assertion
            return f"{type(caught).__name__}: {caught}"

    with isolated_home():
        _shelf()
        capture_server.do_move_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
        capture_server.do_move_sections(1, {"first": 2, "to_box": 2})
        checks.equal(reads(), True, "a sections move after a far-back placement still reads")
        checks.equal(
            _label(1, "o9"), "Origins, Section 1, Card 1",
            "and the card at the far back is card 1 of section 1",
        )

    with isolated_home():
        _shelf()
        capture_server.do_move_range(1, {"indices": [9], "to_box": 1, "before_card": 1})
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
            lambda: capture_server.do_move_range(1, {"indices": [2], "to_box": 1, "before_card": 3}),
            "before_invalid", "item 6: a card put back in front of its own next card is a no-op, refused",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_range(1, {"indices": [3], "to_box": 1, "section_end": 1}),
            "before_invalid", "item 6: the last card of a section put at that section's end is refused",
        )
        capture_server.do_move_range(1, {"indices": [5], "to_box": 2, "section_end": 2})
        refusal(
            checks,
            lambda: capture_server.do_move_range(1, {"indices": [6], "to_box": 1, "before_card": 5}),
            "before_invalid", "item 7: a tombstone is not a card to put anything in front of",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_range(1, {"indices": [2], "to_box": 9, "section_end": 1}),
            "box_not_found", "item 8: a box that does not exist is refused, never made",
        )
        refusal(
            checks,
            lambda: capture_server.do_move_sections(1, {"first": 2, "to_box": 9}),
            "box_not_found", "item 8: and a section move to it is refused too",
        )
        checks.ok(Store().read().inventory.box(9) is None, "and no box 9 was made")
        capture_server.do_create_box({"box": 3, "name": "Empty"})
        capture_server.do_move_range(1, {"indices": [2], "to_box": 3})
        checks.equal(_walk(3), ["o2"], "item 9: a card moves into an empty box")


def check_divider_editor_keys(checks: Checks) -> None:
    """R4 review, item 1: the divider editor keeps a fractional key.

    Red before the fix: `join.divider_index` cut a key to an integer, so saving the editor's
    own unchanged starts after a section move moved every fractional divider, and m2 fell into
    the moved section.
    """
    checks.note("")
    checks.note("BOX MAP R4 — the divider editor after a placement (D265)")
    with isolated_home():
        _shelf()
        capture_server.do_move_sections(1, {"first": 2, "to_box": 2, "before": 2})
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
        capture_server.do_move_sections(1, {"first": 2, "to_box": 2})
        capture_server.do_put_box(2, {"sections": [1, 5]})
        checks.equal(
            (_label(2, "m4"), _label(2, "o4"), _label(2, "o5")),
            ("Mixed, Section 1, Card 4", "Mixed, Section 2, Card 1", "Mixed, Section 2, Card 2"),
            "a divider set at a placed card starts the section at that card",
        )

    with isolated_home():
        _shelf()
        capture_server.do_move_range(1, {"indices": [4], "to_box": 2, "before_card": 3})
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
        body = capture_server.do_move_sections(1, {"first": 2, "to_box": 2})
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
        capture_server.do_move_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
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
    """R4 review, item 4: a 500-card merge into a 500-card box holds the lock under 1 s.

    Red before R3's fix: 3.8 s, growing with the square of the box."""
    import time

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
        start = time.perf_counter()
        capture_server.do_move_sections(1, {"first": 1, "to_box": 2})
        took = time.perf_counter() - start
        checks.ok(took < 1.0, "a 500-into-500 merge takes under a second", f"{took:.2f} s")


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
        capture_server.do_move_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
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
        capture_server.do_move_range(1, {"indices": [2], "to_box": 2, "section_end": 2})
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
        capture_server.do_move_range(1, {"indices": [4, 5, 6, 7], "to_box": 2, "section_end": 2})
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


def _fuzz_dividers(seeds, rounds):
    """The divider proof's fuzz. A PHYSICAL MODEL of each box (sections of card names) is
    kept beside the store, every operation goes through its route, and after each one the
    store's sections and every card's section and card number must equal the model. Returns
    `(operations, failures)`. Fixed seeds, so a failure replays exactly."""
    bad = []
    ops = 0
    for seed in seeds:
        rng = random.Random(seed)
        with isolated_home():
            phys = dict()
            for b in (1, 2, 3):
                capture_server.do_create_box(dict(box=b, name="B" + str(b)))
                phys[b] = [[]]

            def capture(b, phys=phys):
                _, row = capture_server.do_capture(capture_payload(b))
                inv = Store().read().inventory
                phys[b][-1].append(inv.cards[master.position_key(b, row["index"])].cid)

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

            for _ in range(rounds):
                kind = rng.choice(("capture", "S", "undo_S", "move", "range", "sections",
                                   "remove", "capture_undo"))
                b = rng.choice((1, 2, 3))
                dst = rng.choice((1, 2, 3))
                inv = Store().read().inventory
                saved = [[list(sec) for sec in phys[x]] for x in (1, 2, 3)]
                try:
                    if kind == "capture":
                        capture(b)
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
                        capture_server.do_move_cards(b, dict(to_box=dst, indices=[_where(inv, cid)]))
                        drop(b, cid)
                        phys[dst][-1].append(cid)
                    elif kind == "range" and cards(b):
                        cid = rng.choice(cards(b))
                        rest = [c for c in cards(dst) if c != cid]
                        if rest:
                            target = rng.choice(rest)
                            capture_server.do_move_range(b, dict(
                                indices=[_where(inv, cid)], to_box=dst,
                                before_card=_where(inv, target)))
                            drop(b, cid)
                            sec = next(x for x in phys[dst] if target in x)
                            sec.insert(sec.index(target), cid)
                        else:
                            j = rng.randrange(len(phys[dst])) + 1
                            capture_server.do_move_range(b, dict(
                                indices=[_where(inv, cid)], to_box=dst, section_end=j))
                            drop(b, cid)
                            phys[dst][j - 1].append(cid)
                    elif kind == "sections" and cards(b) and b != dst:
                        first = rng.randrange(len(phys[b])) + 1
                        before = rng.randrange(len(phys[dst])) + 1
                        capture_server.do_move_sections(b, dict(
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
                    if not (isinstance(caught, master.SectionEmpty) and not phys[b][-1]):
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
    """The divider proof (D264, D265, D260, D58, D10): no write moves a divider off the cards
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
        capture_server.do_move_range(1, dict(indices=[5], to_box=1, before_card=1))
        capture_server.do_move_cards(2, dict(to_box=1, indices=[1]))
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


CHECKS = (
    check_box_map_safety, check_section_moves, check_order_key_migration,
    check_per_card_order, check_card_moves, check_delete_after_placement,
    check_undo_keeps_paid_answers, check_front_of_box, check_card_move_refusals,
    check_divider_editor_keys, check_delete_keeps_dividers, check_merge_speed,
    check_r5_links_and_empty_sections, check_divider_anchor,
)
