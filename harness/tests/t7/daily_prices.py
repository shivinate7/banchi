"""T7 group: the daily TCGCSV read, `pipeline/dailyprices.py` and `store/dailyprices.py` (D88, D219).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in the order
`CHECK_ORDER` runs them. WHEN THE DAILY JOB CALLS THE READ is `harness/tests/t7/price_moves.py`'s
`check_daily_job_reads_daily_prices_after_a_good_refresh`; this group is the read itself.

NO NETWORK CALL. `FakeTcgcsv` is the `pricehistory.Fetcher` shape (url in, payload out) and serves the payloads
TCGCSV serves. It goes through the REAL `pricehistory.Market`, so URL composition and `parse_prices` are the
module's own; the first check proves the fake is wired right and passes on any checkout. Every other check
imports the build inside itself, so a checkout without it fails each check with its own sentence and the rest of
T7 still runs.

THE SEAMS (a builder follows these names):

  pipeline/dailyprices.py
    run_pass(fetch=None, *, now=None, user_agent=pricehistory.USER_AGENT) -> dict
      fetch  url -> payload. None means `pricehistory.fetch_json(url, user_agent=user_agent)`, looked up when it
             runs: the one HTTP client, never a second.
      now    an aware datetime, default `store.clock.now()`. The day is `store.clock.central_day(now)` as an ISO
             date. A row's `at` is `int(now.timestamp())`.
      It builds its own `pricehistory.Market` with no cache directory (`PRICE_TTL_SECONDS` is seven days: a cached
      file would serve yesterday's prices as today's). It asks `groups(89)` and `prices(89, group)` for each group.
      It asks for no products and no categories. A group whose prices raise `pricehistory.PriceHistoryError` is
      named in `failed` and the other groups go on. It writes through `Store().write()` and never deletes.
      It answers {"day": ISO date, "skipped": bool, "rows": rows written by THIS call,
      "failed": {group_id (int): message (str)}}.
      It skips (nothing fetched, nothing written, "skipped": True) a day that is finished: a pass that ended with no
      failed group. A same-day retry asks again only for the prices of the groups not yet saved. Whether it asks
      for the group list again is not pinned.
  store/dailyprices.py
    `DailyPrice(product_id: int, sub_type: str, day: str, market, low, mid, high, direct_low, group_id: int, at: int)`,
    the five prices `Optional[str]` as the source gives them (`str` of the number, None for null or absent).
    `DailyPrices` holds `.entries`, a `Rows` of `DailyPrice`, table `daily_prices`, key (product_id, sub_type, day).
    The snapshot attribute is `Store().read().daily_prices`.
  scripts/price-refresh-daily.py
    after a good refresh, `from pipeline import dailyprices` then `dailyprices.run_pass(user_agent=...)`.

Temp files follow the run-folder standard (test-temp-standard): each check opens one `<pid>-<UUID>` folder from
`harness/tests/home.py:run_folder`, the store of each case lives inside it (`isolated_home` takes its folder from
`tempfile.tempdir`, which `in_run_folder` points there), and its exit removes it. The sweep of old sibling folders
is proved once, for the helper, by `t1_results.check_run_folder_sweeps_old_siblings_and_keeps_new_ones`.
"""

from __future__ import annotations

import functools
import re
import tempfile
from datetime import datetime, timedelta
from unittest import mock

from harness.tests import Checks
from harness.tests.home import isolated_home, run_folder
from pipeline import pricehistory
from store import clock
from store.session import Store

BASE = pricehistory.CATALOG_HOST + "/tcgplayer/89"

#: One US Central day, two moments in it. LATE is 04:30 UTC on the NEXT UTC date: a day read off UTC says Oct 28.
MIDDAY = datetime(2026, 10, 27, 13, 0, tzinfo=clock.CENTRAL)
LATE = datetime(2026, 10, 27, 23, 30, tzinfo=clock.CENTRAL)
NEXT_DAY = MIDDAY + timedelta(days=1)
DAY, NEXT = "2026-10-27", "2026-10-28"

#: Served order matters: the group that fails in the retry check comes FIRST, so a loop that stops at the first error fails.
GROUPS = [(102, "Spiritforged"), (101, "Origins")]


def source(product_id, sub_type, omit=(), **prices):
    """One row as TCGCSV serves it: JSON numbers, `null`, or a key left out. `prices` is `market`, `low`, `mid`,
    `high`, `direct`, each defaulting to null."""
    names = {"market": "marketPrice", "low": "lowPrice", "mid": "midPrice", "high": "highPrice", "direct": "directLowPrice"}
    row = {"productId": product_id, "subTypeName": sub_type, **{names[key]: prices.get(key) for key in names}}
    for key in omit:
        del row[key]
    return row


# Prices are non-zero and have no trailing zero, so their text is the same however a builder turns a number into text
# without reformatting it: "1.5" is as given, "1.50" is not.
DAY1 = {
    101: [
        source(1001, "Normal", low=0.05, mid=0.2, high=1.5, market=0.25),
        source(1001, "Foil", low=1.5, mid=3.25, high=12.75, market=2.5, direct=2.75),
        source(1002, "Normal", low=0.07, mid=0.12, high=0.9, market=None, omit=("directLowPrice",)),
    ],
    102: [source(2001, "Normal", low=3.5, mid=4.5, high=9.99, market=4.75, direct=4.25)],
}
EXPECT1 = {
    (1001, "Normal"): dict(group_id=101, market="0.25", low="0.05", mid="0.2", high="1.5", direct_low=None),
    (1001, "Foil"): dict(group_id=101, market="2.5", low="1.5", mid="3.25", high="12.75", direct_low="2.75"),
    (1002, "Normal"): dict(group_id=101, market=None, low="0.07", mid="0.12", high="0.9", direct_low=None),
    (2001, "Normal"): dict(group_id=102, market="4.75", low="3.5", mid="4.5", high="9.99", direct_low="4.25"),
}
# The next day: one price moved, one product is new, the Foil and 1002 are gone from the source, 2001 moved.
DAY2 = {
    101: [
        source(1001, "Normal", low=0.06, mid=0.22, high=1.4, market=0.3),
        source(1003, "Normal", low=0.5, mid=0.75, high=2.25, market=0.6),
    ],
    102: [source(2001, "Normal", low=3.75, mid=4.95, high=10.5, market=5.25)],
}
EXPECT2 = {
    (1001, "Normal"): dict(group_id=101, market="0.3", low="0.06", mid="0.22", high="1.4", direct_low=None),
    (1003, "Normal"): dict(group_id=101, market="0.6", low="0.5", mid="0.75", high="2.25", direct_low=None),
    (2001, "Normal"): dict(group_id=102, market="5.25", low="3.75", mid="4.95", high="10.5", direct_low=None),
}


class FakeTcgcsv:
    """The host, as a `pricehistory.Fetcher`. `fail` is the set of group ids whose prices answer an HTTP 500; clear it
    to mend the host. `urls` is every URL asked, in order. It answers the categories list, any category's group list and
    any group's products as well, so a pass that asks for more than it needs fails the request-list assertions below
    with a plain sentence, never with an error from the fake."""

    def __init__(self, prices, fail=()):
        self.prices = prices
        self.fail = set(fail)
        self.urls = []

    def __call__(self, url, *_args, **_kwargs):
        self.urls.append(url)
        path = url[len(pricehistory.CATALOG_HOST):]
        payload = {"success": True, "errors": []}
        if path == "/tcgplayer/categories":
            return {**payload, "results": [{"categoryId": 89, "name": "Riftbound"}]}
        if re.fullmatch(r"/tcgplayer/\d+/groups", path):
            return {**payload, "results": [{"groupId": g, "name": n} for g, n in GROUPS]}
        found = re.fullmatch(r"/tcgplayer/\d+/(\d+)/(prices|products)", path)
        if found and found.group(2) == "products":
            return {**payload, "results": []}
        if found and int(found.group(1)) in self.prices:
            group = int(found.group(1))
            if group in self.fail:
                raise pricehistory.Unreachable("The price service answered 'internal server error'. Try again in a moment.")
            return {**payload, "results": self.prices[group]}
        raise pricehistory.Unreachable("The price service answered 'not found'. Try again in a moment.")


def in_run_folder(fn):
    """The check runs in its own run folder, with no pause between requests and every store inside the folder. One that
    raises reads as one failed line with its sentence, never as a traceback that hides the rest of T7 (the build may
    not exist yet). A shape like `backup.robust`, which is not reused: that one hands its check a folder through a
    global, and this one has to point `tempfile.tempdir` at it for `isolated_home`."""
    @functools.wraps(fn)
    def run(checks: Checks) -> None:
        saved = tempfile.tempdir
        with run_folder() as folder, mock.patch("time.sleep"):
            tempfile.tempdir = str(folder)
            try:
                fn(checks)
            except Exception as exc:  # noqa: BLE001 any failure is the red this exists to show
                checks.ok(False, "%s ran to its end" % fn.__name__, "%s: %s" % (type(exc).__name__, exc))
            finally:
                tempfile.tempdir = saved
    return run


def load(checks: Checks):
    """`pipeline.dailyprices`, or None after one failed check that says it is not built."""
    try:
        from pipeline import dailyprices
    except ImportError as exc:
        checks.ok(False, "pipeline/dailyprices.py exists", "%s: %s" % (type(exc).__name__, exc))
        return None
    return dailyprices if checks.ok(hasattr(dailyprices, "run_pass"), "pipeline.dailyprices has run_pass") else None


def run(checks: Checks, module, fetch, when, label, **kwargs):
    """One pass at `when`: its answer, or None after one failed check that carries the exception."""
    try:
        return module.run_pass(fetch, now=when, **kwargs)
    except Exception as exc:  # noqa: BLE001 a crash is a failed case with its own sentence
        checks.ok(False, "%s: the pass ran" % label, "%s: %s" % (type(exc).__name__, exc))
        return None


def table():
    """Every row the store holds, read through a fresh snapshot: `{(product_id, sub_type, day): row as a dict}`."""
    return {(r.product_id, r.sub_type, r.day): r._asdict() for r in Store().read().daily_prices.entries.values()}


def day_of(rows, day):
    """One day's rows as `{(product_id, sub_type): the five prices and the group}`, the shape `EXPECT1` is written in."""
    wanted = ("group_id", "market", "low", "mid", "high", "direct_low")
    return {key[:2]: {name: row[name] for name in wanted} for key, row in rows.items() if key[2] == day}


@in_run_folder
def check_daily_prices_fake_goes_through_the_real_market(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES FIXTURE — the fake is read by the real Market, so the checks below test the build and not the fake")
    fake = FakeTcgcsv(DAY1)
    market = pricehistory.Market(fetcher=fake, courtesy_delay=0)
    checks.equal(sorted(row["groupId"] for row in market.groups(89).values()), [101, 102], "groups(89) lists both groups")
    prices = market.prices(89, 101)
    checks.equal(
        {key: (None if p.market is None else str(p.market)) for key, p in prices.items()},
        {(1001, "Normal"): "0.25", (1001, "Foil"): "2.5", (1002, "Normal"): None},
        "prices(89, 101) parses a number, a Foil beside its Normal, and a null",
    )
    checks.equal(sorted(fake.urls), [BASE + "/101/prices", BASE + "/groups"], "the two calls asked these two URLs")


@in_run_folder
def check_daily_prices_one_pass_writes_every_row(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 1 — one pass writes one row per product and sub type for today's US Central day, values as given")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1)
        result = run(checks, module, fake, LATE, "one pass")
        if result is None:
            return
        rows = table()
        checks.equal(
            (result.get("day"), result.get("skipped"), result.get("rows"), result.get("failed")),
            (DAY, False, 4, {}),
            "the answer: Central day %s (UTC says %s), not skipped, 4 rows, no failed group" % (DAY, NEXT),
        )
        checks.equal(sorted(rows), sorted(key + (DAY,) for key in EXPECT1), "one row per product and sub type, all on the Central day")
        checks.equal(day_of(rows, DAY), EXPECT1, "every price as given, null where the source gives null or leaves the key out, the group id kept")
        checks.equal({row["at"] for row in rows.values()}, {int(LATE.timestamp())}, "every row carries the second the pass read")


@in_run_folder
def check_daily_prices_same_day_pass_is_skipped(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 2 — a second pass on the same day fetches nothing and writes nothing")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1)
        first = run(checks, module, fake, MIDDAY, "first pass")
        if first is None:
            return
        checks.equal((first.get("skipped"), first.get("rows")), (False, 4), "the first pass of the day reads and writes 4 rows")
        before = table()
        fake.urls.clear()
        # LATE is the same Central day as MIDDAY and the next UTC day: a guard keyed on the UTC date would read again.
        second = run(checks, module, fake, LATE, "second pass")
        if second is None:
            return
        checks.equal((second.get("skipped"), second.get("rows"), second.get("failed")), (True, 0, {}), "the answer says skipped, 0 rows")
        checks.equal(fake.urls, [], "the host is asked for nothing, not even the group list")
        checks.equal(table(), before, "every row is as it was, `at` included")


@in_run_folder
def check_daily_prices_next_day_adds_rows_and_keeps_old_ones(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 3 — the next day adds rows and keeps the old ones, whatever the source stopped listing")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1)
        if run(checks, module, fake, MIDDAY, "day one") is None:
            return
        day_one = table()
        fake.prices = DAY2
        fake.urls.clear()
        result = run(checks, module, fake, NEXT_DAY, "day two")
        if result is None:
            return
        rows = table()
        checks.equal((result.get("day"), result.get("skipped"), result.get("rows")), (NEXT, False, 3), "day two: its own day, not skipped, 3 rows")
        checks.equal(
            sorted(url for url in fake.urls if url.endswith("/prices")), [BASE + "/101/prices", BASE + "/102/prices"],
            "day two asked for every group's file again: a week-long cache would hand back day one's",
        )
        checks.equal(day_of(rows, NEXT), EXPECT2, "day two holds day two's prices, as given")
        checks.equal({row["at"] for key, row in rows.items() if key[2] == NEXT}, {int(NEXT_DAY.timestamp())}, "day two's rows carry day two's second")
        checks.equal({key: row for key, row in rows.items() if key[2] == DAY}, day_one, "day one's rows are untouched, `at` included")
        checks.ok((1001, "Foil", DAY) in rows and (1002, "Normal", DAY) in rows, "a product the source stopped listing keeps its day-one row")
        checks.equal(len(rows), len(day_one) + 3, "the table holds 4 + 3 rows: nothing deleted, nothing doubled")


@in_run_folder
def check_daily_prices_failing_group_is_named_and_retried(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 4 — a failing group is named, the others go on, the day stays open, the retry asks for the failed group only")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1, fail={102})
        first = run(checks, module, fake, MIDDAY, "first pass")
        if first is None:
            return
        failed = first.get("failed") or {}
        checks.equal(set(failed), {102}, "the answer names group 102, the one that failed, and no other")
        checks.ok(all(isinstance(message, str) and message for message in failed.values()), "the answer carries a sentence for it", str(failed))
        checks.equal((first.get("skipped"), first.get("rows")), (False, 3), "the pass is not skipped and wrote the 3 rows of group 101, which was served after the failing one")
        checks.equal(sorted(table()), sorted(key + (DAY,) for key in EXPECT1 if EXPECT1[key]["group_id"] == 101), "only group 101's rows are in the table")
        fake.fail.clear()
        fake.urls.clear()
        retry = run(checks, module, fake, LATE, "retry")
        if retry is None:
            return
        checks.equal((retry.get("skipped"), retry.get("rows"), retry.get("failed")), (False, 1, {}), "the same-day retry is not skipped: it wrote the 1 row that was missing, with no failure")
        checks.equal(sorted(url for url in fake.urls if url.endswith("/prices")), [BASE + "/102/prices"], "the retry asked for the failed group's file and not for group 101's again")
        checks.equal(day_of(table(), DAY), EXPECT1, "the day is whole now: all 4 rows, none doubled")
        fake.urls.clear()
        third = run(checks, module, fake, LATE, "third pass")
        if third is None:
            return
        checks.equal((third.get("skipped"), third.get("rows"), fake.urls), (True, 0, []), "a clean pass finishes the day: the third pass fetches nothing")


@in_run_folder
def check_daily_prices_only_category_89_and_the_request_budget(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 5 — only category 89: its group list and one prices file per group, nothing else, nothing twice")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1)
        if run(checks, module, fake, MIDDAY, "the pass") is None:
            return
        categories = {url.split("/tcgplayer/")[1].split("/")[0] for url in fake.urls if "/tcgplayer/" in url}
        checks.equal(categories, {"89"}, "every URL is under /tcgplayer/89/ (Riftbound): no categories list, no other category")
        checks.equal(
            sorted(fake.urls), sorted([BASE + "/groups", BASE + "/101/prices", BASE + "/102/prices"]),
            "exactly the group list and one prices file per group, no products call: that is the day's request budget",
        )
        checks.equal(len(fake.urls), len(set(fake.urls)), "no file is asked for twice in a pass")


@in_run_folder
def check_daily_prices_site_rules_user_agent_and_pause(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES SITE RULES — the one HTTP client with the named User-Agent, a pause of at least 100 ms between requests")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(DAY1)
        agents, slept = [], []

        def fetch_json(url, timeout=None, user_agent=None):
            agents.append(user_agent)
            return fake(url)

        no_second_client = mock.patch("urllib.request.urlopen", side_effect=AssertionError("a second HTTP client was used"))
        with mock.patch.object(pricehistory, "fetch_json", fetch_json), mock.patch("time.sleep", slept.append), no_second_client:
            try:
                result = module.run_pass(now=MIDDAY, user_agent="banchi-test/9.9")
            except Exception as exc:  # noqa: BLE001 a crash is a failed case with its own sentence
                checks.ok(False, "the pass ran with no fetch given", "%s: %s" % (type(exc).__name__, exc))
                return
        checks.equal(result.get("rows"), 4, "with no fetch given the pass reads through `pricehistory.fetch_json`: 4 rows")
        checks.equal(set(agents), {"banchi-test/9.9"}, "every request carries the User-Agent it was handed, and there are %d of them" % len(agents))
        checks.ok(
            len(slept) >= len(fake.urls) - 1 and all(seconds >= 0.1 for seconds in slept),
            "a pause of at least 0.1 s sits between consecutive requests", "%d requests, pauses %s" % (len(fake.urls), slept),
        )


CHECKS = (
    check_daily_prices_fake_goes_through_the_real_market,
    check_daily_prices_one_pass_writes_every_row,
    check_daily_prices_same_day_pass_is_skipped,
    check_daily_prices_next_day_adds_rows_and_keeps_old_ones,
    check_daily_prices_failing_group_is_named_and_retried,
    check_daily_prices_only_category_89_and_the_request_budget,
    check_daily_prices_site_rules_user_agent_and_pause,
)
