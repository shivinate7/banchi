"""Strip machine-local absolute paths out of anything about to be published.

THE BUNDLE GOES TO A PUBLIC HOST. `/status` and `/pricing` both answer with real filesystem
paths — `captures_root`, `store`, the corpus file — and on a developer's machine those begin
`/Users/<name>/`, which publishes the operator's account name and their directory layout to
anybody who opens devtools on the demo. Nothing on a screen renders them; they are
diagnostics meant for a person standing at the desk.

REWRITTEN RATHER THAN REMOVED, and the shape is kept on purpose: a screen that decides to
draw one of these should still receive a string of the right kind. What must not travel is
the machine.

EXACT PREFIXES, NOT A PATTERN. A regex over `/Users/...` has to guess where the path ends,
and a first attempt at one truncated at the first character class it got wrong and produced
`/demoshivinate/Developer/...` — a string that still carried the account name it was written
to remove. The roots are known exactly, so they are replaced exactly, longest first so that
a demo store nested inside the checkout is rewritten as the demo store rather than as the
checkout.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


def replacements(repo_root: Path, home: Path) -> List[Tuple[str, str]]:
    """The prefixes to rewrite, longest first.

    `home` before `repo_root`: `PKMNSCAN_HOME=demo` puts the demo store INSIDE the checkout,
    so the two share a prefix and the more specific one has to win or every demo path is
    rewritten as a checkout path.
    """
    pairs = [
        (str(home.resolve()), "/demo"),
        (str(repo_root.resolve()), "/banchi"),
        (str(Path.home()), "/home"),
    ]
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def scrub(value, pairs: List[Tuple[str, str]]):
    """`value` with every known machine root rewritten, recursively."""
    if isinstance(value, str):
        for needle, stand_in in pairs:
            if needle in value:
                value = value.replace(needle, stand_in)
        return value
    if isinstance(value, list):
        return [scrub(item, pairs) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item, pairs) for key, item in value.items()}
    return value


def audit(payload: str) -> List[str]:
    """Anything that still looks like somebody's home directory, as a list of samples.

    The scrubber's own check, run over the finished document rather than trusting the walk
    above to have visited every branch of it. A publish step that cannot prove the result is
    clean is one nobody can safely leave running in CI.
    """
    hits: List[str] = []
    for marker in ("/Users/", "/home/", "C:\\\\Users"):
        start = 0
        while True:
            at = payload.find(marker, start)
            if at == -1:
                break
            hits.append(payload[at:at + 60])
            start = at + 1
            if len(hits) >= 5:
                return hits
    return hits
