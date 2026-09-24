---
name: text-density
description: Run the on-demand text-density review over Banchi's own screens. Use when a session is asked to review copy, cut words from a screen, or repeat the 2026-09-23 density review's method, and D194's pinned ceiling is retired.
---

# Text density review

`D-text-shape-checks` replaced D194's pinned word ceiling with three things. None of them is
a count. Two are gates: `app/tests/text-shape.spec.ts` (repetition and sentence shape) and
`app/tests/machine-words.spec.ts` (D196's own rendered-text gap). The third is this tool. It
is a repeatable pass a session runs, never a gate. `docs/decisions/D194-copy-ratchet.md`'s
"Superseded" note and `D-text-shape-checks` carry the full argument.

## Before you run it

1. A dev server must already answer this checkout's own port. Start one: `make dev` (blocks;
   run it in the background) or `make up`.
2. Confirm you are in your own checkout. `git rev-parse --show-toplevel` must print YOUR
   worktree path. A copied tree with no `.git` falls back to a shared port — see CLAUDE.md's
   HAZARD note.

## Running it

```
make text-density                          # every route, 1440, light
make text-density ARGS="--route /pricing"  # one route
make text-density ARGS="--theme dark"      # dark theme
make text-density ARGS="--width 390"       # phone width
```

It prints a table: `main` (words inside `<main>`), `total` (the whole page), `fold` (words
above the fold, on any element), `prose` (blocks of six-plus visible words — the same ruler
`app/tests/textShape.ts` uses for its own repeated-fact check), and `proseWords`. It writes
one report to `.serve/text-density.json`, gitignored — a receipt for that run, never a pin.

## Reading the table

A high `main` figure on its own is not a defect. Read the route in a browser next to the
number. Ask three things, in the 2026-09-23 review's own order:

1. **Does a sentence repeat itself?** The same fact, stated twice on one screen, or the same
   sentence on three or more cards. `app/tests/text-shape.spec.ts` already gates this — if
   you find one it missed, that is a bug in the check, not just a copy fix.
2. **Is a sentence doing the layout's job?** A caption that only restates its own heading, a
   subtitle a control already states. Cut it; the control still says it.
3. **Does the prose explain mechanism?** A pipeline noun, a decision id, a file path.
   `app/tests/machine-words.spec.ts` gates this one too. Check its pending list
   (`app/tests/machine-words-allow.json`) before you assume that a hit is new.

## What this tool does not do

It never asserts. It never fails a build. It has no opinion on whether a word count is too
high. That judgement is why D194's ratchet was retired in the first place. It only shows the
number, so a session, or the owner, can look and decide.

## If a screen looks wordy and the two gates are silent

That is the case this tool exists for. A screen can be dense with short, non-repeating, real
sentences, none of them over 25 words, none of them a machine noun. Read the top prose blocks
this tool prints, or open `.serve/text-density.json` for the full list. Judge them by hand,
the way `docs/reviews/ux-2026-09-23/density.md`'s own cut list was built.
