## D181 — The order is taken once, and a sale may not retake it

**`#/inventory`'s ranking under a search is computed from the copies that are still on hand, so marking one copy sold re-ranks the list the operator is working down — and the fix is to hold the order still and give the operator a press that retakes it, because the ranking is right and only its timing is wrong.**

**This is an amendment to D118, not a new floor.** That entry's ruling is *"a press changes WHAT IS ON THE SCREEN and never where the rest of it is"*, and this is the same sentence on an axis it could not see. See "Why D118's own guards were blind to this" below; the short version is that every instrument D118 built measures PIXELS, and a reshuffle moves no pixels — it moves which row is drawn at which pixel, and the rows are the same shape.

### The report

The owner, 2026-09-12:

> i built sorting in inventory so that it's ordered by when. i search a card it's ranked by the most of the card in a certain section, this is awesome and i love it but i realized if i mark sold while on that sorta view it can reorganize the rankings right in front of me, which feels unintuitive if im trying to mark multiple as sold.

Two things in one sentence, and they point opposite ways. **The ranking is correct and stays** — it is D132's amendment of 2026-09-11, their own rule, *"the largest quantity of whatever I searched, BY SECTION, is the order"*. **What is wrong is that it is recomputed under the hand.** They mark several copies sold in a row; each press changes the arithmetic; the list they were half-way down rearranges itself.

### D28 is the precedent, and the mechanism is deliberately the same one

**"The review answer gets an undo window, and the list stops moving under it."** That entry's first fix is this problem on `#/review`: answering a card shifted the candidate rows by most of a screen, *"under a finger already travelling toward a number"*. Its answer was not to change the ordering but to stop it moving — reserve what varies, prefetch what is coming, and let the operator work down a list that holds still.

The only difference here is what varies. There it was a photograph's height; here it is the rank itself. The ruling is the same one, so the shape is the same one.

### What is frozen is a fact about the copies, not a list of positions

**The obvious build is to snapshot the rendered order as an array of keys and re-apply it.** It was rejected. That array is a fourth copy of an ordering three call sites already compute — the copies list's `byFullest`, the box rail's `liveMatches`, and the walk's `landingInFullest` — and the day any one of them gains a term, the snapshot disagrees with it silently. A frozen order that has quietly stopped being the order the product computes is worse than one that moves.

**What is snapshotted instead is the only INPUT that moves under a press: which copies counted as live when the order was taken.** `app/src/frozenRank.ts` holds it as a set of store keys, and every ranking goes on computing itself — from the state the order was ranked against rather than from the state the store is in now.

**So the set holds the DEPARTURES, not the survivors.** A copy captured after the order was taken is new evidence and is held by nothing, which is right — nothing was ranked around it. A copy that LEFT since the order was taken is held, and every reader treats it as it was.

**One set, one press, for both lists.** It lives in `Inventory.tsx` beside the writes, not inside either list, because one sale makes the copies list AND the box rail stale at the same instant. Two freezes released by two controls is the owner pressing twice to stop one list moving.

### Four readers, and the fourth is the one that is easy to miss

| reader | what the freeze does |
|---|---|
| `CardLocations.tsx` `counts` | a departed copy goes on counting for its section, so the section order does not move |
| `BoxBrowse.tsx` `liveMatches` | a departed copy goes on counting for its box, so no box tile moves in the rail |
| `BoxBrowse.tsx` `holdsLive` / `landingInFullest` | the walk does not jump to another box because the one it is in has just sold out of matches |
| **`BoxBrowse.tsx` `visible` and `CardLocations.tsx` `stays`** | **the row is still DRAWN with `Hide sold` on** |

**That last row is load-bearing and it is D132's other door.** Freezing the arithmetic while letting the fold delete the row puts the jump straight back: the row vanishes and everything under it comes up by its height. D132 offers two behaviours for a departed row — folded away, or sunk under the live ones — and **frozen mode can take neither as written**. A sink is a movement too: every row below the sinking one comes up. So a frozen departure stays exactly where it is and is struck, which is the only rendering that moves nothing.

**The departed row's own rendering is the product's existing one and nothing here invents a second.** `pipeline/join.py:Position` already draws a copy in no slot as `Box 7 · departed · B7 #38` (D68 for why it names the record, D58 for why the number behind it now belongs to a different card), and `.is-gone` already dresses the row. The freeze changes where that row is, not what it says.

### The control

**`Order is N copies stale · re-rank`, a `Chip` in the copies list's header, drawn only once the order has actually gone stale.** Four choices in that sentence, each with a reason:

- **A press, never a timer and never a consequence.** Nothing reshuffles this list on its own, ever. That is the whole ruling.
- **In the copies list's header and not on the walk's status bar beside `Hide sold`.** The press that made it stale is in the rows immediately beneath it; a re-rank across the screen in the left rail is a control the hand has to travel to. It governs both lists all the same — the rail is frozen by the same set.
- **Absent while the order is current.** A control offering to recompute an order that is already current is a button that does nothing, and a permanently drawn one reads as a setting to get right rather than as the state of this list.

- **`copies` and not `sales`, which is one word off the owner's own phrasing.** They wrote *"order is N sales stale"*, and a sale is what they will nearly always have pressed — but D26's other door counts here too: a RETIREMENT takes a copy out of the boxes, changes the same arithmetic, and is held by the same set. This screen does not record which door a hold came through, and threading that distinction through three components to keep one word would be a field carried for a label. `copy` is the product's own word for these rows everywhere else on the panel.

**It counts the copies THIS LIST draws, not every departure the screen has recorded.** `frozen` is the screen's; a sentence saying `3 copies stale` over a list holding one of them would be counting somebody else's cards.

**And it takes a new order on its own in two places, which is not a reshuffle.** A new search is a new order — nothing has been worked down under a query that was just typed — so `BoxBrowse` releases the freeze when the searchbox text changes. And an undo releases that copy's hold, because a staleness figure that survived an undo would be offering to re-rank a store that never moved.

### Why D118's own guards were blind to this

**Every instrument that entry built measures pixels, and this defect moves none.**

- `cursor.spec.ts`'s two cases read the STYLESHEETS for a pointer state that re-lays out a control. A reshuffle is not a CSS rule.
- `inventory.spec.ts`'s sweep records every element outside `.browse-card` by a stable id and its box, and asserts the document height and the scroll. The copies list is INSIDE `.browse-card`, and — decisively — the rows it reorders are identically shaped boxes. Swap two of them and every recorded rectangle is where it was.

**So the proof had to compare the identity of the rows and not their geometry.** Both new cases read the ordered list of each row's `aria-label` — the server's own position label, which is the one string that says WHICH copy is drawn there — and compare it before and after. A `toHaveCount` cannot see a length-preserving reshuffle and neither can a position sweep.

**And both directions are asserted, in a case each.** A case that only says "the order did not change" is green against a build that never ranks at all; a case that only says "the re-rank changed it" is green against a build that re-ranks on every press. **The fixture is built so the two answers differ**: six live copies, three in box 7 section 1 and two in box 2 section 2, and the sale takes box 7 from three to two — a TIE, which the rank breaks the other way. A fixture whose leader stays the leader after a sale cannot tell a frozen order from a recomputed one, and this repo has paid for a one-directional assertion more than once.

### Mutation-tested, eleven arms, and three of them changed the code

**Every reader of the freeze was deleted in turn and the suite re-run. Nine arms go red. One arm deleted a parameter instead. One survives and is named.**

| arm | verdict |
|---|---|
| the copies list's rank ignores the freeze | red |
| the copies list's fold ignores it | red |
| the box rail's rank ignores it | red |
| the walk's fold ignores it | red |
| the shelf pool ignores it | red |
| the re-rank press does nothing | red |
| a sale never holds the order | red (8 cases) |
| a new query never takes a new order | red |
| the control's slot reserves nothing | red |
| the landing ignores the freeze | **deleted — see below** |
| an undo never releases its hold | **survives — see below** |

**Four of those nine were green on the first run, and each was green for the same reason: the case was acting on the row the walk was standing on.** `stays` keeps a row for three reasons — it is the current copy, this screen just sold it and holds a receipt, or the order is frozen by it — and the first two answered every assertion, so the third was never exercised. The cases now act on a MID-LIST row, and the one that reaches the freeze alone is a RETIREMENT: `Inventory.tsx` hands the copies list `soldKeys` and deliberately not `retiredKeys`, so nothing local holds a retired row and the freeze is all there is. A fifth needed a fixture where a box's LAST live match departs, which is the only state the shelf pool can notice.

**The landing's freeze was deleted rather than covered, because it was unreachable.** `landingInFullest` runs only when the query is FRESH, and a fresh query is exactly what releases the freeze — so the parameter could only ever be empty. A mutation that ignored it left the whole suite green, which is the correct answer to a parameter no call can populate. It is gone; the landing ranks on current state, as a fresh answer should.

**The undo's release is the one arm that survives, and it is reported rather than explained away.** Deleting `releaseRank` leaves all 108 cases green. The header was dumped under the mutation to find out why, and the chip IS present on the frame after the undo and gone again shortly after — so something on that path clears the hold without this call, and bounding the assertion to two seconds did not separate them either. **What that does NOT establish is that the call is redundant**, only that this fixture cannot see it, which is a weaker claim than the landing's and is why the code stays. A later session with a reproduction should either find the second clearer and delete one of them, or find the case this one is missing.

### What the control cost, named

**The header's title row now reserves `--bn-control-h-sm` whether or not the chip is in it**, which makes the copies panel's header about eight pixels taller on every card at desktop. That is D118's own trade taken deliberately: the chip appears on a press, this list scrolls inside `.browse-band`'s fixed height, and an unreserved slot would send every copy row down by the chip's height at the exact moment of the sale — the movement this entry exists to stop, reintroduced by the control that stops it. Paid once at render rather than on the press, which is the same bargain `.browse-row-slotghost` makes in D118's own amendment.

**The chip's HEIGHT is the kit's and not a number in `CardLocations.css`** — `.bn-chip` reads `--bn-control-h-sm`, which the token file raises to 40px under 767px and on any coarse pointer, so D117's thumb floor is met by the system. A case asserts it at 390 anyway, because a floor with no reader is not a floor.

### What is not built, and what would reopen this

**No preference is stored.** The freeze is always on and the re-rank is the only escape, so there is no ninth `banchi.*` key and D27's roster is unchanged. The alternative — a remembered "re-rank live" toggle — was not built because nobody has asked for the old behaviour back, and a setting nobody changes is a second code path nobody tests.

**The staleness figure counts DEPARTURES and not "rows that would move".** `Order is 3 copies stale` is true and easy to believe; `3 rows would move` would be truer and would mean recomputing the order on every render to compare it against the frozen one, which is the live re-rank this entry deletes, running invisibly. If an operator reports pressing re-rank and seeing nothing change, that is the trade and this is where it is written down.

**A copy the store departs while nobody is pressing anything is not held.** The freeze is populated by THIS screen's writes. Another device selling a copy mid-search will still re-rank this list on the next re-read — except where this screen saw the `already_sold` refusal, which is held for exactly that reason. Making the freeze a diff against the last answer rather than a log of presses would cover it, and would also freeze a genuine capture arriving. Unmeasured, and named here rather than discovered.
