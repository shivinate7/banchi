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

# THE SAME SET, CARRIED ACROSS A SPAWN, BECAUSE HALF THE PRECEDENCE RULE WAS A PROCESS GLOBAL
# AND EVERY CHILD HERE IS HANDED `dict(os.environ)` (2026-09-11). `scripts/serve.py:_child_env`
# and `server/pipeline_routes.py:_env` copy the environment wholesale, which is right — a child
# must inherit `PKMNSCAN_HOME` or it would run against another store — and it is also how the
# distinction above is lost at the first process boundary: the child sees a value this module
# lifted out of `.env` and cannot tell it from one the operator exported, so `get_live` returns
# it and never reads the file. The rotation the whole of `get_live` exists for stops working one
# process down.
#
# MEASURED ON THE OWNER'S OWN MACHINE, 2026-09-11. The capture server under the main checkout
# carried `ANTHROPIC_API_KEY`, `TCGPLAYER_STORE_COOKIE` and `PKMNSCAN_LAN_NAME` in its initial
# environment — all three lifted out of `.env` by D53's supervisor, which reads exactly one of
# them. The sibling checkout, which has no `.env`, carried none of the three. So this was not a
# hazard waiting to happen: it was the state of the process the owner was using.
#
# NAMES ONLY, NEVER VALUES. The values are already in the environment beside it and a secret
# copied to a second place is a second place to leak it. `ps eww` shows a process's initial
# environment, which is how the measurement above was taken without reading `.env` at all.
FROM_FILE_ENV = "PKMNSCAN_ENV_FROM_FILE"


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


def _inherited() -> set:
    """The names a parent process lifted out of `.env`. See `FROM_FILE_ENV`."""
    return {name for name in os.environ.get(FROM_FILE_ENV, "").split() if name}


def _publish() -> None:
    """Put `_from_file` where a child will find it, since children are spawned with a copy of
    `os.environ` and nothing else travels. Written into the environment rather than passed at
    each spawn site so a spawn site added later inherits the rule instead of having to know it.
    """
    _from_file.discard(FROM_FILE_ENV)
    if _from_file:
        os.environ[FROM_FILE_ENV] = " ".join(sorted(_from_file))


def load(path: Path | None = None, *, force: bool = False) -> None:
    """Populate os.environ from `path`, once per process. Missing file is not an error.

    THE DEFAULT RESOLVES AT CALL TIME, NEVER AT DEFINITION TIME. `path: Path = ENV_FILE` in
    the signature would bind the module global's value the moment Python reads this `def`,
    so a caller that later redirects `envfile.ENV_FILE` (as harness/tests/t7_store_and_seams.py
    does, seven times) would find a bare `load()` still reading the ORIGINAL file. `get_live`
    below already got this right one line after its own `load()` call, by reading `ENV_FILE`
    at call time through `_parse(ENV_FILE)` — this function disagreed with itself.
    """
    global _loaded
    if _loaded and not force:
        return
    _loaded = True
    if path is None:
        path = ENV_FILE

    # A PARENT'S LIFTED NAMES ARE THIS PROCESS'S LIFTED NAMES. Adopted before the file is read
    # so a name the parent lifted and this `.env` no longer carries is still known to have come
    # from a file rather than from a shell.
    _from_file.update(_inherited())

    for name, value in _parse(path).items():
        if name == FROM_FILE_ENV:
            continue  # a `.env` line may not forge the marker
        if name not in os.environ:
            os.environ[name] = value
            _from_file.add(name)

    _publish()


def get(name: str) -> str:
    """Value for `name` from the environment or `.env`, or "" if unset.

    READ ONCE PER PROCESS, which is right for a value that is placed before anything starts
    and does not change under it — a mirror path, a LAN name. IT IS NOT RIGHT FOR A SECRET:
    both of this repo's rotate, and `ANTHROPIC_API_KEY` was read through here until 2026-09-11
    on the judgement corrected in `get_live` below. For a value that changes while the process
    runs, see `get_live`.
    """
    load()
    return os.environ.get(name, "").strip()


def get_live(name: str) -> str:
    """Value for `name`, re-read from `.env` every time. For a secret that ROTATES.

    `get` CANNOT SEE A REPLACED VALUE, AND THAT MADE A REFUSAL'S OWN REMEDY NOT WORK (D64).
    Two caches sit in the way and they fail differently, so both had to go:

      - `load` returns early once `_loaded` is set, so a value ADDED to `.env` while the
        process runs is never seen at all; and
      - it only assigns a name that is not already in `os.environ`, so even `force=True`
        cannot REPLACE one it set earlier.

    `TCGPLAYER_STORE_COOKIE` is a session that EXPIRES: `server/tcg_export.py` refuses
    `tcg_session_expired` and tells the operator to sign in again and replace the value in
    `.env` — and under D53's supervisor, which runs for days and does not watch `.env`, `get`
    would have handed back the dead cookie forever. A refusal whose printed remedy does not
    work is worse than one that says nothing.

    THIS DOCSTRING JUDGED `ANTHROPIC_API_KEY` A VALUE THAT "DOES NOT CHANGE UNDER A RUNNING
    PROCESS", AND THAT WAS WRONG. An API key is placed before anything starts and it also
    EXPIRES, and the operator does the same thing about it that they do about the cookie: paste
    a new one into `.env`. Measured 2026-09-11, on the owner's: the key expired, they replaced
    it, and `./pkmnscan identify` and the `#/runs` press both kept failing with the dead one —
    `make down` / `make up` was the only thing that picked up the new key, which is the restart
    discipline D53 exists to make unnecessary. `PKMNSCAN_IMAGE_MIRROR` keeps the judgement and
    keeps `get`: a path to a disk is not a credential and does not expire.

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
