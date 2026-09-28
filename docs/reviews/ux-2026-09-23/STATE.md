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
PR 1 (`#462`), PR 4A (`#466`), PR 3B, and the demo mirror (`#467` to `#477`) are already on
main. `PLAN-PR4-PR5.md`'s Finished table tracks PR 4B's own lanes, up to lane rulings
(`262f3351`). Read that table, not this section, for which PR 4B lane landed with which
commit.

## What remains
Lane L12, the docs-audit tiers, is the only PR 4B lane still building
(`docs/reviews/test-audit-2026-09-27/TIERS.md`). After it merges: the final head gets
linting only, then the PR, green CI, and `make merge`. `PLAN-PR4-PR5.md`'s "Still to come"
and "After PR 4B merges" sections name what follows.

## Peers
The token-literal sweep already landed: `make token-literal-check` is in `make check`. No
peer session's work is outstanding for PR 4B.

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


## PR 1, 2 and 3, done

PR 1 (`#462`) merged as `316b959e3`, claiming D259 through D285. PR 2 and PR 3 followed and
are both on main. Every lane the 2026-09-25 snapshot tracked here (home, orders, inventory,
capture, kit-icons, records, kit-tighten, review, b-pricing, sales, boxmap, search-server,
library, shipping) landed. Git log on `main` carries the detail. This file no longer repeats
the per-lane table.

The follow-up offender-list entries that snapshot left open (Home's h1, the capture top gap, a
Fulfillment `Page` variant, the Runs R2 dialogs, and six b-pricing icon files) are all
resolved: none of them appear in `scripts/kit-adoption-allow.json` any more. Home's h1 stands
as a PERMANENT, argued exemption (owner's ruling, 2026-09-27, "Keep Home").

## Deferred items, 2026-09-26 (docs sweep)

- **Dark-mode contrast.** Superseded by lane H. The owner asked for a cyberpunk-themed dark
  mode instead of the A/B/C contrast fixes (`ux/dark-palette`). H found its many-color
  direction ("Abyssal Bloom") and left PR 4B as its own deferred PR, recorded on
  `ux/h-record` (`e7c8358a`).
- **Stock card images.** Still an open question for the owner. The tcgcsv product `imageUrl`
  on the TCGplayer CDN, keyed by `productId`, is one source. The vendored catalog is a second
  source, for Pokemon. Coverage across the store is unmeasured.
- **One card named from its rules text.** On the owner's store, box 3, index 987, one card's
  name reads its own rules text rather than its printed name. Still not fixed: the
  2026-09-26 graveyard ruling touched only rendering and the read route
  (`pipeline/identity_checks.py:flag_long_names` already flags it as a `long_name` finding).
