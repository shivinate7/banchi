"""The one throwaway store for every harness test: a temp `BANCHI_HOME`, and an `ENV_FILE`
that does not exist, so no test reads the owner's settings file and none needs one to pass.

`harness/run.py` wraps the whole process in `isolated_home()`; a check that needs its own
empty store nests another. `hermetic()` in `harness/tests/t7/common.py` nests `no_env_file`.
"""

from __future__ import annotations

import os
import tempfile
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
