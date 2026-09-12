## D-the-first-photograph-is-the-name — A card's name is the first photograph of it, frozen at issue

**A card's stable identity is the sha256 of the photograph the store held when the id was issued — read off the disk, frozen from that moment, never recomputed.** SPECIFIED 2026-09-12, NOT BUILT. `docs/specs/stable-card-id.md` is the plan, its measurements and its receipts; this entry is the ruling and the four alternatives it rejects.

It is a birth certificate rather than a live content address, and it is the only candidate identity in this store that can be re-checked against 4.45 GB of photographs that cannot be re-taken. It arrives as `cards.cid`, BESIDE `cards.key` and not instead of it: `store/master.py`'s `position_key` stays, `"<box>/<index>"` stays the primary key of `identifications`, `queues` and `events.position`, and `Box 3 · Section 2 · Card 17` — the instruction to a hand at a drawer — is untouched.

### The deciding measurement

**2,535 of 2,535 stored digests equal the photograph on disk. 0 disagreements, 0 missing files, 0 photographs claimed by no card, 2,535 distinct digests among 4,445,351,065 bytes, 0 duplicates.** The whole corpus hashes in **2.68 s**. So the id is not invented, allocated or guessed — it is READ, and the reading is re-runnable by anybody on any copy forever, with no external state.

**The production receipt that a content id beats a positional one is already in this repo, and it is D36's.** Across 13 run directories, 3,728 records, all carrying `photo_sha256`: **701 of them bind by digest to a different position key than the one they name** — 537 of 544 on one run, 99 crossing box 1 to box 3, 65 crossing box 6 to box 3 — plus 88 whose photograph is gone. `realign` exists because the position was the name. This decision is that measurement applied at the source, and it neither deletes nor demotes that repair layer: a cid cannot reach backwards into an immutable file written before it existed.

### Frozen, not tracked — and the four shapes

**`cid` is issued once and never recomputed, and that single word is what makes it survive a D26 re-shoot, a D89 reclaim, a D83 move, a mid-box renumber and a box deletion.** It is NOT a copy of the current photograph's digest; that field already exists (`Card.photo_sha256`, D89) and keeps its narrow job. Four shapes, all named, none NULL, with the population measured today:

| shape | means | on this store |
|---|---|---|
| `<64 hex>` | named by the photograph the store held at issue | **2,535** |
| `<64 hex>-<n>` | the nth card whose bytes are identical to an earlier card's | **0** |
| `moved:<64 hex…>` | the tombstone a moved card left behind | **0** |
| `nophoto:<box>/<index>@<captured_at>` | a card with no photograph and no digest anywhere | **0** |

**THREE OF THE FOUR HAVE NEVER FIRED, AND THAT IS STATED RATHER THAN GLOSSED.** Every card on this store is named from its own bytes. The other three shapes exist for populations that are empty today and will not always be — a reclaimed card, a duplicate photograph, a card whose photograph has vanished — which is why the spec's self-test must PROVOKE each of them instead of asserting over zero firings.

**A NULL is never one of the four.** A NULL here cannot distinguish *"no photograph was found"* from *"this migration did not look"*, which is this repo's signature defect stated verbatim.

**D89 is narrowed, not repealed.** Its clause — that the digest is `None` while the file exists, *"because while the file exists the file is the fact"* — holds for a field that TRACKS THE CURRENT PHOTOGRAPH, which is precisely the job `cid` must not take. Measured: **0 of 2,535 live cards carry `photo_sha256` or `photo_reclaimed_at`** — all 34 such records were buried with boxes 1 and 6 on 2026-09-11 — so that clause currently describes a population of zero, and the field's surviving job is the digest of the photograph that was RECLAIMED.

### The four rejected alternatives, each with the measurement that killed it

**`capture_id` — REJECTED because it is a photograph's identity, not a card's.** It is present and distinct on 2,535 of 2,535 cards and the order ledger already references copies by it, which is why it looks right. But `do_reshoot` OVERWRITES it, eleven lines below a docstring saying nothing about the card moves; `move_card` CLEARS it on the tombstone, its own docstring giving the reason — *"the photograph, not the vacated slot, is what the id anchors"*; and the column is not UNIQUE. **Measured: 3 of 82 `fulfilment` copy references already dangle**, all three traced to `buried` events, and `Ledger.holder_of` simply answers `None`.

**A never-reused integer from a high-water mark — REJECTED on a measured failure mode neither prior design found.** Two probes, both on copies. **First: a build that does not declare the column strips it on any ordinary write, silently.** 2,535 ids planted, the copy stamped forward, one ordinary state write run under today's build — and the row came back with the column NULL and the payload key gone. 2535 → 2534, no error, and a UNIQUE index does not object because SQLite NULLs are never duplicates. **There are 27 worktrees on this machine right now, every one a pre-guard build.** **Second: under a digest the next migration re-run HEALS that; under an integer it orphans.** Measured — a stripped row's id came back byte-identical, and the re-run issued exactly 3 ids for the 3 stripped rows and 0 for the other 2,532. An allocator would have handed a fresh number and left every reference to the old one pointing at nothing, reporting success both times.

**That self-heal is the whole argument against an allocator**, and it is what makes the reverse safe rather than a wart: re-applying the migration produces the identical ids, where a reverse-and-reapply under an allocator would renumber the store.

**A replay-derived occupancy integer — REJECTED because the algorithm is under-specified in a way no gate can see.** Three independent implementations of the same described replay produced mis-bind rates of **22.3%, 31.3% and 32.8%** against the naive key join, and **every row receives a non-NULL value under all three** — so a count of rows carrying a value cannot tell a correct replay from a wrong one. The correct algorithm exists on paper; it is a later decision, it needs its own measurements, and it may never be worth its risk.

**A server-minted UUID4 — REJECTED for the integer's reason plus one more: it is not derivable, so there is no second source to reconcile it against, ever.**

**And the position key with the box removed — a store-wide running index — REJECTED because it invites being read as an address**, which this repo has already paid for: 291 of 565 queue rows carry a stored label that disagrees with today's rendering.

### What follows from it

**The name is additive and the reverse is byte-exact.** The seeding is one `BEGIN IMMEDIATE` over row writes only, measured at 3.0 s including the hash; the reverse restores all nine tables byte-identically in 0.033 s, leaving an empty nullable column no reader can see. Killed with `-9` mid-transaction, the store comes back unchanged and the recovery procedure is nothing — the next read runs it again. The operation touches no file outside the database: **zero renames, zero unlinks, zero writes outside SQLite**, which is what prices it and what means there is no second half whose ordering against the commit has to be argued.

**The reverse is for a store you are about to open with an OLDER checkout, and the receipt must say so in those words** — on a build that still declares the field, the next read names every card again.

**WHAT THIS DOES NOT BUY IS NAMED RATHER THAN ROUNDED UP.** It takes the box out of the card's NAME and not out of its KEY, the cache's key, the queues' key, `events.position`, the photo path, the sidecar or the ten route regexes. The move is still a tombstone plus hand-moved copies and the renumber is still 1,608 filesystem operations. What changes is that each of those becomes a mechanical follow-through over a name that cannot move, instead of a re-key nobody can safely attempt. The four follow-ons are named in the spec: the batch `custom_id`, the `identifications` re-key, the order-ledger repair, and the key itself.

---
