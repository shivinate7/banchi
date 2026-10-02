# Motion — the app's motion language

This spec is the one place that says how the app moves. It holds the roles and the token for
each role. It holds the utilities that give a new screen correct motion. It holds the check
that keeps every surface on those tokens, and the verdict on every animated surface. A motion
review of the whole app produced it. Its findings are built, and the check below keeps them
built.

`docs/specs/motion-trigger.md` is a different subject: the camera's motion trigger, not animation.

## STATUS

- Every finding in section 5 is BUILT, except the per-screen skeleton shapes under finding 19.
  They wait for the owner to name the screens that matter.
- P2 (one stagger), P3 (deck once a sitting), P4 (theme crossfade) and P5 (lighter capture
  flash) are BUILT. P1 (calmer sale) was not picked, so the sale stays as it was. Section 6
  says how.
- The `raw motion` row of `make docs-audit` refuses a raw duration or easing outside
  `app/src/tokens.css`. Its allow list is empty.

## 1. Principles

Banchi is a work tool. A person uses it many times an hour, often at the rig with a card in one
hand. Motion has four jobs, and only four:

1. **Answer a press.** The control changes on the frame the finger lands. No ease on a press.
2. **Show where a thing came from or went.** A sheet comes from its edge. A row that leaves goes.
3. **Say a state is live.** One loop, one look, for "this is running now".
4. **Mark a rare result.** A sale, a box done. Rare, short, and never in front of the next task.

Everything else is still. Motion that plays on every visit to a screen is a cost, paid each
time, and it must be cheap.

- **Spring is for one small thing that pops.** A check, a chip, a receipt. A large surface does
  not overshoot: a dialog that overshoots its center is a page that wobbles.
- **Distance is small and one size.** An enter rises `--bn-rise`.
- **A list staggers one way.** Row i waits min(i, `--bn-stagger-cap`) times `--bn-stagger`. The
  13th row and after arrive with the 12th, so no list waits more than 360ms.
- **Nested enters do not add.** A page rises as one. An entry inside a page fades and does not
  rise.
- **Reduced motion keeps meaning, loses travel.** An enter becomes a fade that ends at once. A
  loop that says "busy" keeps turning, slower. A burst and a flash are not drawn. The theme
  flips in one frame.
- **A JavaScript timer never copies a duration.** A timer that waits for an animation reads the
  token or waits for `animationend`.

## 2. The roles and their tokens

A component names a role. It never writes a number. Retune one token and every surface of that
role follows. `app/src/tokens.css` holds the values, and `docs/DESIGN.md` locks each name.

| Role | Token | Value | Easing token | Used for |
|---|---|---|---|---|
| Press | none | 0 | none | the `translate` dip in `base.css`, not eased. |
| Hover, focus, exit | `--bn-t-fast` | 120ms | `--bn-ease` to respond, `--bn-ease-in` to leave | color, border, shadow, and every `[data-leaving]` exit. |
| Small enter | `--bn-t` | 200ms | `--bn-ease-out` | menu, popover, tooltip, a row, the theme crossfade. |
| Large enter | `--bn-t-slow` | 280ms | `--bn-ease-out` | page, sheet, dialog, toast. |
| Layout move | `--bn-t-layout` | 240ms | `--bn-ease` | the rail fold, a progress bar's width. |
| One-shot flash | `--bn-t-flash` | 200ms | `--bn-ease-out` | the capture flash. |
| Highlight | `--bn-t-highlight` | 700ms | `--bn-ease-out` | a price cell that just changed. |
| Draw | `--bn-t-draw` | 480ms | `--bn-ease-out` | a bar, a line or a check drawing in, and a sale bill. |
| Live loop | `--bn-t-pulse` | 1.8s | `--bn-ease-loop` | `bn-pulse` (a dot) and `bn-breathe` (anything else). |
| Busy ring | `--bn-t-spin` | 0.7s | `--bn-ease-linear` | `bn-spin`. |
| Sweep | `--bn-t-shimmer` | 1.4s | `--bn-ease-loop` | a skeleton, an indeterminate bar. |
| Reduced-motion floor | `--bn-t-instant` | 0.01ms | none | `base.css` crushes every duration to it. |
| List step | `--bn-stagger`, `--bn-stagger-cap` | 30ms, 12 | none | one cadence for every list. |
| Enter distance | `--bn-rise` | 6px | none | `bn-page-in` and the Home deck. |

A choreography delay is a multiple of the stagger: `calc(var(--bn-stagger) * 2)`. A pace the
data sets (a drain, a settle window) is a custom property that a script sets, read as
`var(--receipt-ms, 20s)`. The fallback is the one place a literal may sit.

## 3. How a new screen gets correct motion

Reuse the utilities. Never write a duration.

- **A page** is `<Page>`. It already enters with `.bn-page` (`bn-page-in`).
- **A list** gets `.bn-stagger` on the list, with `style={{ '--i': index }}` on each child. A
  child whose parent is not the list takes `.bn-stagger-item` instead. Both read the same
  delay and make the entry fade, so a list never rises on top of its page.
- **A live thing** takes `bn-pulse` (a dot) or `bn-breathe` (an icon, a segment, a line) on
  `--bn-t-pulse` and `--bn-ease-loop`.
- **A sheet, dialog, menu or toast** takes the kit's classes. Their exit runs on
  `--bn-t-fast` and `--bn-ease-in` through `[data-leaving]`.
- **A one-shot highlight** names `--bn-t-highlight`. **A drawn line** names `--bn-t-draw`.
- **Hover and press** come from the floors in `base.css`. A component that names its own
  `transition` names every property it animates.

## 4. How it stays this way

- **`raw motion`, a row of `make docs-audit`** (`check_raw_motion`, mechanical). It reads every
  `transition` and `animation` declaration, and their longhands, in `app/src/*.css` outside
  `tokens.css`. It refuses a time literal, a `cubic-bezier(`, `steps(` and the easing keywords.
  It reads the same four style props in TSX and refuses a number there. It skips `var()`
  fallbacks and zero times.
- **The allow list** is `scripts/motion-literal-allow.json`. An entry names a file and a
  literal and carries its reason. An entry that matches nothing is itself a finding, and the
  list is empty today. It only shrinks.
- **Three specs assert the built behavior.** `app/tests/staggerCheck.ts` asserts the delay on
  every row of two screens (Pricing and Runs). `app/tests/motion-theme-flash.spec.ts` samples
  the body color through the theme switch, from light and from dark. It also reads the capture
  flash's peak and duration off the real animation. `make design-check` runs them.

## 5. Surfaces

Verdicts: **keep**, **adjust** (same motion, other numbers), **replace** (other motion for the
same job). Status is BUILT where a verdict changed code.

| # | Surface | Verdict | Status |
|---|---|---|---|
| 1 | Response floor | keep | Unchanged. |
| 2 | Press floor | keep | Unchanged. |
| 3 | Reduced-motion floor | keep | The floor reads `--bn-t-instant`. |
| 4 | Theme crossfade | replace | BUILT, see P4. |
| 5 | Route change | adjust | BUILT: `--bn-t-slow` is 280ms, and entries inside a page fade only. |
| 6 | Sidebar fold to rail | adjust | BUILT: `--bn-t-layout`. |
| 7 | Nav link hover | keep | Unchanged. |
| 8 | Rail tooltip | keep | Unchanged. |
| 9 | Command palette | keep | The exit runs on `--bn-ease-in`. |
| 10 | Which-key hint | keep | Unchanged. |
| 11 | Offline banner | keep | Unchanged. |
| 12 | Phone drawer and tab bar | keep | Phone specs are off (DEBT77). |
| 13 | Button, chip, segment, input | keep | Unchanged. |
| 14 | Busy ring | keep | It reads `--bn-t-spin` and `--bn-ease-linear`. |
| 15 | Check mark | keep | Unchanged. |
| 16 | Tab underline | keep | Unchanged. |
| 17 | Live dot | keep | `bn-pulse` is the dot, and every other live loop is `bn-breathe`. |
| 18 | Receipt | keep | Unchanged. |
| 19 | Skeleton | adjust | BUILT: `--bn-t-shimmer` everywhere. Open: the shape of each skeleton, and a swap that fades over `--bn-t-fast`. Both wait for the owner to name the screens. |
| 20 | Progress bar | adjust | BUILT: `--bn-t-layout`. |
| 21 | Menu, pick panel | keep | The exit runs on `--bn-ease-in`. |
| 22 | Scrim | keep | The exit runs on `--bn-ease-in`. |
| 23 | Dialog | adjust | BUILT: `--bn-ease-out` in and `--bn-ease-in` out, with no overshoot. |
| 24 | Sheet | adjust | BUILT: the exit runs on `--bn-ease-in`. |
| 25 | Toast | keep | The exit runs on `--bn-ease-in`. |
| 26 | Generic enters, `.bn-stagger` | keep | BUILT: the one stagger, plus `.bn-stagger-item`. |
| 27 | Lightbox | keep | Unchanged. |
| 28 | Crop reveal | keep | Unchanged. |
| 29 | Mark sold burst and Undo | adjust | Not picked: see P1. |
| 30 | Card location rows | keep | Unchanged. |
| 31 | Home deck | adjust | BUILT, see P3. |
| 32 | Home ribbon | adjust | BUILT: the delay is `min(n, cap)` times the stagger, and the grow is `--bn-t-draw`. |
| 33 | Home standing line | adjust | BUILT: `bn-breathe`. |
| 34 | Home spine and stage | keep | Unchanged. |
| 35 | Capture flash | adjust | BUILT, see P5. |
| 36 | Capture recent strip | adjust | BUILT: `.bn-stagger-item`, capped. |
| 37 | Capture stage | keep | Its card steps are one to three staggers. |
| 38 | Capture live signals | adjust | BUILT: `bn-breathe`, and the meter reads `--bn-t-fast`. |
| 39 | Review | adjust | BUILT: candidates and group cells on the stagger, and `.review-spinner` on `--bn-t-spin`. |
| 40 | Orders and Shipping | adjust | BUILT: one idiom (`--i`), and the guide steps are staggers. |
| 41 | Runs | adjust | BUILT: rows on the stagger, `bn-breathe`, and money that enters on `--bn-t-slow`. |
| 42 | Fulfiller | adjust | BUILT: owed cards and boxes on the stagger, and `ff-draw` on `--bn-t-draw`. The Fulfiller's floors in `docs/DESIGN.md` hold. |
| 43 | Pricing, Sales, Product | adjust | BUILT: `pricing-flash` on `--bn-t-highlight`, and Pricing rows on the stagger. |
| 44 | Codes (dormant) | adjust | BUILT: rows, bars, task cards and stats on the stagger. |

Duplicate keyframes are gone: `rv-verdict-in` and `codes-row-in` are
`bn-page-in`. `rv-row-in`, `rv-photo-in`, `card-locations-row-in`, `capture-fade` and
`codes-fade` are `bn-fade`. `capture-blink`, `runs-breathe` and `home-standing-pulse` are
`bn-breathe`.

## 6. The five picked changes

- **P1, a calmer sale (NOT PICKED).** The proposal was five bills of `--bn-t-draw`, one
  stagger apart, rising about 36px, with the Undo tooltip held until the burst ends. The sale
  stays as it is: eight bills, 800ms each, the tooltip as it was.
- **P2, one stagger for every list (BUILT).** Every list entry reads `.bn-stagger` or
  `.bn-stagger-item` with `--i`. No file keeps a local step or a missing cap.
- **P3, the Home deck plays once a sitting (BUILT).** The first visit to Home in a page
  session plays the full deck in two staggers per card, ending at about 400ms. Later visits
  fade the deck in at rest over `--bn-t`, with no rise. The flag is the
  `banchi.session.homeDeck` key in `sessionStorage`, so a reload inside a sitting does not
  replay it.
- **P4, the theme flips in one composited fade (BUILT).** `App.tsx`'s `toggle` wraps the flip
  in `document.startViewTransition`. `base.css` times the fade at `--bn-t`. No color passes
  through gray, because the browser blends two finished pictures. Without the API, or under
  reduced motion, the flip is one frame. `banchi.theme` storage is unchanged.
- **P5, a lighter capture flash (BUILT).** `.bn-flash` peaks at 0.6 over `--bn-t-flash`.
  Reduced motion shows no flash.

## 7. How the review was recorded

Each surface was driven in a headless Chromium at 1440 by 900, against the demo store. Each
surface has two recordings. One is a real-speed video in `captures/motion/`, which is
gitignored, so it lives on the machine that made it. The other is a frame strip, taken with
the page clock at a tenth of speed. The "before" frames of the five picked changes are in
`docs/specs/motion/`.

Two limits of the method. A slowed clock does not slow a JavaScript timer, so an exit that
`kit/index.useLeave` unmounts was read from the real-speed video. Headless Chromium gives the
capture screen no camera frames, so the flash is the same `span.bn-flash`, mounted by hand.
