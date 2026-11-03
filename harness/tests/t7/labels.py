"""T7 group: the TCGTracking label pipe (T4 labels under the money gate, T5 tracking back).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

THE FAKE IS THE CONTRACT. `_Tracking` stands in for TCGTracking on 127.0.0.1, counts every
request and fails any path it does not know. The builder meets the answer shapes below, so a
shape that differs from the real API is changed here, once:

    POST /orders              201 {"success": true, "order_id": "TT-0001", "ordernum": "T7-ORD-0001",
                                   "tracking_number": "9400********0001", "pdf_base64": <base64 of the label>,
                                   "pdf_size_bytes": <int>, "carrier_note": "T7-WHOLE-ANSWER-1"}
                              (`carrier_note` is a T7 marker and not an API field: it proves the
                              store keeps the whole answer.)
    POST /orders              200 {"success": true, "order_id": ..., "ordernum": ..., "tracking_number": ...,
                                   "duplicate": true} for a `source_order_id` it has seen: NO pdf_base64
    GET  /orders/<id>/pdf     200 {"pdf_base64": <base64 of the label>, "tracking_number": "9400********0001"},
                              query `size`
    GET  /orders/track        200 {"order_number": <asked>, "status": "T7-SCAN-MARK accepted",
                                   "events": [{"scan": "accepted", "timestamp": <ISO time>}, ...]}
                              404 when nothing matches or no scan has happened yet
    every request             headers X-API-Key and X-Shipper-Number (asserted by `check_labels_auth_headers`)

The shapes are the live API's (read from tcgtracking.com/api/index.php), except the event
`timestamp` key: the live event shape is unread, so the key is a T7 assumption. Every label PDF the
fake hands out is a valid one-page PDF whose page height is 400 plus the id's last four digits, so a
combined file can be told page from page.

THE LABEL ROUTES ARE THE MODULE DOCSTRING OF `server/shipping_routes.py`, plus four routes and one
field it does not yet name (their shape is pinned by the cases below, and only as far as a case reads it):

    pdf_token                     on each GET /shipping/labels row: 32 hex characters, distinct per row.
    GET  /shipping/labels/<pdf_token>/pdf    the stored bytes. The ORDER NUMBER in that place answers 404.
    POST /shipping/batches/<b>/labels/stop   body {}. Ends a confirm after the create in flight.
    GET  /shipping/batches/<b>/labels/pdf    one PDF of every label made for the batch's orders.

THE ROUTES ARE DRIVEN OVER A REAL SOCKET, not through a `do_*` function, because the contract
names paths and not the module that serves them. `server/tcgtracking.py` is imported inside each
check: today it is absent, and one import error at module scope would take every sibling T7
check down with it.

WHAT THE CASES DO NOT PIN, so the builder is free there: the status and code of a refused
confirm, whether a key or shipper refusal is a whole-request error or a `refused` entry (the
code is looked for anywhere in the answer), the top-level shape of the label listing (the
longest list in it is the rows), the insurance field's name (any key holding "insur"), the
body of a stop answer, whether a stopped confirm also names the orders it left in `refused`,
and the refusal for a batch with no labels (any 4xx with a code, or a 404).
"""

from __future__ import annotations

import base64
import contextlib
import csv
import functools
import http.server
import io
import json
import logging
import os
import re
import socket
import threading
import time
import traceback
import urllib.parse
import urllib.request
from unittest import mock

from harness.tests import Checks
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    error_code,
    fresh_hosts,
    isolated_home,
    quiet,
    request,
    store_tables,
)
from harness.tests.t7.shipping import SHIPPING_EXPORT, home_files
from server import capture_server

# A value no fixture, fake answer or message contains. It is the whole secret-leak test.
SENTINEL = "t7-sentinel-key-9f4c2e61b7d0"
SHIPPER = "T7SHIP0042"
SCAN_MARK = "T7-SCAN-MARK"
# The fake's scan events, deliberately out of order: the row's `scanned_at` is the latest, not the first or the last.
SCAN_TIMES = ("2026-11-01T10:00:00Z", "2026-11-02T08:15:00Z", "2026-10-31T17:45:00Z")
LATEST_SCAN = max(SCAN_TIMES)
FEE_WORDS = "fee per your TCGTracking account"
RECEIPT_KEYS = {"made", "existing", "refused", "partial"}


# ------------------------------------------------------------------------------ the fake


class _Tracking:
    """TCGTracking on loopback. `script(n, request)` may answer the nth create `(status, body)`;
    returning None gives the default bought answer. `track_script` does the same for the nth
    track lookup. `hold` parks the create numbered `hold_at` (the first, by default) until
    `release` is set, so a second press can arrive while that create is in flight. `alias` maps each identifier an answer handed out (order
    id, `ordernum`, masked tracking number) to the TCGplayer order it was made for, so a lookup
    or fetch by any of them still names its order in `requests`."""

    def __init__(self, orders):
        self.orders = tuple(orders)
        self.lock = threading.Lock()
        self.requests = []
        self.unknown = []
        self.pdfs = {}
        self.alias = {}
        self.script = None
        self.track_script = None
        self.hold = False
        self.hold_at = 1
        self.arrived = threading.Event()
        self.release = threading.Event()

    @property
    def creates(self):
        return [r for r in list(self.requests) if r["method"] == "POST" and r["path"] == "/orders"]

    @property
    def tracks(self):
        return [r for r in list(self.requests) if r["method"] == "GET" and r["path"] == "/orders/track"]

    def pdf_for(self, order_id):
        return self.pdfs.setdefault(order_id, self.page(order_id))

    @staticmethod
    def tail(order_id):
        return (re.sub(r"\D", "", order_id)[-4:] or "0").zfill(4)

    @classmethod
    def page(cls, order_id):
        """A valid one-page PDF with a real xref table. The page is 288 points wide and 400 + the id's tail high."""
        objects = (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 288 %d] >>" % (400 + int(cls.tail(order_id))),
        )
        out, at = b"%PDF-1.4\n% T7-LABEL-PDF-" + order_id.encode() + b"\n", []
        for number, body in enumerate(objects, 1):
            at.append(len(out))
            out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
        table = b"".join(b"%010d 00000 n \n" % offset for offset in at)
        size = len(objects) + 1
        return out + b"xref\n0 %d\n0000000000 65535 f \n%strailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            size, table, size, len(out))

    def label(self, order_id, **more):
        """The fields every create answer carries."""
        tail = self.tail(order_id)
        return {
            "success": True,
            "order_id": order_id,
            "ordernum": f"T7-ORD-{tail}",
            "tracking_number": f"9400********{tail}",
            **more,
        }

    def bought(self, n):
        order_id = f"TT-{n:04d}"
        pdf = self.pdf_for(order_id)
        return self.label(
            order_id,
            carrier_note=f"T7-WHOLE-ANSWER-{n}",
            pdf_base64=base64.b64encode(pdf).decode(),
            pdf_size_bytes=len(pdf),
        )

    def duplicate(self, order_id):
        """The answer for a `source_order_id` TCGTracking has seen: no PDF in it."""
        return self.label(order_id, duplicate=True)

    def handler(self):
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003
                pass

            def _reply(self, status, body, kind="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _serve(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                parts = urllib.parse.urlsplit(self.path)
                text = raw.decode("utf-8", "replace") + " " + parts.query
                named = urllib.parse.unquote_plus(parts.path + " " + text)
                entry = {
                    "method": self.command,
                    "path": parts.path,
                    "query": parts.query,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": raw,
                    "order": next((o for o in fake.orders if o in text), None)
                    or next((o for a, o in list(fake.alias.items()) if a in named), None),
                }
                with fake.lock:
                    fake.requests.append(entry)
                    n = len(fake.creates)
                    tracked = len(fake.tracks)
                if entry["method"] == "POST" and parts.path == "/orders":
                    if fake.hold and n == fake.hold_at:
                        fake.arrived.set()
                        fake.release.wait(10)
                    scripted = fake.script(n, entry) if fake.script else None
                    status, body = scripted or (201, fake.bought(n))
                    for key in ("order_id", "ordernum", "tracking_number"):
                        if isinstance(body, dict) and isinstance(body.get(key), str):
                            fake.alias[body[key]] = entry["order"]
                    return self._reply(status, body)
                if entry["method"] == "GET" and parts.path == "/orders/track":
                    scripted = fake.track_script(tracked, entry) if fake.track_script else None
                    if scripted:
                        return self._reply(*scripted)
                    asked = (urllib.parse.parse_qs(parts.query).get("order_number") or [""])[0]
                    events = [{"scan": "accepted", "timestamp": when} for when in SCAN_TIMES]
                    return self._reply(200, {"order_number": asked, "status": f"{SCAN_MARK} accepted", "events": events})
                match = re.fullmatch(r"/orders/([^/]+)/pdf", parts.path)
                if entry["method"] == "GET" and match and match.group(1) in fake.pdfs:
                    return self._reply(
                        200,
                        {
                            "pdf_base64": base64.b64encode(fake.pdfs[match.group(1)]).decode(),
                            "tracking_number": f"9400********{fake.tail(match.group(1))}",
                        },
                    )
                fake.unknown.append(f"{entry['method']} {self.path}")
                return self._reply(404, {"error": "no such path"})

            do_GET = _serve  # noqa: N815
            do_POST = _serve  # noqa: N815

        return Handler


# ----------------------------------------------------------------------------- the rig


class _Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class _Rig:
    """One isolated store, the capture server over it, and the fake. Every response body is kept
    in `wire` and every caught refusal text in `texts`, for the secret scan."""

    def __init__(self, home, fake, port, logs, out):
        self.home, self.fake, self.port, self.logs, self.out = home, fake, port, logs, out
        self.wire, self.texts = [], []
        self.batch = None
        self.envelope, self.parcel = [], []

    def raw(self, method, path, payload=None):
        """`(status, body bytes, headers)`: for an answer that is not JSON, such as a PDF."""
        status, body, headers = request(self.port, method, path, payload=payload)
        self.wire.append(body.decode("utf-8", "replace") + repr(headers))
        return status, body, headers

    def call(self, method, path, payload=None):
        status, body, _ = self.raw(method, path, payload)
        try:
            doc = json.loads(body)
        except ValueError:
            doc = {}
        return status, (doc if isinstance(doc, dict) else {"_list": doc})

    def upload(self, checks):
        """Read the committed Export Shipping through the real route; lanes come from its rows."""
        status, doc = self.call(
            "POST", "/shipping/batches", {"name": "orders-shipping.csv", "content": SHIPPING_EXPORT.read_text("utf-8")}
        )
        rows = doc.get("rows") or []
        self.batch = doc.get("batch")
        self.envelope = [r["order"] for r in rows if r.get("lane") == "envelope"]
        self.parcel = [r["order"] for r in rows if r.get("lane") == "parcel"]
        return checks.ok(
            status == 200 and len(self.envelope) >= 8 and self.parcel,
            "a batch is read from the committed Export Shipping, with envelope and parcel orders",
            f"status {status}",
        )

    @property
    def labels_path(self):
        return f"/shipping/batches/{self.batch}/labels"

    def preview(self):
        return self.call("POST", self.labels_path, {"preview": True})

    def confirm(self, orders, insured=None):
        payload = {"confirm": True, "orders": list(orders)}
        if insured is not None:
            payload["insured"] = list(insured)
        return self.call("POST", self.labels_path, payload)

    def listing(self):
        status, doc = self.call("GET", "/shipping/labels")
        return status, _rows(doc)

    def press_held(self, orders):
        """Start a confirm on its own thread and wait until the fake has parked one of its creates.
        Returns `(thread, got)`; `got` gains the confirm's `(status, doc)` when it ends. The caller
        sets `fake.hold_at` first when the create to park is not the first one the fake sees."""
        self.fake.hold = True
        got = []
        thread = threading.Thread(target=lambda: got.append(self.confirm(orders)), daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not self.fake.arrived.is_set() and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        return thread, got

    def key_sent(self):
        return any(SENTINEL in _blob(r) for r in self.fake.requests)


@contextlib.contextmanager
def _rig(*, serve=True):
    """A rig with key, shipper and the fake's address in the environment. `BANCHI_HARNESS` is
    set, which proves the loopback override still works under the harness."""
    fresh_hosts()
    with isolated_home() as home, quiet() as out:
        with open(SHIPPING_EXPORT, newline="", encoding="utf-8") as handle:
            orders = [row[0] for row in list(csv.reader(handle))[1:]]
        fake = _Tracking(orders)
        tracking = http.server.ThreadingHTTPServer(("127.0.0.1", 0), fake.handler())
        tracking_thread = _spawn_server(tracking)
        os.environ.update(
            TCG_TRACKING_KEY=SENTINEL,
            TCG_TRACKING_SHIPPER_NUMBER=SHIPPER,
            BANCHI_TCGTRACKING_URL=f"http://127.0.0.1:{tracking.server_address[1]}",
            BANCHI_HARNESS="1",
        )
        logs, root = _Lines(), logging.getLogger()
        level = root.level
        root.addHandler(logs)
        root.setLevel(logging.DEBUG)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler) if serve else None
        thread = _spawn_server(httpd) if httpd else None
        try:
            yield _Rig(home, fake, httpd.server_address[1] if httpd else 0, logs, out)
        finally:
            fake.release.set()
            for server, worker in ((httpd, thread), (tracking, tracking_thread)):
                if server is not None:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)
            root.removeHandler(logs)
            root.setLevel(level)


def _guarded(check):
    """A check that raises is one FAIL line and not a crash of every T7 check behind it."""

    @functools.wraps(check)
    def run(checks: Checks) -> None:
        try:
            check(checks)
        except Exception as caught:  # noqa: BLE001 - the raise is the failure under test
            tail = traceback.format_exc().splitlines()[-6:]
            checks.ok(False, f"{check.__name__} ran to its end", f"{type(caught).__name__}: {caught}\n" + "\n".join(tail))

    return run


@contextlib.contextmanager
def _sealed(opened):
    """Every network entry point replaced by one that fails the case and notes the call in `opened`."""
    from pipeline import net

    def forbidden(*args, **kwargs):
        opened.append(args)
        raise AssertionError("a network call was made")

    with mock.patch.object(net, "open", forbidden), \
            mock.patch.object(urllib.request, "urlopen", forbidden), \
            mock.patch.object(socket, "create_connection", forbidden):
        yield


def _client(checks):
    """`server.tcgtracking`, or a FAIL line and None while the module does not exist."""
    try:
        from server import tcgtracking
    except ImportError as caught:
        checks.ok(False, "`server/tcgtracking.py` exists and imports", f"{type(caught).__name__}: {caught}")
        return None
    return tcgtracking


# --------------------------------------------------------------------- reading answers


def _rows(doc):
    """The rows of a listing: the longest list in the answer, whatever its key."""
    lists = [v for v in doc.values() if isinstance(v, list)]
    return [r for r in max(lists, key=len, default=[]) if isinstance(r, dict)]


def _names(items):
    """Order numbers in a receipt list: bare strings, or dicts holding `order`."""
    if not isinstance(items, list):
        return []
    return [i if isinstance(i, str) else i.get("order") for i in items if isinstance(i, (str, dict))]


def _codes(node):
    """Every `tracking_*` string anywhere in an answer."""
    if isinstance(node, str):
        return {node} if node.startswith("tracking_") else set()
    if isinstance(node, dict):
        node = list(node.values())
    if isinstance(node, list):
        return set().union(*(_codes(v) for v in node)) if node else set()
    return set()


def _row(rows, order):
    return next((r for r in rows if order in json.dumps(r, default=repr)), None)


def _pairs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key), value
            yield from _pairs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _pairs(value)


def _on(value):
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "none", "null")
    return bool(value)


def _insured(row):
    """The insurance switch of a stored row: True, False, or None when it carries no such key."""
    hits = [_on(v) for k, v in _pairs(row or {}) if "insur" in k.lower()]
    return any(hits) if hits else None


def _asks_insurance(body: bytes) -> bool:
    """Whether a create body asks for insurance: any key holding "insur" with a truthy value."""
    try:
        fields = json.loads(body)
    except ValueError:
        fields = {k: v for k, v in urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
    return any("insur" in k.lower() and _on(v) for k, v in _pairs(fields))


def _sent_body(rig, order):
    return next((c["body"] for c in rig.fake.creates if c["order"] == order), b"")


def _pdf_path(ref):
    """The stored label's path. `ref` is a listing row's `pdf_token`; an order number there is a refused ask."""
    return f"/shipping/labels/{urllib.parse.quote(str(ref), safe='')}/pdf"


def _token(rows, order):
    return (_row(rows, order) or {}).get("pdf_token")


def _pages(pdf):
    """The page heights of a PDF, in file order: through pypdf when it is importable, else by
    reading each object that is a `/Type /Page` and its MediaBox. A page of the fake is 288 wide
    and `400 + tail` high, so the heights name the labels a combined file holds."""
    try:
        import pypdf
    except ImportError:
        objects = re.findall(rb"\bobj\b(.*?)\bendobj\b", pdf, re.S)
        found = [re.search(rb"/MediaBox\s*\[([^\]]*)\]", o) for o in objects if re.search(rb"/Type\s*/Page(?![A-Za-z])", o)]
        return [int(float(m.group(1).split()[-1])) if m else 0 for m in found]
    return [int(float(page.mediabox.height)) for page in pypdf.PdfReader(io.BytesIO(pdf)).pages]


def _blob(req):
    return " ".join((req["path"], req["query"], json.dumps(req["headers"]), req["body"].decode("utf-8", "replace")))


def _stored(home) -> str:
    """Everything the store holds as text: its tables, and the bytes of every file under home
    (the SQLite file and its journal included)."""
    parts = [json.dumps(store_tables(), default=repr)]
    parts += [p.read_bytes().decode("latin-1") for p in home.rglob("*") if p.is_file()]
    return "\n".join(parts)


def _kept(text: str, data: bytes) -> bool:
    """Whether bytes are in a store dump, as they are, as base64 or as hex."""
    return any(form in text for form in (data.decode("latin-1"), base64.b64encode(data).decode(), data.hex()))


def _leaked(rig):
    places = {
        "a response": "\n".join(rig.wire),
        "a refusal text": "\n".join(rig.texts),
        "a log line": "\n".join(rig.logs.lines),
        "printed output": rig.out.getvalue(),
        "the store": _stored(rig.home),
    }
    return [name for name, text in places.items() if SENTINEL in text]


# ------------------------------------------------------------------------ the preview


@_guarded
def check_labels_preview(checks: Checks) -> None:
    """`POST /shipping/batches/<batch>/labels` with `{"preview": true}` is free (D33).

    It answers the count, every order with its lane verdict and insurance switch, and the fee
    sentence, and it makes no request to TCGTracking and writes no store row. The insurance
    switch is off for every order (D326). A parcel-lane order is held back and says why.

    The screen's own fields are pinned here too: the envelope size code and its readable label,
    whether the key and shipper are set (never their values), and the reason codes. THE COMMITTED
    EXPORT CAN MAKE THREE OF THE FIVE: `envelope`, `parcel` and `needs_a_look`. Every envelope-lane
    row in it has a full street, so `no_full_street` is not pinned (a case would need an export of
    its own). `already_labelled` needs a bought label, and `check_labels_preview_presence` has one.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, PREVIEW: free, no network, no store row (D326, D33)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        before = (store_tables(), home_files(rig.home))
        status, doc = rig.preview()
        checks.equal(status, 200, "the preview answers 200")
        checks.ok({"count", "orders", "fee_note"} <= set(doc), "and carries count, orders and fee_note", str(sorted(doc)))
        rows = [r for r in doc.get("orders") or [] if isinstance(r, dict)]
        checks.ok(
            bool(rows) and all({"order", "eligible", "reason", "insured"} <= set(r) for r in rows),
            "every order row carries order, eligible, reason and insured",
        )
        by_order = {r.get("order"): r for r in rows}
        checks.equal(
            doc.get("count"),
            sum(1 for r in rows if r.get("eligible") is True),
            "`count` is the number of orders it would label",
        )
        checks.ok(
            all(by_order.get(o, {}).get("eligible") is True for o in rig.envelope[:8]),
            "envelope-lane orders are eligible",
        )
        checks.ok(
            all(by_order.get(o, {}).get("eligible") is False and by_order[o].get("reason") for o in rig.parcel),
            "every parcel-lane order is held back, and each says why",
        )
        checks.ok(
            bool(rows) and all(r.get("insured") is False for r in rows),
            "the insurance switch is off for every order (D326, off by default)",
        )
        checks.ok(FEE_WORDS in str(doc.get("fee_note")), f"the fee note says \"{FEE_WORDS}\"", str(doc.get("fee_note")))
        checks.equal(doc.get("envelope_size"), "10", "`envelope_size` is the API's code for the size, \"10\"")
        label = doc.get("envelope")
        checks.ok(
            isinstance(label, str) and "envelope" in label.lower() and "10" in label and label != doc.get("envelope_size"),
            "and `envelope` is the readable label for that size",
            repr(label),
        )
        checks.ok(
            doc.get("key_present") is True and doc.get("shipper_present") is True,
            "`key_present` and `shipper_present` are true booleans while both are set",
            f"{doc.get('key_present')!r} {doc.get('shipper_present')!r}",
        )
        checks.ok(
            SENTINEL not in json.dumps(doc) and SHIPPER not in json.dumps(doc),
            "and the answer holds neither the key nor the shipper number",
        )
        unjudged = [o for o in by_order if o not in rig.envelope and o not in rig.parcel]
        checks.ok(
            bool(unjudged) and all(by_order[o].get("reason") == "needs_a_look" for o in unjudged),
            "every unjudged order is held back as `needs_a_look`",
        )
        checks.ok(
            all(by_order[o].get("reason") == "parcel" for o in rig.parcel),
            "and every parcel-lane order as `parcel`",
        )
        checks.equal(
            {r.get("reason") for r in rows},
            {"envelope", "parcel", "needs_a_look"},
            "so before any label the export gives exactly the reasons `envelope`, `parcel` and `needs_a_look`",
        )
        checks.equal(len(rig.fake.requests), 0, "the preview made no request to TCGTracking")
        checks.ok(
            (store_tables(), home_files(rig.home)) == before,
            "and wrote no store row and no file: no claim, no label row",
        )


@_guarded
def check_labels_preview_presence(checks: Checks) -> None:
    """The preview says whether the key and the shipper number are set, and which order is bought.

    Unsetting one variable flips its own flag to false and leaves the other true. The preview still
    answers 200, sends nothing and carries no value. After a confirm the bought order is held back as
    `already_labelled` and `count` falls by one: the reason code a replay would answer as `existing`.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, PREVIEW FIELDS: the key and shipper flags flip with their settings, a bought order is `already_labelled` (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        count = rig.preview()[1].get("count")
        for name, want in (
            ("TCG_TRACKING_KEY", {"key_present": False, "shipper_present": True}),
            ("TCG_TRACKING_SHIPPER_NUMBER", {"key_present": True, "shipper_present": False}),
        ):
            with mock.patch.dict(os.environ):
                os.environ.pop(name)
                status, doc = rig.preview()
            got = {flag: doc.get(flag) for flag in want}
            checks.ok(status == 200 and got == want, f"with {name} unset the preview answers 200 with {want}", f"{status} {got}")
            checks.ok(SENTINEL not in json.dumps(doc) and SHIPPER not in json.dumps(doc), "and the answer holds neither value")
        checks.equal(len(rig.fake.requests), 0, "no preview sent a request to TCGTracking")
        order = rig.envelope[0]
        rig.confirm([order])
        status, doc = rig.preview()
        row = next((r for r in doc.get("orders") or [] if r.get("order") == order), {})
        checks.ok(
            row.get("eligible") is False and row.get("reason") == "already_labelled",
            "after a confirm the bought order is held back as `already_labelled`",
            f"{row}",
        )
        checks.equal(doc.get("count"), count - 1, "and `count` falls by that one order")


# ---------------------------------------------------------------------- the money gate


@_guarded
def check_labels_money_gate(checks: Checks) -> None:
    """Nothing is bought without a confirm, a listed order and an envelope-lane order (D33).

    Five refused presses, one assertion across them: the fake saw no create and the store
    changed by no row. A refusal that left a claim behind would block the order for good. A
    right press at the end is the control: without it a route that does not exist refuses
    all five and the case passes.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, MONEY GATE: no confirm, unlisted order, parcel-lane order buy nothing (D33)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, parcel = rig.envelope[0], rig.parcel[0]
        before = store_tables()
        for payload, label in (
            ({"orders": [e1]}, "a press with no `confirm`"),
            ({"confirm": False, "orders": [e1]}, "a press with `confirm` false"),
            ({}, "an empty press"),
        ):
            status, doc = rig.call("POST", rig.labels_path, payload)
            checks.ok(400 <= status < 500 and not _names(doc.get("made")), f"{label} is refused", f"{status} {doc}")
        for order, label in (
            ("T7-NOT-IN-THE-BATCH-1", "a confirm for an order the preview never listed"),
            (parcel, "a confirm for a parcel-lane order"),
        ):
            status, doc = rig.confirm([order])
            held = status >= 400 or order in _names(doc.get("refused"))
            checks.ok(held and order not in _names(doc.get("made")), f"{label} is refused", f"{status} {doc}")
        checks.equal(len(rig.fake.creates), 0, "across all five presses the fake saw 0 creates")
        checks.ok(store_tables() == before, "and the refusals wrote no store row")
        status, doc = rig.confirm([e1])
        checks.ok(
            status == 200 and _names(doc.get("made")) == [e1] and len(rig.fake.creates) == 1,
            "and the same route buys when the press is right: 1 create (a missing route would refuse all five too)",
            f"{status} {doc}",
        )


# --------------------------------------------------------------- make, replay, insurance


@_guarded
def check_labels_make_and_replay(checks: Checks) -> None:
    """A confirm buys one label per order and keeps the whole answer; a replay buys none.

    Insurance is sent only for orders named in `insured` and is off when the field is omitted.
    The row keeps TCGTracking's whole answer (a field the screen never reads), the label PDF
    and the insured flag, and the listing shows one row per order.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, MAKE AND REPLAY: one create per order, the whole answer kept, a replay buys 0 (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2, e3 = rig.envelope[:3]
        status, doc = rig.confirm([e1, e2], insured=[e2])
        checks.equal(status, 200, "a confirm for two listed envelope orders answers 200")
        checks.ok(set(doc) >= RECEIPT_KEYS, "and the receipt carries made, existing, refused and partial", str(sorted(doc)))
        checks.equal(sorted(_names(doc.get("made"))), sorted([e1, e2]), "both orders are made")
        checks.ok(
            not _names(doc.get("existing")) and not _names(doc.get("refused")) and doc.get("partial") is False,
            "nothing existing, nothing refused, not partial",
        )
        sent = {c["order"]: c for c in rig.fake.creates}
        checks.equal(sorted(sent), sorted([e1, e2]), "the fake saw exactly one create per order, each naming its order")
        checks.ok(
            _asks_insurance(sent.get(e2, {}).get("body", b"")) and not _asks_insurance(sent.get(e1, {}).get("body", b"")),
            "insurance is in the create body for the order in `insured` and for no other",
        )
        checks.ok(rig.key_sent(), "the key reached the fake in some header, path or body (positive control)")
        checks.ok(
            any(SHIPPER in _blob(r) for r in rig.fake.creates),
            "and the shipper number is in the create request",
        )
        status, rows = rig.listing()
        checks.ok(status == 200 and len(rows) == 2, "GET /shipping/labels lists one row per labelled order", f"{status} {rows}")
        checks.ok(
            _insured(_row(rows, e2)) is True and _insured(_row(rows, e1)) is False,
            "and each row carries its insurance flag",
        )
        stored = _stored(rig.home)
        checks.ok(
            "T7-WHOLE-ANSWER-1" in stored and "T7-WHOLE-ANSWER-2" in stored,
            "the store keeps TCGTracking's whole answer, not a projection of it",
        )
        checks.ok(
            all(_kept(stored, rig.fake.pdf_for(f"TT-{n:04d}")) for n in (1, 2)),
            "and keeps each label PDF",
        )

        status, doc = rig.confirm([e1, e2], insured=[e2])
        checks.ok(
            status == 200
            and sorted(_names(doc.get("existing"))) == sorted([e1, e2])
            and not _names(doc.get("made")),
            "a replay of the same confirm makes nothing and names both orders as existing",
            f"{status} {doc}",
        )
        checks.equal(len(rig.fake.creates), 2, "and the fake saw no third create")

        status, doc = rig.confirm([e3])
        checks.equal(_names(doc.get("made")), [e3], "a confirm with no `insured` field makes the order")
        checks.ok(
            not _asks_insurance(_sent_body(rig, e3)) and _insured(_row(rig.listing()[1], e3)) is False,
            "and insurance defaults to off: nothing in the body, false on the row",
        )
        checks.equal(len(rig.listing()[1]), 3, "the listing now holds three rows, one per order")


@_guarded
def check_labels_listing_rows(checks: Checks) -> None:
    """The rows of `GET /shipping/labels` carry their status and three times.

    A create in flight is `pending`: no tracking number and a null `made_at`. A bought label is
    `made` with a `made_at`. Before a scan press `scanned_at` and `checked_at` are present and
    null. After it, `checked_at` is set and `scanned_at` is the latest event time in the answer
    (the fake lists its events out of order, so first and last both read wrong).
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, LISTING ROWS: pending then made, made_at, and the scan times null until a scan press (D326, T5)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        order, fake = rig.envelope[0], rig.fake
        press, _ = rig.press_held([order])
        checks.ok(fake.arrived.is_set(), "the create reached the fake and is held in flight")
        row = _row(rig.listing()[1], order) or {}
        checks.ok(
            row.get("status") == "pending" and not row.get("tracking_number") and row.get("made_at") is None,
            "while it is in flight the row is `pending`, with no tracking number and a null `made_at`",
            f"{row}",
        )
        fake.release.set()
        press.join(timeout=15)
        row = _row(rig.listing()[1], order) or {}
        checks.equal(row.get("status"), "made", "once bought the row is `made`")
        checks.ok(bool(row.get("tracking_number")) and isinstance(row.get("made_at"), str) and row["made_at"], "with a tracking number and a `made_at`", f"{row}")
        checks.ok(
            all(key in row and row[key] is None for key in ("scanned_at", "checked_at")),
            "and before a scan press `scanned_at` and `checked_at` are present and null",
            f"{row}",
        )
        rig.call("POST", "/shipping/labels/scans", {})
        row = _row(rig.listing()[1], order) or {}
        checks.ok(isinstance(row.get("checked_at"), str) and row["checked_at"], "after the press `checked_at` is set", f"{row}")
        checks.equal(row.get("scanned_at"), LATEST_SCAN, "and `scanned_at` is the latest event time in the track answer")


# ------------------------------------------------------------------------ the double press


@_guarded
def check_labels_double_press(checks: Checks) -> None:
    """Two confirms that overlap buy one label.

    The fake parks the first create until the second press has had time to arrive, so the
    claim written before the create is what the second press meets. A replay after the first
    press ends would pass without one.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, DOUBLE PRESS: two overlapping confirms make 1 label (D88, claim before create)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        order = rig.envelope[0]
        first, answers = rig.press_held([order])
        checks.ok(rig.fake.arrived.is_set(), "the first press's create reached the fake and is held in flight")
        second = threading.Thread(target=lambda: answers.append(rig.confirm([order])), daemon=True)
        second.start()
        time.sleep(0.6)
        rig.fake.release.set()
        first.join(timeout=15)
        second.join(timeout=15)
        checks.ok(not first.is_alive() and not second.is_alive(), "both presses answered")
        made = [n for _, doc in answers for n in _names(doc.get("made"))]
        checks.equal(len(rig.fake.creates), 1, "the fake saw exactly 1 create")
        checks.equal(made, [order], "and exactly one press reports the order as made")
        checks.ok(all(s < 500 for s, _ in answers), "and neither press answered with a server error", str(answers))
        checks.equal(len(rig.listing()[1]), 1, "and the store holds 1 label row")


@_guarded
def check_labels_stop(checks: Checks) -> None:
    """`POST /shipping/batches/<batch>/labels/stop` ends a confirm after the create in flight.

    The fake parks the first create of a four-order confirm and a stop arrives meanwhile. That
    create finishes and its label is kept (nothing is voided: the fake sees no request but the
    create), no second create is sent, and the confirm's receipt makes 1 and is partial. A stop with
    nothing in flight answers 200 and changes nothing, and it leaves no mark: the confirm after it
    makes both its orders. A later confirm for the three that were left makes them.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, STOP: the create in flight finishes and is kept, no further create, a partial receipt (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        four, idle = rig.envelope[:4], rig.envelope[4:6]
        fake, stop = rig.fake, f"{rig.labels_path}/stop"
        before = (store_tables(), home_files(rig.home), len(fake.requests))
        status, doc = rig.call("POST", stop, {})
        checks.ok(
            status == 200 and (store_tables(), home_files(rig.home), len(fake.requests)) == before,
            "a stop with nothing in flight answers 200 and changes nothing: no store row, no file, no request",
            f"{status} {doc}",
        )
        status, doc = rig.confirm(idle)
        checks.ok(
            sorted(_names(doc.get("made"))) == sorted(idle) and doc.get("partial") is False,
            "and it leaves no mark: the next confirm makes both its orders",
            f"{status} {doc}",
        )
        fake.hold_at = len(fake.creates) + 1
        press, got = rig.press_held(four)
        checks.ok(fake.arrived.is_set(), "the first create of the four-order confirm reached the fake and is held in flight")
        halted = []
        stopper = threading.Thread(target=lambda: halted.append(rig.call("POST", stop, {})), daemon=True)
        stopper.start()
        time.sleep(0.6)
        fake.release.set()
        press.join(timeout=15)
        stopper.join(timeout=15)
        checks.ok(bool(halted) and halted[0][0] == 200, "the stop press answers 200", f"{halted}")
        status, doc = got[0] if got else (0, {})
        checks.equal(_names(doc.get("made")), four[:1], "the confirm's receipt makes 1: the order whose create was in flight")
        checks.ok(doc.get("partial") is True, "and the receipt is partial", f"{status} {doc}")
        checks.equal(len(fake.creates), len(idle) + 1, "no further create was sent after the stop")
        checks.ok(
            {(r["method"], r["path"]) for r in fake.requests} == {("POST", "/orders")} and not fake.unknown,
            "and the fake saw nothing but creates: the in-flight label was not voided",
        )
        rows = rig.listing()[1]
        mine = _row(rows, four[0]) or {}
        checks.ok(mine.get("status") == "made" and not any(_row(rows, o) for o in four[1:]), "the label is kept as a made row, and the other three have no row", f"{rows}")
        checks.ok(_kept(_stored(rig.home), fake.pdf_for(f"TT-{len(idle) + 1:04d}")), "and its label PDF is stored")
        status, doc = rig.confirm(four[1:])
        checks.equal(sorted(_names(doc.get("made"))), sorted(four[1:]), "a later confirm for the other three makes them all: the stop left no mark")


# ------------------------------------------------------------------ the client module


def _refuses(checks, tt, fn, code, label):
    try:
        fn()
    except Exception as caught:  # noqa: BLE001 - the type and code are the assertion
        got = getattr(caught, "code", None)
        checks.ok(isinstance(caught, tt.TrackingRefused) and got == code, label, f"{type(caught).__name__} code={got!r}: {caught}")
    else:
        checks.ok(False, label, "did not raise")


@_guarded
def check_labels_client(checks: Checks) -> None:
    """`server/tcgtracking.py`: `create`, `track` and `pdf`, and the six named refusals.

    Each refusal is a `TrackingRefused` with its code. A missing key or shipper sends no request
    at all, and a 401, 400 or 429 is one request and no retry (a create is not idempotent). A 500
    that carries an `order_id` is the answer of a bought label and is returned, not raised.
    """
    from pipeline import net

    checks.note("")
    checks.note("TCGTRACKING CLIENT: create, track, pdf and the six named refusals (D326, D319)")
    tt = _client(checks)
    if tt is None:
        return
    with _rig(serve=False) as rig:
        fake = rig.fake
        order = fake.orders[0]
        answer = tt.create({"source_order_id": order})
        checks.ok(isinstance(answer, dict) and answer.get("order_id") == "TT-0001", "`create` returns TCGTracking's answer as a dict", str(answer))
        label = tt.pdf("TT-0001", "T7SIZE")
        checks.ok(label == fake.pdf_for("TT-0001"), "`pdf` returns the label bytes")
        checks.ok("T7SIZE" in fake.requests[-1]["query"], "and sends the size it was given")
        scan = tt.track(order_number=order)
        checks.ok(isinstance(scan, dict) and SCAN_MARK in json.dumps(scan), "`track` returns the scan answer as a dict", str(scan))
        checks.ok(order in fake.requests[-1]["query"], "and asks by the order number")
        tt.track(tracking_number="9400000000000000001234")
        checks.ok("9400000000000000001234" in fake.requests[-1]["query"], "or by the tracking number")

        for missing, code, calls in (
            ("TCG_TRACKING_KEY", "tracking_key_missing", (("create", {"source_order_id": order}), ("track", None), ("pdf", None))),
            ("TCG_TRACKING_SHIPPER_NUMBER", "tracking_shipper_missing", (("create", {"source_order_id": order}),)),
        ):
            for name, argument in calls:
                before = len(fake.requests)
                with mock.patch.dict(os.environ):
                    os.environ.pop(missing)
                    call = {
                        "create": lambda a=argument: tt.create(a),
                        "track": lambda: tt.track(order_number=order),
                        "pdf": lambda: tt.pdf("TT-0001"),
                    }[name]
                    _refuses(checks, tt, call, code, f"`{name}` with {missing} unset raises `{code}`")
                checks.equal(len(fake.requests), before, f"and `{name}` sent 0 requests")

        for status, code in ((401, "tracking_auth_rejected"), (400, "tracking_invalid"), (429, "tracking_rate_limited")):
            before = len(fake.creates)
            fake.script = lambda n, e, s=status: (s, {"error": f"upstream {s} {SENTINEL}"})
            _refuses(checks, tt, lambda: tt.create({"source_order_id": order}), code, f"a {status} raises `{code}`")
            checks.equal(len(fake.creates) - before, 1, f"and the {status} was sent once and not retried")
        fake.script = lambda n, e: (500, {"order_id": "TT-BOUGHT-500", "error": "internal"})
        bought = None
        with contextlib.suppress(Exception):
            bought = tt.create({"source_order_id": order})
        checks.ok(
            isinstance(bought, dict) and bought.get("order_id") == "TT-BOUGHT-500",
            "a 500 whose body carries an `order_id` is returned as a bought label, not raised",
            str(bought),
        )
        fake.script = None

        shut = socket.socket()
        shut.bind(("127.0.0.1", 0))
        gone = shut.getsockname()[1]
        shut.close()
        with mock.patch.dict(os.environ, {"BANCHI_TCGTRACKING_URL": f"http://127.0.0.1:{gone}"}), mock.patch.object(net, "_sleep", lambda s: None):
            _refuses(checks, tt, lambda: tt.create({"source_order_id": order}), "tracking_unreachable", "a host that refuses the connection raises `tracking_unreachable`")


# --------------------------------------------------------------------- the host guard


@_guarded
def check_labels_default_host(checks: Checks) -> None:
    """The default TCGTracking host is refused under `BANCHI_HARNESS` or `CI`, and a plain
    http host that is not loopback is refused always. No socket is opened for either: the
    network entry points are replaced by ones that fail the case."""
    checks.note("")
    checks.note("TCGTRACKING HOST GUARD: the default host under BANCHI_HARNESS or CI, and non-loopback http (D326)")
    tt = _client(checks)
    if tt is None:
        return
    opened = []
    base = {"TCG_TRACKING_KEY": SENTINEL, "TCG_TRACKING_SHIPPER_NUMBER": SHIPPER}
    cases = (
        ({"BANCHI_HARNESS": "1"}, None, "the default host under BANCHI_HARNESS"),
        ({"CI": "1"}, None, "the default host under CI"),
        ({}, "http://tcgtracking.invalid", "a non-loopback http host, outside the harness and CI"),
    )
    for env, url, label in cases:
        with mock.patch.dict(os.environ, {**base, **env}), _sealed(opened):
            for name in ("BANCHI_HARNESS", "CI", "BANCHI_TCGTRACKING_URL"):
                if name not in env:
                    os.environ.pop(name, None)
            if url:
                os.environ["BANCHI_TCGTRACKING_URL"] = url
            for name, call in (
                ("create", lambda: tt.create({"source_order_id": "T7-X"})),
                ("track", lambda: tt.track(order_number="T7-X")),
                ("pdf", lambda: tt.pdf("TT-0001")),
            ):
                try:
                    call()
                except Exception as caught:  # noqa: BLE001 - the type is the assertion
                    checks.ok(
                        isinstance(caught, tt.TrackingRefused) and str(getattr(caught, "code", "")).startswith("tracking_"),
                        f"{label}: `{name}` raises a named `TrackingRefused`",
                        f"{type(caught).__name__}: {caught}",
                    )
                else:
                    checks.ok(False, f"{label}: `{name}` raises a named `TrackingRefused`", "did not raise")
    checks.equal(len(opened), 0, "and no network call was attempted in any of them")


# ------------------------------------------------------------ refusals through the route


@_guarded
def check_labels_refusals(checks: Checks) -> None:
    """Each named refusal answers its code, sends what it should and leaves no claim behind.

    Key missing and shipper missing send 0 requests. A 401, 400 and 429 send one. After every
    refusal the order has no label row, and a later confirm for the same order makes it: a
    refusal that kept the claim would block that order for good. The default host under
    `BANCHI_HARNESS` is refused through the route with no `net.open` call.
    """
    from pipeline import net

    checks.note("")
    checks.note("TCGTRACKING LABELS, REFUSALS: named codes, the right request count, no stuck claim (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2 = rig.envelope[:2]
        fake = rig.fake

        def attempt(label, code, requests, rows, env=None, script=None, order=e1):
            before = len(fake.requests)
            fake.script = script
            with mock.patch.dict(os.environ):
                for name, value in (env or {}).items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
                status, doc = rig.confirm([order])
            fake.script = None
            checks.ok(
                (code in _codes(doc) if code else bool(_codes(doc))) and not _names(doc.get("made")),
                f"{label}: answered with `{code or 'a tracking_ code'}` and made nothing",
                f"{status} {doc}",
            )
            checks.equal(len(fake.requests) - before, requests, f"{label}: {requests} request(s) reached TCGTracking")
            checks.equal(len(rig.listing()[1]), rows, f"{label}: left {rows} label row(s), none from the refused press")

        attempt("a missing key", "tracking_key_missing", 0, 0, {"TCG_TRACKING_KEY": None})
        attempt("a missing shipper number", "tracking_shipper_missing", 0, 0, {"TCG_TRACKING_SHIPPER_NUMBER": None})
        for status, code in ((401, "tracking_auth_rejected"), (400, "tracking_invalid"), (429, "tracking_rate_limited")):
            attempt(
                f"a {status} from TCGTracking",
                code,
                1,
                0,
                script=lambda n, e, s=status: (s, {"error": f"upstream {s} {SENTINEL}"}),
            )
        status, doc = rig.confirm([e1])
        checks.equal(_names(doc.get("made")), [e1], "after all five refusals a confirm for the same order makes the label")
        opened = []

        def counting(*args, **kwargs):
            opened.append(args)
            raise AssertionError("a network call was made")

        with mock.patch.object(net, "open", counting):
            attempt(
                "the default host under BANCHI_HARNESS",
                None,
                0,
                1,
                {"BANCHI_TCGTRACKING_URL": None, "BANCHI_HARNESS": "1"},
                order=e2,
            )
        checks.equal(len(opened), 0, "and the default-host refusal made no `net.open` call")


# ------------------------------------------------------- a partial run, and a bought 500


@_guarded
def check_labels_partial_and_bought(checks: Checks) -> None:
    """A 429 at the third of five stops the press with a partial receipt; a 500 with an
    `order_id` is stored as bought.

    Creates run one at a time and the press stops at the first error, so the fake sees 3
    creates and 2 labels exist. The 429 order is refused with its code and the two unsent
    orders are untouched. A second confirm for the three that were not made then makes them.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, PARTIAL RUN: 429 at item 3 of 5, and a 500 that carries an order_id (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        five, sixth = rig.envelope[:5], rig.envelope[5]
        fake = rig.fake
        fake.script = lambda n, e: (429, {"error": "slow down"}) if n == 3 else None
        status, doc = rig.confirm(five)
        made = _names(doc.get("made"))
        checks.equal(status, 200, "the press answers 200 with a receipt")
        checks.equal(len(made), 2, "2 orders are made")
        checks.ok(doc.get("partial") is True, "and the receipt is partial")
        sent = [c["order"] for c in fake.creates]
        checks.equal(len(sent), 3, "the fake saw 3 creates: the press stopped at the first error")
        refused = _names(doc.get("refused"))
        checks.ok(sent[-1:] and sent[-1] in refused and "tracking_rate_limited" in _codes(doc), "the 429 order is refused with `tracking_rate_limited`", str(doc))
        unsent = [o for o in five if o not in sent]
        checks.ok(len(unsent) == 2 and not set(unsent) & set(made), "and the two orders after it were not sent and are not made")
        rows = rig.listing()[1]
        checks.equal(len(rows), 2, "the store holds 2 label rows")
        checks.ok(all(_row(rows, o) is None for o in unsent + sent[-1:]), "and none of them is the refused or an unsent order")

        fake.script = None
        rest = [o for o in five if o not in made]
        status, doc = rig.confirm(rest)
        checks.equal(sorted(_names(doc.get("made"))), sorted(rest), "a second confirm for the other three makes them all")
        checks.equal(len(rig.listing()[1]), 5, "and the store then holds 5 rows")

        fake.pdf_for("TT-BOUGHT-500")
        fake.script = lambda n, e: (500, {"order_id": "TT-BOUGHT-500", "error": "internal"})
        before = len(fake.creates)
        status, doc = rig.confirm([sixth])
        checks.ok(_names(doc.get("made")) == [sixth] and not _names(doc.get("refused")), "a 500 with an `order_id` is made, not refused", f"{status} {doc}")
        checks.ok("TT-BOUGHT-500" in _stored(rig.home), "and its answer is stored as a bought label")
        status, doc = rig.confirm([sixth])
        checks.ok(_names(doc.get("existing")) == [sixth] and len(fake.creates) == before + 1, "and a replay buys no second label")


# ----------------------------------------------------------------- a duplicate answer, no PDF


@_guarded
def check_labels_duplicate(checks: Checks) -> None:
    """A create answered 200 `duplicate: true` has no PDF in it, and the order is not refused.

    TCGTracking answers that for a `source_order_id` it has already seen, so the label exists.
    The press fetches the PDF with `GET /orders/<id>/pdf` for the id in that answer, keeps it,
    and ends the order `made` or `existing` and never `refused`. A replay sends no create.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, DUPLICATE: a 200 duplicate answer with no PDF is fetched by id and kept (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        order, fake, label = rig.envelope[0], rig.fake, "TT-DUP-0731"
        pdf = fake.pdf_for(label)
        fake.script = lambda n, e: (200, fake.duplicate(label))
        status, doc = rig.confirm([order])
        checks.ok(
            status == 200 and order in _names(doc.get("made")) + _names(doc.get("existing")) and order not in _names(doc.get("refused")),
            "the order ends `made` or `existing` and never `refused`",
            f"{status} {doc}",
        )
        asked = [(r["method"], r["path"]) for r in fake.requests if r["path"] in ("/orders", f"/orders/{label}/pdf")]
        checks.equal(asked, [("POST", "/orders"), ("GET", f"/orders/{label}/pdf")], "the fake saw 1 create, then 1 GET of that label's pdf")
        checks.ok(_kept(_stored(rig.home), pdf), "the store keeps that label PDF")
        checks.equal(len(rig.listing()[1]), 1, "and GET /shipping/labels lists 1 row for the order")
        status, doc = rig.confirm([order])
        checks.ok(
            status == 200 and _names(doc.get("existing")) == [order] and not _names(doc.get("made")),
            "a replay makes nothing and names the order as existing",
            f"{status} {doc}",
        )
        checks.equal(len(fake.creates), 1, "and sends no second create")


# ------------------------------------------------------------------------- the pdf route


@_guarded
def check_labels_pdf_route(checks: Checks) -> None:
    """`GET /shipping/labels/<pdf_token>/pdf` serves the label PDF the store holds.

    Each listing row carries a `pdf_token`, 32 hex characters and distinct per row. The token
    route answers the stored bytes as application/pdf and sends nothing to TCGTracking. The
    ORDER NUMBER in the token's place answers 404 (a buyer's label is not fetched by a guessable
    name), as does a token no row owns. The right press comes first in the case, as in the money
    gate: a route that does not exist answers 404 to every ask too.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, PDF ROUTE: a row's token fetches the stored label as application/pdf, an order number is 404 (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2, e3 = rig.envelope[:3]
        fake = rig.fake
        rig.confirm([e1, e2])
        label = {c["order"]: fake.pdf_for(f"TT-{n:04d}") for n, c in enumerate(fake.creates, 1)}
        rows = rig.listing()[1]
        token = {order: _token(rows, order) for order in (e1, e2)}
        checks.ok(
            all(isinstance(t, str) and re.fullmatch(r"[0-9a-fA-F]{32}", t) for t in token.values()),
            "every listing row carries a `pdf_token` of 32 hex characters",
            str(token),
        )
        checks.equal(len(set(token.values())), 2, "and the two tokens differ")
        before = len(fake.requests)
        for order in (e1, e2):
            status, body, headers = rig.raw("GET", _pdf_path(token[order]))
            kind = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
            checks.ok(
                status == 200 and kind.split(";")[0].strip() == "application/pdf" and body == label.get(order),
                "a row's token answers 200 with its own stored bytes as application/pdf",
                f"{status} {kind!r} {body[:60]!r}",
            )
        checks.equal(len(fake.requests), before, "and the two reads sent 0 requests to TCGTracking")
        for ref, why in (
            (e1, "the order number of a labelled order"),
            (e3, "an order number with no label row"),
            ("0" * 32, "a well-formed token no row owns"),
        ):
            status, _, _ = rig.raw("GET", _pdf_path(ref))
            checks.equal(status, 404, f"{why} answers 404")
        checks.equal(len(fake.requests), before, "and no 404 sent a request to TCGTracking")


@_guarded
def check_labels_combined_pdf(checks: Checks) -> None:
    """`GET /shipping/batches/<batch>/labels/pdf` is one PDF of every label made for the batch.

    A batch with no label answers 404 or a named refusal. After 3 orders are labelled the answer is
    one application/pdf of 3 pages, and the pages are those 3 labels (the fake's pages differ in
    height, so three copies of one label read wrong). It sends nothing to TCGTracking. The empty ask
    comes first, so the later 200 is what shows the route exists.
    """
    checks.note("")
    checks.note("TCGTRACKING LABELS, COMBINED FILE: one PDF of the batch's labels, 3 pages for 3 labels, no network (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        fake, path = rig.fake, f"{rig.labels_path}/pdf"
        status, body, _ = rig.raw("GET", path)
        checks.ok(
            (status == 404 or (400 <= status < 500 and error_code(body))) and not body.startswith(b"%PDF"),
            "a batch with no label answers 404 or a named refusal, not a file",
            f"{status} {body[:80]!r}",
        )
        rig.confirm(rig.envelope[:3])
        before = len(fake.requests)
        status, body, headers = rig.raw("GET", path)
        kind = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
        checks.ok(
            status == 200 and kind.split(";")[0].strip() == "application/pdf" and body.startswith(b"%PDF"),
            "after 3 orders are labelled the answer is 200 and one application/pdf",
            f"{status} {kind!r} {body[:60]!r}",
        )
        try:
            heights = _pages(body)
        except Exception as caught:  # noqa: BLE001 - an unreadable file is the failure
            heights = []
            checks.ok(False, "the combined file can be read as a PDF", f"{type(caught).__name__}: {caught}")
        checks.equal(len(heights), 3, "and it holds 3 pages")
        want = sorted(h for n in (1, 2, 3) for h in _pages(fake.pdf_for(f"TT-{n:04d}")))
        checks.equal(sorted(heights), want, "which are the 3 labels, one page each")
        checks.equal(len(fake.requests), before, "and the read sent 0 requests to TCGTracking")


# ------------------------------------------------------------------------- T5, scans


@_guarded
def check_labels_scans(checks: Checks) -> None:
    """`POST /shipping/labels/scans` reads the scan status of each labelled order and stores
    it. One lookup per label row, none for an order with no label, and no create. With the
    key missing it sends nothing and names the code."""
    checks.note("")
    checks.note("TCGTRACKING SCANS: one press, one lookup per labelled order, stored (D326, T5)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2 = rig.envelope[:2]
        status, doc = rig.call("POST", "/shipping/labels/scans", {})
        checks.ok(status == 200 and not rig.fake.tracks, "with no label rows the press answers 200 and looks up nothing", f"{status} {doc}")
        rig.confirm([e1, e2])
        checks.ok(SCAN_MARK not in _stored(rig.home), "before the press the store holds no scan status")
        status, doc = rig.call("POST", "/shipping/labels/scans", {})
        checks.equal(status, 200, "the press answers 200")
        tracks = rig.fake.tracks
        checks.ok(len(tracks) == 2 and len({t["query"] for t in tracks}) == 2, "the fake saw 2 lookups, one per labelled order", str([t["query"] for t in tracks]))
        checks.equal(len(rig.fake.creates), 2, "and the press created nothing")
        checks.ok(SCAN_MARK in _stored(rig.home), "the track answer is stored")
        checks.ok(SCAN_MARK in json.dumps(rig.listing()[1]), "and GET /shipping/labels shows it")
        before = len(rig.fake.requests)
        with mock.patch.dict(os.environ):
            os.environ.pop("TCG_TRACKING_KEY")
            status, doc = rig.call("POST", "/shipping/labels/scans", {})
        checks.ok("tracking_key_missing" in _codes(doc), "with the key missing the press names `tracking_key_missing`", f"{status} {doc}")
        checks.equal(len(rig.fake.requests), before, "and sends 0 requests")


@_guarded
def check_labels_scans_not_found(checks: Checks) -> None:
    """A lookup that answers 404 (no match, or no scan yet) does not fail the press.

    The fake answers 404 to the FIRST lookup, whichever order that is for, so a press that
    stops at its first error leaves the other order unstored and goes red. The press answers
    200 and looks up both. The other order's status is stored. The 404 order's row records
    the miss, and `tracking_not_found` is in the answer or on that row.
    """
    checks.note("")
    checks.note("TCGTRACKING SCANS, NOT FOUND: a 404 lookup is recorded on its row and the press goes on (D326, T5)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2 = rig.envelope[:2]
        fake = rig.fake
        rig.confirm([e1, e2])
        before = rig.listing()[1]
        fake.track_script = lambda n, e: (404, {"error": "not found"}) if n == 1 else None
        status, doc = rig.call("POST", "/shipping/labels/scans", {})
        fake.track_script = None
        tracks = fake.tracks
        missed = tracks[0]["order"] if tracks else None
        if not checks.ok(missed in (e1, e2), "the first lookup names one of the two labelled orders", str([t["query"] for t in tracks])):
            return
        found = e2 if missed == e1 else e1
        rows = rig.listing()[1]
        gone, there = _row(rows, missed), _row(rows, found)
        checks.equal(status, 200, "the press answers 200 although one lookup answered 404")
        checks.equal(len(tracks), 2, "and both orders were looked up: the 404 did not stop the press")
        checks.ok(there is not None and SCAN_MARK in json.dumps(there, default=repr), "the other order's scan status is stored on its row")
        checks.ok(
            gone is not None and SCAN_MARK not in json.dumps(gone, default=repr) and gone != _row(before, missed),
            "the 404 order's row records the miss and holds no scan status",
            f"{gone}",
        )
        checks.ok(
            "tracking_not_found" in json.dumps(doc) + json.dumps(gone, default=repr),
            "and `tracking_not_found` is in the answer or on that row",
            f"{status} {doc}",
        )


@_guarded
def check_labels_auth_headers(checks: Checks) -> None:
    """Every request TCGTracking sees carries `X-API-Key` (the key) and `X-Shipper-Number` (the shipper).

    One run makes each kind of call the routes make: a create, a pdf fetch (a duplicate answer has
    no PDF in it) and a track lookup. The kinds are asserted too, so a run that sent fewer cannot pass.
    """
    checks.note("")
    checks.note("TCGTRACKING AUTH: X-API-Key and X-Shipper-Number on every create, pdf fetch and track lookup (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2 = rig.envelope[:2]
        fake = rig.fake
        rig.confirm([e1])
        fake.pdf_for("TT-DUP-0731")
        fake.script = lambda n, e: (200, fake.duplicate("TT-DUP-0731"))
        rig.confirm([e2])
        fake.script = None
        rig.call("POST", "/shipping/labels/scans", {})
        kinds = {(r["method"], "pdf" if r["path"].endswith("/pdf") else r["path"]) for r in fake.requests}
        checks.equal(
            kinds,
            {("POST", "/orders"), ("GET", "pdf"), ("GET", "/orders/track")},
            "the run made a create, a pdf fetch and a track lookup",
        )
        bad = [
            (r["method"], r["path"])
            for r in fake.requests
            if r["headers"].get("x-api-key") != SENTINEL or r["headers"].get("x-shipper-number") != SHIPPER
        ]
        checks.equal(bad, [], f"and each of the {len(fake.requests)} requests carries the key and the shipper number as headers")


# --------------------------------------------------------------------- the secret


@_guarded
def check_labels_key_never_leaks(checks: Checks) -> None:
    """The key value is in no response, refusal text, log line, printed line or store row.

    One run through every path that handles it: a preview, a bought label, a 401 and a 429
    whose bodies echo the key back, the scans press, the listing, the pdf route (a token, and an
    order number that is refused), the combined file, the stop press, and the client module's own
    refusals. The positive control is that the fake did receive the key: without it a build
    that never sent the key would pass.
    """
    checks.note("")
    checks.note("TCGTRACKING KEY: a sentinel key is in no response, refusal, log line or store row (D326)")
    tt = _client(checks)
    with _rig() as rig:
        if not rig.upload(checks):
            return
        e1, e2, e3 = rig.envelope[:3]
        rig.preview()
        rig.confirm([e1])
        for order, status in ((e2, 401), (e3, 429)):
            rig.fake.script = lambda n, e, s=status: (s, {"error": f"upstream {s} {SENTINEL}", "key": SENTINEL})
            rig.confirm([order])
        rig.fake.script = None
        rig.call("POST", "/shipping/labels/scans", {})
        rows = rig.listing()[1]
        rig.call("GET", _pdf_path(_token(rows, e1)))
        rig.call("GET", _pdf_path(e1))
        rig.call("GET", _pdf_path(e2))
        rig.call("GET", f"{rig.labels_path}/pdf")
        rig.call("POST", f"{rig.labels_path}/stop", {})
        if tt is not None:
            rig.fake.script = lambda n, e: (401, {"error": f"upstream 401 {SENTINEL}"})
            try:
                tt.create({"source_order_id": e2})
            except Exception as caught:  # noqa: BLE001 - its text is what is scanned
                rig.texts.append("".join(traceback.format_exception(type(caught), caught, caught.__traceback__)))
            rig.fake.script = None
        checks.ok(rig.key_sent(), "the fake received the key (positive control)")
        checks.equal(_leaked(rig), [], "and it appears in no response, refusal, log line, printed line or store row")


CHECKS = (
    check_labels_preview,
    check_labels_preview_presence,
    check_labels_money_gate,
    check_labels_make_and_replay,
    check_labels_listing_rows,
    check_labels_double_press,
    check_labels_stop,
    check_labels_client,
    check_labels_default_host,
    check_labels_refusals,
    check_labels_partial_and_bought,
    check_labels_duplicate,
    check_labels_pdf_route,
    check_labels_combined_pdf,
    check_labels_scans,
    check_labels_scans_not_found,
    check_labels_auth_headers,
    check_labels_key_never_leaks,
)
