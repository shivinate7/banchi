# Owner rulings, 2026-09-23 interview

## Scope
- S1s: fold into the plan, no separate hotfix lane.
- Phase 3 builds EVERYTHING: all 164 findings, nits included.
- Text: cut EVERYTHING the density lens proposed, judgement calls included (~4,200 words).
- Every question-shaped item is an interview, not a default.

## Decisions
- D212 pull list: Cards to pull is built wrong by outcome. Copies are fungible. If an order wants 2 of card X and 14 are in stock, show "pick 2 of X" and where every copy is, never 2 preselected copies.
- D227 product page: owner leans to "merge the price views" OR "link every product name". A deliberation agent reports back first.
- D221 money font: owner wants to see both options drawn before choosing.
- D208 Pricing top: cut the legend and the verdict sentence into one slim bar. A Pricing re-interview is likely needed (hold for later).
- D225 Sales refund notes: show each only when its count is above 0 ("3 refunded lines left out").
- D196 machine words: codes go behind a details disclosure, the word list grows, AND a new browser check reads rendered text.
- D194 word ceilings: owner wants the static pinned ceilings KILLED, replaced by a different mechanism ("I don't like keeping a stagnant static pin"). Replacement: see follow-up.
- D121 Home button: KEEP AS IS.
- D194 replacement: all three — a repetition check (same sentence across rows/cards, one fact twice on a screen), a sentence-shape check (over a word limit, caption repeats its heading), AND the text-density reviewer saved as a repeatable on-demand pass. No pinned counts.
- D121 Home text: the button stays; "Behind that" lines that repeat a figure are cut.
- D214/D250 Sales: rows lead with the card name, table capped at top N with "Show all", "On the shelf" moves above the table or to its own tab.
- D61 Shipping lanes: keep the lane order; collapse every lane on a phone. (Per-card repetition is still cut under the text ruling.)
- D156 run status: name the real next step ("Ready to write"). ALSO: owner says the whole Runs step process is still unintuitive and may need more than rewording, given what is built now. Runs needs its own re-interview / redesign (like Pricing).
- D95 palette: relabel honestly ("Go to"), list every screen, light "More", drawer and palette hold focus. Owner WANTS card search in the palette eventually; build it now if low lift.
- D204 phone drawer: the footer items join the scrolling list; the footer goes.
- D142 Capture box: owner asked for more explanation. Re-asked.
- D142 Capture box: ALWAYS ASK on a fresh device ("No box yet"). Home's tile is relabelled to what it shows (the newest box).
- D197 page widths: ONE width everywhere, one top gap. NEW WIDTH TO SUPPORT: the owner uses Chrome with two tabs side by side (full height, half width, about 720 px at 1440) and wants that view designed as well as the phone view. Add 720 to every verification.
- D180/D153: "box" everywhere on screen, and the count is read live from the store.
- D105/D99/D87 after-write flow: owner wants an AGENT to review the whole flow in depth, not a multiple-choice answer. Combined with the Runs re-think (D156 note).
- Product views: a deliberation (review/product-deliberation.md) recommends a hybrid: one product view, opened as a sheet from every product name, with #/product?sku= kept as the deep link; the Pricing drawer folds into it. It also found a trap: leaving #/product?sku=X sends you back to an empty #/product (ProductHistory.tsx hashchange + writeSkuToHash). Pending the owner's pick.
- Product views: HYBRID. One product view, a sheet from every product name, #/product?sku= kept as the deep link, the Pricing drawer folded in. Fix the leave-the-page trap first.
- Multi-SKU Sales rows: owner asked to CONFIRM this is true before choosing.
- D5/D68 Fulfiller: the recommended fix (filter sold cards out, drop the dead "/" row, make "?" work). Owner: not a big rock.
- Decision reasoning printed as copy (D100 age note, D168 clear rule, D134 "Read-only", D70 "the QR is the code", D102 Kit sweep history, D86 migration note): DELETE ENTIRELY.
- D137 "Near Mint" on every row: owner did not tick it. Ambiguous against "cut everything proposed". Ask.
- Multi-SKU Sales rows (CONFIRMED in Revenue.tsx: rows group by sale.name and keep only lastSku; a foil and a normal printing share one name): the printings must be SEPARATELY IDENTIFIABLE. Split the row or combine in one chart with two labelled lines; either is acceptable. Planner picks and says which.
- D137 "Near Mint": KEEP on every row. An explicit exception to the cut-everything text ruling.

## Coordination notes (not rulings)
- Merge order: claude/integration-photo-issues FIRST. Build lanes off origin/main, then merge main into the UX integration branch after it lands, before the PR.
- sayPlace() (app/src/position.ts on the photo branch) must carry every server place label that becomes text or an accessible name.
- Token-literal guard is on commit 1e209edd (branch worktree-agent-a6e8e28f37b8e7c58), not main. Lanes self-check with `git show 1e209edd:scripts/token-literal-check.py > <scratch>` and run it on their tree. A CSS literal equal to a --bn-* value is forbidden.
- Round-two token sweep runs AFTER the UX PR. Send that session the CSS file list on merge.
- D221 money font: A, MONO everywhere (inputs and chips included) plus a check that refuses a dollar figure drawn any other way.

## Owner asks added mid-interview (2026-09-23)
- Filtering: the owner has gripes about how filtering works (Inventory, Orders, elsewhere). Lens 8 (filtering.md) was dispatched. The owner's own gripes are to be collected and interviewed.
- Locating cards: how fast the owner knows where a card is (sections from the front or back, before/after, the "Identified" icons everywhere). Lens 9 (locating.md) was dispatched, on the photo branch head.
- NEW FEATURE WISH: a visual box map with drag-and-drop of sections between boxes, where the cards move seamlessly. Deliberation dispatched (boxmap-deliberation.md). Needs a spec and a decision before any build.
- DURABILITY (owner, 2026-09-23): what is built today must be reusable. A new sidebar page must inherit the other pages' properties. Plan: wave 0 builds a page scaffold plus shared primitives (search, filter, sort, filtered count, position, status icons, money, product link), with ROUTES as the single registration point, and a mechanized check that fails a route not rendered through the scaffold or a hand-rolled kit primitive. Screen lanes migrate onto it and may not edit it.

## Flow interview (flow-deliberation.md Q1-Q8)
- Q1 Send: Banchi sends the listing file itself; "Download the file instead" stays.
- Q2 Put live: ONE PRESS sends AND makes live. AMENDS D106 (push and publish are two presses). Owner's ruling.
- Q3 Live check: COMBINED. If the app is open when the 15-minute wait ends, it checks by itself with no refresh (an in-page timer). If the app is closed, it checks on the next visit to Pricing or Home. No server-side unattended job.
- Q8 Unsent copies: Pricing names them ("17 copies written, not confirmed at TCGplayer") with "Take them back".
- Q4 Auto-match: YES, matching runs by itself when the reading finishes. A problem becomes the run's next step.
- Q5 Cost check: YES, it runs when the Identify sheet opens. Open, then spend: two presses.
- Q6 Runs screen: DECIDE AFTER the moves land. Lanes keep the #/runs route and its name, and move send/live to Pricing. Then show the owner what is left, and ask.
- Q7 'Check what is live' placement: follows Q3 (automatic). A manual press lives on Pricing's send card and in the Mark-down sheet.

## Owner gripes, verbatim-ish (2026-09-23)
- Inventory: filters must go game THEN set THEN rarity, only in that order. Hated. Filters must work in any order and combine.
- Orders buyer list (screenshot): "atrociously ugly" (tick/untick-shown header, owed bars, step-through hint).
- Orders filter bar (screenshot): the controls are not the same widths; Status opens the native macOS select; the filters are word heavy. Screenshot also shows "611 lines across 806 buyers" (lines < buyers: a count bug).
- Capture's filter/selection UI is "pretty decent": a candidate to reuse as the shared filter control.
- Sales: "literally just an excel sheet", not sexy. Needs a visual redesign.

## Lane-plan questions (LANES.md Q1-Q9)
- Q4 Card number: counts WITHIN THE SECTION ("Card 1, Card 2" under each section header, restarting at every divider). AMENDS the display half of D58 (a card's number counts the cards in the box). Renumbering on departure still holds, within the section.
- Q1 Page width: 1600 px, AND the layout must stay competent when the window is narrower (fluid down through 720, the rail, and the phone).
- Q2 720 layout: the DESKTOP RAIL (move the rail breakpoint below 720, to about 640). Not the phone chrome.
- Q5 Box order: MOST RECENT everywhere (Inventory rail, Capture picker, Home, Cards to pull).
- Q6 Money mono: CONFIRMED (the owner picked A after seeing the pictures).
- Q7 UX-073 in pricing-clip: yes (orchestrator call, same field, a D50 floor).
- Q8 Pricing drawer fold: waits for the Pricing re-interview (orchestrator call).

## Held screens released
- claude/integration-photo-issues MERGED as 70ab39e1 (PR #456). Held screens can be reviewed once the demo shows "Section N, 40 cards". Merge order: UX next, then the token-literal sweep.
- Q3 allow list: a SHRINKING offender list (file -> rule -> lane; fails on a stale entry). Not a pinned count.

## Box map (boxmap-deliberation.md)
- Owner's picture, verbatim: "sections being literally like modular building blocks where if i select move sections, i then select which box i want to move this section into, and after selecting i get a side by side 2d birds view and i literally can drag and drop the section before or after section i want of the other box". So v1 includes placement BEFORE/AFTER any section of the destination. That needs a per-card ordering key (its own decision).
- Divider travels: "the section is deleted from the previous box, think of sections as their own mini objects". A section is a first-class object: it keeps its name, divider and cards.
- Drop saving: no preference. Orchestrator default: saved at once, with a receipt holding the physical instructions and Undo on U.
- Moved cards: PRICING FOLLOWS THE CARD. The join follows a card to its new box, matched by its unique name (cid). AMENDS D165.
- Map home: a "Shelf" view inside Inventory (keeps D31).
- v1 scope: sections between boxes (before/after any section), reorder sections within a box, whole-box merge and split. Single cards and ranges come right after, and are added now IF easy on top.
- Map money: counts only in v1.
- Undo (Q4, no answer asked): orchestrator default is exact restore while neither box changed since; otherwise the way back is a new move.

## Locating (locating.md)
- Box orientation, owner's words: "if i have my cards standing up in a vertical row, the one closest to my body is the last card, and the one all the way in the back is the first card". So CARD 1 IS AT THE FAR BACK, and the highest number is nearest the owner. Every position drawing must show that orientation.
- Ruler (LOC-04/05): REDESIGN in the locating lane. It marks the exact card, uses section numbers throughout, and shows the sections before and after. AMENDS D155.

## Filtering (filtering.md)
- FLT-01 sort press: RE-SORTS AT ONCE. AMENDS D209. The freeze still stops a SALE from re-ranking the list.
- FLT-22 sold fold: NOTHING JUMPS. A sold row stays in place, marked sold, until the next box load or refresh, and then folds. D118 wins over the timing of D132.
- FLT-06/04 search: ONE FORGIVING MATCHER everywhere: name words in any order, card numbers with or without leading zeros (54/132 = 054/132), set, SKU and box, ignoring case and punctuation. Covers the server's FTS5 candidate step too.
- Gripes confirmed: Game-first order lock (changing Game clears Set/Rarity), buyer list, filter bar widths/heights, the "611 lines across 806 buyers" count (lines count owing orders, buyers count every order).

## Incident, 2026-09-23
- The held-Orders reviewer's scratch copy of main (no .git) built an app whose API fell back to localhost:8000, and it read the owner's live store once (page-load reads, no press). The captures were deleted. DEFECT to fix: the port derivation must never fall back to the main checkout's live port from a copied tree. Needs a lane (server/ports.py, app/devPort.ts).
- HOR-04 (S1): "Stand down N orders" in a buyer's Manage sheet closes every open order before today, including live Ready to Ship, and shows no cutoff (breaks D203). Owner warned.
- HOR-07: Undo on a pull fails with sold_origin_unknown on a seeded store. The owner was asked to test once on the real store.

## Sales (sales-directions.md)
- Direction B: a summary band with month bars and the shelf value, the top three cards as photo tiles, a foil/rarity mix tile, places 4-10 as bar rows, then the table.
- $0.00 lines: owner's words, "TCGplayer has all the data of what items sold at what prices tho". So the fix is NOT to exclude them: find the real sale price from TCGplayer's own data (order detail, the shipping export, or another export) and fill it in. First measure whether live lines have an empty unit_price at all (the demo has 6). Only where no TCGplayer source has a price, say so on the line.
- "On the shelf" loads on arrival (after one timing on the real store).
- Thumbnails: yes, a server lookup by SKU for another copy's photo, with a plain tile fallback.
