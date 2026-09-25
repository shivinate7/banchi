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
359ms, and the mid-word row's own p95 is 33ms. The three synthetic-HTTP columns' slower
numbers on the hostile shapes come from PAYLOAD SIZE on a deliberately broad query, never
from the matcher. See the next paragraph.

**A KNOWN CEILING, RECORDED, NOT MECHANIZED AWAY: RESULT PAYLOAD SIZE ON A BROAD QUERY.** `do_search`'s response is UNPAGED — every ranked SKU's full group, every copy, in
one body. A deliberately broad query (`("e " * 100)`, which matches roughly a third of a
Pokemon-shaped store on the letter `e` alone) returns a 719KB body at 3,000 synthetic
cards and 2.4MB at 10,000. Encoding and writing that body is most of what pushes real
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

The rest of this entry, `harness/tests/t7_store_and_seams.py:check_search_fts5`'s own
`midword` case, and `scripts/match-selftest.py`'s case 16 all now assert the FOUND
direction. `docs/specs/store-scaling.md` item 8 and `docs/specs/store-scaling/
08-search-fts5.md` keep their original text as the record of the earlier trade-off, each
with a note pointing here. Item 8 is now marked SUPERSEDED on the mid-word point. The
prefix-only design it argued for is not what shipped.

