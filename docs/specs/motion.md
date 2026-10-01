# Motion — the app's motion language, and a review of every animated surface

This spec answers DEBT80 (no motion designer has reviewed the app's animation). It holds the
inventory of every animated surface, the recordings, the principles, the token set those
principles imply, the findings and the proposals. The owner picks the proposals. Nothing in this
file is built yet. DEBT80 stays open until the picked changes land.

`docs/specs/motion-trigger.md` is a different subject: the camera's motion trigger, not animation.

## STATUS

- Inventory, recordings, findings and proposals: written.
- Product code: not changed. Every change below is a proposal.
- DEBT80: open.

## 1. How the recordings were made

Each surface was driven in a headless Chromium at 1440 by 900, against this checkout's own
server and the demo store (`make demo-seed`). Each surface has two recordings:

- **A video at real speed.** `captures/motion/<surface>.webm`. The folder is gitignored, so the
  videos live on the machine that made them.
- **A frame strip.** `captures/motion/<surface>.png`. The page's animation clock runs at a tenth
  of real speed (the Chrome DevTools `Animation.setPlaybackRate` call), and a frame is taken at
  each label's time. The label is real time in milliseconds after the trigger.

The proposals' "before" strips are committed in `docs/specs/motion/`.

Two limits of the method:

- A slowed clock does not slow a JavaScript timer. An overlay's exit is unmounted by a 140 ms
  timer (`kit/index.useLeave`), so a slowed strip cannot show an exit. Exits were read from the
  real-speed video and from the CSS.
- Headless Chromium gives the capture screen no camera frames. The capture flash is a CSS
  animation on one `span.bn-flash`. The recording mounts that same span by hand.

Dark was recorded where colour carries the motion: the sale burst and the theme cross-fade.
Reduced motion was recorded for the sale burst and a route change.

## 2. Inventory

Outside the floors in `base.css`, 382 declarations in 28 sheets name a `transition` or an
`animation`. The sheets hold 55 `@keyframes`. In the TSX, 17 call sites set their own
`animationDelay` or `--delay`, and 8 set `--i` for `.bn-stagger`. They group into 44 surfaces.
"Rec" names the recording in `captures/motion/`. A dash means that the surface was judged from
its CSS and code.

### 2.1 Floors and the shell

| # | Surface | Where | What moves | Rec |
|---|---|---|---|---|
| 1 | Response floor | `base.css`, the control list under "RESPONSE FLOOR" | colour, border, fill and shadow, `--bn-t-fast` `--bn-ease` | nav-hover |
| 2 | Press floor | `base.css`, the `:active` list under "PRESS FLOOR" | `translate: 0 1px`, not eased | button-press |
| 3 | Reduced-motion floor | `base.css`, `@media (prefers-reduced-motion: reduce)` | crushes every duration; three spinners keep turning | sale-burst-reduced, route-change-reduced |
| 4 | Theme cross-fade | `base.css` `html[data-theme-switching]`; `App.tsx` `toggle` (360 ms timer) | six colour properties on every node, `--bn-t-slow` | theme, theme-dark |
| 5 | Route change | `kit.css` `.bn-page` (`bn-page-in`) | the page fades and rises 6px, `--bn-t-slow` `--bn-ease-out`; no exit | route-change |
| 6 | Sidebar fold to rail | `App.css` `.bn-shell` (`grid-template-columns`), `.bn-brand-slot`, `.bn-brand-lockup` children | the column width and the lockup, `--bn-t-slow` | rail-fold |
| 7 | Nav link hover | `App.css` `.bn-nav-link`, `.bn-nav-link .bn-icon` | the pill fades `--bn-t-fast`; the icon springs `--bn-t` | nav-hover |
| 8 | Rail tooltip | `App.css` `.bn-nav-link[data-tip]::after` | fade and nudge, `--bn-t-fast` | — |
| 9 | Command palette | `App.css` `.bn-cmdk`, `bn-cmdk-in`, `bn-cmdk-out` | spring in `--bn-t`, out `--bn-t-fast` | palette |
| 10 | Which-key hint | `App.css` `.bn-whichkey`, `.bn-whichkey-drain` | spring in, a linear drain | — |
| 11 | Offline banner | `App.css` `.bn-banner` | fade `--bn-t` | — |
| 12 | Phone drawer and tab bar | `App.css` `.bn-drawer`, `.bn-tab-link .bn-icon`, `bn-navfade` | sheet from the left; icon spring | — (phone) |

### 2.2 The kit

| # | Surface | Where | What moves | Rec |
|---|---|---|---|---|
| 13 | Button, chip, segment, input | `kit.css` `.bn-btn`, `.bn-chip`, `.bn-seg-item`, `.bn-input` | colour and shadow `--bn-t-fast` | button-press |
| 14 | Busy ring | `kit.css` `.bn-btn[data-busy='true']::after` (`bn-spin`, `--bn-t-spin`) | a loop | — |
| 15 | Check mark | `kit.css` `.bn-check input::before` | spring `--bn-t-fast` | — |
| 16 | Tab underline | `kit.css` `.bn-tab::after` | `--bn-t` `--bn-ease-out` | — |
| 17 | Live dot | `kit.css` `.bn-dot-live` (`bn-pulse`, `--bn-t-pulse`) | a box-shadow ring, a loop | — |
| 18 | Receipt | `kit.css` `.bn-receipt` (`bn-receipt-in`), `.bn-receipt-bar::after` (`bn-drain`) | spring in; a linear drain | — |
| 19 | Skeleton shimmer | `kit.css` `.bn-skeleton::after` (`bn-shimmer`, 1.4s literal); `kit/Page.tsx` loading frames | a sweep, a loop | skeleton |
| 20 | Progress bar | `kit.css` `.bn-progress > span` | width `--bn-t-slow` | — |
| 21 | Menu and pick panel | `kit.css` `.bn-menu`; `kit/data.css` `.bn-pick-panel` (`bn-pop`) | spring in `--bn-t`, out `--bn-t-fast` | — |
| 22 | Scrim | `kit.css` `.bn-scrim` (`bn-fade`, `bn-fade-out`) | fade in `--bn-t`, out `--bn-t-fast` | keys-sheet |
| 23 | Dialog (Modal) | `kit.css` `.bn-dialog` (`bn-dialog-in`, `bn-dialog-out`) | spring scale and rise, `--bn-t-slow`; out `--bn-t-fast` | keys-sheet, keys-sheet-close |
| 24 | Sheet | `kit.css` `.bn-sheet`, `.bn-sheet-left`, `.bn-sheet-bottom` (`bn-sheet-in`, `-up`, `-out`, `-down`) | 24px slide `--bn-t-slow` `--bn-ease`; out `--bn-t-fast` | — |
| 25 | Toast | `kit.css` `.bn-toast` (`bn-receipt-in`), `bn-toast-out`, `.bn-toast-drain` | spring in `--bn-t-slow`; collapse out `--bn-t` | sale-toast |
| 26 | Generic enters | `kit.css` `.bn-anim-in`, `.bn-anim-pop`, `.bn-stagger` | `bn-page-in`, `bn-pop`, 30ms stagger capped at 12 | inventory-rows |
| 27 | Lightbox | `kit/dialog.css` `.inv-lightbox`, `inv-lightbox-in` | fade, then spring the image | — |
| 28 | Crop reveal | `kit.css` `.home-deck-photo.bn-crop[data-cropped='true']` | width and transform `--bn-t-slow` | home-deck |

### 2.3 Screens

| # | Surface | Where | What moves | Rec |
|---|---|---|---|---|
| 29 | Mark sold burst and framed Undo | `CardLocations.css` `.card-locations-sell`, `.card-locations-undo`, `.card-locations-bill` (`bn-sale-bill`); `CardLocations.UndoSaleButton` | hover fill `--bn-t`; 8 bills, 800ms each, 25ms apart | sale-burst, sale-burst-dark, sale-burst-reduced, sale-toast |
| 30 | Card location rows | `CardLocations.css` `.card-locations-row` (`card-locations-row-in`) under `.bn-stagger` | fade `--bn-t` | — |
| 31 | Home deck | `Home.css` `.home-deck-card`, `.home-deck-address` (`home-deck-in`) | three cards rise 14px, `--bn-t-emphasis`, 60/120/180ms; the address springs at 420ms | home-deck, home-entry |
| 32 | Home history foot (ribbon) | `Home.css` `.home-ribbon-blk` (`home-ribbon-grow`, 520ms literal, delay `140ms + n * 70ms`) | each sitting's block grows up | home-foot |
| 33 | Home standing line | `Home.css` `.home-standing-ic-live` (`home-standing-pulse`), `.home-standing-go` | an opacity pulse; an arrow nudge | — |
| 34 | Home spine and stage | `Home.css` `.home-stage`, `Home.tsx` `.home-spine.bn-stagger` | `bn-page-in` | home-entry |
| 35 | Capture flash | `kit.css` `.bn-flash` (380ms literal), mounted by `CaptureScreen` per shot | white at 0.9, fades out | capture-flash |
| 36 | Capture recent strip | `CaptureScreen.css` `.capture-film`, `.capture-undo-list > li` (inline `at * 30ms`, no cap) | `bn-page-in` `--bn-t-slow` | capture-entry |
| 37 | Capture stage and cards | `CaptureScreen.css` `.capture-card`, `.capture-stage`, `.capture-last`, `.capture-halt`, `.capture-carried` | `bn-page-in` and `capture-drop` | capture-entry |
| 38 | Capture live signals | `CaptureScreen.css` `.capture-lamp.is-live .bn-icon` (`capture-blink`, 1.6s literal), `.capture-ring-fill`, `.capture-meter-fill` (160ms literal), `.capture-pauseplay` | a blink, the settle ring, the meter, the pause control moving | — |
| 39 | Review | `ReviewQueue.css` `.review-photo`, `.review-candidates > li` (inline `at * 40ms`, no cap), `.review-refusal` (`rv-shake`), `.review-done-empty` | photo fade, candidate stagger, shake, a drawn check | review-entry |
| 40 | Orders and shipping lists | `Orders.css` `.orders-index > li`, `.orders-order`, `.orders-pick`; `Shipping.css` `.shipping-row`, `.shipping-guide` | `bn-page-in`; staggers of 30ms and `--delay` | orders-entry |
| 41 | Runs | `Runs.css`, `RunPanel.css` `.run-row` (inline 35ms, cap 10), `.runs-stepper-live` (`runs-breathe`), `.runs-quote-money` (420ms literal), `.run-receipt` (`bn-receipt-slip`) | rows, a breathing bar, money rising | — |
| 42 | Fulfiller | `Fulfillment.css` `.ff-*`: 15 enters, `.ff-sheet` (`bn-sheet-up` spring), `.ff-check path` (`ff-draw`, 360ms literal), `.ff-box` (inline `at * 40ms`, no cap) | the whole hand-off screen | fulfillment-entry |
| 43 | Pricing, Sales, Graveyard, Product | `Pricing.css` `.pricing-price.is-flash` (`pricing-flash` on `--bn-t-spin`); `Revenue.css` rows; `Graveyard.css` `.graveyard-row`; `PriceTrend.css` `pricetrend-draw` | rows, a field flash, a drawn line | pricing-entry, revenue-entry, graveyard-entry |
| 44 | Codes (dormant) | `Codes.css` `.codes-stat` (40ms nth-child steps), `.codes-row` (16ms, cap 24), `.codes-lanebar-seg` (90ms steps) | rows and bars | — |

## 3. Principles

Banchi is a work tool. A person uses it many times an hour, often at the rig with a card in one
hand. Motion has four jobs, and only four:

1. **Answer a press.** The control changes on the frame the finger lands. No ease on a press.
2. **Show where a thing came from or went.** A sheet comes from its edge. A row that leaves goes.
3. **Say a state is live.** One loop, one look, for "this is running now".
4. **Mark a rare result.** A sale, a box done. Rare, short, and never in front of the next task.

Everything else is still. Motion that plays on every visit to a screen is a cost, paid each
time, and it must be cheap.

**Speed by role.** Smaller and more frequent is faster.

| Role | Duration | Easing | Today |
|---|---|---|---|
| Press | 0 | none | `translate` floor. Correct. |
| Hover and focus response | 120ms | standard | `--bn-t-fast` `--bn-ease`. Correct. |
| Exit of anything | 120ms | accelerate (out of view, fast at the end) | `--bn-t-fast` `--bn-ease`. Easing is wrong. |
| Small enter (menu, popover, tooltip, row) | 200ms | decelerate | `--bn-t` `--bn-ease-out`. Correct. |
| Large enter (page, sheet, dialog, toast) | 240 to 320ms | decelerate | `--bn-t-slow`. Easing is mixed. |
| Layout change (rail fold, a bar's width) | 240ms | standard | `--bn-t-slow`. Slightly long. |
| Emphasis (a rare result) | at most 600ms in all | spring for one element, decelerate for many | the sale burst runs about 975ms. |
| Live loop | 1.8s | ease-in-out | four different loops. |

**Spring is for one small thing that pops.** A check, a chip, a receipt. A spring overshoots, so
it reads as "landed". It does not suit a large surface: a dialog that overshoots its centre is
a page that wobbles. Sheets use `--bn-ease`, dialogs use `--bn-ease-spring`, and they are the
same role.

**Distance is small and one size.** An enter rises 6px. Today the same role rises 4, 6, 8, 10 or
14px across sheets.

**A list staggers one way.** 30ms a row, capped at 12 rows (`--bn-stagger`, `--bn-stagger-cap`).
The 13th row and after arrive with the 12th. A stagger with no cap grows with the data, so a
long list waits seconds.

**Nested enters do not add.** A page already fades and rises as one. A row inside it that also
rises makes two motions at two speeds. Inside a page that enters, a list fades only, or does not
move.

**Reduced motion keeps meaning, loses travel.** An enter becomes a short fade or nothing. A
loop that says "busy" keeps turning. A burst is not drawn. Today's floor does this. Keep it.

**A JavaScript timer never copies a duration.** A timer that waits for an animation reads the
token or waits for `animationend`.

## 4. The token set this implies

Kept names stay. Each change maps to today's token.

| Token | Value | Change | Reason |
|---|---|---|---|
| `--bn-t-fast` | 120ms | keep | hover, exit |
| `--bn-t` | 200ms | keep | small enter |
| `--bn-t-slow` | 320ms | keep the name; 280ms is the proposed value | a page, sheet or dialog enter; one notch faster for a tool used all day |
| `--bn-t-layout` | 240ms | add | the rail fold and a bar's width move layout. Today they use `--bn-t-slow`. |
| `--bn-t-draw` | 480ms | keep | a line or bar drawing in |
| `--bn-t-emphasis` | 600ms | keep, and make it the ceiling of a whole emphasis, delays included | the Home deck and the sale burst both pass it today |
| `--bn-t-pulse` | 1.8s | keep, and make it the only live loop | `capture-blink` (1.6s), `runs-breathe` and `home-standing-pulse` read their own numbers |
| `--bn-t-spin` | 0.7s | keep, for busy rings only | `pricing-flash` uses it as a flash length. `.review-spinner` writes 0.7s by hand. |
| `--bn-t-shimmer` | 1.4s | add | three sheets write `1.4s` by hand |
| `--bn-t-flash` | 200ms | add | the capture flash writes 380ms by hand |
| `--bn-ease` | (0.2, 0, 0, 1) | keep | standard |
| `--bn-ease-out` | (0, 0, 0.2, 1) | keep | enter |
| `--bn-ease-in` | (0.4, 0, 1, 1) | add | exit. Every exit uses `--bn-ease` today. |
| `--bn-ease-spring` | (0.34, 1.4, 0.44, 1) | keep, for small pops only | |
| `--bn-rise` | 6px | add | one enter distance |
| `--bn-stagger`, `--bn-stagger-cap` | 30ms, 12 | keep, and make them the only stagger | |

Keyframes that duplicate a kit keyframe go: `rv-verdict-in` is `bn-page-in`. `rv-row-in`,
`rv-photo-in`, `card-locations-row-in`, `capture-fade` and `codes-fade` are `bn-fade`.
`codes-row-in` and `graveyard-row-in` are `bn-page-in` at 4px.

## 5. Findings

Verdicts: **keep**, **adjust** (same motion, other numbers), **replace** (other motion for the
same job), **remove**.

| # | Surface | Verdict | Proposed change | Reason |
|---|---|---|---|---|
| 1 | Response floor | keep | — | Recorded: the nav pill eases in over 120ms and the cursor never waits. |
| 2 | Press floor | keep | — | Recorded: the 1px dip lands on the first frame. |
| 3 | Reduced-motion floor | keep | — | Recorded: a route change is instant and the sale draws no bills. The spinner exception is right. |
| 4 | Theme cross-fade | replace | One View Transition cross-fade of the whole page, 200ms, in place of six transitions on every node. The 360ms timer goes. | Recorded: the page passes through a flat grey at about 60ms, darker panels on a mid-grey ground. Every node runs six transitions at once. The 360ms timer is a copy of `--bn-t-slow`. |
| 5 | Route change | adjust | `--bn-t-slow` to 280ms. Inner lists inside the page stop rising. | Recorded: the page is readable by 120ms and settled by 260ms. Parts arrive at three speeds (list, photo, pane), because inner enters run on top of the page's own. |
| 6 | Rail fold | adjust | `--bn-t-layout` (240ms). | Recorded: the content column reflows on every frame for 320ms; the card photo grows as it goes. Shorter makes the reflow pass faster. |
| 7 | Nav link hover | keep | — | Recorded: the icon spring and the pill fade agree. |
| 8 | Rail tooltip | keep | — | |
| 9 | Command palette | keep | — | Recorded: in place by 120ms. A spring on a small panel. |
| 10 | Which-key hint | keep | — | |
| 11 | Offline banner | keep | — | |
| 12 | Phone drawer | keep | — | Phone specs are off (DEBT77). Not recorded. |
| 13 | Buttons and fields | keep | — | |
| 14 | Busy ring | keep | — | A loop that means busy. |
| 15 | Check mark | keep | — | |
| 16 | Tab underline | keep | — | |
| 17 | Live dot | keep, and make it the one live look | `capture-blink`, `runs-breathe` and `home-standing-pulse` become `bn-pulse` on `--bn-t-pulse` | Four loops say "live" four ways, at 1.6s and 1.8s, by ring and by opacity. |
| 18 | Receipt | keep | — | |
| 19 | Skeleton | adjust | `--bn-t-shimmer`. Each screen's skeleton takes the shape of what replaces it. The swap fades over `--bn-t-fast`. | Recorded on Sales: five list bars give way to a chart, cards and a breakdown. Every block moves at the swap. |
| 20 | Progress bar | adjust | `--bn-t-layout` | Width is layout. |
| 21 | Menu, pick panel | keep | — | |
| 22 | Scrim | keep | — | |
| 23 | Dialog | adjust | `--bn-ease-out` in place of the spring. Exit on `--bn-ease-in`. | The spring curve goes past its rest size before it settles; the keys dialog's 40ms frame shows it mid-scale. A sheet, its sibling, does not overshoot. |
| 24 | Sheet | adjust | Exit on `--bn-ease-in`. | An exit eases out of view; `--bn-ease` slows it at the end, where nobody is looking. |
| 25 | Toast | keep | — | Recorded: in place by 120ms, away from the work. |
| 26 | Generic enters, `.bn-stagger` | keep, and make it the only stagger | see proposal P2 | |
| 27 | Lightbox | keep | — | |
| 28 | Crop reveal | keep | — | |
| 29 | Mark sold burst and Undo | adjust | see proposal P1 | Recorded: about 975ms; bills cross the position bar above; the Undo tooltip and the toast appear at the same time. |
| 30 | Card location rows | keep | — | Fade only, under `.bn-stagger`. |
| 31 | Home deck | adjust | see proposal P3 | Recorded: the hero is empty for 120ms and still moving at 820ms, on every visit to Home. |
| 32 | Home ribbon | adjust | Cap the delay (`min(n, 12)`), or grow the ribbon as one sweep left to right over `--bn-t-draw`. | `140ms + n * 70ms` has no cap. Forty sittings put the last block at about 2.9s. The demo store has one sitting, so the recording does not show it; the owner's real count is unmeasured. |
| 33 | Home standing line | adjust | `bn-pulse`, see 17 | |
| 34 | Home spine and stage | keep | — | |
| 35 | Capture flash | adjust | see proposal P5 | Recorded: 0.9 white, mostly gone by 180ms, gone at 380ms. |
| 36 | Capture recent strip | adjust | `.bn-stagger` | Its stagger has no cap. |
| 37 | Capture stage | keep | — | Recorded: settled by 300ms. |
| 38 | Capture live signals | adjust | `capture-blink` becomes `bn-pulse`; the meter's 160ms becomes `--bn-t-fast` | literal numbers |
| 39 | Review | adjust | Candidates on `.bn-stagger`. `.review-spinner` reads `--bn-t-spin`. | Recorded: photo and candidates are good. The candidate stagger has no cap. |
| 40 | Orders and Shipping | adjust | `.bn-stagger`; Shipping's guide steps of 60ms become the stagger | Recorded: settled by 200ms. Two stagger idioms on one screen (`--i` and `--delay`). |
| 41 | Runs | adjust | `.bn-stagger` (35ms, cap 10 today); `runs-breathe` becomes `bn-pulse`; 420ms becomes `--bn-t-slow` | literal numbers and a second live loop |
| 42 | Fulfiller | adjust | `.ff-box` and `.ff-card` on `.bn-stagger`; `ff-draw` on `--bn-t-draw` | `.ff-box` has no cap. The feel does not change: the Fulfiller's floors are `docs/DESIGN.md`'s. |
| 43 | Pricing, Sales, Graveyard | adjust | `pricing-flash` on its own token, not `--bn-t-spin` | A flash that borrows the spinner's period changes when the spinner does. |
| 44 | Codes (dormant) | adjust when the feature wakes | `.bn-stagger` | Three stagger cadences on one screen. Dormant: no work now. |

**Defects found.** None blocks input. None moves layout under a pointer: every enter uses
`transform` or `opacity`, and the press is `translate`. Two motions run long for how often they
play (29, 31). One stagger family grows with the data (32, 36, 39, 42). The rest are drift:
literal numbers, four live loops, and two curves for one overlay role.

**The tally.** 44 surfaces: 24 keep, 19 adjust, 1 replace, 0 remove.

## 6. Proposals for the owner

Each proposal is one change. Pick any. None depends on another.

### P1. A shorter, calmer sale

**Before:** `docs/specs/motion/sale-burst-light.png`, `docs/specs/motion/sale-burst-dark.png`;
video `captures/motion/sale-burst.webm`.

Eight bills fly up and out of the Undo frame for about 975ms. In light, the green bills are pale
on a pale ground. They cross the position bar above the button. At the same moment the Undo's
tooltip opens over them (focus moves to Undo), and the toast rises in the corner. Three things
start at once, and the operator's next press is often the next card's Mark sold.

**After:** five bills, each 480ms (`--bn-t-draw`), 20ms apart, so the burst ends near 560ms and
inside `--bn-t-emphasis`. They rise less (about 40px) and stay inside the action row. The bill
colour reads `--bn-ok` at full strength in light. The tooltip waits until the burst ends. The
frame and the toast do not change.

### P2. One stagger for every list

**Before:** no recording shows it, because the demo store's lists are short. The arithmetic is
the evidence. Seventeen call sites set their own delay: 16, 25, 30, 35, 40, 70 and 90ms a step.
Outside the dormant Codes screen, five have no cap: the `CaptureScreen` recent strip, `RunFiles`,
two `ReviewQueue` lists and the `Fulfillment` boxes. The Home ribbon has no cap either.

**After:** every list reads `.bn-stagger` and `--i`. 30ms a row, cap 12, so no list waits more
than 360ms for its last row. The Home ribbon grows as one sweep over `--bn-t-draw`.

### P3. The Home deck plays once a sitting

**Before:** `docs/specs/motion/home-deck.png`; video `captures/motion/home-deck.webm`.

On every visit to Home, the hero is empty for 120ms. Then three cards rise 14px over 600ms each,
and the address pill springs in at 420ms. The deck is still moving at 820ms. Home is the screen
a person returns to between every task.

**After:** the full deck plays on the first Home visit of a browser session. Later visits show
the deck at rest, with a 200ms fade only. The rise drops to `--bn-rise`. The whole entry ends
inside `--bn-t-emphasis`.

### P4. The theme flips in one composited fade

**Before:** `docs/specs/motion/theme-crossfade.png` (real time, not slowed); video
`captures/motion/theme.webm`.

At about 60ms the whole page is a flat mid-grey: dark panels on a grey ground, text at low
contrast. It takes about 260ms to reach dark. Every element on the page runs six colour
transitions at once, and a 360ms timer removes them.

**After:** `document.startViewTransition` takes one snapshot of the old theme and fades it out
over the new one in 200ms. No colour passes through grey, because the two themes are drawn
whole and blended as images. No per-node transitions run. Where the API is missing, or under
reduced motion, the theme flips in one frame.

### P5. A lighter capture flash

**Before:** `docs/specs/motion/capture-flash.png`; video `captures/motion/capture-flash.webm`.

Each shot whites out the viewfinder at 0.9 opacity and fades over 380ms. The rig fires every
610ms (`storeHistory.RIG_CEILING_PER_HOUR`), so the frame is bright for a large part of every
cycle. The operator watches this frame to see the card settle.

**After:** peak 0.6, over `--bn-t-flash` (200ms). It still says "taken" on every shot. The card
is back in view well before the next one.

### Not a proposal yet: the skeleton swap

`docs/specs/motion/skeleton-swap.png` shows Sales' skeleton (five list bars) give way to a chart
and a card grid. A skeleton that does not match its screen moves every block at the swap. The
fix is per screen, so it waits for the owner to name the screens that matter.
