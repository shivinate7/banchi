# Capture

The path of the `capture` screen, from its view to the server.

## Open the screen

1. `app/src/CaptureScreen.tsx` — Photograph each card of a box as it feeds, with section dividers and an undo stack.
2. `app/src/PositionLabel.tsx` — ONE rendering of `pipeline/join.py:Position.label` for every OWNER site.
3. `app/src/usePoll.ts` — ONE POLLING PRIMITIVE, WHERE FIVE HAND-ROLLED TIMERS USED TO STAND (D207).
4. `app/src/setHint.ts` — WHETHER A TYPED SET HINT NAMES A REAL SET, ANSWERED AT THE RIG.
5. `app/src/trigger.ts` — The trigger seam: whatever fires a capture, behind one interface.
6. `app/src/motion.ts` — Gate C's auto-capture: a pure MotionMachine (settle, novelty, card presence, deferring refractory) under a thin DOM sampler that feeds it one `64x36` luma grid per decoded frame.
7. `app/src/trace.ts` — D19's Tier-`1` tuning instrument: records every frame's (t, d, dBase, luma) plus the watch-region pixels at each gate verdict and once a second, and downloads the armed session as one self-describing JSON from the HUD.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
