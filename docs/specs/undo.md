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
  **AMENDED 2026-09-25, the owner's ruling (section 11.7, Q1): a move is undoable now.** It
  lasts until either box changes. Section 11.3's UN-14 builds it.

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
  seconds. **AMENDED 2026-09-25, the owner's ruling (section 11.7, Q1): the twenty seconds
  go.** His newest sale keeps its Undo until a newer sale or the next step is built on it. The slow path is owner work and the shell-less screen has no route to it (D5, D31).
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

## 11. The undo session: the plan (the owner's rulings, 2026-09-25)

**STATE: PLANNED, NOT BUILT.** This section replaces the 2026-09-24 placeholder. It distills
a blind audit of the running app and the owner's interview of 2026-09-25. The rulings are
recorded verbatim in `docs/reviews/ux-2026-09-23/RULINGS.md`, under "Undo session". The
blind audit itself stays in the session scratchpad. Its words are quoted below where an item
cites it.

The owner's words, verbatim:

```
How long: "Anytime, from a history".
A press that cannot be undone: "Never ask".
"hmm how would i for example, undo the 24th capture in my capturing run when i'm on capture
36? currently i'd have to undo 12 captures, i imagine there's a way to yes undo all the way
to 24, but also to just undo 24 -- does that make
sense in what im trying to have u think
about? marking something sold on inventory though is much more straight forward.. etc.."
What hurts: "capture mistakes 50%, marking the wrong card sold 30%, wrong review answer 20%".
"I do imagine that at a certain point inventory needs to lose its undo (or more like i would
never use it), it's not that I relaly need undo forever, it's just a couple seconds isn't
enough, and that a day feels arbitrary."
On expiry: "Yes, until it's built on (Recommended)".
```

### 11.1 The one undo model

**An undo has no clock.** It lasts until the next step depends on the action. That step is
"built on" below. After it, the fix is an ordinary action, not an undo. This refines the
first answer ("Anytime, from a history").

**The two mechanisms of section 2 stay.** The fast path is `U` and the receipt. The slow
path is the record's own control. Only the limit changes:

- **A clock limits nothing.** A toast still fades. The undo does not fade with it.
- **Rank decides the FAST PATH, never which rows draw a control (the delta review round,
  item 6, the owner's own ruling).** `U` and the toast reach only the newest reversible
  write on a screen. This section first read that as the only rule there was. Inventory's
  own row-level Undo followed it (finding #12): an older sold row lost its own Undo the
  moment a newer sale took the rank. The owner's ruling settles it the other way for the
  ROW — an undo lasts until it is built on. Every sold row keeps its own Undo until IT is
  built on, on Inventory and Cards to pull alike. Fulfillment's "Pulled today" list already
  worked this way. Inventory now matches it, rather than the other way round. Rank still
  decides the ONE thing `U` and a toast's own Undo reach.
- **"Built on" limits both paths.** The server decides it and refuses with a sentence. The
  screen never guesses it.
- **"Never ask" holds everywhere but one press.** No other press gets a confirm. A press that
  cannot be undone today gets an undo instead. The one exception is "undo just N" on the
  capture strip (Q2). It keeps its confirm and stays permanent.

**Section 2 already ruled out the clock. The build kept it.** `UNDO_WINDOW_MS = 20_000` in
`Inventory.tsx`, `Orders.tsx` and `Fulfillment.tsx` limits the row's Undo and the `U` key.
It does not only time the toast. That is a build that disagrees with its own spec, not a new
ruling.

| Action | Built on when | The fix after that |
|---|---|---|
| Capture | Its sitting ends, or a run identifies it. A sitting ends at a 30-minute gap (`GAP_MINUTES`, D121, D164). "Undo just N" is permanent and asks first (Q2). | Manage box removes the card (D10 ruling 1). |
| Sale on Inventory | Its photograph is reclaimed (D89), or its box is buried (D134). | "This card is still here" puts the card back. A shipped order re-points (the owner's ruling, 11.8). |
| Sale on Orders | Its order ships or closes (`store/orders.py:is_terminal_status`), or as for Inventory. | The same "still here" press. The order keeps its count, and its line becomes a hand-fill (11.8). |
| Sale on Cards to pull | The same as Orders. The Fulfiller keeps the fast path only (D5, D31). | The owner's press on Inventory. |
| Retire | Its box is buried (D134). | None needed. Nothing downstream reads a retirement. |
| Move | Either box changes: a capture, a sale, a retire or a move in either box. | A new move (the box map's Q4 default, RULINGS "Box map"). |
| Review answer | Its SKU is in a written listing file, or holds a listing hold (`undo_too_late`, built). | The card's own correction route (D252). |
| Review close, stand-down | The card is identified by another route. | The next run asks again. |
| Review close, retire | As for Retire. | As for Retire. |
| Typed price | The next send carries it. | Type the price again and send. |
| Clear typed | The next send carries any cleared SKU. A SKU typed since is kept (built). | Type the prices again. |
| Hold | Never. A hold withholds, and nothing reads past it. | Release is the hold's own control. It puts back the answer the hold replaced, value and channel, kept in the hold's `before` field. A hold with no earlier answer releases to none (the owner's ruling, "Bring back $5.16 (Recommended)", RULINGS). A release, and U on a hold, keep the answer's first date: `corpus.stamp_answers` does not re-date a price that returns from a hold with the value, channel and date that the hold kept (the owner's ruling, "Keep the first date (Recommended)", RULINGS). The server sets the hold's kept date from the stored answer it replaces, and never takes it from the client. |
| Cut-off change | The next send prices by it. | Set the cut-off again. |
| Divider | A card is captured behind it. | Manage box edits the sections (`Inventory.set_sections`). |

### 11.2 What the code does today, per audit failure

- **`sold_origin_unknown` is seed-only (HOR-07, UX-195).** Measured on a `.backup` copy of
  the owner's store: 0 of 1,050 sold, 0 of 5 retired and 0 of 2,455 live cards lack an
  earlier state line. On a fresh demo seed, 18 of 18 sold, 2 of 2 retired and 101 of 101
  live cards lack one. `scripts/demo-seed.py` writes cards into `inventory.cards` directly.
  It logs no state line. `_state_before_sale` and `_state_before_retirement` then find no
  earlier state, and correctly refuse to guess.
- **The "no earlier state" refusals have the same cause.** "Bring this card back", Review's
  retire undo, Inventory's "No undo for this one." and the Fulfiller's "You cannot take this
  one back here" all read a null `restores_to`. On the owner's store, each one would reverse.
  A copy that reversed on the seed (Tricksy Tentacles) most likely gained a state line
  earlier in the audit's own session. That is unmeasured.
- **Review's "Can be undone" has a real-store defect under it.** `do_retire` touches no queue
  entry, by its own docstring. `do_queues` lists `open_entries` and reads no card state. So a
  card retired from Review stays in Review, and comes back on reload. The owner's store holds
  0 such entries today.
- **The `U` key has five scopes, one per screen.** No shared primitive exists.
  `Pricing.tsx:onKey` reads `U` only inside a price field. `Orders.tsx` reads it only on the
  pull stage, and only before `lastPull.until`. `Inventory.tsx:onUndoKey` needs a live
  receipt with `canUndo`. `ReviewQueue.tsx` reads its own ten-deep stack with no clock. That
  is why `U` worked after Review's receipt left. On a phone there is no `U` at all.
- **Clear typed loses its undo when the toast goes.** `do_pricing_clear` hands `cleared` back
  to the browser and keeps nothing. `Pricing.tsx` holds that map only in the toast's
  `onPress` closure.
- **Rows move under the finger.** On `#/orders`, `OrderLineRow` draws one `PickLine` per
  unpulled copy. A pull drops its copy from `copies`, so the next copy takes the same
  place. On `#/fulfillment`, `drop()` removes the card and the receipt sheet covers the next
  card's button. D118 already forbids both.
- **Capture stops at ten.** `CaptureScreen.tsx:undoStack` slices `sitting` to `UNDO_DEPTH`
  (10). The server has no cap. Both presses exist: a row walks back to that card, newest
  first (`undoCapture`). The corner press removes one card and slides the later ones down
  (`removeCardInPlace`). From capture 36, capture 24 is the 13th newest, so it has no row.
  The strip also lives in page memory, so a reload ends the sitting.
- **Remove-just-N asks first, and cannot be undone.** The corner press opens "Remove just
  this card?". `do_remove_card` then consumes the photograph as it slides the later cards
  down.

### 11.3 Action items, by the owner's pain weights

Capture is 50%, a wrong sale 30%, a wrong Review answer 20%. Pricing and move follow.
"Owner" names the question in section 11.7 that answered the item.

| id | The user-visible problem | Root cause | Fix | Mechanism | Files | Store risk | The check that proves it | Owner |
|---|---|---|---|---|---|---|---|---|
| UN-1 | From capture 36, capture 24 is out of reach. | `CaptureScreen.tsx:undoStack` slices to `UNDO_DEPTH`. | List the whole sitting, newest first, in a scrolling strip. | Fast | `app/src/CaptureScreen.tsx`, its CSS, `app/tests/capture-undo.spec.ts` | None. Same routes. | A 36-shot case reaches 24 both ways. Put the slice back and it goes red. | Q1 |
| UN-2 | A reload ends the sitting and the strip. | `sitting` is page state. | Rebuild the sitting from the store, by the 30-minute gap. | Fast | `server/capture_server.py` (one read), `app/src/server.ts`, `app/src/types.ts`, `CaptureScreen.tsx` | None. A read. | Capture, reload, and the strip still lists the sitting. | no |
| UN-3 | "Remove just this card?" asks, and the removal cannot be undone. | `do_remove_card` consumes the photograph. | Keep the confirm (Q2). Its words say plainly that the removal is permanent and deletes the photo. | Confirm | `app/src/CaptureScreen.tsx`, `app/tests/capture-undo.spec.ts` | None. Same route. | The dialog's text names both facts. Remove either and the case goes red. | Q2 |
| UN-4 | Every sale undo on the demo refuses (`sold_origin_unknown`). | `scripts/demo-seed.py` logs no state line. | The seed logs the lines a real capture, answer and sale log. | Both | `scripts/demo-seed.py`, a demo self-test | None to the real store. | Every seeded card has an origin. Drop one line and the self-test goes red. | no |
| UN-5 | Sale Undo dies with its toast. "No undo for this one." `U` does nothing. | `UNDO_WINDOW_MS` limits the row, the receipt and `U` on three screens. | Rank, not clock. The newest sale keeps Undo in its row and on the page. | Fast | `app/src/Inventory.tsx`, `Orders.tsx`, `Fulfillment.tsx`, their specs | None. Same route. | Undo still works after a faked 60 s. A newer sale moves it. | Q1 |
| UN-6 | "slid in with its $ button exactly where I had just tapped". | A pull drops its `PickLine`. `drop()` does the same on `#/fulfillment`. | The sold copy keeps its place, and its control becomes Undo (D57). | Fast | `app/src/Orders.tsx`, `Fulfillment.tsx`, their specs | None. | A rect-diff after a pull: no other row moves (D118). | no |
| UN-7 | A sale reverses after its order shipped, or after its photo went. | `_sell` checks state and history only. | Refuse the undo when built on. Add "This card is still here". A shipped order's line re-points to a hand-fill (11.8). | Slow | `server/capture_server.py`, `store/orders.py`, `app/src/BoxBrowse.tsx`, `server.ts` | Yes. A new write. | Ship an order, then undo: a refusal. "Still here" restores the card, and the order keeps its count. | no |
| UN-8 | Review retire says "Can be undone", and the card comes back on reload. | `do_queues` reads no card state. | A departed card owes no answer. Skip it in every open-entry read. | Both | `server/capture_server.py`, `app/src/ReviewQueue.tsx` (copy) | None. A read. | Retire from Review, then reload. The card is gone, and undo brings it back. | no |
| UN-9 | The Review receipt is below the fold at 390, and its 20 px arrow fails. | The receipt sits under the answers, at `size="sm"`. | The page Undo (UN-10) is the door. The arrow meets the 40 px floor (D117). | Fast | `app/src/ReviewQueue.tsx`, its spec | None. | At 390, Undo is in view and 40 px or more. | no |
| UN-10 | Undo looks different on every screen, and a phone loses it with the toast. | No shared primitive. Five `U` scopes. | One kit hook for `U`, and one Undo in `Page`'s toolbar, away from Send. | Fast | `app/src/kit/Page.tsx`, a kit hook, `kit.css`, `App.tsx` `SHORTCUTS`, `Gallery.tsx` | None. | One spec presses `U` on each screen. The kit check fails a screen that binds `U` itself. | no |
| UN-11 | "Clear typed" expires, and "49 prices gone". | `cleared` lives only in the toast closure. | The server keeps the newest clear. Restore reads it until the next send. | Both | `server/pipeline_routes.py`, `pipeline/corpus.py`, `Pricing.tsx`, `ClearPrices.tsx` | Yes. A side file by `prices.json`. | Clear, reload, and restore. A send in between refuses it. | no |
| UN-12 | A Pricing hold ignores `U`, and one `U` undoes half a hold. | `U` is read only in a price field. `setHold` pushes two stack entries. | UN-10's hook. One press is one stack entry. | Fast | `app/src/Pricing.tsx`, its spec | None. | Hold a no-market SKU, press `U` once. The hold is fully gone. | no |
| UN-13 | A cut-off change has no receipt and no undo. | The cut-off write pushes no stack entry. | A receipt, and a stack entry that holds the prior value. | Fast | `app/src/Pricing.tsx`, its spec | None. Same write. | Change it, press `U`, and the old value is back. | no |
| UN-14 | A move has no undo, and moving back puts the card at the front. | Section 4 excluded moves. `move_card` has no reversal. | Delete the transplant while it is the newest, and restore the tombstone. | Both | `store/master.py`, `server/capture_server.py`, `Inventory.tsx` | Yes. A new write. | Move, then undo. The card is back at its index, and nothing else moves. | Q1 |
| UN-15 | A divider has no undo. | No reversal is built. | While no card is behind it, `U` drops it through `set_sections`. | Fast | `CaptureScreen.tsx` | Low. An existing write. | Press `S`, then `U`. The sections are as before. | no |

### 11.4 Lanes

Three lanes, with disjoint files. Lane S goes first. Lanes C and R start at once on the
items that need nothing from S.

- **Lane S, the store (Opus build, Opus review).** UN-4, UN-7 (server half), UN-8, UN-11
  (server half), UN-2 (the read), UN-14. It owns
  `server/`, `store/`, `pipeline/`, `scripts/demo-seed.py`, `app/src/server.ts` and
  `app/src/types.ts`. It writes the store, so it needs an Opus review.
- **Lane C, capture (Sonnet).** UN-1, UN-3 and UN-15 at once. UN-2's screen half after
  lane S lands. It owns `app/src/CaptureScreen.tsx`, its CSS and
  `app/tests/capture-undo.spec.ts`. Its review is Sonnet.
- **Lane R, the sale, Review and Pricing screens (Sonnet build, Opus review).** UN-5, UN-6,
  UN-9, UN-10, UN-12, UN-13 at once. UN-7 and UN-11 (screen halves) after lane S lands. It
  owns `Inventory.tsx`, `Orders.tsx`, `Fulfillment.tsx`, `ReviewQueue.tsx`, `Pricing.tsx`,
  `ClearPrices.tsx`, `BoxBrowse.tsx`, `App.tsx`, `app/src/kit/` and their specs. It decides
  when a sale can be undone on screen, so it gets an Opus review.

### 11.5 Seen, outside undo

- **Enter moves to the next price** (audit 7). `Pricing.tsx:onKey` commits and moves on
  Enter. It is the worklist's walk (D49), and a question for the Pricing lane.
- **Slow screen switches, about 3 s** (audit 10). Unmeasured. A performance item.
- **Stacked toasts cover about 40% of a phone** (audit 9). The toast stack, a kit item.
- **"Clear typed" reads "Clear" on a phone.** A Pricing copy item.
- **"Mark down stale" did nothing visible.** Unmeasured.
- **A moved card showed "No photo was stored for this card."** Unmeasured. The seed writes no
  transplant record, by its own comment in `scripts/demo-seed.py`.
- **Two sold rows both read "#9".** `BoxBrowse.tsx:departedSlot` draws the number the card
  had when it left (D259). D58 gives the next card that number. D68 once fixed this same
  collision with the store key. The owner's word is needed before it changes.
- **A typed-price undo takes about a second.** Unmeasured.
- **Graveyard has no controls.** D134 makes it read-only. The way back is Inventory's row.

### 11.6 Where the owner's answers meet a recorded decision

The owner switched all five on 2026-09-25 (Q1). Each entry now carries its amendment.

- **D164**, "capped at `UNDO_DEPTH` as before". The premise was that ten covers a sitting.
  The owner's own example needs thirteen.
- **D28**, "A twenty-second undo, the shape the product already ships." The premise was that
  twenty seconds is enough. The owner said a couple of seconds is too short (paraphrase).
- **D57**, "the row's control becomes `Undo` for twenty seconds." The same premise.
- **Section 4 of this file**, "Moved is excluded." The premise was that a move's reversal is
  a different write. "Never ask" asks for every press to be undoable.
- **Section 7 of this file**, "He keeps his receipt and his twenty seconds." The Fulfiller's
  clock goes with the others.
- **D10 ruling 1** is untouched. Q2 kept the confirm and the permanent removal.

### 11.7 The owner's answers, 2026-09-25

**Q1. May the five sentences in 11.6 change to "until it is built on"?** The owner's answer,
verbatim:

```
"Switch all five (Recommended)"
```

D164, D28 and D57 each carry an amendment. Sections 4 and 7 of this file carry theirs. UN-14
is in.

**Q2. How does "undo just 24" work with no confirm?** The owner's answer, verbatim:

```
"Keep the confirm here only"
```

"Undo just N" keeps its confirm and stays permanent. It is the one exception to "Never ask".
UN-3 makes the confirm's words say that the removal is permanent and deletes the photo.

### 11.8 Lane S, as built (2026-09-25)

The server halves are built on branch `ux/undo-store`. T7's `check_undo_until_built_on`
proves each one. Three choices the table left open are recorded here.

- **UN-7, "This card is still here", on a shipped order.** It is `{"still_here": true}` on
  the sold route. The card goes back. The order keeps its count (D212), but the card's
  capture id comes off the line as a `sold_separately` hand-fill. With the id left on the
  line, a later pull of the same card would refuse as a second shipment. On an open order,
  "still here" releases the line, as a plain undo does (section 4).
- **UN-8 is a read, not a write.** `do_retire` still touches no queue entry. Every
  open-entry read skips a departed card (`Queue.owed_entries`), so the retire undo brings
  the card back into Review with no second write.
- **UN-2: the server decides when the sitting ended.** `GET /capture/sitting` answers
  `open: false` and no cards once the newest capture is more than 30 minutes old. The
  capture undo route reads the same rule, and refuses `capture_built_on` for a card outside
  the open sitting (the coordinator's word, 2026-09-25). The fix after that is Manage box.
- **UN-14 review round.** A transplant now carries `moved_from`. The sitting read leaves out
  tombstones and transplants. The capture undo refuses a transplant, so it cannot delete a
  moved card or its photo. A tombstone's name is now `moved:<name>@<its key>`. A card moved
  back, or on to a third box, now leaves distinct tombstones, and the UNIQUE index holds.
  The card's own name is unchanged (D172). Older tombstones keep the bare
  form, and the move undo reads both. A divider put in behind the transplant builds on the
  move. A batch move is undone one card at a time, and only its last card is the newest, so
  only that card can be undone. The others are moved back.
- **A chain of moves undoes one link.** Move a card from A to B, then from B to C. Undo the
  second move, and the card is back at B. The first move is then built on, because box B
  changed. Its fix is an ordinary move back to A. Section 11.1's table stands as it is.
- **The move undo restores the order key too (D265).** The card comes home at its own index
  and at its own place in the walk.
- **A section reorder inside a box does not build on a move.** A reorder writes no card
  history, so the move undo still returns the card to its own order key.
- **"Still here" and the ledger: the owner's ruling, 2026-09-25, verbatim:**

  ```
  "Card back, order re-points"
  ```

  The behavior above stands. The card goes back. On a shipped order, the line keeps its
  count and becomes a `sold_separately` hand-fill. The SKU's `sold_here` falls by one.

### 11.9 Lane C, as built (2026-09-25)

Built on branch `ux/undo-capture`, `app/tests/capture-undo.spec.ts`.

- **UN-1.** `CaptureScreen.tsx:undoStack` no longer slices to `UNDO_DEPTH` (D164's cap, gone
  on the owner's Q1). The whole sitting is the strip, newest first. `.capture-undo-list`
  scrolls inside its own footer, a fixed `max-height` at desktop. The tablet breakpoint
  keeps its own horizontal scroll instead. Neither grows the page.
- **UN-15.** A divider gets its own undo. `doSection` remembers the box's dividers as they
  stood before the one it just added (`pendingDivider`). `U` puts them back through
  `updateBox({ sections })`, Manage box's own route. It fires only while `pendingDivider` is
  still the newer of the two reversible writes here, by `at` against the sitting's own
  newest shot. A capture into the SAME box clears it. The divider is built on.
- **UN-3 (Q2, "keep the confirm here only").** The mechanism is unchanged. `do_remove_card`
  still consumes the photograph and slides the later cards down, with no undo. Only the
  words changed. The dialog now says "This permanently deletes the record and its
  photograph" in place of the old "There is no undo."
- **UN-2's screen half.** `getCaptureSitting()` runs once. It waits for the game registry,
  which is the one thing that can resolve a hydrated card's `game` key into a `GameEntry`.
  A second read never fires. It would duplicate every row `shots` already holds. `undoNote`
  reads `capture_built_on` the same way it reads every other refusal, the server's own
  sentence and code, verbatim. It also offers a "Manage box" button, named for the refused
  card's own box, per 11.1's table row for Capture.
- **The pre-existing flake.** `pressing the pause button moves nothing else on the screen
  (D118)` fails at roughly 1 in 2 to 1 in 8 runs, `--workers=1` included, on the tree before
  this lane's own commits too. Checked by running the prior commit's `CaptureScreen.tsx`
  against the same spec. Not this lane's defect. Not investigated further here.

### 11.10 Lane R, as built (2026-09-25)

The screen halves are built on branch `ux/undo-screens`, over lane S's `ux/undo-store`.

- **UN-5.** `Inventory.tsx`, `Orders.tsx` and `Fulfillment.tsx` no longer prune their receipt
  lists on `UNDO_WINDOW_MS`. Rank replaces the clock. `remember` still prepends and dedupes
  by key. The newest sale or retirement keeps `Undo`, in the row and on the toast, until a
  newer write replaces it. The drain bars this made misleading are removed.
- **UN-6.** The first build here froze a just-pulled copy inside `OrderLineRow`/`PickLine`.
  It was UNREACHABLE. `OrderDetail`'s only call site always renders `PickLine` with
  `hidePicks` true. A takeable copy's own Mark sold never draws there in the shipped product.
  `make orient` traced this after the blind audit saw the real defect on a live screen, at
  390: the walk's own card pane, not the Manage sheet. That change is reverted in full.
  The real fix is `OrdersWalkPane.tsx`. `advanceAfter` moves the whole card pane to the next
  take the instant a sale satisfies it. `busyCopy` disables every OTHER row while one sale is
  in flight, but it cleared at once. The new card's own row was never disabled against the
  tap that just landed. `ADVANCE_GUARD_MS` holds `busyCopy` a beat longer after an advance.
  A rect-diff case at 390 (`tests/orders.spec.ts`) is red without the guard and green with it.
  Fulfillment's own row-per-card list never removed a copy the way Orders' did. Its defect was
  the `.ff-sheet`, and it needed no row-freeze.
- **UN-9, UN-10.** `kit/undo.ts`'s `useUndoHotkey` is the one `U` primitive. It is armed once
  per screen instead of five near-identical listeners. `kit/index.tsx`'s `PageUndo` was
  Review's own door onto its below-the-fold receipt, first reached through a prop `Page`
  carried for it. It is measured NOT to reserve space: doing so on every load cost
  `#/review`'s no-scrolling floor 54px it had no slack for (`answering a card costs no
  scrolling`). Inventory and Orders keep their own row-level `Undo` (D57) and never drew one.
  **AMENDED, §11.12: Review no longer draws that header door at all.** The finding #10
  conflict this created is resolved there. The reserved in-body row wins over the
  unreserved header door. **AMENDED AGAIN, the delta review round, low item 7: `Page`'s
  `undo` prop is deleted.** With Review gone, no screen passed it. `Gallery.tsx`'s specimen
  now draws `PageUndo` and its `.bn-page-undo` wrapper directly, the pattern any screen
  reaching for this door again would repeat.
- **UN-12.** `Pricing.tsx`'s `Undo` type is now `{ entries: readonly UndoEntry[] }`. `write`
  is `writeMany`'s one-op case. `setHold` pushes both fields it touches as one entry. One `U`
  now undoes a hold completely.
- **UN-13.** The store-wide cut-off (`setCut`) gets a receipt and a `'cutoff'`-kind
  `UndoEntry` holding the prior `threshold`/`sub_threshold`. It reverts on the same pop
  other entries do.
- **UN-7 (screen half).** `BoxBrowse.tsx:CardOps` offers "This card is still here"
  (`saleStillHere`) once the ordinary reversal refuses `sale_built_on`. It is never a retry of
  the same request. The toast follows the owner's ruling above: the card is back in stock,
  and the order line it was pulled for is marked filled by hand.
- **UN-14 (screen half).** `Inventory.tsx`'s `Receipt.kind` gains `'move'`. `doMove` folds a
  move into the same `remember`/`receipts` list a sale or retirement uses. `U` and the
  toast's own Undo reach it, ranked the same way. `Receipt` also keeps the transplant's
  CURRENT box/index and capture id (`MoveResult.new_box`/`new_index`/`card.capture_id`). On
  `move_built_on`, `moveBack` fires an ordinary `moveCard` again. It aims at that current
  position, back to the receipt's own origin box. `server.ts:moveCard`'s own doc comment
  names this remedy. It is never a second route the way UN-7's `saleStillHere` is.
- **UN-11 (screen half).** `Pricing.tsx` reads `GET /pricing`'s `last_clear`. It offers
  "Restore N cleared" once the toast that named the clear is gone. `restoreLastClear`'s own
  answer carries no per-SKU values, so this reads the corpus fresh afterward. It takes each
  restored SKU's answer off THAT read — the same "the response decides which rows come back"
  rule `withRestored` already follows for the toast's own path.

### 11.11 One vocabulary (the Opus review round, finding #15)

Converged by the orchestrator in the delta review round.

The review found the same outcome named differently on different screens. "Sale undone".
"Move undone". "Card moved back". "Card brought back". "Put X back". "N prices restored".
"Not restored". "The card was not put back". "Already put back". A person reading two of
these got no signal that they name the same kind of event.

This section first drew a line between a true reversal and a write that only looks like
one, and kept each its own phrase. The orchestrator's own delta-review ruling folds that
line away. Every write an Undo press or a toast's own Undo reaches reads `"<what it undid>
undone"`, whichever of the two kinds it is. A REFUSAL is the one thing that stays its own
plain sentence, never forced into the pattern. A refusal is not an outcome to name. It is
a reason to give.

The vocabulary, as built:

- **Sale, retirement, move, hold, cut-off.** `"Sale undone"`, `"Retirement undone"`, `"Move
  undone"`, and Pricing's own hold/cut-off writes all already read this way.
- **`BoxBrowse.tsx:CardOps.resurrect`** (a true reversal of a sale or retirement) reads
  `"Sale undone"` / `"Retirement undone"`. Same words `Inventory.tsx` already uses for the
  identical write.
- **`BoxBrowse.tsx:CardOps.stillHere`** (UN-7's `saleStillHere`, a DIFFERENT write reached
  only after an ordinary reversal refuses `sale_built_on`) reads `"Card undone"` now,
  in place of the old `"Card brought back"`.
- **Orders' pull undo** (a true reversal) reads `"Pull undone"`, in place of the old
  `"Put X back"`.
- **Orders' `pull_not_recorded` case** (finding #8: the pull was already reversed
  elsewhere, a DIFFERENT write from the ordinary undo) reads `"Already undone"`, in place
  of the old `"Already put back"`.
- **Pricing's cut-off/mass-clear restore** reads `"N prices undone"`, in place of the old
  `"N prices restored"`.
- **Every refusal stays plain**, never forced into "<subject> undone": `"Not undone"`,
  `"The card was not put back"`, `"Not undone"` (Pricing's own restore refusal). The reason
  goes in the body, never the raw code (finding #7).

The rule for a new screen: name the result of ANY press an Undo control reaches
`"<subject> undone"`. This holds whether the write is a provable reversal, or a different
write with the same visible effect. Name a refusal plainly. Never borrow "undone" for it.

### 11.12 Finding #10, decided by the orchestrator (the Opus review round)

The review asked that Review's receipt row reserve its own space. Then nothing else moves
when it mounts (D118). Section 11.10's own UN-9/UN-10 entry recorded the opposite ruling,
from the same round. `PageUndo` does NOT reserve space on Review. Reserving it cost the
no-scrolling floor 54px it had no slack for.

Measured for this finding: Review rendered the SAME receipt twice. `.review-tray`'s own row,
in the body, already reserved its height. It moved nothing (proven by the finding #14 test).
`PageUndo`, in the page header, was the redundant second copy. It was the one that was not
reserved. Its mount pushed `.review-filters` and everything below it down 56px on the first
answer of a session.

**Decided: drop the header's `PageUndo` on Review.** `ReviewQueue.tsx` no longer passes
`undo` to `Page` at all. The in-body Tray is the only Undo door Review ever draws. Nothing
is lost on a screen wide enough to see the Tray. `kit/undo.ts`'s own comment says `PageUndo`
exists so a phone reaches Undo "without hunting the in-page receipt, which sits below the
fold on a phone". Review's own Tray sits inside `.review-body`, on screen with the card at
every width this product ships. That reach was never actually lost here. This removes the
duplicate. It keeps both floors, D118 and the no-scrolling floor, intact at once. `PageUndo`
itself is untouched.

**AMENDED, the delta review round, low item 7.** Review was the one screen passing `undo`
to `Page`. With that call site gone, `Page`'s own `undo` prop reached no screen at all.
`Page.tsx` dropped the prop and its `<div className="bn-page-undo">` wrapper. `PageUndo`
the component, and the `.bn-page-undo` class, are UNTOUCHED — `Gallery.tsx`'s specimen
sheet renders both directly, its own `<div className="bn-page-undo">` around its own
`<PageUndo>`, never through `Page`. A screen that wants the header door back writes that
same pair itself, the way the gallery does.

The second option this section once offered stays open. A screen may genuinely need both
a header door and zero reserved space. An overlay `.bn-page-undo` never moves layout. It
spends no permanent space on any screen that draws `PageUndo`. Review does not need it. Its
Tray already does the job.
