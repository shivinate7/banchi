## DEBT59 — an unreadable live claim has no way out on screen

A live send claim or submission whose row will not parse makes `SendClaims.live` and `Submissions.live` raise `StoreError`. That is correct: a money path must not skip a live claim. The press pre-check refuses with `claim_unreadable`, and the Sends list (`send_routes.do_sends`) draws every readable claim and returns `unreadable_claims`, which Pricing's send card shows. Still strict and raising: `_claim_rows`, `_claim_conflict` and `do_pipeline_waiting` in `server/pipeline_routes.py`, and `SendClaims.overlap` and `Submissions.overlap`. The app offers no release, so recovery is a hand repair of the row. It has never occurred on the real store (unmeasured beyond that).

**Outcome at risk.** A press stays refused until someone repairs a database row by hand.

**Closes when.** Claim rows tolerate an unreadable claim so the screen can draw and release it by key. That is more than 40 lines and a screen change, and the owner chose to leave it.
