"""`pkmnscan emit <run-dir>` — write the import CSVs. Free, re-runnable.

TWO FILES PER GAME, and neither split is cosmetic:

    import-listed.csv        above-threshold cards
    import-subthreshold.csv  cards priced by this run's disposition

The valuable cards can be staged and moved live immediately while the bulk file waits, and a
pricing mistake on the cheap file cannot touch the valuable one. Each file independently
obeys the no-duplicate-SKU rule, because two rows with one `TCGplayer Id` in one import file
is undefined behaviour and the emitter must not be able to produce it.

PER GAME because nobody has established that Import to Staged accepts a file spanning two
`Product Line`s — `fixtures/staged-import-accepted.csv` proves it for one line only, and
per-game files are correct under either answer. The default game keeps the two names above;
every other game suffixes its key (`import-listed-riftbound.csv`), see `cli/runs.py`.

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
from pipeline import corpus, decisions, join, merge, pricing, routing, tcgcsv
from store import master, files
from store.session import Store


def _warn_stale(run_dir, say) -> None:
    """Name any import file left by an EARLIER emit, at the moment this one refuses.

    Refusing writes nothing, which correctly leaves a previously-valid file alone — but a
    refusal message sitting next to an `import-listed.csv` from an hour ago is exactly how
    a stale file gets imported. Deleting it would be worse: that file may be the one already
    staged. So it is named, not removed. Globbed rather than listed, because the import
    files are per-game now and a stale one is stale whichever game wrote it.
    """
    stale = [
        path
        for pattern in ("import-listed*.csv", "import-subthreshold*.csv")
        for path in sorted(run_dir.directory.glob(pattern))
    ]
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


def _write(game_join, path, only, choice, say, label):
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
    if not only:
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
    )
    if not rows:
        say(f"{label:<16} nothing new to write — {path.name} left as it is")
        return []
    data = join.write_import(game_join.catalog, path, rows)
    written = tcgcsv.parse(data)
    skus = [row[tcgcsv.SKU_COLUMN] for row in written.rows]
    quantity = sum(int(row[tcgcsv.QUANTITY_COLUMN] or 0) for row in written.rows)
    say(f"{label:<16} {len(skus)} row(s), {quantity} card(s) -> {path}")
    return skus


def run(args, say) -> int:
    # ONE RUN OR SEVERAL, AND THE SINGLE-RUN PATH IS UNTOUCHED. A send of one still writes the
    # two per-game files it always did, so every run already on disk, every harness case and
    # every reconcile written before D86 behaves identically. `run_merged` is reached only by
    # naming more than one run, which is a thing nobody could do until now.
    named = args.run_dir if isinstance(args.run_dir, list) else [args.run_dir]
    if len(named) > 1:
        return run_merged(args, say)
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
    except (decisions.MalformedDecisions, pricing.UnknownRule, pricing.UnknownBasis) as exc:
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

        listed_skus = []
        sub_skus = []
        for game_join in resolved.joins.values():
            game = game_join.game
            if multi:
                say(f"[{game}]")
            listed, sub = _game_only(game_join.report, priced[game])
            listed_skus += _write(
                game_join,
                run_dir.path(runs.import_listed_name(game)),
                listed,
                choice,
                say,
                "listed",
            )
            sub_skus += _write(
                game_join,
                run_dir.path(runs.import_subthreshold_name(game)),
                sub,
                choice,
                say,
                "sub-threshold",
            )
    except (join.OutputSuppressed, join.Undecided, tcgcsv.ReadOnlyColumn) as exc:
        say("REFUSING to write. Nothing was written.")
        for line in str(exc).splitlines():
            say(f"    {line}")
        _warn_stale(run_dir, say)
        return 1

    emitted = set(listed_skus) | set(sub_skus)
    at_cap = [m for g in resolved.joins.values() for m in g.report.at_cap]
    if at_cap:
        # NAMED PER SKU, because "already at the live cap" is almost never the reason
        # (D59): `live_before` reads 0 on every copy of an import this pipeline has not
        # seen land, so the old line told the operator TCGplayer already holds nothing.
        say(f"{'no room':<16} {len(at_cap)} SKU(s) matched and added nothing")
        for match in at_cap[:8]:
            say(f"{'':<16} {match.sku} — {match.nothing_to_add}")

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
    with store.write() as writable:
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
            # bounded by D7's `live_cap` of 4 — and did the identity write inside it. D7 caps
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
        queue_line = writable.queue_summary
        stages = writable.inventory.listing_counts()

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
    listed_names = ", ".join(
        runs.import_listed_name(game) for game in resolved.joins
    ) or runs.IMPORT_LISTED
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


def _resolve_one(run_dir, book, say):
    """One run resolved the way `run` resolves it, for the merged path. Returns None on refusal."""
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
            review_below=run_dir.manifest.get("review_below_confidence", routing.CONFIDENCE_LOW),
        )
    except join.EmptyCatalog as refusal:
        say(f"{run_dir.name}: {refusal}")
        return None


def run_merged(args, say) -> int:
    """`pkmnscan emit <run> <run> ...` — one import file over several runs (D86).

    THE CAP IS THE WHOLE REASON THIS IS NOT A CONCATENATION OF THE FILES `emit` ALREADY WROTE.
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
        resolved = _resolve_one(run_dir, book, say)
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

    rows = merged_plan.rows(listed_only=args.listed_only)
    if not rows:
        say("nothing to write — every matched SKU is held back, unlisted, or has no room")
        for sku, why in list(merged_plan.dropped.items())[:8]:
            say(f"  {sku} — {why}")
        return 1

    corrected = [row for row in merged_plan.skus if row.over_cap]
    if corrected:
        # NAMED AND NOT COUNTED (D59). A row whose per-run claims summed past the cap is a row
        # a concatenation would have over-listed, and the operator is entitled to know which.
        say("")
        say(f"cap              {len(corrected)} SKU(s) the runs separately over-claimed:")
        for row in corrected[:8]:
            say(f"  {row.sku} {row.match.name} — runs claim {row.claimed}, "
                f"{row.match.add_to_quantity} can go")

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
        target = dirs[-1].path(runs.import_merged_name(game))
        csv_rows = merge.import_rows(group)
        try:
            # `write_import` OWNS THE DUPLICATE-SKU GATE, and it is reused rather than
            # restated. `merge.plan` is keyed by SKU so two rows with one `TCGplayer Id`
            # cannot be built here — and a property nothing checks is a comment, which is
            # exactly what that function exists to stop this file from writing.
            join.write_import(catalog, target, csv_rows)
        except join.OutputSuppressed as refusal:
            say(f"REFUSING: {refusal}. Nothing more was written.")
            return 1
        copies = sum(row.match.add_to_quantity for row in group)
        say(f"import           {len(csv_rows)} row(s), {copies} card(s) -> {target}")
        written.append((target, group))

    # --------------------------------------------------------------------- the store
    #
    # ONE PASS OVER THE MERGED PLAN, AND THE COPY BELONGS TO THE RUN THAT HOLDS IT. Every
    # position is in exactly one run, so `set_state` still stamps the run it came from — the
    # audit trail is unchanged. What is merged is the DECISION about which copies reach the
    # file: `live_keys` is sliced once over the union, so two runs cannot both count the same
    # room toward `pushed`.
    pushed = 0
    pushed_skus = 0
    shipped = {row.sku for _, group in written for row in group}
    store = Store()
    with store.write() as writable:
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
                        photo=resolved_by_run[run_name].photos.get(key),
                    )
                )
                stamped = writable.inventory.set_state(
                    key,
                    master.IDENTIFIED,
                    sku=row.sku,
                    condition=row.match.condition,
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
        queue_line = writable.queue_summary
        stages = writable.inventory.listing_counts()

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
