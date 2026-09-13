## D-rescue-is-a-press — `pkmnscan rescue` is reached from a press, and its report is never shown verbatim

**DEBTS §28 named the gap: `pkmnscan rescue` (D165) had been reachable from no screen.**
`cli/cmd_rescue.py:run` — the one-time repair for a run D36 refuses, over a drawer D20 has
since handed to another box — existed with full T7 coverage and a tooltip on `#/pricing` that
NAMED the command in backticks. Nobody could press it: the tooltip's own sentence was the
"three tested routes, zero client functions" defect this repo's hard rule exists to name,
wearing the smaller shape of a route that had never been written at all.

**The fix is the standing pattern this repo already has for a free, store-scale command**:
`POST /pipeline/runs/<name>/rescue`, mirroring `do_queue_refresh`'s shape — free, preview by
default, `write` gated — dispatched in `server/capture_server.py` ahead of `_RUN_STEP_RE` for
the same reason `/export` is, a client function (`rescueRun`) in `app/src/server.ts`, and a
control on `RunPanel.tsx`'s own header, shown only where `detail.box_former` is true. The
`#/pricing` tooltip that used to name the command now points at the row on `#/runs` instead.

**The owner ruled the same day, before this landed, on a wider question this route's own report would otherwise have collided with**: *raw machine text — stdout, JSON, a CLI string, a path — is never visible on the front end, not even behind a disclosure.* Every other free
step's route (`do_queue_refresh`, `do_pipeline_step`) returns `console` verbatim (D33) because
stdout is the one description of what a free command did, and a screen renders it in a
`LogWell`. `cmd_rescue.run`'s own report is unusually unsuited to that: its sentences carry
backticked `pkmnscan …` invocations and reference `CLAUDE.md` by name, which is exactly the
class `no mechanism on screen` (D196) refuses.

**So this route is the deliberate exception to D33's own "stdout verbatim" habit, not a second rule contradicting it.** `do_run_rescue` parses `cmd_rescue`'s stdout into a small structured
shape (`RescueResult`: `ok`, `wrote`, a `reason` CODE, `counts`, `destination`,
`already_rescued`, `new_run`) and writes the raw text to `runs/<name>/logs/rescue-<stamp>.log`
instead of returning it — a person at the machine can open that file, and no screen ever
will. `RunRescue.tsx`'s sheet composes every sentence it draws from those typed fields,
translating `reason` through its own copy table (`REASON_COPY`) rather than showing the CLI's
own words.

**The write is a press, not a route change (D118).** The sheet opens over the run's own
header; a successful write's receipt links back to the new run by name
(`onOpenRun`), and the source run is never edited — `cmd_rescue.run`'s own invariant, carried
through unchanged. Re-opening the sheet after a write re-previews rather than replaying the
last answer, because the shelf may have moved since.

### Built

`server/pipeline_routes.py:do_run_rescue` and `_parse_rescue_console`; the dispatch in
`server/capture_server.py` (`_RUN_RESCUE_RE`, matched ahead of `_RUN_STEP_RE`); `RescueResult`
in `app/src/types.ts`; `rescueRun` in `app/src/server.ts`; `app/src/RunRescue.tsx` and
`RunRescue.css`; the header control in `app/src/RunPanel.tsx`; `Pricing.tsx`'s tooltip
reworded to name no command.

### Mechanized

`harness/tests/t7_store_and_seams.py:check_rescue_route` — the route, preview and write,
against the same stranded-run fixture `check_rescue_stranded_run` builds for the CLI itself;
asserts no `console` key reaches the response in any of the three states (preview, write,
refusal) and that the log file lands on disk. `app/tests/run-panel.spec.ts`'s four D165 cases
(`make design-check`): the control's visibility gate, the preview-before-Apply rule, the
write's receipt and way back, and a refusal drawing a sentence rather than the CLI's own
reason code — the last two also assert the sheet's rendered text never contains `pkmnscan`,
a decision citation, or a log path.

`scripts/docs-audit.py`'s `no mechanism on screen` row gained `_CLI_INVOCATION_RE`: it had no
key for a backticked `pkmnscan …` invocation before this entry, which is exactly the shape
`Pricing.tsx:4468` carried. `check_no_mechanism_self_test` pins a fixture (`CliInvocation.tsx`)
proving it is caught, red-first against the un-widened row.

### Not reopened

D165 (the CLI itself), D36 and D145 (what makes a run stranded and how it is repaired) are
read and cited, not revisited — this entry is the client half of an already-settled server.
