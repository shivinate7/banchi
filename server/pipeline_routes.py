"""The pipeline seam — the four commands of batch script v2, reachable from a screen.

THIS IS THE FILE THAT BREAKS `capture_server.py`'s OLDEST PROMISE, and it does it on
purpose. That file's header said for months: *"no identification, no pricing, no UI. This
process never spends money: it holds no API key and makes no outbound call."* Both halves
of that are still literally true of this process — nothing here reads a key and nothing
here opens a socket to Anthropic — but the sentence was written to mean something stronger,
and pretending the letter is the whole of it would be the drift D16 exists to catch. A
route here can CAUSE money to be spent, by starting a child that spends it.

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
  - **The preflight is free, is a separate route, and is what the screen must show first.**
    `--dry-run` does everything except the API call: it counts the cards, prices the
    submission, and creates no run directory at all.

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

import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cli import runs as run_files  # noqa: E402
from store import files  # noqa: E402

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
    directory, its manifest scope, `join`, `emit`, `reconcile`, the queue it writes and the
    `--bypass` decision taken over it are all exactly what they were. What is new is that one
    press can start several, which is a fact about the REQUEST and not about a run.
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
    max_edge = payload.get("max_edge")
    if max_edge is not None:
        if not isinstance(max_edge, int) or isinstance(max_edge, bool) or not (
            256 <= max_edge <= 4096
        ):
            raise PipelineRefusal(
                HTTPStatus.BAD_REQUEST,
                "max_edge_invalid",
                "`max_edge` must be an integer between 256 and 4096. D32's measured "
                "frontier for this rig runs 900 to 1400.",
            )
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
    if not manifest.get("emitted"):
        return "emit"
    if not manifest.get("reconciled"):
        return "reconcile"
    return "done"


def _summary(directory: Path) -> dict:
    manifest = _manifest(directory)
    pid = _live_pid(directory)
    return {
        "run": directory.name,
        "path": str(directory),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "capture_dir": manifest.get("capture_dir"),
        "scope": manifest.get("scope"),
        "started_by": manifest.get("started_by"),
        "live": pid is not None,
        "pid": pid,
        "phase": _phase(manifest, pid is not None),
        "batch_ids": manifest.get("batch_ids") or [],
        "collected": bool(manifest.get("collected")),
        "joined": bool(manifest.get("joined")),
        "counts": manifest.get("counts") or {},
        "bypass_detection": bool(manifest.get("bypass_detection")),
        "bypassed": manifest.get("bypassed"),
        "usage": manifest.get("usage") or {},
    }


def do_pipeline_runs() -> dict:
    """`GET /pipeline/runs` — every run, newest first. A read; costs nothing."""
    root = files.runs_dir()
    if not root.is_dir():
        return {"runs": []}
    rows = [
        _summary(entry)
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


def _remembered_sub_threshold(directory: Path) -> Optional[dict]:
    """The sub-threshold answer the newest OTHER run gave, or `None`.

    "REMEMBER THAT I SAID SO", WITH NO NEW STORAGE — the owner's words when asked what the
    standing answer should be. Every run already writes its own answer into its own
    `decisions.json`, so the last one is on disk and needs no second home, no migration and
    no file that can disagree with the runs it claims to summarise.

    A LABEL AND NEVER A DEFAULT. D9 is explicit that the sub-threshold disposition is a
    per-run choice and that output is suppressed until it is made — so this removes the time
    spent DECIDING and not the press. A pre-selected answer is one nobody read.

    Bounded to five directories, newest first, stopping at the first run that answered. No
    earlier answer means no label, which is correct: there is nothing to remember.
    """
    root = files.runs_dir()
    if not root.is_dir():
        return None
    seen = 0
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir() or entry == directory:
            continue
        seen += 1
        if seen > 5:
            return None
        path = entry / run_files.DECISIONS
        if not path.is_file():
            continue
        try:
            answer = json.loads(path.read_text("utf-8")).get("sub_threshold")
        except (OSError, ValueError):
            continue
        if answer is not None:
            return {"answer": answer, "run": entry.name}
    return None


def do_pipeline_pricing(name: str) -> dict:
    """`GET /pipeline/runs/<name>/pricing` — the per-SKU table and this run's answers.

    FREE, READ-ONLY, AND IT CREATES NOTHING. It opens files the run directory already holds
    and computes no price: `cli/cmd_join.py` wrote every figure in `pricing.json` through
    `pipeline/pricing.py`, which is the only place in this repo allowed to. This route is a
    reader, and `app/src/server.ts` already records that the app may not compute rules the
    pipeline owns — that rule reaches the server that feeds it.

    TWO FILES IN ONE READ, WHICH IS THE WHOLE REASON IT IS A ROUTE RATHER THAN TWO
    DOWNLOADS. `_DOWNLOADABLE` already matches `.json`, so a screen could fetch
    `pricing.json` and `decisions.json` through `GET .../file` and needs neither route nor
    handler — but two fetches can straddle a re-join, and a table describing one join beside
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
    decisions_path = directory / run_files.DECISIONS
    try:
        pricing = json.loads(table.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "pricing_unreadable",
            f"{run_files.PRICING} could not be read: {exc}. Re-join this run to rewrite it.",
        ) from None
    answers = None
    if decisions_path.is_file():
        try:
            answers = json.loads(decisions_path.read_text("utf-8"))
        except (OSError, ValueError):
            # DELIBERATELY NOT A REFUSAL. `emit` and `join` both answer an unreadable
            # decisions document with a sentence naming what is wrong with it, and that is
            # where an operator should read it; a screen that would not draw AT ALL because
            # its answers file is malformed is a screen that cannot show you the file.
            answers = None
    return {
        "run": directory.name,
        "pricing": pricing,
        "decisions": answers,
        "remembered_sub_threshold": _remembered_sub_threshold(directory),
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
    """`--export` arguments: what was uploaded now, or what the manifest recorded before.

    Falling back to the manifest is what keeps `join` free and re-runnable from a screen —
    change the rule, clear a review, press it again, and the same files answer. `join`
    itself already reads `exports_by_game` when no `--export` is given, so this passes
    nothing rather than re-deriving the mapping and risking a different answer.
    """
    uploads = payload.get("exports")
    if uploads is None:
        return []
    if not isinstance(uploads, list) or not uploads:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "exports_invalid",
            "`exports` must be a non-empty array of {name, content}, or absent to re-use "
            "the files this run was last joined against.",
        )
    argv: List[str] = []
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
        if payload.get("bypass"):
            argv.append("--bypass")
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


def do_pipeline_decisions(name: str, payload: dict) -> dict:
    """`PUT /pipeline/runs/<name>/decisions` — the sub-threshold answer D9 makes a file.

    THE PRICING QUESTION GATES `emit` AND NOTHING ELSE, which is the owner's ruling and is
    already how the pipeline is built: `join` writes `decisions.json` with the run-wide
    choice UNSET and `emit` refuses while it stays that way. This route is the screen's way
    to answer it, and it deliberately does not validate the answer's meaning — `emit` owns
    that refusal, and a second validator here would be a second set of rules about what a
    disposition is, disagreeing with the first at exactly the moment it mattered.

    Replaces the file wholesale, because it is one document the operator is editing and a
    merge would need this route to understand the schema it just declined to own. The client
    reads the current file through `GET /pipeline/runs/<name>/file?name=decisions.json`
    first, which is the same read-modify-write the run report tells a terminal user to do.
    """
    directory = _open_run(name)
    document = payload.get("decisions")
    if not isinstance(document, dict):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "decisions_invalid",
            "Send `decisions` as the whole decisions.json object.",
        )
    target = directory / run_files.DECISIONS
    if not target.is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "decisions_not_written",
            f"Run {name} has no {run_files.DECISIONS} yet — `join` is what writes it, with "
            f"every SKU that needs an answer already filled in.",
        )
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "run": directory.name, "written": str(target)}
