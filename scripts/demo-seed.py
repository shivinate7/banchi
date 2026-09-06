#!/usr/bin/env python3
"""Seed a demo store — real catalogue rows, synthetic photographs, no real inventory.

WHAT THIS IS FOR. The product is shareable only if somebody who has never seen it can
look at a full one. The owner's real store is not that: it is their cards, their buyers
and their money, and `inventory/` has never been in git for exactly that reason. So this
builds a store that is *shaped* like a real one out of material that is safe to publish.

WHAT IS REAL AND WHAT IS NOT, because the distinction is the whole design:

  REAL      the catalogue. Every card here is drawn from `fixtures/`, which are untouched
            TCGplayer Filtered Exports — real SKUs, real names, real numbers, real market
            prices. So the joins are real joins, the pricing table is real arithmetic,
            and a viewer reading `8608039 · Alcremie ex · 075/159 · $0.67` is reading
            something TCGplayer actually published.

  INVENTED   which of those cards are in which box at which index, what sold, what is
            held back and to whom it shipped. None of it describes a physical object.

  SYNTHETIC  the photographs. `card_image()` draws them. NOT real card art and not real
            photographs: a published demo carries neither somebody else's illustration
            nor a picture of the owner's desk, and a drawn card is reproducible from this
            file, which a photograph never is.

DETERMINISTIC. One RNG, seeded from a constant, so re-running writes the same store. The
recorder downstream turns this into a fixture bundle, and a bundle that changed every time
it was built would make every rebuild a diff nobody can read.

    PKMNSCAN_HOME=demo ./scripts/demo-seed.py

Refuses to touch a store that already holds cards unless `--force` says so, because
`PKMNSCAN_HOME` unset means the checkout's own store and that is somebody's real one.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from store import Box, Card, Listing, Store  # noqa: E402
from store import files as store_files  # noqa: E402
from store import orders as orders_mod  # noqa: E402
from store.queues import QueueEntry  # noqa: E402

SEED = 20260906
FIXTURES = REPO_ROOT / "fixtures"

# The demo's clock. Every stamp below is an offset from this, so the store reads as one
# that has been worked for a few weeks rather than one built in a single instant.
NOW = datetime(2026, 9, 6, 14, 30, tzinfo=timezone.utc)


def stamp(days_ago: float = 0.0) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- catalogue


class Row:
    """One export row, reduced to what a card record needs."""

    __slots__ = ("sku", "name", "number", "printed_total", "condition", "rarity",
                 "market", "set_name", "game", "printed")

    def __init__(self, record: dict, game: str) -> None:
        self.sku = record["TCGplayer Id"]
        self.name = record["Product Name"]
        self.number = record["Number"]
        self.condition = record["Condition"]
        self.rarity = record["Rarity"]
        self.set_name = record["Set Name"]
        self.game = game
        self.market = record["TCG Market Price"]
        # THE EXPORT'S `Number` IS THE WHOLE STRING; A CARD RECORD HOLDS THE TWO HALVES.
        # `app/src/cardNumber.ts:collectorNumber` composes `number/printed_total` (D67), so a
        # record carrying the full `013/159` in `number` renders `013/159/159`. Measured:
        # the home screen's hero drew `009/298/298` before this split. One Piece and
        # Riftbound promos carry no denominator at all and keep the identifier verbatim,
        # which is `pipeline/games.py`'s per-game rule and why this is a split rather than
        # a strip.
        self.printed = self.number
        if "/" in self.number:
            head, self.printed_total = self.number.split("/", 1)
            self.number = head
        else:
            self.printed_total = None

    @property
    def price(self) -> float:
        try:
            return float(self.market)
        except (TypeError, ValueError):
            return 0.0


def read_rows(path: Path, game: str) -> List[Row]:
    """Real singles out of a real export.

    A real CSV reader, never `split(",")` — product names carry commas and apostrophes
    (`Billy & O'Nare`), which is CLAUDE.md's rule and the skill's.
    """
    rows: List[Row] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for record in csv.DictReader(handle):
            number = (record.get("Number") or "").strip()
            condition = (record.get("Condition") or "").strip()
            market = (record.get("TCG Market Price") or "").strip()
            # Sealed product carries no Number and an `Unopened` condition — 450 of
            # Riftbound's rows are exactly that. A box of cards holds singles.
            if not number or not condition or condition == "Unopened":
                continue
            if not market:
                continue
            rows.append(Row(record, game))
    return rows


def catalogue() -> Dict[str, List[Row]]:
    return {
        "pokemon": read_rows(FIXTURES / "sv09_export_untouched.csv", "pokemon"),
        "one_piece": read_rows(FIXTURES / "onepiece_export_untouched.csv", "one_piece"),
        "riftbound": read_rows(FIXTURES / "riftbound_export_untouched.csv", "riftbound"),
    }


# ------------------------------------------------------------------------ photographs

# Sized for a static bundle rather than for the rig. The real camera asks for 3840x2160
# (`app/src/useCamera.ts`); a demo ships ~120 of these over the wire to somebody on a
# phone, so they are drawn at the size the review screen actually paints them and no
# larger. Measured: ~14 KB each at quality 72, so the whole set is under 2 MB.
PHOTO_W, PHOTO_H = 360, 480
PHOTO_QUALITY = 72

# Per-game plate colours. Not the card's real art — a flat plate that reads as "a card of
# this game" at thumbnail size, which is the only job these images have.
PLATES = {
    "pokemon": ((208, 176, 68), (150, 116, 32)),
    "one_piece": ((176, 74, 62), (116, 42, 36)),
    "riftbound": ((70, 104, 168), (38, 60, 112)),
}
STAGE = (28, 28, 32)


def _font(size: int):
    from PIL import ImageFont

    # DejaVu ships with Pillow. A named system font would make the bundle depend on which
    # machine built it, which is the one property a reproducible seed cannot have.
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/DejaVuSans.ttf", size
            )
        except OSError:
            return ImageFont.load_default()


def card_image(row: "Row", rng: random.Random):
    """A drawn card on a dark stand — what the capture rig's frame looks like in outline.

    Deliberately NOT a real photograph and NOT real card art. Two reasons, both hard: the
    illustration on a real card belongs to its publisher, and a real photograph of this
    rig is a picture of the owner's desk and their stock. Neither belongs in something
    published to strangers. What a viewer needs from this image is that a card is there,
    roughly where the crop expects it, with the name legible — that is all the review
    screen asks of it, and a drawn plate delivers it.
    """
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("RGB", (PHOTO_W, PHOTO_H), STAGE)
    draw = ImageDraw.Draw(image)

    # The stand: a soft pool of light behind where the card sits, so the frame reads as a
    # photograph rather than as a diagram.
    glow = Image.new("L", (PHOTO_W, PHOTO_H), 0)
    ImageDraw.Draw(glow).ellipse((-40, PHOTO_H // 4, PHOTO_W + 40, PHOTO_H), fill=76)
    glow = glow.filter(ImageFilter.GaussianBlur(48))
    image.paste(Image.new("RGB", (PHOTO_W, PHOTO_H), (80, 84, 99)), (0, 0), glow)

    # The card. Inset with a little jitter, because a hand puts it down slightly
    # differently every time and a grid of pixel-identical crops looks like a mock.
    jx, jy = rng.randint(-6, 6), rng.randint(-5, 5)
    left, top = 46 + jx, 40 + jy
    right, bottom = PHOTO_W - 46 + jx, PHOTO_H - 52 + jy

    shadow = Image.new("L", (PHOTO_W, PHOTO_H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        (left + 2, top + 8, right + 2, bottom + 10), radius=14, fill=150
    )
    image.paste(
        Image.new("RGB", (PHOTO_W, PHOTO_H), (8, 8, 11)),
        (0, 0),
        shadow.filter(ImageFilter.GaussianBlur(9)),
    )
    draw.rounded_rectangle((left, top, right, bottom), radius=14, fill=(247, 245, 240))

    face, deep = PLATES.get(row.game, PLATES["pokemon"])
    inner = (left + 12, top + 12, right - 12, bottom - 74)

    # The art plate, as a vertical wash. Two flat rectangles read as a print error.
    plate = Image.new("RGB", (inner[2] - inner[0], inner[3] - inner[1]))
    pd = ImageDraw.Draw(plate)
    for step in range(plate.height):
        blend = step / max(plate.height - 1, 1)
        pd.line(
            [(0, step), (plate.width, step)],
            fill=tuple(int(face[c] + (deep[c] - face[c]) * blend) for c in range(3)),
        )

    # A diagonal specular band — the sheen a real card throws back at a camera under a
    # desk lamp. This is what stops the plate reading as a colour swatch, and it is the
    # single cheapest thing that makes the frame look photographed.
    sheen = Image.new("L", (plate.width, plate.height), 0)
    sd = ImageDraw.Draw(sheen)
    span = plate.width + plate.height
    for offset in range(-plate.height, plate.width, 3):
        distance = abs(offset - span * 0.22) / (plate.width * 0.55)
        strength = int(max(0.0, 1.0 - distance) * 74)
        if strength:
            sd.line([(offset, 0), (offset + plate.height, plate.height)],
                    fill=strength, width=3)
    plate.paste(
        Image.new("RGB", plate.size, (255, 255, 255)),
        (0, 0),
        sheen.filter(ImageFilter.GaussianBlur(11)),
    )
    image.paste(plate, (inner[0], inner[1]))
    draw.rounded_rectangle(inner, radius=8, outline=(255, 255, 255, 60), width=1)

    # A rarity pip, bottom-right of the plate. Small, but it is the kind of mark a real
    # card carries and its absence is what makes a drawn one look like a placeholder.
    pip = (inner[2] - 26, inner[3] - 26, inner[2] - 10, inner[3] - 10)
    draw.ellipse(pip, fill=(250, 248, 242), outline=(0, 0, 0), width=1)

    name = row.name if len(row.name) <= 26 else row.name[:25] + "\u2026"
    draw.text((left + 16, bottom - 62), name, font=_font(19), fill=(24, 24, 28))
    draw.text(
        (left + 16, bottom - 34),
        "%s  \u00b7  %s" % (row.printed, row.rarity),
        font=_font(14),
        fill=(96, 96, 104),
    )
    return image


def write_photo(path: Path, row: "Row", rng: random.Random) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    card_image(row, rng).save(path, format="JPEG", quality=PHOTO_QUALITY, optimize=True)


# ------------------------------------------------------------------------------- boxes

# The shape of the demo store. Four boxes, chosen so that every case a screen has to draw
# is present somewhere — an open box with dividers, a sealed one with a frozen capacity, a
# mixed box with NO dividers (D10's undeclared box, which renders as one section), and a
# box holding the departed. A demo where every box is the same box teaches nothing.
BOXES = (
    {
        "box": 1,
        "name": "SV Bulk A",
        "game": "pokemon",
        "count": 42,
        "sections": [1, 15, 29],
        "section_names": {"1": "Commons", "15": "Uncommons", "29": "Holos"},
        "state": "open",
        "created": 24.0,
    },
    {
        "box": 2,
        "name": "One Piece Commons",
        "game": "one_piece",
        "count": 28,
        "sections": [1, 16],
        "section_names": {"1": "OP15", "16": "Promos"},
        "state": "open",
        "created": 17.0,
    },
    {
        "box": 3,
        "name": "RB Epics",
        "game": "riftbound",
        "count": 34,
        "sections": [1, 12, 24],
        "section_names": {"1": "Origins", "12": "Legacy", "24": "Signatures"},
        "state": "closed",
        "created": 31.0,
    },
    {
        # No dividers on purpose: D10 amended, an undeclared box renders as ONE section and
        # `card` is the index. Somebody looking at this demo should see that case, because
        # it is what every box looks like before anybody divides one.
        "box": 4,
        "name": "Mixed Singles",
        "game": None,
        "count": 18,
        "sections": [],
        "section_names": {},
        "state": "open",
        "created": 9.0,
    },
)

CONDITIONS = ("Near Mint", "Lightly Played")

# The queue's reasons, spread across several real codes rather than repeating one. Every
# member is a key of `app/src/reasons.ts:REASON_LABELS` — a code that map lacks renders on
# screen as a raw enum, and D78 groups the queue BY reason, so a queue carrying one code has
# nothing to group.
REASONS = (
    "set_ambiguous",
    "low_confidence",
    "duplicate_condition",
    "ambiguous_no_signal",
    "number_unread_name_matched",
)


def pick_rows(rows: List[Row], count: int, rng: random.Random) -> List[Row]:
    """`count` distinct SKUs, biased toward the cheap end.

    Real bulk is mostly worth pennies — the Gate B run's whole review queue was $0.04 to
    $0.40 — and a demo drawn uniformly from the export would show a drawer of chase cards
    and misrepresent both the pricing screen and the sub-threshold split. So: mostly cheap,
    with a few worth real money, which is what a box of bulk actually holds.
    """
    cheap = [r for r in rows if 0 < r.price < 1.0]
    mid = [r for r in rows if 1.0 <= r.price < 8.0]
    dear = [r for r in rows if r.price >= 8.0]

    want_dear = max(1, count // 14)
    want_mid = max(2, count // 5)
    want_cheap = count - want_dear - want_mid

    chosen: List[Row] = []
    for pool, want in ((cheap, want_cheap), (mid, want_mid), (dear, want_dear)):
        if not pool:
            continue
        chosen.extend(rng.sample(pool, min(want, len(pool))))

    # Top up from anywhere if a pool was too thin to fill its share.
    if len(chosen) < count:
        rest = [r for r in rows if r not in chosen]
        chosen.extend(rng.sample(rest, min(count - len(chosen), len(rest))))

    rng.shuffle(chosen)
    return chosen[:count]


# ------------------------------------------------------------------------------ states

# How a real drawer is distributed. Most cards are listed and sitting there; a slice has
# sold; a couple were damaged and retired (D26); one was transplanted to another box (D83);
# and a tail at the end is photographed but not yet identified, which is what gives the
# runs screen and the review queue something to be about.
def state_for(position: int, count: int, rng: random.Random) -> str:
    tail = count - int(count * 0.13)
    if position >= tail:
        return "captured"
    roll = rng.random()
    if roll < 0.14:
        return "sold"
    if roll < 0.16:
        return "retired"
    if roll < 0.175:
        return "moved"
    return "identified"


def build_store(force: bool) -> dict:
    """Write the whole demo store. Returns a summary for the caller to print."""
    rng = random.Random(SEED)
    pools = catalogue()
    store = Store()
    home = store_files.home()

    counts = {
        "boxes": 0, "cards": 0, "photos": 0, "listings": 0,
        "sold": 0, "retired": 0, "moved": 0, "captured": 0, "review": 0,
    }
    # Everything the corpus and the recorder need, collected as we go.
    placed: List[Tuple[Card, Row]] = []

    with store.write() as snapshot:
        inventory = snapshot.inventory

        if len(inventory.cards) and not force:
            raise SystemExit(
                "refusing: %s already holds %d cards. This is a real store unless "
                "PKMNSCAN_HOME says otherwise — pass --force if you meant it."
                % (home, len(inventory.cards))
            )

        for spec in BOXES:
            number = spec["box"]
            inventory.boxes[str(number)] = Box(
                box=number,
                name=spec["name"],
                sections=list(spec["sections"]),
                section_names=dict(spec["section_names"]),
                state="closed" if spec["state"] == "closed" else "open",
                capacity=spec["count"] if spec["state"] == "closed" else None,
                created_at=stamp(spec["created"]),
                closed_at=stamp(spec["created"] - 6) if spec["state"] == "closed" else None,
            )
            counts["boxes"] += 1

            # Box 4 is deliberately mixed — a real "everything else" drawer holds more than
            # one game, and D21 makes game a per-card claim rather than a mode.
            if spec["game"] is None:
                rows: List[Row] = []
                per = spec["count"] // 3 + 1
                for game in ("pokemon", "one_piece", "riftbound"):
                    rows.extend(pick_rows(pools[game], per, rng))
                rng.shuffle(rows)
                rows = rows[: spec["count"]]
            else:
                rows = pick_rows(pools[spec["game"]], spec["count"], rng)

            age = spec["created"]
            for offset, row in enumerate(rows):
                index = offset + 1
                state = state_for(offset, len(rows), rng)
                captured_at = stamp(age - offset * (age / max(len(rows), 1)) * 0.8)

                card = Card(
                    box=number,
                    index=index,
                    photo="captures/cards/box%d/%04d.jpg" % (number, index),
                    game=row.game,
                    capture_id="demo-%d-%04d" % (number, index),
                    captured_at=captured_at,
                    state=state,
                    state_at=captured_at,
                    condition=row.condition,
                    metadata_finish=None,
                )
                if state != "captured":
                    # An identified card knows what it is. A captured one does not yet —
                    # that is the whole difference, and the review queue is where the
                    # difference gets settled.
                    card.name = row.name
                    card.number = row.number
                    card.printed_total = row.printed_total
                    card.sku = row.sku
                    card.confidence = "high"
                    card.run = "demo-run-%d" % number
                if state == "retired":
                    card.retire_reason = "damaged"
                if state == "moved":
                    card.moved_to = "4/%d" % (rng.randint(1, 18))

                inventory.cards[card.key] = card
                placed.append((card, row))
                counts["cards"] += 1
                if state in counts:
                    counts[state] += 1

                write_photo(
                    home / "captures" / "cards" / ("box%d" % number) / ("%04d.jpg" % index),
                    row,
                    rng,
                )
                counts["photos"] += 1

        # D83's third door — a card that left its box by being MOVED rather than sold or
        # retired — is rare enough in the distribution above to miss a seeding entirely, and
        # a state no demo store ever holds is a state no viewer ever sees. Guarantee one.
        if not any(c.state == "moved" for c, _ in placed):
            for card, _ in placed:
                if card.state == "identified" and card.box == 1:
                    card.state = "moved"
                    card.moved_to = "4/7"
                    inventory.cards[card.key] = card
                    counts["moved"] += 1
                    counts["identified"] = counts.get("identified", 0) - 1
                    break

        # ------------------------------------------------------------------- listings
        # One row per SKU, holding QUANTITIES rather than addresses (D7 amended). `live` is
        # a READING of what TCGplayer holds and carries the moment it was taken (D87), so
        # every row written here gets a `live_as_of` — a row without one reads as "never
        # read", and the demo's whole point is that it has been.
        by_sku: Dict[str, List[Card]] = {}
        for card, _row in placed:
            if card.sku and card.state in ("identified", "sold"):
                by_sku.setdefault(card.sku, []).append(card)

        for sku, cards in by_sku.items():
            on_hand = [c for c in cards if c.state == "identified"]
            if not on_hand:
                continue
            pushed = len(cards)
            # The live cap is 4 (D7). More copies than that on hand is the ordinary case in
            # bulk, and the remainder waiting as backstock is what the cap arithmetic is for.
            live = min(len(on_hand), 4)
            inventory.listings[sku] = Listing(
                sku=sku,
                condition=cards[0].condition,
                pushed=pushed,
                staged=0,
                live=live,
                at=stamp(2.0),
                live_as_of=stamp(1.5),
            )
            counts["listings"] += 1

        # ---------------------------------------------------------------- review queue
        # Real ambiguity, not filler. Every entry here is a card the pipeline could not
        # settle on its own, carrying the candidates it was choosing between — which is
        # what the review screen exists to draw (D4, D46).
        review_pool = [
            (card, row) for card, row in placed if card.state == "captured"
        ][:9]
        for offset, (card, row) in enumerate(review_pool):
            siblings = [
                r for r in pools[row.game]
                if r.name == row.name and r.sku != row.sku
            ][:2]
            candidates = [
                {
                    "sku": alt.sku,
                    "name": alt.name,
                    "number": alt.number,
                    "condition": alt.condition,
                    "market": alt.market,
                    "rarity": alt.rarity,
                }
                for alt in ([row] + siblings)
            ]
            # REAL CODES, out of `app/src/reasons.ts:REASON_LABELS`. A code that map has no
            # entry for renders as a raw enum on screen — which is what an invented
            # `variant_ambiguous` did — and D78 makes a reason a HEADING the queue groups
            # under, so the spread across several is the thing worth demonstrating.
            reason = REASONS[offset % len(REASONS)] if len(candidates) > 1 else "no_catalog_row"
            snapshot.review.upsert(
                QueueEntry(
                    position=card.key,
                    box=card.box,
                    index=card.index,
                    label="Box %d · Card %d" % (card.box, card.index),
                    photo=card.photo,
                    read={
                        "name": row.name,
                        "number": row.number,
                        "game": row.game,
                        "set": row.set_name,
                    },
                    confidence="low" if reason == "no_catalog_row" else "medium",
                    reason=reason,
                    candidates=candidates,
                    first_seen=stamp(3.0),
                    market=row.market,
                )
            )
            counts["review"] += 1

        # ---------------------------------------------------------------- order ledger
        # Orders over SKUs the store can actually fill, so `#/orders` resolves each line to
        # real copies at real positions and the pull is a real walk. An order naming a SKU
        # this store has never held would draw an empty panel and teach the viewer nothing.
        sellable = [sku for sku, cards in by_sku.items()
                    if any(c.state == "identified" for c in cards)]
        rng.shuffle(sellable)

        orders: List = []
        cursor = 0
        for n in range(7):
            width = rng.choice((1, 1, 2, 2, 3, 5))
            skus = sellable[cursor:cursor + width]
            cursor += width
            if not skus:
                break
            lines = []
            for sku in skus:
                match = next(
                    (r for _, r in placed if r.sku == sku), None
                )
                lines.append(
                    orders_mod.OrderLine(
                        sku=sku,
                        quantity=rng.choice((1, 1, 1, 2)),
                        name=match.name if match else None,
                        number=match.number if match else None,
                        condition=match.condition if match else None,
                        rarity=match.rarity if match else None,
                        unit_price=match.market if match else None,
                    )
                )
            placed_at = stamp(rng.uniform(0.5, 11.0))
            orders.append(
                orders_mod.OrderRecord(
                    source="tcgplayer",
                    number="A2FFC195-%06d-%05d" % (rng.randint(1, 999999), n + 7),
                    placed_at=placed_at,
                    status="Ready to ship" if n > 1 else "Shipped",
                    lines=lines,
                    first_seen=placed_at,
                )
            )
        snapshot.ledger.ingest(orders)

        # Two of them are partly pulled, so the screen has a half-finished order to draw —
        # an order ledger where every order is untouched shows only one of the two states
        # the pull actually moves between.
        for order in orders[:2]:
            line = order.lines[0]
            copies = [
                c.capture_id for c, _ in placed
                if c.sku == line.sku and c.state == "identified" and c.capture_id
            ][:1]
            if copies:
                snapshot.ledger.record_pull(order.key, line.sku, copies)

    counts["orders"] = len(orders)
    return counts, placed


# ---------------------------------------------------------------------- pricing corpus


def write_corpus(placed: List[Tuple[Card, "Row"]]) -> int:
    """The operator's answers, one file for the whole store, keyed by SKU (D86).

    THE SHAPE IS `pipeline/corpus.py`'s, NOT AN INVENTED ONE. Answers live under `skus` and
    the standing rule under `policy`; a first attempt wrote a top-level `answers` map, which
    `Corpus.parse` round-tripped into `unknown` and no reader ever saw — the join reported
    "0 answer(s) in the corpus" over 90 of them. Written through `Corpus.parse` so that if
    this shape is ever wrong again it raises here rather than being silently kept.

    THREE DELIBERATE HOLDS (D49), because a demo where every card has a price shows only half
    the screen. Holding a card back on purpose — with a reason, a watch and a note — is what
    makes `#/pricing` a judgement tool rather than a calculator, and it is the half a viewer
    would not otherwise know exists. The reasons are the real vocabulary
    (`decisions.WITHHOLD_REASONS`); anything else is refused at parse.
    """
    from pipeline import corpus as corpus_mod

    priced = [(c, r) for c, r in placed if c.sku and c.state == "identified"]
    seen = set()
    unique = []
    for card, row in priced:
        if card.sku in seen:
            continue
        seen.add(card.sku)
        unique.append((card, row))

    holds = (
        {
            "withheld": "bullish",
            "watch_above": "5.00",
            "note": "Reprint rumour didn't land. Holding for the post-rotation bump.",
        },
        {
            "withheld": "keeping",
            "note": "Two live on the market and both are LP. Not racing them down.",
        },
        {
            "withheld": "next_batch",
            "watch_above": "2.50",
            "note": "Edge whitening on the copy in box 3 — re-grade before it goes up.",
        },
    )

    # The dearest three take the holds: realistic, and the useful demo, because a hold is a
    # decision you make about a card worth deciding about.
    unique.sort(key=lambda pair: pair[1].price, reverse=True)
    skus: Dict[str, object] = {}
    for offset, (card, row) in enumerate(unique):
        if offset < len(holds):
            skus[card.sku] = dict(holds[offset])
            continue
        skus[card.sku] = "%.2f" % max(round(row.price * 1.08, 2), 0.49)

    payload = {
        "version": 1,
        "skus": skus,
        "policy": {
            "rule": "match",
            "basis": "market",
            "sub_threshold": {"flat": "0.49"},
        },
    }
    corpus_mod.Corpus.parse(payload).write()
    return len(skus)


# ------------------------------------------------------------------------------- entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true",
        help="seed over a store that already holds cards",
    )
    args = parser.parse_args()

    home = store_files.home()
    if home == REPO_ROOT and not os.environ.get(store_files.HOME_ENV):
        raise SystemExit(
            "refusing: PKMNSCAN_HOME is unset, so this would seed the checkout's OWN "
            "store at %s. Run it as `PKMNSCAN_HOME=demo %s`."
            % (home / "inventory", Path(__file__).name)
        )

    counts, placed = build_store(args.force)
    counts["answers"] = write_corpus(placed)

    home = store_files.home()
    counts["runs"] = 0
    for box, whole_box in ((1, True), (3, False)):
        if write_run(placed, box, home, whole_box) is not None:
            counts["runs"] += 1

    print("demo store seeded at %s" % home)
    for key in ("boxes", "cards", "photos", "listings", "answers", "review",
                "runs", "orders", "sold", "retired", "moved", "captured"):
        print("  %-9s %d" % (key, counts.get(key, 0)))
    return 0



# --------------------------------------------------------------------------------- runs


def write_run(
    placed: List[Tuple[Card, "Row"]], box: int, home: Path, whole_box: bool = True
) -> Optional[Path]:
    """A run directory over one box, in the shape `pkmnscan identify` leaves behind.

    HAND-BUILT AND THEN JOINED FOR REAL, which is the whole point. Identification is the one
    step in this pipeline that costs money — a Batch API call per card — so a demo cannot run
    it, and a demo without a run leaves TWO of the six stages empty: `#/runs` has nothing to
    list and `#/pricing`'s worklist is driven by joined runs, so it draws nothing either.

    Writing `identifications.json` by hand is explicitly supported rather than a trick:
    `cli/resolve.py:_rarity_claim` names "a hand-made or recovered identifications file" as a
    case it defends, and `join` and `emit` are both free and re-runnable by construction. So
    the expensive step is simulated and every step after it is REAL — the join runs against
    the real fixture export, the catalogue lookup is a real lookup, the cap arithmetic is
    real arithmetic, and `pricing.json` is what the pipeline itself computed.

    The identification is what the model WOULD have returned for a card we already know the
    answer for, at the confidence a real read carries. Nothing here invents a card: the
    values come from the export row the seed placed in that slot.
    """
    from cli import runs as run_files

    rows = [(c, r) for c, r in placed if c.box == box and c.state != "captured"]
    if not rows:
        return None

    name = "demo-box%d" % box
    directory = home / "runs" / name
    directory.mkdir(parents=True, exist_ok=True)

    cards_payload = {}
    for card, row in rows:
        cards_payload["%d/%d" % (card.box, card.index)] = {
            "photo": "captures/cards/box%d/%04d.jpg" % (card.box, card.index),
            "box": card.box,
            "index": card.index,
            "set_hint": None,
            "metadata_finish": None,
            "rarity_claim": None,
            "game": card.game,
            "strategy": card.game,
            "note": None,
            "variant_from_flag": None,
            "position_source": "sidecar",
            "sidecar_problem": None,
            "status": "ok",
            "error": None,
            "cached": True,
            "stale_prompt": False,
            "detection": None,
            "retries": 0,
            "retry_reasons": [],
            "identification": {
                "name": row.name,
                "number": row.number,
                "printed_total": row.printed_total,
                # A real run is not uniformly confident, and the review queue's whole reason
                # for existing is the rows that are not. One in nine reads low.
                "confidence": "low" if (card.index % 9 == 0) else "high",
                "finish": None,
            },
            "photo_sha256": None,
        }

    (directory / run_files.IDENTIFICATIONS).write_text(
        json.dumps({"prompt_fingerprint": "demo", "cards": cards_payload}, indent=1) + "\n"
    )
    (directory / run_files.MANIFEST).write_text(
        json.dumps(
            {
                "created_at": stamp(2.0),
                "updated_at": stamp(1.0),
                "capture_dir": "captures/cards/box%d" % box,
                # BOTH SHAPES, ONE PER RUN, because they are different products on screen.
                # A whole-box run costs no temporary directory; a SCOPED one is the ticked
                # selection handed over from `#/inventory` (D39), and `RunPanel.tsx` draws
                # its card count in the row title. A manifest carrying neither — which the
                # first version of this wrote — reads as a scoped run with no count, and
                # every row rendered `Box 3 · RB Epics · ? cards`.
                "scope": (
                    {"box": box, "whole_box": True, "cards": None}
                    if whole_box
                    else {"box": box, "whole_box": False, "cards": len(rows)}
                ),
                "started_by": "demo",
                "batch_ids": ["demo_batch_%d" % box],
                "collected": True,
                "joined": False,
                "counts": {"cards": len(rows)},
                "usage": {},
            },
            indent=1,
        )
        + "\n"
    )
    return directory

if __name__ == "__main__":
    raise SystemExit(main())
