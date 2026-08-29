# Design

Two audiences, two standards. The owner's screens are a tool — dense is fine. The
Fulfiller's screens are the entire product for a retired, non-technical user, and "if a
flow needs explaining twice, redesign the flow" is a real requirement with no way to check
itself. So it is written below as numbers.

## Tokens — locked 2026-08-12

Locked by interview, not by inference. Every value below was chosen by the owner from
rendered alternatives on a real card photo, not described in prose and agreed to. Where a
value was picked over a specific rejected one, the rejected one is named — a token nobody
can argue with is a token the next session will quietly replace.

**Both sheets are in `docs/design-refs/`.** `docs/design-refs/locked.html` draws this token
block; `docs/design-refs/rejected.html` draws what lost and why. Open them before changing
anything here. They are a view of this file and never a second source of truth — see
`docs/design-refs/README.md` for what that costs, since nothing audits the hex values
inside them.

```
Color      #FCFCFD  bg        the page. Everything sits on this.
           #FFFFFF  surface   raised: choice rows, queue rows, panels
           #08090A  ink       all body text, all headings, all money      19.4:1 on bg
           #4E5157  muted     metadata, secondary labels, disabled         7.76:1 on bg
                              7.96:1 on surface, 7.30:1 on hover — its darkest ground
           #E6E7EA  line      the 1px hairline. Every separation, no exceptions.
           #1E40AF  accent    unsure, and the only-action fill             8.5:1 on bg
           — plus two interaction states derived from the above —
           #F4F5F7  hover     row hover only. bg and surface are 1.5% apart, so
                              neither can serve as a hover state for the other.
                              A GROUND THAT CARRIES TEXT: check text tokens against it.
           #17348F  pressed   accent, pressed. White on it: 10.9:1.
           — and one boundary the hairline was too quiet to draw —
           #8C8C8C  field     the border of something you TYPE INTO. Nowhere else.
                              3.36:1 on surface, 3.28:1 on bg, 3.08:1 on hover.
           — and one token that names a value already in use —
           #FFFFFF  on-accent label on an accent or pressed fill. Never a ground.

Display    Cabinet Grotesk  (Fontshare)   700/800 only, and only at >= 20px
Body       Atkinson Hyperlegible (Google) 400/700
Utility    Martian Mono     (Google)      400/500/600, tabular by construction

Spacing    4 8 12 16 24 32 48 64        one scale, no other values
Radius     4px                          one value, everywhere
```

**The position bar carries TWO SCALES, and they must be distinguishable at a glance.**
Added 2026-08-23 on the owner's ask — *"not only its location at the box level but section
level"*, then *"while retaining box depth too"*. The box scale answers how far into the box
to put your thumb (D20's original argument); the section scale answers where you are inside a
divider. They routinely disagree: a card reading `#51 of 53` draws hard right at box scale
and is `Card 1` of section 3 — the very front — at section scale. Both are true, and a person
walking to a box needs the first to get near it and the second to land on it.

Three cues separate them, and none is a new colour: the section track is shorter (8px against
16px), a hairline indents it beneath the box track, and its caption opens with the section
number where the box caption opens with `#`. The marker convention is the server's own
`fraction`, so a card at the front of both sits at the front of both.

**The section denominator says which kind it is** — `slots` for a settled divider, `so far`
for the growing last section of an open box. That rule is D20's, argued there; it is repeated
in the caption because the number is small and the operator is already at the right box, which
is exactly when a silently switching denominator is easiest to miss.

**One system, two densities.** Owner screens use the 4–16 end of the scale; the Fulfillment
view uses 24–64 and the minimums in the table below. Same palette, same three faces, same
radius. The alternative — two deliberately different visual worlds — was considered and
rejected: it doubles the token surface and gives two components to keep in sync, and the
Fulfillment constraints are already expressible as a floor applied to a subset of routes.

**That rule reached the insides of components and never reached the page, which is where all
the waste turned out to be.** "Owner screens use the 4–16 end of the scale" has always been
read as a statement about the gaps inside a panel; nothing in this file said anything about
the chrome a screen stacks above its first row of content, so every screen invented its own
and each one looked reasonable alone. Measured at 1440x900 on 2026-08-23, with the owner
looking at the result and calling it what it was: the Inventory screen spent **240px — 27% of
the viewport** on a 32px page title, a three-line lede and two control bars before the first
card. The review queue — the screen whose own stylesheet argues that every pixel of chrome
pushes the candidate rows further below the fold — spent **215px**, on **32px of outer
padding**, which is the Fulfiller's end of the scale drawn on the owner's densest screen.

**So page chrome gets numbers, and they are these.** They govern every owner route and
nothing else:

- **Outer page padding is 16px, the same on all four sides.** `--s4`, the top of the owner
  range. Not 24, not 32.
- **The page title is the display face at 20px** — that face's own published floor, so this
  is as small as it is allowed to be drawn rather than a size picked to be small — **and it
  shares a line with the screen's controls and counts.** It is never a block of its own.
- **A lede is one line at the metadata size**, beneath that row. If it runs to two lines it
  is not a lede, and the second line is the thing to cut.
- **The first row of real content sits within 150px of the top of the viewport**, nav
  included. A screen that cannot reach that is carrying chrome nobody argued for.

**The shared line is the half that pays, and the arithmetic is the whole argument.** A title
block and a control bar are each about 45px tall; stacked they cost 99px with the gap, and
side by side they cost 45. Nothing is given up, because a page title is one word and a
control bar is short. On the review queue that one change moved the photograph's frame from
y=215 to y=146 — which is one more candidate row on screen beside the photograph the operator
is judging it against, and that is the entire job of that screen.

**Rejected: deleting the ledes.** It is the cheapest 20px available on any screen and it is
the wrong 20px. On an owner screen the lede is the only writing that is not a value or a
label, and the screens that carry one are exactly the screens with a keyboard vocabulary that
nothing else explains. Demote it; do not cut it.

**Rejected: a second scale for page chrome.** The paragraph above already refuses two visual
worlds because they double the token surface, and that argument does not weaken when the
subject is a page header instead of a panel. Every number above is a step of the one spacing
scale.

**None of this reaches `#/fulfillment`.** That view keeps the 24–64 end of the scale and every
floor in the constraints table below, and those floors win wherever the two could be read as
disagreeing — a 20px title cap is an owner rule, and his view has a 20px *minimum* on every
text node for the opposite reason. The one page in the app that is drawn to his floors on the
owner's ground is the unresolved-hash panel, which argues for itself in `app/src/App.css`.

**The nav shares the page's reading edge**, which is what "in line" means here and is the
thing that is most visible when it is wrong. `app/src/App.css` pads the shell to the same
16px, so the first route name in the strip sits directly above a screen's heading. It was
32px — putting the one element that appears on every screen out of line with all of them at
once.

**Nothing mechanical enforces any of this.** The same standing limit the paragraphs above
record for contrast: `scripts/docs-audit.py` compares hex values between this file and
`app/src/tokens.css` and cannot see a padding, and the Playwright specs measure the
Fulfillment view, which is the one route this section does not govern. A screen that drifts
back to a 32px page header will do it silently.

**`field` is a SECOND line colour, and it exists because one number was checked and the other
was not** (added 2026-08-26, on the owner's instruction to decide it). Every token that carries
text clears 7:1 here and always has. Nothing ever asked what `line` measures, and the answer is
**1.24:1 on surface** — so every border, separator and input outline in the product sits far
under WCAG 1.4.11's 3:1 for the boundary of a control. All of the text passed; none of the
edges did.

**The whole-palette fix was built, rendered and refused.** `line` at a true 3:1 is about
`#8C8C8C`, and the render answers the question on its own: the walk's five section rows become a
spreadsheet grid, which is the failure the section below names by name and by product; and
`app/src/BoxOps.css`'s box track is *painted* with `line` rather than bordered by it, so its
segments go from the quietest visible mark in the palette to something that reads as ink. A
criterion aimed at people who cannot find a border is not worth the one thing this design says
it must not become.

**So the split is by JOB, and the job is narrow enough to be checkable.** `line` separates and
fills, and stays exactly as quiet as it was. `field` draws the boundary of a control you type
into — `app/src/SearchField.css`'s box, `app/src/BoxOps.css`'s fields, the run panel's number
input and its `decisions.json` textarea — and nowhere else. That is the case where the low
contrast genuinely bites: an empty text input is a rectangle and nothing else, so a border at
1.24:1 leaves it findable only by its placeholder, while a button at the same contrast is
findable by the ink label inside it at 19.9:1.

**It is deliberately not `edge`, `border` or `control`.** A token named for a general job grows
one, and the first thing that would have taken it is a button border — which is the weight this
product spent a whole session removing from the box operations. Named for the one thing it is
for, it cannot creep without someone renaming it.

**It reaches the Fulfiller's search field too, through the shared `SearchField`, and that is
right rather than an accident.** His view's floors are about making things findable at reading
distance with reading glasses, and a field he can actually see the edge of is on that side of
the argument. No assertion in `app/tests/fulfillment.spec.ts` measures a border; every one of
them measures text, which is untouched.

**Light only, everywhere. There is no dark theme and no theme switcher.** Not a deferral:
building one means defining every token twice and running every contrast assertion twice,
for a surface with one user who works under a desk lamp. Reopening this is a change to this
section.

**Every token that carries text clears 7:1 on every ground it sits on.** There is no
exception and no token that is legal in one view and not another. That is a deliberate
property of the set rather than a happy accident: `muted` was first drawn at `#55585E`,
which measures 6.96:1 — a miss of four hundredths, small enough to be worth documenting as
an exception and reasoned around. It was replaced rather than annotated. A palette
described as "legal except one" hands the next near-miss a precedent, and the argument for
accepting a 6.9 is identical to the argument for accepting a 6.5. The swatch difference is
invisible; the difference between the two sentences is not.

**`hover` is a ground that carries text, and this file did not say so until 2026-08-23.**
The paragraph above was written while the answer to "every ground it sits on" was being read
off the first two rows of the block — `bg` and `surface`, the two things a screen is
obviously made of. `hover` was derived afterwards, as an interaction state, and interaction
states are the row you skip when you are asking which colours a word can land on. But a
hovered row does not empty itself. Every word stays exactly where it was, the row under the
pointer is by definition the row somebody is reading, and `hover` is the darkest of the
three grounds — so it is the one that decides, not the one that is safe to omit.

**What that omission cost, stated because the number is the argument.** `muted` at `#52555B`
measured 7.29:1 on `bg` and **6.86:1 on `hover`** — the same four-hundredths-shaped miss the
paragraph above refused to annotate, hiding behind the ground nobody had checked. It was
rendering: `app/src/ReviewQueue.css` puts `.review-candidate-meta` on `.review-candidate`,
and that row takes `--hover` under the pointer. `muted` is now `#4E5157`, which clears on all
three (7.76 / 7.96 / 7.30), and the same replace-rather-than-annotate rule was applied for
the same reason.

**Read the two paragraphs together as one rule with its blind spot named**: a token's floor
is checked against every ground it can land on, and "ground" means any token a `background`
is ever painted with — `bg`, `surface` and `hover` today, and anything added to that list
tomorrow. `on-accent` is the only token in the block exempt by construction, and its row
says why in three words: never a ground. Nothing mechanical enforces this. The `design
tokens` row of `scripts/docs-audit.py` proves this file and `app/src/tokens.css` agree about
a hex and cannot know what the hex means; the Playwright specs measure rendered pairs, and
they measure the pairs the Fulfillment view actually draws, which is not all of them. Adding
a ground token means recomputing every text token against it by hand.

**Cabinet Grotesk comes from Fontshare, not Google Fonts.** That is a second font host and
a second licence to read before step 7 ships — do it then, and self-host all three faces if
the answer is at all unclear. **Step 7 shipped on 2026-08-13 with the licence unread**, and
`app/index.html` loads all three faces from their hosts and says so in its own comment. The
condition on this paragraph has gone by; it is written down rather than quietly re-dated,
which is the same rule `docs/DEBTS.md` applies to a fix trigger that fires and is passed.

It was picked over Bricolage Grotesque, Archivo Expanded and a single-family Geist system;
the last of those was rejected specifically because it has no characterful face at all, and
would have satisfied the token block by deleting one of its requirements.

**Atkinson Hyperlegible is a Fulfillment decision wearing a typeface.** It was drawn by the
Braille Institute for low vision — disambiguated `0`/`O` and `1`/`l`/`I`, exaggerated
apertures. Every other line about the Fulfiller is an assertion in a test; this one is in
the letterforms, and it is why the same body face is used on both sides rather than the
owner getting something sharper.

**Martian Mono carries every number in the product.** Position labels, prices, collector
numbers, counts, ages. `Box 3 · Section 2 · Card 17` is built by
`pipeline/join.py:Position.label` at 25 cards per section, and it must not shift width
between cards — which a mono gives for free rather than by remembering to set `tnum`.

## What this is not

**Not Collectr, not Discogs, not LibraryThing.** Three cataloguing tools that became
spreadsheets: dense grey tables, everything at one weight, no hierarchy between a $12 card
and a 15-cent one. This is the failure mode with a face on it, and it is worth naming
because the review queue *is* a list of hundreds of rows and will drift there by default.

**Not NYT/FT.** No newspaper coding: no high-contrast serif display, no editorial column
measure, no warm-paper ground. An earlier pass landed there — warm cream, rust accent,
Fraunces — and was rejected as too sanitised-professional for what this is. The register is
tech-forward: mono carrying the metadata, saturated accent rather than muted earth,
hairlines rather than air.

**No confirm dialog on a reversible action.** No "are you sure", no success acknowledgement
to dismiss, no list → detail → back loop in the review queue. Answering a card writes the
answer and advances. Undo covers the mistake; a dialog only makes the ninety-nine correct
answers cost two taps each.

**"Undo covers the mistake" was not true on the review queue, and D28 is the repair.** That
clause is what this whole rule rests on — and on the one screen it matters most,
`store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared, so there
was no undo to cover anything. A single unmodified digit wrote a SKU onto a real card,
permanently, while mark-sold — which is reversible — had a photo to confirm against, a
two-step control and a twenty-second window. The reversible action carried three guards and
the irreversible one carried none.

D28 fixes the premise rather than the rule: the review answer gets the same twenty-second
undo, and the candidate list stops moving between cards so the slip is rarer to begin with.

**Both halves are built as of 2026-08-23.** The layout half first (a measured 538px round-trip
under the finger became zero), then the undo: the answer route goes both ways with an `undo`
flag exactly as mark-sold does, `restores_to` is read off the card inside the lock before the
overwrite, and the screen draws a per-answer receipt with `U` on the newest. **The receipt is
not the "acknowledgement to dismiss" this rule bans** — it demands nothing, blocks nothing,
expires by itself at twenty seconds, and answering the next card never waits on it. What the
rule banned was a step between the operator and the next card; the receipt is a way back that
sits beside the flow rather than in it.

One inherited limit, recorded where a future reader will wonder: **the sixteen Gate B answers
predate the route logging `restores_to`, so they are not reversible** — an undo on any of them
refuses `answer_origin_unknown` rather than guessing. The window exists for answers written
from 2026-08-23 on.
**A confirm dialog was considered and refused again** — one key per card is the property this
rule exists to protect, and requiring a modifier or an Enter would have doubled the keystrokes
on the screen the owner spends the most hours in. Genuinely destructive actions may still gate — but per the
table below, none of those are reachable from the Fulfillment view at all.

**Capture undo is the stated exception, and it gets no dialog either** (settled 2026-08-13).
D10 makes undo a hard delete of the record, the sidecar and the photo, with no backup — so
it is simultaneously the remedy this rule relies on and the one irreversible action in the
app. Those two facts point opposite ways and the ruling is: one tap, no dialog.

The reasoning matters more than the ruling, because the reasoning is what stops a later
session from "fixing" it. **The deleted photo is of a card that is still physically in your
hand**, so the remedy for a wrong undo is to photograph it again. That bounds the loss in a
way a wrong pull or a wrong sale is not bounded, and the "genuinely destructive actions may
still gate" clause above is about those. A dialog on the screen the owner spends the most
hours in would also make the common case — one blurry photo, caught instantly — cost two
actions, which is the thing this whole rule exists to prevent.

Rejected and worth naming: confirming only on a *second consecutive* undo, which protects
against a held key walking backwards through good cards at the cost of one more state to
explain. If that ever happens in practice, it is the fix to reach for first.

This says nothing about the Fulfiller's undo on mark-sold, which is a different control
with its own row in the table below.

**Deliberately not banned, so that no later session reinstates these as rules from an
earlier draft of this file:** card-grid layouts, drop shadows and gradients were each
offered as blanket negative constraints and each declined. Shadows do not appear today
because the separation mechanism is a 1px `line` hairline and nothing else — that is a
positive spec, and a positive spec is what a later session should argue with. The same goes
for the panel header strip: a tinted bar carrying each panel's name and queue depth was
built, looked at, and rejected. Do not add one, and do not write a rule about them either.

## The review queue — BUILT 2026-08-13. Description, except where marked.

**This section specified a screen that now exists, and reads as a description of it.**
`app/src/ReviewQueue.tsx` and `app/src/ReviewQueue.css` render it at `#/review`. Read every
statement below as *does* and hold it against the screen — one card at a time, photo first,
photo beside the choices above 900px; the sentence; the candidate rows with their keys; the human label over the
machine string; a type scale that steps down with the price and a parked row dimmed rather
than merely lower. The old header said "NONE OF THIS IS BUILT" and told you to read every
line as *shall*; it survived the screen by one commit, which is exactly the drift it was
written to prevent, pointing the other way.

**Built met a real queue at Gate B (2026-08-22), and this paragraph previously said it
never had.** The run put real entries in both queue files, the owner answered 16 of them
on this screen through the answer route, and the §10.2 measurements were taken —
`docs/GATES.md`'s Gate B section holds them. What that run could *not* test is the one
number called out below: its queue was uniformly sub-threshold commons, so the
price-banded type hierarchy has still never seen the mixed-value list it was designed
for. The rest of this section now describes a screen that has done its job once.

**What is still written forward, each marked where it stands rather than only here**: the
price band edges the type scale cuts on, the reason labels, and Skip — a control this
section never specified and which is recorded below as an open question rather than
retrofitted into a decision. One paragraph also records where the built screen deliberately
stops short of what this section asks: keys are drawn on the first nine candidates only.

The hardest screen in the product and the one the owner spends hours in, so its shape is
part of the design and not left to step 7.

**One card at a time, photo first — with one narrow exception since D29.** A
queue where every entry shares a reason code AND offers the same single candidate may be
answered as a group. Gate B is the evidence D4 did not have: 16 of 53 entries, every one the
same reason, detection agreeing with itself across every duplicate pair — one systematic fact
about the rig's lighting, sixteen identical taps. Anything looser stays one card at a time,
because a bulk write over cards a human has not compared is exactly what D4 exists to prevent.

**The group confirm (D29, built 2026-08-23) is this screen's one solid fill, and the fill
rule survives it**: the fill means "exactly one thing to do", and D29's eligibility — one
shared reason, one candidate per card, one condition — is precisely what reduces the state to
one action, so there is no second answer for the fill to be biased against. Reason chips in
the rail filter the worklist; `G` opens the group
offer, Enter confirms over the grid of photographs — the grid IS the confirmation — and `U`
reverses the whole group.

Photo as large as the viewport allows, then one sentence naming what the system found, then
the candidate rows with their prices. Answering advances immediately.

**"NO LEFT/RIGHT SPLIT" WAS THIS SECTION'S RULE AND IS REVERSED ABOVE 900px, ON THE OWNER'S
APPROVAL OF 2026-08-24 AND ON A MEASUREMENT THIS FILE NEVER HAD.** The sentence that stood
here — *"No left/right split, so the same layout works on a laptop and a phone"* — bought one
layout for two devices, and the price is now known. Measured in a browser at 1440x900 against
a populated queue: the photograph draws **244x432, which is 8.1% of the viewport**, on the one
screen whose whole job is looking at a photograph; the candidate rows begin at y=721 and the
third is **cut off by the fold**; the pending worklist starts 234px below it; one card costs
**2,356px of scroll**; and **752px — 52% of the width — is empty** beside all of it.

**The empty column is not waste sitting next to a small photograph. It is the CAUSE of it.**
`--photo-cap` exists precisely because everything stacks in one column and the sentence plus
the first candidate must stay in view. Put the choices beside the photograph and the cap stops
having anything to buy.

**The phone keeps the single column, byte for byte.** The split is a desktop layout and
nothing below 900px is re-tuned — which is what preserves the half of the old rule that was
actually about the phone. What the old sentence got wrong was treating one layout for both as
free; it was being paid for by the laptop, in the currency this screen exists to spend.

**The height cap is REBASED, not retired.** Retiring it was the instruction and it is refused:
`--photo-cap` has exactly two readers, `.review-photo`'s `max-height` and `.review-frame`'s
`min-height`, and *their being the same expression is what makes D28's reservation exact*.
Deleting the variable deletes the reservation. Its value moves from `48vh` to the height that
is actually left, and both readers are untouched.

**"As large as the viewport allows" replaced "full width at the top" on 2026-08-13, after
building it.** Full column width is right on a phone and wrong on a laptop: a card is 63×88,
so at a 656px column it draws over 900px tall, and the sentence and the first candidate — the
two things you are comparing the photo *against* — fall off the screen. The first
implementation instead centred the image inside a full-width panel, which drew a correct
photograph beside an equal area of empty surface inside one border, and looked like a bug.

So the rule is a cap on **height**, with width free to bind first: on a phone the column is
narrow and the photo is genuinely full width; on a laptop the height cap keeps the sentence
and a candidate visible beneath it. The number is a judgement and lives in
`app/src/ReviewQueue.css` rather than here — what this section fixes is that the photo is the
largest thing on the screen and that what you compare it to stays in view with it. This is a
judging screen: the photograph has to be big enough to settle whether the foil matches the
toggle, which is the disagreement that put the card in this queue.

**Worked expensive-first — and the sentence that used to follow this one was already false
before the split touched it.** `store/queues.py:sort_key` gained a **starvation tier ahead of
price** on 2026-08-24: an entry past `STARVATION_DAYS` outranks every priced card, oldest
first, because an unpriced `no_catalog_row` has no market and sorted last *permanently* — box
2 left 47 entries queued, counted and unreachable. `bandOf` is price-only and cannot see that
tier, so the five type-size bands render a sort the queue no longer has.

**THE BANDS WERE NOT RETIRED, AND THIS PARAGRAPH SAID THEY WERE.** Corrected 2026-08-25 after
reading the screen rather than this file: `bandOf` is live at `app/src/ReviewQueue.tsx:469`,
applied as `data-band` on every rail row at `:3073`, and all five sizes are the only
`font-size` those spans have (`app/src/ReviewQueue.css:1089-1112`). The worklist was not
retired either — it BECAME the rail. So what is true is narrower and worse than a retirement:
**the five bands still render, and they render a sort the queue only partly has.** That is an
unrepaired mismatch, open as of today, not a completed removal. What DOES discharge "the
ordering is visible" alongside them is honest about the tier `bandOf` cannot see: the card head
carries how long this card has waited, and the rail's reason chips carry counts computed over
the whole queue. A band scale in answer order would render a price sort
the list does not have, which is the same bias this file rejects for the candidate rows.

**The band edges are still the one number on this screen nobody has measured, and Gate B is
why that sentence had to be rewritten rather than deleted.** They are marked as an
assumption at the place they are cut as well as here. They are multiples of D9's $0.40
threshold, so they follow it if it moves — the same instinct D9 applies to its own
sub-threshold bands — but the multiples are a guess at a price distribution that, as of
Gate B, still does not exist. Unpriced is deliberately not the bottom band:
`pipeline/routing.py` holds that no price is not a low price, so drawing it smallest would
teach the eye the opposite of what routing decided.

**The measurement was taken on 2026-08-22 and it came back degenerate.** §10.2 item 3 was
the named instrument and it fired: the whole run priced **$0.04 to $0.40, median ~$0.10**,
and the queue's spread matched the run's. Every card landed in one band, so the type scale
was never asked to separate anything. That is a real result and it is not the one this
paragraph needed — a distribution with no top cannot redraw edges that exist to distinguish
a $3 card from a $300 one. The measurement is therefore still owed, and it now has a
precondition rather than a pointer: **a mixed-value lot**, not merely another run. Recorded
this way because "§10.2 item 3 will redraw them" was true when written, has been executed,
and would otherwise read to the next session as still-pending work that is in fact already
spent.

**Accent does two jobs at two weights, and the heavy one has a rule.**

- *Outline and text weight* — the system is unsure. The reason chip, and each of the two
  conflicting claims in the sentence. This is the common case.
- *Solid fill* — there is exactly one thing to do. Pull-confirm, mark-sold.

**A screen with two answers gets no fill.** This is the rule, and it exists because every
alternative is biased. Filling the pricier candidate teaches the queue to drift toward
over-listing, against the whole point of `pipeline/variant.py` treating the capture toggle
as a claim worth preserving. Filling the toggle's answer is defensible on D3 grounds but
makes the fill mean two different things on two screens. Reserving it for single-action
screens means its meaning never has to be learned twice, and it is why the Fulfiller's
pull-confirm is the loudest thing he ever sees.

**THE THIRD FILL IN THE PRODUCT IS THE RUN PANEL'S SPEND BUTTON** (D33, 2026-08-24; on
`#/runs` since D39), and it is listed here so a later session reading the rule does not find it
as an unexplained exception. `app/src/RunPanel.tsx` draws exactly one solid fill: the control
that starts a paid identification run. **The screen around it draws none** — `Runs.css` says so
in its own comment, because a box picker with thirteen chips is the definition of a screen with
more than one answer. It satisfies the rule literally rather than by argument — the
button **does not exist** until the free preflight has answered, and at the moment it is
drawn the card count and the estimate are on screen directly above it and the only remaining
action is to spend or not to. Every other control on that panel is an outline, including all
three free steps, because a free re-runnable step is never the only thing to do.

**Absent, not disabled, and that distinction is the load-bearing half.** A disabled button is
one attribute away from being pressable, and that attribute is what a later refactor removes
without noticing; an element that is not rendered has to be deliberately re-added.
`app/tests/run-panel.spec.ts` asserts the absence rather than the disablement for exactly
that reason.

**THE SAME SHAPE NOW GUARDS A CLAIM RATHER THAN AN INVOICE (D34, 2026-08-24), AND IT IS NOT A
THIRD FILL.** The listing-release control on the box header is an outline like every other
control in `BoxOps`, so the fill rule above is untouched — what it borrows is the *sequencing*:
a free `GET /boxes/<box>/listings` is fetched when the panel opens, and the button that asserts
"TCGplayer holds none of these" does not exist until that has answered. The reason is the one
this paragraph already gives, and the failure it was written against is on the record: the first
build reported which OTHER boxes a release reached in the receipt, i.e. after the write. The
plan now names the SKUs, the copy counts, the other boxes and whether the box will actually be
freed, above the control. `app/tests/inventory.spec.ts` asserts the absence, not the
disablement.

**The panel must say when a release will NOT free the box.** D34 budgets each SKU by the calling
box's own copies, so a shared SKU leaves a remainder and the delete goes on refusing — correct,
intended, and the one outcome a person reads as a broken gate if nothing says otherwise. That
sentence is drawn before the press and repeated in the receipt.

**The panel is NOT folded, and none of the Fulfillment floors reach it.** It is an owner
surface at the 4–16 end of the scale. This paragraph used to argue the fold on `BoxOps`'
measured grounds — ~250px, reached once a box, above the card detail on the screen whose
question is *where is this card* — and the owner overruled it: *"both box and run, i don't
want click in functionality, i want their buttons just there."* D33 carries the argument.

**What replaces the fold's saving is the panel's own MEASURE, and this sentence has now been
rewritten three times.** It first read *the ROW*: `.browse-boxrun` put the run panel and `BoxOps`
side by side at `1fr 1fr` beneath the card, so the pair cost one panel's height instead of two.
Then the pair stood in a third COLUMN beside the card, where it cost the card's column nothing at
all. Then the BOX left that column for the walk's, because the left column IS the box and the
panel was re-listing sections the walk already draws (D38).

**Then the column itself went (2026-08-26), and the reason is the one axis none of the three
rewrites had checked.** A grid row is as tall as its tallest cell, and this panel shared row 1 with
the card while the card's own copies were row 2 — so the copies began wherever the console ended:
y=938 with it closed and **y=1599 with a run picked**, 1039px of white below the card on a 2214px
page. The answer to *where is this card* was positioned by a panel about something else, at an
unbounded height. The panel became the last row of the content column, at the full width, drawing
**625px closed against 799** and **1143px open against 1461** — no code change, because 1024px
unwraps its head, its notes and its free steps.

**AND THEN THE PANEL LEFT THE SCREEN (D39, 2026-08-29), WHICH IS WHERE FOUR RELOCATIONS INSIDE
ONE ROUTE WERE ALWAYS HEADED.** The owner gave the pipeline `#/runs`. Every measurement above
stands as evidence about the days it was taken and none of it is rewritten; what it adds up to is
the finding — the tallest thing this product draws was being fitted into a column whose question
is *where is this card*, and each fix moved it somewhere that was better on one axis. What
remains here is `BoxRuns`: one row saying whether anything is running over this box, and the
control that hands the ticked selection over. **It must never become two rows**, for the reason
the whole sequence above documents.

**One rule of this section moved with it and one did not.** The page-chrome numbers now govern
`#/runs` as a route of its own — 16px of padding, a 20px display title sharing its line with the
scope, a one-line lede, first content inside 150px — and `app/src/Runs.css` draws them literally.
The density paragraph below is unchanged and still describes the panel.

**The density this section describes is kept and is no longer forced.** 14px step titles rather
than a second rank of 20px display, 32px controls matching what `BoxOps` gives the same job — all
of it was right on its own terms, and none of it was only a consequence of a 370px track.

**Nothing folds, which is the half the owner ruled on.** No disclosure, no cap, no internal
scroller; every step head and note draws in every state and the spend button is still absent
rather than disabled until its preflight has answered. What changed is reading order, and
`app/tests/run-panel.spec.ts` asserts the ruling as an absence — `<details>` and `<summary>` at
zero inside the panel — which is the one form of it no future relocation can quietly falsify.

**Reason codes: human label large, machine string small beneath it.** The pipeline defines
fourteen strings — seven from the variant ladder in `pipeline/variant.py`
(`no_catalog_row`, `metadata_not_stocked`, `metadata_detection_disagreement`,
`detected_finish_not_stocked`, `ambiguous_no_signal`, `duplicate_condition`, and D23's
`rarity_claim_mismatch`, the stack claim contradicting every candidate row) and seven from
routing in `pipeline/routing.py` (`low_confidence`, `no_position`, `identification_failed`,
`set_ambiguous`, `card_not_detected`, `no_market_data`, and D35's
`number_unread_name_matched` — the only reason the JOIN writes over a successful ladder
resolution, keeping that row so the entry offers exactly one candidate, which is what makes a
queue of them one D29 group. It is *not* the only reason sitting on a card the ladder resolved:
`low_confidence` and `no_market_data` do too, and the difference is that they reach
`routing.route` still resolved and are re-routed there, where this one arrives already
un-resolved). Showing only a friendly label
creates a second vocabulary that nothing audits — the drift D16 exists to catch — and
leaves no way to get from what you saw on screen to what the pipeline actually said.
Showing only the raw string is honest and unreadable. Both, at two sizes, costs one line of
chrome and keeps the string greppable across the screen, the run report and `review.json`.
**Owner-side only**: the Fulfillment banned-word list forbids this register entirely.

**Thirteen of the fourteen can reach this screen. `no_market_data` cannot, and this paragraph
used to say otherwise.** It is not a queue reason: `pipeline/routing.py` makes it the fourth
destination beside listed, main and parked, and `pipeline/join.py` writes a queue entry only
for `routing.MAIN` and `routing.PARKED` — so a card with a blank or $0.00 market cell is
priced by hand in `decisions.json` (D9) and never appears here. The screen carries a label
for it all the same, which is right: one line of a lookup table is cheaper than a bare
machine string rendered the first time routing ever queues one. The claim to keep out of
this file is the count — fourteen are defined, thirteen are reachable, and the two numbers
answer different questions.

**Every choice shows its key, and the built screen draws nine of them.** Owner-side, an hour
in the queue is a keyboard and not a mouse, and the keyboard hint is what the
no-confirm-dialog decision looks like in the markup. The Fulfiller's screens are touch and
show none. Recorded as a deviation rather than folded into the sentence above:
`app/src/ReviewQueue.tsx` keys candidates on the digits, because the choice *is* a numbered
list and any other mapping is a second thing to learn — which stops at nine, since a tenth
needs a modifier or a two-key sequence. Rows past the ninth draw no chip rather than a chip
that does nothing. A card with ten candidate rows is rare enough that reaching for the mouse
is the right cost; a real queue full of them is the argument for reopening this.

**THE CAPTURE SCREEN STOPPED AT NINE ON THIS PARAGRAPH'S AUTHORITY AND NO LONGER DOES
(owner, 2026-08-24).** `app/src/CaptureScreen.tsx:Opt` cited the rule above in as many
words — rows past the ninth draw no chip rather than a chip that does nothing — and drew
Pokemon's last four rarities keyless: `Special Illustration Rare`, `Hyper Rare`, `Secret
Rare` and `Rainbow Rare` were mouse-only, on the screen the owner shoots a box from at a
623 ms cadence. `OPTION_KEYS` there is now digits, then `0`, then the letters that screen
has not already spent.

**What the borrowed rule got wrong is one clause: "a tenth needs a modifier or a two-key
sequence".** A tenth needs `0`, and an eleventh needs a letter, and both are one unmodified
press. That was worth an escape hatch on the review queue, where a candidate list is
per-card and a tenth row is rare; it was never worth four permanently unreachable rows in a
vocabulary `pipeline/games.py` authors by hand and the operator claims every stack.

**The review queue is deliberately NOT changed with it, so the two screens disagreeing is a
ruling rather than drift.** Its list is candidate catalog rows — variable per card, ordered
by the pipeline, and its digits are the numbered list they name. The capture screen's is a
fixed authored vocabulary in stack order, where position 11 is `Hyper Rare` on every card
of every run, so a letter there is learned once and not re-read per card. If a real queue
turns up full of ten-candidate cards, the paragraph above is still the one to reopen, and
`OPTION_KEYS` is then the thing to reach for rather than a second alphabet.

**The alphabet SKIPS rather than shadows, and that is the half a later session must not
tidy.** The capture screen has already spent ten letters, two of which are `c` and `u` —
the shutter and the undo. (It read *eleven* until 2026-08-25, and the eleventh was `n`, the
jump to the Box field's second input; D20's amendment merged that input away, so `n` re-enters
the alphabet. It re-enters at its own place, which moves nothing before the twentieth option —
the first thirteen keys are `1234567890ade` either way — so nothing on this screen redrew.) A literal `a`–`z` puts `Rainbow Rare` on `c`. Neither resolution
of that collision is safe: whichever act wins, the other looks like it fired, silently, one
card at a time. So the gaps at `b` and `c` are the design, and they cost nothing to read
because every row draws its own key in its chip. `app/tests/capture-claims.spec.ts` asserts
the skip — the negative case, because nothing in the type system or the render says it.

**THE QUESTION BELOW IS CLOSED AS OF 2026-08-25 — D37 IS THE DECISION ENTRY IT ASKED FOR.**
This section said the screen "needs a real defer that records a reason, and that is a decision
entry rather than a button", and named counting skips as the measurement that would settle it.
The owner asked for the defer directly instead: *"why can't i mark something as known skip
kinda like a stand down on the flag i get that this is a wasted position"*.

`X` now raises a panel offering a **stand-down** — three reasons, `cleared_by_human` set, and
the card itself untouched — beside D26's **retirement**, whose route existed with no control on
this screen. The mid-box delete is deliberately not there: it renumbers every card behind the
one being deleted, which would re-point the worklist the panel is drawn from, and it is the one
operation here with no undo. D37 carries the whole argument.

**Skip survives, narrowed and no longer load-bearing.** It is still the only move that writes
nothing, which is right for a card the owner intends to come back to this session; what it is
no longer is the ONLY move for a card that can never be answered. The paragraphs below are left
standing because their reasoning is what produced D37, and because the measurement they ask for
is still owed — the stand-down's recorded reason is now the instrument that takes it.

**Skip is an OPEN QUESTION, not a decision.** The built screen carries a control this section
never asked for: Skip, on `S`, which moves the current card to the back of this session's
worklist. The owner never chose it, so it is recorded here as a question rather than left
undocumented on the screen this file specifies hardest — and recorded as a question rather
than written up as a decision, because inventing the owner's reasoning after the fact is how
a build's convenience becomes a settled rule nobody argued for.

It exists because two kinds of card cannot be answered at all, and without a way past them
the queue stops dead on the first one. An entry with no candidate rows is refused by
`POST /review/<box>/<index>/answer` as `no_candidates` — it needs another photograph or
another identification run, not an answer. And a card the owner is not ready to rule on has
no other move, because the only write this screen can make is final:
`store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared,
deliberately, so that an answer outlives the question.

Skipping writes nothing — the entry stays open in its file, the run report still counts it,
and a reload forgets every skip. That is the half worth defending: a skip that persisted
would be a third state between open and answered, the same tombstone shape D10 refuses for
undo, and it would have to be cleared by something.

**Gate B was named as what settles this and it did not settle it — the measurement was
missed, not taken.** §10.2 item 1 asked for queue depth and got it (16 of 53), but nothing
recorded how many of those 16 were skipped before being answered, and the owner answered all
16 in one sitting. So the control is exactly as unsettled as it was, minus one opportunity.
Written down rather than left pointing at a gate that has passed: the next real queue
session is the instrument, and **counting skips has to be decided on before it rather than
noticed afterwards**, which is the mistake this paragraph is a record of. If nothing is ever
skipped, delete the control. If most of a queue is, the screen needs a real defer that
records a reason, and that is a decision entry rather than a button.

**Mono carries all metadata.** Reason codes, set and collector number, age, counts,
positions and prices are utility face, uppercase, tracked. The body face is reserved for
sentences a human reads. This one rule does more than any other to keep the thing from
reading as a newspaper.

## Fulfillment view — hard constraints, assert these in a test

The agent cannot see its own output, so these are Playwright assertions, not prose.

**All nine rows now run, against the view itself.** `app/tests/fulfillment.spec.ts` asserts
every row of the table below on the Fulfillment view; `app/tests/pull-confirm.spec.ts` keeps
three of them on step 6's component. `make design-check` runs both. Every contrast ratio is
computed from the *rendered* colours rather than compared against a number published here, so
a token edited in `app/src/tokens.css` without being re-argued in this file has to break
something.

**The assertion count was published here and is not any more.** It read "30 assertions,
observed passing 2026-08-13" and was still saying 30 when the suite had grown to 64 — restated
wrongly in five files at once. D18's test decides it: a count is verifiable and there is
nothing in it a later session could reasonably disagree with, so it is not load-bearing prose
and the honest fix is to stop publishing it rather than to keep it fresh. `npx playwright test`
owns the number. The two places `docs/GATES.md` still says "16 of 30" and "30 of 30" are
deliberately left alone — they sit inside a dated account of the hours 7b shipped unwired, and
renumbering evidence to match a later tree is the one thing a record may never do.

The spec asserts the view is on screen before it measures anything, and that is not defensive
padding: it is what caught 7b shipping unwired, failing 16 of 30 on an unregistered route
rather than reporting nine confident measurements of whatever Vite serves for a hash it does
not recognise.

Two things this does not cover. The requirement under the table rather than in it — D5's "if
a flow needs explaining twice, redesign the flow" — has no instrument but the Fulfiller
filling a real order, and no order has been pulled. And none of this is a harness test: the
contract in `docs/GATES.md` is seven Python tests run at turn end, and this runs a browser.

| Constraint | Assertion |
|---|---|
| Body text | `font-size >= 20px` on every text node in the view |
| Body colour | any text token on any ground token — every pair clears 7:1, so this is a floor the palette cannot violate |
| Position label | `font-size >= 32px`, tabular figures |
| Card photo in pull modal | `>= 320px` on the short edge |
| Tap targets | `>= 44 x 44 px`, `>= 12px` apart |
| Contrast | `>= 7:1` for body text (WCAG AAA — assume reading glasses and a bright room) |
| Destructive actions | zero reachable from this view; assert no route to settings or import |
| Undo | present on every mark-sold, `>= 10s` window |
| Jargon | copy passes a banned-word list: SKU, CSV, import, sync, batch, queue, staged |

Default view on the Fulfiller's device. Sorted in box-walk order. Photo-confirm before each
pull. One-tap mark-sold.

## Step 6 — done 2026-08-12

Tokens locked, and the pull-confirm built against them in all three states. The spec it was
built to, because it is what `app/tests/pull-confirm.spec.ts` asserts:

```
default    fill #1E40AF, label #FFFFFF, radius 4px, >= 44px tall     8.7:1
pressed    fill #17348F, label #FFFFFF                             10.9:1
disabled   fill #FFFFFF, 1px #E6E7EA border, label #4E5157
           — never appears in the Fulfillment view
```

**One value in that block has moved since step 6, and the word "unchanged" that used to
introduce it has gone with it.** The disabled label is `muted`, and `muted` was redrawn on
2026-08-23 for the hover-ground reason argued at the top of this file; it read `#52555B`
here. Restated rather than rewritten silently, because nothing parses this second block —
`scripts/docs-audit.py` reads the fence under `## Tokens` and stops there, so this is the
one place in this file where a stale hex can sit unnoticed indefinitely. The ratio it is
quoted at went up (7.48:1 to 7.96:1 on `surface`), so the assertion this block describes
passes by more than it did; the spec computes it from the rendered colour either way.

`app/src/PullConfirm.tsx` and its stylesheet, rendered on a gallery route at `app/src/Gallery.tsx`.
`make screenshot` draws it into `captures/ui/`; `make design-check` measures it.

**Two props are worth knowing before step 7 reuses this.** `keyHint` is optional and renders
nothing when omitted, which is the Fulfillment case — those screens are touch and show no
keys. `disabled` exists for owner-side screens only; this view has no disabled state at all.

**"Catching a gap on one component is far cheaper than after ten screens" was the argument
for doing this before any screen, and the component paid for itself immediately.** Two of
them, both invisible in prose and both only findable by building the thing:

- **The button label had to be 20px, not the 18px `docs/design-refs/locked.html` draws.**
  The table below puts a 20px floor on every text node in the Fulfillment view, and a button
  label is a text node. The sheet violates the constraint printed a few inches above it.
- **The key chip does not belong on this control.** The sheet draws `↵` on all three
  pull-confirm states; "Every choice shows its key" is an owner-side rule, and this is the
  Fulfiller's button. It is the one control that is purely his.

Both are the doc's to win — `docs/design-refs/README.md` says so — and both are recorded
there so the sheets are not read as current.

## The screenshot loop is mandatory

`make screenshot` renders the key views to `captures/ui/`. Claude Code writes CSS it has
never looked at, so a layout that is technically correct can still be broken. Every UI
change: render, screenshot, compare against the reference and the table above, fix, repeat.
Two or three rounds gets to a production layout; zero rounds gets the generic default.

Give it a real visual reference before it codes. An adjective like "clean" produces the
average of everything the model has seen. A screenshot produces something specific — which
is why the tokens above are hex values and typeface names rather than words like "warm" or
"technical", and why they were chosen against a rendered card rather than described.

**The reference is `docs/design-refs/locked.html`, and it is in the repo for this reason.**
The sheets were built in a scratchpad while the tokens were being chosen and would have
died with that session, which would have left this paragraph asserting something the file's
own state contradicted. Hex values substitute for colour; they do not substitute for layout
or density, and those are most of what a reference carries.

## Copy rules

Active voice. The button says exactly what happens. An action keeps its name through the
whole flow: the button that says "Pull" produces a confirmation that says "Pulled."
Name things by what the Fulfiller controls, never by how the system is built — he has
orders and cards, not SKUs and rows. Errors say what happened and what to do next.

The owner's screens are the exception and only the exception: there, the pipeline's own
reason strings are shown verbatim beneath their labels, because being able to grep what you
saw is worth more to the person debugging a run than a consistent register is.
