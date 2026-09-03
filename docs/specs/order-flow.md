# Order flow, boxes, and search — execution spec (build-order step 13)

Written 2026-08-23, after the code, which is the wrong order and is said plainly rather than
disguised. `docs/specs/capture-server.md` and `docs/specs/capture-app.md` were both written
before their step and read forward; this one was written behind a step already half-landed,
because `docs/GATES.md` named step 13 and pointed at nothing. What that costs is that no
decision below was *made* here — every one was made in `docs/DECISIONS.md` or at a keyboard —
and what it buys is that the arguments are recorded while the evidence for them is still
warm. Read it as a spec in the sense the other two are: the reasoning, the rejected
alternative, and what a later session must not undo.

Where a section describes something that does not exist, it says so in its own heading.

---

## STATUS — 2026-08-23

Three different states are mixed together in this step and telling them apart matters more
than anything else in this file. A session that reads a ratified decision as a built feature
will go looking for code that is not there; a session that reads built code as a proposal
will rebuild it differently.

**BUILT AND VERIFIED.** Store schema v2 and the v1→v2 migration; `GET /search`, `GET /boxes`,
`POST /boxes` and `PUT /boxes/<box>`; the shared components — the position bar, the card
locations panel, the search field and the search hook; the owner's search-and-sell screen and
the Boxes screen; the Fulfiller's search; D28's layout half. T7 reaches the store and the
routes. `make docs-audit` is clean.

**RATIFIED HERE, BUILT SINCE.** D26 (`retired`), D29 (group answers over a homogeneous
queue) and D30 (the gap convention) were owner rulings with no code behind them when this
was written. All three landed by 2026-08-23; `docs/GATES.md`'s build-order step 13 names
them. Section 10 keeps each argument, including the name collision that bit D26.

**IN FLIGHT AS THIS WAS WRITTEN.** D27 (`sessionStorage` for the capture screen's own scratch
state), and D28's undo half, which landed underneath this file between its first draft and its
commit. Section 11 says what was true of the tree at one named moment and nothing more — a
status paragraph about work in progress is stale by construction, so it is scoped to a day and
should be read against the code rather than believed.

**WHAT HAS MET A REAL SHELF.** Nothing in this step has run a physical session. Gate B's 53
cards are behind every number quoted below — the queue measurements, the photograph
dimensions, the 229-card store the Fulfiller's search was built against — but that run
predates every screen in this file. The search box has never been typed into by the person it
is for, no box has been sealed on a real shelf, and no order has been pulled through the new
flow. Treat the whole of it the way `docs/GATES.md` treats T6's synthetic composites:
self-consistent over a wider range than the evidence covers.

### 0.1 — The rule this session runs under

`docs/specs/capture-server.md` section 0.3 documents how writing docs in this repo blocks
your own commit, and it is unchanged. The trap that matters most here is the same one
`docs/specs/capture-app.md` names: a path whose first segment is a real top-level directory
and which does not exist **blocks**. Sections 10 and 11 describe unbuilt things, so they name
them by their behavior and never by a file that has not been written.

---

## 1. What this step is, in one sentence

**Three decisions that look unrelated turned out to be one shape.** D7 says copies of a SKU
are interchangeable, D20 says a box is an object whose size is only known afterwards, and D10
as amended says a position's index is its identity while its label is a rendering. Each one
takes a thing the code treated as an address and demotes it to a view of something else:
a listing stage stops being *which four copies* and becomes *how many*; a box's denominator
stops being a constant and becomes a property of a box that may not know it yet; a section
number stops being arithmetic on an index and becomes a lookup against a layout a human
declared.

The search-and-sell flow is what all three are for. Somebody sells a card, somebody types its
name, and the answer has to be good enough to walk to a shelf with — which requires knowing
every copy (D7), where in the box each one sits (D20), and what the label on that slot
currently reads (D10).

---

## 2. Copies are fungible — D7 as amended

### 2.1 — What moved, and what it was doing wrong

`pushed`, `staged` and `live` were card states. A card wore one the way it wore `captured`,
which made listing progress an **address**: `cli/cmd_join.py` walked a SKU's positions,
filtered to staged copies and promoted the first N, so four of seven identical cards were
sellable and three were not for no physical reason whatsoever. The owner's words are on the
record in D7 and they are the whole ruling: *"if i have 15 of one copy and mark 3 as live,
it's any 3 are live, not 3 specific locations are live and 12 are backstock."*

So the three moved off the card and onto the SKU. `store/master.py:STATES` is now
`(captured, identified, sold)` and `check_state` **refuses** the three that left. That refusal
is the load-bearing half of the change: a caller reaching for the old `set_state(key, LIVE)`
gets an exception rather than silently getting a per-position flag back. Removing the members
without the refusal would have left the old model reachable by anybody who remembered it.

`store/master.py:Listing` holds `pushed` / `staged` / `live` as counts per SKU, with `at` and
`staged_at` stamps. `set` assigns absolutely and `bump` moves by a delta, and they are
separate methods so that a caller has to say which of the two it means — `join` reads `live`
off the export and assigns it, because D8 and D11 put the authority there; `emit` increments
`pushed`, because two runs can push copies of one SKU and the second must not erase the first.

### 2.2 — `Listing.held` excludes `live`, and that is not an oversight to tidy

`held` is `pushed + staged`. The temptation to "simplify" it to `pushed + staged + live` is
strong enough that the reason lives on the property rather than at the call site:
`pipeline/join.py:SkuMatch.add_to_quantity` already subtracts `live_before`, which it reads
straight off the export's `Total Quantity` column. Counting `live` again subtracts the same
copies twice. A SKU with 3 live, 6 copies on hand and a `Total Quantity` of 3 computes room
for 0 instead of 1, and under-lists by one copy from then on, forever, invisibly.

The two numbers answer different questions. `live_before` is what TCGplayer says is for sale.
`held` is what TCGplayer is holding that its live quantity does *not* report.

### 2.3 — `live_positions` survived, as a counting device rather than an address

This is the part most likely to be read as a leftover and deleted. `SkuMatch` still exposes
`live_positions` and `backstock_positions`, still computed by slicing the SKU's uncommitted
positions at `add_to_quantity`. On its face that is exactly the per-position model D7's
amendment removed.

It is not, and the distinction is in `cli/resolve.py`'s own words: the slice is **a counting
device and not an address**. The store records how many copies of a SKU are pushed and
staged; something has to turn a count back into a set the join can subtract, and it picks that
many of the SKU's unsold copies in box-walk order. Any N of them would do — that is the
fungibility ruling — so the choice is made deterministically, and **nothing is written back**.
`cli/cmd_emit.py` walks `live_positions` to record `sku`, `condition` and `run` on each copy,
which are facts about the physical object at that position, and increments the SKU's `pushed`
count, which is a fact about the listing.

The alternative that was rejected in the same breath is worth keeping: **"any non-zero count
commits every copy"**. Seven copies with two staged would commit all seven, `add_to_quantity`
would clamp to zero, and the SKU would never refill to D7's cap again. Counting is what gives
the right answer — two committed, room for two more, exactly what the per-position model
computed before it was removed.

### 2.4 — The optimistic decrement

A sale decrements the SKU's `live` count, floored at zero, before any join runs. That is an
estimate, and D7 is explicit that this is not a weakness of it: D8 and D11 already put the
authority in the export's `Total Quantity`, which `join` reads every run, so this number was
never a second source of truth competing with the export. A run corrects whatever drift a
between-run sale introduced — where its export was read AFTER the sale: the sale stamps
`live_as_of`, and an export older than that stamp is kept out rather than putting the sold
copy back (D87 amended).

The failure the ordering prevents is the opposite one. Holding the count back until a join
would make the app disagree with the shelf the operator is standing in front of, which is the
one place a number like this is actually read.

---

## 3. The box is an object — D20

### 3.1 — Capacity is retroactive because nobody knows a box's size when they start filling it

That sentence is the whole of the lifecycle and everything else in D20 follows from it.
`store/master.py:Box` carries `box`, `name`, `sections`, `state`, `capacity`, `created_at`,
`closed_at`. A box is `open` or `closed`. **While it is open it has no capacity**, and the
honest denominator is the fill so far — a screen saying "#40 of 53" has to also say *so far*,
because tomorrow it is 54. Sealing freezes `capacity` at the final high-water mark, and only
then does the owner's own sentence become true next week: *"if it just says oh the card is at
position 40, i'd rather it said it's at 40/250, so roughly a fifth of the way in you'll see
it."*

**A capacity field on box creation would have been the obvious design and is forbidden.** It
would be a guess, and every fraction drawn from that box would inherit it. `POST /boxes`
accepts no such field and never will.

**Sold cards do not shrink a box.** D10 makes their gaps permanent and `next_index` is a
high-water mark, so a sealed box's capacity never falls as its contents sell. **`capacity`
stopped being the denominator on 2026-08-30 (D58): a card's number counts the cards in the
box, so what every screen divides by is the cards on hand. This paragraph is still true of
`capacity`, and no longer true of the number anybody reads.** Re-opening sets
`capacity` back to `None` rather than leaving a stale number standing — an unsealed box with a
remembered capacity would be the worst of both, a denominator that looks frozen and is not.

### 3.2 — One denominator, two screens

`_denominator` in the capture server is one function because two places need the same answer:
every card's `place` block and every row of `GET /boxes`. A box that said "40 of 250" on one
screen and "40 of 53" on the other would be the second-renderer failure with a number in it
instead of a label, which is the failure this repo has now had twice.

It checks `capacity is not None` rather than trusting `closed` alone. `close_box` always sets
it, so the two disagree only in a hand-edited file, and the fill is the honest fallback there.

### 3.3 — Four things a human decides, and the one that is not among them

The Boxes screen has exactly four controls: what a box is called, where its dividers are,
whether the lid is on, and whether it exists yet. **Its number is not among them and there is
no control for it.** That would be a renumber, which D10 forbids outright — every position
key, every photo directory and every label anybody has read off a screen is built from that
number.

The sealing control **says the number it will freeze before it is pressed**. A button reading
"Seal box" alone would be a permanent decision taken against a denominator the owner would
have to go and find.

### 3.4 — A sealed box refuses before it computes an index

`allocate_capture` raises `BoxClosed` before an index is computed, so a refusal burns nothing.
Admitting one more card would make every fraction already drawn from that box wrong by one.

Capture still never demands a registry entry first: `allocate_capture` calls `ensure_box`,
which creates an unnamed, undeclared, open box if the registry has never seen the number.
Requiring registration would make the registry a second thing to keep in step with the cards,
and the v1 migration produces exactly this shape, so the two paths cannot diverge.

---

## 4. Sections are per-box — D10 as amended

### 4.1 — The index is the identity; the label is a view

These were the same sentence while sections were a global constant, and D10 had to be amended
to say which one it had always meant. **The index is assigned once, survives a sale as a
permanent gap, and nothing renumbers it.** Section and Card are a *rendering* of that index
against the box's current divider layout, so moving a divider relabels every card behind it
without touching a single index.

**D58 TOOK THAT SEAM TO ITS END ON 2026-08-30.** The rendering counts the cards in the box
rather than the slots, so a departure closes up behind it and `Card 17` is the seventeenth
card you can count. The index still never moves — that is what makes it a rendering — and
the section boundaries are mapped into the same space, so both halves of the label stay
countable.

`CARDS_PER_SECTION = 25` used to survive in `pipeline/join.py` as the default a box that had
declared no layout rendered with — kept because it made every label written before boxes
existed byte-identical. **It was deleted on 2026-08-29** (D10, amended by the owner): an
undeclared box renders as the one undivided section it physically is, and the labels of every
undeclared box moved once, deliberately, in exchange for never again naming a divider nobody
put in. The migration still writes an empty layout for every box it finds; what changed is
only what an empty layout renders as.

`check_sections` refuses rather than repairs. A layout is the indices each section *starts*
at, so the first is always 1; sorted, because an unsorted list makes the section a scan whose
answer depends on write order; unique, because two dividers at one index is a section holding
no cards. A silently sorted layout would relabel a box without saying so, which is precisely
the failure D10's amendment accepts the risk of and asks to be made visible.

### 4.2 — The migration is asserted against literal strings, and that is the point

**A formula asserted against itself proves nothing about the cards already on a shelf.** Every
label this repo has ever rendered came out of a global constant; sections are per-box now. If
the migration gets that wrong, every position label in a real inventory shifts at once, and
the only symptom is a person opening the wrong slot weeks later.

So `harness/tests/t7_store_and_seams.py` asserts the migrated labels as strings:

    Box 1 · Section 1 · Card 1
    Box 1 · Section 1 · Card 25
    Box 1 · Section 2 · Card 1
    Box 1 · Section 3 · Card 3

Writing those as `join.Position(...)` calls would have made the test pass under any layout
rule the code happened to adopt, including a wrong one. The literal is the only form that
carries the pre-migration fact into the post-migration world.

The mechanism that makes it true is one line of `Inventory.parse`: every box a card names gets
a registry entry **with no declared layout**. An empty layout renders with the default rule,
which is the rule those labels were written under.

### 4.3 — The other direction, in the same test, on purpose

T7 asserts `GET /inventory`'s decorated rows against `join.Position` itself and **never**
against a literal, and the reason is the mirror image of 4.2: the whole point of the
decoration is that one renderer draws a position label, and a literal there would go on
passing while the app and the pipeline disagreed about where a card is.

Two assertions, two forms, two arguments. A later session tidying them into one convention
would delete one of the two facts.

### 4.4 — Boundaries are freely editable, and what that costs

The owner chose free editing over freezing a section once a card sits in it. The argument for
it: correcting a wrong layout is the whole point, a label was never printed on anything, and
freezing leaves the model permanently unable to describe a box you physically re-divided.

**The cost is recorded rather than designed away: a mis-tap relabels a filled box and nothing
flags it**, and the Fulfiller walks to the wrong slot with no error to see. The mitigation is
a `resectioned` history event carrying both layouts — not a restriction on the operation,
which was the other option and which the owner declined. If that failure ever actually
happens, the fix to reach for first is a confirm on an edit that moves a divider with cards
behind it, not a return to freezing.

`PUT /boxes/<box>` moves the lid **last**, after any layout change in the same request, so a
box being declared and sealed together freezes its capacity with the layout already in place.

---

## 5. `_Places` — one renderer, and the failure that shaped it

### 5.1 — One corrupt record blanked every label in the inventory

This is the most useful thing found while building this step and it should outlive the fix.

D20's sentence is "#40 of 250 · 16% in", and every part of it after the 40 is a property of
the **box**: its layout decides the section, its capacity or its fill is the denominator, its
name is what the operator calls the thing on the shelf. Four routes needed that block, so one
renderer builds it — instantiated per request, never held between them, because
`Inventory.box_fill` is O(cards) and rendering thousands of cards with an uncached denominator
is millions of coercions on the route the app polls.

The denominator is a **whole-box scan**. It raises `BadPosition` on any record in the box, not
only the one being rendered. Letting that escape cost every neighbor its label over one
corrupt row — on the route the app polls. T7 caught it.

**A label needs only its own two integers and the box's layout.** Neither is the scan's
business. Only "of 250" needs the scan. So the two degrade separately now: a bad neighbor
costs the box its denominator (`box_total` 0, `fraction` null, which the app already draws as
"no fraction") and costs nobody their position.

### 5.2 — What does not degrade, and why

`BadSections` is deliberately **not** caught. A layout that will not validate means the
section and card numbers themselves are unknown, and no label is the honest answer. That is a
different failure from a neighbor nobody can place, and collapsing the two would mean either
refusing to draw a whole box over one bad row, or drawing a section number computed against a
rule the box no longer follows.

The `fraction` is 0-based: card 1 of 250 is 0.0 of the way in, not 0.004. It answers "how much
of the box do I pass before I reach this card", which is the question a thumb asks, and the
first card needs no travel at all. It is null rather than zero on an empty box, because there
is no fraction of an empty box and a 0.0 there would draw a marker at the start of nothing. It
goes out raw and unrounded: formatting it to "16%" is the app's job, and rounding on the wire
would decide a precision for every screen that reads it.

---

## 6. The routes

### 6.1 — `GET /search` answers with a SKU and its positions

D7's map made visible. `positions_for_sku` and `copies_on_hand` had existed since the store
did and nothing served them to a screen, so "where are my four Eiscues" was answerable only by
reading `inventory.json`.

Matching walks every card once to find which SKUs answered; each surviving SKU is then
rendered whole by `positions_for_sku`, in box-walk order. **Building the copy list out of the
matched cards instead would be a second scan and a wrong answer**: a query matching on
`set_hint` matches only the copies from that stack, and a group showing three of five copies
because two were captured under a different hint is worse than no search at all.

A group's rank is the **best** rank any copy achieved, because copies of one SKU differ in
`set_hint` and can differ in `name` — a re-identify writes what the model read that time — so
one copy can match on a prefix while another matches on a substring.

### 6.2 — The group is the SKU, whole

Including copies that did not match the query themselves. That is the deliberate consequence
of 6.1 and not a leak.

Zeros rather than null for a SKU with no listing record: "nothing has been emitted for this
SKU" is a fact, not an absence — `emit` creates the record when it writes the row — so a
screen can draw 0/0/0 without having to tell "not listed" from "the server did not say".

`cap` comes from `pipeline/join.py:LIVE_QUANTITY_CAP` imported rather than restated, so a
screen's "3 of 4 live" moves if D7's playset does.

### 6.3 — Unidentified cards group under `null` and sort last

They have no SKU to aggregate on and no listing behind them, so the group is a bag of
individual cards rather than a product: its scalar fields answer null unless every card agrees.
Last, because a card the pipeline has not identified is not the one being looked for when a
real match is on the same screen. **Never dropped**, because a card the pipeline could not name
is exactly the card an operator searches for.

A copy whose position will not render still appears, with a null `place`. Dropping it would
answer a search with silence about a card that matched.

`has_photo` is a `stat`, not `bool(card.photo)`. The consumer is a browser deciding whether to
request the photo route, and that route serves from the derived path, not from the recorded
field — the two come apart in both directions.

### 6.4 — `GET /boxes` is the union, not the registry

Every box in the registry, plus any box a card names. The two agree in practice, because the
migration registers every box a card names and `allocate_capture` calls `ensure_box`; this is
the read that keeps agreeing if they ever stop. A box holding cards and missing from the
registry would otherwise be invisible on the one screen that could repair it.

**Nothing in a box row may raise on bad data** — `GET /status`'s rule applied to the screen
where a bad box is fixed. Two independent failures degrade separately: a `sections` list that
will not validate leaves the section detail empty while the raw list is still echoed, so the
operator can see what is wrong with it; a card record that will not coerce takes `fill`,
`next_index` and the spans to null while the counts still report what could be read.

`cards` counts records naming the box and `fill` is the high-water mark. **They are different
numbers and both are wanted**: a box with 53 records can have a fill of 60, and the difference
is exactly how many holes are in it.

### 6.5 — `POST /boxes` refuses an upsert; `PUT /boxes/<box>` adopts

`ensure_box` is idempotent and returns the incumbent, which is right for capture — a photo must
never be refused because its box is already known — and wrong for a create. A create that
quietly succeeded against an existing box would let the Boxes screen silently rename box 3
while the operator believed they were adding one. So `POST` refuses with `box_exists` and says
which route does the other thing.

`PUT` goes the other way and **adopts a box the registry has never heard of but that cards
already name**, because `GET /boxes` lists exactly that box and refusing would put a row on a
screen with a dead rename control on it. `box_not_found` is kept for the case it actually
describes: a number nothing in the store has ever seen.

Sealing a sealed box is a refusal rather than a no-op, because the alternative reading is that
the call re-froze capacity at a new fill. Re-opening an open box **is** skipped, because
logging a `box_reopened` event for a request that changed nothing is the no-op logging the
card correction route already refuses to do.

### 6.6 — What the box routes deliberately do not do

**BUILT 2026-08-25 — A RENAME NOW APPENDS `box_renamed`, AND IT LANDED WHERE THIS PARAGRAPH
SAID IT HAD TO.** `store/master.py:set_name` owns the event, so it is in the STORE's vocabulary
rather than the server's — which is exactly the objection below, discharged rather than worked
around. `PUT /boxes/<box>` and `ensure_box`'s silent rename both route through it, and the line
carries `name_from` and `name_to`. What retired the cost argument is D20 as amended: a name is
the ADDRESS now — the capture screen finds a box by name — so a rename relabels every card in
the box, exactly as a moved divider relabels every card behind it, and an unlogged rename would
leave no record of what the box used to be called. The paragraph below is kept as the record of
the era in which a name was only a label.

**A rename appends no history event, and that is a gap rather than a decision.**
`set_sections` logs `resectioned` and `close_box` logs `box_closed`; a name change logs
nothing, because the store has no event for it and inventing one in the server would put it in
the server's vocabulary instead of the store's. What it costs is small — a name is a label,
not a claim the pipeline spends money against — but it is a gap and is written down as one.

Related and worth knowing before it bites: the five box event names in the server are a
**mirror** of literals that live inside the store's own log calls, because that module exports
no constants for them. The tuple can drift from the strings actually written and only a test
comparing the two would notice. Naming them in the store is the fix.

---

## 7. The shared components

### 7.1 — The position bar answers a question the label does not

`Box 3 · Section 2 · Card 17` says exactly which slot and says nothing about whether that slot
is at the front of the box or two thirds of the way to the back — which is what decides
whether you lift the lid or dig. The Fulfiller needs it more than the owner does: he is
walking to a box he did not fill.

**It is a drawing, never a claim.** Everything in it computes widths and a percentage out of
numbers the server sent. Nothing in it decides where a divider is, and there is one place that
distinction had teeth:

> Given a single `place` block it looks like a full tiling is one line away — this section is
> `section_end - section_start + 1` cards wide, so lay that width end to end across the box
> and draw every divider. **That is exactly the arithmetic D10 as amended makes wrong rather
> than merely disallowed.** Dividers go where the operator physically put them; a uniform
> width is an assumption about a box nobody made, and a bar drawn that way would show dividers
> that are not in the box, at a glance, with no way to tell it had guessed.

So with a `place` alone it draws the three runs the record actually states — before this
card's section, the section itself, after it — and every tick is a boundary the server sent.
Hand it a box's section detail and it draws the real tiling, computed once, in the one place
the repo allows a layout to be computed.

**No travelled-distance fill**, and its absence is a decision. A bar filled from the front of
the box to the marker would read well and there is no token that means "quiet fill" — `hover`
is row hover only, `line` is the 1px hairline, `accent` has two jobs of which this is neither.
The lesson `on-accent` taught this repo is that the answer to "no token means what I mean" is
a missing token argued for in `docs/DESIGN.md`, never a literal painted in a component.

### 7.2 — The card locations panel: one core, two skins

`docs/DESIGN.md`'s "one system, two densities" applied to a component rather than a
stylesheet: same data, same order, same actions, same tokens. A second component was the
alternative and it is the one this repo has rejected twice — it doubles the surface and gives
two things to keep in step, and the day they drift is the day the Fulfiller's screen shows a
card the owner's does not.

**What the two skins may say is not a style preference.** The owner's screens speak the
pipeline's vocabulary on purpose, because being able to grep what you saw is worth more to the
person debugging a run than a consistent register is. The Fulfiller's may not: the banned-word
list forbids SKU, CSV, import, sync, batch, queue and staged outright, and his skin shows no
machine string at all. Both rules hold **by construction rather than by care** — the
pipeline's words are only ever read inside owner branches, so there is no path by which one
reaches him. His state line is a lookup with a safe default, so that a state added to the
store next year is not the first machine string he has ever seen.

**This component was built after D7's amendment, which makes the obvious implementation the
wrong one.** There is no state to filter a sell control on, no such thing as a copy that is
backstock, and the count of what is for sale comes off the group's listing counts and never off
the copies. A version that walked the copies looking for `state === 'live'` would find none at
all — that word is not a member of the store's states any more — and would silently offer
nothing.

### 7.3 — The debounce lives beside the request, and only one file may spend it

Three rules about asking the server are one decision and live in one place: an empty query
asks nothing, a query waits out the debounce, and an answer to a query that is no longer
current is discarded. Spread across a field component and a screen those three drift apart,
and the way you find out is a screen showing the results for `pika` under the word `pikachu`.

The field carries its own debounce knob and **defaults it to zero**. Two timers in series is
most of a second of a person watching a screen not change, and neither file would own the
number.

`loading` is true through the debounce and not only through the fetch. It answers "is what is
on screen an answer to what is in the box", and during the debounce window it is not — the
results still belong to the previous query. Starting it at the fetch would leave a stale
result sitting there looking settled for exactly the period a fast typist spends looking at it.

**200ms is an assumption and is marked as one** at the constant. Nothing has measured it
against the store's own latency, and `Store.write()` waits up to thirty seconds for the file
lock, so a search issued while `./pkmnscan identify` is running can be slow for reasons no
debounce affects. What would settle it is watching the owner use the screen with a real
inventory behind it — the same instrument every other unmeasured number in this app waits on.

The `/` hotkey is owner-side and its **absence** is Fulfiller-side, both deliberate. A global
key listener that steals `/` on a screen whose user has no keyboard is invisible surface with
no upside, so his skin registers none.

### 7.4 — The measurement that flattened the group: 227px against a 320px floor

`docs/DESIGN.md`'s constraints table requires a card photo at least 320px on its short edge in
the Fulfiller's pull. The card locations panel draws a group as a bordered surface with its own
padding and each copy inside as a second bordered surface with more. On the Fulfillment view,
which is already the panel, that was a surface drawn on a surface — and at 375px it left the
photo at **227px**, against a floor the table asserts and a browser measures.

Two nested boxes is 96px of padding on a 375px screen. The fix is contextual: the group gives
up its own box inside that view and is spaced by the parent's gap, while the copy keeps its box
because the copy is the thing being chosen between. Beneath one breakpoint the photograph also
bleeds to the copy's padding edges, which puts it back over the floor; the text inside keeps
its inset, because the photograph is the one element here whose size is a constraint rather
than a choice.

**It is a contextual rule rather than an edit to the component's own stylesheet.** That
component owns its own look, this raises and lowers nothing about the copies inside it, and the
owner's dense skin is untouched.

The finding that outlives the fix: **nested surfaces eat a constraint silently.** Nothing about
the markup looked wrong, both stylesheets were individually correct, and the only thing that
could tell was a browser measuring a rendered pixel — which is `make design-check`, and which
`docs/GATES.md` records is deliberately not on the commit path.

---

## 8. The screens

### 8.1 — The owner's search-and-sell, and the objection it overturned in writing

This screen writes now, and the argument that said it never would is **kept in the file rather
than deleted**. Overturning an argument by erasing it leaves the next session with a screen
that does the thing and no record that anybody thought about it. So the objection stands,
quoted, and each half is answered where it was made.

The objection was that the sale write belongs to the Fulfillment view, which earns it by
carrying the guards `docs/DESIGN.md` asserts on that view and only on it — photo-confirm before
each pull, an undo window on every mark-sold, no destructive action reachable at all — and that
a sold button on a dense owner-side table would be the same irreversible-looking write with
neither guard, plus a second place to perform one action.

**Answer 1: the guards were never properties of the view.** They are properties of a screen that
records a sale, and `docs/DESIGN.md` asserts them there because that is the view its constraints
table governs. Nothing in D5 says the owner may have the write without them. So this screen
carried both: the sale went through a panel showing the copy's own stored photo at its position
(D6) before anything was written, and every recorded sale leaves a receipt with an undo window.
The sale route answers `restores_to` precisely so a caller knows whether an undo can be offered
at all, and this screen reads it rather than offering one blind.

**THE PHOTOGRAPH HALF WAS RULED REDUNDANT ON 2026-08-30 (D57) AND THE ARGUMENT ABOVE SURVIVES
IT.** The owner: *"for my side i literally have the inventory image in front of me already, it
was redundant."* D38 gave this screen a card band drawing the selected copy's photograph at
449x627, so the panel was answering a question the screen had already answered — and
`docs/DESIGN.md` bans a confirm on a reversible action precisely to stop that. The sale writes
on one press now, and the undo half is DOUBLED rather than dropped: the copy row's own slot
becomes `Undo` for the window, and the receipt above keeps its own because the rows are
unmounted by stepping the walk and the clock does not stop for that.

**What is NOT weakened is the sentence this paragraph opens with.** The guards still belong to
the write rather than to a view; what moved is which guard this screen needs, on a screen that
already draws the photograph. Read §13's rule below with that distinction, which is the whole of
D57.

**Answer 2: the server already refuses the race.** The failure feared was two devices
disagreeing about which copy went. They cannot: the second device's sale comes back
`already_sold`, which is a receipt for a card leaving your list rather than an error, and no
undo may be offered because the undo would reverse the other device's real sale.

### 8.2 — The Boxes screen

Owner-side, and the Fulfillment floors do not bind. It speaks the store's own vocabulary —
fill, capacity, next index, sections — on purpose, because the person reading it is the person
who will compare it against `inventory.json` when something is wrong.

**One read, kept nowhere, re-read after every write.** Every write route answers with the box
row it wrote, and this screen deliberately does *not* patch that answer into a local list.
Boxes are counted in handfuls, the read is cheap, and a screen that merges a response into held
state is a screen holding a second copy — which D13 has exactly one of, on the Mac.

**One write at a time, and the reason is not politeness.** `Store.write()` takes the file lock
per call and waits up to thirty seconds for it, so two edits issued together stack against a
lock and return out of order — and one of them may be a seal, which is permanent.

### 8.3 — The Fulfiller's search: a way in added, none taken away

The Fulfillment view's list was written as a haystack he searches by eye, with the first real
order named as what would say whether that was acceptable. **The store answered first**: 229
cards, 176 of them with no name recorded, in box-walk order, with no photo on the row. There is
nothing to search by eye.

So the haystack got a search field over it, and the list beneath it is untouched. The shape is
the owner's ruling and not a default: a field above, the list kept beneath, typing narrows,
clearing gives him back the box-walk list he already had. A search screen he navigates to and
back from was declined for the reason that governs this whole view — **nothing he can do today
may stop working, because nobody has ever watched him do any of it.** A flow with no instrument
is a flow you add to rather than replace.

The server groups and this screen does not; the owner's screen pulls the whole store and groups
in the browser, which is right for a screen whose job is to show everything and wrong for this
one. **Every copy is its own card** in his skin, each with its own photo, position label,
position bar and action, so he walks to whichever slot is nearest — copies are fungible, so
that choice is his and every option has to carry the same information.

**What it costs him, stated rather than discovered**: a card photographed ten minutes ago and
not yet identified is on his list under a no-name sentence. That is D7's answer and not an
oversight — nothing distinguishes it physically from the copy beside it — but it is the first
thing to watch when a real order is pulled, because it is the one way this list is longer than
the old one.

**What would still settle it is an order feed**, and item 6 of the Gate B measurements in
`docs/specs/capture-app.md` section 10.2 is unchanged by any of this.

---

## 9. D28's layout half — the list stops moving

### 9.1 — 538px and back inside 50ms, under a finger

The review queue's photograph is the only thing on that screen whose height is not known before
it is drawn, and every card's candidate rows sat directly on top of it. The next card's image is
unloaded at the instant of the advance, so the rows jumped **up** to fill the gap and dropped
back when it decoded.

Measured at 1440x900 against the Gate B captures, one skip: the first candidate row's top went
911 to 373 within 5ms and back to 911 at about 50ms. **A 538px round trip under a finger already
travelling toward a digit** — and the answer that finger writes is one the queue will not let a
human take back, because `store/queues.py:Queue.upsert` refuses to re-queue a position a human
has cleared.

The fix is a reserved frame plus a prefetch of the next card's image. `min-height` rather than
`height`, so nothing is ever clipped: the image can only be as tall as the cap because its own
maximum is the same value, and an absent-photo panel that ran longer would grow the frame rather
than overflow it.

**What it costs**: a photograph wider than it is tall does not fill the box, and the difference
is dead space above the position label. Portrait is the rig's normal case and fills it exactly —
Gate B's frames are 2160x3840 and draw 305x540 in a 540px box — but D13 records that the Cam Link
hands the browser a landscape frame however the camera is mounted, so an un-rotated capture binds
on width, draws shorter and leaves the rest empty. That is the price of the rows not moving, and
it is paid on frames the capture-time rotation setting exists to stop producing.

### 9.2 — What is still not reserved, measured rather than assumed

The sentence above the candidates is prose: one line for most reasons and two for
`set_ambiguous`, and each line moves the rows below it by 26px. Against the 538px the photograph
was moving them, that is the difference between a hazard and a detail — and reserving it would
spend the same vertical budget the fold is already short of, to hold space for a line that is
usually not there. A homogeneous queue, which is what Gate B's was, does not vary at all.

Recorded so that the next session measuring this finds the 26px already explained and does not
go looking for a second bug.

---

## 10. D26, D29 and D30 — ratified here, all three built since

**All three are built.** D26 landed 2026-08-23 as `retired` (§10.1 tells it); D29's group
answer is `server/capture_server.py:do_review_group_answer`; D30's gap convention is
`neighbors` and `section_gaps`, rendered per card. **This heading read "Ratified and NOT
BUILT" until 2026-08-30**, and the paragraph under it said none of the section was done —
false for over a week, in a file `CLAUDE.md` tells sessions to read as settled.

What the section is now is the argument each ruling rests on, kept because the reasoning
outlives the build. §10.1's name collision is the part to read before touching the state
tuple; it is still live.

### 10.1 — D26's state, the name collision, and how it resolved

**RESOLVED 2026-08-23: the owner renamed the state `retired` and it is built.** The collision
this section predicted was real and was settled exactly the way it recommends below — the
history event kept its on-disk name, the state got its own word, and the sale route now
refuses a retired card so `_state_before_sale` can never legitimately meet one. The analysis
is kept because it is the argument the rename rests on.

`removed` is a terminal card state, `sold`'s sibling: a card pulled out, damaged, lost or given
away, keeping its record, leaving its gap permanent, carrying a reason
(`pulled | damaged | lost | given_away`). It costs less than when it was first written, because
D7's amendment has just moved three states off the card, so the states tuple it joins is
narrower than the one it was proposed against.

**Whoever builds it must read this paragraph first, because nothing else in the repo says it.**
`removed` is already taken. The capture server uses it as a **history event name** — it is what
undo appends when it deletes a record and releases its position. The server's own comment states
the invariant: not one of its seven event names is a member of the store's states, because
`_state_before_sale` is the only reader of the history file and it scans backwards for the last
event naming a state, filtering against those states so that an event name is inert to it. T7
asserts the two sets are disjoint.

Adding `removed` to the states tuple **breaks that invariant directly**. An undo event from
months ago would suddenly parse as a state, and a reversed sale could be restored to `removed`.
Nothing at import time will catch it; the T7 disjointness case will, which is exactly what it is
for. The resolution is a decision, not an implementation detail — rename the state, rename the
event, or narrow what the history reader will match — and it is the owner's to make.

### 10.2 — D26's re-shoot in place

A bad photograph discovered late has no remedy: undo reaches only the newest capture, and the
current refusal tells the operator to correct the card on TCGplayer instead and leave the
position alone — advice that stops being true the moment D26 exists.

**The operation is not a delete at all**: replace the photo and sidecar at an existing position,
record untouched, position label unchanged, allocator never involved. That shape is what makes
it compatible with D10 rather than a reopening of it.

Two adjacent cases are named in D26 and deliberately left out of scope, so a later session does
not read the entry as having covered them: a returned or cancelled sale, and a single damaged
copy among several. D7's fungibility ruling **sharpens** the second rather than solving it — a
damaged copy is precisely the one copy that is not interchangeable.

### 10.3 — D29's group answers

Gate B's queue was 16 of 53, every one the same reason code, and detection agreed with itself
across every duplicate pair — both Thievuls, both Eiscues, both Pyroars. One systematic fact
about the rig's lighting, sixteen identical taps. The discarded pre-rotation run queued 45 with
one shared cause.

**Grouping and filtering, always. A group write only under both conditions**: every entry shares
a reason code, **and** every entry offers the same single candidate. Anything looser is a bulk
write over cards a human has not actually compared, which is what D4 exists to prevent. A group
write still shows the photographs it is about to answer for.

### 10.4 — D30's gap convention

**AND THE WHOLE SECTION IS OVERTAKEN BY D58 (2026-08-30):** a card's number counts the cards
in the box now, so there is no gap left to leave a marker in and the physical half never had
to be chosen. The digital half stays built and is unchanged. Read what follows as the
argument that produced it rather than as an open item.

**THE DIGITAL HALF IS BUILT (2026-08-23, later the same day):** every located `place` block
carries `neighbors` (nearest non-terminal records, so a sold card is never named as a
landmark) and `section_gaps` (terminal records inside the section — counting records, not
indices, is what makes an unallocated tail not a gap by construction). Rendered as "between
Mantine and Thievul · 2 slots in this section are empty" on the pull preview and both
CardLocations skins. One corrupt record nulls the sentence store-wide rather than naming a
possibly-wrong neighbor. **The physical half — which marker the Fulfiller leaves in an
emptied slot — remains the owner's open item**, and it is the retroactive one.

D10 makes a sold position a permanent gap and the Fulfiller creates one per order. Nothing has
ever told him to leave anything behind in the slot, and nothing teaches anyone to read a position
label: `Card 17` is the **seventeenth slot**, not the seventeenth card you can count. Once a
section has holes those two stop being the same number and every label in that section becomes
uncountable by hand.

**It is retroactive, which is why it wants settling before more sales happen.** A convention
adopted after fifty gaps exist cannot be applied to them.

Two halves, and only one is code. The physical marker is the owner's call and belongs in D30 once
made. The digital half is free and is the part this step could have built: a position rendered
with its neighbors and its section's gap count — "Card 17, between Mantine and Thievul · 2 slots
in this section are empty". Neighbors make a label countable again without anyone learning the
rule; the gap count says why the count came out short.

**The box audit is the check that closes the loop** — count what is physically in a section and
compare it to the record. Nothing has ever compared a physical box against the record, and D20's
fill and section accessors are what make it computable.

---

## 11. In flight on 2026-08-23

Scoped to a day on purpose. A status paragraph about work in progress is stale by construction,
so this one is dated and says only what was true when it was written; read the code, not this
section, for what happened.

**D27 — session state in `sessionStorage`.** The ban on browser storage is about *inventory*:
D13 puts one truth on the Mac so two devices cannot disagree about where a card is. It was never
about the capture screen's own scratch state, and reading it that way costs a real thing. Box
number, set hint, finish claim, rarity claim and the in-flight capture id are device-local and
meaningless anywhere else; they are component state today, so a reload loses all of them — and
the last one matters most, because a reload during a halt makes a lost-response ambiguity
permanently unresolvable and D10's high-water mark hands the burned position straight to the next
physical card. `sessionStorage`, never `localStorage`: a new tab is a new session, and nothing
about a shift survives closing the browser. **Trigger mode is explicitly not covered** — D19
keeps arming an act, and an armed machine that survives a reload is exactly the automatic-anything
that entry refuses.

**D28's undo half — it landed while this file was being written.** The layout half (section 9) was
built first and this was the outstanding piece; by the time this file was committed
`store/queues.py:Queue.reopen`, the server's reversal on the answer route and the client call were
all in the tree, with T7 cases behind the store method. The argument is recorded here anyway,
because it is the part that outlives the commit.

The problem it fixes: pressing a digit writes a SKU and a condition onto a real card, and
`Queue.upsert` refuses to re-queue a position a human has cleared — deliberately, so an answer
outlives the question — so there was no undo, no confirm and no acknowledgement. Meanwhile
mark-sold, which is *reversible*, gets a photo to confirm against, a two-step control, an undo
window and a pre-checked `restores_to`. **The irreversible action had fewer guards than the
reversible one, which is backwards.**

**That last sentence describes the OWNER's screen as it stood on the day, and D57 finished the
correction from the other end on 2026-08-30**: the sale is one press there now, with `Undo` in
the copy row and on the receipt. `#/fulfillment` keeps all four. Nothing D28 added was taken
back — the two entries close the same gap from opposite sides.

**The window is a hole punched in `Queue.upsert`'s refusal on purpose, not a softening of the
rule.** `reopen` is the one door back out and it is deliberately narrow: it refuses anything that
is not present and cleared, so the refusal still stands for everything outside the window. **Every
queue entry the answer cleared is reopened**, because a reversal that reopened one of two would
leave the card half-answered.

It reopens `docs/DESIGN.md`'s no-acknowledgement rule for this one screen, on grounds found inside
that rule: it is justified by "Undo covers the mistake", and on this screen undo did not exist, so
the rule leaned on something that was not there. Fixing the premise is the honest repair; adding a
confirm dialog would have doubled the keystrokes on the screen the owner spends the most hours in,
which is the thing the rule exists to prevent. **Rejected: requiring a modifier or an Enter to
confirm** — one key per card is the property worth keeping.

**Two things to check before treating it as finished**: that the review screen actually draws the
control (the last wiring step, and the exact shape of gap that took 7b several hours to notice —
`docs/GATES.md` step 7), and that the window has no clock living in the store, which D28 rules on
directly.

---

## 12. What this step does not do, and what nobody has measured

- **It closes no gap in the review queue's price bands.** `docs/DESIGN.md` still owes that
  measurement and it now has a precondition rather than a pointer: a mixed-value lot. Gate B's
  queue was $0.04 to $0.40 end to end, so the type scale was never asked to separate anything.
- **It adds no order feed.** The Fulfiller's search is a way into a haystack, not an answer to
  which cards an order wants.
- **Nothing here has been used by the person it is for.** D5's actual requirement — "if a flow
  needs explaining twice, redesign the flow" — still has no instrument but a retired,
  non-technical person filling a real order, and no order has been pulled.
- **The search debounce, the reserved photo height and the position bar's density are all
  judgements**, not measurements. Each is marked as one at the place it is set.
- **No box has been sealed on a real shelf**, so D20's whole lifecycle — the sentence that
  justifies the object existing — has been exercised only against fixtures and by hand.

## 13. What a later session must not undo

- **Do not put a listing stage back on a card.** The states tuple refuses the three that left,
  and the refusal is the guard, not a leftover.
- **Do not "simplify" `Listing.held` to include `live`.** It double-subtracts and under-lists
  forever, invisibly. Section 2.2.
- **Do not delete `live_positions` as a leftover address.** It is a counting device with nothing
  written back, and the alternative rule — any non-zero count commits every copy — stops a SKU
  refilling to the cap ever again. Section 2.3.
- **Do not rewrite the migration's label assertions as `Position` calls.** A formula asserted
  against itself proves nothing about cards already on a shelf. Section 4.2 — and note that the
  opposite convention in the same test file is also deliberate.
- **Do not accept a capacity at box creation.** D20, section 3.1.
- **Do not let the whole-box scan back inside the label path.** One corrupt record blanked every
  label in the inventory once. Section 5.1.
- **Do not tile a position bar from one section's width.** Section 7.1.
- **Do not add a second sale path without both guards** — **amended 2026-08-30 by the owner
  (D57), and the amendment is narrower than it looks.** Section 8.1 answers the objection by
  bringing the guards rather than dismissing them, and that reasoning stands: the guards belong
  to the WRITE and not to the Fulfillment view. What the owner ruled is that on `#/inventory` the
  photograph half is answered by the card band D38 put two inches from the row, so the sale is
  one press and the undo is doubled — in the copy row and on the receipt. **The rule for a THIRD
  sale path is unchanged**: bring the guards, and argue in a decision entry if one of them is
  already satisfied by the screen it would sit on.

  **The third path landed 2026-09-02, and it met that rule rather than going around it.**
  `POST /orders/fill` is how a card leaves inventory on the order walk this screen now hosts: one
  press records a whole order's envelope, every copy pulled and sold in one write. D90 is the
  entry, `docs/specs/order-pipeline.md`'s T6 is the build. Both guards came with it. The
  photograph is answered exactly as D57 answers it here, by the card band beside the row, because
  the walk stands the operator under the copy's own photograph before anything is pressed. **The
  undo is the receipt's alone rather than the doubled pair above**, and that is the one thing the
  envelope does differently: a fill sells every copy it wrote, so those rows draw the plain word
  `sold`, and a row-level Undo would reverse five copies from the slot of one. What it adds that
  neither sale path had is the aim check — every copy carries its own `capture_id`, and a slot
  whose occupant changed under it refuses `capture_id_mismatch` instead of selling whoever sits
  there now.
- **D26's state is `retired`, never `removed` — §10.1 has the collision that decided it.**
