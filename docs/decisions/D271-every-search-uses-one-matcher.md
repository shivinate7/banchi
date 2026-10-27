# D271 — Every search uses one matcher

**Ruling (FLT-06, FLT-04).** One forgiving matcher runs everywhere. It matches:

- the words of a name, in any order,
- a card number with or without leading zeros (`54/132` finds `054/132`),
- a set, a SKU and a box,
- with case and punctuation ignored.

The rule covers the server's FTS5 candidate step too, not only the screens.

### The premise that no longer holds

No decision set one matching rule. Each screen made its own. The store-scaling work added an FTS5 candidate step to server search. The comment on `do_search` names the split of `4/102` into two tokens and accepts it. Before that step, a substring walk found `54/132` inside `054/132`.

### The evidence

Four screens searched the same cards.

- **Inventory and Cards to pull** (the server): `54/132` finds nothing; `054/132` finds the card. `heimerdinger-inventor` finds nothing; `heimerdinger inventor` finds the card. The index finds an accented name, then the rank step drops it (FLT-04, FLT-05).
- **Sales** matches the literal string in the name only. `akali deadly` fails; `akali, deadly` works. A SKU finds nothing, and the field says "Search cards" (FLT-06).
- **Graveyard** matches the literal string. `B4` and `Damaged` find nothing, and its rows draw both (FLT-06).
- **Orders** matches the buyer name and a TCGplayer number that the row does not draw (FLT-07).

### What protects what

The FTS5 step protects a fast search over the owner's store, about 2,500 cards. The matcher keeps the candidate step. It folds the index and the query the same way before they meet: case, punctuation and zero padding. The rank step uses the same fold. It cannot drop what the index found.

D214 (a gross-revenue retrospective is its own route) scoped Sales search to names. The one matcher widens that field to the row's SKU, number and set. The outcome D214 protects, a search by name, stays.

### One matcher in code

- One fold function per side. The server's fold serves `do_search` and every route that searches cards. The browser's fold sits behind `useSearch`, and every search field uses it. A shared case table proves both sides agree. `make harness` runs it for the server. A browser spec runs it for the client.
- Every browser search field calls `matchQuery`/`filterByQuery`, with no named exception (lane F11b). Ruling: one matcher, called the same way everywhere. Ranking stays local where a screen must order results. The palette's `rankMatch` gives an exact or prefix hit a higher tier than a plain match. `matchQuery` decides whether a row matches at all.
- `MatchFields` has an eighth field, `raw` (rule 8 in `kit/match.ts`'s header): a plain, case-folded substring with no word rules. Codes, key caps such as `⌘K`, and Capture's box number use `raw`. A digit run inside one, such as `234` in `PROMO1234`, must still match. Rule 7's digit test only matches the start of a word. `server/match.py` does not carry `raw`. No server caller matches a code or a key cap today.
- Per screen:
  - **Sales** (`Revenue.tsx`): the query also matches `row.skus` and the set name. Both fields already existed on `matchQuery`. None is new.
  - **Codes:** Ruling: keep substring matching on codes. Codes use `raw`, because the old `code.toLowerCase().includes(needle)` found a digit run in the middle of a code.
  - **Palette** (`rankMatch`, `App.tsx`): keeps its own tiers for order. Exact and prefix stay literal string tests. Below those, `matchQuery` decides whether the label matches. Then it decides whether the group, hint or keywords do.
  - **Shortcut sheet** (`rowMatches`, `App.tsx`): moved onto `matchQuery`. The group title and the row's sentence are `text`. The key caps are `raw`. A digit-only cap (`1`) is found on its own. Rule 7's word-start rule would miss it.
  - **Capture's box picker** (`boxMatchesAll`, `CaptureScreen.tsx`): a box number matches as a plain substring, through `raw`. A box name matches as words, through `text`. Rule 5 excludes a box number from `matchQuery`'s `boxes` field on purpose. This screen's exception stays local and explicit.
  - **Graveyard:** moved onto `matchQuery`, over `text`, `numbers` and `skus`.
- Two literal checks survive. Neither is a typed query. `Revenue.tsx`'s `condition.includes('foil')` and `kit/data.tsx`'s finish-in-condition check each carry an inline comment saying so. `setHint.ts` and `pipeline/setnames.py` resolve a stored set hint against the catalog. That is a capture classifier. `server/capture_server.py`'s `_match_rank` and `_fts_query` are the server's decisive step and FTS5 candidate step. They are out of scope here. Every other search field (Inventory, Orders, Fulfillment, Cards to pull, Product history, Review's catalog lookup) calls `do_search`, or `matchQuery` through `useSearch`.
- **Enforcement (D173):** `app/eslint.config.js` bans `x.toLowerCase().includes(y)` under `src/`, with `no-restricted-syntax`. It is scoped away from `tests/`. Tests use that shape to assert a stored key, not a typed query. Proved red on Graveyard's old code, then green.

### Search is not the join

The matcher reuses the number rules the join has: `pipeline/join.py:number_index_key` and the store's own number helpers. It stays game-aware. Riftbound keeps its code verbatim. Pokemon composes the zero-padded number over the printed total. A fuzzy match such as `54` to `054` is fine in search. It must never feed the join. CLAUDE.md already says why: zero padding is composition only, never matching.

### What is built

- **Server:** `server/match.py` is a same-behaviour Python port of `app/src/kit/match.ts`. `scripts/match-selftest.py` proves the two agree over `app/src/kit/match.cases.json`.
- **`do_search`** (`server/capture_server.py:do_search`) calls `match.match_query` as the deciding vote for a candidate. `_fts_query`'s FTS5 candidate step and `_match_rank`'s ranking tier stay in their own right. See the two functions' docstrings for which case routes through which path.
- **Browser half:** the filtering lane's own entry (slug `one-matcher`).
- **Digit test:** `kit/match.ts`'s `\d` is always `[0-9]`, even under the `u` flag. The flag widens `\p{L}`, never `\d`. Python's bare `\d` and `str.isdigit()` are Unicode-aware. So `server/match.py`'s digit tests are ASCII-only on purpose: `_has_digit`, `_DIGITS_ONLY`, `_SKU_SHAPE`, `_HYPHEN_BETWEEN_DIGITS`, and the digit runs in `_drop_leading_zeros` and `_number_shape_ok`. This is the one place the file departs from Python's defaults.
- **Marks:** `server/match.py:fold_text` strips every Unicode Mark by category: `unicodedata.category(ch)[0] == "M"`, which covers Mn, Mc and Me. The stdlib is enough, so no `regex` package is needed. The old test read `unicodedata.combining(ch) != 0`, a canonical combining class. That class is zero for a spacing mark such as U+093E (Mc). The mark became a word break in Python, while the browser folded the same string to one word. `scripts/match-selftest.py`'s `case_match_fold_text_strips_every_mark_by_category` proves the two agree on every mark. It was red on the old code and green on the new.

### Mid-word search

**Ruling: add mid-word search.** Mid-word ships only if a measurement shows search stays fast. This ruling supersedes the FTS5 step's prefix-only trade-off on this one point. `do_search("izard")` finds "Charizard".

`server/capture_server.py:_fts_substring_candidates_for_term` is a fourth candidate source, one term at a time (R1). It folds the query term and each candidate field in Python (`match.fold_text`, `match.compact_text`). FTS5's prefix index cannot answer a substring. A substring scan cannot use an index. No B-tree ordering helps a leading `%`. Its cost grows with the store, not the term. It is folded in Python, so it cannot be a plain SQL `LIKE`.

**R1, round 5: the rank loop ran `_match_rank` once per repeated term, never deduped.** `("1 " * 100)` took 5.6 to 12.4s at 3,000 cards and 19.9s at 10,000. Fix: `_deduped_capped_terms`, shared by the rank loop and the widening step.

**F2, round 5: widening intersected across terms.** `izard ex` returned 20 rows before the intersection and 0 after. A fuzz dropped 64 of 300 two-term queries. Fix: a union, because the base FTS hits already carry the AND.

**A term of 1 or 2 characters never reaches the scan (R3).** `_fts_substring_candidates_for_term` floors at 3 characters. The floor is the owner's own condition. Before the floor, `q=a` measured a 582ms full-table scan.

**The floor's known cost (R5-4).** The 3-character floor applies to the candidate step only. It does not apply to `match_query`'s rule 7, which has no floor. A 1- or 2-character text token matches as a substring anywhere in a folded field. So `do_search` returns fewer rows than `match.match_query` accepts. For `sc` on the real store, `match_query` accepts 195 card records and `do_search` returns 56. That drops 139. The floor's cost was the owner's accepted condition when R3 shipped. It is restated here in a real number.

**A 9th or later distinct term is never widened.** `_SUPPLEMENTAL_TERM_CAP = 8` bounds how many distinct terms reach the widening step and the rank loop's `term_ranks`. A query with 9 or more distinct terms gets no widening for the 9th and beyond. Those terms still take part in the decisive `match.match_query` check, which is unbounded. A candidate that the first 8 terms surface is judged on all its terms. The gap is a row that needs the 9th term's own widening to become a candidate. No case and no permanent fuzz has needed that. The cap is sized against every shape measured so far. It is not sized against zero cost.

**Results are not capped (ceiling).** `do_search`'s response is unpaged. Every ranked SKU's full group and every copy return in one body. A broad query (`("e " * 100)`) matches about a third of a Pokemon-shaped store on `e` alone. It returns 719KB at 3,000 synthetic cards and 2.4MB at 10,000. Encoding and writing that body is most of what pushes real HTTP p95 over 500ms. That happens for `e`×100 and `ex`×66 at 3,000+ synthetic cards. The owner's real store (~3,510 cards) never reaches that cost. The ceiling is recorded at `server/capture_server.py`'s own `ponytail:` comment, where the body is built, and here. Upgrade path: page the response, with `limit`/`cursor` on `groups`. That needs its own decision. It is not built here.

**Mid-word ceiling.** At 3,000 synthetic cards, a real mid-word hit cost 73-76ms in-process (round-4 measurement). At 10,000 cards it costs up to 330ms over HTTP. That is over `useSearch.ts:SEARCH_DEBOUNCE_MS`'s 200ms budget. The round-4 stop condition was: if mid-word cannot stay under about 200ms for 3+ characters, stop and report. The condition is met at 10,000 cards. The store is nowhere near that scale. Round 4 ruled: ship as built. Round 5 ruled: add no result cap. The ceiling and its upgrade path are recorded at `_fts_substring_candidates_for_term`'s own `ponytail:` comment. The upgrade path is an FTS5 trigram index. That is a schema change and needs its own decision.

**Speed condition (in-process is the governing number).** The condition on mid-word and on R1's fix is speed on a real-sized store. Round 3 measured a synthetic 2,600-card store. Round 4 asked for 3,000 and 10,000 cards. Its fixture was `f"Bench Card {i}"`, which could not show R1's rank-loop bug or round 5's F2 intersection bug. Round 5 rebuilt the fixture with Pokemon-shaped names, suffixes (`ex`, `V`, `VMAX`, `VSTAR`), numbers, set names and a SKU prefix digit. It added a fourth column: a read-only copy of the owner's live store. The copy was made with `sqlite3 store.sqlite ".backup"`, which is WAL-safe. The original was never opened for writing, and the copy sat in a throwaway `BANCHI_HOME`. The columns are an in-process call and three HTTP loopback columns. Each HTTP column runs 20 requests per shape, JSON included, using the UX-263 method, against a running `CaptureServer`.

| Query shape | 3,000 in-process | 3,000 HTTP | 10,000 HTTP | real store HTTP |
|---|---|---|---|---|
| 1-char (`a`), floored | — | 5.8ms / 17.4ms | 9.0ms / 44.9ms | 117.8ms / 124.8ms |
| 2-char (`ab`), floored | — | 6.6ms / 9.4ms | 7.0ms / 8.5ms | 44.3ms / 47.5ms |
| 3-char mid-word (`izard`) | — | 162.0ms / 203.4ms | 266.6ms / 329.7ms | 29.9ms / 32.7ms |
| Hostile 100×`1` | 444ms | 444.4ms / 516.9ms | 577.9ms / 707.6ms | 294.7ms / 359.2ms |
| Hostile 100×`e` | 323ms | 474.9ms / 796.9ms | 1055.3ms / 2784.0ms | 148.5ms / 157.3ms |
| Hostile 66×`ex` | 227ms | 450.3ms / 601.8ms | 683.1ms / 807.1ms | 79.6ms / 98.7ms |
| Hostile 50×`001` | 136ms | 89.6ms / 133.9ms | 142.8ms / 149.9ms | 51.7ms / 55.4ms |
| Bare number (`132`) | — | 94.0ms / 115.5ms | 136.2ms / 145.9ms | 48.0ms / 51.7ms |

The real-store column met the condition at every shape measured. p95 tops out at 359ms. The mid-word row's own p95 is 33ms. An earlier claim said the HTTP columns' slower numbers came from payload size alone. That claim was false (R5-1, round 6). The rank loop spent real time on the decisive check, for every candidate a broad union could surface. The payload ceiling above still holds. It was never the whole explanation.

### Rounds 5-8: fixes and re-timing

Each fix below was red on the old code and green on the fix.

- **R5-1 (blocking): the rank loop ran the matcher before the decisive check.** `do_search` computed `term_ranks` (up to 8 `_match_rank` calls) for every candidate. It did this before `match.match_query` decided whether the candidate matched. The union (F2, round 5) lets a query of several `/NNN` terms make most of the store a candidate. `/132 /298 /166 /198 /219 /221 /1 /2` measured 552-578ms on the real store, for a 63-byte body. Fixed: `match_query` runs first. `term_ranks` is computed only for a matched row or a single-term query.
- **R5-2 (real store): the zero-pad widening never matched a composed number.** `_fts_zero_pad_candidates_for_term` compared `LTRIM(col, '0') = ?` against the whole column. 2,919 of the owner's 3,510 real cards keep `number` as `027/166`, with an empty `number_key`. `LTRIM` strips only the front, giving `27/166`, which never equals a bare `27`. `q=0027` dropped 3 of 4 real matches, `0217` 5 of 5, and `0190` 3 of 3. Fixed: also match `LTRIM(col, '0') LIKE bare || '/%'`.
- **R5-3: the widening dedupe was case-sensitive.** `ex`, `EX`, `Ex` and `eX` counted as 4 terms. They used 4 of `_SUPPLEMENTAL_TERM_CAP`'s 8 slots. `ex EX Ex eX ob OB fl FL izard` returned 0 of 15 real matches. The cap filled before `izard`, the one real match, was scanned. Fixed: dedupe on the folded form.
- **R5-5: the zero-pad widening refused digit-plus-letter numbers.** It gated on digits only, so `24a` dropped all 8 real matches for `024a/219` (Rengar). Fixed: `_ZERO_PAD_SHAPE` (digits, then 0-2 letters) replaces the digits-only gate.
- **F6-1: letter-prefixed numbers never widened.** `_ZERO_PAD_SHAPE` admitted only digit-leading terms. `match.canonical_number` drops zeros after leading letters, so `tg05` is `tg5`. The real store has 41 cards numbered `R01a`-`R06a`. `r1a` and `r4a` missed 2 of 2. `tg5`, `swsh22` and `swsh45` missed too. Fixed by reusing `match._drop_leading_zeros` and `match._number_shape_ok` (0-6 leading letters, 1+ digits, 0-2 trailing letters). SQL `LTRIM` cannot express a letter-aware strip, so this runs in Python.
- **F6-2: a 2-character number term now widens.** `6a` inherited the 3-character text floor, which is not about numbers. `match._number_shape_ok` plus a 2-character floor replaces it. Round 8 found it still open. `6a` missed "Order Rune (R06a)", and `1a`-`6a` missed 40 real cards combined. The borrowed floor was the gate on the substring rule. Fixed: a digit-bearing 2-character term also reaches the substring rule. This matches `_is_floor_query`'s definition of "not a floor term".
- **F6-3 (blocking): four widenings meant four scans per term.** Eight distinct 3+ letter mid-word terms took 450-536ms p50, up to 860ms p95. Each of the four widening sources ran its own `SELECT ... FROM cards` per term, up to 32 scans per query. Fixed: `_fts_supplemental_candidates` reads each card's row once. It checks every term's every widening rule against that row. The same 8-term query now costs 77.8ms p50 and 87.3ms p95. Reverting to four SQL sources measured 261.6ms p50 on the same query. The owner ruled the four-scan cost not accepted.
- **F6-4: the fixture was too easy.** `_build_pokemon_store` carried each real-store defect on one named card. Fixed: six seeded number shapes (`random.Random(7)`). They are composed `NNN/MMM` numbers with an empty `number_key`, digit-plus-letter numbers, three letter-prefixed forms (`RNNa`, `TGNN`, `SWSHNNN`), and cards with no `printed_total`. The permanent fuzz gained a second generator, `_generate_card_sampled_queries`. It builds queries from a randomly chosen card's own fields, as the reviewer's `fz.py:gen_queries` does. M2 and M4 now turn the fuzz red.
- **F6-5: the R5-1 timing row could not see its subject.** Every card had the same `printed_total`. `_SET_TOTALS` holds six values that match real Pokemon printed totals. A `/166`, `/198`, `/219` or `/221` term is now a broad candidate on about 1/6 of the store. Reverting R5-1 (`if True:` in place of `if matched or token_count == 1:`) now fails on this fixture.
- **F6-6: timing cried wolf at load average 16.** The timing-only cases went red on a busy CI runner, with no code change. The same query measured 264.0ms p50 and 353.4ms p95 while `make harness` ran. It measured 77.8ms and 87.3ms once the machine was quiet. Wall time answers "how busy is the machine", not "how much work did this query do". Fixed: `_SEARCH_WORK_COUNTERS` (`match_rank_calls`, `match_query_calls`, `rows_walked`) resets before each query and is read after. `rows_walked` proves F6-3's fix. It is 0, or exactly the store's card count, never a multiple. `match_rank_calls` proves R5-1's fix. It measured 11,416 calls under the reverted fix and 0 on the same query fixed. Wall time stays as a generous 5-second backstop.
- **F6-7: a SKU count is not a card count.** R5-4's disclosure first said `sc` drops "33 cards", meaning SKUs. Round 7 switched to `on_hand` cards. That still disagreed with `match_query`'s count across every state. Round 8 counted card records in every state, as above. The unit is card records throughout this entry.

**Re-timed on a fresh real-store copy, R6-fixed code:**

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

Every shape stayed under 235ms p95. That is inside the 500ms bound from the round-6 review. R5-1's `/NNN` shape dropped from 552-578ms to 128.7-134.8ms.

**Real mid-word fragments.** The earlier `izard` cell measured zero hits, because `izard` never appears mid-word in the owner's card names. These fragments do appear in them:

| Mid-word fragment | p50 / p95 | body |
|---|---|---|
| `engar` | 82.4ms / 92.6ms | 43KB |
| `ion` | 97.2ms / 100.9ms | 93KB |
| `ard` | 96.6ms / 103.5ms | 91KB |
| `ing` | 117.5ms / 123.3ms | 198KB |
| `ter` | 114.8ms / 120.8ms | 183KB |

**Re-timed on a fresh real-store copy, R7-fixed code, machine quiet:**

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

Every shape stayed under 240ms p95 on a quiet machine. The R7 hostile 8-term mid-word row is F6-3's subject. It was 450-536ms p50 before the fix. It is now the fastest hostile shape measured.

**Mutations M1-M4, on the final head, each red then restored.** M1 reverts R5-1: 3 cases fail. M2 reverts R5-2: 5 cases fail, including the fuzz. M3 reverts R5-3: 2 cases fail. M4 reverts F6-1: 2 cases fail, including the fuzz.

### Round 8: exact shapes and the two-character path

Round 8 found four blocking items and three disclosures. Timing was already inside bound, and the wolf-crying was gone. The seeded fuzz found 0 false positives in 7,000 queries.

1. **F6-2 was still open on the real copy.** See F6-2 above.
2. **`rows_walked` could not see another function's scans.** The counter lived in `_fts_supplemental_candidates`'s loop. Restoring the round-6 architecture (four SQL sources) stayed green at `rows_walked=0`. Fixed: `conn.set_trace_callback(_count_cards_scan)` on the connection counts a `cards` scan, whichever function issues it. Restoring the round-6 architecture now reads 16 (four sources times up to 8 terms).
3. **`match_rank_calls` was counted at the call site.** A caller could move the rank loop before `match_query` (M5) and leave the counter's increment behind. Fixed: the counter is the first line inside `_match_rank` itself.
4. **`match_query_calls` was never asserted.** It is bounded at 2x the store's card count in the hostile timing case. The legitimate shapes measured reach 1,427 calls at most.
5. **Composed-number misses (replaced; the round-8 "neither reproduced" claim was false).** The round-8 builder tested neighbours of the reported inputs, such as `0024a` and a bare `4`. It did not test the exact shapes. On a fresh real-store copy, every sampled query of four shapes missed. Bare-letter composed (`24a/219` for `024a/219`): 11 of 11. Extra-zero letter composed (`0024a/219`): 11 of 11. Extra-zero plain composed (`0027/166` for `027/166`): 300 of 300. Zero-padded digit word in name text (`004`, "spent 4"): 1 of 1.
   **F1, round 9, closes all four in number normalization.** The widening gate, `match._number_shape_ok(term)`, checked one side of a number only. A term with `/` failed it outright. So no composed term reached any number widening. `match._number_match`, the decisive step, already split on `/` through `match.canonical_number`. `_number_candidate_forms` now computes the same canonical forms, so widening and the decisive step agree. The digit-word shape: a pure-digit term reached the zero-pad widening, which checked only the number columns. `_text_digit_word_matches` fixes it. It mirrors `match._digit_word_match` against `name`, `set_hint` and `note`. Re-verified on a fresh copy. 0 of 52 bare-letter composed queries missed. 0 of 52 extra-zero letter composed queries missed. 0 of 300 extra-zero plain composed queries missed.
   **52 counts card records, not distinct queries.** Round 10 counted 22 distinct numbers. Several boxes hold more than one copy of one printing. So a sweep built per card queries a number twice. Item 6 sets the unit to card records. The case row is `case_do_search_number_widening_mirrors_canonical_number`. It replaces round 8's `case_do_search_known_gap_hash_prefixed_composed_letter_number`. The `#`-prefixed composed shape closes as a side effect.
6. **One unit throughout: card records, never SKUs.** See F6-7 above.
7. **The fold-prefix rule is deleted, not guarded (M10).** Its "strict superset" claim was false. A differential over the real store found one disagreement. `bf` found "B.F. Sword" (`161/221`) through a rule that stripped all punctuation before comparing. `bf` finds nothing without that rule. `bf` is a 2-character term with no digit, inside the accepted 1-2 character text floor. The behaviour stays as it is. See ruling 2 below.

**Re-timed on a fresh real-store copy, R8-fixed code:**

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

Every shape stays under 240ms p95. The `6a` row went from a 30-byte empty body in round 7 to a 6KB result. Timing did not change measurably.

**Mutations on the final head, each red then restored.** M1 (decisive check before the rank loop, reached by reordering rather than `if True:`) fails 4 cases. M5 is the same reorder. The call-site counter would have missed it. The counter inside `_match_rank` does not. M2 fails 5, including the fuzz. M3 fails 2. M4 fails 3, including the fuzz. M8 (the 2-character digit-bearing substring floor, F6-2) fails 2. M10 (the fold-prefix rule) is deleted, so nothing is left to mutate. M6, M7, M9, M11 and M12 are not defined in this entry. This entry does not guess at them.

### Round 9

- **F1** closes the four shapes (round 8, item 5).
- **F2 (round 9): `rows_walked` could not see a second connection.** The trace covers one connection, `do_search`'s own. A per-term scan on a second, untraced `db.connect(...)` stayed green at `rows_walked=0`. The round-8 suite never forced the widening branch, so `in (0, 1)` passed on a query that never widens. Fixed: the docstring states what the trace sees, one connection and not "any code anywhere". The case `case_do_search_rows_walked_is_exactly_one_when_widening_is_needed` names a query that must widen. It asserts `rows_walked == 1`. A disconnected trace, or a scan on an untraced second connection, reads 0 and fails.
- **F3: each counter needed a non-zero floor.** Every case set only an upper bound. Zero satisfies any upper bound, so deleting either increment stayed green. Added: `match_rank_calls >= 1` and `match_query_calls >= 1`, each on a single-term query that matches a real card.
- **F5: `_SEARCH_WORK_COUNTERS` is unlocked module state.** `REQUEST_SLOTS` threads share the dict. Production never reads it, so no user sees an effect. A concurrent test could read another request's counts. The dict's definition says so. Tests read it single-threaded, one `do_search` call per `_reset_search_work_counters()`.

**Mutations, round 9, each red then restored, against the 192-case table:** F1's fix (`_is_number_shape` back to `_number_shape_ok`) fails 2. The composed-number prefix check removed (equality only) fails 6. `conn.set_trace_callback` removed (F2) fails 1. A second untraced `db.connect(...)` added for the row walk fails 1. The `match_rank_calls` increment removed (F3) fails 1. The `match_query_calls` increment removed (F3) fails 1. M1 (R5-1) fails 4. M3 (R5-3) fails 1. M8 (F6-2) fails 2.

### Round 10

- **N1: the tokenizer, not the comparison.** F1 fixed `_number_candidate_forms`'s comparison. It did not touch what fed a term into it. `_deduped_capped_terms` split on bare whitespace (`text.split()`). `match.query_tokens`, the one tokenizer `match_query` uses, also turns a comma into a space. It strips edge punctuation per token. So `rengar,24a/219` is one whitespace token but two real tokens: `rengar` and `24a/219`. `/166,` strips to `/166`. On a real-store copy, `rengar,24a/219` and `repel,126/132` missed 60 of 60 sampled. `/221,` missed 60 of 60. `/166,` missed all 193 real matches. `004,`, `(004)`, `004.` and `unseen,rengar` missed too. Fixed: `_deduped_capped_terms` and the rank loop's `token_count` tokenize through `match.query_tokens`. The widening candidates union with the base FTS hits before the decisive `match.match_query` check. Verified: name-plus-comma-plus-composed-number 52 of 52, 0 missed. Trailing-comma second-half slash 60 of 60, 0 missed, and 8 of 8 on every distinct second half. Case: `case_do_search_comma_and_edge_punctuation_terms_widen`. The permanent fuzz gained comma-joined and edge-punctuation shapes.
- **N2: the hyphen fold was unguarded.** `_number_candidate_forms` folds a hyphen that stands for the collector-number slash (`match._hyphen_to_slash(bare)`). No case exercised it. Removing it kept all 192 round-9 cases green, and `0027-166` then missed Hand Hammer (`027/166`). Case: `case_do_search_hyphen_fold_finds_a_composed_number`.
- **N3 (known gap, not fixed):** `002-64` also matches `264` through `compact_text` in the shared matcher, in `match.py` and `match.ts`. `compact_text` strips every non-alphanumeric character before it compares. That is on purpose, for names like "B.F. Sword". A collector number gets no exemption. Round 11 overturned this gap (ruling 1).
- **N4 (known gap, not fixed):** `_is_floor_query` measured the raw token. So `B.F`, with its period, sat outside the 1-2 character floor, while `bf` sat inside it. Round 11 closed it (ruling 2).

**Mutations, round 10, each red then restored, against the 195-case table:** `_deduped_capped_terms` back to `text.split()` (N1) fails 3. The hyphen-fold term removed from `_number_candidate_forms`'s `forms` set (N2) fails 1.

### Round 11

**Ruling 1 (owner): a hyphen splits the number.** `002-64` must not match 264. A hyphen between two digits stands for the collector-number slash. So `bare`, read whole, must not also be a candidate. `canonical_number` does not split on `-`. The whole-string form therefore joined the digit runs the hyphen kept apart. `002-64` canonicalized whole was `264`. The plain form applies only when no such hyphen exists. The fix covers three places: `server/match.py:_number_match`, `app/src/kit/match.ts:numberMatch`, and `server/capture_server.py:_number_candidate_forms`, the widening step's mirror. `0027-166` still finds Hand Hammer through the hyphen-to-slash composed reading. Two rows land in the shared table `app/src/kit/match.cases.json`. `scripts/match-selftest.py` and `app/tests/match.spec.ts` both read it. The case `case_do_search_hyphen_splits_the_number_never_joins_it` asserts `do_search` end to end. It also asserts `match.match_query` directly. The direct assertion catches a change to `match.py` alone. `do_search`'s filtering would otherwise hide that change.

**Ruling 2: letters that spell a dotted name match it again.** `bf` and `B.F` both find B.F. Sword. `_is_floor_query` (`scripts/match-selftest.py`) measured the raw token. `B.F` keeps its internal period, because `query_tokens` strips only edge punctuation. So `B.F` counted as 3 characters, outside the floor, while `bf` counted as 2, inside it. The fix measures `match.compact_text(token)`, the fold the decisive matcher's substring fallback (rule 7) compares on. Case `case_is_floor_query_classifies_by_the_fold` is a direct unit check. The permanent fuzz never carries a query this distinction changes.

The product half: `B.F` (3 characters) already cleared the substring widening. It found the card once `_deduped_capped_terms` tokenized correctly (round 10). Only bare `bf` needed a fix. `bf` cannot be told apart from an ordinary short word such as `ex` by the term alone. Reopening the widening row walk for every 2-letter term would reopen the R3 floor. So `_fts_letter_pair_alternative` (`server/capture_server.py`) is a second FTS5 clause. It is ORed with the term's prefix match inside `_fts_query`. It is an indexed intersection of two single-letter prefixes, `"b"* AND "f"*`. Its cost does not grow with how common the term is. It is offered for every bare 2-letter alpha term. The decisive `match.match_query` is unchanged. It still needs its compact-fold fallback before it accepts a row. A false candidate is filtered out at no cost.

- Case `case_do_search_dotted_initials_are_brought_back` supersedes round 9's `case_do_search_fold_deletion_narrowed_bf_to_the_accepted_floor`. That case asserted the overturned "does not find" verdict.
- Case `case_do_search_two_character_timing_stays_under_500ms_p95` measures `bf`, `ex`, `hi`, `on`, `gx`, `sc`, `fl`, `ob`, `ad` and `un`, 30 samples, on a 3,000-card store. `rows_walked` stays 0. An indexed lookup makes the cost independent of machine load. On an idle machine, p95 sat well under the owner's 500ms ceiling. The case's wall-time check is a generous 2.0s backstop. That follows F6-6: assert on work done, not wall time. It has the same shape as the 5.0s backstop in `case_do_search_hostile_repeated_terms_stay_fast_on_real_names`. Inside `make check`, the same 30 queries once measured over 1s on a busy machine.

**Mutations, round 11, each red then restored:** removing the `match.py:_number_match` hyphen-split fix (ruling 1) fails 1 case, the direct `match.match_query` assertion. Removing the `match.ts:numberMatch` fix reproduces the bug. The check built the file with esbuild and ran it directly, and `264/300` matched `002-64`. Unwiring `_fts_letter_pair_alternative` from `_fts_term_alternatives` (ruling 2) fails 1 case. Reverting `_is_floor_query` to raw token length fails 2 cases. `server/capture_server.py:_number_candidate_forms`'s copy of ruling 1 cannot be proved through `do_search`. The decisive `match.match_query` is fixed and unmutated, and it rejects the wrong candidate whatever the widening offers. A mutation there changes candidate volume, never the answer. The `match.py` mutation and the direct case prove the rule.

Seeded fuzz after every fix: 0 false positives over 640 queries (`_FUZZ_QUERIES` plus 200 card-sampled).

**Doc fixes.**

- L1: the round-10 sentence "`_fts_query` was checked and needs no change" holds only outside the accepted floor. In `un,9197044`, the number term widens the row. `un` is an ordinary plain substring of `"unseen"`, so it passes the decisive check without any widening. The floor excuses a term like `un` from needing a candidate rule of its own.
- L2: `Dr.`, `Lt.` and `Mr.` alone fold to 2-character terms with no digit (`dr`, `lt`, `mr`). So `_is_floor_query` reads them as floor terms too. This is disclosed, not fixed. These are abbreviated words, not two initials, and the mechanism cannot tell them apart from the term alone. `unicode61` splits `Dr.` into `dr` at index time. An actual `Dr. Something` card is found through the ordinary index either way. The disclosure concerns the test's excuse covering more ground than true dotted-initial pairs. It is never a missed card.
- L3: N4's cause is the period inside the token. `query_tokens` never strips an internal character. The compact-fold classification from ruling 2 makes the two spellings agree.

### Round 12: inventory pass

Lane `ux/pr4-search` checked the open gaps. The gaps were: `#` forms, composed forms with a letter or an extra zero, a digit word in name text, and N4. Each one was verified against the code and a run.

- The `#` and composed shapes, and the digit word in name text, were closed by F1 (round 9), through `_number_candidate_forms` and `_text_digit_word_matches`. `case_do_search_number_widening_mirrors_canonical_number` covers `24a/219`, `#24a`, `0027/166` and the digit word `004` in "spent 4". It passes.
- N4 was closed by ruling 2 (round 11). `case_is_floor_query_classifies_by_the_fold` and `case_do_search_dotted_initials_are_brought_back` both pass.
- `#24a` finds SKU `8802`. The round-9 case covers it through the "Rengar, Unseen (hash)" row, so no new case is needed.

`RULINGS.md` is a dated review record. It stays as evidence, not as a live status page. `make match-selftest` passes 241 of 241 cases, both matchers. T7 (`harness/tests/t7_store_and_seams.py`) passes inside `make harness`. Neither matcher changed. No gap was left with a clear right answer.

### Typos and a near match

**FLT-05 (typos and a near match): CLOSED by ruling. Suggest was chosen.** The choice was among an edit-distance threshold, a "did you mean" surface, and rows versus a suggestion. The "one matcher, both sides" rule did not settle it.

With zero results, `EmptyState`'s `didYouMean` shows "Did you mean <name>?" as a tap target. That tap runs the search. The ranking and results are untouched. The server (`match.did_you_mean`, in `do_search`'s answer) and the browser (`kit/match.ts:didYouMean`) share `kit/didyoumean.cases.json`. A query under five characters, or under a 0.7 ratio, gets no hint. Matching the typo into the ranking stays unbuilt.

Accents are settled by an orchestrator call, not an owner ruling. The matcher folds them, because the "forgiving" ruling covers them. The owner can reverse that call.
