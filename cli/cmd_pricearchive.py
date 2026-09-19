"""`pkmnscan archive` — the price-history archive: sweep the live endpoint into it, or look
at what it holds (D-a-price-history-archive).

WHY THIS COMMAND EXISTS. `pipeline/pricehistory.py`'s history endpoint has a hard ceiling of
357 days; everything older is already gone, and everything not captured from here ages out on
the same schedule. `sweep` is the one press that reads it and keeps a copy this store owns
past that ceiling. Modelled on `pkmnscan readings adopt` (`cli/cmd_readings.py`), and
DELIBERATELY DIFFERENT FROM IT IN ONE RESPECT: `readings adopt --write` is a full replace,
because `readings` is a cache of files still on disk. `archive sweep --write` is never a
replace — see `store/pricearchive.py`'s module docstring for why a bucket this pass did not
mention must survive untouched, forever, once the source can no longer reproduce it.

`sweep` PREVIEWS BY DEFAULT, for the property every free, re-runnable press in this repo
shares — a write nobody watched is how a session finds out a table changed only after
something downstream reads it — even though, like `readings adopt`, there is no operator
JUDGEMENT inside this walk to protect: what it reads is what the endpoint said.

`show` IS READ-ONLY: how many buckets the archive holds, which ranges were last swept and
when, and (with `--sku`) one SKU's own buckets across every range it has been read in.

DELIBERATELY OUT OF SCOPE, BY THE OWNER'S WORD: any timer, cron or launch agent that fires
this on its own. `sweep` is a press a person runs. A schedule reverses D62's own statement
that this reader cannot fire by itself, and that reversal needs its own argument, which
nobody has made yet.
"""

from __future__ import annotations

from pipeline import pricearchive as archive_walk
from pipeline import pricehistory
from store import files
from store.session import Store


def market_cache_dir():
    """Where a sweep's fetches are cached, per checkout (D43) — the same directory
    `server/pipeline_routes.py:market_cache_dir` names, so a sweep run from the CLI is warm
    against a fetch the server already made this hour, and vice versa."""
    return files.inventory_dir() / ".market-cache"


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


def _sweep(args, say) -> int:
    rows = archive_walk.rows_from_store()
    if not rows:
        say("no card in this store carries a SKU — nothing to sweep")
        return 0

    market = pricehistory.Market(cache_dir=market_cache_dir(), user_agent=_user_agent())
    buckets, sources, refusals = archive_walk.sweep(rows, market, ranges=pricehistory.RANGES)

    say(f"{len(rows)} sku(s) asked about -> {len(buckets)} bucket(s) read, "
        f"over {len(sources)} range(s)")
    for source in sources:
        say(f"  {source.range:<10} {source.answered}/{source.requested} sku(s) answered, "
            f"{source.refused} refused")

    say("")
    if refusals:
        say(f"{len(refusals)} sku(s) asked for and never answered:")
        for sku in sorted(refusals)[:20]:
            say(f"  {sku}  {refusals[sku]}")
        if len(refusals) > 20:
            say(f"  ... and {len(refusals) - 20} more")
    else:
        say("every sku asked for came back with an answer or a known reason it could not")

    if not args.write:
        say("")
        say("DRY RUN — nothing written. Re-run with --write to archive what was read.")
        return 0

    with Store().write() as snapshot:
        snapshot.archive.upsert(buckets)
        snapshot.archive.record_pass(sources)

    say("")
    say(f"written          {len(buckets)} bucket(s) folded in, never deleting one this pass "
        "did not mention")
    return 0


def _show(args, say) -> int:
    try:
        current = Store().read().archive
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        say(f"the store could not be read: {exc}")
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
