# Divider close-out: notes

The idea: when a divider passes, the rig judges the section just fed while its cards are still in the output tray. Silent when clean; a chime, photo tiles with tray positions and a held feeder when something needs fixing; anything not fixed is carried to the next session.

**Click through.** Open `divider-closeout.html`. The State bar reaches every state of the plan's section 2, and each has a link: `#state=feeding|clean|to-fix|double-feed|missing-divider|carried|box-summary`. Add `&t=dark` or `&t=light` (none follows the system), `&tray=top`, `&stop=off`, `&labels=off`, `&hide=edge,stack,spoken,ticks,carry`. Buttons inside each verdict work (Fixed, Re-feed, Carry, Split). "Choices on this page" removes one choice per untick.

**Where it lives.** `#/capture`, the `capture` screen (`app/src/CaptureScreen.tsx`). The verdict covers the stage and last-capture columns in one grid cell, the way today's halt overlay does. Nearest spec: `docs/specs/capture-app.md` 5.6 (New section), with 5.4 (Undo) and `docs/specs/subbox-capture.md` 2 (the physical model).

**Choices** (Gain / Lose / Pick)
1. Edge colour: a 14px frame in `--bn-stage-ok|warn|danger`, theme-invariant like the stage. Gain: read from the side, in both themes. Lose: loud on a small screen. Pick: yes.
2. Tray picture: one bar per card, top of tray first, with the flags marked. Gain: the count-down is seen, not done in the head. Lose: one more thing to draw. Pick: yes.
3. Spoken count after the chime. Gain: no look needed. Lose: the plan's first version drops it. Pick: keep as an option.
4. Section list marks (green, amber, red edge bar plus count). Gain: one line per clean section, no other change. Lose: none found. Pick: yes.
5. Carry button on each tile. Gain: a stuck card never blocks the run. Lose: an easy way out of a fix. Pick: yes.
6. Position as an ordinal from the top ("31st"), with the box label (`Long Box Ember, Section 7, Card 28`) muted under it, per `PositionLabel`. Gain: the tray is counted, not looked up. Pick: yes.
7. Carried flags do not colour the edge; they open the next session as a list. Gain: the edge stays a live signal. Pick: yes.
8. A double feed pauses mid-section (red, low buzz), not at the divider. The plan says both (sections 2 and 3). Pick: pause at once. Owner grant: yes.

**Departs from**
- Departs from: capture-app 5.6, `S` is a press that writes the divider — here the rig detects a physical divider passing. Owner grant: yes.
- Departs from: capture-app 5.4 and D10, undo reaches only the newest card and a mid-box delete lives on `#/inventory` — Re-feed replaces the photo of a card mid-section. Owner grant: yes.
- Departs from: DESIGN.md "What this is not", no step between the operator and the next card — a held feeder waits for every flag. Owner grant: yes.
- Departs from: capture-app 2.2, the app does not drive the feeder — "the feeder stops on its own" needs a new control path to the feeder.
- Departs from the plan's wording: "Box 3" becomes a box name, because D259 never draws a box number. Card 31 became Card 28 so that it sits 31st from the top.

**Owner questions (from the plan)**
1. What decides where a divider goes: one per set, a fixed count, or a box layout?
2. In the tray, is the first card fed at the bottom or on top, and will you pull a card mid-session? The "First card fed lands" toggle redraws every position.
3. Should an open flag stop the feeder, or only chime? The "An open flag" toggle shows both.

**Verdicts.** 1440 light (`divider-closeout-1440-light.png`): pass, the verdict, tray and tiles fit with no overflow. 820 dark (`divider-closeout-820-dark.png`): pass, the rail cards move above and the tiles stack in one column. Also looked at: double feed 1440 dark, missing divider 820 light, carried 1440 light, end of box 820 dark, all pass. Feeding and clean were not shot.
