#!/usr/bin/env python3
"""Selftest for `server/ports.py`'s `machine_dir` and `remove_old_agent`, and their env overrides.

Protects: The move to the new machine dir loses no port claim or file, and an old launchd job file is deleted only after its job is stopped.

Every case runs with HOME pointed at a fresh temp dir. `Path.home()` reads `$HOME` on POSIX,
and `setUp` asserts it before each case. `subprocess.run` is replaced, so no case reaches the
real `launchctl`. `BANCHI_LOCK_DIR` lives in `scripts/suite-lock.py`, so that case loads it.

Run: `python3 scripts/ports-machine-selftest.py`. Stdlib only, no fixtures outside `mkdtemp`.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import ports  # noqa: E402

LOCK_DIR_ENV = "BANCHI_LOCK_DIR"

# The real home, read before any case touches HOME. The module teardown proves nothing leaked.
REAL_HOME = Path(os.path.expanduser("~"))
REAL_PKMNSCAN_AT_START = os.path.lexists(REAL_HOME / ".pkmnscan")
REAL_BANCHI_AT_START = os.path.lexists(REAL_HOME / ".banchi")


def _load_suite_lock():
    spec = importlib.util.spec_from_file_location("suite_lock_under_test", ROOT / "scripts" / "suite-lock.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MachineHomeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="banchi-machine-selftest-")
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name).resolve()
        self.new = self.home / ".banchi"
        self.old = self.home / ".pkmnscan"
        self.launch_agents = self.home / "Library" / "LaunchAgents"

        saved_env = dict(os.environ)
        self.addCleanup(self._restore_env, saved_env)
        os.environ["HOME"] = str(self.home)
        os.environ.pop(ports.SLOT_REGISTRY_ENV, None)
        os.environ.pop(LOCK_DIR_ENV, None)

        # Fence: the override must take effect before any case runs.
        self.assertEqual(Path.home(), self.home)

        run = mock.patch.object(ports.subprocess, "run", return_value=mock.Mock(returncode=0))
        self.fake_run = run.start()
        self.addCleanup(run.stop)

    @staticmethod
    def _restore_env(saved):
        os.environ.clear()
        os.environ.update(saved)

    def _dir(self, path: Path, marker: str) -> None:
        path.mkdir(parents=True)
        (path / "marker").write_text(marker, encoding="utf-8")

    def _plist(self, label: str) -> Path:
        self.launch_agents.mkdir(parents=True, exist_ok=True)
        plist = self.launch_agents / (label + ".plist")
        plist.write_text("<plist/>", encoding="utf-8")
        return plist

    # ------------------------------------------------------------------ machine_dir

    def test_machine_dir_moves_old_dir_when_only_old_exists(self):
        self._dir(self.old, "old")
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        self.assertTrue(self.old.is_symlink())
        self.assertEqual((self.new / "marker").read_text(encoding="utf-8"), "old")

    def test_machine_dir_does_nothing_when_only_new_exists(self):
        self._dir(self.new, "new")
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        self.assertFalse(self.old.exists())
        self.assertEqual((self.new / "marker").read_text(encoding="utf-8"), "new")

    def test_machine_dir_both_exist_keeps_new_links_old_and_aside_old_copy(self):
        self._dir(self.old, "old")
        self._dir(self.new, "new")
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        # The new copy wins. The old real directory is kept aside, and the old path links to new.
        self.assertTrue(self.old.is_symlink())
        self.assertEqual((self.new / "marker").read_text(encoding="utf-8"), "new")
        kept = list(self.home.glob(".pkmnscan.old-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0] / "marker").read_text(encoding="utf-8"), "old")

    def test_machine_dir_both_exist_moves_old_only_slot_claims(self):
        # A claim only the old registry held is moved into the new directory, so it still reads.
        self._dir(self.new, "new")
        self.old.mkdir()
        (self.old / ports.SLOT_REGISTRY_NAME).write_text(
            '{"slots": {"/some/checkout": 42}}', encoding="utf-8")
        self.assertEqual(ports.machine_dir(), self.new)
        self.assertEqual(ports.read_claims(), {"/some/checkout": 42})

    def test_machine_dir_neither_exists_returns_new_and_creates_nothing(self):
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        self.assertFalse(self.new.exists())
        self.assertFalse(self.old.exists())

    # ------------------------------------------------------------------ env overrides

    def test_slot_registry_env_override_is_used_and_no_move_happens(self):
        self._dir(self.old, "old")
        override = self.home / "elsewhere" / "slots.json"
        os.environ[ports.SLOT_REGISTRY_ENV] = str(override)
        self.assertEqual(ports.slot_registry(), override)
        self.assertTrue(self.old.is_dir())
        self.assertFalse(self.new.exists())

    def test_lock_dir_env_override_is_used_and_no_move_happens(self):
        self._dir(self.old, "old")
        override = self.home / "elsewhere" / "locks"
        os.environ[LOCK_DIR_ENV] = str(override)
        suite_lock = _load_suite_lock()
        self.assertEqual(suite_lock.lock_dir(), override)
        self.assertTrue(self.old.is_dir())
        self.assertFalse(self.new.exists())

    def test_lock_dir_default_sits_under_banchi(self):
        suite_lock = _load_suite_lock()
        self.assertEqual(suite_lock.lock_dir(), self.new / "locks")

    # ------------------------------------------------------------------ remove_old_agent

    def test_remove_old_agent_deletes_present_pkmnscan_plist(self):
        plist = self._plist("com.pkmnscan.serve.42")
        ports.remove_old_agent("com.banchi.serve.42")
        self.assertFalse(plist.exists())
        self.fake_run.assert_called_once_with(
            ["launchctl", "bootout", "gui/%d/com.pkmnscan.serve.42" % os.getuid()],
            capture_output=True)

    def test_remove_old_agent_absent_plist_is_quiet(self):
        self.launch_agents.mkdir(parents=True)
        ports.remove_old_agent("com.banchi.serve.42")  # must not raise
        self.assertEqual(list(self.launch_agents.iterdir()), [])
        self.fake_run.assert_called_once()

    def test_remove_old_agent_never_touches_banchi_plist(self):
        # The argument is the NEW label. The function derives the OLD one and acts on that only.
        new_plist = self._plist("com.banchi.serve.42")
        ports.remove_old_agent("com.banchi.serve.42")
        self.assertTrue(new_plist.exists())
        self.assertEqual(self.fake_run.call_count, 1)
        for call in self.fake_run.call_args_list:
            self.assertNotIn("com.banchi", " ".join(call.args[0]))

    def test_remove_old_agent_pkmnscan_label_is_a_no_op(self):
        # A label with no com.banchi prefix maps to itself, so the function returns early.
        plist = self._plist("com.banchi.serve.42")
        ports.remove_old_agent("com.pkmnscan.serve.42")
        self.assertTrue(plist.exists())
        self.fake_run.assert_not_called()


    # ------------------------------------------------------------------ next round: symlink
    # RED on the current code: the old path is gone after the move, so nothing is linked.

    def test_machine_dir_leaves_symlink_at_old_path_after_move(self):
        self._dir(self.old, "old")
        ports.machine_dir()
        self.assertTrue(self.old.is_symlink(), "old path must be a symlink after the move")
        self.assertEqual(self.old.resolve(), self.new.resolve())
        (self.old / "written_via_old.txt").write_text("x", encoding="utf-8")
        self.assertTrue((self.new / "written_via_old.txt").is_file())

    def test_machine_dir_both_exist_real_old_moves_missing_files_and_links(self):
        # RED on the current code: the real old dir is left alone and nothing is moved.
        self._dir(self.new, "new")
        (self.new / "common.txt").write_text("new wins", encoding="utf-8")
        self.old.mkdir()
        (self.old / "only_old.txt").write_text("from old", encoding="utf-8")
        (self.old / "common.txt").write_text("old copy", encoding="utf-8")
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        self.assertEqual((self.new / "only_old.txt").read_text(encoding="utf-8"), "from old")
        # For a file present in both, the new one wins. The old copy stays in `.pkmnscan.old-*`.
        self.assertEqual((self.new / "common.txt").read_text(encoding="utf-8"), "new wins")
        self.assertTrue(self.old.is_symlink(), "old path must be replaced by a symlink")
        self.assertEqual(self.old.resolve(), self.new.resolve())

    def test_machine_dir_new_linked_to_old_makes_no_loop(self):
        self._dir(self.old, "old")
        os.symlink(self.old, self.new)
        self.assertEqual(ports.machine_dir(), self.new)
        self.assertTrue(self.old.is_dir() and not self.old.is_symlink())
        self.assertEqual((self.new / "marker").read_text(encoding="utf-8"), "old")

    def test_machine_dir_old_symlink_already_linked_changes_nothing(self):
        # GREEN on the current code by design: this is a guard for the builder's change.
        self._dir(self.new, "new")
        os.symlink(self.new, self.old)
        before = sorted(p.name for p in self.new.iterdir())
        got = ports.machine_dir()
        self.assertEqual(got, self.new)
        self.assertTrue(self.old.is_symlink())
        self.assertEqual(self.old.resolve(), self.new.resolve())
        self.assertEqual(sorted(p.name for p in self.new.iterdir()), before)
        self.assertEqual((self.new / "marker").read_text(encoding="utf-8"), "new")

    # ------------------------------------------------------------------ next round: bootout

    def test_remove_old_agent_keeps_plist_when_bootout_fails(self):
        # RED on the current code: the plist is deleted whatever bootout returns.
        # Exit 5 is "Input/output error" (`launchctl error 5`), not "not loaded".
        plist = self._plist("com.pkmnscan.serve.42")
        self.fake_run.return_value = mock.Mock(
            returncode=5, stderr=b"Boot-out failed: 5: Input/output error")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            ports.remove_old_agent("com.banchi.serve.42")
        self.assertTrue(plist.exists(), "plist must stay when bootout fails")
        self.assertIn("com.pkmnscan.serve.42", out.getvalue(), "a line must be printed")

    def test_remove_old_agent_deletes_plist_when_not_loaded(self):
        # GREEN on the current code by design: exit 113 is "Could not find specified service"
        # (`launchctl error 113`), the "not loaded" code this round uses.
        plist = self._plist("com.pkmnscan.serve.42")
        self.fake_run.return_value = mock.Mock(
            returncode=113, stderr=b"Boot-out failed: 113: Could not find specified service")
        ports.remove_old_agent("com.banchi.serve.42")
        self.assertFalse(plist.exists(), "plist must go when the service is not loaded")


def tearDownModule():
    # A leak into the real home fails the run, even if every case passed.
    assert os.path.lexists(REAL_HOME / ".pkmnscan") == REAL_PKMNSCAN_AT_START, "real ~/.pkmnscan changed"
    assert os.path.lexists(REAL_HOME / ".banchi") == REAL_BANCHI_AT_START, "real ~/.banchi changed"


if __name__ == "__main__":
    unittest.main(verbosity=2)
