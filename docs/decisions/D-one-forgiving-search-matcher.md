## D-one-forgiving-search-matcher — Every search field uses one forgiving matcher, on the server and in the browser

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

Accents are settled. The orchestrator ruled that the matcher folds them, because the
"forgiving" ruling covers them. The owner can reverse that call.

### Search is not the join

The matcher reuses the number rules the join already has: `pipeline/join.py:number_index_key`
and the store's own number helpers. It stays game-aware. Riftbound keeps its code verbatim, and
Pokemon composes the zero-padded number over the printed total. A fuzzy match such as `54` to
`054` is fine in search. It must never feed the join. CLAUDE.md already says why: zero padding is
composition only, never matching.

### What is built

NOT BUILT. In the round-two plan, the filtering lane writes the one case table and the browser
matcher. The search-server lane makes the server pass the same table. The server half touches
`server/capture_server.py`, so a reviewer must see it. The filtering lane's plan also names an
entry for the matcher (slug `one-matcher`). One of the two must go before either merges.
