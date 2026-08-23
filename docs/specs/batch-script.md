# Batch script v2 — spec

Build-order step 4. Interviewed and settled 2026-08-03. Supersedes nothing; where it
contradicts an existing document that contradiction is called out explicitly under
[Required document amendments](#required-document-amendments) and needs the owner's edit
before implementation lands.

Every threshold here is a number. An adjective in this file is a defect.

---

## 1. Scope

Wire the existing pure modules — `pipeline/{tcgcsv,variant,pricing,join}.py` and
`identify/{prompt,batch}.py` — into a runnable pipeline, and build the pieces those modules
deliberately left absent:

- pricing rules beyond `match` (undercut %, markup %, basis, rounding)
- multi-set catalog keying
- the identification cache and run lifecycle
- crop retry for unreadable cards
- the inventory master store and its `pushed → staged → live` states

**Not in scope.** No pokemontcg.io access of any kind — D15 vendors that catalog at build
step 9, *after* Gate B, and states step 4 does not depend on it. No web UI (step 7, behind
Gate B, and CLAUDE.md forbids new surface area before the current gate passes). No capture
server (step 5). No feeder (step 10).

**Logic never lives in `harness/`.** `pipeline/__init__.py` is explicit: the harness tests
the pipeline, so the pipeline cannot live inside the harness. New logic goes in `pipeline/`,
`identify/`, and the new modules named below. The harness grows tests only.

---

## 2. Commands

Four commands, because a batch takes minutes to hours and the pricing decision needs a
human. One blocking command would put a person in the middle of a poll loop.

```
pkmnscan identify   <capture-dir>   submit, wait, collect, cache. Costs money.
pkmnscan join       <run-dir>       resolve against the export. Free, re-runnable.
pkmnscan emit       <run-dir>       write import CSVs. Free, re-runnable.
pkmnscan reconcile  <run-dir> <staged-export.csv>   confirm what TCGplayer actually staged.
```

Each is independently resumable and re-runnable. `join` and `emit` cost nothing, so
re-running them after fixing a review or changing a price is free.

---

## 3. Storage

One master store sits atop the runs and is fed by them. Runs are immutable inputs;
deleting one must never cost money or state.

```
inventory/
  inventory.json        MASTER. Cards, positions, SKUs, listing states.
  history.jsonl         Append-only event log. Never rewritten.
  identifications.json  The cache. Answers already paid for.
  review.json           Standing main review queue. Survives runs.
  parked.json           Standing low-value queue. Survives runs.
  .lock                 Exclusive lock file.

runs/<YYYY-MM-DD>-<label>-<nn>/
  manifest.json         Inputs: capture dir, export path + mtime + sha256, prompt
                        fingerprint, flags, batch ids, cost.
  identifications.json  What this run read, before caching.
  decisions.json        The pricing decision. Written by join, edited by you (or the
                        app at step 7), read by emit.
  report.txt            The join report, both directions, verbatim.
  import-listed.csv      Above-threshold import file.
  import-subthreshold.csv Sub-threshold import file.
  reconcile.txt         Written by reconcile.
```

**Write discipline.** `inventory.json` is rewritten whole: to a temp file in the same
directory, then `os.replace()` into position — atomic on POSIX, so a reader sees the entire
old file or the entire new one and a crash mid-write leaves the old file intact. All
read-modify-write cycles hold an exclusive lock on `.lock`, because atomicity prevents torn
files but not lost updates: two writers each reading, each modifying, each writing back
means the second silently erases the first. The capture server (step 5) uses the same lock
and the same atomic write; it is a second writer, not a second owner.

`history.jsonl` is append-only and is the audit trail — when a card was captured,
identified, pushed, staged, live, sold. D10 makes this worth keeping: positions are never
renumbered and sold cards leave permanent gaps, so the history *is* inventory truth over
time.

**Not SQLite.** D13 settles inventory as server-side JSON. D15's SQLite is the read-only
*catalog* index at build step 9 and is a different thing entirely. A later session that
"upgrades" inventory to SQLite is re-litigating D13.

---

## 4. `identify`

### 4.1 Preflight

Always printed before anything is submitted: card count, total payload bytes, batch chunk
count, estimated cost, prompt fingerprint, cache hits vs sends. `--dry-run` does everything
except the API call — so sidecar problems, unreadable images, and a mistyped directory
surface for free.

### 4.2 Input

Photos plus JSON sidecars (position, box, set hint, variant toggle).

| Sidecar state | Behavior |
|---|---|
| Present and valid | Normal path. |
| Missing or malformed, filename carries position | Position recovered from the filename and treated as equivalent — the same server writes both, so it is the same claim from the same source. |
| Missing, no position recoverable | Card is still identified, then routed to the main review queue flagged `no_position`. Never skipped: a skipped card is v1 bug #5 wearing a report. |

A missing set hint or variant toggle is not an error. The ladder's rung 2 exists for
exactly that case.

### 4.3 Images

Downscale to **1568px** on the longest edge (`--max-edge`). Anything larger is billed and
then discarded by the API. Originals are never modified — the review queue and any retry
read them from disk.

### 4.4 Batching, resume, retry

Submission uses `identify.batch.run_batch` unchanged: one submission, poll, collect by
`custom_id`. There is no per-card path and none is added.

Batch ids are written to `manifest.json` **before** the first poll. Re-running `identify`
on a run directory with an unfinished batch **reattaches and collects by default** —
results stay retrievable for 29 days, so re-submitting is paying twice for an answer you
already own. `--force-resubmit` pays again deliberately (e.g. after a prompt change).

Per-request failures — `errored`, `expired`, `canceled`, `malformed` — are retried with a
bounded budget, **default 1**, `--retry-budget`. The count and the reasons appear in the
run report so a systematic failure cannot look like scattered bad luck. Cards still failing
after the budget go to the **main** review queue as `identification_failed` (no
identification means no price, and an unpriced card is not a cheap card).

### 4.5 Crop retry

A card returning `low` confidence or `malformed` is re-sent once, within the retry budget,
with cropped regions attached alongside the full image. A `025` rendered 40px wide in a
downscaled full-card image is a coin flip; the same digits cropped and upscaled are not.

Region location, in order:

1. **Find the card in the frame** — new `geometry` module. Detect the card's boundary and
   register it to a known rectangle. **Two methods since 2026-08-22, in order**: segment by
   tone, and if that refuses, search for the card's border. The second exists because the
   first found nothing in any of the 53 Gate B photographs — see `docs/GATES.md`'s T6
   section for the measurement and the mechanism. `CardBox.method` says which one answered.
2. **Crop within the registered card** using generous fractional bands (title band, number
   corner). Generous, not tight, so small rotation or offset does not push the number out
   of frame.
3. **Detection fails → no crop retry.** The card goes straight to the main review queue.
   If the card cannot be found in the image at all, a human should look; cropping blind
   produces a miss that is indistinguishable from a bad read. Detection failures are named
   in the report so a systematic rig problem shows as a pattern.

`geometry` is its own module because the Gate C feeder needs the same detection. It runs at
**batch time**, not capture time: D1 requires capture to be fast, offline, and dumb. That
clause used to end "and the capture server does not exist yet", which stopped being true at
step 5 on 2026-08-11 — the reason is D1 on its own, and it did not need the second half.

*Dependency note, and its trigger has now fired.* Downscaling and cropping need Pillow.
Card-boundary detection was specified to be attempted with Pillow + numpy first, with
`opencv-python-headless` named as the fallback **if measured detection rates are poor**.
They were measured on 2026-08-22 and they were as poor as they get: 0 of 53. Written down
rather than quietly re-dated, the same rule `docs/DESIGN.md` applies to a fix trigger that
fires and is passed.

**The fallback was not taken, and the reason is that opencv would not have helped.** The
tone path did not fail for want of a better segmentation library; it failed because its
premise — a background flat relative to the card's own contrast — is false on this rig, and
a planar background fit and a bottom-band background were both measured failing too. What
answered it was a different question (find the border, not the region), and that is forty
lines of numpy. `requirements.txt` still names what it omits, and opencv is still omitted —
now against a measurement rather than against the absence of one.

### 4.6 The cache

Keyed by **position**. Each entry stores the identification, the photo's sha256, the prompt
fingerprint, the timestamp, and `cleared_by_human`.

An answer is reused when position and photo hash still match. Position is the identity; the
photo hash is the staleness check, and it is what makes a re-shot photo get re-read instead
of silently returning the answer to a picture that no longer exists.

**The prompt fingerprint is recorded, not enforced.** It is deliberately not part of the
reuse test — see the `Prompt changed` row below and the rationale under the table. (This
paragraph previously said an answer was reused "only if position, photo hash, and prompt
fingerprint all still match", which contradicted that row. Corrected 2026-08-03; the table
is what was built.)

| Situation | Behavior |
|---|---|
| Run died at card 300 of 500 | 300 reused, 200 sent. |
| 200 new cards added to the box | Only the new 200 sent. |
| Card 47 re-shot | Photo hash changed → re-read automatically. |
| Prompt changed | **Reused, not invalidated.** The report states how many answers came from an older prompt. |
| Prompt changed, `--reidentify-stale` | Re-reads only *weak, uncleared* entries: confidence `low`, or currently sitting in a queue, and `cleared_by_human == false`. |

**A human-cleared identification is permanent.** Once you have looked at the photo and
picked the row, no re-run, prompt change, or re-identification pass overwrites it. If a
later run happens to read that photo and disagrees, the report says so — cheap evidence
that either the prompt improved or a clearing was a mistake — but the human answer stands.

Rationale for not auto-invalidating on a prompt change: T1 must invalidate strictly,
because a score has to come from the prompt being scored, and the harness already does
that. Production inventory is a different problem — re-reading thousands of correct answers
because one line was reworded costs real money to mostly reproduce them. The fingerprint's
production value is that it is *recorded*, making a targeted re-read possible.

---

## 5. `join`

### 5.1 Catalog and multi-set keying

Catalog is built from the TCGplayer Filtered CSV export. Nothing else. Join key stays
`zfill(3)(number) + "/" + printedTotal` (CLAUDE.md, and `161/159` is a secret rare, not an
error).

That key is unique only *within* a set. Multi-set runs are required, so:

1. At catalog build, compute the set of keys that map to rows in more than one `Set Name`.
   Cheap, deterministic, known before a single card is joined.
2. Non-colliding keys — the large majority — join exactly as they do today.
3. A colliding key uses the sidecar **set hint** to pick among the candidate sets.
4. No hint, or a hint matching none of the candidates → main review queue,
   `set_ambiguous`. Never guessed.

The collision count is reported at catalog build so the real exposure is visible rather
than assumed.

This deliberately does **not** make the set hint authoritative everywhere (D2 and the
prompt both call it optional and possibly wrong) and does **not** add a set field to the
identification schema (a prompt change plus a full T1 re-run, to read a set symbol far less
legibly printed than the digits).

*Latent bug this closes:* `variant.resolve` builds `by_condition = {row[CONDITION]: row}`,
which silently keeps the last row when two rows share a condition string — exactly what a
cross-set key collision produces.

### 5.2 Export staleness

The export's mtime, age, and sha256 are recorded in `manifest.json` and the age is printed
on every run. **Warn only; never refuse.** A stale export is a judgment call, and a hard
stop on a snapshot age would block a legitimate run for a reason the operator can see for
themselves.

### 5.3 The ladder

`pipeline/variant.resolve` is used unchanged. D3 is settled; nothing here reopens it.

**One thing now happens before it, and it is not in `resolve`** (added 2026-08-22). D3's
rung 0 — a human's answer from the review screen — is applied by `join_batch`, above the
ladder rather than inside it, and it nulls confidence so the routing table below cannot
re-queue an answered card. `resolve` is genuinely untouched; the addition is a
short-circuit in front of it, because every rung `resolve` walks infers a finish from
evidence and an answer is not an inference. It falls through to the ladder when the current
export no longer carries that SKU, or carries it under a different Condition.

### 5.4 Routing — which queue a card lands in

Confidence describes how legible the title and collector number were. It is the **only**
signal that a card was guessed at: a misread `026/198` as `025/198` is still a valid number
that joins to a real row, so nothing downstream can catch it.

| Condition | Destination |
|---|---|
| Resolved cleanly, confidence `medium`/`high` | Listed. |
| Confidence `low`, resolved market **≥ $0.40** | **Main review queue.** Not listed until looked at. A wrong listing on a $12 card ships the wrong card to a buyer; that is worse than a tap. |
| Confidence `low`, resolved market **< $0.40** | **Parked** in the low-value queue. Not listed, not dropped, never in the main queue. |
| Ladder → review (D3 reasons) | Main queue if the cheapest candidate row is ≥ $0.40, parked if below. |
| No catalog row, or identification failed | **Main queue, sorted last.** No price is not a low price — a misread secret rare is exactly this case. |
| Matched row with blank or $0.00 market price | **`no_market_data` category. Never auto-priced, never swept into the sub-threshold flat price.** A missing price is an unknown price; handing away a $40 chase card at the $0.40 floor is the failure this prevents. |

`--review-below-confidence=none|low|medium` (default `low`) tunes the confidence rule.
`none` restores "confidence never routes on its own".

Main-queue sort order: priced-and-ambiguous first, descending by price; unpriced last. You
work the known-valuable cards first, and nothing is hidden.

### 5.5 The queues

`review.json` and `parked.json` are **standing** files keyed by position, not per-run. Each
entry: position, photo path, what was read, confidence, reason, candidate rows, first-seen
date.

Every run report **leads** with the standing queue totals and their age
(`14 cards in review, oldest 22 days`), and `emit` **restates** them beside the row count it
wrote. You see the number when choosing what to work on, and again at the moment you commit
an import file.

Parked cards are explicitly candidates for the D9 Bulk Lots exit — an unidentifiable
15-cent card may never be worth a tap.

### 5.6 Reviews never block emit

An unresolved card sits at a known position in a box. It is not lost, and it is not urgent.
Holding 400 good cards hostage to 7 ambiguous ones is the wrong trade.

`join` reports both directions in full and writes every unmatched card to a queue **before**
any output exists. `emit` then writes the matched cards. The hard rule — never write output
before reporting unmatched rows in both directions — is satisfied by the report and the
queue files, not by suppression.

**This changes the current behavior of `join.emit_import`,** which raises `OutputSuppressed`
whenever `report.ok` is false. See [Required document amendments](#required-document-amendments).

---

## 6. Pricing

### 6.1 Rules

```
rule    = match | undercut:PCT | markup:PCT
basis   = market (default) | low          --basis
```

Basis default is **`TCG Market Price`** — the recent actual-sale average, so an undercut
prices below the going rate instead of chasing one desperate seller. D8 already names
Market as the pricing source and D9's threshold check uses it, so the default keeps one
number doing both jobs. `--basis=low` switches to `TCG Low Price` for a box you want gone.

The **threshold** check always uses `TCG Market Price` regardless of basis. D9 says market
≥ $0.40 earns a listing; that is a statement about value, not about pricing strategy.

### 6.2 Order of operations

```
price = clamp_floor( round_2dp_half_up( rule(basis_price) ) )
```

Round to two decimals, half up. Then clamp to the floor — in that order, so rounding can
never sneak a price under it. Floor and threshold are both `$0.40`, both configurable, both
already in `pipeline/pricing.py`.

### 6.3 Sub-threshold disposition — `decisions.json`

D9 forbids the script from guessing what happens to a sub-threshold card. The decision is
**a file, not a flag**, so the step 7 React screen becomes a nicer editor for an existing
contract rather than a second code path.

`join` writes `decisions.json` pre-filled with every sub-threshold SKU — name, market price,
copy count, suggested price — and the run-wide choice **unset**. You edit it today; the app
edits the same file through the capture server later. `emit` reads it and refuses to write
if the run-wide choice is still unset.

```jsonc
{
  "rule": "match",
  "basis": "market",
  "sub_threshold": null,          // "floor" | {"flat": "0.25"} — MUST be set
  "overrides": {                  // per-SKU, works above or below threshold
    "8823901": "0.35"
  },
  "no_market_data": {             // never auto-priced; priced here or left unlisted
    "8823944": null
  }
}
```

---

## 7. `emit`

Writes **two** import files:

- `import-listed.csv` — above-threshold cards
- `import-subthreshold.csv` — cards priced by the run's disposition

Two files so the valuable cards can be staged and moved live immediately while the bulk
file waits, and so a pricing mistake on the cheap file cannot touch the valuable one. Each
file independently obeys the no-duplicate-SKU rule.

Byte format is `pipeline.tcgcsv` unchanged: unquoted header, fully quoted data fields, CRLF,
only `Add to Quantity` and `TCG Marketplace Price` ever written, `TCGplayer Id` never
modified. `check_only_writable_changed` runs per row against the catalog original.

`emit` refuses — loudly, writing nothing — when:

- the run-wide sub-threshold choice is unset while sub-threshold SKUs exist
- two rows in one file share a `TCGplayer Id`
- any non-writable column differs from the catalog original
- a `no_market_data` SKU has no hand-entered price

`emit` does **not** refuse for a non-empty review queue. It restates the queue totals beside
the row counts it wrote.

On success, every emitted SKU's copies transition to **`pushed`** in the master store, and
the transition is appended to `history.jsonl`.

---

## 8. `reconcile` and listing states

Writing a CSV proves only that a CSV was written. Three states, each confirmed by something
outside this script:

| State | Confirmed by |
|---|---|
| `pushed` | `emit` wrote the row into an import file. |
| `staged` | **Export From Staged** download, diffed by `reconcile`. |
| `live` | Quantity against that SKU in a later Filtered Export (`Total Quantity`). |

Collapsing `staged` and `live` would make D7's refill math wrong — `Add to Quantity =
min(cap - live, backstock)` reads the *live* number, and an import staged but never moved
live has no live quantity.

`reconcile <run-dir> <staged-export.csv>` uses the existing `join.reconcile_import` and
reports both directions: rows TCGplayer has that the run did not send, and rows the run sent
that did not land. This is the machine-checkable round trip against the real system that
GATES.md calls the highest-value finding from Gate A.

`live` is refreshed whenever `join` loads a fresh export — the `Total Quantity` column is
already read for refill math (`SkuMatch.live_before`), so this costs nothing new.

Cards sitting in `staged` for more than **14 days** (configurable) are named in the run
report — catching an import that was staged and never moved live.

---

## 9. Configuration

| Knob | Default | Where |
|---|---|---|
| `--max-edge` | 1568 | image downscale, longest edge |
| `--retry-budget` | 1 | per-card retries after a batch failure |
| `--review-below-confidence` | `low` | `none` \| `low` \| `medium` |
| `--basis` | `market` | `market` \| `low` |
| `--rule` | `match` | `decisions.json`, seeded by the flag |
| threshold / floor | `$0.40` / `$0.40` | D9, `pipeline/pricing.py` |
| live cap | 4 | D7, `join.LIVE_QUANTITY_CAP` |
| cards per section | 25 | D10 |
| staged-stale warning | 14 days | run report only |
| `--force-resubmit` | off | pay again for an existing batch |
| `--reidentify-stale` | off | re-read weak uncleared entries after a prompt change |
| `--dry-run` | off | everything except the API call |
| `--variant` | unset | fills the finish where a sidecar records none. **Never overrides one.** |

`--variant` is named by D3 rung 1 and was missing from this table as first written (added
2026-08-03). It fills gaps and does not override: D3 spends three paragraphs establishing
that the capture toggle is a *claim*, and a flag that could flatten a box you toggled stack
by stack is the one thing that defeats it. The case it exists for is the capture app not
existing yet — a directory of photos with no sidecars at all, where without it every card
stocked in more than one finish takes a review-queue tap.

---

## 10. Failure modes

| Failure | Behavior |
|---|---|
| Script dies mid-poll | Batch ids persisted before first poll; re-run reattaches and collects. |
| Batch expires (24h API cap) | Reported per card; retried within budget; then main queue. |
| Photo has no sidecar and no recoverable position | Identified, main queue, `no_position`. |
| Card boundary not detectable | No crop retry; main queue; named in report. |
| Two sets collide on one join key | Set hint disambiguates; otherwise main queue, `set_ambiguous`. |
| Matched row has no market price | `no_market_data`; never auto-priced. |
| Sub-threshold decision missing | `emit` refuses to write anything. |
| Concurrent write by the capture server | Exclusive lock; atomic replace. |
| Run directory deleted | Costs nothing — cache and inventory live in the master store. |

---

## 11. Harness changes

Logic in `pipeline/`, `identify/`, `geometry/`; tests in `harness/`.

- **T3 (join coverage)** — extend with multi-set key collisions: colliding key resolved by
  set hint, colliding key with no hint → review, non-colliding keys unaffected.
- **T4 (variant ladder)** — extend with the confidence routing table and the queue-routing
  rules (low + expensive → main, low + cheap → parked, unpriced → main sorted last).
- **T5 (pricing rules)** — new. Undercut and markup against both bases, rounding half-up at
  two decimals, floor clamp applied *after* rounding, threshold always read from market
  price, and the `no_market_data` refusal. A wrong price is a distinct failure from a wrong
  match and deserves its own failing test name.

- **T6 (card geometry)** — new, added at implementation time (2026-08-03) and not in this
  spec as first written. The same argument as T5, one step further along: §4.5's crop retry
  is only as good as its ability to find the card, and a wrong crop produces a miss
  indistinguishable from a bad read. Shipping `geometry/` with no harness test contradicted
  the harness contract more than a sixth test did.

  Synthetic composites only — a card rectangle rendered at a known offset, scale and
  rotation, so the answer key is exact and nothing is downloaded. **A green T6 is not
  evidence that detection works**: it measures the algorithm against images this repo drew,
    which is not the same as photographs from the rig. **That number arrived on 2026-08-22, and
  it was zero**: the tone path found the card in 0 of the 53 Gate B photographs, which is why
  §4.5 now describes two methods and why the border search added beside it finds 53/53.
  `docs/GATES.md`'s T6 section carries the measurement and the mechanism. A green T6 is still
  not a detection rate — one rig, one lighting state, one day, and the regression case is a
  drawing built from the measured ring values rather than a photograph; `docs/DEBTS.md`
  records what that leaves.
  number, and GATES.md records that blind spot the way T1's `finish` blind spot is recorded.

Adding T5 and T6 requires editing `docs/GATES.md`, `CLAUDE.md`'s `make harness` comment
("all four verification tests"), `harness/run.py`'s `TESTS` list, and `README.md`. That is a
deliberate contract change, not a drive-by. **The harness is six tests.**

> **Status, 2026-08-13:** the harness is seven. T7 was added for `store/`, `server/` and
> `cli/`, through exactly the process the paragraph above demands — argued first, the
> contract in `docs/GATES.md` amended, every count reconciled in the same commit. The
> sentence is left as written because the rule it states is the point and still holds; only
> the number moved.

---

## Required document amendments

The spec above contradicted four documents as written, and implementation was gated on the
owner editing them first. All four were applied on 2026-08-03 and the implementation landed
in `41221f6`. Kept as the record of what changed and why, not as an open gate:

1. **`docs/GATES.md`, T3 pass criteria.** Currently: *"zero unmatched, or unmatched reported
   and output suppressed."* Section 5.6 makes reviews non-blocking, so output is **not**
   suppressed. Proposed replacement: *"zero unmatched, or every unmatched card reported in
   both directions and routed to a standing queue with its position retained, before any
   output is written."* Done 2026-08-03.

2. **`docs/GATES.md` and `CLAUDE.md`, harness size.** Both describe the harness as four
   tests. T5 and T6 make it **six**. Done 2026-08-03, along with `README.md` and
   `harness/run.py`'s `TESTS` list.

3. **`pipeline/pricing.py` docstring.** States undercut % and markup % are "build-order step
   4, and are deliberately absent". This spec builds them; the docstring's rationale should
   be retired rather than left describing a state that no longer exists. Done 2026-08-03.

4. **`docs/DECISIONS.md`, D9.** Sub-threshold disposition is described as a per-run choice.
   This spec adds a `no_market_data` category that is *not* dispositioned at all. Worth a
   sentence in D9 so a later session does not "fix" it by sweeping those into the flat
   price. Done 2026-08-03.

---

## Deliberately not built

- Charm pricing (.99/.49) — a second rule interacting with the floor and the undercut.
- Set field in the identification schema — prompt change plus a full T1 re-run to read a
  symbol less legible than the digits already being read.
- Capture-time card registration — D1 keeps capture dumb; revisit at step 5 or Gate C.
- Any pokemontcg.io access — D15, build step 9, after Gate B.
- Interactive prompts of any kind — the pipeline must run unattended.
