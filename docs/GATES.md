# Runs, harness, build order

**THE GATING SYSTEM IS RETIRED (2026-08-23, owner's decision). This file is a record of
what was measured, not a schedule.** Gates A, B and C all passed; no gate is current; no
step is blocked behind one; the deferred list is open. `CLAUDE.md` no longer declares a
current gate and `scripts/docs-audit.py` no longer reconciles one.

**Every number in the gate sections below is evidence about a run that happened on a date,
and none of it is ever rewritten to match a later tree.** 53 cards end to end. Finish
detection at a 30% false-positive rate under the rig's lighting. `detect_card` at 0 of 53,
then 53 of 53 by a second method. A 623 ms feeder cadence over 84 intervals, twice. Those
are the only facts this project has about cards rather than about itself, and renumbering
one to agree with today's code would turn a measurement into a fiction — which is the one
thing a record may never do.

What was retired is the gate as a *control*: the blocking, the sequencing, and the
"current gate" a session had to look up before it was allowed to build. The harness below
is untouched and is still the contract.

## The harness is the contract

`make harness` runs seven tests and exits non-zero on any failure. Nothing is "done" until
it exits 0 and you have seen the output. This is the whole reason the project can be run
by an agent unattended — without it, "looks done" is the only available signal.

T1–T4 are the original contract. T5 and T6 arrived with batch script v2 (build-order
step 4): a wrong price is a distinct failure from a wrong match, and a card the pipeline
cannot find in its own photograph is a third thing again. Each deserves its own failing
test name.

T7 arrived before step 7 and widened what the harness is *for*. T1–T6 all check rules —
what a card is worth, which row it matches, which queue it lands in. T7 checks bookkeeping
and wiring: where a physical card is recorded, whether a correction reaches the file that
will actually be read, which column a price is pulled from. That was a deliberate change to
this contract, argued on the grounds that `store/`, `server/` and `cli/` held about 40% of
product code with nothing checking any of it, and that build-order step 7 was about to add
writers to all three.

Every threshold below is a number, not an adjective. `ID_ACCURACY_FLOOR=0.95` is a spec;
"about 95%" is an opinion an agent can talk itself past.

### T1 — Ground-truth ID eval

Download ~150 official card images from pokemontcg.io across at least 3 sets as labeled
fixtures (the API record IS the label). Run identification against them. Report accuracy
per set and overall.

- **Pass**: `holdout_accuracy >= 0.95`
- **The gate is the holdout, not the whole sample.** The images split deterministically in
  two — a hash of the card id, so there is no seed to lose and the same card lands in the
  same half on any machine. The tuner is allowed to read failures from the tune half only;
  the holdout is the measurement. `overall_accuracy` is still reported and is still useful,
  but it includes the half the prompt was fitted against, which is exactly the number the
  paragraph below says means nothing about the next card. Current split: 82 tune, 68
  holdout, 150 together.
- Rerun after any prompt change. Commit the score to `harness/results/` so regressions are
  visible in the diff. One file per configuration — a hinted run and an unhinted run are
  different measurements and must never share a filename. **No date in the name**: git
  holds the history, and a dated filename turned every new UTC date into a fresh file
  rather than a comparison, which is exactly the noise the next bullet forbids.
- **The results file is rewritten only when the measurement changes.** A cached re-scoring
  recomputes nothing, so it leaves the file byte-identical rather than restamping
  `generated_at`. Otherwise every `make harness` puts a one-line diff on a tracked file and
  a real re-measurement stops being visible among the noise — which is the one thing the
  committed score exists to show. `batch_ids` and `usage` are part of the comparison, so a
  fresh submission always writes even if the accuracy lands on the same number.
- **The rarity-clause A/B was run on 2026-08-23 and the clause lost.** `PKMNSCAN_T1_RARITY=1`
  scores the eval with each card's TRUE rarity as a one-element stack claim — the best case
  the feature could ever see — into its own results file, `harness/results/t1-rarity.json`
  (one file per configuration, as above). Measured against baseline: holdout 0.9706 → 0.9559,
  high-confidence misses 5 → 7, and the finish distribution hardened (`unknown` 27 → 5,
  `normal` 66 → 111) despite the clause's own carve-out sentence — the exact both-directions
  failure the Someday entry warned about, plus a third nobody predicted. The losses were name
  misspellings, not rarity-adjacent; the join key improved by one; and the confident-digit
  miss (`271/167`) survived, which is the class D23 says only the catalog cross-check catches.
  **The production clause is therefore switched off** in `cli/cmd_identify.py` with the
  measurement cited at the switch; the claim's other two jobs — the ladder cross-check and
  the chip narrowing — are unaffected. Cost of knowing: $0.17.
- **Known blind spot**: official API images show no foil texture, so T1 cannot validate the
  `finish` field. Do not let a green T1 be read as variant detection working. **Gate B did
  that job on 2026-08-22 and the answer was bad**: 16 of 53 normals read as foil, a 30%
  false-positive rate, and detection agreed with itself across every duplicate pair — both
  Thievuls, both Eiscues, both Pyroars — so it is systematic sheen under the rig's lighting
  rather than noise. D3's disagreement routing carried all 16 to a human instead of to a
  wrong listing, which is the ladder working. The blind spot is therefore no longer that
  the number is unknown; it is that T1 still cannot see it, so this test will stay green
  while that rate is anything at all.

**Below the floor, tune the prompt — but never against the cards you score on.** Fixing the
specific images that failed and re-measuring on the same set reports a number that means
nothing about the next card, and that number is the whole basis for trusting identification
once there is no answer key. So: hold out a slice the tuner never sees the failures from,
tune against the rest, and report only the held-out score. `PKMNSCAN_REFRESH_IMAGES=1` with
a different `EVAL_SETS` draws a fresh sample.

### T2 — Fixture round-trip

Load `fixtures/sv09_export_untouched.csv`, fill `Add to Quantity` and
`TCG Marketplace Price` on sample rows, write, re-parse.

- **Pass**: exactly 2 fields differ; unquoted header, quoted data fields, CRLF
- Byte format is preserved throughout — the three properties above are the whole of it.
- Assert against `fixtures/staged-import-accepted.csv`, which TCGplayer accepted verbatim.
- After any real import, use TCGplayer's **Export From Staged** button and diff it against
  the pipeline's intended output. That is a machine-checkable round trip against the real
  system, and it is the highest-value finding from Gate A.

### T3 — Join coverage

For a batch of identified cards, every card matches exactly one fixture row for its
resolved condition string. Report unmatched in **both** directions before any output is
written.

Required cases:
- Secret rares where the number exceeds the denominator (`161/159`)
- Blank-`Number` rows (name-matching fallback)
- Names with apostrophes and ampersands (`Billy & O'Nare`)
- 7 identical cards → one row, `Add to Quantity` = 4, 3 recorded as backstock
- Multi-set key collisions: a key that maps to rows in two `Set Name`s resolves by the
  sidecar set hint, reviews as `set_ambiguous` without one, and leaves non-colliding keys
  untouched

- **Pass**: zero unmatched, or every unmatched card reported both ways and routed to a
  standing queue with its position, before any output is written

Output is **not** suppressed by a non-empty queue (batch script v2 §5.6). An unresolved
card sits at a known position in a box: it is not lost and it is not urgent, and holding
400 good cards hostage to 7 ambiguous ones is the wrong trade. What the pass criterion
requires is that the report and the queue file both exist *before* the emitter writes
anything — a card may leave the pipeline unlisted, never unrecorded. `emit_import` enforces
it by refusing to write while any unmatched card has not been routed.

### T4 — Variant ladder

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price: metadata-driven, catalog-forced,
detection-driven, and the disagreement → review path.

Also the routing table (batch script v2 §5.4) — which queue a card lands in, since that is
the other thing that decides whether a resolved card is listed:

- confidence `low` + market ≥ $0.40 → **main** review queue, not listed
- confidence `low` + market < $0.40 → **parked**, not listed, not dropped
- ladder → review: main if the cheapest candidate row is ≥ $0.40, parked if below
- no catalog row, or identification failed → main, sorted last
- matched row with blank or $0.00 market → `no_market_data`, never auto-priced and never
  swept into the sub-threshold flat price
- `--review-below-confidence=none` restores "confidence never routes on its own"

- **Pass**: all four stages correct, review fires on metadata/detection disagreement, and
  every routing row sends the card to the queue named

**The ladder's vocabulary became PER GAME on 2026-08-23, and this test caught nothing about
it because nothing had asked.** `variant.resolve` checked every game's finish against
`variant.FINISHES` — Pokémon's three — and did not refuse politely: it RAISED
`UnknownFinish`, so a Riftbound card claiming `foil`, a finish that game's own registry
entry authors and the capture screen offers, would have taken a join down with a stack
trace. Covered now in both directions, because the fix must not have widened Pokémon's enum
to make the crash go away: `foil` resolves under `riftbound` and still raises under
`pokemon`.

The same class of defect sat one seam further on. `cli/resolve.py` whitelisted the model's
detected finish against the same Pokémon enum, so `foil` landed as `None` and D3 rung 3's
cross-check was lost for every non-Pokémon card — a silent drop, forbidden in as many words
by the comment attached to the line committing it. **The enum-widening case moved with the
home it guards**: it used to assign to `variant.FINISHES`, and now widens the registry
entry, so it exercises `cli/resolve.py` → `variant.vocabulary` → `pipeline/games.py`. T7
keeps the source half and asserts the defective expression is gone rather than the token,
so the comment may still explain what went wrong.

**D3's set-valued rung 1 is covered at every exit** (amended the same day). One member
resolves identically to the bare string it replaces — the compatibility guarantee — and two
or more narrow the rows and fall through: to rung 2 when the claim leaves one row, to rung 3
when detection picks inside the claimed set, to `metadata_detection_disagreement` when it
picks outside, to rung 4 when two rows survive with no detection, and to
`metadata_not_stocked` when no member is stocked at all. Ordering and dedup are asserted,
and one bad member refuses the whole claim rather than being dropped from it.

**Three mutations were observed failing before those cases were kept**: rung 1 returning
instead of falling through, `vocabulary` ignoring its game argument, and `_check_claim`
dropping unknown members. A case that cannot fail is not coverage.

### T5 — Pricing rules

New with batch script v2. Undercut and markup against both bases, rounding half-up at two
decimals, the floor clamp applied *after* rounding, the threshold always read from
`TCG Market Price` whatever the basis, and the `no_market_data` refusal.

- **Pass**: every rule x basis prices exactly; floor clamp applied after rounding;
  threshold always reads market; no_market_data never auto-priced
- "Floor clamp applied after rounding" is also the statement that it cannot be rounded
  under — clamping first would let the rounding step drop the price back below the floor.

### T6 — Card geometry

New with batch script v2. The crop-retry path in §4.5 is only as good as its ability to
find the card in the frame, and a wrong crop produces a miss indistinguishable from a bad
read — so detection gets its own failing test name.

Synthetic composites only: a card rectangle rendered onto a background at a **known**
offset, scale and rotation, so the answer key is exact. No rig photo exists in this repo.

- **Pass**: detected rectangle within tolerance across the sweep; bands contain their
  target; no card -> not found; a ground the tone path cannot segment is still found by its
  borders
- The sweep is offset, scale and rotation. "Bands" are the title band and the number
  corner, and each must contain its target region. "Not found" must be a refusal, never a
  guess.
- **The blind spot this section warned about was measured on 2026-08-22, and it read
  zero.** `detect_card` found the card in **0 of the 53 Gate B photographs**. The paragraph
  below is left standing because it was right; what follows is what it was right about.

  The cause is not a constant. The card sits in a clear stand on a wood desk with a dark
  backdrop above, and its own artwork spans 88 to 231 against a border-ring median of 64,
  so there is no threshold between the two failures: at the adaptive threshold (88.5, which
  the bright card itself sets through the 99th-percentile term) 29% of the card is cut out
  of its own mask and `MIN_FILL` refuses 52 of 53; at `MIN_DELTA` alone the desk grain and
  the stand are foreground too, the box grows to the whole frame, and area and aspect refuse
  all 53. A planar background fit and a bottom-band background were both measured and both
  still find nothing.

  **T6 could not have caught it, and that is the part worth keeping.** `_scene` paints one
  flat colour behind a uniformly bright card — precisely the premise the tone path assumes —
  so the test constructed the one condition under which the method works. A green harness
  was not wrong; it was answering a question nobody had asked it.

  It was latent rather than active: `detect_card` is reached only from the crop-retry path
  (`cli/cmd_identify.py`), and Gate B identified 53/53 at high confidence with zero retries,
  so it never ran. The cost is that the crop-retry rescue is inert on this rig — a weak read
  would get `card_not_detected` and go to a human instead of being retried on an enlarged
  number crop.

  **Fixed 2026-08-22 by a second method, not by moving a threshold.** `geometry/detect.py`
  gains a border search that runs only after the tone path refuses: four long straight
  luminance edges whose spacing matches a card, assuming nothing about what is behind them.
  It finds 53/53 on the Gate B photographs, and `CardBox.method` says which path answered so
  a run report cannot confuse the two. The tone path and its gates are unchanged.

  The regression case is `_rig_scene` in the test: the same synthetic card on a textured,
  unevenly lit ground with artwork running down to the background level, built from the
  measured ring values. It reproduces the mechanism rather than the photograph, because
  `captures/` is gitignored and this repo still holds no rig photo.
- **What is still not evidence.** The border search is measured against 53 photographs of
  one rig in one lighting state on one day. That is 53 more than this section could claim
  before, and it is still not a detection rate. Treat it as T1's finish blind spot is
  treated: recorded here so a green harness cannot be misread.

### T7 — Inventory store, capture server, and the command seams

The first test to reach `store/`, `server/` and `cli/`. Isolation is `PKMNSCAN_HOME` pointed
at a temporary directory, so nothing here touches the real inventory.

- **Pass**: positions never collide and a replay burns none; the sidecar round-trips through the reader identify uses; every refusal answers in its own code; command seams read the columns they name, and commands refuse rather than prompt
- **Two cases are regressions, not new coverage.** Both were live bugs that passed every
  gate in the repo on the day they shipped: the `PUT` that never reached the sidecar — which
  passed its own route test while doing it — and the `c.box == box` filter that dropped a
  string-typed record and returned an index that collided later. Both are recorded in
  `docs/DEBTS.md`, and both were re-introduced deliberately to confirm this test catches
  them before it was committed.
- **What it checks that T1–T6 cannot.** They check rules and this checks wiring. A wrong
  rule gives a wrong answer you can see; a wrong position gives a card that is exactly where
  the inventory says it is not, found weeks later by a person opening the wrong slot.
- **Concurrency is small-N on purpose.** Two and four simultaneous captures over real
  sockets, matching D5's two devices. The twenty-way case that found the listen backlog
  proved something about a socket option and is not worth paying for at every turn end.
- **Undo is covered as of 2026-08-13**, the day its route landed with step 7a: that it
  answers with the position it removed, that the record, sidecar and photo all go, that a
  second call walks back one more card, and that it refuses anything but the newest and
  anything already written into an import file. All D10, and all written the same day the
  route was, which is what this bullet promised when it said the cases were writable then.
  **Narrowed 2026-08-23 by D10's ruling 2**: undo now stops at `captured`, and the case
  that asserted "undo at `identified` is ALLOWED" asserts the refusal instead — and
  exercises the three remedies it names (re-shoot, retire, the mid-box remove). The two
  destructive operations the same rulings added are covered the same day they landed:
  the mid-box delete with its contiguous shift (`renumber_blocked` and the aim check,
  photos following their records byte-for-byte, the `renumbered` mapping and the
  per-position roll-call lines that keep the state reversals reading the right card) and
  the whole-box delete behind `box_not_empty_of_commitments`.
- **The queue's starvation tier is covered as of 2026-08-24, in its own isolated home.**
  `store/queues.py:sort_key` gained a tier that promotes an entry past `STARVATION_DAYS`
  ahead of price, because price alone never releases an unpriced card: `no_catalog_row` has
  no market, so it sorted last permanently, and box 2 left 47 entries queued, counted and
  unreachable. The case asserts oldest-first inside the tier, expensive-first untouched
  inside the threshold, the boundary one day short, and that a missing `first_seen` can
  never starve — **observed failing against the old key before it was kept**.

  **Two findings from writing it, both of which are this file's own lessons repeating.**
  `Queue.upsert` overwrites `first_seen` with today on insert and preserves only an existing
  stamp, so an entry cannot be aged by passing the field in — which is correct for the store
  and means the test writes the stamp afterwards. And the first draft put six entries into
  `check_queues`' shared store and took four of that block's own assertions red: the same
  shared-fixture failure the mass-select bullet below already records, found again the same
  way, and fixed the same way.

- **D34's listing release and its free preflight are covered as of 2026-08-24, in their own
  isolated home.** `GET /boxes/<box>/listings` answers what a release would give up;
  `POST /boxes/<box>/listings/release` gives it up, on the operator's word that TCGplayer is
  holding none of those copies. The block asserts every refusal (`confirm_required` including
  the stringified-flag case, `field_not_settable`, `box_not_found` on both routes, and
  `nothing_to_release` on a replay), that neither the preflight nor any refusal moves a count,
  and the two boundaries that keep the operation honest: **a sold card still holds its box open
  after every listing in it is clear**, and **a SKU shared with another box keeps that box's
  copies untouched**.

  **The budget is what most of the block is about.** Each SKU gives up at most the unsold copies
  the calling box holds (D34, the owner's ruling). The fixture is built to exercise the hard
  case rather than the easy one: box 4 holds 2 of a SKU's 5 staged copies and box 6 holds the
  other 3, so the release gives up 2 and **box 6's three survive** — which the first build,
  zeroing outright, could not promise. A remainder therefore stays, the box is STILL refused
  afterwards, and both the plan and the receipt say so before and after. That remainder is
  intended, not a defect.

  **The gap it closes was found by a box that could not be deleted, and the mechanism is the
  finding.** `staged` is drawn down in exactly one place — `cli/cmd_join.py`, by the *rise* in
  live quantity a fresh Filtered Export reports — so an import that never lands leaves a count
  nothing can take back down. Box 1's 53 Gate B cards sat behind 45 records claiming 53 staged
  copies TCGplayer had long since cleared. `staged_stale` has named that case since D7's
  amendment and nothing could act on it: a diagnostic with no remedy.

  **Its own home, and that is this file's own lesson a third time.** The block writes listings,
  which `check_boxes_and_listings` counts and `check_cli_seams` reads back through `emit` — the
  same shared-fixture failure the two bullets above already record, avoided rather than
  rediscovered.

- **The mass-select on `PUT /inventory/<box>` is covered, in its own isolated home.** The
  owner's `indices` selection narrows the box-wide claim sweep, and it is checked on the
  route rather than as a client loop for the reason the case states: N card calls are N
  chances to half-apply, which is the partial sweep that route's all-or-nothing exists to
  prevent. Both refusals were observed failing under mutation before the cases were kept —
  an empty array quietly meaning the whole box, and a selection naming a card the box does
  not hold being ignored instead of refusing the call.

  **The separate home is itself a finding worth keeping.** These cases first ran inside the
  block above, which counts history lines over a box it builds card by card — so the sweep
  moved numbers that block asserts, and the section failed on its own fixture rather than on
  the code. A test that writes to a shared fixture is a test that will eventually be blamed
  for someone else's assertion.
- **7b's three routes are covered as of 2026-08-13**, the day they landed: `GET /queues`,
  `POST /review/<box>/<index>/answer` and `POST /inventory/<box>/<index>/sold` — the
  standing-queue read, D4's one-tap answer, and D10's mark-sold with its reversal. This
  bullet said those routes did not exist. **Of everything 7b shipped, the routes are the one
  part that did not get built ahead of its evidence**, and that is worth noticing when
  reading the rest of it.
- **Known blind spot, and it is 7b's — half of it closed on 2026-08-22.** Every queue entry
  these cases assert against is still hand-built by the test, so a green T7 still says only
  that the routes behave the way `docs/DESIGN.md` describes. What is no longer true is the
  sentence that used to follow: a real run HAS produced entries, 16 of them, and their shape
  matches what the test builds — `position`, `reason`, `read`, `candidates`, `market`,
  `first_seen`, `cleared_by_human`. All 16 were `metadata_detection_disagreement`, all
  parked, and the owner answered every one through the answer route.

  So the remaining gap is narrower and worth stating exactly: the fixtures are still
  invented, and Gate B's run of one lot produced exactly one reason code. **Box 2 produced a
  second, and this bullet denied it until 2026-08-25**: `no_catalog_row` has stood in the live
  queue as 47 real entries with zero candidates — the case D35 was written for and the case
  D37's `wasted_position` was measured against, both landing in this repo on the strength of
  it. The count was stale too: the roster is fourteen, not twelve. So **two of fourteen have
  met a real card**, and nothing has exercised `set_ambiguous`, `low_confidence` or the other
  eleven against a real queue. Same standing as T6's synthetic composites: self-consistency
  over a wider range than the evidence covers.

---

## Gates

### Gate A — TCGplayer seam. PASSED 2026-07-26

Level 4 confirmed. SV09 fixture exported and committed. 2-row Import to Staged validated
end to end. Finding: an "Export From Staged" button exists — see T2.

### Gate B — 20-card end-to-end smoke test. PASSED 2026-08-22

**Passed with 53 cards, not twenty** — a pre-sorted lot of ME01 commons and uncommons,
fed by the feeder at manual-trigger pace, every card captured, identified, joined,
emitted, imported to Staged, and reconciled back in two clean round trips with zero
unmatched in either direction. The pull preview showed the right photo at the right
physical location, which was the last link in the chain. "No part of this repo has met a
card" was true when this section was written and is now false in the best way available:
**the project's first numbers about cards, rather than about itself, are below.**

**Identification on real rig photos: 53/53, but only once the frames were upright.** The
portrait-mounted camera (the right rig call — a portrait card fills the field) reaches the
browser as a landscape frame, and sideways cards were misread wholesale: 45 of 53 to the
review queue, names and numbers both garbled. The same frames rotated upright read 53/53
with zero low-confidence retries and zero detection failures. The fix is a capture-time
rotation setting; the A/B that convicted rotation was three frames, three perfect reads.

**Finish detection got a 53-card measurement instead of the planned ten photos: 16 of 53
normals read as foil (30% false-positive rate under the rig's lighting), and every one was
a real card a human then ruled on.** Detection agreed with itself across duplicate copies
— both Thievuls, both Eiscues, both Pyroars — so this is systematic sheen-under-lighting,
not noise: a rig finding, exactly as the paragraph this replaces predicted, and D3's
disagreement routing carried all 16 to a human instead of a wrong listing.

**The §10.2 measurements** (capture-app spec), from the corrected run: queue rate 16/53
(30%), all `metadata_detection_disagreement`, all parked (sub-threshold prices).
`no_catalog_row` fired 23 times against a commons-only export and zero times against the
full-rarity export — an export-scope artifact, not a pipeline one. Fired zero times:
`set_ambiguous`, `no_market_data`, `metadata_not_stocked`, `detected_finish_not_stocked`,
`ambiguous_no_signal`, `duplicate_condition`, `low_confidence`, `no_position`,
`identification_failed` — which fired only in the discarded sideways run — and
`card_not_detected`, whose zero says nothing about the owner's stock:
`pipeline/routing.py` defines the constant and nothing in `pipeline/`, `cli/` or
`identify/` ever assigns it, so it could not have fired in either run. Price distribution: $0.04–$0.40 across the run, median ≈ $0.10; the queue's
spread matched the run's, so the review screen's price-banded hierarchy has yet to be
tested by a mixed-value lot. The Fulfiller item was not exercised — no order existed.

**Six defects were found by the run and fixed the same day, three of them with a
regression test observed failing against the old code first:** the Batch API refusing the store's
`box/index` key as a `custom_id`; the capture screen leaking a 33 MB canvas per press;
Chromium idle-scheduling the JPEG encode into 1–7 s stalls a capture burst never gives it;
a re-routed position keeping its stale entry in the queue it left; review answers recorded
by the answer route that nothing on the join path ever consumed (now rung 0 of the
ladder); and a post-import re-emit that double-counted staged copies and regressed their
states. The first is why the run reached the API at all; the second and third are why
capture now sustains burst pace; the last three are why the queues, the answers, and the
import files survived contact with a second cycle.

**Three of the six carry no automated test, and that is recorded rather than rounded up.**
The cross-queue release leak has a T7 case; rung 0 and the re-emit double-count have a T3
case each — all three observed failing against the old code before the fix was restored.
The `custom_id` refusal, the canvas leak and the idle-scheduled encoder have none: `app/`
has no test runner outside the browser `make design-check` starts, and nothing under
`harness/` reaches `cli/cmd_identify.py`'s id translation. Each is guarded by a comment
beside the code and by nothing that runs, which is the weakest guard in this section and
the reason it is named here rather than left to be inferred from the commit stats.

**BOX 1'S RECORDS WERE DELETED ON 2026-08-24, AND EVERY NUMBER ABOVE STANDS.** Recorded so a
later session that goes looking for the 53 records does not conclude the run never happened.
The box was a shakedown lot the owner wanted gone, and it could not go: its 45 listing records
still claimed 53 staged copies and one live, so `box_not_empty_of_commitments` refused it, and
nothing in the repo could clear a staged count that never went live (D34 carries the mechanism).
The listings were released on the owner's word that TCGplayer held none of them — box 1 shared
no SKU with box 2, so every one of its 45 records went to zero and nothing else was reached —
and the box was then deleted whole — 53 records, 53 photographs, 53 sidecars, 16 parked queue entries and 53
cached identification answers. **The measurements in this section are evidence about a run on a
date and are not touched by it**, which is this file's own rule; what is gone is the inventory,
not the finding. The one thing no longer re-checkable by hand is the photographs, so nothing
above may be re-derived from them.

**What the gate did not close:** the owner had no visibility into emitted import files —
their names exist only in CLI output the owner never sees when someone else drives the
commands. Recorded in `docs/DECISIONS.md`'s Someday list with two more operations the run
surfaced (late re-shoot of a bad photo; a `removed` state for cards that leave inventory
without a sale).

### Box 2 — 544 cards, and the first ground truth about finish detection. 2026-08-24

Not a gate. The largest run this project has done, and the first with the owner confirming
what the cards actually are.

**Identification: 544/544, zero errored.** 539 high confidence, 5 medium, none low after one
3-card retry. 114 distinct names. Cropped to the detected card at max-edge 1200. Billed
1,315,698 input and 20,698 output tokens — **$0.71**, against a $0.62 estimate; `SYSTEM_TOKENS`
was 500 where the real turn is ~1,000, and is now the measured figure.

**FINISH DETECTION IS WRONG ON 42% OF A BOX WHOSE TRUTH IS KNOWN.** The owner, after the run:
*"all of the cards provided in box 2 were normal by the way no reverse holo / foils etc"*.
Every capture carried the claim `normal`, and every card was in fact normal. Detection said:

| detected | cards | |
|---|---|---|
| `normal` | 208 | correct |
| `unknown` | 106 | honest non-answer |
| `holo` | 151 | **wrong** |
| `reverse_holo` | 79 | **wrong** |

**230 of 544 wrong — 42%.** Gate B measured 30% on 53 cards and called it systematic sheen
under the rig's lighting; this is the same finding at ten times the sample with the owner
supplying ground truth rather than a per-card ruling.

**It is not noise, and the A/B proves something worse than bias.** Forty of these cards were
also identified at max-edge 900 in a separate run: **19 of the 40 disagreed with themselves on
`finish` between two resolutions of the same photograph**. A signal that changes when the
downscale changes is not measuring foil.

**What it costs is D3 rung 3's whole purpose.** Rung 3 cross-checks the capture toggle against
detection, and a disagreement routes to review. On this box that is 230 cards queued against a
claim that was right every time. D29's group answer cannot absorb them — it requires one shared
candidate, and 230 cards are 230 different catalog rows. This is the paragraph to read before
joining a box shot on this rig.

**The remedy the owner chose, the same day: `join --bypass`** (D3, amended). Rung 3 is
switched off for a run wherever a finish claim exists, so the claim resolves the card and the
disagreement is never raised. Measured against this box with `join --dry-run`, which walks the
ladder twice and writes nothing: **256 cards would queue, 209 of them clear by the claim, and
47 remain** — all `no_catalog_row`, and all of them the crop-damaged reads (38 blank numbers,
9 wrong Pokedex-style numbers) that the flat-pad bug produced before it was fixed. Those 47
have no claim to fall back on, which is exactly where the flag stops.

### Gate C — feeder integration. PASSED 2026-08-22

**The feeder exists and runs today** (confirmed 2026-08-13). Cards are fed onto a tray,
landing in the same spot each time. This gate therefore tuned against a rhythm that already
existed rather than building one — a smaller job than this section was written to describe.

It did not move auto-capture earlier. **Gate B ran manual**, on the original reasoning, and
the reasoning is the part worth keeping: auto-capture was scoped as an incremental addition
after step 7 because of its own complexity, and a run that tests the pipeline and an untuned
trigger at once cannot say which one failed. `docs/specs/capture-app.md` built the trigger
as one replaceable piece, and the seam held — the motion machine landed as an addition
rather than a rewrite.

The feeder pauses per card, so the method is a motion state machine — and **the machine
is BUILT as of 2026-08-22** (`app/src/motion.ts` behind the trigger seam, a mode toggle
and live HUD on the capture screen, two specs in `make design-check`; spec at
`docs/specs/motion-trigger.md`, decision at D19). **Every threshold was derived from Gate
B's frames**, and that provenance is the finding the first live trace then convicted: live
still-noise runs eleven times the stored-JPEG floor `tLo` was fitted to, which silently cost
14 of 86 cards until it was retuned. Video frame extraction is no longer "the fallback if
tuning misbehaves" — D19 rejects it as a capture path outright and keeps it only as a
rig-session debugging instrument.

**What this gate asked for, and what it got.** It asked for the ~30-minute tuning protocol,
a 50-card run, then a full box. The protocol ran and produced the retune above; the 50-card
bar was cleared twice over by two 85-card runs; **the full box has not happened, and neither
has the pipeline half** — see the two paragraphs below, which say exactly what box 95 did
and did not do. Recorded as owed rather than quietly dropped, even though nothing is gated
on it any more.

**The rhythm has a number now, and half of one.** Recorded here because Gate B measured it
by accident and the next run should not have to.

- **The feeder emits roughly every 660 ms**, per the owner. Gate B's run independently
  agrees: the operator's press loop started ~64 ms/card ahead of the machine, banked a peak
  lead of 2.2 s by card 47 on cards the feeder had already dropped, then had to slow to the
  supply — and its **last eight gaps average 661.9 ms**. Two estimates, 2 ms apart.
- **Jitter across the whole run was 34 ms** (robust σ; 57 ms by standard deviation), min
  458 ms, max 796 ms, over 52 intervals. Unimodal and peaked, not piled at a floor.
- **The capture path is not the constraint.** An earlier burst the same evening did 25
  consecutive captures in ≤6 s, bounding press-to-commit at 250 ms, so Gate B ran with
  2.5–3.7× headroom.
- **The half that was missing arrived 2026-08-23, off the first motion trace**: each cycle
  is ~217 ms moving and ~400 ms still (min still gap 132 ms), period 623 ms burst-to-burst
  over 86 cycles — comfortably inside the settle design's feasibility bound. The same trace
  convicted the first `tLo`: live still-noise runs eleven times the stored-JPEG floor it
  was derived from, which silently cost 14 of 86 cards; retuned, the offline replay scores
  86/86 with zero double-fires. `docs/specs/motion-trigger.md` carries the numbers; what
  remains live is the confirmation run.

**The confirmation run happened, and it passed: 85 cards, box 95, nothing dropped.**

- **Nothing dropped, and that is checkable rather than remembered.** Box 95 holds 85
  records at indices 1..85 with **zero gaps** and **85 distinct `capture_id`s**, so the
  machine fired once per card and the replay guard caught no double-submission. All 85
  carry a finish claim; all 85 have a photograph on disk.
- **Cadence, measured over the run's 84 intervals**: median **623 ms**, mean 633 ms,
  robust σ **43 ms** (67 ms by standard deviation), min 520 ms, max 878 ms, and **zero
  intervals above 1.6× the median** — no stall, no double-fire, no recovery gap.
- **The trace's prediction was exact.** The tuning trace above put the period at "623 ms
  burst-to-burst over 86 cycles". The confirmation run's median is 623 ms. The retuned
  `tLo` did what the replay said it would.
- **A second run agrees independently.** Box 99, 85 cards, taken earlier the same evening:
  median 618 ms, mean 631 ms, robust σ 47 ms, min 506 ms, max 903 ms, zero gaps, zero
  outliers. **Two 85-card runs whose means differ by 2 ms.**
- **The motion trigger is slightly faster than the hand it replaced**, at comparable
  jitter: Gate B's manual loop averaged 661.9 ms over its last eight gaps at σ 34 ms;
  this runs at 623 ms and σ 43 ms. The operator was the slower component.

**WHAT THIS RUN DID NOT DO, and it is half of what this section used to ask for.** Box 95
holds 85 records and **every one of them is still `captured`**: zero identified, zero
carrying a SKU, and `runs/` holds no run directory for that box. The cards were photographed
at feeder pace and the pipeline was never pointed at them.

So the trigger half is confirmed and the pipeline half is not. `docs/specs/motion-trigger.md`
said so on the day and was right: *"That clears the 50-card bar for the trigger half of Gate
C; the gate still owes the pipeline half (identify → join → emit → reconcile on a
feeder-paced box) and foil under this lamp."* Written down here rather than left to that
spec, because this section is where a later reader looks for what a run proved, and "85
cards, nothing dropped" reads as end-to-end when it was not. Gate B is still the only run
that has been through identify, join, emit, Import to Staged and reconcile — and it was
hand-triggered, 53 cards, one box.

**Honest limit on the cadence figures.** They are photo **write** times, not shutter times —
the same instrument Gate B used. The interval between consecutive writes measures the cadence
only while encode-and-commit latency is roughly constant, which the zero-outlier count
supports and does not prove.

**`captured_at` is STILL whole-second, and the reason is worth more than the fix was.**
The paragraph this replaces said the millisecond stamp meant the next run would "measure
its own cadence instead of depending on that accident a second time". It depended on the
accident a second time. Every one of box 95's 85 records reads `T03:08:22+00:00` with no
fractional part, and the figures above came off APFS `st_birthtime` again.

The cause is not the code. `store/master.py:now()` was changed to milliseconds at 20:16
and the run was at 22:08 — **after** the fix. The server process serving it had been
started before 20:16 and was holding the old code in memory, which no commit can reach.
**A long-running `make server` outlives the fix that was written for it.** That is a
restart discipline, not a bug, and it belongs beside the money rules: restart the capture
server after any change under `store/` or `server/`, or the run you are about to do is
served by whatever was true when you started it.

---

## Build order

1. ~~Repo init, fixtures committed, git from commit zero~~ — done.
2. ~~**Scaffolding**: `Makefile`, `.claude/settings.json` hooks, `scripts/screenshot.sh`,
   empty harness that exits 1. Do this before any feature so the check exists first.~~ — done.
3. ~~Verification harness (T1–T4)~~ — done; T5 and T6 arrived with step 4.
4. ~~Batch script v2: Batch API, variant ladder, catalog join, real CSV library~~ — code
   done 2026-08-03, spec at `docs/specs/batch-script.md`, harness green at T1–T6.
   `./pkmnscan identify | join | emit | reconcile`. **This line read "not yet run against a
   real card" until 2026-08-22**, when Gate B put 53 through all four commands and reconciled
   back in two clean round trips with zero unmatched in either direction. The run found
   defects in this step's own code that no fixture could: the Batch API refusing the store's
   `box/index` as a `custom_id`, `cmd_join` leaving a re-routed position's stale entry in the
   queue it left, review answers nothing on the join path ever read back (now rung 0 of the
   ladder), and a post-import re-emit that double-counted staged copies. The harness still
   exercises this step against fixtures and synthetic images only; the run itself is in the
   Gate B section above.
5. ~~Capture server: `POST /capture`, position-ordered filenames, JSON sidecars (position,
   box, set hint, variant), `/status`, `GET /photo/<box>/<position>`, `GET`/`PUT` inventory
   state shared across devices.~~ — done 2026-08-11, spec at `docs/specs/capture-server.md`.
   Positions are allocated inside the store lock by `allocate_capture`. **T7 reaches it as
   of 2026-08-13**: every route, every named refusal, and the sidecar seam read back through
   the reader `identify` uses. This line said the opposite for two days — the step shipped
   with nothing under `harness/tests` importing `server`, `store` or `cli` — and the claim
   outlived the gap it described. What T7 still does not assert is in `docs/DEBTS.md`, and
   is now three named cases rather than a whole package.
   The server has grown well past the five routes this line was written about: `DELETE
   /inventory/<box>/<index>` arrived with step 7a's undo; `GET /queues`, `POST
   /review/<box>/<index>/answer` and `POST /inventory/<box>/<index>/sold` with 7b; and
   `GET /search`, `GET /boxes`, `POST /boxes` and `PUT /boxes/<box>` with the order flow.
   Each came with its own T7 cases on the day it landed. **The count is deliberately not
   published here.** It said "nine" while the server served thirteen, and it was restated in
   three files at once — a verifiable fact with nothing in it a later session could disagree
   with, which by D18's test means it is not load-bearing prose and should not be maintained.
   `server/capture_server.py`'s own header is the register.
6. ~~Design tokens locked and one component built against them~~ — done 2026-08-12.
   Tokens locked by interview against rendered alternatives rather than by inference; the
   pull-confirm built against them at `app/src/PullConfirm.tsx`, in all three states, on a
   gallery route `make screenshot` renders and `make design-check` asserts.
   **Building it earned its place**: it caught two points where
   `docs/design-refs/locked.html` contradicts `docs/DESIGN.md` — an 18px button label under
   the view's own 20px floor, and a keyboard chip on a control only the Fulfiller touches.
   Both are recorded in `docs/design-refs/README.md`; neither was visible in prose.
7. ~~Vite capture app: device picker, manual capture, set hint + variant toggles, position
   tracking, undo, inventory views (SKU → positions), review queue, pull preview with
   photo, Fulfillment view.~~ — **both halves built 2026-08-13** on branch
   `step-7-capture-app`. The toolchain arrived with
   step 6 — `app/` is a Vite + React + TypeScript project already, so this step added
   screens rather than a build system. `docs/DESIGN.md`'s Fulfillment table is now *written*
   as assertions in full: three of its rows against step 6's component in
   `app/tests/pull-confirm.spec.ts`, and all nine against the view in
   `app/tests/fulfillment.spec.ts`. Both specs pass, green since the routing
   landed; see below for the several hours in which they did not. (The assertion count used
   to be published here too and no longer is — see `docs/DESIGN.md` for why. The "16 of 30"
   and "30 of 30" further down are evidence about that day and stay as written.)

   **Split at Gate B — and then the split was not honoured.** 7a is the Gate B path: the
   shell, the capture screen, undo, the pull preview and the trigger seam, specified in
   `docs/specs/capture-app.md` and built to it, along with the one new server route and the
   two eslint rules that make `make lint` real. 7b is the review queue, the Fulfillment
   view, the inventory SKU views and mark-sold — scheduled *after* the gate, so that it
   would be built against a real run rather than against guesses about what one produces.

   **7b was built before Gate B, at the owner's explicit instruction.** The spec's scope
   section and its "what this session must not build" list both said otherwise; both are
   left standing there and marked overtaken, and that file's STATUS section carries what it
   costs. The short form used to be that **the screens 7b added display data that no run has
   ever produced** — true when written, false since 2026-08-22. Gate B put 53 real cards
   through them: 16 real queue entries, all answered, and a pull preview that found the right
   photo at the right physical location.

   What survives is the narrower half, and it is worth keeping: all 16 entries carried **one
   reason code out of twelve**, and the run priced $0.04-$0.40 end to end, so the review
   queue's price-driven row hierarchy has still never been shown the mixed-value list it
   exists to sort. Read those screens as validated in outline and unvalidated in range.

   **Built was not routed for a few hours, and the shape of that gap is worth keeping after
   the fix.** 7b shipped with none of its three screens in `app/src/App.tsx`'s ROUTES table,
   no client function in `app/src/server.ts` for the three routes it had added to the
   capture server, and the review queue's calls arriving as a prop nothing supplied — both
   files belonged to another group in that session and were left untouched. `make harness`,
   `make lint`, `make typecheck` and `make docs-audit` were all green throughout. The only
   check that could tell was `make design-check`, which **failed 16 of 30 assertions**,
   every one of them reporting the unregistered route rather than a design defect; the
   Fulfillment spec asserts the view is on screen before measuring anything, precisely so
   that the alternative — nine confident measurements of whatever Vite serves for an unknown
   hash — cannot happen. A wiring pass on 2026-08-13 registered six routes, added one client
   function per new route, and took design-check to **30 of 30**.
   **The finding outlives the fix: nothing on the path that decides whether a commit
   proceeds looks at whether a screen can be opened, and the one check that does is
   deliberately not on it** — it starts a browser and a dev server, which is a different
   weight of check from the rest.

   **The step is therefore done, and step 8 is next — which means the next action in this
   repo is a physical one.** `docs/map.py` said in writing that moving `next` to step 8 was
   "the owner's call to make on the day, not a call to make by editing this file", because
   `make status` would then send whoever runs it to a twenty-card run against a build that
   has never met a card. That is still exactly what it does. It is now also correct: with
   nothing left in step 7 to build, meeting a card is the only remaining way to learn
   anything, and Gate B is the name for doing it. **It was done on 2026-08-22 and the
   paragraph above is now history** — kept because the reasoning for moving `next` onto a
   physical step is the reasoning Gate C will need again, and it was right: the run found
   six defects that every green check in the repo had passed.

   **"CSV import with error reporting" was struck from this list on 2026-08-13.** It was a
   v1 feature that batch script v2 absorbed whole: `emit` writes `pushed`, `reconcile` moves
   `pushed` to `staged` off the Export From Staged, and `join` moves `staged` to `live` off
   the Filtered Export. Every state transition is owned by a command, and the app reads
   state rather than setting it — so there was nothing left for the feature to do. Recorded
   rather than deleted silently, because the phrase would otherwise be reinstated from an
   older copy of this list. The bidirectional-reporting guarantee it once carried (v1 bug 5)
   is T3's, and T3 is unaffected.
8. ~~Gate B smoke test~~ — passed 2026-08-22, 53 cards end to end. The run's record and
   measurements are in the Gate B section above; the six defects it caught are fixed with
   regression tests in T3 and T7.
9. **Vendor the pokemontcg.io catalog** — see D15. Three pieces, in order:
    - Snapshot `PokemonTCG/pokemon-tcg-data` into the repo (183 files, 27.4 MB) with a
      `make` target that refreshes it and records the upstream commit SHA.
    - Build the SQLite index. Cards join to sets by *filename* — `printedTotal` is only in
      `sets/en.json`, and it is half the join key.
    - Fill the image mirror from `images.pokemontcg.io`: rate-limited, resumable,
      manifest-driven, per-file skip on a non-empty existing file. Destination is
      overridable by `PKMNSCAN_IMAGE_MIRROR` (D15); move `harness/images/` there too.
      Dry-run the `Content-Length` sum first — ~16.7 GB is extrapolated from a 197-image
      sample, so confirm before committing the disk.

    Deliberately after Gate B: no production code reads this data. `harness/eval/fixtures.py`
    is the only consumer, step 4's batch script does not depend on it, and a warm harness run
    already makes zero network calls. Retiring the retry/backoff scaffolding in that file is
    part of the step, not a follow-up.
10. Feeder integration (Gate C).
11. ~~Get the free pokemontcg.io key at dev.pokemontcg.io~~ — done 2026-08-03. Read from
    `.env` as `POKEMONTCG_API_KEY`; keyless limits covered the harness but not set-scale
    processing. Step 9 removes the need for it.
12. Only then: scale, polish, deferred list.
13. **Order flow, boxes, and search** — spec at `docs/specs/order-flow.md`. the store's fungible-copy model (D7 amended), the box
    object and its retroactive capacity (D20), per-box section layouts (D10 amended), the
    search-and-sell screens on both sides, and the operations D26-D30 ratify.

    **EVERY ITEM THIS STEP WAS SCOPED AROUND IS BUILT AND REACHABLE as of 2026-08-23**:
    schema v2 with its migration, the server routes, the shared search components, the
    Fulfiller's search, D26 (`retired` and re-shoot in place, both with controls on the
    owner's screen), D27 (session state in `sessionStorage`), D28 in both halves (the
    layout fix and the twenty-second answer undo), D29 (group-answer a homogeneous queue)
    and D30 (the gap convention as `neighbors` and `section_gaps`). D31 then merged
    `#/boxes` and `#/pull` into `#/inventory`, so the screens this step names by their old
    routes are modes of one.

    **This step's Outstanding list ran to five entries while all five were already on disk,
    which is the failure this file warns about pointing the other way.** A stale record is
    believed exactly as hard as a true one, and nothing mechanical checks a list of prose
    claims against the tree. Rebuilt from a grep rather than from the previous list.

    **What was outstanding was never in this list at all: the CLIENT half.** Box delete,
    the mid-box delete with its contiguous shift, and the retroactive claim corrections all
    passed T7 with no client function and no control on any screen — so this step could
    read as complete while three of its operations were unusable. They are reachable now,
    and `app/tests/inventory.spec.ts` asserts it. `CLAUDE.md`'s route-is-not-a-feature rule
    is that discovery written down as a standing rule.
14. **Multi-game** — spec at `docs/specs/multi-game.md`. four capture choices plus `misc`, per D21-D25. Landed: the vendored
    registry with four real TCGplayer exports behind it, four audit rows, per-game dispatch,
    and `game` through all ten capture hops with the picker on the capture bar.

    **EVERY STEP IS NOW BUILT** (2026-08-23): step 5's rarity claim end to end, step 6's
    repeatable `--export` with per-game catalogs and one import file per game (D25), step 7's
    pooled non-located inventory and both opsec discharges, step 8's rarity clause — built
    behind its A/B flag, MEASURED, and switched off because it lost (holdout 0.9706 → 0.9559,
    $0.17; the numbers are in the T1 section above) — and step 9's per-game finalisation:
    `riftbound_card_v1` and `one_piece_card_v1` exist, are registered, are dispatched to by
    the registry and carry parsers.

    **`pokemon_card_v1` did not move: `1ef974bf511d`, unchanged.** `prompt_fingerprint` hashes
    ONE profile's fields, so adding sibling profiles incurs no T1 re-measurement and none is
    owed. The new siblings hash to `2bd952abb691` and `615e974828b5`.

    **The trap that step 9 nearly walked into is worth keeping.** Both new games name their
    identifier field `number`, including Riftbound, whose field study had proposed
    `printed_code`. `cli/resolve.py` reads the RAW payload out of `identifications.json` and
    never calls `prompt.parse`, so a differently-named field would have parsed cleanly,
    recorded cleanly, and handed the join a card with `number=None` — `no_catalog_row` for
    every card in the run, blaming the export. `misc` gets away with `printed_id` only because
    `is_catalogued` diverts it before that read. The seam is now asserted end to end.

    **What no amount of code can close: neither game has met a card.** The store holds zero
    Riftbound and zero One Piece records, so every claim about those two prompts is a claim
    about a CSV and a schema, not about a photograph. Same standing as T6's synthetic
    composites before Gate B.

15. **The pipeline seam: the four commands, reachable from a screen** — D33, built
    2026-08-24. spec-less by choice; the decision entry carries the whole argument.

    **THE LARGEST INSTANCE OF `CLAUDE.md`'s route-is-not-a-feature RULE THIS REPO HAS HAD,
    and nobody had counted it.** `./pkmnscan identify | join | emit | reconcile` has existed
    since step 4, went through Gate B's 53 cards and box 2's 544, and could be reached only
    by somebody typing at a terminal. This section already named the cost in the Gate B
    write-up — *"the owner had no visibility into emitted import files; their names exist
    only in CLI output the owner never sees when someone else drives the commands"* — and
    filed it as a Someday item rather than as the missing half of a built feature.

    `server/pipeline_routes.py` is its own module because it is the one part of the capture
    server that can cause money to be spent. **One route does, and it is named for it**:
    `POST /pipeline/identify` refuses without an explicit `confirm`, and refuses a second run
    over a capture directory a live run is already reading. The preflight beside it is free
    and creates no run directory at all. Everything else there — the reads, and
    `join`/`emit`/`reconcile` — is free and re-runnable, which is D1's two-phase split.

    **The money step spawns detached and is never awaited**; the free steps answer inside the
    request with their own stdout attached. A run therefore outlives a restart of the server
    that started it, which is what makes `GET /pipeline/runs` able to show a run somebody
    started in a terminal.

    `app/src/RunPanel.tsx` draws it UNFOLDED, the owner having overruled the fold on 2026-08-24
    (D33, amended), and `app/tests/run-panel.spec.ts` is the check the hard rule says does not
    exist — the strongest of its cases being negative: **before the free preflight has answered,
    the control that spends does not exist.** Absent, not disabled.

    **THE PANEL'S ADDRESS MOVED TWICE AFTER THIS STEP AND THIS PARAGRAPH NAMED THE FIRST ONE.**
    It read "on `#/inventory` — sharing one `.browse-boxrun` row with `BoxOps`", which D38
    superseded within a day and D39 superseded outright: the pipeline has its own route, `#/runs`,
    as of 2026-08-29. Corrected rather than left standing, because this is a build-order note
    about what exists and not a measurement of a run — the numbers in the gate sections above are
    what this file never rewrites. The case count went with it for the same reason `docs/DESIGN.md`
    stopped publishing its assertion total: `npx playwright test` owns it.

    **What this step did NOT do**: no run has been started from the app. The panel's preflight
    and its three free steps have been exercised against the real store — a real `join` of box
    2 was driven end to end from the screen — but every identification this project has paid
    for was submitted from a terminal, and `POST /pipeline/identify` has been proven only by
    its refusals. Recorded here rather than left to be assumed from a green spec, in the same
    words this file uses for T6's synthetic composites.

**THE FIRST TWO OF THESE THREE were appended rather than inserted, and that is forced rather
than tidy.**
`scripts/docs-audit.py`'s repo-map check compares the set of step numbers here against
`docs/map.py` in BOTH directions, so renumbering 10-12 to make room would have to land in
four files at once. Appending costs nothing and the ordering is carried by `status` and
`blocked_by`, not by the integers.

**Nothing in this list is blocked on a third-party benchmark.** A sub-floor T1 is worked
directly — see the T1 section above. The TCGplayer Scan & Identify comparison was removed
from this list on 2026-08-03 and parked in `docs/DECISIONS.md`; it is available as a
reference point when someone wants it, never as a precondition.
