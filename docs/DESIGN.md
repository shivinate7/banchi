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
           #52555B  muted     metadata, secondary labels, disabled         7.29:1 on bg
           #E6E7EA  line      the 1px hairline. Every separation, no exceptions.
           #1E40AF  accent    unsure, and the only-action fill             8.5:1 on bg
           — plus two interaction states derived from the above —
           #F4F5F7  hover     row hover only. bg and surface are 1.5% apart, so
                              neither can serve as a hover state for the other.
           #17348F  pressed   accent, pressed. White on it: 10.9:1.
           — and one token that names a value already in use —
           #FFFFFF  on-accent label on an accent or pressed fill. Never a ground.

Display    Cabinet Grotesk  (Fontshare)   700/800 only, and only at >= 20px
Body       Atkinson Hyperlegible (Google) 400/700
Utility    Martian Mono     (Google)      400/500/600, tabular by construction

Spacing    4 8 12 16 24 32 48 64        one scale, no other values
Radius     4px                          one value, everywhere
```

**One system, two densities.** Owner screens use the 4–16 end of the scale; the Fulfillment
view uses 24–64 and the minimums in the table below. Same palette, same three faces, same
radius. The alternative — two deliberately different visual worlds — was considered and
rejected: it doubles the token surface and gives two components to keep in sync, and the
Fulfillment constraints are already expressible as a floor applied to a subset of routes.

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
answers cost two taps each. Genuinely destructive actions may still gate — but per the
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
single column; the sentence; the candidate rows with their keys; the human label over the
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

**One card at a time, photo first, single column.** Photo as large as the viewport allows at
the top, then one
sentence naming what the system found, then the candidate rows with their prices. No
left/right split, so the same layout works on a laptop and a phone. Answering advances
immediately.

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

**Worked expensive-first, and that ordering is visible.** `store/queues.py:sort_key` sorts
priced cards first and descending, unpriced last, then box-walk order by box and index;
`app/src/ReviewQueue.tsx:bandOf` puts every worklist row in one of five type-size bands cut
from that same price, and a parked row is dimmed rather than merely lower. A queue where
every row looks equally important has thrown away a sort it already has.

**The band edges are the one number on this screen nobody has measured**, and they are
marked as an assumption at the place they are cut as well as here. They are multiples of
D9's $0.40 threshold, so they follow it if it moves — the same instinct D9 applies to its
own sub-threshold bands — but the multiples are a guess at a price distribution that does
not exist yet. Unpriced is deliberately not the bottom band: `pipeline/routing.py` holds
that no price is not a low price, so drawing it smallest would teach the eye the opposite of
what routing decided. `docs/specs/capture-app.md` §10.2 item 3 is the measurement that
redraws them, and redrawing them invalidates nothing else in that file.

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

**Reason codes: human label large, machine string small beneath it.** The pipeline defines
twelve strings — six from the variant ladder in `pipeline/variant.py`
(`no_catalog_row`, `metadata_not_stocked`, `metadata_detection_disagreement`,
`detected_finish_not_stocked`, `ambiguous_no_signal`, `duplicate_condition`) and six from
routing in `pipeline/routing.py` (`low_confidence`, `no_position`, `identification_failed`,
`set_ambiguous`, `card_not_detected`, `no_market_data`). Showing only a friendly label
creates a second vocabulary that nothing audits — the drift D16 exists to catch — and
leaves no way to get from what you saw on screen to what the pipeline actually said.
Showing only the raw string is honest and unreadable. Both, at two sizes, costs one line of
chrome and keeps the string greppable across the screen, the run report and `review.json`.
**Owner-side only**: the Fulfillment banned-word list forbids this register entirely.

**Eleven of the twelve can reach this screen. `no_market_data` cannot, and this paragraph
used to say otherwise.** It is not a queue reason: `pipeline/routing.py` makes it the fourth
destination beside listed, main and parked, and `pipeline/join.py` writes a queue entry only
for `routing.MAIN` and `routing.PARKED` — so a card with a blank or $0.00 market cell is
priced by hand in `decisions.json` (D9) and never appears here. The screen carries a label
for it all the same, which is right: one line of a lookup table is cheaper than a bare
machine string rendered the first time routing ever queues one. The claim to keep out of
this file is the count — twelve are defined, eleven are reachable, and the two numbers
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
undo, and it would have to be cleared by something. What settles the control is Gate B
traffic (`docs/specs/capture-app.md` §10.2 item 1). If nothing is ever skipped, delete it.
If most of a queue is, the screen needs a real defer that records a reason, and that is a
decision entry rather than a button.

**Mono carries all metadata.** Reason codes, set and collector number, age, counts,
positions and prices are utility face, uppercase, tracked. The body face is reserved for
sentences a human reads. This one rule does more than any other to keep the thing from
reading as a newspaper.

## Fulfillment view — hard constraints, assert these in a test

The agent cannot see its own output, so these are Playwright assertions, not prose.

**All nine rows now run, against the view itself.** `app/tests/fulfillment.spec.ts` asserts
every row of the table below on the Fulfillment view; `app/tests/pull-confirm.spec.ts` keeps
three of them on step 6's component. `make design-check` runs both — 30 assertions, observed
passing 2026-08-13. Every contrast ratio is computed from the *rendered* colours rather than
compared against a number published here, so a token edited in `app/src/tokens.css` without
being re-argued in this file has to break something.

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
built to, unchanged, because it is what `app/tests/pull-confirm.spec.ts` asserts:

```
default    fill #1E40AF, label #FFFFFF, radius 4px, >= 44px tall     8.7:1
pressed    fill #17348F, label #FFFFFF                             10.9:1
disabled   fill #FFFFFF, 1px #E6E7EA border, label #52555B
           — never appears in the Fulfillment view
```

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
