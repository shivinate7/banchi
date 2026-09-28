## 27 — `Fulfillment.tsx`'s store-wide `GET /inventory` browse is argued and left

**Site 1 of this debt is closed. Its record is retired, on the owner's ruling, 2026-09-27**
(the preamble's own argument: "an entry leaves when someone argues it should"). Site 1 was
`Orders.tsx:indexStore`'s `GET /inventory` call. `POST /inventory/copies` closed it (D192,
PR #341). The measurements and the closure record live in git history, at commit b61ffa32.
This entry now holds only the open half, site 2. Confirmed still live on this tree,
2026-09-27: `Fulfillment.tsx` still calls `getInventory()`. The comment above that call still
names this debt by number.

**Site 2 — `Fulfillment.tsx`'s whole-store sellable browse — is unchanged and is argued rather
than patched.** (D5/D6's "no order in hand" fallback) lists every sellable card across every
box. There may be no order to name a box from, and no SKU set to ask about, at all. There is
no set of boxes and no set of SKUs to scope the fetch to. The whole point of this view is that
neither is known before the fetch runs. `POST /inventory/copies` cannot answer it. That
route takes a SKU set as its whole input, and this screen has none to give it. A column
projection and paginated place decoration are named as future work. Neither is built under
this item.

**Not mechanically enforced, and named as such.** The `unscoped walk` guard (item 1) watches
`server/*.py` and `store/master.py` for a full-table walk server-side. `Fulfillment.tsx`'s
`getInventory()` call is client-side — a `fetch` in `app/src` — and that guard's own scope
does not reach it. Nothing currently fails a commit that leaves it as it is.

Cites D192 and D88. Neither is reopened by this entry.
