## D246 — `commit path writes` reads the code, not `checks.py`'s own sentence about itself

**THE DEFECT.** `scripts/checks.py` gives each check a `writes` field. Its own comment says
the field is a sentence, not a flag. Before this entry, `check_commit_path` in
`scripts/docs-audit.py` read only whether that sentence was empty. It never opened the script
the entry names. A commit-path check could `Path.write_text` a tracked file. It could shell
out to something that writes. Its `writes` field could stay `""`. The row would still publish
"none of them writing". This branch already found the same shape twice. `paths` discarded the
line number it claimed to verify. `t3_join_coverage`'s own docstring says a one-directional
check "passes on that bug". D18 is what this row exists to assert: a generator may write, and
nothing that writes may gate a commit. Nothing checked the row's OWN evidence was real.

**WHAT THE ROW NOW READS.** Today two entries carry `commit_path: True`: `docs-audit` and
`sigil-check`. For each, the row parses `entry["runs"]` into its separate `&&`-joined
invocations. It resolves each named `.py` script and parses it with `ast`, never imported,
per this file's own read-only contract. For each invocation's own flags, it finds which
branch of the script's `main()` actually runs. This is mode-scoped on purpose: `docs-audit.py`
and `sigil-check.py` both dispatch on a flag inside `main()`. Scanning the whole file would
blame `--self-test`'s own fixture writers on the plain, no-flag invocation that never reaches
them. That is the same false claim this row exists to stop, aimed at itself. The row closes
over every locally defined function reachable from there by a plain `name(...)` call. It scans
that reachable AST for a fixed vocabulary of write-shaped calls.

  - A writing-mode `open()`.
  - A `Path`-shaped method matched by name — `write_text`, `write_bytes`, `unlink`, `rename`,
    and a few more. Bare `.replace()` is excluded on purpose. It collides with
    `str.replace()`, which is common in this file.
  - An `os` or `shutil` call, resolved through the file's own import aliases.
  - A `subprocess` call whose argv is fully literal and names a write-shaped git verb.

That evidence is reconciled against `entry["writes"]` BOTH WAYS:

  - The code shows a write and the field is empty. FAIL. This is the founding defect above.
  - The field declares a write and the code shows none. FAIL. A stale declaration gets the
    same two-directional discipline `t3_join_coverage` already argues for.

**WHAT IT STILL CANNOT SEE, NAMED RATHER THAN ASSUMED AWAY.** A write reached only through a
bound-method alias is invisible. `f = Path.write_text; f(p, s)` names no call this reader can
follow. A write reached through a base class's own dispatch is invisible too. Argparse calls
`self.error()`, which calls `sys.stderr.write()`. Neither call is a plain `name(...)` this
file's own control flow shows. A write inside an imported library's own code is invisible.
This reader follows only locally defined functions. A `subprocess` call whose argv is built
from a variable, a `*args` spread, or an f-string is invisible. `git(*args)`, defined and
called throughout `docs-audit.py` with read-only git subcommands, is exactly this shape.
Every one of its call sites is named as opaque here, not cleared. A script whose mode-switch
is not shaped as "an `if` testing a flag inside `main()`, calling one function, then
returning" gets read whole-file instead. That over-reports. It never quietly clears a check.

**MEASURED RESULT.** `docs-audit.py`'s own docstring claims "THE AUDIT NEVER WRITES." Read
this way, closing over the roughly 316 functions reachable from `audit()`'s own no-flag
invocation, that claim HOLDS. `self_test()` and its fixture writers are provably excluded
from the reachable set. They are not merely assumed off-path by trusting the
`--staged`/`--self-test` split. The two opaque `subprocess` calls in the reachable code are
named above, not cleared. `sigil-check.py` is checked under both its `--self-test` and its
bare invocation, because the hook runs both. It imports none of `os`, `shutil` or
`subprocess`. It shows no write-shaped call under either mode.

**PROVEN RED ON ITS OWN DEFECT.** `scripts/docs-audit.py --self-test` mutation-tests both
directions against the real files. Every mutant is restored from a `.bak` copy, never
`git checkout <path>`, never `git stash`. Two distinct mutants are planted in `scripts/sigil-check.py`, with `writes` left
empty in both. One is a `Path.write_text` inside `scan()`. The other is a `shutil.copy`
behind a locally aliased import inside `files()`. Both are killed. A mutant in
`scripts/checks.py` flips `sigil-check`'s own `writes` field to a false claim. The real
source stays untouched. That mutant is killed the other direction. A write-shaped mutant
planted in an off-commit-path script, `scripts/claim-ids.py`, produces no finding. That
proves the row's scope stays at the two entries `commit_path: True` actually names. The
unmutated pair passes with zero findings.

**WHY THIS IS WORSE-THAN-NOTHING AVOIDED, NOT MERELY IMPROVED.** A declaration checked one
way only trains the next reader to stop looking. A declaration checked against its own
restated opinion does the same. This branch already paid for that failure twice. A row that
now names its own blind spots is worth less trust than a proof. It is worth more than a
claim nobody opened the file to test.
