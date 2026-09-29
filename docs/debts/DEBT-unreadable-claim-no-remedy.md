## DEBT-unreadable-claim-no-remedy — an unreadable live claim has no way out on screen

**Symptom.** A live send claim or submission whose row will not parse makes `SendClaims.live`
and `Submissions.live` raise `StoreError`. That is correct: a money path must not skip a live
claim. The press pre-check now refuses with the same sentence (`claim_unreadable`).

**Gap.** `_claim_rows` calls `live()` too, so it raises and the claims list cannot draw. The
app therefore offers no release. Recovery today is a hand repair of the row.

**Why not fixed.** A remedy needs claim rows that tolerate an unreadable claim, so the screen
can draw and release it by key. That is more than 40 lines and a screen change. Owner's word,
2026-09-28: leave as a gap. It has never occurred on the real store (unmeasured beyond that).
