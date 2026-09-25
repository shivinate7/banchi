# STATE — Banchi UX overhaul orchestrator

The orchestrating session's own state, kept durable. It drops agent ids and any line that goes
stale in hours. For what merged and what remains at any later moment, read the git log and
`LANES.md` directly, not this file's own memory.

## Role
The session plans, briefs, verifies, and merges lanes into the integration branch. It does not
review screens or build product code itself. The owner names it Orchestrator for one merge at a
time, never as a standing grant (CLAUDE.md's own ruling, 2026-09-20). It asks for the word
before every merge to main.
Planning and deliberation agents run on Opus, by the owner's word. Builders run Opus for
foundation work, the shell, safety, money, store writes and the live account. Sonnet covers
every other lane. Every lane gets its own fresh reviewer for each round. A resumed agent loses
its worktree, so a follow-up round always starts a new one.

## Sources of truth
Read these over chat memory.
- `RULINGS.md`, in this folder: every owner ruling and every orchestrator call, labelled.
- `LANES.md`, in this folder: the waves, the lanes, their files, and later corrections.
- `BUILD-BRIEF.md`, in this folder: the shared builder brief, safety rules included.
- `CONSOLIDATED.md`, in this folder: all 272 findings, UX-001 through UX-272.
- Landed specs and decisions: `docs/specs/ux-overhaul-2026-09-23.md`, `docs/specs/box-map.md`,
  and the slug decision entries under `docs/decisions/`.

## What merged
- Wave 0: `pricing-clip`, the specs, `ports-safety`, `fulfillment`, `kit-data`, `kit-frame`,
  `guards`.
- Wave 1: `product`, `demo`, `shell`, `kit-frame-2`, `demo-2`, `text-checks`, `ports-2`,
  `filtering`, `locating`.
- The send-and-pricing flow work (`b-runs`), through several review rounds. `RULINGS.md`'s
  "Orchestrator calls" sections carry each round's own outcome.
- The offender-list conversion (`ratchets`), replacing the D218 and D229 pinned counters with
  shrinking lists.
- An icon-buttons kit lane, still going through review as of this record. Its own decision
  entry and its iconography spec land with it, under `docs/specs/`.

## What remains
- The wave-2 screen lanes: home, capture, sales, shipping, library, inventory, orders, review,
  search-server, and the Pricing redesign. `LANES.md` names each one's own file scope and done
  check.
- The box map: a spec only so far (`docs/specs/box-map.md`). No build lane has started.
- `docs-sweep`, last, once every other lane has landed.
- A final verification pass: every screen at 1440, 820, 720 and 390, in light and dark, with a
  verdict per screen.
- The merge order: the identity work's own PR first, then this overhaul's first PR (waves 0 and
  1, plus the released `b-runs` rounds and the ratchets work), then the CSS and token-literal
  sweep, then this overhaul's second PR (wave 2).
- The owner's first real TCGplayer test (`REAL-TEST.md`), which runs only after the overhaul
  reaches main.

## Peers
- The token-literal sweep and guard session converts the `token-literal-check` guard itself,
  inside its own sweep, after this overhaul's PR lands. It needs the shared only-shrinks
  helper's module and symbol names, and the changed CSS file list, once the PR is ready.
- The photo-issues analysis session relays the merge order for the identity work and the
  schema bump. Message it the merge commit, the main SHA, the schema number, and the file list,
  once the first PR merges.

## Lessons
- A worktree can vanish once its agent finishes. `git` in that path then resolves to the main
  checkout. Resume by branch, never by agent id. Spawn a fresh agent on the pushed branch, and
  confirm `git rev-parse --show-toplevel` first.
- Two worktrees can derive the same dev port, because the path hash has only 300 slots. Verify
  the listener's own working directory before any browser run.
- The shared Browser pane serves whichever worktree started it, never the calling agent's own.
  An agent verifies its own build with a headless Playwright script on its own checked port
  instead.
- Never let an agent near port 8000, the owner's live store. One incident happened, reads only.
  The `ports-safety` lane is the fix.
- The silent-write hook refuses a quiet git flag. `guard-shell` refuses a checkout over a
  modified file. Resolve a conflict by editing the file, never by forcing a side.
- A janitor sweep can remove a finished agent's worktree. Treat every finished agent as gone.
  Work resumes from its pushed branch, in a fresh worktree, never from the old agent id.
