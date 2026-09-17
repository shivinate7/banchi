## D211 — The Rig panel folds once the setup is already known, and stays open until it is

`app/src/CaptureScreen.tsx`'s Game/Camera/Rotation/Trigger panel — the SESSION box, "set once
when the rig is set up, then read" per this file's own comment — rendered all four fields
expanded on every mount, whether or not the operator had a box already. A walkthrough of the
screen named this: seven settings stand between opening Capture and picking a box, on a screen
D142 already built to remember that box across sittings.

**The fold is keyed off `restored.box`, the field `banchi.capture.setup` already carries (D142) — no new device-memory key.**
A browser with no remembered box starts with the panel OPEN, because the four fields have to
be visible to choose the first time; a browser that remembers one starts FOLDED, showing a
one-line summary (game · rotation · trigger) instead.
Picking a box for the first time in a fresh sitting folds the panel the same way, unless the
operator has already touched the disclosure by hand this sitting — a manual re-open is never
immediately re-closed by the box pick that follows it.

**Why a derived boolean and not a seventh stored field.** `deviceMemory.ts`'s own comments
insist on "the six choices the capture screen remembers" and "ONE KEY FOR SIX VALUES, BECAUSE
IT IS ONE HABIT" — the document's whole argument is that it holds exactly the operator's
setup and nothing else. A `rigOpen` flag is a fact about which way a disclosure was left, not
a claim about the rig or the box, and stuffing it into the same document would be answering a
UI-state question with the vocabulary D142 built for a different one. `restored.box === null`
is already read for the box field itself; the fold reuses that same read rather than adding a
second one.

**What is NOT covered by this entry.** Whether the operator's own manual open/close choice
should PERSIST across sittings (rather than resetting to the box-based default on the next
load) is left for the owner to weigh in on if it turns out to matter in practice — nothing
here writes one, and `rigTouched` is scoped to the component instance, not to storage.

### Mechanized

`app/tests/capture-claims.spec.ts`, three cases: a box-empty fixture starts the panel open
(`aria-expanded="true"`, the Game row visible); a box-seeded fixture (`{box: 3, bid: 23}`)
starts it folded (`aria-expanded="false"`, the Game row ABSENT from the DOM rather than merely
hidden, and the summary reading "Pokémon"), and a press on the summary re-opens it; and a
keyboard shortcut (`g`) fired while the panel reads folded still opens that field's own picker,
proving the fold never traps a shortcut behind hidden markup. Run by `make design-check`.

Whether the operator's own manual toggle should persist across sittings — the one open
question this entry leaves for the owner — is deliberately NOT asserted either way, since
nothing here writes one.
