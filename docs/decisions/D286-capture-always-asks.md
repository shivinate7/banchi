## D286 — Capture always asks on a fresh device, and Home's tile is the thing that lied

**The owner's ruling, 2026-09-24, amends D142.** The owner asked for more explanation first.
Then the owner ruled:

```
D142 Capture box: ALWAYS ASK on a fresh device ("No box yet"). Home's tile is relabelled to
what it shows (the newest box).
```

The finding this closes is UX-011, from the 2026-09-23 UX review round. Home's hero and the
Capture tile said "Box 4, Mixed Singles". Pressing "Start capturing" landed on Capture with
`No box yet. Pick one`. That gave one cold start two answers to "which box am I filling". It
cost a second press.

### The fix is not in Capture, because Capture was never wrong

D142 already settled what a fresh device shows. `storedCaptureSetup()`
(`app/src/deviceMemory.ts:storedCaptureSetup`) reads `banchi.capture.setup` from
`localStorage`. A device that never wrote that key gets `NO_CAPTURE_SETUP` back: `box: null`,
every claim empty. `CaptureScreen.tsx` never seeds a box from anywhere else. No call reads
Home's "newest box". No call reads `banchi.box-recency`'s top entry. No call reads the store's
own highest-numbered box and offers it as a starting pick. The Box row opens `No box yet. Pick
one` on a fresh device today. That is D142's own restore-and-fall-back-to-nothing rule,
working exactly as specified. Reading the two screens side by side made this look like a
Capture defect. It is a Home defect. Home's own sentence claimed a box that Capture had no
memory of, and Capture never promised to pick that box up.

**So this entry does not change `CaptureScreen.tsx`'s restore logic.** D142's fallback rule
already produces the right behaviour. This entry states it as settled policy instead:

1. **A fresh device always shows `No box yet. Pick one` on Capture.** That is a device with no
   `banchi.capture.setup` written yet. No box is inferred from the store, from another screen,
   or from `banchi.box-recency`. The operator names the box every first time.
2. **A returning device keeps D142's own restore.** It is checked against the live store. It
   falls back to no selection on a deleted, sealed or reallocated box (D153), exactly as D142
   already argues.
3. **Home's tile is not Capture's promise.** Home's hero draws a fact about the store. That
   fact is the newest box on record, or the box with the most cards, whichever Home settles
   on. It is not a fact about this device's capture memory. The tile's own sentence must say
   so, and must not imply a hand-off Capture does not make. Relabelling that tile is the home
   lane's own work, in its own decision entry, not this one's.

### What protects the premise this repeals

Nothing is repealed. D142's own argument still holds: session state is device-local, and a
restored setting must be checked rather than trusted. That argument is exactly why Capture
cannot pick up Home's box. Home's figure carries no device-local claim behind it. Drawing it
into the Box field would be the unchecked, cross-device guess D142 was built to end. UX-011's
own direction named a real second option: "Capture arrives with that box picked, or the tile
says what it shows". The owner's ruling picks the second one. Capture has no way to verify
Home's figure against this device's own history.

### What is built

Nothing changes in `CaptureScreen.tsx` or `app/src/deviceMemory.ts` for this entry. The
behaviour it settles already matches the code. The box list stays ordered by the hand
(`banchi.box-recency`, D142's own rule), most recent first, unchanged.
