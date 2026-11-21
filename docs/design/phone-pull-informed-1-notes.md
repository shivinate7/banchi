# Phone Pull: notes, informed designer 1

Mockup: `phone-pull-informed-1.html` in this folder. Designer kind: informed. Every name, card, buyer, price
and count in it is made up.

Deep links take `#s=<state>&t=<light|dark>&h=<hidden options>`. States: `pull`, `buyers`, `card`, `pulled`,
`sold`, `done`, `loading`, `empty`, `nothere`, `unlocated`, `away-wait`, `away-hold`, `find`, `findcard`,
`copy`, `move`, `moved`, `slabs`, `scan`, `scanread`, `slabadded`, `slabrefused`, `today`. With no `t`, the
page follows the system theme. Options: `count`, `marks`, `buyers`, `unloc`, `wait`, `hold`, `scanCert`.
Each option has a Hide button on the page. Focus ids for the waiting page: `opt-count` (state `pull`),
`opt-marks` (`pull`), `opt-buyers` (`buyers`), `opt-wait` (`away-wait`), `opt-hold` (`away-hold`) and
`opt-scanCert` (`slabs`).

Sizes. `layout.py devices` gives no Duo size (`size: null`). The folded pose is drawn at 375 by 812, the
brief's width and the 375x812 phone viewport from `app/tests/fulfillment.spec.ts`. The unfolded pose is
drawn at 820 by 812, the brief's 820 width at the folded height. Both are drawn sizes, not device sizes.
The safe areas use `env(safe-area-inset-*)`. The status bar (50) and home indicator (30) are drawn values
for a desktop page, not Apple numbers.

Apple pages read 2026-11-21, each through its `tutorials/data` JSON, each answered 200: Layout, Typography,
Accessibility, Buttons, Sheets, Lists and Tables, Tab Bars, Toolbars, Search Fields, Segmented Controls.
Searching and Filtering answered 404. Its content is unknown and the mockup does not use it. The type sizes
come from the Typography page's Large (default) table: Large Title 34, Title 1 28, Title 2 22, Title 3 20,
Body 17, Subhead 15, Footnote 13, Caption 2 11. The 44 by 44 pt target comes from Buttons and Accessibility.

## Choices

1. **Four tabs: Pull, Slabs, Today, and Find as the trailing search tab.** On the folded pose the bar sits
   at the bottom. On the unfolded pose it sits at the top, inside the left half (Tab Bars, Search Fields).
   Gain: Pull is first, and search is always one tap away. Loss: the Orders walk and Fulfillment become one
   Pull tab. Pick: this. Owner grant: yes.
   Departs from: `#/fulfillment` (`Fulfillment.tsx` `Fulfillment`) and the walk in `#/orders`
   (`OrdersWalkPane.tsx` `WalkList`) are two screens over the same `POST /orders/walk-plan`.
2. **Each card says how many to pull: "Pull 2".** The number is `Owed.wanted`, already folded per SKU in
   `Fulfillment.owedFrom`. Every copy is still listed in walk order, and none is preselected (the owner's
   ruling quoted in the `Fulfillment.tsx` header comment, and D212). Gain: fixes pain 1. Loss: none seen.
   Pick: this. Owner grant: yes.
   Departs from: docs/DESIGN.md "Fulfillment (B23), built", where an ordinal badge replaced the `Pick N` label.
3. **One row per card, grouped by box and section. The copies live on the card screen.** Gain: the
   sample list is 7 rows. Today it would be about 15 photo cards, one per copy. Loss: a copy in another box
   shows only in the card screen's copy chips. Pick: this. Owner grant: yes.
   Departs from: `Fulfillment` drawing every copy inline through `CardLocations`, each with its own Pull.
4. **Buyer marks.** Each row shows the initials of each buyer it is owed to. The card screen says "Goes to
   Mara Pell". The copy goes to `refs[0]`, the oldest order that still owes the card (`Fulfillment.tsx`
   `Owed.refs`). Gain: fixes pain 2. Cards are sorted into envelopes at the shelf, with no second pass.
   Loss: two buyers can share initials, and a builder needs a rule for that (for example, add a digit).
   Pick: this. Option `marks`. Owner grant: yes.
5. **List by Buyer.** A segmented control turns the same list into one row per buyer, with the lane
   (Envelope or Parcel, the `#/shipping` lanes) and "0 of 3 in". On the unfolded pose the buyers sit beside
   the walk by default. Gain: a packing check. Loss: a second order of the same list. Pick: this. Option `buyers`.
6. **One count, said the same way everywhere.** Owed = to pull + not in a box. The same three numbers show on
   Pull and Today. The tab badge is gone: Tab Bars reserves badges for critical information, and
   docs/DESIGN.md keeps vermilion for "happening now". Gain: fixes pain 3. Loss: the word "Left" goes.
   Pick: this. Owner grant: yes.
   Departs from: `Fulfillment` "N Left" (`totalWanted`) and "N unlocated" (`shortfallCount`), against
   `#/orders` "copies owed", "to pick" and "not in boxes", which counted 74, 176, 256, 92 and 164 on the
   demo. A builder needs one home for the count.
7. **Card screen, folded.** The place (`Card 18`, 34 pt) and "of 54" sit above a thin back-to-front track,
   then the photo at 320 by 447 (`PHOTO_FLOOR` 320), then the action block. The block keeps both steps from
   the start: 64 + 24 + 64 (docs/DESIGN.md, "The action block reserves 152px"). Before Pull, the lower slot
   holds text ("Goes to ..."), never a control. A next-copy button on the photo steps through the copies.
   Gain: the photo, the place and Pull fit one screen with no scroll. Loss: the track's Back and Front words
   are dropped on the folded pose. Its accessibility label says them. Pick: this.
   Departs from: `PositionBar`'s visible words.
8. **The two steps are kept.** Pull, then "Pulled." in Pull's slot and Mark It Sold below it
   (`Fulfillment.actionFor`). The label is "Mark it sold" in Title Case (R5). Gain: a double tap lands on text,
   not on a sale. Loss: none. Pick: this.
9. **After a sale, the answer shows in Pull's slot, with Undo and no clock.** This keeps UN-5
   (`Fulfillment.tsx` `Sale`). The lower slot offers Next Copy. Gain: the answer shows where the press was.
   Loss: none. Pick: this.
   Departs from: the receipt sheet at the foot of `Fulfillment` and its "Pulled today" list. That list is
   not drawn in this pass.
10. **Card screen, unfolded: the hinge separates acting from looking.** The left half holds the place, the
    copies, who the card is for, and the two steps. The right half holds the photo at 360 by 503, on
    `--bn-stage-*`, which stays dark in both themes. Sheets stay inside one half and never cross the hinge.
    Gain: the photo is never under a button. Loss: the list hides while a card is open. Back returns to it.
    Pick: this.
11. **Not Here.** A sheet offers the next copy by place, or Skip for Now (the card moves to the end, on the
    phone only). It writes nothing. Gain: a missing card is no longer a dead end. Loss: no "mark missing",
    because that is an owner write. Pick: this. Owner grant: yes.
12. **Not in a Box list.** Owed cards with no copy (`plan.shortfall`) get their own rows and a Look For It
    button, which opens Find. Gain: the warning gets an action. Loss: none. Pick: this. Option `unloc`.
    Departs from: `Fulfillment`'s "N unlocated" line, which has no action.
13. **Mac out of reach: two options.**
    - Wait for the Mac (`wait`, picked): the list stays from the last read, and a floating notice with Try
      Again moves nothing (`Fulfillment` stale notice, R19). Pull still works. Mark It Sold says it waits.
    - Hold Sales While Away (`hold`): sales are kept on the phone and sent later. Loss: a second writer can
      sell the same copy twice. That breaks D138 (one writer). Owner grant: yes.
14. **Find.** Results show the copy count and boxes. A card shows its copies by place. One copy opens a
    sheet with Sell This Copy (the same two steps) and Move This Copy (box and section pickers,
    `server.moveCard`'s `to_box` and `section`). A move answers with Undo. Gain: `#/inventory`'s two writes
    on a phone. Loss: no bulk select. Pick: this. The search field is drawn at the top. With iOS 26 it may
    sit at the bottom. Unverified.
15. **Slabs and the cert scan.** The list sorts by Card Ladder value, with a slab that never sold last
    (`slabs.spec.ts`). Scan opens the camera on the label's barcode. Type the Cert Instead stays one tap
    away. The Add sheet lists graders with PSA chosen (`Slabs` `SLAB_GRADERS[0]`). The cert is never shown
    (docs/specs/my-slabs.md). The refusal text is the server's own (`slabs.spec.ts` `CERT_NOT_FOUND`).
    Gain: no typing of a long number. Loss: it is unmeasured whether every grader's barcode holds the cert
    number. Pick: this. Option `scanCert`. Owner grant: yes.
16. **Today, read only.** What is not normal comes first (house rule `ux-all-is-well`). Then orders,
    shipping lanes (Envelope, Parcel, Needs a Look) and sales for the last 7 days, with canceled orders
    left out (the `#/revenue` rule). Pick: this.
17. **Type.** The chrome uses the system font at Dynamic Type sizes. Pull keeps the Fulfiller's floors:
    20 pt text, a 34 pt place, 64 pt steps and 44 pt targets. Numbers use the system font's tabular figures.
    Owner grant: yes.
    Departs from: docs/DESIGN.md "`--bn-font-mono` EVERY NUMBER", and Manrope and Inter.
18. **Colour.** `--bn-*` light and dark, mapped onto native surfaces. The step fill is `PullConfirm`'s 7:1
    pair (`--bn-accent-press` light, `--bn-accent-hover` dark). Vermilion marks only the live camera.

## Not drawn

The Pulled Today list, empty and failed states for Find and Slabs, slab detail history, a large Dynamic
Type size, and the regular iPhone.

## Input needed

- Items 1, 2, 3, 4, 6, 11, 13 (Hold), 15 and 17 are `Owner grant: yes`.
- Does a person other than the owner pull on this phone? If so, item 17 keeps the Fulfiller floors. If only
  the owner pulls, Pull can use standard Dynamic Type and show about a third more rows.
- Outside this folder: the capture server's Origin check (`DEFAULT_ALLOWED_ORIGINS`) needs a rule for a
  native client. The phone reaches the Mac over plain HTTP on the home network, which iOS gates.
  Both are unmeasured.
