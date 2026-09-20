## 30 — The copies panel flash guard is shelved, on the owner's own word

**What is off.** Two tests in `app/tests/inventory.spec.ts`, found by title, never by line
number.
The first title starts `the copies list holds while a new answer moves the walk to another drawer`.
The second is its immediate sibling, titled starting `a press to another drawer dims`.
Both are `test.skip` as of 2026-09-19. Each skip carries an `annotation` so the
reason reads in the run output, not only in this file. Both guard the same mechanism, through a
shared helper, `expectCopiesHeld` (near line 6197). It samples every animation frame during a
delayed box fetch. It asserts that no frame lost the copies panel's rows.

**This is SHELVED, not retired, and it is a standing state.** The owner chose to turn it off. The
owner's own words: "Turn the guard off for now on the repo. I give you explicit authority." The
owner will revisit this later. No date is set for that. A session that finds this entry weeks
from now should read it as a standing decision. It is not something somebody forgot to undo.

**The defect it was catching.** On the runner, during a deliberately delayed `GET /inventory/<box>`,
a search-driven re-rank moves the walk from box 7 to box 2. For 14 consecutive
animation frames, about 230 milliseconds, `expectCopiesHeld`'s watch read rows zero, column one,
skeleton two. The copies panel itself did not tear down. Its contents blanked to skeleton
placeholders during that window. The panel recovers, so the final, settled page reads clean.
Only frame sampling can see the flash. This is the D118 stability floor's own subject. A press,
or here a re-rank, may not blank what is already on screen while a new answer is in flight.

**The measurement.** These two tests failed 6 of the last 10 completed runs on main. The failure
always hit the same shard, always these same two tests. The defect predates the most recent
merge to main. It is not a regression this round introduced.

**Why a skip, and not a loosened assertion or a longer timeout.** Trust a guard only once it goes
red on the defect it guards. This one did. Loosening `expectCopiesHeld`'s assertion, or widening
a timeout so the flash falls inside it, would hide the finding instead of shelving it. Either
change would leave a future reader believing the mechanism was fixed. It was only made unable to
see the break. `test.skip`, with an annotation, is honest. `make design-check` and any Playwright
report show these two as skipped, by name, with a reason, every run.

**What is unguarded while this sleeps.** Whether the copies panel on `#/inventory` ever shows a
skeleton flash during a delayed drawer re-rank. That covers both a fresh search answer and a
direct press to another drawer. A regression here would ship silently. It stays silent until
this guard returns, or a person looks at the screen directly during a slow fetch.

**What must be true to turn it back on.** The 230ms flash must stop occurring. Or,
`expectCopiesHeld`'s assertion must be replaced with one the owner has reviewed and accepted as
still catching the same defect. Concretely, one of two things must happen. Either the copies
panel's data flow changes. A fetch in flight must never turn its rows to skeletons while the
panel stays mounted. That is the product fix, and this entry does not authorize it. Or the
owner reviews a new assertion shape and says it still proves the same thing. Neither happened here. This entry is
not itself that review. Fixing the flash is separate work, not undertaken here.

**What this entry does not do.** It does not diagnose the flash's root cause in `BoxBrowse.tsx`
or `Inventory.tsx`. It does not touch the inventory screen or the copies panel. It records what
was measured, who authorized turning the guard off, and the condition for turning it back on.
