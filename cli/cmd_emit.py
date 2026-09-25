"""`pkmnscan emit <run-dir>` — write the import CSV. Free, re-runnable.

ONE FILE, `import.csv`, AND THAT IS THE DEFAULT FOR EVERY SEND — one run or several. The
owner's instruction, verbatim: *"emit by default only should now emit only one spreadsheet by
default (with the ability to split if needed)"*. Two files per game per run was two uploads
for one errand, and a send of three runs over two games was twelve.

TWO FLAGS SPLIT IT, ON TWO DIFFERENT AXES, AND NEITHER IS THE DEFAULT ANY MORE:

    --split-threshold   the old pair back — `import-listed.csv` above the D9 cut-off,
                        `import-subthreshold.csv` below it, one pair per game
    --split-games       one file per game — `import-pokemon.csv`, `import-riftbound.csv`

`--listed-only` is a THIRD thing and is deliberately not a split: it drops the sub-threshold
rows rather than filing them elsewhere, so the valuable cards can be staged first and the
bulk can wait for a later press.

WHAT THE OLD SPLIT WAS FOR, BECAUSE IT WAS NOT COSMETIC AND `--split-threshold` IS WHY IT IS
KEPT. The valuable cards could be staged and moved live while the bulk file waited, and a
pricing mistake on the cheap file could not touch the valuable one. Both are still available
one flag away; what changed is which is the default, and the default is now the errand the
owner actually runs.

THE GAME SPLIT IS AN OPEN QUESTION AND NOT A PREFERENCE. Nobody has established that
TCGplayer's Import to Staged accepts a file spanning two `Product Line`s —
`fixtures/staged-import-accepted.csv` proves it for one line only. The owner asked for one
file and said they would test it; `--split-games` is the one-flag way back if the portal
refuses. A merged file whose games carry different export HEADERS is refused rather than
written, and the refusal names the flag.

EVERY FILE OBEYS THE NO-DUPLICATE-SKU RULE, and merging is where that could have been lost.
Two rows with one `TCGplayer Id` in one import file is undefined behaviour; the buckets are
disjoint SKU sets of one report and a SKU belongs to one `Product Line`, so a merged file
cannot contain one twice by construction — and `join.write_import` asserts it anyway,
because a property nothing checks is a comment.

THE LIVE CAP IS SPENT ONCE ACROSS EVERYTHING ONE PRESS WRITES. Inside a run that is
`SkuMatch.add_to_quantity`, which is per SKU and therefore already once whichever file the
row lands in. ACROSS runs it is `pipeline/merge.py`, which re-derives the figure over the
union of positions deduped on `(box, index)` — see `run_merged`, and D86 for the two SKUs
that reached `pushed: 6` against a cap of 4 before it existed. A merged file is never a
concatenation of the per-run CSVs.

IT REFUSES, LOUDLY, WRITING NOTHING, when:

  - the run-wide sub-threshold choice is unset while sub-threshold SKUs exist
  - a `no_market_data` SKU has no hand-entered price (D9: unknown is not cheap)
  - two rows in one file share a `TCGplayer Id`
  - any non-writable column differs from the catalog original
  - a card was queued but is not actually IN the standing queue — the "reported before any
    output is written" rule, checked against the file on disk rather than against the fact
    that `join` said it would

IT DOES NOT REFUSE for a non-empty review queue. It restates the totals beside the row
counts it wrote, so the number is in front of you at the moment you commit an import file.

Byte format is `pipeline.tcgcsv`, unchanged: unquoted header, fully quoted data fields, CRLF,
only `Add to Quantity` and `TCG Marketplace Price` ever written, `TCGplayer Id` never
modified, and `check_only_writable_changed` run per row against the catalog original.

On success every emitted SKU's `pushed` COUNT rises by the copies this run wrote into a file,
and each copy's identity write is appended to `history.jsonl`. `pushed` is a quantity of a
SKU and not a state a card wears (D7 amended) — which copies back it is deliberately
unrecorded, because every unsold copy is equally sellable and an address here would be a
fiction the pull then has to honour. `pushed` still means one thing only: a CSV was written.
Everything past it is confirmed by something outside this pipeline — see `pkmnscan reconcile`.
"""

from __future__ import annotations

from collections import OrderedDict

from cli import resolve, runs
from pipeline import corpus, decisions, join, merge, pricing, routing, sendguard, tcgcsv
from pathlib import Path

from store import master, files, photos
from store.session import Store


def _cap_for(args):
    """The ceiling this send asked for, or `None` for no cap.

    ONE VOICE, AND IT IS THE FLAG (D7, amended 2026-09-08). There were three — `--cap`, then
    `policy.live_cap`, then none — and the middle one was a standing bound the operator had
    already retired, answering four on any store whose corpus had ever been saved. The policy
    key is deleted; `pipeline/corpus.py:parse` refuses a store that still holds one rather
    than ignoring it.

    THE FIGURE IS A CEILING ON COPIES LIVE, not a send quantity, and every leg of a merged
    send is bound by the same one — `pipeline/merge.py:_merged_cap` takes the tightest any
    leg names, which under one flag is that flag.
    """
    return decisions.parse_live_cap(getattr(args, "cap", None))


def _quantities_for(args) -> dict:
    """SKU -> the copies THIS SEND asked to list, from `--quantity SKU=N` (D7, amended
    2026-09-11 on the operator's ruling). Empty is the ordinary answer: every copy that can
    go, goes. A send quantity and not a ceiling — `_cap_for` is the ceiling — and it reaches
    every leg of a merged send through this one function for `_cap_for`'s reason."""
    return decisions.parse_send_quantities(getattr(args, "quantity", None))


def _say_quantities(quantities, matches, say) -> None:
    """Name what the send's own quantities did, per card, and what they could not.

    NAMED AND NOT COUNTED (D59's rule, applied to the operator's own figures): a card asked at
    5 that goes at 3 is the one line the operator is waiting for, and a SKU named that no run
    in the send holds is a typo that would otherwise vanish — the flag would be accepted, the
    file written, and nothing anywhere would say the figure reached no card.
    """
    if not quantities:
        return
    named = [m for sku, m in matches.items() if sku in quantities]
    say("")
    say(f"{'quantities':<16} {len(named)} SKU(s) at the figure this send asked for")
    for match in named:
        asked = quantities[match.sku]
        if match.asked_short:
            say(f"{'':<16} {match.sku} {match.name} — asked {asked}, only "
                f"{match.add_to_quantity} can go")
        elif asked == 0:
            say(f"{'':<16} {match.sku} {match.name} — asked 0, none sent")
        else:
            say(f"{'':<16} {match.sku} {match.name} — {match.add_to_quantity} of "
                f"{match.copies} on hand")
    missing = sorted(sku for sku in quantities if sku not in matches)
    if missing:
        say(f"{'':<16} {len(missing)} SKU(s) named that this send does not hold: "
            f"{', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}")


class GuardRefused(Exception):
    """The live export named for the double-send guard could not be read. Nothing is written."""


class SendClaimRefused(Exception):
    """Another press holds these SKUs, or moved them while this one was deciding.

    RAISED INSIDE THE STORE WRITE, so the transaction that would have counted the copies sent
    rolls back whole (D88) and nothing this press decided is recorded. D174's rule for a
    purchase, applied to a send: the check and the claim are one transaction.
    """

    def __init__(self, conflicts, stale):
        super().__init__("send claim refused")
        self.conflicts = conflicts
        self.stale = stale


def _listing_basis() -> dict:
    """SKU -> (pushed, staged) as this press's plan will read them. Taken BEFORE the resolve.

    THE PLAN IS DECIDED OUTSIDE THE STORE LOCK and written inside it, so a second press can
    finish deciding before the first has written. `cli/resolve.py:_committed_keys` reads these
    two counts to decide which copies are still unsent; if either moved between this read and
    the write, the plan is over copies another press has already sent, and the write refuses
    rather than count them twice. This is D174's "recompute inside the transaction", reduced to
    the two figures the recompute would read.
    """
    listings = Store().read().inventory.listings
    return {sku: (int(entry.pushed), int(entry.staged)) for sku, entry in listings.items()}


def _out(run_dir, name, args):
    """Where one import file goes: the press's own directory when it has one, else the run's."""
    own = getattr(args, "send_dir", None)
    return Path(own) / name if own else run_dir.path(name)


def _claim_or_refuse(writable, going, basis, args, priced=()) -> None:
    """Check every live send claim and the plan's basis, then claim. One transaction.

    `going` is SKU -> the copies this press's file adds. Called at the top of the store write
    that counts them sent; raises `SendClaimRefused` to roll that write back.

    `priced` is the SKUs of this press's PRICE-ONLY rows. They are CHECKED against every live
    claim, so a price change never races a mark-down or a send still in flight over the same
    card, and they are NEVER CLAIMED: a row that adds no copy holds no copy.
    """
    from store import sendclaims

    own = getattr(args, "send_claim", None)
    conflicts = writable.send_claims.overlap(set(going) | set(priced), excluding=own)
    stale = []
    for sku in sorted(going):
        entry = writable.inventory.listings.get(sku)
        now = (int(entry.pushed), int(entry.staged)) if entry is not None else (0, 0)
        if now != basis.get(sku, (0, 0)):
            stale.append(sku)
    if conflicts or stale:
        raise SendClaimRefused(conflicts, stale)
    # A PRESS THAT ADDS NO COPY CLAIMS NOTHING (the round-2 review, F5). An empty claim holds
    # no card, and nothing would ever release it: the press that wrote it has no file to send.
    if own and going:
        writable.send_claims.claim(
            own,
            sendclaims.KIND_LISTING,
            dict(going),
            pid=getattr(args, "claim_holder", None),
        )


def _say_claim_refusal(refusal, args, say) -> None:
    """Name the refusal, then print its one JSON line for `server/send_routes.py` to read."""
    import json

    say("")
    for claim, shared in refusal.conflicts:
        say(
            f"REFUSING: the send {claim.stamp} (started {claim.started_at}) is already sending "
            f"{len(shared)} of these card(s): {', '.join(shared[:6])}"
        )
    if refusal.stale:
        say(
            f"REFUSING: another press sent {len(refusal.stale)} of these card(s) while this one "
            f"was deciding: {', '.join(refusal.stale[:6])}. Press again to send what is left."
        )
    if not getattr(args, "send_dir", None):
        say("The file written above was NOT counted as sent. Do not upload it.")
    say("Nothing was counted as sent.")
    say(
        json.dumps(
            {
                "send_claim": {
                    "conflicts": [
                        {"stamp": claim.stamp, "started_at": claim.started_at, "skus": shared}
                        for claim, shared in refusal.conflicts
                    ],
                    "stale": list(refusal.stale),
                }
            },
            sort_keys=True,
        )
    )


def _live_guard(args):
    """The live export this send was guarded by, read once: `(name, SKU -> live copies)`, or
    None when the press named no guard (`--live-guard`).

    A FILE THAT CANNOT BE READ IS A REFUSAL, NEVER NO GUARD. A guard that failed open on a bad
    file is the dry-run block-list this repo has already paid for once.
    """
    path = getattr(args, "live_guard", None)
    if not path:
        return None
    target = Path(path)
    try:
        export = tcgcsv.read_export(target)
        live = sendguard.live_by_sku(export.rows, export.header)
    except (OSError, ValueError, tcgcsv.MalformedCsv) as exc:
        raise GuardRefused(f"the live export {target.name} could not be read: {exc}") from None
    return target.name, live


def _apply_guard(guard, matches_by_sku, inventory):
    """Bound every matched SKU by the guard's room. Returns what `_say_guard` reads, or None.

    `matches_by_sku` is SKU -> every match that sends it (one on the single-run path, one per
    leg on the merged path). The room is computed ONCE over the union of their positions, and
    every leg is bounded by it, so the merged plan's `min` over legs is the union's room and
    never one leg's share of it.

    IT WRITES `asked`, THE SEND QUANTITY `--quantity` ALREADY SETS, AND ONLY EVER LOWERS IT.
    That is the existing primitive for "fewer copies of this card this press"
    (`pipeline/join.py:SkuMatch.add_to_quantity`), so `live_keys` and `pushed` below read the
    trimmed figure with no second code path.
    """
    if guard is None:
        return None
    name, live = guard
    rooms = {}
    held = {}
    for sku, matches in matches_by_sku.items():
        keys = sorted(
            {
                master.position_key(position.box, position.index)
                for match in matches
                for position in match.positions
            }
        )
        held[sku] = sendguard.on_hand(inventory.copies_on_hand(sku), inventory.cards, keys)
        rooms[sku] = sendguard.room(live.get(sku, 0), held[sku])
        for match in matches:
            if match.asked is None or match.asked > rooms[sku]:
                match.asked = rooms[sku]
    return {"name": name, "live": live, "held": held, "rooms": rooms}


def _say_guard(applied, would_by_sku, names, say) -> None:
    """Name what the guard trimmed, then print its one JSON line for the route to read.

    `would_by_sku` is what each SKU would have added WITHOUT the guard: the send's own room,
    bounded by any quantity the operator typed. NAMED PER SKU (D59): a trimmed copy is the one
    line the operator is waiting for, and a trim nobody named is a silent drop.
    """
    if applied is None:
        return
    import json

    trimmed = sendguard.trims(
        applied["live"], would_by_sku, applied["rooms"], applied["held"], names
    )
    say("")
    say(f"{'live guard':<16} {len(would_by_sku)} SKU(s) checked against {applied['name']}")
    for trim in trimmed[:8]:
        say(
            f"{'':<16} {trim.sku} {trim.name} — TCGplayer holds {trim.live} of "
            f"{trim.on_hand} on hand; {trim.would} would have gone, {trim.goes} goes"
        )
    if len(trimmed) > 8:
        say(f"{'':<16} ...and {len(trimmed) - 8} more")
    if not trimmed:
        say(f"{'':<16} nothing trimmed")
    say(json.dumps(sendguard.report(applied["name"], len(would_by_sku), trimmed), sort_keys=True))


def _typed_skus(choice) -> set:
    """The SKUs whose price is the owner's own: an `overrides` price, or a hand-entered
    `no_market_data` price. Never a price the standing rule gives, and never a hold."""
    from decimal import Decimal

    out = set(choice.dispositions())
    out |= {sku for sku, value in choice.no_market_data.items() if isinstance(value, Decimal)}
    return out


class PriceRefused(Exception):
    """`--reprice-live` was asked for in a shape this press cannot honour. A sentence."""


def _price_changes(args, guarded, candidates, typed):
    """The price-only rows this press writes, or [] when it asked for none (`--reprice-live`).

    `candidates` is SKU -> (name, the plan's price) for every SKU this press prices and adds
    NO copy of. The live figures come off the same export the double-send guard read, so the
    two halves of one press never disagree about what TCGplayer holds.
    """
    if not getattr(args, "reprice_live", False):
        return []
    if guarded is None:
        raise PriceRefused(
            "--reprice-live needs --live-guard: a price change is only ever measured against "
            "what TCGplayer holds right now"
        )
    try:
        prices = sendguard.live_prices(tcgcsv.read_export(Path(args.live_guard)).rows)
    except (OSError, ValueError, tcgcsv.MalformedCsv) as exc:
        raise PriceRefused(f"the live export's prices could not be read: {exc}") from None
    return sendguard.price_changes(candidates, typed, guarded["live"], prices)


def _say_prices(changes, args, say) -> None:
    """Name every price-only row, then print the one JSON line the route reads."""
    if not getattr(args, "reprice_live", False):
        return
    import json

    say("")
    say(f"{'price changes':<16} {len(changes)} card(s) already live, Add to Quantity 0")
    for change in changes[:8]:
        was = f"${change.was}" if change.was is not None else "no price"
        say(f"{'':<16} {change.sku} {change.name} — {was} to ${change.price}")
    if len(changes) > 8:
        say(f"{'':<16} ...and {len(changes) - 8} more")
    say(json.dumps(sendguard.price_report(changes), sort_keys=True))


def _record_prices(writable, changes, run) -> None:
    """D243: a price that reached a file is a posting, and `replaced` is the live price it
    moves. Inside the store write that commits the press, so a refused press posts nothing."""
    for change in changes:
        writable.postings.record(
            sku=change.sku, price=change.price, source="emit-price", run=run, replaced=change.was
        )


def _price_row(match, price):
    """One price-only row: the catalogue's own row, Add to Quantity 0, the plan's price."""
    return tcgcsv.set_writable(match.row, add_to_quantity=0, marketplace_price=price)


def _keep_listed(changes, sub_skus, args, say):
    """`--listed-only` drops the sub-threshold rows, price-only rows too, and names them."""
    if not args.listed_only:
        return list(changes)
    left = [change for change in changes if change.sku in sub_skus]
    if left:
        say(f"{'price changes':<16} {len(left)} under the cut-off left for a later emit "
            "— --listed-only")
    return [change for change in changes if change.sku not in sub_skus]


def _zero_rows_single(resolved, priced, changes, args, say):
    """The single-run path's price-only rows, per game and bucket: `(by_game, kept changes)`.

    `by_game` is game -> {"listed": rows, "sub": rows}. The bucket is the SKU's own, read off the
    same report the listing rows are partitioned by, so `--split-threshold` files a price-only
    row beside the listing rows of its own bucket.
    """
    below = {
        sku for game_join in resolved.joins.values() for sku in game_join.report.below_threshold.skus
    }
    changes = _keep_listed(changes, below, args, say)
    wanted = {change.sku for change in changes}
    by_game = {}
    for game_join in resolved.joins.values():
        game = game_join.game
        rows = {"listed": [], "sub": []}
        for sku, match in game_join.report.matches.items():
            if sku in wanted and sku in priced[game]:
                rows["sub" if sku in below else "listed"].append(_price_row(match, priced[game][sku]))
        by_game[game] = rows
    return by_game, changes


def _would(match, typed) -> int:
    """What one match adds with the operator's own figure applied and no guard."""
    room = match.room
    asked = typed.get(match.sku)
    return room if asked is None else max(0, min(asked, room))


def _warn_stale(run_dir, say) -> None:
    """Name any import file left by an EARLIER emit, at the moment this one refuses.

    Refusing writes nothing, which correctly leaves a previously-valid file alone — but a
    refusal message sitting next to an `import-listed.csv` from an hour ago is exactly how
    a stale file gets imported. Deleting it would be worse: that file may be the one already
    staged. So it is named, not removed. Globbed rather than listed, because the import
    files are per-game now and a stale one is stale whichever game wrote it.
    """
    # ONE GLOB OVER EVERY SHAPE THIS COMMAND CAN WRITE. It listed the two per-game bucket
    # names and would have said nothing about `import.csv`, which is the file the default
    # press now leaves behind — the exact stale file this function exists to name.
    stale = sorted(run_dir.directory.glob("import*.csv"))
    if not stale:
        return
    say("")
    say("NOTE: this run directory still holds import files from an EARLIER emit.")
    say("They are unchanged and may be out of date. Do not import them as this run's output:")
    for path in stale:
        say(f"    {path}")


def _scoped(dispositions, report):
    """The per-SKU dispositions that belong to this game's report.

    The answers are scoped to the run and SKUs are TCGplayer-global, so with one report per
    game a disposition for a pokemon SKU must not reach the riftbound pricing pass —
    `prices_for` would refuse it as naming a SKU "not in this batch", which is true of the
    slice and false of the run. The run-level version of that refusal still stands: `run`
    below checks every disposition names SOME game's match before any file is written.
    """
    return {sku: d for sku, d in dispositions.items() if sku in report.matches}


def _game_only(report, priced):
    """(listed, sub_threshold) SKU sets for one game's report — emit's two files.

    INTERSECTED WITH WHAT WILL ACTUALLY BE WRITTEN, RATHER THAN GUESSED AT BY SUBTRACTING
    THE EXCLUSIONS WE HAPPENED TO THINK OF. `_write` decides whether to open a file at all
    from whether `only` is empty, and `tcgcsv.render` emits the header before it iterates
    rows — so any SKU that survives here and is then dropped by `import_rows` is a
    header-only file on disk, reported as `0 row(s)`.

    THREE THINGS DROP A SKU AFTER THIS POINT AND THIS FUNCTION USED TO KNOW ABOUT ONE:

      - it is WITHHELD (D49) — `prices_for` leaves it out of the price mapping. Subtracted
        here since 2026-08-29, which is the version of this docstring D54 replaces.
      - it is `no_market_data` ANSWERED `"unlisted"` — `prices_for` drops it too, and
        nothing subtracted it. LIVE ON A FIRST EMIT for a game whose only above-threshold
        entries are unpriced-and-unlisted.
      - its `add_to_quantity` is 0, every copy already committed — which is every SKU on a
        re-emit, and is the one that destroyed the file.

    `priced` is `prices_for`'s output, which is exactly the set `import_rows` prices, so
    intersecting with it closes the first two by construction rather than by enumeration.
    The `add_to_quantity` filter closes the third. What is left cannot be dropped downstream,
    which is what makes `only` a promise rather than an estimate.
    """
    writable = {
        sku for sku in priced if report.matches[sku].add_to_quantity > 0
    }
    listed = {m.sku for m in report.matches.values() if m.listable} | {
        m.sku for m in report.no_market_data
    }
    return listed & writable, set(report.below_threshold.skus) & writable


def _write(game_join, path, only, choice, say, label, extra=()):
    """Write one import file, or leave it alone. Returns the SKUs that reached it.

    ROWS ARE COMPUTED, THEN LOOKED AT, THEN WRITTEN — never computed inside the writer. D54:
    `emit` never opens an import file until it has at least one row for it, because
    `tcgcsv.render` emits the header before it iterates and an empty write therefore replaces
    a good file with a valid CSV of nothing.

    THE EMPTY GUARD STAYS EVEN THOUGH `only` IS NOW EXACT. `_game_only` intersects with what
    `import_rows` will price, so the two should never disagree — and this line is what proves
    it rather than assumes it. It is one branch against a file the operator has already been
    told to import.
    """
    if not only and not extra:
        say(f"{label:<16} nothing to write")
        return []
    rows = join.import_rows(
        game_join.report,
        sub_threshold=choice.sub_threshold,
        sku_dispositions=_scoped(choice.dispositions(), game_join.report),
        no_market_data=choice.no_market_data,
        # UNSCOPED, deliberately, where `sku_dispositions` beside it is scoped: `prices_for`
        # refuses a disposition naming a SKU this game's report does not hold, and has no such
        # check on this set — see the comment at the skip. So a run-wide set is harmless here
        # and scoping it would be machinery guarding nothing.
        withheld=set(choice.withheld()),
        only=only,
    ) if only else []
    # THE PRICE-ONLY ROWS OF THIS BUCKET, after the listing rows. Their SKUs are disjoint from
    # `only` (a SKU in `only` adds a copy), so the file still holds one row per SKU.
    rows = list(rows) + list(extra)
    if not rows:
        say(f"{label:<16} nothing new to write — {path.name} left as it is")
        return []
    data = join.write_import(game_join.catalog, path, rows)
    written = tcgcsv.parse(data)
    quantity = sum(int(row[tcgcsv.QUANTITY_COLUMN] or 0) for row in written.rows)
    say(f"{label:<16} {len(written.rows)} row(s), {quantity} card(s) -> {path}")
    # THE SKUS THAT ADD A COPY, and only those: `emitted` raises `pushed` off this list, and a
    # price-only row adds nothing to raise it by.
    return [
        row[tcgcsv.SKU_COLUMN]
        for row in written.rows
        if tcgcsv.parse_quantity(row[tcgcsv.QUANTITY_COLUMN]) > 0
    ]


class SplitRefused(Exception):
    """One file was asked for over games whose exports carry different columns.

    ITS OWN CLASS SO THE CALLER'S EXISTING REFUSAL BLOCK CATCHES IT. `run` already turns
    `OutputSuppressed`, `Undecided` and `ReadOnlyColumn` into "REFUSING to write. Nothing was
    written." with the stale-file warning under it, and this is the same kind of event: a
    whole-send refusal raised before a single byte is written.
    """


def _merged_targets(rows_by_game, run_dir, split_games, out=None):
    """(path, catalog, rows) for each file one press should write, refusing an impossible one.

    `rows_by_game` is game -> the rows that game contributed, already priced and already
    filtered. With `--split-games` each game gets its own file and no header question arises.
    Without it there is ONE file, and a file whose rows came from two different export headers
    is malformed in a way no reader here would notice — so the headers are compared rather
    than assumed, and the refusal names the flag that fixes it.
    """
    place = out or (lambda name: run_dir.path(name))
    if split_games:
        return [
            (
                place(runs.import_merged_name(game)),
                game_join.catalog,
                rows,
            )
            for game, (game_join, rows) in rows_by_game.items()
            if rows
        ]
    carrying = [
        (game, game_join, rows) for game, (game_join, rows) in rows_by_game.items() if rows
    ]
    if not carrying:
        return []
    headers = {tuple(game_join.catalog.header) for _, game_join, _ in carrying}
    if len(headers) > 1:
        raise SplitRefused(
            "these games' exports carry different columns, and one file needs one header. "
            "Re-run with --split-games. (" + ", ".join(g for g, _, _ in carrying) + ")"
        )
    merged = [row for _, _, rows in carrying for row in rows]
    return [(place(runs.import_merged_name()), carrying[0][1].catalog, merged)]


def _write_merged(resolved, priced, choice, run_dir, args, say, zero=None):
    """The default: one import file, both buckets in it. Returns (listed SKUs, sub SKUs).

    THE TWO BUCKETS ARE ONE `import_rows` CALL PER GAME, NOT TWO CONCATENATED. `only` is the
    union of the two SKU sets, so each SKU is priced once and written once — which is what
    makes the no-duplicate-SKU rule a property here rather than a thing to check. The buckets
    are disjoint by construction (`_game_only` partitions one report on `listable`), so the
    union cannot hold a SKU twice, and the cap is `SkuMatch.add_to_quantity` — per SKU, and
    therefore spent once whichever file the row lands in.

    THE SPLIT IS STILL COMPUTED, because the manifest keeps it. D54 makes `emitted` a union
    that `reconcile` reads in both directions, and its `listed`/`sub_threshold` lists are what
    a screen tells the two apart by. One file on disk does not mean one bucket in the record.

    D54's EMPTY GUARD IS PER FILE AND IS NOT OPTIONAL. `tcgcsv.write_csv` emits the header
    before it iterates rows, so a write with no rows replaces a good file with a valid CSV of
    nothing — the exact destruction D54 was written about, and merging gives it one more way
    to happen, because a file can now be empty for every game at once.
    """
    rows_by_game = OrderedDict()
    listed_skus = []
    sub_skus = []
    for game_join in resolved.joins.values():
        game = game_join.game
        listed, sub = _game_only(game_join.report, priced[game])
        only = listed if args.listed_only else (listed | sub)
        rows = (
            join.import_rows(
                game_join.report,
                sub_threshold=choice.sub_threshold,
                sku_dispositions=_scoped(choice.dispositions(), game_join.report),
                no_market_data=choice.no_market_data,
                withheld=set(choice.withheld()),
                only=only,
            )
            if only
            else []
        )
        # THE PRICE-ONLY ROWS, after the listing rows (`_zero_rows_single`). `--listed-only`
        # already left the sub-threshold ones out and named them.
        extra = (zero or {}).get(game) or {}
        rows = list(rows) + list(extra.get("listed") or []) + list(extra.get("sub") or [])
        rows_by_game[game] = (game_join, rows)
        if args.listed_only and sub:
            say(f"{'sub-threshold':<16} {len(sub)} SKU(s) left for a later emit "
                "— --listed-only")

    targets = _merged_targets(
        rows_by_game, run_dir, args.split_games, out=lambda name: _out(run_dir, name, args)
    )
    if not targets:
        # THE SENTENCE `_write` GIVES, KEPT WORD FOR WORD. An operator pressing emit a second
        # time reads the same thing whichever shape they asked for, and the caller's D54
        # branch below turns it into the "nothing new to send" report.
        say(f"{'import':<16} nothing new to write — every row is already sent")
        return [], []

    for path, catalog, rows in targets:
        data = join.write_import(catalog, path, rows)
        written = tcgcsv.parse(data)
        quantity = sum(int(row[tcgcsv.QUANTITY_COLUMN] or 0) for row in written.rows)
        say(f"{'import':<16} {len(written.rows)} row(s), {quantity} card(s) -> {path}")

    # THE BUCKETS ARE READ BACK OFF WHAT REACHED A FILE, never off what was offered to one.
    # `import_rows` drops a zero-quantity row after `_game_only` has already counted its SKU,
    # and D54's whole finding is that the record must describe the FILE.
    shipped = {row[tcgcsv.SKU_COLUMN] for _, _, rows in targets for row in rows}
    for game_join in resolved.joins.values():
        listed, sub = _game_only(game_join.report, priced[game_join.game])
        listed_skus += sorted(listed & shipped)
        sub_skus += sorted(sub & shipped)
    return listed_skus, sub_skus



def _name_for(key: str, photo) -> str:
    """The card's name for a position the store has never seen (D172, section 3.4).

    TWO OF `store/master.py`'s THREE "seam to watch rather than a guarantee" SITES ARE IN
    THIS FILE, and this is what they were missing. `record_capture` refuses a nameless new
    card — the refusal lives at the BIRTH of a record because a refusal at the flush would be
    a 500 on the shutter mid-feeder — so an emit over a run whose positions the store has
    never seen refused outright without this. That case is real and this file's own comment
    names it: "a position the store has never seen — a run joined from a recovered
    identifications file, say".

    THE LADDER IS THE SPEC'S, BOTH RUNGS. Where the run resolved a photograph, the name is
    that photograph's digest — which is D172's definition exactly, read off the disk rather
    than allocated, so the record this creates is named the same way one born at the shutter
    is. Where it did not, there is no photograph and no digest anywhere, and the honest
    answer is shape 4: a NAME that says so, never a NULL. A NULL cannot distinguish "no
    photograph was found" from "this writer did not look", which is this repo's signature
    defect.

    IT CARRIES `master.now()` AND NOT THE RECORD'S `captured_at`, which is absent here by
    construction: this is the first time the store has seen the position, so there is no
    capture stamp to borrow. The stamp is what keeps two photograph-less cards in one box
    from composing one name.
    """
    if photo:
        try:
            return photos.sha256_of(Path(photo))
        except OSError:
            # The manifest resolved a path and the file is not there. Falling through to
            # shape 4 is right and is not a swallowed error: the position genuinely has no
            # photograph to be named by, and the name says exactly that.
            pass
    return f"{photos.NOPHOTO_PREFIX}{key}@{master.now()}"


def run(args, say) -> int:
    # THE CAP IS PARSED FIRST, SO AN UNUSABLE ONE IS A SENTENCE (D7, amended 2026-09-08).
    # `_cap_for` raises `MalformedDecisions`, and the only `except` that names it wraps
    # `Corpus.read()` — the call itself sits inside a `try` catching `join.EmptyCatalog`
    # alone, so `--cap 0` came back as a traceback. Tolerable while `policy.live_cap` was the
    # ordinary door and this flag was the exception; not on the ONLY door. Parsed here rather
    # than defended at the call site because both paths need it and neither should do work
    # first: a refusal after the store has been read is a refusal that already cost something.
    try:
        _cap_for(args)
        # AND THE QUANTITIES, for the same reason and at the same moment: a malformed pair is
        # a sentence before the store is read, not a traceback after it.
        _quantities_for(args)
    except decisions.MalformedDecisions as refusal:
        say(str(refusal))
        return 1

    # ONE RUN OR SEVERAL, AND THE SINGLE-RUN PATH IS UNTOUCHED. A send of one still writes the
    # two per-game files it always did, so every run already on disk, every harness case and
    # every reconcile written before D86 behaves identically. `run_merged` is reached only by
    # naming more than one run, which is a thing nobody could do until now.
    named = args.run_dir if isinstance(args.run_dir, list) else [args.run_dir]
    if len(named) > 1:
        return run_merged(args, say)
    # BEFORE THE RESOLVE, which is what makes it the plan's basis (`_listing_basis`).
    basis = _listing_basis()
    run_dir = runs.open_run(named[0])
    if _legacy_refusal(run_dir, say):
        say("Nothing was written.")
        return 1
    try:
        plan = resolve.exports_for(run_dir, args.export)
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    # ------------------------------------------------------- READ BEFORE RESOLVING, AND WHY
    #
    # THE PRICING ANSWER IS ONE FILE, AND THIS BLOCK USED TO SIT BELOW `resolve.load`. That
    # ordering is what made the answer file's `rule` and `basis` INERT: the resolve above read
    # them from the run MANIFEST, `prices_for` prices from `SkuMatch.rule` which the resolve
    # sets, and this file's `rule` reached exactly one consumer — the `pricing` line printed a
    # few lines down. So an operator editing `"rule": "undercut:5"` here got a run that PRINTED
    # `rule=undercut:5` and priced every row at market, with nothing anywhere saying they
    # disagreed.
    #
    # The owner's instruction, on being shown it: "I don't understand this it seems like some
    # stuff is in conflict and it shouldn't be, resolve this." One source of truth, and it is
    # this file — which is what `pipeline/decisions.py`'s own docstring has claimed since it was
    # written: *"the pricing decision, as a file rather than as a flag"*. The manifest keeps
    # `rule`/`basis` as the RECORD of what the join was run with (`report.txt` prints them), and
    # a record is not an authority.
    #
    # `UnknownRule` and `UnknownBasis` are caught here as well as `MalformedDecisions`, and that
    # is not tidiness: they are `ValueError`s and NOT `MalformedDecisions` (pipeline/pricing.py),
    # nothing above `cli/__main__.py` caught them, and the policy is typed by hand into
    # `inventory/prices.json` as often as it is pressed on `#/pricing` — so a document can
    # reach every one of these states, and each has to be a sentence rather than a traceback.
    # THE CORPUS IS THE ANSWER AND THE RUN DIRECTORY IS NOT (D86). See `cli/cmd_join.py` at the
    # same seam and `pipeline/corpus.py`'s header for why the per-SKU half of the old run file
    # left the run: a price is a fact about a SKU, and one stored per drawer was one answer per
    # drawer. A legacy run file is not read as a fallback — `_legacy_refusal` refused on it
    # above, before anything was read — it is folded in once by `pkmnscan prices adopt`.
    try:
        book = corpus.Corpus.read()
    except (
        decisions.MalformedDecisions,
        pricing.UnknownRule,
        pricing.UnknownBasis,
        pricing.InvalidThreshold,
    ) as exc:
        say(f"{corpus.FILENAME} is unusable: {exc}")
        return 1
    # THE POLICY BEFORE THE RESOLVE, THE ANSWERS AFTER IT. `resolve.load` needs the rule and
    # the basis to price a match at all; the per-SKU narrowing below needs the match list,
    # which does not exist until it has run. Two reads of one document rather than a document
    # read twice.
    policy = book.policy_for(run_dir.name)

    try:
        resolved = resolve.load(
            run_dir,
            plan.by_game,
            rule=pricing.Rule.parse(policy["rule"]),
            basis=pricing.check_basis(policy["basis"]),
            # THE STORED CUT-OFF, WHICH IS WHAT DECIDES WHICH ROWS ARE SUB-THRESHOLD AND SO
            # WHICH FILE THEY LAND IN UNDER `--split-threshold`. Same source as `rule` and
            # `basis` one line up and for the identical reason: `emit` re-derives the join,
            # and a derivation that read the module constant while the operator had set
            # something else would partition this run differently from the `join` that
            # produced the report they are looking at.
            threshold=pricing.check_threshold(policy["threshold"]),
            # THE SEND'S OWN CAP, AND THE ONLY PLACE ONE IS NAMED (D7, amended 2026-09-08).
            # `--cap N` or nothing; the standing policy key that used to sit between them is
            # deleted, and a store still holding one is refused when the corpus is opened.
            live_cap=_cap_for(args),
            # AND THE PER-CARD QUANTITIES THIS SEND ASKED FOR (D7, amended 2026-09-11).
            quantities=_quantities_for(args),
            review_below=run_dir.manifest.get(
                "review_below_confidence", args.review_below_confidence
            ),
        )
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    # SCOPED TO THIS RUN'S OWN MATCHES, WHICH IS NOT OPTIONAL. The refusal below —
    # `sku_dispositions names SKUs not in this batch` — is right for a run file, where a name
    # matching nothing is a typo, and wrong for a corpus that holds every card this operator
    # has ever priced and is expected to name thousands this run does not. Narrowed here
    # rather than by weakening the check, which is what catches a real typo.
    choice = book.scoped_to(
        set(resolved.matches),
        run_name=run_dir.name,
        unpriced=resolved.no_market_data_skus,
    )


    store = Store()
    snapshot = store.read()

    # THE DOUBLE-SEND GUARD, BEFORE ANY GATE BELOW AND BEFORE ANY FILE. It lowers `asked` on
    # the matches the file is built from, so every write below reads the trimmed figure.
    try:
        guarded = _apply_guard(
            _live_guard(args),
            {sku: [match] for sku, match in resolved.matches.items()},
            snapshot.inventory,
        )
    except GuardRefused as refusal:
        say(f"REFUSING to write: {refusal}. Nothing was written.")
        return 1
    typed = _quantities_for(args)
    _say_guard(
        guarded,
        {sku: _would(match, typed) for sku, match in resolved.matches.items()},
        {sku: match.name for sku, match in resolved.matches.items()},
        say,
    )

    # --------------------------------------------------- reported before any output exists
    missing = sorted(
        position
        for position in resolved.queued_positions
        if position not in snapshot.review.entries
        and position not in snapshot.parked.entries
    )
    if missing:
        say("REFUSING to write: cards were routed to a queue but are not in one on disk.")
        say("Run `pkmnscan join` first — nothing may be written before they are recorded.")
        for position in missing[:10]:
            say(f"    {position}")
        _warn_stale(run_dir, say)
        return 1

    # ------------------------------------------------------------------ decisions gate
    blocking = choice.blocking(resolved.sub_threshold_skus)
    if blocking:
        say(f"REFUSING to write. Nothing was written. Answer it on #/pricing, or edit\n{files.prices_path()}:")
        for reason in blocking:
            say(f"    - {reason}")
        _warn_stale(run_dir, say)
        return 1

    say("")
    say(f"pricing          {choice.describe}")
    for warning in choice.warnings:
        say(f"                 note: {warning}")

    # --------------------------------------------------------------------- write the files
    # One import file per game, and a WHOLE-RUN validation pass before the first byte is
    # written. With a single file, "REFUSING to write. Nothing was written." was a
    # property of `emit_import` raising before its write; with one file per game a
    # refusal on the second game would otherwise leave the first game's file behind —
    # a partial emit that looks complete. So every game is priced and gated first, and
    # only a run that will fully succeed writes anything.
    multi = len(resolved.joins) > 1
    # BOUND ONCE FOR THE WHOLE RUN. Held SKUs are store-wide — a hold is one corpus row and a
    # SKU is TCGplayer-global — and unlike `dispositions` they are never scoped
    # per game, because nothing refuses on an unknown one.
    withheld = set(choice.withheld())
    say("")
    try:
        unknown = set(choice.dispositions()) - set(resolved.matches)
        if unknown:
            raise join.Undecided(
                f"sku_dispositions names SKUs not in this batch: {sorted(unknown)}"
            )
        # KEPT, WHERE THIS PASS USED TO THROW IT AWAY. `prices_for`'s output IS the set
        # `import_rows` will price, so `_game_only` intersects with it rather than guessing
        # which exclusions to subtract — see its docstring for the three that drop a SKU and
        # the two that were not being subtracted.
        priced = {}
        for game_join in resolved.joins.values():
            report = game_join.report
            if not report.ok:
                raise join.OutputSuppressed(
                    "output suppressed; unmatched must be reported first:\n"
                    + "\n".join(f"  - {r}" for r in report.blocking_reasons)
                    + "\n"
                    + report.report()
                )
            priced[game_join.game] = join.prices_for(
                report,
                sub_threshold=choice.sub_threshold,
                sku_dispositions=_scoped(choice.dispositions(), report),
                no_market_data=choice.no_market_data,
                withheld=withheld,
            )

        # THE PRICE-ONLY ROWS (the owner's ruling, 2026-09-24: "Allow mixed"). A SKU this run
        # prices and adds no copy of, already live, whose typed price differs from the live one.
        # Built here, off the same `priced` mapping the listing rows use, so a price-only row
        # and a listing row can never carry two prices for one card.
        changes = _price_changes(
            args,
            guarded,
            {
                sku: (resolved.matches[sku].name, price)
                for by_game in priced.values()
                for sku, price in by_game.items()
                if resolved.matches[sku].add_to_quantity == 0
            },
            _typed_skus(choice),
        )
        zero, changes = _zero_rows_single(resolved, priced, changes, args, say)

        # TWO SHAPES, ONE SET OF ROWS. Whichever branch runs, the rows come out of the same
        # `priced` mapping and the same `_game_only` partition, so the flag decides how many
        # files the rows are spread over and never which rows exist. That is what keeps
        # `--split-threshold` from being a second emitter that can drift from this one.
        listed_skus = []
        sub_skus = []
        if args.split_threshold:
            for game_join in resolved.joins.values():
                game = game_join.game
                if multi:
                    say(f"[{game}]")
                listed, sub = _game_only(game_join.report, priced[game])
                listed_skus += _write(
                    game_join,
                    _out(run_dir, runs.import_listed_name(game), args),
                    listed,
                    choice,
                    say,
                    "listed",
                    extra=zero[game]["listed"],
                )
                if args.listed_only:
                    # NAMED, NOT SILENTLY SKIPPED. `--listed-only` with `--split-threshold`
                    # is a legitimate pair — file the valuable cards now, leave the bulk for
                    # a later press — and a sub-threshold file that simply did not appear
                    # would read as "there were none".
                    if sub:
                        say(f"{'sub-threshold':<16} {len(sub)} SKU(s) left for a later "
                            "emit — --listed-only")
                    continue
                sub_skus += _write(
                    game_join,
                    _out(run_dir, runs.import_subthreshold_name(game), args),
                    sub,
                    choice,
                    say,
                    "sub-threshold",
                    extra=zero[game]["sub"],
                )
        else:
            listed_skus, sub_skus = _write_merged(
                resolved, priced, choice, run_dir, args, say, zero
            )
    except (
        join.OutputSuppressed,
        join.Undecided,
        tcgcsv.ReadOnlyColumn,
        SplitRefused,
        PriceRefused,
    ) as exc:
        say("REFUSING to write. Nothing was written.")
        for line in str(exc).splitlines():
            say(f"    {line}")
        _warn_stale(run_dir, say)
        return 1

    emitted = set(listed_skus) | set(sub_skus)
    # THE SAME MAPPING `import_rows` PRICED FROM, FLATTENED ACROSS GAMES — never a second
    # computation of a price, only a lookup of the one `priced[game]` already decided
    # (D243). A SKU belongs to exactly one game, so this cannot collide.
    priced_flat = {sku: price for by_game in priced.values() for sku, price in by_game.items()}
    at_cap = [m for g in resolved.joins.values() for m in g.report.at_cap]
    if at_cap:
        # NAMED PER SKU, because "already at the live cap" is almost never the reason
        # (D59): `live_before` reads 0 on every copy of an import this pipeline has not
        # seen land, so the old line told the operator TCGplayer already holds nothing.
        say(f"{'no room':<16} {len(at_cap)} SKU(s) matched and added nothing")
        for match in at_cap[:8]:
            say(f"{'':<16} {match.sku} — {match.nothing_to_add}")
    _say_quantities(_quantities_for(args), resolved.matches, say)
    _say_prices(changes, args, say)

    # ---------------------------------------------------------- pushed, and the audit trail
    #
    # TWO WRITES PER SKU, AND THEY ARE ABOUT DIFFERENT THINGS. The card gets its identity —
    # `sku`, `condition`, the run that decided them — because that is a fact about the
    # physical object at that position. The SKU's `Listing` gets the count, because how many
    # copies are pushed is a fact about the listing and deliberately not about any copy: the
    # owner's ruling is that copies are fungible, so an address here would be a fiction the
    # pull would then have to honour.
    pushed = 0
    pushed_skus = 0
    going = {
        sku: int(resolved.matches[sku].add_to_quantity)
        for sku in (set(listed_skus) | set(sub_skus))
        if sku in resolved.matches and resolved.matches[sku].add_to_quantity > 0
    }
    try:
        with store.write() as writable:
            _claim_or_refuse(writable, going, basis, args, [c.sku for c in changes])
            pushed, pushed_skus = _stamp_single(writable, resolved, emitted, priced_flat, run_dir)
            _record_prices(writable, changes, run_dir.name)
            queue_line = writable.queue_summary
            stages = writable.inventory.listing_counts()
    except SendClaimRefused as refusal:
        _say_claim_refusal(refusal, args, say)
        return 1
    return _after_single(
        args, say, resolved, run_dir, listed_skus, sub_skus, pushed, pushed_skus,
        queue_line, stages, len(changes),
    )


def _stamp_single(writable, resolved, emitted, priced_flat, run_dir):
    """The single-run write: stamp every matched copy, count the sent ones. `(pushed, skus)`."""
    pushed = 0
    pushed_skus = 0
    for match in resolved.matches.values():
        # IDENTITY IS WRITTEN FOR EVERY MATCHED SKU; ONLY THE COUNT WAITS FOR A FILE.
        #
        # This was one `continue` doing two jobs, and it was right for exactly as long as
        # "reached an import file" and "we know what this card is" meant the same thing.
        # A withhold (D49) splits them for the first time: the join resolved the card to a
        # catalog row, so the identity is known — and nothing was pushed, so the count must
        # not move. Skipping both left a held card wearing `state: captured` with no `sku`,
        # invisible to `GET /search` and every SKU-keyed surface until the hold was lifted
        # and the run re-emitted. The owner's question, on being shown that: "Wait i want to
        # be able to find it, why can't it be emitted?" It can.
        #
        # IT ALSO FIXES AN OLDER INSTANCE OF THE SAME BUG. A `no_market_data` SKU answered
        # `"unlisted"` has never been stamped either, for this identical reason, since D9
        # gave that field its `unlisted` answer. Fixing only the withhold would have left
        # the same defect one door down.
        #
        # WHAT MUST NOT MOVE, and why this loop is worth reading twice: `pushed` is a
        # commitment that a CSV was written, `docs/GATES.md` records a real post-import
        # re-emit that double-counted staged copies, and `cli/resolve.py:_committed_keys`
        # reads `pushed + staged` back as `committed` — which is where this command's
        # idempotence actually lives. The bump below is gated on `emitted` and the stamp
        # above it is not.
        #
        # THE CAP BOUNDS THE LISTING, NOT THE IDENTITY, AND THIS LOOP READ IT AS BOTH.
        #
        # It iterated `live_positions` — `uncommitted_positions[:add_to_quantity]`, so
        # bounded by D7's THEN-STANDING `live_cap` of 4 — and did the identity write
        # inside it. That bound is retired (no standing cap since 2026-09-08) but the
        # defect it caused is the record here, so the figure stays named as it was at
        # the time. D7 caps
        # how many copies a SKU may have LIVE, on the envelope-buster and stale-price
        # arguments it gives; it says nothing about how many copies we know the name of.
        # Every copy past the fourth was left wearing `sku: null`, which is not backstock
        # in D7's sense (`backstock_positions` is a real answer this command already has)
        # but a copy that no SKU-keyed surface can see at all: `GET /search` misses it,
        # `copies_on_hand` misses it, and `positions_for_sku` cannot map it back.
        #
        # Measured on the owner's store: Rengar, Trophy Hunter (9189797, $30.81) holds
        # SEVEN copies at 3/1, 3/2, 3/4, 3/17, 3/20, 3/30 and 3/36. The first four carry
        # the SKU and the last three carry null, so a card the owner has seven of reported
        # four on hand — and the three invisible ones are the most valuable cards in the
        # box. It is the same split the paragraph above already drew for a withhold, at a
        # different seam: identity is known, and only the COUNT waits on a file.
        #
        # UNCOMMITTED AND NOT `positions`, WHICH IS THE ONE PLACE THIS COULD DESTROY DATA.
        # `match.positions` includes `committed_positions`, and `cli/resolve.py` commits a
        # copy on either of two grounds — a count read back off the `Listing`, or the copy
        # being in a TERMINAL state. So every sold and retired copy of a matched SKU is in
        # `positions`, and `set_state` has no terminal guard: it would move a sold card to
        # `identified`, wiping D10's permanent gap and D26's terminal state. Measured on
        # the owner's box-3 run, EIGHT of its 33 matched positions are sold today, so a
        # re-emit would have resurrected all eight. `uncommitted_positions` is the honest
        # set — every copy this run may still list, live and backstock together — and it
        # cannot contain a departed card by construction.
        #
        # Nothing is lost by excluding the committed ones: a copy committed by COUNT was
        # picked by `_committed_keys` out of `copies_on_hand`, which selects on `sku`, so
        # it is already stamped. A copy committed by having LEFT is not this command's to
        # relabel.
        copies = 0
        live_keys = {
            master.position_key(p.box, p.index) for p in match.live_positions
        }
        for position in match.uncommitted_positions:
            key = master.position_key(position.box, position.index)
            # Upsert first. A position the store has never seen — a run joined from a
            # recovered identifications file, say — would otherwise take a write that
            # lands nowhere and is still reported as having happened.
            writable.inventory.record_capture(
                master.Card(
                    box=position.box,
                    index=position.index,
                    cid=_name_for(key, resolved.photos.get(key)),
                    photo=resolved.photos.get(key),
                )
            )
            # `set_state(key, IDENTIFIED)` rather than assigning `sku` and `condition`
            # straight onto the record, and the choice is not style. It is the only
            # writer that returns False for a position with no record, which is what
            # keeps v1 bug #5 — a transition reported as having happened that did not —
            # out of this loop; and it is the only one that appends to `history.jsonl`,
            # so the moment this pipeline committed to a SKU for this copy survives in
            # the audit trail. `identified` is where the card already is and where it
            # stays: `pushed` is not a state a card can wear any more, and passing it
            # here now raises `UnknownState` rather than silently flagging a position.
            #
            # THE RETURN VALUE IS COUNTED ONLY FOR A COPY THAT REACHED THE FILE. The
            # stamp now runs over a wider set than the count does, so the two can no
            # longer share one increment: `pushed` is a commitment that a CSV row was
            # written, and a backstock copy has no row. Bumping it here would push the
            # count past `add_to_quantity` and double-stage on the next import, which is
            # the failure `docs/GATES.md` records from the first real post-import
            # re-emit. The membership test is what keeps the two apart, and it is on the
            # key rather than on the index because `live_positions` is a slice of the
            # same objects — identity would work and would break the day it is rebuilt.
            stamped = writable.inventory.set_state(
                key,
                master.IDENTIFIED,
                sku=match.sku,
                condition=match.condition,
                # D213: the catalogue
                # row this SKU resolved to is in hand right here, and this is the
                # moment it is committed to the card — the same moment `sku` and
                # `condition` always have been.
                set_name=match.set_name or None,
                rarity=match.rarity or None,
                # D253: the catalogue's own spelling, for the one
                # case `resolved.name_corrections` carries a position at all — a
                # near-miss read name, corrected at the same moment `set_name` and
                # `rarity` are. `None` on every other position, which leaves
                # `card.name` exactly as `record_identification` last wrote it.
                name=resolved.name_corrections.get(key),
                run=run_dir.name,
            )
            if stamped and key in live_keys:
                copies += 1
        if copies and match.sku in emitted:
            # Incremented, not set: two runs can push copies of one SKU, and the second
            # must not erase the first. Re-emitting the SAME run adds nothing because
            # `cli/resolve.py` reads these counts back as `committed`, so those copies
            # are no longer in `match.uncommitted_positions` at all — the idempotence
            # lives there rather than in a special case here, and it is untouched by the
            # stamp above: `_committed_keys` reads the `Listing`, never `card.sku`.
            writable.inventory.listing(
                match.sku, condition=match.condition
            ).bump(master.PUSHED, copies)
            pushed += copies
            pushed_skus += 1
            # THE PRICE THIS PRESS JUST PUT IN A FILE, RECORDED THE MOMENT THE PUSH IS
            # COUNTED — never a proposal, because this gate is the one that already
            # decides a row genuinely reached the file (D243). `emit`
            # tracks no prior asking price, so `replaced` is left unset rather than
            # guessed at.
            writable.postings.record(
                sku=match.sku,
                price=tcgcsv.format_price(priced_flat[match.sku]),
                source="emit",
                run=run_dir.name,
            )
    return pushed, pushed_skus


def _after_single(
    args, say, resolved, run_dir, listed_skus, sub_skus, pushed, pushed_skus, queue_line, stages,
    repriced=0,
) -> int:
    """What the single-run path says once its write has committed."""
    # ONLY WHEN SOMETHING REACHED A FILE. D54: the record is created by the first emit that
    # writes a row and is afterwards only ever added to. Writing it unconditionally is what
    # blanked it on every second press — and `reconcile` reads it, so a blank record made a
    # run that had emitted perfectly an hour ago refuse with "this run has emitted nothing".
    wrote_any = bool(listed_skus or sub_skus)
    if wrote_any:
        run_dir.record_emit(
            listed=listed_skus, sub_threshold=sub_skus, pushed=pushed
        )

    say("")
    say(f"pushed           {pushed} copy(ies) across {pushed_skus} SKU(s) -> "
        f"{master.PUSHED}")
    listings = ", ".join(f"{k} {v}" for k, v in stages.items() if v)
    if listings:
        say(f"listings         {listings}")
    # Restated here on purpose: this is the moment it is easiest to forget that cards are
    # still sitting in a box unlisted.
    say(f"standing queues  {queue_line}")
    say("")
    # NAMED OFF THE SHAPE THAT WAS ASKED FOR, because this line is an instruction. It told
    # the operator to import `import-listed.csv` whatever had been written, which is now
    # usually a file that does not exist.
    if args.split_threshold:
        listed_names = ", ".join(
            runs.import_listed_name(game) for game in resolved.joins
        ) or runs.IMPORT_LISTED
    elif args.split_games:
        listed_names = ", ".join(
            runs.import_merged_name(game) for game in resolved.joins
        ) or runs.IMPORT_MERGED
    else:
        listed_names = runs.IMPORT_MERGED
    if not wrote_any and repriced:
        # A FILE OF PRICE CHANGES ONLY: every row carries Add to Quantity 0, so no copy was
        # counted, and the file above is the one to send.
        say(f"price changes only — {repriced} card(s) already live, no copy added.")
        return 0
    if not wrote_any:
        # NOTHING NEW WENT ANYWHERE, AND SAYING SO IS THE POINT OF THIS BRANCH. Every copy
        # this run holds is already at `pushed`, so there is no row left to send and the
        # files on disk are the ones the first emit wrote. An operator who has just changed
        # `sub_threshold` or a price and pressed again is owed that sentence: the change
        # cannot reach TCGplayer through this run, because these copies have already been
        # sent under the old answer.
        sent = runs.open_run(run_dir.directory).emitted
        say("nothing new to send — every copy this run matched is already at "
            f"{master.PUSHED}.")
        if sent:
            say(f"      {listed_names} is unchanged, from the emit at {sent.get('at', 'an earlier run')}.")
            say("      A price changed after an emit cannot travel this road; the copies "
                "are already sent.")
            say(f"next: pkmnscan reconcile {run_dir.directory} <staged-export.csv>")
        return 0
    say(f"next: import {listed_names} to Staged in TCGplayer, "
        f"then Export From Staged and run")
    say(f"      pkmnscan reconcile {run_dir.directory} <staged-export.csv>")
    return 0


# ------------------------------------------------------------------- one file, several runs


def _legacy_refusal(run_dir, say) -> bool:
    """Refuse a run still carrying `decisions.json`, by name, before anything is read (D86).

    UNCONDITIONAL, AND THE SAME SENTENCE ON BOTH PATHS. The single-run guard used to fire only
    while the corpus was EMPTY, and the merged path had no guard at all — so on a store with
    answers in it, a legacy file was silently ignored by one and never seen by the other.
    """
    legacy = run_dir.path(runs.DECISIONS)
    if not legacy.is_file():
        return False
    say(f"{legacy} is a legacy pricing file; run `pkmnscan prices adopt --write` to fold "
        f"and retire it.")
    return True


def _resolve_one(run_dir, book, say, args):
    """One run resolved the way `run` resolves it, for the merged path. Returns None on refusal.

    `args` CARRIES THE SEND'S CAP AND NOTHING ELSE (D7, rewritten). A merged emit is ONE send,
    so the `--cap` on it applies to every leg — the alternative is legs capped differently
    inside one file, which is exactly the per-run-against-a-global-cap defect D86 measured.

    NO DEFAULT, DELIBERATELY. It was `args=None`, which read as "no cap" — so a caller that
    forgot the argument made one leg of a capped send uncapped, silently, with nothing raised
    and the file written. Harmless while `policy.live_cap` sat behind it and answered anyway;
    a hole once the flag became the only door. Required now, so the mistake is a TypeError at
    the call rather than a quantity in a spreadsheet.
    """
    if _legacy_refusal(run_dir, say):
        return None
    try:
        plan = resolve.exports_for(run_dir, None)
    except join.EmptyCatalog as refusal:
        say(f"{run_dir.name}: {refusal}")
        return None
    policy = book.policy_for(run_dir.name)
    try:
        return resolve.load(
            run_dir,
            plan.by_game,
            rule=pricing.Rule.parse(policy["rule"]),
            basis=pricing.check_basis(policy["basis"]),
            threshold=pricing.check_threshold(policy["threshold"]),
            # THE SEND'S OWN CAP, AND THE ONLY PLACE ONE IS NAMED (D7, amended 2026-09-08).
            # `--cap N` or nothing; the standing policy key that used to sit between them is
            # deleted, and a store still holding one is refused when the corpus is opened.
            live_cap=_cap_for(args),
            quantities=_quantities_for(args),
            review_below=run_dir.manifest.get("review_below_confidence", routing.CONFIDENCE_LOW),
        )
    except join.EmptyCatalog as refusal:
        say(f"{run_dir.name}: {refusal}")
        return None


def _bucket_files(game, group, split_threshold):
    """[(filename, rows)] for one game's slice of a merged plan.

    ONE FILE UNLESS `--split-threshold` IS ASKED FOR, which is the default this command
    exists to have. The pair it splits into is the pair the single-run path writes under the
    same flag, so an operator who wants the old shape gets the old NAMES too — a file called
    something else would not be the thing they asked for.

    `game` IS `None` WHEN THE GAMES ARE NOT BEING KEPT APART. The per-game name helpers take
    a game and answer the un-suffixed name for the default one, which is the right answer
    here as well: a file spanning every game in the send is the one `import-listed.csv`.
    """
    if not split_threshold:
        return [(runs.import_merged_name(game), group)]
    return [
        (
            runs.IMPORT_LISTED if game is None else runs.import_listed_name(game),
            [row for row in group if not row.sub_threshold],
        ),
        (
            runs.IMPORT_SUBTHRESHOLD
            if game is None
            else runs.import_subthreshold_name(game),
            [row for row in group if row.sub_threshold],
        ),
    ]


def run_merged(args, say) -> int:
    """`pkmnscan emit <run> <run> ...` — one import file over several runs (D86).

    THE DEDUPE IS WHY THIS IS NOT A CONCATENATION OF THE FILES `emit` ALREADY WROTE, and the
    cap was the other half until the standing one went (D7, amended 2026-09-08). A card in
    three boxes is ONE row because the union of positions is deduped on `(box, index)`,
    which holds whether or not this send asked for a cap. When it does ask, the figure is
    still spent once across the send rather than once per leg — which is D86's measurement
    and the reason `--cap` reaches every leg through one `_cap_for`.
    `pipeline/join.py:SkuMatch.add_to_quantity` spends `live_cap - copies_out` per RUN against a
    cap that is global, so runs joined before either emitted each believe the whole cap is
    theirs. Measured on this store: five SKUs' per-run claims summed past four, and two reached
    `pushed: 6` against a cap of 4. `pipeline/merge.py` re-derives the figure over the union;
    this command writes the file and the store.

    IT REFUSES EXACTLY WHAT THE SINGLE-RUN PATH REFUSES, per run, before anything is written —
    an unresolved queue, an unanswered no-market-data card, a sub-threshold bucket with no
    disposition. What it adds is one refusal of its own: two runs carrying different per-run
    policy overrides, which one file cannot honour.
    """
    # BEFORE ANY RUN IS RESOLVED, which is what makes it the plan's basis (`_listing_basis`).
    basis = _listing_basis()
    book = corpus.Corpus.read()
    # OLDEST FIRST, WHICH DECIDES WHICH COPIES GO. Run names are date-prefixed, so this is
    # chronological; `merge.plan` slices the cap off the front of the union, so the copies that
    # reach the file are the ones that have been waiting longest.
    dirs = [runs.open_run(path) for path in args.run_dir]
    dirs.sort(key=lambda d: d.name)
    if len({d.name for d in dirs}) != len(dirs):
        say("the same run was named twice")
        return 1

    resolved_by_run: "OrderedDict[str, object]" = OrderedDict()
    policies = {}
    matched = set()
    for run_dir in dirs:
        resolved = _resolve_one(run_dir, book, say, args)
        if resolved is None:
            say("REFUSING to write. Nothing was written.")
            return 1
        resolved_by_run[run_dir.name] = resolved
        policies[run_dir.name] = book.policy_for(run_dir.name)
        matched |= set(resolved.matches)
        for game_join in resolved.joins.values():
            if not game_join.report.ok:
                say(f"{run_dir.name}: output suppressed; unmatched must be reported first")
                for reason in game_join.report.blocking_reasons:
                    say(f"  - {reason}")
                say("REFUSING to write. Nothing was written.")
                return 1

    # THE DOUBLE-SEND GUARD, OVER THE UNION OF EVERY LEG (`_apply_guard` says why the union).
    # Applied to the legs BEFORE `merge.plan`, which takes the tightest `asked` any leg names.
    legs_by_sku: "OrderedDict[str, list]" = OrderedDict()
    for resolved in resolved_by_run.values():
        for sku, match in resolved.matches.items():
            legs_by_sku.setdefault(sku, []).append(match)
    try:
        guarded = _apply_guard(
            _live_guard(args), legs_by_sku, Store().read().inventory
        )
    except GuardRefused as refusal:
        say(f"REFUSING to write: {refusal}. Nothing was written.")
        return 1

    choice = book.scoped_to(matched)
    say(f"send             {len(dirs)} run(s): {', '.join(d.name for d in dirs)}")
    say(f"prices           {files.prices_path()}")
    say(f"                 {choice.describe}")

    try:
        merged_plan = merge.plan(resolved_by_run, choice, policies)
    except (merge.Disagreement, join.Undecided, join.OutputSuppressed) as refusal:
        say(str(refusal))
        say("REFUSING to write. Nothing was written.")
        return 1

    # NAMED BEFORE THE EMPTY CHECK BELOW, so a send the guard trimmed to nothing still says
    # which cards TCGplayer already holds. `room` ignores `asked`, so this is the unguarded
    # figure over the merged union.
    typed = _quantities_for(args)
    _say_guard(
        guarded,
        {row.sku: _would(row.match, typed) for row in merged_plan.skus},
        {row.sku: row.match.name for row in merged_plan.skus},
        say,
    )

    rows = merged_plan.rows(listed_only=args.listed_only)
    # THE PRICE-ONLY ROWS OVER THE MERGED PLAN (the owner's ruling, 2026-09-24). Each is the
    # plan's own row with `add_to_quantity` 0, so `merge.import_rows` writes it as Add to
    # Quantity 0 at the plan's price, with no second code path.
    try:
        changes = _price_changes(
            args,
            guarded,
            {
                row.sku: (row.match.name, row.price)
                for row in merged_plan.skus
                if row.match.add_to_quantity == 0
            },
            _typed_skus(choice),
        )
    except PriceRefused as refusal:
        say(f"REFUSING to write: {refusal}. Nothing was written.")
        return 1
    changes = _keep_listed(
        changes, {row.sku for row in merged_plan.skus if row.sub_threshold}, args, say
    )
    changed = {change.sku for change in changes}
    rows = rows + [row for row in merged_plan.skus if row.sku in changed]
    if not rows:
        say("nothing to write — every matched SKU is held back, unlisted, or has no room")
        for sku, why in list(merged_plan.dropped.items())[:8]:
            say(f"  {sku} — {why}")
        return 1

    # A SKU THAT ADDS NOTHING IS NAMED WHETHER OR NOT ANYTHING ELSE WRITES, which the branch
    # above did only in the total case. `MergedSku.rows()` filters `add_to_quantity == 0` out
    # of the file, so before this a PARTIAL send — ten SKUs going, forty adding nothing —
    # wrote the file, reported `import  10 row(s)` and named the forty NOWHERE. That is the
    # silent drop `CLAUDE.md` forbids by name, reached by the ordinary press.
    #
    # THE SINGLE-RUN PATH ALREADY DID THIS and the two had simply diverged: `no room` above
    # walks `report.at_cap` and prints `match.nothing_to_add` per SKU. This is that block over
    # the merged plan, reading the same property off the merged match so the two answers
    # cannot differ.
    silent = [row for row in merged_plan.skus if row.match.add_to_quantity == 0]
    if silent:
        say("")
        say(f"{'no room':<16} {len(silent)} SKU(s) matched and added nothing")
        for row in silent[:8]:
            say(f"{'':<16} {row.sku} — {row.match.nothing_to_add}")
        if len(silent) > 8:
            say(f"{'':<16} ...and {len(silent) - 8} more")

    corrected = [row for row in merged_plan.skus if row.over_cap]
    if corrected:
        # NAMED AND NOT COUNTED (D59). A row whose per-run claims summed past the cap is a row
        # a concatenation would have over-listed, and the operator is entitled to know which.
        say("")
        say(f"cap              {len(corrected)} SKU(s) the runs separately over-claimed:")
        for row in corrected[:8]:
            say(f"  {row.sku} {row.match.name} — runs claim {row.claimed}, "
                f"{row.match.add_to_quantity} can go")
    # THE SEND'S OWN QUANTITIES, READ OFF THE MERGED MATCH so the figure named is the one
    # spent across the union and not any one leg's (D7, amended 2026-09-11).
    _say_quantities(
        _quantities_for(args), {row.sku: row.match for row in merged_plan.skus}, say
    )
    _say_prices(changes, args, say)

    by_game = {None: rows}
    if args.split_games:
        by_game = OrderedDict(
            (game, [row for row in rows if row.game == game])
            for game in merge.games_in(rows)
        )

    # THE HEADER IS THE CATALOG'S, AND A MERGED FILE NEEDS ONE. Every game's export is read
    # into a catalog carrying its own column list; TCGplayer's format is fixed in practice, so
    # they agree — but a file whose rows came from two different headers is malformed in a way
    # no reader here would notice, so it is checked rather than assumed. The newest run that
    # holds a game is where that game's header comes from, for `_merged_match`'s reason.
    catalogs = {}
    for name in resolved_by_run:
        for game, game_join in resolved_by_run[name].joins.items():
            catalogs[game] = game_join.catalog

    say("")
    written = []
    for game, group in by_game.items():
        if not group:
            continue
        games = merge.games_in(group)
        headers = {tuple(catalogs[one].header) for one in games if one in catalogs}
        if len(headers) > 1:
            say("REFUSING: these games' exports carry different columns, and one file needs")
            say(f"one header. Re-run with --split-games. ({', '.join(games)})")
            return 1
        catalog = catalogs[games[0]]
        # THE SPLIT IS OVER THE ONE PLAN AND NEVER A SECOND ONE. `merged_plan` spent the cap
        # over the union of positions once; filing the rows into two files after the fact
        # cannot change a quantity, which is exactly why the split is applied HERE and not by
        # planning the two buckets separately.
        for name, bucket in _bucket_files(game, group, args.split_threshold):
            if not bucket:
                # D54's EMPTY GUARD, WHICH THE MERGED PATH NEEDS THE MOMENT IT CAN SPLIT. A
                # send whose every row is above the threshold would otherwise write a
                # header-only `import-subthreshold.csv` over an earlier good one.
                continue
            target = _out(dirs[-1], name, args)
            csv_rows = merge.import_rows(bucket)
            try:
                # `write_import` OWNS THE DUPLICATE-SKU GATE, and it is reused rather than
                # restated. `merge.plan` is keyed by SKU so two rows with one `TCGplayer Id`
                # cannot be built here — and a property nothing checks is a comment, which is
                # exactly what that function exists to stop this file from writing.
                join.write_import(catalog, target, csv_rows)
            except join.OutputSuppressed as refusal:
                say(f"REFUSING: {refusal}. Nothing more was written.")
                return 1
            copies = sum(row.match.add_to_quantity for row in bucket)
            say(f"import           {len(csv_rows)} row(s), {copies} card(s) -> {target}")
            written.append((target, bucket))

    # --------------------------------------------------------------------- the store
    #
    # ONE PASS OVER THE MERGED PLAN, AND THE COPY BELONGS TO THE RUN THAT HOLDS IT. Every
    # position is in exactly one run, so `set_state` still stamps the run it came from — the
    # audit trail is unchanged. What is merged is the DECISION about which copies reach the
    # file: `live_keys` is sliced once over the union, so two runs cannot both count the same
    # room toward `pushed`.
    pushed = 0
    pushed_skus = 0
    # A PRICE-ONLY ROW IS NOT SHIPPED: it adds no copy, so it stamps no copy and raises no
    # count. Its posting is `_record_prices`, below.
    shipped = {row.sku for _, group in written for row in group} - changed
    going = {
        row.sku: int(row.match.add_to_quantity)
        for row in merged_plan.skus
        if row.sku in shipped and row.match.add_to_quantity > 0
    }
    store = Store()
    try:
        with store.write() as writable:
            _claim_or_refuse(writable, going, basis, args, sorted(changed))
            pushed, pushed_skus = _stamp_merged(writable, merged_plan, shipped, resolved_by_run)
            _record_prices(writable, changes, ",".join(d.name for d in dirs))
            queue_line = writable.queue_summary
            stages = writable.inventory.listing_counts()
    except SendClaimRefused as refusal:
        _say_claim_refusal(refusal, args, say)
        return 1
    # THE RUN'S EMIT RECORD NAMES THE SKUS THAT ADDED A COPY (D54), never a price-only row.
    copied = [(target, [row for row in group if row.sku not in changed]) for target, group in written]
    return _after_merged(dirs, copied, pushed, pushed_skus, queue_line, stages, say)


def _stamp_merged(writable, merged_plan, shipped, resolved_by_run):
    """The merged write: stamp every copy once, count the sent ones. `(pushed, skus)`."""
    pushed = 0
    pushed_skus = 0
    for row in merged_plan.skus:
        if row.sku not in shipped:
            continue
        live_keys = merged_plan.live_keys.get(row.sku, set())
        copies = 0
        # ONE PASS PER POSITION, NOT PER LEG, AND THE DEDUPE IS THE COUNT. Box 3 has been
        # joined three times on this machine, so its cards are in three of this send's
        # runs and every one of them carries the same `(box, index)`. Walking the legs
        # naively stamped each copy once per leg and counted it toward `pushed` each time
        # — measured against a cleared ledger, that pushed 11 SKUs past the cap of 4 where
        # three separate emits pushed 2. The merged path was WORSE than the thing it
        # exists to fix, which is what a head-to-head against the old path is for.
        #
        # THE FIRST LEG HOLDING A COPY OWNS IT, and legs are in run order, so the stamp
        # names the oldest run that could have listed it — the same first-come rule
        # `merge.plan` spends the cap by.
        owner = {}
        for leg in row.legs:
            for position in leg.match.uncommitted_positions:
                key = master.position_key(position.box, position.index)
                owner.setdefault(key, (leg.run, position))
        for key, (run_name, position) in owner.items():
            writable.inventory.record_capture(
                master.Card(
                    box=position.box,
                    index=position.index,
                    cid=_name_for(key, resolved_by_run[run_name].photos.get(key)),
                    photo=resolved_by_run[run_name].photos.get(key),
                )
            )
            stamped = writable.inventory.set_state(
                key,
                master.IDENTIFIED,
                sku=row.sku,
                condition=row.match.condition,
                set_name=row.match.set_name or None,
                rarity=row.match.rarity or None,
                # D253, read off THIS LEG'S OWN run — the run that
                # owns this position (`owner` above) is the one whose join computed
                # the correction, exactly as `set_name`/`rarity` read `row.match`
                # rather than some other leg's.
                name=resolved_by_run[run_name].name_corrections.get(key),
                run=run_name,
            )
            if stamped and key in live_keys:
                copies += 1
        if copies:
            writable.inventory.listing(row.sku, condition=row.match.condition).bump(
                master.PUSHED, copies
            )
            pushed += copies
            pushed_skus += 1
            # THE MERGED PLAN'S OWN PRICE, THE SAME `row.price` `merge.import_rows` WROTE
            # INTO THE CSV CELL — never recomputed (D243). `run` names
            # every run that contributed a leg to this SKU, since a merged send has no
            # single run of its own.
            writable.postings.record(
                sku=row.sku,
                price=tcgcsv.format_price(row.price),
                source="emit-merged",
                run=",".join(sorted({leg.run for leg in row.legs})),
            )
    return pushed, pushed_skus


def _after_merged(dirs, written, pushed, pushed_skus, queue_line, stages, say) -> int:
    """What the merged path says once its write has committed."""
    # THE RECEIPT IS PER RUN AND ADDS, NEVER SUBTRACTS (D54). Each run in the send records the
    # SKUs it contributed, so `reconcile` on any of them still knows what it sent.
    for run_dir in dirs:
        own = sorted(
            row.sku
            for _, group in written
            for row in group
            if any(leg.run == run_dir.name for leg in row.legs)
        )
        if own:
            run_dir.record_emit(listed=own, sub_threshold=[], pushed=pushed)

    say("")
    say(f"pushed           {pushed} copy(ies) across {pushed_skus} SKU(s) -> {master.PUSHED}")
    listings = ", ".join(f"{k} {v}" for k, v in stages.items() if v)
    if listings:
        say(f"listings         {listings}")
    say(f"standing queues  {queue_line}")
    say("")
    say("next: import the file above to Staged in TCGplayer, then Export From Staged and run")
    say(f"      pkmnscan reconcile {dirs[-1].path('')} <staged-export.csv>")
    return 0
