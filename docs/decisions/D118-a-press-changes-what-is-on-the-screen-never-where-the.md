## D118 — A press changes what is on the screen, never where the rest of it is

**A control's response is the product's, not each screen's — and that has to cover what the PAGE does around the press, not only what the control says to the pointer.** Built 2026-09-07 on the owner's report: *"I am getting a lot of screen shake when I am in inventory and am marking something sold, things should not be moving around when I hit buttons it's too janky — how do we resolve this (not just inventory, but any/everywhere)."*

D50 answered three questions about an interactive element — what the cursor says, whether a hover eases, whether the finger gets a dip — and `app/tests/cursor.spec.ts` guards all three. **None of them is about the thing the owner was looking at.** A control can obey every one of those floors and still sit in a panel that collapses 98px the moment its button is pressed.

### Measured first, at 1440x900 against a seeded store

| press | what moved |
|---|---|
| `Mark sold` on `#/inventory` | the card panel collapsed **98px**; **131 elements** moved |
| stepping the walk one card | **39, 66 or 98px**, depending on which two cards |
| every other route swept — review, pricing, orders, runs | 0 |

**The concentration was not a coincidence and it was not the button.** Three things in one panel were sized by the card's own state, and a write changes that state:

- **the position lens, 85px.** A departed copy drew none (D68), so the lens vanished on the press that sold the card and came back the moment the walk stepped onto a placed one.
- **the action slot, 18px.** `Mark sold` + `Retire` is 40px, the receipt is 50px, the `Sold` pill is 22px, and the slot was whatever the current one needed.
- **the copies list.** As long as the card has copies, so the panel was a different height for every card in the box.

**And a fourth, found by the guard rather than by the eye:** `.browse-row` in the walk declares three grid columns and can draw four children — the slot, the name, a departed badge and a queued one — so a sold copy's badge was auto-placed onto a second grid ROW. Measured: a walk row is 32px until the copy is sold and **50px** after, which pushed every row beneath it 18px down the list.

### The lens stays and its mark leaves, which amends D68

**This reopens D68 and D71 deliberately, on the owner's answer.** Asked how a departed copy should fill the row its lens used to occupy, they said *"a sentence or even better an animation"*. **D68 carries the reversal in its own second amendment** — that entry's bullet is marked in place and the argument for why the lens is not the mark is stated there, beside the ruling it changes, rather than only here.

D68 deleted an empty track captioned `where this sits in the box is not known yet` — its own words, *"a true sentence under an empty track that still reads as a measurement that failed"*. **That is not the object this entry puts back.** The picture is of the BOX, and the box is still there: the section the copy left is still drawn, the caption reads `no longer in the box`, the second scale reads `Section 1 · 10 slots · this copy is not in one`, and the one thing removed is the MARK — which is the only part that would lie about a position. D58's refusal of a slot number for a card that has left is untouched, and so is D71's void where the figure would be.

**The mark leaves rather than being deleted, and that is the animation.** `PositionBar` keeps it mounted through the write with `data-gone`, holding the `left` it last stood at in a ref, and eases it out and down over `--bn-t-slow` while the section it was in fades to a muted ground. A deleted node cannot animate; a node that stays can, and it is the same node the row's height depends on.

**Three assertions in two specs said `toHaveCount(0)` about that bar and now say the opposite.** They are amended in place with the argument rather than deleted, so a later session reads this as a reversal somebody made and not as drift.

### One height for the whole walk, which is the owner's second answer

**`.browse-band` takes a fixed height in its two-column form and the copies list scrolls inside it.** `min(720px, max(520px, calc(100dvh - 280px)))` — bounded by the VIEWPORT and not by the card, which is the whole point: every other candidate for the number is a fact about whichever card is selected, and that is what was moving.

The copies list is what absorbs the difference because it is the only part of the band that is a LIST; scrolling a location card or a photograph would not be ordinary. Its bottom edge fades, the same treatment and the same argument `BoxBrowse.css`'s own scroller already carries — a clipped row with no fade reads as a rendering fault.

**What it costs, named:** a card with more copies than the band holds shows about one and a half rows before it scrolls, where before the panel simply grew. The owner chose that trade over the panel changing size on every step. **What it protects:** `.browse-shot` is `align-self: start`, because a grid cell stretching to a fixed band is D38's `.browse-frame` defect by another name — that entry deleted a wrapper for exactly this reason, and `inventory.spec.ts`'s "never a card-shaped hole" case went red for 192px the first time this height landed without it.

### The press itself was on two clocks

`base.css`'s press floor lands `translate: 0 1px` on the frame the finger goes down and says so in its own comment. **Three rules then eased the movement they made on the same press**: `.bn-btn` transitioned `transform`, where its `scale(0.99)` lives, so every button in the product dipped instantly and eased into the squeeze over 120ms and released the two the same way in reverse; `.pull-confirm` and `.bn-tab-link .bn-icon` did the same, the latter over a 200ms spring.

**The rule is a pair, not a property ban.** A control may ease a `transform` — `.pull-confirm`'s hover LIFT is one, and a lift answers the pointer ARRIVING rather than the finger landing. What may not happen is a control easing the movement its own `:active` rule makes. The two that need both name their repaints inside the `:active` rule and leave the movement out of the list.

### What guards it

**Two cases in `cursor.spec.ts`, where the other three floors are**, because these are the half that can be read off the stylesheets and are not about one screen:

- *a pointer state repaints a control and never re-lays it out* — every `:hover` / `:active` / `:focus` rule across the eleven routes, flagged when it declares a layout longhand. **The DECLARATION convicts and a rendered element can only acquit it**, which is the way round it has to be: the first draft skipped a rule whose selector matched nothing, and the mutation that put the real defect back went green because this worktree's empty store draws no `#/codes` task card at all.
- *a press lands on one frame* — an `:active` rule that moves the control, does not carry its own `transition`, and matches an element that eases that property.

**Two more in `inventory.spec.ts`, which owns the fixtures**, because nothing here is a CSS rule — it is what the panel does when the write lands:

- *the press that sells a copy moves nothing outside the panel it lands in* — a sweep of every element outside `.browse-card`, plus the document height, plus the scroll, plus the location card's and the copy row's own heights.
- *the card panel holds one height for the whole walk*.

**Ten mutations, one per fix, and two of them found holes rather than confirming one.** `sellableStore()` moved `state` and nothing else, so it served a sold card that was still in its slot — a shape the server cannot produce, and it cost the sale case its whole subject: deleting the departed lens outright left it green. And the sweep compared VIEWPORT coordinates while Playwright scrolls a control into view before clicking it, which reported all 192 elements as moved and said nothing about the press.

### What is left, and why it is left

**A copy an open order was waiting on still moves the panel's contents by 46px when it is sold**, because `wantedOf` names only copies that are still on hand and the claim line goes with it. That is `Inventory.tsx`'s own documented behaviour — a pulled copy already reads `Sold` — and reserving 46px of blank on every unclaimed card to hold a line that is usually absent would be padding rather than stability. **Nothing outside the panel moves for it**, which is the floor this entry actually sets.

**What would reopen this**: a card whose copies list is long enough that one and a half visible rows is the wrong trade, or an operator who would rather the panel grew than scrolled.

### Amended 2026-09-07: the floor gets a second platform, and the second platform found a movement the first could not

**`make design-check` is a job in `.github/workflows/check.yml` now.** It was in neither `make check` nor CI, so every floor above — and D50's three, and D117's thumb floor, and the Fulfiller's contractual constraints — fired only when a person typed the command, on one Mac. That is the defect the top of that file already describes: a mechanism that is thorough, correct and never re-evaluated. It is a separate job rather than a step in `check` (a chromium install is a real cost, and a red `check` and a red `design-check` are claims about different things), it runs on `pull_request` and on `push: main`, and it costs twelve to fifteen minutes against ninety seconds — parallel, so it is the last word rather than the first. It gets no `scripts/checks.py` entry, because `check registry` refuses an entry for a target `make check` does not run.

**The "twelve to fifteen minutes" above is what it cost from 2026-09-07 to 2026-09-11 and is left as written; D136 is what it costs now.** Measured over 56 jobs before that entry: 940-1,020s wall-clock per run, `481 passed (15.2m)` on one worker, because a private repo's `ubuntu-latest` has two vCPUs and Playwright's default of half of them floors to one. The job is three shards of one worker each now, the seven real-clock sleeps are a fake clock, and the post-merge run is skipped when the tree already passed on the PR — the new figures, from a dispatch, are in D136.

**Its first run went red on the sale case, on a tree the rig had passed 166 times.** The walk row's slot cell is `minmax(34px, max-content)`; selling the copy rewrites that cell from `#1` to the store key `B2 #1` in the mono face (D68), which is wider — so the column grows and the name and the badges slide right ON THE PRESS. `B2 #1` sets at **33.0px in macOS's monospace fallback and over 34px in Linux's**, either side of the column's own 34px floor. One platform swallowed the movement; the other reported it as one pixel.

**The pixel was the messenger and never the subject.** `B2 #1` is the shortest key a store can produce — box 2, card 1. `B3 #96`, which the owner's store already draws, is 40px, and `B12 #133` is 46px: those sales moved the name six and twelve pixels on **both** platforms, and the case never saw them, because the fixture it walks is the one box whose key fits under the floor. **A tolerance would have been the wrong fix in the most exact way available** — it would have silenced the one measurement that was small enough to look like noise and left every larger one unguarded.

**The fix reserves the width the sale will need before it is spent.** `.browse-row-slotghost` is an `aria-hidden` span whose `::before` carries the future key as `content: var(--bn-slot-key)`, stacked in the same grid cell as the visible slot and set in the face `.is-departed` will switch that cell to. The track is already that wide, so the write changes only which of the two is painted. **It is `content:` and not a text node**: a hidden twin in the DOM would put `B2 #1` into every row's text content, where the census, the walk's locators and the row button's own accessible name all read. **And it is the STRING and not a `ch` count of it** — the count was the first build, and it is an estimate: a face whose weight is synthesized does not set five characters at five times the advance of `0`, which is the register the whole pixel is in.

**What it costs, named**: a row whose key is wider than its slot number starts its name further right than it used to, so a long name ellipsises one word sooner. That is the price of the press not moving anything, and it is paid once at render rather than at the moment of the sale. Looked at in both themes at 1440: the names now align down the list, where before the departed row's name sat out of line with its neighbours.

**The guard is a third case in `inventory.spec.ts`** — *the slot column is already as wide as the key the sale will write into it* — with its own one-card fixture in box 12, card 133, because **the case that already existed could not see this**: its sweep records position and height and deliberately not width, so the column that grows is invisible to it, and its box is the one whose key fits under the floor. The new case reads its own subject before it judges it (the key must clear 34px, measured on the state the sale leaves) and was mutation-tested against the reservation being deleted.
### Amended 2026-09-12: the same sentence on a second axis, which none of these guards can see

**"A press changes what is on the screen, never where the rest of it is" is a claim about ORDER as well as about pixels, and everything above measures only pixels.**
`D181` is the entry; the report is the owner's,
about `#/inventory` under a search: *"if i mark sold while on that sorta view it can reorganize the
rankings right in front of me, which feels unintuitive if im trying to mark multiple as sold."*

**Why the four guards this entry built were silent through it.** `cursor.spec.ts`'s two cases read
the STYLESHEETS, and a reshuffle is not a CSS rule. The sweep in `inventory.spec.ts` records every
element outside `.browse-card` by a stable id and its rectangle — and the copies list is INSIDE
that panel, and, decisively, **the rows a re-rank exchanges are identically shaped boxes**: swap two
of them and every rectangle this entry records is exactly where it was. The document height does
not move, the scroll does not move, and the operator's list has rearranged itself under their hand.

**So the new proof compares the IDENTITY of the rows and not their geometry** — the ordered list of
each row's `aria-label`, which is the one string saying WHICH copy is drawn there — in both
directions, with a fixture built so a frozen order and a recomputed one give different answers.
`toHaveCount` cannot see a length-preserving reshuffle, and neither can anything above.

**And the control that fixes it is bound by this entry in the ordinary way**: it appears on the
press that makes the order stale, inside a band whose height is fixed, so its slot is reserved
whether or not it is occupied — the same bargain `.browse-row-slotghost` makes in the amendment
above, paid once at render rather than at the moment of the sale.

### The copies column may not be torn down and built again (2026-09-19)

**The owner ruled on a CI flake, 2026-09-19.** His word was "fix the product." He had been
watching the same thing on the real rig for weeks.
`inventory.spec.ts`'s "a new search takes a new order" case failed on CI. It failed in 3 of 20
runs, at 2 workers, always the same way. `toHaveCount(6)` passed. A later, non-retrying read of
the same rows then came back `[]`. No press was involved. The operator had only typed a second
query into the same box.

**An earlier amendment of the same day is withdrawn.** It named the landing effect's
`answered` ref. It was reasoned from the trace. It was never reproduced. Both of its changes were
mutation-tested on 2026-09-19, under an ordering that does reproduce the defect. Both passed with
the defect fully present. Neither could reach it. The `BoxBrowse.tsx` half was also a hazard.
Recording a query on a render whose `visible` is empty spends `fresh` on a landing that never
happened, which is D132's rule failing to fire. Both are reverted. What follows was measured.

**IT WAS NEVER A RE-POINT. THE COLUMN WAS DESTROYED AND BUILT AGAIN FROM NOTHING.**
`CopiesPanel` owns a `useSearch()`. Rebuilding it throws away the answer on screen. It then
starts a 200ms debounce and a fetch. What the operator sees is six copy rows, then a skeleton,
then six rows again, with no press. Two separate mechanisms rebuilt it.

**One: the walk's row read null while the drawer it moved to was still in flight.** Since D192
`rows` holds ONE drawer's cards, and `visible` is `rows` narrowed to `shelf`. A fresh answer can
move `shelf` to another drawer. Until that drawer's own `GET /inventory/<box>` lands, `visible`
holds nothing for it. `selectedRow` was `visible.find(...) ?? null`. So it read null,
`Inventory.tsx`'s `detail` became null, and the whole column was unmounted. The fix says a row is
gone only when the drawer it would be in has ANSWERED. `rowsShelf` becomes state, so the render
can read it. The walk keeps the row it was standing on across that window. Null is kept for the
honest case: the shelf has answered and holds no row to walk. One render of null destroys the
column. So the render where the rows land, while `selected` is still the previous drawer's key,
is covered by the same rule.

**Two: `.browse-card` carried `key={selectedRow.key}`.** It came in with the rebuild (D94-D99),
so the panel's `bn-page-in` entrance replayed on every card. `{detail}` is the copies column, and
it is inside that section. The key therefore rebuilt the column on EVERY change of selection,
including the one a fresh answer makes. Every guard `CopiesPanel` carries for a row change
assumes it survives one. This key is why none of them had ever run. The key is gone. The entrance
now plays when the panel appears, which is what an entrance is for. `CardOps` keeps its own key.
That one resets a menu, not a fetch.

**Measured on the rig,** with every box read delayed 400ms and the CPU throttled 6x, which is
D128's lever. The column was absent for 679ms. It returned as the skeleton for 400ms more. With
both fixes the copies list holds six rows on every animation frame, from the keystroke to the
settled new order.

**Guarded by a frame watch rather than a poll.** Every `expect(locator)` retries until it is true
and then stops asking. A list that empties and fills between two polls is invisible to all of
them. That is how this shipped. `installCopiesWatch` samples `requestAnimationFrame`. It records
three numbers per frame: the copy rows, whether `.inventory-detail` exists at all, and whether a
skeleton is inside it. The first says what the operator counts. The second catches a tear-down.
The third catches a rebuild. Telling those apart is what sends the next session to the right
file.

**And the ordering is forced rather than hoped for.** `the copies list holds while a new answer
moves the walk to another drawer` delays the drawer read by 400ms. The hard ordering is then
certain on any machine. A delay cannot make a passing build fail. It holds open a window the
product must survive. Both fixes are mutation-tested against it. Restoring the key draws
`column=1 skeleton=2`. Dropping the held row draws `column=0`.


### The hold was too wide: a press is not a re-rank (2026-09-19)

**Review caught this before it merged.** The fix above holds `selectedRow` across the window
where a shelf's rows are still fetching, so the copies column never gets torn down. It held
across EVERY shelf change. That is wider than the case it was built for.

A fresh search answer can move the walk to another drawer on its own (D132), with no press
behind it. That is the one case the hold exists for. A PRESS to a different drawer, or a
walk-to a specific copy elsewhere, produces the exact same shape. `shelf` changes, and `rows`
still answers for the box before it. The operator asked for a DIFFERENT card on purpose.
Holding then drew box 2's card under a `Box 7` header, with `CardOps` live against it. The
list said "Nothing in box 7 yet" — false, the box held three cards. An operator could act on
the wrong box's card.

**Proved live.** Box 2 to box 7, `/inventory/7` delayed 1500ms. The header said Box 7. The
list claimed the box was empty. The detail column kept drawing box 2's Thievul.

**`shelfSource` says WHY `shelf` last moved**, a ref beside `shelfAnswered`. A press
(`selectShelf`) and a walk-to (both `setShelf` calls in the jump effect) mark it `'manual'`
before they move the shelf. The one effect that re-ranks the walk under a fresh search
answer marks it `'search'`, and only there. `selectedRow`'s hold now reads this. It stands
on the old row only when the move was a search re-rank. A press or a walk-to falls straight
to `null`. That is the behaviour from before the first fix existed. The panel blanks rather
than lying about whose card it shows.

**The same false claim lived in two more places, both fixed the same way.** The walk list's
own "Nothing in box N yet" and the detail column's matching empty state both read
`visible.length === 0` with no regard for WHY it was zero. Both are now also gated on
`awaitingRows` — the shelf's own rows have not landed. This holds regardless of the move's
source, because an honest "nothing here" claim needs the shelf to have actually answered,
not merely to have gone stale.

**Guarded by a one-shot in-page snapshot, not a retrying `expect`.** A `toHaveCount`
assertion polls until it is true or times out. A false claim that clears itself the moment
the delayed `GET /inventory/7` lands would let the assertion settle AFTER the fact. That
proves the DOM healed. It never proves the false state was drawn at all — the identical
trap D118's frame-watch above exists to avoid.

`inventory.spec.ts`'s `a press to another drawer never draws its predecessor's card while
the fetch is in flight` takes one `page.evaluate`. It is called right after the click, before
anything awaits the network. It reads the box-cell's `aria-current` and `.browse-card`'s
count. It also reads box 2's photo alt text, the false-claim sentence in both
capitalisations, and `.browse-empty`'s count. All five come off that single snapshot.

**Mutation-tested.** Reverting the `shelfSource` gate draws `.browse-card` count 1: box 2's
card, under the Box 7 header. Reverting either empty-state gate draws the false claim `true`.

### Blank was itself the defect: the previous drawer stays, dimmed (2026-09-19)

**The owner ruled again, on the fix above.** It fell to `null` for a press or a walk-to —
no row, no rows, no sentence, no spinner. That window runs up to ~1.5s on a slow store.

His word: keep the previous drawer's rows on screen, DIMMED, until the new answer lands.
Both the walk list and the copies column. No new visible words — `copy-budget.json` holds.

**Blank is not neutral.** An empty pane during a press reads as a fault, not a wait. The
first fix traded one wrong claim for a different cost, and the owner ruled the cost real.

**What is held.** `held` already kept the last row `found` in `visible`, for a search
re-rank. Two more refs join it: `heldSections` (the list's last answered `sections`) and
`heldDetail` (the `{detail}` prop, `Inventory.tsx`'s `CopiesPanel`, off the same render).

All three write only when the render is not `awaitingRows`. None can ever hold a partial
or in-flight answer. Each one only ever holds a box that fully answered.

**Dimmed is not a smaller a4f3594b claim.** Box 2's row, drawn under a `Box 7` header, is
literally the shape that regression named. What makes it safe is that it cannot be acted on.

`.browse-list[aria-busy='true']` and `.browse-card[aria-busy='true']` (BoxBrowse.css) drop
to `--bn-disabled` opacity, the token this file already had for "on screen, not live". Both
set `pointer-events: none`. No click can land on a card the header no longer names.

The list also leaves the tab order (`tabIndex={-1}`). Its `onKeyDown` is not attached
while dimmed — the one keyboard path onto a stale row (`TICK_KEY`) cannot fire either.
`aria-busy="true"` stays on both regions the whole time, so a screen reader is told: not
final. Dimmed is drawn, never claimed.

**No layout jump.** Neither region unmounts now. The list keeps its own node across the
wait — nothing collapses and reappears. The card panel's key does not change between the
held row and that same row once it lands. Only a genuinely different card remounts
`CardOps`.

**`inventory.spec.ts`'s renamed case** (`a press to another drawer dims its predecessor's
rows rather than drawing them as the new box's, or drawing nothing`) keeps the one-shot
`page.evaluate` snapshot. It adds both elements' computed `opacity` (under 1) and
`pointerEvents` (`'none'`), both `aria-busy` values (`'true'`), and the list's `tabIndex`
(`-1`). It adds the list's own height, unmoved against its value before the press. Same
box, same content, held through the wait — the one comparison that isolates the fix.
Box 2's row count and photograph are still drawn while held. The false-claim and
`.browse-empty` checks stand: dimmed never lies about what box holds what.

### Review found a keyboard path around pointer-events, and an untested column (2026-09-19)

**Finding 1, HIGH.** `pointer-events: none` blocks the mouse alone. Tab still reached
`CardOps`' "Card actions" button. Enter opened its menu on `held.current` — box 2's card,
live, under the Box 7 header. The same regression a4f3594b named, reached by keyboard.

**Fixed with `inert`.** The dimmed `<section className="browse-card">` carries
`inert={dimPanel}` (React 19 supports `inert` as a boolean prop). `inert` removes the
whole subtree from the tab order. It refuses activation too, by the same mechanism. The
list keeps its own narrower fix (`tabIndex={-1}`, `onKeyDown={undefined}`). It is not
`panelRow`/`panelDetail`'s own subtree, and it carries interactive rows of its own that a
blanket `inert` would also have to cover.

**Guarded by calling `.focus()` on the button directly**, in the same one-shot snapshot,
rather than a real Tab walk. An `inert` subtree refuses a programmatic `.focus()` call, by
the same spec clause that drops it from the tab order. This reads the fact faster, and no
less certainly. `cardInert` and `cardActionsFocusable` are both asserted.

**Finding 2, MEDIUM.** Mutating `panelDetail` back to the live `detail` left the case
green. Nothing had ever read `.browse-under`'s own content — only `.browse-card`'s outer
`aria-busy` and opacity. `underOwnerCount` and `underRowCount` now read
`.card-locations-owner` and `.card-locations-row` inside `.browse-under`. Both are
`CopiesPanel`'s own classes (`CardLocations.tsx`). The case now fails if the copies column
ever draws nothing, or anything invented, in place of the held card's real copies.

**Both mutation-tested** (`.bak` copies, restored, never `git checkout <path>`, never
`git stash`). Reverting `inert={dimPanel}` to `inert={false}` draws `cardInert` false.
Reading the live `detail` instead of `heldDetail.current` draws `underOwnerCount` 0.
