## D-a-postings-view-shelved — The posted-price view is wanted, and it is shelved until there is a history to draw

**The owner's ruling, 2026-09-20.** Asked whether the recorded posting history should get a
screen now, they answered: *"I do but record it shelved for now."* This entry is that record.
It exists so the next session finds a decision rather than a gap, and does not re-ask.

**What the store holds today.** D243, every posted price is recorded, landed earlier the same
day. It is append-only and it starts from empty. A measurement taken read-only against the
owner's real store at that moment found the shape a view would have to draw:

- **The `price_postings` table holds zero rows.** It records only presses made after D243
  landed, and no price has been posted since. Re-verified read-only, 2026-09-20.
- The store holds 914 distinct SKUs.
- Seven markdown worklists sit on disk. Exactly one of them was ever applied: it alone carries
  an `import.csv` and a receipt, and that file names 342 SKUs. Those 342 prices are
  recoverable from a file, never from the table.
- So no name has two recorded asks, and 572 of 914 have none at all.
- Every SKU's first posted price is gone. D243 states why: the number is composed once, into
  a CSV cell, and nothing keeps a second copy.

**Why that argues for shelving rather than building.** A screen drawn against this table today would
draw nothing at all, and a screen drawn against the one recovered file would draw a single dot
per name and no line. Neither teaches a reader anything the current price does not already
say. Worse, it would fix a shape now, against a single point, that the real data has
not yet had a chance to contradict. The repricing cadence, how many presses a name typically
sees, and whether the interesting comparison is against the market line or against the
previous ask are all unmeasured. Each is cheap to measure once the rows exist and expensive to
guess now.

**What un-shelves it.** A name with a real posting history. The honest trigger is the second
recorded posting for any SKU, which arrives the first time a price this store already posted
is changed and pressed again. That is a `price_postings` count exceeding its own distinct-SKU
count. Nothing watches for this today, and nothing is asked to: the next session that reads
this entry can check it in one query.

**Where it would go, when it is built.** Not settled, and deliberately left open. The owner
was offered two homes and chose neither, because they chose to wait. Both remain live options.
The per-product page already draws the market line with the owner's own fills marked on it, so
a posted-price mark is a third series on a timeline that exists. A section on Sales sits beside
what sold and what is unsold, but Sales is already over its own visible-word ceiling, which is
an open question in its own right.

**What this entry does not do.** It changes no code. It records no new capability. `store/
postings.py` and its writers stay exactly as D243 built them, and they keep recording. Nothing
here slows the accumulation this shelving is waiting on.

Cites D243 (every posted price is recorded, and the row is never touched again), D86 (the
pricing answer is one file for the store, newest-wins, which is why the history was lost),
D62 (the price history's ranges are never merged, which governs any series this view would
later draw), D194 (the visible word count on every owner screen may only go down), and D227
(the per-product history page, one of the two homes named above).
