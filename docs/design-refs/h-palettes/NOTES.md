# Method — Banchi dark-mode "cyberpunk anime esque" palettes

Read only `app/src/tokens.css`. Looked at the live demo (shivinate7.github.io/banchi/)
in light mode only, for layout reference. Then forced dark mode and injected each
palette's CSS with Playwright's `page.addStyleTag`. No other repo file was read.
No layout, spacing, radius, font, shadow geometry or element changed. Every rule
below sets `color`, `background(-color/-image)`, `border-color`, `outline-color`,
a `box-shadow` color, or `fill`/`stroke`.

## Hue -> job mapping

Every palette assigns hues to the same fixed list of jobs. This keeps the eight
palettes comparable side by side.

- **accent** — primary buttons, links, the focus ring, and the Home nav row
  (`--bn-accent*`, `--bn-line-focus`, `--bn-accent-tint*`).
- **nav groups** — the sidebar has one ungrouped row (Home) plus three labelled
  groups (`Workflow`, `Sell`, `Library`). Found by reading the rendered DOM
  (`.bn-nav-group`, `.bn-nav-group-label`, `.bn-nav-link[aria-current='page']`),
  never by guessing. Each group gets its own hue for its label text and its active
  row's ink, background and left-edge indicator. Targeted with `:nth-of-type(2/3/4)`
  on `.bn-nav-group`. The group order is fixed (Home, Workflow, Sell, Library) on
  every screen, so the index stays stable.
- **live** — `--bn-live` / `--bn-live-tint`, the capture and live indicator.
- **ok / warn / danger** — the three semantic tokens and their tints. Also the
  matching `--bn-pill-ink-*` tokens, so a status pill's text stays in the same
  hue family as its own tint.
- **money** — `--bn-money`, every dollar figure. The kit already forces money
  into the mono face. Only its color moves here.
- **stage accent** — `--bn-stage-accent` and its siblings. This is a separate
  token family the kit already uses for the camera and photo viewfinder. Giving
  it its own hue, never reused elsewhere in the palette, makes the capture
  screen clash against the shell around it on purpose, for free.
- **segmented tabs** — `.bn-seg-item[aria-selected='true']`, found on Pricing's
  "To send / Live" control. The first tab takes the accent hue. The second takes
  the Sell hue. Two adjacent tabs then read as two different signals.
- **panel and table grounds, and the page canvas** — the "push" lever, used on
  two of the four round-2 palettes (Abyssal Bloom, Carnival Midway). `--bn-surface-2`
  and `--bn-surface-3` move off neutral near-black onto a visibly tinted dark hue,
  not just a faint wash. A `background-image` gradient (radial blobs of two or
  three of the palette's own hues, at 10-16% alpha) is added to `body`, so it
  shows through the gaps between panels. `.pricing-row:nth-child(even)` gets a
  faint tint of the palette's own accent or live hue, so the table itself is not
  a flat black grid. The other six palettes keep grounds close to neutral, with
  only a subtle warm or cool cast. So the two levers read as visibly different,
  side by side in the contact sheet.

## Selectors touched (all color only)

- `:root[data-theme='dark']` — every `--bn-*` token already in the shipped dark
  block: the bg, surface, ink, line, accent, live, ok, warn, danger, money,
  pill-ink, shadow and stage-* families. Nothing outside this token list was
  invented.
- `.bn-nav-group:nth-of-type(2|3|4) .bn-nav-group-label`
- `.bn-nav-group:nth-of-type(2|3|4) .bn-nav-link[aria-current='page']`
- `.bn-nav-group:nth-of-type(2|3|4) .bn-nav-link:hover`
- `.bn-nav-group:nth-of-type(1) .bn-nav-link[aria-current='page']` (Home, accent
  hue)
- `.bn-seg-item[aria-selected='true']` and `.bn-seg-item.active` for the first
  tab, plus the same two with `:nth-of-type(2)` for the second tab
- Ground-push only: `body` (`background-color` plus `background-image`),
  `.pricing-row:nth-child(even)` (`background-color`)

Each selector was confirmed against the rendered DOM in the browser
(`document.querySelectorAll(...)`). None came from reading component source.

## Contrast checks

`contrast.js` computes the standard WCAG relative-luminance contrast ratio
between two hex colors. `check-contrast.js` and `check-contrast2.js` ran every
palette against these pairs before rendering:

- `ink`, `ink-2` and `ink-3` against `bg` and against `surface` (body and
  secondary text)
- `money` against `bg` and against `surface`
- `accent` against `bg` (accent used as link text), and `on-accent` against
  `accent` (a button label on a filled accent button)
- `live`, `ok`, `warn` and `danger` against `bg`. Each is also plain text
  somewhere: "Bullish", a warning line, a pill's own ink.
- the three nav-group hues against `bg` (label text color)

Floor: 4.5:1. Two colors failed on the first pass. Each was re-picked by
raising its lightness until it cleared the floor, then every check ran again.

- Overclock's `accent` moved from `#a13bff` to `#b158ff` (4.34 to 5.40). Its
  `on-accent` pairing moved with it, since the button label sits on the accent
  fill.
- Solar Temple's `danger` moved from `#d81e3f` to `#e8355a` (3.92 to 4.78).
  Its `navSell` moved from `#d2451f` to `#e05a2e` (4.33 to 5.33).

No photo, card image, or `<img>` element was touched. The palettes only ever
set `color`, `background`, `border`, `outline`, `box-shadow`, `fill` or
`stroke` on chrome elements.

## Files

- `palettes.js` / `palettes2.js` — the hue definitions for round 1 and round 2.
  One object per palette: hex values, and which hue does which job.
- `contrast.js` — the WCAG contrast-ratio calculator, shared by both check
  scripts.
- `check-contrast.js` / `check-contrast2.js` — print every pair above for
  every palette. Anything under 4.5 is flagged.
- `build-css.js` / `build-css2.js` — turn a palette object into `<key>.css`,
  one file per palette, all under `:root[data-theme='dark']`.
- `render.js` / `render2.js` — Playwright script: force dark mode, inject the
  palette CSS with `addStyleTag`, screenshot Home, Pricing, Orders and Sales
  at 1440x900.
- `capture-light.js`, `inspect-nav.js`, `inspect2.js`, `inspect3.js`,
  `inspect4.js` — the light-mode reference shots, and the rendered-DOM probes
  that found the selectors above (`.bn-nav-group`, `.bn-seg-item`,
  `.pricing-row`, and others).
- `build-sheet-full.js` — assembles `index.html`, with round 2 on top and
  round 1 below it.
