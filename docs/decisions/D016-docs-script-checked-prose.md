## D16 — Docs checked by script, prose by review

**Every path, target, threshold and id in the markdown is checked by a script. The prose itself is checked by a model, and only the first may block a commit.** Repo markdown carries the architecture and the reasoning behind it. Before `scripts/docs-audit.py` existed, nothing verified a line of it. Every path, `make` target, subcommand, test id, threshold, decision number and env var was true only while someone remembered it. `docs/GATES.md` makes the same argument for the harness. Without a check, *looks done* is the only signal. This entry applies the same rule to the files that tell the next session what done means.

### Three layers, split by how knowable each finding is

1. **Mechanical.** `scripts/docs-audit.py`, stdlib-only, runs in the pre-commit hook and in `make docs-audit`. Every check is deterministic, and **blocking is the default**. A finding is mechanical when a reference is provably wrong. Examples: a path that does not resolve, a `make` target that does not exist, a threshold that disagrees with `docs/GATES.md`. It exits 1, because there is no judgment to defer.

   **A finding prints on exit 2 instead of blocking when judging it needs context the script cannot have.** A decision id cited in a `.py` comment could become a variable name one day. Code that changed beside an unchanged doc is a question, not a defect. A false positive that blocks is worse than one that prints.

   **The roster is not restated here.** `make docs-audit` names every check, and marks each blocking or advisory. That output is the register. A restated count cost more machinery to keep honest than any other check. So the claim was deleted. D18 records the general rule.

   **A check is named, never numbered.** D17 sets this rule for the repo-map check, and it now covers all checks. Positions move. The report's labels are the names.

   **A decision id names one entry.** The old single decisions file carried three entries numbered `## D50` at once. Three sessions had each taken the next free number against the same base. Every row stayed green. The cause was the reader's shape. `decision_headings` returned a set, so three headings collapsed to one. The citation scan passed when a heading existed, not when exactly one did. A reader that collapses its input cannot report what it collapsed. So the list is now the primitive, and the set is derived from it.

   **A duplicate id blocks.** `governed_by` in `docs/map.py`, D17's decision-context hook and every `(D50)` in a comment resolve an id to an entry. With three candidates, they resolve to whichever is found first. The citation is then wrong in a way nothing can see. It points at a real heading, just not the intended one. Two headings with one id is provably wrong, however the file got that way. That is this entry's own test for mechanical.

   **The three were renumbered by position in the file, not by who landed first.** The file stays ascending, and no entry's 200-line block moved. The first keeps D50. The others became D51, D183 and D138. The most-cited entry was left untouched, which kept the change reviewable.

2. **Coupling.** The same script, with `--staged`. It flags code changed under `pipeline/` when `docs/specs/batch-script.md` did not change. **Exit 2 prints and allows.** It fires only above 20 staged lines, so a typo fix stays quiet.
3. **Semantic.** `/docs-audit`, a model that reads prose against the diff. It is never a gate. It costs money, it is not reproducible, and this project does not let a non-deterministic thing decide whether work is done.

**Why the coupling question does not block.** A commit stopped over a question teaches the reach for `git commit --no-verify`. `--no-verify` also switches off the three opsec rules in the same hook. Trading a code-card bearer-instrument guard for a prose reminder is a bad trade. So layer 2 asks and gets out of the way.

What `--no-verify` costs is more than it was. Those three rules now run **only** at commit time. Their `PreToolUse` twin, `scripts/guard-opsec.sh`, was disabled in `.claude/settings.json`. It blocked any write holding a code-shaped literal, including placeholders in prose about the format. Fixtures stay covered through the `permissions.deny` rules. The code-card literal does not. **The owner ruled to re-enable it once D24's build made the condition true.** The narrowed pattern blocks by shape. It stands alone, mixes letters and digits, and has no all-repeated group. It passes byte-exact reconstructions of both historical false positives. It fails open on its own bugs. So `--no-verify` no longer switches off the only opsec layer. The commit-time rules are the backstop again, not the whole guard.

### A git worktree inside the tree is another branch, and the audit does not walk one

Concurrent sessions check worktrees out under `.claude/worktrees/<name>/`. Each is a full source tree of a different branch, inside this one. The walk found them. The audit then checked one branch's prose against another branch's code, and reported the disagreement as a defect in yours. A worktree's `CLAUDE.md` documented a `worktree-setup` target. That target was real on its branch. The make-targets check failed a commit on `main`, which has no such target. **Two branches are allowed to disagree. That is what a branch is.**

**It is pruned twice, by name and by asking git. The two cover different things.** `worktrees` in `SKIP_DIRS` catches the convention, and keeps working when git does not answer. `nested_worktrees()` reads `git worktree list --porcelain`. It prunes any checkout under the repo root, whatever it is called. It was verified against a worktree named `zz-scratch-wt`, which no name rule could guess: zero files walked, audit clean. It fails open, as `ignored_paths` does. A discovery helper that can abort the audit is worse than one that occasionally walks too much.

**This is not the gitignore filter, and neither subsumes the other.** That filter stops a finding being *reported* for local state. This stops a foreign tree being *enumerated*. The finding here was against the make-targets check, which never consults the filter. `--self-test` covers the staged path. The on-disk path needs a real repository with a real worktree. It was verified by hand, and that case says so, rather than implying coverage it does not have.

### The auditor is a package, and `scripts/docs-audit.py` is its entry point

`scripts/docs-audit.py` keeps the docstring, `build_parser` and `main`. The rows live in `scripts/docs_audit/`, one module per group. `--self-test` lives in the `selftest_*` modules there, one `run` per span of cases, called in the order the single function ran them. **`ROWS` in `docs_audit/rows.py` is the one table of rows: name, tier, check, arguments.** The tier is a field, so a row cannot be untiered. `check dispatch` reads the table. A check that any module defines, and that no `ROWS` entry names, fails the commit. A name that two modules share lives in `core`, so imports run one way.

**The reason was the file's shape. The fact behind it is the edit rate.** One file held every row, its fixtures and the wiring. Changes to unrelated rows conflicted by construction. The split was scoped on a count of 90 commits to it in 7 days. Recount with `git log --since=7.days -- scripts/docs-audit.py scripts/docs_audit/`. **Trigger to split again:** one module still takes most of those commits.

**Four things a split file can hide, each with its reader:**
- **`commit path` reads the package the entry imports.** The entry alone closes over three functions, so a write in any row would pass as "nothing writes". The self-test plants a write in a package module and expects the row red.
- **`audit-self-test`'s roster entry in `scripts/guard-scope.py` names the package.** A branch that touches only `scripts/docs_audit/` still runs the self-test.
- **`scripts/audit-history.py` copies the package beside the entry** into each old tree. The entry cannot run without it.
- **Each module holds an imported copy of a shared name.** `ROOT` moves with `set_root`. The self-test patches names through `module_globals()`, which writes every copy. A caller that assigns `ROOT` on the entry script moves nothing.

### Nothing on the audit path can write

The script opens, compares, prints, and sets an exit code. It parses with `ast` rather than importing, so it does not run project code. Its only writes are inside `--self-test`, into a temporary directory it creates and destroys.

**`--self-test` runs in `make check`, never in the git hook.** It is the one mode of this script that writes. D18 forbids a writing thing on the path that decides whether a commit proceeds. `make check` is run by a person on demand, so it is not that path. Before this split, nothing ran it at all. It had gone red unnoticed. A stale fixture in `tested_by reach` had stopped being false while every commit stayed green. The debts record carries the account. The residual gap: `make check` is not automatic either, so a red self-test surfaces only when somebody asks.

Adding a `--fix` flag is a change to this entry, not a configuration knob. The failure this entry exists to prevent is this:

> **A blocked commit is reported, not resolved.** Never edit a doc for the sole purpose of getting a commit through.

An agent that can edit the docs to satisfy its own gate will do exactly that. Each edit will look reasonable. The docs stop recording what was decided, and start recording what was convenient. Unlike a failing test, nothing downstream notices. That is also why `/docs-audit` shows every proposed change in one table before touching anything. It never stages or commits. The owner's own `git diff` is the last link in the chain.

**The docs audit is not a harness test, and must not become one.** Putting it in `harness/run.py:TESTS` was considered and rejected. The harness once ran behind a `Stop` hook. A docs test there would fire at the end of every turn, including turns that touched no markdown. The trigger is commit-time and on-demand, by choice. T7 is the store, server and command-seam test (`docs/GATES.md`). It is unrelated to this entry.

**The allowlist is self-cleaning.** `scripts/docs-audit-allow.txt` records things the docs name before they exist. `BANCHI_IMAGE_MIRROR` was documented by build-order step 9. The audit **fails when an entry comes true**, which forces the line out at that moment. A list that only grows becomes a list nobody has read.

**A threshold is published, not restated.** Each test's `PASS_CRITERIA` must appear word for word as the `- **Pass**:` line of its `### Tn` section. Layer 1 blocks a commit where they disagree. **Reconciliation runs from the test to the gate.** The test is where a threshold is argued about and changed. `docs/GATES.md` is where it is announced. Rewriting a test so a doc-checker goes quiet inverts that, and makes the test worse to please a tool.

Five of six had drifted before this was enforced. Those tests were changed deliberately and approved. The change never reached the markdown. An approved change that does not reach the doc is the failure this entry exists to stop. So it blocks rather than asking.

**One known gap.** Layer 1 proves references resolve and thresholds agree. It does not prove a paragraph is true. Treat a clean mechanical run as `docs/GATES.md` treats a green T1 and T6. The checkable part checks out.

**The owner ruled: a new row is a HARD FACT or it is not a row.** No new check may be ADVISORY, and none may decide on a heuristic. An ADVISORY row prints on every run and blocks nothing. A question nobody must answer becomes a question nobody reads. That is how `entry budget`, `game coverage` and `views exposure` became the ordinary state of exit 2. A row that cannot be made provable is recorded as a debt and left unbuilt. That is a smaller lie than a row that fires forever. **This does not retire the ADVISORY severity.** The rows that have it keep it, and layer 3 is still a person reading prose. The ruling governs what gets added.

**Its first application found the defect it was made for.** Both legs of the threshold check were *substring* tests against the whole section. Lowering T1's `holdout_accuracy >= 0.95` to `>= 0.9` left both rows printing `ok`, because `0.9` occurs inside `0.95`. Comparing by EQUALITY against the lifted claim closed it. **The `- **Pass**:` line above is one of two forms.** Seven sections publish that bullet, and two publish an inline `**Pass: ...**`. The lifter takes both, so the doc did not have to change to be checked properly.
