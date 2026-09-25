# Phase 3 lane plan: Banchi UX overhaul (2026-09-23, merged with round two)

This file merges the lane planner's report and its round-two addendum. `RULINGS.md` wins on
any conflict. `CONSOLIDATED.md` holds every UX-NNN finding in full. `density.md` holds the
TXT-NN cut list. This file names, for each id, only its owner lane. Look up the finding's own
text in `CONSOLIDATED.md` by id.

## Owner rulings applied after planning (override the text below)
- Page width: one width, 1600px, fluid. Every screen stays competent at every narrower width.
- 720px (half-width Chrome): the desktop rail. The rail breakpoint moves below 720px, to about
  640px. The phone chrome does not move.
- Card number: counts within the section. "Card 1" restarts at each divider. Amends the
  display half of D58.
- Box lists: most recent first, everywhere (Inventory rail, Capture picker, Home, Cards to
  pull).
- Money: mono (`.bn-money`) everywhere, confirmed.
- UX-073 moved into `pricing-clip`. The Pricing drawer fold waits for the Pricing
  re-interview.
- The held branch merged as `70ab39e1`. Every lane builds on current `origin/main`.
  `sayPlace()` in `app/src/position.ts` carries every server place label that becomes text or
  an accessible name. `make token-literal-check` runs on main. A CSS literal equal to a
  `--bn-*` value fails.
- The allow-list question (Q3) is answered: a shrinking offender list (file, rule, lane). A
  stale entry fails.

## What changed in the structure between round one and round two
1. Held screens are gone as their own group. The held branch merged as `70ab39e1`. Its three
   ids move: UX-012 to `locating`, UX-077 to `home`, UX-157 to the round-two token sweep, a
   separate session after the UX PR. Three screen lanes replace the held group in wave 2:
   `inventory`, `orders` and `review`.
2. `filtering` and `locating` move from wave 3 to wave 1. Both build shared parts that every
   wave-2 screen lane must use. `filtering` builds one filter control, one matcher and the URL
   view state. `locating` builds one place vocabulary, with section-relative numbers and card 1
   at the back. Wave 3 keeps `docs-sweep` only.
3. Five lanes are new: `ports-safety` (wave 0), `demo` (wave 1), `search-server` (wave 2), and
   the screen lanes `inventory`, `orders` and `review` (wave 2). `orders-safety` is an item
   inside the `orders` lane, not a lane of its own.
4. A file can pass from an earlier wave's owner to a later wave's owner, never inside one wave.
   A later lane takes a file only after the earlier owner merges.
5. A cross-screen finding has one owner lane. Every other lane that also draws the defect lists
   the id under "Adopts" and does not open it again. The sum check counts owner lanes only.
6. Three wave-0 lanes grew in round two: `kit-frame` gained two ids and a wider source on
   UX-047. `kit-data` gained wider sources on five ids. `fulfillment` gained three ids on
   UX-001 and UX-013, and UX-013 is now S1.
7. In wave 2, `search-server` owns `Makefile`, `scripts/checks.py` and `CLAUDE.md`, for one
   `check` target and its census line. No wave-2 lane removes a `banchi.*` storage key. A key
   removal waits for `docs-sweep`.

## Model tier
Opus is for work that touches money, the live account, the store's transactions, or safety.
Sonnet covers every other lane.

| Lane | Tier | Why |
|---|---|---|
| ports-safety | Opus | safety: a build that reaches the live store |
| demo | Opus | a public page, and the QR refusal on every copied photo |
| orders | Opus | stand-down, Mark sold and Undo write to the store |
| inventory | Opus | sell, retire, move and delete write to the store |
| review | Opus | each answer writes an identification |
| search-server | Sonnet | read-only search and counts |
| filtering | Sonnet | client parts, no writes |
| locating | Sonnet | display vocabulary, no writes |

## Shared-file rules (every lane)
1. Kit changes stay backward-compatible. Add props. Never rename or remove them.
2. Never change the value of an existing `--bn-fs-*`, `--bn-r-*` or spacing token. Add role
   tokens as `var()` aliases.
3. `docs/map.py` is generated. Run `make map-fix ARGS=--write` for your own files. Only a lane
   that creates a file writes its prose row.
4. `CLAUDE.md`, `Makefile`, `scripts/checks.py`, `docs/DESIGN.md`: one owner per wave. Wave 0:
   `guards` owns `CLAUDE.md`, `Makefile`, `checks.py`. `kit-frame` owns `DESIGN.md`. Wave 1:
   `text-checks` owns all four. Wave 2: `search-server` owns `Makefile`, `checks.py` and
   `CLAUDE.md` for its own check row. A wave-2 lane writes its own decision amendment into its
   own new decision entry under `docs/decisions/` (a slug filename, never a number).
5. Verify at 1440x900, 820x1180, 720x900, 390x844, in both themes.
6. Screen lanes never edit kit files, shell files or another lane's files. A lane lists its
   needs as "Depends on".

## Wave 0 API contract
- `app/src/kit/Page.tsx` (`kit-frame`): `Page({title?, lede?, verdict?, actions?, toolbar?,
  empty?, children})` renders `<main class="bn-page" data-bn-page>`: one h1, the verdict slot,
  the toolbar slot, the list region, the empty state. It reads `PageRouteContext` (title
  defaults to the route's `title ?? label`). `Section({title, count?, actions?, children})`
  renders an h2. The toolbar folds as one unit.
- `app/src/kit/overlay.tsx` (`kit-frame`): `Sheet`, `Modal`, `Popover` (one header, one
  "Close", a focus trap, focus returned, Escape). `useFocusTrap(ref)`. `useReturnFocus()`.
  `SheetHost`.
- `app/src/kit/sheets.ts` (`kit-data`): `registerSheet(kind, C)`, `openSheet(kind, props)`,
  `closeSheet()`. With no `product` sheet registered, `openSheet('product', {sku})` sets
  `location.hash = '#/product?sku=…'`.
- `app/src/kit/data.tsx` and `data.css` (`kit-data`): `Money`, `Count`, `FilterCount` ("12 of
  40, filtered by …, Clear"), `Select` (never the native OS menu), `FilterChips`,
  `SortControl`, `StatusBadge` plus `STATUS_TONES`, `CardLine`, `CardThumb`, `BoxLabel`, `Sep`
  (a CSS separator, D218), `ProductLink`, `OrderLink`, `Location` (wraps `PositionLabel`).
- `app/src/kit/index.tsx` (`kit-frame`) re-exports all of it.
- Merge order in wave 0: `kit-data`, then `kit-frame`, then `guards`. `pricing-clip` merges on
  its own.

## Wave 0: foundation

### W0-1 kit-frame (Sonnet, L)
Files: `app/src/kit/index.tsx`, `app/src/kit.css`, `app/src/kit/toast.tsx`,
`app/src/kit/Icon.tsx` (additive), `app/src/tokens.css`, `app/src/base.css`,
`app/src/motion.ts`, new `app/src/kit/Page.tsx`, new `app/src/kit/overlay.tsx`,
`app/src/Gallery.tsx`, `app/src/Gallery.css`, `app/tests/gallery.spec.ts`, and
`app/tests/button-stack.spec.ts`. Also `app/src/demoServer.ts`, `app/src/server.ts`
(`describeFailure` only, additive), `docs/DESIGN.md`, and the decision entries D272 (amends
D197) and D269 (amends D196's `Notice.code` exemption), both already landed.
Findings (27, plus HIR-04's receipt pattern and HIR-19's toast lifetime): see `CONSOLIDATED.md`
by id, listed in `findings.json` under `lane: "kit-frame"`.
Work: `Page`/`Section`/`Toolbar`. One `--bn-page-w` (1600, fluid) and one `--bn-page-top`.
`.bn-page` stops reading `--bn-page-max`. Container queries on the page
(`container-type: inline-size`) so tiers follow the column. A three-step heading scale as
aliases, a 13px reading role, a 10-11px label role. `--bn-ink-4` and pill inks reach 4.5:1 in
light. Field and checkbox edges reach 3:1. A visible focus ring on every chip. Reduced motion
stops the live dot and the shimmer. `Kbd` hides on a coarse pointer. `Notice` puts code and
paths behind a `<details>` "What the server said". Refusal and Retry shapes. `ReloadButton`
with a busy state. One `Loading` skeleton. `ConfirmSheet` and the undo-toast rule in
`DESIGN.md`. One meaning per icon. The status slot holds its own space (D118). `Sheet`,
`Modal`, `Popover` and `SheetHost` grow from `Codes.tsx`'s local `Sheet`. `demoServer`'s
refusal text becomes "Not in this demo." (TXT-46). The kit page deletes the design log, the
repo paths and the D102 sweep history entirely. It shows accessible forms, passes axe at 390,
and mounts the `kit-data` specimens. `DESIGN.md` adds 720 and documents the scaffold.
Rulings: D197 one width, D196 codes behind a disclosure, D102's reasoning deleted, the text
ruling.
Decisions: D197, D50, D117, D118, D196, D102, D218, D173.
Done: `make check` is green. `gallery`, `button-stack`, `page-edge` and the phone specs pass.
Axe is clean on `#/gallery` at 390 and 1440. Screenshots of `#/gallery` at four widths, both
themes, show one left edge, one width, one top gap. Every other screen's own specs still pass.
If a token change breaks `fulfillment.spec.ts`, the lane stops and reports.

### W0-2 kit-data (Sonnet, M)
Files: new `app/src/kit/data.tsx`, `data.css`, `sheets.ts`, `data.specimens.tsx`, and
`app/tests/kit-data.spec.ts`. Also `app/src/money.ts`, `app/src/dates.ts`,
`app/src/SearchField.tsx`, `SearchField.css`, `app/src/useSearch.ts`.
Findings (11): see `CONSOLIDATED.md`, `lane: "kit-data"`.
Work: `ProductLink` and `OrderLink`. `SearchField`: an empty press names what to type. `Money`:
mono, always with a `$`. `dates.ts`: one relative and one absolute format. `BoxLabel`: the
number plus the name, boxes listed most recent first. `STATUS_TONES`. Mono only for SKUs, run
ids, card numbers, key caps and money. `CardLine`. `CardThumb` with one "no photo" state.
`Sep`. `Count`. `FilterCount`, `Select` (custom, never the OS menu), `FilterChips` (filters
combine in any order), `SortControl`. Capture's picker is the pattern to follow (the
owner: "pretty decent").
Decisions: D221, D41, D58 (display amended, section-relative), D132, D142, D227, D212.
Done: `kit-data.spec.ts` renders every primitive at four widths. `ProductLink` with no open
sheet lands on `#/product?sku=`. `typecheck` and `lint` pass. Gallery specimens render.

### W0-3 guards (Sonnet, M), after kit-data and kit-frame
Files: new `scripts/kit-adoption.mjs` (a TypeScript AST reader, like
`scripts/user-strings.mjs`), new `scripts/kit-adoption-allow.json`, new
`app/tests/scaffold.spec.ts`, the landed decision entry D275, `Makefile`
(`kit-adoption`, `kit-adoption-selftest`, both in `check`), `scripts/checks.py`, `CLAUDE.md`
(the check census plus "a new page is one ROUTES entry plus a view that returns `<Page>`"),
`docs/map.py` rows.
Static rules: R1 — every `ROUTES` view file renders `<Page>` from `./kit`. R2 — outside
`app/src/kit/**`: no `role="dialog"`/`role="alertdialog"`, no `<input type="search">`, no raw
`<select>`, no kit-reserved class name (`bn-page`, `bn-head`, `bn-title`, `bn-lede`,
`bn-empty*`, `bn-notice*`, `bn-sheet*`, `bn-modal*`, `bn-money`, `bn-skeleton`, `bn-select`), no
`toLocaleDateString`/`toLocaleTimeString`/`Intl.DateTimeFormat` outside `dates.ts`, no
`$`-template with `.toFixed(` outside `money.ts`. The allow list is file, rule, lane. It fails
on an unlisted violation and on a stale entry.
Selftest (in memory, writes nothing, D18): a route view with no `Page` goes red.
`role="dialog"` in a screen goes red. The same construct inside `kit/` stays green. A stale
allow entry goes red. An unlisted violation goes red.
Runtime: `scaffold.spec.ts` sweeps `ROUTES` at four widths. It checks one `[data-bn-page]`, and
one h1 equal to the route title. It checks `max-width` equal to `--bn-page-w`, and the top gap
equal to `--bn-page-top`. It checks no horizontal scroll, the document title
"`<Title> — Banchi`", the palette listing the route, and a keys-sheet entry.
Decisions: D173, D18, D215, D218.
Done: the selftest goes red and green as above. `make check` is green. `scaffold.spec` passes
on `#/gallery`. Removing `Gallery.tsx` from the allow list stays green.

### W0-4 pricing-clip (Sonnet, S)
Files: `app/src/Pricing.tsx`, `Pricing.css`, `app/tests/pricing.spec.ts`.
Findings: UX-002 (S1), UX-073 (the same field's focus ring). See `CONSOLIDATED.md`.
Work: size the price track from its widest value. Fix the track count (5 children, 8 tracks).
Delete the dead `--bn-page-max: 1120px`. Touch nothing else on Pricing.
Done: `pricing.spec.ts` types "$1,234.56" in "Lists at" and reads it back in full at 1440,
1024, 820, 720, 390 and 360, in every variant.

### Already running: fulfillment (round-two grew this lane)
Owns `Fulfillment.tsx`/`.css`, `fulfillment.spec.ts`. Findings: UX-001 (widened, plus LOC-01,
LOC-02, LOC-15), UX-013 (widened, now S1), UX-049, 055, 089, 101, 142, plus residues of UX-004,
012, 042, 116.

## Wave 1 (after wave 0)

### W1-1 shell (Sonnet, L)
Files: `app/src/App.tsx`, `App.css`, `keys.ts`, `main.tsx`, the nav/phone/wide/page-edge/cursor
specs, `tests/shell.ts`, `tests/routes.ts`, `scripts/js-breakpoints.py` (the rail breakpoint
moves below 720), the landed decision entry D276 (amends D95).
Findings (12, widened for UX-022 and UX-092 in round two): see `CONSOLIDATED.md`,
`lane: "shell"`.
Work: `ROUTES` is the single registration point. The palette reads "Go to" and lists every
screen, off-nav included, with a Cards group from `useSearch` that opens `openSheet('product')`
(card search, low lift). Close on touch. A focus trap. The demo refusal hides the Cards group
with "Card search is not in this demo." The drawer is modal, and the footer items join the
scrolling list. The tab bar's "More" stays lit, with one door to the drawer, labels on a quiet
ground. A skip link. The keys sheet opens with its own keys. Foot icons align. The foot reads
"Server online". 720 gets the desktop rail.
Decisions: D95, D120, D204, D205, D201, D51, D227, D207.
Done: the specs pass at four widths. A throwaway route entry gets nav, palette, keys, a title
and the scaffold with no other edit. Focus never escapes an open palette or drawer (nav.spec's
own words: "focus never escapes the open palette, keys sheet or phone drawer (UX-014)"). The
palette finds "Product history" and a demo card. `make check` is green.
Follow-up: `App.css`'s `.app-keys` still switches at 767, "to follow the kit's edge", while
the kit now switches at 639. Align to 639 in a small follow-up (docs-sweep or a kit-3 item).

### W1-2 text-checks (Sonnet, M)
Deletes `app/tests/copy-budget.spec.ts`, `copy-budget.json`, `scripts/copy-budget.mjs`. Edits
`scripts/docs-audit.py` (drops D194, moves `NO_MECHANISM_WORDS` into new
`scripts/machine-words.json`), `typed-interpunct-pin.mjs`, `ste-ratchet-pin.py` comments,
`app/tests/routeFixtures.ts`, `Makefile`, `checks.py`, `CLAUDE.md`, `DESIGN.md`, and marks D194
superseded. New `app/tests/text-shape.spec.ts`, `machine-words.spec.ts`,
`scripts/text-density/` (moved from the review scratchpad), a `text-density` Makefile target
(on demand, never in `check`), `.claude/skills/text-density/SKILL.md`, the landed decision entry D284.
Checks: repetition (a sentence of four words or more on three or more rows or cards, or one
number-plus-noun fact stated twice on a screen). Sentence shape (over 25 words, or a caption
repeating 60 percent or more of its heading's tokens). Machine words read from every route's
rendered text, plus request paths. All three run over the populated route fixtures at 1440 and
390.
Done: no reference to `copy-budget` remains outside a listed exemption. `check` and
`docs-audit` are green. A mutation (a repeated sentence on a Shipping card) turns the spec red.
`make text-density` prints a cut table for `#/`.

### W1-3 product (Sonnet, M)
Files: `app/src/ProductHistory.tsx`, `.css`, `app/tests/product-history.spec.ts`, new
the landed decision entry D278 (amends D227, D62).
Findings: UX-027, UX-132, UX-183 (new in round two).
Work: fix the leave-the-page trap first (a hash that does not start with `#/product` is
ignored — the `hashchange` listener and `writeSkuToHash`'s `replaceState` cause it). Extract
`ProductHistoryView({sku})`. `registerSheet('product', ProductSheet)` with "Open as page". The
page adopts `Page`. The name field uses `SearchField` plus `useSearch`. Cut TXT-40. Printings
of one card stay separately identifiable.
Done: from `#/product?sku=X`, one nav press lands on the target. `openSheet` opens over
`#/gallery` with no route change. "Open as page" lands on the route. The name field finds a
demo card. Verified at four widths.

### W1-4 demo (Opus, M), after kit-frame
Files: `scripts/demo-record.py`, `scripts/demo-seed.py`, `app/src/demoServer.ts` (handed off
from `kit-frame` after it merges), `docs/specs/demo.md`, new
`app/tests/demo-coverage.spec.ts`.
Findings: UX-216. Demo coverage rows (counted apart from the UX sum, 14 rows): the graveyard
list, `#/product` data, Inventory search, and Pricing's price-history sheet. Also the Orders
walk plan and pull list, Sales' "Value my stock" and "Compare to today's market", and demo
photographs returning 404. Also Home's box rows after a sale, the shipping file state on Home
and Orders, the demo refusal text, and Fulfillment search. Also undo answers, Pricing's value
bands and a two-run scope, and Inventory facet counts.
Work: copy photos from the current layout (`photos/<xx>/<sha>.jpg`). The recorder today copies
none. Keep the QR refusal on every copied photo (opsec). Record undo answers, picks, the walk
plan, facet counts, the graveyard, one product history, the value bands and the Cards-to-pull
search. Patch the box walk after a sale. Refuse whatever stays unrecorded, by name ("Not in
this demo.").
Decisions: D183, D126, D52, `docs/specs/demo.md`.
Depends on: `kit-frame` (the refusal text). The shell's palette card search needs a recorded or
refused `/search` answer from this lane.
Done: `make demo-static`, then the spec against `make demo-preview`. Every photo on Inventory,
Review, Capture and Pricing answers 200. Orders draws a walk. Mark sold, then Undo, restores
the card. A Game pick draws counts. A photo whose QR decodes is still refused. `make
demo-freshness` and `make check` are green.

### W1-5 filtering (Sonnet, M), moved from wave 3
Files: new `app/src/kit/filters.tsx`, `filters.css`, `viewState.ts`, `highlight.tsx`,
`filters.specimens.tsx`. `app/src/kit/match.ts` already exists (`matchQuery`, `filterByQuery`,
`useQueryFilter` in `useSearch.ts`, built in `kit-data`) and stays the one matcher. New
`app/src/kit/match.cases.json` beside it (also read by `search-server`). New
`app/tests/filters.spec.ts` and `match.spec.ts`. From `kit-frame` after it merges:
`app/src/kit/index.tsx` (additive re-exports) and `app/src/Gallery.tsx` (mounts the
specimens). New decisions: `D270.md` (amends the native dropdowns of D213 and
D220, and the toggles of D132 and D209), `D285.md` (the owner ruled filter
memory in the URL).
Findings (7): see `CONSOLIDATED.md`, `lane: "filtering"`.
Work: build `FilterBar` from Capture's picker, which the owner called "pretty decent". Its
closed row always shows its own value. Each
option shows a count under the other active filters, and a zero count still shows. Single and
multi choice look different. Each row carries a clear, and one clear resets all. No order lock,
and no wipe. It opens a popover on the desk and a sheet on the phone. Its value lives in the
URL. `HideToggle` is one quiet control with a count. A table-header sort marks its active
column. `FilterBar` draws "N of M" by construction. Add the match highlight. `match.ts` folds
case, accents and punctuation. It reads words in any order, and numbers with or without leading
zeros.
Decisions: D213, D220, D209, D217, D142, D132, D118, D173.
Depends on: `kit-data`, `kit-frame`.
Done: `filters.spec` passes at four widths, both themes. Counts change with each other filter.
No option is disabled by order. A filter survives reload and Back. "N of M" shows under each
narrowing. On a phone the sheet opens and no row moves under the hand. `match.spec` passes
every row of `match.cases.json` (`54/132` finds `054/132`, words match in any order). Gallery
specimens render. `make check` is green.

### W1-6 locating (Sonnet, L), moved from wave 3
Files: `app/src/position.ts`, `app/src/cardNumber.ts`, `app/src/PositionBar.tsx`/`.css`,
`app/src/PlaceNeighbors.tsx`/`.css`, `app/src/PositionLabel.tsx`/`.css`,
`app/src/SectionTitle.tsx`, `app/src/CardLocations.tsx`/`.css`. Place parts only from
`app/src/BoxBrowse.tsx`/`.css` (the row number, the section header badge, the `?box=&card=`
deep link, today reading `?box=` only — the direction, "The box named on the hash", is
this lane's own) and `app/src/ReviewQueue.tsx`/`.css` (the place pill). New
`app/tests/locating.spec.ts`. The landed decision entry D260
(amends the display half of D58 and D92). In wave 2, `BoxBrowse` and `CardLocations` pass to
`inventory`, and `ReviewQueue` to `review`.
Findings (14): see `CONSOLIDATED.md`, `lane: "locating"`.
Work: the owner's orientation. Card 1 sits at the far back, and the highest number sits
nearest the owner. Every position drawing shows that orientation. The section ruler redesign
marks the exact card, uses section numbers throughout, and shows the sections before and
after.
By the box-names ruling (Opus), this lane also owns the server's place-label composition: the
box name, the section, and the card within the section. It carries no typed separator.
It also owns `departed_label`, the stored default box name "Box `<count+1>`" on create (the
next free name if that one is taken), and the backfill "Box N" for existing unnamed boxes.
It also owns `PositionLabel`'s box-number removal beside the name (for example
"BOX RB Epics Box 3"), and the change to `fulfillment.spec.ts`'s "dots and all"
assertion. Cite `D259`.
The lane also finds a box by name only in search. No number shortcut. An unnamed box is
backfilled "Box N", so "box 3" still matches by its name.
Decisions: D58, D92, D155, D30, D116, D41, D45, D67, D68, D183, D5.
Depends on: `kit-data` (`BoxLabel`, `Location`).
Done: `locating.spec` passes at 1440, 820, 720 and 390, both themes. Each instrument uses one
count. The ruler marks the exact card. "Back" labels card 1. Neighbours draw back to front. A
departed card speaks in the past tense. `#/inventory?box=N&card=<cid>` opens that card, and
Review's pill opens it too. A screen reader reads the pill as "Box 1, Section 3, Card 13".
Section names read whole at 1440, each header shows one count. `fulfillment.spec.ts` still
passes. `make check` is green.

## Wave 2: screens
Every wave-2 lane migrates its screen onto `Page` and the primitives, removes its files from
both allow lists, and deletes its screen's dead `--bn-page-max`. It depends on `kit-frame`,
`kit-data` and `shell`. It uses `ProductLink`, `Money`, `CardLine`, `BoxLabel`, `Notice`,
`Loading`. It also uses `filtering`'s `FilterBar`, `HideToggle`, `FilterCount` and `viewState`
wherever it filters, and its `match.ts`. It uses `locating`'s place vocabulary wherever it draws
a place. A wave-2 lane is done when `make check` is green, and its files are gone from both
allow lists. It is also done when the `scaffold`/`text-shape`/`machine-words` specs pass for
its route at four widths, and 720 looks designed.

### W2-1 home (Sonnet, M)
Files: `Home.tsx`/`.css`, `standing.ts`, `tests/home.spec.ts`, and a new decision entry
for the owed-line rule (amends D121).
Findings (13, widened for UX-077 in round two, now S2). The owed-line button stays as it is
(D121 ruling). "Behind that" lines that repeat a figure are cut. The Capture tile relabels to
"newest box". Box rows list most recent first.

### W2-2 capture (Sonnet, L)
Files: `CaptureScreen.tsx`/`.css`, `SubmissionClaims.tsx`/`.css`, `setHint.ts`,
`deviceMemory.ts` (additive), the capture-claims and capture-undo specs, new
a new decision entry for the always-ask box rule (amends D142).
Findings (19, widened for UX-052 in round two, now S2). A fresh device always asks for its box.
The box picker lists most recent first.

### W2-3 sales (Sonnet, L)
Files: `Revenue.tsx`/`.css`, `tests/revenue.spec.ts`, and a new decision entry for one
row per SKU (amends D214, D217).
Findings (16, plus UX-219 and UX-262 new in round two). One row per printing (SKU), so
printings stay separately identifiable. Rows lead with the name, top N rows plus "Show all",
"On the shelf" moves above the table. Refund notes show only above zero. `ProductLink` on
names. The owner's words: "it's just an excel sheet" and "literally just an excel sheet, not
sexy". A visual direction is shown to the owner before this lane builds the layout. The
layout waits for that answer.

### W2-4 shipping (Sonnet, M)
Files: `OrdersShipStage.tsx`, `Shipping.css`, `tests/shipping.spec.ts`, new
a new decision entry for the phone lane collapse (amends D61).
Findings (10, plus UX-218 new in round two). The lane order stays. Every lane collapses on a
phone. The rule prints once, in the lane header. No reason codes on screen.

### W2-5 library (Sonnet, S)
Files: `Graveyard.tsx`/`.css`, `Codes.tsx`/`.css`.
Findings (4). Codes' local `Sheet` is replaced by the kit `Sheet`.

### W2-6 inventory (Opus, L), replaces the held group
Files: `app/src/Inventory.tsx`/`.css`, `app/src/BoxBrowse.tsx`/`.css` and
`app/src/CardLocations.tsx`/`.css` (from `locating`), `app/src/BoxOps.tsx`/`.css`,
`app/src/CardHero.tsx`/`.css`, `app/src/InventoryOverlay.tsx`/`.css`, `app/src/cardState.ts`,
`app/src/frozenRank.ts`, new `+app/src/retireReasons.ts`. Tests: `inventory.spec.ts`,
`correct-answer.spec.ts`, `card-variants.spec.ts`. Three new decision entries. One is for
nothing jumping on a sale, and amends the timing of D132. One is for the inventory walk-first
rail order, and amends D40. One is for retire's own way back.
Findings (31): see `CONSOLIDATED.md`, `lane: "inventory"`. Adopts 40 further ids owned by other
lanes.
Rulings applied: nothing jumps on a sale. A sold row stays, marked sold, until the next box
load. Box lists are most recent first. The rail order changes on the next visit, never under
the pointer. Filters work in any order. 720 gets the desktop rail. Codes go behind a
disclosure.
Decisions: D40, D132, D118, D181, D58, D83, D26, D57, D119, D213, D115, D196, D117, D252, D101.
Depends on: `locating` (hands over `BoxBrowse` and `CardLocations`), `filtering`, `kit-data`,
`kit-frame`, `shell` (the 720 rail). `search-server` supplies its counts in the same wave. The
lane builds against the current count read, and switches when the new one lands.
Done: `inventory.spec` passes at four widths, both themes. Set and Rarity work before Game, and
nothing wipes them. After Mark sold, the next click moves nothing, and the row folds on
reload. The rail never changes order under the pointer. At 1440x900 the walk list is the
tallest item in its column. At 720 the list sits beside the card. The machine-words spec finds
no code, path or pipeline noun. Retire carries a confirm step or a working undo. Each write
shows a receipt in view. `make check` is green.

### W2-7 orders (Opus, L), replaces the held group
Files: `app/src/Orders.tsx`/`.css`, `app/src/OrdersWalkPane.tsx`/`.css`,
`app/src/OrdersHubStore.ts`, `app/src/orderView.ts`, `app/src/orderBuyers.ts`,
`app/src/orderReasons.ts`, `app/src/orderPaste.ts`. Tests: `orders.spec.ts`,
`order-walk.spec.ts`. New decision entries: one for the sort press (amends D209), and one
for the orders walk layout (amends the layout half of D220). The lane stops using `.browse-*`
classes from `BoxBrowse.css` and styles its own walk in its own files.
Findings (35): see `CONSOLIDATED.md`, `lane: "orders"`. Adopts 20 further ids owned by other
lanes.
**The orders-safety item is this lane's first commit, alone.** UX-165 (S1): a store-wide
"Stand down N orders" press offers to close live Ready-to-ship orders, with no cutoff shown.
The owner ruled "S1s: fold into the plan, no separate hotfix lane". The fix is client-only —
the server already takes `cutoff` and `preview` in `_reconcile_cutoff`. The code sits in
`ReconcileBacklogPanel` inside `Orders.tsx`, which this lane owns, so a second lane on that
file would break the one-owner rule. Opus is already the tier here. The commit draws the
cutoff and the oldest and newest order it closes. The owner can move the cutoff. It names each
order TCGplayer still calls Ready to ship. The press sends the drawn cutoff. It lands before
every other orders item. The owner was warned, and the risk stays live until this commit
merges.
Rulings applied: a sort press re-sorts at once, and a sale still never re-ranks. D212, "pick 2
of X" and where every copy is. The buyer-list and filter-bar gripes. The buyer-count bug in
the header. 720 gets the desktop rail. Codes go behind a disclosure. HOR-07 waits for the
owner's one test on the real store.
Decisions: D220, D209, D181, D193, D203, D212, D113, D57, D69, D152, D117, D196.
Depends on: `kit-frame`, `kit-data`, `shell`, `filtering`, `locating` (`SectionTitle`). Some
items wait for the owner's word on the layout half of D220 and on the hub shape. The rest of
the orders work does not wait.
Done: the orders spec seeds a store with 6 open buyers and 30 done buyers. The lede counts one
set (for example "21 copies owed to 6 buyers"). Owed minus short equals the cards in the walk. A sort press re-orders at once. At
1440x900 the walk shows 8 rows or more, and reads "pick 1 of 2". Undo shows only where it
works. The stand-down panel names its cutoff, and the request body carries it. No row stacks
more than one status. At 720 the list and the walk both sit on the page. No code or path
appears in rendered text. `make check` is green.

### W2-8 review (Opus, M), replaces the held group, after inventory merges
Files: `app/src/ReviewQueue.tsx`/`.css` (from `locating`), `app/src/reasons.ts`, test
`review.spec.ts`. A new decision entry for the narrow review layout (amends the photo reserve of D28
below the rail breakpoint).
Findings (8): see `CONSOLIDATED.md`, `lane: "review"`. Adopts 20 further ids owned by other
lanes.
Why after `inventory`: it imports `retireReasons.ts`, and adopts the correction names, the
codes fix and the dialog cuts that `inventory` owns.
Rulings applied: codes go behind a disclosure. 720 gets the desktop rail. The Close dialog's
codes wait for the owner.
Decisions: D28, D37, D164, D118, D171, D196, D41.
Depends on: `inventory`, `locating`, `kit-frame` (the HIR-04 receipt pattern).
Done: `review.spec` passes at four widths. At 720 and 390 the first answer row and the receipt
sit in the first viewport. An answer moves no row of the next card. Each answer carries a
receipt and shows in the session list. One verb names the close. No code shows in text or in a
tooltip. `make check` is green.

### W2-9 search-server (Sonnet, M)
Files: in `server/capture_server.py`, only the search and facet reads (`do_search`,
`_fts_query`, `_match_rank`, and the facet matches in `_box_row`). New `+server/match.py` and
`+scripts/match-selftest.py`. `app/src/useSearch.ts`, handed off from `kit-data`. For wave 2
only: `Makefile`, `scripts/checks.py` and `CLAUDE.md` (one `check` target and its census
line).
Findings (3): see `CONSOLIDATED.md`, `lane: "search-server"`.
Work: the Python matcher passes every row of `app/src/kit/match.cases.json`, which `filtering`
writes. It widens the FTS query so zero padding, hyphens and accents reach the rank step. It
takes facet counts from the same filtered set the walk shows. It measures the 200ms debounce on
a seeded store of the owner's size before the lane keeps or changes it.
Decisions: D166, D213, D132, and item 8 of `docs/specs/store-scaling.md`.
Depends on: `filtering` (the case table). Work runs only on this checkout's own port. The lane
never restarts or touches the owner's server.
Done: `+make match-selftest` goes red on the current `_match_rank` for "54/132", and green
after the fix. It runs in `make check`. `make serve-selftest` is green. The check-census row of
`make docs-audit` is green.

## Wave 3
- `docs-sweep`: `CLAUDE.md`, `README.md`, `DESIGN.md`. It adds the section-relative card
  number and card 1 at the back to "Things you will get wrong" in `CLAUDE.md`. If the owner
  puts FLT-11 in the URL, it also updates the storage-key roster.

## Released (was blocked, now unblocked by the flow and pricing rulings — RULINGS.md)
- `b-runs`: UX-006, 007, 010, 017, 018, 020, 030, 031, 044, 054, 085, 097, 102, 103, 104, 114,
  120, 121, 122, 123, 124, 148, 151, 152, 153. It needs Pricing's write-bar region, so it runs
  in sequence with `b-pricing`, before it.
- `b-pricing`: UX-026, 035, 045, 053, 061, 070, 071, 075, 078, 083, 084, 105, 106, 107, 126,
  131, 135, 146, 160, plus UX-192, UX-212, UX-213 (new in round two).

## Handed off
- `token-sweep`: UX-157, a separate session after the UX PR merges.

## Sum
Every UX id sits in exactly one lane. Round one: 164 ids (119 in a lane, 44 released, 1 handed
off). Round two: 108 ids (105 in a lane, 3 released to `b-pricing`, 0 handed off). Total: 272
distinct ids, 224 in a lane, 47 released, 1 handed off.

## Owner gripes, mapped to lanes
- Inventory: filters go game, then set, then rarity, in that fixed order. They must work in
  any order and combine. Findings: UX-176 (`inventory`), UX-210 (`search-server`), UX-180
  (`filtering`).
- Orders buyer list reads badly (the tick/untick header, the owed bars, the step-through
  hint). Findings: UX-199, UX-232, UX-231, UX-201 (`orders`).
- Orders filter bar: controls of different widths, Status opens the native macOS select, and
  the labels run heavy. Findings: UX-217 (`orders`), UX-180 (`filtering`).
- Orders' header count reads "611 lines across 806 buyers" (fewer lines than buyers).
  Finding: UX-167 (`orders`).
- Capture's filter and selection UI reads well. It is the pattern for the shared filter
  control. Finding: UX-180 (`filtering`).
- Sales reads like a spreadsheet, and needs a visual redesign. Findings: UX-111, UX-113,
  UX-034, UX-219 (`sales`).
- Locating: the "Identified" icon repeats everywhere. Finding: UX-221 (`inventory`).
- Locating: which end holds card 1, and what "before" and "after" mean. Findings: UX-185,
  UX-186, UX-184 (`locating`).

## Not in any lane
- The box-map wish (drag sections between boxes) needs a spec and a decision before any build
  (RULINGS.md, "Box map"). It is not a finding.
- The round-one held note on the shell's Cmd-arrow ring was not checked again in round two.
  The shell lane checks it.

## Orchestrator notes carried from the reviews
- The shell lane joins the palette, keys sheet and drawer to `kit-frame`'s `useOverlayLayer`.
  It checks `overlayOpen()` before the `,`-plus-letter chord and the Cmd-arrow route step, so
  no global key acts under an open layer. It adds `ReloadButton`'s R key to `SHORTCUTS`. It
  swaps `ROUTES` icons per `ICON_MEANINGS`. It wraps the palette footer's keyboard sentence in
  `KeyHint`. It fixes the rail keycaps' and top-bar wordmark's contrast. The tab title reads
  "番地 `<screen in lowercase>`". `kit-data`'s `SearchField`/`Select` field edge needs a 3:1
  follow-up.
- A small `kit-frame-2` lane (Sonnet), after `kit-frame`'s pass: drop `kit-frame`'s stopgap
  thumb-floor rules for `kit-data` classes (`kit-data` owns them now). Fix the danger pill on a
  selected row in dark. It reads 4.08:1 on surface and 4.48:1 on background, so
  `--bn-pill-ink-danger` darkens in dark mode. Add a touch pass to `gallery.spec.ts`'s
  status-slot test.
  Clamp `layerZ` at depth 2, or assert that no screen opens three overlay layers at once.
  Exclude `tabindex="-1"` buttons from the focus-trap selector's stop count. Move the overlay
  and toast-offset breakpoint to 640, to match the 720 desktop-rail ruling.
- `filtering` does not write a separate matcher decision: `D271`
  already covers it. It writes `D285.md`.
- `locating` does not write separate ruler, card-order or section-count decisions:
  `D260` already covers all three.
- `text-checks` starts after `guards` merges — both own `Makefile`, `CLAUDE.md` and
  `checks.py` in their own waves.
- `DESIGN.md` and `docs/map.py` still call 768 the rail edge in places: `text-checks` or
  `docs-sweep` fixes them.
- The demo lane's own round two: load the demo's shipping export at app start (the shipping
  lane owns the file). Update the `select[aria-label="Filter by game"]` line in
  `demo-coverage.spec.ts` once `FilterBar` replaces the native select. Demo product strings
  still show box numbers ("Box 1 (RB Origins)", "B4 #10", "BOX 1", the sale toast), so the
  demo seed names every box. `demo.yml` should run `demo-coverage.spec.ts` after it builds.
  `demo-preview`'s port needs a variable, and a `demo-record-selftest` target.

## Carried to wave 2 (2026-09-24)
- `orders`: `Orders.tsx:fetchMissingPicks` loops forever when a picks answer omits a key. Stop
  asking for a key once an answer comes back. Also clean the stale copy-budget comments in
  `Orders.tsx` and `orders.spec.ts`.
- `inventory` (or its own small lane): Cards to pull's box header still shows a number tile and
  "Box `{n}`". It should show the name only.
- `inventory`: `BoxOps.tsx`'s rename hint still calls the box number the identifier. `#/orders`
  still prints the machine word "staged". The pending text-check entries stay open too.
- `sales`: a 28-word sentence, and `$3.31` set in the wrong face, both on `#/revenue`. Also the
  stale copy-budget comment in `Revenue.tsx`.
- `shipping`: four dollar figures on `#/shipping` are not set in the mono face.
- `product`: a 26-word sentence on `#/product`.
- `library`: the machine word "index" on `#/codes`.
- `docs-sweep`: `PlaceNeighbors`' map prose, and `CLAUDE.md`'s D68 departed-label text. Also
  the shipping and phone specs' stale copy-budget comments, `demo.yml`'s stale comment, the
  demo-coverage spec's name, and one `#/pricing` run-history case.
- `b-runs` moved the store to schema 11. Any other lane that bumps the schema takes 12.
- `inventory`: adopt `FilterBar`'s layout in the rail. Add a popover mode for a narrow desk
  bar. Read server counts under the other active filters, with a value for the unclassified
  bucket.
- `b-pricing`: when a kit picker opens inside the hold panel or the runs picker, put those
  containers on the overlay stack too.

## Offender-list mechanism (2026-09-24)
- The token-literal guard's (D256) conversion belongs to the "Run round two" session, inside
  its own sweep. This lane plan does not build it.
- Three separate "only shrinks against the merge-base" helpers exist today:
  `scripts/kit-adoption.mjs:growth()`, the ratchets lane's list helpers in
  `scripts/docs-audit.py`, and the text-checks specs' allow-list readers. The ratchets lane's
  round 2 (the line-anchor conversion) consolidates these into one shared helper per language,
  and moves the existing lists onto it. It tells the "Run round two" session the symbol names
  once the UX PR merges.
- `review` (wave 2): three refusals still print the raw store key or index:
  `_require_group_answers`' `duplicate_position` ("answers[1] repeats 7/1"),
  `do_review_group_answer`'s `group_entry_refused` aggregate ("7/1: not_in_queue — …"),
  and `do_put_box_claims`'s `card_not_found` ("holds no card at 3, 7"). They move to
  `said_place`/`place_within_box`, with the matching test lines updated.

## Iconography map
Every screen lane builds the rows of its own table in `review/ICON-MAP.md` §1. It applies the
rule in §2 to any press the table does not name. The kit-icons lane builds `IconButton` and the
new icons. It also builds the kit's own rows, the `icon-only-button` check, and
`+docs/specs/iconography.md`. The owner accepted two named risks. Orders' Mark sold converts to
an icon now. Sort direction becomes an arrow icon, while the sort key stays in words.

## Presses that change their label while busy (D118)
Each fix keeps the label, shows the kit `busy` spinner, and puts the status text in a
screen-reader-only line. Each gets a red-first spec case that measures the press box before and
during a press held open by a delayed stub.
- `b-pricing`: `LiveReconcile.tsx`'s "Fetch my live listings" press, `Markdown.tsx`'s fetch
  press, `Pricing.tsx`'s Live-tab "Download the file instead" door, `SendCard.tsx`'s
  "Write the file(s)" press.
- `sales`: `Revenue.tsx`'s "Value my stock"/"Refresh" and "Compare to today's market".
- `review`: the status lines in `RunRescue.tsx` and `ReviewQueue.tsx` that appear only while a
  press runs. Each reserves its own space.
- Not yet assigned: a kit-level guard, either `Button`'s `busy` state holding its own
  footprint, or a lint rule that refuses a label ternary on the busy state.

## Review lane fence
The owner ruled on Review's catalog search. The owner's words: "the search shouldn't cut
off i should see all rows that matched unless it's an egregious amount no? or a 'show 10
more' etc." That search belongs whole to the identity session's own lane: ranking by
capture claims, every match shown, and "Show 10 more". The `review` lane fences
`ReviewQueue.tsx`'s `CatalogPanel` results list. It never redraws the rows or their count,
and never adds a cutoff of its own. A `kit-frame` change there touches only the wrapper.

## Tighten headers and filters (owner, 2026-09-24), every screen
- A filter bar holds one line: search, plus one Filters button with a count badge. Facets and
  sort move into the popover (`FilterBar compact="popover"`, the kit's new default).
- A page header holds at most one worded primary action. The rest read as `IconButton`s or sit
  behind a More menu.
- Orders goes first, as the proof. Then inventory, capture, sales, shipping, library, review
  and pricing apply the rule in their own lanes.
- The kit lane flips `FilterBar`'s default, so every screen already on `FilterBar` goes
  one-line at once. Its new check lists every current offender (a hand-built filter row, or too
  many header actions) in `kit-adoption-allow.json`, keyed to the lane that owns the screen.
  `#/product` goes to the `b-pricing` lane. The Fulfiller is exempt. A wave-2 lane is done only
  when its own entries leave every offender list. Each lane's own done check says so.
- The kit-tighten lane's own input: Orders forces `FilterBar`'s compact mode in `Orders.css`
  today, a stopgap. The kit lane makes one-line-plus-popover the `FilterBar` default, and
  deletes that override.
  Measured on Orders: the filter bar shrinks from 70px to 34px at 1440, and from 190px to
  42px at 720. It shrinks from 140px to 42px at 390.
- Orders, once kit-icons merges: "Add orders" and "Cards to pull" become small square
  `IconButton`s on the same line as the one-line filter bar. This is recorded as planned in
  `D274`.
- `search-server`, which owns `server/`: `reconcile-backlog` must refuse a cutoff after today,
  from the Orders review. The screen already disables that press. The server is the second
  guard.
