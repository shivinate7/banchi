# Undo in Banchi

**STATUS: BUILT 2026-09-17, all four sections.** Every ruling below is the owner's, given in
interview the same day. The session opened on one defect — the pull undo is reachable only from
a toast — and the owner reopened undo as a whole: *"do you want to just reopen the entirety of
undo as a concept on banchi and interview me from the start to see if what's been built or
assumed is in line with what I want?"* This file is the answer to that question, and then the
record of building it.

**What landed, one branch per section:** section 3's `U` widening, section 4's resurrect and the
ledger half of the sale undo, section 5's position drop, and section 6's mid-sitting removal on
the capture strip. Section 8's checks all ran. **Section 5 turned out to be a wire change and
not a screen change** — `#/orders` never drew a position for an already-pulled copy, and
`progress.pulled` had zero readers in the whole front end, so what was removed is a join the
server computed for nobody on a request already measured at 520-580ms. The owner's ruling was
already true on screen.

**One thing this build did not fix, and it turned out not to be a defect at all.** A D118
guard on `#/orders` failed intermittently while integrating, and was recorded as a real
sub-pixel reflow on `main`. Measured again on 2026-09-17, that reading was wrong for the third
time: `getBoundingClientRect` reports the gap as exactly 26px on every run, and what varied was
a `boundingBox()` taken while `kit.css`'s `bn-page-in` was still moving the rows it measured.
`app/tests/motionSettled.ts` waits that out, and the finding is closed.

## 1. What is in the tree today

Three unrelated undo models, none of them decided against the others.

| model | the writes it covers | how long | where it is reached |
|---|---|---|---|
| a stack of the sitting | the shot, the review answer | no clock, ten deep, `U` | drawn on the screen |
| a receipt with a clock | the sale, the retirement, the pull | 20 s | a toast, and nowhere else |
| a control on the record | the hand-fill, the stand-down | no clock, for the life of the line | the line's own row |

**NO SERVER ANYWHERE ENFORCES A TIME LIMIT.** `undo_too_late` is the only undo refusal in
`server/capture_server.py` and it is a STATE test, not a clock: it refuses once a card is
identified or its SKU carries a listing hold. `store/orders.py:reopen_line` says the rest in
the store's own words — *"NO WINDOW AND NO CLOCK, which is `forget_pull`'s ruling: how long an
undo stays offered is the screen's business."* Every twenty-second window in this product is a
screen's choice, and no screen ever argued for one.

**THREE WRITES HAVE A BUILT REVERSAL REACHABLE ONLY FROM A TWENTY-SECOND TOAST.** This is the
defect, and the pull is one of three rather than a case on its own:

| write | its reversal | reachable from |
|---|---|---|
| the sale | `{"undo": true}` on the sold route | the row, and the receipt, both for 20 s |
| the retirement | `{"undo": true}` on the retire route | the receipt only, for 20 s |
| the pull | `{"undo": true}` on the pull route | the receipt only, for 20 s |

`undoPull` has exactly two callers, `Orders.tsx:941` and `Fulfillment.tsx:705`, and both are
toast actions. `UNDO_WINDOW_MS = 20_000` is declared three times.

## 2. The ruling: two mechanisms, and they are not the same mechanism

The owner was asked what undo is for, and answered **both, and they want different
mechanisms**:

- **A mis-press, caught in the second.** *"the way back for an accidental mistake in that
  second is just hitting U."*
- **A mistake found later.** *"there's a three dots on a collapsed row on inventory or
  something that lets me undo and resurrect it exactly where it was and correctly moves the
  indexes of the card."*

**Neither is a clock.** The fast path is short because a receipt is short. The slow path is
open for as long as the card is reversible, which is what the store already decides. A clock
is retired as a limit everywhere and kept only as how long a toast stays on screen.

## 3. The fast path: the receipt, and `U`

**The receipt stays, and stops being the only door.** Twenty seconds, unchanged, because a
toast should fade.

**`U` reaches it.** The owner's ruling. `U` already undoes the newest thing on `#/capture` and
`#/review`. It becomes the one key for the newest reversible write wherever one stands, so
undo means one thing in the product rather than three.

**Newest-first is enough for a walk.** The owner was offered per-pull granularity in the walk
and declined it: a walk is short and a wrong pull is noticed at once. The fast path undoes the
newest pull. Anything older is the slow path's job.

## 4. The slow path: the way back is the card

**It lives on the departed row on `#/inventory`, and this is a correction of what this file
said in its first draft.** The first draft put the way back on the order's own line. The owner
rejected the premise outright: *"I frankly think we're currently bottlenecking ourselves by
trying to pair orders with this undo functionality."*

**The screen already has the row.** `BoxBrowse.tsx`'s own control says it: *"Sold and retired
cards sink under the live ones."* With the fold open they are at the foot of the drawer, in
order, exactly where the owner said they were. Nothing has to be found, surfaced or unhidden.

### What it covers

**Sold and retired.** The owner's ruling, and it widens nothing:

- **Sold is one state.** A pull marks the card sold. There is no second state called pulled,
  and the menu does not need to tell them apart.
- **The retirement's reversal is already built.** The retire route takes `{"undo": true}` and
  `_state_before_retirement` computes what it goes back to. It is reachable today from a
  twenty-second receipt and from nothing else. Giving it a second door is reach for a built
  capability, not a new one.
- **Moved is excluded.** A move is a transplant, and `Inventory.move_card` is the only correct
  way to reach it. Reversing one is a different write wearing the same word.

### What it writes

**It resurrects the card at its own index, and nothing renumbers.** The stored index never
moves (D58) — a departure is a gap, and putting the card back closes that gap because the card
is there again. The number a person reads recounts by itself, which is what D58 already
specifies. **This does not overturn D10's permanence rule**, which is about renumbering and
index reuse, and neither happens here.

**It reverses the order ledger in the same write, where the ledger holds the copy.** This is
forced rather than chosen. If the card comes back on the shelf while the line still counts it
fulfilled, the order claims a shipment that did not happen and the card is offered to the next
buyer. The receipt says the order moved. The operator does not have to go anywhere.

## 5. The order record keeps the fact and drops the position

**The owner's ruling, and it is the shape of the whole thing:** *"if I were to look at this
fulfilled order in the past, it does not need to remain connected to inventory and positions,
it should just be the details like 1 calm rune was pulled."*

**During the walk, positions are real.** The owner's own definition of a walk: tick some
orders, press the button, see what card and what quantity each order wants and where the
copies are. Pick one, mark it sold, and that specific indexed card is sold. Press `U` and that
one comes back. Inventory is exactly right throughout.

**Afterwards, the order says what left and not where it was.** A past order's line reads the
card and the count. It draws no drawer, no index and no way back. `OrderLineProgress.pulled`
joins a position per copy at read time and a past order stops drawing it.

**This is D212 arriving one screen later.** Every copy is fungible and no order claims one.
An order that still names the slot its copy came out of is still holding a claim on a
particular card, in the only place the product had left to hold one.

## 6. The capture strip gets the granularity it is missing

**Brought by the owner, unprompted, and it is a real defect:** *"there's currently no way to
undo an image that's in the middle of the capturings without losing all the subsequent
capturings from that session. That's frustrating. I do appreciate being able to undo many at
once, but I also want that granularity."*

**THE ROUTE ALREADY EXISTS AND IS ALREADY BUILT CORRECTLY.** `POST
/inventory/<box>/<index>/remove` deletes one capture mid-box and slides every higher card down
one index — D10 ruling 1, the one sanctioned renumber. It takes the target's own capture id as
an aim check, and it refuses (`renumber_blocked`) if any higher card in the drawer has sold,
retired or picked up a listing hold. `app/src/server.ts:removeCardInPlace` is the client half,
and `BoxBrowse.tsx:2418` already presses it.

**So this is reach, not a build.** The capture strip's rows get the same press the box browser
already has. The owner confirmed the slide is the behavior wanted: the stack really does close
up, because the cards are still in the hand.

**What stays as it is:** `U` still undoes the newest, still runs ten deep, still spans drawers
in the order the hand took them (D164). The granular press is beside it, not instead of it.

## 7. What this does not do

- **It adds no clock and removes no capability.** Every reversal named here is already built
  and already supported. What changes is where each one can be reached from.
- **It does not touch the writes themselves.** No sale, retirement, pull or capture changes.
- **It does not put a control on the Fulfiller's screen.** He keeps his receipt and his twenty
  seconds. The slow path is owner work and the shell-less screen has no route to it (D5, D31).
- **It does not make `#/inventory` a general writer of the order ledger.** One write reverses
  one pull because the two halves are one act. No other order capability moves there.

## 8. What has to be verified

- Three widths, both themes, per this repo's screen rule.
- **The sale undo's ledger half is mutation-tested against the divergence it closes.** Pull a
  copy, reverse it from the card, and assert the line no longer counts it. A guard that has
  not gone red on its own defect is not a guard.
- **The resurrect is asserted to renumber nothing.** The index the card comes back to is the
  index it left from, and no other card in the drawer moves.
- **`renumber_blocked` reaches the capture strip as a sentence.** The mid-sitting press refuses
  over a sold card higher in the drawer, and the operator is told which one.
- **The copy ceiling is measured and reported either way** (D194). The order line loses its
  position text and gains nothing, so the arithmetic should fall the right way. It is never
  pinned quietly.
- `U`'s new binding is in `SHORTCUTS`. A binding is not done until it is.

## 9. What would reopen this

A second operator. Every ruling here assumes one hand: the fast path is one hand's own newest
press, and the slow path assumes the card in front of you is the card you are reversing. Two
people pulling from the same drawers changes what a resurrect means to the other one.

## 10. The order walk's own row: a rank, never a clock

**AMENDED 2026-09-20.** `app/src/OrdersWalkPane.tsx` drew its own `Undo` inside the walk's own
row, on its own twenty-second clock, separate from the receipt this file already describes. A
copy sold more than twenty seconds ago showed a dead `Sold` pill. This was a fixed time limit
on a reversal. Section 2 rules that shape out for every write in this product.

**The owner gave this its own lane on 2026-09-19, apart from the rest of this file's build.**

**The clock is gone. Rank replaces it.** The walk's own row still offers `Undo`, but only on
the NEWEST pull this walk made. Section 3 already says this for the walk: *"the fast path
undoes the newest pull. Anything older is the slow path's job."* This was a ruling about which
copy gets `Undo`, never about a duration.

**"Newest" is not a countdown. It is a position.** A pull is newest until a later pull replaces
it. Undoing the newest pull hands the rank back to whichever pull came before it, if one is
still standing. Nothing here reads a clock.

**What was the clock protecting, and what protects it now.** The old clock kept a walk from
piling up several open `Undo` buttons at once, one per sold copy. The owner declined that
shape directly (section 3, "per-pull granularity"). The rank does the same job without a
timer: only one row ever carries `Undo`, because only one pull is ever the newest.

**An older sold copy is a dead end IN THIS ROW, on purpose.** Its way back is the card, on
`#/inventory`'s own departed row (section 4). This pane never draws a second door.

**What has to be verified, added to section 8's own list.** A case proves `Undo` on the walk's
newest pull still stands after the OLD twenty-second window would have closed it. The clock is
faked and only advanced, never slept through. A second case proves a later pull is what removes
an older row's `Undo`, mutation-tested against the granularity the owner declined.

## 11. Open: the undo session (the owner's ruling, 2026-09-24)

The 2026-09-23 UX review found undo defects on four screens. The owner moved all of them out of
the screen lanes and into one session of their own:

```
undo in general is buggy everywhere, probably better to have an overall undo session at a
later time than diagnosing it
```

STATE: RECORDED, NOT STARTED. No lane holds these findings. Each id below resolves in
`docs/reviews/ux-2026-09-23/CONSOLIDATED.md`.

| Finding | Screen | What is wrong |
|---|---|---|
| UX-195 (HOR-07) | Orders | The pull receipt offers Undo, and Undo then refuses with `sold_origin_unknown`. |
| UX-204 (HIR-10) | Review | At 390 the receipt and its Undo land below the fold. |
| UX-205 (HIR-11) | Review | An answer that cannot be taken back writes with no warning. |
| UX-249 (HIR-20) | Inventory | After a sale, the card's control becomes a static chip, and the phone bar loses its action. |
| UX-252 (HIR-23) | Inventory | Retire commits on the first tap of a reason, with no undo. |
| (carried) | Inventory | The sale toast's Undo misbehaves. The inventory lane recorded it and did not fix it. |

**Related, and decided already.** The owner accepted the risk that Orders' Mark sold is an icon
while its Undo still refuses. A wrong press needs a fix by hand until this session lands.

**Where to start.** Read sections 1 to 10 first. The session diagnoses each finding against the
two mechanisms in section 2 before it changes either one. Its first measurement is whether
UX-195 happens on a real store or only on the seeded one. The seeded store can lack the sale's
origin record.
