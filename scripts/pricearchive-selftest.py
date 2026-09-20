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
