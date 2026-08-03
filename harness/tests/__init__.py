"""Shared types for the T1-T4 tests.

Each test module exposes:

    NAME            "T1"
    DESCRIPTION     one line
    PASS_CRITERIA   the threshold, verbatim from docs/GATES.md
    run() -> Result

A stub raises NotImplementedYet with a message beginning "NOT_IMPLE" + "MENTED". That
literal is also what scripts/stop-gate.sh keys on to know the harness is still
scaffolding: deleting the last one arms the Stop hook. So use it only in test modules,
and only to mean "this test is a stub" — it is split across a concatenation here so that
this file, which is not a test, does not count as one.
"""

from typing import NamedTuple


class Result(NamedTuple):
    passed: bool
    detail: str = ""


class NotImplementedYet(Exception):
    """Raised by a stub. The runner reports it as a failure, never as a skip."""
