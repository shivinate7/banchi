"""T7 group: the one list's wire — the worklist carries live listings with their suggestions, one
send takes kept suggestions as price-only rows, and the product history carries the asking-price
postings.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

Protects: Every live listing reaches the pricing worklist with its asking price, its last sale
and its suggestion; the market on the day a listing went live comes from the price archive; a
kept suggestion rides a send as a price-only row, posted as "suggested", even with no run named or
in a game no run of the send files; the server rebuilds each kept suggestion, sends one that drifted
a little at its rebuilt price, leaves out one that moved further (a press left with nothing refuses
`suggestion_changed`), and refuses a past-cap one unless the send marks that row ticked; the product
history lists the SKU's asking-price postings, oldest first.
Governs: D100, D107 (reopened for suggestions), D227, D243, D273

THE WIRE THIS GROUP PINS (the one-list-wire lane's brief names the behaviour, not the names):
  - `do_pipeline_worklist(...)["live"]`: one row per SKU the newest live export lists with copies.
    Each row carries `sku`, `asking`, `last_sold_at` (the day of the newest SOLD CARD for the SKU,
    read off the card state, or None; never the sold-event log), `group`, `price`, `source` and
    `reason`.
  - Each live row also carries `name`, `set_name`, `market`, `low` and `image_url`, all read off the
    one `readings` row the engine used for the SKU (the thumbnail's game and number come off the
    export row, which the reading lacks). Each unsent row in `skus` carries `group`, the engine's
    own: `needs_you` at or above `value_line` or with no market price, else `at_rule`.
  - A listing's market on its listing day (`market_listed`) is the price archive's bucket that
    holds `first_seen_live`: the `month` bucket (one day) when there is one, else the `quarter`
    bucket (three days). No bucket holds that day, so the market-moved trigger does not fire.
  - A `prices` row of a send may carry `"source": "suggested"`. Such a row posts with source
    "suggested". A row without it posts as "emit-price", as before.
  - The server rebuilds every named suggestion with the worklist's own code. A rebuilt suggestion
    past the cap refuses `suggestion_past_cap`, unless the send marks that row `"ticked": true` (a boolean on the
    row; a bigger move shows apart and needs a tick). The cap is measured on the price the press sends,
    after a drift re-price. A named price the server rebuilds within
    `sendguard.drift_allowed` is sent at the rebuilt price and named under `moved`. One it does not
    rebuild that close, or that has no rebuilt suggestion, is left out and named under `left_out`;
    a press left with nothing else to send refuses `suggestion_changed`.
  - `do_product_history(sku)["asking_postings"]`: every posting for the SKU, oldest first.
  - A `prices` list names each SKU once. A repeated SKU refuses `prices_invalid` at the route
    (`send_routes._named_prices`) and raises `cmd_emit.PriceRefused` for the emit file, before
    anything is written.
  - A zero-run send of kept suggestions refuses `readings_stale` when a reading behind one was not
    written on today's US Central day (the D166 rule: the export belongs to its day).
  - A kept suggestion on a SKU that is live and held is left out of the send, and the answer names
    that SKU under its top-level `held` key. `send.held` stays the receipt's own boolean.
  - The worklist's no-runs branch, with a corpus that cannot be read, answers `error:
    "corpus_unreadable"` and draws no default-policy suggestion.
  - A live suggestion held back by the owner's limit has a reason ending "; capped at your N%",
    N being the owner's `limit` as a percent.
  - `do_markdown_table(stamp)["skus"]` rows carry `group` (the worklist's own rule, read off each
    survey row's `row` cells). A corpus that cannot be read leaves `group` absent on every row.
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from harness.tests import Checks
from harness.tests.home import isolated_home, run_folder
from harness.tests.t7.common import (
    ARTICUNO_SKU,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    SEAM_SKUS,
    _live_export_bytes,
    append_history,
    seam_run,
)
from harness.tests.t7.price_history import _network_recorder
from harness.tests.t7.read_budget import TABLE_STAMP, _write_survey
from harness.tests.t7.send_markdown import _case, _live_export_priced, _seed_sync, send_portal
from cli import cmd_emit, runs
from pipeline import corpus, pricing, readings, tcgcsv, worklist
from server import pipeline_routes, send_routes
from store import clock, db, files, master
from store.pricearchive import RANGE_WIDTH_DAYS, Bucket
from store.readings import Reading
from store.session import Store

NAME = "T7 one-list wire"

# One Articuno card in box 3. Dunsparce and its reverse are live without a card here, which is the
# case the worklist must still carry. The send cases build on this list, so Dunsparce's sold copies
# (for the worklist's last-sale case) are added there alone, in `DUNSPARCE_SOLD`.
WORKLIST_CARDS = [(3, 1, "Articuno", "161", None)]
DUNSPARCE_SOLD = [(3, 2, "Dunsparce", "120", "normal"), (3, 3, "Dunsparce", "120", "normal")]


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


def _market_reading(sku: str, market: str, low_with_shipping: Optional[str] = None,
                    at: Optional[int] = None) -> None:
    """One market reading for `sku`, written as a `readings` row. Overrides any collected one.
    `at` is its unix second; now when not given."""
    with Store().write() as snapshot:
        snapshot.readings.entries[sku] = Reading(
            market=market,
            at=int(time.time()) if at is None else at,
            source="t7-one-list-wire",
            kind="run",
            low_with_shipping=low_with_shipping,
        )


def _bucket(sku: str, range_: str, start: str, market: str) -> None:
    """One archived `price_history` bucket, written as the archive walk writes it."""
    with Store().write() as snapshot:
        snapshot.archive.upsert({
            f"{sku}:{range_}:{start}":
                Bucket(sku, 4242, range_, RANGE_WIDTH_DAYS[range_], start, market, 5, 2, None, None, 0)
        })


def _sell_card(box: int, index: int, sku: str, at: str) -> None:
    """Mark one card sold, bound to `sku` and stamped `at`. A direct write: `emit` binds a card's
    SKU only on a send, and the sold-event log stays untouched."""
    with Store().write() as snapshot:
        card = snapshot.inventory.cards.get(master.position_key(box, index))
        card.sku = sku
        card.state = master.SOLD
        card.state_at = at


def _seed_send_suggestions() -> None:
    """The market behind the two kept suggestions the send cases name, so the server's rebuild
    agrees with their prices. Dunsparce is 2.06 and unsold 60 days (down from its 2.50). Articuno's
    market rose 20% since it went live (up to 24.00, inside the cap)."""
    _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
    _market_reading(DUNSPARCE_SKU, "2.06", "2.40")
    _set_listing(ARTICUNO_SKU, first_seen_live=_noon(_day(5)))
    _bucket(ARTICUNO_SKU, "month", _day(5).isoformat(), "20.00")
    _market_reading(ARTICUNO_SKU, "24.00", "24.50")


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


def _outcome(fn, *, any_error: bool = False):
    """`("answered", result)` or `("refused", code)`: a refusal names its code and never raises.
    `any_error` also names the refusal's text, and an error the route does not wrap by its class and
    text, so the case reads the refusal's cause and never a crash."""
    try:
        return "answered", fn()
    except pipeline_routes.PipelineRefusal as caught:
        return "refused", f"{caught.code}: {caught}" if any_error else caught.code
    except Exception as caught:
        if not any_error:
            raise
        return "refused", f"{type(caught).__name__}: {caught}"


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


def _typed(sku: str, value) -> None:
    """One corpus answer for `sku`: a typed price, or a dict such as `{"withheld": "keeping"}`."""
    book = corpus.Corpus.read()
    book.answers[sku] = corpus.Answer(value=value)
    book.write()


def _yesterday_at() -> int:
    """Unix seconds of noon UTC on the US Central day before today: that day, whatever the zone."""
    day = _day(1)
    return int(datetime(day.year, day.month, day.day, 18, tzinfo=timezone.utc).timestamp())


def check_worklist_carries_live_listings(checks: Checks) -> None:
    """`do_pipeline_worklist` answers `live`: every SKU the newest live export lists, each with its
    asking price, its newest SOLD CARD's day, and the suggestion the engine gives it.

    Three live SKUs, three shapes:
      Articuno   unsold 60 days and 13% over market, so a suggestion down to market. Its
                 `sold_here_at` is a decoy two days old with no sold card behind it: the sale
                 that counts is a sold CARD, so there is none and the suggestion stands.
      Dunsparce  two sold cards, 50 and 10 days ago. The NEWEST one counts: ten days unsold is
                 under the 30-day trigger, so the row stays at its asking price. A sold event two
                 days old is a decoy: the last sale is the card state, never the event log.
      Reverse    live without a card here, first seen 5 days ago, asking at market: at its price.
    """
    checks.note("")
    checks.note("WORKLIST — every live listing, with its asking price, last sale and suggestion")
    with run_folder() as run, isolated_home(run):
        _seed_sync()
        with _case(checks, "worklist: live listings"):
            seam_run(checks, WORKLIST_CARDS + DUNSPARCE_SOLD)
            _sell_card(3, 2, DUNSPARCE_SKU, _noon(_day(50)))
            _sell_card(3, 3, DUNSPARCE_SKU, _noon(_day(10)))
            append_history([{"at": _noon(_day(2)), "event": "sold", "sku": DUNSPARCE_SKU}])
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

            sold_dunsparce = [c for c in Store().read().inventory.in_state(master.SOLD) if c.sku == DUNSPARCE_SKU]
            checks.equal(len(sold_dunsparce), 2, "precondition: two Dunsparce copies are sold in state")

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
                "Dunsparce: the NEWEST sold card names the last sale (ten days ago, not fifty, and "
                "not the two-day-old event), so under 30 days unsold it stays at its asking price",
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
    """With no run on disk the worklist still carries `live`, and the asking price is the NEWER export's.

    Two live exports sit in the folder; the older names 9.00 and the newer 2.50. The row must ask
    2.50, and the read must not reach the network. No reading exists for the SKU, so the row needs
    you, with no suggested price (spec "Needs you": a live listing with no market price).
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
                    "asking": "2.50", "last_sold_at": None, "group": "needs_you", "price": None,
                    "source": "Live", "reason": "no market price",
                },
                "with no send and no market, the live row needs you with no price, and asks the NEWER export's price",
            )


def check_worklist_market_on_listing_day(checks: Checks) -> None:
    """The market on a listing's listing day (`market_listed`) comes from the price archive: the
    `month` bucket that holds `first_seen_live`, else the `quarter` bucket that holds it.

    Three live SKUs, each asking 10.00 and at market 12.00 now (20% up), first seen 5 days ago:
      Articuno   a month bucket for that day at 10.00 AND a quarter bucket at 8.00. The month wins,
                 so the rise reads 20%: "market up 20% since listed", suggested at 12.00.
      Dunsparce  a quarter bucket only, holding that day at 10.00. The fallback reads the same 20%.
      Reverse    a month bucket for a DIFFERENT day (four days ago). No bucket holds the listing
                 day, so the market-moved trigger does not fire: at its asking price.
    """
    checks.note("")
    checks.note("WORKLIST, MARKET ON THE LISTING DAY — the archive's bucket for that day")
    with run_folder() as run, isolated_home(run), _case(checks, "worklist: market on the listing day"):
        day = _day(5)
        before_day = (day - timedelta(days=1)).isoformat()
        _write_live(
            "20260201-000000",
            _live_export_priced(
                {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1, DUNSPARCE_REVERSE_SKU: 1},
                {ARTICUNO_SKU: "10.00", DUNSPARCE_SKU: "10.00", DUNSPARCE_REVERSE_SKU: "10.00"},
            ),
        )
        for sku in SEAM_SKUS:
            _set_listing(sku, first_seen_live=_noon(day))
            _market_reading(sku, "12.00", "12.50")
        _bucket(ARTICUNO_SKU, "month", day.isoformat(), "10.00")
        _bucket(ARTICUNO_SKU, "quarter", before_day, "8.00")
        _bucket(DUNSPARCE_SKU, "quarter", before_day, "10.00")
        _bucket(DUNSPARCE_REVERSE_SKU, "month", _day(4).isoformat(), "10.00")
        archived = sorted(
            (b.sku, b.range, b.start, b.market) for sku in SEAM_SKUS for b in Store().read().archive.for_sku(sku)
        )
        checks.equal(archived, sorted([
            (ARTICUNO_SKU, "month", day.isoformat(), "10.00"),
            (ARTICUNO_SKU, "quarter", before_day, "8.00"),
            (DUNSPARCE_SKU, "quarter", before_day, "10.00"),
            (DUNSPARCE_REVERSE_SKU, "month", _day(4).isoformat(), "10.00"),
        ]), "precondition: the four archived buckets are in the store")

        with _network_recorder() as attempts:
            payload = pipeline_routes.do_pipeline_worklist([])
        checks.equal(attempts, [], "the listing-day market is read off the archive: no network")

        rose = {
            "asking": "10.00", "last_sold_at": None, "group": "suggested", "price": "12.00",
            "source": "Suggested", "reason": "market up 20% since listed",
        }
        checks.equal(
            _pinned(_live_row(payload, ARTICUNO_SKU)), rose,
            "Articuno: the month bucket holding the listing day names its 10.00, so the rise is "
            "20%, not the quarter's 50%",
        )
        checks.equal(
            _pinned(_live_row(payload, DUNSPARCE_SKU)), rose,
            "Dunsparce: with no month bucket, the quarter bucket that holds the listing day "
            "names its 10.00, so the rise is 20%",
        )
        checks.equal(
            _pinned(_live_row(payload, DUNSPARCE_REVERSE_SKU)),
            {
                "asking": "10.00", "last_sold_at": None, "group": "at_rule", "price": "10.00",
                "source": "Live", "reason": "",
            },
            "Reverse: a bucket for another day is not the listing day's market, so the "
            "market-moved trigger does not fire",
        )


def _one_copy_live(checks: Checks, portal, *, prices: Optional[Dict[str, str]] = None) -> object:
    """Articuno sent once, then live at 22.03 with Dunsparce live beside it. `prices` overrides a
    live price by SKU. Returns the run. The shared step for the send cases: each case then names
    its own prices."""
    run_dir, _ = seam_run(checks, WORKLIST_CARDS)
    portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
    send_routes.do_send({"runs": [run_dir.name], "confirm": True})
    named = {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "2.50", **(prices or {})}
    portal["live"] = _live_export_priced({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1}, named)
    portal["rows"].clear()
    return run_dir


def check_send_takes_suggestions_with_no_run(checks: Checks) -> None:
    """A send naming only prices, `runs: []`, takes two kept suggestions as price-only rows: one
    down (Dunsparce 2.50 to 2.06, 18%) and one up (Articuno 22.03 to 24.00, 9%). Both are inside
    the 25% cap, and both are what the server rebuilds from the market. Each row posts with source
    "suggested" and the price it replaced.
    """
    checks.note("")
    checks.note("SEND, PRICES ONLY — kept suggestions ride with no run named")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: suggestions with no runs"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
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
                    [("22.03", None, "emit"), ("24.00", "22.03", "suggested")],
                    "the Articuno postings are the setup send's 22.03, then a source \"suggested\" "
                    "posting that names the 22.03 it replaced",
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
            _seed_send_suggestions()
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
                    [("22.03", None, "emit"), ("30.00", "22.03", "emit-price")],
                    "the typed price keeps source \"emit-price\", after the setup send's 22.03",
                )
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(DUNSPARCE_SKU)],
                    [("2.06", "2.50", "suggested")],
                    "the suggestion posts as \"suggested\"",
                )


def _past_cap_world(checks: Checks, portal) -> None:
    """Dunsparce live at 3.00, unsold 60 days, with a market of 2.06. The engine's own suggestion is 2.06: 31% from the live
    price, past the 25% cap. The shared step for every past-the-cap case."""
    _one_copy_live(checks, portal, prices={DUNSPARCE_SKU: "3.00"})
    _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
    _market_reading(DUNSPARCE_SKU, "2.06", "2.40")


def _past_cap_row(**fields) -> dict:
    """The one kept past-cap suggestion `_past_cap_world` rebuilds. `fields` adds to the row, such as `ticked`."""
    return {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "3.00", "source": "suggested", **fields}


def check_send_refuses_suggestion_past_cap(checks: Checks) -> None:
    """The engine's own suggestion for Dunsparce is 2.06 (unsold 60 days), and TCGplayer now shows
    3.00. That is 31% from the live price, past the 25% cap. The client names the same 2.06, so the
    server's rebuild agrees with it and refuses by name. No row reaches TCGplayer and no posting is
    written.
    """
    checks.note("")
    checks.note("SEND, PAST THE CAP — the server's own suggestion beyond the cap is refused, and nothing is sent")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: suggestion past cap"):
            _past_cap_world(checks, portal)
            outcome = _outcome(lambda: send_routes.do_send({"runs": [], "confirm": True, "prices": [_past_cap_row()]}))
            checks.equal(outcome, ("refused", "suggestion_past_cap"),
                         "a suggestion past the cap is refused as suggestion_past_cap")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


def check_send_past_cap_needs_a_tick(checks: Checks) -> None:
    """A bigger move shows apart and needs a tick (`docs/specs/pricing-suggest.md`, the cap row). The server accepts a
    past-cap suggestion only when the send marks THAT row `"ticked": true`; the field is a boolean on the row. Three presses,
    each its own case, on the world `check_send_refuses_suggestion_past_cap` builds:

      Ticked     `ticked: true`. The 2.06 goes to TCGplayer as a price-only row, posted "suggested", replacing 3.00.
      Not ticked `ticked: false`, or no `ticked` at all, or a truthy value that is not a boolean: refused
                 `suggestion_past_cap`. No row reaches TCGplayer and no posting is written.
      One tick   two past-cap rows, one ticked: the tick frees its own row alone. The refusal names the other row only.
    """
    checks.note("")
    checks.note("SEND, PAST THE CAP, TICKED — a past-cap suggestion rides only when its own row is ticked")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: ticked past-cap suggestion"):
            _past_cap_world(checks, portal)
            outcome = _outcome(lambda: send_routes.do_send({"runs": [], "confirm": True, "prices": [_past_cap_row(ticked=True)]}))
            checks.equal(
                outcome[0] if outcome[0] == "refused" else "answered",
                "answered",
                f"a ticked past-cap suggestion is answered, not refused (got {outcome[1] if outcome[0] == 'refused' else ''})",
            )
            if outcome[0] == "answered":
                checks.equal(_rows(portal), {DUNSPARCE_SKU: ("0", "2.06")},
                             "it goes to TCGplayer as a price-only row: Add to Quantity 0, at its price")
                checks.equal(
                    [(p["price"], p["replaced"], p["source"]) for p in _postings(DUNSPARCE_SKU)],
                    [("2.06", "3.00", "suggested")],
                    "and posts as \"suggested\", naming the 3.00 it replaced",
                )

    # `refusals` holds the codes a build may answer with. A tick that is not a boolean may be refused as a malformed price
    # (`prices_invalid`) rather than as past the cap; it may never send.
    for label, fields, refusals in (
        ("ticked false", {"ticked": False}, ("suggestion_past_cap",)),
        ("ticked absent", {}, ("suggestion_past_cap",)),
        ("ticked is the text \"true\"", {"ticked": "true"}, ("suggestion_past_cap", "prices_invalid")),
    ):
        with run_folder() as run, isolated_home(run), send_portal() as portal:
            _seed_sync()
            with _case(checks, f"send: past-cap suggestion, {label}"):
                _past_cap_world(checks, portal)
                outcome = _outcome(lambda fields=fields: send_routes.do_send({"runs": [], "confirm": True, "prices": [_past_cap_row(**fields)]}))
                checks.ok(
                    outcome[0] == "refused" and outcome[1] in refusals,
                    f"{label}: refused as {' or '.join(refusals)}",
                    f"answered: {outcome}",
                )
                checks.equal(_rows(portal), {}, f"{label}: TCGplayer receives no row")
                checks.equal(_postings(DUNSPARCE_SKU), [], f"{label}: no posting is written")

    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: two past-cap suggestions, one ticked"):
            _past_cap_world(checks, portal)
            # The reverse holofoil is live at 4.00 beside it, unsold 60 days, market 2.60: a second suggestion 35% below its price.
            portal["live"] = _live_export_priced(
                {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1, DUNSPARCE_REVERSE_SKU: 1},
                {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "3.00", DUNSPARCE_REVERSE_SKU: "4.00"},
            )
            _set_listing(DUNSPARCE_REVERSE_SKU, first_seen_live=_noon(_day(60)))
            _market_reading(DUNSPARCE_REVERSE_SKU, "2.60", "2.90")
            try:
                send_routes.do_send({
                    "runs": [],
                    "confirm": True,
                    "prices": [
                        _past_cap_row(ticked=True),
                        {"sku": DUNSPARCE_REVERSE_SKU, "price": "2.60", "was": "4.00", "source": "suggested"},
                    ],
                })
                refused = None
            except pipeline_routes.PipelineRefusal as caught:
                refused = (caught.code, [note["sku"] for note in (caught.data or {}).get("refused") or []])
            checks.equal(refused, ("suggestion_past_cap", [DUNSPARCE_REVERSE_SKU]),
                         "the unticked row is refused by name and the ticked row is not named")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row, ticked or not")
            checks.equal((_postings(DUNSPARCE_SKU), _postings(DUNSPARCE_REVERSE_SKU)), ([], []), "and no posting is written")


def check_send_suggestion_changed(checks: Checks) -> None:
    """The server never trusts the client's price. Two shapes, each its own press:

      Changed    the engine's own suggestion for Dunsparce is 2.06. The client names 2.20: inside the
                 cap, so the cap check alone would let it through, but not the price the server
                 rebuilds. Refused suggestion_changed.
      Gone       the engine has no market for Dunsparce, so it gives no suggestion. The client still
                 names 4.00. The server rebuilds nothing to confirm, so the named price is refused
                 suggestion_changed, not suggestion_past_cap.

    Each refusal reaches no row at TCGplayer and writes no posting. Both are presses left with nothing
    else to send; a drift inside `sendguard.drift_allowed` is sent, not refused (`check_send_suggestion_drift`).
    """
    checks.note("")
    checks.note("SEND, CHANGED — a named suggestion the server does not rebuild, with nothing else to send, is refused")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: named price differs from the server's suggestion"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "2.20", "was": "2.50", "source": "suggested"}],
            }))
            checks.equal(outcome, ("refused", "suggestion_changed"),
                         "a named price the server's rebuild does not give is refused suggestion_changed")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")

    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: no server suggestion to confirm"):
            _one_copy_live(checks, portal)
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "4.00", "was": "2.50", "source": "suggested"}],
            }))
            checks.equal(outcome, ("refused", "suggestion_changed"),
                         "with no suggestion for the SKU, a named 4.00 is refused suggestion_changed, "
                         "not suggestion_past_cap")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


RIFTBOUND_PRODUCT_LINE = "Riftbound League of Legends Trading Card Game"


def _live_product_line(run, portal, sku: str, product_line: str) -> None:
    """Rewrite one live row's `Product Line` cell in the export the portal serves, so that row is in a
    game no run of the send files. The real CSV reader and writer, in the case's own run folder."""
    path = run / "live.csv"
    path.write_bytes(portal["live"])
    source = tcgcsv.read_export(path)
    rows = [{**row, "Product Line": product_line} if tcgcsv.sku_cell(row) == sku else row for row in source.rows]
    tcgcsv.write_csv(path, source.header, rows)
    portal["live"] = path.read_bytes()


def check_send_suggestion_drift(checks: Checks) -> None:
    """A kept suggestion's price may drift between the draw and the press by the larger of 5% of the
    drawn price and 5 cents (`sendguard.drift_allowed`). Inside that, the press sends the FRESH price
    and names the row under `moved`. Past it, the row is left out and named under `left_out`, and the
    rest of the press still goes.
    """
    checks.note("")
    checks.note("SEND, DRIFT — cents of drift go at the fresh price; a bigger change leaves only that SKU out")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: Dunsparce drawn at 2.08, rebuilt 2.06"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "2.08", "was": "2.50", "source": "suggested"}],
            }))
            checks.ok(outcome[0] == "answered", "two cents of drift is answered", f"refused: {outcome[1]}")
            if outcome[0] == "answered":
                checks.equal(_rows(portal), {DUNSPARCE_SKU: ("0", "2.06")}, "the row goes at the fresh 2.06")
                checks.equal([(m["sku"], m["was"], m["price"]) for m in outcome[1].get("moved") or []],
                             [(DUNSPARCE_SKU, "2.08", "2.06")], "named under `moved`")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: one suggestion changed past the drift, one holds"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [
                    {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"},
                    {"sku": ARTICUNO_SKU, "price": "26.00", "was": "22.03", "source": "suggested"},
                ],
            }))
            checks.ok(outcome[0] == "answered", "the press is answered, with Dunsparce still in it",
                      f"refused: {outcome[1]}")
            if outcome[0] == "answered":
                checks.equal(_rows(portal), {DUNSPARCE_SKU: ("0", "2.06")}, "only Dunsparce goes")
                checks.equal([m["sku"] for m in outcome[1].get("left_out") or []], [ARTICUNO_SKU],
                             "Articuno is named under `left_out`")
                checks.equal([p["source"] for p in _postings(ARTICUNO_SKU)], ["emit"],
                             "no suggested posting for Articuno")


def check_send_suggestion_other_game(checks: Checks) -> None:
    """A kept suggestion whose live row is in a game no run of the send files still rides the send as
    a price-only row, filed under its own game (`cmd_emit._suggested_rows`). The press is answered; it
    is not refused "not in a game this send files"."""
    checks.note("")
    checks.note("SEND, OTHER GAME — a kept suggestion in a game the run does not file still goes")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send with a run: the suggestion's live row is a Riftbound row"):
            run_dir = _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _live_product_line(run, portal, DUNSPARCE_SKU, RIFTBOUND_PRODUCT_LINE)
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [run_dir.name],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"}],
            }), any_error=True)
            checks.ok(outcome[0] == "answered", "the send is answered, not refused", f"refused: {outcome[1]}")
            if outcome[0] == "answered":
                checks.equal(_rows(portal).get(DUNSPARCE_SKU), ("0", "2.06"), "goes as a price-only row")


def check_download_split_other_game(checks: Checks) -> None:
    """A download with `split_threshold` files a kept suggestion in a game no run of the send files
    under that game's own listed file (`runs.import_listed_name`). Dunsparce is in it once, at Add to
    Quantity 0 and price 2.06."""
    checks.note("")
    checks.note("DOWNLOAD, SPLIT, OTHER GAME — a download files a kept suggestion in its own game's listed file")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "download --split-threshold: Riftbound suggestion"):
            run_dir = _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _live_product_line(run, portal, DUNSPARCE_SKU, RIFTBOUND_PRODUCT_LINE)
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [run_dir.name],
                "download": True,
                "split_threshold": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"}],
            }), any_error=True)
            checks.ok(outcome[0] == "answered", "the download is answered, not refused", f"refused: {outcome[1]}")
            if outcome[0] == "answered":
                send = outcome[1]["send"]
                listed = runs.import_listed_name("riftbound")
                checks.ok(listed in send["files"], "the download writes the Riftbound listed file",
                          f"files written: {send['files']!r}")
                if listed in send["files"]:
                    body = send_routes.do_send_file(send["stamp"], listed).decode("utf-8")
                    held = [(row["Add to Quantity"], row["TCG Marketplace Price"])
                            for row in csv.DictReader(io.StringIO(body)) if tcgcsv.sku_cell(row) == DUNSPARCE_SKU]
                    checks.equal(held, [("0", "2.06")],
                                 "and that file holds Dunsparce once: Add to Quantity 0, at 2.06")


def check_send_past_cap_on_sent_price(checks: Checks) -> None:
    """The cap is measured on the price the press SENDS, after a drift re-price. Dunsparce is live at
    10.00 and drawn at 7.60; the server's fresh suggestion is 7.45. The drift (0.15) is inside
    `sendguard.drift_allowed`, so the press would send 7.45. The drawn 7.60 is 24% from 10.00, inside
    the 25% cap; the sent 7.45 is 25.5%, past it. The press is refused `suggestion_past_cap`, naming the
    7.45, and no row is written.
    """
    checks.note("")
    checks.note("SEND, PAST THE CAP AFTER DRIFT — the cap is measured on the price the press sends")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: drawn inside the cap, the sent price past it"):
            _one_copy_live(checks, portal, prices={DUNSPARCE_SKU: "10.00"})
            _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
            _market_reading(DUNSPARCE_SKU, "7.45", "7.90")
            try:
                send_routes.do_send({
                    "runs": [],
                    "confirm": True,
                    "prices": [{"sku": DUNSPARCE_SKU, "price": "7.60", "was": "10.00", "source": "suggested"}],
                })
                outcome = ("answered", [])
            except pipeline_routes.PipelineRefusal as caught:
                outcome = (caught.code, [row["price"] for row in (caught.data or {}).get("refused") or []])
            checks.equal(outcome[0], "suggestion_past_cap", "the press is refused suggestion_past_cap")
            checks.equal(outcome[1], ["7.45"],
                         "and the refusal measures the 7.45 the press would send, not the drawn 7.60")
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


def _emit_outcome(path) -> str:
    """`"refused"` when emit's `--reprice-live` reader raises `PriceRefused`, else `"answered"`."""
    try:
        cmd_emit._named_prices(path)
    except cmd_emit.PriceRefused:
        return "refused"
    return "answered"


def check_send_refuses_repeated_sku_price(checks: Checks) -> None:
    """A SKU named twice in `prices` is refused `prices_invalid`, and nothing is sent.

    The probe: Dunsparce twice, a suggestion at 11.00 and a typed 19.99, against a live 10.00. A
    dict built from the list keeps the row that came last, so the duplicate must be refused before
    any row is built. The route's reader refuses the list on its own, and the press names a run so
    the refusal is the duplicate's and not `runs_required`.
    """
    checks.note("")
    checks.note("SEND, REPEATED SKU — one SKU named twice in `prices` is refused before anything is written")
    probe = [
        {"sku": DUNSPARCE_SKU, "price": "11.00", "was": "10.00", "source": "suggested"},
        {"sku": DUNSPARCE_SKU, "price": "19.99", "was": "10.00"},
    ]
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: repeated SKU in prices"):
            run_dir = _one_copy_live(checks, portal, prices={DUNSPARCE_SKU: "10.00"})
            outcome = _outcome(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True, "prices": probe}))
            checks.equal(outcome, ("refused", "prices_invalid"),
                         "a SKU named twice in prices is refused prices_invalid")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")
            checks.equal(_outcome(lambda: send_routes._named_prices({"prices": probe})),
                         ("refused", "prices_invalid"),
                         "the route's own reader refuses the same list before any row is built")


def check_emit_repeated_sku_price_file(checks: Checks) -> None:
    """`cmd_emit._named_prices` reads the `--reprice-live` file. A SKU named twice in it raises
    `PriceRefused` and never keeps the last row: the same probe the route refuses."""
    checks.note("")
    checks.note("EMIT, REPEATED SKU — the --reprice-live file names one SKU once")
    with run_folder() as run, isolated_home(run):
        path = run / "reprice-live.json"
        path.write_text(json.dumps({"prices": [
            {"sku": DUNSPARCE_SKU, "price": "11.00", "was": "10.00", "source": "suggested"},
            {"sku": DUNSPARCE_SKU, "price": "19.99", "was": "10.00"},
        ]}), encoding="utf-8")
        with _case(checks, "emit: repeated SKU in the named prices file"):
            checks.equal(_emit_outcome(path), "refused",
                         "emit refuses a SKU named twice in the file: PriceRefused, not the last row")


def check_send_refuses_stale_readings(checks: Checks) -> None:
    """A zero-run send of kept suggestions refuses `readings_stale` when a reading behind one was
    written on an earlier US Central day. The D166 rule: an old export is refreshed first or the
    send says why, and a suggestion is only as fresh as the reading it is drawn from.

    Dunsparce's reading is yesterday's, Articuno's is today's. One stale reading refuses the press.
    """
    checks.note("")
    checks.note("SEND, STALE READINGS — a suggestion drawn from an earlier day's reading is refused")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: suggestion from an earlier day's reading"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _market_reading(DUNSPARCE_SKU, "2.06", "2.40", at=_yesterday_at())
            stored = Store().read().readings.entries[DUNSPARCE_SKU].at
            checks.ok(
                clock.central_day(datetime.fromtimestamp(stored, tz=timezone.utc)) < clock.central_day(clock.now()),
                "precondition: Dunsparce's reading was written on an earlier Central day",
            )
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [
                    {"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"},
                    {"sku": ARTICUNO_SKU, "price": "24.00", "was": "22.03", "source": "suggested"},
                ],
            }))
            checks.equal(outcome, ("refused", "readings_stale"),
                         "a zero-run send over a reading from an earlier day is refused readings_stale")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


def check_send_with_run_refuses_stale_readings(checks: Checks) -> None:
    """A send that NAMES A RUN refuses `readings_stale` too, the same as a zero-run send of the same row.

    `refresh_before_send` refreshes only the run's export, and that export is from today here, so it
    does nothing. It never touches the market reading behind a kept suggestion. Dunsparce's reading
    is yesterday's: the suggestion would go out at a price from an earlier day's market.
    """
    checks.note("")
    checks.note("SEND WITH A RUN, STALE READINGS — a suggestion from an earlier day's reading is refused")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send with a run: suggestion from an earlier day's reading"):
            run_dir = _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _market_reading(DUNSPARCE_SKU, "2.06", "2.40", at=_yesterday_at())
            stored = Store().read().readings.entries[DUNSPARCE_SKU].at
            checks.ok(
                clock.central_day(datetime.fromtimestamp(stored, tz=timezone.utc)) < clock.central_day(clock.now()),
                "precondition: Dunsparce's reading was written on an earlier Central day",
            )
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [run_dir.name],
                "confirm": True,
                "prices": [{"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"}],
            }))
            checks.equal(outcome, ("refused", "readings_stale"),
                         "a send naming a run, over a reading from an earlier day, is refused readings_stale")
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


def check_send_held_suggestion_left_out(checks: Checks) -> None:
    """A kept suggestion on a SKU that is live and held is left out of the send. Its held take-off
    is a row of its own (Add to Quantity below 0), and a price-only row beside it is what the
    "Duplicate TCGplayer Id" gate refuses. The answer names the SKU under its top-level `held` key.

    The press names a run: a held SKU in no selected game is `ungamed` and gets no take-off row, so
    only a run that files Dunsparce can show the collision.
    """
    checks.note("")
    checks.note("SEND, HELD — a kept suggestion on a held live SKU is left out and named under `held`")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send: kept suggestion on a held live SKU"):
            run_dir = _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _typed(DUNSPARCE_SKU, {"withheld": "keeping"})
            try:
                outcome = ("answered", send_routes.do_send({
                    "runs": [run_dir.name],
                    "confirm": True,
                    "prices": [{"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"}],
                }))
            except pipeline_routes.PipelineRefusal as caught:
                outcome = ("refused", f"{caught.code}: {caught}")
            checks.equal(outcome[0], "answered",
                         f"the press is answered, not refused (got {outcome[1] if outcome[0] == 'refused' else ''})")
            if outcome[0] == "answered":
                checks.ok(str(DUNSPARCE_SKU) in json.dumps(outcome[1].get("held"), sort_keys=True),
                          "the answer names Dunsparce under its top-level `held` key", repr(outcome[1].get("held")))
                checks.ok(_rows(portal).get(DUNSPARCE_SKU, ("", ""))[0] != "0",
                          "the suggestion's price-only row (Add to Quantity 0) is left out")
                checks.ok("suggested" not in [p["source"] for p in _postings(DUNSPARCE_SKU)],
                          "and no suggested posting is written")


def check_send_zero_run_only_held_suggestion_refuses_naming_it(checks: Checks) -> None:
    """A zero-run send whose only row is a kept suggestion on a held live SKU has nothing left to
    send. It stays refused `nothing_to_send`, but the refusal carries the same top-level `held` key
    the run path's answer carries, naming the SKU, and its sentence names the card (Dunsparce),
    not the SKU id. Nothing is sent and no posting is written."""
    checks.note("")
    checks.note("SEND, ZERO RUNS, ONLY A HELD SUGGESTION — refused nothing_to_send, with `held` and the card's name")
    with run_folder() as run, isolated_home(run), send_portal() as portal:
        _seed_sync()
        with _case(checks, "send, no runs: the only kept suggestion is on a held live SKU"):
            _one_copy_live(checks, portal)
            _seed_send_suggestions()
            _typed(DUNSPARCE_SKU, {"withheld": "keeping"})
            try:
                outcome = ("answered", send_routes.do_send({
                    "runs": [],
                    "confirm": True,
                    "prices": [{"sku": DUNSPARCE_SKU, "price": "2.06", "was": "2.50", "source": "suggested"}],
                }))
            except pipeline_routes.PipelineRefusal as caught:
                outcome = ("refused", caught)
            checks.equal(outcome[0] == "refused" and outcome[1].code, "nothing_to_send",
                         "the press is refused nothing_to_send")
            if outcome[0] == "refused":
                refusal = outcome[1]
                checks.ok(str(DUNSPARCE_SKU) in json.dumps((refusal.data or {}).get("held"), sort_keys=True),
                          "the refusal carries the SKU under its top-level `held` key", repr(refusal.data))
                checks.ok("Dunsparce" in str(refusal) and str(DUNSPARCE_SKU) not in str(refusal),
                          "and its sentence names the card, not the SKU id", str(refusal))
            checks.equal(_rows(portal), {}, "and TCGplayer receives no row")
            checks.equal(_postings(DUNSPARCE_SKU), [], "and no posting is written")


def check_worklist_no_runs_corrupt_corpus(checks: Checks) -> None:
    """With no run on disk and a corpus that cannot be read, the worklist says so: it answers
    `error: "corpus_unreadable"`, and its live row draws no suggestion from the default policy.

    The control: with no corpus file the default policy draws Dunsparce as suggested (unsold 60
    days, market 2.06 under its 2.50 ask). With the file corrupt, that suggestion must not appear
    quietly.
    """
    checks.note("")
    checks.note("WORKLIST, NO RUNS, CORPUS UNREADABLE — the screen is told, and no default suggestion is drawn")
    with run_folder() as run, isolated_home(run):
        _write_live("20260201-000000", _live_export_priced({DUNSPARCE_SKU: 1}, {DUNSPARCE_SKU: "2.50"}))
        _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
        _market_reading(DUNSPARCE_SKU, "2.06", "2.40")
        with _case(checks, "worklist, no runs: corpus unreadable"):
            checks.ok(not files.runs_dir().is_dir(), "precondition: no run is on disk, so the no-runs branch answers")
            control = _live_row(pipeline_routes.do_pipeline_worklist([]), DUNSPARCE_SKU) or {}
            checks.equal(control.get("group"), "suggested",
                         "control: with no corpus file, the default policy draws Dunsparce as suggested")
            files.prices_path().parent.mkdir(parents=True, exist_ok=True)
            files.prices_path().write_text("{ not json", encoding="utf-8")
            payload = pipeline_routes.do_pipeline_worklist([])
            row = _live_row(payload, DUNSPARCE_SKU) or {}
            checks.equal(payload.get("error"), "corpus_unreadable",
                         "the worklist names the corpus that cannot be read, for the screen to show")
            checks.ok(row.get("group") != "suggested" and row.get("source") != "Suggested",
                      "and draws no default-policy suggestion for Dunsparce", repr(row))


class _SpyImages:
    """Stands in for `stockimages.StockImages`: records each ask and answers a url naming it."""

    def __init__(self) -> None:
        self.asked: list = []

    def url_for(self, game, set_name, number):
        self.asked.append((game, set_name, number))
        return f"https://img.test/{game}/{set_name}/{number}"


#: What the market reading says about Articuno here. Every one differs from the live export row
#: and the run's table, so a build that joins a second source shows a different value.
_READING_FACTS = {"name": "Reading Articuno", "set_name": "Reading Set", "market": "30.00", "low": "28.00"}


def _articuno_reading() -> None:
    with Store().write() as snapshot:
        snapshot.readings.entries[ARTICUNO_SKU] = Reading(
            market=_READING_FACTS["market"],
            at=int(time.time()),
            source="t7-one-list-wire",
            kind="run",
            name=_READING_FACTS["name"],
            set_name=_READING_FACTS["set_name"],
            low=_READING_FACTS["low"],
        )


def _card_facts(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {key: row.get(key, "<absent>") for key in ("name", "set_name", "market", "low", "image_url")}


def check_worklist_live_listing_card_facts(checks: Checks) -> None:
    """Each live listing carries its card's `name`, `set_name`, `market`, `low` and `image_url`
    (the unsent rows' own names for the first, second and last), all from the one `readings` row
    the engine read for the SKU. The screen joins nothing else.

    The reading is a decoy: its name, set, market and lowest price differ from the live export
    row's and from the run's table. A build that reads any second source shows a different value.
    The thumbnail asks the resolver with the game and number off the export row (the reading holds
    neither) and the SET OF THE READING. Handed no resolver, `image_url` is present and `None`.
    Both branches of the route are pinned: with a run on disk, and with none.
    """
    checks.note("")
    checks.note("WORKLIST, CARD FACTS — a live listing's name, prices and thumbnail come from its one reading")
    expected = {
        "name": "Reading Articuno", "set_name": "Reading Set", "market": "30.00", "low": "28.00",
        "image_url": "https://img.test/pokemon/Reading Set/161/159",
    }
    live = _live_export_priced({ARTICUNO_SKU: 1}, {ARTICUNO_SKU: "25.00"})
    for label, with_run in (("with a run on disk", True), ("with no run on disk", False)):
        with run_folder() as run, isolated_home(run):
            _seed_sync()
            with _case(checks, f"worklist card facts, {label}"):
                if with_run:
                    seam_run(checks, WORKLIST_CARDS)
                _write_live("20260201-000000", live)
                _articuno_reading()
                _set_listing(ARTICUNO_SKU, first_seen_live=_noon(_day(60)))
                spy = _SpyImages()
                payload = pipeline_routes.do_pipeline_worklist([], images=spy)
                checks.equal(
                    _card_facts(_live_row(payload, ARTICUNO_SKU)),
                    expected,
                    f"{label}: the live row carries the reading's name, set, market and lowest "
                    "price, and the thumbnail the resolver gave for them",
                )
                checks.ok(
                    ("pokemon", "Reading Set", "161/159") in spy.asked,
                    f"{label}: the resolver is asked with the card's game and number and the reading's set",
                    repr(spy.asked),
                )
                bare = _live_row(pipeline_routes.do_pipeline_worklist([]), ARTICUNO_SKU) or {}
                checks.equal(
                    (bare.get("image_url", "<absent>"), bare.get("name", "<absent>")),
                    (None, "Reading Articuno"),
                    f"{label}: with no resolver the row still has `image_url`, as None, and the same name",
                )


def _group_of(payload: dict, sku: str) -> str:
    for row in payload.get("skus") or []:
        if row.get("sku") == sku:
            return row.get("group", "<absent>")
    return "<no row>"


def check_worklist_new_copy_group(checks: Checks) -> None:
    """Each new (unsent) copy on the worklist carries `group`: `needs_you` or `at_rule`.

    The server rule is the engine's own for a listing that is not live (`suggest.review`): no
    market price, or a rule price at or above `value_line`, is `needs_you`. Anything else is
    `at_rule`. Pinned on Articuno, whose rule price is its market, 22.03:
      value line 25 (the default)   at_rule, with Dunsparce (2.06) beside it
      value line 22.03              needs_you: AT the line counts
      value line 22.04              at_rule
    and on a card with no market price, which is `needs_you` whatever the line.

    DIFFERENCES FROM TODAY'S SCREEN RULE (`takeArrival` and `flagOf` in `app/src/Pricing.tsx`):
    the screen flags a market of $5 or more (`WORTH_A_LOOK`); the server's line is the owner's
    `value_line` on the RULE price (25 by default). The screen also flags a typed price 25% off
    market and skips held, locked and nothing-to-add rows; the server cannot see an unsaved typed
    price, so those stay the screen's.
    """
    checks.note("")
    checks.note("WORKLIST, NEW COPIES — each carries a server-computed group")
    cards = WORKLIST_CARDS + [(3, 2, "Dunsparce", "120", "normal")]

    def groups(line: Optional[str], *, market=None) -> dict:
        with run_folder() as run, isolated_home(run):
            _seed_sync()
            seam_run(checks, cards, market=market)
            if line is not None:
                book = corpus.Corpus.read()
                book.value_line = line
                book.write()
            payload = pipeline_routes.do_pipeline_worklist([])
            return {"articuno": _group_of(payload, ARTICUNO_SKU), "dunsparce": _group_of(payload, DUNSPARCE_SKU)}

    with _case(checks, "worklist group: default value line"):
        checks.equal(groups(None), {"articuno": "at_rule", "dunsparce": "at_rule"},
                     "default line 25: a 22.03 card and a 2.06 card are both going at the rule")
    with _case(checks, "worklist group: at the line"):
        checks.equal(groups("22.03"), {"articuno": "needs_you", "dunsparce": "at_rule"},
                     "a rule price AT the value line needs you; the cheaper card does not")
    with _case(checks, "worklist group: just under the line"):
        checks.equal(groups("22.04"), {"articuno": "at_rule", "dunsparce": "at_rule"},
                     "a cent under the line is going at the rule")
    with _case(checks, "worklist group: no market price"):
        checks.equal(groups(None, market={DUNSPARCE_SKU: ""}), {"articuno": "at_rule", "dunsparce": "needs_you"},
                     "a card with no market price needs you, whatever the line")


def check_worklist_group_follows_rule_price(checks: Checks) -> None:
    """A new copy's group is decided from the export's own cells, the ones `SkuMatch.list_price`
    reads, so the group and the `rule_price` the screen shows come from one figure.

    The `snap` cells are two-decimal renderings of cells that are four-decimal in the fixtures.
    Low 22.7240 on markup:10 prices at 25.00 (at the value line); the rendered 22.72 prices at
    24.99. Low 0.0040 prices at the floor, 0.49; the rendered 0.00 reads as no market price.
    A row with no `snap`, or a `snap` with no `low`, is read as blank and never raises.
    """
    checks.note("")
    checks.note("WORKLIST, NEW COPIES — the group follows the rule price")
    market, low = tcgcsv.MARKET_PRICE_COLUMN, tcgcsv.LOW_PRICE_COLUMN
    policy = {"basis": "low", "rule": "markup:10"}

    def group(cells: dict, snap=None, *, basis_policy=policy) -> str:
        row = {"sku": "S", "row": cells}
        if snap is not None:
            row["snap"] = snap
        return worklist.new_copy_groups([row], basis_policy, "2026-11-02")["S"]

    with _case(checks, "worklist group: rule price from the raw cell"):
        raw = tcgcsv.parse_price("22.7240")
        checks.equal(str(pricing.list_price(raw, "markup:10", pricing.FLOOR)), "25.00",
                     "the rule price the screen shows for low 22.7240 is 25.00")
        checks.equal(group({market: "30.0000", low: "22.7240"}, {"market": "30.00", "low": "22.72"}),
                     "needs_you", "25.00 is at the value line, so the group says needs_you")
    with _case(checks, "worklist group: a sub-cent low is still a price"):
        checks.equal(group({market: "1.0000", low: "0.0040"}, {"market": "1.00", "low": "0.00"}),
                     "at_rule", "low 0.0040 prices at the floor 0.49, so the group says at_rule")
    with _case(checks, "worklist group: row with no snap"):
        checks.equal(group({market: "5.0000"}, basis_policy={}), "at_rule",
                     "a row with cells and no snap is read from its cells")
        checks.equal(group({market: "5.0000"}, {"market": "5.00"}), "needs_you",
                     "a snap with no low, on the low basis, is no market price")
    with _case(checks, "worklist group: row with no cells"):
        checks.equal(worklist.new_copy_groups([{"sku": "S"}], {}, "2026-11-02"), {"S": "needs_you"},
                     "a row with neither cells nor snap is no market price")


def check_live_capped_reason_names_the_cap(checks: Checks) -> None:
    """A live listing whose suggested move passes the owner's limit lands in `needs_you`, and its
    reason ends by naming that limit: "; capped at your 25%".

    Dunsparce asks 3.00 at market 2.06, unsold 60 days, so the engine's price is 2.06: a 31% drop,
    over the default 25% limit and far under the 25-dollar value line, so only the cap holds it back.
    Only the ENDING is pinned, not the sentence before it. A second case sets the owner's limit to
    0.20: the ending then names 20%, so the figure is the owner's setting and not a constant.
    """
    checks.note("")
    checks.note("WORKLIST, CAPPED LIVE SUGGESTION — the reason names the owner's limit")
    for label, limit, ending in (
        ("default limit", None, "; capped at your 25%"),
        ("limit 0.20", "0.20", "; capped at your 20%"),
    ):
        with run_folder() as run, isolated_home(run), _case(checks, f"worklist capped reason: {label}"):
            _write_live("20260201-000000", _live_export_priced({DUNSPARCE_SKU: 1}, {DUNSPARCE_SKU: "3.00"}))
            _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
            _market_reading(DUNSPARCE_SKU, "2.06", "2.40")
            if limit is not None:
                book = corpus.Corpus.read()
                book.limit = limit
                book.write()
            row = _live_row(pipeline_routes.do_pipeline_worklist([]), DUNSPARCE_SKU) or {}
            checks.equal(row.get("group"), "needs_you",
                         f"{label}: a suggested move past the limit is held for the owner")
            checks.ok(str(row.get("reason")).endswith(ending),
                      f"{label}: the reason ends {ending!r}", repr(row.get("reason")))


def check_markdown_table_carries_group(checks: Checks) -> None:
    """`do_markdown_table` rows carry the SAME `group` `/pipeline/pricing`'s `live` row gives the
    same SKU, so one listing has one group on both screens (`_live_wire` is the one source).

    Three live SKUs, one shape each, and a fourth the survey saw but the newest live export lacks:
      Articuno   unsold 60 days, 13% over market: a trigger fires, `suggested`.
      Dunsparce  asks 3.00 at market 2.06: the move passes the owner's limit, `needs_you`.
      Reverse    5 days live, asking at market: nothing fires, `at_rule`.
      Gone       in the survey, not in the live export: no `group`.
    The survey's own export cells are set so the old rule (a new copy's group, off those cells) reads
    `at_rule` for Articuno and Dunsparce, which the wire does not. A `prices.json` that cannot be
    read leaves `group` absent on every row, and the table still answers: the owner's settings decide
    the group, and a default policy would guess.
    """
    checks.note("")
    checks.note("MARKDOWN TABLE — each row carries the live wire's group")
    live = {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "2.06", DUNSPARCE_REVERSE_SKU: "2.60"}
    asking = {ARTICUNO_SKU: "25.00", DUNSPARCE_SKU: "3.00", DUNSPARCE_REVERSE_SKU: "2.60"}
    cells = {sku: {tcgcsv.MARKET_PRICE_COLUMN: market + "00"} for sku, market in live.items()}

    def seed() -> None:
        _write_live("20260201-000000", _live_export_priced({sku: 1 for sku in live}, asking))
        for sku, market in live.items():
            _market_reading(sku, market, "2.40" if sku == DUNSPARCE_SKU else None)
        _set_listing(ARTICUNO_SKU, first_seen_live=_noon(_day(60)))
        _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(60)))
        _set_listing(DUNSPARCE_REVERSE_SKU, first_seen_live=_noon(_day(5)))

    def table_groups() -> dict:
        _write_survey(0, (*live, "GONE"), cells)
        table = pipeline_routes.do_markdown_table(TABLE_STAMP)
        return {row["sku"]: row.get("group", "<absent>") for row in table["skus"]}

    with run_folder() as run, isolated_home(run), _case(checks, "markdown table group: readable corpus"):
        seed()
        wire = {sku: (_live_row(pipeline_routes.do_pipeline_worklist([]), sku) or {}).get("group", "<no row>")
                for sku in live}
        checks.equal(wire, {ARTICUNO_SKU: "suggested", DUNSPARCE_SKU: "needs_you", DUNSPARCE_REVERSE_SKU: "at_rule"},
                     "precondition: the live wire fires a trigger on two SKUs and leaves the third at the rule")
        checks.equal(table_groups(), {**wire, "GONE": "<absent>"},
                     "each markdown row's group is the live wire's for that SKU; a SKU the live export lacks has none")
    with run_folder() as run, isolated_home(run), _case(checks, "markdown table group: corpus unreadable"):
        seed()
        files.prices_path().parent.mkdir(parents=True, exist_ok=True)
        files.prices_path().write_text("{ not json", encoding="utf-8")
        checks.equal(table_groups(), {**dict.fromkeys(live, "<absent>"), "GONE": "<absent>"},
                     "an unreadable corpus leaves `group` absent on every row, and the rows still come")


def check_live_no_market_needs_you(checks: Checks) -> None:
    """A live listing with copies and no market price is `needs_you` on `/pipeline/pricing`'s `live`
    wire: the spec's first group is "No market price, a move past the cap, or a card at or above the
    value line", and it holds for a listing that is live as much as for a new copy.

    One Dunsparce listing, first seen 5 days ago so no trigger fires, asking 2.60, in four shapes:
    a blank market, a zero market, no reading row at all (each `needs_you`), and a market of 2.60,
    which stays `at_rule` and keeps the rule honest about the other direction.
    """
    checks.note("")
    checks.note("WORKLIST, LIVE LISTING WITH NO MARKET PRICE — needs you")
    for label, market, expected in (
        ("blank market", "", "needs_you"),
        ("zero market", "0.00", "needs_you"),
        ("no reading", None, "needs_you"),
        ("market present", "2.60", "at_rule"),
    ):
        with run_folder() as run, isolated_home(run), _case(checks, f"worklist no market: {label}"):
            _write_live("20260201-000000", _live_export_priced({DUNSPARCE_SKU: 1}, {DUNSPARCE_SKU: "2.60"}))
            _set_listing(DUNSPARCE_SKU, first_seen_live=_noon(_day(5)))
            if market is not None:
                _market_reading(DUNSPARCE_SKU, market)
            row = _live_row(pipeline_routes.do_pipeline_worklist([]), DUNSPARCE_SKU) or {}
            checks.equal(row.get("group", "<no row>"), expected,
                         f"{label}: a live listing with copies is filed under {expected}")
def check_send_typed_price_with_no_new_copy(checks: Checks) -> None:
    """A typed price on a live listing, sent with no new copy, is answered and goes out under the
    checks a kept suggestion meets (queue item 112: a typed live price with no new copy sends as a
    price-only row): a reading from today
    (`readings_stale`) and a price within the cap of the live price (`suggestion_past_cap`, the
    one cap check).

    Articuno is live at 22.03. Three presses, each its own home:
      24.00, reading from today    answered: a price-only row, posted "emit-price", replacing 22.03
      24.00, reading from yesterday  refused readings_stale; no row, no posting
      40.00, reading from today    refused suggestion_past_cap (82% from 22.03); no row, no posting
    """
    checks.note("")
    checks.note("SEND, TYPED PRICE ONLY — a live listing's typed price needs no new copy, and meets the same checks")

    def press(price: str, *, reading_at: Optional[int]):
        with run_folder() as run, isolated_home(run), send_portal() as portal:
            _seed_sync()
            _one_copy_live(checks, portal)
            _market_reading(ARTICUNO_SKU, "22.03", "22.98", at=reading_at)
            _typed(ARTICUNO_SKU, price)
            outcome = _outcome(lambda: send_routes.do_send({
                "runs": [],
                "confirm": True,
                "prices": [{"sku": ARTICUNO_SKU, "price": price, "was": "22.03"}],
            }))
            return outcome, _rows(portal), [(p["price"], p["replaced"], p["source"]) for p in _postings(ARTICUNO_SKU)]

    with _case(checks, "send: typed price, no new copy, fresh reading"):
        outcome, rows, postings = press("24.00", reading_at=None)
        checks.equal(outcome[0] if outcome[0] == "refused" else "answered", "answered",
                     f"a typed price alone is answered, not refused (got {outcome[1] if outcome[0] == 'refused' else ''})")
        checks.equal(rows, {ARTICUNO_SKU: ("0", "24.00")}, "it goes out as a price-only row at the typed price")
        checks.equal(postings, [("22.03", None, "emit"), ("24.00", "22.03", "emit-price")],
                     "and posts as \"emit-price\", naming the 22.03 it replaced")
    with _case(checks, "send: typed price, no new copy, reading from yesterday"):
        outcome, rows, postings = press("24.00", reading_at=_yesterday_at())
        checks.equal(outcome, ("refused", "readings_stale"),
                     "a typed price over a reading from an earlier day is refused readings_stale")
        checks.equal((rows, postings), ({}, [("22.03", None, "emit")]), "and nothing reaches TCGplayer or the postings")
    with _case(checks, "send: typed price, no new copy, past the cap"):
        outcome, rows, postings = press("40.00", reading_at=None)
        checks.equal(outcome, ("refused", "suggestion_past_cap"),
                     "a typed price more than the cap from the live price is refused suggestion_past_cap")
        checks.equal((rows, postings), ({}, [("22.03", None, "emit")]), "and nothing reaches TCGplayer or the postings")


CHECKS = (
    check_worklist_carries_live_listings,
    check_worklist_without_runs_reads_newest_export,
    check_worklist_market_on_listing_day,
    check_send_takes_suggestions_with_no_run,
    check_send_suggestion_beside_typed_price,
    check_send_refuses_suggestion_past_cap,
    check_send_past_cap_needs_a_tick,
    check_send_suggestion_changed,
    check_send_suggestion_drift,
    check_send_suggestion_other_game,
    check_download_split_other_game,
    check_send_past_cap_on_sent_price,
    check_send_empty_runs_without_prices_refused,
    check_product_history_asking_postings,
    check_send_refuses_repeated_sku_price,
    check_emit_repeated_sku_price_file,
    check_send_refuses_stale_readings,
    check_send_with_run_refuses_stale_readings,
    check_send_held_suggestion_left_out,
    check_send_zero_run_only_held_suggestion_refuses_naming_it,
    check_worklist_no_runs_corrupt_corpus,
    check_worklist_live_listing_card_facts,
    check_worklist_new_copy_group,
    check_worklist_group_follows_rule_price,
    check_live_capped_reason_names_the_cap,
    check_markdown_table_carries_group,
    check_live_no_market_needs_you,
    check_send_typed_price_with_no_new_copy,
)


if __name__ == "__main__":
    # `PYTHONPATH=<repo root> python3 harness/tests/t7/one_list_wire.py`: this group's checks alone, under
    # the one runner's rules (`hermetic`, refused network). The exit code is the verdict.
    import sys

    from harness.tests import t7_store_and_seams

    result = t7_store_and_seams.run(order=lambda _: list(CHECKS))
    print(result.detail)
    sys.exit(0 if result.passed else 1)
