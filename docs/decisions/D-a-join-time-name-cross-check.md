## D-a-join-time-name-cross-check — Measured, not shipped: the join trusts a number that resolves, and the owner asked why

**The ask.** The owner, on seeing the SKU-contradiction check's name-agreement correction:
apply the same correction on the paths that actually use the answer. Not only in a report
someone has to remember to run. Named seams: `pipeline/join.py:_walk` and
`pipeline/pricehistory.py:ProductIndex.find`.

**The seam, found rather than guessed.** `_walk`'s own docstring states the premise
directly. A key that matched never reaches the name rung. That rung is a last resort, not
a peer. A number that resolves is never second-guessed. The owner's own correction
overturned this exact premise, for a different case. Existence is not name agreement. A
number that "resolves" can resolve to the WRONG product, when the read number collides
with a different real card.

**Measured against the owner's real store and two real cached exports** (`inventory/
.exports/riftbound/…csv`, `inventory/.exports/pokemon/…csv`), read-only, no
`pkmnscan` command run:

- 3,297 real, numbered, named cards in catalogued games (riftbound, pokemon).
- 2,636 of them resolve to a catalogue row through the number key alone, with D55's
  set-code repair on a miss. This is exactly how `_walk` resolves them today.
- Of those 2,636, 379 (14.4%) have a number-matched row whose name does not exactly equal
  the card's own stored name (`name_index_key` equality).
- A sibling check already uses a looser tolerance for a legitimate near-miss. Substring
  containment, or a `difflib` ratio of 0.82 or higher. One example: `Repair Specialist`
  beside `Zaun, Repair Specialist`, a champion's short title. Allowing that same
  tolerance here, **134 (5.1%) still disagree.**

**Why this is not shipped.** The 134 remaining disagreements were read by hand, a sample
of 25. Most look like genuine misreads. `Punching Poro` number-matched to `Blade Twirler`
is clearly a different card. A visible minority are close but plausibly distinct products.
This session cannot verify them without the photograph. `Diana, Mount Targon`
number-matched to `Diana, Lunari` names two real champion variants. Neither is obviously
one misread as the other. The owner's own stop condition applies directly here. Their
words: if it moves outcomes that were previously correct, stop and bring it back rather
than shipping it. This session cannot confirm, from a stored name and a CSV export alone,
which of the 134 are true misreads. Some may be legitimate near-name variants outside the
chosen tolerance. Shipping a silent override risks mislisting a currently-correct card.
The owner named that as the one failure mode worse than a wrong report.

**The safe shape this measurement argues for, if built.** Never silently accept a
different row than the number found. Never silently reject a number match either. Add a
rung: a number match whose name disagrees, beyond the tolerance named above, is treated as
a MISS for listing purposes. It falls through to `_walk`'s existing repair-then-name
ladder. It reaches the same review routing a genuine key miss already reaches. This can
only ever ADD a review question over what happens today. It can never change a number
match into a DIFFERENT accepted match. It can never turn a correct auto-list into a wrong
one. Its cost is added review volume, bounded by the 134-of-2,636 measurement above, not a
mislisting risk.

**What is not decided.** Whether 0.82 is the right tolerance for a listing-path rung, as
opposed to a review-report rung. Whether roughly 5% more review volume is an acceptable
cost, in exchange for catching most of that 134's genuine misreads. Whether
`ProductIndex.find`'s own ambiguity rung, multiple hits by number narrowed by name,
already covers part of this and should be reused directly. None of these is answered here.

**What this does not do.** Change `pipeline/join.py`, `pipeline/pricehistory.py`, the
identify path, or any listing outcome. This entry is a measurement and a proposal, not a
build.

Cites D1, D25, D35 (the name rung this seam already has, for the opposite direction), D55
(the set-code repair `_walk` already tries before falling to name), D234, and
`D-a-archive-store-checks` (the tolerance this measurement reuses).
