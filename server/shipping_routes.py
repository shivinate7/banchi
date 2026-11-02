"""The ONE module in this server that holds a buyer's name and street address.

`server/tcg_export.py` is a separate file because the TCGplayer secret never leaves it. This
file is separate for the mirror-image reason: it is the only module in this server that holds a
buyer's real name and real street address, and the only one that emits them. An operator
reading the routes wants ONE file to check when they ask "where does the PII go", and a
reviewer changing a handler wants to know they are inside that file rather than beside it.
It reads an export the operator uploaded, routes it into three lanes, hands back a Pirate Ship
import CSV for the parcel lane, and buys TCGTracking labels for the envelope lane. Its
network calls go through `server/tcgtracking.py`, which alone holds the TCGTracking key and
host. Its store writes are the label rows in `store/orders.Ledger`'s `labels`.

TWO COSTS, RECORDED RATHER THAN DISCOVERED:

  **The batch table lives in this process's memory only.** So two devices do not share a
  batch, and a server restart drops every one of them. `make up` reloads the capture server on
  any Python edit under `server/`, so an edit during a session is a restart, and the refusal
  for a batch that is gone says so in those words rather than reading as a bug. A batch holds
  the rendered parcel `blob`, the `parcels` it was rendered from and the envelope-lane
  `envelope` shipments, for at most `BATCH_TTL_SECONDS`, and a Forget drops them at once.
  The blob touches no disk on the way to the browser (`pirateship.render` returns bytes).

  **A label row is kept** (D326 lifts D61's rule that buyer PII is not stored, for what
  TCGTracking returns): the whole answer, the label PDF, the insurance switch and the last scan.
  The demo-mirror scrub drops every row (`scripts/demo-mirror.py`). The batch itself is still
  never written anywhere.

THE LABEL ROUTES (D326, T4 and T5). Every shape below is the contract the screen reads.

  POST /shipping/batches/BATCH/labels
    {"preview": true}
        -> 200 {"count": int, "envelope_size": "10", "envelope": "#10 envelope", "fee_note": str,
                "key_present": bool, "shipper_present": bool,
                "orders": [{"order", "eligible": bool, "reason": str, "insured": false}]}
        Free: no request to TCGTracking, no store write. `count` is the eligible orders.
        `envelope_size` is the API's code for the size and `envelope` is its readable label.
        `key_present` and `shipper_present` say whether the settings file holds each, never its
        value. `reason` is a fixed code. An eligible order is `envelope`. A held-back order is
        `parcel` (labeled in Pirate Ship), `needs_a_look` (unjudged), `no_full_street` (the
        export row lacks a street, city, state or postal code) or `already_labelled` (it has a
        label row; the confirm still answers it as `existing`).
    {"confirm": true, "orders": [order, ...], "insured": [order, ...]}   (`insured` optional)
        -> 200 {"made": [{"order", "tracking_number", "insured"}],
                "existing": [{"order"}], "refused": [{"order", "code"}], "partial": bool}
        Spends. One create per order, one at a time. It stops at the first 401, 400 or 429:
        that order is `refused` with its code, `partial` is true when any label was made, and
        the orders after it are untouched. A replay lands in `existing`.
        The receipt also holds `stopped`: null, or `{"made": int, "left_over": [{"order"}]}` when a
        stop ended the press (below). `made` there is the count made before the stop, and
        `partial` is true when a label was made and any order was left over.
    400 `labels_confirm_missing`: no `confirm: true`, so nothing is bought.
    400 `labels_order_ineligible`: a confirmed order is parcel, unjudged, short of a full street
        or not in this batch (`not_in_batch`). The whole press is refused before any create, and
        `error.data.ineligible` lists each order with its reason code. An already labeled order
        is not ineligible: it is answered as `existing`.
    A missing key, a missing shipper number or a refused host answers its `tracking_` code as a
        whole-request error, with no request sent and no store write.

  POST /shipping/batches/BATCH/labels/stop   body {}
    -> 200 {"batch", "stopping": int}
        Ends the confirms running on this batch after the create in flight: that create finishes and
        its label is kept (a label is never voided), and the orders after it are left over, in the
        receipt of that confirm. A confirm waiting for its turn to create sends nothing. `stopping` is how many confirms were running. A stop with none
        running changes nothing and leaves no mark, so the next confirm is not stopped.

  GET /shipping/batches/BATCH/labels/pdf
    -> 200 one application/pdf: the stored labels of this batch's labelled orders, in batch
       order, each with its own pages. No request to TCGTracking.
       404 `no_such_batch` when the batch is gone, 404 `labels_none_made` when none is labelled,
       409 `labels_merge_unavailable` when the server runs without the pypdf package, and 502
       `label_unreadable` when a stored label is not a PDF.

  GET /shipping/labels
    -> 200 {"labels": [{"order", "pdf_token", "status": "made" | "pending", "tracking_number", "insured": bool,
                        "made_at": str | null, "scanned_at": str | null, "checked_at": str | null,
                        "scan": null | {"status": str | null, "at": str}}]}
        Read from the store. It carries no PDF bytes. `pending` is a claim with no answer yet
        (a create in flight): it has no tracking number and no `made_at`. `scanned_at` is the
        time of the latest scan event in the track answer, else null. `checked_at` is when
        Banchi last asked TCGTracking for the scan.

  GET /shipping/labels/PDF_TOKEN/pdf
    -> 200 the stored label bytes as application/pdf, with no request to TCGTracking;
       404 `label_not_found` when no label row owns the token. `pdf_token` is 32 hex characters
       drawn at random for each row (128 bits) and listed above. An ORDER NUMBER there is a 404,
       for the same reason the batch file route takes a batch id: a GET is outside the origin
       gate, and the label holds a buyer's address, so its name may not be guessable.

  POST /shipping/labels/scans   body {}
    -> 200 {"checked": int, "found": int, "not_found": [order, ...]}
        One lookup per label row, stored on the row. A 404 from TCGTracking is that row's
        status (`tracking_not_found`) and never a failed press. A missing key answers its code.

THE ELIGIBLE ORDERS are the batch's envelope-lane orders. A parcel-lane order is labeled in
Pirate Ship. An unjudged order is held back with its reason and is never defaulted into a lane.
"""

from __future__ import annotations

import base64
import io
import os
import re
import secrets
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from decimal import Decimal
from fractions import Fraction
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# STDLIB-ONLY AT MODULE SCOPE, like `server/pipeline_routes.py`. `make server` runs
# `python3` and not the venv, so a module this server imports may not need `make venv`;
# both of these reach `csv`, `io`, `codecs`, `dataclasses`, `decimal`, `fractions`,
# `pathlib` and `typing` and nothing else. (`server/tcgtracking.py` and `store/` are stdlib
# only at module scope as well.)
from pipeline import pirateship, shipping  # noqa: E402
from server import tcgtracking  # noqa: E402
from store import files, orders as order_store  # noqa: E402
from store.session import Store  # noqa: E402

# NEVER `from server import capture_server`. That module imports THIS one, and the reverse
# import is the cycle `PipelineRefusal` exists to avoid — see `ShippingRefusal` below. The
# seam is one `except` clause at the dispatch site.

# ------------------------------------------------------------------------------ constants

# The batch holds exactly one file, so the name is a constant rather than a parameter, and
# membership of that one name IS the shape check `do_shipping_file` makes.
IMPORT_FILENAME = "pirateship-import.csv"

# The widest Export Shipping file this project has read is 331 orders at ~46 KB. Eight
# megabytes is a backstop against a body that never ends, not a judgement about how many
# orders an operator may have.
MAX_EXPORT_CHARS = 8 * 1024 * 1024

# FOUR BATCHES AND HALF AN HOUR, and both numbers are chosen to make the window small rather
# than to make the feature comfortable. This is the process holding buyer addresses in
# memory; the operator reads one export, downloads one file, and presses Forget.
BATCH_LIMIT = 4
BATCH_TTL_SECONDS = 1800

# What a `name` is allowed to contain once it is echoed back. `_store_upload`'s rule,
# because the failure is the same one: a name from a request is display text and never a
# path segment.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")

# Four decimal places, because `docs/specs/shipping-export.md` records the observed
# distribution to that precision (0.0700, 1.2850) and the cut sits between them.
_RATIO_PLACES = Decimal("0.0001")


class ShippingRefusal(Exception):
    """A refusal with its own code, converted by the caller.

    A private exception rather than `capture_server.BadRequest`, for the reason
    `pipeline_routes.PipelineRefusal` gives: importing that would make this module depend on
    the file that dispatches to it, and this module is imported BY that file.
    """

    def __init__(self, status: HTTPStatus, code: str, message: str, data: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.data = data


# -------------------------------------------------------------------------- the holder


@dataclass
class _Batch:
    """One read export, held for as long as the operator is working through it.

    THE SOURCE CSV IS NOT IN HERE, and its absence is the point: it is dropped the moment
    `shipping.parse` has read it, so the only buyer PII this process retains is the rendered
    `blob` and the `parcels` it was rendered from. `rows` — what the screen draws — carries
    an order number, a lane, a reason and two numbers, and no name, street, city or postcode
    at all.

    `parcels` IS KEPT RATHER THAN RE-DERIVED because the stamps route named in the module
    docstring re-renders this same set with three columns filled. Re-parsing would mean
    holding the export text, which is the thing this record refuses to hold.

    `parcels` IS THE UNSTAMPED SET AND STAYS THAT WAY. `do_shipping_stamps` renders its own
    stamped copies with `dataclasses.replace` and hands those over without keeping them, so
    what a later press starts from is the export's own reading. That is belt to the braces
    rather than the braces: what actually makes the press idempotent is that every parcel's
    `stamps` is SET on every press — `()` where the order earned none — and never added to.

    `envelope` IS THE ENVELOPE LANE'S SHIPMENTS, kept for the label routes (D326): a label is
    made from the export row's name and address, so they are held beside the parcels for the
    same TTL and dropped by the same Forget. The export text itself is still dropped.

    `stamps` IS THE TALLY AND NOT THE STRINGS. What each parcel carries is on the parcel and
    what each row carries is in `rows`; this is the four counts the screen draws, and `None`
    until the stamps route has run against this batch.
    """

    name: str
    created: float
    rows: Tuple[Dict[str, Any], ...]
    lane_counts: Dict[str, int]
    reason_counts: Dict[str, int]
    parcel_count: int
    shipments: int
    blob: bytes
    parcels: Tuple[pirateship.Parcel, ...] = field(default=())
    stamps: Optional[Dict[str, int]] = None
    envelope: Tuple[shipping.Shipment, ...] = field(default=())


# A `ThreadingHTTPServer` serves each request on its own thread, so every read and write of
# this table is under the lock. Ordered so eviction is oldest-first without a sort.
_BATCHES: "OrderedDict[str, _Batch]" = OrderedDict()
_LOCK = threading.Lock()


def _new_batch_id() -> str:
    """128 unguessable bits, and the id IS the access control.

    `GET` is in `capture_server.SAFE_METHODS`, so the download is NOT behind the origin
    gate, and `HOST` binds every interface, IPv4 and IPv6 both. Anything on the network that can reach this port can ask
    for a batch's file; what it cannot do is name one. A counter or a timestamp here would
    make a buyer's address enumerable from the LAN.
    """
    return secrets.token_hex(16)


_GONE = (
    "That export is no longer being held. The server restarts on every Python edit and "
    "only keeps four at a time — read the file again on the Shipping screen."
)


def _expire_locked(now: float) -> None:
    """Drop everything older than the TTL. Called under `_LOCK` on every access.

    LAZY RATHER THAN A TIMER, because a timer is a thread this server does not otherwise
    run and because there is nothing to do between accesses: an unread batch that outlives
    its window is dropped by the next request that looks, and the next request is the one
    that would have been able to read it.
    """
    dead = [key for key, batch in _BATCHES.items() if now - batch.created > BATCH_TTL_SECONDS]
    for key in dead:
        del _BATCHES[key]


def _remember(batch: _Batch) -> str:
    key = _new_batch_id()
    with _LOCK:
        _expire_locked(time.monotonic())
        _BATCHES[key] = batch
        while len(_BATCHES) > BATCH_LIMIT:
            _BATCHES.popitem(last=False)
    return key


def _recall(batch: str) -> _Batch:
    with _LOCK:
        _expire_locked(time.monotonic())
        held = _BATCHES.get(str(batch or ""))
    if held is None:
        raise ShippingRefusal(HTTPStatus.NOT_FOUND, "no_such_batch", _GONE)
    return held


def _restore(key: str, batch: _Batch) -> None:
    """Put an updated batch back under the id it already has.

    NEVER RE-INSERTS ONE THAT IS GONE. Between the `_recall` that read it and this call the
    operator may have pressed Forget, or the TTL may have passed; writing it back then would
    re-hold buyer addresses the operator had already dropped, which is the one thing
    `do_shipping_forget` exists to prevent. A vanished batch simply keeps the answer it was
    already about to give.
    """
    with _LOCK:
        _expire_locked(time.monotonic())
        if key in _BATCHES:
            _BATCHES[key] = batch


def _forget(batch: str) -> None:
    with _LOCK:
        _expire_locked(time.monotonic())
        if _BATCHES.pop(str(batch or ""), None) is None:
            raise ShippingRefusal(HTTPStatus.NOT_FOUND, "no_such_batch", _GONE)



# ------------------------------------------------------------------------------ guards


def _only(payload: dict, allowed: Tuple[str, ...]) -> None:
    """"You named a field this route does not set", in `_reject_unknown`'s sentence shape.

    Written out here rather than imported: `capture_server` imports this module, so
    reaching back for its helper is the cycle. Four lines is the cost of the seam.
    """
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "field_not_settable",
            # `or "nothing"` for the route that takes a body and sets none of it —
            # "Settable: ." is a sentence with a hole in it where the answer should be.
            "Cannot set {} here. Settable: {}.".format(
                ", ".join(unknown), ", ".join(allowed) or "nothing"
            ),
        )


def _safe_name(raw: Any) -> str:
    """The uploaded file's name, echoed back for the receipt line and nothing else."""
    text = str(raw or "export.csv")
    return _SAFE_NAME.sub("-", Path(text).name) or "export.csv"


# ---------------------------------------------------------------------------- rendering


def _value(value: Optional[Decimal]) -> Optional[str]:
    """A published price as a string. NEVER a float — `Value Of Products` is money."""
    return None if value is None else str(value)


def _ratio(ratio: Optional[Fraction]) -> Optional[str]:
    """`Product Weight / Item Count`, DISPLAY ONLY, with no float anywhere in the path.

    The `_oz` suffix on the wire key is what makes it obviously a rendering. Every real
    comparison stays inside `pipeline/shipping.py:route` against exact `Fraction`s — that
    module records that a float pass over this very column MOVED the lane counts by
    manufacturing a row below a minimum that is exactly 0.07.
    """
    if ratio is None:
        return None
    return str((Decimal(ratio.numerator) / Decimal(ratio.denominator)).quantize(_RATIO_PLACES))


def _stamp_text(stamps: Sequence[str]) -> Optional[str]:
    """The row's ONE `stamp` string, out of the up-to-three the label's corners hold.

    THE WIRE FIELD IS SINGULAR AND THE FORMAT IS NOT, so this is the join and it lives on
    this side of it. `app/src/types.ts` has declared `stamp: string | null` since the seam
    was cut and `OrdersShipStage.tsx` already draws it as one pinned line; a screen taking
    an array instead would be the type change this route was shaped not to need.

    THE SEPARATOR IS ` / ` AND MAY NOT BE ` · `. The label's own parts are joined by ` · `
    (`Box 3 · Section 1 · Card 31`), so joining labels with it would produce a string in
    which the boundary between two different cards is spelled exactly like the boundary
    between a section and a card number — one address to a reader, and the wrong shelf to
    a hand. Nothing parses this back; the CSV takes the strings one per column.
    """
    kept = [str(stamp) for stamp in stamps if str(stamp).strip()]
    return " / ".join(kept) or None


def _row(
    shipment: shipping.Shipment,
    routing: shipping.Routing,
    stamps: Sequence[str] = (),
) -> Dict[str, Any]:
    """One order as the screen draws it: which lane, on what grounds, and how sure.

    `certain` is carried rather than inferred from `reason` at the far end, because
    `Routing.certain` is the module that owns the distinction and a second copy of the rule
    in TypeScript is the second-renderer failure this repo has already recorded.

    `stamp` IS `None` UNTIL THE STAMPS ROUTE HAS RUN, and null rather than absent: the key
    is on the wire from the first read so that filling it changes no type and no component.
    """
    return {
        "order": routing.order,
        "lane": routing.lane,
        "reason": routing.reason,
        "certain": routing.certain,
        "value": _value(routing.value),
        "weight_per_item_oz": _ratio(routing.weight_per_item),
        # `None`, NEVER 0, when the cell is unparseable — absent has to stay
        # distinguishable from small all the way to the screen, which is the whole of
        # `pipeline/shipping.py`'s abstention.
        "item_count": shipment.item_count,
        "stamp": _stamp_text(stamps),
    }


def _payload(key: str, batch: _Batch) -> Dict[str, Any]:
    """One held batch as the wire's `ShippingBatch`. ONE RENDERER FOR BOTH HANDLERS.

    `do_shipping_batches` and `do_shipping_stamps` answer the same object and the second one
    exists to change two of its fields, so a second literal here is a payload that drifts by
    a key the first press has and the second does not — the shape of bug a screen shows as a
    field that empties itself when you press a button.

    `file.bytes` IS READ OFF THE BLOB rather than remembered, because stamping re-renders it
    and a stale length is a download size that disagrees with the download.
    """
    return {
        "batch": key,
        "name": batch.name,
        "expires_in": BATCH_TTL_SECONDS,
        "shipments": batch.shipments,
        "rows": list(batch.rows),
        # STRAIGHT FROM `shipping.lane_counts` / `shipping.reason_counts`, WHICH SEED EVERY
        # KEY INCLUDING THE ZEROS — do not filter them. "Nothing was unjudged" and "nothing
        # was checked" must not be the same payload.
        "lane_counts": batch.lane_counts,
        "reason_counts": batch.reason_counts,
        "parcel_count": batch.parcel_count,
        "file": {"name": IMPORT_FILENAME, "bytes": len(batch.blob)},
        # `None` UNTIL THE STAMPS ROUTE HAS RUN AGAINST THIS BATCH, and that is not the same
        # fact as every count being zero: the first says nobody has asked the ledger, the
        # second says it was asked and had nothing to say. The screen draws two different
        # sentences off exactly this distinction.
        "stamps": dict(batch.stamps) if batch.stamps is not None else None,
    }


# ----------------------------------------------------------------------------- handlers

_BATCH_FIELDS: Tuple[str, ...] = ("name", "content")

# The stamps route takes a body and sets nothing out of it. `_body()` refuses an empty
# request by this server's own uniform rule, so the client sends `{}` — and an empty
# allowlist means any key at all refuses by name rather than being ignored.
_STAMPS_FIELDS: Tuple[str, ...] = ()

# `store.orders` order number -> the position labels of the copies that fill it, plus how
# many orders the ledger holds at all. The caller supplies it; see `do_shipping_stamps`.
StampSource = Callable[[Sequence[str]], Tuple[int, Dict[str, Tuple[str, ...]]]]


def do_shipping_batches(payload: dict) -> dict:
    """`POST /shipping/batches` — read one Export Shipping file and hold the answer.

    Free, re-runnable, and it spends nothing: no key is read, no socket is opened and no
    child is started. What it costs is memory holding buyer addresses, which is what
    `do_shipping_forget` is the way back from.
    """
    _only(payload, _BATCH_FIELDS)

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST, "export_empty", "Nothing to read — that file is empty."
        )
    if len(content) > MAX_EXPORT_CHARS:
        # NAMES THE FILE, unlike `_body()`'s `body_too_large` which names the request. An
        # operator who just picked a 40 MB file needs to be told it was the file.
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_too_large",
            "That file is {} characters, and this screen reads at most {}.".format(
                len(content), MAX_EXPORT_CHARS
            ),
        )
    if "," not in content.splitlines()[0]:
        # The cheap check `_store_upload` already makes, pointed at the right export. The
        # failure it prevents is a parse refusal several lines later about a missing column,
        # for a file that was never a spreadsheet.
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_not_csv",
            "That file's first line has no comma in it, so it is not a CSV. This screen "
            "wants TCGplayer's Orders -> Export Shipping file, not the Pricing tab's "
            "Filtered Export.",
        )

    try:
        export = shipping.parse(content.encode("utf-8"))
    except shipping.MalformedShipping as exc:
        # ONE CODE FOR ALL OF `MalformedShipping`'S CAUSES, ON PURPOSE. A BOM, an empty
        # file, a changed header and a short row have the identical remedy — export the file
        # again from Orders -> Export Shipping — and splitting them into four codes would
        # mean re-parsing the engine's message string to tell them apart, which is a second
        # reader of a format that already has one.
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "export_not_shipping",
            "That file is not the Export Shipping file this screen reads: {}".format(exc),
        ) from None

    # EXPORT ORDER, NEVER SORTED. The operator works down the list beside the file they
    # exported, and a re-ordering here would mean the screen and the spreadsheet disagree
    # about which order is which.
    routings = shipping.route_all(export.shipments)
    rows = tuple(
        _row(shipment, routing) for shipment, routing in zip(export.shipments, routings)
    )

    # `stamps` LEFT AT ITS DEFAULT `()` and `weight` LEFT AT `None`. NEVER pass a weight:
    # `to_parcel` does not read `Product Weight` at all and must not start — it is a summed
    # catalog constant and therefore a LOWER BOUND on what the parcel weighs, so writing it
    # into `Package Weight` buys postage for less than the package weighs, and the bill
    # arrives at the far end weeks later.
    parcels = tuple(shipping.to_parcel(shipment) for shipment, _ in shipping.parcel_lane(export))
    blob = pirateship.render(parcels)

    lane_tally = shipping.lane_counts(routings)
    reason_tally = shipping.reason_counts(routings)

    batch = _Batch(
        name=_safe_name(payload.get("name")),
        created=time.monotonic(),
        rows=rows,
        lane_counts=lane_tally,
        reason_counts=reason_tally,
        parcel_count=len(parcels),
        shipments=len(export.shipments),
        blob=blob,
        parcels=parcels,
        envelope=tuple(
            shipment
            for shipment, routing in zip(export.shipments, routings)
            if routing.lane == shipping.LANE_ENVELOPE
        ),
    )
    key = _remember(batch)

    return _payload(key, batch)


def do_shipping_stamps(batch: str, payload: dict, locate: StampSource) -> dict:
    """`POST /shipping/batches/<batch>/stamps` — fill the three Rubber Stamp corners (T2b).

    Free, re-runnable and idempotent: it spends nothing, opens no socket, writes no file, and
    re-asks the store every time rather than adding to what the last press wrote. What it
    changes is the held batch — the same id, a re-rendered blob, `stamp` on the rows and the
    four counts on `stamps`.

    `locate` IS THE WHOLE SEAM, AND WHAT CROSSES IT IS ORDER NUMBERS AND STRINGS. This module
    may not import `server/capture_server.py` (that file imports THIS one — the cycle
    `ShippingRefusal` exists for), and it must not learn to open the store in any case: it is
    the one file that holds a buyer's name and street, and the answer to "where does the PII
    go" gets harder to give with every second subject in it. So the caller passes a function,
    it is handed the batch's own order numbers, and it hands back labels. An order number is
    the marketplace's identifier for a sale and is not a buyer's anything.

    ALL THREE CORNERS OR NONE, AND THAT IS THE ONE RULE WORTH ARGUING. `pirateship.Parcel`
    enforces no length on a stamp because nobody has measured what Pirate Ship prints, and
    its header says why: truncating at an invented number turns `Box 3 · Card 31` into a
    wrong shelf rather than an obviously broken one. Dropping the fourth position of a
    four-position order is the same failure one register up — the label is the thing in the
    operator's hand, there is no fourth corner to say "and two more", and a short pick list
    that looks complete is worse than an empty one. So an order needing more positions than
    the label has corners gets NONE and is counted as unstamped, which the screen can say and
    a label cannot. **Measured on the owner's own ledger, 2026-09-05: 12 of 20 orders hold
    three copies or fewer and 8 hold between five and thirteen.** If that ratio holds as the
    store deepens, the register is what changes — a stop per BOX, in the vocabulary the order
    screen's own walk plan already speaks, rather than a card per corner — and never this
    rule. `docs/specs/order-pipeline.md`'s T2b carries the argument and cites the entry.

    AN ORDER THE LEDGER DOES NOT HOLD LEAVES ITS CORNERS EMPTY. It is not looked up by name,
    by buyer or by value, and nothing is inferred from the row: the export and the ledger
    agree about an order number or they do not.
    """
    _only(payload, _STAMPS_FIELDS)
    held = _recall(batch)

    # DEDUPED, AND IN THE EXPORT'S OWN ORDER. `dict.fromkeys` rather than a set, because the
    # numbers are handed to somebody else's function and a set would make what it is asked
    # depend on a hash seed.
    numbers = tuple(dict.fromkeys(str(row["order"]) for row in held.rows if row["order"]))
    ledger_orders, found = locate(numbers)

    stamps_for: Dict[str, Tuple[str, ...]] = {}
    for number, labels in found.items():
        kept = tuple(str(label).strip() for label in labels if str(label).strip())
        # OVER THE LIMIT IS EMPTY AND IS NEVER A SLICE — see the docstring. Under it, a
        # `Parcel` built with these cannot raise `MalformedParcel`, which is the format's
        # own guard and stays where it is.
        stamps_for[str(number)] = () if len(kept) > pirateship.STAMP_LIMIT else kept

    parcels = tuple(
        replace(parcel, stamps=stamps_for.get(str(parcel.order_id), ()))
        for parcel in held.parcels
    )
    rows = tuple(
        dict(row, stamp=_stamp_text(stamps_for.get(str(row["order"]), ())))
        for row in held.rows
    )
    # RENDERED BEFORE ANYTHING IS STORED, so a parcel the format refuses takes the press down
    # with the old batch still intact rather than leaving a half-stamped one behind.
    blob = pirateship.render(parcels)

    tally = {
        # How many orders the ledger holds AT ALL. The screen's honest sentence for an empty
        # ledger is "no order has been read in yet", and it cannot be told apart from "none
        # of these twenty is in it" without this number.
        "ledger_orders": int(ledger_orders),
        # Shipments, not parcels: an order in the ledger is matched whichever lane it landed
        # in, and the envelope lane is most of a real export.
        "matched": sum(1 for row in held.rows if str(row["order"]) in found),
        # PARCELS, because these two are the FILE's figures and the file is the parcel lane
        # and nothing else — `stamped of parcel_count` is the sentence the screen draws.
        "stamped": sum(1 for parcel in parcels if parcel.stamps),
        "unstamped": sum(1 for parcel in parcels if not parcel.stamps),
    }

    updated = replace(held, rows=rows, parcels=held.parcels, blob=blob, stamps=tally)
    # IDEMPOTENT BECAUSE EVERY PARCEL'S `stamps` IS SET AND NEVER ADDED TO — `()` above where
    # the order earned none, so a second press re-asks the ledger rather than compounding
    # what the first wrote. The held set is left unstamped besides, so what a later press
    # starts from is the export's own reading; that is the belt, and the line above is the
    # braces.
    _restore(str(batch), updated)
    return _payload(str(batch), updated)


def do_shipping_file(batch: str, filename: str) -> Tuple[bytes, str]:
    """`GET /shipping/batches/<batch>/file?name=<f>` — the import CSV's bytes.

    `do_pipeline_file`'s signature exactly, so the dispatch site is two lines.

    THE NAME IS CHECKED BY MEMBERSHIP AND NOT BY PATTERN, because this batch has exactly one
    file: membership IS the shape check, and `""`, `pricing.json` and `../../inventory.json`
    all land in the same refusal without a traversal rule having to be written or maintained.
    """
    if filename != IMPORT_FILENAME:
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "file_name_invalid",
            "That file is not part of this batch. The batch has one file, {}.".format(IMPORT_FILENAME),
        )
    held = _recall(batch)
    return held.blob, "text/csv"


def do_shipping_forget(batch: str) -> dict:
    """`DELETE /shipping/batches/<batch>` — drop it now rather than in half an hour.

    THIS IS THE WAY BACK that CLAUDE.md's hard rule asks of anything that causes the process
    to hold a buyer's address, and it is the reason the TTL is a backstop rather than the
    only release.

    A BODY RATHER THAN A 204, matching `do_DELETE`'s existing rule that the app names what it
    just removed: the response is where that name comes from.
    """
    _forget(batch)
    return {"batch": str(batch), "forgotten": True}


# ------------------------------------------------------------------------ the labels (D326)

# One marker per server process, written on every claim. A claim whose marker is not this
# process's belongs to a press that died, and `Ledger.claim_label` retries it.
PROCESS_MARK = "{}:{}".format(os.getpid(), secrets.token_hex(4))

# Orders a create of THIS process is making now. `Ledger.claim_label` reads it, so a claim of this
# process whose release write failed is retried and does not block until a restart.
_IN_FLIGHT: set = set()
# Batch id -> the stop flags of the confirms running on it. A stop sets them and creates none.
_PRESS_LOCK = threading.Lock()
# One create at a time across every press of this process: paid calls go one by one. Held around the
# create call alone, NEVER around a `Store.write` (the store lock has four request slots to share).
# So no thread waits on the store lock while it holds `_CREATE_LOCK`, and the two never form a cycle.
_CREATE_LOCK = threading.Lock()
_PRESSES: Dict[str, List[threading.Event]] = {}
# Order -> `(answer, pdf base64 or None, insured)`: a paid create's answer whose store write failed.
# `_write_held` writes it at the next confirm, listing or PDF read. `_HELD_LOCK` guards the dict
# alone and is never held across a `Store.write`.
_HELD: Dict[str, Tuple[Dict[str, Any], Optional[str], bool]] = {}
_HELD_LOCK = threading.Lock()

_TOKEN = re.compile(r"[0-9a-f]{32}")

_LABEL_FIELDS: Tuple[str, ...] = ("preview", "confirm", "orders", "insured")

FEE_NOTE = (
    "Each label is billed at the fee per your TCGTracking account. TCGTracking does not tell this "
    "screen the fee or how many free labels are left."
)

# The reason codes of the preview. The screen words them; the server never does.
REASON_ENVELOPE = "envelope"
REASON_PARCEL = "parcel"
REASON_NEEDS_A_LOOK = "needs_a_look"
REASON_NO_FULL_STREET = "no_full_street"
REASON_ALREADY_LABELED = "already_labelled"
# A press of this process is making the label now. Not eligible in a preview; a confirm answers it `existing`.
REASON_PENDING = "label_pending"
REASON_NOT_IN_BATCH = "not_in_batch"
# What a confirm may name: an already labeled order is answered `existing`, not refused.
_CONFIRMABLE = (REASON_ENVELOPE, REASON_ALREADY_LABELED, REASON_PENDING)

# A label needs all of these on the export row.
_STREET_CELLS = ("Address1", "City", "State", "PostalCode")

# What a TrackingRefused answers when it ends a whole request. Inside a confirm the code goes into
# the receipt instead.
_REFUSAL_STATUS: Dict[str, HTTPStatus] = {
    "tracking_key_missing": HTTPStatus.CONFLICT,
    "tracking_shipper_missing": HTTPStatus.CONFLICT,
    "tracking_host_refused": HTTPStatus.CONFLICT,
    "tracking_rate_limited": HTTPStatus.TOO_MANY_REQUESTS,
    "tracking_not_found": HTTPStatus.NOT_FOUND,
}

# Field names a track answer's events may carry their time under. The live shape is unread, so every
# plausible name is tried and the latest ISO string wins.
_EVENT_TIME_KEYS = ("timestamp", "time", "datetime", "date", "scanned_at", "occurred_at", "event_time")


def _refusal(exc: tcgtracking.TrackingRefused) -> ShippingRefusal:
    return ShippingRefusal(_REFUSAL_STATUS.get(exc.code, HTTPStatus.BAD_GATEWAY), exc.code, tcgtracking.MESSAGES[exc.code])


def _ready() -> None:
    """Check the key, the shipper number and the host before anything is written or sent."""
    try:
        tcgtracking.ready()
    except tcgtracking.TrackingRefused as exc:
        raise _refusal(exc) from None


def _orders_named(raw: Any, field_name: str) -> List[str]:
    """`raw` as a de-duplicated list of order numbers in the order given."""
    if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "labels_orders_invalid",
            "{} must be a list of order numbers.".format(field_name),
        )
    return list(dict.fromkeys(item.strip() for item in raw))


class _Stopped(Exception):
    """A stop arrived while a press waited for `_CREATE_LOCK`: nothing was sent for its order."""


def _ours() -> set:
    """The orders this process must not create again: a create in flight, or one whose answer is held."""
    with _HELD_LOCK:
        return _IN_FLIGHT | set(_HELD)


def _write_held() -> bool:
    """Write each held create answer to the store, in one write; True when none is left held. On a
    store error the answers stay held, and their orders stay ours, so this process never creates
    them again. With none held it writes nothing."""
    with _HELD_LOCK:
        held = dict(_HELD)
    if not held:
        return True
    try:
        with Store().write() as snap:
            for order, (answer, pdf, insured) in held.items():
                row = snap.ledger.labels.get(order)
                if row is None or not row.made:
                    snap.ledger.record_label(order, answer, pdf, insured)
    except files.StoreError:
        return False
    with _HELD_LOCK:
        for order in held:
            _HELD.pop(order, None)
    return True


def _label_state() -> Tuple[set, set]:
    """`(made, pending)`: the orders with a made label, and the orders a press of THIS process is making
    now or holds an unwritten answer for. A claim left by a dead press, or by this process after a failed release, is neither: it is
    eligible, and the confirm retries it (TCGTracking dedups on `source_order_id`)."""
    rows = list(Store().read().ledger.labels.values())
    ours = _ours()
    made = {row.order for row in rows if row.made}
    pending = {row.order for row in rows if not row.made and row.claim == PROCESS_MARK and row.order in ours}
    return made, pending


def _verdict(held: _Batch, order: str, state: Tuple[set, set]) -> str:
    """The reason code for one order: `envelope` when it can be labeled now, else why not."""
    labeled, pending = state
    row = next((row for row in held.rows if row["order"] == order), None)
    if row is None:
        return REASON_NOT_IN_BATCH
    if row["lane"] == shipping.LANE_PARCEL:
        return REASON_PARCEL
    if row["lane"] != shipping.LANE_ENVELOPE:
        return REASON_NEEDS_A_LOOK
    shipment = next((s for s in held.envelope if s.order == order), None)
    if shipment is None or not all(shipment.cells.get(cell, "").strip() for cell in _STREET_CELLS):
        return REASON_NO_FULL_STREET
    if order in labeled:
        return REASON_ALREADY_LABELED
    return REASON_PENDING if order in pending else REASON_ENVELOPE


def _label_body(shipment: shipping.Shipment, insured: bool) -> Dict[str, Any]:
    """The create body for one envelope-lane order, from its export row."""
    cells = shipment.cells
    body: Dict[str, Any] = {
        "customer_name": " ".join(
            part.strip() for part in (cells.get("FirstName", ""), cells.get("LastName", "")) if part.strip()
        ),
        "address_line1": cells.get("Address1", "").strip(),
        "customer_city": cells.get("City", "").strip(),
        "customer_state": cells.get("State", "").strip(),
        "zipcode": cells.get("PostalCode", "").strip(),
        "source_order_id": shipment.order,
        "envelope_size": tcgtracking.ENVELOPE_SIZE,
    }
    if cells.get("Address2", "").strip():
        body["address_line2"] = cells["Address2"].strip()
    if shipment.value is not None:
        # A JSON number, because the API reads one; the value is the export's cell, not a price this app set.
        body["total_amount"] = float(shipment.value)
    if insured:
        body["is_insured"] = True
    return body


def _preview(held: _Batch) -> Dict[str, Any]:
    state = _label_state()
    orders = []
    for row in held.rows:
        reason = _verdict(held, str(row["order"]), state)
        orders.append({"order": row["order"], "eligible": reason == REASON_ENVELOPE, "reason": reason, "insured": False})
    key_present, shipper_present = tcgtracking.presence()
    return {
        "count": sum(1 for order in orders if order["eligible"]),
        "envelope_size": tcgtracking.ENVELOPE_SIZE,
        "envelope": "#{} envelope".format(tcgtracking.ENVELOPE_SIZE),
        "fee_note": FEE_NOTE,
        "key_present": key_present,
        "shipper_present": shipper_present,
        "orders": orders,
    }


def _label_pdf(answer: Dict[str, Any]) -> bytes:
    """The label bytes: in the create answer, or fetched by its order id when the answer has none
    (a duplicate, or a bought 500)."""
    if answer.get("pdf_base64"):
        return tcgtracking.decode_pdf(answer)
    if not answer.get("order_id"):
        raise tcgtracking.TrackingRefused("tracking_unreachable")
    return tcgtracking.pdf(str(answer["order_id"]))


def _fill_pdfs(rows: Sequence[Any]) -> Optional[tcgtracking.TrackingRefused]:
    """Fetch the PDF of each made label row that has none, by the answer's `order_id`, and store what was
    fetched in one write. Stops at the first refusal and returns it (after storing the earlier ones)."""
    fetched: Dict[str, str] = {}
    refused = None
    for row in rows:
        if not row.made or row.pdf:
            continue
        try:
            fetched[row.order] = base64.b64encode(_label_pdf(row.answer or {})).decode("ascii")
        except tcgtracking.TrackingRefused as exc:
            refused = exc
            break
    if fetched:
        with Store().write() as snap:
            for order, pdf in fetched.items():
                snap.ledger.record_label_pdf(order, pdf)
    return refused


def _make_one(order: str, shipment: shipping.Shipment, insured: bool, stop: threading.Event) -> Optional[dict]:
    """Make one order's label. Returns the receipt entry for `made`, or None when the order is
    already labeled, in flight or held. Raises TrackingRefused, or `_Stopped` when `stop` is set once
    `_CREATE_LOCK` is taken, with nothing sent and no claim left behind. Once a create has answered,
    the label is bought, and its answer is stored BEFORE the PDF is fetched.

    THE STORE LOCK IS NEVER HELD ACROSS A CALL: the claim is one `Store.write`, the create runs
    outside it, and the answer is a second `Store.write`. `REQUEST_SLOTS` is four.

    ONCE A CREATE HAS ANSWERED, THE CLAIM IS NEVER RELEASED. The label is paid for. The answer goes
    into `_HELD` as soon as it is in hand, and its write is tried twice. If both fail, it stays held,
    the order is reported made, and the next confirm, listing or PDF read writes it. A held order is ours to `claim_label`, so this process
    never creates it again. A PDF fetch that fails leaves a made row, and a later `_fill_pdfs` gets the
    PDF by the answer's `order_id`. Only a restart loses a held answer: its claim is then a dead
    press's, and the retried create is answered by TCGTracking's dedup on `source_order_id`.
    """
    with Store().write() as snap:
        took = snap.ledger.claim_label(order, PROCESS_MARK, _ours())
        if took:
            _IN_FLIGHT.add(order)
    if not took:
        # A made label with no PDF gets it now.
        held_row = Store().read().ledger.labels.get(order)
        refused = _fill_pdfs([held_row] if held_row is not None else [])
        if refused is not None:
            raise refused
        return None
    answered = False
    try:
        with _CREATE_LOCK:
            # A stop that arrived while this press waited for the lock: nothing is sent.
            if stop.is_set():
                raise _Stopped()
            answer = tcgtracking.create(_label_body(shipment, insured))
        answered = True
        kept = {key: value for key, value in answer.items() if key != "pdf_base64"}
        try:
            blob = tcgtracking.decode_pdf(answer) if answer.get("pdf_base64") else None
        except tcgtracking.TrackingRefused:
            blob = None
        pdf = base64.b64encode(blob).decode("ascii") if blob else None
        entry = {"order": order, "tracking_number": answer.get("tracking_number"), "insured": insured}
        # Held first, so the answer is in hand before any write can fail, then written; tried twice.
        with _HELD_LOCK:
            _HELD[order] = (kept, pdf, insured)
        if not _write_held() and not _write_held():
            return entry
        if blob is None:
            stored = Store().read().ledger.labels.get(order)
            refused = _fill_pdfs([stored] if stored is not None else [])
            if refused is not None:
                entry["pdf_code"] = refused.code
        return entry
    finally:
        try:
            if not answered:
                with Store().write() as snap:
                    snap.ledger.release_label(order, PROCESS_MARK)
        finally:
            _IN_FLIGHT.discard(order)


def _confirm(batch: str, held: _Batch, payload: dict) -> Dict[str, Any]:
    orders = _orders_named(payload.get("orders"), "orders")
    insured = set(_orders_named(payload.get("insured") or [], "insured"))
    if not orders:
        raise ShippingRefusal(HTTPStatus.BAD_REQUEST, "labels_orders_invalid", "Orders names no order.")
    if insured - set(orders):
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "labels_insured_unlisted",
            "Insured names an order that is not in orders: {}.".format(", ".join(sorted(insured - set(orders)))),
        )
    state = _label_state()
    verdicts = {order: _verdict(held, order, state) for order in orders}
    ineligible = [{"order": o, "reason": v} for o, v in verdicts.items() if v not in _CONFIRMABLE]
    if ineligible:
        # THE WHOLE PRESS, before any create: a confirm that lists an order the preview held back is a
        # screen out of step with the server, and half a press is the worse answer.
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "labels_order_ineligible",
            "{} order(s) in this press cannot get an envelope label here. Nothing was bought.".format(len(ineligible)),
            {"ineligible": ineligible},
        )
    _ready()

    envelope = {shipment.order: shipment for shipment in held.envelope}
    made: List[dict] = []
    existing: List[dict] = []
    refused: List[dict] = []
    left_over: List[dict] = []
    _write_held()
    stop = threading.Event()
    with _PRESS_LOCK:
        _PRESSES.setdefault(batch, []).append(stop)
    try:
        for at, order in enumerate(orders):
            if stop.is_set():
                # Checked between orders only, so the create in flight finishes and is kept.
                left_over = [{"order": rest} for rest in orders[at:]]
                break
            try:
                entry = _make_one(order, envelope[order], order in insured, stop)
            except _Stopped:
                left_over = [{"order": rest} for rest in orders[at:]]
                break
            except tcgtracking.TrackingRefused as exc:
                # STOP AT THE FIRST ERROR. A 401 or a 429 on the third order will be the same on the
                # fourth, and creates are paid. The orders after it are untouched.
                refused.append({"order": order, "code": exc.code})
                break
            except files.LockTimeout:
                # The receipt still answers: labels made so far are stored, and this order is retried.
                refused.append({"order": order, "code": "store_busy"})
                break
            if entry is None:
                existing.append({"order": order})
            else:
                made.append(entry)
                if "pdf_code" in entry:
                    break  # the label is bought and kept; the next fetch would fail the same way
    finally:
        with _PRESS_LOCK:
            _PRESSES[batch].remove(stop)
            if not _PRESSES[batch]:
                del _PRESSES[batch]
    return {
        "made": made,
        "existing": existing,
        "refused": refused,
        "partial": bool(made and (refused or left_over or any("pdf_code" in entry for entry in made))),
        "stopped": {"made": len(made), "left_over": left_over} if left_over else None,
    }


def do_shipping_labels(batch: str, payload: dict) -> dict:
    """`POST /shipping/batches/<batch>/labels` — the free preview, or the confirm that buys (D326, D33)."""
    _only(payload, _LABEL_FIELDS)
    held = _recall(batch)
    if payload.get("preview") is True:
        return _preview(held)
    if payload.get("confirm") is not True:
        raise ShippingRefusal(
            HTTPStatus.BAD_REQUEST,
            "labels_confirm_missing",
            "Nothing was bought: a label press needs a confirm after the preview.",
        )
    return _confirm(str(batch), held, payload)


def do_shipping_labels_stop(batch: str, payload: dict) -> dict:
    """The stop route for a batch: end the confirms running on it after the create in flight.
    With none running it sets nothing, so it leaves no mark."""
    _only(payload, ())
    with _PRESS_LOCK:
        running = list(_PRESSES.get(str(batch), ()))
    for flag in running:
        flag.set()
    return {"batch": str(batch), "stopping": len(running)}


def do_shipping_labels_pdf(batch: str) -> Tuple[bytes, str, str]:
    """The combined file route for a batch: its stored labels as one PDF. Calls TCGTracking only for a
    made label that has no PDF yet. A batch that is gone refuses before the store is read."""
    held = _recall(batch)
    _write_held()
    named = list(dict.fromkeys(str(row["order"]) for row in held.rows))
    ledger = Store().read().ledger
    mine = [ledger.labels[o] for o in named if o in ledger.labels]
    if any(row.made and not row.pdf for row in mine):
        _fill_pdfs(mine)
        ledger = Store().read().ledger
    labels = [ledger.labels.get(order) for order in named]
    blobs = [base64.b64decode(label.pdf) for label in labels if label is not None and label.made and label.pdf]
    if not blobs:
        raise ShippingRefusal(HTTPStatus.NOT_FOUND, "labels_none_made", "No label has been made for this batch.")
    try:
        import pypdf  # lazy: `make server` may run without the venv, and only this route needs it
    except ImportError:
        raise ShippingRefusal(
            HTTPStatus.CONFLICT, "labels_merge_unavailable", "This server cannot join label files. Start this server from the venv."
        ) from None
    writer = pypdf.PdfWriter()
    try:
        for blob in blobs:
            writer.append(pypdf.PdfReader(io.BytesIO(blob)))
    except pypdf.errors.PyPdfError:
        raise ShippingRefusal(HTTPStatus.BAD_GATEWAY, "label_unreadable", "A stored label could not be read as a PDF.") from None
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), "application/pdf", "labels-{}.pdf".format(_safe_name(batch))


def _scanned_at(scan: Optional[dict]) -> Optional[str]:
    """The time of the latest event in a stored track answer, or None."""
    answer = (scan or {}).get("answer")
    events = answer.get("events") if isinstance(answer, dict) else None
    stamps = [
        str(event[key])
        for event in (events if isinstance(events, list) else [])
        if isinstance(event, dict)
        for key in _EVENT_TIME_KEYS
        if isinstance(event.get(key), str) and event[key]
    ]
    return max(stamps) if stamps else None


def _scan_status(scan: Optional[dict]) -> Optional[dict]:
    if not scan:
        return None
    answer = scan.get("answer")
    status = scan.get("status") or (answer.get("status") if isinstance(answer, dict) else None)
    return {"status": status, "at": scan.get("at")}


def do_shipping_labels_list() -> dict:
    """`GET /shipping/labels` — one row per label row, read from the store. No PDF bytes. A claim
    with no answer yet is listed `pending`."""
    _write_held()
    rows = list(Store().read().ledger.labels.values())
    if any(row.made and not row.pdf for row in rows):
        _fill_pdfs(rows)  # best effort: a refusal leaves the row listed, and the next read tries again
        rows = list(Store().read().ledger.labels.values())
    rows.sort(key=lambda row: row.order)
    return {
        "labels": [
            {
                "order": row.order,
                "pdf_token": row.pdf_token,
                "status": "made" if row.made else "pending",
                "tracking_number": (row.answer or {}).get("tracking_number"),
                "insured": row.insured,
                "made_at": row.made_at,
                "scanned_at": _scanned_at(row.scan),
                "checked_at": (row.scan or {}).get("at"),
                "scan": _scan_status(row.scan),
            }
            for row in rows
        ]
    }


def do_shipping_label_pdf(token: str) -> Tuple[bytes, str, str]:
    """The stored label for a `pdf_token`: bytes, content type, a safe file name. An order number
    is no key: only the random token finds a row, by one indexed read."""
    _write_held()
    found =Store().read().ledger.labels.where(pdf_token=token) if _TOKEN.fullmatch(token) else []
    row = found[0] if found else None
    if row is not None and row.made and not row.pdf:
        refused = _fill_pdfs([row])
        if refused is not None:
            raise _refusal(refused)
        row = Store().read().ledger.labels.get(row.order)
    if row is None or not row.made or not row.pdf:
        raise ShippingRefusal(HTTPStatus.NOT_FOUND, "label_not_found", "No label has been made for that order.")
    return base64.b64decode(row.pdf), "application/pdf", "label-{}.pdf".format(_safe_name(row.order))


def do_shipping_labels_scans(payload: dict) -> dict:
    """`POST /shipping/labels/scans` — look up each made label's scan status and store it (T5).

    On demand only. A 404 is that row's status and the press goes on. Any other refusal ends the
    press, and the rows already read stay stored."""
    _only(payload, ())
    _ready()
    orders = [row.order for row in Store().read().ledger.made_labels()]
    found = 0
    missing: List[str] = []
    for order in orders:
        stamp = order_store.now()
        try:
            scan: Dict[str, Any] = {"at": stamp, "answer": tcgtracking.track(order_number=order)}
            found += 1
        except tcgtracking.TrackingRefused as exc:
            if exc.code != "tracking_not_found":
                raise _refusal(exc) from None
            scan = {"at": stamp, "status": exc.code}
            missing.append(order)
        with Store().write() as snap:
            snap.ledger.record_scan(order, scan)
    return {"checked": len(orders), "found": found, "not_found": missing}

# --------------------------------------------------------- what this module may never do
#
# NEVER DERIVE `Package Weight`. `Product Weight` is a summed per-product catalog constant
# and a lower bound on the parcel; postage bought against it is postage due at the far end.
# `pipeline/pirateship.py`'s header calls this the rule most likely to be "fixed" by a later
# session, and this is that session being told.
#
# NEVER DEFAULT AN UNJUDGED ORDER INTO A LANE. `shipping.parcel_lane` already excludes them
# and nothing here may add them back. Sweeping them into the parcel lane is a postage charge
# the operator did not choose; sweeping them into the envelope lane is a playmat in a stamped
# mailer. Both are the operator's decision, made looking at the order.
#
# NEVER WRITE AN INSURANCE COLUMN INTO THE PIRATE SHIP FILE. `pirateship.check_no_insurance`
# RAISES rather than dropping the column, and that is correct: insurance on a parcel is a
# per-order judgement the owner makes inside Pirate Ship, and a handler that quietly dropped the
# column would let a caller think it had been carried. An envelope label's insurance is a switch
# on each order, off unless the confirm names the order in `insured` (D326).
#
# NEVER COMPOSE A POSITION LABEL. `pipeline/join.py:Position` is the only label formula in
# this repo — a second one here would be the second-renderer failure it has already recorded
# three times, and since D58 a card's number needs the box's whole occupancy to draw at all.
# `do_shipping_stamps` therefore takes strings from `locate` and writes them out unchanged;
# the only thing it composes is `_stamp_text`'s join, which is a list of labels and not a
# label.
#
# NEVER SLICE AN ORDER'S STAMPS TO FIT. Three corners is the format's whole answer, and an
# order needing four positions gets none — see `do_shipping_stamps`. A truncated pick list
# reads as a complete one, which is a wrong shelf rather than an obviously broken label, and
# it is the same failure `pirateship.Parcel` refuses to enforce a stamp LENGTH over.
