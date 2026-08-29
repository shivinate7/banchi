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

**An empty list means undeclared, and the 25-rule renders it.** That is not a leftover: it is
what keeps every label written before boxes existed byte-identical, and it is what the v1→v2
migration writes for every box it finds. `pipeline/join.py:Position` is still the only label
formula in the repo, and it now takes the layout as an argument rather than reading a constant.

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

**It is SIX again as of 2026-08-29, and the sixth is `#/runs` (D39).** Recorded here because
this is the entry that owns the count and because the direction matters: this merge deleted two
routes that rendered one thing, and that ruling is untouched by a route being added for
something no route rendered at all. `#/inventory` still holds the walk, the card, its copies and
the box's operations; what left it is the pipeline, which was never one of the three screens
this entry merged. The count is restated in `CLAUDE.md`, `docs/map.py` and
`scripts/views.txt`, and the not-rendered-rather-than-hidden rule for the Fulfiller's nav is
untouched — it was never about how many owner routes there are.

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
`pipeline/join.py:_lookup_number_and_printed_total` fell back, when a card carried no number,
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
