# The Banchi mark

**Status: DIRECTION SETTLED, PARAMETERS MOSTLY BOUNDED, ASSETS STALE. THE GROUND IS DERIVED.** This file is the state
of record. The SVGs beside it in `logo/` do **not** match section 3 and must be regenerated
before anyone uses them.

Nothing under `app/` or `server/` has been touched. `app/src/kit/index.tsx:258` (`Logo`) and
`app/public/favicon.svg` still hold the placeholder: a geometric **B** in a rounded square.

## 1. What the mark is

A quintic-superellipse tile in cool near-black. Two diagonal chrome brackets — top-left and
bottom-right — holding a slate card whose surface is a procedural holographic foil. The
brackets taper toward their free ends.

The idea: **番地 is a lot number, an address.** The brackets are the address; the card is what
is at it. With the card removed the same brackets become an empty slot, which is the in-product
mark.

## 2. Reading this file

Every parameter is tagged. The tags matter more than the numbers.

- **LOCKED** — an explicit instruction, or bounded by an observed failure on both sides.
- **RANGED** — bounded on both sides; any value inside is acceptable.
- **HELD** — chosen once and never tested. **These are the risk.** Four of them survived twenty
  rounds of refinement unexamined, and when finally swept, three turned out to be wrong.
- **DRIFTED** — the value in the file disagrees with the value decided.

## 3. The parameters

Units are the 100 x 100 icon viewBox.

| what | value | tag | evidence |
| --- | --- | --- | --- |
| Tile shape | superellipse n = 5 | LOCKED | explicit; n 4 to n 9 are near-identical at icon size |
| Card aspect | 5 : 7 | LOCKED | a 63 x 88 mm trading card |
| Card size | 31.782 x 44.495 | LOCKED | falls out of the mark box |
| Card radius | **1.9** | LOCKED | 1.6 reads as a rectangle; 4.0 too soft |
| Bracket corner radius | **8** | LOCKED | chosen over the derived 9.945 — see section 5 |
| Arm reach | **0.38** | LOCKED | 0.34 and below go stubby; 0.43+ tested and this preferred |
| Bracket stroke | 1.5 – 2.0 | RANGED | 2.2 eliminated; 1.2 and 0.9 lose the gradient |
| Taper tip | 0 – 0.20 | RANGED | — |
| Taper length | 0.12 – 1.5 | RANGED | below 0.12 the profile is a step, not a taper; 2.0 eats the corner |
| Card-to-bracket gap | 10 – 13 | RANGED | 6.7 crowds the card; 15 lets it float |
| Holo displacement | 40 – 68 | RANGED | 14 goes flat; 76 dropped; 90 too much |
| Holo opacity | 1.0 | LOCKED | — |
| Seed | 5, 7, 11, 13, 23, 41 | RANGED | **the seed is part of the design** — a different roll is a different drawing |
| Sheen over the tile top | 0 – 0.30 | RANGED | 0.40 eliminated. **0.22** stays the value of record; see section 6 |
| Ground gradient | derived from the prism | RANGED | see "the ground is the prism, driven to black" below |
| Warm ground | **eliminated** | LOCKED | swept at four chromas on its own hue and rejected at every one |
| Prism | bluesteel, warmer, quieter, lilacish, mint | RANGED | colder and richer rejected |
| Prism chroma | 0.025 – 0.098 | measured | `warmer` and `quieter` are below 0.030 and cannot drive a ground |
| Chrome gradient angle | free | RANGED | 90 to 200 degrees all read as metal |
| Chrome gradient colors | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` | **HELD** | never swept |
| Turbulence base frequency | `0.035 0.09` | **HELD** | never swept — this sets the scale of the marbling |
| Turbulence octaves | 4 | **HELD** | never swept |
| Card base fill | `#5A6E80` | **HELD** | never swept |

### The ground is the prism, driven to black

The ground was never a free choice beside the prism. Measured in OKLCH, **it is the prism's own
hue at L 0.255 → 0.148, carrying a fraction of the prism's peak chroma.** Tonal, not
complementary.

That is a derivation and not a description fitted afterwards. Applied to bluesteel — hue 249.1°,
peak chroma 0.0721 — the formula reproduces both grounds that were already on the sheet:

| ratio | derived | the file's value |
| --- | --- | --- |
| 0.23 | `#1D242B` → `#080B0F` | `held`, `#1E232B` → `#080B0F` |
| 0.39 | `#182430` → `#060B12` | `cooler`, `#182430` → `#050A12` |

**The wall is an absolute chroma, not a ratio, and it is per-prism.** Swept at 0.23 / 0.31 /
0.39 / 0.48 / 0.57 / 0.70, each row deliberately crossing the point where the tile stops reading
as near-black and starts reading as a colored tile:

| prism | hue | peak chroma | last good | first too much | wall at C ≈ |
| --- | --- | --- | --- | --- | --- |
| bluesteel | 249.1° | 0.0721 | 0.48 | 0.57 | 0.038 |
| lilacish | 291.1° | 0.0982 | 0.39 | 0.48 | 0.043 |
| mint | 174.1° | 0.0623 | 0.39 | 0.48 | **0.027** |

Mint turns color soonest — its ground competes with the card for the same green before the
others do. **0.23 – 0.39 is the band all three share**, and it is the band `held` and `cooler`
already occupied.

The answers:

| prism | ground | note |
| --- | --- | --- |
| bluesteel | `#1E232B` → `#080B0F` (`held`) or `#182430` → `#060B12` | widest tolerance of the five; good to 0.48 |
| lilacish | **`#231F34` → `#0B0914`** | 0.39. `#23212D` → `#0B0A10` at 0.23 if it should whisper |
| mint | **`#162722` → `#050D0A`** | 0.39. `#1C2522` → `#070C0A` at 0.23 |
| quieter | `held` | see below |
| warmer | `held` | see below |

**Two of the five prisms cannot drive a ground, and that is the finding rather than a gap.**
`quieter` peaks at 0.025 chroma and `warmer` at 0.0297, against bluesteel's 0.0721. Every ratio
from 0.23 to 0.70 lands inside the greys — the whole row renders as five near-identical tiles.
For `quieter`, 0.70 of its chroma *is* `#1D242B`, the held ground. So the rule does not fail on
these two; it returns the neutral, which is the correct answer.

**`warmer` is not a warm prism.** Its chroma-weighted hue is 283° — violet. The warm stops
(85°, 68°, 77°) are the highlights and carry almost no chroma; the two stops that do carry
chroma sit at 268° and 262°. The rejected warm ground was answering a warmth present only in
the top of the gradient, and on the wrong hue besides — 31°, against a highlight at 75°. Put on
the highlight hue and swept at C 0.008 / 0.016 / 0.028 / 0.045, it browns without ever becoming
right. **A warm ground has to be asserted, not derived, and it was rejected on the sheet.**

Regenerate the sheets this was read off:

```
node docs/specs/logo/sheets/shot.mjs $PWD/docs/specs/logo/sheets/ground-per-prism.html /tmp/a.png 1180 900
node docs/specs/logo/sheets/shot.mjs $PWD/docs/specs/logo/sheets/ground-bisect.html   /tmp/b.png 1080 700
```

### The lockup

`番地` over `BANCHI`, both inside the same diagonal brackets. No tagline.

| what | value | tag |
| --- | --- | --- |
| Kanji | Hiragino Sans, tracking 0.07em | LOCKED |
| Roman | Manrope 700 at 0.36x the kanji, **tracked until it is exactly as wide as 番地** | LOCKED |
| Case | all caps | LOCKED |
| Padding | 0.22 – 0.28 of the kanji size | RANGED |
| Line gap | free, 0.09 to −0.03 | RANGED |
| Bracket stroke | 0.11 of the kanji size | LOCKED |
| Bracket arm | 0.32 | LOCKED |
| Dark-mode stroke | x 0.93 | LOCKED — light strokes optically thicken |

**Padding is four times the lever the gap is.** Measured: gap across its whole range moves the
block 4px; padding moves it 16px. Three rounds were spent tuning the wrong parameter.

### Two optical cuts

| cut | use |
| --- | --- |
| display — the values above | 64px and up |
| small — stroke 3.4, no taper | below 64px |

Not optional. A 1.7 stroke is a scratch at 32px and absent at 16px.

## 4. Where the assets stand

| file | state |
| --- | --- |
| `logo/banchi-icon.svg` | committed, and **stale** against section 3 |
| `logo/pass-gold-silver-on-black.png` | committed, still accurate as a record |
| `logo/pass-brackets.png` | committed, still accurate as a record |
| `logo/sheets/*.html` | **the generators.** Self-contained; render with `sheets/shot.mjs` |
| the two ground sheets as PNG | **not committed** — the pre-commit image guard refuses them |

**No asset matches section 3.** The committed icon predates the corrections in sections 5 and 6
and carries the old stroke, arm, card radius, gap, sheen, displacement and seed. It is kept
because it is what was reviewed, not because it is right.

**Nothing exists for**: the small optical cut, the bare brackets in either cut, or the lockup.
All four are generated from the parameters above rather than drawn, so producing them is
mechanical once the RANGED values are chosen.

**The generators are committed now because they were lost once already.** Every sheet this
design has been judged on was built in a session scratchpad and thrown away with it; the ground
sweep was only reproducible because a temporary directory had not yet been cleaned. `sheets/`
holds the three that survive — `oklch.py` is the sRGB ↔ OKLCH conversion the ground derivation
runs on, and `shot.mjs` renders any of them to PNG at 2x.


## 5. Decisions that broke a rule on purpose

**The bracket corner radius left the derivation.** It was `card radius + offset = 9.945`, the
concentric rule (`r = R − p`), which makes two nested curves look parallel. At a 1.7 stroke the
bracket is a thin wire far from the card and nobody reads the gap as parallel curves, so the
rule bought nothing while the wide corner ate the straight arm. **8** gives the arms visible
length. The rule was right at a 5.5 stroke and stopped applying at 1.7.

**The card radius left the derivation too.** 1.602 is 3.175 mm on 63 mm, a real card. At icon
size it reads as a rectangle. **1.9** is the floor where it reads as a card.

## 6. Two errors worth not repeating

**The taper clamp.** Taper length was clamped at half the path, which binds at about 0.82, so
every value above that rendered identically while being presented as a sweep. Three images
approved as different were the same image.

**The sheen.** It was 0.22 in the first modernist icons and 0.08 in the generated file. The
change was mine and was never flagged; it was found by the owner noticing the tile had gone
flat. The value of record is **0.22**.

**The sheen drift is dissolved and the lesson is not.** Swept 0 to 0.40, everything from 0 to
0.30 was accepted and only 0.40 rejected — so 0.08 and 0.22 are both inside the range, and the
stale asset was never wrong on this axis. That makes the drift harmless in hindsight, which is
exactly the case worth recording: it went unnoticed for as long as it did *because* it was
inside a tolerance nobody had measured. A value silently changed inside an unmeasured range is
the same failure as one changed outside it, minus the luck.

Both were drift about earlier settings rather than mistakes in the moment, and both surfaced
only because a render was questioned. That is the argument for this file existing.

## 7. Method — refract it like an optometrist

The owner named this after a dozen rounds had already gone wrong without it. It is the most
transferable thing in this file.

An optometrist does not ask "how good is this lens." They do seven things:

1. **Forced choice between two.** *Better with one, or two?* People are unreliable at absolute
   judgement and reliable at comparison.
2. **Bracket before bisecting.** Open wide enough that **both ends are wrong**. If nobody ever
   says "worse", the edges have not been found — only the limits of what was offered.
3. **Deliberately cross the optimum.** Go one step past the best value to hear "worse". That
   confirmation is the point. Without it there is no way to tell a peak from a wall.
4. **Halve the interval, then halve again.** Coarse steps first, fine steps near the end.
5. **Never let the answer define the range.** Somebody who keeps choosing the strongest lens
   gets a stronger one fetched. **A pick on the edge of an offered range is not an answer, it is
   evidence the range was wrong.**
6. **One variable at a time.** Sphere, then cylinder, then axis. Two at once and neither result
   means anything — except where two genuinely interact, and then cross them in a matrix and say
   so.
7. **"About the same" is a result.** It means the just-noticeable difference has been reached.
   Stop. Further sweeping is noise dressed as diligence.

**What that produced here.** Stroke went 5.56 → 1.7 only because rule 5 was eventually applied;
every earlier range had its floor at whatever seemed reasonable to the person drawing. The arm
found a real floor at 0.38 because 0.34 and 0.30 were finally shown and failed — rule 3. The
card radius left its derived value because 1.6 was put beside 1.9 and lost.

**What it cost to learn.** Ten rounds where a pick landed on a minimum or a maximum and the
next sheet stayed inside the same walls. Each of those rounds looked like progress and was a
survey of one person's prior.

**Two rules that are specific to doing this by eye rather than by lens.**

**Print the measurement.** The finding that padding moves the lockup four times as much as the
line gap was invisible until block height was rendered as a number under each specimen. A sweep
whose effect cannot be seen must be quantified or it is not a sweep.

**Re-show what was rejected.** An optometrist re-presents an earlier lens to check the answer is
stable. That never happened here — no rejected value was ever shown again to confirm the
rejection held. Every rejection in section 3 rests on a single look.


## 8. Still open

- The four **HELD** parameters in section 3. **The ground sweep took a bite out of one of them**:
  the card base fill `#5A6E80` and the prism gradient sit under a ground that is now derived, so
  the base fill is the next thing worth sweeping — it is the only remaining color in the mark
  that nothing else constrains.
- **Which prism.** Five are RANGED and two of them (`warmer`, `quieter`) resolve to the same
  neutral ground and differ from each other only in the top of the gradient. That is a question
  about whether five options are really five.
- Regenerating the four assets, and generating the lockup.
- A drawn wordmark. `Banchi` is set in Manrope today.
- Which of tile / bare mark the sidebar takes. Decide by looking at the rail.
- How the icon ships: it uses `feTurbulence`, which browsers render but a favicon pipeline may
  drop. Exported bitmaps per size may be needed rather than a live SVG.
