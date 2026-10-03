## DEBT59 — an unreadable live submission claim has no way out on screen

A live send claim that will not parse is drawn and released by key on Pricing's send card. `send_routes.do_release_unreadable` releases it and `do_restore_unreadable` undoes that. Until then it blocks every press.

A live submission claim (the paid identify press) has no such way out. `Submissions.live` and `Submissions.overlap` raise `StoreError`. That is correct: a money path must not skip a live claim. The press pre-check refuses with `claim_unreadable`. `_claim_rows` and `do_pipeline_waiting` in `server/pipeline_routes.py` raise too, so Runs cannot draw the list. The app offers no release, so recovery is a hand repair of the row. It has never occurred on the real store (unmeasured beyond that).

**Outcome at risk.** An identify press stays refused until someone repairs a database row by hand.

**Closes when.** Submission claims get the same three parts. First, `_claim_rows` returns the unreadable key. Second, a release by key keeps a tombstone and has an undo. Third, Runs has a control. `SendClaims.unreadable_rows`, `release_unreadable` and `restore_unreadable` are the model.

**Ruling, send claims.** Release is allowed for a mark-down claim too (key `md-<stamp>`), with a warning. Its confirm says that the price change is not confirmed yet and that a send could run over it. A readable claim is never released from here.
