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
(`server/tcg_export.py`) and is short: one host, one method, one route, and it cannot cause a
charge. The route that can is still `POST /pipeline/identify` and is still named for it.

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
rather than state; this file leans on that entirely and holds nothing between requests.

STDLIB ONLY, like the rest of the server. `make server` runs `python3` and not the venv
(the Makefile says so and gives the reason), so this module may not import anything that
needs `make venv`. It shells out to `./pkmnscan`, which picks the venv itself with the same
rule the Makefile uses — one rule about which Python runs, stated in places that agree.
`cli.runs` is imported for its names, and is stdlib-only itself.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cli import resolve as run_resolve  # noqa: E402
from cli import runs as run_files  # noqa: E402
from pipeline import corpus, decisions, games as game_registry, join, tcgcsv  # noqa: E402
from server import tcg_export  # noqa: E402
# STDLIB-ONLY AT MODULE SCOPE, LIKE EVERY OTHER IMPORT HERE. `pipeline/pricehistory.py`
# reaches `json`, `time`, `urllib`, `dataclasses`, `datetime`, `decimal` and `pathlib`
# and nothing else — verified under bare `/usr/bin/python3`, which is what the Makefile
# falls back to when there is no venv. It is a top-level import rather than one inside
# the handler for exactly that reason: D32 puts the imports inside `crop-preview`
# because Pillow may genuinely be absent, and there is no equivalent risk here.
from pipeline import pricehistory  # noqa: E402
from store import Store, files, master  # noqa: E402

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

# HOW MANY BOXES ONE SEND MAY CARRY. A cart of boxes spawns one detached child per box, so an
# unbounded list is an unbounded number of processes started by one request — the bound is
# what stops a malformed or looping client doing that, and it is not a judgement about how
# many boxes an operator may reasonably send. Sixteen is comfortably more than the thirteen
# this store has ever held.
MAX_LEGS = 16

# How many preflights run at once. They are separate read-only processes doing CPU-bound
# image decodes, so they parallelise cleanly and oversubscribing does not: four legs on four
# threads finish in about the time one takes, and sixteen on sixteen finish in about the time
# four take while making the machine unusable. Bounded rather than unbounded for the same
# reason `MAX_LEGS` exists one constant up.
PREFLIGHT_WORKERS = 4

# Downloadable run artefacts are matched by SHAPE, never by a name from the request. The
# request names a file, this decides whether that name is one this route is willing to
# serve, and nothing built from user input is ever joined onto a path.
_DOWNLOADABLE = re.compile(r"^[A-Za-z0-9._-]+\.(csv|txt|json|log)$")

# What a fetched export is called inside a run directory. It keeps the `export-` prefix every
# uploaded one has, so the run's artefact list reads the same either way, and adds a segment
# that says WHERE it came from — which is the one fact a file dropped into a run directory
# cannot otherwise carry, and the one a later reader of `runs/` will want.
FETCHED_PREFIX = "export-tcgplayer-"

# The box a capture directory names, anchored at the start so `box3` and `box3-12-1724936400`
# both read as 3 and nothing further down a name can be mistaken for one. Used only by
# `_run_box`, and only for runs whose manifest carries no scope — which is every run started
# from a terminal.
_BOX_IN_PATH = re.compile(r"^box(\d+)", re.IGNORECASE)

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
    return files.home() / "captures" / "cards" / f"box{int(box)}"


def _scopes_root() -> Path:
    """Scope directories live OUTSIDE `captures/cards/`, and that is load-bearing.

    `identify.sidecar.scan` walks its root recursively and turns every photo-suffixed file
    into a capture and therefore a paid Batch request. A scope directory of symlinks placed
    under `captures/cards/` would be walked by any run pointed at the box above it, and
    every card in it would be submitted twice.
    """
    return files.home() / ".scopes"


def _scope_dir(box: int, indices: Sequence[int]) -> Path:
    """A directory of symlinks to the chosen cards, so `identify` can be pointed at a subset.

    `identify` takes a DIRECTORY — that is its contract and widening it to take a list of
    files would put a second input shape through `sidecar.scan`, which is the one function
    that decides what a capture is. Symlinks keep the photograph and its sidecar side by
    side under their real names, which is all `scan` reads, and cost nothing on disk.

    Rebuilt from scratch each time rather than reused: the scope is derived from a selection
    the operator just made, and a stale link to a card since deleted would submit a
    photograph the store no longer knows about.
    """
    root = _scopes_root()
    token = f"box{int(box)}-{len(indices)}-{int(time.time())}"
    scope = root / token
    if scope.exists():
        shutil.rmtree(scope)
    scope.mkdir(parents=True)
    source = box_capture_dir(box)
    linked = 0
    for index in indices:
        photo = source / f"{int(index):04d}.jpg"
        sidecar = photo.with_suffix(".json")
        if not photo.is_file():
            continue
        os.symlink(photo, scope / photo.name)
        if sidecar.is_file():
            os.symlink(sidecar, scope / sidecar.name)
        linked += 1
    if not linked:
        shutil.rmtree(scope, ignore_errors=True)
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "no_photos_in_scope",
            f"None of the {len(indices)} selected card(s) in box {box} has a photograph on "
            f"disk. Nothing to identify.",
        )
    return scope


def _sweep_scopes(keep_hours: int = 48) -> None:
    """Old scope directories are symlinks and are safe to drop. Best effort, never fatal."""
    root = _scopes_root()
    if not root.is_dir():
        return
    cutoff = time.time() - keep_hours * 3600
    for entry in root.iterdir():
        try:
            if entry.is_dir() and entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


def _resolve_scope(payload: dict) -> Tuple[Path, dict]:
    """`{box}` or `{box, indices}` -> the directory to identify, and what it describes.

    Whole-box is the common case and takes no temporary anything: the box's own capture
    directory IS the scope, which is exactly what an agent typing the command would have
    pointed at.
    """
    box = payload.get("box")
    if not isinstance(box, int) or isinstance(box, bool) or box <= 0:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "box_required",
            "Send a positive integer `box`. A run is always scoped to one box.",
        )
    source = box_capture_dir(box)
    if not source.is_dir():
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "box_has_no_captures",
            f"Box {box} has no capture directory at {source}. Nothing has been "
            f"photographed into it.",
        )

    raw = payload.get("indices")
    if raw is None:
        return source, {"box": box, "whole_box": True, "cards": None}
    if not isinstance(raw, list) or not raw:
        # The same refusal `PUT /inventory/<box>` makes about an empty selection, for the
        # same reason: an empty array quietly meaning "the whole box" is how a selection
        # that failed to send becomes a run over 544 cards.
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "indices_invalid",
            "`indices` must be a non-empty array of card indices, or absent for the whole "
            "box. An empty array is refused rather than read as the whole box.",
        )
    indices: List[int] = []
    for value in raw:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "indices_invalid",
                f"`indices` holds {value!r}, which is not a positive card index.",
            )
        indices.append(value)
    indices = sorted(set(indices))
    _sweep_scopes()
    return _scope_dir(box, indices), {
        "box": box,
        "whole_box": False,
        "cards": len(indices),
    }


@dataclass(frozen=True)
class Leg:
    """One box in a send: where its photographs are, what it describes, and how it is read.

    THE READING IS PER LEG, AND THAT IS THE WHOLE REASON A CART EXISTS RATHER THAN A
    MULTI-BOX RUN. D32's frontier is a cost-against-sharpness trade measured on real frames,
    and which end of it is right depends on what is IN the drawer: a box of bulk commons
    wants `Cheapest / 900`, and a box worth reading a collector number off wants
    `Measured best / 1200`. One reading stretched across a whole send would make the cart a
    convenience bought with accuracy, which is the trade this repo does not make.

    EVERY LEG IS STILL ONE RUN OVER ONE BOX. Nothing downstream learns a new shape: a run
    directory, its manifest scope, `join`, `emit`, `reconcile` and the queue it writes are
    all exactly what they were. What is new is that one press can start several, which is a
    fact about the REQUEST and not about a run.
    """

    directory: Path
    scope: dict
    flags: List[str]
    label: str


def _one_leg(entry: dict) -> Leg:
    """One entry of a cart, or a whole payload read as a cart of one."""
    directory, scope = _resolve_scope(entry)
    label = entry.get("label")
    if not isinstance(label, str) or not label.strip():
        label = f"box{scope['box']}"
    return Leg(directory, scope, _identify_flags(entry), label.strip())


def _resolve_legs(payload: dict) -> List[Leg]:
    """`{box, ...}` or `{scopes: [{box, ...}, ...]}` -> the boxes this request is about.

    A BARE `box` READS AS A ONE-ELEMENT CART, AND NOTHING EVER WRITES ONE. The same read-side
    widening D3's amendment gives the finish claim and D21 gives `game`, chosen here for the
    same reason: every request written before the cart existed — the harness's, a terminal's,
    and this screen's own single-box send — resolves down the identical path, with no
    migration and no second spelling on the wire for one idea.

    EVERY LEG IS RESOLVED BEFORE ANY IS ACTED ON. `do_pipeline_identify` spawns a detached
    child per leg, and a loop that validated as it went would leave two boxes identifying and
    a third refused — a partial send nobody asked for, with an invoice attached. This is
    D29's validate-everything-then-write-everything, one register up from a queue answer.

    A REFUSAL TEARS DOWN THE SCOPE DIRECTORIES IT BUILT ON THE WAY. `_resolve_scope` creates
    one per ticked selection, so a cart refused on its fourth leg would otherwise leave three
    behind — and T7 asserts, in as many words, that no scope directory survives a refusal.
    """
    made: List[Path] = []
    scopes_root = _scopes_root()

    def _built(leg: Leg) -> Leg:
        if scopes_root in leg.directory.parents:
            made.append(leg.directory)
        return leg

    try:
        raw = payload.get("scopes")
        if raw is None:
            return [_built(_one_leg(payload))]
        if not isinstance(raw, list) or not raw:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "scopes_invalid",
                "`scopes` must be a non-empty array of {box, indices?, crop?, max_edge?}, "
                "or absent to send the one box named at the top level. An empty array is "
                "refused rather than read as every box.",
            )
        if len(raw) > MAX_LEGS:
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "too_many_scopes",
                f"{len(raw)} boxes in one send, and the limit is {MAX_LEGS}. Each box "
                f"spawns its own detached child, so an unbounded list is an unbounded "
                f"number of processes started by one request.",
            )
        legs: List[Leg] = []
        seen: Dict[int, int] = {}
        for position, entry in enumerate(raw, start=1):
            if not isinstance(entry, dict):
                raise PipelineRefusal(
                    HTTPStatus.BAD_REQUEST,
                    "scopes_invalid",
                    f"Scope {position} is not an object.",
                )
            leg = _built(_one_leg(entry))
            first = seen.get(leg.scope["box"])
            if first is not None:
                raise PipelineRefusal(
                    HTTPStatus.BAD_REQUEST,
                    "box_repeated",
                    f"Box {leg.scope['box']} is in this send twice, as scopes {first} and "
                    f"{position}. Two legs over one box is two invoices for one answer — "
                    f"the same refusal a live run earns, made before anything is spawned.",
                )
            seen[leg.scope["box"]] = position
            legs.append(leg)
        return legs
    except PipelineRefusal:
        for path in made:
            shutil.rmtree(path, ignore_errors=True)
        raise


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


def _live_pid(run_dir: Path) -> Optional[int]:
    """The pid of a child still driving this run, or None.

    Checked with signal 0 rather than trusted from the file, because the file outlives the
    process it names — a Mac that slept through a batch leaves a pid that belongs to nobody,
    or worse to something else entirely. A stale marker that blocked every later run would
    make the double-click guard below into a permanent lock.
    """
    marker = run_dir / PID_FILE
    try:
        pid = int(marker.read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return None
    return pid


def _run_box(manifest: dict) -> Optional[int]:
    """Which box a run is reading, from its own manifest.

    THE SCOPE FIRST AND THE PATH SECOND, AND THE SECOND HALF IS NOT A FALLBACK FOR OLD
    FILES — it is the only thing that can see a run started in a TERMINAL. `scope` is
    written by this module and by nothing else, so `pkmnscan identify captures/cards/box3`
    leaves a manifest carrying a capture directory and no scope at all. A guard reading only
    the scope would let this screen start a second batch over a box an agent was already
    identifying, which is precisely the invoice the guard exists to prevent.

    The path form covers both directory shapes because both name their box in the same
    place: `captures/cards/box3` and `.scopes/box3-12-1724936400` are `box3...` either way.
    """
    scope = manifest.get("scope")
    if isinstance(scope, dict):
        box = scope.get("box")
        if isinstance(box, int) and not isinstance(box, bool):
            return box
    recorded = manifest.get("capture_dir")
    if not isinstance(recorded, str) or not recorded:
        return None
    found = _BOX_IN_PATH.match(Path(recorded).name)
    return int(found.group(1)) if found else None


def _box_names() -> Dict[int, Tuple[str, Optional[str], FrozenSet[str]]]:
    """`box -> (the name, when the box was created, the runs its cards came from)`.

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
    names: Dict[int, Tuple[str, Optional[str], FrozenSet[str]]] = {}
    for key, entry in inventory.boxes.items():
        name = entry.name
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            box = int(key)
        except (TypeError, ValueError):
            # A registry key that will not coerce names no box, exactly as `_box_row`'s walk
            # treats a card whose box will not: skipped, never fatal.
            continue
        names[box] = (name, entry.created_at, frozenset(present.get(box, ())))
    return names


def _busy_run(box: int) -> Optional[str]:
    """The name of a live run already reading this BOX, if there is one.

    THE GUARD IS AGAINST A DOUBLE-CLICK, not against an attacker: two live batches over one
    box is the shape that turns one invoice into two. Two runs over DIFFERENT boxes are fine
    and are not blocked — the Batch API takes them in parallel and the cache keys them apart,
    which is what makes a cart of boxes one send rather than a queue.

    IT COMPARES BOXES AND NOT PATHS, AND THAT CLOSED A REAL HOLE. It used to resolve the
    incoming capture directory against each live run's recorded one, which works for a whole
    box — `captures/cards/box3` both times — and cannot work for a ticked selection, because
    `_scope_dir` builds a FRESH `.scopes/box3-<n>-<timestamp>` on every press. Two presses
    over one selection were two different paths, neither saw the other, and the subset path
    therefore had no double-click guard at all.

    It narrows what is allowed, deliberately: two live runs over DISJOINT selections in one
    box are now refused as well. That is the case an operator cannot tell apart from the
    double-click at the moment of the press, and the refusal names the run so the answer is
    one click away rather than one invoice away.
    """
    root = files.runs_dir()
    if not root.is_dir():
        return None
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir() or not (entry / run_files.MANIFEST).is_file():
            continue
        if _live_pid(entry) is None:
            continue
        try:
            manifest = json.loads((entry / run_files.MANIFEST).read_text())
        except (OSError, ValueError):
            continue
        if _run_box(manifest) == box:
            return entry.name
    return None


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


def _preflight_leg(leg: Leg) -> dict:
    """One box's dry run. Free by construction — `--dry-run` returns before `runs.create`."""
    argv = [str(PKMNSCAN), "identify", str(leg.directory), "--dry-run"] + leg.flags
    code, text = _run_sync(argv, PREFLIGHT_TIMEOUT_S)
    return {
        "ok": code == 0,
        "exit_code": code,
        "scope": leg.scope,
        "capture_dir": str(leg.directory),
        "console": text,
        **_parse_preflight(text),
        # The busy check is reported by the preflight so the screen can withhold its own
        # confirm before the operator reaches for it, rather than letting them press a
        # button that is going to refuse.
        "busy_run": _busy_run(leg.scope["box"]),
    }


def _total(answers: Sequence[dict]) -> dict:
    """What the whole send costs, summed HERE and never on the screen.

    THE NUMBER THE CONFIRM IS GATED ON IS THE SERVER'S. `app/src/server.ts` records that the
    app is forbidden from computing rules the pipeline owns, and this is the sharpest case of
    it: the total on screen is the total the operator is agreeing to spend, and a `reduce` in
    TypeScript would be a second implementation of the cost model that can disagree with the
    per-box figures printed directly above it.

    A MISSING FIGURE POISONS ITS SUM RATHER THAN COUNTING AS ZERO. `_parse_preflight` answers
    `None` where a line did not appear, precisely so a changed preflight shows up as a
    missing figure rather than as a confident zero — and a sum that quietly skipped one would
    undo that at the exact moment it mattered, by understating what a press is about to buy.
    """

    def _sum(key: str):
        values = [answer[key] for answer in answers]
        return None if any(value is None for value in values) else sum(values)

    money = _sum("estimate_usd")
    return {
        "photographs": _sum("photographs"),
        "cache_hits": _sum("cache_hits"),
        "to_send": _sum("to_send"),
        # Rounded to cents at the sum rather than per leg: the legs are what the commands
        # printed and are left exactly as printed.
        "estimate_usd": None if money is None else round(money, 2),
        "boxes": len(answers),
        # Every live run standing between this cart and a send, named. The screen withholds
        # its confirm on a non-empty list, which is cheaper than letting the operator press a
        # button that is going to refuse on the third of five boxes.
        "busy": [
            {"box": answer["scope"]["box"], "run": answer["busy_run"]}
            for answer in answers
            if answer["busy_run"] is not None
        ],
    }


def do_pipeline_preflight(payload: dict) -> dict:
    """`POST /pipeline/preflight` — what a send would cost. FREE, and creates no run.

    `identify --dry-run` returns before `runs.create`, so this leaves nothing on disk at all.
    Each box's raw stdout is returned alongside its parsed figures and the screen shows it
    verbatim: `docs/DESIGN.md`'s copy rule makes the owner's screens the place the pipeline's
    own words are shown rather than paraphrased, and the preflight is the densest thing it
    says.

    THE ANSWER IS ALWAYS A LIST, EVEN FOR ONE BOX. A response shape that changed with the
    request would make every reader ask which one it got before it could ask anything else —
    so a single-box send answers as a cart of one, exactly as `_resolve_legs` reads it.

    THE LEGS RUN AT ONCE, WHICH IS A LATENCY FIX AND NOT AN OPTIMISATION. A preflight decodes
    and crops every photograph in its box, measured at about a minute for 544 cards, so five
    boxes in series is a request held open for five minutes with nothing on screen. They are
    separate read-only processes over a lock-free snapshot, so there is nothing for them to
    contend over — `--dry-run` writes nothing at all, which is the property that makes this
    safe rather than merely fast.
    """
    legs = _resolve_legs(payload)
    if len(legs) == 1:
        answers = [_preflight_leg(legs[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(PREFLIGHT_WORKERS, len(legs))) as pool:
            answers = list(pool.map(_preflight_leg, legs))
    return {
        "ok": all(answer["ok"] for answer in answers),
        "scopes": answers,
        "total": _total(answers),
    }


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

    IT CREATES NOTHING AND SPENDS NOTHING. No run directory, no scope directory, no store
    write, no model call. It is a read, and it sits in this module rather than beside
    `GET /photo` because everything it knows — the crop, the max edge, the scope — is this
    module's vocabulary.
    """
    scope_dir, scope = _resolve_scope(payload)
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
        from identify import images as identify_images, sidecar
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

    captures = [c for c in sidecar.scan(scope_dir) if c.has_position]
    total = len(captures)
    if total == 0:
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND,
            "scope_is_empty",
            "Nothing in this scope carries a position, so there is no card to preview.",
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
            "scope": scope,
            "capture_dir": str(scope_dir),
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
        "scope": scope,
        "capture_dir": str(scope_dir),
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


def _spawn(leg: Leg) -> dict:
    """Create this leg's run directory and start its detached child. Costs money."""
    run = run_files.create(leg.label)
    # Written HERE and not left to the child, because `_run_box` reads it: a run whose
    # manifest names neither a scope nor a capture directory until the child's first flush
    # is a run the double-click guard cannot see during exactly the window a double-click
    # happens in.
    run.set(
        capture_dir=str(leg.directory),
        scope=leg.scope,
        started_by="app",
        flags_from_app=leg.flags,
    )

    argv = (
        [str(PKMNSCAN), "identify", str(leg.directory), "--run-dir", str(run.directory)]
        + leg.flags
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
            f"Could not start `pkmnscan identify` for box {leg.scope['box']}: {exc}",
        ) from None
    (run.directory / PID_FILE).write_text(f"{child.pid}\n")
    return {
        "run": run.directory.name,
        "path": str(run.directory),
        "pid": child.pid,
        "scope": leg.scope,
        "argv": argv,
    }


def do_pipeline_identify(payload: dict) -> Tuple[HTTPStatus, dict]:
    """`POST /pipeline/identify` — THE ROUTE THAT SPENDS MONEY. Spawns, does not wait.

    Answers as soon as the children are running, with one run name per box. Everything after
    that is read from the run directories by `do_pipeline_run` — this process keeps nothing,
    which is what lets a run outlive the server that started it.

    IT IS STILL EXACTLY ONE ROUTE THAT SPENDS, AND THAT IS WHY THE CART LANDED HERE RATHER
    THAN BESIDE IT. A send of several boxes could have been a second route, or N calls from
    the screen; both were declined for the same reason. This file's whole claim is that the
    money is behind one door with one `confirm` and one refusal path, and a screen pressing a
    money route five times on one operator decision is five confirms none of which the
    operator gave separately. One press, one request, one `confirm`, one total on the screen
    above it.

    NOTHING IS SPAWNED UNTIL EVERY LEG HAS PASSED. `_resolve_legs` validates the whole cart,
    and the live-run guard runs over all of it before the first child starts — so a cart with
    a busy box in the middle refuses whole, rather than leaving two boxes identifying and an
    error message about the third. D29's shape, with an invoice instead of a queue answer.

    THE ONE THING THAT CANNOT BE PRE-CHECKED IS REPORTED RATHER THAN HIDDEN. `Popen` can fail
    on the fourth leg after three have started, and no amount of validation sees that coming.
    The response carries what STARTED and what did not, both named; the screen draws the
    failures. A partial send reported honestly is recoverable — press again for the boxes
    that did not go — and a partial send reported as a success is an invoice nobody can
    account for.
    """
    if payload.get("confirm") is not True:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "This is the step that spends money. Send `confirm: true` — and show the "
            "operator /pipeline/preflight's card count and estimate before you do.",
        )
    legs = _resolve_legs(payload)
    for leg in legs:
        busy = _busy_run(leg.scope["box"])
        if busy is not None:
            raise PipelineRefusal(
                HTTPStatus.CONFLICT,
                "run_already_live",
                f"Run {busy} is already identifying box {leg.scope['box']}. Two live "
                f"batches over one box is two invoices for one answer — watch that run, or "
                f"wait for it to finish. Nothing in this send was started.",
            )

    started: List[dict] = []
    failed: List[dict] = []
    for leg in legs:
        try:
            started.append(_spawn(leg))
        except PipelineRefusal as refusal:
            failed.append(
                {
                    "box": leg.scope["box"],
                    "code": refusal.code,
                    "message": str(refusal),
                }
            )
    if not started:
        raise PipelineRefusal(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            failed[0]["code"],
            failed[0]["message"],
        )
    return HTTPStatus.ACCEPTED, {"started": started, "failed": failed}


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


def _artefacts(directory: Path) -> List[dict]:
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
                "is_import": entry.name.startswith("import-") and entry.suffix == ".csv",
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


def _box_name_for(
    box: Optional[int],
    run: str,
    ran_at: Optional[str],
    names: Dict[int, Tuple[str, Optional[str], FrozenSet[str]]],
) -> Optional[str]:
    """The registry's name for this box, unless the box in it is a different drawer.

    `_box_names` HAS ALWAYS SAID A VANISHED BOX GETS NO NAME — *"the run remembers a box the
    store no longer has, and a missing name is the honest rendering of that"* — and could not
    see the case where it matters, because the number is REALLOCATED: D20 hands out the
    lowest free integer, so the map is never missing the key, it is holding somebody else's
    answer under it.

    TWO CONDITIONS, BOTH REQUIRED, AND EACH RULES OUT THE OTHER'S FALSE POSITIVE. This is the
    correction to a first version that used the timestamp alone and was wrong:

      the box was created AFTER the run started
      and the box's cards DISOWN the run — it holds some, and none of them is this run's

    **The timestamp alone forbids naming a box afterwards, which is an ordinary thing to
    do.** A run started in a terminal over `captures/cards/box3` can be named the moment the
    owner opens the registry, and T7 asserts exactly that flow: name the box, and the name
    reaches the run on the next read. A rule reading the clock refuses it forever.

    **The card set alone forbids naming a box for a run that has not identified yet.** `run`
    is written onto a card by `identify`, so a fresh run over a box already holding another
    run's cards owns none of them for as long as it is live — and would lose its box's name
    for precisely the window the screen is polling it at 4s.

    Together they name the one shape neither can: a box that arrived after the run AND whose
    contents came from somewhere else. An empty box disowns nobody, which is what keeps the
    name-it-later flow working.

    IT ABSTAINS TOWARDS NAMING. An unparseable or absent timestamp means this cannot tell,
    and withholding on ignorance would strip the name off every run whose manifest predates
    the field — a claim of its own, made about runs this knows nothing about.
    """
    if box is None:
        return None
    found = names.get(box)
    if found is None:
        return None
    name, made_at, runs_present = found
    if not runs_present or run in runs_present:
        return name
    if not isinstance(ran_at, str) or not isinstance(made_at, str):
        return name
    try:
        born = datetime.fromisoformat(made_at)
        ran = datetime.fromisoformat(ran_at)
    except ValueError:
        # Not lexicographic: `...:24+00:00` and `...:24.500+00:00` differ in a character
        # class before the offset, so string order is only accidentally time order.
        return name
    return None if born > ran else name


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
    if names is None:
        names = _box_names()
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
        "box_name": _box_name_for(
            box, directory.name, manifest.get("created_at"), names
        ),
        "started_by": manifest.get("started_by"),
        "live": pid is not None,
        "pid": pid,
        "phase": _phase(manifest, pid is not None),
        "batch_ids": manifest.get("batch_ids") or [],
        "collected": bool(manifest.get("collected")),
        "joined": bool(manifest.get("joined")),
        "counts": manifest.get("counts") or {},
        "usage": manifest.get("usage") or {},
    }


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
    body["files"] = _artefacts(directory)
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
    what stops an `emit`; `app/src/readiness.ts` already mirrors it for the open screen and is
    audited against it, and a third implementation here to answer the same question would be
    the drift that audit exists to catch.
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


def _pricing_constant(chosen: Sequence[str], field: str) -> Optional[str]:
    """One run-wide figure off the newest readable table — `threshold` or `floor`.

    NEWEST FIRST AND THE FIRST ANSWER WINS, because these are `pipeline/pricing.py` constants
    rather than per-run choices: every table on this machine carries the same pair, and the
    newest is simply the one most likely to still be right if that ever stops being true. A
    run whose table cannot be read is skipped rather than answered `None`, which would blank
    a figure on the screen because of a file nobody was looking at.
    """
    root = files.runs_dir()
    for name in reversed(list(chosen)):
        table = root / name / run_files.PRICING
        if not table.is_file():
            continue
        try:
            value = json.loads(table.read_text("utf-8")).get(field)
        except (OSError, ValueError):
            continue
        if value is not None:
            return str(value)
    return None


def do_pipeline_worklist(wanted: Sequence[str]) -> dict:
    """`GET /pipeline/pricing` — one pricing worklist over several runs (D86).

    THE WORKLIST SPANS RUNS, AND SO DOES THE ANSWER. D48's resolution — a send is a cart of
    boxes and a run is still one box, because a run carries a reading that is a property of
    what is in the drawer — stays true of the READING. What this route adds is a VIEW across
    runs; the answer is the corpus's (D86, amended), and there is one write, `PUT /pricing`,
    whatever is on screen.

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
    which directory that is.
    """
    root = files.runs_dir()
    if not root.is_dir():
        return {
            "runs": [],
            "skus": [],
            "roster": [],
            "skipped": [],
            "asked": list(wanted),
            "live_cap": join.LIVE_QUANTITY_CAP,
            "threshold": None,
            "floor": None,
        }

    names = _box_names()
    asked = [str(name) for name in wanted if str(name).strip()]

    # EVERY JOINED RUN AND WHAT IT STILL OWES — the picker's own list, and deliberately not
    # the worklist's. The picker has to draw runs that are NOT loaded (that is what makes it a
    # picker), and it has to say which of them are worth loading. One pass, reusing the reads
    # the chooser below needs anyway.
    try:
        book = corpus.Corpus.read()
    except decisions.MalformedDecisions:
        # A CORPUS THAT CANNOT BE PARSED MUST NOT BLANK THE SCREEN — the operator has to be
        # able to SEE the file that is wrong. Every run then reads as owing an answer, which
        # is the honest reading of "nobody can tell what has been answered".
        book = corpus.Corpus()
    roster: List[dict] = []
    owed_by_run: Dict[str, List[str]] = {}
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / run_files.MANIFEST).is_file():
            continue
        manifest = _manifest(entry)
        if not manifest.get("joined"):
            continue
        table = entry / run_files.PRICING
        parsed: dict = {}
        answers: Optional[dict] = None
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
                {**_summary(entry, names), "owes": owed_by_run[entry.name], "open": True}
            )
            continue
        owes = _run_owes(manifest, parsed, answers)
        owed_by_run[entry.name] = owes
        roster.append({**_summary(entry, names), "owes": owes, "open": bool(owes)})
    # AN EXPLICIT ASK WINS OVER THE FILTER, whether or not the run is open: naming a run has
    # already answered the question `open` exists to ask, and an answered run has to stay
    # openable — that is how a price gets looked at again.
    chosen = asked or [row["run"] for row in roster if row["open"]]

    summaries: List[dict] = []
    written_at: Dict[str, int] = {}
    skipped: List[dict] = []
    # sku -> merged row. An `OrderedDict` because the ORDER IS THE HIERARCHY on this screen
    # (D78) and the first run to mention a SKU is what seeds its place; the sort that decides
    # the final order is the client's, over the same fields it already sorts one run by.
    merged: Dict[str, dict] = OrderedDict()

    for name in chosen:
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

    for row in merged.values():
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
        # `claimed_add` IS WHAT THE RUNS SEPARATELY BELIEVE AND `add_to_quantity` IS WHAT CAN
        # ACTUALLY GO. Drawing the sum would put "7" in the Qty column of a card four of which
        # may be listed, which is the same false-sentence failure D59 named. `copies_out` comes
        # off the NEWEST leg because it read the newest export; the two older `pricing.json`
        # shapes on this machine predate that field, so `live_before` is the documented
        # fallback and never a guess.
        #
        # REPORTED HERE, CORRECTED IN `emit`. This route writes nothing, so the honest thing it
        # can do is show the true figure and flag that the runs disagree with it.
        claimed = sum(leg.get("add_to_quantity") or 0 for leg in row["in"])
        newest = row["in"][-1]
        out_now = newest.get("copies_out")
        if out_now is None:
            out_now = newest.get("live_before") or 0
        room = max(0, join.LIVE_QUANTITY_CAP - int(out_now))
        row["claimed_add"] = claimed
        row["add_to_quantity"] = min(claimed, room, len(row.get("positions") or []))
        row["over_cap"] = claimed > row["add_to_quantity"]
        # A MERGED ROW THAT CAN ADD MUST NOT CARRY ONE RUN'S REASON FOR ADDING NOTHING.
        # `nothing_to_add` reads "every copy in this run is already listed or has left the
        # box" — true of that leg, false of the merge the moment another leg can add.
        if row["add_to_quantity"] > 0:
            row["nothing_to_add"] = None
            row["at_cap"] = False

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
        "threshold": (
            summaries and _pricing_constant(chosen, "threshold")
        ) or None,
        "floor": (summaries and _pricing_constant(chosen, "floor")) or None,
        # `remembered_sub_threshold` IS GONE, HERE AND FROM THE PER-RUN ROUTE (D86, amended
        # 2026-09-02). It walked up to five sibling run directories for the newest answer to a
        # question each run had to be asked separately, and offered it as a LABEL because D9
        # forbade defaulting it. There is one answer now — the corpus's policy, with a default
        # (D9 amended) — so nothing has to be remembered and no screen offers anything.
        "live_cap": join.LIVE_QUANTITY_CAP,
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
    upload = payload.get("export")
    if not isinstance(upload, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_required",
            "Send `export` as {name, content} — TCGplayer's My Pricing export, all printings.",
        )
    target = files.inventory_dir() / ".reconcile"
    target.mkdir(parents=True, exist_ok=True)
    path = _store_upload(target, upload, "live-")
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
    return {"corpus": corpus.Corpus.read().to_payload(), "path": str(files.prices_path())}


def do_pricing_corpus_write(payload: dict) -> dict:
    """`PUT /pricing` — replace the corpus.

    WHOLESALE, EXACTLY AS `PUT .../decisions` WAS, AND FOR ITS REASON: the screen round-trips
    every key it does not understand, so a field a later version adds — or `_note`, which a
    person writes by hand — survives a client that has never heard of it.

    IT VALIDATES THE POLICY AND NOT THE ANSWERS, which is the same line D49 drew. `Corpus.parse`
    raises on a rule or basis outside the enum, because a screen could otherwise write a
    document that makes `emit` answer with a traceback an hour later. A per-SKU answer is left
    alone: `Decisions.parse` is the one parser for what an answer means and it runs at the
    moment one is used, where its refusal names the SKU.
    """
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
    written = book.write()
    return {"ok": True, "written": str(written), "answers": len(book.answers)}


def do_pipeline_merged_emit(payload: dict) -> dict:
    """`POST /pipeline/emit` — one import file over several runs (D86).

    FREE AND RE-RUNNABLE, WHICH IS WHY IT RUNS INSIDE THE REQUEST. `emit` spends nothing: it
    reads the runs, writes a CSV and raises `pushed`. The one route here that can cause money
    to be spent is still `POST /pipeline/identify` and is still named for it.

    IT IS NOT `POST /pipeline/runs/<name>/emit` WIDENED, and the difference is the point. That
    route is per run and stays; this one takes a LIST, because the cap has to be re-derived
    across it — `pipeline/join.py` spends `live_cap - copies_out` per run against a global cap,
    so N per-run presses are exactly the over-push a merged file exists to prevent. Measured:
    three separate emits over three real runs wrote two SKUs past the cap of four.

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
    if len(wanted) > MAX_LEGS:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "too_many_runs",
            f"At most {MAX_LEGS} runs in one send.",
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
        "files": _artefacts(_open_run(newest)),
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
    wanted = (sku or "").strip()
    if not wanted:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "sku_required",
            "A price history is per SKU. Pass ?sku=<TCGplayer Id>.",
        )
    entry = _history_row(directory, wanted)
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
        "run": directory.name,
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
    wanted = [s for s in (str(x).strip() for x in skus) if s]

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
            refused[sku] = (
                f"Run {directory.name} matched no SKU {sku}. A history is read off the "
                f"export row this run stored."
            )
            continue
        if not wanted and entry.get("at_cap"):
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
        "run": directory.name,
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
    if filename not in {row["name"] for row in _artefacts(directory)}:
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
    return target


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
            candidate = directory / wanted
            if not candidate.is_file():
                raise PipelineRefusal(
                    HTTPStatus.NOT_FOUND,
                    "no_such_file",
                    f"Run {directory.name} holds no {wanted}. A fetch that refused deletes "
                    f"what it wrote, so this is a name from a fetch that did not land.",
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
        return {"game": game, "sets": [], "reason": "no_category"}
    category = int(category)
    if category not in _SETS_CACHE:
        try:
            vocabulary = tcg_export.filters(category)
        except tcg_export.FetchRefusal as caught:
            # NOT AN ERROR TO THE SCREEN. The operator is mid-capture; a refusal here is a
            # missing convenience, not a failed capture, and the reason is carried so the
            # screen can say why the list is empty rather than pretending the game has no sets.
            return {"game": game, "sets": [], "reason": caught.code}
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
    }


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

    try:
        scope, asked = _scope_for_run(directory, payload)
        body = tcg_export.fetch(scope)
    except tcg_export.FetchRefusal as caught:
        # A BAD GATEWAY AND NOT A 500. The failure is at TCGplayer or in the credential this
        # machine holds for it, and every one of these carries a sentence saying which.
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY, caught.code, caught.message
        ) from None

    # THE NAME CARRIES A DIGEST, AND A ONE-SECOND STAMP ALONE WAS A DATA-LOSS BUG. T7 found
    # it: two fetches inside the same second composed the same filename, so the second one
    # OVERWROTE the first — and the first is what the run was joined against. A file silently
    # replaced by the very thing being checked against it passes every check by comparing
    # itself to itself. T7's same-second case is the record of that.
    #
    # IDENTICAL BYTES LAND ON THE FILE THE RUN ALREADY HOLDS — AND THAT CLAIM WAS FALSE UNTIL
    # 2026-09-02. This comment said a re-fetch of identical bytes "lands on the identical
    # name", while the per-second stamp came BEFORE the digest in that name: two fetches a
    # second apart never composed the same name, `fresh` was always true, and every re-fetch
    # added a copy. Measured: run `2026-08-31-box3-01` holds two byte-identical 366 KB exports
    # 29 seconds apart. So the digest is computed first and the run directory is searched for
    # a file already carrying it, compared in full — 32 bits of digest is a name, not a proof.
    # A hit IS the file: an identical re-fetch is a fresh observation of the same reading, so
    # its mtime is touched, because the export's observation time is read off that mtime. A
    # miss gets a stamped name of its own and can never clobber a predecessor.
    digest = hashlib.sha256(body).hexdigest()[:8]
    held = [
        path
        for path in sorted(directory.glob(f"{FETCHED_PREFIX}*-{digest}.csv"))
        if path.read_bytes() == body
    ]
    # WHETHER THIS REQUEST CREATED IT DECIDES WHETHER A REFUSAL MAY DELETE IT. "A refusal
    # tears down what it built" is the rule, and the emphasis is on BUILT: re-fetching bytes
    # this run already holds lands on the existing file, and unlinking that would destroy a
    # recorded export over a refusal that fired on something else.
    if held:
        target = held[0]
        fresh = False
        os.utime(target, None)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        target = directory / f"{FETCHED_PREFIX}{stamp}-{digest}.csv"
        fresh = True
        target.write_bytes(body)

    def refuse(status, code, message):
        if fresh:
            target.unlink(missing_ok=True)
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
        "files": _artefacts(directory),
        "summary": _summary(directory),
    }

