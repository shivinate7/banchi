# Home Assistant improvements for banchi

**Status: PROPOSAL. Nothing here is built.** Each candidate needs the owner's word first. No decision
is reopened by this file. It cites decisions to show what a candidate would touch.

The owner runs Home Assistant (HA) on a HA Green. This file records what three of the owner's
repos do with HA and over-the-air (OTA) updates. It then says which of those patterns would help
banchi, and which would not.

Sources, all read-only. Paths are inside each repo.

- `shivinate7/home`: `CLAUDE.md`, `README.md`, `tools/ha-ws.mjs`, `tools/deploy-degen.sh`,
  `records/` (`adguard-home.md`, `ha-mcp.md`, `home-app.md`, `hacs.md`, `backups.md`, `plan.md`,
  `smart-home-design.md`, `scripts.md`, `tunnel.md`).
- `shivinate7/ios-adblock`: `tools/reinstall-phone-apps`, `tools/phone-apps.json`,
  `tools/dev.shivinate.phone-apps.reinstall.plist`, `.github/workflows/` (`ci.yml`,
  `pin-bump.yml`, `export-lists.yml`), `DESIGN.md`.
- `shivinate7/degen` (GitHub only): `ops/ha-addon/` (`README.md`, `config.yaml`, `run.sh`),
  `ops/lan-check.py`, `docs/owner-steps.md`, `docs/decisions/hosting-always-on-host.md`,
  `.github/workflows/nightly.yml`.

Not read: `shivinate7/home-app` (the owner's HA client app) and tcg-dealer (the dispenser
firmware). The `home` records mention both. Claims about them below come from those records only.

## 1. What the three repos do with HA and OTA

### home: the control repo for the HA Green

- **Route to HA.** Four routes, all from the owner's Mac.
  - The HA WebSocket API, through `tools/ha-ws.mjs`. It sends JSON commands and prints the results.
  - SSH to the HA Green as root, with one key. The SSH add-on runs the `ha` CLI and the Supervisor API.
  - The ha-mcp add-on. It is an MCP server over plain HTTP on the LAN, set to read-only (`records/ha-mcp.md`).
  - HACS, which installs custom integrations (`records/hacs.md`).
- **OTA.** Pull, driven by a script on the Mac. `tools/deploy-degen.sh <sha>` does these steps.
  - It exports the commit with `git archive` and builds it.
  - It copies the add-on folder to the Green over SSH.
  - It runs `ha store reload`, then `ha apps update` (or `rebuild`), then starts the add-on.
  - It probes HTTPS with retries.
  - HA add-on updates and HACS installs are done by hand in HA.
  - Static web files for the home app are copied into the HA `www` folder (`records/home-app.md`).
- **Rollback.** Per change, written in the record: remove the files, delete the integration, or
  restore a placeholder. For add-ons, `deploy-degen.sh` takes any SHA, so an older SHA is the
  rollback. No automatic rollback exists. (This last line is my reading of the script.)
- **Auth and secrets.** A long-lived HA token in a mode-600 file on the Mac. The script reads it and
  never prints it. The ha-mcp URL has a secret path that is the only access control. A GitHub token
  sits inside HA's HACS entry. Rule in `CLAUDE.md`: never print or commit a token, and Claude never
  types one into a field.
- **Monitoring.** Two HA automations: `addon_down_alert` (an add-on is off for 2 minutes) and
  `disk_low_alert` (free disk under a floor for 10 minutes). Both push to the HA companion app on
  the owner's phone. The add-on watchdog restarts a stopped add-on first, so a short stop sends no alert.
  The disk alert is recorded as unproven. A "Needs attention" row and a "Last backup" row go on the
  home app's System page. Backups are manual: the record says no schedule and no off-device copy.
- **Lessons in the records.**
  - A Core restart stranded a new HomeKit config entry. A restart now needs a check with the other
    sessions that use HA, and a post-restart check list.
  - HA serves `/local/` with a 31-day cache. A new deploy was not seen. The fix: `index.html` reads
    a `version.json` with no-store, then loads assets with `?v=<n>`.
  - After one reboot the DNS add-on bound only loopback. A restart of the add-on fixed it. The
    record keeps a `dig` check.
  - One restart was cleared with "no work depends on HA". A second session on the same host was
    asked only after. The record says so in its own words.
  - A guard is recorded as unproven until a test makes it fire.

### ios-adblock: HA as a host, and its own OTA loop

- **Route to HA.** Almost none. It does not call the HA API. The HA Green hosts AdGuard Home as an
  add-on, and the phone reaches it through a WireGuard tunnel. The research notes moved to `home`.
- **OTA.** The phone app is signed with a free team, so the signing lapses every 7 days.
  `tools/reinstall-phone-apps` is a daily launchd job on the Mac. For each app in
  `tools/phone-apps.json`, it does these steps.
  - It uses a private clone and runs `git reset --hard origin/main`.
  - It runs the prebuild commands, then builds and signs.
  - It installs with `devicectl`.
  - It keeps a `last-success` stamp per app. It skips if the stamp is under 20 hours old. It alerts
    if the stamp is over 3 days old.
  - Degen is a second entry in the same job.
  - A second OTA path: `.github/workflows/export-lists.yml` makes a versioned GitHub release of the
    blocklists. `pin-bump.yml` opens a daily PR that bumps pinned list sources. The PR auto-merges
    when the required check is green.
- **Rollback.** None for the phone app. The next daily run installs main again. A failed step leaves
  the old build on the phone.
- **Auth and secrets.** The device id and team id are script defaults. No token. CI uses
  `permissions: {}` by default and per-job grants. Actions are pinned by full SHA, and a zizmor
  audit runs in CI.
- **Monitoring.** `notify` uses `osascript` for a Mac notification. It runs on any failed step and
  on an overdue or invalid stamp. Every step has a timeout. Step output goes to a file, not a
  pipe, so a child that holds stdout cannot defeat the timeout. An absent or locked phone is a soft
  fail with its own exit code (75). A nightly CI run opens an issue if main is red (`ci-alarm` action).
- **Lessons in the repo.** A draft-skipped CI run cancelled the real run, so the draft state is now
  in the concurrency group. A bot PR made with the workflow token gets its CI run held for approval,
  so `pin-bump.yml` approves it. The file calls that a bandaid. The script guards its `reset --hard`
  (real directory, own git root, expected origin).

### degen: a feed reader that runs as an HA add-on

- **Route to HA.** HA hosts it. It is not wired into HA. It is a local add-on (`ops/ha-addon/`):
  a Dockerfile, a `config.yaml`, and a `run.sh`. The config has the arch, `boot: auto`, one TCP port,
  `share` read-write, `ssl` read-only, and a `watchdog` on the TCP port. I found no call to the HA API
  in `server/`. Its health route is `/api/health`.
- **OTA.** Server: `deploy-degen.sh` in `home` (above). The add-on `version` is the short SHA, so HA
  sees every commit as an update. The README notes a trap: `rebuild` fails when the version
  changed, so use `update`. Web client: a PWA with a service worker. A test
  (`app/tests/pwa-update.spec.ts`) proves that an open app picks up a new build, and that a resume
  from the background checks for one. iPhone app: the `ios-adblock` reinstall job.
- **Auth and secrets.** The TLS pair lives in the HA `ssl` share and never in git. `run.sh` copies
  it to a private folder (mode 0700). It starts the server as a non-root user with `no-new-privs`.
  Push keys are in an untracked `.env`. HTTPS uses a local CA.
- **Monitoring.** The add-on watchdog, plus `addon_down_alert` from `home`. `ops/lan-check.py` is a
  stdlib script run from the Mac. It prints `PASS`, `FAIL` or `UNKNOWN` per check (dns, tls, health,
  sources, origin, csp, media). A check that cannot run is never a pass. `nightly.yml` is the same
  red-main alarm as above.
- **Lessons.** `ops/ha-addon/README.md` records that the add-on config cannot exclude the data share
  from HA backups. `run.sh` records no memory limit and no disk cap (`ponytail:` notes). Degen's
  hosting decision (`docs/decisions/hosting-always-on-host.md`) lists the facts that would reopen it.

## 2. Candidates for banchi

Order: value against effort, best first. Every candidate is a proposal.

Banchi facts that shape all of them:

- Banchi is a Mac app with a camera, a Bluetooth link and a local store. HA is on a different box
  that can restart. A restart takes a couple of minutes, per the `home` records. So every call to HA
  must be best-effort and short. It must never sit inside a write path or a request slot.
- The server has no auth and binds to the Mac (CLAUDE.md "No auth"). Do not open it to the LAN.
  Push outbound from the Mac. Do not let HA poll in.
- The front end talks to the capture server and nothing else, save the dispenser link (D316, a
  Capture button starts and stops the dispenser). The browser must never call HA.
- A new alert must be shown to fire before it is trusted. The `home` disk alert is still unproven.

### C1. Last-success stamp and overdue alert for the daily agents (no HA needed)

- **What.** The price-refresh and demo-mirror agents each write a `last-success` stamp. A small check
  raises a Mac notification when a stamp is older than a set limit, or invalid. A failed step also
  notifies.
- **Reuses.** `ios-adblock` `tools/reinstall-phone-apps`: stamp file, overdue limit, invalid-stamp
  case, `osascript` notify, and a log-path hint in the message.
- **Gain.** Today a failed or partial price refresh shows as a note on `#/pricing`. The owner sees
  it only if that screen is open. This pushes the news to the owner.
- **Cost and risk.** Small. Both agents already log to a file in `~/.banchi`. Risk: a notification
  from a sleeping Mac is late. Risk: the demo-mirror script sits under an auto-merge fence, so its
  change is its own PR. The price-refresh script notes the same.
- **Touches.** D104, live fetch is its own guarded constant (the daily job runs that fetch). D295,
  the public demo is the scrubbed real store. D42, main moves by pull request (the mirror's
  auto-merge fence).
- **Why first.** It gives most of the value of C2 and C3 with no HA, no secret and no network.

### C2. Alert bridge: banchi failures to the owner's phone through HA

- **What.** When C1 raises an alert, also send it to HA. HA pushes it to the companion app on the
  owner's phone. Events: a daily agent failed or is overdue, a run is stranded, an identify or send
  stopped and needs review, the server restarted by itself.
- **Reuses.** `home` `addon_down_alert` and the companion-app notify service. For the send, prefer an
  HA webhook trigger over the full-access token that `tools/ha-ws.mjs` uses. A webhook can only
  start the one automation it belongs to.
- **Gain.** The owner learns of a stranded run or a missed refresh away from the Mac.
- **Cost and risk.** Small to medium. It needs one HA automation on the owner's side. It needs one
  sender function on the banchi side, with a 3 second timeout that swallows errors.
  - Risk: the webhook id is a secret. Keep it in `~/.banchi` (mode 600). Never put it in git, a
    log or a screen. The pre-commit hook should learn to refuse it.
  - Risk: alert fatigue. Send one digest for review items, not one message per card.
  - Risk: HA is down at the moment of the failure. The Mac notification from C1 stays the floor.
- **Touches.** D305, the reaper stops only its own (the sender must not kill or restart anything).
  D33, reachable from a screen. The hard rule that a route is not a feature applies: the setting
  needs a control the owner can find, with a "send a test alert" press and a receipt.
  CLAUDE.md "Opsec" (the secret scan).

### C3. Heartbeat sensor, and HA alerts on silence

- **What.** A separate launchd watcher on the Mac (not the capture server) reads `/status` once a
  minute. It sends a small digest to HA: server up, its boot id, open review count, unsent copies,
  and last success per agent. HA keeps the digest as sensors. An HA automation alerts when the
  heartbeat stops for longer than a set time.
- **Reuses.** `home` `addon_down_alert` (the "off for N minutes" shape) and the add-on watchdog
  idea (restart first, alert only if the restart did not help). `degen` `ops/lan-check.py`: `PASS`,
  `FAIL` and `UNKNOWN` as three states, so "could not read" never shows as "fine".
- **Gain.** The owner sees that the server or the Mac is down without opening a browser. It covers
  the case where nothing runs to raise C1 or C2.
- **Cost and risk.** Medium.
  - The watcher must be its own process. An alert that lives in the server cannot report that the
    server died.
  - `/status` is on the cheap lock-free lane (`PHOTO_LANE_EXACT`), so one read per minute is safe.
    Do not read `/inventory`.
  - A Mac that sleeps or is off looks dead. HA needs a quiet-hours or "Mac asleep" rule. Without
    it, this alert cries wolf.
  - HA sensors for banchi are a second place that states what is in the store. Keep the digest to
    counts, with no card names, SKUs or photos.
- **Touches.** D176, the primary checkout syncs (the watcher belongs to the primary checkout only,
  like `make launch-agent`). D43, the port follows the store (the watcher reads this checkout's
  port from `server/ports.py`, never a fixed number). D88, SQLite and one transaction per write (the
  watcher reads `/status` only, never the store file).

### C4. A small HA dashboard card for the same digest

- **What.** One HA card with the C3 numbers: server up, review queue, unsent copies, last price
  refresh.
- **Reuses.** `home` dashboards and the home app's System page ("Needs attention" row).
- **Gain.** A glance at the phone or a wall tablet. Low by itself.
- **Cost and risk.** Small once C3 exists, and pointless before. Risk: two screens say the same
  thing (banchi's Home and HA). Banchi's Home stays the source of truth.
- **Touches.** D27, session state is device-local (HA must not become a store of card state).

### C5. Rig and dispenser state on HA

- **What.** Show "dispenser connected", "dealing" and "cards this sitting" in HA.
- **Reuses.** The same digest path as C3.
- **Gain.** Low. The owner is at the Mac when the rig runs, and the Capture screen already shows it.
- **Cost and risk.** Medium to high. The dispenser state lives in the browser (`app/src/dealer.ts`,
  Web Bluetooth). To send it, the browser would post to the capture server, which would store a new
  fact. D316 says "Nothing is stored" about dealing. A phone-visible "dealing" flag could also
  invite a remote start, which is not wanted.
- **Touches.** D316, a Capture button starts and stops the dispenser. D19, arming is an act.
- **Recommendation.** Do not build until C2 and C3 have run for a while and the owner names a need.

### C6. Rig firmware updates through HA (ESPHome)

- **What.** Use the ESPHome add-on already on the HA Green to update the dispenser's ESP32.
- **Reuses.** ESPHome OTA, which the HA Green already hosts.
- **Gain.** Unknown. The dispenser advertises an OTA-style Bluetooth name. Its firmware has its
  own `OTA:` and `WIFI:` commands, which `docs/specs/dispenser.md` forbids banchi to send.
- **Cost and risk.** High. ESPHome would replace the firmware and its Bluetooth protocol. Banchi's
  command allow list (`MOTOR:START`, `MOTOR:STOP`) depends on that protocol. I did not read the
  dispenser firmware repo, so I cannot say if ESPHome can speak it. That is unmeasured.
- **Touches.** D316, a Capture button starts and stops the dispenser (the allow list).
- **Recommendation.** Defer. Read the firmware repo first.

### C7. HA-driven updates of the banchi Mac app

- **What.** HA, or a script like `deploy-degen.sh`, would pull main and restart banchi.
- **Gain.** Close to none. The primary checkout already fast-forwards itself from `origin/main`.
  The supervisor then adopts the new code (D176). Deploys already go by PR.
- **Cost and risk.** High. See section 4. **Not recommended.**
- **Worth keeping.** The `ios-adblock` private-clone guard (real directory, own git root, expected
  origin) fits if banchi ever adds a second automated clone. It is not needed now.

## 3. Open questions for the owner

1. **Which channel for failures?**
   - A: Mac notification only (C1).
   - B: Mac notification, plus HA push to the phone (C1 and C2).
   - C: B, plus a heartbeat (C1, C2 and C3).
   - Recommendation: A now, then B. C only if the Mac is often unattended.
2. **How should banchi send to HA?**
   - A: an HA webhook (secret id, one automation).
   - B: the HA REST API with a long-lived token named for banchi.
   - Recommendation: A. A leaked webhook can only fire one automation. A leaked token controls HA.
3. **Where may the secret live?**
   - A: a mode-600 file under `~/.banchi`, outside every checkout.
   - B: the macOS keychain.
   - Recommendation: A, as `home` does. It matches the machine state banchi already keeps there.
4. **What may HA see?**
   - A: counts and times only.
   - B: counts, times and box names.
   - Recommendation: A. A card name or a code is a store fact or a bearer instrument. HA has its
     own backups and add-ons.
5. **Quiet rule for a sleeping Mac.**
   - A: heartbeat alerts only between set hours.
   - B: alert only if the Mac was last seen awake.
   - C: no heartbeat alerts (skip C3).
   - Recommendation: C unless the Mac runs unattended. Then B.
6. **Who owns the HA side?** Each HA change needs the owner's word. A restart needs a check with
   the other sessions that use HA (the `home` rules).
   - A: the `home` repo holds the automation as a record, and banchi holds only the sender.
   - B: banchi holds both.
   - Recommendation: A (one home per capability).

## 4. What not to do

- **Do not host banchi as an HA add-on (the degen pattern).** Banchi needs the Mac camera, Chrome
  Web Bluetooth and a local store. An add-on has none of these. `degen` can move because it is a
  server and a client.
- **Do not let HA poll the capture server, or open it to the LAN.** The server has no auth. A burst
  of clients can wedge it (`REQUEST_SLOTS`, `PHOTO_SLOTS`). Push outbound instead.
- **Do not let HA or any remote trigger update, restart or stop banchi.** The primary checkout
  syncs from `origin/main` already (D176). A remote restart can bounce the server mid-sitting.
  CLAUDE.md says the capture server is not yours to restart. Main moves by PR (D42). The `home`
  records show a restart that stranded a config entry. Banchi has more state in flight.
- **Do not send the full HA token to banchi.** Use a webhook (C2).
- **Do not put card data, photos, SKUs or code strings in HA.** HA backups are manual. The add-on
  cannot exclude its data share. A code is a bearer instrument.
- **Do not call HA from the browser.** The front end talks to the capture server only. D316 is the
  one exception, and it is for the dispenser.
- **Do not alert on every event.** Send one digest per sitting for review items. A guard that cries
  wolf is ignored, and then it is spent.
- **Do not trust an alert before it fires once.** Show each new alert red on a forced fault. The
  `home` records flag the disk alert as unproven for this reason.
- **Do not add the sender to the server's request path.** HA can be down for minutes. Run a send in
  the separate watcher, with a short timeout and no retry loop.
- **Do not build any of this before the owner names it.** Everything above is a proposal.
