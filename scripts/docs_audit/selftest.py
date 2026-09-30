"""The `--self-test` driver: prove the extractors before trusting a report.

The cases live in the `selftest_*` modules, one `run` each, called in the order the
single function ran them.
"""

from __future__ import annotations

from typing import List

from . import selftest_records
from . import selftest_paths_commands_1
from . import selftest_paths_commands_2
from . import selftest_status_reach
from . import selftest_design
from . import selftest_spelling
from . import selftest_env_map
from . import selftest_registry_scopes
from . import selftest_code_invariants_1
from . import selftest_code_invariants_2
from . import selftest_strings
from . import selftest_code_invariants_3


def self_test() -> int:
    """Prove the extractors before trusting a report. Failures print and exit 1."""
    failures: List[str] = []

    def ok(condition: bool, label: str, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(label)
            if detail:
                for line in detail.splitlines():
                    print(f"       {line}")

    print("docs-audit self-test")
    print("=" * 72)
    selftest_records.run(ok)
    selftest_paths_commands_1.run(ok)
    selftest_paths_commands_2.run(ok)
    selftest_status_reach.run(ok)
    selftest_design.run(ok)
    selftest_spelling.run(ok)
    selftest_env_map.run(ok)
    selftest_registry_scopes.run(ok)
    selftest_code_invariants_1.run(ok)
    selftest_code_invariants_2.run(ok)
    selftest_strings.run(ok)
    selftest_code_invariants_3.run(ok)

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} self-test {'failure' if len(failures) == 1 else 'failures'}")
        return 1
    print("self-test clean")
    return 0
