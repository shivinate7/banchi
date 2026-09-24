"""`pkmnscan archive` — the price-history archive: sweep the live endpoint into it, or look
at what it holds (D219, D224, D223,
D222).

WHY THIS COMMAND EXISTS. `pipeline/pricehistory.py`'s history endpoint has a hard ceiling of
357 days; everything older is already gone, and everything not captured from here ages out on
the same schedule. `sweep` is the one press that reads it and keeps a copy this store owns
past that ceiling. Modelled on `pkmnscan readings adopt` (`cli/cmd_readings.py`).

THIS PRESS TALKS AS IT WORKS, NEVER ONLY AT THE END. Measured 2026-09-19 against the owner's
real store: 914 SKUs over 4 ranges printed nothing for over ten minutes and then the whole
report at once — silence and a hang look identical from outside. `_sweep` says the subject
count and the range list before it does anything, then reports one line per commit as the
pass goes.

`sweep` PREVIEWS BY DEFAULT. `_preview` below reads only the archive and the subject list:
how many SKUs, how many already carry a bucket, how many are fresh enough that a `--write`
pass would not re-read them. That is the shape every other free, re-runnable press in this
repo shares (`reprice list`, `prices adopt`, `reconcile --live`), and it is honest about
what it can say for nothing: what the archive already holds, never a live figure it did not
pay to fetch. Building the SUBJECT LIST no longer costs literally nothing: resolving a
sealed order-ledger SKU's own Set Name needs `Market.category_id`/`.groups`
(`pipeline.pricearchive.rows_from_store`'s widened subject set, the gap D223 named and this closes). Both are cached, whole-CATEGORY reads — at most one
request per distinct Product Line this ledger has ever sold, never per SKU, and zero once
the mirror's category/group lists are warm on disk. A store with no sealed sales, or one
whose mirror lists are already cached, still previews for nothing; the first preview after
a genuinely new sealed sale is the one exception, and it is cheap.

`--write` COMMITS AS IT GOES, IN CHUNKS OF `pipeline.pricearchive.CHUNK_SKUS`, RATHER THAN
ONCE AT THE END. Measured the same day: `archive show` read 0 buckets while a sweep was an
hour into running, because the store was never written to until the whole walk finished. One
Ctrl-C or one dropped connection lost every read that hour — and the source this archive
exists to outlast ages out for good, so a lost read can be unrecoverable at any later date.
Each chunk's buckets and running accounting land in their own `Store.write()` transaction
(D88: many small transactions, not one enormous one), so an interrupt loses at most one
chunk's reads.

A RESUMED SWEEP DOES NOT RE-READ WHAT IT ALREADY HOLDS FROM A RECENT PASS.
`pipeline.pricearchive.freshness_index` and `split_by_freshness` check the archive itself —
not a second, ephemeral cache — before asking the market for anything, using
`pipeline.pricearchive.RESUME_TTL_SECONDS` (six days, D230) as
"recently read enough to trust", NEVER `pipeline.pricehistory.HISTORY_TTL_SECONDS` (one
hour) — that number is right for the live `#/pricing` screen's single-SKU read and wrong
for this walk. `rank_by_revenue` makes this pass read the same few hundred names first,
every time; a one-hour window sent every later pass back to re-read exactly those names
and never advance, measured against the owner's real store.

THE SUBJECT ORDER IS SOLD VALUE FIRST, NOT WHATEVER `cards.select` RETURNED
(`pipeline.pricearchive.rows_from_store`/`rank_by_revenue`, D223).
Measured 2026-09-19: an unranked pass answered for 206 of 914 SKUs before the host throttled
it, and only 37 of those 206 were SKUs the owner had ever actually sold. A pass that gets cut
off should have spent its requests on what earns.

THE HOST THROTTLES THIS SESSION, AND THAT IS THE NORMAL CASE, NOT AN EXCEPTION
(D222). Measured 2026-09-19 with a working `PKMNSCAN_TCG_USER_AGENT`: the
same product answered HTTP 200 minutes into a run and HTTP 403 later in the same session,
with nothing about the request different but the volume already sent. `_sweep` paces itself
on a measured interval (`pipeline.pricearchive.measured_pace`, persisted by `load_pace` /
`save_pace` under `market_cache_dir()`) rather than a guessed number, backs off once if the
host cuts it off after this pass has already read something successfully, and stops the pass
cleanly — never hammering a host that will just refuse the rest — if backing off does not
clear it. `pipeline.pricearchive.classify_refusals` rewrites a throttle's own refusal message
so it stops pointing the operator at `PKMNSCAN_TCG_USER_AGENT`, which this pass has already
proven is not the problem.

`show` IS READ-ONLY: how many buckets the archive holds, which ranges were last swept and
when, and (with `--sku`) one SKU's own buckets across every range it has been read in.

DELIBERATELY OUT OF SCOPE, BY THE OWNER'S WORD: any timer, cron or launch agent that fires
this on its own. `sweep` is a press a person runs. A schedule reverses D62's own statement
that this reader cannot fire by itself, and that reversal needs its own argument, which
nobody has made yet.
"""

from __future__ import annotations

import time
from typing import Dict, List

from pipeline import pricearchive as archive_walk
from pipeline import pricehistory
from store import files
from store.pricearchive import Source
from store.session import Store

from cli import archive_review
from cli import resolve as run_resolve


def market_cache_dir():
    """Where a sweep's fetches are cached, per checkout (D43) — the same directory
    `server/pipeline_routes.py:market_cache_dir` names, so a sweep run from the CLI is warm
    against a fetch the server already made this hour, and vice versa."""
    return files.inventory_dir() / ".market-cache"


def _pace_file():
    """Where a throttle's own measurement lives (`pipeline.pricearchive.save_pace`/
    `load_pace`) — beside the market cache rather than inside it, so `Market`'s own
    `_cache_path` glob over that directory never has to know this file is not one of its
    payloads."""
    return market_cache_dir() / "throttle-pace.json"


def _user_agent() -> str:
    """The same escape hatch `server/pipeline_routes.py:_history_user_agent` reads
    (`pipeline/pricehistory.py:AGENT_ENV`), spelled here rather than imported from `server/`
    — `server/` sits above `cli/` in this repo's layering and this command has to run with no
    server in sight, exactly `cli/cmd_readings.py`'s own reason for living beside
    `pipeline/readings.py` rather than importing `server/pipeline_routes.py`.
    """
    import envfile
    from server import tcg_export

    return (envfile.get_live(tcg_export.AGENT_ENV) or "").strip() or pricehistory.USER_AGENT


def _format_window(seconds: int) -> str:
    """`seconds` as the largest whole unit that divides it evenly, days first — so the
    resume window (D230, days) and
    `pipeline/pricehistory.py:HISTORY_TTL_SECONDS` (minutes) each print in the unit a
    person actually reads them in, rather than one shared `// 60` that turns six days into
    a four-figure minute count nobody would recognize as "six days"."""
    if seconds <= 0:
        return "0 minute(s)"
    if seconds % 86400 == 0:
        return f"{seconds // 86400} day(s)"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} hour(s)"
    return f"{seconds // 60} minute(s)"


def _read_archive(say):
    try:
        return Store().read().archive
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        say(f"the store could not be read: {exc}")
        return None


def _preview(rows: Dict[str, dict], ranges, say) -> int:
    """No network call. Names the subjects, the ranges, and what the archive already holds
    for them — the shape every other free press in this repo previews with."""
    current = _read_archive(say)
    if current is None:
        return 1

    index = archive_walk.freshness_index(current.entries.values())
    now = int(time.time())
    ttl = archive_walk.RESUME_TTL_SECONDS
    needed, fresh_skus = archive_walk.split_by_freshness(rows, index, ranges, now, ttl)
    covered = sum(1 for sku in rows if sku in index)

    say("")
    say(f"{len(current.entries)} bucket(s) already archived, over "
        f"{len(current.sources_payload())} range(s) last swept")
    say(f"{covered} of {len(rows)} sku(s) already carry at least one bucket, of any age")
    say(f"{len(fresh_skus)} sku(s) read within the last {_format_window(ttl)} — a --write "
        f"pass would not re-read them")
    say(f"{len(needed)} sku(s) would be read fresh, up to {len(needed) * len(ranges)} "
        f"request(s), highest-sold-value first")
    say("")
    say("DRY RUN — no network call was made. This preview reads only the archive and the "
        "store. Re-run with --write to sweep.")
    return 0


def _sweep(args, say) -> int:
    # Built before the subject list, not only before a `--write` pass — resolving a sealed
    # SKU's own SET NAME (D231) needs
    # `Market.category_id`/`.groups`,
    # which `rows_from_store` cannot do for itself without one. Both are cached, whole-
    # category reads (one request per PRODUCT LINE this ledger has ever sold, not per SKU),
    # so a store with no sealed sales pays nothing here and a preview costs at most a
    # handful of cheap, cached requests rather than the 357-day history walk this whole
    # command exists to pace.
    pace_file = _pace_file()
    starting_delay = archive_walk.load_pace(pace_file)
    market = pricehistory.Market(
        cache_dir=market_cache_dir(), user_agent=_user_agent(), courtesy_delay=starting_delay,
    )

    ledger_refusals: Dict[str, str] = {}
    fallback_rows: Dict[str, dict] = {}
    rows = archive_walk.rows_from_store(
        market=market, refusals=ledger_refusals, fallback_rows=fallback_rows,
    )
    ranges = pricehistory.RANGES
    if not rows:
        say("no card in this store carries a SKU, and no order-ledger line resolved to a "
            "sealed subject either — nothing to sweep")
        return 0

    if ledger_refusals:
        say(f"{len(ledger_refusals)} order-ledger sku(s) could not be resolved to a "
            "subject and are skipped this pass:")
        for line in archive_walk.format_refusals(ledger_refusals):
            say(f"  {line}")
        say("")

    say(f"{len(rows)} sku(s) subject to this pass, over {len(ranges)} range(s) "
        f"({', '.join(ranges)}) — sold value first")
    say(f"up to {len(rows) * len(ranges)} request(s) if none of it is already archived")

    if not args.write:
        return _preview(rows, ranges, say)

    current = _read_archive(say)
    if current is None:
        return 1

    # RESOLVED BY THE SKU, NEVER BY THE CARD'S OWN READ FIELDS FIRST
    # (D254, owner's ruling 2026-09-23). Read once, here, so
    # every chunk's own `sweep()` call sees the same archive and the same export cache
    # rather than each chunk re-deriving `export_rows` off disk.
    export_index = archive_walk.merged_export_rows_by_sku()
    _resolved, _verified, tiers = archive_walk.resolve_by_sku(rows, current, export_index)
    tier_counts: Dict[str, int] = {}
    for tier in tiers.values():
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    say(
        f"resolved by: {tier_counts.get(archive_walk.TIER_ARCHIVE, 0)} already-verified "
        f"(archive), {tier_counts.get(archive_walk.TIER_EXPORT, 0)} from the store's own "
        f"cached export, {tier_counts.get(archive_walk.TIER_CARD, 0)} falling back to the "
        "card's own stored fields"
    )

    index = archive_walk.freshness_index(current.entries.values())
    now = int(time.time())
    ttl = archive_walk.RESUME_TTL_SECONDS
    needed, fresh_skus = archive_walk.split_by_freshness(rows, index, ranges, now, ttl)

    say("")
    if fresh_skus:
        say(f"{len(fresh_skus)} sku(s) already read within the last {_format_window(ttl)} "
            "— not re-read this pass")
    if not needed:
        say("nothing left to read — every subject is already fresh")
        return 0

    chunks = archive_walk.chunk_rows(needed, archive_walk.CHUNK_SKUS)
    say(f"{len(needed)} sku(s) left to read, in {len(chunks)} batch(es) of up to "
        f"{archive_walk.CHUNK_SKUS}")
    say("")

    totals = {r: {"answered": len(fresh_skus), "refused": 0} for r in ranges}
    all_refusals: Dict[str, str] = {}
    all_resolved_via_ledger: List[str] = []
    total_buckets = 0
    done = 0
    answered_so_far = 0
    requests_baseline = 0
    backed_off_already = False
    pass_start = time.time()
    stopped_early = False

    for i, chunk in enumerate(chunks, start=1):
        buckets, sources, refusals, resolved_via_ledger = archive_walk.sweep(
            chunk, market, ranges=ranges, fallback_rows=fallback_rows,
            archive=current, export_rows=export_index,
        )
        all_resolved_via_ledger.extend(resolved_via_ledger)
        # ONE SIGNAL, USED TWICE — whether to rewrite a 403's message and whether to treat
        # it as a throttle worth backing off for. Computed from THIS chunk's own answered
        # count too, not only earlier chunks', so a chunk that itself answers some SKUs
        # before getting others blocked is not told two different stories about the same
        # pass.
        this_chunk_answered = len(chunk) - len(refusals)
        had_signal = answered_so_far > 0 or this_chunk_answered > 0
        refusals, blocked_count = archive_walk.classify_refusals(
            refusals, had_earlier_success=had_signal
        )
        for source in sources:
            totals[source.range]["answered"] += source.answered
            totals[source.range]["refused"] += source.refused
        all_refusals.update(refusals)
        total_buckets += len(buckets)
        done += len(chunk)
        answered_so_far += this_chunk_answered

        commit_sources = [
            Source(range=r, at=int(time.time()), requested=len(rows),
                   answered=t["answered"], refused=t["refused"])
            for r, t in totals.items()
        ]
        with Store().write() as snapshot:
            snapshot.archive.upsert(buckets)
            snapshot.archive.record_pass(commit_sources)

        say(f"  [{i}/{len(chunks)}] {len(chunk)} sku(s) read -> {len(buckets)} bucket(s), "
            f"{len(refusals)} refused  ({done}/{len(needed)} done)")

        if blocked_count and had_signal:
            elapsed = time.time() - pass_start
            requests_made = requests_baseline + market.requests
            new_delay = archive_walk.measured_pace(requests_made, elapsed)
            say("")
            say(f"the host throttled this session: {blocked_count} sku(s) answered HTTP "
                f"403 after {requests_made} request(s) over {elapsed:.0f}s this pass")
            archive_walk.save_pace(
                pace_file, new_delay, requests_made=requests_made,
                elapsed_seconds=elapsed, at=int(time.time()),
            )
            if backed_off_already:
                say(f"still throttled at {new_delay:.2f}s between requests — stopping this "
                    "pass here.")
                say("every bucket committed above is safe. Re-run `archive sweep --write` "
                    "later to resume; it will not re-read what this pass already archived.")
                stopped_early = True
                break
            say(f"pacing to {new_delay:.2f}s between requests (was "
                f"{starting_delay:.2f}s) and continuing")
            requests_baseline = requests_made
            market = pricehistory.Market(
                cache_dir=market_cache_dir(), user_agent=_user_agent(),
                courtesy_delay=new_delay,
            )
            backed_off_already = True

    say("")
    say(f"{total_buckets} bucket(s) read this pass, over {len(ranges)} range(s)")
    for r in ranges:
        t = totals[r]
        say(f"  {r:<10} {t['answered']}/{len(rows)} sku(s) answered, {t['refused']} refused")

    if all_resolved_via_ledger:
        say("")
        say(f"{len(all_resolved_via_ledger)} sku(s) resolved via the ledger's own row "
            "after the card row could not:")
        for sku in sorted(all_resolved_via_ledger):
            say(f"  {sku}")

    say("")
    if all_refusals:
        say(f"{len(all_refusals)} sku(s) asked for and never answered:")
        for line in archive_walk.format_refusals(all_refusals):
            say(f"  {line}")
    else:
        say("every sku asked for came back with an answer or a known reason it could not")

    # A REFUSAL THAT NAMES THE CARD'S OWN IDENTIFICATION, NEVER ONE ABOUT THE NETWORK, GOES
    # TO THE REVIEW QUEUE WITH ITS PHOTO (`cli/archive_review.py`, this task's own rule off
    # `CLAUDE.md`: "ambiguity goes to the review queue with its photo"). `Queue.upsert`
    # (D167's own primitive) makes this idempotent for free — an already-queued position is
    # refreshed in place rather than duplicated, and an answered one is never re-asked.
    id_refusals = {
        sku: message
        for sku, message in all_refusals.items()
        if archive_review.is_identification_refusal(message)
    }
    if id_refusals:
        inventory = Store().read().inventory
        matches = archive_review.cards_for_refusals(inventory, rows, id_refusals)
        boxes = {match.card.box for match in matches}
        views = run_resolve.box_views(inventory, boxes=boxes)
        build = archive_review.queue_entries(matches, views)
        entries = build.entries
        if entries:
            with Store().write() as writable:
                added = archive_review.apply(writable.review, entries)
            say("")
            say(
                f"queued           {added} card(s) sent to the review queue, "
                f"identification unresolved, with their photograph"
            )
            if added < len(entries):
                say(
                    f"                   {len(entries) - added} already queued or answered — "
                    "left exactly as they stand (D167)"
                )
        # CLAUDE.md's own hard rule, "never drop a card without saying so" (review round,
        # HIGH finding, 2026-09-24). A bound card matched this sweep's own refusal but
        # carried no recorded reading (`archive_review.QueueBuild.unavailable`) — named
        # BY POSITION in this press's own output, never folded into a bare count and never
        # left for a reader to notice is missing.
        if build.unavailable:
            say("")
            say(
                f"unavailable      {len(build.unavailable)} card(s) matched this sweep's "
                f"own refusal but could not be queued:"
            )
            for skipped in build.unavailable:
                say(f"                   {skipped.position}  {skipped.reason}")

    say("")
    say(f"written          {total_buckets} bucket(s) folded in across up to {len(chunks)} "
        "commit(s), never deleting one this pass did not mention")
    return 1 if stopped_early else 0


def _show(args, say) -> int:
    current = _read_archive(say)
    if current is None:
        return 1

    entries = dict(current.entries)
    sources = current.sources_payload()
    say(f"{len(entries)} bucket(s) archived, over {len(sources)} range(s) last swept")
    for source in sources:
        say(f"  {source['range']:<10} {source['answered']}/{source['requested']} sku(s) "
            f"answered  at {source['at']}")

    sku = getattr(args, "sku", None)
    if sku:
        say("")
        found = current.for_sku(sku)
        if not found:
            say(f"{sku}: no bucket archived")
            return 0
        say(f"{sku}: {len(found)} bucket(s)")
        for bucket in found:
            say(f"  {bucket.range:<10} {bucket.start}  market {bucket.market}  "
                f"qty {bucket.quantity}  width {bucket.width_days}d")
    return 0


def run(args, say) -> int:
    if args.archive_command == "sweep":
        return _sweep(args, say)
    return _show(args, say)
