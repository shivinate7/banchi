# Settled decisions

Each file here is one decision, named `D<number>-<slug>.md`. A glob sorts the files into
corpus order. `ORDER.json` records that order, because three chunks are not entries. The
Deferred list, the Someday list and the v1 bug table sit between D79 and D80.

Every entry is closed. Sessions do not re-litigate an entry. To reopen one, name the entry and
the new evidence, then wait for the owner. When a decision changes, rewrite its entry in place.
Do not append history.

## How to find one

- **By id.** Open the file that starts with the number. Cite an entry as `D<n>`.
- **By subject.** `make map ARGS=--decisions` prints the id and title of every entry.
  `make map ARGS="D<n> --full"` prints one entry in full.
- **By the file you are about to edit.** `scripts/decision-context.py` runs as a hook before an
  edit and names the entries that govern the file.

## How to add one

A branch writes `D-<slug>.md` under this folder. The file starts with `## D-<slug> — <title>`,
and the branch cites it as `D-<slug>`. `make merge` claims the number, renames the file, and
rewrites every citation. A branch never picks its own number.
