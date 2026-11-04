#!/usr/bin/env python3
"""`cli/archive_review.py`, proved against a throwaway store.

Protects: The price-archive review command refuses each unresolvable case in its own words and writes nothing on a preview, with no network call.
Governs: D234, D247

NO NETWORK CALL. The network refusals below come out of the real fetch path
(`pipeline/pricehistory.py:fetch_json` and `Market.readings_for_rows`), with `pipeline.net.request`
replaced by a fake that raises or answers. No socket is opened and no pause is taken. The
identification refusals are the text `pipeline/pricehistory.py:ProductIndex.find` writes.

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
  7. Every way a price-history fetch can fail (no connection, a dropped read, HTTP 503, 500,
     403, a body that is not JSON) is a network refusal, never an identification refusal.
     The verdict follows the refusal's kind, not its wording, so a reworded message moves nothing.
  8. A `NotResolvable` from the real catalogue walk is an identification refusal, and it
     stays one when its words happen to name a network failure.
  9. Every `PriceHistoryError` subclass, found by walking the class tree, has its pinned kind.

PATH GATED, THE SEVENTEENTH (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make archive-review-selftest`, wired into
`make check` and `make ci-check` through `scripts/guard-scope.py`. This file is no longer
the exception it was when written — `cli/archive_review.py` is called by `banchi archive
sweep --write` itself (`cli/cmd_pricearchive.py`), the same real, live caller that made
`pricearchive-selftest`'s own exemption go stale. Once it's done, it only needs to be tested
when touched.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import archive_review  # noqa: E402
from cli import resolve as run_resolve  # noqa: E402
from pipeline import net  # noqa: E402
from pipeline import pricehistory  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from pipeline import variant  # noqa: E402
from store import files  # noqa: E402
from store.master import IDENTITY_SKU, Card  # noqa: E402
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


# The kinds `pipeline/pricehistory.py` names, pinned by refusal class. A class missing here is
# unpinned and fails by name, so a new refusal class gets its kind on purpose.
PINNED_KINDS = {
    "NotResolvable": "KIND_IDENTIFICATION",
    "Unreachable": "KIND_NETWORK",
    "Offline": "KIND_NETWORK",
    "Blocked": "KIND_BLOCKED",
    "UnknownRange": "KIND_REQUEST",
}


def _kind_constant(name: str) -> str:
    """One of `pipeline/pricehistory.py`'s KIND_ values, or a named marker while it is not built."""
    return getattr(pricehistory, name, f"<no {name}>")


def _kind_of(message) -> str:
    """The kind a refusal carries. A plain string carries none, and says so by name."""
    return getattr(message, "kind", "<no kind>")


def _offline() -> net.Offline:
    error = net.Offline("Could not connect to infinite-api.tcgplayer.com.")
    error.__cause__ = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
    return error


def _dropped() -> net.Dropped:
    error = net.Dropped("The connection failed while the answer was being read.")
    error.__cause__ = ConnectionResetError(104, "Connection reset by peer")
    return error


def _http(status: int) -> net.NetError:
    return net.NetError(f"The host answered with status {status}.", status=status)


def _network_failures() -> list:
    """Each way one price-history fetch fails, as `pipeline.net.request` answers it:
    `(label, the kind its refusal must carry, how to patch request)`."""
    return [
        ("no connection was made", "KIND_NETWORK", {"side_effect": _offline()}),
        ("the connection dropped after it opened", "KIND_NETWORK", {"side_effect": _dropped()}),
        ("HTTP 503", "KIND_NETWORK", {"side_effect": _http(503)}),
        ("HTTP 500", "KIND_NETWORK", {"side_effect": _http(500)}),
        ("HTTP 403", "KIND_BLOCKED", {"side_effect": _http(403)}),
        ("a 200 body that is not JSON", "KIND_NETWORK", {"return_value": b"<html>maintenance</html>"}),
    ]


def _refusal_through(target, name: str, *, sku: str = "NET", product_ids=None, **how):
    """The refusal `Market.readings_for_rows` writes for `sku` when `target.name` is replaced by
    `mock.patch.object(target, name, **how)`. The real `fetch_json` turns a raise into its own
    error and the real fold turns that into the refusal.

    `product_ids` None pins the SKU to product 7, so the walk starts at the history fetch. Pass `{}`
    to make the walk go through the catalogue. A pause and a clock are never read: `_sleep` and
    `_monotonic` are replaced, and stderr is kept out of the report.
    """
    known = {sku: 7} if product_ids is None else product_ids
    market = pricehistory.Market(courtesy_delay=0)
    with contextlib.redirect_stderr(io.StringIO()), mock.patch.object(pricehistory, "_sleep"), \
            mock.patch.object(pricehistory, "_monotonic", return_value=0.0), \
            mock.patch.object(target, name, **how):
        _readings, refusals = market.readings_for_rows(
            [_row(sku, "Seal of Power", "", "Spiritforged")], ranges=("month",), product_ids=known
        )
    return refusals.get(sku)


def _not_resolvable_refusal(sku: str = "NRV") -> str:
    """The refusal a real catalogue walk writes when the catalogue holds no product line of that
    name: `Market.category_id` raises `NotResolvable` itself, from an empty category list."""
    market = pricehistory.Market(fetcher=lambda url: {"results": []}, courtesy_delay=0)
    _readings, refusals = market.readings_for_rows(
        [_row(sku, "Seal of Power", "", "Spiritforged")], ranges=("month",)
    )
    return refusals.get(sku)


def _refusal_classes() -> list:
    """Every class under `PriceHistoryError`, recursively, as this process has them loaded."""
    found, pending = [], [pricehistory.PriceHistoryError]
    while pending:
        for sub in pending.pop().__subclasses__():
            if sub not in found:
                found.append(sub)
                pending.append(sub)
    return sorted(found, key=lambda cls: cls.__name__)


def _verdicts_from_the_real_path() -> None:
    is_identification = archive_review.is_identification_refusal

    print("-- the real failure paths: never an identification refusal, kind by class --")
    for label, kind, how in _network_failures():
        refusal = _refusal_through(net, "request", **how)
        ok(refusal is not None, f"scope: {label} was refused, not read", refusal)
        ok(not is_identification(refusal), f"{label} is not an identification refusal", refusal)
        ok(_kind_of(refusal) == _kind_constant(kind), f"{label} is tagged {kind}",
           f"got {_kind_of(refusal)!r}")

    print("\n-- a NotResolvable from the real catalogue walk is an identification refusal --")
    not_resolvable = _not_resolvable_refusal()
    ok(not_resolvable is not None, "scope: the unmatched product line was refused", not_resolvable)
    ok(is_identification(not_resolvable),
       "a NotResolvable from the catalogue walk is an identification refusal", not_resolvable)
    ok(_kind_of(not_resolvable) == _kind_constant("KIND_IDENTIFICATION"),
       "a NotResolvable from the catalogue walk is tagged KIND_IDENTIFICATION",
       f"got {_kind_of(not_resolvable)!r}")
    ok(is_identification("a plain message that carries no kind"),
       "an untagged plain str still queues: no review item is hidden")

    print("\n-- the verdict follows the class, never the words --")
    reworded = _refusal_through(
        pricehistory, "_get",
        side_effect=pricehistory.Unreachable("Nothing in this sentence repeats an old one."),
    )
    ok(reworded is not None, "scope: a reworded Unreachable was refused", reworded)
    ok(not is_identification(reworded), "a reworded Unreachable is still a network refusal",
       reworded)
    reworded_offline = _refusal_through(
        pricehistory, "_get",
        side_effect=pricehistory.Offline("A different sentence, the same class."),
    )
    ok(reworded_offline is not None, "scope: a reworded Offline was refused", reworded_offline)
    ok(not is_identification(reworded_offline),
       "a reworded Offline is still a network refusal", reworded_offline)
    named_network = _refusal_through(
        pricehistory.Market, "product_id_for_row", product_ids={},
        side_effect=pricehistory.NotResolvable("The mirror could not be reached for this card."),
    )
    ok(named_network is not None, "scope: a NotResolvable whose words name a network failure "
       "was refused", named_network)
    ok(is_identification(named_network),
       "a NotResolvable whose words say 'could not be reached' still queues", named_network)
    ok(is_identification("The price service could not be reached."),
       "an untagged str that names a network failure still queues: the kind decides, not the words")

    print("\n-- every refusal class has a pinned kind, and a refusal keeps its words --")
    classes = _refusal_classes()
    ok(bool(classes), "scope: the PriceHistoryError class tree was walked", classes)
    refuse = getattr(pricehistory, "refusal", None)
    ok(refuse is not None, "pricehistory.refusal exists: the one place a raise becomes a kind")
    for cls in classes:
        want = (_kind_constant(PINNED_KINDS[cls.__name__])
                if cls.__name__ in PINNED_KINDS else "<not pinned>")
        got = "<no refusal()>" if refuse is None else _kind_of(refuse(cls("a message")))
        ok(got == want, f"{cls.__name__} maps to its pinned kind",
           f"want {want!r}, got {got!r}")
    if refuse is not None:
        changed = [cls.__name__ for cls in classes
                   if str(refuse(cls("a message"))) != "a message"]
        ok(not changed, "every refusal keeps its message text unchanged", changed)


def main() -> int:
    _verdicts_from_the_real_path()

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
            # A fourth refused sku, on a BOUND card whose evidence was never recorded
            # (`identity_source = sku`, `read_name` still the Python default `None` — a
            # card bound before `record_identification` ever wrote `read_*`, or by
            # `cards identity --write`'s own T3/T4u migration). Has a photograph, matches
            # its own refusal in every field, and STILL cannot be queued —
            # `cli/resolve.py:card_reading` answers `READING_UNAVAILABLE` for it, and this
            # is the review round's own HIGH finding: this position must be NAMED in
            # `QueueBuild.unavailable`, never silently absent (CLAUDE.md's hard rule,
            # "never drop a card without saying so").
            snapshot.inventory.cards["1/6"] = Card(
                box=1, index=6, sku="DDD", name="Warden's Hymn", number="",
                set_name="Vendetta", game="riftbound", condition="Near Mint",
                state="identified", photo="/photos/ddd-6.jpg",
                identity_source=IDENTITY_SKU,
            )

        rows = {
            "AAA": _row("AAA", "Shadbow Temple", "", "Vendetta"),
            "BBB": _row("BBB", "Kihoud Temple", "", "Vendetta"),
            "CCC": _row("CCC", "Seal of Power", "", "Spiritforged"),
            "DDD": _row("DDD", "Warden's Hymn", "", "Vendetta"),
        }
        refusals = {
            "AAA": _not_resolvable("Shadbow Temple", "", "Vendetta"),
            "BBB": _not_resolvable("Kihoud Temple", "", "Vendetta"),
            "CCC": _refusal_through(net, "request", sku="CCC", side_effect=_http(503)),
            "DDD": _not_resolvable("Warden's Hymn", "", "Vendetta"),
        }

        print("-- is_identification_refusal --")
        ok(archive_review.is_identification_refusal(refusals["AAA"]),
           "a NotResolvable message is an identification refusal")
        ok(not archive_review.is_identification_refusal(refusals["CCC"]),
           "an HTTP 503 refusal from the real fetch path is never an identification refusal")

        print("\n-- cards_for_refusals: per-card match, never per-sku --")
        inventory = Store().read().inventory
        matches = archive_review.cards_for_refusals(inventory, rows, refusals)
        positions = sorted((m.card.box, m.card.index) for m in matches)
        ok(positions == [(1, 1), (1, 4), (1, 6)],
           "1/1, 1/4 and 1/6 match their own refused identification — 1/2 (different "
           "stored number, same sku), 1/3 (sold) and 1/5 (network refusal, sku CCC) are "
           "all excluded here. 1/4 has no photo and 1/6 is bound with no recorded "
           "reading, both checked next: those filters live in queue_entries, not in the "
           "card match itself",
           positions)
        ok(all(m.reason == variant.NO_CATALOG_ROW for m in matches),
           "the reason is the existing ladder vocabulary, not a new string")

        print("\n-- queue_entries: no photo — never queued, but NAMED, never dropped --")
        # Widen refusals to include BBB alone, whose only matching card has no photo.
        # Lane 7 review: this was the OTHER silent drop CLAUDE.md's hard rule forbids —
        # the 2026-09-24 round named the no-reading gap and left this one exactly as it
        # was, and a card missing its photograph still needs a human told about it.
        bbb_matches = archive_review.cards_for_refusals(
            inventory, rows, {"BBB": refusals["BBB"]}
        )
        views = run_resolve.box_views(inventory, boxes={1})
        bbb_build = archive_review.queue_entries(bbb_matches, views)
        ok(bbb_build.entries == [], "a card with no photograph is never queued",
           bbb_build.entries)
        ok(len(bbb_build.unavailable) == 1,
           "and it IS reported as `unavailable` — named exactly once, not folded into a "
           "bare count",
           bbb_build.unavailable)
        if bbb_build.unavailable:
            skipped = bbb_build.unavailable[0]
            ok(skipped.position == "1/4", "keyed by the card's own position",
               skipped.position)
            ok("BBB" in skipped.reason and "no photograph" in skipped.reason,
               "and the reason names the SKU and says why, in plain words — never a "
               "bare code a reader has to look up", skipped.reason)

        print("\n-- queue_entries: bound, no recorded reading — NAMED, never dropped --")
        # identity-follows-sku.md §5.1 / review round, HIGH finding, 2026-09-24: a card
        # whose own refusal matched, but whose evidence was never recorded, must be named
        # in QueueBuild.unavailable rather than silently absent from the sweep's report.
        ddd_matches = archive_review.cards_for_refusals(
            inventory, rows, {"DDD": refusals["DDD"]}
        )
        ddd_build = archive_review.queue_entries(ddd_matches, views)
        ok(ddd_build.entries == [],
           "a bound card with no recorded reading builds no queue entry",
           ddd_build.entries)
        ok(len(ddd_build.unavailable) == 1, "and it is named exactly once",
           ddd_build.unavailable)
        if ddd_build.unavailable:
            skipped = ddd_build.unavailable[0]
            ok(skipped.position == "1/6", "keyed by the card's own position",
               skipped.position)
            ok("DDD" in skipped.reason and "no recorded reading" in skipped.reason,
               "and the reason names the SKU and says why, in plain words — never a "
               "bare code a reader has to look up", skipped.reason)

        print("\n-- queue_entries + apply: reaches the queue, with its photo --")
        build = archive_review.queue_entries(matches, views)
        entries = build.entries
        ok(len(entries) == 1, "exactly one entry is built", entries)
        entry = entries[0]
        ok(entry.position == "1/1", "keyed by the card's own position", entry.position)
        ok(entry.photo == "/photos/aaa-1.jpg", "carries the card's photograph", entry.photo)
        ok(entry.reason == variant.NO_CATALOG_ROW, "carries the ladder's own reason")
        ok(entry.candidates == [], "zero candidates — this is what NO_CATALOG_ROW means")
        unavailable_positions = sorted(s.position for s in build.unavailable)
        ok(unavailable_positions == ["1/4", "1/6"],
           "and 1/4 (no photo) and 1/6 (bound, no reading) are BOTH named in "
           "`unavailable` in this SAME build, beside the one real entry — never a "
           "separate, easy-to-forget pass",
           build.unavailable)

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
           "entry, D238, for why the real store's own 16 "
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
