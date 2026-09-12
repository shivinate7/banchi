## D16 — The docs are checked mechanically; the prose is checked by asking

**Every path, target, threshold and id in the markdown is checked by a script; the prose itself is checked by a model, and only the first may block a commit.** This repo's markdown carries its architecture and the reasoning behind it, and until `scripts/docs-audit.py` existed nothing verified a single line of it. Every path, `make` target, subcommand, test id, threshold, decision number and env var in it was true only for as long as someone remembered. That is the same argument `docs/GATES.md` makes for the harness — without it, *looks done* is the only available signal — applied to the files that tell the next session what done means.

### Three layers, split by how knowable each finding is

1. **Mechanical** — `scripts/docs-audit.py`, stdlib-only, run by the pre-commit hook and by `make docs-audit`. Every check is deterministic, and **blocking is the default**: a finding is mechanical when a reference is provably wrong — a path that does not resolve, a `make` target that does not exist, a threshold that disagrees with `docs/GATES.md` — and it exits 1, because there is no judgment to defer.

   **A finding prints on exit 2 instead of blocking when judging it needs context the script cannot have.** A decision id cited in a `.py` comment could plausibly become a variable name one day; code that changed beside an unchanged doc is a question, not a defect. A false positive that blocks is worse than one that prints.

   **Neither the roster nor its count is restated here.** `make docs-audit` names every check it runs, each row marked blocking or advisory, and that output is the register. This paragraph used to publish the count, and keeping one restated number honest cost more machinery than any other check in the file — all of it guarding a fact nothing downstream consumed. Deleting the claim deleted the need. D18 records the general rule.

   **A check is named, never numbered** — the same rule D17 sets for the repo-map check, enforced for all of them. Positions moved once already; the report's labels are the names.

   **And a decision id names one entry, which nothing asserted until 2026-08-30.** `docs/DECISIONS.md` carried THREE entries numbered `## D50` at once — the feedback states, the Cmd-arrow nav and the photo URL — written by three sessions that each took the next free number against the same base and all merged. Every row of this audit was green the whole time.

   **The reason is the shape of the reader, not an oversight in the roster.** `decision_headings` returned a SET, so three headings collapsed to one element: the published count was of DISTINCT ids and read 51 over a file holding 53, and the citation scan is satisfied by a heading EXISTING rather than by exactly one existing. A reader that collapses its input cannot report on what it collapsed, so the list is now the primitive and the set is derived from it.

   **What a duplicate costs is worse than an untidy file, which is why this blocks.** `governed_by` in `docs/map.py`, D17's decision-context hook and every `(D50)` in a comment all resolve an id to an ENTRY, and with three candidates they resolve to whichever is found first — a citation that is wrong in no way anything can see, because it points at a real heading, just not the intended one. Two headings carrying one id is provably wrong however the file got that way, which is this entry's own test for mechanical.

   **The three were renumbered by POSITION IN THE FILE rather than by who landed first**, so `docs/DECISIONS.md` stays ascending and no entry's 200-line block had to move: the first keeps D50, and the others became D51, D52 and D53. That also left the most-cited of them untouched, which is the smaller half of the reason and the one that made the change reviewable.

2. **Coupling** — the same script, `--staged`: code changed under `pipeline/`, and `docs/specs/batch-script.md` did not. **Exit 2 prints and allows.** Fires only above 20 staged lines, so a typo fix stays quiet.
3. **Semantic** — `/docs-audit`, a model reading prose against the diff. Never a gate: it costs money, it is not reproducible, and this project does not let a non-deterministic thing decide whether work is done.

**Why the coupling question does not block.** Stopping a commit over a question teaches you to reach for `git commit --no-verify`, and `--no-verify` also switches off the three opsec rules in the same hook. Trading a code-card bearer-instrument guard for a prose reminder is a bad trade, so layer 2 asks and gets out of the way.

Worth being exact about what `--no-verify` costs, because it is more than it was: those three rules run **only** at commit time now. Their `PreToolUse` twin, `scripts/guard-opsec.sh`, has been disabled in `.claude/settings.json` since 2026-08-03 — it blocked any write containing a code-shaped literal, including placeholders in prose about the format, and cost two blocked writes in one session. Fixtures stay covered while it is off by the `permissions.deny` rules; the code-card literal does not. **Revisited and re-enabled 2026-08-23**, when D24's build made the condition true: the narrowed pattern blocks by shape (stands alone, mixes letters and digits, no all-repeated group), passes byte-exact reconstructions of both historical false positives, and fails open on its own bugs — so `--no-verify` no longer switches off the only opsec layer, and the commit-time rules are again the backstop rather than the whole guard.

### A git worktree inside the tree is another branch, and the audit does not walk one

Added 2026-08-29. Concurrent sessions check worktrees out under `.claude/worktrees/<name>/`, which is a full source tree of a DIFFERENT branch sitting inside this one. The walk found them, so the audit was checking one branch's prose against another branch's code and reporting the disagreement as a defect in yours. Observed: a worktree's `CLAUDE.md` documented a `worktree-setup` target, real on its own branch, and the make-targets check failed a commit on `main`, which has no such target. **Two branches are allowed to disagree; that is what a branch is.**

**It is pruned twice, by name and by asking git, and the two cover different things.** `worktrees` in `SKIP_DIRS` catches the convention and keeps working when git does not answer. `nested_worktrees()` reads `git worktree list --porcelain` and prunes any checkout under the repo root whatever it is called — verified against a worktree named `zz-scratch-wt`, which no name rule could guess: zero files walked, audit clean. It fails open exactly as `ignored_paths` does, because a discovery helper that can abort the audit is worse than one that occasionally walks too much.

**This is not the gitignore filter and neither subsumes the other.** That filter stops a finding being *reported* for local state; this stops a foreign tree being *enumerated*. The finding here was against the make-targets check, which never consults the filter. `--self-test` covers the staged path; the on-disk path needs a real repository with a real worktree in it and was verified by hand, which that case says in as many words rather than implying coverage it does not have.

### Nothing on the audit path can write

The script opens, compares, prints, and sets an exit code; it parses with `ast` rather than importing, so it does not even run project code. Its only writes are inside `--self-test`, into a temporary directory it creates and destroys.

**`--self-test` therefore runs in `make check` and never in the git hook** (settled 2026-08-24). It is the one mode of this script that writes, and D18 forbids a writing thing on the path that decides whether a commit proceeds; `make check` is invoked by a person on demand, so it is not that path. Until then nothing ran it at all, and it had gone red without anyone noticing — a stale fixture in `tested_by reach` had stopped being false while every commit stayed green. `docs/DEBTS.md` carries the account. The residual gap is named there too: `make check` is not automatic either, so a red self-test still surfaces only when somebody asks.

Adding a `--fix` flag is a change to this entry, not a configuration knob. The reason is the failure this entry exists to prevent:

> **A blocked commit is reported, not resolved.** Never edit a doc for the sole purpose of getting a commit through.

An agent that can edit the docs to satisfy its own gate will do exactly that, and each edit will look reasonable. The docs stop being a record of what was decided and become a record of what was convenient — and unlike a failing test, nothing downstream ever notices. That is also why `/docs-audit` shows every proposed change in one table before touching anything, and never stages or commits: the owner's own `git diff` is the last link in the chain.

**The docs audit is not a harness test, and must not become one.** Putting it in `harness/run.py:TESTS` was considered and rejected. The harness runs behind the `Stop` hook (`scripts/stop-gate.sh`), so a docs test there would fire at the end of every turn, including turns that touched no markdown at all. The trigger is commit-time and on-demand by choice.

This paragraph used to make that point by naming the number the docs test would have taken, which stopped working the moment a real test needed a number. T7 is now the store, server and command-seam test (`docs/GATES.md`), and it is unrelated to this entry. The rule here was never about a number.

**The allowlist is self-cleaning.** `scripts/docs-audit-allow.txt` records things the docs name before they exist — `PKMNSCAN_IMAGE_MIRROR` was documented by build-order step 9. The audit **fails when an entry comes true**, which forces the line out at that moment. Same instinct as `stop-gate.sh` arming on the absence of `NOT_IMPLEMENTED` markers rather than on a toggle: a list that only grows becomes a list nobody has read since.

**A threshold is published, not restated.** Each test's `PASS_CRITERIA` must appear word for word as the `- **Pass**:` line of its `### Tn` section, and layer 1 blocks a commit where they disagree. **Reconciliation runs from the test to the gate.** The test is where a threshold is argued about and changed; `docs/GATES.md` is where it is announced. Rewriting a test so a doc-checker goes quiet inverts that and makes the test worse to please a tool.

Five of six had drifted before this was enforced, which is the case that decided the direction: those tests were changed deliberately and approved, and the change simply never reached the markdown. An approved change that does not reach the doc is the failure this whole entry exists to stop, so it blocks rather than asking.

**One known gap, recorded so a green report is not misread.** Layer 1 proves references resolve and thresholds agree — not that a paragraph is true. Treat a clean mechanical run exactly as `docs/GATES.md` treats a green T1 and T6: it means the checkable part checks out.

**Amended 2026-09-05, on the owner's ruling: a new row is a HARD FACT or it is not a row.** No new check may be ADVISORY, and none may decide on a heuristic. The reason is what an ADVISORY row costs rather than what it catches: it prints on every run, it blocks nothing, and a question nobody must answer becomes a question nobody reads — which is how `entry budget`, `game coverage` and `views exposure` came to be the ordinary state of exit 2 rather than a signal. A row that cannot be made provable is recorded in `docs/DEBTS.md` and left unbuilt, which is a smaller lie than a row that fires forever. **This does not retire the ADVISORY severity** — the rows that have it keep it, and layer 3 is still a person reading prose — it governs what gets added.

**Its first application found the thing it was made for.** Both legs of the threshold check above were *substring* tests against the whole section, so lowering T1's `holdout_accuracy >= 0.95` to `>= 0.9` — the number deciding whether it is safe to spend on a batch — left both rows printing `ok`, because `0.9` occurs inside `0.95`. Comparing by EQUALITY against the lifted claim is what closed it. **And "the `- **Pass**:` line" above is one of two forms**: seven sections publish that bullet and two publish an inline `**Pass: ...**`, so the lifter takes both and the doc did not have to change to be checked properly.
