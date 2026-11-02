"""T7 group: guards on the TCGTracking label pipe that `labels.py` does not pin.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). It reuses the rig, the fake and the
network seal of `labels.py`. Each check fails on the code without its fix:

    labels_private_read       the label GETs give a page from another origin no leave to read them
    labels_bought_kept        a bought label whose PDF fetch fails stays stored, and is never bought again
    labels_host_guard         the real TCGTracking host is refused by host, not by the whole string
    labels_press_safety       one create at a time across presses; a store lock timeout ends in a receipt
    labels_unbought_answer    a 2xx answer with no `order_id` is no label: refused, no row, bought on the next press
    labels_answer_write_once  a paid create whose answer write times out once is never created a second time
    labels_stop_waiting_press a stop reaches a press that waits for the create lock: it sends nothing, leaves no claim
    labels_claims_pending     a dead press's claim is eligible and bought once; a live press's is `label_pending`
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import threading
import time
from unittest import mock

from harness.tests import Checks
from harness.tests.t7.common import request
from harness.tests.t7.labels import (
    SENTINEL,
    SHIPPER,
    _client,
    _codes,
    _guarded,
    _kept,
    _names,
    _pdf_path,
    _rig,
    _row,
    _sealed,
    _stored,
    _token,
)
from store import files
from store.session import Store

APP = "http://app.t7.test"
EVIL = "http://evil.example"
# Spellings that reach the real host without being its default address string.
REAL_HOST_SPELLINGS = (
    "https://tcgtracking.com/api/v1?x=1",
    "https://TCGTracking.com/api/v1",
    "https://tcgtracking.com:443/api/v1",
    "https://tcgtracking.com./api/v1",
    "https://user@tcgtracking.com/api/v1",
    "https://www.tcgtracking.com/api/v1",
)


def _acao(rig, path, origin=None):
    """`(status, Access-Control-Allow-Origin or None)` for a GET."""
    status, _, headers = request(rig.port, "GET", path, origin=origin)
    return status, {k.lower(): v for k, v in headers.items()}.get("access-control-allow-origin")


@_guarded
def check_labels_private_read(checks: Checks) -> None:
    """The listing, the token PDF and the combined file hand a buyer's address to the app and to no
    other page: a page from another origin gets no leave to read them, an allowed origin does, and an
    ordinary read (a photograph) stays open."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, PRIVATE READS: no leave to read the label GETs from another origin (D326)")
    with _rig() as rig, mock.patch.dict(os.environ, {"BANCHI_ALLOWED_ORIGINS": APP}):
        if not rig.upload(checks):
            return
        order = rig.envelope[0]
        rig.confirm([order])
        token = _token(rig.listing()[1], order)
        if not checks.ok(bool(token), "the listing row of a made label carries a `pdf_token`"):
            return
        paths = {
            "the listing": "/shipping/labels",
            "the token PDF": _pdf_path(token),
            "the combined file": f"{rig.labels_path}/pdf",
        }
        for name, path in paths.items():
            status, allow = _acao(rig, path, EVIL)
            checks.ok(
                status == 200 and allow not in ("*", EVIL),
                f"{name} gives a page from another origin no leave to read it",
                f"{status} {allow}",
            )
            checks.equal(_acao(rig, path)[0], 200, f"{name} still answers a client that sends no Origin")
            status, allow = _acao(rig, path, APP)
            checks.ok(status == 200 and allow == APP, f"{name} lets an allowed origin read it", f"{status} {allow}")
        checks.equal(_acao(rig, "/status", EVIL)[1], "*", "an ordinary read still answers `*` (positive control)")


@_guarded
def check_labels_bought_kept(checks: Checks) -> None:
    """A create answers (a duplicate, no PDF) and the PDF fetch then fails: the label stays stored,
    no second create is sent, and a later read fetches the PDF."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, BOUGHT LABEL KEPT: the answer is stored before the PDF is fetched (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        order, fake, label = rig.envelope[0], rig.fake, "TT-LOST-0911"
        # The fake holds no PDF for this id yet, so the fetch after the answer is a 404.
        fake.script = lambda n, e: (200, fake.duplicate(label))
        status, doc = rig.confirm([order])
        checks.ok(status == 200 and order in _names(doc.get("made")), "the order is made though its PDF is not fetched", f"{status} {doc}")
        checks.ok(doc.get("partial") is True and _codes(doc), "and the receipt is partial and names the fetch failure", str(doc))
        checks.ok(label in _stored(rig.home), "and the bought label's answer is stored")
        token = _token(rig.listing()[1], order)
        status, doc = rig.confirm([order])
        checks.ok(order not in _names(doc.get("made")) and len(fake.creates) == 1, "a second confirm sends no second create", f"{status} {doc}")
        pdf = fake.pdf_for(label)
        status, body, _ = rig.raw("GET", _pdf_path(token))
        checks.ok(status == 200 and body == pdf, "once TCGTracking has the PDF, the label's token route serves it", f"{status}")
        checks.ok(_kept(_stored(rig.home), pdf) and len(fake.creates) == 1, "and it is stored, with still 1 create")


@_guarded
def check_labels_host_guard(checks: Checks) -> None:
    """The real host is refused under `BANCHI_HARNESS` and `CI` however the address is spelled."""
    checks.note("")
    checks.note("TCGTRACKING HOST GUARD, SPELLINGS: the host decides, not the whole string (D326)")
    tt = _client(checks)
    if tt is None:
        return
    opened = []
    base = {"TCG_TRACKING_KEY": SENTINEL, "TCG_TRACKING_SHIPPER_NUMBER": SHIPPER}
    for gate in ("BANCHI_HARNESS", "CI"):
        for url in REAL_HOST_SPELLINGS:
            with mock.patch.dict(os.environ, {**base, "BANCHI_TCGTRACKING_URL": url, gate: "1"}), _sealed(opened):
                for other in {"BANCHI_HARNESS", "CI"} - {gate}:
                    os.environ.pop(other, None)
                try:
                    tt.create({"source_order_id": "T7-X"})
                    got = "did not raise"
                except tt.TrackingRefused as caught:
                    got = caught.code
                except Exception as caught:  # noqa: BLE001 - the type is the assertion
                    got = f"{type(caught).__name__}: {caught}"
            checks.equal(got, "tracking_host_refused", f"{url} under {gate} is refused")
    checks.equal(len(opened), 0, "and no network call was attempted")


@_guarded
def check_labels_press_safety(checks: Checks) -> None:
    """Two presses on different orders create one at a time, and a store lock timeout in the middle of
    a press ends in a receipt that still names the labels made before it."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, PRESS SAFETY: one create at a time, a lock timeout is a receipt (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        first, second, third, fourth = rig.envelope[:4]
        fake = rig.fake
        press, got = rig.press_held([first])
        checks.ok(fake.arrived.is_set(), "the first press's create is held in flight")
        other = threading.Thread(target=lambda: got.append(rig.confirm([second])), daemon=True)
        other.start()
        deadline = time.monotonic() + 1
        while len(fake.creates) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        checks.equal(len(fake.creates), 1, "a second press on another order sends no create while the first is in flight")
        fake.release.set()
        press.join(timeout=15)
        other.join(timeout=15)
        made = sorted(n for _, doc in got for n in _names(doc.get("made")))
        checks.equal(made, sorted([first, second]), "and both labels are made once the first create is done")

        # The store lock times out for every write after `third` is made: the middle of one press of two orders.
        real_write = Store.write

        def busy_after_third(self, *args, **kwargs):
            row = self.read().ledger.labels.get(third)
            if row is not None and row.made:
                raise files.LockTimeout("busy")
            return real_write(self, *args, **kwargs)

        with mock.patch.object(Store, "write", busy_after_third):
            status, doc = rig.confirm([third, fourth])
        checks.ok(
            status == 200 and third in _names(doc.get("made")),
            "a lock timeout mid-press still answers a receipt that names the label made before it",
            f"{status} {doc}",
        )
        checks.ok(
            fourth in _names(doc.get("refused")) and "store_busy" in str(doc),
            "and refuses the order it hit with `store_busy`",
            str(doc),
        )
        checks.equal(len(fake.creates), 3, "and buys nothing for that order")
        status, doc = rig.confirm([fourth])
        checks.equal(_names(doc.get("made")), [fourth], "the refused order is made by the next confirm")


@_guarded
def check_labels_unbought_answer(checks: Checks) -> None:
    """A create answered 200 or 201 with no `order_id` bought nothing: the order is refused with a
    `tracking_` code, no label row is left, and the next confirm sends a fresh create and makes it.

    Two shapes, one order each: `success: false` (a 200 the API means as a failure) and a 201 that says
    `success: true` yet names no order, so a fix that reads only `success` is caught."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, UNBOUGHT ANSWER: a 2xx with no `order_id` is not a label (D326)")
    shapes = (
        (200, {"success": False}),
        (201, {"success": True, "ordernum": "T7-ORD-9999", "tracking_number": "9400********9999"}),
    )
    with _rig() as rig:
        if not rig.upload(checks):
            return
        fake = rig.fake
        for order, (code, body) in zip(rig.envelope, shapes):
            name = f"a {code} answer {sorted(body)}"
            fake.script = lambda n, e, order=order, code=code, body=body: (code, body) if e["order"] == order else None
            status, doc = rig.confirm([order])
            refused = next((r.get("code") for r in doc.get("refused") or [] if isinstance(r, dict) and r.get("order") == order), None)
            checks.ok(
                order not in _names(doc.get("made")) and str(refused).startswith("tracking_"),
                f"{name} is refused with a `tracking_` code and the order is not made",
                f"{status} {doc}",
            )
            checks.ok(_row(rig.listing()[1], order) is None, f"and {name} leaves no label row")
            fake.script = None
            sent = len(fake.creates)
            status, doc = rig.confirm([order])
            row = _row(rig.listing()[1], order) or {}
            checks.ok(
                _names(doc.get("made")) == [order] and len(fake.creates) == sent + 1 and row.get("status") == "made",
                "and the next confirm sends a fresh create and makes the label",
                f"{status} {doc} creates {sent} -> {len(fake.creates)}",
            )


@_guarded
def check_labels_answer_write_once(checks: Checks) -> None:
    """A create is paid, and the store write that records its answer times out once. That press and a
    following confirm together send exactly 1 create for the order, and the order ends made with its
    label stored. The fake answers a second create as a new label, so a double buy shows as 2 creates."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, ANSWER WRITE: a paid create whose answer is not stored is never bought again (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        order, fake = rig.envelope[0], rig.fake
        real_write, timed_out = Store.write, []

        def busy_once(self, *args, **kwargs):
            # The claim is written before the create. The first write after the fake holds a create for this order records its answer.
            if not timed_out and any(c["order"] == order for c in fake.creates):
                timed_out.append(True)
                raise files.LockTimeout("busy")
            return real_write(self, *args, **kwargs)

        with mock.patch.object(Store, "write", busy_once):
            rig.confirm([order])
        checks.ok(bool(timed_out), "the write after the create timed out once")
        rig.confirm([order])
        checks.equal(sum(1 for c in fake.creates if c["order"] == order), 1, "the fake saw exactly 1 create for the order across both presses")
        row = _row(rig.listing()[1], order) or {}
        checks.ok(row.get("status") == "made" and row.get("tracking_number"), "and the order ends made", str(row))
        checks.ok(_kept(_stored(rig.home), fake.pdf_for("TT-0001")), "with the paid label stored")


@_guarded
def check_labels_stop_waiting_press(checks: Checks) -> None:
    """Press 1 holds a create in flight and press 2 has claimed another order and waits behind it. A
    stop arrives and press 1 is released: press 2 sends no create for its order, reports it left over,
    and keeps no claim row, so a later confirm makes the order."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, STOP A WAITING PRESS: a press behind the create in flight sends nothing after a stop (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        first, second = rig.envelope[:2]
        fake = rig.fake
        press, one = rig.press_held([first])
        checks.ok(fake.arrived.is_set(), "press 1's create is held in flight")
        two = []
        waiter = threading.Thread(target=lambda: two.append(rig.confirm([second])), daemon=True)
        waiter.start()
        deadline = time.monotonic() + 5
        while (_row(rig.listing()[1], second) or {}).get("status") != "pending" and time.monotonic() < deadline:
            time.sleep(0.02)
        checks.equal((_row(rig.listing()[1], second) or {}).get("status"), "pending", "press 2 has claimed its order and waits behind press 1")
        status, doc = rig.call("POST", f"{rig.labels_path}/stop", {})
        checks.ok(status == 200 and doc.get("stopping") == 2, "the stop reaches both presses", f"{status} {doc}")
        fake.release.set()
        press.join(timeout=15)
        waiter.join(timeout=15)
        status, doc = two[0] if two else (0, {})
        checks.ok(not [c for c in fake.creates if c["order"] == second], "press 2 sent no create for its order", f"creates {len(fake.creates)}")
        checks.ok(
            second in _names((doc.get("stopped") or {}).get("left_over")) and second not in _names(doc.get("made")),
            "and its receipt reports the order left over",
            f"{status} {doc}",
        )
        checks.ok(_names(one[0][1].get("made")) == [first] if one else False, "while press 1's label in flight is made and kept")
        checks.ok(_row(rig.listing()[1], second) is None, "and no claim row is left for the order")
        status, doc = rig.confirm([second])
        checks.ok(
            _names(doc.get("made")) == [second] and sum(1 for c in fake.creates if c["order"] == second) == 1,
            "a later confirm makes it with 1 create",
            f"{status} {doc}",
        )


def _dead_pid() -> int:
    """The process id of a process that has ended."""
    child = subprocess.Popen([sys.executable, "-I", "-c", "pass"])
    child.wait()
    return child.pid


@_guarded
def check_labels_claims_pending(checks: Checks) -> None:
    """A claim row left by a dead press (another process id) previews eligible and a confirm buys it
    with 1 create. A claim of a press in flight in this process previews `label_pending`, not eligible."""
    checks.note("")
    checks.note("TCGTRACKING LABELS, CLAIMS: a dead press's claim is eligible, a live press's is pending (D326)")
    with _rig() as rig:
        if not rig.upload(checks):
            return
        dead, live = rig.envelope[:2]
        fake = rig.fake
        with Store().write() as snap:
            snap.ledger.claim_label(dead, f"{_dead_pid()}:{secrets.token_hex(4)}", ())

        def preview():
            return {r.get("order"): r for r in rig.preview()[1].get("orders") or [] if isinstance(r, dict)}

        row = preview().get(dead, {})
        checks.ok(row.get("eligible") is True and row.get("reason") == "envelope", "a claim left by a dead press previews eligible", str(row))
        press, _ = rig.press_held([live])
        checks.ok(fake.arrived.is_set(), "a press's create is held in flight")
        seen = preview()
        checks.ok(
            seen.get(live, {}).get("eligible") is False and seen.get(live, {}).get("reason") == "label_pending",
            "the claim of a press in flight previews `label_pending`, not eligible",
            str(seen.get(live)),
        )
        checks.ok(seen.get(dead, {}).get("eligible") is True, "while the dead press's claim still previews eligible", str(seen.get(dead)))
        fake.release.set()
        press.join(timeout=15)
        status, doc = rig.confirm([dead])
        checks.ok(
            _names(doc.get("made")) == [dead] and sum(1 for c in fake.creates if c["order"] == dead) == 1,
            "a confirm buys the dead press's order with 1 create",
            f"{status} {doc}",
        )


CHECKS = (
    check_labels_private_read,
    check_labels_bought_kept,
    check_labels_host_guard,
    check_labels_press_safety,
    check_labels_unbought_answer,
    check_labels_answer_write_once,
    check_labels_stop_waiting_press,
    check_labels_claims_pending,
)
