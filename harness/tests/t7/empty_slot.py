"""T7 group: a photograph of an empty slot is read as `empty_slot`, and is never accepted or sent to the paid read.

`identify.match.empty_slot` takes the 99th-percentile luminance of a photograph, at full size. Under
`EMPTY_SLOT_P99` the slot is empty. `match.read` ranks a dark photograph for its best raw cosine and
answers the code `empty_slot` with that luminance and that best match; it is never accepted. The
press never sends an empty photograph to the paid read, retires a captured card only when the dark
photograph and a weak best match agree, and `cli/resolve.py` files the rest as `card_not_detected`
with their photographs. The fixtures are synthetic images written to a temporary folder at run time,
so no photograph is committed.

INTERFACE ASSUMED (the builder may rename, then re-point here): `match.empty_slot(Path) -> bool`,
`match.read(requests, index, model, aspect, log, promo_games)`, which reads `index.meta` once and
`index.pool` per printing set; `cli.cmd_identify.run`, whose paid transport is `batch.run_batch`; and
the retire event written to `history.jsonl`. The codes and event names are asserted as the wire
literals (`"empty_slot"`, `"card_not_detected"`, `"retired"`), so this file imports on a tree that
lacks the constants.
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
from harness.tests.t7.common import card_photo, events_for, photo_of, quiet, refusal, tree_digest, write_export
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
    index = _PoolIndex({"Set": []})
    request = match.Request("k", photo, "riftbound", "tcg")
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set",), None, "")))
        stack.enter_context(mock.patch.object(match, "_stock_images", lambda: _Catalog(["Set"])))
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
    """A dark crop is ranked, then answered `empty_slot` with its luminance and its best raw cosine.
    It is never accepted, however strong that cosine is."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        result = _ranked_read(_dark_slot(folder), 0.95)
        checks.equal(result.code, CODE, "read answers the code empty_slot for a dark crop")
        checks.ok(not result.accepted, "the empty slot is not accepted, though its best match is strong")
        checks.equal(getattr(result, "best_match", "unset"), 0.95,
                     "the empty answer carries the best raw cosine of the ranking")
        p99 = getattr(result, "p99", None)
        checks.ok(p99 is not None and p99 < 100, "and the 99th-percentile luminance under the cut",
                  f"p99={p99!r}")
        result, _crop, _embed = _read_one(_dark_slot(folder), stub_crop=True)
        checks.equal(result.code, CODE, "a dark crop with no ranking is still answered empty_slot")
        checks.ok(getattr(result, "best_match", "unset") is None,
                  "and carries no best match when no printing was ranked")
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


def _p99(photo: Path) -> float:
    """The 99th-percentile luminance, read here and not through the product, so a check never judges
    its own fixture with the function it is testing."""
    return float(np.percentile(np.asarray(Image.open(photo).convert("L")), 99))


class _FakeIndex:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _PoolIndex:
    """A stand-in for the match index. `sets` maps each set name to its printings, as (product id,
    number, raw cosine to the unit query). `held` is the sets the index holds, all of them by default."""

    def __init__(self, sets: dict, held=None) -> None:
        self._sets = sets
        self._held = list(sets) if held is None else list(held)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def meta(self, _name):
        return match.MODEL_SHA256

    def set_names(self, _game):
        return list(self._held)

    def pool(self, _game, sets):
        rows, vectors, names, printed = [], [], [], []
        for name in sets:
            for product_id, number, cosine in self._sets.get(name, []):
                rows.append(("riftbound", name, product_id, number))
                vectors.append([cosine, (1 - cosine * cosine) ** 0.5])
                names.append(f"Card {product_id}")
                printed.append(number)
        return match.Pool(
            vectors=np.array(vectors, np.float32).reshape(-1, 2),
            rows=rows,
            names=names,
            printed=printed,
            blocked=set(),
            sets=tuple(sets),
        )


class _Catalog:
    """Stands in for the stock images: the set names the catalogue lists for a game."""

    def __init__(self, listed) -> None:
        self._listed = list(listed)

    def catalog_sets(self, _game):
        return [(name, 1) for name in self._listed]


class _BrokenCatalog:
    """Stands in for the stock images when the catalogue read raises."""

    def catalog_sets(self, _game):
        raise OSError("the catalogue cannot be read")


class _StaleIndex(_PoolIndex):
    """An index built by another model file: its meta names another sha."""

    def meta(self, _name):
        return "stale-model"


def _whole_pool_answer(index, game: str):
    """`match._whole_pool`'s answer, or the exception it raised, so a check reads a crash as a failure."""
    try:
        return match._whole_pool(index, game)
    except Exception as exc:  # noqa: BLE001 - the answer is what the check judges
        return f"raised {type(exc).__name__}"


def _ranked_read(photo: Path, top: float):
    """One request through `match.read` with a real ranking over one set. The crop and the embed are
    stubbed; the query is the unit vector, so the top printing's raw cosine is `top`."""
    query = np.array([1.0, 0.0], np.float32)
    index = _PoolIndex({"Set": [("1", "1", top), ("2", "2", 0.0)]})
    request = match.Request("k", photo, "riftbound", "tcg")
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(match, "_resolve_pool", lambda *_a: (("Set",), None, "")))
        stack.enter_context(mock.patch.object(match, "_crop", lambda *_a: object()))
        stack.enter_context(mock.patch.object(match, "embed", lambda cards, _model=None: [query for _ in cards]))
        stack.enter_context(mock.patch.object(match, "_stock_images", lambda: _Catalog(["Set"])))
        return match.read([request], index, None, 0.716, lambda _m: None, promo_games=set())[0]


def _store_captures(box: int, last: int) -> None:
    """Captures through the real route up to position `last`, as `seam_run` does."""
    from server import capture_server
    from store.session import Store
    from harness.tests.t7.common import capture_payload

    while Store().read().inventory.next_index(box) <= last:
        capture_server.do_capture(capture_payload(box))


def _dress_stored(box: int, index: int, luminance: int) -> None:
    """Replace the stored photograph of one position with a flat frame at this luminance."""
    Image.new("L", FRAME, luminance).save(photo_of(box, index), "JPEG", quality=95)


def _caps(folder: Path, box: int, shots: dict, *, game: str = "misc", hint=None) -> Path:
    """One capture folder: a flat photograph per position, at the luminance `shots` gives it. The
    sidecars name the `misc` game and no set hint, unless the caller names them."""
    folder.mkdir(parents=True, exist_ok=True)
    for position, luminance in shots.items():
        name = f"{box}-{position:03d}"
        _jpeg(folder / f"{name}.jpg", np.full(FRAME, luminance, np.uint8))
        sidecar = {"box": box, "position": position, "game": game}
        if hint is not None:
            sidecar["set_hint"] = hint
        (folder / f"{name}.json").write_text(json.dumps(sidecar), "utf-8")
    return folder


def _reader(best_by_name: dict, seen: list):
    """Stands in for `match.read`. A dark photograph is answered `empty_slot` with its luminance and
    the best raw cosine `best_by_name` gives its file name. A bright one is an unaccepted margin."""

    def read(requests, _index, *_a, **_k):
        out = []
        for request in requests:
            seen.append(request.key)
            photo = Path(request.photo)
            if _p99(photo) < 100:
                result = match.Result(request.key, False, code=CODE, detail="the slot holds no card")
                result.p99 = round(_p99(photo), 1)
                result.best_match = best_by_name.get(photo.name)
                out.append(result)
            else:
                out.append(match.Result(request.key, False, code=match.UNREAD_MARGIN, detail="the free reader is not sure"))
        return out

    return read


def _press(caps: Path, *, engine: str = "marqo-b", dry_run: bool = False, ready: bool = True,
           reader=None, sent=None):
    """One `identify` press over `caps`, in the current isolated home. Every paid request meets a stub
    transport that refuses it (`sent` collects the custom ids asked for), and the free reader is
    `reader`. Returns the exit code and every line the press said."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import batch

    argv = ["identify", str(caps), "--engine", engine] + (["--dry-run"] if dry_run else [])
    asked: list = [] if sent is None else sent

    def refuse(requests, log=None, on_submit=None):
        outcomes = {}
        for request in requests:
            asked.append(request.custom_id)
            outcomes[request.custom_id] = batch.Outcome(
                request.custom_id, batch.UNKNOWN_STRATEGY, error="the stub refuses this card"
            )
        return batch.BatchRun(outcomes=outcomes)

    lines: list = []
    real_run_batch = cmd_identify.batch.run_batch
    cmd_identify.batch.run_batch = refuse
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(match, "status", lambda *_a, **_k: {"ready": ready}))
            stack.enter_context(mock.patch.object(match, "Index", _FakeIndex))
            if reader is not None:
                stack.enter_context(mock.patch.object(match, "read", reader))
            with quiet():
                code = cmd_identify.run(cli_entry.build_parser().parse_args(argv), lines.append)
    finally:
        cmd_identify.batch.run_batch = real_run_batch
    return code, lines


def _state(key: str) -> str:
    from store.session import Store

    return Store().read().inventory.cards[key].state


def _retired(key: str) -> list:
    return [event for event in events_for(key) if event.get("event") == "retired"]


def _second_look_code(key: str):
    """The code the run record gives a card's second look, or None when the record names none."""
    from cli import runs

    run = runs.latest()
    if run is None:
        return None
    card = run.read_identifications()["cards"].get(key, {})
    return (card.get("second_look") or {}).get("code")


def check_dark_weak_retires_captured_card(checks: Checks) -> None:
    from cli import runs
    from store import master

    checks.note("")
    checks.note("DARK AND WEAK — a captured card whose photograph is dark, with a weak best match, is retired")
    with isolated_home() as home:
        _store_captures(7, 2)
        caps = _caps(Path(home) / "caps", 7, {1: DARK, 2: CARD})
        seen: list = []
        code, _lines = _press(caps, reader=_reader({"7-001.jpg": 0.2}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0 over the stub transport")
        checks.ok("7/1" in seen, "the dark photograph reached the free read")
        checks.equal(_state("7/1"), master.RETIRED, "the dark card with a weak best match is retired")
        checks.equal(_state("7/2"), master.CAPTURED, "the bright card beside it stays captured")
        retired = _retired("7/1")
        checks.equal(len(retired), 1, "one retired event names the card")
        event = retired[0] if retired else {}
        checks.equal(event.get("reason"), CODE, "the event carries reason empty_slot")
        checks.ok(isinstance(event.get("p99"), float) and event["p99"] < 100,
                  "the event carries the 99th-percentile luminance", f"event={event!r}")
        checks.equal(event.get("best_match"), 0.2, "the event carries the best raw cosine")
        run = runs.latest()
        checks.equal(event.get("identify_run"), run.directory.name if run else None,
                     "the event names the identify run")


def check_dark_strong_stays_captured(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("DARK AND STRONG — a dark photograph whose best match is strong stays captured")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        seen: list = []
        code, _lines = _press(caps, reader=_reader({"7-001.jpg": 0.8}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0")
        checks.equal(_second_look_code("7/1"), CODE,
                     "the empty slot reached the empty decision (its second look names it)")
        checks.equal(_state("7/1"), master.CAPTURED, "the dark card with a strong best match stays captured")
        checks.equal(_retired("7/1"), [], "and no retired event is written")


def check_bright_photograph_is_not_empty(checks: Checks) -> None:
    checks.note("")
    checks.note("BRIGHT — a bright photograph is never an empty slot, and never retired")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        dark_card = folder / "dark-card.jpg"
        card_photo((30, 30, 60)).save(dark_card, "JPEG")
        checks.ok(match.empty_slot(dark_card) is False,
                  "a dark-coloured card with a bright band is not an empty slot")
        flat = _jpeg(folder / "flat.jpg", np.full(FRAME, CARD, np.uint8))
        checks.ok(match.empty_slot(flat) is False, "a flat bright card is not an empty slot")
    with isolated_home() as home:
        _store_captures(7, 2)
        caps = _caps(Path(home) / "caps", 7, {1: CARD, 2: CARD})
        seen: list = []
        code, _lines = _press(caps, reader=_reader({"7-001.jpg": 0.2, "7-002.jpg": 0.2}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0")
        checks.ok("7/1" in seen and "7/2" in seen, "both bright photographs reached the free read")
        checks.ok(_second_look_code("7/1") != CODE, "a bright card is not filed as an empty slot",
                  f"second look code={_second_look_code('7/1')!r}")
        checks.equal(_retired("7/1") + _retired("7/2"), [], "and a bright card with a weak match is not retired")


def check_dark_without_score_stays_in_main(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("NO SCORE — a dark photograph with no free read stays in main")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        code, _lines = _press(caps, engine="haiku")
        checks.equal(code, 0, "`identify --engine haiku` exits 0 over the stub transport")
        checks.equal(_second_look_code("7/1"), CODE,
                     "the empty slot reached the empty decision (its second look names it)")
        checks.equal(_state("7/1"), master.CAPTURED, "under haiku the dark card stays captured")
        checks.equal(_retired("7/1"), [], "and no retired event is written")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        seen: list = []
        code, _lines = _press(caps, ready=False, reader=_reader({"7-001.jpg": 0.2}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0 with the index not ready")
        checks.ok("7/1" not in seen, "the free read never ran, so the dark card has no score")
        checks.equal(_second_look_code("7/1"), CODE,
                     "the empty slot reached the empty decision (its second look names it)")
        checks.equal(_state("7/1"), master.CAPTURED, "with no score the dark card stays captured")
        checks.equal(_retired("7/1"), [], "and no retired event is written")


def check_identified_or_sold_card_is_not_retired(checks: Checks) -> None:
    from server import capture_server
    from store import master
    from store.session import Store

    checks.note("")
    checks.note("IDENTIFIED OR SOLD — a dark photograph on a card already identified or sold is not retired")
    with isolated_home() as home:
        _store_captures(7, 2)
        with Store().write() as snapshot:
            for key in ("7/1", "7/2"):
                snapshot.inventory.record_identification(
                    key, name="Dunsparce", number="120/159", printed_total="159",
                    confidence="high", detected_finish=None, run="an-earlier-run",
                )
        capture_server.do_mark_sold(7, 2, {})
        caps = _caps(Path(home) / "caps", 7, {1: DARK, 2: DARK})
        seen: list = []
        code, _lines = _press(caps, reader=_reader({"7-001.jpg": 0.2, "7-002.jpg": 0.2}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0")
        checks.equal(_second_look_code("7/1"), CODE,
                     "the dark identified card reached the empty decision (its second look names it)")
        checks.equal(_state("7/1"), master.IDENTIFIED, "the identified card keeps its state")
        checks.equal(_state("7/2"), master.SOLD, "the sold card keeps its state")
        checks.equal(_retired("7/1") + _retired("7/2"), [], "and neither card is retired")


def check_blank_cached_answer_is_not_adopted_for_dark(checks: Checks) -> None:
    from cli import cmd_identify
    from identify import images
    from store import cache as cache_mod
    from store import master
    from store.session import Store

    checks.note("")
    checks.note("BLANK CACHE — a blank saved answer never files a dark photograph; a human answer is left alone")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        digest = images.sha256_of(caps / "7-001.jpg")
        with Store().write() as snapshot:
            snapshot.cache.put("7/1", {}, digest, "t7-fingerprint", engine=cache_mod.ENGINE_HAIKU)
        checks.ok(Store().read().cache.reusable("7/1", digest) is not None,
                  "control: the blank answer is held for this photograph")
        sent: list = []
        code, _lines = _press(caps, engine="haiku", sent=sent)
        checks.equal(code, 0, "`identify --engine haiku` exits 0")
        checks.equal(_second_look_code("7/1"), CODE,
                     "the blank dark card reached the empty decision (its second look names it)")
        checks.equal(_state("7/1"), master.CAPTURED, "the blank answer is not adopted: the card stays captured")
        checks.ok(cmd_identify._custom_id("7/1") not in sent,
                  "and the paid transport is never asked for the empty slot")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        digest = images.sha256_of(caps / "7-001.jpg")
        with Store().write() as snapshot:
            snapshot.cache.entries["7/1"] = cache_mod.CacheEntry(
                identification={}, photo_sha256=digest, prompt_fingerprint="t7-fingerprint",
                at=cache_mod.now(), cleared_by_human=True, engine=cache_mod.ENGINE_HAIKU,
            )
        before = Store().read().cache.get("7/1")
        code, _lines = _press(caps, engine="haiku", sent=[])
        after = Store().read().cache.get("7/1")
        checks.equal(
            (after.cleared_by_human, after.identification, after.photo_sha256) if after else None,
            (before.cleared_by_human, before.identification, before.photo_sha256) if before else None,
            "a human-cleared blank answer is left exactly as it was",
        )
        checks.equal(_retired("7/1"), [], "and a cleared answer does not retire the card")


def check_retire_cut_is_strict(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("THE CUT — a best match of exactly 0.40 stays captured; 0.3999 is retired")
    with isolated_home() as home:
        _store_captures(7, 2)
        caps = _caps(Path(home) / "caps", 7, {1: DARK, 2: DARK})
        seen: list = []
        code, _lines = _press(caps, reader=_reader({"7-001.jpg": 0.40, "7-002.jpg": 0.3999}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b` exits 0")
        checks.equal(_state("7/1"), master.CAPTURED, "a best match of exactly 0.40 is not weak: the card stays captured")
        checks.equal(_retired("7/1"), [], "and writes no retired event")
        checks.equal(_state("7/2"), master.RETIRED, "a best match of 0.3999 is weak: the card is retired")
        checks.equal([event.get("best_match") for event in _retired("7/2")], [0.3999],
                     "and its event carries 0.3999")


def check_dry_run_counts_empty_slots_and_writes_nothing(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("DRY RUN — the quote counts the empty slots and the home tree stays byte-identical")
    with isolated_home() as home:
        _store_captures(7, 2)
        caps = _caps(Path(home) / "caps", 7, {1: DARK, 2: CARD})
        before = tree_digest(Path(home))
        seen: list = []
        code, lines = _press(caps, dry_run=True, reader=_reader({"7-001.jpg": 0.2}, seen))
        checks.equal(code, 0, "`identify --engine marqo-b --dry-run` exits 0")
        empty = [line for line in lines if line.startswith("empty slot")]
        checks.ok(len(empty) == 1 and "1 photograph(s)" in empty[0] and "1 would be retired" in empty[0],
                  "the quote counts one empty slot and says it would be retired", f"lines: {empty!r}")
        checks.equal(tree_digest(Path(home)), before, "a dry run writes nothing: the home tree is unchanged")
        checks.equal(_state("7/1"), master.CAPTURED, "and the dark card stays captured")
    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK})
        code, lines = _press(caps, dry_run=True, ready=False)
        checks.equal(code, 0, "`identify --engine marqo-b --dry-run` exits 0 with the index not ready")
        empty = [line for line in lines if line.startswith("empty slot")]
        checks.ok(len(empty) == 1 and "none is counted as retired" in empty[0],
                  "with no free read the quote counts none as retired", f"lines: {empty!r}")


def check_store_backed_join_files_empty_slot(checks: Checks) -> None:
    from cli import resolve, runs
    from store.session import Store

    checks.note("")
    checks.note("STORE-BACKED JOIN — an empty slot is filed as card_not_detected; a bright card gets no second look")
    with isolated_home():
        _store_captures(7, 2)
        _dress_stored(7, 1, DARK)
        _dress_stored(7, 2, CARD)
        payload = resolve.store_payload(["7/1", "7/2"], Store().read().inventory)
        checks.equal((payload["cards"]["7/1"].get("second_look") or {}).get("code"), CODE,
                     "the store payload names the empty slot in second_look")
        checks.equal(payload["cards"]["7/2"].get("second_look"), None,
                     "a bright unidentified card keeps second_look None")
        run = runs.create("t7-empty-join")
        export = write_export(run.path("export.csv"))
        resolved = resolve.load_from_store(run, ["7/1", "7/2"], {"pokemon": export})
        filed = {failure.key: failure for failure in resolved.failures}
        checks.equal(getattr(filed.get("7/1"), "reason", None), "card_not_detected",
                     "the store-backed join files the empty slot as card_not_detected")
        checks.ok(getattr(filed.get("7/1"), "photo", None), "and carries its photograph")
        checks.ok(getattr(filed.get("7/2"), "reason", None) != "card_not_detected",
                  "the bright card is not filed as an empty slot")


def check_manual_retire_refuses_empty_slot_reason(checks: Checks) -> None:
    from server import capture_server
    from store import master

    checks.note("")
    checks.note("MANUAL RETIRE — the route refuses the automatic reason")
    with isolated_home():
        _store_captures(7, 1)
        refusal(checks, lambda: capture_server.do_retire(7, 1, {"reason": CODE}),
                "retire_reason_invalid", "the retire route refuses reason empty_slot")
        checks.equal(_state("7/1"), master.CAPTURED, "and the card is not retired")


@contextlib.contextmanager
def _real_read(index, listed):
    """The real `match.read` and `_read_chunk` run. Stubbed: the index handle, the crop and the embed
    (the photograph model is not on the harness), the set names the catalogue lists, and the status."""
    query = np.array([1.0, 0.0], np.float32)
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.object(match, "Index", lambda *_a, **_k: index))
        stack.enter_context(mock.patch.object(match, "_crop", lambda *_a: object()))
        stack.enter_context(mock.patch.object(match, "embed", lambda cards, _model=None: [query for _ in cards]))
        catalog = listed if isinstance(listed, _BrokenCatalog) else _Catalog(listed)
        stack.enter_context(mock.patch.object(match, "_stock_images", lambda: catalog))
        stack.enter_context(mock.patch.object(match, "status", lambda *_a, **_k: {"ready": True}))
        yield


def _press_real(caps: Path):
    """`identify --engine marqo-b` over `caps`, through the real read. Returns the exit code and the
    custom ids the paid transport was asked for."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify
    from identify import batch

    asked: list = []

    def refuse(requests, log=None, on_submit=None):
        outcomes = {}
        for request in requests:
            asked.append(request.custom_id)
            outcomes[request.custom_id] = batch.Outcome(
                request.custom_id, batch.UNKNOWN_STRATEGY, error="the stub refuses this card"
            )
        return batch.BatchRun(outcomes=outcomes)

    real_run_batch = cmd_identify.batch.run_batch
    cmd_identify.batch.run_batch = refuse
    try:
        with quiet():
            code = cmd_identify.run(
                cli_entry.build_parser().parse_args(["identify", str(caps), "--engine", "marqo-b"]),
                lambda _line: None,
            )
    finally:
        cmd_identify.batch.run_batch = real_run_batch
    return code, asked


def _real_outcome(index, listed, hint=None, game="riftbound"):
    """One captured dark card, pressed through the real read over `index`. Returns the exit code, the
    card's state, its retired events, its second-look code, and whether the paid read was asked for it."""
    from cli import cmd_identify

    with isolated_home() as home:
        _store_captures(7, 1)
        caps = _caps(Path(home) / "caps", 7, {1: DARK}, game=game, hint=hint)
        with _real_read(index, listed):
            code, asked = _press_real(caps)
        paid = cmd_identify._custom_id("7/1") in asked
        return code, _state("7/1"), _retired("7/1"), _second_look_code("7/1"), paid


def check_wrong_set_hint_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("WRONG HINT — a dark card whose set hint names another set is not retired on that set's score")
    index = _PoolIndex({"Base Set": [("1", "1", 0.9)], "Other Set": [("2", "2", 0.2), ("3", "3", 0.1)]})
    code, state, retired, second, paid = _real_outcome(index, ["Base Set", "Other Set"], hint="Other Set")
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 through the real read")
    checks.equal(second, CODE, "the dark card reached the empty decision (its second look names it)")
    checks.equal(state, master.CAPTURED,
                 "the whole pool holds the card's own printing, so the wrong hint does not retire it")
    checks.equal(retired, [], "and no retired event is written")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


def check_index_missing_the_card_set_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("MISSING SET — the index does not hold the set that lists the card's printing, so no retire")
    index = _PoolIndex({"Base Set": [("1", "1", 0.2), ("2", "2", 0.1)], "Other Set": [("9", "9", 0.9)]},
                       held=["Base Set"])
    code, state, retired, second, paid = _real_outcome(index, ["Base Set", "Other Set"])
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 through the real read")
    checks.equal(second, CODE, "the dark card reached the empty decision (its second look names it)")
    checks.equal(state, master.CAPTURED, "the index is incomplete, so there is no whole pool and no retire")
    checks.equal(retired, [], "and no retired event is written")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


def check_promo_with_unfilled_set_name_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("UNFILLED PROMO — a promo listed by the catalogue whose set name is not filled in is not held, so no retire")
    index = _PoolIndex({"Base Set": [("1", "1", 0.2)], "Promo Set": [("P1", "1", 0.9)]}, held=["Base Set"])
    code, state, retired, second, paid = _real_outcome(index, ["Base Set", "Promo Set"])
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 through the real read")
    checks.equal(second, CODE, "the dark card reached the empty decision (its second look names it)")
    checks.equal(state, master.CAPTURED, "a promo with no filled set name leaves the pool incomplete, so no retire")
    checks.equal(retired, [], "and no retired event is written")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


def check_full_pool_weak_retires_captured_card(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("FULL POOL WEAK — every listed set is held and every printing is weak: the card is retired")
    index = _PoolIndex({"Base Set": [("1", "1", 0.2)], "Second Set": [("2", "2", 0.3)]})
    code, state, retired, second, paid = _real_outcome(index, ["Base Set", "Second Set"])
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 through the real read")
    checks.equal(state, master.RETIRED, "the whole pool is complete and weak, so the captured card is retired")
    checks.equal([event.get("best_match") for event in retired], [0.3],
                 "and the one event carries the top raw cosine of the whole pool")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


def check_inventory_retire_refuses_empty_slot_reason(checks: Checks) -> None:
    from store import master
    from store.session import Store

    checks.note("")
    checks.note("GENERAL PATH — Inventory.retire refuses the automatic reason; only retire_empty_slot writes it")
    with isolated_home():
        _store_captures(7, 1)
        with Store().write() as snapshot:
            checks.raises(master.UnknownRetireReason,
                          lambda: snapshot.inventory.retire("7/1", CODE),
                          "Inventory.retire(reason='empty_slot') is refused on the general path")
        checks.equal(_state("7/1"), master.CAPTURED, "and the card is not retired through it")


def check_no_listed_groups_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("NO LISTED GROUPS — a catalogue that lists no sets for the game has no whole pool, so no retire")
    index = _PoolIndex({"Base Set": [("1", "1", 0.2)], "Second Set": [("2", "2", 0.3)]})
    with _real_read(index, []):
        checks.equal(_whole_pool_answer(index, "riftbound"), None,
                     "the catalogue lists no sets, so `_whole_pool` answers None")
    code, state, retired, second, paid = _real_outcome(index, [])
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 through the real read")
    checks.equal(second, CODE, "the dark card reached the empty decision (its second look names it)")
    checks.equal(state, master.CAPTURED, "with no whole pool there is no best match, so the card stays captured")
    checks.equal(retired, [], "and no retired event is written")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


def check_stale_model_or_unserved_game_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("MODEL AND GAME GATE — an index built by another model, or a game the matcher does not serve, has no whole pool")
    weak = {"Base Set": [("1", "1", 0.2)], "Second Set": [("2", "2", 0.3)]}
    listed = ["Base Set", "Second Set"]
    stale = _StaleIndex(weak)
    with _real_read(stale, listed):
        checks.equal(_whole_pool_answer(stale, "riftbound"), None, "a stale model sha answers None")
        checks.equal(_whole_pool_answer(_PoolIndex(weak), "misc"), None, "an unserved game answers None")
    code, state, retired, second, paid = _real_outcome(stale, listed)
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 with a stale model sha")
    checks.equal(second, CODE, "the dark card reached the empty decision with a stale model sha")
    checks.equal(state, master.CAPTURED, "a stale model sha gives no whole pool, so the card stays captured")
    checks.equal(retired, [], "and no retired event is written")
    code, state, retired, second, paid = _real_outcome(_PoolIndex(weak), listed, game="misc")
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 for an unserved game")
    checks.equal(second, CODE, "the dark card reached the empty decision for an unserved game")
    checks.equal(state, master.CAPTURED, "an unserved game gives no whole pool, so the card stays captured")
    checks.equal(retired, [], "and no retired event is written")


def check_failed_catalog_read_does_not_retire(checks: Checks) -> None:
    from store import master

    checks.note("")
    checks.note("CATALOGUE RAISES — a catalogue read that raises proves nothing, so no whole pool and no retire")
    index = _PoolIndex({"Base Set": [("1", "1", 0.2)], "Second Set": [("2", "2", 0.3)]})
    with _real_read(index, _BrokenCatalog()):
        checks.equal(_whole_pool_answer(index, "riftbound"), None, "a catalogue read that raises answers None")
    code, state, retired, second, paid = _real_outcome(index, _BrokenCatalog())
    checks.equal(code, 0, "`identify --engine marqo-b` exits 0 when the catalogue read raises")
    checks.equal(second, CODE, "the dark card reached the empty decision when the catalogue read raises")
    checks.equal(state, master.CAPTURED, "with no whole pool the card stays captured")
    checks.equal(retired, [], "and no retired event is written")
    checks.ok(not paid, "and the paid read is never asked for the dark card")


CHECKS = (
    check_empty_slot_fixtures,
    check_empty_slot_boundary,
    check_empty_slot_keeps_thin_lines,
    check_read_names_empty_slot,
    check_haiku_press_never_sends_an_empty_slot,
    check_dry_run_quote_leaves_the_empty_slot_out,
    check_dark_weak_retires_captured_card,
    check_dark_strong_stays_captured,
    check_bright_photograph_is_not_empty,
    check_dark_without_score_stays_in_main,
    check_identified_or_sold_card_is_not_retired,
    check_blank_cached_answer_is_not_adopted_for_dark,
    check_retire_cut_is_strict,
    check_dry_run_counts_empty_slots_and_writes_nothing,
    check_store_backed_join_files_empty_slot,
    check_manual_retire_refuses_empty_slot_reason,
    check_wrong_set_hint_does_not_retire,
    check_index_missing_the_card_set_does_not_retire,
    check_promo_with_unfilled_set_name_does_not_retire,
    check_full_pool_weak_retires_captured_card,
    check_inventory_retire_refuses_empty_slot_reason,
    check_no_listed_groups_does_not_retire,
    check_stale_model_or_unserved_game_does_not_retire,
    check_failed_catalog_read_does_not_retire,
)
