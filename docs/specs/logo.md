# The Banchi mark

**Status: BUILT.** Seven marks are locked at the display cut (section 9). The small cut is drawn,
swept and shipping (section 11). The lockup is built and generated (sections 13 and 14). The mark,
the lockup, the browser tab and the app icons are all wired into the app (D102).

This file is the state of record. Two generators read it. `scripts/build-mark.mjs` evaluates the
drawing routine in `docs/specs/logo/sheets/small-cut.html` and writes `markGeometry.ts`,
`markPalettes.ts`, the favicon and the app icons. `scripts/build-lockup.mjs` reads section 13's
table and `sheets/lockup-core.js`, and writes `lockupGeometry.ts`. `make docs-audit` reconciles
the generated files against this file (`logo parity`, `lockup params`, `mac icon grid` and
`rail mark`).

Section numbers are stable ids, because code cites them. A missing number is a deleted section.

## 1. What the mark is

A quintic-superellipse tile in cool near-black. Two diagonal chrome brackets, top-left and
bottom-right, hold a slate card whose surface is a procedural holographic foil. The brackets taper
toward their free ends.

The idea: **番地 is a lot number, an address.** The brackets are the address. The card is what is
at it. With the card removed the same brackets become an empty slot, which is the in-product mark.

## 3. The parameters

Units are the 100 x 100 icon viewBox. A tag says how well a value is known.

- **LOCKED**: an explicit instruction, or bounded by an observed failure on both sides.
- **RANGED**: bounded on both sides. Any value inside is acceptable.
- **HELD**: chosen once and never tested. These are the risk. Four of them survived twenty rounds
  unexamined, and when three were swept, all three were wrong.

| what | value | tag | evidence |
| --- | --- | --- | --- |
| Tile shape | superellipse n = 5 | LOCKED | explicit. n 4 to n 9 are near-identical at icon size |
| Card aspect | 5 : 7 | LOCKED | a 63 x 88 mm trading card |
| Card size | 31.782 x 44.495 | LOCKED | falls out of the mark box |
| Card radius | **1.9** | LOCKED | 1.6 reads as a rectangle. 4.0 is too soft |
| Bracket corner radius | **8** | LOCKED | chosen over the derived 9.945 (section 5) |
| Arm reach | **0.38** | LOCKED | 0.34 and below go stubby |
| Bracket stroke | 1.5 to 2.0 | RANGED | 2.2 eliminated. 1.2 and 0.9 lose the gradient |
| Taper length | 0.12 to 1.5 | RANGED | below 0.12 the profile is a step. 2.0 eats the corner |
| Card-to-bracket gap | 10 to 13 | RANGED | 6.7 crowds the card. 15 lets it float |
| Holo displacement | 40 to 68 | RANGED | 14 goes flat. 76 and above drop |
| Seed | 5, 7, 11, 13, 23, 41 | RANGED | the seed is part of the design. A different roll is a different drawing |
| Sheen over the tile top | 0.10 to 0.20 | RANGED | 0 and 0.30 fail on the second look |
| Ground lightness pair | L 0.255 to 0.148 | LOCKED | the one candidate that moved it lost |
| Ground chroma ratio | 0.23 to 0.39 | RANGED | the two ends were called the same |
| Flat, inverted and warm grounds | **eliminated** | LOCKED | flat reads muddy. The sheen cancels an inversion. Warm was rejected at four chromas |
| Prism | **bluesteel, lilacish, mint** | LOCKED | the owner: "bluesteel, lilic, and mint are good" |
| Chrome gradient colors | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` | **HELD** | never swept |
| Turbulence base frequency | `0.035 0.09` | **HELD** | never swept. It sets the scale of the marbling |
| Turbulence octaves | 4 | **HELD** | never swept |
| Card base fill | `#5A6E80` | **HELD** | never swept. The only color in the mark that nothing else constrains |

### The ground is the prism, driven to black

The ground is the prism's own hue at L 0.255 to 0.148, with part of the prism's peak chroma. It
is tonal, not complementary. The rule has four parameters: one hue, one L pair, one chroma ratio
and a chroma taper. The taper is 0.60 of the ratio at the bottom stop. With it the rule
reproduces all twelve published stops byte for byte. The taper was recovered from the published
values.

- **The hue is chroma-weighted** over the five stops, not taken from the strongest stop.
- **The chroma wall is a ratio near 0.47 of each prism's peak**, and not an absolute chroma. The
  band 0.23 to 0.39 is what all three prisms share. The owner called both ends the same, so both
  are live (section 9 holds ground B, and ground A is an unchosen option).
- **Two gray prisms cannot drive a ground.** Their peak chroma is 0.025 and 0.030, so every ratio
  lands inside the greys. Those two prisms are dropped, and so is every ground written for them.
- **A sheet that derives a value this file has locked redraws a rejected option**, because a
  derivation does not know it was overruled. Section 9 is the authority for every ground hex.
  If a prism stop moves, every ground hex is stale.

| prism | ground A, 0.23 | ground B, 0.39 |
| --- | --- | --- |
| bluesteel | `#1D242B` to `#080B0F` | `#182430` to `#060B12` |
| lilacish | `#23212D` to `#0B0A10` | `#231F34` to `#0B0914` |
| mint | `#1C2522` to `#070C0A` | `#162722` to `#050D0A` |

The prism gradient runs at `x1 .671 y1 .030` to `x2 .329 y2 .970`.

### Two optical cuts

| cut | use |
| --- | --- |
| display, the values above | 64px and up |
| small: **stroke 4.2**, no taper, no filter | below 64px |

The cuts are not optional. A 1.7 stroke is a scratch at 32px and absent at 16px. Section 11 holds
the small cut's sweep.

## 5. Decisions that broke a rule on purpose

- **The bracket corner radius left the derivation.** The derived value was the concentric rule
  (`r = R - p`, which is 9.945). At a 1.7 stroke the bracket is a thin wire far from the card, and
  nobody reads the gap as parallel curves. The wide corner only ate the straight arm. **8** gives
  the arms visible length. The rule was right at a 5.5 stroke and stopped applying at 1.7.
- **The card radius left the derivation too.** 1.602 is a real card's 3.175 mm on 63 mm. At icon
  size it reads as a rectangle. **1.9** is the floor where it reads as a card.

## 6. Two errors worth not repeating

- **The taper clamp.** The taper routine clamps the ramp at half the path. Above the clamp every
  value renders the same drawing while the sheet presents a sweep. Three images approved as
  different were the same image. On the settled lockup geometry the ramp binds at `tl` 0.82, so
  0.80 is the largest value that still draws something new. A sweep whose top end is clamped is
  not a sweep. The only defense that has worked is printing the number used under every specimen.
- **The sheen.** It was 0.22 in the first icons and 0.08 in a generated file. Nobody flagged the
  change, and the owner found it by noticing the tile had gone flat. The value of record is
  0.22, which sits a hair past the 0.20 ceiling and is indistinguishable from it. A value silently
  changed inside an unmeasured range is the same failure as one changed outside it, minus the
  luck.

## 7. Method: refract it like an optometrist

1. **Force a choice between two.** People compare well and judge absolutes badly.
2. **Bracket before bisecting.** Open wide enough that both ends are wrong.
3. **Cross the optimum on purpose.** One step past the best value must be heard as "worse".
4. **Halve the interval, then halve again.**
5. **Never let the answer define the range.** A pick on the edge of an offered range shows the
   range was wrong. A row's endpoints are weak evidence, so crowd them and do not just re-show them.
6. **Change one variable at a time.** Where two interact, cross them in a matrix and say so.
7. **"About the same" is a result.** The just-noticeable difference (JND) is reached. Stop.

Three more rules come from judging by eye:

- **Print the measurement.** Nobody saw that padding moves the lockup four times as much as the
  gap until block height was printed under each specimen.
- **Re-show what was rejected**, and leave the incumbent out of the final row. A control that is
  never removed cannot tell "good" from "familiar".
- **Judge at true pixels.** Render at `deviceScaleFactor` 1 and magnify the bitmap with smoothing
  off. A 2x render flatters the small sizes where a floor is set.

## 9. The locked set

Seven marks. The default is bluesteel. Geometry, sheen and the L pair are section 3's and do not
vary across the set. Sheen is **0.15** on all seven.

| mark | prism | ground | bracket | card base |
| --- | --- | --- | --- | --- |
| **bluesteel — DEFAULT** | `#E4EEF8 #B0C8E0 #7F9FC0 #F2F8FF #6086AC` | `#182430` → `#060B12` | chrome | `#5A6E80` |
| lilacish | `#EFEAFA #BCB4E0 #8E86C0 #F6F2FF #6E68A8` | `#231F34` → `#0B0914` | chrome | `#5A6E80` |
| mint | `#E6F6F0 #A8D4C4 #78AC9C #F2FCF8 #589084` | `#162722` → `#050D0A` | chrome | `#5A6E80` |
| yellow gold | `#FFD97A #F0A82E #C9821E #FFEFC0 #B36F18` | `#141619` → `#000000` | pale gold | `#C98A2E` |
| white gold | `#FFFBF2 #EFE6D2 #DCD0B8 #FFFFFF #C9BCA2` | `#141619` → `#000000` | pale gold | `#D8D2C4` |
| rose gold | `#FFD9C8 #F0B49A #DE9070 #FFE9DF #C87A5C` | `#141619` → `#000000` | **rose** | `#D99878` |
| orange | `#FFCB94 #F58A2E #D0600F #FFE4C8 #B34E08` | `#141619` → `#000000` | **amber** | `#DB7A22` |

The bracket gradients:

| bracket | stops |
| --- | --- |
| chrome | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |
| pale gold | `#FFFBEE #E8CE8A #FFFDF6 #C0A254` |
| rose | `#FFF0E8 #E8B49C #FFF8F4 #C88A6C` |
| amber | `#FFF1E2 #F0B27A #FFF8F0 #CC8142` |

- **The three cool marks take ground B (0.39).** Ground A is not rejected. It is an unchosen
  option, and its hexes are in section 3.
- **Orange joins the warm family and takes true black.** It is the owner's color for Riftbound's Epic gem. Its prism is the yellow-gold ramp turned toward red, and its bracket is `amber`. It is paler than the prism and warmer than pale gold. So the L still reads against black, and the mark stays one object, not a gold mark with an orange card.
- **The gold family takes true black.** The tonal rule gives gold an espresso brown, and true
  black is what makes a gold foil read as lit.
- **`rose` names two palettes**: a four-stop bracket gradient and a five-stop prism. Neither is
  derived from the other. Say which.
- **At 28px the brackets are essentially gone.** That is the evidence for the small cut.

## 11. The small cut

The cut is drawn in `sheets/small-cut.html`, which also holds the drawing routine that
`build-mark.mjs` evaluates. Every mark on it is rasterized at true pixel size. The sizes in the app are 16 to 44, and the
display cut is correct at none of them.

| what | result |
| --- | --- |
| **stroke 4.2** | swept 2.4, 3.0, 3.4, 4.2, 5.0. 2.4 is a ghost at 16px. 5.0 chokes the corner. The pick is interior |
| **no taper** | at tip 0.07 a 4.2 stroke is a third of a pixel wide at its end at 28px. The browser tab alone takes a taper (section 18) |
| **gap 11.5** | 9.75 crowds. 13.0 pushes the brackets into the tile's corner |
| **card scale 1.0** | 1.12 and 1.25 buy legibility and stop the mark being a card in a slot |
| **no marbling** | at every size the app uses, the foil loses to a flat prism gradient. Displacement 60 and 30 are indistinguishable, and a flat base with no prism loses the idea |

With no taper the bracket is a stroked path (7,091 bytes) and not a 642-point polygon (25,101).

**The forced choice was between three candidates. C won:** stroke 4.2, flat prism gradient. The
owner asked for whatever is most faithful to "all prisms light beside dark are so nice". A visible
bracket and a glowing card are what read at size. Candidate A (marbled) loses the glow to mush.
Candidate B (stroke 3.4) loses the bracket first as the size drops. B is one number away and was
not eliminated.

## 12. The light-theme ground

A light ground derives from the same rule run upward, and it loses to the mark it would replace.
sRGB runs out above L 0.94 and above ratio 0.39, and the ratio stops mattering. Chrome and
platinum brackets vanish on a near-white tile. A warm bracket makes a bluesteel mark two metals.
A dark bracket with a dark card is a different mark, because foil needs a dark surround to look
lit. At 44, 32, 28 and 16px on a light page, a light tile has no silhouette.

**The mark is fixed dark in both themes.** Light is a display-size idea and every surface in the
app is below 64px. The mark is an object and not an ink color: an app icon does not invert when
the phone does. A dark-bracket, dark-card mark on a light tile was not eliminated. It was not
chosen.

## 13. The lockup

`番地` over `BANCHI`, both inside the same diagonal brackets. No tagline. The kanji is IBM Plex
Sans JP 400 (section 14). The roman is Manrope 700, all caps, tracked so its advance is 0.75 of
the kanji's advance, and it hangs left. Every value scales with the kanji size, so one geometry
serves every size.

### The settled values, and the one place they live

This table is the store of record for the lockup's parameters. `make docs-audit`'s `lockup params`
row reconciles it against `app/src/kit/lockupGeometry.ts` in both directions.

| key | value | settled |
| --- | --- | --- |
| `pad` | 0.50 | closed on the pixel floor |
| `gap` | 0.08 | answered in the sidebar column |
| `stroke` | 0.050 | swept over five rounds |
| `arm` | 0.32 | carried, and confirmed |
| `rrMul` | 4.0 | closed on the JND |
| `tip` | 0.15 | decided on a criterion |
| `tl` | 0.70 | interior to the clamp |
| `romanSize` | 0.25 | crossover at true pixels |
| `romanFill` | 0.75 | won with the incumbent absent |
| `romanTrack` | 0.14 | a SEED, not an answer |
| `romanOpacity` | 0.45 | against a floor, with a stated exception |

A key here is not the same as a key that has been argued, and the last column says which is which.
`romanTrack` seeds a thirty-iteration solve that rewrites the tracking until the roman matches the
kanji's width, so its 0.14 is overwritten before anything draws. The solved tracking is derived
and cannot be swept.

### What each value taught

- **`pad` and `gap`.** Padding moves the block four times as much as the gap. 0.22 was kept in
  one round and rejected in the next, and the drawing had not changed. The company it kept had.
  Only a range wide enough to break the anchor (1.25) settled it. The gap came from specimens
  drawn inside the real 212px column, and where the sweep row and the column disagree, the column
  wins. Zero survived and is a floor.
- **`stroke`, `rrMul`, `tl` and `tip`.** The recovered stroke 0.11 is wrong once the bracket
  tapers. 0.050 holds a whole pixel down to kanji 20. Five radius specimens differ by under 1.4%,
  which is the JND as a number. The stroke was judged against a corner of 4.07, so any pick far
  from 4.0 would invalidate that judgment. The tip 0.07 and 0.15 look the same, so the criterion
  is whether the taper terminates or dissolves. The consistency argument that fixed the radius
  does not transfer to the tip, because the tip was invisible while the stroke was judged.
- **`romanFill`.** The solve did not run for the first twenty-four rounds. `getBoundingClientRect`
  returns the containing block's width for a `display:block` element, so the width difference
  was zero. A `Range` measures inline content. The match is on the advance, and 0.75 of the
  advance is 0.807 of the ink.
- **`romanSize`.** A step of 0.01 is a third of a pixel at the floor. The round used one magnified
  1x crop per specimen, because a client scales a wide row back down. 0.25 is the crossover
  where B and C keep their counters.
- **`romanOpacity`.** WCAG exempts logotypes, so the bar is this product's: the `--bn-ink-4`
  floor, solved against each theme's panel, is alpha 0.50 on light and 0.45 on dark. 0.45 reads
  4.09:1 on dark and 3.02:1 on light. **The light theme sits under its floor on purpose.** The
  roman repeats what the kanji carries. A later session must read this before it "fixes" it. A
  theme-dependent opacity was rejected, because two numbers is where a mark becomes two marks.

### The size floor is kanji 32

Measured at `deviceScaleFactor` 1. The kanji fails first (near kanji 30), the roman second (near
24) and the bracket last (near 20). **The floor is kanji 32, a block of about 83 x 59px, and 番's
density sets it.** The metric is the tenth percentile of 番's interior whites: 1.33px at kanji 40,
1.07 at 32 and 0.87 at 26. The minimum reads 0.02 to 0.07px everywhere and measures antialiasing.
`Lockup` refuses to render below `LOCKUP_FLOOR = 32`. The 64px rail cannot hold the lockup and
gets bare brackets.

## 14. The lockup's font

- **Hiragino Sans cannot ship.** The macOS license allows display and print while the software
  runs, and forbids derivative works. Extracting outlines into the repo is outside it. The typeface
  design is not the problem. The exposure is the agreement.
- **The kanji is IBM Plex Sans JP 400**, chosen by the owner on seeing it drawn. The lockup drew
  Hiragino at regular weight all along, so weight-matched Plex is 400. At kanji 100, 番地 is
  214.00 advance and 199 ink in Hiragino, and 214.81 and 200 in Plex. The block dimensions are
  byte-identical at 32, 40, 48, 64 and 80.
- **`romanSize` and `romanOpacity` survived the swap without a re-vote.** Both criteria are
  face-independent: a crossover measured on Plex, and a contrast ratio of composite color.
- **The match is on the advance.** CSS adds one trailing letter-spacing unit, so advance and ink
  differ by 7.7%. Every round judged the advance-matched drawing. Moving the solve to ink would
  change an approved value. Reopening it means re-offering the round.
- **The type is outlined, and no font ships.** `build-lockup.mjs` reads `@ibm/plex-sans-jp` and
  `@fontsource/manrope` (OFL-1.1 devDependencies) and emits path data. A shipped webfont fails
  silently when it does not arrive. The generator renders the outlines against the live text and
  refuses to write when more than 8% of inked pixels differ. The residual is 6.2% (one pixel of
  outline from hinting). A wrong comparison reads 69%. The solve is baked, so the tracking ships
  as a constant.
- **The lockup is the word**, so it carries `role="img"` and a name. Inside the sidebar's brand,
  which has its own accessible name, the call passes `decorative`. Never a `border-radius`.

## 16. The sidebar

| what | settled | |
| --- | --- | --- |
| size in the open sidebar | **kanji 40** | 128 x 93px block in 212px of usable width |
| bracket on **dark** | **the locked chrome gradient** | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |
| bracket on **light** | **flat ink** | `#0f1217` |

- **40 beat 32 because 32 is a floor and not a choice.** Nothing is displaced at any verified
  height. Kanji 32 puts the roman at 8px, where only a magnified raster resolves it.
- **The dark bracket is the mark's own metal**, so the lockup and the mark are one object. Light
  stays flat ink, because any gradient on white sits far under the contrast floor. A color that
  varies by theme is ordinary. A per-theme opacity would make one drawing two. `lockup bracket`
  checks that the component reads `MARKS.bluesteel.bracket`.
- **The rail draws the empty slot**, the brackets with the card taken out. The sidebar mounts both
  drawings and CSS chooses, because a media query rails the shell at 768 to 1023px. The rail's values are its own: stroke 0.11 and radius 0.146 of the
  frame. `rrMul` 4.0 on a rail bracket leaves an arc with no arm.
- **The collapse is one morph on one drawing.** Both ends are one L, and `taperParts` in
  `sheets/lockup-core.js` emits both at 301 centerline samples (the small cut is `tip = 1`), so a
  point-wise lerp is exact. Both rules change across the move, so each end is resolved to pixels
  and the pixels are interpolated. `build-lockup.mjs` renders its untapered end against the wire in
  `markGeometry.ts` and refuses to write above 2% of inked pixels differing (measured 0.30%).
- **The clock is the box.** The morph reads the slot's animating width, holds no copy of
  `--bn-ease`, and needs no reduced-motion branch.
- **The brand is the collapse control.** At 768 to 1023px it stays a link, because a toggle there
  would set state the layout ignores.
- **The sidebar has a spine at x near 32**, and nothing travels across it in a collapse. Centering
  against an animating width threw the mark 79px right and back, and no end-state check saw it.
  `brand.spec.ts` samples eight points mid-transition and asserts a corridor.

## 17. The macOS app icon

**824pt of artwork, centered on a 1024pt canvas, which is 80.47% of the width.** That is Apple's
macOS icon grid. Safari, Mail and Calculator all measure 80.47% solid body. A full-bleed tile
beside them is 24% wider and 55% more area. `scripts/build-mark.mjs` holds
`MAC_GRID = 824 / 1024` and insets by drawing the mark smaller on a transparent canvas.
Section 3's geometry is untouched.

| asset | inset? | why |
| --- | --- | --- |
| `app/public/icon-1024.png`, `icon-512.png`, `icon-192.png` | **yes** | the manifest set (155 of 192 is 80.73%, the rounding) |
| `app/public/icon-180.png` | **no** | `apple-touch-icon`. iOS masks a full-bleed square itself |
| `app/public/favicon.svg` | **no** | a tab icon is 16 to 32px and has no grid |

The whole manifest set is inset. Chrome builds an installed app's `.icns` by resizing the
manifest icons. A set that disagreed with itself would pad the dock icon at one size and not the
next. `favicon.svg` is out of the manifest for the same reason.

- **No drop shadow.** Every system icon carries one out to 87.5%, and the mark carries none. A
  shadow is a drawing decision and section 3 locks the drawing (see Open).
- **The `.icns` 16 and 32px representations come from the display cut, and this closes as a
  note.** A manifest cannot name a cut per size, and Chrome rewrites a hand-authored `.icns`. The
  dock draws 64pt and up, so these serve only Finder lists and the menu bar. A native bundle
  with its own `.icns` is the fix if they prove to be seen, and that is a different decision from
  D108's.
- **No dark icon variant.** A manifest cannot express one, and section 12 ruled the mark fixed dark.

## 18. The browser tab

`app/public/favicon.svg` is the empty slot: the bracket pair alone, with no tile, no card and no
sheen. It is what the collapsed sidebar is (section 1).

| | |
| --- | --- |
| shape | the mark's L. Corner (22.609, 16.252), arms 20.82 x 25.65, radius 8 |
| weight | **4.2**, section 11's small cut |
| taper | **tip 0.15, ramp 0.70**, section 13's values read from `lockupGeometry.ts` |
| paint | **flat `#A8873F`** |
| ground | **none** |

- **The taper is section 11's rejected range, taken on purpose.** The arm ends drop out at 16px.
  The owner took that, because the taper is better at 32, where a Retina tab renders.
- **Gold, and flat.** With no ground, the paint must survive light and dark tab bars. Silver is
  near-invisible on light and ink is near-invisible on dark. Gold's mid-tones sit in the middle of
  the luminance range. At 16px the pair is about twelve pixels of ink, and a gradient across it
  resolves to noise. `#A8873F` is one shade below section 9's `#C0A254`, because the deeper value
  holds the light bar.
- **`#A8873F` is not in section 9, and must not be added.** Section 9 is an illustration's palette
  and this is one surface's paint. `build-mark.mjs` reads it from the table row above.
- **The tab is the one surface not drawn in a metal**, and the owner took that cost.

## 19. The phone

| surface | draws | size |
| --- | --- | --- |
| sidebar, expanded | the lockup | kanji 40 |
| sidebar, railed | the empty slot | 32 |
| **phone top bar** | **the empty slot** | **32** |
| **phone drawer** | **the lockup** | **kanji 40** |
| `#/gallery` | both, beside the mark | 32 / 40 / 56 |
| browser tab | the empty slot, flat gold | section 18 |

- **The bar is the rail's case.** The lockup's floor is a 102 x 75 block and `--bn-topbar-h` is
  52px. The bar draws the rail's slot in `--bn-lockup-metal`, which `kit.css` resolves per theme.
  The product must not wear two brands by window width.
- **The bar's word is the roman, set as text**, because Manrope already ships. It is uppercase,
  tracked by `ROMAN_TRACK_SOLVED / PARAMS.romanSize` em, at `PARAMS.romanOpacity`, and 13px.
  11px goes weak beside a 32px mark and 16px competes with it.
- **The drawer is the sidebar at a phone's width**, so it draws the lockup at kanji 40 with one
  number and not two. The head grows from 60px to 121px, and the nav already scrolled on phones
  below about 800px.
- **The owner kept the group headings and shrank them.** Five rules tighten the air around each
  label and leave its type alone. The drawer's lockup is kanji 34 on a short screen. The size is
  chosen in JS here, because `Lockup` interpolates between the slot's measured width and its
  `size`. A media query alone would leave the box at 34's width and the math at 40's.
- **A second step, at 740px, sets the rows to 40px**, the thumb floor. A ramp shrinks a screen that
  already fits, because a continuous function of the viewport cannot know whether content fits.
  There is no third step.
- **The SE cannot fit.** With every value at its floor and no headings, the drawer needs 587px in
  577px, so a scroll-progress mask fades the bottom edge.
- **One `BrandSlot` in `app/src/App.tsx`** serves the sidebar, the bar and the drawer, with no
  second drawing and no JSX branch. `brand.spec.ts` guards the bar's wire, the drawer's block
  (127.6 x 93.2) and the floor.

**What would reopen it:** a compact horizontal cut that fits 52px. An 84px bar costs about 10% of
an 844px viewport on every screen.

## Open

- **The HELD base parameters** (section 3) were never swept. See `DEBT74`.
- **A drop shadow on the Mac dock icon** was never tried. See `DEBT73`.
- **A compact horizontal lockup** for the phone bar (section 19).
