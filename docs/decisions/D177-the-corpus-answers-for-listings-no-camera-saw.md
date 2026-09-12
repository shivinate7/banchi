## D177 — The corpus answers for listings no camera here ever saw, so a prune is a list the operator presses and never a rule a join runs

**Pruning `inventory/prices.json` against the cards a join can match is refused. A prune is a preview the operator is shown and a button they press, with the live-book group separated by name and never selected by default.**

The question was open for a good reason. `cli/cmd_join.py` records the asymmetry in its own
comment — *"Nothing here can see the other boxes, so nothing here may remove"* — and that
comment is scoped to a join over one drawer. **A store-wide join removes that specific ignorance**, so it looked as though it removed the objection with it. It does not. The
measurement is `docs/specs/corpus-pruning.md`, taken 2026-09-12 against store
`b9e983c752…` and corpus `1cea3cbd5a…`.

### The argument

**The corpus and the store answer two different questions, and pruning assumes they answer one.** The store holds the cards this rig has photographed. The corpus holds every pricing
answer the operator has given. Since D109 those deliberately diverge: `reconcile --live`
writes a listing record for every SKU TCGplayer holds, `pushed` and `staged` at 0, precisely
so the store remembers listings it never photographed. **So "no card matches" is not evidence that an answer is junk.**

**Measured: 430 answers, 419 would survive, 11 would be deleted, and 0 of the 11 are safe.**

- **7 are prices on listings that are live on TCGplayer right now**, worth $192.52. **Five of the seven are not cards at all** — a One Piece booster pack at $27.50 and another at
  $20.49, an illustration box at $84.99, a Riftbound playmat at $39.79, a sleeve bundle at
  $16.47. They have no card number, no rarity and no photograph, and there is no path through
  `identify` for any of them. **No store-wide join, however complete, can ever match these rows.** They are not leftovers a better join would resolve; they are permanently unmatched by
  construction, and a card-matching rule deletes them on its first run and on every run after.
- **3 sold out of a box that was then deleted**, worth $8.75. This took two events, not one: a
  sold card's record keeps standing and keeps matching, and `pipeline/join.py`'s
  `IdentifiedCard.committed` says so in as many words. **294 sold card records, 113 distinct SKUs, 0 of them among the eleven.** The box delete is what orphaned these three, and box
  number 1 has been created and deleted four times.
- **1 is an orphan nothing in the tree can name**, worth $27.00. Only the older live exports
  still on disk identify `C-4669926` as a One Piece "Double Pack Set Vol. 11", live at
  quantity 3 asking exactly the $27.00 the corpus holds, until it left the book between
  2026-09-10 and 2026-09-12.

**The eleven carry 2.70% of the corpus's typed rows and 28.78% of its typed money** — mean
$20.75 against the corpus's $1.95, a factor of 10.6. That skew is not chance. **The expensive answers in this file are disproportionately the ones with no card behind them, because the expensive things in this store are sealed product and accessories.**

**And the exposure grows rather than converging.** The live book went from 759 rows to 853 in
six days. **350 of those 853 SKUs have no card record here** — 229 Pokemon, 76 Riftbound, 41
One Piece, 2 YuGiOh, 1 Playmat, 1 Card Sleeves. Ten are answered today because the live lens
is new; every row the operator prices on it joins the group. **The prune list is not eleven rows heading for zero, it is eleven heading for three hundred and fifty.**

**The holds survived on luck, not on the rule.** All 23 `bullish` holds are matched today, and
two of them have no copy left on hand — matched only because their records still stand. **Had either been in box 1 on 2026-09-11, a prune would have deleted a judgment the operator wrote in words**, and the card would go out at the rule's price on the next `emit` with nothing said.

### What this decides

**A prune rule keyed on card-matching is refused outright.** Not on a join, not on a schedule,
not behind a flag that defaults on.

**The shape that is permitted already exists**: `pipeline/corpus.py:clearable`, which the
owner's own *"Just give me a mass-clear button"* produced. It previews, the operator points
it, one press spends it, holds and `unknown`-channel answers are excluded by kind, and an
undated answer is named rather than guessed at. **A prune takes that shape or it does not land.** Three things such a preview must show, each earned by a row above:

1. **Whether the SKU is live on TCGplayer right now.** This is the difference between a
   leftover and the asking price on stock that is for sale this minute.
2. **Why no card matches, told apart** — sale, box delete, never photographed, export scope,
   or D36 refusing to read the run at all. The three orphans needed two events to become one.
3. **Whether the answer is dated.** Two of the three carry no `at`, and `clearable` already
   refuses to let an age filter touch those.

**And one thing it must never do: treat the listings table as proof a SKU was never live.**
The earliest first sighting anywhere in this store is `2026-09-12T05:32:37`, so `C-4669926`
was live for four days and has no listing record. **D109's remembering started after it left the book.**

### What this does not decide

**The store-wide join is not touched.** It remains worth building for every reason it was
proposed; what it does not buy is a license to delete. **Nor does this reopen D86** — one file
for the whole store, keyed by SKU, is exactly why the file can hold an answer for a listing no
box ever contained, and that property is the feature rather than the leak.

**The measurement is analytic and says so.** There is no store-wide join to compare against,
so `docs/specs/corpus-pruning.md` §5 names seven ways its model differs from a real one — six
of which make the real prune list longer, never shorter, and the seventh being the sealed
product that no join can reach. **The eleven is a floor.**
