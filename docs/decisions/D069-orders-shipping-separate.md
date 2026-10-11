## D69 — Orders and Shipping are separate routes

`#/orders` answers *which copies does this buyer get, and where in the boxes are they*, from D63's ledger. `#/shipping` answers *which envelope does this order go in*, from TCGplayer's `Orders → Export Shipping` file. These are two routes, not one screen with two modes. `app/src/App.tsx` carries NINE routes: eight are the owner's and one is the Fulfiller's. The build-order plan is discharged: the screens exist, so the transport had somewhere to arrive.

### Two routes, because they are two questions at two moments

**Their inputs do not touch.** The order screen reads `inventory/orders.json` and `inventory/inventory.json` through one store snapshot. The shipping screen reads a CSV the operator uploads. That CSV carries no line items. `pipeline/shipping.py:Shipment` says so in its docstring, and the ledger has never seen it. Neither can be derived from the other. One screen would have to explain why half of it went stale when the other half refreshed.

**The build-order plan named this collision and gave two options:**

```
If the lane badge and the download draw on the order screen, two branches revise one file, which this repo has already paid for twice. Sequence them, or give the lane its own surface.
```

The lane got its own surface. That is the second option.

**The order screen draws NO postage lane. This is a prohibition, not a missing feature.** There is no `ships_in_an_envelope` field on the wire, and no lane span in the markup. Adding one would put a second answer to D61's question on a screen without D61's inputs, computed from data that cannot answer it. D61 rules on the lanes, the abstention, the weight, the insurance and the PII. This entry reopens none of it.

**The cost:** two routes means two nav links, two chords, and one more line in every count of screens. Those counts are often wrong here. The recount for this entry was taken by reading the `ROUTES` table. It was not taken by adding one to the last number anyone wrote down.

### The paste is projected in the browser. The server's allowlist is the backstop

**`app/src/orderPaste.ts` is the ONE place in this app that decides what leaves the browser about a purchase.** It names what it drops rather than dropping it silently. The projection was `{source, number, placed_at, status, lines[]}`, with no buyer, address, city, postcode or payment. **AMENDED (`D193`): the projection is `{source, number, placed_at, status, buyer, lines[]}`.** `buyer` is a display name, and nothing else was added. Address, city, postcode and payment are dropped as before. The dropped list drawn on screen before the send no longer names `buyer`. D193 argues why a name is not the PII this boundary keeps out.

**`server/capture_server.py`'s three allowlist tuples are a backstop, not the boundary.** An unprojected paste refuses by name: `field_not_settable`, naming the excluded field it carried (`buyerName`, `shippingAddress`, `email`, and so on). It is not stored with the extra fields trimmed quietly. Trimming is worse where it matters. A silent trim makes a broken projection look the same as a working one, forever. **`buyer` left this refusal list** when D193 landed. The mechanism is unchanged for everything still on it.

**One door.** `app/src/server.ts:ingestOrders` accepts the projection as its argument and does not project. A second module composing an ingest body would be a second door onto the same wire, and the guarantee would be gone.

### The pull is body-addressed, one card at a time, and its undo lives on the receipt

**Body-addressed, because an order key is `source:number`, and a NUMBER may legally contain a colon.** `store/orders.py` splits on the FIRST colon for that reason. A key in a path segment would need an escaping rule that the one place composing the key does not have. Getting it wrong records a pull against the wrong order.

**One card, one press, no batch control.** The route accepts a list because `record_pull` accepts a sequence, and validate-all-then-write-all is the same code either way. The route does not take a list because a screen should offer multi-select. Nothing in this product picks two cards at once. D39's ruling that there is exactly ONE mass-select in the product is not reopened.

**The undo is the screen receipt alone, never a row control.** A successful pull re-resolves the order, so the pick row it came from unmounts. A control on that row would vanish at the moment it became useful. The receipt survives the re-render. It is where D28's undo window lives on every other screen.

**The receipt reads `places[i]`, never `sales[i].card.place.label`.** The places come back as they were before the write. A sale moves the box's occupancy (D58). Once the answer is composed, the card is departed, and its own label reads `Box 3 · departed`. That is a true sentence and a useless receipt.

### `GET /orders` answers from one snapshot, and `sku_unknown` draws a zero on purpose

**The list and the resolution come from one `Store().read()`.** Two reads could straddle a sale and show a card both on hand and gone. **Only `Ledger.unfulfilled()` orders are resolved.** That is the ledger's own question, computed from its two maps. It is never the feed's `status` string, which `store/orders.py` stores verbatim and unvalidated. A marketplace that learns a new word is not refused at the door.

**`resolve_all` runs with NO paperwork. The cost is named, not hidden.** The run-side backup would come from `cli/resolve.py:paperwork_for`. That takes ONE run, and `realign` HASHES EVERY PHOTOGRAPH OFF DISK and raises on an ambiguous digest. One bad run would take the whole screen down. `cli/runs.py` has no list function to walk the others with. So the resolution is card-first. `sku_unknown`, which fires only when a run's paperwork names a SKU no card wears, is structurally UNREACHABLE from this route. It always draws a zero. **That zero is a limit of the route, not a fact about the store.** It is reported rather than filtered out, because "nothing was short" and "nothing was checked" must not look the same in the payload.

### The transport was measured, and three places in this tree said the wrong thing

**Captured from the owner's logged-in browser.** Request shapes were read from an in-page interceptor. Response schemas were walked with the values discarded. A third-party bridge extension the owner supplied corroborated them. No credential value was read, logged or echoed.

**The order host is a cookie session, not a Bearer challenge.** `order-management-api.tcgplayer.com` authenticates with `credentials: 'include'` and the `TCGAuthTicket_Production` cookie. That is the `.tcgplayer.com` cookie `server/tcg_export.py:_cookie()` already names, so one account session serves both hosts. No `www-authenticate` header appeared on any probed path. The portal's own XHR sets no `Authorization` header. The bridge extension authenticates by cookie alone.

**This repo recorded the opposite in three places and repeated it in a fourth.** They are `server/tcg_export.py`'s docstring, D65's probe table, the build-order plan's exclusion paragraph, and `docs/specs/order-pipeline.md`'s T0. All four are amended in place, not deleted. Sound reasoning that reached a wrong conclusion is worth finding again. D65 treated its own price-history correction the same way.

**What does NOT transfer between the hosts is the body convention, not the auth.** The admin host takes Knockout's `postJson` form: `model=<json>`, form-urlencoded, D65's shape. The order host takes a plain JSON document. A client carrying D65's form here fails, and the failure reads like an auth problem.

**Two calls, because the search result has no SKU and only the order detail does.** `POST /orders/search` returns order numbers. `GET /orders/<number>` returns `products[].skuId`, which is the export's `TCGplayer Id`, which is `store/master.py:Card.sku`. There is no bulk line-item call. Every response is projected to an allowlist inside `server/order_transport.py`. `shippingAddress`, `paymentType` and the transaction breakdown are dropped where they are parsed, and no function there returns them. `buyerName` was on that dropped list until D193 moved it into the projection as `buyer`, a display name only. It is the one field of the four this paragraph named that now survives.

**A 403 is `order_seller_key_rejected`, not an expired session.** `filters.sellerKey` is required. Its absence answers 403, not 400. A client that reads 403 as "log in again" sends the operator to re-authenticate over a body bug. The key is the lowercased prefix of every order number this account has. It identifies the account and is not secret, so it belongs in `.env` as `BANCHI_TCG_SELLER_KEY`, not in a constant.

**Verified after this entry was written.** The operator ran `order_transport.search(page_size=3)` against the live host and got three real orders back. So the stored `TCGPLAYER_STORE_COOKIE` authenticates it, and one credential serves both hosts. An agent may not read `.env`, so the operator ran it. **`detail` and `fetch_open_orders` are still unexercised against the live host.** They are the half that carries a buyer's name and address. The PII projection is proven against fixtures only.

### What this does not decide

**Not the lanes, the abstention or the PII rule:** D61. **Not the ledger's two maps or the sync's one-map write:** D63. **Not whether a browser extension is ever the transport.** That cost is recorded and not spent here. What landed is stdlib `urllib` in one module naming one host. **Not the two write endpoints seen on the wire and deliberately not built,** `POST /orders/status-updates` and `POST /orders/<number>/tracking`. They are steps 13 and 14, and they are someone else's decision.

### What would reopen this

**A shipping export that starts carrying line items.** That would make the lane derivable from the ledger, and the two-surface argument would weaken. **Or a first authenticated fetch that fails.** That would mean the domain-wide cookie does not serve both hosts. The transport would then need its own credential. `.env` would grow a second name, and this entry's second transport paragraph is the one to amend.

---
