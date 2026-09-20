## D237 — What the archive's 16 refusals could have caught, and what could not

**The question, in the owner's own words.** After D233 and D234 closed every cause a rule
could remove, `pkmnscan archive sweep` still ends with 16 names it cannot resolve. The owner
asked whether any of the 16 are identification errors a check could have caught earlier.
This entry answers that, one class at a time. Each class is measured against the owner's
real store. It is not assumed.

Fifteen of the sixteen are named below and matched to a class. The sixteenth is a transient
network failure. This session could not independently identify it. See the closing section.

**No validation check is built here.** This entry names what a check would SEE (D173's rule
for a candidate mechanism). It measures how many of the 15 subjects each class would have
caught. Ranking which ones are worth building is the owner's call, not this session's.

### Class 1 — a name too long to be a card name at all (1 of 15)

One refused name reads as a full paragraph of rules text. In full:

```
While you control this battlefield, when you play a spell, if you spent 4 or more,
PREDICT: (Look at the top card of your Main Deck. You may replace it.)
```

It is stored as a card NAME, 152 characters long, in `Unleashed`.

Measured over every name in the store, 3,510 cards: the next-longest name is 35 characters.
The gap between 35 and 152 is 117 characters. No run of names climbs gradually into this
one. It sits alone past 60 characters.

**What the check would SEE.** A captured name can cross a fixed length threshold. That
threshold sits well above every other name this store has ever held. Past it, the text is
not a card name. It is rules text the model transcribed instead of a title. This is
checkable the instant a name is captured. It needs only the string, no catalog and no
network. **Mechanizable now.**

### Class 2 — a number whose own denominator disagrees with its set (2 of 15)

One card reads `102/166` in `Origins`. Another reads `181/281` in `Unleashed`.

Measured denominators seen per set, this store:

| set | dominant denominator | count | this card's denominator | count |
|---|---|---|---|---|
| Origins | 298 | 258 | 166 | 1 (this card) |
| Unleashed | 219 | 1,025 | 281 | 2 |

**What the check would SEE.** This store does not store a set's own printed total per card.
The total is implied by the denominator every OTHER card of that set already carries. A
number whose denominator is not the set's overwhelming majority is a candidate for review.

This is not the same claim as "wrong." D234's own worked example is the counter-case: `ME01:
Mega Evolution`'s `Bulbasaur - 133/132`, a genuine secret rare printed above its set's total.
That is a real card, correctly numbered, and this exact check would also flag it. The check
can only say "uncommon for this set, look at the photo." It cannot say "wrong" on its own.
That is `CLAUDE.md`'s own boundary: two agreeing signals release a claim (D146). One
disagreeing signal never resolves one on its own.
**Mechanizable as a review signal, from stored data alone, with no network call. Never as an auto-repair.**

### Class 3 — a number with more digits than the set has cards (1 of 15)

One card reads `0934` in `ME01: Mega Evolution`, a 132-card set. Measured: no other card
this store holds in `ME01: Mega Evolution` carries more than 3 digits.

**What the check would SEE.** This is class 2's sibling, and it is cheaper. A number whose
digit count exceeds every other number's digit count in the same set is checkable without
computing a denominator or a mode. It is a plain digit-count comparison over the set's own
stored numbers. The same caveat as class 2 applies. It flags. It never repairs.

### Class 4 — a name one edit away from a DIFFERENT name in this store (3 of 15)

Measured: every OTHER distinct name this store holds in the same set, compared by
`difflib.get_close_matches` at a 0.82 cutoff. No catalog. No network. Just this store's own
`cards.name` column.

| refused name | set | close match already in this store |
|---|---|---|
| `Shadbow Temple` | Vendetta | `Shadow Temple` (a different card, 1 copy) |
| `Seal of Power` | Spiritforged | `Seat of Power` |
| `Glorious Executioner` | Spiritforged | `Draven, Glorious Executioner` (the same card's other two copies carry the full title, and resolved fine) |

**What the check would SEE.** A captured name can match no product in its own set. It can
still sit one edit away from exactly one OTHER name this store already holds in that set.
That is a likely misread. The store is comparing itself to itself, not to the mirror. This
is the narrowest and cheapest class here. No catalog call. No arithmetic. Just a same-set
string comparison against data already on disk.

It is still a review signal, not a repair. A set can legitimately hold two names one letter
apart, a card and its own errata for one example. The check routes to a human. It never
substitutes the close match on its own. **Mechanizable now, from stored data alone.**

### What could not be checked from stored data — 8 of 15

Five names carry a blank number. None has a close match to any other name this store
holds in its set: `Ambushed Recital`, `Black Flame Attar`, `Kihoud Temple`, `Treasure`,
and `Warwick, Unleashed`.

Two more are internally contradictory. `Green Father` has three stored copies, and they
carry three different numbers: `195/210`, `155/219`, and blank. `Heart of the Tempest` has
four stored copies. Two are blank. One reads `132/526`. One reads `155/166`. Neither pair
agrees with itself, let alone with a catalog.

One more, `Exeggutor`, shares its SKU with six other copies that all carry number `005`.
Only this one copy is blank. A shared SKU across two different stored numbers is itself the
ambiguity, and no rule resolves which copy is right.

Measured: a blank number is common in every Riftbound set this store holds, not rare.
`Vendetta` carries one in 481 cards (11%). `Spiritforged` carries one in 939 (5.6%).
`Unleashed` carries one in 1,218 (3.6%). `ME01: Mega Evolution` carries one in 542 (6.8%).
A blank number alone is not a signal. Most of those cards resolve fine on name alone.

What actually makes these 8 refuse is that the name does not uniquely match a product in
the declared set either. Knowing that needs the exact question
`pipeline/pricehistory.py:ProductIndex.find` already asks, against the live mirror, at
sweep time. No rule over this store's own data can answer it earlier. This store has no
second, independent source of truth for a set's real card list. D15 vendors the Pokemon
catalog locally. Riftbound and the newest Pokemon sets have no local mirror at all. `ME01:
Mega Evolution` is not in `vendor/pokemon-tcg-data`, checked directly.

This is `CLAUDE.md`'s own boundary, not a gap in this analysis. A machine cannot tell a
confident correct reading from a guess. A blank number with an unmatched name looks, from
stored data alone, exactly like a genuinely new card this store has never seen before.

The only way to mechanize this class earlier than the archive does today is to run the same
live lookup at capture or join time. That closes the gap between captured and priced from
months to minutes. It is a real option. It is also an architecture change with its own
cost. A network call per ambiguous card, at capture time, hits a host already measured to
throttle this session (D222). Naming it here, rather than building it, leaves that
tradeoff for the owner to rank.

### What could not be checked at all — the sixteenth refusal

The task names 16 total refusals. One is a transient network failure, to be identified from
the run and excluded. This session could not independently identify it. No raw sweep log is
committed to this repository. A search under `docs/`, the debts, the decisions, and any
`.serve/` artifact found none of the 15 identification-error subjects named anywhere else.
None names a sixteenth entry. Re-running `archive sweep` to reproduce the missing entry is
outside this task's own scope. No network call and no `pkmnscan archive` command were run
in this session.

The 15 named subjects above are what this entry, and the routing built alongside it, act
on. Each is independently confirmed against the owner's real store. Two of them,
`Exeggutor` and `Garganacl`, are already named in D234's own closing paragraph. This
sixteenth entry is reported as unknown rather than guessed at. `CLAUDE.md`'s own rule is
that a read that could not run is named as unknown, never as clear.

### Summary

| class | count | mechanizable from stored data, no network |
|---|---|---|
| 1. name too long | 1 | yes, a length threshold |
| 2. denominator disagrees with set | 2 | yes, as a review flag, never a repair |
| 3. digit count exceeds set | 1 | yes, as a review flag, never a repair |
| 4. one edit from a sibling name | 3 | yes, as a review flag, never a repair |
| blank number, unmatched name | 8 | no, needs the live mirror, same as the archive |

Governs nothing yet. No check named here is built. See `D238`,
this session's sibling entry, for the build that routes all 15 to the review queue. Cites
D146 (two agreeing signals release a claim), D173 (a mechanizable rule names what the check
would see), D233, and D234 (the two mechanism rounds this analysis follows).
