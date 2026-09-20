## D238 — The archive's own refusals reach a human, with a photo

**What this builds.** `pkmnscan archive sweep`'s own refusals now route to the standing
review queue. `cli/archive_review.py` is the new module. `store/queues.py:Queue.upsert`
(D167) is the only write primitive it calls. No new queue exists. No new file format
exists. `CLAUDE.md`'s own rule is the reason: an ambiguity goes to the review queue with
its photo, and never gets guessed at or silently dropped.

**Why the primitive is reused, not rebuilt.** `Queue.upsert` already does three things this
task needs. It preserves `first_seen`. It refuses to re-queue a cleared position. It is
already the one door `cli/cmd_join.py` and `cli/requeue.py` write through. A third caller,
over a different source of ambiguity, needed no new mechanism.

**Why the match is per card, never per SKU.** A single SKU can cover several physical
copies that carry different stored numbers. Measured on the owner's real store: `Exeggutor`,
SKU 8936550, in `ME01: Mega Evolution`, covers 7 cards. Six carry `005`. One is blank.
`pipeline/pricearchive.py:rows_from_store` picks ONE row per SKU to test against the
mirror. Only the blank one was ever actually asked about. Queuing every card sharing the
SKU would put six correctly-numbered copies in front of a human for a question that was
never raised. `cli/archive_review.py:cards_for_refusals` matches on the card's own stored
`(name, number, set_name)`, never on the SKU alone.

**Why a network-shaped refusal never reaches the queue.** A refusal that says the host
could not be reached, or answered an HTTP error, is a fact about the network right now, not
about the card's stored identification. `is_identification_refusal` excludes it by matching
known network phrasings — `pipeline/pricehistory.py:Unreachable`'s own three messages, and
`Blocked`'s, both read but not edited. `pipeline/pricearchive.py`, `pipeline/pricehistory.py`
and `store/numbers.py` are all untouched, per this task's own fence.

**Why the reason is `pipeline/variant.py:NO_CATALOG_ROW`.** It is the exact vocabulary the
real join ladder already uses for zero candidate rows found in the catalogue. A new string
for the same fact would be a second word this repo would then have to keep in step.

### The measurement, read-only against the owner's real store

**The 15 subjects from `D237` match 16 physical cards.**
One subject, `Heart of the Tempest`, matches two copies that share the identical
blank identification. Every one of the 16 carries a photograph. This count is not
"far more than 16." It is the expected count.

**Every one of the 16 is ALREADY marked answered in the standing queue.** This is the
finding that matters most. Checked against `inventory/store.sqlite`'s own `events` table:
13 of the 16 positions carry a real `answered` event, meaning a human already looked at the
photo and typed a name, number and SKU. Three more carry no logged event at all, but are
still marked `cleared_by_human` with `reason: no_catalog_row` already recorded, first seen
2026-09-01. **`Queue.upsert` refuses to re-queue any of them, on purpose (D167).** The whole
point of that refusal is that an answer must outlive the question that produced it.

**Measured result: this build would add zero new entries, run today against the real store.**
Not because nothing needs a human's eyes. Because every one of the 16 already
had a human's eyes, and the answer that human gave still does not resolve against the
catalogue.

### The conflict this surfaces, and why it is not resolved here

`CLAUDE.md`'s hard rule for this task is explicit: *"An already-queued card is not
re-queued, and an answered entry is never dropped or re-asked (D167's own promise)."* This
build honours that rule exactly. The result is that the specific 16 cards this task names
cannot be surfaced to a human through the standing queue at all, because a human already
answered for every one of them.

**This is a genuinely different problem than "uncaught ambiguity."** A card that has never
been queued is what `Queue.upsert` is for. A card a human already answered, whose answer
still does not resolve months later against a live catalogue, needs a different mechanism —
one this task does not build, because building it means either reopening an answer
(`Queue.reopen`, D28's own undo window, built for a person reversing themselves inside the
same sitting, never for a machine finding a stale answer months later) or inventing a third
state alongside "open" and "cleared." Both are real product decisions. Neither is named in
this task's brief, and neither is decided here.

**What this build does correctly, for every card not already through review:**
a refused SKU whose card has never been queued, or whose queue entry is still
open, reaches the review queue with its photograph, exactly as specified. The fixture test
below proves this path. The real-store measurement proves the 16 named cards are not that
path, and says so rather than working around it.

### Where this is wired

`cli/cmd_pricearchive.py:_sweep`, at the end of a `--write` pass, after the final refusal
set is known (post-retry, post-throttle). This is "one condition in an existing walk," per
this task's own suggestion, not a new command. There is no separate preview for this step:
`archive sweep`'s own preview never calls the network, so it never knows what would refuse,
and there is nothing new to preview about routing a refusal that has not happened yet.

### What proves it

`scripts/archive-review-selftest.py`, a throwaway store fixture, no network. It proves: a
card whose identification does not resolve reaches the review queue with its photograph. A
second run over the same store adds nothing new. A card sharing the SKU but carrying a
DIFFERENT stored number is never queued. A network-shaped refusal is never queued. A
mutation arm — replacing `Queue.upsert` with a raw dict write that skips its cleared-entry
guard — is shown to duplicate and re-open an answered entry, proving the real code's choice
of primitive is load-bearing.

Governs: `cli/archive_review.py`, `cli/cmd_pricearchive.py`. Cites D167 (the queue's own
refresh precedent and its refusal to re-ask an answered entry), D233 and D234 (this
archive's own two prior mechanism rounds), D28 (the undo window this build does not use),
and `D237` (this session's sibling analysis).
