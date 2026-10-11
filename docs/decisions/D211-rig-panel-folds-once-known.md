## D211 — Rig panel folds once setup is known

`app/src/CaptureScreen.tsx`'s Game, Camera, Rotation and Trigger panel is the SESSION box. Its own comment says the panel is set at rig setup and then read. It rendered all four fields expanded on every mount, whether or not the operator had a box. A walkthrough of the screen found seven settings between opening Capture and picking a box. D142 already remembers that box across sittings.

**The fold is keyed off `restored.box`, the field `banchi.capture.setup` already carries (D142).** No new device-memory key is added. A browser with no remembered box starts with the panel open. Its fields must be visible to choose the first time. A browser that remembers a box starts folded. It shows a one-line summary (game · rotation · trigger) instead.

Picking a box for the first time in a fresh sitting folds the panel the same way. The exception: the operator has already touched the disclosure by hand this sitting. A manual re-open is never re-closed by the box pick that follows it.

**Why a derived boolean, not a seventh stored field.** `deviceMemory.ts`'s comments say "the six choices the capture screen remembers" and "ONE KEY FOR SIX VALUES, BECAUSE IT IS ONE HABIT". The document holds exactly the operator's setup and nothing else. A `rigOpen` flag records which way a disclosure was left. It is not a claim about the rig or the box. Storing it there would answer a UI-state question with the vocabulary D142 built for another one. `restored.box === null` is already read for the box field itself. The fold reuses that read.

**No-box Setup panel (B2, owner sign-off).** The stage keeps its Camera control. The Shooting group keeps the Box select. Only the repeated Camera and Box controls go, from the no-box Setup panel. Add divider stays where it is. The panel count is not a goal.

**What is NOT covered.** Whether the operator's manual open or close choice should persist across sittings is open. Today it resets to the box-based default on the next load. If it matters in practice, the owner should weigh in. Nothing here writes one. `rigTouched` is scoped to the component instance, not to storage.

### Mechanized

`app/tests/capture-claims.spec.ts`, three cases. A box-empty fixture starts the panel open (`aria-expanded="true"`, the Game row visible). A box-seeded fixture (`{box: 3, bid: 23}`) starts it folded (`aria-expanded="false"`). The Game row is ABSENT from the DOM, not merely hidden, and the summary reads "Pokémon". A press on the summary re-opens it. A keyboard shortcut (`g`) fired while the panel is folded still opens that field's own picker. So the fold never traps a shortcut behind hidden markup. `make design-check` runs them.

The manual toggle persistence is deliberately not asserted either way, since nothing here writes one.
