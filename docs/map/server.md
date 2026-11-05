# Server

Capture server: POST /capture, /status, GET /photo/<box>/<position>, GET and PUT inventory state, DELETE /inventory/<box>/<index> — undo — and `7b`'s three: GET /queues, POST /review/<box>/<index>/answer, POST /inventory/<box>/<index>/sold.

## Code files

- `server/capture_server.py` — The capture, status, photo, inventory, queue, review-answer, mark-sold, undo, search, box and order routes — including D34's listing release and the free plan that must be drawn before it, D37's stand-down in both directions, D20's box name as an address (`name_taken`, and a number allocated rather than typed).
  - Decisions: `D65`, `D16`, `D273`, `D61`, `D320`, `D63`, `D69`, `D77`, `D138`, `D43`, `D108`, `D10`, `D6`, `D5`, `D13`, `D172`, `D37`, `D100`, `D252`, `D83`, `D34`, `D264`, `D89`, `D86`, `D145`, `D278`, `D277`, `D227`, `D76`, `D103`, `D326`, `D28`, `D4`, `D26`, `D33`, `D29`, `D20`, `D299`, `D193`, `D91`, `D58`, `D203`, `D191`, `D3`, `D134`, `D7`, `D260`, `D294`, `D259`, `D132`, `D21`, `D23`, `D213`, `D301`, `D70`, `D196`, `D92`, `D183`, `D262`, `D56`, `D174`, `D88`, `D121`, `D164`, `D137`, `D12`, `D22`, `D147`, `D36`, `D115`, `D87`, `D212`, `D67`, `D93`, `D271`, `D113`, `D192`, `D219`, `D189`, `D225`, `D104`, `D168`, `D261`, `D1`, `D8`, `D9`, `D11`, `D24`, `D41`, `D45`, `D54`, `D55`, `D90`, `D97`, `D109`, `D166`, `D231`, `D251`, `D258`, `D298`
- `server/codes_routes.py` — The code-card track's seam: GET /codes (the ledger, its two lanes and its duplicates), POST /codes/scan (decode a box's photographs — FREE, no model call anywhere on this track) and POST /codes/export (preview a channel export, or COMMIT one to an order, reserving every code it returns).
  - Decisions: `D14`, `D24`, `D33`, `D70`
- `server/match.py` — The one forgiving matcher (FLT-`06`/`04`, UX-`173`), ported from `app/src/kit/match.ts` — NFKC/NFKD accent folding, canonical collector-number comparison (zero padding and a hyphen standing for the slash), SKU-prefix and box-name matching, stdlib only (`unicodedata` stands in for the `regex` package's `\p{L}`/`\p{N}` classes, which `requirements.txt`'s own "Deliberately absent" section is why nothing new was added).
  - Decisions: `D271`, `D166`, `D213`
- `server/order_transport.py` — The order transport (D69): this account's own orders off order-management-api.tcgplayer.com, cookie-authenticated with the same TCGPLAYER_STORE_COOKIE the export uses — one .tcgplayer.com session, two hosts.
  - Decisions: `D91`, `D65`, `D34`, `D138`, `D63`, `D69`, `D193`
- `server/pipeline_routes.py` — The pipeline seam: POST /pipeline/preflight (free, creates no run), POST /pipeline/identify (THE ONE THAT SPENDS — spawns a detached child and returns the run name), GET /pipeline/runs and /pipeline/runs/<name> (read the run directory, and hold no ANSWER about a run.
  - Decisions: `D32`, `D301`, `D156`, `D166`, `D65`, `D76`, `D145`, `D174`, `D125`, `D21`, `D188`, `D54`, `D58`, `D104`, `D86`, `D277`, `D36`, `D273`, `D59`, `D7`, `D9`, `D147`, `D87`, `D134`, `D189`, `D16`, `D103`, `D100`, `D22`, `D8`, `D254`, `D219`, `D19`, `D1`, `D2`, `D3`, `D12`, `D13`, `D20`, `D24`, `D25`, `D29`, `D33`, `D35`, `D43`, `D47`, `D56`, `D67`, `D68`, `D88`, `D89`, `D105`, `D137`, `D163`, `D168`, `D170`, `D172`, `D180`, `D196`, `D212`, `D216`, `D225`, `D227`, `D236`, `D258`, `D262`, `D278`, `D291`, `D293`
- `server/portal_http.py` — The transport both TCGplayer hosts share: the session cookie read, the User-Agent, its one door to the retry home (`pipeline/net.py`, no redirect followed) and the one status ladder.
  - Decisions: `D65`, `D69`, `D319`
- `server/ports.py` — Which ports THIS checkout serves on, derived from where the checkout is.
  - Decisions: `D261`, `D13`, `D43`
- `server/refusal.py` — `BadRequest`, the refusal every route module can raise, and `require_box`, the one parser for a box number in a request body.
  - Decisions: `D20`
- `server/send_routes.py` — THE ONE PRESS that sends listings to TCGplayer and makes them live, and the checks around it.
  - Decisions: `D273`, `D100`, `D269`, `D7`, `D59`, `D26`, `D33`, `D54`, `D86`, `D87`, `D99`, `D104`, `D105`, `D174`
- `server/shipping_routes.py` — The shipping seam (D69's second route): POST /shipping/batches reads TCGplayer's Orders -> Export Shipping CSV into D61's three lanes and renders a Pirate Ship import file for the parcel lane, GET .../file?name= hands those bytes to the browser, and DELETE .../<batch> drops the batch now rather than in half an hour.
  - Decisions: `D326`, `D58`, `D33`, `D61`, `D63`, `D69`, `D88`
- `server/slabs_routes.py` — The My Slabs routes: POST /slabs adds a slab by cert (Card Ladder reads `3.1`, `3.2` and `3.4` outside the store lock, then ONE write of the slab, today's snapshot and the sales), GET /slabs lists every slab with its newest snapshot, GET /slabs/<grader>/<cert> reads one, DELETE on that path removes the slab and its sale links (no Card Ladder call, refused while an add runs).
  - Decisions: `D320`, `D88`, `D196`, `D319`
- `server/tcg_export.py` — The outbound calls to the seller admin host, and the only place allowed to make them — one of TWO such modules since D69 gave server/order_transport.py the order host.
  - Decisions: `D65`, `D138`, `D76`, `D3`, `D87`, `D8`, `D9`, `D11`, `D16`, `D24`, `D33`, `D69`, `D104`, `D319`
- `server/tcg_import.py` — THE OUTBOUND WRITE to the seller admin, and the only place in this repo that can change a price a buyer sees (D273).
  - Decisions: `D319`, `D100`, `D13`, `D16`, `D65`, `D87`, `D103`, `D104`, `D273`
- `server/tcgtracking.py` — THE ONE CLIENT OF TCGTracking (D326): create(body) buys a label, track(order_number=|tracking_number=) reads scan status, pdf(order_id) re-renders a label as bytes.
  - Decisions: `D326`, `D319`, `D65`
