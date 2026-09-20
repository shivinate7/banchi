## D-sku-number-contradictions — Two copies, one SKU, two numbers: settled by name agreement, never by mere existence

**What this builds.** A SKU is one product in one condition. Two copies of it have no
legitimate reason to read a different card number. `pipeline/sku_number_contradictions.py`
finds every SKU whose stored numbers disagree, after normalizing through
`store.numbers.strip_set_code` and `pipeline.join.number_index_key`. `pkmnscan cards
contradictions` is the reachable place a human runs it, kept apart from `cards checks`.

**Kept separate from the four approved stored-data checks, built as a sibling PR, on the owner's own ruling.**
The owner's words: keep the more speculative contradiction rate as a separate thing from
the four approved checks. Its own module. Its own decision entry. Its own CLI subcommand.
The four approved checks do not wait on this one.

### This entry's first shape was wrong, and the owner's own measurement is why

The first version of this check asked only "does a real product exist at this candidate
number?" That test is vacuous in a dense set. Measured against Vendetta: 258 products cover
100% of numbers 1 through 166. Both sides of nearly every disagreement always resolve to
SOME real product. The check reported `shared_sku` for what is almost always a plain
misread. That first split — 32 shared, 18 misread, over the 50 same-denominator SKUs — was
wrong, not merely uncertain.

**The owner's correction.** This store already holds the card's NAME on every copy, not
only its number. Ask whether a candidate number's product is ALSO named what this SKU's own
copies stored, not merely whether the number exists.

### Three outcomes, by name agreement

- The name settles exactly one candidate. `Outcome.MISREAD`. The settled number is proposed
  as correct. The rest are misreads.
- The name settles more than one candidate. `Outcome.SHARED_SKU`. Two different,
  correctly-numbered, correctly-named products share one SKU. The numbers are both fine.
  The defect is the SKU.
- The name settles none of the candidates. `Outcome.UNRESOLVED`. No winner is picked.

**A denominator mismatch needs no catalogue call at all.** A set has one size. `134/166`
against `134/266` cannot both be the same product's printed total. This class resolves
before `Market` is even built.

### This is not a guess, and the hard rule is the obvious objection

`CLAUDE.md` forbids guessing an identification. Proposing a number here is not that. A
`MISREAD` outcome is an agreement between THREE independent sources this module did not
invent. Two stored reads, from this SKU's own physical copies. And the catalogue's own
record that this specific name belongs to this specific number. A guess picks the more
plausible of two options it cannot verify. This picks the only option a third, independent
source already confirms, and it still writes nothing. Proposing is as far as this module
goes. A repair is a separate press and a separate decision.

### Measured against the owner's real store and the live catalogue

The owner measured this directly, over the 144 disagreeing Riftbound SKUs of the 150 total
(6 are Pokemon).

**The stored name settles exactly one of the competing numbers in 131 of them. 13 are not settled by the name at all.**
These figures are the owner's own measurement against the live catalogue, used here rather
than re-derived. This session ran no `--resolve` pass and no full sweep.

**What was previously reported.** Before this correction, this module classified the 50
same-denominator SKUs by existence alone. 100 denominator mismatches, 48 "both plausible" —
a mislabelled `shared_sku` majority — and 2 over-numbered. The name-agreement test replaces
the 48-and-2 "both plausible" bucket. It does not touch the 100 denominator mismatches,
which never needed a catalogue call and are unaffected by this correction.

**144 of the 150 disagreeing SKUs are Riftbound. 6 are Pokemon.** This is overwhelmingly a
Riftbound reading problem, not a general one.

### What proves it

`scripts/sku-number-contradictions-selftest.py`. Eight arms. `normalize_number` folds a
glued set code and zero-padding to the same key. `find_disagreements` groups by SKU. A
denominator mismatch resolves against a `RaisingMarket` that fails the test if it is ever
called. That proves the class truly never reaches the network. A name settling exactly one
candidate proposes `MISREAD`, naming the confirmed number. A DENSE-SET fixture mirrors the
owner's own Vendetta measurement: every candidate number is a real product. Name agreement
resolves it correctly where existence alone would have failed. A companion mutation arm
runs the ORIGINAL existence-only resolver against the same dense fixture. It wrongly
reports `shared_sku`, while the real function correctly finds the single name-confirmed
misread. That arm protects `CLAUDE.md`'s own rule. A case where the name settles nothing,
and a case where it settles two, are both proved to propose no single winner.

### What this does not do

Write a card. Apply a repair. Queue anything: `store/queues.py:Queue.upsert` refuses to
re-queue a position already `cleared_by_human` (D167), and a card this check flags has
usually already been through review once. That gap is recorded separately, not closed
here. Touch `pipeline/pricearchive.py`, `pipeline/pricehistory.py`, `store/numbers.py` or
`pipeline/holdings.py`, per this task's own fence.

Governs `pipeline/sku_number_contradictions.py`, `cli/cmd_sku_contradictions.py`, and
`cli/cmd_cards.py`'s `contradictions` dispatch entry. Cites D146 (two agreeing signals
release a claim — here three agree, which is stronger), D167, D173, D234, and the four
approved stored-data checks, this entry's sibling, built as a separate PR.
