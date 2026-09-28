#!/usr/bin/env python3
"""`scripts/demo-record.py`'s resume cache (PR 4B lane M), proved without a real server,
store or kill signal — the way `demo-record-walkplan-selftest.py` proves its own subject,
against the real functions with a fake recording collector.

WHAT THIS IS FOR. The owner: "is there anyway u can have it chunking so that way it's not
starting from zero each time". A real mirror sweep touches hundreds of routes and can run
for minutes; a build interrupted partway used to lose every route it had already answered.
`WorkArea` writes each route's answer to a gitignored cache the instant it lands, keyed by a
digest of the store's own content (`snapshot_key`), so a re-run over the SAME store skips
what is already there and a DIFFERENT store starts over.

WHAT COULD GO WRONG WITHOUT EACH PIECE, PROVED BELOW.
  (a) `take`/`take_post` never check the cache first        -> nothing is ever skipped
  (b) the cache changes what a route answers                -> a resumed bundle can drift
      from a clean one (this is what `POST /shipping/batches`'s random batch id would have
      done — `_new_batch_id()` never repeats — if that one call were not routed through the
      same skip-if-already-recorded check as everything else; see `sweep`'s own comment)
  (c) `save()` writes the final name directly, no temp+rename -> a write a kill catches
      mid-flight leaves a truncated `.json` that `load()` cannot tell from a real answer
  (d) the key is the store's PATH, or its mtime              -> a rebuilt or changed store
      wrongly reuses another store's cached routes, or a copy with an unchanged mtime never
      resumes at all

REVIEW ROUND 2 ADDED TWO MORE, BOTH FOUND BY THE REVIEWER, NOT BY THIS FILE:
  (e) `save()` writes a route's RAW body                     -> a second, persistent copy of
      whatever a route answers (an order or pick's buyer name, D193) sits on disk across
      process runs, unscrubbed, which D295's outcome ("nothing unscrubbed sits anywhere")
      forbids regardless of whether the store it came from was already scrubbed upstream
  (f) a stateful POST (`POST /shipping/batches`, whose id lives only in the SERVER
      PROCESS's own memory, `server/shipping_routes.py:_BATCHES`) is cached the moment it
      succeeds, before its dependent GET does -> a kill in between strands that GET
      forever: a resumed run's server is a NEW process that never heard of the old id

Each is proved on the real `demo_record.WorkArea` / `demo_record.sweep` — a `FakeServer`
answers every GET/POST with a body that depends only on the path, deterministically, so a
clean run and a killed-then-resumed run can be compared byte for byte. `StatefulFakeServer`
(for (f)) is the one exception: its POST-created ids are valid only in the INSTANCE that
created them, the way the real server's in-memory batch table is valid only in that process.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "demo_record", ROOT / "scripts" / "demo-record.py"
)
demo_record = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(demo_record)

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


# ------------------------------------------------------------------------- the fake server


class Interrupted(Exception):
    """Stands in for a kill. Raised instead of the process actually dying, so the on-disk
    state left behind is exactly what a real kill would leave: every route whose `save()`
    completed before this call, and nothing for the one that was in flight."""


def _body_for(key: str) -> dict:
    """A body that is a pure function of the key — never of when or how many times it was
    asked for — so a killed-and-resumed run answers byte-for-byte the same as a clean one."""
    return {"key": key, "digest": hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]}


class FakeServer:
    """No network, no subprocess: every GET/POST answers 200 with `_body_for`'s body.
    `kill_after` raises `Interrupted` from the call after the Nth, simulating a process
    killed mid-sweep. `log` records every call attempted, in order, `(kind, path)` —
    including the one that raises — so a test can find WHERE in the deterministic call
    sequence a given route sits, rather than hand-counting it."""

    def __init__(self, kill_after: int = None) -> None:
        self.calls = 0
        self.kill_after = kill_after
        self.log = []

    def _step(self, kind: str, path: str) -> None:
        self.calls += 1
        self.log.append((kind, path))
        if self.kill_after is not None and self.calls > self.kill_after:
            raise Interrupted("simulated kill after %d call(s)" % self.kill_after)

    def get(self, path: str):
        self._step("GET", path)
        return 200, _body_for(path)

    def post(self, path: str, payload: dict):
        self._step("POST", path)
        return 200, _body_for(demo_record.post_key(path, payload))


class StatefulFakeServer(FakeServer):
    """Like `FakeServer`, except `/shipping/batches` behaves the way the real server's
    `_BATCHES` table does (`server/shipping_routes.py`): the id a POST creates is valid
    only for a GET against THIS SAME INSTANCE. A fresh instance — a resumed run's new
    server process — has never heard of it and answers 404, exactly like the real one
    would for a batch nobody here ever created. Every other path answers like `FakeServer`.
    """

    def __init__(self, kill_after: int = None) -> None:
        super().__init__(kill_after=kill_after)
        self._known_batches = set()
        self._next_batch = 0

    def post(self, path: str, payload: dict):
        self._step("POST", path)
        if path == "/shipping/batches":
            self._next_batch += 1
            batch = "batch-%d-of-instance-%d" % (self._next_batch, id(self))
            self._known_batches.add(batch)
            return 200, {"batch": batch}
        return 200, _body_for(demo_record.post_key(path, payload))

    def get(self, path: str):
        self._step("GET", path)
        prefix = "/shipping/batches/"
        if path.startswith(prefix):
            batch = path[len(prefix):]
            if batch not in self._known_batches:
                return 404, None
            return 200, {"batch": batch, "ok": True}
        return 200, _body_for(path)


def _space(home: Path) -> Dict[str, object]:
    """A small, fixed parameter space — enough to exercise every loop in `sweep()` and
    `sweep_coverage()` without a real store. `home` carries no `shipping-export.csv`, so the
    shipping lane falls back to the repo's own anonymised fixture, read-only."""
    return {
        "home": home,
        "boxes": ["1", "2"],
        "cards": ["1/1", "1/2", "2/1"],
        "games": ["riftbound"],
        "search": ["alpha", "beta"],
        "skus": ["SKU-A", "SKU-B"],
        "orders": [],
    }


def _write_store(home: Path, content: bytes) -> None:
    (home / "inventory").mkdir(parents=True, exist_ok=True)
    (home / "inventory" / "store.sqlite").write_bytes(content)


def _sweep(work: "demo_record.WorkArea", home: Path, kill_after: int = None,
           server_cls=FakeServer, server=None):
    """One sweep over a fake server. Returns `(recorded, stats, server)`, or raises
    `Interrupted` (leaving whatever `work` already holds on disk) if `kill_after` fires.
    Pass `server` (already constructed) to reuse a specific instance, e.g. to prove that a
    resumed run's server is a genuinely DIFFERENT one (`StatefulFakeServer`)."""
    if server is None:
        server = server_cls(kill_after=kill_after)
    recorded, skipped, stats = demo_record.sweep(server, _space(home), work)
    return recorded, stats, server


# ------------------------------------------------------------------------------- the tests


def _save_is_atomic_no_tmp_survives() -> None:
    """The mechanism behind (c): `save()` leaves only the final name, and an orphan `.tmp`
    — the shape a kill mid-write leaves — is invisible to `load()`."""
    with tempfile.TemporaryDirectory() as scratch:
        work = demo_record.WorkArea(Path(scratch) / "home")
        work.dir = Path(scratch) / "work"
        work.save("k1", {"status": 200, "body": {"x": 1}})
        files = sorted(p.name for p in work.dir.iterdir())
        want = hashlib.sha256(b"k1").hexdigest() + ".json"
        ok(files == [want], "save() leaves only the final name, no .tmp survives",
           "got %r" % files)

        orphan = work.dir / "orphan.json.tmp"
        orphan.write_text("garbage", "utf-8")
        ok(len(work.load()) == 1, "an orphan .tmp file (a write caught mid-flight) is "
           "invisible to load()", "got %d entries" % len(work.load()))


def _key_reflects_prices_json_too() -> None:
    """The resume key is not `store.sqlite` alone — the pricing answer lives in its own
    file beside it (D86) — so a change there must count as a different snapshot too."""
    with tempfile.TemporaryDirectory() as scratch:
        home = Path(scratch) / "home"
        _write_store(home, b"same-store")
        key_no_prices = demo_record.snapshot_key(home)
        (home / "inventory" / "prices.json").write_text("{}", "utf-8")
        key_with_prices = demo_record.snapshot_key(home)
        ok(key_no_prices != key_with_prices, "adding prices.json changes the snapshot key")
        (home / "inventory" / "prices.json").write_text('{"x":1}', "utf-8")
        key_changed_prices = demo_record.snapshot_key(home)
        ok(key_with_prices != key_changed_prices,
           "changing prices.json's own content changes the snapshot key")


def _resume_skips_and_matches_a_clean_run() -> None:
    """(a) a re-run over the same store makes no call for a route already on disk.
    (b) its finished bundle is byte-identical to one clean, uninterrupted run."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        home = root / "home"
        _write_store(home, b"snapshot-A")

        clean_area = demo_record.WorkArea(home)
        clean_area.dir = root / "work-clean"
        clean_recorded, clean_stats, _clean_server = _sweep(clean_area, home)
        total = len(clean_recorded)
        ok(total > 30, "the fixture space produces a real number of routes",
           "got %d" % total)
        ok(clean_stats["new"] == total and clean_stats["resumed"] == 0,
           "a clean run records everything as new, nothing resumed")

        killed_area = demo_record.WorkArea(home)
        killed_area.dir = root / "work-killed"
        kill_point = total // 3
        try:
            _sweep(killed_area, home, kill_after=kill_point)
            ok(False, "the kill actually interrupts the sweep")
        except Interrupted:
            pass
        landed = killed_area.load()
        ok(len(landed) == kill_point,
           "the kill leaves exactly the routes that finished landing on disk",
           "got %d, kill_after=%d" % (len(landed), kill_point))

        resumed_recorded, resumed_stats, resumed_server = _sweep(killed_area, home)
        ok(resumed_stats["resumed"] == kill_point,
           "the resumed run's own count of skipped routes matches what was on disk",
           "got %d, want %d" % (resumed_stats["resumed"], kill_point))
        ok(resumed_server.calls == total - kill_point,
           "(a) the resumed run calls the server only for routes the kill never finished",
           "got %d calls, want %d" % (resumed_server.calls, total - kill_point))
        ok(len(resumed_recorded) == total, "the resumed run finishes with every route")

        clean_json = json.dumps(clean_recorded, sort_keys=True)
        resumed_json = json.dumps(resumed_recorded, sort_keys=True)
        ok(clean_json == resumed_json,
           "(b) the resumed run's bundle is byte-identical to the clean run's")


def _corrupted_route_file_is_rerecorded() -> None:
    """(c) A route file that is not valid JSON — never counted as recorded — is asked for
    again on the next sweep, exactly once."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        home = root / "home"
        _write_store(home, b"snapshot-B")
        work = demo_record.WorkArea(home)
        work.dir = root / "work"

        recorded, _stats, _server = _sweep(work, home)
        total = len(recorded)
        victim = sorted(work.dir.glob("*.json"))[0]
        victim.write_text("{not valid json", "utf-8")

        loaded = work.load()
        ok(len(loaded) == total - 1, "a corrupted route file is not counted as recorded",
           "got %d, want %d" % (len(loaded), total - 1))

        rerecorded, _restats, reserver = _sweep(work, home)
        ok(reserver.calls == 1, "exactly the corrupted route is re-fetched",
           "got %d calls" % reserver.calls)
        ok(len(rerecorded) == total, "the corrupted route is whole again after the re-run")


def _changed_snapshot_starts_fresh() -> None:
    """(d) A different store hashes to a different key, so it reads an empty work area —
    no rule needs to notice the change, the key already differs."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        home = root / "home"
        _write_store(home, b"snapshot-C")
        work1 = demo_record.WorkArea(home)
        work1.dir = root / "work" / work1.key
        _sweep(work1, home)
        ok(len(work1.load()) > 0, "the first snapshot leaves a non-empty work area")

        _write_store(home, b"snapshot-D")  # the same home path, a changed store
        work2 = demo_record.WorkArea(home)
        ok(work2.key != work1.key, "a changed store hashes to a different key")
        work2.dir = root / "work" / work2.key
        ok(len(work2.load()) == 0, "the new key's own work area starts empty")


def _work_area_scrubs_before_it_writes_to_disk() -> None:
    """(e) A route's raw answer may carry the machine's own absolute path — `/status`
    really does (`captures_root`, the corpus file) — and the work area is a SECOND,
    PERSISTENT copy that outlives the one process a pre-existing whole-dict scrub at
    publish time used to be enough to cover. Nothing unscrubbed may sit there."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        home = root / "home"
        _write_store(home, b"snapshot-scrub")

        secret_root = Path("/Users/some-owner/Developer/pkmnscan")
        pairs = [(str(secret_root), "/machine")]

        class LeakyServer(FakeServer):
            """`/status` answers with a literal machine path, the way the real one does."""

            def get(self, path):
                self._step("GET", path)
                if path == "/status":
                    return 200, {"captures_root": str(secret_root / "captures")}
                return 200, _body_for(path)

        work = demo_record.WorkArea(home, pairs)
        work.dir = root / "work"
        _sweep(work, home, server=LeakyServer())

        leaked = [f.name for f in work.dir.glob("*.json")
                  if str(secret_root) in f.read_text("utf-8")]
        ok(not leaked, "(e) no work-area file contains a name the scrub replaces",
           "leaked in %r" % leaked)

        status_entry = work.load().get("/status")
        ok(status_entry is not None
           and status_entry["body"]["captures_root"] == "/machine/captures",
           "the scrubbed value, not the raw one, is what a later reader gets back",
           "got %r" % status_entry)


def _stale_keys_are_pruned() -> None:
    """`prune_others()`: a run over a CURRENT key deletes every OTHER key's work area —
    an old snapshot's routes (buyer names included) should not just sit there once a run
    has moved on. Patches the module-level `WORK_ROOT` for the duration of the test alone,
    so this never touches the real, gitignored cache under the checkout."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        original_root = demo_record.WORK_ROOT
        demo_record.WORK_ROOT = root / "cache"
        try:
            home = root / "home"
            _write_store(home, b"snapshot-old")
            old_work = demo_record.WorkArea(home)
            old_work.save("some/route", {"status": 200, "body": {"x": 1}})
            ok(old_work.dir.is_dir(), "the old key's own directory exists before the prune")

            _write_store(home, b"snapshot-new")
            new_work = demo_record.WorkArea(home)
            ok(new_work.key != old_work.key, "the new store hashes to a different key")
            pruned = new_work.prune_others()

            ok(pruned == 1, "prune_others() reports the one stale key it removed",
               "got %d" % pruned)
            ok(not old_work.dir.exists(), "the old key's work area is gone")
            ok(demo_record.WORK_ROOT.is_dir(), "WORK_ROOT itself survives the prune")
        finally:
            demo_record.WORK_ROOT = original_root


def _find_shipping_post_index(home: Path, root: Path) -> int:
    """The 1-based call index of the `/shipping/batches` POST in one full, uninterrupted
    sweep — found empirically rather than hand-counted, so a change elsewhere in
    `sweep()`'s call order cannot make the kill point below silently mean something else."""
    probe = demo_record.WorkArea(home)
    probe.dir = root / "work-probe"
    _recorded, _stats, server = _sweep(probe, home, server_cls=StatefulFakeServer)
    for index, call in enumerate(server.log, start=1):
        if call == ("POST", "/shipping/batches"):
            return index
    raise AssertionError("the fixture sweep never called POST /shipping/batches")


def _shipping_unit_is_not_split_by_a_kill() -> None:
    """(f) A kill between the shipping POST and its dependent GET must never leave the
    POST cached alone: the resumed run's server is a NEW instance
    (`StatefulFakeServer`) that has never heard of the old batch id, so trusting the
    stale POST would strand its GET forever."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        home = root / "home"
        _write_store(home, b"snapshot-shipping")
        post_index = _find_shipping_post_index(home, root)

        work = demo_record.WorkArea(home)
        work.dir = root / "work"
        try:
            _sweep(work, home, kill_after=post_index, server_cls=StatefulFakeServer)
            ok(False, "the kill lands right after the POST, before its dependent GET")
        except Interrupted:
            pass

        landed = work.load()
        shipping_keys = [k for k in landed if "shipping/batches" in k]
        ok("POST /shipping/batches" not in landed,
           "(f) a POST with no completed dependent GET is never cached alone",
           "got %r" % shipping_keys)

        # Resume with a FRESH instance — a new process, an empty batch table.
        recorded, _stats, _server = _sweep(work, home, server_cls=StatefulFakeServer)
        posted = recorded.get("POST /shipping/batches")
        ok(posted is not None, "the whole unit is reissued and lands on resume",
           "got %r" % posted)
        batch = (posted or {}).get("body", {}).get("batch")
        get_key = "/shipping/batches/%s" % batch if batch else None
        ok(get_key is not None and get_key in recorded,
           "the resumed GET matches the resumed POST's own (new) batch id, not a stale one",
           "got %r" % get_key)


def main() -> int:
    _save_is_atomic_no_tmp_survives()
    _key_reflects_prices_json_too()
    _resume_skips_and_matches_a_clean_run()
    _corrupted_route_file_is_rerecorded()
    _changed_snapshot_starts_fresh()
    _work_area_scrubs_before_it_writes_to_disk()
    _stale_keys_are_pruned()
    _shipping_unit_is_not_split_by_a_kill()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
