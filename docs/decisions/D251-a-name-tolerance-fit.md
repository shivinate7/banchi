## D251 — The name tolerance stays at 0.80, and the answers cannot fit a number above it

**The number.** Keep `NAME_DISPUTE_SIMILARITY` at 0.80. Keep the containment escape. This
answers D240, the join trusts a number that resolves, on its tolerance question. The owner's
ruling of 2026-09-20 needs this number. Under it, a name within the tolerance is a match.
The stored name then takes the catalog's spelling. A name outside it goes to Review with
both row sets.

**What was measured.** `scripts/d240-tolerance-fit.py --store`, 2026-09-23, on the owner's
store and the two cached exports. Read-only (`mode=ro&immutable=1`). No `pkmnscan` command.
No network call.

**The labels are real, with one correction.** `cleared_by_human` has two meanings. An answer
writes a SKU. A stand-down (D37, close a question without an answer) writes nothing, so its
card reads as agreement. The script now keeps only a question the event log closes with
`answered`. On this store no `name_disputed` entry was a stand-down, so the counts did not
move. The guard stays for the next store.

- 39 answered `name_disputed` entries. 36 offer one candidate. 3 offer more and are left out.
  Of the 36: 15 misreads (the owner chose another SKU) and 21 accepted (the owner kept the
  number's row).
- 45 answered entries of OTHER reasons whose read name disputes every candidate. The join
  never ran the name check on them, because it runs only when no other reason already
  queued the card. In all 45 the owner chose a SKU outside the candidates: the number was
  wrong. A peer session counted 13, with 10 of this kind. The difference is unmeasured.
  This count reads both queues and every reason.
- 8 more of those kept the number's row under another name. The photograph decides them.
  They are UNKNOWN and enter no count.

Recomputed: 150 SKUs contradict their own stored number, and 115 of them have a hand-cleared
card. The "115" quote holds. The "131 of 144 settled" figure needs the live catalogue. It is
not recomputed here.

**The labels cannot fit a number above 0.80.** An entry reaches `name_disputed` only when the
ratio is below 0.80 and no name contains the other. So every label sits below 0.80, and
containment is true in 0 of 36. From 0.79 up, all 36 are flagged at every step. This is a
selection effect. It is not a result about names.

| tolerance | misreads flagged (of 15 + 45) | accepted cards flagged (of 21) | store-wide flagged | change from 0.80 |
|---|---|---|---|---|
| 0.70 | 60 | 16 | 127 | -6 |
| 0.75 | 60 | 17 | 128 | -5 |
| 0.78 | 60 | 20 | 132 | -1 |
| 0.80 | 60 | 21 | 133 | 0 |
| 0.82 | 60 | 21 | 136 | +3 |
| 0.85 | 60 | 21 | 138 | +5 |
| 0.90 | 60 | 21 | 146 | +13 |
| 0.95 | 60 | 21 | 156 | +23 |

Store-wide is 3,134 cards the export matched by number. 116 of the 133 flagged at 0.80 are
on hand. The full 0.01-step table is the script's own output.

**Why not lower.** The highest known misread has a ratio of 0.632 (`Order Rune` read,
`Mind Rune` row). The band from 0.63 to 0.79 holds champion variants: `Ashe, Freljord`
beside `Ashe, Focused`, and `Diana, Mount Targon` beside `Diana, Lunari`. The owner kept the
number's row on these. But under the ruling a match here renames the card with no person
present, and two real printings share each champion name. A low tolerance renames a real
different card silently. That is a wrong listing, the one failure the owner ranks worse than
a wrong report. Going to 0.75 saves 5 questions store-wide. That is not worth the risk.

**Why not higher.** The labels are silent above 0.80. So the 23 cards between 0.80 and 0.95
were read by name against their catalog rows. At least 20 are a spelling slip of the same
card: `Corfish` and `Corphish`, `Soulspipper` and `Soulspinner`, `Zaun Wardens` and
`Zaun Warrens`, `Iascylla`, `Sterak's Gage`. The lookup could not place 3 of them. No known
misread sits in this band. Going to 0.95 adds 23 questions and catches nothing known.
D239's 0.82 is a different shape. It compares two stored names with `get_close_matches`. It
is not this comparison, and it adds 3 questions for no known catch.

**The margin.** 0.80 sits 0.17 above the highest known misread, and 0.014 above the highest
accepted near-miss (`Blast Cadet` and `Blast Corps Cadet`, 0.786). That accepted card stays
a Review question. That costs one press. It does not cost a wrong listing.

**D240's third question.** `pipeline/pricehistory.py:ProductIndex.find` does not cover this.
Its name step runs only when the number finds two or more products, and it narrows by exact
name. A number that finds one product returns it with no name check. That is the D240 case
exactly. Reuse `join.name_disputes` and this constant there, not `find`'s step. That path
feeds the price archive. It does not feed a listing, so the risk there is lower.

**D240's premise, corrected.** D240 says a number that resolves is never second-guessed.
That holds for `_walk`. It does not hold for the join. `join_batch` runs `name_disputes`
after `_walk` and queues a disputed card with both readings (D146). The rung D240 proposed
exists already, at 0.80, with the listing shape. The gap is the one the 45 above show: the
check does not run on a card that another reason queued.

**What this does not do.** It does not change `pipeline/join.py` or
`pipeline/pricehistory.py`. It does not change a listing outcome.

Cites D37, D146, D239, D240 and D242.
