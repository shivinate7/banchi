#!/usr/bin/env python3
"""Stamp the process a launcher is about to become with the session that started it.

WHY THIS EXISTS. D127 taught `scripts/reap.py` to tell "under this checkout" from "not". It
never had to tell "this session's" from "some other session's in the SAME checkout", because
D43 gave every checkout its own ports and store on the premise that one checkout holds one
session. The 2026-09-27 incident broke that premise: an agent's worktree vanished, it carried
on inside another session's worktree, and `make reap ARGS=--confirm` there stopped that
session's own pre-push check along with everything else. Two sessions CAN stand in one
checkout, so "under the checkout" stopped being a fine enough question.

THE OWNER'S SKETCH WAS AN ENV VAR, READ BACK LATER WITH `ps -E`/`ps eww` ON THE PID THAT HOLDS
IT. MEASURED ON THIS MACHINE (macOS 26, Darwin 27.0.0) AND FOUND FALSE: `ps eww -p <pid>`
prints no environment at all for a process this session did not itself invoke with `ps` as a
direct parent, root or not. A real subprocess started with a marker in its own environment
came back with an empty environment column. So reading env back after the fact cannot be the
mechanism, whatever the sketch assumed about older macOS.

WHAT WORKS INSTEAD, AND WHY IT NEEDED NO NEW PRIMITIVE. `scripts/reap.py:protected_pids`
already solves this exact shape for D53's supervisor: a marker FILE under `.serve/`, holding a
pid, walked DOWN the process tree with `_descendants` to cover children the marker was written
before. This file is that same pattern, generalised from "the one supervisor" to "whichever
session's launcher wrote it": one JSON file per launched root, and `reap.py` reads the whole
directory and walks down from every live entry.

ONE SHELL LINE IS THE WHOLE MECHANISM — FOR A LAUNCHER THAT STAYS IN THE FOREGROUND. A Makefile
recipe runs each line as its OWN child of `make`, so `scripts/reap_mark.py dev` on one line and
`npm run dev` on the next are SIBLINGS — marking the first's pid records a process that has
already exited by the time anyone reads the mark. So `make dev`, `make server` and
`make design-check`/`-quiet` each run

    scripts/reap_mark.py <label>; exec <the real command>

as ONE recipe line. This script's own process is a genuine child of that line's shell, so
`os.getppid()` here names the shell — and the shell either `exec`s into the real command,
KEEPING THE SAME PID, or (where the launcher must stay alive to do cleanup, like
`design-check`'s suite-lock) simply runs the real command as its own child next and stays alive
throughout. Either way the pid this file records is a real ancestor of the launched server for
the whole of its life, which is what `_descendants` needs to be true — PROVIDED THE MARKED
PROCESS STAYS ALIVE, which is the one thing `make up` does not do.

`MAKE UP` CANNOT USE THIS SHAPE, AND THE 2026-09-27 REVIEW IS WHY. `scripts/serve.py:do_up`
`Popen`s a DETACHED supervisor (`start_new_session=True`) and returns within about a second —
by design, D138's "one process, detached." The Makefile line that ran `reap_mark.py up; exec
$(PYTHON) scripts/serve.py up` marked the shell that becomes `do_up`'s own short-lived process,
not the supervisor it spawns and orphans. Once `do_up` exits, that mark's pid is dead, the
supervisor has been reparented to init, and `_descendants` can no longer connect the two —
reproduced on this tree: a mark on the wrapper, a live server on an unrelated pid, and a
subagent's `--confirm` refusing to stop the very server it had just started. So `do_up` calls
`write_mark` BELOW DIRECTLY, on the real `Popen` result, the moment it has that pid — reusing
this file's writer rather than a second copy of it, per this project's own rule that a shared
shape is imported once rather than re-derived per caller. `design-check`/`-quiet` were checked
for the same shape and do NOT have it: `scripts/suite-lock.py:_spawn` calls `subprocess.run`,
which blocks, so that process stays the real child's direct parent for the whole run.

THE OWNER IS `CLAUDE_CODE_SESSION_ID` — READ, NOT INVENTED. It is a primitive Claude Code
itself already sets and every child inherits ordinarily (this is fork/exec inheritance, not
the `ps -E` read-back the sketch assumed and which does not work here). D175 solved the
neighbouring "whose is this" question in `janitor.py` with a Bash-wrapper argv fragment
because no such id existed on this machine in 2026-09-12; it exists now, and this file uses it
directly rather than re-deriving D175's fragment for a question it does not answer (D175
answers "is ANY session's", never "WHICH session's").

A LAUNCHER RUN OUTSIDE A CLAUDE CODE SESSION — a human's bare terminal — HAS NO SUCH ID, AND
THAT IS AN HONEST ANSWER, NOT A FAILURE. The mark is written with an EMPTY owner, which
`scripts/reap.py` reads as untagged: listed under a blanket sweep, never auto-stopped by one,
still reachable by naming it explicitly. See that file's own header for the full rule.

THE MARK NAMES A PROCESS, NOT A PID, AND `write_mark` READS THAT PID'S OWN PROCESS-START TIME
AT THE MOMENT IT WRITES — `reap.py:proc_start_epoch`, the same `ps -o lstart=` reading D175's
entry already uses for the neighbouring question. A pid is a number the OS hands out again. A
mark that only remembered the number would let a LIVE, UNRELATED later process inherit a dead
one's tag the instant the two numbers collided — found in the same review that found the `make
up` gap. `reap.py:_read_owner_marks` checks the live pid's CURRENT start time against what was
recorded, and deletes the mark on the read that finds it does not match, or finds the pid gone.

FAILS OPEN, LIKE EVERYTHING ELSE THIS INCIDENT TOUCHES. No checkout, no writable `.serve/`, a
`.serve` that is a stale file rather than a directory, a pid whose start time cannot be read —
none of these may stop the real command from running; they leave the process unmarked, which
`reap.py` treats exactly like a process nothing here has ever heard of.

NEVER INSTALLED AND NEVER IMPORTED FROM OUTSIDE THIS CHECKOUT. `make janitor-install` copies
`reap.py` alone to `~/.claude/bin` so its hook covers every project on the machine; this script
is a Banchi launcher's own business and reads nothing `reap.py` does not already read back.
`scripts/serve.py` imports `write_mark` below directly — a normal in-repo import, not a copy,
since `serve.py` is never installed anywhere either.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reap import checkout_root, proc_start_epoch  # local import — never copied out, see above


def write_mark(root: str, pid: int, label: str) -> bool:
    """Write `.serve/owners/<pid>.json` for `pid`, tagged with THIS process's own
    `CLAUDE_CODE_SESSION_ID` — the caller who is doing the marking, never the marked pid's own
    environment, which may not even be this session's to read.

    `pid`'s own process-start time is read fresh, right now, with the same `ps -o lstart=`
    `reap.py` will later check it against — not `time.time()`, which times this WRITE and not
    the process, and would still match a same-second pid reuse. Returns whether a mark was
    written; never raises, so a launcher that cannot write one still runs its real command.
    """
    started: Optional[float] = proc_start_epoch(pid)
    owner = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    owners_dir = Path(root) / ".serve" / "owners"
    try:
        owners_dir.mkdir(parents=True, exist_ok=True)
        record = {"pid": pid, "owner": owner, "label": label, "startedAt": started}
        (owners_dir / f"{pid}.json").write_text(json.dumps(record), encoding="utf-8")
        return True
    except OSError:
        return False  # a mark that could not be written leaves the pid untagged, never a hard failure


def main(argv: list) -> int:
    label = argv[1] if len(argv) > 1 else "process"
    root = checkout_root(os.getcwd())
    if not root:
        return 0  # no honest checkout to mark against — the real command still runs
    write_mark(root, os.getppid(), label)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
