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

The owner saw the rebuilt screen over a seeded store beside `#/inventory` and ruled four things. The copy budget is pinned to the measured count, because D194's ratchet accepts Inventory's Details vocabulary on Orders. `so far` is dropped from the position caption everywhere, on the box line and the section line, on every screen. `market` and `listings` shipped with their empty states on Orders at the time (see the amendment below, which reverses this one). The pill's word is `Ready`.

### What this protects, and what protected it before

One pane means one place where a card's copies, position and details are drawn. It also means one set of words the owner has to learn. Before this, each walk build protected the same outcome with its own component, and each drifted from inventory within a day. Now `app/tests/orders.spec.ts` asserts that the pane's classes are inventory's own and that `#/inventory` renders unchanged. It also asserts that a click selects and starts, and that a tick joins live. It asserts that a sale does not re-sort the walk, and that the prohibited words are absent.

### What is still open

Which order a press records against when one card serves several buyers is answered by D212. No order claims a copy, and the write is the only refusal. D96's lost pass figure stays open in the spec. Amended 2026-09-19: the filter strip became a native dropdown on the owner's word, and its place at 390 is discharged with it. The selected order's text in the pane's top-right corner was dropped by the owner the same day.

### Amended 2026-09-20: the nameless buyer's own label, and four small readings fixed with it

Three places drew a nameless buyer's NAME slot as `No name` then a typed dot then the order's own full id. This typed the separator D218 refuses. It also repeated the full order id twice, once in the number slot and once in the name slot.

**The name slot now reads `MM-DD-YY_XXXXX`.** That is the group's own `latest` placed date in UTC, an underscore, then the last five characters of the group's most recent order id. UTC keeps the label stable across viewers. `app/src/orderView.ts:unnamedBuyerLabel` composes it. `BuyerRow`, `OrderPanel`, the phone rail chip and the Manage sheet's title all read it now, instead of building the same string apart. It takes the mono face (D221). A composed id is a machine string, the same reason a SKU takes it.

A nameless group can only ever hold one order. `orderBuyers.ts` keys a nameless order on itself. It never merges two. "Several orders, several dates" cannot happen today. The helper still falls back to the most recent order if that changes. That is the same order `latest` is already computed across. A shorter id draws whole, never padded. The full id stays in the order slot alone. It is never repeated here (`OrderPanel`'s `ORDER <number>` / `<n> ORDERS`).

Landing this also surfaced four small readings on the same screen. Each was fixed in the same pass. A buyer row's per-order pill drew the order's own number, not its status word. "Hide unknown SKUs" named the wrong reason. It filters `sku_unseen`, the "Never seen" chip's own reason. It never filtered `sku_unknown`. "Tick all" and "Untick all" over-claimed their reach. Both act on the rows in view. Both now read "Tick shown" and "Untick shown", matching `#/inventory`'s own wording. "Untick shown" also read the wrong set for its disabled state. The step-through arrow-key hint rendered below phone width, where its handler is gated off.

### Amended 2026-09-20: market and listings are wired, by the same path Inventory uses

The owner reversed the "ship as is" ruling above. He asked for `market` and `listings` on Orders. He asked for them by the path Inventory already uses. This entry is amended to say so.

`WalkMainPane` now reads both facts the same way `BoxBrowse.tsx` reads them. `Orders.tsx` threads `listings` from the free third face of the copies read that already answers `rawCards`. No second fetch is made for it. The walk pane keeps a per-run market cache, copied from Inventory's own `priced`/`asked` pair. It is keyed on the current row's real card. A copy whose run is null never asks for a reading.

The copies route, `POST /inventory/copies`, now answers `listings` too. It is narrowed to the SKUs the route's own scan matched. `GET /inventory/<box>` narrows its own `listings` the same way. This is a dictionary lookup over data the route already read. It is not a new scan. The `unscoped walk` allow list is unchanged.

The measured word count on `#/orders` did not move. The pinned fixture prices no stock key its cards carry. The wiring reaches no new string on that fixture. D194's ratchet stays at its measured figure.

D189 is not adopted here. It puts the market reading in a table. This amendment keeps the per-run live read Inventory already uses. The ask was parity with Inventory's own path. It was not a switch to the newer one.
