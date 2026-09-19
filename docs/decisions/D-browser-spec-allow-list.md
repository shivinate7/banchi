## D-browser-spec-allow-list — Both: the worker count is raised, and the spec allow-list is built

**The owner's ruling, 2026-09-19: "Both — raise the worker count AND build the spec allow-list."**
D136 is amended in its own file for the worker-count half. This entry settles
the second half: `scripts/browser-scope.py specs` and the `check.yml` wiring around it.

### What it protects, and what protected it before

D141 asks one question per pull request: does the change reach what a browser draws at all?
When the answer is RUN, until this entry the whole `design-check` matrix loaded every
`app/tests/*.spec.ts` file, on every shard. It ran the same six shards whether a branch
touched `#/inventory` alone or every screen in the app. That was never wrong. Every spec
answers to a real assertion. Playwright's own default `testDir` sweep is the safe starting
point. **What protects the outcome now**: D141's own argument, one level down, over which
files inside a running matrix actually load.

### The measurement, so nobody oversells it

A derived spec→file map was measured over the last 30 merged PRs before this landed. It would
have narrowed the spec list on 6 of 30, with a median saving of 0 specs. That is real and
small. The worker-count change is the lever that moves wall-clock. This is the lever that
occasionally moves which specs load. It is built alongside the first because the owner asked
for both, not because it was the bigger win. Most PRs touch a shared surface — the kit, the
shell, a config file — or a path the map cannot resolve. Both answer "every spec" by design
(see below). Most runs are unaffected, on purpose.

### How it is derived, never typed

`scripts/browser-scope.py specs` computes, at run time, which specs a change can reach:

- **A spec's own relative import closure.** `import`/`export ... from './x'` and CSS
  `@import`, followed transitively. Comments are stripped first.
- **Plus the closure of every screen whose route hash the spec's body names.** `#/inventory`,
  `#/review`, and so on, matched against `app/src/App.tsx`'s own `ROUTES` table. That is the
  same table `make orient` reads one screen at a time, read here for every route at once.
- **Plus every screen, when the spec calls `routesFromNav(`.** `cursor.spec.ts`,
  `button-stack.spec.ts`, `copy-budget.spec.ts`, `page-edge.spec.ts` and `wide.spec.ts` each
  sweep whatever the nav currently draws. A change to any screen is a change to what they
  assert.

**A shared surface selects every spec, not a narrower guess.**
That means `app/src/kit/`, every file under it, `tokens.css`, `base.css`, `App.tsx`/`App.css`, `main.tsx`,
`index.html`, `app/public/`, every file under it, a non-spec `app/tests/*` file, and the config and package
files (`playwright.config.ts`, `vite.config.ts`, `devPort.ts`, `design-check-reporter.ts`,
`package.json`, `package-lock.json`, every `tsconfig*.json`). It also means anything already
in D141's own top-level `SCOPE` outside `app/` — the Makefile's `design-check` recipe,
`check.yml`, `browser-scope.py` itself, `suite-lock.py`.

### What the fail-open covers, and why each direction picks every spec

This is D141's own argument, one level down. A filter too narrow silently stops testing
something. A gate that quietly narrows is worse than one that does not narrow at all — the
green is still believed either way. Every direction below answers **every spec**, never a
narrower guess, and prints its reason by name:

- no merge-base against the PR's base
- an unreadable diff
- an empty diff (more likely a wrong base than an empty change)
- a changed path under `app/` that no spec's derived closure reaches (an unmapped
  file is a gap in the map, never a license to skip it)
- a changed path outside `app/` already in D141's top-level `SCOPE`
- a changed path carrying whitespace. `make` word-splits `PW_ARGS`. A spaced path would
  silently become two filters. The classifier cannot even name it correctly, let alone
  narrow to it.
- `PKMNSCAN_BROWSER_SCOPE=off` — D141's own escape hatch, reused rather than duplicated

**Never a block-list.** `docs/debts/` already records what a guessed block-list let through
once. A real TCGplayer Staged import got past one written by name. The same argument holds
here: an allow-list that fails open cannot silently widen a gap.

### The pass-record partial rule

D136's `already-passed` job treats an unexpired `design-check-pass-<tree>` artifact as "this
tree was fully tested," with no notion of which specs ran. A partial pull-request run could
leave one of those records. A later push to main on the same tree would then skip a matrix
that never loaded every spec. So `design-check-passed` in `check.yml` now also reads
`needs.browser-scope.outputs.partial != 'true'`. An ordinary full run still writes the record
exactly as before. Most PRs touch a shared surface or an unmapped file, so this is the common
case. A genuinely narrowed run writes nothing. Main's own push then finds no record for that
tree, and it runs the full six-shard matrix, same as it always did before this landed.

### What this does not touch

No spec's own assertions changed. No case in a full matrix run changed. The full matrix —
main's push, and any PR that is not narrowed — still runs every case in `app/tests/`, exactly
as `playwright.config.ts`'s `testDir` already defines it.

### Governed by

D141: fail-open, a derived list with a mechanical reader. Amended here — the browser matrix's
own spec loading is now also scoped, alongside whether it runs at all. D136: amended
separately, same ruling, for the worker count. D18: `browser-scope.py` writes nothing
decision-bearing. `specs` only prints and writes `GITHUB_OUTPUT`/`GITHUB_STEP_SUMMARY`, which
the workflow reads back the same run. D173: the mechanism is `scripts/browser-scope.py
selftest`, wired into `make check`, plus `make docs-audit`'s `spec map` row.
