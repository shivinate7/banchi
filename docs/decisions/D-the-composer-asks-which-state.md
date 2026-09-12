## D-the-composer-asks-which-state — The composer asks which state, a drawer is one narrowing of it, and the filter lives in the address

**The front door speaks in STATES and the room behind it spoke in DRAWERS.** `#/` puts one
ranked sentence on screen — *"412 cards are photographed and not identified"* — and links to
`#/runs`, whose first stage was headed `Which boxes`. The answer to the sentence the operator
had just read was not among the options. Stage one now asks which state, with that state ticked
by default, and the drawer becomes one of three ways to narrow it.

### The two halves that disagreed, and neither was wrong on its own

`app/src/standing.ts` reads `ServerStatus.states.captured`, which is store-wide, and its own
comment says why it names no box: *"`BoxRecord` carries no per-state counts, and attributing a
store-wide figure to one drawer would be a sentence the data cannot support."* That is correct
and stays.

`RunsComposer.tsx` opened on `TITLES.boxes = 'Which boxes'` over a strip of every drawer in the
registry. That was correct too, for a screen reached from `#/inventory`'s box walk, which is
where the panel lived until D39 moved it.
**What made the pair wrong was the link between them**, and the link was added later than
either.

### `#/pricing` had already settled the vocabulary, and two of its four doors had no press

`server/pipeline_routes.py:_unreachable` answers `{captured, in_review, unjoined, reallocated}`
— four states, store-wide, each with a door to the screen that can move it — under a docstring
saying they are *"named rather than left out (`CLAUDE.md`: never silently drop a card)"*.
`in_review` reaches `#/review` and `unjoined` reaches a run's join step.
**`captured` pointed at a screen that could not express it**, and `reallocated` still points at
a command.

So this is not a new vocabulary. It is the one the product already speaks, given a press.

### The rule

**The scope is a STATE plus up to three narrowings, and the narrowings intersect.** `captured`
is the only state this composer can act on; the narrowings are the drawers, the games and the
newest sitting. Nothing narrowed means every card in the state, which is what the primary row
says out loud and what it is pressed to restore.

**A drawer tick alone produces a WHOLE-BOX leg, and that is the load-bearing detail.**
`runSelection.ts:legsFor` asks one question — does this selection cut WITHIN a drawer? — and a
drawer tick does not. So ticking box 4 sends `{box: 4}` with `indices` absent: byte for byte
the request that press has always sent, in one click. A game or a sitting cuts ACROSS drawers,
so each leg carries its matching indices, which is the shape `#/inventory`'s handoff has
produced since D39. **Nothing new goes on the wire.**

**A ticked drawer holding nothing still gets its leg.** The operator asked for that drawer; the
free preflight is the thing entitled to answer *nothing to send*, and it does, with the figure
on screen. Dropping the leg would make a drawer they ticked silently absent from the cost stage.

### "Nothing is scoped on arrival" is retired, and what protected the dollar is untouched

`Runs.tsx` refused to default the scope, on the ground that *"a box chosen for the operator is a
box they did not read, and the next press after it spends money."*

**The first half of that is still enforced: no DRAWER is ever ticked for them**, and
`run-panel.spec.ts` asserts that as an attribute on every tile rather than as an absence. What
is ticked is the STATE, which is not a choice made on the operator's behalf — it is the fact the
front page put on screen and sent them here to act on.

**What actually protects the dollar is D33's money gate and it is unchanged**: the free
preflight has to answer before the confirm EXISTS, the confirm carries the figure in its own
label, and the estimate is void the moment the scope moves. A default scope cannot spend
anything; it can only be the thing a free press is run over.

**One state is now unreachable and that is a gain.** Unticking the last drawer used to leave an
empty cart and a disabled `Next` — the only way to have this dialog open with nothing to do. It
now falls back to the state. There is no press on stage one that reaches "nothing selected".

### The confirm counts cards

It read `Spend $X and identify N cards in 3 boxes`. D33's ruling is that this figure is *"the
number the operator agrees to spend"*, and **a drawer is not what is being bought** — three
drawers holding nine cards read as a bigger press than one drawer holding four hundred. The
drawer count moves to the line under it, where it is a fact about WHERE rather than HOW MUCH,
and the per-leg list above it is unchanged.

`server/pipeline_routes.py:_total` still answers `"boxes": len(answers)`. **No client reads it**,
and it is left alone deliberately: that file is the one part of the server that can spend money
and it was being edited on another branch while this landed.

### Where the figures come from, and why that is not the arithmetic `server.ts` forbids

There is no narrower source on this wire. `BoxRecord` carries `cards`, `on_hand`, `sold`,
`retired`, `moved` and `listed` — **not one of them is "not yet identified"** — and
`ServerStatus.states` is one number for the whole store. So the per-drawer, per-game and
per-sitting figures are counted from `GET /inventory`'s card map, over the `state` field the
server wrote.

**`server.ts`'s rule is that the app may not compute a rule the PIPELINE owns** — the send list,
the cost, a price. Counting records whose `state` equals `captured` is reading a field, and
`Home.tsx` already clusters the same payload into sittings.
**The number that GATES THE SPEND is still the server's**: the preflight's total, untouched. A
route that answered these counts would replace one function.

### The sitting is `storeHistory.ts`'s, and there is no second definition

`GAP_MINUTES` is imported rather than restated, so `#/`, `#/capture` and this stage cannot
disagree about where one sitting ends.
**The window comes from `sittings()` over EVERY card, not the un-identified subset** — a sitting
is a fact about the store's history rather than about what is left in it, and clustering the
subset splits one real sitting in two wherever the identified cards filled a gap, then
undercounts it.

**The chip counts the cards in the STATE inside the window, not the cards in the window.** A
chip that counted the window would say 3 and then quote a preflight over 2, which is the
estimate disagreeing with the control that produced it.

### The filter lives in the address

`#/runs?state=captured&box=4`. Component state was never a place: a bookmark, a reload and the
back button now all land on the same scope, and `standing.ts`'s link is the same address a
bookmark would be. It shares the query with `?run=` and neither reader touches the other's keys;
closing the dialog clears it, so a reload does not reopen one.
**Anything unparseable answers no filter at all** — the same rule `runHandoff.ts` applies to a
stale handoff and D3 rung 0 applies to an identification, and for the same reason: a half-read
scope is a scope the operator did not choose, and the press after it spends money.

### `CarriedScope` is a list of position keys

`{box, indices}` was why a handoff could not span drawers. `#/inventory`'s mass-select walks
whatever the search narrowed it to, which is not a drawer.
**The RECEIVING end was what made it one**, so a cross-drawer tick had nowhere to go and was
never offered.

`box/index` is `identify/sidecar.py:key`, what the identification cache, both standing queues,
the join and D174's claim table are already keyed by.
**It is the STORED index and never D58's countable slot**: a handoff spelled in slots would name
a different card the moment anything in front of it sold.

**A `{box, indices}` handoff written by the previous build reads as nothing.** D27 carries this
repo's own ruling on the same question — the ten storage keys were renamed with no read-time
fallback, because a fallback can never safely be deleted afterwards — and this is the cheapest
of them to abandon: the handoff is cleared on three routes by design, and reading nothing leaves
the operator looking at every drawer with their tick one press away.

**Validation went from whole to per drawer.** A carried box the registry no longer holds used to
drop the handoff entirely, which was right while a handoff WAS one box. Dropping forty cards in
box 9 because box 3 was deleted under them is a narrowing in the one direction that costs the
operator work, so the departed drawer's keys go and the rest stay.

**D39's re-consent rule is unchanged and now reaches four controls**: picking any scope drops
the tick list, because a filter that survives a deliberate choice is one the operator did not
re-consent to.

### Every figure on stage one is the UNNARROWED one

A chip's count says what THAT narrowing holds — `Box 4 · 133` is a fact about box 4 — and not
what it holds under whatever else is ticked. Counts that moved under each other would be four
numbers re-describing one selection, and the selection's own figure is already stated once, on
the footer line, where the scope belongs.

**It is also what keeps D118.** No chip appears, vanishes, changes width or reorders under a
press; the primary row's words never change and its second line reserves its height. Asserted by
a rect sweep over every element in the dialog, keyed by position in the tree rather than by id.

### What is not built

**No real send has gone through this stage.** Every case is a stubbed browser; the preflight,
the confirm and the spend route are intercepted, as this suite requires. The drawer press is
byte-for-byte identical to the one that has run on the rig, which is the argument that it is
safe — not a measurement that it ran.

**The game and sitting narrowings have never been sent.** They produce `indices` legs, which the
route has built symlink directories from since D33, but no run has been started from one.

**`_unreachable`'s other two states still have no press here**, and giving them one is not this
entry: `unjoined` is a run's own join step and `reallocated` is `pkmnscan rescue`.
