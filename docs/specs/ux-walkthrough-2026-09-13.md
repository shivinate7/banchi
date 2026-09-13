# UX walkthrough of the live product, 2026-09-13

Three read-only walks of the owner's live store (main checkout, 2,535 cards, 105 open orders) by
agents playing an end consumer who has never read the code: one over the selling spine (Home,
Capture, Runs, Review, Pricing), one over the library and the sell side (Inventory, Orders,
Shipping, Graveyard, Codes, the shell), one over the Fulfiller's screen. Every page ran behind a
route interceptor that aborted every non-GET request, so nothing could write. Viewports 1440 and
390 (768 for the Fulfiller), both themes. 76 raw findings; consolidated here into 38 debts, with
duplicates across walkers folded and each one checked against the rulings in `docs/decisions/`.

**Status marks.** `BRANCH` — addressed by the copy and layout work on the branch this file
arrived with (verify on merge). `SETTLED` — the walker disagreed with a recorded decision;
listed so the owner can reopen it on purpose, never fixed by a session on its own. Everything
else is open.

## Ranked top 12

1. **`#/pricing?band=top` is empty by URL and populated by click.** Same address, two results:
   a bookmark or a back-button lands on "Nothing sits in that band" under a tab badge reading 5.
   A real bug, reproduced twice. — blocker
2. **On a phone, in-app navigation keeps the previous screen's scroll offset.** Scroll down on
   Capture, jump to Runs with `,R`, land mid-list with the header and the primary actions above
   the fold. Reproduced. — blocker
3. **On a phone, Capture's own shutter button is half under the tab bar on first paint.** No
   scrolling involved. — blocker
4. **Codes is unreachable by touch.** No tab-bar slot, and the More drawer's footer block sits on
   the row Codes renders in (confirmed with `elementFromPoint`, not by eye). — blocker
5. **The command palette pre-selects the wrong screen for an exact name.** Typing `pricing`
   ranks Runs first; Enter goes to Runs. — major
6. **Home's Review tile says "nothing waiting" while Review holds an answerable card**, labelled
   "parked". Two contradictory signals about one queue. — major
7. **A run badged "Not started" shows 42 joined SKUs and populated output files.** The badge
   describes one step; nothing says which. — major
8. **Order rows are only the TCGplayer order id and a date.** Nothing to recognise an order by.
   The walker's "no buyer name" half is resolved: `D193` reopened D63/D69 and Orders now lists
   buyers by name, with a merged per-buyer walk. The id still repeats on Inventory's "Wanted"
   pill and on the Fulfiller's screen, and that half is still open. — blocker as filed, resolved
   for the buyer-name half by `D193`
9. **"Add orders" offers a hand-typed JSON textarea as a primary path.** — blocker as filed; the
   route exists for the harness and demos, so the fix is demotion behind a disclosure, not
   removal
10. **Home's red "Cannot be filled" banner has no button, only a keycap chip**, and its alarm does
    not match the calm stand-down explanation Orders gives for the same 105 orders. — major
11. **Raw identifiers in seller-facing prose**: a literal `reconcile --live` in the markdown
    dialog, `emit` and `Add to Quantity` as code pills, `sku_unseen` and `set_ambiguous` as
    reason pills, `#/inventory` as a word in a sentence, run directory names as labels. — major,
    `BRANCH` for most of the strings; the pills and the route-in-prose need a reader check
12. **Graveyard's RUN column runs off a 1440 window with no scrollbar or edge fade.** Table 1206px
    inside a 1140px scroller. — major

## By theme

### Broken behaviour (fix first; none of these are copy)

- `#/pricing?band=top` cold navigation (top 1).
- Scroll offset carried across routes on the phone (top 2).
- Shutter under the tab bar at 390 (top 3).
- More drawer footer covers the last nav row (top 4).
- Palette ranking (top 5).
- `#/inventory` never leaves its loading skeleton on a store with zero boxes — found by the
  copy worker on this worktree's empty store, not by a walker; the box-selection effect never
  fires. Real for every fresh install.
- The sidebar foot stayed "Server online" through six seconds of every request failing. Either
  the poll is slow or a failed request cannot flip it. — minor as filed, worth measuring

### Contradictions between screens

- Home's Review tile versus Review's parked card (top 6).
- The run badge versus the run's own files (top 7).
- Home's alarm versus Orders' explanation (top 10).
- Two "Card N of M" counters with different meanings side by side on the Fulfiller's screen (the
  position in the pull list and the position in the box). — major

### Identity and naming

- Order rows (top 8) — resolved by `D193`, which put buyer names on Orders. The id still
  repeats on Inventory's "Wanted" pill, which does not link to the order, and across the
  Fulfiller's screen, where it also wraps mid-string at 390 — still open. — major
- Box names: "WB1 R3", "ME01 C/UC", "UNL BBOX C/UC 1" read as product-line shorthand on Home,
  the rail and the Fulfiller's list. These are the owner's own labels and must match the sticker
  on the drawer, so the debt is the absence of a nudge at creation, not the names. — minor
- "Not a single" as a button label on a real decision. — major
- The Fulfiller's search placeholder names Charizard; nothing Pokemon is in this store. — minor
- Tab titles are lowercase single words with no product name except on Home. — minor

### Too much on screen

- Pricing's worklist: single-letter column heads, five badges and a claim sentence per row, on
  the screen where money is decided. Progressive disclosure is the fix. — major
- The sticky write bar on the phone floats over content and clips its own controls at 390. —
  major
- Capture's setup rail shows seven settings before a box is picked. Collapse Rig by default. —
  minor
- The shortcuts sheet is 78 entries with a spec-style intro and no search. — minor, intro `BRANCH`
- The Manage box sheet's FILL and NEXT INDEX tiles are unexplained to the person the sheet is
  for. — major
- The position bar under a card restates the sentence above it in 8px numerals. — minor; the
  bar is D41's, so reopening it is the owner's call
- The Fulfiller's landing list uses a third of a 1440 window. — minor
- Pricing's "Nothing loaded" caption under a skeleton reads as an answer. — minor
- Two "nothing matches" empty states stacked for one Inventory search. — minor
- Both Orders' explainer and its stand-down button sit above the first order row at 390. — minor

### Copy (the sweep on this branch covers most of it)

- The run panel's rarity-claim paragraph reads as a commit message. — `BRANCH`
- "Emit can still refuse for a reason this screen cannot see" under a green check. — `BRANCH`
- The stand-down banner's process prose. — `BRANCH`
- Cut-off status strip "10 typed · 14 held back · 0 on the rule · 0 cheap at $0.29" with no
  legend. — minor
- "Still up." as Home's greeting; "1 runs" on the same screen. — polish
- "CLAIMED · Showcase", the "This read" fields ("Photo read: none", "Sorted as: no claim"), the
  Provenance run id, catalog codes in the Fulfiller's subtitle. — minor
- "8 things on this order are not in the boxes" on the Fulfiller's screen with nothing to do
  about it. — major

### Navigation and chrome

- Orders and Shipping in the sidebar and again as an in-page stage strip. `SETTLED`: two stages
  of one hub, both reachable on purpose (the "two routes, one hub" paragraph in CLAUDE.md).
- Hide sold's chip looks the same in both states. — minor
- Shipping's drop zone leads on a phone where the only usable control is a small text link. —
  minor
- The unknown-route page drops the whole shell and offers the Fulfiller's screen as a way back.
  — minor
- "Cards to pull" in three places. — polish
- Six same-weight status pills on Orders where one bucket (71 of 105 never seen) is the story.
  — polish
- "Read a box" twice on Codes. — polish
- Graveyard's filter tabs clip at 390 with no fade. — minor
- The Fulfiller's position label wraps to three lines at 768. — minor
- "Look through a box" on the Fulfiller's screen caps at 30 of 322 with no search. — minor

## What the walkers said not to break

- Capture's no-camera state and its one button.
- Review's core answering flow: photo, one question, numbered candidates with price.
- The `,`-letter overlay and the palette as a way of moving around.
- "Walk the boxes" on Orders.
- The mobile card reflows on Inventory and Graveyard.
- The Fulfiller's pull → mark-sold control: measured in the DOM, nothing moves or overlaps under
  the thumb; ⌘K and `?` are inert there; the hand-off opens a clean tab; every DESIGN.md floor
  measured clear.

## Not verified

- Undo on the Fulfiller's mark-sold: a write, never pressed.
- Anything behind a confirm dialog: viewed, cancelled.
- The offline banner's real poll interval.

## Counts as filed

| Walk | Blocker | Major | Minor | Polish |
|---|---|---|---|---|
| Selling spine | 4 | 9 | 11 | 2 |
| Library and sell side | 3 | 7 | 16 | 4 |
| Fulfiller | 0 | 3 | 9 | 8 positive |

The raw reports and their screenshots stayed in the session's scratchpad; this file is the
record.

## One decision for the owner

Pricing states its verdict three times on one screen: the "Ready to write" headline, the four
count chips under it, and the ship bar at the foot. The copy sweep left the last two because
`app/tests/pricing.spec.ts` asserts, as behaviour, that the bar names the figure the write will
use and that the chips split typed/held/rule/cheap apart. Collapsing them is a change to what
the write's receipt guarantees, not a copy edit; say the word and it becomes one statement.
