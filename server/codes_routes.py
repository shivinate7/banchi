"""The code-card track's routes. All free; one of them commits codes to a buyer.

ITS OWN MODULE, FOR `pipeline_routes.py`'s REASON ONE REGISTER DOWN. That module is separate
because it is the one part of the server that can cause money to be SPENT. This one is
separate because it is the one part that can cause a bearer instrument to be COMMITTED: a
code handed to a buyer cannot be un-handed, and double-selling one is unrecoverable. Nothing
here costs money — there is no model call anywhere on this track's primary path — so the
gate is not D33's money gate. It is the same SHAPE though, and deliberately so: a free
preview that reserves nothing, then a named, confirmed commit.

    GET  /codes                    the ledger: counts, product tiers, every entry
    POST /codes/scan               decode a box's photographs into the ledger. FREE.
    POST /codes/export             preview a channel export, or COMMIT one to an order

THE CODES TRAVEL IN THE CLEAR ON THIS WIRE, and that is correct rather than an oversight.
The server binds loopback, the store is the owner's own machine, and the whole point of the
Codes screen is that the owner can read a code and paste it to a buyer. The opsec rules
govern what reaches a COMMIT — `scripts/guard-opsec.sh` and the pre-commit hook — not what
reaches the owner's own browser. `codes/ledger.py` masks codes in EXCEPTION text for a
different reason: an exception string ends up in logs and in a bug report.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from codes import ledger, products, qr
from codes import scan as codescan
from store import files
from store.session import Store

# The two lanes C11 settles. A lane is not a channel — it is which of the two POPULATIONS a
# code belongs to, and the channel is chosen outside this repo. Naming them here rather than
# naming eBay or a buylist is deliberate: the channel research found every venue MARGINAL and
# the buy side actively closing, so a route that hardcoded one would be betting on the least
# durable finding in the whole spec.
LANE_BULK = "bulk"
LANE_PREMIUM = "premium"
LANES = (LANE_BULK, LANE_PREMIUM)


class CodesRefusal(RuntimeError):
    """A refusal with a code and an HTTP status, mirroring `pipeline_routes.PipelineRefusal`."""

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def _refuse(status: HTTPStatus, code: str, message: str):
    raise CodesRefusal(status, code, message)


def _entry_row(entry: ledger.Entry) -> dict:
    return {
        "code": entry.code,
        "state": entry.state,
        "product": entry.product,
        "product_display": products.display(entry.product) if entry.product else None,
        "premium": products.is_premium(entry.product),
        "set_hint": entry.set_hint,
        "box": entry.box,
        "index": entry.index,
        "photo": entry.photo,
        "source": entry.source,
        "scanned_at": entry.scanned_at,
        "state_at": entry.state_at,
        "order_id": entry.order_id,
        "buyer": entry.buyer,
        "delivered_at": entry.delivered_at,
        "dead_reason": entry.dead_reason,
        "well_formed": ledger.well_formed(entry.code),
        "duplicate_positions": list(entry.duplicate_positions),
    }


def do_codes() -> dict:
    """The whole ledger, plus the two summaries a screen needs before it draws a row.

    NOT PAGINATED, and the number that decides it is the pile: a code line is about 400
    bytes, so ten thousand codes is four megabytes and a hundred thousand is forty. The
    first is nothing and the second is a problem this track does not have yet and would
    notice immediately. Paginating now would buy a scroll position bug today against a
    payload size nobody has measured.
    """
    entries = ledger.read()
    held = [e for e in entries if e.sellable]
    return {
        "counts": ledger.counts(entries),
        "total": len(entries),
        # The two lanes, counted. This is C11's operating rule made visible before any
        # row is drawn: the screen's whole job is to keep the $1.39 population from being
        # swept into the same submission as the $0.03 one.
        "lanes": {
            LANE_PREMIUM: sum(1 for e in held if products.is_premium(e.product)),
            LANE_BULK: sum(1 for e in held if e.product and not products.is_premium(e.product)),
            "unclaimed": sum(1 for e in held if not e.product),
        },
        "by_product": products.summarise(held),
        # A non-empty list here is a real finding, not bookkeeping: either one card was
        # photographed twice or two cards carry one code, and in the second case one of
        # them is worth nothing.
        "duplicates": [_entry_row(e) for e in entries if e.duplicate_positions],
        "entries": [_entry_row(e) for e in entries],
        "products": [
            {
                "key": p["key"],
                "display": p["display"],
                "premium": p["premium"],
                "redeem_limit": p["redeem_limit"],
            }
            for p in products.PRODUCTS
        ],
    }


def _box_of(payload: dict) -> int:
    raw = payload.get("box")
    try:
        box = int(raw)
    except (TypeError, ValueError):
        _refuse(HTTPStatus.BAD_REQUEST, "box_required",
                f"box was {raw!r}; send the box number whose photographs should be scanned.")
    if box < 1:
        _refuse(HTTPStatus.BAD_REQUEST, "box_required", "a box number is 1 or higher.")
    return box


def do_codes_scan(payload: dict, captures_root) -> Tuple[HTTPStatus, dict]:
    """Decode one box's photographs into the ledger. FREE — no model call, no network.

    TAKES A BOX, NOT A PATH. A path from a browser would be an arbitrary-filesystem-read
    hole in a server that otherwise only ever touches paths it composed itself, and the box
    is what the operator is actually thinking in.
    """
    box = _box_of(payload)
    preview = bool(payload.get("preview"))
    directory = Path(captures_root) / f"box{box}"
    if not directory.is_dir():
        _refuse(HTTPStatus.NOT_FOUND, "box_has_no_photos",
                f"nothing has been captured into box {box} — {directory} does not exist.")
    try:
        reading = codescan.read_directory(directory, box=box)
    except qr.QrUnavailable as exc:
        # 503 rather than 500: the server is fine, its decoder is missing, and the remedy is
        # an install rather than a bug report.
        _refuse(HTTPStatus.SERVICE_UNAVAILABLE, "decoder_missing", str(exc))

    body = {
        "box": box,
        "photographs": reading.photographs,
        "code_cards": reading.code_cards,
        "decoded": len(reading.entries),
        "unread": reading.problems,
        "malformed": [e.code for e in reading.malformed],
        "preview": preview,
    }
    if preview:
        _, counts = ledger.merge(ledger.read(), reading.entries)
        body["would"] = counts
        return HTTPStatus.OK, body

    with Store().write() as writable:
        merged, counts, stamped = codescan.apply(writable, reading.entries)
    body["counts"] = counts
    body["stamped"] = stamped
    body["on_file"] = len(merged)
    return HTTPStatus.OK, body


def _lane_of(payload: dict) -> str:
    lane = str(payload.get("lane") or "").strip().lower()
    if lane not in LANES:
        _refuse(HTTPStatus.BAD_REQUEST, "lane_invalid",
                f"lane was {payload.get('lane')!r}; use one of {', '.join(LANES)}.")
    return lane


def _pool(entries, lane: str, product: Optional[str]) -> List[ledger.Entry]:
    def wanted(entry) -> bool:
        if not entry.sellable:
            return False
        if product is not None:
            return entry.product == product
        if lane == LANE_PREMIUM:
            return products.is_premium(entry.product)
        # THE BULK LANE EXCLUDES UNCLAIMED CODES RATHER THAN SWEEPING THEM IN, and that is
        # the one judgement in this module worth arguing. A code with no product claim MIGHT
        # be a booster, and treating it as one would be right most of the time — which is
        # exactly why it is refused. Being wrong here means a $1.39 Pokemon Center ETB code
        # leaves in a wholesale lot at a penny, and the operator never learns it happened.
        # The screen names the unclaimed count so the fix is a correction, not a guess.
        return bool(entry.product) and not products.is_premium(entry.product)

    return [e for e in entries if wanted(e)]


def do_codes_export(payload: dict) -> Tuple[HTTPStatus, dict]:
    """Preview a channel export, or commit one to an order.

    D33's TWO-STEP SHAPE, FOR A DIFFERENT IRREVERSIBLE THING. Without `confirm` this reserves
    nothing and is a pure read: it says how many codes the lane holds and shows the first few.
    With `confirm` and an `order_id` it RESERVES every code it returns, atomically, and those
    codes can never be handed to anybody else — which is C3's "atomic dequeue" and the whole
    structural defense against double-selling.

    ALL OR NOTHING. A partial fill would leave an order half-served with some codes committed
    against it, which is worse than refusing: the operator can source more stock or split the
    order, but cannot easily discover that three of fifty went out and forty-seven did not.
    """
    lane = _lane_of(payload)
    product = payload.get("product")
    if product is not None:
        product = str(product).strip().lower()
        if product not in products.KEYS:
            _refuse(HTTPStatus.BAD_REQUEST, "product_invalid",
                    f"product was {payload.get('product')!r}; "
                    f"use one of {', '.join(products.KEYS)}.")
    raw_count = payload.get("count")
    confirm = bool(payload.get("confirm"))

    entries = ledger.read()
    pool = _pool(entries, lane, product)

    if raw_count is None:
        count = len(pool)
    else:
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            _refuse(HTTPStatus.BAD_REQUEST, "count_invalid",
                    f"count was {raw_count!r}; send a whole number, or omit it to take the lane.")
        if count < 1:
            _refuse(HTTPStatus.BAD_REQUEST, "count_invalid", "count is 1 or higher.")

    body = {
        "lane": lane,
        "product": product,
        "available": len(pool),
        "count": min(count, len(pool)),
        "committed": False,
    }

    if not confirm:
        body["sample"] = [e.code for e in pool[:5]]
        body["note"] = (
            "PREVIEW — nothing is reserved. Confirming assigns every code below to this "
            "order permanently; a reserved code is never offered again."
        )
        return HTTPStatus.OK, body

    order_id = str(payload.get("order_id") or "").strip()
    if not order_id:
        _refuse(HTTPStatus.BAD_REQUEST, "order_id_required",
                "a confirmed export assigns codes to an order, so it needs an order_id. "
                "Any string you can find the sale by later will do.")
    if len(pool) < count:
        _refuse(HTTPStatus.CONFLICT, "not_enough_codes",
                f"{count} asked for, {len(pool)} sellable in the {lane} lane"
                + (f" for {product}" if product else "")
                + " — nothing was reserved.")

    buyer = str(payload.get("buyer") or "").strip() or None
    with Store().write():
        entries = ledger.read()
        pool = _pool(entries, lane, product)
        if len(pool) < count:
            # Re-checked INSIDE the lock. The pool above was read without one, and a capture
            # server writing between the two reads is exactly the race this store's single
            # lock exists to settle.
            _refuse(HTTPStatus.CONFLICT, "not_enough_codes",
                    f"{count} asked for, {len(pool)} sellable once the store lock was held "
                    "— nothing was reserved.")
        taken = [
            ledger.reserve(entries, entry.code, order_id=order_id, buyer=buyer)
            for entry in pool[:count]
        ]
        ledger.write(entries)

    body["committed"] = True
    body["order_id"] = order_id
    body["buyer"] = buyer
    body["codes"] = [e.code for e in taken]
    body["note"] = (
        f"{len(taken)} code(s) reserved against {order_id}. They will never be offered "
        "again. Mark them delivered once the buyer has them."
    )
    return HTTPStatus.OK, body
