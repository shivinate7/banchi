"""Card-boundary detection: where is the card, and how far is it rotated.

The method, and why each step is the cheap one:

  1. BACKGROUND FROM THE BORDER RING. The outer few percent of a rig photo is the mat, not
     the card. Its median is the background level and its spread is the noise level, both
     measured from the image in hand rather than assumed — a rig that gets re-lit does not
     need a new constant here.

  2. THRESHOLD ON DISTANCE FROM BACKGROUND, not on brightness. A card can be lighter or
     darker than the mat, and a black-bordered card on a black mat is the case a brightness
     threshold silently gets backwards.

  3. BRUTE-FORCE THE ROTATION. Rotate the mask, take the axis-aligned bounding box, keep the
     angle whose box is smallest — that is the minimum-area rectangle, computed by trying
     rather than by deriving it. Coarse pass then a fine pass around the winner: ~30
     rotations of a 512px mask, milliseconds, and no geometry to get subtly wrong.

  4. EDGES FROM PROJECTION PROFILES. Once the card is upright its row and column sums are
     plateaus, so the edges are wherever the profile crosses half its peak. Robust to a
     speck of dust in a way that "first non-zero pixel" is not.

  5. REFUSE ON SHAPE. Area fraction, fill ratio and aspect are checked against a real card
     (63x88mm, 0.716). Something that is the wrong shape is not a card that was found
     badly — it is not a card, and saying so is the whole value of this step.

     THE ASPECT IS THE GAME'S, PASSED IN, and only the default is this module's constant.
     `pipeline/games.py:card_aspect` is the per-game statement of the same physical fact,
     and it is `None` on the one entry that spans games printed at two different sizes.
     A `None` aspect REFUSES — see `UnknownCardShape` — because this step is precisely
     what separates "a card is here" from "a rectangle is here", and a detector that
     skips it is the guess this module's contract forbids.

Coordinates come back NORMALISED, as fractions of the rotated-and-expanded canvas, so
detection can run on a 512px working copy while the crops are taken from the full-resolution
original. Both sides call the same PIL rotate with the same arguments, so they agree by
construction instead of by a scale factor someone has to keep correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

try:  # reported as a message at call time, not as a traceback at import
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - environment problem, not logic
    np = None
    Image = None

# Standard TCG card: 63mm x 88mm. Short edge over long edge.
#
# THE DEFAULT, NOT THE ONLY VALUE, as of 2026-08-23. `detect_card` takes an `aspect` and
# every gate below reads the argument rather than this constant; `pipeline/games.py` carries
# the same physical fact per game (`card_aspect`), and `cli/cmd_identify.py` passes it in.
# The default is deliberately this constant and not the registry's `pokemon` value: it keeps
# a bare `detect_card(frame)` — which is every call T6 makes — byte-identical to what it did
# before the parameter existed, so the sweep is the proof that nothing about Pokemon moved.
CARD_ASPECT = 63.0 / 88.0

# Detection runs here; results are normalised, so the full-resolution image never has to.
WORKING_EDGE = 512

# Shape gates. Generous, because the alternative to a slightly-off box is no crop retry at
# all — but not so generous that a hand or a stack edge passes as a card.
MIN_AREA_FRACTION = 0.04
MAX_AREA_FRACTION = 0.99
# Relative, so +/-15% of 0.716 — accepts 0.609 to 0.823. Wide enough for the foreshortening
# a slightly tilted card produces, narrow enough to refuse a rectangle that is simply not a
# card. Erring toward refusal is the cheap direction: a refusal costs a crop retry and sends
# the card to a human, while a false accept crops the wrong region and answers confidently.
ASPECT_TOLERANCE = 0.15
MIN_FILL = 0.70  # of the bounding box actually covered by the mask

# Rotation search. A rig with a feeder is not going to be 30 degrees off; if it is, that is
# a rig finding and a human should see the photo.
MAX_ANGLE = 12.0
COARSE_STEP = 2.0
FINE_STEP = 0.25

# Threshold floor, in 8-bit levels, so an evenly lit mat cannot threshold on its own noise.
MIN_DELTA = 12.0
BORDER_FRACTION = 0.04

# A column or row counts as part of the card if this many pixels of it survived the mask.
# ABSOLUTE, not a fraction of the profile's peak, and that distinction is load-bearing: a
# rotated rectangle's projection is a trapezoid, so a peak-relative cut clips the ramps at
# both ends, and the more the card is rotated the more it clips. The angle search minimises
# bounding-box area, so a peak-relative cut pays it to keep rotating — it runs away to the
# end of the sweep and reports a confident, wrong angle. Measured, not reasoned about.
PROFILE_FLOOR = 2

# --------------------------------------------------------------------------- EDGE SEARCH
#
# The mask path above segments the card by TONE: everything far enough from the border
# ring's median is foreground. That premise is false on the real rig, and Gate B's 53
# photographs are the measurement — `detect_card` found nothing in any of them.
#
# Why, exactly, because the reason decides that this is a second method rather than a
# tuned constant. The card sits in a clear plastic stand on a wood desk with a dark
# backdrop above, and its own artwork spans 88 to 231 against a background near 64. There
# is no threshold in between:
#
#   * at the adaptive threshold (88.5, which the BRIGHT CARD ITSELF sets through the
#     99th-percentile term) 29% of the card's darker artwork is cut out of its own mask,
#     fill lands at 0.21-0.67 and MIN_FILL refuses 52 of 53;
#   * at MIN_DELTA alone, desk grain and the stand's edges are all foreground too, the
#     box grows to the whole frame, and area and aspect refuse all 53.
#
# A planar background fit and a bottom-band background were both measured and both still
# find nothing, so it is not the ring's non-uniformity on its own. T6 cannot catch any of
# this: `_scene` paints one flat colour behind a uniformly bright synthetic card, which is
# precisely the premise the mask path needs.
#
# So this path does not segment at all. It looks for the card's BORDER — four long straight
# luminance edges whose spacing is a card — and assumes nothing about what is behind them.
# It runs only when the mask path has already refused, so every frame the mask path handles
# is unaffected, and T6's synthetic sweep never reaches here.
#
# NARROW ANGLE RANGE ON PURPOSE. The mask path owns rotation; measured on the 53 rig
# photographs the card is upright to a median of 0.00 degrees and a p90 of 0.50. Searching
# +/-12 here would also cost accuracy rather than buy it: rotating with expand=True paints
# fill triangles whose straight boundary is a stronger edge than any card, and the wider the
# sweep the more of the canvas is fill. `_edge_valid_box` excludes it; a narrow sweep keeps
# the excluded area small.
EDGE_MAX_ANGLE = 4.0
EDGE_COARSE_STEP = 1.0
EDGE_FINE_STEP = 0.25

# Peaks per profile. The four card borders have to be in here alongside the stand's edges
# and any second card in frame, and the pair search is O(n^4) in this.
EDGE_PEAKS = 10
EDGE_MIN_SIDE_FRACTION = 0.15

# Of a possible 4.0, the four borders' normalised gradient strength summed.
EDGE_MIN_BORDER = 1.20

# THE GATE THAT DOES THE REAL WORK. A card's side is ONE continuous edge running the whole
# side. A spurious pairing scores well by borrowing gradient from rows the rectangle does
# not span — which is exactly how an earlier draft of this accepted T6's scattered debris,
# its long-and-thin rectangle and an empty frame. This measures the share of each side's
# gradient that actually lies along that side, and all five of T6's refusals turn on it.
EDGE_MIN_SUPPORT = 0.55

# Peaks this close to the canvas edge are ignored: the frame boundary and the rotation fill
# both produce a perfect straight edge that is not a card.
EDGE_BORDER_GUARD = 0.02


class GeometryError(RuntimeError):
    """Detection could not run at all — missing dependency, unreadable image."""


class UnknownCardShape(GeometryError):
    """No aspect ratio was given, so there is no shape to look for. `card_aspect: None`.

    A REFUSAL RATHER THAN A SKIPPED GATE, and the argument is `detect_card`'s own contract:
    "None means a human should look, never guess". Step 5 of this module's method is REFUSE
    ON SHAPE, and it is the step that makes a positive answer mean anything — area and fill
    say "something is there", and only aspect says "and it is a card". A detector run with
    that gate removed accepts the best-scoring rectangle in the frame, which on this rig is
    as likely to be the stand, the desk edge or the next card along. Cropping to it produces
    "a miss indistinguishable from a bad read", which `geometry/__init__.py` names as the one
    outcome the whole package exists to avoid.

    WHY REFUSING IS CHEAP HERE, AND IT IS THE OTHER HALF OF THE ARGUMENT. `card_aspect` is
    None on exactly one registry entry, `misc` — the ~1% of the shelf that is a Magic,
    Yu-Gi-Oh, Weiss Schwarz or foreign-language card. Yu-Gi-Oh is 59x86mm (0.686) where the
    other three are 63x88mm (0.716), so no single number is true of the population and
    picking one would author a measurement nobody took. What a refusal costs is a crop retry
    on a card already being handled by hand. What widening the tolerance to span both would
    cost is the gate itself: 0.686 and 0.716 with +/-15% each is a band from 0.583 to 0.823,
    which admits shapes no card in any of these games is printed at.

    A SUBCLASS OF `GeometryError` SO EXISTING CALLERS ARE UNCHANGED. `cli/cmd_identify.py`
    already catches `GeometryError` around `detect_card`, records `not_found`, prints the
    exception's own message and sends the card to a human with no crop retry — which is
    exactly the handling this case wants. The distinct type is so a run report can tell
    "we could not look" from "we looked and there is no card"; nothing has to catch it
    separately to behave correctly.
    """


@dataclass(frozen=True)
class CardBox:
    """Where the card is, as fractions of the image rotated by `angle` with expand=True.

    `fill` and `aspect` are kept because they are the evidence the shape gates passed on,
    and a run report that says "detected, fill 0.71" is worth more than one that says
    "detected".
    """

    angle: float
    left: float
    top: float
    right: float
    bottom: float
    fill: float
    aspect: float
    # Which path found it. Defaulted, so every existing construction is unchanged.
    # `mask` is the tone-segmentation path below; `edges` is the border search that
    # rescues the frames it cannot segment. Worth carrying because the two have
    # different failure modes and a run report that cannot tell them apart cannot say
    # which one to distrust — see EDGE SEARCH below for why `fill` means something
    # slightly different on each.
    method: str = "mask"

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def describe(self) -> str:
        return (
            "angle {0:+.2f} box ({1:.3f},{2:.3f})-({3:.3f},{4:.3f}) "
            "fill {5:.2f} aspect {6:.3f} via {7}".format(
                self.angle, self.left, self.top, self.right, self.bottom,
                self.fill, self.aspect, self.method,
            )
        )


def _require() -> None:
    if np is None or Image is None:  # pragma: no cover - environment problem
        raise GeometryError(
            "card detection needs Pillow and numpy — run `make venv`"
        )


def open_image(source):
    """A PIL image from a path or an already-open image. Always RGB, always upright."""
    _require()
    if isinstance(source, Image.Image):
        image = source
    else:
        try:
            image = Image.open(source)
        except Exception as exc:
            raise GeometryError("could not read {0}: {1}".format(source, exc)) from exc
    # EXIF orientation is a real source of sideways phone photos, and a sideways card
    # fails the aspect gate for a reason that has nothing to do with the rig.
    try:
        from PIL import ImageOps

        image = ImageOps.exif_transpose(image)
    except Exception:  # pragma: no cover - malformed EXIF is not worth failing on
        pass
    return image.convert("RGB")


def _working_gray(image):
    """Grayscale, scaled so the longest edge is WORKING_EDGE. Aspect preserved."""
    gray = image.convert("L")
    longest = max(gray.size)
    if longest > WORKING_EDGE:
        scale = WORKING_EDGE / float(longest)
        size = (
            max(1, int(round(gray.size[0] * scale))),
            max(1, int(round(gray.size[1] * scale))),
        )
        gray = gray.resize(size, Image.BILINEAR)
    return np.asarray(gray, dtype=np.float32)


def _foreground_mask(gray):
    """True where the pixel is not the background the border ring measured."""
    height, width = gray.shape
    band_y = max(1, int(round(height * BORDER_FRACTION)))
    band_x = max(1, int(round(width * BORDER_FRACTION)))
    border = np.concatenate(
        [
            gray[:band_y, :].ravel(),
            gray[-band_y:, :].ravel(),
            gray[:, :band_x].ravel(),
            gray[:, -band_x:].ravel(),
        ]
    )
    background = float(np.median(border))
    distance = np.abs(gray - background)

    # 99th percentile rather than the max: one dust speck should not set the scale for the
    # whole image. Half of that, floored, is the threshold.
    span = float(np.percentile(distance, 99))
    threshold = max(MIN_DELTA, span * 0.5)
    return distance >= threshold


def _extent(profile) -> Optional[Tuple[int, int]]:
    """Half-open [start, end) of the occupied run in a projection profile."""
    if float(profile.max()) <= 0:
        return None
    hits = np.flatnonzero(profile >= PROFILE_FLOOR)
    if hits.size == 0:
        return None
    return int(hits[0]), int(hits[-1]) + 1


def _rotate_mask(mask, angle: float):
    """Rotate a boolean mask, expanding the canvas so no corner is clipped away."""
    if abs(angle) < 1e-9:
        return mask
    image = Image.fromarray((mask * 255).astype(np.uint8))
    turned = image.rotate(
        angle, resample=Image.NEAREST, expand=True, fillcolor=0
    )
    return np.asarray(turned) > 127


def _box_at(mask, angle: float):
    """(area, x0, y0, x1, y1, canvas_w, canvas_h) for the mask rotated by `angle`."""
    turned = _rotate_mask(mask, angle)
    columns = _extent(turned.sum(axis=0))
    rows = _extent(turned.sum(axis=1))
    if columns is None or rows is None:
        return None
    x0, x1 = columns
    y0, y1 = rows
    area = (x1 - x0) * (y1 - y0)
    if area <= 0:
        return None
    covered = int(turned[y0:y1, x0:x1].sum())
    return area, x0, y0, x1, y1, turned.shape[1], turned.shape[0], covered


def _angles(centre: float, span: float, step: float) -> List[float]:
    count = int(round(span / step))
    return [centre + step * i for i in range(-count, count + 1)]


def _edge_valid_box(shape, angle: float):
    """Rows and columns of the rotated canvas that are real pixels, not rotation fill."""
    height, width = shape
    if abs(angle) < 1e-9:
        return 0, height, 0, width
    solid = Image.fromarray(np.full(shape, 255, np.uint8)).rotate(
        angle, resample=Image.NEAREST, expand=True, fillcolor=0
    )
    kept = np.asarray(solid) > 127
    rows = np.flatnonzero(kept.all(axis=1))
    columns = np.flatnonzero(kept.all(axis=0))
    if rows.size == 0 or columns.size == 0:
        return None
    return int(rows[0]), int(rows[-1]) + 1, int(columns[0]), int(columns[-1]) + 1


def _edge_peaks(profile, count: int, min_sep: int, guard: int) -> List[int]:
    """The strongest `count` separated positions, ignoring the guarded canvas margins."""
    chosen: List[int] = []
    for index in np.argsort(profile)[::-1]:
        index = int(index)
        if profile[index] <= 0:
            break
        if index < guard or index >= len(profile) - guard:
            continue
        if all(abs(index - kept) >= min_sep for kept in chosen):
            chosen.append(index)
            if len(chosen) >= count:
                break
    return sorted(chosen)


def _edge_rect(gray, aspect: float):
    """Best card-shaped rectangle in an upright frame, by its four borders."""
    height, width = gray.shape
    if height < 16 or width < 16:
        return None
    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    columns, rows = dx.sum(axis=0), dy.sum(axis=1)
    if columns.max() <= 0 or rows.max() <= 0:
        return None
    columns = columns / columns.max()
    rows = rows / rows.max()
    xs = _edge_peaks(columns, EDGE_PEAKS, max(3, width // 40),
                     max(2, int(width * EDGE_BORDER_GUARD)))
    ys = _edge_peaks(rows, EDGE_PEAKS, max(3, height // 40),
                     max(2, int(height * EDGE_BORDER_GUARD)))
    best = None
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            x0, x1 = xs[i], xs[j]
            box_w = x1 - x0
            if box_w < width * EDGE_MIN_SIDE_FRACTION:
                continue
            for a in range(len(ys)):
                for b in range(a + 1, len(ys)):
                    y0, y1 = ys[a], ys[b]
                    box_h = y1 - y0
                    if box_h < height * EDGE_MIN_SIDE_FRACTION:
                        continue
                    area_fraction = (box_w * box_h) / float(width * height)
                    if not (MIN_AREA_FRACTION <= area_fraction <= MAX_AREA_FRACTION):
                        continue
                    short, long_ = ((box_w, box_h) if box_w <= box_h else (box_h, box_w))
                    measured = short / float(long_)
                    if abs(measured - aspect) > aspect * ASPECT_TOLERANCE:
                        continue
                    border = columns[x0] + columns[x1] + rows[y0] + rows[y1]
                    if border < EDGE_MIN_BORDER:
                        continue
                    # `shares` are honest fractions in [0, 1]: how much of each side's
                    # gradient really lies along that side. `support` divides by what a
                    # uniform spread would give, so 1.0 means "no better than smeared" and
                    # the gate reads the same whatever the rectangle's size — that ratio is
                    # what refuses T6's debris and its long-and-thin rectangle. The raw
                    # share is what gets reported, because `fill` is documented as a
                    # fraction and a ratio would print above 1.
                    shares = (
                        dx[y0:y1, x0].sum() / (dx[:, x0].sum() + 1e-9),
                        dx[y0:y1, x1].sum() / (dx[:, x1].sum() + 1e-9),
                        dy[y0, x0:x1].sum() / (dy[y0, :].sum() + 1e-9),
                        dy[y1, x0:x1].sum() / (dy[y1, :].sum() + 1e-9),
                    )
                    span = (box_h / float(height), box_h / float(height),
                            box_w / float(width), box_w / float(width))
                    support = min(sh / sp for sh, sp in zip(shares, span))
                    if support < EDGE_MIN_SUPPORT:
                        continue
                    score = border * support * (area_fraction ** 0.5)
                    if best is None or score > best[0]:
                        best = (score, x0, y0, x1, y1, measured, float(min(shares)))
    return best


def _edge_at(image, angle: float, aspect: float):
    """`_edge_rect` on the image rotated by `angle`, normalised to the rotated canvas."""
    turned = image if abs(angle) < 1e-9 else image.rotate(
        angle, resample=Image.BILINEAR, expand=True, fillcolor=0
    )
    canvas = np.asarray(turned, dtype=np.float32)
    valid = _edge_valid_box(np.asarray(image).shape, angle)
    if valid is None:
        return None
    r0, r1, c0, c1 = valid
    found = _edge_rect(canvas[r0:r1, c0:c1], aspect)
    if found is None:
        return None
    score, x0, y0, x1, y1, measured, support = found
    canvas_h, canvas_w = canvas.shape
    return (
        score,
        (x0 + c0) / float(canvas_w),
        (y0 + r0) / float(canvas_h),
        (x1 + c0) / float(canvas_w),
        (y1 + r0) / float(canvas_h),
        measured,
        support,
    )


def _detect_by_edges(image, aspect: float) -> Optional[CardBox]:
    """The rescue path: find the card by its border rather than by its tone.

    Runs only after the mask path refuses. Returns None on anything it cannot justify —
    the same contract, and T6's five refusal cases all reach here and must survive it.

    `fill` carries the border SUPPORT rather than mask coverage, because this path builds
    no mask. Both answer the same question — how much of the box is really the card —
    and `method` on the returned box says which one is being quoted, so a run report
    cannot silently compare the two.
    """
    working = image.convert("L")
    scale = WORKING_EDGE / float(max(working.size))
    working = working.resize(
        (max(1, int(working.width * scale)), max(1, int(working.height * scale)))
    )
    best = None
    best_angle = 0.0
    for angle in _angles(0.0, EDGE_MAX_ANGLE, EDGE_COARSE_STEP):
        found = _edge_at(working, angle, aspect)
        if found is not None and (best is None or found[0] > best[0]):
            best, best_angle = found, angle
    if best is None:
        return None
    for angle in _angles(best_angle, EDGE_COARSE_STEP, EDGE_FINE_STEP):
        if abs(angle) > EDGE_MAX_ANGLE:
            continue
        found = _edge_at(working, angle, aspect)
        if found is not None and found[0] > best[0]:
            best, best_angle = found, angle
    _, left, top, right, bottom, measured, support = best
    return CardBox(
        angle=best_angle,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        fill=support,
        aspect=measured,
        method="edges",
    )


def corrected_bounds(size, box: CardBox, aspect: Optional[float] = CARD_ASPECT):
    """Where the card is in a canvas of `size`: `(left, top, right, bottom)` in float pixels.

    THE BOX AS DETECTED IS SYSTEMATICALLY TOO SHORT FOR ITS WIDTH, and this restores the
    height a real card of that width would have. It lives here rather than beside either
    caller because BOTH crop paths need it and a second copy is a rectangle that can disagree
    with the one it claims to describe, with no way to tell which drifted.

    THE MEASUREMENT, kept in full because it is what makes this arithmetic rather than a
    guess. Box 2's first run sent 544 cards cropped at a flat 4% margin: 38 came back with NO
    collector number at all, and a handful came back with the wrong one — `0342`, `0326`,
    `0934`, which are NATIONAL POKEDEX numbers read off the artwork strip once the real
    collector number had been cropped away. A blank is recoverable by the name fallback; a
    confident wrong number is the failure D23 says no confidence threshold catches. A card is
    `CARD_ASPECT` — 63/88, 0.716 — and the detected boxes came back at a MEDIAN of 0.790,
    with the failures at 0.801 and the worst at 0.822: the border search locks onto the
    artwork's strong inner edges more readily than the card's own bottom border. A flat margin
    cannot fix a proportional error.

    APPLIED SYMMETRICALLY. The observed deficit sits at the bottom — the number end — but
    `CardBox` reports no per-edge confidence, so attributing the whole correction downward
    would be inventing a fact. Symmetric costs a few pixels at the top and cannot be wrong
    about which edge was short.

    ONLY EVER GROWS. A box already taller than its width implies is left alone: that is a box
    with room to spare, and narrowing it would be this defect in the other direction.

    UNPADDED, UNROUNDED AND UNCLAMPED. The pad is a safety margin on a CUT and belongs to
    whoever is cutting; this is a statement about where the cardboard is, and a caller that
    wants the cardboard — the run panel's band preview measures its strip off this — would
    have the strip a few percent low if it read a padded rectangle instead.
    """
    width, height = size
    left, top = box.left * width, box.top * height
    right, bottom = box.right * width, box.bottom * height
    box_w, box_h = right - left, bottom - top

    if aspect and box_h > 0 and (box_w / box_h) > aspect:
        want_h = box_w / aspect
        grow = (want_h - box_h) / 2.0
        top -= grow
        bottom += grow

    return left, top, right, bottom


def detect_card(source, aspect: Optional[float] = CARD_ASPECT) -> Optional[CardBox]:
    """Find the card, or return None. None means "a human should look", never "guess".

    Returns coordinates as fractions of the image rotated by `CardBox.angle` with
    `expand=True` — feed the box straight to `geometry.crop.crop_regions`.

    `aspect` IS THE GAME'S `card_aspect` (D22), short edge over long. It defaults to
    `CARD_ASPECT`, so a one-argument call is exactly what it was before this parameter
    existed and T6's whole sweep is the regression test for that. `cli/cmd_identify.py`
    passes the value off `pipeline/games.py`, which is 0.716 for all four catalogued games —
    the same physical fact this module used to keep only as a constant.

    `aspect=None` REFUSES BY RAISING `UnknownCardShape` and does not look at the image. Its
    docstring carries the argument; the short form is that a shape gate is what makes a
    positive answer mean "card" rather than "rectangle", and this function's whole contract
    is that it never guesses. Raising rather than returning None keeps the two apart: None
    already means "I looked and found nothing", and a caller shown that for a card it never
    examined would go looking at the photograph for a fault that is in the registry.
    """
    _require()
    if aspect is None:
        raise UnknownCardShape(
            "no card aspect was given, so there is no shape to gate on and any rectangle "
            "in the frame would pass. This is `card_aspect: None` in pipeline/games.py — "
            "the `misc` entry, which spans games printed at different sizes. There is "
            "nothing to fix here: the card is captured, located, noted and identified, and "
            "goes to a human without a crop retry."
        )
    if not 0.0 < aspect <= 1.0:
        raise GeometryError(
            f"card aspect {aspect!r} is not a short-over-long ratio in (0, 1]. Check the "
            "game's `card_aspect` in pipeline/games.py — a value above 1 is the ratio "
            "written upside down."
        )

    image = open_image(source)
    gray = _working_gray(image)
    if gray.size == 0:
        return None

    mask = _foreground_mask(gray)
    if not mask.any():
        return _detect_by_edges(image, aspect)

    # Coarse sweep, then a fine sweep around the winner. Minimum bounding-box area is the
    # minimum-area rectangle; brute force beats a derivation nobody will re-check.
    best_angle = 0.0
    best_area = None
    for angle in _angles(0.0, MAX_ANGLE, COARSE_STEP):
        found = _box_at(mask, angle)
        if found is None:
            continue
        if best_area is None or found[0] < best_area:
            best_area, best_angle = found[0], angle

    if best_area is None:
        return _detect_by_edges(image, aspect)

    for angle in _angles(best_angle, COARSE_STEP, FINE_STEP):
        if abs(angle) > MAX_ANGLE:
            continue
        found = _box_at(mask, angle)
        if found is None:
            continue
        if found[0] < best_area:
            best_area, best_angle = found[0], angle

    found = _box_at(mask, best_angle)
    if found is None:
        return _detect_by_edges(image, aspect)
    area, x0, y0, x1, y1, canvas_w, canvas_h, covered = found

    width, height = x1 - x0, y1 - y0
    fill = covered / float(area)
    short, long_ = (width, height) if width <= height else (height, width)
    measured = short / float(long_)

    # Refuse on shape. Measured against the ORIGINAL frame's area, not the expanded canvas,
    # so rotating does not make every card look smaller than it is.
    frame_area = float(gray.shape[0] * gray.shape[1])
    area_fraction = area / frame_area
    # A shape refusal here is not the end of the question, only the end of THIS method's
    # answer to it. Gate B measured the mask path refusing all 53 rig photographs on
    # exactly these gates, so the refusal is handed to the border search rather than
    # returned. The gates themselves are unchanged and still refuse for the mask path.
    if not (MIN_AREA_FRACTION <= area_fraction <= MAX_AREA_FRACTION):
        return _detect_by_edges(image, aspect)
    if fill < MIN_FILL:
        return _detect_by_edges(image, aspect)
    if abs(measured - aspect) > aspect * ASPECT_TOLERANCE:
        return _detect_by_edges(image, aspect)

    return CardBox(
        angle=best_angle,
        left=x0 / float(canvas_w),
        top=y0 / float(canvas_h),
        right=x1 / float(canvas_w),
        bottom=y1 / float(canvas_h),
        fill=fill,
        aspect=measured,
    )
