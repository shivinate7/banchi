## What shipped

**This was one numbered list with a `status` field until 2026-08-31, and its shape was
telling a lie no individual row was telling.** Rendered the only way a numbered list can be,
it said *"Build step 9 of 15"* — while 13, 14 and 15 were done, 9 had been deferred by choice
for a week, and everything from D34 onward had landed with no step at all. So it is two lists now: this
one, ordered by the date the work landed, and **What is open** below, which is not ordered
and has no "next" — ranking two open items is the owner's call, and "exactly one is next" is
what forced a false answer to it.

**The numbers are stable ids and are never renumbered.** 218 references to `step <n>` live in
this tree — 74 of them `step 7` — so a renumber would leave every one pointing at a real step
that is not the one meant, which nothing could detect, because a stale number still resolves.
That is why the ids below run out of order and why there is a hole at 12. `docs/map.py`'s
`SHIPPED` and `OPEN` carry the same ids, and `make docs-audit`'s `build order mirror` row
checks both directions, so adding or culling a step is a two-file edit a machine watches.

**Step 12 was culled — the only row ever removed.** It read *"Only then: scale, polish,
deferred list"*, named no deliverable, and its *"only then"* pointed at the gating system
retired on 2026-08-23. It then spent a week `blocked` on step 9, a dependency invented on its
behalf so it would not have to claim a blocker that no longer existed. The deferred list it
named lives in `docs/DECISIONS.md` and is that file's to open or close.

