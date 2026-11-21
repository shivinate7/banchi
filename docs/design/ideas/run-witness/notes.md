# Run witness: sort order checks identification (proposal, informed designer)

Cards feed already sorted by set and number. So each card's place in the run is a free second witness beside the paid read.
After a batch, each section is one strip, and a card that fits its run never reaches a person.

**Click through.** Open `run-witness.html` from disk. The bar sets State, Version, Width and Theme, and each one is a link too.
States: `#state=normal|empty|playset|printings|mixed|break|failure|rig`. The rig adds `&break=start|fits|skip|repeat|facedown|setchange|fifth`.
Add `&v=vote` (first version: every card read) or `&v=seams` (the default: paid reads only at seams), `&w=820`, `&t=light|dark`, `&tags=off` and `&bare=1`. `break` is an extra state that this mockup adds to the plan's six.

**Where it lives.** You reach it from Review (`review`). It is a new band, Last Batch by Section, above today's question card. The live warning is on Capture (`capture`), over the stage.
Nearest spec: `docs/specs/identify-engine-pick.md` (what it never reads). Nearest screens: Review and its runs sheet.
Departs from: the hard rule "never guess an identification", and D76 (a set hint is evidence only about its own card; the engine "never borrows a hint from a neighbor"). A predicted card is named from its neighbours. **Owner grant: yes.** This is plan question 1.
Departs from: Capture's stage, which shows no expected next card. A break now pauses the feed and sounds a tone.

**Choices (Gain / Lose / Pick)**
1. One ruler per section, one tick per card in feed order. Gain: you see a break, a playset or a set change before you read any words. Lose: 40 px per strip, and a key to learn once. Pick: yes. Option `text-strip` draws it without the ruler.
2. A read and a prediction never look alike: a solid tick against a hollow one, in the key, the tooltip and the summary. Gain: the departure above stays visible. Lose: none. Pick: yes.
3. A strip that fits carries no pill, and the band says "All is well." (house rule ux-all-is-well). Gain: only the sections that need you stand out. Lose: none. Pick: yes.
4. A break opens under its own strip: the card between its two neighbours, and three one-key answers. Gain: the answer is where you pressed. Lose: the strip grows. Pick: yes.
5. A skip is a soft note with no tone, and the feed goes on. Gain: stock seldom holds every number, so a hard skip would cry wolf. Lose: a card really dropped is caught only after the batch. Pick: soft. **Owner grant: yes** (the plan says the tone sounds on a skip).
6. Repeat, face-down, set changed and a fifth copy each pause the feed and sound the tone. Option `rig-no-pause` only flags them. Gain: the stack gets fixed while it is in your hand. Lose: the rig waits on you. Pick: pause.
7. A paid read after a failure goes through a press that shows the count and the cost ("Read 43 Cards"). It never queues money by itself. Gain: the one-press money gate stays as it is. Lose: one more press. Pick: yes.
8. The Version toggle draws the plan's bet (every card read, with the run as a second vote) beside the full plan. Gain: you see what question 1 costs either way. Lose: two sets of copy. Pick: show both.
9. "Anchor" and "seam" stay off the screen: "first card read" and a dashed "a new set starts here" divider replace them. Gain: plain words. Lose: the screen and the plan use different words. Pick: yes.

**Owner questions (from the plan)**
1. Does a card predicted from its run, with a passing spot-check, count as identified? Or must every card get a paid read or a person?
2. Within one number, is the order of your sorted stock fixed (normal print before reverse holo, the copies of a playset together)?
3. What does one wrong card cost you: a refund, feedback, the Fulfiller's time? The answer sets the spot-check rate and the price above which a card is always read.

**Verdicts.** 1440 light (`run-witness-1440-light.png`, failure state): pass. The key, the notice and four strips fit above the fold, and nothing overflows.
820 dark (`run-witness-820-dark.png`, break state): pass. Each strip stacks into summary then ruler, the break's three answers fit on one row, and nothing scrolls sideways.
