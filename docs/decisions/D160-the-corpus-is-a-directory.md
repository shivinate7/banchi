## D160 — An entry is a file, because two branches appending to one file collide every single time

**One file held every settled decision, and on 2026-09-11 it conflicted five times.**
#275, #278, #281, and then #279 and #280 against
each other — every one a textual conflict at the end of the same document, every one costing
a hand resolution of a 10,000-line file, and not one of them a disagreement about anything.
Two branches each appended an entry; git cannot know they do not overlap.

**The corpus is `docs/decisions/` now, one markdown file per entry.** Two pull requests
adding two files never conflict. That is the whole change; everything else here exists to
keep the readers working across it.

**The numbers did not move and nothing was reworded.** 159 entries went out as D1..D159 in
their own files, byte for byte, and the three sections that are not decisions — Deferred,
Someday and the v1 bug table, which sat between D79 and D80 — went with them and still sit
there. A renumber would have been the worse half of this change by a wide margin: this tree
carries around ten thousand `D<n>` citations across 242 files, and D80 records what a
renumber costs when a stale id still resolves to a real entry that is not the one meant.

**The citations did not have to move either, and that is why this was affordable.** They are
bare ids — `D58`, not `docs/DECISIONS.md#D58` — so not one of the ten thousand changed. What
changed is where the RESOLVERS look, and they were six files.

## What performs it, and what proves it

**`scripts/split-decisions.py` performed the move and is committed beside its result.** A
1.4 MB hand split is unreviewable: a reviewer cannot tell a faithful move from one that
dropped a paragraph. The script cuts the file at every `## ` line, so every line of the
original lands in exactly one chunk and reassembly is concatenation.
**Losslessness is true by construction rather than by testing**, and there is no separator
convention to get wrong.

**The proof is `--verify`, and it was empty**: 1,463,927 characters reassembled identical to
the original, sha256 `e5032052940c5fed…`. `--verify-split REF` re-establishes it later by
reading both sides out of git at one commit, so the claim survives the original leaving the
working tree.

**The self-test asserts the ongoing claim and deliberately not the historical one.**
`make decisions-selftest`. The set is complete — every file the manifest names is present,
every file present is
named, no id is in two files. **It does not hash the live corpus.** An earlier draft did, and
it would have gone red on the very next decision entry, blaming a routine append for a loss
that had not happened. Editing an entry is the normal way this corpus changes.

**The order is `ORDER.json`, not the filesystem's.** Three chunks are not entries, so sorting
by filename would move them, and `decision index` reconciles the index against the headings
IN ORDER.

## The index is generated, which is the other half of the conflict

**A directory fixes the corpus and not the index.** Every appended entry also needed a line
typed into `CLAUDE.md`, in the right place, spelled the same way — so two branches that no
longer collide in the corpus would still collide there.
`scripts/index-decisions.py --write` emits it from the entry headings.

**Write-time, never check-time, which is D18's line.** The generator may edit `CLAUDE.md` and
is therefore not on the commit path; `make docs-audit`'s `decision index` row computes what
the index should say, compares, and blocks. Two programs on purpose — a generator that also
gated could satisfy itself.

Its first run found two drifts a hand-maintained index had already accumulated: D144
misaligned by a space, and a stray line.

## What `docs/DECISIONS.md` became, and why not the alternatives

**A stub that points at the directory.** Considered and rejected: a generated
concatenation, which would have reintroduced the conflict it is removing — every branch
regenerating it collides on 1.4 MB — and **deletion**, which breaks a path cited across the
tree and in merged pull requests nobody can edit. A stub is the only one of the three that
never conflicts, because nothing appends to it.

**This makes D60 better rather than worse, which looks like the opposite.**
That entry dropped the `@` prefix because the corpus cost ~163,000 tokens to
load and a session needs one entry at a time. A monolith made "one entry" something you could
only get by parsing; a directory makes it something you open. `path_for("D58")` is a real
answer now, and `scripts/decision-context.py` can name a file a session reads rather than a
region of one it must not.

## What the readers were, and the one thing that genuinely moved

Six files parsed the monolith: `scripts/docs-audit.py` (eleven call sites across ten rows),
`prose-guard.py`, `decision-context.py`, `claim-ids.py`, `revert-audit.py` and
`claim-selftest.py`. They read `scripts/decisions_corpus.py` now, which hands them the same
bytes, so **the rows assert exactly what they asserted before**. A split that also rewrote ten
audit rows would have been two changes wearing one diff, and only one of them provable.

**Two rows came out stronger rather than merely intact.** `decision ids` compares ACROSS the
corpus, because one id in two files is a duplicate a directory newly permits and a single
document could not express. `decision structure` and `entry budget` now report against the
entry's own file and line 1, instead of an offset into a file nobody scrolls to.

**A parent-relative reference inside an entry was the one real hazard, and the bytes won.**
D135 cites a dot-dot path that meant the repo root while the entry lived one directory
higher, and would now resolve one level too deep.
The resolver treats a relative reference inside a moved entry as rooted at
`docs/` — preserving the author's meaning, rather than editing entry text inside a change
whose whole claim is that it edited none.

## This entry is the first written into the directory, not the last into the file

It is a claim slug, allocated at the merge by `make merge` (D140), and it lives in
`docs/decisions/` like every other entry. The alternative — writing it into the monolith one
last time — would have put the argument for the directory inside the file the same commit
deletes, and left the claimer with a heading in a file that no longer exists.
