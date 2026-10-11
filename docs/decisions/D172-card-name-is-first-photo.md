## D172 — A card's name is its first photograph

**A card's stable identity is the sha256 of the photograph the store held when the id was issued.** The digest is read off the disk and frozen from that moment. It is never recomputed. The photograph is stored under this name now (D183). `docs/specs/stable-card-id.md` holds the plan, the measurements and the receipts. The current scope is in its §0.

It is a birth certificate, not a live content address. It is the only candidate identity in this store that can be re-checked against 4.45 GB of photographs that cannot be re-taken. It arrives as `cards.cid`, beside `cards.key`, not instead of it. `store/master.py`'s `position_key` stays. `"<box>/<index>"` stays the primary key of `identifications`, `queues` and `events.position`. The instruction to a hand at a drawer, `Box 3 · Section 2 · Card 17`, is unchanged.

### The deciding measurement

**2,535 of 2,535 stored digests equal the photograph on disk.** There were 0 disagreements, 0 missing files, and 0 photographs claimed by no card. The 2,535 digests are all distinct, among 4,445,351,065 bytes, with 0 duplicates. The whole corpus hashes in **2.68 s**. So the id is not invented, allocated or guessed. It is read, and anyone can re-run the reading on any copy, at any time, with no external state.

**The production receipt that a content id beats a positional one is already in this repo, in D36.** Across 13 run directories and 3,728 records, all carrying `photo_sha256`, **701 bind by digest to a different position key than the one they name**. That is 537 of 544 on one run, 99 crossing from box 1 to box 3, and 65 crossing from box 6 to box 3. Another 88 have a photograph that is gone. `realign` exists because the position was the name. This decision applies that measurement at the source. It does not delete or demote the repair layer. A cid cannot reach back into an immutable file written before it existed.

### Frozen, not tracked, and the four shapes

**`cid` is issued once and never recomputed.** That single word is what lets it survive a D26 re-shoot, a D89 reclaim, a D83 move, a mid-box renumber and a box deletion. It is not a copy of the current photograph's digest. That field already exists (`Card.photo_sha256`, D89) and keeps its narrow job. Four shapes are named, none is NULL, and the population is measured today:

| shape | means | on this store |
|---|---|---|
| `<64 hex>` | named by the photograph the store held at issue | **2,535** |
| `<64 hex>-<n>` | the nth card whose bytes are identical to an earlier card's | **0** |
| `moved:<64 hex…>` | the tombstone a moved card left behind | **0** |
| `nophoto:<box>/<index>@<captured_at>` | a card with no photograph and no digest anywhere | **0** |

**Three of the four have never fired, and that is stated, not glossed.** Every card on this store is named from its own bytes. The other three shapes exist for populations that are empty today and will not always be. Those are a reclaimed card, a duplicate photograph, and a card whose photograph has vanished. So the spec's self-test must provoke each of them. It must not assert over zero firings.

**A NULL is never one of the four.** A NULL cannot tell "no photograph was found" from "this migration did not look". That is this repo's signature defect, stated plainly.

**D89 is narrowed, not repealed.** D89's clause says the digest is `None` while the file exists, "because while the file exists the file is the fact." That holds for a field that tracks the current photograph. That is exactly the job `cid` must not take. Measured: 0 of 2,535 live cards carry `photo_sha256` or `photo_reclaimed_at`. All 34 such records were buried with boxes 1 and 6. So that clause applies to zero cards today. The field's surviving job is the digest of the photograph that was reclaimed.

### The four rejected alternatives

**`capture_id` is rejected, because it is a photograph's identity, not a card's.** It is present and distinct on all 2,535 cards. The order ledger already references copies by it, which is why it looks right. But `do_reshoot` overwrites it. `move_card` clears it on the tombstone, and that docstring gives the reason: "the photograph, not the vacated slot, is what the id anchors." The column also lacks a UNIQUE constraint. **Measured: 3 of 82 `fulfilment` copy references already dangle.** All three trace to `buried` events, and `Ledger.holder_of` answers `None` for them.

**A never-reused integer from a high-water mark is rejected, on a failure mode that neither earlier design found.** Two probes ran, both on copies. **First, a build that does not declare the column strips it on any ordinary write, silently.** The probe planted 2,535 ids and stamped the copy forward. One ordinary state write ran under today's build. The row came back with the column NULL and the payload key gone. The count fell from 2,535 to 2,534, with no error. A UNIQUE index does not object, because SQLite never treats NULLs as duplicates. There are 27 worktrees on this machine right now, and every one is a pre-guard build. **Second, under a digest the next migration re-run heals the loss. Under an integer it orphans the id.** The stripped row's id came back byte-identical. The re-run issued exactly 3 ids for the 3 stripped rows, and 0 for the other 2,532. An allocator would have handed out a fresh number. Every reference to the old one would then point at nothing, and both runs would report success.

**That self-heal is the whole argument against an allocator.** It is what makes the reverse safe. Re-applying the migration produces the identical ids. A reverse-and-reapply under an allocator would renumber the store.

**A replay-derived occupancy integer is rejected, because its algorithm is under-specified in a way no gate can see.** Three independent implementations of the same described replay gave mis-bind rates of **22.3%, 31.3% and 32.8%** against the naive key join. Every row received a non-NULL value under all three. So a count of rows carrying a value cannot tell a correct replay from a wrong one. The correct algorithm exists on paper. It is a later decision, it needs its own measurements, and it may never be worth its risk.

**A server-minted UUID4 is rejected, for the integer's reason plus one more.** It is not derivable, so there is no second source to reconcile it against, ever.

**The position key with the box removed, a store-wide running index, is rejected.** It invites being read as an address. This repo has already paid for that: 291 of 565 queue rows carry a stored label that disagrees with today's rendering.

### What follows from it

**The name is additive, and the reverse is byte-exact.** The seeding is one `BEGIN IMMEDIATE` over row writes only. It takes 3.0 s, including the hash. The reverse restores all nine tables byte-identically in 0.033 s, and leaves an empty nullable column that no reader can see. If the process is killed with `-9` mid-transaction, the store comes back unchanged. The recovery procedure is nothing. The next read runs the operation again. The seeding touches no file outside the database: zero renames, zero unlinks, zero writes outside SQLite. That keeps it cheap, and it means that no second half needs its ordering against the commit argued.

**The reverse is for a store you are about to open with an OLDER checkout.** The receipt must say so in those words. On a build that still declares the field, the next read names every card again.

**What this does not buy, named rather than rounded up.** It takes the box out of the card's name, not out of its key. The cache's key, the queues' key, `events.position`, the photo path, the sidecar and the ten route regexes are unchanged. The move is still a tombstone plus hand-moved copies, and the renumber is still 1,608 filesystem operations. What changes is that each of those becomes a mechanical follow-through over a name that cannot move. Before, each was a re-key nobody could safely attempt. The four follow-ons are named in the spec: the batch `custom_id`, the `identifications` re-key, the order-ledger repair, and the key itself.

**Re-scope.** This entry was re-scoped on the day it landed, and the re-scope has its own entry. Everything above stands: the name, the four shapes, the frozen-not-tracked distinction, the four rejected alternatives, and every measurement. What the owner rejected was stopping at the name. That left the photograph filed under the address, so the 1,608 filesystem operations stayed. **The photograph is stored under this name now.** That retires the work instead of pricing it. See D183 and `docs/specs/stable-card-id.md` §0. Two paragraphs above would otherwise read as the final scope. One is "The name is additive". It no longer confines the operation to the database. The other is "What this does not buy".
