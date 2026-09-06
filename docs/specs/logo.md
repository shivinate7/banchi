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
| **no taper** | HELD, and now argued rather than asserted. At tip 0.07 a 4.2 stroke is 0.29 wide where it ends — under a third of one unit in a 100-unit box, which is a third of a pixel at 28px. Swept 0.07 / 0.25 / 0.50 / 1.00 |
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
| `pad` | 0.22 | carried from the recovered pass |
| `gap` | 0.06 | carried from the recovered pass |
| `stroke` | 0.050 | rounds 1–5 |
| `arm` | 0.32 | carried; §3's lockup row |
| `rrMul` | 4.0 | rounds 6–10, closed on the JND |
| `tip` | 0.07 | not yet swept |
| `tl` | 0.45 | not yet swept |

**A key in this table is not the same as a key that has been argued.** `tip` and `tl` are here
because the sheet holds them, not because anyone chose them — they are the next two rounds, and
the column says so.

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
accepted the first time and passed over the second, once they were shown against thinner neighbours and
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
and differenced pixel for pixel, adjacent specimens at kanji 40 differ by a mean of **0.7 to 3.5 out of
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
and the only defence that has ever worked here is printing the number.**

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

### The question underneath, which is not about type at all

**Every `Logo` call site in this product is 44px or below, and this lockup is not drawn below
about 150px.** There is no marketing page, no OG card, no app-store listing. The only surfaces
that could carry it are `#/gallery`, the owner's crash page if it grew, and `README.md`.

**If the honest answer is "nothing today", then the right outcome is this section and no
artifact** — the parameters recorded, the measurement made, the license understood, and nothing
built that no screen reaches. That would be CLAUDE.md's own rule applied to a brand asset rather
than to a route.
