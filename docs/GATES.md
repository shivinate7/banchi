# Gates, harness, build order

## The harness is the contract

`make harness` runs four tests and exits non-zero on any failure. Nothing is "done" until
it exits 0 and you have seen the output. This is the whole reason the project can be run
by an agent unattended — without it, "looks done" is the only available signal.

Every threshold below is a number, not an adjective. `ID_ACCURACY_FLOOR=0.95` is a spec;
"about 95%" is an opinion an agent can talk itself past.

### T1 — Ground-truth ID eval

Download ~50 official card images from pokemontcg.io across 2–3 sets as labeled fixtures
(the API record IS the label). Run identification against them. Report accuracy per set
and overall.

- **Pass**: `overall_accuracy >= 0.95`
- Rerun after any prompt change. Commit the score to `harness/results/` so regressions are
  visible in the diff. One file per date AND configuration — a hinted run and an unhinted
  run are different measurements and must never share a filename.
- **Known blind spot**: official API images show no foil texture, so T1 cannot validate the
  `finish` field. That is Gate B's job. Do not let a green T1 be read as variant detection
  working.

**Below the floor, tune the prompt — but never against the cards you score on.** Fixing the
specific images that failed and re-measuring on the same set reports a number that means
nothing about the next card, and that number is the whole basis for trusting identification
once there is no answer key. So: hold out a slice the tuner never sees the failures from,
tune against the rest, and report only the held-out score. `PKMNSCAN_REFRESH_IMAGES=1` with
a different `EVAL_SETS` draws a fresh sample.

**50 images is a small sample.** One card is two percentage points, and the confidence
interval is roughly ±6, so 0.94 and 0.96 are not meaningfully different. Now that the
pokemontcg.io key is in place, prefer 150–200 images — it costs cents and makes the
verdict mean something.

### T2 — Fixture round-trip

Load `fixtures/sv09_export_untouched.csv`, fill `Add to Quantity` and
`TCG Marketplace Price` on sample rows, write, re-parse.

- **Pass**: exactly those two fields differ, and byte format is preserved — unquoted header
  row, fully quoted data fields, CRLF line endings.
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

- **Pass**: zero unmatched, or unmatched reported and output suppressed.

### T4 — Variant ladder

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price: metadata-driven, catalog-forced,
detection-driven, and the disagreement → review path.

- **Pass**: all four stages, plus the review path fires on disagreement.

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
2. **Scaffolding**: `Makefile`, `.claude/settings.json` hooks, `scripts/screenshot.sh`,
   empty harness that exits 1. Do this before any feature so the check exists first.
3. Verification harness (T1–T4).
4. Batch script v2: Batch API, variant ladder, catalog join, real CSV library.
5. Capture server: `POST /capture`, position-ordered filenames, JSON sidecars (position,
   box, set hint, variant), `/status`, `GET /photo/<box>/<position>`, `GET`/`PUT` inventory
   state shared across devices.
6. Design tokens locked and one component built against them — see `docs/DESIGN.md`.
   Before any screen.
7. Vite capture app: device picker, manual capture, set hint + variant toggles, position
   tracking, undo, inventory views (SKU → positions), review queue, pull preview with
   photo, Fulfillment view, CSV import with error reporting.
8. Gate B smoke test.
9. **Vendor the pokemontcg.io catalog** — see D15. Three pieces, in order:
    - Snapshot `PokemonTCG/pokemon-tcg-data` into the repo (183 files, 27.4 MB) with a
      `make` target that refreshes it and records the upstream commit SHA.
    - Build the SQLite index. Cards join to sets by *filename* — `printedTotal` is only in
      `sets/en.json`, and it is half the join key.
    - Fill the image mirror from `images.pokemontcg.io`: rate-limited, resumable,
      manifest-driven, per-file skip on a non-empty existing file. Destination is outside
      the iCloud tree (D15) and overridable by `PKMNSCAN_IMAGE_MIRROR`; move
      `harness/images/` there too. Dry-run the `Content-Length` sum first — ~16.7 GB is
      extrapolated from a 197-image sample, so confirm before committing the disk.

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
