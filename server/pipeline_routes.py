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
  - **The crop preview is free and shells out to nothing.** `POST /pipeline/crop-preview`
    answers what a reading does to the bytes — the cut, and the collector-number strip at
    the resolution it delivers — so the pair is legible before the estimate is asked for.
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

import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
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

# Downloadable run artefacts are matched by SHAPE, never by a name from the request. The
# request names a file, this decides whether that name is one this route is willing to
# serve, and nothing built from user input is ever joined onto a path.
_DOWNLOADABLE = re.compile(r"^[A-Za-z0-9._-]+\.(csv|txt|json|log)$")

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


def _busy_run(capture_dir: Path) -> Optional[str]:
    """The name of a run already reading this capture directory, if one is live.

    THE GUARD IS AGAINST A DOUBLE-CLICK, not against an attacker, and it is scoped to the
    capture directory rather than to the server: two live batches over one box is the shape
    that turns one invoice into two. Two runs over DIFFERENT boxes are fine and are not
    blocked — the Batch API takes them in parallel and the cache keys them apart.
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
        recorded = manifest.get("capture_dir")
        if recorded and Path(recorded).resolve() == capture_dir.resolve():
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


def do_pipeline_preflight(payload: dict) -> dict:
    """`POST /pipeline/preflight` — what a run would cost. FREE, and creates no run.

    `identify --dry-run` returns before `runs.create`, so this leaves nothing on disk at all.
    The raw stdout is returned alongside the parsed figures and the screen shows it verbatim:
    `docs/DESIGN.md`'s copy rule makes the owner's screens the place the pipeline's own words
    are shown rather than paraphrased, and the preflight is the densest thing it says.
    """
    scope_dir, scope = _resolve_scope(payload)
    argv = [str(PKMNSCAN), "identify", str(scope_dir), "--dry-run"] + _identify_flags(payload)
    code, text = _run_sync(argv, PREFLIGHT_TIMEOUT_S)
    figures = _parse_preflight(text)
    return {
        "ok": code == 0,
        "exit_code": code,
        "scope": scope,
        "capture_dir": str(scope_dir),
        "console": text,
        **figures,
        # The busy check is reported by the preflight so the screen can disable its own
        # confirm before the operator reaches for it, rather than letting them press a
        # button that is going to refuse.
        "busy_run": _busy_run(scope_dir),
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
        from PIL import Image
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
        )

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

    rect = (
        identify_images.crop_rect(prepared.original_size, detected)
        if crop and detected is not None
        else None
    )

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


def do_pipeline_identify(payload: dict) -> Tuple[HTTPStatus, dict]:
    """`POST /pipeline/identify` — THE ROUTE THAT SPENDS MONEY. Spawns, does not wait.

    Answers as soon as the child is running, with the run's name. Everything after that is
    read from the run directory by `do_pipeline_run` — this process keeps nothing, which is
    what lets a run outlive the server that started it.
    """
    if payload.get("confirm") is not True:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "This is the step that spends money. Send `confirm: true` — and show the "
            "operator /pipeline/preflight's card count and estimate before you do.",
        )
    scope_dir, scope = _resolve_scope(payload)
    busy = _busy_run(scope_dir)
    if busy is not None:
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "run_already_live",
            f"Run {busy} is already identifying these cards. Two live batches over one box "
            f"is two invoices for one answer — watch that run, or wait for it to finish.",
        )

    label = payload.get("label")
    if not isinstance(label, str) or not label.strip():
        label = f"box{scope['box']}"
    run = run_files.create(label)
    # Written HERE and not left to the child, because `_busy_run` reads it: a run whose
    # manifest names no capture directory until the child's first flush is a run the
    # double-click guard cannot see during exactly the window a double-click happens in.
    run.set(
        capture_dir=str(scope_dir),
        scope=scope,
        started_by="app",
        flags_from_app=_identify_flags(payload),
    )

    argv = (
        [str(PKMNSCAN), "identify", str(scope_dir), "--run-dir", str(run.directory)]
        + _identify_flags(payload)
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
            f"Could not start `pkmnscan identify`: {exc}",
        ) from None
    (run.directory / PID_FILE).write_text(f"{child.pid}\n")
    return HTTPStatus.ACCEPTED, {
        "run": run.directory.name,
        "path": str(run.directory),
        "pid": child.pid,
        "scope": scope,
        "argv": argv,
    }


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
