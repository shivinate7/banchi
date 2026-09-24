# Held screens: Inventory and Review, seven lenses

Target: the published demo, `https://shivinate7.github.io/banchi/`, bundle `index-Bzh3vA1X.js`.
Confirmed post-merge before grading: `#/inventory` draws section titles as
`Section 1: Commons, 11 cards` (the `SectionTitle` component from PR #456, 70ab39e1).
Widths 1440x900, 820x900, 720x900, 390x844 (mobile, touch). Light and dark. Scripts:
HIR scratch file, not kept. Data: HIR scratch file, not kept. Shots: HIR screenshot, not kept.

The demo has no card photographs at all (every photo URL is a 404, see "What I could not
check"). The demo also returns no undo for a sale, a retire or a review answer. Findings that
depend on that are marked "demo-measured".

## Grade matrix

| Lens | `#/inventory` | Reason | `#/review` | Reason |
|---|---|---|---|---|
| 1 Coherence | D | One card's address has six forms on one panel and its dialogs. The delete dialog uses a different number. | C | The Close dialog names the four retire reasons differently from Inventory. Receipts use a different mechanism. |
| 2 Owner's loop | C | Sell, retire and manage are reachable at 1440. Moving one copy hides behind a tick and the box sheet. At 720 the list is in a sheet. | D | At 720 and 390 no answer row and no Undo is in the first viewport. The position link loses the card. |
| 3 Visual system | C | The walk list is a 183 px window at 1440x900. Section names are cut at the widest layout. The "Wrong card?" pill is out of place. | B | Clean and consistent. The chip strip wraps and orphans one chip at 1440. |
| 4 Interaction | C | The corner toast does not leave and covers the sheet's danger rows. "Wrong card?" opens off screen. | C | An answer can move the next card's rows 53 px. Answers with no undo are silent. |
| 5 Copy and register | D | Machine codes, a file path and pipeline nouns on the card panel, the toast and three dialogs. | D | The question vocabulary is pipeline nouns (row, export, read, stand down). Codes show in the Close dialog and in tooltips. |
| 6 Phone, touch, access | C | Tick boxes are 22 px at 390. Four on-screen contrast failures in light, five in dark. Invalid `dl` in the sheet. | C | The NEXT label is 2.81:1. Reason codes are in tooltips. Rows and receipt are below the fold on a phone. |
| 7 Text density | D | "Identified" three times, name, number and game twice, the address four times, the section count twice. | C | Missing-photo notice plus path. A 110-word Close dialog. A 70-word Re-check sheet. |

## Findings

### HIR-01 One card's address has six forms, and the delete dialog uses a different number
- Severity: S2
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory`, click `#6 Long Sword`. Read the photo notice, the card block, the section strip and the list. Then open `...` > `Remove this card...` and `...` > `Correct claims`. Then `#/review`, open `This read`.
- Seen: The same card reads `Box 1, Section 1, Card 6` (photo notice, toast), `BOX RB Origins Box 1 / SECTION 1 Commons / CARD 6` (card block), `Section 1 · Commons · card 6 of 11 slots` and `#6 of 34` (strip), `SECTION 1: COMMONS, 11 CARDS` + `#6` (list), `BOX 1 · SECTION 1 · CARD 6` (Correct claims), and `BOX 1 1/8` plus `capture id demo-1-0008` (Remove dialog). The Remove dialog is the one act with no undo, and it is the one place where the card is `8`, not `6`. Review adds `BOX 1 SECTION 3 CARD 13` (the pill) and `Box 2 · Section 2 · Card 9` (This read, receipts).
- Shot: HIR-01, screenshot not kept.
- Direction: One address sentence for a card, composed once and used by every panel, dialog, toast and receipt. The delete dialog names the card by its name and by the number the list shows.
- Component: `app/src/CardHero.tsx`, `app/src/CardLocations.tsx`, `app/src/BoxBrowse.tsx`, `app/src/Inventory.tsx` (remove dialog), `app/src/ReviewQueue.tsx`
- Annotation: violates D183 (a number a person reads is never a key): the Remove dialog shows the stored index `1/8` and `capture id demo-1-0008`, which is the machine key, to a person. Also violates D67 (the number a screen draws is composed once) in spirit: the address has one server string (`Position.label`) and every surface recomposes it. D41 (the address is a rank) governs only the card block. It does not govern the other five forms, so no decision holds the address to one form app-wide. prior: none for the six-form count. COH-12 logged five forms before the merge.

### HIR-02 A missing photograph has three different drawings
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory` (card panel), the Retire dialog, and `#/review` (first card).
- Seen: Inventory draws a hatched light panel, a warning triangle, an 18-word sentence, a path and `Re-shoot this photo`. Review draws a dark panel, an image glyph, `The file is not on disk`, a different 17-word sentence and a path, with no action. The Retire dialog draws a plain grey tile with an image glyph.
- Shot: HIR-02, screenshot not kept.
- Direction: One missing-photo state, with the same words and the same one action, on every surface that draws a card photograph.
- Component: `app/src/CardHero.tsx`, and the photo pane in `app/src/ReviewQueue.tsx`
- Annotation: no decision covers this. D38 (the photograph is sized by the rows beside it) sizes the frame but says nothing about its empty state. prior: none.

### HIR-03 The four retire reasons have two sets of names and meanings
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory` > Retire (box icon). Then `#/review` > `X`.
- Seen: Inventory: `Pulled out` "Taken out of the box for something else", `Damaged` "Not in a condition to sell", `Lost` "The slot is empty and nobody knows where it went", `Given away` "Left the store as a gift or a trade". Review: `Pulled` "Taken out of the box by hand", `Damaged` "Not sellable at the condition listed", `Lost` "Gone, and not sold", `Given away` "It left without a sale". The four codes underneath are the same.
- Shot: HIR-03, screenshot not kept.
- Direction: One label and one sentence per reason, shared by both dialogs.
- Component: the Retire dialog in `app/src/Inventory.tsx`, and the Close dialog in `app/src/ReviewQueue.tsx`
- Annotation: no decision covers this. D26 (a card leaves inventory by a state, retired) and D37 (a queued question can be closed without answering it) each define the reasons, but no entry makes the two dialogs share one label table. prior: ux-2026-09-20/graveyard.md and ux-2026-09-20/inventory.md #3 logged a third spelling (Graveyard prints the raw code). The label table lives in `Inventory.tsx` only, so Review wrote its own.

### HIR-04 Two receipt mechanisms: a corner toast on Inventory, an inline bar on Review
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory`, Mark sold. `#/review`, `X` then `1`.
- Seen: Inventory confirms in a toast in the bottom-right corner, which did not leave in 20 s. Review confirms in a dark bar under the answer buttons, with an Undo button, a U key cap and a 20 s timer bar. The owner must learn two places to look for "what did I just do".
- Shot: HIR-04, screenshot not kept.
- Direction: One receipt pattern for a write on a card: the same place relative to the press, the same Undo control, the same lifetime.
- Component: `Inventory.tsx` `remember` (toast), and the `ReviewQueue.tsx` receipt (`bn-receipt review-receipt`)
- Annotation: caused by D119 (the receipt lands where the sale was pressed) together with D28 (the review answer gets an undo window). D119 puts the sale receipt in the row and ALSO posts a toast, and D28 puts the answer receipt under the answer rows. Each is right for its screen, but no entry makes them one pattern. prior: none.

### HIR-05 The section is "11 cards" in the list and "11 slots" in the strip
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory`, box 1, card #1.
- Seen: The list header reads `SECTION 1: COMMONS, 11 CARDS`. The strip on the card panel reads `card 1 of 11 slots` for the same 11.
- Shot: HIR-05, screenshot not kept.
- Direction: One unit word for the same count on one screen.
- Component: `app/src/SectionTitle.tsx` and `position.ts:sectionCountWords`, against the strip in `app/src/CardLocations.tsx`
- Annotation: caused by an owner ruling of 2026-09-19 quoted in `position.ts:sectionDepthOf` ("a settled one against its declared width and says `slots`") beside D58 (a card's number counts the cards in the box, not the slots). PR #456 then gave the header a count in `cards`. The two rules now meet on one screen. The ruling is an argument, and this is the outcome it did not foresee. prior: none.

### HIR-06 Correcting a card has four names
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory`, press `Wrong card?` (it opens a panel titled `Correct the listing`), and `...` > `Correct claims`. `#/review`, `Search the export`.
- Seen: `Wrong card?`, `Correct the listing`, `Correct claims` and `Search the export` are four labels for two acts: fix what the card is, and fix what was claimed about it. Nothing tells the owner which one fixes a wrong identification.
- Shot: HIR-06, screenshot not kept.
- Direction: Name each correction once, by what it changes. Use that name on the button and on the panel it opens.
- Component: `CardHero.tsx` (`Wrong card?`), and the card actions menu in `Inventory.tsx`
- Annotation: no decision covers the naming. D252 (a wrong answer gets a correct route) is the new "Wrong card?" route from PR #456, and D101 (a claim a screen names is a claim a screen can fix) is "Correct claims". The two entries do not name each other. prior: none.

### HIR-07 Review's position link opens the box at its first card, not at the card
- Severity: S2
- Screens: `#/review` to `#/inventory`
- Where: 1440/light (all widths use the same link)
- Repro: `#/review`, press the `Not in the export` chip (card Sobble, `BOX 2 SECTION 2 CARD 9`), press the position pill.
- Seen: The link is `#/inventory?box=2`. Inventory opens on `#1 Mantine`, not on Sobble (card 9). The owner who went to look at the card must find it again. This can overlap the locating lens.
- Shot: HIR-07, screenshot not kept.
- Direction: The pill opens Inventory on that exact card.
- Component: `ReviewQueue.tsx` (`review-position` link)
- Annotation: no decision covers this. D45 (the copies list is a way back into the walk) is the Inventory-side pattern that this link does not follow. prior: none in ux-2026-09-20. COH-07 on main calls this pill the app's only card-to-card link.

### HIR-08 Moving one copy is two steps away, and the card's own menu does not offer it
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory`, card panel `...` menu: `Correct claims`, `Re-read the inventory`, `Remove this card...`. No move. Tick the card, then `Manage` > `Move to box: 1 ticked`.
- Seen: The page subtitle says "Sell, retire or move a copy from here." Sell and retire are on the card. Move is only in the box sheet, and it acts only on ticked cards. With nothing ticked, it moves "all 34 cards on hand in box 1".
- Shot: HIR-08, screenshot not kept.
- Direction: A move for the card in view, beside sell and retire.
- Component: the card actions menu in `Inventory.tsx`, and the `BoxOps` sheet
- Annotation: no decision covers this. D83 (a card leaves a box through a third door, moved) defines the move, and D180 (a press names the cards it is over) makes it a ticked selection. Neither puts it on the card. prior: none. LOOP held-screen note on main logged it pre-merge.

### HIR-09 At 720 and 390 no Review answer is visible without a scroll
- Severity: S2
- Screens: `#/review`
- Where: 720/both, 390/both, 820 (the first row starts at y 820 in a 900 viewport)
- Repro: `#/review` at 720x900.
- Seen: The photograph frame fills the first viewport. The three answer rows start below the fold at 720 and 390. At 820 the first row's top edge is at the fold. The owner's half-width tab must scroll on every card, or answer by key without a view of the choices.
- Shot: HIR-09, screenshot not kept.
- Direction: At these widths the question and its answers share the first viewport with the photo.
- Component: `ReviewQueue.tsx` layout
- Annotation: violates D28 (the review answer gets an undo window, and the list stops moving under it) in its first half: that entry reserves the photo so the candidate rows stay under the finger. At 720 and 390 the reserved photo is what pushes the rows off screen. No decision covers the narrow layout. prior: none.

### HIR-10 At 390 the Review receipt and its Undo land below the fold
- Severity: S2
- Screens: `#/review`
- Where: 390/light (measured and seen)
- Repro: `#/review` at 390, press `X`, then `1` (stand down).
- Seen: The receipt with Undo is at y 1145 in an 844 px viewport. After the press, the viewport shows the next photo and nothing about what was written.
- Shot: HIR-10, screenshot not kept.
- Direction: The receipt shows where the thumb is.
- Component: `ReviewQueue.tsx` receipt
- Annotation: violates D28 (the review answer gets an undo window): a window that is off screen is not a window. prior: none.

### HIR-11 An answer that cannot be taken back writes silently (demo-measured)
- Severity: S2
- Screens: `#/review`
- Where: all
- Repro: `#/review`, press `1` six times, then `X` `3` three times.
- Seen: Each answer advances with no receipt and no note. The end screen says "You answered 6 cards", but its "This session" list shows only the 3 stand-downs. In the same no-undo case, Inventory at least says why in a toast.
- Shot: HIR-11, screenshot not kept.
- Direction: Every write gets a receipt that names the card and the answer, with or without an Undo. The session list shows every answer.
- Component: `ReviewQueue.tsx` answer path (`remember` runs only when `canTakeBack` is true)
- Annotation: violates D28 (the review answer gets an undo window) and D171 (a refusal that reaches nobody did not happen), in spirit: a write with no receipt is a write the owner cannot see. The silent path is `remember` gated on `canTakeBack`. prior: none.

### HIR-12 At 720 the Inventory list, filters and box sheet move into a bottom sheet
- Severity: S3
- Screens: `#/inventory`
- Where: 720/both (the owner's half-width desktop tab)
- Repro: `#/inventory` at 720x900.
- Seen: The page changes to the phone shell: a box chip, a stepper, a bottom tab bar. The walk list and `Manage` are inside a sheet that opens from the chip. With a mouse on a half-width window, each jump to another card is sheet open, pick, sheet close.
- Shot: HIR-12, screenshot not kept.
- Direction: At half-width desktop, keep the list beside or above the card.
- Component: `BoxBrowse.tsx` narrow layout
- Annotation: caused by D120 (the shell speaks one brand at every width, and the phone bar is a rail) and D123 (above the desk a screen asks its column). The shell switches to the phone layout by width alone, so a 720 px desktop tab gets the phone walk. prior: none.

### HIR-13 The walk list is a 183 px window at 1440x900
- Severity: S2
- Screens: `#/inventory`
- Where: 1440/both, 820/both
- Repro: `#/inventory` at 1440x900.
- Seen: The list of the box's cards shows four and a half rows (`.browse-list` is 300x183). Above it are the search, three selects, the box list and the box card. The page itself is 1265 px tall, so the screen has room, but the list does not get it.
- Shot: HIR-13, screenshot not kept.
- Direction: The walk list is the tallest thing in its column.
- Component: `BoxBrowse.tsx` rail
- Annotation: caused by D40 (the screen is three columns: the box, the card, and where its copies are). The rail column holds search, three filters, the box list and the box card above the walk list, so the list gets the remainder. prior: none.

### HIR-14 The section name is cut at the widest layout
- Severity: S3
- Screens: `#/inventory`
- Where: 1440 (box 2, and box 1 with any card ticked), 820 always
- Repro: `#/inventory?box=2` at 1440. Or box 1, tick one card.
- Seen: `SECTION 1: COMMO..., 14 CARDS` and `SECTION 1: COMM..., 11 CARDS 2/11`. The name the owner uses is cut to five letters, while the count beside it shows two times (see HIR-37).
- Shot: HIR-14, screenshot not kept.
- Direction: The name fits at 1440. Remove the duplicate count badge before the name is cut.
- Component: `SectionTitle.tsx`, and the section header in `BoxBrowse.tsx`
- Annotation: caused by the PR #456 rule in `SectionTitle.tsx` ("the NAME is the part cut short and the COUNT always stays whole"). It works against D132 (sold is folded away by default, the address leads with the name, and a section can be named): the owner knows a section by its name. The rule is an argument. Its outcome here is a name cut to five letters beside a count shown two times. prior: none.

### HIR-15 "Wrong card?" sits in the Details card's corner with no inset
- Severity: S3
- Screens: `#/inventory`
- Where: 1440/both, 820/dark
- Repro: `#/inventory`, scroll to the foot of `Details`.
- Seen: The grey pill touches the card's left and bottom edges, as if it fell out of the layout.
- Shot: HIR-15, screenshot not kept.
- Direction: Put it inside the card's padding, or beside the other card actions.
- Component: `CardHero.tsx`
- Annotation: no decision covers this. prior: none.

### HIR-16 Sheet eyebrows draw an empty slot between two dots
- Severity: S3
- Screens: `#/inventory` (Manage), `#/review` (Re-check)
- Where: all
- Repro: `#/inventory` > `Manage`. `#/review` > `Re-check every waiting card`.
- Seen: `BOX 1 · · OPEN` and `STORE-WIDE · · FREE`. A missing middle item leaves two separators and a gap.
- Shot: HIR-16, screenshot not kept.
- Direction: An eyebrow draws only the items it has.
- Component: the sheet header that `BoxOps` and the Review re-check sheet share
- Annotation: no decision covers this. D218 (a typed dot is a defect wherever it is typed) moved separators into CSS, which is why an empty item still gets its two CSS separators. prior: none.

### HIR-17 Red for "not read yet", and red for a healthy 1 live
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory` box 1 card #1 (`0 live on TCGplayer, not read yet`). Box 2 card #1 (`1 live, read 18 days ago`).
- Seen: The live count is red with a red dot in both cases. Red reads as an error, but one case is "unknown" and the other is normal.
- Shot: HIR-17, screenshot not kept.
- Direction: Keep red for a real problem. Draw "not read yet" as unknown.
- Component: `CardLocations.tsx` (every-copy counts)
- Annotation: no decision covers the colour. D115 (the reading is what the export said, and what has sold since is counted beside it) defines the figure. prior: none.

### HIR-18 Two small layout slips in the box card and the list toolbar
- Severity: S4
- Screens: `#/inventory`
- Where: 1440, 820, 390
- Repro: `#/inventory` box 1, then `?box=2`.
- Seen: `tick shown` wraps alone onto a second line under `Hide sold`. On box 2 (no `moved` figure) the `open` pill goes inline with the figures. On box 1 it is on its own line.
- Shot: HIR-18, screenshot not kept.
- Direction: One toolbar line. One box-card layout whatever figures it has.
- Component: `BoxBrowse.tsx`
- Annotation: no decision covers this. prior: none.

### HIR-19 The Inventory toast does not leave, and it covers the sheet's danger rows
- Severity: S3
- Screens: `#/inventory`
- Where: 1440/light (measured over 20 s)
- Repro: `#/inventory`, Mark sold, wait. Then open `Manage`.
- Seen: The toast was still there after 20 s and through every later step. It is over the last rows of `Details`. With the sheet open, it is over `Release listing hold`, `Reclaim photographs` and `Delete box 1`.
- Shot: HIR-19, screenshot not kept.
- Direction: A receipt leaves by itself and never covers a sheet's actions.
- Component: the toast stack in the shell, and `Inventory.tsx` `remember`
- Annotation: no decision covers the toast lifetime. D119 (the receipt lands where the sale was pressed) posts this toast beside the in-row receipt. prior: none.

### HIR-20 After a sale the card's control becomes a static chip, and the phone bar loses its action (demo-measured)
- Severity: S3
- Screens: `#/inventory`
- Where: all. The empty bar is at 720 and 390.
- Repro: `#/inventory` at 390, press the bar's `Mark sold`.
- Seen: `Mark sold` becomes a green `Sold` chip (a `span`, not a button). The sticky bar keeps a stepper and a small chip where the primary action was. The toast says that the sale cannot be put back.
- Shot: HIR-20, screenshot not kept.
- Direction: The sold state offers its way back in the same place, or says clearly why not.
- Component: `CardLocations.tsx` (`card-locations-action`), and the sticky bar in `BoxBrowse.tsx`
- Annotation: violates D57 (the sale is one press, and the button becomes the way back) in the demo state: with no undo, the button becomes a static chip, not a way back. prior: none. Demo-measured.

### HIR-21 "Wrong card?" opens its panel below the fold
- Severity: S3
- Screens: `#/inventory`
- Where: 1440/light
- Repro: `#/inventory` at 1440x900. The button is at y 1186. Scroll to it and press it.
- Seen: `Correct the listing` opens under `Details`. Its search field and result are below the viewport, and the page does not scroll to them.
- Shot: HIR-21, screenshot not kept.
- Direction: The panel that a press opens is in view when it opens.
- Component: `CardHero.tsx` and the correct-listing panel
- Annotation: no decision covers this. D252 (a wrong answer gets a correct route) built the panel. prior: none.

### HIR-22 An answer can move the next card's rows by 53 px
- Severity: S3
- Screens: `#/review`
- Where: 1440/light with the rail open (the reason chips wrap to two lines)
- Repro: `#/review` at 1440. Press row 1 with the mouse.
- Seen: The only `Number unreadable` card gets its answer, its chip goes, the chip strip drops to one line, and the question text is shorter. Row 1 moves from y 312 to y 259. A second click in the same place lands on a different row.
- Shot: HIR-22, screenshot not kept.
- Direction: The answer rows start at a fixed place from card to card.
- Component: `ReviewQueue.tsx` (`review-filters`, the question block)
- Annotation: violates D118 (a press changes what is on the screen, never where the rest of it is) and D28 (the list stops moving under it). prior: none.

### HIR-23 Retire commits on the first tap of a reason, with no undo (demo-measured)
- Severity: S3
- Screens: `#/inventory`
- Where: 1440/light
- Repro: `#/inventory`, Retire icon, press `Pulled out`.
- Seen: The card retires at once. The toast says that it "cannot be put back from here". There is no confirm step and no way back.
- Shot: HIR-23, screenshot not kept.
- Direction: Either a confirm step or an undo that works. Not neither.
- Component: the Retire dialog in `Inventory.tsx`
- Annotation: caused by D57 (the sale is one press) applied to Retire through D26 (a card leaves inventory by a state, retired). One press is safe only while an undo exists, and the demo has none. prior: none. Demo-measured.

### HIR-24 The phone box sheet opens with the search field focused
- Severity: S3
- Screens: `#/inventory`
- Where: 390/light (measured, not seen on a real phone)
- Repro: `#/inventory` at 390, press the box chip.
- Seen: The search field has focus when the sheet opens. On a real phone the keyboard would cover the box list and the walk list that the owner opened the sheet for.
- Shot: HIR-24, screenshot not kept.
- Direction: Open the sheet on the list. Focus search only when the owner asks for it.
- Component: the `BoxBrowse.tsx` sheet
- Annotation: no decision covers this. prior: none.

### HIR-25 Keyboard order differs between the two screens, and a section header takes two stops
- Severity: S4
- Screens: `#/inventory`, `#/review`
- Where: 1440/light
- Repro: Load each route, press Tab.
- Seen: On Review the first Tab lands in the page. On Inventory the first 15 Tabs stop in the sidebar. On Inventory each section header is two stops in a row with the same name.
- Shot: HIR-25, screenshot not kept.
- Direction: One start-of-focus rule for every screen. One stop per header.
- Component: the shell, and the section header in `BoxBrowse.tsx`
- Annotation: no decision covers this. prior: none.

### HIR-26 Machine codes printed on screen
- Severity: S2
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory`, Mark sold, then Retire. `#/review`, `X`. Hover a reason chip.
- Seen: The sale toast ends `(sold_origin_unknown)`, the retire toast `(retired_origin_unknown)`. The Retire dialog prints `pulled`, `damaged`, `lost`, `given_away` under each choice. The Close dialog prints `wasted_position`, `cannot_settle`, `not_listing` and the four retire codes in pills. Each reason chip and each queue row has its code as a tooltip (`low_confidence`, `no_catalog_row`, and more). In the demo, the sale toast shows on every sale.
- Shot: HIR-26, screenshot not kept.
- Direction: Codes stay off screen, tooltips included.
- Component: `Inventory.tsx` (the `doSell` note string), the Retire dialog (`inventory-machine`), the `ReviewQueue.tsx` Close dialog and the `review-filter` titles
- Annotation: violates D196 (no user-visible string may name a pipeline-internal noun) for the toast codes and the Retire dialog codes. The toast code is typed into a `note` string that the `no mechanism on screen` row does not read. The Close dialog codes are caused by a ruling in ux-2026-09-20/TASTE-CALLS.md ("the close-choice machine spelling" stays). The reason-chip and queue-row tooltips go against the owner's decision in the same file ("chip -> tooltip -> gone"). prior: ux-2026-09-20/review.md #1 (the visible reason chip). prior: fixed-then-regressed for the tooltip half: the owner ruled the tooltip gone, and the chip and row titles still carry the code. prior: ux-2026-09-20/inventory.md #3 for the retire codes.

### HIR-27 A file path printed on screen
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: any card with no photo file.
- Seen: `/banchi/demo/photos/1/1.jpg?card=demo-1-0001` under the Inventory notice, and `/banchi/demo/photos/1/42.jpg` under the Review notice.
- Shot: HIR-27, screenshot not kept.
- Direction: Say what the owner can do. Keep the path off screen.
- Component: `CardHero.tsx`, and the photo pane in `ReviewQueue.tsx`
- Annotation: violates D196 (no user-visible string may name a repository path). prior: none in ux-2026-09-20. The path is a demo path, but the same component prints the live path.

### HIR-28 Pipeline nouns across both screens
- Severity: S2
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: read both screens and their dialogs.
- Seen: Review asks "Is this the row it matched?" and "Which row is this card?", says "The export has no row for 039", offers `Search the export`, and names reasons `Not in the export`, `Two rows, one condition`, `Nothing decided the finish`. `This read` shows `Sorted as`, `Photo read`, `Queue`. Re-check "Re-resolves every waiting card against the current export". Inventory shows `Pushed 0 · Staged 0`, `Set hint`, `claims`, `provenance`, `Run demo-run-1`, `no import row yet`, `Order is 1 copy stale · re-rank`, `Re-read the inventory`, and the sheet's `NEXT INDEX`, `FILL`, `LISTING-HELD`. The Remove dialog says "sidecar", "index" and "capture id". Correct claims says "the ladder infers the finish" and "refuses the whole apply".
- Shot: HIR-28, screenshot not kept.
- Direction: Say each thing in the owner's words: "listing" and not "row", "TCGplayer's list" and not "the export", and no internal stage names.
- Component: `ReviewQueue.tsx`, `CardHero.tsx`, `CardLocations.tsx`, `BoxOps`, `Inventory.tsx`
- Annotation: violates D196 (no user-visible string may name a pipeline-internal noun). prior: none as one finding. COPY held-screen notes on main logged part of it.

### HIR-29 "Hide sold 8" counts sold and moved, and its tooltip says sold and retired
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory` box 1: `7 sold`, `1 moved`, `Hide sold 8`. Hover the chip.
- Seen: The chip label says sold. The count is 7 sold + 1 moved. The tooltip says "Sold and retired cards are folded away".
- Shot: HIR-29, screenshot not kept.
- Direction: One name for the set that the chip hides, and it agrees with the count.
- Component: `BoxBrowse.tsx` (`browse-hidesold`)
- Annotation: caused by D132 (sold is folded away by default) together with D83 (moved, a third door): the fold hides every departure, but its label names only the first. prior: none.

### HIR-30 One act, five names: Close, close without answering, stand down, stood down, closed
- Severity: S3
- Screens: `#/review`
- Where: all
- Repro: `#/review`, `X`, pick `1`. Finish the queue.
- Seen: The button is `Close`. The dialog is `Close without answering`. The group is `STAND DOWN`. The receipt is `Stood down`. The end line is `3 closed`.
- Shot: HIR-30, screenshot not kept.
- Direction: One verb for the act, everywhere.
- Component: `ReviewQueue.tsx`
- Annotation: caused by D37 (a queued question can be closed without answering it): the entry uses "stand-down" and the button says "Close". prior: none.

### HIR-31 "Card 2 of 9" beside "Queue 8"
- Severity: S3
- Screens: `#/review`
- Where: all
- Repro: `#/review`, answer one card.
- Seen: The header says `Card 2 of 9`. The Queue button says `8`. Two counts of the same queue disagree by one, and no words say why.
- Shot: HIR-31, screenshot not kept.
- Direction: One count, or two labelled counts ("1 done, 8 to go").
- Component: `ReviewQueue.tsx` header
- Annotation: caused by D164 (the undo stack is the sitting, and the counter counts the sitting). The header counts the sitting, the Queue button counts what is left, and neither says which. prior: none.

### HIR-32 Two small copy slips on Review
- Severity: S4
- Screens: `#/review`
- Where: all
- Repro: open the Re-check sheet. Read the question sentence.
- Seen: "Only **Undo**reverses an answer." has no space. The card name inside the sentence ("Draven, Audacious matched one row") is in the mono face, which is for machine strings.
- Shot: HIR-32, screenshot not kept.
- Direction: Add the space. Set names in the UI face.
- Component: `ReviewQueue.tsx`
- Annotation: violates the three type roles in CLAUDE.md "The design system" (mono is for machine strings only). No D-entry covers names in mono. D221 (money stays mono) covers money only. prior: none in ux-2026-09-20. VIS held-screen notes on main logged the mono name.

### HIR-33 On-screen contrast failures (axe, scoped to the page and its dialogs)
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: each item says where
- Repro: HIR-33 scratch file, not kept. Data: HIR-33 scratch file, not kept.
- Seen: Inventory light: the `before` and `after` labels (`.nb-key`) 3.12:1, `not read yet` (`.inv-readage`) 3.63:1, and `Box 1` in the card block (`.boxops-identity-num`) 3.63:1. Also the `open` pill 4.39:1, the retire codes 3.63:1, and the sheet notes 3.12:1 to 3.63:1. Inventory dark: `34 on hand` and `42` on the selected box cell 4.24:1, the sheet's danger details 4.17:1. Review: the `NEXT` label 2.81:1 (light, 820 and 390), the focused `Close` 4.29:1, a queue row reason 4.24:1 (dark).
- Shot: HIR-33, screenshot not kept.
- Direction: Every small label gets 4.5:1 or more in both themes.
- Component: the muted ink in `tokens.css` on the named classes
- Annotation: no decision covers these tokens. prior: none for these classes. ACC held-screen notes on main logged `#7f8791` at 3.63:1.

### HIR-34 Tick boxes are 22 px on a phone
- Severity: S3
- Screens: `#/inventory`
- Where: 390/light (16 px at desktop)
- Repro: `#/inventory` at 390, open the box chip sheet.
- Seen: Every row tick and section tick is 22x22 px, less than the 40 px floor.
- Shot: HIR-34, screenshot not kept.
- Direction: A 40 px hit area around each tick.
- Component: `BoxBrowse.tsx` (`browse-rowtick`, `browse-secttick`)
- Annotation: violates D117 (the thumb floor is the kit's, the measurement is the hit area). prior: none.

### HIR-35 Screen-reader names repeat or break
- Severity: S4
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: read the accessible names (HIR-35 scratch file, not kept).
- Seen: `Tick every card in Section 1: Commons, 11 cards (11 cards)` says the count two times. The Review position link reads `BOX 1SECTION 3CARD13`. The Manage sheet's census is an invalid `dl` (`div > div`, axe `definition-list`).
- Shot: HIR-35, screenshot not kept.
- Direction: Say each fact once, with spaces. Use valid list markup.
- Component: `BoxBrowse.tsx`, `ReviewQueue.tsx`, `BoxOps` (`boxops-census`)
- Annotation: no decision covers this. prior: none.

### HIR-36 The card panel says the same facts two to four times
- Severity: S3
- Screens: `#/inventory`
- Where: 1440 and 820 (Details open)
- Repro: `#/inventory`, card #1.
- Seen: `Identified` three times (chip, eye row, Details `State`). Name, number and game two times (title block, Details). The address four times (photo notice, card block, strip, `#1 of 34`). With one copy: `1 copy` and `1 in the boxes`.
- Shot: HIR-36, screenshot not kept.
- Direction: Each fact once on the panel. See the cut list.
- Component: `CardHero.tsx`, `CardLocations.tsx`
- Annotation: no decision covers duplication. D194 (the visible word count may only go down) is the ratchet that rewards this cut. prior: none.

### HIR-37 The section count shows two times in every header
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory`.
- Seen: `SECTION 1: COMMONS, 11 CARDS` and a count badge `11` beside it. The new title added the count, and the old badge stayed. The badge is what pushes the name into truncation (HIR-14).
- Shot: HIR-37, screenshot not kept.
- Direction: One count per header. Keep the badge only for `2/11` ticked.
- Component: the section header in `BoxBrowse.tsx`, `SectionTitle.tsx`
- Annotation: caused by PR #456 (the section title gained a count) while the older count badge stayed. D194 (the visible word count may only go down) did not catch it because the badge is a figure, not words. prior: none.

### HIR-38 Long dialogs and notices on both screens
- Severity: S3
- Screens: `#/inventory`, `#/review`
- Where: all
- Repro: `#/inventory` > `...` > `Remove this card...` (70 words) and `Correct claims` (about 120 words). `#/review` > `X` (about 110 words) and the Re-check sheet (about 70 words).
- Seen: Each dialog explains the mechanism before the choice. The cut list has the texts.
- Shot: HIR-38, screenshot not kept.
- Direction: One sentence of consequence, then the choice.
- Component: `Inventory.tsx`, `ReviewQueue.tsx`
- Annotation: no decision covers dialog length. D196 (no mechanism on screen) covers part of the content. prior: none.

### HIR-39 The key legend under the walk list is always drawn
- Severity: S4
- Screens: `#/inventory`
- Where: 1440, 820
- Repro: `#/inventory`.
- Seen: `← → card  PgUp PgDn section  X tick` stays under the list, in the 183 px column that already shows only four rows. The `?` sheet already lists the keys.
- Shot: HIR-39, screenshot not kept.
- Direction: Leave the keys to the `?` sheet, or show the legend on focus.
- Component: `BoxBrowse.tsx`
- Annotation: no decision covers this. prior: none.

## Cut list

Word counts are visible words. "Saved" is current minus proposed. Product text is in backticks.

| # | Where | Current text | Proposed text | Saved |
|---|---|---|---|---|
| 1 | Inventory subtitle | `Walk any box card by card. Sell, retire or move a copy from here.` (14) | `Sell, retire or move any card.` (6) | 8 |
| 2 | Inventory missing-photo notice | `The record has a photo but the file is not on disk. The card is still at Box 1, Section 1, Card 1.` and the path (22 and a path) | `Photo missing. Re-shoot it.` (4) | 18 and the path |
| 3 | Review missing-photo notice | `The file is not on disk. The entry has a photograph and nothing here can restore it. The card is still at its slot.` and the path (23 and a path) | `Photo missing.` (2) | 21 and the path |
| 4 | Card panel status | `Identified` chip, eye row `Identified`, Details `State Identified` (3) | the `Identified` chip only (1) | 2 |
| 5 | Card panel Details, identity | `Card Piercing Light`, `Number 023/221`, `Game Riftbound` (6) | remove, because the title block says all three (0) | 6 |
| 6 | Card panel copies | `1 copy` `1 in the boxes` (5) with one copy | `1 in the boxes` (4). Show `N copies` only when N is more than 1 | 1 |
| 7 | Card panel listing line | `Pushed 0 · Staged 0 · Room for 1 more live` (8) | `Not listed yet` (3) | 5 |
| 8 | Card block address | `BOX RB Origins Box 1 / SECTION 1 Commons / CARD 1` (10) | remove, because the strip says `Section 1, Commons, card 1 of 11` (0) | 10 |
| 9 | Section header | `SECTION 1: COMMONS, 11 CARDS` and badge `11` (6) | `Section 1: Commons, 11 cards` (5) | 1 |
| 10 | Walk list legend | `← → card PgUp PgDn section X tick` (8) | none, the `?` sheet has it (0) | 8 |
| 11 | List toolbar | `collapse all · 3 sections` (4) | `Collapse all` (2) | 2 |
| 12 | Sale toast | `Marked sold — Box 1, Section 1, Card 2 — The store cannot say what state this copy was in before the sale, so it cannot be put back from here (sold_origin_unknown).` (30) | `Sold: Gentle Gemdragon, box 1 card 2. No undo for this one.` (11) | 19 |
| 13 | Retire dialog lede | `The card leaves the inventory without a sale. Its record and photo stay, and the position is never reused.` (19) | `Leaves the box without a sale. The record stays.` (9) | 10 |
| 14 | Retire dialog codes | `pulled`, `damaged`, `lost`, `given_away` (4) | none (0) | 4 |
| 15 | Remove dialog | `Remove this card and slide the box down? This deletes the record, the photograph and the sidecar, and every card behind it in box 1 moves down one index — so every stored position above it changes. There is no undo, and this card is not necessarily still in your hand. It is refused if any card behind it has been sold, retired or listed: those records are departures and commitments rather than clutter. aiming at capture id demo-1-0008` (70) | `Delete Long Sword (box 1, card 6)? Every card after it moves up one place. No undo.` (16) | 54 |
| 16 | Correct claims help | `Switch a field on to write it; a field left off is left alone. A field switched on and left empty clears the claim.` and `Finish and rarity are per game, so the choices above come from the game selected here. The server checks every card against its own game and refuses the whole apply, naming the cards, rather than writing some of them.` (62) | `Select a field to change it. Empty clears it.` (9) | 53 |
| 17 | Manage sheet figure notes | `Never comes down, even after a sale` and `Where the next capture lands` (12) | none (0) | 12 |
| 18 | Review Close dialog codes | 7 code pills (7) | none (0) | 7 |
| 19 | Review Close dialog foot | `Delete the capture on Inventory — renumbers cards behind it, cannot be undone.` (12) | remove (0) | 12 |
| 20 | Review Re-check sheet | `Re-resolves every waiting card against the current export. A card it can place leaves the queue; the rest stay, often with a better reason. Nothing is uploaded and nothing is identified — free, and safe to run again.` and `An already-answered card never returns to the queue. Only Undo reverses an answer.` (51) | `Checks every waiting card against the latest TCGplayer list. Free. Answered cards stay answered.` (14) | 37 |
| 21 | Review question lede | `The number read as 148/221, which is in no row. Draven, Audacious matched one row in this set by name.` (20) | `No listing has 148/221. Matched by name.` (7) | 13 |
| 22 | Review `This read` disclosure | `This read what the run recorded about this card` (9) | `What was read` (3) | 6 |
| 23 | Review header buttons | `Re-check every waiting card`, a reload icon and `R` (4) | `Re-check all` (2), as it already reads at 720 | 2 |

Total saved on the first viewport and the first dialogs: about 310 words, and two paths.

## Held-screen notes

The notes that the seven lenses took on main before PR #456, re-checked on the demo after it.
`#/orders` is not in my scope, so its notes are not re-checked here.

**Coherence (`coherence.md`)**
- Box forms, three on one screen (COH-11): **still present**. The rail says `RB Origins`, the panel says `BOX 1 / RB Origins`, the 390 chip says `Box 1 (RB Origins)`.
- `122 cards · 4 boxes` beside `34 on hand` (COH-05): **still present**.
- The card panel shows the SKU as text and `Market could not be read`, with no link to Pricing or history (COH-03, COH-07): **still present**.
- Five position forms on one screen (COH-12): **changed, worse**. There are now six forms and a seventh number in the Remove dialog (HIR-01). The section header gained a count form.
- The Review pill is the only card-to-card link (COH-07): **still present**, and it lands on the box, not the card (HIR-07).
- Candidate prices in Manrope and the NEXT price in Inter (COH-15): **still present** (measured: Manrope 18 px 800 and Inter 11 px 600).

**Loop (`loop.md`)**
- After Mark sold, the box panel and the Manage sheet keep the old figures. After a nav away and back, the sold card offers Mark sold again. Both are **still present** (measured). It may be demo replay.
- The sale and retire toasts carry the code and offer no undo: **still present** (HIR-26, HIR-23).
- `1 live on TCGplayer` stays red after the sale: **still present** (HIR-17).
- The subtitle promises move, and move is only in Manage over ticked cards: **still present** (HIR-08).
- The Retire dialog prints enum codes: **still present** (HIR-26).
- At 390 the in-card Mark sold is at y 1,068: **still present**. But the sticky bar's Mark sold is in the first viewport, as it was before the merge. So this is not a blocked task.
- Review's answered count carried to Home: **not re-checked**.
- The Review missing-photo panel prints its path: **still present** (HIR-27).

**Visual (`visual.md`)**
- The Inventory missing-photo state prints a raw path in mono, and the pill `122 cards · 4 boxes` is mono: **still present**.
- Review's card name in mono: **still present** (HIR-32).
- Review's position strip at 2.80:1 in light: **changed or unknown**. Scoped axe no longer flags `.review-position`. I did not hand-measure it, so this is UNKNOWN, not fixed.
- Candidate prices in a third money face: **still present**.

**Interaction (`interaction.md`)**
- The Inventory search puts its ring on the wrapper: **still present**, and it is consistent. Noted only.
- Review's Reload is disabled and spins: **unknown**. At 80 ms after the press the button was not disabled and had no spin class. The demo reload can finish faster than that.

**Copy (`copy.md`)**
- Review prints the path, internal reason names, `Search the export`, `This read`, and `BOX 1SECTION 3CARD13`: **still present** (HIR-27, HIR-28, HIR-35).
- Inventory `122 cards 4 boxes` as a fourth count, `Run box 1`, `Nothing running`, `42 captured`, and `#1` numbering: **still present**.
- One change in this area: the photo notice address changed from `Box 4 · Section 1 · Card 1.` to `Box 1, Section 1, Card 1.` The typed dots are gone from this string.

**Access (`access.md`)**
- Review chips at 390, 28 px or 40 px: **changed**. I measured 40 px settled, in a sideways scroller with a fade mask.
- The Review NEXT label at 2.81:1: **still present** (HIR-33).
- Row checkboxes and section ticks at a 1.41:1 edge, and `.bn-select` at 1.41:1: **still present** (measured: border `rgba(15, 18, 23, 0.16)` on white, about 1.4:1).
- 33-34 nodes at `#7f8791` on white, 3.63:1: **changed**. Scoped to the page, I found 4 such nodes on Inventory at 1440 light. Most of the 33 were in the sidebar, which is outside my scope.
- The live dot pulse: **not re-checked**.

**Density (`density.md`)**
- Review shows `Box 1 · Section 3 · Card 13` two times (the position label and `This read`): **still present**.
- The Review missing-photo notice at 18 words: **still present**.
- The Inventory lede at 14 words: **still present** (cut list #1).
- The Inventory missing-photo sentence at 23 words that repeats the address: **still present** (cut list #2).

## What I could not check

- **Undo of a sale, a retire and a review answer in the real product.** The demo returns no undo for any of the three. So the undo path (`canTakeBack` true) was never on screen for Inventory, nor for Review answers. HIR-11, HIR-19, HIR-20 and HIR-23 are demo-measured.
- **Photographs.** Every demo photo URL returns 404 (`/banchi/demo/photos/1/1.jpg` gives 404). The demo recorder copies from a `captures/cards/box*/` folder that the seeded store no longer writes, because photos now have the card's name. So the photo frame, its crop, and its size next to the answer rows are UNKNOWN. I graded the missing-photo state only.
- **Box figures after a write.** After a sale, `34 on hand · 7 sold` and `Hide sold 8` did not change. The demo's reads are recorded, so I cannot tell a stale figure from the demo's frozen answers.
- **A collapsed sidebar with labels that leak out (`Sea`, `Dar`, `Serv`)** showed two times on `#/review` at 1440 in my first run (HIR-39 screenshot, not kept, `review-1440-dark.png`). Three later attempts did not reproduce it. Unknown, not a pass.
- **The on-screen keyboard on a real phone** (HIR-24) and the real touch feel.
- **Search, filters and locating a card** are the topics of other lenses. I did not grade them.
