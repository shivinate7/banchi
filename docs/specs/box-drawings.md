# The store as a drawing

**STATUS: SPECIFIED, NOT BUILT, PARKED.** Three ways to draw the inventory as the physical
thing it is. Nothing in `app/` renders any of this and no route is needed for any of it. They
were drawn on 2026-09-07 as candidates for the Home hero's lede, they were not what that slot
needed, and the owner parked them here rather than spend them: *"save those somewhere so I can
look into seeing a use for them at some time, but they won't be on the home screen."*

Open `docs/specs/box-drawings/sheet.html` in a browser. It is static — no build step, no
server — it links the real `app/src/tokens.css` by a relative path so it draws against the live
system rather than a copy of it that goes stale, and it renders every option in both themes with
an empty-store state under each.

**No render is committed beside it, and that is the opsec rule rather than an oversight.**
`scripts/githooks/pre-commit` refuses any image on a tracked path outside `demo-assets/photos/`,
because a code-card photograph is a bearer instrument and a rule with one exception is one a
session can reason its way past. So the sheet is the artefact and a PNG is something you make
when you want one:

```bash
npx --prefix app playwright screenshot --full-page \
  docs/specs/box-drawings/sheet.html /tmp/box-drawings.png
```

## Why they are parked rather than dropped

The lede they were competing for restates figures the six-stage spine already draws 24px below
it, and every drawing here has the same problem in that slot: it is a summary of the store's
size on a screen that is already summarising. That is an argument about **where**, not about
**whether**. `#/inventory` is the box walk and has no overview at all; a box's own panel has no
picture of the box; `#/orders` ranks by how many copies sit in one drawer and draws none of it.
Each of those is a place where a drawing of the drawers answers a question the screen is
actually asking.

## The finding that shaped all three

**A sold card is not a gap.** D58: sell card 17 and the card behind it becomes card 17 — the box
closes up, and the section boundaries move with it. The stored index keeps its hole; the
physical drawer does not. So none of these draws a departed card as a hole in the run: J1 puts
the open slots at the **end** of the packed run, which is what the box has sent out rather than
a hole in it; J2 leaves them out of the field and puts the figure in the key; J3 keeps them out
of the object and annotates them.

A drawing built on the gap premise would have contradicted the store's own rule while looking
entirely plausible, which is the failure mode a picture is worst at announcing.

**Every scale here is derived, never chosen.** J1's common drawer length is the fullest box's
own slot count (`on_hand + sold + dividers − 1`), plus three slots of run-out that the open end
dissolves into so the fade never eats a real card. Nothing claims a `capacity`: that figure is
meaningful only once a box is sealed, and drawing empty air against an unknown one is inventing
data.

## The three

### J1 — The shelf

Four rows, one per box, each a sunken well the length of the fullest drawer, with the cards
standing in it as spines at 1:1 — 41 marks for 41 cards. Dividers are thicker accent tabs
standing proud of the lip at their real indices. Departed cards are open slots at the end of the
run. The far end of every well dissolves. Each row links to `#/inventory?box=N`.

It says that the four boxes are wildly unequal and *how*, which "4 boxes" flattens to one digit;
that dividers exist and where; and that a card is a physical object taking linear space.

**Cost.** Small. Every figure is on `BoxRecord` and already fetched — `on_hand`, `sold`,
`sections`. Roughly 60 lines of TSX and 70 of CSS, no new route. Spine widths are computed
against the well so the small-multiple rescales with its column and needs no width breakpoint.
At four boxes of ~52 slots it is ~210 DOM nodes; at thirty boxes of 200 it is 6,000 and has to
become a canvas or a repeating background.

**Weakest of the three, and the reason is not execution.** Four horizontal tracks with a filled
portion is the silhouette of an occupancy bar that this owner had already turned down, and box 4
— 9 cards in a 54-slot well — reads at a glance like an unfilled progress bar. The countable
marks, the physical divider tabs, the departed slots and the shared well length are a real
defence, but it is a difference you have to look twice to see.

### J2 — The setting

Every card the store holds, set as running text and read like a paragraph: one mark per card, a
hair of space at each divider, a word-space and a labelled floor at each box, the runs wrapping
as units. The last card photographed is the one vermilion mark.

It shows the address space *as a space* — 100 cards, 8 compartments, 4 boxes, in the order you
would walk them, at a density where a finger lands on one card. It is the only one of the three
where the newest card is a located thing rather than a printed string, and the only one whose
growth story needs no second design: four boxes and forty are the same drawing at two lengths.

**Cost.** Smallest. One wrapping container over `sections_detail`, roughly 40 lines of TSX, no
new route.

**Its own flaw**: the mark field is close to a barcode, and a barcode is a machine's object
rather than a person's. If it reads as decoration instead of as 100 countable things, it has
nothing to fall back on. Its empty state is the thinnest of the three, because a field of
nothing is nothing.

### J3 — Plan

An architect's plan, in inline SVG. The object is drawn and nothing else: compartments at their
true lengths, cards hatched standing inside them, divider walls drawn as partitions rising past
the top edge. Everything written about it sits outside the object — compartment dimensions
below, a drafter's balloon per box, one arrowed dimension line with the total broken into it.
No fill anywhere. Theme-aware through `--bn-*` on classes, with `vector-effect="non-scaling-stroke"`
so hairlines stay hairlines at any scale.

It says that this is a *place*, that the place is measured, and that the compartment is the unit
the operator actually works in — `Section 2` is a divider-to-divider run they can put a hand on,
and nothing else drawn for this product has ever shown one. By being a drawing it also says the
store is finite and surveyable, which is the emotional opposite of a dashboard tile. Its empty
state is the best of the three: a dashed empty box under an arrowed dimension line reading `0`.

**Cost.** Highest, and the only one with real layout arithmetic: roughly 90 lines of generator
producing the SVG from `sections_detail`. No new route. SVG text does not reflow, so every label
position is computed and every one is a chance to collide.

**Its own flaw**: it may be too pleased with itself. The balloons and arrowheads do rhetorical
work that eight numbers in eight boxes would do more quietly, and it is the only option where a
phone loses information rather than density.

## If one of these is ever picked up

Three things are already settled and should not be re-derived.

**The D58 rule above.** A departed card is not a hole.

**All three are verified at 1180 and 390, light and dark**, with no horizontal overflow at 390
and no hex literal, no `rgb()` and no `--bn-font-mono` anywhere in the three blocks. J1's rows
go to 44px at 390 and its names ellipsize; J3 hides its compartment dimensions below 460px,
deliberately the first thing to go.

**The node-count ceiling is the real constraint, not the CSS.** One DOM node per card is fine at
100 and is not fine at 10,000. Whichever screen adopts one of these, that is the question to
answer first.
