# Command line

Argument parsing and sequencing for the four commands.

## Code files

- `cli/__init__.py` — Makes `cli` a package.
- `cli/__main__.py` — Parser, COMMANDS dispatch, exit codes.
- `cli/archive_review.py` — Routes one `archive sweep` pass's own identification-shaped refusals (never a network-shaped one) to the standing review queue, with each card's own photograph, over `store/queues.py:Queue.upsert` — never a new queue or write primitive.
- `cli/cmd_boxes.py` — `banchi boxes names` — the one-time backfill that gives every unnamed box the stored name `Box <number>` (`store/master.py:Inventory.box_name_plan`).
- `cli/cmd_cards.py` — `banchi cards <name|audit|checks|identity|contradictions|sku-names|photos|variants>` — the card's stable name (D172) and, since lane `2` of identity-follows-sku.md, its identity.
- `cli/cmd_emit.py` — Write ONE import CSV, `import.csv`; refuses while a price is unanswered.
- `cli/cmd_holdingsroster.py` — `banchi holdings-roster <csv>` — the owner's investment roster valued at this store's prices (D324).
- `cli/cmd_identify.py` — Submit, wait, collect, cache.
- `cli/cmd_join.py` — Resolve identifications against the export; --dry-run previews.
- `cli/cmd_match.py` — `banchi match status | prepare | audit | --sweep-worker` — the free reader's setup and the background reader's worker (D2): it reads the queue and exits, writing only `marqo-b` identifications rows.
- `cli/cmd_pricearchive.py` — `archive sweep` builds a `Market` before it reads `rows_from_store(market=..., refusals=..., include_catalog=True)` (sold value first, sealed product folded in, then up to `CATALOG_SKUS_PER_PASS` Riftbound catalog SKUs, stalest first), prints any ledger SKU that could not be resolved to a subject, then previews: subject count, what the archive already holds, what is fresh enough to skip.
- `cli/cmd_prices.py` — `banchi prices adopt` folds every run's legacy decisions.json into the corpus — previews unless given --write, newest-wins, and NAMES the holds a later price replaced rather than counting them — and RETIRES each folded file to decisions.json.adopted.
- `cli/cmd_queue.py` — `banchi queue refresh` — re-resolve every OPEN queue entry against a current export, store-wide.
- `cli/cmd_readings.py` — `banchi readings adopt` runs `pipeline/readings.py:collect` and folds the result into the `readings` table with `Readings.replace()` — a full clear-then-reinsert, on `--write`.
- `cli/cmd_reconcile.py` — Diff intent against TCGplayer's Export From Staged; --phantoms lists live copies beyond what is really on hand.
- `cli/cmd_reprice.py` — `banchi reprice list` reports which live listings are not selling and writes a WORKLIST with a price already proposed on every row; `reprice apply` reads the operator's edited worklist back and writes the price-only import CSV (D100).
- `cli/cmd_rescue.py` — `banchi rescue <run>` re-addresses a STRANDED run's cards to the positions their photographs are at now and derives a SECOND run over the drawer they are actually in, carrying that drawer's `bid` (D145).
- `cli/cmd_scan.py` — Read the QR codes off a directory of code-card photos into the ledger.
- `cli/cmd_sku_contradictions.py` — `banchi cards contradictions` — RETIRED.
- `cli/cmd_sku_name_contradictions.py` — `banchi cards sku-names` — RETIRED.
- `cli/cmd_skus.py` — `banchi skus adopt` runs `pipeline/skus.py:fill` against an in-memory copy of the table for a preview, or against the real, lock-held snapshot on `--write` — the SAME walk either way, never run twice per invocation.
- `cli/requeue.py` — The store-wide queue refresh's engine.
- `cli/resolve.py` — Turning a run's identifications into a join; shared by join and emit.
- `cli/runs.py` — Run directories and manifest.json.
