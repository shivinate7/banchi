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
1. **Capture-time metadata** — variant toggle in the capture app, stored in the card's JSON
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
2. **Catalog-forced** — no capture-time metadata, and one condition row for that number
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

**Undo is the newest capture in a box, never an arbitrary one.** Deleting a record from the
middle leaves a gap the high-water mark cannot reuse — indistinguishable, later, from the
permanent gap a sale leaves, and the rule above says those mean different things. Restrict
the operation rather than teach the allocator to fill holes: D10's first paragraph is what
makes a printed position label worth trusting, and nothing that renumbers may exist.

A sale is the opposite case and is unchanged. `sold` is a state, the record stays, and the
gap is permanent.

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
`permissions.deny` rules; the code-card literal does not. Revisit before the codes track
handles real cards.

**Nothing on the audit path can write.** The script opens, compares, prints, and sets an
exit code; it parses with `ast` rather than importing, so it does not even run project code.
Its only writes are inside `--self-test`, into a temporary directory it creates and destroys.
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
rebuilt from the record, a `reshot` history line carrying both capture ids) **but no screen
affordance and no client function yet** — where the control lives (pull preview, or a
per-card view) is a design question still open, recorded here rather than guessed at. A sale
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

## Deferred — do not build until all gates pass

- PKMNVAULT and anything Supabase/eBay related, **except** the PKMNCODES track, whose
  manual eBay sales are allowed on the shared foundation.
- Riftbound / One Piece / any non-Pokémon TCG. The architecture already keeps the door
  open — the catalog join is product-line-agnostic; only the export's Category filter and
  the finish enum are Pokémon-specific. Expansion later is config plus an enum, so no
  session redesigns for it early.
- Perceptual-hash identification layer (v2 accuracy cross-check).

---

## Someday — worth doing, blocking nothing

Distinct from Deferred above: those are things not to build yet. These are things that can
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

- **Re-shoot a stored photo in place, long after capture.** Gate B's owner asked for it by
  name: a bad photo discovered late currently has no remedy, because D10's undo reaches
  only the newest capture. The operation that fits D10 is not a delete at all — replace
  the photo and sidecar at the same position, record untouched, position label unchanged,
  allocator never involved. Needs a route, a screen affordance, and a decision entry
  ratified by the owner before it is built.

- **A `removed` state for cards that leave inventory without a sale.** Sold-in-person is
  already `mark-sold` — a state, a kept record, a permanent gap that means what it says.
  What has no representation is a card pulled out, damaged, or given away: today the
  choices are a sale record that lies or a mid-box delete D10 forbids. The fix is
  `sold`'s sibling — a terminal state, record kept, gap permanent — not a tombstone in
  D10's sense, because D10's refusal was about *undo* inventing a third thing the store
  explains, and `sold` already proved the state-machine shape. Needs a decision entry
  ratified by the owner; reopens nothing in D10.

- **The owner can't see what a run produced without reading CLI output.** Found at Gate B:
  emit's import files existed only as filenames in terminal output the owner never saw,
  because someone else was driving the commands. The app deliberately reads state rather
  than owning transitions, but a read-only view of a run's outputs and next action —
  "these files are waiting for Import to Staged" — is reading state too. Design question,
  not a bolt-on; belongs with whoever next touches the owner-side screens.

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
review-queue traffic. Just do not optimize for it before Gate C.

---

## v1 bugs — do not reintroduce

| # | Bug | Guard |
|---|-----|-------|
| 1 | Variant mispricing — blindly took `holofoil \|\| reverseHolofoil \|\| normal` | Harness test 4 (variant ladder) |
| 2 | Naive `split(",")` CSV parsing | Harness test 2 + lint rule |
| 3 | `facingMode: "environment"` broke desktop camera selection | Device picker; lint rule |
| 4 | Web Audio contexts created per-sound, never closed | Code review checklist |
| 5 | CSV import matched by box+position, silently skipped identified cards, reported nothing for unmatched rows | Harness test 3 (bidirectional reporting) |
