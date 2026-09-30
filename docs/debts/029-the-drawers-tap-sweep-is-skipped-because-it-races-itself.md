## 29 — The drawer's tap sweep is skipped, because it races itself on a slower runner

`app/tests/phone.spec.ts`'s `every drawer route is reachable by tap, at two phone heights` is `test.skip`, a temporary bandaid on the owner's word. It failed identically three times on CI (shard 2 of 3, `page.goto: net::ERR_ABORTED; maybe frame was detached?`) and never on the rig. Hypothesis, unconfirmed: the loop taps a drawer row, asserts the URL, then calls `page.goto('/')` while the tap's own navigation is still in flight. Reproduce it under throttling or load before fixing, because a fix that passes locally proves nothing here.

**Outcome at risk.** A phone regression in the drawer ships silently: a row unreachable by thumb at 390 and 360, or the drawer's foot covering a row's centre. That is what left the Codes screen unreachable by touch.

**Closes when.** The failure is reproduced and fixed at its cause. Never by a retry, a `waitForTimeout`, a loosened assertion or a narrower sweep: the test discovers the drawer's own rows, and that is why it catches anything.
