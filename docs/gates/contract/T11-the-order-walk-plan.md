### T11 — The order walk plan

New 2026-09-17, with `pipeline/walkplan.py` and `docs/specs/order-walk-plan.md`. **Pass: the plan is the proven optimum on a fixture greedy gets wrong. A section holding one
copy never satisfies a demand for two. An unfillable SKU lands in the shortfall rather
than making the instance infeasible. A pooled game is one stop, last, and never a
section. And `exact` comes back false when the budget cannot be met.**

**There is no T10, and the gap is deliberate.** T10 is spelled for the Intelligent Mail
barcode encoder. That encoder was shelved on the owner's ruling with `pipeline/imb.py`, on
branch `claude/tcgtracking-in-house-a7cb43` at c9391e1, and DEBT26 names it as T10 throughout.
This repo renumbers its own ids and never another branch's. So the shelf keeps its number and
the harness takes the next one. `harness/run.py`'s `TESTS` list is the count. The range in
that file's title is the highest id, never a claim that every id between it and 1 exists.

**The inputs are seeded in memory, and that is the whole fixture.** `pipeline/walkplan.py`
reads no file, takes no lock and writes nothing. So a `master.Inventory` and a
`store.orders.Ledger` built by the test are the same inputs the spec's route will hand it.
Every count is small enough to check by eye. Six SKUs over three sections in one box for the
optimum, four cards for the multiplicity case. That is the point of the sizes: a fixture
nobody can verify by hand proves only that the solver agrees with itself.

**Why it exists.** A solver is confidently wrong in a way no screen reveals. A plan that is
one drawer too long renders exactly like a correct one. So does a plan that asks for a copy
the drawer does not hold. The operator finds out at the shelf, and the reach is already spent.
The spec rules deliberately that nothing on screen tells a solved plan from a listed one, in
its own section 10. This test is the only thing that can.

**Each clause of the threshold is a different failure at the drawer.**

- **The optimum** is asserted on an instance where greedy is strictly worse. Three sections
  hold `A B C D`, `A B E` and `C D F`, and one copy of each of six SKUs is wanted. Greedy
  takes the biggest section first and lands on three drawers. The optimum is two. A fixture
  where greedy already equals the optimum goes green over a solver that had quietly become
  greedy. On the owner's own store greedy equalled the optimum at every measured size, so
  that regression is invisible there by construction.
- **Multiplicity** is the set-cover-versus-multicover distinction the spec calls load-bearing
  in its section 5. A section holding one copy of a card the walk wants two of does not cover
  it. Asserted on an instance a set-cover solver answers in one stop where the answer is two.
- **The shortfall** is an unfillable SKU, capped out of the demand before the solve and
  reported rather than made infeasible. On the owner's store 23 of the 59 SKUs their forty
  open orders want cannot be filled at all. A solver that refuses to answer over those
  refuses to answer at all. The test also asserts that `solve` refuses an uncapped demand by
  name, through `Uncoverable`. That refusal was added because removing the cap left every
  other assertion green over a silently partial cover. It was found by mutation, not by
  reading.
- **The pooled stop** is one per game, last, with no box and no section. It is not counted
  among the boxes, under D24 — a code card is a count, not a place. Latent today, because the
  store holds zero code-card records.
- **`exact: false` is reachable**, driven by a budget of zero seconds. A solver that exhausts
  its budget and returns the greedy incumbent without saying so cannot be told apart from one
  that proved the optimum. That is the failure the flag exists to prevent. A flag nobody can
  make false is a flag nobody has tested.

**Every assertion was mutation-tested before it was believed**, under the repo's standing
rule. Five defects were committed into `pipeline/walkplan.py` in turn. They were: shipping the
greedy incumbent, treating the instance as plain set cover, dropping the availability cap, and
two more. The fourth let a pooled stop sort among the drawers. The fifth pinned `exact` true.
Each one turned this test red on the clause that names it.

**What a green T11 does not mean.** It does not mean the plan is fast on the owner's store.
The 27.9 ms figure for all 275 walkable orders was measured there and is recorded in the
spec's section 6. It is not re-measured here, because a timing assertion on a shared CI box is
a flake rather than a guard. A green T11 also does not mean any of this is on a screen. The
route and the screen are separate work, and no code under test reaches a wire.
