## D287 — Home keeps shape; five stages

**Amends D121.** The owner's ruling on this lane was short and specific: keep Home as is. The Home button stays, and the "Behind that" repeats are cut. Box lists are most recent first. Boxes show names only, never a box number. Runs folds into Review, so Home's six-stage strip becomes five. The Runs tile goes, and its identify count points at Review. Do not redesign the hero. This entry records what the ruling changed in `app/src/standing.ts` and `app/src/Home.tsx`. It records nothing the ruling did not name.

### "Behind that" no longer repeats a spine figure (UX-050, TXT-25)

D121 built the line to say what the spine could not. Three of its five branches (`unfindable`, `pull`, `review`) pushed the SAME figures into a second line. That line was captioned "Behind that:", 24px under the spine. It repeated "27 copies to pull", "9 to review" and "2 runs to price". By D121's own definition it was furniture: duplicated, already known, and answering nothing.

`standing.ts`'s `behind` field is now `readonly string[]`, plain sentences with no figure in them. The three branches that repeated a count return `behind: []`. The three that did not (`fresh`, `working`, `clear`) are unchanged. Their one line each carries no number the spine draws: "Boxes are made as you fill them.", "Nothing is waiting on you.", and "Every card photographed has been identified, priced and sent." So those stay. `Home.tsx`'s `StandingLine` no longer computes a "Behind that:" label. With no figure left to introduce, the label had nothing to point at.

### The verdict says "missing" once, not "cannot" twice (UX-051, TXT-26)

"Cannot be filled — 6 copies for 7 open orders cannot be found." made the same claim twice. It also undercounted on a fast read: "6 copies for 7" reads as less than one each. It is now "Cannot be filled — 6 copies missing across 7 orders." The Orders stage tile uses the same word: "27 to pull, 6 missing" (UX-039's own example). It used to say "not found".

### The press opens the orders that are actually short (UX-077)

The sentence names copies this store cannot find, across every open order. The press opens Orders on the buyer list's "Show" facet, as `#/orders?show=<facet>`. `standing.ts` builds that `href`.

Amended at the PR 2 integration, on the orchestrator's word. The first build set a per-reason filter (`OrdersHubStore.setHub`) before the press navigated. The orders lane removed that filter. The buyer list now filters only on each buyer's worst open order (UX-199). So the press names a facet in the URL (D285) and sets no shared state.

The first mapping sent `REASON: short` and `no_copies_on_hand` to `show=short`. But `statusOf` files a no-copies line under "Needs a look" unless a copy was recorded for it. On the owner's store, Home said "135 copies missing across 71 orders" and opened `show=short`. That list held 6 buyers and 10 of the copies. The other 125 were under "Needs a look", and only 57 open orders missed a copy at all.

The second build filed each buyer under `worstStatus` and opened the "Show" facet holding the most missing copies. That still split the copies across two facets: 125 under "Needs a look", 10 under "Short". No single status list matched the sentence.

The owner chose option c: a "missing a copy" filter. The build now does this:

- One rule, `orderBuyers.ts`'s `groupMissing`. A buyer's missing copies are the `outstanding` copies on its open orders (D121). Its missing orders are the open orders with any.
- Home's sentence sums that rule over every buyer (`missingCopies`). It counts every missing copy, and only the open orders that miss one.
- Orders' "Show" facet gains a value, `missing`, labelled "Missing a copy". It lists every buyer the same rule counts, whatever that buyer's state. Its count is the rows it shows. It is offered only while it has any. Under it, each row says its own missing copies and orders.
- The press opens `#/orders?show=missing&show=noneleft&show=short` (D285's URL view state; D304 Q2b words each).

`app/tests/home.spec.ts` presses the line against a ledger shaped like the owner's store. One buyer misses 5 copies under "Needs a look". One misses 1 copy under "Short". One open order misses nothing. The case checks "6 copies missing across 3 orders", then sums the opened list's rows, and requires exactly 6 copies and 3 orders. The old code opened `show=look` and went red. `app/tests/orders.spec.ts` checks the option's count, its list, and that it is not offered while no buyer owes a missing copy.

### Five stages, not six (Q6)

Runs folded into Review. Review's own screen gains an "Identify N cards, ~$X" strip, and the Runs tile leaves the spine. Home's Review tile now falls back to the count of cards photographed and never sent to a run (`status.states.captured`). It does this the moment its own queue is answered. That backlog is never invisible for want of a tile, which is what the removed Runs tile used to carry. `#/runs` stays a registered route. Nothing here removes it.

### Box lists are most recent first (Q5), and a box is shown by its name

The Boxes panel sorts by `deviceMemory.ts:storedBoxRecency()`. That is the store `BoxBrowse`'s rail and `CaptureScreen`'s picker read (D142). Then it sorts by cards on hand, then by number. The sort is read once on mount. No box on this screen draws its bare number now. The panel's leading badge is an icon. The hero's fallback address chip, and its accessible names, draw the box's NAME: `box.name`, or the owner's endorsed default, `Box <n>`. They never draw a second, different-looking guess.

The Capture tile is relabelled to match what it shows: the newest box's own card count, and its name in the note. It no longer implies that it is the box the operator is capturing into now.

### A zero-count Review tile goes plain (B14)

On Home, a Review tile at zero draws plain. It has no chevron, and its count is quiet. It keeps the same box as the other tiles.

### Runs rows show a date, a time and a quantity

Each row in Home's recent runs keeps what it shows now: the box label, the relative date and the stage. It also shows the run's date, its time stamp and its quantity run. The row adds no box name and no run name (D196, no mechanism on screen). A quantity run is the number of cards in the run.

### Two smaller fixes, in the same files

**UX-139**: a box row's trailing figure (every card ever captured into that box) drew no unit. It is removed. The bar and the "on hand"/"sold" pair already carry what the row needs. The unlabeled count was the one figure on this screen naming nothing.

**UX-032 / UX-019**: Home had no link into `#/revenue`, the loop's last stage. The foot's own "sold" figure is now that link. It is also the one place where Home's "ever sold" count and Sales' order-ledger total could be read as one number. They count two different things.

**UX-074**: the Capture tile said "no boxes yet" while `GET /boxes` was still loading. Those were the same words a genuinely empty store would draw. It now says "reading…" until the read lands.

### What this entry does not touch

**The hero.** The greeting, the date, the button and the deck keep their shape and copy. TXT-28 and UX-129, both about the hero's own layout, are UNFIXED by name. The owner's ruling was to keep Home as is and not redesign the hero. A bigger title or a smaller greeting is exactly that.

**UX-021.** Home's one button (`Start capturing`) stays the primary action, whatever the standing line ranks first. That is an explicit exception the "button stays" ruling carries, not an oversight.

**UX-004, fully.** Home's own words are internally consistent: "on hand", "photographed", "sold", each used once for one meaning. The cross-screen half is different. The sidebar's count, Cards to pull's count, and the Runs and Identify counts each name a different population, with no shared word. That reaches files this lane does not own.

**UX-081, fully.** Home's own uses of the review-queue concept now agree: "waiting", in the standing line and the tile. Pricing's "N in review" sits in a different file, owned by a different lane.

**`<Page>` (kit-adoption R1, R2-class, R2-date).** `app/src/Home.tsx` is still listed in `scripts/kit-adoption-allow.json`'s static block, owed to `home`, against all three rules. Rendering `<Page>` puts a second, route-titled `<h1>` ("Home") over a hero whose own `<h1>` is the greeting. R2-date's fix needs a new `dates.ts` export: one for "weekday, month, day", and one for "day, month" with no year. Neither exists. `dates.ts` is not this lane's file to add to. Both are named rather than guessed at.
