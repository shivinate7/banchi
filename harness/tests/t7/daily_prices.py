"""T7 group: the daily TCGCSV read, `pipeline/dailyprices.py` and `store/dailyprices.py` (D88, D219).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in the order
`CHECK_ORDER` runs them. WHEN THE DAILY JOB CALLS THE READ is `harness/tests/t7/price_moves.py`'s
`check_daily_job_reads_daily_prices_after_a_good_refresh`; this group is the read itself.

THE KEY IS THE SOURCE'S OWN UPDATE, NEVER THE CLOCK. TCGCSV refreshes once a day and says when in
`last-updated.txt`. A read at 23:00 and another at 05:15 the next day get the same data; a key on the Central or
UTC date of the READ would save that data twice under two dates and corrupt the history. So a pass asks for the
stamp first, skips when it is the newest stored one and that update is finished, and otherwise stores the rows under
the stamp's UTC date with the full stamp beside them. `now` stamps `at` and nothing else.

NO NETWORK CALL. `FakeTcgcsv` serves the payloads TCGCSV serves. The JSON ones go through the REAL
`pricehistory.Market`, so URL composition and `parse_prices` are the module's own; the first check proves the fake is
wired right and passes on any checkout. Every other check imports the build inside itself, so a checkout without it
fails each check with its own sentence and the rest of T7 still runs.

THE SEAMS (a builder follows these names):

  pipeline/dailyprices.py
    run_pass(fetch=None, *, now=None, user_agent=pricehistory.USER_AGENT) -> dict
      fetch  url -> payload: the text (a `str`) for `last-updated.txt`, the parsed JSON for every other URL. None
             means the module's own client: `pricehistory.fetch_json` for JSON and a text twin of it for the stamp,
             both through `pipeline.net.request(url, headers={"User-Agent": user_agent}, ...)`, looked up when it
             runs. One HTTP client, never a second.
      now    an aware datetime, default `store.clock.now()`. A row's `at` is `int(now.timestamp())`.
      It asks for `last-updated.txt` FIRST. The stamp is `text.strip()`, e.g. "2026-10-27T03:30:00+0000"; a row's
      `day` is its UTC date as an ISO date, and its `updated` is the stamp. It builds its own `pricehistory.Market`
      with no cache directory (`PRICE_TTL_SECONDS` is seven days: a cached file would serve yesterday's prices as
      today's). It asks `groups(89)` and `prices(89, group)` for each group, no products and no categories. A group
      whose prices raise `pricehistory.PriceHistoryError` is named in `failed` and the other groups go on. It writes
      through `Store().write()` and never deletes. A pause of at least 0.1 s sits between consecutive requests, the
      stamp's included.
      It answers {"day": ISO date, "updated": stamp, "skipped": bool, "rows": rows written by THIS call,
      "failed": {group_id (int): message (str)}}.
      It skips (nothing asked for after the stamp, nothing written, "skipped": True) when the stamp equals the newest
      stored one AND that update is finished: a pass that ended with no failed group. An update with a failed group is
      NOT finished, so the next pass, though it sees the same stamp, asks again for the prices of the groups not yet
      saved and for no others. Whether it asks for the group list again is not pinned.
  store/dailyprices.py
    `DailyPrice(product_id: int, sub_type: str, day: str, market, low, mid, high, direct_low, group_id: int,
    updated: str, at: int)`, the five prices `Optional[str]` as the source gives them (`str` of the number, None for
    null or absent). `DailyPrices` holds `.entries`, a `Rows` of `DailyPrice`, table `daily_prices`, key
    (product_id, sub_type, day). The snapshot attribute is `Store().read().daily_prices`.
  scripts/price-refresh-daily.py
    after a good refresh, `from pipeline import dailyprices` then `dailyprices.run_pass(user_agent=...)`, with or
    without `--no-sweep`.

Temp files follow the run-folder standard (test-temp-standard): each check opens one `<pid>-<UUID>` folder from
`harness/tests/home.py:run_folder`, the store of each case lives inside it (`isolated_home` takes its folder from
`tempfile.tempdir`, which `in_run_folder` points there), and its exit removes it. The sweep of old sibling folders
is proved once, for the helper, by `t1_results.check_run_folder_sweeps_old_siblings_and_keeps_new_ones`.
"""

from __future__ import annotations

import functools
import json
import re
import tempfile
from datetime import datetime
from unittest import mock

from harness.tests import Checks
from harness.tests.home import isolated_home, run_folder
from pipeline import pricehistory
from store import clock
from store.session import Store

BASE = pricehistory.CATALOG_HOST + "/tcgplayer/89"
STAMP_URL = pricehistory.CATALOG_HOST + "/last-updated.txt"

#: Moments a pass runs, as the Mac's clock saw them. None of them is a day a row is keyed on.
MIDDAY = datetime(2026, 10, 27, 13, 0, tzinfo=clock.CENTRAL)
LATE = datetime(2026, 10, 27, 23, 0, tzinfo=clock.CENTRAL)
EARLY = datetime(2026, 10, 28, 5, 15, tzinfo=clock.CENTRAL)  # the next Central day, 6 hours 15 minutes after LATE
NEXT_DAY = datetime(2026, 10, 28, 13, 0, tzinfo=clock.CENTRAL)

#: The source's updates. STAMP1 is Oct 27 in UTC and Oct 26 (22:30) in Central, so a day read off the stamp's Central
#: date is wrong too; read from NEXT_DAY, the clock says Oct 28 in either zone. Only D1 is right.
STAMP1, D1 = "2026-10-27T03:30:00+0000", "2026-10-27"
STAMP2, D2 = "2026-10-28T20:05:49+0000", "2026-10-28"

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
PRICES1 = {
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
# The next update: one price moved, one product is new, the Foil and 1002 are gone from the source, 2001 moved.
PRICES2 = {
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
    """The host. `stamp` is what `last-updated.txt` says (served with a trailing newline, as a text file may be);
    set it, and `prices`, to publish a new update. `fail` is the set of group ids whose prices answer an HTTP 500;
    clear it to mend the host. `urls` is every URL asked, in order. The stamp is answered as text and every other URL
    as JSON, and it answers the categories list, any category's group list and any group's products as well, so a
    pass that asks for more than it needs fails the request-list assertions below with a plain sentence, never with
    an error from the fake. As a `fetch` it is the shape `run_pass` takes."""

    def __init__(self, prices, stamp=STAMP1, fail=()):
        self.prices = prices
        self.stamp = stamp
        self.fail = set(fail)
        self.urls = []

    def __call__(self, url, *_args, **_kwargs):
        self.urls.append(url)
        if url == STAMP_URL:
            return self.stamp + "\n"
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


def stamps_of(rows, day):
    return {row["updated"] for key, row in rows.items() if key[2] == day}


@in_run_folder
def check_daily_prices_fake_goes_through_the_real_market(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES FIXTURE — the fake is read by the real Market, so the checks below test the build and not the fake")
    fake = FakeTcgcsv(PRICES1)
    market = pricehistory.Market(fetcher=fake, courtesy_delay=0)
    checks.equal(sorted(row["groupId"] for row in market.groups(89).values()), [101, 102], "groups(89) lists both groups")
    prices = market.prices(89, 101)
    checks.equal(
        {key: (None if p.market is None else str(p.market)) for key, p in prices.items()},
        {(1001, "Normal"): "0.25", (1001, "Foil"): "2.5", (1002, "Normal"): None},
        "prices(89, 101) parses a number, a Foil beside its Normal, and a null",
    )
    checks.equal(sorted(fake.urls), [BASE + "/101/prices", BASE + "/groups"], "the two calls asked these two URLs")
    checks.equal(fake(STAMP_URL), STAMP1 + "\n", "the stamp is served as text")


@in_run_folder
def check_daily_prices_one_pass_writes_every_row(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 1 — one pass writes one row per product and sub type under the source's update, values as given")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(PRICES1)
        result = run(checks, module, fake, NEXT_DAY, "one pass")
        if result is None:
            return
        rows = table()
        checks.equal(
            (result.get("day"), result.get("updated"), result.get("skipped"), result.get("rows"), result.get("failed")),
            (D1, STAMP1, False, 4, {}),
            "the answer: day %s, the stamp's UTC date (the clock says %s, the stamp's Central date is 2026-10-26), the stamp, not skipped, 4 rows, no failed group"
            % (D1, NEXT_DAY.date().isoformat()),
        )
        checks.equal(sorted(rows), sorted(key + (D1,) for key in EXPECT1), "one row per product and sub type, all on the stamp's day")
        checks.equal(day_of(rows, D1), EXPECT1, "every price as given, null where the source gives null or leaves the key out, the group id kept")
        checks.equal(stamps_of(rows, D1), {STAMP1}, "every row keeps the full stamp, with the file's trailing newline gone")
        checks.equal({row["at"] for row in rows.values()}, {int(NEXT_DAY.timestamp())}, "every row carries the second the pass read")


@in_run_folder
def check_daily_prices_same_update_is_skipped(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 2 — a second pass over the same update asks for the stamp only and writes nothing, across midnight too")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(PRICES1)
        first = run(checks, module, fake, LATE, "first pass")
        if first is None:
            return
        checks.equal((first.get("skipped"), first.get("rows")), (False, 4), "the first pass reads and writes 4 rows")
        before = table()
        fake.urls.clear()
        # EARLY is the next Central day: a key on the day of the read would save these rows again under Oct 28.
        second = run(checks, module, fake, EARLY, "second pass")
        if second is None:
            return
        checks.equal((second.get("skipped"), second.get("rows"), second.get("failed")), (True, 0, {}), "the answer says skipped, 0 rows")
        checks.equal(fake.urls, [STAMP_URL], "the host is asked for the stamp and for nothing more, not even the group list")
        checks.equal(table(), before, "every row is as it was, `at` included")


@in_run_folder
def check_daily_prices_new_update_adds_rows_and_keeps_old_ones(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 3 — a new update adds rows and keeps the old ones, whatever the source stopped listing")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(PRICES1)
        if run(checks, module, fake, MIDDAY, "update one") is None:
            return
        day_one = table()
        fake.stamp, fake.prices = STAMP2, PRICES2
        fake.urls.clear()
        result = run(checks, module, fake, NEXT_DAY, "update two")
        if result is None:
            return
        rows = table()
        checks.equal(
            (result.get("day"), result.get("updated"), result.get("skipped"), result.get("rows")), (D2, STAMP2, False, 3),
            "update two: its own day and stamp, not skipped, 3 rows",
        )
        checks.equal(
            sorted(url for url in fake.urls if url.endswith("/prices")), [BASE + "/101/prices", BASE + "/102/prices"],
            "update two asked for every group's file again: a week-long cache would hand back update one's",
        )
        checks.equal(day_of(rows, D2), EXPECT2, "update two holds update two's prices, as given")
        checks.equal(stamps_of(rows, D2), {STAMP2}, "its rows keep its stamp")
        checks.equal({row["at"] for key, row in rows.items() if key[2] == D2}, {int(NEXT_DAY.timestamp())}, "its rows carry the second of the pass that read them")
        checks.equal({key: row for key, row in rows.items() if key[2] == D1}, day_one, "update one's rows are untouched, `at` included")
        checks.ok((1001, "Foil", D1) in rows and (1002, "Normal", D1) in rows, "a product the source stopped listing keeps its update-one row")
        checks.equal(len(rows), len(day_one) + 3, "the table holds 4 + 3 rows: nothing deleted, nothing doubled")


@in_run_folder
def check_daily_prices_failing_group_is_named_and_retried(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 4 — a failing group is named, the others go on, the update stays open, the retry asks for the failed group only")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(PRICES1, fail={102})
        first = run(checks, module, fake, MIDDAY, "first pass")
        if first is None:
            return
        failed = first.get("failed") or {}
        checks.equal(set(failed), {102}, "the answer names group 102, the one that failed, and no other")
        checks.ok(all(isinstance(message, str) and message for message in failed.values()), "the answer carries a sentence for it", str(failed))
        checks.equal((first.get("skipped"), first.get("rows")), (False, 3), "the pass is not skipped and wrote the 3 rows of group 101, which was served after the failing one")
        checks.equal(sorted(table()), sorted(key + (D1,) for key in EXPECT1 if EXPECT1[key]["group_id"] == 101), "only group 101's rows are in the table")
        fake.fail.clear()
        fake.urls.clear()
        # The stored stamp now equals the source's, and the update is still unfinished: a guard that compares stamps alone skips here.
        retry = run(checks, module, fake, LATE, "retry")
        if retry is None:
            return
        checks.equal((retry.get("skipped"), retry.get("rows"), retry.get("failed")), (False, 1, {}), "the retry over the same stamp is not skipped: it wrote the 1 row that was missing, with no failure")
        checks.equal(sorted(url for url in fake.urls if url.endswith("/prices")), [BASE + "/102/prices"], "the retry asked for the failed group's file and not for group 101's again")
        checks.equal(day_of(table(), D1), EXPECT1, "the update is whole now: all 4 rows, none doubled")
        checks.equal(stamps_of(table(), D1), {STAMP1}, "every row, the retried one too, keeps the one stamp")
        fake.urls.clear()
        third = run(checks, module, fake, LATE, "third pass")
        if third is None:
            return
        checks.equal((third.get("skipped"), third.get("rows"), fake.urls), (True, 0, [STAMP_URL]), "a clean pass finishes the update: the third pass asks for the stamp and nothing more")


@in_run_folder
def check_daily_prices_only_category_89_and_the_request_budget(checks: Checks) -> None:
    checks.note("")
    checks.note("DAILY PRICES 5 — only category 89: the stamp, its group list, one prices file per group, nothing else, nothing twice")
    module = load(checks)
    if module is None:
        return
    with isolated_home():
        fake = FakeTcgcsv(PRICES1)
        if run(checks, module, fake, MIDDAY, "the pass") is None:
            return
        categories = {url.split("/tcgplayer/")[1].split("/")[0] for url in fake.urls if "/tcgplayer/" in url}
        checks.equal(categories, {"89"}, "every URL under /tcgplayer/ is under /tcgplayer/89/ (Riftbound): no categories list, no other category")
        checks.equal(fake.urls[:1], [STAMP_URL], "the first request is the stamp")
        checks.equal(
            sorted(fake.urls[1:]), sorted([BASE + "/groups", BASE + "/101/prices", BASE + "/102/prices"]),
            "then exactly the group list and one prices file per group, no products call: that is the day's request budget",
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
        fake = FakeTcgcsv(PRICES1)
        agents, slept = [], []

        def request(url, headers=None, **_kwargs):
            agents.append((headers or {}).get("User-Agent"))
            answer = fake(url)
            return (answer if isinstance(answer, str) else json.dumps(answer)).encode()

        no_second_client = mock.patch("urllib.request.urlopen", side_effect=AssertionError("a second HTTP client was used"))
        with mock.patch.object(pricehistory.net, "request", request), mock.patch("time.sleep", slept.append), no_second_client:
            try:
                result = module.run_pass(now=MIDDAY, user_agent="banchi-test/9.9")
            except Exception as exc:  # noqa: BLE001 a crash is a failed case with its own sentence
                checks.ok(False, "the pass ran with no fetch given", "%s: %s" % (type(exc).__name__, exc))
                return
        checks.equal(result.get("rows"), 4, "with no fetch given the pass reads, the stamp included, through `pipeline.net.request`: 4 rows")
        checks.equal(set(agents), {"banchi-test/9.9"}, "every request carries the User-Agent it was handed, and there are %d of them" % len(agents))
        checks.ok(
            len(slept) >= len(fake.urls) - 1 and all(seconds >= 0.1 for seconds in slept),
            "a pause of at least 0.1 s sits between consecutive requests, the stamp's included", "%d requests, pauses %s" % (len(fake.urls), slept),
        )


CHECKS = (
    check_daily_prices_fake_goes_through_the_real_market,
    check_daily_prices_one_pass_writes_every_row,
    check_daily_prices_same_update_is_skipped,
    check_daily_prices_new_update_adds_rows_and_keeps_old_ones,
    check_daily_prices_failing_group_is_named_and_retried,
    check_daily_prices_only_category_89_and_the_request_budget,
    check_daily_prices_site_rules_user_agent_and_pause,
)
