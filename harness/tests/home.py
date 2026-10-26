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


# One temp root for this repo's test runs. A run's files live in one `<pid>-<UUID>` folder under it.
TEMP_ROOT = Path(tempfile.gettempdir()) / "banchi-test-runs"
_RUN_NAME = re.compile(r"^\d+-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_STALE_AFTER_S = 24 * 60 * 60


@contextmanager
def run_folder(root=None):
    """One `<pid>-<UUID>` folder under `root` (default `TEMP_ROOT`); a test takes every temp path from it.

    Entering removes sibling run folders whose mtime is over a day old and keeps newer ones. Only a
    name of that shape is touched, so a stray folder in the root survives. Leaving removes this run's
    folder."""
    root = Path(root or TEMP_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - _STALE_AFTER_S
    for sibling in root.iterdir():
        if _RUN_NAME.match(sibling.name) and sibling.is_dir() and sibling.stat().st_mtime < cutoff:
            shutil.rmtree(sibling, ignore_errors=True)
    folder = root / "{0}-{1}".format(os.getpid(), uuid.uuid4())
    folder.mkdir()
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
