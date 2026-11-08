"""T7 group: the run's own output, and what a spawned child process does with the run.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

WHY. A cloud run of T7 printed nothing for about twelve minutes, so a session's stall watcher
read it as hung. The run now writes one flushed stderr line as each check ends. And a script that
calls `run` at top level, with no `__main__` guard, re-ran all of T7 inside every spawned child it
started, so it never finished. A spawned child now refuses at once instead.

BOTH CASES USE `run(order=...)`, the seam `t7_store_and_seams.run` already has, so one case costs
two probe checks instead of the whole run. The spawn case runs its own script in a subprocess. It
uses a single probe as its order rather than the full T7 on purpose: on the current code a full
run inside a child would reach live hosts and start children of its own, which a fixture may not
do. One probe still shows the defect, because the probe runs in the child.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from contextlib import redirect_stderr

from harness.tests import Checks
from harness.tests.home import run_folder
from harness.tests.t7.common import REPO_ROOT

# `<number>/<total> <seconds>s <check name>`: one line per check, as the check ends.
PROGRESS_LINE = re.compile(r"^T7 (\d+)/(\d+) \d+\.\d+s (\S+)$", re.MULTILINE)
# `scripts/ci-skip-count.sh` counts this shape as a skipped case, so a progress line must never take it.
SKIP_SHAPED_LINE = re.compile(r"^[a-z0-9-]+: SKIPPED ", re.MULTILINE)
SPAWN_TIMEOUT_S = 60

SPAWN_SCRIPT = """\
import multiprocessing
import os
import sys

sys.path.insert(0, {repo!r})

from harness.tests import t7_store_and_seams


def probe(checks):
    # The pid, not `multiprocessing.parent_process()`: during a spawn child's top-level import that
    # is None, so a probe asking it cannot tell the child from the main process.
    print("PROBE RAN pid=%d" % os.getpid(), flush=True)
    checks.ok(True, "probe")


# No __main__ guard around the run, on purpose: this is the shape that re-ran all of T7 in each child.
t7_store_and_seams.run(order=lambda todo: [probe])


def child_body():
    print("CHILD BODY", flush=True)


if __name__ == "__main__":
    print("MAIN pid=%d" % os.getpid(), flush=True)
    process = multiprocessing.get_context("spawn").Process(target=child_body)
    process.start()
    process.join(20)
    print("PARENT DONE alive=" + str(process.is_alive()), flush=True)
"""


class _FlushRecorder(io.StringIO):
    """A stderr stand-in that keeps what its last flush released, so a probe can read it."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed = ""

    def flush(self) -> None:
        self.flushed = self.getvalue()
        super().flush()


def check_run_prints_one_flushed_line_per_check(checks: Checks) -> None:
    """Each check's end writes one numbered, named line to stderr, and the line is flushed.

    The second probe reads what the first flush released. A line written but not flushed is not
    yet on the reader's screen, and the stall this exists to end is exactly a run that holds its
    output back.
    """
    from harness.tests import t7_store_and_seams  # lazy: that module imports this one

    checks.note("")
    checks.note("T7 RUN LINES — one flushed stderr line as each check ends")
    stream = _FlushRecorder()
    seen = {}

    def probe_first(_checks: Checks) -> None:
        pass

    def probe_second(_checks: Checks) -> None:
        seen["flushed_before_second"] = stream.flushed

    with redirect_stderr(stream):
        t7_store_and_seams.run(order=lambda todo: [probe_first, probe_second])

    text = stream.getvalue()
    checks.equal(
        PROGRESS_LINE.findall(text),
        [("1", "2", "probe_first"), ("2", "2", "probe_second")],
        "one numbered, named line per check, as each check ends",
    )
    flushed = seen.get("flushed_before_second", "")
    checks.ok(
        re.search(r"^T7 1/2 \d+\.\d+s probe_first$", flushed, re.MULTILINE) is not None,
        "the first check's line was flushed before the second check began",
        f"flushed when the second check began: {flushed[-300:]!r}",
    )
    checks.ok(
        SKIP_SHAPED_LINE.search(text) is None,
        "no progress line is shaped like a skip line",
        text[-300:],
    )


def check_run_refuses_inside_a_spawned_child(checks: Checks) -> None:
    """A spawned child that reaches `run` refuses at once: it runs no check and says so in one line.

    The script calls `run` at top level, as the bad script did. The main process runs its one
    probe. The spawned child must not, and must print exactly one line naming T7 before it exits.
    """
    checks.note("")
    checks.note("T7 SPAWN — a spawned child that reaches run refuses at once, and runs no check")
    with run_folder() as folder:
        script = folder / "spawn_run.py"
        script.write_text(SPAWN_SCRIPT.format(repo=str(REPO_ROOT)), encoding="utf-8")
        try:
            done = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=SPAWN_TIMEOUT_S,
                stdin=subprocess.DEVNULL,
                cwd=str(folder),
            )
        except subprocess.TimeoutExpired:
            checks.ok(False, f"the script did not finish within {SPAWN_TIMEOUT_S} s")
            return
    output = done.stdout + done.stderr
    mains = re.findall(r"^MAIN pid=(\d+)$", output, re.MULTILINE)
    probe_pids = re.findall(r"^PROBE RAN pid=(\d+)$", output, re.MULTILINE)
    main_pid = mains[0] if len(mains) == 1 else ""
    checks.equal(
        probe_pids.count(main_pid), 1,
        "the main process ran its one probe, as a top-level run does",
    )
    checks.equal(
        [pid for pid in probe_pids if pid != main_pid], [],
        "a spawned child ran a check instead of refusing",
    )
    t7_lines = [line for line in output.splitlines() if line.startswith("T7")]
    checks.equal(
        len(t7_lines), 1,
        "the spawned child printed exactly one line naming T7",
    )
    checks.ok(
        "PARENT DONE alive=False" in output,
        "the spawned child exited before the parent's wait ran out",
        output[-600:],
    )


CHECKS = (
    check_run_prints_one_flushed_line_per_check,
    check_run_refuses_inside_a_spawned_child,
)
