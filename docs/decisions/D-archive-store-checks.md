## D-archive-store-checks — Four stored-data checks, built whole, from D237

**What this builds.** The four checks D237 named. Each is
mechanizable from stored data, with no catalogue and no network. The owner took all four.
`pipeline/identity_checks.py` holds the pure logic. `pkmnscan cards checks` is the one
reachable place a human runs them, read-only, beside `cards name` and `cards audit`.

1. **A name too long to be a card name.** `flag_long_names`, threshold 60 characters.
2. **A denominator that disagrees with its set.** `flag_denominator_outliers`, per set,
   against that set's own dominant denominator.
3. **More digits than the set has cards.** `flag_digit_count_outliers`, per set, against
   that set's own dominant numerator length.
4. **A name one edit from a different name this store holds in the same set.**
   `flag_near_duplicate_names`. `difflib.get_close_matches` at a 0.82 cutoff. Same-set only.

**What this does not build.** The SKU self-contradiction check is a separate build. Two
copies of one SKU can read different numbers. That check is kept apart, on the owner's own
ruling. It lives in its own module and its own decision entry,
the sku-number-contradictions build (a separate PR). It is not part of this one. A blank number is not a check
here either. The cited analysis measured it at 3.6% to 11% of every Riftbound set the
owner holds. Most resolve fine on name alone. A check that fires on one in ten fine cards
is spent (`CLAUDE.md`'s cry-wolf rule).

**Every check is a review signal, never a repair.** None of the four writes a card. Each
returns a `Flag` a human reads beside the photograph. D234's own worked example is a
genuine secret rare, printed above its set's total. Classes 2 and 3 flag it exactly as
they would flag a misread. The check can say "uncommon for this set, look at the photo,"
and nothing stronger. D146's own boundary: one disagreeing signal never resolves a claim
alone.

### Threshold choices, and why

**60 characters (class 1).** Measured over the owner's 3,510 stored names. The
next-longest real name is 35 characters. The one known defect is 152. Sixty sits in the
gap. It sits well above every real name this store has held. It sits well below the one
that is not a name at all.

**Dominant, not first-seen (classes 2 and 3).** The check compares against the value the
MAJORITY of a set's own cards carry. It never compares against the first value a pass
happens to read. `scripts/identity-checks-selftest.py`'s mutation arm proves the choice is
load-bearing. A mutant compares against the first-seen value instead. Feed it a set where
the one disagreeing card is captured first. The mutant blames the majority. The real
function still finds the minority.

**0.82 cutoff (class 4).** This is the cutoff the cited analysis measured against the
owner's store. It stays tight enough to still catch a single glued letter
(`Shadbow`/`Shadow`). It stays loose enough to register a champion's short title beside its
own full name (`Grandmaster at Arms`/`Jax, Grandmaster at Arms`). That second shape is the
one D237 names as `Draven, Glorious Executioner`, "resolved
fine."

### Measured against the owner's real store, read-only, 2026-09-20

| check | flags | subjects (unique names/sets) |
|---|---|---|
| long_name | 1 | the one known 152-character defect |
| denominator_outlier | 108 | across `Spiritforged`, `Vendetta`, `Origins`, `Unleashed` |
| digit_count_outlier | 6 | 5 cards in `ME01: Mega Evolution`, 1 in `Vendetta` |
| near_duplicate_name | 257 card copies, 47 distinct name pairs | across all six named sets |

**`long_name` and `digit_count_outlier` match the cited analysis exactly.** The
dominant-count design keeps them narrow.

**`denominator_outlier` and `near_duplicate_name` fire far more broadly than the analysis's own counts of 2-of-15 and 3-of-15.**
Those two counts were over the 15 already-refused subjects only. This build runs the same
rule over every card the store holds. The widening is intended. This is a general
capability. It is not a re-run of one prior measurement.

**No false-positive count is reported for classes 1 through 3.** Each is a plain,
per-set arithmetic comparison. None does fuzzy matching. Every flag is either the exact
shape the check was built for, or a genuine minority reading. The check is honest that it
cannot call the minority "wrong" on its own — see the D234 secret-rare caveat above.

**Class 4's 47 pairs were read by hand.** Most look like real OCR confusions
(`Corfish`/`Corphish`/`Corpfish`/`Corprish`, `Alkali`/`Akali`, `Mel`/`Mei`). A visible
minority carry the champion-short-title pattern the analysis already calls "resolved
fine." That pattern is a known, accepted shape of this check's own signal. It is not a
defect in the check. 257 flagged copies against 3,510 stored cards is 7.3%. That volume is
low enough that this check does not cry wolf. It is not shipped blind to that number.

### What proves it

`scripts/identity-checks-selftest.py`. 13 arms. One positive and one negative case per
check — the exact subjects the cited analysis measured, and the same shape with the defect
removed. A case proving classes 2 and 3 flag a genuine rare print honestly, rather than
hiding it. A case proving class 4 stays inside its own set boundary. A case reproducing the
analysis's own `Draven, Glorious Executioner` finding. A mutation arm over class 2: it
fails on a "compare to the first reading" bug, then shows the real "compare to the
dominant reading" logic survives it. Not wired into `make check`. This follows
`scripts/pricearchive-selftest.py`'s own precedent for a package whose one caller is a CLI
subcommand, rather than a pipeline step under harness coverage.

Governs `pipeline/identity_checks.py`, `cli/cmd_cards.py`'s `checks` subcommand, and
`cli/__main__.py`'s `cards checks` parser. Cites D146, D173, D234, and D237.
