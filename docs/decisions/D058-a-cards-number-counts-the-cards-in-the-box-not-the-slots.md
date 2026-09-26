## D58 — A card's number counts the cards in the box, not the slots

**A card's number counts the cards in the box, so selling one makes the card behind it take that number on every screen.** Built 2026-08-30 on the owner's instruction: when cards are marked sold, the slot is not left empty — the cards before it move up one.

**It is the answer to D30, which had been waiting on the owner since 2026-08-23.** That entry states the problem in the sentence this one deletes: `Card 17` is the **seventeenth slot**, not the seventeenth card you can count, and once a section has holes those two stop being the same number and every label in that section becomes uncountable by hand.

D30 answered it with `neighbors` and `section_gaps` — built, and both kept — and with a physical marker for the emptied slot, which was the owner's open item and is now moot: there is no gap left to mark. Its box-audit paragraph gets easier for the same reason, because what is in the section and what the record says are the same count again.

### Two things are wider than the ask, and both are the owner's

**The stored index never moves; the LABEL does.** The instruction says to assume the indexes can move, and D10 as amended already carved the seam this uses instead — *positions are never renumbered* governs the INDEX, and the label is a view — restated in `pipeline/join.py:Position`'s own docstring. Moving the stored index was costed and rejected on four measurements, each a reason not to reach for it later:

- **`do_remove_card` deletes its target and a sale must not**, so a sold record's index has nowhere to go once the survivor above slides into it. Every answer is a v3 schema, rewriting `next_index`, `box_fill`, `copies_on_hand`, `positions_for_sku`, `_walk`, `_release_plan`, the box-delete gate and the migration.
- **The Fulfiller's twenty-second undo would aim at the wrong card.** `undoSale` posts to `/inventory/<box>/<index>/sold` — a POSITION, with `SOLD_FIELDS = ("undo",)` and no aim check — and after a shift that position holds his next card.
- **D28's answer-undo and D37's stand-down reversal would stop working.** `_answer_before` and `_clearing_event` treat a `renumbered` history line as a hard stop, and every sale would write one.
- **D52 would gain a fourth occupant-changing operation**, on six screens whose `photoUrl` callers rest on the element re-keying when a card moves.

**Sealed boxes consolidate too, so there is no open/sealed distinction at all.** The ask gated this on the lid; the owner dropped the gate when shown that the alternative makes every label jump the moment a box with sold cards is sealed. What it costs is named in D20 below: a sealed box's denominator moves now, which that entry froze `capacity` to prevent.

### What it is, measured

On the owner's store the day it landed:

| box | state | records | sold | retired | holds |
|---|---|---|---|---|---|
| 1 · UNL Rares | open | 133 | 2 | 0 | **131** |
| 2 · ME01 C/UC | sealed | 543 | 0 | 1 | **542** |
| 3 · RB Epics | open | 39 | 9 | 0 | **30** |

Every label above a departed card moved once, deliberately — the same event as D10's deletion of automatic sectioning on 2026-08-29, and pinned the same way, so the next such shift cannot be accidental either.

**`Position` gains the box's occupancy and stays the only label formula in the repo.** `occupied` is every on-hand index in the box, ascending, and `departed` is every terminal one. `slot` is this card's place among the first; `section`, `section_start`, `section_end` and `card` all read it. **`None` and `()` are opposite facts and the sentinel is `None`**: an empty tuple is a box every card has left, whose cards must still render as departed rather than reverting to slot numbers, and `None` is a caller with no inventory to consult — which renders in index space, byte-identically to the day before this landed. `BoxView` is that pair with a name and `BoxView().at(box, index)` is the one constructor.

### The sections adjust, and that is what makes both numbers countable

**Mapping the cards and not the dividers would have been a half-build that looks right.** A divider declared at index `s` stands in front of the first card still on hand at or above it, so its number is the count of cards below `s` plus one. Both `slot` and `section_start` then move by the same amount for a departure in an earlier section, and `card` — their difference — does not. Worked on box 2's real layout `[1, 86, 171, 253, 394]` after four cards depart at 10, 20, 30 and 180:

| | before | after |
|---|---|---|
| divider numbers | 1, 86, 171, 253, 394 | 1, **83**, **168**, **249**, **390** |
| the card at index 200 | `Section 3 · Card 30` | `Section 3 · Card 30` |

It becomes `Card 29` only when 180 sells, which is a card in its own section and in front of it. *Go to the third divider and count twenty-nine cards* — and a sale anywhere else in the box does not disturb the count. T7 asserts both halves, because a build that mapped nothing passes the second and a build that mapped only the cards passes the first.

**An empty section keeps its number.** Two dividers with no card left between them map to one number and are deliberately not deduped: the plastic is still in the box, and renumbering the sections behind it would send a person to the wrong divider. `sections_detail` reports it with `count: 0`.

**A divider past the fill keeps its unfilled slots, and a T7 case caught the version that did not.** `[1, 51]` typed into a five-card box means section 2 starts at the fifty-first CARD, and answering *the sixth* would quietly delete a plan. `Position._divider` adds one for each slot between the box's high-water mark and the divider, so the two definitions agree everywhere inside a box that has grown into its own dividers.

**The stored layout is still in index space and is never rewritten.** Same argument as the index itself: a divider list rewritten on every sale is an answer that can drift and that nobody can correct. Only the rendering maps.

**So the dividers editor moved to count space**, and this is the piece the owner's own question exposed. `BoxOps.tsx` seeded the field from the raw `record.sections` and posted the same list, so under this change an operator would have been typing index numbers that appear nowhere else in the product. It seeds from `sections_detail[].start` now, and `do_put_box` maps what comes back through `join.divider_index` before `check_sections` sees it. **`divider_index` answers the index of the card the section starts at** — which is what `open_section` already writes when the operator presses `S` at the box, so a divider typed in and a divider put in at the feeder are the same kind of number. **Ordinal 1 is always index 1**, even where card 1 itself has sold, because `check_sections`' rule is a fact about the front of a box rather than about its contents. Property-tested over 4,000 random boxes: the round trip is exact and the result is always sorted, unique and starting at 1.

### A departed card is in no slot

**It does not keep the number it held**, because that number belongs to the card that closed up behind it, and answering it would send a person to the wrong slot. `join.departed_label` renders `Box 3 · departed`, beside `pooled_label` in the same file for the reason that helper's own comment gives: the string that REPLACES a label belongs next to the label formula.

**It names no door.** `sold` and `retired` are different departures with different reversals and both are already on the record beside this string. A second spelling of the state inside the one label formula is what `pooled_label` refuses one paragraph up.

**Its section stays.** The numbers go and the section does not: a departed record belongs to a real part of a real box, the walk groups by it, and nulling it would file every sold card under a third heading that is not a section.

**A receipt is untouched and must stay so.** `Inventory.tsx` and `Fulfillment.tsx` both snapshot the label BEFORE the write, so *Sold Box 3 · Section 1 · Card 7* still names where the operator just was. The departed string is for the record afterwards, not for the moment.

### The denominator follows, which amends D20

**`_denominator` is retired and the answer is the cards on hand, sealed or open.** Forced by the numerator rather than chosen: `slot` counts cards, so dividing it by a frozen capacity draws a card at a percentage of a box it is not at, drifting further wrong with every sale. On a 543-card box that has sold 200, `#100 of 543` puts a thumb a third of the way from the card.

**What the function bought is now held structurally, which is stronger.** It existed so two renderers could not disagree; `_Places.view` computes the count from the walk it already runs and `_box_row` reads it off the SAME instance. One scan, two renderers, nothing to keep in step.

**`capacity` keeps its D20 job and loses this one.** It records how full the box got. `GET /boxes` still reports it, `close_box` still freezes it at the high-water mark, and the seal control still names that number before it is pressed — what it no longer is, is what anything divides by. A sealed box's identity line carries both (`542 of 543 sealed`), because one of them beside a bar reading `#40 of 542` would be the second-renderer failure with two numbers instead of one.

**`GET /boxes` gains `on_hand`**, and `fill`, `next_index`, `cards`, `sold` and `retired` are untouched — `BoxOps` promises its census greps to `inventory.json` and it still does.

### A live defect this forced, and the rule that fixes it

**`store/queues.py:QueueEntry.label` is a stored rendering and nothing had ever recomputed it.** Written once by `cli/resolve.py` at join time, served verbatim by `GET /queues`, drawn by `ReviewQueue.tsx`. Measured on the owner's real store: **15 of 92 entries carry a label drawn against `CARDS_PER_SECTION = 25`**, the divider rule D10's amendment deleted on 2026-08-29. Box 1 declares no dividers at all and its queue holds both `Box 1 · Section 1 · Card 108` and `Box 1 · Section 5 · Card 18` — a section that does not exist.

**It is latent rather than live today, and saying so is the point of measuring it.** All 92 of those entries are `cleared_by_human`, so `open_entries` serves none of them and nothing has been drawing a wrong label on screen. What the measurement establishes is the SHAPE: the field is a rendering that was written down, nothing has ever recomputed it, and a rule that moved left it behind. D28's `Queue.reopen` is the path that would surface one, and the next join writes fresh entries that go stale the next time a layout changes.

**Re-rendered through the fix, 74 of the 92 come out differently** — the 15 stale ones, the retired card at `2/95` which is now `Box 2 · departed`, and the rest renumbered by the cards that have left in front of them.

**D56 states the fix for exactly this shape one register up**, about a run's box name: never write down an answer nobody can correct; join it when it is read. `do_queues` re-renders the label from the live inventory through the same `_Places` every other screen uses. The stored field keeps its value on disk so nothing already written moves, and no route serves it.

**And `cli/resolve.py` built every `Position` with no layout at all**, which is older than D58 and is fixed with it: a box-2 queue entry was written as `Section 1 · Card 300` where the app rendered `Section 4 · Card 48`. Two renderers, two answers, and nothing had ever compared them. `box_views` is that walk, and **T7 asserts the two spell one address on a real card** — the same shape `make port-agreement` uses for the other pair that has to agree.

### The same defect at a second site — `pricing.json` (amendment, 2026-08-30)

**The queue was not the only stored rendering, and `pricing.json` is the one that was on a screen.** `cli/cmd_join.py:_pricing_table` writes `{"box", "index", "label"}` per matched SKU, `GET /pipeline/runs/<name>/pricing` served the stored string verbatim, and `app/src/Pricing.tsx` drew it into `.pricing-photo-caption` under the copy's photograph. Found by sweeping for the shape the section above describes, not by a failure.

**Measured on the owner's store, both runs that have a pricing table:**

| run | positions | unchanged | departed | renumbered |
|---|---|---|---|---|
| `2026-08-29-box1-01` | 113 | 4 | 18 | 91 |
| `2026-08-30-box3-01` | 33 | 0 | 20 | 13 |
| | **146** | **4** | **38** | **104** |

Box 1 holds 133 records with 18 sold, box 3 holds 39 with 24, and neither declares a divider — so all 104 are cards that closed up over a departure in front of them and all 38 are copies pointed at a slot they have left.

**This one was LIVE where the queue's was latent.** Those 92 entries were all `cleared_by_human` and `open_entries` served none of them. All 146 of these are served the moment either run is opened, under a photograph `photoUrl` addresses BY SLOT — so the picture was always the index's current occupant while the caption was the join's, and nothing on the screen said which was which.

**Same posture: re-rendered at read, file untouched.** `server/pipeline_routes.py:_relabel_positions` composes against the live store on every request and serves the stored string never; `box` and `index` travel exactly as written, because they are the key `photoUrl` is aimed by. No re-join corrects those 146 — opening the screen does.

**Through `cli/resolve.py:box_views`, which is forced rather than preferred:** `capture_server` imports `pipeline_routes`, so reaching `_Places` is the cycle `PipelineRefusal` exists to avoid. Not a second renderer — it is the walk the paragraph above says T7 already holds against `_Places`.

**`place_text` rather than `Position.label`, which fixed a pooled bug on the way past.** `pokemon_code` is `located: False` **and** `catalogued: True`, so its cards do reach a join — and were landing here wearing the one string D24 says may never be printed for them. Its store key also keeps two copies of one SKU from drawing the identical caption in a strip built for stepping between them (D68).

**A box the walk will not answer for gets `null`, never an index-space label** — the store-wide degrade, or a box deleted out from under the run. A bare `BoxView()` would render both in the numbering this entry replaced, beside captions drawn in the other one. The screen shows `no label · <box>/<index>`, which is `BoxBrowse`'s fallback rather than a new vocabulary.

**Two things here are deliberately NOT fixed.** The stored `box`/`index` KEYS go stale too under a mid-box delete (D36); `cli/resolve.py:paperwork_for` realigns them by hashing photographs for the order path, which is too much for a route a screen opens, and it is benign here only because `photoUrl` addresses by slot as well, so caption and picture now agree. And `GET .../file?name=pricing.json` still hands the raw file: a download is the artifact, not a rendering of it.

### What is deliberately not changed

- **`next_index`, `box_fill`, `allocate_capture` and the store schema.** No migration. D10's permanent gap survives intact in the one place it was ever load-bearing — the allocator — which is why T7's two hardest cases, `check_allocator`'s and `check_mark_sold`'s, are untouched.
- **`renumber_blocked`.** Its sold/retired clause's stated reason weakens — the box already closes up over a departure, so there is no gap left to close — but relaxing a refusal is its own decision, and this one would let the mid-box delete shift indices across records that are history and commitments. The refusal stands; the copy on `BoxBrowse` that recited the old reason is corrected, because a refusal explaining itself with something nobody can check any more teaches an operator to read past it.
- **D52, `photoUrl` and `?card=`.** No index moves, so there is no fourth occupant-changing operation.
- **D30's `neighbors`.** Kept, and still worth having for confirming a slot. `section_gaps` is structurally zero for a consolidated box and `placeSentence` already omits the phrase at zero.

### What it costs

**A corrupt record now blanks labels rather than only the decoration, store-wide.** T7 asserted the opposite until today — that one bad record does not take the route down, and every other row keeps its label — on the ground that a label needs only this record's own two integers and the box's layout. That ground is exactly what this removed. A record nobody can place might be in this box and might be on hand, so the count is unknown; answering the index-space label instead would put a second numbering system on the screen with nothing saying which it is, and a person sent to `Card 40` in a box that has sold three would open the wrong slot and see nothing wrong.

**Narrowing the blast radius per box is the fix to reach for if that bites**, and it is not taken here because it would be an untested branch added to make a case go green: a record whose INDEX will not read could be attributed to its box and poison only that one, where a record whose BOX will not read could be in any of them.

**What would reopen this: a box whose slots are fixed.** Everything above rests on the physical fact that a card pulled out of a stack lets the cards behind it slide forward — the same premise D10 ruling 1 already leans on for the mid-box delete. A binder, a sleeved page or any storage where a slot stays empty is a box this numbering describes wrongly, and the honest answer then is per-box rather than global: the flag would sit on `Box` beside `sections`, and the seal gate the owner dropped is the cheapest version of it.

### Amended 2026-09-25: capacity is gone

The paragraph above that keeps `capacity` for "its D20 job" is superseded. The owner removed the
seal (D-sealed-boxes-removed), and `close_box` was the only writer of `capacity`. So a box has
no capacity, and this entry's rule that every number counts the cards on hand is the only rule.
