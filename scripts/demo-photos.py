#!/usr/bin/env python3
"""Curate real card photographs — and their real identifications — into a tracked set.

WHY THIS EXISTS. The demo drew its own cards until 2026-09-06, which was safe and looked
like a placeholder. The owner's ruling: *"i'd rather it show real photography... just take
some random pics of mine that i made -- that's not a copyright issue."* These are their
photographs of their own cards, taken on their own rig, and they have said to publish them.

THE PHOTOGRAPH AND THE LABEL COME FROM THE SAME CARD, which is the whole reason this reads
the store rather than just copying JPEGs. A real photograph under an invented name is worse
than a drawn one — a viewer who knows the game sees a Heimerdinger captioned `Komala` and
stops believing anything else on the screen. So each entry here carries the identification
the pipeline actually wrote for that photograph, and `demo-seed.py` builds the card from it.

WHAT IS CHECKED BEFORE ANYTHING IS WRITTEN, because this is the one script in the repo that
takes a private photograph and puts it on a path headed for a public host:

  1. NO CODE CARDS, BY DECODE RATHER THAN BY ASSUMPTION. A live unredeemed code card is a
     bearer instrument — the repo's one repo-wide opsec rule — and its whole identification
     IS the QR (D70). So every candidate is run through `codes/qr.py` and REFUSED if
     anything decodes. That is a positive mechanical test on the image itself, not a
     provenance argument about which cards the store thinks it holds.
  2. `game != pokemon_code` as well, because the two tests fail differently: a decode
     catches a mislabelled record, and the label catches a code card whose QR this rig
     could not read. Neither subsumes the other.
  3. IDENTIFIED ONLY. An unidentified card has no name to caption it with.

SELECTED FOR THE JOIN, NOT AT RANDOM, and that constraint is measured rather than assumed.
`--in-fixtures` keeps only cards whose SKU appears in one of `fixtures/`'s exports, because
a run is joined against those and a card the export has never heard of queues as
`no_catalog_row`. Measured on the owner's store 2026-09-06: 1,010 of their Riftbound cards
are in the vendored Riftbound export and 0 of their 542 Pokemon are — theirs are Mega
Evolution, the fixture is SV09. So the boxes that carry a RUN are drawn from the first pool
and the boxes that do not are free to use the second: inventory, sales and orders need no
export, and only join, emit and pricing do.

    ./scripts/demo-photos.py --source ~/Developer/pkmnscan --count 122

Writes `demo-assets/`, which IS tracked — see the pre-commit hook's narrow exception and
the reason beside it. Re-run it only to change the set; the demo seed reads what it wrote.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

ASSETS = REPO_ROOT / "demo-assets"
PHOTOS = ASSETS / "photos"
MANIFEST = ASSETS / "cards.json"

# The published width. The card fills most of the frame after the crop below, so this is
# larger in CARD pixels than the number suggests. Measured over the owner's photographs:
# ~26 KB each at this width and quality, so a 122-card set is ~3.2 MB tracked — paid once,
# and the reason the crop is worth doing at all.
OUT_W, OUT_H = 360, 540
QUALITY = 72

FIXTURES = (
    ("sv09_export_untouched.csv", "pokemon"),
    ("onepiece_export_untouched.csv", "one_piece"),
    ("riftbound_export_untouched.csv", "riftbound"),
)


def fixture_rows() -> Dict[str, dict]:
    """Every SKU the vendored exports carry, as SKU -> row."""
    rows: Dict[str, dict] = {}
    for name, _game in FIXTURES:
        path = REPO_ROOT / "fixtures" / name
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for record in csv.DictReader(handle):
                rows[record["TCGplayer Id"]] = record
    return rows


# ------------------------------------------------------------------------------ the guard


def carries_a_qr(path: Path) -> Optional[str]:
    """The QR payload in this photograph, or None. A code card's whole identity (D70).

    THE ONE CHECK THAT LOOKS AT THE IMAGE. Everything else here reasons about what the store
    SAYS a card is, which is exactly the assumption a mislabelled record breaks. `codes/qr.py`
    is the same decoder the code-card track runs — measured at 140/140 on physically possible
    frames — so a clean read here is a real answer rather than a hopeful one.

    Decoded at FULL resolution, before the downscale. A 1 cm QR at 360px wide is a smear no
    decoder can read, so checking the published copy would pass everything and prove nothing.
    """
    from codes import qr

    try:
        read = qr.decode(path)
    except qr.QrUnavailable:
        # UNAVAILABLE IS NOT ABSENT, and this is the one place that distinction is worth a
        # hard stop. Publishing a photograph because the decoder could not be loaded is the
        # exact failure the check exists to prevent.
        raise SystemExit(
            "refusing: the QR decoder is unavailable, so no photograph can be cleared of "
            "carrying a live code. Install requirements.txt (zxing-cpp) and re-run."
        ) from None
    if read is None:
        return None
    return read.payload if getattr(read, "payload", None) else "<undecoded symbol>"


# -------------------------------------------------------------------------------- the crop


def cropped(path: Path):
    """The card, centred at a consistent size, with enough stand around it to read as a photo.

    NOT A TIGHT CROP AND NOT A RAW ONE. A card cut to its own edges looks like catalogue art;
    what this product photographs is a card ON A STAND under a lamp, and the demo should look
    like what the rig produces. But padding the detected box by a percentage — the first
    version — inherits every variation in how big the card happened to sit in frame, and a
    contact sheet of it showed cards ranging from filling the frame to floating in a third of
    it, with one clipped at the edge.

    So the box is not padded, it is RE-FRAMED: a window of fixed aspect is centred on the
    detected card and sized so the card is always the same fraction of the height. Every
    published photograph then has the same composition, which is what makes a grid of them
    look like one set rather than 122 accidents. A window that would leave the image is slid
    back inside rather than clamped narrower, so the aspect never changes.

    `geometry.detect.detect_card` returns None rather than guessing, which is its whole
    contract — a miss falls back to a fixed centre band. Over the owner's photographs the
    detector answers on essentially all of them.
    """
    from PIL import Image
    from geometry.detect import detect_card

    image = Image.open(path).convert("RGB")
    width, height = image.size

    try:
        box = detect_card(str(path))
    except Exception:
        box = None

    if box is None:
        left, right, top, bottom = 0.04, 0.96, 0.14, 0.94
        window_w = (right - left) * width
        window_h = (bottom - top) * height
        cx = (left + right) / 2 * width
        cy = (top + bottom) / 2 * height
    else:
        card_h = (box.bottom - box.top) * height
        cx = (box.left + box.right) / 2 * width
        cy = (box.top + box.bottom) / 2 * height
        # The card occupies this much of the frame's height, always. Chosen by looking at a
        # contact sheet: tighter and the stand disappears, looser and the card stops being
        # the subject.
        window_h = card_h / 0.80
        window_w = window_h * OUT_W / OUT_H

    # Slide the window back inside the image rather than shrinking it — a clamped window
    # changes aspect, and a set with two aspects is the inconsistency this function exists
    # to remove. A window larger than the image in either axis is scaled down whole.
    scale = min(1.0, width / window_w, height / window_h)
    window_w, window_h = window_w * scale, window_h * scale
    cx = min(max(cx, window_w / 2), width - window_w / 2)
    cy = min(max(cy, window_h / 2), height - window_h / 2)

    image = image.crop((
        int(cx - window_w / 2), int(cy - window_h / 2),
        int(cx + window_w / 2), int(cy + window_h / 2),
    ))
    return image.resize((OUT_W, OUT_H), Image.LANCZOS)


# ----------------------------------------------------------------------------- the picking


def candidates(source: Path, rows: Dict[str, dict]):
    """Every card in `source` that may be published, newest box first.

    Two pools, because they are good for different things (see the header). `joinable` is
    what a RUN can be built over — its SKU is in a vendored export, so the join finds a
    catalogue row and the pricing table is real arithmetic. `other` is a real card with a
    real name that no vendored export prices, which is everything the inventory, order and
    sale screens need and nothing the pipeline does.
    """
    os.environ["PKMNSCAN_HOME"] = str(source)
    from store import Store

    snapshot = Store().read()
    joinable: List[Tuple[object, Optional[dict]]] = []
    other: List[Tuple[object, Optional[dict]]] = []

    for card in snapshot.inventory.cards.values():
        if card.game == "pokemon_code":
            continue
        if not card.name or not card.sku:
            continue
        photo = source / "captures" / "cards" / ("box%d" % int(card.box)) / (
            "%04d.jpg" % int(card.index)
        )
        if not photo.is_file():
            continue
        entry = (card, photo)
        (joinable if card.sku in rows else other).append(entry)

    return joinable, other


def take(pool, want: int, rng: random.Random, rows: Dict[str, dict], seen_sku: set):
    """`want` cards off `pool`, QR-checked, one per SKU.

    ONE PER SKU so the demo's cards are distinct cards rather than the same card four times:
    the owner's bulk holds many duplicates, and a box drawn from them would show one name
    repeated down the list. Copies still exist in the demo — the seed makes them — but they
    are made deliberately rather than by accident of sampling.
    """
    rng.shuffle(pool)
    picked = []
    refused = []
    for card, photo in pool:
        if len(picked) >= want:
            break
        if card.sku in seen_sku:
            continue
        payload = carries_a_qr(photo)
        if payload is not None:
            # NEVER PUBLISHED, AND NEVER PRINTED. The payload is the instrument; naming the
            # file is enough to go and look.
            refused.append(str(photo))
            continue
        seen_sku.add(card.sku)
        picked.append((card, photo, rows.get(card.sku)))
    return picked, refused


# ------------------------------------------------------------------------------- the entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True,
        help="a checkout whose store holds the photographs (the main one, normally)",
    )
    parser.add_argument("--count", type=int, default=122)
    parser.add_argument(
        "--joinable", type=int, default=86,
        help="how many of them must be priceable against a vendored export",
    )
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not (source / "inventory" / "store.sqlite").exists():
        raise SystemExit("no store at %s" % (source / "inventory"))

    rng = random.Random(args.seed)
    rows = fixture_rows()
    joinable, other = candidates(source, rows)
    print("candidates: %d priceable against a fixture, %d not" % (len(joinable), len(other)))

    seen: set = set()
    want_joinable = min(args.joinable, args.count)
    first, refused_a = take(joinable, want_joinable, rng, rows, seen)
    second, refused_b = take(other, args.count - len(first), rng, rows, seen)
    picked = first + second
    refused = refused_a + refused_b

    if refused:
        print("REFUSED %d photograph(s) carrying a decodable QR — a code card is a bearer "
              "instrument and never reaches a tracked path:" % len(refused))
        for path in refused[:5]:
            print("   ", path)

    if PHOTOS.exists():
        for stale in PHOTOS.glob("*.jpg"):
            stale.unlink()
    PHOTOS.mkdir(parents=True, exist_ok=True)

    manifest = []
    for offset, (card, photo, row) in enumerate(picked):
        name = "%04d.jpg" % offset
        cropped(photo).save(PHOTOS / name, "JPEG", quality=QUALITY, optimize=True)
        manifest.append({
            "photo": name,
            # THE IDENTIFICATION THIS PHOTOGRAPH ACTUALLY GOT, so the caption and the picture
            # are the same card. `number`/`printed_total` are stored as the two halves the
            # record holds, because `cardNumber.ts:collectorNumber` composes them (D67).
            "name": card.name,
            "number": card.number,
            "printed_total": card.printed_total,
            "sku": card.sku,
            "game": card.game,
            "condition": card.condition,
            # From the export where there is one — the price and rarity the pipeline would
            # read. Absent for a card no vendored export carries, which is what
            # `priceable` says out loud rather than leaving to be discovered.
            "rarity": (row or {}).get("Rarity"),
            "market": (row or {}).get("TCG Market Price"),
            "set_name": (row or {}).get("Set Name"),
            "priceable": row is not None,
        })

    ASSETS.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    total = sum((PHOTOS / e["photo"]).stat().st_size for e in manifest)
    games: Dict[str, int] = {}
    for entry in manifest:
        games[entry["game"]] = games.get(entry["game"], 0) + 1
    print()
    print("wrote %d photographs (%.1f MB) and %s" % (
        len(manifest), total / 1024 / 1024, MANIFEST.relative_to(REPO_ROOT)))
    print("  priceable   %d" % sum(1 for e in manifest if e["priceable"]))
    print("  games       %s" % ", ".join("%s %d" % kv for kv in sorted(games.items())))
    print("  QR-refused  %d" % len(refused))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
