## D57 — The sale is one press, and the button becomes the way back

**Mark-sold writes on one press, and the row's control becomes `Undo` for twenty seconds.** Built 2026-08-30 on the owner's instruction, on `#/inventory` only.

**This honors `docs/DESIGN.md`'s headline rule rather than carving an exception out of it.** That file bans a confirm dialog on a reversible action and has specified one-tap mark-sold since it was written. A sale is the most reversible write in the product — one route, two directions, no expiry, no listing hold — and it was the only one carrying a modal. D28 fixed the same asymmetry from the other side by giving the review answer an undo; every guard D28 added stays.

### The modal's photograph was redundant

`Inventory.tsx`'s panel confirmed identity rather than intent, and said so in its own comment: the question was *is the card in your hand the card at this position*, which only a photograph answers. D38 overtook it by drawing the selected copy's photograph at 449x627 on the same screen.

- **Exact** for the row the walk points at (`aria-current`) — same bytes, same position, one panel over.
- **Approximate** for a second copy of the same SKU in another box: same card face, different slot. D45 makes that copy's own photograph one press away, because the position label is a control that walks the browse to it.

The check is demoted from mandatory to available, not deleted.

### Undo appears twice, and the second one is not redundant

| site | why |
|---|---|
| the row's slot | where the press was and where the eye is |
| the screen receipt | the only one that survives unmount, and the only one that can explain a refusal |

Copy rows unmount on three paths — stepping the walk, a query matching nothing, and a failed re-read, since `useSearch` clears its results on failure. The twenty-second clock stops for none of them, which is why `Inventory.tsx` and `BoxBrowse.css` have both argued that the promise has to outlive the list. `app/tests/inventory.spec.ts` asserts it by selling a copy and then stepping the walk.

`already_sold` and `sold_origin_unknown` return `canUndo: false`, so the row draws the plain word `sold`. The sentence saying why there is no way back needs prose, and a 32px slot has none.

**Accessible names differ deliberately:** the receipt's is `Undo <place>` and the row's is `Undo the sale at <place>`. Identical names would leave a screen reader unable to tell one sale's two ways back from two different sales. The visible word is `Undo` on both.

**No `Retire` sits beside it**, because the server refuses to retire a sold card and the control could only fail.

**It renders inside the `sold` branch, which is forced rather than stylistic.** `doSell` sets the optimistic `soldKeys` overlay in the same continuation as the receipt, so the next render is already past the sold guard and a branch above it would be unreachable.

### Retirement is unchanged, and the asymmetry is the ruling

D26's write keeps its panel, its photograph and its receipt-only undo. A retirement without a reason is refused (`retire_reason_invalid`), so its four reason buttons are the write's only input rather than an acknowledgement to dismiss. This entry removed a press that asked an already-answered question; that panel asks one with four answers.

### Overshoot

**The guard is `busyKey` and nothing else**, which is the owner's choice over displacing the control. `Fulfillment.css` records the opposite ruling for the same failure one screen over, and it was earned: `Pull` and `Mark sold` occupied one position one state apart, so a double-tap sold a card whose photo was never seen. `app/tests/fulfillment.spec.ts` measures those two rectangles.

What covers it here, in descending order of worth: every control in the slot is disabled while a write is in flight and `doSell` returns early besides; the slot shrinks to one right-packed control, vacating the coordinate `Mark sold` occupied; and a receipt appearing above pushes the copies list down. **What does not cover it is the busy gate**, which against a local server reopens in milliseconds and does not span a human double-tap.

**Two residual risks, named so they are not found as surprises.** `Mark sold` is an ordinary `<button>` in the tab order, so Tab-then-Enter now writes where it used to open a modal, and a held Enter can oscillate sell to `Undo` to sell. Neither is reachable from a key binding: `BoxBrowse`'s window handler navigates and writes nothing, and `App.tsx`'s leader chord only sets a hash. The slot's two-controls-to-one change replaces the DOM node, so focus falls to `<body>` and a held Enter stops; the arrow keys still walk, because that listener is on `window`.

### Consequences

- **It overturns `docs/specs/order-flow.md` §13**, which forbids a second sale path without both guards. One guard is dismissed on the owner's ruling, and §8.1's argument survives intact: the guards belong to the write rather than to the Fulfillment view, and nothing in D5 says the owner may have the write without them. `#/fulfillment` is untouched, per D31.
- **It is a client change only.** `POST /inventory/<box>/<index>/sold` already took `{}` and `{"undo": true}` on one path and already answered `restores_to`. Store, harness and every Python test are unaffected.
- **The accent fill left the screen with the panel**, and `Inventory.css` records why. `docs/DESIGN.md` says where a fill may go, never that a screen must have one; `#/runs` draws none either.

**The change was makeable with every check green, which is worth more than the feature.** `app/tests/inventory.spec.ts` asserted only that `Mark sold` and `Retire` were visible and never pressed either, so the confirm panel, the receipt, the undo window, `canUndo` and the `already_sold` path were entirely unasserted, and `open()` did not even stub the sale route. Six cases now cover it. Three mutations were observed failing before they were kept: dropping the `canUndo` filter, never drawing the row's `Undo`, and a press that writes nothing.

**What would reopen this: a sale recorded against a copy the owner did not mean.** The fix to reach for is `.fulfillment-step`'s displacement, not the panel this replaced.
---

### Amended 2026-09-25: the row's Undo has no clock

The owner's ruling of 2026-09-25, verbatim: "Switch all five (Recommended)". The row's control stays `Undo` past twenty seconds. It lasts until a newer sale replaces it, or until the sale is built on. That is when its order ships or closes, its photograph is reclaimed, or its box is buried. `docs/specs/undo.md` section 11 is the plan, and UN-5 builds it.
