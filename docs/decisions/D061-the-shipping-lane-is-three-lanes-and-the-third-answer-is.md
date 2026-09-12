## D61 — The shipping lane is three lanes, and the third answer is "I cannot tell"

**Built 2026-08-30.** `pipeline/shipping.py` reads the TCGplayer Export Shipping CSV and routes one order into one lane; `pipeline/pirateship.py` writes the Pirate Ship import spreadsheet. Every number below is measured against `fixtures/orders-shipping.csv`, 331 real orders.

**The number is the third lane, not the $50 line.** The obvious build is a comparison — under fifty an envelope, over fifty tracking — and it is wrong about two real orders at once:

    < $50, all cards           tcgtracking IMb envelope    (not this entry's to build)
    < $50, contains non-card   Pirate Ship parcel
    >= $50                     Pirate Ship parcel

A **playmat cannot go in an envelope whatever it cost**, and a **$600 single may not go untracked whatever it weighs** — TCGplayer mandates tracking above $49.99. Two independent facts about one order, so a rule reading only the money puts a $12 sealed booster box in a stamped mailer and a rule reading only the contents ships the single. Neither signal subsumes the other.

### The two signals are not the same strength of claim, and the order they are asked in is the whole design

**`Value Of Products` is a fact.** Present on all 331 rows, needs no weight, and $50 is a threshold TCGplayer publishes rather than one this project fitted.

**`Product Weight / Item Count` is a proxy, and it abstains.** It is a summed per-product **catalog constant**, so the ratio proxies *does this order contain a non-single*; the derivation, the five exact values and the empty band are `docs/specs/shipping-export.md`'s and are not restated here. Two numbers cross the seam because the router compares against them: the cut is **0.30**, the geometric midpoint of an empty band 18.4x wide, and the singles constant is **0.07**. Derived from where a real distribution is empty rather than picked, which is D19's rule. Missing on **97 of 331 rows**.

**So the fact is asked before the proxy, and that is worth 58 orders.** Measured: **58 of the 97 weightless orders are at or over $50** and are answered with certainty by a rule that never needed a weight. **Abstention falls from 97 orders (29%) to 39 (11.8%).**

**It also answers the case that spec names as its own worst** — *"it abstains on 29% of orders, and one of them is a $1750 order."* That order is `A2FFC195-0000F4-006AC`, one item, no weight, $1750.00, and this router sends it to a tracked parcel **without consulting the proxy at all**. T7 asserts it by name, because a router that abstained first would still produce three lanes, still count correctly on every weight-bearing row, and still look right.

**The proxy says "heavier than cards alone" and may never say "contains a playmat".** Even at 18x that is an inference. `non_card_signal` produces the same lane the value rule does, so nothing downstream needs the guess sharper than it is.

### Abstention is a third answer, never a default to a lane

`LANE_UNJUDGED` is returned, named and counted. Defaulting it to the envelope ships a playmat in a stamped mailer; defaulting it to the parcel spends postage nobody asked for. **Both are decisions this module is not entitled to make** — the operator is. `parcel_lane` hands the emitter the 126 the router placed there and nothing else.

**Five reasons, because two lanes are reached on different grounds and three abstentions have different remedies.** `Routing.certain` is the split that matters — `value_at_threshold` reads a published price against a published threshold, everything else is the inference — and a screen that cannot tell them apart cannot show which answers are worth checking.

**Two of the three abstentions are latent, and saying so is the point of counting them.** Both report zero over the fixture, and neither is speculative machinery: each is one comparison standing between a silent wrong answer and a visible refusal.

- **`sub_single_weight` is the spec's own named false-negative, turned into an abstention.** `docs/specs/shipping-export.md` records the mechanism and has no row for it: one card plus one weightless non-card reads 0.035 oz/item, *below* the singles constant, so it reads as safer than pure singles. No summed catalog constant can come out below 0.07, so a ratio that does means a product carries less than a card's weight — the weightless non-card itself. Compared only against the 0.30 cut it reads `cards_only`: a playmat in a stamped envelope, silently. The model does not apply, so the router has nothing to say.

- **`no_value_data` was a comment before it was a line of code, and T7 caught the difference.** `route` carried a comment claiming a missing `Value Of Products` landed in the unjudged lane. It did not: a valueless order of pure singles fell past the threshold check, past the proxy, and out as `cards_only` — **a $600 single going out untracked**, from a router whose comment said otherwise. D41's failure (a premise deleted, the conclusion left standing), caught inside the session that wrote it by a test written before the code was believed. **The proxy may not rescue it**, which is why the guard sits above the ratio: a cards-only ratio is the shape an expensive single takes.

### Exact rational arithmetic, never floats

`docs/specs/shipping-export.md` records a float pass **reporting a phantom sub-0.07 row** on a distribution whose true minimum is exactly 0.07 — the one band this router treats as impossible, so **a float manufactures the outcome the bullet above exists to refuse**. Not decoration: T7 run with `Fraction(float(weight))` substituted moves the **lane counts themselves**. `Fraction` and not `Decimal`, because a ratio of two decimals is not a decimal — 45.14/20 terminates, 115/86 does not, and that row is real.

### The emitter: a spreadsheet, because there is no API

**Pirate Ship has no API**, and this is not a gap to work around. Their three first-class entry points are a typed address, a marketplace connection and a **spreadsheet import**; the third is the only one this project can drive, and it is supported rather than improvised.

**`Name` is pre-joined from `FirstName` + `LastName`.** Their auto-mapper is good and it is a guess made on the far side of a seam no committed fixture can test. We own the columns, so it need not work out that two of ours make one of theirs — a recipient addressed as a first name alone is a package at the right street with the wrong person on it, and the failure is invisible from this end.

**`Order ID` is what closes the loop.** `Tracking #` and `Carrier` are empty on **all 331 rows** of the export, structurally rather than incidentally, so carrying the TCGplayer order number across is what lets the tracking number Pirate Ship mints be matched back.

**The rubber stamp makes the label the pick instruction.** Pirate Ship prints three in the label corners, so `Box 3 · Card 31` is read off the thing already in the picker's hand rather than off a second screen. **No label is composed here**: `pipeline/join.py:Position` is the only label formula in this repo and D58 makes drawing one need the box's whole occupancy, so a second formula here is the second-renderer failure already recorded three times. A stamp is an opaque string written out unchanged.

**No length is enforced on a stamp, because nobody has measured one** — truncating at an invented number cuts the end off a pick instruction, and a wrong shelf reads as a right one. Too many stamps refuses, because *that* is knowable from the format.

### Three things the emitter may never do, and all three are D49 in another lane

D49 states it as *"nothing here is ever defaulted on your behalf — that is the entire point"*.

- **It never selects insurance.** An insurance-shaped column **raises** rather than being dropped, matched folded and stripped so a differently-spelled header cannot slip past. Dropping it silently is an operator who believes they asked for insurance and did not; it is a per-order judgement made inside Pirate Ship, looking at the card.

**The named list is a deny list over a set already closed by `COLUMNS`, and what it adds is the reason.** A refusal reading *"not a Pirate Ship column"* invites the fix of adding it. One naming this entry does not.

- **It never buys a label.** No API exists to buy one with, and it would be spending.

- **It never derives a weight, which is the one most likely to be "fixed" later.** The obvious candidate is `Product Weight`, and it is wrong **in the expensive direction**: the catalog constant counts the cardboard and not the mailer, the toploader or the tape, so it is a **lower bound**. Writing it buys postage for less than the package weighs — returned or postage due, at the far end, weeks later. `Package Weight` is whatever the caller measured and blank until they have; Pirate Ship's import sets one weight across every row after the fact, which is where a number off a scale belongs.

T7 asserts the blank **on an order routed by its weight**, so the temptation is strongest where the assertion stands. The first draft took the first order in the lane and passed vacuously: 58 of the 126 carry no weight at all, so it asserted that a blank column stayed blank.

### Buyer PII passes through and is not persisted

Names and addresses enter as arguments and leave as the bytes the caller asked for. Neither module reaches `store/` and neither caches, and `render` returns **bytes rather than a path**, so a buyer's name need never touch a disk. `write_csv` is the one function that writes, and only where it is told.

### The one-way edge, and why this is two modules

`shipping.py` imports `pirateship.py` and never the reverse, so the Pirate Ship format knows nothing about TCGplayer and can be fed by the Bridge untouched. `tcgcsv.py` is the precedent: a foreign format gets its own module.

### This is a pre-line-data stopgap, and it is to be RETIRED rather than tuned

**The export carries no line items at all** — no SKUs, no product names, only `Item Count`, confirmed against a real export. That is what makes a weight ratio the best signal available rather than a proper answer. `pipeline/orders.py` already answers the same question correctly from declared line kinds (`OrderResolution.ships_in_an_envelope`). The day a feed supplies them, **the cut here is the thing to delete, not the thing to re-fit.**

### IT IS A LIBRARY AND NOT A FEATURE

No route, no client function in `app/src/server.ts`, and no screen reaches either module. By `CLAUDE.md`'s route-is-not-a-feature rule it is **not landed**, and this entry says so rather than letting a green harness read as a shipped lane. The remaining half is the unfinished part of this task, not a follow-up to it. `docs/specs/shipping-export.md` said *"nothing reads this file and nothing reads the fixture"*; that is now false in its second half and true in its first, and the spec is amended to say which.

### What would reopen this

**Line items, which retire the cut.** **A measured stamp length**, which makes the unenforced limit enforceable. **Or Pirate Ship refusing the file** — the one thing no committed fixture can hold, because nobody has fed their importer this CSV. Same standing as T6's synthetic composites, and the reason `Name` is pre-joined.

### On this entry's own number

Taken as D61, free now that the number below it has merged; it was contested by two unmerged branches when this was written, which is the heading collision D16 records, in progress again. **The owner's rule, given when asked: always renumber YOUR OWN branch, never another's.** That is narrower than D16's renumber-by-position rule and does not conflict with it — D16 settles headings that have **already** landed, and this settles who yields **before** they do: the incoming branch, always. The alternative is each session moving whichever entry it finds easiest, which is how a cited id comes to point at a different entry.

---
