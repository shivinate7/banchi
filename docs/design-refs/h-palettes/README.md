# Lane H: a loud, many-color dark mode (deferred PR)

This folder is the record for lane H. H left PR 4B on the owner's word (2026-09-27) and waits
as its own PR. Nothing here changes the app. The palettes are CSS overrides of the dark
`--bn-*` tokens, rendered over the published demo.

## The owner's rulings, in order (2026-09-27)

- H started as the epilogue of PR 4B: `it'll be the epilogue of PR4`.
- Rounds 1 and 2 used one accent each. They were Neon Noir, Terminal and Synthwave, then Arcade, Glitch and Signage. The owner's verdict:
  - `all of the H concepts tend to just pick one color and stick to it, when the power of cyberpunk is its fusion of several loud color schema contrasting and clashing`
  - `neon noir was the closest of the dynamism though if i had to pick one`
  - `none were good tho`, and on round 2, `pretty underwhelming`
- The method that worked: a new BLIND agent saw only the LIGHT mode, and read only `app/src/tokens.css`. The owner's brief:
  - `super spicy, loud, color schema (no actual boxes and stuff change, just colors, but not just one color, MANYYY COLORS) cyberpunk anime esque dark mode as though you're a league of legends pro`
- Its first four palettes were Championship, Drift King, Overclock and Lantern District. Owner: `This version of H is absolute fire`.
- Its second four were Abyssal Bloom, Solar Temple, Kaiju Alert and Carnival Midway. Owner: `abysall bloom might be gold -- love it`.
- Owner: `commit all the work done for  H and leave it all as something to come back to in its own PR`.

## What is here

- `index.html` is the contact sheet. Round 2 is on top, and round 1 is below. Each palette is
  a row of Home, Pricing, Orders and Sales at 1440x900, with its swatches and each hue's job.
- One CSS file per palette. Each file is the whole override, ready to inject.
- `NOTES.md` is the colorist's method. It covers the hue-to-job map, the selectors it colored,
  and the contrast checks. Body text is at least 4.5:1.
- `method/` holds the scripts that captured the light-mode references, built the CSS, rendered
  the screens and checked contrast. They carry absolute scratch paths from their session.
- The screenshots are not in this commit yet. The pre-commit hook refuses images outside the
  demo photo folders. Lane G (on `ux/pr4b-G`) changes that rule, so every staged image gets
  the QR scan in any folder. After G merges, the 32 screenshots join this folder as JPEGs.

## When this PR resumes

- Start from Abyssal Bloom, the owner's favorite. Carnival Midway is the other palette that
  pushes color into the page and table grounds.
- Ask the owner which palette, or which blend, becomes the dark theme. Then decide whether a
  theme switch keeps today's dark mode beside it.
- A build moves the chosen values into `app/src/tokens.css` under `:root[data-theme='dark']`.
  The per-selector rules become kit classes, not page CSS. `app/src/tokens.css` stays the only
  file that names a color. Verify every screen at 1440, 820 and 390 against the contrast
  floors. Leave the Fulfiller's screen unchanged.
