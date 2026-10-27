# D305 — The reaper stops only its own

**Built after an incident D43 did not anticipate.** An agent's own worktree vanished mid-session. It carried on inside another session's worktree. The two trees look identical from inside the wrong one. It ran `make reap ARGS=--confirm`.

D127 did exactly what it was built to do. It stopped every process under that checkout, except the caller's own chain. One of those processes was the OWNING session's own `scripts/revert-audit.py` pre-push check, mid-run. That session's push then failed.

**D43's premise was one checkout, one session.** Every process a session needs to kill sits under its own checkout. Everything it must not kill sits under somebody else's. So "under the checkout" was a fair question for `verdict_for` to answer. Two sessions in one tree was a case nobody had hit. Now both sessions' processes answer "yes" to that question.

### The ruling

Reap stops only what the caller started. Tag each process with its owner's id. `--confirm` stops only processes carrying the caller's tag. It lists every other process, and stops none of them. This belongs in Banchi, not the parent repo. It limits the damage when an agent lands in the wrong tree.

**Narrowed later:** the orchestrator's blanket sweep stays wide. A subagent's blanket sweep is limited to its own tagged processes. A bare `make reap ARGS=--confirm` with no target named stays D127's full-checkout sweep, when the caller is the top-level session a person drives. That case is unchanged in every respect. The same bare `--confirm` from a subagent stops only pids tagged with that subagent's own session id. See "What this leaves open" below for the gap this choice leaves.

### The sketch's mechanism failed a real measurement

The sketch read an env var back off a pid this session did not start, with `ps -E` or `ps eww`. **Measured on this machine** (macOS 26, Darwin 27.0.0): `ps eww -p <pid>` prints no environment column for a process this session did not invoke `ps` from directly. Root does not help either. A real `subprocess.Popen` child, carrying a marker in its own environment, showed nothing readable. The environment is not there to read on this machine, whatever the sketch assumed about an older macOS. So a tag cannot be read back from the process table after the fact, here, at all.

**The working mechanism needed no new primitive.** It needed only `scripts/reap.py`'s own pattern, one register down. `protected_pids` already solves this shape for D138's one supervisor. It uses a marker FILE under `.serve/`, holding a pid. `_descendants` walks DOWN from it, to reach children spawned after the marker was written. `scripts/reap_mark.py` generalizes that from "the one supervisor" to "whichever session's launcher wrote it". It writes one JSON file per launched root, under `.serve/owners/<pid>.json`: `{pid, owner, label, startedAt}`. `reap.py` now reads the whole directory, not one fixed name.

**One shell line is the whole mechanism.** A Makefile recipe runs each line as its own child of `make`. A mark written on one line and a server started on the next are SIBLINGS. The mark would record a pid already gone by the time anyone reads it. So every launcher runs one line:

```
scripts/reap_mark.py <label>; exec <the real command>
```

Where the launcher must survive to do its own cleanup, as `design-check`'s suite-lock does, the line drops `exec` and keeps the `;`. `reap_mark.py`'s own `os.getppid()` names that one shell. That shell either `exec`s into the real, long-running process, keeping the same pid, or stays its direct parent for its whole life. **This was measured on a real child process, not asserted.** A throwaway `sh -c "python3 reap_mark.py x; exec sleep 60"` recorded pid 22222. `ps` on pid 22222 a moment later showed `sleep 60`, the exact process the mark names, under the exact pid it recorded.

**The owner is `CLAUDE_CODE_SESSION_ID`, read directly.** Claude Code already sets it. Every child inherits it by ordinary fork and exec. That is not the `ps -E` read-back the sketch assumed, and this file measured that the read-back does not work. **The reaper's older method** solved a neighboring "whose is this" question with a Bash-wrapper argv fragment. No per-session id existed on this machine at that time. That fragment answers ANY session, never WHICH session. That method is not replaced. This entry answers a question it never asked.

### Every launcher, found by reading the code

Four targets call `$(PORT_CLAIM)` first, as their own recipe line: `make dev`, `make server`, `make up`, and `make design-check` (and its `-quiet` twin). `$(PORT_CLAIM)` runs `scripts/port-slots.py claim --quiet`. That line could not be the mark site, since it is a sibling of the real server, never its ancestor. Each target's own FINAL recipe line now marks first.

`scripts/launch-config.py` also calls `port-slots.py claim`, through its own `claim_slot()`. It starts no long-running process of its own. It writes `.claude/launch.json`, then exits. It needs no mark, and gets none. The brief named it as a possible launcher. Reading the code showed it starts nothing. That finding is recorded here, not dropped.

### The four cases `_ownership_verdict` decides

1. **Tagged with the caller's own id.** Always allowed, explicit or blanket, orchestrator or subagent. This is the ordinary case: a session stopping the server it just started.
2. **Tagged with a different, non-empty id.** Never allowed, with one exception in case 4. Naming a pid on purpose does not un-own it. D127's asymmetry still holds: a false refusal costs one sentence, and a false permission costs somebody their process.
3. **Untagged, and named explicitly.** Untagged means that there is no mark, or a mark with an empty owner. A process started before this change, by hand, or by a launcher outside a Claude Code session, is untagged this way. Named explicitly means that the target is a `pid:`, `port:` or `match:` form. This is allowed. The caller pointed at exactly this process, the same judgment those forms carried before ownership existed.
4. **Untagged, and reached only by a blanket sweep** (no target named). Allowed for the top-level session. Refused for a subagent. This is the owner's own narrowing. It is the one case where who is asking changes the answer.

**The orchestrator's blanket sweep is wider than the other three cases, on purpose.** A bare `--confirm`, with no target, run by the top-level session, skips ownership entirely. It stops everything `verdict_for` already calls `OURS`, including processes tagged to another session. That is exactly what D127 built, before this entry. The ruling in plain form: everything under the checkout except the caller's chain. It names no exception for another session's tag. It does not close the exact incident, had the wandering session been the orchestrator itself. See the next section.

### Who is the caller: measured, not assumed

`is_top_level_caller()` reads three env vars Claude Code already sets. None were invented for this entry. `CLAUDE_CODE_CHILD_SESSION=1` is set on a subagent. It is absent on the session a person types into. This was measured directly, on a real spawned subagent, while this entry's code was built. `CLAUDE_CODE_HOST_SESSION_ID` corroborates it. On a subagent it names the orchestrator's own session id, which differs from `CLAUDE_CODE_SESSION_ID`, this process's own id. A top-level session has nothing above it to name. So its host id is absent, or equal to its own.

**The default reading is narrow.** Absence of the child-session marker is not proof of the top level. A bare terminal, CI, or a future Claude Code build that spells this differently all read the same way. So `is_top_level_caller()` returns true only when every signal agrees. A false "narrow" costs an orchestrator one refused blanket sweep, still reachable by naming a target. A false "top level" is the incident this entry exists to close.

### What this leaves open

A misrouted TOP-LEVEL session, running a blanket `--confirm` in the wrong checkout, is not covered. The owner's narrowing draws its line at subagent versus orchestrator. It does not draw a line at checkout versus checkout. A person driving the top-level session keeps the same full-sweep power D127 always gave it. Had the incident's wandering session been the top-level one, this entry would not have stopped it. This is a scope choice, not an oversight. It is recorded here so nobody rediscovers it by hitting it again.

**A caller with no Claude Code signal at all reads as narrow, on purpose.** A bare terminal, or a session from another tool such as Codex, sets none of `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION` or `CLAUDE_CODE_HOST_SESSION_ID`. `is_top_level_caller()` returns false the moment `caller_id()` is empty. That is case 4's narrow reading, the same one a subagent gets. So a bare `--confirm` from such a caller LISTS every untagged process under the checkout. It STOPS none of them, the same as for a subagent in someone else's tree. This is the narrow default doing its job: a caller this file cannot place is never assumed to be the orchestrator. The remedy is naming the target directly. `pid:`, `port:` and `match:` still take an untagged process, from any caller. `_ownership_verdict` prints that remedy in the refusal itself.

**A launcher that starts a server some other way leaves it untagged.** By hand, from a bare terminal, or from a tool this repo does not wrap, all read this way. That is the correct, honest answer (case 3 or 4 above), not a gap to close. A mark this file did not write is not evidence this file can invent.

**A mark is an implementation detail of this repo's own launchers.** A process `make dev` started on main before this change lands, still running when a branch's session reaps its own checkout, reads as untagged. Case 3 or 4 applies again. It is listed, and left alone, unless named explicitly.

### Verification

`make reap-selftest` proves each rule by violating it, against real processes in a throwaway checkout. A `--confirm` stops a process tagged with the caller's own id. It lists, but does not stop, a process tagged with another session's id under the same checkout. A subagent's blanket sweep lists but does not stop an untagged process. The orchestrator's blanket sweep stops that same untagged process. Both directions are proved, not only the restrictive one. An explicit `pid:` still takes an untagged process, even for a subagent. The caller's own chain is never stopped, D127's original case, unchanged. `reap_mark.py`'s own mechanism (one shell line, mark then exec, one pid throughout) is proved directly, not only through the launchers that call it.

### What the PreToolUse hook does with this

A raw `kill`, `pkill` or `killall` always names its target. That is what `pid:`, `port:` and `match:` do on `make reap`'s own command line. A hand-typed kill has no blanket spelling to begin with. So `--hook` judges every `OURS` target through cases 1 to 3 above, the explicit branch. It does this whether the session running it is the orchestrator or a subagent. A raw kill that would hit a pid tagged to another session is BLOCKED, the same as an explicit `make reap` targeting it would be refused. Case 4's wider orchestrator allowance has no equivalent here, since there is nothing here for it to apply to.

### No install

`reap.py` reads `.serve/owners/` inside whatever checkout it is asked about. So it sees a project's own marks from the repo's own copy. Nothing is installed. The user's Claude bin directory is claude-settings' `install.sh`'s, and `make janitor-install` copies nothing.

Reap's "under this checkout" is the verdict's own test. A nested worktree is another checkout.

A process whose session is gone is offered, never reaped.
