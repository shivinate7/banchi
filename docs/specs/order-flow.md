# Order flow, boxes, and search (build-order step 13)

The spec holds the reasoning, the rejected alternative and what a later session must keep. A
section that describes something not built says so in its own heading.

---

## STATUS

**BUILT.** Store schema v2 and its migration. `GET /search`, `GET /boxes`, `POST /boxes` and
`PUT /boxes/<box>`. The shared components: the position bar, the card locations panel, the
search field and the search hook. The owner's search-and-sell on `#/inventory`. The Fulfiller's
search on `#/fulfillment`. D26 (`retired`), D29 (group answers), D58 (the gap convention), D27
and D28. T7 reaches the store and the routes.

**NOT MEASURED.** No physical session has used these screens. Every number in this file comes
from fixtures and from the store the screens were built against. Read each as self-consistent
over a wider range than the evidence covers.

### 0.1 — The rule this session runs under

`docs/specs/capture-server.md` section 0.3 says how writing docs in this repo blocks a
commit. A path whose first segment is a real top-level directory, and which does not exist,
blocks. Name an unbuilt thing by its behavior, never by a file that does not exist.

---

## 1. What this step is, in one sentence

**Three decisions that look unrelated are one shape.** D7 says copies of a SKU are
interchangeable. D20 says a box is an object whose size is known only afterwards. D10, as
amended, says a position's index is its identity and its label is a rendering. Each takes a
thing the code treated as an address and makes it a view of something else. A listing stage
stops being *which four copies* and becomes *how many*. A section number stops being
arithmetic on an index and becomes a lookup against a layout a human declared.

The search-and-sell flow is what all three are for. Somebody sells a card and types its name.
The answer must be good enough to walk to a shelf with. That needs every copy (D7), where in
the box each one sits (D20), and what the label on that slot reads now (D10).

---

## 2. Copies are fungible — D7 as amended

### 2.1 — What moved, and what it was doing wrong

`pushed`, `staged` and `live` were card states. A card wore one, so listing progress was an
**address**. Four of seven identical cards were sellable and three were not, for no physical
reason. The owner's ruling in D7: any 3 of 15 copies are live, and not 3 specific locations.

The three moved off the card and onto the SKU. `store/master.py:STATES` is
`(captured, identified, sold, retired, moved)`. `check_state` raises `UnknownState` for
`pushed`, `staged` and `live`. That refusal is the guard. A caller that reaches for
`set_state(key, LIVE)` gets an exception and never a per-position flag.

`store/master.py:Listing` holds `pushed`, `staged` and `live` as counts per SKU. `set`
assigns absolutely. `bump` moves by a delta. They are two methods so a caller must say which
it means. `join` reads `live` off the export and assigns it, because D8 and D11 put the
authority there. `emit` increments `pushed`, because two runs can push copies of one SKU and
the second must not erase the first.

### 2.2 — `Listing.held` excludes `live`, and that is not an oversight to tidy

`held` is `pushed + staged`. Do not "simplify" it to include `live`.
`pipeline/join.py:SkuMatch.add_to_quantity` already subtracts `live_before`, which comes
from the export's `Total Quantity`. Counting `live` again subtracts the same copies twice. A
SKU with 3 live, 6 copies on hand and a `Total Quantity` of 3 computes room for 0 and not 1.
It then under-lists by one copy, and nothing shows it.

The two numbers answer different questions. `live_before` is what TCGplayer says is for sale.
`held` is what TCGplayer holds that its live quantity does not report. `pushed` means only
that a CSV was written. After the import it is reported in `Total Quantity`, so `cli/resolve.py`
bounds the claim by `Inventory.copies_not_sold` and never trusts `held` alone.

### 2.3 — `live_positions` is a counting device, not an address

Do not delete `SkuMatch.live_positions` and `backstock_positions` as a leftover of the
per-position model. They are `uncommitted_positions` cut at `add_to_quantity`. The store
records how many copies are pushed and staged. Something must turn that count back into a
set that the join can subtract. It picks that many unsold copies in box-walk order. Any N
would do, so the choice is deterministic, and **nothing is written back** for the choice.

`cli/cmd_emit.py` walks `live_positions` to record `sku`, `condition` and `run` on each
copy. Those are facts about the physical object. It increments the SKU's `pushed` count,
which is a fact about the listing.

The rejected rule was "any non-zero count commits every copy". Seven copies with two staged
would commit all seven. `add_to_quantity` would then clamp to zero, and the SKU could never
list its uncommitted copies again. Counting gives the right answer: two committed, and the
rest still listable. `uncommitted_positions` is what keeps a copy from going out twice.

### 2.4 — The live estimate

A sale lowers the SKU's number at once, with no join between. Two fields hold it.
`Listing.live` is the last reading of the export, and `live_as_of` is when it was read.
`sold_here` counts sales made here since that reading, and `sold_here_at` stamps the newest.
`Listing.live_estimate` is the reading less the counter, floored at zero. D115 records the
ruling.

The export stays the authority (D8, D11). `observe_live` takes a reading only when the
export was read later than the stored reading. `sales_pending` decides which counted sales
survive a reading. It is all or nothing. A file that cannot be shown newer than the newest
counted sale clears no sale. So an older export is adopted for its figure, and the counter
survives it. A sale never stamps `live_as_of`, because a sale observed nothing about
TCGplayer.

The counter is floored only in `live_estimate`. Sell, sell, undo and undo return exactly to the
start, even where every middle estimate read zero. Holding the count back until a join would
make the app disagree with the shelf in front of the operator.

---

## 3. The box is an object — D20

### 3.1 — A box has no seal and no capacity (D299)

D20 once sealed a box to freeze its capacity, so that "#40 of 250" stayed true. D58 made
every number count the cards on hand. The capacity then divided nothing, and D299 removed the
seal. `store/master.py:Box` carries `box`, `bid`, `name`, `sections`, `section_names` and
`created_at`. It has no `state`, no `capacity` and no `closed_at`. `PUT /boxes/<box>` refuses a
body that sends `state`. `POST /boxes` accepts no capacity.

Old history can still hold `box_closed` and `box_reopened` lines. Nothing writes them now.
Sold cards do not shrink a box. D10 makes their gaps permanent, and `next_index` is a
high-water mark.

### 3.2 — One denominator, two screens

A card's `place` block and each row of `GET /boxes` need the same box total. Both take it
from one renderer. A box that said "40 of 250" on one screen and "40 of 53" on another would
be the second-renderer failure with a number in it. The total is the cards on hand (D58).

### 3.3 — Three things a human decides, and the one that is not among them

`PUT /boxes/<box>` takes `name`, `sections` and `section_names`. The box number is not among
them. A change of number is a renumber, which D10 forbids. Every position key, every photo
directory and every label a person has read is built from that number.

### 3.4 — Capture does not need a registry entry

`allocate_capture` calls `ensure_box`. It creates an unnamed, undeclared box when the registry
has never seen the number. Requiring registration would make the registry a second thing to
keep in step with the cards. The v1 migration produces the same shape, so the two paths cannot
diverge.

---

## 4. Sections are per-box — D10 as amended

### 4.1 — The index is the identity; the label is a view

**The index is assigned once, survives a sale as a permanent gap, and nothing renumbers it.**
Section and Card are a *rendering* of that index against the box's current divider layout.
Moving a divider relabels every card behind it and touches no index.

D58 took the seam to its end. The rendering counts the cards in the box and not the slots.
A departure closes up behind it, and `Card 17` is the seventeenth card that a person can
count. The section boundaries are mapped into the same space, so both halves of the label
stay countable.

A box that declared no layout renders as one undivided section. There is no default section
size. The migration writes an empty layout for every box it finds.

`check_sections` refuses a bad layout and never repairs it. A layout is the indices at which
each section starts. So the first is 1. The list is sorted, because an unsorted list makes the
section depend on write order. It is unique, because two dividers at one index make a section
with no cards. A silent sort would relabel a box without a word.

### 4.2 — The migration is asserted against literal strings, and that is the point

A formula asserted against itself proves nothing about the cards already on a shelf. If the
migration is wrong, every position label in a real inventory shifts at once. The only symptom
is a person who opens the wrong slot weeks later. So `harness/tests/t7_store_and_seams.py`
asserts the migrated labels as strings, such as `Box 1 · Section 1 · Card 25`. A
`join.Position(...)` call there would pass under any layout rule, including a wrong one.

### 4.3 — The other direction, in the same test, on purpose

T7 asserts `GET /inventory`'s decorated rows against `join.Position` and never against a
literal. The point of the decoration is that one renderer draws a position label. A literal
there would go on passing while the app and the pipeline disagreed about where a card is. Two
assertions, two forms, two arguments. Do not merge them into one convention.

### 4.4 — Boundaries are freely editable, and what that costs

The owner chose free editing over freezing a section once a card sits in it. A wrong layout
must be correctable. A label was never printed on anything. A frozen layout cannot describe a
box that a person re-divided.

**The cost:** a mis-tap relabels a filled box and nothing flags it. The Fulfiller then walks to
the wrong slot. The mitigation is a `resectioned` history event that carries both layouts. It
is not a restriction on the edit. If the failure happens, add a confirm on an edit that moves
a divider with cards behind it. Do not return to freezing.

---

## 5. `_Places` — one renderer, and the failure that shaped it

### 5.1 — One corrupt record blanked every label in the inventory

`server/capture_server.py:_Places` builds the `place` block for four routes. It is made per
request and never held between them. `Inventory.box_fill` is O(cards), and rendering thousands
of cards with an uncached total is millions of coercions on the route that the app polls.

The box total is a whole-box scan. It raises `BadPosition` on any record in the box, and not
only the record being rendered. Letting that escape once cost every neighbor its label. T7
caught it. **A label needs only its own two integers and the box's layout.** Only the total
needs the scan. So the two degrade separately. A bad neighbor costs the box its total
(`box_total` 0 and `fraction` null, which the app draws as "no fraction"). It costs nobody
their position.

### 5.2 — What does not degrade, and why

`BadSections` is not caught. A layout that will not validate means that the section and card
numbers are unknown, and no label is the honest answer. Collapsing that into the neighbor
case would mean refusing to draw a whole box over one bad row. Or it would draw a section
number against a rule the box no longer follows.

`fraction` is 0-based. Card 1 of 250 is 0.0 of the way in. It answers "how much of the box do I
pass before this card". It is null on an empty box, because a 0.0 would draw a marker at the
start of nothing. It goes out raw and unrounded. Formatting it is the app's job.

---

## 6. The routes

### 6.1 — `GET /search` answers with a SKU and its positions

`do_search` finds candidate cards with an FTS5 query (`cards_fts`, kept in step by triggers
inside `Store.write()`). `_match_rank` ranks each candidate as an exact number, a name prefix
or a substring. Each surviving SKU is then rendered whole by `positions_for_sku`, in box-walk
order. **Building the copy list from the matched cards would be a wrong answer.** A query that
matches on `set_hint` matches only the copies from that stack. A group with three of five
copies is worse than no search.

A group's rank is the best rank of any copy. Copies of one SKU can differ in `set_hint` and in
`name`, because a re-identify writes what the model read that time.

### 6.2 — The group is the SKU, whole

The group includes copies that did not match the query. That is the deliberate result of 6.1.
A SKU with no listing record answers zeros, and not null. "Nothing has been emitted" is a
fact. A screen then draws 0/0/0 without telling "not listed" from "the server did not say".

There is no `cap` field. D7's standing cap is deleted, so `listable` is what the box holds.
`app/src/CardLocations.tsx:headroom` reads it.

### 6.3 — Unidentified cards group under `null` and sort last

They have no SKU and no listing, so the group is a bag of cards and not a product. Its scalar
fields answer null unless every card agrees (`_agreed`). It sorts last, because an
unidentified card is not the one being looked for when a real match is on the screen. It is
**never dropped**. A card the pipeline could not name is the card an operator searches for.

A copy whose position will not render still appears, with a null `place`. `has_photo` comes
from `photo_for`, the lookup that the photo route serves from. It is not `bool(card.photo)`.

### 6.4 — `GET /boxes` is the union, not the registry

`do_boxes` lists every box in the registry and every box a card names. A box that holds cards
and is missing from the registry would otherwise be invisible on the one screen that could
repair it.

**Nothing in a box row may raise on bad data.** A `sections` list that will not validate leaves
the section detail empty, and the raw list is still echoed. A card record that will not coerce
takes `fill`, `next_index` and the spans to null, and the counts still report what could be
read. `cards` counts records that name the box. `fill` is the high-water mark. Both are
wanted: a box with 53 records can have a fill of 60, and the difference is the holes.

### 6.5 — `POST /boxes` refuses an upsert; `PUT /boxes/<box>` adopts

`ensure_box` is idempotent, which is right for capture. A photo must never be refused because
its box is known. A create that quietly succeeded against an existing box would let a screen
rename box 3 while the operator thought they added one. So `POST` refuses with `box_exists`.

`PUT` adopts a box that the registry has never seen but that cards already name. `GET /boxes`
lists that box, and a refusal would leave a dead rename control on the row. `box_not_found`
stays for a number that nothing in the store has seen. A duplicate name refuses with
`name_taken`, because a name is how a box is addressed. A request to `POST /boxes` that names
no number gets the lowest free one from `next_box_number`.

### 6.6 — Rename is logged

`store/master.py:set_name` appends `box_renamed` with `name_from` and `name_to`. Both `PUT
/boxes/<box>` and `ensure_box` call it. A name is an address. A rename relabels every card in
the box, as a moved divider relabels every card behind it. An unlogged rename would leave no
record of what the box was called.

---

## 7. The shared components

### 7.1 — The position bar answers a question the label does not

`Box 3 · Section 2 · Card 17` names a slot. It does not say where the slot sits in the box.
The slot can be at the front, or two thirds toward the back. That decides whether to lift the
lid or dig. The Fulfiller needs it more, because he walks to a box he did not fill.

**It is a drawing, never a claim.** It computes widths and a percentage from numbers the
server sent. Nothing in it decides where a divider is. Do not tile a bar from one section's
width: `section_end - section_start + 1` laid end to end assumes uniform sections, which D10
makes wrong. Dividers go where the operator put them.

With a `place` alone, `app/src/PositionBar.tsx` draws the three runs the record states: before
this section, the section and after it. Every tick is a boundary the server sent. Given a
box's section detail (`sections`), it draws the real tiling. The bar hides an empty section.

There is no travelled-distance fill, because no token exists for a quiet fill. When no token
fits what a component needs, argue for a new token in `docs/DESIGN.md`. Never paint a literal
in a component.

### 7.2 — The card locations panel: one core, two skins

`app/src/CardLocations.tsx` serves both personas with one component: same data, same order,
same actions, same tokens. A second component would double the surface. The day the two drift
is the day the Fulfiller's screen shows a card the owner's does not.

The owner's skin speaks the pipeline's vocabulary, so a person can grep what they saw. The
Fulfiller's skin may not. The banned-word list forbids SKU, CSV, import, sync, batch, queue and
staged, and his skin shows no machine string. Both rules hold by construction. The pipeline's
words are read only inside owner branches. His state line is a lookup with a safe default,
so a new store state is not the first machine string he sees.

There is no copy state to filter a sell control on. The count of what is for sale comes from
the group's listing counts and never from the copies. A version that looked for
`state === 'live'` would find none and offer nothing.

### 7.3 — The debounce lives beside the request, and only one file may spend it

`app/src/useSearch.ts` holds three rules. An empty query asks nothing. A query waits out the
debounce (`SEARCH_DEBOUNCE_MS`, 200). An answer to a query that is no longer current is
discarded. Spread across two files, the rules drift, and a screen shows the results for `pika`
under the word `pikachu`. `SearchField.tsx` defaults its own debounce to zero. Two timers in
series would be most of a second of a screen that does not change.

`loading` is true through the debounce and not only through the fetch. It answers whether the
screen shows an answer to what is in the box. During the debounce it does not.

The 200ms value is an assumption, marked as one at the constant. Unmeasured: how it compares
with the store's latency. The `/` hotkey is owner-side only. The Fulfiller's screens are touch
and register no key.

### 7.4 — Nested surfaces eat a constraint silently

`docs/DESIGN.md` requires a card photo of at least 320px on its short edge in the Fulfiller's
pull. A group drawn as a bordered surface with each copy inside as a second bordered surface
left the photo at 227px at 375px wide. Two nested boxes cost 96px of padding. The fix is
contextual. In that view the group gives up its own box and the parent's gap spaces it. The
copy keeps its box, because the copy is the thing being chosen. Under one breakpoint the photo
bleeds to the copy's padding edges.

Both stylesheets were correct alone, and only a browser measuring a rendered pixel could tell.
That is `make design-check`, which is not on the commit path.

---

## 8. The screens

### 8.1 — The owner's search-and-sell, and the objection it overturned

`#/inventory` records a sale. The argument that said it never would stays here, because a
screen that does the thing needs a record that someone thought about it.

The objection: the sale write belongs to the Fulfillment view, which carries the guards that
`docs/DESIGN.md` asserts there. Those are photo-confirm before each pull, an undo window on
every mark-sold, and no reachable destructive action. A sold button on a dense owner table
would be an irreversible-looking write with neither guard.

**Answer 1: the guards belong to the write, and not to a view.** Any screen that records a
sale needs them. D57 ruled that on `#/inventory` the photo half is answered by the card band
(D38), which draws the selected copy's photograph beside the row. A confirm on a reversible
action is banned. So the sale writes on one press. The undo is doubled: the copy row's slot
becomes `Undo` for the window, and the receipt keeps its own. Stepping the walk unmounts the
rows, and the clock does not stop for that. The sale route answers `restores_to`, so a caller
knows whether an undo can be offered.

**The rule for any new sale path:** bring the guards. If the screen already satisfies one,
argue that in a decision entry. A path that arrives with neither is refused.

**Answer 2: the server refuses the race.** Two devices cannot disagree about which copy went.
The second sale comes back `already_sold`, a receipt for a card that leaves your list. No undo
is offered, because it would reverse the other device's real sale.

There are two sale paths. One is the owner's sale on `#/inventory`. The other is an order's
pass through the drawers, `POST /orders/pull` from `#/orders`, a card at a time. The walk
stands the operator under the copy's own photograph before anything is pressed, so the photo
half is answered as D57 answers it. Every copy carries its own `capture_id`. A slot whose
occupant changed refuses `capture_id_mismatch` and never sells whoever sits there now.

### 8.2 — Box management

Box management is owner-side, and the Fulfillment floors do not bind. `BoxOps.tsx` speaks the
store's vocabulary on purpose. There is no `#/boxes` route (D31, one owner-side view).

**Re-read after every write.** Every write route answers with the box row it wrote. The
screen does not patch that answer into a local list. Boxes are counted in handfuls, and the
read is cheap. A screen that merges a response into held state holds a second copy of state
that D13 keeps once, on the Mac.

**One write at a time.** `Store.write()` takes the file lock per call. Two edits issued
together stack against the lock and can return out of order.

### 8.3 — The Fulfiller's search: a way in added, none taken away

The Fulfillment list was a haystack that he searched by eye. The store answered first: 229
cards, 176 with no name recorded, with no photo on the row. There was nothing to search by
eye. So a `SearchField` sits above the list. The list stays beneath it. Typing narrows it.
Clearing gives back the box-walk list. A search screen that he navigates to and from was
declined. **Nothing he can do may stop working, because nobody has watched him do any of
it.** A flow with no instrument is a flow to add to and never to replace.

The server groups. The owner's screen pulls the whole store and groups in the browser, which
is wrong for this one. **Every copy is its own card** in his skin, with its own photo,
position label, position bar and action. Copies are fungible, so he walks to the nearest
slot, and every option carries the same information.

The cost: a card photographed ten minutes ago and not yet identified is on his list under a
no-name sentence. That is D7's answer. Nothing distinguishes it physically from the copy
beside it. It is the first thing to watch when a real order is pulled.

---

## 9. D28's layout half — the list stops moving

### 9.1 — The photograph is the one unknown height

The review queue's photograph is the one thing on that screen whose height is not known
before it draws. The next card's image was unloaded at the advance, so the candidate rows
jumped up and dropped back when it decoded. The answer that a finger writes there cannot be
taken back, because `store/queues.py:Queue.upsert` refuses to re-queue a cleared position.

The fix is two parts. The stage reserves its height (`--rv-photo-h` in
`app/src/ReviewQueue.css`), and `ReviewQueue.tsx` prefetches the next card's image. A photo
wider than it is tall leaves dead space above the label. That is the price of rows that do
not move. The rig's Cam Link hands the browser a landscape frame, so the capture-time
rotation setting exists to stop producing those frames (D13).

### 9.2 — What is not reserved

The sentence above the candidates is prose. One line for most reasons, two for
`set_ambiguous`, and each line moves the rows below it by 26px. Reserving it would spend
vertical budget for a line that is usually absent. That 26px is known and explained. It is not
a second bug. Unknown: whether the current stage still shows the same 26px, because the screen
has been reworked since the measurement.

---

## 10. D26, D29 and D58 — ratified here, all built

All three are built. D26 is the state `retired`. D29's group answer is
`server/capture_server.py:do_review_group_answer`. D58's gap convention is `neighbors` and
`section_gaps`, rendered per card. This section keeps the argument each ruling rests on.

### 10.1 — D26's state, and the name collision

`retired` is a terminal card state, `sold`'s sibling. A card is pulled out, damaged, lost or
given away. It keeps its record and its permanent gap. It carries a reason from
`RETIRE_REASONS`: `pulled`, `damaged`, `lost` or `given_away`. The sale route refuses a
retired card, so `_state_before_sale` never meets one.

**The name is `retired` and never `removed`.** `removed` is a history event name. Undo appends
it when it deletes a record and releases its position. The server holds that no history event
name is a member of the store's states. `_state_before_sale` and `_state_before_retirement`
scan back for the last event that names a state, and an event name must be inert to them. A
state named `removed` would make an old undo event parse as a state. A reversed sale could then
restore to `removed`. T7 asserts that the two sets are disjoint.

### 10.2 — D26's re-shoot in place

Undo reaches only the newest capture. A bad photograph found late needs another remedy. The
operation is not a delete. It replaces the photo and sidecar at an existing position. The
record, the label and the allocator stay untouched. That shape is what keeps it compatible with
D10.

Two adjacent cases are out of scope: a returned or cancelled sale, and a single damaged copy
among several. D7's fungibility ruling sharpens the second. A damaged copy is the one copy
that is not interchangeable.

### 10.3 — D29's group answers

One systematic fact about the rig's lighting can queue many cards for one reason. The screen
groups and filters always. **A group write needs two conditions.** Every entry shares a
reason code. Every entry offers exactly one candidate row, and every row carries the same
condition string. Anything looser is a bulk write over cards that a human has not compared,
which D4 forbids. The shared SKU is not required, because different cards are different
catalog rows. A group write still shows the photographs it answers for.

`do_review_group_answer` validates every position first, and then writes all of them inside
one `Store.write()`. A refused group changes nothing.

### 10.4 — D58's gap convention

**D58 overtook this section.** A card's number counts the cards in the box, so no gap is left
to hold a marker. The digital half is built. Every located `place` block carries `neighbors`
(the nearest non-terminal records, so a sold card is never a landmark) and `section_gaps`
(terminal records inside the section). Counting records and not indices means that an
unallocated tail is not a gap. A screen draws "between Mantine and Thievul · 2 slots in this
section are empty". One corrupt record nulls the sentence store-wide, and no possibly-wrong
neighbor is named.

Unknown: which physical marker, if any, the Fulfiller leaves in an emptied slot. It is the
owner's open item, and no record of a ruling exists. A box audit would close the loop. It
counts what is in a section and compares it to the record. No code does that today.

---

## 11. D27 and D28's undo half

**D27, session state.** The ban on browser storage is about *inventory*. D13 puts one truth on
the Mac. It never covered the capture screen's own scratch state. One key stays in
`sessionStorage`, the in-flight capture id, because a reload during a halt would make a
lost-response ambiguity unresolvable. D10's high-water mark would then hand the burned position
to the next card. D142 moved the other settings to `deviceMemory.ts`. Trigger mode is not
stored (D19). An armed machine that survives a reload is the automatic act that D19 refuses.

**D28, the undo.** Pressing a digit on the review screen writes a SKU and a condition onto a
real card. `Queue.upsert` refuses to re-queue a cleared position, so an answer outlives the
question. The screen had no undo. Mark-sold, which is reversible, had a confirm, an undo
window and a `restores_to` check. The irreversible action had fewer guards than the
reversible one. `store/queues.py:Queue.reopen` is the one door back. It refuses anything that
is not present and cleared. Every entry that the answer cleared is reopened, because a
reversal of one of two would leave the card half-answered.

The window is the screen's, and no clock lives in the store. A deadline enforced in the store
would fail when the store was slow to lock. The rule that D28 reopens is `docs/DESIGN.md`'s
no-acknowledgement rule. It leaned on "undo covers the mistake", and undo did not exist there.
A confirm would double the keystrokes on the screen where the owner spends the most hours.
**Rejected:** a modifier or an Enter to confirm. One key per card is the property to keep.

---

## 12. What this step does not do, and what nobody has measured

- **It closes no gap in the review queue's price bands.** `docs/DESIGN.md` owes that
  measurement. It needs a mixed-value lot.
- **It adds no order feed.** The Fulfiller's search is a way into a haystack. It does not say
  which cards an order wants.
- **Nothing here was used by the person it is for.** D5 says that a flow which needs
  explaining twice must be redesigned. Its only instrument is a retired, non-technical person
  who fills a real order.
- **The search debounce, the reserved photo height and the position bar's density are
  judgements.** Each is marked at the place it is set.

## 13. What a later session must not undo

- **Do not put a listing stage back on a card.** `check_state` refuses the three that left.
- **Do not "simplify" `Listing.held` to include `live`.** Section 2.2.
- **Do not delete `live_positions` as a leftover address.** Section 2.3.
- **Do not rewrite the migration's label assertions as `Position` calls.** Section 4.2. The
  opposite convention in the same file is also deliberate.
- **Do not accept a capacity or a seal on a box.** D299, section 3.1.
- **Do not let the whole-box scan back inside the label path.** Section 5.1.
- **Do not tile a position bar from one section's width.** Section 7.1.
- **Do not add a sale path without both guards.** Section 8.1 has the rule and D57's
  narrowing of it. On `#/inventory` the card band answers the photo half, and the undo is
  doubled.
- **D26's state is `retired`, never `removed`.** Section 10.1 has the collision.
