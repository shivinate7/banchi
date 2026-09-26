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
matches as a substring ANYWHERE in a folded field, with no length minimum. ONE UNIT
THROUGHOUT THIS ENTRY, CARD RECORDS, NEVER SKUS (F6-7, round-8 Opus delta review,
2026-09-25, correcting round-7's own SKU-counted version, which then also picked
`on_hand` — excluding sold and departed copies — where `match_query`'s own count
covers every state). `sc` measured on the real store: `match_query` accepts 195 card
records, `do_search` returns 56, DROPPING 139. This is the floor's own known cost,
accepted at the time R3 shipped, restated here in a real number rather than only in
principle.

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

**F6-7: A SKU COUNT IS NOT A CARD COUNT. Round-7's own attempted fix was ITSELF wrong, corrected again in round 8, below.** R5-4's disclosure originally said `sc` drops
"33 cards" on the real store, meaning 33 SKUs. Round 7 corrected the number to cards,
but picked `on_hand` (excluding sold and departed copies) rather than the full count
`match_query` itself counts — the two units still disagreed. Round 8's own re-measurement,
using ONE unit throughout, card records in every state: `match_query` accepts 195,
`do_search` returns 56, dropping 139. Corrected above, in place.

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

**ROUND 8, OPUS DELTA REVIEW, 2026-09-25, ON f2d13ae7.** Four blocking items, narrow —
0 false positives found in 7,000 fuzz queries, timing already inside bound, the
wolf-crying gone. Three more disclosures.

**1. F6-2 WAS STILL OPEN ON THE REAL COPY.** Round 7 lowered only the ZERO-PAD rule's
floor. `6a` missed "Order Rune (R06a)" (2 card records). `1a`-`6a` missed 40 real cards
combined. `match_query` accepts a 2-character digit-bearing term by rule 7's own
SUBSTRING check, which has no floor at all. The borrowed 3-character TEXT floor on the
SUBSTRING widening rule was the actual gate. Fixed: a digit-bearing 2-character term now
also reaches the substring rule, matching `_is_floor_query`'s own definition of "not a
floor term".

**2. `rows_walked` COULD NOT SEE A SEPARATE CODE PATH'S OWN SCANS.** Round 7's counter
lived inside `_fts_supplemental_candidates`'s own loop body. That was proof the loop
ran, and nothing else. Loading round-6's four separate per-term SQL sources back in
stayed green at `rows_walked=0`. A different function's own scans never touched that
counter at all. Fixed: `conn.set_trace_callback(_count_cards_scan)`, attached to the
connection itself, counts a `cards` table scan no matter which Python function issues
the SQL. Confirmed by literally restoring the round-6 architecture: `rows_walked` now
reads 16 (4 sources times up to 8 terms scanning independently), never 0.

**3. `match_rank_calls` COUNTED AT THE CALL SITE, NOT INSIDE `_match_rank`.** A caller
restructuring could defeat it. Moving the rank loop's own computation before
`match_query` runs is the same shape as M1, arrived at by reordering rather than
changing a condition. This could leave the call-site counter's own increment behind
while `_match_rank` still ran just as often. Fixed: the counter is now the first line
inside `_match_rank` itself. It fires whenever the function actually runs, regardless of
how the caller decided to call it.

**4. `match_query_calls` WAS NEVER ASSERTED.** Bounded now at 2x the store's own card
count in the hostile timing case. This is generous against every legitimate shape
measured (at most 1,427 calls), nowhere near what an unbounded blowup would produce.

**5. THIS ITEM WAS WRONG, ROUND 8, AND IS REPLACED HERE. "0 extra-zero composed queries missed" and "neither reproduced" were both FALSE.** The round-8 builder tested NEIGHBOURS of the reported inputs — `0024a` (no
slash) and a bare `4` — never the EXACT reported shapes (`0027/166`, and `4` specifically
inside a longer sentence, "spent 4"). Tested against the exact inputs, on a fresh real
store copy: EVERY sampled query of four shapes missed. Bare-letter composed (`24a/219`
for `024a/219`): 11 of 11. Extra-zero letter composed (`0024a/219`): 11 of 11.
Extra-zero plain composed (`0027/166` for `027/166`): 300 of 300. Zero-padded digit
word in name text (`004`, "spent 4"): 1 of 1.

**F1, round 9, CLOSES ALL FOUR SHAPES, in number normalization.** The candidate
widening's own gate, `match._number_shape_ok(term)`, checks one side of a number only.
A term containing `/` fails it outright. No COMPOSED query term ever reached any number
widening at all, whatever its zero-padding. `match._number_match` (the DECISIVE step)
never had this bug — it already splits on `/`, through `match.canonical_number`.
`_number_candidate_forms` now computes the SAME canonical forms `match._number_match`
itself accepts, so the widening step and the decisive step agree. The digit-word shape
was separate. A pure-digit term always reached the zero-pad widening. That widening
only ever checked the NUMBER columns, never `name`/`set_hint`/`note`. Fixed by
`_text_digit_word_matches`, mirroring `match._digit_word_match` against the same three
text fields the substring rule already reads. Re-verified at scale on a fresh real-store
copy: 0 of 52 bare-letter composed queries missed. 0 of 52 extra-zero letter composed
queries missed. 0 of 300 extra-zero plain composed queries missed.
**52 IS CARD RECORDS, NEVER DISTINCT QUERIES** (round 10's own check, 2026-09-25, after
the reviewer counted 22 on the same store). 52 letter-composed card records share only
22 distinct numbers.
Several boxes hold more than one physical copy of the same printing. A sweep built per
CARD queries the same number twice. A sweep built per distinct number or SKU queries
it once. Both counts are correct readings of the same store, on different units. This
entry's own rule (item 6, below) already settled the unit for every other figure here
as card records, never SKUs, so 52 stays. Case-table row:
`case_do_search_number_widening_mirrors_canonical_number`. It replaces round 8's own
`case_do_search_known_gap_hash_prefixed_composed_letter_number`. The `#`-prefixed
composed shape that case disclosed as a gap closes as a side effect of the same fix.

**6. ONE UNIT THROUGHOUT THIS ENTRY, CARD RECORDS, NEVER SKUS.** R5-4's own disclosure,
above, is corrected in place. F6-7's own round-7 fix was ITSELF wrong. It corrected the
unit to cards but picked `on_hand`, excluding sold and departed copies, where
`match_query`'s own count covers every state. `sc` measured on the real store:
`match_query` accepts 195 card records, `do_search` returns 56, dropping 139.

**7. THE FOLD-PREFIX RULE IS DELETED, NOT GUARDED. M10: "if it is redundant, delete it." CORRECTED, round-9: "strict superset" was FALSE.** A differential over the real store found one real disagreement: `bf` found "B.F. Sword"
(`161/221`) through the fold rule, which stripped ALL punctuation before comparing. `bf`
finds nothing without it. `bf` is a 2-character term with no digit — the SAME accepted
1-2 character TEXT floor (`_is_floor_query`) every other short text term already lives
inside. The behaviour stays as it is. See `case_do_search_fold_deletion_narrowed_bf_to_
the_accepted_floor` and `_fts_supplemental_candidates`'s own docstring.

**RE-TIMED ON A FRESH REAL-STORE COPY, R8-FIXED CODE:**

| Query shape | p50 / p95 | body |
|---|---|---|
| 1-char (`a`), floored | 121.6ms / 125.8ms | 351KB |
| 2-char (`ab`), floored | 44.1ms / 48.8ms | 14KB |
| Hostile 100×`1` | 231.0ms / 236.9ms | 12KB |
| Hostile 100×`e` | 134.9ms / 141.8ms | 161KB |
| Hostile 66×`ex` | 73.2ms / 76.4ms | 45KB |
| Hostile 50×`001` | 59.4ms / 63.6ms | 12KB |
| R6 hostile 8×`/NNN` | 143.0ms / 145.9ms | 63B |
| R6 hostile mixed | 45.9ms / 48.1ms | 60B |
| R7 hostile 8×mid-word | 64.8ms / 67.4ms | 61B |
| Bare number (`132`) | 53.2ms / 56.8ms | 12KB |
| Floor `sc` | 59.8ms / 64.3ms | 44KB |
| F6-1 letter-prefixed (`tg5`) | 35.6ms / 39.4ms | 31B |
| **F6-2 short number-shaped (`6a`)** | **47.4ms / 48.6ms** | **6KB, a real hit now** |

Every shape stays under 240ms p95. F6-2's own `6a` row went from a 30-byte empty body
(round 7) to a 6KB real result, at no measurable timing cost.

**MUTATION RESULTS, ON THE FINAL HEAD, EACH CONFIRMED RED THEN RESTORED:**

| Mutation | Reverts | Result |
|---|---|---|
| M1 | R5-1 (decisive check before the rank loop) | 4 cases fail |
| M2 | R5-2 (composed-number `/%` widening) | 5 cases fail, including the fuzz |
| M3 | R5-3 (case-folded widening dedupe) | 2 cases fail |
| M4 | F6-1 (letter-prefixed number widening) | 3 cases fail, including the fuzz |
| M5 | reorders the rank loop before `match_query`, not merely `if True:` | 4 cases fail. Round-7's own call-site counter would have missed this. The round-8 counter, inside `_match_rank` itself, does not |
| M8 | F6-2 (the 2-character digit-bearing substring floor) | 2 cases fail |
| M10 | the fold-prefix rule | deleted outright, nothing left to mutate |

M6, M7, M9, M11 and M12 are not described in this round's brief. This entry names only
the mutations it was given a definition for, rather than guessing at the rest.
**ROUND 9, OPUS DELTA REVIEW, 2026-09-25, ON 28d233b2.** Three blocking items, one doc
item. All four closed here.

**F1 IS THE FOUR-SHAPE FIX ABOVE (item 5).** Round 8's own D271 text was wrong about it,
also corrected above.

**F2: `rows_walked` COULD NOT SEE A SECOND CONNECTION.** Round-8's own claim — "no
matter which code... issues it" — overclaimed. The trace is scoped to ONE connection,
`do_search`'s own. A per-term scan issued on a SECOND, untraced `db.connect(...)` stayed
green at `rows_walked=0`. The round-8 test suite never forced the widening branch at
all (`in (0, 1)` passes on a query that never widens too). Fixed two ways: the docstring
now says exactly what the trace sees, scoped to one connection, never "any code
anywhere". A new case,
`case_do_search_rows_walked_is_exactly_one_when_widening_is_needed`, names a query
that MUST widen. It asserts `rows_walked == 1` exactly. A disconnected trace, or a scan
on an untraced second connection, now reads 0 here and fails.

**F3: EACH COUNTER NEEDED A KNOWN NON-ZERO FLOOR.** Every existing case set only an
UPPER bound. Deleting either increment (`match_rank_calls` inside `_match_rank`, or
`match_query_calls` in the rank loop) stayed green — 0 is always at or under any upper
bound. Two new cases, each a single-term query that matches a real card: `match_rank_
calls >= 1` and `match_query_calls >= 1`.

**F4 IS THE "STRICT SUPERSET" CORRECTION ABOVE (item 7).**

**F5: `_SEARCH_WORK_COUNTERS` IS UNLOCKED MODULE STATE, NOTED.** `REQUEST_SLOTS` threads
concurrent requests through the same dict, unlocked. Production never reads it, so there
is no user-facing effect — but a concurrent TEST could read another request's counts.
Documented at the dict's own definition: tests must read it single-threaded, one
`do_search` call per `_reset_search_work_counters()`.

**MUTATION RESULTS, ROUND 9, EACH CONFIRMED RED THEN RESTORED, AGAINST THE FINAL 192-CASE TABLE:**

| Mutation | Reverts | Result |
|---|---|---|
| F1's own fix (`_is_number_shape` back to `_number_shape_ok`) | the composed-number normalization fix | 2 cases fail |
| Composed-number prefix check removed (equality only) | the composed-number widening | 6 cases fail |
| `conn.set_trace_callback` removed | F2's own fix | 1 case fails |
| A second, untraced `db.connect(...)` added for the row walk | F2's own fix | 1 case fails |
| `match_rank_calls` increment removed | F3's own fix | 1 case fails |
| `match_query_calls` increment removed | F3's own fix | 1 case fails |
| M1 (decisive check before the rank loop) | R5-1 | 4 cases fail |
| M3 (case-folded widening dedupe) | R5-3 | 1 case fails |
| M8 (the 2-character digit-bearing substring floor) | F6-2 | 2 cases fail |

Every mutation here was chosen because round 9's own review named it directly.


**ROUND 10, OPUS DELTA REVIEW, 2026-09-25, ON fdc84825.** One blocking item, one medium,
two doc-only disclosures, one figure check.

**N1: THE SAME CLASS AS F1, ONE LEVEL UP — THE TOKENIZER, NOT THE COMPARISON.** F1
(round 9) fixed `_number_candidate_forms`'s own NUMBER comparison to agree with
`match._number_match`. It never touched what fed a TERM into that comparison in the
first place. `_deduped_capped_terms` split a query on bare whitespace
(`text.split()`). `match.query_tokens` — the ONE tokenizer `match_query` (the decisive
step) has always used — also turns a comma into a space and strips edge punctuation
per token. `rengar,24a/219` is one whitespace token. It is two real tokens, `rengar`
and `24a/219`. `/166,` strips to `/166`. Measured on a real-store copy:
`rengar,24a/219` and `repel,126/132` missed 60 of 60 sampled. `/221,` missed 60 of 60.
`/166,` missed all 193 real matches. `004,`, `(004)`, `004.` and `unseen,rengar` all
missed too. Fixed: `_deduped_capped_terms` and the rank loop's own `token_count` now
tokenize through `match.query_tokens`. `_fts_query` was checked and needs no change.
The widening step's candidates are UNIONED with the base FTS hits before the decisive
`match.match_query` check runs. That check is already correctly tokenized. A candidate
the fixed widening step now supplies reaches the decisive check either way. What the
base FTS query found for a malformed string does not matter. Verified at the SAME
scale the reviewer
measured, on a fresh real-store copy, with only the `_deduped_capped_terms` fix:
name-plus-comma-plus-composed-number, 52 of 52 sampled, 0 missed. Trailing-comma
second-half slash, 60 of 60 sampled, 0 missed, and 8 of 8 on every distinct second
half. Case-table row: `case_do_search_comma_and_edge_punctuation_terms_widen`. The
permanent fuzz (`_generate_fuzz_queries` and `_generate_card_sampled_queries`) both
gained comma-joined and edge-punctuation shapes, so a future regression here fails the
fuzz too, never only the two hand-written cases.

**N2: THE HYPHEN FOLD WAS UNGUARDED.** `_number_candidate_forms` already folds a
hyphen standing for the collector-number slash (`match._hyphen_to_slash(bare)`, inside
its own `forms` set) — that line shipped in round 9, but no case ever exercised it.
Removing it kept all 192 round-9 cases green. `0027-166` then misses Hand Hammer
(`027/166`). A new case, `case_do_search_hyphen_fold_finds_a_composed_number`, makes
that term load-bearing.

**N3, DEFERRED, DOC ONLY, NO BEHAVIOUR CHANGE.** `002-64` also matches `264` through
`compact_text` in the shared matcher — `match.py` and `match.ts` alike, not a
server-only quirk. `compact_text` strips every non-alphanumeric character before comparing. A hyphen and
a hyphen-free digit run collapse to the same string on purpose, for names like
"B.F. Sword". A collector number is not exempt from that same fold. This is a known
gap, not a defect this round fixes.

**N4, DEFERRED, DOC ONLY, NO BEHAVIOUR CHANGE.** `_is_floor_query` measures the RAW
token, before edge-punctuation stripping. `B.F` (with its own trailing period, unlike
the bare `bf` case above) counts as OUTSIDE the accepted 1-2 character floor, where
`bf` counts as inside it. The two spellings of the same short fragment disagree on
whether the floor applies. This is a known gap, not a defect this round fixes.

**THE "0 OF 52" FIGURE IS CORRECT — CARD RECORDS, NOT DISTINCT QUERIES.** Explained
in place at item 5, above. 52 counts card records. 22 counts the distinct numbers
those 52 records share, several boxes holding more than one copy of the same
printing.

**MUTATION RESULTS, ROUND 10, EACH CONFIRMED RED THEN RESTORED, AGAINST THE FINAL 195-CASE TABLE:**

| Mutation | Reverts | Result |
|---|---|---|
| `_deduped_capped_terms` back to `text.split()` | N1's own fix | 3 cases fail |
| The hyphen-fold term removed from `_number_candidate_forms`'s `forms` set | N2's own fix | 1 case fails |

Both mutations were chosen because round 10's own review named them directly.


**ROUND 11, GAPS REVIEW, 2026-09-25, ON 74b4682d.** Two owner rulings, one check,
three doc fixes. Both quoted verbatim.

**RULING 1, QUOTED VERBATIM.**

> "No, a hyphen splits (Recommended)": "002-64" must NOT match 264. The hyphen splits
> the number. It must no longer read as `compact_text`'s joined digits. Change it in
> BOTH matchers, `server/match.py` and `app/src/match.ts`, and keep them in agreement
> (the matcher selftest and any parity test). `0027-166` must still find Hand Hammer,
> because the hyphen-to-slash composed form stays.

Round 10's own N3 disclosed this as a doc-only gap. The owner overturned that
disclosure. `_hyphen_to_slash` only changes its input when a hyphen stands BETWEEN TWO
DIGITS. When it does, the hyphen is doing a real job. It stands for the
collector-number slash. `bare` read WHOLE must never also be a candidate form then.
`canonical_number` does not split on `-`. So the whole-string form joins two digit
runs the hyphen kept apart. `002-64` canonicalized whole was `264`. Only when there is
no such hyphen does the plain form still apply.

Fixed in three places, the same shape each time. `server/match.py:_number_match`.
`app/src/kit/match.ts:numberMatch`. `server/capture_server.py:_number_candidate_forms`,
the widening step's own mirror. `0027-166` still finds Hand Hammer through the SAME
composed hyphen-to-slash reading this repo kept since round 9 and 10.

Two case rows landed in the SHARED table, `app/src/kit/match.cases.json`. Both
`scripts/match-selftest.py` and `app/tests/match.spec.ts` read that one table. This is
the ruling's own "keep them in agreement" instruction, built in. A third case asserts
`do_search` end to end:
`case_do_search_hyphen_splits_the_number_never_joins_it`. It ALSO asserts
`match.match_query` directly. The candidate step's own fix already keeps the wrong
candidate from reaching the decisive check for this exact query. Without the direct
assertion, a mutation of `match.py` alone would hide behind `do_search`'s own
filtering.

**RULING 2, QUOTED VERBATIM.**

> "Bring it back (Recommended)": letters that spell a dotted name match it again, so
> "bf" and "B.F" behave the same and both find B.F. Sword. The reviewer's lead: make
> the floor test measure a token AFTER folding, so `B.F` and `bf` classify the same
> way. Then give the folded dotted-initial case a path to B.F. Sword without opening
> every 2-letter term to widening. Show that the 2-character timing stays under 500ms
> p95.

Two halves. First, the TEST HARNESS. `_is_floor_query`
(`scripts/match-selftest.py`) measured the RAW token's own length. `B.F` keeps its own
internal period — `query_tokens` strips only edge punctuation. So `B.F` is 3
characters and counted as OUTSIDE the 1-2 character floor. Punctuation-free `bf` is 2
characters and counted as inside it. Both spell the identical two letters. Fixed:
measure `match.compact_text(token)` instead. That is the same fold the decisive
matcher's own substring fallback (rule 7) already compares on. New case,
`case_is_floor_query_classifies_by_the_fold`, a DIRECT unit check. The permanent fuzz
corpus never happens to carry a query this distinction changes the verdict for. It
could not mutation-prove this half on its own.

Second, the PRODUCT. `B.F` (with its own period) was never actually inside the floor.
At 3 characters it already cleared the existing substring widening unconditionally.
It always found the card once `_deduped_capped_terms` tokenized correctly (round 10).
Only bare `bf` (2 characters, no punctuation) needed a real fix. There is no way to
tell `bf` apart from an ordinary short word like `ex` by the term alone. Reopening the
WIDENING ROW WALK for every 2-letter term was the R3 floor this repo has stood behind
since round 4. The ruling asks for a path that does not reopen it.

`_fts_letter_pair_alternative` (`server/capture_server.py`) is a SECOND FTS5 CLAUSE.
It is ORed with the term's own prefix match inside `_fts_query`. It is an INDEXED
intersection of two single-letter prefixes, `"b"* AND "f"*`. That costs what any
indexed AND costs. It never grows with how common the term is, unlike a per-row
Python scan. It is offered for every bare 2-letter alpha term. Nothing about the term
alone says which are real initials. The decisive `match.match_query` is unchanged. It
still requires its own compact-fold fallback before accepting a row this admits as a
candidate. A false candidate is filtered for free.

New cases: `case_do_search_dotted_initials_are_brought_back` supersedes round 9's own
`case_do_search_fold_deletion_narrowed_bf_to_the_accepted_floor`, which asserted the
now-overturned "does not find" verdict.

`case_do_search_two_character_timing_stays_under_500ms_p95` measures `bf`, `ex`, `hi`,
`on`, `gx`, `sc`, `fl`, `ob`, `ad` and `un` (30 samples) against a 3,000-card store.
`rows_walked` stays 0 throughout. That is the real proof. An INDEXED lookup is what
makes the cost independent of machine load. Isolated on an otherwise-idle machine, p95
measured well under the owner's own 500ms ceiling.

ASSERTED ON WORK DONE, NOT WALL TIME (F6-6, round-7): "a guard that goes red when
nothing is wrong is spent." Inside the full `make check` run, sharing the CPU with
dozens of other checks, the SAME 30 queries measured over 1s wall once. The machine
was busy. The query was not slow. The case's own wall-time check stays a generous
2.0s backstop now, the same shape `case_do_search_hostile_repeated_terms_stay_fast_
on_real_names` already uses for its own 5.0s one.

**CHECK: DOES `#24a` FIND ITS CARD NOW?** Yes, unchanged since round 9. It is already
pinned by `case_do_search_number_widening_mirrors_canonical_number`'s "Rengar, Unseen
(hash)" row (`#24a` finds SKU `8802`). Round 9 added that row when the `#`-prefixed
composed shape closed as a side effect of F1. No new case is needed. The existing one
already covers this exact query and card.

**DOC FIXES.**

L1: the round-10 sentence "`_fts_query` was checked and needs no change" is narrowed
to hold OUTSIDE the accepted floor. A query like `un,9197044` shows why. Once
`_deduped_capped_terms` splits it into `un` and `9197044`, the number term candidates
the row through widening. `un` itself (2 characters, no digit) sits inside the
accepted floor for the WIDENING MECHANISM alone. It still passes the decisive
`match.match_query` fine. `un` is an ordinary plain substring of the card's own folded
text, `"unseen"`. It needs no widening help at all. `_fts_query` needing no change was
never in question for this shape. The floor is what excuses a term like `un` from
ever needing a candidate-generating rule of its own.

L2: `Dr.`, `Lt.` and `Mr.` alone, with no second initial paired beside them, also fold
to a 2-character no-digit term (`dr`, `lt`, `mr`). Each reads as a floor term too,
under `_is_floor_query`'s own fold-based classification. This is disclosed, not
fixed. These are ordinary abbreviated WORDS, not two separate initials joined by a
dot. The mechanism cannot tell the two apart from the term alone. In practice each
already tokenizes as a real FTS5 index token — `unicode61` splits `Dr.` into `dr` at
index time. An actual `Dr. Something` card is found through the ordinary index lookup
regardless of the floor classification. The disclosure is about the TEST'S OWN excuse
covering more ground than true dotted-initial pairs. It is never a missed card.

L3: N4's own cause, corrected. The cause is not "the raw token before edge-punctuation
stripping" in general. The cause is the PERIOD ITSELF, sitting INSIDE the token —
`query_tokens` never strips an internal character. That period is what makes `B.F`
three characters wide where `bf` is two. The `compact_text`-based classification from
ruling 2, above, is what makes the two agree now.

**MUTATION RESULTS, ROUND 11, EACH CONFIRMED RED THEN RESTORED:**

| Mutation | Reverts | Result |
|---|---|---|
| `match.py:_number_match` hyphen-split fix removed | ruling 1 | 1 case fails (direct `match.match_query` assertion) |
| `match.ts:numberMatch` hyphen-split fix removed (built with esbuild, run directly) | ruling 1 | reproduces the bug (`264/300` matches `002-64`) |
| `_fts_letter_pair_alternative` wiring removed from `_fts_term_alternatives` | ruling 2 | 1 case fails |
| `_is_floor_query` back to raw token length | ruling 2's test half | 2 cases fail |

`server/capture_server.py:_number_candidate_forms`'s own copy of ruling 1's fix is not
independently mutation-provable through `do_search`. The decisive `match.match_query`
is fixed and unmutated. It rejects the wrong candidate regardless of what the
widening step offers. A mutation there changes candidate volume, never the answer.
Its own docstring states the mirror it keeps. The direct `match.match_query` case and
the `match.py` mutation above are what prove the rule itself.

Seeded fuzz re-run after every fix: 0 false positives, 640 queries (`_FUZZ_QUERIES`
plus 200 card-sampled).
