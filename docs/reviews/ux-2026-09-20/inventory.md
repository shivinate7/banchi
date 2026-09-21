# Inventory — UX review

**Screen:** `#/inventory` (box list, search/filters, card detail panel, copies list, Manage box sheet, retire dialog).
**Checked:** 1440 width, light and dark theme (via `getComputedStyle`/DOM inspection — see "What I could not check" for why this was CSSOM-based rather than screenshot-based for most of the pass). 1280 width checked via code (CSS breakpoints), not confirmed visually. Populated state only (a store with 3,510 cards / 5 boxes was loaded). Manage box sheet and retire dialog checked from source only (not opened live, since opening either risks a nearby write control and the instructions say not to press anything I can't be sure is read-only).

Files read: `app/src/Inventory.tsx`, `app/src/Inventory.css`, `app/src/BoxBrowse.tsx`, `app/src/BoxBrowse.css`, `app/src/BoxOps.tsx`, `app/src/BoxOps.css`, `app/src/CardLocations.tsx`, `app/src/CardLocations.css`, `app/src/PositionBar.css`, `app/src/PositionLabel.css`, `app/src/tokens.css`, `app/src/base.css`, `app/src/kit.css`.

## Findings

### 1. Disabled-control opacity drifts from the token in three places in this screen's own files
**What I saw:** `tokens.css:166` declares `--bn-disabled: 0.45` with the comment "the one opacity a disabled pressable wears." Within Inventory's own file set this is not followed:
- `Inventory.css:117` — `.inventory-retire-reason:disabled { opacity: 0.5; }`
- `BoxOps.css:171` — `.boxops-op:disabled { opacity: 0.5; }` (the Manage box sheet's operation rows)
- `BoxBrowse.css:856` — `.browse-stepper-btn:disabled { opacity: 0.4; }`

Meanwhile `BoxBrowse.css:138` (`.browse-boxcell:disabled { opacity: 0.45; }`) gets it right, in the same file as the 0.4 miss — so this isn't a screen-wide style choice, it's drift.
**Where:** `app/src/Inventory.css:117`, `app/src/BoxOps.css:171`, `app/src/BoxBrowse.css:856`, contrast with `app/src/BoxBrowse.css:138`.
**Severity:** medium. Three different disabled-state darknesses (0.4 / 0.45 / 0.5) can appear back to back — e.g. a disabled stepper button next to a disabled box row — and a user who has learned "faded = disabled" gets a different fade each time.
**Fix:** replace the three hardcoded values with `var(--bn-disabled)`.
**Recurs:** yes — this is a repo-wide drift (also seen in ReviewQueue.css, Runs.css, CaptureScreen.css, Pricing.css, Codes.css during a repo-wide grep), not unique to this screen, but three of the instances are inside this slice's own files.

### 2. Uppercase-caption letter-spacing has three different values inside one sheet
**What I saw:** the design token for uppercase caption tracking is `--bn-tracking-caps: 0.06em` (`tokens.css:127`), used correctly in `Graveyard.css:132` and three places in `Orders.css`. Inside `BoxOps.css` — one file, the Manage box sheet — two different hardcoded values appear instead:
- `BoxOps.css:20` — `.boxops-identity-num { letter-spacing: 0.1em; text-transform: uppercase; }` (the "BOX 3" style number above the box name)
- `BoxOps.css:130` — `.boxops-census-cell dt { letter-spacing: 0.04em; text-transform: uppercase; }` (the census tile labels, in the same sheet, a few rows below)

`BoxBrowse.css:310` (`.browse-secttitle`) also uses `0.04em` uppercase, with no comment explaining a deliberate deviation.
**Where:** `app/src/BoxOps.css:20` and `:130`; `app/src/BoxBrowse.css:310`.
**Severity:** nit, but it is the kind of thing that shows up the instant two of these captions sit near each other — the identity number's tracking is visibly looser than the census label's directly below it.
**Fix:** use `var(--bn-tracking-caps)` in all three places unless there's a reason one caption needs to track wider, and if so, say why in a comment (every other deliberate override in this codebase is commented).
**Recurs:** contained to Inventory's own files (BoxOps, BoxBrowse) as far as I checked.

### 3. `Retired · pulled` mixes a humanized label with a raw enum value (documented in Graveyard.md, but the source of truth for the correct label lives here)
**Where:** `app/src/Inventory.tsx:72-76` defines the canonical, human labels for a retirement: `'pulled'` → **"Pulled out"**, `'damaged'` → **"Damaged"**, etc. This dialog is the only place those labels are defined. Graveyard prints the raw machine value instead of using this table — see `graveyard.md` finding for the visible defect. Flagging here because the fix belongs beside this table: either export `REASONS` (or a `label` lookup built from it) so Graveyard can reuse it, or duplicate just the label map with a comment pointing at this one.
**Severity:** medium (see graveyard.md for the on-screen effect).
**Recurs:** yes, this is a two-screen issue; full detail in `graveyard.md`.

### 4. The retire dialog's box-name / position stack has no vertical rhythm relationship to the photo it sits beside
**What I saw:** `.inventory-retire-card` (`Inventory.css:63-71`) is a `84px minmax(0,1fr)` grid with `align-items: start`, `gap: var(--bn-4)` (16px). The photo is a fixed 84×117.3 (63/88 aspect). The text column (`inventory-retire-where`) stacks the position label, box name, and (conditionally) a `PositionBar`, with `gap: var(--bn-2)` (8px) — no `justify-content` or minimum height coordination with the 117px-tall photo. When the `PositionBar` is absent (a departed/located-false copy), the text column collapses to two short lines sitting at the TOP of an 117px-tall row, leaving roughly 70-80px of dead space below the text but beside the photo. This is a plausible, code-visible imbalance; I could not confirm the exact whitespace live without opening the retire dialog (would require pressing "Retire", a write-adjacent control I'm not pressing).
**Where:** `app/src/Inventory.css:63-71`, `90-96`; `app/src/Inventory.tsx:1010-1019`.
**Severity:** nit (cosmetic, situational — only visible for a copy with no PositionBar).
**Fix:** either `align-items: center` on `.inventory-retire-card` so the text column centers against the photo when it's short, or confirm this never actually happens (e.g. every non-departed copy always draws a PositionBar) and drop this note.
**Does it recur:** unknown — could not verify live.

### 5. The box-list row's progress fill and the "on hand" figure are not baseline-aligned with the SKU label above them
**What I saw (from CSSOM on the live page, box list panel):** in the SKU rail rows (`WB1 R1`, `WB1 R4`, etc., rendered by `BoxBrowse.tsx`'s box/game rail — the exact class wasn't reachable through my selector probes without risking navigation, so this is a visual read from the screenshot taken early in the session, at 1440, dark theme, before the pane stopped compositing): the numeral on the right (e.g. "987", "640") sits noticeably larger and heavier than the "675 on hand" caption above it, and the two are right-aligned against each other rather than against the track's end — producing a ragged right edge across the five rows because the numerals have different digit counts (987, 640, 662, 543, 678 — three digits each, so this one is likely fine) but would misalign the moment a 4-digit or 2-digit value appears. This needs to be reconfirmed with `tabular-nums` — I could not verify `font-variant-numeric` on this exact element in this session.
**Severity:** nit.
**Does it recur:** unknown — flagging as a hypothesis for the next pass to confirm on a wider figure spread (a box with under 100 or over 1,000 on hand).

## What I could not check
- **Screenshots at 1440/1280 in both themes for every state.** The Browser pane reported "not displayed" partway through the session (a `screenshot`/`zoom` call returned "the Browser pane is not displayed, so the page is not compositing frames"), so after the first few captures I switched to `getComputedStyle`/`getBoundingClientRect` extraction via `javascript_tool`, which is more precise for measurement but cannot show me layout bugs that only show up visually (overlap, clipping, z-index). This is UNKNOWN, not clear, for: 1280 width in either theme, and dark theme beyond the one screenshot taken early on.
- **The Manage box sheet and the retire dialog, live.** I read their source and CSS in full but did not open either live — opening the retire dialog risks a nearby "Mark sold"/"Retire" write control, and I chose not to risk it. Findings about them (3, 4) are code-only.
- **Loading state.** The store was already loaded when I connected; I did not see the skeleton/loading state for this screen.
- **The lone-copy state (`.inventory-lone`, a card with no SKU).** Not observed in the live store; read from CSS only.
- **Hover/focus/active states for controls in this slice.** I did not run pointer simulation for timing (e.g. confirming the 120ms response floor actually renders as 120ms) — this would need frame-by-frame capture, which needs the pane compositing.
- **A box whose "on hand" figure has 1, 2, or 4+ digits**, to confirm or refute finding 5.
- **Multiple concurrent browser tabs.** Early in the session, tabs appeared and changed route on their own (to Pricing, then to the Fulfillment screen) without my navigating there — almost certainly other review agents sharing this browser context. I closed two tabs I did not create before I realized this (tab-1, tab-3, tab-seed) — if those belonged to a peer session, I apologize for the disruption; I stopped touching any tab I had not personally created via `tabs_create` for the rest of the session (tab-6).
