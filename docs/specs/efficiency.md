# Efficiency: reads cost what they return

Governed by D173 (a rule that can be enforced is) and D88 (SQLite and one transaction per write). Built: no. Each check below lands in its own lane.

A read must cost what it returns, not what the store holds. The owner's store once made `GET /capture/sitting` take up to 71.6 s, because each card rebuilt the box layout (PR 711). This spec holds the checks that stop that class of cost, and the rule for changing them.

## The three checks

- **Server read budget.** `harness/tests/t7/read_budget.py` counts work per read route: SQL statements on every connection, store opens, box walks and export parses. It counts at two store sizes, S and 2S. A counter that should not grow must be equal at both. Each route has an exact budget, and its expected status. EXPLAIN QUERY PLAN flags a full-table scan not on `SCAN_ALLOWED`. The check never asserts wall time. A write keeps its one transaction (D88), and the budget reads only.
- **Expensive calls in loops.** The `loop expensive` row of `make docs-audit` flags a store call inside a loop body, and a same-module helper called in a loop that makes one. `LOOP_EXPENSIVE_ALLOWED` lists each known site with a reason.
- **Client request budget.** `app/tests/request-budget.spec.ts` walks every `ROUTES` screen. It caps reads in flight at 4 and polls at one per 3 s. It allows one read per identical GET, and it caps the reads after a sale or a review answer. A screen aborts its reads when it is left. `app/tests/request-budget-allow.json` pins each known overage at its measured count.

## The ratchet

- Every allow list pins a number, and it only goes down. A measured value above its pin fails. A value below it fails as stale, with "lower to N".
- The commit that makes a read cheaper lowers its pin in the same commit. A test-author applies the change to a harness or spec file. A builder may lower a pin in `scripts/docs_audit/core.py`. Nobody raises a pin. A change that would raise one is deferred or redesigned.

## Known gaps

- Some routes are budgeted on their miss path only.
- The loop check misses a helper two levels down, a method on another object and a callee from another module. It also misses `map(lambda)` and a nested function inside a method.
- The read budget does not growth-check `read_sidecar`.

## Deferred fixes

- Revenue reads its range summary once per range. A single read adds a scan and one statement, which the ratchet bars without an index.
- The price archive sweep rewrites unchanged rows, because each bucket gets a new `at`. A fix needs a new way to stamp freshness.
- Join works out changed rows under the lock. A fix needs a bulk `last_seen` touch in the store.
- With `--crop`, Check cost prices whole frames, because no card box is stored at capture. A stored box would make the crop quote exact.
