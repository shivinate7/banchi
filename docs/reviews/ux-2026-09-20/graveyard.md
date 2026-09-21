# Graveyard — UX review

**Screen:** `#/graveyard` (toolbar with search + How filter, one table, no shell beyond the standard page header).
**Checked:** 1440 width, light theme confirmed live via DOM/CSSOM (`javascript_tool`) with a real store loaded (863 departed rows: 596 sold, 3 retired, 264 moved, 303 buried against an "All" count that does not sum cleanly to 863 — see finding 5). Dark theme checked from `tokens.css` values only, not confirmed live on this screen specifically. 1280 width checked from CSS only (no width-specific media query exists between 1280 and 1440 for this screen's table, so this is a low-risk claim, but not an observed one).

Files read: `app/src/Graveyard.tsx`, `app/src/Graveyard.css`, `app/src/kit.css` (table primitives), `app/src/cardState.ts` (referenced), `app/src/tokens.css`.

## Findings

### 1. A departed card with no name renders a blank Card cell instead of "Unidentified"
**What I saw:** the first row in the live "All" table (a Retired/pulled Riftbound card) renders `<span class="graveyard-name"></span>` — empty. The Card cell shows nothing but a "Riftbound" game pill; there is no card name, no dash, no "Unidentified" text. I sampled the next 14 rows and all had real names, so this is a specific data case (an empty-string name), not the norm.
**Where:** `app/src/Graveyard.tsx:234` — `<span className="graveyard-name">{row.name ?? <span className="bn-faint">Unidentified</span>}</span>`. The `??` operator only substitutes on `null`/`undefined`; it does not catch an empty string `""`, which is what this row's `name` field actually holds (confirmed: `JSON.stringify(row.name)` on the live element returned `""`, not `null`).
**Severity:** high — a row in a permanent, read-only historical ledger has no legible identity at all. In a screen whose entire purpose is "every card that's left inventory," a card that cannot be identified from the row is a real gap, not a cosmetic one.
**Fix:** change the check to `row.name ? row.name : <span className="bn-faint">Unidentified</span>` (or `row.name?.trim() ? ... : ...` if whitespace-only names are possible), matching what `gameLabel()` two functions above already does correctly with `.trim() === ''`.
**Does it recur:** the same `??`-on-a-possibly-empty-string pattern is worth checking anywhere else `row.name` is read this way; I did not grep the rest of the app for it.

### 2. The retirement reason is printed as a raw, lowercase machine string next to a Title Case label
**What I saw:** the "How" column for a retired card renders, verbatim: **"Retired · pulled"** (confirmed live). "Retired" is Title Case; "pulled" is the raw enum value with no capitalization or humanizing applied.
**Where:** `app/src/Graveyard.tsx:56` — `<span className="graveyard-reason">{row.retire_reason}</span>` prints `row.retire_reason` directly. Compare `app/src/Inventory.tsx:72-76`, which defines the canonical human label for the exact same enum, in the exact same product, for the retire dialog: `'pulled'` → **"Pulled out"**, `'damaged'` → **"Damaged"**, `'lost'` → **"Lost"**, `'given_away'` → **"Given away"**. Graveyard reinvents nothing and instead skips the humanizing step entirely for this one field, while `gameLabel()` three lines above it in the same file DOES humanize its own raw string ("raw_underscored" → "Raw underscored").
**Severity:** medium. It reads as an internal code leaking onto a screen meant to be read casually ("pulled" out of context could be misread as "pulled for an order" rather than "pulled out of the box for something else," which is what the reason actually means per Inventory.tsx:73). It also breaks the sentence's own register — every other word around it is a normal capitalized word.
**Fix:** export the `REASONS` label map (or an equivalent `RETIRE_REASON_LABEL` lookup) from wherever it's shared, and have `howIt()` look up `row.retire_reason` through it, falling back to the raw string only if the value is unrecognized.
**Does it recur:** this is the one place I found it in this slice; worth a repo-wide check for any other screen reading `retire_reason` raw (I did not find another reader in `app/src`).

### 3. `.graveyard-condition` uses a token the app's own design system documents as failing contrast for this exact use
**What I saw, measured:** `.graveyard-condition` (e.g. the "Near Mint Foil" line under a card's name) is `color: var(--bn-ink-4)` at `font-size: var(--bn-fs-xs)` (11px). Confirmed live: `rgb(127, 135, 145)` text on `rgb(244, 245, 248)` background (the page ground; the table has no card/surface behind it — I walked up six ancestors and all had `background-color: transparent`). Computed contrast ratio ≈ **3.34:1**. WCAG AA for normal text (11px is not "large text") requires 4.5:1.
This isn't a guess about the token — `app/src/CardLocations.css:130-132` documents the identical problem in the identical codebase and switched away from `--bn-ink-4` for exactly this reason: *"INK-3, NOT INK-4: it is a sentence a person reads, and at 11px ink-4 measures 3.64:1 in the light theme — under AA for body text. ink-4 is for a mark, not for a line of prose."* `tokens.css:56-57` says the same thing generally: *"ink-4 is the floor a word may sit at, never a caption; data-bearing text reads ink-3."* A card's condition ("Near Mint Foil") is exactly the kind of word CardLocations.css is describing — a fact a person reads, not a decorative mark.
**Where:** `app/src/Graveyard.css:95` — `.graveyard-condition { ... color: var(--bn-ink-4); }`.
**Severity:** high — it's a quantified AA failure, on a token the codebase's own comments say not to use here, in the very file (Graveyard) that sits beside CardLocations.css in the same product area.
**Fix:** change to `var(--bn-ink-3)`, matching `CardLocations.css`'s own resolution of the identical problem.
**Does it recur:** dark theme's `--bn-ink-4` (`#707886` on `#0c0e12`) computes to roughly 4.3:1 by my calculation — closer to AA but still under 4.5:1, and still against the token file's own stated rule that ink-4 is never for a caption/word. So this is a two-theme issue, worse in light.

### 4. Departed rows fade in all at once instead of using the product's own stagger convention
**What I saw:** `.graveyard-row { animation: graveyard-row-in var(--bn-t-slow) var(--bn-ease-out) backwards; }` (`Graveyard.css:82`) applies the same `320ms` fade-and-rise to every row with no `animation-delay` offset. `kit.css:80-81` defines the product's shared stagger mechanism (`.bn-stagger > * { animation-delay: calc(min(var(--i,0), var(--bn-stagger-cap)) * var(--bn-stagger)) }`), and `Orders.tsx` uses it for its own lists (`orders-index bn-stagger` at line 3276, `orders-map-stops bn-stagger` at line 4400). Graveyard's table never applies `.bn-stagger` or sets `--i` per row, so with up to 863 rows in the DOM at once, they all fade in on the same frame rather than cascading — visually a single flat fade rather than the cascading-list reveal used elsewhere in the product.
**Where:** `app/src/Graveyard.css:82-86`; contrast `app/src/kit.css:80-81` and `app/src/Orders.tsx:3276`.
**Severity:** nit — but it is a real, visible difference between this list and its sibling screens, not just a missed convention on paper.
**Fix:** either apply `.bn-stagger` + `--i` per row (capped, as the mechanism already handles via `--bn-stagger-cap`), or if 863 rows makes a stagger impractical (it would take `12 * 30ms` = 360ms to reach the cap and then hold flat — probably fine), state a reason in a comment for why this list is exempt.
**Does it recur:** no — this is the only list-type screen in my slice missing it; Orders (also in my slice) uses it correctly.

### 5. All 863 rows are rendered in the DOM at once, with no virtualization
**What I saw:** `document.querySelectorAll('.graveyard-table tbody tr').length` returned 863 on the live store. There is no windowing/virtualization in `Graveyard.tsx`.
**Where:** `app/src/Graveyard.tsx` (the render loop over `rows`, around line 200+).
**Severity:** nit-to-medium depending on how large this ledger is expected to grow — at 863 rows scroll performance seemed fine in this session, but this is a ledger that only grows (nothing is ever un-buried), so this is worth flagging before it becomes a real problem at, say, 5,000+ rows.
**Fix:** not urgent; noting for awareness rather than recommending immediate work.
**Does it recur:** n/a, unique to this screen's read-only, ever-growing nature.

### 6. Filter segmented control counts don't visibly cross-check against "All"
**What I saw:** All (863), Sold (596), Retired (3), Moved (264), Buried (303). 596+3+264+303 = 1,166 ≠ 863. This is very likely correct by design — a buried record can independently also be sold/retired/moved (the screen's own doc comment says "TWO SOURCES, ONE TABLE... merges both"), so the categories are not mutually exclusive with "Buried," and a card can be both e.g. Sold AND Buried. I'm flagging this only because, from a plain read of five mutually-labeled filter pills, a person doing the arithmetic in their head (as I did) will get a number that doesn't match and may wonder if the counts are wrong.
**Severity:** nit.
**Fix:** none needed if this is intentional (it reads as intentional from the code comment) — but consider whether "Buried" being a different axis from the other four (an axis of "how it left the box in the log" vs "whether the box itself was deleted") deserves a visual separator in the filter row (e.g. `All | Sold | Retired | Moved  ·  Buried`) so it doesn't read as a fifth sibling category that should sum with the rest.
**Does it recur:** no.

## What I could not check
- **Dark theme, live, on this screen specifically.** I confirmed the dark-theme token values from `tokens.css` and recomputed contrast for finding 3 from those values, but did not re-open Graveyard in dark theme in the browser after the pane stopped compositing screenshots.
- **1280 width, live.** No Graveyard-specific breakpoint exists between 1280 and 1440 in `Graveyard.css` (the table just gets `overflow-x: auto` if it doesn't fit), so I have no reason to expect a defect there, but I did not visually confirm it.
- **The loading skeleton** (`.graveyard-loading`/`.graveyard-skel-row`) — not observed live (the store answered before I could catch it); read from CSS only.
- **The empty state** (a store with zero departed cards) — not observed; this store has 863.
- **The failure/retry state** (`.graveyard-failure`) — not observed; the server was reachable throughout.
- **The phone/narrow card-layout CSS** (`@media max-width: 639px` in `Graveyard.css`) — explicitly out of scope (desktop only), not reviewed.
- **Filter-row scroll-edge-fade behavior** (`Graveyard.css:39-52`, the `animation-timeline: scroll()` mask) — this only applies under 767px, out of scope for this pass, not reviewed.
