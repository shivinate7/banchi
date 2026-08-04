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
misfiled, while disagreements scattered across a run mean individual cards are mis-sorted.

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
location before pulling. Photos are already position-keyed on disk — this is display, not
new storage.

## D7 — Duplicates aggregate by SKU at join time

Multiple copies of the same card+variant collapse into ONE fixture row with
`Add to Quantity` = copy count. Inventory keeps every copy as its own position with its own
photo; the app maps SKU → all positions holding it.

**Live quantity caps at 4 per SKU** (a playset; configurable) regardless of copies owned.
This blocks envelope-buster orders, and a price spike sells at most 4 stale-priced copies
before repricing — the same rationale behind TCGplayer's own Buylist Max Listing feature.

Excess copies are backstock at known positions. Refill on later imports as
`Add to Quantity = min(cap - live, backstock)`, with live quantities read from Export From
Live. Order pulls select specific positions and mark them sold individually; remaining
copies stay listed. Price is per-SKU and shared across copies.

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

Sequential position assigned at capture. 25 cards per divider (configurable). Location =
Box N, Section N, Card N. Sold cards leave permanent gaps — positions are never renumbered.

## D11 — Listing path is a catalog join, never a from-scratch CSV

TCGplayer flow: Pricing tab → Export Filtered CSV (All Printings, so one file covers every
variant) → pipeline fills fields → Import to Staged → review → Move to Live. Rows match by
the `TCGplayer Id` SKU, which is never modified.

## D12 — Scope

Modern era only (SWSH/SV), English, all Near Mint (hardcoded). Vintage/WOTC condition
strings (1st Edition, Shadowless, Unlimited) are a spec change, not a parameter.

## D13 — Stack

Vite + React web app in a desktop browser. Python capture server + batch script. Inventory
state is server-side JSON on the Mac, read and written through the capture server, so the
owner's and Fulfiller's devices share one truth. Photos on Mac disk, organized by set.
Build environment is Claude Code on the Mac; code never lives in chat.

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

**The image mirror must live outside the iCloud tree.** The repo sits under
`~/Library/Mobile Documents/com~apple~CloudDocs/`. iCloud with Optimize Mac Storage evicts
large cold files and leaves `.icloud` placeholders behind, at which point an `is_file()` check
returns False and the mirror silently fails the guarantee it exists to provide. 160 MB of eval
images sync today; a full mirror is ~16.7 GB (measured: 834 KB average across 197 hires PNGs).
Path is overridable; `harness/images/` moves out at the same time. Mirroring at all is the
point — `images.pokemontcg.io` is the piece most likely to throttle or disappear, and it is
the one piece the JSON repo does not cover.

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

Ten markdown files carry this project's architecture and the reasoning behind it, and until
`scripts/docs-audit.py` existed nothing verified a single line of them. Every path, `make`
target, subcommand, test id, threshold, decision number and env var in them was true only
for as long as someone remembered. That is the same argument `docs/GATES.md` makes for the
harness — "without it, 'looks done' is the only available signal" — applied to the files
that tell the next session what done means.

**Three layers, split by how knowable each finding is.**

1. **Mechanical** — `scripts/docs-audit.py`, stdlib-only, run by the pre-commit hook and by
   `make docs-audit`. Nine checks, all deterministic. **Exit 1 blocks**, because a dangling
   path is provably wrong and there is no judgment to defer.
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

**Not a harness test.** T7 was considered and rejected. The harness runs behind the `Stop`
hook (`scripts/stop-gate.sh`), so a docs test there would fire at the end of every turn,
including turns that touched no markdown at all. The trigger is commit-time and on-demand
by choice. Do not add it to `harness/run.py:TESTS`.

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
reading it once; `scripts/docs-audit.py` check 10, which verifies every claim in it; and
`scripts/decision-context.py`, the `PreToolUse` hook that names the governing decisions
before a file is edited. Prose serves the first well and the other two not at all.

**It is audited exactly as hard as it is trusted.** An index that drifts is worse than no
index, because it is believed. Check 10 fails when a `built` path is missing, when a
`planned` path has quietly arrived, when `governed_by` cites a decision with no heading,
when gate status disagrees with `docs/GATES.md`, and — the rule that does the real work —
when a source file exists that no entry mentions. Adding a module without touching the map
fails the commit. That orphan rule is the difference between a map and a stale map.

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
