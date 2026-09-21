# Where this stands, 2026-09-20

Paused at the owner's word with every lane built and reviewed, and nothing merged.
No agent is running. Nothing is half-finished.

## The five branches, all built and all reviewed

Each lives in its own worktree under `.claude/worktrees/agent-<id>/`. None is pushed.
None has a PR. `make check` passes on every one, independently re-run by a reviewer.

| Branch | Head | What it carries |
| --- | --- | --- |
| `worktree-agent-ad5bd1304d0a7bea6` | `845ccde0` | `css-var-check` + selftest (21 cases) + the five undefined-property fixes |
| `worktree-agent-a1fca84e56d2a9949` | `120474f6` | `--bn-ink-3` darkened, four unnamed registers named, Fulfillment consolidated |
| `worktree-agent-ad76bcb8686577a1b` | `c466f794` | Inventory, Orders, Graveyard defects |
| `worktree-agent-ac86c5a49aef02cd0` | `d6b7c873` | Pricing, Sales, Product, Codes defects + review follow-ups |
| `worktree-agent-a63f666e7288731a3` | `6ea60998` | Shell rail resize, Home timing, Review reason code removed |

## Next action, in order

1. **Integrate.** One integration branch, each lane's commits kept, on the owner's word.
2. **Re-measure one thing on the merged result.** `.graveyard-condition` was moved onto
   `--bn-ink-3` by one lane and measures 4.43:1 against that token's OLD value — 0.07 short
   of the floor. Another lane darkened the token to 4.85:1. Neither lane is wrong and
   neither could see it alone; the fix only completes once both are on one branch. Verify
   it there rather than assuming it.
3. **Run the cleanup lane on top of the integration branch**, not against main — its four
   items touch files owned by all four lanes. The owner approved all four:
   `font-weight: 650` in six files; `.bn-rule` off the faint token; wire `.review-key` onto
   the new `.bn-kbd-lg`, which has zero callers until then; `.bn-faint` applied to real
   data text in `Graveyard.tsx` and `Codes.tsx`.
4. **Then round two**, deferred by the owner until this lands: the literal-vs-token sweep
   (~40 literals duplicating a token exactly) plus a guard so they cannot return. The
   tokens it needs now exist.

## The one gap nobody could close

**No worktree can reach real data**, so no builder and no reviewer has seen these screens
with actual cards in them. Every visual verdict in this effort is against an empty store,
a demo seed, or a patched `fetch`. Recorded as UNKNOWN throughout, never as a pass.

The owner granted permission to fix this just before the pause: feed the agents real data,
however it can be done without conflicts. **Not yet acted on.** The shape that looks right:
copy `inventory/store.sqlite` (67MB) into a verification worktree so the real store is
never written, and run one verification pass against the INTEGRATION branch rather than
four partial passes against four lanes.

**Two things to settle before doing that.** The photo corpus is 5.4GB, so it wants a
read-only reference rather than a copy — and whatever is chosen must make a photo delete
impossible, not merely unlikely. And the real store holds 543 Pokemon and 2,967 Riftbound
cards: any pooled code-card photograph is a bearer instrument, so no image from that
verification may be committed anywhere, and `captures/` being gitignored is not on its own
a sufficient answer.

## Still the owner's, unanswered

- The rail resize needs a real window drag across 1280. This environment's viewport
  emulation never fires the events, proven by control experiment. The headline fix of the
  whole effort is UNKNOWN until someone drags a window.
- `.claude/settings.local.json`'s two override keys. Cannot be removed from inside a running
  session — verified three times. Until then every commit here needs `PKMNSCAN_DOCS=off`,
  which the owner granted for this session only.
- The word ratchet, which the owner would rather rethink than re-pin. Two screens will
  exceed their ceilings. It counts screen-reader-only text against a visible-word budget,
  which may mean it measures the wrong thing.

## Exhaust to sweep

Two dev servers are alive and belong to finished agents: `:5201`
(`agent-a63f666e7288731a3`) and `:5468` (a reviewer's disposable worktree at
`/private/tmp/review-120474f6`, which also wants `git worktree remove --force`).

Neither can be stopped from here — `make reap` only sees its own checkout, by design.
Do not run `make janitor ARGS=--confirm` to get them while any agent is live; it has
removed a worktree mid-build before.

## Read these first

`RANKING.md` for what was found, `TASTE-CALLS.md` for why each judgement call went the way
it did and where to reverse it, `FOLLOW-UPS.md` for the tooling friction this cost.
