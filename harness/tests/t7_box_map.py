"""T7's box map cases (D262, D264, D265): a section moves whole, and nothing it owns is lost.

A SIBLING OF `t7_store_and_seams.py`, NOT A NEW HARNESS TEST. `t7_store_and_seams.run()` calls
every `check_*` here, so T7's verdict carries them and the harness still has ten tests. They
live in their own file because they share one fixture (a box of named sections) and the
parent file is already 36,000 lines.

Every case below was observed FAILING before its fix was kept.
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

from harness.tests.t7_store_and_seams import (
    Checks,
    Store,
    capture_payload,
    capture_server,
    fake_cid,
    isolated_home,
    join,
    master,
    refusal,
    resolve,
    seam_run,
)


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
        capture_server.do_put_box(2, {"state": master.BOX_CLOSED})
        refusal(
            checks, lambda: capture_server.do_move_sections(1, {"first": 2, "to_box": 2}),
            "box_closed", "a sealed destination refuses (D20)",
        )
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

    order = master.BoxOrder.from_sequence(list(range(1, 10)), 10)
    checks.ok(order.identity, "an order that is the index is stored as nothing: no migration")


CHECKS = (check_box_map_safety, check_section_moves)
