# Capture server

`server/capture_server.py` is the LAN server that the capture app writes through. It runs on
`http.server.ThreadingHTTPServer` and adds nothing to `requirements.txt`. This file holds the
allocator's rule (§5) and the server's contract (§6). The module header in
`server/capture_server.py` is the register of routes. This file does not count them.

---

## 0. Rules that bind a doc

### 0.3 — Writing docs in this repo without blocking your own commit

The pre-commit hook runs the opsec rules and then `make docs-audit` in staged mode. Exit 1
blocks the commit. These constructs block:

- A path whose first segment is an existing top-level directory, and which does not exist.
  Backticks and fences do not exempt it.
- `make <target>` in backticks with no such Makefile target.
- `banchi <verb>` in backticks with an unregistered verb.
- An environment variable that no code, script or settings file names.
- The phrase "check" followed by a number. Name a row by its printed label instead.
- A decision id with no entry.

Name an unbuilt thing by its behavior and never by a file that does not exist. Paths under a
gitignored tree, such as `captures/` and `inventory/`, are skipped. Run `make docs-audit` on
the whole tree before staging.

---

## 5. allocator

D10 (inventory model) says a position is assigned at capture. `Inventory.allocate_capture` in
`store/master.py` does it.

### 5.1 — Where it lives, and its shape

The allocator lives on `Inventory`, beside `record_capture`. It does not live on the session,
which holds the lock and the transaction and has no domain logic. It does not live in the
server, which stays a transport.

Allocation folds into the write. `allocate_capture(box, capture_id=, cid=, section=,
layout_token=, **claims)` takes no index, so no stale read can enter a write. It returns
`(card, created)`. `created` is False only when `capture_id` replays a capture already
recorded.

`next_index(box)` is display only: status and run reports. Never pass its value into a write.
Two devices could both show "next: 17" and both post. Reading the value and then recording it
takes two lock acquisitions with a network round trip between them. That is the lost update
that `store/session.py` explains.

On a collision, `allocate_capture` raises `PositionOccupied`. It never upserts. `record_capture`
would take its existing-record branch and copy photo, set hint and finish over the incumbent
without a log. One physical card would vanish from inventory.

`record_capture` stays public and takes a `Card` with an explicit box and index. The CLI
depends on it. The safety is that the server never calls it for a capture.

`capture_id` is a field on `Card`. A retry guard that forgets across a restart is not a guard.

### 5.2 — The rule

`next = 1 + max(index of every card in the box, over all states, default 0)`. This is a
high-water mark. It is not count+1 and it is not first-free.

Indices are 1-based. Section and card derive from the index, so index 0 would label a slot
that does not exist.

- count+1 agrees with the high-water mark until anything deletes a record. Then it collides
  silently.
- first-free contradicts D10. Sold cards leave permanent gaps. The next captured card goes on
  the end of the stack, because that is where the operator's hand puts it.

A record whose box or index will not coerce to an integer stops the scan. It refuses and names
the position. Skipping it would hide the collision it is about to cause.

### 5.3 — Sections

Dividers are declared per box. An undeclared box is one undivided section, and no window size
is assumed. `pipeline/join.py`'s `Position` derives section, card and label from the box's own
layout. This file names it and does not restate it. `harness/tests/t3_join_coverage.py`
asserts the rendered label, so the server never re-derives one.

A divider goes in one at a time through `POST /boxes/<box>/sections`. The capture screen's `S`
sends it. A whole layout can be typed through `PUT /boxes/<box>`. Neither invents a divider.

A capture can name a section by divider key (`docs/specs/subbox-capture.md`). The store then
files the card at the tail of that section. An unknown key (`SectionGone`) writes nothing.

### 5.4 — Edge cases

- An empty box gives index 1.
- A box has no seal and no capacity (D299).
- A box that does not exist is created implicitly. `allocate_capture` calls `ensure_box`,
  which makes an unnamed, undeclared box if the registry has never seen the number. Capture
  never demands a registry entry first.
- A typo such as `box=33` for box 3 is a valid new box, and nothing downstream can tell. The
  app's box field creates boxes by name (`docs/specs/capture-app.md` §5.2), so no number is
  typed.
- Undo deletes the record and releases its index. `docs/specs/undo.md` owns it.

---

## 6. capture-server

### 6.1 — Framework

The load is two devices on a LAN. The app runs on the venv's Python 3.12 (`VENV_PYTHON` in the
Makefile). Stand-alone scripts that the Makefile runs with bare `python3` use the system Python
3.9. Keep those scripts free of `X | None` and `match`. `requirements.txt` lists what it deliberately omits
(D15), so every addition is a recorded decision.

### 6.2 — The module docstring carries the contract

The module docstring states the route list and status codes. It states that every write goes
through the store session, and that the server never touches disk state directly.

### 6.3 — The sidecar contract

The server writes a sidecar beside each photo. `identify/sidecar.py` reads it. The link is
one-way. A mismatch surfaces at identification time, which is when money is spent.

**Location.** A photograph is filed under the card's name: `<home>/photos/<aa>/<cid>.jpg`
(D183). The sidecar is `<cid>.json` beside it. `store/photos.py` is the only module that
composes that path. `<home>/captures/cards/box<N>/<index>.jpg` is the legacy address. Reads
try it only until the store's `photos_relocated` gate is set.

**The money rule.** `identify.sidecar.scan` walks its root recursively. It turns every file
with a photo suffix into a capture and so into a paid Batch request. Nothing but card photos
and their sidecars may sit under a scanned root. Photos live outside `captures/` for this
reason. `captures/ui/` holds screenshots, which are also photo-suffixed.

**One extension.** The client posts JPEG bytes. The server checks the magic bytes and refuses
anything else. It does not convert. Re-encoding at capture time is forbidden by §6.6.

**Keys.** `sidecar_payload` writes `box`, `index` and the claims. `CLAIM_WIRE_NAMES` maps each
claim to its wire spelling: `set_hint`, `variant` (the record's `metadata_finish`), `game`,
`rarity_claim`, `product` and `note`. An empty claim is never written, because absent means no
claim (D3, D23).

Write `index` as an integer. Never write `position`. The reader accepts it as an alias, but the
store's `position_key` returns a string such as `"3/17"`. With a valid `box` present, the
reader takes the sidecar branch on the box alone. It then labels the capture as coming from the
sidecar while the index came from the filename. No problem is recorded. The server's own
output hides that mistake.

A missing or malformed sidecar is not a failure. The reader recovers the position from the
filename. `identify/sidecar.py` documents the reader's cases. A photo named by its card
digest carries no position, and the reader refuses to invent one.

### 6.4 — Routes

The port is 8000 in the main checkout. A linked worktree derives its own port from
`server/ports.py` (D43). Bodies are JSON in and JSON out, except photo bytes.

**`POST /capture`.** The body is `application/json` with a base64 `image`. The stdlib has no
multipart parser worth using on the path that allocates positions. The body carries `box` and
`image`. It can carry `capture_id`, `section`, `layout_token` and the claims. The server holds
no current box. Box, hint and finish are client state, resent on every capture. That is how two
devices share one truth without a session. The response is 201 with the card, its position
label and section key. A replayed `capture_id` returns the original card with 200.

The server checks the claims before it decodes the image, because the claims are cheap and a
refusal should burn nothing. It computes the card's name from the decoded bytes before it takes
the lock.

**`GET /status`.** It takes no lock and has no side effects. It reports counts, the next index
per known box, and whether the store parses. It never probes the lock, because the only
primitive is an acquire and a read route must not become a writer. It carries `boot_id`, a
per-process id. A client can then tell a restart from a reload, and a stale server is visible.

**`GET /photo/<box>/<position>`.** It returns the photo bytes, or 404 when absent (D6, one
photo route serves every view).

**`GET /inventory` and `PUT /inventory/<box>/<position>`.** `GET` returns the card map. `PUT`
is per position and never a whole-document replace. A replace would rebuild every card from a
client's stale snapshot, which is the lost update of §5.1 with a wider blast radius. `PUT`
corrects the claims in `PUT_FIELDS`, and it never creates a card. It also rewrites the
sidecar, because `cli/cmd_identify.py` builds its card from the sidecar and would otherwise
revert the correction. It appends a `corrected` event.

**Errors.** Every error body says what happened and what to do next, because the app shows
these strings. Reserve 500 for bugs. Every anticipated condition gets its own code.

**CORS and origin gate.** The app is a different origin, and the Fulfiller's device is on the
LAN. There is no auth and no TLS on this LAN tool (D13, D5). Do not add a login screen.

- Reads allow any origin, so `GET /photo/...` stays embeddable.
- The mutating verbs are gated by an origin allowlist. `_dispatch` runs the gate ahead of
  every handler. Without it, any page open in the owner's browser could preflight and send
  `DELETE /inventory/3/17`, which hard-deletes the record, the sidecar and the photo.
- An absent `Origin` may write. A browser page cannot omit the header. `curl`, `./banchi`
  and the harness all omit it, so requiring it would break every command-line path.
- An unknown origin is told `GET, HEAD, OPTIONS` only. Its preflight for a write fails in the
  browser, and the request never leaves. `fetch` then rejects with a bare `TypeError`.
  `app/src/server.ts` probes `GET /status` on that path and raises `origin_blocked`, which
  names the address as the thing refused. It never reports `unreachable` for a running server.
- The defaults are this checkout's own dev origin, `http://localhost:<dev port>` and
  `http://127.0.0.1:<dev port>` (D43). `BANCHI_ALLOWED_ORIGINS` extends them and never
  replaces them. Entries are comma- or whitespace-separated, lowercased, without a trailing
  slash. A port is never defaulted in. Comparison is by exact string, so `*` refuses
  everything and does not open the gate. T7 asserts this.
- `BANCHI_LAN_NAME` (D138) names the owner's DNS name for this Mac. `scripts/serve.py` reads
  it through `envfile`, so it belongs in `.env` and not in a shell profile. It composes
  `BANCHI_ALLOWED_ORIGINS` from that name and this Mac's Bonjour name. A phone can then
  write and not only read.

### 6.4b — Is the LAN URL still good? (`make lan-check`)

`make lan-check` runs the whole chain from this machine and says whether the LAN address works
for a phone. Reads are ungated and writes are origin-checked. Losing the LAN name leaves the
app rendering every screen while capture, undo, mark-sold and every other write answer 403
`origin_not_allowed`. So "I opened it and it looked fine" is not evidence. The check presses a
write to find out.

Parts that hold `http://banchi.lan:8000` up:

| Where | What | If it is wrong |
|---|---|---|
| the owner's router | a DHCP reservation pinning this Mac | the name resolves to an address this Mac no longer holds |
| the owner's router | a local DNS record for `banchi.lan` | the name does not resolve |
| here | `app/vite.config.ts`'s `allowedHosts` | "Blocked request. This host is not allowed." |
| here | `app/src/server.ts` composing the capture base from `location.hostname` | the phone calls itself |
| here | `BANCHI_LAN_NAME` in `.env` | writes answer 403 and reads do not |
| here | `BANCHI_ALLOWED_ORIGINS`, composed by `scripts/serve.py` | the same |

The check writes nothing. The origin gate runs ahead of the body read. `POST /capture` with no
body therefore answers `origin_not_allowed` for an unknown origin and `body_required` for a
known one. `body_required` is raised before the store opens. The same request with one header
different is the experiment. A foreign-origin request is the control. It also asks the
preflight question, because a `curl`-only check would pass on a rig where the browser blocks
every phone write.

It does not prove that the phone resolves the name. Every row runs from this Mac. A phone on a
guest VLAN, or with a VPN, can fail while everything here passes.

It is not in `make check`. `make check` answers from the tree alone. A row that resolves DNS
and expects a server would go red on a train and in every worktree.

### 6.4a — Shutdown, and why it counts requests rather than threads

`make up` restarts the server whenever a watched Python file changes (D138), so shutdown
happens many times a day. The store commits one SQLite transaction per write (D88). A kill
between file writes of photos and sidecars can still leave a file the store does not describe.

On SIGTERM or Ctrl-C the server stops accepting first, then waits for in-flight requests, then
exits. `DRAIN_SECONDS` bounds the wait. It is `files.LOCK_TIMEOUT_SECONDS + 5`, derived and not
chosen. A capture can wait on `./banchi identify` for the full lock timeout before it answers
`store_busy`. A shorter drain would cut a request that behaved correctly.
Past the bound the server exits and says so loudly.

The counter lives at `_dispatch` and counts requests, not threads or connections.
`ThreadingHTTPServer` sets `daemon_threads = True`, so `server_close()`'s join is already a
no-op. Setting it to `False` would block forever, because HTTP/1.1 keeps a handler thread
alive for the whole connection. T7's `check_drain` asserts the seam.

### 6.5 — Concurrency

The server is a second writer and not a second owner. It holds no authoritative copy between
requests. It has no cache, no dirty set and no periodic flush.

1. Reads take no lock. The lock is an exclusive `flock`, so a shared read mode would serialize
   both devices' polling behind every write. A read that lost the race would stall for the full
   30-second timeout.
2. Every write goes through `Store().write()` and nothing else. It opens one SQLite transaction
   (`BEGIN IMMEDIATE`) inside the lock. It commits on a clean exit and writes nothing when an
   exception escapes. Do not catch and continue inside the block.
3. Photographs and sidecars are outside the transaction. A crash between a file write and the
   commit can leave a file that the store does not describe. Write the expensive file so that
   every partial failure left is the cheap one.
4. Allocation happens inside the same lock as the record (§5.1).
5. Never hold the lock across a network wait. Decode the whole body first, then open the
   session.
6. No background thread mutates the store.

The `flock` is on a fresh handle per call. Two threads in one process contend as two processes
do, so a threading server needs no extra in-process lock.

### 6.6 — What the capture path must not do

- No detection, cropping, downscaling or re-encoding at capture time. That is batch-time work.
- No identification. The capture server reads no API key, makes no Batch call and never spends
  money.
- No pricing, CSV, join or catalog work on the capture path.
- No renumbering, compaction or gap-filling by capture (D10). Those operations would make the
  history file lie.
- No auto-capture logic. The trigger is client-side (`docs/specs/capture-app.md` §6).

### 6.7 — `make server` blocks

`make server` runs in the foreground. An agent that runs it in the foreground hangs its own
turn. Agents background it, or use `make up`.
