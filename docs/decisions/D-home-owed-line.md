## D-home-owed-line — Home keeps its shape, the "Behind that" line stops repeating the spine, and the spine drops to five stages

**Wave 2, home lane, 2026-09-24. Amends D121.** The owner's ruling on this lane was short and
specific. Quoted here: *"Keep Home as is". The Home button stays, and the "Behind that"
repeats are cut. box lists most recent first. box names only, never a box number. Runs FOLDS
INTO REVIEW (2026-09-24), so Home's six-stage strip becomes five: the Runs tile goes. Point its
identify count at Review. Do not redesign the hero.* This entry records what that ruling
changed in `app/src/standing.ts` and `app/src/Home.tsx`. It records nothing the ruling did not
name.

### "Behind that" no longer repeats a spine figure (UX-050, TXT-25)

D121 built the line to say what the spine could not. Three of its five branches (`unfindable`,
`pull`, `review`) pushed the SAME figures into a second line. That line was captioned "Behind
that:", 24px under the spine that already drew them — "27 copies to pull", "9 to review", "2
runs to price". That line was furniture on D121's own definition. It was duplicated, already
known, and answering nothing reading it changed.

`standing.ts`'s `behind` field is now `readonly string[]`, plain sentences with no figure in
them. The three branches that repeated a count return `behind: []`. The three that did not —
`fresh`, `working`, `clear` — are unchanged. Their one line each ("Boxes are made as you fill
them.", "Nothing is waiting on you.", "Every card photographed has been identified, priced and
sent.") carries no number the spine also draws, so it stays. `Home.tsx`'s `StandingLine` no
longer computes a "Behind that:" label. With no figure left to introduce, the label had nothing
to point at.

### The verdict says "missing" once, not "cannot" twice (UX-051, TXT-26)

"Cannot be filled — 6 copies for 7 open orders cannot be found." made the same claim twice. It
also undercounted itself on a fast read: "6 copies for 7" reads as less than one each. It is
now "Cannot be filled — 6 copies missing across 7 orders." The Orders stage tile uses the same
word: "27 to pull, 6 missing" (UX-039's own example). It used to say "not found".

### The press opens the orders that are actually short (UX-077)

The sentence names copies this store cannot find, across every open order. The press opens
Orders on the buyer list's "Show" facet, as `#/orders?show=<facet>`. `standing.ts` builds that
`href`.

Amended at the PR 2 integration, 2026-09-25, on the orchestrator's word. The first build set a
per-reason filter (`OrdersHubStore.setHub`) before the press navigated. The orders lane removed
that filter. The buyer list now filters only on each buyer's worst open order (UX-199). So the
press now names a facet in the URL (D285), and it sets no shared state.

The mapping, in `orderBuyers.ts`'s `unfindableFacet`:

- `dominantMissingReason` finds the reason that carries the most outstanding copies among the
  open orders (D202). It reads the same `resolution.orders` rows that the sentence sums. A tie
  keeps `ORDER_REASONS`'s own order.
- `short` and `no_copies_on_hand` map to `show=short`. Every other reason maps to `show=look`.
- The facet filters buyers, not lines. A buyer who owes a missing copy can read "Needs a look"
  because of another line. So the mapped facet is kept only where at least one buyer who owes
  a missing copy has it. If none does, the worst state that such a buyer has is used. The list
  is never empty while Home's figure is above 0.
- Where no open order owes a missing copy, the press opens plain `#/orders`.

`app/tests/home.spec.ts` presses the line against two ledgers: a buyer who is only short
(`show=short`), and a no-copies line whose buyer reads "Needs a look" (`show=look`). Each
checks that the buyer list is not empty. Dropping the fallback turns the second case red.

### Five stages, not six (Q6, 2026-09-24)

Runs folded into Review. Review's own screen gains an "Identify N cards, ~$X" strip, and the
Runs tile leaves the spine. Home's Review tile now falls back to the count of cards
photographed and never sent to a run (`status.states.captured`). It does this the moment its
own queue is answered. That backlog is never invisible for want of a tile — exactly what the
removed Runs tile used to carry. `#/runs` stays a registered route. Nothing here removes it.

### Box lists are most recent first (Q5), and a box is shown by its name (2026-09-23 ruling)

The Boxes panel now sorts by `deviceMemory.ts:storedBoxRecency()`. That is the same store
`BoxBrowse`'s own rail and `CaptureScreen`'s own picker read (D142). Then it sorts by cards on
hand, then by number, read once on mount. No box on this screen draws its bare number any more.
The panel's leading badge is an icon. The hero's fallback address chip, and its accessible
names, now draw the box's NAME. That is `box.name`, or the owner's own endorsed default,
`Box <n>` — never a second, different-looking guess.

The Capture tile is relabelled to match what it actually shows: the newest box's own card
count, and its name in the note. It no longer implies that it is the box the operator is
capturing into right now. The owner's D142 note said *"Home's tile is relabelled to what it
shows"*.

### Two smaller fixes, in the same files

**UX-139**: a box row's trailing figure (every card ever captured into that box) drew no unit.
It is removed. The bar and the "on hand"/"sold" pair already carry what the row needs. The
count with no label was the one figure on this screen naming nothing.

**UX-032 / UX-019**: Home had no link into `#/revenue`, the loop's last stage. The foot's own
"sold" figure is now that link. It is also the one place Home's "ever sold" count, and Sales'
own order-ledger total, could otherwise be read as one number. They are two different counts of
two different things.

**UX-074**: the Capture tile said "no boxes yet" while `GET /boxes` was still loading. Those
were the same words a genuinely empty store would draw. It now says "reading…" until the read
lands.

### What this entry does not touch

**The hero.** The greeting, the date, the button and the deck keep their shape and their copy.
TXT-28 and UX-129, both about the hero's own layout, are UNFIXED by name. The owner's ruling
was "keep Home as is" and "do not redesign the hero". A bigger title, or a smaller greeting, is
exactly that.

**UX-021.** Home's one button (`Start capturing`) stays the primary action, regardless of what
the standing line ranks first. That is an explicit exception the "button stays" ruling carries,
not an oversight.

**UX-004, fully.** Home's own words are internally consistent: "on hand", "photographed",
"sold", each used once for one meaning. The cross-screen half of this finding is different. The
sidebar's own count, Cards to pull's own count, and Runs' and Identify's own counts, each name
a different population, with no shared word. That reaches files this lane does not own.

**UX-081, fully.** Home's own uses of the review-queue concept now agree with each other:
"waiting", in the standing line and the tile. Pricing's own "N in review" sits in a different
file, owned by a different lane.

**`<Page>` (kit-adoption R1, R2-class, R2-date).** `app/src/Home.tsx` is still listed in
`scripts/kit-adoption-allow.json`'s static block, owed to `home`, against all three rules. See
this lane's report for why. Rendering `<Page>` puts a second, route-titled `<h1>` ("Home") over
a hero whose own `<h1>` is the greeting. R2-date's fix needs a new `dates.ts` export. It needs
one for "weekday, month, day", and one for "day, month" with no year. Neither exists, and
`dates.ts` is not this lane's file to add one to. Both are named rather than guessed at.
