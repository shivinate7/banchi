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


class GeometryError(RuntimeError):
    """Detection could not run at all — missing dependency, unreadable image."""


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
            "fill {5:.2f} aspect {6:.3f}".format(
                self.angle, self.left, self.top, self.right, self.bottom,
                self.fill, self.aspect,
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


def detect_card(source) -> Optional[CardBox]:
    """Find the card, or return None. None means "a human should look", never "guess".

    Returns coordinates as fractions of the image rotated by `CardBox.angle` with
    `expand=True` — feed the box straight to `geometry.crop.crop_regions`.
    """
    _require()
    image = open_image(source)
    gray = _working_gray(image)
    if gray.size == 0:
        return None

    mask = _foreground_mask(gray)
    if not mask.any():
        return None

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
        return None

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
        return None
    area, x0, y0, x1, y1, canvas_w, canvas_h, covered = found

    width, height = x1 - x0, y1 - y0
    fill = covered / float(area)
    short, long_ = (width, height) if width <= height else (height, width)
    aspect = short / float(long_)

    # Refuse on shape. Measured against the ORIGINAL frame's area, not the expanded canvas,
    # so rotating does not make every card look smaller than it is.
    frame_area = float(gray.shape[0] * gray.shape[1])
    area_fraction = area / frame_area
    if not (MIN_AREA_FRACTION <= area_fraction <= MAX_AREA_FRACTION):
        return None
    if fill < MIN_FILL:
        return None
    if abs(aspect - CARD_ASPECT) > CARD_ASPECT * ASPECT_TOLERANCE:
        return None

    return CardBox(
        angle=best_angle,
        left=x0 / float(canvas_w),
        top=y0 / float(canvas_h),
        right=x1 / float(canvas_w),
        bottom=y1 / float(canvas_h),
        fill=fill,
        aspect=aspect,
    )
