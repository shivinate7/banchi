"""Capture server — build-order step 5, plus the routes steps 7a and 7b add.

    POST   /capture                        take a photo into the next position in a box
    GET    /status                         counts, next index per box, store health
    GET    /photo/<box>/<index>            the stored JPEG bytes
    GET    /inventory                      the whole card map, each row carrying its label
    PUT    /inventory/<box>/<index>        correct the set hint or variant on one card
    DELETE /inventory/<box>/<index>        undo the newest capture: every trace of one position
    GET    /queues                         both standing queues, in the order they are worked
    POST   /review/<box>/<index>/answer    the human picks a candidate row (D4)
    POST   /inventory/<box>/<index>/sold   mark one copy sold, or put its state back

The first five are build-order step 5 in `docs/GATES.md`. The sixth is the capture app's
undo, and it lives here rather than in the app because deleting a record, a sidecar, a
photo, two queue entries and a paid answer together is a store write, and D13 keeps exactly
one writer for those — the app has no filesystem and no lock. The last three are 7b's three
screens — the review queue, the inventory views, and the Fulfillment view's mark-sold — and
they are here for the same reason: each of them ends in a write to `inventory.json`,
`review.json` or `parked.json`, and there is one writer for those.

7b IS BUILT BEFORE GATE B, WHICH `docs/specs/capture-app.md` SECTION 0 SAYS NOT TO DO. The
owner authorised it explicitly on this branch. The consequence to keep in mind while reading
the three routes below is not that they are unverified — T7 covers every one of them — but
that the DATA they move has never been produced by a real run. Every queue entry these
routes have ever seen was hand-built, here or in the harness, so wherever `docs/DESIGN.md`
does not settle a behaviour the route says so in a comment naming what would settle it,
rather than picking the plausible-looking option and leaving no trace.

Still absent and still deliberate: no identification, no pricing, no UI. This process never
spends money: it holds no API key and makes no outbound call.

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
refuses once `emit` has written the card's row into an import file. 7b's three routes landed
with their own cases in the same test, which is the schedule `docs/specs/capture-app.md`
section 3 set for the undo route and the one thing it got right about scheduling.

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
                          history line is still missing. `do_review_answer` joins it below,
                          for the same reason and with the same shrug: the store logs state
                          transitions, and writing a SKU onto a card is not one.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlparse

# `make server` runs this by path, so sys.path[0] is server/ and the project packages are
# not importable without this. Same idiom and same reason as harness/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import join, variant  # noqa: E402
from store import Store, files, master, queues  # noqa: E402

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
_REVIEW_ANSWER_RE = re.compile(r"^/review/(\d+)/(\d+)/answer$")
_SOLD_RE = re.compile(r"^/inventory/(\d+)/(\d+)/sold$")

# Fields a PUT may change. Both are operator claims recorded at capture time, so correcting
# a mis-toggled stack is exactly what this route is for. Nothing about listing state is
# settable here — those transitions belong to identify, join and emit.
PUT_FIELDS = ("set_hint", "variant")

# What a review answer carries. Both are copied verbatim off ONE candidate row the pipeline
# already offered — see `do_review_answer` for why the pair is checked against that row
# rather than trusted, and for why `condition` is required at all when the SKU implies it.
ANSWER_FIELDS = ("sku", "condition")

# Mark-sold's whole body. The sale itself needs nothing: the position is in the path and the
# state is a constant, so `{}` sells and `{"undo": true}` reverses. One route rather than a
# second `/unsold` path, because the two are one control on screen with one undo window
# (docs/DESIGN.md: undo present on every mark-sold, at least 10 seconds), and splitting them
# would let a client reach the reversal without ever having been told what it reverses.
SOLD_FIELDS = ("undo",)

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


def _require_text(payload: dict, key: str, code: str, message: str) -> str:
    """A non-empty string, or a refusal in this route's own code."""
    text = _optional_text(payload, key)
    if text is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, code, message)
    return text


def _reject_unknown(payload: dict, allowed: Sequence[str]) -> None:
    """One code for "you named a field this route does not set", shared by three routes.

    Lifted out of `do_put_card`, which had it inline and had it FIRST — before the position
    is even looked up. That order is the point and is why this is shared rather than copied:
    a body carrying an unrecognised key is almost always a client written against a
    different route, and answering it with the position's own problem sends the reader off
    debugging the wrong thing. The message names what this route does accept, so the next
    request is the right one rather than another guess.
    """
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "field_not_settable",
            f"Cannot set {', '.join(unknown)} here. Settable: {', '.join(allowed)}.",
        )


def _optional_flag(payload: dict, key: str, code: str) -> bool:
    """A JSON boolean, or a refusal. Absent means False.

    NOT `bool(raw)`, and that is the whole reason this exists rather than a `.get`. The
    string `"false"` is truthy in Python, so a client that stringified its flag — the one
    mistake this shape invites — would reverse a sale while asking not to. A flag whose two
    values are "do it" and "undo it" is the last place to accept a value it had to guess at.
    """
    raw = payload.get(key)
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            code,
            f"{key} was {raw!r}; send the JSON literal true or false, not a string.",
        )
    return raw


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


def _card_row(box: int, index: int, card: master.Card) -> dict:
    """One whole inventory record, decorated exactly as `GET /inventory` decorates its rows.

    THE SAME THREE FIELDS AND THE SAME RENDERER, so a screen holding this answer against a
    row of `GET /inventory` compares field for field — `app/src/types.ts` already types that
    shape as `InventoryCard`, and the routes below need no fourth vocabulary for a card. The
    whole record rather than `_card_summary`'s eight fields because 7b's answers change
    `sku`, `condition` and `state`, none of which that summary carries: it answers "where did
    this card land", and these two answer "what does this card say now".

    THE POSITION IS RENDERED FROM THE CALLER'S OWN INTEGERS, not from `card.box` and
    `card.index`. The record was found under `position_key(box, index)`, so those two
    integers are what identify it, and they arrive here having already matched `(\\d+)/(\\d+)`
    in the route. The stored fields may be strings — `Inventory.parse` coerces nothing — and
    rendering from them is the one way this could raise on a record the caller has already
    located. `do_inventory` has to read the record's own fields because it has no caller-
    supplied position to use, and that is exactly why it needs the try/except this does not.

    WIRE-ONLY, the same constraint `do_inventory` works under: `Inventory.parse` filters on
    `Card.__annotations__`, so a `label` reaching `inventory.json` is dropped silently on the
    next reload. `asdict` copies the record out, so there is nothing here for a commit to
    pick up even though these routes run inside `Store.write()`.
    """
    position = join.Position(int(box), int(index))
    row = asdict(card)
    row["label"] = position.label
    row["section"] = position.section
    row["card"] = position.card
    return row


def _queue_depth(queue: queues.Queue) -> Tuple[Optional[int], Optional[str]]:
    """How many cards are still waiting in one queue, or None and a finding. Never raises.

    `len(Queue)` IS A SORT, which is not obvious from the call and is what made this
    necessary. It runs `open_entries`, which orders by `QueueEntry.sort_key` — so a `market`
    that is not a number raises `decimal.InvalidOperation`, and a `box` that arrived as a
    JSON string raises `TypeError` on the tuple compare (`Queue.parse` coerces nothing).
    Both were measured escaping `/status`, the one route you reach for when something is
    wrong. It already refuses to be taken down by a bad inventory record; this is the same
    rule applied to the file 7b taught it to read.

    NULL RATHER THAN A SUBSTITUTE NUMBER. Falling back to `len(queue.entries)` would answer
    with the count of every record in the file, cleared or not — the number `do_status`
    stopped publishing on purpose, because it says there is work left after the last card
    has been answered. A count that is wrong in the direction of "there is more to do" is
    worse here than no count, since this is the number the owner works from.

    PER QUEUE, so a corrupt `review.json` does not also hide what is sitting in parked.
    """
    try:
        return len(queue), None
    except (ArithmeticError, TypeError, ValueError) as exc:
        return None, (
            f"{queues.FILENAMES[queue.name]} holds an entry that cannot be ordered "
            f"({type(exc).__name__}: {exc}), so the {queue.name} queue cannot be counted."
        )


def do_status() -> dict:
    """Lock-free. Counts, the next index per box, and whether the inventory parses.

    Deliberately does NOT probe the lock. The only primitive the store exposes is an
    acquire, so reporting on it would make a read route a writer.

    NOTHING IN HERE MAY RAISE ON BAD DATA. Every finding is reported in `problem` and the
    field it belongs to answers null. That rule is older than this route's queue counts and
    is why they are guarded the same way the inventory scan is.
    """
    snapshot = Store().read()
    inventory = snapshot.inventory
    problems: List[str] = []

    body = {
        "captures_root": str(captures_root()),
        "store": str(files.inventory_dir()),
        "store_exists": files.inventory_dir().is_dir(),
        "cards": len(inventory.cards),
        "states": inventory.counts(),
        # OPEN entries, which is what `len(Queue)` returns, what `Queue.summary` prints in
        # every run report, and what `GET /queues` hands the review screen. This counted
        # `entries` — every record in the file, cleared or not — until 7b, and the two were
        # indistinguishable because NOTHING IN THIS REPO HAD EVER SET `cleared_by_human`;
        # `store/queues.py` and `store/cache.py` both say so in their headers.
        # `do_review_answer` below is its first writer, so from here the two numbers diverge:
        # a card the owner has already answered would go on being counted here forever while
        # disappearing from the screen that works the queue. This is the number he reads to
        # decide whether there is work left, so it is the one that must not drift.
        #
        # Each side answers null when its file holds an entry that cannot be ordered —
        # `_queue_depth` has why, and why the count is not faked. `app/src/types.ts` types
        # this pair and has to widen to `number | null` to match.
        "queues": {queues.MAIN: None, queues.PARKED: None},
    }

    # Keyed off each queue's own `name`, which is where `_queue_depth` reads its filename
    # from too — so the two wire keys and the finding that explains a null one cannot come to
    # disagree about which file is meant.
    for queue in (snapshot.review, snapshot.parked):
        depth, finding = _queue_depth(queue)
        body["queues"][queue.name] = depth
        if finding:
            problems.append(finding)

    # A corrupt record must not take down the health endpoint — that is the one route you
    # reach for when something is wrong. Report it as a finding instead.
    try:
        boxes = sorted({int(card.box) for card in inventory.cards.values()})
        body["next_index"] = {str(box): inventory.next_index(box) for box in boxes}
    except (master.BadPosition, TypeError, ValueError) as exc:
        body["next_index"] = None
        problems.append(
            f"the inventory holds a card whose box or index is not a number ({exc}). "
            "Positions cannot be allocated until it is corrected."
        )

    # ONE `problem` STRING, JOINED, rather than a list or a second key. Two independent
    # findings can now be true at once, and the alternatives both cost more than they pay
    # for: a `problems` array changes the shape every client already reads for a case that
    # is rare, and a second key invites a screen that shows one of them. With one finding
    # the string is byte-identical to what this route has always answered, which is the
    # property that made joining the cheap option.
    if problems:
        body["problem"] = " ".join(problems)

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
    _reject_unknown(payload, PUT_FIELDS)

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


# ------------------------------------------------------------------------ standing queues


def _queue_row(entry: queues.QueueEntry) -> dict:
    """One waiting card, as the review screen reads it.

    `asdict` WHOLE rather than a hand-picked subset, for the reason `app/src/types.ts` gives
    for keeping the server's own field names: the first thing anyone debugging a run does is
    hold what the screen shows against `review.json`, and a projection turns that comparison
    into a lookup. It also means `candidates`, `reason`, `market` and `photo` — the four
    things `docs/DESIGN.md` draws a queue row out of — arrive because they are fields of the
    record, not because this function remembered them.

    `age_days` IS THE ONE ADDITION, and it is here because it is a property rather than a
    field, so `asdict` does not carry it. `docs/DESIGN.md` lists age among the metadata a
    queue row shows in the utility face; computing it in the app would put a second copy of
    `_age_days`'s date arithmetic there, which is the same argument `do_inventory` makes for
    the position label. Null when `first_seen` is missing or unparsable — `_age_days` already
    refuses to guess, and a placeholder age would be a claim about how long a card has waited.

    `cleared_by_human` is present and is always false in this payload, because
    `open_entries` filters on exactly that. Kept rather than stripped: it is a real field of
    the record, and a subtraction maintained by hand is the thing that drifts.

    `photo` IS A FILESYSTEM PATH ON THE MAC, exactly as `Card.photo` is — a browser cannot
    load one, and `GET /photo/<box>/<index>` is D6's route and the only way to show it.
    """
    row = asdict(entry)
    row["age_days"] = entry.age_days
    return row


def do_queues() -> dict:
    """Both standing queues, in the order they are meant to be worked.

    THE ORDER IS THE PAYLOAD'S WHOLE POINT. `Queue.open_entries` sorts priced first and
    descending, unpriced last, then box-walk order by box and index — built, running today,
    and the sort every run report has already printed. `docs/DESIGN.md` says the screen's job
    is to make that ordering visible rather than to recompute it, so this route hands the
    list over in that order and the app must not re-sort. An app-side sort is a second copy
    of `QueueEntry.sort_key` one edit away from disagreeing with the report the owner read
    before he opened the screen.

    TWO LISTS AND NOT ONE, because the separation is the point (`store/queues.py`): main is
    work, parked is the low-value queue an unidentifiable card may never be worth a tap on.
    Concatenating them here and letting the app filter would put the merge in the one place
    that cannot see why the split exists.

    LOCK-FREE, like `do_status` and `do_inventory`. Every write is an atomic replace, so a
    reader sees one whole file (`store/__init__.py`) — and a route the queue screen polls
    must not serialise itself behind a running `./pkmnscan join`, which holds the lock for
    the length of a join.

    CLEARED ENTRIES ARE ABSENT, which is what `open_entries` means. They stay in the file:
    `Queue.release` preserves them deliberately, so a human's answer outlives the question it
    answered. This route answers "what is left to do", and an answered card is not that.
    """
    snapshot = Store().read()
    return {
        "review": [_queue_row(entry) for entry in snapshot.review.open_entries],
        "parked": [_queue_row(entry) for entry in snapshot.parked.open_entries],
    }


def _candidate_with_sku(candidates: Sequence[dict], sku: str) -> Optional[dict]:
    """The offered row carrying this SKU, or None.

    String comparison on both sides. A candidate's `sku` comes from the export's
    `TCGplayer Id` column and is a string there; a client sending the same value as a JSON
    number would otherwise miss its own candidate and be told it invented one.
    """
    for candidate in candidates:
        if str(candidate.get("sku") or "") == sku:
            return candidate
    return None


def do_review_answer(box: int, index: int, payload: dict) -> dict:
    """D4's one-tap choice: the human picks one candidate row and the card takes it.

    THE SKU MUST BE ONE THE PIPELINE OFFERED, and that refusal is the reason this route is
    not a general "set the sku on a card" PUT. `CLAUDE.md`'s hard rule — never guess an
    identification, ambiguity goes to the review queue with its photo — is a rule about the
    pipeline, and a screen that could write an arbitrary SKU onto a card would be that rule
    broken by hand instead: an answer the pipeline never proposed, indistinguishable
    afterwards from one it did, on the card it was least sure about in the first place. The
    candidates recorded on the entry are the whole of what may be chosen.

    THE CONDITION IS CHECKED, NOT TRUSTED, and is required even though the SKU implies it.
    Every candidate row is one `TCGplayer Id`, so the pair is redundant on the wire — which
    is exactly what makes it worth carrying: the client says which row it believes it is
    picking, and a disagreement means the screen was drawn from a queue file that has since
    been rewritten by a join. Deriving the condition silently would accept that stale click
    and write the wrong finish onto a real card. The alternative — accepting the SKU alone —
    is one field shorter and cannot tell those two cases apart.

    IT CLEARS THE ENTRY RATHER THAN DELETING IT. `cleared_by_human` is the flag
    `store/queues.py` was built around and had never been written by anything:
    `Queue.upsert` refuses to re-queue a cleared position, `Queue.release` refuses to drop
    one, and `open_entries` hides it. Popping the entry instead would leave the next
    `./pkmnscan join` free to ask the same question again, which is the one thing that file
    says must never happen. `do_delete_card` pops rather than clears, and the difference is
    principled: there the card, the question and the photograph are all gone.

    BOTH QUEUES ARE SEARCHED AND BOTH ARE CLEARED. A position can hold an entry in each file
    — nothing in `store/queues.py` prevents it and `do_delete_card` already clears both for
    that reason — so an answer that cleared only the first would leave the screen still
    showing a card whose answer is already written.

    BUT ONLY ONE ENTRY'S CANDIDATES ARE THE OFFER, and until 2026-08-13 this validated
    against the UNION of both. Measured before this was written: a position in both files,
    review offering one SKU and a stale parked entry offering another, accepted the parked
    SKU, wrote it onto the card and cleared both queues. That is the hard rule this route
    exists to keep — never guess an identification — defeated by bookkeeping: the answer was
    one no screen ever showed for the row being answered, and afterwards it is
    indistinguishable from one the pipeline proposed. See the code for which entry governs.

    WHAT IT DELIBERATELY DOES NOT DO, three things, because each is a plausible-looking
    addition that `docs/DESIGN.md` does not ask for:

      it does not change state   The card stays `identified`. `emit` owns the move to
                                 `pushed`, and a state written here would be a second owner
                                 of a transition (`app/src/types.ts`: the app reads state and
                                 never sets it).
      it does not touch the      `store/cache.py` says the review screen writes
      identification cache       `cleared_by_human` there too, and this route does not.
                                 Marking a model answer human-cleared claims a person vouched
                                 for the NAME AND NUMBER the model read, while what was
                                 actually picked is a catalog row; the two coincide for a
                                 `low_confidence` card and come apart for a finish
                                 disagreement, where the read was never in doubt. Settled by
                                 Gate B: a real queue shows which reasons actually occur, and
                                 whether the chosen row should replace the model's answer in
                                 `identifications.json` is a decision to make with that in
                                 hand rather than now.
      it appends no history      Same gap `do_put_card` and `do_delete_card` carry, recorded
      line                       in `docs/DEBTS.md`: the store logs state transitions and
                                 writing a SKU onto a card is not one.

    ASSUMPTION, AND THE ONE WORTH READING TWICE: nothing downstream consumes this answer
    yet. `cli/cmd_emit.py` re-derives its join from the run's identifications and writes
    import rows for matched positions, so a card answered here is recorded on its own record
    and does not appear in any CSV. That is not a defect in this route — it is the seam 7b
    could not build against, because it has never seen a real review queue. What would settle
    it: Gate B produces one, and then a decision on whether `emit` reads human answers off
    `inventory.json`. Until it is made, the honest description of this route is that it
    records the owner's answer and takes the card off his screen.
    """
    _reject_unknown(payload, ANSWER_FIELDS)
    sku = _require_text(
        payload,
        "sku",
        "sku_required",
        "Send `sku` — the TCGplayer Id of the candidate row being chosen.",
    )
    condition = _require_text(
        payload,
        "condition",
        "condition_required",
        "Send `condition` — the condition string of the candidate row being chosen, "
        "copied from that row.",
    )

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        # THE CARD IS CHECKED BEFORE THE QUEUE, deliberately, and the other order was
        # considered. The answer is written onto the card record, so a position with no
        # record has nothing to answer onto — and telling the operator "that card is not in
        # a queue" about a position that holds no card at all sends him to read the wrong
        # file. This is reachable rather than theoretical: `cli/resolve.py` queues a card
        # from a run's identifications, and a run recovered without its captures has entries
        # whose positions the store never recorded.
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. This route answers a card that "
                f"exists; it never creates one.",
            )

        holders: List[Tuple[queues.Queue, queues.QueueEntry]] = []
        already: List[str] = []
        for queue in (snapshot.review, snapshot.parked):
            entry = queue.entries.get(key)
            if entry is None:
                continue
            if entry.cleared_by_human:
                already.append(queue.name)
            else:
                holders.append((queue, entry))

        if not holders:
            # TWO CODES, NOT ONE, because the remedies are opposite. An already-answered card
            # is the two-device case D5 and D13 describe — the Fulfiller or the other browser
            # tab got there first — and the operator should reload, not retry. A position
            # that was never queued is a client asking about the wrong card.
            if already:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "already_answered",
                    f"Box {box}, card {index} has already been answered and is no longer "
                    f"in a queue. Reload the queue — the answer may have come from the "
                    f"other device.",
                )
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_in_queue",
                f"Box {box}, card {index} is not waiting in the review or parked queue, so "
                f"there is nothing to answer. Reload the queue.",
            )

        # ONE ENTRY GOVERNS THE OFFER, and it is the main-queue one whenever the position is
        # in both. `holders` is built review-first above, so this is `holders[0]` and not a
        # search. Every alternative was worse:
        #
        #   the union of both    what this did, and the bug. A stale parked entry launders a
        #                        SKU the review entry never offered, and the laundering is
        #                        invisible afterwards — the card carries a real SKU from a
        #                        real catalog row, just not one that was ever proposed for it.
        #   the intersection     safe and unanswerable. `cli/resolve.py:failure_entry` records
        #                        no candidates at all, so a position sitting in both files
        #                        with one of them a failure entry would refuse every answer
        #                        forever, including the correct one.
        #   naming the queue     the client would send which file its row came from. That is a
        #   in the request       field the screen has no reason to know (it taps a position),
        #                        and it puts the choice of what may be answered on the wire,
        #                        where a stale client picks it.
        #
        # Main wins because main is the queue that is worked — `store/queues.py` splits them
        # exactly so: work versus the low-value queue a card may never be worth a tap on. A
        # card in both is a card the owner answers from the review screen.
        offering, governing = holders[0]
        candidates: List[dict] = list(governing.candidates)
        if not candidates:
            # `cli/resolve.py:failure_entry` records no candidates at all — an identification
            # that failed, or a card with no position, has no rows for a human to choose
            # between. `docs/DESIGN.md` describes a screen of candidate rows and says nothing
            # about what to do when there are none, so this refuses rather than inventing a
            # free-text path into the one field the hard rule protects. What would settle it:
            # Gate B, and how often a run actually produces one of these.
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "no_candidates",
                f"Box {box}, card {index} is queued in {offering.name} as "
                f"`{governing.reason}` and records no candidate rows, so there is nothing to "
                f"choose. It needs a re-shoot or a re-identify, not an answer.",
            )

        chosen = _candidate_with_sku(candidates, sku)
        if chosen is None:
            offered = ", ".join(sorted(str(c.get("sku") or "") for c in candidates))
            # The queue is NAMED, because the case this refusal now catches is a card sitting
            # in both files whose two entries disagree — and "that is not one of the rows
            # offered" reads as a bug to anyone looking at the other row on screen.
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "sku_not_a_candidate",
                f"{sku} is not one of the rows offered for box {box}, card {index}. "
                f"Offered in {offering.name}: {offered}. Answer with one of those, or reload "
                f"the queue if it has been re-joined since this screen was drawn.",
            )

        offered_condition = str(chosen.get("condition") or "")
        if condition != offered_condition:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "condition_mismatch",
                f"{sku} is offered as {offered_condition!r}, not {condition!r}. The screen "
                f"was drawn from an older queue file — reload it and choose again.",
            )

        card.sku = sku
        card.condition = offered_condition

        cleared = {queues.MAIN: False, queues.PARKED: False}
        for queue, entry in holders:
            entry.cleared_by_human = True
            cleared[queue.name] = True

        body = {
            "answered": key,
            "box": int(box),
            "index": int(index),
            "sku": sku,
            "condition": offered_condition,
            # Reported the way undo reports what it removed, and for the same reason: a
            # write says what it touched. Both true is the entry-in-both-queues case, which
            # is worth seeing rather than smoothing over — and it is the case the client
            # needs, since a screen holding both lists must drop BOTH rows on one answer or
            # go on showing a card whose answer is already written. Both keys are always
            # present, false rather than absent, so the app reads two booleans and never has
            # to tell "not cleared" from "the server did not say".
            "review_cleared": cleared[queues.MAIN],
            "parked_cleared": cleared[queues.PARKED],
            "card": _card_row(box, index, card),
        }

    return body


# ------------------------------------------------------------------------------ mark sold


def _state_before_sale(events: Sequence[dict], key: str) -> Optional[str]:
    """The state to put back, read out of `history.jsonl`. None when it cannot be known.

    THE PRIOR STATE IS NOT STORED ON THE CARD, and it deliberately is not: `store/master.py`
    holds one `state` per card, `Inventory.parse` filters on `Card.__annotations__`, and a
    `previous_state` field would be a second piece of state to keep true through every
    transition in the pipeline for the sake of one ten-second window on one screen.

    IT DOES NOT NEED TO BE. `history.jsonl` is append-only and already records every
    transition — `set_state` and `record_capture` both log one — so the state a card was in
    before it sold is a fact the store has held all along. Reading it back needs no new event
    name either, which matters: `docs/DEBTS.md` records that adding an `undone` event to the
    store's vocabulary is a D10 question rather than a logging one, and this route asks
    nothing of it. A sale and its reversal read as `live, sold, live`, which is what
    happened.

    THE RULE IS THE LAST EVENT FOR THIS POSITION NAMING A STATE OTHER THAN `sold`. Scanning
    backwards rather than taking the second-to-last entry, so a position that somehow carries
    two adjacent `sold` events still restores to the state underneath them instead of to
    `sold`. Filtered against `master.STATES` so a future non-state event in this log cannot
    be handed to `set_state` as one.

    NONE IS A REFUSAL AND NOT A DEFAULT. Defaulting to `live` is the obvious guess and is
    exactly what would make the reversal inexact for a card sold out of `pushed` or `staged`
    — which is most of what a real order pull will touch before an Export From Staged has
    ever been run. A store whose history was truncated gets told so.
    """
    for event in reversed(list(events)):
        if event.get("position") != key:
            continue
        state = event.get("event")
        if state in master.STATES and state != master.SOLD:
            return str(state)
    return None


def _sale_origin(store: Store, key: str) -> Tuple[Optional[str], Optional[str]]:
    """The state to put back, or None and the reason it cannot be known. Never raises.

    A MALFORMED LINE IN `history.jsonl` DEGRADES TO "ORIGIN UNKNOWN" RATHER THAN TAKING THE
    ROUTE DOWN, which is the whole reason this wrapper exists. `files.read_jsonl` refuses the
    entire file over one bad line, and this read runs before either branch — so a single
    corrupt line stopped the SALE as well as the reversal and answered a Fulfiller's tap with
    `store_unavailable`. Measured: a hand-appended `{not json` left a card `captured` after a
    503. A sale is the one event in this product that has already happened in the physical
    world, and `CLAUDE.md`'s standing trade is that unlisted is fine and unrecorded is not.

    WHAT DEGRADING COSTS IS THE UNDO CONTROL AND NOTHING ELSE, which is why it is the right
    trade rather than a shrug. `restores_to` is already null-when-unknown and the app reads
    that null as "do not offer undo", so the Fulfiller sees a recorded sale with no undo
    button instead of a failed tap — and a reversal attempted anyway refuses in
    `sold_origin_unknown`, exactly as it does for a truncated history. Nothing guesses.

    THE READ STAYS INSIDE THE LOCK, which is the other repair that was considered. Moving it
    out addresses the parse cost — O(history), and history only ever grows — but addresses
    nothing about the corrupt line, and it pays for that with a value read before the lock
    was taken. `store/session.py` opens by explaining that a snapshot from before the lock is
    the lost update the lock exists to prevent: a card re-sold by the other device (D13)
    between the read and the lock would restore to the state it held two sales ago, and the
    reversal is the one thing here that must be exact. The cost is real and is recorded
    rather than hidden — one parse per sale, under a lock `Store.write()` already holds for a
    whole-store read.
    """
    try:
        events = store.history()
    except (files.StoreError, OSError, ValueError) as exc:
        # Broad on purpose: a bad line, an unreadable file and non-UTF-8 bytes are one
        # condition to this route — history cannot say — and each of them must leave the
        # sale writable. Narrowing this to StoreError alone would re-open the same hole for
        # the next way a log file goes wrong.
        return None, f"history.jsonl could not be read ({type(exc).__name__}: {exc})"
    state = _state_before_sale(events, key)
    if state is None:
        return None, "history.jsonl records no earlier state for it"
    return state, None


def do_mark_sold(box: int, index: int, payload: dict) -> dict:
    """Mark one copy sold, or put its state back. D10, and the server half of undo.

    SOLD IS A STATE, NEVER A REMOVAL (D10). The record stays, the position stays, and the
    position is never reused — `Inventory.next_index` is a high-water mark that counts every
    state, so the gap a sale leaves is permanent and a printed label is still true a year
    later. Nothing here deletes anything, and that is the difference from
    `do_delete_card`: undo of a CAPTURE removes a card that was never listed, undo of a SALE
    is a state transition backwards.

    ONE COPY, NOT ONE SKU. D7 keeps every copy as its own position with its own photo
    precisely so an order pull can mark one of them sold and leave the rest listed. The
    position in the path is the whole of the selection.

    THE UNDO WINDOW IS THE APP'S; THE REVERSIBILITY IS THIS ROUTE'S. `docs/DESIGN.md`
    requires undo on every mark-sold with at least a ten-second window, and there is
    deliberately no expiry here. A server-side deadline would fail the reversal exactly when
    the network was slow, and would turn a mistake noticed a minute later — a Fulfiller
    tapping the row above the one he meant — into something only the owner can repair by
    hand. What the ten seconds govern is how long the control is on screen.

    NO CONFIRM DIALOG IS IMPLIED BY ANY OF THIS. `docs/DESIGN.md` bans one on a reversible
    action, and this route is what makes the action reversible.

    WHICH STATES MAY BE SOLD FROM — ASSUMPTION, and it is permissive. Anything but `sold`
    itself. `docs/DESIGN.md` and D10 say what a sale IS and never say which cards may have
    one, and the narrower rule (refuse a card that was never pushed to TCGplayer) would leave
    a person holding a card he has genuinely sold with no way to record it — against
    `CLAUDE.md`'s standing trade that unlisted is fine and unrecorded is not. The cost of
    being wrong is one reversible state change. What would settle it: Gate B, and what the
    Fulfillment view actually lists.

    ONE `Store.write()` for either direction, and nothing outside the store is touched — no
    photo, no sidecar, no queue entry. A sold card keeps its capture photo, which is what the
    pull preview shows (D6) and what makes a dispute answerable afterwards.

    A SALE IS NEVER BLOCKED BY `history.jsonl`. The log is read here to say what an undo
    would put back, and `_sale_origin` degrades an unreadable one to "origin unknown" rather
    than refusing — the reversal is what loses, and only the reversal. Its own docstring has
    the argument, including why the read stays inside the lock.
    """
    _reject_unknown(payload, SOLD_FIELDS)
    undo = _optional_flag(payload, "undo", "undo_invalid")

    key = master.position_key(box, index)
    store = Store()

    with store.write() as snapshot:
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. A sale is recorded against a card "
                f"that exists; this route never creates one.",
            )

        # Read inside the lock, before either branch writes. The `sold` event of the sale
        # being reversed was committed by an earlier request, so it is on disk by now —
        # `Store.write()` appends history after the yield, which is why this cannot see an
        # event the CURRENT request has queued and does not need to. `_sale_origin` never
        # raises: an unreadable history makes the origin unknown, it does not block the sale.
        previous, origin_unknown = _sale_origin(store, key)
        was = card.state

        if undo:
            if was != master.SOLD:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "not_sold",
                    f"Box {box}, card {index} is {was}, not sold, so there is no sale to "
                    f"reverse. It may already have been reversed on the other device.",
                )
            if previous is None:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "sold_origin_unknown",
                    # The reason is carried rather than assumed: "no earlier state" and "the
                    # log will not parse" are one refusal and two repairs, and the second one
                    # is a file to go and fix.
                    f"Box {box}, card {index} is sold, but {origin_unknown}, so there is no "
                    f"state to put back. Set it by hand rather than letting this guess — a "
                    f"card restored to the wrong state is a listing that disagrees with "
                    f"TCGplayer.",
                )
            restored = previous
        else:
            if was == master.SOLD:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "already_sold",
                    f"Box {box}, card {index} is already sold. Send {{\"undo\": true}} to "
                    f"reverse that sale; marking it again would record a second sale of one "
                    f"physical card.",
                )
            restored = master.SOLD

        # `set_state` returns False only for a position with no record, and the card was
        # found above inside this same lock. Checked anyway rather than assumed: a silent
        # no-op reported as a success is v1 bug 5's exact shape, which is the reason that
        # return value exists at all.
        if not snapshot.inventory.set_state(key, restored):
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "inventory_conflict",
                f"Box {box}, card {index} vanished between being read and being written. "
                f"Retry; if it repeats, another process is writing inventory.json outside "
                f"the store lock.",
            )

        body = {
            "position": key,
            "box": int(box),
            "index": int(index),
            # True when this call reversed a sale. The app reads this rather than comparing
            # states, so one field answers "which way did that go" in both directions.
            "undone": bool(undo),
            "state": card.state,
            "previous_state": was,
            # What an undo of THIS call would put back, or null when history cannot say.
            # Null on a reversal because there is then nothing to reverse; null on a sale
            # means the undo control should not be offered, which is worth knowing at the
            # moment of the sale rather than at the tap that fails.
            "restores_to": None if undo else previous,
            "card": _card_row(box, index, card),
        }

    return body


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
            if path == "/queues":
                return self._json(HTTPStatus.OK, do_queues())
            match = _PHOTO_RE.match(path)
            if match:
                blob = do_photo(int(match.group(1)), int(match.group(2)))
                return self._send(HTTPStatus.OK, blob, "image/jpeg")
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No GET route {path}.")

        self._dispatch(run)

    def do_POST(self) -> None:  # noqa: N802
        """Capture, and 7b's two writes.

        BOTH OF 7b's READ A BODY, including mark-sold, whose sale needs nothing in it — send
        `{}`. `self._body()` refuses an empty request as `body_required`, and that uniformity
        is the reason rather than an oversight: every write in this server reads its body the
        same way, and a second reader that tolerated an absent one would be a second set of
        rules about request size and encoding. The cost is two characters on the wire.
        """

        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/capture":
                status, body = do_capture(self._body())
                return self._json(status, body)
            match = _REVIEW_ANSWER_RE.match(path)
            if match:
                body = do_review_answer(
                    int(match.group(1)), int(match.group(2)), self._body()
                )
                return self._json(HTTPStatus.OK, body)
            # Matched after the review route and before the fallthrough. `/inventory/3/17`
            # keeps its own regex, anchored to end there, so this cannot shadow the PUT and
            # DELETE paths — a sale is a different verb on a longer path, not a mode of them.
            match = _SOLD_RE.match(path)
            if match:
                body = do_mark_sold(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
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
