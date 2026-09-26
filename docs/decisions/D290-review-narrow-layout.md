## D290 — the photo reserve shrinks below the rail breakpoint

**Amends D28's first half.** D28 reserves the photo's height so answering one card does not shift the candidate rows. It fixed the SHIFT. It did not fix the SIZE the reserve claims below the rail breakpoint (Q2, ~640px). There, the reserve pushed the first answer row off the first viewport entirely.

**The finding, S2, round two (UX-203, UX-204).** At 720 and 390 the photograph filled the first viewport on its own. The answer rows started below the fold at 720 and 390, and near it at 820. After an answer at 390, the receipt with Undo also landed below the fold. A write with no visible confirmation is D171's silent write, on the one screen D28 built an undo window for.

**Measured**, `#/review`, a nine-card queue, headless Chromium, `getBoundingClientRect` on the first `.review-candidates li` (or `.review-actions .bn-btn`), before this entry and after:

| width | before (first row top) | after |
|------:|------------------------:|------:|
| 1440  | 358px (unaffected)      | 358px |
| 820   | 1110px                  | 812px |
| 720   | 900px (at the fold)     | 664px |
| 390   | 1001px                  | 755px |

**The fix, two parts.**

1. **`--rv-photo-h` shrinks below 899px.** It read `min(56vh, calc((100vw - 48px) * 1.7778))`. 56vh alone claimed nearly all of a phone or a narrow-desktop viewport. No answer row had drawn yet. It now reads `min(34vh, ...)` in the same rule (`app/src/ReviewQueue.css`). The width-based half is untouched. A genuinely narrow column still sizes the photo to what it can carry, exactly as D28 measured.
2. **The receipt tray is sticky at phone width.** `.review-tray` holds the receipt and the refusal notice. It now sticks above the tab bar under 768px, the same way `.review-group-bar` already does. The tray still scrolls with the card. It only stops once its own slot would carry it past the bottom edge. The twenty-second undo window D28 built now stays in view.

**A third, smaller fix rides with this one (UX-251).** The claims chip strip (`Claims`, `.review-claims`) used to return `null` on a card with no evidence chips. It rendered one or two lines on a card with some. That is a second violation of D28's "the list stops moving." The candidate rows below it moved by however many lines the chips did not need. Measured: 53px. The strip now always renders, with a one-row `min-height`. It grows past that floor on the rare card whose chips wrap to a second line. It does not reserve two rows on every card, unlike an earlier draft. That draft traded UX-251 back against UX-203/204 on the same screen.

**What this does not touch.** The rail breakpoint itself (Q2: the desktop rail should hold down to ~640px) is the shell's own file, not this screen's. `#/review` only consumes wherever that breakpoint lands. Moving it is not this entry's fix.

**UX-205, built the same round.** A different defect from the two above: a receipt that never renders, not one rendered off-screen. `remember` ran only when `canTakeBack` was true. Six of nine answers in one real session drew no receipt at all. `Receipt` gets a new `undoable` field. `remember` now runs on every write. Undo hides itself when `undoable` is false.

**UX-255, decided round two.** Five names for one closing act (Close / Close without answering / Stand down / Stood down / closed). The owner, 2026-09-25: "I think one word is better if it sounds intuitive still." **The word is "Closed."** It already named the trigger button and the dialog title. It reads naturally for both real outcomes. A card stood down is closed. A card retired is closed too. `said` is `'Closed'` for every close, whichever choice was picked. The outcome still shows, as a plain description beside it rather than a second verb: `Closed · left in place` or `Closed · retired` (`Receipt.outcome`, `.review-receipt-outcome` / `.review-session-outcome`). The panel's own two choices, "Stand down" and "Retire," keep their names. They are not the act's own name. They are what the operator is choosing between, and D37's vocabulary for the stand-down choice specifically stays. The session tally already said "closed." Nothing there changed.
