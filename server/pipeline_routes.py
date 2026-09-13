"""The pipeline seam — the four commands of batch script v2, reachable from a screen.

THIS IS THE FILE THAT BREAKS `capture_server.py`'s OLDEST PROMISE, and it does it on
purpose. That file's header said for months: *"no identification, no pricing, no UI. This
process never spends money: it holds no API key and makes no outbound call."* A route here
can CAUSE money to be spent, by starting a child that spends it — and the temptation, when
that landed, was to keep the promise alive by qualifying it to "no socket TO ANTHROPIC",
which is exactly the drift D16 exists to catch. It was rewritten instead.

BOTH HALVES ARE NOW FALSE OF THIS MODULE OUTRIGHT (D64). `POST /pipeline/runs/<name>/export`
reads the TCGplayer session cookie out of `.env` and fetches the operator's own Filtered
Export from `store.tcgplayer.com` — a secret, and a socket, in the file that used to be able
to say it had neither. What replaces THAT promise is stated where the call lives
(`server/tcg_export.py`) and is short: one host, three routes, all of them reads, and it
cannot cause a charge. This sentence said *one method, one route* until 2026-09-06, having
been copied from that file's own bullet on the day D65 made it false there; the count lives
in one place now and `make docs-audit`'s `transport promise` row is what keeps it there. The
route that can spend is still `POST /pipeline/identify` and is still named for it.

The owner asked for exactly this: *"how do i get api calls/pushing from our localhost
server so that i can actually push runs at box/section/whatever-level i want, get data
back, and manage CSVs?"* Until this file, the answer was that they could not — every run
this project has ever done was driven by an agent typing commands, which made the pipeline
the one capability in the product with no way in. `CLAUDE.md`'s route-is-not-a-feature rule
is about exactly that gap, pointed at the pipeline instead of at a server route.

WHAT REPLACES THE PROMISE, since a guarantee that is deleted and not replaced is a
regression:

  - **One route spends, and it is named for it.** `POST /pipeline/identify`. Everything
    else here is free and re-runnable, which is the property D1 gave the two-phase split
    and the reason `join`/`emit`/`reconcile` can run synchronously inside a request.
  - **It refuses without an explicit `confirm`.** Not a typed string — the owner ruled
    against typing on this control — but a field a stray request does not carry. Combined
    with `capture_server.SAFE_METHODS`' origin check, no other tab in the browser can
    reach it.
  - **It refuses to start a second run over a capture directory a run is already reading.**
    A double-click is the realistic accident here, not an attacker, and two live batches
    over one box is the shape that turns one into two invoices.
  - **The crop preview is free and shells out to nothing.** `POST /pipeline/crop-preview`
    answers what a reading does to the bytes — the cut, and the collector-number strip at
    the resolution it delivers — so the pair is legible before the estimate is asked for.
  - **The preflight is free, is a separate route, and is what the screen must show first.**
    `--dry-run` does everything except the API call: it counts the cards, prices the
    submission, and creates no run directory at all.
  - **The export fetch is free, and it is reported separately from the join.** It downloads,
    rules on the file with `cli/resolve.py:exports_for` before anything is joined, and
    deletes what it wrote on every refusal — so a fetch that failed and a join that failed
    are never one console the operator has to tell apart.

AND ONE ROUTE NOW OPENS A SOCKET OF ITS OWN, WHICH IS THE SECOND HALF OF THAT PROMISE
GOING AND HAS TO BE SAID AS PLAINLY AS THE FIRST. `GET /pipeline/runs/<name>/history`
fetches from `tcgcsv.com` and `infinite-api.tcgplayer.com`. The letter of the old sentence
survives — those are not Anthropic and no key is read — but the sentence meant *this process
talks to nobody*, and it no longer does. Leaning on the letter is the drift D16 exists to
catch, so:

  - **It spends nothing, and that is a property rather than a hope.** Both hosts are public:
    no key, no cookie, no session, no account. There is no way to run up a bill on either,
    which is what makes this a different kind of route from the one above rather than a
    second one of it.
  - **It reads and never writes, except its own derived cache.** No run directory is
    touched, no store lock is taken, and nothing about a card changes.
  - **It cannot fire on its own.** No screen polls it and no effect fires it on a walk; it
    answers one press about one SKU. That is the guard that keeps a courtesy delay honest
    against a free public mirror.
  - **A third party being down is a sentence, never a stack trace.** `Unreachable` and
    `NotResolvable` are named refusals with their own codes, so a mirror having a bad day
    costs the panel its reading and costs the screen nothing.

THE MONEY STEP IS SPAWNED AND NEVER AWAITED; EVERY OTHER STEP RUNS IN THE REQUEST. That
split is not a preference, it is the shape of the work. A Batch job takes minutes to hours
(`identify/batch.py` polls until the batch ends), and no HTTP request may be held open for
that. `join`, `emit` and `reconcile` are local arithmetic over a parsed CSV and finish in
seconds, so they answer in the response with their own stdout attached — which is also what
makes them honest: the operator reads the same text the command printed, not a summary of
it written here.

The child is detached (`start_new_session`) and its console goes to `console.log` inside the
run directory. Both facts matter for the same reason: **a run outlives this server.** The
Mac sleeps, `make server` gets restarted, a terminal closes — and the batch keeps running,
the log keeps filling, and `GET /pipeline/runs/<name>` reads the run directory rather than
any state held in this process. `cli/runs.py` already says a run is an immutable input
rather than state, and this file leans on that entirely.

WHAT IT DOES HOLD BETWEEN REQUESTS IS A HANDLE ON ITS OWN CHILDREN, AND NOTHING ELSE. That
sentence read "and holds nothing between requests" until 2026-09-11, and it was paid for: a
detached child is still a CHILD (`start_new_session` is `setsid`, a new session and not a new
parent), nothing here ever waited on one, and an unwaited child that exits is a ZOMBIE holding
its pid — which `os.kill(pid, 0)` accepts. A finished run therefore read `Running 8m` on
`#/runs` for as long as this server stayed up. `_CHILDREN` below is the fix, and it is
deliberately not an answer about a run: what a run has DONE is still read from its directory
every time, and an absent handle means *ask the files* rather than *not running*, so a
restarted server reads every run exactly as it did before. The promise above is intact — a run
still outlives this server — and it is rewritten rather than leaned on, which is what this
file already did to `capture_server.py`'s money promise one paragraph up.

STDLIB ONLY, like the rest of the server. `make server` runs `python3` and not the venv
(the Makefile says so and gives the reason), so this module may not import anything that
needs `make venv`. It shells out to `./pkmnscan`, which picks the venv itself with the same
rule the Makefile uses — one rule about which Python runs, stated in places that agree.
`cli.runs` is imported for its names, and is stdlib-only itself.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cli import cmd_reprice  # noqa: E402
from cli import resolve as run_resolve  # noqa: E402
from cli import runs as run_files  # noqa: E402
from pipeline import corpus, decisions, games as game_registry, join, reprice, tcgcsv  # noqa: E402
from pipeline import readings as readings_walk  # noqa: E402
from pipeline import selection as selection_mod  # noqa: E402
from pipeline import worklist  # noqa: E402
# ALIASED, BECAUSE `pricing` IS A LOCAL IN THIS MODULE. Two handlers bind the name to a
# run's parsed `pricing.json`; importing the module under it would make which one you
# got a matter of where in the function you were standing.
from pipeline import pricing as pricing_mod  # noqa: E402
from server import tcg_export  # noqa: E402
from server import tcg_import  # noqa: E402
# STDLIB-ONLY AT MODULE SCOPE, LIKE EVERY OTHER IMPORT HERE. `pipeline/pricehistory.py`
# reaches `json`, `time`, `urllib`, `dataclasses`, `datetime`, `decimal` and `pathlib`
# and nothing else — verified under bare `/usr/bin/python3`, which is what the Makefile
# falls back to when there is no venv. It is a top-level import rather than one inside
# the handler for exactly that reason: D32 puts the imports inside `crop-preview`
# because Pillow may genuinely be absent, and there is no equivalent risk here.
from pipeline import pricehistory  # noqa: E402
# THE SAME RULE, AND IT IS WHY THE RATES MOVED OUT OF `cli/cmd_identify.py`. `identify/cost.py`
# reaches `decimal` and nothing else, and `identify/__init__.py` is a docstring with no imports
# in it, so this costs one stdlib module. The command module could not be imported for them:
# it reaches geometry, PIL and sqlite.
from identify import cost  # noqa: E402
from identify import sidecar  # noqa: E402
from store import Store, files, master  # noqa: E402
from store import readings as store_readings  # noqa: E402
from store import submissions as claims  # noqa: E402
from store.session import Snapshot  # noqa: E402

PKMNSCAN = REPO_ROOT / "pkmnscan"
CONSOLE = "console.log"
PID_FILE = "running.pid"

# The free commands, and the flags each will accept from a request. An allowlist rather than
# a passthrough: a request that could append arbitrary argv to `./pkmnscan` would be a shell
# for anything on this machine that the origin check is not strong enough to guard.
FREE_STEPS = ("join", "emit", "reconcile")

# How long a free step may take before the request gives up. Generous, because a join over a
# 544-card run against a 30k-row export is seconds and a slow disk is not a failure — but
# bounded, because a request that never answers is worse than one that refuses.
STEP_TIMEOUT_S = 600

# The preflight decodes and (optionally) crops every photograph, which is the slowest free
# thing in this file: measured at roughly a minute for a 544-card box with `--crop`.
PREFLIGHT_TIMEOUT_S = 900

# HOW MANY RUNS ONE MERGED EMIT MAY NAME. This was `MAX_LEGS` and was shared with the cart of
# boxes, which is gone: a send is one selection now and spawns one child, so there is nothing
# left for a leg bound to bound. The emit's bound is NOT the same bound wearing the same name
# and is kept with its own (D156 records it as a decision: *"the bound is against a request
# nobody meant"*). What it guards is different too — `emit` spawns nothing, and every run name
# lands in one child's argv, so this is `ARG_MAX` and a malformed client rather than a process
# count. The operator has ten joinable runs and the steady state is the last sitting or two.
MAX_MERGED_RUNS = 16

# How many of a claim's cards the wire carries. Enough to recognise which selection it is —
# two or three positions is what tells a double-click from a drawer you had forgotten — and
# bounded because a store-wide press claims hundreds and the screen draws a sentence.
CLAIM_KEYS_SHOWN = 8

# ------------------------------------------------------------ the children we started
#
# THE `Popen` OF EVERY CHILD THIS PROCESS STARTED, KEYED BY RUN DIRECTORY.
#
# WHY A HANDLE AND NOT A PID. `_spawn` used to drop its `Popen` on the floor: the object was a
# local, nothing ever called `.wait()` or `.poll()`, and this server installs no SIGCHLD
# handler. `start_new_session=True` is `setsid` — a new SESSION, not a new parent — so the
# child is STILL OUR CHILD, and a child nobody waits on becomes a ZOMBIE when it exits. A
# zombie holds its pid, and `os.kill(<zombie>, 0)` SUCCEEDS. `_live_pid` therefore went on
# reporting a finished run as live: `Running 8m` on `#/runs` with the batch collected, the
# console finished and the child long gone. Measured 2026-09-11 on a run that took 3m52s. It
# corrected itself only when something else in this process happened to construct a `Popen` —
# CPython calls `subprocess._cleanup()` in `Popen.__init__`, which reaps whatever `__del__`
# filed in `subprocess._active` — or when the server restarted. A run nobody else touched said
# Running indefinitely, and the box guard of the day refused that box for just as long.
#
# HOLDING THE HANDLE AND POLLING IT IS THE FIX, AND THE POLL IS THE REAP: `Popen.poll()` is
# `waitpid(pid, WNOHANG)`, so the zombie goes at the first read that looks at it.
#
# ONE LOCK, BECAUSE THIS SERVER IS THREADED. `CaptureServer.process_request` submits every
# request to a `ThreadPoolExecutor(REQUEST_SLOTS)`, so `GET /pipeline/runs` and
# `POST /pipeline/identify` can be inside this table at the same instant.
#
# AND IT IS NOT STATE ABOUT THE RUN, which is the promise this module's header makes. Nothing
# here is consulted to answer WHAT a run has done — the run directory is still the only source
# of that. What is held is a handle on a process of OURS: a fact about this process, not about
# the run. Its ABSENCE is defined to mean "ask the files", never "not running", so a restarted
# server holds no handles and reads every run exactly as it does today.
_CHILDREN: "OrderedDict[str, subprocess.Popen]" = OrderedDict()
_CHILDREN_LOCK = threading.Lock()

# How many handles to keep. A dead child's handle is a TOMBSTONE and is deliberately NOT
# dropped the moment it is found dead: pids are reused, and a table that forgot the pid it had
# just buried would fall through to the marker file — whose pid may now belong to something
# else entirely — and report Running again. Bounded anyway, because every table in this server
# is; and a RUNNING child is never evicted whatever the count, because evicting one is the bug
# this section exists to fix.
CHILD_MEMORY = 64


class _Child(NamedTuple):
    """What the table can say about a run: the pid we started, and whether it is still up."""

    pid: int
    running: bool


def _child_key(run_dir: Path) -> str:
    """THE RESOLVED PATH, NEVER THE RUN NAME.

    `store/files.py:home()` reads the environment on every call, so two stores can hold runs
    with the same `<date>-<slug>-<nn>` name — and T7 moves `PKMNSCAN_HOME` between sections
    inside one process, which is exactly that case in the one place it would be found late.
    """
    try:
        return str(run_dir.resolve())
    except OSError:
        return str(run_dir)


def _remember_child(run_dir: Path, child: subprocess.Popen) -> None:
    """Hold the handle for a child this server just started."""
    with _CHILDREN_LOCK:
        _CHILDREN[_child_key(run_dir)] = child
        while len(_CHILDREN) > CHILD_MEMORY:
            for key, held in _CHILDREN.items():
                if held.returncode is not None:  # a tombstone, already reaped: droppable
                    del _CHILDREN[key]
                    break
            else:
                break  # every handle is a live child. Keep them all.


def _child_of(run_dir: Path) -> Optional[_Child]:
    """What this server knows about the child driving this run, or None if it started none.

    `poll()` IS CALLED UNDER OUR OWN LOCK, and both halves of that are deliberate.

    It is called because `poll()` is the reap — `waitpid(WNOHANG)` — so the zombie goes at the
    first read that looks, and the answer is a fact rather than a guess.

    It is serialised because CPython takes `Popen._waitpid_lock` NON-BLOCKING:
    `_internal_poll` returns None — documented in the stdlib as *"Something else is busy
    calling waitpid. Don't allow two at once. We know nothing yet"* — when another thread is
    already inside waitpid for this child. Two request threads polling one child at once could
    therefore answer STILL RUNNING about a child that had exited, which is the one direction
    that matters here. Holding this lock removes that answer and costs nothing: a WNOHANG
    waitpid does not block, and nothing else happens inside the lock. It is a leaf lock —
    nothing in here calls back into route code, reads a file, or takes the store lock.
    """
    with _CHILDREN_LOCK:
        child = _CHILDREN.get(_child_key(run_dir))
        if child is None:
            return None
        return _Child(child.pid, child.poll() is None)

# Downloadable run artefacts are matched by SHAPE, never by a name from the request. The
# request names a file, this decides whether that name is one this route is willing to
# serve, and nothing built from user input is ever joined onto a path.
_DOWNLOADABLE = re.compile(r"^[A-Za-z0-9._-]+\.(csv|txt|json|log)$")

# What a fetched export is called. It keeps the `export-` prefix every uploaded one has, so a
# run's artefact list reads the same either way, and adds a segment that says WHERE it came
# from — which is the one fact a file dropped into a run directory cannot otherwise carry.
FETCHED_PREFIX = "export-tcgplayer-"

# THE EXPORT IS A PROPERTY OF THE GAME, NOT THE DRAWER, AND THIS IS WHERE THAT IS SPELT.
# `inventory/.exports/<game>/`, store-wide, one copy of any given bytes — `LIVE_DIR`'s shape
# one directory over and for `LIVE_DIR`'s reason: the file is the evidence for the reading a
# run was joined against, so it is kept and never swept. The GAME is in the path because
# `cli/resolve.py:exports_for` maps game -> exactly one file and `Scope.category_id` is
# scalar; there is no third axis a directory could be cut on.
#
# WHAT IT REPLACES IS A PER-RUN COPY WHOSE DEDUPE COULD NOT SEE ITS SIBLINGS. The dedupe
# below globbed the run's OWN directory, so bytes already on disk one directory over were
# invisible to it. Measured on the owner's store 2026-09-12: 19 exports, 27.1 MB, 13
# distinct — 9.0 MB in 6 redundant copies, and 5 of those 6 are CROSS-RUN and therefore
# outside anything a per-run glob can reach. Five byte-identical 1,733,052 B copies landed
# in eighteen seconds (07:41:33 to 07:41:51) across five run directories.
EXPORTS_DIR = files.EXPORTS_DIRNAME

# HOW LONG A FETCHED EXPORT ANSWERS THE NEXT PRESS, IN SECONDS, AND THIS IS THE HALF THAT
# SAVES THE REQUEST RATHER THAN THE DISK. Deduping after the fetch turns six files into one
# and still spends six round trips; re-joining a store means pressing Fetch once per run, and
# the seven presses that produced the measurement above were nine minutes apart end to end
# while five of them were eighteen seconds apart. A press whose game already holds an export
# fetched inside this window, at a scope that COVERS what this run needs, answers from that
# file and opens no socket.
#
# FIFTEEN MINUTES IS SIZED TO THE SITTING AND NOT TO THE READING. An export is a reading of
# `Total Quantity` and `TCG Market Price`, and `describe_source`'s mtime is when that reading
# was taken — so reuse must never be long enough that an operator thinks they refreshed and
# did not. A re-join pass over a store is minutes; a deliberate refresh the next morning is
# hours. `refresh: true` on the request forces the socket open whatever the age, and the
# receipt says `reused` with the file's age on it either way, so nothing here is silent.
EXPORT_REUSE_S = 900

# WHEN A WIDENED FETCH IS REPORTED WITH BOTH FIGURES ON IT (D65/D76). `tcg_export.MAX_BYTES`
# is 32 MB and refuses past it; a scope that widens to the whole category is the only way to
# approach that, and it is much closer than the constant's own comment believed. MEASURED
# 2026-09-12, one fetch of the whole Pokemon category: 32,629,598 B — 222,849 rows, 31.12 MB,
# 97.24% of the cap, 903 KB of headroom, against 238,482 B for the one set the owner's 543
# Pokemon cards actually name. A widening is 137x here and it lands two per cent short of a
# hard refusal, so it may not be silent.
EXPORT_NEAR_CAP = 0.80

# The two numbers a screen must show before it may ask to spend. Parsed out of the
# preflight's own stdout rather than recomputed here, so the figure on the screen and the
# figure in the log are the same string produced by the same code.
_TO_SEND = re.compile(r"^to send\s+(\d+)\s*$", re.M)
_ESTIMATE = re.compile(r"^estimated cost\s+\$([0-9.]+)\s*$", re.M)
_CACHE_HITS = re.compile(r"^cache hits\s+(\d+)\s*$", re.M)
_PHOTOGRAPHS = re.compile(r"^photographs\s+(\d+)\s*$", re.M)


class PipelineRefusal(Exception):
    """A refusal with its own code, converted to a `BadRequest` by the caller.

    A private exception rather than `capture_server.BadRequest` directly, because importing
    that would make this module depend on the file that dispatches to it — and this module
    is imported BY that file. The seam is one `except` clause at the dispatch site.
    """

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


# ------------------------------------------------------------------------------- scoping


def box_capture_dir(box: int) -> Path:
    """The LEGACY capture directory for a box — where photographs were filed before D172.

    Kept because 4.45 GB moves once and resumably: while `meta.photos_relocated` is unset
    the photographs are still here, and `pipeline/selection.py:Selection.roots()` names this
    directory alongside the content-addressed store, so a half-moved store identifies exactly
    as it always did.
    """
    return files.home() / "captures" / "cards" / f"box{int(box)}"


def _run_box_id(manifest: dict) -> Optional[int]:
    """The TRUE INDEX this run recorded for its box, or None (D145).

    `_run_box`'s sibling, and deliberately WITHOUT its path fallback. A box number can be
    recovered from a capture directory's name because the directory is named after it; an id
    is written in one place and appears nowhere on disk, so there is nothing to fall back to
    and a run that did not record one simply did not. None is the honest answer, and
    `_run_drawer` has a rule for it.
    """
    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        return None
    bid = scope.get("bid")
    if isinstance(bid, int) and not isinstance(bid, bool) and bid > 0:
        return bid
    return None


def _box_bid(box: int) -> Optional[int]:
    """The TRUE INDEX of the drawer this run is about to read (D145).

    THIS IS THE ONE THING A RUN DIRECTORY MAY RECORD ABOUT ITS BOX BESIDES THE NUMBER, and it
    does not contradict D56's rule that a name is never written into a manifest. The two are
    different kinds of fact: a name is a LABEL the owner edits, so a copy of it goes stale the
    first time they rename the drawer; an id is an IDENTITY that is fixed at the moment the
    drawer is created and can never be edited, so a copy of it is as true in a year as it is
    now. Recording the id is what LETS the name go on being joined at read time — against the
    right drawer.

    None RATHER THAN A REFUSAL when the registry cannot be read or the box has no entry. A run
    is about photographs on disk and `box_capture_dir` above has already confirmed those; a
    store that will not open must not stop a run from starting. A run with no id here is read
    exactly like every run written before this field existed, by the rule `_box_name_for`
    has kept since D56.
    """
    try:
        entry = Store().read().inventory.box(box)
    except Exception:  # noqa: BLE001 — an identity is never worth an unstarted run
        return None
    return None if entry is None else entry.bid


def _resolve_selection(payload: dict) -> selection_mod.Selection:
    """The wire's selection, refused as a `PipelineRefusal` rather than a `SelectionError`.

    IT IS `_resolve_scope` RENAMED, AND THE NAME IS THE CHANGE. That function refused anything
    that did not name a positive integer `box` — *"A run is always scoped to one box"* — which
    is this entry's thesis stated as a 400.

    ONE SEAM, ONE TRANSLATION. `pipeline/selection.py` is the reader for both surfaces and
    raises its own exception so that it depends on neither the server nor argparse; this is the
    two-line adapter, and the `empty` flag is what picks the status — a term this cannot read is
    the request's fault (400) and a well-formed selection that matched nothing is a 404, which
    is exactly the split `box_required` and `box_has_no_captures` used to make.
    """
    try:
        return selection_mod.parse(payload)
    except selection_mod.SelectionError as exc:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND if exc.empty else HTTPStatus.BAD_REQUEST,
            exc.code,
            str(exc),
        ) from None


def _selection_captures(selection: selection_mod.Selection) -> List["sidecar.Capture"]:
    """The photographs this selection is over. Reads the disk, and the store only if asked to.

    THE ROUTE SCANS AND NO LONGER SYMLINKS, which is this entry's deletion in one line.
    `_scope_dir` existed because `identify` took a directory and a subset is not one, so a
    ticked selection was expressed by building `.scopes/box3-<n>-<stamp>` out of symlinks and
    pointing the command at it. The command takes the selection itself now, and the only thing
    this function is for is answering the questions the ROUTE has to answer before it spends:
    how many cards, whose claim they collide with, and which drawer the run will record.

    THE STORE IS READ ONLY WHERE A TERM NEEDS IT. `Selection.needs_store` is four terms — an
    id, a section, a state and a capture time — and the ordinary drawer press is none of them,
    so `{box: 3}` resolves off the sidecars alone. `Inventory.in_state` is a full-table pass
    (about a second on the operator's store), and paying it on every preflight of a press that
    cannot use it would be D163's decode-before-you-hash in another register.

    IT NEVER RAISES ON A MISSING CAPTURE ROOT AND ANSWERS EMPTY INSTEAD, because the one
    refusal a well-formed selection can earn belongs to the caller: the preflight wants to say
    "this names no photograph, out of N scanned" with the terms on it, and a `FileNotFoundError`
    from three frames down cannot.

    THE CONTENT-ADDRESSED STORE (D172) IS ONE OF `selection.roots()`'S OWN ROOTS NOW, not a
    second scan bolted on here — this function has exactly one caller that spends
    (`do_pipeline_identify`, through the child it spawns) and `cli/cmd_identify.py` walks the
    same roots for the same reason, so the fix belongs where both read it. See
    `Selection.roots()`.
    """
    captures: List["sidecar.Capture"] = []
    for root in selection.roots(files.home()):
        try:
            captures += sidecar.scan(root)
        except (FileNotFoundError, OSError):
            continue
    inventory = None
    if selection.needs_store:
        try:
            inventory = Store().read().inventory
        except Exception:  # noqa: BLE001 — a store that will not open is not an empty store
            raise PipelineRefusal(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "store_unavailable",
                "This selection names a state, a section, a drawer id or a capture time, and "
                "all four are answered by the store — which will not open right now.",
            ) from None
    try:
        return selection_mod.narrow(
            selection, captures, inventory=inventory, run_keys=_run_keys
        )
    except selection_mod.SelectionError as exc:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND if exc.empty else HTTPStatus.BAD_REQUEST, exc.code, str(exc)
        ) from None


def _run_keys(name: str) -> List[str]:
    """Every position key a run's own answers name. `--run <name>`'s reader.

    THROUGH `_open_run`, so the name is validated as a name and never joined onto a path blind
    — the same posture every other run route here takes. A run with no answers on disk yet
    names no card, which is the honest reading: `identifications.json` is written whole or not
    at all (`write_atomic`), so there is no half-answered run to mis-read.
    """
    try:
        payload = run_files.Run(_open_run(name)).read_identifications()
    except Exception:  # noqa: BLE001
        return []
    cards = payload.get("cards")
    return sorted(cards) if isinstance(cards, dict) else []


@dataclass(frozen=True)
class Send:
    """ONE PRESS: the cards it is over, how they are read, and what its run will be called.

    IT REPLACES `Leg`, AND THE DIFFERENCE IS THAT THERE IS EXACTLY ONE OF THEM. A `Leg` was an
    element of a list — `_resolve_legs` built one per box, `do_pipeline_identify` spawned a
    detached child per element, and every function between them took a `Sequence`. What that
    bought was the ability to give each drawer its own reading, which D48 called the deciding
    argument and which this entry measures as never used: 13 of 13 scope blocks on this store
    record `whole_box: True`, and 12 of 15 runs share one `max_edge`.

    THE READING IS STILL PER PRESS, which is the half of D48 that survives. One selection gets
    one crop and one max edge, and an operator who wants box 3 read at 1200 and box 5 at 900
    presses twice — two presses, two runs, two readings, and no list shape on the wire to carry
    a combination nobody has ever sent.
    """

    selection: selection_mod.Selection
    flags: List[str]
    label: str


def _resolve_send(payload: dict) -> Send:
    """`{state?, box?, bid?, section?, game?, since?, keys?, run?, paths?}` -> one press.

    THE `box_required` REFUSAL IS GONE, AND IT WAS THE THESIS STATED AS A 400. It read *"Send a
    positive integer `box`. A run is always scoped to one box"* — so "identify everything that
    still needs it" was not a sentence this route could be asked, and a pile spanning two
    drawers was two presses however few cards it held. Every request that used to satisfy it
    still does: `{box: 3}` is a selection naming one term.

    AN UNBOUNDED SELECTION IS ALLOWED HERE AND REFUSED IN A TERMINAL, and the asymmetry is
    argued in `Selection.named`. The screen has the free preflight and a confirm in front of
    it; a terminal has a newline.
    """
    selection = _resolve_selection(payload)
    label = payload.get("label")
    if not isinstance(label, str) or not label.strip():
        label = _default_label(selection)
    return Send(selection, _identify_flags(payload), label.strip())


def _default_label(selection: selection_mod.Selection) -> str:
    """What a run is CALLED when the press did not say — and it is still `boxN` where it can be.

    `runs.create` slugs this into `<date>-<slug>-<nn>`, so it is the operator's own handle on
    the run for the rest of its life and it is worth being the same string it has always been.
    A press over one drawer is `box3`, exactly as `_one_leg` named it; a press over a state is
    named for the state; a press over everything is `store`. Nothing reads the name back —
    `_run_box` reads the manifest's scope block and no longer parses this — so it is a label
    for a person and is allowed to be short.
    """
    if selection.box:
        return f"box{selection.box}"
    if selection.bid:
        return f"drawer{selection.bid}"
    if selection.run:
        return f"rerun-{selection.run}"
    if selection.game:
        return str(selection.game)
    if selection.state:
        return str(selection.state)
    if selection.keys:
        return f"cards{len(selection.keys)}"
    return "store"


# ------------------------------------------------------------------------- running things


def _env() -> dict:
    """The child's environment. `PKMNSCAN_HOME` is inherited so a test server pointed at a
    temporary store cannot start a run against the real one."""
    child = dict(os.environ)
    child.setdefault("PYTHONUNBUFFERED", "1")
    return child


def _run_sync(argv: Sequence[str], timeout: int) -> Tuple[int, str]:
    """A free command, run to completion inside the request. stdout and stderr, interleaved.

    `check=False`: a non-zero exit is an ANSWER here, not an exception. `join` refusing a
    missing export and `emit` refusing an unanswered price are the two most useful things
    those commands do, and a 500 with a stack trace would throw away the message they wrote
    to say which it was.
    """
    try:
        finished = subprocess.run(
            list(argv),
            cwd=str(REPO_ROOT),
            env=_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise PipelineRefusal(
            HTTPStatus.GATEWAY_TIMEOUT,
            "step_timed_out",
            f"`{' '.join(argv[1:3])}` did not finish within {timeout}s. Nothing here writes "
            f"partially — re-run it, or run it in a terminal to watch.",
        ) from None
    except FileNotFoundError:
        raise PipelineRefusal(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "pkmnscan_missing",
            f"{PKMNSCAN} is not executable from {REPO_ROOT}.",
        ) from None
    return finished.returncode, finished.stdout.decode("utf-8", "replace")


def _record_written(run_dir: Path) -> bool:
    """Has this run written the record the NEXT step reads?

    `Run.write_identifications` goes through `store/files.py:write_atomic`, so this file is
    never observable half-written: it is absent, or it is whole. That is what makes it safe to
    hang a liveness answer on, and it is why this is one `stat` rather than a manifest parse.
    """
    return (run_dir / run_files.IDENTIFICATIONS).is_file()


def _live_pid(run_dir: Path) -> Optional[int]:
    """The pid of a child still driving this run, or None.

    THREE ANSWERS IN THIS ORDER, AND THE ORDER IS THE FIX.

      1. a child of OURS still running   -> its pid. Nothing overrules this.
      2. a child of ours that has EXITED -> None. Not the marker file, not signal 0.
      3. no child of ours                -> the marker file, and a floor.

    (2) IS WHY THIS FUNCTION CHANGED. `start_new_session` is a new SESSION, not a new parent:
    the child stays ours, nothing waited on it, and an unwaited child that exits is a ZOMBIE
    holding its pid. `os.kill(<zombie>, 0)` SUCCEEDS — measured — so signal 0 alone said
    `identifying` for as long as this server stayed up. See `_CHILDREN` for the whole account.

    (1) TAKES NO MANIFEST INTO ACCOUNT, AND THAT IS WHAT CLOSES THE RACE. `cli/cmd_identify.py`
    writes `collected=True` at line 794, `identifications.json` at 840, and then records every
    card into the store under the store lock — seconds, on a 544-card run, in which the
    manifest says collected and the run is still going. A rule letting the manifest demote a
    RUNNING child would put `Needs join` on the screen inside that window, and `join` pressed
    there reads a file that is not there yet.

    (3) IS THE ORPHAN, AND IT IS THE ONLY CASE THE FILES DECIDE. A run started before this
    server was last restarted was reparented to launchd, which reaps it, so signal 0 is honest
    there — right up until the pid is REUSED. The floor is the run's own record rather than
    `collected`, for (1)'s reason one register over: `collected` is a claim about money spent
    and stays true through the whole tail above, while `identifications.json` is what the next
    step READS, is written atomically, and cannot be seen before it is complete.

    A NON-POSITIVE PID IS NOT A PID. `os.kill(0, 0)` probes the CALLER'S OWN process group and
    always succeeds, so a marker holding `0` read as live forever.
    """
    child = _child_of(run_dir)
    if child is not None:
        # The handle, not the marker: `_spawn` registers before it writes the file, so a poll
        # landing between the two still reads a just-started run as live.
        return child.pid if child.running else None

    marker = run_dir / PID_FILE
    try:
        pid = int(marker.read_text().strip())
    except (OSError, ValueError):
        return None
    if pid <= 0:
        return None
    try:
        # `ProcessLookupError` is an `OSError`; naming both was redundant.
        os.kill(pid, 0)
    except OSError:
        return None
    return None if _record_written(run_dir) else pid


def _run_box(manifest: dict) -> Optional[int]:
    """Which box a run is reading, from its own manifest's scope block. `None` where it says.

    THE PATH ARM IS GONE AND IT WAS CONFIDENTLY WRONG TWICE ON THIS STORE. It parsed
    `^box(\\d+)` off the capture directory's basename for a run whose manifest carried no
    scope — written for the run an agent starts in a terminal, which `_scope_for` has given a
    scope block of its own since D145. Measured on the operator's runs: `2026-09-02-box6-01`'s
    65 cards are all in box 3 today and `2026-08-29-box1-01`'s 99 are too, while the regex
    answers 6 and 1 without hesitating. A directory name is a CONVENTION — the sidecar is the
    claim (`identify/sidecar.py`) — and `--box` is a filter over what each capture recorded
    precisely because of those two runs.

    `None` IS THE HONEST ANSWER AND IS WHAT THE READERS WANTED ALL ALONG. `_summary` draws no
    drawer label for it (`runScope.ts:runBoxLabel` returns null), `refuse_reallocated` has
    nothing to compare and reports the run unverified rather than passing it through, and
    `_run_drawer` has a rule for it. Every one of those is better than a number off a folder:
    a run filed under the wrong drawer is the one fault none of them can detect, because a
    wrong box number resolves.

    WHAT IT COSTS is the drawer label on runs written before D145 and never re-joined — two
    on this store, both of which it was answering WRONGLY. The two mis-filed runs above also
    carry a wrong `scope.box`, so this does not make them right; it stops a second voice
    agreeing with the first for a different bad reason.
    """
    scope = manifest.get("scope")
    if isinstance(scope, dict):
        box = scope.get("box")
        if isinstance(box, int) and not isinstance(box, bool):
            return box
    return None


@dataclass(frozen=True)
class BoxFacts:
    """What the registry knows about the drawer wearing one box number, right now.

    A NAMED TUPLE GREW A FOURTH MEMBER AND STOPPED BEING READABLE (D145). This was
    `(name, created_at, runs)` and every reader unpacked it positionally; `bid` made it four,
    and a fourth anonymous slot in a tuple that is built in one place and read in two is how
    `_box_name_for`'s two conditions get passed in the wrong order by somebody in a hurry.
    """

    name: Optional[str]
    bid: Optional[int]
    created_at: Optional[str]
    runs: FrozenSet[str]


@dataclass(frozen=True)
class RunDrawer:
    """Which drawer a run was over, and what to call it on a screen (D145).

    `former` IS THE FIELD THE OWNER ASKED FOR, and `name` changes meaning with it: for a
    current drawer the name is the registry's LIVE one, joined at read time exactly as D56
    requires; for a departed one it is the name frozen onto the `box_deleted` history line,
    because there is no registry entry left to join against.
    """

    name: Optional[str]
    former: bool


def _run_drawer(
    box: Optional[int],
    bid: Optional[int],
    run: str,
    ran_at: Optional[str],
    names: Dict[int, "BoxFacts"],
    deleted: Optional[Dict[int, str]] = None,
) -> RunDrawer:
    """Is the box wearing this number today the drawer this run was over, and what is it called?

    TWO WAYS TO ANSWER, AND THE FIRST ONE IS NOT A HEURISTIC (D145).

      THE ID, where the run recorded one. `bid` is fixed at the drawer's creation and can
      never be edited or reissued, so comparing it against the id the current box wears is a
      decision and not an inference: equal is the same drawer, different is not, and there is
      no third answer. Every run started after this landed takes this arm.

      THE SHAPE OF THE EVIDENCE, where it did not. `store/master.py:box_disowns_run` — the
      stamp and the card set, both required, argued at length there and in D36. Every run that
      predates this field takes this arm, which is EVERY RUN ON THE OWNER'S MACHINE INCLUDING
      THE ONE THAT PRODUCED THE COMPLAINT, so it is the arm that has to keep working rather
      than a compatibility shim to be deleted next quarter.

    THE ARMS ARE NOT COMBINED, AND THE ID WINS OUTRIGHT WHERE IT EXISTS. The older rule
    abstains towards the box being the run's own — it must, since it is reasoning from
    absence — and letting an abstention soften a fact would be a rule that gets LESS certain
    as it learns more. A run carrying an id that does not match is a departed drawer even
    though its cards are gone and its timestamps say nothing.

    A BOX THE REGISTRY HAS NEVER SEEN IS NOBODY'S TO DISOWN, which is the same abstention
    `Inventory.box_disowns_run` makes: a run over a box with no registry entry gets no name
    and is not called departed, because nothing here knows that it departed rather than that
    it was never registered.
    """
    if box is None:
        return RunDrawer(name=None, former=False)
    found = names.get(box)
    if found is None:
        return RunDrawer(name=None, former=False)

    if isinstance(bid, int) and not isinstance(bid, bool) and found.bid is not None:
        if int(bid) == int(found.bid):
            return RunDrawer(name=found.name, former=False)
        lookup = _deleted_box_names() if deleted is None else deleted
        return RunDrawer(name=lookup.get(int(bid)), former=True)

    if not master.box_disowns_run(found.created_at, found.runs, run, ran_at):
        return RunDrawer(name=found.name, former=False)
    # The older rule can say THAT the drawer departed and never WHICH it was, so there is no
    # id to look a name up by. `(deleted)` with no name is the honest rendering, and it is
    # already the whole of what the complaint asked for.
    return RunDrawer(name=None, former=True)


def _box_names() -> Dict[int, "BoxFacts"]:
    """`box -> what the registry knows about the drawer wearing that number right now`.

    THE SECOND AND THIRD ARE HERE BECAUSE A BOX NUMBER IS REUSED AND A NAME IS NOT TIED TO A
    RUN. `next_box_number` allocates the lowest FREE integer (D20), so a box that goes and
    another that arrives share a number — and this map, keyed by the number alone, then hands
    a run from before the change the name of the drawer that replaced it. Observed:
    `2026-08-22-box1-03` drew `UNL Rares`, a registry entry made seven days after that run
    and holding none of its 53 cards.

    THE RUN SET COSTS ONE PASS OVER THE CARDS THIS ALREADY PARSED. `Inventory.parse` is the
    expensive half and it was happening anyway; walking the parsed cards for `box` and `run`
    is arithmetic beside it, and it is done ONCE for a whole run list rather than per row.

    THE STORE IS THE SOURCE AND THE RUN IS NOT, WHICH IS THE WHOLE POINT OF READING IT HERE
    (D56). A run directory records the box NUMBER it was over — in its scope block, or in the
    capture directory its name is derived from — and it has never recorded a name, correctly:
    D20 makes a rename a live edit to the registry that relabels every card in the box on
    every screen that draws one, so a name copied into a manifest would be a second answer
    that goes stale the first time the owner renames the drawer. This reads the current one.

    NAMED BY THE REGISTRY OR NOT NAMED AT ALL. D20 makes a name unique and deliberately NOT
    required, so a box with none is the ordinary case rather than a fault, and it is simply
    absent from this map — the caller draws `box 3` and says nothing it cannot support. Same
    for a box that has since been deleted (D10 ruling 3): the run remembers a box the store
    no longer has, and a missing name is the honest rendering of that.

    IT READS THE CARDS AND NOTHING ELSE. This used to parse `inventory.json` directly rather
    than take `Store().read()`, because that read also parsed the identification cache and
    both queue files — measured at 7.3ms against 4.5ms over a 268KB cache nothing here
    reads. Since D88 a snapshot loads only the tables a caller touches, so the ordinary read
    is the cheap one and the direct parse is gone with the file it parsed. `GET
    /pipeline/runs` is polled at 4s while a run is live; two column-only queries answer it.

    IT NEVER RAISES, which is `do_status`'s rule applied to a decoration. A store this cannot
    read costs the run list its box names and must not cost it the run list — the phase, the
    elapsed time and the download links are what that poll is actually for.
    """
    try:
        inventory = Store().read().inventory
        present: Dict[int, set] = {}
        for _, (box, run) in inventory.cards.select(("box", "run")):
            if box is not None and isinstance(run, str) and run.strip():
                present.setdefault(int(box), set()).add(run)
    except Exception:  # noqa: BLE001 — a name is never worth an unanswered poll
        return {}
    names: Dict[int, BoxFacts] = {}
    for key, entry in inventory.boxes.items():
        name = entry.name
        if not isinstance(name, str) or not name.strip():
            name = None
        try:
            box = int(key)
        except (TypeError, ValueError):
            # A registry key that will not coerce names no box, exactly as `_box_row`'s walk
            # treats a card whose box will not: skipped, never fatal.
            continue
        # AN UNNAMED BOX IS IN THE MAP NOW, WITH `name=None` (D145). It was
        # skipped for as long as this answered one question, because a box with no name has
        # no name to hand back. It answers two questions now — what is this drawer called,
        # and IS IT THE RUN'S DRAWER — and the second one has a real answer for an unnamed
        # box: the owner's own case is a `Box 1` nobody ever named.
        names[box] = BoxFacts(
            name=name,
            bid=entry.bid,
            created_at=entry.created_at,
            runs=frozenset(present.get(box, ())),
        )
    return names


def _deleted_box_names() -> Dict[int, str]:
    """`bid -> the name that drawer had when it was deleted` (D145).

    THE HISTORY IS THE ONLY PLACE THIS CAN COME FROM, and that is the point rather than a
    limitation. D56 forbids writing a name into a run directory because a live name is
    editable; once the drawer is deleted the name stops being editable — there is nothing
    left to edit — so the last name it wore is a FACT, and `box_deleted` is where the store
    recorded it. Joining it back onto a run is D56's read-time join pointed at the one
    registry entry that no longer exists.

    FROZEN AT THE DELETION AND NEVER LATER. A name shown for a departed drawer cannot go
    stale in the way D56 guards against, because nothing can rename a box that is gone.

    LAZY AND CACHED FOR ONE RUN LIST. Only a run whose drawer has actually departed needs
    this, which on a healthy store is no run at all, so a whole poll usually pays nothing.

    IT NEVER RAISES, `_box_names`' rule: a history this cannot read costs a departed run its
    drawer's name, and it still gets `(deleted)` — which is the half that answers the
    complaint.
    """
    out: Dict[int, str] = {}
    try:
        events = Store().named_events("box_deleted")
    except Exception:  # noqa: BLE001
        return out
    # Newest first, so an id that somehow appears twice keeps the name it was last deleted
    # under — and `setdefault` is what makes "first seen wins" mean that.
    for event in events:
        bid = event.get("bid")
        name = event.get("name")
        if not isinstance(bid, int) or isinstance(bid, bool):
            continue
        if isinstance(name, str) and name.strip():
            out.setdefault(bid, name.strip())
    return out


def _send_keys(captures: Sequence["sidecar.Capture"]) -> List[str]:
    """Every position key the photographs in this selection carry.

    THE SELECTION, NOT THE SEND LIST, and the difference is what makes this check cheap enough
    to run at a press. The send list needs a digest per photograph and a cache consult; the
    SELECTION needs only the sidecars, which is what `cli/cmd_identify.py` reads first anyway.
    A claim holds the other press's MISSES, so intersecting this against it is exact in the
    direction that matters — a press whose selection touches a claimed card is refused, and a
    press whose selection touches none of them is not.

    WHAT IT CAN OVER-REFUSE, named rather than hidden: a card of mine that is a cache HIT and
    somebody else's live miss. My press would pay nothing for it and is refused anyway, for as
    long as their claim stands. That is the correct trade at a money press, and their claim
    goes when their run finishes.

    THE SIDECARS AND NOT THE FILENAMES. `<index>.jpg` looks like it names the key and does not:
    `Capture.box` is what the capture RECORDED, and the two disagree the moment a directory is
    renamed or handed over as a pile — `cli/cmd_identify.py:_scope_for` carries the same note.
    Reading them is one small file per photograph and no decode: MEASURED at 35 ms over 678
    sidecars, which is the count box 4 really holds and the one the hash-first reorder was
    measured on. That is the whole reason this check can run at a press at all — the digests
    the real claim needs cost 0.687 ms EACH, and the crop-and-prepare pass 114.96 ms each.

    IT NEVER RAISES, AND IT NO LONGER SCANS. `_selection_captures` has already walked the
    disk for the preflight's own count, so this is a list comprehension over what is in hand —
    which is what lets the courtesy check cost nothing on top of the answer the screen was
    getting anyway. It used to re-scan the leg's directory per leg.
    """
    return [capture.key for capture in captures if capture.has_position]


def _claim_conflict(captures: Sequence["sidecar.Capture"]) -> Optional[dict]:
    """Which of these cards a live submission is already holding, or None. ONE press, ONE answer.

    THE COURTESY HALF OF THE GUARD (D174), AND IT IS NOT THE GUARD. The binding one is
    `store/submissions.py:claim_or_refuse`, called by the command inside the transaction it
    writes the claim in — that is the only place a refusal can be atomic with respect to another
    press. This runs before anything is spawned so that the ordinary double-click is answered AT
    THE PRESS, with a sentence, instead of by a child that starts, refuses and dies as a red row
    on the screen.

    BOTH EXIST BECAUSE THEY FAIL DIFFERENTLY. This one can be beaten by a press that lands
    between the read and the spawn; the command's cannot.

    IT IS THE WHOLE OF THE COURTESY NOW THAT `_busy_run` IS GONE, AND THAT IS A NARROWING WORTH
    STATING. `_busy_run` refused a second press over a DRAWER a live run was reading, whatever
    the cards; this refuses a second press over CARDS a live run is paying for. What stops
    being refused is a press whose overlap with a live run is entirely cache hits — and that
    press is spending nothing on those cards, which is D174's own rule for why an empty send
    list writes no row: *"It is spending nothing, so there is nothing to protect."* What starts
    being refused is everything `_busy_run` could not see: a live run over a pile spanning two
    drawers, which `_run_box` answers `None` for, and two disjoint selections in one drawer,
    which it refused for no reason.

    THE BOX IS OFF THE ROW AND THE CARDS ARE ON IT. `_claim_conflicts` returned one row per leg
    carrying `box`, because a cart's refusal had to say WHICH leg. There is one selection now,
    so the row says what it is about in the vocabulary the claim itself uses — the receipts, the
    runs, the card count and the server's own sentence.
    """
    try:
        held = Store().read().submissions
        live = held.live()
    except Exception:  # noqa: BLE001
        return None
    if not live:
        return None
    overlap = held.overlap(_send_keys(captures))
    if not overlap:
        return None
    return {
        "cards": sum(len(shared) for _, shared in overlap),
        "receipts": [sub.receipt for sub, _ in overlap],
        "runs": [sub.run for sub, _ in overlap if sub.run],
        "sentence": claims.conflict_sentence(overlap),
    }


def _claim_rows() -> List[dict]:
    """Every live claim, as the screen draws it. FREE, reads the store and holds nothing.

    THE COUNT BEFORE THE CONTROL THAT FIRES, which is `GET /boxes/<box>/photos`' shape one
    feature over (D89): the release button is not drawn until this has answered, so the
    receipt, the run, the number of cards and whether the holder is still alive are all on
    screen before anything can be pressed.

    `holder_alive` IS THE FIELD THE SCREEN BRANCHES ON, and it is reported rather than acted
    on. A claim whose holder is gone still blocks — a run killed after it submitted has a
    batch in flight that nobody collected, and a guard that auto-healed that row would hand
    the operator a green button over an invoice already rung up. So the screen says WAIT for a
    live holder and OFFERS THE RELEASE for a dead one, and the choice stays the operator's.
    """
    held = Store().read().submissions
    rows = []
    for sub in held.live():
        rows.append(
            {
                "receipt": sub.receipt,
                "run": sub.run,
                "pid": sub.pid,
                "started_at": sub.started_at,
                "cards": len(sub.keys),
                # Enough to recognise the selection, never the whole set: a store-wide press
                # claims hundreds and the screen draws a sentence, not a manifest. IN POSITION
                # ORDER AND NOT THE STORED ORDER — the row's `keys` is sorted as strings so the
                # payload is stable, which puts `3/10` before `3/2` and reads on screen like a
                # fault in the guard itself.
                "sample": sorted(sub.keys, key=claims.by_position)[:CLAIM_KEYS_SHOWN],
                "capture_dir": sub.capture_dir,
                "holder_alive": claims.holder_alive(sub),
            }
        )
    return rows


def do_pipeline_submissions() -> dict:
    """`GET /pipeline/submissions` — what is claimed right now, and what it cost to know."""
    rows = _claim_rows()
    return {
        "claims": rows,
        # THE WORK, ON THE WIRE. Rows, cards locked, and how many are held by a process that
        # is gone — the three figures that say whether this guard is doing anything, published
        # rather than inferred from the fact that nothing went wrong.
        "counts": {
            "claims": len(rows),
            "keys": sum(row["cards"] for row in rows),
            "stale": len([row for row in rows if not row["holder_alive"]]),
        },
    }


def do_pipeline_submission_release(receipt: str, payload: dict) -> dict:
    """`POST /pipeline/submissions/<receipt>/release` — give up a claim, on the operator's word.

    THE NAMED WAY OUT, and the reason a row is allowed not to self-heal. `_busy_run` recovered
    from a wedge by itself because `_CHILDREN` empties on a restart; a row does not, and that
    is deliberate — see `store/submissions.py`. What replaces the automatic recovery is this:
    one press, with the receipt on it, after a free preview that says whether the holder is
    still there.

    IT SPENDS NOTHING AND IT CAN COST SOMETHING, which is why it takes a `confirm` exactly as
    the money route does. Releasing a claim whose holder is still submitting re-opens those
    cards to a second press, and that press would be the double invoice the claim existed to
    prevent. The refusal says so, and the preview says which case this is.

    A RECEIPT THAT IS NOT THERE IS A 404 AND ONE ALREADY RELEASED IS AN ORDINARY ANSWER. The
    distinction `do_review_answer`'s undo already draws: nothing there, versus already done —
    so a replayed request and a stale screen both land on the first press's answer.
    """
    if payload.get("confirm") is not True:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Releasing a claim re-opens its cards to another press. If its holder is still "
            "submitting, that press is the second invoice this claim exists to prevent. Send "
            "`confirm: true`, and show the operator whether the holder is alive first.",
        )
    if not isinstance(receipt, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", receipt or ""):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST, "receipt_invalid", f"{receipt!r} is not a receipt."
        )
    with Store().write() as writable:
        claim = writable.submissions.get(receipt)
        if claim is None:
            raise PipelineRefusal(
                HTTPStatus.NOT_FOUND,
                "no_such_claim",
                f"There is no claim {receipt}. Read /pipeline/submissions for the ones there "
                f"are — a claim released earlier is gone from that list by design.",
            )
        was_live = claim.live
        cards = len(claim.keys)
        run = claim.run
        writable.submissions.release(receipt, claims.BY_OPERATOR)
    return {
        "receipt": receipt,
        "run": run,
        # WHAT THE PRESS ACTUALLY DID, so the receipt on screen is a figure and not a word.
        "released": was_live,
        "cards": cards,
        "claims": _claim_rows(),
    }


# ------------------------------------------------------------------------- the preflight


def _max_edge(payload: dict) -> Optional[int]:
    """The request's `max_edge`, validated, or `None` where it names none.

    ONE VALIDATOR FOR TWO ROUTES. The preflight turns it into a flag and the crop preview
    uses the number itself, and a second range check written beside the second caller is a
    refusal that can disagree with the one the run will actually get — the preview would
    then draw a reading the identify route refuses.
    """
    max_edge = payload.get("max_edge")
    if max_edge is None:
        return None
    if not isinstance(max_edge, int) or isinstance(max_edge, bool) or not (
        256 <= max_edge <= 4096
    ):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "max_edge_invalid",
            "`max_edge` must be an integer between 256 and 4096. D32's measured "
            "frontier for this rig runs 900 to 1400.",
        )
    return max_edge


def _identify_flags(payload: dict) -> List[str]:
    """The identify flags a request may set, allowlisted one at a time.

    `--force-resubmit` is deliberately NOT here. It is the one identify flag whose whole
    purpose is to pay again for an answer already bought, and D32's known cache gap means a
    re-crop cannot be distinguished from a re-run by the cache — so a screen offering it
    would be a screen offering to double an invoice for a reason the operator cannot see.
    It stays a terminal flag until the crop is part of the cache identity.
    """
    flags: List[str] = []
    if payload.get("crop"):
        flags.append("--crop")
    max_edge = _max_edge(payload)
    if max_edge is not None:
        flags += ["--max-edge", str(max_edge)]
    retry = payload.get("retry_budget")
    if retry is not None:
        if not isinstance(retry, int) or isinstance(retry, bool) or not (0 <= retry <= 3):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "retry_budget_invalid",
                "`retry_budget` must be an integer between 0 and 3.",
            )
        flags += ["--retry-budget", str(retry)]
    return flags


def _parse_preflight(text: str) -> dict:
    """The two numbers the confirm step needs, lifted out of the preflight's own stdout.

    LIFTED RATHER THAN RECOMPUTED, which is the same rule `cmd_join`'s dry-run follows about
    reading its counts off `entries_for`. A second implementation of the cost model here
    would be a number that can disagree with the one in the log, and the operator would have
    no way to tell which had drifted. `None` where a line did not appear, so a changed
    preflight shows up as a missing figure on the screen rather than as a confident zero.
    """

    def _one(pattern, cast):
        found = pattern.search(text)
        return cast(found.group(1)) if found else None

    return {
        "photographs": _one(_PHOTOGRAPHS, int),
        "cache_hits": _one(_CACHE_HITS, int),
        "to_send": _one(_TO_SEND, int),
        "estimate_usd": _one(_ESTIMATE, float),
    }


def _preflight(send: Send) -> dict:
    """The dry run. Free by construction — `--dry-run` returns before `runs.create`.

    ONE CHILD, AND IT USED TO BE ONE PER BOX ON A FOUR-WORKER POOL. `_preflight_leg` shelled
    `identify --dry-run` per leg, and `PREFLIGHT_WORKERS` existed because five drawers in
    series held the request open for five minutes with nothing on screen. A selection is one
    command however many drawers its cards are in, so the pool, the bound and the latency
    argument all go together — a press over the whole store is ONE `identify --dry-run` over
    2,535 photographs where a cart of five would have been five, each re-walking a drawer.

    THE CAPTURES ARE SCANNED HERE AND HANDED DOWN. The count, the claim check and the drawer
    the run would record all need the same list, and the child re-derives it for itself because
    it is a separate process — but nothing on THIS side walks the disk twice for one press.
    """
    captures = _selection_captures(send.selection)
    if not captures:
        try:
            selection_mod.refuse_empty(send.selection, _scanned(send.selection))
        except selection_mod.SelectionError as exc:
            raise PipelineRefusal(HTTPStatus.NOT_FOUND, exc.code, str(exc)) from None
    argv = [str(PKMNSCAN), "identify", *send.selection.flags(), "--dry-run"] + send.flags
    code, text = _run_sync(argv, PREFLIGHT_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "selection": send.selection.describe(),
        "sentence": send.selection.sentence(),
        "scope": _scope_for_send(captures),
        "capture_dirs": [str(root) for root in send.selection.roots(files.home())],
        "console": text,
        # THE SAME COURTESY THE BOX CHECK USED TO BE, IN THE ONE VOCABULARY THAT HAS AN ANSWER
        # FOR EVERY PRESS (D174). Null where nothing is claimed, so a screen branching on it
        # reads exactly as it did when `busy_run` sat beside it.
        "claimed": _claim_conflict(captures),
        "total": _total(text, captures),
    }


def _scanned(selection: selection_mod.Selection) -> int:
    """How many photographs were in view before the terms narrowed them. For the refusal only.

    IT IS THE HALF THAT MAKES AN EMPTY ANSWER READABLE. `box_has_no_captures` could say one
    thing — this drawer has no directory — and an empty selection has three causes: a mistyped
    term, a drawer whose cards are all in a state the selection excluded, and a capture root
    that is not there. The count separates the last from the first two at no cost, because the
    scan has already happened.
    """
    total = 0
    for root in selection.roots(files.home()):
        try:
            total += len(sidecar.scan(root))
        except (FileNotFoundError, OSError):
            continue
    return total


def _scope_for_send(captures: Sequence["sidecar.Capture"]) -> Optional[dict]:
    """Which drawer this press would record, by `pipeline/selection.py`'s one derivation.

    THROUGH THE SHARED FUNCTION AND NOT A COPY OF IT. This block is what `_run_box`,
    `_run_box_id`, `refuse_reallocated` (D36) and `_summary`'s drawer label (D56) all read, and
    it was derived twice — here and in `cli/cmd_identify.py:_scope_for` — with a comment in each
    pointing at the other. The preflight reports the id the run WOULD record for the same reason
    it always did: a preview that showed a different scope from the press would be a preview of
    a different run.
    """
    try:
        inventory = Store().read().inventory
    except Exception:  # noqa: BLE001 — an identity is never worth an unquoted press
        inventory = None
    return selection_mod.scope_block(captures, home=files.home(), inventory=inventory)


def _total(console: str, captures: Sequence["sidecar.Capture"]) -> dict:
    """What this press costs, and how many cards it is over. LIFTED HERE, NEVER ON THE SCREEN.

    THE NUMBER THE CONFIRM IS GATED ON IS THE SERVER'S. `app/src/server.ts` records that the
    app is forbidden from computing rules the pipeline owns, and this is the sharpest case of
    it: the total on screen is the total the operator is agreeing to spend, and arithmetic in
    TypeScript would be a second implementation of the cost model that can disagree with the
    console printed directly below it.

    A MISSING FIGURE ANSWERS `None` RATHER THAN ZERO, which is the half of this function that
    survived the cart intact. `_parse_preflight` answers `None` where a line did not appear,
    precisely so a changed preflight shows up as a missing figure rather than as a confident
    zero — and the screen draws a blank for it rather than `$0.00`.

    `cards` REPLACES `boxes`, AND THAT IS THE ONE NOUN D33 CHANGES. That entry's rule is that
    the total is *"the number the operator agrees to spend"*, and boxes are not what is being
    bought — a press over 2,535 cards in five drawers reported `5`, which is the least useful
    true number available about it. It is the count of the SELECTION and not of the send list:
    `to_send` beside it is what will be paid for, and the two differing is the cache doing its
    job. Measured on the operator's store 2026-09-12: a press over everything is 2,535 cards and
    0 to send, because all 2,535 are cache hits.
    """
    figures = _parse_preflight(console)
    return {
        **figures,
        # Rounded to cents where the console printed a figure at all, and left exactly as
        # printed otherwise.
        "estimate_usd": (
            None if figures["estimate_usd"] is None else round(figures["estimate_usd"], 2)
        ),
        "cards": len(captures),
    }


def do_pipeline_preflight(payload: dict) -> dict:
    """`POST /pipeline/preflight` — what a send would cost. FREE, and creates no run.

    `identify --dry-run` returns before `runs.create`, so this leaves nothing on disk at all —
    and as of this entry that is true of the ROUTE as well as of the command. `_resolve_scope`
    built a directory of symlinks per ticked selection before the command was even started, so
    a preflight that spent nothing still wrote to disk and still needed sweeping: 264 such
    directories on the operator's checkout, every one named `-1-` because every one was the crop
    preview stepping a single card.

    THE ANSWER IS ONE QUOTE, WHERE IT USED TO BE A LIST OF ONE OR MORE. D48's rule was that the
    shape must not change with the request, and that is exactly why a cart's response was always
    a list; with one selection per press there is one thing being quoted, and a one-element list
    would be the cart's ghost. The raw stdout is returned beside the figures and the screen shows
    it verbatim: `docs/DESIGN.md`'s copy rule makes the owner's screens the place the pipeline's
    own words are shown rather than paraphrased, and the preflight is the densest thing it says.

    THERE IS NO SPEND CEILING HERE AND THERE IS NOT GOING TO BE ONE. The owner's ruling,
    2026-09-12: *"Give me settings if I can have them, but if I want to run everything, then I
    get to run everything."* So what this route owes the screen is the FIGURE and the COUNT,
    honestly, and the screen owes the operator a confirm that is loud in proportion — a refusal
    at some number would be this route deciding how much of their own store the operator may
    read.
    """
    return _preflight(_resolve_send(payload))


# ------------------------------------------------------------------- the crop preview

# The band is JPEG at this quality. High, because the whole point of the strip is whether
# the digits survive the reading — compression artefacts of our own invention would be a
# preview lying in the one direction that matters.
BAND_QUALITY = 92

# WHICH BAND THE PREVIEW DRAWS, when the card's game claims one. `geometry/crop.py` owns
# where a band IS and `pipeline/games.py` owns which bands a game CLAIMS; this names the one
# the preview is about, and asks the registry per card whether that card's game claims it.
PREVIEW_BAND = "number"


def _band_rect(sent_size, prepared, det, rect, band_fractions):
    """Where the collector number is IN THE BYTES THAT WILL BE SENT, as a rectangle.

    A rectangle rather than a cut-out image, because the screen already has those bytes: it
    draws the sent image in the frame and paints this region of the same file at 1:1
    underneath. One image over the wire, two views of it, and the second cannot drift from
    the first because there is no second file to drift.

    Located off `card_rect` — the corrected, UNPADDED card — because the band is a fraction
    of the cardboard, not of the cut. Measuring it off the padded rectangle would put the
    strip a few percent low on every card, which is exactly the error the pad correction
    exists to undo.
    """
    from identify import images as identify_images

    sent_w, sent_h = sent_size
    card = identify_images.card_rect(prepared.original_size, det)
    if rect is not None:
        origin_x, origin_y = float(rect[0]), float(rect[1])
        source_w, source_h = float(rect[2] - rect[0]), float(rect[3] - rect[1])
    else:
        origin_x = origin_y = 0.0
        source_w, source_h = (float(v) for v in prepared.original_size)
    if source_w <= 0 or source_h <= 0:
        return None

    scale_x, scale_y = sent_w / source_w, sent_h / source_h
    left = (card[0] - origin_x) * scale_x
    top = (card[1] - origin_y) * scale_y
    right = (card[2] - origin_x) * scale_x
    bottom = (card[3] - origin_y) * scale_y

    frac_l, frac_t, frac_r, frac_b = band_fractions
    width, height = right - left, bottom - top
    cut = (
        max(0, int(round(left + width * frac_l))),
        max(0, int(round(top + height * frac_t))),
        min(sent_w, int(round(left + width * frac_r))),
        min(sent_h, int(round(top + height * frac_b))),
    )
    if cut[2] - cut[0] < 2 or cut[3] - cut[1] < 2:
        # The card is off the edge of its own frame, which is a real thing a bad capture
        # does. No band rather than a sliver — a two-pixel strip drawn as evidence would
        # read as a detector fault when it is a photograph fault.
        return None
    return cut


def do_pipeline_crop_preview(payload: dict) -> dict:
    """`POST /pipeline/crop-preview` — what this reading actually sends. FREE, writes nothing.

    D32's amendment gave the crop three named pairs and a sentence each, because the owner
    could not tell from the controls what the crop did: *"walk me through how im supposed to
    understand crop with just this dialog box"*. The sentences are true and they are still
    prose about pixels. This is the same answer in the medium the decision is actually about.

    TWO ANSWERS, BECAUSE THE PAIR HAS TWO AXES AND ONE PICTURE CANNOT SHOW BOTH:

      - `rect` is where the crop cuts, in the ORIGINAL frame's pixels, so the screen can draw
        it over the photograph it already has. It answers *is the identifier inside the
        bytes* — box 2's failure, 38 numbers cut clean off — and a picture of the crop alone
        could never answer it, because what was cut is not in the crop.
      - `band` is the collector-number strip AS SENT, at the resolution this reading
        delivers. It answers *will the digits survive*, and it is the only half that moves
        when `max_edge` moves: the rectangle is identical at 1200 and at 900, so a preview
        that drew only the rectangle would leave two of the three readings looking the same.

    ONE CARD PER CALL, WALKED BY `offset` (the owner, 2026-08-29). It answered three evenly
    spaced cards for a few hours, on the argument that cards move on the tray so the front of
    a box does not stand for it — D32 measured card area at 39-81% across box 2. That
    argument is sound about SAMPLING and it lost to a plainer fact: three cards abreast in a
    panel are three small pictures, and the operator could not see the thing they were being
    shown. One card at the size of the column, and the spread is reached by walking rather
    than by being sampled for.

    THE BAND IS THE REGISTRY'S TO GRANT, PER CARD, AND THIS IS A DEFECT THIS ROUTE SHIPPED
    WITH. It cut `geometry/crop.py`'s number band over every game, and `pipeline/games.py`
    refuses that in writing for exactly this case: *"the bands are fractions measured on a
    Pokemon card. Nothing has measured where a Riftbound card puts its title or its number,
    and a band claimed without that measurement is cut over the wrong pixels."* Box 1 is
    Riftbound, and the strip drew its rules text as though it were a collector number. A game
    whose `crop_bands` does not claim the band gets NO band and a sentence saying why —
    the same refusal `crop_regions` makes, reached through the same registry field.

    IT CREATES NOTHING AND SPENDS NOTHING. No run directory, no store write, no model call. It
    is a read, and it sits in this module rather than beside `GET /photo` because everything it
    knows — the crop, the max edge, the selection — is this module's vocabulary.

    AND IT NO LONGER WRITES A SYMLINK DIRECTORY TO DO IT, which is where that sentence was
    quietly false. Every one of the 264 scope directories on the operator's checkout was built
    by THIS route: each is named `box<n>-1-<stamp>`, a selection of exactly one card, which is
    what stepping the preview does. A free read that had to write to disk and then be swept was
    the clearest sign the directory was standing in for a vocabulary that did not exist.
    """
    selection = _resolve_selection(payload)
    crop = bool(payload.get("crop"))
    offset = payload.get("offset", 0)
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "offset_invalid",
            "`offset` must be a non-negative integer — it walks the preview, nothing else.",
        )

    try:
        import geometry
        from geometry.crop import BAND_PROFILES
        from identify import images as identify_images
        from pipeline import games
        from PIL import Image  # noqa: F401 — probes Pillow's presence, same as the four imports above it
    except ImportError as exc:
        # NAMED RATHER THAN FATAL, and the import is in here rather than at module scope for
        # exactly this reason: `server/capture_server.py` has never needed Pillow, and a
        # top-level import would turn a missing dependency into a server that will not boot
        # over a preview nobody had asked for yet.
        raise PipelineRefusal(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "imaging_unavailable",
            f"The crop preview needs Pillow, numpy and geometry in the SERVER's "
            f"interpreter — run `make venv` and restart `make server`. ({exc})",
        ) from exc

    captures = [c for c in _selection_captures(selection) if c.has_position]
    total = len(captures)
    if total == 0:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "selection_is_empty",
            f"Nothing to preview: {selection.sentence()} names no photograph carrying a "
            f"position.",
        )

    # WRAPS RATHER THAN CLAMPS. The stepper is held down as often as it is tapped, and a
    # clamp at the end of a 543-card box leaves the operator pressing a key that does
    # nothing; wrapping means the walk always moves.
    at = offset % total
    capture = captures[at]

    try:
        detected = geometry.detect_card(capture.photo)
    except Exception:
        # The same swallow `cli/cmd_identify.py` performs around this call, and for the same
        # reason: detection is an optimisation, and a photograph it cannot read is sent whole
        # rather than failing the card. A preview that raised where the run would shrug would
        # be describing a different run.
        detected = None

    max_edge = _max_edge(payload) or identify_images.MAX_EDGE
    try:
        prepared = identify_images.prepare(
            capture.photo,
            max_edge=max_edge,
            crop_box=detected if crop else None,
        )
    except identify_images.ImageError as exc:
        return {
            "selection": selection.describe(),
            "capture_dirs": [str(root) for root in selection.roots(files.home())],
            "crop": crop,
            "max_edge": max_edge,
            "total": total,
            "offset": at,
            "sample": {"box": capture.box, "index": capture.index, "unreadable": str(exc)},
        }

    # THE CUT THE RUN WILL ACTUALLY MAKE, WHICH IS NOT ALWAYS THE ONE DETECTION PROPOSED.
    # `prepare` applies `images.crop_refusal` and can decline a box that came back looking
    # fine — a rectangle inside the card, which sends the collector number outside the bytes.
    # Reading the refusal off `prepared` rather than re-running the guard is the same rule
    # `_parse_preflight` follows and the same one `crop_rect` exists for: the preview draws
    # what was made, never a second opinion about it.
    crop_refused = prepared.crop_refused
    rect = (
        identify_images.crop_rect(prepared.original_size, detected)
        if crop and detected is not None and crop_refused is None
        else None
    )

    # THE PICTURE IS THE PAYLOAD, NOT THE FILE ON DISK (the owner, 2026-08-29: *"the crop
    # preview should also show the depixelation reflected as you change the options"*). The
    # frame used to draw `GET /photo`, which is the same bytes at every reading — so the one
    # thing the operator was changing was the one thing the picture could not show. Sending
    # the prepared bytes costs 235-441KB on a localhost socket, debounced, for one card.
    sent_image = "data:image/jpeg;base64," + base64.b64encode(prepared.data).decode("ascii")

    # THE REGISTRY DECIDES WHETHER THERE IS A BAND AT ALL, per card, off the card's own game.
    # `game_or_default` rather than the raw claim: D21 puts the backfill at the read, and a
    # sidecar written before that field existed is a Pokemon card.
    game = capture.game_or_default
    try:
        claims = games.get(game)["crop_bands"]
    except Exception:
        # An unregistered game is refused by the run itself, by name. Here it simply means no
        # band — guessing one would be the defect this block exists to fix.
        claims = ()
    band_rect = band_absent = None
    if PREVIEW_BAND not in claims:
        band_absent = (
            f"`{game}` claims no {PREVIEW_BAND} band, so nothing points itself at the "
            f"identifier on this game's cards — `geometry/crop.py`'s bands are fractions "
            f"measured on a Pokemon card. Point at the card above to read any part of it."
        )
    elif detected is not None:
        band_rect = _band_rect(
            prepared.sent_size, prepared, detected, rect, BAND_PROFILES[PREVIEW_BAND]
        )

    return {
        "selection": selection.describe(),
        "capture_dirs": [str(root) for root in selection.roots(files.home())],
        "crop": crop,
        "max_edge": max_edge,
        "total": total,
        "offset": at,
        "sample": {
            "box": capture.box,
            "index": capture.index,
            "game": game,
            "frame": list(prepared.original_size),
            "sent": list(prepared.sent_size),
            "rect": list(rect) if rect is not None else None,
            # `rect: null` because the crop is OFF and `rect: null` because detection REFUSED
            # are opposite facts to an operator — one is the setting they chose, the other is
            # a card going at whole-frame cost when they asked for a crop. This is the only
            # field that tells them apart.
            "method": detected.method if detected is not None else None,
            # WHY THE CARD WAS FOUND AND STILL NOT CROPPED TO. A third fact, and it is not
            # either of the two above: `method` says a card was located, `rect: null` says
            # nothing was cut, and only this says the box was refused and what was wrong with
            # it. Without it the preview would draw a whole frame over a found card and give
            # the operator no way to tell that from the crop simply being switched off.
            "crop_refused": crop_refused,
            # THE SENT BYTES THEMSELVES. The frame draws these rather than the stored
            # photograph, so the picture changes when the reading does — and the 1:1 view
            # below is a region of this same file, which is why the two can never disagree.
            "sent_image": sent_image,
            # Where the collector number is INSIDE `sent_image`, for the default 1:1 aim.
            # Null where the registry claims no band; the pointer still reaches every pixel.
            "band_rect": list(band_rect) if band_rect is not None else None,
            "band_px": (
                [band_rect[2] - band_rect[0], band_rect[3] - band_rect[1]]
                if band_rect is not None
                else None
            ),
            "band_absent": band_absent,
        },
    }


# --------------------------------------------------------------------- the one that spends


def _spawn(send: Send, captures) -> dict:
    """Create the run directory and start the detached child. Costs money. ONE child.

    IT USED TO BE CALLED ONCE PER BOX IN A LOOP, and the loop is what `D48`'s cart was: one
    detached child per drawer, each its own run, each its own reading. What replaces it is one
    child over one selection — so a pile spanning three drawers is one run and one invoice
    instead of three presses, and a press over the store is one process instead of five.
    """
    run = run_files.create(send.label)
    roots = send.selection.roots(files.home())
    # Written HERE and not left to the child, because `_run_box` reads it: a run whose manifest
    # names no scope until the child's first flush is a run the claim panel and the drawer label
    # cannot see during exactly the window a double-click happens in. The child re-derives it
    # from what it actually read, through the same `selection.scope_block`, and overwrites this.
    run.set(
        # ONE ROOT OR NONE, NEVER A JOINED STRING. `Run.capture_dir` is typed `Optional[Path]`
        # and every reader of it treats absence as "this run does not say" — which is the honest
        # answer for a selection naming several roots, where the full list is in `selection`
        # below. It was the input to `_run_box`'s deleted path arm and has no Python reader now.
        capture_dir=str(roots[0]) if len(roots) == 1 else None,
        scope=_scope_for_send(captures),
        selection=send.selection.describe(),
        started_by="app",
        flags_from_app=send.flags,
    )

    argv = (
        [str(PKMNSCAN), "identify", *send.selection.flags(), "--run-dir", str(run.directory)]
        + send.flags
    )
    console = run.directory / CONSOLE
    try:
        with open(console, "ab", buffering=0) as log:
            log.write(f"$ {' '.join(argv)}\n".encode("utf-8"))
            child = subprocess.Popen(  # noqa: S603
                argv,
                cwd=str(REPO_ROOT),
                env=_env(),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                # DETACHED, and this is the whole reason a run survives a restart of this
                # server: a child in the server's own process group dies with it, and a
                # Batch job killed halfway is paid for and not collected.
                start_new_session=True,
            )
    except OSError as exc:
        raise PipelineRefusal(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "spawn_failed",
            f"Could not start `pkmnscan identify` for {send.selection.sentence()}: {exc}",
        ) from None
    # THE HANDLE FIRST, THE MARKER SECOND. `_live_pid` reads the handle for a run this server
    # owns, so a poll landing between the two still reads the run as live; the reverse order
    # leaves a window in which the marker names a pid the table has never heard of and the run
    # reads as somebody else's orphan.
    #
    # THE MARKER IS STILL WRITTEN AND STILL NEVER DELETED. It is the only thing about this
    # child that survives this process — a restart, a `make up` reload, a crash — and it is
    # what `scripts/reap.py` and a person reading a run directory have to go on. Deleting it
    # from `_live_pid` was considered and declined: `scripts/serve.py` documents that function
    # as one that "only ever READS", it is the 4s-polled path, and cases 1 and 2 never open it.
    _remember_child(run.directory, child)
    (run.directory / PID_FILE).write_text(f"{child.pid}\n")
    return {
        "run": run.directory.name,
        "path": str(run.directory),
        "pid": child.pid,
        "selection": send.selection.describe(),
        "scope": _scope_for_send(captures),
        "cards": len(captures),
        "argv": argv,
    }


def do_pipeline_identify(payload: dict) -> Tuple[HTTPStatus, dict]:
    """`POST /pipeline/identify` — THE ROUTE THAT SPENDS MONEY. Spawns, does not wait.

    Answers as soon as the child is running, with the run's name. Everything after that is READ
    FROM THE RUN DIRECTORY by `do_pipeline_run`, which is what lets a run outlive the server
    that started it: this process keeps no answer about a run.

    It does keep a HANDLE on the child it spawned (`_CHILDREN`), and that is not the same thing
    — it is a fact about this process, not about the run, and its absence means "ask the files"
    rather than "not running". Without one, nothing ever reaped a detached child and a finished
    run read as still identifying.

    IT IS STILL EXACTLY ONE ROUTE THAT SPENDS (D33), AND IT IS NOW ONE CHILD PER PRESS. The
    cart's argument for landing here rather than beside it still holds and is now easier to
    keep: this file's whole claim is that the money is behind one door with one `confirm` and
    one refusal path, and there is one selection, one total and one run behind that door.

    WHAT WENT WITH THE CART IS THE PARTIAL SEND. `_resolve_legs` validated every leg before any
    was acted on precisely because `Popen` could fail on the fourth after three had started —
    an invoice for three drawers reported as one failure — so the response carried `started` and
    `failed` side by side and the screen drew both. One child cannot half-start: it spawns or it
    refuses, and `failed` is `[]` on every success and unreachable on every refusal. Both keys
    stay on the wire because the screen's partial-send notice is one `length` check and a shape
    that changed under it would be a reader asking which response it got.

    THE BOX GUARD IS GONE AND THE CARD GUARD IS WHAT IS LEFT. `_busy_run` refused a second
    press over a drawer a live run was reading; it took a box number, and there is no longer a
    box number on this route to give it. Its replacement is D174's claim, which was built for
    exactly this and which that entry says must be exercised before the guard it replaces comes
    out — `_claim_conflict` here at the press, `claim_or_refuse` in the transaction that decides
    what is being bought.
    """
    if payload.get("confirm") is not True:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "This is the step that spends money. Send `confirm: true` — and show the "
            "operator /pipeline/preflight's card count and estimate before you do.",
        )
    send = _resolve_send(payload)
    captures = _selection_captures(send.selection)
    if not captures:
        try:
            selection_mod.refuse_empty(send.selection, _scanned(send.selection))
        except selection_mod.SelectionError as exc:
            raise PipelineRefusal(HTTPStatus.NOT_FOUND, exc.code, str(exc)) from None
    # THE CARD-LEVEL REFUSAL, BEFORE THE CHILD STARTS (D174). IT IS NOT THE BINDING GUARD AND
    # MUST NOT BE READ AS ONE. `store/submissions.py`'s claim, written by the command inside the
    # transaction that recomputes what is being bought, is the only refusal that is atomic
    # against another press; this one can be beaten by a press landing between the read and the
    # spawn, and its job is to answer the ordinary double-click AT THE PRESS with a sentence
    # instead of with a dead run on the screen.
    conflict = _claim_conflict(captures)
    if conflict is not None:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "cards_already_claimed",
            conflict["sentence"]
            + ". Two live batches over one card is two invoices for one answer. Watch that "
            "run, or release its claim on this screen if its holder is gone. Nothing in this "
            "send was started.",
        )
    return HTTPStatus.ACCEPTED, {"started": [_spawn(send, captures)], "failed": []}


# --------------------------------------------------------------------------- reading runs


def _open_run(name: str) -> Path:
    """A run directory by name. The name is validated as a NAME, never joined blind.

    `runs.create` builds `<date>-<slug>-<nn>` and nothing else ever should, so anything with
    a separator or a dot-dot in it is not a run name and is refused before it touches the
    filesystem — the same posture `_DOWNLOADABLE` takes for artefacts one level down.
    """
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name or ""):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST, "run_name_invalid", f"{name!r} is not a run name."
        )
    directory = files.runs_dir() / name
    if not directory.is_dir() or not (directory / run_files.MANIFEST).is_file():
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_run",
            f"There is no run {name}. Read /pipeline/runs for the ones there are.",
        )
    return directory


def _manifest(directory: Path) -> dict:
    try:
        return json.loads((directory / run_files.MANIFEST).read_text())
    except (OSError, ValueError):
        return {}


def _artifacts(directory: Path) -> List[dict]:
    """Every file in the run a screen may offer for download, newest-relevant first.

    Listed off the DIRECTORY rather than off a table of names this file knows, because
    `runs.import_listed_name` makes the import filenames per-game and a hard-coded list here
    would silently stop offering the file for every game added after it was written.
    """
    out: List[dict] = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or not _DOWNLOADABLE.match(entry.name):
            continue
        stat = entry.stat()
        out.append(
            {
                "name": entry.name,
                "bytes": stat.st_size,
                "modified": int(stat.st_mtime),
                # `import` AND NOT `import-`, WHICH WAS WRONG FROM THE DAY THE MERGED FILE
                # WAS ADDED. `cli/runs.py:IMPORT_MERGED` is `import.csv` with no hyphen, so
                # the one file `emit` now writes by default was listed as an ordinary
                # artefact and the run panel's import affordance never appeared over it.
                "is_import": entry.name.startswith("import") and entry.suffix == ".csv",
            }
        )
    return out


def _console_tail(directory: Path, limit: int = 20000) -> str:
    """The last of the child's console. Bounded, because a 544-card run writes a lot of it.

    Read from the end rather than the start: the interesting part of a long-running command
    is always what it said most recently, and a head-truncated log would show the preflight
    forever while the batch it describes finished.
    """
    path = directory / CONSOLE
    try:
        size = path.stat().st_size
        with open(path, "rb") as handle:
            if size > limit:
                handle.seek(size - limit)
            blob = handle.read()
    except OSError:
        return ""
    text = blob.decode("utf-8", "replace")
    return text.split("\n", 1)[-1] if size > limit and "\n" in text else text


def _phase(manifest: dict, live: bool) -> str:
    """Which of the four steps this run is waiting for. What the screen puts on the row.

    Derived from the run directory every time rather than stored, for `cli/runs.py`'s stated
    reason: a run is an immutable input and not state, so a phase held anywhere would be a
    second answer to a question the files already answer.
    """
    if live:
        return "identifying"
    if not manifest.get("collected"):
        return "identify" if manifest.get("batch_ids") else "ready"
    if not manifest.get("joined"):
        return "join"
    # A RECORD NAMING NOTHING IS NOT AN EMIT. Truthiness of the dict was the test, and
    # `{"listed": [], "sub_threshold": [], "pushed": 0}` is a truthy dict — so a run whose
    # record had been blanked read `reconcile` on the panel while `reconcile` itself refused
    # with "this run has emitted nothing". D54 stops that record ever being written, and this
    # is the belt to that braces: a hand-edited manifest, or one written by an older
    # checkout, must not send the operator to a step that will refuse them.
    emitted = manifest.get("emitted") or {}
    if not (list(emitted.get("listed") or []) + list(emitted.get("sub_threshold") or [])):
        return "emit"
    if not manifest.get("reconciled"):
        return "reconcile"
    return "done"


def _summary(directory: Path, names: Optional[Dict[int, str]] = None) -> dict:
    """One run, as every route that mentions one answers with it.

    `box` AND `box_name` ARE THE SERVER'S ANSWER TO WHICH DRAWER THIS WAS, AND THE CLIENT NO
    LONGER HAS TO DERIVE EITHER (D56). The box was always derivable from `scope` or from the
    capture directory, and `RunPanel.tsx:boxOf` derived it — a second implementation of
    `_run_box` in another language, with an unanchored regex where this one anchors on the
    basename. It agreed on every run on this machine and was one oddly-named parent directory
    from not agreeing. The name was derivable by nobody: it lives in the store, which no
    screen drawing a run list had read.

    `names` IS PASSED IN BY THE LIST AND READ HERE BY THE SINGLE-RUN ROUTES. The registry is
    one read whatever the answer, so a list of twenty runs must not take twenty of them; a
    route answering about one run has nothing to share it with and reads its own.
    """
    manifest = _manifest(directory)
    pid = _live_pid(directory)
    box = _run_box(manifest)
    bid = _run_box_id(manifest)
    if names is None:
        names = _box_names()
    drawer = _run_drawer(box, bid, directory.name, manifest.get("created_at"), names)
    return {
        "run": directory.name,
        "path": str(directory),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "capture_dir": manifest.get("capture_dir"),
        "scope": manifest.get("scope"),
        # DERIVED ON EVERY READ, NEVER STORED. `box` restates what the manifest already
        # holds; `box_name` is a join against the registry as it stands right now, so a
        # rename shows up on the next poll rather than on the next run.
        "box": box,
        "box_name": drawer.name,
        # THE TRUE INDEX OF THE DRAWER THIS RUN WAS OVER, and the only field here a run
        # directory stores for itself (D145). `null` for every run written
        # before the field existed, which `_run_drawer` reads as "decide by the older rule"
        # rather than as "no drawer".
        "box_bid": bid,
        # THE DRAWER THIS RUN WAS OVER IS NOT THE BOX WEARING ITS NUMBER TODAY. The whole of
        # the owner's complaint: *"i deleted an old box 1, started writing into a new box
        # (now new box 1) and ... it shows that i'd run a 'Box 1' run a long time ago etc.
        # it's confusing."* `runScope.ts:runBoxLabel` draws `Box 1 (deleted)`.
        "box_former": drawer.former,
        "started_by": manifest.get("started_by"),
        "live": pid is not None,
        "pid": pid,
        "phase": _phase(manifest, pid is not None),
        "batch_ids": manifest.get("batch_ids") or [],
        "collected": bool(manifest.get("collected")),
        "joined": bool(manifest.get("joined")),
        "counts": manifest.get("counts") or {},
        "usage": _usage(manifest),
    }


def _usage(manifest: dict) -> dict:
    """What this run spent, and what that cost.

    THE ARITHMETIC IS NOT REIMPLEMENTED HERE, which is the rule `_parse_preflight` keeps one
    register up. `identify/cost.py` is the only place in this repo that multiplies a token
    count by a rate; the run that records the figure and this read call the same function, so
    a filled-in figure is byte-identical to what that run would have written for itself.

    RECORDED BEATS COMPUTED, ALWAYS, AND THE ORDER OF THESE BRANCHES IS THAT RULE. A run is an
    immutable input (`cli/runs.py`) and `cost_usd` is the rate sheet as it stood on the day the
    money was spent. A read that recomputed it would restate history the first time a rate
    moves — and one already has: `PIXELS_PER_TOKEN` "read 500 and was wrong by about half".

    THE BACKFILL IS WHY THIS IS A FIX AND NOT A PROMISE. Every run on this machine predates the
    field, including the one this was reported against, and D21's `game` backfill is the same
    shape: fill at the READ for records written before the field existed. It SAYS SO — a screen
    that cannot tell a recorded figure from today's rates applied to an old run has no way to
    show the difference on the day the two stop agreeing.

    A MISSING TOKEN COUNT ANSWERS NOTHING RATHER THAN ZERO, for `_total`'s own reason: a
    confident $0.00 is worse than a blank, because a blank is visibly a blank. `bool` is
    excluded by name because `isinstance(True, int)` is True, and a hand-edited manifest is
    exactly what `_phase`'s own comment already braces against.
    """
    usage = dict(manifest.get("usage") or {})
    if usage.get("cost_usd") is not None:
        return usage
    tokens_in = usage.get("input_tokens")
    tokens_out = usage.get("output_tokens")
    if any(not isinstance(n, int) or isinstance(n, bool) for n in (tokens_in, tokens_out)):
        return usage
    usage["cost_usd"] = cost.recorded(tokens_in, tokens_out)
    usage["cost_backfilled"] = True
    return usage


def do_pipeline_runs() -> dict:
    """`GET /pipeline/runs` — every run, newest first. A read; costs nothing."""
    root = files.runs_dir()
    if not root.is_dir():
        return {"runs": []}
    # ONE REGISTRY READ FOR THE WHOLE LIST. This is the polled route — 4s while anything is
    # live — and the names are the same map for every row in it.
    names = _box_names()
    rows = [
        _summary(entry, names)
        for entry in sorted(root.iterdir(), reverse=True)
        if entry.is_dir() and (entry / run_files.MANIFEST).is_file()
    ]
    return {"runs": rows}


def do_pipeline_run(name: str) -> dict:
    """`GET /pipeline/runs/<name>` — one run, with its console tail and its files.

    This is the poll. It reads the directory on every call and holds nothing, so a screen
    polling it sees a run started by a terminal exactly as it sees one started by itself.
    """
    directory = _open_run(name)
    body = _summary(directory)
    body["console"] = _console_tail(directory)
    body["files"] = _artifacts(directory)
    body["manifest"] = _manifest(directory)
    return body


def _position_label(
    views: Dict[int, join.BoxView],
    inventory: Optional[master.Inventory],
    box,
    index,
) -> Optional[str]:
    """Where the copy stored at `box/index` is RIGHT NOW, or None where that cannot be said.

    THE POOLED BRANCH COMES BEFORE THE VIEW LOOKUP, exactly as `capture_server._Places.of`
    orders it and for its reason: a pooled card borrows nothing from the box, and
    `cli/resolve.py:box_views` skips pooled records by ruling (D24) — so a box holding only
    code cards has no view at all, and asking for one first would answer null for a card
    whose place is perfectly well known to be no place.

    A BOX WITH NO VIEW ANSWERS None, NEVER AN INDEX-SPACE LABEL. `box_views` returns `{}`
    when a record's position will not coerce — its own store-wide degrade — and omits a box
    no located record names, which is a box deleted out from under this run. A bare
    `join.BoxView()` would render both of those as `Box N · Section N · Card M` in the
    numbering D58 replaced, silently, on a screen already drawing the other one. `_Places`
    calls that "no honest label" and answers null; this answers null with it.
    """
    if inventory is None:
        return None
    try:
        number, at = int(box), int(index)
    except (TypeError, ValueError):
        return None
    card = inventory.cards.get(master.position_key(number, at))
    game = str(getattr(card, "game", None) or game_registry.DEFAULT_GAME)
    if not join.is_located(game):
        return join.place_text(game, join.BoxView().at(number, at))
    view = views.get(number)
    if view is None:
        return None
    return join.place_text(game, view.at(number, at))


def _relabel_positions(table) -> None:
    """Re-render every position label in a parsed `pricing.json`, in place. The file is not touched.

    THE STORED LABEL IS NEVER SERVED (D58, on D56's rule), and this is the third surface to
    say so. `cli/cmd_join.py:_pricing_table` writes `{"box", "index", "label"}` per matched
    SKU at join time and `cli/runs.py` makes a run an immutable input — so that label is a
    snapshot of a rendering, and every rule that moves a rendering leaves it behind. Two
    already have, and both were live here:

      a copy that sold or retired after the join went on drawing `Box N · Section N · Card M`
      at a slot whose occupant closed up behind it, which is the exact claim D58 refuses;

      a divider layout edited after the join left the label describing a sectioning that is
      no longer in the plastic, which is the failure D58 MEASURED at 15 of 92 entries on the
      review queue the day it landed.

    IT IS THE PHOTO CAPTION, WHICH IS WHY IT MATTERS MORE THAN ITS TYPOGRAPHY SUGGESTS.
    `app/src/Pricing.tsx` draws this string under the copy's photograph beside `2 of 3`, and
    `photoUrl` addresses that photograph BY SLOT — so the picture was always the current
    occupant of the index while the caption was the join's. Re-rendering here is what makes
    the caption describe the photograph above it rather than a different moment of it.

    THE LABEL ONLY, AND NOTHING IS WRITTEN BACK — D58's own posture for the queue, for its
    reason: nothing already on disk moves, no re-join is needed, and every run already
    written is corrected the next time a screen opens it. `box` and `index` travel exactly as
    stored, because they are the store key `photoUrl` is aimed by and the key
    `cli/resolve.py:paperwork_for` realigns (D36); this composes a string and re-binds
    nothing.

    `cli/resolve.py:box_views` RATHER THAN `capture_server._Places`, AND THE CHOICE IS
    FORCED: `capture_server` imports this module, so the reverse import is the cycle
    `PipelineRefusal` exists to avoid. It is not a second renderer — it is the OTHER
    implementation of D58's walk, the one every report in `cli/resolve.py` renders through,
    and T7 already asserts the two agree on a real card.

    `place_text` RATHER THAN `Position.label`, WHICH FIXES A POOLED BUG ON ITS WAY PAST.
    `pokemon_code` is `located: False` AND `catalogued: True` (D24), so its cards do reach a
    join and did land in this table wearing `Box N · Section N · Card M` — the one string the
    pooled ruling says may never be printed for them. `place_text` answers the pooled fact
    with the store key beside it, which is also what keeps two copies of one SKU from drawing
    the identical caption in a strip whose whole job is stepping between them (D68).
    """
    if not isinstance(table, dict):
        return
    try:
        inventory = Store().read().inventory
    except (files.StoreError, OSError, ValueError, TypeError):
        # THE PRICING SCREEN DOES NOT GO DOWN WITH THE STORE, and that is a property this
        # route had for free until it started reading one. Its table comes off the run
        # directory; the store is consulted only to compose a caption. So an unreadable
        # inventory costs the captions and nothing else — the same call the handler below
        # makes for a malformed corpus, degrading the way `_Places` does: null,
        # never the stored string and never a guess.
        inventory = None
    views = {} if inventory is None else run_resolve.box_views(inventory)
    for entry in table.get("skus") or ():
        if not isinstance(entry, dict):
            continue
        for at in entry.get("positions") or ():
            if not isinstance(at, dict):
                continue
            at["label"] = _position_label(views, inventory, at.get("box"), at.get("index"))


def do_pipeline_pricing(name: str) -> dict:
    """`GET /pipeline/runs/<name>/pricing` — the per-SKU table and this run's answers.

    FREE, READ-ONLY, AND IT CREATES NOTHING. It opens files the run directory already holds
    and computes no price: `cli/cmd_join.py` wrote every figure in `pricing.json` through
    `pipeline/pricing.py`, which is the only place in this repo allowed to. This route is a
    reader, and `app/src/server.ts` already records that the app may not compute rules the
    pipeline owns — that rule reaches the server that feeds it.

    IT DOES COMPOSE ONE THING, AND IT IS NOT A PRICE. Every position label in the table is
    re-rendered against the live store before it goes out and the stored one is never served
    — D58 on D56's rule, the same treatment `capture_server._queue_row` gives the review
    queue, argued at `_relabel_positions`. So this handler now reads the store as well as the
    run directory, and it reads it LOCK-FREE like `do_queues`: a screen must not serialise
    behind a running `./pkmnscan join`. A store it cannot read costs the captions and not the
    table.

    IT ALSO ANSWERS WHEN THE TABLE WAS WRITTEN, which is what lets a screen say how stale a
    market price is — see `written_at` below for why that is a file mtime and what it does not
    claim.

    THE TABLE AND THE ANSWERS IN ONE READ, WHICH IS THE WHOLE REASON IT IS A ROUTE RATHER
    THAN A DOWNLOAD BESIDE `GET /pricing`. `_DOWNLOADABLE` already matches `.json`, so a
    screen could fetch `pricing.json` through `GET .../file` and the corpus through its own
    route — but two fetches can straddle a re-join, and a table describing one join beside
    answers written against another is a screen quietly pricing the wrong set of cards.

    IT IMPORTS NOTHING NEW. `make server` runs bare `python3`, so this module is stdlib-only;
    this handler opens, parses and returns.
    """
    directory = _open_run(name)
    table = directory / run_files.PRICING
    if not table.is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_not_written",
            f"Run {name} has no {run_files.PRICING} — `join` is what writes it, and every "
            f"run made before it predates the file. Join this run and it will appear.",
        )

    try:
        pricing = json.loads(table.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_unreadable",
            f"{run_files.PRICING} could not be read: {exc}. Re-join this run to rewrite it.",
        ) from None
    # THE LABELS, RE-RENDERED BEFORE ANYTHING LEAVES (D58). In place on the document just
    # parsed, which nothing else holds — the file on disk is untouched, exactly as D58 left
    # `QueueEntry.label`.
    _relabel_positions(pricing)
    # THE ANSWERS COME FROM THE CORPUS, SCOPED TO THIS RUN'S OWN SKUS (D86, amended). They
    # used to be `runs/<n>/decisions.json`, which is why the same card carried one answer per
    # drawer it had been photographed in. Narrowed to this run's rows so a screen drawing one
    # run is not handed every answer the operator has ever given.
    #
    # AN UNREADABLE CORPUS IS NOT A REFUSAL HERE. `emit` and `join` both answer one with a
    # sentence naming what is wrong, and that is where an operator should read it; a screen
    # that would not draw AT ALL because its answers file is malformed is a screen that cannot
    # show you the file.
    answers = None
    try:
        book = corpus.Corpus.read()
        wanted = {str(row.get("sku")) for row in pricing.get("skus") or []}
        answers = book.scoped_to(wanted, run_name=directory.name).to_payload()
    except Exception:  # noqa: BLE001 - see above: a bad corpus must not blank the table
        answers = None
    return {
        "run": directory.name,
        "pricing": pricing,
        "decisions": answers,
        # WHEN THIS TABLE WAS WRITTEN, WHICH IS THE ONLY AGE THIS SERVER CAN HONESTLY GIVE A
        # PRICE. `cli/cmd_join.py` rewrites `pricing.json` on every join, so its mtime is the
        # moment a join last read an export — and every figure under `snap` came out of that
        # export. It is NOT when TCGplayer computed the price: the export is a file the operator
        # downloaded at some earlier moment this machine has no way to see, so a screen drawing
        # this must say "read" and never "as of".
        #
        # THE FILE'S OWN MTIME RATHER THAN A FIELD INSIDE IT. A `joined_at` written into the
        # table would be better data and would be absent from every run already on disk, which
        # is exactly the runs a screen is opened over. This needs no re-join and cannot drift
        # from the bytes it describes. What it does not survive is the run directory being
        # copied, which resets it; nothing in this repo copies one.
        "written_at": int(table.stat().st_mtime),
    }


# ----------------------------------------------------------- the cross-run worklist (D86)


def _run_is_open(manifest: dict, pricing: dict, answers: Optional[dict]) -> bool:
    """Whether this run still has pricing work in it — the default worklist's filter.

    TWO WAYS TO BE OPEN AND THE FIRST IS THE COMMON ONE. A joined run that has never emitted
    is work by definition: nothing has been shipped out of it. A run that HAS emitted is open
    only while `emit` would still refuse it, which is `Decisions.blocking` and nothing else —
    the same question `app/src/readiness.ts:owed` asks the other side of the wire, asked here
    against the Python that actually refuses rather than against a third implementation of it.

    A MALFORMED CORPUS READS AS OPEN. `do_pipeline_pricing` already rules that an
    unreadable `inventory/prices.json` must not stop a screen drawing — the operator has to
    be able to SEE the file that is wrong. The same argument decides this: a run whose answers
    cannot be parsed is exactly the run somebody needs to open.
    """
    return bool(_run_owes(manifest, pricing, answers))


def _run_owes(manifest: dict, pricing: dict, answers: Optional[dict]) -> List[str]:  # noqa: D401
    """Why this run still has pricing work in it, in the words `emit` would refuse it with.

    THE PICKER DRAWS A REMAINDER RATHER THAN A TOTAL BECAUSE OF THIS FUNCTION. Every chip used
    to carry `counts.skus`, which is the SIZE of the job and never the job — box 2 at 109 SKUs
    is one `floor` press and box 3 at 199 is 117 real decisions. `counts.sub_threshold` and
    `counts.no_market_data` have ridden every poll since the manifest gained them and are read
    by nothing; they are the DENOMINATOR, and what a person wants is what is left.

    IT ASKS THE PYTHON THAT ACTUALLY REFUSES. `Decisions.blocking` is the one authority on
    what stops an `emit`, and a third implementation here to answer the same question would be
    exactly the drift this arrangement avoids. `app/src/readiness.ts` mirrors the same
    vocabulary for the open screen — BY HAND, and checked by nobody. This docstring said it was
    "audited against it" until 2026-09-05 and `scripts/docs-audit.py` has never read that file;
    the mirror is a convention two comments asserted and no row enforced.
    """
    if not manifest.get("joined"):
        return []
    try:
        answered = decisions.Decisions.parse(answers or {})
    except decisions.MalformedDecisions:
        return ["answers file cannot be read"]
    below = [
        row.get("sku")
        for row in pricing.get("skus") or []
        if row.get("bucket") == "sub_threshold"
    ]
    owes = list(answered.blocking(below))
    if not manifest.get("emitted"):
        # NEVER EMITTED IS WORK, AND IT IS THE COMMON CASE. Nothing has been shipped out of
        # this run, so it is open whatever its answers say — but it is listed AFTER the
        # blocking reasons, because a refusal names something to fix and this names something
        # to press.
        owes.append("never emitted")
    return owes


# THE CONFLICT HELPERS THAT STOOD HERE ARE DELETED, AND THE DELETION IS THE POINT (D86,
# amended). `_answer_for`, `_is_hold`, `_same_price` and `_conflict` detected one card answered
# two ways across runs — 8 SKUs on this machine, 3 of them a hold overridden by a later price.
# They were machinery for reconciling a duplication, and the duplication is gone: the answer
# lives once in `pipeline/corpus.py`, keyed by SKU, so a card cannot be answered two ways.
#
# Reporting a defect is worth less than making it unrepresentable, and the owner said so:
# *"why is it we've made a federalist state system when this is best done as a centralized
# system?"* What is kept below is `over_cap`, which is a different fact and still real — the
# CAP is spent per run against a global limit whatever the answers do.


def _policy_threshold(book) -> str:
    """The store's stored D9 cut-off, as a string, for a screen to draw and compare against.

    NEVER `None` AND NEVER A REFUSAL. The empty-store branch of `do_pipeline_worklist`
    answers `None` for both figures because there is nothing on screen to draw them over;
    here there is, and a threshold is a property of the STORE rather than of the runs in the
    worklist — so an unusable one falls back to the constant the partition would have used
    anyway rather than blanking a heading the rows are already sorted under.
    """
    try:
        return str(pricing_mod.check_threshold(book.policy_for()["threshold"]))
    except (ValueError, AttributeError, KeyError, TypeError):
        return str(pricing_mod.THRESHOLD)


# ----------------------------------------- every unsent copy in the store, counted live


class UnsentLedger(NamedTuple):
    """Which copies in every joined run TCGplayer does not hold yet, decided against the
    store as it stands NOW rather than as each run's `pricing.json` recorded it.

    `unsent` is sku -> the position keys (`box/index`) that may still go; `by_run` is
    run -> how many of that run's own positions are among them; `held_out` and `live_out`
    are the per-SKU figures the merge would carry (`pipeline/merge.py:_merged_match`).
    """

    unsent: Dict[str, List[str]]
    by_run: Dict[str, int]
    held_out: Dict[str, int]
    live_out: Dict[str, int]


def _run_live_by_sku(run: "run_files.Run") -> Dict[str, "run_resolve.LiveReading"]:
    """Each SKU's `Total Quantity` off the exports this run recorded, dated the way
    `cli/resolve.py:load` dates them — so the figure this route draws is the figure `emit`
    computes for the same leg, and not a second reading of the same file.

    AN EXPORT THAT HAS MOVED COSTS THE RUN ITS READING AND NOTHING ELSE. `_copies_out`
    keeps the store's own figure for a SKU no file reports (D87), which is exactly the
    answer a run whose file is gone should get here: the send will refuse it by name
    (`exports_for`), and this route says what the store knows in the meantime.
    """
    parsed: Dict[Path, tcgcsv.Export] = {}
    as_of: Dict[Path, str] = {}
    for path in set(run.exports_by_game.values()):
        try:
            parsed[path] = tcgcsv.read_export(path)
            as_of[path] = str(run_files.describe_source(path)["mtime"])
        except (OSError, ValueError, KeyError):
            continue
    return run_resolve._live_by_sku(parsed, as_of)


def _catalog_rows(
    tables: Sequence[Tuple["run_files.Run", dict]], wanted: set
) -> "Dict[str, Tuple[tcgcsv.Row, str]]":
    """The export row for each wanted SKU, with the game whose catalogue named it.

    FOR THE SKUS A REVIEW ANSWER STAMPED AND NO TABLE CARRIES, and for nothing else: the
    caller passes the handful the ledger found, so the early return costs a screen with no
    such answers exactly nothing. On a store that has some, this is one parse per export the
    chosen runs recorded — the same files `_run_live_by_sku` reads, and the same refusal
    posture, since a file that has moved simply does not answer for its SKUs.

    FIRST FILE WINS, WALKING THE RUNS IN THE ORDER THE CALLER CHOSE THEM — ascending name
    order, which is ascending date, so the OLDEST export that still carries the SKU answers.
    That is deliberate and it is the conservative direction: the row is only ever used to
    compose a row for a card whose copies are on the shelf, and the newest reading of its
    PRICE is not here to be had — a SKU no table names is one no recent join priced. The row
    carries its own `TCG Market Price` cell and `#/pricing` draws the age of the run beside
    it, which is the existing sentence for "this reading is as old as its run".

    A SKU NO EXPORT NAMES IS SIMPLY ABSENT from the result, and the caller then draws no row
    for it. That is not a silent drop: the copies stay counted in `unreachable` and in the
    run's own `unsent`, and the operator's door is `Join again` — which is the one case where
    a re-join really is the answer, because the catalogue on hand does not describe the card.
    """
    found: "Dict[str, Tuple[tcgcsv.Row, str]]" = {}
    if not wanted:
        return found
    for run, _table in tables:
        if len(found) == len(wanted):
            break
        for game, path in run.exports_by_game.items():
            try:
                export = tcgcsv.read_export(path)
            except (OSError, ValueError, KeyError):
                continue
            for row in export.rows:
                sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
                if sku in wanted and sku not in found:
                    found[sku] = (row, game)
    return found


def _unsent_ledger(
    inventory: master.Inventory, tables: Sequence[Tuple["run_files.Run", dict]]
) -> UnsentLedger:
    """THE ARITHMETIC `emit` DOES, DONE HERE SO THE SCREEN AGREES WITH THE PRESS
    (D156).

    `pricing.json` froze `add_to_quantity`, `committed` and `copies_out` at the moment of the
    JOIN, and every emit since has moved what they describe: a run emitted under the old
    standing cap of four wrote `add 4 · backstock 3` and closed, and the three copies it held
    back went on reading `4 of 7` on every later visit while `emit` — which re-derives the
    join against the live store — would have offered exactly those three. Measured on the
    owner's store on 2026-09-11: 387 copies across 138 SKUs sat in runs this screen no longer
    opened, and every one of them drew a figure the press disagreed with.

    IT IS `cli/resolve.py`'s OWN FUNCTIONS AND NOT A RESTATEMENT OF THEM. `_live_by_sku`
    reads each run's recorded export the way `load` reads it and keeps the NEWEST reading of
    a SKU across every file, which is D87's rule; `_copies_out` answers what TCGplayer holds
    per SKU off that reading and the store's own; `_committed_keys` spends the figure on
    positions — oldest capture first (D147) — and the same set
    subtraction `SkuMatch.uncommitted_positions` makes decides what is left. A copy in a
    TERMINAL state is committed by the same arm `load` uses for one. Nothing here is a third
    implementation of the claim, which is what would have let the two figures drift again.

    ONE READING PER SKU AND ONE `_copies_out`, WHERE THE SEND RESOLVES ONE PER LEG. That
    function walks every listing the store holds with two queries each — measured at 0.9s
    per call on the owner's 492 listings — and ten legs would put nine seconds in front of
    every reload. The newest reading is what `Listing.live_reading` would have picked inside
    each leg anyway; the one shape where the two answers differ is two legs of one SKU whose
    OLDER export read higher than the newer, where `pipeline/merge.py:_merged_match` keeps
    the larger and calls that a stand-in in its own words. On a store that reconciles, the
    store's reading is newer than both files and the case does not arise.

    A COPY STAMPED SINCE THE JOIN IS COUNTED, because the send counts it. A review answer
    writes `sku` onto a record after `pricing.json` was written, and `load` adopts that
    identity on the next resolve; so a SKU's positions here are the tables' union PLUS every
    copy on hand carrying the SKU whose `run` is one of these runs. Measured on the owner's
    store: 74 copies across the ten joinable runs were in no table and in the press.

    THE KEY IS READ AS STORED AND NEVER REALIGNED (D36), which is the posture of every other
    reader on this route: `box` and `index` are the store key the photograph is addressed by,
    and `paperwork_for` — the one reader that does realign — hashes every photograph in the
    box to do it, which is not a cost a screen's reload may carry. A mid-box delete since the
    join therefore counts the card now standing at the slid key, and the send, which does
    realign, corrects it. NO CAP IS SPENT HERE. This previews the worklist; `--cap` and a
    row's own quantity are asked for at the press and spent there (D7).

    ONE `_cards_by_sku` READ FOR THE WHOLE FUNCTION (store-scaling item 4). Every per-SKU
    walk below — the orphan scan that used to be `distinct("sku")` plus a `copies_on_hand`
    loop, the on-screen fold-through's own `copies_on_hand` loop, and `_copies_out`'s and
    `_committed_keys`' own internal per-SKU reads — shares the SAME one-pass dict, built once
    here and handed down, rather than each re-walking `cards` on its own.
    """
    by_sku = run_resolve._cards_by_sku(inventory)
    positions: Dict[str, "OrderedDict[str, None]"] = OrderedDict()
    per_run: Dict[str, Dict[str, set]] = {}
    readings: Dict[str, "run_resolve.LiveReading"] = {}
    for run, table in tables:
        mine: Dict[str, set] = per_run.setdefault(run.name, {})
        for row in table.get("skus") or []:
            if not isinstance(row, dict):
                continue
            sku = str(row.get("sku") or "")
            if not sku:
                continue
            for at in row.get("positions") or []:
                if not isinstance(at, dict) or at.get("box") is None or at.get("index") is None:
                    continue
                key = master.position_key(int(at["box"]), int(at["index"]))
                positions.setdefault(sku, OrderedDict())[key] = None
                mine.setdefault(sku, set()).add(key)
    on_screen = set(per_run)

    # ------------------------------------------------------------------------------------
    # A SKU NO TABLE CARRIES IS STILL THIS STORE'S COPY (the review answer's fold-through).
    #
    # The union below used to iterate `positions` — the SKUs some run's `pricing.json`
    # already names — so a review answer only counted when a SIBLING copy of the same card
    # had resolved at join time. A card whose answer named a SKU no table carried had no row
    # to be counted onto, and so appeared on `#/pricing` nowhere at all: the operator
    # answered it by hand and the only way to make it reachable was to press Join again on
    # another screen, which is the chore the owner named — *"after finishing review queue
    # having to do 'join' again, is so fucking unintuitive."*
    #
    # Measured on the owner's store 2026-09-12: of 489 hand-answered copies still on hand,
    # 458 carried a SKU some table names and folded through already; **31 copies across 17
    # SKUs carried one no table names** and were invisible. Three runs held them —
    # `2026-08-29-box1-01` 18, `2026-09-01-box5-01` 9, `2026-09-11-box1-01` 4.
    #
    # `by_sku` IS ALREADY ONE FULL PASS OVER `cards` (store-scaling item 4), so "every SKU
    # any card carries" is just its key set — no second `distinct("sku")` scan, and no
    # `copies_on_hand` call per orphan SKU either, since `by_sku` already carries every row
    # (state, box, index, run) that call would have re-read from the store. The orphan set
    # is tiny by construction — it is the answers a join has not seen yet.
    orphans: List[str] = sorted(sku for sku in by_sku if sku not in positions)
    for sku in orphans:
        for row in by_sku.get(sku, ()):
            if row.state in master.TERMINAL_STATES or row.run not in on_screen:
                continue
            positions.setdefault(sku, OrderedDict())[row.key] = None
            per_run[row.run].setdefault(sku, set()).add(row.key)
    # ------------------------------------------------------------------------------------

    # THIS LEG'S READING FOR THIS LEG'S OWN SKUS, AFTER THE ORPHANS ARE IN. Narrowed before
    # anything walks it — a Filtered Export names ~10,000 SKUs and a per-SKU answer does not
    # depend on the other 9,800 — and folded newest-wins per SKU across legs, which is
    # `_live_by_sku`'s own rule across the files of one run. It reads `per_run` rather than a
    # local because the orphan pass above may have added SKUs to this leg since the tables
    # were walked, and a reading this loop skipped would leave `_copies_out` answering off
    # the store alone for a SKU whose own export reports it.
    for run, _table in tables:
        mine = per_run.get(run.name) or {}
        for sku, reading in _run_live_by_sku(run).items():
            if sku not in mine:
                continue
            held = readings.get(sku)
            if held is None or master.newer_stamp(reading.as_of, held.as_of):
                readings[sku] = reading

    for sku in list(positions):
        for row in by_sku.get(sku, ()):
            if row.state in master.TERMINAL_STATES:
                continue
            if row.run in on_screen and row.key not in positions[sku]:
                positions[sku][row.key] = None
                per_run[row.run].setdefault(sku, set()).add(row.key)

    held_out, live_out = run_resolve._copies_out(inventory, readings, by_sku=by_sku)
    committed = run_resolve._committed_keys(inventory, held_out, by_sku=by_sku)
    unsent: Dict[str, List[str]] = {}
    for sku, keys in positions.items():
        free: List[str] = []
        for key in keys:
            card = inventory.cards.get(key)
            if card is None or card.state in master.TERMINAL_STATES:
                continue
            # A RECORD RE-IDENTIFIED SINCE THE JOIN IS NOT THIS SKU'S COPY ANY MORE — the
            # review answer or a later emit stamped it with the card it actually is.
            if card.sku and str(card.sku) != sku:
                continue
            if key in committed:
                continue
            free.append(key)
        unsent[sku] = free
    by_run = {
        name: sum(len(keys & set(unsent.get(sku, ()))) for sku, keys in mine.items())
        for name, mine in per_run.items()
    }
    return UnsentLedger(unsent=unsent, by_run=by_run, held_out=held_out, live_out=live_out)


def _on_hand_by_run(inventory: master.Inventory) -> Dict[str, int]:
    """run name -> how many of its cards this store still HOLDS. One column read, once.

    THE FIGURE A WARNING ABOUT A RUN HAS TO CARRY, and the reason it is counted off the
    CARDS rather than off the run directory: a run's `identifications.json` records what was
    read, and what a stranded run is withholding is what is still on a shelf — which is
    smaller every time one of its cards sells and is zero once its drawer is deleted.
    Measured on the owner's store: `2026-08-29-box1-01` read 133 cards and holds 99.

    SOLD AND RETIRED ARE NOT ON HAND and are not counted; a buried record is not in this
    table at all (D134). `cards.select` reads two indexed columns and builds no card
    objects (D88), so this is one pass over the store rather than `_copies_out`'s per-run
    full-table scan — which is ~1s a call on this machine and was never meant for a loop.
    """
    counts: Dict[str, int] = {}
    for _key, (run, state) in inventory.cards.select(("run", "state")):
        if not isinstance(run, str) or not run.strip():
            continue
        if state in (master.SOLD, master.RETIRED, master.MOVED):
            continue
        counts[run] = counts.get(run, 0) + 1
    return counts


def _unreachable(inventory: master.Inventory, review_count: int, root: Path) -> dict:
    """The copies NO worklist can offer, named rather than left out (`CLAUDE.md`: never
    silently drop a card). Each figure is a door to the screen that can move it.

    `captured` has never been identified — `#/runs` is the press. `in_review` is waiting on
    a person at `#/review`. `unjoined` is identified and never joined, run by run, and
    `reallocated` is a run over a drawer whose number was deleted and reused (D36), which
    no join can reach and which is left out of the union above for exactly that reason —
    counted here, it would offer the NEW drawer's cards under the OLD run's identities.

    EVERY ROW CARRIES A CARD COUNT, BECAUSE A RUN IS NOT A QUANTITY. Both lists were drawn
    as a number of RUNS, so `2 runs over a deleted box` read identically whether the store
    was withholding nothing or was withholding a hundred sellable cards — and on the
    owner's machine it was saying both at once: `2026-08-22-box1-03` has 0 cards left on
    hand and `2026-08-29-box1-01` has 99, all identified and all carrying a SKU. The
    operator could not tell the false alarm from the real stranded stock.
    """
    unjoined: List[dict] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / run_files.MANIFEST).is_file():
            continue
        manifest = _manifest(entry)
        if manifest.get("joined") or _live_pid(entry) is not None:
            continue
        try:
            cards = len(run_files.open_run(entry).read_identifications().get("cards") or {})
        except (run_files.RunError, OSError, ValueError, AttributeError):
            cards = 0
        unjoined.append({"run": entry.name, "cards": cards})
    return {
        "captured": inventory.counts().get(master.CAPTURED, 0),
        "in_review": review_count,
        "unjoined": unjoined,
        # filled by the caller, which is the one that walked the joined runs
        "reallocated": [],
    }


def do_pipeline_worklist(wanted: Sequence[str]) -> dict:
    """`GET /pipeline/pricing` — one pricing worklist over several runs (D86), and since
    D156 the standing list of EVERY COPY THE STORE HOLDS THAT TCGPLAYER
    DOES NOT, across every joined run.

    THE WORKLIST SPANS RUNS, AND SO DOES THE ANSWER. D48's resolution — a send is a cart of
    boxes and a run is still one box, because a run carries a reading that is a property of
    what is in the drawer — stays true of the READING. What this route adds is a VIEW across
    runs; the answer is the corpus's (D86, amended), and there is one write, `PUT /pricing`,
    whatever is on screen.

    WHAT "OPEN" MEANS WIDENED, AND THAT IS THE WHOLE OF THE UNSENT WORKLIST. A run was open
    while `emit` would still refuse it or had never run; a run that had emitted and been
    answered closed, and every copy it had held back — under the old standing cap of four,
    or under a `--cap` or a per-card quantity since — closed with it. The operator's words:
    *"the only time it's intuitive to push supply is right when pricing a run, which
    shouldn't be the case."* A run is open now while it OWES something OR HOLDS AN UNSENT
    COPY, `roster[].unsent` says how many, and the default landing — no `?run=` — is
    therefore every copy anywhere in the store that can still go out, priced where prices
    are decided and sent by the press that already writes one file across runs
    (`POST /pipeline/emit`). `owes` itself is untouched: it is still emit's own refusal
    vocabulary plus "never emitted", which is what Home's "runs to price" counts.

    AND THE FIGURES ARE LIVE. Every merged row's `add_to_quantity`, `committed`, `copies_out`
    and `listing` are re-derived against the store as it stands by `_unsent_ledger`, which
    is `cli/resolve.py`'s own arithmetic and not a copy of it; the stored table's figures are
    the join's record and are not served. `claimed_add` keeps what the runs' tables SAY, so
    `over_cap` still names a table the press disagrees with.

    WHY A ROUTE RATHER THAN N FETCHES FROM THE CLIENT. Two reasons and the second is the one
    that matters. The default landing is every open run, which on this machine is eight tables
    totalling ~909KB — eight round trips before a screen draws. And two tables fetched either
    side of a `join` describe different worlds: `do_pipeline_pricing` already spends a
    paragraph on why its own two files are read together, and a client-side union would
    reintroduce exactly that straddle between runs instead of within one.

    `?run=` REPEATS RATHER THAN CARRYING A COMMA LIST — `/trends` and `/scope`'s rule, for
    their reason: a comma inside a value is indistinguishable from the separator. With none,
    the handler picks every OPEN run itself; see `_run_is_open`. An explicitly named run is
    taken whether or not it is open, because a screen asking for a specific run has already
    answered the question this filter exists to answer.

    IT IS A READ AND IT PRESSES NOTHING. No child, no socket, no write — the same posture as
    `do_pipeline_pricing`, which this delegates the per-run half of the work to rather than
    re-implementing. A run that refuses (never joined, unreadable table) is REPORTED in
    `skipped` and does not take the others down with it: an operator whose eight-run worklist
    would not draw because one directory is half-written is worse off than one who is told
    which directory that is. A run over a REALLOCATED drawer (D36) is skipped the same way,
    under `box_reallocated`, whether or not it was asked for: the send refuses it outright,
    and its positions now belong to another drawer's cards.
    """
    root = files.runs_dir()
    if not root.is_dir():
        return {
            "runs": [],
            "skus": [],
            "roster": [],
            "skipped": [],
            "asked": list(wanted),
            "threshold": None,
            "floor": None,
            "unreachable": {"captured": 0, "in_review": 0, "unjoined": [], "reallocated": []},
        }

    names = _box_names()
    asked = [str(name) for name in wanted if str(name).strip()]

    # EVERY JOINED RUN AND WHAT IT STILL OWES — the picker's own list, and deliberately not
    # the worklist's. The picker has to draw runs that are NOT loaded (that is what makes it a
    # picker), and it has to say which of them are worth loading. One pass, reusing the reads
    # the chooser below needs anyway.
    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError):
        # A CORPUS THAT CANNOT BE PARSED MUST NOT BLANK THE SCREEN — the operator has to be
        # able to SEE the file that is wrong. Every run then reads as owing an answer, which
        # is the honest reading of "nobody can tell what has been answered".
        book = corpus.Corpus()

    # THE STORE, ONCE, FOR EVERYTHING BELOW THAT COUNTS A COPY. Lock-free like every other
    # read on this route: a screen must not serialise behind a running `./pkmnscan join`.
    try:
        snapshot: Optional[Snapshot] = Store().read()
    except (files.StoreError, OSError, ValueError, TypeError):
        snapshot = None

    # ONE PASS, BEFORE THE RUN LOOP, because the loop asks this question once per run and
    # the answer is one read of two columns for the whole store.
    on_hand = None if snapshot is None else _on_hand_by_run(snapshot.inventory)

    roster: List[dict] = []
    owed_by_run: Dict[str, List[str]] = {}
    reallocated: List[dict] = []
    # THE TABLES THE LEDGER IS DERIVED OVER — every joined run whose drawer is still its own.
    tables: List[Tuple["run_files.Run", dict]] = []
    parsed_by_run: Dict[str, dict] = {}
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / run_files.MANIFEST).is_file():
            continue
        manifest = _manifest(entry)
        if not manifest.get("joined"):
            continue
        table = entry / run_files.PRICING
        parsed: dict = {}
        answers: Optional[dict] = None
        summary = _summary(entry, names)
        try:
            if table.is_file():
                parsed = json.loads(table.read_text("utf-8"))
            # THE ANSWERS ARE THE CORPUS'S, SCOPED TO THIS RUN (D86, amended). One read for the
            # whole roster would be cheaper and would be wrong: `_run_owes` asks what `emit`
            # would refuse THIS run for, and that question is about this run's own rows.
            answers = (
                book.scoped_to(
                    {str(row.get("sku")) for row in parsed.get("skus") or []},
                    run_name=entry.name,
                ).to_payload()
                if parsed
                else None
            )
        except (OSError, ValueError, decisions.MalformedDecisions):
            owed_by_run[entry.name] = ["run files cannot be read"]
            roster.append(
                {**summary, "owes": owed_by_run[entry.name], "open": True, "unsent": 0}
            )
            continue
        if summary.get("box_former"):
            # A RUN OVER A DRAWER THAT NO LONGER EXISTS (D36). Never open, never in the
            # union: its positions are another drawer's cards now, and `emit` refuses it by
            # name. Drawn in the picker as `Box N (deleted)` so the operator can see why.
            # THE COUNT IS WHAT MAKES THIS ROW READABLE (see `_unreachable`). None where
            # the store would not open — unknown is not zero, and a warning that silently
            # became "nothing to see" on an unreadable store would be the worst of the two.
            reallocated.append(
                {
                    "run": entry.name,
                    "box": summary.get("box"),
                    "cards": None if on_hand is None else on_hand.get(entry.name, 0),
                }
            )
            roster.append({**summary, "owes": [], "open": False, "unsent": 0})
            continue
        owes = _run_owes(manifest, parsed, answers)
        owed_by_run[entry.name] = owes
        parsed_by_run[entry.name] = parsed
        if parsed:
            tables.append((run_files.open_run(entry), parsed))
        roster.append({**summary, "owes": owes, "open": bool(owes), "unsent": 0})

    ledger: Optional[UnsentLedger] = None
    if snapshot is not None and tables:
        ledger = _unsent_ledger(snapshot.inventory, tables)
        for row in roster:
            held = ledger.by_run.get(row["run"], 0)
            row["unsent"] = held
            # OPEN WHILE IT HOLDS AN UNSENT COPY, whatever its answers say. `owes` is left
            # exactly as `_run_owes` wrote it — Home counts "runs to price" off it, and a
            # run that is priced and merely under-sent is not one of those.
            row["open"] = bool(row["open"] or held > 0)

    # AN EXPLICIT ASK WINS OVER THE FILTER, whether or not the run is open: naming a run has
    # already answered the question `open` exists to ask, and an answered run has to stay
    # openable — that is how a price gets looked at again.
    former = {row["run"] for row in reallocated}
    chosen = [name for name in (asked or [row["run"] for row in roster if row["open"]])]

    summaries: List[dict] = []
    written_at: Dict[str, int] = {}
    skipped: List[dict] = []
    # sku -> merged row. An `OrderedDict` because the ORDER IS THE HIERARCHY on this screen
    # (D78) and the first run to mention a SKU is what seeds its place; the sort that decides
    # the final order is the client's, over the same fields it already sorts one run by.
    merged: Dict[str, dict] = OrderedDict()

    for name in chosen:
        if name in former:
            skipped.append(
                {
                    "run": name,
                    "code": "box_reallocated",
                    "message": (
                        f"Run {name} describes a drawer whose number was deleted and reused "
                        f"since (D36); its positions are another drawer's cards now and "
                        f"`emit` refuses it. Re-identify the box as it is today."
                    ),
                }
            )
            continue
        try:
            payload = do_pipeline_pricing(name)
        except PipelineRefusal as exc:
            skipped.append({"run": name, "code": exc.code, "message": str(exc)})
            continue
        directory = _open_run(name)
        summaries.append(_summary(directory, names))
        if payload.get("written_at") is not None:
            written_at[name] = payload["written_at"]
        for row in payload["pricing"].get("skus") or []:
            sku = str(row.get("sku") or "")
            if not sku:
                continue
            leg = dict(row)
            leg["run"] = name
            here = merged.get(sku)
            if here is None:
                # THE WHOLE ROW, NOT A CHOSEN SUBSET. A merged entry has to BE a `PricingSku`
                # — `app/src/Pricing.tsx` draws sixteen export cells, a snap table, a presets
                # map and a positions list off it, and a server that lifted "the fields the
                # screen needs today" would be choosing what matters from the wrong file, the
                # thing D49 wrote `row` verbatim to avoid. The aggregate fields below are the
                # only ones that differ from a single run's, and each says why.
                merged[sku] = dict(row)
                merged[sku]["in"] = [leg]
            else:
                # NEWEST RUN WINS EVERY CARD FACT. `chosen` walks the runs directory in
                # ascending name order and run names are date-prefixed, so the last leg
                # appended is the newest — it read the newest export, and the bucket is
                # decided by that export's Market cell alone (`pipeline/join.py:prices_for`).
                # Taking the row and the bucket together keeps them one reading rather than
                # two halves of different ones.
                legs = here["in"] + [leg]
                # POSITIONS CONCATENATE AND DEDUPE ON `(box, index)`, AND THE DEDUPE IS NOT
                # DEFENSIVE — IT IS THE COUNT. Box 3 has been joined three times on this
                # machine, so its cards appear in three runs; summing each run's `copies`
                # made Void Assault twelve copies of a card there are seven of. The physical
                # copies are the distinct positions and nothing else, which is also how
                # `pipeline/join.py:uncommitted_positions` counts them.
                seen = {(p.get("box"), p.get("index")) for p in here.get("positions") or []}
                positions = list(here.get("positions") or [])
                for place in row.get("positions") or []:
                    if (place.get("box"), place.get("index")) not in seen:
                        seen.add((place.get("box"), place.get("index")))
                        positions.append(place)
                merged[sku] = dict(row)
                here = merged[sku]
                here["in"] = legs
                here["positions"] = positions
                here["copies"] = len(positions)

    loaded_names = {row["run"] for row in summaries}
    views = (
        run_resolve.box_views(snapshot.inventory) if snapshot is not None and ledger else {}
    )

    # ------------------------------------------------------------------------------------
    # THE ROW A REVIEW ANSWER EARNED, COMPOSED HERE BECAUSE NO TABLE CARRIES IT.
    #
    # `_unsent_ledger` now finds a SKU the store holds that no joined run's `pricing.json`
    # names — a card the operator identified by hand since the join. The loop below draws
    # every merged row's live figures, and it can only draw a row that EXISTS, so without
    # this the ledger would count those copies in `by_run` and the screen would show no row
    # to price them on: the run would read `3 unsent` and offer nothing.
    #
    # THE ROW IS THE JOIN'S OWN (`pipeline/worklist.py:sku_row`) AND NOT A SECOND
    # DESCRIPTION OF IT. Twenty fields with four arithmetic ones is not a shape to write
    # twice — `over_cap` and `claimed_add` a few lines down exist because two descriptions
    # of one send disagreed once already. The `SkuMatch` handed to it is composed from the
    # export row the card's own run recorded, the positions the ledger says may still go,
    # and the store's policy; every figure it computes is `pipeline/join.py`'s.
    #
    # `claimed_add` IS ZERO AND THAT IS THE HONEST ANSWER. That field is what the runs'
    # TABLES believe they may add, and no table believes anything about this SKU — so the
    # single leg carries `add_to_quantity: 0` and `over_cap` stays False. What CAN go is
    # `add_to_quantity`, written by the loop below off the live store like every other row.
    if ledger is not None and snapshot is not None:
        orphans = {
            sku for sku, keys in ledger.unsent.items() if keys and sku not in merged
        }
        policy = book.policy_for()
        for sku, (export_row, game) in _catalog_rows(tables, orphans).items():
            places = []
            for key in ledger.unsent.get(sku, []):
                card = snapshot.inventory.cards.get(key)
                if card is None or card.run not in loaded_names:
                    continue
                places.append(
                    views.get(int(card.box), join.BoxView()).at(card.box, card.index)
                )
            if not places:
                continue
            match = join.SkuMatch(
                sku=sku,
                row=export_row,
                positions=places,
                threshold=pricing_mod.check_threshold(policy.get("threshold")),
                rule=pricing_mod.Rule.parse(str(policy.get("rule", "match"))),
                basis=str(policy.get("basis", "market")),
                held_out=ledger.held_out.get(sku),
                live_out=ledger.live_out.get(sku),
            )
            record = snapshot.inventory.listings.get(sku)
            built = worklist.sku_row(
                match,
                game,
                worklist.bucket_for(
                    match,
                    below=match.has_market_data and not match.listable,
                    unpriced=not match.has_market_data,
                ),
                None
                if record is None
                else {
                    "pushed": int(record.pushed),
                    "staged": int(record.staged),
                    "live": int(record.live),
                    "sold_here": int(record.sold_here),
                },
            )
            # THE LEG NAMES THE RUN THE COPY BELONGS TO, so `app/src/pricingSource.ts` can
            # say where it came from rather than falling back to whichever run is in scope.
            owner = snapshot.inventory.cards.get(
                next(iter(ledger.unsent.get(sku, [])), "")
            )
            leg = dict(built)
            leg["run"] = (owner.run if owner is not None else None) or next(
                iter(sorted(loaded_names)), ""
            )
            leg["add_to_quantity"] = 0
            built["in"] = [leg]
            merged[sku] = built
    # ------------------------------------------------------------------------------------

    for sku, row in merged.items():
        # THE CAP, COMPUTED ONCE ACROSS THE RUNS THIS SCREEN IS SHOWING.
        #
        # `pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` per RUN against a
        # cap that is global, so two runs joined before either emitted each spend the same
        # room. Measured on 2026-09-01: a cart joined boxes 3, 4 and 5 in the same second, five
        # SKUs' per-run claims summed past four, and two of them went on to reach `pushed: 6`
        # in the store against a cap of 4. That is D59's defect one register up — it fixed
        # per-BOX capping inside one join, and this is per-RUN capping across joins that never
        # saw each other.
        #
        # `claimed_add` IS WHAT THE RUNS' TABLES SAY AND `add_to_quantity` IS WHAT CAN
        # ACTUALLY GO. Drawing the sum would put "7" in the Qty column of a card four of which
        # may be listed, which is the same false-sentence failure D59 named.
        claimed = sum(leg.get("add_to_quantity") or 0 for leg in row["in"])
        held = len(row.get("positions") or [])
        row["claimed_add"] = claimed
        if ledger is None:
            # THE STORE COULD NOT BE READ. The tables' own figures are all there is, and the
            # merge over positions is still the deduped union (D7, amended 2026-09-08).
            row["add_to_quantity"] = min(claimed, held)
        else:
            # THE LIVE FIGURE (D156): the copies of this card, across
            # every run on screen, that the store says TCGplayer does not hold and that have
            # not left a box — `_unsent_ledger`'s docstring is the argument. `copies` is the
            # union; `committed` is what is not free; `copies_out` and `listing` are the
            # store's own, so the row's sentences describe now and not the join.
            drawn = {
                master.position_key(int(p["box"]), int(p["index"]))
                for p in row.get("positions") or []
                if p.get("box") is not None and p.get("index") is not None
            }
            # A COPY THE SEND COUNTS THAT NO TABLE DREW — stamped by a review answer after
            # the join — joins the row's positions here, labelled off the live store like
            # every other, so the Qty cell's denominator is the copies the press will see.
            for key in ledger.unsent.get(sku, []):
                if key in drawn:
                    continue
                card = snapshot.inventory.cards.get(key) if snapshot is not None else None
                if card is None or card.run not in loaded_names:
                    continue
                row.setdefault("positions", []).append(
                    {
                        "box": card.box,
                        "index": card.index,
                        "label": _position_label(views, snapshot.inventory, card.box, card.index),
                    }
                )
                drawn.add(key)
            free = [key for key in ledger.unsent.get(sku, []) if key in drawn]
            held = len(row.get("positions") or [])
            row["add_to_quantity"] = len(free)
            row["copies"] = held
            row["committed"] = held - len(free)
            row["backstock"] = 0
            row["copies_out"] = ledger.held_out.get(sku, row.get("copies_out") or 0)
            row["at_cap"] = len(free) == 0
            row["nothing_to_add"] = (
                "every copy is already at TCGplayer or has left the box" if not free else None
            )
            entry = snapshot.inventory.listings.get(sku) if snapshot is not None else None
            if entry is not None:
                row["listing"] = {
                    "pushed": int(entry.pushed),
                    "staged": int(entry.staged),
                    "live": int(entry.live),
                    "sold_here": int(entry.sold_here),
                }
        row["over_cap"] = claimed > row["add_to_quantity"]
        # A MERGED ROW THAT CAN ADD MUST NOT CARRY ONE RUN'S REASON FOR ADDING NOTHING.
        # `nothing_to_add` reads "every copy in this run is already listed or has left the
        # box" — true of that leg, false of the merge the moment another leg can add.
        if row["add_to_quantity"] > 0:
            row["nothing_to_add"] = None
            row["at_cap"] = False

    unreachable = (
        _unreachable(snapshot.inventory, len(snapshot.review), root)
        if snapshot is not None
        else {"captured": 0, "in_review": 0, "unjoined": []}
    )
    unreachable["reallocated"] = reallocated

    return {
        "runs": summaries,
        "skus": list(merged.values()),
        # NO PER-RUN `decisions` AND NO PER-RUN `defaults` (D86, amended 2026-09-02). Both
        # were served for a screen that seeded and wrote one document per run; the answer is
        # the corpus's, read once through `GET /pricing`, and a payload carrying eight copies
        # of it keyed by run was a shape nothing read for a day and a half.
        "written_at": written_at,
        "roster": roster,
        "skipped": skipped,
        "asked": asked,
        # THE TWO RUN-WIDE FIGURES A ROW IS DRAWN AGAINST, OFF THE NEWEST RUN DRAWN. The
        # screen prints "Below $X" over the sub-threshold section and "At the $Y floor" on a
        # button; both are `pipeline/pricing.py` constants that every run on this machine
        # agrees about, and taking them off the newest table rather than restating them here
        # keeps the one place they are decided the one place they are read.
        # BOTH ARE THE STORE'S STORED POLICY, AND THEY ARE ONE FIGURE (D9, amended
        # 2026-09-09). `policy.threshold` is the market price at or above which a card earns a
        # listing AND the cheapest price this store lists anything at, so `SkuMatch.list_price`
        # clamps at it and a markdown may not go below it. Two keys on the wire because the
        # screen draws them in two sentences, one source because a second one drifts.
        #
        # THE FLOOR CAME OFF THE NEWEST RUN'S `pricing.json` UNTIL THIS AMENDMENT, and while
        # that cell held `pipeline/pricing.py`'s constant it was the reason the screen said
        # "clamped at the $0.40 floor" to a store whose cut-off was $0.29. A run's table is a
        # RECORD of what one join partitioned by — right for a history, stale the hour after
        # the cut-off moves — which is the argument `threshold` already made on the line
        # above; the floor simply had not been given it.
        "threshold": _policy_threshold(book),
        "floor": _policy_threshold(book),
        # WHAT NO WORKLIST CAN OFFER, NAMED (D156). A copy never
        # identified, one waiting in review, one in a run nobody has joined, and one in a run
        # over a reallocated drawer are each a door to another screen rather than a row here.
        "unreachable": unreachable,
        # `remembered_sub_threshold` IS GONE, HERE AND FROM THE PER-RUN ROUTE (D86, amended
        # 2026-09-02). It walked up to five sibling run directories for the newest answer to a
        # question each run had to be asked separately, and offered it as a LABEL because D9
        # forbade defaulting it. There is one answer now — the corpus's policy, with a default
        # (D9 amended) — so nothing has to be remembered and no screen offers anything.
    }


# ------------------------------------------------------- what every card on hand is worth


#: One SKU's most recently observed market price, and where it came from — now a row of the
#: `readings` table (`store/readings.py`) rather than a value this function computed. Aliased
#: under its old private name because every caller below still reads `reading.market`,
#: `.at`, `.source`, `.name`, `.set_name` and `.condition` exactly as it always did.
_Reading = store_readings.Reading


def _readings() -> Tuple[Dict[str, _Reading], List[dict]]:
    """`sku -> the NEWEST market price this machine has read for it`, and where each came from.

    A SELECT AGAINST `readings`, AND NOTHING ELSE (D189). This function used to
    walk every run's `pricing.json` and the newest live export on every call, comparing two
    sources on a clock and reporting which files answered — the two-source arbitration
    `pipeline/readings.py:collect` still does, word for word, but only when
    `pkmnscan readings adopt --write` runs it. What lives here now is the read half of that
    split: `store.readings.Readings` is a snapshot field like every other table (D88), and
    this function's whole job is turning it back into the `(sku -> reading, sources)` shape
    every caller below already expects.

    THE OLD DOCSTRING'S MEASUREMENT STILL EXPLAINS WHY TWO SOURCES EXIST AND WHY NEITHER
    ALONE IS ENOUGH, and it now lives on `pipeline/readings.py:collect`, which is where the
    comparison actually happens. What changed is WHEN it happens: on every `GET
    /pipeline/value` before this, and only on an explicit `readings adopt` press now. A
    caller reading `_readings()` between two adopts sees the table as of the last one, not
    the filesystem as of this instant — the read-once/write-many trade this table exists to
    make, argued in D189.

    IT NEVER RAISES, exactly as before: an unreadable store answers with an empty reading
    rather than a 500, because `do_pipeline_value` already refuses loudly on the read one
    call above this one, and `#/pricing`'s value screen would rather draw with no prices than
    not draw at all.
    """
    try:
        snapshot = Store().read()
    except (files.StoreError, OSError, ValueError, TypeError):
        return {}, []
    found: Dict[str, _Reading] = dict(snapshot.readings.entries)
    sources = snapshot.readings.sources_payload()
    return found, sources


#: Why a card on hand carries no market price. Three causes, three remedies, and a screen
#: that collapsed them would be telling the operator to do one thing for three problems.
_NEVER_IDENTIFIED = "never_identified"
_READ_NOTHING = "read_nothing"
_NO_READING = "no_reading"


def _market_of(text) -> Optional[Decimal]:
    """A market cell as money, or `None` for anything that is not money. It never raises.

    `tcgcsv.parse_price` RAISES ON A CELL THAT IS NOT A NUMBER, and that is right where it is
    used — every other caller is reading a file the operator is about to upload, where a
    malformed price has to stop the write rather than be quietly dropped. Here the same cell
    is one row of two thousand on a screen, and the reading this route can honestly give is
    "no price", which `do_pipeline_value` then reports as `no_reading` with the rest.

    NEVER A ZERO, WHICH IS THE WHOLE REASON THIS IS A FUNCTION. Coercing an unreadable cell to
    `Decimal("0")` ranks the card at the very bottom of the cheap band and sweeps it into a
    bulk pull — a wrong answer wearing the shape of a confident one, which is the failure this
    repo refuses everywhere it prices.
    """
    try:
        return tcgcsv.parse_price(str(text or ""))
    except (ArithmeticError, ValueError, TypeError):
        return None


def do_pipeline_value() -> dict:
    """`GET /pipeline/value` — every card on hand, with what it is worth and where it sits.

    THE QUESTION IS PHYSICAL AND SO IS THE UNIT: one row per COPY, never per SKU. The owner
    asked to *"immediately see either the most valuable or least valuable cards so maybe i
    can easily start querying them for bulk collection and taking them out of boxes"*, and a
    hand goes to a slot rather than to a SKU. Measured on their store: the 122 cards at or
    above $5 are 38 SKUs — Rengar, Trophy Hunter at $40.73 sits in three slots of box 4 and
    Vilemaw in seven — so a per-SKU list would draw 38 rows for 122 physical cards and send
    the operator to a third of the drawer they actually have to open. `pipeline/join.py:
    uncommitted_positions` counts the same way for the same reason.

    IT IS A READ AND IT PRESSES NOTHING — `do_pipeline_worklist`'s posture, and the owner's
    ruling for this screen: *"read-only now, writes once you've used it"*. No child, no
    socket, no lock, no write. Taking a card out of a box is still `#/inventory`'s sale,
    retirement or move, which is where the store already learns a card has left.

    NOTHING ON HAND IS OMITTED, WHICH IS THE PART THAT COSTS FIELDS. 386 of the owner's 2,245
    cards on hand carry no market price at all, and a ranked view that quietly dropped 17% of
    the store would be the silent drop this repo forbids in as many words. So every on-hand
    card is a row, a row with no price carries `market: null` and a `why` naming which of the
    three causes it is, and `unrankable` counts them for the header:

      `never_identified`  captured and never put through a run — 214 of theirs. The remedy is
                          a run, and `#/runs` is where that is pressed.
      `read_nothing`      identified, and the model returned no name and no number — 172 of
                          theirs, every one with a photograph, none in the review or parked
                          queue. The remedy is a human looking at the photograph.
      `no_reading`        a SKU this machine has never seen a market price for — 4 of theirs.
                          The remedy is a join or a live fetch.

    THE BAND IS THE CLIENT'S AND THE FACTS ARE THIS ROUTE'S. Four ways of choosing a band
    were asked for — a typed price, the store's own cut-off, a top-N percentile, and the
    drawers ranked by value — and every one of them is a slice of the same ranked list.
    Computing them here would be four server-side answers that a screen has to keep in step
    with the sort it is already drawing, and a percentile in particular cannot be computed
    without the whole list anyway. The rows arrive sorted by market DESCENDING, unpriced
    last, so the head is the head and reversing it is the tail.

    `boxes` IS NOT A ROLLUP OF `copies` AND MUST NOT BE COMPUTED FROM ONE. It counts every
    card in the drawer including the unpriced ones, because the operator's question at the
    drawer level is *is this whole box bulk* — and on their store the answer is yes twice:
    box 2 is 540 of 542 cards under the cut-off and box 5 is 102 of 102, together 646 cards
    worth $66.79. A rollup computed off priced rows alone would have said box 4 was 418 cards
    when it holds 633, and called the 215 unpriced ones nothing.

    THE LABEL IS COMPOSED FRESH AND THE STORED ONE IS NEVER SERVED — `_relabel_positions`'
    rule (D58, on D56's), through the same `box_views` walk, so a copy that sold after a join
    and a divider moved since both read against the box as it is today. `box` and `index` are
    the store key beside it, exactly as `PricingSku.positions` splits them.
    """
    try:
        inventory = Store().read().inventory
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        raise PipelineRefusal(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "store_unreadable",
            f"The store could not be read, so nothing can be valued: {exc}",
        ) from None

    found, sources = _readings()
    views = run_resolve.box_views(inventory)
    # THE CORPUS ANSWERS THE ASKING PRICE AND NEVER THE RANKING, and an unreadable one costs
    # only that column — `do_pipeline_pricing`'s call, for its reason: a screen that will not
    # draw because the answers file is malformed is a screen that cannot show you the file.
    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError, OSError):
        book = corpus.Corpus()
    answers = book.to_payload().get("skus") or {}
    threshold = _policy_threshold(book)
    # THE CUT-OFF IS THE STORE'S OWN FIGURE AND `FLOOR` IS ONLY THE FALLBACK (D9, amended
    # 2026-09-09). `policy.threshold` does all three jobs — the price at which a card earns a
    # listing, the price the cheap half goes out at, and the price nothing may go below — so
    # the drawer counts below partition on exactly the line `emit` partitions on.
    cut = _market_of(threshold) or pricing_mod.FLOOR
    listings = inventory.listings

    copies: List[dict] = []
    tally: Dict[int, dict] = {}
    unrankable = {_NEVER_IDENTIFIED: 0, _READ_NOTHING: 0, _NO_READING: 0}
    by_box: Dict[str, int] = {}
    total = Decimal("0")
    valued = 0

    for card in inventory.cards.values():
        if card.state in master.TERMINAL_STATES:
            continue
        try:
            box, index = int(card.box), int(card.index)
        except (TypeError, ValueError):
            # A RECORD WHOSE POSITION WILL NOT COERCE IS SKIPPED, `do_inventory`'s rule: it
            # sits in no drawer a hand can be sent to and belongs to no box a total can be
            # counted against, so there is nothing this screen could truthfully say about it.
            # `do_status` is where a record like that is reported, and it reports it already.
            continue

        sku = str(card.sku or "")
        reading = found.get(sku) if sku else None
        market: Optional[Decimal] = None
        if reading is not None:
            market = _market_of(reading.market)
            if market is None:
                # A CELL THAT WILL NOT PARSE IS UNPRICED AND NEVER A ZERO. Ranking a card at
                # $0.00 because its market cell was malformed drops it to the very bottom of
                # the cheap band and into a bulk pull — a wrong answer wearing the shape of a
                # confident one, which is what this repo refuses everywhere it prices.
                reading = None

        why: Optional[str] = None
        if market is None:
            if not sku:
                why = _NEVER_IDENTIFIED if card.state == master.CAPTURED else _READ_NOTHING
            else:
                why = _NO_READING
            unrankable[why] += 1
            by_box[str(box)] = by_box.get(str(box), 0) + 1

        seat = tally.setdefault(
            box,
            {
                "cards": 0,
                "valued": 0,
                "unpriced": 0,
                "under": 0,
                "over": 0,
                "total": Decimal("0"),
                "top": None,
            },
        )
        seat["cards"] += 1
        if market is None:
            seat["unpriced"] += 1
        else:
            valued += 1
            total += market
            seat["valued"] += 1
            seat["total"] += market
            if market < cut:
                seat["under"] += 1
            else:
                seat["over"] += 1
            if seat["top"] is None or market > seat["top"]:
                seat["top"] = market

        record = listings.get(sku) if sku else None
        answer = answers.get(sku) if sku else None
        decided = answer.get("value") if isinstance(answer, dict) else None
        copies.append(
            {
                "box": box,
                "index": index,
                "label": _position_label(views, inventory, box, index),
                "sku": sku or None,
                # THE READING'S OWN NAME FIRST AND THE CARD'S SECOND. The export row is what
                # TCGplayer calls the product; `card.name` is what the model read off the
                # photograph, and 172 of the owner's are the empty string. The one a person
                # recognizes standing at the drawer is the catalogue's.
                "name": (reading.name if reading else None) or card.name or None,
                "set_name": (reading.set_name if reading else None) or card.set_hint or None,
                "condition": (reading.condition if reading else None)
                or card.condition
                or None,
                "game": card.game or None,
                "state": card.state,
                "market": tcgcsv.format_price(market) if market is not None else None,
                # WHAT THE OPERATOR DECIDED TO ASK, WHICH IS NOT WHAT THE CARD IS WORTH (D86).
                # Round-tripped as the corpus holds it — a string, a number, or a
                # `WithheldRecord` — because flattening that last shape would turn a
                # deliberate hold (D49) into a missing price.
                "answer": decided,
                # HOW MANY COPIES OF THIS SKU TCGPLAYER HOLDS, NEVER WHETHER THIS COPY IS ONE.
                # `live` is per-SKU and the store does not record which physical copy a push
                # spent — D147 decides that ordering at the write and not here — so a row
                # claiming "this one is listed" would be inventing a fact. The operator ruled
                # these appear with no distinction, which matters because 70% of the copies
                # under their cut-off are live: this is context on the row, never a filter.
                "live": int(getattr(record, "live", 0) or 0) if record is not None else 0,
                "read_at": reading.at if reading is not None else None,
                "source": reading.source if reading is not None else None,
                "why": why,
            }
        )

    # SORTED HERE RATHER THAN ON THE CLIENT, because the percentile band is a slice of this
    # exact order and two sorts of one list is two places for a tie-break to differ. Ties
    # break on `(box, index)`, so a band's rows arrive in walk order within each price — the
    # measurement that shaped this screen is about contiguity, and a stable address order is
    # what lets the cheap band read as 6.5 cards per reach rather than as 1,042 separate trips.
    copies.sort(
        key=lambda row: (
            row["market"] is None,
            -(_market_of(row["market"]) or Decimal("0")),
            row["box"],
            row["index"],
        )
    )

    names = _box_names()
    boxes = [
        {
            "box": box,
            "name": getattr(names.get(box), "name", None),
            "cards": seat["cards"],
            "valued": seat["valued"],
            "unpriced": seat["unpriced"],
            "under_cutoff": seat["under"],
            "at_or_over": seat["over"],
            "total": tcgcsv.format_price(seat["total"]),
            # THE MEAN IS OVER EVERY CARD IN THE DRAWER AND NOT OVER THE PRICED ONES. "What is
            # a card out of this box worth" is the question that decides whether the whole
            # drawer is bulk, and dividing by the priced subset would flatter box 4 — 633
            # cards, 215 of them unpriced — against box 2, where every card has a price.
            "per_card": tcgcsv.format_price(
                (seat["total"] / seat["cards"]) if seat["cards"] else Decimal("0")
            ),
            "top": tcgcsv.format_price(seat["top"]) if seat["top"] is not None else None,
        }
        for box, seat in sorted(tally.items())
    ]

    return {
        "at": master.now(),
        "basis": "market",
        "threshold": threshold,
        "sources": sources,
        "copies": copies,
        "boxes": boxes,
        "unrankable": {"total": sum(unrankable.values()), **unrankable, "by_box": by_box},
        "totals": {
            "cards": len(copies),
            "valued": valued,
            "value": tcgcsv.format_price(total),
        },
    }


# ---------------------------------------------------------------- the store-wide reconcile


def do_reconcile_live(payload: dict) -> dict:
    """`POST /pipeline/reconcile-live` — the whole store against one live export (D87).

    FREE, AND IT WRITES ONLY WITH `write`. The preview is the default for the same reason
    `pkmnscan prices adopt` previews: it moves the quantities `pipeline/join.py`'s cap
    arithmetic reads, over every SKU at once, and a settlement nobody watched is how a wrong
    number becomes the new floor.

    NOT RUN-SCOPED, WHICH IS THE WHOLE POINT. `POST /pipeline/runs/<name>/reconcile` exists
    and stays — it answers one import against one Export From Staged. This answers the STORE
    against a full live export, which is the only document that can report the other direction:
    SKUs TCGplayer holds that this pipeline never sent.

    THE FILE IS UPLOADED RATHER THAN NAMED BY PATH, for `_store_upload`'s reason: a route that
    opened any absolute path a request named would be a file-read primitive behind an origin
    header. It lands under `inventory/.reconcile/`, beside the store it is about to settle.
    """
    # THE SAME DOCUMENT THE MARKDOWN READS, AND NOW THE SAME FILE. `fetched` names one this
    # server already holds, so an operator who marks down and then reconciles is acting on ONE
    # reading rather than two downloads taken minutes apart.
    path = _live_export_from(payload)
    argv = [str(PKMNSCAN), "reconcile", "--live", str(path)]
    if payload.get("write"):
        argv.append("--write")
    code, console = _run_sync(argv, STEP_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "wrote": bool(payload.get("write")) and code == 0,
        "console": console,
    }


# --------------------------------------------------------- the standing queues, refreshed


def do_queue_refresh(payload: dict) -> dict:
    """`POST /queues/refresh` — re-resolve every OPEN queue entry, store-wide.

    FREE, RE-RUNNABLE, AND IT WRITES ONLY WITH `write` — `do_reconcile_live`'s shape, for
    `do_reconcile_live`'s reason: it rewrites every open entry at once, and a migration
    nobody watched is how a wrong number becomes the new floor. The preview is the default.

    NOT RUN-SCOPED, WHICH IS THE WHOLE POINT, and the same sentence D87 wrote one screen over.
    `store/queues.py:upsert` refreshes an entry and is reached only from `queues.apply_run`,
    which is reached only from a join; a join is scoped to a run and a run to a box, so an
    entry whose box holds no live run froze at the code that wrote it. Measured on the
    owner's store: 513 of 565 entries carried neither the `rarity` that landed on candidate
    rows on 2026-09-11 nor D137's Near Mint filter, and no re-join could reach them.

    NO FILE IS UPLOADED AND NO PATH IS NAMED ON THE WIRE, which is where this differs from
    `do_reconcile_live`. The exports are the ones the joined runs already recorded, chosen by
    the command itself — and that is not a shortcut: what the frozen entries need is the
    LADDER as it stands now, which repairs them against the very file they were joined
    against. A route that took a path would be `_store_upload`'s file-read primitive behind
    an origin header for no gain.

    STDOUT VERBATIM, like every other command on this server (D33). The command's own report
    names what it would change, what it refuses and why, and a structured summary here would
    be a second description of it to keep in step.
    """
    argv = [str(PKMNSCAN), "queue", "refresh"]
    if payload.get("write"):
        argv.append("--write")
    code, console = _run_sync(argv, STEP_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "wrote": bool(payload.get("write")) and code == 0,
        "console": console,
    }


# ------------------------------------------------------------- the stale-listing markdown


MARKDOWNS = "markdowns"
_STAMP = re.compile(r"^[0-9]{8}-[0-9]{6}$")


def _markdowns_dir() -> Path:
    return files.inventory_dir() / MARKDOWNS


def _stamps() -> List[str]:
    root = _markdowns_dir()
    if not root.is_dir():
        return []
    return sorted(
        (entry.name for entry in root.iterdir()
         if entry.is_dir() and _STAMP.match(entry.name)),
        reverse=True,
    )


def _open_markdown(stamp: str) -> Path:
    """One markdown directory, by stamp. Matched by SHAPE and then by MEMBERSHIP.

    `do_pipeline_file`'s rule, one directory over: the pattern refuses a path segment, and
    the membership check refuses a well-shaped name that is not actually a markdown this
    store made. Nothing built out of a request is joined onto a path until both have passed.
    """
    if not _STAMP.match(stamp or ""):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "stamp_invalid",
            f"{stamp!r} is not a markdown stamp.",
        )
    if stamp not in _stamps():
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_markdown",
            f"No markdown called {stamp}. `reprice list --write` is what makes one.",
        )
    return _markdowns_dir() / stamp


def _markdown_summary(stamp: str) -> dict:
    """One markdown, as the screen needs it: what it asked, and which files exist.

    The manifest is read for `asked` and the SKU count and for nothing else. Whether the
    upload has been written is answered by the FILE being there rather than by a flag in the
    manifest, because the flag could be true of a file somebody deleted.
    """
    directory = _markdowns_dir() / stamp
    payload = files.read_json(directory / cmd_reprice.MANIFEST, {}) or {}
    return {
        "stamp": stamp,
        "at": payload.get("at"),
        "asked": payload.get("asked") or {},
        "source": (payload.get("source") or {}).get("path"),
        "skus": len(payload.get("skus") or {}),
        "files": [
            row["name"] for row in _artifacts(directory)
        ],
        # WHAT TCGPLAYER IS HOLDING FOR THIS MARKDOWN, so a reload has a way back to it. The
        # push receipt is a server write, and CLAUDE.md's rule is that every server write has
        # a way back — without this, an operator who pushed and then reloaded would have rows
        # staged at TCGplayer and no control in this app that could publish them. Read off
        # disk on every list, never cached: `published_at` is what the publish route latches
        # on, and a stale copy of it would offer a second move of rows already moved.
        "pushed": _read_push(directory),
    }


def do_markdowns() -> dict:
    """`GET /pipeline/markdowns` — every markdown this store has written. Free, reads only."""
    return {"markdowns": [_markdown_summary(stamp) for stamp in _stamps()]}


def do_markdown_list(payload: dict) -> dict:
    """`POST /pipeline/markdowns` — which live listings are stale, and what they would become.

    FREE, RE-RUNNABLE, AND IT WRITES ONLY WITH `write`, which is `do_reconcile_live`'s shape
    and for a related reason: the preview is the whole point of the press. What it reports is
    a proposal about money, over the whole store at once, and the operator has to be able to
    look at it before a file exists.

    IT SPENDS NOTHING AND DELETES NOTHING AT TCGPLAYER. The file `write` produces is a
    worklist — it is not uploaded anywhere by this process, and every row of it carries
    `Add to Quantity` 0, so it cannot change a quantity even if it were.

    THE STAMP IS DISCOVERED BY DIFFING THE DIRECTORY, not parsed out of the command's stdout.
    `reprice list` names the directory it made in a sentence meant for a person, and a route
    that scraped that sentence would break the moment the sentence was reworded.
    """
    path = _live_export_from(payload)

    argv = [str(PKMNSCAN), "reprice", "list", str(path)]
    argv += _markdown_flags(payload)
    write = bool(payload.get("write"))
    if write:
        argv.append("--write")

    before = set(_stamps())
    code, console = _run_sync(argv, STEP_TIMEOUT_S)
    fresh = sorted(set(_stamps()) - before, reverse=True)
    return {
        "ok": code == 0,
        "exit_code": code,
        "wrote": write and code == 0,
        "console": console,
        "stamp": fresh[0] if fresh else None,
    }


def _markdown_flags(payload: dict) -> List[str]:
    """The allowlisted flags, one at a time, each validated here.

    AN ALLOWLIST AND NEVER A PASSTHROUGH, which is this module's standing rule: a request
    that could append arbitrary argv to `./pkmnscan` would be a shell. Every value is either
    coerced to a number here or matched against a set the CLI also knows.
    """
    argv: List[str] = []
    days = payload.get("days")
    if days is not None:
        argv += ["--days", str(_positive(days, "days"))]
    rule = payload.get("rule")
    percent = payload.get("percent")
    if rule is not None:
        text = str(rule)
        if not re.match(r"^(match|undercut:[0-9]+(\.[0-9]+)?|markup:[0-9]+(\.[0-9]+)?)$", text):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "rule_invalid",
                f"{text!r} is not a pricing rule. match | undercut:PCT | markup:PCT.",
            )
        argv += ["--rule", text]
    elif percent is not None:
        argv += ["--percent", str(_number(percent, "percent"))]
    basis = payload.get("basis")
    if basis is not None:
        if basis not in reprice.BASES:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "basis_invalid",
                f"{basis!r} is not a basis. One of: {', '.join(reprice.BASES)}.",
            )
        argv += ["--basis", str(basis)]
    above = payload.get("above_market")
    if above is not None:
        argv += ["--above-market", str(_number(above, "above_market"))]
    limit = payload.get("limit")
    if limit is not None:
        argv += ["--limit", str(_positive(limit, "limit"))]
    if payload.get("again"):
        argv.append("--again")
    return argv


def _number(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "number_invalid",
            f"`{field}` is {value!r}, which is not a number.",
        ) from None


def _positive(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = -1
    if number < 0:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "number_invalid",
            f"`{field}` is {value!r}, which is not a whole number of 0 or more.",
        )
    return number


#: Where a fetched live export is kept, and what it is named. MOVED TO `store/files.py`
#: (D189), because `pipeline/readings.py:collect` now reads this same directory
#: to arbitrate a market reading and `pipeline/` cannot import `server/` — the layering runs
#: the other way. Aliased here, under their original names, because this module still WRITES
#: into it (`do_live_export`) and `harness/tests/t7_store_and_seams.py` still spells them
#: `pipeline_routes.LIVE_DIR` / `pipeline_routes.LIVE_PREFIX`.
LIVE_DIR = files.LIVE_DIRNAME
LIVE_PREFIX = files.LIVE_PREFIX


def do_live_export() -> dict:
    """`POST /pipeline/live-export` — fetch the operator's own live listings from TCGplayer.

    FREE, AND IT IS NOT THE ROUTE THAT SPENDS — `do_pipeline_export`'s sentence, and for its
    reason: this is a download of the operator's own Pricing tab, nothing starts a child and
    nothing here can put a number on an invoice. What it does that almost nothing else does is
    read a secret and open a socket, which is why the call lives behind one function in
    `server/tcg_export.py`.

    THE SECOND DOCUMENT, NOT THE SECOND SCOPE. `POST /pipeline/runs/<name>/export` fetches the
    CATALOGUE — `MyInventory: False`, narrowed to a run's sets, whose whole job is listing cards
    that are NOT listed. This fetches the opposite: everything the operator has live, across
    every product line, which is what `reprice list` and `reconcile --live` both read. See
    `tcg_export.LIVE_QUERY` for the request, which was MEASURED off the portal's own
    `Export From Live` button rather than designed — a GET with two query parameters and no
    scope, because a live inventory has none.

    ONE FETCH FEEDS BOTH CONSUMERS. The file is kept and named, and `POST /pipeline/markdowns`
    and `POST /pipeline/reconcile-live` both accept `fetched: <name>` in place of an upload — so
    an operator who marks down and then reconciles is acting on ONE reading rather than two
    downloads taken minutes apart, which is the same argument `Markdown.tsx` makes for holding
    the uploaded bytes across its two presses.
    """
    directory = files.inventory_dir() / LIVE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    try:
        body = tcg_export.fetch_live()
    except tcg_export.FetchRefusal as caught:
        # A BAD GATEWAY AND NOT A 500, `do_pipeline_export`'s rule: the failure is at TCGplayer
        # or in the credential this machine holds for it, and every one of these carries a
        # sentence saying which.
        raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, caught.code, str(caught)) from None

    name = f"{LIVE_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    path = directory / name
    path.write_bytes(body)

    try:
        export = tcgcsv.read_export(path)
    except (tcgcsv.MalformedCsv, OSError) as exc:
        # A REFUSAL TEARS DOWN WHAT IT BUILT — `do_pipeline_export`'s rule again. A directory
        # accumulating one dead file per mis-timed press stops explaining itself.
        path.unlink(missing_ok=True)
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "tcg_unexpected_response",
            f"TCGplayer answered with something that is not an export: {exc}. Nothing was kept.",
        ) from None

    live_rows = 0
    live_copies = 0
    for row in export.rows:
        held = tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, ""))
        if held > 0:
            live_rows += 1
            live_copies += held

    # -------------------------------------------------------------- readings cache (D189)
    # THE `export` OBJECT ABOVE IS ALREADY PARSED — this reuses it rather than re-reading
    # `path` a second time, which is the whole cost `pipeline/readings.py:_newest_live_reading`
    # would otherwise pay again on every fetch. `at` comes off the file's own NAME through
    # `live_export_at`, never `master.now()` or the write's wall-clock moment: a full
    # `readings adopt --write` run later reads this same file and must compute the identical
    # `at`, and `pipeline/readings.py:live_export_at`'s docstring is explicit that the stamp
    # in the name is "the only honest clock here" — matching it is what keeps the incremental
    # path and the full recollect path from ever disagreeing about this file's age.
    #
    # SUPERSEDES EVERY EXISTING `live` SOURCE, NOT JUST THIS ONE'S OWN NAME. Unlike a run
    # table, `_newest_live_reading` only ever credits the SINGLE newest live file — the
    # instant this fetch lands, every SKU any OLDER live file was still carrying in `readings`
    # is no longer backed by anything `collect()` would read, whether or not this file
    # happens to reprice the same SKU. `Store().read()` here is a second, lock-free read; it
    # costs one connection and no full-table scan (`readings_sources` is small).
    at = readings_walk.live_export_at(name)
    if at is not None:
        live_found, live_source = readings_walk.reading_from_export(export, at=at, source=name)
        stale_live = [
            s.name for s in Store().read().readings.sources.values()
            if s.kind == store_readings.KIND_LIVE
        ]
        with Store().write() as writable:
            writable.readings.replace_source(
                store_readings.KIND_LIVE, name, live_found, live_source,
                supersede=stale_live or [name],
            )

    return {
        "ok": True,
        "fetched": name,
        "at": master.now(),
        "rows": len(export.rows),
        "live_rows": live_rows,
        "live_copies": live_copies,
    }


def _open_live_export(name: str) -> Path:
    """One fetched live export, by name. Shape, then prefix, then membership.

    `_open_markdown`'s RULE, and it is what keeps a name from being a file-read primitive
    guarded only by an origin header.
    """
    if not _DOWNLOADABLE.match(name or "") or not str(name).startswith(LIVE_PREFIX):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "fetched_invalid",
            f"{name!r} is not the name of a fetched live export.",
        )
    path = files.inventory_dir() / LIVE_DIR / name
    if not path.is_file():
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_fetch",
            f"No fetched live export named {name}. Fetch one, or drop a download in.",
        )
    return path


def _live_export_from(payload: dict) -> Path:
    """The live export this request means — a fetched one it names, or bytes it uploaded.

    BOTH, AND NEITHER IS THE FALLBACK. A fetch is the ordinary path now; an upload is what an
    operator does with a download they already have, or when the cookie has expired. A request
    carrying both has not decided which file it means, and guessing would pick the other one.
    """
    fetched = payload.get("fetched")
    upload = payload.get("export")
    if fetched is not None and isinstance(upload, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "fetched_and_export",
            "Send `fetched` (a live export this server holds) or `export` (bytes), never both.",
        )
    if fetched is not None:
        return _open_live_export(str(fetched))
    if not isinstance(upload, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_required",
            "Send `export` as {name, content} — TCGplayer's My Pricing export, all printings — "
            "or `fetched` naming one this server already has.",
        )
    target = files.inventory_dir() / ".reprice"
    target.mkdir(parents=True, exist_ok=True)
    return _store_upload(target, upload, "live-")


def do_markdown_apply(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/apply` — the edited worklist back, as an upload file.

    THE WORKLIST COMES BACK AS AN UPLOAD, because it left the machine. The operator downloads
    it, opens it in a spreadsheet, and hands back a file the server has never seen — so this
    writes those bytes into the markdown's own directory and runs `reprice apply` against
    them, with the manifest that is already there.

    SENDING NO WORKLIST MEANS "the one you wrote", which is the flow for an operator who did
    not want to edit anything: `reprice list` already put a proposed price on every row.

    OR AS `edits`, WHICH IS WHAT `#/pricing` SENDS (D103). The lens holds `{sku -> price}` and
    no CSV writer: `app/package.json` has exactly two runtime dependencies, and PapaParse — the
    library `CLAUDE.md` requires for this job — is not among them. So the pairs arrive as JSON
    and are materialised HERE with `tcgcsv.write_csv`, the repo's own writer, into the same
    directory and under the same name a hand-back would take.

    IT IS TWO COLUMNS AND THAT IS THE POINT. `reprice apply` reads exactly `TCGplayer Id` and
    `TCG Marketplace Price` out of whatever it is handed, and builds every other byte from the
    manifest. A file with only those two columns is the narrowest possible expression of
    D100's *"the operator's editor is not where the bytes come from"* — there is no column in
    it for a quantity to hide in. Downstream nothing knows the difference, so `read_back`,
    `import_rows`, `check_only_writable_changed`, `check_quantities_zero`, the duplicate sweep
    and the whole-file `raised` refusal all run exactly as they do for a spreadsheet.

    THE TWO ARE MUTUALLY EXCLUSIVE. A request carrying both is a caller that has not decided
    which file it means, and guessing would pick the one it did not.

    PREVIEWS BY DEFAULT, and the write half is the last press before bytes leave for a
    marketplace. What it writes is `import.csv`, whose every row carries `Add to Quantity` 0.
    """
    directory = _open_markdown(stamp)
    worklist = directory / cmd_reprice.WORKLIST
    upload = payload.get("worklist")
    edits = payload.get("edits")
    if isinstance(upload, dict) and edits is not None:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "worklist_and_edits",
            "Send `worklist` (a file the operator edited) or `edits` (the pairs a screen "
            "holds), never both — they are two spellings of the same instruction sheet.",
        )
    if isinstance(upload, dict):
        worklist = _store_upload(directory, upload, "edited-")
    elif edits is not None:
        worklist = _write_edits(directory, edits)
    if not worklist.is_file():
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_worklist",
            f"Markdown {stamp} has no worklist to apply. Send one as `worklist`.",
        )
    argv = [str(PKMNSCAN), "reprice", "apply", str(worklist)]
    # THE STALE-WRITE GUARD, TRAVELLING TO THE SUBPROCESS. Absent means "did not read one",
    # which the command allows for the terminal user; present-and-behind refuses the whole
    # file before a byte is built. See `cli/cmd_reprice.py:_apply`.
    revision = payload.get("revision")
    if isinstance(revision, str) and revision:
        argv += ["--corpus-revision", revision]
    if payload.get("write"):
        argv.append("--write")
    code, console = _run_sync(argv, STEP_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        # ANSWERED BY THE FILE BEING THERE RATHER THAN BY A FLAG, which is the rule
        # `_markdown_summary` already states one function up. `_apply` exits 0 with nothing
        # written when every row was refused — a single unreadable price does it — and this
        # used to answer `wrote: true` over an `import.csv` that does not exist.
        "wrote": bool(payload.get("write"))
        and code == 0
        and (directory / cmd_reprice.IMPORT).is_file(),
        "console": console,
        "stamp": stamp,
        # THE NEW DIGEST, SO THE SCREEN CAN ADOPT IT. `apply --write` moves the corpus behind
        # the screen's back — `emit` never did, it only reads — so without this the operator's
        # very next keystroke is refused `corpus_moved` for a write they just made themselves.
        "revision": corpus.revision(),
    }


def _write_edits(directory: Path, edits: object) -> Path:
    """`[{sku, price}]` as the two-column instruction sheet `reprice apply` reads.

    VALIDATED HERE AND SHAPED HERE, because everything past this point treats the file as the
    operator's word. A price is kept as the STRING it arrived as rather than parsed: `read_back`
    compares as `Decimal` and refuses an unreadable cell by name, and re-formatting a figure on
    the way in would be this route having an opinion about money.
    """
    if not isinstance(edits, list) or not edits:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "edits_invalid",
            "Send `edits` as a non-empty list of {sku, price}.",
        )
    rows = []
    for entry in edits:
        if not isinstance(entry, dict):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST, "edits_invalid", "Every edit must be {sku, price}."
            )
        sku = str(entry.get("sku") or "").strip()
        price = str(entry.get("price") or "").strip()
        if not sku or not price:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "edits_invalid",
                f"An edit is missing its sku or its price: {entry!r}",
            )
        rows.append({tcgcsv.SKU_COLUMN: sku, tcgcsv.PRICE_COLUMN: price})
    target = directory / "edited-screen.csv"
    tcgcsv.write_csv(target, (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN), rows)
    return target


def _survey(directory: Path) -> Dict[str, dict]:
    """`survey.json`'s rows keyed by SKU, or a refusal naming which half is missing.

    THE MARKDOWN'S ANSWER TO `_history_row`, AND ITS DOCSTRING'S ARGUMENT CARRIES OVER WORD
    FOR WORD: the document that priced this card is the document that says what it is. The
    survey keeps every live row's export bytes verbatim, which is the five identity cells the
    catalogue walk reads, so there is no second source to keep in step and no re-parse of an
    export.
    """
    path = directory / cmd_reprice.SURVEY
    if not path.is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "survey_not_written",
            f"Markdown {directory.name} has no {cmd_reprice.SURVEY}. It was written before "
            f"the lens existed — re-run `reprice list --write` over the same export.",
        )
    try:
        payload = json.loads(path.read_text("utf-8"))
        rows = payload["skus"]
    except (OSError, ValueError, KeyError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "survey_unreadable",
            f"{cmd_reprice.SURVEY} could not be read: {exc}. Re-run `reprice list --write`.",
        ) from None
    # PROJECTED SO BOTH DOCUMENTS ANSWER `_history_for_entry` IN ONE SHAPE. A run's
    # `pricing.json` entry nests the export's own figures under `snap`; a survey row carries
    # `market` at the top because that is `Candidate`'s word for it. The panel draws
    # `snap.market` — the export's price, BESIDE the reading and never mixed into it — so
    # without this a live listing's own asking market read as "the export carries no price for
    # this card", which is a false sentence over a row the export priced.
    return {
        str(row.get("sku") or ""): {**row, "snap": {"market": row.get("market")}}
        for row in rows
        if row.get("sku")
    }


def _markdown_floor() -> str:
    """The store's cut-off, which is the floor a markdown may not price below.

    `_policy_threshold`'s body plus the read, and the read is what needs the guard: this is a
    FREE table route over a survey on disk, and an unreadable `prices.json` must not be able
    to stop a screen drawing 441 live listings. An unusable corpus falls back to the constant
    for that function's stated reason — `cli/cmd_reprice.py` is what actually refuses a price,
    it refuses rather than falls back, and a screen drawing a figure is not the enforcement.
    """
    try:
        return _policy_threshold(corpus.Corpus.read())
    except (OSError, ValueError):
        return str(pricing_mod.THRESHOLD)


def _survey_row(directory: Path, sku: str) -> dict:
    entry = _survey(directory).get(sku)
    if entry is None:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "sku_not_in_markdown",
            f"Markdown {directory.name} surveyed no SKU {sku}. A history is read off the "
            f"export row this markdown stored, so a SKU it never saw has no row here to read.",
        )
    return entry


def do_markdown_table(stamp: str) -> dict:
    """`GET /pipeline/markdowns/<stamp>/table` — every live listing this survey saw (D103).

    THE LENS'S WHOLE INPUT, and free: it reads `survey.json` and holds nothing. What makes it
    a lens rather than a gate is that the refused rows are here too, each carrying the code
    that refused it, so `#/pricing` can draw the operator's entire live inventory and let
    staleness be a filter they loosen rather than a decision taken before the data arrived.

    THE ORDER IS THE FILE'S, WHICH IS THE REPORT'S. `Plan.surveyed` walks the offer by
    `at_risk`, then the deferred, then the refusals in `SKIP_ORDER`; a screen drawing this top
    to bottom draws what the terminal printed.
    """
    directory = _open_markdown(stamp)
    # THROUGH `_survey` FOR THE REFUSALS, then the file once more for the envelope around
    # them. `_survey` is what names a missing or unreadable survey with a code the screen can
    # act on, so it runs first and this read cannot be the one that fails.
    rows = list(_survey(directory).values())
    payload = json.loads((directory / cmd_reprice.SURVEY).read_text("utf-8"))
    return {
        "stamp": stamp,
        "asked": payload.get("asked") or {},
        "counts": payload.get("counts") or {},
        "source": payload.get("source") or {},
        "at": payload.get("at"),
        "skus": rows,
        # THE SENTENCES, SENT ONCE RATHER THAN PER ROW AND NEVER RE-WORDED ON THE CLIENT.
        # `pipeline/reprice.py:SKIP_SENTENCE` is the one table; a screen composing its own
        # phrasing for a refusal code is a second description of one fact, which is the drift
        # D16 exists to catch.
        "says": dict(reprice.SKIP_SENTENCE),
        # WHICH CODES MAY NEVER BE PUSHED, so the row can refuse the field rather than let the
        # operator type a price the apply will throw away. Server-side, because `read_back` is
        # what actually enforces it and two lists would drift.
        "unpriceable": list(reprice.UNPRICEABLE_CODES),
        # THE STORE'S OWN CUT-OFF, WHICH IS THE FLOOR (D9, amended 2026-09-09). Read now
        # rather than out of the survey, for `cli/cmd_reprice.py:_apply`'s reason: what a price
        # may not go below is the figure in force at the moment of the press, and the press is
        # what this screen is holding. The constant was here while the apply refused 293 rows
        # against $0.40 on a store set to $0.29, so the sheet drew the wrong figure and the
        # receipt named it.
        "floor": _markdown_floor(),
    }


def do_markdown_history(stamp: str, sku: str) -> dict:
    """`GET /pipeline/markdowns/<stamp>/history?sku=<sku>` — the reading for one live listing.

    `do_pipeline_history`'s body over the markdown's own document — see `_history_for_entry`
    for why that is one implementation and two addresses, and see that route's header for the
    third-party argument, which is unchanged: it spends nothing, both hosts are public, it
    writes only its own derived cache, and it cannot fire without a press.
    """
    directory = _open_markdown(stamp)
    wanted = _wanted_sku(sku)
    return _history_for_entry(
        _survey_row(directory, wanted), wanted, {"markdown": directory.name}
    )


def do_markdown_trends(stamp: str, skus: Sequence[str] = ()) -> dict:
    """`GET /pipeline/markdowns/<stamp>/trends?sku=…` — the strip, over named SKUs only.

    AN EXPLICIT LIST IS REQUIRED HERE AND OPTIONAL ON A RUN, and the difference is size rather
    than taste. The run route measured 46 SKUs at ~34s of courtesy delay; a survey of the
    owner's live inventory is 441 rows, which is about five and a half minutes at a free
    public mirror for readings nobody asked for. D62's rule is that this is a press, and a
    walk that big would make the press meaningless — so the client sends the rows the operator
    is actually looking at, filtered, in chunks.
    """
    directory = _open_markdown(stamp)
    wanted = [s for s in (str(x).strip() for x in skus) if s]
    if not wanted:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "skus_required",
            "Name the SKUs to read: a survey is the whole live inventory, and walking it "
            "unasked would be ~5.5 minutes at a public mirror. Pass ?sku= per row.",
        )
    return _trends_for_entries(
        _survey(directory),
        wanted,
        {"markdown": directory.name},
        missing=(
            f"Markdown {directory.name} surveyed no SKU {{sku}}. A history is read off the "
            f"export row this markdown stored."
        ),
        skip_at_cap=False,
    )


def do_markdown_file(stamp: str, filename: str) -> Tuple[bytes, str]:
    """`GET /pipeline/markdowns/<stamp>/file?name=<f>` — the worklist and the upload.

    `do_pipeline_file`'s two gates, unchanged: the shape pattern, then membership in what the
    directory actually holds. The import CSV is the file the operator uploads to TCGplayer,
    so it has to be reachable from the browser that asked for it.
    """
    directory = _open_markdown(stamp)
    if not _DOWNLOADABLE.match(filename or ""):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "file_name_invalid",
            f"{filename!r} is not a downloadable markdown artefact.",
        )
    if filename not in {row["name"] for row in _artifacts(directory)}:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_file",
            f"Markdown {stamp} has no file called {filename}. `reprice apply --write` is "
            f"what writes {cmd_reprice.IMPORT}.",
        )
    target = directory / filename
    kind = "text/csv" if target.suffix == ".csv" else "text/plain; charset=utf-8"
    return target.read_bytes(), kind


# ------------------------------------------------------------- the push to TCGplayer


def do_markdown_push(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/push` — the import file, into TCGplayer's STAGED.

    THIS IS THE SECOND ROUTE IN THIS SERVER THAT REACHES THE OUTSIDE WORLD AND CHANGES
    SOMETHING THERE, and the first one that is not a download. `POST /pipeline/identify` can
    spend money (D33) and is named for it; this one can change what the operator's storefront
    holds, so it is named for that and lives here beside its sibling rather than being folded
    into `apply`.

    NOTHING A BUYER CAN SEE CHANGES. Staged is the operator's own working copy — measured
    2026-09-06, a 100-row push moved 0 of 759 live prices and 0 live quantities. Publishing is
    `do_markdown_publish` below, and it is a separate press on purpose: the whole reason that
    day's accidental upload was survivable is that these two are not one button.

    IT PUSHES THE FILE, NOT THE STORE. `import.csv` is what the operator can open, download and
    diff, so it is what goes; re-deriving the rows from the corpus here would mean the thing
    uploaded is not the thing on screen.
    """
    directory = _open_markdown(stamp)
    target = directory / cmd_reprice.IMPORT
    if not target.exists():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "no_import_file",
            f"Markdown {stamp} has no {cmd_reprice.IMPORT} to push. Answer step 3 first — "
            f"`reprice apply --write` is what writes it.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "A push to TCGplayer is not a preview. Send `confirm` once the operator has "
            "pressed it; nothing was sent.",
        )
    rows = tcg_import.rows_from_csv(target.read_text(encoding="utf-8"))
    try:
        pushed = tcg_import.push_to_staged(rows, filename=cmd_reprice.IMPORT)
    except tcg_import.FetchRefusal as refusal:
        raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, refusal.code, refusal.message) from None
    _record_push(directory, pushed)
    return {"pushed": pushed.as_dict(), "stamp": stamp}


def do_markdown_publish(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/publish` — move THIS upload's staged prices to live.

    **THIS CHANGES WHAT BUYERS PAY.** It is the only route in this server that does, and the
    refusals below are shaped by that rather than by symmetry with its neighbours.

    THE UPLOAD ID COMES OFF DISK AND NEVER OFF THE REQUEST. A client-supplied id would let a
    mistyped or replayed body publish an upload this markdown never made — and `scope` is
    fixed at "this upload" in `server/tcg_import.py` for the same reason, so the id IS the
    scope. `push.json` is written by the push above and is the only place this is read from.
    """
    directory = _open_markdown(stamp)
    record = _read_push(directory)
    if record is None:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "nothing_staged",
            f"Markdown {stamp} has not been pushed to TCGplayer, so there is no staged upload "
            f"to publish. Push it first; nothing was sent.",
        )
    if record.get("published_at"):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "already_published",
            f"That upload was already moved to live at {record['published_at']}. Publishing it "
            f"again would be a second move of rows TCGplayer no longer holds staged; nothing "
            f"was sent.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Moving prices to live is not a preview. Send `confirm` once the operator has "
            "pressed it; nothing was sent.",
        )
    try:
        answer = tcg_import.move_to_live(str(record["upload_id"]))
    except tcg_import.FetchRefusal as refusal:
        raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, refusal.code, refusal.message) from None
    record["published_at"] = _now_iso()
    record["result"] = answer
    _write_push(directory, record)
    return {"published": record, "stamp": stamp}


def do_markdown_rollback(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/rollback` — discard a staged upload at TCGplayer.

    THE UNDO FOR A PUSH, AND ONLY BEFORE IT IS PUBLISHED. Once the rows are live there is
    nothing here to roll back: TCGplayer no longer holds them staged, and the way a live price
    goes back is another markdown (D100 — nothing is deleted to change a price).

    IT IS NARROWER THAN THE PORTAL'S OWN CONTROL, DELIBERATELY. `clearstagedinventory` is one
    call that empties the operator's WHOLE staged channel and takes no id;
    `rollbackexportcsv` takes the upload id and undoes exactly what this markdown sent. Only
    the second is reachable from here, for `move_to_live`'s reason — a scope that can widen
    is not something a button should be able to choose.
    """
    directory = _open_markdown(stamp)
    record = _read_push(directory)
    if record is None:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "nothing_staged",
            f"Markdown {stamp} has nothing staged at TCGplayer, so there is nothing to "
            f"discard. Nothing was sent.",
        )
    if record.get("published_at"):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "already_published",
            f"That upload went live at {record['published_at']}, so TCGplayer no longer holds "
            f"it staged and there is nothing to roll back. A live price goes back the way it "
            f"came down — another markdown. Nothing was sent.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Discarding a staged upload reaches TCGplayer. Send `confirm` once the operator "
            "has pressed it; nothing was sent.",
        )
    try:
        tcg_import.rollback(str(record["upload_id"]))
    except tcg_import.FetchRefusal as refusal:
        raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, refusal.code, refusal.message) from None
    # THE RECEIPT GOES WITH THE UPLOAD IT DESCRIBED. Leaving it would leave the screen
    # offering to publish rows TCGplayer has been told to forget.
    (directory / PUSH_RECORD).unlink(missing_ok=True)
    return {"rolled_back": record.get("upload_id"), "stamp": stamp}


PUSH_RECORD = "push.json"


def _now_iso() -> str:
    """UTC, to the second. The same stamp shape every other receipt in this module writes."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _record_push(directory: Path, pushed: "tcg_import.StagedUpload") -> None:
    """The receipt for a push, beside the file that was pushed.

    IT LIVES IN THE MARKDOWN DIRECTORY because that is what the run directory already is: the
    immutable record of one operation. The upload id is what `publish` scopes to and what a
    rollback would need, so losing it would leave a staged upload nothing here can name.
    """
    record = pushed.as_dict()
    record["pushed_at"] = _now_iso()
    record["published_at"] = None
    _write_push(directory, record)


def _write_push(directory: Path, record: dict) -> None:
    (directory / PUSH_RECORD).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_push(directory: Path) -> Optional[dict]:
    target = directory / PUSH_RECORD
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except ValueError:
        return None


# ------------------------------------------------------------------ the pricing corpus


def do_pricing_corpus() -> dict:
    """`GET /pricing` — every listing answer this operator has given, and the policy (D86).

    ONE READ FOR THE WHOLE SCREEN, which is the shape the corpus makes possible. `#/pricing`
    used to fetch one `decisions.json` per run it was showing and reconcile them in the client;
    there is one document now, so there is one read and nothing to reconcile.

    IT IS SEPARATE FROM `GET /pipeline/pricing` ON PURPOSE. That route answers the WORKLIST —
    which cards are in front of the operator, out of which runs, with which export rows. This
    one answers what has been decided, and it is the same document whatever is on screen. Two
    facts, two routes, and the screen holds them apart the same way.
    """
    book = corpus.Corpus.read()
    return {
        "corpus": book.to_payload(),
        "path": str(files.prices_path()),
        "revision": _corpus_revision(),
        "clearable": _clearable_block(book),
    }


def _clearable_block(book: corpus.Corpus) -> dict:
    """Which answers a mass-clear MAY remove, and how old each one is — in the ENVELOPE.

    BESIDE `corpus` AND NEVER INSIDE IT, which is `revision`'s own rule and matters more here.
    `PUT /pricing` replaces the document wholesale and `Corpus.parse` round-trips every
    top-level key it does not recognise, so a derived block written into the document would be
    carried straight back into `inventory/prices.json` and then read by the next screen as
    though it were a fact somebody stored. It is a reading of the file, not part of it.

    THE CLIENT GETS THE LIST AND NOT THE RULE. `#/pricing` has to say "clear 269 typed prices"
    BEFORE the press, and per scope and per age window, which means counting. Shipping the
    per-SKU ages lets it count by intersecting this list with the rows it drew — set
    arithmetic — where re-deriving *which answers are clearable* in TypeScript would be a
    second implementation of `corpus.clearable`, on the one file in this product that holds
    money. That is the mistake D49 refused to make across two languages and D103 found
    `preset_prices` making across two Python modules.

    IT IS ADVISORY, AND THE PRESS RE-DERIVES. `do_pricing_clear` never trusts this list: it
    reads the file again and runs the same predicate, taking the client's SKUs as a SCOPE only.
    So an age here going stale between the read and the press costs an inaccurate label, never
    a wrong deletion.
    """
    now = master.now()
    plan = corpus.clearable(book, now=now)
    return {
        # sku -> whole days since this answer was written, or `null` for one carrying no
        # readable `at`. `null` is the honest answer and not a zero: 20 of the owner's 407
        # predate `stamp_answers` or were folded in by the migration, which D103 rules may
        # never be given an invented date.
        "days": {
            sku: corpus.age_in_days(book.answers[sku].at, now) for sku in plan.skus
        },
        "holds": len(plan.holds),
        "unknown": len(plan.unknown),
    }


def _corpus_revision() -> str:
    """A short digest of `inventory/prices.json` as it stands on disk, or `""` if absent.

    A DELEGATION, AND THE ONE LINE IS THE POINT. The body moved to `pipeline/corpus.py:revision`
    so that the CLI writers — `reprice apply`, which read-modify-writes this same file from a
    subprocess — can be guarded by the identical digest. `cli/` may not import `server/`, so a
    guard living here could only ever cover the route, and for as long as it did, `PUT /pricing`
    refused a stale write while a subprocess clobbered one silently.

    THE NAME STAYS BECAUSE THE CALL SITES DO. This is read three times in this module and the
    indirection costs nothing; what it buys is that there is exactly one reader of the file, a
    hazard `check_corpus_revision`'s own header names — a digest CACHE added here would leave a
    route-only test green while the real refusal stopped firing.
    """
    return corpus.revision()


def do_pricing_corpus_write(payload: dict) -> dict:
    """`PUT /pricing` — replace the corpus.

    WHOLESALE, EXACTLY AS `PUT .../decisions` WAS, AND FOR ITS REASON: the screen round-trips
    every key it does not understand, so a field a later version adds — or `_note`, which a
    person writes by hand — survives a client that has never heard of it.

    IT VALIDATES THE POLICY AND NOT THE ANSWERS, which is the same line D49 drew. `Corpus.parse`
    raises on a rule or basis outside the enum, and on a `threshold` that is not a positive
    price, because a screen could otherwise write a document that makes `emit` answer with a
    traceback an hour later. All three are `ValueError`s and the `except` below is what turns
    them into a 400 naming the value rather than a 500 naming a line number. A per-SKU answer is left
    alone: `Decisions.parse` is the one parser for what an answer means and it runs at the
    moment one is used, where its refusal names the SKU.
    """
    # THE STALE-WRITE REFUSAL. Absent means "did not read one", which is the terminal user
    # editing the file and PUTting it back, and it is allowed — the guard is for a client that
    # DID read a revision and is now behind, which is the only case that can silently destroy
    # somebody else's write.
    offered = payload.get("revision")
    if isinstance(offered, str) and offered:
        current = _corpus_revision()
        if current and offered != current:
            raise PipelineRefusal(
                HTTPStatus.CONFLICT,
                "corpus_moved",
                "The pricing file changed since this screen read it — another tab, or an edit "
                "on disk. Reload before saving, or this write would revert it.",
            )

    document = payload.get("corpus")
    if not isinstance(document, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "corpus_invalid",
            "Send {\"corpus\": {...}} — the whole document, as `GET /pricing` answers it.",
        )
    try:
        book = corpus.Corpus.parse(document)
    except (decisions.MalformedDecisions, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST, "corpus_invalid", str(exc)
        ) from None

    # THE ANSWER IS DATED HERE, WHICH IS WHERE IT WAS NOT (D103). `Answer.at` was written in
    # exactly one place in this repo — `reprice apply` — and read in one, that command's
    # ratchet, so `priced_recently` meant "marked down recently" while D100 claimed it meant
    # *"a card the operator hand-priced on #/pricing yesterday is not stale"*. It did not; the
    # screen has never stamped anything, and hand-pricing fifty live listings left every one
    # of them reading as stale the next morning. Now that the markdown IS a lens on this
    # screen, that gap is the ordinary path rather than an edge.
    #
    # DIFF-BASED, AND `corpus.stamp_answers` IS WHERE THE THREE RULES LIVE. This route replaces
    # the document wholesale on every debounced save, so a blanket stamp would move every
    # answer's `at` to now on every keystroke and read the whole corpus as `priced_recently`
    # forever — the ratchet inverted into a permanent refusal.
    # A CORPUS ON DISK THIS PARSER CANNOT READ IS NOT A REASON TO REFUSE THE WRITE that
    # replaces it — the same posture `do_pipeline_worklist` takes. Every answer then reads as
    # new and is stamped, which is the honest answer when there is no `before` to compare
    # against.
    previous = corpus.Corpus()
    with contextlib.suppress(decisions.MalformedDecisions, ValueError):
        previous = corpus.Corpus.read()
    corpus.stamp_answers(previous, book, master.now())

    written = book.write()
    return {
        "ok": True,
        "written": str(written),
        "answers": len(book.answers),
        "revision": _corpus_revision(),
    }


#: The most SKUs one clear or one restore may name. The corpus is hundreds of answers — the
#: owner's largest ever is 430 — and a worklist scope is a subset of it, so a request naming
#: ten thousand is not a press from this screen. `MAX_QUANTITIES` bounds the emit route for the
#: same reason and this is deliberately the same order of magnitude.
MAX_CLEAR_SKUS = 5000


def _clear_revision_guard(payload: dict) -> None:
    """Refuse a clear or a restore offered against a corpus that has since moved.

    THE SAME GUARD `PUT /pricing` TAKES, AND TAKING IT IS THE WHOLE REASON A SECOND WRITER IS
    ALLOWED HERE. D86's amendment of 2026-09-04 is blunt: *"ONE FILE MEANS TWO WRITERS, AND THE
    SECOND ONE WAS SILENTLY REVERTING THE FIRST"*, and D105 states the rule as *"one file may
    not have two unguarded writers"*. UNGUARDED is the operative word — `pkmnscan reprice apply`
    is already a second writer and is admitted by carrying `--corpus-revision`. These two routes
    are the third and fourth and they carry the identical digest.

    ABSENT MEANS "DID NOT READ ONE" AND IS ALLOWED, verbatim as the PUT has it: that is the
    terminal user with `curl`. The guard exists for a client that DID read a revision and is now
    behind, which is the only case that can destroy a write nobody saw happen.
    """
    offered = payload.get("revision")
    if isinstance(offered, str) and offered:
        current = _corpus_revision()
        if current and offered != current:
            raise PipelineRefusal(
                HTTPStatus.CONFLICT,
                "corpus_moved",
                "The pricing file changed since this screen read it — another tab, or an edit "
                "on disk. Reload before clearing, or this would act on answers you have not "
                "seen.",
            )


def _clear_scope(payload: dict) -> Optional[List[str]]:
    """The SKUs a clear is narrowed to, or `None` for the whole store.

    A SCOPE AND NEVER A PREDICATE, which `corpus.clearable` restates from the other side. What
    arrives here says *which answers to consider*; whether each of those may be removed is
    decided in Python against the file as it stands. A screen cannot name a hold into being
    clearable, and a screen working from a list that went stale between the read and the press
    removes fewer answers than it meant to rather than a different set.
    """
    raw = payload.get("skus")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "scope_invalid",
            "`skus` must be a list of SKU ids, or absent to mean the whole store.",
        )
    if len(raw) > MAX_CLEAR_SKUS:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "scope_invalid",
            f"{len(raw)} SKUs is more than one press can name ({MAX_CLEAR_SKUS}).",
        )
    return [str(sku) for sku in raw]


def _clear_window(payload: dict) -> Optional[int]:
    """`older_than_days`, or `None` for every age.

    THERE IS NO DEFAULT AND THERE MAY NOT BE ONE. The operator was offered an expiry rule — a
    typed price going stale by itself after N days — and refused it: *"Just give me a mass-clear
    button."* A default window here would be that rule wearing a different hat, chosen by this
    file rather than by them. Absent means every age, which is what the control says.
    """
    raw = payload.get("older_than_days")
    if raw is None:
        return None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "window_invalid",
            "`older_than_days` must be a whole number of days, or absent for every age.",
        ) from None
    if days < 0:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "window_invalid",
            f"A window of {days} days is not a window. Leave it out to clear every age.",
        )
    return days


def do_pricing_clear(payload: dict) -> dict:
    """`POST /pricing/clear` — remove typed prices in bulk, and hand back what was removed.

    THE OPERATOR ASKED FOR EXACTLY THIS AND FOR NOTHING AROUND IT: *"I also need a clear claims
    on pricing (after several emits a lot of pricing is pre typed but stale and there's no way
    to mass clear)"*. Offered an expiry rule instead they said *"Just give me a mass-clear
    button."* So this is a press. Nothing here runs on a timer, no answer ages out on its own,
    and `older_than_days` is a filter the operator points at one press rather than a policy the
    store carries.

    WHAT IT MAY REMOVE IS `corpus.clearable`'s, RE-DERIVED HERE FROM THE FILE. Holds are left
    standing (D49 — a judgement with a reason, a watch and a note attached), `channel !=
    "price"` answers are left standing (the ABSENCE of an answer, which `decisions.blocking`
    reads to refuse an `emit`), and an undated answer is left standing by an age filter that
    cannot place it. The response names all three, so the screen states the blast radius rather
    than implying it.

    THE WAY BACK IS `cleared`, AND IT IS THE ANSWERS AND NOT THE SKUS. Each carries its `value`,
    its `at` and its `from_run` verbatim, which is what lets `do_pricing_restore` put a price
    back with the date it was actually typed on. Handing back a list of SKUs would make the undo
    a re-type: the values would be gone, and any restore built from the screen's own memory
    would re-date every answer to now and read as `priced_recently` on tomorrow's survey — D103's
    ratchet inverted by the undo of all things.

    IT IS ITS OWN ROUTE RATHER THAN A `PUT /pricing` OF NULLS. `Corpus.parse` does read `null`
    as "drop this answer" (D49's rule, kept), so a client could clear by nulling keys — and
    then the client would be deciding WHICH keys, which is `corpus.clearable` written a second
    time in TypeScript against money. The predicate stays in Python and the screen presses a
    button.
    """
    _clear_revision_guard(payload)
    scope = _clear_scope(payload)
    window = _clear_window(payload)

    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError) as exc:
        # A CORPUS THIS PARSER CANNOT READ IS A REFUSAL HERE, WHERE `PUT /pricing` LETS THE
        # WRITE THROUGH. That route REPLACES the document, so an unreadable one is what is
        # being fixed; this one reads the document to decide what to destroy inside it, and
        # deciding that against a file nothing could parse is the one thing it must not do.
        raise PipelineRefusal(
            HTTPStatus.CONFLICT, "corpus_unreadable", str(exc)
        ) from None

    plan = corpus.clearable(
        book, now=master.now(), skus=scope, older_than_days=window
    )
    cleared = {
        sku: {
            "value": book.answers[sku].value,
            **({"at": book.answers[sku].at} if book.answers[sku].at else {}),
            **(
                {"from_run": book.answers[sku].from_run}
                if book.answers[sku].from_run
                else {}
            ),
        }
        for sku in plan.skus
    }

    if plan.skus:
        # WRITTEN ONLY WHEN SOMETHING GOES. A press that selects nothing must not move the
        # digest: the screen holds a revision, and re-writing a byte-identical document would
        # still change nothing while a write that DID change the file would leave every other
        # open tab stale for a press that did nothing.
        for sku in plan.skus:
            del book.answers[sku]
        book.write()

    return {
        "ok": True,
        "cleared": cleared,
        "count": len(plan.skus),
        "holds": len(plan.holds),
        "unknown": len(plan.unknown),
        "undated": len(plan.undated),
        "answers": len(book.answers),
        "revision": _corpus_revision(),
    }


def do_pricing_restore(payload: dict) -> dict:
    """`POST /pricing/restore` — put back exactly what a clear removed. The way back.

    THE INVERSE OF THE ROUTE ABOVE AND NOTHING WIDER, which is what keeps it from being a
    second unguarded door onto `inventory/prices.json`. It writes an answer ONLY for a SKU the
    corpus does not currently hold, so it can never overwrite a price typed since the clear —
    the operator who cleared 269 answers, priced three cards, and then pressed Undo gets their
    266 back and keeps the three. Those three are named in `skipped` rather than silently
    dropped, because a way back that quietly does less than it says is worse than one that
    refuses.

    IT WRITES `at` AND `from_run` VERBATIM AND DOES NOT STAMP. `corpus.stamp_answers` is for an
    answer somebody just gave; a restore is the assertion that an answer given five days ago
    was never withdrawn. Stamping here would make the undo of a clear read as a store-wide
    re-pricing on the next markdown survey, refusing every restored SKU `priced_recently` —
    D103's ratchet, inverted by the one press whose entire job is to change nothing.

    IT IS NOT A GENERAL WRITE PATH. A hold cannot arrive through it — `Corpus.parse` is not
    reached and the shape is `{value, at?, from_run?}` — and a SKU the corpus already answers
    is refused per row. The general write is `PUT /pricing` and it is unchanged.
    """
    _clear_revision_guard(payload)
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "restore_invalid",
            "Send {\"answers\": {\"<sku>\": {\"value\": …}}} — the `cleared` map a clear "
            "answered with.",
        )
    if len(answers) > MAX_CLEAR_SKUS:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "restore_invalid",
            f"{len(answers)} answers is more than one press can restore ({MAX_CLEAR_SKUS}).",
        )

    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT, "corpus_unreadable", str(exc)
        ) from None

    restored: List[str] = []
    skipped: List[str] = []
    for sku, row in sorted(answers.items()):
        key = str(sku)
        if not isinstance(row, dict) or "value" not in row:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "restore_invalid",
                f"{key}: each answer must be an object carrying a `value`.",
            )
        if key in book.answers:
            skipped.append(key)
            continue
        book.answers[key] = corpus.Answer(
            value=row["value"],
            at=row.get("at"),
            from_run=row.get("from_run"),
        )
        restored.append(key)

    if restored:
        book.write()

    return {
        "ok": True,
        "restored": restored,
        "skipped": skipped,
        "answers": len(book.answers),
        "revision": _corpus_revision(),
    }


def _cap_flag(payload: dict) -> list:
    """`--cap N` for a send that asked for one, or nothing at all (D7, rewritten 2026-09-07).

    THERE IS NO STANDING CAP, so absent is the ordinary answer and means no bound: every copy
    the run holds that TCGplayer does not already have goes out. A number here is one press
    saying otherwise.

    BOUNDED AND INTEGER-CHECKED HERE RATHER THAN PASSED THROUGH, for `max_edge`'s reason a few
    routes over: this reaches a child process's argv, and a route that forwarded whatever
    arrived would be an argv a request controls.

    ONE PARSER FOR BOTH EMIT ROUTES. The per-run route's own comment already refuses the
    asymmetry — *"a screen that could ask for a split on a send of three and not on a send of
    one would be answering a question about how many runs are open"* — and a cap is that same
    kind of answer. Two copies of this arithmetic is how they would come to disagree.
    """
    cap = payload.get("cap")
    if cap is None:
        return []
    try:
        asked = int(cap)
    except (TypeError, ValueError):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "cap_invalid",
            "`cap` must be a whole number of copies, or absent for no cap.",
        ) from None
    if asked < 1:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "cap_invalid",
            f"A cap of {asked} would send nothing. Leave it out for no cap at all.",
        )
    return ["--cap", str(asked)]


#: The most SKUs one send may name a quantity for. The worklist is hundreds of rows at most and
#: every named pair is two argv entries; a request naming thousands is not a press.
MAX_QUANTITIES = 2000


def _quantity_flags(payload: dict) -> list:
    """`--quantity SKU=N` per card this send named a figure for, or nothing (D7, amended
    2026-09-11 on the operator's ruling).

    A SEND QUANTITY, NOT A CEILING. `{"quantities": {"8608859": 2}}` puts two copies of that
    card in the file whatever TCGplayer holds, bounded at emit time by the copies on hand that
    are not already listed. `0` sends none of that card this press. Absent or empty is the
    ordinary press: every copy that can go, goes.

    VALIDATED HERE FOR `_cap_flag`'s REASON: every pair reaches a child process's argv. The SKU
    must be a TCGplayer id — digits — and the figure a whole number in `decisions`' range,
    refused by name rather than forwarded. ONE PARSER FOR BOTH EMIT ROUTES, also for the
    reason that function gives.
    """
    asked = payload.get("quantities")
    if asked is None:
        return []
    if not isinstance(asked, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "quantities_invalid",
            "`quantities` must be an object of TCGplayer id -> whole number of copies.",
        )
    if len(asked) > MAX_QUANTITIES:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "quantities_invalid",
            f"At most {MAX_QUANTITIES} SKUs may carry a quantity in one send.",
        )
    flags = []
    for sku, count in asked.items():
        if not isinstance(sku, str) or not sku.isdigit():
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "quantities_invalid",
                f"`quantities` is keyed by TCGplayer id, got {sku!r}.",
            )
        if isinstance(count, bool) or not isinstance(count, int):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "quantities_invalid",
                f"`quantities[{sku}]` must be a whole number of copies, got {count!r}.",
            )
        if count < 0 or count > decisions.MAX_SEND_QUANTITY:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "quantities_invalid",
                f"`quantities[{sku}]` must be between 0 and {decisions.MAX_SEND_QUANTITY}, "
                f"got {count}.",
            )
        flags += ["--quantity", f"{sku}={count}"]
    return flags


def do_pipeline_merged_emit(payload: dict) -> dict:
    """`POST /pipeline/emit` — one import file over several runs (D86).

    FREE AND RE-RUNNABLE, WHICH IS WHY IT RUNS INSIDE THE REQUEST. `emit` spends nothing: it
    reads the runs, writes a CSV and raises `pushed`. The one route here that can cause money
    to be spent is still `POST /pipeline/identify` and is still named for it.

    IT IS NOT `POST /pipeline/runs/<name>/emit` WIDENED, and the difference is the point. That
    route is per run and stays; this one takes a LIST because the copies are deduped across
    it — a card in three runs is ONE row over the union of positions, keyed on `(box, index)`,
    which holds whether or not this send asked for a cap. When it does ask, the figure is also
    spent once across the send rather than once per leg: `pipeline/join.py` spends
    `live_cap - copies_out` per run, so N per-run presses at one cap are exactly the over-push
    a merged file prevents. Measured at the old standing cap of four: three separate emits over
    three real runs wrote two SKUs past it, and one merged emit wrote none.

    THE OUTPUT IS THE COMMAND'S OWN STDOUT, VERBATIM (D33). It names the file, the runs, and
    every SKU whose runs over-claimed; a screen summarising that would be deciding what
    mattered on the operator's behalf at the one moment a file is written.
    """
    wanted = payload.get("runs")
    if not isinstance(wanted, list) or not wanted:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "runs_required",
            "Send a non-empty `runs` list. A merged emit over no run is not a send.",
        )
    if len(wanted) > MAX_MERGED_RUNS:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "too_many_runs",
            f"At most {MAX_MERGED_RUNS} runs in one send.",
        )
    # RESOLVED THROUGH `_open_run`, WHICH VALIDATES THE NAME AND NEVER JOINS A PATH BLIND —
    # the same guard every other run route uses, applied before anything is read.
    directories = [str(_open_run(str(name))) for name in wanted]
    newest = sorted(str(name) for name in wanted)[-1]
    argv = [str(PKMNSCAN), "emit", *directories]
    if payload.get("listed_only"):
        argv.append("--listed-only")
    if payload.get("split_games"):
        argv.append("--split-games")
    if payload.get("split_threshold"):
        argv.append("--split-threshold")
    argv += _cap_flag(payload)
    argv += _quantity_flags(payload)
    code, console = _run_sync(argv, STEP_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "runs": [str(name) for name in wanted],
        "console": console,
        # THE FILE LANDS IN THE NEWEST RUN OF THE SEND, so that run's artefact list is where a
        # screen finds it — `GET /pipeline/runs/<name>/file` already serves it and needed no
        # widening. Answered here so the client does not have to re-derive which run that was.
        "run": newest,
        "files": _artifacts(_open_run(newest)),
        "summary": _summary(_open_run(newest)),
    }


# ------------------------------------------------------------------- the price history


def market_cache_dir() -> Path:
    """Where `pipeline/pricehistory.py`'s fetches are cached. Derived, deletable, per checkout.

    THIS IS THE DIRECTORY THAT MODULE'S HEADER WARNED THE FIRST CALLER ABOUT, and this is
    the caller. It says: *"the moment a command passes `files.home() / <something>` the
    derived cache lands in the checkout and needs a `.gitignore` line, with D47's rule
    attached: no trailing slash on a path a worktree can provision."* `/.cache` is that
    line, anchored to the repo root so it cannot silently swallow `harness/.cache`, and
    bare so it matches whatever kind of thing is at the name.

    UNDER `files.home()` AND THEREFORE PER CHECKOUT, which is D43 rather than a default. A
    worktree gets its own, usually empty, and warms it the first time somebody presses the
    key — the same posture its store, its runs and its captures already take. Sharing one
    across checkouts would save a handful of requests and put a branch's writes inside the
    main tree, which is the trade D43 spends a whole entry refusing.

    NOTHING PRUNES IT AND NOTHING NEEDS TO. Entries are small JSON, the TTLs inside the
    module decide what is stale, and a corrupt entry is read as a miss rather than as a
    refusal — so the worst this directory can do is take up a few megabytes, and `rm -rf`
    is a complete remedy at any moment.
    """
    return files.home() / ".cache" / "market"


def _history_row(directory: Path, sku: str) -> dict:
    """This run's `pricing.json` entry for one SKU, or a refusal naming which half is missing.

    THE EXPORT ROW IS WHAT THE READER NEEDS, AND THIS RUN ALREADY HOLDS IT VERBATIM.
    `cli/cmd_join.py:_pricing_table` writes every matched SKU's row unmodified under `row`,
    for D49's reason — the screen shows what the CSV says — and that is exactly the five
    cells the catalog walk reads: `Product Line`, `Set Name`, `Number`, `Product Name` and
    `TCGplayer Id`. So there is no second source to keep in step and no re-parse of an
    export: the run that priced this card is the run that says what it is.
    """
    table = directory / run_files.PRICING
    if not table.is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_not_written",
            f"Run {directory.name} has no {run_files.PRICING} — `join` is what writes it, "
            f"and a price history is read off the export row it stores. Join this run.",
        )
    try:
        payload = json.loads(table.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_unreadable",
            f"{run_files.PRICING} could not be read: {exc}. Re-join this run to rewrite it.",
        ) from None
    for entry in payload.get("skus") or ():
        if str(entry.get("sku") or "") == sku:
            return entry
    raise PipelineRefusal(
        HTTPStatus.NOT_FOUND,
        "sku_not_in_run",
        f"Run {directory.name} matched no SKU {sku}. A history is read off the export row "
        f"this run stored, so a SKU it never matched has no row here to read.",
    )


def _money(value) -> Optional[str]:
    """A `Decimal` as a string, or None. The wire carries money as text, never as a float.

    `cli/cmd_join.py` writes every figure in `pricing.json` this way and for the same
    reason: a price that goes through a JSON float comes back as binary floating point,
    and `pipeline/pricing.py` computes in `Decimal` precisely so that never happens.
    """
    return None if value is None else str(value)


def _history_series(series) -> dict:
    """One range of one SKU, as the screen reads it.

    THE VWAP IS THE ANCHOR AND THE BOUND IS A SANITY CHECK. Both are on the wire and they
    are NOT peers: `pipeline/pricehistory.py`'s header is explicit that a true VWAP is not
    computable from buckets and that rendering the two as a price and an error bar of
    comparable authority is that paragraph being ignored. The field names carry the
    distinction as far as a payload can — `vwap` is a figure, `bound` is an object with its
    own two widths — and `app/src/Pricing.tsx` is where the drawing honours it.

    `points` IS THE BUCKETS, ASCENDING, and it is here because a sparkline answers *is this
    rising* in one glance where four numbers do not. It is the parsed order and never the
    wire order — the endpoint sends newest-first, `Series.parse` sorts, and a payload that
    passed the raw list through would draw every rising card falling.
    """
    momentum = series.momentum()
    bound = series.bound
    starts = [b.start for b in series.buckets if b.start is not None]
    return {
        "range": series.range,
        "buckets": len(series.buckets),
        # The span the buckets actually cover, which is what lets the panel caption a range
        # without restating the width table in TypeScript. `annual` is the STALER of the two
        # — weekly buckets are stamped at the start of their week — so a screen drawing both
        # has to be able to say when each one ends.
        "from": starts[0].isoformat() if starts else None,
        "to": starts[-1].isoformat() if starts else None,
        "latest_market": _money(series.latest_market),
        "vwap": _money(series.vwap),
        "bound": (
            None
            if bound is None
            else {
                "low": _money(bound.low),
                "high": _money(bound.high),
                # BOTH DENOMINATORS, NAMED, which is `Bound`'s own rule: one card's interval
                # is honestly "48% wide" and "62% wide" and a bare percentage invites the two
                # to be read as a disagreement about the same card.
                "width_of_vwap": _money(bound.width_of_vwap),
                "width_of_low": _money(bound.width_of_low),
            }
        ),
        "momentum": {
            "early": _money(momentum.early),
            "late": _money(momentum.late),
            "change": _money(momentum.change),
            "fraction": _money(momentum.fraction),
            "window": momentum.window,
        },
        "liquidity": series.liquidity,
        "transactions": series.total_transaction_count,
        "units_per_transaction": _money(series.units_per_transaction),
        "dispersion": _money(series.dispersion),
        "points": [
            {
                "at": bucket.start.isoformat() if bucket.start else None,
                "market": _money(bucket.market),
                "quantity": bucket.quantity,
                "low": _money(bucket.low),
                "high": _money(bucket.high),
            }
            for bucket in series.buckets
        ],
    }


def do_pipeline_history(name: str, sku: str) -> dict:
    """`GET /pipeline/runs/<name>/history?sku=<sku>` — what this SKU has been selling for.

    THE ONE ROUTE IN THIS FILE THAT TALKS TO A THIRD PARTY. The header above carries the
    whole argument and the short form is: it spends nothing, both hosts are public, it
    writes only its own derived cache, and it cannot fire without a press.

    IT PRICES NOTHING AND D8 IS NOT REOPENED. `pipeline/pricehistory.py`'s own header is
    emphatic on this and the route is the place it could quietly stop being true: nothing
    here computes a listing price, writes `TCG Marketplace Price`, or reaches
    `inventory/prices.json`. It is a READING taken beside the export, on the screen where a hold is
    set — D49 records that the `bullish` withhold and its `watch_above` threshold have been
    set against the operator's memory of what a card used to cost, and this is the fact that
    was missing. The day a listing price is allowed to depend on a trend, that is a change
    to D8 argued on its own terms and not a widening of this handler.

    IT IS SYNCHRONOUS, AND THAT IS THE SHAPE OF THE WORK RATHER THAN A SHORTCUT. The
    header's rule is that the money step spawns because a Batch takes hours, and everything
    else answers in the request because it finishes in seconds. This is the second kind:
    five requests cold and two warm, each one a small JSON document off a mirror. The server
    is threaded, so a slow host costs this request and no other.

    A REFUSAL IS A SENTENCE WITH ITS OWN CODE, and there are four kinds. The run has no
    table, or no such SKU (`_history_row`). The card is not one a catalogue covers
    (`not_catalogued`). The walk found no single product (`history_unresolved`). A host did
    not answer (`history_unreachable`). Each names what to do next, because a panel that
    said only "failed" would send the operator to the wrong file — a `misc` card with no
    product line and a mirror having a bad day are not the same problem.
    """
    directory = _open_run(name)
    wanted = _wanted_sku(sku)
    return _history_for_entry(_history_row(directory, wanted), wanted, {"run": directory.name})


def _wanted_sku(sku: str) -> str:
    wanted = (sku or "").strip()
    if not wanted:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "sku_required",
            "A price history is per SKU. Pass ?sku=<TCGplayer Id>.",
        )
    return wanted


def _history_for_entry(entry: dict, wanted: str, source: dict) -> dict:
    """The reading for one row, whichever document that row came out of.

    THE SPLIT IS THE ADDRESS, NOT THE WORK. A run's `pricing.json` entry and a markdown's
    `survey.json` entry are two shapes over one fact — the verbatim export row — and the
    catalogue walk reads five cells out of it (`Product Line`, `Set Name`, `Number`,
    `Product Name`, `TCGplayer Id`), which a My Pricing export carries on every row. So the
    markdown routes are a second ADDRESS over this body and never a second implementation:
    `not_catalogued`, `history_unresolved` and `history_unreachable` are one vocabulary, and
    the cache below is keyed by product rather than by document, so a card already read on a
    run is warm here.

    `source` NAMES THE DOCUMENT and is spread into the answer — `{"run": …}` or
    `{"markdown": …}`. A markdown stamp sent back under a field called `run` would be a lie
    the client had to decode.
    """
    row = entry.get("row") or {}

    # NOT EVERY CARD HAS A CATALOGUE, AND THAT IS D22 RATHER THAN A GAP. `misc` carries
    # `product_line: None` by construction, so there is no cell to look a category up by and
    # no history to fetch — checked here, where the caller can act on it, rather than left to
    # refuse three hops down the walk with a message about a category name.
    if not pricehistory.catalogued_row(row):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "not_catalogued",
            f"{entry.get('name') or wanted} is not in a catalogued product line, so there is "
            f"no product to look a history up by. D22 makes that the permanent state for "
            f"`misc` rather than a missing export.",
        )

    market = pricehistory.Market(cache_dir=market_cache_dir())
    try:
        reading = market.reading_for_row(row)
    except pricehistory.Unreachable as exc:
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "history_unreachable",
            f"{exc} Nothing is wrong with this run — a public mirror did not answer, and "
            f"the reading is the only thing lost. Try again.",
        ) from None
    except pricehistory.NotResolvable as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "history_unresolved",
            str(exc),
        ) from None

    return {
        **source,
        "sku": reading.sku,
        "product_id": reading.product_id,
        # The card's own identity, off the run's table rather than re-derived, so the panel
        # can caption itself without the caller passing three strings it already holds.
        "name": entry.get("name"),
        "set_name": entry.get("set_name"),
        "condition": entry.get("condition"),
        # THE EXPORT'S OWN FIGURE, BESIDE THE READING AND NEVER MIXED INTO IT. This is what
        # the card is priced against today (D8), and the whole point of the panel is to put
        # it next to what the card has actually been selling for. They are two sources read
        # at two moments and nothing here averages them.
        "market": (entry.get("snap") or {}).get("market"),
        # ONE ENTRY PER RANGE, IN `DEFAULT_RANGES` ORDER — finest first. The ranges OVERLAP
        # and this list is two readings to present side by side, never two halves to add up:
        # `annual` is not the year before `month`, it is 357 days that INCLUDE the same
        # recent days at a coarser width. Nothing here merges them and nothing may start.
        "ranges": [
            _history_series(reading.series[r])
            for r in pricehistory.DEFAULT_RANGES
            if r in reading.series
        ],
        # A CARD THE ENDPOINT HAS NEVER SEEN SELL IS AN EMPTY LIST AND NOT AN ERROR. HTTP 200
        # with a null result is what it answers for a real, catalogued product that has
        # simply never traded — measured on two of them — so a screen that read an empty
        # `ranges` as a failure would report a join defect over a card that is merely
        # illiquid. This flag is what lets the panel say the honest thing instead.
        "never_sold": not reading.series,
    }


def _history_spark(series) -> dict:
    """One range of one SKU, as a ROW draws it. Deliberately not `_history_series`.

    THE LEAN SHAPE IS THE POINT, AND IT IS A DESIGN RULE RATHER THAN A SAVING. D62's panel
    is where a reading's numbers live — the vwap at display size, its bound muted beneath,
    liquidity, spread, the export's own figure beside them. A row has space for a shape and
    one number, so this carries a shape and one number, and a row that wanted more would be
    the panel drawn badly forty-six times.

    NO MONEY CROSSES THIS FUNCTION AND THAT IS THE SECOND REASON. The row already carries
    four dollar columns and the field a listing price is typed into; a fifth figure that is
    a READING rather than a price would sit inches from that field inviting the operator to
    copy it in, which is the D8 reopening D62 refused in as many words. `fraction` is
    dimensionless and `points` are drawn to a 44px box and never labelled.

    THE SIZE IS ALSO WHY. `_history_series` carries five fields per bucket; over 46 SKUs and
    two ranges that is ~19,000 numbers for a strip that draws one of the five.
    """
    starts = [b.start for b in series.buckets if b.start is not None]
    return {
        "range": series.range,
        # The span, because the two ranges END ON DIFFERENT DAYS — weekly buckets are stamped
        # at the start of their week, so `annual` is the STALER of the pair. The row has no
        # room to caption that and the section's caption states it once, off these.
        "from": starts[0].isoformat() if starts else None,
        "to": starts[-1].isoformat() if starts else None,
        # POSITIVE IS RISING, and the sign survives only because `Series.parse` sorted the
        # buckets ascending — the endpoint sends them newest-first.
        "fraction": _money(series.momentum().fraction),
        # THE SHAPE, AND NOTHING ELSE OFF THE BUCKET. A `null` is a bucket with no price at
        # all and the client BREAKS the line there rather than interpolating: measured on
        # Vilemaw's annual, whose oldest bucket predates the card's printing, and joining
        # through it would draw a year-long slope that never happened.
        "points": [_money(bucket.market) for bucket in series.buckets],
    }


def do_pipeline_trends(name: str, skus: Sequence[str] = ()) -> dict:
    """`GET /pipeline/runs/<name>/trends` — the shape of many SKUs at once, for the row strip.

    D62 NAMED THIS ROUTE AND THE CONDITION FOR BUILDING IT. Its closing paragraph: *"What
    would reopen this: the panel being opened on every card... the honest answer is a batched
    route — `readings_for_rows` already exists in the module and groups by productId — and a
    column on the row rather than a panel beside it. The measurement is whether the operator
    presses `T` more often than they press `H`."* The owner answered that measurement on
    2026-08-31 by asking for the graphs on every row. This is the route that entry specified,
    built to the shape it specified, and D79 records what the answer cost.

    IT IS STILL A PRESS AND THAT IS THE WHOLE OF D62 THAT SURVIVES INTACT. Nothing polls
    this and no render fires it: a screen that read it on mount would turn every visit to
    `#/pricing` into ~92 requests at a free public mirror for readings nobody asked for,
    which is the one way D62 said this feature could become rude. What changed is the
    GRANULARITY of the press — one for the list instead of one per card — and not whether
    there is one.

    IT SKIPS THE ROWS THIS RUN CAN ADD NOTHING FOR, on the owner's instruction of the same
    day: *"I don't need the prices for the rows that have none left."* `at_cap` is the field
    `cli/cmd_join.py` already writes and the same one the list groups those rows under, so
    the two agree by construction rather than by two definitions kept in step. Measured on
    `2026-08-31-box3-01`: 60 SKUs, 14 at the cap, so 46 asked and 28 requests not made.
    **They are not unreachable** — `T` still reads any one of them, which is the right shape
    for a row the operator has a reason to be curious about and no reason to be shown.

    AN EXPLICIT `?sku=` LIST OVERRIDES THAT FILTER, AND IT IS WHAT MAKES THE ROUTE
    PROGRESSIVE. 46 SKUs is ~34s of courtesy delay and the client walks them in chunks so the
    strip fills in waves rather than after a blank half-minute — see `app/src/Pricing.tsx`.
    A named SKU is fetched whatever its `at_cap`, because a caller naming a row has already
    decided; the filter is a default over the run, not a rule about SKUs.

    BOTH DIRECTIONS, WHICH IS `CLAUDE.md`'s HARD RULE. Every asked SKU comes back in exactly
    one of `skus` or `refused`, never dropped — `readings_for_rows` makes the same promise one
    layer down and this route keeps it across the two filters it applies on top: a SKU that is
    not in this run's table and one whose product line has no catalogue (D22) are named with
    the reason rather than silently absent.
    """
    directory = _open_run(name)
    table = directory / run_files.PRICING
    if not table.is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_not_written",
            f"Run {directory.name} has no {run_files.PRICING} — `join` is what writes it, "
            f"and a price history is read off the export rows it stores. Join this run.",
        )
    try:
        payload = json.loads(table.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_unreadable",
            f"{run_files.PRICING} could not be read: {exc}. Re-join this run to rewrite it.",
        ) from None

    entries = {
        str(entry.get("sku") or ""): entry
        for entry in (payload.get("skus") or ())
        if str(entry.get("sku") or "")
    }
    return _trends_for_entries(
        entries,
        [s for s in (str(x).strip() for x in skus) if s],
        {"run": directory.name},
        missing=(
            f"Run {directory.name} matched no SKU {{sku}}. A history is read off the "
            f"export row this run stored."
        ),
        skip_at_cap=True,
    )


def _trends_for_entries(
    entries: Dict[str, dict],
    wanted: Sequence[str],
    source: dict,
    *,
    missing: str,
    skip_at_cap: bool,
) -> dict:
    """The strip's readings over many rows, whichever document those rows came out of.

    ONE IMPLEMENTATION, TWO ADDRESSES — `_history_for_entry`'s argument, and the same cache.
    What differs between a run and a markdown is entirely in the caller: which file the
    entries came from, what to call a SKU it does not hold, and whether an unfiltered walk is
    allowed at all.

    `skip_at_cap` IS A RUN'S DEFAULT AND IS MEANINGLESS FOR A MARKDOWN. It skips the rows a
    run can add nothing for, on the owner's *"I don't need the prices for the rows that have
    none left"*; nothing on a live listing is at the cap, so the markdown route passes False
    and requires an explicit list instead — see `do_markdown_trends` for why the size makes
    that necessary rather than tidy.
    """
    refused: Dict[str, str] = {}
    skipped = 0
    rows: List[dict] = []
    for sku in wanted or list(entries):
        entry = entries.get(sku)
        if entry is None:
            # ONLY REACHABLE THROUGH AN EXPLICIT `?sku=`, since the unfiltered walk is over
            # this table's own keys. Named rather than dropped: a client asking about a SKU
            # this run never matched has a stale list, and silence would look like a mirror
            # that had nothing to say about a real card.
            refused[sku] = missing.format(sku=sku)
            continue
        if skip_at_cap and not wanted and entry.get("at_cap"):
            # THE DEFAULT SKIP, AND IT IS COUNTED RATHER THAN HIDDEN. A screen that showed 46
            # readings over a 60-row list with no number beside them would look like 14 rows
            # had failed. This is what lets it say they were never asked about.
            skipped += 1
            continue
        row = entry.get("row") or {}
        if not pricehistory.catalogued_row(row):
            # D22 MAKES THIS PERMANENT RATHER THAN A GAP. `misc` carries no product line, so
            # there is no category to look a history up by — a refusal with its own sentence,
            # not an empty reading.
            refused[sku] = (
                f"{entry.get('name') or sku} is not in a catalogued product line, so there "
                f"is no product to look a history up by (D22)."
            )
            continue
        rows.append(row)

    market = pricehistory.Market(cache_dir=market_cache_dir())
    # THE WALK ITSELF NEVER RAISES PAST HERE. `readings_for_rows` catches every
    # `PriceHistoryError` per product and answers refusals alongside readings, which is the
    # right shape for a batch: one unresolvable card must not cost the other forty-five their
    # reading, and a mirror having a bad day is reported per SKU rather than as one 502 that
    # says nothing about which rows were affected.
    readings, walked = market.readings_for_rows(rows)
    refused.update(walked)

    return {
        **source,
        "asked": len(rows),
        "skipped": skipped,
        "skus": {
            sku: {
                "product_id": reading.product_id,
                # ONE ENTRY PER RANGE, IN `DEFAULT_RANGES` ORDER — finest first, the same
                # order the panel draws and the same list. The ranges OVERLAP and are never
                # two halves to add up.
                "ranges": [
                    _history_spark(reading.series[r])
                    for r in pricehistory.DEFAULT_RANGES
                    if r in reading.series
                ],
            }
            for sku, reading in readings.items()
        },
        "refused": refused,
    }


def do_pipeline_file(name: str, filename: str) -> Tuple[bytes, str]:
    """`GET /pipeline/runs/<name>/file?name=<f>` — one artefact's bytes, for download.

    The filename is matched against `_DOWNLOADABLE` and then checked to be a file THIS run
    directory actually lists, which is belt and braces on purpose: the pattern already
    excludes a separator, and the membership test means even a pattern loosened later cannot
    reach outside the run.
    """
    directory = _open_run(name)
    if not _DOWNLOADABLE.match(filename or ""):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "file_name_invalid",
            f"{filename!r} is not a downloadable run artefact.",
        )
    if filename not in {row["name"] for row in _artifacts(directory)}:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_file",
            f"Run {name} has no file called {filename}. It may not have been written yet — "
            f"`emit` is what writes the import files.",
        )
    target = directory / filename
    kind = "text/csv" if target.suffix == ".csv" else "text/plain; charset=utf-8"
    return target.read_bytes(), kind


# --------------------------------------------------------------- the free steps of the run


def _store_upload(directory: Path, upload: dict, prefix: str) -> Path:
    """Write an uploaded CSV into the run directory and return its path.

    UPLOADED RATHER THAN NAMED BY PATH, and the reason is worth stating because a path would
    have been three lines. A screen cannot know what is on the server's disk, and a route
    that opened any absolute path a request named would be a file-read primitive guarded by
    an origin header. Uploading also leaves the run holding the exact bytes it was joined
    against, which `cli/runs.py`'s manifest can only describe by hash — a run whose export
    has since been deleted from Downloads can still be re-joined, re-emitted and explained.
    """
    content = upload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_empty",
            "An uploaded export carried no content.",
        )
    if "," not in content.splitlines()[0]:
        # The cheapest possible check that this is a CSV at all, and it earns its place: the
        # failure it prevents is `join` refusing an empty catalog several seconds later with
        # a message about product lines, for a file that was never a spreadsheet.
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_not_csv",
            "That file's first line has no comma in it, so it is not a TCGplayer export. "
            "Use the Pricing tab's Export Filtered CSV, All Printings.",
        )
    raw = str(upload.get("name") or "export.csv")
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", Path(raw).name) or "export.csv"
    target = directory / f"{prefix}{stem}"
    target.write_text(content, encoding="utf-8")
    # THE STORED COPY WEARS THE FILE'S OWN TIME, because that mtime is when the export's
    # `Total Quantity` was read and the store arbitrates `live` by it (D87 amended,
    # `store/master.py:Listing.observe_live`). `modified` is the browser's `File.lastModified`
    # — MILLISECONDS since the epoch — and without it every upload was dated to the moment it
    # was copied in, so a week-old export outranked every reading the store had taken since.
    # Sanity-bounded rather than trusted: a stamp before 2000 or past tomorrow is nonsense,
    # and nonsense that reads as "newer than everything" would settle the whole store.
    modified = upload.get("modified")
    if isinstance(modified, (int, float)) and not isinstance(modified, bool):
        seconds = float(modified) / 1000.0
        if _UPLOAD_MTIME_FLOOR <= seconds <= time.time() + 86400:
            os.utime(target, (seconds, seconds))
    return target


# 2000-01-01T00:00:00Z. A `File.lastModified` below this is not a time anybody exported at.
_UPLOAD_MTIME_FLOOR = 946684800.0


def _find_fetched(directory: Path, wanted: str) -> Optional[Path]:
    """A fetched export by name: this run's own directory, then the game directories.

    SHAPE, THEN PREFIX, THEN MEMBERSHIP — `_open_live_export`'s rule, and the caller has
    already done the first two. What changed with the move is that membership is now of a SET
    of directories rather than of one, and it is still membership: the name is matched against
    files that exist, never joined onto a path and opened.

    THE RUN'S OWN DIRECTORY IS FIRST AND IT IS NOT A FALLBACK — it is the LEGACY location, and
    the owner's store holds 19 files there. Those runs go on joining against the file they were
    joined against, which is the rule a run directory being an immutable input already implies.
    """
    legacy = directory / wanted
    if legacy.is_file():
        return legacy
    root = files.inventory_dir() / EXPORTS_DIR
    for game in sorted(game_registry.keys()):  # noqa: SIM118 — pipeline.games MODULE
        candidate = root / game / wanted
        if candidate.is_file():
            return candidate
    return None


def _exports_for_join(directory: Path, payload: dict) -> List[str]:
    """`--export` arguments: what was fetched, what was uploaded, or what the manifest holds.

    Falling back to the manifest is what keeps `join` free and re-runnable from a screen —
    change the rule, clear a review, press it again, and the same files answer. `join`
    itself already reads `exports_by_game` when no `--export` is given, so this passes
    nothing rather than re-deriving the mapping and risking a different answer.

    THE THREE SOURCES COMPOSE, which is what a mixed-game run needs: one game's export can be
    fetched while another's is uploaded, and `cli/resolve.py:exports_for` is what rules on the
    result — one file per game, refusing two claimants, refusing a game the run holds and no
    file covers. This function chooses no game and reads no `Product Line` cell.
    """
    argv: List[str] = []

    # A FILE THIS RUN ALREADY HOLDS, NAMED RATHER THAN RE-SENT. `POST .../export` fetched it
    # and wrote it here; asking the client to read it back and upload it again would put a
    # megabyte through the browser twice to arrive at the bytes the server already has. The
    # name is validated the way `do_pipeline_file` validates a download — by SHAPE, then by
    # membership of this run's own directory — so nothing built from a request is joined onto
    # a path, and the prefix check means only a file THIS route wrote can be named.
    fetched = payload.get("fetched")
    if fetched is not None:
        if not isinstance(fetched, list) or not fetched:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "fetched_invalid",
                "`fetched` must be a non-empty array of file names this run holds, or be "
                "absent. POST /pipeline/runs/<name>/export is what puts one there.",
            )
        for wanted in fetched:
            if (
                not isinstance(wanted, str)
                or not _DOWNLOADABLE.match(wanted)
                or not wanted.startswith(FETCHED_PREFIX)
            ):
                raise PipelineRefusal(
                    HTTPStatus.BAD_REQUEST,
                    "fetched_invalid",
                    f"{wanted!r} is not the name of a fetched export.",
                )
            candidate = _find_fetched(directory, wanted)
            if candidate is None:
                raise PipelineRefusal(
                    HTTPStatus.NOT_FOUND,
                    "no_such_file",
                    f"No fetched export named {wanted}, in run {directory.name} or under "
                    f"inventory/{EXPORTS_DIR}/. A fetch that refused deletes what it wrote, "
                    f"so this is a name from a fetch that did not land.",
                )
            argv += ["--export", str(candidate)]

    uploads = payload.get("exports")
    if uploads is None:
        return argv
    if not isinstance(uploads, list) or not uploads:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "exports_invalid",
            "`exports` must be a non-empty array of {name, content}, or absent to re-use "
            "the files this run was last joined against.",
        )
    for upload in uploads:
        if not isinstance(upload, dict):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST, "exports_invalid", "Each export must be an object."
            )
        argv += ["--export", str(_store_upload(directory, upload, "export-"))]
    return argv


def _pricing_flags(payload: dict) -> List[str]:
    flags: List[str] = []
    rule = payload.get("rule")
    if rule is not None:
        if not isinstance(rule, str) or not re.fullmatch(
            r"match|undercut:\d+(\.\d+)?|markup:\d+(\.\d+)?", rule
        ):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "rule_invalid",
                "`rule` is match, undercut:PCT or markup:PCT.",
            )
        flags += ["--rule", rule]
    basis = payload.get("basis")
    if basis is not None:
        if basis not in ("market", "low"):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST, "basis_invalid", "`basis` is market or low."
            )
        flags += ["--basis", basis]
    below = payload.get("review_below_confidence")
    if below is not None:
        if below not in ("none", "low", "medium"):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "review_below_invalid",
                "`review_below_confidence` is none, low or medium.",
            )
        flags += ["--review-below-confidence", below]
    return flags


# ------------------------------------------------------------ the export, fetched not typed
#
# THE LAST MANUAL STEP IN `runs -> join`, AND WHAT REMOVING IT COSTS (D64). `identify` spawns
# detached, `join`, `emit` and `reconcile` are free and re-runnable, and every artefact is
# downloadable — so the one thing an operator still had to do by hand between a finished
# batch and a joined run was open TCGplayer, press Export Filtered CSV, wait, and upload the
# file back. `server/tcg_export.py` fetches it instead, and this route is the only caller.
#
# IT IS REPORTED SEPARATELY FROM THE JOIN, deliberately: a fetch that fails and a join that
# fails are different faults with different remedies, and one console carrying both would
# leave "the session expired" and "no catalog row" reading as the same kind of bad day.


def _sku_set(export) -> set:
    """Every `TCGplayer Id` in an export. The unit the receipt counts SKUs in."""
    return {
        str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
        for row in export.rows
        if str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
    }


def _distinct(export, column: str) -> List[str]:
    """The distinct values of one column, in first-appearance order — for the report."""
    seen: List[str] = []
    for row in export.rows:
        value = str(row.get(column) or "").strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def _export_report(path: Path, games: Sequence[str]) -> dict:
    """What arrived, in the terms the operator filters the portal in."""
    export = tcgcsv.read_export(path)
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "games": list(games),
        "rows": len(export.rows),
        "skus": len(_sku_set(export)),
        "sets": _distinct(export, tcgcsv.SET_COLUMN),
        "conditions": _distinct(export, tcgcsv.CONDITION_COLUMN),
        "product_lines": list(tcgcsv.product_lines(export)),
    }


# The set vocabulary, cached for this process. TCGplayer's set list for a category changes
# when a set releases, which is monthly at most, and the capture screen asks for it every time
# the operator opens the hint field. Cached rather than re-fetched because the rig is the
# latency-sensitive surface in this product (D19's 623 ms cadence) and because a screen that
# fetched per keystroke would spend the owner's session on autocomplete.
_SETS_CACHE: Dict[int, list] = {}


def do_tcg_sets(game: str) -> dict:
    """`GET /tcg/sets?game=<game>` — the real set names for a game, for the capture screen.

    THE WHITELIST HALF OF D65. A hint typed free-hand has to be matched against TCGplayer's
    vocabulary later, and the two do not agree: `OGN` is the community code for the set
    TCGplayer calls `Origins`. Offering the real names at capture time makes the stored hint
    exact by construction, so the matching that follows is an equality test rather than three
    rules and an alias table.

    IT DEGRADES TO NOTHING AND MUST. The capture screen is the rig, and D19 measures its
    cadence in milliseconds; a set list that cannot be fetched — no cookie, no network, the
    portal down — has to leave the operator typing free text exactly as before rather than
    blocking a capture. So every failure here answers 200 with an empty list and a reason,
    and the screen renders a plain input when the list is empty.
    """
    entry = game_registry.get(game) or {}
    category = entry.get("tcgplayer_category_id")
    if not category:
        # NOT A TRANSPORT REFUSAL AND SO NOT A TRANSPORT SENTENCE. Nothing was fetched:
        # this game carries no `tcgplayer_category_id`, which is a fact about
        # `pipeline/games.py` rather than about the portal, and the screen says so in
        # its own words. The key is present and null for the one-shape rule above.
        return {"game": game, "sets": [], "reason": "no_category", "message": None}
    category = int(category)
    if category not in _SETS_CACHE:
        try:
            vocabulary = tcg_export.filters(category)
        except tcg_export.FetchRefusal as caught:
            # NOT AN ERROR TO THE SCREEN. The operator is mid-capture; a refusal here is a
            # missing convenience, not a failed capture, and the reason is carried so the
            # screen can say why the list is empty rather than pretending the game has no sets.
            #
            # AND THE SENTENCE TRAVELS WITH IT, WHICH IT DID NOT UNTIL 2026-09-06. This was
            # the one refusal path of four that kept the code and dropped `message` — the
            # other three (`do_pipeline_export`, `do_live_export`, `do_run_scope`) all carry
            # it — and it is the one whose consumer re-labels from a map. `hintReason` named
            # two of the NINE codes `tcg_export.filters` can raise, so seven fell to that
            # map's unknown-code tail.
            #
            # THE TAIL IS A DESIGN AND THE MAP IS THE FIX. `CaptureScreen.tsx` argues the
            # bare code deliberately — docs/DESIGN.md shows reason codes beside names, so
            # what the operator saw stays greppable — and that argument is older than this
            # comment. What was wrong was seven of nine landing on it. The map is wide now,
            # `make docs-audit`'s `hint reasons` row keeps it wide, and this key is the layer
            # between the two: words instead of a bare token for a code the map has not
            # caught up with. NOT what the operator normally reads, and the screen must not
            # let it become that — the sentences below name `.env`, and that screen does
            # not.
            return {"game": game, "sets": [], "reason": caught.code, "message": caught.message}
        _SETS_CACHE[category] = [
            {"name": str(row.get("Text") or ""), "id": str(row.get("Value") or "")}
            for row in (vocabulary.get("Sets") or [])
            if str(row.get("Value") or "") != "0"
        ]
    aliases = entry.get("set_aliases") or {}
    return {
        "game": game,
        "sets": _SETS_CACHE[category],
        # The codes the owner types, offered beside the names so the list is searchable by
        # either. A hint stored as an alias still resolves — `match_sets` folds it first.
        "aliases": {str(k): str(v) for k, v in aliases.items()},
        "reason": None,
        # ALWAYS PRESENT, NULL ON SUCCESS, so the client reads one shape rather than probing
        # for a key. `previous` in the export receipt is the same rule.
        "message": None,
    }


def _scope_counts(directory: Path) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """Per game in this run: how many cards, how many carry a set hint, and which hints.

    COUNTED, NOT COLLECTED, AND THAT IS THE WHOLE OF D76. The shape here used to be a set of
    hint strings, which cannot answer "did EVERY card carry one" — a set of hints has already
    forgotten how many cards there were. `cards` and `hinted` are the two numbers the
    unanimity rule turns on, so they are what this returns.

    ONE COUNTER FOR THE PREVIEW AND THE FETCH. `GET .../scope` draws what a press would ask
    for and `POST .../export` presses it; two implementations of "how many cards are hinted"
    would be a screen that can disagree with the request it launches, which is the same class
    of defect as the estimate `_parse_preflight` refuses to recompute.

    Returns `(every game the cards claim, the subset with a catalog to ask for)`.
    """
    cards = (files.read_json(directory / run_files.IDENTIFICATIONS) or {}).get("cards") or {}
    if not cards:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "export_refused",
            f"{directory / run_files.IDENTIFICATIONS} does not exist — run `pkmnscan "
            f"identify` first.",
        )

    by_game: Dict[str, dict] = {}
    for record in cards.values():
        game = record.get("game") or game_registry.DEFAULT_GAME
        hint = (record.get("set_hint") or "").strip()
        held = by_game.setdefault(game, {"cards": 0, "hinted": 0, "hints": set()})
        held["cards"] += 1
        if hint:
            held["hinted"] += 1
            held["hints"].add(hint)

    # A GAME STRING NOBODY REGISTERED IS DROPPED HERE RATHER THAN RAISED. `games.get` refuses
    # an unknown key by design and `identify/sidecar.py` deliberately carries one through
    # unchanged, so a single bad sidecar reaching this line used to be a 500 on a free route.
    # It has no category id, so it has nothing to ask for and belongs in neither branch.
    catalogued: Dict[str, dict] = {}
    for key, held in by_game.items():
        try:
            entry = game_registry.get(key)
        except game_registry.UnknownGame:
            continue
        if entry.get("catalogued", True) and entry.get("tcgplayer_category_id"):
            catalogued[key] = held
    return by_game, catalogued


def _scope_for_run(directory: Path, payload: dict) -> Tuple[object, dict]:
    """What to ask TCGplayer for: the run's own claims, the game's rule, and the operator.

    THE CLAIMS THE OPERATOR ALREADY MADE ARE THE DEFAULT SCOPE (D65). A card carries its game
    and, where the operator set one, a set hint — so a box captured as Riftbound/Unleashed
    already says which category and which set its export needs, and nothing new is asked.

    ONE CATEGORY PER FETCH, because `CategoryId` is scalar in the portal's own request. A
    mixed-game run therefore fetches once per game, which the join composes; the game is
    chosen by `game` in the request or is the run's only one.

    WIDENING IS ALWAYS SAFE AND NARROWING NEVER IS — AND THE FIRST BUILD COUNTED THE WRONG
    THING (D76). It collected the hints that EXISTED and never counted the cards carrying
    none, so a box sorted by rarity with one set hint on one card scoped the whole export to
    that one set. Measured on a synthetic 200-card Riftbound run: `SetNameIds` came back
    `["77"]`, 199 cards had no catalog row to match, and the positive check passed because
    the set that was asked for did arrive. A hint is now evidence about the card that carries
    it and about no other card, so a set filter needs the box to be UNANIMOUS.

    THREE THINGS DECIDE, IN THIS ORDER, and each is reported in `asked` so the screen can say
    which one spoke:

      the operator   explicit `set_ids` is a claim about this box that outranks every
                     inference, in both directions. `scope` alone picks the axis.
      the game       `games.export_scope` — `category` where the whole catalogue is measured
                     to come down in one file (riftbound), `sets` everywhere else.
      the cards      under `sets`: every card hinted and every hint resolved, or it widens.
    """
    payload_game = payload.get("game")
    by_game, catalogued = _scope_counts(directory)
    if not catalogued:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "export_no_category",
            f"No game in this run has a TCGplayer category id, so there is nothing to ask "
            f"for. Games held: {', '.join(sorted(by_game)) or 'none'}.",
        )
    if payload_game is not None:
        if payload_game not in catalogued:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "game_not_in_run",
                f"This run holds no {payload_game} card that needs a catalog. It holds: "
                f"{', '.join(sorted(catalogued))}.",
            )
        game = payload_game
    elif len(catalogued) == 1:
        game = next(iter(catalogued))
    else:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "game_required",
            f"This run holds more than one game and one fetch answers for one category. "
            f"Send `game` as one of: {', '.join(sorted(catalogued))}. Each is fetched "
            f"separately and the join takes them together.",
        )

    entry = game_registry.get(game)
    category = int(entry["tcgplayer_category_id"])
    held = catalogued[game]
    hints = sorted(held["hints"])
    total, hinted = int(held["cards"]), int(held["hinted"])
    unhinted = total - hinted

    policy = game_registry.export_scope(game)
    wanted = payload.get("scope")
    if wanted is not None and wanted not in game_registry.EXPORT_SCOPES:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "scope_invalid",
            f"`scope` is one of {', '.join(game_registry.EXPORT_SCOPES)}, or absent to use "
            f"this game's own rule ({policy}).",
        )
    chosen = payload.get("set_ids")

    set_ids: Tuple[int, ...] = ()
    unresolved: Tuple[str, ...] = ()
    names: List[str] = []
    vocabulary: Optional[dict] = None

    def _vocabulary() -> dict:
        """The portal's set list, fetched at most once and only where a name is needed.

        LAZY BECAUSE THE WHOLE-CATEGORY PATH DOES NOT NEED IT. `getjsonfilters` is a second
        network round trip against the same host, and a fetch that has already decided to
        take every set has nothing to resolve and no name to print.
        """
        nonlocal vocabulary
        if vocabulary is None:
            vocabulary = tcg_export.filters(category)
        return vocabulary

    def _names(ids) -> List[str]:
        wanted_ids = {str(i) for i in ids}
        return [
            str(e.get("Text"))
            for e in (_vocabulary().get("Sets") or [])
            if str(e.get("Value")) in wanted_ids
        ]

    if chosen is not None:
        # THE OPERATOR NAMING SETS OUTRANKS EVERYTHING, INCLUDING THE UNANIMITY RULE ABOVE.
        # The rule exists because a hint is evidence about one card; a person ticking sets on
        # `#/runs` is making a claim about the BOX, which is the thing the inference was
        # trying to guess. Validated against the portal's own vocabulary rather than passed
        # through, because an id the portal does not know comes back as `System Error` — a
        # 200 carrying an HTML page that reads exactly like a rejected cookie.
        if not isinstance(chosen, list) or not chosen:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "set_ids_invalid",
                "`set_ids` must be a non-empty array of TCGplayer set ids, or absent to let "
                "this run's own claims decide. An empty array is refused rather than read "
                "as every set.",
            )
        wanted_ids: List[int] = []
        for value in chosen:
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise PipelineRefusal(
                    HTTPStatus.BAD_REQUEST,
                    "set_ids_invalid",
                    f"`set_ids` holds {value!r}, which is not a TCGplayer set id. `0` is the "
                    f"portal's all-sets row — send `scope` as `category` for that.",
                )
            wanted_ids.append(value)
        known = {str(e.get("Value")) for e in (_vocabulary().get("Sets") or [])}
        stray = [i for i in wanted_ids if str(i) not in known]
        if stray:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "set_ids_unknown",
                f"TCGplayer's {game} category has no set with id "
                f"{', '.join(str(i) for i in stray)}. The portal answers a body it cannot "
                f"read with its System Error page, which reads like an expired session, so "
                f"this refuses here instead.",
            )
        set_ids = tuple(dict.fromkeys(wanted_ids))
        names = _names(set_ids)
        scope_used, chosen_by, reason = "sets", "operator", None
    elif (wanted or policy) == "category":
        scope_used = "category"
        chosen_by = "operator" if wanted is not None else "policy"
        reason = "operator_asked" if wanted is not None else "game_policy"
    elif not hints:
        scope_used, chosen_by, reason = "category", "cards", "no_hints"
    elif unhinted > 0:
        # THE DEFECT D76 IS NAMED FOR. Some cards carry a hint and some do not, so the hints
        # describe part of the box and the export would be cut to that part. Every unhinted
        # card outside those sets would queue `no_catalog_row` behind a fetch that reported
        # success — which is exactly what the owner hit on a Riftbound box sorted by rarity.
        scope_used, chosen_by, reason = "category", "cards", "partial_hints"
    else:
        set_ids, unresolved = tcg_export.match_sets(
            hints, _vocabulary().get("Sets") or [], entry.get("set_aliases")
        )
        if unresolved:
            scope_used, chosen_by, reason = "category", "cards", "unresolved_hints"
            set_ids = ()
        elif not set_ids:
            scope_used, chosen_by, reason = "category", "cards", "no_hints_resolved"
        else:
            names = _names(set_ids)
            scope_used, chosen_by, reason = "sets", "cards", None

    # THE CLIFF IS MADE UNREACHABLE HERE, AND ONLY FOR A WIDENING THE CARDS CAUSED.
    #
    # `games.export_needs_hint` marks a game whose whole category has been WEIGHED and found
    # too close to the transport's own ceiling to widen into on a guess — Pokemon, measured
    # 2026-09-12 at 97.24% of `MAX_BYTES` with 903 KB of headroom. D76 held that a widening
    # is always safe; for this category it is 903 KB from a refusal, and one unhinted card
    # reaches it, because the unanimity rule widens the moment the box stops agreeing.
    #
    # `chosen_by == "cards"` IS THE WHOLE PREDICATE, and it is exactly right rather than
    # merely convenient. It is set by the four branches above that widen because the CARDS
    # under-specified the scope — `no_hints`, `partial_hints`, `unresolved_hints`,
    # `no_hints_resolved` — and by no other. So D76's other two voices survive untouched: an
    # operator naming `set_ids` or asking for `scope=category` is `operator` and passes
    # straight through, which is both the override and the reason nothing is ever stranded,
    # and a game whose own `export_scope` is `category` is `policy` and never reaches here.
    #
    # AND IT REFUSES IN ONE PLACE FOR TWO BEHAVIOURS. `do_pipeline_export` lets this out as a
    # 409 and spends nothing; `do_pipeline_scope` catches it and DRAWS it, because that route
    # already reads a `PipelineRefusal` as data. So the operator meets this on the
    # press-nothing preview, before the money gate, rather than on the press — which is the
    # posture D76 built that route for.
    if scope_used == "category" and chosen_by == "cards" and (
        game_registry.export_needs_hint(game)
    ):
        # THE DISPLAY NAME AND NOT THE KEY. `pokemon` is a registry key; `Pokémon` is what a
        # person calls the game, and CLAUDE.md's register rule is that an enum value is
        # labelled rather than printed raw. This sentence is rendered verbatim on `#/runs`,
        # so the raw key would be on screen.
        display = str(entry.get("display") or game)
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "export_needs_set_hint",
            f"Every {display} card in a run has to name its set, and "
            f"{_unhinted_said(total, hinted, unresolved, reason, display)}. "
            f"{_widening_said(game, display)} "
            f"Set the hint on the cards that lack one from #/inventory — open the box, "
            f"Manage box, Set claims — or tick the sets on #/runs to ask for them anyway.",
        )

    scope = tcg_export.Scope(category_id=category, set_ids=set_ids)
    asked = {
        "game": game,
        "category_id": category,
        "hints": list(hints),
        "set_ids": list(set_ids),
        "unresolved_hints": list(unresolved),
        "sets": names,
        # KEPT, AND IT IS THE SAME FACT `scope` CARRIES. Every client written against D65
        # reads this boolean; `scope`, `chosen_by` and `reason` are what D76 adds beside it,
        # because "the whole category" was never the interesting half — WHY it went wide is.
        "widened": scope_used == "category",
        "scope": scope_used,
        "policy": policy,
        "chosen_by": chosen_by,
        "reason": reason,
        "cards": total,
        "hinted": hinted,
        "unhinted": unhinted,
    }
    return scope, asked


def do_pipeline_scope(name: str, payload: dict) -> dict:
    """`GET /pipeline/runs/<name>/scope` — what a fetch would ask TCGplayer for, and why.

    FREE, AND IT PRESSES NOTHING. `POST .../export` is what fetches; this answers the
    question that press used to answer only in hindsight — the receipt named the scope AFTER
    the file was on disk, so the one moment an operator could have corrected a wrong scope
    was the one moment they could not see it. D76 makes it a lever, and a lever needs its
    current position drawn.

    IT REFUSES ALMOST NOTHING, WHICH IS THE OPPOSITE POSTURE FROM THE FETCH. A mixed-game run
    is a refusal at `POST` (`game_required`, one category per request) and is simply a LIST
    here, because a screen that must ask which game cannot draw the picker if the route that
    would tell it the games refuses to answer without one.

    AND IT DEGRADES THE WAY `GET /tcg/sets` DOES, for the same reason one step further along:
    resolving a hint to a set id needs the portal, and no cookie, no network or a portal
    outage must not blank a panel whose other half — the counts, the game's rule, the reason
    it would widen — is local and knowable. `asked` is null with `reason` naming the refusal
    code; every count above it still draws.
    """
    directory = _open_run(name)
    _, catalogued = _scope_counts(directory)

    games = [
        {
            "game": key,
            "display": str((game_registry.get(key) or {}).get("display") or key),
            "category_id": int(game_registry.get(key)["tcgplayer_category_id"]),
            "cards": int(held["cards"]),
            "hinted": int(held["hinted"]),
            "unhinted": int(held["cards"]) - int(held["hinted"]),
            "hints": sorted(held["hints"]),
            "policy": game_registry.export_scope(key),
        }
        for key, held in sorted(catalogued.items())
    ]

    asked: Optional[dict] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    if games:
        try:
            _, asked = _scope_for_run(directory, payload)
        except PipelineRefusal as caught:
            # THE REFUSAL IS DATA HERE, NOT A STATUS. `game_required` over a two-game run is
            # the screen's cue to draw a picker, and `set_ids_unknown` over a stale tick is
            # the cue to redraw the list — both are worth saying and neither is worth
            # withholding the counts for.
            reason, message = caught.code, str(caught)
        except tcg_export.FetchRefusal as caught:
            reason, message = caught.code, caught.message

    return {
        "run": directory.name,
        "games": games,
        "scopes": list(game_registry.EXPORT_SCOPES),
        "asked": asked,
        "reason": reason,
        "message": message,
        # WHAT THE PRESS WOULD WEIGH, DRAWN BEFORE IT (D65/D76). Null until this game has been
        # fetched at a covering scope once — an honest "not measured" rather than an estimate,
        # because the only thing that can size an export is an export.
        #
        # IT IS ANSWERABLE ONLY BECAUSE THE EXPORTS ARE PER-GAME NOW. Per-run copies gave every
        # drawer its own unrelated sample and no one of them was the game's, so this figure had
        # nowhere to be read from and the widening was priced at nothing.
        "width": _width_note(str(asked["game"]), asked) if asked else None,
        # AND THE FILE THAT WOULD ANSWER WITHOUT A REQUEST, if there is one. A preview that
        # showed the scope but not whether pressing would even open a socket leaves the
        # operator re-fetching bytes the machine holds, which is the measured defect.
        "reusable": _reuse_note(asked),
    }


def _exports_dir(game: str) -> Path:
    """`inventory/.exports/<game>/`, made on demand.

    THE GAME IS VALIDATED BY ITS REGISTRY MEMBERSHIP AND NEVER BY ITS SHAPE. Every caller
    reaches here through `_scope_for_run`, which answers a key out of `pipeline/games.py`,
    so the segment cannot be built from a request — the same rule `_open_run` follows one
    directory over, and the reason a name is never joined onto a path in this module.
    """
    if game not in set(game_registry.keys()):  # noqa: SIM118 — pipeline.games MODULE
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "unknown_game",
            f"{game!r} is not a registered game, so it has no export directory.",
        )
    return files.inventory_dir() / EXPORTS_DIR / game


def _note_path(export: Path) -> Path:
    """Where an export's own scope note lives: the file's name plus `.scope.json`.

    THE FILE CANNOT SAY WHAT IT WAS ASKED FOR, WHICH IS D65's WHOLE ARGUMENT. Completeness
    is not readable off an export — three filters narrow it and one leaves no trace — so a
    reuse that inferred the scope from the contents would be exactly the inference D65 exists
    to replace. The note records what was ASKED, beside the file that answered.
    """
    return export.with_name(export.name + ".scope.json")


def _read_note(export: Path) -> Optional[dict]:
    """One export's scope note, or None for a file that has none or whose note is unreadable.

    NONE IS "CANNOT BE REUSED", NEVER "REUSE IT ANYWAY". A file with no note is an export
    this build did not fetch — an operator's own drop, or one written before this landed —
    and the safe answer for an unknown scope is to fetch rather than to guess that it covers.
    """
    try:
        note = json.loads(_note_path(export).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return note if isinstance(note, dict) else None


def _write_note(export: Path, asked: dict, size: int) -> None:
    """Record what this file was asked for, beside it. Never fatal.

    A NOTE THAT FAILS TO WRITE COSTS A REUSE AND NOTHING ELSE, which is why it is not allowed
    to take a good fetch down with it: the export is on disk and joinable, and the next press
    simply opens a socket it could have skipped.
    """
    with contextlib.suppress(OSError):
        _note_path(export).write_text(
            json.dumps(
                {
                    "game": asked["game"],
                    "category_id": int(asked["category_id"]),
                    "set_ids": [int(i) for i in asked["set_ids"]],
                    "scope": asked["scope"],
                    "widened": bool(asked["widened"]),
                    "bytes": int(size),
                    "at": master.now(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _covers(note: dict, scope: "tcg_export.Scope") -> bool:
    """Does the file this note describes answer for `scope`?

    ONE DIRECTION ONLY, AND THE ASYMMETRY IS THE POINT. A file fetched for the whole category
    covers every set in it; a file fetched for {A} does NOT cover {A, B}, and the missing set
    would queue as `no_catalog_row` for every card in it — the defect D76 is named for,
    arriving by a different door. So a wider file serves a narrower need and never the
    reverse, and `set_ids` empty means "all of them" exactly as `Scope` encodes it.
    """
    if int(note.get("category_id") or 0) != int(scope.category_id):
        return False
    held = {int(i) for i in (note.get("set_ids") or [])}
    if not held:
        return True
    return bool(scope.set_ids) and {int(i) for i in scope.set_ids} <= held


def _held_exports(game: str) -> List[Path]:
    """Every export this game holds, newest reading first.

    ORDERED BY MTIME BECAUSE THE MTIME IS THE READING'S OWN TIME (`cli/runs.py`
    `describe_source`), not by the stamp in the name: a dedupe hit touches the file, so the
    name says when the bytes were first seen and the mtime says when they were last observed,
    and the fresher OBSERVATION is the one a reuse is entitled to.
    """
    directory = _exports_dir(game)
    if not directory.is_dir():
        return []
    return sorted(
        (p for p in directory.glob(f"{FETCHED_PREFIX}*.csv") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _reusable(game: str, scope: "tcg_export.Scope") -> Optional[Tuple[Path, float]]:
    """The export that answers this scope without a request, with its age in seconds.

    THIS IS THE HALF THAT SAVES THE REQUEST, and it is the only part of this route whose
    saving an outcome assertion cannot see: a reuse and a fetch produce the same file, the
    same receipt figures and the same join. `harness/tests/t7_store_and_seams.py` counts the
    stub's requests for exactly that reason.
    """
    for path in _held_exports(game):
        note = _read_note(path)
        if note is None or not _covers(note, scope):
            continue
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            continue
        if 0 <= age <= EXPORT_REUSE_S:
            return path, age
    return None


def _keep_export(store_dir: Path, body: bytes) -> Tuple[Path, bool, float]:
    """Keep these bytes in the game's own directory, or answer with the copy already there.

    THE NAME CARRIES A DIGEST, AND A ONE-SECOND STAMP ALONE WAS A DATA-LOSS BUG. T7 found it:
    two fetches inside the same second composed the same filename, so the second one OVERWROTE
    the first — and the first is what a run was joined against. A file silently replaced by
    the very thing being checked against it passes every check by comparing itself to itself.
    T7's same-second case is the record of that.

    THE SEARCH IS THE GAME'S WHOLE DIRECTORY, WHICH IS THE CHANGE. It used to be the RUN's own
    directory, so bytes already on disk one directory over were invisible: measured on the
    owner's store 2026-09-12, 19 exports holding 13 distinct files, 9.0 MB in 6 redundant
    copies — and 5 of those 6 were CROSS-RUN and outside anything a per-run glob can reach.
    Five byte-identical 1,733,052 B copies landed in eighteen seconds across five run
    directories, each one a fetch that reported success and wrote a file that already existed.

    THE DIGEST IS COMPUTED FIRST AND THE BYTES ARE COMPARED IN FULL — 32 bits of digest is a
    name, not a proof. A hit IS the file: an identical re-fetch is a fresh observation of the
    same reading, so its mtime is touched, because the export's observation time is read off
    that mtime. A miss gets a stamped name of its own and can never clobber a predecessor.

    THE STAMP GOES ON THE MISS AND THE AGE COMES BACK ZERO EITHER WAY, because both arms here
    OBSERVED these bytes just now; `_reusable` is the arm that did not, and it reports a real
    age. Two presses racing one game can still each write a stamped name for the same digest —
    bounded, benign (the byte compare means neither is wrong) and not worth a lock on a
    directory that is deliberately outside the store transaction.
    """
    digest = hashlib.sha256(body).hexdigest()[:8]
    held = [
        path
        for path in sorted(store_dir.glob(f"{FETCHED_PREFIX}*-{digest}.csv"))
        if path.read_bytes() == body
    ]
    # WHETHER THIS REQUEST CREATED IT DECIDES WHETHER A REFUSAL MAY DELETE IT, AND THE STAKES
    # WENT UP WITH THE MOVE. "A refusal tears down what it built" is the rule, and the emphasis
    # is on BUILT: this file is now SHARED, so unlinking one another run's manifest names would
    # destroy a recorded export over a refusal that fired on something else. `fresh` is false
    # for every hit by construction — bytes nothing on disk carries cannot be in a manifest —
    # so the rule holds without the refusal having to know who else is reading.
    if held:
        target = held[0]
        os.utime(target, None)
        return target, False, 0.0
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    target = store_dir / f"{FETCHED_PREFIX}{stamp}-{digest}.csv"
    target.write_bytes(body)
    return target, True, 0.0


def _width_note(game: str, asked: Optional[dict]) -> Optional[dict]:
    """What a fetch at this scope is known to weigh, against the cap — or None if unmeasured.

    PRESS-NOTHING, AND IT IS READ OFF FILES THIS CHECKOUT ALREADY HOLDS. The store-wide
    export directory is what makes this answerable at all: per-run copies gave every drawer
    its own unrelated sample, and no one of them was the game's.

    WHY IT EXISTS (D65/D76). `tcg_export.MAX_BYTES` is 32 MB and the fetch refuses past it.
    A widening to the whole category is the only scope that approaches it, and MEASURED
    2026-09-12 the whole Pokemon category is 32,629,598 B — 97.24% of the cap, 903 KB of
    headroom — against 238,482 B for the one set the owner's 543 Pokemon cards name. So the
    widening is not a detail of how the request is spelt: it is a 137x change in what comes
    back, two per cent short of a refusal. `GET /pipeline/runs/<name>/scope` draws this
    BEFORE the press, which is the whole reason that route is a preview.
    """
    if not asked:
        return None
    try:
        held = _held_exports(game)
    except PipelineRefusal:
        return None
    scope = tcg_export.Scope(
        category_id=int(asked["category_id"]),
        set_ids=tuple(int(i) for i in asked["set_ids"]),
    )
    for path in held:
        note = _read_note(path)
        if note is None or not _covers(note, scope):
            continue
        size = int(note.get("bytes") or 0)
        if size <= 0:
            continue
        return {
            "bytes": size,
            "max_bytes": int(tcg_export.MAX_BYTES),
            "headroom": int(tcg_export.MAX_BYTES) - size,
            "of_max": round(size / float(tcg_export.MAX_BYTES), 4),
            "near_cap": size >= EXPORT_NEAR_CAP * tcg_export.MAX_BYTES,
            "measured": note.get("at"),
            "from": path.name,
            # WHETHER THIS FIGURE IS THE WIDE ONE. A narrow reading beside a `widened: true`
            # scope is a measurement of a DIFFERENT request, and saying so is the difference
            # between a preview and a reassurance.
            "widened": bool(note.get("widened")),
        }
    return None


def _reuse_note(asked: Optional[dict]) -> Optional[dict]:
    """The file a press would answer from without a request, or None. PRESSES NOTHING."""
    if not asked:
        return None
    scope = tcg_export.Scope(
        category_id=int(asked["category_id"]),
        set_ids=tuple(int(i) for i in asked["set_ids"]),
    )
    try:
        held = _reusable(str(asked["game"]), scope)
    except PipelineRefusal:
        return None
    if held is None:
        return None
    path, age = held
    return {"file": path.name, "age_s": int(age), "window_s": EXPORT_REUSE_S}


def _unhinted_said(
    total: int,
    hinted: int,
    unresolved: Sequence[str],
    reason: Optional[str],
    display: str,
) -> str:
    """Which cards under-specified the scope, in the shape the refusal above needs.

    FOUR REASONS WIDEN AND THEY ARE NOT ONE SENTENCE. "No card carries a hint" and "3 of 200
    do not" are different instructions — the first says start hinting, the second says find
    the gap — and an unresolvable hint is a THIRD thing, where the operator did the work and
    the string missed. Saying "some cards carry no set hint" over a box whose every card is
    hinted and whose hint is a typo sends somebody to look for cards that are all there.
    """
    unhinted = total - hinted
    if reason == "unresolved_hints":
        named = ", ".join(f"`{h}`" for h in unresolved)
        return (
            f"{named} names no {display} set TCGplayer knows, so the {total} cards carrying "
            f"it cannot be narrowed to one"
        )
    if reason == "no_hints_resolved":
        return f"none of this run's hints resolved to a set, so all {total} cards widen it"
    if reason == "no_hints":
        return f"none of its {total} cards carries one"
    return f"{unhinted} of its {total} do not"


def _widening_said(game: str, display: str) -> str:
    """What the widening this refusal prevented would have weighed, or silence.

    THE FIGURE COMES OFF THE REGISTRY AND NOT OFF A HELD FILE, WHICH IS THE WHOLE REASON
    `export_category_bytes` IS A FIELD. `_width_note` can only answer from an export this
    checkout has already fetched at a covering scope — and this refusal exists to stop that
    fetch, so on any machine that has obeyed it there is no such file and the figure would be
    null exactly when it is needed. A refusal whose number is missing in the common case is a
    refusal nobody can weigh.

    AND IT SAYS NOTHING RATHER THAN GUESSING. A game marked `export_needs_hint` without a
    measurement cannot exist — the audit row refuses it — but this is the sentence that would
    have to be honest if it did.
    """
    measured = game_registry.export_category_bytes(game)
    if measured is None:
        return (
            f"Without one the export asks TCGplayer for the whole {display} category, which "
            f"this game is marked as unable to afford."
        )
    cap = int(tcg_export.MAX_BYTES)
    return (
        f"Without one the export asks for the whole {display} category — about "
        f"{measured / 1_000_000:.1f} MB, {measured / float(cap) * 100:.0f}% of the "
        f"{cap // (1024 * 1024)} MB this download is refused past."
    )


def _too_large_sentence(asked: Optional[dict]) -> str:
    """What to add to `tcg_export_too_large` when the scope is what made it large (D65/D76).

    THE TRANSPORT'S OWN SENTENCE BLAMES THE DOWNLOAD AND HANDS THE OPERATOR NOTHING. It says
    the widest export this project has read is under 2 MB — measured 2026-09-12, the widest
    it can ask for is 31.12 MB and the owner's own catalogue is one of the two that can. The
    actionable half is never "the file was big": it is that the scope went wide, and why, and
    that hinting the cards or naming the sets is what narrows it.
    """
    if not asked or not asked.get("widened"):
        return ""
    unhinted = int(asked.get("unhinted") or 0)
    cards = int(asked.get("cards") or 0)
    why = {
        "no_hints": f"none of this run's {cards} {asked['game']} cards carries a set hint",
        "partial_hints": (
            f"{unhinted} of this run's {cards} {asked['game']} cards carry no set hint, so "
            f"the hints describe part of it and cutting the export to them would queue every "
            f"other card as no_catalog_row (D76)"
        ),
        "unresolved_hints": "this run's set hints match no set TCGplayer knows",
        "no_hints_resolved": "this run's set hints resolved to no set",
        "game_policy": f"{asked['game']}'s export_scope is `category` in pipeline/games.py",
        "operator_asked": "the scope was asked for as `category`",
    }.get(str(asked.get("reason") or ""), "the scope widened to the whole category")
    return (
        f" THE SCOPE IS WHY: this asked TCGplayer for the whole {asked['game']} category "
        f"because {why}. Hint the cards, or name the sets on #/runs — "
        f"GET /pipeline/runs/<name>/scope draws what would be asked for and presses nothing."
    )


def do_pipeline_export(name: str, payload: dict) -> dict:
    """`POST /pipeline/runs/<name>/export` — fetch this run's export from TCGplayer.

    FREE, AND IT IS NOT THE ROUTE THAT SPENDS. The Filtered Export is a download of the
    operator's own Pricing tab; nothing here starts a child and nothing here can put a number
    on an invoice. What it DOES do that no other route in this server has ever done is read a
    secret and open a socket, which is why the call lives in `server/tcg_export.py` behind one
    function and why `capture_server.py`'s file-boundary sentence is rewritten rather than
    qualified.

    THE ORDER IS FETCH, THEN RULE, THEN KEEP. `cli/resolve.py:exports_for` is what decides
    whether a file may be joined — it is run here, over the fetched file plus whichever of the
    run's recorded exports it does not replace, BEFORE anything is joined, which is that
    function's own stated contract. So the check is the real rule rather than a second
    approximation of it, and a fetched file that would refuse at join time refuses here where
    the fault is attributable to the fetch. The receipt then reports the last export this run
    was joined against beside this one, per game, and refuses nothing on that comparison —
    D65 names the scope, so what the file is checked for is what was asked, and a run's first
    fetch has nothing earlier to be compared with by construction (D64, amended 2026-09-02).

    A REFUSAL TEARS DOWN WHAT IT BUILT. The bytes are written first because
    `exports_for` reads files rather than buffers, and every refusal path unlinks them again —
    the rule D48 states for a cart's scope directories, for the same reason: a run directory
    accumulating one dead export per mis-timed press is a run that stops explaining itself.
    """
    directory = _open_run(name)

    # THE SCOPE IS DECIDED IN ITS OWN TRY, AHEAD OF THE FETCH, so that a refusal raised by the
    # FETCH can be told apart from one raised while deciding what to ask for — and so
    # `_too_large_sentence` below has an `asked` to read. These two shared a `try` and a
    # handler, which left `asked` unbound on exactly the path that most needs it.
    try:
        scope, asked = _scope_for_run(directory, payload)
    except tcg_export.FetchRefusal as caught:
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY, caught.code, caught.message
        ) from None

    game = str(asked["game"])
    store_dir = _exports_dir(game)
    store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------ THE REQUEST THAT IS NOT SENT
    #
    # A PRESS WHOSE GAME ALREADY HOLDS A COVERING, RECENT EXPORT OPENS NO SOCKET. This is the
    # saving, and it is the one thing about this route that no assertion over its OUTPUT can
    # see: a reuse and a fetch answer with the same file, the same figures and the same join.
    # The measurement it is built for is on the owner's store — seven presses over nine
    # minutes re-joining one store, five of them eighteen seconds apart, every one of them
    # asking TCGplayer for bytes the machine already had.
    #
    # `refresh: true` FORCES THE SOCKET OPEN, and the receipt says `reused` with the file's
    # age either way. An operator who means to take a new reading must be able to, and one
    # who did not mean to must be able to see that they did not.
    reused = None if payload.get("refresh") else _reusable(game, scope)
    if reused is not None:
        target, age = reused
        body = target.read_bytes()
        fresh = False
        # THE MTIME IS NOT TOUCHED HERE, AND THAT IS THE DIFFERENCE BETWEEN THIS ARM AND THE
        # DEDUPE ARM BELOW. `describe_source` reads an export's OBSERVATION TIME off its
        # mtime, and `Listing.live_reading` weighs that against the store's own stamps. A
        # re-fetch of identical bytes really is a fresh observation and is touched; a reuse
        # observed nothing, and touching it would date a reading that was never taken —
        # letting a stale export outrank a newer sale.
    else:
        try:
            body = tcg_export.fetch(scope)
        except tcg_export.FetchRefusal as caught:
            # A BAD GATEWAY AND NOT A 500. The failure is at TCGplayer or in the credential
            # this machine holds for it, and every one of these carries a sentence saying
            # which — plus, for the one refusal a SCOPE can cause, what made it wide.
            message = caught.message
            if caught.code == "tcg_export_too_large":
                message += _too_large_sentence(asked)
            raise PipelineRefusal(
                HTTPStatus.BAD_GATEWAY, caught.code, message
            ) from None
        target, fresh, age = _keep_export(store_dir, body)

    def refuse(status, code, message):
        if fresh:
            target.unlink(missing_ok=True)
            _note_path(target).unlink(missing_ok=True)
        return PipelineRefusal(status, code, message)

    try:
        fetched_export = tcgcsv.read_export(target)
        claimed = run_resolve.games_claimed(fetched_export)
    except Exception as caught:  # noqa: BLE001 — a file we cannot parse is the refusal
        raise refuse(
            HTTPStatus.BAD_GATEWAY,
            "tcg_not_csv",
            f"What TCGplayer sent does not parse as an export: {caught}. Nothing was kept.",
        ) from None

    # THE MANIFEST IS READ AFTER THE FETCH, NOT BEFORE IT. The download can take a minute, and
    # what it is about to be compared against is whatever this run was last joined with — so
    # reading the baseline first would compare against a manifest that a join finishing in
    # that window has already replaced. `cli/runs.py` makes a run an immutable input and its
    # MANIFEST is the one part that moves, which is exactly why it is read as late as it can
    # be used.
    run = run_files.open_run(directory)

    # The run's recorded exports for every OTHER game, so a mixed-game run can refresh one
    # game's file without being told it has lost the other. A baseline for a game this file
    # also claims is deliberately NOT passed on: `exports_for` refuses two files claiming one
    # game, and refusing the replacement of a file by its own successor would be that rule
    # firing on the one case it is not about.
    baselines = {
        game: path
        for game, path in run.exports_by_game.items()
        if game not in claimed and Path(path).is_file()
    }
    try:
        plan = run_resolve.exports_for(run, [str(target)] + [str(p) for p in baselines.values()])
    except run_files.RunError as caught:
        raise refuse(
            HTTPStatus.CONFLICT,
            "export_refused",
            f"{caught}",
        ) from None

    answers_for = [game for game in plan.by_game if plan.by_game[game] == target]
    if not answers_for:
        # NOT THE PRICING TAB. Since D65 `_scope_for_run` names `CategoryId` from the run's
        # own game, so the portal's saved filter is not consulted and cannot be what is
        # wrong. What is left is a wrong `tcgplayer_category_id` in `pipeline/games.py`,
        # `PKMNSCAN_TCG_EXPORT_URL` pointing at the old unscoped endpoint, or TCGplayer
        # renumbering a category — and the sentence names all three, with the product lines
        # the file actually carries, because `claimed` is empty whenever none is registered.
        lines = ", ".join(tcgcsv.product_lines(fetched_export)) or "no product line at all"
        raise refuse(
            HTTPStatus.CONFLICT,
            "export_wrong_game",
            f"Asked TCGplayer for category {asked['category_id']} ({asked['game']}) and the "
            f"file that came back carries {lines}; this run holds no card of a game that "
            f"claims it. The category is `tcgplayer_category_id` for {asked['game']} in "
            f"pipeline/games.py and the request went to {tcg_export.endpoint()} — one of "
            f"those is wrong, or TCGplayer renumbered. Nothing was kept.",
        )

    # ---------------------------------------------- THE POSITIVE CHECK (D65)
    #
    # ASKED-FOR RATHER THAN INFERRED, WHICH IS THE WHOLE POINT OF SCOPING THE REQUEST. The
    # scope was NAMED by this process — the category, the sets, all printings, every
    # condition — so the file can be checked for what was asked rather than read for what
    # somebody else's filter might have left out: the question is "did I get what I asked
    # for", which the file can answer.
    #
    # It refuses rather than warns because a set that was asked for and did not arrive means
    # the cards in it will queue as `no_catalog_row` — a whole box's worth, silently, from a
    # fetch that reported success.
    if asked["sets"]:
        arrived = {str(row.get(tcgcsv.SET_COLUMN) or "") for row in fetched_export.rows}
        absent = [name for name in asked["sets"] if name not in arrived]
        if absent:
            raise refuse(
                HTTPStatus.CONFLICT,
                "export_scope_incomplete",
                f"This export was asked for {', '.join(asked['sets'])} and came back without "
                f"{', '.join(absent)}. Every card of a missing set would queue as "
                f"no_catalog_row. Nothing was kept.",
            )

    # ------------------------------------ WHAT THE LAST JOIN USED, BESIDE WHAT ARRIVED
    #
    # INFORMATION, AND NEVER A REFUSAL. D64's delta guard compared this file against the
    # export the run was last joined with and refused a narrower one; it was retired
    # 2026-09-02 (D64, amended) because D65 names the scope — so the check above is the
    # whole guard — and because a run's FIRST fetch has nothing to compare with by
    # construction, which made every run cost an acknowledgement. The figures stay on the
    # receipt so that a narrower file is visible to the operator who asked for it. Read off
    # `run.exports_by_game` directly: `baselines` above deliberately EXCLUDES the games this
    # file claims. A previous file that no longer parses is OMITTED rather than raised — a
    # 500 is the one answer this route may not give, and that file's state is not this
    # fetch's fault.
    previous: Dict[str, dict] = {}
    for game in answers_for:
        prev = run.exports_by_game.get(game)
        if prev is None or not Path(prev).is_file():
            continue
        try:
            was = _export_report(Path(prev), [game])
        except Exception:  # noqa: BLE001 — omit the game rather than fail the fetch
            continue
        previous[game] = {"file": was["file"], "rows": was["rows"], "skus": was["skus"]}

    # THE NOTE IS WRITTEN LAST, AFTER EVERY REFUSAL THIS ROUTE CAN RAISE. It is what makes the
    # file reusable without a request, so writing it before the file has been ruled on would
    # let the NEXT press answer out of an export this one was about to tear down.
    if fresh:
        _write_note(target, asked, len(body))

    report = _export_report(target, answers_for)
    report.update(
        {
            "ok": True,
            "run": directory.name,
            # ALWAYS PRESENT, POSSIBLY EMPTY: a run with no earlier export reports none,
            # which is a fact about the run and not a fault in the fetch.
            "previous": previous,
            "source": tcg_export.endpoint(),
            # WHAT WAS ASKED FOR, beside what arrived. A receipt that showed only the result
            # cannot be read for whether the scope was right — and the scope is the operator's
            # own capture claims, so it is the half they can correct.
            "asked": asked,
            # WHETHER A SOCKET WAS OPENED, AND THIS IS THE ONE FIGURE THE REST OF THE RECEIPT
            # CANNOT IMPLY. A reuse and a fetch produce the same file, the same rows, the same
            # SKUs and the same join; the only difference is the work done to get there, so it
            # is said rather than left to be inferred. `age_s` is how old the reading is —
            # zero for anything observed by this press.
            "reused": reused is not None,
            "age_s": int(age),
            "kept": True,
            # WHERE THE FILE IS, WHICH IS NO LONGER INSIDE THE RUN (D166). A
            # client that built a download path out of the run's name would break silently;
            # this says the directory the game's exports live in.
            "store": str(store_dir),
            # WHAT THIS SCOPE WEIGHS AGAINST THE CAP (D65/D76). Measured, not estimated — it
            # is the file that just landed.
            "width": _width_note(game, asked),
        }
    )
    return report


def do_pipeline_step(name: str, step: str, payload: dict) -> dict:
    """`POST /pipeline/runs/<name>/<join|emit|reconcile>` — a free step, run in the request.

    Free and fast, so it answers with its own stdout rather than a summary of it. That is
    the same choice `docs/DESIGN.md`'s copy rule makes for owner screens — the pipeline's
    reason codes are shown verbatim because being able to grep what you saw is worth more
    than a consistent register — applied to a whole command's output.

    A NON-ZERO EXIT IS A 200 WITH `ok: false`. `emit` refusing while a price is unanswered
    is the most useful thing that command does, and turning it into an HTTP error would put
    a stack trace where the operator needs the sentence naming the SKU.
    """
    directory = _open_run(name)
    if step not in FREE_STEPS:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_such_step",
            f"{step!r} is not a step. The free ones are {', '.join(FREE_STEPS)}; identify "
            f"is POST /pipeline/identify because it spends money.",
        )

    argv = [str(PKMNSCAN), step, str(directory)]
    if step == "join":
        argv += _exports_for_join(directory, payload)
        argv += _pricing_flags(payload)
        if payload.get("dry_run"):
            argv.append("--dry-run")
    elif step == "emit":
        argv += _exports_for_join(directory, payload)
        argv += _pricing_flags(payload)
        # THE SAME THREE SHAPE FLAGS `POST /pipeline/emit` TAKES. One run and several are the
        # same command, and a screen that could ask for a split on a send of three and not on
        # a send of one would be answering a question about how many runs are open.
        if payload.get("listed_only"):
            argv.append("--listed-only")
        if payload.get("split_games"):
            argv.append("--split-games")
        if payload.get("split_threshold"):
            argv.append("--split-threshold")
        # AND THE CAP, FOR THE PARAGRAPH ABOVE'S OWN REASON (D7, rewritten). A cap offered on a
        # send of three and withheld from a send of one would be exactly the question that
        # comment refuses to answer.
        argv += _cap_flag(payload)
        # AND THE PER-CARD QUANTITIES, for the same reason (D7, amended 2026-09-11).
        argv += _quantity_flags(payload)
    else:  # reconcile
        staged = payload.get("staged_export")
        if not isinstance(staged, dict):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "staged_export_required",
                "Send `staged_export` as {name, content} — TCGplayer's Export From Staged "
                "download. Reconcile compares what it staged against what emit wrote.",
            )
        argv.append(str(_store_upload(directory, staged, "staged-")))

    code, text = _run_sync(argv, STEP_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "step": step,
        "run": directory.name,
        "console": text,
        "dry_run": bool(payload.get("dry_run")) and step == "join",
        "files": _artifacts(directory),
        "summary": _summary(directory),
    }

