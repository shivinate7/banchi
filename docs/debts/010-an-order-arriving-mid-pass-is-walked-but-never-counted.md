## 10 — An order arriving mid-pass is walked but never counted, and a tab outlives its sitting

`WalkView`'s figure counts the orders THIS PASS has completed — `OrdersHubStore.walkKeys`, frozen when
the walk is entered and cleared by a fetch or by a capture-server restart (D96, amended 2026-09-04).
Two things it still cannot say, both deliberate and both reachable on the owner's store. **A third —
that a restarted server ends the pass — was one of them and is closed**; it is kept below because the
three attempts it took are the useful part.

**An order that arrives after the press is walked but never counted.** The screen re-reads after every
pull, so a new order joins `walk.rows` and the operator pulls its copies like any other — and the pill
goes on describing the pass they started rather than the work now in front of them. The head beside it
is the figure that moves, which is why this is a gap and not a lie: *"4 still to pull across 3 open
orders"* is always current. Counting arrivals would make the figure a different one — progress against
a moving target — and that is a design question, not a fix.

**And the pass is held for as long as the tab is.** `HubState` lives as long as the tab by its own
argument, and `mode` already survives an Orders → Shipping → Orders detour under it, so `walkKeys` does
too. A tab left open overnight keeps a figure describing a sitting that ended, and nothing on screen
says so. `onFetch` clears it, which is the boundary the operator actually draws — but only if they
press it. **The fix that would close this is WALL-CLOCK ELAPSED TIME USED AS A SEMANTIC INPUT —
expiring a pass after N minutes have passed — and this repo does not put THAT kind of clock in the
client** (`store/orders.py`'s `now()`/`changed_at` is the one deliberate exception, a server-side
timestamp rather than a client timer, and it argues the distinction at length), so the honest
alternatives are an explicit *end this pass* control nobody has asked for, or leaving it here. THIS
IS NOT A CLAIM THAT THE CLIENT CARRIES NO REPEATING TIMER — it carries five, all of them polls
re-asking a question on a cadence rather than a wall clock deciding an answer has gone stale by
itself, and `D207` gives them one shared primitive rather than a sixth hand-rolled one. The
sentence above was read as the opposite once and corrected here rather than reopened: a poll and an
expiry are different mechanisms, and this repo has built the first kind five times and the second
kind never.

**A capture-server restart DOES end it now, closed 2026-09-05.** `onServerBoot` clears `walkKeys`
beside the shipping batch: a server that restarted may have taken orders since, so a figure counted
against the old set describes a sitting that is over — and unlike a stale batch it is not visibly
broken, it is a smaller number that looks fine.

**The reason this took three attempts is worth more than the fix, because it was never the code.**
The first two blamed the boot header: `app/tests/orders.spec.ts` stubs only the four `/orders*`
routes, so `/status`, `/games` and `/boxes` reach the real capture server with a boot id of their own,
and that was recorded here as a hazard for every spec. **It is not one.** `server.ts:noteBoot`
early-returns on an absent header and says why in its own comment — *"far more likely in a test — a
stubbed route, and inventing a reload from a missing header would make every spec that stubs the wire
report one"* — and the real server's id is CONSTANT while it runs. The listener fires only when two
different non-empty ids alternate, which is what the investigation's own experimental stub
introduced. The hazard was manufactured and then filed as the repo's.

**What actually defeated it was a catch-all route that forwarded a write.** The stub rewriting the
header matched by PORT and therefore also caught `POST /orders/pull`, which `route.fetch()` sent to
the real capture server. It was refused there — a fixture's order does not exist in a real store — so
`pullCopy` threw, `onPull` never reached its re-read, and the payload never moved. The case failed
for a reason that had nothing to do with what it tested, **and a write came one refusal away from
landing on a live store.** The rewrite is GET-only now and says so at the line.

**The case that closed it carries its own vacuity guard.** A third order stays open through the
restart, because with only two the second pull leaves nothing open, `buildWalk` returns no rows, and
`WalkView` draws its EmptyState before the head — the figure would be absent because the whole head
is. Proven by removing the third order AND the clear together: the case still passes. Observed
failing with the clear removed, and with the boot id held constant, both at `Expected 0, Received 1`.

**And `onServerBoot` is exercised on purpose at last.** No spec drove the boot header before this one,
so the listener — including D73's shipping-batch clear, which throws away real state — had never been
tested at all.

**Why the remaining gap is not fixed.** The mid-pass arrival was surfaced by an adversarial review of
the change that introduced the figure, before it shipped, rather than found afterwards — and it is the
figure being narrower than the screen rather than wrong about what it counts.
