# Cards to Pull, buyer-first: design notes

Designer kind: directed. Direction: buyer-first, one envelope at a time, each buyer's cards gathered
before the next. Mockup: `docs/design/pull-directed-1.html`. Every name, card and figure in it is
made up.

Deep links: `#s=list`, `#s=pull`, `#s=pulled`, `#s=sold`, `#s=two`, `#s=full`, `#s=short`,
`#s=done`, `#s=empty`, `#s=failed`. Add `&w=820` for the iPad frame, `&t=dark` for dark, `&l=0` to
hide the Today and New labels. Options: `order=oldest|fewest`, `copies=folded|listed`,
`also=shown|off`, `short=leave|aside`, and `h=<variant>` hides one.

The device list for this repo reads `unknown`, so the frames are the brief's sizes: 1440 x 900 and
820 x 1180, light and dark.

## Measured in the frame (headless Chromium, both themes)

| State | Width | Pull | Mark it sold | Next | Photo |
|---|---|---|---|---|---|
| pull, pulled, sold | 1440 | 538 to 602 | 626 to 690 | 714 to 778 | 328 x 458 |
| two copies | 1440 | 582 to 646 | 670 to 734 | 758 to 822 | 328 x 458 |
| pull, pulled, sold | 820 | 767 to 831 | 855 to 919 | 943 to 1007 | 328 x 458 |
| two copies | 820 | 839 to 903 | 927 to 991 | 1015 to 1079 | 328 x 458 |

Every step is above the fold at both sizes (900 and 1180). The smallest text node in the screen is
20px. No button, field or summary is under 44 x 44. Contrast is unmeasured; the screen's text is
`--bn-ink` or `--bn-ink-2` only.

## Choices

1. **One envelope at a time, one buyer per envelope.** The day is a list of envelopes. One opens,
   its cards are pulled in box order, it is closed, then the next. Gain: each buyer's cards are
   gathered in one place, so nothing is sorted at the end and no card lands in the wrong envelope.
   An envelope is a finish line he can see. Loss: a box is opened once per buyer that needs it. In
   the sample, WB1 R3 opens for Dana and again for Sam, and WB2 R1 for Dana and again for Priya.
   The overview prints the boxes each envelope opens, so the owner can weigh it. Pick: yes, it is
   the direction.
   Departs from: `docs/specs/order-walk-plan.md` section 1 rule 3 (walk across orders) and the
   solver's packing across orders (sections 5 and 6). `Fulfillment.tsx`'s `owedFrom` folds
   `plan.stops[].takes[]` to one entry per card, not per buyer. Owner grant: yes.

2. **A press records against the open envelope's buyer.** Gain: what is in the envelope is what
   the order says. Loss: `pickOrderFor`'s rule (the open order closest to done takes the copy)
   no longer decides; the envelope does. D212 still holds: no copy is claimed before the press.
   Pick: yes. Departs from: `docs/specs/order-walk-plan.md` section 8, "How a row closes". Owner
   grant: yes.

3. **One place at a time, and how many to pull.** Each card says "Pick 2 of 3" (the Orders walk's
   own figure, section 8 and D279) when there is a choice, and "Pick 1" when the store holds exactly
   what is wanted. A card with a choice adds "Any copy will do." in words, in place of the walk's
   "(either)", which reads wrong over three copies. Two or more wanted adds "This is copy 1 of 2
   for this envelope." One Pull per copy wanted, not one per copy on hand. Gain: fixes the audit's
   first pain point. Loss: he sees one place, not all three, until he asks. D97 holds: the screen
   says any copy will do, and every other place is one press away (item 4). Pick: yes.
   Departs from: `Fulfillment.tsx` `actionFor`, which gives each on-hand copy its own Pull with no
   count, and section 8's "Pick N of M" form when M equals N. Owner grant: yes.

4. **Option, the other copies: "Folded under one line" or "Listed under the steps"** (focus
   `#ff-other`). Folded keeps the screen calm; listed shows the choice without a press. Each row
   has "Take this one instead". Both sit below the steps, so neither moves Pull. Pick: folded.

5. **Option, a later envelope's card in the same box: "Offer it while the box is open" or "One
   envelope only"** (focus `#ff-also`). The offer names the card and the buyer, and one press pulls
   it now for that envelope. A line over the place says "Put this one in Sam Ortiz's envelope, not
   Dana's.", the sale says "Put it in Sam's envelope.", and a "Back to Dana Whitlock's envelope"
   step follows. Gain: it buys back most of item 1's cost. Loss: it bends
   buyer-first, and he holds two envelopes' cards at once. Pick: offer it. Owner grant: yes, as it
   changes item 1.

6. **Option, which envelope first: "Oldest order first" or "Fewest boxes first"** (focus
   `#ff-envelopes`). Oldest follows `pickOrderFor`'s tie rule (the order placed longest ago).
   Fewest boxes puts quick envelopes first and a short envelope last. Pick: oldest first.

7. **"176 unlocated" leaves his screen.** A card that is not in any box shows only where it blocks
   something: on its envelope's row ("1 not in the boxes"), on its tile, and in its own panel,
   which says "This card is not in the boxes" and gives a control that leads on. Pooled copies are
   never his to pull (D24). Gain: no warning he cannot act on. Loss: the store-wide figure is gone
   from this screen; it stays on the owner's Orders header (section 14). Departs from:
   `Fulfillment.tsx`'s `today`, the `ff-today-warn` line. Owner grant: yes.

8. **Option, an envelope that waits for a card: "Leave it in its place" or "Set it aside"** (focus
   `#ff-short-act`). Leave keeps every row where it was and marks it "Waiting for a card". Set aside
   moves it to a "Waiting for a card" group at the foot of the list, the one row that leaves the
   open list. Pick: leave it in its place (ux-order-holds-still).

9. **One unit: cards.** The bar reads "9 cards to pull" and "4 envelopes to pack". A card here is
   one copy, so it reconciles with section 14's `owed = pick + short + elsewhere` (here: pick). Home,
   Orders and Pricing count the same work in other words today (the audit's third pain point). That
   change is outside this screen and outside a designer's scope. Owner grant: yes.

10. **A third reserved spot for "Next".** The action block reserves 64 + 24 + 64 + 24 + 64 from the
    start: Pull, then Mark it sold below it, then "Next card", "Next copy of", "Back to" or "Finish
    this envelope" below that. Nothing moves on a press, and each step starts below where the one
    before it ended, so a double tap lands on words. The screen never moves on by itself (UN-6).
    Departs from: `docs/DESIGN.md`, "The action block reserves 152px". Owner grant: yes.

11. **Undo beside the press, not in a sheet.** After Mark it sold, Pull's own spot shows "Pulled."
    with Undo, and the sale's spot says "Sold. Put it in Dana's envelope." It names the buyer every
    time, because he puts the card in by hand. Undo has no clock (UN-5) and
    `U` still works. Gain: the answer shows at the press (ux-answer-at-press), and nothing floats over
    the next step. Loss: no dismissible receipt panel. Departs from: `Fulfillment.tsx`'s `sheet`
    (`ff-sheet`, `ff-receipt`). Owner grant: yes.

12. **The ship-to name leads the envelope.** "Ship to" over the name, then the order number, as
    `Fulfillment.tsx`'s `OrderEyebrow` and `orderLabel` do (D193: packing reads the name on the
    parcel). Kept.

13. **An envelope is a finish line.** When its last card is in: "All 4 cards are in Dana Whitlock's
    envelope. Close it and put it with the envelopes to post." and one press, "Next envelope: Sam
    Ortiz". That press sits above where "Finish this envelope" was, so a double tap cannot reach it.
    New. Pick: yes.

14. **Day done.** "3 envelopes are packed. 1 waits for a card.", the waiting envelope with what it
    needs and a control to open it, then "Pulled today" with Undo on the newest only. Kept from
    `Fulfillment.tsx`'s `done` list; the envelope sentence is new.

15. **Kept as today.** The empty day's sentence (`ff-today-none`), now with one "Find a card"
    control. The floating "These cards may have changed" notice with "Try again" (R19). Search as
    the second way in (`SearchField`); its results here are a sketch. The photo opens bigger on a
    press. Positions renumber after a pull in the same box (D58): Ember Warden reads Card 10, not 11,
    once Glass Moth at Card 4 is out.

16. **1440 shows the envelope list beside the open envelope; 820 shows "All envelopes" and
    "Envelope 1 of 4" above it.** The day overview (`#s=list`) is the same at both sizes. Pick: yes.

## Critique pass (impeccable critique, single context)

The run was single-context: this session exposes no sub-agent tool. The snapshot step was not run.

- Fixed: "Pick 1 of 1" on most cards was noise. It reads "Pick 1" when there is no choice (item 3).
- Fixed: "(either)" over three copies was wrong. It is the sentence "Any copy will do." (item 3).
- Fixed: the overview had two names, "See all" at 1440 and "All envelopes" at 820. It is "All
  envelopes" at both sizes.
- Fixed: "It is in the envelope" claimed an act he has not done yet, and during a detour it did not
  name the right buyer. The sale and the detour line name the buyer (items 5 and 11).
- Fixed: the detector flagged two repeating stripes (the short pip's hatch and the photo
  stand-in's text lines). Both are plain fills now.
- Not fixed: the detector flags Inter as an overused face. Inter is the repo's `--bn-font-ui`, so
  this is a false alarm for this mockup.
- Not fixed: the reserved action block leaves an empty band under Pull until the steps fill it.
  It is the cost of the double-tap guard (item 10).
- Open questions are in the report's Input Needed.
