# UX review, 2026-09-23

The record of the second whole-product UX review. Seven blind lenses looked at the published
demo, built from main at PR #454 and #455. Two more lenses joined during the owner's interview.
A held-screen pass followed once the photo branch merged (PR #456). Every reviewer was
read-only. Nothing was pressed that writes to a real store.

The design that came out of it lives in `docs/specs/ux-overhaul-2026-09-23.md`. The box map
feature lives in `docs/specs/box-map.md`. The decision entries are cited from both.

## The standard these were written to

The owner's complaint started the review:

```
I think I really need a massive UX pass/review again as so many features have been
incorporated since we started banchi and they're not syncing.
```

Each lens graded in two passes. **Pass 1 was blind.** A lens did not read `docs/decisions/`,
`docs/DESIGN.md`, `docs/specs/` or this folder before its grades and findings were written. It
graded by what the owner experiences. **Pass 2 annotated.** The lens then read the decisions
and marked each finding "caused by", "violates" or "no decision covers this". So a finding may
contradict a settled decision on purpose. The owner weighs that.

## The files

| File | Covers |
| --- | --- |
| `CONSOLIDATED.md` | The merged findings (UX ids), the grade matrix, the ten themes, the decisions in question, and the gaps |
| `RULINGS.md` | The owner's rulings from the interview, and the orchestrator's notes |
| `LANES.md` | The lane plan, both rounds merged, with the wave-2 file scopes and the iconography pointer |
| `BUILD-BRIEF.md` | The shared brief every builder lane reads before it starts |
| `REAL-TEST.md` | The owner's first real TCGplayer test, step by step, after the overhaul reaches main |
| `coherence.md` | Lens 1: one concept, one name, one count (COH) |
| `loop.md` | Lens 2: the daily loop, walked end to end (LOOP) |
| `visual.md` | Lens 3: the visual system, and a read-only look at the live app (VIS) |
| `interaction.md` | Lens 4: interaction and feedback (INT) |
| `copy.md` | Lens 5: the words on screen (COPY) |
| `access.md` | Lens 6: keyboard, focus, contrast and touch (ACC) |
| `density.md` | Lens 7: text density, and the cut list (TXT) |
| `filtering.md` | Lens 8: filters, sorting, search and scope, and the owner's gripes (FLT) |
| `locating.md` | Lens 9: how fast the owner knows where a card is (LOC) |
| `held-orders-review.md` | The held-screen pass on `#/orders` (HOR) |
| `held-inventory-review.md` | The held-screen pass on `#/inventory` and `#/review` (HIR) |

## Before you rank anything, read this

1. **The counts.** The first seven lenses logged 250 findings, which merged into 164 distinct
   findings. Round two added 142 lens findings: 38 FLT, 29 LOC, 35 HOR, 39 HIR and one incident.
   The second consolidation merged all 392 into **272 distinct findings**, UX-001 to UX-272: 9
   S1, 74 S2, 138 S3 and 51 S4. Each round-two finding maps to exactly one UX id.
2. **Coverage is uneven.** Every file ends with what it could not check. An UNKNOWN is not a
   pass. The demo has no server, so seven write paths are refused there. The demo also has no
   photographs and no recording for several reads.
3. **The live look was GET only.** The visual lens loaded five screens of the owner's live app,
   10 loads in all. The held-orders reviewer's scratch copy also read the live store once by
   accident. `RULINGS.md` records that incident.
4. **`CONSOLIDATED.md` is the second consolidation.** Every round-one id is stable. The first
   version, with 164 findings, is in this folder's git history. The lane plan that follows from
   it is section 5 of `docs/specs/ux-overhaul-2026-09-23.md`.

## What was changed from the reviewers' own files

The copies here differ from the files the reviewers wrote, in six ways only.

1. **No screenshot, script or raw data was kept.** Each "Shot" line now names its finding and
   says "screenshot not kept". A path into the reviewers' scratch folder became the lens id and
   "not kept".
2. **Every line that named a private live screenshot was removed.** The live screenshots held
   real store data. The markers that flagged live data went with them.
3. **Two live revenue totals and a real product string were removed.** A sentence now says
   "two five-figure dollar totals". The words now say only what shape the live catalog string
   had. Store counts, such as open orders and rows, stay, by an orchestrator call.
4. **No real buyer name appears.** The held-orders pass gave its seeded orders invented names.
   Those names are the only buyer names here.
5. **Line numbers were dropped from code citations.** A citation names a symbol, never a line.
   Where a finding cited a file at a line, it now names the file alone.
6. **A few spellings changed** so the path and id audits read them right. In
   `CONSOLIDATED.md`, each theme id became "Theme" and its number, because a T id reads as a
   harness test. A request path
   got its method (`GET /pipeline/price-now`). One card place, written as a short code, became
   words.
