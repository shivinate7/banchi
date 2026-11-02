# D61 — Shipping routes three lanes, one unsure

**`pipeline/shipping.py` reads the TCGplayer Export Shipping CSV and routes each order to one lane. `pipeline/pirateship.py` writes the Pirate Ship import spreadsheet.** Every number below is measured against `fixtures/orders-shipping.csv`, which holds 331 real orders.

**The number is the third lane, not the $50 line.** The obvious build is a comparison: under fifty, an envelope; over fifty, tracking. It is wrong about two real orders at once:

    < $50, all cards           tcgtracking IMb envelope    (not this entry's to build)
    < $50, contains non-card   Pirate Ship parcel
    >= $50                     Pirate Ship parcel

A **playmat cannot go in an envelope, whatever it cost.** A **$600 single cannot go untracked, whatever it weighs.** TCGplayer requires tracking above $49.99. These are two independent facts about one order. A rule that reads only the money puts a $12 sealed booster box in a stamped mailer. A rule that reads only the contents ships the single. Neither signal covers the other.

### The two signals make different claims, and the order they are asked in is the design

**`Value Of Products` is a fact.** It is present on all 331 rows and needs no weight. $50 is a threshold that TCGplayer publishes. This project did not fit it.

**`Product Weight / Item Count` is a proxy, and it abstains.** It is a summed per-product **catalog constant**. So the ratio proxies "does this order contain a non-single". The derivation, the five exact values and the empty band are in `docs/specs/shipping-export.md`, and this entry does not restate them. Two numbers cross into this router. The cut is **0.30**, the geometric midpoint of an empty band 18.4x wide. The singles constant is **0.07**. Both come from where a real distribution is empty, not from a pick. That is D19's rule. The weight is missing on **97 of 331 rows**.

**So the fact is asked before the proxy. That order is worth 58 orders.** **58 of the 97 weightless orders are at or over $50.** A rule that never needed a weight answers them with certainty. **Abstention falls from 97 orders (29%) to 39 (11.8%).**

**It also answers the case the spec names as its worst.** The spec says the router abstains on 29% of orders, and one of them is a $1750 order. That order is `A2FFC195-0000F4-006AC`. It has one item, no weight, and $1750.00. This router sends it to a tracked parcel **without consulting the proxy**. T7 asserts that by name. A router that abstained first would still produce three lanes and still count correctly on every row with a weight. It would look right.

**The proxy shows that an order is heavier than cards alone. It never shows that an order contains a playmat.** Even at 18x, that is an inference. `non_card_signal` produces the same lane the value rule does, so nothing downstream needs the guess to be sharper than it is.

### Abstention is a third answer, never a default lane

`LANE_UNJUDGED` is returned, named and counted. Defaulting it to the envelope ships a playmat in a stamped mailer. Defaulting it to the parcel spends postage that nobody asked for. **Both choices belong to the operator, not to this module.** `parcel_lane` hands the emitter the 126 orders the router placed there, and nothing else.

**There are five reasons, because two lanes are reached on different grounds, and the three abstentions need different remedies.** `Routing.certain` is the split that matters. `value_at_threshold` reads a published price against a published threshold. Everything else is inference. A screen that cannot tell them apart cannot show which answers are worth checking.

**Two of the three abstentions are latent. Counting them is the point.** Both report zero over the fixture. Neither is speculative machinery. Each is one comparison between a silent wrong answer and a visible refusal.

- **`sub_single_weight` is the spec's own named false negative, turned into an abstention.** `docs/specs/shipping-export.md` records the mechanism but has no row for it. One card plus one weightless non-card reads 0.035 oz per item. That is below the singles constant, so it looks safer than pure singles. No summed catalog constant comes out below 0.07. So a ratio below 0.07 shows that the product carries less than a card's weight. That is the weightless non-card itself. Compared only against the 0.30 cut, it reads `cards_only`: a playmat in a stamped envelope, silently. The model does not apply, so the router has nothing to say.
- **`no_value_data` was a comment before it was a line of code, and T7 caught the gap.** `route` carried a comment that said a missing `Value Of Products` landed in the unjudged lane. It did not. A valueless order of pure singles fell past the threshold check and past the proxy, and it went out as `cards_only`. **A $600 single would go out untracked**, from a router whose comment said otherwise. This is D41's failure again: a premise deleted while its conclusion stayed. A test written before the code was trusted caught it. **The proxy may not rescue it.** That is why the guard sits above the ratio. A cards-only ratio is the shape an expensive single takes.

### Exact rational arithmetic, never floats

`docs/specs/shipping-export.md` records a float pass that **reported a phantom row below 0.07**. The true minimum of that distribution is exactly 0.07. That is the one band this router treats as impossible. So a float manufactures the outcome the bullet above exists to refuse. The effect is not cosmetic. T7 run with `Fraction(float(weight))` substituted moves the **lane counts themselves**. The code uses `Fraction`, not `Decimal`, because a ratio of two decimals is not always a decimal. 45.14/20 terminates. 115/86 does not, and that row is real.

### The emitter: a spreadsheet, because there is no API

**Pirate Ship has no API.** That is not a gap to work around. Its three entry points are a typed address, a marketplace connection, and a **spreadsheet import**. The spreadsheet is the only one this project can drive, and it is supported, not improvised.

**`Name` is joined in advance from `FirstName` and `LastName`.** Pirate Ship's auto-mapper is good, but it guesses on the far side of a seam that no committed fixture can test. This project owns the columns, so it does not need Pirate Ship to work out that two columns make one. A recipient addressed by first name alone is a package at the right street with the wrong person on it. The failure is invisible from this end.

**`Order ID` closes the loop.** `Tracking #` and `Carrier` are empty on **all 331 rows** of the export. That is structural, not incidental. So carrying the TCGplayer order number across is what lets the tracking number that Pirate Ship creates be matched back.

**The rubber stamp makes the label the pick instruction.** Pirate Ship prints three in the label corners. So `Box 3 · Card 31` is read from the item already in the picker's hand, not from a second screen. **No label is composed here.** `pipeline/join.py:Position` is the only label formula in this repo. D58 requires the box's whole occupancy to draw one. A second formula here would be the second-renderer failure already recorded three times. A stamp is an opaque string, written out unchanged.

**No length is enforced on a stamp, because nobody has measured one.** Truncating at an invented number cuts the end off a pick instruction, and a wrong shelf then reads as a right one. Too many stamps is refused, because the format makes that knowable.

### Three things the emitter never does, all from D86

D86 states the rule: nothing here is ever defaulted on the operator's behalf.

- **It never selects insurance.** An insurance-shaped column **raises** rather than being dropped. The header is matched folded and stripped, so a differently spelled header cannot slip past. Dropping it silently would leave an operator who thinks they asked for insurance and did not. Insurance is a per-order judgment made inside Pirate Ship, while looking at the card.

**The named list is a deny list over a set that `COLUMNS` already closes. What it adds is the reason.** A refusal that says "not a Pirate Ship column" invites the fix of adding the column. The named refusal does not.

- **It never buys a label.** No API exists to buy one with, and buying would spend money.

- **It never derives a weight.** This is the one most likely to be "fixed" later. The obvious candidate is `Product Weight`, and it is wrong **in the expensive direction**. The catalog constant counts the card stock, not the mailer, the toploader or the tape. So it is a **lower bound**. Writing it buys postage for less than the package weighs. The package is then returned, or postage is due at the far end, weeks later. `Package Weight` is whatever the caller measured. It stays blank until the caller measures it. Pirate Ship's import sets one weight across every row after the fact. A number from a scale belongs there.

T7 asserts the blank **on an order routed by its weight**, so the temptation is strongest where the assertion applies. The first draft took the first order in the lane and passed by accident. 58 of the 126 carry no weight at all. So it asserted only that a blank column stayed blank.

### Buyer PII passes through these two modules

Names and addresses enter as arguments and leave as the bytes the caller asked for. Neither module reaches `store/`, and neither caches. The order ledger may keep them: D326 (the TCGTracking pipe) keeps every field the imports return. These two modules still store nothing. `render` returns **bytes, not a path**, so a buyer's name never has to touch a disk. `write_csv` is the one function that writes, and only where it is told to.

### The one-way edge, and why this is two modules

`shipping.py` imports `pirateship.py`, never the reverse. So the Pirate Ship format knows nothing about TCGplayer, and the Bridge can feed it unchanged. `tcgcsv.py` is the precedent: a foreign format gets its own module.

### A stopgap, to be RETIRED rather than tuned

**The export has no line items.** It has no SKUs and no product names, only `Item Count`. This was confirmed against a real export. That is why a weight ratio is the best signal available, and not a proper answer. `pipeline/orders.py` already answers the same question correctly, from declared line kinds (`OrderResolution.ships_in_an_envelope`). The day a feed supplies line items, **the cut here is the thing to delete, not the thing to re-fit.**

### It is a library, not a feature

No route, no client function in `app/src/server.ts`, and no screen reaches either module. By `CLAUDE.md`'s rule that a route is not a feature, it is **not landed**. This entry says so, so a green harness is not read as a shipped lane. The remaining half is unfinished work of this task, not a follow-up to it. `docs/specs/shipping-export.md` said that nothing reads this file and nothing reads the fixture. That is now false for the second half and still true for the first. The spec is amended to say which.

### What would reopen this

**Line items, which retire the cut.** **A measured stamp length**, which makes the unenforced limit enforceable. **Or Pirate Ship refusing the file.** No committed fixture can test that, because nobody has fed their importer this CSV. It has the same standing as T6's synthetic composites. It is also why `Name` is joined in advance.

### This entry's number

Its number is free now that the number below it has merged. Two unmerged branches claimed it when this was written. That is the heading collision D16 records, in progress again. **The owner's rule: a session renumbers its OWN branch, never another's.** That is narrower than D16's renumber-by-position rule, and it does not conflict with it. D16 settles headings that have already landed. This rule settles who yields before they land: the incoming branch, always. The alternative is each session moving whichever entry it finds easiest. Then a cited id points at a different entry.

Lane order stays; phones open every lane folded; the rule is said once.
