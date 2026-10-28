# D58 — A card's number counts cards, not slots

**A card's number counts the cards in the box.** Selling one makes the card behind it take that number on every screen. The owner's instruction: when cards are marked sold, the slot is not left empty. The cards before it move up one.

This answers the open question about gaps. `Card 17` is the seventeenth slot, not the seventeenth card you can count. Once a section has holes, those two numbers differ, and every label in that section becomes impossible to count by hand. The earlier design used `neighbors` and `section_gaps` (both kept), and a physical marker for the emptied slot. That marker was the owner's open item and is moot now: no gap is left to mark. The box-audit paragraph gets simpler for the same reason. The section and the record now give the same count.

### Two things are wider than the ask, and both are the owner's

**The stored index never moves. The label does.** The instruction said to assume indexes can move. D10, as amended, already set the seam this design uses: *positions are never renumbered* governs the index, and the label is a view. `pipeline/join.py:Position`'s docstring restates it. Moving the stored index was costed and rejected on four measurements, each a reason not to reach for it later:

- **`do_remove_card` deletes its target, and a sale must not.** A sold record's index has nowhere to go once the card above slides into it. Every answer needs a v3 schema. It rewrites `next_index`, `box_fill`, `copies_on_hand`, `positions_for_sku`, `_walk`, `_release_plan`, the box-delete gate and the migration.
- **The Fulfiller's twenty-second undo would aim at the wrong card.** `undoSale` posts to `/inventory/<box>/<index>/sold`, a POSITION, with `SOLD_FIELDS = ("undo",)` and no aim check. After a shift, that position holds the next card.
- **D28's answer-undo and D37's stand-down reversal would stop working.** `_answer_before` and `_clearing_event` treat a `renumbered` history line as a hard stop. Every sale would write one.
- **D183 would gain a fourth occupant-changing operation** on six screens. Their `photoUrl` callers rely on the element re-keying when a card moves.

**Sealed boxes consolidate too, so no open/sealed distinction remains.** The ask gated this on the lid. The owner dropped the gate after seeing that the alternative makes every label jump when a box with sold cards is sealed. The cost is in D20 below: a sealed box's denominator now moves. D20 froze `capacity` to prevent that.

### What it is, measured

On the owner's store at landing:

| box | state | records | sold | retired | holds |
|---|---|---|---|---|---|
| 1 · UNL Rares | open | 133 | 2 | 0 | **131** |
| 2 · ME01 C/UC | sealed | 543 | 0 | 1 | **542** |
| 3 · RB Epics | open | 39 | 9 | 0 | **30** |

Every label above a departed card moved once, on purpose. This is the same event as D10's deletion of automatic sectioning, and it is pinned the same way. The next such shift cannot be accidental either.

**`Position` gains the box's occupancy and stays the only label formula.** `occupied` is every on-hand index in the box, ascending. `departed` is every terminal one. `slot` is this card's place among the occupied indexes. `section`, `section_start`, `section_end` and `card` all read it. **`None` and `()` are opposite facts, and the sentinel is `None`.** An empty tuple is a box every card has left. Its cards must still render as departed, not revert to slot numbers. `None` is a caller with no inventory to consult. It renders in index space, byte-identical to the day before this change. `BoxView` is that pair with a name. `BoxView().at(box, index)` is the one constructor.

### The sections adjust, and that makes both numbers countable

**Mapping the cards and not the dividers would be a half-build that looks right.** A divider declared at index `s` stands in front of the first card still on hand at or above it. Its number is the count of cards below `s`, plus one. Then `slot` and `section_start` move by the same amount for a departure in an earlier section, and `card`, their difference, does not move. Worked on box 2's layout `[1, 86, 171, 253, 394]`, after four cards depart at 10, 20, 30 and 180:

| | before | after |
|---|---|---|
| divider numbers | 1, 86, 171, 253, 394 | 1, **83**, **168**, **249**, **390** |
| the card at index 200 | `Section 3 · Card 30` | `Section 3 · Card 30` |

It becomes `Card 29` only when 180 sells. That card is in its own section, in front of it. *Go to the third divider and count twenty-nine cards*. A sale anywhere else in the box does not change the count. T7 asserts both halves. A build that mapped nothing would pass the second, and a build that mapped only the cards would pass the first.

**An empty section keeps its number.** Two dividers with no card between them map to one number. They are deliberately not deduped. The plastic is still in the box, and renumbering the sections behind it would send a person to the wrong divider. `sections_detail` reports it with `count: 0`.

**A divider past the fill keeps its unfilled slots.** A T7 case caught the version that did not. `[1, 51]` typed into a five-card box means section 2 starts at the fifty-first card. Answering *the sixth* would quietly delete a plan. `Position._divider` adds one for each slot between the box's high-water mark and the divider. The two definitions then agree everywhere inside a box that has grown into its own dividers.

**The stored layout stays in index space and is never rewritten.** A divider list rewritten on every sale would be an answer that can drift, and nobody could correct it. Only the rendering maps.

**The dividers editor moved to count space.** This is the piece the owner's own question exposed. `BoxOps.tsx` seeded the field from the raw `record.sections` and posted the same list. An operator would have typed index numbers that appear nowhere else in the product. It now seeds from `sections_detail[].start`. `do_put_box` maps the result through `join.divider_index` before `check_sections` sees it. **`divider_index` answers the key of the first record after the card in front, departed or not.** A departed record between the two cards goes into the new section. A departed record in front of the card before stays in the old one. Where nothing has left, that record is the card itself, which is what `open_section` writes when the operator presses `S` at the box. One past the last card on hand follows the same rule: the first departed record behind it, or the slot after the last record when none sits there. A divider typed in and one put in at the feeder are the same kind of number. **Ordinal 1 is the front of the box**, even where card 1 has sold: index 1, or below it where a section was placed in front of card 1 (D294). `check_sections`' rule is a fact about the front of a box, not its contents. No property test exists. `master.check_sections` refuses a layout that is not sorted and unique or that does not start at the front of the box, so a bad result is refused at the write. Example cases cover the round trip: `harness.tests.t7.inventory_routes.check_consolidated_numbering` sends the editor's seeded starts back and finds the store unchanged, and `harness.tests.t7_box_map.check_divider_editor_keys` does the same after a section move. Whether the round trip is exact for every box is unmeasured.

### A departed card is in no slot

**It does not keep the number it held.** That number belongs to the card that closed up behind it. Answering with it would send a person to the wrong slot. `join.departed_label` renders `Box 3 · departed`. It sits beside `pooled_label` in the same file, as that helper's comment explains: the string that replaces a label belongs next to the label formula.

**It names no door.** `sold` and `retired` are different departures with different reversals. Both are already on the record beside this string. A second spelling of the state inside the label formula is what `pooled_label` refuses.

**Its section stays.** The numbers go. The section does not. A departed record belongs to a real part of a real box. The walk groups by section. Nulling it would file every sold card under a third heading that is not a section.

**A receipt is untouched and must stay so.** `Inventory.tsx` and `Fulfillment.tsx` snapshot the label before the write. So *Sold Box 3 · Section 1 · Card 7* still names where the operator just was. The departed string is for the record afterward, not for the moment of the sale.

### The denominator follows, which amends D20

**`_denominator` is retired. The answer is the cards on hand, sealed or open.** The numerator forces this. `slot` counts cards, so dividing it by a frozen capacity places a card at a percentage of a box it is not in. The error grows with every sale. On a 543-card box that has sold 200, `#100 of 543` puts a thumb a third of the way from the card.

**What `_denominator` gave is now held structurally, which is stronger.** It existed so two renderers could not disagree. `_Places.view` now computes the count from the walk it already runs, and `_box_row` reads it from the same instance. One scan, two renderers, nothing to keep in step.

**`capacity` keeps its D20 job and loses this one.** It records how full the box got. `GET /boxes` still reports it. `close_box` still freezes it at the high-water mark. The seal control still names that number before it is pressed. It is no longer the divisor. A sealed box's identity line carries both (`542 of 543 sealed`), because one of them beside a bar reading `#40 of 542` would be the second-renderer failure with two numbers instead of one.

**`GET /boxes` gains `on_hand`.** `fill`, `next_index`, `cards`, `sold` and `retired` are unchanged. `BoxOps` promises its census greps to `inventory.json`, and it still does.

### A live defect this forced, and the rule that fixes it

**`store/queues.py:QueueEntry.label` is a stored rendering, and nothing recomputed it.** `cli/resolve.py` wrote it once at join time. `GET /queues` served it verbatim, and `ReviewQueue.tsx` drew it. On the owner's store, **15 of 92 entries carry a label drawn against `CARDS_PER_SECTION = 25`**. D10's amendment deleted that divider rule. Box 1 declares no dividers, yet its queue holds `Box 1 · Section 1 · Card 108` and `Box 1 · Section 5 · Card 18`. A section that does not exist.

**It is latent, not live.** All 92 entries are `cleared_by_human`. `open_entries` serves none of them, so no wrong label reached a screen. The measurement shows the shape: a rendering was written down, and no rule change ever recomputed it. D28's `Queue.reopen` would surface one. The next join writes fresh entries that go stale on the next layout change.

**Re-rendered through the fix, 74 of 92 come out different.** That is the 15 stale ones, the retired card at `2/95` (now `Box 2 · departed`), and the rest renumbered by cards that left in front of them.

**D56 states the fix for this shape at the run's box name.** Never write down an answer nobody can correct. Join it when it is read. `do_queues` re-renders the label from the live inventory through the same `_Places` every other screen uses. The stored field keeps its value on disk, so nothing already written moves. No route serves it.

**`cli/resolve.py` built every `Position` with no layout.** That predates this entry and is fixed with it. A box-2 queue entry was written as `Section 1 · Card 300`, where the app rendered `Section 4 · Card 48`. Two renderers gave two answers, and nothing compared them. `box_views` is that walk. **T7 asserts the two spell one address on a real card.** `make port-agreement` uses the same shape for the other pair that must agree.

### The same defect at a second site: `pricing.json` (amendment)

**`pricing.json` is the other stored rendering, and it reached a screen.** `cli/cmd_join.py:_pricing_table` writes `{"box", "index", "label"}` per matched SKU. `GET /pipeline/runs/<name>/pricing` served the stored string verbatim. `app/src/Pricing.tsx` drew it into `.pricing-photo-caption` under the copy's photograph. A sweep for the shape above found it. No failure did.

**Measured on the owner's store, both runs with a pricing table:**

| run | positions | unchanged | departed | renumbered |
|---|---|---|---|---|
| `2026-08-29-box1-01` | 113 | 4 | 18 | 91 |
| `2026-08-30-box3-01` | 33 | 0 | 20 | 13 |
| | **146** | **4** | **38** | **104** |

Box 1 holds 133 records, 18 of them sold. Box 3 holds 39, 24 of them sold. Neither declares a divider. So all 104 renumbered cards closed up over a departure in front of them. All 38 departed copies point at a slot they have left.

**This one was live where the queue's was latent.** The 92 queue entries were all `cleared_by_human`. All 146 of these are served as soon as either run opens. The picture is addressed by slot, through `photoUrl`. So the picture always showed the index's current occupant, while the caption showed the join's card. Nothing on screen said which was which.

**Same posture: re-rendered at read, file untouched.** `server/pipeline_routes.py:_relabel_positions` composes against the live store on every request. It never serves the stored string. `box` and `index` travel as written, because they are the key `photoUrl` is aimed by. No re-join corrects those 146. Opening the screen does.

**The walk is `cli/resolve.py:box_views`, which is forced rather than preferred.** `capture_server` imports `pipeline_routes`. Reaching `_Places` would form the cycle `PipelineRefusal` exists to avoid. The walk is not a second renderer. It is the walk T7 already holds against `_Places`.

**`place_text` replaces `Position.label`, which fixed a pooled bug on the way.** `pokemon_code` is `located: False` and `catalogued: True`. Its cards do reach a join, and they landed here wearing the one string D24 says may never be printed for them. The store key also keeps two copies of one SKU from drawing the same caption in a strip built for stepping between them (D68).

**A box the walk will not answer for gets `null`, never an index-space label.** That covers a store-wide degrade, or a box deleted out from under the run. A bare `BoxView()` would render both in the numbering this entry replaced, beside captions drawn in the other. The screen shows `no label · <box>/<index>`, which is `BoxBrowse`'s fallback, not a new vocabulary.

**Two things are deliberately not fixed.** The stored `box` and `index` keys go stale under a mid-box delete (D36). `cli/resolve.py:paperwork_for` realigns them by hashing photographs, for the order path. That is too much for a route a screen opens. It is benign here, because `photoUrl` addresses by slot too, so caption and picture now agree. `GET .../file?name=pricing.json` still returns the raw file. A download is the artifact, not a rendering of it.

### What is deliberately not changed

- **`next_index`, `box_fill`, `allocate_capture` and the store schema.** No migration. D10's permanent gap survives intact in the one place it was ever load-bearing, the allocator. That is why T7's two hardest cases, `check_allocator` and `check_mark_sold`, are untouched.
- **`renumber_blocked`.** Its sold/retired clause gives a reason that is weaker now. The box already closes up over a departure, so no gap is left to close. Relaxing a refusal is its own decision, though. This one would let a mid-box delete shift indices across records that are history and commitments. The refusal stands. The copy on `BoxBrowse` that recited the old reason is corrected. A refusal that explains itself with something nobody can check teaches an operator to read past it.
- **D183, `photoUrl` and `?card=`.** No index moves, so there is no fourth occupant-changing operation.
- **`neighbors`.** Kept. It is still useful for confirming a slot. `section_gaps` is structurally zero for a consolidated box, and `placeSentence` already omits the phrase at zero.

### What it costs

**A corrupt record now blanks labels, not only the decoration, store-wide.** T7 asserted the opposite until this change. One bad record did not take the route down, and every other row kept its label. The ground for that was that a label needs only this record's own two integers and the box's layout. That ground is what this change removed. A record nobody can place might be in this box, and might be on hand, so the count is unknown. Answering with the index-space label would put a second numbering system on the screen, with nothing saying which it is. A person sent to `Card 40` in a box that has sold three would open the wrong slot and see nothing wrong.

**Narrowing the blast radius per box is the fix to reach for if this bites.** It is not taken here, because it would be an untested branch added to make a case go green. A record whose index will not read could be attributed to its box and poison only that box. A record whose box will not read could be in any of them.

**What would reopen this: a box whose slots are fixed.** Everything above rests on a physical fact. A card pulled from a stack lets the cards behind it slide forward. D10 ruling 1 leans on the same premise for the mid-box delete. A binder, a sleeved page, or any storage where a slot stays empty is a box this numbering describes wrongly. The honest answer then is per box, not global. The flag would sit on `Box` beside `sections`. The seal gate the owner dropped is the cheapest version of it.

### Amended: capacity is gone

The paragraph above that keeps `capacity` for its D20 job is superseded. The owner removed the seal (D299), and `close_box` was the only writer of `capacity`. So a box has no capacity. The rule that every number counts the cards on hand is the only rule.
