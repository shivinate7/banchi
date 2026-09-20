# Friction found while building, for the owner to resolve later

Recorded as encountered during the 2026-09-20 UX review and the fixes that followed.
None of these blocked the work. None were fixed, on the owner's instruction that repo
rules and tooling questions are settled after the work, not during it. Each entry says
what happened, what it cost, and what would close it.

Open as of 2026-09-20.

## Infrastructure that fights parallel agents

### 1. `preview_start` returns another session's checkout and port

Twice, a builder in its own worktree called `preview_start` with its own `launch.json`
config naming its own port, and got back a server rooted in the ORCHESTRATOR's checkout,
on the orchestrator's port, attributed to the agent's own session id.

An agent cannot tell this has happened except by noticing the reported `cwd` looks wrong,
and cannot tell a server of its own from an inherited one at all, because the tool returns
no PID. One agent noticed and called `preview_stop`, which was a guess either way.

**Cost:** one incident investigation. Benign — the port was the orchestrator's own and
nothing was running on it.

**Would close it:** agents run `make dev` over Bash instead, which is what every brief
now says. A real fix would have `preview_start` refuse, or at least report, when the
config it resolved does not belong to the caller's checkout.

### 2. The Browser pane is shared, and concurrent agents fight over the tab

One lane reported its tab "repeatedly hijacked to other worktrees' ports" and had to
re-confirm its URL immediately before every single reading. Another lane could not get
screenshots at all for a whole session, and a third reported the pane going
non-displayable partway through, which cost real coverage: 1280px and light theme are
UNKNOWN across several of the review files for exactly this reason.

**Cost:** the largest single source of missing coverage in the whole review.

**Would close it:** a browser context per agent, or an explicit claim on the pane.

### 3. Viewport emulation never fires `matchMedia` or `ResizeObserver`

The sidebar's resize behaviour — the highest-value fix in the review — could not be
verified. `window.innerWidth` and a fresh `matchMedia().matches` both report the new size
correctly, but no existing `MediaQueryList` change event ever fires, and a plain
`ResizeObserver` attached by hand never fires either, despite `clientWidth` genuinely
changing.

Proven to be the tool and not the code by control experiment: the PRE-EXISTING `useMedia`
mechanism, already shipped and untouched, shows identical non-reactivity.

**Cost:** the headline fix of this whole effort is recorded as UNKNOWN rather than passed.

**Would close it:** nothing available here. It needs a real window drag, which is the
one follow-up the owner has agreed to do by hand.

## Ownership and cleanup

### 4. Nobody may stop an orphaned process in another checkout

`scripts/reap.py` only recognises processes started under the running session's own
checkout, which is correct and is what D43 asks for. The consequence is that a reviewer's
own disposable dev server, started in a disposable worktree, cannot be stopped by the
reviewer, by the orchestrator, or by any session but the dead one that started it.

`PKMNSCAN_KILL=off` exists for this and was refused by the auto-mode safety classifier as
a bypass attempt, so the documented escape hatch was not reachable either.

Two servers were left alive this session (`:5201`, `:5468`) plus a disposable worktree at
`/private/tmp/review-120474f6`.

**Cost:** accumulating exhaust nobody is allowed to sweep.

**Would close it:** `make reap` growing a way to act on a process whose own session is
provably dead, which is the same liveness oracle the janitor already uses.

### 5. `make janitor ARGS=--confirm` is unsafe while agents are live

It has previously removed a worktree mid-build. So the one tool that WOULD clean up item 4
cannot be run during exactly the period that generates the mess.

**Would close it:** the same session-liveness oracle, consulted before removing a worktree.

## Gates that block or mislead

### 6. `.claude/settings.local.json` cannot be repaired from inside a running session

A stale subagent-model override with no expiry fails `make docs-audit`'s `subagent
override` row, which blocks EVERY commit in that worktree. Removing the two keys does not
work: the runtime rewrites the file back within the same Bash call. Verified twice. The
auto-mode classifier also refuses the edit outright as self-modification.

**Cost:** several rounds, and every commit in that worktree made through the hook's own
`PKMNSCAN_DOCS=off` hatch rather than with a passing gate.

**Not a cost:** the orchestrator twice told the owner this meant subagents were running on
Opus rather than Sonnet. That was inferred from the file and never observed. The owner
confirmed the agents were on Sonnet throughout. The problem here is only the gate.

**Would close it:** the audit row reading the file's mtime or the session's own start
time, so a live session's own override is not indicted as forgotten.

### 7. A worktree has no capture server, so data-bearing screens cannot be seen

Correct by design (D43), but it means an agent fixing a screen sees the "server did not
answer" empty state and nothing else. One lane worked around it by patching `window.fetch`
with fixture shapes lifted from an existing spec, which proves the component renders the
fixture and not much more. Another could not screenshot the four screens it had just
changed.

**Would close it:** a documented way to seed a worktree store for visual work — the demo
seed is close, but it does not record every route (`/pipeline/value` and
`/orders/walk-plan` both 404 in the demo build).

### 8. The `js breakpoints` check does not see a bare numeric literal

A builder believed `window.innerWidth < 1280` was failing D123's check and refactored to
satisfy it. The check never saw that code: its regex only matches matchMedia-shaped
strings `(max-width: NNNpx)`. The refactor was still an improvement, but it was made for
a reason that was not true.

**Cost:** a wrong justification written into a commit message, caught only because a
reviewer ran the checker directly instead of believing the claim.

**Would close it:** the check reading bare numeric comparisons against `innerWidth` too,
or its own docs saying plainly what it does not cover.

### 9. The copy ratchet counts screen-reader-only text

`copy-budget.spec.ts` counts words from `innerText`, which includes `.bn-sr` content. So
adding an invisible label for a screen-reader user spends the visible-word budget.

Recorded without a recommendation, because whether that is a defect depends on what the
ratchet is FOR — if it is about visible density, sr-only text should not count; if it is
about total reading burden, it should.

## Smaller things, recorded without argument

- `make map-fix ARGS=--write` is needed after adding a comment that cites a decision id,
  and nothing says so until the `repo map` row refuses the commit.
- `docs-audit` reports ~32 pre-existing "code changed, its doc did not" advisories on a
  clean tree, which makes a genuine new one easy to miss.
- `.bn-kbd-lg` was added to the kit this session and has zero callers, pending another
  lane wiring `.review-key` onto it. An unreachable primitive until then.
- `--bn-ink-3`'s new light value clears 4.5:1 on `--bn-surface-2` by 1.2%. It passes with
  no headroom for a future surface tweak.
