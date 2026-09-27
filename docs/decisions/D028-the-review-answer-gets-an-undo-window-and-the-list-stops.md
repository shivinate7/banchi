## D28 — The review answer gets an undo window, and the list stops moving under it

**The review answer gets a twenty-second undo, and the candidate list stops moving between cards.** The review queue's irreversible action had fewer guards than the product's reversible one, which is backwards.

Pressing a digit writes a SKU and a condition onto a real card. `store/queues.py:Queue.upsert` refuses to re-queue a position a human has cleared — deliberately, so an answer outlives the question — so there was no undo, no confirm and no acknowledgement. Meanwhile mark-sold, which is reversible, got a photo to confirm against, a two-step control, a twenty-second undo and a pre-checked `restores_to`.

**That sentence described the owner's screen until 2026-08-30 and now describes the Fulfiller's** (D57). Kept as written because it is the MEASUREMENT this entry was built from, and nothing about the repair depends on it still being current — but a later reader would otherwise go looking for a photo-confirm on `#/inventory` and find none. D57 finished the correction from the other end: this entry gave the irreversible action its undo, and that one took the redundant press off the reversible write, so the sale is one press with `Undo` in the row and on the receipt. `#/fulfillment` keeps all four.

**Two fixes, because there are two halves.**

1. **The list stops moving.** The photo has no reserved dimensions, so answering one card can shift the candidate rows by most of a screen — under a finger already travelling toward a number. Reserve the photo's height and prefetch the next card's image. This removes the cause of most mis-taps and costs no keystroke.
2. **A twenty-second undo**, the shape the product already ships. `Queue.upsert`'s refusal stands for everything outside that window; the window is a hole punched in it on purpose, not a softening of the rule.

**This reopens `docs/DESIGN.md`'s no-acknowledgement rule for this one screen, and the grounds are in the rule itself.** That rule is justified by *undo covers the mistake* — and on this screen undo did not exist, so the rule leaned on something that was not there. Fixing the premise is the honest repair; adding a confirm dialog would have doubled the keystrokes on the screen the owner spends the most hours in, which is what the rule was written to prevent.

**Rejected: requiring a modifier or an Enter to confirm.** Declined for the reason above — one key per card is the property worth keeping.

### Amended 2026-09-25: the answer's undo has no clock

The owner's ruling of 2026-09-25, verbatim: "Switch all five (Recommended)". The "twenty-second undo" no longer limits anything. The receipt may still fade. The undo lasts until the answer is built on. That is when its SKU is in a written listing file or holds a listing hold (`undo_too_late`). `docs/specs/undo.md` section 11 is the plan.
