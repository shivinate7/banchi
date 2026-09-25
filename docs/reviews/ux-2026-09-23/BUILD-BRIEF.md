# Shared brief for every builder lane (Banchi UX overhaul, 2026-09-23)

Read in this order. First your lane's section in `LANES.md`, with its "Owner rulings applied
after planning" and "Shared-file rules" sections. Then `RULINGS.md`, the owner's rulings, which
win over any finding's stated direction. Then each of your findings in `CONSOLIDATED.md` by id,
and your TXT rows in `density.md`'s cut list.

## Setup
- In your worktree: `git fetch origin && git switch -c ux/<lane> origin/main`. Then
  `make worktree-setup` and `npm --prefix app ci`.
- Commit on your branch in small steps, with clear messages. Push the branch to origin. Do not
  open a PR. Do not merge anything.
- Never run `git stash`, `git reset --hard`, `git checkout <path>` or `git restore`.
  Mutation-test with a `.bak` copy instead.
- Never touch `localhost:8000`/`5173`, or any server you did not start. Use `make dev` or
  `make up` in your own worktree only, on its own ports (D43). `make reap` stops only your own
  processes.
- A new decision entry lives under `docs/decisions/`, named by a slug file, never a number.

## How to build
- Before a screen change, run `make orient ARGS=<file.tsx>` and `make map ARGS=<path>`, and
  read each governing decision with `make map ARGS="D<n> --full"`. A decision's outcome binds
  you. Where the owner's ruling amends it, write the amendment entry your lane names.
- Check that the primitive already exists before you build one. Fix the cause, not the
  symptom.
- CSS uses `--bn-*` tokens only. A literal equal to a token's value fails
  `make token-literal-check`. Never type a middle dot or a bullet into a user-visible string
  (D218).
- No user-visible string names a decision, a repository path, or a pipeline-internal noun
  (D196).
- A press never moves the rest of the screen (D118).
- Stay inside your own files. If you need a file another lane owns, stop and report it under
  Input Needed.

## Done means
1. `cd app && npx tsc --noEmit` prints nothing. `make lint` passes.
2. Your lane's own "Done" line in `LANES.md` is met.
3. Every new check or test goes red on the defect before your fix (show it with a `.bak`), and
   green after.
4. Browser specs: `make design-check ARGS=--wait PW_ARGS="<your spec files>"`, then read
   `.serve/design-check.json` once, after it lands. Never poll it, and never pipe it into
   `tail`.
5. Screenshots of every screen you changed, at 1440, 820, 720 and 390, in light and dark. Use
   your own dev server with a seeded store (`make demo-seed`, `PKMNSCAN_HOME` set to a
   directory you own). Save them to your own scratchpad's `lanes/<lane>/` folder. Look at
   them, and give a verdict per screen, per size.
6. `make check` passes, or you name exactly which target fails, and whether it also fails on
   `origin/main`.

## Report
One blockquote, with bold labels Done, Deviations, Input Needed, in Simplified Technical
English. Done: the branch and head commit, one line per finding id (fixed, or not fixed and
why), the checks with their verdicts (never their output), and the screenshot directory. Never
paste a passing run's output.

## Hazard (added 2026-09-23, after an incident)
A local build from a folder with no `.git` (for example a scratch copy of main) falls back to
`localhost:8000`, the owner's live server. Before you load any page from a local build, confirm
the API port it calls. In every Playwright script, abort every request to a localhost port
other than your own. Never load a page that calls `:8000`.

## Screenshots: headless only (added after the fulfillment lane)
Take screenshots with a headless Playwright script that you write and run through Bash, saving
PNG files. Never use the shared Browser pane. Every agent in this session shares its tabs, and
one lane already saw another's tab land in its own view.

## Decision entries already written (branch `origin/ux/specs`) — cite, never duplicate
These slug entries already argue the owner's rulings. A lane cites them. It records only what
its own build adds, and only in its own lane's entry, where `LANES.md` names one not already
covered here.
The list: `D-pull-list-is-a-pick-count`, `D-money-is-mono-everywhere`,
`D-one-press-sends-and-makes-live` (with the double-send auto-reconcile),
`D-a-moved-card-keeps-its-price`, and `D-a-card-is-counted-in-its-section` (with card 1 at the
back, "slots", the departed label). Also `D-a-press-reorders-and-nothing-else-moves` (D209's
sort, D132's fold), `D-one-forgiving-search-matcher`, `D-a-section-is-an-object`, and
`D-card-order-key`. Also `D-reasoning-is-not-screen-copy`, `D-drawer-foot-joins-the-list`,
`D-pricing-is-one-list-and-one-send`, `D-sales-is-a-leaderboard`,
`D-orders-and-shipping-are-two-rows`, and `D-a-box-is-shown-by-its-name`.
So a lane does not write its own entry for the matcher, or the section ruler. Nor for card 1
at the back, the section-card number, nothing jumping, the orders sort press, or the orders
walk layout.
The sales-rows-by-sku entry records only its own per-SKU row build detail. The shell lane does
not write a D204 entry.
Read an entry from `origin/ux/specs` under `docs/decisions/`, by its slug filename.

## Worktree safety (added after an agent's worktree vanished mid-run)
Before every git write and every build, confirm `git rev-parse --show-toplevel` names your own
worktree path. If your worktree folder is gone, git resolves to the owner's main checkout.
Stop at once, and report it. Never write there.

## Port collision (added 2026-09-24)
Two worktrees can derive the same dev and capture port, because the path hash has only 300
slots. Playwright reuses a server already on the port, so a test run can pass against another
tree's code. Before any browser run, confirm the listener on your dev port names your own
checkout as its working directory. If it does not, do not kill it. Use a different port instead,
and say so. A fix lane (`ports-2`) is in flight.

## Wave 2: every lane is pausable
The owner's words, 2026-09-24:

```
It needs to be super pausable too because i'll run out of usage
```

- Work in small steps. After each finding group, commit and push your lane branch. Never hold
  more than about one hour of work uncommitted.
- Keep your own scratchpad's `lanes/<lane>/PROGRESS.md` current after each push. Record the
  head SHA, the finding ids done, the id in progress, and the next ids. Add any open question,
  and the exact command that proves the last step. A fresh agent must be able to resume from
  that file and the branch alone.
- If you stop mid-step, commit the work as "WIP: `<what>`" on your branch, and push it. Never
  stash it.
- Your screen lane's findings sit in `CONSOLIDATED.md`, by id. The owner's rulings sit in
  `RULINGS.md`, and override the finding text. Your file scope is your lane's section in
  `LANES.md`, plus its "Carried to wave 2" lines.
- A design question the rulings do not answer stops that one item. Write it in `PROGRESS.md` as
  a question, with options and a recommendation, and move on to the other items. Report it
  under Input Needed. Never guess.

## Wave 2: icons (owner ruling, 2026-09-24, see `RULINGS.md`'s iconography section)
- A common, repeated action on your screen becomes an icon button through the kit's
  `IconButton`, which the kit-icons lane builds on branch `ux/kit-icons`. Each one carries a
  tooltip, an accessible name, and a 40px target. These cover Mark sold, Undo, Retire, Edit,
  Delete, Copy, Download, Open, Close, Filter, Sort, and any action of the same kind.
- A press that spends money or cannot be undone keeps its words, for example Send, Identify and
  Stand down.
- Until `ux/kit-icons` merges into the integration branch, build your other items first. Then
  merge `origin/ux/kit-icons` into your lane, and convert the presses. Never hand-roll an
  icon-only button. `kit-adoption` refuses it.

## Wave 2: done means your offender entries are gone (2026-09-24)
Your lane is not done while any entry keyed to your lane remains in
`scripts/kit-adoption-allow.json`, an `app/tests/*-allow.json` file,
`scripts/typed-interpunct-allow.json`, or `scripts/ste-offenders.json`, for your own files.
Report the count left for each list.
