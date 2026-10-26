# The home tier: the HA Green, its 2 TB drive, the network and a Mac Studio

**Status: PARKED by the owner. Nothing here is built.** Each role needs the owner's word before it is built. The
file cites decisions to show what a role touches. Ruling 6 removed D13's one-Mac paragraph. Section 6
lists the other decisions a role would change.

## Owner rulings

1. **Alerts are not the goal.** Home automations (lights, buttons, phone panels) are not the goal either.
2. **The goal is infrastructure.** The always-on HA Green, its 2 TB USB drive, the UniFi network and a
   possible Mac Studio become banchi's second tier, beside the Mac. The design starts from the problems
   banchi has because it lives on one computer.
3. **The Green tier takes four roles:** storage tier, front door, scheduler and waker, standby read
   copy. Each is designed in section 4.
4. **Also in scope:** the Green does the server's internet fetching and holds caches.
5. **The Green is trusted as the Mac is.** The owner's HA setup sits inside an encrypted setup as secure
   as the Mac. The store, the photos and the secrets (the TCGplayer cookie, the Anthropic key) may live on it.
6. **No rule ties the store to one Mac.** D13's paragraph that the store and photos live on one Mac and
   are read only through its server is deleted as too specific. D13's camera rules stay. Untangling
   decisions that hold more than one rule is a later lane.
7. **Reclaim moves sold photos to a recycle bin on the drive.** A later cleanup empties the bin. Its
   timing is open. This is planning only: D89 changes when R1 is built, not before.

## 1. What the tier is

| Part | Facts | Limits that shape the design |
|---|---|---|
| HA Green | Rockchip RK3566, four Cortex-A55 cores, 4 GB RAM, 32 GB eMMC, gigabit Ethernet, two USB 2.0 ports. About 2-3 W. Always on. | It shares the box with HA Core, AdGuard (the phone's DNS over WireGuard) and the `degen` add-on. The Supervisor has no per-add-on memory cap, so a runaway add-on can take down DNS. USB 2.0 caps bulk copies well below gigabit. Keep data on the USB drive, not the eMMC. An HA restart takes about 2 minutes. HA backups are off. |
| 2 TB USB drive | Already HA's data disk, so add-on `/share` and `/data` live on it. | The drive has no backup of its own. Never open a live SQLite file over SMB or NFS (DEBT67, D88). |
| UniFi UDR7 | WireGuard server, a fixed IP for the Green, and AdGuard rewrites under `home.arpa` (`feed.home.arpa` already points at the Green). | A Wake-on-LAN magic packet is broadcast, so the Mac must be on the same network. |
| This Mac | MacBook Pro, M5 Pro, 24 GB. On Wi-Fi. `pmset` sleep is 0 and `womp` is 1. 84 GB free on the system disk. | A laptop can leave the house. Wake-on-LAN does not work over Wi-Fi. |
| Mac Studio (possible) | Idle about 6-9 W. | Not bought. Lean-server spec section 7 (option e) parks a whole-store move to a Mac mini. |

Measured on this Mac: `store.sqlite` 126 MB, `inventory/` 733 MB (354 MB of it the model file),
`captures/` 5.1 MB in 450 files for 4,286 cards. D172 recorded 4.45 GB of photos. The gap is
unexplained (unmeasured why).

## 2. Problems from living on one computer

Each row names the role in section 4 that answers it. "None" means no role here answers it.

| Aspect | Problem for the owner | Evidence | Role |
|---|---|---|---|
| Durability | The store and every photo exist once. Error text says "restore from a backup", and nothing makes one. | DEBT67, D88 | R1 |
| Durability | `price_history` is the only copy once a bucket leaves the source's 357-day window. | D219, D222 | R1 |
| Durability | A photo reclaim deletes the sold photo with no undo. | D89 | R1 |
| Durability | `.env` holds the Anthropic key and the TCGplayer cookie on this Mac only. | `envfile.get_live` | R1, R2 |
| Fetching | A catalog export holds one of four request slots for up to 120 s. | D104, D166 | R2 |
| Fetching | An orders fetch is about 115 requests against a 120 a minute budget, in the request. Two presses in a minute can break the budget. An unattended fetch needs its own entry. | D91, `order_transport.fetch_open_orders` | R2 |
| Fetching | The price-history sweep is 3,656 requests, about an hour, run nightly by the daily price job. | D224, DEBT32 | R2 |
| Fetching | Stock photos are hotlinked from two CDNs with no disk cache. pokemontcg.io ends on 2027-03-01. | D301, DEBT44 | R2 |
| Fetching | The catalog image mirror is 16.7 GB, by hand only. | D15, `make catalog-mirror` | R2 |
| Fetching | A Haiku batch is polled by a child of the server for up to an hour. | `identify.batch` | R2 |
| Availability | The daily price refresh and demo mirror run at set times. Nothing handles a missed run. | `scripts/launchagent.py` | R3 |
| Availability | When the Mac is off, the Fulfiller cannot see the pack list or where a card is. | D152 | R4 |
| Access | The server has no auth and listens on every interface. A LAN client that sends no Origin can write or delete. | `capture_server.HOST`, D5 | R5 |
| Access | Plain http on a LAN name is not a secure context. The Fulfiller's phone loses `crypto.randomUUID` and any camera use. | `useCamera`, `server.ts` | R5 |
| Access | No way in from outside the house. | None found | R5 |
| Load | Slow reads are GIL-bound inside the server (`/orders`, `/inventory`, `/boxes`, `/search`, `/pricing`). | DEBT11, lean-server spec | None. Lean-server spec, PR #852. |
| Ops | Dev and prod share the Mac. Test fleets wedged the live server, and branch code reached :8000 twice. | DEBT11, DEBT16, D158 | R6 |

## 3. The shape: the Green fetches and keeps, the Mac writes

One writer stays one writer (D88, D138). The Green never writes `store.sqlite`.

- The Green runs the outbound work on its own clock and drops raw results into a folder on the 2 TB
  drive. This is the drop-folder pattern of `degen`'s JDownloader add-on: `in`, then `done` or
  `refused`, checked by a guard that fails closed.
- The Mac's server ingests a drop under its own store lock, the next time it is up.
- The Mac pushes copies out: the store as a replica, photos as files.
- Heavy compute (the free reader peaks at 1.1 GB, the card finder) never runs on the Green. It stays on
  the Mac, or later the Studio.

## 4. Roles

### R1. Storage tier

- **What.** Litestream streams the store's WAL to the Green over SFTP, as a replica copy. A nightly
  `sqlite3 .backup` is the simpler fallback. Photos and `price_history` exports sync as files. The
  catalog image mirror lives on the drive. A reclaim moves a sold photo to a recycle bin on the drive
  instead of deleting it (ruling 7). A later cleanup empties the bin.
- **Solves.** DEBT67, the one-copy store. The `price_history` loss. D89's no-undo reclaim.
- **Cost.** Small. One replication process on the Mac and one SFTP or SSH target on the Green (the
  `core_ssh` add-on exists). Litestream needs WAL mode and a `busy_timeout`, and the store already uses WAL (D88).
- **Risk.** The store holds buyer names and addresses (D295 scrubs them for the demo). Ruling 5 allows it
  on the Green. Keep it in the banchi add-on's own `/data` anyway, so no other add-on reads it by accident.
  HA backups are off, so the Green copy is a second copy, not a backed-up one.
- **Touches.** D88, D89 (reclaim becomes a move), DEBT67, `make status` (a "last copied" line).

### R2. Fetch tier and cache

- **What.** A local add-on on the Green runs banchi's outbound fetches and writes each result to the
  drop folder:
  - catalog exports per game
  - the live listings export
  - the orders pages
  - the price-history sweep, on a schedule
  - Haiku batch polling
  - the catalog image mirror

  An nginx `proxy_cache` in front of the stock-photo CDNs keeps each image once, revalidates it, and
  serves it stale when the CDN is down. After 2027-03-01 the cache is the Pokemon stock-photo source.
- **Solves.** No fetch holds a request slot. Jobs run on time with the Mac asleep. Fetches stay paced
  from one place. DEBT32 and DEBT44.
- **Cost.** Medium to large. The fetch code moves behind a drop-folder contract, and ingest becomes a
  server step. The Green is aarch64 Linux. Banchi's fetch modules are stdlib Python, but `server.ports`
  shells out to Mac-only tools, so the add-on needs a fetch-only entry point (unmeasured effort).
- **Risk.** The TCGplayer cookie and the Anthropic key live on the Green (ruling 5). The cookie expires
  and is pasted by hand (`order_session_expired`), so the paste must reach the Green.
- **Touches.** D104 (live fetch is a guarded constant), D166 (export reuse), D91 (unattended orders
  fetch needs its own entry), D301 (stock photos are hotlinked).

### R3. Scheduler and waker

- **What is left of it after R2.** Fetches no longer need the Mac awake. The waker only matters when
  ingest or a Mac-only job must finish before a sitting, such as the demo mirror, which needs `gh` and
  the checkout.
- **How.** Wake-on-LAN needs Ethernet, and this Mac is on Wi-Fi, so it cannot work today. The working
  path is `pmset repeat wakeorpoweron` on the Mac, with HA as the one scheduler for everything on the
  Green. Missed-run handling (catch up on the next wake) goes into both daily scripts.
- **Cost.** Small.
- **Touches.** `scripts/launchagent.py`, D295 (demo mirror), D176.

### R4. Standby read copy

- **What.** A read-only view on the Green, built from R1's replica and labeled with its age. First form:
  a static pack list and a "where is this card" lookup, regenerated on each replica update and served
  by nginx. It takes no writes.
- **Why static first.** A read-only banchi server on aarch64 Linux is unproven (`server.ports` is
  Mac-bound, and onnxruntime is untested there). A static page needs neither.
- **Solves.** The Fulfiller can pack while the Mac is off or away.
- **Cost.** Medium.
- **Risk.** A stale answer about a card that just sold. The age label and "read only" must be on screen
  (D196 keeps mechanism words off screen, so the label is a sentence).
- **Touches.** D5 (two personas), D27, ruling 6.

### R5. Front door

- **What.** `banchi.home.arpa` through an AdGuard rewrite, TLS from a proxy on the Green (Nginx Proxy
  Manager add-on, or Caddy), a login at the proxy, and WireGuard for outside the house.
- **The gap a proxy alone leaves.** The Mac's server listens on every interface, so the LAN can walk
  around the proxy. One of these must close the bare port:
  - The server accepts only loopback and the Green's address.
  - The macOS firewall does the same.
  - The proxy runs on the Mac instead.

  `HOST = "::"` fixed a dual-stack collision, and any change must keep that fix.
- **What TLS gives.** The Fulfiller's phone gets a secure context. The capture tab stays on `localhost`,
  because the rig is wired to the Mac and Web Bluetooth needs a secure page. A new host resets the
  camera grant and the device keys on that device (D138, D27).
- **Certificate choice.** A Caddy internal CA needs its root installed on each device. Let's Encrypt
  DNS-01 needs a real domain with a DNS API, and gives a publicly trusted certificate (Q4).
- **Cost.** Medium. A certificate to renew, a proxy to keep up, and a bind change on the Mac.
- **Touches.** D5, D138, D27, the `BANCHI_ALLOWED_ORIGINS` list.

### R6. The Mac Studio, later

- **What.** The Studio runs prod: the store, capture and the heavy readers. The Green stays the
  always-on edge (R1 to R5). This MacBook becomes a dev machine and a client.
- **Solves.** Dev and prod stop sharing a machine (DEBT16, D158). The laptop can leave the house.
- **Plan.** Lean-server spec section 7 is the move plan. This role adds the edge in front of it.

## 5. Order

1. R1, the storage tier. It changes no decision except D89's reclaim, and it closes the worst gap.
2. R3, the scheduler. Missed-run handling and `pmset` alone. Small.
3. R2, the fetch tier. Start with the stock-photo cache and the price-history sweep. They
   need no cookie.
4. R5, the front door, after the bind decision.
5. R4, the standby copy, after R1 has run for a while.
6. R6, when a Studio exists.

## 6. Open questions for the owner

Asked one at a time. Each ruling moves into "Owner rulings" above.

1. **Where may the store, the photos and the secrets live?** Ruled: ruling 5.
2. **D13, once "the Mac holds the one truth", now the camera path.** Ruled: ruling 6.
3. **D89's reclaim.** Ruled: ruling 7. Still open: when the cleanup empties the recycle bin.
4. **Certificates.** Deferred by the owner until more of the plan has landed. Options then: reuse the
   mkcert root `degen` uses for `feed.home.arpa`, Let's Encrypt DNS-01 on a real domain, or a Caddy internal CA.
5. **Closing the bare port.** Deferred with question 4, as front-door detail. Options: loopback plus
   the Green, a firewall rule, or the proxy on the Mac.
6. **Who owns the Green-side config.** Deferred: decided when the first Green piece is built. Options:
   a banchi add-on folder (the `degen` pattern), or the `home` repo.

## 7. What not to do

- **Never run a live store on the Green, or over SMB or NFS.** One writer (D88). `fcntl.flock` and
  `os.replace` do not hold over a network share (DEBT67).
- **Never run heavy compute on the Green.** It has 4 GB of RAM, no memory cap, and it carries the phone's DNS.
- **Never let HA or the Green restart, update or stop banchi.** The primary checkout syncs itself (D176),
  and main moves by PR (D42).
- **Never put the full HA token in banchi.** Banchi needs no HA API for these roles.
- **Never put a code-card photo or code string on the Green.** A live code is a bearer instrument
  (CLAUDE.md "Opsec").
- **Never trust a copy that was never restored.** R1 is done only after a restore from the replica
  passes a check.

## Sources

Read-only: `shivinate7/home` records, `shivinate7/home-app` `SPEC.md`, `shivinate7/ios-adblock`
research notes and tools, `shivinate7/degen` `ops/ha-addon/` and its hosting decision,
`shivinate7/tcg-dealer` `PROTOCOL.md`. Vendor docs: HA Green, HA add-on configuration, Litestream,
SQLite backup and "use over a network", nginx `proxy_cache`, `pmset`, MDN secure contexts, Caddy
automatic HTTPS, Let's Encrypt challenge types.

Set aside by ruling 1: an earlier draft proposed failure alerts, a heartbeat and an HA dashboard card.
It also proposed rig state in HA, ESPHome dispenser firmware and HA-driven updates. Git keeps it.
