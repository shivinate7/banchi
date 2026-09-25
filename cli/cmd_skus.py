"""`pkmnscan skus adopt` — the one-time backfill press over every export already on disk
(docs/specs/identity-follows-sku.md §3.2, lane 0).

Modelled on `pkmnscan readings adopt` (`cli/cmd_readings.py`): a re-runnable press that walks
files already fetched and folds them into a store table, previewing by default. THE FOLD IS
NOT A FULL REPLACE, unlike `readings adopt` — `store/skus.py`'s whole argument is that this
table never deletes, so `adopt` is a fold onto whatever the table already holds, never a
clear-then-reinsert. A preview folds onto an IN-MEMORY COPY of the table as it stands; nothing
here is written until `--write`, and the same walk runs once, for real, inside the store lock
on that press — never twice, and never outside it.

The spec names one subcommand, `adopt`. This module builds only that one; a `skus show`
sibling, the shape every other table-backed command here carries (`prices show`, `readings
show`, `archive show`), is deliberately left for a later word rather than built unasked —
see this lane's own report for why.
"""

from __future__ import annotations

import time
from typing import Dict

from pipeline import skus as skus_walk
from store import files
from store.rows import Rows
from store.skus import SkuRow, Skus
from store.session import Store


def _adopt(args, say) -> int:
    write = bool(getattr(args, "write", False))
    try:
        before: Dict[str, SkuRow] = dict(Store().read().skus.entries)
    except (files.StoreError, OSError, ValueError, TypeError) as exc:
        say(f"the store could not be read: {exc}")
        return 1
    before_count = len(before)

    started = time.time()
    if write:
        with Store().write() as snapshot:
            report = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            after_count = len(snapshot.skus.entries)
    else:
        preview = Skus(entries=Rows(Skus.ENTRIES, objects=dict(before)))
        events: list = []
        report = skus_walk.fill(preview, events)
        after_count = len(preview.entries)
    elapsed = time.time() - started

    say(f"{report.files_read} file(s) read"
        + (f", {len(report.files_skipped)} skipped (an unreadable stamp or a malformed "
           "export)" if report.files_skipped else "")
        + f", in {elapsed:.2f}s")
    say(f"{report.inserted} new, {len(report.changed)} changed, {report.unchanged} unchanged, "
        f"{report.stale} stale (an older file, already superseded on disk)")
    if report.changed:
        say("")
        say("  CHANGED — a newer file disagrees with what an older one said about this SKU:")
        for sku, old, new in report.changed[:10]:
            say(f"    {sku}  {old.product_name} ({old.rarity}) -> "
                f"{new.product_name} ({new.rarity})")
        if len(report.changed) > 10:
            say(f"    ... and {len(report.changed) - 10} more")
    say("")
    say(f"{after_count} sku(s) in the table ({before_count} before this press)")

    if not write:
        say("")
        say("DRY RUN — nothing written. Re-run with --write to adopt.")
        return 0

    say("")
    say(f"written          {after_count} sku(s)")
    return 0


def run(args, say) -> int:
    if args.skus_command == "adopt":
        return _adopt(args, say)
    say("usage: pkmnscan skus adopt [--write]")
    return 1
