## DEBT59 — an unreadable live claim has no way out on screen

**Symptom.** A live send claim or submission whose row will not parse makes `SendClaims.live`
and `Submissions.live` raise `StoreError`. That is correct: a money path must not skip a live
claim. The press pre-check now refuses with the same sentence (`claim_unreadable`).

**Gap.** Callers that stay strict and raise: `_claim_rows` (the claims list), `_claim_conflict`
and `do_pipeline_waiting` in `server/pipeline_routes.py`, and `SendClaims.overlap` /
`Submissions.overlap` (emit, the claim itself). The Sends list (`send_routes.do_sends`, through
`_held_stamps` and `_markdown_records`) no longer raises: it draws every readable claim and
returns `unreadable_claims`, which Pricing's send card shows. The app still offers no release. Recovery today is a hand repair of the row.

**Why not fixed.** A remedy needs claim rows that tolerate an unreadable claim, so the screen
can draw and release it by key. That is more than 40 lines and a screen change. Owner's word,
2026-09-28: leave as a gap. It has never occurred on the real store (unmeasured beyond that).
