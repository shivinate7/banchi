#!/usr/bin/env python3
"""Curate a SECOND, small, real card set for the demo — opt-in, additive, never the default.

RUN ONCE, BY HAND, AGAINST A READ-ONLY COPY of the owner's store. Writes
`demo-assets/extra/cards.json` and `demo-assets/extra/photos/`, a manifest and photograph set
in the exact shape `demo-photos.py` already writes for the default 132-card set — but under
its OWN path, so nothing here can collide with, resize, or renumber that already-committed
set or the specs pinned to its count. `scripts/demo-seed.py`'s `add_extra_real_boxes()` is the
only reader, and only when `PKMNSCAN_DEMO_EXTRA_REAL=1` is set.

Reuses `demo-photos.py`'s QR clearance and crop (loaded by path — the filename's hyphen
blocks a plain `import`), so a candidate photograph is refused on exactly the same positive
decode test, at full resolution, before anything is written.

`demo-assets/real-facts.json` (`scripts/extract_real_facts.py`) supplies the pinned SKUs and
the real typed prices / sale facts this script attaches when a pinned or sampled card's SKU
has one.

    python3 scripts/demo-extra-real.py --source <read-only copy> --photo-root <real store>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRA = REPO_ROOT / "demo-assets" / "extra"
PHOTOS = EXTRA / "photos"
MANIFEST = EXTRA / "cards.json"
FACTS = REPO_ROOT / "demo-assets" / "real-facts.json"


def _demo_photos():
    spec = importlib.util.spec_from_file_location(
        "demo_photos_module", REPO_ROOT / "scripts" / "demo-photos.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--photo-root", help="defaults to --source")
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260925)
    args = parser.parse_args()

    dp = _demo_photos()
    source = Path(args.source).expanduser().resolve()
    photo_root = Path(args.photo_root).expanduser().resolve() if args.photo_root else source
    if not (source / "inventory" / "store.sqlite").exists():
        raise SystemExit("no store at %s" % (source / "inventory"))

    facts = json.loads(FACTS.read_text()) if FACTS.is_file() else {}
    pin_skus = set(facts.get("pin_skus", []))
    typed_prices: Dict[str, str] = facts.get("typed_prices", {})
    sales: Dict[str, list] = facts.get("sales", {})

    # NEVER A SKU THE DEFAULT 132-CARD SET ALREADY CURATED. Both sets draw from the same
    # real store, and `cards.cid` is UNIQUE on the photograph's own digest (D172) — two
    # different cards can share a SKU's catalogue row, but the base build and this one must
    # never place the SAME physical photograph twice.
    base_manifest = REPO_ROOT / "demo-assets" / "cards.json"
    already_curated = set()
    if base_manifest.is_file():
        already_curated = {e["sku"] for e in json.loads(base_manifest.read_text())}

    os.environ["PKMNSCAN_HOME"] = str(source)
    from store import Store
    from store import photos as store_photos

    rows = dp.fixture_rows()
    snapshot = Store().read()
    relocated = bool(getattr(snapshot.inventory, "photos_relocated", None))

    candidates = []
    for card in snapshot.inventory.cards.values():
        if card.game == "pokemon_code" or not card.name or not card.sku:
            continue
        if card.sku in already_curated:
            continue
        photo = store_photos.find(
            card.cid, card.box, card.index, relocated=relocated, home=photo_root,
        )
        if photo is None:
            continue
        candidates.append((card, photo))

    rng = random.Random(args.seed)
    rng.shuffle(candidates)

    seen_sku: set = set()
    picked = []
    refused = []

    def take(card, photo) -> bool:
        if card.sku in seen_sku:
            return False
        payload = dp.carries_a_qr(photo)
        if payload is not None:
            refused.append(str(photo))
            return False
        seen_sku.add(card.sku)
        picked.append((card, photo))
        return True

    for card, photo in candidates:  # pinned real-fact cards first, guaranteed
        if card.sku in pin_skus:
            take(card, photo)
    for card, photo in candidates:  # then a plain random sample, up to --count
        if len(picked) >= args.count:
            break
        take(card, photo)

    missing_pins = pin_skus - seen_sku

    if PHOTOS.exists():
        for stale in PHOTOS.glob("*.jpg"):
            stale.unlink()
    PHOTOS.mkdir(parents=True, exist_ok=True)

    manifest = []
    for offset, (card, photo) in enumerate(picked):
        name = "%04d.jpg" % offset
        dp.cropped(photo).save(PHOTOS / name, "JPEG", quality=dp.QUALITY, optimize=True)
        row = rows.get(card.sku)
        entry = {
            "photo": name,
            "name": card.name,
            "number": card.number,
            "printed_total": card.printed_total,
            "sku": card.sku,
            "game": card.game,
            "condition": card.condition,
            "rarity": (row or {}).get("Rarity"),
            "market": (row or {}).get("TCG Market Price"),
            "set_name": (row or {}).get("Set Name"),
            "priceable": row is not None,
        }
        if card.sku in typed_prices:
            entry["typed_price"] = typed_prices[card.sku]
        if card.sku in sales:
            # Real dollar amount and real date, nothing else — the owner's own ruling
            # ("sales dollars are ok") never extends to the order it came off.
            entry["sale"] = {
                "unit_price": sales[card.sku][0]["unit_price"],
                "placed_at": sales[card.sku][0]["placed_at"],
            }
        manifest.append(entry)

    EXTRA.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    total = sum((PHOTOS / e["photo"]).stat().st_size for e in manifest)
    print("wrote %d photographs (%.2f MB) and %s" % (
        len(manifest), total / 1024 / 1024, MANIFEST.relative_to(REPO_ROOT)))
    print("  QR-refused  %d" % len(refused))
    for path in refused:
        print("   ", path)
    if missing_pins:
        print("  pin SKU(s) with no photographable candidate: %s" % ", ".join(sorted(missing_pins)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
