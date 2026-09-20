## D-sku-number-contradictions — Two copies, one SKU, two numbers: kept separate, resolved against the catalogue

**What this builds.** A SKU is one product in one condition. Two copies of it have no
legitimate reason to read a different card number. `pipeline/sku_number_contradictions.py`
finds every SKU whose stored numbers disagree, after normalizing through
`store.numbers.strip_set_code` and `pipeline.join.number_index_key`. `pkmnscan cards
contradictions` is the reachable place a human runs it, kept apart from `cards checks`.

**Kept separate from the four approved stored-data checks, built as a sibling PR, on the owner's own ruling.**
The owner's words: keep the more speculative contradiction rate as a separate thing from
the four approved checks. Its own module. Its own decision entry. Its own CLI subcommand.
The four approved checks do not wait on this one.

### The owner's second ruling: resolve against the catalogue, do not assume

The owner raised a real false-flag risk. In Riftbound, an over-numbered card can carry the
same name and text as its base-rarity twin, while being a genuinely different card. Two
copies reading differently might be two CORRECT reads of two DIFFERENT cards. The real
defect would then be the SKU they share, not either number. Their ruling, in short: a
catalogue lookup is cheap, so normalize against the catalogue rather than assume.

**Three outcomes, never collapsed into one.**

- Only one side resolves to a real product number in the group. The other side is a
  misread. `Outcome.MISREAD`, naming the confirmed key.
- Both sides resolve to real, distinct product numbers. The numbers are both fine. The SKU
  itself is shared between two cards. `Outcome.SHARED_SKU` names this, a different defect,
  never a misread.
- Neither resolves. The catalogue cannot settle it. `Outcome.UNRESOLVED`. No winner is
  picked. `CLAUDE.md`'s own rule against guessing an identification applies here exactly.

**A denominator mismatch needs no catalogue call at all.** A set has one size.
`134/166` against `134/266` cannot both be the same product's printed total. This class
resolves before `Market` is even built. `Market.products(category_id, group_id)` answers
a whole group in one cached request. The catalogue cost for the rest is roughly one
request per (game, set) pair among the SKUs that need it, not one request per SKU.

### Measured against the owner's real store, read-only, 2026-09-20

**150 of 881 SKUs with a number disagree, after normalizing.** 219 disagree on the raw
string. Most of that gap is glued set codes D234's own repair already handles. Comparing
before the normalizing fold overstates the finding by nearly half.

Split three ways, matching the owner's own measurement of the same 150 SKUs:

- **101 disagree on the denominator itself.** Unambiguous. No catalogue needed.
- **47 have both sides plausible within the set.** These need the catalogue to settle.
- **2 have one side numbered above the set total** — the owner's own over-number case.
  Real, and rare.

**This module's own classifier, re-run moments later, landed at 100 and 50.** That second
figure splits into 48 plausible plus 2 over-numbered, on the same 150 total. The one-record
difference from the owner's figures is measurement drift over a live store, not a
different method. Both counts fold a stored number with no clean `NUM/DENOM` shape — a
glued fragment, a bare digit run — into the unambiguous denominator-mismatch bucket. Neither
treats it as a third, uncategorized class the check cannot act on.

**144 of the 150 are Riftbound. 6 are Pokemon.** This is overwhelmingly a Riftbound
reading problem, not a general one.

**No resolved catalogue count is reported here.** `--resolve` opens a real network
connection. This session ran none, per the task's own constraint. The 47-and-2 split above
is what the owner's ruling asks this module to tell apart. Doing so for real is `pkmnscan
cards contradictions --resolve`'s own job, not this entry's.

### What proves it

`scripts/sku-number-contradictions-selftest.py`. Seven arms. `normalize_number` folds a
glued set code and zero-padding to the same key. `find_disagreements` groups by SKU and
reports only the ones that disagree. A denominator mismatch resolves against a
`RaisingMarket` that fails the test if it is ever called, proving the class truly never
reaches the network. A misread, a shared SKU, and an unresolved case each exercise a
`FakeMarket` duck-typed against `pipeline/pricehistory.py:Market`'s own three calls. A
mutation arm: a naive "first side wins" resolver is shown to pick a wrong, silent winner
on the SHARED_SKU fixture. The real function is then shown to report both sides and pick
none.

### What this does not do

Write a card. Pick a winner between two disagreeing, catalogue-real numbers. Queue
anything: `store/queues.py:Queue.upsert` refuses to re-queue a position already
`cleared_by_human` (D167), and a card this check flags has usually already been through
review once. That gap is recorded separately, not closed here. Touch `pipeline/pricearchive.py`,
`pipeline/pricehistory.py`, `store/numbers.py` or `pipeline/holdings.py`, per this task's
own fence.

Governs `pipeline/sku_number_contradictions.py`, `cli/cmd_sku_contradictions.py`, and
`cli/cmd_cards.py`'s `contradictions` dispatch entry. Cites D146, D167, D173, D234, and
the four approved stored-data checks, this entry's sibling, built as a separate PR.
