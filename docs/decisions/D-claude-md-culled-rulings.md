## D-claude-md-culled-rulings — Rulings that CLAUDE.md carried in prose, now held here

**Why this entry exists.** The owner asked for CLAUDE.md to be rewritten in place and cut to rules.
A ruling's home is a decision entry. CLAUDE.md points at it. These rulings had no entry, so this one holds
them. Each is the owner's, and each is settled until the owner reopens it.

### Product and process

**Code cards are a feature, not a second track.** The owner has not used the feature. It stays in the build.
It is marked DORMANT in one place, the "Code cards (dormant feature)" section of CLAUDE.md.
D14 keeps its structural half. `codes/` is its own package. `docs/map.py` keeps `TRACKS`.
`scripts/decision-context.py` keeps its banner. Repeal of those needs the owner's word.
D248 folded the code-card rules into the one file.

**Gating is retired.** Gate A, B and C passed. Gate B was 53 real cards end to end.
Gate C was two 85-card feeder runs. Nothing is blocked behind a gate.
`docs/GATES.md` records runs and is never a schedule.
Its numbers are evidence and are never rewritten to match a later tree.

**The name is the app's, and nothing beneath it.** D94 holds the argument. It does not hold two facts.
The local directory `~/Developer/pkmnscan` is not renamed. The GitHub repository is `shivinate7/banchi`.
GitHub Pages followed the rename. `.github/workflows/demo.yml` derives `DEMO_BASE` from the repository name.
The Makefile's own default is a stale fallback for a hand-run build, by design.

**Merge needs an Orchestrator that the owner named.** A session merges only after the owner names the act.
Only a session that the owner has called an Orchestrator may merge. It may merge only PRs it planned and reviewed.
It merges only through `make merge ARGS="<n> --confirm"`, with CI green, and never with `--admin`.
The designation is never inherited. It is never assumed from the shape of the work.
It is never carried over from an earlier session. It replaced a standing grant. D42 holds the rest.

**Model tiers.** Opus is for planning and for adversarial review of anything that touches money, TCGplayer or the
store's data. Opus also serves a builder that redesigns a whole flow, and a hard merge.
Sonnet builds and reviews every ordinary screen lane, fix round and delta review.

**A builder commits and pushes its branch after every pass, even when a check is red.**
Each commit message ends with a `Done:` line and a `Next:` line.
The `Next:` line names what is left, in order, so a lane resumes from its branch alone.

**Experience is everything.** These are the owner's words for screen work.
Run a design pass before you build a screen.
Review the built screen against that pass before you call it done.

### Screens

**390px is checked only on an owner phone report.** Verify a screen at 1440 and 820, in both themes.
The specs that assert phone layout stay in CI.

**The Sales screen is an eleventh nav row on purpose.** The owner saw the cost of 37px past the fold at 390x754.
The owner chose the sidebar tab anyway. D214 holds the retrospective itself.

**The route and screen count is read from `ROUTES`, never from prose.**
A hand-typed count that a table already gives is deleted, not reconciled.
README's route table stays. The `route rosters` row of `make docs-audit` reconciles it.

### Store

**`banchi.runs.spend-notice` is a notice and never a cap.** The owner's words:
"if I want to run everything, then I get to run everything." D180 holds the selection.

**No standing cap on copies.** A cap is something a send asks for.
`policy.live_cap` is deleted, and a stored key is refused by name.
The cap never stopped a copy going out twice. `uncommitted_positions` does that. D7 holds the rest.

### What moved out of CLAUDE.md, and where it lives now

- The Commands block explanations: one line each remains. `make explain` and `make help` hold the rest.
- The route roster: `ROUTES` in `app/src/App.tsx`, and README's route table.
- The `make check` list: `make explain`. The `check registry` row of `make docs-audit` reads the recipe.
- Each check's enforcement story: the decision entry that cites it, and the check's own docstring.
- The spec index in the Map section: `docs/specs/`, reached through `make map`.
