"""Read `KEY=value` from the gitignored `.env`. Shared by everything that needs a secret.

Deliberately not a dotenv dependency: this reads a handful of `KEY=value` lines and
nothing else — no interpolation, no `export` syntax, no shell-out. A real environment
variable always wins, so CI can set one without editing a file.

`.env` is the repo's secret location by existing convention: `.gitignore` excludes it,
and `.claude/settings.json` denies reading it, which keeps keys out of an agent's context
while still letting the code use them. `.gitignore` matches `.env*` rather than `.env`
because an editor that saves as `.env.rtf` otherwise leaves a live key one `git add -A`
from being committed — which is exactly what happened once.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"

_loaded = False

# THE NAMES THIS MODULE PUT INTO `os.environ`, so `get_live` can tell them from the ones that
# were already there. Without it the two are indistinguishable a moment after `load` runs,
# and "a real environment variable always wins" becomes uncheckable rather than merely
# unchecked.
_from_file: set = set()


def _parse(path: Path) -> dict:
    """`.env` as a plain dict. No environment, no cache, no side effect.

    Split out of `load` so `get_live` can read the file without the two caches that make
    `load` wrong for a rotating secret, and so both readers agree byte for byte about what a
    line means — a second parser here would be a second answer to "is `FOO = bar` a value
    with a space in it".
    """
    out: dict = {}
    try:
        text = path.read_text("utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name:
            out[name] = value.strip().strip('"').strip("'")
    return out


def load(path: Path = ENV_FILE, *, force: bool = False) -> None:
    """Populate os.environ from `path`, once per process. Missing file is not an error."""
    global _loaded
    if _loaded and not force:
        return
    _loaded = True

    for name, value in _parse(path).items():
        if name not in os.environ:
            os.environ[name] = value
            _from_file.add(name)


def get(name: str) -> str:
    """Value for `name` from the environment or `.env`, or "" if unset.

    READ ONCE PER PROCESS, which is right for everything that was in this file before D60: an
    API key and a mirror path are set before anything starts and do not change under a
    running process. For a value that DOES change while the process runs, see `get_live`.
    """
    load()
    return os.environ.get(name, "").strip()


def get_live(name: str) -> str:
    """Value for `name`, re-read from `.env` every time. For a secret that ROTATES.

    `get` CANNOT SEE A REPLACED VALUE, AND THAT MADE A REFUSAL'S OWN REMEDY NOT WORK (D60).
    Two caches sit in the way and they fail differently, so both had to go:

      - `load` returns early once `_loaded` is set, so a value ADDED to `.env` while the
        process runs is never seen at all; and
      - it only assigns a name that is not already in `os.environ`, so even `force=True`
        cannot REPLACE one it set earlier.

    Neither mattered before. `ANTHROPIC_API_KEY` and `PKMNSCAN_IMAGE_MIRROR` are placed
    before anything runs and do not change under it. `TCGPLAYER_STORE_COOKIE` is a session
    that EXPIRES: `server/tcg_export.py` refuses `tcg_session_expired` and tells the operator
    to sign in again and replace the value in `.env` — and under D53's supervisor, which runs
    for days and does not watch `.env`, `get` would have handed back the dead cookie forever.
    A refusal whose printed remedy does not work is worse than one that says nothing.

    THE PRECEDENCE IS UNCHANGED, which is the whole reason `_from_file` exists. A real
    environment variable still wins — that is what lets CI set one without editing a file —
    and it is told apart from a value this module lifted out of `.env`, which after `load`
    are the same thing to anyone reading `os.environ`. The file is consulted only for names
    the caller's environment did not already own.

    NOTHING IS WRITTEN BACK. Assigning the fresh value into `os.environ` would make it look
    like a real environment variable to the next call, and the rotation after that would be
    ignored — the same defect one turn later.
    """
    load()
    if name in os.environ and name not in _from_file:
        return os.environ[name].strip()
    fresh = _parse(ENV_FILE).get(name)
    if fresh is not None:
        return fresh
    return os.environ.get(name, "").strip()
