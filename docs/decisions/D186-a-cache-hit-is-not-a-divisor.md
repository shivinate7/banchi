## D186 — A per-card price is divided by the cards actually submitted, and a reading is chosen on a metric the reading can move

**A per-card cost is total tokens over the cards ACTUALLY SUBMITTED, never over the cards in the run, because a cache hit is billed nothing and a run that served a third of itself from cache reports a per-card price a third too low.**

**And a parameter is compared on a metric that parameter can move.** Both halves were found on 2026-09-12 while pricing the per-run reading (`--max-edge`, D32's pair), and each one had already produced a wrong published figure.

### The first half: the divisor

**A sibling plan priced the reading at ~2,180 input tokens per card at 900 against ~2,420 at 1200, for a store-wide saving of ~$0.36.** The 900 figure is right and reproduces exactly at **2,179**, because **both 900 runs had zero cache hits**. The 1200 figure is low, because it averaged two runs and one of them — `2026-09-01-box3-01`, 723 cards — served **191 of them from the cache**: `1,423,570 / 723 = 1,969`, the published number, against `1,423,570 / 532` submitted = **2,676**.

**Measured over every run carrying a usage block, submitted cards only: 2,179 input tokens/card at 900 and 2,641 at 1200** — a delta of **462** rather than 240, and a store-wide saving over 2,535 cards of **$0.60** rather than $0.36. The inflation factor reaches **4.26x** on `2026-09-11-box4-04`, which billed 626 tokens per card in the run and 2,665 per card it actually sent.

**The direction of the error is the part worth remembering: it makes the DEARER setting look cheap.** Cache hits accumulate on a box that has been re-joined, and re-joins concentrate on the settings already in use — so the incumbent reading is the one whose price gets deflated, and the saving from changing is the figure that gets understated. `identify`'s own preflight has always had this right; it prints `cache hits` and `to send` as separate lines and estimates on the second.

### The second half: the metric

**The same plan proposed to settle accuracy on queued count over 100 cards. Every queued card in the two runs it cited is `no_catalog_row`** — 5 of 723 and 1 of 544 — **and that reason code is catalog completeness, not reading difficulty.** The composed key found no row in the export. No downscale can make a catalog row exist, so the metric was one the variable under test cannot move at all.

**The resolution-sensitive code is `number_unread_name_matched`** (D35 — the number could not be read, so the name answered), at **212 of 2,535 store-wide, 8.36%**, against 0.47% for the queued count. That is the metric a reading is chosen on.

### Why 100 cards was never going to answer it

**The design is paired — the same cards at both readings — so only discordant pairs carry information and six of them, all one way, is the floor for `p<0.05`** (`2 x 0.5^6 = 0.031`). Against a 0.47% base rate, producing six discordants in 100 cards needs the 900 rate to reach 6.47%: a **13.7x** effect. **The chance both arms return zero is 38.7%, and the power to see a 1.5x change is 0.0%** — 18.3% even at n=1,600. The likeliest single outcome of the press was `0 vs 0`, which is what the two small 900 runs already say.

**A paired 100 on `number_unread_name_matched` detects a ≥1.7x change**, with 36% power against a doubling and 67% at n=200. That is the experiment worth ~$1.04 of the approved $0.29's budget line, and the one to run.

### What this does not repeal

**D32 stands entirely and its frontier table is not corrected by any of this** — that table prices configs per box from 20 real frames and is a different basis, not a competing reading of the same one. What this entry adds is the arithmetic rule underneath it.

**The one paired reading this project already had is the one that found an effect, and it is still on the record**: `docs/GATES.md`'s Box 2 section, **19 of 40 cards disagreeing with themselves on `finish` between 900 and 1200 on the same photographs**. That effect was large and plainly visible at n=40. `finish` is no longer sent to the model, so it is not the field a reading is chosen on now — but it is the standing proof that the reading does change the answer, and that a metric with a real base rate shows it at small n.

**A cross-run comparison of the two readings is confounded twice over and must not be quoted as one**: both 900 runs are 100% Riftbound, all 544 Pokemon sit only in the 1200 arm, and `number_unread_name_matched` already ranges 3.4% to 11.7% between boxes at a fixed reading. Pokemon composes a denominator into its number key and Riftbound does not, so the games are not interchangeable on precisely the axis being measured.
