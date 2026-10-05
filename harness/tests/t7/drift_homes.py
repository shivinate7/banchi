"""T7 group: one home per capability. Four drifts the sweep found between the match, store and pipeline layers.

Part of `harness/tests/t7_store_and_seams.py` (one verdict).

  1. name fold      `pipeline.join._name_compare_key` and `identify.prompt.normalize_name` fold curly
                    apostrophes and en/em dashes the same way, and `identity_binding.name_fold_matches`
                    accepts a card whose name differs only in that typography (RED today).
  2. terminal state `identify.match.held_promo_games` reads `store.master.TERMINAL_STATES` (RED today).
  3. EXIF           an orientation-6 JPEG: `geometry.card_box.model_card`, `identify.images.prepare` and
                    `identify.images._preview_compute` work in the upright pixel space `geometry.detect`
                    uses (RED today).
  4. set fold       `pipeline.setnames.fold` equals `pipeline.join.normalize_set` (passes; guards the dedupe).

No model, no network, no store: the finder session is a fake, the store is an in-memory table.
"""

from __future__ import annotations

import io
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from harness.tests import Checks

APOSTROPHES = ("’", "‘", "ʼ", "´", "`")
DASHES = ("–", "—", "‐", "−")


def check_name_fold_one_home(checks: Checks) -> None:
    from identify import prompt
    from pipeline import identity_binding, join

    for odd in APOSTROPHES:
        plain, curly = "Sterak's Gage", f"Sterak{odd}s Gage"
        checks.equal(join._name_compare_key(curly), join._name_compare_key(plain), f"join folds apostrophe U+{ord(odd):04X}")
        checks.equal(prompt.normalize_name(curly), prompt.normalize_name(plain), f"prompt folds apostrophe U+{ord(odd):04X}")
        checks.ok(identity_binding.name_fold_matches(curly, plain), f"name_fold_matches accepts apostrophe U+{ord(odd):04X}")
    for odd in DASHES:
        plain, fancy = "Iron-Valiant Kai", f"Iron{odd}Valiant Kai"
        checks.equal(join._name_compare_key(fancy), join._name_compare_key(plain), f"join folds dash U+{ord(odd):04X}")
        checks.equal(prompt.normalize_name(fancy), prompt.normalize_name(plain), f"prompt folds dash U+{ord(odd):04X}")
        checks.ok(identity_binding.name_fold_matches(fancy, plain), f"name_fold_matches accepts dash U+{ord(odd):04X}")
    checks.ok(
        identity_binding.name_fold_matches("Sterak’s Gage", "Sterak's Gage - 101/250"),
        "name_fold_matches: curly read against a catalog name that embeds the number",
    )
    # The fold stays typography only: a different card is still a different card.
    checks.ok(not identity_binding.name_fold_matches("Iron Valiant", "Iron Valiant ex"), "fold does not merge ex with base")


def check_terminal_states_from_store(checks: Checks) -> None:
    from identify import match
    from store import db, master

    conn = sqlite3.connect(":memory:")
    conn.execute("create table cards (game text, set_name text, state text)")
    conn.executemany(
        "insert into cards values (?, ?, ?)",
        [("pokemon", "Black Star Promo", "vaulted"), ("riftbound", "Origins Promo", "held")],
    )
    with mock.patch.object(master, "TERMINAL_STATES", tuple(master.TERMINAL_STATES) + ("vaulted",)), \
            mock.patch.object(db, "open_read_only", lambda *_a, **_k: conn), \
            mock.patch.object(db, "path", lambda *_a, **_k: "x"), \
            mock.patch.object(match.store_files, "inventory_dir", lambda *_a, **_k: Path("x")):
        games = match.held_promo_games()
    checks.equal(games, {"riftbound"}, "a state added to TERMINAL_STATES leaves held_promo_games' query")


def _exif6_jpeg(directory: str):
    """`(path, upright_size)`: a 400x600 card scene stored as 600x400 with EXIF orientation 6.
    Red 40x40 patch at the UPRIGHT top-left, so a reader can tell which frame it was given."""
    from PIL import Image

    upright = Image.new("RGB", (400, 600), (20, 20, 20))
    upright.paste((255, 0, 0), (0, 0, 40, 40))
    raw = upright.rotate(90, expand=True)  # CCW; exif_transpose for 6 turns it back CW
    exif = Image.Exif()
    exif[274] = 6
    path = str(Path(directory) / "rot.jpg")
    raw.save(path, "JPEG", quality=95, exif=exif)
    return path, (400, 600)


def check_exif_one_pixel_space(checks: Checks) -> None:
    import numpy as np
    from geometry import card_box, detect
    from identify import images

    with tempfile.TemporaryDirectory() as tmp:
        path, upright = _exif6_jpeg(tmp)
        checks.equal(detect.open_image(path).size, upright, "fixture: geometry.detect reads it upright")

        # model_card: which frame does the finder see? Red must sit at the upright top-left.
        seen = {}

        class Session:
            def run(self, _out, inputs):
                seen["pixels"] = inputs["images"][0]
                size = card_box.SIZE
                return None, np.array([[[0.1, 0.1, 0.9, 0.9]]], np.float32) * size, np.array([[0.9]], np.float32)

        with mock.patch.object(card_box, "_load", lambda: Session()):
            card_box.model_card(path)
        pixels = seen.get("pixels")
        red_corner = pixels is not None and float(pixels[0, :20, :20].mean()) > 0.8 and float(pixels[1, :20, :20].mean()) < 0.2
        checks.ok(red_corner, "model_card feeds the finder the upright frame")

        # prepare: a box found in the upright frame cuts the upright frame.
        box = detect.CardBox(angle=0.0, left=0.1, top=0.1, right=0.9, bottom=0.9, fill=0.9, aspect=0.67)
        got = images.prepare(path, crop_box=box)
        checks.equal(got.original_size, upright, "prepare reports the upright frame size")
        checks.ok(got.sent_size[1] > got.sent_size[0], "prepare's crop of an upright box is portrait", f"sent_size {got.sent_size}")

        # _preview_compute: the same, for the crop preview.
        with mock.patch.object(images, "card_box_for", lambda *_a, **_k: box):
            rect, jpeg, _final = images._preview_compute(path)
        checks.ok(rect is not None and (rect[2] - rect[0]) < (rect[3] - rect[1]), "preview rect is portrait", f"rect {rect}")
        if jpeg:
            from PIL import Image

            w, h = Image.open(io.BytesIO(jpeg)).size
            checks.ok(h > w, "preview cut is portrait", f"{w}x{h}")
        else:
            checks.ok(False, "preview cut is portrait", "no jpeg")


def check_set_fold_one_spelling(checks: Checks) -> None:
    from pipeline import join, setnames

    battery = ("SV09: Journey Together", "sv9", "SV09", "Journey Together", "Scarlet & Violet - 151", "SWSH12.5",
               "  Crown   Zenith  ", "", "Sun & Moon: Team Up", "XY-P Promo", "SV010", "0", "007", "Pokémon GO", "Origins (OGN)")
    for name in battery:
        checks.equal(setnames.fold(name), join.normalize_set(name), f"set fold agrees on {name!r}")
    checks.equal(setnames.fold(None), join.normalize_set(None), "set fold agrees on None")


def check_exif_verbatim_bytes_upright(checks: Checks) -> None:
    """`prepare`'s verbatim branch (no crop box, under the cap) sends the file's own bytes. Those bytes must
    decode, EXIF ignored, to the size `sent_size` reports (the upright frame)."""
    from PIL import Image
    from identify import images

    with tempfile.TemporaryDirectory() as tmp:
        path, upright = _exif6_jpeg(tmp)
        got = images.prepare(path)
        checks.equal(got.sent_size, upright, "prepare reports the upright frame as sent")
        raw = Image.open(io.BytesIO(got.data))  # PIL's open honors no EXIF until exif_transpose
        checks.ok(raw.size == got.sent_size, "the bytes prepare sends are the size sent_size reports",
                  f"bytes decode to {raw.size}, sent_size {got.sent_size}, resized={got.resized}")


def check_exif_crop_refusal_path(checks: Checks) -> None:
    """`crop_refusal` given a path reads an EXIF-rotated file upright."""
    from PIL import Image
    from geometry import detect
    from identify import images

    with tempfile.TemporaryDirectory() as tmp:
        path, _upright = _exif6_jpeg(tmp)
        # A small box over the red patch (upright top-left). The upright frame keeps the patch's detail;
        # the raw sideways frame puts the same box on flat pixels and refuses. Only one frame refuses.
        box = detect.CardBox(angle=0.0, left=0.0, top=0.0, right=0.2, bottom=0.15, fill=0.9, aspect=0.67)
        sideways = Image.open(path).convert("RGB")  # no exif_transpose
        checks.ok(images.crop_refusal(sideways, box) is not None, "fixture: the raw sideways frame refuses this box")
        checks.equal(images.crop_refusal(path, box), None, "crop_refusal on a path judges the upright frame")


CHECKS = (check_name_fold_one_home, check_terminal_states_from_store, check_exif_one_pixel_space,
          check_exif_verbatim_bytes_upright, check_exif_crop_refusal_path, check_set_fold_one_spelling)
