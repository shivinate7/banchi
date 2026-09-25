## D266 — The phone drawer has no fixed foot, and its items join the one scrolling list

**The owner's ruling, 2026-09-23.** On a phone, the drawer's footer items join the scrolling
list. The footer goes. This amends D204 (the phone drawer's nav scrolls in the space above its
foot).

The record of the review is `docs/reviews/ux-2026-09-23/`. The finding is UX-037 (ACC-05).

### The premise that no longer holds

D204 proved that Codes can be tapped after a scroll, at 13 phone heights and in two engines. It
did not ask whether a person knows to scroll.

### The evidence

The access lens opened the drawer at 390x844. The nav list is 542px tall over a scroll height of
629px. Under "Library" only "Inventory" shows, then a divider and "Cards to pull". Graveyard and
Codes sit under the foot. The only sign is a 32px fade. So the Library group looks complete with
one row, and two screens seem not to exist on a phone. At 360x740, Codes hides the same way.

### What D204 protected, and what protects it now

D204 protects one outcome: every row of the drawer can be reached, for any row count. With no
fixed foot, nothing covers the end of the list. The foot's items (Cards to pull, the theme
toggle and the server line) become rows at the end of the one list. A person who scrolls sees
every row pass, and no row sits under a fixed block.

The review recommended a visible cue or a shorter foot. The owner chose to remove the foot.

### What goes with the foot

D204's `--bn-drawer-foot-h` token describes the foot's fixed height. It has no subject once the
foot goes, so it goes too, in the same change. The spec that D204 added reads a row's center
with `elementFromPoint`. It stays, and it now also asserts that the drawer draws no fixed foot.

### What is built

BUILT by the shell lane of the 2026-09-23 overhaul, beside the palette changes in
D276 (amends D95, the shell is a rail, a palette and a reference sheet). The drawer is
the kit's `Sheet` now, so it is modal and holds focus (UX-014). Its last group holds Cards to
pull, the theme toggle and the server line. `--bn-drawer-foot-h` is gone. D204's tap sweep in
`app/tests/phone.spec.ts` is still skipped (DEBT29). A new case in that file asserts that the
drawer draws no fixed foot. It also asserts that every screen in the drawer shows without a
scroll at 390x844.
