# Server

Capture server: POST /capture, /status, GET /photo/<box>/<position>, GET and PUT inventory state, DELETE /inventory/<box>/<index> — undo — and `7b`'s three: GET /queues, POST /review/<box>/<index>/answer, POST /inventory/<box>/<index>/sold.

## Code files

- `server/capture_server.py` — The capture, status, photo, inventory, queue, review-answer, mark-sold, undo, search, box and order routes — including D34's listing release and the free plan that must be drawn before it, D37's stand-down in both directions, D20's box name as an address (`name_taken`, and a number allocated rather than typed).
- `server/codes_routes.py` — The code-card track's seam: GET /codes (the ledger, its two lanes and its duplicates), POST /codes/scan (decode a box's photographs — FREE, no model call anywhere on this track) and POST /codes/export (preview a channel export, or COMMIT one to an order, reserving every code it returns).
- `server/match.py` — The one forgiving matcher (FLT-`06`/`04`, UX-`173`), ported from `app/src/kit/match.ts` — NFKC/NFKD accent folding, canonical collector-number comparison (zero padding and a hyphen standing for the slash), SKU-prefix and box-name matching, stdlib only (`unicodedata` stands in for the `regex` package's `\p{L}`/`\p{N}` classes, which `requirements.txt`'s own "Deliberately absent" section is why nothing new was added).
- `server/order_transport.py` — The order transport (D69): this account's own orders off order-management-api.tcgplayer.com, cookie-authenticated with the same TCGPLAYER_STORE_COOKIE the export uses — one .tcgplayer.com session, two hosts.
- `server/pipeline_routes.py` — The pipeline seam: POST /pipeline/preflight (free, creates no run), POST /pipeline/identify (THE ONE THAT SPENDS — spawns a detached child and returns the run name), GET /pipeline/runs and /pipeline/runs/<name> (read the run directory, and hold no ANSWER about a run.
- `server/portal_http.py` — The transport both TCGplayer hosts share: the session cookie read, the User-Agent, its one door to the retry home (`pipeline/net.py`, no redirect followed) and the one status ladder.
- `server/ports.py` — Which ports THIS checkout serves on, derived from where the checkout is.
- `server/refusal.py` — `BadRequest`, the refusal every route module can raise, and `require_box`, the one parser for a box number in a request body.
- `server/send_routes.py` — THE ONE PRESS that sends listings to TCGplayer and makes them live, and the checks around it.
- `server/shipping_routes.py` — The shipping seam (D69's second route): POST /shipping/batches reads TCGplayer's Orders -> Export Shipping CSV into D61's three lanes and renders a Pirate Ship import file for the parcel lane, GET .../file?name= hands those bytes to the browser, and DELETE .../<batch> drops the batch now rather than in half an hour.
- `server/slabs_routes.py` — The My Slabs routes: POST /slabs adds a slab by cert (Card Ladder reads `3.1`, `3.2` and `3.4` outside the store lock, then ONE write of the slab, today's snapshot and the sales), GET /slabs lists every slab with its newest snapshot, GET /slabs/<grader>/<cert> reads one, DELETE on that path removes the slab and its sale links (no Card Ladder call, refused while an add runs).
- `server/tcg_export.py` — The outbound calls to the seller admin host, and the only place allowed to make them — one of TWO such modules since D69 gave server/order_transport.py the order host.
- `server/tcg_import.py` — THE OUTBOUND WRITE to the seller admin, and the only place in this repo that can change a price a buyer sees (D273).
- `server/tcgtracking.py` — THE ONE CLIENT OF TCGTracking (D326): create(body) buys a label, track(order_number=|tracking_number=) reads scan status, pdf(order_id) re-renders a label as bytes.
