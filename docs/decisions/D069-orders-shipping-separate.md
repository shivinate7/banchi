## D69 — Orders and Shipping are separate routes

**Built 2026-08-30.** `#/orders` answers *which copies does this buyer get, and where in the boxes are they*, out of D63's ledger. `#/shipping` answers *which envelope does this order go in*, out of TCGplayer's own `Orders → Export Shipping` file. Two routes, not one screen with two modes. `app/src/App.tsx` now carries NINE routes. Eight are the owner's and one is the Fulfiller's. The build-order plan is discharged: the screens exist, so the transport had somewhere to arrive.

### Two routes, because they are two questions asked at two moments

**Their inputs do not touch.** The order screen reads `inventory/orders.json` and `inventory/inventory.json` through one store snapshot. The shipping screen reads a CSV the operator uploads. That CSV carries no line items at all. `pipeline/shipping.py:Shipment` says so in its own docstring, and the ledger has never seen it. Neither can be derived from the other. A screen that drew both would have to explain to the operator why half of it went stale when the other half was refreshed.

**The build-order plan named the collision this avoids and offered exactly these two options.** *"If the lane badge and the download draw on the order screen, two branches revise one file, which this repo has already paid for twice. Sequence them, or give the lane its own surface."* The lane got its own surface. That is the second option taken, not a new argument.

**The order screen therefore draws NO postage lane, and this is a prohibition rather than an omission to fill in later.** There is no `ships_in_an_envelope` field on the wire. There is no lane span in the markup. Adding one would not be an enhancement. It would put a second answer to D61's question on a screen with none of D61's inputs, computed from data that cannot answer it. D61 rules on the lanes, the abstention, the weight, the insurance and the PII. This entry reopens none of it.

**The cost, named.** Two routes is two nav links, two chords, and one more line in every count of screens this repo publishes. This repo's own record is that those counts are wrong more often than they are right. The recount that goes with this entry was taken from the `ROUTES` table by reading it. It was not taken by adding one to the last number anybody wrote down.

### The paste is projected in the browser, and the server's allowlist is the backstop

**`app/src/orderPaste.ts` is the ONE place in this app that decides what leaves the browser about a purchase**. It NAMES what it dropped rather than dropping it silently. The projection was `{source, number, placed_at, status, lines[]}` and nothing else. It had no buyer, no address, no city, no postcode, no payment. **AMENDED 2026-09-13 (`D193`): the projection is now `{source, number, placed_at, status, buyer, lines[]}` — a display name, and nothing else added.** Address, city, postcode and payment are dropped exactly as before. The dropped list drawn on screen before the send now says so, with `buyer` no longer on it. That entry argues why a name is not the PII this boundary exists to keep out.

**`server/capture_server.py`'s three allowlist tuples are a BACKSTOP AND NOT THE BOUNDARY.** An unprojected paste refuses BY NAME — `field_not_settable`, naming whichever excluded field it carried (`buyerName`, `shippingAddress`, `email`, …) — rather than being stored with the extra fields quietly trimmed. Trimming was the alternative, and it is worse in the only case that matters. A silent trim makes a broken projection indistinguishable from a working one, forever. The first person to notice would be whoever read the store. **`buyer` moved off this refusal list on 2026-09-13**. The mechanism — refuse by name rather than trim — is unchanged for everything still on it.

**One door.** `app/src/server.ts:ingestOrders` accepts the projection as its argument and does not project. A second module composing an ingest body would be a second door onto the same wire, and the guarantee would be gone.

### The pull is body-addressed, one card at a time, and its undo lives on the receipt

**Body-addressed because an order key is `source:number` and a NUMBER may legally contain a colon.** `store/orders.py` splits on the FIRST one for exactly that reason. A key in a path segment would need an escaping rule that the one place the key is composed does not have. The failure mode of getting it wrong is a pull recorded against the wrong order.

**One card, one press, and there is no batch control.** The route accepts a LIST because `record_pull` accepts a sequence, and validate-all-then-write-all is the same code either way. It does not take a list because a screen should offer a multi-select. Nothing in this product picks two cards at once. D39's ruling that there is exactly ONE mass-select in the product is not reopened here.

**The undo is the screen receipt alone and never a row control.** A successful pull re-resolves the order, so the pick row it was pressed from unmounts. A control living on that row would vanish at the moment it became useful. The receipt is what survives the re-render, and it is where D28's undo window already lives on every other screen.

**The receipt reads `places[i]`, never `sales[i].card.place.label`.** The places come back AS THEY WERE BEFORE THE WRITE. A sale moves the box's occupancy (D58). So by the time the answer is composed, the card is departed, and its own label reads `Box 3 · departed`. That is a true sentence and a useless receipt.

### `GET /orders` answers from one snapshot, and `sku_unknown` draws a zero on purpose

**The list and the resolution come out of one `Store().read()`.** Two reads could straddle a sale. They could show a card both on hand and gone. **Only `Ledger.unfulfilled()` orders are resolved.** That is the ledger's own question, computed from its own two maps. It is never the feed's `status` string, which `store/orders.py` stores verbatim and unvalidated. That way, a marketplace which learns a new word is not refused at the door.

**`resolve_all` is called with NO paperwork, and the cost is named rather than hidden.** The run-side backup would come from `cli/resolve.py:paperwork_for`. That takes ONE run, and `realign` HASHES EVERY PHOTOGRAPH OFF DISK and raises on an ambiguous digest. One bad run would take the whole screen down, and `cli/runs.py` has no list function to walk the others with. So the resolution is card-first. `sku_unknown`, the reason that fires only when a run's paperwork names a SKU no card wears, is structurally UNREACHABLE from this route. It always draws a zero. **That zero is a limit of the route and not a fact about the store.** It is reported rather than filtered out, because "nothing was short" and "nothing was checked" must not be the same payload.

### THE TRANSPORT WAS MEASURED, AND THREE PLACES IN THIS TREE SAID THE WRONG THING

**Captured 2026-08-30 off the owner's own logged-in browser**, request shapes were read off an in-page interceptor, and response SCHEMAS were walked with the values discarded. A third-party bridge extension the owner supplied corroborated them. No credential value was read, logged or echoed.

**The order host is a COOKIE SESSION and NOT a Bearer challenge.** `order-management-api.tcgplayer.com` authenticates with `credentials: 'include'` and the `TCGAuthTicket_Production` cookie. That is the same `.tcgplayer.com` cookie `server/tcg_export.py:_cookie()` already names, so ONE account session serves both hosts. No `www-authenticate` header appeared on any path probed. The portal's own XHR sets no `Authorization` header, and the bridge extension authenticates purely by cookie.

**This repo recorded the opposite in three places and repeated it in a fourth**. They are `server/tcg_export.py`'s docstring, D65's probe table, the build-order plan's exclusion paragraph, and `docs/specs/order-pipeline.md`'s T0. All four are amended in place rather than deleted. The reason is that sound reasoning that reached a wrong conclusion is worth finding again. That is the same treatment D65 gave its own price-history correction.

**What genuinely does NOT transfer between the two hosts is the BODY CONVENTION, not the auth.** The admin host needs Knockout's `postJson` form: `model=<json>`, form-urlencoded, which is D65's shape. The order host takes a PLAIN JSON document. A client carrying D65's form here fails, and it fails in a way that reads like an auth problem.

**Two calls, because the search result carries no SKU and only the order detail does.** `POST /orders/search` returns order numbers. `GET /orders/<number>` returns `products[].skuId`, which is the export's `TCGplayer Id`, which is `store/master.py:Card.sku`. There is no bulk line-item call. Every response is PROJECTED to an allowlist inside `server/order_transport.py`. `shippingAddress`, `paymentType` and the transaction breakdown are dropped where they are parsed, and are returned by no function there. **`buyerName` was on that dropped list until 2026-09-13.** `D193` moved it into the projection as `buyer`, a display name only. It is the one field of the four this paragraph named that now survives.

**A 403 is `order_seller_key_rejected` and is NOT an expired session.** `filters.sellerKey` is required, and its absence answers 403 rather than 400. So a client that reads 403 as "log in again" sends the operator to re-authenticate over a body bug. The key is the lowercased prefix of every order number this account has. It is account-identifying rather than secret, so it belongs in `.env` as `BANCHI_TCG_SELLER_KEY`, and not in a constant.

**Verified 2026-08-30, after this entry was written**: the operator ran `order_transport.search(page_size=3)` against the live host and got three real orders back. So the stored `TCGPLAYER_STORE_COOKIE` does authenticate it, and one credential serves both hosts. An agent may not read `.env` here, so the run was the operator's. **`detail` and `fetch_open_orders` are still unexercised against the live host.** They are the half that carries a buyer's name and address. The PII projection is proven against fixtures only.

### What this does not decide

**Not the lanes, the abstention or the PII rule** — D61. **Not the ledger's two maps or the sync's one-map write** — D63. **Not whether a browser extension is ever the transport** — that cost is recorded and is not spent here. What landed is stdlib `urllib` in one module naming one host. **And not the two write endpoints seen on the wire and deliberately not built**, `POST /orders/status-updates` and `POST /orders/<number>/tracking`. They are steps 13 and 14, and they are somebody else's decision.

### What would reopen this

**A shipping export that starts carrying line items**, which would make the lane derivable from the ledger. The two-surface argument would be weaker. **Or a first authenticated fetch that fails**, which would mean the domain-wide cookie does not in fact serve both hosts. The transport would then need its own credential. In that case `.env` grows a second name, and this section's second paragraph is the one to amend.

---
