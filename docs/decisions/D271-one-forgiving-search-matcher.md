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

**A known, unfixed gap.** `kit/match.ts:foldText` deletes every Unicode Mark character
outright (`\p{M}`), whatever its canonical combining class. `server/match.py:fold_text` only
strips a mark with a NON-ZERO combining class — a real combining accent
(`unicodedata.combining(ch) != 0`). A "ccc-0" mark has combining class zero, a SPACING mark
such as a Devanagari vowel sign. That test does not remove it. A Mark character is never
`str.isalnum()`, so it folds into a WORD BREAK on the Python side instead of vanishing. The
browser would have kept the word joined. No case in the shared table has ever needed a ccc-0
mark folded. Not chased: `unicodedata` alone cannot express `\p{M}`. The `regex` package
would, and `requirements.txt` deliberately does not carry it. Fixing this is a dependency
decision, not a bug fix.
