# Settled decisions — singles pipeline

Every entry here is closed. Sessions do not re-litigate them. To reopen one, name the
entry and the new evidence, then wait for the owner. Rewrite entries in place when a
decision changes — do not append history.

---

## D1 — Two-phase architecture

Capture is fast, offline, and dumb. Identification and pricing happen later in batch.
Never merge them: speed, cost, and reliability all favor the split.

## D2 — Identification is Claude Haiku vision, owned end to end

OCR was researched and rejected (~85–90% accuracy). Perceptual hashing is deferred to v2
as a cross-check. Haiku costs ~$5–15 per 10k cards via the Batch API, which is negligible.
The set hint is an optional accelerator recorded in the capture app: identification works
without it, better with it.

**TCGplayer Scan & Identify was evaluated and rejected as a pipeline component.** It is
UI-only with no API contract, inserts a manual browser step into an autonomous flow, does
not guarantee per-image→position mapping, and couples identification to one platform. No
integration code is written, ever.

**It is also not a precondition for anything** (changed 2026-08-03). It was previously the
required next step whenever T1 scored below the floor, which put a manual browser session
on the critical path between a red harness and any attempt to fix it — the tail wagging the
dog. A sub-floor T1 is now worked directly. S&I is parked in the Someday list below as an
optional reference point: it answers "is this task hard, or is our prompt weak?", which is
worth knowing eventually and worth nothing urgently.

Evaluate any future third-party integration on: API or UI? Does it return the data the core
depends on? Does the cost it replaces matter? Does it add a manual step? Does it couple us
to one platform?

## D3 — Variant resolution ladder

Resolve normal / reverse holo / holo per card, in order:

0. **A human's answer, if there is one** (added 2026-08-22). Above the ladder rather than a
   rung inside it: `pipeline/join.py` applies it before the walk below starts, and the
   routing gate cannot re-queue it. The distinction is the point — every rung below infers
   a finish from evidence, and an answer is not an inference. It reads `sku` and
   `condition` off the live inventory record, so a card the owner has ruled on in the
   review queue keeps that ruling on every later join.

   **It falls through rather than guessing.** If the current export no longer carries that
   SKU, or carries it under a different Condition, the answer is discarded and the card
   walks the ladder normally — the same as if nobody had answered.

   Recorded here because Gate B is what produced it: the answer route wrote answers that
   nothing on the join path ever read back, so sixteen answered cards re-derived their
   disagreement on every join and re-parked forever. An answer that does not outlive the
   question is not an answer. Tested by T3, not T4 — it is a join behaviour, not a ladder
   behaviour, which is the same distinction this entry draws.
1. **Capture-time metadata** — finish claim in the capture app, stored in the card's JSON
   sidecar. Primary path. `--variant` on the batch script **fills the finish in where a
   sidecar records none, and never overrides one** (clarified 2026-08-03; this entry
   previously read "only an override", which the implementation would have had to read as
   licence to replace a recorded toggle).

   Fill-gaps rather than override, because the rest of this entry spends three paragraphs
   establishing that the toggle is a *claim* — and a flag that can flatten a box you
   toggled stack by stack is precisely what makes it stop being one. The case the flag
   actually exists for is the capture app not existing yet: a directory of photos with no
   sidecars at all, where every card stocked in more than one finish would otherwise cost a
   review-queue tap. Overriding a recorded toggle buys nothing there, since there is
   nothing recorded to override.

   **THE CLAIM IS A SET, NOT A SINGLE FINISH** (amended 2026-08-23, by the owner). It was
   one string, and one string can only describe a stack that is uniform. A stack that
   genuinely holds two finishes had no honest claim available: the operator could name one
   finish and be wrong about half the cards, or claim nothing and throw away the half of
   the truth they did know. Both are worse than saying what is actually true, which is
   *"this stack is normals and reverse holos"*.

   **How many members it has decides what it DOES, and this is the whole of the amendment:**

   - **One member behaves exactly as this rung always has.** It determines. It outranks the
     catalog at rung 2 and it is what detection is cross-checked against at rung 3. Nothing
     about the single-claim path changes, which is what makes this amendment additive
     rather than a rewrite of the ladder — every card captured before today reads as a
     one-member claim and resolves down the identical path.
   - **Two or more members FILTER rather than determine.** The candidate rows are narrowed
     to the claimed finishes, and the rungs below choose within what survives — the catalog
     at rung 2 if exactly one row is left, detection at rung 3 otherwise. The claim is still
     trusted; it is simply less specific, and a less specific claim can only ever narrow.
   - **A filter that empties reviews as `metadata_not_stocked`**, the reason code that
     already means "the operator claimed a finish this number is not stocked in". No new
     reason code, because no new situation: claiming `{holo, reverse_holo}` against a number
     that stocks only `normal` is the same fact as claiming `holo` against it, and the
     triage a human does is the same.
   - **An empty set is no claim at all**, identical to the null this field has always
     allowed, and it is what leaves rungs 2 and 3 fully live.

   **This is deliberately the shape D23 gave the rarity claim** — filter the candidates,
   contradict if nothing survives — and the two now behave the same way for the same
   reason. That is worth more than the feature: a capture screen whose claims all work one
   way is one rule to hold, and the alternative was a finish that determines beside a rarity
   that filters, with nothing but history to explain the difference.

   **A BARE STRING READS AS A ONE-MEMBER SET, AND NOTHING EVER WRITES ONE.** The same
   read-side backfill D21 uses for `game`, chosen for the same reason and with the same
   boundary: 767 live records and every sidecar ever written carry a string, and a
   migration that rewrote them would be a write across the whole store to change nothing
   any reader could not do for itself. Read-side, never write-side — a new capture always
   writes a list, so the file converges without a migration and without a version bump.2. **Catalog-forced** — no capture-time metadata, and one condition row for that number
   (most SV-era rares are holofoil-only), so the row decides.
3. **Haiku `finish` field** (`normal | holo | reverse_holo`), returned in every
   identification call at no extra cost. Runs as a cross-check even when metadata exists:
   a normal card mis-sorted into the reverse stack still matches a valid catalog row, so
   only detection catches it.
4. **Review queue** — still ambiguous, detection disagrees with metadata, the catalog
   contradicts metadata, or no matching catalog row.

**The toggle is trusted.** It is set per stack, so metadata is a claim and not a hint.
Metadata naming a variant the catalog does not stock — toggle says normal, the number has
only a holofoil row — reviews rather than being corrected to the only available row. This
costs a tap per mis-toggled holofoil-only rare; that is the price of the toggle meaning
something, and it is why rung 2 is reachable only without metadata. The two review reasons
stay distinct so the queue can be triaged: a run full of contradictions means a stack is
misfiled, while disagreements scattered across a run mean individual cards are mis-sorted — or that the detector is systematically wrong, which is the reading Gate B added on 2026-08-22 and the first one to check now. 16 of 53 normals read as foil under the rig's lighting, and detection agreed with itself across duplicate copies of the same card, so that run's scattered `metadata_detection_disagreement` meant neither a misfiled stack nor mis-sorted cards: it meant the rig. `docs/GATES.md`'s Gate B section holds the numbers. Rung 3 survives it — a cross-check that spends 30% of a run on review taps is still cheaper than one wrong listing — but the two-way triage above is no longer the whole table.

**RUNG 3 CAN NOW BE SWITCHED OFF FOR A RUN, AND BOX 2 IS WHY** (owner's ruling, 2026-08-24;
`pkmnscan join --bypass`). The paragraph above kept rung 3 on the argument that a 30%
false-positive rate is still cheaper than one wrong listing. At 544 cards with the owner
supplying ground truth, the rate was **42% — 230 cards contradicting a claim that was right
every single time** — and the same photograph read differently at two downscales on 19 of 40
cards. `docs/GATES.md`'s box-2 section holds the numbers. A cross-check that is wrong more
often than the thing it checks has stopped being a cross-check, and 230 review taps against a
claim the operator already knows is correct is not a cost the ladder is entitled to impose.

**The flag is ONE RULE: where a finish claim exists, detection may not contradict it — but it
may still choose inside it.** Both halves matter. Suppressing rung 3 wholesale would throw away
its real work, which is picking between the members of a multi-finish claim; suppressing only
its power to contradict is the narrowest change that answers the measurement.

**It does not reach any other rung, and the reason is the same one that makes the flag
honest.** A card with no claim is untouched, because there is nothing to resolve it by.
`metadata_not_stocked` is untouched, because a claim the *catalog* contradicts is a different
fact from a claim *detection* contradicts, and listing through it would sell a finish the
number is not stocked in. `no_catalog_row` is untouched, because there is no row to resolve
to. The operator's own framing is the boundary and it is worth keeping in their words: the
bypass trusts your claim, it does not invent a row for it.

**A bypassed card resolves at RUNG 1 and is COUNTED.** No new stage and no new reason code:
rung 1 has always meant "the claim determined", which is exactly what happened. What is new is
that `Resolution.bypassed` records that a contradiction was set aside, so `join` can report the
number rather than leave it inferred from a smaller queue — the owner's choice, in their words,
was *"resolved by the claim, and the run report says so"*. It is named on the run's stdout, in
`report.txt`, and in the manifest as `bypass_detection` beside its count.

**Per-run and opt-in, never a default.** The precedent is `--review-below-confidence=none`,
which this deliberately copies: a routing switch the operator sets for a run they can see the
shape of, rather than a threshold moved once for everybody. `join --dry-run` exists so the
shape is visible before the choice — it walks the ladder twice, with the flag and without, and
diffs the two queues, writing nothing at all.

**What would reopen this: a rig that measures better.** The flag treats the detector as
untrustworthy under this lamp, which is what two runs measured. It is not a finding about
foil detection in general, and a re-measurement after the lighting changes is the evidence
that would make rung 3 worth leaving on.

## D4 — Review queue is digital-only

Shows the stored capture photo beside candidate catalog rows for a one-tap choice. The
physical card never leaves its box; unresolved cards stay unlisted at a known position.

## D5 — Two personas

The owner handles capture, processing, pricing, imports, and settings. A retired,
non-technical family member handles fulfillment from his own device. Fulfillment-facing
screens must be self-evident. Constraints in `docs/DESIGN.md`.

## D6 — Photo service and pull preview

The capture server serves stored photos at `GET /photo/<box>/<position>`. The review queue
requires it; the pull modal reuses it, showing the card's own capture photo beside its
location before pulling. Photos are position-keyed on disk — this is display, not new
storage.

## D7 — Duplicates aggregate by SKU at join time

Multiple copies of the same card+variant collapse into ONE fixture row with
`Add to Quantity` = copy count. Inventory keeps every copy as its own position with its own
photo; the app maps SKU → all positions holding it.

**Live quantity caps at 4 per SKU** (a playset; configurable) regardless of copies owned.
This blocks envelope-buster orders, and a price spike sells at most 4 stale-priced copies
before repricing — the same rationale behind TCGplayer's own Buylist Max Listing feature.

Excess copies are backstock at known positions. Refill on later imports as
`Add to Quantity = min(cap - live, backstock)`, with live quantities read from Export From
Live. Price is per-SKU and shared across copies.

**COPIES ARE FUNGIBLE, AND `live` IS A QUANTITY RATHER THAN A SET OF ADDRESSES** (amended
2026-08-23, by the owner). This entry used to say order pulls "select specific positions",
and `cli/cmd_join.py` implemented that literally: it walked `positions_for_sku`, filtered to
staged copies, and promoted the first N of them, so four of seven identical cards were
sellable and three were not for no physical reason at all. The owner's words: *"if i have 15
of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations are live and 12
are backstock."*

So the three listing stages moved off the card and onto the SKU:

- A position's `state` is `captured`, `identified` or `sold`, and describes one physical
  card. `pushed`, `staged` and `live` are no longer members of `master.STATES`, and
  `check_state` refuses them — which is what stops a caller reaching for the old
  `set_state(key, LIVE)` and quietly getting a per-position flag back.
- `store/master.py:Listing` holds `pushed` / `staged` / `live` as counts per SKU.
- **Every unsold copy is sellable.** The pull marks whichever copy the hand reached, and the
  sale decrements the SKU's `live` count, floored at zero.
- Copies on hand is a count of unsold positions; listed quantity is `min(cap, on hand)`.

**THAT LAST `min` REACHED THE PIPELINE AND NOT THE SCREEN, until the owner caught it on
2026-08-25.** `pipeline/join.py:add_to_quantity` has always bounded by the copies actually held
(`min(room, uncommitted)`), but `GET /search` sent the bare `LIVE_QUANTITY_CAP` and
`CardLocations.tsx` drew it as the denominator of `listed N of ...` — so a card the owner had
exactly one of read **`listed 0 of 4`**, two inches from `on hand 1`. Not wrong about the cap;
wrong about what a fraction means. A denominator is read as what is achievable, and three of
those four copies do not exist — which is the failure D20 spends its whole entry on, at SKU
scale instead of box scale.

`SearchGroup` now carries **both**: `cap` is the rule, `listable` is `min(cap, on hand)` for that
SKU. Computed server-side, because `app/src/server.ts` records that the app is forbidden from
computing the live cap and a `Math.min` in TypeScript is that rule kept in two places. T7 asserts
the arithmetic rather than the literal, so it moves the day the cap does.

**The decrement is an optimistic local estimate, and that is not a weakness of it.** D8 and
D11 already put the authority in the TCGplayer export's `Total Quantity`, which `join` reads
on every run — so this number was never a second source of truth competing with the export,
and a run corrects whatever drift a between-run sale introduced. The failure this ordering
prevents is the opposite one: holding the count back until a join makes the app disagree with
the shelf the operator is standing in front of.

**Backstock is therefore a number, not a place.** "Excess copies are backstock at known
positions" above stays true in the only sense that matters — every copy is at a known
position and the app maps SKU to all of them — but no copy is *designated* backstock, and
nothing may reintroduce a per-position listing flag to make it so.

## D8 — Pricing source is the TCGplayer Filtered CSV export itself

It carries live, per-SKU, per-variant `TCG Market Price`. Threshold checks and pricing rules
run directly against it. No external pricing API.

pokemontcg.io data serves identification support (set IDs, collector numbers, printedTotal)
and eval images only — never pricing. That role is unchanged by D15, which vendors the same
data locally: the split above is why a snapshot is safe, since nothing price-shaped is in it.
Read this entry as naming what the data is *for*, not as authorising a call to the live API.

## D9 — Threshold and floor are both $0.40

Both configurable, both derived from the $60/hr labor bar: a marginal pull is ~20s, and
0.8675 × $0.40 clears it.

- **Threshold**: market ≥ $0.40 earns a listing.
- **Floor**: listed price = `max(pricing-rule output, $0.40)` — clamps undercut rules in
  collapsing markets. TCGplayer's own seller guidance is to set the floor where a sale
  loses money including labor, and always price above it.

Pricing rules: match / undercut % / markup %.

**Sub-threshold disposition is a per-run choice, never a constant in the code.** The owner
picks one default for the run — flat at the floor, or a flat price set for that run — and
can name individual SKUs to override it. Output is suppressed until that choice is made: a
card under the threshold is not quietly listed and not quietly dropped.

**A row with a blank or $0.00 market price is `no_market_data`, and is not sub-threshold.**
A missing price is an unknown price, not a low one, so it gets no disposition at all — not
the flat price, not the floor, not the bulk lot. It is priced by hand in `decisions.json`
or explicitly left unlisted, and `emit` refuses to write while one is still unanswered.
Recorded because the tempting "fix" is to sweep these into the sub-threshold bucket, where
the whole point of the bands above is that they describe cards whose value is *known* to be
small. The failure that prevents: handing away a $40 chase card at the $0.40 floor because
its market cell happened to be empty.

The join preserves the sub-threshold price distribution in bands rather than lumping it,
because "everything under $0.40" hides the difference between a $0.38 rare and a $0.01
code card, and that difference is what decides later which of them are worth a bulk lot.
Bands are cut as fractions of the threshold, so they follow it if it moves.

TCGplayer's native Bulk Lots category (Level 4, Pricing tab) remains the exit for whatever
is not listed — selected against that distribution, not sorted into blindly at emit time.
No eBay needed.

## D10 — Inventory model

Sequential position assigned at capture. Location = Box N, Section N, Card N. Sold cards
leave permanent gaps — positions are never renumbered.

**SECTIONS ARE PER-BOX AND DECLARED AT CAPTURE TIME** (amended 2026-08-23, by the owner).
`CARDS_PER_SECTION = 25` was a bare module literal no env var, flag or parameter could reach,
and real boxes have dividers where the operator physically put them. A box now carries its own
list of divider indices — `[1, 31, 56]` means section 2 starts at card 31 — set by a **New
section** control on the capture screen at the moment the real divider goes in.

**AN EMPTY LIST MEANS UNDECLARED, AND AN UNDECLARED BOX IS ONE SECTION. THERE IS NO AUTOMATIC
DIVIDER** (amended 2026-08-29, by the owner: *"delete automatic sectioning"*). This paragraph
read "an empty list means undeclared, and the 25-rule renders it", defended as the thing that
kept every label written before boxes existed byte-identical. That was true and it was the
wrong trade. The 25-rule cut a divider into every undeclared box every twenty-five cards
whether or not one was in the plastic, and byte-identical labels are worth nothing when what
they are identical to is a boundary nobody put there.

**The measurement is the owner's own store.** Box 1 holds 133 cards and declares no layout, so
it rendered as six sections and a person sent to `Section 4 · Card 8` would have been counting
for a divider that does not exist. Box 2 declares `[1, 86, 171, 253, 394]` and is untouched by
this, as is every other declared box: the change reaches exactly the boxes that never claimed
to have dividers.

**What replaces the constant is `(1,)` — the one divider every box really has, at its front.**
`pipeline/join.py:Position.layout` states the fallback once and `section`, `section_start` and
`section_end` all read it, where the constant had three branches doing their own arithmetic.
So `card` is the index, `section` is 1, and `section_end` is None, which is D20's existing
answer for a final section rather than a new rule — the caller holding the box's capacity
fills it in. `Position` is still the only label formula in the repo, and the v1→v2 migration
still writes an empty layout for every box it finds; only what an empty layout RENDERS AS has
moved.

**The labels of every undeclared box moved once, deliberately, and that is the cost.** It is
the same risk `harness/tests/t7_store_and_seams.py` names for the migration — every position
label in a real inventory shifting at once, with the only symptom a person opening the wrong
slot weeks later — realised on purpose instead of by accident. It is affordable for the reason
this entry already gives twice: a label was never printed on anything, only ever read live off
a screen. T7 pins the new strings so that the next such shift is not accidental either.

**THE `New section` CONTROL THIS ENTRY HAS DESCRIBED SINCE 2026-08-23 EXISTS AS OF 2026-08-29,
AND IT IS `S` ON THE CAPTURE SCREEN.** The owner: *"make sectioning something I can create
from the capture screen itself, just like C is capture, I want S for Sectioning (remap S for
set hint to H)"*. Until then the sentence above was aspirational — the only way to declare a
divider was `PUT /boxes/<box>` with a whole layout, typed into a field on `#/inventory`, which
is a different operation wearing the same words: performed later, from another screen, and
needing the operator to remember which card they were on when the divider went in.

**The two halves of that instruction are one design.** Deleting the automatic divider is what
makes the key worth having — a screen that invents a boundary every 25 cards does not need a
control for putting one in — and the key is what makes deleting it safe, because the operator
who loses the invented dividers gains a way to record the real ones at the moment they exist.

- **`POST /boxes/<box>/sections` takes NO INDEX.** `store/master.py:open_section` reads
  `next_index` inside the store lock, so the divider lands in front of the card the next
  capture will actually take. A client computing it would read a high-water mark across a
  round trip and send it back — the lost update `next_index`'s own docstring exists to
  prevent, and at the feeder's measured 623 ms cadence not a theoretical one.
- **It is `next_index` and not count+1**, which matters exactly where D10 already matters: a
  box with permanent gaps in it. A count would put the divider in front of a card that will
  never be captured.
- **An undeclared box materialises `[1, at]`, not `[at]`.** `check_sections` requires a layout
  to start at index 1 and is right to — there is no card before the front of a box. Nothing is
  invented by that: section 1 already started at card 1, and this is the first time anything
  needed to write it down.
- **It logs `resectioned` through `set_sections`**, the event the dividers editor already
  writes, carrying both layouts. A new event name was considered and rejected on D26's
  evidence: this store has already been bitten by a state and a history event sharing a word.
- **Three refusals, each in its own code**: `section_empty` (pressed twice with nothing
  captured between — the divider you want is already there, and an empty box takes this too,
  since card 1 is where the first section starts), `section_ahead` (a divider already declared
  past the next card, which the dividers editor allows and this cannot append behind), and
  `box_closed` (a sealed box takes no more cards, so a section with none to come is a divider
  in front of nothing).
- **No confirm and no undo, and neither is an oversight.** Nothing is spent and nothing is
  destroyed; the remedy for a mis-press is the dividers editor, which is where a wrong layout
  is corrected anyway, and `resectioned` carries the layout it moved from. A dialog on the
  screen the owner shoots a box from at feeder pace is what `docs/DESIGN.md` refuses in as
  many words.

**The set hint is `H` now, and the swap cost nothing else.** `S` was on a field an operator
opens a few times a run and was wanted for an act performed at the box. The option alphabet
(`docs/DESIGN.md`) is every key this screen has not spent, so it lost `s` and gained `h` — and
because `h` sorts after `e`, the first thirteen option keys are `1234567890ade` before and
after, which is why `app/tests/capture-claims.spec.ts` pins them and stayed green.

**"Positions are never renumbered" governs the INDEX. The label is a view.** These were the
same sentence while sections were a global constant and they are not any more, so the entry
has to say which one it meant. The index is the identity: it is assigned once, it survives a
sale as a permanent gap, and nothing renumbers it — that part is unchanged and absolute.
Section and Card are a *rendering* of that index against the box's current divider layout, so
moving a divider relabels every card behind it without touching a single index.

**Boundaries are freely editable from any screen, and labels always recompute** (the owner's
ruling, chosen over freezing a section once a card sits in it). The argument for it: correcting
a wrong layout is the whole point, a label was never printed on anything, and the alternative
leaves the model permanently unable to describe a box you physically re-divided.

The cost is recorded here rather than designed away, because it is real: **a mis-tap relabels a
filled box and nothing flags it**, and the Fulfiller walks to the wrong slot with no error to
see. Mitigated by a `resectioned` history event carrying both layouts — not by restricting the
operation, which was the other option and which the owner declined. If that failure ever
actually happens, the fix to reach for first is a confirm on an edit that moves a divider with
cards behind it, not a return to freezing.

**Undo deletes the record; it does not tombstone it** (settled 2026-08-12, before step 7
built it). A tombstone would be a third thing the store has to explain — not captured, not
sold, still occupying a position — and every reader would have to learn it. A deleted
record is a card that was never captured, which is exactly what the operator means by undo.

This decides index reuse, which is otherwise the allocator's most surprising behaviour.
`next_index` is a high-water mark, `1 + max(index in this box)`, so deleting the newest
record hands its index straight back to the next capture. That is the correct outcome and
not an accident of the implementation: the position was assigned to a photo that no longer
exists, and burning it would put a permanent hole in a box over a mis-tapped button.

**THE BOX-NUMBER ALLOCATOR IS A DIFFERENT RULE, AND IT IS NOT THIS ONE** (D20, amended
2026-08-25). `store/master.py:next_box_number` hands out the lowest free integer rather than a
high-water mark, because a box number names an object on a shelf and nothing about it is a
position a card was assigned to. Cross-referenced here so the paragraph above is not read as a
rule about every allocator in the store: this one governs the INDEX inside a box, and that is
the only thing it governs.

**Undo is the newest capture in a box, never an arbitrary one.** Deleting a record from the
middle leaves a gap the high-water mark cannot reuse — indistinguishable, later, from the
permanent gap a sale leaves, and the rule above says those mean different things. Restrict
the operation rather than teach the allocator to fill holes: D10's first paragraph is what
makes a printed position label worth trusting, and nothing that renumbers may exist.

**THE CAPTURE SCREEN SHOWS TEN OF THEM AS OF 2026-08-29, AND THE RULE ABOVE IS WHY A ROW IS
NOT A DELETE.** The owner: *"make undo capture actually U undo's the most recent one, but
it's actually a growing queue, let's say the 10 most recent captures that I can just click
undo capture on from the sidebar"*. The control was one card and one button; it is the
session's ten most recent captures into the current box, newest first, every row its own
control.

**Pressing row N undoes N cards — that row and everything captured after it.** It is the
same route N times, newest first, which is the only thing the sentence above permits: card
N-1 is not the newest until card N is gone. A per-row delete of a middle card would be D10
ruling 1's mid-box remove, which slides every higher card down one index — and putting that
on this list would renumber the very rows it was pressed from, which is the defect D37
refuses for the review screen's worklist in as many words. That operation exists and stays
on `#/inventory`.

**The count is drawn on the row, and that is the whole of the guard.** `docs/DESIGN.md` makes
capture-undo the one place a destructive act gets no dialog, on the argument that the deleted
photo is of a card still within reach of the hand that fed it — an argument that is about ONE
card. A press that deletes five needs the five to be visible before it, not a confirmation
after it, so the row carries the number of cards it removes. It is also the row's ordinal,
which is what lets one chip say both. The top row carries `U` instead, because that is the
key that fires it.

**A walk that is refused partway stops there and says how far it got.** The next delete is
only legal because the one before it succeeded, so carrying on would aim at a card that is no
longer the newest. The count is the only thing left that says where the operator is: the
cards that went and the cards that did not have both left the list either way.

**The stack is this session's captures, and where the server is ahead it collapses to one
row.** A capture that committed and lost its response, or a capture the other device made
into the same box (D13 permits both), leaves the store holding cards this session never took
— no label, no photograph, no count for them. Offering to undo *back to* a row underneath
them would be offering to delete somebody else's captures sight unseen, from a list that
cannot draw them. So the depth is exactly one until the two agree again, which one ordinary
undo restores.

A sale is the opposite case and is unchanged. `sold` is a state, the record stays, and the
gap is permanent.

**THREE OWNER RULINGS, 2026-08-23 (evening), each narrowing or overruling a line above:**

1. **Mid-box delete WITH contiguous shift exists now, bounded.** "Nothing that renumbers may
   exist" is overruled for exactly one case: deleting a junk capture mid-box when **every
   higher-index card in that box is still `captured` or `identified`, with no listing hold**
   — the physical truth of pulling a card out of a contiguous stack, where the cards behind
   it really do slide forward. The boundary is what keeps the old rule's reason alive: a
   sold or retired gap above the deleted index refuses (`renumber_blocked`), because
   shifting across it would close a gap that means something, and a listed card's row is
   already in a file that names its position. Photos and sidecars are renamed inside the
   same locked operation; a `renumbered` history event maps every old index to its new one,
   so the log stays true across the shift.
2. **Capture-undo narrows to `captured` alone.** "Undo at `identified` is ALLOWED — only the
   identification fee is lost" is reversed: once a card has been identified it has made it
   into inventory proper, and the capture screen's undo may not reach it. The remedies for
   an identified card are the ones built for it — re-shoot, retire, or the mid-box delete
   above where its bounds allow.
3. **A whole box may be deleted** — records, photos, sidecars, queue entries, cache — gated
   as the genuinely destructive action it is (docs/DESIGN.md's clause), and refused while
   the box holds any sold, retired, or listing-held card: those records are history and
   commitments, not clutter.

## D11 — Listing path is a catalog join, never a from-scratch CSV

TCGplayer flow: Pricing tab → Export Filtered CSV (All Printings, so one file covers every
variant) → pipeline fills fields → Import to Staged → review → Move to Live. Rows match by
the `TCGplayer Id` SKU, which is never modified.

## D12 — Scope

Modern era only (SWSH/SV), English, all Near Mint (hardcoded). Vintage/WOTC condition
strings (1st Edition, Shadowless, Unlimited) are a spec change, not a parameter.

**Those two sentences went missing between 2026-08-13 and 2026-08-23** — dropped by the
motion-trigger commit, not by any decision — leaving an entry titled "Scope" that stated no
scope, two paragraphs referring to "the two blocks named above" and "the parenthetical" with
nothing above them to name, and the Vintage/WOTC rule spliced onto the end of an unrelated
paragraph. D15 and D26 both cite this entry as though it said what it says again now.
Restored verbatim from `e955afd` rather than rewritten, because the surrounding argument was
built against that exact wording.

**Gate B ran entirely outside the two blocks named above, and nothing noticed.** The 53
cards of 2026-08-22 were `ME01: Mega Evolution`, a block later than SV, and they went
through capture, identification, join, emit, import to Staged and reconcile without a
scope question arising — because nothing in the tree enforces the parenthetical. The only
code that cites this entry for scope is `pipeline/variant.py`'s `CONDITION_BY_FINISH`,
which hardcodes the Near Mint strings; there is no set or era filter anywhere. Read
`(SWSH/SV)` as the blocks that existed the day this was written, not as an allowlist.

**Whether "modern era" is open at the top end is unsettled, and it is the owner's call.**
Recorded rather than answered, because a passing gate is evidence that nothing broke, not
a decision that every future block is in scope. It matters in one place today: D15's
mirror-scope paragraph reads this entry as the enumeration `SWSH/SV` when it sizes a
narrowed image mirror at ~4.8 GB, so narrowing the mirror on that basis would exclude the
only era this project has ever run against. Settle both lines together or neither.

## D13 — Stack

Vite + React web app in a desktop browser. Python capture server + batch script. Inventory
state is server-side JSON on the Mac, read and written through the capture server, so the
owner's and Fulfiller's devices share one truth. Photos on Mac disk, box-keyed by capture
position — see D6. Build environment is Claude Code on the Mac; code never lives in chat.

**THE MAC STAYS THE ONE TRUTH, AND THE OWNER IS KEEPING A PORT OPEN** (recorded 2026-08-23 at
their instruction, when asked whether to host the capture server somewhere persistent). The
answer for now is no: the photographs and `inventory.json` live on this machine, and hosting
means moving 682 photographs and the store off it — which is not a deployment detail but a
different product, with backups, secrets and uptime attached. Remote access, when it is
wanted, is a tunnel to this machine and needs no code change.

Recorded rather than left implicit because the owner said it may eventually become a product
for other people. Nothing in the design is being bent toward that today, and this paragraph
is the marker so a later session knows the single-operator assumption is a CHOICE with a
known exit, not an assumption nobody examined. The pieces that would have to move are named
where they are: this entry (one truth on one disk), D5 (two personas on two devices), and
D24's opsec rules, which assume a machine one person controls.

**The rig's camera path, recorded 2026-08-13 because nothing in this repo ever said it.**
A Sony RX100 VII or A7C, over HDMI into an Elgato Cam Link 4K.

The consequence is why this belongs in a decision rather than in a spec's prose: **the Cam
Link presents the camera to the browser as a plain UVC webcam.** It is not distinguishable
by kind from a laptop's built-in camera — only by its device label and id. That is exactly
why `facingMode: "environment"` was v1 bug 3, and it is why the device picker is a
requirement rather than a nicety: there is no camera-facing hint to select on, and the
wrong guess photographs a whole box through the wrong lens.

**The Cam Link hands the browser a landscape frame however the camera is mounted.**
The second consequence of the same path, measured at Gate B on 2026-08-22 and the largest
single defect that run found. The rig mounts the camera on its side so a portrait card
fills the portrait field — the right call by the frame-tight rule below — and the stored
photo came out sideways anyway. Haiku misread 45 of 53 of them into the review queue with
names and numbers both garbled; `docs/GATES.md`'s Gate B section carries the rest of the
counts. It belongs in this entry for the reason the paragraph above gives: nothing about
the capture device reaches the browser except its label, its id, and the frame it sends,
so mount orientation is not a thing the app can detect.

**THE ROTATION IS TWO CHOICES, NOT FOUR (owner, 2026-08-24).** It was `0 | 90 | 180 | 270`,
and offering all four was offering two answers that are never right. The geometry above does
not vary: the camera is mounted on its side and the Cam Link sends landscape regardless, so
the stored photograph is upright only after a QUARTER turn — 90 or 270 depending which way
the body faces. 0 leaves every card sideways; 180 leaves it sideways and upside down.

**And 0 was the fallback, which is the half that actually bit.** The reader answered 0 for a
missing, malformed or out-of-range value, so every new browser and every cleared device
started in the state that produced this entry's own disaster — 45 of 53 misread, names and
numbers garbled. It answers 90 now, and a stored 0 or 180 from before today migrates to it
rather than being obeyed. A guess that is right half the time beats one that is wrong always,
and the other half is one keypress away on a control whose value is printed in the sidebar.

The narrowed union did the rest of the work by itself: TypeScript found the landscape stage,
the landscape frame and the landscape undo thumbnail as unreachable branches, and all three
are deleted rather than left permanently true.

The fix is a rotation remembered per device and applied at capture time rather than in the
identify path: `app/src/useCamera.ts` holds the setting and `app/src/encode-worker.ts`
turns the frame before it is encoded. Rotating there corrects the model, `geometry/`'s crop
bands and the review queue's judging photo at once, where a fix in `identify/` would have
left a sideways photo on every screen that shows one. The live preview is deliberately left
as the camera sends it — the stored photo is the record that has to be right, and the
last-capture panel shows it, so one capture confirms the setting.

**The camera is not driven directly, and that was asked rather than assumed.** Tethered
capture over USB — Sony's Camera Remote SDK, or `gphoto2` in PC Remote mode — buys full
sensor resolution at a cost of roughly one to three seconds per frame, a platform-specific
native dependency, and a refocus per shot. Sony's Imaging Edge Desktop is ruled out before
any of that by `CLAUDE.md`: no manual third-party UI step inside the autonomous pipeline.

**Frame the card tight in the 4K field; that matters more than the sensor.** The reasoning
is in `docs/specs/capture-app.md` and it corrects a simpler argument that was nearly
recorded here: resolution is *not* irrelevant just because `identify/images.py` downscales
the whole card to 1568px. The crop-retry path in `geometry/crop.py` upscales the collector
number to at least 600px, and it can only enlarge pixels that were really captured — which
is the failure mode T1's recorded misses actually have. Tight framing at 4K recovers most of
what tethering would have bought, for free, and glare on the number corner is unrecoverable
at any resolution.

## D14 — Two tracks, one rig

Shared: physical rig, capture server, capture app shell (mode toggle), photo storage,
operating rules. Separate: schemas, identification, sales channel, fulfillment.

Sequencing: codes rides the shared foundation (harness → rig → server → app shell), serves
as the feeder's shakedown cruise, and may sell manually on eBay early. Its delivery
automation is gated on singles Gate B.

## D15 — Catalog data is vendored, not fetched

The pokemontcg.io dataset is a committed snapshot of the maintainer's own
`PokemonTCG/pokemon-tcg-data` repo. Nothing calls `api.pokemontcg.io` at runtime. Zero rate
limits, zero latency, zero dependency on someone else's uptime. Build-order step 9 — after
Gate B, because no production code reads this data today.

**Why a snapshot is safe here, when a pricing snapshot would not be.** D8 routes every price
through the TCGplayer export, and the raw repo carries no price block at all. What is left —
set ids, collector numbers, printedTotal, names, rarity — is fixed the day a card is printed.
Staleness therefore has exactly one form: a *new* set is missing. That fails loudly as an
unknown set id, never quietly as a wrong price. Refresh is a `make` target run monthly that
records the upstream commit SHA, so a T1 score is attributable to a catalog revision.

**SQLite, not Postgres.** ~20k rows, read-only after load, one machine. Every Postgres
advantage is absent: no concurrent writers (D13's two devices share one truth *through* the
capture server, so there is still one writer), no network access, no indexing at a scale
SQLite strains at. Against that it adds a service that must be running for `make harness` to
pass — the exact class of dependency this entry deletes. `sqlite3` is stdlib, so
`requirements.txt` keeps its property of naming what it deliberately omits.

**Card records carry no nested `set` object.** Unlike the API response, the set is implied by
the *filename*, and `printedTotal` lives only in `sets/en.json`. The join key is
`zfill(3)(number) + "/" + printedTotal`, so joining card→set by filename is the one detail a
loader must get right. There is no `tcgplayer` block either; see D8 for why that is fine.

**The image mirror's path is a knob, because of its size.** A full mirror is ~16.7 GB
(measured: 834 KB average across 197 hires PNGs) against the 160 MB of eval images held
today, which is large enough that which disk it lands on is a choice worth having. Path is
overridable through `PKMNSCAN_IMAGE_MIRROR`; `harness/images/` moves with it rather than
being left behind as a second copy. Mirroring at all is the point —
`images.pokemontcg.io` is the piece most likely to throttle or disappear, and it is the one
piece the JSON repo does not cover.

**Mirror scope is a knob with a default, not a constant.** Full catalog is the default. D12
scopes the product to SWSH/SV, which would cut the mirror to under a third (~4.8 GB) — recorded
so that narrowing it later is a decision rather than an oversight.

**Upstream publishes no license file.** Private, single-operator use only. Recorded so no
later session assumes redistribution rights that were never granted.

**A defect this erases.** The current fetch requests `pageSize=250` with no pagination loop,
but sv1 has 258 cards, sv4 266, sv8 252 — and the banked `sv1.json` holds exactly 250 records,
so sv1 is truncated today. Low severity: the manifest pins the selection, so committed scores
stay reproducible and the effect is sampling bias rather than a wrong number. A local file has
no page size.

## D16 — The docs are checked mechanically; the prose is checked by asking

This repo's markdown carries its architecture and the reasoning behind it, and until
`scripts/docs-audit.py` existed nothing verified a single line of it. Every path, `make`
target, subcommand, test id, threshold, decision number and env var in it was true only
for as long as someone remembered. That is the same argument `docs/GATES.md` makes for the
harness — "without it, 'looks done' is the only available signal" — applied to the files
that tell the next session what done means.

**Three layers, split by how knowable each finding is.**

1. **Mechanical** — `scripts/docs-audit.py`, stdlib-only, run by the pre-commit hook
   and by `make docs-audit`. Every check is deterministic, and **blocking is the
   default**: a finding is mechanical when a reference is provably wrong — a path that
   does not resolve, a `make` target that does not exist, a threshold that disagrees
   with `docs/GATES.md` — and it exits 1, because there is no judgment to defer.

   **A finding prints on exit 2 instead of blocking when judging it needs context the
   script cannot have.** A decision id cited in a `.py` comment could plausibly become
   a variable name one day; code that changed beside an unchanged doc is a question,
   not a defect. A false positive that blocks is worse than one that prints.

   **Neither the roster nor its count is restated here.** `make docs-audit` names
   every check it runs, each row marked blocking or advisory, and that output is the
   register. This paragraph used to publish the count, and keeping one restated number
   honest cost more machinery than any other check in the file — all of it guarding a
   fact nothing downstream consumed. Deleting the claim deleted the need. D18 records
   the general rule.

   **A check is named, never numbered** — the same rule D17 sets for the repo-map
   check, enforced for all of them. Positions moved once already; the report's labels
   are the names.

2. **Coupling** — the same script, `--staged`: code changed under `pipeline/`, and
   `docs/specs/batch-script.md` did not. **Exit 2 prints and allows.** Fires only above 20
   staged lines, so a typo fix stays quiet.
3. **Semantic** — `/docs-audit`, a model reading prose against the diff. Never a gate: it
   costs money, it is not reproducible, and this project does not let a non-deterministic
   thing decide whether work is done.

**Why the coupling question does not block.** Stopping a commit over a question teaches you
to reach for `git commit --no-verify`, and `--no-verify` also switches off the three opsec
rules in the same hook. Trading a code-card bearer-instrument guard for a prose reminder is
a bad trade, so layer 2 asks and gets out of the way.

Worth being exact about what `--no-verify` costs, because it is more than it was: those
three rules run **only** at commit time now. Their `PreToolUse` twin, `scripts/guard-opsec.sh`,
has been disabled in `.claude/settings.json` since 2026-08-03 — it blocked any write
containing a code-shaped literal, including placeholders in prose about the format, and cost
two blocked writes in one session. Fixtures stay covered while it is off by the
`permissions.deny` rules; the code-card literal does not. **Revisited and re-enabled
2026-08-23**, when D24's build made the condition true: the narrowed pattern blocks by shape
(stands alone, mixes letters and digits, no all-repeated group), passes byte-exact
reconstructions of both historical false positives, and fails open on its own bugs — so
`--no-verify` no longer switches off the only opsec layer, and the commit-time rules are
again the backstop rather than the whole guard.

**A GIT WORKTREE INSIDE THE TREE IS ANOTHER BRANCH, AND THE AUDIT DOES NOT WALK ONE** (added
2026-08-29). Concurrent sessions check worktrees out under `.claude/worktrees/<name>/`, which is a
full source tree of a DIFFERENT branch sitting inside this one. The walk found them, so the audit
was checking one branch's prose against another branch's code and reporting the disagreement as a
defect in yours. Observed: a worktree's `CLAUDE.md` documented a `worktree-setup` target, real on
its own branch, and the make-targets check failed a commit on `main`, which has no such target.
**Two branches are allowed to disagree; that is what a branch is.**

**It is pruned twice, by name and by asking git, and the two cover different things.** `worktrees`
in `SKIP_DIRS` catches the convention and keeps working when git does not answer. `nested_worktrees()`
reads `git worktree list --porcelain` and prunes any checkout under the repo root whatever it is
called — verified against a worktree named `zz-scratch-wt`, which no name rule could guess: zero
files walked, audit clean. It fails open exactly as `ignored_paths` does, because a discovery
helper that can abort the audit is worse than one that occasionally walks too much.

**This is not the gitignore filter and neither subsumes the other.** That filter stops a finding
being *reported* for local state; this stops a foreign tree being *enumerated*. The finding here
was against the make-targets check, which never consults the filter. `--self-test` covers the staged path;
the on-disk path needs a real repository with a real worktree in it and was verified by hand, which
that case says in as many words rather than implying coverage it does not have.

**Nothing on the audit path can write.** The script opens, compares, prints, and sets an
exit code; it parses with `ast` rather than importing, so it does not even run project code.
Its only writes are inside `--self-test`, into a temporary directory it creates and destroys.

**`--self-test` therefore runs in `make check` and never in the git hook** (settled 2026-08-24).
It is the one mode of this script that writes, and D18 forbids a writing thing on the path that
decides whether a commit proceeds; `make check` is invoked by a person on demand, so it is not
that path. Until then nothing ran it at all, and it had gone red without anyone noticing — a
stale fixture in `tested_by reach` had stopped being false while every commit stayed green.
`docs/DEBTS.md` carries the account. The residual gap is named there too: `make check` is not
automatic either, so a red self-test still surfaces only when somebody asks.
Adding a `--fix` flag is a change to this entry, not a configuration knob. The reason is the
failure this entry exists to prevent:

> **A blocked commit is reported, not resolved.** Never edit a doc for the sole purpose of
> getting a commit through.

An agent that can edit the docs to satisfy its own gate will do exactly that, and each edit
will look reasonable. The docs stop being a record of what was decided and become a record
of what was convenient — and unlike a failing test, nothing downstream ever notices. That is
also why `/docs-audit` shows every proposed change in one table before touching anything,
and never stages or commits: the owner's own `git diff` is the last link in the chain.

**The docs audit is not a harness test, and must not become one.** Putting it in
`harness/run.py:TESTS` was considered and rejected. The harness runs behind the `Stop` hook
(`scripts/stop-gate.sh`), so a docs test there would fire at the end of every turn,
including turns that touched no markdown at all. The trigger is commit-time and on-demand
by choice.

This paragraph used to make that point by naming the number the docs test would have taken,
which stopped working the moment a real test needed a number. T7 is now the store, server
and command-seam test (`docs/GATES.md`), and it is unrelated to this entry. The rule here
was never about a number.

**The allowlist is self-cleaning.** `scripts/docs-audit-allow.txt` records things the docs
name before they exist — `PKMNSCAN_IMAGE_MIRROR` is documented by build-order step 9 today.
The audit **fails when an entry comes true**, which forces the line out at that moment.
Same instinct as `stop-gate.sh` arming on the absence of `NOT_IMPLEMENTED` markers rather
than on a toggle: a list that only grows becomes a list nobody has read since.

**A threshold is published, not restated.** Each test's `PASS_CRITERIA` must appear word for
word as the `- **Pass**:` line of its `### Tn` section, and layer 1 blocks a commit where
they disagree. **Reconciliation runs from the test to the gate.** The test is where a
threshold is argued about and changed; `docs/GATES.md` is where it is announced. Rewriting a
test so a doc-checker goes quiet inverts that and makes the test worse to please a tool.

Five of six had drifted before this was enforced, which is the case that decided the
direction: those tests were changed deliberately and approved, and the change simply never
reached the markdown. An approved change that does not reach the doc is the failure this
whole entry exists to stop, so it blocks rather than asking.

**One known gap, recorded so a green report is not misread.** Layer 1 proves references
resolve and thresholds agree — not that a paragraph is true. Treat a clean mechanical run
exactly as `docs/GATES.md` treats a green T1 and T6: it means the checkable part checks out.

## D17 — The repo describes itself in `docs/map.py`, and the map is audited

Two questions kept costing a full search to answer: *what is built and what is TBD*, and
*which settled decisions govern the file I am about to edit*. Both were already answered in
prose — `docs/GATES.md` has the build order, this file has the rulings — but prose has to be
read whole before it can be trusted, and the first question alone cost a subagent sweep and
roughly 285k tokens in one session.

`docs/map.py` answers both in one Read: build-order status, gate status, and per-component
`does` / `status` / `governed_by` / `tested_by`. Pure literals, no imports, read with
`ast.literal_eval` by everything that consumes it.

**Data, not another markdown section, because it has three consumers.** A human or agent
reading it once; `scripts/docs-audit.py`'s repo-map check, which verifies every claim in it
— named rather than numbered, because a positional index re-drifts every time a check is
added, and this one already had; and
`scripts/decision-context.py`, the `PreToolUse` hook that names the governing decisions
before a file is edited. Prose serves the first well and the other two not at all.

**It is audited exactly as hard as it is trusted.** An index that drifts is worse than no
index, because it is believed. The repo-map check fails when a `built` path is missing,
when a `planned` path has quietly arrived, when `governed_by` cites a decision with no
heading, when gate status disagrees with `docs/GATES.md`, and — the rule that does the real
work — when a source file exists that no entry mentions. Adding a module without touching
the map fails the commit. That orphan rule is the difference between a map and a stale map.

**`governed_by` is a superset of the citations in the file's own comments,** enforced in the
same check. The code already said `D9` in `pipeline/pricing.py`; the map may add D8, which
the file never names but which decides where its prices come from. It may never know *less*
than the code does.

**The hook is advisory and silent by default.** `scripts/decision-context.py` exits 0
unconditionally — bad input, missing map, its own bugs — and prints nothing for files no
entry covers. It summarises each decision by lifting the entry's own bolded lead-in
sentences out of this file, so a summary cannot drift from the decision it summarises;
nothing is restated by hand. It emits `additionalContext`, never `permissionDecision`:
`"allow"` would auto-approve every Write and Edit in the project.

Precedent for the caution: the opsec `PreToolUse` guard over-triggered and was disabled
within a day. A hook that speaks on every edit gets muted, and a muted hook protects
nothing. The first draft of this one merged each package's decisions into every module and
told you `pipeline/pricing.py` was governed by D2, Haiku vision — true of `pipeline/`,
useless there. Module entries now stand alone.

**Known limit.** The hook depends on a payload shape that has moved between Claude Code
releases. If a release ignores `additionalContext` the JSON is printed instead, so the
failure mode is a lost nudge and never a blocked edit — and `CLAUDE.md` points at
`docs/map.py` directly, which needs no hook at all.

## D18 — A generator may write. Nothing that writes may gate a commit.

D16 forbids the audit writing, and gives the reason: "An agent that can edit the docs
to satisfy its own gate will do exactly that, and each edit will look reasonable."
That argument is about a *path*, not about a script, and D16 states it as a property
of the script — which leaves a loophole wide enough to drive a build target through. A
generator that rewrites a doc from a code constant is not the audit, breaks none of
D16's letter, and recreates its failure exactly if it runs inside the gate: `make
check` regenerates, the audit passes, nothing fails, and the doc now says whatever the
code said.

**Nothing that writes may run on the path that decides whether a commit proceeds.**
D16's "Nothing on the audit path can write" is one instance of this rule, not the
whole of it. Generation is permitted; generation inside the gate is not.

**A seam is permitted only where a file's job is reference, and the permitted
locations are listed here by name.** The list is currently empty. Adding to it is a
change to this entry, argued on its own terms — not a judgement call made while
implementing something else. This is the rule that keeps generation from spreading
into the files agents read as argument, and it is stated early because it is the one
most likely to be eroded quietly.

**The list above is empty, and that is the finished state, not an unfinished one.**
This entry was written while considering a generator for one specific number, and the
act of writing the seam rule is what showed the better answer was to stop publishing
the number at all. Nothing in this repo generates anything today. Read this entry as a
guardrail placed across a loophole D16 left open — not as an invitation to use a
mechanism sitting ready. A later session finding an empty list has found the intended
condition. Adding the first entry means arguing that a fact must be published in prose
*and* cannot be hand-maintained, and that argument has not yet been made once.

**The test for "carries an argument": could a later session reasonably disagree with
this line?** A count, a status word, a list of registered names — verifiable, nothing
to disagree with. A threshold, a rationale, a trade-off — arguable, and therefore
never generated. A second test, applied together with the first: if the span were
replaced by its bare value, would the surrounding paragraph still mean the same thing?
If not, the fact is load-bearing inside an argument, and the seam would cut it out of
its reasoning. Prose that explains *why* is never a generation target, no matter how
mechanically derivable the number inside it is.

**The split is write-time versus check-time.** The docs-gen make target writes and is
invoked by the owner. The pre-commit hook and `make check` verify freshness and fail —
they never regenerate. Verification is not free: it means computing what the span
should say and comparing, which is the generator's logic running on the audit path
minus the write. Budget it as its own cost. Generated output is committed, so the
owner's own `git diff` remains the last link in the chain, exactly as D16 requires for
the semantic pass.

**The generator is stdlib and reads with `ast`, for as long as freshness is checked in
the git hook.** The hook runs `python3` with nothing installed, so a generator whose
freshness check runs there cannot require a package. That rules out `cog` — otherwise
the right tool, actively maintained, with a check mode built for exactly this —
because it is a PyPI dependency and it executes the embedded Python, which would make
the hook depend on the import graph staying free of third-party modules at module
scope. Nothing enforces that today; `ast` does not care. **This constraint is
contingent, not permanent: if freshness verification moves to CI, the stdlib rule
stops binding on the generator and `cog` becomes viable.** Recorded so a later session
reads this as a consequence of there being no CI today, not a standing judgement about
the tool.

**What this supersedes.** D16's paragraph beginning "Nothing on the audit path can
write" stands unchanged as a statement about the audit. This entry generalises its
scope: read that paragraph as the specific case and this rule as the general one. A
fix flag on the audit remains forbidden by D16, and this entry does not soften it — a
generator is a separate program with no findings, not the audit gaining a write mode.

**The failure this prevents:** a generator on the commit path turns every wrong
constant into a confidently published sentence, with the audit green and no diff a
reviewer would question. Checking lets two things disagree in public. Generating makes
one thing true everywhere, including when it is wrong.

## D19 — Motion capture: live fire behind the seam, a trace for tuning, video for neither

**The auto-capture trigger fires live, per card, through the same `POST /capture` a key
press uses. Recording the run to video and extracting frames afterwards was worked through
and rejected as a capture path** — not on image quality, which is a configuration choice,
but because segmenting a tape into per-card frames IS the motion state machine run offline:
it avoids none of the tuning, while giving up the position↔photo binding `allocate_capture`
makes inside the store lock at the instant of capture, D10's undo (whose whole safety
argument is that the deleted photo is of a card still in your hand), and §5.5's
halt-at-the-moment-of-failure. What video genuinely offers — re-runnability while tuning —
the 64x36 luma trace offers at a thousandth of the bytes, so the tape is a debugging
instrument for the rig session at most, never a photo source, and deleted once parameters
sit on a plateau.

**THE CARD-PRESENCE GATE READS A QUANTILE, NOT A MEAN, AND A SECOND RIG IS WHAT PROVED IT
(2026-08-29).** `cardLumaFloor` was the mean ROI luma, and a mean is a statement about the whole
watch region rather than about whether a card is in it. Those coincide only while the card
FILLS the region — which is what the rig this was tuned against happened to do. On the owner's
new rig the card occupies part of the region against a dark surround, so the mean is dominated
by background:

    empty stand    mean 27-30    bright quantile 62-69
    settled card   mean 62-86    bright quantile 125-236

**The floor of 90 sat above both means**, so the gate could not fire at any brightness and no
relighting would have fixed it — the failure is geometric, not photographic. One session
settled twenty cards correctly and refused every one; the next settled fifteen and fired twice,
both on a static frame before the feeder started. **Motion and settle detection were never at
fault**, which the traces show plainly: every card was found at the feeder's cadence.

**The constant does not move and neither does any other.** 69 against 125 leaves 90 where it
was, and a card that fills the region has a quantile at least as high as its mean, so Gate B's
~172 still passes. Re-scored offline through the fix — the traces exist for exactly that — the
two sessions go 2 fires to 15 of 15, and 0 to 7 on the under-lit one, with the empty stand
still refused. `CARD_QUANTILE` is 0.9 rather than a maximum because a specular highlight, a
lamp in shot or one hot pixel all carry a maximum and none is a card.

**This is the paragraph below working as intended, and also its limit.** Every parameter here is
derived from a measurement — but the measurements came from ONE rig, and what this found is
that a constant can be right while the STATISTIC it is compared against is wrong. A second rig
is the only thing that could have shown it, and the trace is what let it be diagnosed and fixed
without a rig trip.

**Every parameter is derived from a measurement, and the measurements are named where the
constants live.** Gate B's recovered cadence (median gap 609.5 ms, robust σ 34 ms, floor
458 ms, the feeder's own ~660 ms), the <250 ms capture round trip, and a worst-case
frame-difference SNR of ~20x on the real frames. `docs/specs/motion-trigger.md` carries the
full derivation; `docs/GATES.md`'s Gate C section carries the numbers. The thresholds are
rig-tunable constants and the rig has not yet tuned them — BUILT is not TUNED, and the
50-card run is where that changes.

**Arming is an act, not a setting.** The mode is session-only and never persisted,
deliberately unlike the remembered camera and the rotation chip: a remembered camera cannot
take a photo on its own, and a remembered motion mode is an automatic shutter armed by a
page load. Every session starts manual.

**A fire the screen declines is counted, on screen, and the halt banner does the
arithmetic.** Under a key, a swallowed fire is fine — the finger is attached to someone
watching. Under a feeder that keeps delivering, each one is a card that may have passed the
lens unrecorded, which is §5.5's exact failure. So motion mode counts every declined fire
by reason, and a halt with the feeder running renders the count as the sentence it means:
that many cards to set aside and re-feed.

**A jam surfaces and does not fire.** Continuous motion past the stall window reports
`stalled` on the HUD rather than capturing a moving card. The other side was argued —
"never silently drop a card" favours firing — and loses for v1 because a hand in frame
would capture-spam, and a loud stall is not silent. If the rig session shows real cards
dying to stalls, this is the paragraph to reopen.

**Undo stays manual forever.** No automatic anything reaches a control that hard-deletes a
record, a sidecar and a photo. The motion trigger exists behind the capture seam only.

**The ordering is the owner's, 2026-08-22: motion capture end to end before any other
work.** Step 9 (vendor the catalog) was `next` for a few hours and is re-sequenced behind
Gate C — it touches no app code, so nothing collides; one `next` is the rule and the owner
chose which. This also dissolves the map's old circularity of step 10 being blocked by the
gate that IS step 10.

## D20 — A box is an object, and its capacity is retroactive

Before this, **there was no box object anywhere in the repo** — `docs/specs/capture-server.md`
§5.4: *"there is no box object anywhere in `store/`, only a flat dict keyed by box and index."*
A box existed only because a card named one. The consequences were all small and all daily: a
box could not be created empty, could not be named, could not be listed on any screen but
Capture, and a mistyped number was caught only by the `new_box` flag *after* a photo had been
written — which `server/capture_server.py` notes catches the first typo only.

`store/master.py:Box` carries `box`, `name`, `sections` (D10), `state`, `capacity`,
`created_at`, `closed_at`. A box is `open` or `closed`.

**Capacity is retroactive, and that is the whole of the lifecycle.** It is not asked for when
a box is created, because nobody knows it then. While a box is open it has none, and the
honest denominator is the fill so far — a screen saying "#40 of 53" has to also say *so far*,
because tomorrow it is 54. **Sealing the box freezes `capacity` at the final high-water mark**,
and only then does "#40 of 250 · 16% in" become a sentence that is still true next week.

That sentence is the reason the object exists. The owner's ask: *"if it just says oh the card
is at position 40, i'd rather it said it's at 40/250, so roughly a fifth of the way in you'll
see it."* A bare index tells you nothing about where to put your thumb; a fraction does, and a
fraction needs a denominator that does not move.

**A sealed box takes no more cards.** `allocate_capture` refuses with `BoxClosed` before it
computes an index, so a refusal burns nothing. Admitting one more card would make every
fraction already drawn from that box wrong by one.

**Sold cards do not shrink a box.** D10 makes their gaps permanent and `next_index` is a
high-water mark, so a sealed box's capacity never falls as its contents sell. Re-opening a box
sets `capacity` back to unknown rather than leaving a stale number standing.

**THE SAME ARGUMENT HAS A SECOND INSTANCE ONE SCALE DOWN, and it arrived on 2026-08-23 with
the section-scale position bar.** A section has a denominator problem of exactly this shape:
`section_end` is a DECLARED bound taken from the box's dividers, not a count of the cards
actually behind it. Box 1's section 3 runs 51..75 and holds three cards, so `card 3 of 25` and
`card 3 of 3` are both true and mean opposite things — which is this entry's original complaint
about `#40 of 53` versus `#40 of 250`, restated per section.

The rule, and it turns on which bound is final rather than on the box's lid alone:

- **Settled** — a divider with cards behind it, so the width is a fact. Render the declared
  width and say **`slots`**: `Section 1 · card 1 of 25 slots`.
- **Growing** — the last section of an open box, the one the next capture lands in, where the
  end is not a divider but the edge of what exists. Render the fill and say **`so far`**, the
  same two words this entry already puts on an open box's denominator, for the same reason.

**The caption must name which it is.** A denominator that silently switches meaning between a
full section and a half-empty one is precisely the failure this entry exists to prevent, and
at section scale it is easier to miss because the number is smaller and the operator is
already standing at the right box.

**A BOX HAS A NAME, THE NAME IS HOW IT IS ADDRESSED, AND NAMES ARE THEREFORE UNIQUE** (built
2026-08-25). This entry authored `name` as an optional label and nothing checked it, which was
right while it was decoration: the number was the identifier, and a second box called
`commons` cost nothing worse than a confusing row on a screen. The capture screen now finds a
box BY name — one free-text field searching number and name together — so a duplicate name is
an ambiguous *physical address*. That moves the ambiguity off the key the operator has stopped
typing and onto the label they navigate by, which is worse than where it started.
`store/master.py:_check_name_free` refuses one as `BoxNameTaken`, which
`server/capture_server.py` answers as 409 `name_taken`.

**FOLDED AND STRIPPED TO COMPARE, STORED VERBATIM.** `Commons`, `commons` and `commons ` are
one box to a person standing at a shelf, so they collide; what is written down is what was
typed. It is the same split `pipeline/join.py:number_index_key` draws between a matching form
and a stored one, for the same reason — a normalised value written back is a value the
operator cannot correct.

**UNIQUE, NOT REQUIRED, and that boundary was chosen rather than fallen into.** Requiring a
name would invalidate every box registered before today and would break `BoxOps`' own
"Name (optional)" create form. Uniqueness is the property that matters once a name is an
address; existence is not.

**A RENAME APPENDS `box_renamed`, CARRYING BOTH NAMES.** `server/capture_server.py` recorded
the absence of this event as a known gap and gave the right reason for leaving it — *"a name
is a label, not a claim the pipeline spends money against"* — and that sentence stopped being
true the moment the name became the address. A rename relabels every card in the box on every
screen that draws one, so an unlogged rename leaves no record of what the box used to be
called. **This is D10's divider argument at box scale, and it resolves the same way**: D10
chose a `resectioned` event carrying both layouts over restricting the operation, and
`box_renamed` carries both names for exactly that reason. The trail is the safety, not a
confirm dialog `docs/DESIGN.md` would ban anyway. `ensure_box`'s silent rename routes through
`set_name` as well, so a name reached by that path gets the same check and the same line —
assignment there is what made the name a field two callers could set by different rules.

**THE NAME DOES NOT REACH `Position.label`, AND IT WAS BUILT AND REVERTED TO SETTLE THAT.**
`app/tests/fulfillment.spec.ts` floors that label at 32px with tabular figures wherever one is
drawn, and D31 is explicit that the spec stays unweakened. The name already travels as
`box_name` in the place block and is already drawn beside the label on `CardLocations` and
`Inventory`, so putting it inside the label bought nothing and spent a hard constraint.

**A BOX NUMBER IS ASSIGNED NOW, NOT TYPED: `next_box_number`, the lowest free integer.**
`POST /boxes` takes a name with no number and allocates inside the lock; sending neither
refuses `box_or_name_required`. It reads the CARDS as well as the registry, because a box that
holds cards and has no registry entry is a real box — `_box_row` renders exactly that case —
and handing its number out again would put two boxes' photographs in one directory.

**IT IS DELIBERATELY NOT A HIGH-WATER MARK, WHICH IS THE OPPOSITE OF D10's CARD ALLOCATOR, AND
THE TWO MUST NOT BE MADE TO MATCH.** `next_index` hands a deleted card's index straight back,
because burning it would put a permanent hole in a box over a mis-tapped button. A box number
is the other case: it names an object on a shelf, the operator no longer types it, and nothing
but the store, the disk and the wire reads it — so the lowest free number is the honest answer
and there is no gap for it to close wrongly.

**What this makes stale, named here because the spec is older than the screen**:
`docs/specs/capture-app.md` §5.2 said box selection was a list from `GET /status` and that
"starting a new box is a typed number". Both are overtaken — the field reads `GET /boxes`, and
the number is allocated rather than typed — and that section is marked accordingly rather than
rewritten, the same way §5.1 was when Pass D landed.

**AN EMPTY BOX IS A BOX, AND FOR ONE COMMIT IT WAS UNREACHABLE** (found and fixed 2026-08-26).
`#/inventory`'s box strip was built from the CARD ROWS — `BoxBrowse.tsx:shelvesOf` walked the
cards and collected the boxes they named — so a registered box holding no cards produced no row,
therefore no shelf, therefore no cell. The strip is the only way to SELECT a shelf, and
`BoxIdentity` and `BoxOps` draw for the selected one, so rename, dividers, seal and the whole-box
delete were all unreachable for it. Measured on the owner's store the day it was found: **12 of
13 boxes**, including every box they had just created to test with. `Register a box` was a loop —
it made a box that immediately vanished.

**It is `CLAUDE.md`'s route-is-not-a-feature rule caught from the far end.** That rule was written
for a capability with no control; this is a control, a client function and a tested route, all
present and all correct, for a box no screen could be put on. Worth recording as its own shape:
the checklist that rule prescribes — route, client function, control on the screen a human would
look for it on — was fully satisfied and the feature was still unusable, because nothing in it
asks whether the OBJECT the control acts on can be selected.

**And it is a regression with a commit.** `13c397a`, D31's merge, wrote both this strip and
retired `#/boxes`, whose entire content was the registry list. The merge carried the cards over
and not the registry.

**THE REGISTRY IS UNIONED IN ONLY WHERE NOTHING IS BEING SEARCHED FOR, and that boundary is the
fix rather than a caveat on it.** `shelvesOf` was written so a cell can never lead to an empty
list, and that rule is RIGHT about a query: under one, a cell for a box holding no match is a
dead end. It was wrong only as a rule about the STORE, where an empty box's empty list is not a
dead end but the truth — and it is the only state from which that box can be renamed, sealed or
deleted. The walk says so in words rather than rendering a blank column beside a box header.

**The claim editor is not offered over nothing.** `Set claims on all 0 cards in box 6` was a real
string on a real screen the moment empty boxes became reachable. It is the one control in
`BoxOps` that writes CARDS rather than the box, so it is the only one an empty box can leave with
nothing to do. Absent rather than disabled, per `docs/DESIGN.md`.

**THE WHOLE-BOX DELETE IS TWO PRESSES THAT BOTH NAME THE BOX, NOT A TYPED NUMBER** (the owner,
2026-08-26: *"make deleting boxes just require a confirm click, not type something"*). D10's
ruling 3 gates this operation as the genuinely destructive action it is, and the gate was a typed
box number. The argument for typing is worth keeping because it is most of the argument for what
replaced it: a yes/no dialog is answered by the same reflex that pressed the button, and this
control's whole risk is deleting box 9 while looking at box 95, so a gesture that could not be
performed by momentum forced the operator to read which box they were aimed at.

**What it was measured against was eleven empty spam boxes and eleven typed numbers**, in the
session that made empty boxes reachable at all. A gate whose cost scales with how many boxes you
are tidying up is a gate that gets resented, and a resented gate is read past rather than read.

**So the half that survives is the half that was doing the work: naming the target.** `Delete box
6…` opens the panel and `Delete box 6 permanently` fires it, so the number is printed twice and
the second press is on a control that has to be found rather than one sitting under the pointer.
What is given up is the momentum guarantee, deliberately and by the owner. **This is still not
the "are you sure" `docs/DESIGN.md` bans**: that dialog's confirm says nothing about what it is
confirming, and both of these say the box.

**What would reopen it: a box deleted by mistake.** The fix to reach for first is then graduating
the gate by what the box HOLDS rather than restoring typing everywhere — an empty box's delete
destroys a name and a number, and box 2's destroys 543 photographs. That is one condition on
`record.cards`, and it is named here rather than built because the owner asked for the simple
thing and no such mistake has happened.

## D21 — Game is a per-card claim, not a mode

The product expands to four capture choices — `pokemon`, `riftbound`, `one_piece`,
`pokemon_code` — and the picker sits on the **capture screen** beside Box, Set hint and Finish,
not on the app shell.

**`game` joins the claim family and behaves exactly like the others**: client state, resent with
every capture, written to the record and the sidecar. **Mixed boxes are therefore legal.** That
is not a concession — it is what makes the claim a claim. A shell-level mode would make the game
a property of the *session*, and the first time a Riftbound card turned up in a Pokémon box the
operator would have to either lie or stop.

**`game` is required and defaults to `pokemon`, and D3's null-means-no-claim does not transfer.**
Worth stating because the two look identical and are not. `FinishClaim`'s `null` is meaningful
because there is a **ladder underneath it** that infers a finish from evidence — catalog rows,
detection, a human. **There is no ladder that infers a game.** A missing game is not "no claim";
it is "no export", and every consumer below would have nothing to join against. So the field is
required, and the default is a read-side backfill for records written before the field existed —
never a write-side default.

**This does not discharge D14.** D14's mode toggle is the *track* axis — singles versus codes,
two schemas, two sales channels, two fulfilment stories sharing one rig. `game` is the *product*
axis inside a track. `pokemon_code` sits at the intersection and is the reason both axes have to
exist: it is a Pokémon product line, captured on the singles rig, and disposed of down the codes
track (D24).

## D22 — Taxonomies are hand-authored per game, and audited so they cannot drift

`pipeline/games.py` holds one entry per game: the exact `Product Line` cell, the ordered `Rarity`
cells, the finish enum, the finish→`Condition` map, and the rarity→finish matrix. Pure literals,
importing nothing from this repo, so `scripts/docs-audit.py` can read it with `ast` **without
running project code** — the same rule `docs/map.py` follows and the audit enforces on itself.

**Hand-authored, never generated.** Every field is ARGUMENT in D18's sense: a later session could
reasonably disagree with the stack order of the rarities, or with which finishes a rarity is
allowed to claim. D18's seam list stays empty and this entry is not a request to open it.

**Audited in the direction that can be proved.** The audit reads the committed exports and blocks
on what is provably wrong — a rarity whose folded form matches an export string but whose raw form
does not is a typo and can never false-positive; an export rarity accounted for by nothing is a
gap. It only *asks* about the reverse, because absence from one set proves nothing: `Promo` and
every pre-SV rarity are legitimately missing from an SV09 fixture.

**Rarity strings render verbatim, the way reason codes do.** A second friendly vocabulary is a
thing nothing audits, and the drift D16 exists to catch.

**That state existed for two games and is now occupied by nobody** (measured 2026-08-23). The
entry used to say it was "not yet established that TCGplayer carries Riftbound or One Piece as
`Product Line` values at all", and that it was the highest-risk assumption in the design —
because if it were false, D8 and D11 would have no data and the architecture would change
shape. The owner exported all three. **TCGplayer carries both, on the identical 16-column
header**, so the join is structurally valid for every product line. The exact cells, which
nobody would have guessed:

    Pokemon
    Riftbound League of Legends Trading Card Game
    One Piece Card Game

**Every consumer still refuses on an empty vocabulary rather than falling back to Pokémon's.**
A guessed rarity list is exactly what this repo refuses; an empty one that refuses loudly is
strictly better than a plausible one that prices wrong. The state stays for the next game
added — it is not deleted just because it is currently unoccupied.

**THE SUPERSET RULE COLLECTED ITS FIRST EVIDENCE AND WON, and this is the paragraph to read
before ever narrowing the matrix.** `finish_by_rarity["Rare"]` carried `normal` against an SV09
that stocks no plain Near Mint `Rare` — it was the authored-beyond-the-data example this entry
and D23 both cited, and the standing temptation was to trim it to what one export proved. The
wider Pokémon export stocks **60 plain-NM Rares** (Cosmic Eclipse 38, Crown Zenith 22).
Narrowing it would have made two whole eras unclaimable, on a screen where the excluded chip is
unselectable and the operator has no way to say what is true.

The canonical unproved case is therefore no longer `Rare`/`normal`. It is One Piece's `SR` and
`TR`, authored with `normal` against an export of three sets out of many — and the audit asks
about them as questions rather than blocking, which is the whole shape of the rule.

**A third state, `catalogued`, sits orthogonal to `unverified`** (added 2026-08-23 with the
`misc` entry). The two describe opposite situations and must never share a flag:

- `catalogued: True, unverified: True` — a real product line nobody has an export for yet.
  **Temporary, with a remedy**: get the export. Refusing is right, because a guess becomes a
  price.
- `catalogued: False` — `misc`: the occasional Yu-Gi-Oh, Weiss Schwarz, foreign-language or
  Magic card, about 1% of stock. **Permanent, and correct.** No export is coming. It must NOT
  refuse, because refusing on every misc capture would make a legitimate part of the shelf read
  as a fault, and a real fault would then hide among them.

`misc` carries `product_line: None` rather than `""` — `None` is not a `str`, so the catalog's
comparison can never be true, whereas `""` is both a value a row could carry and the value an
unverified entry uses. It is captured and located like any card, takes **no identification
call** (it is being handled by hand anyway), and carries a free-text operator note instead so
it is findable by search. It sits outside D12 on two axes at once — foreign language breaks
"English", and the other three are different product lines entirely.

## D23 — The rarity claim does three jobs, and one of them pays for the feature

The capture screen gains a multi-select rarity claim, scoped by the chosen game. It does three
things, and they are listed in order of what they are worth.

**1. Cross-check — the new `rarity_claim_mismatch` review reason.** Emitted in the **variant
ladder**, not in routing: routing answers *"is this trusted enough to list?"* and the ladder
answers *"which row is this?"*, and routing is currently the only pipeline module with no Pokémon
in it. It filters the candidate rows to the claimed rarities and reviews when nothing survives —
filter-then-contradict, because on a multi-set collision the filter breaks a `duplicate_condition`
tie for free.

**This is the job that pays.** T1's recorded misses are `051/197` for `031/197` and `271/167` for
`211/167` — *confident* answers, name right, digits wrong. No confidence threshold fires on those.
A rarity contradiction does.

**Rung 0 must not consult it.** A human who looked at the photograph beside the candidate rows
outranks a claim about the stack it came from. `answered()` already refuses to re-consult metadata
and detection, and the failure that taught it is on the record: sixteen answered cards re-deriving
their disagreement and re-parking on every join.

**2. Narrow the finish chips.** Offered = the **union** of `finish_by_rarity` over the claimed
rarities — union, not intersection, because a Common+Rare stack legitimately holds both plain-NM
Commons and holo Rares. Three rules, each of which exists to stop a specific harm:

- **An empty rarity claim narrows nothing.** The screen behaves exactly as it does today. This is
  the compatibility guarantee that makes the whole feature strictly additive.
- **It never auto-selects, not even when one finish is left.** A claim of `{Double Rare}` leaves
  only `holo` and the control still rests on `no claim`. Ladder rung 2 (`CATALOG_FORCED`) already
  resolves a holo-only Double Rare for free, and a manufactured claim makes rung 2 unreachable for
  every card this rig sees.
- **Excluded chips are rendered and unselectable, not hidden**, so the operator can see what the
  claim cost them and take it back by clearing the rarity.

**3. Prompt injection — MEASURED AND SWITCHED OFF (2026-08-23).** Built in the user turn
because it is per-card, scoped so it could not poison D3 rung 3, pinned under its own
`rarity_fingerprint` so the scored default never moved — and then measured with best-case
claims for $0.17, where it lost on every watched axis: holdout down 1.5 points, high-confidence
misses up two, and the finish distribution hardened against the carve-out sentence itself.
`docs/GATES.md`'s T1 section carries the numbers; the switch in `cli/cmd_identify.py` cites
them and names the re-enable condition (a rig-photo measurement, `PKMNSCAN_T1_RARITY=1`).
Jobs 1 and 2 are what this entry now rests on, which is where it always put the weight.

The original design, kept because the machinery still exists behind the switch: `SYSTEM_PROMPT` already says *"Do not infer the finish from the card's rarity"*, and a
careless clause makes it do exactly that — poisoning the one signal that catches a mis-sorted
card. Gated behind `PKMNSCAN_T1_RARITY=1` for an A/B, the same shape as the set-hint knob, and
**shipped in its own step** so the fingerprint moves once, deliberately, with a re-measured T1.

**THE SUPERSET RULE IS WHAT MAKES UNSELECTABLE SAFE, and the two must never be separated.**
`finish_by_rarity` is authored as a superset of what any one export proves. SV09 stocks no plain
Near Mint `Rare`; a matrix derived from that observation alone would make a legitimate plain-NM
`Rare` stack **unclaimable**, and with the chip unselectable the operator would have no way to say
what is true. The audit enforces the superset direction — it blocks on an observed pair the matrix
is missing and only asks about the excess. **If anyone ever narrows the matrix to one export's
observations, unselectable becomes a trap.**

## D24 — Code cards are pooled inventory, not located

Owner's ruling: a code card has **no box, section or card position**. It is a count. An index is
acceptable as a key — it is what the photo and sidecar are named after on disk — but it is not
meaningful, because the physical cards are disposed of once the code is extracted.

**The seam is one registry flag, `located`**, and it is the concrete form of D14's "two tracks,
one rig". `code-card-fork/CLAUDE.md` already said it: *"Codes are fungible pool inventory, not
located items. No box, no section, no position. Do not reuse the singles schema."*

- `located: True` — D10 in full. Sequential position at capture, never renumbered, the label
  rendered everywhere.
- `located: False` — `allocate_capture` is unchanged, because the record still needs an index to
  key its files. But **`Position.label` is never rendered**: not in the review queue, not in a run
  report, not in the pull preview. **Non-located cards never enter the Fulfillment view or the
  pull flow**, because there is nothing to walk to, and that is asserted in
  `app/tests/fulfillment.spec.ts` rather than left to prose.

**Quantity is the unit, and the pipeline already computes it.** D7 aggregates by SKU with
`Add to Quantity` = copy count. The count the owner wants is a thing the join already produces —
surface it; do not build a second inventory.

**D10 and the fork's C3 do not conflict, and the reason is worth having in one sentence:** D10
positions a piece of cardboard, C3 pools a code string. Two records, two primary keys, joined by
the position key.

**Disposal is a terminal state shared with Someday's `removed`.** A code card whose code has been
extracted leaves inventory permanently — record kept, gap permanent, exactly `sold`'s shape.
Someday already carries the same need for a single card pulled out, damaged or given away, and
calls the alternative *"a sale record that lies"*. **Build them as one state, not two.** It is not
a tombstone in D10's sense: D10's refusal was about *undo* inventing a third thing the store must
explain, and `sold` already proved the state-machine shape.

**Channel is a disposition, not a pipeline stage.** D9 wrote this three months early — *"everything
under $0.40 hides the difference between a $0.38 rare and a $0.01 code card, and that difference is
what decides later which of them are worth a bulk lot."* Above threshold, a code card lists by the
ordinary path. Below it, "PKMNCODES eBay lot" becomes a third sub-threshold disposition beside
flat-at-the-floor and flat-price-for-the-run, and `emit` already refuses to write while a
disposition is unanswered.

**The own-box convention (owner, 2026-08-23).** Code cards live in their own box, sorted by
set. Mixed boxes stay legal (D21), but a pooled card captured into a LOCATED box knowingly
consumes a slot number and inflates that box's denominator — the high-water mark counts slots
consumed, and a code card consumes one it will never occupy. Convention rather than refusal,
because a refusal mid-feed is the rhythm-breaker the capture screen is built to avoid.
`docs/CODES-DECISIONS.md` C8 carries the ledger this feeds.

**The render-conditions ruling (owner, 2026-08-23), which is what closes the `views
exposure` questions.** Screenshot renders are LOCAL-ONLY: `captures/ui/` is gitignored, the
pre-commit hook blocks stray images, and the standing opsec rule already forbids a code-card
photo in any listing, README, screenshot or commit. A pooled card's photo appearing in a
local render is therefore contained by guards that already exist, and the five advisory
questions the `views exposure` row asks are answered by this paragraph rather than by
per-screen filtering — which would have cost the owner's own screens their code-card rows.
The row stays: it is the tripwire that re-asks the question if a new screen starts rendering
stored photos.

**Two opsec triggers fire with this work and must be discharged in the same commit.**
`scripts/guard-opsec.sh` has been disabled since 2026-08-03, and D16 says in writing *"Revisit
before the codes track handles real cards."* This work makes that condition true. The recorded
failure was **over-triggering** — it blocked placeholders in prose about the code format — so the
fix is a narrower pattern, never a toggle. And `scripts/views.txt` may never name a URL whose
render can contain a code card.

## D25 — The join partitions by game, and `Product Line` becomes a real reader

**BUILT 2026-08-23, with the acceptance test this entry implies passed literally**: a
single-export Pokemon run was captured before the change and re-run after, and every output —
join stdout, emit stdout, report, both import files, decisions.json — diffed byte-identical.
One addition beyond this entry, flagged rather than slipped in: an `--export` file whose
`Product Line` cells match no registered game refuses by name, because accepting and silently
not using a file is the silent-drop shape the hard rules forbid.

`--export` is repeatable. **Never infer the game from a filename**: read each file's
`Product Line` column, map file → games, then invert to game → files, which must be exactly one.

**This corrects a claim this file used to make.** The Deferred entry said the catalog join was
"product-line-agnostic". Measured, it was product-line **blind** — `Product Line` was declared in
`CANONICAL_HEADER` and read by nothing, so two exports concatenated would have cross-joined in
silence. Blind is not agnostic.

**Catalogs are built per game and never merged.** A merged `_by_number` would report cross-*game*
collisions through `colliding_keys` as though they were the cross-*set* collisions that report is
actually about — different faults with different remedies, since a set hint fixes one and nothing
fixes the other.

`Catalog.from_export` filters to the game's `product_line` and, where set, its
`product_line_rarities`, **reports the drop count, and refuses if the filter leaves zero rows** —
which means the wrong file, and is the one case where continuing is worse than stopping.

**One import file per game.** Nobody has established whether TCGplayer's Import to Staged accepts
a file spanning two `Product Line`s, and `fixtures/staged-import-accepted.csv` proves it for one
line only. Per-game files are correct under either answer, so the question does not need settling
first.

**Refusals exit 1, write nothing, touch no queue, and never prompt.** Two cases: two files
claiming one game, and a game present in the run with no export — the second names up to eight
positions and points at the `PUT` correction route. The check runs before any catalog is built, so
a run that will refuse costs nothing.

## D26 — A card leaves inventory by a state — `retired` — and a bad photo is replaced in place

Ratifies two items that sat on the Someday list, each marked "needs a decision entry ratified by
the owner". Both were named by Gate B's own run.

**`retired` — a terminal card state, `sold`'s sibling.** It was drafted as `removed` and
renamed by the owner on 2026-08-23, because the name was already taken: `server/capture_server.py`
appends a `removed` HISTORY EVENT when capture-undo hard-deletes a record, T7 asserts no event
name is a member of `master.STATES`, and `_state_before_sale` scans history filtering against
that tuple — so a state called `removed` would make months-old undo events parse as states and
a reversed sale restorable to one. The event keeps its on-disk name (nothing already written
moves); the state gets its own word. A card pulled out, damaged, lost or given
away has no representation today, so the only options are a sale record that lies or a mid-box
delete D10 forbids. `removed` keeps the record, leaves the gap permanent, and carries a reason:
`pulled | damaged | lost | given_away`.

**It is not a tombstone in D10's sense**, and the distinction is the reason D10's refusal does not
block this. D10 refused to let *undo* invent a third thing the store must explain — not captured,
not sold, still occupying a position. `removed` is not that: it is a terminal state on a card that
really has left, and `sold` already proved the shape. It also costs less than when it was first
written, because D7's amendment has just moved three states off the card, so the `STATES` tuple it
joins is narrower than the one it was proposed against.

**Both halves were BUILT on 2026-08-23.** `retired` has its route
(`POST /inventory/<box>/<index>/retire`, mark-sold's mirror, reversible with `restores_to`),
its four reasons, and an owner-side control on the Inventory screen with a receipt and undo.
Re-shoot has its route (`POST /inventory/<box>/<index>/photo` — bytes replaced, sidecar
rebuilt from the record, a `reshot` history line carrying both capture ids) **and, since
later the same day, its control: on the pull preview, by the owner's ruling** — the screen
whose whole job is looking at one stored photo beside its position, so the moment a bad
photo is discovered is the moment the remedy is already on screen. A file input rather than
a camera (that screen has none; the rig screen is for live shooting), and the screen's
look-only header now argues its one write honestly. A sale
now refuses a retired card (`card_retired`): the old permissive rule's own justification —
"the only way to record a departed card" — is what this entry retired.

**Re-shoot in place, as originally argued.** A bad photograph discovered late has no remedy: D10's undo reaches only the
newest capture, and `undo_too_late` currently tells the operator to "correct this card on
TCGplayer instead, and leave the position alone" — advice that stops being true the moment this
entry exists. The operation is not a delete at all: **replace the photo and sidecar at an existing
position, record untouched, position label unchanged, allocator never involved.**

**Two adjacent cases are named here and deliberately left out of scope**, so a later session does
not read this entry as having covered them: a returned or cancelled sale (`sold` is terminal and
the only reversal is the Fulfiller's twenty-second window), and a single damaged copy among
several (D12 hardcodes Near Mint, and `decisions.json`'s unlisted is per-SKU rather than
per-copy). D7's fungibility ruling sharpens the second one rather than solving it — a damaged copy
is precisely the one copy that is *not* interchangeable.

## D27 — Session state is device-local and may be persisted

`CLAUDE.md`'s ban on browser storage is about **inventory** — D13 puts one truth on the Mac so two
devices cannot disagree about where a card is. It was never about the capture screen's own
scratch state, and reading it that way costs a real thing.

**Box number, set hint, finish claim, rarity claim and the in-flight `capture_id` are device-local
and meaningless anywhere else.** They are `useState` today, so a reload loses all of them — and
the last one matters most: a reload during a halt makes a lost-response ambiguity permanently
unresolvable, and D10's high-water mark hands the burned position straight to the next physical
card.

**`sessionStorage`, never `localStorage`**, and the permitted keys are named here so a lint rule
can enforce the boundary. Session scope is the point: a new tab is a new session, and nothing
about a shift survives closing the browser.

**A SECOND USE JOINED THE CARVE-OUT ON 2026-08-29, AND IT IS A HANDOFF RATHER THAN A MEMORY
(D39).** `pkmnscan.run-scope` carries a box and the cards ticked in it from `#/inventory` to
`#/runs`, because the pipeline moved to a route of its own and the one mass-select in the product
did not. It qualifies on this entry's own test — device-local, meaningless anywhere else, and not
a fact about where a card IS — and it is `sessionStorage` for the same reason everything else
here is: a tick list that outlived the browser would be a filter over a spend button that nobody
alive remembered setting.

**It differs from the four above in what a reload means, which is why it is worth naming
separately.** Those exist so a reload does not lose the shift. This one exists so a reload does
not silently WIDEN what the next press pays for — and it is cleared deliberately on three
routes rather than expiring: the operator's control, picking a box, and arriving from
`#/inventory` with nothing ticked. `app/src/runHandoff.ts` is the one module that reads or
writes it.

`useCamera.ts` already argues this carve-out informally for the device id and the rotation chip;
this entry generalises what that file worked out and makes it checkable.

**Trigger mode is explicitly NOT covered.** D19 keeps arming an act, and an armed machine that
survives a reload is exactly the automatic-anything that entry refuses.

## D28 — The review answer gets an undo window, and the list stops moving under it

The review queue's irreversible action has fewer guards than the product's reversible one, and
that is backwards.

Pressing a digit writes a SKU and a condition onto a real card. `store/queues.py:Queue.upsert`
refuses to re-queue a position a human has cleared — deliberately, so an answer outlives the
question — so there is no undo, no confirm and no acknowledgement. Meanwhile mark-sold, which is
reversible, gets a photo to confirm against, a two-step control, a twenty-second undo and a
pre-checked `restores_to`.

**Two fixes, because there are two halves.**

1. **The list stops moving.** The photo has no reserved dimensions, so answering one card can
   shift the candidate rows by most of a screen — under a finger already travelling toward a
   number. Reserve the photo's height and prefetch the next card's image. This removes the cause
   of most mis-taps and costs no keystroke.
2. **A twenty-second undo**, the shape the product already ships. `Queue.upsert`'s refusal stands
   for everything outside that window; the window is a hole punched in it on purpose, not a
   softening of the rule.

**This reopens `docs/DESIGN.md`'s no-acknowledgement rule for this one screen, and the grounds are
in the rule itself.** That rule is justified by "Undo covers the mistake" — and on this screen undo
does not exist, so the rule leans on something that is not there. Fixing the premise is the honest
repair; adding a confirm dialog would have doubled the keystrokes on the screen the owner spends
the most hours in, which is the thing the rule was written to prevent.

**Rejected: requiring a modifier or an Enter to confirm.** Considered and declined for the reason
above — one key per card is the property worth keeping.

## D29 — A homogeneous queue may be answered as a group

**BUILT 2026-08-23.** The reading that shipped, enforced server-side: each entry offers
exactly ONE candidate — its own — under one shared reason and one shared condition string. A
shared SKU is deliberately not required and cannot be what "same single candidate" means:
sixteen cards are sixteen catalog rows, and answering card A with card B's SKU would be
corruption wearing a reading. Validate-everything-then-write-everything in one store session
(`group_entry_refused` / `group_not_uniform` exit with zero edits); every position gets its
own `answered` line tagged `group: N`; the group confirm is the review screen's first solid
accent fill, ruled legal because the eligibility conditions are precisely what reduce the
state to one action; and the undo reverses per position through the single route, reporting a
partial reversal honestly rather than pretending atomicity it does not have.

Reopens D4's one-card-at-a-time, narrowly, on evidence D4 did not have.

Gate B's queue was 16 of 53, **every one the same reason code**, and detection agreed with itself
across every duplicate pair — both Thievuls, both Eiscues, both Pyroars. One systematic fact about
the rig's lighting, sixteen identical taps. The discarded pre-rotation run queued 45 with one
shared cause.

**Grouping and filtering, always. A group write only under both conditions:** every entry in the
group shares a reason code, **and** every entry offers the same single candidate. Anything looser
is a bulk write over cards a human has not actually compared, which is what D4 exists to prevent.

D4's "digital-only, one-tap choice beside the photo" is unchanged for every card that does not
meet both conditions — and a group write still shows the photographs it is about to answer for.

## D30 — The physical convention for a gap

D10 makes a sold position a permanent gap, and the Fulfiller creates one per order. Nothing has
ever told him to leave anything behind in the slot, and nothing teaches anyone to read a position
label — `Card 17` is the **seventeenth slot**, not the seventeenth card you can count. Once a
section has holes those two stop being the same number, and every label in that section becomes
uncountable by hand.

**This is retroactive, which is why it wants settling before more sales happen.** A convention
adopted after fifty gaps exist cannot be applied to them.

Two halves, and only one is code:

- **Physical**: the operator leaves a marker in the slot a pulled card came out of. Which marker
  is the owner's call and belongs in this entry once made.
- **Digital, and free**: a position renders with its neighbours and its section's gap count —
  "Card 17, between Mantine and Thievul · 2 slots in this section are empty". Neighbours make a
  label countable again without anyone learning the rule, and the gap count says why the count
  came out short.

**A box audit is the check that closes this loop** — count what is physically in section 2 and
compare it to what the record says. Nothing has ever compared a physical box against the record,
and D20's `box_fill` and `sections_for` are what make it computable.

---

## D31 — One owner-side view of stored cards, and the Fulfiller does not get a vote on it

**Three routes rendered the same 767 records and the owner named it: they read as separate
instances of one thing** (2026-08-23). `#/inventory` searched by SKU and sold a copy,
`#/boxes` held the registry and the layout editor with no way into a box's contents at all,
and `#/pull` walked a box with photographs. Same store, same records, three looks, and the
one question a person actually arrives with — *what is in this box, and can I click it* —
was answerable on the screen named after a fulfilment errand and nowhere else.

**All three collapse into `#/inventory`.** `#/boxes` and `#/pull` cease to exist as routes.
Box operations — name, sections, seal, delete — live on the box header inside the browse,
beside the box they operate on.

**IT SHIPPED AS TWO MODES BEHIND A SWITCH, AND THAT WAS WRONG.** This entry first read "two
ways in, because there are exactly two questions", and it was built that way: a segmented
control offering *Browse the boxes* or *Find a card*. The owner, on seeing it:

> *"i imagined moreso in this merge that these wouldn't be two tabs, instead it's basically
> find a card in a box-based system if anything.."*

That is a better reading of the same merge and it is the one that shipped on 2026-08-23.
**The box walk is the SPINE — box → section → card — and finding a card is search over it,
not a mode beside it.** The switch is gone. D7's SKU→positions map did not go with it: it is
drawn for whichever card the walk currently points at, so "every copy of this card and where
each one sits" is a property of the selected card rather than a different screen. Searching
narrows the walk and the box strip together; picking a result puts you in the box, at the
card, with its copies beneath it.

**Two tabs was the wrong answer for a reason worth keeping**: it preserved the old screens'
boundary inside the new route, which is the shape a merge takes when it is performed on the
routing table instead of on the question the screens answer. There was only ever one
question — *where is this card* — asked from two directions.

**THE FOLD IS PRESENTATION AND NEVER A FILTER.** Sections collapse (box 2 holds 22 of them
over 544 cards), and the collapsed set does not touch what the keyboard walks: arrows,
PageUp/PageDown, Home/End and the box strip all still traverse the whole box, and stepping
into a shut section opens it. A fold that also filtered would make the arrow keys and the
scrollbar disagree about what the box contains, and the operator would have no way to tell
which one was lying. Not persisted, for the reason D19 gives about arming: state that acts
on its own must be re-established deliberately.

**COLLAPSED IS THE RESTING STATE, and the control names what ONE press does.** Both were
owner reports on 2026-08-23 and they are the same defect seen twice. The screen opened with
the selected card's section already open while the button offered `expand all`, so the first
press expanded and a second was needed to reach collapsed — *"you gotta click it once or twice
for it to be working right"*. The cause was the mark-never-hidden effect firing for the
INITIAL, automatic selection, which the operator never made. A move is now a step between two
selections, so nothing opens on load, on a reload, or on an upstream write.

The fold control reads `any` rather than `every`, so from a partial state one press always
produces the state the label names. Collapse wins the tie because collapsed is where the walk
rests.

**A SEARCH OPENS EVERY SECTION HOLDING A MATCH, and clearing it collapses fully.** A result
you cannot see is not a result. It is deliberately NOT a clause in `isOpen` — a fold made
during a search has to stick, which is the same act-versus-consequence line drawn above.
Clearing returns to the resting state rather than restoring what was open before, so there is
one state to learn instead of two.

**MASS-SELECT IS BOX-SCOPED AND IS NOT PERSISTED.** The selection clears on a box change
because the write it feeds is box-scoped, and a selection surviving into a box it cannot
apply to is a loaded gun. It survives a FOLD — the count is carried on the status line and on
every section header — because a fold that could hide what a write would reach is the one
combination of these two features that is genuinely dangerous.

**The three routes that had no client half at all landed here, on this screen** — the
whole-box delete, the mid-box delete with its contiguous shift, and the retroactive claim
corrections at both the card and the selection level. They existed with full T7 coverage and
no control anywhere, which is what produced `CLAUDE.md`'s route-is-not-a-feature rule; this
is where they became reachable, and `app/tests/inventory.spec.ts` is what asserts they stay
that way.

**The re-shoot control comes with it and may not be dropped in the move.** D26 put it on the
pull preview deliberately — *"the screen whose whole job is looking at one stored photo
beside its position, so the moment a bad photo is discovered is the moment the remedy is
already on screen"*. That argument is about a detail panel showing one card's photograph,
not about a URL, so it transfers intact to the browse's card detail. A merge that loses it
has broken D26.

**`CLAUDE.md`'s "six screens and six routes" was already wrong before this entry and is
rewritten by it.** The table in `app/src/App.tsx` carried SEVEN — the gallery makes the
seventh, and that file's own comment says "it matters more at seven routes than it did at
three" while `CLAUDE.md` still said six. Five remained: capture, review, inventory,
fulfillment, gallery.

**It is SEVEN as of 2026-08-30: `#/runs` (D39) and `#/pricing` (D49).** Recorded here because
this is the entry that owns the count and because the direction matters: this merge deleted two
routes that rendered one thing, and that ruling is untouched by routes being added for things no
route rendered at all. `#/inventory` still holds the walk, the card, its copies and the box's
operations; what left it is the pipeline, which was never one of the three screens this entry
merged, and what joined it is hand-pricing, which no screen has ever offered. The count is
restated in `CLAUDE.md`, `docs/map.py`, `README.md`, `app/src/App.tsx` and `scripts/views.txt`,
and the not-rendered-rather-than-hidden rule for the Fulfiller's nav is untouched — it was never
about how many owner routes there are.

**AND THE COUNT WAS FALSE IN FIVE PLACES FOR THE WHOLE OF D39's LIFE, WHICH IS THE FINDING
WORTH MORE THAN THE NUMBER.** `#/runs` landed and `README.md` went on saying five screens,
`docs/map.py` five routes, and `app/src/App.tsx`'s own header — the file that HOLDS the table —
`Five now`. None of it failed a check, because `scripts/docs-audit.py` reconciles no count of
anything: D18 deleted the last published one deliberately, on the argument that a verifiable
fact nobody can disagree with is not load-bearing prose.

That argument is right about a number in a report and wrong here, and the difference is worth
naming. A count of routes is what a session reads to learn the SHAPE of the product before it
edits anything, and a wrong one sends it looking for a screen that does not exist or building
one that does. It is still not mechanically checked — a check would have to decide what counts
as a screen, and this entry is not opening that — so the defence is that this paragraph exists
and that D31 is named in every file that restates the number.

**THE FULFILLER'S SURFACE IS DOWNSTREAM AND IS NOT A COUNTERPOINT.** Recorded because it was
argued the wrong way round and the owner corrected it: *"do not concern yourself with
fulfiller concerns, fulfiller concerns/settings are downstream of build work and should not
be a counterpoint to any build work."* The case was real — `#/pull` was offered as a screen
the fulfilment flow leans on, as a reason to merge less — and it is exactly the inversion
this rule forbids. D5 makes the Fulfiller's screens a *skin* over what the owner's build
produces and D13 puts one truth behind both; a skin settles after the thing it presents
exists. Letting it veto upstream structure lets a consumer decide the shape of what it
consumes.

**What this does NOT license, stated because the sentence above is the kind that gets
overread**: `app/tests/fulfillment.spec.ts` and `docs/DESIGN.md`'s nine hard constraints
still pass, unchanged and unweakened. `#/fulfillment` is not merged into anything and keeps
its own route — it is a different persona at a different posture, and it is the one screen
in the product whose whole design is a floor. The ruling is about which arguments may
decide architecture, not about which tests may go red.

---

## D32 — The pixel budget is spent on the card, not the desk

**The owner's question, 2026-08-23**: *"should we run a mass crop / should i be prompted on a
way to trim images where im like for this run you wont need the top or bottom 5% ... resizing
with sliders or something to save on pixel load and thereby less tokens?"* The instinct was
right and the axis was right — measured over 544 real frames, the card fills 80–88% of the
width and only 61–72% of the height, so the waste really is top and bottom.

**Detection, not sliders.** `geometry.detect_card` already answers this per frame, locally,
for free — the border search built for Gate B and covered by T6. Over all 544 box-2 frames it
found the card **544 times, refusing none** (467 by edge search, 77 by tone). A fixed
percentage would be a guess that is wrong per frame: card area across that same box ranges
39% to 81%, because cards move on the tray. The detector knows; the operator would be
estimating.

**At identify time, in memory, never on disk.** The photograph is not modified. A wrong crop
costs one re-run of a free local step; a crop written at capture is irreversible by the time
anyone notices, because the card is back in the box. That is D10's undo argument read the
other way — undo is safe *because* the card is still in your hand, and at identify time it is
not. It also means the 682 photographs already taken benefit, which a capture-time preset
could never do, and that every other consumer keeps the full frame: the review queue photo a
human judges foil against, the pull preview matched to a physical slot, the re-shoot
comparison.

**A refusal sends the whole frame.** `detect_card` answers `None` rather than guessing (T6:
*"'Not found' must be a refusal, never a guess"*), and the honest response is to send what was
always sent. The preflight names the count, because a nonzero refusal count means some cards
are going at whole-frame cost and that is worth seeing before spending.

**THE COST MODEL WAS GOT WRONG IN PUBLIC FIRST, AND THE CORRECTION IS THE USEFUL PART.** The
first estimate reasoned from the card's AREA in the frame — 53%, therefore a ~40% saving. That
is wrong, because `MAX_EDGE` normalises the LONG EDGE, not the area. The frames are 2160x3840
(aspect 0.56) and a card is aspect 0.72 — fatter — so at an unchanged 1568 cap the crop sends
*more* pixels, not fewer: measured, +26% cost. Cropping buys resolution by default and only
buys money if `--max-edge` comes down with it. Recorded because the arithmetic looks obvious
in the wrong direction and a later session will re-derive it the same way.

The measured frontier, 20 real frames, against today's full-frame @1568 baseline of $0.72 for
box 2 and 268x57 native pixels on the collector-number strip:

| config | box 2 | native px on the number | vs today |
|---|---|---|---|
| crop @1400 | $0.76 | 1.95x area | dearer, much sharper |
| crop @1200 | $0.62 | +16% linear | cheaper AND sharper |
| crop @1100 | $0.56 | +6% linear | cheaper, ~parity |
| crop @1000 | $0.50 | -3% linear | cheaper, ~parity |
| crop @900 | $0.44 | -13% linear | cheapest, softer |

**Off by default, behind `--crop`.** It changes the bytes a card is read from, and Gate B's
53-card end-to-end run — the only one this project has — was full-frame. Turning it on is a
per-run choice until a measurement says otherwise.

**KNOWN GAP, NAMED RATHER THAN PATCHED: the crop is not part of the cache identity.** The
cache is keyed by card key plus the profile's prompt fingerprint, and neither `--crop` nor
`--max-edge` is in that hash — so a cropped run over cards already answered uncropped would
reuse the old answers and report cache hits. It cannot bite today: box 2 has zero cached
answers, and the A/B that measures this ran in isolated `PKMNSCAN_HOME` directories precisely
so the two configurations could not read each other's cache. The remedy when it matters is the
shape `rarity_fingerprint` already established — a sibling hash kept deliberately OUT of
`prompt_fingerprint`, so recording what an image was read from cannot move `1ef974bf511d`.

**THE SCREEN OFFERS THE PAIR, NOT THE TWO CONTROLS (owner, 2026-08-25).** The run panel drew
this decision as a checkbox reading `Crop to the card` beside a number reading `Max edge`, and
those two labels were **every user-visible string in the block**. The owner asked the question
that settles it: *"walk me through how im supposed to understand crop with just this dialog
box"*. They could not. Everything above — what the crop does, that the photograph on disk is
untouched, what a refusal falls back to, and above all that the two are ONE decision — lived in
this entry and in a code comment.

**The paragraph on getting the cost model wrong in public is what makes this a defect rather
than a missing sentence.** That correction exists because the arithmetic runs backwards from
intuition: cropping at an unchanged max edge sends MORE pixels, measured at +26%. A checkbox
that reads as *send less* beside a number nobody explained is an invitation to do exactly that,
and the panel had no guard against it — it was one click from the most expensive setting on the
frontier while appearing to ask for the cheapest.

**So `READINGS` offers three named PAIRS, and a pair cannot be got wrong.** `Measured best ·
1200`, `Cheapest · 900`, `Whole frame · 1568` — three rows of the measured table above, each
setting both values, each carrying the sentence that says what it costs and what it buys on the
box it was measured on. `Sharpest · 1400` is not one of the three: it is the row strictly dearer
than the baseline, and three chips fit the 340px end of D38's column where four do not. It lives
behind **`Custom`**, which reveals the old checkbox and number unchanged — demoted, never taken
away, because a free-form max edge is a real need and this entry's own frontier runs wider than
three points.

**The warning follows the mistake to where it is still reachable.** `Custom`'s sentence is the
only one that names the +26%, because `Custom` is the only state that can produce it.

**THE ESTIMATE IS VOID WHEN THE READING MOVES, and that was a hole in D33's money gate rather
than a copy gap.** `RunPanel.tsx`'s `scopeKey` was `box:indices` alone, so unticking the crop
after Check cost left a stale figure standing above a live *Spend $0.62 and identify 36 cards*
button — an estimate for a send that was no longer the one about to happen. The effect's own
comment already stated the governing rule, *"a confirm whose first step described a different
set of cards is not a confirm at all"*; it named cards where the estimate is computed from
BYTES, and the crop and the max edge are what decide those. Both values are in the key now.
`app/tests/run-panel.spec.ts` asserts the void as an ABSENCE, the same shape as the spend
button's own case, and it was observed failing against the old key before it was kept.

**The cache gap above is now said on screen, in the words it means rather than the words it
is.** Where the preflight reports any cache hits, the quote carries one line: *cards already
answered keep the answer they were first read with, and the reading only reaches the cards
being sent*. No hash is named — the panel has no business publishing `prompt_fingerprint` — and
nothing about the gap is closed. Drawn only above zero, because a warning about answers that do
not exist is the kind an operator learns to skip.

**THE READING IS DRAWN NOW, NOT ONLY DESCRIBED (built 2026-08-29, at the owner's instruction:
*"there should be a crop preview on the runs tab given that I need to select a crop there"*).**
`POST /pipeline/crop-preview` is free, writes nothing, shells out to nothing, and answers what
the selected pair would send for one card; `RunPanel.tsx` draws it in a column beside the
chips. Everything above stands — this is the sentence the READINGS block could not be.

**THE MEASUREMENT THAT DECIDED THE DESIGN: the rectangle is IDENTICAL at 1200 and at 900.**
The cut comes from `detect_card` plus the aspect correction plus `CROP_PAD`, and not one of
those reads `max_edge` — the downscale happens after. So a preview that drew only the crop
would leave two of the three chips looking exactly alike, which is most of the question the
owner was asking. The pair has two axes and one picture cannot carry both:

- **The crop decides FRAMING**, and the frame shows it as a composite: the discarded margin is
  the stored photograph at 35% opacity, and the cut region is **the payload itself**, at full
  strength, with the accent outline on the boundary. It answers *is the collector number inside
  the bytes* — box 2's failure, 38 numbers cut clean off — and **a picture of the crop alone
  could never answer it, because what was cut is not in the crop.**
- **The max edge decides RESOLUTION**, and it is shown by a **1:1 window onto the same file**.
  `background-size: auto` with a pixel `background-position` IS 1:1, with no scaling arithmetic
  to get wrong and no second request. That is the review queue's loupe one screen over, aimed
  at the PAYLOAD rather than at the stored photograph, and the same standards are behind it:
  FADGI and Metamorfoze both require this class of judgement at 100%, and here a downscale is
  precisely what is being judged.

**THE FRAME DREW THE STORED PHOTOGRAPH UNTIL THE OWNER CAUGHT IT** — *"the crop preview should
also show the depixelation reflected as you change the options"*. It did not, and could not: it
was `GET /photo`, which is the same bytes at every reading, so the one thing being changed was
the one thing the picture could not show. It draws the prepared bytes now, which costs 235-441KB
on a localhost socket, debounced, for one card.

**AND THE FRAME STILL CANNOT SHOW THE DIFFERENCE, WHICH IS PHYSICS RATHER THAN A DEFECT.** It
draws the payload at roughly 28% of its pixels, and no two downscales are distinguishable under
a reduction that large — an operator comparing 1200 against 900 up there will correctly see no
difference and wrongly conclude there is none. So the caption says `shown reduced`, and the 1:1
window below is where the comparison is actually made. Recorded because the obvious "fix" is to
enlarge the frame, and no size short of 100% would work.

**THE BAND STOPPED BEING A SECOND IMAGE, and that is what makes the pair trustworthy.** It was
a separately encoded JPEG of the number strip; it is a RECTANGLE INTO the sent bytes now, and
the window paints that region of the file the frame is already showing. One image over the
wire, two views of it, and **the second cannot drift from the first because there is no second
file to drift**. It also costs fewer bytes than the two-image version it replaces.

**THE WINDOW FOLLOWS THE POINTER, AND THAT IS WHAT MAKES A BANDLESS GAME USABLE.** It rests on
the collector number where the registry claims one and reads whatever the pointer is over
otherwise — so on Riftbound, where nobody has measured where the identifier prints, the
operator points at it themselves. A refusal that had taken the magnifier away with it would
have left that game strictly worse off than before the preview existed.

**ONE COMPUTATION, TWO CALLERS, AND THAT IS THE HONESTY OF IT.** `identify/images.py:crop_rect`
is the rectangle `card_crop` cuts, extracted so the screen can draw it rather than derive one
of its own. A preview with its own copy of that arithmetic is a preview that can reassure the
operator about a crop it is not describing — which is EXACTLY the failure the aspect correction
was written for. `card_rect` splits out beside it, unpadded, because the number band is a
fraction of the cardboard rather than of the cut. T6 asserts the identity and was observed
failing against a `card_crop` that had quietly stopped using it; the extraction was checked
byte-for-byte against the committed version on 25 real box-2 frames before anything was built
on it.

**IT IS PRESSED BEFORE THE PREFLIGHT, WHICH IS THE ORDER OF THE DECISION.** The reading is
chosen here, the estimate is what the choice costs, and the spend button does not exist until
the estimate has answered — three steps down the panel in the order they happen. It is keyed on
the same `scopeKey` that voids the estimate, so a chip press redraws the picture and clears the
number together. The previous strip stays up, dimmed, while the next is fetched: blanking would
move `Check cost` under a pointer already travelling toward it, which is D28's hazard on the
one panel whose next button spends money.

**`rect: null` MEANS TWO OPPOSITE THINGS AND `method` IS WHAT SEPARATES THEM.** The crop being
off is a setting the operator chose; detection refusing is a card going at whole-frame cost
when they asked for a crop. The route reports both and the strip says which, because the
preflight counts refusals across the box and this is where one can actually be looked at.

**ONE CARD, BESIDE THE CHIPS, WALKED BY THE ARROW KEYS — and it was three abreast underneath
them for a few hours.** The first build sampled three cards evenly across the box on this
entry's own measurement: card area runs 39-81% across box 2 because cards move on the tray, so
the front of a box does not stand for it. That argument is right about SAMPLING and it lost to
a plainer fact, which the owner put plainly: *"the preview right now is too small"*. Three
pictures across a panel are three small pictures — each frame drew 112px wide — and a preview
nobody can read is not a preview. One card in a column of its own is ~2.5x the linear size for
the same block of screen, and the spread is reached by WALKING, which is also the only version
of it that lets the operator look at a card they actually suspect.

**The walk wraps, on both sides of the wire.** The route takes `offset % total` so a stale
client cannot send a negative, and the screen wraps too so the caption stays inside the box
being looked at. Arrow keys are the control and the buttons beside the card do the same thing:
a key with no visible affordance is a key nobody finds. **The listener is guarded on the
event's target** — this panel holds a number input and a `decisions.json` textarea, and an
unguarded window listener steals the caret keys from both. The fetch is debounced at 140ms,
because a held arrow key repeats faster than a photograph decodes.

Measured at ~115ms a card — 63-84ms of detection, ~51ms to crop, downscale and encode — so
firing it on every chip press and every arrow press is affordable.

**Two things came with it that are not about pixels.** `make server` ran bare `python3`, whose
interpreter has no Pillow, so this route would have refused on the one machine it is for; it
runs `$(PYTHON)` now, which is the venv where one exists and `python3` where none does — the
property that line protected was *"must not NEED `make venv`"*, and that is intact. And the
imports are inside the handler, so a missing Pillow is a named `imaging_unavailable` refusal
rather than a server that will not boot over a preview nobody asked for.

**D24's tripwire fired, and it is answered by D24 rather than by new machinery.** `scripts/
docs-audit.py`'s `views exposure` row now names `#/runs` as a screen that can draw stored
capture photos — which is exactly what that row is for, and the render-conditions ruling in D24
already answers it: renders are local-only, `captures/ui/` is gitignored, and the pre-commit
hook blocks stray images. No per-screen filtering, for the reason that ruling gives.

**What this does NOT do: it does not record what a PAST run sent.** The strip recomputes with
today's detector, so it describes the run you are about to start and nothing else. That
distinction matters for box 2 specifically — its crops were cut by the flat pad this entry
records, fixed in `d431afb` about 35 minutes after that run was submitted, so a recomputation
of those cards shows the corrected crop rather than the one that lost 38 collector numbers.
Making a run replayable means recording the box on the run payload at identify time, which is a
change to what `identify` writes and has not been argued. Until it is, this is a preview and
never a receipt.

**THE BAND IS THE REGISTRY'S TO GRANT, PER CARD, AND THIS SHIPPED WRONG FIRST.** The first
build cut `geometry/crop.py`'s number band over every card whatever game it was, and
`pipeline/games.py` refuses exactly that in writing: *"the bands are fractions measured on a
Pokemon card. Nothing has measured where a Riftbound card puts its title or its number, and a
band claimed without that measurement is cut over the wrong pixels."* Box 1 is Riftbound, the
owner opened it, and the strip drew that card's RULES TEXT as though it were a collector
number. Only `pokemon` claims a number band today; a game that does not gets **no band and the
registry's own sentence saying why**, which is the same refusal `crop_regions` makes reached
through the same field. **The CUT is unaffected** — a card is 63x88mm whatever is printed on
it, so the crop is right for every game even where no band has been measured, and that
asymmetry is the whole reason the two halves are separate answers.

Worth naming as a class rather than an instance: the registry already held the answer and the
first build did not ask it. A preview is a second reader of everything the pipeline knows, and
every fact it draws has an owner somewhere in `pipeline/` — drawing one from a constant instead
of from its owner is how a picture ends up more confident than the thing it depicts.

**What would reopen this: a refusal the walk never reaches.** The preflight counts detection
refusals across the whole box and the walk shows one card at a time, so a box with three
refusals among 543 is a hunt. If that ever costs a real session, the fix is a control that
jumps to the next refused card once the preflight has answered — not a return to sampling,
which is what made the picture too small to read in the first place.

---

## D33 — The pipeline is reachable from a screen, and one route can spend

**BUILT 2026-08-24, and it is the largest instance of `CLAUDE.md`'s route-is-not-a-feature rule
this repo has had.** The owner: *"how do i get api calls/pushing from our localhost server so
that i can actually push runs at box/section/whatever-level i want, get data back, and manage
CSVs?"* — and then, after a session that designed the screen, interviewed them about it and drew
a mockup without building any of it: *"i also don't see any of the UI you stated you'd be
building that let me do all of this within the app???"* Both were correct. `./pkmnscan identify |
join | emit | reconcile` has existed since build-order step 4, has been through a 53-card run and
a 544-card run, and could be reached only by somebody typing at a terminal.

**`server/pipeline_routes.py` is its own module because it is the one part of the server that
can cause money to be spent.** `server/capture_server.py`'s header promised *"this process never
spends money: it holds no API key and makes no outbound call"*. Both halves stay literally true —
nothing there reads a key or opens a socket to Anthropic — and the sentence was written to mean
more than its letter, so it is rewritten rather than leaned on. A promise that quietly narrows to
a technicality is the drift D16 exists to catch.

**What replaces it, because a guarantee deleted and not replaced is a regression:**

- **One route spends and is named for it** — `POST /pipeline/identify`. It refuses without an
  explicit `confirm` field, and it refuses a second run over a capture directory a live run is
  already reading: a double-click is the realistic accident, and two live batches over one box
  is two invoices for one answer.
- **The preflight is free, is a separate route, and creates no run directory at all** —
  `identify --dry-run` returns before `runs.create`. It is what the screen must show first.
- **Everything else is free and re-runnable**, which is the property D1 gave the two-phase split.

**THE MONEY STEP SPAWNS AND IS NEVER AWAITED; EVERY OTHER STEP RUNS IN THE REQUEST.** Not a
preference — the shape of the work. A Batch takes minutes to hours and no HTTP request may be
held open for that; `join`, `emit` and `reconcile` are local arithmetic over a parsed CSV. The
child is detached and logs into the run directory, so **a run outlives the server that started
it**: the Mac sleeps, `make server` restarts, a tab closes, and the poll still reads the run
directory. `cli/runs.py` already makes a run an immutable input rather than state, and this
leans on that entirely — nothing is held between requests.

**Scope is a box, or a selection inside one.** A subset becomes a directory of symlinks built
**outside `captures/cards/`**, which is load-bearing: `identify.sidecar.scan` walks its root
recursively, so a scope directory under it would be walked by the next run pointed at the box
above and every card submitted twice. Gitignored under the opsec rule as well as the derived one
— a bearer instrument reached through a symlink is still a bearer instrument.

**Exports are uploaded, never named by path.** A screen cannot know what is on the server's disk,
and a route that opened any absolute path a request named would be a file-read primitive guarded
by an origin header. It also leaves the run holding the exact bytes it was joined against, which
the manifest could only describe by hash.

**THE MONEY GATE IS TWO STEPS AND NO TYPING** (the owner's ruling). Check cost, read the count and
the estimate the command itself printed, then press the confirm that appears beneath them. The
confirm **does not exist** before the preflight has answered — absent, not disabled, because a
disabled button is one attribute away from pressable and that attribute is what a later refactor
drops without noticing. `docs/DESIGN.md` permits a gate on a genuinely destructive action; the
cheapest honest gate here is making the number impossible not to have seen.

**The panel sat on `#/inventory` UNTIL 2026-08-29 AND NOW HAS A ROUTE — see D39, which is where
that argument was overruled and how.** The reasoning here is unchanged and is what D39 was built
against: D31 collapsed three screens into that route on the finding that they were separate
instances of one thing, and a run is not a different thing again — it is something done to the
box being walked, or to the cards just ticked in it. A route of its own would re-implement the
box strip, the search and the mass-select, and would then be free to disagree with them about
what is selected.

**What D39 does with that is split it.** The box IS re-answered, by a picker of its own, which
is cheap and cannot disagree with anything. The SELECTION is not: `#/inventory` keeps the one
mass-select in the product and hands the ticked indices over, so there is still exactly one
place a selection can be made. Read the paragraph above as the specification that build had to
satisfy rather than as a placement this file still asserts.

**IT IS NO LONGER FOLDED, AND NEITHER IS `BoxOps` (owner, 2026-08-24).** This entry read "folded
by default", on `BoxOps`' measured reason: ~250px, reached once a box, on a screen whose question
is *where is this card*. The owner overruled it in three messages, the last unambiguous: *"both
box and run, i don't want click in functionality, i want their buttons just there."*

The argument the fold rested on has the weaker half of a true premise. Reached once a box IS
every box, which is the definition of the primary task rather than an exception to it, and NN/g
prices a collapsed panel at five accumulating substeps — scroll, scan, decide, target, wait —
before the first click of real work. This repo's own record already made the same point one
notch further along: three routes shipped with full T7 coverage and no reachable control at all,
which is where `CLAUDE.md`'s route-is-not-a-feature rule came from. A control behind a fold is
one step better than that, not a different kind of thing.

**What replaces the fold's saving has been rewritten three times, and the third is the panel's own
MEASURE (2026-08-26).** The column is gone: its HEIGHT was setting the grid row that positioned the
card's copies (D38, amended), so the panel moved to the last row of the content column and got the
full width instead. Given 1024px it draws **625px closed and 1143px open**, against 799 and 1461 in
a 370px track, with no code change — the head stops wrapping four command names and the step notes
and free steps unwrap with it. Nothing folds, nothing is capped, nothing scrolls internally, and
every control this entry protects is still drawn unconditionally; what moved is reading order.
`app/tests/run-panel.spec.ts` now asserts that as an absence — `<details>` and `<summary>` at zero
inside the panel — which is the one form of this ruling no future relocation can falsify.

The two earlier answers, kept because the sequence is the argument:

**What replaces the fold's saving is the COLUMN, not the disclosure** — and that sentence said
*the row* until 2026-08-25, which is the honest way to record what actually happened. `BoxOps` and
the run panel first shared one grid row beneath the card detail (`.browse-boxrun`, `1fr 1fr`), so
the pair cost one panel's height rather than two. `defaultOpen`, the two disclosure triangles,
their `[open]` flips and both `-webkit` marker resets were deleted then and stay deleted.

**They now stand in a third column of their own, to the right of the card** (the owner, the next
day: *"put box top right, and runs below it"*). It is the same argument at its limit rather than a
different one: the row cost the card's column one panel's height, and the column costs it nothing.
The space came from the card's own photograph, shrunk to the height of the fact rows beside it —
see D38, which is where that measurement and the rest of the rebuild live. Stacked in that column
`BoxOps` sits above the run panel, and `.browse-boxrun` is a flex column rather than a grid so the
shelves that get no box panel produce no leading gap.

**ALL FOUR STEPS ARE ON SCREEN IN EVERY STATE, AND THREE OF THEM WERE NOT UNTIL 2026-08-25.**
`RunPanel.tsx`'s `STEPS` list is authored rather than derived from `phase`, and says why in its own
comment: *"a screen that only drew the current step would leave the operator unable to see that
emit exists until join had finished."* That promise was kept against `phase` and broken against
`detail` — join, emit and reconcile rendered inside the open-run guard, so with no run picked the
panel drew Identify and nothing else, and **with no runs at all the pipeline's other three
quarters existed nowhere in the document**. A first-time operator could not learn the pipeline had
four parts until after they had paid for one. `app/tests/run-panel.spec.ts` demonstrated the gap in
its own body: it had to click a run row before it could assert the four titles.

The heads and the notes now always draw; the CONTROLS stay behind a picked run, **absent rather
than disabled** — the discipline the money gate already keeps, for the reason `.run-button`'s
comment gives: a disabled button is one attribute away from being pressable. One sentence above the
three says which state you are in. The panel gained the column when the box left it (D38), and this
is what it does with it.

**Three defects were fixed alongside, all reachable before and none of them cosmetic.** `stepOut`,
`decisions` and `decisionsBad` were never cleared when the open run changed — so run A's answer
rendered under run B, and `saveDecisions` posts the textarea to whatever `openRun` is at the moment
of the press, which could write A's edited `decisions.json` into B. A step's answer now renders
inside the step that produced it and is matched on **the step the click requested, never the
server's echo**; the spec mocks all three routes and returns `step: 'join'` for every one, which
was harmless only while the answer rendered unconditionally. And the run list is re-read on a
timer — 4s while anything is live, 20s otherwise — because a run started in a TERMINAL begins live,
so a poll gated on "something is live" could never discover the one case this route exists for.
A live run says how long it has been running, from its own `created_at`: `identify/batch.py` logs
only when the batch's status CHANGES, so a console tail written forty minutes ago is
indistinguishable from a hang. Elapsed is measured, not estimated — there is no per-card signal on
the wire and **no progress bar is invented**.

**Every command's stdout is shown verbatim and nothing summarises one**, which is
`docs/DESIGN.md`'s copy rule for the owner's screens. The one thing the panel adds on top is the
download link for a file the console can only name — the gap `docs/GATES.md` records as what
Gate B did not close: *"emit's import files existed only as filenames in terminal output the
owner never sees when someone else drives the commands."*

**`decisions.json` is edited as text, not as a form.** The route says in its own comment that it
does not validate what a disposition MEANS — `emit` owns that refusal — and a typed form would
encode the schema a second time in TypeScript, where nothing audits it against
`pipeline/decisions.py`. The file already explains itself: `join` writes a `_note` block naming
every field and what `emit` will refuse without.

**`--force-resubmit` is deliberately not offered to a screen.** It is the one identify flag whose
purpose is to pay again for an answer already bought, and D32's known cache gap means a re-crop
cannot be distinguished from a re-run by the cache. It stays a terminal flag until the crop is
part of the cache identity.

---

## D34 — A listing hold is released against the releasing box's own copies

**BUILT 2026-08-24, and it was found by a box that could not be deleted.** The owner asked why
box 1 — the 53 Gate B cards — refused `box_not_empty_of_commitments` when nothing in it had
been sold or retired. It was held by 45 listing records carrying **53 staged copies and one
live**, written by run `2026-08-22-box1-03`, whose `reconcile.txt` records a real Export From
Staged confirming the import had landed on TCGplayer. The rows had long since been cleared
there. The store had no way to know that, and no way to be told.

**THE GATE HAD TWO GROUNDS AND ONE DOOR.** A box held open by a sold or retired card can be
freed: both states reverse on their own routes, and the refusal names them. A box held open by
a LISTING could not be, ever. `staged` is written by `reconcile` and drawn down in exactly one
place — `cli/cmd_join.py`, by the **rise** in live quantity a fresh Filtered Export reports.
That is the right answer for an import that lands: the copies move to live and the staged count
follows them down. It has no answer at all for an import that does not. A staged row deleted on
TCGplayer never becomes live, so live never rises, so the drawdown never runs. The count stands
forever and the box is permanently undeletable.

`store/master.py:staged_stale` has named exactly this case since D7's amendment — its own
docstring calls it *"the import nobody finished"* — and until now **nothing anywhere could act
on the warning**. A diagnostic with no remedy is the shape of this defect.

**THE RELEASE IS BUDGETED BY THE CALLING BOX'S UNSOLD COPIES. It never zeroes a SKU outright,
and this is the owner's ruling of 2026-08-24 overruling the first build.** That build zeroed
the record, on the argument that *"TCGplayer holds nothing for this SKU"* is a claim about
TCGplayer and therefore cannot be scoped to a box. The owner overruled it, and the replacement
reason is better than the argument it replaced:

> **A release reached from box 1 must never be able to give up commitments that only box 3's
> copies could account for.**

A budget makes that impossible structurally rather than unlikely by care. Each SKU gives up at
most the number of unsold copies the calling box holds; `pipeline` and `store` are untouched by
the distinction because `Listing.release(budget)` is where it lives.

**THE REMAINDER IS DELIBERATE, AND CONFIRMED BY THE OWNER: *"Yes I would like a remainder to
exist, that's as planned."*** Where a SKU is shared, what is left keeps `_listing_hold`
non-empty, so **the box stays refused after a release that did exactly what it said**. That is
the honest state — TCGplayer really is still holding copies of a SKU this box has copies of, and
D7 makes every copy equally a candidate for being one of them. It is not a failure of the route,
and the screen's job is to say so before the press rather than let it read as a broken gate.

**LEAST-COMMITTED FIRST: `pushed`, then `staged`, then `live`, against one shared budget.** Not
`budget` from each stage — two departing cards cannot account for two staged *and* two live
copies, and per-stage decrements would give up four commitments for two cards. Which stage a
given copy actually backs is unknowable by construction (D7: the backing is deliberately
unrecorded), so the order is a rule rather than a lookup, and it is the conservative one:
`pushed` is a row in a file that may never have been imported, `staged` is a row TCGplayer
confirmed, `live` is a card actually for sale. Being wrong about `live` costs the most, so it is
surrendered last.

**A SOLD OR RETIRED COPY DOES NOT COUNT TOWARD THE BUDGET.** It has already left — a sale
decrements `live` where it can — and it is not one of the copies a remaining commitment could be
backed by. It is also what the operator counts when they look in the box, which is the number
they will check the screen against. Such a box is refused by the sold clause anyway, so this
opens no new dead end.

**`staged_at` clears only where `staged` reaches zero.** `Listing.set` stamps it as
`staged_at or at`, so a record released to zero and later re-staged would otherwise carry the old
date forward and read as stale on the day it was staged — a warning firing on success. A record
with copies REMAINING keeps its stamp, because those copies really have been staged since that
date and are exactly what the warning exists to find.

**The record survives at zeros rather than being popped**, because `_listing_hold` already reads
all-zeros as not held.

**IT ASSERTS RATHER THAN MEASURES, AND THAT DECIDES THE REST.** D8 and D11 put the authority
over these numbers in the export, and **no export this pipeline reads can say "nothing is
staged"**: a Filtered Export reports live quantity, and an Export From Staged lists the rows that
*are* there, so absence from it is unbounded — a SKU can be missing because it was never staged.
The only party who can state that TCGplayer holds nothing is the operator looking at TCGplayer.
A route whose entire content is a human's claim owes three things:

- **`confirm: true`, required.** D33's field one register down. That route refuses without it
  because the next thing that happens costs money; this one refuses because the next thing that
  happens is a fact being recorded on somebody's word.
- **A history line, always.** `listings_released`, box-level like `box_deleted`, carrying the
  box, the SKU count, the copies given up **and `still_held`**. The last is the half a later
  reader cannot re-derive: without it the log would say a release happened and not that it was
  partial. After the write there is no other evidence the counts ever stood.
- **The plan, ahead of the press.** `GET /boxes/<box>/listings` — free, read-only, creating
  nothing.

**TWO ROUTES, AND THE FREE ONE COMES FIRST — D33's PREFLIGHT SHAPE, AND THE OWNER ASKED FOR IT
BY NAME.** The first build reported the blast radius in the *receipt*: honest, and after the
write. An operator releasing from box 1's header learned box 3 was involved once it was already
done. The preflight names every SKU, its copy count, what it would give up, what it would keep,
which other boxes hold copies, and **`frees_box`** — whether the box would actually become
deletable. `server/capture_server.py:_release_plan` is the single source for both routes, and it
simulates by copying the record and calling `Listing.release` itself, so the preview cannot drift
from the write even if the ordering rule changes.

**The screen fetches the plan on opening the panel, and the control that releases does not exist
until it has answered** — absent, not disabled, `docs/DESIGN.md`'s rule for the run panel's spend
button applied for the same reason. No extra press: the fetch runs on open.

**IT REACHES NO OTHER GROUND OF THE REFUSAL.** A sold or retired card still holds its box open
after every listing in it is released, because those are departures recorded in the store and
this route says nothing about a departure. T7 asserts the refusal survives.

**ONE PRESS ON THE SCREEN, WHERE THE WHOLE-BOX DELETE TAKES TWO.** That delete used to demand
the box number TYPED, on the grounds that its risk is destroying box 9 while looking at box 95
and a gesture that cannot be performed by momentum answers that; the owner traded the typing for
a second naming press on 2026-08-26 (D20, amended). The contrast survives and is smaller: this
control's risk is a claim that turns out to be wrong, and neither typing digits nor pressing
twice makes anyone go and look at TCGplayer. The plan above the button is the gate here —
numbers a person can actually check. Nothing is destroyed either way: a wrongly released count
is re-established by staging again.

**Each press is its own assertion, and the cap is per press.** Releasing twice spends the budget
twice; the route keeps no memory of what a box has released before. That follows from the budget
being a statement about the copies in front of you rather than a quota.

**`GET /boxes` NOW REPORTS `retired` AND `listed` BESIDE `sold`.** Counted in the walk `_box_row`
was already running. Without them a screen could say a box has commitments and never which kind,
and the three kinds have three different remedies — so the delete panel recited the rule and the
operator learned which clause applied by pressing an irreversible button and reading the error.

**What would reopen this: a staged quantity the pipeline can read.** If `reconcile` were ever
pointed at a *fresh* Export From Staged and allowed to set `staged` absolutely — absence meaning
zero — the release would stop being the only way to clear a stale count, and the honest thing
would be to prefer the measurement over the claim. That is a change to `cli/cmd_reconcile.py`'s
contract (it currently moves `pushed → staged` and reads no absence), not a change to this entry,
and it has not been argued.

---

## D35 — A number that cannot be read falls back to the name, and the card still faces a human

**BUILT 2026-08-24, and it was found by the owner asking why the review queue was full of
cards they did not think needed reviewing.** It held 46 entries, every one `no_catalog_row`,
every one with **zero candidate rows** — so they could not be answered at all, only skipped:
`POST /review/<box>/<index>/answer` refuses an entry with no candidates as `no_candidates`.

**The gap was one line, and its comment stated the false assumption outright.**
`pipeline/join.py`'s Pokemon lookup fell back, when a card carried no number,
to `catalog.rows_for_blank_number_name` — an index of **only those export rows whose own
`Number` cell is blank**. Its comment: *"No collector number on the product (code cards, some
promos). These are exactly the rows whose `Number` is blank."* That reads `card.number is
None` as a fact about the PRODUCT when it is a fact about the READ. The two coincide only
while the photograph is good.

Box 2's 544 cards were cropped by a pad that cut the collector number off the bottom of the
frame (fixed in `d431afb`, ~35 minutes after that run was submitted). 37 came back with no
number at all and 9 with a **National Pokedex number read off the artwork strip** — `0326`,
`0342`, `0934`, `721`. Every one landed on that fallback, found nothing, and queued as
`no_catalog_row` against an export that held its row the whole time and had already matched
that row for other copies in the same run.

**Measured against that run's own export, matching by name inside the declared set: 47 cards
carried an unusable number (38 blank, 9 Pokedex-style misreads); ONE of them — `2/7`,
`Stonjourner` — has since been deleted from the box, so 46 reach the rung and 45 OF THE 46
RESOLVE TO EXACTLY ONE CARD, WITH ZERO AMBIGUOUS.** The one that does not is a Mega Signal
misread as `Mewtwo ex 009/102` — name and number both wrong, so nothing can rescue it, and it
correctly stays `no_catalog_row`.

**Those are the counts on disk today, and the arithmetic was re-checked on 2026-08-25 rather
than carried forward.** This entry was written before D36's realign existed and read "46 of the
47"; the deleted card was still being counted. `inventory/parked.json` holds 45
`number_unread_name_matched` entries and `inventory/review.json` the single zero-candidate
`no_catalog_row` — which is the run this paragraph is about, as it actually stands.

**THE NAME IS THE MORE RELIABLE FIELD, WHICH IS THE ARGUMENT FOR THE WHOLE RUNG.** T1's
recorded misses are `051/197` for `031/197` and `271/167` for `211/167` — confident answers,
**name right, digits wrong**. `docs/GATES.md` says no confidence threshold fires on those. The
same shape produced all nine of box 2's wrong numbers. A rung that trusts the name when the
number finds nothing is not a weaker check; it is the check aimed at the field that survives.

**IT FIRES ONLY ON AN EMPTY RESULT, AND BOTH EMPTINESS CASES COUNT.** A number that matches
rows is never second-guessed. What was nearly missed is the second case: four of box 2's
misreads carried a denominator too, so they composed a well-formed key that matched nothing
and stopped there — so an empty NUMBER lookup falls through as well as a missing one. It
cannot mislist anything, because it is reached only when the card was bound for
`no_catalog_row` regardless, and what it produces is a queue entry rather than a listing.

**`CLAUDE.md`'s HARD RULE IS NARROWED, NOT REPEALED**, and this paragraph is the narrowing.
That file says *"Never join on Product Name — it inconsistently embeds numbers."* It is right,
and the inconsistency is live in the owner's own data: box 2's export writes `Delibird -
105/132` and `Nickit` in the same column, and the first pass at the measurement above matched
raw names and scored 35 of 46 instead of 46 of 47. So: **never as the primary key; permitted
as a last resort that fires only when the number key finds nothing; folded on both sides by
`join.name_index_key`, which strips a trailing ` - <n>/<total>` and the case; and never able to
list a card on its own.** `name_index_key` is `number_index_key`'s twin and exists for the same
reason — two sources spell one identity differently and neither is wrong.

**A CARD FOUND THIS WAY IS QUEUED, NEVER LISTED, AND THAT IS THE OWNER'S RULING.** Listing was
offered and declined. Their words: *"I should be able to bulk clear them when the scenario is
such that I have claimed that they're all a certain set that you have an excel for and that you
have exact name matches."* The field that tells one card from another is precisely the field
that could not be read, so the last check is a person looking at the photograph.

**IT COSTS ONE PRESS, NOT ONE PER CARD, AND THAT IS WHY QUEUING IS AFFORDABLE.** Every entry
from this rung carries **one** candidate — the row the ladder chose — under **one** shared
reason, and a uniform stack gives **one** shared condition string. That is exactly D29's
group-answer eligibility, so box 2's 45 are one `G`, one Enter, and one `U` to reverse, over a
grid of their photographs. No new screen and no new route: `routing.NUMBER_UNREAD_NAME_MATCHED`
plus a label was the whole client change.

**The lookup string says `name?:` and not `name:`.** A row found because the product prints no
number and a row found because we could not read one are different facts with different
remedies, and both are printed on the RUN REPORT (D16 — the machine string stays greppable).

**It does NOT reach the queue entry, and this entry claimed it did until 2026-08-25.**
`store/queues.py:QueueEntry` has no `lookup` field and `Queue.parse` drops unknown keys, so the
string lives only in `JoinReport`'s output. The consequence is worth naming rather than
papering over: a name-inferred card that does NOT resolve cleanly — `set_ambiguous`, or any
ladder review reason — never reaches the block that stamps `number_unread_name_matched`, so its
queue entry carries an ordinary reason with nothing recording that the row set was reached by
name at all. The review screen draws its "matched by name" sentence off that reason code alone,
so such a card is indistinguishable on screen from one whose number read fine. Carrying the
lookup onto `QueueEntry` is the fix, and it is a schema change nobody has argued for yet.

**What would reopen this: a name that resolves to two cards in one set.** Measured at zero
across box 2, but a set with two prints of one name would produce it. The behaviour is already
correct — two surviving rows means two candidates and an ordinary one-card review — but it has
never been seen, and the group offer would correctly refuse it as `group_not_uniform`.

**IT WAS A RULE ABOUT POKEMON'S LOOKUP UNTIL 2026-08-29, AND IT WAS WRITTEN AS A RULE ABOUT A
READ.** This entry argues throughout that the NUMBER is the field that fails and the NAME is
the field that survives — a claim about photographs and models, with nothing game-specific in
it. It was nevertheless implemented in the Pokemon lookup alone, so every game
keyed by a printed identifier (`riftbound`, `one_piece`) returned an empty row set and stopped
where Pokemon fell through to the name.

**The owner found it from the far end**, asking why cards whose rows are plainly in the export
were sitting in the review queue as unanswerable. Run `2026-08-29-box1-01`, 133 real Riftbound
cards: **4 unusable reads, all 4 zero-candidate `no_catalog_row`** — and a zero-candidate entry
is refused by `POST /review/<box>/<index>/answer` as `no_candidates`, so those cards could not
be answered at all, only skipped, every session, forever. Three carried a set-code prefix the
Riftbound prompt forbids in as many words (`UNL • 140/219` for `140/219`, twice with a bullet
and once with a middot — a model slip at 3 of 133, not a prompt gap), and **all three hold
exactly one row by name**. One of them, `Hwei, Brooding Painter` at **$2.86**, is above D9's
threshold: a listable card stuck unanswerable. The fourth read `Wuju Master` for the export's
`Master Yi, Wuju Master` and correctly stays unmatched — the name it gave is not the name the
export carries, so nothing can rescue it.

**Nothing about the rung is widened by this.** It still fires only on an empty result, so it is
reached only by a card already bound for `no_catalog_row`; it still produces a queue entry and
never a listing; it still answers `name?:` rather than `name:`. What changed is which strategies
run it. `name_only` deliberately does NOT gain it: there the name IS the key, so there is
no unreadable number to fall back from.

**THE REAL FINDING WAS THE SHAPE, AND IT IS FIXED — the owner's ruling, same day.** Each game
had its own `_lookup_*` function, and each re-implemented the same four-step ladder — build a
key, look it up, try the blank-`Number` name, fall back to the name — differing only in STEP
ONE, the only genuinely per-game part. D35 landed in one copy and nothing compared them, because
nothing could: they were three unrelated functions that happened to be parallel.

`pipeline/join.py:_walk` is now the ladder, written once, and `KeyStrategy` is the per-game part
as a VALUE — a key builder, the lookup label, and whether D35's rung applies. **A rung added to
`_walk` cannot land in one game and not another**, which is the property the old shape could not
offer at any level of care.

**THE OWNER ASKED WHETHER THE EXPORTS DIFFER PER GAME, AND THEY DO NOT.** Measured across all
four committed fixtures — SV09, the wide Pokemon export, Riftbound and One Piece — the 16-column
header is **byte-identical** (one md5 between them), which is what makes a shared ladder correct
rather than merely tidy. What is genuinely per-game is the `Product Line` cell, the rarity
vocabulary, the shape of the `Number` cells, and one import file per game (D25) — none of which
lives below step one.

**`name_only` KEEPS ITS EXEMPTION, AND IT IS NOT COMPATIBILITY DEBT.** `pokemon_code` has no
collector number at all and lives inside the Pokemon export as a blank-`Number` row, so
`rows_for_name` would match it to the NUMBERED card of the same name — a code card listed as the
card it came with. The rung is for "we could not READ the number"; a product that prints none has
nothing to fall back from. That is now a declared `name_rung=False` rather than an absence
somebody has to notice.

**Behaviour-preserving, and checked as such rather than asserted.** `join --dry-run` over both
real runs — box 1's 133 Riftbound cards and box 2's 544 Pokemon cards — produced **byte-identical
output** before and after the restructure.

Covered by T3 in both directions, observed failing against the old code first.

---

## D36 — The run says what the model read; the store says which slot it is in

**BUILT 2026-08-24, immediately after D35, because applying D35 exposed it.** A re-join of box
2 wrote all 47 queue entries **one position off** — every entry carrying the right read with its
neighbour's slot, photograph and label. On screen: `Wally's Compassion` described over a
photograph of an Inteleon. It was caught before it was answered; the queue was restored from a
backup taken minutes earlier.

**Nothing about D35 caused it. Any re-join of that run would have done the same.**

**THE TWO HALVES ARE EACH CORRECT AND THE SEAM BETWEEN THEM WAS NOT.** `cli/runs.py` makes a run
an immutable input on purpose: it is what lets a Batch outlive the server that started it (D33)
and what makes a run an auditable record of what was submitted and billed. D10 ruling 1 lets a
junk capture be deleted from the middle of a box, sliding every higher card down one slot, and
the store does that completely — records, photographs, sidecars and **both queue files** are
remapped and a `renumbered` event maps every old index to its new one. Neither is wrong. What
was wrong is that the run's POSITIONS were then read as truth.

Box 2: card `2/7` was deleted, 537 cards shifted down one, and the run directory — correctly
unable to be rewritten — still described the box as it had been.

**The owner's reading is the one this is built to, and it is a better diagnosis than the three
options they were offered:**

> *"It should've gone away and autocorrected all the others too... I don't see how these could've
> been disconnected."*

**SO THE RUN NO LONGER OWNS THE SLOT NUMBER.** It owns what the model read from a PHOTOGRAPH;
the store owns which slot that photograph is in. `photo_sha256` is the join between them, it is
on every run record whose photograph could be read, and it is the only binding that survives a
renumber (a record whose photograph raised an `ImageError` carries `None`, which is the
digest-less case below) — a slot number
is exactly what moved. `cli/resolve.py:realign` runs before anything reads a position out of the
payload, and the run directory on disk is never touched.

**Measured before it was chosen**: box 2's 543 photographs are 997 MB and hash in **0.56s**, to
543 distinct digests with no collisions. Reading the photographs is affordable per join and is
strictly better than trusting the store's identification cache, which is another derived copy a
future defect could leave stale in the same way.

**FIVE OUTCOMES, REASONED PER BOX, AND THE PER-BOX PART IS NOT A DETAIL.** The first draft
reasoned over the whole run and declared **all 53 of box 1's cards departed** — because box 1's
photographs have been deleted from disk while its records live on. That inverts the check:
absence of photographs is absence of evidence, not evidence of absent cards.

- **moved** — the digest is on disk at a different slot. Re-bound, and named in the report.
- **departed** — the digest is on no photograph in a box whose *other* photographs are present.
  The card has left: deleted mid-box or retired. Skipped, because there is nothing to join it
  to, and **named** — `CLAUDE.md` forbids dropping a card silently, not dropping one at all.
- **ambiguous** — the digest is on two photographs. That is a question, not a slot, and guessing
  an identity is forbidden. Refuses the whole run.
- **collided** — two RECORDS carry one digest, so they re-bind to one slot. **Added 2026-08-25,
  and it is `ambiguous`'s missing twin**: that outcome checks the DISK for a digest appearing
  twice, and nothing checked the PAYLOAD. Two records landing on one key overwrote each other in
  the rebuilt payload — measured at two cards in and one card out, with `departed` empty and
  nothing printed. A silent drop inside the function written to prevent one. Refuses the whole
  run and names the contested slot.
- **unverified** — the box offers nothing to check against: no photographs on disk, no record
  carrying a digest, or no digest that matches any photograph there. Its records pass through
  exactly as the run recorded them, and the report says the slots were **not** checked, so an
  unchecked box cannot read as a verified one. The third case is why this is stated as "nothing
  to check against" rather than "no photographs": a box whose photographs have all been REPLACED
  (D26's re-shoot writes new bytes at the same slot) matches none of the run's digests, and
  calling its cards departed would be the same inversion the paragraph above refuses.

**A RECORD WITH NO DIGEST IS THE FIFTH THING THAT CAN REFUSE, and it is not an outcome of a
box.** `cli/cmd_identify.py` writes `photo_sha256` as `None` for any card whose photograph
raised an `ImageError`, so a run written today can carry digest-less records — this is live, not
merely a guard against payloads older than the field. Such a record is harmless while nothing in
its box has moved and unplaceable once something has, so it refuses only in the second case.

**A healthy run returns the identical payload object**, which is what keeps its join
byte-for-byte unchanged — verified against Gate B's box-1 run, which diffs clean.

**What would reopen this: a second binding that outlives a renumber.** `capture_id` is on the
card record but not on the run record; if it were carried into the run payload it would be a
cheaper key than hashing a gigabyte, and hashing could become the fallback rather than the
primary. That is a change to what `identify` writes, not to this entry.

---

## D37 — A queued question can be closed without answering it, and the card is left alone

**BUILT 2026-08-25, and it settles a question this repo has carried open since the review
screen was built.** `docs/DESIGN.md` has said, in writing, for as long as Skip has existed:

> **Skip is an OPEN QUESTION, not a decision.** … If nothing is ever skipped, delete the
> control. If most of a queue is, the screen needs a real defer that records a reason, and
> that is a decision entry rather than a button.

The owner pulled that trigger: *"why can't i mark something as known skip kinda like a stand
down on the flag i get that this is a wasted position etc ? from the review window itself"*.

**THERE WERE TWO WAYS PAST A CARD AND BOTH WERE WRONG FOR THIS.** An answer writes a SKU onto
a real card, which the operator must not do to a card they cannot identify — `CLAUDE.md`'s
hard rule is that ambiguity goes to the queue rather than being guessed. Skip writes nothing
at all and a reload forgets it, so a card that will never be answerable comes back every
session, forever. Between "invent an identification" and "be asked again tomorrow" there was
no third move.

**THE THIRD MOVE IS ONE FLAG, AND THE FLAG ALREADY EXISTED.** `store/queues.py` was built
around `cleared_by_human`: `Queue.upsert` refuses to re-queue a cleared position,
`Queue.release` refuses to drop one, `open_entries` hides it. The machinery for "stop asking,
and keep not asking across every future run" predates the review screen. The only thing that
could ever SET it was an answer — and an answer costs a SKU. `POST /review/<box>/<index>/
stand-down` sets the same flag with a reason and nothing else.

**IT IS A THIRD THING, NOT A SOFTER RETIREMENT, AND THE BOUNDARY IS THE ENTRY:**

- an **answer** (D4) writes `sku` and `condition`. The pipeline is told what the card IS, and
  every later join reads it back as rung 0.
- a **retirement** (D26) writes a terminal state. The CARD left inventory; the record stays
  and the gap is permanent.
- a **stand-down** writes nothing to the card at all. It does not move, change, or leave. It
  keeps its slot, its photograph and its place in the box walk, and stays sellable if it is
  ever identified properly. What closes is the QUESTION.

**ITS OWN THREE REASONS RATHER THAN `master.RETIRE_REASONS`.** Those four — `pulled`,
`damaged`, `lost`, `given_away` — all say the card is gone, and borrowing them would make
"stop asking me" indexable as "this card has left", which is the one thing it must never
mean. `queues.STAND_DOWN_REASONS` is `wasted_position | cannot_settle | not_listing`,
hand-authored in D22's sense and rendered verbatim beneath its human label the way every
reason code on that screen is.

**THE REASON IS REQUIRED, AND IT IS THE INSTRUMENT `docs/DESIGN.md` SAYS WAS NEVER READ.**
That file records Gate B's mistake by name: the run produced a real queue, the owner answered
all of it, and *nothing counted how many were skipped first* — so the control stayed exactly
as unsettled as it began. A stand-down without a reason would repeat that. With one, the log
can finally answer which questions get waved off and why, beside `queue_reason`, the queue's
own reason for asking.

**THE CANONICAL CASE IS REAL AND WAS FOUND THE SAME DAY.** Box 2 position 95 holds a
photograph whose mean luma is **1.7 out of 255** — a black frame, captured at 3120x4160 where
every other card in the box is 2160x3840. Haiku was shown nothing and returned `Mewtwo ex
009/102` at HIGH confidence; it matched no row, so it queued as `no_catalog_row` with zero
candidates, which `POST /review/.../answer` refuses outright as `no_candidates`. That card
could not be answered, could not be usefully re-shot, and came back every single session.
That is `wasted_position`, and it is what this entry is for.

**THE REVERSAL REFUSES AN ANSWERED CARD, WHICH IS THE GUARD WORTH NAMING.** Both directions
sit on one path (D28's shape, and `do_mark_sold`'s reason: a reversal reachable without going
through the thing it reverses is a route a stale client finds on its own). Reopening a queue
entry is the same store operation either way, so `_clearing_event` reads the log to learn
which event closed the question and refuses `not_stood_down` when it was an ANSWER — taking
back a real identification through the un-dismiss control is the one thing this route may not
do. It inherits `_answer_before`'s `renumbered` hard stop for D10 ruling 1's reason: a
clearing line older than a mid-box shift belongs to the slot's previous occupant.

**NO LISTING HOLD IS CONSULTED, in either direction.** `undo_too_late` asks whether a SKU
this Mac wrote is already out in an import file. A stand-down writes no SKU, changes no SKU
and moves no listing count, so nothing downstream can disagree with it.

**THE SCREEN OFFERS RETIREMENT BESIDE IT, AND DELETE DELIBERATELY NOT.** Both were asked for
in the same breath. `POST /inventory/<box>/<index>/retire` already existed and already had a
client function; what it lacked was a control on the screen the card is actually on, which is
`CLAUDE.md`'s route-is-not-a-feature rule in its mildest form. **The mid-box delete stays on
`#/inventory`** for two reasons that are about this screen rather than about the operation:
it slides every card behind it down one slot, so pressing it from a worklist would renumber
the very positions that worklist is drawn from — the defect D36 was written to stop, invited
back in by hand — and it is the one operation here with no undo at all. The panel says so on
screen rather than leaving someone to hunt for it.

**ONE PANEL, KEYED, BECAUSE THE DIFFERENCE IS THE HARD PART.** The owner's confusion was not
about where the buttons are; it was that these are three different acts with three different
costs, which no button label conveys alone. `X` raises a panel that names what each one does
to the card, and it owns the keyboard while it is up for the group offer's reason — its
choices are keyed on digits that mean candidates everywhere else on that screen.

**What would reopen this: the reason counts.** If `wasted_position` dominates, the fix is
upstream — a capture that can produce a black frame at a different resolution than the rest
of its box is a rig fault, not a queue fault, and no amount of dismissing is the remedy for
it. That is the measurement `docs/DESIGN.md` has been asking for since Gate B, and this route
is what finally takes it.

---

## D38 — The photograph is sized by the rows beside it, and the box and the runs get the third column

**BUILT 2026-08-25.** `#/inventory` drew two columns — the box walk, and one 1004px column holding
everything else stacked: the card detail, then the copies, then `BoxOps` and the run panel side by
side.

**Measured at 1440x900, on box 2 card 1 with its six copies, the body went 1878px -> 1396px**, and
the photograph **420x587 -> 150x204**. Both are off the running store through one instrument: the
old arrangement was rebuilt in the live DOM, measured, and reloaded away. The saving is
data-dependent — most of what remains is the copies list, where a `position-bar` takes a line of
its own by rule — so read 482px as this card, not as every card.

**THE PHOTOGRAPH WAS SIZED AGAINST THE WRONG SCREEN, AND THAT IS THE FINDING.** D33's build gave
it a `minmax(280px, 420px)` track on 2026-08-24, arguing that 280px was small because the review
queue gives the same job 415x736. The two screens do not have the same job. The review queue is
where a card is JUDGED — `docs/DESIGN.md` spends a section on making the photograph the largest
thing on it, because the question is whether the foil matches the toggle. This screen's question
is *where is this card*, and its photograph confirms you are looking at the right slot. Borrowing
a floor from a screen with a different job is the same mistake that file names when it refuses to
draw the Fulfiller's minimums on the owner's screens.

**So the photograph is sized by the seven fact rows beside it** (the owner: *"shrink the preview
image ... to now be in line with the rows going from card to finish, those should all occupy the
same vertical space"*). `.browse-facts` measures 203.5px, and 63:88 at that height is 145.7px
wide — a 150px track, down from 420.

**IT TOOK ITS HEIGHT FROM THE FACTS FOR A FEW HOURS AND IS SIZED BY ITS COLUMN AGAIN**, and the
middle step is what made the right size findable. Pinned to the rows the photograph was 150x204;
the owner then asked for it back — *"more space given to the middle (ie photo gets larger)"* —
which reads as a contradiction and is not. The two are only in conflict while the facts are as
wide as they were, and they are not: `Captured` printed a full ISO stamp at ~234px and now reads
`6:35pm · Aug 23` at ~100px, so the widest value on the card is the card's own NAME and the facts
want ~270px instead of ~426px. The photograph takes the width that frees. `CardOps` moves up
beside the facts to fill the air under them, and the re-shoot control becomes a 24px icon with its
words on `aria-label` rather than a full-width button in the photograph's own column.

**THE FRAME WENT WITH IT, AND THAT DELETED A CLASS OF DEFECT RATHER THAN AN INSTANCE.** While the
photograph took its height from the facts, the reservation had to live on a WRAPPER — and a
wrapper holds whatever `PhotoPanel` returns, so a card whose file was missing got a card-shaped
box drawn around a paragraph (measured: 424x592 around 424x149, with the re-shoot control pushed
to y=985 of a 900px viewport). `aspect-ratio` is back on the `<img>`, where it cannot reach
anything that is not an image. **Moving a reservation off the thing it describes and onto a
wrapper gives it to everything else that wrapper can hold** — that is the lesson, and it is why
`align-self: stretch`, `.browse-frame` and a `:not(.is-absent)` media rule are all gone.

**`object-fit: cover` STAYS, against the obvious objection.** The frame is no longer guaranteed
63:88, so `cover` crops by a variable amount and `contain` looks like the honest answer. It is not:
D32 measured these frames at 2160x3840 with the card filling 80–88% of the width and 61–72% of the
height, so `contain` would letterbox a frame narrower than its box and shrink the card inside an
already small photo. `cover` crops the desk off the top and bottom, which is the crop you want.

**THE ~270px THE PHOTOGRAPH GAVE UP IS THE THIRD COLUMN**, and that is the trade rather than a
consequence. `BoxOps` and the run panel move out of the card's column into one of their own —
which rewrites the last line of D33: the row cost the card's column one panel's height, and the
column costs it nothing. Nothing folds. The copies list moves to a full-width row beneath the band,
where D33's argument for keeping it in the facts column (a 587px photograph would push it off a
900px viewport) is void.

**"THE COLUMN COSTS IT NOTHING" WAS TRUE ABOUT WIDTH AND FALSE ABOUT HEIGHT, AND THE THIRD COLUMN
IS GONE (owner, 2026-08-26: *"solve the dead pixel space in inventory between the card and its
details, and then the location data that scrolls away after whitespace"*).** This paragraph
checked one axis. A grid row is as tall as its tallest cell, and the card and the run panel shared
row 1 while the copies were row 2 — so the copies began wherever the console ended. Measured on
the owner's store, box 2:

    console closed             799px  ->  copies at y=938,  378px of white,  page 1552
    console with a run PICKED  1461px ->  copies at y=1599, 1039px of white, page 2214

Picking a run is an ordinary act and the panel polls its own list on a 4s/20s timer, so the second
row is a resting state — which means the answer to *where is this card* was positioned by
something that is not about the card, at a height with no cap. A fix that closed 378px would have
closed the best case only.

`.browse-body` is now two columns and three rows: the walk, then the card, the copies and the
console stacked in the content column. **The console pays for its own move** — widened from 370px
to 1024px it draws 625px closed and 1143px open with no code change at all, because its head stops
wrapping four command names and its notes and free steps unwrap with it. **What this entry got
right and the rebuild keeps**: the box belongs in the walk's column, the runs are not the card's
neighbour, and nothing folds.

**What it costs, stated because it is the whole price**: `Check cost` was at viewport y=495 and is
now a page down, below the copies. Identifying is done once per box; the copies answer the
per-card question this route was merged to ask. If that trade is ever wrong the fix is to swap the
last two rows, **never to restore the column** — the column is the mechanism.

**THEN THE BOX LEFT THAT COLUMN AGAIN, AND THE SECOND MOVE IS THE ONE WORTH READING** (owner,
same day): *"merge its functionality (so not visual merge, but rebuild type merge) and all exist
on the left side"*. The evidence was a duplication nobody had counted: `BoxOps` drew `Section 1
#1–#85  85 cards` as inert text for every divider, while `.browse-secthead` in the walk drew the
same five rows — foldable, tickable, walkable — a thousand pixels to the left. **The walk IS the
sections list.** That is D31's own finding one scale down, and it decides where the box goes: the
left column is the box (the strip picks it, the list is its cards), so the box's readings and its
operations belong there and the panel headed `Box 2` was the redundant instance.

`BoxIdentity` is split out of `BoxOps` for it — name, fill, state and the segment track, under the
strip that names the box. The operations stay in `BoxOps` and sit at the bottom of the walk. They
sat there *beside `RegisterBox`* until 2026-08-26, when the owner deleted that control from this
screen outright — nothing is lost by it, because `CaptureScreen.tsx:createOfferedBox` calls the
same `POST /boxes` from the Box field and makes the same empty box, which is where a person
reaching for a new drawer already is. The operations are now the last thing in the column. The
sections list, its
`Layout and controls` heading, and the `sections 1 86 171 253 394` clause of the meta line are all
**deleted rather than moved**: three renderings of one fact on one screen. The third column keeps
the runs alone and narrows to 370px, and the card takes the difference.

**A REAL DEFECT CAME WITH THAT MOVE AND IS FIXED HERE.** `.browse-map` is sticky and capped at the
viewport, so anything past the cap renders below the fold and the page scroll cannot bring it back
— a sticky element does not move. Harmless while the column held a search, a strip and a list;
not harmless once the box's editors moved in, where opening the claims editor on a 720px-tall
window put the Apply button permanently off-screen. The column scrolls itself now, and
`.browse-list` keeps a 6rem floor so an editor below it cannot squeeze the walk to nothing.
`app/tests/inventory.spec.ts` asserts the escape hatch rather than the button's position.

**THE DENSITY WAS TIGHTENED TO EARN THE NARROWER TRACK, at the owner's instruction** — *"there's a
lot of wasted space in the runs blurb and box blurb ... tighten its spacing / buttons to be more
efficient, and then allocate space accordingly."* Two cuts did nearly all of it:

- **`BoxOps` drew one row per section, with no bound at all.** The row is 25.5px, so N dividers
  cost 25.5N px and nothing stops it — the panel's height was a function of how finely a box
  happened to be divided, which is not a thing anyone chose. **Be honest about which half of this
  is measured**: box 2 declares five sections today and the list draws **127px**, so the cap saves
  nothing at the current layout. What earns it is the other end — D31 records **this same box at
  22 sections**, ~560px by that row height, more than the rest of the panel put together — and D10
  makes dividers freely editable from any screen, so that state is one edit away at all times.
  Capped at six rows and scrolled, with the section total already on the heading beside it so a
  capped list cannot read as a short one. Its row tracks narrow from 8rem/10rem to 5rem/7rem, which
  moves the panel's wrap cliff from ~399px to ~280px — the thing that actually decides how narrow
  the column may be.
- **The run panel drew four 20px display headings**, the same size as its own panel title, so an
  open run said the steps and the panel were the same rank. 14px body, matching what `BoxOps`
  gives the same job one panel down. Its buttons drop to 32px, which is `.boxops-plain`'s height —
  the two panels in this column disagreed about how tall a control is by 17%.

The column is then **`minmax(340px, 400px)`**, allocated after the cuts rather than before them.

**THREE COLUMNS ARE A >= 1240px LAYOUT and below it the pair goes back under the card.** 1240
rather than 1440: the owner works at 1440x900, and a breakpoint at exactly the working size is one
you cross by un-maximising a window. It also puts Playwright's 1280x720 inside the new layout, so
`make design-check` exercises the three columns rather than only the fallback.

**THE NUMBER SURVIVED THE COLUMNS (2026-08-26).** There is no three-column body any more and the
body has no breakpoint at all — one arrangement at every width, which deleted the `@media
(max-width: 1239px)` block and the two-rows-versus-three overlap hazard that block spends a
paragraph documenting. 1240 now governs the CARD BAND's third track, and the reason above transfers
without a word changed: Playwright's 1280 renders three tracks rather than only the fallback.

**FOUR THINGS THE CARD PANEL GAINED ON 2026-08-25, from a design consultation the owner asked
for and an adversarial pass over its proposals.** Recorded together because they are one finding
in four places: this panel had been drawn for the layout and not for what it must SAY.

- **`Rarity` and `Note` are on it, and `CardOps` could overwrite both without showing either.**
  `ClaimEditor` writes five claims and the list drew three — and it opens with those fields empty
  and reads armed-and-empty as a CLEAR, so `Correct claims` was a blind overwrite of two values
  that appeared nowhere on screen. `rarity_claim` is set on 543 of 543 records, so this was live.
  Rarity renders verbatim (D22: no second friendly vocabulary), through the same renderer as the
  finish claim so a second `' · '` join cannot drift from it.
- **`Run` and `Confidence`.** `run` is on all 543 records and is the join between this panel and
  the run panel one column right, which lists run directories and cannot say which cards each
  touched. `Confidence` is the only place a RESOLVED card's hedge is readable — `#/review` draws
  it only for a card that was queued. Shown FLAT, never as a chip or a colour: T1's and D35's
  recorded misses are all confident and wrong, so `high` is not reassurance. That is an argument
  about what the value means, not about whether to print it.
- **Whether the card has an open question, from `GET /queues`.** A card in the review queue
  rendered `State: identified` and nothing else — and `state` there is not merely silent, it is
  MISLEADING, because it describes how far capture and identify got while the question was raised
  by the JOIN. The candidate count is load-bearing: zero candidates is the difference between "go
  and answer it" and "it cannot be answered as it stands", which is what points at the re-shoot
  icon already on this panel. The label map moved to `app/src/reasons.ts` and is IMPORTED by both
  screens rather than copied — its own docstring says nothing keeps it in step with
  `pipeline/variant.py`, and the defence is making that drift visible, which a second copy would
  defeat. `scripts/docs-audit.py`'s reason-codes check follows it there.
- **The copies list spans the card's column AND the runs'.** Measured: in the middle column it was
  976px of a 1450px page on the default card and 1713px of 2187px on an eleven-copy one, while
  778px of viewport sat empty beside it. Wide, the row goes 144px to 82px and eleven copies go
  1598px to 902px — a 43% cut with nothing removed. That is `CardLocations.css`'s own recorded
  complaint answered rather than worked around, and it is keyed to a **container query** rather
  than a breakpoint because that file's promise is to be honest "with no breakpoint to keep in
  step". It also collapses `detail`'s two render sites into one, which turns the surviving-receipt
  invariant from a prose promise into a structural fact.

  **Amended 2026-08-26: the copies span the CONTENT COLUMN, which is the same width by another
  name.** With the third column gone they take 1024px at 1440 and 864px at 1280 — the exact widths
  they had spanning columns 2 and 3 — so every measurement above is untouched. The container query
  is what makes the width non-negotiable and it was re-measured on the way past: a row is 83px at
  >= 940px of container, 115px at 864, 127px at 860 and 159px at 630. **The 860 threshold is
  therefore mis-set** — it buys a 127px row, not the one-line 83px one — and it is left alone
  deliberately, because raising it to 940 without guaranteeing the container is that wide would
  drop 1280 from a 115px row to a 159px one. Recorded as the sharpest known defect in this area.

**The four new fact rows closed the band's air and slightly overshot**, which is worth recording
because a test had to change for it: the facts are now 415px against a 349px photograph, so the
~90px that sat under the facts is ~66px under the photograph instead. Which side is taller was
never the property worth guarding — it is an accident of how many rows the panel draws, and it has
now flipped once. What the assertion checks is that the two stay within a band of each other.

**What would reopen this: a photograph nobody can read.** The band is sized for confirming a slot,
not for judging a card. If the owner finds themselves opening the review queue to look at a card
they were already looking at here, the answer is not a bigger photo in this band — it is that this
screen has quietly acquired the other screen's job, and that is worth naming before it is resized.

**A TWELFTH ROW ARRIVED ON 2026-08-29 AND IT IS THE FIRST FACT ON THIS PANEL THAT IS NOT ON THE
RECORD.** The owner: *"if a join has happened on that set, can I get the TCG Market Price as part
of the data summary on the top right of the card (with a note of how stale/fresh that data is?)"*.

**THE STORE HOLDS NO PRICE, AND THAT IS D8 RATHER THAN A GAP.** Every figure in this product comes
out of the TCGplayer Filtered Export, and `store/master.py` has not one field shaped like money —
so *what is this card worth* was answerable on `#/pricing` and on no screen the operator is
actually standing at when they ask it. The eleven rows above are `asdict(card)`; this one is a
join.

**THE EDGE IS D46'S, REUSED RATHER THAN REBUILT: card -> `run` -> that run's `pricing.json`.**
`cli/cmd_join.py` writes that file on every join with each matched SKU's export row verbatim AND
every position holding a copy, so a position resolves to a SKU and to a Market cell with **no new
route, no new field on the wire and no schema change anywhere**. `GET /pipeline/runs/<name>/
pricing` is free, read-only and creates nothing, which is what makes it safe to open from a screen
that is not about running anything.

**KEYED BY POSITION AND NEVER BY `card.sku`, which is the one decision here that could be silently
wrong.** That field is written by `emit`, for SKUs that reached an import file — so a
sub-threshold card, a card withheld under D49, and every card in a run that was joined but never
emitted all carry `null`. A SKU-keyed lookup would draw nothing for all of them and would look
correct on the cards it happened to reach. The position is on both sides of the join and is
written by neither. `app/tests/inventory.spec.ts` prices a fixture card carrying `sku: null`,
which is the case that fails the wrong implementation.

**ONE READ PER RUN, CACHED BY RUN NAME.** `pricing.json` is per-run and every card in a box
normally names one run, so walking a whole box costs ONE read — the argument `queued` beside it
already makes, and it matters more here because a real table is ~80KB for 50 SKUs. Keyed by RUN
and not by box, because a run is what wrote the file: D33 scopes a run to a SELECTION inside a
box, so two cards on one shelf can carry two tables read at two different moments, which is
exactly the staleness this row exists to report.

**THE AGE IS NEVER OPTIONAL, AND `read` IS NEVER `as of`.** `join` is free, re-runnable and
routinely pointed at a refreshed export, so a bare `$5.47` claims a currency the file cannot
support. What the age measures is the JOIN: `GET .../pricing` answers `written_at`, the mtime of
`pricing.json`, because the export is a CSV the operator downloaded from TCGplayer at an earlier
moment nothing on this machine can see. The freshest honest sentence is when the pipeline last
looked at it, so the row reads `$0.34 · read 3 days ago`.

**THE MTIME RATHER THAN A `joined_at` INSIDE THE TABLE.** A field written into the file would be
better data and would be absent from every run already on disk — which is precisely the runs a
screen is opened over. The mtime needs no re-join and cannot drift from the bytes it describes.
What it does not survive is the run directory being copied; nothing in this repo copies one.
T7 backdates the file and requires the route to report the backdate, because asserting against
the live mtime is VACUOUS — the test joins immediately before the request, so a route stamping
`time.time()` answers the same integer. That version was written, mutated to a clock, and
**observed passing**.

**FIVE OUTCOMES, FIVE SENTENCES, AND THE ROW IS NEVER CONDITIONAL** — the rule `Rarity` and `Note`
above it already follow, for the reason stated there: a row that disappears leaves *this card has
no price* and *this screen does not show prices* indistinguishable. No run on the card is `not
joined yet`; a run with no table is `no pricing table — join this run`, which is the one refusal
worth telling apart because its remedy is a join rather than a look at the server; a position the
table does not hold is `no row matched by this run`, which is `no_catalog_row` and the review
queue's business rather than a missing price; and a **blank Market cell is `no_market_data`**,
verbatim and underscore and all, because it is `pipeline/routing.py`'s own `NO_MARKET_DATA` and
D9 is emphatic that a missing price is an UNKNOWN price rather than a low one. Rendering that as
`$0.00` is what hands a chase card away at the floor.

**The underscore is a ruling rather than an oversight.** Spelled `no market data` it is neither
the machine string nor a human label — the second vocabulary D22 refuses and D16 exists to catch
— and it greps to nothing on the day somebody holds this screen against `decisions.json`'s own
`no_market_data` block, which is where such a card is actually priced by hand. So the row splits:
**plain English where THIS SCREEN has nothing** (the shape every other fallback in this list
takes), and **the pipeline's own word where the PIPELINE said something**.

**A RELOAD RE-READS IT, AND LEAVING THAT OUT WAS A LIVE BUG found by pressing the button against
the real store.** The cache is cleared on the reload counter and the READ was keyed on the run
NAME alone, which does not change when a box is re-read — so the cleared entry was never
re-fetched and the row sat on `reading…` permanently. A clear and its re-read are one gesture and
must be triggered by the same thing. It matters more than an ordinary staleness bug would: Reload
is pressed *after* something downstream changed, and a join is the thing that rewrites a price.

**BENEATH `Run` AND ABOVE `Note`.** The same placement argument `Confidence` gets for sitting
under the read it hedges: the price is not a property of the card, it is what one join found in
one export, and the age beside it is that join's age — so provenance is a straight read-down
rather than two glances. Both rows would be inexplicable apart, since `Run` names a directory and
cannot say what it found, and a price with no run named is a number from nowhere.

**WHAT THIS DOES NOT DO: it does not put pricing on this screen.** No preset, no override, no
snap, nothing writable — `#/pricing` is where a price is DECIDED (D49) and this is where one is
READ, on the screen whose question is where a card is. The other four price columns, the
presets and `decisions.json` stay there. If this row starts growing controls, it has acquired
that screen's job, which is the failure the paragraph above already names for the photograph.

**What would reopen this: a box whose cards span many runs.** The one-read-per-run cache is sized
for the ordinary case of a box identified in one go; a box assembled from a dozen ticked
selections would fetch a dozen tables while the arrow keys walk it. The measurement is how many
distinct `run` values a single box's records carry — two today, across the whole store.

---

## D39 — The pipeline gets a route, and the selection is handed to it

**BUILT 2026-08-29, and it reverses D33's placement on the owner's instruction after a design
consultation they asked for.** The question put to that consultation was narrow — should the
runs panel stay on `#/inventory`, move to `#/review`, or take a route of its own — and the
recommendation was to keep it where it was. The owner overruled it: *"I want to give runs its
own tab for now, put it between capture and review queue."* `#/runs` is the route,
`app/src/Runs.tsx` is the screen, and `RunPanel.tsx` is unchanged inside it.

**THE ARGUMENT AGAINST IS D33's AND IT IS RECORDED HERE RATHER THAN DELETED, because it names
the one thing that could go wrong.** D33 put the panel on `#/inventory` because a run is
something you do TO a box, or to the cards you have just ticked inside it, and that screen is
where both are chosen: *"a route of its own would have to re-implement the box strip, the search
and the mass-select, and would then be free to disagree with them about what is selected."* That
sentence is still true, and it is the specification this build was written against rather than a
prediction it disproved.

**THE BOX IS RE-ANSWERED AND THE SELECTION IS NOT RE-IMPLEMENTED, WHICH IS THE WHOLE OF THE
DESIGN.** The two halves of a scope have different costs and the answer splits on that:

- **A box picker is cheap and cannot disagree with anything.** `#/runs` draws its own strip
  from `GET /boxes` — thirteen chips carrying a card count each, the same idiom the walk's shelf
  strip already uses. There is no second source of truth about which boxes exist.
- **A ticked selection is expensive and would.** `BoxBrowse`'s mass-select is the ONLY one in
  the product, and it is also what a box-wide claim correction reaches, so two of them would be
  two answers to what "the selection" means. So there is still exactly one, and `#/inventory`
  HANDS IT OVER: `app/src/runHandoff.ts` carries the box and its indices through
  `sessionStorage`, and `#/runs` draws what it was handed with a control that says where it came
  from and one that gives it back.

**THE HANDOFF IS D27's CARVE-OUT AND NOT A NEW ONE.** That entry opens session storage to state
that is device-local and meaningless anywhere else, against `CLAUDE.md`'s ban — a ban D13
imposes so two devices cannot disagree about where a card IS. A tick list is not where a card is.
The key is `pkmnscan.run-scope`, it is declared in one module, and every reader and writer in the
app goes through that module's three functions.

**IT IS NOT CLEARED BY BEING READ, AND IT IS CLEARED BY EVERY OTHER ROUTE INTO THE SCREEN.** A
reload during a live run is ordinary — the panel polls, and an identify run takes minutes to
hours — so a read-once handoff would silently drop the operator from "36 ticked cards" to "the
whole box", which is a change to what the next press spends money on. What clears it: the
operator's own control, picking any box on `#/runs`, and **arriving from `#/inventory` with
nothing ticked**. That last one is the case that is easy to miss and the reason the control on
`#/inventory` writes on every press rather than only when there is something to write — without
it, ticking cards, going over, coming back and pressing again would restore yesterday's
selection from storage.

**A CARRIED BOX THAT NO LONGER EXISTS IS DROPPED WHOLE**, checked against the registry on
arrival, because `runHandoff.ts` can validate a shape and only the screen knows which boxes are
real. Falls through to the picker, which is where the operator would have been had nothing been
handed over — D3 rung 0's rule one register down.

**NOTHING IS SCOPED ON ARRIVAL, AND THAT IS A STATE THE OLD ADDRESS NEVER HAD.** On `#/inventory`
the walk had always picked a shelf by the time the panel drew, so `scope.box` was never null in
practice. `Runs.tsx` refuses to default it: a box chosen for the operator is a box they did not
read, and the next press after it is the one that spends money. The free preflight is disabled
until a box is picked — **disabled rather than absent, and it is the one control on this screen
that gets to be.** `docs/DESIGN.md`'s absent-not-disabled rule is about the control that
COMMITS; the spend button still does not exist until the preflight has answered. This one is
free, it is the next thing to press, and a control that vanishes until an unrelated press brings
it back is a screen that looks broken.

**WHAT THE MOVE BUYS, and it is the half D33 could not.** `App.tsx`'s own route table calls
`#/inventory` a `look` route — "reached when asked, not on a rhythm" — and housed the four
commands there, which are the loop a session actually is. The panel is also the tallest thing
this product draws (625px closed, 1143px with a run picked), and on `#/inventory` it was the
last row of the content column, which put `Check cost` a page-scroll below the card. Neither was
going to be answered by a fourth relocation inside one screen; D38 records the three that were
already tried.

**`,R` REACHES IT AND THE REVIEW QUEUE MOVED TO `,Q`** (the owner's instruction, in those
terms). `App.tsx` said every route's chord key is its own INITIAL, and that claim is now false
and is rewritten there rather than left standing: two routes start with `r`, `#/runs` has no
second word to fall back on and the review queue does. What survives is the rule that actually
makes it learnable — the key is a letter the owner would say out loud naming the screen.

**WHAT STAYS ON `#/inventory` IS ONE ROW, AND IT MUST NEVER BECOME TWO.** `app/src/BoxRuns.tsx`
sits in the slot the panel vacated and does exactly two things: it says whether anything is
running over the box in front of you, and it is the handoff. **No step, no console, no figures,
and above all no control that spends** — D33's money gate is two presses that must both happen
where the estimate is on screen, and a spend reachable from a screen that never drew a preflight
is precisely what that gate exists to prevent.

**The live-run line is there because it is the one fact whose latency matters.**
`identify/batch.py` logs only when a batch's status CHANGES, so a console written forty minutes
ago is indistinguishable from a hang — which is why a run row says how long it has been running
rather than inventing a progress bar. Whether the box you are standing at has one going is worth
a line on the screen you are standing on; everything else about a run is a page away and should
be.

**A GRID DEFECT CAME WITH THE MOVE AND IS FIXED HERE, and it was caught by this repo's own
test.** `.browse-map` spans `grid-row: 1 / -1`, and a grid item spanning several AUTO tracks has
its height distributed across them. That was invisible while the console sat in row 3 at
625–1143px, because row 3 alone exceeded the sticky map's viewport cap. With a 50px status line
there instead, the map's ~700px went into rows 1 and 2 — measured, a query matching no card put
the runs row at y=266 with nothing above it. The last row is `1fr` now, which excludes it from
that distribution. The case that went red is the one D38 wrote for the opposite defect, which is
the argument for having written it as a measurement rather than as a class name.

**THE TWO QUEUE FIGURES BECAME THE WAY INTO THE QUEUE.** `join` writes a review queue and the
panel reported its depth with no route out of the report — a capability with a screen, and a
screen with no way to it, which is `CLAUDE.md`'s route-is-not-a-feature rule in miniature. Both
`Review` and `Parked` link to `#/review`; parked is not a second route, because
`ReviewQueue.tsx` draws both files and its reason chips filter between them.

**WHAT WOULD REOPEN THIS: the handoff going unused.** If runs are never started from a ticked
selection, the mass-select coupling this entry spends most of its length preserving is
decorative, and the honest simplification is to delete `BoxRuns`' handoff and leave the status
line. The measurement is `scope.cards` being non-null on any run in `runs/`, and
`docs/GATES.md` step 15 still records that no run has ever been started from the app at all.

---

## D40 — The screen is three columns: the box, the card, and where its copies are

**BUILT 2026-08-29, on the owner's own layout.** Their words, after being shown the two-column
screen: *"I know for a fact that Box 2 Run Box at the bottom, and then the amount of whitespace to
the right of card photo and description are seriously triggering me"* — and then the design
itself: *"Think rule of thirds. The left 1/3 sidebar stays put. The middle 1/3 gets the photo,
then the buttons correct claims remove this card and then the description (vertical) and then the
right gets the card locations. Maybe it's like 20% 35% 45%."*

**THE TWO COMPLAINTS WERE ONE DEFECT, THREE DAYS OLD.** `2ec06f8` deleted the body's third column
(D38, amended) and re-created it one level down as `.browse-detail`'s third track — `minmax(0, 1fr)`,
a RESIDUAL track, so it absorbed every spare pixel in a 1024px content column and held two buttons
in 408 of them. Measured: 408x374 of track holding 408x32 of content, **91% empty**, and that track
was 40% of the content column's width. The stacked full-width copies list below it was the other
half of the same problem — a band that could not fill 1024px, stacked on a list that needed it.

**THE FILE HAD ALREADY CONFESSED IT AND BET ON A JUSTIFICATION THAT DID NOT HOLD.** `BoxBrowse.css`
called the space "THE RESIDUAL, NAMED RATHER THAN DRESSED UP" and defended it as "the rail's
declared growth room" for the open-question block. Measured on the owner's store the day this
changed: **both queue files were empty**, so that block drew on **0 of 543 cards**. The same comment
also asserted "that is not the space the owner named" — it guessed the complaint was the
photo-facts gap. The owner has now named it, and it was the rail.

**THE RATIO IS 22 / 33 / 45 AND ONLY THE FIRST NUMBER IS DERIVED.** At 1440 the body is 1408px and
two 24px gaps leave 1360, so the owner's 20% is 272px — **8px inside the ~280px wrap cliff**
`BoxOps.css` was tuned to clear (D38). 22% is 299px. A 285px floor holds it above the cliff at
1280, where 22% of 1200 would be 264. `fr` rather than percentages, because percentages plus two
gaps overflow a container that has no slack to absorb it — `.browse-map` is sticky and would be the
thing clipped.

**THE DESCRIPTION LEFT THE MIDDLE COLUMN, AND THAT IS THE ONE PLACE THIS DEPARTS FROM THE OWNER'S
SPEC — AT THEIR OWN SUGGESTION.** They asked for photo, then buttons, then description, stacked. It
was built that way and measured, and the arithmetic refuses it: the middle column has 715px above a
900px fold, and photo + buttons + eleven fact rows needs ~1050. Capping the photo to fit costs it
twice — **311x435 (1.35x today) AND 165px of dead slack beside it**, because a height-capped
photograph that keeps 63:88 gets NARROWER than its track. The owner then proposed the answer
themselves: *"I think you'd be able to fit the description as some sort of aesthetic thing at the
top of the locations on the right third too though."* That is what shipped.

**WHAT IT BUYS, MEASURED AT 1440x900 ON BOX 2, CARD 1:**

| | before | after |
|---|---|---|
| photograph | 268x374 | **449x627**, aspect 0.716, **2.81x area** |
| description | 300x318, one column, in the band | 578x171, **two columns**, capping the copies |
| run line | y=1164, 264px below the fold | **y=62**, in the header |
| copies, first row | y=626, 82px rows, 3.35 visible | y=379, 144px rows, **3.62 visible** |
| ink / void | 33.34% / 41.99% | **47.97% / 26.30%** |
| page | 1230 | 1273 |

**VOID IS A MEASURED NUMBER AND THE TARGET WAS MISSED.** The owner asked for "less than a fifth" of
the whitespace. Against an instrument that rasterises every text and image rect at 8px and keeps
only empty area more than 24px from any ink — so normal line-leading does not count and real holes
do — the honest result is **41.99% -> 26.30%, a 37% cut, not 80%**. Recorded as a miss rather than
rounded up, because the owner's own rule is that a number is evidence. What binds it is the copies
rows: the largest surviving void component is inside them.

**THE COPY-ROW RE-TUNE WAS ASKED FOR AND IS REFUSED, ON THE FILE'S OWN RULE.** The owner approved
narrowing the row toward D38's measured 83px. At the 586px this column gives it, the row is
`8 + place 51 + gap 12 + bar 65 + 8 = 144`, and line one already uses **583 of 586px** — so the
position bar genuinely cannot join it. Lowering `CardLocations.css`'s 860px container threshold to
560 does shorten the row to 129px, and it does it by squeezing `.card-locations-place` to 231px,
which **wraps the position label**. That file forbids exactly this: *"the position label is the
string somebody carries to a shelf and it must not break."* A row that is 15px shorter and lies
about where a card is, is not a trade this repo makes.

**And the re-tune turned out not to be needed for its stated purpose.** The column move alone takes
rows-visible from **3.35 to 3.62** — the rows are taller and there are more of them on screen,
because they start 247px higher. The owner's "tighter width wise yet longer height" is what a 144px
row at 586px IS; it was the goal, not the defect.

**THE REFUSAL ABOVE WAS OF ONE MECHANISM, NOT OF THE GOAL, AND A DIFFERENT ONE SHIPPED THE SAME DAY
(2026-08-29, the owner: "Yes do the copy row density change").** What is refused, permanently, is
lowering the 860px container threshold: it buys 15px by squeezing `.card-locations-place` to 231px
and wrapping the position label, which `CardLocations.css` forbids by name. That paragraph stands.

What was missed while writing it is that the row's dead space is not in its first line at all — it
is inside the BAR. The bar is four stacked full-width children (box track 16, its caption 14, the
section block's 8px track and its own 14px caption) on 570px lines carrying captions that measure
~120px and ~200px. **Beside their tracks instead of under them, the same four parts are two rows
rather than four**: bar **65 -> 34px**, row **144 -> 114px** at 1440 and **188 -> 158px** at 1280,
copies visible on landing **3.61 -> 4.56**, page 1274 -> 1092, and the landing void **26.30% ->
22.32%** — which takes the cut from this file's own 41.99% baseline to **47%**.

**Nothing is given up for it, and that is checked rather than asserted.** The box track is still
16px, the section track still 8px, the section block keeps its indent, and the captions keep their
`#` and `Section` prefixes — all three cues `docs/DESIGN.md` names for telling the two scales
apart. The position label stays on one line at 586px.

**The case that guards it had to be pinned to 1440 to be worth anything**, and that is the finding
worth keeping: this suite runs at 1280, where the container is 528px and the rejected threshold
change behaves identically to the shipped one. Written at the default viewport, the case passed
against the very mutation it exists to catch. It is red at 1440 against that change and green
against this one, observed both ways.

**AND THE FOLD EXPOSED A CLIFF POINTING THE WRONG WAY, WHICH IS FIXED HERE (860 -> 880).**
`CardLocations.css` switches the bar into the row at a container threshold, and 860 was chosen
against a 144px narrow row. Once the narrow row was 114px the wide branch was producing **126px at
the exact width it engaged**: measured across the sweep, 820 -> 114, **860 -> 126**, 880 -> 85,
900+ -> 82. Crossing into the better branch made the row twelve pixels taller.

**It was dormant rather than invisible, and that is the worse condition.** The copies container is
612px at 1440 and 528px at 1280, so `min-width` needs roughly a **1980px viewport** to fire at all
— nothing in the suite and nothing on the owner's display would ever have rendered it. 860 was
picked because "columns 2+3 measure 862px at Playwright's 1280", a layout this very entry deleted,
so the number was inherited from a dead premise. That is the same defect D41 found in the position
label's own comment, in a rule that had no way to fail while it waited.

**The assertion is the PROPERTY, not the new number**: a container that grows may never make a row
taller. Pinning 880 would go green on any later change that moves the cliff somewhere else, which
is exactly how this one survived.

**WHAT IT COSTS, NAMED RATHER THAN BURIED.** `.boxops-meta` wraps from one line to two — 17px to
33px — because it needs the full 360px track and now has 299. Measured across 299-360px: it is
one line at 360 and two below it, with no intermediate. Accepted rather than fixed: it is a
metadata line, not a control, in a sticky column that has ~290px of unused height at the owner's
size, and holding 360px for it would cost the description its second column.

**THE RUN LINE IS IN THE HEADER, WHICH IS D39's RULE HELD RATHER THAN SPENT.** `BoxRuns` is
box-scope content that was living in the content column, so its y was set by the copy count and by
whether the claims editor was open — measured, **y=1164 on a six-copy card and y=1572 on an
eleven-copy one**, both below the fold. `docs/DESIGN.md` authorises the header directly ("the page
title ... shares a line with the screen's controls and counts"), and it was the one item on this
screen missing that file's own "first row of real content within 150px" floor, by 1014-1422px.
D39's *"it must never become two rows"* stops being a promise in a comment and becomes structural:
on a shared line it cannot. The left column — where D38's "the left column IS the box" would point
— is **rejected by measurement**, not preference: its content box is ~334px and the ordinary ticked
state is 428px, so it would wrap to two lines the moment anything is ticked.

**THIS IS THE FIFTH RELOCATION OF THAT SLOT IN FOUR DAYS** (third column, row 3 of the content
column, `#/runs` for the panel, row 3 for the line, header). Said plainly because D38 records the
first three and a reader is entitled to count. What moved this time is a 32px status line, not the
625-1143px panel that made the earlier moves expensive.

**WHAT WOULD REOPEN THIS: a copies column wide enough for an 83px row.** That needs ~860px of
container, which three columns cannot give at 1408px of body. If the owner ever works at a width
where 45% exceeds 860 — a 1920px display puts it at 828, still short — the row improves on its own
through the container query already there, with no change to this entry.

---

## D41 — The address is a rank, not a list, and the separator is deleted rather than replaced

**BUILT 2026-08-29, from a design pass the owner asked for and then chose from.** Their words:
*"can you also fix this area? don't just decrease the font, make a new aesthetic design there
currently i didn't ever like the dot theme to separate would rather have actual shapes or
something idk"*, and a few minutes later, of the sidebar's own dotted line: *"same with this part
going into two lines"*. Two designers worked the problem from opposite lenses — shape-led and
typographic — and six treatments were rendered against the real store. The owner picked the
**terminal-dominant** address and the **census-triad** meta block.

**IT WAS NOT A FONT-SIZE PROBLEM AND THE ARITHMETIC IS WHY.** `Box 2 · Section 1 · Card 14` is 27
cells at Martian Mono's measured **0.70em** advance = **453.6px**, in a track that is 448.8px at
1440 and **387.1px** at 1280. It overflowed by 4.8px and wrapped. Of those 27 cells only **four
are digits** — 67.2px, **14.8%** — while the words, dots and spaces are **386.4px, 85.2%**. The
chrome alone is larger than the entire 1280 track: the separator and the labels consumed the
column before a single number was drawn. Shrinking to fit needs **17px**, and `CardLocations`
prints the same string at 13px seven rows below on the same screen, so the fix the owner
pre-emptively refused would have made the answer 4px louder than its own footnotes.

**THE COMMENT THAT JUSTIFIED THE OLD SIZE HAD ALREADY BEEN FALSIFIED BY A LAYOUT CHANGE.**
`BoxBrowse.css` read: *"The worst realistic label — `Box 100 · Section 12 · Card 543` — draws
521px inside a 630px track, so nothing reflows."* The px figure is right (520.8). **The 630px
track no longer exists** — D40 made it 448.8px. A later change deleted the premise and left the
conclusion standing, which is the exact failure `docs/DESIGN.md` and D16 are both written
against. Recorded here rather than quietly corrected, because the class of defect matters more
than this instance.

**THE THREE PARTS ARE NOT EQUAL, AND THE OLD RENDERING CLAIMED THEY WERE.** `Box 2` is the drawer
you walk to, `Section 1` narrows it, `Card 14` is the slot. On THIS screen the first two are
already answered everywhere the eye lands — the box strip, the identity block, every section
header, every copies row. **Measured: the literal string `Box 2` renders nine times in the
document.** `Card N` is the only part of the address this panel uniquely supplies, so it is the
only part drawn at size: the path becomes an 11px muted two-line stack and the slot a **44px**
figure beside it. The payload goes 24px -> 44px, **+83%**, on a screen whose whole question is
*where is this card*.

**THE SEPARATOR IS GONE, NOT RESTYLED, AND THAT IS THE OWNER'S ASK ANSWERED LITERALLY.** Nothing
takes the interpunct's place — with the path stacked and the slot beside it there is no seam left
for a character to mark. `.browse-position-joint` is deleted. That rule was itself only three days
old (2026-08-26, painting the dots muted so the parts would bind); it treated the joints as the
thing to quieten, and this treats them as the thing to remove. Both answer the same complaint; the
owner rejected the first.

**THE SERVER STRING IS UNTOUCHED AND IS STILL THE ACCESSIBLE NAME.** `pipeline/join.py:Position.label`
emits `Box N · Section N · Card N` and keeps emitting it. `PositionParts` recomposes it into
key/figure pairs for THIS screen only and carries the original verbatim on `aria-label`, so what
a screen reader announces is exactly what the store said. That is what makes a client-side split
a VIEW rather than a quiet edit of the record. `.review-position` and `.card-locations-label`
draw the same string and are deliberately untouched — taking this to them is a decision about all
three sites, not a copy of this one.

**`app/tests/fulfillment.spec.ts` IS NOT REACHED AND WAS CHECKED RATHER THAN ASSUMED.** Its 32px
tabular-figure floor probes `.fulfillment-place` and `.card-locations-place-large` inside
`view(page)`; `.browse-position` is neither, and no spec selects it. D31's rule that the
Fulfilment spec stays unweakened is intact.

**THE SIDEBAR LINE IS THE SAME COMPLAINT WITH THE SCARCE AXIS INVERTED.** `cards 543 · sold 0 ·
fill 543 · next index 544` is 46 cells = **354.2px** in a track that D40 narrowed to 299px at
1440 and 285px at 1280. It is **not** a digit-count problem — box 1's four-characters-shorter
line wraps identically — it is four label words and three interpuncts, 277.2px of chrome against
77.0px of digits. Here horizontal is fixed and **vertical is ~290px of unused height** under the
column in D31's resting state, so the block flows DOWN instead of across: three census figures at
16px in a row, `next index` on its own line at the muted register.

**`next index` LEAVES THE ROW BECAUSE IT IS NOT A FOURTH STATISTIC.** `cards`, `sold` and `fill`
describe what is in the box; `next index` is D10's high-water mark — what the allocator will hand
out next. Four peers joined by dots was a false claim about them, and the structure is now the
distinction rather than a sentence explaining it.

**AND D20's TWO WORDS ARE ON SCREEN ONCE, ON THE IDENTITY LINE.** That entry is explicit that a
denominator whose meaning switches silently between an open box and a sealed one is the failure it
exists to prevent — `fill` is a fill-**so far** while the box is open and a frozen capacity once
**sealed**.

**THE QUALIFIER WAS PUT ON `.boxops-meta`'s FILL AND TAKEN OFF AGAIN ONE COMMIT LATER**, and the
correction is worth recording because the first version made a duplication EXACT that had until
then only been approximate. `BoxIdentity` sixteen pixels above already renders `133 so far`;
adding the same two words to the meta line put the identical string on screen twice, nine words
apart. Measured on the owner's store, both before and after.

**The field stays and only the qualifier goes**, which is the half that matters: `BoxOps.tsx`
promises these key names grep to `inventory.json`, so dropping `fill` outright — the other option
considered — would have broken one promise to keep another. D20 is discharged either way, because
its rule is that the number is unambiguous ON SCREEN, not that it is annotated at every site that
draws it.

**FIELD NAMES STAY VERBATIM IN THE DOM.** `BoxOps.tsx` promises that what is on screen greps to
`inventory.json`; the keys are written lowercase and uppercased by `text-transform` at paint only,
so a copy out of the DOM still matches the store. `app/tests/inventory.spec.ts` asserts the
lowercase text, and a `toUpperCase()` in the component — which would look identical on screen —
takes it red. That mutation was run.

**WHAT IT COSTS, MEASURED.** The address block goes **86px wrapped -> 70px**, so it is shorter
than the state it replaces. The meta block goes **33px -> 62px**. That height is free in D31's
resting state and is **not** free once a section is open, where `.browse-map` is at its viewport
cap and `.browse-list` is the scroller — there it comes out of the walk at 25.5px per card row,
about 1.2 rows. The ledger variant that was also rendered cost 81px and ~1.9 rows, and was
declined on that number.

**THAT REOPENING HAPPENED THE SAME DAY. The owner: "Full treatment for all -- amendment."** The
paragraph this replaces named `.review-position` and `.card-locations-label` and said taking the
treatment to them was "a decision about all three sites, not a copy of this one". This is that
decision, and the count was wrong: the capture screen draws the address in **five** more places,
three of them inside running sentences. Six owner sites, not three.

**THE STRUCTURE IS UNIVERSAL AND THE SIZE IS PER SITE, WHICH IS WHAT THE OLD PARAGRAPH'S WARNING
BUYS.** It predicted that "a 44px figure repeated seven times in a list would be a different and
worse defect", and that is now measured rather than predicted: at 44px the copies row goes
114.17 -> 126.48px, +86px on a seven-copy list, and copies visible on landing drop 4 -> 3 — on the
screen whose recorded complaint (D38 twice, D40 again) is that the copies scroll away. So what is
shared is the RANK — muted stacked path, no separator, the slot as the only thing drawn at size —
and each site sets its own figure.

**ONE COMPONENT, `app/src/PositionLabel.tsx`, AND ONE DECLARATION PER SITE.** `--pos-slot` is the
figure and `.position-num` is `1em`, so a site's whole register is one line in its own stylesheet.
The key is `clamp(var(--pos-path), 0.295em, 13px)` — 12.98px at a 44px figure and 11px at 32, 28
and 20 — so `#/inventory` keeps its shipped key to within 0.02px and no other site declares one.

**PROPORTIONAL SCALING WAS TRIED AND REFUSED, WITH THE ARITHMETIC.** D41's shipped ratio is path
11px against 44px, 0.25em. At the review head's 32px that is 8px and at the copies row's 28px it is
7px, below anything this product draws. Probed independently, **all four new sites landed on the
same 11px path against four different figures** — the path tracks each screen's metadata register
(`.review-machine` 11px, `.card-locations-boxname` 10px) while the figure tracks its payload. Two
scales, not one; a single multiplier would have claimed these screens are scaled copies of each
other.

**THE FIGURE IS FREE UP TO 32.3px, AND THAT IS ONE MEASUREMENT NOT FIVE.** The two-line path is
33.9px, so at `line-height: 1.05` every figure to 32.3px draws the same 33.9–34.0px block: 20, 24,
28 and 32 cost nothing, 36 costs 4px and 44 costs 12. Three of the four new sites sit on that
plateau by construction. **It is a property of a THREE-part label** — a two-part label has a
one-line path and the plateau collapses, which D36 and D24 both contemplate.

**THREE SITES NEEDED A RULE THE BAND DID NOT.**

- **The copies list leads with the SLOT, not the path**, because it is a list. Down seven rows the
  coarse parts are identical, so path-first stands seven `BOX 2 / SECTION n` blocks in front of the
  only thing that differs — the dense-grey-table failure `docs/DESIGN.md` names by the front door.
  It is height-free **only because the two-line path absorbs `.card-locations-boxname`**; a box
  with no name pays +17px on every row, and D20 made names unique but deliberately NOT required.
  Latent today, nothing warns.
- **An in-sentence label gets the RANK without the geometry** — the `run` form. Stacking inside a
  sentence measured 79px against 23px and orphaned the trailing period onto its own line; at
  `inline-flex` it rendered `BOX 2` above the baseline as a superscript footnote marker.
- **A NUMERIC GUARD, which D41's own splitter did not have.** `#/inventory` draws only real
  positions. `#/review` draws D24's pooled label `Pokémon code cards · pooled`, which the shipped
  splitter turned into a path reading `POKÉMON CODE cards` and a lowercase word promoted to a
  300.9px figure. Nothing broke geometrically and no assertion saw it. A promoted slot is a slot
  NUMBER or the label renders whole.

**THE FULFILLER'S FIREWALL IS THE COMPONENT GRAPH, NOT A SELECTOR.** `Fulfillment.tsx` and
`CardLocations.tsx:FulfillerCard` do not import the component, so no `.position-*` rule can reach
his 32px and 36px labels — which is why stripping a class prefix cannot breach it. The breach that
would actually happen is somebody lifting the call out of `OwnerCard` into a shared render path,
and `app/tests/fulfillment.spec.ts` now states that as a CAUSE (`.position-parts` count zero)
rather than leaving it to be diagnosed from a font size. Mutation-tested: the lift takes the
firewall case red, and eleven other cases with it.

**TWO ASSERTIONS WERE FOUND DEFECTIVE ON THE WAY, BOTH WRITTEN EARLIER THE SAME DAY.**
`inventory.spec.ts`'s `labelLines` read `getClientRects().length` off a column-flex child, which is
blockified and returns exactly ONE rect however many lines it holds — measured on the shipped tree,
the label wraps to 2/3/4 real lines at 200/120/80px and the assertion read 1 every time. Its case
only ever went red on a different assertion, which hid it. And `review.spec.ts`'s
`.not.toHaveText(/Card 14$/)` would have gone vacuous the moment the DOM text stopped containing
that string, passing forever while detecting nothing — the silently-weakened shape D16 forbids.
Both now assert against `aria-label` or a geometric fact.

**WHAT IS NOT TREATED, AND WHY.** `.review-row-position` (11px, 23 in the rail), `.review-group-pos`
(10px) and the capture screen's bare-integer consumer keep the plain string: the mechanism is RANK,
and a 10px caption has no rank to spend — stacking it would cost height in the two lists whose only
job is to be scannable. The consequence is honest: **`#/review` now renders the address two ways.**
So does `#/inventory`, where the band's 44px figure and the copies list's 28px sit ~500px apart in
one idiom; the 1.57 ratio is what keeps the band dominant, and it is the first thing to look at if
the screen starts feeling noisy.

**ONE SITE IS UNTREATED FOR A STRUCTURAL REASON RATHER THAN A DESIGN ONE.**
`CaptureScreen.tsx:1931` composes `Note saved on ${target.card.label}.` as a plain STRING inside a
notice payload — there is no element to style and no JSX to return, so it cannot take even the run
form without changing the notice type across the component. Named here rather than silently left,
because it is the one place the owner's "all" is not satisfied.

**WHAT WOULD REOPEN THIS: a two-part label, or a box with no name.** Both collapse a measurement
this rests on — the first ends the 32.3px free plateau, the second costs the copies list 17px a row.
Neither is hypothetical: D24 pools cards without positions and D20 leaves names optional.

---

## D42 — main moves by pull request, and the guard is local because the server-side one is not for sale

**BUILT 2026-08-29, after main moved under live worktrees twice in one day.** `637e2e4` was
authored on one session's branch and fast-forwarded into main while three others were working
on branches cut from it; `f5dcc2b` was pushed straight to `origin/main` during the session that
wrote this entry, which is how the second half of the guard got specified. `origin/main`'s
reflog is five consecutive `update by push`. Nothing in the repo had ever said a session may
not do that, and nothing checked.

**BRANCH PROTECTION WAS THE OBVIOUS ANSWER AND IT IS NOT AVAILABLE ON THIS REPOSITORY.**
Measured rather than assumed — both surfaces answer 403:

    GET repos/shivinate7/pkmnscan/rulesets                   403
    GET repos/shivinate7/pkmnscan/branches/main/protection   403
    "Upgrade to GitHub Pro or make this repository public to enable this feature."

Free plan, private repo. The second half of that sentence is not an option: `CLAUDE.md`'s
repo-wide opsec rule makes a live unredeemed code card a bearer instrument, and this tree
carries the enforcement for it. So the server-side gate costs a Pro subscription, and the
owner chose the local guard instead.

**AND IT WOULD NOT HAVE CLOSED THIS ON ITS OWN, WHICH IS THE PART WORTH KEEPING IF THE PLAN
EVER CHANGES.** Branch protection bites at `git push`. Both incidents moved main **locally**
first, under worktrees that share this clone — by which point every session cut from main is
already sitting on a different history than the one it started from. A gate at the remote
would have caught the second incident and been silent through the first.

**TWO HOOKS, BECAUSE THERE ARE TWO WAYS OUT, AND NEITHER COVERS THE OTHER.**

- `scripts/githooks/reference-transaction` — main does not move in this clone. It is a ref
  hook and not a commit hook **because the first incident created no commit**: a fast-forward
  merge moves a ref and runs no commit hook, and `git rebase`, `git reset --hard`,
  `git branch -f` and `git update-ref` are the same shape. Underneath they are all one ref
  update, so the ref update is the only place that catches all of them and the only one that
  cannot be routed around by reaching for a different porcelain command.
- `scripts/githooks/pre-push` — nothing pushes to main. `git push origin HEAD:main` never
  touches `refs/heads/main` locally and lands the commit on GitHub anyway, so the first hook
  is blind to it. This is the piece standing in for branch protection, and it is weaker in one
  nameable way: it lives on this machine, so it protects this clone rather than the repository.

**THE ONE LEGITIMATE MOVE IS TO A COMMIT ORIGIN ALREADY HAS.** That is the whole allow rule,
and it is what makes the pair a workflow rather than a wall: a PR is merged on GitHub,
`git pull` fast-forwards, and the commit was on the remote before it was ever on your main.
It cannot be forged from inside a session, because a local commit is not on origin until
something pushes it, and pushing to main is what the second hook refuses.

**THE `old` COLUMN OF A reference-transaction PAYLOAD IS NOT EVIDENCE, AND BELIEVING IT SHIPPED
TWO HOLES BEFORE THE SELF-TEST FOUND THEM.** The format is `<old> <new> <ref>`, so the obvious
rules are *allow a no-op* (`old == new`) and *allow a creation* (`old` all zeros). Both are
wrong. Measured on git 2.39.3:

    git branch -D main              0000000... 0000000... refs/heads/main
    git branch -f main feature      0000000... 3f5f2cd... refs/heads/main
    git update-ref refs/heads/main  0000000... 8f06f47... refs/heads/main

Git reports zeros for the old value **whenever the caller did not state an expected one**, even
where main exists at a real commit. So a deletion is indistinguishable from a no-op, and
`branch -f` is indistinguishable from a creation — the first draft waved both through, and main
was genuinely deleted in the test rig. The hook now decides on `new` alone and asks git for the
pre-update value itself when it wants one.

**IT FAILS OPEN ON ITS OWN BUGS, AND THAT IS A TRADE RATHER THAN A WEAKNESS.** This hook runs on
every ref update in every worktree of the clone. A version that exits non-zero when it did not
mean to does not block one commit; it breaks git for every concurrent session at once. So the
only non-zero exit in the file is the deliberate refusal, and an unknown phase, an unparseable
line or a missing git allows. Same rule `scripts/docs-audit.py:nested_worktrees` states for
itself, and the same one `scripts/guard-opsec.sh` took after it over-triggered (D16).

**THE HOOKS ARE INSTALLED INTO THE GIT COMMON DIR. THIS PARAGRAPH SAID SOMETHING ELSE FOR
ABOUT AN HOUR AND BOTH OF ITS CLAIMS WERE FALSE — the amendment is dated the same day as the
entry, which is the useful part of it.** What it said: point `core.hooksPath` at the MAIN
worktree's `scripts/githooks`, absolutely, because "that setting lives in the common `.git`
dir, so one value governs every worktree of this clone."

**Claim one, falsified within the hour of merging.** A working tree's contents are a function
of whatever branch that checkout is on. The moment this entry landed on main, the main
checkout was sitting on another session's WIP branch that predated it, so the directory git
actually read held **one hook out of three**. The guard was armed at zero and nothing said so
— the silent-failure class this repo refuses everywhere else, reproduced by the fix for it.

**Claim two, falsified by running the test rather than reading the config.** `extensions.
worktreeConfig` is **on** in this clone, and whatever creates `.claude/worktrees/` writes a
per-worktree `core.hooksPath` into `.git/worktrees/<name>/config.worktree` — beside a
`core.longpaths`, so it is that tooling and not this repo. **A per-worktree value beats the
common one.** After an install that printed success, `git config --get core.hooksPath` inside
a worktree still answered the old path, and all four worktrees were still unguarded. It was
found by running the nineteen cases against the INSTALLED directory — `PKMNSCAN_HOOKS_DIR`
exists on the self-test for exactly this — and it would not have been found by reading the
config, because the config that lies is not the one you look at.

**So: `make hooks` copies the tracked hooks into `<git-common-dir>/hooks-armed`, points the
common config there, and UNSETS the per-worktree override in every worktree.** `.git` is
per-clone, shared by every worktree, and no branch can empty it. Unsetting rather than
re-pointing, because one value is the property this paragraph wanted in the first place and
four copies is four things that can drift. Verified after the change: all seven worktrees
resolve to the install, the installed copy passes all nineteen cases, and a live
`git push --dry-run --force origin <branch>:main` in the real repository is refused by name.

**IT INSTALLS WHAT GIT TRACKS, NOT WHAT THE DIRECTORY HOLDS.** The first version copied
`scripts/githooks/*`, and this repo lived in iCloud Drive at the time, which had made `pre-push 2` and
`reference-transaction 2` beside the originals — so it installed five hooks from three files,
two of them untracked and reviewed by nobody. Git dispatches on exact names so it would not
have RUN those two, and the damage was cosmetic; the mechanism is not. A hook directory whose
contents are decided by whatever is lying on disk has given up the reviewability that is the
whole reason these files are tracked rather than written into `.git` by hand. `git ls-files`
is the only enumeration that means "the thing someone reviewed", and untracked files present
are reported rather than silently skipped.

**WHAT IS GIVEN UP, NAMED RATHER THAN DESIGNED AWAY: the copy can go stale**, and a new
worktree gets handed the per-worktree override again by whatever creates it. Neither can be
closed by a check without lying — the tracked file legitimately differs between branches, so
"installed does not match this tree" is a fact and never a fault, and it must never gate a
commit. `make status` reports both instead: it reads NOT ARMED whenever the effective path is
not the install, and prints which hooks differ from the current tree. That is the one surface
in this repo whose whole job is saying what state you are actually in.

**THE ESCAPE HATCH IS `PKMNSCAN_MAIN=off`,** spelled the way `PKMNSCAN_GATE=off` and
`PKMNSCAN_DOCS=off` already are. It is one variable and it is printed in every refusal, because
a guard with no visible way past it gets disarmed at the config instead — and a disarmed
`core.hooksPath` takes the three opsec rules with it, which is the trade D16 already refused to
make for the docs audit.

**`make githooks-selftest` IS THE EVIDENCE, AND IT RUNS IN `make check` AND NEVER IN THE GIT
HOOK.** D18's rule: it writes — a bare repo, a clone, commits, pushes — and nothing that writes
may run on the path that decides whether a commit proceeds. It has a second reason of its own
that the docs audit's self-test does not: it exercises the guard by **violating** it, so a
version wired into the commit path would be refusing its own commits. Nineteen cases, and two
of them were green for the wrong reason until the harness was made to check whose refusal it
was: git declines to delete the branch you are standing on and declines to push what is already
up to date, both without consulting a hook. A refusal now has to carry the hook's own marker to
count.

**WHAT IT DOES NOT COVER, stated so a green self-test is not misread.** It is one machine's
clone. A push from anywhere else, a commit made in a different clone, and the GitHub web
editor are all outside it. That is the exact gap branch protection would close, which is why
the next paragraph is short.

**What would reopen this: GitHub Pro, or the repository going public.** Either makes rulesets
available, and the honest response is to add one requiring a pull request on main and keep both
hooks — the server gate for what reaches the repository, these for what reaches this clone's
main. Not either/or: the two incidents that produced this entry were one of each.

---

## D43 — the port follows the store, because the store was already per-checkout

**BUILT 2026-08-29.** `store/files.py:home()` has always defaulted to `REPO_ROOT` — the
checkout the code is running from — so every git worktree has its own `inventory/`, its own
`runs/` and its own `captures/`. The capture server's port was the bare constant `8000` in all
of them, and `app/src/server.ts` asked for `http://localhost:8000` whatever tree served it.

**A SHARED PORT OVER PER-CHECKOUT STORES IS NOT A BUSY-PORT PROBLEM. IT IS A DATA-LOSS
PROBLEM, AND IT RUNS IN BOTH DIRECTIONS.** Whichever server won the bind answered every tree's
UI:

- a worktree's screens drive the owner's real 767-card inventory, on a branch, with whatever
  half-finished route that branch happens to define; or
- the MAIN checkout's capture screen — the one the owner actually shoots a box from — is
  answered by a worktree's server, and real card photographs are written into
  `<worktree>/captures/cards/` and deleted with the branch.

The second is unrecoverable and silent. Nothing on either screen says which process replied.

**HALF OF THIS WAS ALREADY FIXED AND THE HALF THAT WAS LEFT IS THE ONE THAT WRITES.**
`app/devPort.ts` (2026-08-29, earlier the same day) gave every checkout its own **Vite** port,
after `make design-check` in a worktree attached to the main tree's dev server and asserted
`docs/DESIGN.md`'s floors against code the worktree had never seen — and passed. That entry's
own reasoning is the argument here: *"the shared PORT is the whole fault"*. It stopped at
Vite and Playwright. The capture server, which is the process that writes photographs and
inventory to disk, kept the shared constant.

**`app/tests/inventory.spec.ts` HAD ALREADY WRITTEN THE BUG REPORT.** Its stubs are justified
in a comment saying an unstubbed read is *"a request to whatever is listening on port 8000,
which in this repo is the owner's actual capture server over their actual 767-card
inventory."* That is this defect, observed, worked around locally, and never filed.

**ONE SLOT, TWO PORTS.** `sha256` of the checkout's canonical path, first four bytes, modulo
300. Dev is `5200 + slot`, capture is `8100 + slot`, so a tree reads as a pair — 5276 beside
8176 — and there is one number to recognise rather than two unrelated ones. **The main working
tree keeps 5173 and 8000**, so every doc, the Makefile's help and `scripts/views.txt` stay
true and the ordinary single-checkout workflow is untouched.

**DERIVED, NOT ALLOCATED**, for the reason `app/devPort.ts` already gives: the same tree
answers the same port on every run, which is what makes a printed URL worth keeping and what
lets `strictPort` tell *"someone else is here"* from *"I moved"*. Collisions are possible —
300 slots, a handful of trees — and are loud: Vite refuses to start, and the capture server
raises `EADDRINUSE` rather than serving somewhere else. The remedy is to rename the worktree
directory; the port follows the path.

**TWO IMPLEMENTATIONS OF ONE ALGORITHM, ASSERTED RATHER THAN TRUSTED.** Python serves and
TypeScript addresses, and neither can import the other. `make port-agreement` runs both over
the same real directories and diffs them, and it is in `make check` rather than the git hook
because it needs node and the hook runs bare. **It was mutation-tested in both directions
before it was kept** — moving the Python band takes the composed-port case red, and changing
the slot width takes every path red. A check that cannot fail is not coverage; this repo
already paid for that lesson at the multi-game prompt seam, where a differently-named
identifier field would have parsed cleanly and joined nothing.

**CANONICALISATION IS PART OF THE ALGORITHM AND WAS THE ONE REAL TRAP.** Both sides realpath
the root before hashing — Node's `realpathSync`, Python's `Path.resolve()` — because `/tmp` is
a symlink to `/private/tmp` on this machine and one worktree genuinely lives under it. The
agreement test therefore feeds **real directories** rather than invented strings: a path that
does not exist canonicalises differently in the two languages, so synthetic inputs would have
tested the test rather than the code. `app/devPort.ts` was moved from `resolve()` to
`realpathSync` for this, and it was measured first — every worktree in this clone answers the
same slot either way, so **no existing dev port moved.**

**IT IS SAID IN THE THREE PLACES A SESSION ACTUALLY LOOKS, which is the half that makes it
reliable rather than merely correct.** The owner's complaint was exact: the port reasoning
existed only in a source comment, *"not on CLAUDE.md nor on any hook, so it's not reliable"*.
So: `CLAUDE.md` carries the rule; `scripts/worktree-guard.sh` — the SessionStart hook — prints
this tree's two ports before any work begins; `make status` prints them and says outright when
you are in a worktree; and `make server`'s banner names the store it is about to serve and
warns when that store is not the main checkout's.

**`PKMNSCAN_PORT` OVERRIDES, the same knob and shape as `PKMNSCAN_HOME`.** An unparseable or
out-of-range value is **ignored rather than obeyed**: a typo must not put the server on a port
no client will look at, which is this entry's own failure arriving by another road.
`VITE_CAPTURE_SERVER` still outranks the derived default on the client, because that is the
operator's explicit override and the case `docs/specs/capture-app.md` §11 leaves open — the
Fulfiller's device pointed at this Mac by address.

**WHAT THIS DOES NOT DO: it does not give worktrees a shared store.** Each still has its own,
still usually empty, and that is D13's "one truth on the Mac" holding — the truth is the main
checkout's. A worktree that wants to work against real data points `PKMNSCAN_HOME` at it
deliberately, which is a decision with a visible env var rather than an accident of which
process bound a socket first.

**What would reopen this: wanting one capture server for every tree.** The honest shape then
is one server on 8000 with `PKMNSCAN_HOME` pinned to the main checkout and the worktrees'
clients pointed at it by `VITE_CAPTURE_SERVER` — which is the knob that already exists. That
is a different decision about where the truth lives, not a tweak to this one.

**ONE FILE WAS MISSED AND IT WAS THE ONE A HUMAN LOOKS THROUGH: `.claude/launch.json`** (found
and fixed 2026-08-30, immediately after this entry landed). It was tracked, and it hardcoded
`"port": 5173` — right in the main tree and wrong in every linked worktree. `vite.config.ts`,
`playwright.config.ts`, `server/capture_server.py` and `app/src/server.ts` all moved onto the
derivation; the Browser pane's own launch config did not, so `preview_start` would start THIS
tree's dev server on its own port and then open a tab on 5173.

**That is this entry's own defect wearing a different hat, and the worse half of it.** A dead
tab is a nuisance. A tab on 5173 while the main tree's `make dev` is up is a worktree
**previewing main and looking like it worked** — the same silent-wrong-answer shape
`app/devPort.ts` records for `make design-check`, which that file calls "the worst shape a
check can fail in, because the only signal it gives is the one you were hoping for."

**A tracked file cannot hold a per-checkout value, so it stopped being tracked.**
`.claude/launch.json` is gitignored and written by `make launch-config` from
`server/ports.py` — the same derivation the other four read, so all five cannot disagree. It
hangs off `make venv`, which is already the documented first step in a fresh clone and is what
`make worktree-setup` calls; it is a standalone target as well, because **the port follows the
PATH** and a renamed worktree needs it written again.

**The precedent is `.claude/settings.local.json`, already gitignored beside it.** The split
inside that directory is not new: what every checkout shares is tracked, what one machine or
one checkout answers is not. Nothing in the repo reads `launch.json` — no doc names it, no
audit check resolves it — so this cost nothing but the file.

**What this gives up, stated because it is a real trade:** a fresh clone has no launch config
until `make venv` runs, where before it had a wrong one immediately. That is the right
direction for a file whose only failure mode is pointing somewhere plausible and wrong.

---

## D44 — an iCloud conflict copy is refused at the commit and never deleted on a guess

**BUILT 2026-08-29, and it is a decision about an ENVIRONMENT rather than about the product.**
This repo lived in iCloud Drive until later the same day (see the amendment at the foot of this
entry). iCloud resolves a same-file race by writing a second file beside the original with
`" 2"` appended to the stem — `pre-push 2`, `githooks-selftest 2.sh`. Three appeared in one
afternoon. The owner was moving the repo off iCloud; this entry is what held until they did,
and it costs nothing afterwards.

**IT HAD ALREADY DONE DAMAGE TWICE BEFORE ANYTHING GUARDED IT.** `make hooks` copied
`scripts/githooks/*` and installed **five hooks from three files**, two of them untracked and
reviewed by nobody — git dispatches on exact names so it would not have run them, but the
mechanism put unreviewed code into the hook directory. And `githooks-selftest 2.sh` failed a
commit on the repo-map orphan rule, which is the *good* outcome and only happens inside a
mapped directory with a declared suffix.

**THE THIRD FAILURE IS THE ONE WORTH RECORDING, because it is not about file names at all.**
An in-place overwrite of `server/ports.py` left iCloud serving **stale bytes to Python's
import machinery**: in one interpreter, `open(path).read()` returned the new file and
`import` ran the old one, with no `__pycache__` present and `-B` set. A test that had just
been mutated read as passing against code that was no longer on disk. The mitigation is a
same-directory stage plus `os.replace` — a rename swaps the inode and cannot be served
stale — and it is why `scripts/status.py`'s helper preserves mode as well, having dropped
`+x` from a SessionStart hook on its first outing.

**THREE RESPONSES, GRADED BY HOW SURE WE CAN BE:**

- **`make hooks` installs only what `git ls-files` returns.** Not a guess — a hook directory
  whose contents are decided by what is lying on disk has given up the reviewability that is
  the reason those files are tracked at all.
- **The pre-commit hook REFUSES a staged conflict copy.** They are untracked, so they are
  invisible until something says `git add -A`, which is exactly what an agent session says. A
  committed `foo 2.py` is a second copy of a module no import reaches and no test runs, read
  later as a file somebody meant to write. `PKMNSCAN_DUPES=off` is the bypass, for the
  deliberate `Section 2.md` nothing in this repo has yet needed.
- **`make icloud-sweep` deletes ONLY a copy that is byte-identical to its original**, and
  reports every differing one without touching it. That asymmetry is the whole design.
  Identical means iCloud copied a file that still exists unchanged, so there is nothing in it
  to lose. Differing means it is not provably a duplicate — it may be the newer of two real
  edits, and this script cannot know which. Guessing there would be the one way a cleanup tool
  destroys work.

**IT IS NOT IN `make check` AND NOT IN THE GIT HOOK.** D18 at its strongest: it is the only
target in this repo that can delete a file. It is also not a defect to *have* conflict copies
— the commit path already refuses them — so failing `check` would gate a tidy-up on something
the filesystem creates on its own schedule. `make status` reports the count, which is where a
fact you should know but need not act on belongs, and is silent when there are none.

**What retires this: leaving iCloud Drive.** The sweep then finds nothing forever, the
pre-commit rule costs one grep per commit, and the `git ls-files` enumeration in `make hooks`
is correct on its own terms and stays regardless.

**THAT CONDITION FIRED ON 2026-08-29. The repo is at `~/Developer/pkmnscan` and nothing in this
entry is deleted.** The paragraph above is the whole disposition and it was written to be
executed rather than re-argued: `make icloud-sweep` reports `no conflict copies` and will go on
doing so, the pre-commit rule is one grep, and `make hooks` enumerating `git ls-files` was never
about iCloud in the first place. So all three stay armed.

**Kept rather than retired, and the distinction is what this amendment is for.** A guard that
costs a grep is not worth the argument it takes to remove, and the hazard is a property of a
DIRECTORY rather than of this project — the repo could move back, a checkout could be made
inside a synced folder on another machine, and the same `foo 2.py` would appear with nothing
watching for it. What IS retired is the urgency: this entry no longer describes the environment
the work happens in, and a session reading it should treat the three failures below as an
account of what the guards were built from rather than as conditions live today.

**The one thing that genuinely ends is the stale-import hazard**, because it was never about
file names: `os.replace` in `scripts/status.py`'s helper is correct on its own terms and stays,
but the failure it mitigates — iCloud serving an interpreter bytes that are no longer on disk —
cannot happen in a directory nothing syncs.

---

## D45 — The copies list is a way back into the walk, and the filter yields to the jump

**BUILT 2026-08-29, from the owner's question**: *"on the inventory tab, would it be easy on the
preview of copies, for clicking that to redirect me to that copy's photo (thereby switching the
box im viewing etc) essentially a backroad way of getting around?"*

**D7's MAP WAS A READ-ONLY ANSWER, AND THAT IS THE WHOLE OF WHAT THIS CHANGES.** Every copy of a
card sits at its own position and `CardLocations` has drawn them since the order flow — three
copies, three boxes, three position labels — with no way to get to any of them but reading the
box number off the row and pressing that cell on the strip. The walk already draws the
photograph, the facts, the queue block and the box operations for whatever it points at, so
moving the mark is the ONLY thing a press has to do; everything the owner asked for follows for
free.

**THE LABEL IS THE CONTROL AND THE ROW IS NOT.** The row already holds `Mark sold` and the
retire door, and a button inside a button is invalid markup — which is the same constraint that
put `aria-current` on the `<li>` rather than on anything pressable. The label is also the better
target on its own terms: `Box 7 · Section 1 · Card 40` is both the affordance and the statement
of where the press is about to go. It renders through the identical class in both branches, so a
walkable row is not louder than a look-only one; what the button adds is `cursor`, an underline
on hover and focus, and `Walk to <position>` as its accessible name.

**IT IS ABSENT ON THE CURRENT COPY AND ON A POOLED ONE.** The first is where the walk already
stands. The second is D24: a code card is a count rather than a location, so there is no slot to
walk to and that cell is carrying the pooled fact instead of a position.

**`BoxBrowse` GAINS ONE INBOUND PROP, WHICH IS THE MIRROR OF `onSelect`.** `goTo: { key, at }`.
The two shapes declined: an imperative ref handle, which hides a state change inside a method
call; and lifting `selected` into `Inventory.tsx`, which hands a page the walk's own bookkeeping
— the four effects that keep the mark inside the filter, the shelf and the fold. The counter is
there because the same copy can be asked for twice — walk to it, arrow away, press it again —
and because a request already answered must not be replayed by a re-render of the caller.

**THE FILTER IS THE FAILURE THIS ENTRY IS MOSTLY ABOUT, AND IT WAS MEASURED RATHER THAN
REASONED.** Under a query the walk holds only matches, and the two follows-the-filter effects
move the mark to the first visible row whenever the selection is not among them. So a jump to a
card the query does not reach lands on **whatever card is first**, under its own photograph,
with nothing on screen saying the wrong one was reached. Observed, by removing the guard and
running the case: pressing `Walk to Box 7 · Section 1 · Card 40` drew `Box 2 · Section 1 ·
Card 1`.

**IT IS REACHABLE FOR ONE REASON AND THE REASON IS WORTH KEEPING.** `do_search` renders a SKU's
group WHOLE — every copy, including ones that did not match the query — so a copy of a matched
SKU is always inside the walk's own filter. **The `sku: null` group is the exception**: it is
built from the cards that matched THEMSELVES, and a named, never-emitted card is most of this
store today. Two copies of one name in two boxes and a query that reached only one of them is
the live case.

**SO THE QUERY IS DROPPED RATHER THAN THE JUMP.** The owner pressed a position; the filter was a
way of finding it, and it has been found. Clearing re-runs the landing with the whole walk to
land in, which is why the request is held in state rather than answered in one pass.

**THE JUMP OPENS THE LANDING'S SECTION ITSELF, and that is not what the
mark-is-never-hidden rule already does.** That effect runs a commit later and the scroll's
dependencies do not include the folds, so a jump that left the opening to it lands on a row the
scroller never scrolls to. Measured on a forty-card box: viewport ratio 0. The landing effect is
declared AFTER both fold effects for the same class of reason — clearing a query fires the
collapse-everything effect in the same pass, and last means the open is the final word.

**WHAT IT COSTS IS THE TICKS, NAMED RATHER THAN DESIGNED AWAY.** A shelf change clears the
mass-select (D31: the selection is box-scoped because the write it feeds is), so walking to a
copy in another box discards a selection that may have been on its way to `#/runs` via D39's
handoff. It is the same cost a box-chip press already carries; what is new is that the gesture
looks like a click on a row rather than a click on a box. The mitigation is the control itself —
the thing pressed prints the box it is going to.

**A KEY THE WALK DOES NOT HOLD DOES NOTHING.** The copies come from `GET /search` on every
selection and the walk from `GET /inventory` at mount, so a card deleted from another device
sits in one and not the other until a Reload. Naming it would need a refusal channel out of a
component that reports three things upward and takes one back; the press doing nothing and the
Reload beside the list being the remedy is the honest cheap answer.

**IT DOES NOT REACH THE FULFILLER, and that is D31's downstream rule rather than an omission.**
`onGoTo` is optional and owner-skin only; his view has no walk to move. The gallery passes
nothing. The lone-copy fallback passes nothing either — that copy IS the card the walk is
standing on.

**THIS PARAGRAPH WAS WRITTEN AGAINST A PREMISE THAT NO LONGER EXISTED BY THE TIME IT MERGED, AND
THE CORRECTION IS THE USEFUL PART.** It read *"D41 IS UNTOUCHED — that entry rules that the three
sites drawing `Position.label` are decided one at a time, and this changes none of them:
`.card-locations-label` renders the same string through the same class at the same size"*. Both
halves went stale in the hours this branch was out: D41's amendment took the treatment to **six**
owner sites behind `app/src/PositionLabel.tsx`, and the copies list is one of them — so
`.card-locations-label` carries the SITE rule (`--pos-slot`, the face, the colour) and renders
none of the string itself. Left standing it would have been D41's own recorded failure repeating
in the entry that cites it: a later change deleting the premise and leaving the conclusion.

**WHAT IS TRUE INSTEAD, AND IT IS A STRONGER PROPERTY THAN THE ONE CLAIMED.** The walk-to is a
TRANSPARENT WRAPPER around `PositionLabel` — same three props, no text of its own, the site's
font and `--pos-slot` inherited through it — so a walkable row and a look-only one are the same
pixels, and the copies list does not become a seventh site by acquiring a control. The one thing
the wrapper adds is hover and focus, and it is scoped to `.position-slot`, the anchor that
component already chooses, so it cannot reach the five sites that offer no walk-to.
`pipeline/join.py:Position` still composes the string and it still travels verbatim on
`aria-label`; the button's own name says what pressing it does.

**WHAT WOULD REOPEN THIS: the same affordance asked for elsewhere.** If walking to a position
becomes how the owner navigates generally, `#/review`'s position is the next site — and it is now
a decision about a shared component rather than about three copies of a treatment, which makes it
cheaper to take and easier to take carelessly. **The Fulfiller is not on that list at all**:
`PositionLabel`'s own header records that his screens never import it, `app/tests/fulfillment.spec.ts`
floors his position at >=32px plain, and D31 keeps that spec unweakened.

**THE JUMP WAS SCROLLING THE PAGE RATHER THAN THE WALK, AND IT COST THE TOP OF THE SCREEN
(the owner, 2026-08-29: *"picking from a copy of a card moves the screen down a little to where
it hides the top bars"*).** The landing effect above ends by scrolling the landed row into view,
and it did that with `Element.scrollIntoView` — an API that scrolls EVERY scrollable ancestor,
the document included.

**ON A STICKY COLUMN THAT MOVES THE PAGE WITHOUT MOVING THE ROW, which is why the press cost
something and bought nothing.** `.browse-map` is `position: sticky`, so a row inside it does not
change its viewport position when the document scrolls; the browser computes a delta from the
row's current geometry all the same, spends it on the page, and the row stays exactly where it
was. Measured at 1280x720 with the page at rest: **`window.scrollY` 0 -> 280, the document's
whole range**, putting the nav at y=-280 and this screen's own header at y=-218. The landing was
already going to be visible — the walk's own scroller had done that work — so the entire effect
of the page scroll was losing the nav, the title row, the search field and the box strip.

**THE FIX IS A CEILING, NOT A FLAG: `BoxBrowse.tsx:scrollWithin`.** It adjusts `scrollTop` by
hand on each scrollable ancestor from the row up to `.browse-map` inclusive and stops, so the
document scroller is unreachable **by construction**. `scroll-margin-top` is read off the row
rather than ignored, because `.browse-row` sets 28px to clear its own sticky section header and a
hand-rolled scroll that dropped it would park every landing underneath that header. The innermost
scroller takes `start` and every outer one takes `nearest`: `start` is a statement about where the
row sits in the LIST, and asking the same of the column outside it would drag the search field and
the box strip off the top of a column that is only ever scrolled to reach the box's editors.

**THE CEILING HOLDS WITH THE BOUNDARY MISSING, and that is a separate line rather than a null
check.** The walk stops at `document.body`/`documentElement` before it consults the boundary at
all, so a ref that has not mounted yet cannot let the walk past — a ceiling that depends on a ref
being non-null is not a ceiling, and the symptom would have reappeared nowhere near the check
that failed.

**IT REACHES EVERY GESTURE THAT MOVES THE MARK, not just the walk-to**, because they all land in
one effect: arrow keys, PageUp/PageDown, Home/End, a box-chip press and a search landing. Verified
against the owner's own store — a walk-to across 133 real cards moves `.browse-list` 1242px and
the page zero, and a box-chip press from y=5 leaves the page at y=5.

**`focus()` IS THE SAME DEFECT'S SECOND DOOR AND IS SHUT WITH IT.** Two presses hand the keys to
the walk, and `HTMLElement.focus()` scrolls the focused element into view by default — the
document included. Measured, neither fires today: the column is sticky at the top of the viewport,
so the list it holds is already on screen whenever these run. Latent rather than live, closed for
one object, and recorded here so it is not read as belt and braces: `scrollWithin` owns where this
component scrolls and nothing else in it may.

**A COMMENT THAT ARGUED FOR THE DEFECT IS CORRECTED RATHER THAN DELETED.** The landing effect
ended *"and the page scroll this brings with it is wanted here: the copies list is below the card
band, and the photograph is what was asked for."* The intention was right and what happened was
its opposite — the scroll came from the landed ROW, so it moved the page DOWN, away from the card
band. Kept in the file with that account attached, because a comment that reasons its way to the
wrong behaviour is more useful than a missing one.

**Asserted as a MEASUREMENT rather than as a class name**: `app/tests/inventory.spec.ts` reads
`window.scrollY` and the nav's own `top` before and after the press and requires both unchanged,
AND requires the landed row in the viewport — either alone is satisfiable by doing the wrong
thing, since a screen that scrolled nothing and landed nowhere would pass the first and the old
code passed the second. Observed red against `scrollIntoView` before it was kept.

**One trap on the way, worth keeping because it wasted the first attempt.** Playwright's own
`.click()` scrolls its target into view first, so the first version of this measurement read 280
both before and after and proved nothing. The case dispatches the press instead.

---

## D46 — A card the pipeline could not place is offered the catalog, and a human may point at a row

**BUILT 2026-08-29, and the owner found it from the far end.** Shown three cards rescued by
D35's name rung, they asked why the fourth was still a dead end and why the screen said nothing
useful about it: *"it should've brought up what cards it could have matched too (along with
letting me literally just enter in what it is)"*.

**THE DEAD END WAS REAL AND IT WAS TOTAL.** A queue entry with no candidate rows cannot be
answered — `POST /review/<box>/<index>/answer` refuses it as `no_candidates` — so the only two
moves were Skip, which writes nothing and asks the same question next session forever, and
D37's stand-down, which closes the question rather than answering it. Neither one lists the
card. The row was in the export the whole time.

**THE CASE THAT REOPENED IT IS THE ONE THE OLD REFUSAL SAID DID NOT EXIST.** That refusal
argued from evidence and named it: *"Every one of them wanted a re-export or a re-shoot, never
a typed SKU, so the refusal stands on the evidence it asked for."* True of the cards it was
written about. Box 1 position 108 is not one of them. Its photograph is **good** — measured at
2160x3840 with mean luma 72.2, statistically indistinguishable from two copies of the same card
that read perfectly — and `Master Yi, Wuju Master` came back as `Wuju Master`, the champion
dropped. A re-shoot repairs nothing, a re-identify is a coin toss, and a person looking at the
card can see what it is.

**IT IS NOT A FREE-TEXT PATH INTO THE FIELD THE HARD RULE PROTECTS, AND THAT IS THE WHOLE
DESIGN.** The operator never types a SKU into a card. They pick a ROW, and the server re-reads
that row **out of the export this card was joined against, inside the write lock**, before
anything is written:

- an unknown SKU refuses as `sku_not_in_catalog`;
- the **condition is taken from the row, never from the request** — a client that sends the
  wrong one gets the right one rather than an error, so the SKU is the only thing the request
  decides;
- and `from_catalog` reaches only an entry with **zero** candidates. An entry with rows of its
  own still answers only from those rows, so the anti-laundering refusal is untouched.

The property the old guard protected — that no string a client sends can become a listing on
its own — is therefore unchanged. What changed is that a human may point at a row the pipeline
failed to find, instead of only being able to walk away from it.

**THE EDGE IS ON THE CARD, NOT ON THE QUEUE ENTRY, and that is what makes the lookup exact.**
`store/queues.py:QueueEntry` records no run, no game and no export, and `Queue.parse` drops any
key it does not declare — so nothing about a run can be written into `review.json` without a
schema change. `master.Card` has carried `run` since identification wrote it and `game` since
D21, and the answer path already loads the card. So: card -> run -> that run's manifest -> the
export for that card's game. Guessing the run by scanning `runs/` for one whose scope covers
the box was the alternative and it is **unsound**: two runs on this machine touch box 1,
`first_seen` is date-only, and `Queue.upsert` preserves it across re-joins. An exact edge that
is sometimes absent beats an inferred one that is always present and sometimes wrong. Every way
it can be absent is a named refusal — `no_run_recorded`, `run_not_found`, `no_export_for_game`,
and `export_missing`, which is the legacy case: a join driven from a terminal records the
`--export` path it was handed, typically `~/Downloads/...` and often gone, while a join driven
from the app uploads the bytes into the run.

**THE MATCH IS LOOSE IN BOTH DIRECTIONS AND IS ALLOWED TO BE, because it decides nothing.**
`CLAUDE.md` forbids the JOIN to match on Product Name, and that stands — this is not the join.
It ranks rows for a person to choose between, so a loose match costs a row on a list rather
than a wrong card in an import file. Measured on that export: **490 of 494 epithets identify
exactly one product, against 38 of 98 champion names**, and the same run truncated in both
directions (`Wuju Master` three times, `Master Yi` twice). So both directions are offered and
neither is trusted without a human looking at the photograph.

**THE ROWS GO WHERE THE CANDIDATE ROWS GO, and are answered on the same digits.** Not a panel
below them: `ReviewQueue.css` holds that nothing may come between the sentence and the rows,
and these ARE the rows — found by a lookup rather than by the join, drawn through the same
markup. One vocabulary rather than two, because whether the pipeline or the catalog found a row
is not something the finger needs to know. The search box is a form, so Enter submits it, and
`isEditableTarget` is what stops a typed `1` from answering the card — asserted as a negative
case, because nothing in the type system says so.

**THE HISTORY LINE CARRIES `from_catalog`, and only when it is true.** `_history` drops a None
extra, so every line already on disk keeps its exact shape. A row the PIPELINE offered and a row
a HUMAN went and found are different claims about how much the machine knew, and after the write
there is no other evidence which happened.

**THE STALE COPY WENT WITH IT.** That arm drew one paragraph saying the only move was to skip
and pointing at a command in a terminal. D37 had put a stand-down on this very screen months
earlier and the copy never mentioned it — the one place that most needed to.

**What would reopen this: the flag being used on cards that had a good answer available.** If
`from_catalog` starts appearing on answers for cards whose export row a better join would have
found, the fix is upstream in the join, not more catalog searching. `_strip_set_code` is the
first instance of exactly that: three of box 1's four dead ends turned out to be a set code
glued to a correct identifier, and code now recovers them without a human at all.
## D47 — A tracked symlink is a path baked into the tree, and a checkout will spend a directory to place one

**BUILT 2026-08-30, after a `git merge --ff-only origin/main` in the main working tree replaced
the 133 MB eval-image mirror with a link pointing at itself.** No file was written by hand and no
script misbehaved: the checkout did exactly what it was told, and what it was told was wrong.

**THE DATA CAME BACK, AND THE ENTRY IS WRITTEN AS THOUGH IT HAD NOT.** iCloud Drive restored the
directory from its own copy about ten minutes later — 150 images and the manifest, intact, and it
removed the empty conflict copy it had made in the meantime. That is luck wearing the clothes of
a backup: the same sync layer D44 exists to defend against is what happened to be holding the
only other copy. On a machine without it the loss is permanent, and the remedy would have been a
151-file re-download rather than nothing at all only because D15 makes this data derived. **The
first draft of this entry said the mirror was deleted, because that was true of every observation
available for ten minutes.** Corrected rather than quietly softened, because the mechanism is
unchanged by the recovery and is the reason the rules below exist.

**THE MECHANISM, WHICH IS THE WHOLE VALUE OF THIS ENTRY.** `scripts/worktree-guard.sh`
provisions a linked worktree by symlinking two gitignored things to the main tree —
`app/node_modules` and `harness/images`. Correct there, and necessarily an **absolute path**.
Then:

1. `.gitignore` said `node_modules/` and `harness/images/`. **A pattern ending in `/` matches
   directories only**, and git does not count a symlink as a directory — so neither link was
   ignored in a worktree, and both were invisible to a reader who had just read the ignore file
   and concluded they were covered.
2. A session ran `git add -A` and committed both, as mode `120000` blobs whose contents are an
   **absolute path on one Mac** — the main working tree's own location, followed by the same
   two names.
3. In the **main** working tree those paths name the links' own locations. Checking the commit
   out there makes each one a symlink to itself, and **git removes an ignored file or directory
   that stands in the way of a checkout without asking**. The real directories were ignored, so
   they were removed.

**WHAT IT COST, MEASURED.** `harness/images` — 133 MB, 150 eval images and the manifest that
labels them — was replaced by a self-referential link at 20:13 on 2026-08-29, with an empty iCloud
conflict copy (`harness/images 2`) beside it. Every worktree linking to that path went dangling
with it. T1 failed with a `FileExistsError` from `IMAGES_DIR.mkdir(exist_ok=True)`, which is what
`mkdir` does when the path exists and is not a directory: **the error names the symptom and says
nothing about the cause**, which is why this took a full investigation rather than a glance.

**`app/node_modules` WAS IN THE SAME TRAP AND SURVIVED BY ACCIDENT.** The pull that detonated
the images also carried a commit that had removed the node_modules entry from the index — for an
unrelated reason, while cleaning a merge — so the add and the delete cancelled and git left the
real directory alone. An accident is not a guard, and this entry is what replaces it.

**THE FIX IS THREE THINGS, AND ONLY THE THIRD IS NEW MACHINERY.**

- **`harness/images` is untracked.** It was the only tracked symlink left in the tree.
- **Both ignore patterns lose the trailing slash** — `node_modules` and `harness/images` — so
  they match a link as well as a directory. That is the one-character fault at the root of it,
  and it is now stated in the file with the reason attached.
- **The pre-commit hook refuses a staged symlink that leaves the repository.** It reads mode
  `120000` out of the index rather than guessing from a name; an absolute target is refused
  outright, and a relative one is refused when it climbs out of the tree. **A relative link that
  stays inside is allowed**, because that is the only kind that survives a clone on another
  machine — which is the property actually being enforced. `PKMNSCAN_LINKS=off` bypasses, in
  the shape the iCloud-duplicate rule beside it already uses.

**AND THE MIRROR MOVES OUT OF iCLOUD, WHICH IS THE OWNER'S CALL AND NOT A CONSEQUENCE OF THE
BUG.** `PKMNSCAN_IMAGE_MIRROR` has been documented since build-order step 9 was written and read
by nothing; `harness/eval/fixtures.py` honours it now, and the allowlist entry that carried it as
a documented-but-unbuilt name is retired the moment it came true, exactly as D16 requires. The
default is unchanged, so a tree that sets nothing behaves as it always did and every banked score
stays comparable. The reason for moving it was D44's: this repository sat in iCloud Drive, and
133 MB of derived binaries syncing there is what produced the conflict copies that entry refuses.

**AND MOVING IT GIVES UP THE THING THAT JUST SAVED THE MIRROR, WHICH IS THE HONEST WAY TO RECORD
THIS TRADE.** iCloud's copy is what restored the directory above. Outside it there is no second
copy and no version history — the recovery path becomes the re-download, which is exactly what
D15 says this data is for: derived, reproducible, and never the artefact worth keeping. The
trade is a safety net that costs conflict copies, against a clean tree whose worst case is one
download. The owner took the second.

**THE MIRROR CAME HOME ON 2026-08-29, HOURS AFTER IT LEFT, BECAUSE THE REPO LEFT iCLOUD AND TOOK
THE WHOLE REASON WITH IT.** `PKMNSCAN_IMAGE_MIRROR` is unset, `harness/eval/fixtures.py` falls
back to its own default, and the 152 files sit at `harness/images` where every version of this
project before 2026-08-30 expected them. Measured after the move: `IMAGES_DIR` resolves in-repo,
152 entries with the manifest, `make harness` all 7 passed, `make ignore-check` green.

**BOTH PARAGRAPHS ABOVE ARE VOID AS DISPOSITIONS AND KEPT AS REASONING, AND THE SECOND ONE IS WHY
THIS WAS CHEAP TO REVERSE.** The trade it records — a safety net that costs conflict copies,
against a clean tree whose worst case is one download — had exactly one term on each side, and
leaving iCloud zeroed both at once. There are no conflict copies to pay because nothing syncs the
directory, and there is no safety net to give up because there was none left to lose. A decision
whose two arguments both evaporate is not a decision that has to be re-argued; it is one whose
premise is gone, and the honest move is to put the data back where the default already pointed.

**WHAT SURVIVES, NAMED SO NOTHING IS UNPICKED WITH IT.** Three things landed under this heading
and only one of them was about iCloud:

- **The knob stays and is still honoured.** D15 authored `PKMNSCAN_IMAGE_MIRROR` for the
  mirror's SIZE, not for its sync status, and ~16.7 GB at full catalog is still the reason
  which disk it lands on is a choice worth having. Unset is not unbuilt: the code reads it, the
  allowlist entry stays retired, and a tree that wants the mirror elsewhere sets one line.
- **The provisioner still ASKS rather than assumes.** `scripts/worktree-guard.sh` running the
  main checkout's `fixtures.py` to learn where the mirror is was written because the move broke
  it, and it is correct whatever the answer — including today's answer, which is the in-repo
  default it used to hardcode. Reverting it would restore the silent skip, not the old code.
- **`harness/images` keeps its type-agnostic ignore pattern.** That is D47's own subject and has
  nothing to do with where the bytes live: the pattern exists so a worktree's SYMLINK at that
  name is ignored, which is the fault this entry opens with. A directory there now makes the
  pattern matter more, not less.

**What would reopen this: the repo going back into a synced folder.** Then D44's hazard returns
and the mirror is the largest thing in the tree that would sync, so moving it out is the first
remedy to reach for — and it is one line in `.env`, which is the whole point of leaving the knob
alone.

**WHAT THIS DOES NOT DO.** It does not stop `worktree-guard.sh` making the links — they are
right, and they are what keep T1 from re-downloading 151 files per worktree. It does not make
symlinks a bad idea. It stops one of them being **committed**, which is the only step in the
chain where a local convenience becomes every checkout's problem.

**IT ALSO BROKE THE AUDIT ON ITS WAY IN, AND THAT DEFECT WAS OLDER THAN THIS ENTRY.** Writing
the paragraphs above put the string `app/node_modules` into a doc, which made it a path
candidate — and `scripts/docs-audit.py:ignored_paths` probes missing candidates through
`git check-ignore --stdin`, which **exits 128 and stops** on a pathspec it refuses. A
provisioning symlink is exactly such a pathspec (*"beyond a symbolic link"*), so the batch
aborted and every candidate after it lost its answer. The audit then blocked the commit over
`harness/.cache/` in `docs/GATES.md` — a reference that was correct, unchanged, and in a
different file.

**A BATCH THAT DID NOT RUN CLEANLY IS NOT EVIDENCE ABOUT ANYTHING.** check-ignore's contract is
0 when something matched and 1 when nothing did; any other code means it gave up. It now falls
back to asking one candidate at a time so a refusal is contained to the candidate that caused
it. The failure mode this replaces is the worse kind: not a check that misses something, but a
check that **reports a defect in a file nobody touched**, which is what sends a session
investigating the wrong doc.

**MOVING THE MIRROR BROKE THE PROVISIONER, AND THE PROVISIONER SAID NOTHING** (found 2026-08-30,
by a Stop hook that failed T1 in a worktree whose main checkout was healthy). This entry moved
the mirror out of iCloud behind `PKMNSCAN_IMAGE_MIRROR` and did not look at the one script whose
job is to give a worktree that mirror. `scripts/worktree-guard.sh` and `make worktree-setup` both
read `[ -d "$main/harness/images" ]` and linked THAT path — and after the move the main checkout
has no `harness/images` at all, so the precondition went false and both blocks were skipped
whole. **Neither printed anything**: the only failure message sat on the `ln`, and the `ln` was
never reached. A fresh worktree then downloaded 151 images at its first `make harness`, which is
the exact cost the guard's own header says that line exists to avoid.

**THE FIX IS TO ASK RATHER THAN TO ASSUME, AND THE THING ASKED IS THE ONE RESOLUTION.** Both call
sites now run the MAIN checkout's own `harness/eval/fixtures.py` and link to whatever
`IMAGES_DIR` answers — env var, then that checkout's `.env`, then its in-repo default. Re-deriving
that precedence in shell is how the two drift apart a second time, and `fixtures.py` is stdlib-only
at module scope so a bare `python3` can answer it. The script never reads `.env` itself; `envfile`
does, and the only thing crossing the pipe is a path. Where there is no mirror to link, it now
SAYS so — the silent skip was the defect, not the missing link.

**That resolution answers `harness/images` again as of 2026-08-29**, the mirror having come home
with the repo (see the amendment above). The fix is untouched by that and must stay: what it
replaced was a hardcoded path that happened to be right, and it is exactly as wrong to hardcode
a path that happens to be right today.

**AND THE PATH BELONGS IN `.env`, NOT IN A SHELL PROFILE.** Tried and reverted the same day: an
export in `~/.zshenv` fixes an interactive session and does nothing for the Stop hook, which runs
`scripts/stop-gate.sh` under **bash** — a shell that reads no zsh profile and, spawned from an app
started before the export existed, inherits nothing either. `.env` is what every reader of this
repo already consults regardless of shell, and `envfile.get` still lets a real environment
variable win. Two records of one path is also the drift this file dislikes: a stale export would
outrank a corrected `.env` and point at a mirror that had moved.

**WHAT WOULD REOPEN THIS: a third provisioned path.** The guard is general — it refuses by mode
and by target, not by name — so a new link is covered the day it is added. What is not covered is
the reverse direction: a path that ought to be ignored and is not, which is what let the first
one through. `git check-ignore` over the provisioned set, run somewhere off the commit path,
would close that half.

**IT REOPENED THE SAME DAY, BY THE REVERSE DIRECTION THIS PARAGRAPH NAMED, AND THE OTHER HALF IS
NOW BUILT (2026-08-30).** Two of the four provisioned paths kept their directory-only patterns —
`harness/.cache/` and `.venv/` — on the reasoning that `scripts/worktree-guard.sh` COPIES the
first and BUILDS the second, so neither is ever a link. That reasoning is sound about the script
and says nothing about the path. A session that provisioned a worktree by hand linked both, and
got this entry's own state straight back: **untracked rather than ignored**, one `git add -A`
from committing an absolute path into one Mac.

**It also broke something this entry did not predict.** `scripts/docs-audit.py`'s ignore filter
exists so a gitignored path is not reported as a dangling reference — and it had nothing to
match, so every doc reference to `harness/.cache/` read as a broken path and the pre-commit hook
blocked a commit over two of them. That is the audit being right for the wrong reason: the
reference was fine and the ignore was not.

**So the rule is about the PATH and not about today's provisioning.** All four patterns are
type-agnostic now. The precision a trailing slash buys is worth nothing on a name nothing else
in the tree bears, and it is worth less than nothing when it silently depends on a script's
current behaviour staying what it is.

**AND `make ignore-check` IS THE GUARD THIS ENTRY ASKED FOR**, doing exactly what the paragraph
above specified: `git check-ignore` over the provisioned set, asserting each is ignored **as a
file, as a directory and as a symlink**. It is in `make check` and deliberately NOT in the git
hook — D18's rule, and a second reason of its own: what it checks is a property of the local
worktree's provisioning, so a fresh clone with none of these paths present would fail a commit
over something that is not wrong. Off the commit path is where a check about local state belongs.

---

## D48 — A send is a cart of boxes; a run is still one box

**BUILT 2026-08-29, on the owner's instruction after being told what the pipeline could and
could not already do.** Their words: *"I want to be able to multi select and have them all send
at one time"*, and then, when the first answer proposed one run spanning several boxes,
*"why couldn't the bypasses be at a per box level, and then they join a 'queue to Haiku' and
then there's a further button that batch sends all the individualized boxes at the same time?"*

**THE OWNER'S SHAPE WAS BETTER THAN THE ONE PROPOSED TO THEM, AND THE CORRECTION IS THE USEFUL
PART.** The first recommendation was ONE RUN over several boxes, on the argument that `join`
already reasons per box (D36's realign does), that `sidecar.scan` already parses `box3-0017.jpg`,
and that emit aggregating across boxes gives one import file per game instead of several. Every
one of those facts is true and none of them is the deciding one. What decides it is that a run
carries a **reading**, a `--bypass` ruling and a `decisions.json`, and all three are properties
of what is IN the drawer — so one run across three boxes forces one answer to three questions
that deserve three. The owner's word for it was *"individualized"*, and it is the right one.

**SO THE CART IS THE REQUEST AND THE RUN IS UNCHANGED.** `POST /pipeline/identify` takes
`scopes: [{box, indices?, crop?, max_edge?}, ...]` and spawns one detached child per box. Every
box gets its own run directory, its own manifest scope, its own queue, its own join and its own
pricing answer. Nothing downstream learns a new shape, and that is the property worth protecting:
`cli/runs.py`, `join`, `emit` and `reconcile` were not touched by this entry at all.

**ONE ROUTE STILL SPENDS, WITH ONE `confirm` AND ONE TOTAL.** Two alternatives were declined for
the same reason. A second route beside the first would double the surface D33 spent a whole entry
putting behind one door. N calls from the screen would be N confirms for one operator decision,
which is the two-step money gate satisfied in letter and broken in substance. One press, one
request, one `confirm`, one estimate on screen above it.

**THE TOTAL IS SUMMED ON THE SERVER, AND A MISSING FIGURE POISONS ITS SUM.** `app/src/server.ts`
already records that the app may not compute rules the pipeline owns, and this is the sharpest
case: the total is the number the operator agrees to spend. `_parse_preflight` answers `None`
where a line did not appear — deliberately, so a changed preflight shows as a missing figure
rather than a confident zero — and a sum that skipped a `None` would undo that at the one moment
it matters, by understating what a press is about to buy.

**A BARE `box` READS AS A CART OF ONE, AND NOTHING EVER WRITES ONE.** The read-side widening D3's
amendment gives the finish claim and D21 gives `game`, for the same reason and with the same
boundary: the harness, a terminal, and every request written before today resolve down the
identical path with no migration and no second spelling on the wire. The RESPONSE is always a
list too — a shape that changed with the request would make every reader ask which one it got
before it could ask anything else.

**EVERY LEG IS RESOLVED BEFORE ANY IS ACTED ON, AND A REFUSAL TEARS DOWN WHAT IT BUILT.** D29's
validate-everything-then-write-everything with an invoice instead of a queue answer: a bad flag
on the fourth box refuses the whole send rather than leaving three boxes identifying. Because
`_resolve_scope` creates a symlink directory per ticked selection, a refusal also removes the
ones earlier legs had already made — T7 asserts, in as many words, that no scope directory
survives a refusal, and a cart could otherwise leave one per mis-typed send in the one directory
`identify` walks recursively.

**THE ONE THING THAT CANNOT BE PRE-CHECKED IS REPORTED RATHER THAN HIDDEN.** `Popen` can fail on
the fourth leg after three have started. The response names what STARTED and what did not, and
the screen draws the failures: a partial send reported honestly is recoverable by pressing again
for the boxes that did not go, and one reported as a success is an invoice nobody can account
for. Recorded here because the tempting alternative — refusing the whole response — would throw
away the names of runs that are already costing money.

**THE DOUBLE-CLICK GUARD NOW COMPARES BOXES, WHICH CLOSED A HOLE THAT HAD NO GUARD AT ALL.**
`_busy_run` resolved the incoming capture directory against each live run's recorded one. That
works for a whole box — `captures/cards/box3` both times — and cannot work for a ticked
selection, because `_scope_dir` builds a fresh `.scopes/box3-<n>-<timestamp>` on every press. Two
presses over one selection were two different paths, neither saw the other, and **the subset path
was therefore unguarded from the day it was built**. It compares box numbers now, read from the
manifest's scope first and from the capture directory's name second — and the second half is not
a fallback for old files, it is the only thing that can see a run started in a TERMINAL, because
`scope` is written by the route and by nothing else.

**It narrows what is allowed, deliberately.** Two live runs over DISJOINT selections in one box
are now refused as well. That is the case an operator cannot tell apart from a double-click at
the moment of the press, and the refusal names the run, so the answer is one click away rather
than one invoice away. Two runs over DIFFERENT boxes stay legal and unblocked — the Batch API
takes them in parallel and the cache keys them apart, which is the whole reason a cart is one
send rather than a queue.

**THE LEGS PREFLIGHT AT ONCE, AND THAT IS A LATENCY FIX RATHER THAN AN OPTIMISATION.** A
preflight decodes and crops every photograph in its box — measured at about a minute for 544
cards — so five boxes in series is a request held open for five minutes with nothing on screen.
They are separate read-only processes over a lock-free snapshot and `--dry-run` writes nothing at
all, which is the property that makes this safe rather than merely fast. Bounded at four workers,
and the cart itself at sixteen boxes: each leg is a detached child, so an unbounded list is an
unbounded number of processes started by one request. The bound is a guard against a malformed
client, not a judgement about how many boxes an operator may send.

**D39's HANDOFF RULE IS NARROWED RATHER THAN WEAKENED.** That entry drops the ticked selection
whenever a box is picked on `#/runs`, because *"a tick list that survived the operator
deliberately choosing a box is a filter they did not re-consent to, sitting over the control that
spends"*. Under a single-select every press REPLACED the scope, so every press was a re-consent
question. Adding box 7 to a cart does not touch what box 3 means, so the rule now scopes to the
carried box: un-ticking it drops the handoff, and toggling any other box leaves it alone. There
is still exactly one mass-select in the product and `#/inventory` still owns it.

**A DEFECT WAS FOUND IN THE RUN LIST ON THE WAY PAST AND IS FIXED HERE.** `RunPanel.tsx` computed
a three-way partition — live, this box, other boxes — and then rendered it only when
`scope.box === null`, which is precisely when `mine` is empty by construction. So a screen with a
box selected threw the grouping away and drew the server's order, and a screen with none drew the
groups and could caption a section `other boxes` with no box to be other than. Both halves
backwards at once, which is why neither looked wrong on its own.

**What would reopen this: a cart that is never used with more than one box.** The whole cost of
this entry is the list shape on the wire and the per-box reading state; if every send is one box
forever, the honest simplification is a single-box request again. The measurement is whether any
`POST /pipeline/identify` carries more than one scope.

---

## D49 — The pricing answer is one file, and a card can be held back on purpose

**BEING BUILT 2026-08-29, from an interview the owner asked for.** They had never been asked what
they wanted a listing price to BE — `match` on `market` was the CLI default running by accident
through every run this project has done. Their answer: *"I want all the data from the CSV shown
when I make the decision, but I actually intend to be hand-pricing for now."* And on volume, which
inverts every measurement taken before it: *"almost everything coming next is all above 0.40."*

**WHAT THAT LAST SENTENCE OVERTURNS, because a build was nearly aimed at the opposite.** Measured
across the two Pokemon runs on disk — 596 cards, 153 SKUs — the total value of every per-item
pricing decision available was **zero**: box 2's export tops out at $0.74 and stocks no Near Mint
row at or above the threshold, and Gate B's `import-listed.csv` is header-only. The honest reading
of that history is a screen whose job is to report that there is nothing to do. The owner says the
next boxes are the other thing, and the export bears out the mechanism: Near Mint **normal** is
9.5% listable, **reverse holo** 40.6%, **holo 76.2%**. The exception rate is a function of the
finish claim made at capture, so it is predictable before a run starts and it is about to go up.

---

**PART ONE — `decisions.json` DECIDES, AND THE MANIFEST RECORDS.** Two bugs in one seam, and the
owner's instruction on being shown them was *"I don't understand this it seems like some stuff is
in conflict and it shouldn't be, resolve this."*

- **`emit` priced from the run MANIFEST and printed the rule from `decisions.json`.** So an
  operator who set `"rule": "undercut:5"` in the file got a run that printed `rule=undercut:5` and
  wrote every row at market. The file's own module docstring has called it *"the pricing decision,
  as a file rather than as a flag"* since it was written, and `rule` was the one thing in it that
  decided nothing.
- **`join` assigned `choice.rule` and `choice.basis` back from the run** immediately after printing
  *"merging into existing decisions.json — your edits are kept"*. Measured: `markup:100` on `low`
  reverted to `match` on `market` on a plain re-join while `sub_threshold` beside it survived — so
  the file looked merged and was not. `join` is free and re-runnable and is re-run routinely, so
  this was not an edge case.

**The file is the authority; the manifest keeps `rule`/`basis` as the RECORD of what a join ran
with**, which `report.txt` prints. A record of what happened and the answer to what should happen
are different facts and only one of them may be authoritative. `--rule` still seeds the file on the
FIRST join, because a document that cannot answer its own question is not a document.

**Both commands now refuse `UnknownRule` and `UnknownBasis` with a sentence.** They are `ValueError`
subclasses and NOT `MalformedDecisions`, nothing above `cli/__main__.py` caught them, and
`PUT /pipeline/runs/<name>/decisions` writes this file with no validation at all — so a screen could
put a run into a state where `emit` answered with a traceback. T7's `check_pricing_authority` block
holds all of it, and both halves were **observed failing against the old code** before they were
kept.

---

**PART TWO — A CARD CAN BE WITHHELD, AND THE HOLD SAYS WHY.** The owner: *"say i'm bullish on the
price going up, and don't want to list any right now"*, and then *"definitely want someway of
flagging that i'm intentionally holding this card // am bullish maybe even price threshold etc"*.

Before this there was no way to say it. `overrides` demanded a price, `"unlisted"` was accepted only
under `no_market_data`, and a card with a market price had no representation for *not this run*.

**`overrides` gains two shapes and every existing shape stays byte-identical.** A scalar is a price.
The bare string `"unlisted"` is a hold with no reason — the spelling a terminal user types, and the
one `no_market_data` has accepted since D9. An object is a hold **with** a reason, which is what the
screen writes:

    "9114773": {"withheld": "bullish", "watch_above": "12.00", "note": "waiting on rotation"}

**A strict widening, not a new failure mode**: before this a dict reached `_price`,
`Decimal(str({...}))` raised, and it was already a clean `MalformedDecisions` rather than a
traceback.

**`withheld` AND NOT `held`, WHICH IS D26's RENAME FOR D26's REASON.** `store/master.py:Listing.held`
already means copies **TCGplayer** is holding — the opposite direction — and `_listing_hold` in the
capture server means a box may not be deleted. D26 renamed `removed` to `retired` because a state
sharing a word with an existing one makes both unreadable; this is the same call.

**THE VOCABULARY IS DISJOINT FROM THE TWO IT COULD BE CONFUSED WITH, and no word appears twice.**
`WITHHOLD_REASONS` is `bullish | keeping | next_batch`, against D26's `pulled | damaged | lost |
given_away` (the CARD left inventory) and D37's `wasted_position | cannot_settle | not_listing` (the
QUESTION was closed). `next_batch` rather than the obvious `not_yet`, because `not_listing` is
already a stand-down reason and the two read as one word at the 10px a machine string is drawn at.

**A WITHHOLD IS NONE OF THE THREE THINGS IT SITS BESIDE.** Not a retirement: the card does not move,
does not change state, keeps its slot and its photograph, and is sellable the moment the hold is
lifted. Not a stand-down: nothing is asking — the card resolved cleanly, with a catalog row and a
market price, and what is refused is the *listing*. Not a sale: no count at `pushed`, `staged` or
`live` moves. What is withheld is one run's import row, and nothing else.

**HOLDS ARE ABSENT FROM `dispositions()`, AND THAT IS THE SURVIVAL GUARANTEE RATHER THAN TIDINESS.**
`emit` refuses the whole run when that mapping names a SKU the batch does not hold, and
`prices_for` refuses again per game. A withheld SKU is precisely the one most likely to fall out of
a later run — it was withheld *because* it is not being listed — so letting holds reach those checks
would mean the act of holding a card back eventually breaks `emit` for the entire run, with no
control anywhere able to clear it. For the same reason `prices_for`'s `withheld` set carries
**no unknown-key check**, unlike the dispositions beside it.

**A HEADER-ONLY IMPORT FILE WAS ONE LINE AWAY AND IS CLOSED HERE.** `prices_for` leaving a SKU out
and `import_rows` skipping its row is correct — but `emit` decides whether to write a file AT ALL
from whether its SKU set is empty, and the writer emits the header before it iterates rows. A game
whose every listable SKU was held would have written a header-only `import-listed.csv` and reported
`listed 0 row(s)`. That is the Gate B shape exactly, and `_game_only` subtracts the holds instead.

**THE PRICE THRESHOLD IS BUILT, NOT DEFERRED, and the argument that nearly deferred it was wrong in
an instructive way.** A watch looked pointless on the grounds that it can only fire while somebody
is already looking at the price. They are not: a re-join is driven from `#/runs` (D39), and `join`
is free and re-runnable precisely so it can be pointed at a **refreshed export** — which is the only
moment a market price has moved and therefore the only moment a watch has anything to say.
`Decisions.watches(matches)` is a method rather than a `warnings` entry because `warnings` is a
zero-argument property and cannot see a price.

**A HOLD LIVES IN ITS RUN AND DIES WITH IT.** `decisions.json` is per-run, so a hold survives every
re-join of its own run — which is where it does its work, since a box is identified once and
re-joined many times — and a **second** run over the same box starts with none. That is a real limit
and the screen says so in words rather than implying it. A durable per-SKU home outside the run
directory — beside `Listing` in the store, or a standing `holds.json` beside the queue files — is
**recorded and deferred**: it is a schema change, a route and a client function, and scope is argued.

**A second cost, named because nothing else would say it.** `emit` writes a card's identity only for
SKUs that reached a file, so a withheld SKU's copies keep `state: captured` and carry no `sku` —
invisible to `GET /search` and every SKU-keyed surface until the hold is lifted and the run
re-emitted.

---

---

**PART THREE — THE SCREEN, BUILT 2026-08-30.** `#/pricing` is the seventh route, and it is where
the owner sets by hand what every SKU a run matched will list at. One row per SKU, sorted market
descending, carrying every export column that holds data — *"I want all the data from the CSV
shown when I make the decision"*. It draws no photograph on the row, no price type-size bands and
no solid accent fill; the box, the cart and the money gate stay on `#/runs`, and **nothing here
spends**.

**AFTER THE REVIEW QUEUE AND NOT BEFORE IT**, which is the owner's ruling and reverses what the
first design pass proposed. Answering the queue changes what the next join resolves, so pricing
before the queue is worked prices a set that is about to move.

**THE SUGGESTION WRITES NOTHING, AND THAT IS THE LOAD-BEARING DECISION OF THE WHOLE SCREEN.**
The run's rule prefills every row as a visible suggestion; the first digit typed clears it, Enter
commits and advances, and `m`/`d`/`l`/`s` snap the price to a named export column. But an
untouched row writes no key at all — because an override is layer 1 of the ladder and beats the
rule at layer 4, so a screen that wrote its hundred suggestions would produce a run where
**changing the preset silently changed nothing**. That failure has no symptom. `pipeline/
decisions.py` states the rule it rests on in one line: *"Nothing here is ever defaulted on your
behalf — that is the entire point."* If a later session finds itself wanting a *write all
suggestions* button, that button is this defect.

**THE KEYBOARD WORKS WITH THE HANDS IN A FIELD, WHICH NO OTHER SCREEN HERE DOES.** Every other
handler in the app returns on `isEditableTarget`; on this one the hands are in a price field
essentially always, so that rule would make every letter dead. What makes it safe is that the
field's alphabet is CLOSED — `[0-9.]`, one dot, two decimals, enforced at `beforeinput` — so a
letter is unambiguously a command and there is nothing to disambiguate. That closure is the
entire safety argument and may not be widened without taking the keyboard with it.

**A PRESET PRICES WHAT IT CAN AND NAMES WHAT IT COULD NOT** (the owner's ruling, over refusing the
whole press). Measured: 394 of 2,476 listable rows in the wide export carry no `TCG Low Price`,
so a Low-based preset genuinely cannot price every row, and `SkuMatch.list_price` is `None` there
— which `tcgcsv.set_writable` would turn into an import row carrying a quantity and no price.
The three presets and their numbers are the owner's: match market, market −5%, TCG Low −1%.

**THE RUN COMES FROM A PICKER OR FROM THE URL, AND NEVER FROM STORAGE.** D39's handoff exists
because `#/inventory`'s mass-select is the only one in the product and a second would be two
answers to *which cards*. A run name has no such property — `GET /pipeline/runs` reads the runs
directory and is the single source — so a picker here cannot disagree with anything, and `#/runs`
links a specific run as `#/pricing?run=<name>`. A link, not a handoff: no second `sessionStorage`
key and no clearing rules. **The hash router did not strip a query until this landed**, so the
link matched no route and rendered `NoSuchView` — a defect invisible from either the route table
or the screen, and fixed in `currentPath`.

**THE PHOTOGRAPH IS ON DEMAND, TOGGLED BY ONE KEY, AND NAMES WHICH COPY IT IS DRAWING.** The
owner asked the question that settles it: *"if multiple captures/cards of the same exist, how
would that resolve?"* A SKU averages five copies with five photographs, they are the same card by
construction, and **there is no quality signal worth trusting** — confidence is the tempting one
and is exactly wrong here, since T1's recorded misses are confident answers with the digits
wrong. So the pick is the first in box-walk order, captioned with its real position and `1 of N`,
and steppable. The stepping is what makes an arbitrary pick safe, and it earns a second job:
five photographs answer *are these actually the same card*, and if they are not, the
identification was wrong.

**`scripts/docs-audit.py` GAINS A `withhold reasons` ROW**, reconciling `WITHHOLD_REASONS` across
`pipeline/decisions.py` and `app/src/holds.ts`. Blocking, because a mismatch is provably wrong —
and it matters more here than for the review vocabulary, since `PUT .../decisions` validates
nothing and the screen's only defence against writing an unparseable file is that the two
declarations agree. Mutation-tested in both directions before it was kept.

**WHAT IS NOT BUILT, named rather than left to be discovered**: no durable home for a hold
outside the run directory; no cross-run view of what is being held; no search or sort control,
because the sort is the hierarchy and a re-sort under a finger is D28's defect; and no `Custom`
preset — any other rule or basis is typed into `decisions.json` on `#/runs`, in the text editor
D33 chose, and a re-join regenerates the suggestions.

**WHAT WOULD REOPEN THIS: a hold nobody lifts.** If holds accumulate across runs and are re-set by
hand every time, the per-run home is the wrong one and the deferred durable store becomes the
answer. The measurement is whether the same SKU is withheld in two runs over one box.

---

## Deferred — argued, not gated: nothing here is blocked, and none of it starts without a decision entry

**THE HEADING READ "do not build until all gates pass" UNTIL 2026-08-25, AND NO GATE HAS BEEN
CURRENT SINCE 2026-08-23.** All three passed; `CLAUDE.md` and `docs/GATES.md` both say the
gating system is retired and that nothing is blocked behind one. A list whose whole force came
from a control that no longer exists reads as either binding or void, and neither is right.
What actually holds these items back is `CLAUDE.md`'s standing rule — *scope is argued, not
gated* — so the bar is a decision entry and an argument, not a gate that will never fire.

- PKMNVAULT and anything Supabase/eBay related, **except** the PKMNCODES track, whose
  manual eBay sales are allowed on the shared foundation.
- Riftbound / One Piece / any non-Pokémon TCG. The architecture already keeps the door
  open — the catalog join partitions by `Product Line` and builds one catalog per game (D25);
  only the export's Category filter and the finish enum are Pokémon-specific. **This line read
  "product-line-agnostic" until 2026-08-25 and D25 had already corrected it in as many words:
  measured, the join was product-line BLIND — the column was declared and read by nothing, so
  two exports concatenated would have cross-joined in silence. Blind is not agnostic**, and the
  two words point at opposite properties, which is why the stale one is replaced here rather
  than left to be read as agreement. Expansion later is config plus an enum, so no
  session redesigns for it early.
- Perceptual-hash identification layer (v2 accuracy cross-check).

---

## Someday — worth doing, blocking nothing

Distinct from Deferred above: those need an argument and a decision entry first. These are
things that can
be done any time, in any order, that no other work waits on. Nothing here belongs in a plan
or a gate. If an item starts blocking something, it has stopped being a Someday item and
needs a decision entry of its own.

- **Benchmark T1's eval images through TCGplayer Scan & Identify.** Hand-feed the same
  ~50 images and compare. Answers one question and only one: when Haiku scores below the
  floor, is the task hard or is the prompt weak? That reframes whether to keep tuning or
  move the bar. Manual, ~30 minutes, no integration code — see D2.
- **Measure what the set hint is actually worth.** D2 asserts identification is "better
  with it"; T1 can A/B it directly (`PKMNSCAN_T1_SET_HINT=1`). Watch both directions: a
  hint that raises accuracy but also raises *confidence on wrong answers* is a bad trade,
  because it converts review-queue taps into silently mislisted cards.
- **Send the number-corner crop on every card, not only on a retry.** `geometry/crop.py`
  exists, is tested by T6, and upscales the collector number to at least 600px — but the
  batch script only reaches for it when a first read comes back weak. T1's recorded misses
  are not weak reads. `051/197` for `031/197` and `271/167` for `211/167` are confident
  answers with the name right and the digits wrong, and a confidence threshold never fires
  on them.

  So: attach the crop alongside the downscaled card every time, and let the model read the
  number from pixels that were not thrown away. T1 measures it directly, the same A/B shape
  as the set-hint item above. Cost is roughly double the image tokens on a job D2 prices at
  $5–15 per 10k cards, so the downside is a few dollars and the upside is the number the
  gate rests on.

  Honest limit, and why this is Someday rather than a plan: it might do nothing. The
  crop-retry path was built on the assumption that enlarging the number helps, and that
  assumption has never been measured on its own — which is exactly what makes it worth an
  experiment rather than an edit.

**THREE ITEMS LEFT THIS LIST BY BEING BUILT, and they are struck here rather than deleted so
that a later session reading an older copy does not reinstate them as open work.** Each one did
what this list's own header says it must — *"if an item starts blocking something, it has
stopped being a Someday item and needs a decision entry of its own"* — and each got one:

- ~~**Re-shoot a stored photo in place, long after capture.**~~ **BUILT 2026-08-23 — D26.**
  `POST /inventory/<box>/<index>/photo` replaces the bytes and rebuilds the sidecar with the
  record untouched and the allocator never involved, exactly as this item asked; the control
  is on the card detail, and D31 carries the rule that a merge may not drop it.
- ~~**A `removed` state for cards that leave inventory without a sale.**~~ **BUILT 2026-08-23
  as `retired` — D26.** Renamed on the way in, and the rename is the finding: `removed` was
  already a history event name, so a state sharing it would have made months-old undo lines
  parse as states. Four reasons, reversible, and a sale now refuses a retired card.
- ~~**The owner can't see what a run produced without reading CLI output.**~~ **BUILT
  2026-08-24 — D33.** `#/inventory` carries the run panel: every command's stdout verbatim,
  the import CSVs as downloads, and a money gate that cannot be pressed before the free
  preflight has answered. This item is quoted by name in `docs/GATES.md`'s "what the gate did
  not close", which is where it came from.

- **Cross-check the collector number against the local catalog** (needs D15). Not a
  replacement for the model's read — a second, independent derivation of the same fact, the
  same shape as D3 rung 3, where detected `finish` cross-checks capture metadata even when
  metadata already exists. The model returns `name`, `number`, `printed_total`; given a set
  hint, the catalog independently yields `(set, name) → number` and `(set) → printedTotal`.
  Agreement is confidence, disagreement is a review-queue reason.

  The two sources cover different failure modes, which is the whole argument for running
  both. T1's key misses (`051/197` for `031/197`, `271/167` for `211/167`) had the name right
  and the numerator misread — the catalog catches those. A name misread with the number right
  (`Rhydhorn` for `Rhyhorn`) disagrees from the other side — the model's digits catch that.
  Either source alone is blind to half of it.

  Honest limit, and the reason this is Someday rather than a plan: a cross-check converts
  misses into review-queue taps, not into correct answers. It buys safety, not a higher T1
  number — the mirror image of the trade the set-hint item above warns about.

---

Unsorted scanning is **not** deferred: it works today via the optional hints, with more
review-queue traffic. Just do not optimize for it ahead of work that has a decision entry.
(This read "before Gate C" until 2026-08-25; Gate C passed 2026-08-22.)

---

## v1 bugs — do not reintroduce

| # | Bug | Guard |
|---|-----|-------|
| 1 | Variant mispricing — blindly took `holofoil \|\| reverseHolofoil \|\| normal` | Harness test 4 (variant ladder) |
| 2 | Naive `split(",")` CSV parsing | Harness test 2 + lint rule |
| 3 | `facingMode: "environment"` broke desktop camera selection | Device picker; lint rule |
| 4 | Web Audio contexts created per-sound, never closed | Code review checklist |
| 5 | CSV import matched by box+position, silently skipped identified cards, reported nothing for unmatched rows | Harness test 3 (bidirectional reporting) |
