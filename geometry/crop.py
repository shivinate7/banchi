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

from typing import Dict, Optional, Sequence

from geometry.detect import CardBox, GeometryError, open_image

# THE ONE EDGE FROM `geometry/` INTO `pipeline/`, and it costs nothing: `pipeline/games.py`
# imports `typing` and nothing else from this repo, by the rule D22 puts on it so the docs
# audit can read it with `ast`. Importing it here buys the import-time reconciliation below —
# a band name in the registry that this module cannot cut fails at import, next to the
# mismatch, rather than at whichever retry first reaches for it.
from pipeline import games

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

# ------------------------------------------------------------------ per-game dispatch
#
# `pipeline/games.py` says WHICH bands a game claims, by name — `("title", "number")` for
# `pokemon`, `()` for `pokemon_code`, whose card has neither of those things in those places.
# It cannot hold the rectangles, because the registry must stay `ast.literal_eval`-safe (D22)
# and a fraction tuple there would be a second copy of the two below. So the registry names
# bands and this module knows where they are.
#
# A PROFILE IS A SELECTION OF BANDS, and a game's `crop_bands` field IS that selection. There
# is deliberately no per-game rectangle here: a card is 63x88mm whatever is printed on it
# (`card_aspect` says so on every entry), so the bands are properties of the cardboard and
# the only per-game question is which of them are worth cutting.
BAND_PROFILES: Dict[str, tuple] = {
    REGION_TITLE: TITLE_BAND,
    REGION_NUMBER: NUMBER_BAND,
}

# Every band name the registry knows about has to be a band this module can cut, checked at
# import for the same reason `pipeline/variant.py` reconciles its finish enum there: a name
# added to `CROP_BAND_NAMES` with no rectangle here would produce a retry that quietly
# attached one fewer image than it said it would. The reverse — a rectangle here that no
# registry name mentions — is not checked and must not be: `REGION_CARD` is not a band at
# all, and a band authored ahead of the game that will claim it is ordinary.
_uncuttable = [name for name in games.CROP_BAND_NAMES if name not in BAND_PROFILES]
if _uncuttable:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "geometry/crop.py:BAND_PROFILES cannot cut "
        + ", ".join(repr(name) for name in _uncuttable)
        + ", which pipeline/games.py lists in CROP_BAND_NAMES. Give the band a rectangle "
        "here, or take the name out of the registry — a band nothing can cut is a band an "
        "entry can claim and never get."
    )

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


def crop_regions(
    source, box: Optional[CardBox], bands: Optional[Sequence[str]] = None
) -> Dict[str, object]:
    """The regions to attach to a crop retry, or `{}` when there is no card.

    An empty mapping is the caller's signal to skip the retry entirely and send the card to
    the main review queue (v2 §4.5 rung 3) — never to retry with the raw frame, which is
    the picture that already failed.

    `bands` is a game's `crop_bands` field: which of `BAND_PROFILES` to cut. NONE MEANS ALL
    OF THEM, which is what every caller passes today and is byte-identical to the behaviour
    before the registry existed — the `pokemon` entry claims both bands, so a Pokemon card
    was never going to get a different answer. An EMPTY sequence is a different thing and
    means what it says: `pokemon_code` claims no bands, so a code card's retry carries the
    registered card alone. The card is never optional and is not a band; it is the retry's
    baseline, and there is no game for which deskewing and cutting the mat away is wrong.

    A name outside `BAND_PROFILES` refuses rather than being skipped. Silently cutting one
    band where two were asked for is a retry that reports itself as having done more than it
    did, and the caller has no way to tell.
    """
    if box is None:
        return {}

    wanted = tuple(BAND_PROFILES) if bands is None else tuple(bands)
    unknown = [name for name in wanted if name not in BAND_PROFILES]
    if unknown:
        raise GeometryError(
            "no band is defined for "
            + ", ".join(repr(name) for name in unknown)
            + "; BAND_PROFILES cuts "
            + ", ".join(sorted(BAND_PROFILES))
            + ". Check the game's `crop_bands` in pipeline/games.py."
        )

    card = registered_card(source, box)
    regions = {REGION_CARD: _upscale(card)}

    width, height = card.size
    for name in wanted:
        left, top, right, bottom = BAND_PROFILES[name]
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
