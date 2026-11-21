# p-attention-further

The Weekly Sitting gets one dated default per item and a cut line set by the owner's time budget. Graduated autopilot is its second stage, and every default can be undone except a short list of irreversible kinds. Nothing here was checked against the repo, as the brief asked.

**1) One week, item by item**
- **An item enters** when an event creates it: a captured batch is ready to list, a match is unclear, a listing goes stale, the Fulfiller re-files a card. Each item stores the reason, the value at stake, an estimate of the minutes it takes, its default and its default date.
- **The default** is the safest action that can be undone, usually "hold". The date is the day of the next sitting. If an outside clock runs out sooner (the marketplace's ship-by deadline), the date is set before that deadline.
- **The sitting** happens at a fixed time the owner picks. It opens with one header: "34 min · 22 items · $380 at stake · 5 defaults already applied."
- **The cut line** sits where the owner's time budget runs out. Items are sorted by dollars at stake per minute. Items above the line get a decision. Items below it keep their defaults, and the screen says so before the owner closes it.
- **A default applies** on its date if no one touched the item. The system logs it with what it did and how to reverse it.
- **Next week's sitting** opens with "What defaulted": one line per applied default, each with one Undo control. Reading this list is part of the time budget.

**2) States**
- **A normal sitting:** the header, the list sorted by value per minute, the cut line, and a closing summary such as "14 decided, 8 kept their default."
- **A skipped sitting:** defaults apply on their dates anyway. Items that must not default carry over to the top of the next sitting. A second skipped week shows a banner: "2 weeks missed: 3 items have waited 14 days."
- **An item that must not default:** it is marked and has no date. It waits in the queue, and it becomes a single interruption only when an outside deadline gets close (a slab order going unshipped, for example).
- **An empty week:** "Nothing needs you. 6 defaults applied." The owner can read the list in under a minute or skip the week. Nothing nags.
- **A kind proposed for autopilot:** "You kept the default for 12 of 12 stale listings. Make this automatic?" The owner answers Yes or Not yet. A kind on autopilot drops out of the sitting and shows up only in "What defaulted."
- **An undo of a default:** each kind has its own reverse action (delist, put the old price back, send back to the queue). The undone item comes back with today's date. Kinds that cannot be undone say "cannot undo" before they ever apply.

**3) Item kinds and their defaults**
- A priced batch ready to list → list at the rule price. This can be undone by delisting.
- An unclear identification or variant → stays unlisted in the review queue with its photo. It never defaults to a guess.
- A listing with no sale for N days → keep it listed.
- A price outside the round-1 rule bands → keep the current price. This kind comes from round 1, so it is only fed in here, not designed again.
- The Fulfiller fixed a card's location → accept the fix.
- A box or section is nearly full → start the next section in the next box with space.
- An identify batch is waiting → run it up to the standing weekly spend cap and hold the rest. **Cannot be undone (it spends money).**
- A cheap card is missing on an order → cancel before the ship-by deadline. **Cannot be undone (a cancellation).**
- A missing graded slab or high-value card, or a high-value order problem → must not default.
- An order file not imported for N days → must not default. It is a chore, and it grows louder each week.

**4) Smallest first version**
Three kinds only: a batch ready to list, an unclear identification held back, and a stale listing. All three can be undone. It has the iPad list, the cut line, dates, defaults that apply on their own, and "What defaulted" with Undo. It leaves out autopilot, any kind that spends money or cancels an order, and interruptions.

**5) One measure**
Owner minutes per week spent on the business: time in the sitting plus each interruption. It is valid only while the undo rate of applied defaults stays below the bar the owner sets.

**6) Owner questions**
- Which day and how long a time budget? My recommendation is Sunday, 40 minutes.
- May any default spend money or cancel an order? The options are an identify spend under a cap, and cancelling a missing cheap card. My recommendation is no in the first version, and the cap only once it has a record.
- How many agreements in a row before a kind is offered autopilot, and is a kind that cannot be undone ever eligible? My recommendation is 10 in a row, and never.
