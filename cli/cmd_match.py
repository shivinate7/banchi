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
import signal
import time
from typing import Callable, Dict, Optional

from identify import match, sweep
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


def sweep_worker(say) -> int:
    """The background reader's worker (`identify/sweep.py` starts it): read the queue, then exit.

    It loads the model once, reads the waiting cards a few at a time, and stops at the next
    capture or the next SIGTERM, whichever comes first. It writes one thing, an `identifications`
    row with engine `marqo-b`, through `Cache.put`, which never overwrites a Haiku or a cleared
    row. It never writes card state, and it never spends. A card it cannot accept is remembered as
    tried against this photograph and waits for a press."""
    from pipeline import games

    if not match.status()["ready"]:
        say("sweep           the model file or the fingerprints are not ready; nothing read")
        return sweep.EXIT_NOT_READY
    os.nice(10)  # the capture server and the feeder come first
    stop = []
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop.append(True))
    store = Store()
    started = time.time()
    accepted = tried = 0
    with match.Index() as index:
        while not stop:
            conn = db.open_read_only(db.path(store_files.inventory_dir()))
            try:
                if sweep.newest_capture(conn) > started or not db.match_sweep_on(conn):
                    break
                waiting = sweep.queue(conn, limit=SWEEP_CHUNK)
            finally:
                conn.close()
            if not waiting:
                break
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
                meta[key] = (card, capture_id, photos.sha256_of(path))
            results = match.read(requests, index) if requests else []
            with store.write() as writable:
                for result in results:
                    card, capture_id, digest = meta[result.key]
                    now = writable.inventory.cards.get(result.key)
                    # THE CARD MAY HAVE CHANGED WHILE IT WAS READ: gone, no longer captured, or
                    # re-shot. Then this answer is about bytes that no longer stand there.
                    if now is None or now.state != "captured" or now.capture_id != card.capture_id:
                        continue
                    if result.accepted and result.payload is not None:
                        writable.cache.put(
                            result.key, result.payload, digest, match.MODEL_SHA256,
                            engine=ENGINE_MATCHER, cid=card.cid,
                        )
                        accepted += 1
                    else:
                        noted[result.key] = capture_id
            sweep.remember_tried(noted)
            tried += len(noted)
    say(f"sweep           {accepted} matched, {tried} left for a press")
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
    say("usage: pkmnscan match status | prepare [--model-only | --fingerprints-only] | --sweep")
    return 64
