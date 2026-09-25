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


## PR 2 / PR 3 lane status, 2026-09-25

PR 1 (#462) merged as `316b959e3`, claiming D259 through D285. PR 2 carries every wave-2 lane
except Sales and Box map, which build in parallel and land in PR 3. Each lane rebases onto
main after PR 1. This table is a snapshot. Read the branch and `LANES.md` for the current
state.

| Lane | Branch | State |
|---|---|---|
| home | `ux/home` | Done, reviewed. |
| orders | `ux/orders` | Round 5 and round 6 passed. Done for PR 2. |
| inventory | `ux/inventory-r2` | Round 3 built (main plus icons, tightening, the icon map, BoxOps select, CardHero fixes). Round 4 runs the InventoryOverlay icon and the R2 dialog. One review then covers rounds 3 and 4. |
| capture | `ux/capture` | Round 3 passed. Done for PR 2, apart from any capture entries left in the offender-list sweep. |
| kit-icons | `ux/kit-icons` | Passed its round-3 delta review. Not merged anywhere yet. Each lane merges `origin/ux/kit-icons` into its own branch. It lands with PR 2. |
| records | `ux/review-records` | Round 2 runs now: merge main, re-sync every ruling since round 1, and fix the D278 stale path. A Sonnet review of the whole branch follows. |
| kit-tighten | `ux/kit-tighten` | Passed. The popover browser check stayed vacuous, since no screen drew FilterBar yet. Each screen lane checks it in its own pass. Lanes were told to merge it and clear their round-2 entries. |
| review | `ux/review` | Round 1 runs now (the W2-8 findings, folding Runs in, three raw refusals, icons, offender entries). It merges `inventory-r2` again before its final pass. |
| b-pricing | `ux/b-pricing` | Round 1 runs now, on Opus. It covers the whole Pricing flow, Q1 through Q7, D277, and `#/product`. |
| sales (PR 3) | `ux/sales` | Round 1 reviewed. Every item passed, apart from two small fixes, one of them a confirmed zero-price no-source claim. Round 2 runs now: the spark stroke and the `/skus/photos` server cap. The PR 3 checkpoint stands in for a separate re-review. |
| boxmap (PR 3) | `ux/boxmap` | Round 1 built the runs-on-the-box form. The owner asked for a per-card key and a singles-and-ranges slice next. Round 2 runs now: the rework to a per-card key, the singles-and-ranges slice, and a merge of `inventory-r2`. An Opus review follows. |
| search-server | `ux/search-server` | Round 3 built (findings F1 through F8 fixed, mid-word search shipped, p95 44.7ms to 95.1ms measured on 2,600 cards). A fresh Opus delta review runs now. |
| library | `ux/library` | Round 2 passed. The Codes "slot" gap is recorded in `docs/specs/code-cards.md` §8, item 8. One round-2 filter-row entry (the Codes chip row) stays in the PR 2 sweep list. |
| shipping | `ux/shipping` | Passed review, 69 of 69. A note for later: two dead `REASON_SAYS` strings. Its OrdersHub-onto-`<Page>` item carries to the orders lane. |

Other PR 2 and PR 3 notes:
- Once kit-icons passes, it merges into PR 1 if PR 1 is still open, or into PR 2 otherwise.
  Orders, inventory and capture then merge it and convert their presses per `ICON-MAP.md`.
- `docs-sweep` has not started. It waits for PR 2.
- Deferred by the owner: an independent UI/UX review of the Orders walk mode, until budget
  allows, and the undo session (undo spec §11).
- Recorded, to build later: Orders' "Add orders" and "Cards to pull" as small square icon
  buttons on the filter line. This is recorded in D274.

## Follow-up lane after PR 2 (2026-09-25, the orchestrator's call, option a)

The PR 2 offender sweep left these entries in place. Each one needs a ruling or a lane of its
own, and none of them is a fix that the integration branch can make safely.

- Home's h1 is the greeting. `scaffold.spec.ts` wants the route's own title ("Home") as the one
  h1, and it wants the kit's top gap. The hero's h1 is the greeting (D121), so the `/` h1 and
  top entries stay until the owner rules on the hero.
- The capture top gap. Capture keeps its vertical inset small so that the viewfinder stays
  above the fold. The `/capture` top entry stays until a layout keeps both the kit gap and the
  fold.
- A `Page` variant for Fulfillment. The ruling keeps page and h1 for `#/fulfillment` and exempts
  width and top gap. `Page` draws its own header and the page width, so a `Page` with no
  header and no width is the fix. The R1, page and R2-class entries stay until it exists.
- The Runs R2 entries. `LiveReconcile`, `RunRescue`, `RunsComposer` and `RunPanel` still
  hand-roll a dialog, a select or a kit class. They wait on the runs fold into Review, per the
  coordinator's message to the review lane. The PR 2 fix made their sheets join the kit's
  overlay stack, scrims included, so they are correct now but not yet kit primitives.
- The six `icons` entries: `ClearPrices`, `Markdown`, `PriceHistory`, `Pricing`,
  `ProductHistory` and `SendCard`. All six are b-pricing's files, and the b-pricing branch
  already clears them, so they leave when b-pricing lands.
