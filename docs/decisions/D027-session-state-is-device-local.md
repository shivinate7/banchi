## D27 — Session state is device-local

**The capture screen's scratch state may live in `sessionStorage`.** `CLAUDE.md`'s ban on browser storage is about inventory. D13 puts one truth on the Mac, so two devices cannot disagree about where a card is. That rule was never about the capture screen's scratch state.

Box number, set hint, finish claim, rarity claim and the in-flight `capture_id` are device-local. They mean nothing anywhere else. They were `useState`, so a reload lost all of them. The in-flight id matters most. A reload during a halt makes a lost-response ambiguity permanently unresolvable. D10's high-water mark then hands the burned position to the next physical card.

**`sessionStorage`, never `localStorage`.** The permitted keys are named below, so a lint rule can enforce the boundary. Session scope is the point. A new tab is a new session, and nothing about a shift survives closing the browser.

### The roster

The whole set, as the app spells it:

```
banchi.session.captureId  banchi.run-scope  banchi.session.homeDeck
```

`app/src/CaptureScreen.tsx`'s `SESSION_KEYS` declares the first. `app/src/runHandoff.ts` declares the second. `app/src/Home.tsx` declares the third. `make docs-audit`'s `storage keys` row holds this fence against the keys the app writes, in both directions. The row reads the fence only. Prose around it is not checked.

### Settings that left this carve-out

D142 moved six capture settings (`box`, `setHint`, `finish`, `game`, `rarityClaim`, `product`) into `app/src/deviceMemory.ts`'s `banchi.capture.setup`. A shift ends when the operator stops feeding cards, not when a tab closes. Those settings persist across tabs.

### Key naming

Every browser-storage key this app writes is `banchi.*`. There is no frozen set to remember. The `pkmnscan.` prefix was not kept. D94 covers a storage key like every other name. Old values are abandoned in place. No migration runs, and no read-time fallback exists, because a fallback can never safely be deleted.

Cost of the rename, named. Two `localStorage` keys were lost on the rig: the remembered 4K capture card and the quarter turn. Seven `sessionStorage` keys were lost too, but only in a tab left open across a deploy. The exception is `captureId`. A capture in flight when the new build loads could burn a position. D10's high-water mark would then hand that position to the next card. `run-scope` is the cheapest of the ten. Reading nothing is its safe answer, since its purpose is to stop a press paying for more than the operator ticked.

### A handoff, not a memory

`banchi.run-scope` carries a box and the cards ticked in it from `#/inventory` to `#/runs` (D39). The pipeline moved to a route of its own, and the one mass-select in the product did not. It qualifies on this entry's own test: device-local, meaningless elsewhere, and not a fact about where a card is. It is `sessionStorage` because a tick list that outlived the browser would filter a spend button that nobody alive remembered setting.

It differs from the other keys in what a reload means. Those exist so a reload does not lose the shift. This one exists so a reload does not silently widen what the next press pays for. It is cleared deliberately on three routes rather than expiring: the operator's control, picking a box, and arriving from `#/inventory` with nothing ticked. `app/src/runHandoff.ts` is the one module that reads or writes it.

### The Home deck

`banchi.session.homeDeck` records that the deck's full entry already played in this sitting, so a reload inside the sitting does not replay it (`docs/specs/motion.md`, P3). It names no card, box or position. A new sitting should play the deck again, which is why it is session scope and not device scope.

`useCamera.ts` argues this carve-out informally for the device id and the rotation chip. This entry generalizes that and makes it checkable.

**Trigger mode is not covered.** D19 keeps arming an act. An armed machine that survives a reload is the automatic behavior that entry refuses.
