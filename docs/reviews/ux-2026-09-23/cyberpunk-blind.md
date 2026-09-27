# Lane H: a blind first look at dark mode, for a cyberpunk mode

An Opus agent with no project history made this review on 2026-09-27. It read no repository
file. It shot the published demo in dark and light, at 1440x900 and 390x844, on 14 routes. The
owner asked for it: `send an opus agent to blindly just see wht the app looks like now`. The
hex values below come from the live page's computed styles. This is input for lane H's
interview, not a ruling.

## What dark mode looks like now

- Surfaces are near-black and cool: page #0c0e12, card #14171c, raised control #1b1f26. The
  steps are small. Tiles and tables separate mostly by a white hairline at 8% alpha.
- Text: #eef0f4 at 16.9:1 and #b9bfc9 at 10.4:1 are good. The third grey (#838b98, 5.6:1) and
  the fourth (#707886, 4.3:1) carry many meta lines at 12 to 13px, and they read dim.
- One accent, periwinkle #7f90ff, means act, selected, link and data at once. On Sales the
  bars, the pill and the tabs compete.
- Status colors are vivid and healthy. The amber "Held" fill on Pricing reads as disabled.
- What works: the brand lockup, the mono money, the keycap hints, the 2px focus ring, and the
  card photos.
- What reads flat or muddy:
  - Home has a dead band under the headline, about 120px on a phone.
  - Secondary buttons on Pricing are darker than their container, so they look sunken.
  - Control borders are about 1.65:1, below the 3:1 non-text minimum. Search and Qty fields
    almost disappear.
  - Pricing's TREND column is an empty header.
  - Sales' "No photo" boxes fill the top-seller cards.
  - The ghost and quiet button variants look nearly the same.

## Three concepts

- **A. Neon Noir.** Cyan #22e5ff and magenta #ff3ea5 on blue-black #0a0a12. A squarer display
  face for h1 only. Static glows on h1, money and the primary button. A chromatic edge on the
  brand mark only.
- **B. Terminal.** Phosphor green #39ff6a on black, all mono, scanlines. One hue cannot
  separate accent, success and selection. Scanlines hurt reading and the photos.
- **C. Synthwave Dusk.** Pink and orange on purple #1a0f2e. The purple ground tints every card
  photo, which makes grading harder.

## The agent's recommendation: A, used with restraint

The ground stays neutral, so photos keep their true color. Cyan becomes act, focus and
selected. Magenta becomes money and brand. It maps onto the current color roles, so it is a
palette swap plus a small effects layer.

| Role | Hex | Contrast on bg / surface / top |
|---|---|---|
| Background | #0a0a12 | |
| Surface | #12121e | |
| Top layer | #1a1a2b | |
| Text | #eef0ff | 17.4 / 16.4 / 15.1 |
| Muted text | #a9adc9 | 8.9 / 8.4 / 7.8 |
| Faint text, large labels only | #8a8fb0 | 6.2 / 5.9 / 5.4 |
| Accent, cyan | #22e5ff | 12.9 / 12.1 / 11.2 |
| Secondary accent, magenta | #ff3ea5 | 6.1 / 5.7 / 5.3 |
| Success | #3dffa0 | 15.0 / 14.2 / 13.1 |
| Warning | #ffc53d | 12.5 / 11.8 / 10.9 |
| Danger | #ff5c7a | 6.6 / 6.3 / 5.8 |
| Control border | #6a6aa6 | 4.0 on bg, 3.7 on surface |
| Hairline, decoration only | #34345a | 1.6 |

## Loud against calm

- Loud: the brand lockup, the page h1, and the one primary action per screen.
- Also loud: headline money in magenta mono, the live dot, and the focus ring. A static grid
  could fill Home's empty band.
- Calm, with no glow and no overlay: Pricing rows, the buyer list, the Inventory list, the
  rulers, the Sales table, the Shipping lanes, and every card photo. Per-row money stays plain.
- The Fulfiller's screen stays exactly as it is.
- Fix in any theme first: the brown "Held" fill, the sunken secondary buttons, and the control
  borders.

## Cost notes

Static glows are cheap. An animated glow or a backdrop blur is expensive on long lists. A
full-screen scanline lowers small-text contrast by about 10 to 20 percent. A chromatic filter
blurs text below 24px.
