# D329 — A press that is taken but must wait says so at once

**A press that the app accepts but cannot act on yet answers on screen the moment it is pressed.** It keeps that answer until it runs, and never waits silently for the write it is queued behind.

Kind: build
Plan: D329#the-rule (web)

**Why.** Bug 9 of the Orders plumbing hunt. On the Orders walk, U pressed while a Mark Sold is still saving is queued. Once the sale lands, U undoes that sale, as the undo spec's section 10 rules. But the screen showed nothing for about 560 ms, measured on main with the sale held for 600 ms. A press with no answer reads as a press that was lost, and the reader presses again.

## The rule

- Any press that the app takes and queues behind another write shows a queued state on the control or row it acts on. The state lasts from the press until the press runs. Then the usual result (a receipt, a refusal or a no-answer message) replaces it.
- A queued press whose target is gone when it runs is skipped, with no write.
- The queued state is one shared primitive, used by every screen. No screen builds its own. A new press that queues behind a write uses it too.
- The wording and the look come from the design system (`--bn-*` tokens only), and are checked at 1440 and 820, in light and dark.

## Home and users

- Home: `app/src/writeLine.ts`, one write line per screen (module level, so a write outlives the screen that pressed it). `queueWrite` adds a write, `isQueued` and `writeOut` read the line, `sayQueued` gives the shared words, and `cancel` drops a write still waiting.
- Users now:
  - Orders walk: U and the toast Undo (`WALK_LINE`, `app/src/OrdersWalkPane.tsx`).
  - Inventory: U and the toast Undo (`app/src/Inventory.tsx`).
  - Review: U (`app/src/ReviewQueue.tsx`).
  - Fulfillment: Undo on the receipt and on the Pulled today rows (`app/src/Fulfillment.tsx`).

**Ruled by.** The owner, on the bug 9 question: answer at once, and build it as a shared path, not for Orders alone.
