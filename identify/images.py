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
CROP_PAD = 0.04

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


def card_crop(image, box, pad: float = CROP_PAD):
    """The detected card plus `pad`, clamped to the frame. `box` is a `geometry.CardBox`.

    IN MEMORY, NEVER ON DISK, and that placement is the whole safety argument. A crop
    written at capture time would be irreversible by the time anyone noticed — the card is
    back in the box — whereas a wrong crop here costs one re-run of a free local step. It is
    the same reasoning D10 uses to allow capture-undo without a dialog, read the other way:
    undo is safe *because* the card is still in your hand, and at identify time it is not.

    Every other consumer keeps the full frame: the review queue photograph a human judges
    foil against, the pull preview matched to a physical slot, the re-shoot comparison. Only
    the bytes headed for the model are narrowed.
    """
    width, height = image.size
    left, top = box.left * width, box.top * height
    right, bottom = box.right * width, box.bottom * height
    pad_x, pad_y = (right - left) * pad, (bottom - top) * pad
    return image.crop((
        max(0, int(left - pad_x)),
        max(0, int(top - pad_y)),
        min(width, int(right + pad_x)),
        min(height, int(bottom + pad_y)),
    ))


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
