## D-run-binds-to-bid — A run is bound to the drawer's true index, and the run the number stranded is repaired once by hand

**Settled 2026-09-12, on the owner's ruling, which rejected the two options put to them.** A run records the `bid` of the box it was over, from every path that starts one; `cli/resolve.py:refuse_reallocated` compares ids rather than inferring from timestamps; and the 99 cards one legacy run had stranded are recovered by `pkmnscan rescue`, a preview-first repair that derives a second run from the first and never edits it.

### The report, and the ruling

**The owner, verbatim:** *"It's basically just wrong that their run is named after box 1 that was then deleted and reused, like the PROBLEM IS UPSTREAM -- one time save these and NEVER LET THIS HAPPEN AGAIN BASICALLY there shouldn't have been this mistaken path !!!"*

**And their summary of the class:** *"Boxes were just over used / referenced too much of a crutch."*

The question put to them was whether D36's refusal should be per-card rather than per-run. **Both options treated the refusal as the thing to tune, and both were wrong**: the refusal is correct and stays. The upstream fault is that a run is bound to a box NUMBER and box numbers are reallocated, so a label that moved made a run undecidable about cards that had not moved at all.

### What was measured, read-only, on the owner's live store

The emit preflight warned *"2 runs not joined · 2 runs over a deleted box"*. Decoded:

| Run | What the warning said | Cards it read | On hand today |
|---|---|---|---|
| `2026-09-11-box4-01`, `-02` | not joined | no manifest counts at all | **0** — empty husks |
| `2026-08-22-box1-03` | over a deleted box | 53 | **0** — they went with box 1 on 2026-08-25 |
| `2026-08-29-box1-01` | over a deleted box | 133 | **99**, all `identified`, all carrying a SKU |

**Three of those four rows are a false alarm and the fourth is not, and the sentence could not tell them apart.**

**The 99 are not in a deleted drawer.** On 2026-09-11 the operator MOVED them out of box 1 into box 3 (D83) — `1/1 -> 3/724` through `3/822`, 99 `moved` events — then deleted box 1, which buried the 133 source records (D134), and box 1's number was reused the same evening for a new drawer. They sit at box 3 indices **724–822** today. The runs around them own 54–722 and 823–887, so **724–822 is a gap no live run covers** and no re-join by any run could reach them. They were refused because the RUN is named after box 1, which is a fact about a label and not about where a single one of those cards is.

### The upstream fix, and exactly how far it reaches

**`Box.bid` already existed (D145) and the run object had only half adopted it.** `server/pipeline_routes.py:_resolve_scope` has written `bid` into the scope block since that entry landed, and `refuse_reallocated` has read it. **A run started in a TERMINAL had no `scope` block at all** — `_run_box`'s own docstring says so, and falls back to parsing the box number out of the capture directory's NAME — so the CLI was the last creation path that could still produce a run nobody can bind. `cli/cmd_identify.py:_scope_for` closes it.

**The box comes from the sidecars, not from the path.** `captures/cards/box3` is a convention; `Capture.box` is what the capture itself recorded, and the two disagree the moment a directory is renamed, mirrored or handed over as a pile. **A run whose captures name two boxes gets no scope rather than a guessed one** — D48 keeps a run to one box, and a scope naming one of two would be a claim the command cannot support.

**WHICH RUNS THIS PROTECTS, STATED PLAINLY, BECAUSE IT IS LESS THAN IT SOUNDS.** The binding protects **runs started from now on**, by either path. It cannot reach backwards, and the reason is not an oversight: **a drawer deleted before D145 landed has no `bid` to recover.** The backfill gave the boxes alive that day ids 1–5 matching their numbers, and the drawer `2026-08-29-box1-01` was over was deleted on 2026-09-11 — it never had one and never can.

Measured across the owner's fifteen run directories: **one carries a `bid`** (`2026-09-12-box4-01`), twelve carry a scope block with no id, and two carry no scope at all. **Every one of the other fourteen is read by the older inference rule, unchanged**, which is the arm D145 already said had to go on working rather than be a shim.

So the honest division is: **the binding ends the class going forward; the rescue is the only thing that can reach the run already stranded**, and it is keyed on the cards' own current `(box, index)` and photograph digest rather than on the run at all.

### The rescue, and why it is a second run rather than an edit

**It is `cli/resolve.py:realign`'s mechanism with one restriction lifted.** `realign` re-binds a run's records to the slots their photographs occupy now, and it looks only in the boxes THE RUN NAMES — which is right inside a join, because a join must never follow a card into a drawer nobody asked it about. That restriction is also exactly why it cannot see this case: the cards left the box the run names. `rescue` searches every live drawer.

**That widening is safe here and would not be safe inside a join**, and the difference is the three properties this command has and `realign` does not: it is an explicit operator act, it previews before it writes, and it produces a NEW run rather than changing what any join does.

**THE PHOTOGRAPH IS THE TRUTH, WHICH IS D36's OWN SENTENCE.** Nothing here trusts a slot number, a run name, a box number, or the `run` column on a card. Every binding is a sha256 of the photograph on disk matched against the sha256 the run recorded when it read that card. Measured on the owner's store: **99 of the run's 133 records match exactly one live photograph each, with 0 duplicated digests and 0 ambiguities**; the other 34 never left box 1 and went with it.

**A digest on two records, or on two photographs, refuses the whole run.** `realign`'s rules unchanged — a digest that names two slots is a question, not a slot, and `CLAUDE.md` forbids guessing an identity. Cards spread across two drawers refuse too, because D48 keeps a run to one box.

**WHAT IT WRITES IS A NEW RUN, BECAUSE A RUN IS AN IMMUTABLE INPUT.** `cli/runs.py` says so in its first sentence and the whole pipeline rests on it: a run directory is a record of what was read, and editing one would make every report about it a claim nobody can check. The rescue derives a second run — the same readings, re-addressed to the positions the photographs are at now, scoped to the drawer they are actually in and carrying that drawer's `bid` — and leaves the first exactly as it is. **The new run joins and emits by the ordinary path with no special case anywhere**, which is the property that made this shape worth the extra directory.

**The reading carries over and the source run's own ACTS do not.** `model`, the prompt fingerprints, `flags` and `rule` describe how these cards were read and are as true of the rescue as of the source. `joined`, `emitted`, `counts`, `usage`, `batch_ids` and `collected` are a record of what the SOURCE did; copied across they would claim this run had submitted a batch, spent money and sent a file, none of which it has.

**It refuses a run that is not stranded**, which is a safety property rather than tidiness. A healthy run is joinable already; rescuing one would put a second run over the same positions in `runs/`, which is the shape D86 measured a capped send over.

**It is safe to run twice.** A rescue whose identifications would be byte-identical to one that already exists writes nothing and says so. A rescue that would differ writes a new directory rather than editing the old one, for the same reason the source is never edited.

### What the rescue recovered, and the thing it turned out NOT to be

**Run against a copy of the owner's store, the rescue re-addressed all 99 and the join matched every one**: `cards in: 99 | SKUs matched: 42 | copies matched: 99`, with `unmatched cards: 0`, `unmatched rows: 0`, `cards dropped: 0`.

**And `emit` then wrote nothing, which is the correct answer and was not the expected one.** All 99 are **already live at TCGplayer**: the source run emitted 133 copies on 2026-08-30, and across all 42 SKUs the store reads `copies on hand == pushed == live`, with **zero** copies on hand that TCGplayer is not recorded as holding. `uncommitted_positions` is what stopped the resend, exactly as D7 says, and the rescue cannot double-send.

**So what was stranded was not the stock — it was the pricing surface.** Those 42 SKUs were in no joined run, so `#/pricing` could not offer them, they could not be re-priced or held, and the moment a copy sold there would have been nothing able to re-emit the rest. **The rescue puts them back on that surface and makes them re-emittable the instant TCGplayer stops holding a copy.** With those 42 listing records cleared in a second throwaway copy — the counterfactual where they had never been sent — the same rescue run emits **42 rows, 99 cards**, every one of the 99.

**The claim in the ruling is therefore narrowed rather than met in full, and it is narrowed in the operator's favour:** the cards were never unsellable, they were unreachable, and both halves of that are now fixed.

### The warning counts cards, and drops the rows holding none

`_unreachable`'s two lists counted RUNS, so `2 runs over a deleted box` read identically whether the store was withholding nothing or 99 sellable cards — and on this machine it was saying both at once. Every row carries `cards` now, counted off the CARDS rather than off the run directory because what a stranded run is withholding is what is still on a shelf: smaller every time one of its cards sells, and zero once its drawer is deleted. `#/pricing` drops a row holding none.

**Nothing is dropped by that.** A run with no card on hand is withholding no card, so the figures still account for every copy the worklist cannot offer. **A `null` count is an unreadable store rather than a zero and is kept** — unknown is not the same claim as nothing, and a warning that went quiet on a store that would not open would be the worst of the two.

### What this does not do

**It does not repeal or weaken D36, and its guard gains arms rather than losing them.** The refusal is untouched on both paths; `realign`, `_photo_digests` and `refuse_reallocated` are unchanged. D36's caution is earned — a re-join of box 2 once wrote all 47 queue entries one position off, `Wally's Compassion` described over a photograph of an Inteleon — and nothing here makes a join follow a card anywhere.

**It does not make the rescue reachable from a screen, and that is a choice rather than an omission.** `CLAUDE.md`'s route-is-not-a-feature rule governs capabilities built in `server/`; this is a CLI repair in the shape `pkmnscan prices adopt` already has — one press, by the owner, once. What the SCREEN gained is the figure that says the repair is needed, and `#/pricing`'s warning names the command. **If a second run is ever stranded this way, that is the signal to reopen and build the door.**

**It does not take the box out of anything else.** `_resolve_scope`, `_busy_run` and the selection are a separate pass with its own entry and its own measurements; this touches none of them.

### What would reopen it

**A second run stranded after this lands.** The binding is meant to make that impossible for any run started from now on, so one occurring would mean a creation path nobody has found.

**A stranded run whose cards are spread across two drawers.** It refuses today and names both, because D48 keeps a run to one box. A cart-shaped run would make it a list, which is the same sentence D145 already wrote about `refuse_reallocated`.

**A drawer that outlives its `bid`.** Nothing can restore an id that was never issued, so any future repair reaching backwards past D145 is a rescue keyed on photographs, not a binding.
