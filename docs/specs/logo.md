# The Banchi mark

**Status: SIX MARKS LOCKED AT THE DISPLAY CUT (section 9). THE GROUND IS DERIVED, AND ITS RULE
GAINED A FOURTH PARAMETER ON 2026-09-05 (section 3). THE SMALL CUT IS DRAWN AND SWEPT AND AWAITS
ONE CHOICE (section 11). THE LOCKUP IS STILL UNDRAWN, AND THE COMMITTED SVG IS STALE AGAINST ALL
OF IT.** This file is the state of record. `logo/banchi-icon.svg` matches neither section 3 nor
section 9 and must be regenerated before anyone uses it.

**A light-theme ground was derived on 2026-09-05 and lost to the mark it would have replaced
(section 12).** The mark is fixed dark in both themes.

**THE MARK IS WIRED INTO THE APP AS OF 2026-09-05 (D102).** `app/src/kit/index.tsx`'s `Logo`
renders §9's six marks at both optical cuts, and `app/public/favicon.svg` is the small cut in
bluesteel. Neither is hand-drawn: `scripts/build-mark.mjs` reads `sheets/small-cut.html` and
generates `app/src/kit/markGeometry.ts`, `app/src/kit/markPalettes.ts` and the favicon, so this
file stays the store of record and the app cannot drift from it by being edited. `make
docs-audit`'s `logo parity` row reconciles the palettes against §9 in both directions.
Nothing under `server/` has been touched. The placeholder — a geometric **B** in a rounded
square — is gone.

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
| Sheen over the tile top | 0.10 – 0.20 | RANGED | 0 and 0.30 eliminated on the second look; 0.40 on the first |
| Ground lightness pair | L 0.255 → 0.148 | LOCKED | `deeper drop` (0.288 → 0.115) was the only candidate that moved it, and lost |
| Ground chroma ratio | 0.23 – 0.39 | RANGED | `held` and `cooler` called "about the same" — the JND, §7 rule 7 |
| Flat ground | **eliminated** | LOCKED | no bottom to fall to; the sheen lifts its top and it reads muddy |
| Inverted ground | **eliminated** | LOCKED | the sheen cancels the inversion rather than adding to it |
| Ground gradient | derived from the prism | RANGED | see "the ground is the prism, driven to black" below |
| Warm ground | **eliminated** | LOCKED | swept at four chromas on its own hue and rejected at every one |
| Prism | **bluesteel, lilacish, mint** | **LOCKED** | the owner's words, 2026-09-05: *"bluesteel, lilic, and mint are good"* |
| Prism — parked | `warmer`, `quieter` | PARKED | ground unresolved; see "the two gray prisms" below |
| Prism chroma | 0.025 – 0.098 | measured | `warmer` and `quieter` are below 0.030 and can never drive a ground |
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

**THE RULE HAS A FOURTH PARAMETER AND THIS FILE STATED IT WITH THREE.** Written as above — one
hue, one L pair, one chroma ratio — the rule reproduces every ground's TOP stop exactly and
misses every BOTTOM stop in the file. **The chroma falls to 0.60 of its ratio at the bottom of
the gradient**, and with that taper the rule reproduces **all twelve published stops byte for
byte**: three prisms, both chroma families, top and bottom.

| | held constant | tapered to 0.60 | published |
| --- | --- | --- | --- |
| bluesteel 0.23 | `#060B11` | **`#080B0F`** | `#080B0F` |
| bluesteel 0.39 | `#030B16` | **`#060B12`** | `#060B12` |
| lilacish 0.39 | `#080918` | **`#0B0914`** | `#0B0914` |
| mint 0.39 | `#000E0B` | **`#050D0A`** | `#050D0A` |

The taper was never chosen; it was **recovered from the values the rule had already produced**,
by asking what single multiplier reconciles the stated rule with the published bottoms. It is
0.60 for all six. Nothing was drawn wrong — the grounds on the sheets are right, and were made
by an eye that was applying a rule it had not fully written down. What was wrong is the
sentence, and a sentence is what the next session derives from.

**`docs/specs/logo/sheets/grounds.py` is the one implementation**, and it prints that twelve-stop
check on every run. The sheets carry its output as literals rather than repeating the arithmetic:
a second implementation of a rule is a second thing to drift, which is what `make docs-audit`'s
`motion params` row already exists to catch elsewhere in this repo.

**Two facts the script also pins down.** The hue is the **chroma-weighted** hue of the five stops,
not the hue of the highest-chroma stop — the two disagree by up to 5° and only the weighted one
reproduces this file's 249.1 / 291.1 / 174.1 / 76.0. And the dark side never meets the sRGB
gamut wall, which the light side does immediately (§12).

**The wall is a RATIO of about 0.47, and this file said "an absolute chroma, not a ratio" until
2026-09-05.** That was wrong on its own numbers: as absolute chroma the three walls spread
.027 – .043, a factor of 1.6, while as a ratio of each prism's peak they spread 0.43 – 0.53, a
factor of 1.2 — and the 0.53 is only high because bluesteel was bracketed at the coarse
0.48 / 0.57 step. The claim was made from three points, read off whichever column was in front of
me. Swept at 0.23 / 0.31 / 0.39 / 0.48 / 0.57 / 0.70, each row deliberately crossing the point
where the tile stops reading as near-black and starts reading as a colored tile:

| prism | hue | peak chroma | last good | first too much | wall at C ≈ |
| --- | --- | --- | --- | --- | --- |
| bluesteel | 249.1° | 0.0721 | 0.48 | 0.57 | 0.038 |
| lilacish | 291.1° | 0.0982 | 0.39 | 0.48 | 0.043 |
| mint | 174.1° | 0.0623 | 0.39 | 0.48 | **0.027** |

Mint turns color soonest — its ground competes with the card for the same green before the
others do. **0.23 – 0.39 is the band all three share**, and it is the band `held` and `cooler`
already occupied.

**The correction is not cosmetic; it decided the other two prisms.** At a ratio of 0.47 the
tonal rule's own ceiling is C .014 for `warmer` and C .012 for `quieter` — both invisible. Read
as an absolute wall of ~.035, the rule looked as though it merely *returned* a neutral for those
two, which is what this file said. Read correctly it can never produce a usable ground for them
at any setting: a neutral was not the rule's answer, it was the rule having no answer. The owner
reached the same place by looking, and first — *"warmer and quieter need different backgrounds
for them to look nice."*

**The ratio was settled by the owner at ratio, not per prism.** `held` (0.23) and `cooler`
(0.39) were called *"both work"* — §7 rule 7, the just-noticeable difference. **Both families are
live and neither is a fallback**, so the answer is two complete sets rather than one set with an
alternate:

### THE THREE THAT ARE SETTLED

**These are LOCKED as of 2026-09-05** — *"bluesteel, lilic, and mint are good"* — at sheen
0.10 – 0.20 over the L pair 0.255 → 0.148. **The prism keeps its own name; the ground is named
after it.** Both chroma ratios are live because the owner called `held` and `cooler` the same.

| prism | prism stops | ground A · 0.23 | ground B · 0.39 |
| --- | --- | --- | --- |
| **bluesteel** | `#E4EEF8 #B0C8E0 #7F9FC0 #F2F8FF #6086AC` | `#1D242B` → `#080B0F` | `#182430` → `#060B12` |
| **lilacish** | `#EFEAFA #BCB4E0 #8E86C0 #F6F2FF #6E68A8` | `#23212D` → `#0B0A10` | `#231F34` → `#0B0914` |
| **mint** | `#E6F6F0 #A8D4C4 #78AC9C #F2FCF8 #589084` | `#1C2522` → `#070C0A` | `#162722` → `#050D0A` |

The prism stops are written out here because they are the input the grounds are derived from —
**if a prism stop ever moves, every ground hex in this table is stale**, and there would
otherwise be no way to tell. The five-stop gradient runs at `x1 .671 y1 .030` → `x2 .329 y2 .970`.

### The two gray prisms, parked

`warmer` and `quieter` are **not settled and not rejected.** The tonal rule cannot serve them —
its ceiling is C .014 and C .012, both invisible — so their ground has to be asserted. Seven were
put up for each on 2026-09-05 and the pass was cut short by a pivot to black and gold before an
answer. **The candidates are recorded so the pass does not have to be re-run**, and the working
hypothesis from the sweep is that a gray card wants a *contrasting* hue at C .045 – .065, roughly
three times what the tonal rule permits, because it has no hue of its own to compete with:

| prism | strongest candidates |
| --- | --- |
| warmer | deep indigo `#1B1F40` → `#07091A`; its cool shadow hue `#182239` → `#060A16` |
| quieter | its own blue at 2.6x, `#042441` → `#010B1A`; at 1.6x, `#132435` → `#040B14` |

**Both picks land close to each other, and the two cards were already nearly one tile.** That is
twice over the same evidence: **five prism options may really be four.** Settle that before
settling their grounds, or one of these two answers is wasted.

**The owner's rejection confirmed the lightness pair without being asked to.** Three grounds went
up at sheen 0.20 — `held` (ratio 0.23), `deeper drop`, `cooler` (ratio 0.39). `deeper drop` was
the only one of the three that moves L, to 0.288 → 0.115, and it is the only one that lost. The
two that were kept are exactly the two the formula produces at the L pair it already had. That
is a derived value surviving a test it was not the subject of, which is the one kind of evidence
this file has been short of.

**`flat` and `inverted` were shown again rather than dropped quietly** — §7's re-show rule, which
this file records as never having been honoured. Both failed for a reason that is about the
interaction rather than about either parameter: **the sheen substitutes for the top of the ground
gradient but not the bottom.** `flat` has no dark bottom to fall to, so the sheen lifts its top
and the whole tile reads lighter and muddier. `inverted` is lit from below, and at sheen 0.20 the
sheen is *cancelling* the inversion — it looks acceptable by accident and comes apart the moment
the sheen moves. Neither could have been judged in a sweep that moved one parameter at a time,
which is why they were crossed in a matrix and §7 rule 6 says to say so.

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
| small — **stroke 4.2**, no taper, no filter | below 64px |

Not optional. A 1.7 stroke is a scratch at 32px and absent at 16px.

**The small cut is DRAWN and SWEPT as of 2026-09-05, and the stroke in this row MOVED — see
§11.** This table asserted 3.4 before anything had been drawn. The sweep put 3.4 against 2.4 /
3.0 / 4.2 / 5.0 and the owner chose **4.2**, which is what `app/src/kit/markGeometry.ts` ships.
The taper's removal survived. Two things this row does not mention — the marbling and the
filter — did not.

## 4. Where the assets stand

| file | state |
| --- | --- |
| `logo/banchi-icon.svg` | committed, and **stale** against section 3 |
| `logo/pass-gold-silver-on-black.png` | committed, still accurate as a record |
| `logo/pass-brackets.png` | committed, still accurate as a record |
| `logo/pass-ground-per-prism.png` | the ground derived per prism, and the two null rows |
| `logo/pass-ground-bisect.png` | 0.23 → 0.70 bisected, where each wall is |
| `logo/pass-ground-matrix.png` | the 5 x 4 ground x sheen cross on bluesteel |
| `logo/pass-ground-choice.png` | the forced choice that settled the L pair, with the two rejections shown |
| `logo/pass-family.png` | **both families, all five prisms, on the settled parameters** |
| `logo/pass-gray-prisms.png` | the seven asserted grounds each for `warmer` and `quieter` |
| `logo/pass-black-and-gold.png` | **section 8** — nine golds, five blacks, five brackets |
| `logo/pass-white-and-rose-gold.png` | white gold and rose gold on the locked black, one pass each |
| `logo/pass-locked-set.png` | **section 9 — the six locked marks**, at 200px and at 48/28px |
| `logo/pass-small-cut.png` | **§11 — the small cut swept**, rasterized at the sizes the app draws |
| `logo/pass-light-ground.png` | **§12 — the light ground**, derived and rejected |
| `logo/sheets/*.html` | **the generators.** Self-contained; render with `sheets/shot.mjs` |
| `logo/sheets/grounds.py` | **the ground rule, and the only implementation of it.** Self-checks against every published stop |

**Every PNG here went in past the pre-commit image guard, on the owner's word each time.** That
guard has no `PKMNSCAN_*=off` hatch — unlike the dupes, links, docs and sigil guards — because a
photograph is the one staged file that can carry a live code. `--no-verify` is the only way past
it and it takes every other guard down with it, so the rule is: ask, stage nothing but the
images, and say so in the message.

**No asset matches section 3.** The committed icon predates the corrections in sections 5 and 6
and carries the old stroke, arm, card radius, gap, sheen, displacement and seed. It is kept
because it is what was reviewed, not because it is right.

**Nothing exists for**: the bare brackets in either cut, or the lockup. **Both** are generated
from the parameters above rather than drawn, so producing them is mechanical once the RANGED
values are chosen — though the bare brackets are less mechanical than they look, because the
card is drawn OVER the brackets and removing it is a change to the drawing rather than a layer
being switched off.

**This paragraph said "the small optical cut" and "All four" over a list of three until
2026-09-05.** The small cut is built and shipping (§11, D102); the count was never right. Both
errors survived because nothing reads this sentence — `logo parity` reads §9's palette table and
stops there, and `paths` resolves repo-relative tokens, not claims about what exists.

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
0.30 was accepted and only 0.40 rejected. **Shown a second time against the ground it sits on,
the band narrowed to 0.10 – 0.20** — 0 and 0.30 both failed on the second look, which is rule 3
working: crossing the optimum in both directions is what turned a five-wide acceptance into a
two-wide answer.

That leaves the drift harmless anyway. `0.22` sits a hair past 0.20 and is indistinguishable
from it side by side, so **the value of record stands and needs no correction** — and `0.08`,
the value in the stale file, was inside the first range if not the second. Which is exactly the
case worth recording: the change went unnoticed for as long as it did *because* it sat inside a
tolerance nobody had measured. **A value silently changed inside an unmeasured range is the same
failure as one changed outside it, minus the luck.**

Both were drift about earlier settings rather than mistakes in the moment, and both surfaced
only because a render was questioned. That is the argument for this file existing.

## 7. Method — refract it like an optometrist

The owner named this after a dozen rounds had already gone wrong without it. It is the most
transferable thing in this file.

An optometrist does not ask "how good is this lens." They do seven things:

1. **Forced choice between two.** *Better with one, or two?* People are unreliable at absolute
   judgment and reliable at comparison.
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


## 8. Black and gold

**A separate mark on the same geometry, not a sixth prism.** Asked for on 2026-09-05. Everything
settled stays settled — the superellipse, the L pair, sheen 0.10 – 0.20, the bracket construction.
Only what makes it gold moves.

**The card base under the holo is amber `#C98A2E`, not the slate `#5A6E80` the cool marks use.**
That is assumed rather than swept: a gold foil over a slate base reads dirty. It is the one HELD
value this section adds, and it is named so it does not become another of section 3's quiet four.

**Locked 2026-09-05**, on the owner's instruction — *"have pale gold with true black as our
locked option"*:

| what | value | tag | evidence |
| --- | --- | --- | --- |
| Brackets | **pale gold** — `#FFFBEE #E8CE8A #FFFDF6 #C0A254` | **LOCKED** | the owner's instruction; and it clears chrome's own floor at the taper tip, see below |
| Ground | **true black** — `#141619` → `#000000` | **LOCKED** | the owner's instruction; the espresso lost, see below |
| Gold prism | `rich`, `yellow`, `honey` | RANGED | not named in the instruction, so it stays open. `antique` and `brass` go olive; `bronze` and `rose` stop being gold |
| Card base | `#C98A2E` amber | **HELD** | never swept |
| Sheen | 0.15 | LOCKED | inside the settled 0.10 – 0.20 |

**The alternatives on that sheet are KEPT, not pruned** — the owner's words, same instruction:
*"the other passes in here are really good and i may wanna revisit some day"*. That is a rule
about this file, not a passing remark. `near-black`, `graphite`, the cool black, the six golds that were not
picked, and the chrome / cream / bronze brackets are **live alternatives, not rejections**, and a
future session must not delete them to tidy the table. Everything needed to put any of them back
on screen is in `logo/sheets/black-and-gold.html`.

**A rejection and an option that was simply not picked are different things, and this file now says which is
which.** Section 3's rejections were argued and bounded on both sides. These were simply not
picked, once, by one person, on one day. Section 7 rule 5 already warns that a single look is
thin evidence; letting "not chosen" harden into "eliminated" would turn thin evidence into a
locked door.

### The tonal rule gives the wrong answer for gold, and this is the first place it has failed

Applied to `rich` gold — hue 76.0°, peak chroma 0.1519 — the rule produces an espresso,
`#2C200F` → `#100903` at ratio 0.23. Put on the sheet it is clearly worse than plain black: the
ground reads *brown* rather than black, and the card loses its separation.

**The mechanism is not the wall this file already measured.** At ratio 0.47 gold's wall would be
C .071 and the espresso sits at C .035, well inside it. What fails is the premise underneath:
tonal works when the ground can be driven to something the eye still calls black, and a warm hue
at L 0.255 stops being black long before a cool one does. **Black and gold is a contrast pairing
by construction** — the appeal is a warm metal against a cold void — so the tonal move deletes
the effect it is named for.

This is *not* the warm ground rejected in section 3. That one was a warm ground under a **blue**
card, where warm was a clash. This is a warm ground under a **gold** card, where warm is tonal.
Both fail, for opposite reasons, which is why it was put back on trial rather than assumed dead.

### The brackets, measured rather than eyeballed

The locked mark's brackets are chrome. Gold card plus chrome brackets is two metals; gold
brackets make it one, which is what "black and gold" asks for. But plain gold is darker:

| bracket | mean L | darkest stop |
| --- | --- | --- |
| chrome — the locked one | 0.878 | 0.709 |
| gold | 0.829 | **0.606** |
| **pale gold** | 0.891 | **0.723** |
| bronze | 0.743 | 0.510 |

**The darkest stop is the one that matters**, because the gradient puts it at the taper tip,
where the bracket is already at its thinnest and nearest to vanishing. Plain gold spends 0.10 of
lightness exactly where the mark can least afford it; pale gold clears chrome's own floor. This
is the section 3 problem in miniature — a value chosen by eye for its mid-tone, failing at an end
nobody looked at.

**Pale gold is the locked bracket and the measurement is why.** It is the only candidate on the
sheet whose darkest stop clears chrome's — the bracket this mark has been drawn with all along —
so nothing is given up at the taper tip to gain the second metal. That is a rare shape for an
answer here: the owner's eye and the number agreed, rather than one overriding the other.

**None of this has been rendered at 32px or 16px, where a weak taper tip would actually show.**
Section 3's *small* optical cut removes the taper entirely, so the small cut is where this would
be settled if it ever came under doubt.

### White gold and rose gold, one pass each

Asked for on 2026-09-05, on the locked true black at sheen 0.15. **Both are RANGED — one pass is
one look, and section 7 rule 5 says that is not an answer yet.** The card base moves with the
family and is HELD in both cases: amber is tuned for yellow gold and would show through a
near-white foil as a stain.

| | prism | card base | bracket |
| --- | --- | --- | --- |
| white gold | `warm` `#FFFBF2 #EFE6D2 #DCD0B8 #FFFFFF #C9BCA2`, or `champagne` | `#D8D2C4` HELD | pale gold holds; **`gold` gives the most separation** |
| rose gold | `classic` `#FFD9C8 #F0B49A #DE9070 #FFE9DF #C87A5C`, or `blush` | `#D99878` HELD | pale gold is the most elegant; chrome the most separated |

**The pale-gold bracket carried two of the three metals, not all three.** I reported "one bracket
across three metals" on 2026-09-05 and it was wrong — read off the bracket *sweeps* in sections 2
and 4 rather than off the comparison row that was actually locked, where rose gold carries `rose`
brackets. The true result is narrower and still worth having: **pale gold was chosen against
yellow gold on a lightness measurement at the taper tip, and white gold did not need it
replaced.** Rose gold does.

**Two findings, and both are about the limits of the idea rather than about a value.**

**White gold's `cool` palette is not a white gold — it is bluesteel.** Driven cool enough to stop
being warm, a near-white foil lands in exactly the hue the locked `bluesteel` prism occupies, and
on the sheet the two are hard to tell apart. So white gold's range is bounded on one side by an
existing member of the family, not by taste: **`neutral` is about as cool as it can go and stay
its own mark.** The bracket sweep says the same thing from the other direction — `white gold`
brackets on a white gold card is the one combination where the brackets and the card stop being
separate objects.

**Rose gold reads as salmon rather than as metal.** The holo is `feTurbulence` marbling, which
sells a *mineral* — foil, stone, opal — and yellow gold survives that because a warm high-chroma
marble still reads as gold leaf. Rose gold's appeal is specifically metallic sheen at low chroma,
and marbling at that chroma reads as coral. **This is a limit of the holo treatment, not of the
palette**, so sweeping more pinks will not fix it; the fix, if it is wanted, is a different
surface for that one variant, and that is a bigger change than a color.

Sheet: `logo/pass-white-and-rose-gold.png`. Generator: `logo/sheets/white-and-rose-gold.html`.

## 9. The locked set

**Six marks, locked 2026-09-05 on the owner's instruction — *"lock all on #5; we'll have the
bluesteel one be the default"*.** Row 5 of `logo/pass-white-and-rose-gold.png` is the definition,
and this table is that row written out. Geometry, sheen and the L pair are section 3's and do not
vary across the set.

| mark | prism | ground | bracket | card base |
| --- | --- | --- | --- | --- |
| **bluesteel — DEFAULT** | `#E4EEF8 #B0C8E0 #7F9FC0 #F2F8FF #6086AC` | `#182430` → `#060B12` | chrome | `#5A6E80` |
| lilacish | `#EFEAFA #BCB4E0 #8E86C0 #F6F2FF #6E68A8` | `#231F34` → `#0B0914` | chrome | `#5A6E80` |
| mint | `#E6F6F0 #A8D4C4 #78AC9C #F2FCF8 #589084` | `#162722` → `#050D0A` | chrome | `#5A6E80` |
| yellow gold | `#FFD97A #F0A82E #C9821E #FFEFC0 #B36F18` | `#141619` → `#000000` | pale gold | `#C98A2E` |
| white gold | `#FFFBF2 #EFE6D2 #DCD0B8 #FFFFFF #C9BCA2` | `#141619` → `#000000` | pale gold | `#D8D2C4` |
| rose gold | `#FFD9C8 #F0B49A #DE9070 #FFE9DF #C87A5C` | `#141619` → `#000000` | **rose** | `#D99878` |

Sheen **0.15** on all six. The bracket gradients:

| bracket | stops |
| --- | --- |
| chrome | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |
| pale gold | `#FFFBEE #E8CE8A #FFFDF6 #C0A254` |
| rose | `#FFF0E8 #E8B49C #FFF8F4 #C88A6C` |

**`bluesteel` is the default** — the one `app/src/kit/index.tsx`'s `Logo` and `app/public/favicon.svg`
take when nothing else is specified. The other five are the set, not alternates to it.

**Locking row 5 also resolved the chroma ratio: the three cool marks are family B, 0.39.** That
was left as a genuine two-way tie on the owner's *"1 or 3 both work"*, and row 5 happened to draw
B. **Family A is not thereby rejected** — it is the same kind of unchosen-not-eliminated option as
section 8's, and its values are in the section 3 table above. A session that wants the quieter
ratio has it.

**One naming hazard, recorded before it bites.** `rose` names two different palettes in
`logo/sheets/`: a four-stop **bracket** gradient and a five-stop **prism**. They are not the same
colors and neither is derived from the other. In the generators they live in separate objects
(`BRK` and `PRISMS`) so nothing breaks, but a sentence that says "rose" without saying which is
ambiguous, and this table is the place that disambiguates.

Sheet: `logo/pass-locked-set.png` — the six at 200px, and again at 48px and 28px.

**At 28px the brackets are essentially gone.** That row is not a decision, it is the evidence for
section 3's *small* optical cut, which §11 has now drawn and swept at 4.2. **Six marks were
locked at the display cut and none at the small cut when this row was written**, and a favicon
is 28px.

## 10. Still open

- The four **HELD** parameters in section 3. `#5A6E80` was put up against three alternatives on
  the light ground (§12 §5) and nothing there argues against it, but that was a sweep about the
  ground and not about the base — **it is still HELD, and still the only color in the mark that
  nothing else constrains.**
- **The small optical cut is SWEPT and awaiting one choice** (§11). It is no longer the biggest
  gap; the forced choice between its three candidates is. Every color decision on this page was
  still made at 104 – 268px, and §11 is the first evidence any of them survives being small.
- **`warmer` and `quieter`**, parked in section 3, are outside the locked six. They differ from
  each other only in the top of the gradient and take the same ground in both families — **five
  candidate prisms may really have been four**, and the locked set answers that by taking three.
  Nothing is owed here unless they are wanted back.
- Regenerating the four assets, and generating the lockup.
- A drawn wordmark. `Banchi` is set in Manrope today.
- Which of tile / bare mark the sidebar takes. The rail takes the TILE today (D102) and it was
  looked at; the bare mark is still undrawn, and it is a real code change rather than a layer
  toggle, because the card is drawn OVER the brackets.
- How the icon ships: the display cut uses `feTurbulence`, which browsers render but a favicon
  pipeline may drop. **§11 narrows this**: at the sizes a favicon and a rail use, the marbling is
  not merely invisible, it loses to a flat prism gradient — so the small cut may carry no filter
  at all, and the question becomes moot for every surface in the app.

## 11. The small cut, drawn

**Swept 2026-09-05. Section 3 asserted this cut in two words and nothing had ever drawn it.**
Sheet: `logo/sheets/small-cut.html`, render `logo/pass-small-cut.png` — which went in past the
pre-commit image guard on the owner's word, the way every PNG in this directory did. Re-render:

```
node docs/specs/logo/sheets/shot.mjs $PWD/docs/specs/logo/sheets/small-cut.html /tmp/small.png 1240 1000
```

**Every mark on that sheet is rasterized at its true pixel size and then magnified with
nearest-neighbor**, so what is on screen is the pixel grid a display actually gets. This is not
a presentation detail. Section 9's small row scaled the *vector* down and was shot at
deviceScaleFactor 2, so its "28px" tiles carry 56 real pixels — it flattered itself by a factor
of two, in the one row whose whole job was to show a failure.

**The sizes swept are the sizes that occur**: 16, 28, 32 and 44. Nothing in the app draws this
mark larger. `App.tsx` renders it at 32 (sidebar and rail), 26 (phone bar), 30 (drawer) and 40
(both crash pages); `Fulfillment.tsx` at 44; the favicon is 16 to 32. **The display cut is
correct at none of them.**

### What held

| what | result |
| --- | --- |
| **stroke — 3.4 asserted, 4.2 chosen** | Swept 2.4 / 3.0 / 3.4 / 4.2 / 5.0. 2.4 is still a ghost at 16px; 5.0 chokes the corner and crowds the card. Both ends fail and the pick is interior, which is section 7 rule 5 satisfied — but the pick is **4.2**, not the 3.4 section 3 had asserted, and §3's row is corrected rather than left standing |
| **no taper** | HELD, and now argued rather than asserted. At tip 0.07 a 4.2 stroke is 0.29 wide where it ends — under a third of one unit in a 100-unit box, which is a third of a pixel at 28px. Swept 0.07 / 0.25 / 0.50 / 1.00. **AMENDED 2026-09-06 for the browser tab ONLY — see §18**, which takes the taper at tip 0.15 and accepts the loss this row measured |
| **gap 11.5** | HELD. 9.75 crowds; 13.0 pushes the brackets into the tile's own corner radius |
| **card scale 1.0** | HELD. 1.12 and 1.25 buy legibility and stop the mark being a card *in* a slot |

### What did not, and it is the marbling

**At every size the app uses, the holographic foil is not merely invisible — it loses to a flat
prism gradient.** Swept at displacement 60 (locked), 30, no marbling, and a flat base with no
prism at all. 60 and 30 are indistinguishable, which is section 7 rule 7 and the end of that
axis. With the marbling removed the same five prism stops render as a clean diagonal highlight
and the card reads as a lit, glossy surface; with it, the card is mush. The flat base is the
failing end — it loses the idea, not just the texture — so the sweep is bounded on both sides.

**This is the same shape of finding as section 8's bracket measurement.** A value chosen at
200px, failing at a size nobody had looked at, for a reason that is about the size rather than
about the value.

**And it decides the engineering.** `feTurbulence` was §10's open question about whether the icon
can ship as a live SVG. If the small cut carries no filter, the question does not arise for any
surface in the app, because every surface in the app is below 64px.

### What it costs, measured

With no taper the bracket is a constant-width wire, so it does not need the 642-point outlined
polygon that variable width forces. A real stroked path — which is the construction
`banchi-icon.svg` has used all along — draws the same shape:

| construction | bytes |
| --- | --- |
| outlined polygon | 25,101 |
| stroked path | 7,091 |

Section 7's *print the measurement*: "smaller" is not an argument until it is a number.

### The forced choice, open

Three candidates, all with the taper removed, differing in the two things the sweeps left
genuinely open. **This is the one thing §11 does not settle**:

| | stroke | card face |
| --- | --- | --- |
| **A** | 3.4 | marbled, displacement 60 — section 3 as written |
| **B** | 3.4 | flat prism gradient |
| **C** | 4.2 | flat prism gradient |

B and C differ only in whether 3.4 is enough bracket at 16px, which is the browser tab and the
one size where the answer is least comfortable.

**C is the pick, on the owner's instruction of 2026-09-05** — *"all prisms light beside dark are
so nice, just do whatever's most faithful to that"*. What makes §12's §6 row read is a **visible
bracket** and a **card that glows**; A loses the glow to mush and B loses the bracket first as
the size drops. C keeps both at every size the app draws. **B is one number away** and section 8's
rule applies: it was not chosen, it was not eliminated.

## 12. The light-theme ground — derived, and it loses

**Asked for on 2026-09-05 and answered on the sheet rather than in a sentence.** Sheet:
`logo/sheets/light-ground.html`, render `logo/pass-light-ground.png`. Re-render:

```
node docs/specs/logo/sheets/shot.mjs $PWD/docs/specs/logo/sheets/light-ground.html /tmp/light.png 1300 1000
```

The mark is a dark tile in both themes. The question was whether a light ground can be derived
for it the way the dark one was — the prism's own hue, driven the other way.

**It can be derived. It loses to the mark it would replace.**

### The derivation is sound; the object is not

Section 3's rule runs upward without modification, and `grounds.py` produces the light grounds by
the same arithmetic that reproduces all twelve dark stops. Two walls appear that the dark side
never meets:

- **sRGB runs out.** Above L 0.94, and above chroma ratio 0.39, the ground leaves the gamut and
  the hex is a clip rather than the prism's hue. The dark side has no equivalent — there is
  always room below.
- **The chroma ratio stops mattering.** Swept 0.23 to 0.70, the five tiles are one tile. Section
  7 rule 7: the just-noticeable difference has been reached and further sweeping is noise.

### Why it fails, and section 3 already knew

**The mark is a lit object on a dark ground, and both of its parts are light.** The chrome
bracket runs `#FFFFFF` → `#8FA4B8`; the prism runs `#E4EEF8` → `#6086AC`. Put either on a
near-white tile and it stops being an object. On the sheet, **chrome and platinum brackets are
not faint — they are invisible.**

This is section 3's own elimination of the `inverted` ground, arriving again from the other
direction: *"the sheen substitutes for the top of the ground gradient but not the bottom."* A
light ground has no bottom to fall to and nothing to light.

**The fixes were tested and each one costs the mark.** Cream, pale gold and bronze brackets are
visible on a light ground — because they are warm against a cool tile, which makes a bluesteel
mark two metals, the exact thing section 8 says "black and gold" was invented to avoid. A dark
card base helps the card sit and does nothing for the tile. A dark bracket **with** a dark card
is legible, and is a different mark: the foil stops reading as foil, because a holographic
surface needs a dark surround to look lit.

Put beside the locked mark on the app's own light page — section 7 rule 1, with the incumbent
present so that "worse" is available as an answer — **the locked dark mark wins, and not
narrowly.**

### The first version of this section argued it on a broken comparison

**§6 of that sheet drew three of the six dark marks with a ground this file had already
eliminated.** It derived all six grounds from the tonal rule, and for `rich`, `wg_warm` and
`rg_classic` the tonal rule produces the espresso — `#331E00`, `#26221B`, `#341C12` — that
**section 8 rejected in favor of true black.** Section 9's locked grounds for those three are
`#141619` → `#000000`. So the comparison that was put up showed light against a dark row that
was one-half a set of drawings this file says are wrong, and it flattered light by exactly the
amount section 8 had already measured.

Corrected, the dark row is stronger than the one that was reviewed: true black behind a gold
foil is the whole point of section 8, and the espresso is what section 8 says removes it.

**The finding this cost is worth keeping.** A sheet that DERIVES a value the file has LOCKED
will silently redraw a rejected option, because a derivation does not know it was overruled.
Section 9's table is the authority for the six grounds and a sheet must read it, not re-derive
it. `light-ground.html` now carries `LOCKED9` written out for that reason.

### And the light family does not survive being small, which is the whole app

The corrected §6 is a fair fight and the light row is genuinely attractive at 150px — six tinted
tiles, each with its card glowing. **That is not the question the app asks.** Drawn at 44 / 32 /
28 / 16px on the app's own light page, the light tiles **lose their silhouette**: a near-white
tile on a near-white page has no edge, so the mark stops being an object and becomes a smudge.
The dark tile keeps a hard silhouette at every size, on both page colors.

**So the answer is not "light is worse."** It is that light is a display-size idea and every
surface in this app is below 64px — the same boundary section 3 draws for the two optical cuts,
arriving from a completely different direction.

### The recommendation, and what would reopen it

**The mark stays fixed dark in both themes**, and the reason is the size rather than the taste. It is an object, not an ink color: an app icon on
a phone home screen does not invert when the phone does, and this is the same kind of thing.
What changes is the placeholder's behavior — `Logo` today is drawn in `--bn-ink` on `--bn-bg`
and so inverts — and the change is deliberate rather than a regression.

**What is NOT eliminated**, in section 8's sense of the word: the dark-bracket, dark-card mark on
a light tile is a real drawing that a person could prefer, and its stops are on the sheet. It was
not chosen, once, by one person, on one day. `logo/sheets/light-ground.html` §7 puts it back on
screen.

## 13. The lockup — recovered, and given tails

**THIS PASS WAS LOST AND HAS BEEN RECOVERED, WHICH IS THE THING TO READ FIRST.** The lockup was
drawn on `claude/logo-state-of-record`, judged over eleven sheets in one session, and **never
committed** — that branch carries three files under `logo/` and none of them is a lockup. §4 of
this file already records the lesson it repeats: *"the generators are committed now because they
were lost once already. Every sheet this design has been judged on was built in a session
scratchpad and thrown away with it."* The rule was written and then not applied to the next
thing drawn.

It survived only because a temporary directory had not been cleaned. `sheets/lockup-tight.html`
is that sheet, committed verbatim, and `sheets/lockup-tails.html` continues it.

**A session that draws a pass and does not commit its generator has not done the work**, however
good the render is. The render goes to the owner and the parameters go nowhere.

### What was approved, written down

Recovered from the generator rather than from memory:

| what | value |
| --- | --- |
| Kanji | Hiragino Sans, `letter-spacing: .07em` |
| Roman | Manrope 700 at **0.36×** the kanji, tracked by iteration until its measured width equals the kanji's, then pulled back by the trailing unit |
| Roman opacity | **0.62** — the roman is subordinate by tone, not only by size |
| Case | all caps |
| Padding | fractions of the kanji size; `0.28` and `0.22` are the two kept |
| Line gap | `0.06` of the kanji size |
| Bracket stroke | **`0.050`** of the kanji size — swept over five rounds, see below |
| Bracket arm | `0.32` |
| Bracket corner radius | **`1.85 × stroke`** — a value §3 never names |

**The roman's 0.62 opacity is not in §3's table and is doing real work.** It is what makes the
roman read as subordinate at a size that would otherwise compete, and it was recovered from the
generator; nobody had written it down.

### The settled values, and the one place they live

**This table is the store of record for the lockup's parameters, and `make docs-audit`'s
`lockup params` row reconciles it against `sheets/lockup-round.html`'s declared holds in both
directions.** A value settled in a round and then typed a second time somewhere else is how the
two caption bugs in that sheet happened, twice, in the same row.

| key | value | settled |
| --- | --- | --- |
| `pad` | 0.50 | rounds 16–20, closed on the pixel floor |
| `gap` | 0.08 | rounds 21–23, answered in the column |
| `stroke` | 0.050 | rounds 1–5 |
| `arm` | 0.32 | round 24 — carried, and CONFIRMED rather than moved |
| `rrMul` | 4.0 | rounds 6–10, closed on the JND |
| `tip` | 0.15 | round 13 |
| `tl` | 0.70 | rounds 11–12 |
| `romanSize` | 0.25 | rounds 28–31 |
| `romanFill` | 0.75 | rounds 25–27 |
| `romanTrack` | 0.14 | a SEED, not an answer — see below |
| `romanOpacity` | 0.45 | rounds 32–34, with a stated exception |

**A key in this table is not the same as a key that has been argued.** The `settled` column says
which is which, and it is the only place that says it — a value carried from the recovered pass
and a value chosen against four alternatives look identical once they are both just numbers.

**The three `roman*` keys were literals in `sheets/lockup-core.js` until round 25, and that is
why they are last.** Everything else here has been reconciled against this table on every commit
since the `lockup params` row landed; those three were typed into the markup, so they could not
be swept, could not be declared as held, could not be asserted against the drawing, and could
not disagree with this file in any way anything would notice. **A parameter that is not a
parameter is outside every guard this project has**, which is the general form of it.

**`romanTrack` is in this table and is not a settled value, and that distinction was found by
publishing it as one.** `frame()` runs a thirty-iteration solve that width-matches the roman to
the kanji by rewriting `letter-spacing`, which is the recovered pass's whole reason for existing.
So the 0.14em is a *seed*: it changes how many iterations the solve takes and nothing else, and
it is overwritten before anything is drawn. Published as settled it would have been a number in
this file that **no drawing on any sheet has ever used** — the same defect as a caption naming a
value the picture beside it does not have, one level further back. The drawing now records
`romanTrackSolved`, the tracking that actually reached it, and **it cannot be swept**: it is
derived, and §7 rule 6 has nothing to hold constant while it moves.

### The roman's opacity, settled over three rounds — and the light theme sits under a floor on purpose

**0.45 of the ink.** It replaces the 0.62 carried from the recovered pass.

| round | offered | kept | what it proved |
| --- | --- | --- | --- |
| 32 | 0.35 – 1.00 | 0.35 – 0.62 | the low end was not bracketed |
| 33 | 0.20 – 0.58, **both grounds** | 0.27 – 0.45 | the grounds are not mirrors |
| 34 | 0.35 – 0.50, against a floor | 0.45 | one value clears, on one ground |

**An opacity is the only parameter in this set whose failure can be measured rather than judged**,
and two measurements were built for it. The caption prints the WCAG ratio against the specimen's
own ground. `sheets/ink.mjs` counts, at the floor size and at `deviceScaleFactor: 1`, how many
pixels the letterforms reach at each of six distances from that ground.

**The two grounds are not mirrors, and the figures say by how much.** The same alpha carries about
a quarter more contrast on dark — 0.35 reads 2.98:1 there against 2.27:1 on white. Light gives
sharper peaks and fewer pixels; dark gives lower peaks and broader coverage, because antialiasing
a light stem onto a dark ground spreads outward rather than thinning.

**The bar is this product's, because WCAG declines to supply one** — it exempts logotypes from
contrast minimums outright, so citing 4.5:1 would be borrowing authority the standard withholds.
`tokens.css`'s faintest ink, `--bn-ink-4`, carries its own note: *"this is the floor a word may
sit at, never a caption."* Solved per channel against the panel each theme draws on — `#ffffff`
and `#14171c` — **that floor is alpha 0.50 on light and 0.45 on dark.**

**So the light theme sits under its own floor, and that is a decision rather than an oversight.**
0.45 reads 4.09:1 on dark, clearing 4.0; and 3.02:1 on light, under 3.6. 0.50 was drawn and would
have cleared both — the owner chose 0.45 with the cost named. Two things make it defensible: the
roman repeats information the kanji already carries, and ink-4's note was written for interface
text rather than for a logotype's second line. **A later session finding the light theme under
that floor should read this paragraph before "fixing" it.**

**The reopening condition is a theme-dependent opacity**, which was considered and rejected here:
dark could take a lower value on the same argument, and two numbers is where a mark starts
becoming two marks.

### The roman's size, settled over four rounds — and the last one changed the instrument

**0.25 of the kanji — a quarter.** It replaces the 0.36 carried from the recovered pass, which
is the largest move any value in this series has made.

| round | offered | kept | what it proved |
| --- | --- | --- | --- |
| 28 | 0.24 – 0.48 | 0.24 – below 0.36 | the low end was not bracketed |
| 29 | 0.14 – 0.34 | 0.19 – below 0.34 | both ends failed |
| 30 | 0.20 – 0.33 | 0.23 – 0.27, undecided | the step reached 1.1px at the floor |
| 31 | 0.23 – 0.27, **at true pixels** | 0.25 | the rounding was the whole difference |

**With `romanFill` settled first, this sweep asks about weight rather than length.** Every
specimen occupies the same 77px, because the solve holds it there — so what moves is the roman's
presence against the kanji. Round 25 deferred the size for exactly this reason: a size judged
against a moving width is judged against nothing (§7 rule 6).

**Round 31 is where the method had to change rather than stop.** The step was 0.01, which is
0.32px of type at kanji 32 — and a sheet cannot ask anyone to choose between two drawings a third
of a pixel apart. **Drawing them larger is the wrong fix**, and §9's small row is this project's
own record of making it: shot at `deviceScaleFactor: 2`, its "28px" tiles carried 56 real pixels,
in the one row whose whole job was to demonstrate a failure. So `sheets/pixels.mjs` does the
opposite — it renders at `deviceScaleFactor: 1`, which is what a 1× display gets, and magnifies
the resulting **bitmap** with smoothing off. **At this step the screen's rounding is the entire
difference**, and that is the only form of the question with an answer: at the floor, 0.23 and
0.24 lose the counters of B and C, 0.26 and 0.27 hold their stems, and 0.25 is the crossover.

**One crop per specimen, stacked.** A magnified row of five is six thousand pixels wide, and any
client that receives it scales it back to fit — which undoes the magnification exactly and leaves
an image that looks like evidence and is not.

**Two failure modes bound this variable and they are at opposite ends.** Below, legibility, and it
binds at the floor size first: a 0.14 roman is 4.5px at kanji 32. Above, the fill — held at 0.75,
so past about 0.43 the type's natural width exceeds the target and the solve tracks **negative**,
crowding the letters. The sheet prints the solved tracking and flags a negative one in the
rejection red.

### The roman's run, settled over three rounds — and the parameter did not exist when they started

**0.75 of the kanji's width.** The roman is tracked out to three quarters of 番地 and hangs left.

| round | offered | kept | what it proved |
| --- | --- | --- | --- |
| 25 | 0.62 – 1.00 | 0.62 – 0.88 open | both ends failed on the first pass |
| 26 | 0.66 – 0.87 | 0.66 – 0.83 open | the incumbent survived a forced choice |
| 27 | 0.68 – 0.82, **incumbent absent** | 0.75 | it won without it in the row |

**`romanFill` did not exist before round 25, and the reason it had to is a defect.** `frame()`
has always contained a thirty-iteration solve that tracks the roman out to match the kanji's
width. **It never ran.** `.go` and `.rom` are both `display:block`, so
`getBoundingClientRect().width` returns the *containing block's* width for either — the same
number, always — and `kw - rw` was identically zero. The loop exited on its first iteration
having already written `letter-spacing: 0px`, and that assignment destroyed the 0.14em seed
before anything was drawn. A `Range` measures inline content regardless of the box's display,
which is the fix.

**So every lockup in rounds 1 – 24 carried zero tracking on the roman**, and the width it filled
— 0.775 of the kanji at roman 0.36 — was never chosen by anyone. It was where Manrope lands.
**It is also not stable**: the unmatched roman fills a different fraction at every roman size, so
the relationship being judged would have moved the moment the size did. As a fraction it is the
same shape at every size, which is the difference between a design and a coincidence.

**Shown the repaired match, the owner rejected both states** — flush right was too much, and the
accident was not a choice — which is what made it a parameter rather than a switch.

**Round 27 is the one worth reading twice.** 0.775 had sat in two consecutive rows and been kept
both times, and nothing in the method could yet distinguish *good* from *familiar* — the eye had
twenty-five rounds of practice with that exact drawing. So it was **left out of the final row**.
0.75 won against four alternatives with the familiar one absent, and it is 2.6px from the
accident at the sidebar size: **the incumbent was near-optimal, and not optimal.** A control that
is never removed cannot tell you which of those it is.

**Below the natural width the tracking goes negative and the letters tighten**, which is a floor
rather than a taste. The sheet prints the solved tracking and flags a negative one in the same
red it uses for a rejection.

### The line gap, settled over three rounds — and the first answer that came from the column

**0.08 of the kanji size**, between 番地 and BANCHI. It replaces the 0.06 carried from the
recovered pass, the second and last value this series inherited rather than chose.

| round | offered | kept | what it proved |
| --- | --- | --- | --- |
| 21 | 0.00 – 0.38 | 0 – below 0.24 | zero survived, and zero is a floor |
| 22 | 0.00 – 0.23 | 0.08 picked | picked off the **context** row |
| 23 | 0.02 – 0.14 | 0.05 – below 0.11 | the step reached 1.4px |

**Rule 5's one legitimate exception is recorded here rather than left to look like a lapse.**
Round 21 ended with 0.00 — the smallest value offered — inside the kept band, which normally
means the range anchored the answer and the sweep must be reopened wider. It cannot be, because
**there is nothing below zero to offer.** The low end is bracketed by geometry rather than by
taste, the same way §11's size floor was bounded by 番's counters closing rather than by anyone's
preference. Two of the padding's five rounds were spent on genuinely unbracketed ends; this is
not one of those, and a later session should not read it as one.

**That zero was kept is a finding.** The roman is allowed to sit hard under the kanji, reading as
one block rather than two lines. It lost to 0.08, but only by a round.

**0.08 came off the context row, and no other answer in this series did.** It was not among the
sweep row's values at all — it was drawn only inside the 212px sidebar column, which had been
added in round 18 on the argument that air always reads calmer with nothing to be calm against.
That is the evidence for the row, and the rule it earns: **where the two rows disagree, the
column wins.**

**The stop is the same measured one the padding used.** Round 23's step was 1.4px at the sidebar
size — finer than the 1.9px that closed the padding — and 0.08 is the midpoint of the final
0.05 – 0.11 bracket, taken under §7 rule 7 rather than split into a twenty-fourth round.

### The padding, settled over five rounds — and rule 5 fired twice more

**0.50 of the kanji size, each side.** It replaces the 0.22 carried from the recovered pass,
which had been the ground under fifteen earlier rounds without ever being offered against
anything.

| round | offered | kept | what it proved |
| --- | --- | --- | --- |
| 16 | 0.10 – 0.36 | 0.22 and up | the top end was not bracketed |
| 17 | 0.22 – 0.52 | above 0.28, up | the top end was not bracketed **again** |
| 18 | 0.34 – 1.25 | 0.34 – below 0.72 | both ends failed at last |
| 19 | 0.30 – 0.70 | above 0.40 – below 0.60 | both ends failed again |
| 20 | 0.42 – 0.58 | above 0.46 – 0.54 | the step reached 1.9px |

**Rule 5 fired twice, and the shape it took is worth recording.** Rounds 16 and 17 each ended
with the largest value offered still in the kept band, so neither said anything about where the
top was. More than that: **0.22 was kept in round 16 and rejected in round 17.** The drawing did
not change between them — the company it kept did. That is what a range does to an eye, and it
is the reason rule 5 exists rather than a lapse by the person answering.

**The round that broke the anchor ran to 1.25 — padding wider than the kanji is tall.** Only a
range too wide to anchor could tell a real preference from a tracked one, and 0.72 failed the
moment one was offered.

**The stop is measured, not felt.** Each caption prints its own gap from the specimen before it,
so the size of the question is on the sheet. Round 20's step was 1.9px of padding at the sidebar
size; the next halving is 0.96px, and a sheet asking for a choice between two drawings a pixel
apart is measuring the monitor rather than the design. The final bracket was 0.46 – 0.54 and
**0.50 is its midpoint**, taken under §7 rule 7 rather than split further.

**One value failed by measurement rather than by eye**, and it is the only one in this variable
that did: at 1.25 the block is 229px wide and the sidebar gives 212px, so it is outside the
product before taste gets a vote.

**What the sweep found that was not about padding.** Past about 0.40 the padding stops being the
visible difference and the height of the brand block becomes it — 108px of sidebar column at
0.42 against 124px at 0.58, above a nav that begins immediately underneath. That is why the
sheet gained a third row drawing each value inside the 212px the shell actually gives; on white,
more air always reads calmer, because there is nothing for it to be calm against.

### The stroke, settled over five rounds

**`0.11` was the recovered value and it is wrong once the bracket is tapered.** The owner's first
word on the tails was that they read too thick, and five rounds of forced choice put the stroke at
**0.050 of the kanji size** — less than half what the recovered pass carried.

| round | offered | taken |
| --- | --- | --- |
| 1 | 0.045 – 0.140 | 0.045 – 0.085 |
| 2 | 0.018 – 0.085 | 0.026 – 0.045 |
| 3 | 0.026 – 0.045 | 0.036 – 0.045 |
| 4 | 0.036 – 0.056 | 0.045 and 0.050 |
| 5 | forced pair | **0.050** |

**§7 rule 5 fired twice and both times the range was mine.** Round 1's band reached its own floor, so
round 2 opened downward; round 3's reached its own ceiling, so round 4 opened upward — and opening
upward exposed a hole nobody had noticed, that 0.045 was good and 0.065 was not with *nothing between
them ever drawn*. A 44% step had been standing in for a bracket.

**Rounds 1 and 2 disagree, and that is rule 3 rather than a contradiction.** 0.065 and 0.085 were
accepted the first time and passed over the second, once they were shown against thinner neighbors and
at size. §6 records the identical narrowing for the sheen.

**The last step was decided by a measurement, not by the eye.** 0.045 and 0.050 are a fifth of a pixel
apart at kanji 40 and another bisection would have been noise (rule 7). What separates them is that the
stroke is a *fraction* of the kanji size, so it shrinks with the lockup: **0.050 holds a whole pixel down
to kanji 20, and 0.045 gives out at 22.2.**

**What this leaves open, and it is not small.** The corner radius was pinned at `1.85 × 0.110` for the
whole sweep so the stroke could move alone (§7 rule 6). At the settled stroke that pin is **4.07 × the
stroke**, where the recovered rule says 1.85 ×. Every specimen judged across those five rounds carries a
corner more than twice the rule's — so the radius is not merely unswept, it is currently *wrong*, and it
is the next round.

### The corner radius, settled over five rounds — and it is 0.20 of the kanji size

**`1.85 × stroke` was the recovered rule and it is eliminated.** Rounds 6 to 10 swept the radius as a
multiple of the stroke, and the multiple the original pass shipped lost in round 7.

| round | offered | taken |
| --- | --- | --- |
| 6 | 1.0 – 7.0 × | 1.85 – 5.5 × — both ends failed, 1.0 "far too square" |
| 7 | 1.85 – 5.5 × | 2.6 – 5.5 × — the recovered rule out |
| 8 | 2.6 – 6.2 × | 3.3 – 5.5 × — both ends failed |
| 9 | 3.3 – 5.5 × | 3.85 – under 5.5 × — 5.5 out after surviving three rounds |
| 10 | 3.85 – 4.95 × | **all five alike — the JND** |

**Round 10 ended on §7 rule 7 and the claim is measured rather than reported.** Rendered at true size
and subtracted pixel for pixel, adjacent specimens at kanji 40 differ by a mean of **0.7 to 3.5 out of
255** — under 1.4% — with the deviation confined to a few dozen pixels at each corner. "About the same"
is a result, and here it is a number.

**The pick is `4.0 × the stroke`, which is `0.20` of the kanji size, and the reason is not aesthetic.**
The radius sat pinned at `1.85 × 0.110` through rounds 1 to 5 so the stroke could move alone; at the
settled stroke that pin is **4.07 ×**. Every judgement about the stroke was therefore made against a
corner of 4.07. Picking anything far from it would mean the stroke was chosen against a corner that
does not ship. 4.0 is **0.34px from the pin at kanji 96** — a tenth of the difference the JND
measurement already calls invisible — and it is a round number in both expressions: 4.0 × the stroke,
0.20 of the kanji size.

**A finding this sweep produced twice, by accident, and which belongs in §7.** A value at the END of a
row is not being tested the way an interior one is. 5.5 × was accepted in rounds 6, 7 and 8 while it
sat at the top of the row with nothing above it and a coarse step below; the first time it had 4.95 and
4.4 pressed against it, it lost. §6 records the same shape for the sheen and §3 for the ground, both
times as "shown a second time it failed". The sharper statement is that **a row's endpoints are weak
evidence regardless of how many times they are shown**, and the fix is to crowd them rather than to
re-show them.

### The tail's ramp, settled at 0.70 — and the clamp finally has a number

| round | offered | taken |
| --- | --- | --- |
| 11 | 0.15 – 0.75 of the arm | above 0.30 – 0.75 — reached my ceiling |
| 12 | 0.38 – 0.80 | **0.70** |

**Round 11's ceiling was mine; round 12's was the geometry's.** §6 records that the taper routine
clamps the ramp at half the path and that above the clamp every value renders identically — and never
says where the clamp is, so each session has rediscovered it by walking into it. **On the settled
geometry it binds at `tl` 0.82**, reaching 63.0px at kanji 96; **0.80 is the largest fraction that
still draws something new.** Round 12 therefore spanned the entire remaining possibility, and 0.70 is
interior to it.

### The tip, settled at 0.15 — and why the radius argument does not transfer

Round 13 offered 0 to 0.40 of the stroke and both ends failed on the first offer: a true point out, 0.25
and 0.40 out. The survivors, 0.07 and 0.15, were called meaningless to tell apart, and they are — a
bisection would have offered steps of **0.096px at kanji 96**, a tenth of a pixel.

**So it was decided on a criterion rather than an eye, and the criterion is whether the taper
TERMINATES or DISSOLVES.** A stroke whose end is sub-pixel fades into antialiasing; one that crosses a
whole pixel ends definitely.

| tip | reaches 1px at | |
| --- | --- | --- |
| 0.07 | kanji 286 | never, in practice |
| **0.15** | kanji 133 | reachable at a README or display size |

**0.15 is the only value in the accepted band that ever gives the tail a resolvable terminal**, and it
costs nothing at small sizes because both are sub-pixel there anyway.

**The consistency argument that decided the radius deliberately does NOT apply here, and the difference
is measurable.** The radius was pinned at 4.07 while five rounds of stroke were judged, and at kanji 96
that pin is **19.54px** — it drove every judgement, so moving far from it would have invalidated them.
The tip across those same rounds was **0.34px at kanji 96 and 0.08px at kanji 22**: under a third of a
pixel, and it drove nothing. Consistency binds a parameter that was visible while other things were
being judged. It does not bind one that was invisible. Applying the same rule to both would have been
the rule spreading past its own argument.

### The size floor is kanji 32, and the bracket is not what sets it

**Measured at deviceScaleFactor 1 and magnified by whole pixels**, because a floor judged on a 2×
render is judged at twice the detail a 1× screen gives — which is exactly what §9's small row did.

Three things give out, and they give out at different sizes:

| kanji | block | 番 counters (p10) | roman | bracket |
| --- | --- | --- | --- | --- |
| 40 | 104 × 74 | 1.33 | 14.4 | 2.00 |
| 32 | 83 × 59 | **1.07** | 11.5 | 1.60 |
| 26 | 68 × 48 | *0.87* | 9.4 | 1.30 |
| 22 | 57 × 41 | *0.73* | *7.9* | 1.10 |
| 18 | 47 × 33 | *0.60* | *6.5* | *0.90* |
| 14 | 36 × 26 | *0.47* | *5.0* | *0.70* |

**The kanji fails first, at about kanji 30. The roman second, about 24. The bracket last, about 20.**

**So the floor is `kanji 32` — a block of about 83 × 59px — and the thing that sets it is 番's
density, not the bracket.** That is worth stating plainly because it is the opposite of what fourteen
rounds of bracket refinement would lead anyone to assume: the part that was swept hardest is the part
with the most headroom, and it is the last of the three to break.

**The metric is the tenth percentile of 番's interior whites**, measured off the rendered glyph — the
point at which a tenth of its counters stop being resolvable and a dense glyph begins filling in. The
*minimum* was tried first and is useless: it is a single near-tangent between two strokes and reads
0.02 – 0.07px at every size, which measures antialiasing rather than legibility. The median is the
typical counter and stays comfortable everywhere. Only the p10 moves through the range that matters.

**What this settles about the sidebar.** The expanded sidebar is 236px and holds a kanji-32 lockup
with room to spare. The 64px rail cannot: the block at kanji 22 is already 57px wide and two of the
three measures have failed by then. **The lockup is an expanded-sidebar object and the rail needs
something else** — which is the bare-bracket question §13 leaves open.

### The sidebar, and the rail's own two values

Sheet: `logo/sheets/sidebar-morph.html`. **The lockup when the sidebar is open, the bare brackets when
it is a rail** — the owner's idea, and §1's own description of the mark: *"with the card removed the
same brackets become an empty slot, which is the in-product mark."*

**Neither size is chosen; both are what fits.** The expanded sidebar is 236px with 12px padding, so the
lockup sits at **kanji 32** — exactly the floor above — with a block of 83 × 59px inside 212px of
usable width. The 64px rail **cannot hold the lockup at all**, which is why it gets brackets rather
than a smaller lockup.

**The rail's bracket does NOT inherit the lockup's rules, and that is a correction rather than a
choice.** `rrMul` is 4.0 × a stroke of 0.050 — 0.20 of the kanji. Applied to a rail bracket at 0.11 of
its frame, 4.0 × gives 0.44 of the frame: an arc with no arm left, which is what the first draft drew.
The rail takes the icon's own proportion instead.

| | rail |
| --- | --- |
| stroke | **0.11** of the frame — swept at 44px and 64px, both ends failing |
| radius | **0.146** of the frame — the icon's 8 in a 54.8 box |

**The morph is drawn rather than described.** Both brackets are the same routine at the same point
count, so the path interpolates directly and the sheet's filmstrip is real intermediate geometry at
five points, not a cross-fade standing in for one. **Both rules change across the move** — 0.050 of the
kanji becomes 0.11 of the frame, 4.0 × the stroke becomes 0.146 of the frame — so each end is resolved
to pixels and the pixels are interpolated. Interpolating the *rules* sends the middle frames somewhere
neither end goes; the first draft did exactly that and carried a stroke seven times too heavy through
the middle.

**What the mockup puts in front of a decision.** At the rail the brackets enclose nothing. §1 says that
empty slot *is* the mark, and the drawing is the first chance to judge whether it reads that way or
reads as a frame around an absence.

### The tails

The brackets were plain stroked paths with round caps. They carry the icon's tapered outline now,
off the same `taperParts` the sheet already used for the icon — asked for on 2026-09-05.

**The clamp is at 0.82 on this geometry, and §6 never said where it was.** That entry records the
defect — *"every value above that rendered identically while being presented as a sweep"* — without
ever quantifying it, so every later session had to rediscover it. Measured at the settled stroke,
radius and arm: **the ramp binds at `tl` 0.82**, where it reaches 63.0px at kanji 96 and the taper runs
from the tip to the midpoint of both arms. Above 0.82 the routine draws an identical bracket forever.
That is a ceiling on the parameter itself rather than a matter of taste, and it is the one edge in this
whole sweep that a wider range cannot move.

**§6's taper clamp came back in the sweep that added them.** `taperParts` clamps the ramp at half
the path, so a ramp fraction above that renders identically while being presented as a sweep —
*"three images approved as different were the same image."* At pad 0.22 the clamp binds at 0.80.
The sheet prints the ramp actually used under every specimen and marks a clamped one in orange,
so the defect is visible rather than silent. **A sweep whose top end is clamped is not a sweep,
and the only defense that has ever worked here is printing the number.**

## 14. The lockup's font — what it cannot ship with, and what it can

**Drawn 2026-09-05, on the owner's instruction to take the lockup next.** Sheet:
`logo/sheets/lockup.html`. Re-render:

```
node docs/specs/logo/sheets/shot.mjs $PWD/docs/specs/logo/sheets/lockup.html /tmp/lockup.png 1420 1000
```

**It works.** 番地 over BANCHI inside the same diagonal brackets reads as a member of the family
at 420, 260 and 150px, in both themes, and §3's ×0.93 dark-mode stroke correction does what it
says — the two weights read the same. Below about 150px wide the roman's tracking becomes
fragile and the lockup should hand off to the icon.

### §3 asked for a width match and did not say which width

*"Tracked until it is exactly as wide as 番地"* has two answers, and they differ by 7.7%.
Measured on this machine at kanji size 100, so every figure is also a fraction of the em:

| | 番地, Hiragino Sans, tracked 0.07em | BANCHI, Manrope 700 at 0.36 |
| --- | --- | --- |
| advance | **214.00** | 211.35 |
| ink width | **198.70** | 198.70 |
| ink height | 91.50 | 25.54 |
| tracking | 7.00, locked | **11.22 = 0.312em**, solved |

**CSS applies letter-spacing after every glyph including the last**, so the advance carries one
trailing unit of air the ink does not. Matched on advance, the roman overhangs the kanji's
visible edge on both sides by half that unit. **The match is on INK**, and the sheet's §1 puts
both up with their measured ink boxes drawn so the choice is a forced pair rather than an
assertion.

### AMENDED 2026-09-06: the match is on the ADVANCE, and the code was always right

**The table above says the match is on ink, and `sheets/lockup-core.js` has always solved against
the advance.** §15 found the disagreement and left it open; this closes it in the code's favour,
because **every one of §13's thirty-seven rounds judged the advance-matched drawing.** Moving the
solve to ink now would silently change a value the owner approved against a picture that would no
longer exist — and `romanFill` would have to be restated as 0.807 of the ink for the same drawing.

So `romanFill` **0.75 is 0.75 of the advance**, and the paragraph below stands as the argument for
what the difference IS rather than as a rule the code breaks. Re-opening it means re-offering the
round, not swapping the definition.

**Nothing is positioned by line box.** Hiragino's font box is 88 up / 12 down on a 100 em;
Manrope's is 92 up / 23 down — 115 units on the same em. Stacking the two by their line boxes
puts the optical center in the wrong place by construction.

### The bracket corner radius is this section's own HELD value

§3's lockup table names a stroke and an arm and no radius. The icon's 8 cannot simply travel:
its bracket box is 54.8 x 67.5 and the lockup's is a different shape entirely. The sheet sweeps
1.0 / 1.6 / **2.2** / 3.0 / 4.2 multiples of the stroke and 2.2 is drawn as the pick. **It is
HELD in §2's sense — chosen once, never tested against a second eye** — and it is named here
rather than buried, which is the whole point of that tag.

### THE FONT CANNOT SHIP, AND THAT IS A CONTRACT PROBLEM RATHER THAN A COPYRIGHT ONE

`Hiragino Sans` is LOCKED in §3 and is on every Mac. **Extracting its outlines into this
repository is not permitted by the license this machine holds.** macOS SLA §2E grants the fonts
only *"to display and print content while running the Apple Software"*; §2N forbids derivative
works of any part of it. The `fsType` bit on all ten weights is 8, Editable embedding — that
governs embedding the FONT into a document and is **not** authority to ship extracted outlines.

**So the sheet is a judging reference and not a deliverable.** It sets live system text, which
is exactly what the license permits, and it renders only on a Mac. Nothing generated from it may
be committed.

**The framing matters, because the obvious conclusion from that paragraph is wrong.** Typeface
*designs* are not copyrightable in the US — *Eltra v. Ringer*, and the Copyright Office's own
1988 rule that digitized typeface designs are not registrable. What *is* protected is the font
file's control-point data (*Adobe v. Southern Software*, N.D. Cal. 1998). Japan sets a higher
bar still: the Supreme Court's 2000 *Gona U* decision requires distinctive originality **and**
artistic quality, and SCREEN markets Hiragino in precisely the disqualifying terms —
*"orthodox, universally preferable and with excellent readability."* **The exposure is the
macOS agreement, not the typeface.** A spec that says "we cannot use this typeface" would be
wrong and would push toward a redesign nobody needs.

### Three ways out, measured rather than guessed

| route | what it costs | what it costs the repo |
| --- | --- | --- |
| **Adobe Fonts** — Hiragino Kaku Gothic ProN | a Creative Cloud subscription | the generator runs only on a licensed Mac |
| **MyFonts** — Hiragino Sans W0–W9 | $109 – $210 per weight, perpetual | same, minus the subscription |
| **Vendor an OFL face** | nothing | re-runnable forever, and a real departure from a LOCKED row |

**Adobe Fonts is the same drawing, not a lookalike, and that was checked rather than assumed.**
All four faces in `ヒラギノ角ゴシック W6.ttc` point at one CFF table at one offset, and 番
extracted from face 0 (Hiragino Sans W6) and face 2 (Hiragino Kaku Gothic ProN W6) is
byte-identical. Adobe's font licensing terms permit exactly the operation the lockup needs:
convert type to outlines, modify them, and trademark the result — only modifying the font
software file is barred.

**No open face is a drop-in, and the closest one is not the obvious one.** Rendered to a
normalized 200x200 mask and scored by intersection-over-union against Hiragino W6:

| face | IoU vs W6 |
| --- | --- |
| **IBM Plex Sans JP 700** | **0.848** |
| BIZ UDPGothic 700 | 0.836 |
| IBM Plex Sans JP 600 | 0.830, and its ink ratio matches W6 exactly |
| Noto Sans JP 700 | 0.785 |
| Noto Sans JP 500 | 0.762 |

**`Zen Kaku Gothic New` is ruled out on a measurement rather than on taste.** It draws 番 nearly
5% wider relative to the em than 地, where Hiragino keeps the pair within 0.5% — in a two-glyph
lockup that reads as visibly unbalanced.

An 85% outline overlap is not a shape match. **Substituting is a design change to a LOCKED row,
not a like-for-like swap**, and it is the owner's call rather than a session's.

### DECIDED 2026-09-06: IBM Plex Sans JP 400, and the weight is the correction

**The owner chose the OFL face on seeing it drawn**, weight-matched, at the sizes the lockup
ships. Free, re-runnable on any machine, and subset to 番地 it is about 1.1KB.

**The weight in that table is not the weight this uses, and that mattered.** §14 scores every
candidate against **Hiragino W6**, because it was written when the lockup was a display asset.
`.go` sets no `font-weight`, so all thirty-five of §13's rounds drew Hiragino at **regular** —
and the first comparison sheet put Plex **700** beside it, which compares a semibold with a book
weight and reads the difference as a typeface difference. Weight-matched, **Plex JP 400** is what
sits beside it.

**The geometry does not move at all, which was measured rather than hoped.** At kanji 100, 番地 is
214.00px advance / 199px ink in Hiragino and 214.81 / 200 in Plex 400. Re-rendering §13's settled
lockup on the new face at 32, 40, 48, 64 and 80 gives **byte-identical block dimensions at every
size** — 102 × 75, 128 × 93, 153 × 112, 204 × 149, 255 × 186. Nothing that is a fraction of the
kanji's box changed, because a full-width em is a full-width em.

**So what the swap can still cost is optical, and only two values are exposed to it**: `romanSize`
and `romanOpacity`, both judged as the roman's weight against the kanji's. Sheet:
`logo/sheets/lockup-face.html`.

**§15's gate is discharged without re-grading them, and the reason is that neither was chosen on
taste.** Rounds 36 and 37 were built to re-offer both and then withdrawn — a forced choice is
worth an owner's attention only when nothing else can answer, and here something can:

- **`romanSize` 0.25** was picked as the crossover in the magnified raster — below it, B and C
  lose their counters at the floor size. Re-measured on Plex 400 at `deviceScaleFactor: 1`: same
  crossover.
- **`romanOpacity` 0.45** was picked against a floor derived from `--bn-ink-4`, and **a contrast
  ratio is a property of the composite color and the ground, not of the letterform.** Re-measured
  on Plex: 4.09:1 on dark and 3.02:1 on light, identical to the figures §13 recorded.

**Both criteria are face-independent, so both survive the substitution intact** — which is a
stronger claim than a second forced choice would have produced, because it says *why* the answer
did not move rather than only that it did not.

**What the face does change is pixel coverage**, and `ink.mjs` measures it: at 0.45 and kanji 32,
Plex reaches 70 of ~140 pixels at a distance of 64 on light and 95 on dark, against Hiragino's 73
and 73. The light ground loses a little; the dark ground gains more.

### The question underneath, which is not about type at all

**Every `Logo` call site in this product is 44px or below, and this lockup is not drawn below
about 150px.** There is no marketing page, no OG card, no app-store listing. The only surfaces
that could carry it are `#/gallery`, the owner's crash page if it grew, and `README.md`.

**If the honest answer is "nothing today", then the right outcome is this section and no
artifact** — the parameters recorded, the measurement made, the license understood, and nothing
built that no screen reaches. That would be CLAUDE.md's own rule applied to a brand asset rather
than to a route.

## 15. Wiring the lockup into the app — the plan

**Written 2026-09-06, after §13's thirty-five rounds settled every parameter.** Nothing in this
section is built. It is the plan, and its first item is a gate rather than a task.

### §14's closing conclusion is overtaken, and that is why this section exists

§14 ended by asking whether the lockup has a surface at all: *"this lockup is not drawn below
about 150px… If the honest answer is 'nothing today', then the right outcome is this section and
no artifact."* That was true of the lockup as it stood. **Round 15 moved the floor to kanji 32 —
a 102 × 75px block** — and rounds 16–34 settled the parameters that make it hold together there.

So the surface is real now: **the sidebar brand row**, 212px of usable width, currently drawing
`[mark] Banchi / every card has an address`. The lockup replaces all three of those, because it
already says the name twice in two scripts.

### The gate: every judgement in this series was made on a font that cannot ship

**Measured rather than assumed.** Rendering 番 at 100px through the sheets' own family stack and
differencing pixel for pixel against each candidate: the stack resolves to **Hiragino Sans, with
zero pixels different.** Not the ProN variant (1,293 pixels differ), and Noto Sans JP is not
installed on this machine at all — its "difference" equals a nonexistent family's.

§14 establishes that Hiragino cannot be redistributed and ranks the open faces by outline overlap
(IBM Plex Sans JP 700 leads at IoU 0.848). What §14 does not say — because the parameters did not
exist yet — is **which of the eleven settled values depend on the face**, and that determines how
much of this series has to be re-run after a substitution.

| parameter | face-dependent? | why |
| --- | --- | --- |
| `romanSize` 0.25 | **yes** | it was judged as the roman's *weight against the kanji's*, and no two faces carry the same stem weight at the same nominal size |
| `romanOpacity` 0.45 | **yes** | same argument, and `ink.mjs`'s counts are a measurement of one face's stems |
| `romanFill` 0.75 | **barely — measured** | see below |
| `pad` `gap` `arm` `stroke` `rrMul` `tl` `tip` | no | all relative to the kanji's **box**, and a full-width em is a full-width em |

**`romanFill` was written into this table as the most exposed value and the measurement says
otherwise.** At kanji 100, 番地 is **214.00px advance / 199px ink in Hiragino Sans** and
**214.81 / 200 in IBM Plex Sans JP 400** — 0.4% and 0.5% apart. The denominator barely moves,
so neither does the picture. The claim was reasoned from "it is a ratio to the kanji" and was
wrong; it is corrected here rather than left standing because a plan's risk table is the part a
later session acts on.

**What the substitution costs is weight, not width**, which is why the two rows above it survive.

**And one discrepancy inside this spec was found by taking that measurement.** §14 says the match
is on **ink** — *"CSS applies letter-spacing after every glyph including the last… matched on
advance, the roman overhangs the kanji's visible edge on both sides by half that unit"* — but
`sheets/lockup-core.js` solves against a `Range`'s box, which is the **advance**. So `romanFill`
0.75 is 0.75 of the advance and **0.807 of the ink**. Every round in §13 used one definition
consistently, so the settled value is sound; what is not sound is a spec asserting two things.
**Resolving that is part of the build, not a footnote**: either the solve moves to ink and
`romanFill` is restated as 0.807, or §14's rule is amended to name the advance and say why.

**So the plan is gated on the face, and the re-run is bounded.** Once a face is chosen, the three
rows above are re-offered — one round each, as a same-or-different check against the settled
value, with a full sweep only where the answer is "different". The other seven are asserted
unchanged by `lockup params` and need no eye.

### The solve is baked, not shipped

`frame()`'s width-match depends on exactly four things — the face, the two strings, `romanSize`
and `romanFill` — and **all four are fixed at build time.** Shipping the solve would mean
measuring text in a layout effect on every mount: a reflow, a flash before it settles, and a
different answer whenever the webfont arrives late. `scripts/build-lockup.mjs` runs it once and
emits the letter-spacing as a constant, the way `build-mark.mjs` already emits the mark's geometry.

**Nothing about the lockup is hand-drawn or hand-edited**, and that rule carries over from D102
verbatim: change §13's table, re-run the script.

### What gets built

| artifact | note |
| --- | --- |
| `scripts/build-lockup.mjs` | reads §13's settled table and `sheets/lockup-core.js`; writes the outlines, the baked tracking and the block |
| `app/src/kit/lockupGeometry.ts` | generated, never hand-edited |
| `app/src/kit/Lockup.tsx` | `Lockup({size, className, decorative})` |

**BUILT 2026-09-06, and the font row is gone: the type is OUTLINED and no font ships.** The plan
above called for the chosen face subset to 番地 and served as a webfont. That has a silent
failure — if the file does not arrive, the browser draws a fallback CJK face at letter-spacing
solved for IBM Plex, and nothing reports it. Outlines cannot fail that way, they render
identically on every rasterizer, and they make the lockup **the same kind of artifact as the
mark**, which already ships path data rather than text.

**The fonts are read at build time and never committed.** `@ibm/plex-sans-jp` and
`@fontsource/manrope`, both OFL-1.1, both devDependencies. Outlines are artwork rather than font
software, so §14's whole license argument is satisfied by not shipping a font at all.

**The generator carries a check `build-mark.mjs` does not have**, because outlining is the one
step that can silently change a drawing thirty-seven rounds approved: it renders the generated
paths against the live text they replace and refuses to write when more than 8% of inked pixels
differ. **That ceiling is measured, not chosen** — the residual on the settled parameters is
**6.2%**, and rendering the difference shows a one-pixel outline around each glyph and nothing on
the bracket. The woff is Plex's *hinted* build, so the browser snaps stems to the pixel grid where
a vector path does not; that is the same property that makes outlines more consistent across
rasterizers, showing up here as the cost of the comparison. A real error is not subtle at this
threshold — the first version of the check, which matched an outline's bounding box against a
`Range`'s **line** box, read 69%.

**The accessibility contract is the opposite of the mark's — and then inverts again inside a link,
which this section did not anticipate.** `Logo` is `aria-hidden` because it
sits beside the word "Banchi". **The lockup *is* that word**, so standing alone it carries
`role="img"` and an
accessible name.

**Inside the sidebar's brand it must NOT.** That element already carries its own accessible name
— since §16's correction it is a `<button>` labelled *"Collapse the sidebar"*, and an `<a>`
labelled *"Banchi home"* at the tablet breakpoint — and a named child announces the name over it.
So the one call site that replaces the wordmark passes `decorative` and both drawings are
`aria-hidden`. The a11y tree is then identical either side of the collapse, which is the right
outcome and not one this section saw coming when it wrote the rule.

**Never a `border-radius`**, for the same reason as the mark.

### Where it goes

- **The sidebar brand row**, replacing the mark, the wordmark and the tagline together.
- **The rail keeps bare brackets.** The lockup does not fit 64px: at kanji 22 the block is 57px
  and two of its three measures have already failed §11's floor. The morph between them is drawn
  in `sheets/sidebar-morph.html` as real interpolated geometry at five points, not a cross-fade.
- **`#/gallery`**, beside the mark.
- **Nowhere else.** No marketing page exists to want one.

### The guard that has to come with it

`lockup params` today reconciles §13's table against the *sheet*. Once a generated file exists it
must reconcile **both directions against that too**, exactly as `logo parity` does for
`markPalettes.ts` — otherwise the generated file is free to drift from the spec that produced it,
which is the failure `logo parity` was written for. `raw color` cannot see a `.ts` file, so the
same argued exemption applies and the same row is what makes it safe.

`app/tests/brand.spec.ts` gains the floor — a lockup below kanji 32 must not render — and the
accessible name.

### The one open question, and what would answer it

**What size does the lockup sit at in the open sidebar?** 32, 40 and 48 all fit the 212px column.
Every round in §13 was drawn at 48 and at the floor, so both ends are familiar and the middle is
not. **This is not answerable from a sheet** — it is a question about how much of a 236px panel a
brand row should eat above a nav — so it gets mockups of the real sidebar at all three, in both
themes, and a forced choice like every other value in this section.

### What would make this not worth building

Stated so it is a decision rather than a drift: **if the chosen face's re-run fails all three
face-dependent rows**, the honest reading is that the lockup was designed against a typeface it
cannot have, and the right outcome is to keep the mark alone in the sidebar and leave §13 as a
record. That is §14's own conclusion, held open rather than quietly dropped now that a surface
exists.

## 16. The sidebar — the size, and the metal on dark

**Settled 2026-09-06, against the real app rather than a sheet.** Both were judged by injecting
the lockup into the running application's own `.bn-brand` at 1440 in both themes — real sidebar,
real nav with its key caps, real Home screen in the column beside it. A sidebar drawn in
isolation cannot answer either question, and §15 said so before these were asked.

| what | settled | |
| --- | --- | --- |
| size in the open sidebar | **kanji 40** | 128 × 93px block in 212px of usable width |
| bracket on **dark** | **the locked chrome gradient** | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |
| bracket on **light** | **flat ink**, unchanged | `#0f1217` |

### The size cost nothing, which is why the floor lost

Measured in the running app, the nav's last item and the sidebar's own scroll height at each
candidate:

| viewport | kanji 32 | kanji 40 | kanji 48 | scrolls? |
| --- | --- | --- | --- | --- |
| 900 | nav ends 709 | 727 | 746 | no |
| 820 | 709 | 727 | 746 | no |

**Nothing is displaced at any height the shell is verified at**, and below about 740 the app
already shrinks the brand row itself, so the choice stops applying before it starts costing.

**So 32 lost because it is a floor rather than a choice.** §11 settled kanji 32 as *the smallest
this may ever be drawn*; a brand row is the last element that should sit at its own minimum with
no headroom. It also puts the roman at 8px — the size at which round 31 had to abandon ordinary
rendering and judge on a magnified true-pixel raster, because nothing else could resolve the
difference. At 40 the roman is 10px and off that edge.

**The argument 32 had, and lost on:** the rail draws the mark at 32, so a matching kanji would
keep identical scale across the collapse and make the morph a pure shape change. That optimises
the transition over the resting state, and the sidebar is open far more than it is animating.

### The dark bracket is the mark's own metal, and that is the whole argument

**Flat white was never a decision** — it was `--bn-ink` because nothing had asked. But the mark's
bracket has never been flat in any of the six locked variants; it is a four-stop gradient. Drawing
the lockup's bracket in flat ink makes it **a different object from the mark it is the expanded
form of.** In `bluesteel`'s bracket — the default mark's own — they are one object in one metal,
and collapsing the sidebar changes only the shape.

**Gold was drawn and declined.** It holds its tail better on dark: `#C0A254` sits further from
`#0c0e12` than silver's `#8FA4B8`, so silver's lower-right arm fades where gold's does not, and
at kanji 32 it nearly disappears. That is a real cost and it is **part of why 40 won** — the fade
is what makes the floor size expensive rather than free. What gold cannot do is be the same metal
as the mark, and that is the property being bought.

**Light is unchanged, and the asymmetry is deliberate.** Any of these gradients on the light
theme's white panel would sit far under §13's own contrast floor. A *color* that varies by theme
is ordinary — every token in `tokens.css` does it — where the per-theme *opacity* §13 rejected
would have made one drawing into two. This varies the ink and not the drawing.

**No sheet owns these hexes.** `opt.bracketStops` in `sheets/lockup-core.js` takes a palette and
never names one; `make docs-audit`'s `lockup bracket` row reconciles the sheet's four stops
against `markPalettes.ts`, and its `rail mark` row does the same for the bracket path and stroke.

### BUILT 2026-09-06 — and the collapse turned out to be a defect before it was a design

**The sidebar mounts both drawings and CSS chooses.** A JSX branch on `rail` would be wrong at
768–1023px, where `App.css` rails the shell by media query and `data-rail` is inert — a stylesheet
reads the same condition the layout does. Verified at 820: the lockup's three parts read opacity 0
and the mark reads 1.

**The rail draws the EMPTY SLOT — the brackets with the card taken out — and not the tile mark**
(corrected 2026-09-06, on the operator's report). This section shipped with `Logo` in that slot on
the reasoning that §16 settled the lockup's size and metal, not the rail's drawing. **That was
over-cautious and §1 had already answered it**: *"with the card removed the same brackets become an
empty slot, which is the in-product mark."* What shipped read as the favicon sitting above a nav.

**And it is not a second component. It is this drawing, morphed** (corrected again the same day, on
the operator's report that the lockup *disappeared* and the brackets *appeared*). The first fix
mounted a `RailMark` beside the lockup and crossfaded them; that component is deleted.

### The morph this section said was impossible

**What §16 recorded:** *"a ~600-point filled taper against a 52-byte stroked wire … paths that
shape cannot interpolate"*, and therefore a 40ms rest between two drawings, *"because showing a
tapered outline beside a stroked wire invites the eye to compare two objects the design insists are
one."*

**The claim is true of how the two are EXPRESSED and false of what they are.** Both are one L: a
vertical leg, a rounded elbow, a horizontal leg. `taperParts` in `sheets/lockup-core.js` is that L
parametrically, at a fixed 301 centreline samples — and **the mark's small cut is the same call
with `tip = 1`**, because `tip` is the width at the free end and §11 removed the taper and changed
nothing else. One sampler emits both ends at identical topology, and a point-wise lerp between them
is exact. The reasoning that closed this off compared two *files* and concluded something about two
*shapes*.

**Nothing about what the rail draws changed, and that is asserted rather than argued.**
`build-lockup.mjs` renders its untapered end against `markGeometry.ts`'s shipped stroked wire and
refuses to write if they differ by more than 2% of inked pixels at 10x. Measured: **0.30%**, which
is the antialiased boundary. The rail is still the mark's own wire (D102, §1), reached by a path
that can be interpolated instead of by a second component.

**The clock is the box.** The morph reads the slot's own animating width and derives its progress
from it. So it cannot drift from the panel it sits in, it holds no copy of `--bn-ease` — retuning
that token retunes this — and `prefers-reduced-motion` is honoured with no branch at all: `base.css`
crushes the width transition, the width jumps, and the morph lands in the same frame. The
five-delay reduced-motion override this section used to need is down to two, and the one it needed
most — the 200ms hole where the name had gone and the mark had not arrived — cannot exist, because
there is no arrival.

**The type is drawn in, not switched off.** Filmed against two alternatives at
0/40/80/120/160/220/320ms: on a pure opacity fade the name is a ghost by 40ms and gone by 80, so the
eye reads a switch and then a separate frame animation. Scaling it toward the frame's own centre, on
the slower duration, keeps it faintly legible at 80ms *inside* a frame that has already closed a
long way — which is the sentence the gesture is making. The overlap is the point.

**A defect this hid, and how.** `base.css` gives every svg `max-width: 100%` — right everywhere
else and fatal here: the slot closes 128px → 32px, the svg was capped with it, and **the whole
viewBox rescaled underneath the morph**, landing the bracket at a quarter of the mark (4.73px wide
against 18.87). Both resting states still looked plausible; it took a magnified filmstrip to see.
`app/tests/brand.spec.ts` now derives the ink box the mark's wire must occupy at 32px — reading
`markGeometry.ts` off disk rather than retyping its numbers — and measures the settled bracket
against it to half a pixel.

### The brand IS the collapse control

**Settled 2026-09-06, on the operator's instruction** — *"frankly, it should be the logo collapses
and opens the sidebar."* It replaces a 22px circular chevron pinned to the sidebar's right edge,
and the reason it replaces it rather than joining it is that the chevron was **mostly not
clickable**: `.bn-side` is `overflow: hidden` and the button sat at `right: -1px` with
`translateX(50%)`, so its outer half was CLIPPED by the panel it hung off, and whatever occupied
the content column at y = 18 — the offline banner, for instance — covered much of what was left.
Measured with probes at 50%, 65% and 85% of its own box: all three missed. About 11px of a 22px
control was real, on the affordance the whole gesture depends on.

So it moves onto the thing that is already 128 × 93. Nothing is lost by the brand no longer being
a link — Home is a nav item with its own key — and the chevron survives as a **label for the row**
rather than a control: **always drawn, and quiet** — `--bn-ink-4` at 0.55, up to full ink under the
cursor — pinned to the row's right edge by `margin-left: auto`, and gone entirely in the rail,
where 64px less two gutters leaves 48 and the mark takes 32.

**Always-visible was settled 2026-09-06 against a hover-only reveal**, from four treatments drawn
at rest and hovered. Hover-only is tidier at rest and it hides the only thing on screen that says
this row collapses the sidebar; an affordance that must be discovered before it can help is a poor
way to announce the sole control on a row. What that buys is paid for in volume rather than in
absence.

**The rule was deleted once, by accident, and shipped.** The morph commit rewrote the CSS region it
sat inside and took it with it, so the chevron rendered as a bare `.bn-icon` — full ink, always on,
no auto margin, floating 12px off the frame in the middle of a 109px row. `make check`, `make
harness` and 407 browser specs were all green: the filmstrips never hovered and nothing asserted
where it sat or how loud it was. `app/tests/brand.spec.ts` asserts both now, and the operator found
it by looking at the product.

**At 768–1023px it stays a link.** That breakpoint rails the shell by media query and ignores
`data-rail`, so a toggle there would set state the layout does not read and appear to do nothing,
which is worse than not offering one. `App` resolves that width with a `matchMedia` hook and passes
no handler, and the element renders as the anchor it was.

### The defect the choreography found, which had nothing to do with the lockup

**The rail's rules centered their children** — `justify-content: center` on the brand and
`margin: 0 auto` on every nav link — and both resolve against a width that is *animating*. Measured
at 1440 on ⌘.: the mark's centre went **36 → 114.8 → 31.5** and every nav icon did the same. The
sidebar threw itself 79px right and slid back, on every collapse, in the shipped product.

The sidebar has a spine at **x ≈ 32** and the collapse is meant to delete everything to the right
of it while nothing travels. That held at both resting states and failed at every frame between,
which is why no check could see it: a screenshot proves nothing and neither does an assertion on
either end. `app/tests/brand.spec.ts` now samples **mid-transition** and asserts a *corridor*
rather than a curve, so it survives anyone retuning `--bn-ease`.

**It then found two more of the same defect after that fix landed**, which is the argument for
keeping the test rather than treating it as a one-off:

- **The padding was given a transition and should not have been.** `.bn-side` cuts its gutter
  12px → 8px in the rail, and easing that was meant to keep the panel closing as one thing. But a
  railed nav link is a 48px box at `padding-left`, so its icon's centre *is* `padding-left + 24`:
  easing the padding dragged it **33 → 35.9 → 32**, three pixels right of both resting positions.
  It snaps now, and what that costs is 4px of gutter moving instantly under a column that eases,
  in a strip where nothing is drawn at rest.
- **The footer was never looked at.** It still centered its buttons against the animating column
  (`align-items: center`, the same shape as the nav's old `margin: 0 auto`) and measured
  **37 → 103.8 → 20.5**. Its buttons went 40px → 48px at the same time, to match `.bn-nav-link`:
  at 40 they rested at x = 20.5, eleven pixels left of every icon above them.

**And three samples was a flaky test, not a weaker one.** The padding overshoot lived in the first
~80ms, so the test failed one run in three and passed the other two on identical code. Eight
samples across the 320ms.

### Still open: the phone

**The phone top bar is 52px and the lockup at its floor is 102 × 75.** It is 23px taller than the
whole bar, and §11's floor is a measurement rather than a preference. So the bar keeps the mark at
26 beside a "Banchi" title, unchanged.

The three ways out, none of them free: **grow the bar to ~91px**, which costs 39px on the device
where vertical space is scarcest and breaks its match with the 52px tab bar; **design a horizontal
lockup**, which is a new artifact needing its own rounds; or **leave it**, which is what ships.
Recorded as a decision deferred rather than a surface nobody looked at.

## 17. The macOS app icon — the grid, and why the tile does not fill it

**Asked for on 2026-09-06, once the mark was going into the dock (D108).** The mark is a tile
that fills its frame, and every icon beside it in the dock does not. This section locks the one
number that reconciles them.

### The grid

**824pt of artwork, centered on a 1024pt canvas — 80.47% of the width.** That is Apple's macOS
icon grid, and it is not a guideline this project chose to follow: it is what the neighbors
already are. Measured on this Mac at 2026-09-06, from the shipped `.icns` of three system apps,
taking the solid body and ignoring the drop shadow:

| icon | solid body | including its shadow |
| --- | --- | --- |
| Safari | 80.47% | 87.50% |
| Mail | 80.47% | 87.50% |
| Calculator | 80.47% | 87.50% |
| **Banchi, before this section** | **100.00%** | 100.00% |
| **Banchi, after** | **80.47%** | 80.47% |

Three unrelated apps agreeing to the second decimal place is the grid, not a coincidence. A
full-bleed tile beside them is **24% wider and 55% more area**, which is what "it looks too big
in the dock" turns out to mean when it is measured.

### What is inset and what is not

**The inset is applied by drawing the mark smaller on a transparent canvas.** Section 3's
geometry is untouched — nothing here redraws the tile, changes its corner, or pads the SVG.
`scripts/build-mark.mjs` holds `MAC_GRID = 824 / 1024` and `make docs-audit`'s `mac icon grid`
row reconciles it against this section, in both directions.

| asset | inset? | why |
| --- | --- | --- |
| `app/public/icon-1024.png` | **yes** | the manifest's largest, and what a Retina dock draws from |
| `app/public/icon-512.png` | **yes** | in the manifest set |
| `app/public/icon-192.png` | **yes** | in the manifest set; 155 of 192 is 80.73%, the rounding |
| `app/public/icon-180.png` | **no** | `apple-touch-icon`. iOS masks a full-bleed square itself, and insetting would put the mark in a box inside a box |
| `app/public/favicon.svg` | **no** | a tab icon is 16 to 32px and has no grid to obey |

**The whole manifest set is inset rather than only the largest, and that is the load-bearing
choice.** Chrome builds an installed app's `.icns` by resizing the manifest icons; a set that
disagreed with itself would pad the dock icon at one size and not at the next, which is worse
than either answer applied consistently. **`favicon.svg` was removed from the manifest's icon
list** for the same reason — it is full bleed, `sizes: "any"` makes it a candidate at every
size, and one un-inset entry is all it takes.

### What is NOT done, and it is the shadow

**Every system icon measured carries a drop shadow out to 87.5% and the mark carries none.** It
was left alone deliberately: a shadow is a drawing decision, section 3 locks this drawing, and
adding one to fit a platform convention is the kind of change this file exists to stop being
made in passing. What it costs is that Banchi sits slightly flatter on the dock's shelf than
its neighbors. **What would settle it: a sweep, on a sheet, at 128, 64 and 32px against the
same three icons** — the method section 7 already sets out, not a value typed here.

### Also not done: the `.icns` carries one cut, and its small reps get the wrong one

**Looked at, at real pixels, magnified 6x — not inferred.** Chrome builds the installed app's
`.icns` by downsizing the manifest PNGs, which are the DISPLAY cut, and an `.icns` carries 16
and 32px representations. At 32px the display cut's brackets go thin and mushy and the card
reads as noise; the SMALL cut at the same inset is crisp and legible. That is section 11's
finding arriving at a surface section 11 did not cover — it swept the favicon and the rail, and
the dock's small representations are the same size band.

**It cannot be fixed from here, and that is why it is written down rather than filed as work.**
A manifest cannot say "this cut below 64px"; Chrome picks the source and rewrites the `.icns`
itself, so hand-authoring one would be overwritten. **It is also not new** — the display cut has
always been what those reps were downsized from. What the inset changed is the degree: the
artwork is 80.47% of the canvas now, so a 32px rep carries 26 pixels of mark where it carried
32, and the cut was already past its range at both.

**What would settle it, and it is not a value to type here**: whether the dock's 16 and 32px
reps are ever actually seen. The dock draws 64pt and up; 32 and 16 are Finder lists, ⌘-Tab at
small settings, and the menu bar. If the answer is "rarely", this stays a note. If not, the
honest fix is a native bundle that ships its own `.icns` — which is a different decision from
D108's, and would have to argue its way past the camera question that entry settles.

### The light and dark question, answered by section 12 rather than here

**macOS 26 introduced per-appearance app icons — an app may ship a dark variant — and Banchi
cannot use it, twice over.** The platform half: those variants are authored as an Icon Composer
`.icon` asset in a native bundle, and Chrome builds a plain `.icns` from manifest PNGs, which
has no way to express one. The web half is smaller still — a manifest icon takes no media
query, and there is no `prefers-color-scheme` on `icons[]`.

**And the design half already ruled, before either mattered.** Section 12 derived a light ground
and rejected it, in these words: *the mark stays fixed dark in both themes*, because it *"is an
object, not an ink color: an app icon on a phone home screen does not invert when the phone
does."* A dark-mode dock icon is that same argument at the same size. **Nothing here reopens
it** — if it is ever reopened it is section 12's to reopen, on a sheet, and the platform
question is downstream of that rather than a reason to revisit it.

## 18. The browser tab — the empty slot, and what it gives up

**Settled 2026-09-06, on the owner's decision, after three rounds of true-pixel renders.**
`app/public/favicon.svg` is no longer the mark. It is **the empty slot**: the bracket pair alone,
in `bluesteel`'s own metal, with no tile, no card and no sheen.

| | |
| --- | --- |
| shape | the mark's L — corner (22.609, 16.252), arms 20.82 × 25.65, radius 8 |
| weight | **4.2**, §11's small cut |
| taper | **tip 0.15, ramp 0.70** — §13's lockup values, read from `lockupGeometry.ts` |
| paint | **flat `#A8873F`** — see "the paint is gold, and flat" below |
| ground | **none** |

### Why the empty slot at all

§1 has always said it: *"with the card removed the same brackets become an empty slot, which is
the in-product mark."* That sentence was read as scoped to surfaces inside the app, and the tab
kept the whole mark by default rather than by decision. The owner's instruction closes it — the
tab should be what the collapsed sidebar is.

### The taper is §11's rejected range, and it is taken anyway

**§11 swept tip at 0.07 / 0.25 / 0.50 / 1.00 and chose 1.00.** The lockup's 0.15 falls *inside*
the band that sweep rejected, and §11's arithmetic applies unchanged: a 4.2 stroke at tip 0.15
ends 0.63 units wide, which is 0.2px at 32 and 0.1px at 16. **The arm ends do drop out at 16px.**
Rendered at true 16 and 32 on three grounds before the choice, against the untapered wire.

The owner chose the taper knowing that. It is the drawing the open lockup makes, it is
unmistakably better at 32 — where a Retina tab actually renders — and the tab is the one surface
where the mark is decoration rather than a control. **§11's finding is not overturned**: it governs
`Logo`, every in-app surface and the app icons, all of which stay untapered below 64px.

### The paint is gold, and flat

**Settled 2026-09-06, after the first version shipped in silver and was wrong on half the
world's tab bars.** The tab carries no ground, so its paint has to survive both — and *neither*
of the mark's existing treatments does:

| paint | dark tab bar | light tab bar |
| --- | --- | --- |
| `bluesteel.bracket` silver — `#FFFFFF` … `#8FA4B8` | reads | **near-invisible** |
| ink `#0f1217` | **near-invisible** | reads |
| gold `#C0A254` / **`#A8873F`** | reads | reads |

**Gold is the only paint in §9's vocabulary whose mid-tones sit in the middle of the luminance
range**, which is exactly the property a groundless icon needs. Silver's four stops are
`#FFFFFF`, `#B8C8D8`, `#F2F8FF`, `#8FA4B8` — three of them near-white. Black has the same
problem inverted. This was drawn before it was chosen: silver, ink, ink-with-gold-tips, the
`whiteGold` gradient, flat `#C0A254` and flat `#A8873F`, all at true 16/20/32/48 on both bars.

**And it is FLAT, not the gradient.** `whiteGold`'s four stops were drawn too. At 16px the
bracket pair is about twelve pixels of ink and a four-stop gradient across it resolves to noise;
the flat fill is the only version that is unambiguous at every size on both grounds. `#A8873F` is
one shade below §9's `#C0A254` — the deeper value holds the light bar better and costs a little
on dark, and the light bar is where the groundless icon was failing.

**`#A8873F` IS NOT IN §9, AND THAT IS DELIBERATE.** It is not one of the six locked marks'
colours and must not be added to them: the marks are an illustration's palette (D102) and this is
one surface's paint. It lives here, in this table, and `scripts/build-mark.mjs` READS it out of
this section rather than holding its own copy — the same arrangement `tip` and `tl` already have
with `lockupGeometry.ts`. `make docs-audit`'s `rail mark` row reconciles the two.

**What this gives up:** the tab is now the one Banchi surface not drawn in a metal. The mark, the
lockup, the rail and the app icons all keep their gradient; the tab trades it for legibility it
could not otherwise have. Two ways of keeping the metal were drawn and declined — a dark tile
(a ground the owner did not want) and two icons chosen by `sizes` (the tab would not always look
the same).

### No tile, and the cost is named

`bluesteel`'s bracket metal runs `#FFFFFF` to `#8FA4B8`. With no ground of its own, **the tab icon
is close to invisible on a light browser tab bar** — measured at 16, 20, 32 and 48px against
Chrome's light chrome (`#dee1e6`). It reads well on a dark tab bar and on the mid-grey of a
bookmarks bar.

This is §12's finding arriving at a surface §12 did not cover. That section fixed the mark's tile
dark in both themes *because* a light ground lost the silhouette; the same physics applies here and
there is no tile to fix. Two ways out were drawn and both declined: keeping the dark tile (legible
everywhere, but a ground the owner did not ask for) and two icons chosen by `sizes` (legible
everywhere, but the tab would not always look the same). **The owner took the trade explicitly.**

### What did not change

The **app icons keep the full mark** — `icon-180.png`, `icon-1024.png` and §17's macOS grid all
still draw the tile, the card and the brackets. `markGeometry.ts` and `markPalettes.ts` are
byte-identical across this change, so `Logo` and every in-product surface are untouched. This is
the tab and nothing else.

`scripts/build-mark.mjs` emits it from `tabSvg()`, reading `tip` and `tl` out of
`lockupGeometry.ts` rather than retyping them — that file is generated from §13's table and
`make docs-audit`'s `lockup params` row reconciles the two, so the tab cannot drift from the
lockup it is named after. Its `rail mark` row holds the tab to the mark's own L.

## 19. The phone — the bar is a rail, and the drawer is the sidebar

**Settled 2026-09-07, on the owner's instruction, against the running application at 390 and
320 in both themes.** §15 said where the lockup goes and ended the list with *"Nowhere else. No
marketing page exists to want one."* That sentence was written listing three surfaces — the
sidebar, the rail, `#/gallery` — and the phone chrome was never among the things it was asked
about. So the phone kept what it had before the lockup existed: a `Logo` tile in the top bar, and
a tile with a wordmark and the tagline in the More drawer.

**What that cost is not subtle.** The product wore two different brands depending on how wide the
window was, and the drawer's brand was the only surface in the shell still drawing a wordmark. On
dark the bar's tile — a dark superellipse on `--bn-surface-glass` over a near-black page — very
nearly disappeared, which is the same failure §16 gave the sidebar's bracket a chrome gradient to
avoid, at a size where it is worse.

| surface | draws | size |
| --- | --- | --- |
| sidebar, expanded | the lockup | kanji 40 (§16) |
| sidebar, railed | the empty slot | 32 |
| **phone top bar** | **the empty slot** | **32** |
| **phone drawer** | **the lockup** | **kanji 40** |
| `#/gallery` | both, beside the mark | 32 / 40 / 56 |
| browser tab | the empty slot, flat gold | §18 |

### The bar is the rail's case, and the arithmetic is §11's

**The lockup cannot go in the top bar and the reason is already written down.** Its floor is
kanji 32 (§11), which is a 102 × 75 block; `--bn-topbar-h` is 52px. That is the same refusal the
64px rail takes, for the same measurement — 番's counters close at about kanji 30, before the
roman and long before the bracket.

So the bar draws what the rail draws. **This is not a new ruling.** §18 settled it for the browser
tab on the owner's own instruction — *"the tab should be what the collapsed sidebar is"* — citing
§1: *"with the card removed the same brackets become an empty slot, which is the in-product
mark."* §19 is that sentence reaching the third surface it was always about.

**One difference from the tab, and it is deliberate.** §18's favicon is flat gold on no ground,
because a tab is 16px of chrome the app does not paint. The phone bar is an in-app surface, so it
takes the rail's own paint: `--bn-lockup-metal`, which `kit.css` resolves per theme — flat ink on
light, the locked chrome gradient on dark.

### The drawer takes the sidebar's number, and the tagline goes with it

**The drawer IS the sidebar at a phone's width.** Same nav, same groups, same foot, one tap away
instead of always on. So it draws the sidebar's brand at the sidebar's size, and §16's rule
applies unchanged: **the lockup replaces the mark, the wordmark and the tagline together.**

**Forced choice, kanji 32 against kanji 40**, drawn in the real drawer at 390 and at 320, in both
themes, before this was written:

| | kanji 32 | kanji 40 |
| --- | --- | --- |
| block | 102 × 75 | 128 × 93 |
| fits the drawer (`min(300px, 86vw)`, ~268px usable) | yes | yes |
| fits at 320 (drawer 275px) | yes | yes |
| nav still reaches the foot without a scroll at 844 | yes | yes |
| reads as | a smaller copy of the sidebar's | the sidebar's |

**40 is taken.** 32 buys about 45px of drawer above the fold and nothing needs it — nine nav items
and the foot reach the bottom of an 844px drawer at either size. What 40 buys is that there is one number, not
two: the drawer and the sidebar are the same object and a second value is a second thing to keep
in step, which is the defect §13 spent thirty-seven rounds learning.
### The choice was made on WIDTH, and here is the height it was not made on

**The head grows 60px to 121px, and on any phone shorter than about 800px the drawer's nav list
scrolls.** That is worth writing down because the forced choice above was drawn at 390 and 320
*wide*, both on tall viewports — §16's method applied to one axis. Measured afterwards, on the
same demo store:

| viewport | on main | at kanji 40 | at kanji 32 |
| --- | --- | --- | --- |
| 390 x 844 | no scroll | **no scroll** | no scroll |
| 414 x 736 | 42px | **103px** | 85px |
| 375 x 667 (SE) | 111px | **172px** | 154px |
| 360 x 640 | 138px | **199px** | 181px |

**Three things follow, and none of them reopens the size.** The nav ALREADY scrolled on every one
of those phones — nine items, three group labels and a foot do not fit 667px of drawer, and did
not before this. The lockup adds 61px to a scroll that existed. And **kanji 32 gives back 18 of
those 61**, which is not a fix; it is the parity argument traded away for a sixth of the problem.

**The foot never scrolls, and that is why this is a nuisance rather than a defect.** `.bn-drawer`
is a flex column and `.bn-nav` is the only thing in it that scrolls, so `Cards to pull`, the theme
toggle and the server line are pinned and reachable at every size measured above. Nothing became
unreachable.

### The phone bar's word IS the roman, and every value comes off the drawing

**Amended 2026-09-07, on the owner's instruction: "the exact same look that we currently have as
the roman subtext in the lockup, all caps with that faint aesthetic/spacing."**

The bar drew `Banchi` in Manrope 700 at 16px — sentence case, no tracking, full ink — beside a
mark whose own name is drawn in caps at 45% with a tracking a width-match solved for. The right
face in the wrong voice.

**It is set as TEXT, not drawn, and that is possible because the roman is Manrope.**
`lockupGeometry.ts`'s own header says so: *"BANCHI — Manrope 700 at 0.25 of the kanji, tracked to
0.75 of its advance"*, and Manrope is `--bn-font-display`, which this app already ships. The kanji
could never be text — it is outlined precisely because IBM Plex Sans JP cannot ship (§14) — but
the roman can be, and text is findable, selectable and announced.

| what | where it comes from |
| --- | --- |
| face | Manrope 700, `--bn-font-display` — the face the generator outlines it in |
| case | `text-transform: uppercase`; the DOM keeps `Banchi` |
| tracking | `ROMAN_TRACK_SOLVED / PARAMS.romanSize` em — the SOLVED answer, not §13's seed |
| ink | `PARAMS.romanOpacity`, 0.45, over `--bn-ink` |
| size | **13px** (`--bn-fs-md`) — the one value the geometry does not decide |

**Nothing above is typed into a stylesheet.** The element publishes the tracking and the opacity
as custom properties the way `BrandSlot` publishes the block, so a re-solve of the width-match or
a move of `romanSize` reaches the bar without anyone remembering to follow it. A number copied out
of that file is the defect §13 spent thirty-seven rounds learning, and it is the same file it
would have been copied from.

**The size is a forced choice and the geometry cannot make it.** In the lockup the roman is a
fraction of the kanji; in the bar there is no kanji to be a fraction of — the mark is the rail's
bracket. Drawn at 11, 12, 13, 14 and 16px in the running bar, both themes: **11 reads as a
caption and goes weak beside a 32px mark; 16 stops being faint and starts competing with it, a
wide caps run at 45% turning into a banner; 13 sits with the bracket as one object.** For scale,
the sidebar's own roman renders at about 10px — the bar's is a little larger because it carries
the name alone rather than under 番地.

**Two things went with it, both dead before this edit.** The bar's title said `Not found` for an
unknown hash — a branch that cannot run, because `hasChrome` is false when `route` is undefined
and the shell is never rendered for one. `PhoneBar` took a `route` prop only to feed it. And a
`margin-right` compensating the trailing letter's tracking was written, kept, and then measured:
the gap to the search button is 135px with it and 135px without, because the word is `flex: 1 1
auto` and grows to fill the bar whatever its content measures. `brand.spec.ts` asserts the grow,
so the day the word stops growing that reasoning fails loudly instead of leaving 5.8px of air.

`app/tests/brand.spec.ts` asserts the face, the case, the tracking against the geometry's own
arithmetic, the opacity and the grow. Four of five were observed red under mutation; the fifth
(the margin) is what the measurement above deleted.

**What would move it is the drawer's own density**, not the brand — the 44px rows, or the three
group labels.

### And that is what was done, on the owner's ruling: shrink the headings, do not drop them

**Settled 2026-09-07, from renders of both.** The table above understates it, because it measures
the phone's own height and Safari's toolbars take about 90px more. At 390 x 754 — an iPhone 14
with the toolbars up — the nav ran 85px past the fold and showed **7 of its 9 rows**.

Two builds were drawn side by side at that size, in both themes:

| | rules | iPhone 14 | 15/16 | mini / 11 Pro | SE |
| --- | --- | --- | --- | --- | --- |
| as it stood | — | 7/9, 85px | 8/9, 77px | 7/9, 117px | 5/9, 262px |
| headings dropped | 1 | **9/9 fits** | fits | **fits** | 5/9, 175px |
| **headings shrunk** | 5 | **9/9 fits** | **fits** | 8/9, 29px | 5/9, 174px |

**The owner chose to keep them**, and the arithmetic is why that costs five rules rather than
one. The three label rows are about 70px of the 85; the last 15 come from the brand, so the
drawer's lockup is **kanji 34 on a short screen** and 40 everywhere else.

**The heading's own type is untouched** — same 10px, same caps, same 0.1em. What closes is the air
around it: 4px of padding above and below each label, a line box of 1.5, the 12px between groups
and the 4px between rows. **The rows keep their 44px.** A `font-size: 10px` was written into that
block first and deleted: `--bn-fs-2xs` is already 10px, so it changed nothing and read as though
it had.

**What it costs, stated rather than buried:** the mini, X, XS and 11 Pro — 375 x 812, a real
population — fit under the dropped build and are one row short under this one. That is the trade
the ruling made.

**THE SIZE IS CHOSEN IN JS HERE, AND IT IS THE ONE PLACE IN THIS SHELL THAT IS TRUE.** `Sidebar`'s
own comment says a stylesheet should read the condition the layout does, and it is right for the
rail. It is wrong here: `Lockup` interpolates the bracket between the slot's MEASURED width and
the `size` it was handed, so a media query that shrank the slot without telling the component
would leave the box at 34's width and the maths at 40's — measured, the bracket renders a fifth of
the way toward the rail. One source decides and both read it.

### The SE cannot fit, so the cut edge says so

Nine rows do not go into 577px at any size in that table, and on main they did not either — 5 of
9, ending on `.bn-side-foot`'s own rule, which reads as the bottom of the menu rather than the top
of a fold. Four screens looked absent rather than below the line.

**The fade is the mechanism the thumb-floor pass gives the scrolling chip rows, turned
vertical**: a mask driven by the scroller's
own progress, so the bottom edge dissolves while there is more to reach and the top edge does once
you have scrolled. **A list that fits gets nothing at all** — a scroll-progress timeline whose
scroller has no overflow is inactive and applies no effect, so there is no measurement and no
class to keep in step. Behind `@supports`, because the fallback is what ships today.

**`every card has an address` left the product with this edit**, on the owner's ruling, and that
is worth stating plainly because it was not a side effect. The drawer was its last home — the
sidebar dropped it when the lockup landed, and `#/gallery` uses it only as a type specimen.
Home's own lede still ends *"Every one has an address."*, which is the sentence a person reads,
grammatically bound to the count in front of it.

### What is built

One `BrandSlot` in `app/src/App.tsx`, rendered by the sidebar, the bar and the drawer.
**There is no second drawing and no JSX branch**: `--bn-brand-open` is inherited, `App.css` sets
it to 0 on `.bn-topbar-brand`, and the morph reads the slot's own width — so the bar gets the
rail end from one declaration. `Lockup` did not change for any of this.

`app/src/App.css` lost `.bn-brand-text`, `.bn-brand-name` and `.bn-brand-tag`, whose last render
site this was.

### The floor is a guard now, four weeks after it was asked for

§15 said *"`app/tests/brand.spec.ts` gains the floor — a lockup below kanji 32 must not
render"*, and nothing built it. `Lockup` refuses below `LOCKUP_FLOOR = 32` and returns null.
It can only fire on a call site that does not exist yet — every surface above is at or over the
floor, and the rail's 32 comes through `railSize`, which is the mark rather than this drawing.

`app/tests/brand.spec.ts` asserts the bar's bracket is `markGeometry.ts`'s own wire at 32 with no
tile and its type at opacity 0; the drawer's lockup at 127.6 × 93.2 with the kanji at full opacity
and no wordmark, tagline or `every card has an address` anywhere in the document; and that every
lockup drawn at either width clears the floor's block. All three were observed red under mutation.

### What would reopen this

A bar tall enough for a kanji-32 lockup — 84px against today's 52 — is the only thing that would
change the top half of the table, and it costs about 10% of an 844px viewport on every screen.
It was considered and refused on that arithmetic, not overlooked.
