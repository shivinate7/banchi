"""The one throwaway store for every harness test: a temp `BANCHI_HOME`, and an `ENV_FILE`
that does not exist, so no test reads the owner's settings file and none needs one to pass.

`harness/run.py` wraps the whole process in `isolated_home()`; a check that needs its own
empty store nests another. `hermetic()` in `harness/tests/t7/common.py` nests `no_env_file`.
"""

from __future__ import annotations

import atexit
import os
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
def isolated_home():
    """A whole store in a temporary directory, with no settings file, restored on the way out.

    Restores the previous value rather than deleting the key: other tests share this process.
    """
    previous = os.environ.get(files.HOME_ENV)
    with tempfile.TemporaryDirectory() as tmp, no_env_file(tmp):
        os.environ[files.HOME_ENV] = tmp
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous


# THE RUN-FOLDER STANDARD (test-temp-standard) for a check that needs more than an empty store:
# one temp root, one `<pid>-<uuid>` folder per test run under it, and every temp path of the run
# below that folder. `scripts/demo-mirror-daily-photos-selftest.py` holds the same convention
# inline; it runs at import, so a harness group cannot import it, and this is the second home.
TEMP_ROOT = Path(tempfile.gettempdir()) / "banchi-test-runs"
RUN_MAX_AGE = 86400  # a crashed run's folder goes after a day; a newer sibling belongs to a parallel run
_run_folder = None


def remove_tree(path) -> None:
    """Delete a tree, opening any folder or file a case made read-only first. Never follows a link."""
    def open_up(p):
        if os.path.islink(p):
            return
        try:
            os.chmod(p, 0o700)
            if os.path.isdir(p):
                for name in os.listdir(p):
                    open_up(os.path.join(p, name))
        except OSError:
            pass

    open_up(str(path))
    shutil.rmtree(path, ignore_errors=True)


def sweep(root=None) -> None:
    """The first request of a run: drop sibling run folders older than a day, keep the newer ones."""
    root = Path(root or TEMP_ROOT)
    for d in root.glob("*-*") if root.is_dir() else []:
        if d.is_dir() and time.time() - d.stat().st_mtime > RUN_MAX_AGE:
            remove_tree(d)


def run_folder() -> Path:
    """This process's one run folder. The first ask sweeps old siblings and makes it; exit removes it."""
    global _run_folder
    if _run_folder is None or not _run_folder.is_dir():
        sweep()
        _run_folder = TEMP_ROOT / f"{os.getpid()}-{uuid.uuid4()}"
        _run_folder.mkdir(parents=True)
        atexit.register(remove_tree, _run_folder)
    return _run_folder
