# Gates, harness, build order

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
- **Known blind spot**: official API images show no foil texture, so T1 cannot validate the
  `finish` field. That is Gate B's job. Do not let a green T1 be read as variant detection
  working.

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
  target; no card -> not found
- The sweep is offset, scale and rotation. "Bands" are the title band and the number
  corner, and each must contain its target region. "Not found" must be a refusal, never a
  guess.
- **Known blind spot, and it is the important one**: this measures the algorithm against
  images this repo generated, which is not the same as measuring it against photographs
  from the rig. Real detection rates are a Gate B number. A green T6 means the geometry is
  self-consistent, **not** that detection works. Treat it exactly as T1's finish blind spot
  is treated: recorded here so a green harness cannot be misread.

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
- **7b's three routes are covered as of 2026-08-13**, the day they landed: `GET /queues`,
  `POST /review/<box>/<index>/answer` and `POST /inventory/<box>/<index>/sold` — the
  standing-queue read, D4's one-tap answer, and D10's mark-sold with its reversal. This
  bullet said those routes did not exist. **Of everything 7b shipped, the routes are the one
  part that did not get built ahead of its evidence**, and that is worth noticing when
  reading the rest of it.
- **Known blind spot, and it is 7b's**: every queue entry these cases assert against was
  hand-built by the test. What a green T7 says is that the routes behave the way
  `docs/DESIGN.md` describes — **not** that a real run produces entries of that shape,
  because no real run has produced one at all. Same standing as T6's synthetic composites
  and T1's flat renders: self-consistency, not evidence. Gate B is where that changes.

---

## Gates

### Gate A — TCGplayer seam. PASSED 2026-07-26

Level 4 confirmed. SV09 fixture exported and committed. 2-row Import to Staged validated
end to end. Finding: an "Export From Staged" button exists — see T2.

### Gate B — 20-card end-to-end smoke test

**This gate is a physical run, and it is next.** Build-order step 7 is done as of
2026-08-13, so nothing further can be built toward this — twenty real cards, the rig, the
camera, the lamp and a person feeding them. It cannot be simulated, and no harness result
substitutes for it.

**No part of this repo has met a card.** That is a statement about the whole tree and not
about one unfinished screen. Step 4's pipeline is verified against fixtures and synthetic
composites; step 5's server is verified against T7's temporary directories; step 7's app —
both halves, capture and queue alike — is verified against `docs/DESIGN.md` and hand-built
props. T1 scores flat catalog renders with no foil, no glare and no rig lighting, and
`docs/map.py` and T6's own section both say in writing that a green harness is
self-consistency rather than evidence. **Every number this project has is a number about
itself.** Gate B is the first one that will be about a card.

Manual capture button, no auto-detect. Capture → server save → batch script → join → CSV →
import back into app → pull modal shows correct location.

Also validates what the harness cannot: **Haiku finish detection against ~10 real photos of
known-variant cards.** Include one raking-light shot — the diffused glare-killing rig may
suppress exactly the foil signal detection relies on. If it does, that is a rig finding,
not a model finding, and the fix is a second capture angle rather than a prompt change.

**Take measurements while it runs, and know which ones before the day.**
`docs/specs/capture-app.md` section 10.2 lists them: queue depth as a rate, which of the
twelve reason codes fired and which fired zero times, and the price distribution across the
run and across the queue. Those three were guesses when 7b was built early, and this run is
the first chance to replace them with numbers. **None of them moves the pass criteria** —
pass or fail stays at twenty cards end to end, per that spec's section 10.1.

### Gate C — feeder integration

**The feeder exists and runs today** (confirmed 2026-08-13). Cards are fed onto a tray,
landing in the same spot each time. This gate is therefore tuning against a rhythm that
already exists, not building one — which is a smaller job than this section was written to
describe.

It does not move auto-capture earlier. Gate B stays manual, on the original reasoning:
auto-capture was scoped as an incremental addition after step 7 because of its own
complexity, and a gate that tests the pipeline and an untuned trigger at once cannot say
which one failed. `docs/specs/capture-app.md` builds the trigger as one replaceable piece
so that this gate is an addition rather than a rewrite.

The feeder pauses per card, so the favored method is v1's motion state machine
(motion → stabilize → capture → cooldown), tuned once against a consistent mechanical
rhythm. Video frame extraction (ffmpeg) is the fallback if tuning misbehaves. Confirm with
a 50-card run, then scale to a full box.

---

## Build order

1. ~~Repo init, fixtures committed, git from commit zero~~ — done.
2. ~~**Scaffolding**: `Makefile`, `.claude/settings.json` hooks, `scripts/screenshot.sh`,
   empty harness that exits 1. Do this before any feature so the check exists first.~~ — done.
3. ~~Verification harness (T1–T4)~~ — done; T5 and T6 arrived with step 4.
4. ~~Batch script v2: Batch API, variant ladder, catalog join, real CSV library~~ — code
   done 2026-08-03, spec at `docs/specs/batch-script.md`, harness green at T1–T6.
   `./pkmnscan identify | join | emit | reconcile`. **Not yet run against a real card**:
   that is Gate B, and until it passes this is verified against fixtures and synthetic
   images only.
5. ~~Capture server: `POST /capture`, position-ordered filenames, JSON sidecars (position,
   box, set hint, variant), `/status`, `GET /photo/<box>/<position>`, `GET`/`PUT` inventory
   state shared across devices.~~ — done 2026-08-11, spec at `docs/specs/capture-server.md`.
   Positions are allocated inside the store lock by `allocate_capture`. **T7 reaches it as
   of 2026-08-13**: every route, every named refusal, and the sidecar seam read back through
   the reader `identify` uses. This line said the opposite for two days — the step shipped
   with nothing under `harness/tests` importing `server`, `store` or `cli` — and the claim
   outlived the gap it described. What T7 still does not assert is in `docs/DEBTS.md`, and
   is now three named cases rather than a whole package.
   The server carries nine routes now, not the five this line was written about: a sixth,
   `DELETE /inventory/<box>/<index>`, arrived with step 7a's undo, and three more with 7b —
   `GET /queues`, `POST /review/<box>/<index>/answer`, `POST /inventory/<box>/<index>/sold`.
   All four came with their own T7 cases on the day they landed.
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
   `app/tests/fulfillment.spec.ts`. Both specs pass — 30 assertions, green since the routing
   landed; see below for the several hours in which they did not.

   **Split at Gate B — and then the split was not honoured.** 7a is the Gate B path: the
   shell, the capture screen, undo, the pull preview and the trigger seam, specified in
   `docs/specs/capture-app.md` and built to it, along with the one new server route and the
   two eslint rules that make `make lint` real. 7b is the review queue, the Fulfillment
   view, the inventory SKU views and mark-sold — scheduled *after* the gate, so that it
   would be built against a real run rather than against guesses about what one produces.

   **7b was built before Gate B, at the owner's explicit instruction.** The spec's scope
   section and its "what this session must not build" list both said otherwise; both are
   left standing there and marked overtaken, and that file's STATUS section carries what it
   costs. The short form, and the reason this list carries it too: **the screens 7b added
   display data that no run has ever produced.** The review queue's row hierarchy is tuned
   against a price distribution nobody has measured, and the twelve reason codes it renders
   have never all fired. Read those screens as specified-and-unvalidated, never as
   observed.

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
   anything, and Gate B is the name for doing it.

   **"CSV import with error reporting" was struck from this list on 2026-08-13.** It was a
   v1 feature that batch script v2 absorbed whole: `emit` writes `pushed`, `reconcile` moves
   `pushed` to `staged` off the Export From Staged, and `join` moves `staged` to `live` off
   the Filtered Export. Every state transition is owned by a command, and the app reads
   state rather than setting it — so there was nothing left for the feature to do. Recorded
   rather than deleted silently, because the phrase would otherwise be reinstated from an
   older copy of this list. The bidirectional-reporting guarantee it once carried (v1 bug 5)
   is T3's, and T3 is unaffected.
8. Gate B smoke test.
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

**Nothing in this list is blocked on a third-party benchmark.** A sub-floor T1 is worked
directly — see the T1 section above. The TCGplayer Scan & Identify comparison was removed
from this list on 2026-08-03 and parked in `docs/DECISIONS.md`; it is available as a
reference point when someone wants it, never as a precondition.
