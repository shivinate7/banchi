# Lane D — kit-adoption allow-list, five items for the owner to see and rule on

Scope: `scripts/kit-adoption-allow.json`'s five listed exceptions (D275). Plus one unlisted
gap the owner flagged on Capture (F4). No product code changed.

Every screenshot below came from this worktree's own seeded store, on its own port
(`make worktree-setup`). Temporary CSS edits used to produce an "after" image were made with
a `.bak` copy, then swapped back. Nothing here was committed. No `git checkout` or `stash`
was used.

Images are `docs/reviews/ux-2026-09-23/lane-d/<name>.png`, referenced below by filename only.

---

## 1. Home's own top gap (`runtime "/" top`)

**The exception.** Every other screen's h1 sits exactly `--bn-page-top` below the page's top
edge. That is 24px on desktop, 16px on phone. Home's h1 ("Good evening.") sits further down.
`Home.css` reorders its `lede` (the weekday date) to draw ABOVE the h1, with
`.home .bn-lede { order: -1; ... }`. The DOM order is unchanged. Only the visual order moves.
D121 and D287 both rule that Home keeps its own shape. Its hero is not to be redesigned.

**Before / after.**
- 1440 light: `home-1440-light-before.png` / `home-1440-light-after.png`
- 390 light: `home-390-light-before.png` / `home-390-light-after.png`
- 1440 dark: `home-1440-dark-before.png` / `home-1440-dark-after.png`
- 390 dark: `home-390-dark-before.png` / `home-390-dark-after.png`

The "after" removes only the `order: -1`, one line in `Home.css`. That line is the entire
mechanism. Nothing else about Home moved.

**What changes for the user.** The date line moves from above the greeting to below it. This
is the kit's own order: eyebrow, then heading. The huge greeting now sits flush at the very
top. The small date sits crowded underneath it. The "after" image reads worse. The date reads
like an afterthought under a headline, instead of announcing it. This is why the exception
exists. D121 built the eyebrow-above-heading order on purpose. The intent was a masthead:
date, then greeting, not a heading with a small caption.

**Cost.** One CSS line. **Risk.** None to any other screen. The change is `.home`-scoped.
**Test.** `app/tests/scaffold.spec.ts`'s `top` assertion for `/` would go green. The allow
entry would then be stale, and the test already refuses a stale entry.

**Recommendation.** Keep the exception. This is D121's placement working as designed. It is
not an accident. Closing it makes the screen worse, not more consistent.

---

## 2. Review's and Runs' own top gap (`runtime "/review"` and `"/runs"` `top`)

**The exception.** `ReviewQueue.css` sets `.review.bn-page { padding-top: var(--bn-4); }`,
16px, instead of the kit's `--bn-page-top` (24px desktop). The file's own comment names the
reason: D32, "the pixel budget is spent on the card, not the desk." The page's whole chrome
was measured and cut to 172px (`--rv-chrome`). This lets the card photograph clear
`review.spec.ts`'s floor of 23% of the screen at 1440x900. Page padding-top gave up 8 of the
86 cut pixels. `/runs` carries the same entry for one reason: `#/runs` renders Review
underneath its "Runs" sheet (D291). It is not a second gap. It is the same one, reached by a
second route.

**Before / after.**
- 1440 light: `review-1440-light-before.png` / `review-1440-light-after.png`
- 390 light: `review-390-light-before.png` / `review-390-light-after.png`
- 1440 dark: `review-1440-dark-before.png` / `review-1440-dark-after.png`
- 390 dark: `review-390-dark-before.png` / `review-390-dark-after.png`
- Runs, same underlying page, sheet open, 1440/390, light/dark:
  `runs-1440-light-before.png` / `runs-1440-light-after.png`, and the -390-, -dark- variants.

**What changes for the user, on `/review`.** The header sits 8px lower. The card photograph
gets 8px shorter. Both are barely visible at this scale, but real. The "after" edit changed
only the padding-top. It did not re-tune `--rv-chrome`'s 172px budget. Those 8px are simply
lost, not reclaimed elsewhere. A real fix needs the whole 86px budget re-measured, not just
this one line. That budget is the same kind of hand-measured, multi-line arithmetic as item 5
below.

**What changes for the user, on `/runs`.** Nothing visible. The "Runs" sheet is opaque. It
covers the page's own header completely. Compare `runs-1440-light-before.png` and
`runs-1440-light-after.png`: they are pixel-identical. The `/runs` entry is real. The
underlying page fails the same assertion `/review` does. But a fix there has zero visible
effect, because nobody ever sees Review's header while the Runs sheet is open.

**Cost.** Closing `/review`'s entry costs re-deriving the D32 budget to reclaim the 8px. That
budget is 5 numbers, in one file, already documented. The alternative is accepting a
3.7%-relative-smaller photograph. Closing `/runs` costs nothing extra once `/review` is
fixed. It is the same page. **Risk.** `review.spec.ts`'s photograph-size floor could go red,
if the budget is not re-measured in the same change. **Test.**
`app/tests/scaffold.spec.ts`'s `top` assertion for both routes. Also
`app/tests/review.spec.ts`'s photograph-size floor, as a guard against the opposite
regression.

**Recommendation.** Leave both. `/review`'s gap is a deliberate, measured, cited trade for
the card photograph (D32). It is not an oversight. `/runs`'s entry is real but invisible to a
user. Closing it buys nothing anyone would see. It only removes a stale-sounding list entry.
Weigh that against the real, if small, risk to the photograph floor.

---

## 3. `app/src/ReviewQueue.tsx` — five R2 findings

Each hand-rolled a primitive the kit already owns.

### R2-dialog — the "Close without answering" panel
`reviewqueue-r2-dialog.png`. A hand-rolled `<div role="dialog">` (`ClosePanel`, opened by the
`X` key). Not the kit's `Sheet`, `Modal` or `Popover`. Moving it onto the kit's `Modal` would
change two things. Focus trap and Escape handling would come from the kit, instead of this
file's own `trapTab` and `useOverlayFocus` glue. The surface, radius and motion would match
every other dialog in the app, instead of this screen's own `.review-close` styling.
**Cost estimate:** about 40-60 lines. Delete the hand-rolled trap and focus code, then wrap
the existing content in `<Modal>`. **Test:** `make kit-adoption` (R2-dialog). No runtime
scaffold test covers dialogs today.

### R2-search — the catalog lookup's search box
`reviewqueue-r2-search.png`. A raw `<input type="search">`, with its own label and icon
markup. Not the kit's `SearchField`. Moving it over would add three things for free: the
clear button, the forgiving-match wiring (D271), and the shared focus ring. Today this box
has none of them. `SearchField` already gives every other search box in the app a clear
button and a `/` shortcut hint — compare Codes' own search field in
`codes-r2-filter-row.png`. **Cost estimate:** about 15-25 lines. **Test:** `make kit-adoption`
(R2-search).

### R2-class — hand-rolled `bn-skeleton` loading bars
`reviewqueue-r2-class.png`, caught mid-fetch under a throttled network, in the "Re-check
every waiting card" sheet. Three raw `<span className="bn-skeleton ...">` bars, instead of
the kit's `Loading` component (`app/src/kit/Page.tsx`). In this screenshot the individual
bars are barely visible against their own container. Both share `var(--bn-surface-2)`.
`Loading`'s own tuned skeleton shapes do not have that problem elsewhere in the kit. Moving
to `Loading` would fix this too. **Cost estimate:** about 10 lines. **Test:**
`make kit-adoption` (R2-class).

### R2-date — the queue's own date format
Not separately screenshotted. It renders as plain text, such as "Aug 24", inside rows already
shown above. `sinceText()` in `ReviewQueue.tsx` calls `toLocaleDateString` directly, instead
of using `app/src/dates.ts`'s shared formatter. Moving it over is a plain find-and-replace of
the formatting call. The rendered text does not change today. Only its source does.
**Cost estimate:** about 3 lines. **Test:** `make kit-adoption` (R2-date).

### R2-money — the queue's own price format
Also visible in the background of `reviewqueue-r2-dialog.png` and `reviewqueue-r2-search.png`
(the "$1.32" rows). `priceText()` builds a string like `$0.48` by hand, instead of using the
kit's `Money` component or `money()` from `app/src/money.ts`. D221 requires every dollar
figure to render in the mono face. `app/tests/money-face.spec.ts` checks the rendered face,
not the source. So this file gets that right today only because its own CSS happens to apply
the mono face to its price classes. Moving to `Money` or `money()` would make that a property
of the primitive, not something this file must remember. **Cost estimate:** about 10-15
lines. **Test:** `make kit-adoption` (R2-money) and `app/tests/money-face.spec.ts`, already a
gating regression guard.

**Recommendation.** All five are real, small, and independently landable. None touches the
review scoring or field logic. Only the markup changes. R2-class and R2-date are the
cheapest and lowest-risk. R2-dialog is the largest single one, because of the focus-trap code
it deletes.

---

## 4. `app/src/Codes.tsx` — `R2-filter-row`

`codes-r2-filter-row.png`. Codes is a DORMANT feature, per CLAUDE.md. The ledger rows shown
were seeded with obviously-fake test codes, such as `TEST-0000-0000-0000`. They were written
only into this worktree's own gitignored store, for this screenshot. Nothing here was
committed.

**The exception.** The screen builds its own filter row by hand. A `SearchField`, "Find a
code...", sits in `.codes-ledger-head`. A separate `.codes-toolbar` of hand-rolled
`<button className="codes-chip">` state and lane facets sits right below it. Neither is
assembled through the kit's `FilterBar` (`app/src/kit/filters.tsx`), which exists to be
exactly this: a search field plus facet chips, as one unit. **What changes visually:**
little. `FilterBar`'s own chip styling is already close to `.codes-chip`'s. What changes is
behavior. D270 rules "one filter bar, everywhere a list is filtered." Every other filtered
list gets that primitive's keyboard navigation between chips for free, and its own tuned
responsive collapse. This file hand-rolls both today, in its own CSS.

**Cost estimate:** about 40-60 lines. The two chip groups and their counts map onto
`FilterBar`'s facet-group shape. The `IconButton` "reveal codes" toggle at the row's end
stays outside it. **Risk.** Low. This route is dormant. A regression here would be caught
only by a session that deliberately opens `#/codes`, not by daily use. **Test.**
`make kit-adoption` (R2-filter-row). No runtime scaffold test covers filter rows today. This
would rely on the static check alone, plus a manual look.

**Recommendation.** This is the one item where "the feature is dormant" argues for the fix,
not against it. Nobody uses this screen today. The risk of finding a real regression window
is close to zero. The fix is small, mechanical and self-contained. It is cheap to land while
nobody depends on the screen's current behavior.

---

## 5. Capture's own gap below the subheading (owner feedback F4)

This gap is not on any allow list, and not recorded anywhere before now. Confirmed by reading
`scripts/kit-adoption-allow.json` and `app/tests/scaffold.spec.ts`: `/capture` carries no
`top` entry. Scaffold.spec.ts's `top` assertion, the h1's own distance from the page's top
edge, already passes for it. An earlier lane closed that exact exception.

The gap the owner is seeing is a different measurement. It is the space AFTER the header,
between the bottom of the title-and-odometer block and the first content below it. That is
the camera stage, on both desktop and phone. No test asserts this space today.

**The cause, measured, not guessed.** `.capture.bn-page` is `display: flex; flex-direction:
column; gap: var(--cap-gap)`, where `--cap-gap` is `--bn-3`, 12px. Its only two direct
children are the kit's own `<header class="bn-page-head">` and `<div class="bn-page-body">`.
The kit already puts `margin-bottom: var(--bn-4)`, 16px on desktop, on that header. Capture's
own narrow-container override drops this to `var(--bn-2)`, 8px. Because the flex `gap` and
the header's own `margin-bottom` both fire between the same two elements, the two stack.

- Desktop, 1440px: 16px margin plus 12px gap equals 28px measured. Every other screen shows
  16-24px, from the `--bn-page-top` family alone.
- Phone, 390px: a second copy of the same `gap: var(--bn-3)` is set again, inside Capture's
  own `@media (max-width: 767px)` block. The stacking survives there too: 8px margin plus
  12px gap equals 20px measured.

This is not a one-line accident. The file's own comments already budget for the extra space.
`--cap-chrome`'s calc adds `--cap-gap` and `--bn-4` as two separate terms. The phone stage's
hand-measured 298px and 366px height constants do the same. Whoever wrote this knew both
numbers were live, and planned around their sum, rather than removing the redundancy.

**Before / after.** Temporary CSS only, `.bak` swap, never committed. The page-level `gap`
was removed from `.capture.bn-page`'s base rule, and from its own copy inside the
`@media (max-width: 767px)` block. `--cap-chrome` and the phone stage's height constants were
deliberately left untouched. So the "after" images are the safe direction: the stage gets a
few idle pixels of extra room under it, never less.

- 1440 light: `capture-1440-light-before.png` / `capture-1440-light-after.png`, 28px to 16px
- 390 light: `capture-390-light-before.png` / `capture-390-light-after.png`, 20px to 8px
- 1440 dark: `capture-1440-dark-before.png` / `capture-1440-dark-after.png`
- 390 dark: `capture-390-dark-before.png` / `capture-390-dark-after.png`

No clipping or overlap appeared in any of the four renders. Removing the gap only ever
shrinks the reserved space. The two now-unused budget terms already over-estimate, on the
safe side.

**What changes for the user.** The header sits visibly closer to the camera stage, and to the
setup panel beside it. That is about 12px tighter, on both desktop and phone. This matches
the spacing every other screen uses, between its own header and its own first block.

**Cost.** Two CSS lines, to delete the redundant `gap`. A real fix also touches the numbers
that were budgeted around the redundancy. `--cap-chrome`'s calc loses one term.
`.capture-stage`'s phone-only height comment and constant need a fresh measurement. Both are
already named, measured and cited in the file. This is a re-derivation of existing
arithmetic, not new measurement. Estimated at about 10-15 lines, including comment updates.

**Risk.** Low on desktop. That `--cap-chrome` term only sizes the desktop viewfinder's own
height. Leaving it stale means that the desktop camera stays fractionally shorter than it
could be. It never overflows. The phone stage uses hard pixel constants, 298px and 366px,
rather than a calc. Those need a real re-measurement, not just a deleted token, to close the
gap on phone without leaving a stale comment.

**Test.** No existing test asserts this gap. It is a genuine coverage hole:
`scaffold.spec.ts`'s `top` only checks the h1's own offset from the page. It never checks the
space after the header. Proving a fix needs one of two things.

The first option: a new assertion, in `scaffold.spec.ts` or a Capture-specific spec. It
checks that `.bn-page-body`'s top, minus `.bn-page-head`'s bottom, equals the header's own
`margin-bottom`, with no double count.

The second, smaller option: re-run `app/tests/phone.spec.ts`'s shutter case. That confirms
the phone stage still clears the tab bar, once the redundant gap is gone and the height
constant is re-measured.

**Recommendation.** Fix it. This is a real, measured, two-line redundancy, with no argued
reason behind it. Unlike items 1 and 2, nothing here cites a design decision for the double
gap. The comments show awareness of the sum, not an intent to keep it doubled. Land the CSS
fix together with the `--cap-chrome` and phone-stage re-measurement, in one pass. Add the
missing head-to-body gap assertion too, so this class of bug cannot reappear silently on any
screen.
