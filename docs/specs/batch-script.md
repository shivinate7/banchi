# Batch script v2 — spec

## STATUS — BUILT 2026-08-03, and run against real cards since

**Step 4 is done and this file describes live code.** `./pkmnscan identify | join | emit |
reconcile` exists, and it is no longer a spec waiting on anything: Gate B put 53 real cards
through all four commands on 2026-08-22 and reconciled back with zero unmatched in either
direction, and box 2 followed with 544. `docs/GATES.md`'s build-order step 4 carries the run
record and the four defects those cards found that no fixture could.

**The document amendments this file was gated on were all applied on 2026-08-03**, and that
section is marked as a record rather than an open gate. The gating sentence below is left
standing as the original terms.

**This is the doc `make docs-audit` couples to `pipeline/`, `identify/`, `geometry/`,
`store/` and `cli/`** — twenty staged lines under any of them without this file asks the
coupling question. It is the most-read spec in the repo for that reason.

---

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
pkmnscan reconcile  --live <my-pricing.csv>        the WHOLE store, both directions (D87).
                      Previews; --write settles `live`. Reachable on #/runs.
```

Each is independently resumable and re-runnable. `join` and `emit` cost nothing, so
re-running them after fixing a review or changing a price is free.

---

## 3. Storage

One master store sits atop the runs and is fed by them. Runs are immutable inputs;
deleting one must never cost money or state.

```
inventory/
  store.sqlite          MASTER, since D88 (2026-09-01). One SQLite file: cards, boxes,
                        listings, the identification cache, both standing queues, the
                        order ledger and the history — one table each, one transaction
                        per write. store.sqlite-wal and -shm beside it are the database.
  legacy-json/          the six JSON files this store was migrated FROM, moved aside whole
                        on the first open and read by nothing. MIGRATED.json says what was
                        imported and how to reverse it.
  prices.json           the pricing corpus (D86). Still a file.
  codes.jsonl           the code ledger (C8). Still a file.
  .lock                 Exclusive lock file — the writer's lock.

runs/<YYYY-MM-DD>-<label>-<nn>/
  manifest.json         Inputs: capture dir, export path + mtime + sha256, prompt
                        fingerprint, flags, batch ids, cost. The last of those was
                        a claim this line and cli/runs.py's header both made from
                        the day they were written and neither kept: `usage` held
                        the TOKEN counts and nothing priced them, so `#/runs` drew
                        `290,470 tokens in` and no figure. Since 2026-09-11 the
                        collect writes `usage.cost_usd` from identify/cost.py, at
                        the rates in force the day it ran.
  identifications.json  What this run read, before caching.
  decisions.json.adopted  A pre-D86 answer file, folded by `prices adopt` and retired.
                        Nothing reads it; the live answers are `inventory/prices.json`.
  report.txt            The join report, both directions, verbatim.
  import.csv            THE import file — one press, one spreadsheet (D99). Across
                        games and across the listed/sub-threshold split.
  import-listed.csv      Above-threshold import file. `--split-threshold` only.
  import-subthreshold.csv Sub-threshold import file. `--split-threshold` only.
  import-<game>.csv     `--split-games` only.
  reconcile.txt         Written by reconcile.
```

**Write discipline.** Every `Store.write()` is one SQLite transaction over every table,
opened inside an exclusive lock on `.lock` and committed whole on a clean exit or not at
all (D88). The lock is still needed, because atomicity prevents torn writes but not lost
updates: two writers each reading, each modifying, each writing back means the second
silently erases the first, so the session reads inside the lock. The capture server (step
5) uses the same lock and the same transaction; it is a second writer, not a second owner.

**This section said the opposite until 2026-09-01.** It read: *"`inventory.json` is
rewritten whole: to a temp file in the same directory, then `os.replace()` into position"*,
and, under a bold **Not SQLite**, that *"D13 settles inventory as server-side JSON ... A
later session that 'upgrades' inventory to SQLite is re-litigating D13."* D88 re-litigated
it in the open. The per-file atomic replace was real and the SET of five files was never one
transaction — a kill between two writes left the inventory and a queue disagreeing — and
every capture re-read and rewrote every card in the store, which crossed the feeder's own
cadence at ~48,000 cards. D13's sentence — one truth, server-side, on the Mac, read and
written through the capture server — is unchanged; the file format behind it moved.

The history is the `events` table and is still append-only and still the audit trail —
when a card was captured, identified, pushed, staged, live, sold. D10 makes this worth
keeping: positions are never renumbered and sold cards leave permanent gaps, so the history
*is* inventory truth over time. Since D88 the rows describing a change commit in the same
transaction as the change, where `history.jsonl` was appended afterwards.

---

## 4. `identify`

### 4.1 Preflight

Always printed before anything is submitted: card count, total payload bytes, batch chunk
count, estimated cost, prompt fingerprint, cache hits vs sends. `--dry-run` does everything
except the API call — so sidecar problems, unreadable images, and a mistyped directory
surface for free.

### 4.1a The claim — the last free act before the money

**Between the preflight and the first submitted byte, the press claims the cards it is about
to buy** (D174). One row in the store's `submissions` table, holding the
position keys of the send list — not the selection — so a second press over any of those
cards is refused on intersection, naming the receipt and the overlapping cards.

The claim is written inside the same `Store.write()` that **recomputes** the send list from
the cache, because the list §4.1 printed was decided before the prepare pass and two presses
can both finish deciding before either has claimed. `--dry-run` claims nothing: it returns
before this point, as it does before `runs.create`.

**The claim is released by the same commit that banks the answers it paid for** — §4.6's cache
writes — or by neither. A run that dies in between keeps its claim, deliberately: the batch is
paid for and its results keep for 29 days, so the cards stay held until somebody looks. The way
out is the release control on `#/runs`, and `--run-dir` re-entering a run releases that run's
own claim as it resumes.

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

**Which is why the press hashes before it decodes** (D163, 2026-09-12). The
reuse test above needs the sha256 of the bytes on disk and nothing else, so `identify` hashes
every photograph, asks the store what it already owns, refuses what has no prompt, and only
then crops and downscales what is actually being sent. Until that reorder it prepared the
whole directory first and consulted the cache afterwards — measured on box 4's own 678 JPEGs
at `--crop --max-edge 1200`: **0.687 ms to hash against 114.96 ms to crop and prepare**, so
the decode was 167x the cost of the question it was not an input to. One dry-run leg of that
directory went from 79 s to 24 s and submitted the same 214 cards.

**`Item.stage` is what keeps §4.1's roster honest across it.** `prepared is None` used to
mean both *unreadable* and *nothing to send*, which were the same set while everything was
prepared; a cache hit is unprepared now too, so the four figures the preflight prints —
cache hits, to send, unreadable, refused — read a named stage rather than the absence of
bytes. The run payload's `photo_sha256` reads it too, because `cli/resolve.py` treats a
record without a digest as one D36's realign cannot re-bind.

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

Catalog is built from the TCGplayer Filtered CSV export. Nothing else.

**AND IT IS NARROWED TO THE CONDITIONS THIS PRODUCT LISTS (D137, 2026-09-11)** — the game's
own `condition_by_finish` values plus `Unopened`, so sealed product survives and every play
grade goes. `Catalog.from_export` had never cut on `Condition` at all, which was invisible
while the export was downloaded by hand with the portal's Near Mint filter checked and cost
D3 rung 2 outright once the fetch started sending all eleven: 0 of 1,246 numbers held a
single row, against 629 once the grades are gone. A play grade is not a finish — no number
loses one.

**THE JOIN KEY IS PER GAME, AND THIS SECTION DESCRIBED ONLY POKEMON'S UNTIL 2026-08-29.**
It read *"Join key stays `zfill(3)(number) + "/" + printedTotal`"* full stop, which was true
the day it was written and was overtaken by D25 in August when the join learned to partition
by `Product Line`. Corrected rather than deleted, because the Pokemon key is unchanged and
`161/159` is still a secret rare rather than an error.

`pipeline/games.py` names each game's strategy and `pipeline/join.py:JOIN_KEY_STRATEGIES`
implements it:

| strategy | games | key |
|---|---|---|
| `number_and_printed_total` | `pokemon` | `zfill(3)(number) + "/" + printedTotal` |
| `printed_code` | `riftbound`, `one_piece` | the printed identifier, verbatim |
| `name_only` | `pokemon_code` | no key — the blank-`Number` rows, by name |
| `not_joined` | `misc` | never joined at all |

**ONLY THAT KEY IS PER GAME.** `pipeline/join.py:_walk` is one ladder for every game — build
the key, look it up, repair it once where the game declares a repair, try the blank-`Number`
name, then D35's name rung — and `KeyStrategy`
is the per-game part as a value. It is written that way because the alternative was measured
and failed: three parallel `_lookup_*` functions each re-implemented the ladder, D35's rung
landed in the Pokemon copy alone, and `riftbound` returned zero candidates for a year's worth
of cards whose rows were in the export the whole time. A rung added to `_walk` cannot now land
in one game and not another.

**Both sides of a comparison go through one fold**, never two spellings of one rule:
`number_index_key` for the number, `name_index_key` for the name. `_repair_set_code` is the
ladder's second rung for the printed-code games and removes a set code the model glued onto the
front of the identifier against its own prompt — matched by SHAPE (two to five letters, no
digits, then one separator) rather than by naming the separator, because the separator turned
out to be arbitrary: one 39-card box produced three of them and read one card both ways. D55
carries the measurement that licenses it, and the reason it runs only after the key has missed.

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

**Rung 3 no longer contradicts a finish claim, and the flag that used to switch that off is
gone** (`--bypass`, added 2026-08-24; retired 2026-09-02, D3 amended). For nine days
`resolve` took `trust_claim` and, where a finish claim existed, let detection choose inside it
but not against it. Every run since Gate B was joined with the flag on — 256 cards, 16 of 16
rulings to the claim, box 2's 230 disagreements all wrong — and a switch every run flips is a
default wearing a flag. So the rule is the ladder's now: a detection outside the claimed set is
dropped, `metadata_detection_disagreement` is retired, and `Resolution.bypassed` and the
manifest's `bypass_detection`/`bypassed` keys went with it — old manifests keep them, unread.
Nothing else moves: a card with no claim walks the identical ladder, and `metadata_not_stocked`
and `no_catalog_row` still refuse.

**`--dry-run` previews the join and writes nothing.** It walks the ladder once, counts what
would queue by reason code, and returns before the first write: no queues, no
`inventory/prices.json` change, no `report.txt`, no manifest. A preview built from a different source than
the write is a preview that can be wrong in the one way that matters, so the counts come off
`entries_for` — the same function the write uses.

**Raw reason codes, no gloss table.** `app/src/reasons.ts` holds the only label map in the
product; a second table in the CLI would be a third vocabulary with even less holding it
together (D16). The plain English the operator needs is about the rule, not about each code,
and it is one sentence printed once.

**Two corrections, 2026-09-05.** The map used to live in `app/src/ReviewQueue.tsx` and this
paragraph still named that file. And it said *nothing keeps it in step with the Python
constants* — two rows do now. `reason codes` reconciles the labels against the constants and
`docs/DESIGN.md`; `reason emissions` reconciles them against the rosters the pipeline
publishes (`variant.LADDER_REASONS`, `routing.ROUTING_REASONS`) and fails on a declared reason
with no producer. The argument for one table is unchanged — it was never the drift that made a
second table wrong — but the drift itself is no longer unwatched.

### 5.4 Routing — which queue a card lands in

Confidence describes how legible the title and collector number were. It is the **only**
signal that a card was guessed at: a misread `026/198` as `025/198` is still a valid number
that joins to a real row, so nothing downstream can catch it.

| Condition | Destination |
|---|---|
| Resolved cleanly, confidence `medium`/`high` | Listed — **unless the row was reached by NAME**, one row down. |
| Row found by NAME because the number could not be read (D35) | **Main queue if that row is ≥ $0.40, parked if below. Never listed on the name alone**, however cleanly the ladder resolved or however confident the read. `join_batch` rewrites the resolution to `REVIEW` before routing, keeping the chosen row — so the entry carries one candidate under one shared reason, which is D29's group-answer eligibility. Rung 0 is exempt: a card a human has already answered is listed on that answer. |
| Confidence `low`, resolved market **≥ $0.40** | **Main review queue.** Not listed until looked at. A wrong listing on a $12 card ships the wrong card to a buyer; that is worse than a tap. |
| Confidence `low`, resolved market **< $0.40** | **Parked** in the low-value queue. Not listed, not dropped, never in the main queue. |
| Ladder → review (D3 reasons) | Main queue if the cheapest candidate row is ≥ $0.40, parked if below. |
| No catalog row, or identification failed | **Main queue, sorted last.** No price is not a low price — a misread secret rare is exactly this case. |
| Matched row with blank or $0.00 market price | **`no_market_data` category. Never auto-priced, never swept into the sub-threshold flat price.** A missing price is an unknown price; handing away a $40 chase card at the floor is the failure this prevents. |

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
never sneak a price under it. Floor and threshold are both `$0.40` by default, and **they are
one figure rather than two defaults that happen to agree** (D9, amended 2026-09-09): the
operator's `policy.threshold` in `inventory/prices.json` is what earns a listing, what the
cheap half goes out at, and what nothing may be priced below. `SkuMatch.list_price` clamps at
`SkuMatch.threshold`; `pipeline/pricing.py:THRESHOLD` and `:FLOOR` are what a store that has
never set one reads.

This paragraph said *"the floor is still the constant; nobody has asked for that one"* until
the ask arrived as a defect. On the owner's real store the cut-off was `$0.29` and every clamp
read `$0.40`, so `reprice apply` refused **293 of 354** hand-priced rows as `below_floor`
against a figure the store had not used for a week, and the join priced a card the same
cut-off calls listable ABOVE its own market — market `$0.32`, `match`, clamped to `$0.40`.
There is deliberately no `policy.floor`: a floor above the cut-off produces that inversion and
one below it undercuts the price the cheap half is already going out at, so a second key could
only ever be set wrong.

### 6.3 Sub-threshold disposition — `inventory/prices.json` `policy.sub_threshold`, default flat $0.49 (D86; D9 amended 2026-09-02)

D9 forbids the script from guessing what happens to a sub-threshold card. The decision is
**a document, not a flag**, so `#/pricing` is an editor for an existing contract rather than
a second code path.

The answer is the store's standing policy and not a run's (D86): `pipeline/corpus.py` reads
`policy.sub_threshold` out of `inventory/prices.json` and projects it into every run's
`Decisions`. Where the key is absent or null the corpus applies the default, **flat $0.49**
(`DEFAULT_SUB_THRESHOLD`), on read, and writes it on the next save — so a fresh store's first
`emit` is not refused for want of an answer the owner has already given once. `"floor"` and a
written flat price say what they say. The press that changes it is on `#/pricing`, and `join`
names the standing disposition on its own `sub-threshold` line every time it runs. What `emit`
still refuses on is an unanswered `no_market_data` card, and that rule is unchanged.

```jsonc
{
  "version": 1,
  "policy": {
    "rule": "match",                    // match | undercut:PCT | markup:PCT
    "basis": "market",                  // market | low
    "sub_threshold": {"flat": "0.49"}   // "floor" | {"flat": "0.25"} — the default when silent
  },
  "skus": {                             // one answer per SKU, for the whole store (D86)
    "8823901": {"value": "0.35"},       // a price, above or below the threshold
    "8823944": {"value": null, "channel": "unknown"}   // no market price: a price, or "unlisted"
  }
}
```

---

## 7. `emit`

Writes **one** import file, `import.csv`, carrying every row it has — above the D9
cut-off and below it, and across every game in the send. The owner's instruction, 2026-09-03:
*"emit by default only should now emit only one spreadsheet by default (with the ability to
split if needed)"*. See D99.

Two flags split it, on two different axes, and neither is the default:

- `--split-threshold` — the old pair back: `import-listed.csv` above the cut-off,
  `import-subthreshold.csv` below it, one pair per game. It exists because the split was
  never cosmetic: the valuable cards can be staged and moved live while the bulk file
  waits, and a pricing mistake on the cheap file cannot touch the valuable one.
- `--split-games` — one file per game, if Import to Staged refuses a file spanning two
  `Product Line`s. Still unestablished; `fixtures/staged-import-accepted.csv` proves the
  format for one line only, and a merged file whose games carry different export headers is
  refused rather than written.

`--listed-only` is a third thing and is not a split: it drops the sub-threshold rows rather
than filing them elsewhere, and says how many it left for a later press.

Every file independently obeys the no-duplicate-SKU rule, and merging cannot break it: the
two buckets are disjoint SKU sets of one report, so one `import_rows` call over their union
prices and writes each SKU once. The live cap is spent ONCE across everything one press
writes — `add_to_quantity` is per SKU inside a run, and `pipeline/merge.py` re-derives it
over the union of positions across runs.

**A card's quantity can be named per send** (D7, amended 2026-09-11): `--quantity SKU=N`,
repeatable, puts exactly N copies of that card in the file this press — a send quantity,
bounded by the copies on hand that are not already listed and never by what TCGplayer holds,
which is what distinguishes it from `--cap`. `0` sends none of the card without holding it.
The report names every card given a figure, says *asked 9, only 3 can go* where the shelf is
short, and names back a SKU the send does not hold. A merged send spends the figure once across
the union. Nothing is recorded: the figure is the press's, and `#/pricing`'s Qty field clears
on a successful write.

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

On success `emit` makes **two writes per SKU, and they are about different things** — one
about the cards, one about the listing.

**The cards get their identity**: `sku`, `condition` and the run that decided them, written
to every copy the run matched, with the transition appended to `history.jsonl`. **Every copy,
not the listable subset** — the identity write runs over `uncommitted_positions`, so a card
held past D7's live cap is still findable by `GET /search`, `copies_on_hand` and
`positions_for_sku` (D7 amended; the cap bounds the listing, never the record). It runs over
`uncommitted_positions` and **not** `positions`, because every terminal copy of a matched SKU
is committed and `set_state` has no terminal guard — iterating those would move a sold card
back to `identified`.

**The listing gets the count**: `pushed`, bumped by the copies that actually reached an import
file, which is `live_positions` and nothing wider. `pushed` has not been a card state since
D7's amendment moved the three listing stages off the card and onto the SKU's `Listing` as
counts; the card stays at `identified`, and passing `pushed` to `set_state` now raises
`UnknownState`. This paragraph said "every emitted SKU's copies transition to `pushed`", which
named a state that no longer exists and a set that was never right.

---

## 8. `reconcile` and listing states

Writing a CSV proves only that a CSV was written. Three states, each confirmed by something
outside this script:

| State | Confirmed by |
|---|---|
| `pushed` | `emit` wrote the row into an import file. |
| `staged` | **Export From Staged** download, diffed by `reconcile`. |
| `live` | Quantity against that SKU in a later Filtered Export (`Total Quantity`). |

**`reconcile --live` IS THE SECOND FORM AND IT IS NOT RUN-SCOPED (D87).** One full My Pricing
export against every SKU in the store, whatever run or box it came from. It reports **both
directions** — copies this pipeline sent that TCGplayer no longer holds, and SKUs it holds that
were never sent from here — and the second half is the one a per-run reconcile cannot have,
because a run only knows what it sent.

**What it writes is `live`, and only `live`.** `pushed` is the cumulative record of what was
sent and `_copies_out` already corrects a stuck one against the physical ceiling (below);
rewriting it would destroy the only cumulative record there is, since an import file holds the
last delta only (D54). Measured on the owner's store the first time it ran: **405 of 443 SKUs
read `live: 0` while carrying pushed copies**, so this table's third row was a state nothing
had ever written. The cap arithmetic went from seeing 93 live copies to 1,079.

Collapsing `staged` and `live` would make D7's refill math wrong — `Add to Quantity =
min(cap - live, backstock)` reads the *live* number, and an import staged but never moved
live has no live quantity.

**THAT PARAGRAPH IS THE DIRECT COUNTER-ARGUMENT TO D59, AND D59 ANSWERS IT RATHER THAN
REPEALING IT** (2026-08-30). The two are easy to mistake for each other, so the answer is
put here in one place: **`min(cap - live, backstock)` is what this pipeline computes again
as of D59, and it is not what it computed before.** `SkuMatch.add_to_quantity` read
`cap - live - len(committed_positions)` — a count of the positions in front of THIS RUN,
standing where a per-SKU quantity belongs. **The sentence above was right and the pipeline
was not obeying it**, and it had stopped obeying it without anyone collapsing a state: a SKU
split across two boxes had the cap enforced once per box, a SOLD copy shrank what its SKU
could ever list, and `pushed` was subtracted a second time the moment the import landed.
D7's arithmetic is the thing D59 restored, not the thing it argues with.

**Nothing in this section moves.** Three states, not two; `reconcile` still moves
`pushed → staged` off the Export From Staged; `cli/cmd_join.py` still draws `staged` down
by the **rise** in live quantity a fresh Filtered Export reports; and `live` is still read
from `Total Quantity` and from nowhere else. An import staged but never moved live still
has no live quantity, which is still the reason the two states are not one.

**WHAT IS NEW IS A CEILING OVER `pushed`, AND `pushed` IS THE ONE ROW THIS TABLE'S OWN LEAD
SENTENCE DOES NOT COVER.** "Each confirmed by something outside this script" is true of
`staged` and of `live`, and false of the row above them: `emit` writes `pushed` and
`reconcile` is the only thing that clears it, so an operator who never downloads an Export
From Staged never clears it at all. The claim then stands forever over an import that went
live months ago. Measured on the owner's store when this was found: **167 copies across 72
SKUs at `pushed`, with `staged` and `live` both zero.**

`cli/resolve.py:_copies_out` answers, per SKU:

    min(live + pushed + staged, max(live, copies not sold))

- **The NEWER reading of `live` is a FLOOR and cannot be argued below.** D8 and D11 put
  the authority in `Total Quantity` for the moment the file was read, so the store may
  never talk the live quantity down on an older reading — and, since 2026-09-02 (D87
  amended), an older export may not talk it down either: `Listing.live_reading` picks
  whichever of the store's `live_as_of` and the file's mtime is later, which is what makes
  a stale export harmless here in both directions.
- **The physical count is a CEILING, and it is the only thing that can correct a claim
  with no drawdown.** TCGplayer cannot be holding more copies of a SKU than this Mac owns
  and has not sold. No write, no second CSV, and no inference about whether an import
  landed — `store/master.py:Inventory.copies_not_sold` is a fact about cardboard.
- **A RETIRED copy still counts as sent** (D26). It left this box; TCGplayer was never told,
  so its row is still out there and freeing a slot under the cap for it would be wrong.

**It is not a reason to collapse `staged` into `live`, and the distinction is exactly the
one the paragraph above draws.** The ceiling bounds what this pipeline may CLAIM is out
there. It says nothing about which stage a given copy is at, and it could not — that is
the question only an Export From Staged answers. Two different questions, and only one of
them has an answer that can be inferred locally.

`reconcile <run-dir> <staged-export.csv>` uses the existing `join.reconcile_import` and
reports both directions: rows TCGplayer has that the run did not send, and rows the run sent
that did not land. This is the machine-checkable round trip against the real system that
GATES.md calls the highest-value finding from Gate A.

`live` is refreshed whenever `join` loads a fresh export — the `Total Quantity` column is
already read for refill math (`SkuMatch.live_before`), so this costs nothing new — and only
where the export is the NEWER reading: one older than the store's own `live_as_of` is kept
out, and the join report names each SKU it kept (D87 amended).

Cards sitting in `staged` for more than **14 days** (configurable) are named in the run
report — catching an import that was staged and never moved live.

---

## 9. Configuration

| Knob | Default | Where |
|---|---|---|
| `--max-edge` | 1568 | image downscale, longest edge |
| `--retry-budget` | 1 | per-card retries after a batch failure |
| `--review-below-confidence` | `low` | `none` \| `low` \| `medium` |
| `--dry-run` (join) | off | preview both queues, write nothing |
| `--basis` | `market` | `market` \| `low` |
| `--rule` | `match` | `inventory/prices.json` `policy.rule`, seeded by the flag on the first join of an empty corpus (D86) |
| threshold / floor | `$0.40` / `$0.40` | D9, `pipeline/pricing.py`. ONE FIGURE, not two (D9 amended 2026-09-09): both are the default for a store that has never set `policy.threshold` (D99), and both follow it when it is set |
| `--cap N` (emit) | *none* | D7 rewritten 2026-09-07: no standing cap; a CEILING on copies live per SKU, asked for per send. `join.LIVE_QUANTITY_CAP` (4) is only the figure a press may offer |
| `--quantity SKU=N` (emit) | *none* | D7 amended 2026-09-11: a SEND QUANTITY per card, this press only — bounded by the copies on hand not already listed, never by what TCGplayer holds; `0` sends none. Composes with `--cap` to the tighter |
| cards per section | *no default* | D10 — dividers are declared, never assumed |
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

**Two things about the finish changed under this spec on 2026-08-23, and both are in
`pipeline/variant.py` rather than here.**

**The ladder's finish vocabulary is per game.** It read `variant.FINISHES` — Pokémon's
three — for every game, and RAISED `UnknownFinish` rather than reviewing, so a Riftbound
`foil` would have ended a join with a stack trace. `variant.resolve` now takes a `game` and
reads that game's entry out of `pipeline/games.py` through `variant.vocabulary`;
`cli/resolve.py`'s whitelist for the model's detected finish was the same defect one seam
along and moved with it, and so was `identify/sidecar.py`'s reader — which was the worst of
the three, because it neither raised nor refused: it DROPPED a Riftbound `foil` claim and
reported it as outside an enum the file had never named. It was also read three lines above
the game key, while the rarity claim directly beneath it carries a comment saying that order
is load-bearing. `--variant`'s own `choices` are still Pokémon's, which is a smaller
version of the same thing and is recorded rather than fixed: the flag fills gaps in a
sidecar-less directory, and no such directory exists for any other game yet.

**The pixel budget can be spent on the card rather than the desk** — `--crop`, D32. Off by
default. It crops to `geometry.detect_card`'s box before the downscale, correcting the box
toward a real card's 63/88 proportions first, because the detector's boxes come back
systematically short for their width and a flat margin cannot fix a proportional error. A
frame where detection refuses is sent whole and the preflight names the count.

**And so is a frame where detection ANSWERED and the box was not the card** — D75. The
detector has no way to say "found the wrong thing", and over the owner's 867 real
photographs it returned a box for every one and refused none while nine of them were a
card-shaped rectangle inside the card. `identify/images.py:crop_refusal` declines a crop
under 30% of the frame that keeps under half the frame's detail, `prepare` sends the whole
frame instead, and the preflight names that count SEPARATELY from the detection refusals
above and prints the reason per card. The same guard stands in front of the crop retry in
§4.5, where the bands would otherwise be cut out of the wrong rectangle and sent as evidence.

**And §4.5's bands are now cut from a card-shaped rectangle**, which they were not until
2026-08-31 — D75's amendment. `card_rect`'s aspect correction reached the primary image and
not `geometry/crop.py:registered_card`, so every band was a fraction of a box measured at a
median aspect of 0.789 against a real card's 0.716. It moved down into
`geometry.corrected_bounds` so both paths share one computation.

**D3 rung 1's claim is a SET.** One member determines exactly as this table's behavior
always described; two or more filter the candidate rows and let rungs 2 and 3 choose within
what survives. `--variant` is unchanged by that — it still fills a gap and still never
overrides — but it fills it with a one-member claim, which is what every record written
before the amendment reads as.

---

## 10. Failure modes

| Failure | Behavior |
|---|---|
| Script dies mid-poll | Batch ids persisted before first poll; re-run reattaches and collects. |
| Batch expires (24h API cap) | Reported per card; retried within budget; then main queue. |
| Photo has no sidecar and no recoverable position | Identified, main queue, `no_position`. |
| Card boundary not detectable | No crop retry; main queue; named in report. |
| Card located, box is not the card | Crop refused with its reason; whole frame sent; no crop retry; named in report as `unfit crop` (D75). |
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
