# Every judgement call made during the 2026-09-20 fixes

A defect fix needs no argument. A taste call does. This file records each one: who
decided, what they argued, what they rejected, what a reviewer said about it, and the
exact place to change it if the owner later wants it to go the other way.

Nothing here is settled. This is a record of reasoning, not a decision log, and going the
other way on any of it costs one edit at the place named.

**Each "Reverse at" names a file and a symbol rather than a line number.** A line number in
a document is wrong the moment anyone edits the file above it, and `main` now carries a
`line anchor ratchet` that holds a new document to none. A rule name or a function name is
found by grep and survives the edit.

## Layout and treatment

### Pricing's two panels merged into one surface

**Decided:** one bordered, shadowed surface with an internal hairline divider, replacing
two side-by-side `bn-panel` cards. Bottom edges now agree exactly (479.13px), where the
step had been 114px (407 vs 521).
**Argued:** the review named three options. Height-matching by stretching had already been
tried and rejected in the file's own comment. Leaving a 114px jagged step between two
bordered cards reads as broken. Merging removes the mismatch rather than papering over it.
**Rejected:** stretching either panel to match; leaving it alone.
**Watch:** a merged surface usually fails where two panels did not — when one side is
empty, or much taller than the other. That is what its reviewer was asked to test.
**Reverse at:** the `.pricing-cheap`/`.pricing-verdict` merged-surface block in
`app/src/Pricing.css`, and the `data-cards` class names in `app/src/Pricing.tsx`.

### The Fulfiller's action button given a solid fill

**Decided:** `.ff-step` ("Pull this card") moves from the quiet outline variant to a solid
`--bn-ink`/`--bn-bg` fill.
**Argued:** it is the largest element on the card panel and the one thing the screen exists
to make someone press. An outline button reads as secondary. The screen is used fast and
under pressure, where "looks optional" is a real cost. It also fixes a dark-theme artifact
where the 2px `--bn-ink` inset border drew as a bright thin rectangle.
**Rejected:** the accent fill — this file reserves `--ff-fill`/accent for the one press that
writes, per its own comment, so the solid ink register matches `.ff-start` instead.
**Reverse at:** `app/src/Fulfillment.css`, the `.ff-step` block.

### Home's hover timing pulled to match everything else

**Decided:** `.home-standing-row`, `.home-stage`, `.home-deck` ease at 120ms, were 200ms.
**Argued:** every button and nav link in the product eases at 120ms. Each timing is fine
alone; the mismatch shows when a tile and a button sit near each other.
**Reverse at:** the `--bn-t-fast` transitions on `.home-standing-row`, `.home-stage` and
`.home-deck` in `app/src/Home.css`.

## Numbers and formatting

### Sales verdict bolded

**Decided:** 400 → 700.
**Argued:** it is the largest text on the screen's most important line and was the only
headline in the product treated quietly. Matches `.bn-title`, `.bn-empty-title`,
`.bn-section-title`, `.codes-task-title`.
**Against:** the review flagged the light weight as *possibly deliberate* — a verdict is a
sentence, not a numeral, and treating it quietly may have been the intent.
**Reverse at:** the verdict rule in `app/src/Revenue.css`.

### Per-product Gross comma-grouped

**Decided:** grouped, crossing the file's own comment saying a comma would be the only one
in a column of otherwise-plain figures.
**Argued:** that premise is already false on this store's real data (`$4,411.80`), and the
Copies column beside it was already inconsistent about whether large numbers get commas.
**Reverse at:** `app/src/Revenue.tsx`, the `moneyGrouped()` call sites.

### The date reformatted

**Decided:** `8/31/2026` → `Aug 31, 2026`.
**Argued:** the numeric form was the one column in its table whose width jittered row to
row, because `5/2/2026` and `12/13/2026` differ by four characters.
**Watch:** whether this is now inconsistent with dates rendered on other screens, and
whether it trades one jitter for another. Its reviewer was asked both.
**Reverse at:** `formatLastSold` in `app/src/Revenue.tsx`, now over `saleDate()` in
`app/src/dates.ts`.

## The design system

### `--bn-ink-3` darkened — OWNER ACCEPTED

`#6b7280` → `#666c76`. On the page background 4.43:1 → 4.85:1; on sunken wells
4.16:1 → 4.55:1. Both clear the 4.5 floor. The second clears it by 1.2% with no headroom
if a surface tone ever changes. Owner accepted that margin on 2026-09-20.
**Reverse at:** `app/src/tokens.css`, light-theme `--bn-ink-3`.

### `--bn-tracking-tight` folded onto `-0.02em` — OWNER NOT YET DECIDED

`-0.015em` → `-0.02em`, so the token and the 36 hand-written uses of `-0.02em` become one
value. Changes 13 call sites in files the deciding lane did not own. At the largest real
caller (22px) the difference is 0.11px per character, which is sub-pixel.
**Alternatives:** keep both values; or point the 36 literals at the existing `-0.015em` so
the token's value never moves.
**Reverse at:** `app/src/tokens.css`, `--bn-tracking-tight`.

### Fulfillment gets its own type register, not an extension of the shared one

**Decided:** `--ff-fs-*` (20/24/26/32/34/38/56px) scoped to `.fulfillment`.
**Argued:** three of those sizes have no neighbour within 2px in the shared scale, so
folding them in would widen the product's whole type vocabulary to serve one screen's
arm's-length reading distance. It is a closed, single-file register rather than an open one
other screens can add to.
**Reviewer agreed**, and noted the lane also de-duplicated the four literals (22/28/36/48)
that already matched shared tokens exactly — the sign of a real audit rather than a rubber
stamp.
**Reverse at:** `app/src/tokens.css` and `app/src/Fulfillment.css`.

### The unnamed registers, and the names chosen

- **Micro-spacing:** `--bn-0-5` (2px), `--bn-0-75` (3px), `--bn-1-5` (6px) — named as
  fractions of `--bn-1` so they read as a continuation of the existing scale rather than a
  competing scheme.
- **Line-height:** four tokens (`tight` 1.1, `snug` 1.25, `base` 1.4, `relaxed` 1.55) chosen
  from the 15 distinct values shipping. Deliberately not 15 tokens.
- **Radius:** `--bn-r-2xl-sm` (18px), the step nine call sites had each invented separately.

### `.bn-menu-label` moved off the faint token, `.bn-rule` left on it

The lane moved `.bn-menu-label` (3.64:1) and left `.bn-rule` (3.34:1), calling the latter
structural chrome rather than data. **Its reviewer disagreed**, and so do I: the words
rendered — "or", "or paste one", "This session" — are read by a person; the divider lines
either side are the chrome. Owner has since sent it to the cleanup lane to move.

## Copy and markup

### The reason code: chip → tooltip → gone — OWNER DECIDED

Removed from the page entirely. The human sentence beside it already says the same thing,
and a `title` is unreliable for screen readers and unreachable by touch. If the raw string
is wanted for debugging it belongs in a log.
**Two other `.review-code` sites stay** — the close-choice machine spelling and the
absent-detail note. Confirmed as distinct contexts, never the leak.

### `aria-label` rather than a hidden phrase

**Decided:** name Home's standing-row affordance with `aria-label`, not a visually-hidden
span.
**Argued on merit, after the word-ratchet reasoning was withdrawn:** the span is a kbd chip
and an arrow with no text of its own, so naming the affordance directly beats parking a
floating phrase in the reading order.

### The empty name in the graveyard

**Decided:** an empty-string card name renders "Unidentified".
**Argued:** the `??` fallback never fired on an empty string, so one row in a permanent
ledger had no identity at all. A blank is worse than a word that admits the gap.
**Reverse at:** the card-name fallback in `app/src/Graveyard.tsx`.

### Orders lede names the buyer count

`"551 lines"` → `"551 lines across 39 buyers"`. A walk is per person, so the buyer count is
the number that tells you the size of the job. Raises that screen's word ceiling; the owner
has deferred all ratchet questions to after the work.

### One disabled opacity instead of three

0.4, 0.45 and 0.5 could appear side by side, so "faded means disabled" stopped being a
reliable signal. Unified on `var(--bn-disabled)`.

## Tooling

### The regex gap in the css-var guard: documented, not fixed — OWNER DECIDED

A regex literal containing a quote inside a `style={{...}}` span can mask a finding. No
such shape exists in the codebase. Full regex-versus-divide disambiguation was judged not
worth the brittleness in a guard whose only value is that its green can be trusted.
Recorded in the script's own "what it cannot do" section.

### `--bn-rail-break-px`

The sidebar's breakpoint lives in `App.css` and is read back by `matchMedia` at runtime.
One number, one home, safe fallback. **The original justification was false** — the builder
believed a bare `1280` failed a check that never saw it. The design stands on merit; the
invented reason was corrected in the commit message and the comment.

## Three fixes deliberately NOT made

Recorded because a correct refusal is worth as much as a fix, and because each of these
looks like an unfixed finding unless the reasoning survives.

- **Capture's "New section" reading as `New sectionS`.** Verified through the accessibility
  tree, not the source: the accessible name is already "New section". The review's finding
  was an artifact of its own `textContent`-based script.
- **Inventory's box-rail numeral/caption drift.** The numeral and the caption already share
  size, colour and tabular-nums. The review itself flagged this as an unconfirmed hypothesis
  from a screenshot it could not re-verify. No matching defect exists in the code.
- **Shipping's all-null row.** The adjoining reason text already explains it.
