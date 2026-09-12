## D143 — The claim reads the checked-out tree, so which tree that is must be established before anything reads it

**Ruled 2026-09-11, the same evening D140 landed and a few hours after it.** `make merge ARGS="270 --confirm"` was run from the primary checkout while it was standing on `main`. The claim half read `main`, found no slug in it, printed `no unclaimed id on this branch — nothing to claim`, and merged pull request #270's slug onto main verbatim. Pull request #270's slug sat on `main` as a heading until #273 repaired it with the claimer itself — six files, no hand edits. The slug is deliberately not spelled here: it is a number now, and a spelled one would be a citation of an entry that no longer exists under that name.

**The guard that should have stopped it existed, and was seven lines too late.** D140's own prose says the claim half refuses when the checkout is not standing on the pull request's own head branch. It does — but `if not pending: return 0` sat ABOVE `if here != branch`, so the precondition was unreachable on exactly the path that reaches main: a tree with nothing to claim returns before it is ever asked which tree it is. **"The guard does not exist" and "the guard is seven lines too late" are different defects and get fixed differently, and only the second one is what happened.**

### Every reader here asks its question of the checked-out tree

**That is not a flaw in the readers; it is what they are for.** `claims_pending` reads the working tree because the slug it must substitute is in the working tree. `stale_claim` reads it for the same reason, and standalone `make claim-stale` is CORRECT reading it — there, the tree you are in is the tree you are asking about.

**What neither reader can do is tell whether that tree is the pull request's**, and neither should learn: only `merge-pr.py` knows the head branch, and teaching `claim-ids.py` to care would give it a second job and a reason to grow a `gh` dependency D140 spent a paragraph refusing. **So the precondition belongs where the pointing happens**, and it is one hoist rather than a check in each reader.

### It had to move above the STALENESS read, not merely above the pending check

**The pending check is what let the slug through, and stopping there would leave a second, quieter defect.** A run standing on a branch that itself holds a stale number, merging a DIFFERENT pull request, would refuse with a sentence that is true about the tree it is in and names a pull request it is not merging — sending the reader to the wrong branch to fix the wrong thing. The tree is established first, so every refusal below it is about the right tree by construction.

### What it repairs in the entry above it, which is the part nobody would have looked for

**D140's staleness half was blind in exactly the same way, and fixing the claim alone would have made that worse rather than better.** `stale_claim` reads the checked-out tree, so from `main` it computes what `main` adds over its own merge base — nothing — and reports `every id this branch adds is still free` while the branch's stale number sits untouched. Measured on a throwaway repository before this was written: standing on the branch, exit 3 and a refusal; standing on `main`, exit 0 and clean, with the stale number unmerged in both runs.

**And the same reader had to learn what a merge in progress means.** Mid-merge the working tree already holds the other side's entries while the merge base has NOT moved, so every id that merge brought in reads as this branch's own and every one is on the ref by definition. The advice would be to un-claim an id belonging to somebody else's merged work. **The routine that produces it is the documented pre-merge step** — fetch, merge `origin/main`, resolve, push — and `make claim-stale` is in `make check`, so it is common rather than exotic: this entry's own branch hit it while resolving against D142, one refusal naming an id main had merged an hour earlier. A tree mid-merge is ALLOWED and says so, on the same reasoning as a missing ref: a question that cannot be asked is not a failure.

**A green row asserting something nobody checked is worse than the silence it replaced**, and that is what patching the claim half alone would have shipped. One hoist fixes both, because both readers sit below it.

### Proved from the wrong tree, which is why it was invisible

**Every existing test stood in the right place.** The claim half had no driver at all before this — `main()` reaches it only through `pr_state()`, which is `gh` — so nothing exercised a precondition that looked tested because its prose described it.

**It is drivable with no network**: `claim_half`'s `if not confirm: return 0` sits above its first `gh` call, so `scripts/claim-selftest.py` imports `scripts/merge-pr.py` and calls it in preview against a throwaway repository. Eight arms, and the one that matters reproduces the evening's failure exactly — a slug on the pull request's branch, nothing pending in `main`, the run made from `main`. **Restoring the original ordering turns five of them red.** Five mutations, none survived, including the partial hoist that stops above the pending check but below the staleness read.

### The same question, wrong in the auditor, found by trying to write this entry

**`docs-audit.py`'s `on_main()` said YES about a branch, and its own docstring denied that could happen.** It answers "is this checkout main" three ways, and the third is commit equality — written for a CI runner's DETACHED head, where there is no branch name to read. But **a branch cut from main and not yet committed to sits AT `origin/main`**, so equality called it main.

**The effect is that D140's workflow was unusable on a fresh branch.** `id claims` is gated on `on_main()`, so writing a slug and committing it — the first commit, the one that introduces the slug — was refused with `main carries 1 unclaimed id`, a sentence that is false and whose repair instruction points at main. This entry's own branch hit it, which is how it was found.

**Commit equality is now the detached-head rule and nothing else**: a NAMED branch is not main however recently it was cut, and `--abbrev-ref` prints the literal `HEAD` when detached, so that is the test.

**The deciding logic is pure now, and that is the finding rather than the fix.** It was welded to `git`, so asking it anything required a repository in three states, so nothing ever asked — and it was wrong for as long as that was true. `is_main` takes the four readings as arguments and `--self-test` drives seven cases over it with no repository at all. Two mutations, both caught; restoring the original rule turns the named-branch case red.

### What it does not decide

**Not that the dirty-tree check moves with it.** That one guards the WRITE — the claim commits everything it rewrites — and it is still where it was, below the readers, because a tree can be legitimately dirty while a preview answers a question about it. **Not that `make claim-stale` gains a tree argument**: it is a standalone check about the tree you are standing in and is right as it is. **And not D140's refusal of the network**: nothing here reads a pull request, and the head branch it compares against is a string `make merge` already had in hand.
