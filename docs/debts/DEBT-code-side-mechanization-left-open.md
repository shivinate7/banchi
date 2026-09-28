## DEBT-code-side-mechanization-left-open — code-side mechanization left open after PR #379 / PR #380

`docs-audit` mechanizes claims written in markdown. Two rounds — PR #379, PR #380,
2026-09-17 — extended that to claims written in code. Four new `docs-audit` rows landed.
Route reachability landed. `make mutate-guards`/`make mutate-anchors` landed. Four items
stayed open, named in both PRs, and stay open as of the 2026-09-27 memory migration.

1. **Nothing reconciles the shell-clause NUMERAL in `CLAUDE.md`'s prose, against
   `scripts/guard-shell.py`'s own `CLAUSES` table.** The `env names` `docs-audit` row checks
   the escape-hatch NAMES, never the count. The Makefile has already once said "FIVE," while
   the guard carried eight.
2. **`reap-selftest.sh` has no arm that exercises an UNKNOWN verdict.** That is a real,
   untested branch, in the guard that decides whether to kill a process. It was found because
   a mutation introduced there SURVIVED, on the corpus's first run.
3. **`make mutate-guards` covers five guards, not the fourteen that carry a hand-written arm
   count in prose.** `make mutate-anchors` only proves the five it already has stay anchored.
   A reworded guard, among the other nine, can still drift silently.
4. **The Vite side of the `dist path agreement` `docs-audit` row is uncovered.** Closing it
   needs its own Node-side target. `docs-audit` itself sits on the commit path. It runs with
   a bare `python3`.

Also left open, from the same measurement sweep, never separately actioned: 73 `docs-audit`
rows carry no negative arm, meaning no fixture proven red. Six measured constants inside
code — store size and similar — drift against the real world. They never drift against the
tree. Nothing catches them going stale.
