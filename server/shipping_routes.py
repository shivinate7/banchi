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

BUILT 2026-09-05 — `POST /shipping/batches/<batch>/stamps` (T2b). It fills Pirate Ship's
three Rubber Stamp columns from the order ledger, so the label in the operator's hand IS the
pick instruction. Both of the reasons this header gave for there being no code here are
spent: the `store.orders.OrderRecord -> pipeline.orders.Order` adapter the order branch also
needed is `server/capture_server.py:_engine_order`, whose own docstring calls itself THE ONLY
ADAPTER, so the two-branches-one-file collision D66 warned of cannot happen any more; and
D63's maps stopped being empty on 2026-09-02, when twenty real orders with real SKUs were
fetched into the owner's ledger, so the control has something to answer.

  **THIS MODULE STILL HOLDS NO STORE AND COMPOSES NO LABEL, and both halves are the seam.**
  `do_shipping_stamps` takes a `locate` callable and hands it ORDER NUMBERS — which it
  already has, and which are not a buyer's anything — and gets back strings. It never sees a
  `Snapshot`, an `Inventory` or a `Ledger`, so the file an operator reads to answer "where
  does the PII go" did not grow a second subject. The strings come from
  `pipeline/join.py:Position` by way of `_Places`, which is the one label formula in this
  repo; the closing note below says why a second one here would be a defect.
"""

from __future__ import annotations

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
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

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

    `parcels` IS KEPT RATHER THAN RE-DERIVED because the stamps route named in the module
    docstring re-renders this same set with three columns filled. Re-parsing would mean
    holding the export text, which is the thing this record refuses to hold.

    `parcels` IS THE UNSTAMPED SET AND STAYS THAT WAY. `do_shipping_stamps` renders its own
    stamped copies with `dataclasses.replace` and hands those over without keeping them, so
    what a later press starts from is the export's own reading. That is belt to the braces
    rather than the braces: what actually makes the press idempotent is that every parcel's
    `stamps` is SET on every press — `()` where the order earned none — and never added to.

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
# `do_shipping_stamps` therefore takes strings from `locate` and writes them out unchanged;
# the only thing it composes is `_stamp_text`'s join, which is a list of labels and not a
# label.
#
# NEVER SLICE AN ORDER'S STAMPS TO FIT. Three corners is the format's whole answer, and an
# order needing four positions gets none — see `do_shipping_stamps`. A truncated pick list
# reads as a complete one, which is a wrong shelf rather than an obviously broken label, and
# it is the same failure `pirateship.Parcel` refuses to enforce a stamp LENGTH over.
