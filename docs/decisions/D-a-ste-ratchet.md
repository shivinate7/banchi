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
found three classes a machine can tell apart from ordinary prose without guessing:

- **Table row.** A `|`-delimited cell. The linter already exempts this shape from its
  sentence-level rules. It never extended the exemption to the word-level ones this ratchet
  tracks.
- **Decision-citation shorthand.** `(D<n>; …)`. The semicolon there separates an id from
  its gloss, not one clause from another.
- **The literal `VS Code`.** A false match on the abbreviation pattern, not the
  abbreviation itself.

A fourth class, `via`, is exempt too, on a different basis. See "Ruling one" below.

A fifth class, an enumeration collapsed into one paragraph, is named and left unbuilt. The
survey's own rule calls it a proxy. Three or more semicolons look like an enumeration. Some
genuinely long ones should become real bullet lists instead, so this class stays unbuilt.

A sixth class, verbatim quotation, was built and then removed. See "Ruling two" below.

`vs` in ordinary prose stays counted. Over half the sampled Latin-abbreviation findings were
this shape. Whether swapping the word reads better is a style call, not a mechanical one.

### The floor this leaves, named rather than hidden

The survey's own extrapolated floor, judging every borderline case against the writer, was
roughly 2.7 errors per 1,000 words, combined across the four rules. That figure predates the
rulings below. It is kept here as the survey's own number, not restated against today's pin.

This repo's built, MECHANICAL exemptions do not chase that floor. They remove two things
only: what a machine can prove, and what the owner has ruled by argument. They never remove
what a person's judgment would merely excuse. A ratchet that guessed at judgment calls could
not be trusted.

### The owner's rulings, 2026-09-19

Four questions went to the owner. Each answer below is a ruling, not a recommendation.

**Ruling one, on `via` and `vs`.** `via` is exempt. `vs` stays a real finding. The literal
`VS Code` stays exempt, as already built.

The rule's own stated reason for STE007 is that a Latin abbreviation reads differently to
different readers, and that machine translation handles it badly. That reason holds for the
rule's true abbreviations: the ones with a full stop, and the two-word Latin phrases. It
does not hold for `via`. `via` is not an abbreviation. It is an ordinary English
preposition. Every reader reads it the same way. It sits in the rule's table by category
error, not because it behaves like one. Plain-word style guides do prefer `through` or `by`
over `via`. A writer may still choose the plainer word on that ground. A gate is the wrong
instrument for a preference.

`vs` is the opposite case. It is a real abbreviation, of `versus`. The rule's own
replacement for it is `compared with`. It stays a finding.

**What could not be verified.** The published standard's own dictionary is not freely
available in full. Two searches did not settle whether `via` carries a specific entry
there. The argument above rests on the rule's own stated reason, and on the shape of its
word table, read directly. It does not rest on the standard's own text. This is recorded as
unmeasured, not as a settled fact.

**Ruling two, on verbatim quotation.** There is no exemption for a verbatim quotation. The
owner chose to rewrite around a quoted line that trips a rule, rather than exempt it.

The cost is named plainly, because the owner chose it with the cost in view. The
contraction rule measured 93.3% artifact in the survey. Almost all of that was verbatim
quotations of the owner's own words. Those findings now stay in the count. They come out
only when a document paraphrases the owner, rather than quoting the owner.

The pin below carries the count before and after this ruling.

**Ruling three, on the size reader.** `ENTRY_BUDGET` and the `entry budget` row stay. The
owner wants the constant re-derived against today's corpus of 219 entries. The owner also
wants its label corrected. The constant counts characters. Its own name and comment say
bytes. That work is its own pull request and its own reviewer. It is not built here. Every
line of `ENTRY_BUDGET` and the `entry budget` row is exactly as this entry found it.

**Ruling four, on the claim step.** A defect in the claim step is its own pull request. A
separate lane is taking it. Nothing about it is built or argued here.

### The pin, before and after every change on this branch

First pin, this branch's opening measurement, with all four exemption classes as first
built:

- Total 11,029. STE001 8,047. STE006 2,767. STE007 124. STE008 91.

After ruling two removed the verbatim-quotation class, before ruling one added `via`:

- Total 11,175. STE001 8,104. STE006 2,790. STE007 127. STE008 154.

After ruling one added the `via` exemption, the branch's current pin:

- Total 11,117. STE001 8,104. STE006 2,790. STE007 69. STE008 154.

STE001 and STE006 answer only to ruling two. They moved once, from the first pin to the
second. STE007 and STE008 moved on both rulings. The net move against the first pin is
+88, on the total.

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
