# Runs, harness, build order

**THE GATING SYSTEM IS RETIRED (2026-08-23, owner's decision). This file is a record of
what was measured, not a schedule.** Gates A, B and C all passed; no gate is current; no
step is blocked behind one; the deferred list is open. `CLAUDE.md` no longer declares a
current gate and `scripts/docs-audit.py` no longer reconciles one.

**Every number in the gate sections below is evidence about a run that happened on a date,
and none of it is ever rewritten to match a later tree.** 53 cards end to end. Finish
detection at a 30% false-positive rate under the rig's lighting. `detect_card` at 0 of 53,
then 53 of 53 by a second method. A 623 ms feeder cadence over 84 intervals, twice. Those
are the only facts this project has about cards rather than about itself, and renumbering
one to agree with today's code would turn a measurement into a fiction — which is the one
thing a record may never do.

What was retired is the gate as a *control*: the blocking, the sequencing, and the
"current gate" a session had to look up before it was allowed to build. The harness below
is untouched and is still the contract.
