## 32 — The archive sweep stays a press, and the owner intends to schedule it eventually

`pkmnscan archive sweep` is a press. Nothing fires it on its own (D278, and the docstring of `cli/cmd_pricearchive.py`, which puts any timer, cron or launch agent out of scope by the owner's word). `make launch-agent` starts only the capture server. The owner's intent is to leave it a press for now and schedule it eventually.

A schedule reverses half of D33's outbound-call rule, that every outbound read is free, cached, or a press a person chose to make. It needs its own argument: pace against a host already measured to throttle this client (D222), what runs when nobody watches a terminal, and what a scheduled failure does that a press's visible failure need not.

**Outcome at risk.** Price history goes unarchived unless a person remembers to press.

**Closes when.** A decision entry argues the schedule (pace, failure mode, what changes about D278's guarantee) and the owner rules on it.
