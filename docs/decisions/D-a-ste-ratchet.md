## D-a-ste-ratchet — A prose ratchet gets a reader, and bytes are not the ruler

The owner believed this repo already mechanized prose concision. It did not. `make vale`
carries two style rules. It gates nothing (D74, D18). `entry budget` counts characters. That
is a size proxy, not a prose-tightness ruler.

### The two problems, kept separate

**Problem one: nothing enforces Simplified Technical English.** A linter for this exists
outside the repo, at `$HOME/.claude/lint/ste_lint.py`. Nothing in this repo runs it.

**Problem two: `ENTRY_BUDGET` measures the wrong thing.** `scripts/docs-audit.py`'s own
comment already names this. It compares against Python `len()`. That counts characters, not
bytes. This entry does not touch `ENTRY_BUDGET`. It is a separate ruling, not yet made.

A measurement settles which problem this is. Total-errors-per-entry against entry size:
r = 0.898. That is a size proxy wearing a prose hat. Errors-per-1,000-words against entry
size: r = 0.0020. That reads the prose, not the document's length.

### The linter is vendored, not referenced

`scripts/ste/ste_lint.py` is a byte-for-byte copy of the linter above. `scripts/ste/
LICENSE-ste_lint` carries its MIT notice, unmodified, per the license's one condition. The
copy is a copy, never a symlink (D47). A fresh clone, a CI runner, and this repo's own git
history all lack `$HOME/.claude`. A gate here cannot depend on a path outside its own tree.

### Why the toolchain argument against Vale does not transfer

D74 widened Vale's file scope to every tracked `.md` file. D74's own text never argues that
a prose check must not gate a commit. That argument is D18's: nothing that writes may gate,
and a gate needing software present would make the opsec hooks depend on it too.

Vale is a third-party Go binary. The bare-`python3` pre-commit hook cannot depend on one
being present. The vendored linter is pure standard-library Python. That is the same
interpreter the hook already runs, with nothing else installed. So the toolchain objection
does not apply here. One property still needs protecting, either way: a machine holding
only this repo's own clone can run every commit gate in it.

### The ruler

The measure is STE errors per thousand words, per bucket and repo-wide. A flat byte cap was
ruled out. This ruler reads the prose, not the document's size. Word count is plain
(`text.split()`, matching `wc -w`), not the linter's own STE-adjusted count, which drops
headings and tables. The two counts answer different questions. Stating the difference once,
here, keeps them from being read as one.

Five buckets: `docs/decisions`, `docs/specs`, `docs/gates`, `docs/debts`, and `other` for
everything else tracked markdown reaches. A sixth, `repo`, is every file combined.

### Exemptions are a named, mechanical, proven class, or they do not exist

A sampled, hand-classified survey of 265 findings (`scratchpad/lane2-falsepositives.md`)
found four classes a machine can tell apart from ordinary prose without guessing:

- **Table row.** A `|`-delimited cell. The linter already exempts this shape from its
  sentence-level rules. It never extended the exemption to the word-level ones this ratchet
  tracks.
- **Verbatim quotation.** A blockquote line, or this repo's own `*"…"*` convention for a
  quoted spoken line. Ninety-three percent of the sampled contraction findings sat here. A
  contraction inside a quotation cannot be fixed without misquoting the speaker.
- **Decision-citation shorthand.** `(D<n>; …)`. The semicolon there separates an id from
  its gloss, not one clause from another.
- **The literal `VS Code`.** A false match on the abbreviation pattern, not the
  abbreviation itself.

A fifth class, an enumeration collapsed into one paragraph, is named and left unbuilt. The
survey's own rule calls it a proxy. Three or more semicolons look like an enumeration. Some
genuinely long ones should become real bullet lists instead, so this class stays unbuilt.

Bare `via` and `vs` in ordinary prose stay counted for the same reason. Over half the
sampled Latin-abbreviation findings were this shape. Whether swapping the word reads better
is a style call, not a mechanical one.

### The floor this leaves, named rather than hidden

The survey's own extrapolated floor, judging every borderline case against the writer, is
roughly 2.7 errors per 1,000 words, combined across the four rules. This repo's built,
MECHANICAL exemptions reach a smaller floor than that, by design. They remove only what a
machine can prove, not what a person's judgment would also excuse. The gap between the two
numbers is real prose debt. This ratchet does not hide that gap. It is also not a defect in
the ratchet. A ratchet that guessed at judgment calls could not be trusted.

### The ratchet, mirroring D194 and D218

A hard gate over an eleven-thousand-finding backlog would block every commit on day one.
This repo already owns the better shape, in its own copy-word-count ratchet and its own
typed-interpunct ratchet:

- A count that rises fails. It names which dimension rose: the total, one rule's own count,
  or one bucket's ratio.
- A count that falls, or ties, passes silently. It is printed, never a finding.
- A missing or unreadable pin file is its own failure. It is reported as unpinned, never as
  a pass over an empty comparison.

`scripts/ste-ratchet.json` holds the pin. `scripts/ste-ratchet-pin.py --pin` is the one
writer. It sits on no `make` target and no hook (D18). `git diff scripts/ste-ratchet.json`
is the receipt. `copy-budget.mjs` and `typed-interpunct-pin.mjs` already keep this same
discipline for their own ratchets.

`scripts/ste_measure.py` is the one shared measurer. Both the row and the pin script call
it. Neither reimplements it. No language boundary forces the one duplicated regex D218's
own pair had to accept.

### Scope

This entry does not change `make vale`. It does not change `ENTRY_BUDGET`'s value or its
row's behavior. Both stay exactly as they are. Nothing here rewrites the prose backlog by
hand. A pull request that lowered the count by editing entries would hide whether the
mechanism works.

### Governed by

D18 is why the row never writes, and why the pin script sits on no hook.

D47 is why the vendored linter is a copy, never a symlink.

D74 is the entry this correction cites accurately. It widened Vale's file scope. It never
argued that a prose check must not gate.

D194 and D218 are the two ratchets this one mirrors. A rise fails. A fall is silent. An
unpinned file is its own failure.

D173 names the mechanism: `make docs-audit`'s `ste ratchet` row.

---
