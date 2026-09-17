# Known gaps, deliberately unfixed

Findings recorded rather than repaired. Each says what is wrong, what it costs, and why it is
not fixed. This file exists so a green `make docs-audit` is not read as "the auditor is
complete" — it means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves when someone argues it should, the way
`docs/DECISIONS.md` entries are argued.

**Section 15 left 2026-09-07, and its number is not reused.** It recorded that the lockup does not
fit the 52px phone top bar, that the bar therefore kept `Logo` at 26 beside a "Banchi" title, and
that three costed ways out were waiting on the owner. D120 answered it — the bar was not grown,
the horizontal lockup was refused, and the bar took the collapsed rail's own drawing, so
`App.tsx`'s `PhoneBar` renders `BrandSlot`. **The argument lives in D120 and `docs/specs/logo.md`
section 19**, and nothing is left unfixed for this file to hold: the 2026-08-30 sweep below removed
closure narrative for exactly this reason, and a third copy of a settled fact is what goes stale
next. Sections 1 to 14 keep their numbers and section 16 keeps its own — a renumber leaves every
citation pointing at a real section that is not the one meant, which is `docs/map.py`'s own rule
for its step ids.

**Grouped by the work that would close them, not by when they were found** (2026-08-30). The
old chronological order hid the fact that five separate entries were one defect, and put two
one-line UI questions eleven sections apart. Each cluster names what unblocks it.

**Swept 2026-08-30**, from 1,401 lines. The majority was closure narrative for defects nobody
can hit any more; it is in git. Every surviving entry was re-checked against the tree, and
**three were wrong**:

- `check dispatch` said `--self-test` is "on no gate at all: not the pre-commit hook, not
  `make check`". `make check` has run `audit-self-test` since 2026-08-24 — recorded 900 lines
  further down in this same file.
- The `fixtures/` entry called a commit-time byte check "the tractable route, named rather
  than built". `scripts/githooks/pre-commit` has done exactly that since the repo's first
  commit.
- The registry table claimed six fields were read by nothing. Five now have consumers.

**The lesson, which is this file's own failure mode turned on itself:** an entry naming a
residue is a claim about the code, and no row of `make docs-audit` reads a claim made here. A
cluster is worth what a human re-checking it is worth, and that had not happened in
seventeen days.

---
