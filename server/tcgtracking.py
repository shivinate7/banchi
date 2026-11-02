"""The ONE client of TCGTracking (D326): buy a label, read its scans, fetch its PDF again.

`create(body)`, `track(order_number=|tracking_number=)` and `pdf(order_id)` are the whole surface.
Every call goes out through `pipeline/net.open` (D319, one retry home). A create is
`idempotent=False` and follows no redirect: a second create after the first may have been
sent could buy twice, though TCGTracking answers a repeated `source_order_id` with
`duplicate: true`. This is the only file that names the TCGTracking host.

THE KEY AND THE SHIPPER NUMBER are read on every call with `envfile.get_live`, because the key
rotates, and are sent as the `X-API-Key` and `X-Shipper-Number` headers. THE KEY APPEARS IN NO
ANSWER, REFUSAL, LOG LINE OR STORE ROW. So no header, key or upstream body is logged, a refusal
carries a fixed sentence per code and never quotes what the host said (a 401 body may echo the
key), and every `TrackingRefused` is raised `from None` so no chained exception carries one.

EVERY FAILURE IS A `TrackingRefused` WITH A `tracking_` CODE: key or shipper number missing
(raised before any request), host refused (the default host under `BANCHI_HARNESS` or `CI`, or
plain http beyond loopback; no socket), rejected (401), invalid (400), rate limited (429),
not found (404), unreachable (no connection, a server error, or an answer this module cannot
read). A create answer is a bought label only when it carries an `order_id`, a 500's included:
`create` returns it, and the caller must keep it.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import envfile  # noqa: E402
from pipeline import net  # noqa: E402

KEY_ENV = "TCG_TRACKING_KEY"
SHIPPER_ENV = "TCG_TRACKING_SHIPPER_NUMBER"
# The test seam. Unset, the default host is called.
URL_ENV = "BANCHI_TCGTRACKING_URL"
DEFAULT_BASE = "https://tcgtracking.com/api/v1"
REAL_HOST = "tcgtracking.com"
# The smallest label envelope size TCGTracking offers, the one an envelope-lane order ships in.
ENVELOPE_SIZE = "10"
# A create can take several seconds to render a PDF. It is not retried once it may have been sent.
TIMEOUT_SECONDS = 30

_LOOPBACK = ("127.0.0.1", "localhost", "::1")

MESSAGES: Dict[str, str] = {
    "tracking_key_missing": (
        "The TCGTracking key is missing from the Mac's settings file (the .env file in the app's "
        "folder). Nothing was sent to TCGTracking."
    ),
    "tracking_shipper_missing": (
        "The TCGTracking shipper number is missing from the Mac's settings file (the .env file in "
        "the app's folder). Nothing was sent to TCGTracking."
    ),
    "tracking_auth_rejected": (
        "TCGTracking rejected the key. Put a current key in the Mac's settings file, then try again."
    ),
    "tracking_invalid": (
        "TCGTracking refused the request as invalid. Check the address and the order, then try again."
    ),
    "tracking_rate_limited": (
        "TCGTracking is limiting this account for now. Wait a little, then press again."
    ),
    "tracking_not_found": "TCGTracking has no match for that order.",
    "tracking_unreachable": (
        "TCGTracking could not be reached, or gave an answer this server cannot read. Pressing again "
        "is safe: a label already made is not bought a second time."
    ),
    "tracking_host_refused": (
        "This server will not call that TCGTracking address: the real host is not called from the "
        "test rig or CI, and plain http is allowed only on this Mac."
    ),
}


class TrackingRefused(Exception):
    """A call TCGTracking, or this module, refused. `code` is a `tracking_` code; the text is fixed
    per code and never quotes the host's answer."""

    def __init__(self, code: str) -> None:
        super().__init__(MESSAGES[code])
        self.code = code


def _refuse(code: str):
    raise TrackingRefused(code) from None


def _base() -> str:
    """The base URL after the host guard, or `tracking_host_refused`.

    The guard reads the HOST of the address, never the whole string: a query, a port, a trailing dot
    or capitals reach the real host as well as the default text does."""
    override = (envfile.get_live(URL_ENV) or "").strip().rstrip("/")
    parts = urllib.parse.urlsplit(override or DEFAULT_BASE)
    host = (parts.hostname or "").lower().rstrip(".")
    if (host == REAL_HOST or host.endswith("." + REAL_HOST)) and (os.environ.get("BANCHI_HARNESS") or os.environ.get("CI")):
        _refuse("tracking_host_refused")
    if not override:
        return DEFAULT_BASE
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOOPBACK):
        return override
    return _refuse("tracking_host_refused")


def ready() -> Dict[str, str]:
    """The headers for a call, after the key, the shipper number and the host are all checked. Raises
    before any request is made. A caller about to spend calls this first, so a press that cannot
    succeed writes nothing."""
    key = (envfile.get_live(KEY_ENV) or "").strip()
    if not key:
        _refuse("tracking_key_missing")
    shipper = (envfile.get_live(SHIPPER_ENV) or "").strip()
    if not shipper:
        _refuse("tracking_shipper_missing")
    _base()
    return {"X-API-Key": key, "X-Shipper-Number": shipper, "Accept": "application/json"}


def presence() -> tuple:
    """`(key_present, shipper_present)`: whether the settings file holds each. Never the values."""
    return bool(envfile.get_live(KEY_ENV).strip()), bool(envfile.get_live(SHIPPER_ENV).strip())


def _call(method: str, path: str, *, query: Optional[Dict[str, str]] = None, body: Optional[dict] = None) -> tuple:
    """`(status, parsed JSON or None)` for any HTTP answer. A failure to reach the host is
    `tracking_unreachable`. The body is parsed and never quoted."""
    headers = ready()
    url = _base() + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        status, _, raw = net.open(
            url,
            method=method,
            data=data,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
            idempotent=method == "GET",
            follow_redirects=False,
        )
    except net.NetError:
        _refuse("tracking_unreachable")
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, ValueError):
        parsed = None
    return status, (parsed if isinstance(parsed, dict) else None)


def _answer(status: int, parsed: Optional[dict], *, bought: bool = False) -> dict:
    """The answer dict for a good status, else the refusal for the status. With `bought`, an answer
    is good only when it names an `order_id`: a 2xx without one bought nothing."""
    if status in (200, 201) and parsed is not None and (not bought or parsed.get("order_id")):
        return parsed
    if bought and status == 500 and parsed is not None and parsed.get("order_id"):
        # The label was bought. The error text is dropped: an error body is never kept.
        return {k: v for k, v in parsed.items() if k != "error"}
    codes = {401: "tracking_auth_rejected", 400: "tracking_invalid", 429: "tracking_rate_limited", 404: "tracking_not_found"}
    if status in codes:
        _refuse(codes[status])
    # A 5xx, a redirect, or a 2xx this module cannot read are all "no usable answer". Another 4xx is a request this module built wrongly.
    _refuse("tracking_invalid" if 400 <= status < 500 else "tracking_unreachable")


def create(body: dict) -> dict:
    """Buy one label. Returns TCGTracking's answer: 201, or 200 with `duplicate: true` and no PDF, or the
    answer of a 500 that carries an `order_id`. An answer with no `order_id` is `tracking_unreachable`:
    nothing was bought, so the caller releases its claim and a later press creates again."""
    status, parsed = _call("POST", "/orders", body=body)
    return _answer(status, parsed, bought=True)


def track(*, order_number: Optional[str] = None, tracking_number: Optional[str] = None) -> dict:
    """The scan status of one label, by TCGplayer order number or by tracking number. 404 is
    `tracking_not_found`: no match, or no scan yet."""
    query = {"order_number": order_number} if order_number else {"tracking_number": tracking_number or ""}
    status, parsed = _call("GET", "/orders/track", query=query)
    return _answer(status, parsed)


def pdf(order_id: str, size: str = ENVELOPE_SIZE) -> bytes:
    """The label PDF of one TCGTracking order id, as bytes (the API answers it as base64 in JSON)."""
    status, parsed = _call("GET", "/orders/" + urllib.parse.quote(str(order_id), safe="") + "/pdf", query={"size": size})
    return decode_pdf(_answer(status, parsed))


def decode_pdf(answer: Dict[str, Any]) -> bytes:
    """The bytes of an answer's `pdf_base64`, or `tracking_unreachable` when it is absent or unreadable."""
    try:
        return base64.b64decode(str(answer.get("pdf_base64") or "")) or _refuse("tracking_unreachable")
    except (binascii.Error, ValueError):
        return _refuse("tracking_unreachable")
