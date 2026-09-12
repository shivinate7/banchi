## D66 — The order screen comes before the transport, and the shipping lane needs neither

**Recorded 2026-08-30, and nothing here is built.** `docs/specs/order-pipeline.md` is the plan that produced it — steps 8 to 14, order in to tracking back — landed out of a planning session whose findings were living in a chat transcript. This entry settles the ORDER the remaining work is done in, because a five-session sequence had already been written down and two of its dependencies do not exist.

**Three modules have full T7 coverage and no reachability whatsoever**: `pipeline/orders.py`, `pipeline/shipping.py` and `pipeline/pirateship.py`, covered by `check_order_resolver` and `check_shipping_lane`, with no route, no client function in `app/src/server.ts`, no subcommand and no screen. `store/orders.py` is the fourth module of the order flow and is the exception — see below. `make harness` and `make check` are green over every one of them. That is `CLAUDE.md`'s route-is-not-a-feature rule and this repo's own recorded failure, at four modules at once.

### The screen is built before the transport, and the reason is the Done criterion

**A transport-first session cannot state a Done this repo accepts.** The version this reverses read *"an order from the live account lands in `inventory/orders.json`; ingest writes no card state; a replay is a no-op"* — three true and testable sentences, all of them server-side. Every one is satisfied by an ingest route no human can reach, which is the exact shape the paragraph above indicts. It carried a paste door as its first deliverable, and a paste door is a control: it needs a screen, so that session either ships the unreachable half or silently contains the screen session.

**The screen first is a complete product with no network in it.** `resolve_all` returns picks, `pipeline/join.py:Position` labels them, and `store/orders.py` already holds `record_pull`, `forget_pull` and `holder_of` — so a screen fed by pasted JSON pulls a real order end to end. The transport is then a better source behind a control that exists, which is a smaller change than a route looking for a home.

**`store/orders.py` is the half-wired one, and that is what makes this cheap.** `store/session.py` carries `Ledger` in `Snapshot` and writes it last on every store write. The ledger is loaded and persisted already; it has simply never had an order put in it.

### The shipping lane is not downstream of either, and the dependency graph said it was

**`pipeline/shipping.py` reads the Export Shipping CSV, which carries no line items at all.** Its `Shipment` says so in its own docstring, `to_parcel`'s `stamps` argument **defaults to empty** and its docstring states that nothing there knows where a card sits, and `fixtures/orders-shipping.csv` is committed at 331 real orders. So the parcel lane is reachable from an uploaded file with no order feed and no resolver, and the resolver's only contribution is the location in `Rubber Stamp` — optional by construction rather than by omission.

**The limit, stated so this is not read as a license to parallelize.** The engine dependency is zero and the surface dependency is not: if the lane badge and the download draw on the order screen, two branches revise one file, which this repo has already paid for twice. Sequence them, or give the lane its own surface.

### One exclusion is struck, because D64 shipped the thing it excluded

**"Python bearing the session cookie" was ruled out and is now running.** The exclusion's reason — the extension reduces the cookie to a yes-or-no answer and never exposes its value — was an argument about the extension, and it was carried to a conclusion it does not reach: the owner can place the cookie themselves, which is what `server/tcg_export.py` reads out of `.env`. The row stays visible in the spec rather than being deleted, because sound reasoning arriving at a wrong conclusion is worth being able to find again.

**What survives is one probe, not a session.** The admin host answers a cookie-session 302 and `order-management-api` answers a Bearer challenge; two hosts, two schemes, and D64's result does not transfer. That question is answered by one request, and the spec puts it in the free work rather than letting a build be organised around it.

**Amended 2026-08-30 (D69): the probe ran, and answered cookie rather than Bearer.** `order-management-api.tcgplayer.com` authenticates with `credentials: 'include'` and the same `TCGAuthTicket_Production` cookie the admin host uses — one `.tcgplayer.com` session, two hosts — so *two hosts, two schemes* is one scheme, and D64's result DOES transfer as far as auth is concerned. The paragraph is amended rather than removed because its structural claim was right: one request settled it, and organising a build around the answer would have been organising it around a guess. What does not transfer is the body convention — form-urlencoded `model=<json>` there, plain JSON here. The capture, the two calls, the required `sellerKey` and the 403 that reads like an expired session are all in D69.

### The relay, if it is built, is work this repo cannot verify

**There is no extension in this tree.** The requirements set on it — an exact derived origin, an action allowlist inside the extension, its own rate limit, since `onMessage` has none — are changes to a codebase `make check` never sees, `docs/map.py` does not map and the git hooks do not guard, in a project whose verification argument rests on those three. Not a reason to reject it; a reason the session that takes it states the cost up front instead of finding it halfway through.

### What this does not decide

**Not the resolver, the ledger or the lanes** — D63 and D61 settled those and this entry re-opens neither. **Not whether the relay is the right transport**, which the probe decides. **And not the eleven rulings the planning session took**: they are recorded in the spec with their original letters, two of them already overtaken by built code, and this entry deliberately does not restate them.

### What would reopen this

**A screen that turns out to need the feed to be built at all** — the claim here is that pasted JSON is a sufficient input, and it is untested until somebody pastes one. **Or the probe answering Bearer**, which does not change the order but does change what the transport session is. *(It did not: the probe ran 2026-08-30 and answered cookie — see the amendment above and D69.)*

---
