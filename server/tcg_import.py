"""The outbound WRITE to the seller admin — the only place in this repo that can change a price a buyer sees.

WHY THIS IS NOT IN `server/tcg_export.py`. That module's docstring makes four promises, and
the second is **"It cannot cause a charge."** Everything it does is a download of the
operator's own data. Putting a write beside it would either falsify that promise or force it
to be narrowed to a technicality, which is the move D16 exists to catch. So the write lives
here, under its own promises, and that file's stay true.

WHAT THIS MODULE PROMISES INSTEAD, since a module that can move money owes a stricter set:

  - **Two operations, both explicit, and one of them is not reversible by pressing again.**
    `push_to_staged` writes to the operator's STAGED inventory, which no buyer can see;
    `move_to_live` publishes one staged upload. Nothing here is implicit, cached, or
    retried on the caller's behalf.
  - **A move is scoped to ONE upload and cannot be scoped any other way.** The portal's own
    control offers three scopes — 1 "This Page", 2 "My Search Results", 3 "this upload" —
    and only 3 is reachable from here, because 1 and 2 would publish rows this pipeline
    never staged and cannot describe. `SCOPE_THIS_UPLOAD` is a constant, not a parameter.
  - **A failed push is rolled back, not left half-written.** The portal's own client does
    this (`rollBackUpload`), and a staged upload abandoned mid-transaction is a pile of rows
    the operator has to find and clear by hand.
  - **The secret never leaves this module**, and neither does a response body: TCGplayer
    echoes product names and ids, and a refusal message composed from one would put store
    contents into a log. Messages here are composed from a status code and constants.

THE TRANSPORT IS BORROWED, NOT COPIED. `tcg_export._open` carries the redirect discipline —
one hop, never to the logon page, a 3xx delivered rather than followed — and D104 already
settled that this rule gets ONE implementation because it is the part that rots in a copy.
So the private helpers are imported deliberately. What is NOT shared is the promise set: the
import is the reason this is a separate file, and the export's guarantees are why it could
not be the same one.

THE PAYLOAD SHAPE WAS READ OFF THE PORTAL'S OWN BUNDLE, NOT GUESSED. Every field below comes
from `PricingStagedPrice` in `admin/scripts/pricing/main-built.js`, which is the constructor
their importer runs over each CSV row. FOUR OF THE FIVE HAVE BEEN RUN AGAINST THE OWNER'S REAL
ACCOUNT on 2026-09-06: `initializeexportcsv`, `uploadexportcsv` and `finalizeexportcsv` for a
100-row file TCGplayer accepted, and then the whole chain plus `movetolive` for a single row —
Vilemaw, $23.22 to $750.00 and back, confirmed on the portal's own Live grid. `rollbackexportcsv`
is the one still only read. `docs/specs/stale-listings.md` §6 carries the timeline.

WHAT THAT RUN ALSO MEASURED, and it is not about this module: `Export From Live` is NOT
read-your-writes. Forty seconds after a confirmed publish it still served the pre-publish price
while the grid served the new one — so `pkmnscan reconcile --live`, which writes `live` off that
export (D87), records the old price if it runs straight after a publish. Nothing guards it.

JQUERY'S DEEP FORM ENCODING IS THE WIRE FORMAT, AND IT IS NOT JSON. `$.post` with a nested
array serialises to `data[0][ProductConditionId]=...&data[0][MyPrice]=...`, and the observed
body was 46,560 bytes for 100 rows — ~465 per row, which is eleven form fields with escaped
names and rules out a JSON body. `_form` below reproduces that encoding.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import tcg_export  # noqa: E402
from server.tcg_export import FetchRefusal  # noqa: E402

# THE HOST IS THE EXPORT'S HOST, and it is derived from that module rather than restated so
# an override cannot move one and leave the other pointing at the real portal.
BASE = "https://store.tcgplayer.com"

INITIALIZE = "/admin/pricing/initializeexportcsv"
UPLOAD = "/admin/pricing/uploadexportcsv"
FINALIZE = "/admin/pricing/finalizeexportcsv"
ROLLBACK = "/admin/pricing/rollbackexportcsv"
MOVE_TO_LIVE = "/admin/pricing/movetolive"

# `type` is a STRING and not an integer. The page's own settings object is
# `pricingTypes: { Buylist: 'Buylist', Pricing: 'Pricing' }` — read out of the live page on
# 2026-09-06, because the bundle only ever compares against the symbol.
TYPE_PRICING = "Pricing"

# 750, from `self2.CHUNK_SIZE = 750` in their bundle. Matched rather than chosen: a smaller
# value is more requests for no gain, and a larger one is a body size their server has never
# been asked for. THE PORTAL FIRES ITS CHUNKS CONCURRENTLY and this module does not — four
# request slots are shared with the whole capture server (CLAUDE.md), and a 750-row chunk is
# already one request per 350KB.
CHUNK_SIZE = 750

# Their own validator's ceiling, from `MAX_LISTING_PRICE = 2e5`, with the floor from the
# `min` rule on `MyPrice`. Checked HERE so a bad figure is refused before a transaction is
# opened rather than after some chunks have landed.
MIN_PRICE = 0.01
MAX_PRICE = 200000.0

# Only "this upload". See the module promise above: 1 and 2 are reachable in their UI and
# deliberately not from here.
SCOPE_THIS_UPLOAD = 3

# The ten fields `PricingStagedPrice` reads, mapped from the export's own column names.
# ORDER IS THIS DICT'S ORDER and matters only for reproducibility of the body, not for the
# server — but a stable body is what makes a captured request diffable against a later one.
COLUMNS: Sequence[Tuple[str, str]] = (
    ("ProductConditionId", "TCGplayer Id"),
    ("CategoryName", "Product Line"),
    ("SetName", "Set Name"),
    ("ProductName", "Product Name"),
    ("ConditionName", "Condition"),
    ("AddToQuantity", "Add to Quantity"),
    ("MyPrice", "TCG Marketplace Price"),
    ("ProOnlineStoreReserveQuantity", "My Store Reserve Quantity"),
    ("ProOnlineStorePrice", "My Store Price"),
    ("Number", "Number"),
)


def unclear(refusal: FetchRefusal) -> bool:
    """Might TCGplayer have done the work this refused write was asking for?

    THE ONE READING OF A FAILED WRITE, and a send's whole safety turns on it
    (`D-one-press-sends-and-makes-live`, round 2). A CLEAR refusal — a 4xx, a redirect to the
    login page, a redirect anywhere else — is a request the portal turned away before acting.
    An UNCLEAR one — no answer in time, a dropped connection, a 5xx, a 200 whose body is not
    JSON — is a request the portal may have carried out and then failed to report. A caller
    never takes copies back on an unclear answer; it holds them until a live read says.
    """
    if refusal.code in ("tcg_unreachable", "tcg_write_unreadable"):
        return True
    if refusal.code == "tcg_write_refused":
        return refusal.status is None or int(refusal.status) >= 500
    return False


class PushFailed(FetchRefusal):
    """A push that stopped part-way, and whether the upload it opened was rolled back.

    `upload_id` is None when no upload was opened, so nothing can be waiting at TCGplayer.
    `rolled_back` is True only when the portal ANSWERED the rollback; False means the upload
    may still sit in the operator's Staged list, which a person can publish by hand. The
    caller's rule (`server/send_routes.py`): copies go back on the list only on True or on no
    upload at all.
    """

    def __init__(self, cause: FetchRefusal, upload_id, rolled_back):
        super().__init__(cause.code, cause.message, getattr(cause, "status", None))
        self.cause = cause
        self.upload_id = upload_id
        self.rolled_back = rolled_back


class StagedUpload:
    """What a completed push is: an id, and what the portal said about it.

    `upload_id` IS THE WHOLE POINT. It is what `move_to_live` scopes to and what
    `rollback` undoes, so a push that cannot report one is a push that cannot be finished
    or reversed — which is why `push_to_staged` refuses rather than returning a partial.
    """

    def __init__(self, upload_id: str, rows: int, accepted: int, messages: List[str]):
        self.upload_id = upload_id
        self.rows = rows
        self.accepted = accepted
        self.messages = messages

    def as_dict(self) -> dict:
        return {
            "upload_id": self.upload_id,
            "rows": self.rows,
            "accepted": self.accepted,
            "messages": self.messages,
        }


def _url(path: str) -> str:
    """The absolute URL, with the export module's override honoured.

    THE OVERRIDE IS SHARED ON PURPOSE. `PKMNSCAN_TCG_EXPORT_URL` exists so a test can point
    the cookie at a loopback server, and a knob that redirected reads but not writes would
    send a real price change to the real portal during exactly the test that was trying to
    avoid it.
    """
    base = BASE
    try:
        override = tcg_export.endpoint()
        parsed = urllib.parse.urlparse(override)
        if parsed.scheme and parsed.netloc:
            base = f"{parsed.scheme}://{parsed.netloc}"
    except FetchRefusal:
        # `endpoint()` refuses on a malformed override. A write must not fall back to the
        # real portal when the operator has said "point somewhere else and I got it wrong".
        raise
    return base + path


def _form(fields: Dict[str, object]) -> bytes:
    """jQuery's `$.param` for the shapes this module sends: scalars and a list of dicts.

    NOT `urlencode`, WHICH CANNOT EXPRESS THE ROWS. `data` is a list of dicts and their
    server reads `data[0][MyPrice]`; `urlencode({"data": [...]})` would stringify the whole
    list into one value and the server would see no rows at all.
    """
    pairs: List[Tuple[str, str]] = []

    def put(key: str, value: object) -> None:
        if value is None:
            # jQuery sends an empty string for null/undefined, not the literal "None".
            pairs.append((key, ""))
        elif isinstance(value, bool):
            pairs.append((key, "true" if value else "false"))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                put(f"{key}[{index}]", item)
        elif isinstance(value, dict):
            for name, item in value.items():
                put(f"{key}[{name}]", item)
        else:
            pairs.append((key, str(value)))

    for key, value in fields.items():
        put(key, value)
    return urllib.parse.urlencode(pairs).encode("utf-8")


def _post(path: str, fields: Dict[str, object]) -> dict:
    """One form POST on the operator's session, decoded as JSON.

    EVERY REFUSAL IS COMPOSED FROM A STATUS AND A CONSTANT. The portal echoes product names
    and, on some errors, the submitted row; putting a response body into a message would put
    store contents into a log line and, on the logon page, HTML carrying the session state.
    """
    url = _url(path)
    status, headers, body = tcg_export._open(
        url,
        cookie=tcg_export._cookie(),
        data=_form(fields),
        content_type="application/x-www-form-urlencoded; charset=UTF-8",
    )
    if status in (301, 302, 303, 307, 308):
        location = str(headers.get("Location") or "").lower()
        if "logon" in location or "login" in location:
            raise FetchRefusal(
                "tcg_session_expired",
                "TCGplayer redirected the write to its login page, so the stored session has "
                "expired. Nothing was written. Sign in again and replace "
                "TCGPLAYER_STORE_COOKIE in .env.",
            )
        raise FetchRefusal(
            "tcg_unexpected_redirect",
            f"TCGplayer redirected {path} somewhere other than the login page. Nothing here "
            f"follows a redirect on a write, so nothing was written.",
        )
    if status != 200:
        # NOT "NOTHING WAS WRITTEN" ANY MORE, which this sentence said until the adversarial
        # review of 2026-09-24. A 5xx is the portal failing AFTER it may have done the work —
        # the stand-in's `published_then_5xx` mode is exactly that — so only a 4xx is a
        # request turned away. `unclear` below is the one reading of the difference.
        raise FetchRefusal(
            "tcg_write_refused",
            f"TCGplayer answered {status} to {path}.",
            status=status,
        )
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise FetchRefusal(
            "tcg_write_unreadable",
            f"TCGplayer answered 200 to {path} with a body that is not JSON, which is what "
            f"an interstitial or a WAF challenge looks like. Nothing is assumed to have been "
            f"written, and nothing further was sent.",
        ) from None


def rows_from_csv(text: str) -> List[dict]:
    """The import CSV as the rows their importer builds, one dict per line.

    THIS IS THE SAME READ THE BROWSER DOES, and it is deliberately not a re-derivation from
    the store: what gets pushed must be what is in the file the operator can open, download
    and diff. `csv.DictReader` and never `split(",")` — CLAUDE.md's rule, and this file has
    product names with commas in them.
    """
    import csv
    import io

    rows: List[dict] = []
    for index, record in enumerate(csv.DictReader(io.StringIO(text))):
        row: Dict[str, object] = {"Id": index}
        for field, column in COLUMNS:
            value = record.get(column)
            row[field] = "" if value is None else value.strip()
        rows.append(row)
    return rows


def _check(rows: Sequence[dict], *, listing: bool = False) -> None:
    """Refuse a file their validator would refuse, before a transaction exists.

    THE CHECKS ARE THEIRS, NOT THIS REPO'S OPINION. `MyPrice` between 0.01 and 200000 and
    `AddToQuantity` an integer are `PricingStagedPrice`'s own validation extenders. Running
    them here turns "chunk 3 of 5 failed and now there is a half-written staged upload" into
    a refusal with nothing sent.

    `listing` IS THE ONE DOOR FOR A FILE THAT ADDS COPIES (`D-one-press-sends-and-makes-live`),
    and it is a keyword so no existing caller can reach it by position. A price file keeps
    D100's zero rule exactly as it was. A listing row must add a whole number of copies, 1 or
    more: the listing file is written by `emit` behind the double-send guard
    (`pipeline/sendguard.py`), and a negative figure is a file this repo did not write. A row
    adding 0 would change only a price, and a price goes through the price door, where D100's
    zero rule stays whole (the round-2 review). WHETHER
    THIS DOOR SHOULD EXIST IS STILL THE OWNER'S OPEN QUESTION (the decision entry's "D100's
    check on the transport"), and nothing sends through it before the owner's first test.
    """
    if not rows:
        raise FetchRefusal("tcg_import_empty", "That file has no rows, so there is nothing to push.")
    for row in rows:
        sku = str(row.get("ProductConditionId") or "")
        if not sku:
            raise FetchRefusal(
                "tcg_import_no_sku",
                "A row carries no TCGplayer Id. TCGplayer refuses the whole file for that, so "
                "nothing was sent.",
            )
        try:
            price = float(str(row.get("MyPrice")))
        except (TypeError, ValueError):
            raise FetchRefusal(
                "tcg_import_bad_price",
                f"SKU {sku} carries a TCG Marketplace Price that is not a number. Nothing was "
                f"sent.",
            ) from None
        if not (MIN_PRICE <= price <= MAX_PRICE):
            raise FetchRefusal(
                "tcg_import_bad_price",
                f"SKU {sku} is priced at {price}, outside the {MIN_PRICE}–{MAX_PRICE:.0f} "
                f"TCGplayer accepts. Nothing was sent.",
            )
        try:
            quantity = int(str(row.get("AddToQuantity")))
        except (TypeError, ValueError):
            raise FetchRefusal(
                "tcg_import_bad_quantity",
                f"SKU {sku} carries an Add to Quantity that is not an integer. Nothing was sent.",
            ) from None
        if listing:
            if quantity <= 0:
                # A LISTING ROW ADDS AT LEAST ONE COPY. A row adding none would only move a
                # price, and a price moves through a mark-down's door, where D100's zero rule
                # holds whole (the round-2 review). `emit` never writes such a row.
                raise FetchRefusal(
                    "tcg_import_moves_quantity",
                    f"SKU {sku} carries Add to Quantity {quantity}. A listing file only ever "
                    f"adds copies, so nothing was sent.",
                )
            continue
        if quantity != 0:
            # NOT TCGPLAYER'S RULE — THIS REPO'S. D100 is built on every row of every file
            # this path writes carrying 0, which is what makes an accidental re-upload a
            # no-op. A non-zero quantity here means the file did not come from `reprice`.
            raise FetchRefusal(
                "tcg_import_moves_quantity",
                f"SKU {sku} carries Add to Quantity {quantity}, and this path only ever "
                f"pushes 0 — that is what makes uploading the same file twice a no-op (D100). "
                f"Nothing was sent.",
            )


def push_to_staged(
    rows: Sequence[dict], filename: str = "import.csv", *, listing: bool = False
) -> StagedUpload:
    """Initialize, upload every chunk, finalize. Rolls back if any chunk or the finalize fails.

    NOTHING A BUYER CAN SEE CHANGES HERE. Staged is the operator's own working copy; measured
    2026-09-06, a 100-row push moved 0 of 759 live prices and 0 live quantities. Publishing is
    `move_to_live`, a second call. Since `D-one-press-sends-and-makes-live` one PRESS makes
    both calls, and they stay two calls so a failed publish can still roll this upload back.
    """
    _check(rows, listing=listing)

    try:
        opened = _post(INITIALIZE, {"filename": filename, "type": TYPE_PRICING})
    except FetchRefusal as refusal:
        # NO UPLOAD ID, SO NOTHING TO ROLL BACK AND NO ROW SENT. Even an unclear answer here
        # is safe: an upload the portal opened and never named holds no rows.
        raise PushFailed(refusal, None, None) from None
    upload_id = opened.get("StagedPricingUploadId")
    if not upload_id:
        raise PushFailed(
            FetchRefusal(
                "tcg_import_not_opened",
                "TCGplayer accepted the request to start an upload but named no upload id, so "
                "there is nothing to add rows to and nothing to roll back. Nothing was written.",
            ),
            None,
            None,
        )

    accepted = 0
    messages: List[str] = []
    try:
        for start in range(0, len(rows), CHUNK_SIZE):
            chunk = list(rows[start : start + CHUNK_SIZE])
            answer = _post(
                UPLOAD,
                {
                    "data": chunk,
                    "stagedPricingUploadId": upload_id,
                    "fileName": filename,
                    "type": TYPE_PRICING,
                },
            )
            accepted += int(answer.get("SuccessfulProductCount") or 0)
            for message in answer.get("Messages") or []:
                messages.append(str(message))
        _post(
            FINALIZE,
            {
                "stagedPricingUploadId": upload_id,
                "productCount": accepted,
                "type": TYPE_PRICING,
            },
        )
    except FetchRefusal as refusal:
        # THE ROLLBACK'S FAILURE DOES NOT REPLACE THE REAL REFUSAL, AND IT IS NO LONGER
        # SWALLOWED EITHER. What went wrong is still the refusal the caller reads; whether the
        # upload was cleared is the second fact, carried on `PushFailed`, because a caller that
        # puts copies back on the list over an upload still waiting in Staged has set up the
        # double send this module exists to prevent (the 2026-09-24 review, S1-b).
        rolled = True
        try:
            rollback(str(upload_id))
        except FetchRefusal:
            rolled = False
        raise PushFailed(refusal, str(upload_id), rolled) from None

    return StagedUpload(str(upload_id), len(rows), accepted, messages)


def rollback(upload_id: str) -> None:
    """Undo one staged upload. The portal's own `rollBackUpload`, minus the chunk aborts."""
    _post(ROLLBACK, {"stagedPricingUploadId": upload_id, "type": TYPE_PRICING})


def move_to_live(upload_id: str) -> dict:
    """PUBLISH one staged upload. This changes what buyers pay.

    THE SCOPE IS FIXED AT 3 AND IS NOT A PARAMETER — see the module promises. Their own UI
    sets `scope(3)` the instant a `stagedPricingUploadId` exists, and 1 and 2 would publish
    rows this pipeline never staged.

    `connectionId` IS SENT EMPTY AND THAT IS NOT A GAP. It is a SignalR handle their page
    uses to receive `onUpdate`/`onStatus` progress callbacks, and their own
    `establishConnection` resolves its deferred inside `.always()` — so their client
    proceeds with the move even when the hub connection has failed. What is lost without it
    is the percentage, not the operation.

    `searchModel` IS SENT EMPTY FOR THE SAME REASON THE SCOPE IS FIXED: it narrows scopes 1
    and 2, and it is read for neither under scope 3.
    """
    if not upload_id:
        raise FetchRefusal(
            "tcg_move_no_upload",
            "A move to live names one staged upload, and no id was given. Nothing was sent.",
        )
    return _post(
        MOVE_TO_LIVE,
        {
            "searchModel": "",
            "scope": SCOPE_THIS_UPLOAD,
            "connectionId": "",
            "stagedPricingUploadId": upload_id,
            "type": TYPE_PRICING,
        },
    )
