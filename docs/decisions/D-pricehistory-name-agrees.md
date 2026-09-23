## D-pricehistory-name-agrees — A resolved number is not trusted alone. The name gets a say.

**The seam this closes.** D240 measured it and stopped short of shipping it.
`pipeline/pricehistory.py:ProductIndex.find` accepted a number match the instant it was
unique. It looked at the name only when two or more products shared the number. A misread
number that happened to land on a different, real product read that product's whole price
history under the wrong card's SKU. This happened silently. "The number resolved" was
treated as proof by itself. D240 named two seams together, `pipeline/join.py:_walk` and
this one. It measured this one at 14.4% of numbered, named cards disagreeing with the
number-matched row's own name outright. 5.1% still disagreed after a fuzzy tolerance. D240
declined to ship a fix. It asked for the owner's word first. It named the one failure mode
worse than a wrong report: silently turning a currently-correct listing into a wrong one.

**The owner's ruling (2026-09-23), verbatim:** *"it should match off name and number, and
that if the name isn't exactly right it ought to be able to fuzzy match / recorrect ... and
we'd allow those to count! If both don't match even after that, yes it can come for review,
but in the review it ought to have presuggested options with the context it already has ie
a name match and/or a number match option."*

**What changed, in `ProductIndex.find`.**

- A number match's name is now checked, for one hit or for several. A name that DISPUTES a
  number-found candidate drops that candidate. This reuses
  `pipeline/join.py:name_disputes`'s own fold and tolerance rather than a second copy of
  either. A name that merely agrees, or lands within tolerance, is unchanged. It is
  accepted exactly as before.
- Where the number narrows to nothing this way, the name gets its own turn. This reuses
  D162's rule, already settled for the real listing join: where the name resolves to
  exactly one product, that product is the answer.
- Where neither settles it, `find` answers `None`, exactly as it always has for ambiguity.
  The caller's refusal now names BOTH candidate sets: what the number alone found, and
  what the name alone found. This reaches `Market.product_id_for_row`'s `NotResolvable`
  message, through the new `ProductIndex.refusal`. This module has no review screen of its
  own. `str(exc)` folded into `cli/archive_review.py`'s queue reason is the one surface a
  refusal reaches. That is D238's already-built path, reused rather than rebuilt.
- The two-or-more-hits narrowing rung already existed. It now runs through the SAME fold
  and tolerance as the single-hit check, rather than a separate exact `by_name` membership
  test. The two can no longer disagree with each other, or with `pipeline/join.py`'s own
  comparison.

**What this does not decide.** The shared tolerance's own value,
`pipeline/join.py:NAME_DISPUTE_SIMILARITY` at 0.80 with containment, is a separate
branch's decision. This entry only reads it. If that value moves, this module moves with
it, because nothing here holds a second copy of it.

**What this does not touch.** `pipeline/join.py` itself. Another lane owns it. This entry
only imports from it. What the archive already stores for a product it resolves correctly
is untouched. So is the archive's key (D219) and its pacing (D222). The real listing
join's own D162/D240 behaviour is untouched too.

**Measured against the owner's real store**, read-only, no network call. The subjects are
every card-covered SKU (`pipeline/pricearchive.py:rows_from_store`), checked against the
cached tcgcsv groups already on disk. 914 subjects, all resolved against a cached group.
865 (94.6%) resolve the same way, old and new. 49 (5.4%) resolve differently. That is close
to D240's own 5.1% estimate. Of those 49, 29 now resolve to a different, name-settled
product. 20 now refuse instead of silently keeping the old, disputed answer. Nothing here
was written. The store was only read.

Cites D240 (the seam and its measurement), D162 (the name-decides-uniquely rule, reused),
D234 (the glued-set-code repair this class already runs before the name rung, unchanged),
D219 (the archive this module's readings ultimately feed, untouched), D238 (a refusal
reaches a human, with a photo — the path this entry's refusal message reuses).
