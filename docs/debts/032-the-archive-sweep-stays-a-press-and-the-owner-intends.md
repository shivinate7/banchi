## 32 — The archive sweep stays a press, and the owner intends to schedule it eventually

**What is recorded.** `pkmnscan archive sweep` is a press today. Nothing in this repo fires
it on its own. D62 states this plainly, for the same reader `pipeline/pricearchive.py`
walks: "it cannot fire on its own, since no screen polls it." `cli/cmd_pricearchive.py`'s
own module docstring says the same thing again, by name: "any timer, cron or launch agent
that fires this on its own" is "DELIBERATELY OUT OF SCOPE, BY THE OWNER'S WORD."

**This entry does not change that.** The sweep is still a press, run by a person, after this
entry lands. No timer, cron job or launch agent is added here. `make launch-agent` still
starts only the capture server, never the archive sweep.

**The owner's own words.** Asked whether the sweep should become scheduled: *"Leave it as a
press for now, but record that I intend to eventually make it scheduled."* This is intent,
not an argument. It is recorded here rather than acted on, so it is not mistaken for done
and not mistaken for abandoned.

**Why a schedule needs its own argument, and cannot ride in on this one.** D62's own
statement — this reader cannot fire on its own — is one of the guarantees D33 named when it
broke this process's outbound-call rule in half: no socket to Anthropic, and every other
outbound read is either free, cached, or a press a person chose to make. A schedule reverses
half of that sentence. It needs its own reasoning about pace against a host already measured
to throttle this session (D222), about what runs when nobody is watching a terminal, and
about what a scheduled failure should do that a press's own visible failure does not have to
answer. None of that reasoning exists yet. `cli/cmd_pricearchive.py`'s own docstring says so:
"that reversal needs its own argument, which nobody has made yet."

**What would close this entry.** A decision entry that argues the schedule on its own terms
— the pace, the failure mode, and what changes about D62's own guarantee — reviewed and
ruled on by the owner. Until then this stays a press, and this entry stays open, the way
debt 30 records a standing, dated deferral rather than a task with a deadline.

**What this entry does not do.** It does not design the schedule. It does not pick a cron
expression, a launch agent, or a trigger. It does not touch `pipeline/pricearchive.py`,
`pipeline/pricehistory.py`, `cli/cmd_pricearchive.py`'s own sweep logic, or `make
launch-agent`. It records one sentence of intent, where a later session or the owner will
look for it before assuming the sweep either always was, or never will be, anything but a
press.
