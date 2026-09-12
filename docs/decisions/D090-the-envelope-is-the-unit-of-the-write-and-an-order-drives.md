## D90 — The envelope is the unit of the write, and an order drives the walk as a mode of the inventory screen

**An order takes over `#/inventory`: the walk lands on the first copy that order needs, an arrow steps to the next, and the whole order is recorded on ONE press that says the envelope is filled.** Built 2026-09-02 on the owner's want: *"as orders arrive on TCGPlayer I want them to be matched against PKMNSCAN for SKUs they may hit, and then I literally want to be able to have all the cards pulled either in one go across all orders or work order by order with basically an order fulfillment screen showing me one after the other without me searching for each card"*. Both halves of that sentence are modes — `#/inventory?orders=open` is the one go across all orders, `#/inventory?order=<key>` is order by order.

**The mechanic was asked for by name, and it is the mechanic that already exists.** *"you know how currently in inventory if you're on one card and left or right arrow you go to the cards next to you in the box, and when you move from card x to card y, you also went from seeing all the positions card x was in to now seeing all the positions card y is in, i want that same mechanic on the order walks too"*. The arrows step the queue instead of the box while a walk is on — consulted by `BoxBrowse`'s existing window `keydown` listener, after its existing guards, so there is one key table and one listener — and the copies panel follows the focus for free, because that is all it has ever done.

### The unit of the write, and the failure it exists to end

**The owner named their own error point and rejected the obvious remedy in the same breath.** *"does order driving the walk mean mark sold is auto applied / auto matched? i'd rather it be i can't move on from the envelope until I click a button saying the envelope is filled all items mark sold something like that, yanno? currently i think my biggest error point might be remembering only after i've already switched to pulling another card that oh did i even mark the previous card sold?"*

**So the walk writes nothing per card.** No advance records anything, no arrow spends a copy, and `POST /orders/fill` records every copy of one order — pulled and sold — on the press that says the envelope is filled; in order mode the next order is not offered until that press lands. The state the owner described is unrepresentable rather than recoverable: there is no moment at which some cards of an envelope are recorded and others are not, so *"did I even mark the previous card sold"* has no true answer that is not the whole envelope.

**Auto-applying the sale on the advance was the alternative and it reproduces the doubt one register down**: instead of wondering whether a card was recorded, the operator would wonder whether an arrow pressed twice recorded twice. An advance is a statement about where the eyes are; a press on the envelope is a statement about what is in it.

### This reopens D69 on the owner's word, and what moved is the unit

**D69 ruled `One card, one press, and there is no batch control.`** That sentence stands over `POST /orders/pull`, which is untouched: one SKU, its copies, its own undo, its receipt. What this entry moves is the unit of the write for the WALK, and it moves it on the owner's instruction rather than on an argument D69 got wrong.

**D69's ruling was about a screen that lists picks, and a list is not a pass through drawers.** On `#/orders` the operator reads rows and presses the one they just fetched, and one card, one press is the honest gesture there. The walk is a different posture: minutes at a drawer, hands full, eyes on cardboard. The envelope is the unit the OPERATOR works in, and D69 had no walk to notice that from.

**What did NOT move, and it is most of the machinery.** Every copy is still aimed by its own `capture_id`; the aim is still checked against the card actually at that slot (`capture_id_mismatch`, rather than selling whatever slid into the index after a mid-box delete — D10 ruling 1, D58); the SKU check and the duplicate guard are the same code, because `_prepare_targets` and `_ledger_pull` were lifted out of `do_order_pull` and both doors go through them. `ORDER_FILL_TARGET_LIMIT = 50` bounds one press.

**N calls to `/orders/pull` were the cheap build and they were refused for a reason that is not taste.** That route takes one SKU per call, so a three-line envelope is three writes, and a refusal on the second leaves a half-recorded envelope the undo cannot reverse in one press: `/orders/pull`'s undo NAMES no line — it discovers the holder from the ledger — and refuses `pull_spans_lines` the moment the copies belong to two of them. The operator would be left pressing undo once per line, in the right order, after a failure. One transaction, one refusal (`fill_entry_refused`, naming the line and the position, with nothing written), one undo (which names its lines and refuses `fill_line_mismatch` if the ledger disagrees).

**D39's one-mass-select rule is not reopened.** This is not a multi-select over cards; nothing on the screen is ticked to compose it. The envelope is the resolver's own answer for one order, and the press either records that answer or refuses it whole.

### The queue is of lines, and wave mode sorts by position without drawing one

**T6's first determination ruled `A queue of positions would stand a second pick list beside the panel already drawn`, and wave mode sorts stops by `(landing.box, landing.index)`.** That reads like the determination being ignored and is not: what the sentence protected is the second-RENDERER rule, and it is intact. Nothing new is drawn. A stop is expressed as the walk's own focus through `goTo` (D45), every label is `place.label` off the wire (`pipeline/join.py:Position`, still the one formula), and `app/src/CardLocations.tsx` still draws the copies of whatever the walk points at. The sort decides the ORDER of a queue whose members are still lines; it renders nothing.

**The sort is the argument FOR ordering by position rather than against it.** Order mode walks the drawers in the order the buyer's cart happened to be composed in: all three copies of X, then both of Y. If X sits in boxes 2, 5 and 7 and Y in 2 and 5, that is five shelf changes where the interleaved pass is three — and the interleaved pass is the whole content of *"all the cards pulled either in one go across all orders"*.

**A landing is re-derived on every read, so the pass is a property of the read and never a stored list.** A three-copy line whose first copy was just filled stands at its next unfilled copy the next time the queue is computed; a mid-box delete on another device moves an index and the landing moves with it. `app/src/orderWalk.ts` holds no state, calls no server and imports no React for this reason, and the only thing carried across reads is the cursor.

**A line the walk cannot stand on is counted rather than walked to.** A line still owed copies with no pick the walk can aim at — `no_copies_on_hand`, a pooled copy (D24), a record with no capture id — is `unfillable`: the banner counts it and links to `#/orders`, and the queue never lands on a place that does not exist.

### It is a mode, and D31's ruling against two modes is untouched

**D31's correction was against two TABS over one set of records** — a segmented control asking which way to look at the same 767 cards when there was only ever one question: *"i imagined moreso in this merge that these wouldn't be two tabs, instead it's basically find a card in a box-based system if anything.."*

**A driver is not a tab.** The spine is the same — box, section, card — the photograph is the same, the copies panel is the same, the writes are the same door. What the mode adds is a banner saying which order is driving, a queue the arrows step, and a way out. Nothing is offered twice and nothing has to be chosen between, which is the property D31 was defending.

**It is not a chord either, and that ruling is not touched.** `app/src/App.tsx`'s chord table is a ROUTE table whose own comment rules out a second key space reaching a mode inside a route, and D51 settles Cmd-arrow as the one modifier the shell takes. Entry is a link on `#/orders` — `Walk this order` per open order, `Walk every open order` in its header — and exit is `Stop walking`, drawn ALWAYS LAST in the banner so the press that leaves is never where the press that fills has just been.

### The URL is the handoff, because the order key has one source of truth

**Entry is `#/inventory?order=<key>` or `#/inventory?orders=open`, and not `app/src/runHandoff.ts`.** That `sessionStorage` handoff exists, is D27's carve-out rather than a new one, and would have worked. D49's argument for `#/pricing?run=` is taken here verbatim: the key has one source of truth — the ledger — and a copy of it in a second store is a second thing with its own clearing rules, its own staleness and its own way of disagreeing with the address bar.

**What that buys is T6's own open question answered.** That section closed with *"Whether the queue survives a reload"* and declined to settle it, noting the argument is stronger here than for a run handoff because a pull walk is minutes at a drawer rather than seconds between two screens. It survives: the ask is read out of the hash, the key is validated against the payload on every read, and a reload lands on the first REMAINING stop rather than on nothing or on one already filled. The colon in `source:number` is why the key is encoded.

### The resolver is asked for what is owed, not for what the buyer bought

**`_engine_order` passed `line.quantity` raw and the ledger's recorded pulls were subtracted nowhere, so a partly filled line resolved as if nothing had been pulled.** `Ledger.outstanding` is the quantity that reaches the engine now. The defect predates this work and was live on `#/orders`; it is one this entry found rather than one it pays for.

| the case | before | after |
|---|---|---|
| a line of 3, one copy pulled, 3 copies in the store | wants 3, finds the 2 unsold, reports `short` | wants 2, reports `resolved` |
| a line of 3, one copy pulled, 5 copies in the store | wants 3, allocates **3** picks against a line owed 2 | wants 2, allocates 2 |

**The second row is not a local error, and that is why it is the one that bites.** `resolve_all` is a one-pass allocation over the WHOLE open set and its double-book guard is D69's single most important property. A third pick allocated to a line owed two is a copy taken out of the pool every other order for that SKU draws from, so the visible symptom is a SECOND buyer's line reading `short` over a copy the first buyer is not owed — a wrong answer on a row nobody touched.

**`pipeline/orders.py:OrderLine` accepts quantity zero now and refuses only negatives.** A line owed nothing arrives wanting zero, the engine picks none, and it answers `resolved` with the breakdown still counted — which is how a filled line keeps drawing its figures without a second implementation of the row. On the wire a resolved line gained `owed`, the ledger's figure, beside `wanted`, the buyer's.

### A pulled copy's slot is joined at read time, and storing it would break D36

**`_order_progress` answers `pulled: [{capture_id, box, index}]`, composed per read from `card_by_capture_id`, and nothing writes it down.** The copies panel needs it and can get it no other way: a pulled copy is SOLD, so the resolver offers it in no pick, and nothing else says which slot it came out of. (`SearchCopy` carries a capture id since D93, so a client could now match the ledger's records itself — that would be a second implementation of a join the store is indexed for, and the browser's copy would be the one with no `card_by_capture_id` to be right about duplicates.) The ledger holds capture ids, the walk is keyed by position, and this is the join between them.

**It may never be stored, and D36 is the reason in one sentence: a run directory's slot numbers are not the truth, the photograph is.** A `{box, index}` written into the ledger beside a capture id is a second address for a card, and it goes stale the first time a card in front of it leaves the box (D10 ruling 1, D58) — with none of the recovery D36 gives a run record, which at least carries a `photo_sha256` to re-bind by. Composed per answer it is simply true. `card_by_capture_id` is an indexed lookup under D88; a card that is gone, or a duplicate id the store refuses to guess between, answers nulls rather than taking `GET /orders` down, and `harness/tests/t7_store_and_seams.py` holds the renumber case that proves it.

### Boxes get no say in which copy fills a line

**Told that `Take this one instead` would be fenced to the copy under the photograph and never one in another box, the owner refused the fence: `You're giving boxes too much independence` (2026-09-02).**

**They are right, and D7 had already ruled it: `Every unsold copy is sellable`, and price is per-SKU and shared across copies.** A box-scoped swap would be the one place in the product where a copy's drawer decided whether it could fill an order — while the copies panel draws those copies across boxes precisely because they are interchangeable, and D45 makes each one press away. Any unsold copy of the line's SKU, in any box, may be taken.

**One copy is refused, and it is refused by the ALLOCATION rather than by the drawer.** A copy another stop in the queue already targets — another line of this envelope, or in wave mode another buyer's order — cannot be swapped in. `resolve_all` is a one-pass allocation over the whole open set precisely so two envelopes cannot name one card, and a hand-swap able to undo that would put D69's double-book defect back one register up: both envelopes would count the copy, the first press would take it, and the second would refuse at the server with the operator holding a card the screen had promised them. The row says `for order N` beside the missing button, which is the reason rather than a fence. The test that proves the box has no say and the test that proves the allocation does are deliberately the same case, over two copies in ONE drawer of which only one is offered.

**And the stop FOLLOWS the copy taken.** The landing is the stop's first target rather than the server's first pick, so a swap into another box moves the walk to that box instead of snapping back to the drawer the resolver happened to choose. The two client maps behind it are `targetsOf`'s `retargets` and `excluded` — the copies re-aimed, and the capture ids the operator said were not there.

**In this mode `Mark sold` is hidden on every row, and `Retire` is not.** T6's second determination is the reason and it is the seam the whole feature turns on: `POST /inventory/<box>/<index>/sold` writes card state and NOT the ledger, so a card sold that way while an order drives leaves its line owed forever and the operator ships a card the ledger still wants. Retiring is a different claim about a different card and belongs to nobody's order.

### What it costs

**The mass-select clears on an advance nobody pressed.** T6 named this and it is kept: a shelf change clears the ticks (D31, because the write the selection feeds is box-scoped) and D45 already pays it for a label press. What the walk adds is that the shelf now changes on an arrow, or on a fill that re-derives the queue, rather than on a gesture aimed at a box.

**Re-aims and exclusions are this screen's and this session's.** `retargets` and `excluded` are React state; a reload drops them and the envelope falls back to the resolver's picks. That is deliberate over a store write per swap — a swap is a statement about the next press, not a fact about the store — but an operator who re-aimed three copies and then reloaded gets the resolver's answer back with nothing on screen saying it changed.

**The banner costs about 62px above the walk at every stop.** It renders between `.browse-controls` and `.browse-body`, so the photograph's own floor and everything under it start about 62px lower for as long as the mode is on. It is one row, `nowrap`, and its height never changes — D28's rule that a list must not move under an undo, applied to the row that carries the undo.

**A copy taken without pressing the swap records the slot the walk was standing on.** The envelope sends the targets the SCREEN holds, not the card in the hand. Take a different copy of the same SKU silently and the write is right about the SKU and wrong about the slot: the store says a card is gone that is still in the drawer, and the aim check cannot catch it because the card at the recorded slot really is that SKU. The discipline is the one the walk is built around — take the copy the walk is standing on, or press `Take this one instead` and let the stop follow you.

**It is built over an ingest no real order has ever been through.** Measured against the owner's own store on 2026-09-02:

| | |
|---|---|
| cards in the store | 1,625 |
| cards sold | 104 |
| orders in the ledger | **0** |
| copies ever recorded as pulled for an order | **0** |

All 104 of those sales went through `#/inventory`'s plain sale — the write this mode hides, for the reason those 104 demonstrate: it moves the card and leaves the ledger alone. D91 built the door an order arrives through on the same day, and its own table records the fetch having returned an order zero times before it. Every guarantee here is proven by `harness/tests/t7_store_and_seams.py` and by nothing that has held a buyer's money.

**A row's correction and its reversal share a rectangle, so a double press takes one back.** `.card-locations-action` is right-anchored, `Take this one instead` is about 177px and `Not here` about 84px, and the shorter one lands inside the longer one's footprint. Neither press reaches the server, so there is no busy gate to cover an overshoot the way one covers the sale. This is the same overshoot `Inventory.css` already records for `Mark sold`, decided the same way and for the smaller stake: nothing is written, the row's mark changes word and register, and the banner's `take` figure moves — so the second press is visible rather than silent, and one more press undoes it. What was fixed instead is the part that was NOT visible: with every copy excluded the landing used to fall back to the resolver's first pick and walk the operator to a drawer they had just said the card was not in. It stays where it is now.

**In wave mode the banner is not one height, and the envelopes list is why.** The ROW is constant — that is the measured invariant and the one the arrows are pressed against — but the list beneath it is one 40px row per open order, and a read that changes which orders are open changes it. An envelope filled here keeps its row, drawn `filled`; one another device fills, or one whose last copy leaves the store, simply goes, and the walk below moves up 48px. Order mode has no list and is the constant-height case the measurements were taken in. Fixing it properly means holding a row for an order this screen never filled, which is a claim about somebody else's work that this screen has no business making.

**What would reopen this, and there are three.**

*A second pair of hands.* Everything here assumes one operator at one screen: the cursor, the re-aims and the exclusions are this session's, and two people walking the same wave would each hold an allocation the other has already spent. The measurement is a second device on a walk at the same time.

*A real envelope pressed and found wrong.* The first press against an order a buyer actually placed is the measurement this entry does not have. Watch for `fill_entry_refused` naming a position the operator was standing at: that would mean the aim check and the walk disagree about what is at a slot, which is a store bug wearing this feature's error message.

*`SearchCopy` gaining a `capture_id`.* Today a copy is swapped in only by walking to it, because the aim needs an id the search rows do not carry. If they carried one, an unpicked copy could be taken straight off the panel without the walk moving — worth arguing rather than taking, because the walk-to IS the flow: you look at the card before you swap it in.
