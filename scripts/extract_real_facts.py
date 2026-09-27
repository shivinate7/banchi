#!/usr/bin/env python3
"""Read a READ-ONLY COPY of the owner's store and write demo-assets/real-facts.json.

RUN ONCE, BY HAND, AGAINST A SNAPSHOT — never against the owner's own checkout, never over
port 8000. Its output is the only place a real store's own facts reach the tracked tree.
`demo-photos.py` and `demo-seed.py` read the OUTPUT of this script; neither ever touches a
real store again, which is what keeps `make demo-seed` deterministic and runnable in CI with
no store on disk at all.

WHAT IT WRITES, and nothing else:

  pin_skus       real SKUs `demo-photos.py` must force into the curated set, so the seed's
                 required cases (worth $5+, a 25%+ typed-price mismatch, a foil/normal pair
                 of one name, an unsent card with no market price) are REAL cards rather than
                 invented ones. Each is verified against a vendored fixture (`fixtures/`) —
                 the same catalogue `demo-seed.py` already prices everything else against —
                 so "25%+ mismatch" means against the demo's own real arithmetic, not a
                 number that only held on the owner's Mac at a different moment.
  typed_prices   {sku: "X.XX"}, straight out of the copy's `prices.json`. Only kept for a
                 SKU a vendored fixture also carries, because an untethered typed price has
                 nothing to be a mismatch AGAINST once it reaches the demo.
  sales          {sku: [{"unit_price": "X.XX", "placed_at": "..."}]}, out of the copy's
                 `orders` table. THE BUYER, THE ORDER NUMBER AND THE ADDRESS ARE NEVER READ
                 OUT OF THE ROW — only `unit_price` and the order's `placed_at` cross this
                 boundary, matching the owner's own ruling: "card photos is ok and sales
                 dollars are ok."

    python3 scripts/extract_real_facts.py --store <read-only copy dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "demo-assets" / "real-facts.json"

FIXTURES = ("sv09_export_untouched.csv", "onepiece_export_untouched.csv",
            "riftbound_export_untouched.csv")

# Hand-picked from a real measurement of the owner's store (docs cite the source rather than
# re-deriving it here): the SKUs that make each required demo case real. Each is checked
# against the vendored fixture below before it is written — an entry the fixture disagrees
# with is dropped and the drop is printed, never written silently.
CANDIDATE_HIGH_VALUE = ["9191942", "9277742", "9139842", "9454356"]
CANDIDATE_MISMATCH = ["9018548", "9201604"]
CANDIDATE_FOIL_PAIR = ["9405643", "9446010"]  # Shadow Order Disciple: normal, then foil
CANDIDATE_NO_MARKET_UNSENT = ["8937315"]  # Garganacl — Pokemon, no fixture row at all


def fixture_market() -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for name in FIXTURES:
        path = REPO_ROOT / "fixtures" / name
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                try:
                    prices[row["TCGplayer Id"]] = float(row["TCG Market Price"])
                except (TypeError, ValueError):
                    continue
    return prices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="a read-only copy holding "
                         "inventory/store.sqlite and inventory/prices.json")
    args = parser.parse_args()

    store = Path(args.store).expanduser().resolve()
    db_path = store / "inventory" / "store.sqlite"
    prices_path = store / "inventory" / "prices.json"
    if not db_path.is_file():
        raise SystemExit("no store at %s" % db_path)

    market = fixture_market()

    typed_prices: Dict[str, str] = {}
    if prices_path.is_file():
        raw = json.loads(prices_path.read_text()).get("skus", {})
        for sku, entry in raw.items():
            if sku not in market:
                continue  # nothing in the demo's own catalogue to compare it against
            value = entry.get("value") if isinstance(entry, dict) else None
            if not isinstance(value, str):
                continue
            try:
                float(value)
            except ValueError:
                continue
            typed_prices[sku] = value

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    sales: Dict[str, List[dict]] = {}
    for row in conn.execute("SELECT payload FROM orders"):
        payload = json.loads(row["payload"])
        placed_at = payload.get("placed_at")
        for line in payload.get("lines", []):
            sku = line.get("sku")
            unit_price = line.get("unit_price")
            if not sku or sku not in market or not unit_price or not placed_at:
                continue
            sales.setdefault(sku, []).append({
                "unit_price": str(unit_price),
                "placed_at": str(placed_at),
            })
    conn.close()

    # Cap and sort each SKU's sales, newest first — the manifest only ever needs one or two.
    for sku, entries in sales.items():
        entries.sort(key=lambda e: e["placed_at"], reverse=True)
        sales[sku] = entries[:2]

    pin_skus = []
    dropped = []
    for sku in CANDIDATE_HIGH_VALUE + CANDIDATE_MISMATCH + CANDIDATE_FOIL_PAIR:
        if sku in market:
            pin_skus.append(sku)
        else:
            dropped.append(sku)
    for sku in CANDIDATE_NO_MARKET_UNSENT:
        if sku not in market:
            pin_skus.append(sku)  # the point of this case IS that it has no fixture row
        else:
            dropped.append(sku)

    # The mismatch case is checked here, against the SAME fixture prices the demo will use,
    # so a 25%+ gap printed below is the gap the viewer will actually see.
    mismatches = []
    for sku in CANDIDATE_MISMATCH:
        typed = typed_prices.get(sku)
        if typed is None or sku not in market or market[sku] <= 0:
            continue
        pct = abs(float(typed) - market[sku]) / market[sku] * 100
        mismatches.append((sku, market[sku], typed, pct))

    out = {
        "pin_skus": sorted(set(pin_skus)),
        "typed_prices": typed_prices,
        "sales": sales,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")

    print("wrote %s" % OUT.relative_to(REPO_ROOT))
    print("  pin_skus      %d (%s)" % (len(out["pin_skus"]), ", ".join(out["pin_skus"])))
    print("  typed_prices  %d SKUs comparable against a vendored fixture" % len(typed_prices))
    print("  sales         %d SKUs carry at least one real order line" % len(sales))
    if dropped:
        print("  DROPPED (no fixture row, or already had one): %s" % ", ".join(dropped))
    for sku, mkt, typed, pct in mismatches:
        print("  mismatch check: %s market $%.2f typed $%s -> %.1f%%" % (sku, mkt, typed, pct))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
