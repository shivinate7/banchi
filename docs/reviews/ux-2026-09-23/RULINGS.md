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
  prices on zero rows. The listing door stays open and widens. The owner asked why a send
  could not include zero rows, and called the old restriction odd (owner, paraphrased).
- Box-name backfill: once the integration branch reaches main, run
  `./pkmnscan boxes names` as a preview, show the owner, and write only on the owner's yes.
- HOR-07 and undo: not diagnosed now. The owner's words: "undo in general is buggy
  everywhere, probably better to have an overall undo session at a later time than
  diagnosing it." The undo findings (HOR-07, HIR-09, HIR-10, HIR-11, HIR-20, HIR-23) move to
  that later undo session, out of wave 2.

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
- Owner, 2026-09-24: split the UX PR, if the split is doable and easy (owner, paraphrased).
  PR 1 carries the integration branch: waves 0 and 1, b-runs r6, ratchets through r3, after
  one screen verification pass. PR 2 carries wave 2 plus b-runs r7, rebased on main after
  PR #461 and the CSS sweep. Merge order: PR 1, then the CSS sweep, then PR #461, then
  PR 2.
- Owner, from "Photo issues analysis", 2026-09-24: the merge order changed. PR #461 (identity)
  merges first, then UX PR 1. The split still stands. After PR #461 merges, main merges into
  the integration branch.
  Seventeen files conflict, measured against the peer's merge-tree at `b63e90ee`. The schema
  bump becomes 12, since PR #461 already took 11. Card identity writes go only through
  `IDENTITY_WRITERS` (`docs/specs/identity-follows-sku.md` §4, the `identity writers` audit
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
  `docs/specs/iconography.md` through the kit-icons lane. Each screen lane builds its own
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
- UX-268 (nameless buyer): the owner asked, "why would a buyer have no name?" A read-only
  measurement of the real store found 0 of 834 orders without a buyer name. The fallback
  exists only for pasted orders. Orchestrator call: the fallback text reads
  "Buyer on order …NNNNN".
- Orders card details (market and live counts): the owner's words: "i'd need to see real
  visual mockups to decide." Three mockups were rendered by the orders builder: A drops the
  detail, B shows one line, C shows a table. This was pending the owner's pick.
  Answered: B, one quiet line under the card, for example "$4.20 market, 3 live".
- Orders stand-down first cutoff: the oldest Ready-to-ship day. Orchestrator call, judged safe.
- Owner, 2026-09-24, UX-254: the Inventory hide toggle becomes "In stock only". The owner's
  words: "maybe in stock only should be the toggle name? or available?" It stays on by
  default, and its count is the cards that left.
- Owner, 2026-09-24, UX-243: the button and its panel read "Change the card". Both claim
  editors read "Edit claims". Neither uses a question-form label.
- Owner, 2026-09-24: Opus was used too generously. Opus is reserved for planning,
  money/TCGplayer/store-data adversarial reviews, and whole-flow or merge builders. Sonnet
  covers screen builders, screen reviewers, fix rounds and verification.
- Orders review failed, blocking: the stand-down preview drops today's orders while the press
  sends a future cutoff instead. The fix round goes to the same builder, and stays on Opus,
  since the item can close live orders.
- Owner, 2026-09-24, Orders walk at narrow widths. The owner's words:

  ```
  try being super shrunk instead, and look at how much space is wasted by stuff i dont need
  to see when im in the order walk hogging real estate
  ```

  Build: measure the space above the walk, then add a walk mode below 1000px. That mode
  carries a slim title, Filters behind one button, and the buyer chip. It also carries a
  one-line header, the card as a thin row, and the walk filling the screen. Before-and-after
  shots go to the owner.
- Owner, 2026-09-24, on filter bars and headers generally. The owner's words:

  ```
  well i think add orders, cards to pull, and all the filters, i question whether they
  deserve all that real estate frankly it's egregious i imagined we had a plan to tighten
  them up immensely
  ```

  And:

  ```
  literally 50% of the phone view is a wasted upper currently
  ```

  System rule, from this ruling: every filter bar holds one line, search plus one Filters
  button with a count badge. Facets and sort move into the popover. A page header holds at most
  one worded primary action, with every other action an IconButton or folded into a More menu.
  Orders goes first, with before-and-after shots to the owner. A small kit lane then
  makes the filter bar's one-line popover the default, and adds a kit-adoption rule that caps
  header actions, after kit-icons merges. Every later screen lane applies the rule.
- Owner asked, 2026-09-24, whether the tightening reaches current screens, not only new ones.
  Yes: the kit's default flip, and a check that lists every current offender by lane. A lane
  counts as done only once its own entries leave that list (`BUILD-BRIEF.md`).
- Inventory review failed on three blocking items: an endless loader stops three route sweeps,
  a sold row folds on click, and the rail reorders on a sale. Round 2 goes to a fresh Sonnet
  builder, by the owner's own Opus rule, on branch `ux/inventory-r2`. UX-252 stays with the undo
  session. The value sort builds in this round. Set-name and slug search belong to the
  search-server lane.
- Owner, 2026-09-24, on the walk-mode shots. The owner's words:

  ~~~
  much better, a little overkill, but much better than before, i think you'd need ot send
  another ui/ux agent to independently review to make it better than this, and i don't think
  we have the budget for that right so probably deferring further editing is better on that
  ~~~

  Accepted as built. An independent UI/UX review of walk mode is deferred until budget allows,
  and sits on the follow-up list under no lane's ownership.
- Owner, 2026-09-24, Capture UX-069: pin the shutter, so a field opening above it never moves
  it.
- Owner, 2026-09-24, Capture UX-076. The owner asked:

  ```
  do we have that data? if so name the reason
  ```

  We do, from the server's own halt code. Each known code gets a headline and a way to resume.
  An unknown code keeps its generic wording.
- Orchestrator call: Capture header tightening stops at the measured 9.4px gain. The owner
  deferred further tuning.
- Owner, 2026-09-24, Capture motion mode. The owner's words:

  ```
  i'd love it if when i'm on motino mode i get a pause button and/or a super prominent / easy
  way (maybe spacebar) to just turn off the motion mode ... if there was just a pause play of
  motion by one press that'd be a game change
  ```

  Built in the capture lane: a prominent Pause and Resume toggle, plus a one-key toggle, in
  `SHORTCUTS`. Pausing stops firing only. The trigger's own arithmetic stays untouched.
- Owner correction, 2026-09-24. The owner's words:

  ```
  we shouldn't change any actions from how it operates now, this pause button should
  literally be like if i switched it off motion mode and play being switching it back onto
  motion mode
  ```

  Pause is the existing switch to key mode. Play is the existing switch back to motion mode,
  through that same code path. There is no new state and no new behaviour.
- Owner, 2026-09-24. The owner's words:

  ```
  add orders and cards to pull ought to be mini square buttons that'll fit on the same line
  eventually i'd imagine, but that can happen later (as long as you RECORD taht somewhere)
  ```

  Orders' "Add orders" and "Cards to pull" become small square IconButtons on the same line as
  the one-line filter bar, once kit-icons merges. This is recorded as planned in
  `D274` and in `LANES.md`.
- Owner, 2026-09-24. The owner's words:

  ```
  once reviews are passed and ci is green, you have my permission to merge
  ```

  The owner then named this session Orchestrator for PR 1 only. PR 1 merges with
  `make merge ARGS="<n> --confirm"`, a real GitHub merge, never `--admin`. It merges only after
  both the Opus merge review and the Sonnet screen pass report a pass, with CI green. The grant
  does not reach PR 2 or any other PR.
- Owner, 2026-09-24: tell "Photo issues analysis" when PR 1 merges, and treat it as a teammate.
  On merge, message it the merge commit, main's new SHA, the schema number, and the list of
  files PR 1 touched.
- Owner, 2026-09-24: a definitive ruling, finding or plan gets committed out of the scratchpad
  and into the repo, by every agent, this session included. The scratchpad is temporary.
- Owner, 2026-09-25. The owner's words:

  ```
  oh frankly if you can be precautious enough to where your sessions/agents are commiting
  often, i don't mind you running up till usage kills yall randomly given that ideally yall
  are being proactive enough going forward for the remainder of this little usage to mini
  commit often after each pass etc -- get me?
  ```

  The pause is lifted. Wave 2 goes on until usage stops it. Every agent commits and pushes
  after each pass, for each finding, each fix, and each review step. Each commit message names
  the ids done and the next id, so the branch alone is enough to resume.
- Owner, 2026-09-25, asked how a shared copy's Mark sold should look. The owner's words:
  "i had said to get rid of claiming wanted by <order> as a visual descriptor". The
  "wanted by <order>" caption on Orders pick rows is removed. Every copy is fungible (D212),
  so every Mark sold looks the same. No shared-copy signal comes back.
- 2026-09-25: PR 1 (#462) merged as `316b959e3` under the owner's grant. Ids D259 through D285
  are claimed.

## PR 2 scope (owner, 2026-09-25)
- The owner's words: "sure we can work in parallel letting pr2 go without sales and box map".
  PR 2 carries every wave-2 lane except Sales and Box map. Sales and Box map build in parallel
  now and land in PR 3.
- Codes "slot {index}" (owner, 2026-09-25): leave it, a known gap. It is recorded as an open
  item until the dormant codes feature wakes. The library lane records it in the codes
  decision and spec open items.
- Mid-word search (owner, 2026-09-25): add mid-word search. D271's one matcher wins over
  store-scaling item 8's prefix-only trade-off. It builds only if a measurement on a
  2,500-plus card store shows search stays fast. The search-server lane owns D271.
- `hide_sold` on `getBoxes` (orchestrator, process-only): the inventory lane wires the client
  flag. The search-server lane owns the server half.
- Box map order key (owner, 2026-09-25, answering D265's open question): "A key on each
  card". Every card carries its own order key. The rejected "box order is runs" shape (never
  written as an entry) is not chosen, and gets reworked. The boxmap lane owns the D265
  amendment.
- Box map single cards and ranges (owner, 2026-09-25): "Next box-map slice". A card list sits
  inside a lifted section on the Shelf.
- Owner, 2026-09-25, process-only: "You are now the head orchestrator session for banchi."
  This does not by itself carry merge authority for PR 2 and later. That is asked separately.
- Merge grant (owner, 2026-09-25, process-only, verbatim): "Yes you have perpetual merge authority in this
  session." The scope, per CLAUDE.md, covers PRs this session planned and reviewed. It applies
  once reviews pass and CI is green, through `make merge ARGS="<n> --confirm"`, never
  `--admin`. The grant is session-bound. No later session inherits it.
- Review cadence (owner, 2026-09-25: "Ensure reviews are occuring at major checkpoints and not
  repetitively over every little thing burning tokens"). Process-only.
  1. One review per lane, at lane-done, covers every round since its last review. A merge, an
     icon round, or a small-fix round gets no review of its own.
  2. Another review runs only after a fail, as a delta review of the fix. Opus is reserved for
     store, money, TCGplayer, or search paths.
  3. The PR is the major checkpoint: one Opus integration review of store and search paths,
     plus one all-screen pass.
  4. No review runs on work an open owner question may still change.
- Pricing cut-off exception (owner, 2026-09-25): "Keep the exception". A typed price equal to
  the cut-off, on a card worth less than the cut-off, is not a 25% drift, and stays out of
  "Needs you". The b-pricing lane's own decision entry, not yet landed, records this.
- Review close words, UX-255 (owner, 2026-09-25, verbatim): "I think one word is better if it
  sounds intuitive still". One verb covers the close act, only if it still reads naturally.
  The review lane's own decision entry records this.
- Pricing Q3 server half (orchestrator, applying the existing Q3 ruling — every ready copy
  goes out, and an unpriced row stays on the list, paraphrased): the send leaves out
  unanswered no-price rows and sends the rest. No new owner question was needed.
- Mid-word minimum length (orchestrator, applying the owner's "only if fast" condition): the
  substring scan needs at least 3 characters, measured again on 2,500-plus cards.
- Mid-word ceiling (orchestrator, applying the owner's "only if fast on 2,500+" condition):
  ship it. The 3-character mid-word hit measured 73ms and 76ms, p50 and p95, at 3,000 cards
  (the live store holds about 3,450), and 249ms and 260ms at 10,000. The 10,000 ceiling is
  recorded in D271, with the upgrade path (an FTS5 trigram index, its own decision).

## Quotes and the STE lint (owner, 2026-09-25)
- The owner's words: "Keep D226, reword the 7." D226 stands. A quote that trips the lint is
  rewritten as a close paraphrase, marked as a paraphrase. Every other owner quote stays
  verbatim. This applies to the records lane, and to every decision entry (b-pricing's Q3
  prose already reads this way).
- Sealed boxes killed (owner, 2026-09-25, verbatim): "what was the point of sealed boxes?
  lets kill this." The point was D20: freeze capacity, so "#40 of 53" stopped moving. D58
  took the denominator off capacity, so that premise is gone. What sealing still did: refuse
  new captures into a box, and the "so far / sealed" label. Remove the seal state, its
  control, its refusals, and its label. Existing sealed boxes become ordinary boxes. D20 and
  D58 are amended. The boxmap lane owns this — it already owns `store/master.py`'s move path.
- Q2, the 25% edge (orchestrator, applying the owner's words "25% or more"): compare exactly,
  with no rounding.

## Live store, demo seed and integration calls (2026-09-25)
- Live store (owner, 2026-09-25, paraphrased): the live store is not precious to the owner.
  The owner does not use the app now, and said that the live server or better demo seed data
  are both fine. Orchestrator use: measure on a copy of the live store first, which has no
  cost and no risk. The live server still has 4 request slots (DEBT11), so one agent at a
  time. Nothing contacts TCGplayer or spends money: that still needs the owner present.
- Review close word "Closed" (owner, 2026-09-25, on the screenshots, verbatim): "sure it looks
  decent". Accepted. D290 records it.
- Measured on a copy of the owner's store, 2026-09-25: 3,510 cards, 2,455 on hand, 916 SKUs,
  5 boxes and 13 runs. Q2's "Needs you" holds 9 of 33 unsent SKU rows: 0 with no market, 4
  worth $5 or more, and 5 typed 25% or more away. Q9: no single rule fits (the best is market
  plus $0.23, at 16.9%), so "Make this the rule" has little to offer. Sales lines at $0: 0 of
  1,406. Sealed boxes: 1 (ME01 C/UC). Box-name backfill: every box has a name, so the item
  is closed.
- Demo seed (owner, 2026-09-25, verbatim): "send a haiku agent to just populate the demo with
  more data from my actual data". Card facts only. Buyer and order data stay invented,
  because the demo is public.
- Demo seed, widened (owner, 2026-09-25, verbatim): "card photos is ok and sales dollars are
  ok". Real single-card photos are allowed if each one passes the QR-clear check. Real sale
  dollars are allowed. Buyers and orders stay invented.
- Search payload ceiling (orchestrator, under the owner's "fast on a real-sized store"
  condition): the copy of the real store stays fast, at 359ms p95 or less for a hostile query
  and 33ms mid-word. Broad hostile queries on 3,000-plus synthetic cards go past 500ms p95
  over HTTP, because of the payload size. D271 records that as known, with paging as the
  upgrade. No cap was added.
- Demo seed shape (owner, 2026-09-25, paraphrased): copy data that already exists so that the
  demo is not empty, and touch or break nothing. The test seed does not change. Real cards
  are added as extra boxes, only in the published build, behind an opt-in flag.
- Home "Cannot be filled" against the Orders filter removal (orchestrator, an integration
  conflict): option 2. Home opens `#/orders?show=<facet>`, chosen from the dominant reason.
  UX-077's intent is kept at buyer level, and the orders lane is not reopened.
  D287 records the build.
- PR 2 scope rule (orchestrator, process-only): search-server or b-pricing may not pass by
  the time the integration branch is otherwise green. Then that lane moves to PR 3, and PR 2
  goes without it.
- Existing off-by-one places (owner, 2026-09-25, paraphrased): the existing ones are not
  worth a repair, because the store is still usable, but prevention from now on is wanted. No
  repair of existing data. Prevention is the box map lane's fix: dividers stay with their
  physical card after a delete. PR 3's checkpoint must also prove two things on today's code.
  A plain "Move to box" (D83) can no longer shift a divider or a label, and neither can a
  mid-box delete.
- Deferred (orchestrator): the emit exit-code split. After a full send, `emit --listed-only`
  exits 0 over one run and 1 over several, and the route answers the same for both. It is
  older than b-pricing, and b-pricing's send matrix records it. It is its own item after PR
  2. DEBT35 records it (emit exits differently on one run and several runs).
- Demo box name (owner, 2026-09-25, verbatim): "Demo Box". No "owner" wording about these
  cards appears anywhere on the public page.

## Undo session (owner, 2026-09-25)

The plan that applies these rulings is `docs/specs/undo.md` section 11. The owner's process
ask and the interview answers, verbatim:

```
The process: "send an opus agent at first blindly just through our screens with no context
of our upbringing/decisions/building-process, and have it basically analyze all the
mechanisms we have of undo from an end user perspective. then have another agent with our
context distill those findings and create action items. Interview me for my perspective too
as maybe what's been written down for undo isn't how i feel about it anymore too."
How long: "Anytime, from a history".
A press that cannot be undone: "Never ask".
Where undo lives: "hmm how would i for example, undo the 24th capture in my capturing run
when i'm on capture 36? currently i'd have to undo 12 captures, i imagine there's a way to
yes undo all the way to 24, but also to just undo 24 -- does that make
sense in what im
trying to have u think about? marking something sold on inventory though is much more
straight forward.. etc.."
What hurts: "capture mistakes 50%, marking the wrong card sold 30%, wrong review answer 20%".
Refinement: "I do imagine that at a certain point inventory needs to lose its undo (or more
like i would never use it), it's not that I relaly need undo forever, it's just a couple
seconds isn't enough, and that a day feels arbitrary."
On expiry: "Yes, until it's built on (Recommended)".
```

- "Never ask" means no confirms. Every press is made undoable instead.
- Capture needs two acts: undo back to a card, and undo just that card.
- RULING: an undo has no clock. It lasts until the next step depends on the action. After
  that step, the fix is an ordinary action, not an undo. This refines "Anytime, from a
  history". The plan defines that step for each action.
- Measured for the plan, not a ruling: `sold_origin_unknown` (HOR-07) is seed-only. The
  owner's store has 0 sold or retired cards with no earlier state. So the owner need not
  test HOR-07 on the real store.
- Q1, the five sentences that set a clock or a cap on undo (owner, 2026-09-25, verbatim):
  "Switch all five (Recommended)". D164, D28 and D57 carry amendments. Sections 4 and 7 of
  `docs/specs/undo.md` are amended. A move is undoable (UN-14).
- Q2, "undo just N" on the capture strip (owner, 2026-09-25, verbatim): "Keep the confirm
  here only". It keeps its confirm and stays permanent. It is the one exception to "Never
  ask". The confirm's words say plainly that the removal is permanent and deletes the photo
  (UN-3).
- "This card is still here" on a shipped order (owner, 2026-09-25, verbatim): "Card back,
  order re-points". The card goes back. The order line keeps its count and becomes a
  `sold_separately` hand-fill, and the SKU's `sold_here` falls by one (UN-7,
  `docs/specs/undo.md` 11.8).

## Search, send and Home calls for PR 3 (2026-09-25)
- Search (orchestrator): 8 different mid-word terms of 3 or more letters measured over 500ms
  p95 on the copy of the real store. That is not inside the accepted "fast on a real-sized
  store" call. The fix walks the rows once. A timing guard must count work, not only wall
  time, so that it does not go red when nothing is wrong.
- Defect found (the b-pricing R7 builder, older than the lane, on main):
  `emit --cap N --live-guard F` does not count live copies. So TCGplayer can hold 2 copies
  against a cap of 1. D7 says `--cap N` holds a SKU to at most N copies live, so D7 already
  calls this a defect. It touches the send path, so it gets its own item with an Opus review
  and a send matrix row. The send-fixes lane owns the fix.
- Carried PR 2 items (orchestrator, option a): five items go to one follow-up lane after PR
  2. They are the Home h1 greeting, the capture top gap, the Fulfillment `<Page>` variant,
  Runs R2, and 6 icon entries.
- Search (orchestrator): `#` forms, composed forms with a letter or an extra zero, and a digit
  word in name text are older than the lane. D271 discloses them as known gaps, with rows in
  its case table. They do not block.
- Home "Cannot be filled" (owner, 2026-09-25, the owner's chosen option, verbatim): "New
  \"missing a copy\" filter". Orders gets a show facet for every buyer who is missing a copy,
  and Home opens it. So the number on Home and the list on Orders always agree.
  D287 and D285 record the build.
- Home's h1 (owner, 2026-09-25, verbatim): "yeah just keep the greeting". Home's h1 stays the
  greeting (D121). The scaffold check learns it as a deliberate exception, not as an
  allow-list entry. A hidden "Home" h1 was declined, because the document title already says
  Home. The layout follow-up lane lands this as an amendment to D275.
- The cap count under `--live-guard` (owner, 2026-09-25, the owner's chosen option,
  verbatim): "Take the larger (Recommended)". The cap counts the larger of the guard's live
  count and the store's pending copies, never their sum. That is right in the usual case,
  where the pending copy has landed. In the rare case, the send can go over the cap by up to
  the number of pending copies. That is a known limit. The send-fixes lane lands this in D7's
  amendment, with its own debt entry.
- Inventory's view switch (owner, 2026-09-25, verbatim): "List / Map / Sets". The box walk
  is "List", the box map is "Map", and the by-set view is "Sets", on one switch. The URL
  values stay `walk`, `shelf` and `sets` (the integration builder's call, process-only: a
  label changes, a machine key does not). D264 and D-set-view record the build.
- A typed price on a card whose market went blank (owner, 2026-09-26, the owner's chosen
  option, verbatim): "Screen shows $5.16 (Recommended)". Pricing shows the typed price in
  the field, with a short "No market price" mark, and never "Needs a price". Home counts
  that copy as ready. The screen follows what the send already lists. The send, the files
  it writes and the stored prices do not change. DEBT42 records the gap and its close.

## Re-synced from the session record, 2026-09-26

- LIVE STORE (owner, 2026-09-25, paraphrase: the live store is not precious). The owner is not using the app now. Either the live server or better demo seed data is fine. Orchestrator use: measure on a COPY of the live store first (no cost, no risk). The live server still has 4 request slots (DEBT11), so one agent at a time. Nothing contacts TCGplayer or spends money: that still needs the owner present (REAL-TEST).
- MEASURED on a copy of the owner's store, 2026-09-25 (livecopy/MEASUREMENTS.md): 3,510 cards, 2,455 on hand, 916 SKUs, 5 boxes, 13 runs. Q2 "Needs you" = 9 of 33 unsent SKU rows (0 no market, 4 worth $5+, 5 typed 25%+ away). Q9: no single rule fits (best: market + $0.23, 16.9%), so "Make this the rule" has little to offer. Sales $0 lines: 0 of 1,406. Sealed boxes: 1 (ME01 C/UC). Box-name backfill: nothing to do, every box has a name (item CLOSED).
- Demo seed shape (owner, 2026-09-25, paraphrase: copy in some of the owner's own data so demo is not empty, and touch nothing else). The test seed stays unchanged. Real cards are added as extra boxes, only in the published build, behind an opt-in flag.
- Existing off-by-one places (owner, 2026-09-25, paraphrase: not worth fixing today's data, but prevention matters going forward). No repair of existing data. Prevention is the box map lane's fix: dividers stay with their physical card after a delete. PR 3's checkpoint must also prove two things. A plain "Move to box" (D83) cannot shift a divider or a label. Neither can a mid-box delete on today's code.
- DEFECT FOUND (b-pricing R7 builder, pre-existing on main): `emit --cap N --live-guard F` does not count live copies, so TCGplayer can end up holding 2 against a cap of 1. D7 says "--cap N hold this SKU to at most N copies LIVE", so D7 already decides it: a defect. It touches the send path, so it gets its own Opus-reviewed item plus a matrix row. It lands as a DEBT entry in the PR 3 integration.
- OWNER RULINGS (2026-09-25):
  - PR 3 and PR 4 become ONE combined PR, to save review. The owner asked "can we merge pr3 and pr 4 into one larger pr to save on review?".
  - Runs fold: "Build it now, in this PR (Recommended)". The D291 fold plan is built in the combined PR by an Opus builder.
  - The "002-64" search: "No, a hyphen splits (Recommended)". A hyphen splits the number, so "002-64" must not match 264. This holds in both matchers, match.py and match.ts.
  - The "bf" search: "Bring it back (Recommended)". Letters that spell a dotted name match it again, so "bf" and "B.F" behave the same and find B.F. Sword.
- OWNER (2026-09-25): a by-set Inventory view. Asked for: "do i have anyway of seeing my inventory by set order? basically a view where i just know what qty of each card ...". Then: "send a sonnet builder on it now ...". The set view joins the combined PR. Undo joins too if it is ready in time.
- OWNER (2026-09-25), the undo process, paraphrase: send an Opus agent blind, with no context of the repo's history, to read every screen and list its undo mechanisms. Then send a second agent, with full context, to distill those findings into action items. Interview the owner too, since the owner's own feel for undo may have moved past what earlier docs say.
- OWNER UNDO INTERVIEW (2026-09-25), the answers:
  - How long: "Anytime, from a history".
  - A press that cannot be undone: "Never ask". No confirms, so make every press undoable instead.
  - Where undo lives, paraphrase: undoing capture 24 from capture 36 means undoing every capture between them, not just one. Marking a card sold on Inventory is simpler.
    - Orchestrator note: two acts, rewind-to-N and remove-just-N. The capture stack today is capped at ten, so capture 24 is out of reach from 36.
  - What hurts: "capture mistakes 50%, marking the wrong card sold 30%, wrong review answer 20%".
- OWNER, undo refinement (2026-09-25), paraphrase: at some point the owner may stop using undo on Inventory, since seconds are too short and a day feels arbitrary as a limit. On expiry, paraphrase: continue until the feature is built on (Recommended).
  - RULING: an undo has no clock. It lasts until the next step depends on the action. Examples: a sale lasts until it is shipped or its order closes. A capture lasts until its sitting ends or it is identified. A Review answer lasts until it is listed.
  - After that step, the fix is an ordinary action, not an undo. This REFINES the earlier answer "Anytime, from a history". The distiller defines that step for each action.
- OWNER, the identify strip on Review (2026-09-25): "i should be able to pick whether i want to wait and get the free pre-check or if i wanna just go right through to the bill". Then, on what "Identify now" does: "Spend immediately".
  - RULING: the strip offers two presses. "Check first" runs the existing free pre-check flow. "Identify now" starts the paid run at once, with no pre-check and no confirm.
  - The strip's ~$X is the store's past cost per card times N. This amends the two-step money gate for this press only, and it sits in line with the owner's 2026-09-12 ruling "if I want to run everything, then I get to run everything".
- OWNER, undo plan (2026-09-25):
  - Q1: "Switch all five (Recommended)". These five sentences change to "until it is built on": D164's cap of ten, the twenty seconds in D28 and D57, the undo spec's "Moved is excluded" (section 4), and the Fulfiller's twenty seconds (section 7). UN-14, move undo, is in.
  - Q2: "Keep the confirm here only". "Undo just capture N", which removes one card mid-sitting, keeps its confirm and stays permanent. It is the one exception to "Never ask".
- OWNER (2026-09-25), a defect: "i notice sections can pass the width of their container (wb1 R2 has 12 sections but only 11 show on a card's locator)". It goes to lane ux/section-ruler.
- OWNER (2026-09-25), the Inventory card locator block, paraphrase: the locators waste space, the icons are small, and the card locator should sit below the section locator. The screenshot shows BACK/THIS/FRONT neighbours, three small icon buttons (sell, retire, move), "Section 1 · card 17 of 39" over a card ruler, a section ruler, and BACK / "Section 1 of 12" / FRONT. It goes to lane ux/section-ruler as expanded scope.
- OWNER (2026-09-25), Orders sort: "on orders, on its filters, under the sort category, you can only pick placed by newest and placed by oldest, we could have more there? dollar value? etc?". Then picked all four: "Dollar value,Card count,Buyer name,Fewest drawers to open". It goes to lane ux/orders-sort, which joins the combined PR.
- OWNER (2026-09-25), the combined-order walk:
  - A card that is short on hand: "i'd say just flag as too few on hand orsomething but yea if we were to give it to someone whoever it completes". The walk flags the card as too few on hand, and the copy goes to the order it would complete.
  - The wording, paraphrase: say what is short, without wordiness.
  - Bug confirmed by diagnosis: `pickOrderFor` in OrdersWalkPane.tsx falls back to a full order (for[0]), so the server refuses the press with over_fulfilled. The spec (§8) says "first order not filled". It goes to lane ux/walk-fix.
- LESSON: a PW_ARGS glob like "tests/capture*.spec.ts" is a REGEX to Playwright and matches nothing, so the run is a false green. My briefs used it for capture, fulfillment and orders. Use "tests/capture" (a prefix) instead. The final full design-check on the integration branch is the real proof.
- OWNER (2026-09-25), the locator redesign, paraphrase: if cheaper, build boldly. Otherwise, record findings. Orchestrator call: now is cheaper, because the lane holds the context and undo-screens is the critical path anyway. The same builder does a design-led pass with 2 mockups for the owner to pick from.
- OWNER (2026-09-25), BACK/FRONT in the locator: "Keep it on each ruler". D260 stands, and each ruler keeps its own BACK/FRONT.
- OWNER (2026-09-25), the locator direction: "B, large ruler (Recommended)". The card ruler is the dominant element (64px), with 48px icons and one identity line. BACK/FRONT stays on each ruler. The build uses CSS separators (D218) and keeps $ as the sell icon.
- OWNER (2026-09-25), an empty last section: "Into the empty section (Recommended)". When a box ends with an empty section, the next captured or moved-in card goes INTO that section, behind the divider. This is fix (a): `next_key`/`_birth_key` read the last divider. It is the divider proof's F1.
- DIVIDER PROOF (Opus, on 5915ad0a): FAIL, with 3 defects in this PR. F1: an orphaned empty last divider. F2: the UN-15 divider undo sends order keys where `do_put_box` reads card counts. F3: the `unmove_card` guard mixes key and index spaces. The owner's existing data: box 2 "ME01 C/UC" has 4 boundaries each reading one card late, from the 2026-08-25 mid-box delete under the old model. 264 cards were moved before this PR with no origin recorded. 10 dividers start at a departed card. Boxes 4 and 6 have an empty last section. Report only, no correction (the owner: "not worth correcting").
- Owner, 2026-09-26, sections as sub-boxes, verbatim: "if i am in section 1, and i am capturing away, then section 1 is continuing to expand, if i am selecting section 2, then i am capturing that fills in section 2, kinda like a subbox". Divider-fix takes option (a): a divider typed ahead of the fill takes the next captures. The section picker is in THIS PR: "in this pr, but i think we need to properly plan it out before just building off these few lines, come with a plan".
