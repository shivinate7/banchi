## DEBT-slab-add-refusal-hidden — a Card Ladder failure on Add hides its plain sentence

**The Add sheet titles `cardladder_failed` and `cardladder_unreadable` with the screen's generic line.** `Slabs.tsx` words only the codes in `SAID`. For any other code the title is "That slab could not be added.", and the server's sentence sits behind "What the server said".

- **Result:** a Card Ladder 502 on Add, a normal event, shows the owner a generic line. The plain reason ("Card Ladder could not be read just now.") needs a second press to see.
- **Not fixed because** the third review round found it, and the lane had used its three rounds.
- **Closes when** both codes join `SAID` with their own sentences (neither names a key), and a case in `app/tests/slabs.spec.ts` shows the sentence as the title, red on the old screen.
- **Points to** D196 (no user-visible string may name a decision) and the My Slabs spec 4.9 (a refusal shows its sentence in the sheet).

**Outcome at risk.** The owner sees that an add failed but not why, and may retry a call that Card Ladder will refuse again.
