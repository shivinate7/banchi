## D-pull-list-is-a-pick-count — Cards to pull asks for a count of a card, and shows where every copy is

**The owner's ruling, 2026-09-23, in the UX review interview.** Cards to pull is built wrong
by outcome. Copies are fungible. When an order wants 2 of card X and the store holds 14, the
screen says "pick 2 of X". It then shows where every copy is. It never shows 2 copies that
the app chose.

The record of the review is `docs/reviews/ux-2026-09-23/`. The finding is UX-001, the one S1
on the Fulfiller's screen. The locating lens found the same state again as LOC-02.

### The premise that no longer holds

D212 (every copy is fungible, so no order claims one) took the claim out of the resolution.
It measured 84 picks on `GET /orders` on a seeded store. Cards to pull still builds its list
from those picks. `Fulfillment.tsx` keeps an order group only when the group holds a card,
and it makes the cards from `resolution.orders[].lines[].picks`.

### The evidence

The visual lens read the live wire, GET only, on 2026-09-23. `GET /orders` carried 0 picks for
71 open orders and 216 wanted copies. On the demo it carried 0 picks for 7 open orders. The
Orders screen reads its picks from `POST /orders/picks`. Cards to pull reads `GET /orders`.
So the Fulfiller reads "No orders are waiting for a card right now" while Home says copies
are owed. Which change moved the picks off `GET /orders` is unmeasured.

### What D212 protected, and what protects it now

D212 protects one outcome: no order holds a copy hostage, so a sale can record against any
owing order. This entry keeps that outcome and makes the screen agree with it. A line on
Cards to pull is a count of a card, not a list of chosen copies. Under the count, the screen
draws every copy of that card on hand, with its place. The hand picks any of them. The sale
records against an owing order, as D212 already rules.

The count comes from the order ledger (wanted less recorded), not from picks. So the screen
cannot say that nothing waits while an order is open. A line whose card has no copy on hand
says so by name.

**The screen must never say "nothing is waiting" while any order is open.**

### The same screen, three smaller rulings

The owner also ruled on the Fulfiller's screen, and called it "not a big rock". These keep D5
(two personas) and D68 (a departed label names the record). They amend neither.

1. A departed card never shows on the Fulfiller's list or card page. LOC-01 found a sold card
   offered with "Pull this card" and "It sits between". That sends a person to a slot that
   holds a different card. D58 (a card's number counts the cards, not the slots) exists to
   stop exactly that.
2. The shortcut list drops the `/` row, because no `/` binding exists on that screen.
3. The `?` key opens the reference sheet on that screen, as the list says it does.

### What is built, and who builds it

NOT BUILT. The fulfillment lane of the 2026-09-23 overhaul builds it (UX-001, UX-013, UX-089,
UX-101). `docs/specs/ux-overhaul-2026-09-23.md` holds the lane plan.

### What protects the outcome once built

A browser spec on `#/fulfillment` over a seeded store with open orders. It asserts that the
count of owed lines equals the count Home draws. It asserts that no line names a departed card.
It asserts that the empty sentence does not draw while an order is open. The spec must fail on
today's tree first. The repo trusts a guard only once it has gone red on its defect.
