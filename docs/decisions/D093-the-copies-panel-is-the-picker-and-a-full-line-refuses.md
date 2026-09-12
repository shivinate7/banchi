## D93 — The copies panel is the picker, and a full line refuses the take

**Which copies of a line go in the envelope is CHOSEN off the copies panel, one press per copy, in any box.** Built 2026-09-02 on the owner's complaint: *"When I have an order of 2 cards and I have inventory for 3, I basically should be able to pick which two I sell, instead currently it's like predetermined, and using the 'take this one instead' system is not intuitive it should be done differently."*

**This is D90's own third reopening condition, taken.** That entry closed with *"`SearchCopy` gaining a `capture_id`. Today a copy is swapped in only by walking to it, because the aim needs an id the search rows do not carry. If they carried one, an unpicked copy could be taken straight off the panel without the walk moving — worth arguing rather than taking, because the walk-to IS the flow: you look at the card before you swap it in."* The argument came back the other way from the person doing the walking, and the flow it defended is what they called unintuitive.

### What was actually in the way, and it was one field

**`resolve_all` decides which copies fill a line before anybody reaches a drawer, and that half is right and unchanged.** It allocates over the WHOLE open set in one pass so two envelopes cannot name one card, and the operator wanting a different copy of the same SKU is not a defect in that allocation — it is a fact about which cards are in their hand.

**What made the correction awkward was that a copy could not be AIMED at.** Every write in the walk aims by `capture_id`, checked against the card actually at the slot (`capture_id_mismatch`, D90) — and `GET /search` did not send one, so the only aimable copies were the resolver's own picks and whichever card the walk was standing on. Hence the two-press errand the owner objected to: walk to the copy, then press `Take this one instead`, which replaced the stop's first target one copy at a time.

**The carve-out this reopens is narrower than it read.** `app/src/types.ts:SearchCopy` refused `confidence` and `capture_id` together, to stop *"a second inventory view growing inside a search result"*. That rule stands for the metadata; it never had an argument about the identity. **An identity is not a view.** `_copy_row` sends `capture_id` now, null on a record written before ids were kept — and a copy carrying null says `no capture id` where its control would be, rather than offering a press the server would refuse.

### A full line refuses the take, and the ring was the alternative

**Told that the panel would be the picker, the owner was asked what a third tap should do when the line already has the two copies it is owed, and chose the refusal.** At `2 of 2` every other row draws the count where its control would be; dropping one is what makes room.

**The alternative was a ring, and it is the one this build would have shipped unasked.** Tapping a third copy would drop the longest-standing take — one press per correction, and because the resolver's picks are always the oldest members, tapping exactly the copies in your hand converges on exactly those. It was declined on the property that makes it convenient: **nothing may leave the envelope on a press aimed at something else.** A row that un-takes itself because a different row was pressed is a change the finger did not make, to a list whose whole job is to say what is in the operator's hand.

**What it costs is the second press, and it is named rather than hidden.** A swap is `Don't take` then `Take`, and the panel says so in one sentence.

### One map, not two, and an empty list is an answer

**`retargets` and `excluded` collapse into `chosen`.** They existed because the gesture was a CORRECTION: a replacement list for the copy swapped in, and a set of capture ids the operator had said were not in the drawer. A picker has one fact per stop — the copies taken — so there is one map, keyed by stop, and `targetsOf` reads it with `??` rather than `||`: a stop the operator has emptied stays empty instead of falling back to the picks it was seeded from. *"None of these"* is a thing that can now be said.

**The vocabulary follows the gesture.** `taking` in ink and `not taking` in muted, `Take` and `Don't take` on the rows, `2 of 2 taken` where a full line refuses, and `take 2 of 2` on the banner — a bare numerator answered "is this line full" only for somebody who remembered what the buyer asked for. `Not here`, `Back in` and `taken instead` are gone.

### The walk follows a drop and not a take

**Taking a copy appends it, so the walk stands still.** The landing is the stop's first target; a copy pushed to the FRONT — which is what the swap did, deliberately, so the stop followed the operator to the drawer they had walked to — would now jump the screen to whatever row was just ticked, and under the refusal above a swap is two presses, so it would move the walk twice for one correction.

**Dropping the copy the walk is standing on DOES move it**, to the next copy the envelope is taking, in another box if that is where it is. That is the errand D90 built the landing for, and it is the half worth keeping: the walk goes where the cards are, not where the taps are.

### The two shortfalls survive, and the order of derivation is what keeps them honest

**`short` is copies the resolver never found and `not taken` is copies it found that the operator has not put in the envelope** — the ledger's problem and the shelf's, and one number covering both sends a person to the wrong place. `Stop.available` is the count of aimable picks; what is missing is `owed - take`; as much of that as a pick could still answer for is `not taken`, and the rest is `short`.

**Derived in that order rather than as two independent counts, which is what stops them double-counting.** A copy taken that the resolver never offered — a free copy in another drawer — closes the gap rather than being counted against it, and the old subtraction (`all picks` minus `kept picks`) could not express that at all, because a hand-taken copy was not in either list.

### What did not move

**The resolver's picks are still the default, and that is what keeps the common case free.** A line owed two with two copies on the shelf is zero presses; the picker costs a press only where the operator has an opinion about which copies. Nothing about the envelope moved either: one press per order, one transaction, `Mark sold` hidden on every row while an order drives (D90's seam), `Retire` still offered.

**A copy another stop has been allocated is still refused, and still by the allocation rather than by the drawer** (D7, and the owner's *"You're giving boxes too much independence"*). The mark says `for order N` beside the missing control. A pooled copy (D24) is refused too: it is a count rather than a location, so there is no slot for the aim check to check against.

### What it costs

**The choice is still this screen's and this session's.** `chosen` is React state; a reload drops it and the envelope falls back to the resolver's picks with nothing on screen saying it changed. That is D90's cost unchanged, and the case for storing it is no stronger now — a take is a statement about the next press, not a fact about the store.

**A line the resolver could not answer at all is still not walkable.** `stopsOf` keeps a line with no aimable pick out of the queue, so the picker cannot be used to fill one by hand. No reachable gap follows from it today — the copies that would fill such a line are pooled, id-less, or held by another order, and all three are refused on their own terms — but the queue's membership is now decided by a narrower question than the panel can answer.

**The take is per stop, and the panel draws one SKU.** In wave mode each stop keeps its own list, which is right; what it means is that no screen shows the whole envelope's copies at once, and the banner's counts are what stands in.

**And it is still built over an ingest no real order has been through.** D90's table is unchanged: 0 orders in the ledger, 0 copies ever recorded as pulled for one. Every guarantee here is proven by `app/tests/order-walk.spec.ts` and by nothing that has held a buyer's money.

**What would reopen this.** *A second pair of hands*, exactly as D90 has it — two people walking one wave each hold a `chosen` the other has already spent. *A line the resolver answered short while a copy sat takeable in the panel*, which would mean the queue's membership test and the picker disagree about what is fillable. *A tap that costs a card* — the refusal above is a bet that a change the finger did not make is worse than a second press, and the measurement that settles it is an operator swapping copies at a real drawer.

---
