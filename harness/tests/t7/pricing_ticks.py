"""T7 group: the owner's kept ticks on `#/pricing`, saved on the server by `POST /pricing/ticks`.

Protects: a tick pressed on a suggestion is kept beside the price file, so a reload reads it back;
an untick is kept too, so a reload does not re-tick it; a kept tick holds only while its suggestion
stays within the send's own drift (`sendguard.drift_allowed`), and a Live row holds none; a bad press
refuses by name and writes nothing; a send that goes out forgets the ticks of the SKUs it priced,
while a refused send and a download keep them.
Governs: D107 (a suggestion the owner ticks is sent on his word, reopened for suggestions),
D168 (a typed price clears by press, which a tick is not).

EVERY CASE GOES THROUGH THE REAL SURFACE. A press is a `POST /pricing/ticks` on a running capture
server, a read is a `GET /pipeline/pricing`, and a send is `send_routes.do_send`. None of the new
Python names is called here, so a checkout that lacks them fails on the wire's answer and never on a
missing name: on a checkout without the feature the press answers 404, and each case then names the
outcome it expected.

THE ON-DISK FILE is `inventory/pricing-ticks.json`, named here as the owner's store names it. A case
reads it only to say what a send or a drop left behind, never to build a state.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

if __name__ == "__main__":
    # Run by path from a checkout: the repo root goes first, so `harness` and `server` import from it.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.tests import Checks
from harness.tests.home import isolated_home, run_folder
from harness.tests.t7.common import (  # noqa: E402
    ARTICUNO_SKU,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    QuietHandler,
    _spawn_server,
    request,
    seam_run,
)
from harness.tests.t7.one_list_wire import (  # noqa: E402
    WORKLIST_CARDS,
    _day,
    _market_reading,
    _noon,
    _one_copy_live,
    _outcome,
    _seed_send_suggestions,
    _set_listing,
    _write_live,
)
from harness.tests.t7.send_markdown import _case, _live_export_priced, _seed_sync, send_portal  # noqa: E402
from server import capture_server, pipeline_routes, send_routes  # noqa: E402
from store import files  # noqa: E402

NAME = "T7 pricing ticks"

TICKS_FILE = "pricing-ticks.json"
PRICING_PATH = "/pipeline/pricing"
TICKS_PATH = "/pricing/ticks"


@contextmanager
def _served():
    """The real capture server on a free port, for one check. A press goes through its POST dispatch."""
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    thread = _spawn_server(httpd)
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        thread.join()


def _json(raw: bytes):
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def _post(port, payload) -> tuple:
    """`POST /pricing/ticks` with `payload` as sent. Returns `(status, answer)`."""
    status, raw, _ = request(port, "POST", TICKS_PATH, payload=payload)
    return status, _json(raw)


def _press(port, ticks=None, drop=None) -> tuple:
    return _post(port, {"ticks": ticks or {}, "drop": drop or []})


def _refusal(answer) -> str:
    """The code a refusal names: the wire answers `{"error": {"code", "message"}}`."""
    if not isinstance(answer, dict):
        return "<no answer>"
    error = answer.get("error")
    if isinstance(error, dict):
        return str(error.get("code", "<no code>"))
    return "<no code>"


def _wire_rows(port) -> dict:
    """`GET /pipeline/pricing`'s live rows, keyed by SKU: the screen's own read, after a reload."""
    status, raw, _ = request(port, "GET", PRICING_PATH)
    if status != 200:
        return {"<status>": {"answered": status}}
    return {row["sku"]: row for row in _json(raw).get("live") or []}


def _wire_row(port, sku) -> dict:
    return _wire_rows(port).get(sku) or {}


def _wire_price(port, sku):
    return _wire_row(port, sku).get("price", "<no price>")


def _ticked(port, sku):
    """The row's `ticked`: True or False where a kept tick holds, None where none does. Absent from the
    wire it reads `<absent>`, and a row that is not on the wire at all reads `<no row>`."""
    row = _wire_row(port, sku)
    if not row:
        return "<no row>"
    return row.get("ticked", "<absent>")


def _ticks_file() -> Path:
    return files.inventory_dir() / TICKS_FILE


def _kept_on_disk():
    """The SKU -> `{price, on}` the file holds, `{}` when there is no file, and None when it does not parse."""
    target = _ticks_file()
    if not target.is_file():
        return {}
    try:
        return json.loads(target.read_text("utf-8")).get("ticks", {})
    except (ValueError, AttributeError):
        return None


def _only_live_export(quantities: dict, prices: dict) -> None:
    """Replaces every fetched live export with one priced export. The worklist reads the newest file by
    name, and a send's own fetch of the portal's live list is newer than any stamp a case would pick."""
    folder = files.inventory_dir() / pipeline_routes.LIVE_DIR
    for old in folder.glob(f"{pipeline_routes.LIVE_PREFIX}*.csv"):
        old.unlink()
    _write_live("20260201-000000", _live_export_priced(quantities, prices))


def _world(checks: Checks, *, with_run: bool) -> None:
    """The live listings the tick cases read.

    Dunsparce suggests 2.20: unsold 60 days, asking 2.50, a market of 2.20, so the suggestion is inside
    the cap and reads group `suggested`. Dunsparce's reverse is asking 3.00 against a market of 2.06, a
    move past the cap, so its suggestion reads group `needs_you`. Articuno is live at market, so its row
    is a Live row, and a Live row holds no tick. `with_run` also writes a run on disk, which moves the
    worklist onto its other branch.
    """
    if with_run:
        _seed_sync()
        seam_run(checks, WORKLIST_CARDS)
    _write_live(
        "20260201-000000",
        _live_export_priced(
            {DUNSPARCE_SKU: 1, DUNSPARCE_REVERSE_SKU: 1, ARTICUNO_SKU: 1},
            {DUNSPARCE_SKU: "2.50", DUNSPARCE_REVERSE_SKU: "3.00", ARTICUNO_SKU: "25.00"},
        ),
    )
    _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
    _market_reading(DUNSPARCE_SKU, "2.20", "2.40")
    _set_listing(DUNSPARCE_REVERSE_SKU, first_seen_live=_noon(_day(60)))
    _market_reading(DUNSPARCE_REVERSE_SKU, "2.06", "2.40")
    _set_listing(ARTICUNO_SKU, first_seen_live=_noon(_day(5)))
    _market_reading(ARTICUNO_SKU, "25.00", "25.50")


def check_ticks_are_kept_and_read_back(checks: Checks) -> None:
    """A press is kept beside the price file and read back on a reload. A tick is `on` true, an untick is
    `on` false, and the untick is kept too, so a reload does not re-tick the row."""
    checks.note("")
    checks.note("TICKS, KEPT — a press is written beside the price file, and a reload reads it back")
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "ticks: round trip"):
            checks.equal(_wire_price(port, DUNSPARCE_SKU), "2.20",
                         "control: the suggestion the press is made against is 2.20")
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": True}})
            checks.equal(status, 200, "POST /pricing/ticks keeps a tick: it answers 200")
            checks.equal(_kept_on_disk(), {DUNSPARCE_SKU: {"price": "2.20", "on": True}},
                         "the kept tick is written to inventory/pricing-ticks.json as its price and on")
            checks.equal(_ticked(port, DUNSPARCE_SKU), True,
                         "a reload reads the kept tick back: the Suggested row is ticked")
        with _case(checks, "ticks: untick kept"):
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": False}})
            checks.equal(status, 200, "POST /pricing/ticks keeps an untick: it answers 200")
            checks.equal(_kept_on_disk(), {DUNSPARCE_SKU: {"price": "2.20", "on": False}},
                         "the untick is kept as on false, not dropped as no tick")
            checks.equal(_ticked(port, DUNSPARCE_SKU), False,
                         "a reload reads the untick back: the row reads unticked, and it holds")


def check_ticks_drop_removes_and_empty_file_goes(checks: Checks) -> None:
    """A drop forgets the SKU's kept tick and leaves the others, and the file goes once no tick is left."""
    checks.note("")
    checks.note("TICKS, DROPPED — a drop forgets one SKU, and the file goes when none is left")
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "ticks: drop"):
            status, _ = _press(port, {
                DUNSPARCE_SKU: {"price": "2.20", "on": True},
                DUNSPARCE_REVERSE_SKU: {"price": "2.06", "on": True},
            })
            checks.equal(status, 200, "precondition: two ticks are kept, so the press answers 200")
            checks.ok(_ticks_file().is_file(), "precondition: the kept ticks are a file on disk before any drop")
            status, _ = _press(port, drop=[DUNSPARCE_REVERSE_SKU])
            checks.equal(status, 200, "a drop answers 200")
            checks.equal(_kept_on_disk(), {DUNSPARCE_SKU: {"price": "2.20", "on": True}},
                         "the drop forgets its SKU and keeps the other tick on disk")
            checks.equal(_ticked(port, DUNSPARCE_REVERSE_SKU), None,
                         "the dropped SKU reads None on a reload: no kept tick holds")
        with _case(checks, "ticks: file goes when empty"):
            status, _ = _press(port, drop=[DUNSPARCE_SKU])
            checks.equal(status, 200, "a drop of the last tick answers 200")
            checks.ok(not _ticks_file().exists(),
                      "the tick file is deleted once no tick is left, rather than kept as an empty file")


def check_ticks_corrupt_file_reads_as_none(checks: Checks) -> None:
    """A tick file that does not parse reads as no ticks, and a press over it is kept and read back."""
    checks.note("")
    checks.note("TICKS, CORRUPT FILE — a file that will not parse is no ticks, and the next press is kept")
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "ticks: corrupt file"):
            _ticks_file().parent.mkdir(parents=True, exist_ok=True)
            _ticks_file().write_text("{not json", "utf-8")
            checks.equal(_ticked(port, DUNSPARCE_SKU), None,
                         "a tick file that will not parse reads as no ticks: the Suggested row reads None")
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": True}})
            checks.equal(status, 200, "a press over a corrupt file is kept: it answers 200")
            checks.equal(_ticked(port, DUNSPARCE_SKU), True,
                         "and the press reads back ticked, the corrupt file replaced by a good one")


def check_ticks_refuse_a_bad_press(checks: Checks) -> None:
    """A press with a SKU that is not numeric, a price of zero or junk, an `on` that is not a boolean, or a
    drop list that is not SKUs refuses `ticks_invalid`, and writes no tick file."""
    checks.note("")
    checks.note("TICKS, REFUSED — a bad press is refused by name, and nothing is written")
    bad = (
        ("a SKU that is not numeric", {"ticks": {"ABC": {"price": "2.20", "on": True}}, "drop": []}),
        ("a price of zero", {"ticks": {DUNSPARCE_SKU: {"price": "0", "on": True}}, "drop": []}),
        ("a price that is junk", {"ticks": {DUNSPARCE_SKU: {"price": "junk", "on": True}}, "drop": []}),
        ("an empty price", {"ticks": {DUNSPARCE_SKU: {"price": "", "on": True}}, "drop": []}),
        ("an on that is a word", {"ticks": {DUNSPARCE_SKU: {"price": "2.20", "on": "yes"}}, "drop": []}),
        ("an on that is a number", {"ticks": {DUNSPARCE_SKU: {"price": "2.20", "on": 1}}, "drop": []}),
        ("a drop that names a SKU that is not numeric", {"ticks": {}, "drop": ["ABC"]}),
        ("ticks that are a list, not a map", {"ticks": [], "drop": []}),
    )
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "ticks: refusals"):
            checks.equal(_wire_price(port, DUNSPARCE_SKU), "2.20",
                         "control: the suggestion the press names is 2.20")
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": True}})
            checks.equal(status, 200, "precondition: a good tick is kept first, so there is a kept tick to protect")
            for label, payload in bad:
                status, answer = _post(port, payload)
                checks.equal((status, _refusal(answer)), (400, "ticks_invalid"),
                             f"a press with {label} is refused 400 ticks_invalid")
            checks.equal(_kept_on_disk(), {DUNSPARCE_SKU: {"price": "2.20", "on": True}},
                         "and a refused press leaves the kept tick on disk exactly as it was")


def check_ticks_empty_press_and_drop_cap(checks: Checks) -> None:
    """The empty press is answered 200 and keeps nothing. A drop of exactly the cap is answered 200, and one
    SKU past the cap is refused `ticks_invalid`."""
    checks.note("")
    checks.note("TICKS, EMPTY AND FULL — the empty press keeps nothing, and the drop cap is exact")
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "ticks: empty press"):
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": True}})
            checks.equal(status, 200, "precondition: a tick is kept first, so there is one to leave alone")
            status, _ = _post(port, {})
            checks.equal(status, 200, "an empty press, with no ticks and no drop, answers 200")
            checks.equal(_kept_on_disk(), {DUNSPARCE_SKU: {"price": "2.20", "on": True}},
                         "and leaves the kept tick on disk as it was")
        with _case(checks, "ticks: drop cap"):
            at_cap = [str(number) for number in range(1, pipeline_routes.MAX_CLEAR_SKUS + 1)]
            status, _ = _post(port, {"ticks": {}, "drop": at_cap})
            checks.equal(status, 200, f"a drop of exactly {pipeline_routes.MAX_CLEAR_SKUS} SKUs answers 200")
            status, answer = _post(port, {"ticks": {}, "drop": at_cap + [str(pipeline_routes.MAX_CLEAR_SKUS + 1)]})
            checks.equal((status, _refusal(answer)), (400, "ticks_invalid"),
                         f"one SKU past the cap of {pipeline_routes.MAX_CLEAR_SKUS} is refused 400 ticks_invalid")


def check_worklist_holds_a_tick_by_drift_and_kind(checks: Checks) -> None:
    """On a reload, a tick 4c off the suggestion holds, a tick 20c off does not, an untick holds, and a Live
    row holds no tick. This runs on both branches of the worklist: with no run on disk, and with one."""
    for with_run in (False, True):
        where = "with a run on disk" if with_run else "with no run on disk"
        checks.note("")
        checks.note(f"WORKLIST, TICKS HELD — the tick holds within the send's drift, {where}")
        with run_folder() as run, isolated_home(run), _served() as port:
            _world(checks, with_run=with_run)
            with _case(checks, f"worklist holds: {where}"):
                checks.equal(_wire_row(port, DUNSPARCE_SKU).get("source"), "Suggested",
                             f"control ({where}): Dunsparce's row is a Suggested row")
                _press(port, {DUNSPARCE_SKU: {"price": "2.16", "on": True}})
                checks.equal(_ticked(port, DUNSPARCE_SKU), True,
                             f"a tick 4c off the 2.20 suggestion holds ({where})")
                _press(port, {DUNSPARCE_SKU: {"price": "2.00", "on": True}})
                checks.equal(_ticked(port, DUNSPARCE_SKU), None,
                             f"a tick 20c off the 2.20 suggestion does not hold, and reads None ({where})")
                _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": False}})
                checks.equal(_ticked(port, DUNSPARCE_SKU), False,
                             f"an untick at the 2.20 suggestion holds, and reads False ({where})")
                _press(port, {ARTICUNO_SKU: {"price": "25.00", "on": True}})
                checks.equal(_wire_row(port, ARTICUNO_SKU).get("source"), "Live",
                             f"control ({where}): Articuno's row is a Live row")
                checks.equal(_ticked(port, ARTICUNO_SKU), None,
                             f"a Live row holds no tick, even on the price the press named ({where})")


def check_reload_reads_each_group_its_tick(checks: Checks) -> None:
    """A reload reads a tick on a Needs you suggestion as True, and an untick on a Suggested row as False.
    The group each row sits in is read first, so a row in the wrong group cannot pass."""
    checks.note("")
    checks.note("WORKLIST, RELOAD — a tick on a Needs you suggestion reads True; an untick on Suggested reads False")
    with run_folder() as run, isolated_home(run), _served() as port:
        _world(checks, with_run=False)
        with _case(checks, "reload: needs you and suggested"):
            checks.equal(_wire_row(port, DUNSPARCE_REVERSE_SKU).get("group"), "needs_you",
                         "control: the reverse, past the cap, is in Needs you")
            checks.equal(_wire_row(port, DUNSPARCE_SKU).get("group"), "suggested",
                         "control: Dunsparce's suggestion is in Suggested")
            status, _ = _press(port, {DUNSPARCE_REVERSE_SKU: {"price": "2.06", "on": True}})
            checks.equal(status, 200, "a tick on the Needs you suggestion is kept: 200")
            checks.equal(_ticked(port, DUNSPARCE_REVERSE_SKU), True,
                         "a reload reads the Needs you tick as True, and the row stays in Needs you")
            checks.equal(_wire_row(port, DUNSPARCE_REVERSE_SKU).get("group"), "needs_you",
                         "and a ticked row is still in Needs you, not moved to Suggested")
            status, _ = _press(port, {DUNSPARCE_SKU: {"price": "2.20", "on": False}})
            checks.equal(status, 200, "an untick on the Suggested row is kept: 200")
            checks.equal(_ticked(port, DUNSPARCE_SKU), False,
                         "a reload reads the Suggested untick as False, and it stays unticked")


SENT_PRICES = [
    {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"},
    {"sku": ARTICUNO_SKU, "price": "24.00", "was": "22.03", "source": "suggested"},
]
BOTH_TICKS = {DUNSPARCE_SKU: {"price": "2.06", "on": True}, ARTICUNO_SKU: {"price": "24.00", "on": True}}


def _send_world(checks: Checks, portal, port) -> None:
    """Articuno is sent once and live at 22.03, Dunsparce is live at 2.50, and both carry a suggestion
    (`_seed_send_suggestions`: Dunsparce 2.06, Articuno 24.00). Both suggestions are ticked on the server."""
    _one_copy_live(checks, portal)
    _seed_send_suggestions()
    _only_live_export({DUNSPARCE_SKU: 1, ARTICUNO_SKU: 1}, {DUNSPARCE_SKU: "2.50", ARTICUNO_SKU: "22.03"})
    status, _ = _press(port, {
        DUNSPARCE_SKU: {"price": "2.06", "on": True},
        ARTICUNO_SKU: {"price": "24.00", "on": True},
    })
    checks.equal(status, 200, "precondition: both suggestions are ticked, so the press answers 200")
    checks.equal((_ticked(port, DUNSPARCE_SKU), _ticked(port, ARTICUNO_SKU)), (True, True),
                 "precondition: both ticks read back ticked before any send")


def check_send_keeps_ticks_when_refused_or_downloaded(checks: Checks) -> None:
    """A send TCGplayer never takes, and a download, keep the kept ticks of the SKUs they name."""
    checks.note("")
    checks.note("SEND, TICKS KEPT — a refused send and a download keep their SKUs' ticks")
    with run_folder() as run, isolated_home(run), send_portal() as portal, _served() as port:
        _seed_sync()
        with _case(checks, "send: refused and download keep ticks"):
            _send_world(checks, portal, port)
            refused = _outcome(lambda: send_routes.do_send({
                "runs": [], "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "1.50", "was": "2.50", "source": "suggested"}],
            }))
            checks.equal(refused, ("refused", "suggestion_changed"),
                         "a send that names a price the server does not rebuild is refused suggestion_changed")
            checks.equal(_kept_on_disk(), BOTH_TICKS, "a refused send keeps both ticks on disk")

            downloaded = _outcome(lambda: send_routes.do_send({
                "runs": [], "download": True, "prices": SENT_PRICES,
            }))
            checks.equal(downloaded[0], "answered", "a download of the same prices is answered")
            checks.equal(_kept_on_disk(), BOTH_TICKS, "a download keeps both ticks on disk")


def check_send_forgets_what_it_priced(checks: Checks) -> None:
    """A send that goes out forgets the kept ticks of the SKUs it priced, and leaves none behind."""
    checks.note("")
    checks.note("SEND, TICKS FORGOTTEN — a send that goes out forgets the ticks of the SKUs it priced")
    with run_folder() as run, isolated_home(run), send_portal() as portal, _served() as port:
        _seed_sync()
        with _case(checks, "send: forgets ticks"):
            _send_world(checks, portal, port)
            sent = _outcome(lambda: send_routes.do_send({"runs": [], "confirm": True, "prices": SENT_PRICES}))
            checks.equal(sent[0], "answered", "the send that goes out is answered")
            checks.equal(_kept_on_disk(), {},
                         "a send that goes out forgets the ticks of the SKUs it priced, and no tick is left")


CHECKS = (
    check_ticks_are_kept_and_read_back,
    check_ticks_drop_removes_and_empty_file_goes,
    check_ticks_corrupt_file_reads_as_none,
    check_ticks_refuse_a_bad_press,
    check_ticks_empty_press_and_drop_cap,
    check_worklist_holds_a_tick_by_drift_and_kind,
    check_reload_reads_each_group_its_tick,
    check_send_keeps_ticks_when_refused_or_downloaded,
    check_send_forgets_what_it_priced,
)


def main() -> int:
    """Runs this group's checks alone, as the T7 runner runs them: each under `hermetic()`, with the network
    refused, and every temp path taken from one run folder."""
    from harness import t7_run_support
    from harness.tests.t7.common import hermetic

    checks = Checks()
    with run_folder() as run, isolated_home(run), t7_run_support.refused_network():
        for check in CHECKS:
            with hermetic():
                check(checks)
    result = checks.result("T7 pricing ticks: the owner's kept ticks on #/pricing")
    print(result.detail)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
