---
name: text-density
description: Run the on-demand text-density pass over Banchi's own screens and read its cut table. Use when a session is asked to review copy, cut words from a screen, or repeat the 2026-09-23 density review's method, now that D194's pinned ceiling is retired.
---

# Text density pass

`D-text-shape-checks` replaced D194's pinned word ceiling with three things. None of them is
a count. Two are gates: `app/tests/text-shape.spec.ts` (repetition and sentence shape) and
`app/tests/machine-words.spec.ts` (D196's own rendered-text gap). The third is this pass. A
session runs it on demand. It is never a gate. `D-text-shape-checks` carries the argument.

## Running it

```
make text-density                                  # every route, 1440 and 390
make text-density ARGS="--route '#/pricing'"       # one route
make text-density ARGS="--route '#/' --top 8"      # more prose blocks per route
make text-density ARGS="--json"                    # the raw measurements
```

It needs no dev server and no store. It runs `app/tests/text-shape.spec.ts` in a report mode
(`TEXT_DENSITY=1`). That spec sweeps every route through `app/tests/routeSweep.ts`: the
populated fixture of `app/tests/routeFixtures.ts`, each screen read only once it is loaded.
So the table shows the same screens, in the same state, as the gates. Playwright starts this
checkout's own Vite, or reuses the one already on its port. Every read is stubbed.

Before a run, confirm you stand in your own checkout: `git rev-parse --show-toplevel` must
print your worktree path. Two worktrees can derive the same port. If a server that is not
yours answers your dev port, stop and say so.

## Reading the cut table

For each route and width the table prints:

- The view's visible word count.
- Its largest prose blocks, with word counts (a prose block is a block element with six or
  more visible words).
- `REPEATS` — one sentence on three or more cards or rows.
- `FACT` — one number-plus-noun fact stated in two prose blocks.
- `LONG` — one sentence over 25 words.
- `CAPTION` — a caption that repeats most of its heading.

It writes one receipt, `.serve/text-density.json`, gitignored. It never touches
`.serve/design-check.json`.

A high word count on its own is not a defect. Open the route next to the table. Ask three
things, in the 2026-09-23 review's own order:

1. **Does a sentence repeat itself?** The two gates already fail on `REPEATS`, `FACT`, `LONG`
   and `CAPTION`, unless a lane's pending entry lists the finding. Check
   `app/tests/text-shape-allow.json` before you treat one as new.
2. **Is a sentence doing the layout's job?** A caption that only restates its own heading, or
   a subtitle that a control already states. Cut it. The control still says it.
3. **Does the prose explain mechanism?** A pipeline noun, a decision id, a file path.
   `app/tests/machine-words.spec.ts` gates this one. Check its pending list,
   `app/tests/machine-words-allow.json`, before you treat a hit as new.

## What this pass does not do

It never asserts and never fails a build. It has no opinion on whether a word count is too
high. That judgement is why D194's ratchet was retired. It reads only each route's landing
state: no sheet, modal, toast, drawer or palette is opened.

## If a screen looks wordy and the gates are silent

That is the case this pass exists for. A screen can be dense with short, real sentences that
never repeat, never run long and name no machine word. Read the largest prose blocks in the
table. Judge them by hand, the way the 2026-09-23 density review built its cut list.
