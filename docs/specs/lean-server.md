# Lean server: stock images outside Review

**Status: PROPOSAL. No option is built.** Options (a) to (e) have no code, route or setting. The owner decides which option, if any, to build. Section 2 describes what exists: `image_url` on `GET /pipeline/sets` and `GET /pipeline/pricing`, and stock-first photos on Pricing, Sets and the Orders walk.

Governed by D301 (stock photos are hotlinked, never mirrored), D89 (a sold card's photo is reclaimed on purpose), D36 (the store decides a card's slot), D43 (each checkout gets its own port), D88 (SQLite is the store of record), D316 (a Capture button starts and stops the dispenser) and D42 (main moves by pull request).

## 1. The idea

The owner wants the server to take less of the Mac. The plan: the photos the rig takes stop being what every screen shows. Stock images (the hotlinked art from the catalog) draw every photo view once a card is verified. The real photograph is a backup, and Review is the only screen that shows it. At the far end, the server itself moves to the cloud and the Mac keeps only the camera and the dispenser.

## 2. Current state

### Where a real photograph lives

- **Write.** `server/capture_server.py:do_capture` calls `store/photos.py:write`. The file is `photos/<2 hex>/<cid>.jpg`, outside `captures/` and gitignored (D172, a card is filed by its name; D183, photos are filed by name). Photos are outside the SQLite transaction (`docs/specs/capture-server.md`, rule 3).
- **Size.** About 1.8 MB each (D89). The corpus is 4.45 GB (`cli/cmd_cards.py`, the `cards photos` header). In this checkout no `photos/` or `captures/` directory exists, so the measure is 0 bytes. The owner's Mac figure is **unmeasured**.
- **Serve.** `GET /photo/<box>/<index>` (`do_photo`) reads the file and hashes it for an ETag: about 0.6 ms read plus 0.15 ms hash (its docstring). `GET /photo/by-card/<cid>?v=<capture_id>` (`do_photo_by_card_ex`) answers a repeat view with a 304 and no file read. `?crop=card` runs the card finder (`identify/images.py:preview_cut`). One finder runs at a time (`_finder_lock`), and a busy finder answers the whole frame. The crop cache is 48 MB (`PREVIEW_CACHE_BYTES`).
- **Lane.** `/photo/` and `/assets/` use `PHOTO_SLOTS = 4`, a pool apart from `REQUEST_SLOTS = 4` (DEBT11, a parked writer holds a request slot). The sweep measured 53 req/s at one slot against 12 unbounded. Photo p50 rose from 5 ms to 136 ms under six looping `/orders` readers.
- **Reclaim.** `POST /boxes/<box>/photos/reclaim` deletes only sold cards' photos and keeps the digest (D89). No other photo is ever deleted.

### Where stock images come from

- `pipeline/stockimages.py:StockImages` resolves `(game, set_name, number)` to a hotlinked CDN URL or `None`. Pokemon reads `vendor/pokemon-tcg-data/` (26 MB here, no network). Riftbound and One Piece read tcgcsv. The URL rides as `image_url` on `GET /pipeline/sets` and `GET /pipeline/pricing`. The browser loads the bytes from the CDN. The Mac serves no stock byte (D301).
- One exception: the free reader fetches each stock image once, takes a 768-number fingerprint and drops the bytes (`cli/cmd_match.py`, `banchi match prepare`).
- `make catalog-mirror` fills a local copy of the hires art, about 16.7 GB (`scripts/catalog-image-mirror.py`). It is a harness input (D15), not a serving path.

### Which screens show which photo today

Counts are references to `photoUrl` or `previewUrl` in `app/src/*.tsx`.

| Screen | Real photo | Stock image |
|---|---|---|
| Review (`ReviewQueue`, `ReviewBandSheet`, `RunsComposer`) | yes (5, 2, 3) | no |
| Capture (`CaptureScreen`) | yes (4), the Recent rail | no |
| Inventory (`Inventory`, `CardHero`, `CardLocations`, `BoxBrowse`) | yes, cropped previews (2, 3, 2, 4) | Sets view only (`InventorySets`); one variant thumbnail in `BoxBrowse` |
| Home (`Home`) | yes (2) | no |
| Pricing (`Pricing`) | yes (4) | yes (6), the main view |
| Product (`ProductHistory`) | none | none |
| Orders walk (`OrdersWalkPane`) | fallback only | first choice (`image_url ?? photoUrl`) |
| Revenue (`Revenue`) | when a copy is on hand | fallback (`stockPhotos[sku]`) |
| Fulfillment (`Fulfillment`) | yes (6): the pull photo (`previewUrl`) and a full view | no |
| Codes (`Codes`) | yes | no |

So the stock-first change is already built for Pricing, Sets and the Orders walk. The screens left are Inventory, Card hero, Box browse, Home and Fulfillment.

### Where the server load is

This comes from code and the records. Nothing here is a new measurement.

- **Photo bytes: cheap.** About 0.75 ms per full-frame request, and a 304 skips the read. The lane exists to keep this path fast (DEBT11).
- **Crop: the one named photo hot spot.** `preview_cut` runs the card finder on a cache miss. It is GIL-bound and runs one at a time. Cost per run: unmeasured.
- **Free reader sweep.** `identify/sweep.py` reads every `captured` photo with the marqo model in a worker process. It reads real photos from disk and takes no request slot. Capture p99 measured 30.5 ms with it on and 30.6 ms with it off. Idle memory is the watcher only (stdlib and sqlite3). Worker CPU and memory: unmeasured.
- **Heavy reads.** `/pipeline/waiting`, `/boxes`, `/search` and `/capture/sitting` are fixed (section 6, Q7). DEBT11 names `/orders`, `/inventory`, `/boxes`, `/search`, `/pricing`, `/graveyard` and `/pipeline/*` as the GIL-bound reads that wait behind parked writers. A stock image does not change these. They return rows, not photos.
- **Writes.** One SQLite transaction per capture: 2.4 to 2.9 ms from 1,560 to 50,000 cards (D88).
- **Client request budget.** Reads in flight are capped at 4, and polls at one per 3 s (`app/tests/request-budget.spec.ts`, `docs/specs/efficiency.md`).

**Finding.** The photo path is already the cheapest part of the server. Stock images in place of real photos save disk and the finder, and little else. The Mac's load comes mostly from the heavy GIL-bound reads, the sweep and the finder. Section 5 measures this before any build.

## 3. Options, smallest to largest

### (a) Stock image first on every non-Review screen; real photo kept and one press away

- **Changes.** Inventory, Card hero, Box browse, Home and Fulfillment draw `image_url` first. They fall back to `photoUrl` when a card has no stock image. Each gets a "my photo" press that loads the real one. The server adds `image_url` to `/inventory` rows, or the app reads it from the Sets path. No storage change.
- **Gain.** No more `crop=card` requests on those screens, so no finder runs there. Fewer `/photo/` hits. A sold card's crop never loads. Mac load: unmeasured, expected small (section 2).
- **Cost.** Stock art can be the wrong printing, condition or language. It cannot confirm a physical slot (D38, a photo is sized to confirm a slot). It cannot show wear. A printing with no stock image still needs the real photo. A CDN outage blanks the screen unless the real photo is the fallback.
- **Decisions touched.** D38: its premise is that the owner's photo confirms where the card is. Stock art cannot. D6 (one photo route serves every view): premise "the pull modal shows the card's own capture photo". D301 stays true, since stock stays hotlinked. D125 (photos crop to card): the crop moves to Review and press-through only.
- **What a person sees.** Inventory and Home show catalog art with the card's own label. Fulfillment's pull photo is the risk (section 6, Q2). Review and Capture are unchanged.

### (b) Real photos leave the server's hot path: a separate photo store or cold storage

- **Changes.** `store/photos.py` stays the one home, and gains a backend with two places. Hot is local disk for the newest and unreviewed cards. Cold is object storage or an external disk. Verified cards' photos upload to cold on a schedule. Review reads hot, then cold. D89 reclaim keeps its meaning for sold cards.
- **Gain.** Disk: up to 4.45 GB now, about 176 GB at 100,000 cards (D89's arithmetic), minus reclaim. CPU: none by itself. Pairs with (a).
- **Cost.** A new moving part: upload, retry, a cold-read delay in Review, an account and a bill. The ETag and 304 path (`do_photo_by_card_ex`) needs a cold-read branch.
- **Decisions touched.** D89: premise "the retained set is about 9 GB". Cold storage makes keeping every photo cheap, so reclaim could stop. D36 (the store decides a slot): its `photo_sha256` binding needs the bytes, so a re-bind on cold photos reads from the cloud. D172 stays, because the cid is still the key.
- **What a person sees.** The same as (a). Review is slower on a card whose photo went cold, unless a prefetch runs for the queue.

### (c) Split: cloud API plus a thin local capture agent

- **Changes.** The Mac runs only a capture agent: camera frames, the dispenser link (D316) and an upload queue. The cloud runs the API, the store (SQLite or a hosted DB), pipeline routes, TCGplayer export handling, the sweep and the photo store. The front end talks to the cloud.
- **Gain.** The Mac sheds the server, the store, the sweep and the finder. What stays: the browser tab, the camera and the Bluetooth link. Mac load drops most here. Measured: no.
- **Cost.** Auth and TLS (section 4). A hosted bill. A second deploy path. Capture must work with the network down, so the agent needs a local spool and a rule for a card whose upload has not landed. Latency per capture rises from about 30 ms (local p99) to a network round trip.
- **Decisions touched.** D138 (one process serves the product): premise "one process". D43 (each checkout gets its own port and store) and D13 (one truth on the Mac, as D43 states it): premise "the truth lives in the Mac's main checkout". D88: premise "one file, one lock, local disk". D5 (two personas): the Fulfiller's phone would reach the cloud, not the LAN. D42: the deploy needs its own rule about what may reach production.
- **What a person sees.** The same screens. Capture shows a "waiting to upload" state. Every screen needs an offline state it does not have today.

### (d) The full cloud server

- **Changes.** (c) plus the capture step: the browser sends frames to the cloud directly, and no local agent exists. Only the dispenser's Web Bluetooth link stays in the tab (D316).
- **Gain.** The Mac is a browser. No local process to restart.
- **Cost.** Everything in (c). Capture also needs the network on every card. The feeder paces at 623 ms per card (D88), so a dropped link stalls the line or loses a card. The photos cannot be re-taken.
- **Decisions touched.** All of (c). Also the "no auth" line in CLAUDE.md, and the rule that nothing about a card lives in `localStorage`. Also D19 (arming is an act), if the arm state moves.
- **What a person sees.** The same screens, slower on a bad link. Not recommended.

## 4. Hard constraints and risks

- **Identity truth.** D36 makes the photograph the truth about which card is in which slot. `realign` hashes photos. "Never guess an identification" sends doubt to Review with its photo. `banchi match audit` compares the free reader against every filed card's photo. A stock image is the catalog's art for a printing the card was already matched to. It cannot show that the match is right. So Review must keep the real photo. Any cloud move must keep every unverified card's photo readable.
- **What stays on the Mac in every option.** The camera, the dispenser link (D316) and the capture step up to the shutter. In (a) and (b) the server and store stay on the Mac as well, one store per checkout (D43).
- **Offline capture.** The owner shoots a box in one sitting. Options (c) and (d) put a network on the critical path of a photo nothing can regenerate. A local spool is the minimum. This is the largest risk in the proposal.
- **Privacy of real photos.** The photos show the owner's stock. Today they never leave the Mac. In (b) to (d) they sit with a cloud provider. The owner decides what is acceptable, including who can read the bucket.
- **Code-card opsec.** A live unredeemed code card is a bearer instrument. A code-card photo in cloud storage is a copy of that instrument. The pre-commit hook keeps every code-card photo and code string out of git, and so off GitHub (CLAUDE.md, "Code cards" and "Opsec"). That rule stands. Storage off the Mac is allowed (Q5).
- **Auth.** The front end has no auth. The server's only guard is an Origin allowlist on mutating verbs. Its own comment says it is not authentication (`server/capture_server.py`, the `SAFE_METHODS` block). `GET /photo` is `*` on purpose. That is acceptable on localhost and the LAN. It is not acceptable on the internet. Options (c) and (d) cannot ship without a login, TLS and a per-route read rule. No such design exists.
- **Threaded server in the cloud.** `CaptureServer` is a `ThreadingHTTPServer` with 4 + 4 slots tuned to one Mac's GIL (DEBT11). A cloud host would need the same bounds or a real WSGI or ASGI stack. The tuning does not transfer.
- **SQLite.** The store is one local file with a lock and a WAL (D88). A hosted copy needs one writer. Two writers (Mac and cloud) corrupt the truth.
- **TCGplayer exports and CSVs.** Exports land in `inventory/.exports/<game>/` and imports are written locally (D166, the catalog export belongs to the game). Export download uses the owner's TCGplayer session. Moving that to a cloud host is a credential question, not a code one.
- **Stock image availability.** DEBT44 records a brand-new set with no vendored row. `no_photo` and `no_url` printings exist. Sealed product resolves through tcgcsv only. Each needs a fallback to the real photo.
- **Cost.** Unmeasured. Storage for 4.45 GB is small. The variable cost is a hosted API with an always-on database, and egress for Review photos.

## 5. Recommended first step

**Measure, then do (a) on the one screen that costs the most.** This is small and reversible.

1. **Baseline, no code.** Read the `slow request:` lines (`scripts/status.py` greps them) and `photo_slots_in_use` over one working week. Record Activity Monitor CPU and memory for the server, the sweep worker and the browser tab. Do this during one capture sitting and one Inventory session. These are **unmeasured today**. They answer whether photos are the load at all.
2. **Count the finder.** Add one counter of `preview_cut` cache misses and their wall time to `/status`. This is the smallest piece of code in the proposal. It names the one photo hot spot.
3. **Build (a) for Inventory previews only** (`Inventory.tsx`, `BoxBrowse.tsx`). Put it behind a setting the owner can disable, with the real photo one press away. Leave Fulfillment, Home and Card hero alone until the owner rules on Q2.

**Proof it helped.** Compare the baseline week against the week after. Compare finder misses per Inventory session, `/photo/` requests per session, the `slow request:` count, and server CPU in the same sitting. **If the finder count and CPU do not move, stop.** Photos were not the load. The next lever is then the heavy reads in DEBT11 (a third bound, or a writer that yields its slot), not a cloud move.

**Undo.** Disable the setting. No data moves and nothing is deleted.

## 6. Open questions for the owner

1. **What is the Mac load you feel?** Options: (i) capture sittings run slow, (ii) browsing Inventory or Review is slow, (iii) fan or battery use with the server idle, (iv) disk space. Recommend naming one. Items (i) and (iii) point at the sweep and the heavy reads. Only (iv) points at photo storage.
   **Ruled: (ii), pages are slow.** The `.serve/capture.log` slow-request lines agree: 667 slow lines, only 26 on `/photo/` and `/assets/`. The rest are `/boxes`, `/search`, `/orders`, `/pipeline/waiting`, `/pipeline/crop-preview`, `/status`, `/inventory`, `/pipeline/pricing` and `/capture/sitting`. The first lever is the heavy reads in DEBT11, not a photo change.
2. **Should Fulfillment keep the real photo for a pull?** Options: (i) real photo always (today), (ii) stock first with "my photo" one press away, (iii) stock only. Recommend (i). The Fulfiller confirms the card in hand, and D38's premise holds there.
   **Ruled: (ii), stock first with "my photo" one press away.** This overrides the recommendation. D38's premise (the owner's photo confirms the slot) and D6's premise (the pull modal shows the card's own capture photo) are now weaker on this screen. The press must load the real photo, and a card with no stock image shows the real one (Q6).
3. **Keep every real photo after the card is verified?** Options: (i) keep all on the Mac (today). (ii) Keep all, and move verified ones to cold storage ((b)). (iii) Reclaim verified ones as sold ones are (D89). Recommend (i) until the disk is a measured problem. Option (iii) cannot be undone. It drops D36's re-bind for those cards.
   **Ruled: (i), keep all on the Mac, for now.** The owner has ideas and will revisit. Nothing moves or is deleted.
4. **Is a cloud server wanted, or only a lighter Mac?** Options: (i) a lighter Mac only ((a), (b)). (ii) A cloud API with a local capture agent ((c)). (iii) The full cloud ((d)). Recommend (i). Option (c) needs auth, an offline spool and a hosting bill. None of these exist.
   **Ruled: lighter Mac first, then a fifth option the spec did not list: (e) the same server moved to an always-on device at home.** (e) keeps one process and one store on the LAN, so D43, D88 and D138 hold and the Origin-only guard stays acceptable. It needs no cloud login or offline spool. Open for (e): which device, how the camera and dispenser reach it, and how the store moves (one writer, so a copy and a switch, never two live stores).
5. **May real photos leave the Mac at all?** Options: (i) never, (ii) only verified cards of non-code games, (iii) all. Recommend (i) until Q4 picks (c).
   **Ruled: (iii), all.** Code-card photos may leave the Mac like other photos. No rule says they stay local: CLAUDE.md bars them only from tracked files, listings, READMEs, screenshots and commits, and that rule stands. A commit reaches GitHub, which is publishing, not storage.
6. **Stock image fallback when none exists.** Options: (i) real photo, (ii) a labeled placeholder. Recommend (i).
   **Ruled: (i), the real photo.**
7. **What to build first?** Options: (i) a baseline and the slow reads (`/boxes`, `/search`, `/pipeline/waiting`, `/capture/sitting`), (ii) Fulfillment stock art (Q2), (iii) the home-device plan, (iv) the baseline alone. Recommend (i).
   **Ruled: (ii) and (iii), as two lanes, then revised.** The home-device plan is section 7 of this spec. Fulfillment stock art is parked as DEBT96 (Fulfillment still shows the owner's photo first). The slow reads are fixed with no baseline step. `POST /pipeline/waiting` reads only the chosen cards' photos (#893). `/boxes`, `/search` and `/capture/sitting` place cards from columns, not whole card objects (#896). Each has a T7 read-budget check that stays flat as the store grows.

## 7. Home-device plan (option (e))

Plan only. Nothing here is built. The home-tier spec (`docs/specs/home-assistant.md`) covers the always-on devices at home. This section covers only a whole-store move.

### What the device must keep

- **One process, one store, one writer** (D138, D88). The store and every photo move together. The Mac's server stops before the device's starts. Two live stores never exist.
- **The camera and the dispenser stay in a browser** (`app/src/useCamera.ts`, `app/src/dealer.ts`, D316). Chrome gives the camera and Web Bluetooth only to a secure page: `http://localhost` or HTTPS. `http://banchi.lan:8000` is not secure, so a capture tab pointed at the device loses both. `useCamera.ts` already names this failure (`INSECURE_CONTEXT_MESSAGE`).
- **Writes are Origin-checked** (`server/capture_server.py`, `DEFAULT_ALLOWED_ORIGINS`). Each new address the browser uses needs one entry in `BANCHI_ALLOWED_ORIGINS`.
- **The background jobs move too.** Start at login, the daily price refresh and the demo mirror are launchd agents today (`make launch-agent`, `make price-refresh-agent`, `make demo-mirror-agent`). The free reader needs its model runtime on the device.

### Where the capture tab runs: three ways

| Way | How the browser reaches the camera and dispenser | Gain | Cost |
|---|---|---|---|
| **A. Capture at the device** | The Cam Link and dispenser plug into the device. Chrome on the device opens `http://localhost`. | No change to the secure-page rule, the Origin list or the code. | The device needs a screen, a keyboard and Chrome, at the capture desk. |
| **B. A local tunnel from the capture machine** | The Mac forwards its own `localhost:8000` to the device (for example `ssh -L`). Chrome sees `localhost`. | Capture stays at the Mac. No certificate. | A tunnel must be up for every sitting, and a dropped tunnel stops capture mid-box. |
| **C. HTTPS on the device** | The device serves HTTPS under a name with a trusted certificate. | Any machine at home opens one secure address. | A certificate to issue and renew, and TLS added to a server that has none. New surface. |

**Recommend A on a Mac mini.** It keeps every launchd agent, the threaded server tuning (DEBT11) and the camera stack the same. Only the store moves. A Linux board needs systemd units in place of every launchd agent, and an unproven model runtime for the free reader.

### How the store moves

1. Stop the Mac's server (`make down`, by the owner).
2. Copy `inventory/` (store, photos, exports) and `~/.banchi` to the device. Size, measured on the owner's Mac (`docs/specs/home-assistant.md`, section 1): `store.sqlite` 126 MB and `inventory/` 733 MB, 354 MB of it the model file. The photo total is not known there: D172 recorded 4.45 GB, and the gap to the measured `captures/` is unexplained.
3. Start the device's server. Check `make status` and one capture.
4. Remove the Mac's start-at-login agent (`make launch-agent ARGS=--remove`), so the Mac never starts a second store.

**Undo.** Copy back and swap the agents again. Nothing is deleted on either side until the owner says so.

### Open for the owner

- **Which device.** Recommend a Mac mini, with way A. **Ruled: decide later.** The plan is parked.
- **Where capture happens.** At the device (A), or at the Mac through a tunnel (B).
- **Measure first.** The photo total, so the copy and the device's disk are known. The store and `inventory/` sizes are in step 2 above.
