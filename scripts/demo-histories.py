#!/usr/bin/env python3
"""Record the demo's price histories ONCE, on the owner's Mac, into new committed fixtures.

WHY THIS EXISTS AND WHY IT RUNS HERE ONLY. Every price history this product draws is read from
`infinite-api.tcgplayer.com`, and that host refuses the honest User-Agent (D216). The owner
allows the browser signature from the owner's own machine only, never from CI. So the published
demo cannot fetch a history when it is built. The owner's ruling (2026-09-24): the histories are
recorded once, here, into committed fixtures, and refreshed only when the owner chooses. CI
never calls this. The seed and the recorder read what it writes.

    PKMNSCAN_TCG_USER_AGENT="<your browser's User-Agent>" make demo-histories

WHAT IT RECORDS. For every card in `demo-assets/cards.json` that a committed export can place,
every range the demo draws (`pipeline/pricehistory.py:RANGES`). One file per product and range,
under `fixtures/demo-price-history/<date>/history/<productId>-<range>.json`, holding the
endpoint's answer VERBATIM except that `result` keeps only the SKUs the demo holds. An
`index.json` beside them maps each SKU to its product and names every SKU that could not be read.

NEVER MODIFIES A FIXTURE. Each run writes a NEW dated directory, and refuses if that directory
exists (`fixtures/` is ground truth: CLAUDE.md). The readers take the newest directory.

ONLY PUBLIC MARKET DATA. Every key of every answer is checked against `ALLOWED_RESULT` and
`ALLOWED_BUCKET` before anything is written. An answer carrying any other key refuses the whole
run. The User-Agent string itself is never written anywhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURES = REPO_ROOT / "fixtures"
OUT_ROOT = FIXTURES / "demo-price-history"
MANIFEST = REPO_ROOT / "demo-assets" / "cards.json"
EXPORTS = (
    "riftbound_export_untouched.csv",
    "sv09_export_untouched.csv",
    "onepiece_export_untouched.csv",
    "pokemon_wide_export_untouched.csv",
)

# The keys the endpoint answers, measured on `fixtures/tcgplayer_price_history_vilemaw_month.json`.
# A key outside these refuses the run: it is the one mechanical proof that nothing but public
# market figures reaches a committed file.
ALLOWED_TOP = {"count", "result"}
ALLOWED_RESULT = {
    "skuId", "variant", "language", "condition", "averageDailyQuantitySold",
    "averageDailyTransactionCount", "totalQuantitySold", "totalTransactionCount",
    "trendingMarketPricePercentages", "buckets",
}
ALLOWED_BUCKET = {
    "marketPrice", "quantitySold", "lowSalePrice", "lowSalePriceWithShipping", "highSalePrice",
    "highSalePriceWithShipping", "transactionCount", "bucketStartDate",
}
HISTORY_URL = re.compile(r"/price/history/(\d+)/detailed\?range=([a-z]+)$")


def unexpected_keys(payload: dict) -> List[str]:
    """Every key in one answer that is not public market data, as `where.key`."""
    found = [f"top.{key}" for key in payload if key not in ALLOWED_TOP]
    for result in payload.get("result") or []:
        found += [f"result.{key}" for key in result if key not in ALLOWED_RESULT]
        for bucket in result.get("buckets") or []:
            found += [f"bucket.{key}" for key in bucket if key not in ALLOWED_BUCKET]
    return sorted(set(found))


def demo_rows() -> Dict[str, dict]:
    """The committed export row of every demo card an export can place, keyed by SKU."""
    from pipeline import tcgcsv

    wanted = {str(entry["sku"]) for entry in json.loads(MANIFEST.read_text()) if entry.get("sku")}
    rows: Dict[str, dict] = {}
    for name in EXPORTS:
        for row in tcgcsv.read_export(FIXTURES / name).rows:
            sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
            if sku in wanted and sku not in rows:
                rows[sku] = dict(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", default=date.today().isoformat(), help="the directory name")
    args = parser.parse_args()

    import envfile
    from pipeline import pricehistory

    agent = (envfile.get_live(pricehistory.AGENT_ENV) or "").strip()
    if not agent or agent == pricehistory.USER_AGENT:
        raise SystemExit(
            f"refusing: {pricehistory.AGENT_ENV} is not set. The history host refuses the honest "
            "User-Agent (D216). Run this on the owner's Mac with the browser's User-Agent."
        )
    out = OUT_ROOT / args.date
    if out.exists():
        raise SystemExit(f"refusing: {out.relative_to(REPO_ROOT)} exists. Fixtures are never modified; "
                         "pass a new --date.")

    rows = demo_rows()
    held = set(rows)
    captured: Dict[str, dict] = {}

    def fetcher(url: str) -> dict:
        payload = pricehistory.fetch_json(url, user_agent=agent)
        found = HISTORY_URL.search(url)
        if found:
            captured[f"{found.group(1)}-{found.group(2)}"] = payload
        return payload

    market = pricehistory.Market(fetcher=fetcher)
    readings, refusals = market.readings_for_rows(rows.values(), ranges=pricehistory.RANGES)

    files: Dict[str, dict] = {}
    for slug, payload in sorted(captured.items()):
        bad = unexpected_keys(payload)
        if bad:
            raise SystemExit(f"refusing: history/{slug} carries keys that are not market data: {bad}")
        kept = [r for r in payload.get("result") or [] if str(r.get("skuId")) in held]
        files[slug] = {"count": payload.get("count"), "result": kept}

    (out / "history").mkdir(parents=True)
    for slug, payload in files.items():
        (out / "history" / f"{slug}.json").write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    index = {
        "captured": args.date,
        "source": "infinite-api.tcgplayer.com price history, read with a browser User-Agent (D216)",
        "ranges": list(pricehistory.RANGES),
        "skus": {sku: reading.product_id for sku, reading in sorted(readings.items()) if reading.series},
        "refused": dict(sorted(refusals.items())),
        "unplaced": sorted(
            str(e["sku"]) for e in json.loads(MANIFEST.read_text()) if e.get("sku") and str(e["sku"]) not in held
        ),
    }
    (out / "index.json").write_text(json.dumps(index, sort_keys=True, indent=1) + "\n")
    print("demo price histories -> %s" % out.relative_to(REPO_ROOT))
    print("  %d SKU(s) read, %d file(s), %d refused, %d with no export row"
          % (len(index["skus"]), len(files), len(refusals), len(index["unplaced"])))
    print("  every key checked against the public market-data allow list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
