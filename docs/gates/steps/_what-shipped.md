## What shipped

This was one numbered list with a `status` field. Its shape told a lie that no single row told. Rendered as a numbered list, it said "Build step 9 of 15". Yet steps 13, 14 and 15 were done. Step 9 had been deferred by choice for a week. Everything from D34 onward had landed with no step at all.

So it is two lists now. This one is ordered by the date the work landed. **What is open** below is not ordered and has no "next". Ranking two open items is the owner's call. "Exactly one is next" forced a false answer to that call.

**The numbers are stable ids and are never renumbered.** 218 references to `step <n>` live in this tree. 74 of them are `step 7`. A renumber would leave every one pointing at a real step that is not the one meant. Nothing could detect that, because a stale number still resolves. That is why the ids below run out of order, and why there is a hole at 12. `docs/map.py`'s `SHIPPED` and `OPEN` carry the same ids. `make docs-audit`'s `build order mirror` row checks both directions. So adding or culling a step is a two-file edit that a machine watches.

**Step 12 was culled. It is the only row ever removed.** It read "Only then: scale, polish, deferred list". It named no deliverable. Its "only then" pointed at the gating system, which is retired. It then spent a week `blocked` on step 9. That dependency was invented on its behalf, so it would not have to claim a blocker that no longer existed. The deferred list it named lives in `docs/decisions/` and is that file's to open or close.
