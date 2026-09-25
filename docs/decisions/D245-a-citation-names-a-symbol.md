## D245 — A citation names a symbol, not a line, and a line-number row sees only the half that shrank

**Unreadable.** A citation written `path:N` was invisible to every row in this repo.
`scripts/docs-audit.py`'s `_CANDIDATE_RE` carries no `:` in its character class. So line 884
of `docs/GATES.md` was extracted as the bare filename, the file resolved, and the `paths` row
reported "references resolve". A citation could point at a line deleted weeks earlier and the
row stayed green. The row was not wrong about what it checked. It was read as checking
something wider.

### The measurement, and why the obvious guard is the wrong one

**Thirteen visible.** 713 line anchors were in the staged documents, and 13 pointed past
their target's end. Three of those targets are now index stubs of 38, 92 and 66 lines. They
are `docs/DECISIONS.md`, `docs/DEBTS.md` and `docs/GATES.md`, their records split into one
file each. The 13 are visible only because those three files got SHORTER.

**The disease is far wider.** Of 443 anchors into code, 313 name an identifier in the same
sentence. Those can be checked without reading meaning.
**219 of them point at the wrong line**, a rate of 69.7%. A stricter probe counted only sentences naming a bare identifier
rather than a path. It put the rate at 183 of 206, or 89%.

The two populations are genuinely different and are NOT reconciled here. Neither definition
leaves the direction in doubt. Most line anchors into code in this repo are already wrong.

Four were checked by hand and all four were genuine. `_blank_number_by_name` was cited at
line 1192 and is really at 1384. `do_pipeline_scope` was cited at 2455 and is really at 6537.
`bandOf` was cited at 340 and is really at 472. `pokemon_code`, cited at 689, is absent.

**So the obvious row is the wrong one.** A row that only asks whether line N exists would go
green over 219 known-wrong citations, printing a confident verdict while doing it. That is
the defect this entry exists to remove, one level up. A guard reading green over its own
subject is the founding complaint here. It was the first design proposed for this work, and
the measurement rejected it.

### What is built, and what each clause can see

A line number rots on the next edit to any line above it. A symbol does not. `check_paths`
already verified a `module.attribute` citation against `module_attributes()`. The primitive
existed. The work is to move prose onto it, not to build a second reader for a form nothing
can keep true.

**Clause A — the line must exist.** `path:N` and `path:N-M` fail when the file is shorter.
Hard fail.

**Clause B — no anchor into a split-record stub.** The roster is derived from which corpus
module reads a directory rather than the file. It is never typed. This clause catches two
citations Clause A is structurally blind to, both in `docs/specs/capture-server.md`. One
named lines 5 to 7 of `docs/GATES.md`. The other named lines 11 to 15 of `docs/DEBTS.md`.
Both landed on real lines holding unrelated text, because the stubs are longer than the
anchors.

**Clause C — a per-file ratchet.** It counts anchors per citing file, in D229's shape,
because a repo-wide number is one every merge takes from somebody. Every anchor counts,
resolving or not. The owner's ruling was "leave nothing alone".

**A file the pin has never seen is held to zero.** This is where the clause departs from the
STE ratchet it otherwise mirrors. That ratchet measures a ratio over prose that already
exists, where a new file at its own natural rate is reasonable. This one counts an absolute
number of a thing ruled to only go down. New documents are where new citations get written.
Mirroring the other rule would leave the ratchet open on precisely its own subject.

**The TypeScript reader** extends the `module.attribute` form to `.ts` and `.tsx`. Both were
in `KNOWN_SUFFIXES` and so never reached the fallback. The reader works statically. Its
docstring names what it cannot see: a symbol from a generic factory, a re-export, and a name
assembled at run time.

### What the row cannot see, stated rather than implied

D149, a section number that resolves is not a citation that is right, ruled that no check can
read what a sentence is about. It measured the nearest proxy at one genuine catch against
three false alarms over 38 citations, and declined it.

**Nothing here repeals that.** These clauses read SHAPE. A citation pointing at a real line
whose content has moved stays invisible. That is 219 of 313 checkable code anchors today.
Clause B is the one slice where shape and meaning coincide, and only because a stub's records
are all somewhere else by construction. The ratchet governs the inflow. It makes no existing
citation right.

**The rot reader is a measurement and never a gate.** It recomputes the rate each run. A
number typed into this entry would rot exactly like the citations it describes.

**It was wrong on its first build.** It scored a citation as verified when the file's own
name appeared inside the file. A citation of line 1192 in `pipeline/join.py` contributed the
token `join`. **59 of 155 hits, or 38%, were carried by nothing else.** A further 118
sentences named no real identifier and were folded into the denominator as checkable. That is
D149's own closing lesson reproduced inside the reader built to honour it. A probe that finds
nothing reports nothing, and nothing reads as green. Tokens from the anchor's own path are
now excluded. An arm asserts that a sentence whose only backticked span is the citation
scores not-checkable.

### The exemption, and why it is four lines and not a file-level pass

D149 names four addresses in the file `docs/DECISIONS.md` used to be. Those are a RECORD of
where wrong citations stood when that file was one document. Rewriting them falsifies the
record. They are exempt by name in `scripts/docs-audit-line-allow.txt`, which refuses an
entry once its anchor resolves again.

**A file-level exemption was proposed and rejected.** Its subject was
`docs/specs/capture-server.md`. That file's own header calls it "the record of a plan that
ran" and states that its line numbers have moved, which reads as an argument to leave it
alone. It is cited as live authority by more than twenty sites, several of them in code.
`pipeline/join.py` calls its section 6.3 the only label formula in the repo.
`server/capture_server.py`, `geometry/__init__.py`, `harness/tests/t7_store_and_seams.py` and
`scripts/lan-check.py` cite its sections as binding. Those callers cite it by SECTION, which
is the durable form. All 19 of its anchors were converted.

**Two were not address problems.** They were not repaired as though they were. One asserted a
`docs/GATES.md` sentence that appears nowhere in this tree. The rule survives in CLAUDE.md's
working agreement, already cited in the same passage. So the dead pointer was dropped rather
than re-aimed at a nearby record, which would manufacture a source. The other named a
`docs/DEBTS.md` framing rewritten away before the split. That sentence now says so, instead
of naming an address no reader can use.

### A measured tension, recorded and not acted on

**Concision raised the error ratio.** Deleting 19 error-free words moved that file from
13.985 to 14.018 errors per thousand words. The error count held at 113 while the denominator
shrank. So the concision this repo asks for and the error-rate ratchet pull in opposite
directions. It fired on the first prose deletion this work made. It is recorded here for the
owner's ruling rather than fixed, on their word.

### Proved by violating it

Every clause was mutation-tested. Each was then re-tested by the orchestrator in a separate
checkout, rather than accepted on a builder's report. A citation past the end goes red, and
one in range goes green. A range anchor's upper bound past the end goes red. An anchor into a
stub goes red, and the same number into a non-stub file goes green. A raised per-file count
goes red. A lowered one is accepted silently and printed. An allow entry whose anchor
resolves again goes red. Restores were made from a `.bak` copy, never `git checkout <path>`.

**This entry was itself refused by the row.** Its first draft quoted three stale anchors as
examples and cited D149 by path. The guard caught all four before the commit.

The row gates and writes nothing. `scripts/line-anchors-pin.py --pin` is the generator. It is
on no target and no hook, and a person runs it on purpose (D18).

### Superseded in part 2026-09-24 — `D-ratchets-become-offender-lists`

**Clause C's pin is gone. The rule stays.** A citation still names a symbol, never a line. The owner's ruling was "convert both of the last pins". The `line anchor ratchet` row is now the `line anchor offenders` row. It fails on each anchor that `scripts/line-anchor-offenders.json` does not list, by file and by anchor as written. It also fails on a stale entry, and on growth over the list at the merge-base. A new file still starts clean, unless the anchor moved out of another file. Growth is counted over the whole list, so the total of each anchor never rises and the inflow stays shut. `scripts/line-anchors.json` and `scripts/line-anchors-pin.py` are deleted.

**What is kept.** Clauses A and B, the `line anchor allowlist` row, the printed rot rate, and "leave nothing alone": every anchor is listed, resolving or not.
