## D118 — A press never moves other content

**A control's response is the product's, not each screen's. It covers what the page does around the press.** The owner ruled that nothing on screen moves when a button is pressed, anywhere in the product. The trigger was screen shake when marking a card sold in `#/inventory`.

D50's three floors (cursor, hover easing, press dip) are in `app/tests/cursor.spec.ts`. None of them checks what moves. A control can obey all three and still sit in a panel that collapses 98px on press.

### Measured at 1440x900 against a seeded store

| press | what moved |
|---|---|
| `Mark sold` on `#/inventory` | the card panel collapsed **98px**; **131 elements** moved |
| stepping the walk one card | **39, 66 or 98px**, depending on the two cards |
| every other route swept (review, pricing, orders, runs) | 0 |

Three things in one panel were sized by the card's own state. A write changes that state.

- **The position lens, 85px.** A departed copy draws no lens (D68). The lens vanished on the sale and returned when the walk stepped onto a placed copy.
- **The action slot, 18px.** `Mark sold` and `Retire` need 40px. The receipt needs 50px. The `Sold` pill needs 22px. The slot took whatever the current state needed.
- **The copies list.** A card with copies makes the panel taller. Each card in the box had a different panel height.

A fourth cause was found by the guard. `.browse-row` in the walk declares three grid columns, but it can draw four children. A sold copy's badge landed on a second grid row. A walk row is 32px before the sale and **50px** after it. That pushed every row below it 18px down the list.

### The lens stays and its mark leaves (amends D68 and D41)

The owner ruled that a departed copy fills the row its lens used to occupy. The fill is a sentence or, better, an animation. **D68 carries the reversal in its own second amendment.**

D68 deleted an empty track with an unknown-position caption. That is not the object this entry puts back. The picture is still of the BOX, and the box stays. The section the copy left is still drawn. Its caption reads `no longer in the box`. The second scale reads `Section 1 · 10 slots · this copy is not in one`. Only the MARK is removed. It is the only part that would lie about a position. D58's refusal of a slot number for a departed card stands. D41's void where the figure would be stands.

The mark leaves by animation, not by deletion. `PositionBar` keeps the mark mounted through the write, with `data-gone`. It holds the `left` it last stood at in a ref. It eases the mark out and down over `--bn-t-slow`. The section fades to a muted ground. A deleted node cannot animate.

Three assertions in two specs said `toHaveCount(0)` for that bar. They now assert the opposite. They are amended in place with the argument. A later reader sees a reversal, not drift.

### One height for the whole walk

`.browse-band` has a fixed height in its two-column form. The copies list scrolls inside it: `min(720px, max(520px, calc(100dvh - 280px)))`. The height is bounded by the viewport, not by the card. Every other candidate for the number depends on the selected card. That dependence was the movement.

The copies list absorbs the difference, because it is the only part of the band that is a list. Its bottom edge fades. `BoxBrowse.css`'s own scroller uses the same fade. A clipped row with no fade looks like a rendering fault.

**Cost:** a card with more copies than the band holds shows about one and a half rows before it scrolls. The owner chose that trade over the panel changing size on every step.

**Protects:** `.browse-shot` is `align-self: start`. A grid cell that stretches to a fixed band is D38's `.browse-frame` defect again. `inventory.spec.ts`'s "never a card-shaped hole" case failed by 192px when this height landed without that rule.

### The press was on two clocks

`base.css`'s press floor sets `translate: 0 1px` on the frame the finger goes down. Three rules also eased the movement on that same press. `.bn-btn` transitioned `transform`, where its `scale(0.99)` lives. So every button dipped instantly. It eased into the squeeze over 120ms, then released the same way in reverse. `.pull-confirm` and `.bn-tab-link .bn-icon` did the same. The last one used a 200ms spring.

**The rule is a pair, not a ban on one property.** A control may ease a `transform`. `.pull-confirm`'s hover lift is one. A lift answers the pointer arriving, not the finger landing. A control may not ease the movement its own `:active` rule makes. The two controls that need both name their repaints inside the `:active` rule. They leave the movement out of the list.

### What guards it

Two cases in `cursor.spec.ts` cover the half the stylesheets show:

- *a pointer state repaints a control and never re-lays it out.* It checks every `:hover`, `:active` and `:focus` rule across the eleven routes. It flags any rule that declares a layout longhand. **The declaration convicts. A rendered element can only acquit it.** A rule whose selector matches nothing is still checked.
- *a press lands on one frame.* It flags an `:active` rule that moves the control. The rule carries no `transition` of its own, and it matches an element that eases that property.

The first draft skipped a rule whose selector matched nothing. A mutation that put the real defect back passed under it. This worktree's empty store draws no `#/codes` task card.

Two more cases in `inventory.spec.ts` cover what the panel does when a write lands:

- *the press that sells a copy moves nothing outside the panel it lands in.* A sweep checks every element outside `.browse-card`. It checks the document height, the scroll, and the heights of the location card and the copy row. The sweep compares page coordinates, not viewport coordinates. Playwright scrolls a control into view before it clicks. Viewport coordinates would report all 192 elements as moved.
- *the card panel holds one height for the whole walk.*

Ten mutations, one per fix. Two found holes. `sellableStore()` moved `state` and nothing else. It served a sold card still in its slot, which the server cannot produce. Deleting the departed lens outright left the sale case green.

### What is left, and why

**A copy an open order was waiting on still moves the panel's contents by 46px when it is sold.** `wantedOf` names only copies still on hand, and the claim line goes with it. That is `Inventory.tsx`'s documented behavior: a pulled copy already reads `Sold`. Reserving 46px of blank on every unclaimed card would hold a line that is usually absent. That is padding, not stability. **Nothing outside the panel moves for it.** That is the floor this entry sets.

**What would reopen this:** a card whose copies list is long enough that one and a half visible rows is the wrong trade. Or an operator who would rather the panel grew than scrolled.

### Platform floor: `make design-check` runs in CI

`make design-check` is a job in `.github/workflows/check.yml`. It runs on `pull_request` and on `push: main`. Before that job, it ran in neither `make check` nor CI. Every floor in this entry fired only when a person typed the command on one Mac. That covers D50's three, D117's thumb floor and the Fulfiller's contractual constraints.

The job is separate, not a step in `check`. A chromium install is a real cost. A red `check` and a red `design-check` make claims about different things. The job has no `scripts/checks.py` entry, because `check registry` refuses an entry for a target that `make check` does not run.

**The cost is D136's.** Measured over 56 jobs before D136: 940 to 1,020s wall-clock per run. The output was `481 passed (15.2m)` on one worker. A private repo's `ubuntu-latest` has two vCPUs. Playwright's default floors to one worker. The job runs three shards of one worker each. The seven real-clock sleeps use a fake clock. The post-merge run is skipped when the tree already passed on the PR. Current figures are in D136.

**The first CI run went red on the sale case.** The rig had passed that tree 166 times. The walk row's slot cell is `minmax(34px, max-content)`. A sale rewrites `#1` to the store key `B2 #1`, in the mono face (D68). The key is wider. The column grows, and the name and badges slide right on the press. `B2 #1` sets at **33.0px in macOS's monospace fallback** and at **over 34px on Linux**. The column floor is 34px. One platform hid the movement. The other reported it as one pixel.

The pixel was a symptom. `B2 #1` is the shortest key a store can produce. `B3 #96` is 40px. `B12 #133` is 46px. Those sales moved the name six and twelve pixels on **both** platforms. The case never saw them. Its fixture walks the one box whose key fits under the floor. A tolerance would hide the one small measurement and leave every larger one unguarded.

**The fix reserves the width before the sale spends it.** `.browse-row-slotghost` is an `aria-hidden` span. Its `::before` carries the future key as `content: var(--bn-slot-key)`. It stacks in the same grid cell as the visible slot, in the face that `.is-departed` switches the cell to. The track is already that wide. The write changes only which of the two is painted.

The key is `content:`, not a text node. A hidden twin in the DOM would add `B2 #1` to every row's text. The census, the walk's locators and each row button's accessible name all read that text. The reservation uses the string, not a `ch` count. A face with synthesized weight does not set five characters at five times the advance of `0`.

**Cost:** a row whose key is wider than its slot number starts its name further right. A long name ellipsises one word sooner. The cost is paid once at render, not at the sale. Looked at in both themes at 1440: the names now align down the list, where before the departed row's name sat out of line with its neighbors.

**Guard:** a third case in `inventory.spec.ts`. Its subject is *the slot column is already as wide as the key the sale will write into it*. It has its own one-card fixture in box 12, card 133. The existing case could not see this. Its sweep records position and height, not width. Its box is the one whose key fits under the floor. The new case first reads its subject: the key must clear 34px, measured on the state the sale leaves. It was mutation-tested with the reservation deleted.

### The same sentence on a second axis, which none of these guards can see

A press changes what is on the screen, never where the rest of it is. That is a claim about order as well as pixels. The guards above measure only pixels.

`D181` is the entry. Marking a copy sold under a search reordered the rankings in front of the operator. The operator was marking several copies as sold.

Why the four guards in this entry were silent: `cursor.spec.ts`'s cases read the stylesheets, and a reshuffle is not a CSS rule. The sweep in `inventory.spec.ts` records every element outside `.browse-card` by a stable id and its rectangle. The copies list is inside that panel. The rows a re-rank exchanges are identically shaped boxes. Swap two of them, and every rectangle stays where it was. The document height and the scroll do not move.

So the proof compares the IDENTITY of the rows, not their geometry. It compares the ordered list of each row's `aria-label`. That label names the copy drawn there. The comparison runs in both directions. The fixture makes a frozen order and a recomputed order give different answers. `toHaveCount` cannot see a reshuffle that keeps the length.

The control that fixes this is bound by this entry in the usual way. It appears on the press that makes the order stale. It sits inside a band with a fixed height, so its slot is reserved whether or not it is shown. This is the same bargain `.browse-row-slotghost` makes. It is paid once at render, not at the moment of the sale.

### The copies column may not be torn down and built again

**The owner ruled that the CI flake is a product defect, and that the product gets fixed.** The same failure had shown on the real rig for weeks.

`inventory.spec.ts`'s "a new search takes a new order" case failed on CI in 3 of 20 runs, at 2 workers, always the same way. `toHaveCount(6)` passed. A later read of the same rows, without retries, returned `[]`. No press was involved. The operator had typed a second query into the same box.

The earlier `answered`-ref change and the `BoxBrowse.tsx` change were reverted. The `answered` change named a ref from a trace that was never reproduced. Both changes passed with the defect present, under an ordering that does reproduce it. The `BoxBrowse.tsx` change recorded a query on a render whose `visible` was empty. That spent `fresh` on a landing that never happened. That is D132's rule failing to fire.

**The column was destroyed and built again from nothing.** It was never a re-point. `CopiesPanel` owns a `useSearch()`. Rebuilding it discards the answer on screen. It then starts a 200ms debounce and a fetch. The operator saw six copy rows, then a skeleton, then six rows again, with no press. Two mechanisms caused the rebuild.

- **One: the walk's row read null while the new drawer was in flight.** Since D192, `rows` holds ONE drawer's cards. `visible` is `rows` narrowed to `shelf`. A fresh answer can move `shelf` to another drawer. Until that drawer's `GET /inventory/<box>` lands, `visible` holds nothing for it. `selectedRow` was `visible.find(...) ?? null`. So `Inventory.tsx`'s `detail` became null, and the whole column unmounted. The fix treats a row as gone only when its drawer has answered. `rowsShelf` becomes state, so the render can read it. The walk keeps the row it stands on across that window. Null remains for the honest case: the shelf has answered and holds no row to walk. The render where the rows land follows the same rule. At that render, `selected` still holds the previous drawer's key.
- **Two: `.browse-card` carried `key={selectedRow.key}`.** The key came in with the rebuild (D94 to D99). The `bn-page-in` entrance replayed on every card. `{detail}`, the copies column, sits inside that section. So the key rebuilt the column on every change of selection. That included the change a fresh answer makes. Every guard in `CopiesPanel` for a row change assumes that the column survives one. This key is why none of those guards ever ran. The key is removed. The entrance now plays when the panel appears. `CardOps` keeps its own key. That key resets a menu, not a fetch.

**Measured on the rig.** Every box read was delayed 400ms, and the CPU was throttled 6x (D128's lever). The column was absent for 679ms. It returned as the skeleton for 400ms more. With both fixes, the copies list holds six rows on every animation frame, from the keystroke to the settled order.

**Guard: a frame watch, not a poll.** Every `expect(locator)` retries until it is true, then stops. A list that empties and fills between two polls is invisible to all of them. `installCopiesWatch` samples `requestAnimationFrame`. It records three numbers per frame: the copy rows, whether `.inventory-detail` exists, and whether a skeleton is inside it. The first is what the operator counts. The second catches a tear-down. The third catches a rebuild.

The case *the copies list holds while a new answer moves the walk to another drawer* delays the drawer read by 400ms. The order is then certain on any machine. A delay cannot make a passing build fail. It holds open the window the product must survive. Restoring the key draws `column=1 skeleton=2`. Dropping the held row draws `column=0`.

### The hold was too wide: a press is not a re-rank

Review caught this before merge. The fix above held `selectedRow` across every shelf change. That is wider than the case it covers. A fresh search answer can move the walk to another drawer with no press behind it (D132). The hold exists for that case. A press to a different drawer has the same shape. So does a walk-to a copy elsewhere. The operator asked for a different card on purpose. The hold drew box 2's card under a `Box 7` header, with `CardOps` live against it. The list said "Nothing in box 7 yet" when the box held three cards.

Proved live: box 2 to box 7, with `/inventory/7` delayed 1500ms. The header said Box 7. The list said the box was empty. The detail column kept box 2's card.

The fix: `shelfSource` records why `shelf` last moved. It is a ref beside `shelfAnswered`. A press (`selectShelf`) marks it `'manual'`. So does a walk-to, which is both `setShelf` calls in the jump effect. Only the effect that re-ranks the walk under a fresh search answer marks it `'search'`. `selectedRow`'s hold reads this ref. It holds the old row only when the move was a search re-rank. A press or a walk-to falls straight to `null`. The panel blanks rather than show another box's card.

The same false claim appeared in two more places. The walk list's "Nothing in box N yet" and the detail column's empty state both read `visible.length === 0`. Neither checked why the list was empty. Both are now also gated on `awaitingRows`: the shelf's own rows have not landed. This gate applies whatever the source of the move. An honest "nothing here" needs the shelf to have answered. Going stale is not enough.

**Guard: a one-shot in-page snapshot, not a retrying `expect`.** A `toHaveCount` polls until it is true or times out. A false claim that clears when the delayed `GET /inventory/7` lands would let the assertion settle after the fact. That proves the DOM healed. It never proves the false state was drawn. `inventory.spec.ts`'s `a press to another drawer never draws its predecessor's card while the fetch is in flight` takes one `page.evaluate` right after the click. It runs before anything waits on the network. It reads the box cell's `aria-current`, the `.browse-card` count, box 2's photo alt text, the false-claim sentence in both capitalisations, and the `.browse-empty` count.

Reverting the `shelfSource` gate draws a `.browse-card` count of 1. Reverting either empty-state gate draws the false claim as `true`.

### Blank was the defect: the previous drawer stays, dimmed

**The owner ruled on the fix above.** It fell to `null` for a press or a walk-to. The window showed no row, no rows, no sentence and no spinner. It runs up to about 1.5 seconds on a slow store. The ruling: keep the previous drawer's rows on screen, dimmed, until the new answer lands. Do this in both the walk list and the copies column. No new visible words are added. `copy-budget.json` holds.

**Blank is not neutral.** An empty pane during a press reads as a fault, not a wait. The earlier fix traded one wrong claim for a different cost.

**What is held.** `held` already kept the last found row in `visible` for a search re-rank. Two more refs join it. `heldSections` keeps the list's last answered `sections`. `heldDetail` keeps the `{detail}` prop from `Inventory.tsx`'s `CopiesPanel`. All three write only when the render is not `awaitingRows`. None can hold a partial or in-flight answer. Each holds only a box that fully answered.

**Dimmed is not a smaller a4f3594b claim.** Box 2's row, drawn under a `Box 7` header, is literally the shape that regression named. What makes it safe is that it cannot be acted on.

**Dimmed is drawn, never claimed.** `.browse-list[aria-busy='true']` and `.browse-card[aria-busy='true']` (in BoxBrowse.css) drop to `--bn-disabled` opacity. That token marks content that is on screen but not live. Both set `pointer-events: none`. The list sets `tabIndex={-1}`. Its `onKeyDown` is not attached while dimmed. So the one keyboard path onto a stale row (`TICK_KEY`) cannot fire. `aria-busy="true"` stays on both regions for the whole wait. A screen reader is told the content is not final.

**No layout jump.** Neither region unmounts. The list keeps its node across the wait. The card panel's key does not change between the held row and the same row once it lands. Only a different card remounts `CardOps`.

The case *a press to another drawer dims its predecessor's rows* keeps the one-shot snapshot. It adds the computed `opacity` (under 1) and `pointerEvents` (`'none'`) of both elements. It also adds both `aria-busy` values (`'true'`), the list's `tabIndex` (`-1`), and the list's height. That height must match its value before the press. Box 2's row count and photograph still draw while held. The false-claim and `.browse-empty` checks stand.

### Review found a keyboard path around pointer-events, and an untested column

- **Finding 1, HIGH.** `pointer-events: none` blocks the mouse only. Tab still reached `CardOps`' "Card actions" button. Enter opened its menu on `held.current`, which is box 2's card, under the Box 7 header. That is the same regression a4f3594b named, reached by keyboard. **Fixed with `inert`.** The dimmed `<section className="browse-card">` carries `inert={dimPanel}`. React 19 supports `inert` as a boolean prop. `inert` removes the subtree from the tab order and refuses activation. It is not `panelRow`/`panelDetail`'s own subtree, and it carries interactive rows of its own. The list keeps its narrower fix (`tabIndex`, `onKeyDown`). It holds interactive rows that a blanket `inert` would also have to cover. **Guard:** the snapshot calls `.focus()` on the button directly. An `inert` subtree refuses a programmatic `.focus()`. The case asserts `cardInert` and `cardActionsFocusable`.
- **Finding 2, MEDIUM.** Mutating `panelDetail` back to the live `detail` left the case green. Nothing read `.browse-under`'s own content. `underOwnerCount` and `underRowCount` now read `.card-locations-owner` and `.card-locations-row` inside `.browse-under`. Both classes belong to `CopiesPanel` (`CardLocations.tsx`). The case now fails if the copies column draws nothing. It also fails if the column draws anything invented in place of the held card's real copies.

Both were mutation-tested with `.bak` copies, restored by hand. Reverting `inert={dimPanel}` to `inert={false}` draws `cardInert` false. Reading the live `detail` instead of `heldDetail.current` draws `underOwnerCount` 0.
