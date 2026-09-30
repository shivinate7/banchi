"""The docs audit, one module per group of rows. `scripts/docs-audit.py` is the entry point.

Dependencies run one way: `core` first, then the row modules, then `rows` and `selftest`,
which name every check. A name that two row modules share lives in `core`.
"""

from __future__ import annotations

from . import (
    core,
    paths_commands,
    harness_criteria,
    records,
    code_invariants,
    env_map,
    games,
    reasons,
    status_reach,
    design,
    screens,
    strings,
    hygiene,
    registry_scopes,
    dispatch,
    spelling,
    rules,
    rows,
    selftest,
)

MODULES = (
    core,
    paths_commands,
    harness_criteria,
    records,
    code_invariants,
    env_map,
    games,
    reasons,
    status_reach,
    design,
    screens,
    strings,
    hygiene,
    registry_scopes,
    dispatch,
    spelling,
    rules,
    rows,
    selftest,
)
