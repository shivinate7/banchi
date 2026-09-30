# Capture app

The browser app that photographs each card into a box and section, and the screens around it.
It is the front end of the capture server (`docs/specs/capture-server.md`). Code comments cite
the section numbers below, so they do not change.

---

## STATUS

Built and validated in part. Gate B ran 53 real cards end to end. It covered the capture
screen at feeder pace and the review queue against a real run. The pull preview showed a
stored photo at its correct physical location. The gates corpus's `GateB` record holds the
measurements.

Still unexercised:

- The Fulfillment view against a real order. `make design-check` asserts its floors. Only a
  non-technical person filling a real order can test D5's (two personas) rule: if a flow needs
  explaining twice, redesign it.
- The review screen's price bands against a mixed-value lot. The one real queue held 16 cards
  of one reason code, all priced $0.04 to $0.40.

**A built screen is not a wired one.** A screen can typecheck, lint and pass `make harness`
while nothing routes to it. `make design-check` asserts that a view is on screen before it
measures anything. It is not in `make check`, because it starts a browser and a dev server.

**Reason codes.** Fifteen exist: six ladder reasons (`pipeline/variant.py`'s `LADDER_REASONS`)
and nine routing reasons (`pipeline/routing.py`'s `ROUTING_REASONS`). `docs/DESIGN.md` requires
each on screen as a human label with the machine string small beneath. Two cannot reach the
queue:

- `no_market_data` is a routing destination of its own. `pipeline/join.py` writes a queue
  entry only for `routing.MAIN` and `routing.PARKED`. A card with a blank or $0.00 market cell
  is priced by hand on `#/pricing` (D9, threshold and floor, and D86, one file for the store).
- `card_not_detected` has no producer in `pipeline/`, `cli/` or `identify/`. The `reason
  emissions` row of `make docs-audit` excuses it by name in `UNEMITTED_REASONS`. That exemption
  goes stale the day something emits it. The screen still labels it.

## 0. Scope

Two passes, built and reviewed separately:

- **7a, the Gate B path.** The app shell, the capture screen, undo, the pull preview and the
  undo route. The chain is capture, server save, batch script, join, CSV, import, pull preview.
- **7b.** The review queue, the Fulfillment view, the inventory SKU views, mark-sold, and three
  more server routes.

Gate B predicted close to zero review items at T1's holdout accuracy. It got 16 of 53. T1
cannot warn about this, because it is blind to finish detection (`docs/GATES.md`).

## 2. Settled amendments

### 2.1 — The app has no CSV import

`emit` writes `pushed`. `reconcile` moves `pushed` to `staged` off the Export From Staged.
`join` moves `staged` to `live` off the Filtered Export. Every transition belongs to a command.
The app reads state and never sets it. This is not a deferral, because an import feature would
have nothing left to do. T3 guards against silently skipped cards.

### 2.2 — The feeder exists

Cards are fed onto a tray and land in the same spot each time. Auto-capture is therefore a
matter of tuning a trigger against an existing rhythm (D19, auto-capture fires live).

### 2.3 — The rig's camera

The camera is a Sony RX100 VII or A7C over HDMI into an Elgato Cam Link 4K. D13 (the Mac holds
the one truth) owns the consequences. The browser sees a plain UVC webcam. So the device picker
is required, and `facingMode` is never used.

### 2.4 — Undo is the exception to the no-dialog rule

`docs/DESIGN.md` refuses a confirm on a reversible action. Undo deletes the record, the
sidecar and the photo (D10, inventory model). Even so, it takes one tap and no dialog. The
deleted photo is of a card still in the operator's hand, so the remedy for a wrong undo is to
photograph the card again. That loss is bounded in a way a wrong pull or sale is not.

Rejected: a confirm only on a second consecutive undo. If a held key ever walks backwards
through good cards, try that first.

## 3. undo-route

`DELETE /inventory/<box>/<index>`. `docs/specs/undo.md` owns the whole behavior. This screen
depends on these rules:

- It deletes and never tombstones. Nothing in the response hints at a third state between
  captured and absent.
- It removes only the newest card in the box. `next_index` is a high-water mark, so a mid-box
  delete would leave a gap that reads like a sale's permanent gap. The refusal names the
  position that is undoable.
- It removes only a `captured` card (`UNDOABLE_STATES`), and only inside the open sitting.
  An older card refuses `capture_built_on`. An identified card has entered inventory. Its remedies are re-shoot, retire and the mid-box remove. `undo_too_late` names
  all three.
- It runs in one `Store.write()`. It removes the record, the queue entries and the paid answer.
  It then removes the photo before the sidecar. A stranded sidecar costs nothing. A stranded
  photo is a paid Batch request for a card that no longer exists.
- Repeated calls walk backwards, one card each.

## 4. server-client

`app/src/server.ts` owns every call to the capture server. The failure behavior in §5.5 is then
one decision, applied once.

The base URL is derived per checkout. `vite.config.ts` injects this checkout's own capture port
(D43, the port follows the store), and `VITE_CAPTURE_SERVER` outranks it. Reads allow any origin. Writes need an allowed origin
(`docs/specs/capture-server.md` §6.4). There is no auth and no TLS. Do not add a login screen.

The app shows the server's own message. That message says what happened and what to do next.
The app must not paraphrase it into something less actionable.

## 5. capture-screen

The owner spends hours on this screen. `docs/map.py`'s `CaptureScreen.tsx` entry and the
component's own comments carry the current control layout. The SESSION panel is at the top, the
claims are in the middle, and the shutter and undo are at the foot.

### 5.1 — Layout

The live camera is on the left. The photo just taken is on the right, large enough to show a
blur or a finger on the card. Catching a bad photo at once is the reason undo exists. Three
weeks later, the same card cannot be identified, and nobody can correct its position without
handling the box.

The position label of the card just taken sits beside its photo. The renderer that
`pipeline/join.py` uses builds it. The server returns it, and the app never composes a second
one.

### 5.2 — Box selection

The box field is one free-text control. It searches number and name together. It reads
`GET /boxes` on mount and on open. `POST /boxes` creates a box by name and allocates the
lowest free number inside the lock (`next_box_number`), so no number can be mistyped. A
duplicate name refuses `name_taken`. The creation row is drawn last, so Enter on the top row
cannot make a junk box. A box has no seal and no capacity (D299). New-box entry has no
confirmation.

Box, set hint and finish are client state, resent on every capture. The server holds no notion
of a current box, so two devices can work without a session.

### 5.3 — Set hint and finish

Both are always visible and changeable in one action.

The finish toggle is a claim and not a hint. D3 (variant ladder) treats it as trusted. A
mis-toggled stack therefore goes to review and is never silently corrected.

The set hint breaks a tie when a collector number matches rows in two sets. Without it, the
card reviews as `set_ambiguous` (T3). The field is free text over a real vocabulary
(`GET /tcg/sets`, D65). A `datalist` suggests from it and a `select` never constrains it,
because the rig may not be refused. The field also says whether the typed text names one of the
sets. That fact decides whether the export scopes to a set or widens to the whole game.

### 5.4 — Undo

Undo takes one tap, has no dialog, and is always visible. It shows what it will delete before
you press it: the position and the thumbnail. That is the difference between an undo you aim
and one you fire hopefully.

The stack is the whole sitting's captures, newest first, across drawers. It draws in a strip
that scrolls (D164, the undo stack is the sitting). Row N undoes N cards: that card and every
card captured after it. It walks the undo route N times, because undo reaches only the newest
card in a box. Reverse-chronological order over the sitting is also reverse-chronological
within each drawer, so every target is its box's newest when the walk reaches it. A mid-box
delete is a different operation (D10) and stays on `#/inventory`.

The row draws the count of cards it removes. That count is the guard. The no-dialog rule is
argued for one card within reach of the hand that fed it. A press that deletes five must
therefore make the five visible. `U` and the trigger seam mean exactly one card, the top row.

A refused walk stops at the refusal and says how far it got. With no shots in the sitting (for
example after a reload), the stack is one unlabeled row. It aims at the server's newest card
in the box.

An open Section or Box list shows in front of the Recent strip and scrolls. It stays out of
flow (D118, a press changes what is on screen). When an edge would sit under a bar, opening the
list scrolls the viewport.

### 5.5 — Failure behavior

A failed capture stops the run and says so loudly. A feeder that keeps feeding past a quiet
failure leaves physical cards with no record and no photo. Nothing afterwards says which cards.
Queue-and-continue is rejected. Photos held in the browser make a second place where inventory
lives, and D13 allows one.

Every capture sends a `capture_id`. A response can be lost between commit and client. Resending
the same id then returns the original card with `created` false and burns no index. That is a
retry of one request and not a queue.

### 5.6 — New section

`S` puts one divider in front of the next card, as the physical divider goes into the box. It
is an act and not a field. It writes to the store on the press, like the shutter and undo, and
it shares their trigger primitive.

- It sends no index. `POST /boxes/<box>/sections` takes an empty body, and the store reads its
  high-water mark inside the lock. A client-computed index would race the feeder's cadence.
- A capture can name a section. `S` can name the section it goes after. Each names it by
  divider key and never by index (D300). `docs/specs/subbox-capture.md` has the wire contract.
- A second press with nothing captured between refuses `section_empty` (D10). The screen draws
  a quiet sentence and never a halt, because a refused divider changed nothing. No note beside
  a control prints a reason code (D196, no user-visible string may name a decision). Only a
  halt's "What the server said" does.
- `U` takes the divider back out while it is the last one and no card is behind it (UN-15,
  `DELETE /boxes/<box>/sections?div=<key>`). After that, the remedy is the dividers editor on
  `#/inventory`. A `resectioned` history line carries the layout it moved from.
- There is no dialog. A confirm on a screen shot at feeder pace is what `docs/DESIGN.md`
  refuses.

### 5.7 — Layout and control rules

- An empty-section `S` is a normal no-op. The button stays enabled. The server is the judge,
  and a stale client count must not block a good press. `capture-claims.spec.ts` asserts the
  error state.
- There is no "Open the camera first" line under Capture. The disabled button carries the
  reason as its accessible description.
- The closed Rarity row draws bars only. Picked names are screen-reader text.
- Clear (RIG) opens the kit's `ConfirmSheet`. Esc cancels and Enter confirms. The toast Undo
  stays.
- A Recent tile caption names the box through `boxTitle` and the card's number from the
  rendered label. No `B<n> #<n>` key is drawn or spoken (D259).
- On desktop and tablet, the viewfinder panel hugs its portrait frame. Its width derives from
  its height (`--cap-stage-w`) and not from a `1fr` track. The last-capture column hugs its
  9:16 photo (`--cap-last-w`), and the freed width goes to the rail. On tablet the receipt sits
  beside the photo. `capture-width.spec.ts` measures no unpainted band at 1440 and 820.
- On a phone (390, 375, 430), the panel hugs the frame. It sits beside the last capture in one
  row, so the shutter stays above the tab bar. The receipt scrolls inside its panel.
- Layout changes never touch capture, the motion trigger or rotation. §5.1's order holds.

## 6. trigger-seam

Whatever fires a capture is one module (`app/src/trigger.ts`) with one job. The capture screen
does not know which implementation is behind it. A manual key and button sit behind the same
seam as the motion state machine (`app/src/motion.ts`, `docs/specs/motion-trigger.md`, D19).
Video frame extraction is rejected, and D19 records why.

The key is shown on screen. An hour at this screen is a keyboard, and the visible hint is what
the no-dialog decision looks like in markup.

### 6.1 — The camera

Nothing touches the camera until someone asks. `useCamera`'s `started` flag gates asking, and
`retry()` is both the opener and the retry. `revealLabels` calls `getUserMedia` only to un-blank
the device labels. An eager mount would therefore raise a permission prompt on every visit that
is not for shooting. An automated browser can never clear that prompt.

Three states must not be collapsed:

- `started === false`: nobody has asked yet. `CameraPicker` draws a plain "Open the camera".
- `missing`: the remembered camera is not connected.
- `error`: the camera was asked for and failed.

A failure reported for a device nobody requested makes a working rig look broken. The flag
gates asking and not requiring. This is never a headless mode. A session that proceeds without
a camera photographs nothing and does not notice.

The picker lists video inputs and selects by `deviceId`, never by `facingMode` (D13). §8 has the
lint rule. The app remembers the chosen device and re-selects it silently. A visible control
changes it. If the remembered device is absent, the app says so and asks. It never falls back
to another camera, because that photographs a box through the wrong lens.

### 6.2 — Why the camera is not driven directly

Tethered capture over USB was rejected. `identify/images.py` downscales every photo to 1568px
on the long edge. Resolution still matters through the crop. `geometry/crop.py` upscales the
collector-number corner to at least 600px, and it can only enlarge pixels that were really
captured. T1's recorded misses are numerator misreads. Roughly, on a 63x88mm card:

| capture | card long edge | number corner |
|---|---|---|
| framed to the 1568px target | 1568px | ~100px |
| 4K, card filling the frame | ~3400px | ~230px |
| full-resolution still | ~5500px | ~370px |

Tethering buys about 1.6x the linear detail of a tightly framed 4K frame. Framing closes most of
that gap for free. Tethering also costs:

- Latency the feeder will not forgive. A PTP shutter-and-download is commonly one to three
  seconds a frame. A video frame is one frame.
- A native dependency and a new failure surface. It also inverts the flow: the Mac would ask for
  a photo and would not receive bytes.
- Refocus on every shot. A video stream holds focus on a fixed tray.

`CLAUDE.md` rules out Sony's Imaging Edge Desktop: no manual third-party UI step inside the
autonomous pipeline.

The Cam Link path requires these settings:

- Frame the card to fill the field. This is the largest accuracy lever at capture time.
- Request the native resolution explicitly. A browser default of 640x480 falls under the 1568px
  target.
- Encode at high JPEG quality. The pipeline re-encodes later.
- Turn clean HDMI output on at the camera. Otherwise the camera's overlays are burned into
  every card.
- Remove the pillarbox. Compare the camera's HDMI resolution and aspect with what the Cam Link
  receives. A black bar wastes the frame.
- Use manual exposure: a fast shutter, a stopped-down aperture and a fixed ISO. A knock then
  does not blur, and a card proud of the tray keeps its corner.
- Lock manual focus at tray distance. The tray does not move.
- Disable auto power off. A sleeping body drops the HDMI signal while the Cam Link stays
  enumerated. The screen halts the run when the track dies, but the stoppage is avoidable.
- Glare on the number corner is unrecoverable at any resolution. The number corner under
  raking light is unmeasured.

## 7. pull-preview

The pull preview is look-only, with no actions. It shows the photo and the position label from
`join.Position.label`. `GET /photo/<box>/<position>` serves the photo (D6). The view is
`app/src/BoxBrowse.tsx`, reached through `#/inventory` (D31, one owner-side view).

## 8. eslint

`app/eslint.config.js` bans `facingMode` in any camera constraint (v1 bug 3). It also bans
`split(",")` CSV parsing (v1 bug 2). `docs/decisions/`'s v1 bug table names lint as the guard
for both.

## 9. What the app may not build

- No identification, pricing, joining or CSV work of any kind. The four commands own all of it,
  and the app reads state and never sets it.
- No second store in the browser.
- No auth, no login, no TLS.
- No renumbering, compaction or gap-filling, ever.

## 11. What is left open

What the Fulfiller's device points at. The base URL is configurable (§4), so the question stays
answerable later.
