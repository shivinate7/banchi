### The per-run reading — 900 against 1200, priced and powered. 2026-09-12

**NO PAID SUBMISSION WAS MADE, AND THE REASON IS THE MEASUREMENT AND NOT THE MONEY.** The
spend was approved and the two dry-run estimates came in under it. What stopped the press is
that the experiment as designed cannot answer the question it was built to answer, and the
**2,570 cards this project has already paid for prove that for nothing.** Everything below was
read out of `runs/*/manifest.json`, `runs/*/identifications.json`, `runs/*/report.txt` and the
store opened `mode=ro&immutable=1`. **The store was never opened for writing here, and it moved
anyway — which is the evidence rather than a hole in it.** It read
`md5 5fd8192d22cdbc69d7096330466f9867` / 7,438,336 B at 12:00 local and
`0865077949780989d2f40605b4b0834b` / 7,450,624 B at 13:24, because the owner's own live server
(`make launch-agent`, pid 53501 on `server/capture_server.py`) was in use throughout and wrote
**four `sold` events at 17:00 UTC** — `4/5`, `3/52`, `3/53`, `3/54`. What this session could have
touched did not move: `cards` 2,535 and `identifications` 2,535 before and after, and the
photograph corpus still 2,535 files at 4,445,351,065 B. The 100 photographs were **hardlinked**
into the throwaway tree, so no byte was copied or written.

**The archive already holds the A/B, at 24x the proposed n.** Per-card figures count only
cards actually submitted — a cache hit is billed nothing, so it is not a divisor:

| reading | runs | submitted | cached | input tok/card | output tok/card | $/card | `low` confidence |
|---|---|---|---|---|---|---|---|
| 900 | 2 | 104 | 0 | **2,179** | 32.9 | **$0.001172** | **0 of 104** |
| 1200 | 10 | 2,466 | 1,105 | **2,641** | 35.1 | **$0.001409** | **8 of 2,466 (0.32%)** |
| 1568 | 1 | 53 | 0 | 2,509 | 38.1 | $0.001350 | 0 of 53 |

**The saving is LARGER than the sibling plan published, and the gap is a cache hit used as a
divisor.** That plan read ~2,180 at 900 and ~2,420 at 1200 for a store-wide saving of ~$0.36.
The 900 figure reproduces exactly (2,179) because **both 900 runs had zero cache hits**. The
1200 figure does not: it averaged two runs, one of which — `2026-09-01-box3-01`, 723 cards —
served **191 of them from the cache**. `1,423,570 / 723 = 1,969`, which is the published
number; `1,423,570 / 532` submitted is **2,676**. The inflation reaches **4.26x** on
`2026-09-11-box4-04` (626 against 2,665). Corrected: **462 input tokens/card**, a store-wide
saving of **$0.60** over 2,535 cards rather than $0.36.

**Accuracy does not argue against 900 on this evidence, and it cannot argue for it either.**
0 of 104 against 8 of 2,466 is not a comparison; it is one arm with no events and a base rate
of a third of a percent in the other.

**The two runs the plan cited for accuracy queued 6 cards between them, and all six are
`no_catalog_row`** — `2026-09-01-box3-01` 5 of 723, `2026-08-24-box2-01` 1 of 544, both 900
runs 0. That reason code is **catalog completeness**: the composed key found no row in the
export. **No downscale can make a catalog row exist**, so the metric the comparison was to be
scored on is one the variable under test cannot move.

**Why 100 cards cannot settle it, stated as arithmetic.** The design is paired — the same
cards at both readings — so only discordant pairs carry information and the test is McNemar's.
**Six discordant pairs all in one direction is the floor for p<0.05** (`2 x 0.5^6 = 0.031`):

| metric | base rate at 1200 | 900 rate needed for 6 discordants in 100 | that is |
|---|---|---|---|
| queued (`no_catalog_row`) | 6/1,266 = 0.47% | ≥ 6.47% | **13.7x** |
| `low` confidence | 8/2,466 = 0.32% | ≥ 6.32% | **19.4x** |
| `number_unread_name_matched` | 212/2,535 = 8.36% | ≥ 14.36% | 1.7x |

At n=100 the chance **both arms return zero** is 38.7% on the queued metric and 52.2% on
confidence, and the power to see a 1.5x change in the queued rate is **0.0%** — still only
18.3% at n=1,600. The most likely single outcome of the press was `0 vs 0`, which is the
non-result the two small 900 runs already carry.

**The resolution-sensitive code is `number_unread_name_matched`** (D35 — the number could not
be read, so the name answered), and it is the one metric with a base rate a small run can see:
store-wide 212 of 2,535. A paired 100 detects a **≥1.7x** change there; power against a
doubling is 36% at n=100 and 67% at n=200.

**Between-box spread at a FIXED reading is 3.4-fold, which is why only the paired form can
work**: `number_unread_name_matched` runs 3.4% (box 1, 11/322), 8.3% (box 2, 45/543), 11.7%
(box 3, 104/887), 6.9% (box 4, 47/678), 4.8% (box 5, 5/105). A cross-run 900-against-1200
comparison is also **confounded by game**: both 900 runs are 100% Riftbound, and all 544
Pokemon cards sit only in the 1200 arm — and Pokemon carries a denominator in its number key
where Riftbound does not.

**The prior paired reading on this file is not superseded and is the one that found an
effect.** The Box 2 section above records **19 of 40 cards disagreeing with themselves on
`finish` between 900 and 1200 on the same photographs**. That effect was large and visible at
n=40; `finish` is no longer sent to the model, so it is not the field a reading is now chosen
on.

**The rig was built and dry-run, so the press is one command whenever the n is worth it.** A
deliberately mixed-value 100-card lot — market value **$0.04 to $48.02**, median $1.60, 22/22/22/21/13
across the five bands `<$0.29 / $0.29-1 / $1-5 / $5-20 / >$20`, 80 Riftbound and 20 Pokemon
across 5 boxes, the >$20 band capped at the 13 such cards on hand — over a `.backup()` copy of
the store with `identifications` emptied (2,535 → 0) so neither arm could be answered from
cache, and the photographs hardlinked rather than copied. Both dry-runs reported
**`cache hits 0`, `to send 100`**: **$0.10 at 900** (13.8 MB payload) and **$0.12 at 1200**
(23.8 MB). The payload ratio 1.72 tracks the pixel ratio `(1200/900)^2 = 1.78`.

**What would settle it**: the same paired pass scored on `number_unread_name_matched`, at
n≈400 per arm — about **$1.04** for both arms at the measured $0.0013/card, against the $0.29
that buys a coin flip.

---
