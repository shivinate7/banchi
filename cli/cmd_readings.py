"""`pkmnscan readings` — the cached market-reading table: fold the two sources in, or look at it.

WHY THERE IS A COMMAND AT ALL. `server/pipeline_routes.py:_readings()` used to walk every
run's `pricing.json` and the newest live export on EVERY `GET /pipeline/value`, comparing the
two sources on a clock. Correct, and expensive to keep doing on a store with a growing
`runs/` directory — every one of those files was re-parsed on every request whether or not
anything on disk had moved since the last one. `readings` (`store/readings.py`) is the table
that walk now fills once; `_readings()` is a plain `SELECT` against it.

`adopt` DOES THE WALK AND WRITES THE TABLE. IT PREVIEWS BY DEFAULT.

Modelled on `pkmnscan prices adopt` (`cli/cmd_prices.py`), and DELIBERATELY SIMPLER than it in
one respect: `prices adopt` previews because folding a run's `decisions.json` into the shared
corpus is a REAL DECISION — newest-wins can silently replace a deliberate price hold with a
figure nobody meant to compare it to (D86). Nothing here is a decision. `readings` holds no
operator judgement at all; it is what the market says, arbitrated on nothing but which file
is newer, and running the same walk twice over the same files produces the same answer both
times. The preview exists anyway, for the property `prices adopt`, `join`, `reconcile` and
`reprice list` all share: a write nobody watched is how a session finds out a table changed
only after something downstream reads it. `--write` is one press, and there is no `--force` —
there is nothing here for a flag to override.

`show` IS READ-ONLY AND NEVER WRITES: what the table holds right now, and which files it
last credited.
"""

from __future__ import annotations

from typing import Dict

from pipeline import readings as readings_walk
from store import files
from store.readings import Reading
from store.session import Store


def _adopt(args, say) -> int:
    found, sources = readings_walk.collect()

    try:
        before: Dict[str, Reading] = dict(Store().read().readings.entries)
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        say(f"the store could not be read: {exc}")
        return 1

    added = sorted(sku for sku in found if sku not in before)
    dropped = sorted(sku for sku in before if sku not in found)
    changed = sorted(
        sku for sku, reading in found.items()
        if sku in before and before[sku] != reading
    )
    unchanged = len(found) - len(added) - len(changed)

    say(f"{len(sources)} source(s) -> {len(found)} reading(s)")
    for source in sources:
        say(f"  {source.kind:<4} {source.name}  {source.skus} sku(s) priced  at {source.at}")
    if not sources:
        say("  no run carries a readable pricing.json and no live export could be read — "
            "nothing to adopt")

    say("")
    say(f"{len(added)} new, {len(changed)} changed, {unchanged} unchanged, "
        f"{len(dropped)} dropped against the table as it stands")
    if dropped:
        say("dropped — no source offers these SKUs any more (a run directory removed, or a "
            "live export retired by hand):")
        for sku in dropped[:20]:
            say(f"  {sku}")
        if len(dropped) > 20:
            say(f"  ... and {len(dropped) - 20} more")

    if not args.write:
        say("")
        say("DRY RUN — nothing written. Re-run with --write to adopt.")
        return 0

    with Store().write() as snapshot:
        snapshot.readings.replace(found, sources)

    say("")
    say(f"written          {len(found)} reading(s), {len(sources)} source(s)")
    return 0


def _show(args, say) -> int:
    try:
        current = Store().read().readings
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        say(f"the store could not be read: {exc}")
        return 1

    entries = dict(current.entries)
    sources = current.sources_payload()
    say(f"{len(entries)} reading(s), from {len(sources)} source(s)")
    for source in sources:
        say(f"  {source['kind']:<4} {source['name']}  {source['skus']} sku(s) priced  "
            f"at {source['at']}")
    return 0


def run(args, say) -> int:
    if args.readings_command == "adopt":
        return _adopt(args, say)
    return _show(args, say)
