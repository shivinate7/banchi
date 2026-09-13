## D-run-phase-treats-joined-as-identified — `_phase` reads `joined` as sufficient evidence identification happened

**The report, 2026-09-13:** a run panel badged "Not started" beside 42 SKUs already joined and
`pricing.json` on disk — one badge, one set of files, disagreeing inside a single panel.

**Root cause.** `server/pipeline_routes.py:_phase` gated every stage past `"ready"`/`"identify"`
on `manifest.get("collected")` alone. `collected` is written only by the ordinary
camera→batch→collect path (`cli/cmd_identify.py`). **D188** ("A join reads the store directly
when there is no run directory to replay") gave `join` a second entry point,
`resolve.load_from_store`, that resolves cards straight off the live store's own `Card`
records — no `identify` run, no `identifications.json` — so a store-backed join's run
directory legitimately carries `joined: True`, real `counts.skus`, a real `pricing.json`, and
`collected` absent forever. `_phase`'s `collected` check short-circuited before it ever reached
the `joined` check, so such a run could never advance past `"ready"`, and
`RunsStage.stageOf`/`app/src/App.tsx`'s badge read that phase verbatim as "Not started" — while
`RunPanel.tsx`'s own SKU stats, gated on the raw `joined` boolean rather than on `phase`, drew
the correct count beside it. Two fields, two different write conditions, one screen showing
both without reconciling them.

**The fix.** `_phase`'s first branch now gates on `collected or joined` rather than `collected`
alone. This is sound because `joined=True` can only ever be written after a `Resolved` was
produced (`cli/cmd_join.py`), and a `Resolved` — by either loader D188 names — cannot exist
without identifications having happened, whether frozen (`identifications.json`) or live (the
store's own `Card` rows). "Joined" is strictly stronger evidence than "collected" was ever
meant to gate on; the two checks were simply in the wrong priority order for a run type that
did not exist when `_phase` was written, pre-D188. No other branch changes: a genuinely
un-joined run (`collected`, not yet `joined`) still falls through to `"join"` exactly as
before, and the widening only ever pulls a run PAST the old gate, never adds one behind it — no
run that passed through the old `collected`-only gate regresses.

**Why the fix lives in `_phase` and nowhere else.** `_phase` is the one function every reader —
the badge, the stage bar, `RunsStage.stageOf` — ultimately derives from. Teaching every client
"joined implies past identify" separately would be the same rule written twice, which is the
drift this repo's own `D16` names.

**Guard.** `harness/tests/t7_store_and_seams.py:check_store_backed_join` now asserts
`pipeline_routes._phase(new_run.manifest, live=False)` is not `"ready"`/`"identify"` on the
store-backed join's own manifest, immediately after asserting its `pricing.json`/`report.txt`
exist. Red on the unfixed tree (`_phase` returned `"ready"`); green after. A one-line footnote
was added to `D188`'s own entry pointing here, so a future reader of D188 finds the fix rather
than rediscovering the gap.

**Naming the step on screen — a follow-on, not required here.** Once this lands, "Not started"
only ever means what it says: no batch, no store-backed join has touched this run yet.
`"ready"`/`"identify"` still conflate "nothing submitted at all" with "a batch is mid-flight",
and a future case may want the badge to name which. Not done in this pass — recommended, not
required, and left for whoever next finds the ambiguity load-bearing.
