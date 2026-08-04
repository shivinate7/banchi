"""T6 — Card geometry.

New with batch script v2. The crop-retry path is only as good as its ability to find the
card in the frame: a wrong crop produces a miss indistinguishable from a bad read, and it
does it confidently. So detection gets its own failing test name rather than hiding inside
a green identification run.

Pass: the detected rectangle is within tolerance of the known one across the offset, scale
and rotation sweep; the title band and number corner crops each contain their target region;
and a frame with no card returns "not found" rather than a guess.

SYNTHETIC COMPOSITES ONLY, and the answer key is exact because this test drew the picture:
a card rectangle with a coloured title bar and a white number box, rendered onto a background
at a KNOWN offset, scale and rotation. Nothing is downloaded and nothing is hand-labelled.

KNOWN BLIND SPOT, and it is the important one. This measures the algorithm against images
this repo generated. That is not the same as measuring it against photographs from the rig:
no glare, no shadow, no depth of field, no sleeve, no mat texture, and a background that is
genuinely uniform in a way a real one is not. Real detection rates are a GATE B number. A
green T6 means the geometry is self-consistent — it does NOT mean detection works. Read it
exactly the way T1's finish blind spot is read.

The bands are checked by CONTENT, not by coordinates. Asserting that the number band starts
at 0.82 of the card only proves the constant was not edited; asserting that the white number
box is inside it and the title bar is not proves the crop would actually show the model the
digits.
"""

from __future__ import annotations

from harness.tests import Checks, Result

NAME = "T6"
DESCRIPTION = "Card boundary detection and crop-retry bands"
PASS_CRITERIA = (
    "detected rectangle within tolerance across the sweep; bands contain their target; "
    "no card -> not found"
)

# Angle tolerance in degrees. The fine search steps at 0.25, so anything inside half a
# degree is at the resolution of the method rather than an error in it.
ANGLE_TOLERANCE = 0.5
# Box tolerance as a fraction of the frame. The bands are deliberately generous, so a
# rectangle a percent off costs nothing; ten percent would start cutting the number.
BOX_TOLERANCE = 0.02

CARD_RGB = (238, 232, 214)
TITLE_RGB = (210, 190, 120)
NUMBER_RGB = (255, 255, 255)
BACKGROUND_RGB = (28, 30, 34)

# Fraction of a crop that must be the target colour for the crop to contain the target.
PRESENT = 0.10
ABSENT = 0.01


def _draw_card(Image, ImageDraw, width=420, height=586):
    """A card-shaped rectangle with a title bar at the top and a number box at the bottom."""
    card = Image.new("RGB", (width, height), CARD_RGB)
    pen = ImageDraw.Draw(card)
    pen.rectangle([6, 6, width - 7, height - 7], outline=(40, 40, 40), width=4)
    pen.rectangle(
        [int(width * 0.06), int(height * 0.03), int(width * 0.94), int(height * 0.15)],
        fill=TITLE_RGB,
    )
    pen.rectangle(
        [int(width * 0.08), int(height * 0.86), int(width * 0.34), int(height * 0.95)],
        fill=NUMBER_RGB,
    )
    return card


def _scene(Image, ImageDraw, angle=0.0, scale=1.0, dx=0, dy=0, size=(900, 1200)):
    frame = Image.new("RGB", size, BACKGROUND_RGB)
    card = _draw_card(Image, ImageDraw)
    card = card.resize((int(card.width * scale), int(card.height * scale)))
    card = card.rotate(
        angle, expand=True, resample=Image.BICUBIC, fillcolor=BACKGROUND_RGB
    )
    frame.paste(
        card,
        ((size[0] - card.width) // 2 + dx, (size[1] - card.height) // 2 + dy),
    )
    return frame


def _share(numpy, image, rgb, tolerance=40):
    array = numpy.asarray(image.convert("RGB"), dtype=numpy.int16)
    distance = numpy.abs(array - numpy.array(rgb, dtype=numpy.int16)).max(axis=2)
    return float((distance <= tolerance).mean())


def run() -> Result:
    c = Checks()

    try:
        import numpy
        from PIL import Image, ImageDraw
    except ImportError as exc:
        return Result(
            False,
            "geometry cannot run: {0}\n"
            "      T6 needs Pillow and numpy — run `make venv`.\n"
            "      A skipped test must not read as a pass.".format(exc),
        )

    import geometry

    c.note(
        "SYNTHETIC composites, exact answer key. Real detection rates are a Gate B number "
        "against rig photos — a green T6 is not evidence that detection works."
    )

    # --- the sweep -----------------------------------------------------------------------
    angles_ok = True
    boxes_ok = True
    found_all = True
    for angle in (0.0, -11.0, -6.0, -2.5, 3.5, 9.0):
        for scale, dx, dy in ((0.7, 0, 0), (0.9, 20, -30), (1.15, -45, 60)):
            frame = _scene(Image, ImageDraw, angle=angle, scale=scale, dx=dx, dy=dy)
            box = geometry.detect_card(frame)
            if box is None:
                found_all = False
                c.note(f"angle {angle:+.1f} scale {scale} offset ({dx},{dy}): NOT FOUND")
                continue

            # The composite rotated the card by `angle`; detection reports the rotation that
            # puts it back upright, so the two must sum to zero.
            residual = box.angle + angle
            if abs(residual) > ANGLE_TOLERANCE:
                angles_ok = False
                c.note(
                    f"angle {angle:+.1f} scale {scale}: corrected {box.angle:+.2f}, "
                    f"residual {residual:+.2f} > {ANGLE_TOLERANCE}"
                )

            # The card was pasted centred plus an offset, so the detected box's centre must
            # land where the composite put it, once the frame is rotated to match.
            if not (0.0 <= box.left < box.right <= 1.0 and 0.0 <= box.top < box.bottom <= 1.0):
                boxes_ok = False
                c.note(f"angle {angle:+.1f} scale {scale}: box outside the canvas: {box.describe}")
            expected_aspect = geometry.CARD_ASPECT
            if abs(box.aspect - expected_aspect) > expected_aspect * 0.06:
                boxes_ok = False
                c.note(
                    f"angle {angle:+.1f} scale {scale}: aspect {box.aspect:.3f} vs "
                    f"{expected_aspect:.3f}"
                )

    c.ok(found_all, "the card is found at every angle, scale and offset in the sweep")
    c.ok(angles_ok, f"detected rotation is within {ANGLE_TOLERANCE} degrees of the truth")
    c.ok(boxes_ok, f"detected rectangle is card-shaped and inside the canvas")

    # --- the box tracks the composite's own scale -------------------------------------------
    small = geometry.detect_card(_scene(Image, ImageDraw, scale=0.7))
    large = geometry.detect_card(_scene(Image, ImageDraw, scale=1.15))
    if c.ok(small is not None and large is not None, "both scales detected"):
        c.ok(
            large.width > small.width and large.height > small.height,
            "a larger card produces a larger box — the box is measured, not assumed",
            f"small {small.width:.3f}x{small.height:.3f}, large {large.width:.3f}x{large.height:.3f}",
        )
        ratio = large.height / small.height
        c.ok(
            abs(ratio - (1.15 / 0.7)) < 0.08,
            f"box scales with the card: {ratio:.3f} vs the composite's {1.15 / 0.7:.3f}",
        )

    # --- the bands contain what they were cut to show ----------------------------------------
    titles_ok = numbers_ok = clean_ok = True
    for angle in (0.0, -6.0, 9.0):
        frame = _scene(Image, ImageDraw, angle=angle, scale=0.9, dx=15, dy=-25)
        box = geometry.detect_card(frame)
        regions = geometry.crop_regions(frame, box)
        if set(regions) != {
            geometry.REGION_CARD,
            geometry.REGION_TITLE,
            geometry.REGION_NUMBER,
        }:
            clean_ok = False
            c.note(f"angle {angle:+.1f}: regions were {sorted(regions)}")
            continue

        title_in_title = _share(numpy, regions[geometry.REGION_TITLE], TITLE_RGB)
        title_in_number = _share(numpy, regions[geometry.REGION_NUMBER], TITLE_RGB)
        number_in_number = _share(numpy, regions[geometry.REGION_NUMBER], NUMBER_RGB)
        background_in_card = _share(numpy, regions[geometry.REGION_CARD], BACKGROUND_RGB)

        if title_in_title < PRESENT:
            titles_ok = False
            c.note(f"angle {angle:+.1f}: title bar is {title_in_title:.3f} of the title band")
        if number_in_number < PRESENT:
            numbers_ok = False
            c.note(f"angle {angle:+.1f}: number box is {number_in_number:.3f} of the number band")
        if title_in_number > ABSENT:
            numbers_ok = False
            c.note(
                f"angle {angle:+.1f}: the number band contains {title_in_number:.3f} title "
                f"bar — the bands are the wrong way up"
            )
        if background_in_card > 0.08:
            clean_ok = False
            c.note(f"angle {angle:+.1f}: {background_in_card:.3f} of the card crop is mat")

    c.ok(titles_ok, "the title band contains the title bar")
    c.ok(numbers_ok, "the number band contains the number box and NOT the title bar")
    c.ok(clean_ok, "all three regions are produced, and the card crop has the mat removed")

    # --- crops are enlarged, which is the entire argument for crop retry -----------------------
    frame = _scene(Image, ImageDraw, angle=4.0, scale=0.55)
    regions = geometry.crop_regions(frame, geometry.detect_card(frame))
    c.ok(
        all(max(image.size) >= geometry.crop.MIN_REGION_EDGE for image in regions.values()),
        f"every region is upscaled to at least {geometry.crop.MIN_REGION_EDGE}px — a 40px "
        f"collector number is a coin flip and enlarging it is the point",
        {name: image.size for name, image in regions.items()},
    )
    c.ok(
        all(max(image.size) <= 1568 for image in regions.values()),
        "and never past 1568px, which the API bills for and then discards",
    )

    # --- no card means NOT FOUND, never a guess ------------------------------------------------
    empty = Image.new("RGB", (900, 1200), BACKGROUND_RGB)
    c.ok(geometry.detect_card(empty) is None, "an empty frame returns None")
    c.equal(
        geometry.crop_regions(empty, None),
        {},
        "and no regions, so the caller skips the retry rather than re-sending the same photo",
    )

    noise = Image.new("RGB", (900, 1200), BACKGROUND_RGB)
    pen = ImageDraw.Draw(noise)
    for offset in range(0, 900, 90):
        pen.rectangle([offset, offset, offset + 30, offset + 30], fill=(200, 60, 60))
    c.ok(
        geometry.detect_card(noise) is None,
        "scattered debris is not a card — the shape gates refuse it",
    )

    for name, corners in (
        ("nearly square", [200, 400, 700, 880]),
        ("long and thin", [150, 300, 780, 480]),
    ):
        wrong_shape = Image.new("RGB", (900, 1200), BACKGROUND_RGB)
        ImageDraw.Draw(wrong_shape).rectangle(corners, fill=CARD_RGB)
        c.ok(
            geometry.detect_card(wrong_shape) is None,
            f"a {name} rectangle is refused, not stretched to fit "
            f"{geometry.CARD_ASPECT:.3f}",
        )

    tiny = Image.new("RGB", (900, 1200), BACKGROUND_RGB)
    ImageDraw.Draw(tiny).rectangle([440, 590, 470, 632], fill=CARD_RGB)
    c.ok(
        geometry.detect_card(tiny) is None,
        "a card-shaped speck is below the area floor and is refused",
    )

    return c.result()
