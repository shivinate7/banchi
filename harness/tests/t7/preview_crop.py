"""T7 group: card previews crop to the card (owner ruling after D38's `contain`).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

THE NAMES THE BUILDER FOLLOWS (this file is their spec):
  * `capture_server.do_photo_by_card(cid, if_none_match=None, version=None, crop=False)`: with
    `crop=True` the bytes are the card's region, else the stored bytes. The route spells it
    `GET /photo/by-card/<cid>?crop=card`. A refusal or no box answers the stored bytes.
  * `identify.images.preview_rect(path) -> Optional[(l, t, r, b)]`: the ONE home of the preview
    cut. It finds with `geometry.locate_card` (falling back to `geometry.detect_card`, as
    `prepare_located` does) and guards with `crop_refusal`. Cached per photograph.
  * No new threshold and no second crop rule: `images.SMALL_CROP_AREA`/`MIN_CROP_DETAIL` only.
"""

from __future__ import annotations

import io
from contextlib import contextmanager

from harness.tests import Checks
from harness.tests.t7.common import isolated_home
from server import capture_server
from store import photos
from store.session import Store

FRAME = (900, 1600)  # 9/16, as the rig shoots
CARD_ASPECT = 63 / 88


def _jpeg(image) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", quality=92)
    return out.getvalue()


def _clear_card_frame(tilt: float = 0.0):
    """A card filling 56% of a tall frame on a flat mat, white number band at its foot."""
    from PIL import Image, ImageDraw

    frame = Image.new("RGB", FRAME, (28, 30, 34))
    w, h = 760, 1060
    card = Image.new("RGB", (w, h), (238, 232, 214))
    pen = ImageDraw.Draw(card)
    pen.rectangle([8, 8, w - 9, h - 9], outline=(40, 40, 40), width=6)
    pen.rectangle([int(w * .06), int(h * .03), int(w * .94), int(h * .15)], fill=(210, 190, 120))
    pen.rectangle([int(w * .08), int(h * .86), int(w * .34), int(h * .95)], fill=(255, 255, 255))
    if tilt:
        card = card.rotate(tilt, expand=True, fillcolor=(28, 30, 34))
    frame.paste(card, ((FRAME[0] - card.width) // 2, (FRAME[1] - card.height) // 2))
    return frame


def _noisy_frame_with_tiny_card():
    """Texture everywhere EXCEPT a 200x280 card: a box on the card keeps little of the detail."""
    import numpy
    from PIL import Image, ImageDraw

    rng = numpy.random.default_rng(3)
    frame = Image.fromarray(rng.integers(0, 255, (FRAME[1], FRAME[0], 3), dtype=numpy.uint8))
    ImageDraw.Draw(frame).rectangle([100, 100, 299, 379], fill=(238, 232, 214))
    return frame


def _store_photo(blob: bytes) -> str:
    cid = photos.sha256_of_bytes(blob)
    photos.write(cid, blob)
    with Store().write() as snapshot:
        snapshot.inventory.allocate_capture(1, game="pokemon", cid=cid)
    return cid


@contextmanager
def _counting_finders():
    """Count every call of the two finders through the names `prepare_located` reads."""
    import geometry

    calls = {"locate": 0, "detect": 0}
    real_locate, real_detect = geometry.locate_card, geometry.detect_card

    def locate(*a, **k):
        calls["locate"] += 1
        return real_locate(*a, **k)

    def detect(*a, **k):
        calls["detect"] += 1
        return real_detect(*a, **k)

    geometry.locate_card, geometry.detect_card = locate, detect
    try:
        yield calls
    finally:
        geometry.locate_card, geometry.detect_card = real_locate, real_detect


def _cropped(cid):
    """`do_photo_by_card(..., crop=True)` bytes, or None when the seam does not exist yet."""
    try:
        blob, _ = capture_server.do_photo_by_card(cid, crop=True)
        return blob
    except TypeError:
        return None


def check_preview_crop_yields_card(checks: Checks) -> None:
    """The photo with `crop` is the card: card aspect, number band inside, smaller than frame."""
    from PIL import Image

    checks.note("")
    checks.note("PREVIEW CROP — A CLEAR CARD COMES BACK AS THE CARD")
    with isolated_home():
        original = _jpeg(_clear_card_frame())
        cid = _store_photo(original)
        blob = _cropped(cid)
        checks.ok(blob is not None, "do_photo_by_card accepts crop=True (the builder's seam)")
        if blob is None:
            return
        image = Image.open(io.BytesIO(blob)).convert("RGB")
        w, h = image.size
        checks.ok(w < FRAME[0] and h < FRAME[1], f"the crop is smaller than the frame ({w}x{h})")
        checks.ok(
            abs(w / h - CARD_ASPECT) < 0.06,
            f"the crop's aspect is near geometry.CARD_ASPECT ({w / h:.3f})",
        )
        band = image.crop((int(w * .05), int(h * .80), int(w * .40), h))
        white = sum(1 for p in band.getdata() if min(p) > 245) / (band.width * band.height)
        checks.ok(white > 0.05, f"the number band is inside the crop ({white:.2f} white)")
        checks.ok(
            capture_server.do_photo_by_card(cid)[0] == original,
            "without crop the stored bytes are untouched",
        )


def check_preview_crop_refused_sends_whole_photo(checks: Checks) -> None:
    """A tiny box (the 'zoomed 30x' case) or no box answers the stored bytes, never a crop."""
    import geometry
    from PIL import Image

    checks.note("")
    checks.note("PREVIEW CROP — A REFUSED OR ABSENT BOX SENDS THE WHOLE PHOTO")
    with isolated_home():
        tiny = _jpeg(_noisy_frame_with_tiny_card())
        cid = _store_photo(tiny)
        # Force the finder onto the card-shaped patch of texture the guard exists to refuse.
        wrong = geometry.CardBox(0.0, 0.11, 0.06, 0.33, 0.24, 0.9, CARD_ASPECT, "dfine")
        real = geometry.locate_card
        geometry.locate_card = lambda *a, **k: wrong
        try:
            blob = _cropped(cid)
        finally:
            geometry.locate_card = real
        checks.ok(blob is not None, "do_photo_by_card accepts crop=True (the builder's seam)")
        checks.ok(blob == tiny, "a box the guard refuses answers the whole stored photo")

        blank = _jpeg(Image.new("RGB", FRAME, (40, 40, 40)))
        cid = _store_photo(blank)
        checks.ok(_cropped(cid) == blank, "no box found answers the whole stored photo")


def check_preview_finder_runs_once_per_photo(checks: Checks) -> None:
    """Listing does not run the finder; N crop reads of one photo run it at most once."""
    checks.note("")
    checks.note("PREVIEW CROP — THE FINDER IS NOT IN THE LISTING PATH AND RUNS ONCE PER PHOTO")
    with isolated_home():
        cids = [_store_photo(_jpeg(_clear_card_frame(tilt=0.2 * n))) for n in range(3)]
        with _counting_finders() as calls:
            capture_server.do_inventory()
            capture_server.do_boxes()
            checks.equal(
                (calls["locate"], calls["detect"]), (0, 0),
                "listing a box of cards runs no card finder",
            )
            for _ in range(3):
                _cropped(cids[0])
            checks.ok(
                calls["locate"] == 1,
                f"three crop reads of one photo run the finder exactly once ({calls['locate']})",
            )


CHECKS = (
    check_preview_crop_yields_card,
    check_preview_crop_refused_sends_whole_photo,
    check_preview_finder_runs_once_per_photo,
)
