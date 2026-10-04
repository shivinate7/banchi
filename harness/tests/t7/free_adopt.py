"""T7 group: a free match makes the card identified, as a paid read does (owner's ruling).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). The ruling: the background reader
(`cli/cmd_match.py:sweep_worker`) adopts every card it ACCEPTS through the press's own path
(`cli/cmd_identify.py:_adopt_cached` and `record_identification`, then the catalog join), so an
accepted card is `identified` with no press. An unaccepted card stays `captured` for a press's
paid second look. Nothing spends.

THE TWIN. The press path is the oracle: a second throwaway store, the same three cards, the
same fake matcher answers, read by `cmd_identify.run` (the press) and then `cmd_join.run`. What
the press leaves behind is what the sweep must leave behind. Nothing here loads the model or
touches the network: the matcher, the clock and the paid batch are fakes.

THE CARDS (fixtures/sv09_export_untouched.csv, SV09):
    A  Articuno 161/159, one stocked finish        the ladder settles it
    B  Dunsparce 120/159, normal and reverse       no claim, so `ambiguous_no_signal`
    C  Dunsparce 120/159, the matcher passes on it  stays `captured` for the paid second look
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from harness.tests import Checks
from harness.tests.t7 import engine_sweep
from harness.tests.t7.common import (
    FIXTURE_EXPORT,
    capture_payload,
    isolated_home,
    quiet,
)
from pipeline import tcgcsv
from identify import batch, match, prompt
from identify import images as identify_images
from server import capture_server
from store import cache as cache_mod
from store import files, master
from store import session as store_session
from store.session import Store

MATCHER, HAIKU = cache_mod.ENGINE_MATCHER, cache_mod.ENGINE_HAIKU
ARTICUNO = {"name": "Articuno", "number": "161", "printed_total": "159", "finish": "unknown", "confidence": "high"}
DUNSPARCE = {"name": "Dunsparce", "number": "120", "printed_total": "159", "finish": "unknown", "confidence": "high"}
AMBIGUOUS = "ambiguous_no_signal"
_N = iter(range(1, 10_000))


def _jpeg() -> bytes:
    """A real, distinct JPEG: the press prepares a card it sends to the paid batch."""
    n = next(_N)
    out = io.BytesIO()
    identify_images.Image.new("RGB", (64, 89), (n * 7 % 256, n * 13 % 256, n * 29 % 256)).save(out, "JPEG")
    return out.getvalue()


def _shoot(said: dict, hint: str = "SV09") -> str:
    """One captured Pokemon card hinted to `hint`, through the real route. Returns its key."""
    before = set(Store().read().inventory.cards)
    body = capture_payload(3, capture_id=f"adopt-{next(_N)}", game="pokemon", set_hint=hint)
    body["image"] = base64.b64encode(_jpeg()).decode("ascii")
    capture_server.do_capture(body)
    return next(iter(set(Store().read().inventory.cards) - before))


def _seed_export(*, blank_market: str = "", age: float = 0.0) -> Path:
    """The fixture export where the reader looks for one: `inventory/.exports/<game>/`.

    A scope note sits beside it (the shape `pipeline_routes._write_note` writes: the whole
    Pokemon category, no set narrowing), so a reader that reuses only covered, fresh exports
    finds it too."""
    folder = files.inventory_dir() / files.EXPORTS_DIRNAME / "pokemon"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "export-tcgplayer-adopt-fixture.csv"
    shutil.copyfile(FIXTURE_EXPORT, target)
    if blank_market:  # a catalog row with no market price: an UNPRICED SKU
        table = tcgcsv.read_export(FIXTURE_EXPORT)
        rows = [dict(r, **{tcgcsv.MARKET_PRICE_COLUMN: ""}) if r["TCGplayer Id"] == blank_market else r for r in table.rows]
        tcgcsv.write_csv(target, table.header, rows)
    if age:  # `pipeline_routes._reusable` reuses an export up to EXPORT_REUSE_S (900 s) old
        stamp = time.time() - age
        os.utime(target, (stamp, stamp))
    Path(str(target) + ".scope.json").write_text(
        json.dumps({"game": "pokemon", "category_id": 3, "set_ids": [], "scope": "category",
                    "widened": True, "bytes": target.stat().st_size, "at": master.now()}),
        "utf-8",
    )
    return target


def _results(keys, accepted: dict):
    """The fake matcher: `accepted` maps a key to its answer; every other key is passed on."""
    def read(requests, _index=None, *_a, **_k):
        return [
            match.Result(r.key, True, dict(accepted[r.key], engine=MATCHER), margin=0.2, floor=0.95)
            if r.key in accepted
            else match.Result(r.key, False, None, match.UNREAD_MARGIN, margin=0.03, floor=0.9)
            for r in requests
        ]
    return read


@contextmanager
def _fake_matcher(read):
    with mock.patch.object(match, "status", lambda *_a, **_k: {"ready": True}), \
            mock.patch.object(match, "Index", engine_sweep._FakeIndex), \
            mock.patch.object(match, "read", read), \
            mock.patch.object(os, "nice", lambda _n: 0), \
            mock.patch("signal.signal", lambda *_a: None):
        yield


def _sweep(read) -> int:
    """Run the background worker over the store's queue, once, under the fake matcher."""
    from cli import cmd_match

    engine_sweep._switch(True)
    reads = []

    def counted(requests, index=None, *a, **k):
        reads.append([r.key for r in requests])
        if len(reads) > 5:  # a queue that never empties ends as a red case, not a hang
            engine_sweep._switch(False)
        return read(requests, index, *a, **k)

    with _fake_matcher(counted), quiet():
        code = cmd_match.sweep_worker(lambda _line: None)
    assert code == 0, f"the worker exited {code}"
    return len(reads)


def _press(keys, accepted: dict, paid: dict):
    """The press: `identify --keys <keys> --engine marqo-b`, free first, a fake paid batch.

    Returns (keys sent to the paid batch, keys `record_identification` was called for,
    keys `_adopt_cached` was called for)."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify

    sent, recorded, adopted = [], [], []
    real_record, real_adopt = master.Inventory.record_identification, cmd_identify._adopt_cached
    (Path(os.environ[files.HOME_ENV]) / "captures" / "cards").mkdir(parents=True, exist_ok=True)

    def fake_batch(requests, log=None, on_submit=None):
        outcomes = {}
        for r in requests:
            sent.append(r.custom_id)
            outcomes[r.custom_id] = batch.Outcome(
                r.custom_id, batch.SUCCEEDED, identification=prompt.parse(dict(paid), r.strategy)
            )
        return batch.BatchRun(outcomes=outcomes)

    def record(self, key, **kw):
        recorded.append(key)
        return real_record(self, key, **kw)

    def adopt(item, entry, fingerprints):
        adopted.append(item.key)
        return real_adopt(item, entry, fingerprints)

    argv = ["identify", "--keys", ",".join(keys), "--engine", "marqo-b"]
    preflight = lambda requests, *_a, **_k: {  # noqa: E731
        "cards": len(requests), "can_read": len(requests), "unread": {}, "state": {"ready": True},
    }
    with _fake_matcher(_results(keys, accepted)), mock.patch.object(match, "preflight", preflight), \
            mock.patch.object(cmd_identify.batch, "run_batch", fake_batch), \
            mock.patch.object(master.Inventory, "record_identification", record), \
            mock.patch.object(cmd_identify, "_adopt_cached", adopt), quiet():
        code = cmd_identify.run(cli_entry.build_parser().parse_args(argv), lambda _l: None)
    assert code == 0, f"the press exited {code}"
    return sent, recorded, adopted


def _join(keys, export: Path) -> None:
    from cli import __main__ as cli_entry
    from cli import cmd_join

    argv = ["join", "--keys", ",".join(keys), "--export", str(export)]
    with quiet():
        code = cmd_join.run(cli_entry.build_parser().parse_args(argv), lambda _l: None)
    assert code == 0, f"the join exited {code}"


def _card(key: str) -> tuple:
    """What a reading leaves on a card. Not `run` (a press stamps its run; the reader has none)."""
    c = Store().read().inventory.cards[key]
    return (c.state, c.read_name, c.read_number, c.read_printed_total, c.confidence,
            c.detected_finish, c.name, c.number, c.printed_total)


def _review(keys) -> list:
    """The review queue's (position, reason) rows for these cards."""
    entries = Store().read().review.entries
    return sorted((k, entries[k].reason) for k in keys if k in entries)


def _skus() -> list:
    return sorted(str(s) for s in Store().read().skus.entries)


def _matches(keys, export: Path) -> dict:
    """`resolve.load_from_store`'s answer: SKU -> (positions, finish stage, market price)."""
    from cli import resolve, runs
    from pipeline import tcgcsv

    run = runs.Run(directory=files.runs_dir() / "adopt-probe", manifest={})
    resolved = resolve.load_from_store(run, list(keys), {"pokemon": export})
    return {
        sku: (sorted(f"{p.box}/{p.index}" for p in m.positions), list(m.stages), m.row[tcgcsv.MARKET_PRICE_COLUMN])
        for sku, m in sorted(resolved.matches.items())
    }


def _twin_home(accepted_for, paid):
    """The press path on a fresh store, run to the end (identify, then join). Returns what it left."""
    a, b, c = (_shoot(ARTICUNO), _shoot(DUNSPARCE), _shoot(DUNSPARCE))
    export = _seed_export()
    _press([a, b, c], {a: ARTICUNO, b: DUNSPARCE}, paid)
    _join([a, b, c], export)
    return {
        "cards": {k: _card(k) for k in (a, b)},
        "review": _review((a, b)),
        "skus": _skus(),
        "matches": _matches((a, b), export),
        "keys": (a, b, c),
    }


# ----------------------------------------------------------------------- 1, 2, 3, 4, 6 together


def check_free_match_identifies(checks: Checks) -> None:
    checks.note("")
    checks.note("FREE MATCH IS IDENTIFIED — the sweep adopts an accepted card as a press would")
    from cli import cmd_identify

    with isolated_home():
        twin = _twin_home(None, DUNSPARCE)
    a, b, c = twin["keys"]
    checks.equal(twin["cards"][a][0], master.IDENTIFIED, "(twin) the press identifies the settled card")
    checks.equal(twin["review"], [(b, AMBIGUOUS)], "(twin) the press sends only the unsettled card to review, as ambiguous_no_signal")
    checks.ok(a in {p for v in twin["matches"].values() for p in v[0]}, "(twin) the settled card is matched to a SKU")

    with isolated_home():
        a2, b2, c2 = (_shoot(ARTICUNO), _shoot(DUNSPARCE), _shoot(DUNSPARCE))
        checks.equal((a2, b2, c2), (a, b, c), "both stores hold the same three positions")
        export = _seed_export()
        c_before = repr(Store().read().inventory.cards[c])
        adopted = []
        real = cmd_identify._adopt_cached
        with mock.patch.object(cmd_identify, "_adopt_cached", lambda i, e, f: (adopted.append(i.key), real(i, e, f))[1]):
            _sweep(_results((a, b, c), {a: ARTICUNO, b: DUNSPARCE}))

        # 1. identified, with what a press gives
        checks.equal(_card(a)[0], master.IDENTIFIED, "1. a sweep-accepted card is `identified`, with no press")
        checks.equal(_card(a), twin["cards"][a], "1. and carries the reading a press records (name, number, finish, confidence)")
        checks.equal(_skus(), twin["skus"], "1. the SKU table holds what the press's join put there")
        checks.equal(_matches((a, b), export), twin["matches"], "1. SKU, finish rung and price match the press's, per SKU")
        checks.equal(sorted(adopted), sorted([a, b]), "1. the adoption ran through `cmd_identify._adopt_cached`, once per accepted card (one home)")

        # 2. the ladder cannot settle B: review, same reason, same state a press leaves
        checks.equal(_review((a, b)), twin["review"], "2. an accepted card the ladder cannot settle is in review with the press's reason")
        checks.equal(_card(b), twin["cards"][b], "2. and its card state is what a press leaves")

        # 3. an unaccepted card is untouched
        checks.equal(repr(Store().read().inventory.cards[c]), c_before, "3. an unaccepted card stays `captured`, byte for byte")
        checks.ok(_review((c,)) == [] and Store().read().cache.get(c) is None, "3. with no queue entry and no cache row")
        checks.ok(c in engine_sweep.sweep.tried(), "3. and is recorded as tried, for the press's paid second look")

        # 6. re-shoot of an adopted card
        a_before, b_before, review_before = _card(a), _card(b), _review((a, b))
        engine_sweep._reshoot(a)
        engine_sweep._reshoot(b)
        checks.equal((_card(a), _card(b)), (a_before, b_before), "6. a re-shot adopted card keeps its state and reading (`do_reshoot` leaves the record)")
        checks.equal(_review((a, b)), review_before, "6. and keeps its review entry")
        checks.ok(Store().read().cache.get(a) is None, "6. while its marqo-b row is dropped, as the re-shoot rule says")
        engine_sweep._switch(True)
        checks.ok(a not in engine_sweep._queue() and b not in engine_sweep._queue(), "6. an identified card is not queued for the reader again")


def check_press_after_sweep(checks: Checks) -> None:
    checks.note("")
    checks.note("PRESS AFTER SWEEP — bills the unaccepted card only, adopts nothing twice")
    with isolated_home():
        a, b, c = (_shoot(ARTICUNO), _shoot(DUNSPARCE), _shoot(DUNSPARCE))
        _seed_export()
        _sweep(_results((a, b, c), {a: ARTICUNO, b: DUNSPARCE}))
        checks.equal(_card(a)[0], master.IDENTIFIED, "(precondition) the sweep identified the accepted card")
        before = {k: repr(Store().read().inventory.cards[k]) for k in (a, b)}
        review_before = Store().read().review.entries[b].first_seen if b in Store().read().review.entries else None
        sent, recorded, _adopted = _press([a, b, c], {a: ARTICUNO, b: DUNSPARCE}, DUNSPARCE)
        checks.equal(len(sent), 1, "4. the press bills exactly one card: the one the reader passed on")
        checks.equal(recorded, [c], "4. and records an identification for that card only: the accepted ones are not written again")
        checks.equal({k: repr(Store().read().inventory.cards[k]) for k in (a, b)}, before, "4. the accepted cards are unchanged by the press")
        entry = Store().read().review.entries.get(b)
        checks.ok(entry is not None and entry.first_seen == review_before, "4. and the review entry the reader made is the one still there")


# ------------------------------------------------------------------------------ 5. the lock


def check_sweep_one_lock_per_chunk(checks: Checks) -> None:
    """MEASURE: count entries into `Store.write` while `sweep_worker` runs, against the number of
    `match.read` calls (one per chunk of `SWEEP_CHUNK`). The server is threaded, so a lock per
    card would hold every capture request behind the reader. Ten accepted cards are two chunks
    (8 and 2): the count must be 2, and every card must be identified by it."""
    checks.note("")
    checks.note("LOCK COST — one `Store.write` per chunk, never per card")
    with isolated_home():
        keys = [_shoot(ARTICUNO) for _ in range(10)]
        _seed_export()
        writes = []
        real = store_session.Store.write

        def counted(self, *a, **k):
            writes.append(1)
            return real(self, *a, **k)

        with mock.patch.object(store_session.Store, "write", counted):
            chunks = _sweep(_results(keys, {k: ARTICUNO for k in keys}))
        states = {Store().read().inventory.cards[k].state for k in keys}
        checks.equal(states, {master.IDENTIFIED}, "all ten accepted cards are identified by the sweep")
        checks.equal(chunks, 2, "ten cards are read in two chunks")
        checks.equal(len(writes), chunks, "and the worker enters `Store.write` once per chunk, not per card")


def _worklist() -> list:
    """`do_pipeline_worklist`'s SKU rows, minus what a run name or a photo digest would vary."""
    from server import pipeline_routes

    rows = pipeline_routes.do_pipeline_worklist([])["skus"] or []
    keep = ("sku", "bucket", "copies", "add_to_quantity", "backstock", "live_before", "committed",
            "copies_out", "nothing_to_add", "condition", "snap", "presets", "rule_price")
    return sorted(
        ({k: r.get(k) for k in keep} | {"at": sorted((p["box"], p["index"]) for p in r["positions"])} for r in rows),
        key=lambda r: r["sku"],
    )


def _unsent() -> list:
    """The unsent ledger the worklist's roster carries: copies owed per run, run name dropped."""
    from server import pipeline_routes

    roster = pipeline_routes.do_pipeline_worklist([])["roster"] or []
    return sorted(r["unsent"] for r in roster if r.get("unsent"))


def _corpus() -> dict:
    from pipeline import corpus

    return {sku: (a.value, a.channel) for sku, a in sorted(corpus.Corpus.read().answers.items())}


def _twin_pricing(blank: str):
    """The press, then the join, on a fresh store: what the worklist, the ledger and the corpus say."""
    a, b, c = (_shoot(ARTICUNO), _shoot(DUNSPARCE), _shoot(DUNSPARCE))
    export = _seed_export(blank_market=blank)
    _press([a, b, c], {a: ARTICUNO, b: DUNSPARCE}, DUNSPARCE)
    _join([a, b, c], export)
    return _worklist(), _unsent(), _corpus()


def check_adopted_card_is_priced(checks: Checks) -> None:
    checks.note("")
    checks.note("PRICING — a reader-adopted card is on the worklist, in the ledger and in the corpus as a press leaves it")
    for blank, label in (("", "a priced SKU"), ("8608859", "an unpriced SKU")):
        with isolated_home():
            twin = _twin_pricing(blank)
        checks.ok(bool(twin[0]) and bool(twin[1]), f"(twin, {label}) the press leaves a SKU on the worklist and copies in the unsent ledger")
        with isolated_home():
            a, b, c = (_shoot(ARTICUNO), _shoot(DUNSPARCE), _shoot(DUNSPARCE))
            _seed_export(blank_market=blank)
            _sweep(_results((a, b, c), {a: ARTICUNO, b: DUNSPARCE}))
            checks.equal(_worklist(), twin[0], f"1. {label}: the adopted card is on the worklist with the press twin's SKU, bucket, price and presets")
            checks.equal(_unsent(), twin[1], f"1. {label}: and the unsent ledger owes the twin's copies")
            checks.equal(_corpus(), twin[2], f"2. {label}: and the corpus holds the twin's answers (an unpriced SKU is seeded, not left out)")


def check_adoption_export_gate(checks: Checks) -> None:
    checks.note("")
    checks.note("EXPORT GATE — the reader adopts only on an export a press would reuse, covering the card's set")
    with isolated_home():
        a, b = _shoot(ARTICUNO), _shoot(DUNSPARCE)
        _seed_export(age=1000)  # past EXPORT_REUSE_S = 900
        _sweep(_results((a, b), {a: ARTICUNO, b: DUNSPARCE}))
        checks.equal({_card(k)[0] for k in (a, b)}, {master.CAPTURED}, "3. a stale export (1000 s old) adopts nothing: the cards wait for a press")
        checks.ok(_review((a, b)) == [] and _skus() == [], "3. and queue nothing, and fill no SKU table")
    with isolated_home():
        hinted, plain = _shoot(ARTICUNO, hint="SV10"), _shoot(ARTICUNO)
        _seed_export()  # holds SV09 only
        _sweep(_results((hinted, plain), {hinted: ARTICUNO, plain: ARTICUNO}))
        checks.equal(_card(hinted)[0], master.CAPTURED, "4. a card hinted into a set the export lacks (SV10) is not adopted")
        checks.equal(_card(plain)[0], master.IDENTIFIED, "4. while a card the export covers still is")


CHECKS = (
    check_free_match_identifies,
    check_press_after_sweep,
    check_sweep_one_lock_per_chunk,
    check_adopted_card_is_priced,
    check_adoption_export_gate,
)
