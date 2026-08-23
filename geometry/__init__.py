"""Find the card in the frame, and cut known regions out of it.

Its own package, not a helper inside `identify/`, because the Gate C feeder needs the same
detection: a motion state machine has to know a card is present and settled before it fires
the shutter, and that is this question asked at a different moment.

It runs at BATCH time, not capture time. D1 requires capture to be fast, offline and dumb,
and the capture server does none at capture time — `docs/specs/capture-server.md` §6.6 rules
out "detection, cropping, downscaling or re-encoding at capture time" in as many words, so
nothing looks for the card in the frame while the photograph is being taken. **The step-5 half
of that revisit trigger has fired and been passed**: the server shipped 2026-08-11 and Gate B
pushed 53 captures through it on 2026-08-22 without moving detection forward. D1 was always the
reason; the missing server never was. Gate C is the half still open, for the reason in the
paragraph above.

WHAT THIS IS FOR. Crop retry (v2 §4.5). A `025` rendered 40px wide in a downscaled
full-card image is a coin flip; the same digits cropped and upscaled are not. So a card that
comes back `low` confidence or malformed is re-sent once with cropped regions attached
alongside the full image.

THE BANDS ARE GENEROUS ON PURPOSE. A tight crop of the number corner is a better picture
right up until the card sits two degrees off, at which point the number is outside the frame
and the retry answers confidently about nothing. Generous bands cost a few hundred tokens
and cannot lose the thing they were cut to show.

DETECTION FAILURE IS NOT A CROP FAILURE. If the card cannot be found at all, there is no
crop retry: the card goes straight to the main review queue and is named in the run report.
Cropping blind produces a miss indistinguishable from a bad read, and a systematic rig
problem should show up as a pattern of detection failures rather than as a scatter of wrong
identifications.

Pillow + numpy, not OpenCV. `opencv-python-headless` was the recorded fallback IF measured
detection rates turned out poor. **They were measured on 2026-08-22 and they were poor: 0 of
53 Gate B photographs.** The fallback was still not taken, because opencv would not have
helped — see below.

TWO METHODS, IN ORDER, AND THE SECOND EXISTS BECAUSE THE FIRST MET A PHOTOGRAPH.

  1. Threshold against the background, brute-force the rotation that minimises the bounding
     box, read the edges off the projection profiles. This is the easy case the paragraph
     above used to promise — "the rig is fixed, consistent lighting, consistent background,
     one card roughly centred" — and every word of that is true of the rig and none of it
     was enough. The card sits in a CLEAR STAND on a wood desk under a dark backdrop, and
     its own artwork spans 88 to 231 against a border-ring median of 64. Consistent is not
     the same as uniform, and this method needs uniform.

  2. Find the card's BORDER instead: four long straight luminance edges whose spacing is a
     card, assuming nothing about what is behind them. Runs only when (1) refuses. 53/53.

`CardBox.method` says which one answered. docs/GATES.md's T6 section carries the
measurement and why no threshold sits between the two ways (1) fails.

BOTH METHODS GATE ON A SHAPE, AND THE SHAPE IS THE GAME'S (D22). `detect_card(source,
aspect=...)` takes `pipeline/games.py:card_aspect`; the default is this package's own
constant, so every existing one-argument call is unchanged. An entry whose `card_aspect` is
`None` — `misc`, which spans games printed at 0.716 and 0.686 — raises `UnknownCardShape`
rather than detecting with the gate switched off. Refusing costs a crop retry on a card
already being handled by hand; skipping the gate costs the difference between finding a card
and finding a rectangle, which is the distinction the paragraph above is about.
"""

from geometry.detect import (  # noqa: F401
    CARD_ASPECT,
    CardBox,
    GeometryError,
    UnknownCardShape,
    detect_card,
)
from geometry.crop import (  # noqa: F401
    NUMBER_BAND,
    REGION_CARD,
    REGION_NUMBER,
    REGION_TITLE,
    TITLE_BAND,
    crop_regions,
)
