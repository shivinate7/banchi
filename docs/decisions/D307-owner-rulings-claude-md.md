# D307 — Owner rulings CLAUDE.md points to

**Why this entry exists.** The owner asked for CLAUDE.md to be rewritten in place and cut to rules.
A ruling's home is a decision entry. CLAUDE.md points at it. These rulings had no entry, so this one holds
them. Each is the owner's, and each is settled until the owner reopens it.

### Product and process

**Code cards are a feature, not a second track.** The owner has not used the feature. It stays in the build.
It is marked DORMANT in one place, the "Code cards (dormant feature)" section of CLAUDE.md.
D14 (two tracks, one rig) keeps its structural half. `codes/` is its own package. `docs/map.py` keeps `TRACKS`.
`scripts/decision-context.py` keeps its banner. Repeal of those needs the owner's word.
D248 (code cards fold into one rules file) folded the code-card rules into the one file.

**Gating is retired.** Gate A, B and C passed. Gate B was 53 real cards end to end.
Gate C was two 85-card feeder runs. Nothing is blocked behind a gate.
`docs/GATES.md` records runs and is never a schedule.
Its numbers are evidence and are never rewritten to match a later tree.

**The name is the app's, and nothing beneath it.** D94 (the product's name) holds the argument. It does not hold two facts.
The local directory is `~/Developer/banchi`. The GitHub repository is `shivinate7/banchi`.
GitHub Pages followed the rename. `.github/workflows/demo.yml` derives `DEMO_BASE` from the repository name.
The Makefile's own default is a stale fallback for a hand-run build, by design.

**Merge runs through the batch runner.** claude-settings decision session-tiers names the tiers. The batch
runner owns the integration batch, the CI waits, the merge tool runs and archiving finished lanes. The coordinator
starts lanes and talks with the owner. The batch runner, the session the coordinator starts and tags `cs-build:batch-runner`, batches every reviewed lane the owner set out, across all
sessions, into one integration branch and merges it under the coordinator's standing grant. A lane session hands the batch runner
each reviewed lane branch with its head commit and review verdict. A lane session never builds an integration branch,
opens an integration PR, marks a PR ready or merges.
The batch runner merges only through `make merge ARGS="<n> --confirm"`, with CI green, and never with `--admin`.
`make merge` never rebases or force-pushes, and a moved head stops it.
A session's role comes from its own `cs-build` tag (claude-settings decision session-tiers). D42 (main moves by PR) holds the rest.

**Model tiers.** A lane session runs Opus (claude-settings decision session-tiers). The agents it starts follow
`agent-model-cap`. Sonnet is the default and the ceiling. Plan, the built-in advisor, the designer, the design
reviewer and a builder's third try run Opus. Reviewers run Sonnet from round 2; round 1 uses the role's model.
Any other Opus agent needs the owner's grant. It is said in one line first, and raised only on the owner's grant
in `.claude/settings.local.json`.

**A builder commits and pushes its branch after every pass, even when a check is red.**
Each commit message ends with a `Done:` line and a `Next:` line.
The `Next:` line names what is left, in order, so a lane resumes from its branch alone.

**Experience is everything.** This is the owner's ruling for screen work.
Run a design pass before you build a screen.
Review the built screen against that pass before you call it done.

### Screens

**390px is checked only on an owner phone report.** Verify a screen at 1440 and 820, in both themes.
The specs that assert phone layout stay in CI.

**The Sales screen is a nav row on purpose.** The owner saw the cost of 37px past the fold at 390x754.
The owner chose the sidebar tab anyway. D214 (gross-revenue retrospective) holds the retrospective itself.

**The route and screen count is read from `ROUTES`, never from prose.**
A hand-typed count that a table already gives is deleted, not reconciled.
README's route table stays. The `route rosters` row of `make docs-audit` reconciles it.

### Store

**A press has no spend cap and no threshold notice.** The owner's ruling: a press runs everything it selects. The confirm names the cards and the spend. D180 (press names the cards) holds the selection.

**No standing cap on copies.** A cap is something a send asks for.
`policy.live_cap` is deleted, and a stored key is refused by name.
The cap never stopped a copy going out twice. `uncommitted_positions` does that. D7 (duplicates aggregate by SKU) holds the rest.

### What moved out of CLAUDE.md, and where it lives now

- The Commands block explanations: one line each remains. `make explain` and `make help` hold the rest.
- The route roster: `ROUTES` in `app/src/App.tsx`, and README's route table.
- The `make check` list: `make explain`. The `check registry` row of `make docs-audit` reads the recipe.
- Each check's enforcement story: the decision entry that cites it, and the check's own docstring.
- The spec index in the Map section: `docs/specs/`, reached through `make map`.
