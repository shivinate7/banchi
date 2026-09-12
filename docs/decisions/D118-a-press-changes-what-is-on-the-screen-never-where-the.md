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
