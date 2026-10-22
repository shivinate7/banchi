"""T7 group: a run's manifest keeps every holder's change when two holders write it.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `cli/runs.py`'s `Run.save` writes only
the fields this object changed since it last read or wrote the disk, under the per-run lock
`manifest.lock`, laid over what is on disk. `cli/cmd_match.py`'s `_Session.leave_joined` reads the
disk first, so a worker never mistakes a run a press joined for its own unjoined one.

Every assertion reads the disk through a fresh `runs.open_run`, never through the writer's object:
the writer's copy looks right even when the disk lost its write.

A tree without these changes still runs these checks. The methods that do not exist there
(`leave_joined`) are reported as FAIL lines, never raised.
"""

from __future__ import annotations

import multiprocessing

from harness.tests import Checks
from harness.tests.t7.common import isolated_home

WRITERS = 6
WRITES = 4


def _writer(directory: str, index: int, barrier, writes: int) -> None:
    """One process: hold its own copy of the run, wait until every peer does, then write."""
    from cli import runs

    run = runs.open_run(directory)
    barrier.wait(timeout=120)
    for j in range(writes):
        run.set(**{f"w{index}_{j}": index * 100 + j})
        run.add_batch_id(f"b{index}-{j}")


def check_manifest_concurrent_writers_lose_nothing(checks: Checks) -> None:
    """Six processes, each with a stale copy, each writing its own field and batch id: none lost."""
    from cli import runs

    ctx = multiprocessing.get_context("spawn")
    with isolated_home():
        run = runs.create("match-sweep")
        barrier = ctx.Barrier(WRITERS)
        procs = [
            ctx.Process(target=_writer, args=(str(run.directory), i, barrier, WRITES))
            for i in range(WRITERS)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=300)
        hung = [proc for proc in procs if proc.is_alive()]
        for proc in hung:
            proc.terminate()
            proc.join(timeout=30)
        checks.ok(not hung, f"all {WRITERS} writer processes finish", f"{len(hung)} still running")
        codes = [proc.exitcode for proc in procs]
        checks.ok(all(code == 0 for code in codes), "every writer process exits 0", f"exit codes: {codes}")

        manifest = runs.open_run(run.directory).manifest
        expected = {f"w{i}_{j}": i * 100 + j for i in range(WRITERS) for j in range(WRITES)}
        lost = sorted(key for key, value in expected.items() if manifest.get(key) != value)
        checks.ok(not lost, f"all {len(expected)} distinct fields survive the concurrent writes",
                  f"lost: {lost[:12]}")
        expected_ids = {f"b{i}-{j}" for i in range(WRITERS) for j in range(WRITES)}
        lost_ids = sorted(expected_ids - set(manifest.get("batch_ids") or []))
        checks.ok(not lost_ids, f"all {len(expected_ids)} batch ids survive the concurrent add_batch_id",
                  f"lost: {lost_ids[:12]}")


def check_manifest_join_survives_worker_set(checks: Checks) -> None:
    """A press joins a run the worker still holds. The worker's next set must not unjoin it."""
    from cli import runs

    with isolated_home():
        worker = runs.create("match-sweep")
        worker.set(selection={"keys": ["k1"]}, cards={"k1": {"state": "identified"}}, collected=True)
        press = runs.open_run(worker.directory)
        press.set(joined=True, counts={"cards_in": 1})
        worker.set(selection={"keys": ["k1", "k2"]},
                   cards={"k1": {"state": "identified"}, "k2": {"state": "identified"}})
        on_disk = runs.open_run(worker.directory).manifest
        checks.ok(on_disk.get("joined") is True, "joined stays True after the worker's next set",
                  f"joined on disk: {on_disk.get('joined')!r}")


def check_manifest_leave_joined_rotates(checks: Checks) -> None:
    """A worker that names unjoined cards leaves a run a press has joined, and opens a new one."""
    from cli import cmd_match, runs

    with isolated_home():
        worker = runs.create("match-sweep")
        worker.set(selection={"keys": ["k1"]}, cards={"k1": {"state": "identified"}}, collected=True, joined=False)
        press = runs.open_run(worker.directory)
        press.set(joined=True, counts={"cards_in": 1})

        session = cmd_match._Session()
        session.run, session.keys = worker, ["k1"]
        leave = getattr(session, "leave_joined", None)
        if leave is None:
            checks.ok(False, "the worker session has leave_joined", "missing on this tree")
        else:
            leave()
            checks.ok(session.run is None, "leave_joined drops a joined run the worker still held",
                      f"run kept: {session.run!r}")
            checks.ok(session.keys == [], "leave_joined drops the keys of that run", f"keys: {session.keys!r}")
            checks.ok(session.open_run().directory != worker.directory,
                      "the next chunk opens a new run, not the joined one")

        unjoined = runs.create("match-sweep")
        unjoined.set(selection={"keys": ["k2"]}, cards={"k2": {"state": "identified"}}, collected=True, joined=False)
        keep = cmd_match._Session()
        keep.run, keep.keys = unjoined, ["k2"]
        keep_leave = getattr(keep, "leave_joined", None)
        if keep_leave is None:
            checks.ok(False, "the worker session has leave_joined (unjoined run)", "missing on this tree")
        else:
            keep_leave()
            checks.ok(keep.run is unjoined and keep.keys == ["k2"],
                      "leave_joined keeps an unjoined run and its keys", f"keys: {keep.keys!r}")


def check_manifest_press_set_keeps_worker_adds(checks: Checks) -> None:
    """A worker adds a key to selection and cards while a press holds an older copy. The press's
    set (its own selection, cards and joined) must not drop the key."""
    from cli import runs

    with isolated_home():
        base = runs.create("match-sweep")
        base.set(selection={"keys": ["k1"]}, cards={"k1": {"state": "identified"}}, collected=True, joined=False)
        press = runs.open_run(base.directory)
        worker = runs.open_run(base.directory)
        worker.set(selection={"keys": ["k1", "k2"]},
                   cards={"k1": {"state": "identified"}, "k2": {"state": "identified"}})
        press.set(selection={"keys": ["k1"]}, cards={"k1": {"state": "priced"}}, joined=True)
        on_disk = runs.open_run(base.directory).manifest
        checks.ok("k2" in (on_disk.get("selection") or {}).get("keys", []),
                  "the worker's key k2 survives the press's selection write",
                  f"keys on disk: {(on_disk.get('selection') or {}).get('keys')!r}")
        checks.ok("k2" in (on_disk.get("cards") or {}), "the worker's card k2 survives the press's cards write",
                  f"cards on disk: {sorted((on_disk.get('cards') or {}))!r}")
        checks.ok(((on_disk.get("cards") or {}).get("k1") or {}).get("state") == "priced",
                  "the press's own change to card k1 lands", f"k1 on disk: {(on_disk.get('cards') or {}).get('k1')!r}")
        checks.ok(on_disk.get("joined") is True, "the press's joined=True lands", f"joined: {on_disk.get('joined')!r}")


def check_manifest_caller_removal_sticks(checks: Checks) -> None:
    """A caller that removes a key, a card and a selection sub-key still removes them, even while a
    peer adds a key the caller never saw."""
    from cli import runs

    with isolated_home():
        base = runs.create("match-sweep")
        base.set(selection={"keys": ["k1", "k2"], "since": "2026-01-01"},
                 cards={"k1": {"state": "identified"}, "k2": {"state": "identified"}}, collected=True)
        caller = runs.open_run(base.directory)
        peer = runs.open_run(base.directory)
        peer.set(selection={"keys": ["k1", "k2", "k3"], "since": "2026-01-01"})
        caller.set(selection={"keys": ["k1"]}, cards={"k1": {"state": "identified"}})
        on_disk = runs.open_run(base.directory).manifest
        selection = on_disk.get("selection") or {}
        checks.ok("k2" not in selection.get("keys", []), "a removed selection key stays removed",
                  f"keys on disk: {selection.get('keys')!r}")
        checks.ok("k3" in selection.get("keys", []), "the peer's key k3 survives the caller's removal",
                  f"keys on disk: {selection.get('keys')!r}")
        checks.ok("since" not in selection, "a removed selection sub-key stays removed",
                  f"selection on disk: {selection!r}")
        checks.ok("k2" not in (on_disk.get("cards") or {}), "a removed card stays removed",
                  f"cards on disk: {sorted(on_disk.get('cards') or {})!r}")


CHECKS = (
    check_manifest_join_survives_worker_set,
    check_manifest_leave_joined_rotates,
    check_manifest_press_set_keeps_worker_adds,
    check_manifest_caller_removal_sticks,
    check_manifest_concurrent_writers_lose_nothing,
)
