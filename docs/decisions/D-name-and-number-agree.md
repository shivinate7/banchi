## D-name-and-number-agree — A card lists off name AND number agreeing, never off the number alone

**The owner's ruling, 2026-09-23.** A card should match off name and number together. A
name that is not exactly right should still be allowed to fuzzy match, or recorrect,
through the tolerance a sibling session fits. Where both signals still disagree after that,
the card goes to review, with presuggested options for the context already in hand. That
means both a name match and a number match, offered together.

**The defect, measured on the owner's store, read-only.** `pipeline/join.py`'s name
cross-check only ran when `not resolution.needs_review`. That is a card the ladder had
already resolved outside review. A card already queued for a reason of its own never got
the check at all. Three reasons carry no row: `ambiguous_no_signal`, `set_ambiguous`,
`rarity_claim_mismatch`. A card queued under one of them offered only the number's wrong
candidates.

**The count, corrected.** This branch first counted 13 such entries, review queue only,
with a confident "true card" for three of them. `D-a-name-tolerance-fit` re-measured,
reading both the review and the parked queue, over every reason. It found 45 answered
entries whose read name disputed every candidate offered. In all 45 the owner's own answer
picked a SKU outside the offered candidates. The number was wrong every time, by the
owner's own hand. A SEPARATE eight kept the number's row as the owner's answer. Those
eight are undecided. Only the photograph settles whether the number or the name read the
card right, and this session has neither. This entry's own 13 is superseded by the 45 and
the 8 together, and the "true card" claims below are withdrawn.

- `4/176`: read "Daisy!" `190/219`, queued `ambiguous_no_signal`. It offered only Lilting
  Lullaby's conditions, `190/219` being Lilting Lullaby's own number. Which card is real is
  one of the 8 undecided entries, not a confirmed misread.
- `6/563`: read "Frigid Jewel" `024/219`. Capture claimed a foil finish and a
  Common/Uncommon rarity. It queued `rarity_claim_mismatch`, a reason that never carries a
  row. It offered only Rengar, Unseen (Rare). This is also one of the 8 undecided entries.
- `4/442`: read "Pyke, Returned" `150/219`. It offered only Vex, Apathetic. Undecided too.

**What changed.** The gate over the disputed-name block widened. It used to be `disputed
and not resolution.needs_review and resolution.row is not None`. It is now `disputed and
resolution.stage != variant.HUMAN_ANSWERED`. The check now fires on any disputed card.
This holds whatever the card was already queued for. This holds whether or not the ladder
gave it a row to start from.

**D162 stays exactly what it was: the one release rule.** A name that points to exactly
one card still decides alone, in the owner's own words from 2026-09-12. Two conditions
still both apply. The read name must resolve to exactly one card. The ladder must settle
that one card's own finish from the same capture claims (`metadata_finish`,
`rarity_claim`). Where both hold, the card lists. No human is asked, whatever it was
queued for a moment before. Where either fails, it queues, now with both readings offered.
The name's rows come first. The number's own rows follow. `resolution.row` is used where
the ladder had one. `found.rows` in full is used where it did not. `rarity_claim_mismatch`
and `ambiguous_no_signal` never carry a single row to fall back to. The primary reason the
card was already queued for survives unchanged. Only the candidate list grows. A card the
ladder had resolved outside review still gets `NAME_DISPUTED` on a dispute. That is
unchanged since 2026-09-12.

**What is not settled, and why it matters here.** D162's 209-of-209 measurement covers two
shapes only. One is a card the ladder had already resolved to a row. The other is a
number-unread card. Neither shape starts from `ambiguous_no_signal`, `set_ambiguous`, or
`rarity_claim_mismatch`, the three this entry newly reaches. Of the 8 undecided entries
`D-a-name-tolerance-fit` found, the owner's own answer kept the NUMBER's row on every one.
This does not mean the number was right on any of them. Only the photograph can say that.
D162's release now reaches a shape it has no matching measurement for yet. A future
session should replay every entry these three reasons would now release, against the
owner's own past answers. Only that replay earns this extension the same standing D162's
original two shapes already have.

**Fuzzy recorrection was already built.** This entry reuses it rather than inventing a
second one. `name_disputes`'s `NAME_DISPUTE_SIMILARITY` constant is the tolerance a read
must clear to not dispute a row. Containment counts. A `difflib` ratio at or above the
constant also counts. `D-a-name-tolerance-fit` (branch `claude/d240-tolerance-fit`) fit
that number and settled it at 0.80. The highest known misread ratio is 0.632. Containment
holds in zero of the true misreads. 0.80 sits 0.014 above the highest accepted near-miss
the store carries, `Blast Cadet` against `Blast Corps Cadet` at 0.786. This entry leaves
the constant untouched.

**Claims rank the settled row, even with no row to start from.**
`pipeline/join.py:name_alternatives` already resolves the name's own rows through the same
ladder. That ladder is `variant.resolve`. It reads `metadata_finish`, `rarity_claim` and
`detected_finish`. This is D23 and D146's existing machinery, not new machinery. What was
missing was a place to carry that answer back out. `NameSide` now carries the ladder's own
`Resolution` over the settled row. `join_batch` reads its `stage` and `reason`, rather than
the review reason it replaces. `rarity_claim_mismatch` has no finish decision of its own to
inherit. Frigid Jewel's case is exactly this shape. The claim contradicts the wrong card's
rows and queues with no row. Run again over Frigid Jewel's own two rows inside
`name_alternatives`, the same claim is released by `name_corroborated=True` (D146). The
foil metadata claim then settles Near Mint Foil, first and alone.

**The near-miss half.** An accepted name that was not byte-identical corrects the stored
name. A card can resolve outside review with a read name that agreed with its row
without being identical to it after the fold. `Corfish` for `Corphish` is that shape. This
covers the containment half of `name_corroborates`, and a fuzzy near-miss neither the
containment test nor the exact-match test catches. For that card, the catalogue's own
spelling is offered as a correction for `Card.name`. The mechanism is
`pipeline/join.py:JoinReport.name_corrections`, a `(box, index) -> catalog name` map. It is
read by `cli/cmd_emit.py`, at the same moment `set_name` and `rarity` are already written
onto the card (D213). The write goes through a new `name` parameter on
`store/master.py:Inventory.set_state`. The model's own reading is untouched. It stays
exactly where `record_identification` already wrote it, in the run's own record. A
disputed card never reaches this as a near miss. One that settled did so onto the name's
own row. `catalog.rows_for_name` is an exact fold lookup, so the read and the row are
byte-identical by construction. One that did not settle is still `needs_review`.

**D240, by its own id.** D240 measured `pipeline/join.py:_walk` and
`pipeline/pricehistory.py:ProductIndex.find` against a premise its own docstring states.
The premise reads: a number that resolves is never second-guessed. That premise was
already false for the disputed-name path this entry fixes. `name_disputes` and
`name_corroborates` (D146), plus D162's release, already second-guess a resolved number.
They read the same evidence D240 asks for. D240's 134-of-2,636 gap is measured over
`_walk`'s number-key resolution path directly. It is never measured over this queue-time
cross-check. The two figures do not share a denominator. This entry does not close D240's
gap. It closes a narrower, adjacent one. That one is cards this cross-check already
flagged as disputed, but only some of which it ever acted on. The split between "already
caught here" and "still only `_walk`'s problem" is unmeasured.

**Cites** D35 (the fallback rung this one mirrors, and whose rule against listing a
name-found card on its own D162 already amended once), D146 (the two-signal release the
claim re-run inside `name_alternatives` depends on), D162 (the release rule this entry
widens the reach of, never the rule itself), D167 (the queue-refresh precedent for
re-resolving an already-queued entry against fresh evidence), D240 (the premise this closes
a slice of, cited above by sentence), D242 (name agreement over mere existence, the same
shape one register over, a stored fact's own copies rather than one card's two readings),
and `D-a-name-tolerance-fit` (the sibling measurement this entry's own count defers to, and
the source of the 0.80 tolerance figure above).

**What this does not do.** It does not change `_walk`, any join key strategy, D55's
set-code repair, or any emit or pricing behaviour. D35's rule stands: a name-found row
may never list a card on its own. D162's own one-card release remains the one exception,
already in force. It does not touch `app/src/Inventory.tsx`, `BoxBrowse.tsx`, or
`position.ts`. It does not build a second write path for a card's stored name.
`cli/cmd_emit.py`'s two `set_state` calls are the only two places a join's answer already
reaches the store, through `set_name` and `rarity`. This entry reuses both.

**Coverage.** `harness/tests/t3_join_coverage.py` carries four cases. Daisy's shape covers
a card queued for a reason of its own, where the name disputes the number and resolves to
one card elsewhere. D162 releases it regardless of the original reason. Frigid's shape
covers `rarity_claim_mismatch`, with no row at all. The claim ranks the name's own rows,
so it settles the claimed finish first. An unsettled dispute over a reason of its own
covers the queued path. The primary reason survives and both row sets are offered. The
number's side is `found.rows` in full, since there is no single row to fall back to. The
near-miss name correction, fired and withheld, is the fourth case. `app/src/ReviewQueue.tsx`
already draws both row sets for a payload like this. `found_by` and `CandidateButton` key
off the `candidates` field and `name_matched_skus`. They do not key off the review reason.
This has held since 2026-09-12 (D162), so no front-end change was needed. `make orient
ARGS=app/src/ReviewQueue.tsx` names `Card`, `Claims` and `CandidateButton` as the drawing
components. `tagsFor` is the one that reads `found_by`.
