## DEBT60 — the demo builds with Hide unpullable forced off

**Symptom.** Orders' landing view hides buyers with nothing on hand to pull (owner's ruling,
2026-09-28), so "Walk N" ticks the pullable set: 35 of 70 buyers, 39 orders on the committed
mirror. The mirror's recording holds no walk plan for that set, and the demo refuses any
unrecorded ticked set, so the walk drew "Could not read where the copies are". The coverage spec
passed on a race until CI load exposed it (main's demo run 36599655970).

**Stopgap.** The demo build lands with the toggle off (`Orders.tsx`, `IS_DEMO`), so "Walk N"
sends the recorded walk-all set of 74 orders.

**Cause.** `scripts/demo-record.py:default_view_walkable_orders` recorded the old landing set.
It now takes `/orders`' own `resolution` and records the pullable set as well (fixed on this
branch, checked against the mirror: 39 orders). The committed mirror bundle is unchanged, so it
still lacks that plan.

**Remedy.** On the owner's Mac, re-run `make demo-mirror` (it needs the real store, never run in
CI or by a session). Then delete `IS_DEMO` and its `!IS_DEMO &&` in `Orders.tsx`, and
delete this entry.

**Why not fixed now.** Recording a plan needs the store's walk solver over real inventory. The
mirror bundle is the only input a session has, and it holds recorded answers, not a solver.
