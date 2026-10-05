# Dispenser button

Governed by D316 (a Capture button starts and stops the dispenser). Built: yes.

## What the owner gets

One control under the Capture shutter. **Connect** links the tcg-dealer dispenser. **Start** deals
cards one at a time until the hopper is empty or the owner presses **Stop**. Motion photographs each
card as today. Nothing about the trigger changes.

## The link (from tcg-dealer `PROTOCOL.md` and `start.html`)

- Web Bluetooth. Advertised name `ESP_OTA_GATTS`.
- Service `7e8a1e10-1234-4bcd-8aef-1234567890ab`. Command characteristic (write) `7e8a1e11-…`,
  reply characteristic (notify) `7e8a1e12-…`, same suffix. Lowercase in the API.
- Allowed payloads: `MOTOR:START` and `MOTOR:STOP`, UTF-8, no terminator. One constant holds the list.
  Never `MOTOR:START:<n>` (it changed the card length and broke ejection until a power cycle),
  `WIFI:`, `OTA:` or `0x01`.
- Connect: `requestDevice({filters:[{name},{services:[SVC]}], optionalServices:[SVC]})` is the first
  await in the click handler. The device is kept in module memory, so a second Connect in the same
  page load skips the chooser. Then connect, get the service, subscribe to replies, listen for
  `gattserverdisconnected`.

## The loop

One START ejects one card, then `MOTOR:COMPLETE` arrives after about 0.42 s. A burst of STARTs drops
cards. So the loop is: START, wait for COMPLETE and for the card's photo to be taken, pause `DEAL_GAP_MS`,
repeat. The next card is dealt when the photo is taken (frame grabbed), not when the save returns. Saving
finishes in the background. The dealer never deals on a timer alone, and never before the last dealt
card's photo is taken.

- `DEAL_GAP_MS = 50`. It is one exported constant.
- COMPLETE: count one card. The next START needs COMPLETE and the card's photo taken, in either order,
  then `DEAL_GAP_MS`. `dealer.photoTaken(save)` is the photo: Capture calls it where the frame is grabbed,
  with a closure that posts the already-encoded frame. It calls `save` at once. Extra photos for one card
  let one card through. A photo while not dealing runs `save` once and counts for nothing.
- At most one photo is unsaved: a START waits while an earlier card's save is out.
- A save that rejects is retried once with the same bytes. A second failure stops the dealer, sends STOP
  and says "Stopped: a photo was not saved." No card is lost silently.
- No photo within `SAVE_WAIT_MS` (3000, exported) after COMPLETE: stop, send STOP, and say "Stopped: no
  photo came after the last card. Check the tray." Stop cancels the wait.
- `createDealer({ onMark })` reports `photo-taken`, `save-answered` and `start-sent` with the card number.
  Capture feeds them to `MotionTrace.mark`, so a downloaded trace carries `marks` and the photo-to-START
  gap reads off the file.
- `MOTOR:END`: the hopper is empty. Stop, not an error.
- `MOTOR:ERROR`, `MOTOR:CLEARED`, `MOTOR:CARDLEN_SET`, any other reply, 5 s with no reply, or a lost
  link: stop. One `finish(reason)` ends every path.

## When it may deal

- Start is enabled only when motion is armed with a baseline and capture is possible: the Capture
  button's own blockers (a box picked, a game loaded and verified, the camera ready, no halt). Otherwise
  the reason shows, e.g. "Pick a box first", "Turn on motion first". With no `navigator.bluetooth`:
  "Needs Chrome on the Mac".
- A Start pressed while the last START awaits its COMPLETE waits for it, or 1 s after Stop. Every stop
  cancels a waiting Start.
- Stop sends `MOTOR:STOP` after any write in flight. A card already moving still lands.
- Dealing stops when: Capture unmounts; the tab is hidden; capture halts (`halt !== null`); the
  dropped count rises since Start; the camera stops being ready; motion is switched off.
- Nothing persists. Dealing never resumes on its own (D19, arming is an act).

## Screen

- One full-width kit `Button` `size="lg"` under the shutter in `.capture-controls`. Labels:
  "Connect dispenser", "Connecting", "Start dispenser", "Stop dispenser".
- One reserved status line in a kit `Slot`, always present (D313, nothing moves). Lines:
  "Not connected", "Connected", "Dealing, 12 cards", "Stopped after 12 cards", "Out of cards after 12",
  "Lost the dispenser. Check it is on, then connect again.", "No answer. Check it is on and nothing
  else is using it.", "Stopped: a card was not photographed. Resume captures first.", "Stopped: no photo came after the last card. Check the tray.", "The dispenser
  reported a fault. Check it, then connect again.", "Bluetooth is off. Turn it on, then connect again.",
  "Could not connect. Check it is on, then try again." A canceled chooser says nothing. The line is
  muted small text with two lines reserved.
- While `state` is `dealing`, the Recent rail (`footer.capture-undo`) stays live but draws only the newest `DEALING_RAIL_TILES` (15) and says so in one reserved line. When dealing ends, including a no-photo stop or an error, older tiles load in below, with no animation and no scroll change. `aside.capture-last` stays live. Undo and its keys read the live whole-sitting stack, and a tile names its card.
- Tokens only. No hotkey. No storage key.

## Code

- `app/src/dealer.ts`: local Web Bluetooth types (no `@types` package), `createDealer()` (link and
  loop, no React) and `useDealer({halted, dropped, ready, armed})` returning
  `{state, cards, said, connect, start, stop}`. `state` is `idle | connecting | connected | dealing |
  stopped | error`.
- `app/src/CaptureScreen.tsx`: one hook call and the control. No `server.ts` function, no server change.

## Tests

- Unit (`app/tests/unit/`): a fake `navigator.bluetooth` that replays tcg-dealer's recorded sequences
  (paced loop 10 of 10, COMPLETE after 420 ms; empty hopper, 3 then END after 540 ms). It rejects any
  write that is not the next expected one, and any payload off the allow list. Synthetic cases,
  labeled so: ERROR, silence, disconnect mid-loop, Stop while a START is pending (Stop is the next
  write, no START after it). Never replay `bad_card_length.json`.
- Browser: like `motion-live.spec.ts`, the same fake via an init script. Arm motion, Connect, Start.
  No box is picked, so the first fire drops and dealing must stop. Also: disabled with its reason in
  Manual; "Needs Chrome" with `navigator.bluetooth` removed.
- Hardware, manual: load 10 cards, compare cards dealt with the HUD's `fires`.

## Deferred

Dock-app Bluetooth (unverified; the owner uses a Chrome tab). Remembering the dispenser across page
loads. A "dealt minus fires over 3" stop. A 200-card cap.
