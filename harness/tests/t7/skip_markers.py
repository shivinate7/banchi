"""T7 group: a skipped case reaches the harness output as a gated skip, and adds no pass.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

A SKIP IS NOT A PASS, AND IT IS NOT A NOTE. The backup check's read-only case cannot run as root
(root reads and deletes a 0500 folder whatever its mode), so it is skipped. Until now that skip was
an indented note inside the check's detail. Nothing counts a note, so `scripts/ci-skip-count.sh`
read zero skips and T7 went green with the case unbuilt.

THE CONTRACT THE BUILD MEETS. The build adds these, and the checks read them only through the output:
  harness/tests/__init__.py   `Checks.skip(name, reason)`: records one skipped case by a kebab name and
                              a reason. It adds no `ok` line and moves no pass count.
  harness/run.py              prints each recorded skip as one unindented line,
                              `<kebab-name>: SKIPPED — <reason>`, after its test's detail.

Every case reads the harness's own printing (`harness/run.py`'s `main`, over one fixture test) and
counts gated skips with `scripts/ci-skip-count.sh`, the one reader CI uses. No case reads `Checks`
internals.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from harness.tests import Checks
from harness.tests.home import run_folder
from harness.tests.t7 import backup

CI_SKIP_COUNT = Path(__file__).resolve().parents[3] / "scripts" / "ci-skip-count.sh"
OK_LINE = re.compile(r"^\s+ok\s", re.MULTILINE)
# The ok lines each backup check makes before its skipped case, measured as root at the head this group was
# last changed on. A skip beside an `ok` line in those checks changes the count, and that is the failure.
UNWRITABLE_OK_LINES = 4
UNREADABLE_OK_LINES = 1


def _harness_output(body) -> str:
    """`body(checks)` is one harness test, run through `harness/run.py`'s own printing. Returns its stdout."""
    import harness.run as harness_run  # lazy: run.py imports every test module, this one's runner among them

    def run():
        inner = Checks()
        body(inner)
        return inner.result("one fixture test")

    fixture = SimpleNamespace(NAME="FIXTURE", DESCRIPTION="one fixture test", PASS_CRITERIA="a fixture", run=run)
    out = io.StringIO()
    with mock.patch.object(harness_run, "TESTS", [fixture]), contextlib.redirect_stdout(out):
        harness_run.main()
    return out.getvalue()


def _gated_count(out: str, folder: Path):
    """The gated count `scripts/ci-skip-count.sh` prints for one harness output, or None when it prints none."""
    log = folder / "make.log"
    log.write_text(out, encoding="utf-8")
    # The summary goes into this run's folder: a CI job sets GITHUB_STEP_SUMMARY, and the nested call must not write it.
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(folder / "step-summary.md")}
    try:
        proc = subprocess.run(["bash", str(CI_SKIP_COUNT), "harness-fixture", str(log)],
                              capture_output=True, text=True, env=env, check=False)
    except OSError:
        return None
    found = re.search(r"(\d+) gated self-test", proc.stdout)
    return int(found.group(1)) if found else None


def _passed_lines(out: str) -> list:
    """The headline pass count `harness/run.py` prints for the fixture."""
    return [line.strip() for line in out.splitlines() if line.strip().endswith("checks passed")]


def _record_skip(checks: Checks, name: str, reason: str) -> None:
    """Records one skip through `Checks.skip`. Without the method this writes nothing, so the case that
    calls it fails on its own assert: no gated marker printed."""
    skip = getattr(checks, "skip", None)
    if callable(skip):
        skip(name, reason)


def _one_ok(checks: Checks) -> None:
    checks.ok(True, "the only check")


def _one_ok_and_one_skip(checks: Checks) -> None:
    checks.ok(True, "the only check")
    _record_skip(checks, "a-skipped-case", "running as root")


def _one_ok_and_two_skips(checks: Checks) -> None:
    checks.ok(True, "the only check")
    _record_skip(checks, "first-skipped-case", "running as root")
    _record_skip(checks, "second-skipped-case", "running as root")


def _two_oks(checks: Checks) -> None:
    checks.ok(True, "first check")
    checks.ok(True, "second check")


def _two_oks_and_a_skip(checks: Checks) -> None:
    checks.ok(True, "first check")
    _record_skip(checks, "a-skipped-case", "running as root")
    checks.ok(True, "second check")


def check_a_skipped_case_is_one_gated_skip_to_the_ci_counter(checks: Checks) -> None:
    """A fixture with no skip reads as zero gated skips, and each skip it records reads as one more: the
    counter counts skips, not tests."""
    with run_folder() as folder:
        checks.equal(_gated_count(_harness_output(_one_ok), folder), 0,
                     "control: a fixture with no skip reads as zero gated skips")
        checks.equal(_gated_count(_harness_output(_one_ok_and_one_skip), folder), 1,
                     "a fixture that skips one case reads as 1 gated self-test skipped")
        checks.equal(_gated_count(_harness_output(_one_ok_and_two_skips), folder), 2,
                     "and two skipped cases read as 2")


def check_a_skipped_case_adds_no_ok_line_and_no_pass(checks: Checks) -> None:
    """The skip is a marker, not an assertion: the same two `ok` lines print with or without it, and the
    headline reads the same pass count. The marker is asserted first; the other two are gated on it, so a
    run that printed no marker cannot pass them vacuously."""
    with run_folder() as folder:
        plain = _harness_output(_two_oks)
        checks.equal(_passed_lines(plain), ["all 2 checks passed"],
                     "control: two ok checks read as all 2 checks passed through the harness output")
        skipped = _harness_output(_two_oks_and_a_skip)
        if checks.equal(_gated_count(skipped, folder), 1, "the skipped case prints its gated marker"):
            checks.equal(len(OK_LINE.findall(skipped)), len(OK_LINE.findall(plain)),
                         "and prints no ok line of its own")
            checks.equal(_passed_lines(skipped), _passed_lines(plain),
                         "and the pass count reads the same as without it")


def check_a_root_run_of_the_backup_read_only_case_is_one_gated_skip(checks: Checks) -> None:
    """Run as root (`os.geteuid` reads 0), the backup check's read-only case is skipped and the skip reaches the
    output as one gated marker. The check's own run-folder assertion is the only ok line: the skipped case adds
    none. The root branch is asserted first, so a claim about the skip is never made for a run that did not
    take it."""
    with run_folder() as folder:
        with mock.patch("os.geteuid", return_value=0) as geteuid:
            out = _harness_output(backup.check_backup_run_folder_deletes_read_only_trees_and_follows_no_link)
        reached = checks.ok(geteuid.called, "the backup check, run as euid 0, reaches its root branch",
                            "os.geteuid was never read, so the check never took the root branch")
        marked = reached and checks.equal(_gated_count(out, folder), 1,
                                          "running as root, its read-only case is one gated skip")
        if marked:
            checks.equal(len(OK_LINE.findall(out)), 1,
                         "and that skip adds no ok line: the one ok is the run-folder check")


def check_a_root_run_of_the_backup_unwritable_destination_is_one_gated_skip(checks: Checks) -> None:
    """As root, a 0500 destination is still writable, so the unwritable-destination case is skipped. The probe that
    decides it is answered the way root answers it, for `photos/probe` only, so the branch runs as any user. The
    check must reach the probe before a skip is claimed, and the skip must reach the output as one gated marker."""
    probed = []
    real_write_bytes = Path.write_bytes

    def root_writes_the_probe(self, data):
        if self.name == "probe":
            probed.append(self)
            return len(data)
        return real_write_bytes(self, data)

    with run_folder() as folder:
        with mock.patch.object(Path, "write_bytes", root_writes_the_probe):
            out = _harness_output(backup.check_backup_failure_is_recorded_and_harmless)
        if checks.ok(bool(probed), "the backup check, run as root, reaches its writable probe",
                     "the probe was never written, so the check never took the writable branch"):
            checks.equal(_gated_count(out, folder), 1,
                         "running as root, its unwritable-destination case is one gated skip")
            checks.equal(len(OK_LINE.findall(out)), UNWRITABLE_OK_LINES,
                         "and the skipped case adds no ok line of its own")


def check_a_root_run_of_the_backup_unreadable_folder_is_one_gated_skip(checks: Checks) -> None:
    """As root, a mode-0 `photos/dd` folder is still readable, so the unreadable-folder case is skipped. The access
    check that decides it is answered the way root answers it, for directories only, so the branch runs as any
    user. The check must reach that access before a skip is claimed. The skip must reach the output as one gated
    marker, and no ok line may carry it: a skipped case adds no pass."""
    asked = []
    real_access = os.access

    def root_reads_directories(path, mode, *args, **kwargs):
        if Path(path).is_dir():
            asked.append(Path(path))
            return True
        return real_access(path, mode, *args, **kwargs)

    with run_folder() as folder:
        with mock.patch("os.access", root_reads_directories):
            out = _harness_output(backup.check_backup_an_unreadable_photo_folder_fails_the_night)
        if checks.ok(any(p.name == "dd" and p.parent.name == "photos" for p in asked),
                     "the backup check, run as root, reaches its readable-folder branch for photos/dd",
                     f"os.access was asked about {[str(p) for p in asked]}"):
            checks.equal(_gated_count(out, folder), 1,
                         "running as root, its unreadable-folder case is one gated skip")
            checks.ok(not re.search(r"^\s+ok\s.*SKIPPED", out, re.M),
                      "and no ok line carries the skip: a skipped case adds no pass")
            checks.equal(len(OK_LINE.findall(out)), UNREADABLE_OK_LINES,
                         "and the skipped case adds no ok line of its own")


def check_skip_refuses_a_name_that_is_not_kebab_case(checks: Checks) -> None:
    """`Checks.skip` takes the kebab name CI's counter matches, `[a-z0-9-]+`, and raises ValueError on any other
    name. A name that got through would print a marker the counter does not match, and the skip would count as
    nothing. Each bad name is refused: an underscore, an uppercase letter, a space, an empty name. A good name is
    the control, and it is accepted."""
    inner = Checks()
    for name in ("t7_x", "T7-x", "x y", ""):
        checks.raises(ValueError, lambda n=name: inner.skip(n, "a reason"),
                      f"a skip named {name!r} is refused with ValueError")
    try:
        inner.skip("t7-good-name", "a reason")
    except ValueError as exc:
        checks.ok(False, "control: a kebab-case skip name is accepted", str(exc))
    else:
        checks.ok(True, "control: a kebab-case skip name is accepted")


CHECKS = (
    check_a_skipped_case_is_one_gated_skip_to_the_ci_counter,
    check_a_skipped_case_adds_no_ok_line_and_no_pass,
    check_a_root_run_of_the_backup_read_only_case_is_one_gated_skip,
    check_a_root_run_of_the_backup_unwritable_destination_is_one_gated_skip,
    check_a_root_run_of_the_backup_unreadable_folder_is_one_gated_skip,
    check_skip_refuses_a_name_that_is_not_kebab_case,
)
