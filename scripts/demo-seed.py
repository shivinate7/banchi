#!/usr/bin/env python3
"""Seed a demo store — real catalog rows, synthetic photographs, no real inventory.

WHAT THIS IS FOR. The product is shareable only if somebody who has never seen it can
look at a full one. The owner's real store is not that: it is their cards, their buyers
and their money, and `inventory/` has never been in git for exactly that reason. So this
builds a store that is *shaped* like a real one out of material that is safe to publish.

WHAT IS REAL AND WHAT IS NOT, because the distinction is the whole design:

  REAL      the catalog. Every card here is drawn from `fixtures/`, which are untouched
            TCGplayer Filtered Exports — real SKUs, real names, real numbers, real market
            prices. So the joins are real joins, the pricing table is real arithmetic,
            and a viewer reading `8608039 · Alcremie ex · 075/159 · $0.67` is reading
            something TCGplayer actually published.

  INVENTED   which of those cards are in which box at which index, what sold, what is
            held back and to whom it shipped. None of it describes a physical object.

  CURATED    the photographs. Real photographs of the owner's own cards, on the owner's
            ruling (see `write_photo`), read from `demo-assets/` — the one tracked-image
            exception — and QR-cleared twice: at full resolution when `make demo-photos`
            curates them, and again on the published bytes when `demo-record.py` copies
            them. A live code card is a bearer instrument (D70). This paragraph said
            SYNTHETIC, drawn by `card_image()`, until 2026-09-24; that function was gone
            since 2026-09-06 (`docs/specs/demo.md` §3).

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
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from identify import cost  # noqa: E402
from pipeline import games as games_module  # noqa: E402
from pipeline import identity_binding as ib  # noqa: E402
from pipeline import skus as skus_fill  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from store import Box, Card, Listing, Store  # noqa: E402
from store import files as store_files  # noqa: E402
from store import orders as orders_mod  # noqa: E402
from store import photos as store_photos  # noqa: E402
from store.queues import QueueEntry  # noqa: E402

SEED = 20260906
FIXTURES = REPO_ROOT / "fixtures"

# The demo's clock. Every stamp below is an offset from this, so the store reads as one
# that has been worked for a few weeks rather than one built in a single instant.
NOW = datetime(2026, 9, 6, 14, 30, tzinfo=timezone.utc)


def stamp(days_ago: float = 0.0) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- catalog

ASSETS = REPO_ROOT / "demo-assets"
MANIFEST = ASSETS / "cards.json"


class Row:
    """One curated card: a real photograph and the identification that photograph got.

    THE PICTURE AND THE CAPTION ARE THE SAME CARD, which is why this reads a manifest rather
    than sampling an export. The demo drew its own cards until 2026-09-06 and could caption
    them anything; real photography cannot. A Heimerdinger captioned `Komala` costs a viewer
    their trust in everything else on the screen, so `scripts/demo-photos.py` carries the
    identification across with the image and this reads both together.
    """

    __slots__ = ("sku", "name", "number", "printed_total", "condition", "rarity",
                 "market", "set_name", "game", "printed", "photo", "priceable")

    def __init__(self, entry: dict) -> None:
        self.photo = entry["photo"]
        self.sku = entry["sku"]
        self.name = entry["name"]
        # Already the two halves a card record holds — `demo-photos.py` copies them straight
        # off the store, where `identify` wrote them. `cardNumber.ts:collectorNumber`
        # composes them for display (D67); nothing here recomposes.
        self.number = entry["number"]
        self.printed_total = entry["printed_total"]
        self.game = entry["game"]
        self.condition = entry["condition"] or "Near Mint"
        self.rarity = entry.get("rarity") or ""
        self.market = entry.get("market") or ""
        self.set_name = entry.get("set_name") or ""
        self.priceable = bool(entry.get("priceable"))
        self.printed = (
            "%s/%s" % (self.number, self.printed_total)
            if self.printed_total else (self.number or "")
        )

    @property
    def price(self) -> float:
        try:
            return float(self.market)
        except (TypeError, ValueError):
            return 0.0


def export_variants() -> Dict[str, List[dict]]:
    """Every vendored export row, grouped by Product Name.

    WHAT THE REVIEW QUEUE OFFERS AS CANDIDATES. A queued card is one the ladder could not
    settle, and what it is choosing BETWEEN is a set of export rows — the same card at
    different conditions and finishes, which is where D3's ambiguity actually lives
    (`Near Mint`, `Near Mint Holofoil`, `Near Mint Reverse Holofoil`). Read here rather than
    from the curated manifest because that holds ONE row per card by construction, so it has
    no siblings to offer and the queue would draw a single-candidate question.

    Grouped by name and NEVER JOINED ON IT. CLAUDE.md forbids the name as a join key because
    the column inconsistently embeds numbers; this is not a join, it is "which rows would a
    human be shown", and the number is checked below before any of them is offered.
    """
    grouped: Dict[str, List[dict]] = {}
    for name in ("sv09_export_untouched.csv", "onepiece_export_untouched.csv",
                 "riftbound_export_untouched.csv"):
        path = FIXTURES / name
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for record in csv.DictReader(handle):
                if not (record.get("Number") or "").strip():
                    continue
                grouped.setdefault(record["Product Name"], []).append(record)
    return grouped


def catalog() -> Tuple[List[Row], List[Row]]:
    """The curated set, split by whether a vendored export can price it.

    TWO POOLS BECAUSE A RUN NEEDS THE FIRST ONE. A run is joined against `fixtures/`, so a
    card no vendored export carries queues as `no_catalog_row` and prices at nothing.
    Measured on the owner's store: 1,010 of their Riftbound cards are in the vendored
    Riftbound export and 0 of their 542 Pokemon are — theirs are Mega Evolution, the fixture
    is SV09. So the boxes carrying a RUN are built from `priceable`, and the boxes that carry
    none are free to use the rest: the inventory walk, the sale, the orders and the
    Fulfiller's screen need no export at all, and only join, emit and pricing do.
    """
    if not MANIFEST.is_file():
        raise SystemExit(
            "no curated photographs at %s — run `make demo-photos SOURCE=<checkout>` "
            "first. It reads a store's real photographs, refuses any carrying a decodable "
            "QR, and writes the tracked set this seed builds from."
            % MANIFEST.relative_to(REPO_ROOT)
        )
    entries = json.loads(MANIFEST.read_text())
    rows = [Row(entry) for entry in entries]
    return (
        [r for r in rows if r.priceable],
        [r for r in rows if not r.priceable],
    )


# ------------------------------------------------------------------------ photographs


def photo_digest(row: "Row") -> str:
    """This card's NAME: the sha256 of the photograph the store is about to hold (D172).

    DETERMINISTIC BY CONSTRUCTION, WHICH IS THE PROPERTY THIS WHOLE FILE RESTS ON. A digest
    is a pure function of bytes that are TRACKED — `demo-assets/photos/` is the one
    tracked-image exception in this repo — so an unchanged tree rebuilds the same names, and
    the bundle CI republishes on every merge does not churn. There is no RNG here and there
    must never be one: `store/master.py:record_capture` refuses a nameless card, so the seed
    has to issue the name itself, and a name drawn from the seeded stream would make the
    store's primary content addresses depend on the order the boxes happen to be walked in.

    UNIQUE BY CONSTRUCTION TOO, AND MEASURED RATHER THAN ASSUMED: the pool is 132 files with
    132 distinct digests, 0 duplicate groups, and `pick_rows` threads `taken` on `row.photo`
    so no photograph is placed twice. The store's 122 cards therefore hold 122 distinct
    names, which is what `cards_cid`'s UNIQUE index requires — and it is why no card here
    needs D172's `<digest>-<n>` shape for a second card holding identical bytes.
    """
    return store_photos.sha256_of(ASSETS / "photos" / row.photo)


def relative_photo(digest: str) -> str:
    """`photos/6b/6b1cf2fd….jpg` — what goes in `Card.photo`, RELATIVE TO THE HOME.

    A REAL CAPTURE WRITES THE ABSOLUTE PATH HERE (`do_capture`: `card.photo = str(path)`) AND
    THIS ONE MAY NOT. `Card.photo` reaches the wire — `types.ts:CardSummary.photo`, a
    filesystem path and not a URL, which the app never fetches because every photograph is
    addressed through `photoUrl` — so an absolute path would bake this machine's
    `PKMNSCAN_HOME` into the recorded bundle and make every rebuild a diff. The store already
    holds both shapes on the owner's own machine (1,993 absolute, 542 relative, 0 tail-drift),
    so nothing downstream cares which; determinism does.
    """
    return f"{store_photos.DIRNAME}/{digest[:store_photos.SHARD]}/{digest}.jpg"


def write_photo(digest: str, row: "Row") -> None:
    """The curated photograph, filed under the card's own name.

    COPIED, NOT DRAWN. Until 2026-09-06 this rendered a card plate with Pillow — safe, and
    it looked exactly like what it was. The owner's ruling: *"i'd rather it show real
    photography... just take some random pics of mine that i made -- that's not a copyright
    issue."* So the picture is theirs, of their own card, on their own rig, and it was
    cleared of carrying a decodable QR before it was ever written to a tracked path
    (`scripts/demo-photos.py`).

    FILED UNDER THE DIGEST RATHER THAN THE SLOT (D172). `store/photos.py` composes the path
    and is the only module allowed to, so this takes the card's name and not a box and an
    index — and `shutil.copyfile` rather than `photos.write` because the bytes are already a
    file on disk and there is no reason to read 1.9 MB into RAM to hand it straight back.
    """
    path = store_photos.path(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / "photos" / row.photo, path)


# ------------------------------------------------------------------------------- boxes

# The shape of the demo store. Four boxes, chosen so that every case a screen has to draw
# is present somewhere — two boxes with dividers, a
# mixed box with NO dividers (D10's undeclared box, which renders as one section), and a
# box holding the departed. A demo where every box is the same box teaches nothing.
# The shape of the demo store. Four boxes, chosen so every case a screen has to draw is
# present somewhere — two boxes with dividers, a
# mixed box with NO dividers (D10's undeclared box, which renders as one section), and a
# box holding the departed. A demo where every box is the same box teaches nothing.
#
# `pool` IS LOAD-BEARING, NOT DECORATION. `priceable` means every card in it is one a
# vendored export can price, which is what a RUN needs — boxes 1 and 3 are joined for real
# against `fixtures/`, so their cards must be findable there. Boxes 2 and 4 carry no run and
# are free to hold the owner's Pokemon, which no vendored export covers: the inventory walk,
# the sale, the orders and the Fulfiller's screen ask nothing of an export.
BOXES = (
    {
        "box": 1, "name": "RB Origins", "pool": "priceable", "count": 42,
        "sections": [1, 15, 29],
        "section_names": {"1": "Commons", "15": "Uncommons", "29": "Signatures"},
        "created": 24.0,
        "sittings": ((24.0, 34, 2.9), (20.6, 8, 5.2)),
    },
    {
        "box": 2, "name": "MEG Bulk", "pool": "other", "count": 28,
        "sections": [1, 16],
        "section_names": {"1": "Commons", "16": "Holos"},
        "created": 17.0,
        "sittings": ((17.0, 28, 6.5),),
    },
    {
        "box": 3, "name": "RB Epics", "pool": "priceable", "count": 34,
        "sections": [1, 12, 24],
        "section_names": {"1": "Origins", "12": "Legacy", "24": "Epics"},
        "created": 31.0,
        "sittings": ((31.0, 19, 3.4), (29.4, 15, 4.7)),
    },
    {
        # No dividers on purpose: D10 amended, an undeclared box renders as ONE section and
        # `card` is the index. Somebody looking at this demo should see that case, because
        # it is what every box looks like before anybody divides one. Mixed pools too — a
        # real "everything else" drawer holds more than one game, and D21 makes game a
        # per-card claim rather than a mode.
        "box": 4, "name": "Mixed Singles", "pool": "mixed", "count": 18,
        "sections": [], "section_names": {},
        "created": 9.0,
        "sittings": ((9.0, 18, 3.9),),
    },
)

# WHY EACH BOX CARRIES `sittings`, AND WHY A SPREAD ACROSS ITS AGE WAS NOT ONE.
#
# `app/src/storeHistory.ts` recovers a SITTING by clustering `captured_at` at a 30-minute gap,
# and the foot of the Home hero draws one block per sitting — as wide as its minutes and as
# tall as its cards an hour. This file used to stamp a box's cards evenly across the box's own
# age, which puts box 1's 42 cards eleven HOURS apart: every card clustered alone, every
# sitting spanned zero time, `rate` was null on all 122 of them, and the ribbon drew ticks and
# no blocks at all. The drawing was not broken; it was correctly reporting a store that had
# never sat down at a rig.
#
# So a box is captured in one or two sittings, minutes long, days apart — `(days_ago, cards,
# seconds_per_card)`. The cadences are between the rig's own measured 0.6095 s a card
# (`docs/specs/motion-trigger.md`, the physical floor and the ribbon's ceiling) and the ~4.2 s
# a card the owner's real store averages across its six sittings. They VARY between sittings
# on purpose: a ribbon whose blocks are all one height carries nothing the printed card count
# does not already say.
SITTING_JITTER_MS = 900


def capture_stamps(spec: dict) -> List[str]:
    """One ISO stamp per card in `spec`, oldest first, clustered into that box's sittings.

    Deterministic, and on its OWN RNG rather than the caller's: `state_for` draws from the
    shared stream, so borrowing it here would silently re-deal which cards are sold.
    """
    plan = spec.get("sittings")
    if plan is None:
        raise SystemExit("box %d has no `sittings`" % spec["box"])
    if sum(cards for _, cards, _ in plan) != spec["count"]:
        raise SystemExit(
            "box %d: sittings hold %d cards, the box holds %d"
            % (spec["box"], sum(cards for _, cards, _ in plan), spec["count"])
        )
    jitter = random.Random(SEED + spec["box"])
    out: List[str] = []
    for days_ago, cards, seconds in plan:
        start = NOW - timedelta(days=days_ago)
        elapsed = 0.0
        for i in range(cards):
            if i:
                elapsed += seconds + jitter.uniform(-1, 1) * (SITTING_JITTER_MS / 1000.0)
            out.append((start + timedelta(seconds=max(0.0, elapsed))).isoformat(timespec="seconds"))
    return out


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


def pick_rows(pool: List[Row], count: int, taken: set) -> List[Row]:
    """`count` unused cards off `pool`, in order.

    NO PRICE BANDING, and the previous version's is deleted rather than kept. That code
    over-sampled the cheap end to imitate what real bulk looks like — which was right while
    the cards were drawn at random from a 10,078-row export. These are the owner's ACTUAL
    cards, sampled from their actual store, so the distribution is already the real one and
    a second opinion about it would make the demo less true rather than more.

    `taken` threads across boxes so no card is placed twice.
    """
    picked = []
    for row in pool:
        if len(picked) >= count:
            break
        if row.photo in taken:
            continue
        taken.add(row.photo)
        picked.append(row)
    return picked


# ---------------------------------------------------------------------- identity binding

# The three real, vendored exports `export_variants()` above already reads for the review
# queue's candidates — the same files, reused rather than a fourth copy of the list.
FIXTURE_EXPORTS = (
    "sv09_export_untouched.csv",
    "onepiece_export_untouched.csv",
    "riftbound_export_untouched.csv",
)

# ONE card, deliberately mis-identified, so the confirm press, "Read as" and "Listed as"
# (identity-follows-sku.md §5.9, lane 6) have something to draw on the published demo. Box
# 3 is `priceable` — every SKU in it is a real fixture row — and never touched by the
# "guarantee one moved card" fallback below (that one reaches into box 1), so this position
# is safe from being overwritten by a later, unrelated rule.
DISPUTE_BOX = 3
DISPUTE_OFFSET = 0


def seed_skus(inventory, skus) -> None:
    """Fold the demo's own real fixture exports into the store's `skus` table
    (identity-follows-sku.md §3.2, lane 0), through `pipeline/skus.apply_rows` — the SAME
    fold `pkmnscan skus adopt` runs on a real store. Run before any card is bound: `bind_sku`
    reads this table and refuses `sku_unknown` for anything not folded here first (§3.2:
    "every writer upserts the row it is about to bind... before calling bind_sku").

    ONE FIXED STAMP FOR ALL THREE FILES, off the demo's own clock rather than
    `pipeline/skus.stamp_of` (which reads a `YYYYMMDD-HHMMSS` run stamp out of a FETCHED
    export's filename) — these are checked-in fixtures named for what they hold, not when
    they were pulled, so `stamp_of` finds nothing in any of the three names and a real
    timestamp (`time.time()`) would make every rebuild a diff, the one property this whole
    file exists to keep (SEED, NOW). The three files carry disjoint SKUs (three different
    product lines), so no fold here is ever `CHANGED` — the exact stamp cannot move the
    outcome, only `first_seen`/`last_seen`.
    """
    at = int(NOW.timestamp())
    for name in FIXTURE_EXPORTS:
        export = tcgcsv.read_export(FIXTURES / name)
        skus_fill.apply_rows(
            export.rows, at=at, source=name, skus=skus, events=inventory.events,
        )


def bind_or_hold(
    inventory,
    skus,
    card: Card,
    *,
    sku: Optional[str],
    game: str,
    run: str,
    read_name: Optional[str],
    read_number: Optional[str],
    read_printed_total: Optional[str],
    confidence: str,
    bound_at: str,
) -> None:
    """One card's identity, written the way the product writes it now
    (identity-follows-sku.md §4, lane 6), never straight onto the record.

    `record_identification` FIRST, ALWAYS — the evidence group (`read_name`/`read_number`/
    `read_printed_total`/`confidence`/`read_disputes`), and, while the card carries no
    binding yet, the identity group too (that method's own rule: "on a card with no SKU the
    identity follows the read"). `card` must already be in `inventory.cards` — both writers
    below are silent no-ops on a key they cannot find.

    THREE OUTCOMES, NEVER TWO. `sku` absent from `skus` (the `other` pool: 0 of 40 in any
    fixture export) calls `hold_sku(card.key, at=bound_at)` with no `sku` to offer — lane 7's
    own writer, not "as before": the card's `identity_source` still ends up `IDENTITY_READ`,
    the outcome is the same as it always was, but `bound_at` is now stamped too (to the
    caller's own fixed clock, never a real `now()` — see below), where the pre-lane-7 code
    left it `None`. `sku` present and the read
    AGREES is `bind_sku` — the same branch a real join takes, faked here only because
    identification is the one paid step (see the module docstring). `sku` present and the
    read DISPUTES the row is REVIEW ROUND, NOT LANE 6'S FIRST PASS: §4.1, "a join caller
    refuses to bind a card whose read disputes the row." `bind_sku` is never called — the
    card is left HELD, through `Inventory.hold_sku` (lane 7, §4.3: the fourth writer,
    `cli/cmd_cards.py`'s own migration held branch routes through the same method) rather
    than the `card.sku = sku` / `card.identity_source = IDENTITY_READ` this file wrote
    directly before that lane. `record_identification` above already put the read on both
    the evidence and the identity fields, and `read_disputes` travels with it, so `hold_sku`
    is called with `read_disputes=True` rather than left at its own leave-alone default —
    this branch's `disputes` is always true by construction (the `if disputes:` above it).
    This is `#/inventory`'s "the listing is right?" case verbatim (§8.1): a card whose drawn
    name is only the camera's, and whose SKU already names the real listing.

    Measured (§3.2, and this file's own `catalog()`): every `priceable` row's SKU is a real
    row in the three fixture exports; 0 of the `other` pool's are.

    `bound_at` IS THE CALLER'S FIXED CLOCK, THREADED INTO `bind_sku`'s OWN `at` — `bind_sku`
    stamps `now()` by default, which would put a different `bound_at` on every one of the
    ~90 cards this seed binds per `make demo` run (review round: measured, 97 timestamps
    differed between two runs before this parameter existed). `SEED`/`NOW` are this file's
    whole promise of a byte-identical rebuild; a wall-clock stamp inside the one writer broke
    it from underneath.
    """
    row = skus.entries.get(sku) if sku else None
    disputes = ib.name_disputes(read_name, [ib._row_dict(row)]) if row is not None else False
    inventory.record_identification(
        card.key, name=read_name, number=read_number, printed_total=read_printed_total,
        confidence=confidence, run=run, read_disputes=disputes,
    )
    if row is None:
        inventory.hold_sku(card.key, at=bound_at)
        return
    if disputes:
        inventory.hold_sku(card.key, sku, skus=skus, read_disputes=True, at=bound_at)
        return
    entry = games_module.get(game)
    inventory.bind_sku(
        card.key, sku, bound_by="join", skus=skus,
        number_strategy=entry["join_key"], expected_product_line=entry.get("product_line"),
        read_disputes=False, event="sku_bound", at=bound_at,
    )


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
    priceable, other = catalog()
    taken: set = set()
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

        # EVERY BOX HAS A NAME. The owner ruled that a box number is never shown, so a demo box
        # with no name would draw whatever fallback a screen invents for one.
        box_names = {spec["box"]: str(spec.get("name") or "").strip() for spec in BOXES}
        unnamed = sorted(box for box, name in box_names.items() if not name)
        if unnamed:
            raise SystemExit("every demo box needs a name; box(es) %s have none" % unnamed)
        if len(set(box_names.values())) != len(box_names):
            raise SystemExit("two demo boxes share a name, and D20 makes a name unique")
        seed_skus(inventory, snapshot.skus)

        for spec in BOXES:
            number = spec["box"]
            inventory.boxes[str(number)] = Box(
                box=number,
                name=spec["name"],
                sections=list(spec["sections"]),
                section_names=dict(spec["section_names"]),
                created_at=stamp(spec["created"]),
            )
            counts["boxes"] += 1

            if spec["pool"] == "mixed":
                half = spec["count"] // 2
                rows = pick_rows(priceable, half, taken)
                rows += pick_rows(other, spec["count"] - len(rows), taken)
                rng.shuffle(rows)
            else:
                source = priceable if spec["pool"] == "priceable" else other
                rows = pick_rows(source, spec["count"], taken)

            stamps = capture_stamps(spec)
            for offset, row in enumerate(rows):
                index = offset + 1
                state = state_for(offset, len(rows), rng)
                # ONE DELIBERATE MISREAD (§5.9, review round), FORCED TO `identified`
                # REGARDLESS OF THE ROLL ABOVE. `#/inventory`'s confirm press needs
                # `state === 'identified'` (`eligible = sku !== null && card.state ===
                # 'identified'`, `app/src/CardHero.tsx`) — a `sold` roll here would seat the
                # dispute in a pane that draws no press at all.
                disputed = spec["box"] == DISPUTE_BOX and offset == DISPUTE_OFFSET
                if disputed:
                    state = "identified"
                captured_at = stamps[offset]

                # THE CARD'S NAME, AND THE SEED HAS TO ISSUE IT ITSELF (D172). These rows go
                # into `inventory.cards` directly rather than through `record_capture` —
                # which is where a real capture's name is minted and where a nameless card
                # is refused — so the digest is computed here, off the photograph this loop
                # is about to write, exactly as `do_capture` computes it off the blob in RAM.
                #
                # A `moved` CARD IS A TOMBSTONE AND WEARS `moved:<name>` (D83). The photograph
                # belongs to the TRANSPLANT, so one name never sits on two rows and
                # `photos.is_photo_cid` answers False for this one — which is why the
                # graveyard draws no photograph for it. The demo writes no transplant record
                # (`moved_to` names a slot in box 4 that another card holds), so the bytes
                # under the plain digest are claimed by no row here: a simplification of the
                # fiction, not of the layout, and it is written down rather than discovered.
                digest = photo_digest(row)
                card = Card(
                    box=number,
                    index=index,
                    photo=relative_photo(digest),
                    cid=(
                        store_photos.MOVED_PREFIX + digest
                        if state == "moved"
                        else digest
                    ),
                    game=row.game,
                    capture_id="demo-%d-%04d" % (number, index),
                    captured_at=captured_at,
                    state=state,
                    state_at=captured_at,
                    condition=row.condition,
                    metadata_finish=None,
                )
                inventory.cards[card.key] = card
                if state != "captured":
                    # An identified card knows what it is. A captured one does not yet —
                    # that is the whole difference, and the review queue is where the
                    # difference gets settled. Written through `record_identification` and
                    # `bind_sku`/held now, never straight onto the record
                    # (identity-follows-sku.md §4, lane 6) — `bind_or_hold` above is what
                    # decides which of the three this card gets.
                    #
                    # ONE DELIBERATE MISREAD (§5.9, review round): the model's reading names
                    # a DIFFERENT real card (`rows[DISPUTE_OFFSET + 1]`) from the one this
                    # position's own SKU actually names, so `read_disputes` comes back true —
                    # `bind_or_hold` leaves it HELD rather than binding it (§4.1's own
                    # refusal), and the confirm press, "Read as" and "Listed as" all have
                    # something to draw.
                    read_row = rows[DISPUTE_OFFSET + 1] if disputed else row
                    bind_or_hold(
                        inventory, snapshot.skus, card,
                        sku=row.sku, game=row.game, run="demo-run-%d" % number,
                        read_name=read_row.name, read_number=read_row.number,
                        read_printed_total=read_row.printed_total,
                        confidence="low" if disputed else "high",
                        bound_at=stamp(2.0),
                    )
                if state == "retired":
                    card.retire_reason = "damaged"
                if state == "moved":
                    card.moved_to = "4/%d" % (rng.randint(1, 18))

                placed.append((card, row))
                counts["cards"] += 1
                if state in counts:
                    counts[state] += 1

                write_photo(digest, row)
                counts["photos"] += 1

        # D83's third door — a card that left its box by being MOVED rather than sold or
        # retired — is rare enough in the distribution above to miss a seeding entirely, and
        # a state no demo store ever holds is a state no viewer ever sees. Guarantee one.
        if not any(c.state == "moved" for c, _ in placed):
            for card, _ in placed:
                if card.state == "identified" and card.box == 1:
                    card.state = "moved"
                    card.moved_to = "4/7"
                    # AND THE NAME BECOMES A TOMBSTONE'S, WHICH THE LOOP ABOVE DOES AT BIRTH
                    # AND THIS HAS TO DO AFTER THE FACT (D83). `move_card` wears
                    # `moved:<name>` for one reason: the transplant keeps the plain name, and
                    # `cards_cid` holds it UNIQUE, so one photograph's name can never sit on
                    # two rows. Rewriting it here rather than re-deriving the digest, because
                    # the card in hand already carries the name the seed issued it.
                    if card.cid and not card.cid.startswith(store_photos.MOVED_PREFIX):
                        card.cid = store_photos.MOVED_PREFIX + card.cid
                    inventory.cards[card.key] = card
                    counts["moved"] += 1
                    counts["identified"] = counts.get("identified", 0) - 1
                    break

        # ------------------------------------------------------------------- listings
        # One row per SKU, holding QUANTITIES rather than addresses (D7 amended). `live` is a
        # READING of what TCGplayer holds and carries the moment it was taken (D87).
        #
        # A FRESHLY JOINED RUN IS NOT LISTED YET, AND THE FIRST VERSION OF THIS GOT IT
        # BACKWARDS. It wrote `live = min(on_hand, 4)` for every SKU in the store, so every
        # row on `#/pricing` came back `at_cap` — `room = LIVE_QUANTITY_CAP - live` was zero,
        # `add_to_quantity` was zero, and the screen correctly reported that every copy was
        # "already listed or has left the box". The import file would have added nothing, the
        # trend walk skips capped rows so "Load trends" had one row to ask about, and the
        # whole point of the pricing screen was missing from the demo of it.
        #
        # The honest state after `identify` and `join` and before `emit` is: these cards are
        # on hand and NOT listed. So the run boxes get no listing row at all unless a copy
        # has sold — a sale proves the SKU was listed once — and the boxes carrying no run
        # hold the older, already-listed stock, kept under the cap so they have room too.
        RUN_BOXES = {spec["box"] for spec in BOXES if spec["pool"] == "priceable"}
        by_sku: Dict[str, List[Card]] = {}
        for card, _row in placed:
            if card.sku and card.state in ("identified", "sold"):
                by_sku.setdefault(card.sku, []).append(card)

        for sku, cards in by_sku.items():
            sold = [c for c in cards if c.state == "sold"]
            on_hand = [c for c in cards if c.state == "identified"]
            if not sold and not on_hand:
                continue
            fresh = any(int(c.box) in RUN_BOXES for c in cards) and not sold
            if fresh:
                # Never listed. `join` will report it as room for every copy on hand, which
                # is what gives `#/pricing` something to answer.
                continue
            pushed = len(sold) + len(on_hand)
            # UNDER THE CAP ON PURPOSE. At 4 there is no room and the row is inert; at 1 or 2
            # the screen shows a partly-listed SKU, which is both the commoner real state and
            # the one where the cap arithmetic is legible.
            live = min(len(on_hand), 2)
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
        variants = export_variants()
        for offset, (card, row) in enumerate(review_pool):
            # The export's own rows for this card — its real conditions and finishes, at
            # their real prices. Matched on the printed number as well as the name, so a
            # shared name across sets cannot put another card's row in front of a human.
            siblings = [
                record for record in variants.get(row.name or "", [])
                if (record.get("Number") or "").strip() == row.printed
            ][:3]
            candidates = [
                {
                    "sku": record["TCGplayer Id"],
                    "name": record["Product Name"],
                    "number": record["Number"],
                    "condition": record["Condition"],
                    "market": record["TCG Market Price"],
                    "rarity": record["Rarity"],
                }
                for record in siblings
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
                    # BY THE BOX'S NAME, NEVER ITS NUMBER (the owner's ruling: a box number
                    # is never shown). `/queues` re-labels every entry through the server's
                    # own place formula, so this string is a fallback nothing draws today.
                    label="%s, card %d" % (box_names[card.box], card.index),
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
                    # `or None`, NEVER the empty string. `QueueEntry.price` does
                    # `Decimal(self.market)` for anything non-None, and `Decimal("")` raises
                    # `InvalidOperation` — which surfaced as a traceback out of
                    # `queue_summary` in the middle of a join, nowhere near this line. A
                    # card no vendored export prices has no market, and None is how the
                    # queue spells that.
                    market=row.market or None,
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


# --------------------------------------------------------------------- the price archive

# THE DEMO'S PRICE HISTORIES, RECORDED ONCE ON THE OWNER'S MAC (the owner's ruling, 2026-09-24).
# Every history this product draws is read from a host that refuses an honest User-Agent (D216),
# and the owner allows the browser signature from the owner's own machine only, never from CI.
# So `make demo-histories` records them there, into a new dated directory under
# `fixtures/demo-price-history/`, and this reads the newest one. Real readings, never invented.
HISTORIES_ROOT = FIXTURES / "demo-price-history"


def history_directory() -> Optional[Path]:
    """The newest recorded directory, or None when nobody has recorded one."""
    if not HISTORIES_ROOT.is_dir():
        return None
    dated = sorted(p for p in HISTORIES_ROOT.iterdir() if (p / "index.json").is_file())
    return dated[-1] if dated else None


class FixtureMarket:
    """`pipeline/pricearchive.py:_MarketLike`, answered from the recorded histories only.

    THE REAL SWEEP DOES THE WORK. `write_archive` hands this to `pricearchive.sweep`, so the
    buckets the archive holds are built by the same code `pkmnscan archive sweep --write`
    runs. This class replaces only the network. A SKU the recording does not carry is a
    refusal, named, never an invented series.
    """

    def __init__(self, directory: Path) -> None:
        from pipeline import pricehistory

        self.pricehistory = pricehistory
        self.directory = directory
        self.products: Dict[str, int] = {
            str(sku): int(pid)
            for sku, pid in json.loads((directory / "index.json").read_text()).get("skus", {}).items()
        }

    def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
        from pipeline import tcgcsv

        readings: Dict[str, object] = {}
        refusals: Dict[str, str] = {}
        for row in rows:
            sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
            product = self.products.get(sku)
            series = {}
            for range_ in ranges or self.pricehistory.RANGES:
                path = self.directory / "history" / ("%d-%s.json" % (product or 0, range_))
                if product is None or not path.is_file():
                    continue
                found = self.pricehistory.parse_history(
                    json.loads(path.read_text()), product, range_
                ).get(sku)
                if found is not None:
                    series[range_] = found
            if not series:
                refusals[sku] = "no recorded reading for this SKU"
                continue
            readings[sku] = self.pricehistory.Reading(sku=sku, product_id=product, series=series)
        return readings, refusals


def write_archive() -> int:
    """The price-history archive (D219), from the recorded histories. Returns buckets written.

    Read by `#/product` (archive first, D227) and by `#/revenue`'s "Value my stock" (D236), so
    both draw real ranges on the published page. The export rows are the committed exports, and
    `at` is the demo's own clock, so a rebuild is byte-identical.
    """
    from pipeline import pricearchive, pricehistory, tcgcsv

    directory = history_directory()
    if directory is None:
        return 0
    market = FixtureMarket(directory)
    rows: Dict[str, dict] = {}
    for name in ("riftbound_export_untouched.csv", "sv09_export_untouched.csv",
                 "onepiece_export_untouched.csv", "pokemon_wide_export_untouched.csv"):
        for row in tcgcsv.read_export(FIXTURES / name).rows:
            sku = str(row.get(tcgcsv.SKU_COLUMN))
            if sku in market.products and sku not in rows:
                rows[sku] = dict(row)
    if not rows:
        return 0
    buckets, sources, refusals, _ = pricearchive.sweep(
        rows, market, pricehistory.RANGES, now=int(NOW.timestamp())
    )
    with Store().write() as snapshot:
        snapshot.archive.upsert(buckets)
        snapshot.archive.record_pass(sources)
    return len(buckets)


# ---------------------------------------------------------- extra real box (opt-in only)


def add_extra_real_boxes() -> dict:
    """A SECOND, small, real box — additive, opt-in, and never the default build.

    OFF UNLESS `PKMNSCAN_DEMO_EXTRA_REAL=1`. `make demo-seed` on its own never calls this
    branch at all, so the default store stays byte-identical to the build before this
    function existed — `make demo-determinism-selftest` proves the digest matcher without
    ever setting the variable, and nothing above this function changes.

    RUNS IN ITS OWN `store.write()`, AFTER THE DETERMINISTIC BASE STORE IS ALREADY
    COMMITTED. So it cannot perturb `SEED`/`NOW`, `placed`, the corpus, the review queue, or
    either run directory the base build writes — this only ever ADDS a box, its cards, and a
    listing row per SKU. `docs/specs/demo.md` §4's REAL/INVENTED split still holds: reads
    `demo-assets/extra/cards.json` (`scripts/demo-extra-real.py`'s own output), which is
    itself real names, numbers, SKUs, rarities, market prices, typed prices and sale facts
    curated from a READ-ONLY COPY of the owner's store. WHICH BOX AND INDEX each card sits
    at is invented, exactly like the base build's boxes — nothing here claims otherwise.

    NO ORDER IS WRITTEN, on the owner's own ruling: buyers and orders stay invented, and nothing
    here adds either.
    """
    if not os.environ.get("PKMNSCAN_DEMO_EXTRA_REAL"):
        return {}

    manifest_path = REPO_ROOT / "demo-assets" / "extra" / "cards.json"
    if not manifest_path.is_file():
        print("PKMNSCAN_DEMO_EXTRA_REAL is set but %s is missing — run "
              "scripts/demo-extra-real.py first. Skipping." % manifest_path.relative_to(REPO_ROOT))
        return {}
    entries = json.loads(manifest_path.read_text())
    photos_dir = manifest_path.parent / "photos"

    counts = {"boxes": 0, "cards": 0, "photos": 0, "listings": 0, "sold": 0, "identified": 0}
    store = Store()
    with store.write() as snapshot:
        inventory = snapshot.inventory
        box_number = max((int(b) for b in inventory.boxes), default=0) + 1
        box_name = "Demo Box"
        if box_name in {b.name for b in inventory.boxes.values()}:
            return {}  # already added by an earlier run — never a second box
        inventory.boxes[str(box_number)] = Box(
            box=box_number,
            name=box_name,
            sections=[1],
            section_names={},  # section 1 carries no name, on the owner's own ruling
            state="open",
            capacity=None,
            created_at=stamp(1.0),
        )
        counts["boxes"] += 1

        for offset, entry in enumerate(entries):
            index = offset + 1
            digest = store_photos.sha256_of(photos_dir / entry["photo"])
            dest = store_photos.path(digest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(photos_dir / entry["photo"], dest)
            counts["photos"] += 1

            sale = entry.get("sale")
            state = "sold" if sale else "identified"
            captured_at = stamp(1.0)
            card = Card(
                box=box_number,
                index=index,
                photo=relative_photo(digest),
                cid=digest,
                game=entry["game"],
                capture_id="demo-extra-%04d" % index,
                captured_at=captured_at,
                state=state,
                # A REAL DATE WHERE THERE IS ONE — the sale's own `placed_at`, never
                # `now()`. Everything else here is the same fixed `stamp(1.0)` the base
                # build's own review-queue entries use.
                state_at=sale["placed_at"] if sale else captured_at,
                condition=entry.get("condition") or "Near Mint",
            )
            inventory.cards[card.key] = card
            counts["cards"] += 1
            counts[state] = counts.get(state, 0) + 1

            if entry.get("sku"):
                bind_or_hold(
                    inventory, snapshot.skus, card,
                    sku=entry["sku"], game=entry["game"], run="demo-extra",
                    read_name=entry["name"], read_number=entry["number"],
                    read_printed_total=entry.get("printed_total"),
                    confidence="high", bound_at=captured_at,
                )
                if state == "identified":
                    inventory.listings[entry["sku"]] = Listing(
                        sku=entry["sku"], condition=card.condition,
                        pushed=0, staged=0, live=0, at=captured_at, live_as_of=captured_at,
                    )
                    counts["listings"] += 1
    # A real typed price reaches the pricing corpus for real, so a viewer of `#/pricing`
    # sees the actual gap between what the owner typed and today's market — not a synthetic
    # one. Merged into the corpus `write_corpus` already wrote, above main()'s own call to
    # this function — never a second, competing writer of the same file at once.
    typed = {e["sku"]: e["typed_price"] for e in entries if e.get("typed_price")}
    if typed:
        from pipeline import corpus as corpus_mod
        current = corpus_mod.Corpus.read()
        for sku, value in typed.items():
            current.answers[sku] = corpus_mod.Answer(value=value, at=stamp(1.0))
        current.write()
        counts["typed_prices"] = len(typed)

    return counts


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
    counts["archived"] = write_archive()

    home = store_files.home()
    counts["runs"] = 0
    for box, whole_box in ((1, True), (3, False)):
        if write_run(placed, box, home, whole_box) is not None:
            counts["runs"] += 1

    extra = add_extra_real_boxes()
    if extra:
        for key, value in extra.items():
            counts["extra_" + key] = value

    print("demo store seeded at %s" % home)
    for key in ("boxes", "cards", "photos", "listings", "answers", "archived", "review",
                "runs", "orders", "sold", "retired", "moved", "captured"):
        print("  %-9s %d" % (key, counts.get(key, 0)))
    if extra:
        print("  extra real box (PKMNSCAN_DEMO_EXTRA_REAL):")
        for key, value in extra.items():
            print("    %-9s %d" % (key, value))
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
    the real fixture export, the catalog lookup is a real lookup, the cap arithmetic is
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
            # THE RECORD'S OWN PHOTO FIELD, VERBATIM, RATHER THAN A SECOND COMPOSITION OF
            # IT. A run record's `photo` is what `cli/resolve.py:queue_entry` carries onto a
            # queue entry and what the review screen renders, so it has to name the same
            # file the card does — and the two agreeing because they are one string is
            # stronger than the two agreeing because two format strings match today.
            # D172's layout is why this matters now: the name is a digest, so a mismatch
            # would no longer be a plausible-looking neighbouring slot, it would be nothing.
            "photo": card.photo,
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
                # THE BOX'S CAPTURE DIRECTORY, COMPOSED IN THE ONE MODULE ALLOWED TO AND
                # THEN MADE RELATIVE. It is still the LEGACY address and that is correct:
                # `server/pipeline_routes.py:box_capture_dir` keeps reading it while the
                # relocation is unfinished, and the content store is flat and shared, so no
                # run can be a directory of it — D172 §0.4 answers that with a built
                # `.scopes/` view and this becomes that path when it is. Relative for
                # `relative_photo`'s reason: this string reaches `#/runs` through
                # `_summary`, and an absolute one would bake this machine's home into the
                # recorded bundle. `_summary` reads `scope.box` first and falls back to the
                # `box<N>` in this basename, which survives the `relative_to` either way.
                "capture_dir": str(store_photos.legacy_box_dir(box, home).relative_to(home)),
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
                # WHAT THE RUN COST, BECAUSE A DEMO THAT SHOWS `Already paid` SHOWS NOTHING.
                # `#/runs` reports the figure on the Identify step, and a manifest with an
                # empty `usage` is the one shape that has none to report — which is what the
                # published demo would have drawn. Scaled off the card count from the owner's
                # own 2026-09-11 run (290,470 in / 3,761 out over 464 photographs) so the
                # arithmetic a viewer checks against `identify/cost.py` comes out right.
                # Deterministic, like everything else here: no RNG, so an unchanged tree
                # rebuilds byte-identically.
                "usage": {
                    "input_tokens": 626 * len(rows),
                    "output_tokens": 8 * len(rows),
                    "cost_usd": cost.recorded(626 * len(rows), 8 * len(rows)),
                },
            },
            indent=1,
        )
        + "\n"
    )
    return directory

if __name__ == "__main__":
    raise SystemExit(main())
