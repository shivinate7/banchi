## 37 — ~~under `--cap`, a pending copy and an unseen live copy can both be out~~ — CLOSED 2026-09-27, on the owner's word

**Closed by a different fix than the one this entry recorded.** The owner did not choose
"take the sum." They did not keep "take the larger" either. Their own words: *"We just need
to make capping only be available to be used once we reconcile with live no?"* `emit --cap`
now REFUSES a card outright while a copy sent since is still pending. It no longer spends the
cap against either of two readings. Each reading could be wrong on its own. D7 carries the
fix in full. This entry keeps the measurements that found the problem.

**The overshoot this entry measured cannot happen any more, because the state it needed
cannot happen any more either.** A pending copy no longer reaches the cap's arithmetic at
all — it refuses the card first. The two probes below are historical: what the store did
before this fix, not a shape the cap can still be in.

- One pending copy, one live copy the store had not read, and a cap of 2. The send added 1,
  so 3 were out, 1 over the cap.
- Three pending copies, four live copies, and a cap of 5. The send added 1, so 8 were out,
  3 over the cap.

**The under-send this entry also measured is closed by the same rule, from the other side.**
Where the store's own reading is stale, the fix is not a guard file. It is a fresh
`reconcile --live`. Once reconciled, the cap reads the store's one reading again. The
probe's own steps (`emit --cap 1`, `reconcile --live`, a second `emit --cap 1`) send exactly
as much as the reconciled reading allows.

**The two wording gaps this entry named are both closed too, in the same pass.** A guard
trim the cap had already made invisible no longer reads as a typed zero. `SkuMatch
.guard_trimmed` tells the two apart. The empty-send headline now counts a card the cap
closed, as `capped`, apart from `live`.

**Covered by T7's `check_send_matrix`.** `freshcap/{one,two}/{below,at,over}`,
`pendingcap/{one,two}`, `capsempty/{one,two}` and `share/{one,two}/cap1-guardall`. Every new
row was red against the unfixed code first.

Cites D7 (emit's send controls, the 2026-09-27 amendment) and D59 (the live cap is a
per-SKU quantity).
