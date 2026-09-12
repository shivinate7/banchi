## D180 — A press names the cards it is over, and the drawer is one of the names

**The box stops being the unit of work. `POST /pipeline/identify` and `pkmnscan identify` take ONE SELECTION — a set of terms, each of which narrows a set of cards — and the drawer is a term in it rather than the thing a run is made of.** Built 2026-09-12. **This OVERTAKES D48**, on the owner's word, and the rot in that entry is documented below rather than deleted.

### What stood, and the sentence it rested on

`server/pipeline_routes.py:_resolve_scope` refused any request that did not name a positive integer `box`:

> *"Send a positive integer `box`. A run is always scoped to one box."*

That is the thesis stated as a 400. `pkmnscan identify` took exactly one directory, `_scope_dir` symlinked a ticked selection into `.scopes/box3-<n>-<stamp>` so that a subset could be expressed as the one thing the command accepted — a path — and D48 made a SEND a cart of those, one detached child per drawer.

**So "identify everything that still needs it" was not a sentence this product could be asked**, and a pile spanning two drawers was two presses however few cards it held.

### D48's deciding sentence, and which part of it rotted

D48 did not rest on convenience. It was the owner's own correction of a worse proposal, and its deciding sentence is this:

> *"a run carries a **reading**, a `--bypass` ruling and a `decisions.json`, and all three are properties of what is IN the drawer — so one run across three boxes forces one answer to three questions that deserve three."*

That argument was right when it was written. **All three supports are gone, and two of them by other entries that did not look back at this one.**

- **`--bypass` was retired 2026-09-02** by D3's amendment. `pipeline/variant.py:357` is where the ladder decides now; 16 of 16 measured.
- **`decisions.json` moved store-wide 2026-09-02** by D86: the pricing answer is one file for the whole store, keyed by SKU. **0 live `decisions.json` files in `runs/`, 8 `.adopted` tombstones.** A run carries no pricing answer at all any more.
- **The per-run READING is alive as text and has never been exercised.** Measured across all 15 runs on the operator's store: **12 at `max_edge` 1200, 2 at 900, 1 at 1568** — and the three that differ are three separate presses on three different days, never two legs of one send.

**One of the three is therefore still true as code and false as an argument.** The reading IS per run; what it is not is a reason to carry a LIST on the wire, because nothing has ever sent two readings in one press.

### What D48 was protecting, and what protects it now

It was protecting **the operator's ability to give a bulk drawer and a collector drawer different readings** — D32's cost-against-sharpness frontier, decided per drawer. That is a real want and it is not dismissed here.

**It is protected by pressing twice.** One selection gets one reading; two readings is two presses, two runs, two receipts. What is given up is doing that in ONE press, which no press has ever done.

### D48 NAMED ITS OWN REOPENING CONDITION, AND THE MEASUREMENT DOES NOT MEET IT

> *"What would reopen this: a cart that is never used with more than one box... The measurement is whether any `POST /pipeline/identify` carries more than one scope."*

**It has been.** On **2026-09-01T21:50:52** the operator sent boxes **3, 4 and 5** in one press: three run directories created in the same second, all `started_by: app`. So the cart was used, once, and a selection that could name only one drawer would have taken a capability away.

**So `box` is list-valued, and that is this entry's answer to D48's condition rather than a dodge around it.** `{"box": [3, 4, 5]}` is one selection over 1,670 cards — verified by running it — and it produces **one run where that press produced three**, which is one join, one export fetch and one emit instead of three of each. A filter naming three values is still one filter.

**What the measurement does NOT support is the per-leg reading**: all three legs of that press carried `max_edge` 1200. The cart survives as a list-valued filter; the per-drawer reading does not.

### The terms are names the store already has for a group of cards

That is the whole design rule, and nothing here invents a grouping:

| term | what it is | who owns the vocabulary |
| --- | --- | --- |
| `paths` | the photographs under these directories | `identify/sidecar.py:scan`, unchanged |
| `state` | `captured`, `identified`, `sold`, `retired`, `moved` | `store/master.py:STATES` verbatim |
| `box` | the number on the shelf, one or several | `Card.box` — the SIDECAR's claim |
| `bid` | the drawer's true index | D145 |
| `section` | the dividers somebody put in one drawer | D10 |
| `game` | the per-card claim | D21 |
| `since` | captured at or after an instant | `Card.captured_at` |
| `keys` | `box/index` position keys | `Capture.key` — the cache's, the queues', the join's, D174's |
| `run` | the cards a run's own answers name | the run directory |

**Every term NARROWS and none widens**, so the order they are applied in cannot change the answer and there is no precedence to remember. It is also what makes the empty answer safe to refuse: nothing matched means these terms name no card, never that one term overrode another.

**`unjoined` was asked for and is not here, named rather than quietly dropped.** It is a property of a RUN — whether that run has been joined against an export — and not of a card, so it would be a sixth value beside five real ones with a different kind of answer behind it. Nothing would identify an unjoined card either: the join is the next step over an answer already bought. `--state identified` plus `--reidentify-stale` is the re-read.

**`sitting` was asked for and is `since` instead.** A sitting is a CLUSTER computed from `captured_at`, and that clustering lives in `app/src` for Home's library drawing (`storeHistory.ts`'s own `GAP_MINUTES`). A second clustering in Python would be a second answer to "which sitting is this". The screen spends a sitting as a `since` bound, which for "the pile I just shot" is exactly the same set of cards.

### `--box` is a FILTER, and the old `--box` is `--assume-box`

Two opposite jobs were wearing one name.

- **`--assume-box` FILLS a gap**: `sidecar.scan(box=...)` supplies a box for a photograph whose sidecar and filename carry none. It is the no-card-is-lost path for a pile somebody dropped on the desk. **It has fired on 0 of 2,535 captures** on the operator's store — measured 2026-09-12, every one resolved from a sidecar, none from a filename and none from nowhere — and it is kept for the pile the store has never seen, which is the one case nothing else can recover.
- **`--box` FILTERS** on what each capture recorded.

One name for both is how a press aimed at box 3 quietly relabels an unpositioned photograph as box 3. The fill keeps the verb; the filter keeps the noun.

### THE PATH IS A CONVENTION AND THE SIDECAR IS THE CLAIM, AND THIS STORE HAS THE RECEIPTS

`_run_box` parsed `^box(\d+)` off the capture directory's basename for any run whose manifest carried no scope. **It is confidently wrong on two of this store's fifteen runs:**

- **`2026-09-02-box6-01`** — 65 cards, keys `3/823`…`3/887`, **all in box 3 today**. The regex answers **6**. Box 6 has never existed on this store: `select count(*) from cards where box=6` is 0 and so is `boxes`.
- **`2026-08-29-box1-01`** — 99 cards, keys `3/724`…`3/822`, **all in box 3**. The regex answers **1**.

**The path arm is deleted and `_run_box` answers `None` where the manifest does not say.** `runScope.ts:boxOf`'s TypeScript copy of the same regex goes with it — a second implementation of exactly the thing being removed.

**What that costs is the drawer label on a pre-D145 terminal run that has never been re-joined: two on this store, and it was answering WRONGLY for both.** What it buys is that a run filed under the wrong drawer stops being undetectable, because a wrong box number RESOLVES and a null does not.

**It does not make those two runs right.** Their own `scope.box` says 1 and 6 as well — both voices agree and both are wrong. This stops the second voice agreeing with the first for a different bad reason; repairing the records is `pkmnscan rescue`'s job (D36), not this entry's.

**And `--box` is a filter over what each capture RECORDED precisely because of those two runs.** A photograph sitting in `box7/` whose sidecar says box 3 is found by `--box 3` and not by `--box 7`, which no narrower scan root can do.

### `.scopes/` is deleted, and the count is the finding

`_scope_dir`, `_scopes_root` and `_sweep_scopes` are gone, with the `.scopes/` root.

**Measured on the operator's checkout 2026-09-12: 264 directories, and 264 of 264 are named `box<n>-1-<stamp>`** — a selection of exactly ONE card. **Every one was built by the crop PREVIEW stepping a card at a time, and not one has ever been a submission.** 13 of 13 run manifests record `whole_box: True, cards: None`, so no ticked-selection run has ever been started on this store at all.

**A free read that had to write symlinks to disk and then be swept was the clearest evidence the directory was standing in for a vocabulary that did not exist.** The selection is a list of position keys on the wire; the preview writes nothing.

### D33 is KEPT, with one noun changed

One route spends, one `confirm`, one total, and that total is the server's. **`_total`'s `"boxes": len(answers)` becomes `"cards"`**, because D33's own rule is that the total is *"the number the operator agrees to spend"* and boxes are not what is being bought — a press over 2,535 cards in five drawers reported `5`, which is the least useful true number available about it.

`cards` counts the SELECTION; `to_send` beside it is what will be paid for, and the two differing is the cache doing its job. **Measured: a press over everything on this store is 2,535 cards and 0 to send**, because all 2,535 are cache hits.

### D39 is NARROWED, not repealed

Its re-consent rule stands: a tick list that survives a deliberate choice is a filter the operator did not re-consent to, sitting over the control that spends. Under the cart the rule scoped to the carried BOX — un-ticking it dropped the handoff, toggling any other left it alone. **A drawer is a term now rather than the unit, so the rule scopes to the START**: choosing any start other than the ticked cards drops them. Toggling a drawer while the drawers start is showing is not a deliberate choice away from the tick list — it is the operator building the selection they already chose.

`#/inventory` still owns the one mass-select and still hands it over through `runHandoff.ts`.

### D65/D76 hold, and the denominator changes

The export-scope argument is untouched and so is the unanimity rule — **a hint narrows only when every card of that game carries one and every hint resolves**. What changes is the denominator: it was the cards in the drawer and it is now the cards being joined. **D170 landed the same day and already guards the widening this would otherwise have worried about**: an unhinted Pokemon card refuses the fetch with the width on it, because that category is 903 KB from `MAX_BYTES`.

### `_busy_run` is deleted, and D174 said this would be a separate change

D174 wrote: *"`_busy_run` is left in place by this entry. Both checks now run in `do_pipeline_identify`. Deleting its callers is a separate change with its own reasoning, because a guard is removed only once its replacement has been exercised."* **This is that change and this is the reasoning.**

**It took a BOX NUMBER, and this route no longer has one to give it.** Widening it was never the fix — D174 says so in as many words — because the vocabulary was the problem.

**The narrowing, named: a press whose overlap with a live run is entirely CACHE HITS is no longer refused.** That press is spending nothing on those cards, which is D174's own rule for why an empty send list writes no row: *"It is spending nothing, so there is nothing to protect."*

**The widening is the half that costs money**: a live run over a pile spanning two drawers is invisible to a box compare in BOTH directions, and two disjoint selections in one drawer were refused for no reason at all.

`_claim_conflicts` is NOT deleted with it. It survives as `_claim_conflict` — the courtesy check at the press, over sidecars rather than digests (35 ms over 678), still the only thing that answers a double-click AT the press. `claim_or_refuse` is still the binding one.

### THE SPEND SETTING, ON THE OWNER'S RULING

Asked whether a store-wide press wants a standing spend ceiling, 2026-09-12:

> *"Give me settings if I can have them, but if I want to run everything, then I get to run everything."*

**So there is no cap on this route and there is not going to be one.** A ceiling that refuses "everything" is the wrong shape: it would be the server deciding how much of their own store the operator may read.

**What there is instead is a NOTICE, device-local, with a default, raisable at the confirm, and never a block.** `banchi.runs.spend-notice` in `app/src/deviceMemory.ts`. **Default $1.00**, derived: input is $0.50/MTok batch-discounted (`identify/cost.py`), a card at `max_edge` 1200 measures **2,641 input tokens**, so $1.00 is about **757 cards** — larger than every drawer on this store but box 3 (887), and roughly a quarter of a full store re-read (2,535 cards ≈ $3.35). An ordinary drawer press never trips it; a store-wide one always does.

**Device-local is argued rather than convenient.** D13 puts one truth on one Mac so two devices cannot disagree about where a card IS; a notice threshold is how loud a button is on THIS browser, which is the same side of that line as D114's order-status filter — a preference the owner ruled belongs there. Two devices disagreeing about it costs nothing.

**AND THE THING THE OWNER SHOULD KNOW, which is not a cap.** The per-drawer press was doing unstated work as a **sampling gate**: today you can identify one drawer, look at `#/review`, discover the model is misreading a set's number format, and stop. A store-wide default spends that lesson in one act. **The mitigation is the preflight's honesty rather than a ceiling** — it names the figure and the count in cards before anything is bought — and the honest note is that this trade is real and was made deliberately.

### What is proved, and what is not

**Proved.** `make harness` 9 of 9. The selection driven against the operator's real capture tree through a COPIED store (`--dry-run` only, never a paid call): `--box 3` narrows 2,535 to 887, `--game pokemon` to 543, `--state sold` to 294, `--box 3,4,5` to 1,670, `--box 3 --section 1` to 141. Every cross-term refusal fires.

**THE WORK IS COUNTED AND NOT ONLY THE OUTCOME**, which is the lesson the hash-first change paid for: deleting its own gate left every outcome assertion green, because hash-first and decode-everything agree on every ANSWER. So T7 asserts the legs that are **no longer spawned** (one child for a two-drawer press, where the cart spawned two — `Popen` monkeypatched, nothing submitted), the **preflight no longer shelled twice** (one `identify --dry-run` for two drawers, where the cart ran one per leg on a four-worker pool), and **nothing added to the home at all** by ten crop previews.

**NOT proved: no press has spent money through this.** The route that spends has never been exercised end to end here and cannot be — a test proving the happy path would submit a real Batch. Every measurement above is a dry run, a monkeypatched spawn, or a read of what is already on disk.

**NOT proved: the multi-drawer press has not been re-made.** The 2026-09-01 press is reconstructed as a selection and its card count verified (1,670); it has not been run for real as one run.

### What would reopen this

**A selection term nobody uses.** Each is a name the store already has, but that is an argument for coherence rather than evidence of use. The measurement is `selection` blocks in `runs/*/manifest.json`: a term that appears in none of them after a month of real presses is surface area with no reader, and D80's rule applies to it.

**A press that genuinely wants two readings.** If the operator asks for one drawer at 1200 and another at 900 in one act, D48's deciding sentence is live again for the one support that has not rotted, and the honest answer is a cart of readings — not a cart of boxes.
