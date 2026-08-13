# Gates, harness, build order

## The harness is the contract

`make harness` runs six tests and exits non-zero on any failure. Nothing is "done" until
it exits 0 and you have seen the output. This is the whole reason the project can be run
by an agent unattended — without it, "looks done" is the only available signal.

T1–T4 are the original contract. T5 and T6 arrived with batch script v2 (build-order
step 4): a wrong price is a distinct failure from a wrong match, and a card the pipeline
cannot find in its own photograph is a third thing again. Each deserves its own failing
test name.

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

---

## Gates

### Gate A — TCGplayer seam. PASSED 2026-07-26

Level 4 confirmed. SV09 fixture exported and committed. 2-row Import to Staged validated
end to end. Finding: an "Export From Staged" button exists — see T2.

### Gate B — 20-card end-to-end smoke test

Manual capture button, no auto-detect. Capture → server save → batch script → join → CSV →
import back into app → pull modal shows correct location.

Also validates what the harness cannot: **Haiku finish detection against ~10 real photos of
known-variant cards.** Include one raking-light shot — the diffused glare-killing rig may
suppress exactly the foil signal detection relies on. If it does, that is a rig finding,
not a model finding, and the fix is a second capture angle rather than a prompt change.

### Gate C — feeder integration

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
   Positions are allocated inside the store lock by `allocate_capture`. **No harness test
   reaches it**: nothing under `harness/tests` imports `server`, `store` or `cli`, so a
   green harness says nothing about this step — see `docs/DEBTS.md`.
6. ~~Design tokens locked and one component built against them~~ — done 2026-08-12.
   Tokens locked by interview against rendered alternatives rather than by inference; the
   pull-confirm built against them at `app/src/PullConfirm.tsx`, in all three states, on a
   gallery route `make screenshot` renders and `make design-check` asserts.
   **Building it earned its place**: it caught two points where
   `docs/design-refs/locked.html` contradicts `docs/DESIGN.md` — an 18px button label under
   the view's own 20px floor, and a keyboard chip on a control only the Fulfiller touches.
   Both are recorded in `docs/design-refs/README.md`; neither was visible in prose.
7. Vite capture app: device picker, manual capture, set hint + variant toggles, position
   tracking, undo, inventory views (SKU → positions), review queue, pull preview with
   photo, Fulfillment view, CSV import with error reporting. The toolchain arrived with
   step 6 — `app/` is a Vite + React + TypeScript project already, so this step adds
   screens rather than a build system. Extend `app/tests/pull-confirm.spec.ts` to the rest
   of `docs/DESIGN.md`'s Fulfillment table as the views that carry those rows land.
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
