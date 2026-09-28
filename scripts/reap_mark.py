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

ONE SHELL LINE IS THE WHOLE MECHANISM. A Makefile recipe runs each line as its OWN child of
`make`, so `scripts/reap_mark.py dev` on one line and `npm run dev` on the next are SIBLINGS —
marking the first's pid records a process that has already exited by the time anyone reads the
mark. So every launcher instead runs

    scripts/reap_mark.py <label>; exec <the real command>

as ONE recipe line. This script's own process is a genuine child of that line's shell, so
`os.getppid()` here names the shell — and the shell either `exec`s into the real command,
KEEPING THE SAME PID, or (where the launcher must stay alive to do cleanup, like
`design-check`'s suite-lock) simply runs the real command as its own child next and stays alive
throughout. Either way the pid this file records is a real ancestor of the launched server for
the whole of its life, which is what `_descendants` needs to be true.

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

FAILS OPEN, LIKE EVERYTHING ELSE THIS INCIDENT TOUCHES. No checkout, no writable `.serve/`, a
`.serve` that is a stale file rather than a directory — none of these may stop the real
command from running; they leave the process unmarked, which `reap.py` treats exactly like a
process nothing here has ever heard of.

NEVER INSTALLED AND NEVER IMPORTED FROM OUTSIDE THIS CHECKOUT. `make janitor-install` copies
`reap.py` alone to `~/.claude/bin` so its hook covers every project on the machine; this script
is a Banchi launcher's own business and reads nothing `reap.py` does not already read back.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reap import checkout_root  # local import — this file is never copied out, see above


def main(argv: list) -> int:
    label = argv[1] if len(argv) > 1 else "process"
    root = checkout_root(os.getcwd())
    if not root:
        return 0  # no honest checkout to mark against — the real command still runs
    pid = os.getppid()
    owner = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    owners_dir = Path(root) / ".serve" / "owners"
    try:
        owners_dir.mkdir(parents=True, exist_ok=True)
        record = {"pid": pid, "owner": owner, "label": label, "startedAt": time.time()}
        (owners_dir / f"{pid}.json").write_text(json.dumps(record), encoding="utf-8")
    except OSError:
        pass  # a mark that could not be written leaves the pid untagged, never a hard failure
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
