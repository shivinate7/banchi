15. ~~**The pipeline seam: the four commands, reachable from a screen**~~ — **done 2026-08-24.** D33, built
    2026-08-24. spec-less by choice; the decision entry carries the whole argument.

    **THE LARGEST INSTANCE OF `CLAUDE.md`'s route-is-not-a-feature RULE THIS REPO HAS HAD,
    and nobody had counted it.** `./pkmnscan identify | join | emit | reconcile` has existed
    since step 4, went through Gate B's 53 cards and box 2's 544, and could be reached only
    by somebody typing at a terminal. This section already named the cost in the Gate B
    write-up — *"the owner had no visibility into emitted import files; their names exist
    only in CLI output the owner never sees when someone else drives the commands"* — and
    filed it as a Someday item rather than as the missing half of a built feature.

    `server/pipeline_routes.py` is its own module because it is the one part of the capture
    server that can cause money to be spent. **One route does, and it is named for it**:
    `POST /pipeline/identify` refuses without an explicit `confirm`, and refuses a second run
    over a capture directory a live run is already reading. The preflight beside it is free
    and creates no run directory at all. Everything else there — the reads, and
    `join`/`emit`/`reconcile` — is free and re-runnable, which is D1's two-phase split.

    **The money step spawns detached and is never awaited**; the free steps answer inside the
    request with their own stdout attached. A run therefore outlives a restart of the server
    that started it, which is what makes `GET /pipeline/runs` able to show a run somebody
    started in a terminal.

    `app/src/RunPanel.tsx` draws it UNFOLDED, the owner having overruled the fold on 2026-08-24
    — **on `#/inventory` until 2026-08-29, when D39 gave the pipeline `#/runs` of its own.**
    Left saying so rather than rewritten to have always meant `#/runs`: what this step built
    is the seam, and the address it was first reachable at is part of what it built
    (D33, amended), and `app/tests/run-panel.spec.ts` is the check the hard rule says does not
    exist — the strongest of its cases being negative: **before the free preflight has answered,
    the control that spends does not exist.** Absent, not disabled.

    **The panel's address moved twice after this step and this paragraph named the first one.**
    It read "on `#/inventory` — sharing one `.browse-boxrun` row with `BoxOps`", which D38
    superseded within a day and D39 superseded outright: the pipeline has its own route, `#/runs`,
    as of 2026-08-29. Corrected rather than left standing, because this is a build-order note
    about what exists and not a measurement of a run — the numbers in the gate sections above are
    what this file never rewrites. The case count went with it for the same reason `docs/DESIGN.md`
    stopped publishing its assertion total: `npx playwright test` owns it.

    **What this step did NOT do**: no run has been started from the app. The panel's preflight
    and its three free steps have been exercised against the real store — a real `join` of box
    2 was driven end to end from the screen — but every identification this project has paid
    for was submitted from a terminal, and `POST /pipeline/identify` has been proven only by
    its refusals. Recorded here rather than left to be assumed from a green spec, in the same
    words this file uses for T6's synthetic composites.
