# D328 — A spec heavier than a shard's mean runs as two halves

A browser spec that costs more than the mean shard load is cut in two by Playwright's own `--shard`, and each half gets a shard to itself.

Kind: process
Home: scripts/browser-scope.py

**Why.** D136, The suite is sharded, never widened, packs whole spec files onto shards by measured time. A whole file cannot be balanced. On push run 43384801390 (2026-11-13), `pricing.spec.ts` ran alone on shard 2 with 1,123 summed worker-seconds, a 569 s step and a 662 s job. Most other shards ran a 180 to 360 s job. `inventory.spec.ts` ran alone on shard 1 at 822 summed seconds (417 s). The table said 590 s and 697 s. The sum of all 64 files is 6,709 summed seconds, 559 a shard.

**The rule.** `plan_shards` in `scripts/browser-scope.py` cuts a file into two halves when four things hold. It declares more than one test (a one-test file has an empty second half). Its time exceeds the mean shard load of the whole table, not of the list a narrowed run was handed. The cut leaves a shard for the rest. It lowers the slowest shard against `pack_shards`. A half runs `<file> --shard=1/2` or `--shard=2/2`. A half holds its shard alone, because `--shard` cuts every file a run names. `pack_shards` places the remaining files on the shards left, as D136 does. With `fullyParallel` on, Playwright cuts by test case, so the halves are even by case count and not by time.

**The table.** `scripts/browser-spec-times.json` holds a cut file's whole time. `shard-refresh` adds the halves of a cut file, and keeps the whole-file time when one run listed the file whole and another listed halves. The run's `fileSeconds` are summed over two workers, so they read about twice the shard's step.

**Projected, unmeasured.** The same table packs to a slowest shard of 597 summed seconds (about 300 s of step), against 1,123 (569 s). No run has used the plan yet. The first full run after this merge is the measure.
