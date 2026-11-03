# Capture Recent rail, hand-fed mode: design notes

Lane kind: informed. Mockup: `capture-recent-rail.html`. Component: `CaptureScreen` draws the rail.
`railList` builds the list and `UndoCell` draws each tile. `writeTile` labels each tile by its rank. The
CSS lives in `.capture-undo-list`, `.capture-undo-still` and `.capture-undo-spacer`. Hand-fed means the
dispenser is not dealing (`useDealer` state is not `dealing`).

This is a performance lane, so nothing new is drawn. The page fixes the rail's visible contract, and the fix
must leave that contract unchanged. The mockup copies the rail's CSS rule for rule. Its Figures panel
measures that copy live in the browser, and the expected figures come from the same rules.

Deep links: `#s=5`, `#s=20`, `#s=60`, `#s=far`, `#s=removed`, `#s=capped`. Add `&w=820` and `&t=dark`.
With no `t`, the page follows `prefers-color-scheme`. `&h=capped` hides the refused state.

Devices: `layout.py devices` prints `unknown` for this repo, so the page draws the brief's sizes: 1440
and 820, light and dark. The two other dark palettes swap tokens only, so the page does not draw them.

## The contract

1. **Tile and grid at 1440.** The rail sits in the 340px column. It has 5 columns, each tile is 56 x 99.6
   (9:16), and the row pitch is the tile height plus 6px. The rail box caps at 360px tall and scrolls
   inside itself, about 3.4 rows in view. Measured on the copied rules:

   | captures | rows | scroll extent | rail box |
   |---|---|---|---|
   | 5 | 1 | no scroll | 109.6 |
   | 20 | 4 | 426.2 | 360 |
   | 60 | 12 | 1270.7 | 360 |

   Gain: the figures are what the CSS builds today. Pick: keep all of them.
2. **One row at 820.** Every width at 1279px and under shows one horizontal row of 56px tiles with
   16px gaps, about 9.7 tiles in view. The rail box is 119.6px tall. The scroll extent is 352px (no scroll), then 1432px at 20
   captures and 4312px at 60. Pick: keep.
3. **The newest tile lands at rank 0.** It sits top left at 1440 and leftmost at 820, with the accent
   `U` key. A capture moves every older tile one cell, with no transition, as today. Only the new
   tile fades in (`bn-page-in`). A tile at rank 15 or past never animates (`.capture-undo-still`).
   Pick: keep. Loss: none.
4. **The scroll extent is the whole sitting from the first frame.** At 60 captures the scrollbar
   thumb measures 60 tiles, not 15. If the fix uses a spacer, that spacer must equal the tiles it
   stands for, as D316's spacer does today. Pick: keep.
5. **The rows never drop during a sitting.** `stripFloor` ghost cells hold the height after a
   single-card remove (`#s=removed`: 17 tiles, 3 ghosts, 4 rows). Pick: keep.
6. **The reserved lines stay.** These lines keep their space in hand-fed mode: the head ("Recent",
   "N recent", "U undoes the newest"), the dispenser line (`.capture-film-paused`, empty) and the
   undo note. Pick: keep.
7. **Every tile of the sitting is a real row.** Tab reaches it in rank order, and a screen reader
   counts N items. A scroll shows its photo, never a blank tile. `content-visibility: auto` keeps a
   tile in the tab order and the accessibility tree. A spacer does not.
   Two specs depend on real rows. `app/tests/capture-undo.spec.ts` counts 36 rows after 36
   captures and presses capture 24. `app/tests/capture-freeze.spec.ts` uses `tiles.nth(20)` after 26
   captures. The builder keeps both specs green unedited, or re-points them with a reason
   (`outcomes-tests-are-statements`). Pick: keep.
8. **A tile far down is live before it can be read or pressed** (`#s=far`). When it scrolls in or
   takes focus, its key shows rank + 1, and its overlay shows "Undo 21". Its accessible name is
   "Undo 21 captures, back to Box 5, Section 1, Card 40". Enter or a press undoes exactly 21 cards,
   newest first (`undoBack`, D164). The trash button removes that card alone
   (`removeCardInPlace`). Both are disabled while a capture or an undo is busy. The spec
   capture-freeze, "a tile far down the rail carries its live Undo label when it scrolls in or takes
   focus", asserts this. Pick: keep.
9. **Nothing moves unless the person moves it (D313).** Across one capture, the rail's top, the
   Stack card and the Rig card hold still. `app/tests/stability.spec.ts` asserts the loading case on
   Capture at 1440 and 820, and its case S20 asserts the undo note's slot. The `past 15 cards` case
   in capture-freeze asserts the list height and everything below it across Stop. Pick: keep.
10. **Unmeasured: a capture while the rail is scrolled down.** Scroll anchoring may hold the view
    while the tiles shift by one cell, or the view may drift. Nobody has measured today's behaviour.
    The fix keeps it, whatever it is. The design reviewer measures it on main and on the branch.
11. **Named residue: the scrollbar gutter.** At 1440 a classic scrollbar (Linux, Windows) takes its
    gutter from the list's width once the rail scrolls, so the tiles narrow by a few pixels at the
    16th capture, the first fourth row. An overlay scrollbar (macOS, headless) takes none. This is today's behaviour, and
    the mockup reports it live. The fix keeps it. Changing it is out of scope.

## The one refused picture

12. **The newest 15 and a spacer in hand-fed mode** (`#s=capped`, hide with `&h=capped`). This
    extends D316's dealing rule to hand-fed mode as it stands. Gain: the cost per capture is flat
    with the least code. Loss: cards 1 to 45 cannot be reached by press, Tab or a screen reader,
    and hand-fed mode has no "dealing ends" to load them back in. Pick: no.
    Departs from: D164 (undo covers the whole sitting), its amendment "the capture strip lists
    every card of the sitting", and `docs/specs/undo.md` UN-1 ("a 36-shot case reaches capture 24
    both ways"). This applies only if the fix ships this picture. A fix that keeps item 7 departs
    from nothing.

## Ruling check

No decision rules that hand-fed mode must keep every tile live in the DOM. D164 (amended) and UN-1
rule that every card is listed and reachable. D313 rules the space and the motion. D316 rules only
dealing mode. `scripts/decision-context.py --check app/src/CaptureScreen.tsx` names no other ruling
on the rail's mechanism.

## Found outside scope

13. `docs/DESIGN.md`, the capture-undo paragraph ("The control is a stack of ten"), still says "the
    session's ten most recent captures into the current box". D164's amendment made that the whole
    sitting, across drawers. That file is outside the design folder, so a builder must fix it.
