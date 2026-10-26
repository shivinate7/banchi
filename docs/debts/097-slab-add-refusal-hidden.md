## DEBT97 — fixed: a Card Ladder failure on Add shows its plain sentence

**The Add sheet titles `cardladder_failed` and `cardladder_unreadable` with their own sentences.** Both codes are in `SAID` in `Slabs.tsx`, and Undo's reasons (`UNDO_WHY`) reuse the same two constants. The owner reads why an add failed with no second press.

- **Fixed.** The cases in `app/tests/slabs.spec.ts` that cite this entry now pass. A test-author swaps their cite, and then this file is deleted.
- **Points to** D196 (no user-visible string may name a decision) and the My Slabs spec 4.9 (a refusal shows its sentence in the sheet).
