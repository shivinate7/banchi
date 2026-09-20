## D-archive-live-catalogue-lookup-at-join-time — Recorded, not built: ask the catalogue earlier than the archive does

**What this records.** the archive-refusal-mechanization analysis (PR #444, unmerged) measured a gap. 8 of 15
identification errors behind the archive's own 16 refusals cannot be caught from stored
data by any rule. This store carries no independent source of truth for a set's real card
list. D15 vendors the Pokemon catalogue locally. Riftbound and the newest Pokemon sets have
no local mirror at all. The only earlier catch is asking the live catalogue. Today that
happens months later, at sweep time.

**The owner's ruling.** Record the option, likely at join time, and do not build it now.
Nothing in this entry is built. `pipeline/join.py`, `pipeline/pricehistory.py` and
`cli/cmd_join.py` are untouched.

**Why join time, over capture time.** A join is already a networked, slow step. It already
asks the catalogue a question per card, through `Market.product_id_for_row`. A second
catalogue question there costs no new architecture. Capture is deliberately free and
offline (D1's own two-phase split: capture is fast, dumb and never touches a network). A
catalogue call at capture time would put a paid, throttled network wait between an operator
and the next photograph. That is the exact cost D1 built capture to avoid.

**The cost, named rather than hidden.** This would add a network call per ambiguous card.
It would run against a host already measured to throttle this client (D222, the archive's
own press pace). A box of newly captured cards would go from one free, offline join pass
to a pass carrying a per-card network wait, on every run. That cost would land on every
run, not only the runs that turn out to need it. The 15-subject measurement covers the
store's whole history, not one run. The per-run rate this would add is not yet measured.

**What is not decided.** Three questions stay open. Which cards would trigger the lookup:
every unresolved card, or only one a check from `D-archive-store-checks` or
the sku-number-contradictions build (a separate PR) already flagged. Whether a failed lookup should block the
join, or fall through to today's behaviour. How the result would be cached, so a re-join of
the same box does not re-ask the same question. None of these is answered here. Building
this is future work, gated on the owner's word.

Cites D1 (why capture stays offline), D15 (the vendored catalogue's own limits), D222 (the
archive's measured throttle), and PR #444's archive-refusal-mechanization analysis (the
8-of-15 measurement this entry answers).
