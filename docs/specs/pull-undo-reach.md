# The pull receipt outlives its toast

**STATUS: SPECIFIED, NOT BUILT.** This file is a proposal and waits on the owner's word. It
was scoped on the owner's ruling of 2026-09-17, interviewed on the order-walk plan: the reach
of the pull undo is not a clause of that rebuild and is fixed separately, across `#/orders`
and `#/fulfillment` together.

## 1. The complaint, measured

`undoPull` has exactly two callers in the product. Both are toast actions, both live twenty
seconds:

| caller | what it is |
|---|---|
| `app/src/Orders.tsx:941`, inside `undoFromToast` | the toast's `Undo` on `#/orders` |
| `app/src/Fulfillment.tsx:705` | the toast's `Undo` on `#/fulfillment` |

`UNDO_WINDOW_MS = 20_000` is declared three times — `Orders.tsx:102`, `Inventory.tsx:54`,
`Fulfillment.tsx:77`. Leave the screen, or let the twenty seconds run out, and the card stays
sold with no control anywhere that puts it back. The route is fine and the write is
supported; nothing reaches it.

**THE LEDGER NEVER FORGETS WHICH COPIES WENT, WHICH IS WHY THIS IS A SCREEN DEFECT AND NOT A
STORAGE ONE.** `store/orders.py:LineProgress.copies` holds the capture ids of every recorded
copy for the life of the line, and `Ledger.holder_of` is the reverse index over them. The
record the undo needs is permanent. Only the control is temporary.

**`forget_pull` ALREADY RULED ON THE CLOCK AND THE SCREEN DID NOT READ IT.**
`store/orders.py:reopen_line` says it in the store's own words: *"NO WINDOW AND NO CLOCK,
which is `forget_pull`'s ruling: how long an undo stays offered is the screen's business."*
The twenty seconds is a screen choice nobody argued for, sitting on top of a store that
imposes none.

## 2. The asymmetry that makes this a defect rather than a gap

D113 gave a line three ways to close, and named a reversal for each. Two of the three are
reachable from the line for as long as the line exists. The third is reachable for twenty
seconds.

| closer | reversal | how long it is reachable |
|---|---|---|
| `record_fill` | `forget_fill` | for the life of the line, from the line's own row |
| `close_line` | `reopen_line` | for the life of the line, from the line's own row |
| `record_pull` | `forget_pull` | twenty seconds, from a toast |

The pull is the only one of the three that moves a physical card, so it is the one most worth
being able to take back, and it is the only one that expires. Nothing in D113 asked for that;
the difference was never decided.

## 3. What already exists, before anything is designed

**`OrderLineProgress.pulled` IS ALREADY ON THE WIRE, ALREADY THE RIGHT SHAPE, AND ALREADY
DRAWN AS A COUNT.** `app/src/types.ts:3188`:

```ts
export type OrderPulledCopy = { capture_id: string; box: number | null; index: number | null }
```

That is `PullTarget`'s tuple. `types.ts:2844` describes the field as *"Where each recorded
copy sits RIGHT NOW, joined at read time off its capture id and stored nowhere."* Every copy
`undoPull` would need is on the screen's own data today.

**`#/orders` DRAWS IT AS A SENTENCE AND THROWS THE LIST AWAY.** `Orders.tsx:4117` renders
*"N copies have already been pulled for this order and left the box"*, and `LineFigureView`
renders *"N already pulled"*. The comment above the first argues the present shape honestly:
*"a pulled copy is sold, so it has left the box and has no drawer to walk to; the ledger's own
count is the honest form of it."* The count is honest. It is also the whole of the reach.

**`#/graveyard` ALREADY NAMES THE ORDER A DEPARTED CARD WENT TO.** `DepartedCard.order` is
the `holder_of` join, best-effort, and `#/graveyard` is read-only by D134.

**NOTHING RESEMBLING A RECEIPT LOG EXISTS, AND NOTHING SHOULD BE BUILT.** `history.jsonl` is
position-keyed, has no route, and is read only to compute `restores_to`. A new log would be a
second spelling of `LineProgress.copies`, which is already the log this asks for.

## 4. The three candidates, weighed

### The order's own row on the buyer list — RECOMMENDED

The record lives on the line, so the control belongs on the line. This is D57's sentence
applied one screen over: the button becomes the way back. It costs no new storage, no new
route and no new wire field — the count at `Orders.tsx:4117` becomes a list, and each entry
carries its own `Undo` over the tuple it is already holding.

It also repairs the asymmetry in §2 by construction: all three of D113's reversals then sit
in one place, under one rule about how long they stay offered.

### The card's row on `#/inventory` — REJECTED AS THE HOME, REQUIRED AS A GUARD

`SearchCopy` carries `capture_id`, `box`, `index`, `state` and `state_at`, so the tuple is
there. Three things rule it out as the place the undo lives:

- **Sold is hidden by default** (D132), so the control would be behind a filter on a screen
  whose job is what is on hand.
- **`SearchCopy` cannot tell a pull-sale from a hand-sale.** It carries no `held_by`. The
  screen has no way to draw the distinction the control depends on.
- **The write it offers is the wrong one.** `#/inventory`'s undo reverses the SALE. The
  ledger's `fulfilled` and `copies` are untouched by it.

**That last point is a live correctness defect, and it is worse than the one this file was
opened for.** `POST /inventory/<box>/<index>/sold` with `{"undo": true}` consults
`_sale_origin` and nothing else — `holder_of` is called in exactly three places in
`server/capture_server.py` (the graveyard's two joins and `_ledger_pull`), and none of them
is the sale route. So today: pull a copy, wait out the toast, find the card on `#/inventory`
with sold shown, press `Undo`. The card returns to the shelf as `identified`, live and
offered to the next buyer, while the order still reads that copy as fulfilled. That is the
double-shipment D113's `record_pull` requires a `capture_id` to prevent, reached from the
other end.

**The repair is a refusal, not a control.** The sale undo learns `holder_of`, and refuses
`copy_pulled_for_order` when a line holds the copy, naming the order and pointing at it —
the exact mirror of `pull_not_recorded`, whose text already sends the operator the other way
(*"If it was marked sold on #/inventory, reverse it there"*). One direction has had that
signpost since D113. The other has never had it.

### A short receipt log — REJECTED

A new surface answering a question `LineProgress.copies` already answers, with its own
retention rule, its own route and its own screen. It is the answer to reach for if the
recommended one turns out not to be reachable, and nothing found here suggests that.

## 5. The design

### On `#/orders`

The pulled-copies sentence becomes a list, one row per copy, under the line it belongs to.
Each row says the card and where it came from, in the operator's words, and carries `Undo`.

- **No clock.** The row is offered for as long as the ledger holds the copy, which is
  `forget_pull`'s own ruling. The toast keeps its twenty seconds as the fast path for the
  press that was just made; it stops being the only path.
- **Nothing re-ranks on an undo.** D181 and D118's rule: the list order is taken once and a
  reversal may not retake it. An undone row stays where it is and draws its new state.
- **The rows reserve the height of their tallest state** (D118), so the sentence-to-list
  change and the undo's own state change move nothing around them.
- **A copy whose `box` or `index` is null gets no `Undo`** and says why in a sentence. The
  card is gone — its box was deleted, or the record was buried — and there is no position to
  put it back to. `#/graveyard` is where it is read.
- **The register rule holds** (D196): the rows say the card's name and the drawer, never a
  capture id, a route or a reason code.

### On `#/fulfillment`

**No new control.** The Fulfiller is one person doing one job with no shell and no route out
(D5). A list of past pulls with reversals on it is owner work, and putting it on his screen
would be the D31 mistake with the personas swapped. His toast keeps its twenty seconds
unchanged; the owner's reach on `#/orders` covers what the toast drops.

### On `#/inventory`

**The guard in §4, and nothing else.** No control is added.

### On `#/graveyard`

**Unchanged.** It already names the order and is read-only by D134.

## 6. What this does not do

- **It does not widen D28.** That entry punched a window in `Queue.upsert`'s refusal, and
  the window is the hole rather than the rule. The ledger has no equivalent refusal to
  soften: `forget_pull` is an ordinary supported write with no clock of its own.
- **It does not touch the pull.** `record_pull`, its refusals and its receipt are unchanged.
- **It does not re-plan anything.** An undo restores a copy to the shelf; whether that
  changes a walk is the walk's own question and the order-walk plan's freeze rule answers it.
- **It does not add a storage field.** Every value it draws is already on the wire.

## 7. What would have to be verified

- The three widths and both themes, per this repo's screen rule.
- **The `#/inventory` guard is mutation-tested against the divergence it prevents**: pull a
  copy, undo the sale, and assert the refusal. A guard that has not gone red on its own
  defect is not a guard.
- **`app/tests/copy-budget.json`'s ceiling for `#/orders`** (D194). This adds rows to a
  screen under a word ceiling that only goes down. The list replaces a sentence, so the
  arithmetic is not obviously against it, but it is measured and reported either way, and
  never pinned quietly.
- The undo's own refusals reach the screen as sentences: `pull_not_recorded` and
  `pull_spans_lines` both exist and neither has a reader on this path today.

## 8. The question for the owner

**Does the pulled-copy list sit open under the line, or behind a disclosure?**

`#/orders` is already dense and D208 ruled that the pricing screen discloses progressively.
A line with three pulled copies gains three rows. The recommendation is **open**, because a
folded reversal is most of the way back to a reversal nobody can find, and because the rows
replace a sentence that was already drawn. If the measured word count argues otherwise, the
disclosure is the fallback and the ceiling is what decides it.
