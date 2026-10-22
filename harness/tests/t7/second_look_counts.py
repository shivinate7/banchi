"""T7 group: a join records where each second-look card went, in one place.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). The run panel's receipt reads
`counts.second_look_held`, `second_look_main` and `second_look_parked` from the run's own
join record (`cli/cmd_join.py`'s `record_join`). It does not read the live queues, so the
receipt and the counts beside it cannot disagree.

The join is faked at its boundary: `record_join` reads a run's manifest and a resolved join
through a handful of attributes, and those are all this check supplies. Nothing here touches
a store, a catalog or the network.

THE CARDS. Six second-look keys, and what each one does at the join:
    9/1  held    queued to the main queue for readers_disagree
    9/2  held    queued to the main queue for second_look_unsure
    9/3  main    queued to the main queue for any other reason
    9/4  parked  queued to the parked queue
    9/5  main    failed before the join saw it (a pre-join failure is always the main queue's)
    9/6  settled in neither queue
A card queued outside the second look (9/7, 9/8) is counted nowhere.
"""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace as NS

from harness.tests import Checks


def _queued(box: int, index: int, queue: str, reason: str) -> NS:
    return NS(card=NS(position=NS(box=box, index=index)), queue=queue, destination=NS(queue=queue, reason=reason))


class _Report:
    def __init__(self, queued: list) -> None:
        self.queued = queued
        self.cards_in = len(queued)

    def queue(self, name: str) -> list:
        return [q for q in self.queued if q.queue == name]


class _RunDir:
    def __init__(self, manifest: dict) -> None:
        self.manifest = manifest
        self.written: dict = {}

    def set(self, **fields) -> None:
        self.written = fields


def check_second_look_record(checks: Checks) -> None:
    checks.note("")
    checks.note("SECOND-LOOK RECORD — record_join counts each second-look card in one of three places, or none")
    from cli import cmd_join
    from pipeline import routing

    keys = [f"9/{n}" for n in range(1, 7)]
    queued = [
        _queued(9, 1, routing.MAIN, routing.READERS_DISAGREE),
        _queued(9, 2, routing.MAIN, routing.SECOND_LOOK_UNSURE),
        _queued(9, 3, routing.MAIN, "match_too_weak"),
        _queued(9, 4, routing.PARKED, "match_too_weak"),
        _queued(9, 7, routing.MAIN, "match_too_weak"),
        _queued(9, 8, routing.PARKED, "match_too_weak"),
    ]
    game = NS(game="pokemon", source={}, report=_Report(queued))
    resolved = NS(
        joins=OrderedDict([("pokemon", game)]),
        failures=[NS(key="9/5")],
        matches={},
        rule="rule",
        basis="basis",
        no_market_data_skus=(),
        sub_threshold_skus=(),
    )
    run_dir = _RunDir({"second_look": [{"key": key} for key in keys]})
    cmd_join.record_join(run_dir, resolved, 0.5)
    counts = run_dir.written.get("counts", {})
    held = counts.get("second_look_held", 0)
    main = counts.get("second_look_main", 0)
    parked = counts.get("second_look_parked", 0)

    checks.equal(held, 2, "held: readers_disagree and second_look_unsure in the main queue count as held")
    checks.equal(main, 2, "main: another reason in the main queue, and a pre-join failure, count as main")
    checks.equal(parked, 1, "parked: a second-look card in the parked queue counts as parked")
    checks.equal(
        len(keys) - held - main - parked,
        1,
        "settled: the one second-look card in neither queue is the settled remainder",
    )

    bare = _RunDir({})
    cmd_join.record_join(bare, resolved, 0.5)
    no_look = bare.written.get("counts", {})
    checks.ok(
        not any(name.startswith("second_look_") for name in no_look),
        "no second look, no second_look_* keys in the join record",
        f"counts: {no_look!r}",
    )


CHECKS = (check_second_look_record,)
