# D181 — Order is taken once; a sale keeps it

**Ruling: `#/inventory` holds the order still under a search. A sale does not re-rank the list. A press retakes the order.** The ranking is right. Only its timing is wrong. The list is recomputed from the copies still on hand. Marking one copy sold re-ranks the list the operator is working down.

This is an amendment to D118, not a new floor. D118's ruling: "a press changes WHAT IS ON THE SCREEN and never where the rest of it is." The same ruling applies to an axis that D118's guards could not see. Those guards measure pixels. A reshuffle moves no pixels. It changes which row is drawn at which pixel. See "Why D118's guards were blind" below.

### The problem

The operator marks several copies sold in a row. Each press changes the arithmetic, and the list re-sorts under the hand. Two facts point opposite ways. The ranking is correct, and it stays. D132's amendment set it: the largest quantity of the searched card, by section, is the order. What is wrong is that it is recomputed under the hand.

### D28 is the precedent

D28's ruling: "The review answer gets an undo window, and the list stops moving under it." Its first fix was this problem on `#/review`. Answering a card shifted the candidate rows by most of a screen. The answer was to stop the ordering from moving. Reserve what varies, prefetch what is coming, and let the operator work through a list that holds still. Here the varying thing is the rank itself. The ruling is the same, so the shape is the same.

### What is frozen is a fact about the copies, not a list of positions

A snapshot of the rendered order, kept as an array of keys and re-applied, was rejected. That array would be a fourth copy of an ordering. Three call sites already compute it: the copies list's `byFullest`, the box rail's `liveMatches`, and the walk's `landingInFullest`. When one gains a term, a snapshot would disagree with it silently. A frozen order that stopped matching the product's order is worse than one that moves.

What is snapshotted instead is the one input that moves under a press: which copies counted as live when the order was taken. `app/src/frozenRank.ts` holds it as a set of store keys. Every ranking keeps computing itself, from the state the order was ranked against, not from the store's current state.

**The set holds departures, not survivors.** A copy captured after the order was taken is new evidence. Nothing was ranked around it, so nothing holds it. A copy that left since the order was taken is held. Every reader treats it as it was.

**One set, one press, for both lists.** The set lives in `Inventory.tsx` beside the writes, not inside either list. One sale makes the copies list and the box rail stale at the same instant. Two freezes released by two controls would make the owner press twice to stop one list.

### Four readers

| reader | what the freeze does |
|---|---|
| `CardLocations.tsx` `counts` | a departed copy keeps counting for its section, so the section order does not move |
| `BoxBrowse.tsx` `liveMatches` | a departed copy keeps counting for its box, so no box tile moves in the rail |
| `BoxBrowse.tsx` `holdsLive` / `landingInFullest` | the walk does not jump to another box because its box just sold out of matches |
| **`BoxBrowse.tsx` `visible` and `CardLocations.tsx` `stays`** | **the row stays DRAWN with `Hide sold` on** |

The last row is load-bearing. It is D132's other door. Freezing the arithmetic while the fold deletes the row brings the jump back. The row vanishes, and every row under it moves up by its height. D132 offers two treatments for a departed row: fold it away, or sink it under the live ones. Frozen mode takes neither. A sink is a movement too. A frozen departure stays where it is, struck through. That is the only rendering that moves nothing.

The departed row's text is the product's existing one. `pipeline/join.py:Position` already draws a copy in no slot as `Box 7 · departed · B7 #38` (D68 for why it names the record, D58 for why the number now belongs to a different card). `.is-gone` already dresses the row. The freeze changes where the row is, not what it says.

### The control

`Order is N copies stale · re-rank`, a `Chip` in the copies list's header. It draws only once the order is stale.

- **A press, never a timer and never a consequence.** Nothing reshuffles this list on its own.
- **In the copies list's header, not the walk's status bar beside `Hide sold`.** The press that made it stale is in the rows beneath it. A control in the left rail would be far from the hand. It governs both lists, and the rail is frozen by the same set.
- **Absent while the order is current.** A control that recomputes a current order does nothing. A permanent control would read as a setting, not as the state of this list.
- **The word is `copies`, not `sales`.** A sale is what the operator will nearly always press. A retirement (D26's other door) changes the same arithmetic and is held by the same set. This screen does not record which door a hold came through. Recording it would cost three components of plumbing to keep one word. `copy` is the panel's word for these rows everywhere else.

**The count covers the copies this list draws, not every departure the screen recorded.** `frozen` belongs to this screen. A sentence saying `3 copies stale` over a list that holds one of them would count somebody else's cards.

**Two places take a new order without a press.** A new search is a new order. So `BoxBrowse` releases the freeze when the search text changes. An undo releases that copy's hold. A staleness figure that survived an undo would offer to re-rank a store that never moved.

### Why D118's guards were blind

- `cursor.spec.ts`'s two cases read the stylesheets for a pointer state that re-lays out a control. A reshuffle is not a CSS rule.
- `inventory.spec.ts`'s sweep records every element outside `.browse-card` by a stable id and box, and asserts document height and scroll. The copies list is inside `.browse-card`. Its rows are identically shaped boxes. Swap two, and every recorded rectangle is where it was.

So the proof compares the identity of the rows, not their geometry. Both new cases read each row's `aria-label` in order. That is the server's position label, the one string that says which copy is drawn there. The cases compare it before and after. A `toHaveCount` check cannot see a length-preserving reshuffle. A position sweep cannot either.

**Both directions are asserted, one case each.** A case that says only "the order did not change" passes against a build that never ranks. A case that says only "the re-rank changed it" passes against a build that re-ranks on every press. The fixture makes the two answers differ. It has six live copies: three in box 7 section 1, and two in box 2 section 2. The sale takes box 7 from three to two. That is a tie, which the rank breaks the other way. A fixture whose leader stays the leader after a sale cannot tell a frozen order from a recomputed one.

### Mutation results

Each reader of the freeze was deleted in turn, and the suite re-ran. Nine arms go red. One arm deleted a parameter. One survives, named below.

| arm | verdict |
|---|---|
| the copies list's rank ignores the freeze | red |
| the copies list's fold ignores it | red |
| the box rail's rank ignores it | red |
| the walk's fold ignores it | red |
| the shelf pool ignores it | red |
| the re-rank press does nothing | red |
| a sale never holds the order | red (8 cases) |
| a new query never takes a new order | red |
| the control's slot reserves nothing | red |
| the landing ignores the freeze | deleted, see below |
| an undo never releases its hold | survives, see below |

- Four of the nine were green on the first run, for one reason. The case acted on the row the walk stood on. `stays` keeps a row for three reasons: a current copy, a receipt from this sale, or a freeze. The first two answered every assertion. The cases now act on a mid-list row. The retirement case reaches the freeze alone, because `Inventory.tsx` hands the copies list `soldKeys`, not `retiredKeys`. A fifth needed a box whose last live match departs. That is the only state the shelf pool can notice.
- **The landing's freeze was deleted, not covered.** `landingInFullest` runs only on a fresh query. A fresh query releases the freeze, so the parameter could never be populated. A mutation that ignored it left the whole suite green. The landing ranks on current state, as a fresh answer should.
- **The undo's release survives.** Deleting `releaseRank` leaves all 108 cases green. The chip disappears shortly after the undo, so something else on that path clears the hold. Bounding the assertion to two seconds did not separate the two. That does not show the call is redundant. The claim is weaker than the landing's, and the code stays. A later session with a reproduction should find the second clearer and delete one, or find the case this one misses.

### What the control costs

The header's title row reserves `--bn-control-h-sm` whether or not the chip is shown. The copies panel header is about eight pixels taller on every card at desktop. That is D118's trade, taken on purpose. The chip appears on a press. The list scrolls inside `.browse-band`'s fixed height. An unreserved slot would push every copy row down by the chip's height at the moment of the sale. That is the movement this entry exists to stop. The cost is paid once at render, not on the press. It is the same bargain `.browse-row-slotghost` makes in D118's amendment.

The chip's height comes from the kit, not from a number in `CardLocations.css`. `.bn-chip` reads `--bn-control-h-sm`. The token file raises that to 40px under 767px and on any coarse pointer. D117's thumb floor is met by the system. A case asserts it at 390 anyway, because a floor with no reader is not a floor.

### Not built, and reopening

**No preference is stored.** The freeze is always on, and the re-rank press is the only escape. So there is no ninth `banchi.*` key, and D27's roster is unchanged. A remembered "re-rank live" toggle was not built. No one has asked for the old behavior back. A setting nobody changes is a second code path nobody tests.

**The staleness figure counts departures, not "rows that would move".** `Order is 3 copies stale` is easy to believe. `3 rows would move` would be truer. But it needs the order recomputed on every render to compare with the frozen one. That is the live re-rank this entry deletes, running invisibly. If an operator presses re-rank and nothing changes, that is the trade.

**A copy that the store departs while nobody presses anything is not held.** The freeze is filled by this screen's own writes. Another device selling a copy mid-search still re-ranks this list on the next re-read. The exception is an `already_sold` refusal this screen saw, which is held for that reason. A freeze built as a diff against the last answer, not a log of presses, would cover it. It would also freeze a genuine capture that arrives. Unmeasured. Named here, not discovered.
