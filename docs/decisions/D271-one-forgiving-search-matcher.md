## D271 — Every search field uses one forgiving matcher, on the server and in the browser

**The owner's ruling, 2026-09-23 (FLT-06, FLT-04).** One forgiving matcher runs everywhere. It
matches:

- the words of a name, in any order,
- a card number with or without its leading zeros, so `54/132` finds `054/132`,
- a set, a SKU and a box,
- with case and punctuation ignored.

The rule covers the server's FTS5 candidate step too, not only the screens.

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `filtering.md`.

### The premise that no longer holds

No decision set one matching rule for the app. Each screen made its own. The store-scaling work
added an FTS5 candidate step to the server search (`docs/specs/store-scaling.md`, item 8). The
comment on `do_search` names the split of `4/102` into two tokens, and accepts it. Before that
step, a substring walk found `54/132` inside `054/132`.

### The evidence

The filtering lens searched the same cards on four screens.

- **Inventory and Cards to pull** (the server): `54/132` finds nothing, and `054/132` finds
  the card. `heimerdinger-inventor` finds nothing, and `heimerdinger inventor` finds the card.
  The index finds an accented name, then the rank step drops it (FLT-04, FLT-05).
- **Sales** matches the literal string in the name only. `akali deadly` fails, and
  `akali, deadly` works. A SKU finds nothing, and the field says "Search cards" (FLT-06).
- **Graveyard** matches the literal string. `B4` and `Damaged` find nothing, and its rows draw
  both (FLT-06).
- **Orders** matches the buyer name and a TCGplayer number that the row does not draw (FLT-07).

### What the old rules protected, and what protects it now

The FTS5 step protects a fast search over the owner's store, about 2,500 cards. The lens did not
measure speed at that scale. The new matcher keeps the candidate step. It folds the index and
the query the same way before they meet: case, punctuation and zero padding. The rank step uses
the same fold, so it cannot drop what the index found.

D214 (a gross-revenue retrospective is its own route) scoped the Sales search to names. The
one matcher widens that field to the SKU, number and set of the row. The outcome D214 protects,
a search by name, stays.

### What one matcher means in code

One fold function per side. The server's fold serves `do_search` and every route that searches
cards. The browser's fold lives behind the kit-data lane's `useSearch`, and every search field
uses it. A shared table of cases proves both sides agree. It runs in `make harness` for the
server and in a browser spec for the client.

### What is still open

- **Typos and a near match.** FLT-05 asked for the closest name on a miss. Not ruled.
- **Speed at the owner's scale.** Measure before and after on a store of 2,500 cards or more.

Accents are settled by an orchestrator call, not an owner ruling. The matcher folds them, because the
"forgiving" ruling covers them. The owner can reverse that call.

### Search is not the join

The matcher reuses the number rules the join already has: `pipeline/join.py:number_index_key`
and the store's own number helpers. It stays game-aware. Riftbound keeps its code verbatim, and
Pokemon composes the zero-padded number over the printed total. A fuzzy match such as `54` to
`054` is fine in search. It must never feed the join. CLAUDE.md already says why: zero padding is
composition only, never matching.

### What is built

The server half. `server/match.py` is a same-behaviour Python port of `app/src/kit/match.ts`.
`scripts/match-selftest.py` proves the two agree, over `app/src/kit/match.cases.json`.

The server's own search (`server/capture_server.py:do_search`) now calls `match.match_query`.
The Opus review (2026-09-25) found the port existed. `do_search` never called it. The case
table proved nothing about the actual search. `_fts_query`'s FTS5 candidate step and
`_match_rank`'s ranking tier stay in their own right. `match.match_query` is now the deciding
vote for a candidate, alongside them, not instead of them. See the two functions' own
docstrings for which case still routes through which path.

The filtering lane's own entry for the browser half (slug `one-matcher`) is separate.

**One digit test, corrected.** `kit/match.ts`'s `\d` is JS syntax. It is always `[0-9]`, even
under the `u` (Unicode) flag — the flag widens `\p{L}`, never `\d`. Python's bare `\d` and
`str.isdigit()` are both Unicode-aware. So `server/match.py`'s digit tests (`_has_digit`,
`_DIGITS_ONLY`, `_SKU_SHAPE`, `_HYPHEN_BETWEEN_DIGITS`, and the digit runs inside
`_drop_leading_zeros`/`_number_shape_ok`) are now ASCII-only on purpose. It is the one place
this file departs from Python's own Unicode-aware defaults.

**The ccc-0 gap this entry once recorded was wrong (F7, round-3 Opus review, 2026-09-25).**
The earlier text here said `unicodedata` alone could not express `kit/match.ts:foldText`'s
`\p{M}` (every Unicode Mark, whatever its category) without the `regex` package. It called
the gap a dependency decision rather than a bug. That premise was false.
`unicodedata.category(ch)[0] == "M"` answers the SAME question `\p{M}` does. `Mn`
(non-spacing), `Mc` (spacing) and `Me` (enclosing) all start with `M`. The stdlib alone is
enough. The old code tested `unicodedata.combining(ch) != 0` instead, a canonical COMBINING
CLASS. That class is zero for a SPACING mark such as a Devanagari vowel sign (U+093E,
category Mc), even though it is still a Mark. A ccc-0 mark stayed in the string. It fell
through to `fold_text`'s own "not alnum -> space" step. It became a WORD BREAK instead of
vanishing: folding a letter, that mark, and another letter gave two words. The browser
folded the identical string to one. `server/match.py:fold_text` now tests the category.
The two implementations agree on every mark, spacing or not. `scripts/match-selftest.py`'s
`case_match_fold_text_strips_every_mark_by_category` proves it, verified red on the old
code and green on the new one.

**MID-WORD SEARCH IS ADDED, the owner's ruling, 2026-09-25, verbatim: "Add mid-word search."** The owner set one condition. Mid-word ships "only if a measurement... says
search stays fast." D271 wins over store-scaling item 8's own prefix-only trade-off. That
item is now SUPERSEDED on this one point (below). `do_search("izard")` now finds
"Charizard", the exact case store-scaling item 8 measured and traded away.

`server/capture_server.py:_fts_substring_candidates_for_term` is a fourth candidate
source, one term at a time (R1, round-4 Opus review, 2026-09-25 — see below). It folds
both the query term and each candidate field in Python (`match.fold_text`,
`match.compact_text`). FTS5's own prefix index can never answer this shape: a token has
to start with what was typed. A substring scan cannot use an index. No B-tree ordering
helps a pattern with a leading `%`, or a Python `in` check standing in for one. Its cost
grows with the STORE, not with the term, unlike every other candidate source here. It is
folded in Python, so it cannot be pushed into SQL as a plain `LIKE` either.

**Measured before shipping, never on the owner's own store — until round 5.** Round 3
measured a synthetic 2,600-card store. Round 4 asked for 3,000 AND 10,000 cards. It named
1, 2 and 3-character queries, plus the hostile multi-term shapes R1 fixed. All of it ran
on a `f"Bench Card {i}"` fixture. No real query matched enough of that fixture to see
either R1's rank-loop bug or F2's intersection bug (both round-5 findings). Round 5
rebuilt the fixture with
real Pokemon-shaped names, suffixes (`ex`, `V`, `VMAX`, `VSTAR`), numbers, set names and a
SKU prefix digit. It added a FOURTH column: the owner's own live store, copied read-only
(`sqlite3 store.sqlite ".backup"`, WAL-safe, the original never opened for writing) into a
throwaway `PKMNSCAN_HOME`. Four measurement methods, each labeled. An in-process call
timed directly, and three real HTTP loopback columns (20 requests per shape, JSON encoding
included, matching UX-263's own method) against a running `CaptureServer`:

| Query shape | 3,000, in-process | 3,000, HTTP | 10,000, HTTP | real store (~3,510), HTTP |
|---|---|---|---|---|
| 1-char (`a`), floored (R3) | — | 5.8ms / 17.4ms | 9.0ms / 44.9ms | 117.8ms / 124.8ms |
| 2-char (`ab`), floored (R3) | — | 6.6ms / 9.4ms | 7.0ms / 8.5ms | 44.3ms / 47.5ms |
| 3-char mid-word (`izard`) | — | 162.0ms / 203.4ms | 266.6ms / 329.7ms | 29.9ms / 32.7ms |
| Hostile 100×`1` | 444ms | 444.4ms / 516.9ms | 577.9ms / 707.6ms | 294.7ms / 359.2ms |
| Hostile 100×`e` | 323ms | 474.9ms / 796.9ms | 1055.3ms / 2784.0ms | 148.5ms / 157.3ms |
| Hostile 66×`ex` | 227ms | 450.3ms / 601.8ms | 683.1ms / 807.1ms | 79.6ms / 98.7ms |
| Hostile 50×`001` | 136ms | 89.6ms / 133.9ms | 142.8ms / 149.9ms | 51.7ms / 55.4ms |
| Bare number (`132`) | — | 94.0ms / 115.5ms | 136.2ms / 145.9ms | 48.0ms / 51.7ms |

**THE GOVERNING NUMBER IS THE IN-PROCESS ONE (owner's ruling, round-5 Opus delta review reply, 2026-09-25).** The owner's condition on both mid-word and R1's fix was "fast on a
real-sized store." The real-store column meets it at every shape measured. p95 tops out at
359ms, and the mid-word row's own p95 is 33ms. THIS ENTRY ONCE SAID the three
synthetic-HTTP columns' slower numbers came from PAYLOAD SIZE alone, "never from the
matcher." That claim was ITSELF FALSE (R5-1, round-6 Opus delta review, 2026-09-25). The
rank loop spent real time on the matcher's own decisive check. It did this for every
candidate a broad union could surface, before that check ever ran. See ROUND 6, below,
for the fix and the corrected numbers. The payload-size ceiling this paragraph pointed to
still holds, in the next paragraph, but it was never the WHOLE explanation.

**A KNOWN CEILING, RECORDED, NOT MECHANIZED AWAY: RESULT PAYLOAD SIZE ON A BROAD QUERY.** `do_search`'s response is UNPAGED — every ranked SKU's full group, every copy, in
one body. A deliberately broad query (`("e " * 100)`) matches roughly a third of a Pokemon-shaped
store on the letter `e` alone. It returns a 719KB body at 3,000 synthetic cards and
2.4MB at 10,000. Encoding and writing that body is most of what pushes real
HTTP p95 over 500ms for `e`×100 and `ex`×66 at 3,000+ cards. The owner's real ~3,510-card
store never reaches this cost. A real query there matches far fewer rows than a
deliberately hostile one does (measured: the real-store column's own p95 tops out at
359ms). The ceiling is recorded at `server/capture_server.py`'s own `ponytail:` comment,
where the body is built, and here. Upgrade path: page the response, a `limit`/`cursor` on
`groups`. That is a real change, and it needs its own decision, named and not built here.

**R1 AND F2, ROUND-5 OPUS DELTA REVIEW, 2026-09-25, ON 65b8f39d.** `do_search`'s rank loop
ran `_match_rank` once per REPEATED term per candidate. It was never deduped, a second
copy of R1's own defect one function over from where R1 first fixed it. `("1 " * 100)`
measured 5.6-12.4s at 3,000 cards and 19.9s at 10,000 on the real-name fixture (round-4's
own fixture never matched enough candidates to notice). Fixed by `_deduped_capped_terms`,
one shared helper for both the rank loop and the candidate-widening step. Separately,
`_fts_supplemental_candidates` INTERSECTED across terms. That is wrong whenever only one
term needed a widening. `izard ex` returned 20 rows before the intersection existed, 0
after. `ex` (an ordinary token the base FTS query already covers) never produces its own
supplemental candidate, so the intersection of "what `izard` widened" with "nothing" is
empty. A fuzz found 64 of 300 two-term queries dropped this way. Fixed by a UNION. The
base FTS `hits` dict already carries the real AND across every term. This function only
ever widens what already-passing rows the decisive step sees.

**A 1 OR 2-CHARACTER TERM NEVER REACHES THE SCAN (R3).**
`_fts_substring_candidates_for_term` floors at 3 characters. This is the owner's own
condition: `q=a` measured a 582ms full-table scan before this floor existed.

**A REAL MID-WORD HIT IS A KNOWN CEILING, NOT MECHANIZED AWAY.** The owner's live store
holds about 3,450 cards. At 3,000 synthetic cards, a real hit costs 73-76ms in the earlier
round-4 in-process measurement. The round-5 real-store column measures the mid-word row's
own HTTP cost directly at 30-33ms. At 10,000 synthetic cards it costs up to 330ms over
HTTP, OVER `useSearch.ts:SEARCH_DEBOUNCE_MS`'s 200ms budget. The round-4 review's own stop
condition ("if mid-word still cannot stay under about 200ms for 3+ characters, stop and
report") is met at the store's real scale, confirmed twice now. Once by extrapolation in
round 4, and once directly against a copy of the real store in round 5. It is not met at
10,000 cards, a scale the store is nowhere near. Shipped on that measurement, per the
owner's word. Round-4 reply: "Ship it as built." Round-5 reply: "Do not add a result
cap." The ceiling and its upgrade path are recorded at `_fts_substring_candidates_for_
term`'s own `ponytail:` comment, never only here. The upgrade path is an FTS5 trigram
index, a schema change needing its own decision.

**ROUND 6, OPUS DELTA REVIEW, 2026-09-25, ON ce5a6168.** Four more defects. All found on
the owner's OWN real store (a read-only copy), or by this session's own new fuzz test.
Round 5's fixture still hid them.

**R5-1 (BLOCKING): THE RANK LOOP RAN THE MATCHER BEFORE THE DECISIVE CHECK.** `do_search`
computed `term_ranks` (up to 8 `_match_rank` calls) for EVERY candidate. This ran before
`match.match_query` ever decided whether that candidate was a real match at all. It was
cheap while the candidate set stayed narrow. F2's UNION (round 5) means a query of
several `/NNN` terms can make most of the store a candidate. Each term widens on its
own, and nothing intersects the union back down. `/132 /298 /166 /198 /219 /221 /1 /2` measured
552-578ms on the real store, for a 63-byte body. Almost every candidate was rejected, so
almost all of that time was `term_ranks` no result ever used. Fixed: `match_query` runs
first, and `term_ranks` is computed only for a matched row or a single-term query.

**R5-2 (REAL STORE): THE ZERO-PAD WIDENING NEVER MATCHED A COMPOSED NUMBER.**
`_fts_zero_pad_candidates_for_term` compared `LTRIM(col, '0') = ?` against the WHOLE
column. 2,919 of the owner's 3,510 real cards keep `number` as `027/166`, with an empty
`number_key`. `LTRIM` on that whole string only strips its FRONT (`27/166`). That is
never equal to a bare `27`. `q=0027` dropped 3 of 4 real matches, `0217` 5 of 5, `0190` 3 of 3.
Fixed: also match `LTRIM(col, '0') LIKE bare || '/%'`.

**R5-3: THE WIDENING STEP DEDUPED CASE-SENSITIVELY.** `ex`, `EX`, `Ex` and `eX` counted
as 4 distinct terms. That burned 4 of `_SUPPLEMENTAL_TERM_CAP`'s 8 slots on the SAME
word, spelled 4 ways. `ex EX Ex eX ob OB fl FL izard` returned 0 of 15 real matches. The
cap filled on case variants before `izard`, the mid-word term the one real match needed,
ever got scanned. Fixed: dedupe on the FOLDED form.

**R5-5: THE ZERO-PAD WIDENING NEVER REACHED A DIGIT-PLUS-LETTER NUMBER.**
`_fts_zero_pad_candidates_for_term` gated on digits only, refusing `24a` outright. `24a`
dropped all 8 real matches for a card numbered `024a/219` (Rengar). Fixed:
`_ZERO_PAD_SHAPE` (digits, then 0-2 letters) replaces the digits-only gate.

**RE-TIMED ON A FRESH REAL-STORE COPY, R6-FIXED CODE:**

| Query shape | p50 / p95 | body |
|---|---|---|
| 1-char (`a`), floored | 123.1ms / 129.3ms | 351KB |
| 2-char (`ab`), floored | 45.9ms / 49.7ms | 14KB |
| Hostile 100×`1` | 227.3ms / 234.8ms | 12KB |
| Hostile 100×`e` | 132.1ms / 138.4ms | 161KB |
| Hostile 66×`ex` | 72.0ms / 82.9ms | 45KB |
| Hostile 50×`001` | 50.1ms / 52.5ms | 12KB |
| R6 hostile 8×`/NNN` | 128.7ms / 134.8ms | 63B |
| R6 hostile mixed | 131.6ms / 140.7ms | 60B |
| Bare number (`132`) | 46.0ms / 49.1ms | 12KB |
| Floor `sc` | 60.1ms / 63.5ms | 44KB |

Every shape stays under 235ms p95 on the real store, well inside the 500ms bound the
round-6 review set. R5-1's own `/NNN` shape, the round's blocking finding, dropped from
552-578ms to 128.7-134.8ms.

**REAL MID-WORD HITS, REPLACING THE EARLIER "izard" CELL, WHICH MEASURED ZERO HITS ON THE REAL STORE.** `izard` never appears mid-word in the owner's own card names. No
Charizard was in the live store at capture time. That cell answered a query with no real
target, not a mid-word measurement at all. Real fragments the owner's own names contain:

| Mid-word fragment | p50 / p95 | body |
|---|---|---|
| `engar` | 82.4ms / 92.6ms | 43KB |
| `ion` | 97.2ms / 100.9ms | 93KB |
| `ard` | 96.6ms / 103.5ms | 91KB |
| `ing` | 117.5ms / 123.3ms | 198KB |
| `ter` | 114.8ms / 120.8ms | 183KB |

**DISCLOSURE, R5-4: THE 1-2 CHARACTER FLOOR MEANS `do_search` RETURNS FEWER ROWS THAN `match.match_query` ACCEPTS.** `_fts_substring_candidates_for_term`'s 3-character floor
(R3, the owner's own accepted condition) is a floor on the CANDIDATE step. It is not a
floor on `match_query`'s own rule 7, which has none at all. A 1-2 character text token
matches as a substring ANYWHERE in a folded field, with no length minimum. `sc` measured on
the real store: `match_query` accepts 47 SKUs (195 CARDS — `do_search` groups by SKU, and
a SKU count is never a card count, F6-7, round-7 Opus delta review, 2026-09-25, correcting
this entry's own earlier unit error). `do_search` returns 14 SKUs (25 cards), DROPPING 33
SKUs (170 cards). This is the floor's own known cost, accepted at the time R3 shipped,
restated here in real numbers rather than only in principle.

**DISCLOSURE: A 9TH OR LATER DISTINCT TERM IS NEVER WIDENED.**
`_SUPPLEMENTAL_TERM_CAP = 8` bounds how many distinct terms reach the candidate-widening
step and the rank loop's own `term_ranks` computation. A query naming 9 or more distinct
terms gets no widening for the 9th term and beyond. Those terms still take part in the
DECISIVE `match.match_query` check, which is unbounded. So a candidate the FIRST 8
terms' widening already surfaced is still correctly judged on all of its terms. A row
that needs the 9TH term's OWN widening to become a candidate at all is the gap. No case in this
file's own case table, nor the permanent fuzz, has ever needed a 9th distinct term's
widening to find a real card. The cap is sized against every query shape measured so
far, not against zero cost.

**ROUND 7, OPUS DELTA REVIEW, 2026-09-25, ON e76f6fc2.** Seven more findings, from the
reviewer's own fuzz and mutation tools (`fz.py`, `mut.py`, in the scratchpad) run
against a real-store copy. R5-1 through R5-5 held. Reverting any of them still turns
the fuzz or a named case red.

**F6-1 (real misses): LETTER-PREFIXED NUMBERS NEVER WIDENED.** `_ZERO_PAD_SHAPE` let
only a digit-leading term through. `match.canonical_number` also drops zeros AFTER
leading letters (`tg05` is `tg5`). The real store has 41 cards numbered `R01a`-`R06a`.
`r1a` and `r4a` missed 2 of 2. `tg5`, `swsh22` and `swsh45` missed too. Fixed by reusing
`match._drop_leading_zeros` and `match._number_shape_ok` directly (0-6 leading letters,
1+ digits, 0-2 trailing letters). This is the SAME primitive `match.canonical_number`
itself is built from, done in Python rather than SQL `LTRIM`, which cannot express a
letter-aware strip at all.

**F6-2: A 2-CHARACTER NUMBER TERM NOW WIDENS.** `6a` never reached the zero-pad rule. It
inherited the mid-word TEXT floor (3 characters, R3), which was never about numbers. A
number-shaped term is not a common substring the way a 1-2 character text fragment is.
`match._number_shape_ok` plus a 2-character floor replaces the borrowed one.

**F6-3 (BLOCKING, the owner's ruling: NOT accepted): FOUR WIDENINGS, FOUR SEPARATE SCANS PER TERM.** 8 distinct 3+ letter mid-word terms took 450-536ms p50, up to 860ms
p95 on the real store. Each of the 4 widening sources ran its OWN `SELECT ... FROM
cards` per term, up to 32 scans for one query. Fixed: `_fts_supplemental_candidates` now
reads each card's row ONCE and checks every term's every widening rule against it before
moving to the next row. Re-timed on a fresh real-store copy: the SAME 8-term mid-word
shape now costs 77.8ms p50 / 87.3ms p95. A mutation reverting this fix (splitting the
walk back into 4 SQL sources) measured 261.6ms p50 on the identical query, over 3x
slower, confirming the fix is real, not query-shape luck.

**F6-4: THE FIXTURE WAS TOO EASY.** `_build_pokemon_store` carried each real-store
defect on exactly ONE named card. A mutation reverting the fix that card existed for
could still pass the permanent fuzz, which never happened to query that one card. Fixed:
six SEEDED number shapes (`random.Random(7)`, matching the reviewer's own tool). These
are composed `NNN/MMM` numbers with an empty `number_key`, digit+letter numbers, three
letter-prefixed forms (`RNNa`, `TGNN`, `SWSHNNN`), and cards with no `printed_total` at
all. The permanent fuzz itself grew a SECOND generator, `_generate_card_sampled_
queries`, which builds a query from a RANDOMLY CHOSEN CARD'S OWN fields. This mirrors
the reviewer's `fz.py:gen_queries` exactly, rather than only a fixed word list. M2 and
M4 now turn the fuzz itself red, not only the hand-written single-card cases.

**F6-5: THE R5-1 TIMING ROW COULD NOT SEE ITS SUBJECT.** The old fixture gave every
card the same `printed_total`. A `/NNN` query for any OTHER total matched almost
nothing, never the "most of the store is a candidate" shape R5-1 was about. `_SET_
TOTALS`'s six values (matching real Pokemon printed totals) mean a `/166`, `/198`,
`/219` or `/221` term is now a real, broad candidate on about 1/6 of the store. This is
the same shape the owner's own `/132 /298 /166 /198 /219 /221 /1 /2` query hit at
552-578ms before R5-1. Reverting R5-1 (`if True:` in place of `if matched or token_count
== 1:`) now measures a clean fail on this fixture too.

**F6-6 (a guard that cries wolf): TIMING RED AT LOAD AVERAGE 16, NO DEFECT.** The
timing-only cases went red on a busy CI runner with no code change at all. This
session's OWN re-timing hit the same effect directly. The same query measured 264.0ms
p50 / 353.4ms p95 while `make harness` ran concurrently in the background, and 77.8ms
p50 / 87.3ms p95 once the machine was quiet. Wall time answers "how busy is the
machine", never "how much work did this query do". Fixed: `_SEARCH_WORK_COUNTERS`
(`match_rank_calls`, `match_query_calls`, `rows_walked`), reset before each query and
read after. `rows_walked` proves F6-3's fix directly. It is 0 or exactly the store's own
card count, NEVER a multiple of it. `match_rank_calls` proves R5-1's fix. It is bounded
per query, measured at 11,416 calls under a reverted fix against 0 on the same query
fixed. Wall time stays as a generous 5-second BACKSTOP, which still catches a genuine
algorithmic regression outright, and never cries wolf over a busy machine alone.

**F6-7: A SKU COUNT IS NOT A CARD COUNT.** R5-4's disclosure said `sc` drops "33 cards"
on the real store. Those are 33 SKUs. `do_search` groups by SKU, and a SKU with several
copies is several cards. Measured directly: `match_query` accepts 47 SKUs (195 cards).
`do_search` returns 14 SKUs (25 cards), dropping 33 SKUs (170 cards). Corrected above,
in place, with the count checked directly against a fresh real-store copy rather than
carried forward.

**RE-TIMED ON A FRESH REAL-STORE COPY, R7-FIXED CODE, MACHINE QUIET:**

| Query shape | p50 / p95 | body |
|---|---|---|
| 1-char (`a`), floored | 166.1ms / 186.6ms | 351KB |
| 2-char (`ab`), floored | 72.8ms / 84.2ms | 14KB |
| Hostile 100×`1` | 231.1ms / 238.3ms | 12KB |
| Hostile 100×`e` | 152.2ms / 158.4ms | 161KB |
| Hostile 66×`ex` | 88.8ms / 92.2ms | 45KB |
| Hostile 50×`001` | 71.7ms / 89.2ms | 12KB |
| R6 hostile 8×`/NNN` | 177.8ms / 195.8ms | 63B |
| R6 hostile mixed | 67.3ms / 70.8ms | 60B |
| **R7 hostile 8×mid-word** | **77.8ms / 87.3ms** | 61B |
| Bare number (`132`) | 68.6ms / 72.8ms | 12KB |
| Floor `sc` | 84.2ms / 94.6ms | 44KB |
| F6-1 letter-prefixed (`tg5`) | 46.9ms / 51.8ms | 31B |
| F6-2 short number-shaped (`6a`) | 21.0ms / 21.9ms | 30B |

Every shape stays under 240ms p95 on a quiet machine. The R7 hostile 8-term mid-word row
is F6-3's own subject. It was previously 450-536ms p50, up to 860ms p95, unfixed. It is
now the FASTEST of the hostile shapes measured, at 77.8ms p50.

**MUTATION RESULTS, M1-M4, ON THE FINAL HEAD.** Each reverts one round-5/6/7 fix in
isolation, confirmed red, then restored:

| Mutation | Reverts | Result |
|---|---|---|
| M1 | R5-1 (decisive check before the rank loop) | 3 cases fail |
| M2 | R5-2 (composed-number `/%` widening) | 5 cases fail, INCLUDING the fuzz |
| M3 | R5-3 (case-folded widening dedupe) | 2 cases fail |
| M4 | F6-1 (letter-prefixed number widening) | 2 cases fail, INCLUDING the fuzz |

The rest of this entry, `harness/tests/t7_store_and_seams.py:check_search_fts5`'s own
`midword` case, and `scripts/match-selftest.py`'s case 16 all now assert the FOUND
direction. `docs/specs/store-scaling.md` item 8 and `docs/specs/store-scaling/
08-search-fts5.md` keep their original text as the record of the earlier trade-off, each
with a note pointing here. Item 8 is now marked SUPERSEDED on the mid-word point. The
prefix-only design it argued for is not what shipped.
