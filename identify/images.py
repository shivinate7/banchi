"""Preparing a photograph for the API: downscale, encode, hash.

DOWNSCALE TO 1568px ON THE LONGEST EDGE. Anything larger is billed and then discarded by
the API — the image is resized server-side regardless, so sending a 4000px photo buys
nothing and pays for it. `--max-edge` moves the number for anyone who wants to measure
whether it matters.

ORIGINALS ARE NEVER MODIFIED. Everything here reads. The review queue shows the original
photo, and a crop retry re-reads it from disk, so an in-place "optimisation" would degrade
the two paths that exist to recover from a bad read.

RE-ENCODE ONLY WHEN THERE IS A REASON TO. A photo already inside the cap goes to the API as
the exact bytes on disk: no re-encode, no generation loss, no CPU. Only a resize (or a
format the API does not take) costs an encode.

The sha256 is of the ORIGINAL file, not of what was sent. It is the cache's staleness check
— "is this still the same photograph?" — and hashing the downscale would make the answer
depend on `--max-edge`, so changing that flag would silently invalidate every cached answer
in the box.
"""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from typing import Optional

import geometry

try:  # reported as a message at call time, not as a traceback at import
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - environment problem, not logic
    np = None
    Image = None

MAX_EDGE = 1568

# HOW MUCH OF THE DETECTED CARD'S OWN SIZE TO KEEP AROUND IT, per side. The owner chose this
# looking at the rendered boxes over five real frames — the detected edge alone read as too
# tight to trust, and this is the margin that made it read as safe.
#
# It is a fraction of the CARD, not of the frame, so it scales with however large the card
# happens to sit in shot. Measured over all 544 box-2 frames: mean card area 56% of frame,
# so a 4% pad sends ~65% and saves ~35% of the image tokens — and the card lands on roughly
# twice the pixels it would have at the same `MAX_EDGE`, which is the half that matters.
# T1's recorded misses are confident digit misreads, and a collector number is the first
# thing to die in a downscale.
#
# Clamped to the frame, so a pad that would run off the edge is simply cut short. The card
# is never cut: the pad only ever adds.
# RAISED FROM 4% TO 8% ON EVIDENCE, 2026-08-23. The aspect correction below fixes a
# PROPORTIONAL error; it cannot fix a box that is also OFFSET. Crawdaunt at 2/15 is the case
# that proved the difference: its box came back at aspect 0.745 — only mildly short, so the
# correction added just 4% — and its collector number was still clipped, because the box was
# shifted up as well as squashed. Swept on that worst case: `085/132` is cut at 4%, whole at
# 6%, and has real margin at 8%.
#
# Chosen at 8% rather than 6% because 6% was the point where it merely fit. A margin that is
# exactly sufficient on the worst frame measured is not a margin.
CROP_PAD = 0.08

JPEG_QUALITY = 90

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
# What we produce when a re-encode is needed. JPEG: these are photographs, and a lossless
# format on a photograph is a payload three times the size for no legibility gain.
ENCODED_MEDIA_TYPE = "image/jpeg"


class ImageError(RuntimeError):
    """The photograph could not be read or prepared."""


@dataclass(frozen=True)
class Prepared:
    """One image, ready to attach to a batch request."""

    data: bytes
    media_type: str
    sha256: str  # of the ORIGINAL file
    original_size: tuple
    sent_size: tuple
    resized: bool
    # WHY THIS IMAGE WAS NOT CROPPED although a crop was asked for and a card WAS found —
    # `crop_refusal`'s sentence, or None. Carried rather than logged because two screens and
    # the preflight all have to say it: a run that silently sent whole frames would report
    # itself as having cropped, and the operator's only evidence would be the bill.
    crop_refused: Optional[str] = None

    @property
    def data_b64(self) -> str:
        return base64.standard_b64encode(self.data).decode("ascii")

    @property
    def payload_bytes(self) -> int:
        # base64 is 4 bytes per 3, which is what actually counts against the batch cap.
        return (len(self.data) + 2) // 3 * 4


def _require():
    if Image is None:  # pragma: no cover - environment problem
        raise ImageError("image handling needs Pillow — run `make venv`")


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode(image, quality: int = JPEG_QUALITY) -> bytes:
    _require()
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def downscale(image, max_edge: int = MAX_EDGE):
    """Fit the longest edge, preserving aspect. Never upscales."""
    _require()
    longest = max(image.size)
    if longest <= max_edge:
        return image, False
    scale = max_edge / float(longest)
    size = (
        max(1, int(round(image.size[0] * scale))),
        max(1, int(round(image.size[1] * scale))),
    )
    return image.resize(size, Image.LANCZOS), True


def card_rect(size, box, aspect: float = geometry.CARD_ASPECT):
    """WHERE THE CARD IS in a frame of `size`: corrected, UNPADDED, and in float pixels.

    THE PAD WAS A FLAT GUESS AND IT CUT COLLECTOR NUMBERS OFF. Box 2's first run sent 544
    cards cropped at a flat 4%: 38 came back with NO number at all, and a further handful
    came back with the wrong one — `0342`, `0326`, `0934`, which are NATIONAL POKEDEX
    numbers read off the artwork strip once the real collector number had been cropped
    away. A blank is recoverable by the name fallback; a confident wrong number is the
    failure D23 says no confidence threshold catches.

    The cause is measurable and was sitting in the detector's own output the whole time. A
    card is `CARD_ASPECT` — 63/88, 0.716 — and the detected boxes came back at a MEDIAN of
    0.790, with the failures at 0.801 and the worst at 0.822. The box is systematically too
    SHORT for its width, because the border search locks onto the artwork's strong inner
    edges more readily than the card's own bottom border. A flat margin cannot fix a
    proportional error: 92% of the cards that DID keep their number had the same distortion
    and merely landed on the right side of it.

    SO THE CORRECTION IS COMPUTED, NOT GUESSED. If the box is short for its width, restore
    the height a real card of that width would have. The pad is then a genuine safety
    margin on a box that is already the right shape, rather than the only thing standing
    between the crop and the number.

    Applied symmetrically. The observed deficit sits at the bottom — the number end — but
    `CardBox` reports no per-edge confidence, so attributing the whole correction downward
    would be inventing a fact. Symmetric costs a few pixels at the top and cannot be wrong
    about which edge was short.

    ONLY EVER GROWS. A box already taller than its width implies is left alone: that is a
    box with room to spare, and narrowing it would be this defect in the other direction.

    UNPADDED AND UNROUNDED ON PURPOSE, which is what makes it worth its own name. The pad
    is a safety margin on the CUT (`crop_rect`), not a statement about where the cardboard
    is — and the second caller wants the cardboard: the run panel's preview measures the
    number band off this rectangle, and measuring it off the padded one would put the band
    a few percent low on every card. Rounding belongs at the cut for the same reason.
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


def crop_rect(
    size, box, pad: float = CROP_PAD, aspect: float = geometry.CARD_ASPECT
):
    """THE PIXELS `card_crop` CUTS, as a plain `(left, top, right, bottom)`.

    SEPARATE FROM THE CUT SO THAT NOTHING HAS TO RE-DERIVE IT. `#/runs` draws this
    rectangle over the photograph before a run is paid for, and a preview carrying its own
    copy of this arithmetic is a preview that can reassure you about a crop it is not
    describing — which is precisely the failure `card_rect`'s correction was written for.
    One computation, two callers: the same rule `server/pipeline_routes.py:_parse_preflight`
    follows when it lifts the preflight's figures out of stdout rather than recomputing
    them, and for the same reason — a second implementation is a number that can disagree
    with the one it claims to describe, with no way to tell which drifted.

    Clamped to the frame, so the rectangle is always drawable and always the real cut: a
    card near an edge pads into nothing rather than off the picture.
    """
    width, height = size
    left, top, right, bottom = card_rect(size, box, aspect)
    box_w, box_h = right - left, bottom - top
    pad_x, pad_y = box_w * pad, box_h * pad
    return (
        max(0, int(left - pad_x)),
        max(0, int(top - pad_y)),
        min(width, int(right + pad_x)),
        min(height, int(bottom + pad_y)),
    )


# ------------------------------------------------- IS THE DETECTED BOX ACTUALLY THE CARD?
#
# `geometry.detect_card` answers "not found" honestly and it has no way to answer "found the
# wrong thing". On the real rig it sometimes locks onto a rectangle INSIDE the card — the
# rules-text panel, the artwork frame — and returns it with a card's aspect, a passing border
# score and no sign of trouble. Cropping to that sends a sliver of the card with the collector
# number outside it, which is the box-2 failure `card_rect` was written for arriving by a
# different road: a confident wrong number, the one thing D23 says no threshold catches.
#
# MEASURED 2026-08-31 over all 867 photographs in the owner's three real boxes — box 1 (133
# Riftbound), box 2 (543 Pokemon), box 3 (191 Riftbound). `detect_card` returned a box for
# every one of them and refused none. NINE were confirmed wrong by eye, all in box 3, and on
# the PADDED rectangle that is actually cut the two populations read:
#
#                             area of the frame            detail the crop keeps
#     858 correct              0.300 - 0.988                   0.438 - 0.995
#       9 wrong                0.068 - 0.270                   0.152 - 0.435
#
# NEITHER COLUMN IS SAFE ON ITS OWN, and that is why this is two measurements rather than one
# constant. On area the gap is 0.270 to 0.300 — and box 1's smallest correct crop sits exactly
# on 0.300, because box 1 is shot further back and its correct crops are genuinely small. On
# detail the gap is 0.435 to 0.438, which is under a percent. A threshold in either gap on its
# own is a number fitted to one rig, not a margin.
#
# So the rule is an AND, and each leg covers the other's boundary: a crop under 30% of the
# frame has to justify itself by keeping at least half the frame's detail. Over the measured
# set that refuses all 9 wrong crops and none of the 858 correct ones. The legs are doing
# separate work — 27 correct crops (box 1, area 0.300-0.362) fall under the DETAIL line and
# are kept by the area leg, while every wrong crop is under BOTH.
#
# ERRING TOWARD REFUSAL IS THE CHEAP DIRECTION, which is what lets a threshold sit on a
# boundary at all. A refusal sends the whole frame: more image tokens, the reading the run
# made before `--crop` existed, and a correct answer. A false accept sends a picture with the
# collector number cut out of it and gets a confident answer about nothing.
#
# ONE RIG, ONE DAY, 867 FRAMES — read this the way docs/GATES.md says to read T6's green.
# What is established is that these two numbers separate these two populations; what is not
# is a rate at which detection goes wrong.

# A CROP SMALLER THAN THIS HAS TO JUSTIFY ITSELF. Above it, nothing is asked: a crop that is
# most of the frame cannot be a rectangle inside the card.
SMALL_CROP_AREA = 0.30

# And this is how it justifies itself — the share of the frame's detail it keeps.
MIN_CROP_DETAIL = 0.50

# A PLAIN FLOOR WAS TRIED HERE AND TAKEN OUT AGAIN, which is worth the four lines. "Refuse any
# crop under 10% of the frame, whatever else is true" is the obvious guard and it is the one a
# person reaches for first. Over the measured set it catches nothing the rule above does not —
# every one of the nine is under BOTH lines — and it has a case where it is simply wrong: T6's
# own `_scene(scale=0.55)` is a small card correctly found on a plain mat, 8% of the frame and
# keeping 94% of its detail, and a floor refuses it. A second rule that adds no catch and
# subtracts a correct crop is not redundancy.

# The detail measure runs here. It is a ratio of sums over the whole frame, so it is stable
# under the resize, and 256px keeps the whole guard at ~25ms a frame.
DETAIL_EDGE = 256


def detail_share(image, rect) -> float:
    """Of all the DETAIL in the frame, the share `rect` keeps. In [0, 1].

    Detail is the summed absolute luminance gradient — the measure that already answers
    "where is the structure in this picture", and the one `geometry/detect.py`'s border
    search is built on, so the guard and the detector are reading the same signal.

    WHY THIS IS THE SECOND AXIS AND NOT, SAY, A TIGHTER ASPECT GATE. The failure being caught
    is a rectangle cut out of the middle of the card, and the thing that is unmistakably true
    of it is that the rest of the card is still outside the crop — sharp, structured, and
    thrown away. A crop of the subject keeps the subject. A crop that discards more than half
    of everything the photograph has to say is a crop of a piece of something.

    It is a RATIO, so it needs no calibration to the rig: a dark backdrop, a bright desk and a
    busy tray all cancel out of the numerator and the denominator together.
    """
    _require()
    if np is None:  # pragma: no cover - environment problem
        raise ImageError("the crop guard needs numpy — run `make venv`")
    gray = image.convert("L")
    scale = DETAIL_EDGE / float(max(gray.size))
    if scale < 1.0:
        gray = gray.resize(
            (max(1, int(gray.width * scale)), max(1, int(gray.height * scale))),
            Image.BILINEAR,
        )
    array = np.asarray(gray, dtype=np.float32)
    if array.shape[0] < 2 or array.shape[1] < 2:
        return 0.0
    dx = np.abs(np.diff(array, axis=1))
    dy = np.abs(np.diff(array, axis=0))
    energy = np.zeros_like(array)
    # Each difference belongs to both pixels it was taken between, so a gradient on the crop's
    # own boundary is not silently assigned to the side that happens to be outside it.
    energy[:, :-1] += dx
    energy[:, 1:] += dx
    energy[:-1, :] += dy
    energy[1:, :] += dy
    total = float(energy.sum())
    if total <= 0:
        # A frame with no gradient anywhere has no detail to lose. Nothing about it is
        # evidence against the crop, so the guard is told it passed rather than failed —
        # a blank photograph is a photograph problem, not a detection problem.
        return 1.0
    width, height = image.size
    rows, columns = array.shape
    x0 = max(0, min(columns, int(round(rect[0] / float(width) * columns))))
    x1 = max(x0, min(columns, int(round(rect[2] / float(width) * columns))))
    y0 = max(0, min(rows, int(round(rect[1] / float(height) * rows))))
    y1 = max(y0, min(rows, int(round(rect[3] / float(height) * rows))))
    return float(energy[y0:y1, x0:x1].sum()) / total


def crop_refusal(
    image, box, pad: float = CROP_PAD, aspect: float = geometry.CARD_ASPECT
) -> Optional[str]:
    """Why this box must NOT be cropped to, or None to go ahead. See the block above.

    A SENTENCE RATHER THAN A BOOLEAN, because every caller has to say this out loud. The
    preflight prints it before any money is spent, the run panel's preview draws no rectangle
    and shows it instead, and a crop retry that refuses here sends the card to a human. A
    silent fallback to the whole frame would be the run quietly not doing what the operator
    asked for, which is the one thing `--crop`'s own preflight line exists to prevent.

    `image` is an open image or a path. The path form is for the crop-retry path, which holds
    a filename rather than a frame — and having it open the file here keeps PIL inside this
    module, where the rest of the repo's image handling already lives.
    """
    _require()
    if not isinstance(image, Image.Image):
        try:
            with Image.open(image) as opened:
                opened.load()
                return crop_refusal(opened, box, pad, aspect)
        except Exception as exc:
            raise ImageError(f"{image}: {exc}") from exc
    width, height = image.size
    if width <= 0 or height <= 0:
        return "the frame has no pixels"
    left, top, right, bottom = crop_rect(image.size, box, pad, aspect)
    area = ((right - left) * (bottom - top)) / float(width * height)
    if area >= SMALL_CROP_AREA:
        return None
    kept = detail_share(image, (left, top, right, bottom))
    if kept < MIN_CROP_DETAIL:
        return (
            f"the crop is {area * 100:.0f}% of the frame and keeps only {kept * 100:.0f}% of "
            f"its detail, so most of what the photograph has to show is outside it — that is "
            f"a crop of part of the card, not of the card. Sent whole."
        )
    return None


def card_crop(image, box, pad: float = CROP_PAD, aspect: float = geometry.CARD_ASPECT):
    """The detected card plus `pad`, clamped to the frame. `box` is a `geometry.CardBox`.

    IN MEMORY, NEVER ON DISK, and that placement is the whole safety argument. A crop
    written at capture time would be irreversible by the time anyone noticed — the card is
    back in the box — whereas a wrong crop here costs one re-run of a free local step. It is
    the same reasoning D10 uses to allow capture-undo without a dialog, read the other way:
    undo is safe *because* the card is still in your hand, and at identify time it is not.

    Every other consumer keeps the full frame: the review queue photograph a human judges
    foil against, the pull preview matched to a physical slot, the re-shoot comparison. Only
    the bytes headed for the model are narrowed.

    THE RECTANGLE IS `crop_rect`'s, not this function's — see there for why the arithmetic
    lives one call away from the only line that uses it here.
    """
    return image.crop(crop_rect(image.size, box, pad, aspect))


def prepare(path, max_edge: int = MAX_EDGE, crop_box=None) -> Prepared:
    """Read a photo from disk and return exactly what should be sent for it.

    `crop_box` is an optional detected card. WHEN IT IS PASSED THE VERBATIM PATH BELOW
    CANNOT BE TAKEN — the bytes on disk are no longer what should be sent — which is why the
    crop happens before the `resized` test rather than after it.

    UNLESS `crop_refusal` REFUSES THE BOX, in which case the whole frame is what should be
    sent and the reason travels back on `Prepared.crop_refused`. The guard is applied HERE, at
    the one place the bytes are made, so nothing downstream can hold a box this function
    declined and cut with it anyway.
    """
    _require()
    path = Path(path)
    suffix = path.suffix.lower()
    digest = sha256_of(path)

    try:
        with Image.open(path) as opened:
            opened.load()
            original_size = opened.size
            refused = None
            if crop_box is not None:
                refused = crop_refusal(opened, crop_box)
                if refused is not None:
                    crop_box = None
                else:
                    opened = card_crop(opened, crop_box)
            scaled, resized = downscale(opened, max_edge)
            if crop_box is not None:
                # Re-encode ALWAYS. A cropped image that happened to land inside the cap is
                # still not the file on disk, and returning `path.read_bytes()` for it would
                # send the whole frame while every counter said it had been cropped.
                return Prepared(
                    data=encode(scaled),
                    media_type=ENCODED_MEDIA_TYPE,
                    sha256=digest,
                    original_size=original_size,
                    sent_size=scaled.size,
                    resized=True,
                )
            if not resized and suffix in MEDIA_TYPES:
                # Already inside the cap and in a format the API takes: send it verbatim.
                return Prepared(
                    data=path.read_bytes(),
                    media_type=MEDIA_TYPES[suffix],
                    sha256=digest,
                    original_size=original_size,
                    sent_size=original_size,
                    resized=False,
                    crop_refused=refused,
                )
            data = encode(scaled)
            return Prepared(
                data=data,
                media_type=ENCODED_MEDIA_TYPE,
                sha256=digest,
                original_size=original_size,
                sent_size=scaled.size,
                resized=resized,
                crop_refused=refused,
            )
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"{path}: {exc}") from exc


def prepare_region(image, max_edge: int = MAX_EDGE) -> Prepared:
    """A crop (already a PIL image) packaged the same way. No file, so no original hash."""
    _require()
    scaled, resized = downscale(image, max_edge)
    data = encode(scaled)
    return Prepared(
        data=data,
        media_type=ENCODED_MEDIA_TYPE,
        sha256="",
        original_size=image.size,
        sent_size=scaled.size,
        resized=resized,
    )


def media_type_for(path) -> Optional[str]:
    return MEDIA_TYPES.get(Path(path).suffix.lower())
