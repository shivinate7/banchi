"""Cut the crop-retry regions out of a registered card.

Three regions, and the reason there are three:

  card    the whole card, deskewed and with the mat cut away. The retry's baseline — even
          without a band, removing the background and the rotation is worth something.
  title   the top band. Where the name is, and a name misread is one of the two failure
          modes the retry exists for.
  number  the bottom band, FULL WIDTH. The collector number is bottom-left on SV-era cards
          and bottom-right on some older ones, and a band that covers both costs a few
          hundred tokens while a band that guesses wrong costs the whole retry.

Bands are fractions of the registered card, not pixel offsets, so they follow the card
whatever resolution it was shot at. They are deliberately loose: the point of registering
the card first is that a loose band is now anchored to the card rather than to the frame.

Crops are UPSCALED to `MIN_REGION_EDGE` when they come out smaller. That is the whole
argument for crop retry — a `025` rendered 40px wide is a coin flip, and the same digits at
600px are not — so a band that came out small is exactly the band that needed enlarging.
"""

from __future__ import annotations

from typing import Dict, Optional

from geometry.detect import CardBox, GeometryError, open_image

try:
    from PIL import Image
except ImportError:  # pragma: no cover - environment problem, not logic
    Image = None

REGION_CARD = "card"
REGION_TITLE = "title"
REGION_NUMBER = "number"

# (left, top, right, bottom) as fractions of the registered card.
TITLE_BAND = (0.0, 0.0, 1.0, 0.20)
NUMBER_BAND = (0.0, 0.82, 1.0, 1.0)

BANDS = {
    REGION_TITLE: TITLE_BAND,
    REGION_NUMBER: NUMBER_BAND,
}

# Below this, a band is upscaled — the digits are the point.
MIN_REGION_EDGE = 600
# And never past this, because a band larger than the API's own cap is billed and discarded.
MAX_REGION_EDGE = 1568


def _upscale(image):
    longest = max(image.size)
    if longest >= MIN_REGION_EDGE:
        return image
    scale = min(MIN_REGION_EDGE, MAX_REGION_EDGE) / float(longest)
    size = (
        max(1, int(round(image.size[0] * scale))),
        max(1, int(round(image.size[1] * scale))),
    )
    return image.resize(size, Image.LANCZOS)


def registered_card(source, box: CardBox):
    """The card alone: rotated upright, mat cut away, portrait."""
    if Image is None:  # pragma: no cover - environment problem
        raise GeometryError("cropping needs Pillow — run `make venv`")

    image = open_image(source)
    rotated = image.rotate(box.angle, resample=Image.BICUBIC, expand=True)
    width, height = rotated.size
    card = rotated.crop(
        (
            int(round(box.left * width)),
            int(round(box.top * height)),
            int(round(box.right * width)),
            int(round(box.bottom * height)),
        )
    )
    # A card lying on its side passes the aspect gate — the gate compares short to long
    # edge — so straighten it here rather than cutting a "title band" across the artwork.
    if card.size[0] > card.size[1]:
        card = card.rotate(90, expand=True)
    return card


def crop_regions(source, box: Optional[CardBox]) -> Dict[str, object]:
    """The regions to attach to a crop retry, or `{}` when there is no card.

    An empty mapping is the caller's signal to skip the retry entirely and send the card to
    the main review queue (v2 §4.5 rung 3) — never to retry with the raw frame, which is
    the picture that already failed.
    """
    if box is None:
        return {}

    card = registered_card(source, box)
    regions = {REGION_CARD: _upscale(card)}

    width, height = card.size
    for name, (left, top, right, bottom) in BANDS.items():
        band = card.crop(
            (
                int(round(left * width)),
                int(round(top * height)),
                int(round(right * width)),
                int(round(bottom * height)),
            )
        )
        if band.size[0] > 0 and band.size[1] > 0:
            regions[name] = _upscale(band)
    return regions
