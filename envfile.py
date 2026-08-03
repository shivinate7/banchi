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


def load(path: Path = ENV_FILE, *, force: bool = False) -> None:
    """Populate os.environ from `path`, once per process. Missing file is not an error."""
    global _loaded
    if _loaded and not force:
        return
    _loaded = True

    if not path.is_file():
        return
    try:
        text = path.read_text("utf-8")
    except OSError:
        return

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def get(name: str) -> str:
    """Value for `name` from the environment or `.env`, or "" if unset."""
    load()
    return os.environ.get(name, "").strip()
