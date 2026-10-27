# Retire to master set: design notes

Lane kind: informed. Mockup: `inventory-retire.html`. Spec: `docs/specs/master-set.md`, sections
2 and 5. The frame draws my pick. The Options panel under it draws each alternative, and each has
a control that hides it.

Deep links: `#s=picker`, `#s=offer`, `#s=sending`, `#s=sent`, `#s=failed`, `#s=matches`,
`#s=onway`, `#s=nosession`. Add `&w=820` and `&t=dark` (or `abyssal-bloom`, `carnival-midway`).
With no `t`, the page follows `prefers-color-scheme`.

Components: the reasons are `Inventory.RetirePanel`, which reads `cardState.RETIRE_REASONS`. The
receipt is the toast that `Inventory.remember` raises through `kit/toast.toast`, drawn by
`toast.Toaster`. The walk behind them is a plain stand-in, not `BoxBrowse`.

1. **The fifth reason, "Master set", said "Kept for your own collection."** It spans the last row
   of the two-column grid, so the four reasons keep their places. Gain: a hand that knows the
   four still finds them. Pick: yes.
2. **Master set first (option R1).** Gain: the new reason is the first thing read. Loss: the four
   move down one row. Pick: no.
3. **Master set in a plain half row (option R2).** Loss: a half-empty last row reads unfinished.
   Pick: no.
4. **Today's first reason reads "Removed", not "Pulled".** `RETIRE_REASONS` labels `pulled` as
   "Removed". The mockup draws "Removed". The spec and the brief say "Pulled".
5. **The take-off lives in the retire toast (my pick).** The toast keeps Undo where it is today.
   The take-off is a line under the body: a sentence and the press, then the answer in the same
   place (ux-answer-at-press). Gain: the answer shows where the press was. Loss: two changes to
   the kit toast. A toast holds one action today, and a receipt drains in 20 seconds, so the press
   could fade before the person reads it and the answer could land after the toast is gone. The
   toast must take a second press and stay until the take-off settles or the person dismisses it.
   **Owner grant: yes.**
6. **The take-off on the retired copy's row (option T1).** Today a confirmed retired row draws no
   control. Gain: no kit change. Loss: the row goes when the walk leaves the card, and so does the
   answer.
7. **The take-off in a notice above the walk (option T2).** Gain: it stays until the next write.
   Loss: a second receipt for one press, apart from the toast that says "Retired".
8. **Every state of the line sits in one grid cell; only the current one is visible.** So the
   receipt's box is its tallest state's from the first paint, and Undo never moves (D313, nothing
   moves unless the person moved it). The headless check measured the toast and Undo boxes across
   all seven receipt states.
9. **Busy keeps the press's box.** The words go clear and a ring turns in their place, as
   `.bn-btn[data-busy]` does. The press reads TCGplayer first, then sends.
10. **Sent names the card, the copies and the answer, and says what Undo does now:** "TCGplayer
    accepted: 1 copy of Mimikyu ex is off. Undo lists it again at your next send." (spec section 5:
    undo does not put the listing back).
11. **Failed offers "Try again".** Nothing went live, and the retirement stands. The spec does not
    say whether the press comes back. Gain: no dead end (ux-no-dead-end). **Owner grant: yes.**
12. **Nothing to take off (`#s=matches`) and on its way (`#s=onway`)** are the spec's two other
    answers: the live read found no extra copy, and one take-off per card is outstanding. Neither
    has a press.
13. **No TCGplayer sign-in (`#s=nosession`): one sentence, no press, as the spec says.** The house
    rule ux-no-dead-end asks for a control that leads on. The app has no sign-in control, and once
    the toast goes no screen can take the copy off later: D100 (never delete to lower a price)
    builds no screen control for a phantom. The listing then stays above what is on hand.
    **Owner grant: yes.**
14. **Review's Close dialog has its own reason list** (`ReviewQueue`). The spec does not say
    whether it gains Master set. Not drawn.
15. **At 820** the toast's presses and the reason buttons measured 40 px or more, with the
    coarse-pointer heights the frame states.
