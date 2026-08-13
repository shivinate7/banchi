"""Capture server — build-order step 5, plus the one route step 7a adds.

    POST   /capture                   take a photo into the next position in a box
    GET    /status                    counts, next index per box, store health
    GET    /photo/<box>/<index>       the stored JPEG bytes
    GET    /inventory                 the whole card map, each row carrying its label
    PUT    /inventory/<box>/<index>   correct the set hint or variant on one card
    DELETE /inventory/<box>/<index>   undo the newest capture: every trace of one position

The first five are build-order step 5 in `docs/GATES.md`. The sixth is the capture app's
undo, and it lives here rather than in the app because deleting a record, a sidecar, a
photo, two queue entries and a paid answer together is a store write, and D13 keeps exactly
one writer for those — the app has no filesystem and no lock. Everything else that app needs
already existed at step 5.

Still absent and still deliberate: no identification, no pricing, no mark-sold, no UI. This
process never spends money: it holds no API key and makes no outbound call.

EVERY WRITE GOES THROUGH `store.session.Store.write()`. The server never touches
`inventory.json` and never writes a photo outside that lock. `store/__init__.py` calls it
"a second writer, not a second owner", which concretely means the server holds no
authoritative copy of anything between requests: no cache, no dirty set, no periodic flush.
Reads take no lock at all, because every write is an atomic replace — and because the lock
is exclusive-only, a server that locked to read would serialise both devices' polling
behind every write and then fail after the 30-second timeout.

POSITIONS ARE NEVER CHOSEN HERE. `Inventory.allocate_capture` assigns them, takes no index,
and runs inside the same lock as the record it writes. Any design where this file computes
an index and hands it to a writer is the lost update `store/__init__.py` exists to warn
about — two devices both showing "next: 17", both posting, the second silently overwriting
the first.

PHOTO LAYOUT is box-keyed (D6, D13), under `<home>/captures/cards/box<N>/<index>.jpg` with
a JSON sidecar beside it. The `cards` level is not decoration: `identify.sidecar.scan`
walks its root recursively and turns EVERY file with a photo suffix into a capture and
therefore a paid Batch request, and `scripts/screenshot.sh` writes UI renders into
`captures/ui/`. Rooting at `captures/` would bill every screenshot. Nothing but card photos
and their sidecars may ever be written below `captures/cards/`.

T7 REACHES THIS FILE, as of 2026-08-13, and the paragraph here used to say the opposite —
which was true when this module shipped at step 5 and stopped being true the day
`harness/tests/t7_store_and_seams.py` landed. It imports this module and calls every route
in it: allocation and its refusal codes, `/status` on a healthy store and on a corrupt
record, the sidecar seam `identify.sidecar` reads back, `GET /inventory` and the position it
renders, two- and four-way concurrent captures over real sockets, and each of the DELETE
route's rules — what it removes, that it removes only the newest card in a box, and that it
refuses once `emit` has written the card's row into an import file.

WHAT T7 STILL DOES NOT REACH, from `docs/DEBTS.md`, so a green harness is read for what it
is. Three named cases rather than a package nobody looks at:

  twenty-way contention   T7 runs two and four simultaneous captures, matching D5's two
                          devices. The twenty-way case is what found `request_queue_size`
                          at its default of 5 — 8 served, 12 reset by the OS — and if that
                          constant below is ever lowered, nothing will notice.
  the bare-interpreter    `make server` runs this on system `python3` with no venv. T7
  start                   imports the module under whichever interpreter runs the harness,
                          so it cannot see a missing dependency that the harness supplies.
  the PUT history line    a correction through `do_put_card` appends nothing to
                          `history.jsonl`. T7 asserts the correction reaches the sidecar,
                          which is the part that costs money when it fails; the missing
                          history line is still missing.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

# `make server` runs this by path, so sys.path[0] is server/ and the project packages are
# not importable without this. Same idiom and same reason as harness/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import join, variant  # noqa: E402
from store import Store, files, master  # noqa: E402

HOST = "0.0.0.0"
PORT = 8000

CAPTURES_DIRNAME = "captures"
CARDS_DIRNAME = "cards"
PHOTO_SUFFIX = ".jpg"
SIDECAR_SUFFIX = ".json"
INDEX_PAD = 4

# A 24 MB ceiling on one decoded image. A phone JPEG is 2-5 MB; this refuses a body that
# would sit in memory on a threaded server rather than trusting the client's Content-Length.
MAX_IMAGE_BYTES = 24 * 1024 * 1024

# The server writes `.jpg` and only `.jpg`, so `GET /photo` can find a file from a box and
# an index alone. It therefore verifies the bytes rather than converting them: re-encoding
# at capture time belongs to the batch step, and writing a PNG under a `.jpg` name is a lie
# that surfaces three stages downstream.
JPEG_MAGIC = b"\xff\xd8\xff"

CORS_HEADERS = (
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type"),
)

_PHOTO_RE = re.compile(r"^/photo/(\d+)/(\d+)$")
_INVENTORY_ITEM_RE = re.compile(r"^/inventory/(\d+)/(\d+)$")

# Fields a PUT may change. Both are operator claims recorded at capture time, so correcting
# a mis-toggled stack is exactly what this route is for. Nothing about listing state is
# settable here — those transitions belong to identify, join and emit.
PUT_FIELDS = ("set_hint", "variant")

# States at which a card may still be undone. D10 draws the line at `emit`: up to `pushed`
# nothing outside this Mac knows the card exists, so removing it costs the identification
# fee and nothing else, while after it a file on disk would disagree with the inventory.
#
# Written as the ALLOWED set rather than the refused one, which is not a style choice: a
# state added to `store.master.STATES` later is then refused by default. The inverse spells
# out `pushed, staged, live, sold` and silently permits whatever comes next, and the failure
# that produces is an undo that deletes a card TCGplayer already knows about.
UNDOABLE_STATES = (master.CAPTURED, master.IDENTIFIED)


class BadRequest(ValueError):
    """A request this server refuses, carrying the status and code to answer with."""

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


# --------------------------------------------------------------------------------- paths


def captures_root() -> Path:
    """Where card photos live. Moves with `PKMNSCAN_HOME`, as the rest of the store does."""
    return files.home() / CAPTURES_DIRNAME / CARDS_DIRNAME


def photo_path(box: int, index: int) -> Path:
    """`<root>/box3/0017.jpg`.

    The stem is the index and nothing else. `identify.sidecar` strips the box marker and
    then reads the LAST run of digits in what remains, so a stem like `0017.2` parses as
    index 2. Zero-padded to four because `scan()` sorts by path string.
    """
    return captures_root() / f"box{int(box)}" / f"{int(index):0{INDEX_PAD}d}{PHOTO_SUFFIX}"


def sidecar_path(photo: Path) -> Path:
    return photo.with_suffix(SIDECAR_SUFFIX)


def sidecar_payload(box: int, index: int, set_hint, metadata_finish) -> dict:
    """What `identify.sidecar.load` reads back.

    Keys are chosen against that reader, not invented here. `box` is read from `box` alone;
    the index is read from `index`, and note that `position` is an accepted ALIAS for the
    same integer — never write it. `store.master.position_key` returns the string "3/17"
    for what it calls a position, and a sidecar carrying `{"position": "3/17"}` fails the
    integer coercion, falls back to the filename, and — because a valid `box` is also
    present — is recorded as having come from its sidecar with no problem noted. That is
    undetectable in exactly the shape this server writes, which is why only `index` appears.

    A hint or a toggle the operator did not set is omitted rather than written null. The
    reader treats absent and null identically, so this costs nothing and keeps the file a
    record of claims actually made (D3 rung 1: the toggle is a claim, not a hint).
    """
    payload = {"box": int(box), "index": int(index)}
    if set_hint:
        payload["set_hint"] = set_hint
    if metadata_finish:
        payload["variant"] = metadata_finish
    return payload


# ---------------------------------------------------------------------- request decoding


def _require_box(payload: dict) -> int:
    raw = payload.get("box")
    if raw is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, "box_required", "Send a box number.")
    try:
        box = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "box_invalid", f"box was {raw!r}; send a whole number."
        ) from None
    if box < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "box_invalid", f"box was {box}; boxes start at 1."
        )
    return box


def _require_image(payload: dict) -> bytes:
    raw = payload.get("image")
    if not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "image_required", "Send the photo as base64 in `image`."
        )
    try:
        blob = base64.b64decode(raw, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "image_invalid", "`image` is not valid base64."
        ) from None
    if len(blob) > MAX_IMAGE_BYTES:
        raise BadRequest(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "image_too_large",
            f"{len(blob)} bytes exceeds the {MAX_IMAGE_BYTES} byte ceiling.",
        )
    if not blob.startswith(JPEG_MAGIC):
        raise BadRequest(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "image_not_jpeg",
            "Send JPEG bytes. The server stores what it is given and never converts.",
        )
    return blob


def _optional_variant(payload: dict) -> Optional[str]:
    raw = payload.get("variant")
    if raw is None or raw == "":
        return None
    text = str(raw).strip()
    if text not in variant.FINISHES:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "variant_invalid",
            f"variant was {raw!r}; use one of {', '.join(sorted(variant.FINISHES))}.",
        )
    return text


def _optional_text(payload: dict, key: str) -> Optional[str]:
    raw = payload.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


# -------------------------------------------------------------------------------- routes


def do_capture(payload: dict) -> Tuple[HTTPStatus, dict]:
    """Allocate the next position in a box, store the photo, record the card.

    Order matters and is not arbitrary. The index is unknown until `allocate_capture`
    returns, and the filename is derived from it, so the photo cannot be written first.
    Everything therefore happens inside one `Store.write()`: if the photo or sidecar write
    raises, the exception leaves the block and the session commits nothing, so there is no
    record pointing at a file that was never written.
    """
    box = _require_box(payload)
    blob = _require_image(payload)
    set_hint = _optional_text(payload, "set_hint")
    metadata_finish = _optional_variant(payload)
    capture_id = _optional_text(payload, "capture_id")

    with Store().write() as snapshot:
        card, created = snapshot.inventory.allocate_capture(
            box,
            capture_id=capture_id,
            set_hint=set_hint,
            metadata_finish=metadata_finish,
        )
        if created:
            path = photo_path(card.box, card.index)
            path.parent.mkdir(parents=True, exist_ok=True)
            files.write_atomic(path, blob)
            files.write_json(
                sidecar_path(path),
                sidecar_payload(card.box, card.index, set_hint, metadata_finish),
            )
            # Set after the write, because the path is not knowable before the index. The
            # history event `record_capture` already appended carries the position and a
            # null photo for that reason; the record itself carries the path.
            card.photo = str(path)
        body = _card_summary(card, created=created)

    return (HTTPStatus.CREATED if created else HTTPStatus.OK), body


def _card_summary(card: master.Card, *, created: bool) -> dict:
    position = join.Position(int(card.box), int(card.index))
    return {
        "box": int(card.box),
        "index": int(card.index),
        "key": card.key,
        "label": position.label,
        "section": position.section,
        "card": position.card,
        # True only on the first capture into a box. The app should confirm the box number
        # with the operator when it sees this: a typo like box 33 for box 3 is a valid int,
        # a real photo and a real listing, and nothing downstream can tell. It catches the
        # FIRST typo only — a second into the same phantom box looks ordinary.
        "new_box": created and int(card.index) == 1,
        "created": created,
        "photo": card.photo,
        "capture_id": card.capture_id,
    }


def do_status() -> dict:
    """Lock-free. Counts, the next index per box, and whether the inventory parses.

    Deliberately does NOT probe the lock. The only primitive the store exposes is an
    acquire, so reporting on it would make a read route a writer.
    """
    snapshot = Store().read()
    inventory = snapshot.inventory

    body = {
        "captures_root": str(captures_root()),
        "store": str(files.inventory_dir()),
        "store_exists": files.inventory_dir().is_dir(),
        "cards": len(inventory.cards),
        "states": inventory.counts(),
        "queues": {
            "review": len(snapshot.review.entries),
            "parked": len(snapshot.parked.entries),
        },
    }

    # A corrupt record must not take down the health endpoint — that is the one route you
    # reach for when something is wrong. Report it as a finding instead.
    try:
        boxes = sorted({int(card.box) for card in inventory.cards.values()})
        body["next_index"] = {str(box): inventory.next_index(box) for box in boxes}
    except (master.BadPosition, TypeError, ValueError) as exc:
        body["next_index"] = None
        body["problem"] = (
            f"the inventory holds a card whose box or index is not a number ({exc}). "
            "Positions cannot be allocated until it is corrected."
        )

    return body


def do_photo(box: int, index: int) -> bytes:
    path = photo_path(box, index)
    if not path.is_file():
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "photo_not_found",
            f"No photo stored at box {box}, card {index}.",
        )
    return path.read_bytes()


def do_inventory() -> dict:
    """The whole card map, each row decorated with its rendered position.

    DECORATED BECAUSE THE ALTERNATIVE IS A SECOND RENDERER, and the alternative is what
    happened: an undecorated row carries `box` and `index` and nothing else, so the app
    reimplemented D10's 25-cards-per-section arithmetic in TypeScript to draw a label with.
    Two copies of the rule that says where a physical card is, one edit away from
    disagreeing about it. `_card_summary` already answers POST and PUT with exactly these
    three fields, so this makes the two shapes agree rather than inventing a third.

    THE DECORATION IS WIRE-ONLY, and that is the constraint that shapes the code below.
    `Inventory.to_payload` is the on-disk format: `inventory.json` is parsed back by
    `Inventory.parse`, which filters on `Card.__annotations__` and would drop a `label`
    silently on the next reload. So the fields are added to the dict `to_payload` has just
    built out of `asdict`, on a snapshot this function then discards — they cannot reach a
    write, because nothing here holds the snapshot long enough to commit it.

    A RECORD WHOSE POSITION WILL NOT COERCE IS LEFT UNDECORATED rather than labelled. Both
    alternatives are worse. Raising takes the entire card map down over one bad row, on the
    route the app polls. A placeholder label — `Box ? · Section ?` — names a position that
    does not exist, which is the one thing a position label may never do, since D10's whole
    argument is that a printed label is worth trusting a year later. `do_status` is where a
    record like that is reported, and it reports it already.
    """
    payload = Store().read().inventory.to_payload()
    for record in (payload.get("cards") or {}).values():
        try:
            position = join.Position(int(record["box"]), int(record["index"]))
        except (KeyError, TypeError, ValueError):
            continue
        record["label"] = position.label
        record["section"] = position.section
        record["card"] = position.card
    return payload


def do_put_card(box: int, index: int, payload: dict) -> dict:
    """Correct the set hint or variant on one card that already exists.

    Per-position, never a whole-document replace: rebuilding every card from a client's
    stale snapshot is the same lost update the allocator is shaped to avoid, with a wider
    blast radius.

    This mutates the stored card directly rather than going through `record_capture`, whose
    first branch CREATES a card from whatever it is handed. A PUT naming a position that
    does not exist would otherwise invent one — logged as a capture, answered with a
    success, flagged to nobody.

    IT REWRITES THE SIDECAR TOO, and that is not housekeeping. `cli/cmd_identify.py` builds
    its card from `identify.sidecar`, not from the inventory record, so a correction that
    stopped at `inventory.json` would never reach the variant ladder: the run would take D3
    rung 2 or 3 as though no toggle had ever been set. Worse, it would not survive — the
    upsert in `record_capture` writes the sidecar's value back over the record whenever the
    sidecar has one, so a correction against a sidecar that already named a finish would be
    silently reverted by the next identify run. Measured both ways before this was written.

    The sidecar is skipped when the photo is absent — a card recorded by `emit` rather than
    captured has nothing for the reader to find, and a lone `.json` under the capture tree
    would serve no one.
    """
    key = master.position_key(box, index)
    known = {field for field in PUT_FIELDS}
    unknown = sorted(set(payload) - known)
    if unknown:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "field_not_settable",
            f"Cannot set {', '.join(unknown)} here. Settable: {', '.join(PUT_FIELDS)}.",
        )

    set_hint = _optional_text(payload, "set_hint") if "set_hint" in payload else None
    metadata_finish = _optional_variant(payload) if "variant" in payload else None

    with Store().write() as snapshot:
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. This route corrects; it never creates.",
            )
        if "set_hint" in payload:
            card.set_hint = set_hint
        if "variant" in payload:
            card.metadata_finish = metadata_finish

        photo = photo_path(card.box, card.index)
        wrote_sidecar = photo.is_file()
        if wrote_sidecar:
            files.write_json(
                sidecar_path(photo),
                sidecar_payload(card.box, card.index, card.set_hint, card.metadata_finish),
            )

        body = _card_summary(card, created=False)
        body["sidecar"] = str(sidecar_path(photo)) if wrote_sidecar else None

    # Known gap, recorded in docs/DEBTS.md rather than repaired here: a correction made
    # through this route appends nothing to history.jsonl, because the store logs state
    # transitions and this is not one. Adding a log call means editing an uncovered module.
    return body


def _unlink(path: Path) -> bool:
    """Delete a file, reporting whether one was there. Absence is not a failure.

    A card recorded by `emit` rather than captured has no photo and no sidecar, and an undo
    of one must answer 200 rather than a 500 that reads like a bug in this file. Caught
    rather than probed with `is_file()` so there is no window between the two calls — the
    store lock closes that window for other writers, but not for the operator's own Finder.
    """
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def do_delete_card(box: int, index: int) -> dict:
    """Undo one capture: the record, the queue entries and the paid answer, then the files.

    IT DELETES AND IT DOES NOT TOMBSTONE (D10). No `undone` state, no deleted flag, nothing
    in the response hinting at a third condition between captured and absent. `sold` stays
    the only way a position stops being listable while keeping its record, and it means
    sold. A soft delete was rejected in the spec rather than here, and the reason is that it
    puts a record in `inventory.json` that every consumer downstream has to learn to skip.

    ONLY THE NEWEST CARD IN THE BOX. `next_index` is a high-water mark, so deleting from the
    middle leaves a gap that can never be reused and that reads, a year later, exactly like
    the permanent gap a sale leaves. The refusal names the position that *is* undoable,
    because a refusal that does not say what would have worked costs a round trip. Deleting
    the newest releases its index instead, and that release is the allocator's own
    behaviour rather than anything arranged here: the high-water scan simply stops finding
    the record. T7 asserts it against `Inventory.next_index` directly for that reason.

    REPEATED CALLS WALK BACKWARDS, one card each, and that costs no code — every call
    deletes whatever is newest by the time it runs.

    IT CLEARS ALL FOUR STORES KEYED BY THIS POSITION, not just the inventory. The snapshot
    carries `review`, `parked` and `cache` as well, and `Store.write()` writes every one of
    them back on the way out — so dropping the record alone does not leave the others
    untouched, it commits them unchanged around a position that no longer exists. Details
    below, at the code.

    ONE `Store.write()`, the same shape `do_capture` uses — and it is NOT a transaction
    spanning the store and the filesystem, because no such thing is available here. What is
    actually guaranteed, stated exactly rather than as "atomic":

      a failing unlink        escapes the block, so nothing commits. Every edit above is
                              discarded, the record keeps its photo, and the request can be
                              repeated.
      a failure in the        leaves the record in place with its photo already gone. Undo
      commit, after the       again repairs it: the card is still the newest, still in an
      unlinks have run        undoable state, and `_unlink` treats an absent file as no
                              failure — so the retry commits what the first attempt could
                              not.

    THE FILESYSTEM WORK IS DELIBERATELY NOT MOVED AFTER THE BLOCK, which would make the
    first row cover everything and is the obvious repair. Outside the block it runs after
    the commit, and then a partial failure strands a PHOTO with no record —
    `identify.sidecar.scan` finds captures by photo suffix, so that orphan is a paid Batch
    request for a card nothing else knows about, silent until the bill. The
    record-without-photo above costs nothing and heals on a retry. Cheap and retryable beats
    expensive and silent.

    The limit underneath all of it, from `docs/specs/capture-server.md` §6.5: the session
    replaces four JSON files and appends history after the yield, each atomically but not
    together. The commit is per file, so this route cannot promise more than the rows above
    however it is ordered.

    THE PHOTO IS UNLINKED BEFORE THE SIDECAR, and that ordering is the money rule from the
    other direction. `identify.sidecar.scan` finds captures by photo suffix and reads
    sidecars beside them, so a stranded sidecar costs nothing while a stranded PHOTO is a
    paid Batch request for a card that no longer exists. Deleting the expensive one first
    means every partial failure left after it is a cheap one.
    """
    key = master.position_key(box, index)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        card = inventory.cards.get(key)
        # The high-water mark minus one: the newest card in this box, or 0 if it is empty.
        # Read inside the lock like everything else here — a value read before it would be
        # a stale claim about which position is undoable.
        newest = inventory.next_index(box) - 1

        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. "
                + (
                    f"The newest capture in that box is card {newest}."
                    if newest >= 1
                    else "That box holds no cards at all."
                ),
            )

        # STATE IS CHECKED BEFORE POSITION, deliberately. The other order answers a request
        # to undo a pushed card in the middle of a box with "card 12 is the newest, undo
        # that instead" — which invites the operator to delete good captures one at a time
        # on the way to one that could never have been removed at all.
        if card.state not in UNDOABLE_STATES:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_too_late",
                f"Box {box}, card {index} is {card.state}: its row is already in an import "
                f"file, so deleting it here would leave that file disagreeing with the "
                f"inventory. Undo stops after {' and '.join(UNDOABLE_STATES)} — correct "
                f"this card on TCGplayer instead, and leave the position alone.",
            )

        if int(index) != newest:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_not_newest",
                f"Box {box}, card {index} is not the newest capture, and a position is "
                f"never reused once it is passed. Undo removes box {box}, card {newest}; "
                f"press it again to walk back one card at a time.",
            )

        photo = photo_path(card.box, card.index)
        sidecar = sidecar_path(photo)

        # `card.photo` is deliberately not consulted as the path to delete. The layout is
        # derived from the position, the same way `do_put_card` derives it, because that is
        # the one layout this server ever writes — and a record created by `emit` carries a
        # null photo while a stale absolute path from another machine's store would send
        # this at a file that is not ours.
        del inventory.cards[key]

        # THE OTHER THREE STORES ARE KEYED BY POSITION TOO, and this is the whole of what
        # made undo leave wreckage. Measured before this was written: after undoing 3/2 the
        # record, the photo and the sidecar were gone, while `review.json` still held an
        # entry whose `photo` field named the file this route had just deleted,
        # `identifications.json` still held the paid answer, and `GET /status` went on
        # counting the phantom in `queues.review`.
        #
        # The orphan was PERMANENT rather than untidy. Nothing clears a queue entry before
        # 7b's review screen — `store/queues.py` says so out loud — and the one removal that
        # exists, `Queue.release` from `cli/cmd_join.py`, frees positions a later run
        # PROCESSED. A position with no photo is never scanned, so never processed, so never
        # released. It is also most reachable exactly where it costs most: `cli/cmd_emit.py`
        # marks only matched positions `pushed`, so a card sitting in a queue stays
        # `identified` — and `identified` is inside UNDOABLE_STATES. The undoable set and
        # the queued set overlap by construction.
        #
        # `entries.pop` RATHER THAN `Queue.release`, which is the method that already removes
        # queue entries, and the difference is deliberate. `release` preserves anything a
        # human cleared, on the stated grounds that the answer should outlive the question.
        # Here the question, the card and the photograph are all gone, and the index is
        # released — so the next capture into this box takes this very position, and a
        # preserved answer would be a human's ruling about card A attached to physical card
        # B. `Cache.put` refuses to overwrite a cleared answer for the same reason and would
        # be wrong here for the same reason. A stale answer on a new card is worse than the
        # orphan this replaces, so removal here is unconditional.
        review_deleted = snapshot.review.entries.pop(key, None) is not None
        parked_deleted = snapshot.parked.entries.pop(key, None) is not None
        cache_deleted = snapshot.cache.entries.pop(key, None) is not None

        photo_deleted = _unlink(photo)
        sidecar_deleted = _unlink(sidecar)
        released = inventory.next_index(box)

    # Known gap, the same one `do_put_card` carries: nothing is appended to history.jsonl.
    # The store logs state transitions and a deletion is not one, and there is no `undone`
    # event to log without adding a name to the enum in an uncovered module — which is the
    # tombstone this route exists not to create. What history keeps is the `captured` event,
    # and that stays true: the capture did happen. It is the record that is gone.
    return {
        "deleted": key,
        "box": int(box),
        "index": int(index),
        "photo_deleted": photo_deleted,
        "sidecar_deleted": sidecar_deleted,
        # What the other three stores gave up, reported the same way and for the same
        # reason: an undo says what it destroyed, and a card that was sitting in a review
        # queue with a paid answer against it is the case where that matters most. Booleans
        # rather than counts, because each of these files holds at most one entry per
        # position — a count could only ever be 0 or 1, and printing it as a number invites
        # the next reader to believe otherwise.
        "review_deleted": review_deleted,
        "parked_deleted": parked_deleted,
        "cache_deleted": cache_deleted,
        # The index this box will hand out next, after the release. The app redraws its
        # position from this rather than decrementing its own counter, which would drift the
        # moment the other device (D13) captured into the same box.
        "next_index": released,
    }


# ------------------------------------------------------------------------------- handler


class CaptureHandler(BaseHTTPRequestHandler):
    server_version = "pkmnscan-capture/1"
    protocol_version = "HTTP/1.1"

    # -------------------------------------------------------------------- responding

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for header, value in CORS_HEADERS:
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload) -> None:
        self._send(status, json.dumps(payload).encode("utf-8") + b"\n", "application/json")

    def _fail(self, status: HTTPStatus, code: str, message: str) -> None:
        """Every error says what happened and what to do next — DESIGN.md's copy rule
        reaches here, because step 7 shows these strings to a person."""
        self._json(status, {"error": {"code": code, "message": message}})

    # ------------------------------------------------------------------------ input

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "length_invalid", "Content-Length is not a number."
            ) from None
        if length <= 0:
            raise BadRequest(HTTPStatus.BAD_REQUEST, "body_required", "Send a JSON body.")
        # Base64 inflates by a third, and the decoded ceiling is enforced separately.
        if length > MAX_IMAGE_BYTES * 2:
            raise BadRequest(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body is too large."
            )
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "body_invalid", "Body is not valid JSON."
            ) from None
        if not isinstance(payload, dict):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "body_invalid", "Body must be a JSON object."
            )
        return payload

    # ----------------------------------------------------------------------- routing

    def _dispatch(self, handler) -> None:
        """One place to turn a refusal into a response.

        `LockTimeout`'s own text blames the capture server for holding the lock, which is a
        lie about itself when the server is the one raising it — so it is answered with a
        message that points at the other process instead of being echoed.
        """
        try:
            handler()
        except BadRequest as exc:
            self._fail(exc.status, exc.code, str(exc))
        except files.LockTimeout:
            self._fail(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "store_busy",
                "The inventory is locked by another process — most likely a running "
                "`./pkmnscan identify` or `./pkmnscan emit`. Wait for it, then retry.",
            )
        except (master.BadPosition, master.PositionOccupied, master.DuplicateCaptureId) as exc:
            self._fail(HTTPStatus.CONFLICT, "inventory_conflict", str(exc))
        except files.StoreError as exc:
            self._fail(HTTPStatus.SERVICE_UNAVAILABLE, "store_unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 — 500 is reserved for bugs, and this is one
            self.log_error("unhandled %s: %s", type(exc).__name__, exc)
            self._fail(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "server_error",
                f"{type(exc).__name__}: {exc}. This is a bug — check the server log.",
            )

    def do_OPTIONS(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/status":
                return self._json(HTTPStatus.OK, do_status())
            if path == "/inventory":
                return self._json(HTTPStatus.OK, do_inventory())
            match = _PHOTO_RE.match(path)
            if match:
                blob = do_photo(int(match.group(1)), int(match.group(2)))
                return self._send(HTTPStatus.OK, blob, "image/jpeg")
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No GET route {path}.")

        self._dispatch(run)

    def do_POST(self) -> None:  # noqa: N802
        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/capture":
                status, body = do_capture(self._body())
                return self._json(status, body)
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No POST route {path}.")

        self._dispatch(run)

    def do_PUT(self) -> None:  # noqa: N802
        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            match = _INVENTORY_ITEM_RE.match(path)
            if match:
                body = do_put_card(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No PUT route {path}.")

        self._dispatch(run)

    def do_DELETE(self) -> None:  # noqa: N802
        """Undo. No body is read: the position is the whole request.

        Answers 200 with a body rather than 204, because the app names the position it just
        removed and this response is where that name comes from. A 204 would make the app
        compose it from what it believed it was deleting — and the two disagree exactly when
        the other device (D13) has captured since.
        """

        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            match = _INVENTORY_ITEM_RE.match(path)
            if match:
                body = do_delete_card(int(match.group(1)), int(match.group(2)))
                return self._json(HTTPStatus.OK, body)
            raise BadRequest(
                HTTPStatus.NOT_FOUND, "no_such_route", f"No DELETE route {path}."
            )

        self._dispatch(run)

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.command:6} {fmt % args}")


class CaptureServer(ThreadingHTTPServer):
    """`ThreadingHTTPServer` with a listen backlog big enough for the real client.

    `socketserver` defaults `request_queue_size` to 5. That is the queue of connections the
    OS holds between SYN and `accept()`, and anything past it is reset before this process
    sees it — with HTTP/1.1 keep-alive a browser opens several connections per origin, and
    two devices (D13) reach that on their own.

    Measured before this was raised: 20 simultaneous captures, 8 served and 12 reset by the
    OS. Worth being exact about what that did and did not break, because the two are easy
    to confuse. The 8 that arrived got distinct contiguous indices, wrote 8 photos and 8
    records, and lost nothing — the lock and `allocate_capture` did their job. The other 12
    never reached the handler at all. A dropped connection is a capture the operator can
    see fail and retry; a duplicated index would be a card silently overwritten, and that
    is the failure this server is shaped to prevent.
    """

    request_queue_size = 128


def serve(host: str = HOST, port: int = PORT) -> None:
    root = captures_root()
    root.mkdir(parents=True, exist_ok=True)
    httpd = CaptureServer((host, port), CaptureHandler)
    print(f"pkmnscan capture server on http://{host}:{port}")
    print(f"  photos    {root}")
    print(f"  store     {files.inventory_dir()}")
    print("  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
