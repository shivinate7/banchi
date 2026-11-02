"""T7 group: four guards on the TCGTracking label pipe that `labels.py` does not pin.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). It reuses the rig, the fake and the
network seal of `labels.py`. Each check fails on the code without its fix:

    labels_private_read   the label GETs give a page from another origin no leave to read them
    labels_bought_kept    a bought label whose PDF fetch fails stays stored, and is never bought again
    labels_host_guard     the real TCGTracking host is refused by host, not by the whole string
    labels_press_safety   one create at a time across presses; a store lock timeout ends in a receipt
"""

from __future__ import annotations

import os
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


CHECKS = (
    check_labels_private_read,
    check_labels_bought_kept,
    check_labels_host_guard,
    check_labels_press_safety,
)
