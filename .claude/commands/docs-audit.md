---
description: Audit the markdown against the code it describes, and propose fixes for review.
allowed-tools: Bash(python3 scripts/docs-audit.py:*), Bash(make docs-audit), Bash(git diff:*), Bash(git status), Bash(git log:*), Read, Grep, Glob, Edit
---

Audit this repo's documentation against the code, and propose changes for the owner to
approve. Scope: $ARGUMENTS (empty means the working tree against `HEAD`).

This is the semantic half of D16. `scripts/docs-audit.py` already checks everything a
machine can settle — sixteen checks: paths, the allowlist, `make` targets, `./pkmnscan`
subcommands, test ids, thresholds and their verbatim wording, decision numbers in docs and
in code, env vars, the current gate, every claim in `docs/map.py`, the sources
`scripts/status.py` declares, its own published check count, and checks named by position
in the docs and in code. Your job is the part it cannot: **prose that is still grammatical,
still well-formed, and no longer true.**

## Run it in this order

**1. Mechanical first.**

```bash
python3 scripts/docs-audit.py
```

Exit 1 means a provably wrong reference; exit 2 means the coupling question fired; exit 0
means neither. Report what it found — do not re-derive it by hand.

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

Report a finding only when a specific sentence is now **false** — a described default that
changed, a flag that no longer exists, a sequence of steps in the wrong order, a stated
guarantee the code stopped making. Not: wording you would have phrased differently, a
section you would have organized another way, or prose that is merely terse.

`docs/DECISIONS.md` needs its own care. Entries there are settled rulings, and its header
says sessions do not re-litigate them. A decision entry is stale only when it describes the
implementation incorrectly. **A decision you disagree with is not a finding.** If the code
contradicts a decision, that is a code finding — report it as one and leave the entry alone.

## Then, before you touch anything

Print the whole set at once:

| # | File:line | What the doc claims | What the code does | Proposed change |
|---|---|---|---|---|

One row per finding, one line each. Then ask how to proceed, offering: **all**, **none**, or
**specific numbers**. The owner sees the shape of the entire edit before approving any of
it — that is the point of this step, so never begin editing during the walk-through, and
never present findings one at a time in a way that hides the total.

If the set is empty, say so plainly and stop. A clean audit is a result.

## Applying

- Edit only the lines the approved rows name. No reformatting, no reflowing, no
  "while I was in there".
- Match the surrounding voice. These docs argue for their decisions and state what a
  failure would cost; a flat rewrite loses the reasoning that makes them worth reading.
- Keep the 96-column wrap the files already use.
- When done: `git diff --stat -- '*.md'` and then the full `git diff -- '*.md'`.

**Never `git add`. Never `git commit`.** Leave the tree dirty. The owner reviews with their
own `git diff` and stages what they want — that final read is the last check in the chain
and it is not yours to skip on their behalf.

## The rule that matters most

> **A blocked commit is reported, not resolved.**

If the pre-commit hook blocked a commit, show the findings and the proposed markdown change
and **wait**. Never edit a doc for the sole purpose of getting a commit through, and never
reach for `PKMNSCAN_DOCS=off` or `--no-verify` on the owner's behalf — both are theirs to
choose, and `--no-verify` also switches off the three opsec rules guarding code-card
bearer instruments.

The docs are this project's memory and its reasoning. An agent that edits them to satisfy
its own gate converts that memory into fiction, one plausible sentence at a time. The gate
exists to catch drift, not to be satisfied.
