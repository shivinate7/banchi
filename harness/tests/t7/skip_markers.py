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
import errno
import io
import os
import re
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from harness.tests import Checks
from harness.tests.home import run_folder
from harness.tests.t7 import backup, emit_pricing, server_hardening, store_core

CI_SKIP_COUNT = Path(__file__).resolve().parents[3] / "scripts" / "ci-skip-count.sh"
OK_LINE = re.compile(r"^\s+ok\s", re.MULTILINE)
# The assertion lines `Checks` prints, at the indent a check's detail carries. The indent is spaces or tabs only: `\s`
# would also take a blank line, and then the fixture's own column-0 `FAIL  FIXTURE` headline would count as a check.
OK_CHECK = re.compile(r"^[ \t]+ok ", re.MULTILINE)
FAIL_CHECK = re.compile(r"^[ \t]+FAIL ", re.MULTILINE)
# `socket.socket` as it is before any case patches it. The stand-ins below answer every other family with it.
REAL_SOCKET = socket.socket
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


def check_a_send_matrix_without_node_modules_is_one_gated_skip(checks: Checks) -> None:
    """With `app/node_modules` absent, the send matrix cannot read Home: `_m_home` raises `_ToolchainMissing`, and
    the check must say so as one gated skip, never as an ok line or a note. The matrix's own loop runs every store
    shape before that read, seconds of work that say nothing about this branch, so the loop is given an empty
    matrix and the branch is reached with nothing else run. The stub is the scope: it must be called before a
    skip is claimed."""
    reached = []

    def no_toolchain(worklists):
        reached.append(dict(worklists))
        raise emit_pricing._ToolchainMissing()

    with run_folder() as folder:
        with mock.patch.object(emit_pricing, "_m_cases", lambda: {}), \
                mock.patch.object(emit_pricing, "_m_home", no_toolchain):
            out = _harness_output(emit_pricing.check_send_matrix)
        if checks.ok(len(reached) == 1, "the send matrix, with no node modules, reaches its Home read",
                     f"_m_home was called {len(reached)} times"):
            checks.equal(_gated_count(out, folder), 1,
                         "and that branch is one gated skip")
            checks.equal(len(OK_LINE.findall(out)), 0,
                         "and that branch adds no ok line")


def _check_lines(out: str) -> int:
    """How many assertions the run printed, passed or failed. A note starts with neither `ok` nor `FAIL`, so it is not
    counted."""
    return len(OK_CHECK.findall(out)) + len(FAIL_CHECK.findall(out))


def _refuse_af_inet6(errnum: int, asked: list):
    """A `socket.socket` that answers every AF_INET6 request with `errnum` and makes every other family as the real
    one does. Each AF_INET6 request is appended to `asked`, so a case can show the check reached its probe."""

    def socket_for(family=-1, *args, **kwargs):
        if family == socket.AF_INET6:
            asked.append(family)
            raise OSError(errnum, os.strerror(errnum))
        return REAL_SOCKET(family, *args, **kwargs)

    return socket_for


def _answer_first_af_inet6(asked: list):
    """A `socket.socket` that answers the first AF_INET6 request with a socket of this kernel's own family, so a probe
    succeeds. Every later AF_INET6 request is the real one, which this kernel may refuse for real."""
    answered = []

    def socket_for(family=-1, *args, **kwargs):
        if family == socket.AF_INET6:
            asked.append(family)
            if not answered:
                answered.append(family)
                return REAL_SOCKET(socket.AF_INET, socket.SOCK_STREAM)
        return REAL_SOCKET(family, *args, **kwargs)

    return socket_for


def check_a_root_run_of_the_read_only_door_is_one_gated_skip(checks: Checks) -> None:
    """Run as root (`os.geteuid` reads 0), the read-only door's no-side-file case is one gated skip, and the four
    assertions a root run still makes pass and print no FAIL. Root writes into a 0555 folder, so that one case
    cannot be built. The root branch is asserted first, so the skip is never claimed for a run that did not take it."""
    with run_folder() as folder:
        with mock.patch("os.geteuid", return_value=0) as geteuid:
            out = _harness_output(store_core.check_open_read_only)
        if checks.ok(geteuid.called, "the read-only door check, run as euid 0, reaches its root branch",
                     "os.geteuid was never read, so the check never took the root branch"):
            checks.equal(_gated_count(out, folder), 1,
                         "running as root, its no-side-file case is one gated skip")
            checks.equal(len(FAIL_CHECK.findall(out)), 0, "and the run prints no FAIL line")
            checks.equal(len(OK_CHECK.findall(out)), 4,
                         "and the four assertions that pass as root still run and pass")


def check_a_non_root_run_of_the_read_only_door_is_no_skip(checks: Checks) -> None:
    """Run as a non-root user (`os.geteuid` reads 1000), the read-only door's no-side-file case is not skipped, and all
    five assertions are made. The count of assertions is the proof the check ran, and it is pinned, not the pass count.
    This box is root, and root writes into the 0555 folder whatever the mode, so this forced run may print that one
    line as FAIL here."""
    with run_folder() as folder:
        with mock.patch("os.geteuid", return_value=1000):
            out = _harness_output(store_core.check_open_read_only)
        checks.equal(_gated_count(out, folder), 0,
                     "running as non-root, no case of the read-only door is skipped")
        checks.equal(_check_lines(out), 5, "and all five of its assertions are made")


def check_a_root_run_of_the_read_only_race_is_one_gated_skip(checks: Checks) -> None:
    """Run as root, the read-only race is one gated skip and makes no assertion. The race needs the plain `mode=ro`
    open to refuse a 0555 folder, and root can write into one, so the immutable fallback it races is never reached.
    The root branch is asserted first, so the skip is never claimed for a run that did not take it."""
    with run_folder() as folder:
        with mock.patch("os.geteuid", return_value=0) as geteuid:
            out = _harness_output(store_core.check_open_read_only_race)
        if checks.ok(geteuid.called, "the read-only race, run as euid 0, reaches its root branch",
                     "os.geteuid was never read, so the case never took the root branch"):
            checks.equal(_gated_count(out, folder), 1,
                         "running as root, the read-only race is one gated skip")
            checks.equal(_check_lines(out), 0,
                         "and it makes no assertion of its own: a skipped case adds no pass and no FAIL")


def check_a_non_root_run_of_the_read_only_race_is_no_skip(checks: Checks) -> None:
    """Run as a non-root user, the read-only race is not skipped and its three assertions are made. The count is pinned,
    not the pass count, for the same reason as the read-only door's non-root case."""
    with run_folder() as folder:
        with mock.patch("os.geteuid", return_value=1000):
            out = _harness_output(store_core.check_open_read_only_race)
        checks.equal(_gated_count(out, folder), 0,
                     "running as non-root, the read-only race is not skipped")
        checks.equal(_check_lines(out), 3, "and its three assertions are made")


def check_a_no_ipv6_run_of_the_dual_stack_bind_is_one_gated_skip(checks: Checks) -> None:
    """The probe decides, not `socket.has_ipv6`. This case reads `has_ipv6` as True and still has the AF_INET6 probe
    refused with errno 97 (EAFNOSUPPORT), which is what a kernel with IPv6 switched off answers. That is one gated skip,
    and the check makes no assertion of its own."""
    asked: list = []
    with run_folder() as folder:
        with mock.patch.object(socket, "has_ipv6", True), \
                mock.patch("socket.socket", _refuse_af_inet6(errno.EAFNOSUPPORT, asked)):
            out = _harness_output(server_hardening.check_dual_stack_bind)
        if checks.ok(bool(asked), "the dual-stack check reaches its AF_INET6 probe",
                     "no AF_INET6 socket was asked for, so the check never reached the probe"):
            checks.equal(_gated_count(out, folder), 1,
                         "with no IPv6 (errno 97), the dual-stack bind is one gated skip")
            checks.equal(_check_lines(out), 0, "and it makes no assertion of its own")
            checks.equal(len(FAIL_CHECK.findall(out)), 0, "and prints no FAIL line")


def check_an_ipv6_run_of_the_dual_stack_bind_is_no_skip(checks: Checks) -> None:
    """A kernel that reads `has_ipv6` False but whose AF_INET6 probe succeeds is not skipped: the probe decides. This
    box has no IPv6, so the bind after the probe is the real one, refused here as it really is, and the check prints
    its own FAILs. The count of assertions is pinned, not the pass count: four on a kernel with IPv6, where all four
    pass."""
    asked: list = []
    with run_folder() as folder:
        with mock.patch.object(socket, "has_ipv6", False), \
                mock.patch("socket.socket", _answer_first_af_inet6(asked)):
            out = _harness_output(server_hardening.check_dual_stack_bind)
        if checks.ok(bool(asked), "the dual-stack check reaches its AF_INET6 probe",
                     "no AF_INET6 socket was asked for, so the check never reached the probe"):
            checks.equal(_gated_count(out, folder), 0,
                         "with the probe answered, the dual-stack bind is not skipped")
            checks.equal(_check_lines(out), 4, "and all four of its assertions are made")


def check_a_dual_stack_probe_failing_for_another_reason_is_not_skipped(checks: Checks) -> None:
    """Any probe error other than EAFNOSUPPORT is a failure, never a skip. EMFILE (too many open files) stands for
    the other reasons: the check prints one FAIL that names the probe, and no ok line beside it."""
    asked: list = []
    with run_folder() as folder:
        with mock.patch.object(socket, "has_ipv6", True), \
                mock.patch("socket.socket", _refuse_af_inet6(errno.EMFILE, asked)):
            out = _harness_output(server_hardening.check_dual_stack_bind)
        if checks.ok(bool(asked), "the dual-stack check reaches its AF_INET6 probe",
                     "no AF_INET6 socket was asked for, so the check never reached the probe"):
            checks.equal(_gated_count(out, folder), 0,
                         "a probe that fails with EMFILE is not a skip")
            checks.equal(len(FAIL_CHECK.findall(out)), 1, "and it is one FAIL line")
            checks.equal(len(OK_CHECK.findall(out)), 0, "and no assertion passes beside it")
            checks.ok(re.search(r"^[ \t]+FAIL .*AF_INET6 probe", out, re.MULTILINE) is not None,
                      "and that FAIL names the probe")


CHECKS = (
    check_a_skipped_case_is_one_gated_skip_to_the_ci_counter,
    check_a_skipped_case_adds_no_ok_line_and_no_pass,
    check_a_root_run_of_the_backup_read_only_case_is_one_gated_skip,
    check_a_root_run_of_the_backup_unwritable_destination_is_one_gated_skip,
    check_a_root_run_of_the_backup_unreadable_folder_is_one_gated_skip,
    check_skip_refuses_a_name_that_is_not_kebab_case,
    check_a_send_matrix_without_node_modules_is_one_gated_skip,
    check_a_root_run_of_the_read_only_door_is_one_gated_skip,
    check_a_non_root_run_of_the_read_only_door_is_no_skip,
    check_a_root_run_of_the_read_only_race_is_one_gated_skip,
    check_a_non_root_run_of_the_read_only_race_is_no_skip,
    check_a_no_ipv6_run_of_the_dual_stack_bind_is_one_gated_skip,
    check_an_ipv6_run_of_the_dual_stack_bind_is_no_skip,
    check_a_dual_stack_probe_failing_for_another_reason_is_not_skipped,
)
