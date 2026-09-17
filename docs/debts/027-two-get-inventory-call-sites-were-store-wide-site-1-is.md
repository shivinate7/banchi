## 27 — Two `GET /inventory` call sites were store-wide; site 1 is closed, site 2 is argued and left

**D192 (store-scaling item 2, PR #341) closed most of `getInventory()`'s callers and
named these two rather than patching around them.** `#/inventory` and Home's hero deck moved to
`GET /inventory/<box>` and `GET /inventory/recent`; `Fulfillment.tsx`'s whole-store sellable
browse and `Orders.tsx`'s `indexStore` (the per-line copy-map widening) did not, and this is
that debt's own record — referenced from both code comments by number rather than argued twice.

**SITE 1 IS CLOSED.** `Orders.tsx:indexStore` no longer calls `getInventory()` at all.
`POST /inventory/copies` (`server/capture_server.py:do_inventory_copies`) answers exactly the
question that call was standing in for — every on-hand copy of a requested SKU set, store-wide
— from one unfiltered `_cards_by_sku`-shaped scan whose derived box set (never a guessed one)
is handed to `_Places.for_keys`. This is the "lean on-hand copies by SKU, store-wide" route
this entry named as the candidate primitive two paragraphs below, before it was built.

**Measured, on `docs/specs/store-scaling.md` §1's own method (five runs, median, base and
20x), on a SYNTHETIC store built to the real store's own shape** rather than a `.backup` of the
owner's actual inventory — this branch worked in an isolated agent worktree with no access to
the main checkout's real store, and that substitution is recorded here rather than silently
presented as the owner's own numbers. 2,535 cards over 5 boxes, 300 distinct SKUs, 20 of them
asked about (a realistic count of SKUs an operator's open orders would actually name at once):

| call | base (2,535 cards) | 20x (50,700 cards, boxes 1-100) | ratio |
|---|---|---|---|
| `GET /inventory` (old site 1, `Inventory.to_payload()`) | 130.5 ms | 2,684.3 ms | 20.6x |
| `POST /inventory/copies` (new, `do_inventory_copies`) | 12.2 ms | 219.8 ms | 18.0x |
| speedup (old / new) | **10.7x** | **12.2x** | |

**And the wire, which is the half the operator's own browser pays for**: the base store's whole
`GET /inventory` answer is 2,914,751 bytes over 2,535 cards; the same store's
`POST /inventory/copies` over the 20 asked-about SKUs is 114,521 bytes over 112 on-hand copies
— **25x smaller**. These numbers are close to `docs/specs/store-scaling.md` §1's own
`Inventory.to_payload()` row (78 ms / 1,485 ms on the owner's real 2,535-card store, 19.0x) —
the synthetic store's base 130.5 ms sits in the same order of magnitude, and the gap is
plausibly this store's larger average `sku`/place-decoration load per card rather than a
methodology difference.

**THE COST DID NOT DISAPPEAR — IT MOVED, AND THAT IS SAID IN THE SAME BREATH AS THE FIX.** The
scan inside `do_inventory_copies` is still a full, unfiltered pass over `inventory.cards` —
genuinely store-wide, by the same argument that made scoping it to "the boxes an order's
resolver picks name" unsound (see the next paragraph, unchanged). `scripts/docs-audit.py`'s
`unscoped walk` guard (item 1) pins this: `UNSCOPED_WALK_EXPECTED` moved **9 -> 10**, the first
time that pin has ever moved up, with `do_inventory_copies` named on its own allowlist line and
the reason argued there rather than silently absorbed. What is smaller is not the scan — it is
the WIRE: the client no longer downloads and decorates every card in the store, only the ones a
requested SKU actually has on hand.

**SITE 2 — `Fulfillment.tsx`'s browse — IS UNCHANGED AND IS ARGUED RATHER THAN PATCHED.**
(D5/D6's "no order in hand" fallback) lists every sellable card across every box, precisely
because there may be no order to name a box from — or a SKU set to ask about — at all. There is
no set of boxes and no set of SKUs to scope the fetch to; the whole point of this view is that
neither is known before the fetch runs. `POST /inventory/copies` cannot answer it: that route
takes a SKU set as its whole input and this screen has none to give it. This entry's own
conclusion (§27, unchanged) is to leave site 2 as the store-wide `GET /inventory` read it always
was, named here again rather than quietly closed by a route that does not fit its question.
A column projection and paginated place decoration are named as future work for site 2 and are
NOT built under this item.

**Why site 2 (and the resolver's own picks, for site 1) could not be box-scoped instead — the
argument that made the box-scoped shape the idea to avoid rather than the one to build:**

- **`Fulfillment.tsx`'s browse** lists every sellable card across every box, precisely because
  there may be no order to name a box from at all. There is no set of boxes to scope the fetch
  to — the whole point of this view is that none is known.
- **`Orders.tsx`'s `indexStore`** widens each order line's copy map to "every on-hand copy of
  that SKU the store holds, including copies in far boxes no resolver pick names" (`copiesOf`'s
  own comment in that file). Scoping the fetch to "the boxes an order's resolver picks name"
  would silently hide copies of the same SKU sitting in boxes no pick ever mentions — the
  resolver only returns as many picks as needed to fill demand, so a box holding three spare
  copies of a card that already has enough elsewhere would never be named at all. That is a
  correctness regression (fewer copies drawn than exist), not merely a slower screen, which is
  why D192's own decision entry (D192) declined to patch around it, and why
  `do_inventory_copies` derives its box set from an unscoped SCAN rather than from a guess —
  the fix moves the SCOPING QUESTION off "which boxes" onto "which SKUs", which the screen
  genuinely has in hand, rather than trying to answer the box question more cleverly.

**Not mechanically enforced for site 2, and named as such.** The `unscoped walk` guard (item 1)
watches `server/*.py` and `store/master.py` for a full-table walk server-side; `Fulfillment.tsx`'s
`getInventory()` call is client-side — a `fetch` in `app/src`, which that guard's own scope does
not reach. Nothing currently fails a commit that leaves it as it is.

**D192 and D88 are not reopened by this closure.** This paragraph is site 1's own record of
what changed; neither decision's ruling is amended, and no new decision number was claimed for
it — the closure is exactly the shape D192 already argued for and named as future work.
