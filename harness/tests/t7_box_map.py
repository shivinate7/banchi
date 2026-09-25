"""T7's box map cases (D262, D264, D265): a section moves whole, and nothing it owns is lost.

A SIBLING OF `t7_store_and_seams.py`, NOT A NEW HARNESS TEST. `t7_store_and_seams.run()` calls
every `check_*` here, so T7's verdict carries them and the harness still has ten tests. They
live in their own file because they share one fixture (a box of named sections) and the
parent file is already 36,000 lines.

Every case below was observed FAILING before its fix was kept.
"""
from __future__ import annotations

import os

from harness.tests.t7_store_and_seams import (
    Checks,
    Store,
    capture_server,
    isolated_home,
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


CHECKS = (check_box_map_safety,)
