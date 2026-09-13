## D-heartbeat-is-a-caller — The repo-state heartbeat is a thin caller of what already exists, and it remembers across runs in a file

**docs/GATES.md item 24 ("A durable scheduled heartbeat that watches repo state across sessions") is BUILT.** `scripts/heartbeat.py`, added 2026-09-13.

### What it answers, and what it does not build to answer it

Every session here sees only its own tree and its own branch — a worktree cannot tell whether
another one has gone stale, whether a PR nobody touched has sat green and unmerged for a day,
or whether a claim it made an hour ago has since been taken by main. Item 24 names six things
nobody is positioned to ask from inside a session. **Four of them are already answered, in full, by `scripts/coordinator.py --json`**: open PRs pinned to their head SHA, `id claims` (out
of `docs-audit.py`), every worktree holding uncommitted work, and live sessions read from the
console app's own records with the start time checked.

Building a second reader of those four facts was the first draft of this entry and it was
wrong — check whether the primitive already exists before designing around its absence. So
`scripts/heartbeat.py` **calls** `coordinator.py --json` rather than re-implementing its
`verdict_for` precedence table (nothing reported / something failed / something still running
/ the required-check floor not satisfied / green) a second time, a copy that would drift the
first time D148's wait logic changes and this file's copy does not.

**What it adds is the two bullets coordinator does not answer:**

- **whether main's own last push is green.** `coordinator.py:block_main` compares
  `refs/heads/main` against `origin/main` — agreement, never CI — because the incident it
  exists for was a session running from a stale local main. Nothing there reads main's own
  check-runs. `block_main_ci` in the new file does: `branches/main/protection`'s required
  contexts and `commits/<origin/main's tip>/check-runs`, the same two reads
  `coordinator.py:block_floor` and `verdict_for` make for a PR head, pointed at main's own tip
  instead. Duplicated as a dozen lines rather than imported, because coordinator's functions
  are keyed to a `Floor` object built for a PR and constructing one for main would be more
  code than the duplication.
- **`make janitor`'s own preview**, in its own tier vocabulary (a merged branch no tree holds,
  a worktree with no live session) — never `--confirm`, because this file has read-and-report
  authority only and the underlying tool is invoked exactly the way a human would run it to
  look first.

### The two binding constraints, and how the file satisfies each

**Never a daemon.** `scripts/heartbeat.py` runs once and exits; nothing in it loops, sleeps, or
waits for a next tick. The cadence is the scheduled task's job, registered against the same
`mcp__scheduled-tasks` mechanism this environment already exposes for a periodic agent run — a
fresh Claude session invoking `python3 scripts/heartbeat.py --json` on a schedule the desktop
app owns, never a process this repository starts or keeps alive. There is no `make` target
that backgrounds anything; `make heartbeat` runs the script in the foreground and prints, the
same shape as `make status` and `make coordinator`.

**Each run is a fresh session with no conversation context.** The script itself starts knowing
nothing, and so would an agent session spawned to run it. Anything needing memory of a
*previous* run therefore lives in a file, never in a session:
`.serve/heartbeat/latest.json` is overwritten every run, `.serve/heartbeat/history.jsonl` gets
one appended line per run, and `diff_since_last` computes `new_since_last_run` by comparing
this run's open-PR numbers and worktree paths against the *previous* `latest.json` — which is
the "a pull request now conflicting with a live session that has not been told" bullet,
answered mechanically: whether something has been told is exactly whether it was already in
the last report. Both constraints point the same way, which item 24's own note already says:
**read-and-report authority, never merge authority.** The script never passes `--confirm` to
anything it shells out to, and it writes nothing outside `.serve/heartbeat/`.

### What this is not, on the record — because two earlier drafts of this same session built it wrong

This entry exists partly to correct its own history. Two intermediate drafts, produced before this one, built a **client-side scheduler inside `app/src`** — a `subscribe(job, { everyNBeats })` primitive meant to share one `setInterval` between the sidebar's server-status
dot and a future Orders live-arrival poll, with tab-visibility awareness and failure backoff.
That work was deleted from this branch before landing. **It was answering a different, real bug** (`app/src/App.tsx`'s "Server online" dot staying green through several seconds of every
request failing, from the 2026-09-13 UX walkthrough) that has nothing to do with item 24 beyond
sharing the word "heartbeat" — GATES item 24 is about *this repository's own state across
sessions and branches*, never about a browser tab's connection to its own capture server. That
fix belongs to whichever session owns `useServerPresence` and `app/src/server.ts`, and is not
this entry's to claim. `docs/DEBTS.md` §10 is unchanged by this entry: no client-side clock was
added by the work this entry actually ships.

### What no check can see

**NOT MECHANIZED:** whether the report this script produces is actually READ by anyone is not
something a machine can verify — the same limit `docs/GATES.md` item 24's own note names for
"read-and-report authority": a heartbeat that fires into a file nobody opens is indistinguishable,
from the repo's own point of view, from one that fires into nothing. What is mechanized is
narrower and real: `scripts/heartbeat.py` exits non-zero when any of its four blocks could not
be read at all (the same "silence must never render as success" rule `coordinator.py` states
for itself), and `docs/map.py`'s `build order mirror` row keeps this entry's step (24, in
`SHIPPED` now) reconciled against `docs/GATES.md`'s own numbering.
