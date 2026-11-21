# p-rig

**Direction 1**
**Name:** Expected-order watch
**The idea:** The cards come in already sorted by set and number, so the rig knows roughly what card should come next. A cheap local read of the set symbol and collector number corner, done before the paid identify step, compares each card with that expected order. It flags a gap, a repeat, a reversal or a card back the moment it passes. The owner hears the problem instead of finding it in the batch an hour later.
**Who it helps:** The owner while feeding, and the identify budget, since fewer bad frames go to the paid read.
**Why now:** At 1,300 cards an hour, one unnoticed double-feed shifts every later position by one. A tone at card 412 costs nothing to act on. Finding the same fault at card 1,300 means re-checking hundreds of slots.
**Rough shape:**
- A soft tick for each card in order. A distinct tone for "skipped one", "same card twice" and "face down".
- The rig pauses itself on a double-feed or a card back and shows the last three frames side by side.
- One tap: "re-feed from here", or "that's right, it's a playset".
**Risk:** Repeated copies and mixed bulk break the order guess, so the cue must learn the run it is in, or it cries wolf.

**Direction 2**
**Name:** Section close-out at each divider
**The idea:** Each divider becomes a checkpoint. When the rig sees one, it shows a one-line verdict for the section just fed, such as "Section 7: 58 cards, order clean, 2 need a look". The owner fixes the two while those cards are still in the output tray. Each divider also resets the position count, so a jam can only throw off positions inside one section.
**Who it helps:** The owner, and later the Fulfiller, whose pick list depends on positions being right.
**Why now:** Cleaning up is cheap while the stack is in hand and expensive once it is back in a box with 700 others. With 9 to 22 dividers per box, each fix-up window is short.
**Rough shape:**
- A large, glanceable verdict card at each divider: green, or a count of items to fix.
- The flagged cards show as photos with their tray position: "4th and 31st from the top".
- The owner can carry an unresolved flag forward, so the next session opens with it.
**Risk:** Owners will learn to skip a verdict that interrupts too often, so it must stay silent when the section is clean.

**Direction 3**
**Name:** Jam replay and self-healing re-feed
**The idea:** The rig keeps a short rolling buffer of recent frames and sensor events. After a jam, or when the owner looks back from a distraction, it shows exactly where the clean record ends and which physical card to re-feed from. It recognises re-fed cards by their photo and does not count them twice. It also tracks the owner's fault rate as the hour goes on, and suggests a break at the next divider when that rate climbs.
**Who it helps:** The owner at minute 50, when attention drops.
**Why now:** Jams and look-aways are where an hour of capture turns into a second hour of cleanup. A single recovery screen means the owner never has to rebuild a stack from memory.
**Rough shape:**
- After a jam: a filmstrip with the last trusted card outlined and "re-feed starting with this one".
- Re-fed cards that are already recorded show a "matched, not re-counted" chip.
- A gentle note, "faults doubled in the last 10 minutes, the next divider is a good stop", never a hard stop.
**Risk:** Matching a re-fed card to a near-identical common card by photo alone can merge two real copies into one.

**Bet:** Section close-out first, because it limits every other failure, including jams, double-feeds and fatigue, to one section that is still in the owner's hand. Expected-order watch and jam replay then make each close-out shorter.
