# D238 — Archive refusals go to review

**`banchi archive sweep`'s own refusals now route to the standing review queue.** `cli/archive_review.py` is the new module. Its only write primitive is `store/queues.py:Queue.upsert` (D167). No new queue exists, and no new file format exists. `CLAUDE.md` requires the route. An ambiguity goes to the review queue with its photo. It is never guessed at, and it is never dropped silently.

**The primitive is reused, not rebuilt.** `Queue.upsert` already does three things this task needs. It keeps `first_seen`. It refuses to re-queue a cleared position. It is already the one door that `cli/cmd_join.py` and `cli/requeue.py` write through. A third caller, over a different source of ambiguity, needed no new mechanism.

**The match is per card, never per SKU.** One SKU can cover several physical copies that carry different stored numbers. Measured on the owner's real store: `Exeggutor`, SKU 8936550, in `ME01: Mega Evolution`, covers 7 cards. Six carry `005`. One is blank. `pipeline/pricearchive.py:rows_from_store` picks ONE row per SKU to test against the mirror. Only the blank one was ever asked about. Queuing every card that shares the SKU would put six correctly numbered copies in front of a person for a question nobody raised. `cli/archive_review.py:cards_for_refusals` matches on the card's own stored `(name, number, set_name)`, never on the SKU alone.

**A network refusal never reaches the queue.** A refusal that says the host could not be reached, or returned an HTTP error, describes the network at that moment. It says nothing about the card's stored identification. `is_identification_refusal` excludes it by matching known network phrasings. Those phrasings are the three messages of `pipeline/pricehistory.py:Unreachable`, and the message of `Blocked`. The module reads them and does not edit them. `pipeline/pricearchive.py`, `pipeline/pricehistory.py` and `store/numbers.py` are untouched, as this task's fence requires.

**The reason is `pipeline/variant.py:NO_CATALOG_ROW`.** It is the exact vocabulary that the real join ladder already uses for zero candidate rows in the catalogue. A new string for the same fact would be a second word this repo must keep in step.

### The measurement, read-only against the owner's real store

**The 15 subjects from `D239` match 16 physical cards.** One subject, `Heart of the Tempest`, matches two copies with the same blank identification. All 16 carry a photograph. The count of 16 is the expected count, not a surprise.

**All 16 are already marked answered in the standing queue.** This is the finding that matters most. Checked against the `events` table in `inventory/store.sqlite`, 13 of the 16 positions carry a real `answered` event. A person already looked at each photo and typed a name, number and SKU. Three more have no logged event. They are still marked `cleared_by_human`, with `reason: no_catalog_row` already recorded, and they were first seen earlier. **`Queue.upsert` refuses to re-queue any of them, on purpose (D167).** That refusal exists because an answer must outlive the question that produced it.

**Measured result: this build adds zero new entries when run against the real store today.** Nothing needs a person's eyes that does not already have them. Every one of the 16 cards already had a person's review. The answer that person gave still does not resolve against the catalogue.

### The conflict this surfaces, and why it is not resolved here

`CLAUDE.md`'s hard rule for this task says two things. A card already in the queue is not queued again. An answered entry is never dropped or asked again. That is D167's own promise. This build keeps the rule exactly. As a result, the 16 cards named in this task cannot reach a person through the standing queue. A person has already answered for every one of them.

**This is a different problem from uncaught ambiguity.** A card never queued is what `Queue.upsert` is for. A card that a person already answered needs another mechanism. Its answer still does not resolve months later against a live catalogue. This task does not build that mechanism. Building it means either reopening an answer (`Queue.reopen`, the D28 undo window, built for a person who reverses a choice in the same sitting, never for a machine that finds a stale answer later) or adding a third state beside "open" and "cleared". Both are product decisions. The task brief does not name either one, so this entry does not decide either one.

**What this build does correctly, for every card not already through review:** a refused SKU reaches the review queue with its photograph, as specified. This holds when the card was never queued, or when its queue entry is still open. The fixture test below proves this path. The real-store measurement proves that the 16 named cards are not on this path. It says so, and it does not work around that.

### Where this is wired

`cli/cmd_pricearchive.py:_sweep`, at the end of a `--write` pass, after the final refusal set is known (after retry and after throttle). This is one condition in an existing walk, as the task suggested. It is not a new command. There is no separate preview for this step. `archive sweep`'s own preview never calls the network, so it cannot know what would refuse. A refusal that has not happened yet has nothing to preview.

### What proves it

`scripts/archive-review-selftest.py` uses a throwaway store fixture and makes no network calls. It proves five things. A card whose identification does not resolve reaches the review queue with its photograph. A second run over the same store adds nothing. A card that shares the SKU but carries a DIFFERENT stored number is never queued. A network refusal is never queued. A mutation arm replaces `Queue.upsert` with a raw dict write that skips the cleared-entry guard. That arm duplicates and reopens an answered entry, which proves that the real code's choice of primitive matters.

Governs: `cli/archive_review.py`, `cli/cmd_pricearchive.py`. Cites D167 (the queue's refresh precedent, and its refusal to ask again about an answered entry), D231 and D234 (this archive's two earlier mechanism rounds), D28 (the undo window this build does not use), and `D239` (the sibling analysis from the same session).
