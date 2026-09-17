## D212 — Every copy is fungible, so no order claims one, and the write is the only refusal left

**The owner, 2026-09-16, on why two open orders for one SKU should both be offered it.** Every card is fungible. Nothing should claim one or take priority over another order. The owner had already agreed to this for the order walk. A person sees every copy of a card and is free to pick any one. Mid-review, the owner widened the ruling to the walk itself, asking why it showed only one instance of a card the store held many of. Landed in `10d5e6fc`, alongside two unrelated fixes to the same screen. This entry covers only the claim removal.

### What existed, and what it was for

`pipeline/orders.py:_Draw._taken` was a set of identities. `resolve_all` drew it down once, across a single pass over every open order. The first order to reach a SKU took up to `line.quantity` copies. Those copies then vanished from what any later order in the sequence could see. `order_sequence`'s oldest-first ordering existed only to make that draw deterministic. The same store, resolved twice, allocated the same copies to the same orders both times.

### The ruling removes the premise D113's exclusion stood on

D113 (a line closes three ways, and only one of them claims a copy went) found already-shipped orders drawing ahead of live ones. Being older, they took the first crack at a shared pool. 31 physical copies went to orders that had already shipped, while `Ready to Ship` lines beside them read `short` over the same cards sitting in the box. D113's fix excluded terminal-status orders from the resolution pool. Its own words: *"a shipped order, being older, took a copy ahead of a live one"* — a sentence about priority in a shared, exclusive pool.

With `_taken` gone, there is no pool to be ahead in. Nothing an order draws is withheld from any other order. A terminal order sitting in the resolution can no longer take a copy a live one needed, because nothing is taken. The harm the exclusion prevented cannot happen now, by construction, not by keeping the excluded order out of the room. So the exclusion has no premise left. Both call sites now resolve every order still owing copies, terminal or not.

This is CLAUDE.md's own procedure for a rotted premise, run against a decision three weeks old. Name the entry. Name the sentence. Say which part of the argument is gone. Replace the mechanism rather than repeal the rule around it.

**What survives from D113 untouched.** The three-way table (`record_pull` / `record_fill` / `close_line`), which write claims a copy went. `is_terminal_status`, deciding what `open_keys` on the wire means. The vocabulary itself — `open` and `terminal` did not change, and a terminal order still draws as Done. Only the resolution's *exclusion* of a terminal-but-owing order is gone. A walkable body is now decided by `ownsAWalkableBody`, in `app/src/Orders.tsx` — a file this entry reports on rather than edits. It reads `order.open`, or `order.terminal` together with `order.wanted > order.recorded`.

### D174 is a different claim on a different thing, unamended

D174 (a press claims the cards it is about to buy) protects a dollar spent on identification. Its `submissions` row covers the position keys an `identify` press is about to pay Anthropic to read. It refuses on intersection, so two presses cannot both bill for one card. Nothing about it is an order-fulfilment claim. `10d5e6fc` touches neither `store/submissions.py` nor `cli/cmd_identify.py`. Its whole argument is a check-then-write race over money already about to be spent. A resolver that spends nothing and stores nothing has no analogue to race. **Concluded: D174 is untouched. This entry does not amend it.**

### D93 and D97 already said this, one register up

D93 (the copies panel is the picker) put the inventory side of a line in the operator's hand. Every copy the store holds of a SKU is drawn. None is preselected. None is hidden. Its own words: *"the machine ranks, the person reaches."* D97 (the copy map ranks and never picks) applies the same rule to the order side. A line's map is a recommendation over every copy the store holds, never an allocation.

`10d5e6fc` brings the resolver itself into agreement with a rule its own screen already enforced around it. `picks` is no longer capped at `line.quantity`. It is no longer drawn from a pool other lines have already depleted. It is every candidate `_Draw.available` offers, the same list D97's map already reads from. D97 named this exact reopening condition directly. A real double-take against the ledger would turn the map's mark into a refusal, taking D93's own shape. That refusal already exists — see below. This entry is D93 and D97 reaching the resolver, not a new rule.

### Where the safety actually lives, and always did

The write-time refusal was never `_taken`. `store/orders.py:record_pull` raises `CopyAlreadyPulled` against the ledger's own recorded pulls, independent of anything `pipeline/orders.py` computes. `_taken` only stopped the resolver from offering the same copy twice inside one preview pass. It never touched a copy pulled by hand between two resolutions. `record_pull`'s refusal had to exist regardless.

Removing `_taken` removes a second, redundant gate over the same act. Offering one copy to two orders in a preview is now permitted, on purpose. The operator's hand at the shelf decides which order actually gets it, and `record_pull` guards that moment. T7 (`harness/tests/t7_store_and_seams.py`) now asserts the refusal directly against the same physical copy offered to two orders by one pass.

### What was given up, plainly

`short` used to cover two cases. A genuine shortfall, and copies that exist but were spoken for by an earlier order in the pass. It now means only the first — the store holds fewer copies than the line wants, full stop. Two orders can both read `Ready` against the same physical card. The actual shortfall surfaces at the shelf, on whichever order's pull loses to `CopyAlreadyPulled`. The owner was offered an alternative. A contention warning would flag a line whose copies are also claimed by another open order. The owner declined it for the simpler rule: nothing is withheld, the write refuses.

### The measurements

- The owner's real store: 804 orders, 40 open, 250 terminal, of which **235 are terminal and still owe copies**. Every one of those was unwalkable before this.
- Of 68 lines resolved on the real store under the old exclusive draw, **2** were denied an on-hand copy purely by draw order. Smaller than 2026-09-06's 31. Most of that backlog had since been stood down or shipped through.
- Seeded store: resolved orders 17 → 28 of 28. Lines reading `short` while copies sat on hand, **26 → 0**. Total picks offered, 21 → 84.
- **The cost.** `GET /orders` measured 54–98ms before this. It measures **520–580ms** after, on a copy of the real store. 40 resolutions became 260. Every order is resolved now, not only the open ones. Every line carries every candidate copy now, rather than up to `quantity` of them. Profiled: 52% of the added time is repeated `join.layout` label work, recomputed per candidate. A follow-up to resolve per order rather than the whole ledger on every fetch is in flight. This entry does not build that follow-up. The follow-up's own entry should cite this one. It should say why the request got five times slower on the day it got correct.

### What would reopen this

The owner might find real shortfalls at the shelf often enough that the contention warning declined here starts looking cheap. It would beat a walk to an empty slot. A second operator is the sharper case. Two hands pulling from the same drawers at once changes the shape of the risk. Offering one card to any number of orders, and letting the write sort it out, is safe for one hand. It is not as safe for two. A second hand does not learn `CopyAlreadyPulled` failed until after walking to the wrong box.
