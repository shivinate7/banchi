# The 2026-09-20 review, assessed

One pass over all sixteen logs. Findings are deduplicated across files, re-tallied by hand,
and ranked by breadth times confidence times cheapness. Every item below was confirmed
against the live app by the agent that filed it, unless it says otherwise.

Read `INDEX.md` first for the standard these were written to and for the coverage gaps.

## Tier 1 — do these first

Three items. All cheap, all confirmed, and each one carries across several screens.

### 1. Five CSS custom properties are referenced and never defined

| Property | Referenced at | What renders |
| --- | --- | --- |
| `--bn-r-md` | `app/src/CaptureScreen.css:154` | `.capture-rig-summary`, square corners |
| `--bn-radius-md` | `app/src/OrdersWalkPane.css:15` | `.orders-walk-photo`, square corners |
| `--bn-well` | `app/src/Pricing.css:835` | `.pricing-locked` loses its muted ground |
| `--bn-muted` | `app/src/Pricing.css:836` | the same pill renders at full contrast |
| `--bn-border` | `app/src/ProductHistory.css:75` | `border-style: none`, panels near-invisible in light theme |

A `var()` with no definition and no fallback drops the whole declaration silently. Two
agents confirmed these by reading `getComputedStyle` in the running app, not off the
stylesheet. Four screens, five one-line fixes.

**The fix worth more than the five fixes:** nothing in this repo reads for an undefined
custom property. A check that walks `app/src/**/*.css`, collects every `var(--x)` with no
fallback, and fails when `--x` is defined nowhere would have caught all five the day they
landed. It is a small script and it never needs looking at again.

### 2. Contrast, one token and two call sites

- `--bn-ink-3` measures **4.43:1** on `--bn-bg` and **4.16:1** on `--bn-surface-2` in light
  theme, against the 4.5:1 body text needs. The token's own comment gives it the job of
  "metadata, captions, placeholders" — reading text. Every caller who uses it exactly as
  documented still fails. Darkening the light-theme value fixes every one of them at once.
- `.bn-menu-label` (`app/src/kit.css:785`) sets 10px all-caps text in `--bn-ink-4`, 3.64:1,
  two lines below that token's own comment saying it may never be a caption.
- `.graveyard-condition` (`app/src/Graveyard.css:95`) puts card condition prose in
  `--bn-ink-4` at 3.34:1. `CardLocations.css:130` forbids this exact usage in a comment.

### 3. The sidebar decides collapsed or expanded once, at mount

`app/src/App.tsx:324` reads `window.innerWidth < 1280` as a `useState` lazy initializer
(`:1352`) and nothing re-runs it. With no stored preference, a window resized from 1440 to
1000 keeps the rail expanded until a reload. Reproduced directly. One listener fixes it for
every screen in the product.

## Tier 2 — the system is drifting, and it drifts silently

These are not visible defects today. Each one is a mechanism by which a future change to a
token quietly stops reaching the screens that meant to use it.

### 4. Literals that duplicate a token exactly

`22px` (11 uses) is `--bn-fs-2xl`. `28px`, `36px`, `48px` and `13px` each duplicate a font
token. `22px`, `16px`, `8px`, `6px`, `4px` and `999px` each duplicate a radius token.
`480ms` is `--bn-t-draw` and `600ms` is `--bn-t-emphasis`. `4px`, `8px` and `12px` each
duplicate a spacing token.

Re-tune any of those tokens and the copies stay where they are. This is the single largest
category in the review by count, and it is invisible until the day someone re-tunes.

### 5. Whole registers that were never named

- **Type.** Eleven tokens are defined; roughly twenty distinct sizes ship. Most of the
  excess is `Fulfillment.css`, which invented an arm's-length register (20, 24, 26, 32, 34,
  38, 56px) and registered none of it. The kit sheet presents the scale as complete, so a
  whole screen's type is invisible on the page that claims to document the system.
- **Micro-spacing.** `6px` (77 uses) and `2px` (68 uses) are more common than several real
  spacing tokens. The scale starts at 4px, so this register has nowhere to live and is
  re-invented file by file. The fix is to name 2 / 3 / 6px, not to force these onto `--bn-1`.
- **Radius.** `18px` appears 9 times, always splitting the gap between `--bn-r-xl` (16) and
  `--bn-r-2xl` (22). One design decision, made independently nine times.
- **Line-height.** Fifteen distinct values ship and there is no line-height token at all.
- **Letter-spacing.** Thirteen values, two of them tokens. `-0.02em` (36 uses) sits next to
  `--bn-tracking-tight` (-0.015em) — the same intent written as two different numbers.

### 6. `font-weight: 650`, seven times

`fonts.css` states in its own header that 650 resolves to 700 against the shipped faces.
Seven rules across five files read as a deliberate intermediate weight and render as
ordinary bold.

## Tier 3 — screen defects worth fixing on their own

Ordered by how badly each one reads, not by cost.

1. **A permanent ledger row with no identity.** `Graveyard.tsx:234` falls back with `??`,
   which does not fire on an empty string. One live row renders with no card name at all,
   on the one screen whose entire job is recording what left.
2. **Sales money does not line up.** `Revenue.css:81` gives every month row its own grid, so
   the Gross figure's left edge drifts up to 13px row to row — measured 1084.15 to 1097.30px
   over five rows. A stacked column of dollar figures that is not a column.
3. **Product history labels collide.** `ProductHistory.tsx:205` wraps the heading in an
   unstyled `div` that shrink-wraps inside a flex row, so the range tag drops to a cramped
   second line 5px below instead of sitting beside it. All four panels, both widths.
4. **The Fulfiller's primary action is styled as secondary.** `.ff-step` is the largest
   element on the card panel and uses the quiet outline variant. On the one screen built for
   someone working fast, the button to press does not look like the button to press.
5. **Review prints its own internal reason code** next to the human sentence it already
   wrote (`ReviewQueue.tsx:1685` and `:1846`).
6. **Three disabled opacities** — 0.4, 0.45 and 0.5 — can appear side by side on Inventory,
   so "faded means disabled" stops being a reliable signal.
7. **Duplicated primitives.** `.ff-empty-art` against the kit's `.bn-empty-art` (same shape,
   same colors, different hardcoded size); `.review-key` against `.bn-kbd`, which the kit
   sheet itself already labels "a candidate for promotion"; and three separate local
   icon-badge treatments inside `Fulfillment.css`.

## What the review found to be genuinely good

Worth recording, because these are the parts nobody needs to look at again.

- **Zero live hardcoded colors** across roughly one hundred stylesheets. Every hex found
  outside `tokens.css` and `markPalettes.ts` was inside a comment.
- **The elevation system.** Three shadow levels and one accent glow, no competing literals;
  components compose with the tokens rather than inventing new shadows.
- **Reduced motion**, handled centrally with a narrow, documented allow-list.
- **The press and response floors** were checked for the specific failure modes they exist
  to prevent — animating `background-image`, clobbering a component's own `transform`,
  reflowing a target under the pointer — and none were found.
- **The command palette** measured 0px baseline variance across all 16 items in 5 groups.

## Before acting on any of this

- Coverage is uneven. 1440 and dark are measured throughout. 1280 and light theme are
  UNKNOWN in several files, because two agents lost the browser pane partway. Every file
  names its own gaps and an UNKNOWN is not a pass.
- Tier 2's counts were gathered by regex over single-value shorthand. Multi-value shorthand
  that mixes a token and a literal on one line is undercounted, so those numbers are floors.
- One line-height outlier (`line-height: 22`, no unit) was never traced to a file. It may be
  a grep artifact. Confirm before treating it as real.
- Mobile was out of scope entirely.
