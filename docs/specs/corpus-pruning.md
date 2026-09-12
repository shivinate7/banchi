# Corpus pruning — what it would delete, read off the store

## Status

**Recorded, not built, and the recommendation is that pruning never be automatic.** This file
is a measurement, not a plan. Nothing here prunes; no code was written; the owner's
`inventory/prices.json` was read and never opened for writing, and the store was read through
a `.backup()` snapshot in a scratchpad.

**Taken 2026-09-12, against these exact bytes.** The store moves under a measurement — this
repo has watched two figures go stale inside a single press — so every number below is
reported against a digest and is expected to drift, not to be maintained:

| | path | sha256 |
| --- | --- | --- |
| the corpus | `inventory/prices.json` | `1cea3cbd5ae62b22d410f682da988e56bd904c5a3e19d8416f87d8dd28bc2411` |
| the store | `inventory/store.sqlite` | `b9e983c7523017341cdb1bd52352c676f539439dd38307aa25dda4717213002a` |
| Pokemon catalog | `runs/2026-08-24-box2-01/export-tcgplayer-20260912-074105-7410f561.csv` | `7410f561dc71…` |
| Riftbound catalog | `runs/2026-09-12-box4-01/export-tcgplayer-20260912-074950-df21a601.csv` | `df21a601b9e1…` |
| the live book | `inventory/.live/live-tcgplayer-20260912-081253.csv` | `67ed5658de01…` |

**The store moved while this was being briefed, which is the point of the digest.** The brief
this was taken from gave 289 sold cards; the snapshot holds **294**. Five sales landed in
between. The corpus figures it gave — 407 typed prices, 23 `bullish` holds, 269 answered on
one day — all reproduce exactly. **Do not repair the numbers below against a later store.
Retake the measurement (section 10) and date the new one.**

**And it moved again during the measurement, in a way a digest alone reports as a false
alarm — which is worth recording on its own.** At 13:24:56 the store's digest became
`b0ba865d7a…`, and the file grew by three pages. **Nothing in this file went stale.** Checked
table by table: `cards`, `boxes`, `listings`, `events`, `orders`, `queues`, `identifications`
and `fulfilment` are all byte-identical in content to the snapshot. The only row that changed
is `meta.schema`, 2 to 3, and the only object that appeared is an empty `submissions` table
with its index — another branch's additive migration, applied by the owner's live server when
its supervisor re-executed. **So a bare digest comparison would have condemned a measurement that is still exactly correct.** A retake should diff the tables it read, not the file: section
10 says how.

## 1. What "pruning" means, for a reader who has not been in the code

`inventory/prices.json` is one file holding **every pricing answer this store has ever
given**, filed by SKU — a SKU being TCGplayer's id for one exact printing of one card in one
condition. There are two kinds of answer in it. A **price** is a number somebody typed. A
**hold** is a refusal to sell yet, with a reason on it — all 23 in this file say `bullish`,
meaning *this is worth more than the rule thinks, do not list it cheap*.

**That file only ever grows.** When the pipeline joins a box against TCGplayer's catalog it
adds answers for cards it saw, and it removes nothing. `cli/cmd_join.py` says why in its own
comment, and the reason is good: a join is pointed at **one drawer**, so it has no way of
knowing whether an answer it does not recognize belongs to a card in some other drawer or to
no card at all. Deleting on that ignorance would throw away a price for a card sitting two
boxes over.

**Pruning is the idea that a join which sees the WHOLE store could safely delete the
leftovers** — because a join that sees everything genuinely can tell "no card here has this
SKU" from "not in this drawer." That store-wide join is planned and not built.

**So the question this file answers is: if we did that, what exactly would be deleted?** Not
how many. Which ones, and what each one is worth. Because the things that would go are typed
prices and deliberate holds, and both of those are somebody's time.

## 2. The answer

**430 answers examined. 419 would survive. 11 would be deleted. Not one of the 11 is safe to
delete, and 7 of them are prices on listings that are live on TCGplayer right now.**

| | count | of 430 | typed value |
| --- | --- | --- | --- |
| would survive a store-wide join | 419 | 97.4% | $565.00 |
| **would be deleted** | **11** | **2.6%** | **$228.27** |
| — safe to delete | **0** | 0.0% | $0.00 |
| — unsafe: live listings this store never photographed | 7 | 1.6% | $192.52 |
| — needs a human's eye | 4 | 0.9% | $35.75 |

**The eleven rows carry 2.70% of the corpus's typed rows and 28.78% of its typed money.**
Mean price on a row that would be deleted: **$20.75**. Mean across the whole corpus:
**$1.95** — the rows pruning reaches are **10.6x** the average answer. Median $16.47 against
$0.29. This is not a coincidence and section 5 explains it: the expensive answers in this
file are disproportionately the ones with no card behind them, because the expensive things
in this store are sealed product and accessories, which no camera here has ever photographed.

**Pruning would delete three rows in every hundred — and twenty-nine cents on every dollar.**

## 3. What is in the corpus, before any pruning

| | count |
| --- | --- |
| answers | 430 |
| — typed prices | 407 |
| — holds (`bullish`) | 23 |
| — `unknown` channel (a card the catalog could not price) | 0 of 430 |
| typed prices carrying no `at` date | 20 |
| holds carrying no `at` date | 19 of 23 |

Typed prices by the day they were answered — the concentration the owner already knows about:

| day | prices | |
| --- | --- | --- |
| 2026-09-07 | 269 | 66.1% |
| 2026-09-10 | 59 | 14.5% |
| 2026-09-11 | 33 | 8.1% |
| 2026-09-12 | 26 | 6.4% |
| (no date) | 20 | 4.9% |

Policy in the file today: `rule=match`, `basis=market`, `threshold=$0.29`,
`sub_threshold={"flat":"0.29"}`.

## 4. The eleven rows, named

### 4a. Seven live listings this store never photographed — DO NOT PRUNE

**This is the group to be loudest about.** D109 means the store deliberately remembers
listings it never photographed: `reconcile --live` reads the operator's My Pricing export and
writes a record for every SKU TCGplayer holds, leaving `pushed` and `staged` at 0 because
this pipeline sent none of it. **Those are the operator's own live listings.** Pruning them
deletes the asking price on stock that is for sale this minute.

| SKU | what it is | live qty | price | answered |
| --- | --- | --- | --- | --- |
| `8868403` | One Piece Card Game Illustration Box Vol. 4 | 1 | $84.99 | 2026-09-10 |
| `9342228` | Riftbound Playmat — Lunar Revel 2026 | 2 | $39.79 | 2026-09-10 |
| `6768597` | Paramount War — Booster Pack (One Piece) | 4 | $27.50 | 2026-09-07 |
| `C-4619147` | Paramount War — Booster Pack (One Piece) | 6 | $20.49 | 2026-09-07 |
| `9342244` | Riftbound Sleeves — Lunar Revel Bundle 2026 | 2 | $16.47 | 2026-09-07 |
| `8948210` | Drifblim - 006 (Cosmos Holo), ME Promo | 4 | $2.99 | 2026-09-10 |
| `8927762` | The Arena's Greatest, 290/298 Origins | 3 | $0.29 | 2026-09-07 |

**Five of the seven are not cards.** A booster pack, an illustration box, a playmat and a
sleeve bundle have no card number, no rarity and no photograph — there is no path through
`identify` for any of them and there never will be. **No store-wide join, however complete,
can ever match these rows.** They are not stale leftovers that a better join would resolve;
they are permanently unmatched by construction. A prune rule keyed on "no card matches" would
delete them on its first run and on every run after.

**And the exposure grows.** The live book has gone from 759 rows to 853 in six days. **350 of
those 853 SKUs have no card record in this store at all** — 229 Pokemon, 76 Riftbound, 41 One
Piece, 2 YuGiOh, 1 Playmat, 1 Card Sleeves. Only 10 of the 350 are answered in the corpus
today, because the live-pricing lens is new. Every one the operator prices on `#/pricing`'s
live book joins this group. **The prune list is not eleven rows converging on zero; it is
eleven rows on their way to three hundred and fifty.**

### 4b. Three sold out of a box that was then deleted — needs a human's eye

| SKU | card | pushed | live | price | answered |
| --- | --- | --- | --- | --- | --- |
| `9201544` | Irresistible Faefolk, 112/219 Unleashed, NM Foil | 2 | 0 | $5.47 | **no date** |
| `9191200` | Hwei, Brooding Painter, 080/219 Unleashed, NM Foil | 3 | 0 | $2.99 | **no date** |
| `9197384` | Determined Sentry, 111/219 Unleashed, NM Foil | 1 | 0 | $0.29 | 2026-09-10 |

These are the only three rows where "the card is gone" is literally true, and it took **two**
events, not one. Each was identified in run `2026-08-29-box1-01`, sold, had its photograph
reclaimed (D89), and then — on 2026-09-11 at 21:39:20 — **its record was buried when box 1
was deleted** (D134). Box 1 at that moment was named `UNL Rares` and held 133 cards; all 133
were buried, 34 of them sold records covering 16 distinct SKUs. Box number 1 was then reused
19 minutes later for `WB1 R3`, which holds 322 cards today.

**A sale alone does not do this, and that matters for any prune rule.** A sold card's record
keeps standing in its box and keeps carrying its SKU, and `pipeline/join.py`'s
`IdentifiedCard.committed` is explicit that *"a committed copy still matches and still counts
in the report — it is a real card at a real position."* Measured: **294 sold card records,
113 distinct SKUs, and 0 of those 113 are among the eleven.** All 294 are matched. **A sale
is not why any answer in this corpus is orphaned. The box delete is** — and the three rows
above are the only place in this store where a box delete and a sale have coincided.

Two things argue for keeping these three anyway:

- **Two of the three carry no date.** `pipeline/corpus.py:clearable` already refuses to let
  an age filter touch an undated answer, and says why: they are almost certainly the oldest
  answers in the file, and *"almost certainly" is not something this repo clears money on.*
  A prune rule that deletes them is overriding a judgment the mass-clear already made.
- **The cards are in active circulation here.** All three are `Unleashed` rares, and **722
  card records in this store are `Unleashed` rows.** Box 4 was joined four times on
  2026-09-11 and again on 2026-09-12. The next copy of Hwei that comes off the feeder wants
  exactly this answer pre-filled, and that is what the corpus is for.

### 4c. One orphan nothing can name — needs a human's eye

`C-4669926`, $27.00, answered 2026-09-07T06:50:37. **No card record, no listing record, no
history event, and it is in neither catalog nor the current live book.** The only reason
this file can tell you what it is at all is that the older live exports still on disk can:

> **`C-4669926` — "Double Pack Set Vol. 11", set "The Time of Battle", One Piece sealed
> product.** Live at quantity 3, asking $27.00, in every live export from
> `live-tcgplayer-20260906-161847.csv` through `live-tcgplayer-20260910-034806.csv`. **Absent
> from `live-tcgplayer-20260912-053237.csv` onward.**

The corpus answer is $27.00 and the price it was live at was $27.00, so this is the operator
pricing their own listing and that listing then leaving the book — three copies sold, or the
lot delisted. **Only the operator knows which.**

**It also exposes a real gap in D109, worth recording on its own.** This SKU has no listing
record even though it was live for four days. **The earliest first sighting anywhere in this
store is `2026-09-12T05:32:37`** — 489 of the 567 listing records carry a `first_seen_live`
and every one of them is stamped that moment or `2026-09-12T08:12:53`, the two
`reconcile --live` runs of that morning. **D109's remembering started one export too late for
this SKU**, which had already left the book. So a prune rule that trusted the listings table
to mean "was this ever live" would have called this row junk, and it was a $27.00 listing
eight days ago.

## 5. What this measurement is, and where it differs from a real store-wide join

**The difference is itself a finding, and it runs in the safe direction for six of the seven
ways it differs.** What was computed:

> A SKU **survives** if some card record in the store carries it as its settled identity and
> the current catalog export still has that row; **or** if the ladder could reach it from a
> card that has no settled identity yet. Everything else would be deleted.

That models rung 0 of `pipeline/variant.py`'s ladder, which is what `cli/resolve.py` feeds a
join: it reads `sku` + `condition` off the record into `IdentifiedCard.answered_sku` and
`join_batch` resolves to that row before the ladder runs. Seven caveats:

1. **There is no store-wide join to compare against.** `cli/resolve.py:load` reads
   `run.read_identifications()` — a run directory, not the store. Nothing in this tree walks
   all cards. **So the store-wide join's SKU set is a design choice PR G still has to make**,
   and the two obvious designs give different answers: walking card records uses settled
   identities, while walking every run's identifications and realigning re-derives them.
2. **A run-assembled store-wide join would be REFUSED on the run that produced 4b's three
   rows.** D36's `refuse_reallocated` refuses a run whose box number was deleted and reused,
   and box number 1 has been created and deleted **four** times: 53 cards deleted 2026-08-25,
   `Test` deleted 2026-08-27, `UNL Rares` deleted 2026-09-11, `WB1 R3` standing now. Run
   `2026-08-29-box1-01` was over `UNL Rares`. **"This run may not be read" is a different
   answer from "no card matches," and a prune rule must not collapse them.**
3. **`bid` cannot rescue it.** D20's never-reused box index was migrated in at
   2026-09-11T23:28:13 — **after** `UNL Rares` was deleted at 21:39. Today's box 1 carries
   `bid` 1. **All 198 buried payloads carry no `bid` at all.** The evidence that those three
   records belonged to a different physical box is the `buried` history line and nothing else.
4. **The ladder probe over-approximates, deliberately.** For the 173 cards with no settled
   SKU it took the union of every catalog row their number key or D35's name key could
   reach — all conditions, all variants — where the real ladder narrows by set hint, rarity
   claim and finish and picks one row. **Over-approximating is the safe direction for a
   question about deletion**, and it came back empty regardless (section 6).
5. **The catalog scope used is the most favorable one that exists.** Both exports are from
   2026-09-12 and both are full-category (1,614 Pokemon rows, 10,191 Riftbound). D76 means a
   real run fetches to a narrower scope. **A narrower scope makes the prune list longer,
   never shorter**, so the eleven is a floor.
6. **A stored SKU the export has dropped would fall through to the ladder** rather than be
   guessed at — `answered_sku`'s own contract. Measured: **0 of 567** stored SKUs are missing
   from the current exports, so this caveat does not bite today. It would the moment a set
   rotates out of a fetched scope.
7. **Sealed product and accessories can never enter a join at all** (4a). This is the one
   caveat that runs the *unsafe* way, and it is why the recommendation is what it is: it is
   not an artifact of how this was measured, it is a permanent property of the inputs.

## 6. What was checked and came back empty

Each of these is a count over a real population, not over nothing:

- **Holds that would be deleted: 0 of 23 examined.** Every `bullish` hold is still matched by
  at least one standing card record. **Two of the 23 have no copy left on hand at all** —
  `8925742` (1 record, sold) and `9405753` (2 records, both sold) — and **they still match,
  because their records still stand.** The 23 holds are the most expensive thing on this list
  to lose and today pruning reaches none of them. **That is true because box 1 happened not
  to contain one. It is luck, not a property of the rule** — had one of those two been in
  `UNL Rares` on 2026-09-11, a prune would delete a judgment the operator wrote in words, and
  the card would go out at the rule's price on the next `emit` with nothing said.
- **SKUs whose every copy has departed but whose records still stand: 16 examined, 6 of them
  answered in the corpus, 0 of them among the eleven.** This is the population that a prune
  rule reading "nothing on hand" instead of "no record" would delete. **It is five times the
  size of the group that is genuinely orphaned**, which is the whole argument for matching on
  the record rather than on the shelf.
- **Answers in the `unknown` channel that would be deleted: 0 of 0 examined** — the corpus
  holds no `unknown`-channel answers at all right now, so `cli/cmd_join.py`'s seeded
  `Answer(value=None, channel="unknown")` rows are not part of this question today. They
  would be the moment a join runs against a card the catalog cannot price, and
  `pipeline/decisions.py:blocking` reads that table to refuse an `emit` — so a prune rule must
  exclude them by channel exactly as `clearable` does.
- **Prune candidates the SKU-less cards' ladder could reach: 0 of 11.** The probe is not
  vacuous: **173 cards were probed, 165 of them reached at least one catalog row, and the
  union is 1,430 distinct catalog SKUs** (median 10 rows reached per card, max 40). **None
  of those 1,430 is answered in the corpus at all.** So the empty result is a real negative.
- **Stored SKUs the current export has dropped: 0 of 567 examined.**
- **Card records pointing at a box that no longer exists: 0 of 2,535 examined.** Every one of
  the 12 runs named by a card record resolves to a live box; the 164 buried records that were
  *moved* rather than sold all name a successor position, and box 6's 65 cards are in box 3.
- **Retired cards among the prune candidates: 0 of 1 examined.** This store has exactly one
  retired card, it carries no SKU, and it is in no way implicated.

## 7. The value at stake

**$228.27 of typed prices, against a whole-corpus total of $793.27 across 407 rows.**

| group | rows | value |
| --- | --- | --- |
| live listings never photographed here | 7 | $192.52 |
| sold, then box deleted | 3 | $8.75 |
| orphan nothing can name | 1 | $27.00 |
| **total** | **11** | **$228.27** |

**The holds are not in that figure and cannot be.** A hold has no price on it — it is a
refusal to sell with a reason attached, and its value is whatever the card turns out to be
worth once the operator stops holding it. There are 23 of them and pruning reaches none today.
**What a lost hold costs is not a number on this page: it is the card going out at the rule's
price on the next `emit`**, which is a money consequence in the direction that costs, and it
is silent.

## 8. Recommendation

**Pruning should never be automatic. Not on a join, not on a schedule, not behind a flag that
defaults on.**

The load-bearing reason is not the eleven rows. It is that **the corpus and the store answer
two different questions, and pruning assumes they answer one.** The store holds the cards
this rig has photographed. The corpus holds every pricing answer the operator has given — and
since D109 that deliberately includes listings no camera here ever saw. **"No card matches"
is therefore not evidence that an answer is junk.** For 7 of today's 11 it is evidence of
nothing at all: they are booster packs, an illustration box, a playmat and sleeves, and no
join will ever match them because they cannot be photographed. A rule keyed on card-matching
deletes them on its first run and on every run forever after.

If a control is wanted, **the shape already exists and is the right one**:
`pipeline/corpus.py:clearable` is a preview the operator points and one press spends, with
holds and `unknown`-channel answers excluded by kind and undated answers named rather than
guessed at. The owner's own ruling produced it — *"Just give me a mass-clear button"* — and
the same ruling applies here. **A prune should be a list the operator is shown and a button
they press, with the live-book group separated out by name and never selected by default.**

Three things a preview must show, each earned by something above:

1. **Whether the SKU is live on TCGplayer right now** — 4a. This is the difference between a
   leftover and the price on stock that is for sale.
2. **Why no card matches, told apart** — sale, box delete, never photographed, or export
   scope. 4b needed two events to become orphaned, and section 5's caveat 2 is a fifth
   reason that is not about cards at all.
3. **Whether the answer is dated** — 2 of the 3 rows in 4b are not, and the mass-clear
   already refuses to age-filter those.

And one thing it must not do: **treat the listings table as proof a SKU was never live.**
`C-4669926` was live for four days and has no listing record, because D109's remembering
started after it left the book.

## 9. What is BUILT, RECORDED, NEITHER

- **BUILT: nothing.** No code, no route, no screen. Deliberately — the brief was a preview
  for a decision, and building the control before the decision is made is the thing this repo
  refuses.
- **RECORDED: this file, and the decision entry beside it.** The 11 rows, the four groups,
  the $228.27, the six empty categories with their populations, the seven ways this differs
  from a real store-wide join, and the three things a preview must show.
- **NEITHER: the preview control itself, and the store-wide join it would read.** The join is
  PR G of the unboxing plan. The control has no route, no client function and no screen, and
  under this repo's own rule that means it is not a feature and must not be reported as one.

## 10. How to retake this measurement

Everything above came from three read-only inputs: `inventory/prices.json` parsed by
`pipeline/corpus.py:Corpus.read` with an explicit path, a `.backup()` snapshot of
`inventory/store.sqlite` taken through a `mode=ro` connection, and the export files named in
the table at the top. **No write of any kind was made to the owner's data, and no
identification was submitted.** `prices.json` carries the same digest it did before this file
existed.

**The digests date the result; they do not invalidate it.** A schema migration or a WAL
checkpoint moves the store's digest without touching a row, which happened here once
already. **So the test for staleness is a content diff of the eight data tables, not a hash
of the file** — snapshot the store, hash each table's rows in primary-key order, and compare.
Anything that comes back identical leaves every count above standing. When a count does
move, replace it and date the new one; **do not edit a figure to match a later tree, which
is what this repo means by a measurement being evidence.**
