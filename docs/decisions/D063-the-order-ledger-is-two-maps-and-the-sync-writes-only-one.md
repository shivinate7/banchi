## D63 — The order ledger is two maps, and the sync writes only one of them

**Built 2026-08-30, as the durable half of the order flow.** `pipeline/orders.py` resolves
an order line to the copies that fill it and stores nothing; this is `inventory/orders.json`
and `store/orders.py`, one record per `{source}:{order_number}`, upserted, read and written
through the existing `Store` session in the shape `store/queues.py` uses.

**The split is the design and not a packaging choice.** The resolver's answer is a set of
positions true of ONE `Inventory` snapshot and of no other — D36, which exists because a run
directory's own slot numbers stopped being the truth the moment a mid-box delete slid every
higher card down one — so it is recomputed on every read. An ORDER is the opposite kind of
fact: it happened outside this machine, it outlives every snapshot, and re-deriving it is
not possible at all. One of those must be stored and the other must never be.

### The file has two top-level maps, and `ingest` can name only one

    orders      what the FEED said.  Replaced wholesale on every sync.
    fulfilment  what WE did.         `ingest` cannot reach it.

**One record holding both is the defect this entry exists to prevent.** Ingest replaces by
key, so a fulfilment count living inside the replaced record is destroyed on the next sync —
and the consequence is not a lost statistic. It is the resolver handing out a copy that is
already in an envelope, and a picker walked to a slot whose card left the building on
Tuesday. **The same physical card sold twice**, discovered by the second buyer.

**A careful merge inside `ingest` WOULD ALSO WORK, AND IS REFUSED.** `Queue.upsert` is
exactly that shape — it preserves `first_seen` and refuses to touch a cleared entry — and it
has held for months, so this is not an argument that merges are unsafe. It is an argument
about which property a later session can check. "Two maps, and this method touches one of
them" is verifiable by reading eleven lines; "this merge preserves everything it should" is
verifiable only by knowing every field that must survive, which is a list that grows. The
merge is one refactor from being wrong and the split is not.

**`first_seen` is a deliberate exception and is marked as one.** It is preserved across an
ingest, by the same mechanism `Queue.upsert` uses, because losing a date is cosmetic and
losing a card is not.

**AMENDED 2026-09-13 (`D193`): a second field is now carried over the same way, and "exactly one" below is corrected in place rather than left to contradict it.**
`buyer` — the display name a fetch already wrote — survives a paste that names no buyer,
because a paste's narrower shape must not erase a name the ledger already holds. Naming both
exceptions is what keeps the rule readable: two fields ride across an ingest untouched, and
each is one whose loss costs something a re-sync cannot recover — a date, or which person a
drawer walk is for.

### Ingest writes no card state and no listing count

**NOT `set_state`, NOT `Listing.bump`, NOT ONE BYTE OF `inventory.json`.** Pressing sync
twice is therefore a no-op **by construction** rather than by a guard somebody has to keep
true: `store/orders.py` holds no `Inventory` and imports nothing that does, so it cannot
reach a card. A ledger that moved a card to `sold` on ingest would re-sell every order in
the file on every sync, and a guard against that is one refactor from being wrong. Not
having the capability is not.

**And an unchanged re-ingest rewrites no bytes.** `changed_at` is stamped only where the
feed's content actually differs — T1's own rule for `harness/results/`, which does not
restamp `generated_at` on a cached re-scoring, for the reason that file gives: a one-line
diff on every run is how a real change stops being visible. There is deliberately no
`last_synced_at`, because when the sync ran is a property of the sync rather than of an
order, and storing it would defeat this paragraph to record something no reader needs.

**T7 asserts that as byte equality of three files, which is D54's LESSON APPLIED.** That
entry's guard read `len(rows) == 0` under the message "the file holds no zero row", and "the
file holds 0 rows" is satisfied **identically** by the emitter correctly omitting a row and
by the emitter overwriting two good rows with a bare header; the destruction lived behind it
for as long as it existed. So a second sync here must leave `orders.json`, `inventory.json`
**and** `history.jsonl` byte-for-byte as they were. A row count would go green on a ledger
that threw its fulfilment away and re-ingested the same order over the top.

### Fulfilment is a count, and the one identity it holds is a `capture_id`

**`LineProgress.fulfilled` is a number and is never a list of positions.** D10 ruling 1 lets
a junk capture be deleted from the middle of a box and slides every higher index down one, so
a position written down today names a different card tomorrow. A count survives that because
it names no slot, and it still tells a filled order from an unfillable one — which is the
only thing anybody asks of it.

**`LineProgress.copies` CARRIES `capture_id`s, THE ONE IDENTITY THIS MODULE HOLDS.**
It is minted once per `POST /capture`, it is unique store-wide
(`master.Inventory.card_by_capture_id` refuses a duplicate rather than picking one), and it
survives a renumber by construction: the shift rewrites `box` and `index` and the record keeps
its id. `server/capture_server.py:_drop_from_stores` exists precisely because the two queues
and the answer cache **are** position-keyed and must be remapped by hand at every delete;
a fourth store in that condition is a fourth thing to remember at three call sites, and this
one declines to be it.

**Measured in T7 rather than argued.** Five cards, two pulled at 3/2 and 3/3, then a real
`POST /inventory/3/1/remove`: both pulled copies slide down one, and
**position 3/3 now holds a card that was never pulled**. A ledger storing `["3/2", "3/3"]` ships
it. The case asserts both halves, because the first alone is satisfied by a ledger that
stores nothing at all.

**WHAT `capture_id` DOES NOT SURVIVE, named rather than left to be found: a re-shoot.**
`do_reshoot` requires the NEW photograph's id and writes it onto the record (D26), so a copy
re-shot after being pulled reads as one this ledger has never seen. It is not reachable
through any sequence that makes sense — a pulled copy is in the post and is not
re-photographed — and it is the honest limit on the paragraph above.

### No order state, and no history line

**Nothing is added to `master.STATES`, AND THE TRAP IS D26's EXACTLY.**
`server/capture_server.py:_state_before_sale` and `_state_before_retirement` scan
`history.jsonl` for the last event whose name is in that tuple, so a new member makes both
reversals restore a card to something that is not a state. That is why `removed` was renamed
`retired` on 2026-08-23, and this module stays on the other side of it by holding no states
at all. T7 ingests orders either side of a real sale and requires the reversal to still read
`identified` back out of the log.

**And it logs nothing to `history.jsonl`.** Two reasons, both load-bearing. A sync appending a
line per order would not be the no-op the section above promises, however small the line is.
And this module changes nothing about a card, so there is nothing for that log to describe —
when the pull route is built, **it** touches a card and **it** logs, through `Inventory._log`,
in the same locked session.

### The refusals, each of which is a different way to ship the wrong card

`record_pull` validates everything and then writes everything, which is D29's rule for the
group answer and for D29's reason: a refusal partway through would leave copies recorded
against a pull the operator was told had failed.

- **`CopyAlreadyPulled`** — this physical card is already recorded against another line. The
  thing this module exists to prevent, said out loud rather than counted twice.
- **`CopyNotIdentifiable`** — a copy carrying no `capture_id`. Refused rather than counted
  blind: without an identity the pull cannot be made idempotent, and a silent double-pull is
  the worst outcome this feature has. Every record on the owner's store carries one, so this
  guards a legacy card rather than a common path.
- **`OverFulfilled`** — more copies than the buyer ordered. Refused rather than clamped;
  you cannot ship the fourth, so there is nothing to be gained by hiding it.
  **`Ledger.over` exists anyway**, because a later ingest can REDUCE a quantity under a pull that was
  legitimate when it was made: refuse to create the state, tolerate and report it where it
  arises.
- **`DuplicateOrderLine`** — one order carrying two lines for one SKU. Fulfilment is keyed by
  SKU because that is the only line identity stable across two ingests — a line's POSITION in
  the list is whatever order the feed serialised it in — so two lines sharing a SKU make "how
  many of this have we pulled" a question with two answers.
  **Summing them was the alternative and is worse**: a merged line loses which one was filled.
- **`UnknownOrder` / `UnknownOrderLine`** — a pull against an order never ingested, or a SKU
  the buyer did not order.
- **`BadOrderKey`** — a source carrying the key separator, or an empty half. The key splits on
  the FIRST colon, so a source containing one makes two different orders share a record; an
  order NUMBER may contain one, and that asymmetry is what the refusal buys.

**The key folds case and strips to compare, and stores verbatim** — D20's rule for a box
name, one register over and for the same reason: `TCGplayer` and `tcgplayer` are one
marketplace to a person, and a normalized value written back is a value the operator cannot
correct.

### What it deliberately does not do

**Nothing clears an order.** No `drop`, no `release`. That is `store/queues.py`'s arrangement
for `store/queues.py`'s reason — the queues only grow, because a card in a queue is at a known
position in a box and is not lost — and a cancellation is not a deletion either: `status`
carries the feed's own word for it, verbatim and unvalidated. Deciding what "open" means from
a marketplace's status string is the guessing `CLAUDE.md` forbids, so `Ledger.unfulfilled`
answers the question this ledger actually owns — which orders still owe copies — out of its
own two halves, in the same sequence `pipeline/orders.py:order_sequence` serves them.

**It imports nothing from `pipeline/`, WHICH IS WHY `OrderLine` IS DECLARED TWICE.** The edge
runs the other way and `docs/map.py` records that `store/` imports nothing from `pipeline/`,
so reusing the resolver's frozen `OrderLine` would be a cycle. They are not redundant: the
same split `QueueEntry` has against `pipeline/join.py`'s carriers, for the same reasons — one
is a mutable dataclass that `asdict` round-trips and `__annotations__` filters, the other is a
frozen domain object whose `__post_init__` coerces the SKU. `kind` is carried verbatim and
validated nowhere here, because `pipeline/orders.py` owns `LINE_KINDS` and a second copy is
two lists nothing reconciles — the drift D16 exists to catch.

**AND `parse` FILTERS ON `__annotations__` AT ALL THREE LEVELS.** `store/master.py` records
what one missing filter costs: a field written but not declared is served, persisted, and
**silently dropped** on the next reload, so it looks live right up until the process restarts.
`OrderLine` and `LineProgress` are nested, so filtering only the record lets exactly that
through one level down.

**No address, no email — AND, AS OF 2026-09-13, A NAME.** The ledger holds a SKU, a quantity,
what the feed called the card and, since `D193`, the buyer's display
name: an owner ruling that a hand walking drawers per person needs a name to walk by, over a
session's earlier design that excluded it with the rest. `inventory/` being gitignored whole
is a reason to keep bearer instruments and postal addresses out of a commit
(`store/files.py`'s code ledger); it was never a license to keep a name out too, and it still
is not a license to add anything past a name — address, email, payment and the transaction
breakdown stay excluded, at the same allowlists, for the same reason.

**It does no i/o and holds no lock.** Like `queues.py` it is a data structure; `session.py`
reads it and writes it back inside the lock it already holds. `files.exclusive` polls at 50ms
and gives up at 30s while the feeder captures a card every 623ms, so a module down here that
fetched an order feed would stall real capture — the fetch belongs to the caller, ABOVE the
lock, and `ingest` takes records already in memory. T7 asserts that as an import check rather
than behaviourally, because a behavioural test would have to hang in order to fail.

### What it costs: a fifth file in a set that is not atomic

**`Store.write()` replaces four JSON files in sequence and the set is not one transaction.**
**This is a fifth, and it widens that window by a fifth.** Said here rather than discovered
later. Each file is atomic alone — `files.write_atomic` stages beside the target and
`os.replace`s — and nothing makes the set atomic, so a kill between two calls leaves the store
internally inconsistent. The exposure is live at Ctrl-C frequency rather than theoretical,
which is why D53's supervisor drains in-flight requests before restarting a child, and it is
why the Someday list refuses to put this store on a NAS.

**The only mitigation is an ORDERING, and it is a preference among losses rather than a fix.**
The ledger is written LAST, so a torn write loses the order feed — which can simply be
ingested again, this entry's whole second section being that re-ingesting is free — rather
than the inventory, which names photographs nothing can regenerate. Closing it properly means
one transaction over all five: a staged directory swapped by a single `os.replace`, or a real
embedded store. Neither has been argued, and this entry is not the place to argue it.

### It is RECORDED, not BUILT

**Nothing calls `store/orders.py`. No route serves it, and no screen draws it.**
`CLAUDE.md`'s rule is that a wrap-up claiming BUILT for something unreachable is
wrong rather than merely incomplete, so this entry does not claim it. What is genuinely built
is a store module and its coverage; what is genuinely done is this decision. The precedent is
`pipeline/pricehistory.py`, which the Someday list records the same way and in the same words,
and `pipeline/orders.py` itself, which is reachable only from `cli/resolve.py`'s imports.

**The unfinished part of this same task, named as such rather than as a follow-up**: a route
that ingests a feed, a client function in `app/src/server.ts`, and a control on a screen. Until
those exist there is no order flow — there is a ledger that would hold one.

**What would reopen this: a feed that reorders or re-keys its lines.** Everything above rests
on the SKU being the stable per-line identity across two ingests, which `DuplicateOrderLine`
enforces at the boundary. A marketplace that issues its own per-line id would be a better key,
and adopting one is a schema change plus a migration for every record already written — worth
taking if a real feed offers it, and not worth inventing before one does.

---
