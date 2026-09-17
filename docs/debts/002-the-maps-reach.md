## 2 — The map's reach

**Unblocked and small. Cluster 1's `governed_by` row belongs here too; it is filed there
because it shares that cluster's decision.**

### The orphan rule cannot see an extensionless file, and those are the three enforcement seams

`scripts/docs-audit.py:scan_plan` rejects any `source_suffixes` member not starting with a
dot, so no declaration can reach a filename without an extension. Recorded 2026-08-13 as a
thought experiment — *"creating a second extensionless hook beside it — a `pre-push`, say —
left the row reading `ok repo map` at exit 0."*

**D42 then committed that exact file.** `scripts/githooks/pre-push` and
`scripts/githooks/reference-transaction` arrived 2026-08-29 and the rule was silent for both;
they are in `docs/map.py` by hand and nothing would have failed had the author forgotten. The
same commit added `scripts/githooks-selftest.sh` one directory up, which carries a declared
suffix and duly **failed the commit** until it was described. **One commit, both outcomes: the
rule's coverage is decided by whether a filename happens to have a dot in it.**

**What it now protects is what moves the priority.** The unscanned directory held one file
when this was written. ~~It holds three — `pre-commit`, `pre-push`, `reference-transaction`~~ —
**it holds five.** `post-merge` and `post-checkout` arrived afterwards with the `make hooks`
staleness reminder, and neither was written into `docs/map.py`. So the sentence below —
*"a fourth sibling's arrival is not [caught]"* — was not a prediction. It was already a
description of what had happened, and it happened twice more before anyone counted.

**That half is closed as of 2026-09-05.** `scripts/docs-audit.py:check_hook_roster` compares
the directory against the `scripts/` entry's `modules` in both directions and blocks.

**A SECOND, WORSE HOLE IN THE SAME DIRECTORY WAS FOUND WHILE CLOSING THE FIRST.** `make hooks`
COPIES these files into `.git/hooks-armed`, and nothing kept the copy in step — so the armed
`pre-commit` sat **four days** behind a merged sigil check (D92) and every commit in this
clone skipped it while reporting clean. Worse than an unlisted hook, because the reminder that
was supposed to catch it already existed: `post-merge` and `post-checkout` print one, and it
fires only on pull or branch switch and scrolls away. `pre-commit` now compares its own armed
copy against **main** before any other rule, and **`PKMNSCAN_HOOKS=off`** is its bypass.

**Why main and not the working tree**, since the tree is the obvious comparison: a branch
legitimately editing a hook differs from its armed copy by definition, so a tree comparison
fires constantly, and the one command that silences it — `make hooks` — installs that branch's
UNMERGED hooks as the gate for every worktree in the clone. That is a worse outcome than the
staleness. So it blocks only where the armed copy is behind main *and* this tree matches main,
which is precisely where the fix it prints is safe. It is
deliberately NOT the widening this section proposes below: the suffix rule is doing real work
everywhere else — it is what keeps `views.txt` and a stray `README` from being conscripted into
demanding entries — and repealing it repo-wide to repair one directory is the larger change.
One directory's roster against one directory's entries.

**What is still open here is the general rule, not the hooks.** A sixth enforcement seam
somewhere else with no extension is still invisible, and `check_hook_roster` will not see it,
because it looks in exactly one place.

**The fix exists a few hundred lines away.** `code_haystack()` reaches that same file by
handing `_walk` the whole filename as a suffix. Not done because it changes what
`source_suffixes` means; `docs/map.py` records the hole at the `scripts/` entry.

### An entry proves a file is described, never that the description is true

165 hand-written lines. A `does` describing the wrong file passes exactly as well, and there
is no equivalent fix — an import is in a parse or it is not, a sentence about what a file does
is neither. Two specifics: **a stale cross-reference in prose is invisible to every row** (the
two orphan-rule entries each described the other's coverage, written in one run by different
hands, and nothing would ever have told either); and **`.json` is deliberately outside `app/`'s
suffixes**, since including it would conscript `app/package-lock.json` — so `app/package.json`,
holding the npm scripts `make lint`, `make typecheck` and `make design-check` all run through,
has no entry.

---
