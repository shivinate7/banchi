## D-a-typed-price-is-cleared-by-a-press — A typed price is cleared by a press, never by an expiry, and the set it may clear is the set the corpus dates

**A typed pricing answer stands until the operator clears it, and `#/pricing` gains one control that clears many at once — scoped, counted in its own label, and reversible — because the alternative the operator was offered was an expiry rule and they turned it down.**

The report, verbatim: *"I also need a clear claims on pricing (after several emits a lot of pricing is pre typed but stale and there's no way to mass clear)."* Asked whether a typed price should go stale by itself after N days, they answered: *"Just give me a mass-clear button."*

**So there is no TTL, no auto-stale and no expiry anywhere in this change.** `older_than_days` is an argument to one call, spent by one press; the store carries no memory of it and nothing runs on a clock. This entry is about a CONTROL, and the policy question it could have been is answered `no`.

### The measurement

Taken read-only from a copy of the owner's `inventory/prices.json`, 2026-09-12, the file having last been written at 03:42 that morning. **430 answers under `skus`**:

| | count |
|---|---|
| typed prices | **407** |
| holds — every one `withheld: bullish` | 23 |
| of the 407: answered 2026-09-07 | **269** |
| answered 2026-09-10 | 59 |
| answered 2026-09-11 | 33 |
| answered 2026-09-12 | 26 |
| carrying no `at` at all | **20** |

**66% of every typed price in the store was five days old and still pre-filling its field.** D49 is explicit that an untouched row writes no key — the rule's suggestion is a ghost that writes nothing — so what was pre-filling those fields was not a suggestion. It was 269 real answers, each one a figure the operator typed once, each one about to be what `emit` wrote.

**The removal was per-row and only per-row**: select the field, delete the digits, three hundred times. Nothing in the product removed more than one.

### What it may clear is exactly what `stamp_answers` dates

The safety of a mass-delete over the one file in this product that holds money is entirely the question of which answers it can reach. **`pipeline/corpus.py:clearable` uses the predicate `stamp_answers` already uses — `channel == "price" and not is_hold`** — and that is a symmetry rather than a convenience: **if an answer earned a date, it is a typed price; if it did not, it is either a judgement or the absence of an answer.** Both halves are asserted against each other in `harness/tests/t7_store_and_seams.py:check_pricing_clear`.

The three things it never touches, and how each one fails differently:

**A HOLD IS NOT A PRICE, AND THIS IS THE ONE I WOULD HAVE GOT WRONG BY DEFAULT.** D49 built `withheld` to carry a reason, a `watch_above` and a note — *"a way of flagging that the hold is intentional"* — and its own vocabulary section spends a paragraph keeping the word disjoint from two others so the three cannot be confused. Clearing one does not return a row to a blank field with a suggestion behind it: **it puts the card back into the next `emit`**, which is a money consequence in the direction that costs. The owner's 23 are all `bullish`, which is a claim about where a price is going, not an answer about where it is. `stamp_answers` rule 3 already says *"a hold is not a price"* in as many words; this is that rule pointed at deletion. **No control in the sheet reaches them, and the sheet says the figure** rather than leaving it to be discovered.

**A `channel != "price"` ANSWER IS THE ABSENCE OF ONE.** `cli/cmd_join.py` seeds `Answer(value=None, channel="unknown")` for every card the catalogue could not price, and `pipeline/decisions.py:blocking` reads that table to decide whether `emit` must refuse. Clearing one makes an unpriced card read as though nothing were owed on it — the direction that costs money again, and invisibly. `Answer.channel`'s own docstring records this gate being broken once before by dropping the field.

**AN UNDATED ANSWER CANNOT BE PLACED BY AN AGE FILTER, SO AN AGE FILTER LEAVES IT.** 20 of the owner's 407 carry no `at`: they predate `stamp_answers`, or `prices adopt` folded them in and D103 rules that inventing a date for those is refused. They are almost certainly the oldest answers in the file — and *almost certainly* is not a standard this repo deletes money on. An age window skips them and **names the count**; `Any age` takes them like any other typed price, which is what that option means. A `null` age is reported as `null` and never as `0`, because a zero reads as *written today* and that is the direction that makes a stale price look fresh.

### The blast radius is a control, and the narrow position is the default

**This is the central risk and it is a design problem, not a coding one.** D86 made `inventory/prices.json` one file for the whole store, so the natural shape of a clear is *everything*. An operator looking at one run's rows who presses a button labelled `Clear` and loses 407 answers across twelve runs has been ambushed by a decision nobody showed them.

So the sheet asks the scope first, in two positions, and **the worklist is selected**:

- **`On this worklist · N`** — the SKUs this screen loaded. The sentence beneath names them the way the header already does (`Box 3 · RB Epics`).
- **`Everywhere · M`** — and its sentence says what that means: *"Every run at once. The pricing answer is one file for the whole store, so this reaches cards in runs that are not on this screen and boxes you are not looking at."*

**The figure is in the button's own label** — `Clear 269 typed prices everywhere` — because this repo's rule for a press that costs something is that the label carries the figure, and a count in a tooltip is a count nobody reads.

**THE SCOPE IS THE WORKLIST AND NOT THE VISIBLE ROWS, WHICH IS THE ONE PLACE THIS COULD HAVE BEEN MORE LITERAL AND SHOULD NOT BE.** `#/pricing` has lens chips and a cut-off that re-partitions live, so *the rows on screen* is a set that moves as the operator toggles a filter they may have set ten minutes ago. A destructive press whose meaning depends on a chip is a press nobody can predict. The worklist is what the screen LOADED, it has a name the sheet can say out loud, and that is what makes the radius legible rather than merely bounded.

**And the sheet opens in its safest state every time** — scope `worklist`, window `Any age` — rather than remembering the last press. A remembered destructive default is one the operator did not choose this time.

**There is no default window, and there may not be one.** A window chosen here would be the expiry rule the owner refused, wearing a different hat.

### Every window draws its own count, which is D103's finding applied

D103 measured a staleness GATE selecting *"177 SKUs at one day, 109 at three and at seven, and 0 at ten and at fourteen"* and ruled the zero was the whole argument: **a window can be empty for a reason that is about the store's age rather than about the answers.** The same is true here. On the owner's store today a 7-day window selects **nothing**, because the oldest typed price in the file is five days old.

The remedy is that the count sits ON the option, before the press. An empty window is then visible rather than discovered by pressing a button that does nothing. That is why the windows are a row of two-line cells rather than the kit's `Segmented`, which draws one line of label per option and has no shape for a word plus a figure — said out loud here because building beside the kit is the thing that needs an argument.

### Two routes, both carrying D86's revision guard

**`POST /pricing/clear`** removes and hands back what it removed. **`POST /pricing/restore`** puts it back. Both take the digest `PUT /pricing` has taken since D86's amendment of 2026-09-04.

**THIS IS THE THIRD AND FOURTH WRITER OF THAT FILE AND THE GUARD IS WHY THAT IS ALLOWED.** That amendment is blunt — *"ONE FILE MEANS TWO WRITERS, AND THE SECOND ONE WAS SILENTLY REVERTING THE FIRST"* — and D105 states the rule as *"one file may not have two unguarded writers"*. **Unguarded is the operative word**: `pkmnscan reprice apply` is already a second writer and is admitted by carrying `--corpus-revision`. An absent revision still lands, verbatim as the PUT has it, because absent means *did not read one* and that is the terminal user.

**A clear is its own route rather than a `PUT /pricing` of nulls.** `Corpus.parse` does read `null` as *drop this answer* (D49's rule, untouched), so a client could clear by nulling keys — and then the CLIENT would be deciding which keys, which is `corpus.clearable` written a second time in TypeScript against money. That is what D49 refused across two languages and what D103 found happening across two Python modules with `preset_prices`. **The predicate stays in Python and the screen presses a button.**

**The client's SKU list is a SCOPE and never a predicate.** The route re-derives membership from the file as it stands on every call, so a list that went stale between the read and the press removes *fewer* answers than the label said, never a different set — and a screen cannot name a hold into being clearable. `check_pricing_clear` presses exactly that: a scope naming only a hold and an `unknown` seed clears nothing, and **a build that trusted the client's list would delete both while every other assertion in that case still passed.**

**The counts the label needs ride the envelope of `GET /pricing`**, beside `revision` and never inside `corpus` — that document is replaced wholesale and round-trips keys it does not recognise, so a derived block written into it would end up stored in `inventory/prices.json` and read by the next screen as a fact somebody wrote. The screen intersects that list with its own rows. Set arithmetic over an answer Python already gave is not a second opinion about it.

### The way back is the answers, with their dates

**`cleared` carries each answer's `value`, `at` and `from_run` verbatim, and that is what makes the undo an undo.** Handing back a list of SKUs would make it a re-type.

**`restore` writes `at` verbatim and does not stamp.** A restore is the assertion that an answer given five days ago was never withdrawn; stamping it would make the undo of a clear read as a store-wide re-pricing on the next markdown survey, refusing every restored SKU `priced_recently` — **D103's ratchet inverted by the one press whose entire job is to change nothing.**

**It writes only a SKU the corpus no longer answers**, so an undo can never overwrite a price typed since the clear. Those come back in `skipped` and the toast names them: an undo that quietly does less than it says is worse than one that refuses. That also keeps the route from being a general write path — the general write is `PUT /pricing`, unchanged.

**The press is refused while the screen has unsaved work**, and the sheet says so. `#/pricing` autosaves the whole document; a clear landing under an unsaved keystroke would be undone by that save, silently — D86's two-writer defect reached from inside a single tab.

**And the screen does not reload afterwards.** It holds the document the server confirmed, so the new one is that minus the cleared keys, with `book` and `savedBook` put on the same object so `dirty` stays false. A reload would be correct and would flash skeletons over the whole list, which is D118's rule broken by the one press that has no business moving anything.

### What this does not do, named rather than left to be discovered

**No hold is ever cleared, by any control here, and there is no option that would.** An operator who wants a hold gone lifts it on its own row, where the reason and the watch are visible. If holds ever need a bulk lift that is a different press with a different argument, and it is not this one.

**Nothing is scoped to a run's own answers** — there is no *clear box 3's prices* — because a price is a fact about a SKU and not about a drawer (D7, D86), and the worklist scope is what a run-shaped ask actually means on a screen that merges runs.

**No file is written and nothing at TCGplayer moves.** A cleared row is a row with no answer; what it goes out at is the standing rule, at the moment `emit` runs, exactly as an unanswered row always has.

**`pipeline/reprice.py:_parse_stamp` now delegates to `pipeline/corpus.py:parse_stamp`.** Its own docstring gave the reason it could not use `store/master.py`'s — *"this module does not import `store`"* — and that reason is satisfied by `corpus`, which is where `Answer.at` is defined. Two readers of one field is how `priced_recently` and a mass-clear would come to disagree about which answers are old. `store/master.py` keeps its own, which is not drift: it parses stamps the store wrote, from code that already has the database open, and `pipeline/` may not import it.

### What would reopen this

*An operator who clears the same window every week*, which would mean the expiry rule was the right answer after all and the press is a ritual. The measurement is whether two consecutive sittings clear at the same window with no other pricing in between.

*A hold nobody can lift in bulk*, if holds ever accumulate the way typed prices did. D49's own reopening measurement watches the neighbouring case.

*A worklist scope that is never used.* If every press is `Everywhere`, the scope control is ceremony and the honest simplification is one press with the figure on it. The measurement is the scope each clear is sent with.
