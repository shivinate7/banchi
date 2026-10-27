# Retire to master set: design notes

Lane kind: informed. Mockup: `inventory-retire.html`. Spec: `docs/specs/master-set.md`, sections
2 and 5. The frame draws my pick. The Options panel under it draws each alternative, and each has
a control that hides it. The owed list this receipt points to is `pricing-owed.html`.

Deep links: `#s=picker`, `#s=offer`, `#s=sending`, `#s=sent`, `#s=failed`, `#s=matches`,
`#s=onway`, `#s=nosession`. Add `&w=820` and `&t=dark` (or `abyssal-bloom`, `carnival-midway`).
With no `t`, the page follows `prefers-color-scheme`. `&h=R1,K1` hides options.

Components: the reasons are `Inventory.RetirePanel`, which reads `cardState.RETIRE_REASONS`. The
receipt is the toast that `Inventory.remember` raises through `kit/toast.toast`, drawn by
`toast.Toaster`. The walk behind them is a plain stand-in, not `BoxBrowse`.

Owner rulings this page draws: the take-off press is on the retire receipt at once; a take-off not
pressed, or one that failed, goes on the owed list on Pricing's send card; a failed take-off offers
Try again; Review's Close dialog is unchanged.

1. **The fifth reason, "Master set", said "Kept for your own collection."** It spans the last row
   of the two-column grid, so the four reasons keep their places. Gain: a hand that knows the
   four still finds them. Pick: yes.
2. **Master set first (option R1).** Gain: the new reason is the first thing read. Loss: the four
   move down one row. Pick: no.
3. **Master set in a plain half row (option R2).** Loss: a half-empty last row reads unfinished.
   Pick: no.
4. **Today's first reason reads "Removed", not "Pulled".** `RETIRE_REASONS` labels `pulled` as
   "Removed". The mockup draws "Removed". The spec says "Pulled".
5. **The take-off lives in the retire toast, and the toast still needs a kit change.** The fade
   needs no change now: an unpressed take-off goes on the owed list, so the toast fades after 20
   seconds as today. Four changes stay. (a) A toast holds a second action; it holds one today.
   (b) That press does not dismiss the toast; `Toaster` dismisses on every action press today,
   which would take Undo away with it. (c) The toast's line changes in place after the press;
   `toast()` returns an id and has no update. (d) The drain waits while the press runs, and the
   action button has a busy state. Without (d) a press at second 19 loses its answer at the press;
   the owed list still holds the result.
6. **No kit change (option K1).** The retire receipt keeps Undo, and the offer is a second status
   toast with the press as its one action. Gain: no kit change. Loss: two toasts for one retire;
   the press dismisses its own toast, so the answer is a third toast, and the stack moves. Pick:
   no.
7. **Every state of the line sits in one grid cell; only the current one is visible.** So the
   receipt's box is its tallest state's from the first paint, and Undo never moves (D313, nothing
   moves unless the person moved it). The headless check measured the toast and Undo boxes across
   all seven receipt states, at 1440 and 820, in light and dark: no change.
8. **Busy keeps the press's box.** The words go clear and a ring turns in their place, as
   `.bn-btn[data-busy]` does. The press reads TCGplayer first, then sends.
9. **The press reads "Take It Off TCGplayer".** DESIGN.md R5 puts a button in Title Case. The
   same words are on the owed line on Pricing, so the act has one name on both screens.
10. **The offer says where the take-off goes if it is left:** "Leave it, and Pricing keeps it on
    a list." Failed, on its way and no sign-in each say Pricing holds it.
11. **Sent names the card, the copies and the answer, and says what Undo does now:** "TCGplayer
    accepted: 1 copy of Mimikyu ex is off. Undo lists it again at your next send." (spec section 5:
    undo does not put the listing back).
12. **Failed offers "Try again"** (owner's ruling), in the kit `Retry` words. Nothing went live,
    and the retirement stands.
13. **Nothing to take off (`#s=matches`) and on its way (`#s=onway`)** are the spec's two other
    answers. Neither has a press.
14. **No TCGplayer sign-in (`#s=nosession`): one sentence, no press, as the spec says.** The
    sentence says the take-off waits on Pricing. Prose that names a place is not a control
    (ux-no-dead-end), so option P1 adds an "Open Pricing" press where the take-off waits there.
    Gain: a control that leads on. Loss: a third press in a small toast. Pick: no; the owed list
    is one nav press away.
15. **At 820** the toast's presses and the reason buttons measured 40 px or more, with the
    coarse-pointer heights the frame states.
