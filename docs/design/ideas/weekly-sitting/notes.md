# Weekly Sitting: notes

The idea: everything that can wait goes into one weekly queue, sorted by dollars at stake per minute. Each item carries a safe default and a date. A cut line marks where the owner's time budget ends, and untouched items apply their default on its date.
Next week opens with What Defaulted, with an Undo on each line. A kind the owner always accepts is later offered autopilot.

**Click through.** Open `weekly-sitting.html`. The State bar reaches every state of the plan's section 2. Each state has a link: `#state=normal|closed|skipped|missed-2|must-not-default|empty|autopilot|undo`. Add `&t=dark` or `&t=light` (none follows the system), `&budget=20|60`, `&kinds=v1` (the plan's first version, 3 kinds), `&labels=off`, and `&hide=bar,clock,rate,ledger,closebar`. Every press works: the default and its alternative, Undo on a decided row, Undo on each default, Close Sitting, Make Automatic or Not Yet, and Skip This Week.

**Where it lives.** It is a new owner route with its own nav item, and Home's standing line names it (`app/src/standing.ts`, D121, Home states what is owed). The nearest existing screens: Review's queue (unclear matches stay there with their photo), Pricing's "Needs you" group (`docs/specs/pricing-suggest.md` sections 2 and 3), and `docs/specs/stale-listings.md` (stale listings). The undo model is `docs/specs/undo.md` section 11.1.

**Choices** (Gain / Lose / Pick)
1. Minutes bar: one segment per item, with the budget drawn as a hard tick. Gain: you see the size of the week and where the cut falls before you read a row. Lose: one more panel above the list. Pick: yes.
2. Running clock on each row (`4:30`, then the item's minutes). Gain: the cut line is a time you can see coming. Lose: a mono column on every row. Pick: yes.
3. Dollars per minute on each row. Gain: the sort explains itself. Lose: one more figure in the meta line. Pick: keep, it is the sort key.
4. The default is the outlined button with a "Default" tag; the alternative is plain. Gain: leaving the row and pressing the default mean the same thing. Lose: none found. Pick: yes.
5. The close bar says what defaults before you close. The plan requires this. Pick: yes.
6. Kinds ledger: the agree count and status per kind (Asks, Offered, Automatic, Never Automatic, No Default). Gain: you see autopilot coming. Lose: it belongs to stage two. Pick: show, hide it in the first build.
7. Thumb sizes: every press here is at least 42px below 1024 wide. At 820 the actions take a full row under the item. Gain: iPad first. Pick: yes.
8. A row with no default has a red edge, reads "Waits for you, with no date", and is never told that it "keeps its default", even below the cut. A row that cannot be undone has a pill, and its default line says "with no undo" before it applies.

**Departs from**
- Departs from: `pricing-suggest.md` section 2 and D273 (one press sends listings live), where no live price moves without a press — here a priced batch lists by date with no press. Owner grant: yes.
- Departs from: DESIGN.md "Ask first, or undo after" (UX-099) — the identify spend and the cheap-card cancel would apply unasked. The plan's first version leaves both out (`&kinds=v1`). Owner grant: yes.
- Departs from: the term "sitting". It already means a capture sitting (D121, D164, undo covers the whole sitting). "Weekly Sitting" needs a new name or a glossary line. Owner grant: yes.

**Owner questions (from the plan)**
1. Which day, and how long a budget? Recommended: Sunday, 40 minutes. The Time Budget control moves the cut line.
2. May any default spend money or cancel an order? Recommended: no in the first version, and a spend cap only once it has a record.
3. How many agreements in a row before a kind is offered autopilot, and can a kind that cannot be undone ever get it? Recommended: 10 in a row, and never.
4. What should the screen be called, given the collision with "sitting"?

**Verdicts.** 1440 light (`weekly-sitting-1440-light.png`): pass. The header, minutes bar, What Defaulted, ledger and cut line all fit with no overflow. 820 dark (`weekly-sitting-820-dark.png`): pass. The rail is 64px, the stats go to two columns, the ledger moves under the list and the actions take full-width rows. Also looked at all seven other states at 1440 dark: each renders as named.
