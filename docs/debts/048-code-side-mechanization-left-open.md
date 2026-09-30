## DEBT48 — code-side mechanization left open

`docs-audit` mechanizes claims written in markdown. Four claims written in code stay open:

1. Nothing reconciles the shell-clause count in `CLAUDE.md`'s prose against `scripts/guard-shell.py`'s `CLAUSES` table. The `env names` row checks the hatch names, never the count.
2. `scripts/reap-selftest.sh` has no arm for an UNKNOWN verdict, a real branch in the guard that decides whether to kill a process.
3. `make mutate-guards` covers six guards. Other guards that carry a hand-written arm count in prose are not covered, so a reworded one can drift silently.
4. The Vite side of the `dist path agreement` row is uncovered. `docs-audit` sits on the commit path and runs with a bare `python3`, so closing it needs its own Node-side target.

Also open: many `docs-audit` rows have no negative arm (no fixture proven red), and measured constants in code (store size and similar) drift against the world with nothing to catch it.

**Outcome at risk.** A guard or a count drifts while its row stays green.

**Closes when.** Each item gets its check, or its own decision.
