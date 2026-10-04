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
            h > w and abs(w / h - CARD_ASPECT) < 0.08,
            # D125: the finder's box is the card as the model sees it (0.778 here), never reshaped
            # to CARD_ASPECT. So check portrait and near card aspect, not the corrected aspect.
            f"the crop is card-shaped: portrait, near geometry.CARD_ASPECT ({w / h:.3f})",
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


def _ex(cid, **kw):
    """`do_photo_by_card_ex` on a versioned crop read: (bytes, etag, final)."""
    return capture_server.do_photo_by_card_ex(cid, version=kw.pop("version", "v1"), crop=True, **kw)


@contextmanager
def _clean_preview_cache():
    """Run with an empty preview cache and put back the cap and the rule version after."""
    from identify import images

    saved = (images.PREVIEW_CACHE_BYTES, images.CROP_RULE_VERSION)
    images._preview_cache.clear()
    images._preview_cache_bytes = 0
    try:
        yield images
    finally:
        images.PREVIEW_CACHE_BYTES, images.CROP_RULE_VERSION = saved
        images._preview_cache.clear()
        images._preview_cache_bytes = 0


def check_preview_busy_finder_answers_whole_photo(checks: Checks) -> None:
    """A busy finder is never waited on: whole photo, an ETag ending `p`, not final (no long cache)."""
    checks.note("")
    checks.note("PREVIEW CROP — A BUSY FINDER ANSWERS THE WHOLE PHOTO AT ONCE")
    with isolated_home(), _clean_preview_cache() as images:
        original = _jpeg(_clear_card_frame(tilt=0.3))
        cid = _store_photo(original)
        with _counting_finders() as calls:
            images._finder_lock.acquire()
            try:
                blob, etag, final = _ex(cid)
            finally:
                images._finder_lock.release()
            checks.ok(blob == original, "a busy finder answers the whole stored photo")
            checks.ok(etag.endswith('p"'), f"its ETag ends in p ({etag})")
            checks.ok(final is False, "the answer is not final, so the route sends no long cache")
            checks.equal(calls["locate"], 0, "a busy finder runs no second finder")
            blob, etag, final = _ex(cid)
            checks.ok(blob is not None and blob != original, "the next read, finder free, is the crop")
            checks.ok(final is True and not etag.endswith('p"'), "the crop is final and its ETag is not a p ETag")


def check_preview_failures_are_never_cached(checks: Checks) -> None:
    """A raising finder or a failed model load is served whole but runs the finder again next time."""
    import geometry

    checks.note("")
    checks.note("PREVIEW CROP — A FAILURE IS SERVED BUT NEVER CACHED")
    with isolated_home(), _clean_preview_cache():
        original = _jpeg(_clear_card_frame(tilt=0.4))
        cid = _store_photo(original)
        real = geometry.locate_card
        runs = {"n": 0}

        def raising(*a, **k):
            runs["n"] += 1
            raise RuntimeError("finder broke")

        geometry.locate_card = raising
        try:
            first = _ex(cid)
            second = _ex(cid)
        finally:
            geometry.locate_card = real
        checks.ok(first[0] == original and first[2] is False, "a raising finder answers the whole photo, not final")
        checks.equal(runs["n"], 2, "a raising finder runs again on the next request")
        checks.ok(second[1].endswith('p"'), "and its ETag still ends in p")

        cid = _store_photo(_jpeg(_clear_card_frame(tilt=0.5)))
        real_failed = geometry.card_box.model_failed
        geometry.card_box.model_failed = lambda: True
        try:
            with _counting_finders() as calls:
                a = _ex(cid)
                b = _ex(cid)
        finally:
            geometry.card_box.model_failed = real_failed
        checks.ok(a[2] is False and b[2] is False, "a failed model load is never final")
        checks.equal(calls["locate"], 2, "a failed model load runs the finder again on the next request")
        with _counting_finders() as calls:
            ok = _ex(cid)
            _ex(cid)
        checks.ok(ok[2] is True and calls["locate"] == 1, "once the model loads, the answer is final and cached")


def check_preview_cache_is_byte_bounded(checks: Checks) -> None:
    """The cut-crop cache drops its oldest entry past the byte cap."""
    checks.note("")
    checks.note("PREVIEW CROP — THE BYTE CAP EVICTS OLD CROPS")
    with isolated_home(), _clean_preview_cache() as images:
        cids = [_store_photo(_jpeg(_clear_card_frame(tilt=0.6 + 0.1 * n))) for n in range(3)]
        one = len(_cropped(cids[0]))
        images._preview_cache.clear()
        images._preview_cache_bytes = 0
        images.PREVIEW_CACHE_BYTES = int(one * 1.5)  # room for one crop, not two
        with _counting_finders() as calls:
            for cid in cids:
                _cropped(cid)
            checks.equal(calls["locate"], 3, "three photos run the finder three times")
            _cropped(cids[2])
            checks.equal(calls["locate"], 3, "the newest crop is still cached")
            _cropped(cids[0])
            checks.equal(calls["locate"], 4, "the oldest crop was evicted, so its finder runs again")
        checks.ok(
            images._preview_cache_bytes <= images.PREVIEW_CACHE_BYTES * 1.5 and len(images._preview_cache) <= 2,
            f"the cache holds at most what the cap allows ({images._preview_cache_bytes} bytes)",
        )


def check_preview_rule_version_changes_etag(checks: Checks) -> None:
    """CROP_RULE_VERSION rides in the crop's ETag: a bump leaves no 304 for an old ETag."""
    checks.note("")
    checks.note("PREVIEW CROP — A NEW RULE VERSION GIVES A NEW ETAG")
    with isolated_home(), _clean_preview_cache() as images:
        cid = _store_photo(_jpeg(_clear_card_frame(tilt=0.7)))
        blob, old, _ = _ex(cid)
        checks.ok(blob is not None, "the first read sends bytes")
        again, same, _ = _ex(cid, if_none_match=old)
        checks.ok(again is None and same == old, "the same rule version answers 304 to its own ETag")
        images.CROP_RULE_VERSION = images.CROP_RULE_VERSION + "-next"
        fresh, new, _ = _ex(cid, if_none_match=old)
        checks.ok(fresh is not None, "a changed rule version does not 304 the old ETag")
        checks.ok(new != old, "a changed rule version gives a new ETag")


CHECKS = (
    check_preview_crop_yields_card,
    check_preview_crop_refused_sends_whole_photo,
    check_preview_finder_runs_once_per_photo,
    check_preview_busy_finder_answers_whole_photo,
    check_preview_failures_are_never_cached,
    check_preview_cache_is_byte_bounded,
    check_preview_rule_version_changes_etag,
)
