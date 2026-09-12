## D159 — The band is copies rather than SKUs, the drawer is the first answer, and nothing on hand is dropped

**Built 2026-09-12, on the owner's request and after the store was measured.** Their words:

> *"something i was pondering you build is a way to see at all times just like how we made a
> screen to price / manage quantities unpushed, i want either on that screen or another screen
> (maybe just a pricing feature idk send a suggested task we'll brainstorm this all) that lets
> me immediately see either the most valuable or least valuable cards so maybe i can easily
> start querying them for bulk collection and taking them out of boxes"*

They asked to brainstorm it rather than receive it, so the store was measured first and the
options were put to them.
**Every shaping decision below is a measurement or a ruling, and the measurement came first.**

### What the store actually looks like

Measured on the live store, 2026-09-11, over 2,245 cards on hand:

| band | cards | % of cards | value | % of value |
|---|---|---|---|---|
| $0.00–0.09 | 346 | 18.6% | $21.58 | 0.9% |
| $0.10–0.28 (under the cut-off) | 696 | 37.4% | $123.74 | 4.9% |
| cut-off $0.29–0.99 | 449 | 24.2% | $215.48 | 8.5% |
| $1.00–4.99 | 246 | 13.2% | $624.32 | 24.7% |
| $5.00–9.99 | 61 | 3.3% | $456.34 | 18.1% |
| $10.00–24.99 | 56 | 3.0% | $891.00 | 35.2% |
| $25.00–49.99 | 5 | 0.3% | $195.40 | 7.7% |

Median $0.23, mean $1.36, top card $47.74, nothing over $50.
**The top 5% is 92 cards carrying 53.8% of the value.**
**The bottom 56% is 1,042 cards carrying 5.7% of it.**

### The load-bearing measurement: value clusters by BOX and scatters WITHIN one

| box | name | cards | under cut-off | box $ | $/card | ≥$5 |
|---|---|---|---|---|---|---|
| 1 | WB1 R3 | 322 | 115 | $102.19 | $0.32 | 3 |
| 2 | ME01 C/UC | 542 | **540 (99.6%)** | $58.72 | $0.11 | 0 |
| 3 | WB1 R1 | 644 | 273 | $703.58 | $1.09 | 23 |
| 4 | WB1 R2 | 633 | 12 (2.9%) | **$1,655.30** | **$2.62** | **96** |
| 5 | UNL BBOX C/UC 1 | 104 | **102 (100%)** | $8.07 | $0.08 | 0 |

**Box 4 is 65% of the money.**
**Boxes 2 and 5 together are 646 cards worth $66.79 — those two drawers ARE the bulk, whole.**
But inside a box the head is scattered:

| band | cards | boxes | sections | contiguous runs | cards per reach |
|---|---|---|---|---|---|
| ≥$25 | 5 | 1 | 4 | 5 | 1.00 |
| ≥$5 | 122 | 3 | 12 | 87 | 1.40 |
| ≥$1 | 368 | 3 | 17 | 178 | 2.07 |
| < cut-off | 1,042 | 5 | 19 | 160 | **6.51** |

**The two ends want opposite artefacts, which is why it is one control with two ends.**
The expensive end is a pick list — the top 25 cards are 25
separate grabs across 10 sections — and every row has to carry an address. The cheap end is not
a list at all: 1,042 rows improve on nothing when the honest instruction is *take drawer 2 and
drawer 5*.

### The unit is the COPY, and this is the measurement that settles it

The 122 cards at or above $5 are **38 SKUs**. Rengar, Trophy Hunter at $41.57 sits in three
slots of box 4; Vilemaw at $21.52 sits in seven. The cheap tail's biggest stack is 20 copies.
**A per-SKU list draws a third of the rows and a third of the drawers a hand has to open.**
`pipeline/join.py:uncommitted_positions` already counts positions for
this reason; `GET /pipeline/value` counts them for the same one.

### Nothing on hand is dropped, and the three causes stay apart

**390 of 2,245 cards on hand carry no market price at all** — 17.4% of the store, and box 4
alone hides 215 of them. A ranked view that silently omitted them would be the silent drop this
repo forbids in as many words. Every on-hand card is a row; an unpriceable one carries
`market: null` and a `why` naming which of three causes it is, because each has a different
remedy and a screen that collapsed them would prescribe one thing for three problems:

| `why` | count | what it is | the remedy |
|---|---|---|---|
| `never_identified` | 214 | captured, never put through a run | a run, on `#/runs` |
| `read_nothing` | 172 | identified, and the model returned no name and no number — every one has a photograph, none is in the review or parked queue | a person looking at it |
| `no_reading` | 4 | a SKU this machine has never seen a market price for | a join, or a live fetch |

**A malformed market cell is `no_reading` and never `$0.00`.** `tcgcsv.parse_price` raises on a
cell that is not a number — right where it is used, since every other caller is about to upload
the file — and coercing here would rank the card at the very bottom of the cheap band and sweep
it into a bulk pull. `_market_of` is the non-raising reader, and the harness proved it was
needed: the case was written before the code and the route threw.

### The newest reading wins on a CLOCK, never on a precedence between files

Two sources: each run's `pricing.json` at the table's own mtime — `do_pipeline_pricing` already
establishes that this is the moment a join last read an export — and the newest file under
`inventory/.live`, at the stamp in its own name rather than its mtime, because the stamp travels
with the bytes and an mtime does not.

**The obvious rule — "a live fetch beats a run table" — is wrong on this store today.** The
newest fetch is 2026-09-10 and the newest run table was written 2026-09-11, so a fixed
precedence would serve a day-old figure for every SKU both files carry. Measured coverage: run
tables alone price 1,823 of 2,245 cards on hand (81.2%), the newest live export alone 1,584
(70.6%), the two together 1,855 (82.6%).

### `boxes` is not a rollup of `copies`, and the mean divides by every card

The drawer block counts every card in the drawer including the unpriced ones. Dividing
`per_card` by the priced subset would flatter box 4 — 633 cards, 215 of them unpriced — against
box 2, where every card has a price. The question at drawer level is *is this whole box bulk*,
and that question is about the whole box.

### What the owner ruled in the interview, and what each ruling cost

- **Both ends, one control.** Not two screens.
- **A cross-box list.** *"cross box lists are the direction im trying to take the whole app."*
- **All four band selectors** — a typed price, the store's own cut-off, a top-N percentile, and
  the drawers ranked by value. They were offered as alternatives and the answer was *"i should
  have all the settings i'd like tbh"*.
- **A listed card appears with no distinction.** This is the ruling with the largest consequence
  and it was made on the figure: **70% of the copies under the cut-off are live at TCGplayer**
  (~727 of 1,042), against 34% of the ≥$5 band. The row carries `live` as context and nothing
  filters on it.
- **Read-only now, writes once it has been used.** Taking a card out of a box stays on
  `#/inventory`, where the store already learns that a card has left.
- **Both the drawer rollup and the flat list**, and the operator picks.

### Why it is a lens on `#/pricing` and not a twelfth route

D31 deleted `#/boxes` and `#/pull` for drawing the same records with no relationship between
them, so a new owner-side route needs the strongest argument and this one does not have it.
D105 puts prices where prices are decided. The lens is `#/pricing?band=…`, which is D103's own
mechanism for `?markdown=<stamp>`: `App.tsx` renders under `key={path}` with the query stripped,
so the lens lands under the operator rather than remounting, and it costs no `ROUTES` row —
which matters, because a row there moves three mechanical counts.

**The owner is separately considering renaming `#/pricing` to an Appraisal tab.** Asked how far
that goes in this round, they chose *"build the value list now, rename separately"*. The rename
touches the nav, the palette, `,P`, the `SHORTCUTS` sheet, the route census, the document title
and five documents; it is its own change with its own entry, and nothing here presumes it.

### The band is the client's and the facts are the route's

`GET /pipeline/value` answers one list sorted by market descending, unpriced last, ties broken on
`(box, index)` so a band's rows arrive in walk order within each price.
**All four selectors are slices of that one order.**
Computing them server-side would be four answers a screen has to keep
in step with a sort it is already drawing, a percentile cannot be taken without the whole list
anyway, and two sorts of one list is two places for a tie-break to differ.

It is a read and it presses nothing: no child, no socket, no lock, no write. Measured at 0.11s
and ~739KB over 2,245 rows, the same order as `GET /pipeline/pricing` (~909KB across eight
tables) and fetched once rather than polled for the same reason.

### What is NOT built, named rather than left to be discovered

- **No write.** The operator ruled it read-only for now, and the reopening condition is theirs:
  having used it. A press that marks a copy pulled would need a receipt, a way back, and an
  answer to what a pulled-but-still-listed card means for the ~727 live copies under the cut-off.
- **No virtualization.** The screen draws 1,042 rows at the cheap end where `#/pricing` already
  draws ~423 SKUs without virtualizing (D103 measured that objection and it did not survive
  contact). If it becomes a problem it will be a measurement, not a guess.
- **No second price basis.** It ranks on market. The corpus answer — what the operator decided
  to ask — rides on the row beside it, because D86 makes those two different facts and this
  screen would be claiming they are one if it ranked on either indiscriminately.
