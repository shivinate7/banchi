# Codes (`#/codes`)

**Coverage:** 1440px and 1280px, light and dark theme. State seen: **empty only** — this store carries zero code-card entries, so `Codes.tsx` renders its minimal "No codes on file yet" empty state and never mounts the pile/tasks/ledger (confirmed live: `.codes-pile`, `.codes-tasks`, `.codes-ledger` are all absent from the DOM when `ledger.total === 0`). The populated ledger, the pile hero, the three task cards, the lots table and every sheet were reviewed from source only (`Codes.tsx`, `Codes.css`) and are flagged below as unverified. Measurements via `getComputedStyle`/`getBoundingClientRect` (screenshots unavailable this session).

## Findings

### 1. Empty state — clean
**What I saw:** header ("Codes" / "Read, tier, and hand off code cards."), a `Reload` icon button (34×34, matches `--bn-control-h`) and a `Read a box` primary button (127×34) at the top right with an 8px gap between them (`--bn-2`, correct), and a single `bn-panel codes-empty` block holding the kit's standard `EmptyState` (qr icon, 18px/700 title, 14px/400 `--bn-ink-3` body, one `Go to capture` primary action). No horizontal overflow at either 1440 or 1280 (`scrollWidth === clientWidth` at both). No layout, spacing, token, or contrast defect found in this state in either theme.
**Severity:** n/a — recorded as a clean baseline, not a finding.

### 2. "Go to capture" is a `<button onClick>`, not an `<a href>` — checked, and it is the app's established convention
**What I saw:** the empty state's CTA fires `window.location.hash = '#/capture'` from a `<Button>` (real `<button>` element) rather than an anchor, which on its own would mean no hover-preview of the destination and no cmd/middle-click-to-open-in-new-tab. I checked whether this is a Codes-specific inconsistency against the rest of the app: the exact same `onClick={() => (window.location.hash = '#/capture')}` pattern on a `<Button>` appears in `BoxBrowse.tsx` (three call sites), `CaptureScreen.tsx`, and `Home.tsx` for the identical "go to capture" action — while genuinely link-like destinations elsewhere (`#/inventory?box=…`, `#/runs?run=…`) do use `<a href>`. This is a consistent, repo-wide convention for this specific action, not a one-off — recorded as cleared after cross-checking, not a defect.
**Severity:** n/a (cleared).

### 3. Two independent hard-coded hatch patterns for "unclaimed," not tokenised
**What I saw:** the diagonal-stripe treatment used to mark an "unclaimed" lane is written twice, with two different pitches, as literal `repeating-linear-gradient()` values rather than a shared class or token: `.codes-lanebar-seg.is-unclaimed { background: repeating-linear-gradient(-45deg, var(--bn-warn) 0 4px, transparent 4px 8px), var(--bn-warn-tint); }` (the 14px-tall lane bar) and `.codes-legend-item.is-unclaimed .codes-legend-dot { background: repeating-linear-gradient(-45deg, var(--bn-warn) 0 2px, transparent 2px 4px), var(--bn-warn-tint); }` (the 10px legend dot). The two pitches (4px/8px vs 2px/4px) are proportional to the two elements' sizes, which reads as a deliberate, sized-correctly choice rather than a mismatch — I could not fault the output, only note that the same visual idea is authored twice by hand with no shared definition, so a future change to the "unclaimed" texture (angle, colour, density) has two places to update and no reader that checks they stay in step, unlike this repo's usual `--bn-*` token discipline.
**Where:** `app/src/Codes.css:227-229` and `app/src/Codes.css:236`.
**Severity:** nit. Not a visible defect today; a maintainability observation given the file's own stated design ("Every colour is a token") — the colours *are* tokens (`--bn-warn`, `--bn-warn-tint`), but the pattern geometry itself is duplicated free text.
**Fix:** express the smaller dot's gradient as a `scale()` of the bar's, or pull the angle/stop-width pair into one shared rule parameterised by element size, so the two can't silently drift apart.

## What I could not check

- **The pile / hero** (`.codes-pile`, `.codes-stats` six-tile figure row, the lane bar with real proportions, "By product" column, D218 dot-joined facts) — never rendered, because this store has zero code-card entries. All of `Codes.css`'s largest, most figure-dense block (lines 139-269) is unverified live.
- **The three task cards** (`.codes-tasks`, hover lift `translateY(-2px)`, icon scale on hover, press state) — never rendered; not exercised.
- **The ledger table** (`.codes-ledger`, tabs, search, filter chips, the entries/lots table, sortable columns, masked/shown code strings, `.codes-code.is-odd` warn-underline treatment, photo links) — never rendered. This is the screen's actual body per its own file header comment ("the ledger is the body") and is entirely unverified in this session.
- **Duplicate-code banner and the inline product-fix row** (`.codes-fix`, `.codes-dups`, `.codes-banner`) — never rendered; these only appear when the ledger holds specific problem states.
- **Any sheet** (read/hand-off/reconcile forms opened from a task card or a row) — none opened; this store's empty ledger gives no entry point to reach one without pressing a control that reads a box, which is outside this review's fence in any case (reading a box is free per the repo's own docs, but doing so would write real ledger state to the owner's store, which this review does not do).
- **Loading state** (`.codes-loading` skeleton) — not caught; the initial fetch resolved before it could be measured, and reload was not pressed repeatedly to try to catch it mid-flight.
- **The "could not be read" failure state** (`.codes-unreadable`, `EmptyState` with `icon="alert"`) — not reached; the ledger read succeeded.
- **390px / phone width** — out of scope per the brief, not checked.
- **Screenshots** — the Browser pane returned "the Browser pane is not displayed" for every screenshot/zoom call this session; the one state I could reach was verified by live CSSOM measurement, not a visual pass.

Given how much of this screen's surface area (the pile, the tasks, the whole ledger) was unreachable with this store's data, this file is the weakest-covered of the four in this review. A follow-up pass with a store that has code-card entries — or a fixture — would be needed to review the bulk of `Codes.css`'s roughly 640 lines with the same rigour as the other three screens in this slice.
