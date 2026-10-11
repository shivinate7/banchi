---
description: Audit the markdown against the code it describes, and propose fixes for review.
allowed-tools: Bash(python3 scripts/docs-audit.py:*), Bash(make docs-audit), Bash(git diff:*), Bash(git status), Bash(git log:*), Read, Grep, Glob, Edit
---

Audit this repo's documentation against the code, and propose changes for the owner to
approve. Scope: $ARGUMENTS (empty means that the working tree against `HEAD`).

This is the semantic half of D16. `scripts/docs-audit.py` already checks everything a
machine can settle; run it and read the roster — every row is named, and marked blocking
or advisory. Your job is the part it cannot: **prose that is still grammatical, still
well-formed, and no longer true.**

## Run it in this order

**1. Mechanical first.**

```bash
python3 scripts/docs-audit.py
```

Exit 1 means that there is a provably wrong reference. Exit 2 means that **any ADVISORY row has findings**. Exit 0 means neither. Report what it found — do not re-derive it by hand.

**Exit 2 is not the coupling question**, which is what this line said until 2026-09-05. The coupling row only runs under `--staged`. But `entry budget`, `game coverage`, `views exposure` and several others emit ADVISORY on every plain run. So exit 2 is the ordinary outcome here, not a signal that staged code and its docs disagreed. Read the rows; the code says which.

**2. Read the diff, then the docs it touches.**

`git diff HEAD` (or the range in `$ARGUMENTS`). Map changed source to the docs that
describe it using the same coupling in `scripts/docs-audit.py`:

| Source | Doc |
|---|---|
| `pipeline/` `identify/` `geometry/` `store/` `cli/` | `docs/specs/batch-script.md` |
| `harness/tests/` `harness/run.py` | `docs/GATES.md` |
| `Makefile` `cli/__main__.py` | `README.md`, `CLAUDE.md` |

Read the coupled docs in full. A claim three paragraphs from the changed line is still a
claim.

**3. Judge each candidate against a real bar.**

When a specific sentence is now **false**, report a finding, and only then. A finding is a described default that changed, a flag that no longer exists, or steps out of order. A stated guarantee the code stopped making is also a finding. Wording you would have phrased differently is not a finding. Neither is a section you would have organized another way. Prose that is merely terse is not a finding either.

`docs/decisions/` needs its own care. Entries there are settled rulings, and its header
says sessions do not re-litigate them. When it describes the implementation incorrectly, a decision entry is stale. No other case makes it stale. **A decision you disagree with is not a finding.** If the code
contradicts a decision, that is a code finding — report it as one and leave the entry alone.

## Then, before you touch anything

Print the whole set at once:

| # | File:line | What the doc claims | What the code does | Proposed change |
|---|---|---|---|---|

One row per finding, one line each. Then ask how to proceed, offering: **all**, **none**, or
**specific numbers**. The owner sees the shape of the entire edit before approving any of it. That is the point of this step. So never begin editing during the walk-through. Never present findings one at a time in a way that hides the total.

If the set is empty, say so plainly and stop. A clean audit is a result.

## Applying

- Edit only the lines the approved rows name. No reformatting, no reflowing, no
  "while I was in there".
- Match the surrounding voice. These docs argue for their decisions and state what a
  failure would cost; a flat rewrite loses the reasoning that makes them worth reading.
- Keep the 96-column wrap the files already use.
- When done: `git diff --stat -- '*.md'` and then the full `git diff -- '*.md'`.

**Never `git add`. Never `git commit`.** Leave the tree dirty. The owner reviews with their
own `git diff` and stages what they want. That final read is the last check in the chain.
It is not yours to skip on their behalf.

## The rule that matters most

> **A blocked commit is reported, not resolved.**

If the pre-commit hook blocked a commit, show the findings and the proposed markdown change
and **wait**. Never edit a doc for the sole purpose of getting a commit through. Never
reach for `BANCHI_DOCS=off` or `--no-verify` on the owner's behalf. Both are theirs to
choose. `--no-verify` also switches off the three opsec rules guarding code-card
bearer instruments.

The docs are this project's memory and its reasoning. An agent that edits them to satisfy
its own gate converts that memory into fiction, one plausible sentence at a time. The gate
exists to catch drift, not to be satisfied.
