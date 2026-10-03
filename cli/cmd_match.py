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
import time
from pathlib import Path
from typing import Callable, Optional

from identify import match
from store import files as store_files
from store.session import Store


def progress_path() -> Path:
    return store_files.inventory_dir() / "match-prepare.json"


def _write_progress(state: str, phase: str, done: int, total: int, message: str = "", started: Optional[float] = None) -> None:
    store_files.write_json(
        progress_path(),
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


def run(args, say) -> int:
    action = getattr(args, "match_action", None)
    if action == "status":
        return _status(args, say)
    if action == "prepare":
        return prepare(
            say,
            model_only=bool(getattr(args, "model_only", False)),
            fingerprints_only=bool(getattr(args, "fingerprints_only", False)),
        )
    say("usage: pkmnscan match status | prepare [--model-only | --fingerprints-only]")
    return 64
