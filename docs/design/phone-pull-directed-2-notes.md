# Phone pull, one thumb: design notes

Designer kind: directed. Direction: one thumb while walking: one glanceable next card at a time,
every control in the thumb zone. Mockup: `phone-pull-directed-2.html`. Every name, card, count,
cert and price in it is made up.

The idea that matters most: the walk is one card on one screen, and the thumb has two fixed slots.
The upper slot pulls. The lower slot sells. Neither slot ever changes size, so a double tap can
never sell a card whose photo was not seen.

## Deep links

Add `t=dark` or `t=light` to any link; with no `t`, the page follows the system. `l=1` turns on the
dashed Today and New labels. `sell=each`, `off=hold` and `env=name` show the other option in each
group. `h=sell,off,env` hides an option from the Options panel.

- Pull tab: `#s=pull`, `#s=loading`, `#s=empty`.
- Walk: `#s=walk`, `#s=pulled`, `#s=sold`, `#s=short`, `#s=found-fewer`, `#s=unlocated`,
  `#s=list`, `#s=offline`, `#s=sell-failed`, `#s=done`.
- Find: `#s=find`, `#s=find-card`, `#s=move`, `#s=moved`, `#s=find-sold`.
- Slabs: `#s=slabs`, `#s=scan`, `#s=scan-read`, `#s=slab-added`.
- Home: `#s=home`.

## Sizes

`python3 ~/.claude/lint/layout.py devices` gives no size for either Duo pose, and the brief names
none. The folded pose is drawn at 375 by 812 pt: 375 is the brief's phone width, and 375 by 812 is
the phone viewport of `app/tests/fulfillment.spec.ts`. The unfolded pose is drawn at 760 by 812 pt,
an assumed size, not a device value. The status bar and home bar insets are mock values: the CSS
reads `env(safe-area-inset-*)` first and falls back to them.

## Apple pages read

Read 2026-11-21 through `developer.apple.com/tutorials/data/design/human-interface-guidelines/<page>.json`.
Each answered 200.

- layout: respect safe areas; lay out by size class (compact or regular width).
- typography: Dynamic Type sizes at the default (Large) size: Large Title 34, Title 1 28, Title 2 22,
  Title 3 20, Headline 17, Body 17, Callout 16, Subhead 15, Footnote 13, Caption 2 11.
- accessibility: default control 44 by 44 pt, minimum 28 by 28; text size up to 200 percent.
- buttons: hit region of at least 44 by 44 pt; button sizes Regular 44, Large 52, Extra large 64.
- sheets: Cancel or Close leads the top bar, Done trails.
- tab-bars: navigation, not actions; floats above the content at the bottom; badges for critical
  information only.
- toolbars: a large title turns into a standard title when people scroll.
- lists-and-tables: read, used for the grouped lists.

## Choices

1. **The walk is one card per screen, with no tab bar.** The walk opens over the tabs, like a
   full-screen cover. Gain: the place, the count to take, the photo and both thumb slots fit in one
   folded screen with no scroll. Loss: the tabs are one press away (the list button, then End Walk).
   Today: `Fulfillment.tsx` is one long list, one location card per copy. Pick: yes.
2. **The order of reading is fixed: place, count, neighbours, name, photo, slots.** The place
   ("WB1 R2, Section 2" over "Card 18 of 54") is read first, from a stride away, at Large Title
   34 pt. Gain: the walker knows where to reach before the photo is needed. Loss: the photo sits
   below the fold of attention. Today: the place label is the location card's heading
   (`Fulfillment.tsx`, `sayPlace`). Pick: yes.
3. **"Take 3": one count per card, never one row per copy.** Pain point 1. The pill beside the card
   number says how many copies to pull. Gain: one look says how many to grab. Loss: a single press
   now stands for several copies (see 5). Departs from: `Fulfillment.tsx` draws one Pull per copy
   (`copy.key`). Pick: yes.
4. **The two thumb slots.** Upper slot: list button, then Pull. Lower slot: Can't Find It and Later
   before the pull, Mark Sold after it, a "Sold" sentence after the sale. Undo and Next Card take
   the upper slot after a sale. Gain: the sale is always one slot below the pull, so the two-step
   guard holds (DESIGN.md, "Two-step pull"; `Fulfillment.tsx`, the comment above the
   `PullConfirm` call). A double tap on Mark Sold lands on a sentence. A double tap on Next Card
   lands on the next card's Pull, which writes nothing. Loss: the walker moves the thumb between
   two heights for each card. Pick: yes.
5. **Option `sell`: how a card with several copies is sold.** One press sells all of them (pick), or
   one press per copy ("Mark 1 Sold (1 of 3)"). One press: fewer taps, Undo takes all back. Per
   copy: the hand and the screen count together. Both keep D57's one tap per sale step. Pick: one
   press. Owner grant: yes, because one press records several copies against several orders
   (`pickOrderFor` in `OrdersWalkPane.tsx` runs once per copy).
6. **The pane never moves on by itself.** After the sale, the card stays and Next Card is a press.
   Gain: keeps UN-6 ("The pane does not advance itself", `docs/specs/order-walk-plan.md`, How a row
   closes). Loss: one more press per card. Pick: yes.
7. **Envelopes, one per order, numbered.** Pain point 2. The Pull tab lists each order as an
   envelope with a number. After Pull, the upper slot says "Pulled. Put in [1] ×2 [3] ×1". Gain:
   cards are sorted into envelopes at the shelf, so no second sort at the desk. Loss: the walker
   must number the envelopes before the walk. Departs from: today no screen groups a pull by buyer
   (`Fulfillment.tsx` sorts by box-walk order only). Owner grant: yes.
8. **Option `env`: number or first name on the envelope chip.** Number (pick): short, big, same
   width. First name: reads with no lookup, but it is wider, and two buyers can share one.
9. **One Pull tab for both today's Fulfillment and the Orders walk.** All owed orders are in by
   default, as on `#/fulfillment`. Gain: one place to pull and one count. Loss: the Orders walk's
   rule "nothing is ticked by default" (`docs/specs/order-walk-plan.md`, Selecting) does not apply
   on the phone. Departs from: `#/orders` walk, which starts with no order ticked. Owner grant: yes.
10. **One count, in cards, everywhere.** Pain point 3. "38 cards to pull" on the Pull tab, "26 left"
    in the walk, "38 cards to pull" on Home: one unit (copies still owed) and one source. No tab
    badge, so the count shows in fewer places that could disagree, and HIG keeps badges for
    critical news. Today: `Fulfillment.tsx` says "N Left" (`ff-count-num`). Pick: yes.
11. **Can't Find It: a stepper, "how many did you find?".** Found 2 of 3 turns Pull 3 into Pull 2.
    The rest stay owed and go on the Not Found list at the end. Gain: a short shelf is one press
    and one number, not a dead end. Loss: a new write the server does not take today (a "not
    found" mark). Owner grant: yes.
12. **No place on file: last in the walk, with a stock image.** Today the unlocated cards are a
    warning with no action (`Fulfillment.tsx`, "unlocated"). Here each one is a card with "Look by
    name", the stock image (`docs/specs/lean-server.md`, option a) and Pull or Not Found. Gain: an
    action for every owed card. Loss: a walk can end on cards that may not exist. Owner grant: yes.
13. **The walk sheet.** The list button opens next stops, envelope progress and End Walk, with
    "Each sale is saved when you press it". Each stop is a press that goes to it. Gain: the plan,
    a way back to a card set aside with Later, and the exit stay one press away.
    Today: a pull is banked at the press (`store/orders.py`, `record_pull`). Pick: yes.
14. **Option `off`: the Mac is out of reach.** Wait (pick): a floating notice with Try Again (R19,
    DESIGN.md, Fulfillment) and the lower slot says "Selling waits for the Mac." The list and Pull
    still work from the last read. Hold: the phone keeps sales and sends them later; that is a
    second writer (`docs/specs/lean-server.md`, section 7, "one process, one store, one writer").
    Owner grant: yes, for hold.
15. **Walk Done.** "37 of 38 sold", the Not Found list and each envelope's count. One press looks for
    the missing card again. Pick: yes.
16. **Find: search at the bottom, copies with Mark Sold and Move.** The search field sits above the
    tab bar, in thumb reach. A card shows its copies in box order, each with Mark Sold and Move.
    Move opens a sheet of boxes. Each answer is a receipt in the row, with Undo. Today: Inventory's
    sale and move (`Inventory.tsx`, the `sale` and `move` receipts). Pick: yes.
17. **Slabs: scan the cert on the camera stage.** The viewfinder is dark in both themes (DESIGN.md,
    Stage). A guide box frames the label; it turns green when read. A sheet shows the card, the
    grade and a grader segmented control (PSA, Beckett, SGC, CGC: `docs/specs/my-slabs.md`, 3.1),
    then Add Slab. The cert is not shown on screen (`docs/specs/my-slabs.md`, 4.1). Type It In
    stays as the other way. Today: Add a Slab on the Mac (`#/slabs`). Owner grant: yes (a camera
    reader is new work).
18. **Home: read only.** Needs you (only what is not normal), sales, shipping lanes. No action but
    the jump to Pull. Pick: yes.
19. **Type: the Fulfiller's floors hold in the walk.** Every walk text is 20 pt (Title 3) or larger,
    the place is 34 pt (Large Title), the buttons are 64 pt with 22 pt labels, and the walk uses only
    ink and ink-2 for text (7:1 or better). DESIGN.md, "Fulfillment view — hard constraints":
    `BODY_FLOOR` 20, `PLACE_FLOOR` 32, `TARGET_FLOOR` 44, `GAP_FLOOR` 12, `CONTRAST_FLOOR` 7.
    Other tabs use the native sizes (Body 17). Pick: yes.
20. **Photo: 320 pt on the short edge, folded and unfolded.** `PHOTO_FLOOR` 320. Folded, the photo
    is 320 by 447. Unfolded, it is 372 by 520 beside the place and the slots. Pick: yes.
21. **Unfolded: photo left, place and slots right, "Up next" between.** A regular-width layout, not
    the folded one made wider. The slots sit at the bottom right, under the right thumb. Pick: yes.
22. **Native parts.** System font, Dynamic Type sizes, a floating tab bar of four tabs (Pull, Find,
    Slabs, Home), sheets with a grabber and Cancel or Close leading, inset grouped lists, a
    segmented control. Token map: `--bn-bg` is the grouped background, `--bn-surface` the rows,
    `--bn-accent-press` (light) and `--bn-accent-hover` (dark) the pull fill, as in
    `PullConfirm.css`. Figures use tabular system digits, not JetBrains Mono, for a native look.
    Departs from: DESIGN.md, "EVERY NUMBER AND EVERY MACHINE STRING" in mono. Pick: yes.

23. **Later, not Skip.** The second lower-slot button moves the card to the end of the walk, and
    the walk sheet marks it "Moved here by Later". Gain: the word says where the card goes. Loss:
    a longer word than Skip. Pick: yes.
24. **A sale that does not save.** `#s=sell-failed`: the upper slot says "Nothing was saved. Press
    Mark 3 Sold again." and the button stays. Today: `Fulfillment.tsx` sets the same sentence for
    a failed sale (`setTrouble`). Pick: yes.
25. **The envelope setup line.** The Pull tab says "One envelope per order. Write its number on it
    before you start." Gain: a first walker learns the one setup step where the list is. Pick: yes.
26. **Large text.** The one-screen walk fits at the default text size only. At larger Dynamic Type
    sizes the walk must scroll, or the photo must go under its 320 pt floor. Not drawn. See Input
    Needed in the report.

## What a builder needs from outside this folder

- A server write for "not found" (items 11 and 12) and a cert reader (item 17).
- A tokens file for the app (`tokens/tokens.json` per skill `ios-apps`); the repo has none.
