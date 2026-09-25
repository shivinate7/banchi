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

## Pricing re-interview (pricing-deliberation.md)
- Q1 first view: EVERY ROW, the rows that need the owner on top, then the rest by value. (Not the fold-into-a-count proposal.)
- Q2 needs-you rows: no market price, OR worth $5+, OR typed price 25%+ away from today's market. Count these on the owner's store first.
- Q3 Send with unpriced rows: send every ready copy; unpriced rows stay on the list.
- Q4 slim bar: sticky at the top at 1440 and 720; on a phone, one line pinned above the tab bar.
- Q5 rule and cut-off: one line above the list with "Change", which opens one sheet (the rule, the cut-off, a box's own cut-off).
- Q6 mark-down: a "Live" tab on Pricing with the same rows. The separate sheet goes.
- Q7 mark-down send: ONE PRESS, and NO "Put the old prices back" control.
- Double-send guard (owner's words): "maybe before submitting prices there's a mandatory reconciliation that auto runs seeing my sales and live inventory". So every Send (new listings and mark-downs) first runs a live reconcile automatically (live export + sales). It sends only the copies TCGplayer does not already hold, and refuses or trims a send that would double a quantity. It shows what it trimmed.
- Live check cannot run (signed out, slow): Send REFUSES and says why, with "Try again".
- Value list (What's worth pulling, D159 bands): becomes an Inventory "by value" sort via the shared SortControl. Leaves Pricing.
- Suggest-a-rule: MEASURE the owner's typed prices first; if most follow one pattern, Pricing offers "Make this the rule" once.
- Send menu: NOTHING beside Send. The caps (at most N per card, only above the cut-off) leave the Send press. "Split in two files" lives under "Download the file instead".

## Orchestrator calls (reversible, stated to the owner)
- Search ignores accents (the "forgiving" ruling covers it).
- (SUPERSEDED by the owner's box-numbers ruling below) BoxLabel name-first with number.
- Rendered-page money check (D221): owned by text-checks (it already reads rendered text).
- "Card 1 at the far back" belongs to the locating lane (the ruler redesign), not to fulfillment.

## Search-server lane note (from Photo issues analysis)
- Reuse the number rules in store/numbers.py (strip_set_code, join_key, split_catalog_number on their branch) and pipeline/join.py:number_index_key. Keep it game-aware: Riftbound keeps its code verbatim, Pokemon composes zfill(3)/printedTotal. Fuzzy "54" to "054" is fine in SEARCH, and must never feed the join ("zfill is COMPOSITION only, never matching").

## Orchestrator calls on consolidation round 2 (stated to the owner)
- The "cut everything" text ruling also applies to the HIR and HOR cut lists.
- D196 (codes behind a disclosure) wins over the 2026-09-20 taste call for Review's Close dialog.
- UX-013 stays S1: the Fulfiller was sent to pull a card that had left the box.

## Final interview rulings (owner, 2026-09-23)
- "Slots" (HIR-05, LOC-22): "slots" in Inventory's header and strip (the box's capacity), "cards" elsewhere.
- Orders layout (D220): keep the walk model; the walk gets the screen's full height; Orders and Shipping become TWO SIDEBAR ROWS, no tabs. Amends D220's layout half and the one-screen-two-stages note in CLAUDE.md.
- Filter memory (FLT-11): in the URL on every screen (link, bookmark and back restore the view). The CLAUDE.md storage-key roster changes in docs-sweep.
- The shrinking allow list (LANES Q3) is the OWNER's ruling, not an orchestrator call.

## Box numbers are never shown (owner, 2026-09-23)
- Owner's words: "I don't want to see "Box 4" part at all, those box numbers are arbitrary index values that you get to keep on the back end, having a count of boxes is great, having each box labeled with a number is not ok. If I choose to not name a box, it can default to count+1 Box as a default name".
- So: a box is shown ONLY by its name, everywhere (screens, place labels, departed labels, receipts, pickers). The number (and bid) stay internal. A count of boxes may show.
- A new box with no name given gets a STORED default name "Box <count+1>". It is a name, so it never renumbers. If that name is taken, use the next free one (D20: names are unique).
- Overrides the orchestrator's BoxLabel call ("Mixed Singles, Box 4") and D68's "Box 3 · departed · B3 #96" form. Server-composed place labels must use the name.
- Existing unnamed boxes: backfill the stored name "Box N" from today's number, so nothing visible changes and physical labels still match. Renamable after.
- Departed card label: box NAME + section + card number within the section (the location stays). Sold/retired/moved is shown by a VISUAL differentiator (not the word "sold"/"departed"). Replaces D68's "Box 3 · departed · B3 #96" and the store key on screen.
- Lane: the server-side label composition (place labels, departed_label, receipts), the default-name-on-create, and the backfill go to the LOCATING lane, upgraded to Opus (it touches store writes: the backfill and box creation). The kit-data BoxLabel shows the name only.
- Orchestrator calls (kit-frame review): no copy-budget re-pin (text-checks merges first); ink-4 is non-text only, ink-4 text moves to ink-3; ConfirmSheet first focus = Cancel; phone top gap 16 px below 768.
- Tooling defect noticed: `npx playwright test --list` overwrites .serve/design-check.json with a pass verdict of 0 tests. Needs a guard (verdict file must not be written by a list run).
- b-pricing and b-runs are RELEASED (the Pricing re-interview and the flow interview are done). They run in sequence (both touch Pricing.tsx's write bar): b-runs first (send/live/reconcile plumbing), then b-pricing (the screen).


## Tab title (owner, 2026-09-23)
- One FIXED tab title: "番地 " then the screen name in lowercase (for example "番地 pricing"). No alternation, no "— Banchi".

## Orchestrator calls (guards review)
- PriceHistory.tsx belongs to the product lane.
- #/fulfillment is exempt from the scaffold's width and top-gap rules (D5, DESIGN.md floors), but keeps page and h1.
- Live-store COUNTS may appear in public docs; a real product string or buyer name may not.
- The D100 transport check: the docs must not claim it is replaced; recorded as an open question derived from the send rulings.
- Orchestrator call (guards): the offender list can gain keys only for a rule that does not
  exist at the merge-base (a rule born on that branch). Every existing rule's own entries only
  shrink. Home's tab title is "番地 home".
- Demo price histories (owner, 2026-09-24): record once from the owner's Mac into committed
  fixtures (D216 allows the owner's machine). CI never fetches. Refresh only when the owner
  chooses.
- Orchestrator call (filtering review): every facet trigger inside one FilterBar holds one
  equal width. The width never changes on a pick — the owner's gripe named the width
  difference itself.
- D68 twins (owner, 2026-09-24): two departed copies of one card at one place can look the
  same. The owner accepted this. No date and no key tell them apart.
- LOC-28 (owner, 2026-09-24): unread cards count as neighbours ("an unread card" / "N unread
  cards"). Amends D116.
- Orchestrator calls (locating review): a cleared box name stores the default name
  "Box <count+1>" (the next free number), never a bare number fallback. The server's refusal
  messages that print "Box {box}, card {index}" move to box name plus section plus card
  (locating round 2 owns them).
- Take them back (owner, 2026-09-24): this control appears only after a live check runs past
  the 15-minute wait for that receipt.
- Other pinned counts (owner, 2026-09-24): replace the D218 typed-dot ratchet and the D229
  per-file prose ratchet too, with rule checks plus shrinking offender lists. No pinned counts
  remain. A `ratchets` lane follows once text-checks merges.
- Orchestrator call (locating r2 review): a cleared box name's default starts at
  `len(boxes)`, and does not count the box itself. A lone box stays "Box 1".
- Orchestrator call (b-runs r2 review): for a downloaded file, "Take them back" appears only
  after a second live check, one wait later. The wait counts from when Banchi wrote the file,
  never from the owner's upload.
- Docs cost (owner, 2026-09-24): yes, fix what you touch. A reworded listed sentence cannot be
  re-listed. Editing a paragraph leaves it clean.
- Last pins (owner, 2026-09-24): convert both the line-anchor ratchet and the token-literal
  guard (D256) to offender lists. The "Run round two" session owns the token-literal guard and
  coordinates its move.
- Orchestrator call (b-runs r3 review): remove the price wait. Its premise is false —
  `reprice apply --write` already writes the new price into the price file, so a listing send
  cannot restore the old price. The wait only held copies silently.

## Owner answers, 2026-09-24 (post-compaction interview)
- First real TCGplayer test: yes, both steps, after b-runs passes review. Step 1 sends one
  listing row to Staged, checks it, then rolls it back. Step 2 sends one real copy. Stop and
  report any surprise.
- Runs screen (Q6): fold into Review. Review shows an "Identify N cards, ~$X" strip only when
  cards wait. Past runs sit behind a link. `#/runs` stays a route for links. Home's six-stage
  strip becomes five stages. The owner heard the counterpoint, a money press on a daily
  screen, and chose to fold it anyway.
- Demo licensing: accept as is. The owner heard that the risk lands on the seller account, and
  that the TCGplayer terms stay unread and unmeasured here. The owner takes that risk.
- D100 transport and send quantity: allow mixed sends. One Send can carry rows that add copies
  and zero rows that only reprice live listings. The guard checks copies on adding rows and
  prices on zero rows. The listing door stays open and widens. The owner asked why a send could
  not include zeros, and called the old restriction odd.
- Box-name backfill: once the integration branch reaches main, run
  `./pkmnscan boxes names` as a preview, show the owner, and write only on the owner's yes.
- HOR-07 and undo: not diagnosed now. The owner said undo is buggy everywhere in general, and
  asked for one overall undo session later rather than a diagnosis now. The undo findings
  (HOR-07, HIR-09, HIR-10, HIR-11, HIR-20, HIR-23) move to that later undo session, out of
  wave 2.

## Orchestrator calls, 2026-09-24
- Ratchets review failed: reflow breaks sentence identity across a line-crossing code span.
  The fix takes the reviewer's option (a), plus a stale-only pruner that stays off the commit
  path (D18). Lane: `ux/ratchets-r2`.
- Orchestrator call: the offender-list pruner (`scripts/offenders-prune.py`) needs no D18
  amendment. D18, verbatim:

  ```
  A generator may write. Nothing that writes may gate a commit.
  ```

  The pruner runs on no hook and sits outside `make check`, so it complies as written.
- Orchestrator call: ratchets r2 review failed on three should-fix items. The rename rule
  takes the reviewer's option (a): count dot growth by file and string, without the scope, and
  keep the scope in the unlisted-and-stale check. Round 3 goes to the same builder.
- Orchestrator call: ratchets r3 review failed, blocking: the whole-list dot-growth key lets a
  cross-file trade pass. The fix takes the reviewer's option (a) — file plus string, with
  renames mapped through git — and shares `offenders-prune.git_renames`. Round 4 goes to the
  same builder.
- Orchestrator calls, b-runs r5 adversarial review failed on three blocking items, B1 through
  B3. The owner can override any of these:
  - Price rows carry only the SKUs the owner typed on the worklist, sent by the screen. The
    server refuses any other price row.
  - Price rows take the mark-down door's floor.
  - A quantity of 0 plus a typed price on a live card counts as a price-only edit, and stays.
  - The Staged test door is a one-off hand call to `tcg_import.push_to_staged` and its
    rollback, run by the orchestrator under the owner's existing yes. No new press exists for
    it.
  - A 200 response from rollback is not proof by itself. Only the owner's step 1 proves it.
- Owner, 2026-09-24: a new copy of a card already live carries the stored price. The button
  names the live copies that move and the price they move to, for example
  "Send 1 copy, 2 live copies move to $19.99". A mark-down already made still sticks.
- Owner, 2026-09-24: the real test runs both steps after the overhaul reaches main. No Staged
  step runs from a worktree.
- Orchestrator calls, b-runs r6 review passed and merged. Round 7 carries the owner's
  stored-price ruling above. Round 7 also reshapes deviation 3, as the reviewer proposed.
  The `was` value now comes from the newest live export on disk. A refusal now carries
  `{sku, live, price}`, so the screen can offer to re-send. Round 7 also carries R6-2 (undo
  drops `typedHere`), R6-4 (reuse `send_held`), and a corrected record sentence.
- Owner, 2026-09-24: split the UX PR if the split is doable and easy. PR 1 carries the
  integration branch: waves 0 and 1, b-runs r6, ratchets through r3, after one screen
  verification pass. PR 2 carries wave 2 plus b-runs r7, rebased on main after PR #461 and the
  CSS sweep. Merge order: PR 1, then the CSS sweep, then PR #461, then PR 2.
- Owner, from "Photo issues analysis", 2026-09-24: the merge order changed. PR #461 (identity)
  merges first, then UX PR 1. The split still stands. After PR #461 merges, main merges into
  the integration branch.
  Seventeen files conflict, measured against the peer's merge-tree at `b63e90ee`. The schema
  bump becomes 12, since PR #461 already took 11. Card identity writes go only through
  `IDENTITY_WRITERS` (`+docs/specs/identity-follows-sku.md` §4, the `identity writers` audit
  row). `cards variants` is retired.
- Owner, 2026-09-24, iconography, a rule for every screen lane. The owner's words:

  ```
  i saw that retire got converted into an icon and its made me feel that there should be
  more iconography overall
  ```

  Common, repeated actions become icon buttons. Each button carries a tooltip and an
  accessible name. The list: Mark sold, Undo, Retire, Edit, Delete, Copy, Download, Open,
  Close, Filter, Sort. A press that spends money or cannot be undone keeps its words: Send,
  Identify, Stand down. A kit
  check holds new screens to the rule. A kit lane (`kit-icons`) builds `IconButton` plus that
  check. Screen lanes adopt it. Mark sold and Undo move from the identity session's follow-up
  into the inventory lane.
- Owner, 2026-09-24, on icons. The owner's words:

  ```
  i think it should be integrated into a certain part, with an opus agent sent to catch up
  and mold it into your plan no? wont it save on work (in the long run)
  ```

  Done: an Opus planner maps every press to a lane, icon or words. Its table lands in
  `LANES-ADDENDUM`'s "Iconography map" section, and each screen lane builds against it.
- Icon map adopted: `review/ICON-MAP.md`, written by the Opus planner. It lands in the repo as
  `+docs/specs/iconography.md` through the kit-icons lane. Each screen lane builds its own
  table rows from it.
- Owner, 2026-09-24: Orders' Mark sold converts to an icon now, even though Orders' Undo stays
  broken until the undo session. The owner accepts that a mis-tap needs a fix by hand until
  then.
- Owner, 2026-09-24: sort key stays in words. Sort direction becomes an arrow icon, with its
  words in the tooltip and the accessible name. This settles the conflict with UX-214.
- Orchestrator calls, b-runs r7 review passed. Round 8 carries: a move under the floor is
  refused, the same rule as S1. Several moves are listed on the card before the press, per the
  owner's ruling that names the price. The move's copy count is checked. A blank-priced live
  row counts as a move. Round 7 and round 8 then merge into the integration branch for PR 1,
  since PR 1 is not open yet.
- Orchestrator calls, kit-icons review failed on ten design-check failures: the toast glyph
  is invisible in light mode, and the search field grows by 2px. The fix makes the hit area a
  `::before` inset so the face keeps its own size. The overlay Close shows its word on the
  Fulfiller persona. Every should-fix item lands, plus a browser spec for `IconButton`. Round 2
  goes to the same builder.
- UX-268 (nameless buyer): the owner asked why a buyer would have no name. A read-only
  measurement of the real store found 0 of 834 orders without a buyer name. The fallback
  exists only for pasted orders. Orchestrator call: the fallback text reads
  "Buyer on order …NNNNN".
- Orders card details (market and live counts): the owner asked to see real visual mockups
  before choosing. Three mockups were rendered by the orders builder: A drops the detail, B
  shows one line, C shows a table. This was pending the owner's pick.
  Answered: B, one quiet line under the card, for example "$4.20 market, 3 live".
- Orders stand-down first cutoff: the oldest Ready-to-ship day. Orchestrator call, judged safe.
- Owner, 2026-09-24, UX-254: the Inventory hide toggle becomes "In stock only". The owner
  suggested this name. It stays on by default, and its count is the cards that left.
- Owner, 2026-09-24, UX-243: the button and its panel read "Change the card". Both claim
  editors read "Edit claims". Neither uses a question-form label.
- Owner, 2026-09-24: Opus was used too generously. Opus is reserved for planning,
  money/TCGplayer/store-data adversarial reviews, and whole-flow or merge builders. Sonnet
  covers screen builders, screen reviewers, fix rounds and verification.
