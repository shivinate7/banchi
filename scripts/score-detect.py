#!/usr/bin/env python3
"""Re-score `geometry.detect_card` over real capture directories — the D75 pass, repeatable.

THE PROMISE THIS DISCHARGES. `identify/images.py`'s block above `SMALL_CROP_AREA` records a
measurement taken on 2026-08-31: 867 photographs across three real boxes, a box returned for
every one, none refused, and nine crops that were a rectangle INSIDE the card. Two constants
were fitted to that sample and they now gate the paid identification path. The sample was a
one-off — a session, an afternoon, a set of frames nobody can re-select the same way — and
since then the same three boxes have grown to 1,625 photographs, of which 226 were captured
after the constants were chosen. A number that gates money and cannot be re-taken is a number
that can only be trusted or abandoned, never checked. This is the pass, written down.

WHAT IT ANSWERS, and — more importantly — what it does not:

    scan     per box and overall: how many photographs yielded a box, how many the detector
             refused, and how many of the boxes it did return the crop guard then declines
             to cut. With the area and detail distributions, because those are the two axes
             the constants sit between and a rate with no distribution behind it cannot say
             whether a line is in a gap or in the middle of the population.
    sweep    what other (area, detail) pairs would have declined, over the same scan.

WHAT NOBODY SHOULD READ OUT OF THIS: A WRONGNESS RATE. The nine wrong crops of 2026-08-31
were confirmed by eye, one photograph at a time, and nothing here has an answer key. This
script cannot tell a small crop that is the whole card shot from far back from a small crop
that is the card's rules-text panel; the guard cannot either, which is exactly why the guard
is two measurements and an AND rather than one threshold. `crop_refusal` says "declined",
never "wrong", and so does every count below. The block in `identify/images.py` closes by
saying what is established and what is not — "what is not is a rate at which detection goes
wrong" — and this script does not change that sentence.

WHAT IT IS FOR, THEN. A refusal rate that is comparable across boxes and across time. Every
box on this rig was shot the same way, so a box whose rate departs from its neighbours', or
whose rate moves between two runs of this script, is the cheap signal that something under
the constants changed — the light, the stand, the camera, the detector — while the constants
did not. That signal costs no answer key and no eye, and it is the one this repo has never
had. Confirming a departure still means looking at the frames.

    scripts/score-detect.py scan  [<captures dir>] [--box <name>] [--limit <n>] [--write]
    scripts/score-detect.py sweep [<captures dir>] [--box <name>] [--limit <n>]

THE DIRECTORY DEFAULTS TO THIS CHECKOUT'S OWN `captures/`, WHICH IN A WORKTREE IS EMPTY, and
that is D43 working rather than failing: captures follow the checkout, so a worktree's are its
own and usually there are none. A real scan names the main checkout's directory outright. It
is opened read-only — nothing here writes, moves or re-encodes a photograph.

THE CONSTANTS ARE IMPORTED, NOT MIRRORED, which is the one place this parts company with
`scripts/score-trace.py`. That script keeps its own copy of `app/src/motion.ts`'s parameters
because the machine it grades is TypeScript and cannot be imported, and `make docs-audit`'s
`motion params` row exists to keep the copy honest. Here the machine is `identify/images.py`
and importing it is free, so a second copy would be a number able to disagree with the one it
claims to grade, with no way to tell which drifted. The scan does keep its own arithmetic for
the rule — area and detail on every crop, not only on the small ones `crop_refusal` measures —
and it checks that arithmetic against `crop_refusal`'s own verdict on every frame; a
disagreement is reported as a defect in THIS file rather than as a finding about the rig.

Pillow and numpy are required and not optional, unlike score-trace.py's stdlib half: there is
no detection without them. Run it from the repo venv.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import geometry  # noqa: E402
from identify import images, sidecar  # noqa: E402
from pipeline import games  # noqa: E402
from store import files  # noqa: E402

try:  # said once, here, rather than as a traceback per frame
    from PIL import Image
except ImportError:  # pragma: no cover - environment problem, not logic
    raise SystemExit(
        "score-detect needs Pillow and numpy — there is no detection without them. "
        "Run it from the repo venv (`make venv`)."
    ) from None

RESULTS_DIR = ROOT / "harness" / "results"

# The files whose behaviour a score is a score OF. A number taken from a different detector
# is not comparable to one taken from this one, which is `harness/results/README.md`'s rule
# about the prompt hash read across to the thing being measured here.
FINGERPRINTED = (
    "geometry/detect.py",
    "geometry/crop.py",
    "identify/images.py",
)

# How near a line a crop has to sit to be called a close call. Not a threshold anything acts
# on — it exists so the report can say how much of the population the constants are actually
# adjudicating, rather than only how the vote came out.
NEAR = 0.05

# What `sweep` tries. Bracketing the two live constants rather than centred on them, because
# the question a sweep answers is which side of each line the population is piled on.
AREA_GRID = (0.20, 0.25, 0.30, 0.35, 0.40)
DETAIL_GRID = (0.40, 0.45, 0.50, 0.55, 0.60)

FOUND = "found"
NOT_FOUND = "not_found"
NO_SHAPE = "no_shape"
UNREADABLE = "unreadable"

# THE ONE REFUSAL THAT NEEDS TO NAME D43, because in a worktree it is the correct answer and
# reads like a fault. A checkout's captures are its own, so a branch's are usually absent.
_NO_BOXES = (
    "{root} {why}, so there are no box directories to score. In a worktree that is D43 "
    "working rather than a fault — captures follow the checkout — and the real scan names "
    "the main checkout's captures directory outright."
)


@dataclass
class Photo:
    """One photograph's verdict. `area` and `detail` are None unless a box was returned."""

    name: str
    game: str
    outcome: str
    method: Optional[str] = None
    area: Optional[float] = None
    detail: Optional[float] = None
    # `crop_refusal`'s own sentence, or None to go ahead. THE AUTHORITY on the verdict.
    refusal: Optional[str] = None
    # Set when the guard could not read the frame back. Counted apart: a guard that could not
    # look is not the rig failing a rule, and cmd_identify treats it as a refusal anyway.
    guard_error: bool = False
    note: Optional[str] = None


def _fingerprint() -> str:
    """One short digest over the detector and the guard, in a fixed order."""
    digest = hashlib.sha256()
    for name in FINGERPRINTED:
        digest.update(name.encode("utf-8"))
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()[:12]


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * q)))]


def _spread(values: Sequence[float]) -> Optional[Dict[str, float]]:
    """min / p05 / p25 / median / p75 / p95 / max, or None for an empty population."""
    if not values:
        return None
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "p05": round(_quantile(values, 0.05), 4),
        "p25": round(_quantile(values, 0.25), 4),
        "median": round(_quantile(values, 0.50), 4),
        "p75": round(_quantile(values, 0.75), 4),
        "p95": round(_quantile(values, 0.95), 4),
        "max": round(max(values), 4),
    }


def _box_dirs(root: Path) -> List[Path]:
    """The `box*` directories under `root`, or `root` itself when it is one.

    Depth is not assumed. The rig writes `captures/cards/box<N>` and the operator says
    `captures/`, so a walk that only looked one level down would find nothing and report a
    clean zero — which is the shape of answer this repo has been bitten by before.
    """
    if not root.is_dir():
        raise SystemExit(_NO_BOXES.format(root=root, why="does not exist"))
    if root.name.startswith("box"):
        return [root]
    found = sorted(
        (path for path in root.rglob("box*") if path.is_dir()),
        key=lambda path: (len(path.parts), str(path)),
    )
    # A box directory inside another box directory is somebody's backup, not a second box.
    outer: List[Path] = []
    for path in found:
        if not any(seen in path.parents for seen in outer):
            outer.append(path)
    return sorted(outer, key=lambda path: str(path))


def _score(capture) -> Photo:
    """One photograph through exactly the path `cli/cmd_identify.py` puts it through.

    The game comes off the sidecar with D21's read-side backfill, the aspect off the game's
    own `card_aspect` (D22), and the verdict off `images.crop_refusal` rather than off any
    rule written here. What is computed locally is only the two figures the guard does not
    always take: `crop_refusal` measures detail solely on the crops the area leg has already
    put in question, and a distribution needs it on all of them.
    """
    game = capture.game_or_default
    try:
        entry = games.get(game)
    except games.UnknownGame:
        return Photo(capture.photo.name, game, NO_SHAPE, note="game not in the registry")

    aspect = entry["card_aspect"]
    try:
        box = geometry.detect_card(capture.photo, aspect=aspect)
    except geometry.UnknownCardShape:
        return Photo(capture.photo.name, game, NO_SHAPE, note="the game declares no card shape")
    except geometry.GeometryError as exc:
        return Photo(capture.photo.name, game, UNREADABLE, note=str(exc))

    if box is None:
        return Photo(capture.photo.name, game, NOT_FOUND, method=None)

    try:
        with Image.open(capture.photo) as opened:
            opened.load()
            width, height = opened.size
            rect = images.crop_rect(opened.size, box, images.CROP_PAD, aspect)
            area = ((rect[2] - rect[0]) * (rect[3] - rect[1])) / float(width * height)
            detail = images.detail_share(opened, rect)
            refusal = images.crop_refusal(opened, box, aspect=aspect)
    except images.ImageError as exc:
        return Photo(
            capture.photo.name,
            game,
            FOUND,
            method=box.method,
            refusal=str(exc),
            guard_error=True,
        )
    except OSError as exc:
        return Photo(capture.photo.name, game, UNREADABLE, note=str(exc))

    return Photo(
        capture.photo.name,
        game,
        FOUND,
        method=box.method,
        area=round(area, 6),
        detail=round(detail, 6),
        refusal=refusal,
    )


def scan_box(directory: Path, limit: Optional[int] = None) -> List[Photo]:
    captures = sidecar.scan(directory)
    if limit is not None:
        captures = captures[:limit]
    return [_score(capture) for capture in captures]


def _summarise(photos: Sequence[Photo]) -> Dict[str, object]:
    """Everything one population has to say, with no verdict about correctness in it."""
    found = [p for p in photos if p.outcome == FOUND]
    measured = [p for p in found if p.area is not None]
    refused = [p for p in found if p.refusal is not None]
    small = [p for p in measured if p.area < images.SMALL_CROP_AREA]
    thin = [p for p in measured if p.detail < images.MIN_CROP_DETAIL]

    methods: Dict[str, int] = {}
    for photo in found:
        methods[photo.method or "unknown"] = methods.get(photo.method or "unknown", 0) + 1
    by_game: Dict[str, int] = {}
    for photo in photos:
        by_game[photo.game] = by_game.get(photo.game, 0) + 1

    return {
        "photographs": len(photos),
        "found": len(found),
        "not_found": sum(1 for p in photos if p.outcome == NOT_FOUND),
        "no_shape": sum(1 for p in photos if p.outcome == NO_SHAPE),
        "unreadable": sum(1 for p in photos if p.outcome == UNREADABLE),
        "method": methods,
        "games": by_game,
        "crop_refused": len(refused),
        "crop_refusal_rate": round(len(refused) / len(found), 4) if found else None,
        "guard_errors": sum(1 for p in found if p.guard_error),
        # The three ways the AND rule can land, which is the only way to see the two legs
        # doing separate work rather than one of them carrying the whole rule.
        "asked_nothing": len(measured) - len(small),
        "justified": sum(1 for p in small if p.detail >= images.MIN_CROP_DETAIL),
        "declined": sum(1 for p in small if p.detail < images.MIN_CROP_DETAIL),
        "kept_by_area_leg": sum(1 for p in thin if p.area >= images.SMALL_CROP_AREA),
        # How much of the population the constants are actually adjudicating.
        "near_area_line": sum(1 for p in measured if abs(p.area - images.SMALL_CROP_AREA) <= NEAR),
        "near_detail_line": sum(1 for p in small if abs(p.detail - images.MIN_CROP_DETAIL) <= NEAR),
        "area": _spread([p.area for p in measured]),
        "detail": _spread([p.detail for p in measured]),
        # The detail of the crops the detail leg is the one judging. The whole-population
        # figure above is dominated by big crops nothing asks anything of.
        "detail_of_small_crops": _spread([p.detail for p in small]),
        # This script's own arithmetic against the guard's verdict, per frame. A non-zero
        # count is a defect HERE and the distributions beside it should not be believed.
        "rule_mismatches": sum(
            1
            for p in measured
            if ((p.area < images.SMALL_CROP_AREA and p.detail < images.MIN_CROP_DETAIL))
            != (p.refusal is not None)
        ),
    }


def _print_spread(label: str, spread: Optional[Dict[str, float]]) -> None:
    if spread is None:
        print(f"  {label:<24} —")
        return
    print(
        f"  {label:<24} min {spread['min']:.3f}  p05 {spread['p05']:.3f}  "
        f"median {spread['median']:.3f}  p95 {spread['p95']:.3f}  max {spread['max']:.3f}"
        f"   n={spread['n']}"
    )


def _print_block(title: str, stats: Dict[str, object]) -> None:
    rate = stats["crop_refusal_rate"]
    rate_text = "—" if rate is None else f"{rate * 100:.1f}%"
    print(f"{title}   {stats['photographs']} photographs   {stats['games']}")
    print(
        f"  {'found':<24} {stats['found']:>5}   not found {stats['not_found']}   "
        f"no shape {stats['no_shape']}   unreadable {stats['unreadable']}   "
        f"via {stats['method']}"
    )
    print(
        f"  {'crop guard declined':<24} {stats['crop_refused']:>5}   {rate_text} of the boxes "
        f"returned   (guard errors {stats['guard_errors']})"
    )
    print(
        f"  {'the rule':<24} {stats['asked_nothing']} asked nothing   "
        f"{stats['justified']} small and justified   {stats['declined']} small and declined"
    )
    print(
        f"  {'the legs':<24} {stats['kept_by_area_leg']} kept by the area leg alone "
        f"(detail < {images.MIN_CROP_DETAIL})"
    )
    print(
        f"  {'close calls':<24} {stats['near_area_line']} within {NEAR} of the area line   "
        f"{stats['near_detail_line']} within {NEAR} of the detail line"
    )
    _print_spread("area of the crop", stats["area"])
    _print_spread("detail the crop keeps", stats["detail"])
    _print_spread("detail, small crops", stats["detail_of_small_crops"])
    if stats["rule_mismatches"]:
        print(
            f"  !! {stats['rule_mismatches']} frames where this script's rule disagrees with "
            f"images.crop_refusal. That is a defect in scripts/score-detect.py."
        )
    print()


def _payload(root: Path, per_box: Dict[str, List[Photo]]) -> Dict[str, object]:
    every = [photo for photos in per_box.values() for photo in photos]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(root),
        "boxes_scanned": sorted(per_box),
        "image_count": len(every),
        "constants": {
            "SMALL_CROP_AREA": images.SMALL_CROP_AREA,
            "MIN_CROP_DETAIL": images.MIN_CROP_DETAIL,
            "CROP_PAD": images.CROP_PAD,
            "DETAIL_EDGE": images.DETAIL_EDGE,
            "CARD_ASPECT": geometry.CARD_ASPECT,
        },
        "detector_fingerprint": _fingerprint(),
        "detector_files": list(FINGERPRINTED),
        "overall": _summarise(every),
        "per_box": {name: _summarise(photos) for name, photos in sorted(per_box.items())},
        "not_measured": (
            "NO WRONGNESS RATE IS IN THIS FILE. Every count here is about what the detector "
            "returned and what images.crop_refusal did with it. Whether a returned box is "
            "the card or a rectangle inside it was settled by eye over 867 photographs on "
            "2026-08-31 and has been settled no other way since; nothing here has an answer "
            "key. A refusal rate that departs from a neighbouring box's, or from this file's "
            "last value at the same detector_fingerprint, is a reason to go and look."
        ),
    }


def _same_measurement(existing: dict, payload: dict) -> bool:
    """Everything but `generated_at`. A timestamp is not a finding.

    `harness/results/README.md`'s rule, and the same comparison `harness/tests/
    t1_id_eval.py:_same_measurement` makes, for the same reason: a re-score that recomputes
    the same numbers must leave the committed file byte-identical, or every run produces a
    one-line diff and the log stops being able to tell a re-measurement from a clock.
    """
    return {k: v for k, v in existing.items() if k != "generated_at"} == {
        k: v for k, v in payload.items() if k != "generated_at"
    }


def _scope(root: Path, per_box: Dict[str, List[Photo]], only: Optional[str]) -> Optional[str]:
    """What this scan is OF, as a filename suffix — None for a whole captures tree.

    READ OFF WHAT WAS SCANNED AND NOT OFF THE FLAG. `--box box4` and naming
    `captures/cards/box4` outright are the same measurement, and deciding this from `--box`
    alone would let the second form write the whole-tree filename over the whole-tree score.
    That is the exact substitution `harness/results/README.md` names — whichever ran last
    silently becomes "the" committed number — arriving by the argument nobody thought about.
    """
    if only is None and not root.name.startswith("box"):
        return None
    return "-".join(sorted(per_box))


def _write_results(payload: dict, scope: Optional[str]) -> Tuple[Path, bool]:
    """One file per configuration, no date in the name. Returns (path, wrote).

    THE CONFIGURATION IS THE SCOPE SCANNED. A whole-tree scan is `detect.json`; a single box
    is `detect-<box>.json`. They are different measurements and must never share a filename,
    for the reason the README gives about a hinted and an unhinted T1 run — whichever ran last
    would silently become "the" committed score, and a one-box scan is the run somebody makes
    on the way to a question, not the run that stands for the rig.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{scope}" if scope else ""
    path = RESULTS_DIR / f"detect{suffix}.json"

    if path.exists():
        try:
            existing = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            existing = None  # unreadable or corrupt: overwrite it, that IS a change
        if isinstance(existing, dict) and _same_measurement(existing, payload):
            return path, False

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")
    return path, True


def _walk(root: Path, only: Optional[str], limit: Optional[int]) -> Dict[str, List[Photo]]:
    directories = _box_dirs(root)
    if only:
        directories = [path for path in directories if path.name == only]
        if not directories:
            raise SystemExit(f"{root}: no box directory named {only!r}")
    if not directories:
        raise SystemExit(_NO_BOXES.format(root=root, why="holds none"))
    per_box: Dict[str, List[Photo]] = {}
    for directory in directories:
        photos = scan_box(directory, limit)
        per_box[directory.name] = photos
        stats = _summarise(photos)
        rate = stats["crop_refusal_rate"]
        print(
            f"  {directory.name:<8} {stats['photographs']:>5} photographs   "
            f"found {stats['found']:>5}   declined "
            f"{stats['crop_refused']}"
            f"{'' if rate is None else f' ({rate * 100:.1f}%)'}",
            flush=True,
        )
    return per_box


def scan(root: Path, only: Optional[str], limit: Optional[int], write: bool) -> None:
    # Refused before the scan rather than after it: the work is the expensive part, and a
    # report printed and then disowned is the shape of answer nobody reads to the end.
    if write and limit is not None:
        raise SystemExit(
            "--limit truncates the scan, so what it produces is not a measurement of "
            "anything a later run could be compared against. Drop --limit to write."
        )
    print(f"{root}   detector {_fingerprint()}   "
          f"area {images.SMALL_CROP_AREA} / detail {images.MIN_CROP_DETAIL} / pad {images.CROP_PAD}")
    per_box = _walk(root, only, limit)
    print()
    for name, photos in sorted(per_box.items()):
        _print_block(name, _summarise(photos))
    every = [photo for photos in per_box.values() for photo in photos]
    if len(per_box) > 1:
        _print_block("ALL", _summarise(every))

    named = [p for p in every if p.refusal is not None]
    if named:
        print("declined crops, by name — these are the frames to look at, not a wrongness list:")
        for photo in named:
            print(f"  {photo.name:<14} area {photo.area:.3f}  detail {photo.detail:.3f}")
        print()

    if not write:
        return
    payload = _payload(root, per_box)
    path, wrote = _write_results(payload, _scope(root, per_box, only))
    print(f"{path.relative_to(ROOT)}  {'written' if wrote else 'unchanged, left alone'}")


def sweep(root: Path, only: Optional[str], limit: Optional[int]) -> None:
    """What other (area, detail) pairs would have declined, over one scan.

    THE OUTPUT IS NOT A SCORE AND THE GRID HAS NO WINNER. Without an answer key a pair that
    declines fewer crops is not better than one that declines more — it is only looser. What
    the grid shows is where the population is piled: a line that moves a long way and changes
    nothing sits in a gap, and one where a step of 0.05 moves dozens of frames is a line
    sitting in the middle of the distribution it is supposed to be separating.
    """
    print(f"{root}   detector {_fingerprint()}")
    per_box = _walk(root, only, limit)
    measured = [
        photo
        for photos in per_box.values()
        for photo in photos
        if photo.outcome == FOUND and photo.area is not None
    ]
    print()
    if not measured:
        print("nothing to sweep: no box was returned for any photograph.")
        return
    print(f"of {len(measured)} crops, how many each pair would decline — LOOSER IS NOT BETTER")
    print(" " * 13 + "".join(f"detail {d:.2f}  " for d in DETAIL_GRID))
    for area_line in AREA_GRID:
        cells = []
        for detail_line in DETAIL_GRID:
            declined = sum(
                1 for p in measured if p.area < area_line and p.detail < detail_line
            )
            cells.append(f"{declined:>6}       ")
        live = "  <- live area line" if area_line == images.SMALL_CROP_AREA else ""
        print(f"  area {area_line:.2f}  " + "".join(cells) + live)
    print(f"\n  the live pair is area {images.SMALL_CROP_AREA} / detail {images.MIN_CROP_DETAIL}.")


def _flag(argv: List[str], name: str) -> Tuple[List[str], Optional[str]]:
    """`--name value`, removed from argv. Returns (rest, value)."""
    if name not in argv:
        return argv, None
    at = argv.index(name)
    if at + 1 >= len(argv):
        raise SystemExit(f"{name} takes a value")
    return argv[:at] + argv[at + 2:], argv[at + 1]


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    command, rest = argv[1], list(argv[2:])
    write = "--write" in rest
    rest = [item for item in rest if item != "--write"]
    rest, only = _flag(rest, "--box")
    rest, limit_text = _flag(rest, "--limit")
    limit = int(limit_text) if limit_text is not None else None
    if len(rest) > 1:
        raise SystemExit("one captures directory at a time")
    root = Path(rest[0]).expanduser().resolve() if rest else (files.home() / "captures")

    if command == "scan":
        scan(root, only, limit, write)
    elif command == "sweep":
        sweep(root, only, limit)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
