# D121 — Home states what is owed

**Ruling: the Home lede states what is owed, ranked, with the verb in it.** The old lede read "100 cards on hand in 4 boxes · 19 sold. Every one has an address." Six replacements for it were rejected. The reason is the payload, not the presentation.

Each replacement restated the store's aggregate size. That figure repeats in the six-stage spine 24px below and in the Boxes panel below that. The one person who writes to this store already knows it. It is unchanged between most two openings of the page. Repeated, known and static is not information. It is furniture. The test for a replacement: does reading it change what the operator does in the next ten minutes?

### What the slot says

The slot shows what will not fix itself. `app/src/standing.ts` holds the order, and nothing else decides it. In rank order:

1. Copies an order has already sold that the store cannot find.
2. Copies to pull.
3. The review queue.
4. Runs owing a price.
5. A live run.
6. Cards photographed and never sent to a run.
7. Clear.

It is a module, not a component branch. A ranking that decides the front page every time it opens has to be somewhere a person can find it. A person must also be able to argue with it and test it.

### The null invariant

Three non-values are ranked at the row they would have answered: loading, failed, and read but refused. `ok` is reachable only from a complete reading, so green is never painted over a gap. `ServerStatus.queues.review` is `number | null` for this reason. Its own comment says a reader must render the gap and never coerce the null to zero. A count that errs toward "nothing to do" is worse than no count.

### The hero ends in one button

"Find a card" is gone. It duplicated `,I`, the palette, the nav item and the Inventory screen. It existed only to stop the primary button standing alone. `CLAUDE.md` described this screen as ending in one action while it drew two. That sentence is true now. The standing line is conditional, and the button is standing. The line joins them rather than replacing them. On a fresh store the line has nothing to press.

### The library is the ground, not the headline

The prior session and the whole library sit below the button, behind a hairline, in `--bn-ink-3`. The reader's eye lands on the first action.

The library figure is `status.cards - states.moved`, two integers already on Home's critical path. It is never `Σ boxes[].cards`, which counts both halves of D83's move. Nor is it a sum over `boxes[].on_hand`, whose member is null exactly when a box could not be counted. The code this replaced summed that nullable field behind `b.cards - b.sold - b.retired - b.moved`. It invented a figure in the case where the server had refused to give one.

### The unit is a sitting

A sitting is neither a day nor a run.

- **Not a day.** The operator shoots across midnight in UTC. Two of six real sittings fall on a different local day than their UTC day. Every bucket would move with the timezone. One UTC day held two sittings eighteen hours apart.
- **Not a run.** Three of the owner's nine runs share one `created_at`. That stamp is the identify date, not the capture date. `counts.cards_in` is not what a run photographed. `pipeline/join.py` builds it as `len(cards)` over the run's whole `identifications.json`. So it is the box's running total, rewritten on every re-join. Nine real manifests sum to 1,908, against 1,625 real records.

A sitting is recovered from `captured_at`, which is present on all 1,625 records. The 30-minute gap is a measurement, not a preference. A 5-minute gap gives 12 sittings. 15 gives 7. 30, 60, 120 and 240 all give 6.

### The drawing: a ribbon and a rug

Each block is as wide as the minutes that sitting took. It is as tall as the cards an hour it ran at, scaled so the fastest shown sitting draws at full height. Area is cards only, up to that one shared scale. So the marks do not read as absolute counts.

The axis is cumulative minutes. 113 minutes inside 9.4 days is 0.84% of the width. A calendar axis draws every block as a hairline: 2.1px at the widest and 0.04px at the newest. The calendar stays, demoted to the rug below the rule. A constant-size tick is the only mark that survives that scale.

The window is bounded. A plinth covers everything older, then the last eight sittings. So the drawing never grows with history. It has nine marks at six sittings and nine at two hundred.

### Colour is spent on pace, and redundant on purpose

The ramp runs from ink to `--bn-accent`. That is this system's action hue, not a status. So the foot makes no claim about whether anything is wrong. The standing line owns warn, live and ok. That separation is why the foot is achromatic. Hue and height both carry the pace, so a reader who cannot separate the hues loses nothing.

Vermilion is spent only while a run is actually running. Vermilion means live everywhere else in this product. Marking a sitting live because it is recent would be the one dishonest paint available here.

The dashed line at the top marks full height. Every other block is its rate's share of it.

### Fixed in the same change

`Home.css` set `pointer-events: none` on `.home-hero-art` with nothing to restore it. So the deck's own `<a>`, its hover lift and its focus ring were reachable by keyboard alone. Fewer than fifteen lines of comment said the deck opens the card it shows. The wrapper keeps the rule, so the empty-state deck stays inert. `a.home-deck` restores events for itself.

### What retires this

A second reader of the standing line's rank. The ranking is a policy with one consumer today. When a second screen needs "what is owed", the ranking should move to the server rather than be derived twice.

A Home figure equals the total its destination screen draws. Home counts only orders that read open.
