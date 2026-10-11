## D180 — A press names the cards it covers

**The box stops being the unit of work. `POST /pipeline/identify` and `banchi identify` take ONE SELECTION, a set of terms, each of which narrows a set of cards.** The drawer is a term in the selection. It is not the thing a run is made of. This overtakes the cart design, on the owner's word. The cart design's rot is recorded below rather than deleted.

### What stood, and the sentence it rested on

`server/pipeline_routes.py:_resolve_scope` refused any request that did not name a positive integer `box`. The refusal said a run is always scoped to one box. `banchi identify` took exactly one directory. `_scope_dir` symlinked a ticked selection into `.scopes/box3-<n>-<stamp>`, so a subset could be expressed as the one thing the command accepted: a path. The cart design made a send a cart of those, one detached child per drawer.

So "identify everything that still needs it" was not a request this product could take. A pile spanning two drawers was two presses, however few cards it held.

### The cart design's supports, and which of them rotted

The cart design argued that a run carries a reading, a `--bypass` ruling and a `decisions.json`. All three are properties of the drawer. So one run across three boxes forces one answer to three questions that deserve three. That was right when it was written. All three supports are gone now. Two of them went by other entries that did not look back at this one.

- **`--bypass` was retired** by D3's amendment. `pipeline/variant.resolve` decides the ladder now. 16 of 16 measured.
- **`decisions.json` moved store-wide** by D86. The pricing answer is one file for the whole store, keyed by SKU. 0 live `decisions.json` files exist in `runs/`, and 8 `.adopted` tombstones. A run carries no pricing answer at all.
- **The per-run reading is alive as text and has never been exercised.** Across all 15 runs on the operator's store: 12 ran at `max_edge` 1200, 2 at 900, and 1 at 1568. The three that differ were three separate presses on three days, never two legs of one send.

The reading is still per run as code. It is not a reason to carry a list on the wire, because no press has ever sent two readings.

### What the cart protected, and what protects it now

The cart protected the operator's ability to give a bulk drawer and a collector drawer different readings. That is D32's cost-against-sharpness frontier, decided per drawer. That want is real and is not dismissed.

It is protected by pressing twice. One selection gets one reading. Two readings is two presses, two runs and two receipts. What is given up is doing that in one press, which no press has done.

### The cart design named its own reopening condition, and the measurement does not meet it

The cart design named its own reopening condition: a cart never used with more than one box. The measurement is whether any `POST /pipeline/identify` carries more than one scope. The condition is not met. The operator sent boxes 3, 4 and 5 in one press. Three run directories were created in the same second, all `started_by: app`. A selection that could name only one drawer would have taken that capability away.

So `box` is list-valued. That is this entry's answer to the condition. `{"box": [3, 4, 5]}` is one selection over 1,670 cards, verified by running it. It produces one run where that press produced three. One join, one export fetch and one emit replace three of each. A filter naming three values is still one filter.

The measurement does not support the per-leg reading. All three legs of that press carried `max_edge` 1200. The cart survives as a list-valued filter. The per-drawer reading does not.

### The terms are names the store already has for a group of cards

That is the whole design rule. Nothing here invents a grouping.

| term | what it is | who owns the vocabulary |
| --- | --- | --- |
| `paths` | the photographs under these directories | `identify/sidecar.py:scan`, unchanged |
| `state` | `captured`, `identified`, `sold`, `retired`, `moved` | `store/master.py:STATES` verbatim |
| `box` | the number on the shelf, one or several | `Card.box`, the SIDECAR's claim |
| `bid` | the drawer's true index | D145 |
| `section` | the dividers somebody put in one drawer | D10 |
| `game` | the per-card claim | D21 |
| `since` | captured at or after an instant | `Card.captured_at` |
| `keys` | `box/index` position keys | `Capture.key`, the cache's, the queues', the join's, D174's |
| `run` | the cards a run's own answers name | the run directory |

Every term narrows. None widens. So the order they apply in cannot change the answer, and there is no precedence to remember. This also makes an empty answer safe to refuse. Nothing matched means that the terms name no card. It never means one term overrode another.

`unjoined` was requested and is not here. It is a property of a run, whether that run was joined against an export, not of a card. It would be a sixth value beside five real ones, with a different kind of answer behind it. Nothing would identify an unjoined card either, because the join is the next step over an answer already bought. The re-read is `--state identified` plus `--reidentify-stale`.

`sitting` was requested and is `since` instead. A sitting is a cluster computed from `captured_at`. That clustering lives in `app/src` for Home's library drawing (`storeHistory.ts`'s own `GAP_MINUTES`). A second clustering in Python would be a second answer to "which sitting is this". The screen spends a sitting as a `since` bound. For "the pile I just shot", that is the same set of cards.

### A selection never widens a press

A selection refuses a null term, an unknown top-level key on a selection route, and an empty CLI selection flag. A run never widens to the whole store unless the operator asked for all. A null term, a misspelled key and an empty flag each read as "no term". A selection with no term would be every card in the store. The refusals keep a paid press on the cards the operator named.

- **How all is asked for.** The CLI spells it `--all`. `banchi identify` refuses a selection that names nothing without it. The route has no term for all. There, a selection that names nothing is the whole store, with the preflight and the confirm in front of it (`Selection.named`).
- **Where each refusal lives.** A null term: `pipeline/selection.parse`. An unknown top-level key: `server/pipeline_routes._resolve_send`. An empty flag: `cli/cmd_identify._selection_from`.

### `--box` is a filter, and the old `--box` is `--assume-box`

Two opposite jobs wore one name.

- **`--assume-box` fills a gap.** `sidecar.scan(box=...)` supplies a box for a photograph whose sidecar and filename carry none. It is the no-card-is-lost path for a pile somebody dropped on the desk. It has fired on 0 of 2,535 captures on the operator's store. Every capture resolved from a sidecar, none from a filename and none from nowhere. It is kept for the pile the store has never seen, the one case nothing else can recover.
- **`--box` filters** on what each capture recorded.

One name for both is how a press aimed at box 3 quietly relabels an unpositioned photograph as box 3. The fill keeps the verb. The filter keeps the noun.

### The path is a convention, and the sidecar is the claim

`_run_box` parsed `^box(\d+)` off the capture directory's basename for any run whose manifest carried no scope. It was confidently wrong on two of the store's fifteen runs:

- `2026-09-02-box6-01`: 65 cards, keys `3/823`…`3/887`, all in box 3 today. The regex answers 6. Box 6 has never existed on this store. `select count(*) from cards where box=6` is 0, and so is `boxes`.
- `2026-08-29-box1-01`: 99 cards, keys `3/724`…`3/822`, all in box 3. The regex answers 1.

The path arm is deleted. `_run_box` answers `None` where the manifest does not say. `runScope.ts:boxOf`, a TypeScript copy of the same regex, goes with it. It was a second implementation of the thing being removed.

The cost is the drawer label on a pre-D145 terminal run that was never re-joined. There are two on this store. The label answered wrongly for both. What it buys: a run filed under the wrong drawer stops being undetectable. A wrong box number resolves. A null does not.

This does not make those two runs right. Their own `scope.box` says 1 and 6 as well. Both voices agree, and both are wrong. Repairing the records is `banchi rescue`'s job (D36), not this entry's.

`--box` filters over what each capture recorded, for this reason. A photograph in `box7/` whose sidecar says box 3 is found by `--box 3` and not by `--box 7`. No narrower scan root can do that.

### `.scopes/` is deleted, and the count is the finding

`_scope_dir`, `_scopes_root` and `_sweep_scopes` are gone, with the `.scopes/` root. On the operator's checkout there were 264 directories. All 264 are named `box<n>-1-<stamp>`, one card each. Every one was built by the crop preview stepping a card at a time. None was ever a submission. 13 of 13 run manifests record `whole_box: True, cards: None`, so no ticked-selection run has ever started on this store.

A free read wrote symlinks to disk and then swept them. That was the clearest evidence that the directory stood in for a vocabulary that did not exist. The selection is a list of position keys on the wire. The preview writes nothing.

### D33 is kept, with one noun changed

One route spends, with one `confirm` and one total. The total is the server's. `_total`'s `"boxes": len(answers)` becomes `"cards"`. D33's rule is that the total is the number the operator agrees to spend. Boxes are not what is bought. A press over 2,535 cards in five drawers reported `5`, the least useful true number available about it.

`cards` counts the selection. `to_send` beside it is what will be paid for. The two differ because the cache does its job. A press over everything on this store is 2,535 cards and 0 to send, because all 2,535 are cache hits.

### D39 is narrowed, not repealed

Its re-consent rule stands. A tick list that survives a deliberate choice is a filter the operator did not re-consent to, sitting over the control that spends. Under the cart, the rule scoped to the carried box. Un-ticking it dropped the handoff. Toggling any other left it alone. A drawer is a term now, not the unit, so the rule scopes to the start. Choosing any start other than the ticked cards drops them. Toggling a drawer while the drawers start is showing is not a deliberate choice away from the tick list. It is the operator building the selection they already chose.

`#/inventory` still owns the one mass-select and still hands it over through `runHandoff.ts`.

### D65 and D76 hold, and the denominator changes

The export-scope argument is untouched, and so is the unanimity rule. A hint narrows only when every card of that game carries one and every hint resolves. The denominator changes. It was the cards in the drawer. It is now the cards being joined. D170 already guards the widening this would otherwise have worried about. An unhinted Pokemon card refuses the fetch with the width on it, because that category is 903 KB from `MAX_BYTES`.

### `_busy_run` is deleted

`_busy_run` is left in place by this entry. Both checks now run in `do_pipeline_identify`. D174 said deleting `_busy_run`'s callers would be a separate change, because a guard is removed only once its replacement has been exercised. This is that change.

`_busy_run` took a box number, and this route no longer has one to give it. Widening it was never the fix. D174 says so, and the vocabulary was the problem.

The narrowing: a press whose overlap with a live run is entirely cache hits is no longer refused. That press spends nothing on those cards. D174's rule for an empty send list is the reason. It spends nothing, so there is nothing to protect.

The widening is the half that costs money. A live run over a pile spanning two drawers is invisible to a box compare in both directions. Two disjoint selections in one drawer were refused for no reason at all.

`_claim_conflicts` is not deleted with it. It survives as `_claim_conflict`. That is the courtesy check at the press, over sidecars rather than digests (35 ms over 678). It is still the only thing that answers a double-click at the press. `claim_or_refuse` is still the binding one.

### No spend setting, by the owner's ruling

The owner ruled that there is no standing spend ceiling. A press runs everything it selects. So this route has no cap, and it will not get one. A ceiling that refuses "everything" would have the server decide how much of their own store the operator may read.

There is no threshold notice either. The paid read (Haiku 5.5) costs about a tenth of what it did, so a warning above a dollar protected nothing. The confirm that names the cards and the spend is the whole of it. The device key `banchi.runs.spend-notice` is deleted.

The owner should know this, though it is not a cap. The per-drawer press did unstated work as a **sampling gate**. An operator could identify one drawer, look at `#/review`, find the model misreading a set's number format, and stop. A store-wide default removes that gate. **The mitigation is the preflight's honesty, not a ceiling.** It names the figure and the count in cards before anything is bought. The trade is real, and it was made on purpose.

### What is proved, and what is not

**Proved.** `make harness` passes 9 of 9. The selection ran against the operator's real capture tree through a copied store, with `--dry-run` only and no paid call. Results: `--box 3` narrows 2,535 to 887. `--game pokemon` narrows to 543. `--state sold` narrows to 294. `--box 3,4,5` narrows to 1,670. `--box 3 --section 1` narrows to 141. Every cross-term refusal fires.

The work is counted, not only the outcome. Deleting the hash-first gate left every outcome assertion green, because hash-first and decode-everything agree on every answer. So T7 asserts the legs that are no longer spawned. A two-drawer press spawns one child, where the cart spawned two. `Popen` is monkeypatched, and nothing is submitted. T7 also asserts the preflight is no longer shelled twice. One `identify --dry-run` runs for two drawers, where the cart ran one per leg on a four-worker pool. Ten crop previews add nothing to the home.

**Not proved: no press has spent money through this.** The route that spends has never been exercised end to end here, and it cannot be. A test of the happy path would submit a real Batch. Every measurement above is a dry run, a monkeypatched spawn or a read of what is on disk.

**Not proved: the multi-drawer press has not been re-made.** The press of boxes 3, 4 and 5 is reconstructed as a selection, and its card count verified (1,670). It has not been run for real as one run.

### What would reopen this

**A selection term nobody uses.** Each term names something the store already has. That argues for coherence, not for use. The measurement is `selection` blocks in `runs/*/manifest.json`. A term that appears in none of them after a month of real presses is surface area with no reader. D80's rule applies to it.

**A press that wants two readings.** If the operator asks for one drawer at 1200 and another at 900 in one act, the cart design's deciding argument is live again. It is live for the one support that has not rotted: a run carries a **reading**, a `--bypass` ruling and a `decisions.json`, and all three are properties of what is IN the drawer — so one run across three boxes forces one answer to three questions that deserve three. The honest answer is a cart of readings, not a cart of boxes.
