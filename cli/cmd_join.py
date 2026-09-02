"""`pkmnscan join <run-dir>` — resolve identifications against the export. Free.

Free and re-runnable, which is what makes the rest of the design affordable: clear a review,
refresh the export, change the rule, run it again. Nothing here spends money and nothing here
writes an import file.

WHAT IT PRODUCES. The report, in both directions and in full. The standing queues, updated
with every card that did not list. And `decisions.json`, pre-filled with every SKU that needs
an answer and the run-wide choice left UNSET — `emit` refuses until you set it.

REVIEWS DO NOT BLOCK. An unresolved card sits at a known position in a box: it is not lost
and it is not urgent, and holding 400 good cards hostage to 7 ambiguous ones is the wrong
trade (v2 §5.6). What the hard rule actually demands is that unmatched be reported in both
directions BEFORE any output exists, and that is exactly the order here — this command
reports and queues, and `emit` is a separate command that runs afterwards.

THE EXPORT'S AGE IS A WARNING, NEVER A REFUSAL. A stale export is a judgment call, and a
hard stop on a snapshot's age would block a legitimate run for a reason already on screen.
"""

from __future__ import annotations

import json
from collections import Counter

from cli import resolve, runs
from pipeline import corpus, decisions, join, pricing, routing, tcgcsv
from store import master, queues
from store import files
from store.session import Store

STALE_EXPORT_DAYS = 7


def _reason_counts(resolved: resolve.Resolved) -> Counter:
    """What this run would put in the standing queues, counted by reason code.

    Read off `entries_for` rather than off the reports directly, so the preview counts the
    entries that would actually be WRITTEN — pre-join failures included. A preview built
    from a different source than the write is a preview that can be wrong in the one way
    that matters.

    Raw reason strings, never a friendly gloss. `app/src/ReviewQueue.tsx` carries the only
    label table in the product and says in its own comment that nothing keeps it in step
    with the Python constants; a second table here would be a third vocabulary with even
    less holding it together, which is exactly the drift D16 exists to catch.
    """
    main, parked = resolve.entries_for(resolved)
    return Counter(entry.reason for entry in main + parked)


def _counts_block(say, counts: Counter, indent: str = "                   ") -> None:
    for reason, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        say(f"{indent}{reason:<34} {count}")


# The three presets the pricing screen offers, priced HERE so `pipeline/pricing.py` runs
# once and in Python (D49). The owner picked these three and their numbers in an interview:
# match market, undercut market by 5, undercut TCG Low by 1. A fourth is a change to this
# tuple and to `app/src/Pricing.tsx`'s labels, and to nothing else.
#
# THE CLIENT PERFORMS NO ARITHMETIC ON MONEY, WHICH IS WHAT THIS TUPLE BUYS. Re-implementing
# `Rule.apply` + `round_money` + `clamp_floor` in TypeScript would put `pricing.py`'s
# rounding-before-clamping order in two languages with nothing auditing the second, and that
# order is the whole reason `list_price` is a function rather than an expression.
PRESETS = (
    ("market_match", pricing.RULE_MATCH, pricing.BASIS_MARKET),
    ("market_undercut_5", "undercut:5", pricing.BASIS_MARKET),
    ("low_undercut_1", "undercut:1", pricing.BASIS_LOW),
)


def _cell(row, column):
    """One export cell as a rendered price, or `None` where it is blank.

    Rendered through `tcgcsv.format_price` rather than passed raw, because three of the four
    price columns are FOUR-decimal in every populated cell and two are two — so a screen
    drawing them side by side without this reads `$0.0100` beside `$0.07` and loses the
    decimal column. The raw string travels too (`row`), so nothing is lost.
    """
    value = tcgcsv.parse_price(row.get(column, ""))
    return None if value is None else tcgcsv.format_price(value)


def _preset_prices(match):
    """What each named preset would list this SKU at, or `None` where it cannot price it.

    `None` IS A REAL ANSWER AND NOT AN ERROR. Measured on the wide Pokemon export, 394 of
    2,476 listable rows carry a blank `TCG Low Price`, so a Low-based preset genuinely has
    nothing to price them from — and `SkuMatch.list_price` returns `None` there, which
    `tcgcsv.set_writable` would turn into an import row carrying a quantity and no price.
    The screen prices what it can, leaves the rest, and says which (the owner's ruling).
    """
    out = {}
    for name, rule, basis in PRESETS:
        basis_price = tcgcsv.parse_price(
            match.row.get(
                tcgcsv.MARKET_PRICE_COLUMN
                if basis == pricing.BASIS_MARKET
                else tcgcsv.LOW_PRICE_COLUMN,
                "",
            )
        )
        out[name] = (
            None
            if basis_price is None or basis_price <= 0
            else str(pricing.list_price(basis_price, rule=pricing.Rule.parse(rule)))
        )
    return out


def _pricing_table(run_dir, resolved, choice, snapshot):
    """`pricing.json` — every SKU this run matched, with everything needed to price it.

    WRITTEN BY `join` AND BY NOTHING ELSE, from the values it has already computed. The
    alternative was a server route that re-ran `resolve.load` per request, which re-parses
    the export, re-reads the store and SHA-256s every photograph in the box (D36) — seconds
    per call, for a screen that polls nothing but is opened repeatedly.

    IT IS DATA BECAUSE A SCREEN READS IT. `report.txt` beside it is prose written for a
    person and cannot be parsed back without inventing a format nothing owns; this file
    carries each export row VERBATIM under `row`, so the screen shows what the CSV says
    rather than what an intermediate layer decided the CSV meant.
    """
    skus = []
    for game_join in resolved.joins.values():
        report = game_join.report
        below = set(report.below_threshold.skus)
        unpriced = {m.sku for m in report.no_market_data}
        listing_of = snapshot.inventory.listings
        for match in report.matches.values():
            record = listing_of.get(match.sku)
            skus.append(
                {
                    "sku": match.sku,
                    "game": game_join.game,
                    # VERBATIM, every cell, unmodified. D49's whole premise is the owner's
                    # "I want all the data from the CSV shown when I make the decision".
                    "row": dict(match.row),
                    "bucket": (
                        "no_market_data"
                        if match.sku in unpriced
                        else "sub_threshold"
                        if match.sku in below
                        else "listable"
                    ),
                    "copies": match.copies,
                    "add_to_quantity": match.add_to_quantity,
                    "backstock": match.backstock,
                    "live_before": match.live_before,
                    "committed": len(match.committed_positions),
                    # WHAT TCGPLAYER ACTUALLY HOLDS, AND WHY `live_before` BESIDE IT IS NOT
                    # THAT NUMBER. `live_before` is the export's live column alone, which
                    # reads 0 for every copy sitting on an import nobody has reconciled —
                    # measured at 167 pushed copies across 72 SKUs of the owner's store,
                    # zero of them live, so a screen drawing it said TCGplayer holds
                    # nothing about SKUs it holds several of. `copies_out` is live plus
                    # pending, per SKU and across every box. Both ship: the screen names
                    # the export's own figure where it means the export, and this one
                    # where it means the shelf (D59).
                    "copies_out": match.copies_out,
                    "at_cap": match.add_to_quantity == 0,
                    # The SENTENCE, composed where the numbers are, never re-derived from
                    # the three fields above. `at_cap` says a row was not written and
                    # cannot say why — at the cap, or held out by an unreconciled push, or
                    # every copy in this run already gone. A screen reassembling that from
                    # parts is a second copy of `SkuMatch.nothing_to_add`'s reasoning with
                    # nothing auditing the two against each other.
                    "nothing_to_add": match.nothing_to_add,
                    "condition": match.condition,
                    "set_name": match.set_name,
                    "name": match.name,
                    "snap": {
                        "market": _cell(match.row, tcgcsv.MARKET_PRICE_COLUMN),
                        "direct_low": _cell(match.row, tcgcsv.DIRECT_LOW_COLUMN),
                        "low": _cell(match.row, tcgcsv.LOW_PRICE_COLUMN),
                        "low_with_shipping": _cell(
                            match.row, tcgcsv.LOW_WITH_SHIPPING_COLUMN
                        ),
                        "now": _cell(match.row, tcgcsv.PRICE_COLUMN),
                    },
                    "presets": _preset_prices(match),
                    "rule_price": (
                        None if match.list_price is None else str(match.list_price)
                    ),
                    # The first copy in box-walk order and how many there are — the
                    # representative photograph, named rather than picked silently, and
                    # steppable on the screen. `positions` is already sorted.
                    "positions": [
                        {"box": pos.box, "index": pos.index, "label": pos.label}
                        for pos in match.positions
                    ],
                    "listing": (
                        None
                        if record is None
                        else {
                            "pushed": record.pushed,
                            "staged": record.staged,
                            "live": record.live,
                        }
                    ),
                }
            )

    # Market descending, and `None` last. The sort is the hierarchy on the screen — there are
    # no price type-size bands, because `ReviewQueue.css`'s own comment calls its breakpoints
    # a guess and docs/DESIGN.md records them as drawing a sort that queue only partly has.
    skus.sort(
        key=lambda s: (
            s["snap"]["market"] is None,
            -float(s["snap"]["market"] or 0),
            s["sku"],
        )
    )

    bands = []
    for game_join in resolved.joins.values():
        for band in game_join.report.below_threshold.bands():
            bands.append(
                {
                    "game": game_join.game,
                    "label": f"${band.lower}-${band.upper}",
                    "skus": len(band.matches),
                    "copies": band.copies,
                }
            )

    return {
        "run": run_dir.name,
        "threshold": str(pricing.THRESHOLD),
        "floor": str(pricing.FLOOR),
        "rule": str(choice.rule),
        "basis": choice.basis,
        "presets": [name for name, _, _ in PRESETS],
        "games": [
            {
                "game": g.game,
                "import_listed": runs.import_listed_name(g.game),
                "import_subthreshold": runs.import_subthreshold_name(g.game),
            }
            for g in resolved.joins.values()
        ],
        "skus": skus,
        "bands": bands,
    }


def _preview(args, run_dir, plan, resolved, say) -> int:
    """`--dry-run`: everything the join would compute, and nothing it would write.

    ONE walk of the ladder, counted by reason code off the same function the write reads.
    It walked twice until 2026-09-02 — once with the finish cross-check and once without,
    diffing the two queues so the operator could see what `--bypass` would buy — and the
    second walk went with the cross-check it was measuring (D3, amended). What is left is
    the preview: the queue this join would write, before it writes it.
    """
    mine = _reason_counts(resolved)
    say("")
    say(f"DRY RUN          nothing written — no queues, no {runs.DECISIONS}, no "
        f"{runs.REPORT}, no manifest")
    say(f"would queue      {sum(mine.values())} card(s)")
    _counts_block(say, mine)
    say("")
    say(f"next: pkmnscan join {run_dir.directory} --export <file>  (to write it)")
    return 0


def run(args, say) -> int:
    run_dir = runs.open_run(args.run_dir)
    # The file->game mapping, read off each file's own Product Line cells, and every
    # refusal it can raise — two files claiming one game, a game in the run with no
    # export, a file naming no registered game — fires HERE, before the store is opened,
    # before any catalog is built, before anything is written or queued.
    try:
        plan = resolve.exports_for(run_dir, args.export)
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    store = Store()
    snapshot = store.read()

    # The queue totals LEAD the report — you see them while choosing what to work on.
    say("")
    say(f"standing queues  {snapshot.queue_summary}")

    # `staged_stale` reads LISTINGS now, not positions (D7 amended): staged is a quantity of
    # a SKU rather than a state a card wears, so what has gone stale is the SKU's import and
    # not any one copy. The line names the SKU and how many copies of it are sitting there,
    # because that is what you would go and finish in TCGplayer — a position label would send
    # you to a box, which is the one place the problem is not.
    stale = snapshot.inventory.staged_stale()
    if stale:
        say(
            f"staged >{master.STAGED_STALE_DAYS} days  {len(stale)} SKU(s) staged and never "
            f"moved live: " + ", ".join(f"{e.sku} x{e.staged}" for e in stale[:8])
        )

    try:
        resolved = resolve.load(
            run_dir,
            plan.by_game,
            rule=args.rule,
            basis=args.basis,
            review_below=args.review_below_confidence,
        )
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    # One export/catalog block per game. A one-game run prints exactly the block it
    # always did; a multi-game run names the game on each line, because two files with
    # two ages and two collision counts under one unlabelled heading is a report that
    # cannot be read back.
    multi = len(resolved.joins) > 1
    say("")
    for game_join in resolved.joins.values():
        source = game_join.source
        prefix = f"{game_join.game}: " if multi else ""
        say(f"export           {prefix}{source['path']}")
        say(f"                 {source['mtime']} ({source['age_days']} days old), "
            f"sha256 {source['sha256'][:12]}")
        if source["age_days"] >= STALE_EXPORT_DAYS:
            say(f"                 WARNING: {source['age_days']} days old. Prices and "
                f"quantities move. Warning only — this run is not blocked.")
        catalog = game_join.catalog
        dropped = (
            f", {catalog.dropped_rows} row(s) of other product lines dropped"
            if catalog.dropped_rows
            else ""
        )
        say(f"catalog          {prefix}{len(game_join.export.rows)} rows, "
            f"{len(catalog.set_names)} set(s), "
            f"{len(catalog.colliding_keys)} colliding key(s){dropped}")
        if catalog.colliding_keys:
            for key in catalog.colliding_keys[:8]:
                say(f"                   {key} -> {', '.join(catalog.sets_for_key(key))}")
    for note in plan.notes:
        say(f"                 {note}")
    say(f"pricing          rule={resolved.rule} basis={resolved.basis} "
        f"review-below-confidence={args.review_below_confidence}")
    say("")

    # ------------------------------------------------- the report itself, game by game
    sections = []
    for game_join in resolved.joins.values():
        text = game_join.report.report()
        sections.append(f"[{game_join.game}]\n{text}" if multi else text)
    report_text = "\n\n".join(sections)
    for line in report_text.splitlines():
        say(line)

    # D36 — said before the report rather than after it, because it changes what every
    # position in that report MEANS. A correction the operator learns about afterwards is one
    # they have already read a run report without.
    if resolved.realigned:
        say("")
        say(
            f"slots realigned: {len(resolved.realigned)} card(s) matched to the slot their "
            f"photograph is in NOW, not the slot they were identified at."
        )
        say(
            "    A card was deleted from the middle of this box since it was identified, so "
            "everything after it slid down one (D10). Matched by photograph, never guessed."
        )
        for old_key, new_key in sorted(
            resolved.realigned.items(), key=lambda kv: int(kv[0].split("/")[1])
        )[:5]:
            say(f"    {old_key} -> {new_key}")
        if len(resolved.realigned) > 5:
            say(f"    ... and {len(resolved.realigned) - 5} more")
        say("")

    # Named rather than dropped in silence — `CLAUDE.md`'s rule is that a card may leave the
    # pipeline unlisted, never unrecorded, and a card that has left the BOX is the one case
    # where there is no queue to record it into.
    if resolved.departed:
        say(
            f"skipped: {len(resolved.departed)} card(s) in this run are no longer in the box "
            f"— deleted mid-box or retired since it was identified."
        )
        for key in resolved.departed[:5]:
            say(f"    {key} (identified here, photograph is gone)")
        if len(resolved.departed) > 5:
            say(f"    ... and {len(resolved.departed) - 5} more")
        say("")

    # An unchecked box must not read as a verified one.
    if resolved.unverified_boxes:
        boxes = ", ".join(str(b) for b in resolved.unverified_boxes)
        say(
            f"slots NOT verified for box {boxes}: nothing on disk to check them against — "
            f"no photographs, no record carrying a digest, or none of this run's digests "
            f"among the photographs there (a re-shoot replaces the bytes). This run's slot "
            f"numbers were taken as recorded. If a card was deleted mid-box since it was "
            f"identified, they are wrong and nothing here can tell."
        )
        say("")

    if resolved.failures:
        say(f"pre-join failures (-> main queue): {len(resolved.failures)}")
        for failure in resolved.failures:
            say(f"    {failure.describe}")

    # ------------------------------------------------------------------------ dry run
    # BEFORE the first write and after the whole report, which is the only ordering that
    # makes this useful: a preview that skipped the report would preview nothing, and one
    # that ran after the queues were written would not be a preview.
    if args.dry_run:
        return _preview(args, run_dir, plan, resolved, say)

    # --------------------------------------------------------------- write the queues
    main, parked = resolve.entries_for(resolved)
    # A card this run resolved leaves whichever queue it was sitting in. Scoped to the
    # positions this run actually processed, so joining box 3 cannot evict box 7's entries.
    freed = resolved.processed_positions - resolved.queued_positions
    with store.write() as writable:
        # Upsert and release as one unit — `queues.apply_run` also releases the entry a
        # re-routed position leaves behind in the OTHER queue, which the two independent
        # release calls that used to sit here could not see. Found by a real run: 16
        # positions moved review -> parked and every stale review entry survived.
        added_main, added_parked, released = queues.apply_run(
            writable.review, writable.parked, main, parked, freed
        )

        # `live` is refreshed here and costs nothing new: the export's `Total Quantity` is
        # already read for D7's refill math (`SkuMatch.live_before`). A SKU that now shows
        # quantity against it on TCGplayer has been moved live by a human, and nothing else
        # in this pipeline would ever notice.
        #
        # IT IS SET, NOT INCREMENTED, AND IT IS SET FROM THE EXPORT. D8 and D11 put the
        # authority in the export, so the stored number is the optimistic local estimate
        # `master.Listing` describes and this is the line that corrects it. A count that
        # walked up on its own would be a second source of truth competing with the file
        # the whole join is built on.
        #
        # This block used to choose WHICH positions went live — the first `live_before`
        # copies in box-walk order took a `live` state and the rest stayed `staged`. That
        # made listing progress an address for no physical reason (the owner's ruling is
        # that copies of one SKU are fungible), and it could not represent the ordinary
        # case of a SKU showing more live quantity than this pipeline ever pushed.
        moved_live = []
        for match in resolved.matches.values():
            quantity = max(0, int(match.live_before))
            # Peeked rather than got-or-created: `Inventory.listing` creates on read, and
            # calling it for every matched SKU would fill the file with empty records whose
            # only content is that the SKU exists — which the export already says, better.
            if writable.inventory.listings.get(match.sku) is None and quantity == 0:
                continue
            listing = writable.inventory.listing(match.sku, condition=match.condition)
            before = listing.live
            if quantity == before:
                continue
            listing.live = quantity
            listing.at = master.now()
            moved_live.append((match.sku, before, quantity))

            # Copies that just went live are no longer staged. `reconcile` is the only thing
            # that puts a copy in `staged` and nothing else would ever take it out, so
            # without this drawdown `staged_stale` names every SKU that has ever staged,
            # forever — a warning that fires on success is a warning nobody reads.
            #
            # Drawn down by the RISE in live quantity, never by the absolute reading. The
            # absolute number would also erase copies staged since the last join, which are
            # exactly the copies the stale warning exists to find.
            newly_live = quantity - before
            if newly_live > 0 and listing.staged > 0:
                listing.bump(master.STAGED, -min(listing.staged, newly_live))

        queue_line = writable.queue_summary
        counts = writable.inventory.counts()
        stages = writable.inventory.listing_counts()

    say("")
    say(f"queued           +{added_main} main, +{added_parked} parked, "
        f"-{len(released)} resolved and released")
    say(f"standing queues  {queue_line}")
    if moved_live:
        rose = sum(after - before for _, before, after in moved_live if after > before)
        fell = sum(before - after for _, before, after in moved_live if after < before)
        say(f"live             {len(moved_live)} SKU(s) moved, +{rose}/-{fell} cop(ies), "
            f"read from the export")
        for sku, before, after in moved_live[:8]:
            say(f"                   {sku}  {before} -> {after}")
    held = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
    if held:
        say(f"inventory        {held}")
    # The three TCGplayer stages used to appear on the line above, because a card wore one
    # of them as its state. They are quantities of a SKU now, so they are counted separately
    # — reporting only `counts()` would have quietly deleted them from every run report.
    listed = ", ".join(f"{k} {v}" for k, v in stages.items() if v)
    if listed:
        say(f"listings         {listed}")

    # ----------------------------------------------------------- the pricing corpus (D86)
    #
    # THE ANSWER LIVES IN ONE FILE FOR THE WHOLE STORE, AND THIS COMMAND NO LONGER WRITES A
    # PER-RUN ONE. `runs/<n>/decisions.json` held two different kinds of fact — a lot's policy
    # and a CARD's answer — and only the first is a property of the drawer. The second is a
    # property of the SKU, which is why the same card carried one answer per box it had ever
    # been photographed in: 66 SKUs, 8 of them answered twice, 3 of those a hold overridden by
    # a later price. See `pipeline/corpus.py` and D86.
    #
    # A RUN FILE THAT STILL EXISTS IS LEGACY AND IS NOT READ. `pkmnscan prices adopt` folds it
    # in, once, with a report of every answer it had to choose between. Reading it here as a
    # fallback would put the duplication back the moment somebody re-joined an old run.
    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, pricing.UnknownRule, pricing.UnknownBasis) as exc:
        say(f"{corpus.FILENAME} is unusable: {exc}")
        say("Fix it, or delete it and let this join write a fresh one.")
        return 1

    legacy = run_dir.path(runs.DECISIONS)
    if legacy.is_file() and not book.answers:
        say(f"this run has a legacy {runs.DECISIONS} and the corpus is empty")
        say("Run `pkmnscan prices adopt` to fold every run's answers into one file first.")
        return 1

    # SEEDED, NEVER PRUNED, AND THE ASYMMETRY IS THE WHOLE POINT OF CENTRALISING. `prune` used
    # to drop unanswered entries this run no longer matched, which is right for a file scoped
    # to one run and catastrophic for one that is not: pruning against box 3's matches would
    # delete box 7's answers. Nothing here can see the other boxes, so nothing here may remove.
    added = []
    for sku in sorted(resolved.no_market_data_skus):
        if sku not in book.answers:
            book.answers[sku] = corpus.Answer(value=None, channel="unknown", from_run=run_dir.name)
            added.append(sku)

    # `rule` AND `basis` ARE THE CORPUS'S AND ARE NOT REASSIGNED FROM THE RUN. D49 Part One,
    # unchanged and pointed one level up: the manifest records what THIS join ran with and
    # `report.txt` prints it, and a record of what happened is not the answer to what should
    # happen. `--rule` seeds an EMPTY corpus and nothing else, because a document that cannot
    # answer its own question is not a document.
    if not book.answers and book.rule == "match" and book.basis == "market":
        book.rule, book.basis = str(resolved.rule), resolved.basis
    written = book.write()
    choice = book.scoped_to(
        set(resolved.matches),
        run_name=run_dir.name,
        unpriced=resolved.no_market_data_skus,
    )

    say(f"decisions        {written}")
    say(f"                 {choice.describe}")
    say(f"                 {len(book.answers)} answer(s) in the corpus, {len(resolved.matches)} matched here")
    if added:
        say(f"                 +{len(added)} unpriced SKU(s) need a hand-entered answer")
    for warning in choice.warnings:
        say(f"                 note: {warning}")

    # THE WATCH, AND THIS IS THE ONLY COMMAND THAT CAN FIRE IT (D49). A withhold can name a
    # market price the operator wants to be told about; `join` is free, re-runnable and
    # pointed at a REFRESHED export, so it is the only moment a price has moved and therefore
    # the only moment a watch has anything to say.
    for crossed in choice.watches(resolved.matches):
        say(f"                 WATCH: {crossed}")

    for reason in choice.blocking(resolved.sub_threshold_skus):
        say(f"                 EMIT WILL REFUSE: {reason}")

    # ---------------------------------------------------------------- pricing.json (D49)
    # WRITTEN AFTER `decisions.json`, so the rule it records is the one this join resolved
    # with and the one the screen will draw as the source of every suggestion. Written on
    # every join for the same reason the report is: it describes THIS join, and a stale copy
    # beside a fresh report would be the two-files-from-two-moments problem the pricing route
    # exists to avoid.
    pricing_path = run_dir.path(runs.PRICING)
    # A FRESH SNAPSHOT, not the one read at the top of this command. The write block above
    # moved `live` and drew `staged` down, so the snapshot taken before it is stale by
    # exactly the counts this table reports — and a screen drawing `pushed 2 staged 0` from
    # the wrong side of a join is a screen that disagrees with `emit` about what TCGplayer
    # holds. Lock-free, because every write in this store is an atomic replace.
    pricing_path.write_text(
        json.dumps(_pricing_table(run_dir, resolved, choice, store.read()), indent=2) + "\n",
        encoding="utf-8",
    )
    say(f"pricing table    {len(resolved.matches)} SKU(s) -> {pricing_path}")

    # ------------------------------------------------------------------------ persist
    # `exports` is the recorded shape: {game: source}, the mapping VERIFIED off the
    # files' own Product Line cells above. An old run's scalar `export` key is read-side
    # backfilled by `runs.Run.exports_by_game` and never rewritten here — this writes
    # what THIS join verified, nothing else.
    run_dir.set(
        exports={g.game: g.source for g in resolved.joins.values()},
        rule=str(resolved.rule),
        basis=resolved.basis,
        review_below_confidence=args.review_below_confidence,
        joined=True,
        counts={
            "cards_in": sum(g.report.cards_in for g in resolved.joins.values()),
            "skus": len(resolved.matches),
            "queued_main": sum(
                len(g.report.queue(routing.MAIN)) for g in resolved.joins.values()
            )
            + len(resolved.failures),
            "queued_parked": sum(
                len(g.report.queue(routing.PARKED)) for g in resolved.joins.values()
            ),
            "no_market_data": len(resolved.no_market_data_skus),
            "sub_threshold": len(resolved.sub_threshold_skus),
        },
    )

    full_report = "\n".join(
        [f"run: {run_dir.name}"]
        + [
            f"export: {(g.game + ': ') if multi else ''}{g.source['path']} "
            f"({g.source['age_days']}d, {g.source['sha256'][:12]})"
            for g in resolved.joins.values()
        ]
        + [
            f"rule={resolved.rule} basis={resolved.basis}",
        ]
        + [
            "",
            report_text,
            "",
            "pre-join failures:",
        ]
        + [f"    {f.describe}" for f in resolved.failures]
        + ["", f"standing queues: {queue_line}"]
    )
    path = run_dir.write_text(runs.REPORT, full_report + "\n")
    say("")
    say(f"report           {path}")
    say(f"next: price on #/pricing (or edit {files.prices_path()}), then pkmnscan emit "
        f"{run_dir.directory}")
    return 0
