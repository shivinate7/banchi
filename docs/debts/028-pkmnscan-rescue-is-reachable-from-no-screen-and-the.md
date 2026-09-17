## 28 — `pkmnscan rescue` is reachable from no screen, and the screen that needs it names a command

**CLOSED 2026-09-13 (D210).** `#/pricing`'s "over a deleted box" sentence used
to tell the operator, in a tooltip, to run `pkmnscan rescue` on the stranded run — a CLI press
with no route, no client function and no control, the shape CLAUDE.md's "a route is not a
feature" rule refuses for a server capability, one register over. On 2026-09-13 the owner hit
the sentence, could not act on it from the app, and a session ran the three steps (`rescue`,
`--write`, `join`) for them from a terminal. PR #347 made the sentence go away once a joined
rescue exists; it did not put the press on a screen.

**What closed it.** `POST /pipeline/runs/<name>/rescue` (free, preview by default, `write`
gated — `do_queue_refresh`'s shape) in `server/pipeline_routes.py`, dispatched in
`server/capture_server.py` ahead of `_RUN_STEP_RE`; a client function (`rescueRun`) in
`app/src/server.ts`; and a control on `RunPanel.tsx`'s own run header, drawn only when
`detail.box_former` is true — the same gate the tooltip used. The tooltip now names the
screen instead of the command. The owner's same-day ruling that raw machine text may never
reach a screen meant the route could not simply relay `cmd_rescue`'s stdout the way every
other free step does; `do_run_rescue` parses it into a structured `RescueResult` instead, and
the raw report goes to a log file under the run's own directory. See D210 for
the whole argument, and `harness/tests/t7_store_and_seams.py:check_rescue_route` and
`app/tests/run-panel.spec.ts`'s four rescue cases for what proves it.

Original text, kept for the record — **why it was deferred rather than built, at the time**:
D165 records that every run on the owner's machine that CAN strand predates the `bid` field,
and every run since 2026-09-12 binds to the drawer's true index and cannot strand. So the
press was for a shrinking, legacy set — one run at the time — and a control on `#/runs` beside
the run panel was real work for a case D145 had already made rare. It was named there so the
next session that widened `#/runs` would find the argument, not the tooltip. That session is
this one.
