"""`pkmnscan match` — set up the free reader. `status` is free. `prepare` downloads and reads.

The reading itself is `pkmnscan identify --engine marqo-b`. This command is only the one-time
preparation that reader needs, and it is the ONLY place a model file is downloaded or a stock
photograph is read (D301's one exception: each image is read once, in memory, and only its
fingerprint is kept). Nothing starts it on its own: the owner presses Prepare on the runs sheet,
which runs this as a detached child exactly as a paid press runs `identify`.

  match status      what is ready: the model file, the fingerprints, how many printings have no
                    stock photo. Free. No model is loaded.
  match prepare     1. download the pinned model file from its release asset, if it is absent;
                    2. read each stock image of every set the store holds cards for, plus every
                       Riftbound set, once, and keep the fingerprint.
                    Resumable: a stopped run carries on, a refresh reads only what is new, and a
                    printing that had no photo is asked about again (a set that has just released
                    gains its images). It never spends money and it never touches card state.

PROGRESS IS A FILE, `inventory/match-prepare.json`, so the screen polls the same way it polls a
run directory and the work outlives the server that started it.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import time
from typing import Callable, Dict, Optional

from pathlib import Path

from identify import match, sweep
from pipeline import join
from store import db
from store import files as store_files
from store import photos
from store.cache import ENGINE_MATCHER
from store.session import Store

# How many cards one transaction of the background reader covers. Small, so a capture that
# arrives is noticed within a second or two and the store lock is held for a moment.
SWEEP_CHUNK = 8


def _write_progress(state: str, phase: str, done: int, total: int, message: str = "", started: Optional[float] = None) -> None:
    store_files.write_json(
        match.progress_path(),
        {
            "state": state,  # running | done | failed
            "phase": phase,  # model | fingerprints
            "done": done,
            "total": total,
            "message": message,
            "pid": os.getpid(),
            "started": started,
            "at": time.time(),
        },
    )


def _status(args, say) -> int:
    state = match.status()
    say(f"model file      {'ready' if state['model_ok'] else ('present but not the pinned file' if state['model_present'] else 'not downloaded')} "
        f"({state['model_bytes'] / 1_000_000:.0f} MB, {match.MODEL_FILENAME})")
    say(f"fingerprints    {state.get('fingerprints', 0)} stock photos in {state.get('sets', 0)} set(s); "
        f"{state.get('no_image', 0)} printing(s) with no stock photo")
    say(f"index           {'built by the pinned model file' if state['index_current'] else ('built by another model file' if state['index_present'] else 'not built')}")
    say(f"ready           {'yes' if state['ready'] else 'no'}")
    if getattr(args, "json", False):
        say(json.dumps(state, sort_keys=True))
    return 0


def _store_pairs():
    cards = Store().read().inventory.cards.values()
    return sorted({(str(c.game or "pokemon"), str(c.set_name)) for c in cards if getattr(c, "set_name", None)})


def prepare(
    say: Callable[[str], None],
    *,
    model_only: bool = False,
    fingerprints_only: bool = False,
) -> int:
    from pipeline import pricehistory
    from pipeline.stockimages import StockImages
    from cli.cmd_pricearchive import market_cache_dir

    started = time.time()
    try:
        if not fingerprints_only:
            # A HALF FILE FROM A DEAD DOWNLOAD IS NOT THE MODEL and is 372 MB at worst. Every
            # Prepare clears it first, whether or not the model itself is already here.
            match.model_path().with_name(match.MODEL_FILENAME + ".part").unlink(missing_ok=True)
        if not fingerprints_only and not match.model_ready():
            say(f"downloading the model file ({match.MODEL_BYTES / 1_000_000:.0f} MB) from {match.MODEL_URL}")
            last = [0.0]

            def tick(done: int, total: int) -> None:
                if time.time() - last[0] >= 1.0:
                    last[0] = time.time()
                    _write_progress("running", "model", done, total, "Downloading the model file", started)

            match.download_model(progress=tick)
            say("model file      downloaded and checked")
        elif not fingerprints_only:
            say("model file      already here and checked")
        if model_only:
            _write_progress("done", "model", 1, 1, "The model file is ready", started)
            return 0
        if not match.model_ready():
            raise match.ModelDownloadError("The model file is not here. Prepare it first.")

        stock = StockImages(market=pricehistory.Market(cache_dir=market_cache_dir()))
        targets = match.targets_for(stock, _store_pairs())
        say(f"fingerprints    {len(targets)} set(s) to read")
        _write_progress("running", "fingerprints", 0, len(targets), "Reading stock photos", started)
        with match.Index() as index:
            report = match.build_index(
                index, targets, stock, log=say,
                progress=lambda done, total, name: _write_progress("running", "fingerprints", done, total, name, started),
            )
        say(f"fingerprints    {report.embedded} read, {report.skipped} already held, "
            f"{report.no_image} with no stock photo, {report.unreadable} could not be read")
        for name in report.unresolved:
            say(f"                not found in the catalogue: {name}")
        _write_progress("done", "fingerprints", 1, 1, "The free reader is ready", started)
        return 0
    except (match.ModelDownloadError, match.IndexError_) as exc:
        say(str(exc))
        _write_progress("failed", "model" if isinstance(exc, match.ModelDownloadError) else "fingerprints", 0, 0, str(exc), started)
        return 1


class _Session:
    """What one worker keeps between chunks: the parsed export per path (so a lock held per chunk
    never pays a CSV parse), the set names each export holds, each file's (mtime, size) as parsed,
    and the run its adopted cards belong to."""

    # ponytail: a run closes at this many cards, so a chunk re-joins at most this many (one run per
    # worker session would re-join every card the session ever adopted, under the lock).
    RUN_CARDS = 64

    def __init__(self) -> None:
        self.parsed: dict = {}
        self.sets: dict = {}
        self.stamp: dict = {}
        self.run = None
        self.keys: list = []
        self.fresh = False  # the run was created by this worker and holds no joined card yet
        self.resumed = False
        self.recover = False  # the open run's last join did not finish: its cards join again

    def resume(self, store) -> None:
        """Pick up the newest `match-sweep` run while it holds fewer than `RUN_CARDS` cards (a
        worker lives for one queue, so a run per worker would be a run per chunk). A run whose
        manifest is not `joined` was cut short between the store write and its record: its cards
        that are still identified join again with the next chunk (`recover`). Never creates."""
        from cli import runs

        if self.resumed:
            return
        self.resumed = True
        for directory in sorted(store_files.runs_dir().glob("*-match-sweep-*"), reverse=True)[:1]:
            run = runs.open_run(directory)
            keys = list((run.manifest.get("selection") or {}).get("keys") or [])
            cards = store.read().inventory.cards
            held = [k for k in keys if k in cards and cards[k].state != "captured"]
            if len(held) < self.RUN_CARDS:
                self.run, self.keys = run, held
                self.recover = bool(held) and not run.manifest.get("joined")

    def open_run(self):
        """The run the next chunk's cards join into, created when none is open or it is full."""
        from cli import runs

        if self.run is None or len(self.keys) >= self.RUN_CARDS:
            self.run = runs.create("match-sweep")
            self.keys, self.fresh = [], True
        return self.run

    def drop_empty_run(self) -> None:
        """A run this worker created and never joined a card into (every prep aborted) is
        removed, so the runs sheet never lists an empty unjoined run."""
        if self.fresh and self.run is not None and not self.keys:
            shutil.rmtree(self.run.directory, ignore_errors=True)
            self.run = None
        self.fresh = False


def _export_for(game: str):
    """The newest export this game holds whose scope note covers the whole category, or None,
    with NO age limit (owner's ruling). The 900 s rule belongs to a press, because an export is
    also a price reading (D166); the reader only uses the file to name and adopt cards, and dates
    everything it writes from it to the file's own mtime. `pipeline_routes._held_exports` orders
    them and `_covers` is the press's own scope test. A narrower file is never used: it would
    queue a card of a set it lacks as `no_catalog_row`."""
    from server import pipeline_routes, tcg_export
    from pipeline import games

    category = games.get(game).get("tcgplayer_category_id")
    if category is None:
        return None
    scope = tcg_export.Scope(category_id=int(category))
    for path in pipeline_routes._held_exports(game):
        note = pipeline_routes._read_note(path)
        if note is not None and pipeline_routes._covers(note, scope):
            return path
    return None


def _still_here(inventory, card, key) -> bool:
    """THE CARD MAY HAVE CHANGED WHILE IT WAS READ: gone, no longer captured, re-shot (a new
    capture id) or renamed (a new cid). Then the answer is about bytes that no longer stand there."""
    now = inventory.cards.get(key)
    return (
        now is not None
        and now.state == "captured"
        and now.capture_id == card.capture_id
        and now.cid == card.cid
    )


def _adopt(target, accepted, meta, paths, session, *, rehearsal=False):
    """THE ADOPTION, ONE FUNCTION FOR BOTH ITS CALLERS: the prep runs it on a read snapshot
    (nothing flushes it) and the lock runs it on the writable one. Bank each accepted answer, then
    take it onto the card as a press does (`cmd_identify._adopt_cached`, `record_adopted`).
    Returns the keys adopted. A card is not adopted when no reusable export exists for its game,
    or its set hint names no set the export holds: a press names those, never a guess."""
    from cli import cmd_identify
    from identify import sidecar
    from pipeline import games, setnames

    adopted = []
    for result in accepted:
        card, _capture_id, digest, photo = meta[result.key]
        target.cache.put(
            result.key, result.payload, digest, match.MODEL_SHA256,
            engine=ENGINE_MATCHER, cid=card.cid,
        )
        game = str(card.game or games.DEFAULT_GAME)
        if game not in paths:
            continue
        now = target.inventory.cards[result.key]
        if now.set_hint and setnames.resolve(now.set_hint, session.sets[paths[game]]) is None:
            continue
        item = cmd_identify.Item(
            capture=sidecar.Capture(
                photo=photo, box=now.box, index=now.index, set_hint=now.set_hint, game=now.game,
                metadata_finish=tuple(now.metadata_finish) if now.metadata_finish else None,
            ),
            photo_sha256=digest, game=game, strategy=str(games.get(game)["prompt"]),
        )
        if rehearsal:
            item.identification = dict(result.payload)
        else:
            cmd_identify._adopt_cached(item, target.cache.get(result.key), {})
        if cmd_identify.record_adopted(target, item, session.open_run().name):
            adopted.append(result.key)
    return adopted


def _stamp(path):
    st = path.stat()
    return st.st_mtime_ns, st.st_size


def _write_chunk(store, results, meta, noted, *, adopt: bool, session: "_Session") -> int:
    """ONE `Store.write` for one chunk, holding the lock only for writes. Every card the reader
    ACCEPTS gets the press's own adoption (`_adopt`) and then the join's own write
    (`cmd_join.apply_join`), so a free match is `identified` as a paid read is. A card the ladder
    cannot settle lands in review as a press leaves it. An unaccepted card is only noted as tried.

    THE JOIN'S READS HAPPEN BEFORE THE LOCK OPENS: the export parse, the catalog and the ladder
    (`resolve.load_from_store` over a read snapshot with the adoption applied to it in memory), and
    which SKU rows the export would change. The lock replays the adoption, re-checks that every
    card is still `captured` under the same capture id and that the export is still the file the
    prep read, and applies the prepared join. A card or export that moved sends the chunk back to
    the prep, twice at most, then it only banks the answers. After the lock closes the run gets a
    press's join record (corpus seed, `pricing.json`, manifest). Returns how many were accepted."""
    from cli import cmd_join, resolve, runs
    from pipeline import corpus, games, pricing, routing, skus as skus_walk, tcgcsv

    paths: dict = {}
    stamps: dict = {}
    if adopt:
        session.resume(store)
        wanted = {str(meta[r.key][0].game or games.DEFAULT_GAME) for r in results if r.accepted}
        if session.recover:
            cards = store.read().inventory.cards
            wanted |= {str(cards[k].game or games.DEFAULT_GAME) for k in session.keys}
        for game in wanted:
            if (path := _export_for(game)) is not None:
                paths[game] = path
    threshold = pricing.check_threshold(corpus.Corpus.read().policy_for(None)["threshold"]) if paths else None

    for attempt in range(3):
        live = [r for r in results if r.accepted and r.payload is not None]
        resolved, fold, run = None, {}, None
        if paths and (live or session.recover) and attempt < 2:
            for path in paths.values():  # EACH PREP READS THE FILE AS IT NOW STANDS, and the lock re-checks against that
                stamps[path] = _stamp(path)
                if session.stamp.get(path) != stamps[path]:
                    export = tcgcsv.read_export(path)
                    session.parsed[path] = (export, runs.describe_source(path))
                    session.sets[path] = sorted({str(r.get(tcgcsv.SET_COLUMN) or "") for r in export.rows} - {""})
                    session.stamp[path] = stamps[path]
            snap = store.read()
            ready = [r for r in live if _still_here(snap.inventory, meta[r.key][0], r.key)]
            adopted = _adopt(snap, ready, meta, paths, session, rehearsal=True)
            if adopted or session.recover:
                run = session.open_run()
                resolved = resolve.load_from_store(
                    run, session.keys + adopted, paths, threshold=threshold,
                    rule=pricing.MATCH, basis=pricing.BASIS_MARKET, review_below=routing.CONFIDENCE_LOW,
                    snapshot=snap, export_cache=session.parsed,
                )
                book, _added, _written, choice = cmd_join.seed_corpus(run, resolved, write=False)
                skus_snap = store.read().skus
                for game_join in resolved.joins.values():
                    path = Path(str(game_join.source["path"]))
                    at, name = cmd_join._skus_stamp(game_join.source)
                    fold[path] = skus_walk.changed_rows(session.parsed[path][0].rows, at=at, source=name, skus=skus_snap)
        accepted = 0
        if resolved is not None:
            # THE INTENT, BEFORE THE LOCK: these keys are the run's, and it is not joined until its
            # record is written. A kill after the store write leaves a run the next worker finishes.
            run.set(selection={"keys": session.keys + adopted}, joined=False)
        with store.write() as writable:
            if resolved is not None and (
                any(_stamp(p) != stamps[p] for p in paths.values())
                or [r.key for r in ready if not _still_here(writable.inventory, meta[r.key][0], r.key)]
            ):
                continue  # something moved since the prep: nothing written, prepare again
            ok = [r for r in (ready if resolved is not None else live)
                  if _still_here(writable.inventory, meta[r.key][0], r.key)]
            for result in results:
                if not (result.accepted and result.payload is not None) and _still_here(
                    writable.inventory, meta[result.key][0], result.key
                ):
                    noted[result.key] = meta[result.key][1]
            accepted = len(ok)
            if resolved is not None:
                keys = _adopt(writable, ok, meta, paths, session)
                source = {Path(str(g.source["path"])): g.source for g in resolved.joins.values()}
                cmd_join.apply_join(writable, resolved, fold, source)
                # DATED TO THE EXPORT, NEVER TO NOW: the oldest file joined, so the pricing screens see its true age.
                at = min(int(Path(str(g.source["path"])).stat().st_mtime) for g in resolved.joins.values())
                table = cmd_join._pricing_table(run, resolved, choice, writable)
                cmd_join.record_readings(writable, run, table, at)
                session.keys = session.keys + [k for k in keys if k not in session.keys]
            else:
                _adopt(writable, ok, meta, {}, session)
        break
    if resolved is not None:
        # FILES, OUTSIDE ANY LOCK, each safe to write again: `resume` finishes a run whose record
        # is missing, and the join over the same keys writes the same files.
        cmd_join.seed_corpus(run, resolved)
        cmd_join.write_pricing_table(run, table, at)
        run.set(selection={"keys": list(session.keys)})
        cmd_join.record_join(run, resolved, routing.CONFIDENCE_LOW)
        session.recover = False
    session.drop_empty_run()
    return accepted


def sweep_worker(say) -> int:
    """The background reader's worker (`identify/sweep.py` starts it): read the queue, then exit.

    It loads the model once and reads the waiting cards a few at a time until the queue is empty,
    the switch is off or it is sent SIGTERM. For each card it ACCEPTS it writes an `identifications`
    row with engine `marqo-b` (`Cache.put`, which never overwrites a Haiku or a cleared row) and
    then adopts it as a press does: the card is `identified`, joined against the game's export and
    routed (`_write_chunk`). It never spends. A card it cannot accept is remembered as tried
    against this photograph and waits for a press.

    EXIT CODES the watcher reads: 0 done, 3 "not ready" (no model file or index, or a runtime that
    cannot load: numpy or onnxruntime missing), 1 a crash. Before each chunk it records the cards
    in `match-sweep-inflight.json`, so a crash that leaves no Python exception behind (an
    out-of-memory kill) still halves the next chunk and, alone, sets the card aside: it cannot loop."""
    from pipeline import games

    sweep.settle_inflight()
    if not match.status()["ready"]:
        say("sweep           the model file or the fingerprints are not ready; nothing read")
        return sweep.EXIT_NOT_READY
    os.nice(10)  # the capture server and the feeder come first
    stop = []
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop.append(True))
    store = Store()
    accepted = tried = 0
    session = _Session()
    try:
        with match.Index() as index:
            sweep.set_blocked(None)
            while not stop:
                conn = db.open_read_only(db.path(store_files.inventory_dir()))
                try:
                    if not db.match_sweep_on(conn):
                        break
                    waiting = sweep.queue(conn, limit=sweep.chunk_limit(SWEEP_CHUNK))
                finally:
                    conn.close()
                if not waiting:
                    break
                sweep.mark_inflight(dict(waiting))
                inventory = store.read().inventory
                requests, meta = [], {}
                noted: Dict[str, str] = {}
                for key, capture_id in waiting:
                    card = inventory.cards.get(key)
                    path = photos.find(card.cid) if card is not None else None
                    if card is None or path is None:
                        noted[key] = capture_id  # nothing to read now; a re-shoot changes the id
                        continue
                    game = str(card.game or games.DEFAULT_GAME)
                    requests.append(match.Request(
                        key=key, photo=path, game=game,
                        strategy=str(games.get(game)["prompt"]), set_hint=card.set_hint,
                    ))
                    meta[key] = (card, capture_id, photos.sha256_of(path), path)
                results = match.read(requests, index) if requests else []
                before = dict(noted)
                try:
                    accepted += _write_chunk(store, results, meta, noted, adopt=True, session=session)
                except join.EmptyCatalog:
                    # THE EXPORT CANNOT ANSWER THIS CHUNK: nothing was written (the write rolled
                    # back). Bank the answers only, as before; a press adopts them.
                    noted.clear()
                    noted.update(before)
                    accepted += _write_chunk(store, results, meta, noted, adopt=False, session=session)
                sweep.remember_tried(noted)
                sweep.clear_inflight()
                sweep.reset_chunk()
                tried += len(noted)
    except ImportError as exc:
        # A MISSING RUNTIME is "not ready", not a crash: the watcher waits 300 s and says why.
        say(f"sweep           the reader's runtime is not installed ({exc.name or exc}); nothing read")
        sweep.clear_inflight()
        sweep.set_blocked("runtime_missing")
        return sweep.EXIT_NOT_READY
    except Exception as exc:  # noqa: BLE001
        # THE CHUNK HALVES (a lone card is set aside), so one bad photograph cannot take the next worker down.
        say(f"sweep           stopped by {type(exc).__name__}: {exc}")
        sweep.settle_inflight(crashed=True)
        return 1
    say(f"sweep           {accepted} matched, {tried} left for a press")
    return 0


def _disagrees(card, payload) -> bool:
    """The free pick names another card than the filed one: a different number, or a name that
    matches nothing the filed name stands for (`join.name_disputes`, the join's own test)."""
    from pipeline import tcgcsv

    if join.number_index_key(payload.get("number")) != join.number_index_key(card.read_number):
        return True
    return join.name_disputes(payload.get("name"), [{tcgcsv.NAME_COLUMN: card.read_name}])


def audit(say, *, write: bool = False) -> int:
    """`match audit [--write]`: the free reader over every card with a photo and an identity,
    with or without a SKU. Never spends. READS FIRST, NO LOCK (D88); the lock is taken once, for
    the write only, and re-checks each card is still the one that was read. A card the reader
    cannot accept is counted "not checked", never a disagreement. In stock goes to Review as
    `free_reader_disagrees` with its photo; sold is only listed."""

    if not match.status()["ready"]:
        say("match audit    not ready: the model file or the fingerprints are missing. Run `match prepare`.")
        return sweep.EXIT_NOT_READY
    lock = sweep.acquire_lock()  # the sweep's own lock: the two never load the model together
    if lock is None:
        say("match audit    the background reader is running and holds the model. Turn the Rig switch off, or wait, then run it again.")
        return 1
    try:
        return _audit_locked(say, write)
    finally:
        lock.close()


def _audit_locked(say, write: bool) -> int:
    from pipeline import games
    from pipeline.routing import FREE_READER_DISAGREES
    from store import master
    from store.queues import QueueEntry

    os.nice(10)  # the sweep's own level: the capture server and the feeder come first
    snapshot = Store().read()
    inventory, in_review = snapshot.inventory, set(snapshot.review.entries)
    requests, meta = [], {}
    for key, card in sorted(inventory.cards.items()):
        path = photos.find(card.cid) if card.cid else None
        if path is None or not card.read_name or not card.read_number:
            continue
        game = str(card.game or games.DEFAULT_GAME)
        requests.append(match.Request(key=key, photo=path, game=game, strategy=str(games.get(game)["prompt"]), set_hint=card.set_hint))
        meta[key] = (card, path)
    started = time.time()
    try:
        with match.Index() as index:
            results = match.read(requests, index) if requests else []
    except ImportError as exc:
        say(f"match audit    not ready: the reader's runtime is not installed ({exc.name or exc})")
        return sweep.EXIT_NOT_READY
    per_card = (time.time() - started) / len(requests) if requests else 0.0
    unchecked, found, skipped = {}, [], 0
    for result in results:
        card, path = meta[result.key]
        if not (result.accepted and result.payload is not None):
            code = str(result.code or "unread")
            unchecked[code] = unchecked.get(code, 0) + 1
            continue
        bad = _disagrees(card, result.payload)
        gone = card.state in master.TERMINAL_STATES
        held = result.key in in_review
        say(f"{result.key:<8} {'disagree' if bad else 'agree':<9} filed {card.sku or 'no SKU'} as {card.read_name} {card.read_number}"
            + (f"; free read {result.payload.get('name')} {result.payload.get('number')}" if bad else "")
            + (f"; {card.state}" if gone else "") + ("; already in review" if bad and not gone and held else ""))
        if bad and not gone:
            if held:
                skipped += 1  # a card already in review keeps its entry, whatever the reason
            else:
                found.append((result, card, path))
    queued = 0
    if write and found:
        with Store().write() as writable:  # the only lock, held for the write alone
            for result, card, path in found:
                now = writable.inventory.cards.get(result.key)
                if (now is None or now.state in master.TERMINAL_STATES or now.cid != card.cid
                        or (now.read_name, now.read_number) != (card.read_name, card.read_number)
                        or result.key in writable.review.entries):
                    continue  # changed since the read: the answer is about another card or photograph
                payload = result.payload
                queued += writable.review.upsert(QueueEntry(
                    position=result.key, box=now.box, index=now.index,
                    label=join.place_text(now.game or games.DEFAULT_GAME, join.Position(box=now.box, index=now.index)),
                    photo=now.photo or str(path),
                    read={"name": payload.get("name"), "number": payload.get("number"),
                          "printed_total": payload.get("printed_total"), "set_hint": now.set_hint},
                    confidence=now.confidence, reason=FREE_READER_DISAGREES, market=None,
                    candidates=[{"name": payload.get("name"), "number": payload.get("number"),
                                 "printed_total": payload.get("printed_total"), "found_by": "free_reader"}],
                ))
    why = ", ".join(f"{code} {n}" for code, n in sorted(unchecked.items()))
    say(f"match audit    {len(requests)} read, {sum(unchecked.values())} not checked" + (f" ({why})" if why else "")
        + f", {len(found)} in stock disagree, {skipped} already in review, "
        f"{queued} queued for Review ({per_card:.2f} s per card)"
        + ("" if write else "; nothing written, add --write to queue them"))
    return 0


def run(args, say) -> int:
    if getattr(args, "sweep_worker", False):
        return sweep_worker(say)
    if getattr(args, "sweep", False):
        return sweep.watch_main([])
    action = getattr(args, "match_action", None)
    if action == "status":
        return _status(args, say)
    if action == "prepare":
        return prepare(
            say,
            model_only=bool(getattr(args, "model_only", False)),
            fingerprints_only=bool(getattr(args, "fingerprints_only", False)),
        )
    if action == "audit":
        return audit(say, write=bool(getattr(args, "write", False)))
    say("usage: pkmnscan match status | prepare [--model-only | --fingerprints-only] | audit [--write] | --sweep")
    return 64
