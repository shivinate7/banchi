## D292 — The lane order stays, a phone opens every lane folded, and the rule is said once

**The owner's ruling, 2026-09-23: keep the lane order. Collapse every lane on a phone. State the rule once, in the lane header. No reason codes.**

This amends the DISPLAY half of D61 (the shipping lane is three lanes). The router keeps its
own three lanes, their order and their reasons. What changes is how
`app/src/OrdersShipStage.tsx` draws them.

### What the 2026-09-23 review measured

- **UX-016 (LOOP-24, ACC-19).** All 331 cards drew open on every width. On a phone the Needs-a-look
  lane — the one lane that asks the owner to decide — started at y = 32,257 of a 37,150 px page.
- **UX-015 (TXT-01), UX-005 (TXT-02).** The Envelope lane's chip already said "Cards only, under
  $50", and 166 Envelope cards then each repeated `Cards only, and under $50.` beneath it, with
  the raw `cards_only` string a third time. Same shape on 112 Parcel cards for `value_at_threshold`.
  1,726 words said one fact.

### The rule, in three parts

1. **Lane order is unchanged.** Envelope, Parcel, Needs-a-look — `SHIP_LANES` in
   `OrdersHubStore.ts`, which mirrors `pipeline/shipping.py:LANES`. The owner's ruling keeps it.
   Nothing here reorders a lane by what it holds.
2. **Every lane collapses by default on a phone.** `ShipStage`'s own `usePhone()` (the same
   `(max-width: 767px)` convention `ReviewQueue.tsx`, `Pricing.tsx`, `Orders.tsx` and
   `BoxBrowse.tsx` already use) decides the `lanes` set a freshly read batch starts with: every
   lane on a wider viewport, no lane on a phone. The existing fold-and-show chip is the
   mechanism — nothing new was built for it, only its default. A lane a person opens stays open
   until they close it or read a new file. This is a starting position, not a lock.
3. **A card's own reason draws only where it differs from its lane's rule.** `LANE_OWN_REASON`
   names the one reason each of Envelope and Parcel already states in `LANE_HEAD`: `cards_only`
   and `value_at_threshold`. A card carrying that reason draws no sentence. `non_card_signal`
   (the 14 Parcel cards that reached the lane on the OTHER ground D61 names) and every
   Needs-a-look reason still draw their own sentence. The header there names no single ground,
   so each abstention still has to say which one it is. The raw reason string
   (`cards_only`, `value_at_threshold`, …) is deleted from every card (D196). It repeated the
   sentence a third time, and it was the mechanized register rule's own gap: a string in a
   `Record` lookup is data, not a JSX literal the check could see.

### What this does not change

The router (`pipeline/shipping.py`), the five reasons, the abstention itself, and the file's own
"no sort, no search, filter removes and never reorders" rules are all D61's. They are untouched.
This entry is the screen's DISPLAY of D61's answer, not a second copy of the rule that produces it.

### Built

`app/src/OrdersShipStage.tsx` (`usePhone`, `LANE_OWN_REASON`, `reasonSentenceOf`, the deleted
`.shipping-reason`), `app/src/Shipping.css`. Proved by `app/tests/shipping.spec.ts`'s phone/desktop
default-fold case and its reason-sentence case.
