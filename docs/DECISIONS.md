# Settled decisions — singles pipeline

**THE ENTRIES ARE IN `docs/decisions/`, ONE FILE EACH, AND THIS FILE IS A POINTER.** It was
one 1.4 MB document until 2026-09-12. Nothing reads it; `scripts/decisions_corpus.py` reads
the directory and hands every checker the same bytes it used to get from here.

Every entry is closed. Sessions do not re-litigate them. To reopen one, name the entry and
the new evidence, then wait for the owner. Rewrite entries in place when a decision changes
— do not append history.

## How to find one

- **By id** — the files are named `D<number>-<slug>.md` and sort
  into corpus order, so a glob and `ls` agree without anybody sorting.
- **By subject** — the index in `CLAUDE.md`, which is generated from these files by
  `python3 scripts/index-decisions.py --write` and reconciled against them on every
  `make docs-audit` by the `decision index` row.
- **By the file you are about to edit** — `scripts/decision-context.py`, the PreToolUse hook,
  names the governing entries before the edit and is the reason D60 dropped the `@`.

## Why it is a directory

**Two pull requests appending an entry to one file conflict textually every single time.**
It happened five times on 2026-09-11 alone, each costing a hand resolution of a 10,000-line
file. Two pull requests adding two files never conflict.

**This makes D60 better rather than worse.** That entry dropped the `@` because the corpus
cost ~163,000 tokens to load and a session needs one entry at a time. A monolith made "one
entry" something you could only get by parsing; a directory makes it something you open.

**The order is `docs/decisions/ORDER.json`, not the filesystem's.** Three chunks in it are
not entries — `Deferred`, `Someday` and the v1 bug table sat between D79 and D80 and still
do — so sorting by filename would move them, and `decision index` reconciles the index
against the headings in order.

The move was performed by `scripts/split-decisions.py` and is proved lossless by its own
`--verify`, which reassembles the directory and diffs it against the bytes this file used to
hold. `make decisions-selftest` runs that proof.
