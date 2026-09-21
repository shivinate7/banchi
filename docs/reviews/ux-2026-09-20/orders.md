# Orders — UX review

**Screen:** `#/orders` (the "pull" stage of the Orders/Shipping hub — buyer index, walk pane, order-line list, paste composer).
**Checked:** 1440 width, light theme confirmed live via DOM/CSSOM with a real store loaded (39 buyers, 551 lines). Dark theme and 1280 width read from CSS breakpoints and token values, not confirmed live (see "What I could not check" — the Browser pane stopped compositing frames partway through this review). Populated state confirmed (an open buyer, a walk card with a real photo). Empty/loading states not observed.

Files read: `app/src/Orders.tsx`, `app/src/Orders.css`, `app/src/OrdersWalkPane.tsx`, `app/src/OrdersWalkPane.css`, `app/src/OrdersHubStore.ts` (referenced), `app/src/BoxBrowse.css` (shared `.browse-*` primitives this screen depends on), `app/src/tokens.css`, `app/src/kit.css`.

## Findings

### 1. `--bn-radius-md` does not exist — the walk pane's photo placeholder has no border-radius
**What I saw, verified live:** when a walk card's take has not resolved to a real row (`row === null` in `OrdersWalkPane.tsx:692`), it renders a placeholder tile with class `.orders-walk-photo` instead of the real `PhotoPanel`. That class is styled at `OrdersWalkPane.css:12-22`:
```
.orders-walk-photo {
  width: 100%;
  aspect-ratio: 5 / 7;
  border-radius: var(--bn-radius-md);
  ...
}
```
`--bn-radius-md` is never defined anywhere in the app — I grepped every `.css` file under `app/src` and it appears exactly once, on this line. `tokens.css` defines `--bn-r`, `--bn-r-sm`, `--bn-r-lg`, `--bn-r-xl`, `--bn-r-2xl`, `--bn-r-full`, `--bn-r-xs`, but nothing named `--bn-radius-md`. A `var()` reference to an undefined custom property with no fallback computes to its initial value, which for `border-radius` is `0`. So this placeholder tile renders with square corners, next to every other photo frame in the product, all of which use a real token — e.g. the resolved-state `.browse-photo-frame` on this same screen computes to `12px` (`var(--bn-r-lg)`) live.
**Where:** `app/src/OrdersWalkPane.css:15`.
**Severity:** medium. It's a real, silent CSS bug (an invalid variable reference, not a deliberate `0`), and it breaks visual consistency the instant this state is reached — a squared-off placeholder sitting where a rounded photo frame belongs everywhere else in the product.
**Fix:** change `var(--bn-radius-md)` to `var(--bn-r-lg)` (matching `.browse-photo-frame`'s own 12px, since this tile is standing in for that exact element) or `var(--bn-r)`.
**Does it recur:** no other file references `--bn-radius-md`, so this is contained to one line, but I'd flag it for a broader search of undefined `var()` references across the app — this one only surfaced because I happened to read the file closely; a build-time or lint-time check for undefined custom properties would catch this class of bug automatically.

### 2. The lede collapses from a full sentence to a bare, jargon-y count once the ledger loads
**What I saw:** before the order ledger answers, `Orders.tsx:2167` shows a full descriptive sentence: *"Which copies each buyer gets, and where in the boxes they are. One press per copy, with twenty seconds to take it back."* The instant it loads, the lede becomes just `<strong>551</strong> lines` (via `summaryOf()`, `Orders.tsx:914-921`) — no sentence, no explanation of what a "line" is. Confirmed live: the header under "Orders" reads exactly **"551 lines"** with nothing else.
**Where:** `app/src/Orders.tsx:2163-2168`, `914-921`.
**Severity:** nit-to-medium. "Line" is order-fulfillment jargon (an order line item) that a returning owner probably knows, but it's a steep drop in informativeness compared to the loading-state sentence one line above it in the same function, and a new/infrequent user gets no help understanding what the number means.
**Fix:** something like `<strong>551</strong> lines across 39 buyers` (or similar), keeping the number but restoring a little context, the way `Shipping`'s own lede ("TCGplayer's shipping export, sorted into three lanes") stays a full sentence permanently rather than collapsing to a bare figure.
**Does it recur:** the counterpart Shipping lede does NOT have this problem (it's a fixed sentence, never collapses) — so this is specific to the Orders/pull half of this shared hub component.

### 3. The buyer index row's meta line is an unconditionally-rendered empty span for a single-order buyer
**What I saw, live:** the first buyer row's DOM is:
```
<span class="orders-index-main">
  <span class="orders-index-number">Sean Jenson</span>
  <span class="orders-index-meta"></span>
</span>
```
`app/src/Orders.tsx:3641-3644`'s own comment confirms this is by design — the meta span is "drawn only when there is something to count," i.e. only a buyer with more than one order gets content in it — but the `<span>` itself is still emitted empty rather than omitted for a single-order buyer like this one. Visually inert (an empty inline span takes no space), but it's a small amount of dead markup on every single-order row in a 39-row list.
**Where:** `app/src/Orders.tsx:3641-3644`.
**Severity:** nit.
**Fix:** render the span conditionally (`{hasMultiple ? <span className="orders-index-meta">...</span> : null}`) rather than always emitting an empty one — purely a cleanliness nit, no visible effect.
**Does it recur:** no, single occurrence.

### 4. Three different micro-gap values used for icon-to-text spacing in adjoining rules
**What I saw:** within `Orders.css`, several visually similar "icon + short text" patterns use different `margin-right`/`gap` values for what reads as the same relationship: `margin-right: 3px` (`Orders.css:477`), `margin-right: 4px` (`Orders.css:521`), and `gap: 4px` used elsewhere for the same icon-label pairing pattern (e.g. `Orders.css:678`, `894`, `908`). None of these are on the `--bn-*` spacing scale (which starts at 4px/`--bn-1`), so `3px` in particular is a one-off value with no token backing it.
**Where:** `app/src/Orders.css:477`, `521` (compare `678`, `894`, `908`).
**Severity:** nit — these are all sub-token "optical" adjustments and might be individually justified (kerning against a specific glyph), but a 3px vs 4px split for the same visual role, with no comment explaining why one icon needs 1px less clearance than another, reads as drift rather than intent. Nothing else in this codebase's more heavily-commented files (PositionBar.css, PositionLabel.css) leaves an optical adjustment like this uncommented — every hand-tuned pixel value there has a paragraph explaining the measurement.
**Fix:** either standardize on one value for icon-to-label clearance in this file, or add the same kind of one-line comment this codebase uses everywhere else to justify a non-token value.
**Does it recur:** yes, this pattern (uncommented sub-token pixel values) appears across `Orders.css`, `BoxOps.css`, `CardLocations.css` — see the Inventory report's tracking-letter-spacing finding for another instance of the same underlying habit.

## What I could not check
- **Dark theme, live, on this screen.** Read from `tokens.css` values only after the Browser pane stopped compositing frames; not visually confirmed.
- **1280 width, live.** `Orders.css:108` and `:145` both switch layout at `max-width: 1279px` (the view-controls grid and the two-pane `.orders-layout` column width, 300px → 268px). At exactly 1280 the wide layout should still apply per the CSS; I did not confirm this boundary live, only read it.
- **The Shipping half of this same file** is covered in `shipping.md`, not here, even though they share one React component (`Orders.tsx`) and one `OrdersHubStore`.
- **Empty state** (zero open orders) — not observed; the live store had 39 buyers.
- **Loading state** — the ledger answered before I could reliably catch the loading sentence live; I only have it from source (`Orders.tsx:2167`).
- **The paste composer** (pasting a new order export) — not opened; it's a write-adjacent flow I did not want to risk triggering a real submission.
- **Keyboard walk (`J`/`K` stepping)** and **undo** — not exercised, since Undo is a write-adjacent control per the task's safety fence.
- **Finding 3's exact trigger condition** — needs a closer read of `Orders.tsx` than I completed in this pass.
