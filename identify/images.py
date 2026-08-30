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
    from PIL import Image
except ImportError:  # pragma: no cover - environment problem, not logic
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
    """
    _require()
    path = Path(path)
    suffix = path.suffix.lower()
    digest = sha256_of(path)

    try:
        with Image.open(path) as opened:
            opened.load()
            original_size = opened.size
            if crop_box is not None:
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
                )
            data = encode(scaled)
            return Prepared(
                data=data,
                media_type=ENCODED_MEDIA_TYPE,
                sha256=digest,
                original_size=original_size,
                sent_size=scaled.size,
                resized=resized,
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
