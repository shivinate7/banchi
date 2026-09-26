## D291 — the fold's plan, D196 done, the build not yet

**The owner's ruling (RULINGS.md, Q6).** Fold Runs into Review. When cards wait, Review shows an "Identify N cards, ~$X" strip. Past runs sit behind a link. `#/runs` stays a route for links. Home's six-stage strip becomes five. The owner was told the counterpoint — the money press on a daily screen — and chose the fold.

**This entry is the plan, not the build.** The screen merge touches six files (`Runs.tsx`, `RunPanel.tsx`, `RunsComposer.tsx`, `RunRescue.tsx`, `RunsLog.tsx`, `RunsStage.tsx`), a route change, and Home's own strip. That is bigger than one round of the review lane. The lane's own brief says so: past that size, do the D196 half, write the plan here, stop, and report.

### D196 done this round

`RunPanel.tsx`'s `run-row-name` and `runs-detail-name` drew the run's own directory name ("demo-box3") as primary visible text — a repository path, D196. The box label already tells two runs apart, off `scopeOf(row)`, the row's own text. The raw id now rides a title tooltip only. That is the pattern `claim()`'s `raw` argument already uses elsewhere on this screen for a pipeline spelling. Two now-dead CSS rules got deleted. Two `run-panel.spec.ts` row selectors, which located a row by its raw-id text, moved to the title attribute instead.

### The fold plan

1. **`#/review`'s header grows one conditional strip.** "Identify N cards, ~$X", drawn only when the pipeline has cards waiting — `Runs.tsx`'s own pending-box read. It presses through to the existing Runs money-gate flow (`RunsComposer`). Absent when nothing is waiting.
2. **Past runs move behind a link.** Off that strip, or off a More menu on the Review header. Not drawn inline, the way `RunPanel`'s master list draws today.
3. **`#/runs` stays a registered route.** Its `ROUTES` entry is unchanged. A deep link and the palette's "Go to" keep working. A route is not a feature, and losing reachability is its own defect. It becomes off-nav, the same shape `App.tsx` already gives `#/product` and the kit — reachable, not a destination the nav points at.
4. **Home's six-stage strip becomes five.** That file is Home's own, not this lane's file scope. The orchestrator or Home's own lane carries this step.
5. **Every ICON-MAP row keyed to a `Runs*.tsx` file** (twelve rows, `review/ICON-MAP.md`'s Runs table) lands as part of this fold, once its files are settled into the merged screen. Converting them ahead of the fold would mean converting them again once the files move.

### What is still open, named rather than guessed

- The exact SHAPE of "Identify N cards, ~$X" — a strip, a banner, a card — is a design call for whoever builds the fold. It is informed by `docs/DESIGN.md` and the kit's own primitives.
- Whether "past runs" is a full list behind a link, or a summary count with the list one press further, is likewise open.
- The header rule applies to whatever the merged header ends up drawing. It should be built in from the start rather than retrofitted. That rule is the owner's 2026-09-24 tightening: at most one worded primary, and the rest are IconButtons or a More menu.
