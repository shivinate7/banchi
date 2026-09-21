# Home (`#/`)

Widths looked at: 1440, 1280 (both via viewport emulation + `getBoundingClientRect`/`getComputedStyle` measurement; the Browser pane itself was hidden for most of this pass, so pixel numbers below come from live DOM measurement, not screenshots).
Themes looked at: dark (measured in depth), light (screenshotted earlier in this session, at 1440 only — confirmed colors swap correctly, not independently re-measured pixel-by-pixel).

## Findings

1. **Home's hero tiles ease into hover at 200ms; every button and nav link in the product eases at 120ms.**
   What I saw: measuring `transitionDuration` on every interactive element on Home, 37 elements
   (buttons, kbd, nav links, `Start capturing`) return `0.12s`, matching the product's
   `--bn-t-fast` floor. But 8 elements on this same screen — `.home-standing-row` (the
   "Cannot be filled…" banner row), `.home-deck` (the card-photo link, top right), and all
   6 `.home-stage` stat tiles (Capture/Runs/Review/Pricing/Orders/Shipping) — return `0.2s`
   for their hover transitions (`box-shadow`, `background-color`, `transform`).
   Where: `app/src/Home.css:40` (`.home-standing-row`, uses `var(--bn-t)`), `:241` (`.home-stage`,
   `var(--bn-t)`), `:341` (`.home-deck`, `var(--bn-t)`). The rest of the product (checked:
   sidebar nav links, topbar, `Start capturing` button, command palette items, keyboard sheet)
   uses `var(--bn-t-fast)` (120ms) for the same kind of hover response.
   Severity: nit (each is smooth and correct on its own; the mismatch is only visible when
   moving quickly between a tile and a button, or comparing side by side).
   Fix: swap `var(--bn-t)` for `var(--bn-t-fast)` in the three rules above, or accept the
   80ms difference is deliberate (cards feel "heavier" than buttons) and say so in a comment.
   Recurs elsewhere? Checked Capture, Runs, Review — none of their hover-affected elements use
   `var(--bn-t)`; every one measured there is `0.12s`. So this looks isolated to Home's hero
   section, not a repo-wide drift.

2. **Sidebar rail state is decided once at mount from `window.innerWidth`, never re-evaluated on resize** (this affects every screen, documented in full with the reproduction steps in `shell.md` finding 1 — not re-stated here to avoid duplicating the same evidence across files, since it is a shell-level defect that happens to also govern Home's own left inset). Filed under shell.md as the primary location; flagging its presence here since it changes Home's `x` origin (`.bn-page` left edge shifts between 236px-from-edge (expanded) and 64px-from-edge (collapsed) depending on this state).

3. **The standing-line's trailing hint reads as a bare `,0` next to a chevron, with no visible label saying what pressing it does.**
   What I saw: at the end of the "Cannot be filled — 47 copies for 40 open orders cannot be
   found." row, there is a `<kbd>` chip and a chevron-right icon. The kbd's rendered text is
   the literal keyboard shortcut string (I observed `,0` and `,C` in different states across
   this session). Read out of context, `,0` looks like a stray comma-zero rather than a
   keyboard hint, unless the reader already knows the app's `,`-then-letter leader convention.
   Where: `app/src/Home.tsx:216-219` (`say.kbd` rendered as `<kbd className="bn-kbd">{say.kbd}</kbd>`
   immediately before the chevron, with no "press" or "shortcut" affordance beyond the kbd's own
   chip styling).
   Severity: nit. The kbd-chip convention is used consistently everywhere else in the product
   (Start capturing's `,C`, the command palette's per-item hints, the keyboard sheet itself),
   so a returning user learns it fast; a first-time reader on the very first screen they see
   has no such context yet.
   Fix: none required if the convention is meant to be learned from the `?` sheet; if it should
   be self-explanatory on first contact, consider a tooltip or the word "Go" beside the chevron.
   Recurs elsewhere? This is the kit's standard kbd-chip pattern, used correctly and identically
   on every screen I checked (Capture's `,C`/`,S` etc., the command palette, the `?` sheet) — so
   this is a first-encounter-order question about Home specifically (it is the landing screen),
   not a defect in the pattern itself.

4. **Boxes/Recent runs section headers are pixel-identical to each other, no defect found.**
   Measured for completeness: both `.bn-section-title` headers ("Boxes", "Recent runs") are
   16px/700 weight, their icons and their "Browse →" / "All runs →" links share the exact same
   vertical center (`cy` = 739.69px, 0px difference) — icon, title text and trailing link are
   perfectly baseline-aligned. No fix needed; recorded so a later pass does not re-measure it.

5. **Six `.home-stage` tiles and five `.home-box`/`.home-run` list rows all use consistent,
   exact-token gaps.** Measured: the 6 stat tiles are 180px wide (1440) / 182px (1280) with a
   uniform 12px gap between every pair; the "Boxes" and "Recent runs" row lists step by exactly
   55px per row with no drift. No defect found; recorded for completeness.

6. **No horizontal overflow at 1280.** `document.documentElement.scrollWidth` equals
   `clientWidth` at 1280 (1280 vs 1280) with the sidebar expanded. Not independently checked
   with the sidebar collapsed at 1280 (see "What I could not check").

## What I could not check

- **Screenshots at 1280 (either theme) and light theme at 1440 in full pixel detail**: the
  Browser pane was hidden for the middle and back half of this pass (a host-side state I
  cannot toggle), so 1280 and most of light-theme Home is backed by DOM measurement
  (`getBoundingClientRect`/`getComputedStyle`) rather than a visual screenshot. I am confident
  in the numbers reported above, but a purely visual defect that leaves no computed-style
  signature (for example, an image that failed to decode, a color that "reads wrong" to the
  eye despite correct hex values) would not have been caught this way. UNKNOWN, not clear.
- **The exact light-theme color values on Home's warn-toned tiles** (Review/Pricing/Orders)
  were not re-measured numerically in light mode; only visually spot-checked earlier in this
  session (looked correct, orange-tinted background against light ground).
- **Hover and focus states were measured via computed style, never via an actual pointer
  hover** (the pane being hidden meant `computer.hover` could not be used reliably). The
  `transitionDuration` values reported above are real and load-bearing, but I did not confirm
  the actual painted colors at the hover midpoint of the animation.
- **Home at widths between 1280 and 1440**, and above 1440, were not checked (out of the
  required range, noted only for completeness).
