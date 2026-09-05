# The Banchi mark

**Status: SIX MARKS LOCKED AT THE DISPLAY CUT (section 9). THE GROUND IS DERIVED. THE SMALL CUT
AND THE LOCKUP ARE STILL UNDRAWN, AND THE COMMITTED SVG IS STALE AGAINST ALL OF IT.** This file
is the state of record. `logo/banchi-icon.svg` matches neither section 3 nor section 9 and must be
regenerated before anyone uses it.

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
| small — stroke 3.4, no taper | below 64px |

Not optional. A 1.7 stroke is a scratch at 32px and absent at 16px.

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
| `logo/sheets/*.html` | **the generators.** Self-contained; render with `sheets/shot.mjs` |

**Every PNG here went in past the pre-commit image guard, on the owner's word each time.** That
guard has no `PKMNSCAN_*=off` hatch — unlike the dupes, links, docs and sigil guards — because a
photograph is the one staged file that can carry a live code. `--no-verify` is the only way past
it and it takes every other guard down with it, so the rule is: ask, stage nothing but the
images, and say so in the message.

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
section 3's *small* optical cut (stroke 3.4, no taper), which has still never been drawn. **Six
marks are locked at the display cut and none is locked at the small cut**, and a favicon is 28px.

## 10. Still open

- The four **HELD** parameters in section 3. **The ground sweep took a bite out of one of them**:
  the card base fill `#5A6E80` and the prism gradient sit under a ground that is now derived, so
  the base fill is the next thing worth sweeping — it is the only remaining color in the mark
  that nothing else constrains.
- **The small optical cut, which is now the biggest gap in this file.** Six marks are locked at
  the display cut and **none at the small cut**. A favicon is 28px and a nav rail is 48px; at
  those sizes the locked brackets are essentially gone, which section 9's second row shows. Every
  color decision on this page was made at 104 – 268px.
- **`warmer` and `quieter`**, parked in section 3, are outside the locked six. They differ from
  each other only in the top of the gradient and take the same ground in both families — **five
  candidate prisms may really have been four**, and the locked set answers that by taking three.
  Nothing is owed here unless they are wanted back.
- Regenerating the four assets, and generating the lockup.
- A drawn wordmark. `Banchi` is set in Manrope today.
- Which of tile / bare mark the sidebar takes. Decide by looking at the rail.
- How the icon ships: it uses `feTurbulence`, which browsers render but a favicon pipeline may
  drop. Exported bitmaps per size may be needed rather than a live SVG.
