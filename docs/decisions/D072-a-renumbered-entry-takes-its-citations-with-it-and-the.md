## D72 — A renumbered entry takes its citations with it, and the branch's own history is what says one moved

**Built 2026-08-30, after `docs/map.py` was found citing D67 in 24 places where it meant D69.** The order-screen entry was D67 while its branch was open; main took 67 and 68, and the renumber to D69 reached `docs/DECISIONS.md` and some prose but not the map's citations. Nine OTHER D67 citations in that same file were the real entry — the number-composition one — so no sweep could be run blind, and the wrong ones read as ordinary prose: *"the order transport (D67)"*, *"(D67) gave each its own route"*.

**EVERY DECISION CHECK THIS REPO HAD ASKS WHETHER A CITED ID EXISTS, AND A RENUMBER BREAKS NONE OF THEM.** `check_decision_ids` says the same thing about a duplicate heading in its own comment — *"the citation is then not wrong in a way anything can see — it points at a real heading, just not the intended one"* — and that sentence is exactly as true when one entry moves as when two share a number. `check_map`'s superset rule is one-directional by construction: a decision a file cites must appear in `governed_by`, so a **wrong** entry there is invisible, and prose inside a `does` string is read by nothing at all.

**Thirteen renumber events are in this repo's history and the collisions are structural.** `D50 -> D51 -> D53`, `D50 -> D52 -> D54`, `D61 -> D62 -> D64`, `D65 -> D66`, `D67 -> D69`, `D67 -> D70`, `D69 -> D71`. Several branches take "the next free number" against one base and all of them merge; D16 already carries the three-headings-at-D50 incident, which is the same collision landing a step earlier.

### The title is the identity, and the branch is the scope

**A renumber is a heading that KEPT ITS NAME AND CHANGED ITS ID**, which is the one pair no id-based check can see and the only signal that needs no judgement. `moves_across` reads it out of a sequence of states and is pure for exactly that reason: the git walk around it cannot run without a repository, and the logic that could be wrong is the part that must be testable. Five cases in `--self-test` floor it, and every id in them is real history rather than invented, so the data does not fall into the illustration problem `governed_by` already carries for `D2`.

**An entry that moved TWICE reports its FIRST id.** `D50 -> D51 -> D53` is real, and the citations that need chasing were written while it was D50; reporting the middle id would name a number nobody wrote and miss every site.

**Branch-scoped, which is what makes it quiet.** The renumber that matters is the one this branch did, and the files that matter are the ones this branch touched — a `D67` that main already had is not this branch's to move. On main, `merge-base` is `HEAD` and the row is empty for nothing. `origin/main` is the reference rather than `main`, because a worktree commonly has no local `main`: CLAUDE.md's merge discipline keeps it checked out somewhere else.

**NOT `--staged`, AND THAT IS THE LOAD-BEARING HALF.** The `D67 -> D69` renumber was committed in `9d7f473`, a MERGE — *"Merge origin/main: D67 was taken twice over"* — and git runs no pre-commit hook for a merge commit. A staged-only check would have missed it, and would have missed most of the thirteen: renumbering is what a session does while resolving a merge, by definition. Reading the branch's own commits catches it however it was committed, and the Stop hook runs this at turn end.

### Advisory, because the last step is a judgement and the list is the product

**Replayed against `9d7f473` it names nine files, and two of them were wrong.** `docs/map.py` and `app/src/Orders.css` carried the corruption; the other seven — `CLAUDE.md`, `app/src/types.ts`, `app/tests/inventory.spec.ts`, `docs/DEBTS.md`, `harness/tests/t7_store_and_seams.py`, `scripts/docs-audit.py`, `server/capture_server.py` — cite the number-composition entry and are correct. **Nothing mechanical separates those two groups**, and a check that blocked would have to be right about which is which. What nobody had was the list, and the list is what this row is.

**A file naming BOTH ids is annotated and is not evidence either way.** `docs/map.py` named both and was wrong in 24 places and right in 9; `app/src/types.ts` named both and is right in both. The finding says so rather than ranking on it, because a hint that reads as a verdict is worse than none.

### Amended 2026-09-11: the half that is this branch's own line blocks

**The sentence above — *"nothing mechanical separates those two groups"* — is true of a site the branch INHERITED and false of one the branch WROTE.** The row is two rows now. `renumbered ids` keeps the first half, its wording and its ADVISORY severity; `vacated ids` is the second half and it fails the commit.

**What made the split necessary.** A branch holding `## D132` merged main twice. Main had taken 132, 133 and 134, so the branch moved to D135; four commits later main had taken 135 and 136 too, so it moved again. **After the first of those renumbers three prose citations in `CLAUDE.md` still said D132** — the `make up` comment block, the `make dev` comment block, and a pointer to that branch's own spec — and all three silently named main's unrelated inventory decision. A stale id RESOLVES, so nothing failed: `make check` was green, the commit hook passed, and the branch was pushed. They were found afterwards by a separate audit, not by the tree. The advisory row named them and nothing had to read it, which is D16's own account of what an advisory row costs.

**What makes a site provable is three facts git already holds.** A line citing `old` is this branch's mistake when it is present in the tree NOW, absent at the MERGE BASE, and already present at the commit just BEFORE the one that vacated `old`. The last clause is the argument: **two headings may not share an id** — `decision ids` blocks that, and D16 records the incident — so at the moment that line was written `old` named exactly ONE entry in this branch's tree, the entry that has since moved. The citation therefore means the moved entry, and the move left it behind. Nothing is left to judge, which is this entry's own test for mechanical, and D16's.

**The third clause is there rather than "every line this branch added", and that is not caution for its own sake.** A branch that vacates D132 and LATER writes prose about main's D132 has added a line citing the old id that is perfectly correct. Blocking it would be the false positive D16 says is worse than a printed line, on a row with no escape hatch. It goes to the advisory row instead, where a human reads it — and the self-test carries that case as an arm, because a rule with no counter-example in its tests is a rule nobody can see the edge of.

**Per LINE, never per file.** After a merge both ids legitimately live in one file — `docs/map.py` carried 24 wrong and 9 right — so a file naming both is not evidence about any line in it. The advisory row already annotated this and never decided on it; the blocking row could not have been built on the file as the unit at all.

**And deduped by RESOLVED path, which is new since D135.** `AGENTS.md` is a tracked symlink to `CLAUDE.md`, and `branch_files` lists it by name the moment the link itself is added or changed — `read()` then follows it and reports every one of `CLAUDE.md`'s citations a second time, under a path a person cannot edit. The real file wins where both are listed. `.agents/skills` was the directory half of this and `branch_files` already guarded it; this is the file half, and it arrived with the same decision.

**Mutation-tested against a real repository, five arms.** `moves_across` and the new `vacating_index` are pure and floored on their own data; what is left is the part that reads blobs, follows a symlink and decides per line, and all three of those were wrong in draft. The self-test builds a throwaway repo with a base, a branch that writes its entry and cites it, and a merge that moves the id, then points the module's `ROOT` at it. Dropping the merge-base clause, the before-the-move clause, the symlink dedupe, or the MECHANICAL severity each turns an arm red.

**This does not widen the advisory row and does not narrow it either.** Every site it named before, it still names, minus the ones now blocked and the duplicates a symlink was producing. What changed is that the provable ones stopped being a question.

### Retired 2026-09-11: a branch does not take a number, so nothing renumbers

**`renumbered ids` and `vacated ids` are both DELETED, and this entry stops being a live mechanism.** Everything above repairs a renumber. The owner's ruling the same day is that a renumber should not happen: *"rework the decision system so that branches claim decision numbers only at merge time"*. A branch now writes a SLUG and `scripts/claim-ids.py` allocates the number inside `make merge`. D140 carries the design, the vocabulary and what it cost.

**The reason it could be retired rather than kept as a backstop.** Both rows guard a path that no longer exists: a branch that never takes a number never vacates one. Keeping them was argued and declined — a row that fires only when somebody works around the convention is a row nobody has read in a year, which is D16's own account of what an unread check is worth. What replaces them is `id claims`, whose load-bearing clause is that **main carries no slug**: that one is checkable, is checked on main after every merge, and cannot be satisfied by accident.

**The convention *renumber your own, never another's* is retired with them.** It was a rule about who loses a race, and the race no longer runs.

**What stays is everything above this heading, and it stays because it is evidence.** The thirteen renumber events, the D67/D69 corruption in `docs/map.py` — 24 wrong and 9 right in one file — and the three `CLAUDE.md` citations that silently named main's inventory decision are what the new design is answerable to. `docs/GATES.md`'s rule applies here as it does to a measurement: what happened is not edited to match a later tree.

**Measured while the replacement was built, which is the strongest thing this entry can say for it**: `origin/main` took two decision numbers and two build steps during the session that wrote the claimer. The allocator, reading main, moved its answer accordingly. Under the old convention that session would have guessed at the start and been wrong by the end — and would have found out at the merge, which is where all thirteen were found.

---
