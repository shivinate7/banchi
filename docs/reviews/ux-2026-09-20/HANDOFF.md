# Handoff, 2026-09-20

The session that produced this work was stopped by a monthly spend limit and resumed on
credits. This file is what a fresh session needs to pick it up.

**Nothing was lost.** Every lane had committed before the stop. Each agent, on resume,
confirmed its own work was already in place and that only its dev server had been reaped.
All five branches are now pushed to `origin`, so they no longer depend on a worktree
surviving.

## The work, all of it pushed

| Branch | Head | Carries |
| --- | --- | --- |
| `worktree-agent-ad5bd1304d0a7bea6` | `845ccde0` | `css-var-check`, its 21-case selftest, and the five undefined-property fixes |
| `worktree-agent-a1fca84e56d2a9949` | `120474f6` | `--bn-ink-3` darkened, four unnamed registers named, Fulfillment duplicates consolidated |
| `worktree-agent-ad76bcb8686577a1b` | `c466f794` | Inventory, Orders, Graveyard |
| `worktree-agent-ac86c5a49aef02cd0` | `d6b7c873` | Pricing, Sales, Product, Codes, plus review follow-ups |
| `worktree-agent-a63f666e7288731a3` | `6ea60998` | Shell rail resize, Home timing, reason code removed |

`claude/checkout-screens-ux-review-f97777` holds the review itself and its records:
`RANKING.md`, `TASTE-CALLS.md`, `FOLLOW-UPS.md`, `STATE.md`, and the sixteen per-screen logs.

Every branch passes `make check`, each verified by a reviewer that did not write it. None is
merged. None has a PR.

## Do this next, in this order

1. **Integrate the five into one branch**, keeping each lane's commits. The owner chose one
   integration branch over five PRs.
2. **Re-measure one pair on the merged result.** `.graveyard-condition` was moved onto
   `--bn-ink-3` by one lane and measures 4.43:1 against that token's OLD value, 0.07 short
   of the floor. Another lane darkened the token to 4.85:1. Neither lane was wrong and
   neither could see it alone. It only resolves once both are on one branch, so verify it
   there rather than assuming.
3. **Run the cleanup lane on top of the integration branch**, never against `main` — its
   four items touch files owned by all four lanes. All four are owner-approved:
   `font-weight: 650` across six files; `.bn-rule` off the faint token (3.34:1, worse than
   what was just fixed); wire `.review-key` onto the new `.bn-kbd-lg`, which has zero callers
   until someone does; and `.bn-faint` applied to real data text in `Graveyard.tsx` and
   `Codes.tsx`.
4. **Round two**, deferred until the above lands: the literal-vs-token sweep — roughly 40
   literals that duplicate a token's value exactly and will desync the day anyone re-tunes
   one — plus a guard so they cannot return. The tokens it needs now exist.

## Still the owner's

- **The window drag.** Whether the sidebar actually collapses on a live resize is UNKNOWN.
  This environment's viewport emulation never fires the events, proven by control experiment
  against a mechanism that already shipped. The headline fix of the whole effort needs
  someone to drag a real window across 1280 in both directions.
- **`.claude/settings.local.json`'s two override keys.** Cannot be removed from inside a
  running session — the runtime rewrites the file back within the same command, verified
  three times. Until they go, every commit in that worktree needs `PKMNSCAN_DOCS=off`, which
  the owner granted for that session only. **A new session must ask again.**
- **The word ratchet.** Two screens will exceed their ceilings. The owner would rather
  rethink the ratchet than re-pin it, having been shown it counts screen-reader-only text
  against a visible-word budget.
- **Real data for verification.** Granted in principle, not acted on. No worktree can reach
  the real store, so every visual verdict in this effort is against an empty store, a demo
  seed or a patched `fetch` — recorded as UNKNOWN throughout, never as a pass. Two things to
  settle first: the photo corpus is 5.4GB so it wants a read-only reference rather than a
  copy, and whatever shape that takes must make a photo delete impossible rather than
  unlikely; and the real store holds 543 Pokemon and 2,967 Riftbound cards, so any pooled
  code-card photograph is a bearer instrument and no image from such a run may be committed
  anywhere. `captures/` being gitignored is not on its own a sufficient answer.

## Found while recovering, and NOT this effort's to touch

A sweep of every worktree in this clone turned up uncommitted work belonging to other
branches and other sessions. None of it is from this effort. It is recorded because it is
exactly what `make janitor ARGS=--confirm` would destroy, and because nobody appears to be
watching it:

- `agent-a15a5d06b5e296393` (`claude/price-history-archive`) — 8 staged files including a
  decision rename.
- `agent-a7abe1aaf47590cb3` — the same 8, plus an unstaged spec change.
- `agent-a5f4ae6d7cc593381` — 3 modified, plus 2 untracked scripts (`derived-numbers.py`,
  `derived-numbers-pin.py`).
- `agent-af0216c6165c6e375` — 2 modified, plus 3 untracked (`line-anchors.json`,
  `line-anchors-pin.py`, `docs-audit-line-allow.txt`).
- `agent-a65220c112b67286b` (`claude/holdings-screen`) — 4 staged.
- `agent-a184713aa19ea527b` — 4 modified docs.
- `agent-ac9e8483a19d6d29e` — 1 modified, plus an untracked decision file.
- `agent-ab58854e8074072a9`, `agent-aafbf46670e6d6ef1`, `agent-af10730f59eb4b646` — untracked
  scripts and scratch directories.

**Do not run `make janitor ARGS=--confirm` until each of those has been claimed or written
off by its owner.**

## Exhaust from this effort

- `/private/tmp/review-120474f6` — a disposable review worktree, detached at `120474f6`, no
  edits, now process-free. Its reviewer's `git worktree remove` was refused by the shared-tree
  guard as a precaution. `git worktree remove --force /private/tmp/review-120474f6` clears it.
  Nothing is at risk if it is left.
- The dev servers on `:5201` and `:5468` have since been stopped.

## One thing worth carrying forward

The css-var guard went green three separate times over a defect that was really there: it
never scanned TSX for references, its brace-counter could be silenced by a stray `{` in a
string, and its comment stripper was corrupting three real files. Every one was found by
attacking it, never by running it. A guard that has only ever been run has not been tested.
