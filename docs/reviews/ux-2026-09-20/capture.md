# Capture (`#/capture`)

Widths looked at: 1440, 1280 (DOM measurement via `getBoundingClientRect`; Browser pane was
hidden for this whole screen's pass, so no direct screenshot at either width this round —
see "What I could not check"). One screenshot from earlier in this same session (dark, 1440,
before the pane hid) is used for qualitative confirmation only.
Themes looked at: dark only, confirmed by `data-theme` and computed `background-color`. Light
theme not reached this pass — UNKNOWN.
Store state: no camera open, no box picked (the owner's real "no box yet" state) — I did not
press "Open the camera" or "Pick a box" (would start a capture flow / write).

## Findings

1. **Header title and icon are pixel-perfect on their shared baseline.**
   Measured: `.capture-title` occupies y=33, h=30.8 (center 48.4); its icon occupies
   y=38.4, h=20 (center 48.4) — 0px difference. No defect; recorded for completeness.

2. **The three-column capture layout (RUN/undo/stack/rig cards, camera stage, LAST CAPTURE)
   uses a single consistent 16px column gap and 12px vertical card gap at both 1440 and 1280,
   with no horizontal overflow at either width.**
   Measured at 1440: left column x=268 w=300, gap to stage 16px (584−268−300), stage w=488,
   gap to last-capture panel 16px (1088−584−488), last-capture w=320. Vertically: run-card
   ends at y=477.7, next card starts 489.7 (12px gap); repeats identically down the column
   (12px, 12px). At 1280: same structure, columns scale to 272/434/250 with the same 16px
   gaps, `scrollWidth − clientWidth = 0` (no overflow). No defect found in the grid itself.

3. **Single-letter keyboard hints in the left rail (`B`, `S`, `H`, `R`, `F`, `G`, `V`, `O`,
   `T`) are visually consistent with each other (10px, weight 600, same muted color,
   `capture-k` modifier class) — except the `C` hint on the primary "Capture card" button,
   which is 12px and dark-on-accent instead of 10px and muted.**
   This is NOT a bug: the `C` kbd sits inside `.bn-btn-primary`, which has its own documented
   kbd override (`app/src/kit.css:217`, `.bn-btn-primary .bn-kbd`) for contrast against the
   accent fill. Recorded because it was the one outlier in an automated sweep and is worth a
   later reviewer not re-flagging it.

4. **"New section" button's kbd hint (`S`) reads as `New sectionS` when read as flat text,
   but this is a `textContent` artifact of my own extraction script, not a real spacing
   defect** — the button and its kbd are separate flex children with a normal gap. Checked
   and dismissed; recorded so a later pass does not re-raise it from the same false trail.

5. **Sidebar collapses at some point after mount without the page reloading (see `shell.md`
   finding 1 for the root cause).** On Capture specifically this shifts the RUN/stack/rig
   column's `x` from 268 (expanded, 236px sidebar) to a narrower left inset (64px rail) with
   no other layout change — the column widths adjust and nothing overlaps in either state, so
   the capture layout itself tolerates the bug gracefully. Filed at shell.md as the primary
   location.

## What I could not check

- **No screenshot this pass.** The Browser pane was hidden for the entire Capture screen
  investigation; every number above comes from `getBoundingClientRect`/`getComputedStyle`,
  which cannot see a purely visual defect (a photo that fails to decode, a color that reads
  wrong to the eye, a font that fails to load and silently falls back). One screenshot exists
  from earlier in this conversation (before the pane hid) showing the "no box yet" state at
  1440 dark, which is consistent with the measurements above, but I did not re-verify it
  pixel-by-pixel against a fresh render.
- **Light theme**: not reached at all this pass. UNKNOWN.
- **1280 width was measured but not screenshotted.** The layout numbers show no overflow and
  proportional scaling, but I did not visually confirm the "LAST CAPTURE" panel's photo
  placeholder or the RIG panel's dropdowns still look correct at the narrower 250px column
  width — only that the box models don't collide.
- **The actual camera view, capture button in an active/busy state, the halt/undo flow, the
  set-hint/rarity/finish claim rows in their "answered" state, and the RIG panel's dropdown
  menus open** — none of these were exercised, since doing so risks a real capture/write
  against the owner's live store, which is fenced off. UNKNOWN for all interaction states
  beyond the idle "no box yet" screen.
- **Keyboard-hint chip colors and sizes in light theme** were not measured.
