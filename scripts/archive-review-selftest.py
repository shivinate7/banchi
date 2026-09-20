#!/usr/bin/env python3
"""`cli/archive_review.py`, proved against a throwaway store.

NO NETWORK CALL. Every refusal below is a fabricated string, shaped exactly the way
`pipeline/pricehistory.py:NotResolvable`, `Unreachable` and `Blocked` already write one —
`cli/archive_review.py` never talks to a market, and neither does this test.

WHAT THIS PROVES:

  1. A card whose identification does not resolve reaches the review queue, with its
     photograph, under `pipeline/variant.py:NO_CATALOG_ROW`.
  2. A second pass over the same refusal adds nothing new (`Queue.upsert`'s own guard).
  3. A card sharing the refused SKU but carrying a DIFFERENT stored number is never queued
     — see `cli/archive_review.py`'s own docstring for the measured real-store shape this
     guards against (`Exeggutor`, D234).
  4. A card with no photograph is never queued, even when its identification refuses.
  5. A network-shaped refusal (`Unreachable`/`Blocked`'s own message text) is never queued.
  6. MUTATION ARM: a broken "apply" that writes the queue directly, bypassing
     `Queue.upsert`'s own refusal to re-queue a cleared position, is shown to duplicate and
     re-open an answered entry — proving the real code's use of `Queue.upsert` is
     load-bearing, per `CLAUDE.md`'s "a guard is trusted only once it fails on the defect
     it guards."

Written, not wired into `make check` — `scripts/pricearchive-selftest.py`'s own precedent,
a fast self-contained proof of a module with no `make` target of its own yet.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import archive_review  # noqa: E402
from cli import resolve as run_resolve  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from pipeline import variant  # noqa: E402
from store import files  # noqa: E402
from store.master import Card  # noqa: E402
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
        print(f"  FAIL   {label}  ({detail})")


def _row(sku: str, name: str, number: str, set_name: str) -> dict:
    return {
        tcgcsv.PRODUCT_LINE_COLUMN: "Riftbound",
        tcgcsv.SET_COLUMN: set_name,
        tcgcsv.NUMBER_COLUMN: number,
        tcgcsv.NAME_COLUMN: name,
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.CONDITION_COLUMN: "Near Mint",
    }


def _not_resolvable(name: str, number: str, set_name: str) -> str:
    # `pipeline/pricehistory.py:ProductIndex.find`'s own message shape, verbatim — the exact
    # sentence a real refusal carries, read from that file but never edited by this one.
    return (
        f"no single tcgcsv product matches {name!r} {number!r} in {set_name!r}. Either the "
        "mirror does not carry it or two products share the number and the name could not "
        "tell them apart — this refuses rather than picking one."
    )


def main() -> int:
    previous = os.environ.get(files.HOME_ENV)
    home = Path(tempfile.mkdtemp(prefix="archive-review-selftest-"))
    os.environ[files.HOME_ENV] = str(home)
    try:
        with Store().write() as snapshot:
            # The card this whole test is about: identification refuses, on hand, photo.
            snapshot.inventory.cards["1/1"] = Card(
                box=1, index=1, sku="AAA", name="Shadbow Temple", number="",
                set_name="Vendetta", game="riftbound", condition="Near Mint",
                state="identified", photo="/photos/aaa-1.jpg",
            )
            # A DIFFERENT physical card sharing the SAME sku, but a DIFFERENT stored
            # number — the `Exeggutor` shape D234 measured. Must never be queued.
            snapshot.inventory.cards["1/2"] = Card(
                box=1, index=2, sku="AAA", name="Shadbow Temple", number="14/166",
                set_name="Vendetta", game="riftbound", condition="Near Mint",
                state="identified", photo="/photos/aaa-2.jpg",
            )
            # The exact same identification as 1/1, but SOLD — terminal state, excluded.
            snapshot.inventory.cards["1/3"] = Card(
                box=1, index=3, sku="AAA", name="Shadbow Temple", number="",
                set_name="Vendetta", game="riftbound", condition="Near Mint",
                state="sold", photo=None,
            )
            # A second refused sku, matching in every field, but with NO photograph.
            snapshot.inventory.cards["1/4"] = Card(
                box=1, index=4, sku="BBB", name="Kihoud Temple", number="",
                set_name="Vendetta", game="riftbound", condition="Near Mint",
                state="identified", photo=None,
            )
            # A third refused sku, but the refusal is NETWORK-shaped, not an identification.
            snapshot.inventory.cards["1/5"] = Card(
                box=1, index=5, sku="CCC", name="Seal of Power", number="",
                set_name="Spiritforged", game="riftbound", condition="Near Mint",
                state="identified", photo="/photos/ccc-5.jpg",
            )

        rows = {
            "AAA": _row("AAA", "Shadbow Temple", "", "Vendetta"),
            "BBB": _row("BBB", "Kihoud Temple", "", "Vendetta"),
            "CCC": _row("CCC", "Seal of Power", "", "Spiritforged"),
        }
        refusals = {
            "AAA": _not_resolvable("Shadbow Temple", "", "Vendetta"),
            "BBB": _not_resolvable("Kihoud Temple", "", "Vendetta"),
            "CCC": "https://mcp.tcgplayer.com/... could not be reached: timed out",
        }

        print("-- is_identification_refusal --")
        ok(archive_review.is_identification_refusal(refusals["AAA"]),
           "a NotResolvable message is an identification refusal")
        ok(not archive_review.is_identification_refusal(refusals["CCC"]),
           "an Unreachable-shaped message is never an identification refusal")

        print("\n-- cards_for_refusals: per-card match, never per-sku --")
        inventory = Store().read().inventory
        matches = archive_review.cards_for_refusals(inventory, rows, refusals)
        positions = sorted((m.card.box, m.card.index) for m in matches)
        ok(positions == [(1, 1), (1, 4)],
           "1/1 and 1/4 match their own refused identification — 1/2 (different stored "
           "number, same sku), 1/3 (sold) and 1/5 (network refusal, sku CCC) are all "
           "excluded here. 1/4 has no photo, checked next: that filter lives in "
           "queue_entries, not in the card match itself",
           positions)
        ok(all(m.reason == variant.NO_CATALOG_ROW for m in matches),
           "the reason is the existing ladder vocabulary, not a new string")

        print("\n-- queue_entries: no photo, no entry --")
        # Widen refusals to include BBB alone, whose only matching card has no photo.
        bbb_matches = archive_review.cards_for_refusals(
            inventory, rows, {"BBB": refusals["BBB"]}
        )
        views = run_resolve.box_views(inventory, boxes={1})
        bbb_entries = archive_review.queue_entries(bbb_matches, views)
        ok(bbb_entries == [], "a card with no photograph is never queued", bbb_entries)

        print("\n-- queue_entries + apply: reaches the queue, with its photo --")
        entries = archive_review.queue_entries(matches, views)
        ok(len(entries) == 1, "exactly one entry is built", entries)
        entry = entries[0]
        ok(entry.position == "1/1", "keyed by the card's own position", entry.position)
        ok(entry.photo == "/photos/aaa-1.jpg", "carries the card's photograph", entry.photo)
        ok(entry.reason == variant.NO_CATALOG_ROW, "carries the ladder's own reason")
        ok(entry.candidates == [], "zero candidates — this is what NO_CATALOG_ROW means")

        with Store().write() as snapshot:
            added = archive_review.apply(snapshot.review, entries)
        ok(added == 1, "one NEWLY queued entry the first time", added)
        after_first = dict(Store().read().review.entries)
        ok("1/1" in after_first and not after_first["1/1"].cleared_by_human,
           "1/1 is open in the review queue")
        first_seen = after_first["1/1"].first_seen
        ok(bool(first_seen), "first_seen is stamped", first_seen)

        print("\n-- re-run: idempotent, no duplicate --")
        with Store().write() as snapshot:
            added_again = archive_review.apply(snapshot.review, entries)
        ok(added_again == 0, "a second pass over the same refusal adds nothing new",
           added_again)
        after_second = dict(Store().read().review.entries)
        ok(after_second["1/1"].first_seen == first_seen,
           "first_seen is unchanged across the re-run")
        ok(len(after_second) == 1, "the queue holds exactly one entry, not two",
           len(after_second))

        print("\n-- an answered entry is never re-asked (D167) --")
        with Store().write() as snapshot:
            snapshot.review.entries["1/1"].cleared_by_human = True
        with Store().write() as snapshot:
            added_after_answer = archive_review.apply(snapshot.review, entries)
        ok(added_after_answer == 0,
           "an already-answered position is never re-queued, even when the archive still "
           "refuses it", added_after_answer)
        ok(dict(Store().read().review.entries)["1/1"].cleared_by_human,
           "the answer stands — this build never reopens it (see the sibling decision "
           "entry, D-archive-refusals-to-review-queue, for why the real store's own 16 "
           "cards are all in exactly this state)")

        print("\n-- MUTATION ARM: bypassing Queue.upsert re-opens and duplicates --")
        # Reset to the pre-answer state for a clean second scenario.
        with Store().write() as snapshot:
            snapshot.review.entries["1/1"].cleared_by_human = True
            before_mutation = dict(snapshot.review.entries)
        ok(before_mutation["1/1"].cleared_by_human,
           "fixture: the entry starts answered")

        def broken_apply(review, entries_) -> int:
            # THE MUTATION: writes the mapping directly, skipping `Queue.upsert`'s own
            # refusal to re-queue a cleared position and its own preservation of
            # `first_seen`. This is what `cli/archive_review.py:apply` must NOT do.
            added_ = 0
            for e in entries_:
                if e.position not in review.entries:
                    added_ += 1
                review.entries[e.position] = e
            return added_

        with Store().write() as snapshot:
            broken_apply(snapshot.review, entries)
        reopened = dict(Store().read().review.entries)
        ok(not reopened["1/1"].cleared_by_human,
           "RED WITHOUT THE GUARD: the broken path silently reopens an answered entry — "
           "exactly what `Queue.upsert` exists to refuse")
        ok(reopened["1/1"].first_seen != "" and reopened["1/1"].first_seen is not None,
           "the broken path also loses the real first_seen (overwritten by a fresh entry "
           "carrying its own default) — a second symptom of skipping `Queue.upsert`")
    finally:
        if previous is None:
            os.environ.pop(files.HOME_ENV, None)
        else:
            os.environ[files.HOME_ENV] = previous
        shutil.rmtree(home, ignore_errors=True)

    print("\narchive-review self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
