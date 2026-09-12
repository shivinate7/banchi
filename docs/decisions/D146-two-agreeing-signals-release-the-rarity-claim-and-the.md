## D146 — Two agreeing signals release the rarity claim, and the same comparison run backwards is a review reason

**Settled 2026-09-11, from a stack the owner sorted correctly asking them 141 questions.**
They claimed `Epic` on a 143-card Riftbound stack in `2026-09-11-box1-01`. The
catalogue calls those cards `Rare`. D23's cross-check treats a typed rarity as a hard fact,
so it refused 141 of them — and in 136 of those the single row it offered was
**byte-for-byte the SKU the owner then chose by hand.**
One typed word, 136 taps to agree with the machine.

The owner's ruling, in their own words: *"two agreeing signals is enough to auto-list"*, and
*"batch it, one press clears the whole group"*.

### The claim was refusing right cards and waving wrong ones through

Both halves are measured, and the second is why this is not a nuisance fix.

**The refusals.** Over every run the store holds, `rarity_claim_mismatch` fired **159**
times. A claim-released ladder resolves **145** of those cleanly; a human later answered
**every one** of the 145; and **142** of those answers are byte-identical to the row the
ladder was already holding. Three are genuinely the wrong card — `3/564`, `1/65`, `1/73`.

**The mirror.** The same claim AGREED with the wrong card whenever the wrong card's rows
happened to satisfy it, and then nothing was flagged at all. Box 1's `1/51` read
`Irelia, Blade Dancer` and carried number `190/221`, which in that export is
**`Forgefire Cape` — `Epic`, `Near Mint Foil`**. The claim was satisfied, the row was found,
the card was listed, and no queue entry has ever existed for it. Nine box-1 cards are that
shape and five are genuinely different cards (`1/51`, `1/223`, `1/262`, `1/310`, `1/311`).

So the cross-check refused 136 right cards and passed five wrong ones, and a fix to only the
first half would have made the pipeline quieter in the wrong direction too.

### What the second signal is

The model reads a NAME and a NUMBER off one photograph. The number finds the rows. The name
is the only other thing on that photograph that can say whether those rows are the right
card — and it was being thrown away. `pipeline/join.py:name_corroborates` compares it against
the rows the number found, and `variant.resolve` gains `name_corroborated: bool = False`:
where the claim empties the candidate list, a corroborating name falls through to the ladder
instead of returning.

**IT FALLS THROUGH; IT DOES NOT RESOLVE.** The claim is released, not believed. Every rung
below runs on the unfiltered rows, so two rows still reach rung 2 as two and still review.
`1/65` and `1/73` are exactly that shape and both are the wrong card — which is the argument
against the shortcut this entry rejects below.

**The boolean is computed by the caller.** `name_index_key` is D35's fold and it lives in
`pipeline/join.py`; `variant.py` importing it back would put one rule in two places, which is
the whole thing that fold exists to prevent.

### Two predicates, because the two questions want different thresholds

`name_corroborates` is strict: one name contains the other and covers at least **60%** of the
longer. `name_disputes` is lenient: the read resembles **no** row — no containment at any
length, and no pair above **0.80** similarity.

They are not each other's negation, and between them sits a band that raises nothing: a
partial read (`Rell` for `Rell, Magnetic`) is too weak to overrule a contradicting rarity and
far too strong to call the card a different one. One predicate serving both jobs has to be
wrong at one of them.

- The coverage floor costs **2** of the 138 releases (`Anivia` against `Anivia, Primal`,
  `Chem-Baroness` against `Renata Glasc, Chem-Baroness`) and is kept anyway, because what it
  guards against is not on this store's record: a three-letter read corroborating every card
  whose name contains it.
- The similarity floor absorbs **23** cards the model simply spelled wrong — `Corfish` for
  `Corphish`, `The Runiation` for `The Ruination`, `Steraks Gage` for `Sterak's Gage`. Every
  one is the right card, and without it each becomes a review entry.

**THE CATALOG'S TRAILING PARENTHETICAL HAD TO BE FOLDED.**
Finding that out is what kept the mirror from shipping broken.
Riftbound's export writes `Rengar, Unseen (Alternate Art)`.
Measured over the whole store, **84 of 195** raw disagreements were that suffix and nothing
else — a flood of review entries for cards nobody had misread. It is decoration on an
identity, the same argument `name_index_key` makes for the embedded number, so it is folded
on the CATALOG side only; a read name is not an index key. Accents are folded for the same
reason, and that one is load-bearing on Pokemon: the model reads `Pokémon Center Lady` and
the export writes `Pokemon Center Lady`.

### What it comes to, on the store as it stands

| | today | after |
|---|---|---|
| `rarity_claim_mismatch` refusals | 159 | 23 |
| refusals released and listed | — | **136, every one on the SKU the human chose** |
| released onto a DIFFERENT SKU | — | **0** |
| new `name_disputed` review entries | — | 35, including all five of box 1's wrong cards |

`routing.NAME_DISPUTED` is a routing reason and not a ladder one, following D35's precedent
exactly: it is a fact about how well the row FITS the card, which is the catalog's question,
and like `number_unread_name_matched` the JOIN writes it over a resolution the ladder
completed. Rung 0 is exempt from both halves — a human who looked at the photograph has
already answered the question, and re-raising it is the sixteen-cards failure D3 rung 0
exists to prevent.

### The group press was suppressed by two cards out of a hundred and one

`groupOffer` required the WHOLE filtered worklist to be uniform. The owner's parked queue
held **101** entries for this run, **99** of them offering exactly one row of one condition
(`Near Mint Foil`) and **two** offering two. Those two returned null for the other
ninety-nine, and the ninety-nine were answered one press at a time.

It is now the largest cluster **anchored on the card on screen** — anchored rather than
largest-anywhere, because D29's eligibility rests on the operator looking at the photographs
they are answering, and a group they are not standing in inverts that. A `name_disputed`
entry is never in a group at any size: that reason exists because two readings of one
photograph disagree, which is precisely the card D29's *"a claim about a set of cards nobody
is looking at individually"* must not sweep up. The confirm panel says how many the press is
leaving behind, because an unstated remainder reads as "the queue is done".

**The server's check is untouched, byte for byte.** A subset of a set that satisfied it
satisfies it by construction, so this narrows what is offered and can never widen what is
accepted.

### The two words are on screen, and neither ever was

`rarity_claim_mismatch` is the one reason in the vocabulary whose meaning is *"A contradicts
B"*, and it could name neither A nor B. `docs/DECISIONS.md` had recorded that as needing a
schema change; it is one, and it is additive — `rarity` on each candidate row and
`rarity_claim` on the read. The sentence now says *"You claimed this stack holds Epic, and
every row 190/221 found is Rare"*, and falls back to the old wording for any entry queued
before the fields existed. That is what turns a 141-card mystery into a one-card diagnosis.

### What is rejected

**A blanket "one candidate means auto-approve."** `1/51` is the counterexample sitting in the
owner's store: one row, claim satisfied, wrong card, never asked about. The rule is two
AGREEING signals and never one uncontradicted row.

**A `join --ignore-rarity-claim` flag.** `pipeline/variant.py` records what happened to the
last per-run bypass switch, and the sentence is the ruling: *"a switch every run flips is a
default wearing a flag."*

**Loosening the server's group eligibility, or letting a group press write an L-search row.**
A catalog row found by a person looking at one photograph may not be applied to cards nobody
looked at.

### What this does not do

**It does not reopen the 141 cards already answered.** `store/queues.py:upsert` will not
re-queue a position a human has cleared, deliberately and correctly. This is a forward fix:
it changes what the NEXT join asks, and the work already done stays done.

**The rule has been measured on Riftbound and asserted on Pokemon.** Every figure in this
entry comes from riftbound runs, because that is what the store holds. D23's own motivating
misses are Pokemon, so the harness carries a Pokemon arm — but an arm is not a measurement,
and the first Pokemon box through this rule is where it gets one.

**`name_disputes` has no evidence about a game that spells names unlike the model does.**
The 0.80 floor was fitted to two games' worth of real reads. A
third game arriving with a different naming convention is a reason to re-measure it, not to
assume it travels.
