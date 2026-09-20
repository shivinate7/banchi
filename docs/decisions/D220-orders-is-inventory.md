## D220 — Orders is inventory's screen with orders in the rail, and the walk is a mode of it

**The owner's ruling, 2026-09-19, verbatim:**

```
Orders gets inventory's exact structure/layout skeleton, except the left column becomes
all the orders, and when I select an order it immediately starts that order's walk, with
the option to hit ticks to the side so I can select multiple and then walk. Then in order
walk it's sorted by density.
```

The full specification is `docs/specs/order-walk-plan.md` §13. This entry records why the screen is built that way and what it supersedes.

### What was built three times, and why each was wrong

Three builds in two days took inventory's frame and not its engine. Section 8's stop, section 9a's findings row, and the rebuilt stop on `CardLocations` (#406) each drew a walk-specific component. A stop header, a take row, a bar, a pill. The owner saw the third on the live store and rejected all of it. He could not see where every copy of a card was. The words on the screen (`identified`, `pull`, `drawer`) were nowhere else in the app.

D90 had the shape right in 2026-08. An order drives the walk as a mode of the inventory screen. D96 deleted it on the interview's word. The owner overruled that deletion. He did not restore D90 verbatim: "do not just bring d90 back, take into account what I'm saying right now."

### The decision

**`#/orders` is `#/inventory`'s skeleton with orders where the boxes are.** Two sidebar items, two independent screens. Inventory is untouched. In the rail, the orders list sits where the box list was, one tick beside each row. The order panel sits where the box panel was: label, buyer, `Manage`, status pill, an owed/sold/short triad, a bar, the placed date. The walk sits where the section list was, boxes and sections in density order. Clicking an order starts its walk at once. Ticking a second order while in the first widens the walk live to both. There is no Start button. Fetch, paste, the status picker and the stand-downs sit behind the panel's `Manage`.

**The main pane is inventory's card pane, one component, reused whole.** `app/src/CardHero.tsx` holds the hero head, the framed photograph and the Details fold. They moved out of `BoxBrowse.tsx`, and both screens import them. `Mark sold` is the button and the word. On this screen it also records the copy against an owing order (D212). What the walk needs and the pane does not draw is added to inventory, and both screens get it.

**Inventory's words, only.** `drawer`, `pull`, `stop`, `take` and `all pulled` do not appear. The order pill reads `Ready`. No string types a middle dot (D218).

**`OrdersWalk.tsx` and its sheet are deleted, not adapted.** The density route and the #406 wire (`WalkPlanCopy` with `key`, `place`, `here`) stay. They feed only the walk list's order and the pane's landing.

### Four answers after the second render

The owner saw the rebuilt screen over a seeded store beside `#/inventory` and ruled four things. The copy budget is pinned to the measured count, because D194's ratchet accepts Inventory's Details vocabulary on Orders. `so far` is dropped from the position caption everywhere, on the box line and the section line, on every screen. `market` and `listings` ship with their empty states on Orders. The pill's word is `Ready`.

### What this protects, and what protected it before

One pane means one place where a card's copies, position and details are drawn. It also means one set of words the owner has to learn. Before this, each walk build protected the same outcome with its own component, and each drifted from inventory within a day. Now `app/tests/orders.spec.ts` asserts that the pane's classes are inventory's own and that `#/inventory` renders unchanged. It also asserts that a click selects and starts, and that a tick joins live. It asserts that a sale does not re-sort the walk, and that the prohibited words are absent.

### What is still open

Which order a press records against when one card serves several buyers is answered by D212. No order claims a copy, and the write is the only refusal. D96's lost pass figure stays open in the spec. Amended 2026-09-19: the filter strip became a native dropdown on the owner's word, and its place at 390 is discharged with it. The selected order's text in the pane's top-right corner was dropped by the owner the same day.
