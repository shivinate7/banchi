# Held screen: #/orders (all seven lenses)

Reviewed on main at 70ab39e1 (PR #456). Scope: `#/orders`, its buyer list, its order walk, and the
hub header and stage strip it shares with `#/shipping`. Shipping's own lanes and the filter bar
are out of scope.

**How it was seen.** The published demo refuses `POST /orders/picks`, so the walk never draws
there (see HOR-29). To see the walk, I built main's `app/`. I ran main's own capture server on my
own port (18777). Its store is one that `make demo-seed` wrote into a scratch copy of main
(HOR scratch file, not kept). The seed has no buyer names. I gave its 7 orders invented names, and one
buyer holds 2 orders. I added 30 invented DONE orders from 30 other buyers. I added one
never-seen SKU line to 2 open orders (HOR scratch file, not kept, `hor-unseen.py`).

The demo gate was checked first. The published `#/inventory` draws "Section 1: Commons, 11 cards"
(the `SectionTitle` form), so the demo is the merged build.

Widths 1440, 820, 720, 390. Light and dark. Shots: HOR screenshot, not kept. Data: HOR scratch file, not kept.

## Grade matrix

| Route | Lens | Grade | One-line reason |
|---|---|---|---|
| #/orders | 1 Coherence | D | One screen gives five different counts. Store-wide actions live in one buyer's Manage sheet. The tabs repeat the sidebar. |
| #/orders | 2 Owner's loop | D | The pull list is a 96px scroll window at 1440. New orders are fetched only from a buyer's Manage sheet. The "short" figure is wrong. Nothing hands off to Shipping. |
| #/orders | 3 Visual system | C | Duplicate chips, a hint on top of a row, a black chip that outweighs the page, sheets with no inset, unpadded body text in the walk panel. |
| #/orders | 4 Interaction | D | Undo is offered and then refuses. A pull turns the buyer from Short to Needs a look. Tick shown changes the walk while the panel names one buyer. |
| #/orders | 5 Copy | C | Machine codes and a route path on screen. "Every ticked order's" with nothing ticked. Three words (tick, walk, Tick shown) for one act. |
| #/orders | 6 Phone, touch, a11y | C | The phone and 720 sheets have no side gutter. 10px warn pills fall to 3.84:1. Three nested scroll areas at desktop. |
| #/orders | 7 Density | C | A buyer row carries up to six signals. The Manage sheet holds 441 words. An inventory detail table fills the pull screen. |

## Findings

### HOR-01 The header's "N lines across M buyers" divides two different populations
- Severity: S1
- Screens: #/orders
- Where: all
- Repro: Seeded store with 7 open orders (6 buyers) and 30 done orders (30 other buyers). Open `#/orders`.
- Seen: The lede reads "21 lines across 36 buyers", but the list shows 6 buyers. The line count comes from the server's resolution of orders that still owe copies. The buyer count comes from `groupBuyers` over EVERY order in the ledger, done ones included. The two numbers never describe the same set. The longer the order history, the more the buyers outnumber the lines. This is the bug behind the owner's "611 lines across 806 buyers" (see Owner remarks, b).
- Shot: HOR-01, screenshot not kept.
- Direction: Say one fact about what is owed now, over one population, for example "21 copies owed to 6 buyers". Count buyers from the same open set that gives the lines, or drop one of the two numbers.
- Component: `app/src/Orders.tsx` `summaryOf`, and `OrdersHub`'s `buyerCount` (`groupBuyers(payload.orders)`, all orders). The line count is `resolution.counts` from `server/capture_server.py` over `ledger.unfulfilled()`.
- Annotation: no decision covers this. It was caused by the 2026-09-20 taste call "Orders lede names the buyer count" (docs/reviews/ux-2026-09-20/TASTE-CALLS.md), which counted buyers over every order. D193 (the ledger names the buyer) supplies `groupBuyers`. prior: ux-2026-09-20/orders.md (finding 2). That fix introduced this defect.

### HOR-02 "short" counts every owed copy on a short line, not the copies that are missing
- Severity: S1
- Screens: #/orders
- Where: all
- Repro: Select Ada Moreno (2 orders). Read the three figures under the name.
- Seen: "11 owed, 1 sold, 8 short". The four short lines each want 2 and each has 1 copy on hand. So 4 copies are missing, not 8. The walk below lists 7 cards to pull. A reader subtracts 11 − 8 and expects 3.
- Shot: HOR-02, screenshot not kept.
- Direction: "short" must be the copies that cannot be pulled (wanted minus on hand, per line). Then owed minus short equals the number of cards in the walk.
- Component: `app/src/Orders.tsx` `OrderPanel` (`short` sums `line.owed` over lines whose reason is `short`).
- Annotation: no decision covers this. D220 (Orders is inventory's screen) names the owed, sold and short triad, but not its arithmetic.

### HOR-03 The pull list is a 96px scroll window, and one card's inventory detail takes the page
- Severity: S1
- Screens: #/orders
- Where: 1440 and 820, both themes
- Repro: `#/orders` at 1440x900. Look for the list of cards to pull.
- Seen: The walk (7 cards across 6 sections for Ada) is in the 300px left column, under the buyer list and the buyer's panel. It is a `.browse-list` 96px tall (scrollHeight 452), so two rows show. The panel around it clips its own foot ("J K card" is cut at 820). The 820px right column shows one card's photo, stats, a position strip and a 14-row Details table. At 1440x900 no walk row is above the fold.
- Shot: HOR-03, screenshot not kept.
- Direction: The walk is the task. Give it the height of the screen. The card's photo and one action are enough beside it.
- Component: `app/src/Orders.tsx` `PullStage` (the `.browse-walk.bn-panel` block), and `OrdersWalkPane.tsx` `WalkList`, inside the `.browse-list` layout of `BoxBrowse.css`.
- Annotation: caused by D220 (Orders is inventory's screen): the walk sits where the section list was, and the main pane is the card pane reused whole. The outcome argues against the layout half of D220. It is an argument, not a defence.

### HOR-04 Store-wide "Stand down 5 orders" offers to close live Ready-to-ship orders
- Severity: S1
- Screens: #/orders (Manage sheet)
- Where: all
- Repro: Select any buyer. Press Manage.
- Seen: A warning block reads "5 orders, nothing recorded. 5 'Ready to ship'. Nothing sold, nothing claimed." with a primary blue "Stand down 5 orders". The rule takes every open order placed before today with nothing recorded. In the seed, those are real open orders from 3 weeks ago that TCGplayer still calls Ready to ship. No date is named. The block sits inside one buyer's sheet, but it acts on the whole store.
- Shot: HOR-04, screenshot not kept.
- Direction: Name the cutoff date, and the oldest and newest order it would close, before the press. Say so plainly when the orders are ones TCGplayer still calls Ready to ship. Move the block out of a per-buyer sheet.
- Component: `app/src/Orders.tsx` `ReconcileBacklogPanel` (the cutoff is today's date).
- Annotation: violates D203 (backlog stood down over a cutoff the operator sees). The cutoff is today's date and is never drawn. D203 also calls the reconcile one-time, but the panel draws in every Manage sheet. The status breakdown that D203 names as the guard does draw.

### HOR-05 Fetching or pasting orders is only inside one buyer's Manage sheet
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: With orders in the store, look for "Fetch from TCGplayer" on the screen. Then press Manage on any buyer.
- Seen: The screen has no fetch or paste control. "Add orders", "Fetch from TCGplayer", "Fetch two years", the status picker and the paste box are at the top of the Manage sheet, above "Ada Moreno's orders". The first step of the daily loop is behind a button for one buyer.
- Shot: HOR-05, screenshot not kept.
- Direction: Put "Fetch from TCGplayer" in the header or the rail, where the store-wide state lives.
- Component: `app/src/Orders.tsx` `OrdersHub` `wellOf`, drawn in the Manage sheet by `PullStage`.
- Annotation: caused by D220 (Orders is inventory's screen): "Fetch, paste, the status picker and the stand-downs sit behind the panel's Manage." The outcome is a store-wide act behind a per-buyer button. That is an argument to take to the owner.

### HOR-06 At 720 and 390 the buyer list and walk hide behind a buyer-name dropdown
- Severity: S2
- Screens: #/orders
- Where: 720 and 390, both themes
- Repro: `#/orders` at 720 (half of a 1440 desktop) or 390.
- Seen: Below the tabs is one field, "Ada Moreno", with a chevron. Under it is one card's detail. Who else is owed, how many cards are left, and which card comes next are only in the sheet that the field opens. At 720, the owner's side-by-side desktop gets the phone chrome, bottom tab bar included.
- Shot: HOR-06, screenshot not kept.
- Direction: At 720, show the buyer list and the walk on the page. On a phone, show at least "Ada Moreno, 7 cards left, next: Section 1 #8" above the card.
- Component: `app/src/Orders.tsx` `PullStage` (the rail sheet, `.browse-railsheet`).
- Annotation: caused by D220 (Orders is inventory's screen), which reuses the rail sheet at narrow widths. No decision covers 720. The owner asked for 720 to be designed in the D197 ruling of 2026-09-23 (RULINGS.md).

### HOR-07 The pull receipt offers Undo, and Undo then refuses
- Severity: S2
- Screens: #/orders
- Where: all (measured in the seeded store)
- Repro: Select Ada Moreno. Press Mark sold. Press Undo on the toast.
- Seen: The toast says "Marked sold: Promising Future, from Box 1, Section 1, Card 8, for Ada Moreno" with Undo. Undo answers "The card was not put back. Box 1, card 10 is sold, but the store's history records no earlier state for it…" and a code. In the same store, `#/inventory` knows this at the press and offers no Undo. The refusal also calls the card "card 10" after the receipt called it "Card 8".
- Shot: HOR-07, screenshot not kept.
- Direction: Offer Undo only where it can work, as Inventory does. Name the card the same way in the receipt and the refusal.
- Component: `app/src/Orders.tsx` `undoFromToast`. The receipt is in `OrdersWalkPane.tsx`.
- Annotation: violates D57 (the sale is one press, and the button becomes the way back). The way back is offered and then fails.

### HOR-08 A pull on a short line turns the buyer from "Short" to "Needs a look"
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: Select Ada Moreno (Short). Mark sold Promising Future (wants 2, 1 on hand).
- Seen: The buyer's pill changes to "Needs a look", and a second chip appears. In Manage, the line now reads "Every copy has left the boxes" with two stand-down buttons. The owner's own sale, recorded on this screen a second ago, shows as a problem to solve.
- Shot: HOR-08, screenshot not kept.
- Direction: A line whose on-hand copies were all pulled for this order is "short by 1", not "needs a look".
- Component: `app/src/Orders.tsx` `statusOf` (any reason other than resolved or short gives `look`).
- Annotation: no decision covers this. D113 (a line closes three ways) supplies the "no copies on hand" reason that fires here.

### HOR-09 Finishing a buyer shows "0 sold" and names no next step
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: Select Lena Park (1 card). Press Mark sold.
- Seen: The panel reads "Done, 0 owed, 0 sold, 0 short" right after the sale. Then "0 sections, Hide sold 1" and "Nothing to walk. Every ticked order's copies are either already sold or nowhere on hand." Nothing points to Shipping, which is the next stage.
- Shot: HOR-09, screenshot not kept.
- Direction: Show "1 of 1 pulled, all done" and one action to the Shipping stage.
- Component: `app/src/Orders.tsx` `OrderPanel` (sold counts `group.open` only). `OrdersWalkPane.tsx` `WalkList` draws the empty sentence.
- Annotation: no decision covers this.

### HOR-10 A walk row says where, never how many or for whom
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: Select Ada Moreno. Read the walk rows.
- Seen: Each row is "#8 Promising Future". Akali wants 2 and has 1, but it shows one row with no sign that the order wants more. With every buyer ticked, rows from seven buyers mix with no buyer name.
- Shot: HOR-10, screenshot not kept.
- Direction: Each row carries "pick 1 of 2" when short, and the buyer when the walk holds more than one.
- Component: `app/src/OrdersWalkPane.tsx` `WalkList`.
- Annotation: violates D212 (every copy is fungible, so no order claims one) as the owner restated it on 2026-09-23 (RULINGS.md): show "pick 2 of X" and where every copy is.

### HOR-11 Tick shown merges every buyer into the walk while the panel names one
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: Press "Tick shown".
- Seen: The walk grows to 8 sections of all ticked buyers' cards. The panel above it still reads "2 ORDERS, Ada Moreno, 10 owed".
- Shot: HOR-11, screenshot not kept.
- Direction: When more than one buyer is ticked, the panel says so ("7 buyers, 21 cards").
- Component: `app/src/Orders.tsx` `OrderPanel` beside `useOrderWalk`.
- Annotation: caused by D220 (Orders is inventory's screen): "Ticking a second order while in the first widens the walk live to both." The panel was not told.

### HOR-12 A buyer row stacks up to six status signals
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: `#/orders`. Look at Ada Moreno's row.
- Seen: Status dot, "2 orders" pill, "Short" chip, a second "Short" chip (one per order that is not ready), "11 owed", and a bar. The dot is the same amber for Short and Needs a look. It adds nothing the chips do not already say.
- Shot: HOR-12, screenshot not kept.
- Direction: One status per buyer (the worst), and one figure.
- Component: `app/src/Orders.tsx` `BuyerRow`.
- Annotation: caused by D193 (the ledger names the buyer): a buyer row draws an "N orders" pill and a chip per open order. prior: ux-2026-09-20/orders.md (finding 3, the meta line).

### HOR-13 One never-seen line makes a whole buyer "Needs a look"
- Severity: S2
- Screens: #/orders
- Where: all
- Repro: Tomas Ek has 5 found lines and 1 never-seen SKU.
- Seen: The row drops the green dot for amber and carries "Needs a look". But 5 of the 6 cards are ready to pull. The chip does not say what to look at.
- Shot: HOR-13, screenshot not kept.
- Direction: Say what is wrong in the chip ("1 card not in store"). Let the pullable cards still read as ready.
- Component: `app/src/Orders.tsx` `statusOf`, `STATUS_PILL`.
- Annotation: no decision covers this.

### HOR-14 The buyer list is a 216px window at every desktop height
- Severity: S2
- Screens: #/orders
- Where: 1440 and 820
- Repro: `#/orders` at 1440x900 with 6 buyers.
- Seen: `.orders-index` is 216px tall and scrolls inside the page. Three and a half buyers show. It does not grow with the window.
- Shot: HOR-14, screenshot not kept.
- Direction: Let the list take the rail's height.
- Component: `app/src/Orders.tsx` `PullStage` rail, `Orders.css` `.orders-index`.
- Annotation: caused by D220 (Orders is inventory's screen), which takes the rail skeleton of `#/inventory`.

### HOR-15 "step through buyers" sits on top of the fourth row
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820, both themes
- Repro: `#/orders`. Look at the foot of the buyer list.
- Seen: The ↑ ↓ keycaps and "step through buyers" are drawn over the list. The fourth buyer's name shows through above and behind them.
- Shot: HOR-15, screenshot not kept.
- Direction: Give the hint its own row below the list, or move it to the keyboard sheet.
- Component: `app/src/Orders.tsx` `.orders-index-hint`.
- Annotation: no decision covers this.

### HOR-16 "Tick shown / Untick shown" reads as two column headings
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: `#/orders`, top of the buyer list.
- Seen: Two centred bold words over the list, like a table header. The checkboxes they act on are named "Walk Ada Moreno" for a screen reader. Tick, walk and "Tick shown" are three names for one act, and nothing says what ticking does.
- Shot: HOR-16, screenshot not kept.
- Direction: One control that says the outcome ("Walk all 6 buyers"), and the same verb on the checkboxes.
- Component: `app/src/Orders.tsx` `.orders-select-bar`.
- Annotation: no decision covers this. D220 (Orders is inventory's screen) asks only for "one tick beside each row".

### HOR-17 The row bar measures sold, the figure beside it measures owed
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: Look at the right side of any buyer row.
- Seen: "11 owed" sits over a bar that fills by sold over wanted. So the bar is empty on almost every row. One cell holds two scales.
- Shot: HOR-17, screenshot not kept.
- Direction: Drop the bar, or make it show what the figure says.
- Component: `app/src/Orders.tsx` `BuyerRow` `.orders-index-bar`.
- Annotation: no decision covers this.

### HOR-18 Five counts for one screen
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: `#/orders`. Read the header, tab, filter and list.
- Seen: Tab "7 open" (orders), filter "All open (7)" (orders), list of 6 buyers, lede "36 buyers", lede "21 lines". Each is true about something different.
- Shot: HOR-18, screenshot not kept.
- Direction: One unit on the page (buyers or copies), and the tab pill in the same unit.
- Component: `app/src/Orders.tsx` `OrdersHub` (tabs, lede) and the filter select.
- Annotation: no decision covers this.

### HOR-19 The hub tabs repeat the sidebar and change the header under them
- Severity: S3
- Screens: #/orders, #/shipping (hub only)
- Where: all
- Repro: Press the Shipping tab.
- Seen: Orders and Shipping are both sidebar rows and both tabs. On the Shipping tab the title changes, the "Cards to pull" button goes, and the lede turns from a count into a description. The tab strip is a second navigation to two pages the nav already reaches.
- Shot: HOR-19, screenshot not kept.
- Direction: Either one sidebar row with a stage strip, or two sidebar rows and no tabs.
- Component: `app/src/Orders.tsx` `OrdersHub` `tabs`.
- Annotation: caused by D69 (the order screen and the shipping lane get a route each) and D220 (Orders is inventory's screen, "two sidebar items").

### HOR-20 A search with no match stacks four empty states
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: Type "zzz" in the buyer search.
- Seen: "No buyer matches", then "NO BUYER SELECTED, Choose a buyer on the left.", then "0 sections, Hide sold 0", then "Nothing to walk. Every ticked order's copies are either already sold or nowhere on hand." The last line is body text flush to the panel's edges, with no padding.
- Shot: HOR-20, screenshot not kept.
- Direction: One empty state with "Clear search". Hide the panel and the walk until a buyer is chosen.
- Component: `app/src/Orders.tsx` `PullStage`. `OrdersWalkPane.tsx` `WalkList`.
- Annotation: no decision covers this.

### HOR-21 The Done filter shows one folded line and selects a buyer it hides
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: Choose "Done (30)" in the filter.
- Seen: The list holds only "Earlier: 30 buyers", with no chevron. The panel beside it shows "Ivy Reyes, Done, 0 owed, 0 sold, 0 short", a buyer the list does not show. The order was filled, but the panel says "0 sold".
- Shot: HOR-21, screenshot not kept.
- Direction: Under a Done filter, list the done buyers open. Count sold from every order.
- Component: `app/src/Orders.tsx` `PullStage` "Earlier" group, `OrderPanel`.
- Annotation: caused by D193 (the ledger names the buyer), which folds buyers with nothing open under "Earlier".

### HOR-22 Manage sheet contents run flush to its edges
- Severity: S3
- Screens: #/orders
- Where: 1440, both themes
- Repro: Press Manage.
- Seen: The two warning blocks and the "Ada Moreno's orders" heading touch the sheet's left edge with no inset. The paste form above them is inset. Two primary blue buttons sit in one sheet.
- Shot: HOR-22, screenshot not kept.
- Direction: One inset for the whole sheet, and one primary action.
- Component: `app/src/Orders.tsx` `BacklogPrompt`, `ReconcileBacklogPanel`, Manage sheet.
- Annotation: no decision covers this.

### HOR-23 The rail sheet has no side gutter at 720 and 390
- Severity: S2
- Screens: #/orders
- Where: 720 and 390, both themes
- Repro: At 390 or 720, tap the buyer field.
- Seen: The filter select, the search field and the "Hide never-seen SKUs" box start at x=0. At 720 the filter drops to the left on its own row, and search and status stack to its right.
- Shot: HOR-23, screenshot not kept.
- Direction: A 16px gutter on the sheet, and one column of controls.
- Component: `app/src/Orders.tsx` `.orders-rail-toolbar` inside `.browse-railsheet`.
- Annotation: no decision covers this. prior: the loop lens held-screen note of this review.

### HOR-24 The collapsed rail keeps four letters of each name and loses the walk
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: Press "Collapse the buyer rail".
- Seen: Buyers become tiles "Ada, Lena, Toma, sam, Chri, Priy", with no status or owed count. The walk disappears, so the owner cannot pull with the rail collapsed.
- Shot: HOR-24, screenshot not kept.
- Direction: Keep the walk in the collapsed state. Collapse the buyer list, not the task.
- Component: `app/src/Orders.tsx` `buyerMiniLabel`, `PullStage`.
- Annotation: caused by D152 (every row in the collapsed rail draws one glyph on one spine).

### HOR-25 "Hide sold" is the heaviest object in the rail
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: `#/orders`, the walk panel.
- Seen: A solid black chip in light and a solid white chip in dark, for a secondary filter. It outweighs "Manage" and "Mark sold".
- Shot: HOR-25, screenshot not kept.
- Direction: Give the toggle the same weight as the other quiet controls.
- Component: `.browse-hidesold` (`BoxBrowse.css`), drawn by `PullStage`.
- Annotation: caused by D132 (sold is folded away by default) for the toggle itself. No decision covers its weight.

### HOR-26 Section titles cut the name to an ellipsis and leave a space before the comma
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: Walk panel, first section.
- Seen: "RB ORIGINS, SECTION 1: … , 11 CARDS" at 1440, and "SECTIO…, 11 CARDS" at 820. The part that is cut is the name the owner wrote on the divider, in a 300px column.
- Shot: HOR-26, screenshot not kept.
- Direction: Wrap the title to two lines in the walk. The divider name is how the hand finds the section.
- Component: `app/src/SectionTitle.tsx` in `OrdersWalkPane.tsx` `WalkList`.
- Annotation: no decision covers this. `SectionTitle` (PR #456) chose to cut the name and keep the count whole.

### HOR-27 Machine words and a route path on screen
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: Open "Why each line answered as it did". Open Manage.
- Seen: `resolved`, `short`, `no_copies_on_hand`, `sku_unknown`, `sku_unseen` and `not_a_single` show under each reason, and the same code shows under each line in Manage. Other strings: "reconcile on #/inventory", "the sale on #/inventory", "tcgplayer says Shipped", "Spoken for by A2FFC195-678998-00008", and the code `(sold_origin_unknown)` in the undo refusal.
- Shot: HOR-27, screenshot not kept.
- Direction: Words only. A link, not a path. The brand as TCGplayer.
- Component: `app/src/Orders.tsx` `WhyPanel`, `BacklogPrompt`, `OrderDetail`, `LineStandDown`, `undoFromToast`.
- Annotation: violates D196 (no mechanism on screen).

### HOR-28 "Why each line answered as it did" is far from the list and lists zeros
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: Scroll below the card detail.
- Seen: The panel sits under the card's Details table, away from the buyer list it explains. Three of six rows read 0. One of them says `Not asked on this screen; always 0.`
- Shot: HOR-28, screenshot not kept.
- Direction: Show only reasons above 0, next to the filter that uses them. Delete the row that is always 0.
- Component: `app/src/Orders.tsx` `WhyPanel`.
- Annotation: violates D196 (no mechanism on screen) for the codes. The always-0 row is a D194 (word count may only go down) case.

### HOR-29 The demo's refused walk is drawn as a vague note and raw text
- Severity: S4
- Screens: #/orders (published demo)
- Where: all
- Repro: Published demo, `#/orders`.
- Seen: "Showing only the copies this order was offered — not every copy in the store. Read it again." does not say that the read of the copies failed. The refusal sentence is drawn at body size, unpadded, inside the walk panel. At 390 the page is a note, one field and a fold.
- Shot: HOR-29, screenshot not kept.
- Direction: Say "Could not read where the copies are", and draw the refusal in the kit's notice shape.
- Component: `app/src/Orders.tsx` `.orders-store-note`. `OrdersWalkPane.tsx`.
- Annotation: no decision covers this.

### HOR-30 The inventory detail table fills the pull screen
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: `#/orders`. Scroll the right column.
- Seen: Under the photo are the copy stats, a SKU line, "Pushed 0, Staged 0, No copies can go live", a position strip, then Details. Details holds Card, Number, Game, Set hint, Finish, Rarity, Note, State, Captured, Run, Confidence, Market and Listed. None of it answers "which card, for whom, how many".
- Shot: HOR-30, screenshot not kept.
- Direction: Keep the photo, the address and Mark sold. Leave the rest to `#/inventory`.
- Component: `app/src/OrdersWalkPane.tsx` `WalkMainPane` (CardHero, CardLocations, Details).
- Annotation: caused by D220 (Orders is inventory's screen): "The main pane is inventory's card pane, one component, reused whole."

### HOR-31 Manage sheet: 441 words, and one 80-word paragraph per stuck line
- Severity: S3
- Screens: #/orders
- Where: all
- Repro: Press Manage on Ada Moreno.
- Seen: The sheet holds 441 visible words. Every line with no copies repeats the full paragraph that explains its two stand-down buttons ("records that the copy went out for this order but left through the sale on #/inventory, so nothing counted it here…").
- Shot: HOR-31, screenshot not kept.
- Direction: One sentence per button, said once per sheet.
- Component: `app/src/Orders.tsx` `LineStandDown`.
- Annotation: caused by D113 (a line closes three ways), whose two closes each carry their own explanation on every line.

### HOR-32 Small warn pills fall to 3.84:1 in the phone sheet
- Severity: S3
- Screens: #/orders
- Where: 390 and 720, light
- Repro: At 390, open the buyer sheet. Run axe.
- Seen: The 10px "Short" pills are #b45309 on #e9dfdd, 3.84:1, because the sheet's scrim tints the pill. "Needs a look" is 4.36:1. Axe also flags the shell's kbd hints (2.22:1) on this route. Those belong to the shell, not to this screen.
- Shot: HOR-32, screenshot not kept.
- Direction: 4.5:1 for 10px text on every ground the pill sits on.
- Component: `bn-pill-warn bn-pill-sm` in `BuyerRow`.
- Annotation: no decision covers this.

### HOR-33 Three scroll areas inside the page at desktop
- Severity: S3
- Screens: #/orders
- Where: 1440 and 820
- Repro: `#/orders`. Turn the wheel over the buyer list, then over the walk.
- Seen: The page scrolls, the buyer list (216px) scrolls, and the walk list (96px) scrolls. A wheel over the rail moves a different thing for each pixel. Measured, and seen in the shots as clipped lists.
- Shot: HOR-33, screenshot not kept.
- Direction: One scroll for the rail.
- Component: `.orders-index` and `.browse-list` inside `PullStage`.
- Annotation: caused by D220 (Orders is inventory's screen), through the rail skeleton it reuses.

### HOR-34 Desktop hit areas below the kit's 40px
- Severity: S4
- Screens: #/orders
- Where: 1440 and 820
- Repro: Measure the controls at 1440.
- Seen: Buyer checkboxes 16x16, "Tick shown" 24px tall, filter and status selects 28px, Manage 28px, Mark sold 28px, walk rows 32px. At 390 the phone sizes are 40px or more.
- Shot: HOR-34, screenshot not kept.
- Direction: Hit areas of 40px at every width, as the kit asks.
- Component: `BuyerRow` `.orders-index-tick`, `.orders-select-quiet`, `.bn-select`.
- Annotation: caused by D117 (the thumb floor is the kit's, and a phone-width spec reads it). The floor is measured only at phone width.

### HOR-35 A nameless buyer gets a date and number that reads as an order id
- Severity: S4
- Screens: #/orders
- Where: all
- Repro: Published demo (no buyer names).
- Seen: Rows read "09-03-26_00012" in mono. It looks like an order number and sorts like one.
- Shot: HOR-35, screenshot not kept.
- Direction: "Buyer on order …00012" or "No name, Sep 3".
- Component: `orderBuyers.ts` `unnamedBuyerLabel`, `BuyerRow`.
- Annotation: caused by D193 (the ledger names the buyer): a nameless buyer draws the short id and date tail of `unnamedBuyerLabel`.

## Cut list

Words that can go from `#/orders` with no loss of a fact (density lens):
- Lede "21 lines across 36 buyers" becomes "21 copies owed to 6 buyers" (this also fixes HOR-01).
- "Tick shown" and "Untick shown" become one "Walk all" toggle.
- The "step through buyers" hint goes to the keyboard sheet only.
- The per-order chips on the buyer row go. Keep one status per buyer.
- The owed bar under each buyer row.
- The "placed Sep 3" line with its own dot on the buyer panel. Manage already shows the order date.
- The "Pushed 0, Staged 0, No copies can go live" line and the whole Details table in the pull pane.
- In "Why each line answered as it did": the three rows at 0, the note `Not asked on this screen; always 0.`, and every machine code.
- In Manage: "A repeat skips known orders." and the 21-word sentence about what leaves this browser become a tooltip.
- In Manage: the 80-word stand-down paragraph per line is said once.
- In Manage: "Standing down marks nothing sold and claims no copy left. Any card shipped is still in its box — reconcile on #/inventory." becomes one sentence with no path.
- The empty walk sentence "Nothing to walk. Every ticked order's copies are either already sold or nowhere on hand." goes when no buyer is selected, and becomes "All pulled" when a buyer is done.
- "NO BUYER SELECTED, Choose a buyer on the left." goes under a "No buyer matches" state.

## Owner remarks, verified

**(a) The buyer list is "atrociously ugly". CONFIRMED, part by part.**
- "Tick shown / Untick shown" header: confirmed. It reads as two column headings over the list, and it names an act the list does not explain (HOR-16).
- The checkboxes: confirmed. They are 16px at desktop, and their names say "Walk", while the header says "Tick" (HOR-16, HOR-34).
- The status dots: confirmed. The dot is amber for both Short and Needs a look. So it repeats the chip beside it and does not tell the two apart (HOR-12).
- The "Needs a look" chips: confirmed. One chip draws per order that is not ready, so a 2-order buyer shows "Short" twice. One never-seen line turns a buyer with 5 pullable cards into "Needs a look" (HOR-12, HOR-13).
- The "N owed" figures with bars: confirmed. The bar fills by sold, not by owed, so it is empty on nearly every row (HOR-17).
- The "step through buyers" hint: confirmed, and worse than ugly. It is drawn on top of the fourth row (HOR-15).
- Not in the remark but from the same cause: the list is a 216px window at desktop (HOR-14).

**(b) "611 lines across 806 buyers". CONFIRMED AS A BUG.** Reproduced as "21 lines across 36 buyers" with 6 buyers owed. `summaryOf` in `app/src/Orders.tsx` gets two numbers from two sets. The lines are `resolution.counts` from `server/capture_server.py`. That resolution covers only `ledger.unfulfilled()`, the orders that still owe a copy (terminal ones too). The buyers are `groupBuyers(payload.orders)` over EVERY order in the ledger. That set includes the two-year backfill and all done orders. So the buyer count grows with history and the line count does not. Fewer lines than buyers is the expected result of the code, not a sign of odd data (HOR-01).

## Held-screen notes, verified against main

Only the `#/orders` notes are in my scope. The `#/inventory` and `#/review` notes are for the reviewers of those screens.

| Lens | Note (short) | Now |
|---|---|---|
| coherence | Rows titled "09-03-26_00012" while the lede says "7 buyers" and search says "Search buyers" | Still present on the demo, which has no buyer names (HOR-35). With names, the names show. |
| coherence | Stage tab reads "No export" until Shipping is visited, then "331 orders" | Still present. Measured on the demo: "No export" before, "331 orders" after one visit. The typed dot is gone. The count is a pill now. |
| coherence | Demo notice under the order panel is an unstyled paragraph at body size to the card edge | Still present (HOR-29). |
| loop | Every order card draws the demo's refusal as unstyled body text under "0 sections" | Still present on the demo (HOR-29). On a real server the walk draws, but only 2 rows show (HOR-03). |
| loop | With a buyer picked, the right pane holds only "Why each line answered as it did" | Changed. On the demo it is still true. On a real server the right pane now holds the card's full inventory detail (HOR-30). |
| loop | At 390 the buyer sheet has no side gutter | Still present, and also at 720 (HOR-23). |
| loop | Stage strip says "No export" until Shipping is visited once | Still present (same as the coherence note). |
| visual | Raw enum codes in the "why each line" legend | Still present (HOR-27). |
| visual | Order-id text is 11px at 3.64:1 in light | Still present. Measured 3.64:1, `#7f8791`, 11px. |
| visual | `bn-pill-sm` "Short" is 3.84:1 at 10px | Still present in the phone sheet (HOR-32). |
| interaction | Arrival by ⌘→ selects a buyer, writes `?buyer=…`, and shows the "Showing only the copies…" line | Still present on the demo. The URL became `#/orders?buyer=order%3Atcgplayer%3A…`. On a real server the "Showing only" line does not draw, because the picks read succeeds. |
| interaction | Filter select and search show focus as a tint ring | Not re-checked. It was noted only. |
| copy | Buyers show as `09-03-26_00012` | Still present on the demo. Demo data. |
| copy | `Hide never-seen SKUs`, `owed / sold / short`, `Every copy found (15)` beside `Ready to ship (5)`, `Tick shown / Untick shown` | All still present (HOR-16, HOR-02). |
| copy | Stage strip says "No export" while Shipping has 331 orders loaded | Still present. |
| copy | "Showing only the copies this order was offered…" explains a mechanism | Still present on the demo (HOR-29). |
| access | Row checkbox and `.bn-select` edges at 1.41:1 | Still present. The border is still `rgba(15, 18, 23, 0.16)` on white. |
| access | 11px ids at `#7f8791`, 3.63:1 | Still present (see the visual row). |
| access | At 360, the last list item ends at 758px in a 740px page | Changed. Nothing visible reaches past the tab bar now. One element still measures a bottom of 758px (measured, not seen). |
| access | Stage tabs 138x40 and 166x40, 4px apart | Still present, same sizes at 390. |
| density | "Why each line" row that is always 0, with its note | Still present (HOR-28). |
| density | "Showing only the copies…" (14 words) | Still present on the demo. |

## What I could not check

- The walk on the published demo. The demo refuses `POST /orders/picks`. I saw everything about the walk on my own server over a seeded scratch store.
- A line that wants 2 with 2 or more copies on hand. Every seeded SKU has exactly 1 copy, so whether the walk draws one row or two for it is UNKNOWN.
- Whether the Undo refusal (HOR-07) happens on the owner's real store. The seeded cards have no earlier history state. UNKNOWN for real cards.
- A buyer list of hundreds of names, fetched orders, and the fetch flow. The fetch is refused on the demo and needs a TCGplayer session on a server.
- Screen reader output beyond axe and the accessible names. Reduced motion.
