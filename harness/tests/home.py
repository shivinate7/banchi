"""The one throwaway store for every harness test: a temp `BANCHI_HOME`, and an `ENV_FILE`
that does not exist, so no test reads the owner's settings file and none needs one to pass.

`harness/run.py` wraps the whole process in `isolated_home()`; a check that needs its own
empty store nests another. `hermetic()` in `harness/tests/t7/common.py` nests `no_env_file`.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import envfile
from store import files


@contextmanager
def no_env_file(directory=None):
    """`envfile.ENV_FILE` points at a file that does not exist; its state is put back on exit."""
    saved = envfile.ENV_FILE, set(envfile._from_file), envfile._loaded
    envfile.ENV_FILE = Path(directory or tempfile.gettempdir()) / "harness-no-such-settings"
    try:
        yield
    finally:
        envfile.ENV_FILE, from_file, envfile._loaded = saved
        envfile._from_file.clear()
        envfile._from_file.update(from_file)


@contextmanager
def _home_folder(root):
    """The folder a home is made in: a fresh `home` under `root` (a run folder, which its own
    `run_folder` removes), or a system temporary directory when no root is given."""
    if root is None:
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)
    else:
        home = Path(root) / "home"
        home.mkdir(parents=True, exist_ok=True)
        yield home


@contextmanager
def isolated_home(root=None):
    """A whole store in a temporary directory, with no settings file, restored on the way out.

    `root`, when given, is a run folder from `run_folder()` (test-temp-standard): the home is
    made under it and nothing here removes it. Restores the previous value rather than deleting
    the key: other tests share this process.
    """
    previous = os.environ.get(files.HOME_ENV)
    with _home_folder(root) as tmp, no_env_file(tmp):
        os.environ[files.HOME_ENV] = str(tmp)
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous


# THE RUN-FOLDER STANDARD (test-temp-standard), for a check that needs more than an empty store:
# one temp root, one `<pid>-<UUID>` folder per test run under it, and every temp path of the run
# below that folder. This is the one home; no test builds its own.
TEMP_ROOT = Path(tempfile.gettempdir()) / "banchi-test-runs"
_RUN_NAME = re.compile(r"^\d+-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_STALE_AFTER_S = 24 * 60 * 60


def open_up(path) -> None:
    """Make a tree the case locked read-only readable and writable again. Never follows a link."""
    p = str(path)
    if os.path.islink(p):
        return
    try:
        os.chmod(p, 0o700)
        if os.path.isdir(p):
            for name in os.listdir(p):
                open_up(os.path.join(p, name))
    except OSError:
        pass


def remove_tree(path) -> None:
    """Delete a tree, opening any folder or file a case made read-only first. Never follows a link."""
    open_up(path)
    shutil.rmtree(path, ignore_errors=True)


@contextmanager
def run_folder(root=None):
    """One `<pid>-<UUID>` folder under `root` (default `TEMP_ROOT`); a test takes every temp path from it.

    Entering removes sibling run folders whose mtime is over a day old and keeps newer ones. Only a
    name of that shape is touched, so a stray folder in the root survives, and a link is never
    followed. Leaving removes this run's folder, read-only paths included."""
    root = Path(root or TEMP_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - _STALE_AFTER_S
    for sibling in root.iterdir():
        try:
            stale = (
                _RUN_NAME.match(sibling.name)
                and not sibling.is_symlink()
                and sibling.is_dir()
                and sibling.stat().st_mtime < cutoff
            )
        except OSError:  # a parallel run swept it first
            continue
        if stale:
            remove_tree(sibling)
    folder = root / "{0}-{1}".format(os.getpid(), uuid.uuid4())
    folder.mkdir()
    try:
        yield folder
    finally:
        remove_tree(folder)
