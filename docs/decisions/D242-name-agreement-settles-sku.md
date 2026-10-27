# D242 — Name agreement settles SKU number conflicts

**Amended, merged into `D258`, ruling 6.** This class read "the card's own stored name and number." Once a card is bound, those are no longer the read. So this class is empty by construction. That is the outcome it protected. `cards identity`, one report, reads `read_*` against the SKU table instead. It excludes any card a human bound. The sibling class merges into the same report.

**What this builds.** A SKU is one product in one condition. Two copies of it have no legitimate reason to read a different card number. `pipeline/sku_number_contradictions.py` finds every SKU whose stored numbers disagree. It normalizes through `store.numbers.strip_set_code` and `pipeline.join.number_index_key` first. `banchi cards contradictions` is the reachable place a human runs it. It is kept apart from `cards checks`.

**Kept separate from the four approved stored-data checks.** The owner ruled that the more speculative contradiction rate stays a separate thing from the four approved checks. It gets its own module, its own decision entry, and its own CLI subcommand. The four approved checks do not wait on this one.

### The first shape was wrong. The owner's measurement showed why.

The first version asked one question: does a real product exist at this candidate number? That test is vacuous in a dense set. Against Vendetta, 258 products cover 100% of numbers 1 through 166. Both sides of nearly every disagreement resolve to some real product. The check reported `shared_sku` for what is almost always a plain misread. The first split was 32 shared and 18 misread, over the 50 same-denominator SKUs. That split was wrong, not merely uncertain.

**The owner's correction.** This store already holds the card's NAME on every copy, not only its number. So the check asks whether a candidate number's product is also named what this SKU's own copies stored. Existence alone is not enough.

### Three outcomes, by name agreement

- The name settles exactly one candidate. `Outcome.MISREAD`. The settled number is proposed as correct. The rest are misreads.
- The name settles more than one candidate. `Outcome.SHARED_SKU`. Two different, correctly numbered, correctly named products share one SKU. Both numbers are fine. The defect is the SKU.
- The name settles none of the candidates. `Outcome.UNRESOLVED`. No winner is picked.

**A denominator mismatch needs no catalog call at all.** A set has one size. `134/166` and `134/266` cannot both be the same product's printed total. This class resolves before `Market` is built.

### This is not a guess

`CLAUDE.md` forbids guessing an identification. Proposing a number here is not that. A `MISREAD` outcome is an agreement between three independent sources. This module did not invent any of them. Two stored reads come from this SKU's own physical copies. The third is the catalog's own record that this name belongs to this number. A guess picks the more plausible of two options it cannot verify. This picks the only option a third, independent source confirms. It still writes nothing. Proposing is as far as this module goes. A repair is a separate press and a separate decision.

### Measured against the owner's real store and the live catalog

The owner measured this directly, over the 144 disagreeing Riftbound SKUs of the 150 total. Six are Pokemon. **The stored name settles exactly one of the competing numbers in 131 of them. It does not settle 13 at all.** These figures are the owner's measurement against the live catalog. They are used here as measured, not re-derived. No `--resolve` pass or full sweep was run for this entry.

**What was reported before the correction.** This module classified the 50 same-denominator SKUs by existence alone. The result: 100 denominator mismatches, 48 "both plausible", and 2 over-numbered. The "both plausible" bucket was mostly a mislabeled `shared_sku` majority. The name-agreement test replaces the 48-and-2 bucket. It does not touch the 100 denominator mismatches. Those never needed a catalog call, and the correction leaves them unchanged.

**144 of the 150 disagreeing SKUs are Riftbound. Six are Pokemon.** This is mostly a Riftbound reading problem, not a general one.

### What proves it

`scripts/sku-number-contradictions-selftest.py` has eight arms. `normalize_number` folds a glued set code and zero-padding to the same key. `find_disagreements` groups by SKU. A denominator mismatch resolves against a `RaisingMarket` that fails the test if it is ever called. That proves the class never reaches the network. A name that settles exactly one candidate proposes `MISREAD`, naming the confirmed number. A DENSE-SET fixture mirrors the Vendetta measurement: every candidate number is a real product. Name agreement resolves it correctly, where existence alone would have failed. A companion mutation arm runs the ORIGINAL existence-only resolver against the same dense fixture. It wrongly reports `shared_sku`. The real function finds the single name-confirmed misread. That arm protects `CLAUDE.md`'s own rule. A case where the name settles nothing, and a case where it settles two, both prove that no single winner is proposed.

### What this does not do

It does not write a card. It does not apply a repair. It does not queue anything. `store/queues.py:Queue.upsert` refuses to re-queue a position already `cleared_by_human` (D167). A card this check flags has usually been through review once. That gap is recorded separately, not closed here. It does not touch `pipeline/pricearchive.py`, `pipeline/pricehistory.py`, `store/numbers.py` or `pipeline/holdings.py`. That is this task's own fence.

Governs `pipeline/sku_number_contradictions.py`, `cli/cmd_sku_contradictions.py`, and `cli/cmd_cards.py`'s `contradictions` dispatch entry. It cites D23 (two agreeing signals release a claim; here three agree, which is stronger), D167, D173, D234, and the four approved stored-data checks. The four checks are this entry's sibling, built as a separate PR.

Two stored names on one SKU is a sibling class in the same report.
