## D147 — The claim is spent on the oldest copies, because a card captured tonight was in no file sent last week

**When the store says TCGplayer holds N copies of a SKU, the N positions that stand for them are the N OLDEST CAPTURES.** Built 2026-09-11, from the operator's report that an emit was *"showing several items from my run already at quantity 0, as though they're already listed, that's just not true/possible"*.

### The expression, and the sentence that hid it

`cli/resolve.py:_committed_keys` turns a per-SKU quantity into a set of positions — the store counts copies, `SkuMatch.committed_positions` needs addresses — and it picked with `inventory.copies_on_hand(sku)[:out]`. That list is **box-walk order** (`store/master.py`), so the lowest box number goes first.

Its docstring justified the arbitrary pick like this: *"the only thing the join does with them is `len()` and a set subtraction. Any N of them would do — that is the fungibility ruling."*

**The `len()` is true and the set subtraction is not.** `SkuMatch.uncommitted_positions` subtracts those keys from **one run's** positions, so which copies are chosen decides **which run may list**. D7's fungibility ruling is about physical cardboard and is untouched — any three of fifteen identical copies really are the three that are live — but it says nothing about which run gets to send one, and this function read it as though it did. That false sentence is why the defect was invisible for as long as it was: it told every reader there was nothing here to get wrong.

### What it cost, on the operator's own store

Their backstock is **box 3**; tonight's capture is **box 1**. Box 1 sorts first, so the copies photographed an hour ago were marked as the ones TCGplayer already holds, and the older backstock — which no run is joining — was left uncommitted and therefore reachable by nobody.

Run `2026-09-11-box1-01`, 322 cards, joined against its own fetched export:

| | before | after |
|---|---|---|
| rows `emit` would write | 196 | **241** |
| copies `emit` would send | 260 | **315** |
| matched SKUs adding nothing | **52** | 7 |

**59 real cards were stranded across those 52 SKUs**, every one reported as *"every copy in this run is already listed or has left the box"* — the sentence the operator correctly called impossible. **52 of the 59 are this defect.** The other seven are the stuck claim below.

Worked example, sku 9027355 (Switcheroo): `copies_out` 4, eleven copies on hand, committed set `1/39, 3/429, 3/440, 3/443`. The run's only copy was `1/39`; three box-3 copies stayed free and unreachable.

**A further 3 copies came back on 3 SKUs that were not at zero but were under-offering**, for the same reason one register down — a run copy committed while a backstock copy went free. 55 copies in all, of which 52 are the SKUs that offered nothing.

### Why capture time, and not something tidier

**A copy captured after the last emit cannot be among the copies that emit sent.** `cli/cmd_emit.py` walks the run's own `uncommitted_positions`, a run covers cards photographed at one sitting, and cards photographed tonight were in no file written last week. The store cannot NAME the copy that backs a listing — D7 rules copies fungible and nothing records it, and D59 records the marker that would make it exact as *"available rather than owed"* — so this is an inference. It is the only one causality permits.

**A copy with no `captured_at` sorts oldest**, which is the conservative direction: committing it withholds it from this press rather than sending it, and D7's estimate errs low. It also makes the function identical to the old box-walk slice on a store where no record carries a stamp — the empty string ties every key and `(box, index)` decides — so a store written before the field existed behaves exactly as it did.

**`Inventory.copies_on_hand` keeps box-walk order and was not touched.** `pipeline/orders.py` hands that list to the fulfiller and the box walk is the order a hand moves through a drawer; re-ordering the store method would have changed which copy a pull sends somebody to, which is not this defect. The ordering is local to the one caller that needs the other question answered.

**`Listing.at` is not a push time and could not be used.** It is the touch stamp, written by every writer of every field — its own comment says so, and says why it must not be overloaded. There is no stamp recording when a claim was sent, so the ordering is what stands in for one.

### What was refused: preferring copies outside the run being emitted

It is the obvious repair and it over-sends. It makes the committed set a function of which run is emitting, so two runs holding one SKU each exclude themselves and the same claimed copies are subtracted from neither — **a global quantity answered by a run-scoped view, which is D59's defect exactly**.

Measured on the same store: **83 copies across 61 SKUs offered past what exists to offer.** That is the same register as the reconcile-forward projection D59 itself published (78 rows across 61 SKUs), which is unsurprising, because it is the same arithmetic failing the same way.

### It is NOT D7's send quantity, which is what the operator first suspected

They asked whether this was the `--quantity` control amended into D7 the same day. **It is not, and the reason is checkable rather than a matter of judgement**: no quantity was typed on that press, so `SkuMatch.asked` is `None` and `add_to_quantity` returns `room` unchanged — the `min(asked, room)` arm is not reached at all. `--cap` is likewise absent, so `room` is `len(uncommitted_positions)` with no ceiling term. Both per-send controls were inert on the press that produced the report; what was wrong was which positions `uncommitted_positions` had left to count.

### What this does NOT fix

**Seven SKUs still add nothing, and they are a different defect: a claim `_copies_out` cannot age.** `pushed` is stuck, the copies actually sent have SOLD, and `_copies_out` only ages a claim the export corroborates — with `Total Quantity` at 0 the gate is off, so the claim still covers the whole shelf. No ordering can reach them: `copies_out >= len(copies_on_hand)` for all seven, so every copy is committed whichever ones are picked.

That guard is load-bearing, not defensive — D59 records that dropping it takes `check_listing_commands`' re-emit idempotence case red — and separating a Staged copy pulled by hand from a Live copy that sold needs information this pipeline does not have. **Recorded as DEBT24 with the measurement, rather than half-fixed.** *(Fixed the next day by `D150`: the export answers a second question, and all seven are offered. The measurement above is what this branch left and is not rewritten.)*

**Their report sentence is still wrong and is deliberately not patched.** *(It went with the arithmetic — it was false because the arithmetic was.)* Those seven go on printing *"every copy in this run is already listed or has left the box"*, which is false about the run's copy. `SkuMatch` cannot tell them from an ordinary un-reconciled re-emit — both read `pending = copies_out - live_now` with `live_now` at zero — so a true sentence needs the sold count threaded onto the match, which is new surface area on the wire for a figure nothing else reads. It belongs with the arithmetic fix, and §24 carries both.

### What would reopen this

**A marker that a copy actually reached an import file.** D59 names it — one field on `Card`, written by `cmd_emit`'s push loop beside the `sku` stamp. With it, the committed set is READ rather than inferred and this ordering becomes a fallback for records written before it. It is worth more now than when D59 recorded it, because this entry is the second defect to turn on not having it.

**A run over more than one box** (D48). The argument here is about capture time and not about boxes, so it survives — but the fixture that guards it would need a shape where one run spans two sittings.