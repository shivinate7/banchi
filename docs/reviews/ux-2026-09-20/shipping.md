# Shipping — UX review

**Screen:** `#/shipping` (the "ship" stage of the same Orders/Shipping hub component — drop zone, lane guide tiles, three-lane list, per-order row).
**Checked:** source and CSS in full (`app/src/OrdersShipStage.tsx`, `app/src/Shipping.css`). Live: the hub was on the "pull" (Orders) stage when I reached it and I did not switch to "Shipping" and confirm a populated ship state live before the Browser pane stopped compositing frames — see "What I could not check." All findings below are therefore code-derived and unconfirmed against the live rendered page; I'm marking severity accordingly and this file should be read as lighter-confidence than `inventory.md`, `orders.md`, and `graveyard.md`.

Files read: `app/src/OrdersShipStage.tsx`, `app/src/Shipping.css`, `app/src/tokens.css`, `app/src/kit.css`.

## Findings

### 1. The three-lane grid stays 3-wide right up to 1279px, then drops straight to 2 columns — no observed problem at 1280, but the guide comment reveals the layout was previously broken between 1024 and 1279
**What I saw:** `Shipping.css:290-304`:
```
@media (min-width: 768px) and (max-width: 1279px) {
  .shipping-lanes { grid-template-columns: repeat(2, minmax(0, 1fr)); ... }
  ...
}
```
with a comment explaining that 3 columns below 1280 measured ~210-250px per lane and caused figures to wrap onto a second line, "Inferred" to wrap off the row entirely, and the reason code to wrap onto a third line. The fix already ships (drop to 2 columns below 1280), so this is not a live defect — but it means the exact 1280px boundary this review is asked to check is the boundary where the layout deliberately snaps from 2-wide back to 3-wide. I could not confirm live that 1280 (not 1279) actually gives each of the 3 lanes enough room, because I never got the Ship stage on screen before losing frame compositing. Given the same lane content (a certainty tag, up to 3 figure chips, a mono reason code) needs to fit in ~316px at 1280 (my estimate: (1280 − 236 sidebar − 64 page padding − 32 gap)/3), which is more room than the 1440 layout the comment says works (~340px), this is LIKELY fine — but I want to flag it as the one width in this whole slice where a documented past failure and my required check width are the same number.
**Where:** `app/src/Shipping.css:293-304`.
**Severity:** unknown/nit — flagging for a live check rather than reporting a confirmed defect.
**Fix:** none proposed; re-verify live at exactly 1280.
**Does it recur:** n/a.

### 2. `.shipping-chip-count`'s dimmed color under a collapsed lane is a hand-picked value, and the comment explaining it undercuts its own reasoning at a glance
**What I saw:** `Shipping.css:222-227`:
```
/* A COLLAPSED LANE IS RECESSED, NEVER FADED. The count is the figure this screen exists to
   show; dropping it to the lightest ink took it to 2.4:1 in light. The fold is carried by the
   chevron, the "folded away" line and the ground — not by making the number hard to read. */
.shipping-chip[aria-pressed='false'] { background: var(--bn-surface-2); box-shadow: none; }
.shipping-chip[aria-pressed='false'] .shipping-chip-count { color: var(--bn-ink-2); }
```
This is actually a well-reasoned, well-documented decision (avoiding a contrast failure by using `--bn-ink-2` rather than a lighter ink) — I'm noting it not as a defect but as a POSITIVE pattern that Graveyard's `.graveyard-condition` (see `graveyard.md` finding 3) should have followed and didn't. No action needed here; cross-referencing for the record.
**Severity:** n/a (not a defect).

### 3. `figuresOf()` can return an empty array, and the row still renders `.shipping-figures` as an empty flex container
**What I saw in source:** `OrdersShipStage.tsx:92-98`, `figuresOf()` returns `[]` when a row has no value, no weight, and no item count (all three are nullable and independently omitted "on purpose," per the surrounding comment at lines 89-91, so a fully-unknown row is plausible for the `unjudged` lane specifically). `Shipping.css:261` styles `.shipping-figures { display: inline-flex; flex-wrap: wrap; gap: 6px; }` with no empty-state handling. If `figuresOf(row)` is empty, this renders a zero-height, zero-content flex box — harmless layout-wise (no visible gap since `gap` only applies between children) but means an `unjudged` row with literally no data at all shows nothing where the reader would expect at least a "no data" cue, right next to the `REASON_SAYS` text that already explains why (e.g. `no_value_data`/`no_weight_data`). This is very likely fine in practice since the reason text carries the explanation, but I flag it because I could not confirm live whether this combination (all three figures null) actually occurs in real export data, or whether the router's own logic guarantees at least one figure survives whenever a reason like `no_weight_data` fires (which by definition means weight is absent, but value or item count could still be present).
**Where:** `app/src/OrdersShipStage.tsx:92-98`; `app/src/Shipping.css:261-271`.
**Severity:** nit, unconfirmed live.
**Does it recur:** n/a.

### 4. `.shipping-guide-unjudged` and `.shipping-chip-unjudged` both draw a dashed warning outline with `outline-offset: -1.5px` — consistent between the two, but double-check against the sold-value semantics used elsewhere
**What I saw:** `Shipping.css:91`, `:199` — both correctly use the identical `outline: 1.5px dashed var(--bn-warn); outline-offset: -1.5px;` for the guide tile and the live lane chip. This is good consistency, not a defect — noted only because it's the kind of pair that's easy to let drift and didn't. No action needed.
**Severity:** n/a (not a defect — noted as a healthy pattern, for contrast with the Inventory/BoxOps drift findings in `inventory.md`).

## What I could not check
- **Everything visual on this screen, live.** I never switched the Orders/Shipping hub to its "ship" stage before the Browser pane stopped compositing frames (`screenshot`/`zoom` began failing with "the Browser pane is not displayed, so the page is not compositing frames" partway through the session, and I prioritized the screens I'd already reached). Every finding above is code-derived only. This is UNKNOWN, not clear and not broken, for: the drop-zone empty state, the populated three-lane state, the file-picked state (two file cards), the caveats disclosure, 1280 width, and both themes.
- **Dark theme entirely** — not reached on this screen.
- **The actual TCGplayer export flow** — not exercised (would require dropping/uploading a real file, a write-adjacent action I did not attempt).
- **Whether finding 1's 1280px boundary is actually safe** — flagged as a question, not answered.
- **Whether finding 3's all-null-figures case is reachable with real data** — flagged as a question, not answered.
