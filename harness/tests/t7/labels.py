"""T7 group: the TCGTracking label pipe (T4 labels under the money gate, T5 tracking back).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

THE FAKE IS THE CONTRACT. `_Tracking` stands in for TCGTracking on 127.0.0.1, counts every
request and fails any path it does not know. The builder meets the answer shapes below, so a
shape that differs from the real API is changed here, once:

    POST /orders              200 {"order_id": "TT-0001", "tracking_number": "9400********0001",
                                   "status": "created", "carrier_note": "T7-WHOLE-ANSWER-1",
                                   "pdf": <base64 of the label>}
    GET  /orders/<id>/pdf     the same label bytes, application/pdf
    GET  /orders/track        200 {"order_number": <asked>, "status": "T7-SCAN-MARK accepted", ...}

THE ROUTES ARE DRIVEN OVER A REAL SOCKET, not through a `do_*` function, because the contract
names paths and not the module that serves them. `server/tcgtracking.py` is imported inside each
check: today it is absent, and one import error at module scope would take every sibling T7
check down with it.

WHAT THE CASES DO NOT PIN, so the builder is free there: the status and code of a refused
confirm, whether a key or shipper refusal is a whole-request error or a `refused` entry (the
code is looked for anywhere in the answer), the top-level shape of the label listing (the
longest list in it is the rows), and the insurance field's name (any key holding "insur").
"""

from __future__ import annotations

import base64
import contextlib
import csv
import functools
import http.server
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
FEE_WORDS = "fee per your TCGTracking account"
RECEIPT_KEYS = {"made", "existing", "refused", "partial"}


# ------------------------------------------------------------------------------ the fake


class _Tracking:
    """TCGTracking on loopback. `script(n, request)` may answer the nth create `(status, body)`;
    returning None gives the default bought answer. `hold` parks the first create until
    `release` is set, so a second press can arrive while the first is in flight."""

    def __init__(self, orders):
        self.orders = tuple(orders)
        self.lock = threading.Lock()
        self.requests = []
        self.unknown = []
        self.pdfs = {}
        self.script = None
        self.hold = False
        self.arrived = threading.Event()
        self.release = threading.Event()

    @property
    def creates(self):
        return [r for r in list(self.requests) if r["method"] == "POST" and r["path"] == "/orders"]

    @property
    def tracks(self):
        return [r for r in list(self.requests) if r["method"] == "GET" and r["path"] == "/orders/track"]

    def pdf_for(self, order_id):
        return self.pdfs.setdefault(order_id, b"%PDF-1.4\n% T7-LABEL-PDF-" + order_id.encode() + b"\n%%EOF\n")

    def bought(self, n):
        order_id = f"TT-{n:04d}"
        return {
            "order_id": order_id,
            "tracking_number": f"9400********{n:04d}",
            "status": "created",
            "carrier_note": f"T7-WHOLE-ANSWER-{n}",
            "pdf": base64.b64encode(self.pdf_for(order_id)).decode(),
        }

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
                entry = {
                    "method": self.command,
                    "path": parts.path,
                    "query": parts.query,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": raw,
                    "order": next((o for o in fake.orders if o in text), None),
                }
                with fake.lock:
                    fake.requests.append(entry)
                    n = len(fake.creates)
                if entry["method"] == "POST" and parts.path == "/orders":
                    if fake.hold and n == 1:
                        fake.arrived.set()
                        fake.release.wait(10)
                    scripted = fake.script(n, entry) if fake.script else None
                    return self._reply(*(scripted or (200, fake.bought(n))))
                if entry["method"] == "GET" and parts.path == "/orders/track":
                    asked = (urllib.parse.parse_qs(parts.query).get("order_number") or [""])[0]
                    return self._reply(
                        200, {"order_number": asked, "status": f"{SCAN_MARK} accepted", "events": [{"scan": "accepted"}]}
                    )
                match = re.fullmatch(r"/orders/([^/]+)/pdf", parts.path)
                if entry["method"] == "GET" and match and match.group(1) in fake.pdfs:
                    return self._reply(200, fake.pdfs[match.group(1)], "application/pdf")
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

    def call(self, method, path, payload=None):
        status, body, headers = request(self.port, method, path, payload=payload)
        self.wire.append(body.decode("utf-8", "replace") + repr(headers))
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
        checks.equal(len(rig.fake.requests), 0, "the preview made no request to TCGTracking")
        checks.ok(
            (store_tables(), home_files(rig.home)) == before,
            "and wrote no store row and no file: no claim, no label row",
        )


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
        rig.fake.hold = True
        answers = {}

        def press(tag):
            answers[tag] = rig.confirm([order])

        first = threading.Thread(target=press, args=("a",), daemon=True)
        first.start()
        deadline = time.monotonic() + 5
        while not rig.fake.arrived.is_set() and first.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        checks.ok(rig.fake.arrived.is_set(), "the first press's create reached the fake and is held in flight")
        second = threading.Thread(target=press, args=("b",), daemon=True)
        second.start()
        time.sleep(0.6)
        rig.fake.release.set()
        first.join(timeout=15)
        second.join(timeout=15)
        checks.ok(not first.is_alive() and not second.is_alive(), "both presses answered")
        made = [n for tag in answers for n in _names(answers[tag][1].get("made"))]
        checks.equal(len(rig.fake.creates), 1, "the fake saw exactly 1 create")
        checks.equal(made, [order], "and exactly one press reports the order as made")
        checks.ok(all(s < 500 for s, _ in answers.values()), "and neither press answered with a server error", str(answers))
        checks.equal(len(rig.listing()[1]), 1, "and the store holds 1 label row")


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
    from pipeline import net

    checks.note("")
    checks.note("TCGTRACKING HOST GUARD: the default host under BANCHI_HARNESS or CI, and non-loopback http (D326)")
    tt = _client(checks)
    if tt is None:
        return
    opened = []

    def forbidden(*args, **kwargs):
        opened.append(args)
        raise AssertionError("a network call was made")

    base = {"TCG_TRACKING_KEY": SENTINEL, "TCG_TRACKING_SHIPPER_NUMBER": SHIPPER}
    cases = (
        ({"BANCHI_HARNESS": "1"}, None, "the default host under BANCHI_HARNESS"),
        ({"CI": "1"}, None, "the default host under CI"),
        ({}, "http://tcgtracking.invalid", "a non-loopback http host, outside the harness and CI"),
    )
    for env, url, label in cases:
        with mock.patch.dict(os.environ, {**base, **env}), \
                mock.patch.object(net, "open", forbidden), \
                mock.patch.object(urllib.request, "urlopen", forbidden), \
                mock.patch.object(socket, "create_connection", forbidden):
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


# --------------------------------------------------------------------- the secret


@_guarded
def check_labels_key_never_leaks(checks: Checks) -> None:
    """The key value is in no response, refusal text, log line, printed line or store row.

    One run through every path that handles it: a preview, a bought label, a 401 and a 429
    whose bodies echo the key back, the scans press, the listing, and the client module's own
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
        rig.listing()
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
    check_labels_money_gate,
    check_labels_make_and_replay,
    check_labels_double_press,
    check_labels_client,
    check_labels_default_host,
    check_labels_refusals,
    check_labels_partial_and_bought,
    check_labels_scans,
    check_labels_key_never_leaks,
)
