#!/usr/bin/env python3
"""`store/pricearchive.py` and `pipeline/pricearchive.py`, proved against a throwaway store
(D219).

NO NETWORK CALL. `FakeMarket` below is a stand-in for `pipeline/pricehistory.py:Market`,
duck-typed to the one method `pipeline/pricearchive.py:sweep` calls
(`readings_for_rows(rows, ranges=...)`), and it answers out of canned
`pipeline/pricehistory.py:Bucket`/`Series`/`Reading` objects built in this file — the same
dataclasses the real `Market` returns, never a second, drifting shape.

THE ARM THIS FILE EXISTS FOR proves the D62 argument this branch's own decision entry makes
(D219): archiving the SAME calendar day out of `semiannual` and
`annual` — both seven-day-wide ranges — must leave TWO rows, because the two are independent
observations
even when their bucket happens to start on the same date. A second arm builds the archive's
own key with `width_days` in place of `range` and shows THAT key collapses the two into one
row — the guard is trusted only once it has been seen to fail on the defect it guards
(`CLAUDE.md`'s own rule).

Written, not wired into `make check` — `make catalog-index-selftest`'s own precedent, a fast
self-contained proof of a package with no caller yet reachable from a screen.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import pricearchive as archive_walk  # noqa: E402
from pipeline.pricehistory import Bucket as HistoryBucket  # noqa: E402
from pipeline.pricehistory import Reading as HistoryReading  # noqa: E402
from pipeline.pricehistory import Series  # noqa: E402
from store import files  # noqa: E402
from store.master import Card  # noqa: E402
from store.orders import OrderLine, OrderRecord  # noqa: E402
from store.pricearchive import Bucket, PriceArchive, Source, _key  # noqa: E402
from store.session import Store  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


class FakeMarket:
    """Answers `readings_for_rows` out of a fixed script, no network, no `Market` at all.

    `script` maps sku -> {range: Series}. A sku with no entry is a REFUSAL, exactly like the
    real `Market.readings_for_rows` reporting a sku it could not resolve — both directions
    (found and refused) are exercised by every test below that touches this class.
    """

    def __init__(self, script: Dict[str, Dict[str, Series]], refuse: Dict[str, str] = None):
        self.script = script
        self.refuse = refuse or {}

    def readings_for_rows(self, rows, ranges=()):
        readings = {}
        refusals = dict(self.refuse)
        for row in rows:
            sku = row.get("TCGplayer Id", "")
            series_by_range = self.script.get(sku)
            if series_by_range is None:
                refusals.setdefault(sku, "not in the script")
                continue
            wanted = {r: s for r, s in series_by_range.items() if r in ranges}
            readings[sku] = HistoryReading(sku=sku, product_id=42, series=wanted)
        return readings, refusals


class RecordingMarket:
    """Answers every SKU it is asked about out of `script`, and REMEMBERS every SKU it was
    ever asked about — the proof surface for "a resumed sweep must not re-fetch what it
    already holds from this same pass" (D224). A test hands this the
    SKUs a chunk is supposed to skip and asserts they never appear in `.asked`.

    ONE CALL RAISES ON PURPOSE, IF `raise_on` NAMES A SKU. This is the stand-in for a
    dropped connection or a Ctrl-C mid-chunk (D224's other half): the
    exception is a plain `RuntimeError`, never a `pipeline.pricehistory.PriceHistoryError`,
    so it propagates PAST `readings_for_rows`'s own per-product `except` the same way a
    `KeyboardInterrupt` would — this class is not exercising that internal catch, it is
    exercising what happens to a CALLER who chunks the walk instead of a caller who does not.
    """

    def __init__(self, script, raise_on=None):
        self.script = script
        self.raise_on = raise_on or set()
        self.asked = set()

    def readings_for_rows(self, rows, ranges=()):
        readings = {}
        refusals = {}
        for row in rows:
            sku = row.get("TCGplayer Id", "")
            self.asked.add(sku)
            if sku in self.raise_on:
                raise RuntimeError(f"connection dropped reading {sku}")
            series_by_range = self.script.get(sku)
            if series_by_range is None:
                refusals.setdefault(sku, "not in the script")
                continue
            wanted = {r: s for r, s in series_by_range.items() if r in ranges}
            readings[sku] = HistoryReading(sku=sku, product_id=42, series=wanted)
        return readings, refusals


def _series(sku: str, range_: str, start: date, market: str, quantity: int = 1) -> Series:
    bucket = HistoryBucket(
        start=start,
        market=Decimal(market),
        quantity=quantity,
        transactions=quantity,
        low=Decimal(market),
        high=Decimal(market),
    )
    return Series(
        sku=sku, product_id=42, range=range_, variant="Normal", condition="Near Mint",
        language="English", total_quantity_sold=quantity, total_transaction_count=quantity,
        buckets=(bucket,),
    )


def main() -> int:
    print("price-history archive self-test\n")

    # ---------------------------------------------------------------- store-level: the key
    print("-- store/pricearchive.py: the key argument (D62) --")
    archive = PriceArchive()
    same_day = date(2026, 1, 1)
    semiannual = Bucket(
        sku="111", product_id=42, range="semiannual", width_days=7,
        start=same_day.isoformat(), market="5.00", quantity=2, transactions=2,
        low="4.50", high="5.50", at=100,
    )
    annual = Bucket(
        sku="111", product_id=42, range="annual", width_days=7,
        start=same_day.isoformat(), market="6.00", quantity=3, transactions=3,
        low="5.50", high="6.50", at=100,
    )
    archive.upsert({
        _key("111", "semiannual", same_day.isoformat()): semiannual,
        _key("111", "annual", same_day.isoformat()): annual,
    })
    ok(len(archive.entries) == 2,
       "same sku, same start date, different ranges -> two rows, not one",
       dict(archive.entries))
    ranges_seen = {b.range for b in archive.entries.values()}
    ok(ranges_seen == {"semiannual", "annual"},
       "both ranges survive, each carrying its own market figure", ranges_seen)

    # The defect this guards against, PROVEN to fail on it: a WIDTH-only key merges them.
    width_only: Dict[str, Bucket] = {}
    for bucket in (semiannual, annual):
        collision_key = f"{bucket.sku}:{bucket.width_days}:{bucket.start}"
        width_only[collision_key] = bucket
    ok(len(width_only) == 1,
       "a key built from (sku, width_days, start) instead DOES collapse the two ranges into "
       "one row — this is the bug D219's key design avoids",
       width_only)

    # ---------------------------------------------------------------- never-delete
    print("\n-- store/pricearchive.py: a bucket a later pass does not mention survives --")
    archive2 = PriceArchive()
    archive2.upsert({
        _key("222", "month", "2026-01-01"): Bucket(
            sku="222", product_id=1, range="month", width_days=1, start="2026-01-01",
            market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=100,
        ),
    })
    # A later pass over a DIFFERENT sku entirely — "222" is not mentioned at all.
    archive2.upsert({
        _key("333", "month", "2026-01-01"): Bucket(
            sku="333", product_id=2, range="month", width_days=1, start="2026-01-01",
            market="2.00", quantity=1, transactions=1, low="2.00", high="2.00", at=200,
        ),
    })
    ok("222:month:2026-01-01" in archive2.entries,
       "a sku no later sweep mentions is never deleted", dict(archive2.entries))
    ok(len(archive2.entries) == 2, "the new sku is ADDED beside it, not instead of it")

    # A later pass over the SAME key, with a corrected reading, replaces just that row.
    archive2.upsert({
        _key("222", "month", "2026-01-01"): Bucket(
            sku="222", product_id=1, range="month", width_days=1, start="2026-01-01",
            market="1.50", quantity=2, transactions=2, low="1.00", high="2.00", at=300,
        ),
    })
    corrected = archive2.entries["222:month:2026-01-01"]
    ok(corrected.market == "1.50" and corrected.at == 300,
       "a re-read of the SAME key with newer data replaces that row", corrected)

    # `record_pass` replaces only the range it names, not the whole sources table.
    archive2.record_pass([Source(range="month", at=100, requested=1, answered=1, refused=0)])
    archive2.record_pass([Source(range="annual", at=200, requested=1, answered=1, refused=0)])
    payload = {s["range"]: s for s in archive2.sources_payload()}
    ok(set(payload) == {"month", "annual"},
       "a pass over one range never erases another range's own accounting row", payload)

    # ---------------------------------------------------------------- pipeline: rows_from_store
    print("\n-- pipeline/pricearchive.py: rows_from_store reads only the store --")
    previous = os.environ.get(files.HOME_ENV)
    home = Path(tempfile.mkdtemp(prefix="pricearchive-selftest-"))
    os.environ[files.HOME_ENV] = str(home)
    try:
        with Store().write() as snapshot:
            snapshot.inventory.cards["1:1"] = Card(
                box=1, index=1, sku="444", name="Pikachu", number="25/102",
                set_name="Base Set", game="pokemon", condition="Near Mint",
            )
            snapshot.inventory.cards["1:2"] = Card(
                box=1, index=2, sku="555", name="Bulbasaur", number="44/102",
                set_name="Base Set", game="pokemon", condition="Near Mint", state="sold",
            )
            snapshot.inventory.cards["1:3"] = Card(box=1, index=3, sku=None)

        rows = archive_walk.rows_from_store(Store().read())
        ok(set(rows) == {"444", "555"},
           "every distinct, non-empty sku is a subject — sold or on hand alike", rows)
        ok(rows["444"]["Product Line"] == "Pokemon" and rows["444"]["Product Name"] == "Pikachu",
           "the export-shaped row carries the card's own name and resolved product line",
           rows["444"])

        # -------------------------------------------------------- pipeline: sweep (no network)
        print("\n-- pipeline/pricearchive.py: sweep, against a FakeMarket, both directions --")
        script = {
            "444": {
                "semiannual": _series("444", "semiannual", same_day, "3.00"),
                "annual": _series("444", "annual", same_day, "3.20"),
            },
        }
        market = FakeMarket(script)
        buckets, sources, refusals = archive_walk.sweep(
            rows, market, ranges=("semiannual", "annual"), now=1_000,
        )
        ok(len(buckets) == 2,
           "one sku swept over two overlapping ranges -> two archived buckets", buckets)
        ok("555" in refusals,
           "a sku the market could not answer for is reported as a refusal, never dropped",
           refusals)
        ok(all(b.at == 1_000 for b in buckets.values()),
           "every bucket this pass wrote carries this pass's own clock")
        answered = {s.range: s.answered for s in sources}
        ok(answered.get("semiannual") == 1 and answered.get("annual") == 1,
           "the accounting counts one answered sku per range", answered)
        refused_count = {s.refused for s in sources}
        ok(refused_count == {1},
           "the accounting's refused count matches the refusal this pass actually saw",
           sources)

        # -------------------------------------------------------- end to end through Store
        print("\n-- end to end: sweep, then Store().write(), then a second sweep --")
        with Store().write() as snapshot:
            snapshot.archive.upsert(buckets)
            snapshot.archive.record_pass(sources)
        stored = dict(Store().read().archive.entries)
        ok(len(stored) == 2, "both buckets landed in the store, keyed by (sku, range, start)")

        # A second sweep over a store where "555" no longer resolves (its only source vanished
        # from the script) must not touch "444"'s already-archived buckets.
        market_narrower = FakeMarket({})
        buckets2, sources2, refusals2 = archive_walk.sweep(
            {"555": rows["555"]}, market_narrower, ranges=("month",), now=2_000,
        )
        ok(not buckets2, "a pass that resolves nothing writes nothing")
        with Store().write() as snapshot:
            snapshot.archive.upsert(buckets2)
            snapshot.archive.record_pass(sources2)
        after = dict(Store().read().archive.entries)
        ok(after == stored,
           "a later pass over a different, narrower selection never deletes what an earlier "
           "pass archived", after)

        # ---------------------------------------------------- ranking: sold value first
        print("\n-- pipeline/pricearchive.py: revenue_by_sku and rank_by_revenue "
              "(D223) --")
        with Store().write() as snapshot:
            # "444" sells for $10.00 once (a real reading). "555" never sells (already
            # sold=state above, but no ORDER line — on-hand-or-sold is not the same fact as
            # earned revenue). "666" has a CANCELED order and must count as zero.
            snapshot.ledger.orders["ebay:1"] = OrderRecord(
                source="ebay", number="1", status="Open",
                lines=[OrderLine(sku="444", quantity=2, unit_price="5.00")],
            )
            snapshot.ledger.orders["ebay:2"] = OrderRecord(
                source="ebay", number="2", status="Canceled",
                lines=[OrderLine(sku="666", quantity=9, unit_price="99.00")],
            )
        revenue = archive_walk.revenue_by_sku(Store().read().ledger)
        ok(revenue.get("444") == Decimal("10.00"),
           "gross is unit_price * quantity, summed across lines", revenue)
        ok("666" not in revenue,
           "a CANCELED order contributes nothing — app/src/Revenue.tsx's own rule", revenue)
        ok("555" not in revenue,
           "a sku nobody has ever ordered earns nothing, whether or not it is on hand",
           revenue)

        ranked = archive_walk.rank_by_revenue(["555", "444", "999"], revenue)
        ok(ranked == ["444", "555", "999"],
           "sold value first; ties (both zero) break on the sku string", ranked)

        ranked_rows = archive_walk.rows_from_store(Store().read())
        ok(list(ranked_rows)[0] == "444",
           "rows_from_store itself walks sold-value-first, with no second sort needed by "
           "its caller", list(ranked_rows))

        # -------------------------------------- resuming: freshness (D224)
        print("\n-- pipeline/pricearchive.py: freshness_index and split_by_freshness --")
        existing = [
            Bucket(sku="AAA", product_id=1, range="month", width_days=1, start="2026-01-01",
                   market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=990),
            Bucket(sku="AAA", product_id=1, range="annual", width_days=7, start="2026-01-01",
                   market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=990),
            # "BBB" was read for month only — annual is MISSING, so BBB is not fresh.
            Bucket(sku="BBB", product_id=2, range="month", width_days=1, start="2026-01-01",
                   market="2.00", quantity=1, transactions=1, low="2.00", high="2.00", at=990),
            # "CCC" was read for both, but long enough ago to have aged out of the TTL.
            Bucket(sku="CCC", product_id=3, range="month", width_days=1, start="2026-01-01",
                   market="3.00", quantity=1, transactions=1, low="3.00", high="3.00", at=100),
            Bucket(sku="CCC", product_id=3, range="annual", width_days=7, start="2026-01-01",
                   market="3.00", quantity=1, transactions=1, low="3.00", high="3.00", at=100),
        ]
        index = archive_walk.freshness_index(existing)
        rows_for_resume = {sku: {} for sku in ("AAA", "BBB", "CCC", "DDD")}
        needs, fresh = archive_walk.split_by_freshness(
            rows_for_resume, index, ranges=("month", "annual"), now=1_000, ttl_seconds=100,
        )
        ok(fresh == ["AAA"],
           "only the sku fresh in EVERY requested range is skipped", fresh)
        ok(set(needs) == {"BBB", "CCC", "DDD"},
           "one stale or missing range sends the whole sku back — BBB (missing annual), "
           "CCC (aged past the ttl) and DDD (never read) all need a fetch", needs)
        ok(list(needs) == ["BBB", "CCC", "DDD"],
           "order is preserved from the caller's own ranking, not re-sorted here", needs)

        # -------------------------------------------------------------- chunk_rows
        print("\n-- pipeline/pricearchive.py: chunk_rows preserves order --")
        five = {str(i): {} for i in range(5)}
        chunks = archive_walk.chunk_rows(five, 2)
        ok([list(c) for c in chunks] == [["0", "1"], ["2", "3"], ["4"]],
           "chunks are ordered pieces, never re-sorted", chunks)

        # ------------------------------------------------- pacing (D222)
        print("\n-- pipeline/pricearchive.py: classify_refusals and measured_pace --")
        blocked_message = (
            "https://infinite-api.tcgplayer.com/price/history/652771/detailed?range=month "
            "answered HTTP 403. That is either an authorization change at the host or its "
            "own defenses declining this client by its request signature — set "
            "PKMNSCAN_TCG_USER_AGENT in .env to the User-Agent your browser sends and try "
            "again."
        )
        refusals_in = {"652771": blocked_message, "other": "not in the script"}

        # THE GUARD, PROVEN TO FAIL WITHOUT THE FIX FIRST: with no evidence of an earlier
        # success, the message is left exactly as `Blocked` phrased it — still pointing at
        # the User-Agent, which is the WRONG remedy once a run has actually throttled.
        unchanged, blocked_count = archive_walk.classify_refusals(
            refusals_in, had_earlier_success=False
        )
        ok(unchanged["652771"] == blocked_message,
           "with no earlier success this pass, a 403 is left exactly as Blocked phrased it "
           "— this function has no evidence yet to call it a throttle", unchanged)
        ok(blocked_count == 1, "exactly one refusal carried the 403 signature", blocked_count)

        # NOW THE FIX: after this pass has already read something successfully, the SAME
        # message is rewritten, and it never repeats the disproved remedy.
        rewritten, blocked_count2 = archive_walk.classify_refusals(
            refusals_in, had_earlier_success=True
        )
        ok("PKMNSCAN_TCG_USER_AGENT" not in rewritten["652771"],
           "after an earlier success this pass, the rewritten message never repeats the "
           "remedy this pass has already disproved", rewritten)
        ok("throttle" in rewritten["652771"].lower(),
           "the rewritten message names what it actually is", rewritten)
        ok(rewritten["other"] == "not in the script",
           "a refusal that never carried the 403 signature is left untouched", rewritten)
        ok(blocked_count2 == 1, "the blocked count is unchanged by the rewrite", blocked_count2)

        ok(archive_walk.measured_pace(0, 0) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "no requests measured yet -> the naive default, never a divide-by-zero")
        paced = archive_walk.measured_pace(requests_made=800, elapsed_seconds=80)
        ok(paced == 0.2,
           "800 requests survived over 80s -> 0.1s/request observed, doubled by the "
           "backoff factor -> 0.2s", paced)
        floor_paced = archive_walk.measured_pace(requests_made=1000, elapsed_seconds=1)
        ok(floor_paced == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "a rate faster than the naive default never paces BELOW it", floor_paced)

        pace_path = home / "throttle-pace.json"
        ok(archive_walk.load_pace(pace_path) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "no measurement on disk yet -> the naive default")
        archive_walk.save_pace(
            pace_path, 0.42, requests_made=800, elapsed_seconds=80, at=1_000,
        )
        ok(archive_walk.load_pace(pace_path) == 0.42,
           "a saved measurement is what the next press starts from")
        pace_path.write_text("not json", "utf-8")
        ok(archive_walk.load_pace(pace_path) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "a corrupt measurement file is a cache miss, never a refusal — `Market._cached`'s "
           "own rule, applied here")

        # ---------------------------------------- end to end: an interrupted sweep, resumed
        print("\n-- end to end: an interrupted sweep commits what it already read, and a "
              "resumed sweep does not re-fetch it --")
        interrupt_rows = {sku: {"TCGplayer Id": sku} for sku in ("R1", "R2", "R3")}
        script = {
            sku: {"month": _series(sku, "month", same_day, "1.00")}
            for sku in interrupt_rows
        }

        # THE GUARD, PROVEN TO FAIL FIRST: the OLD shape (one `sweep()` call over every row,
        # written once at the end) loses EVERYTHING when the connection drops partway —
        # nothing is committed because nothing was ever written before the raise.
        os.environ[files.HOME_ENV] = str(Path(tempfile.mkdtemp(prefix="pricearchive-old-")))
        try:
            with Store().write() as snapshot:
                pass  # establish an empty store to read back against
            one_shot_market = RecordingMarket(script, raise_on={"R2"})
            raised = False
            try:
                archive_walk.sweep(interrupt_rows, one_shot_market, ranges=("month",))
            except RuntimeError:
                raised = True
            ok(raised, "the one-shot call really does raise on the dropped sku")
            after_old = dict(Store().read().archive.entries)
            ok(after_old == {},
               "the OLD one-transaction-at-the-end shape has nothing to commit when the "
               "call that would have produced it never returned — this is the bug "
               "D224's chunking fixes", after_old)
        finally:
            shutil.rmtree(os.environ[files.HOME_ENV], ignore_errors=True)
            os.environ[files.HOME_ENV] = str(home)

        # THE FIX: chunked, one commit per chunk. R1 lands before R2's chunk raises; R3 is
        # never even reached this pass.
        chunked_market = RecordingMarket(script, raise_on={"R2"})
        chunks_of_one = archive_walk.chunk_rows(interrupt_rows, 1)
        interrupted_at = None
        for idx, chunk in enumerate(chunks_of_one):
            try:
                b, s, r = archive_walk.sweep(chunk, chunked_market, ranges=("month",))
            except RuntimeError:
                interrupted_at = idx
                break
            with Store().write() as snapshot:
                snapshot.archive.upsert(b)
        ok(interrupted_at == 1, "the second chunk (R2) is where the drop happens", interrupted_at)
        survived = dict(Store().read().archive.entries)
        ok(any(b.sku == "R1" for b in survived.values()) and
           not any(b.sku in ("R2", "R3") for b in survived.values()),
           "R1's chunk committed before the drop; R2 and R3 never landed", survived)
        ok("R3" not in chunked_market.asked,
           "the pass stopped at the drop rather than pressing on past it", chunked_market.asked)

        # THE RESUME: a fresh pass re-reads the store, sees R1 already fresh, and never asks
        # the market about it again — only R2 and R3 are sent.
        resume_index = archive_walk.freshness_index(
            Store().read().archive.entries.values()
        )
        resume_needs, resume_fresh = archive_walk.split_by_freshness(
            interrupt_rows, resume_index, ranges=("month",), now=100_000, ttl_seconds=3_600,
        )
        ok(resume_fresh == ["R1"], "R1 is skipped on resume — it is already archived", resume_fresh)
        ok(set(resume_needs) == {"R2", "R3"},
           "R2 and R3 still need a read", resume_needs)

        resume_market = RecordingMarket(script)
        for chunk in archive_walk.chunk_rows(resume_needs, 1):
            b, s, r = archive_walk.sweep(chunk, resume_market, ranges=("month",))
            with Store().write() as snapshot:
                snapshot.archive.upsert(b)
        ok("R1" not in resume_market.asked,
           "the resumed pass never asks the market about a sku the archive already holds "
           "fresh from this same pass", resume_market.asked)
        ok({"R2", "R3"} <= resume_market.asked,
           "the resumed pass does read what it still owes", resume_market.asked)
        final_skus = {b.sku for b in Store().read().archive.entries.values()}
        ok({"R1", "R2", "R3"} <= final_skus,
           "after the resume, every subject from this pass is archived exactly once",
           final_skus)
    finally:
        if previous is None:
            os.environ.pop(files.HOME_ENV, None)
        else:
            os.environ[files.HOME_ENV] = previous
        shutil.rmtree(home, ignore_errors=True)

    print("\nprice-history archive self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
