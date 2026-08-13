"""Shared types for the T1-T7 tests.

Each test module exposes:

    NAME            "T1"
    DESCRIPTION     one line
    PASS_CRITERIA   the threshold. Published verbatim as the `- **Pass**:` line of this
                    test's section in docs/GATES.md, and `make docs-audit` blocks a commit
                    where the two disagree.

                    THE TEST IS THE SOURCE; THE GATE PUBLISHES IT. Change a threshold here
                    and update `### Tn` in docs/GATES.md to match — never the reverse. This
                    is where a threshold is argued about and changed; the doc is where it is
                    announced, and rewording a test to satisfy the doc makes the test worse
                    to please a checker. Five of six drifted while nothing enforced this.
    run() -> Result

A stub raises NotImplementedYet with a message beginning "NOT_IMPLE" + "MENTED". That
literal is also what scripts/stop-gate.sh keys on to know the harness is still
scaffolding: deleting the last one arms the Stop hook. So use it only in test modules,
and only to mean "this test is a stub" — it is split across a concatenation here so that
this file, which is not a test, does not count as one.
"""

from typing import List, NamedTuple, Optional


class Result(NamedTuple):
    passed: bool
    detail: str = ""


class NotImplementedYet(Exception):
    """Raised by a stub. The runner reports it as a failure, never as a skip."""


class Checks:
    """Collects assertions so one run reports every failure, not just the first.

    Same reasoning as the runner running every test after one fails: a harness is a
    status signal, and stopping early hides the state of everything behind it.
    """

    def __init__(self) -> None:
        self.lines: List[str] = []
        self.failures = 0

    def note(self, text: str) -> None:
        for line in str(text).splitlines():
            self.lines.append(f"       {line}")

    def ok(self, condition: bool, label: str, detail: str = "") -> bool:
        passed = bool(condition)
        self.lines.append(f"  {'ok  ' if passed else 'FAIL'} {label}")
        if not passed:
            self.failures += 1
            if detail:
                self.note(detail)
        return passed

    def equal(self, actual, expected, label: str) -> bool:
        return self.ok(
            actual == expected, label, f"expected: {expected!r}\nactual:   {actual!r}"
        )

    def raises(self, exc_type, fn, label: str) -> Optional[BaseException]:
        try:
            fn()
        except exc_type as caught:
            self.ok(True, label)
            return caught
        except Exception as caught:  # wrong exception is still a failure
            self.ok(False, label, f"raised {type(caught).__name__}: {caught}")
            return None
        self.ok(False, label, "did not raise")
        return None

    def result(self, headline: str = "") -> Result:
        body = list(self.lines)
        if headline:
            body.insert(0, headline)
        total = len(
            [line for line in self.lines if line.startswith(("  ok  ", "  FAIL"))]
        )
        body.append(
            f"  {total - self.failures}/{total} checks passed"
            if self.failures
            else f"  all {total} checks passed"
        )
        return Result(self.failures == 0, "\n".join(body))
