## D121 — The front page says what is owed, and the library is drawn as the work that made it

**Built 2026-09-07, on the owner's instruction.** The lede under Home's greeting read
*"100 cards on hand in 4 boxes · 19 sold. Every one has an address."* Six replacements were
drawn and all six were rejected at once; the owner's verdict was that none of them were doing
it. They were right, and the reason is structural rather than a matter of treatment.

**THE PAYLOAD WAS THE PROBLEM, NOT THE PRESENTATION.** Every one of the six restated the store's
aggregate size, and that figure is (a) drawn again by the six-stage spine 24px below and by the
Boxes panel below that, (b) already known to the only person who ever writes to this store, and
(c) unchanged between most two consecutive openings of the page. Duplicated, already known and
static is not information; it is furniture. Six pieces of furniture in six shapes. The test the
replacement had to pass is whether reading it changes what the operator does in the next ten
minutes.

**WHAT THE SLOT SAYS NOW IS WHAT WILL NOT FIX ITSELF**, ranked, in one sentence, with the verb
in it. `app/src/standing.ts` holds the order and nothing else decides it: copies an order has
already sold that the store cannot find, then copies to pull, then the review queue, then runs
owing a price, then a live run, then cards photographed and never sent to a run, then clear. It
is a module and not a component branch because a ranking that decides the front page of this
product every time it opens has to be somewhere a person can find, argue with and test.

**THE NULL INVARIANT IS THE LOAD-BEARING PART.** Three distinct non-values — loading, failed,
and read-but-refused — are each ranked at the row they would have answered, and `ok` is
reachable only from a complete reading, so green can never be painted over a gap.
`ServerStatus.queues.review` is `number | null` for exactly this reason, and that type's own
comment already said a reader must render the gap and never coerce the null to zero, because a
count that is wrong in the direction of "there is nothing to do" is worse than no count at all.

**THE HERO ENDS IN ONE BUTTON.** "Find a card" is gone: it duplicated `,I`, the palette, the nav
item and the whole Inventory screen, and existed to stop the primary being lonely. `CLAUDE.md`
described this screen as ending in *one action* while it drew two; that sentence is now true
rather than needing an edit. The standing line is CONDITIONAL and the button is STANDING, which
is why the line joins them rather than replacing them — on a fresh store the line has nothing
to press.

**THE LIBRARY CAME BACK, BUT AS THE GROUND AND NOT THE HEADLINE.** The owner's amendment was
that the replacement lacked *"the library at a glance — no way of seeing my prior session nor
entirety of library."* Both now sit BELOW the button, behind a hairline, in `--bn-ink-3`, so a
reader's eye lands on what to do first. The figure is `status.cards - states.moved` — two
integers already on Home's critical path — and never `Σ boxes[].cards`, which counts both halves
of D83's move, nor a sum over `boxes[].on_hand`, whose member is null exactly when a box could
not be counted. The code this replaced summed that nullable field behind
`b.cards - b.sold - b.retired - b.moved`, inventing a figure in precisely the case where the
server had refused to give one.

**THE UNIT IS A SITTING, AND IT IS NEITHER A DAY NOR A RUN.** A day is wrong because the
operator shoots across midnight in UTC — two of six real sittings fall on a different local day
than their UTC day, so every bucket moves with the timezone, and one real UTC day held two
sittings eighteen hours apart. A run is wrong three times over: three of the owner's nine runs
share one `created_at`; that stamp is the IDENTIFY date rather than the capture date; and
`counts.cards_in` is not what a run photographed at all — `pipeline/join.py` builds it as
`len(cards)` over the run's whole `identifications.json`, so it is the box's running total,
rewritten on every re-join, and nine real manifests sum to 1,908 against 1,625 real records.
A sitting is recovered from `captured_at`, which is present on all 1,625 of them.
**The 30-minute gap is a measurement and not a preference**: 5 minutes gives 12 sittings,
15 gives 7, and 30, 60, 120 and 240 all give 6.

**THE DRAWING IS A RIBBON AND A RUG, AND ITS AREA IS ITS CARDS.** Each block is as wide as the
minutes that sitting took and as tall as the cards an hour it ran at, so `minutes × rate ÷ 60 =
cards` is an identity and the marks still sum to the figure printed above them while the height
carries something that figure cannot. Read back off the drawn geometry the six blocks give
543 / 172 / 152 / 138 / 555 / 65, which are the true counts. The axis is CUMULATIVE MINUTES
because 113 minutes inside 9.4 days is 0.84% of the width — a calendar axis draws every block
as a hairline, 2.1px at the widest and 0.04px at the newest. The calendar is not dropped but
demoted to the rug below the rule, where a constant-size tick is the only mark that survives
that scale. The window is bounded — a plinth for everything older, then the last eight sittings
— so the drawing never grows with history: nine marks at six sittings and nine at two hundred.

**COLOUR IS SPENT ON PACE, AND IT IS REDUNDANT ON PURPOSE.** The ramp runs from ink to
`--bn-accent`, which is this system's ACTION hue and not a status, so the foot makes no claim
about whether anything is wrong — the standing line above owns warn, live and ok, and that
separation is the whole reason the foot was achromatic to begin with. Hue and height both carry
the pace, so a reader who cannot separate the hues loses nothing.
**Vermilion is spent only while a run is actually running**, because vermilion means live
everywhere else in this product; marking a sitting live for being recent would be the one
dishonest paint available here.

**The ceiling is a physical fact.** Full height is 5,906 cards an hour — the rig's own measured
0.6095 s per card. Without the ceiling drawn, a block 1.5px tall reads as a MISSING block rather
than as a slow sitting, which is the opposite of the truth.

**Fixed in the same change, because it ships into this hero either way**: `Home.css` set
`pointer-events: none` on `.home-hero-art` with nothing restoring it, so the deck's own `<a>`,
its hover lift and its focus ring were reachable by keyboard alone — for as long as the deck has
been a link, under fifteen lines of comment saying it opens the card it is showing. The wrapper
keeps the rule, so the empty-state deck stays inert; `a.home-deck` restores it for itself.

**What retires this:** a second reader of the standing line's rank. It is a policy with one
consumer today, and the moment a second screen wants "what is owed" the ranking should move to
the server rather than being derived twice.
