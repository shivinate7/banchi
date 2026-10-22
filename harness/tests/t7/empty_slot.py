"""T7 group: a photograph of an empty slot is read as `empty_slot`, and is never sent to the paid read.

`identify.match.empty_slot` takes the 99th-percentile luminance of a photograph, at full size. Under
`EMPTY_SLOT_P99` the slot is empty. The check runs in three places: `match.read` answers the code
`empty_slot` without cropping or embedding; `identify` skips an empty photograph on every engine, so
the paid transport is never asked for it; and `cli/resolve.py` files it as `card_not_detected`
with its photograph. The fixtures are synthetic images written to a temporary folder at run time,
so no photograph is committed.

INTERFACE ASSUMED (the builder may rename, then re-point here): `match.empty_slot(Path) -> bool`,
`match.read(requests, index, model, aspect, log, promo_games)`, which reads `index.meta` once, and
`cli.cmd_identify.run`, whose paid transport is `batch.run_batch`. The codes are asserted as the
wire literals (`"empty_slot"`, `"card_not_detected"`), so this file imports on a tree that lacks
the constants.
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from harness.tests import Checks
from harness.tests.home import isolated_home
from harness.tests.t7.common import quiet
from identify import match

CODE = "empty_slot"
DARK = 20  # a uniform dark slot: its 99th percentile sits here
CARD = 180  # a flat card face, bright enough to clear the cut
FRAME = (1434, 1024)  # tall, the size a rig photograph is read at (full size, no downscale)


def _jpeg(path: Path, grid: np.ndarray, quality: int = 90) -> Path:
    Image.fromarray(grid).save(path, "JPEG", quality=quality)
    return path


def _dark_slot(folder: Path) -> Path:
    return _jpeg(folder / "dark.jpg", np.full(FRAME, DARK, np.uint8))


def _dark_with_bright_patch(folder: Path) -> Path:
    grid = np.full(FRAME, DARK, np.uint8)
    grid[: FRAME[0] // 2, : FRAME[1] // 2] = 230  # a quarter of the frame, far over 1% of pixels
    return _jpeg(folder / "patch.jpg", grid)


def _empty_slot_fn(checks: Checks):
    fn = getattr(match, "empty_slot", None)
    checks.ok(callable(fn), "identify.match exposes empty_slot", "no empty_slot in identify/match.py")
    return fn


def _read_one(photo: Path, stub_crop: bool) -> tuple:
    """One request through `match.read`. The pool is fixed, so only the photograph decides the code.
    `stub_crop` makes the crop find nothing, so a read that gets past the empty check ends there;
    without it the real crop runs and names a missing photograph."""
    index = mock.Mock()
    index.meta.return_value = match.MODEL_SHA256
    request = match.Request("k", photo, "riftbound", "tcg")
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set",), None, "")))
        embed = stack.enter_context(mock.patch.object(match, "embed"))
        crop = stack.enter_context(mock.patch.object(match, "_crop", return_value=None)) if stub_crop else None
        result = match.read([request], index, None, 0.716, lambda _m: None, promo_games=set())[0]
    return result, crop, embed


def check_empty_slot_fixtures(checks: Checks) -> None:
    fn = _empty_slot_fn(checks)
    if fn is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        checks.ok(fn(_dark_slot(folder)) is True, "a dark uniform JPEG is an empty slot")
        checks.ok(fn(_dark_with_bright_patch(folder)) is False,
                  "a dark JPEG with a bright quarter is not an empty slot")
        try:
            answer = fn(folder / "absent.jpg")
        except Exception as exc:  # a photograph that will not open is a named failure, never a crash
            checks.ok(False, "a missing photograph does not crash empty_slot", repr(exc))
        else:
            checks.ok(answer is False, "a missing photograph is not an empty slot", f"got {answer!r}")


def check_empty_slot_boundary(checks: Checks) -> None:
    """The cut is strict: a frame whose 99th percentile is 99 is empty, 100 is not. Lossless PNGs,
    so the luminance read is exactly the value written."""
    fn = _empty_slot_fn(checks)
    if fn is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        for value, empty in ((99, True), (100, False), (101, False)):
            photo = Path(tmp) / f"flat-{value}.png"
            Image.new("L", FRAME, value).save(photo, "PNG")
            checks.equal(fn(photo), empty, f"a flat frame at luminance {value} reads as empty={empty}")


def check_empty_slot_keeps_thin_lines(checks: Checks) -> None:
    """A dark card with 1px white lines is not an empty slot. At full size the lines keep the 99th
    percentile at 255. A downscaled decode averages each line into the dark (about 86 at 1/4 scale),
    which would call this card empty. This check fails on that regression."""
    fn = _empty_slot_fn(checks)
    if fn is None:
        return
    grid = np.full(FRAME, DARK, np.uint8)
    grid[::40, :] = 255  # one white row every 40
    with tempfile.TemporaryDirectory() as tmp:
        photo = _jpeg(Path(tmp) / "lines.jpg", grid, quality=95)
        checks.ok(fn(photo) is False, "a dark card with 1px white lines is not an empty slot",
                  "the full-size read must keep the lines; a downscaled read would average them dark")


def check_read_names_empty_slot(checks: Checks) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        result, crop, embed = _read_one(_dark_slot(folder), stub_crop=True)
        checks.equal(result.code, CODE, "read answers the code empty_slot for a dark crop")
        checks.ok(not result.accepted, "the empty slot is not accepted")
        checks.ok(not crop.called and not embed.called,
                  "the empty slot never reaches the crop or the embed")
        result, crop, _ = _read_one(_dark_with_bright_patch(folder), stub_crop=True)
        checks.ok(result.code != CODE, "a photograph with a bright quarter is not read as empty",
                  f"code={result.code}")
        checks.ok(crop.called, "and it goes on to the crop")
        result, _, _ = _read_one(folder / "absent.jpg", stub_crop=False)
        checks.equal(result.code, "photo_unreadable",
                     "a missing photograph is the named photo_unreadable failure")


def _write_caps(caps: Path) -> None:
    """Three photographs in one box: 7/1 an empty slot, 7/2 and 7/3 flat cards (sidecars name the
    `misc` game, which needs no set hint)."""
    _jpeg(caps / "7-001.jpg", np.full(FRAME, DARK, np.uint8))
    _jpeg(caps / "7-002.jpg", np.full(FRAME, CARD, np.uint8))
    _jpeg(caps / "7-003.jpg", np.full(FRAME, CARD - 40, np.uint8))
    for position in (1, 2, 3):
        (caps / f"7-00{position}.json").write_text(
            json.dumps({"box": 7, "position": position, "game": "misc"}), "utf-8"
        )


def check_haiku_press_never_sends_an_empty_slot(checks: Checks) -> None:
    """`--engine haiku` skips the free reader, so `identify` runs the empty check itself. The paid
    transport is asked for the two flat cards and never for the empty slot, and the run record keeps
    the empty card with `second_look.code == empty_slot`. Then `resolve.load` files it as
    `card_not_detected` with its photograph, and the card that failed on the paid read keeps
    `identification_failed`."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify, resolve, runs
    from identify import batch

    checks.note("")
    checks.note("HAIKU PRESS — empty slot never sent; resolve files it as card_not_detected")
    with isolated_home() as home:
        caps = Path(home) / "slot-caps"
        caps.mkdir()
        _write_caps(caps)
        transported: list = []

        def fake_run_batch(requests, log=None, on_submit=None):
            outcomes = {}
            for request in requests:
                transported.append(request.custom_id)
                outcomes[request.custom_id] = batch.Outcome(
                    request.custom_id, batch.UNKNOWN_STRATEGY, error="the stub refuses this card"
                )
            return batch.BatchRun(outcomes=outcomes)

        real_run_batch = cmd_identify.batch.run_batch
        cmd_identify.batch.run_batch = fake_run_batch
        try:
            with quiet():
                code = cmd_identify.run(
                    cli_entry.build_parser().parse_args(["identify", str(caps), "--engine", "haiku"]),
                    lambda *_a: None,
                )
        finally:
            cmd_identify.batch.run_batch = real_run_batch
        checks.equal(code, 0, "`identify --engine haiku` exits 0 over the stub transport")
        checks.equal(sorted(transported), sorted(cmd_identify._custom_id(key) for key in ("7/2", "7/3")),
                     "the paid transport is asked for the two flat cards and never for the empty slot")

        run = runs.latest()
        if not checks.ok(run is not None, "the press left a run to resolve"):
            return
        cards = run.read_identifications()["cards"]
        checks.equal((cards.get("7/1", {}).get("second_look") or {}).get("code"), CODE,
                     "the run record keeps the empty card with second_look.code empty_slot")

        resolved = resolve.load(run, {})
        filed = {failure.key: failure for failure in resolved.failures}
        checks.equal(filed["7/1"].reason, "card_not_detected",
                     "the empty slot is filed as card_not_detected")
        checks.ok(str(filed["7/1"].photo or "").endswith("7-001.jpg"),
                  "and carries its photograph", f"photo={filed['7/1'].photo!r}")
        checks.equal(filed["7/2"].reason, "identification_failed",
                     "a card the paid read failed on, with no second look, keeps identification_failed")


def check_dry_run_quote_leaves_the_empty_slot_out(checks: Checks) -> None:
    """The free-first quote counts what is sent. An empty slot is not sent on any engine, so the
    quote's `to send` and `second look` lines count the one flat card, not two."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify

    checks.note("")
    checks.note("DRY-RUN QUOTE — the empty slot is out of the second-look count")
    with isolated_home() as home:
        caps = Path(home) / "quote-caps"
        caps.mkdir()
        _write_caps(caps)
        lines: list = []
        with quiet():
            code = cmd_identify.run(
                cli_entry.build_parser().parse_args(["identify", str(caps), "--engine", "marqo-b", "--dry-run"]),
                lines.append,
            )
    checks.equal(code, 0, "`identify --engine marqo-b --dry-run` exits 0")
    to_send = [line for line in lines if line.startswith("to send")]
    second = [line for line in lines if line.startswith("second look")]
    checks.ok(len(to_send) == 1 and to_send[0].split()[-1] == "2",
              "control: three photographs, one empty — the quote sends the other two",
              f"to send lines: {to_send!r}")
    checks.ok(len(second) == 1 and second[0].split()[2] == "2",
              "the second-look line counts the two sent cards, not the empty slot",
              f"second look lines: {second!r}")


CHECKS = (
    check_empty_slot_fixtures,
    check_empty_slot_boundary,
    check_empty_slot_keeps_thin_lines,
    check_read_names_empty_slot,
    check_haiku_press_never_sends_an_empty_slot,
    check_dry_run_quote_leaves_the_empty_slot_out,
)
