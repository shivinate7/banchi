## D316 — A Capture button starts and stops the dispenser

**The Capture screen has a Connect, then Start, control for the tcg-dealer dispenser. It deals one card per command over Web Bluetooth, from the browser. Motion still takes every photo. Nothing about the trigger changes.**

The owner ruled the scope: a button that turns the dispenser on, and nothing of tcg-dealer's own plan. The design is `docs/specs/dispenser.md`.

**The rule.**
- **Two presses.** Connect picks and links the dispenser. Start deals. Stop is the same button while dealing.
- **One home.** `app/src/dealer.ts` holds the link, the command allow list (`MOTOR:START`, `MOTOR:STOP`) and the paced loop. No other file talks to the dispenser.
- **One card per command.** The loop sends START, waits for `MOTOR:COMPLETE`, pauses, and repeats. A dead page or a lost link ends dealing within one card.
- **It deals only while motion can photograph.** The control is off until motion is armed and the camera is ready. Any capture failure stops it.
- **The Recent rail shows the newest 15 while dealing.** `DEALING_RAIL_TILES` names the 15 once (three rows of five). One reserved line says so ("Showing the newest 15 while the dispenser deals."). When dealing ends for any reason, older tiles load in below them, which stay put, with no animation. The Last capture panel stays live. Undo data and keys cover the whole sitting (D164). "Dealing" is `useDealer`'s state, never a second source (D313, nothing moves unless the person moved it).
- **Nothing is stored.** Chrome holds the pairing grant. "Dealing" never persists and never resumes on its own (D19, arming is an act).
- **The screen word is "dispenser"**, the owner's word.

**What it bends.** CLAUDE.md "over the capture server and nothing else" gains one clause for this link. `motion-trigger.md` section 5 names this as the one feeder control.

**Deferred.** The dock app's Bluetooth is unverified. The owner deals from a Chrome tab on localhost. A WiFi bridge is not planned.

**What would reopen this.** A real run shows the pace misses photos, or the owner wants the dock app.
