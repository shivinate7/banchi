## DEBT60 — the demo builds with Hide unpullable forced off

Orders' landing view hides buyers with nothing on hand to pull, so "Walk N" ticks the pullable set (35 of 70 buyers, 39 orders on the committed mirror). The mirror's recording holds no walk plan for that set, and the demo refuses any unrecorded ticked set, so the walk drew "Could not read where the copies are". Stopgap: the demo build lands with the toggle off (`Orders.tsx`, `IS_DEMO`), so "Walk N" sends the recorded walk-all set. `scripts/demo-record.py:default_view_walkable_orders` now records the pullable set as well, but the committed mirror bundle is unchanged and still lacks that plan.

**Outcome at risk.** The public demo cannot show the owner's landing view.

**Closes when.** The owner re-runs `make demo-mirror` on their Mac (it needs the real store, so never in CI or by a session), then deletes `IS_DEMO` and its `!IS_DEMO &&` in `Orders.tsx`, and this entry.
