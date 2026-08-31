"""The ONE module in this server that holds a buyer's name and street address.

`server/tcg_export.py` is a separate file because the secret never leaves it. This file is
separate for the mirror-image reason: it is the only module in this server that ever holds a
buyer's real name and real street address, and the only one that emits them. An operator
reading the routes wants ONE file to check when they ask "where does the PII go", and a
reviewer changing a handler wants to know they are inside that file rather than beside it.
Everything here reads an export the operator uploaded, routes it into three lanes, and hands
back an import CSV; nothing here writes a file, opens a socket, reads a key, starts a child,
or takes the store lock.

TWO COSTS, RECORDED RATHER THAN DISCOVERED:

  **The batch table lives in this process's memory only.** So two devices do not share a
  batch — the phone that read the export cannot download the import file from the laptop —
  and a server restart drops every one of them. `make up` reloads the capture server on any
  Python edit under `server/`, so an edit during a session is a restart, and the refusal for
  a batch that is gone says so in those words rather than reading as a bug.

  **D61's rule that buyer PII passes through and is NOT persisted is what
  `pirateship.render` returning BYTES rather than a path exists to make possible, and this
  module must not undo it.** The rendered import lives in this dict for at most
  `BATCH_TTL_SECONDS`, is handed to the operator's browser, and touches no disk on the way.
  A cache directory, a temp file, a run-directory artefact or a log line carrying a row
  would each be the persistence that decision refuses — and each would be one line to add
  here, which is why the prohibition is written down beside the code rather than only in the
  entry.

SPECIFIED AND NOT BUILT — `POST /shipping/batches/<batch>/stamps`. It would fill Pirate
Ship's three Rubber Stamp columns from the order ledger, so the label in the operator's hand
IS the pick instruction. NO CODE FOR IT EXISTS HERE, deliberately, and for two reasons:
both of D63's maps are empty today, so the control could only ever answer "nothing"; and it
needs a `store.orders.OrderRecord -> pipeline.orders.Order` adapter that the order branch
also needs, which is exactly the two-branches-one-file collision D66 told us to avoid. The
wire already carries `stamp` on every row and `stamps` on the batch as nulls, so the later
route changes no type and no component.
"""

from __future__ import annotations

import re
import secrets
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# STDLIB-ONLY AT MODULE SCOPE, like `server/pipeline_routes.py`. `make server` runs
# `python3` and not the venv, so a module this server imports may not need `make venv`;
# both of these reach `csv`, `io`, `codecs`, `dataclasses`, `decimal`, `fractions`,
# `pathlib` and `typing` and nothing else.
from pipeline import pirateship, shipping  # noqa: E402

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

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


# -------------------------------------------------------------------------- the holder


@dataclass
class _Batch:
    """One read export, held for as long as the operator is working through it.

    THE SOURCE CSV IS NOT IN HERE, and its absence is the point: it is dropped the moment
    `shipping.parse` has read it, so the only buyer PII this process retains is the rendered
    `blob` and the `parcels` it was rendered from. `rows` — what the screen draws — carries
    an order number, a lane, a reason and two numbers, and no name, street, city or postcode
    at all.

    `parcels` IS KEPT RATHER THAN RE-DERIVED because the future stamps route named in the
    module docstring re-renders this same set with three columns filled. Re-parsing would
    mean holding the export text, which is the thing this record refuses to hold.
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


# A `ThreadingHTTPServer` serves each request on its own thread, so every read and write of
# this table is under the lock. Ordered so eviction is oldest-first without a sort.
_BATCHES: "OrderedDict[str, _Batch]" = OrderedDict()
_LOCK = threading.Lock()


def _new_batch_id() -> str:
    """128 unguessable bits, and the id IS the access control.

    `GET` is in `capture_server.SAFE_METHODS`, so the download is NOT behind the origin
    gate, and `HOST` is `0.0.0.0`. Anything on the network that can reach this port can ask
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
            "Cannot set {} here. Settable: {}.".format(
                ", ".join(unknown), ", ".join(allowed)
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


def _row(shipment: shipping.Shipment, routing: shipping.Routing) -> Dict[str, Any]:
    """One order as the screen draws it: which lane, on what grounds, and how sure.

    `certain` is carried rather than inferred from `reason` at the far end, because
    `Routing.certain` is the module that owns the distinction and a second copy of the rule
    in TypeScript is the second-renderer failure this repo has already recorded.

    `stamp` IS ALWAYS `None` TODAY — the null the future stamps route will fill. See the
    module docstring for why it is a null and not an absent key.
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
        "stamp": None,
    }


# ----------------------------------------------------------------------------- handlers

_BATCH_FIELDS: Tuple[str, ...] = ("name", "content")


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
    )
    key = _remember(batch)

    return {
        "batch": key,
        "name": batch.name,
        "expires_in": BATCH_TTL_SECONDS,
        "shipments": batch.shipments,
        "rows": list(rows),
        # STRAIGHT FROM `shipping.lane_counts` / `shipping.reason_counts`, WHICH SEED EVERY
        # KEY INCLUDING THE ZEROS — do not filter them. "Nothing was unjudged" and "nothing
        # was checked" must not be the same payload.
        "lane_counts": lane_tally,
        "reason_counts": reason_tally,
        "parcel_count": batch.parcel_count,
        "file": {"name": IMPORT_FILENAME, "bytes": len(blob)},
        "stamps": None,
    }


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
            "{!r} is not a file of this batch. It holds one: {}.".format(
                filename, IMPORT_FILENAME
            ),
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
# NEVER WRITE AN INSURANCE COLUMN. `pirateship.check_no_insurance` RAISES rather than
# dropping the column, and that is correct: insurance is a per-order judgement the owner
# makes inside Pirate Ship, and a handler that quietly dropped the column would let a caller
# think it had been carried.
#
# NEVER COMPOSE A POSITION LABEL. `pipeline/join.py:Position` is the only label formula in
# this repo — a second one here would be the second-renderer failure it has already recorded
# three times, and since D58 a card's number needs the box's whole occupancy to draw at all.
