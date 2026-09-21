# Sales (`#/revenue`)

**Coverage:** 1440px and 1280px, light and dark theme. States seen: populated verdict + month strip + product table (6 months, 748 orders, $66,334.71 gross), a product row's drill-down disclosure. Measurements via `getComputedStyle`/`getBoundingClientRect` against the running app (screenshots unavailable this session — see "What I could not check").

## Findings

### 1. The month strip's Gross figures do not align horizontally between rows
**What I saw:** each `.revenue-month-row` is its own independent CSS grid (`grid-template-columns: 1fr auto auto`), not a shared grid across the list. Because the money cell's track is sized to that row's own content (`auto`), and the row's `1fr` name column absorbs the remaining width, the left edge of the money figure shifts row to row depending on how many digits that row's own figure has. Measured across five consecutive rows at 1440, dark theme:
  - Sep 2026: `$11,814.18` — x = 1084.40
  - Aug 2026: `$14,071.40` — x = 1085.13
  - Jul 2026: `$5,058.36` — x = 1097.30
  - Jun 2026: `$10,688.80` — x = 1086.63
  - May 2026: `$24,701.97` — x = 1084.15

  That is a 13.15px jitter in the money column's left edge (1084.15 to 1097.30) across a list of six numbers stacked for exactly the purpose of scanning them together. The `Orders` column to its right (`.revenue-month-orders`) is explicitly `text-align: right` and its right edge is correctly flush at x=1240 on every row — only the money figure between the name and the order count is left unaligned.
**Where:** `app/src/Revenue.css:81-102` (`.revenue-month-row` grid + `.revenue-month-orders`; the money cell in between has no class and no `text-align` rule at all).
**Severity:** high. This is exactly the kind of numeric list the review brief calls out — a stacked column of dollar figures — and it currently reads as a ragged left edge rather than a column, which defeats the point of a month-over-month strip (a reader scanning down expects to compare figures at a glance).
**Fix:** either give the money cell a class with a fixed `min-width` (sized to the widest figure, e.g. via the same `ch`-based technique used elsewhere in this file for the order-number column) and `text-align: right`, or move `.revenue-month-rows` to a single shared grid (CSS Grid on the list, not per-row) so all rows share one set of column tracks. Either fixes the alignment; the second also fixes it for any future row count without a manual width guess.
**Recurs elsewhere in slice:** the money figures in `.revenue-table` (per-product Gross column) do not have this problem — that table shares one grid via `<table>`/`<td class="num">`, so its column is genuinely shared and right-aligned consistently.

### 2. Per-product Gross figures are not thousands-grouped, unlike the two headline totals on the same screen
**What I saw:** the verdict ("You grossed $66,334.71…") and the month-strip figures both use `moneyGrouped()` and show commas. The per-product table's Gross column (line 966, `money(row.gross)`) deliberately does not: a Booster Pack product's Gross cell read `$4411.80` with no thousands separator, right next to a Copies cell that *does* use `.toLocaleString()` (`320`, would be `1,320` past four digits). The code comment at `Revenue.tsx:961-965` argues this is deliberate ("a comma here would be the only one in a column of otherwise-plain figures").
**Where:** `app/src/Revenue.tsx:960-966`.
**Severity:** nit. The stated rationale is about visual noise in a column of "three or four digit" figures, but $4,411.80 already needs four digits before the decimal on a real product in this exact store, and any collectible booster-box or ETB line that outsells this row (a realistic case for a Sales screen) will read as an ungrouped five- or six-digit dollar figure — exactly the case `moneyGrouped()`'s own doc comment says a comma earns its keep ("the difference between reading it and counting zeros"). The Copies column right beside it is already grouped, so within one row the reader has to apply two different digit-grouping rules depending on which column they're looking at.
**Fix:** either group the Gross column too (simplest, and consistent with the Copies column beside it), or keep it plain but drop the grouped Copies column to match — right now the row itself is internally inconsistent about whether big numbers get commas.

### 3. "Last sold" date format is un-padded and screen-local, unlike every other date treatment in the slice
**What I saw:** the product table's "Last sold" column uses a bare `row.last.toLocaleDateString()`, producing `5/29/2026` — single-digit month, no leading zero, US locale ordering with no punctuation guard. `Pricing.tsx`'s `runDay()` formats the same kind of fact as `Sep 9` (month name, no year); `Revenue.tsx` itself defines a `pad2()` helper and a zero-padded ISO formatter for its own date-range fields two hundred lines above this cell, but does not reuse it here.
**Where:** `app/src/Revenue.tsx:967` (`<td>{row.last.toLocaleDateString()}</td>`), compare to `pad2`/`formatShort` used elsewhere in the same file (`Revenue.tsx:168, ~700s`) and `Pricing.tsx`'s `runDay()`.
**Severity:** nit. A locale date with variable digit width in a right-adjacent-to-numbers table column means the column's visual width jitters row to row (`5/2/2026` vs `12/13/2026` differ by 4 characters), and it is the only date on this screen (or in this slice) not expressed through a shared, padded formatter.
**Fix:** reuse `formatShort`/`pad2` (or the same relative/absolute convention `Pricing.tsx` and `ProductHistory.tsx` already use) for this cell.

### 4. Verdict sentence uses a display typeface at regular (400) weight
**What I saw:** `.revenue-verdict-said` ("You grossed $66,334.71 over 6 months, across 748 orders.") is set in `--bn-font-display` (Manrope) at 18px, but the rule declares no `font-weight`, so it renders at the browser default 400 — confirmed live (`fontWeight: "400"`). Every other headline-weight use of the display face in this kit (`.bn-title` 800, `.bn-empty-title` 700, `.bn-section-title` 700, `.codes-task-title` 700) is bold or heavier; Manrope's regular cut was designed as body-adjacent weight, not a headline weight, and next to those it reads visibly thinner than the rest of the product's "this is the important number" moments.
**Where:** `app/src/Revenue.css:27-32`.
**Severity:** nit. This may be a considered choice (the verdict is a sentence, not a numeral, and treating it quietly could be intentional), but it is the single largest piece of text on the screen's most important line and is the only "verdict" style in the kit that is not bold.
**Fix:** if the quieter treatment is not deliberate, add `font-weight: 700` to match the rest of the display-face vocabulary.

## What I could not check

- **Screenshots.** As with the other three files in this review, the Browser pane refused to composite frames this session ("the Browser pane is not displayed"), so every finding above comes from live CSSOM measurement rather than a visual pass. I did not get a whole-page look at composition, only at the specific elements queried.
- **Filters and cross-filtering** (D217's month-row-as-filter, the search box actually typed into, sort-by-column click behaviour) — the search input and sort buttons were located and measured (dimensions, positions) but not exercised; I did not click a sort header or type a query, so I cannot report on the resulting re-sort/re-filter visuals, only on the resting control geometry.
- **Custom date range picker** (the `revenue-range` fields, "Custom" period option) — not opened.
- **Market-compare cells** (`revenue-market`, `revenue-market-delta`) — this store's current products payload returned no market-compare data (`prices === null` path), so the compare column, its "no reading" state, and its delta/age styling were read from source only, not seen live.
- **Empty state** (a period with zero orders) — not reached; this store has continuous sales across the whole visible range.
- **Loading state** — not caught; the fetch resolved before it could be measured.
- **390px / phone width** — out of scope per the brief, not checked.
