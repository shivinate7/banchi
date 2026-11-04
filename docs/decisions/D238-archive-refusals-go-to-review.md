# D238 — Archive refusals go to review

**Only an identification refusal reaches the review queue.** A refusal from `banchi archive sweep` carries a kind. `pipeline/pricehistory.refusal` sets it from the exception class, as one of the `KIND_*` constants. `cli/archive_review.is_identification_refusal` queues only `KIND_IDENTIFICATION`.

- `NotResolvable` and a bare `PriceHistoryError` are identification. An untagged message counts as identification, so no review item is hidden.
- `Unreachable` and `Offline` are network. `Blocked`, an HTTP 403, is blocked, never identification. `UnknownRange` is request. None of these is queued.
- An HTTP 404 is identification until measured. Whether a 404 means a missing product or an outage is unmeasured.
- Ledger-path refusals (`pipeline/pricearchive._ledger_export_rows`) carry their kind the same way.
- The verdict follows the kind, never the wording.

**Match the card, never the SKU.** One SKU can cover copies with different stored numbers. On the owner's store, `Exeggutor`'s SKU covers seven copies: six numbered `005`, one blank (D234, archive reads the composed card number). `pipeline/pricearchive.rows_from_store` tests one row per SKU. A SKU match would queue six correct cards. `cli/archive_review.cards_for_refusals` matches each card's own stored `(name, number, set_name)`.

**Write the queue through one door.** `store/queues.py:Queue.upsert` keeps `first_seen`. It refuses to re-queue a cleared position, so an answer outlives its question (D167, queue entries re-resolve where they stand). `Queue.reopen` is not used: D28 (review answers undo) is for a person in the same sitting. The reason is `pipeline/variant.NO_CATALOG_ROW`, the join ladder's word for zero candidate rows.

**Where it runs.** `cli/cmd_pricearchive._sweep`, at the end of a `--write` pass, after retry and throttle. A preview makes no network call, so it cannot list refusals.

**Known gap.** A stale catalog list can make a network fault look like an unknown set, so it is queued as identification. Debt: `DEBT-stale-cache-fault-looks-like-id`.

**Limit.** Answered entries never resurface, even when wrong. See DEBT33 (an answered queue entry can never resurface).

**What proves it.** `scripts/archive-review-selftest.py`, on a throwaway store, with no network call. `make archive-review-selftest` runs it, path-gated (D247, guard self-tests are path-gated). It proves:

- An identification refusal reaches the review queue with its photograph, under `pipeline/variant.NO_CATALOG_ROW`.
- A second pass over the same refusal adds nothing.
- A card that shares the SKU but carries a different stored number is never queued.
- A card with no photograph is never queued.
- A network-shaped refusal is never queued.
- A mutation arm that writes the queue directly duplicates and reopens an answered entry. So the choice of `Queue.upsert` is load-bearing.
- Each fetch failure the header lists (no connection, a dropped read, HTTP 503, 500, 403, an unreadable body) is never an identification refusal.
- A `NotResolvable` is identification, even when its words name a network failure.
- Every `PriceHistoryError` subclass has its pinned kind.
- An HTTP 404 from the history endpoint is an identification refusal and queues for review.

Ledger-path kinds are proved in `scripts/pricearchive-selftest.py`, under its section "a ledger refusal carries the kind its failure was".

Governs: `cli/archive_review.py`, `cli/cmd_pricearchive.py`.
