## 27 — `Fulfillment.tsx`'s store-wide `GET /inventory` browse is argued and left

`Fulfillment.tsx` still calls `getInventory()` for its "no order in hand" fallback (D5, D6), which lists every sellable card across every box. There is no set of boxes or SKUs to scope the fetch to, and `POST /inventory/copies` (D192) takes a SKU set as its whole input. A column projection and paginated place decoration are named and not built. The `unscoped walk` guard watches `server/*.py` and `store/master.py`. A client `fetch` in `app/src` is outside it, so nothing fails a commit that leaves this as it is. Site 1, `Orders.tsx:indexStore`, closed with D192.

**Outcome at risk.** The fallback view loads the whole store on a large inventory.

**Closes when.** A projection or a paginated read the fallback can use, measured on the owner's store.
