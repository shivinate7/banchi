## D177 — Prices are pruned by press, never rule

**Pruning `inventory/prices.json` against the cards a join can match is refused.** A prune is a preview the operator is shown, and a button the operator presses. The live-book group is separated by name and never selected by default.

The question was open for a good reason. `cli/cmd_join.py` records the asymmetry in its comment: *"Nothing here can see the other boxes, so nothing here may remove."* That comment is scoped to a join over one drawer. A store-wide join removes that ignorance, so it looked as if it removed the objection too. It does not. The figures below come from one `.backup` snapshot of the store and the corpus file.

### The argument

**The corpus and the store answer two different questions, and pruning assumes that they answer one.** The store holds the cards this rig has photographed. The corpus holds every pricing answer the operator has given. Since D109 they deliberately diverge. `reconcile --live` writes a listing record for every SKU TCGplayer holds, with `pushed` and `staged` at 0. That lets the store remember listings it never photographed. **So "no card matches" is not evidence that an answer is junk.**

**Measured: 430 answers. 419 survive, and 11 would be deleted. Zero of the 11 are safe.**

- **7 are prices on listings live on TCGplayer now**, worth $192.52. Five of the seven are not cards. They are a One Piece booster pack at $27.50 and another at $20.49. Also an illustration box at $84.99, a Riftbound playmat at $39.79, and a sleeve bundle at $16.47. They have no card number, no rarity and no photograph. No path through `identify` reaches them. **No store-wide join, however complete, can match these rows.** They are not leftovers a better join would resolve. A card-matching rule would delete them on its first run and on every run after.
- **3 sold out of a box that was then deleted**, worth $8.75. This took two events, not one. A sold card's record keeps standing and keeps matching. `pipeline/join.py`'s `IdentifiedCard.committed` says so. **294 sold card records, 113 distinct SKUs, and none of them among the eleven.** The box delete orphaned these three. Box number 1 has been created and deleted four times.
- **1 is an orphan nothing in the tree can name**, worth $27.00. Only older live exports still on disk identify `C-4669926` as a One Piece "Double Pack Set Vol. 11". It was live at quantity 3, asking exactly the $27.00 the corpus holds, until it left the book.

**The eleven carry 2.70% of the corpus's typed rows and 28.78% of its typed money.** Their mean is $20.75 against the corpus's $1.95, a factor of 10.6. The skew is not chance. **The expensive answers are disproportionately the ones with no card behind them, because the expensive things in this store are sealed product and accessories.**

**The exposure grows rather than converging.** The live book went from 759 rows to 853 in six days. **350 of those 853 SKUs have no card record here:** 229 Pokemon, 76 Riftbound, 41 One Piece, 2 YuGiOh, 1 Playmat and 1 Card Sleeves. Ten are answered today, because the live lens is new. Every row the operator prices on it joins the group. **The prune list is not eleven rows heading for zero. It is eleven heading for 350.**

**The holds survived on luck, not on the rule.** All 23 `bullish` holds are matched today. Two of them have no copy left on hand, and match only because their records still stand. **Had either been in box 1 at the snapshot, a prune would have deleted a judgment the operator wrote in words.** The card would go out at the rule's price on the next `emit`, with nothing said.

### What this decides

**A prune rule keyed on card matching is refused outright.** Not on a join, not on a schedule, and not behind a flag that defaults on.

**The permitted shape already exists:** `pipeline/corpus.py:clearable`. The owner's request for a mass-clear button produced it. It previews, and the operator points it. One press spends it. Holds and `unknown`-channel answers are excluded by kind. An undated answer is named, not guessed at. **A prune takes that shape or it does not land.** A prune preview must show three things. Each is earned by a row above.

1. **Whether the SKU is live on TCGplayer now.** This is the difference between a leftover and the asking price on stock for sale this minute.
2. **Why no card matches, told apart:** sale, box delete, never photographed, export scope, or D36 refusing to read the run at all. The three orphans needed two events to become one.
3. **Whether the answer is dated.** Two of the three carry no `at`. `clearable` already refuses to let an age filter touch those.

**A prune must never treat the listings table as proof that a SKU was never live.** The earliest first sighting in this store is `2026-09-12T05:32:37`. So `C-4669926` was live for four days and has no listing record. **D109's remembering started after it left the book.**

### What this does not decide

**The store-wide join is not touched.** It remains worth building for every reason it was proposed. It does not buy a license to delete. **Nor does this reopen D86.** One file for the whole store is keyed by SKU. That is why it can hold an answer for a listing no box ever contained. That property is the feature, not the leak.

**The measurement is analytic, and it says so.** No store-wide join exists to compare against. So the figures differ from a real store-wide join in seven ways. Six of those ways make the real prune list longer, never shorter. The seventh is the sealed product no join can reach. **The eleven is a floor.** The model: a SKU survives if some card record carries it as its settled identity and the current catalog export still has that row. A SKU also survives if the ladder could reach it from a card with no settled identity yet.

1. **No store-wide join exists to compare against.** `cli/resolve.py:load` reads one run directory, never the store. Walking card records uses settled identities. Walking every run's identifications and realigning re-derives them. The two give different answers, so the join's SKU set is still a design choice.
2. **A run-assembled join can refuse a run.** D36's `refuse_reallocated` refuses a run whose box number was deleted and reused. "This run may not be read" differs from "no card matches". A prune rule must not collapse them.
3. **`bid` cannot rescue a buried record.** D20's box index was migrated in after the box was deleted. The buried payloads carry no `bid`. The `buried` history line is the only evidence they belonged to another box.
4. **The ladder probe over-approximates on purpose.** For cards with no settled SKU, it took the union of every catalog row their number key or name key could reach. The real ladder narrows by set hint, rarity and finish. Over-approximation is the safe direction for a question about deletion.
5. **The catalog scope is the most favorable one.** Both exports were full-category. D76 means that a real run fetches a narrower scope, which makes the prune list longer.
6. **A stored SKU the export has dropped falls to the ladder.** It is never guessed. None was missing in the snapshot. One would appear the moment a set rotates out of a fetched scope.
7. **Sealed product and accessories never enter a join.** This runs the unsafe way. It is a permanent property of the inputs, not an artifact of the measurement.
