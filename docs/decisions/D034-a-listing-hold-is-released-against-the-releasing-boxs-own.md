## D34 — A listing hold releases against the box's own copies

**A box's listing holds release on the operator's word, budgeted by that box's own unsold copies.** `staged` is drawn down only by a rise in live quantity, so a staged row deleted on TCGplayer never clears and the box is undeletable forever. `store/master.py:staged_stale` names that case, and a diagnostic needs a remedy.

- **A release never zeroes a SKU outright.** Each SKU gives up at most the unsold copies the calling box holds, so a release from box 1 cannot give up commitments only box 3's copies could account for. Where a SKU is shared, the remainder keeps the box refused after a release that did what it said. The screen says so before the press.
- **One shared budget, spent `pushed`, then `staged`, then `live`.** Which stage a copy backs is unrecorded (D7), so the order is a rule: `live` is the costliest to be wrong about and goes last. A sold or retired copy does not count. `staged_at` clears only where `staged` reaches zero. The record survives at zeros (`_listing_hold` reads all zeros as not held).
- **It asserts and does not measure.** No export can say that nothing is staged, because absence from an Export From Staged is unbounded. Only the operator looking at TCGplayer can. So the route owes three things: `confirm: true`, a `listings_released` history line (box, SKU count, copies given up and `still_held`), and a free plan ahead of the press.
- **The plan is `GET /boxes/<box>/listings`.** It names each SKU's copies, what it gives up and keeps, the other boxes involved and `frees_box`. `server/capture_server.py:_release_plan` serves both routes by calling `Listing.release` on a copy, so the preview cannot drift from the write. The screen fetches it on open, and the release control is absent until it answers.
- **One press, because the plan is the gate.** Typing or a second press would not make anyone check TCGplayer. A wrong release is undone by staging again. Each press is its own assertion, with the cap per press.
- **It reaches no other ground of the refusal.** A sold or retired card still holds the box open (T7 asserts it). `GET /boxes` reports `retired` and `listed` beside `sold`, because the three have three remedies.

Reopen if the pipeline can read a staged quantity: a fresh Export From Staged setting `staged` absolutely would beat the claim.
