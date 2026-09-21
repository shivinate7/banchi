# The design system — UX review (centerpiece)

Method: `app/src/tokens.css`, `app/src/kit.css`, `app/src/kit/`, `app/src/base.css` read in full; every `*.css` under `app/src` grepped for raw literal values (font-size, font-weight, line-height, letter-spacing, padding/margin/gap, border-radius, transition duration, hex colors) versus token usage; contrast ratios computed directly (WCAG relative-luminance formula) for every token pair actually used as text-on-background in `tokens.css`; several claims verified live in the browser via CSSOM (`getComputedStyle`) rather than assumed from the source.

## Type scale

Documented scale (`tokens.css` `--bn-fs-*`, exhibited on `#/gallery`):

| Token | Value | Named use (gallery) |
|---|---|---|
| `--bn-fs-2xs` | 10px | Keycap · badge |
| `--bn-fs-xs` | 11px | Label · pill |
| `--bn-fs-sm` | 12px | Metadata |
| `--bn-fs-md` | 13px | Controls · table |
| `--bn-fs-base` | 14px | Body |
| `--bn-fs-lg` | 16px | Row primary |
| `--bn-fs-xl` | 18px | Section heading |
| `--bn-fs-2xl` | 22px | Stat value |
| `--bn-fs-3xl` | 28px | Page title |
| `--bn-fs-4xl` | 36px | Hero figure |
| `--bn-fs-5xl` | 48px | Home greeting |

Token usage counts across `app/src/**/*.css` (`var(--bn-fs-*)`): `sm` 217, `xs` 163, `md` 120, `base` 54, `2xs` 41, `lg` 40, `xl` 25, `2xl` 16, `3xl` 8, `4xl` 3. **`--bn-fs-5xl` (48px) has zero stylesheet uses of the token itself** despite being exhibited on the gallery as "Home greeting" — either Home sets it as a raw literal (untokenized) or the specimen is aspirational and nothing currently ships at that size through the token. Either way it's a token defined and shown but not demonstrably wired to the screen it's named for.

Raw literal `font-size: Npx` values found OUTSIDE the token scale (i.e., not going through a `--bn-fs-*` variable), with counts:

| Value | Count | Notes |
|---|---|---|
| 20px | 15 | Fulfillment.css's whole body register — an entire screen's base size (14px in the token scale) is a bespoke 20px, with no token for it |
| 22px | 11 | Overlaps `--bn-fs-2xl` (22px) exactly — these should be reading the token and are not |
| 32px | 7 | No corresponding token (between 28 and 36) |
| 24px | 6 | No corresponding token (between 22 and 28) |
| 34px | 5 | No corresponding token (between 28 and 36) |
| 26px | 3 | No corresponding token (between 22 and 28) |
| 56px | 1 | Exceeds the largest token (48px) |
| 48px | 1 | Duplicates `--bn-fs-5xl` as a literal instead of the token |
| 38px | 1 | No corresponding token (between 36 and 48) |
| 36px | 1 | Duplicates `--bn-fs-4xl` as a literal |
| 28px | 1 | Duplicates `--bn-fs-3xl` as a literal |
| 13px | 1 | Duplicates `--bn-fs-md` as a literal |

**Verdict: this is an accumulation, not a scale.** The token file defines 11 clean sizes; the shipped CSS actually renders at roughly 20 distinct sizes once literals are counted, and several of the literals (22, 28, 36, 48, 13px) exactly duplicate an existing token's value while bypassing the token — meaning a future re-tuning of, say, `--bn-fs-2xl` will silently stop matching the 11 places that hardcoded `22px` instead of reading it. Nearly all of the off-scale sizes trace to `app/src/Fulfillment.css`, which appears to have designed its own "arm's-length" register (20/24/26/32/34/38/56) without ever registering it as tokens.

Font-weight: 197 uses of 600, 103 of 700, 74 of 500, 72 of 800, 17 of 400, and **7 uses of 650** across `LiveReconcile.css`, `Markdown.css`, `RunPanel.css`, `ClearPrices.css`, `Orders.css`. `fonts.css`'s own header comment (lines 24-28) states plainly that 650 "resolves against these discrete faces to 700" — i.e., these 7 rules ask for a weight the shipped font files cannot produce, and get ordinary bold. This is dead specificity: a reader of the CSS sees "650" and reasonably infers a deliberate, subtly-lighter-than-bold weight was chosen; in the rendered product it is pixel-identical to `font-weight: 700`.

Line-height: 15 distinct values ship (1, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.4, 1.45, 1.5, 1.55, 1.6, and one bare `22` — a unitless-looking outlier at `line-height: 22` with no `px`, which if literal is a 22 multiplier rather than 22px, worth a direct look). No token exists for line-height at all — every one of these 15 values is a hand-typed literal beside a token'd font-size, so nothing prevents (and nothing has prevented) 15 different leading ratios shipping across the same handful of type sizes.

Letter-spacing: 13 distinct values ship, only 2 of which are tokens (`--bn-tracking-caps` 0.06em, `--bn-tracking-tight` -0.015em). The other 11 (-0.02em ×36 uses, -0.01em, 0.02em, 0.1em, -0.03em, 0.04em, 0.01em, -0.025em, 0.08em, -0.035em, -0.005em) are one-off literals. `-0.02em` alone (36 uses) is close enough to `--bn-tracking-tight` (-0.015em) that it looks like the same design intent expressed twice with two slightly different numbers.

## Spacing scale

Documented scale (`tokens.css` `--bn-1`…`--bn-10`): 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px — a clean, doubling-ish 4px-rooted scale, used pervasively via `var(--bn-N)`.

Off-scale raw-px `padding`/`margin`/`gap` values shipping outside any `--bn-N` token, with counts: `6px`×77, `2px`×68, `4px`×53 (this one exactly equals `--bn-1` and should be the token), `1px`×16, `5px`×14, `3px`×11, `10px`×8, `8px`×5 (exactly equals `--bn-2`, should be the token), `7px`×3, `9px`×1, `12px`×2 (exactly equals `--bn-3`), plus assorted `padding` single values (`10px`×8, `3px`, `7px`, `14px`, `9px`).

**Verdict: a real scale exists and is used correctly the majority of the time, but there is a large, consistent shadow-scale of small values (1–10px) that never goes through a token** — `6px` (77 uses) and `2px` (68 uses) are by far the two most common non-token spacing values in the codebase, more common than several of the actual tokens. This isn't scattered noise; it reads as an unstated "micro-spacing" register (icon gaps, badge padding, dot sizes) that the 4px-rooted scale is too coarse for (the smallest token, `--bn-1`, is already 4px). The fix is not "use the existing tokens for everything" — it's that the system needs a documented sub-4px-rooted micro scale (2/3/6px) the way it already has one for spacing ≥4px, because right now that register is invented ad hoc, file by file.

## Color ramp

Computed contrast ratios (WCAG relative luminance), light theme:

| Pair | Ratio | Needed | Verdict |
|---|---|---|---|
| `--bn-ink` on `--bn-bg` | 17.21:1 | 4.5 (body) | pass |
| `--bn-ink-2` on `--bn-bg` | 9.43:1 | 4.5 | pass |
| `--bn-ink-3` on `--bn-bg` | 4.43:1 | 4.5 (documented use: "metadata, captions, placeholders") | **FAIL, by 0.07** |
| `--bn-ink-3` on `--bn-surface-2` | 4.16:1 | 4.5 | **FAIL** |
| `--bn-ink-4` on `--bn-bg` | 3.33:1 | 3.0 (UI/large only — token's own comment says never a caption) | pass for its documented role |
| `--bn-ink-4` on `--bn-surface-2` | 3.13:1 | 3.0 | pass (borderline) |
| `--bn-accent` on `--bn-surface` | 5.34:1 | 4.5 | pass |
| `--bn-accent` on `--bn-bg` | 4.90:1 | 4.5 | pass (borderline) |
| `--bn-ok` on `--bn-surface` | 5.02:1 | 4.5 | pass |
| `--bn-warn` on `--bn-surface` | 5.02:1 | 4.5 | pass |
| `--bn-danger` on `--bn-surface` | 6.47:1 | 4.5 | pass |
| `--bn-live` on `--bn-surface` | 4.60:1 | 4.5 | pass (borderline, 0.1 margin) |

Dark theme:

| Pair | Ratio | Needed | Verdict |
|---|---|---|---|
| `--bn-ink` on `--bn-bg` | 16.93:1 | 4.5 | pass |
| `--bn-ink-2` on `--bn-bg` | 10.45:1 | 4.5 | pass |
| `--bn-ink-3` on `--bn-bg` | 5.62:1 | 4.5 | pass |
| `--bn-ink-3` on `--bn-surface` | 5.23:1 | 4.5 | pass |
| `--bn-ink-4` on `--bn-bg` | 4.34:1 | 3.0 | pass |
| `--bn-ink-4` on `--bn-surface` | 4.04:1 | 3.0 | pass |
| `--bn-accent` on `--bn-bg` | 6.75:1 | 4.5 | pass |
| `--bn-ok` on `--bn-bg` | 10.83:1 | 4.5 | pass |
| `--bn-warn` on `--bn-bg` | 9.46:1 | 4.5 | pass |
| `--bn-danger` on `--bn-bg` | 6.38:1 | 4.5 | pass |

**Finding: `--bn-ink-3` fails body-text contrast in light theme in the two places it is most likely to actually be read as a caption** — 4.43:1 on the page background (needs 4.5) and 4.16:1 on `--bn-surface-2` (sunken wells). The token's own comment in `tokens.css` documents its role as "metadata, captions, placeholders" — i.e., real reading text, not decoration — so this is a genuine, if narrow, AA failure for that token's own stated job, not a misuse by a caller.
Severity: medium (narrow miss, but it's the SYSTEM token failing its own documented contract, not a one-off screen bug — every caller who follows the rule correctly still fails).
Fix: darken `--bn-ink-3` slightly (light theme) — e.g. from `#6b7280` to something ≥`#5f6672`-equivalent — to clear 4.5:1 on both `--bn-bg` and `--bn-surface-2`.

**Finding: `.bn-menu-label` (kit.css:785) sets `color: var(--bn-ink-4)` for real, small (10px), all-caps text** — directly contradicting the token's own comment two lines above its definition in `tokens.css`: "Data-bearing text reads ink-3; this is the floor a word may sit at, never a caption." A menu-group label ("BOX" as a section label inside a dropdown) is exactly a caption. Measured contrast for `ink-4` on `--bn-surface` is 3.64:1 (light) — below the 4.5:1 a 10px caption needs.
Where: `app/src/kit.css:785`.
Severity: medium — low-vision users will struggle to read menu section labels, and it is the kit itself violating a rule written two lines above the color's own definition.
Fix: change `.bn-menu-label` to `var(--bn-ink-3)`.

**Hardcoded colors outside `tokens.css`/`markPalettes.ts`:** the only literal hex/rgb values found outside those two files were inside CSS *comments* (`CaptureScreen.css`, `ReviewQueue.css`, `kit.css`, `BoxBrowse.css`, `Orders.css` — all prose referencing colors by their hex for explanatory purposes, not live declarations). **Zero live hardcoded colors found in the ~100 other stylesheets** — this part of the system is genuinely clean and is worth naming as a strength, not just an absence of findings.

## Radii, borders, shadows

Documented radius scale: 4, 6, 8, 12, 16, 22px, plus a 999px pill (`--bn-r-xs/sm/r/lg/xl/2xl/full`). Token usage is heavy (92/86/39/36/19/15/12 uses respectively) — this is a real, well-adopted scale.

Off-scale raw `border-radius: Npx` literals with counts: `2px`×14, `3px`×13, `22px`×10 (duplicates `--bn-r-2xl` as a literal), `18px`×9 (no token — between 16 and 22, and used repeatedly, e.g. throughout `Fulfillment.css`'s panels), `4px`×8 (duplicates `--bn-r-xs`), `14px`×7 (no token — between 12 and 16), `5px`×5, `7px`×4, `16px`×4 (duplicates `--bn-r-xl`), `20px`×2 (no token), `999px`×1 (duplicates `--bn-r-full`), `8px`×1 (duplicates `--bn-r`), `6px`×1 (duplicates `--bn-r-sm`), `26px`×1 (no token, exceeds `--bn-r-2xl`), `1px`×1, `10px`×1.

`18px` (9 uses, all effectively "a radius between `--bn-r-xl` (16) and `--bn-r-2xl` (22) that isn't either") is the clearest sign of an implicit second radius step that never got named — most of Fulfillment's panel corners (`.ff-today-none`, `.ff-notice`, `.ff-empty` uses 22, but `.ff-box`, `.ff-order`, `.ff-more`, `.ff-sheet`-adjacent elements use 18) are on this unnamed step.

**Two undefined custom properties, confirmed live in the browser:**
- `border-radius: var(--bn-r-md)` — used at `app/src/CaptureScreen.css:154` (`.capture-rig-summary`). `--bn-r-md` is never defined anywhere in `app/src` (checked every `.css` file). Confirmed live: injecting a test element with `border-radius: var(--bn-r-md)` into the running app and reading `getComputedStyle(...).borderRadius` returns **`"0px"`** — i.e., this control renders with hard square corners in production, on every theme, contradicting every other rounded surface in the product.
- `border-radius: var(--bn-radius-md)` — used at `app/src/OrdersWalkPane.css:15` (`.orders-walk-photo`). Same story: `--bn-radius-md` is never defined. This is a photograph frame that should be rounded (every other photo frame in the product is — `.bn-photo` uses `--bn-r-lg`, `.ff-photo-btn` uses 22px) and instead renders with 0px corners.
Severity: **high**. These are not style nits — they are two custom-property typos (probably meant to both read the same token, and neither one is a real token name) that silently strip rounded corners from two live controls. Confirmed by direct computed-style read, not inferred.
Fix: point both at `--bn-r-lg` (12px, the closest existing "medium" step) or define `--bn-r-md` for real if a genuine in-between value is wanted, and use it consistently instead of two different misspelled names for what both call sites clearly intend to be the same thing.

Shadows: exactly 3 shadow levels plus 1 accent glow (`--bn-shadow-1/2/3/accent`), each carefully specified with 2-3 layered box-shadows, and no raw literal `box-shadow` values found competing with them outside per-component *modifications that reuse the tokens* (e.g. `.ff-notice`'s `inset ... var(--bn-warn), var(--bn-shadow-1)`, which composes a token with an inset ring rather than inventing a new shadow). **This is a real, disciplined elevation system — the one part of "radii/borders/shadows" with no drift to report.**

## Motion

Documented scale: 3 durations (`--bn-t-fast` 120ms, `--bn-t` 200ms, `--bn-t-slow` 320ms) × 3 eases (`--bn-ease`, `--bn-ease-out`, `--bn-ease-spring`), plus named specials (`--bn-t-draw` 480ms, `--bn-t-emphasis` 600ms, `--bn-t-pulse` 1.8s, `--bn-t-spin` 0.7s). Token usage is very heavy (236/119/105 uses for fast/base/slow) — the core 3-duration scale is well adopted.

Raw literal `Nms` values shipping outside the token scale, with counts: `0ms`×10 (likely reduced-motion or "no transition" overrides — check individually), `40ms`×6, `60ms`×4, `520ms`×3, `160ms`×3, `80ms`×2, `420ms`×2, `30ms`×2, `220ms`×2, `180ms`×2, and singletons at `90ms, 70ms, 700ms, 600ms, 560ms, 480ms, 380ms, 360ms, 18ms, 140ms, 1200ms`. Several of these exactly duplicate a token as a literal (`480ms` matches `--bn-t-draw`, `600ms` matches `--bn-t-emphasis`), meaning if either named duration is ever re-tuned, these literals silently go out of step with the system they were copying.

`40ms` (6 uses) is the most common off-scale duration and does not correspond to any documented step — worth checking whether these are meant to be `--bn-t-fast` (120ms) written wrong, or a genuine "micro" fourth duration nobody named.

Reduced-motion is handled centrally and correctly in `base.css` (crushes all durations to 0.01ms, with a documented, narrow allow-list of loops that must keep turning) — this is a system strength, not a finding.

**Property-animation correctness, spot-checked:** `base.css`'s response floor explicitly and correctly excludes `transform`/`padding`/`width`/`font-size` from the shared hover transition (documented reasoning: these can reflow a target under a moving finger, D28's original defect). The press floor correctly uses `translate` (not `transform`) so it composes with, rather than clobbers, any element's own `transform: scale()`. No instance was found of a rule animating `background-image` (correctly avoided everywhere per the file's own stated rule; `kit.css`'s hover-fill patterns all use solid `background-color` or an inset `box-shadow`, never a gradient transition). This part of the system was checked for the specific failure modes the brief calls out and none were found — a genuine strength worth naming.

## Interaction states (sampled)

- `.bn-btn` family: hover, active (with a documented, deliberate double-timing "wobble" — 1px instant dip + 120ms scale ease), disabled (opacity 0.45, transform cancelled), and busy (spinner, color hidden) are all present and distinct. Focus relies entirely on the global `base.css` `:focus-visible` rule (2px accent outline) rather than a button-specific focus style — this was checked for a real defect hypothesis (that the global rule's own `border-radius: var(--bn-r-xs)` would visually square off pill-shaped buttons on focus) and **that hypothesis was refuted by live testing**: real keyboard-Tab focus on a `.bn-btn-pill` element showed `border-radius` staying `999px` under `:focus-visible`, because `kit.css` (loaded after `base.css`) re-declares the pill's radius at equal specificity and wins the cascade tie by source order. Recorded here as a check that was run and passed, per the instruction to verify rather than guess.
- `.bn-chip`: hover, active (via the shared press floor), disabled, and a distinct `[aria-pressed='true']` selected state (inverts to ink-on-bg) are all present — a complete state set.
- `.bn-tab`: hover, selected (`aria-selected`/`aria-current`), and an underline transition are present; the kit's own comment explains, correctly, why selected tabs deliberately do not have a distinct hover (no background to change). No disabled state is defined for tabs at all — not flagged as a defect since tabs are typically not disabled in this product's own vocabulary, but worth noting as an absence.
- `.bn-pill`: confirmed via grep that pills are used exclusively as non-interactive status badges in this codebase (no `onClick`/`<button>` usage found anywhere pairing with `bn-pill`) — so the apparent absence of hover/active/focus states on pills is correct, not a gap. This is a case where the brief's checklist ("does each component have every state it needs") is correctly answered "it needs none, and has none."
- `.bn-input`/`.bn-select`/`.bn-textarea`: hover (border darkens), focus-visible (accent border + ring), and disabled all present via a shared rule block — complete.

## Duplicates (components hand-rolled where the kit already provides one)

1. **`.ff-empty-art` (Fulfillment.css:391-399, 72×72px, `--bn-r-2xl`, `--bn-accent-tint`/`--bn-accent`) vs `.bn-empty-art` (kit.css:653-662, 56×56px, `--bn-r-xl`, identical color pair).** Same shape, same color logic, different hardcoded size — should be a kit size modifier, not a screen-local reinvention. (Also logged in `fulfillment.md`.)
2. **`.review-key` vs `.bn-kbd`** — the kit's own gallery text admits this is "a candidate for promotion," i.e., a second keycap implementation living outside the kit that the system's own authors already flagged as needing consolidation. (Also logged in `kit.md`.)
3. **`font-weight: 650` vs `700`** — not a component duplicate in the traditional sense, but functionally the same defect pattern: two spellings for one rendered result, one of which (650) is dead weight in every sense of the phrase.
4. **The 18px "unnamed radius step"** (9 uses, see Radii section above) functions as a duplicate of the gap between `--bn-r-xl` (16) and `--bn-r-2xl` (22) — every one of those 9 call sites made an independent, uncoordinated decision to split that gap the same way, which is really one design decision expressed 9 times without ever being named.

## What I could not check
- Hover/active states were verified against the CSS source and, for the focus-radius hypothesis, live in the browser; the remaining hover/active color values were NOT re-verified pixel-for-pixel on screen (the Browser pane was hidden for most of this session) — treat the "interaction states" section above as CSS-source-verified plus one live-confirmed check, not a full visual sweep.
- Dark-theme contrast was computed from `tokens.css`'s declared dark values, not cross-checked against any component that might apply an additional overlay (e.g., `--bn-surface-glass`, backdrop blur) that could alter effective on-screen contrast in a real composited frame.
- Line-height's one outlier (`line-height: 22` with no unit, found in the grep) was not traced to a specific file/line in this pass — flagged as needing a follow-up grep with file context before treating it as confirmed rather than a possible grep artifact (e.g. matching inside a shorthand or a comment).
- The micro-spacing values (2px/6px used 145 times combined) were counted but not traced file-by-file to confirm none of them are, in fact, meant to be `--bn-1` (4px) mis-typed as `--bn-2`'s intended half-step — a full file-by-file audit of all 145 occurrences was out of scope for this pass.
- Motion and radius "off-scale" literal counts were gathered via regex over single-value shorthand (`padding: Npx`) and may undercount multi-value shorthand (`padding: 4px 8px 4px 8px`) that mixes token and literal values on one line — the true off-scale count is likely higher than reported here, not lower.
