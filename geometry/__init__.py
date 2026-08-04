"""Find the card in the frame, and cut known regions out of it.

Its own package, not a helper inside `identify/`, because the Gate C feeder needs the same
detection: a motion state machine has to know a card is present and settled before it fires
the shutter, and that is this question asked at a different moment.

It runs at BATCH time, not capture time. D1 requires capture to be fast, offline and dumb,
and step 5's capture server does not exist yet — so nothing registers a card while the
photograph is being taken. Revisit at step 5 or Gate C, not before.

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

Pillow + numpy, not OpenCV. The rig is fixed — consistent lighting, consistent background,
one card roughly centred — which makes this the easy case rather than general document
scanning: threshold against the background, brute-force the rotation that minimises the
bounding box, read the edges off the projection profiles. `opencv-python-headless` is the
recorded fallback IF measured detection rates are poor, and nothing has been measured:
there is not one rig photo in this repo. Gate B is where that number comes from.
"""

from geometry.detect import (  # noqa: F401
    CARD_ASPECT,
    CardBox,
    GeometryError,
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
