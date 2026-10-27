"""T7 group: the one list's wire — the worklist carries live listings with their suggestions, one
send takes kept suggestions as price-only rows, and the product history carries the asking-price
postings.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

Protects: Every live listing reaches the pricing worklist with its asking price, its last sale
and its suggestion; a kept suggestion rides a send as a price-only row, posted as "suggested",
even with no run named; a suggestion past the cap is refused; the product history lists the
SKU's asking-price postings, oldest first.
Governs: D100, D107 (reopened for suggestions), D227, D243, D273

THE WIRE THIS GROUP PINS (the one-list-wire lane's brief names the behaviour, not the names):
  - `do_pipeline_worklist(...)["live"]`: one row per SKU the newest live export lists with copies.
    Each row carries `sku`, `asking`, `last_sold_at` (the day of the newest `sold` EVENT for the
    SKU, or None, never `sold_here`), `group`, `price`, `source` and `reason`.
  - A `prices` row of a send may carry `"source": "suggested"`. Such a row posts with source
    "suggested". A row without it posts as "emit-price", as before.
  - A suggested price more than the cap away from the live price refuses `suggestion_past_cap`.
  - `do_product_history(sku)["asking_postings"]`: every posting for the SKU, oldest first.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from harness.tests import Checks
from harness.tests.home import isolated_home, run_folder
from harness.tests.t7.common import (
    ARTICUNO_SKU,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    _live_export_bytes,
    append_history,
    seam_run,
)
from harness.tests.t7.price_history import _network_recorder
from harness.tests.t7.send_markdown import _case, _live_export_priced, _seed_sync, send_portal
from pipeline import corpus, readings
from server import pipeline_routes, send_routes
from store import clock, db, files
from store.pricearchive import Bucket
from store.session import Store

NAME = "T7 one-list wire"

# One Articuno card in box 3. Dunsparce and its reverse are live without a card here, which is the
# case the worklist must still carry.
WORKLIST_CARDS = [(3, 1, "Articuno", "161", None)]


def _day(days_ago: int):
    """The US Central day `days_ago` before today."""
    return clock.central_day(clock.now()) - timedelta(days=days_ago)


def _noon(day) -> str:
    """A store stamp at noon UTC on `day`: the same calendar day in every US zone."""
    return clock.iso(datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc))


def _write_live(stamp: str, body: bytes) -> None:
    folder = files.inventory_dir() / pipeline_routes.LIVE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{pipeline_routes.LIVE_PREFIX}{stamp}.csv").write_bytes(body)


def _set_listing(sku: str, **fields) -> None:
    with Store().write() as snapshot:
        entry = snapshot.inventory.listing(sku)
        for name, value in fields.items():
            setattr(entry, name, value)


def _seed_readings() -> None:
    """Markets for live SKUs with no run table, read the way `#/pricing` reads them."""
    with Store().write() as snapshot:
        snapshot.readings.replace(*readings.collect())


def _live_row(payload: dict, sku: str) -> Optional[dict]:
    for row in payload.get("live") or []:
        if row.get("sku") == sku:
            return row
    return None


def _pinned(row: Optional[dict]) -> Optional[dict]:
    """The wire fields a case pins, or None when the row is missing (so the diff names it)."""
    if row is None:
        return None
    keys = ("asking", "last_sold_at", "group", "price", "source", "reason")
    return {key: row.get(key, "<absent>") for key in keys}


def _outcome(fn):
    """`("answered", result)` or `("refused", code)`: a refusal names its code and never raises."""
    try:
        return "answered", fn()
    except pipeline_routes.PipelineRefusal as caught:
        return "refused", caught.code


def _rows(portal) -> dict:
    return {row["ProductConditionId"]: (row["AddToQuantity"], row["MyPrice"]) for row in portal["rows"]}


def _postings(sku: str) -> list:
    conn = db.connect(files.inventory_dir())
    try:
        return db.postings_for_sku(conn, sku)
    finally:
        conn.close()


def _pushed(sku: str) -> int:
    listing = Store().read().inventory.listings.get(sku)
    return 0 if listing is None else listing.pushed


def _typed(sku: str, price: str) -> None:
    book = corpus.Corpus.read()
    book.answers[sku] = corpus.Answer(value=price)
    book.write()


def check_worklist_carries_live_listings(checks: Checks) -> None:
    """`do_pipeline_worklist` answers `live`: every SKU the newest live export lists, each with its
    asking price, its newest SOLD EVENT's day, and the suggestion the engine gives it.

    Three live SKUs, three shapes:
      Articuno   unsold 60 days and 13% over market, so a suggestion down to market. Its
                 `sold_here_at` is a decoy two days old with no sold event behind it: the sale
                 that counts is a sold EVENT, so there is none and the suggestion stands.
      Dunsparce  two sold events, 50 and 10 days ago. The NEWEST one counts: ten days unsold is
                 under the 30-day trigger, so the row stays at its asking price.
      Reverse    live without a card here, first seen 5 days ago, asking at market: at its price.
    """
    checks.note("")
    checks.note("WORKLIST — every live listing, with its asking price, last sale and suggestion")
    with run_folder() as run, isolated_home(run):
        _seed_sync()
        with _case(checks, "worklist: live listings"):
            seam_run(checks, WORKLIST_CARDS)
            _write_live(
                "20260201-000000",
                _live_export_priced(
                    {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1, DUNSPARCE_REVERSE_SKU: 1},
                    {ARTICUNO_SKU: "25.00", DUNSPARCE_SKU: "2.50", DUNSPARCE_REVERSE_SKU: "2.60"},
                ),
            )
            _seed_readings()
            _set_listing(ARTICUNO_SKU, first_seen_live=_noon(_day(60)), sold_here=2, sold_here_at=_noon(_day(2)))
            _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
            _set_listing(DUNSPARCE_REVERSE_SKU, first_seen_live=_noon(_day(5)))
            append_history([
                {"at": _noon(_day(50)), "event": "sold", "sku": DUNSPARCE_SKU},
                {"at": _noon(_day(10)), "event": "sold", "sku": DUNSPARCE_SKU},
            ])

            name, live_now = pipeline_routes._newest_live_listing()
            checks.ok(
                name is not None and all(live_now.get(s, (None, 0))[1] for s in (ARTICUNO_SKU, DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU)),
                "precondition: the newest live export lists all three SKUs live",
                repr(live_now),
            )
            with _network_recorder() as attempts:
                payload = pipeline_routes.do_pipeline_worklist([])
            checks.equal(attempts, [], "the worklist fetches nothing: every live price is read off disk")

            checks.equal(
                _pinned(_live_row(payload, ARTICUNO_SKU)),
                {
                    "asking": "25.00", "last_sold_at": None, "group": "suggested", "price": "22.03",
                    "source": "Suggested", "reason": "unsold 60 days, priced 13% over market",
                },
                "Articuno: the decoy `sold_here_at` is not a sale, so the unsold trigger fires and "
                "the suggestion is market, inside the cap",
            )
            checks.equal(
                _pinned(_live_row(payload, DUNSPARCE_SKU)),
                {
                    "asking": "2.50", "last_sold_at": _day(10).isoformat(), "group": "at_rule",
                    "price": "2.50", "source": "Live", "reason": "",
                },
                "Dunsparce: the NEWEST sold event names the last sale (ten days ago, not fifty), "
                "so under 30 days unsold it stays at its asking price",
            )
            checks.equal(
                _pinned(_live_row(payload, DUNSPARCE_REVERSE_SKU)),
                {
                    "asking": "2.60", "last_sold_at": None, "group": "at_rule", "price": "2.60",
                    "source": "Live", "reason": "",
                },
                "the live-only reverse is carried too, with no run row under it, at its asking price",
            )


def check_worklist_without_runs_reads_newest_export(checks: Checks) -> None:
    """With no run on disk the worklist still carries `live`, and the price is the NEWER export's.

    Two live exports sit in the folder; the older names 9.00 and the newer 2.50. The row must read
    2.50, and the read must not reach the network.
    """
    checks.note("")
    checks.note("WORKLIST, NO RUNS — the newest live export is the price, read off disk")
    with run_folder() as run, isolated_home(run):
        _write_live("20260102-000000", _live_export_priced({DUNSPARCE_SKU: 1}, {DUNSPARCE_SKU: "9.00"}))
        _write_live("20260103-000000", _live_export_priced({DUNSPARCE_SKU: 1}, {DUNSPARCE_SKU: "2.50"}))
        with _case(checks, "worklist without runs: newest export"):
            with _network_recorder() as attempts:
                payload = pipeline_routes.do_pipeline_worklist([])
            checks.equal(attempts, [], "no run and no network: the live rows come off disk alone")
            checks.equal(
                _pinned(_live_row(payload, DUNSPARCE_SKU)),
                {
                    "asking": "2.50", "last_sold_at": None, "group": "at_rule", "price": "2.50",
                    "source": "Live", "reason": "",
                },
                "with no run and no market, the live row carries the NEWER export's asking price",
            )


def _one_copy_live(checks: Checks, portal) -> object:
    """Articuno sent once, then live at 22.03 with Dunsparce live at 2.50 beside it. Returns the
    run. The shared step for the send cases: each case then names its own prices."""
    run_dir, _ = seam_run(checks, WORKLIST_CARDS)
    portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
    send_routes.do_send({"runs": [run_dir.name], "confirm": True})
    portal["live"] = _live_export_priced(
        {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1}, {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "2.50"}
    )
    portal["rows"].clear()
    return run_dir


def check_send_takes_suggestions_with_no_run(checks: Checks) -> None:
    """A send naming only prices, `runs: []`, takes two kept suggestions as price-only rows: one
    down (Dunsparce 2.50 to 2.06, 18%) and one up (Articuno 22.03 to 24.00, 9%). Both are inside
    the 25% cap. Each row posts with source "suggested" and the price it replaced.
    """
    checks.note("")
    checks.note("SEND, PRICES ONLY — kept suggestions ride with no run named")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: suggestions with no runs"):
            _one_copy_live(checks, portal)
            checks.equal(_pushed(ARTICUNO_SKU), 1, "precondition: Articuno's one copy is live (pushed 1)")
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [
                    {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"},
                    {"sku": ARTICUNO_SKU, "price": "24.00", "was": "22.03", "source": "suggested"},
                ],
            }))
            checks.equal(
                outcome[0] if outcome[0] == "refused" else "answered",
                "answered",
                f"a prices-only send is answered, not refused (got {outcome[1] if outcome[0] == 'refused' else ''})",
            )
            if outcome[0] == "answered":
                sent = outcome[1]["send"]
                checks.equal(
                    _rows(portal),
                    {DUNSPARCE_SKU: ("0", "2.06"), ARTICUNO_SKU: ("0", "24.00")},
                    "each suggestion goes to TCGplayer as a price-only row: Add to Quantity 0, at its price",
                )
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(DUNSPARCE_SKU)],
                    [("2.06", "2.50", "suggested")],
                    "the Dunsparce posting is source \"suggested\" and names the 2.50 it replaced",
                )
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(ARTICUNO_SKU)],
                    [("24.00", "22.03", "suggested")],
                    "the Articuno posting is source \"suggested\" and names the 22.03 it replaced",
                )
                checks.equal((_pushed(ARTICUNO_SKU), _pushed(DUNSPARCE_SKU)), (1, 0),
                             "a price-only row counts no copy")
                checks.equal((sent["copies"], sent["prices"]), (0, 2),
                             "the receipt names no copy and two price changes")


def check_send_suggestion_beside_typed_price(checks: Checks) -> None:
    """One press, one typed price and one suggestion, with a run named. The typed price keeps its
    own source ("emit-price"); the suggestion posts as "suggested". The source belongs to the row,
    so a build cannot rename every posting to one word.
    """
    checks.note("")
    checks.note("SEND, MIXED — a typed price and a suggestion in one press keep their own sources")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: typed beside suggested"):
            run_dir = _one_copy_live(checks, portal)
            _typed(ARTICUNO_SKU, "30.00")
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [run_dir.name],
                "confirm": True,
                "prices": [
                    {"sku": ARTICUNO_SKU, "price": "30.00", "was": "22.03"},
                    {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"},
                ],
            }))
            checks.equal(
                outcome[0] if outcome[0] == "refused" else "answered",
                "answered",
                f"the mixed press is answered (got {outcome[1] if outcome[0] == 'refused' else ''})",
            )
            if outcome[0] == "answered":
                checks.equal(
                    _rows(portal),
                    {ARTICUNO_SKU: ("0", "30.00"), DUNSPARCE_SKU: ("0", "2.06")},
                    "both price-only rows go out in the one press",
                )
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(ARTICUNO_SKU)],
                    [("30.00", "22.03", "emit-price")],
                    "the typed price keeps source \"emit-price\"",
                )
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(DUNSPARCE_SKU)],
                    [("2.06", "2.50", "suggested")],
                    "the suggestion posts as \"suggested\"",
                )


def check_send_refuses_suggestion_past_cap(checks: Checks) -> None:
    """A suggested price 60% above the live 2.50 is past the 25% cap. The press refuses by name,
    and no row reaches TCGplayer and no posting is written.
    """
    checks.note("")
    checks.note("SEND, PAST THE CAP — a suggestion beyond the cap is refused, and nothing is sent")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: suggestion past cap"):
            _one_copy_live(checks, portal)
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "4.00", "was": "2.50", "source": "suggested"}],
            }))
            checks.equal(outcome, ("refused", "suggestion_past_cap"),
                         "a suggestion past the cap is refused as suggestion_past_cap")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


def check_send_empty_runs_without_prices_refused(checks: Checks) -> None:
    """Guard against an overbroad build: an empty `runs` with NO prices named is still refused
    `runs_required`. Only named prices may stand in for runs. Green today; it must stay green.
    """
    checks.note("")
    checks.note("SEND, NOTHING NAMED — an empty runs list with no prices is still refused")
    with run_folder() as run, isolated_home(run):
        _seed_sync()
        with _case(checks, "send: empty runs, no prices"):
            outcome = _outcome(lambda: send_routes.do_send({"runs": [], "confirm": True}))
            checks.equal(outcome, ("refused", "runs_required"),
                         "an empty runs list with no prices named is refused runs_required")


def check_product_history_asking_postings(checks: Checks) -> None:
    """`do_product_history` answers the SKU's asking-price postings, oldest first, on the archive
    path (no network). Two postings: the first as recorded by an emit, the second a suggestion
    that replaced the first's price.
    """
    checks.note("")
    checks.note("PRODUCT HISTORY — the asking-price line's postings, oldest first")
    with run_folder() as run, isolated_home(run):
        _seed_sync()
        with _case(checks, "product history: asking postings"):
            seam_run(checks, [(3, 4, "Dunsparce", "120", "normal")])
            with Store().write() as snapshot:
                snapshot.archive.upsert({
                    f"{DUNSPARCE_SKU}:month:2026-09-10":
                        Bucket(DUNSPARCE_SKU, 4242, "month", 1, "2026-09-10", "0.50", 5, 2, None, None, 0)
                })
                snapshot.postings.record(sku=DUNSPARCE_SKU, price="2.50", source="emit-price", at=1790000000)
                snapshot.postings.record(
                    sku=DUNSPARCE_SKU, price="2.06", source="suggested", replaced="2.50", at=1790000600
                )
            payload = pipeline_routes.do_product_history(DUNSPARCE_SKU)
            checks.equal(payload.get("source"), "archive", "precondition: the archive answers, so no network")
            checks.equal(
                [(p.get("price"), p.get("source"), p.get("replaced")) for p in payload.get("asking_postings") or []],
                [("2.50", "emit-price", None), ("2.06", "suggested", "2.50")],
                "the product history carries the asking-price postings, oldest first, each with its "
                "price, source and the price it replaced",
            )
            checks.equal(
                all((p.get("at") is not None) for p in payload.get("asking_postings") or []),
                True,
                "and every posting carries when it was written",
            )


CHECKS = (
    check_worklist_carries_live_listings,
    check_worklist_without_runs_reads_newest_export,
    check_send_takes_suggestions_with_no_run,
    check_send_suggestion_beside_typed_price,
    check_send_refuses_suggestion_past_cap,
    check_send_empty_runs_without_prices_refused,
    check_product_history_asking_postings,
)
