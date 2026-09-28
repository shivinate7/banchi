# Memory migration, 2026-09-27

Auto memory for this repo goes off once this lane merges. The owner's ruling: "Migrate first,
then off." This file judges all 71 live entries in the session memory index for this repo.
That index lives under the user's home Claude projects directory. It excludes the index's own
`archive/` folder, already judged covered. Each entry gets one verdict: COVERED, DEBT, RECORD,
GLOBAL or STALE, plus a home.

## The table

| # | Entry | Verdict | Home |
|---|---|---|---|
| 1 | Gate B capture cadence | COVERED | D121 cites the 0.6095s/card figure directly |
| 2 | Score a trace before believing it | COVERED | `docs/specs/motion-trigger.md`: read `scripts/score-trace.py` before a threshold change |
| 3 | Fulfiller is downstream | COVERED | D031, quotes the owner's ruling verbatim |
| 4 | git push HTTP 400 | DEBT | `PENDING-DEBTS.md` §A |
| 5 | D-number collisions | STALE | Superseded by D140 / `scripts/claim-ids.py`. Its docstring says this exact collision "cannot happen" now |
| 6 | envfile secret trap | COVERED | `envfile.py`: `load(path: Path \| None = None, ...)` and `FROM_FILE_ENV` are both already the fix this entry asked for |
| 7 | UX first | RECORD | `CLAUDE.md`, Working agreement (added this pass) |
| 8 | GUI work shows in their foreground | GLOBAL | Proposed sentence G1 below |
| 9 | Design sweeps need real pixels | COVERED | `docs/specs/logo.md` §9, same finding, same wording ("flattered itself by a factor of two") |
| 10 | Browser pane paints only the fold | DEBT | `PENDING-DEBTS.md` §B |
| 11 | Workflow worktrees leak when dirty | DEBT | `PENDING-DEBTS.md` §A (gh --author, never-leave-main) and §B (worktree leak) |
| 12 | Dry-run blocklists fail open | DEBT | `PENDING-DEBTS.md` §C.12 |
| 13 | Demo photos are real, QR-cleared | COVERED | `docs/specs/demo.md` §3, §9 |
| 14 | Hover deltas need the transition to settle | COVERED | D50, `app/tests/cursor.spec.ts`, CLAUDE.md design-system section — the entry's own text points here |
| 15 | Verify where the gate runs | COVERED | Global rule `verification-green-proves-only-its-fixtures` |
| 16 | Demo dry-run on a branch | RECORD | `docs/specs/demo.md` §11a (added this pass) |
| 17 | Bump to the floor, not the latest | COVERED | `.github/workflows/demo.yml`'s `deploy` step comment, plus global rule `verification-bump-first-fix-version`, plus closed PR #202 |
| 18 | Banchi home hero | COVERED | D121. Shipped as a "ribbon and rug," not the memory's mid-session "lollipop" — verified against D121's own text |
| 19 | A guard must see its subject | DEBT | `PENDING-DEBTS.md` §C (the whole catalogue) |
| 20 | Press stability floor | COVERED | D118, `app/tests/cursor.spec.ts`, `app/tests/inventory.spec.ts` |
| 21 | Message the session, not the PR | DEBT | `PENDING-DEBTS.md` §B |
| 22 | CI design-check flakes 1-in-462 | COVERED | `docs/debts/008-recorded-and-correctly-unfixed.md`, section "The runner's one-test red..." |
| 23 | Cadence trigger D130 | COVERED | D130, D131 |
| 24 | Merges can revert settled work | COVERED | `recorded deletions` `docs-audit` row, D119 amendment |
| 25 | Worktree node_modules go stale | COVERED | D257 |
| 26 | CI shards + fake clock | COVERED | D136 |
| 27 | gh api -f turns GET into POST | DEBT | `PENDING-DEBTS.md` §A |
| 28 | Scroll-offset sweep triage | DEBT | `PENDING-DEBTS.md` §C.7 |
| 29 | Click-then-mutate fixture race | COVERED | `docs/debts/023-a-sale-fixture-that-moves-after-the-press-is-only-wrong.md` |
| 30 | Read the fulfilled body, not the timeline | DEBT | `PENDING-DEBTS.md` §C.8 |
| 31 | PW_ARGS word-splitting fakes a pass | DEBT | `PENDING-DEBTS.md`. `verification-cost.md` already claimed this was filed; it was not, until this pass |
| 32 | preview_start serves the launch dir | DEBT | `PENDING-DEBTS.md` §B |
| 33 | _copies_out is a full-table pass | DEBT | `PENDING-DEBTS.md` §E |
| 34 | reap-selftest red on main | DEBT | `PENDING-DEBTS.md` §C.13. Status not re-verified this session |
| 35 | A clean tree is not a loss | DEBT | `PENDING-DEBTS.md` §B |
| 36 | A fixture and a machine-wide resource | DEBT | `PENDING-DEBTS.md` §C.5 |
| 37 | Banchi store value shape | COVERED | D159, same figures (2,245 cards, $2,531.64, 390 unpriced) |
| 38 | Doc citations spelled three ways | COVERED | D149, same finding, same numbers (16 total, the working pattern) |
| 39 | reap's bare sweep read argv only | COVERED | D169 |
| 40 | Order freeze on #/inventory (filename's own draft number, later renumbered) | COVERED | D181 |
| 41 | Row retention has three causes | DEBT | `PENDING-DEBTS.md` §C.10 |
| 42 | resolve4.py breaks on rewrites | DEBT | `PENDING-DEBTS.md` §A |
| 43 | Motion traces have no surround | COVERED | `docs/specs/motion-trigger.md`, the 38x28 grid and ARM-TIME surround discussion |
| 44 | Batch PRs into one integration PR | DEBT | `PENDING-DEBTS.md` §A. Superseded in part by #70 (COVERED), but its three named traps have no home yet |
| 45 | Code claims had no reader | DEBT | Shipped half COVERED (PR #379, live in `scripts/docs-audit.py`). Leftover items in `PENDING-DEBTS.md` §D |
| 46 | Mutation corpus, not prose | COVERED | `make mutate-guards` / `make mutate-anchors` exist and run, confirmed in the Makefile |
| 47 | Code mechanization: four open items | DEBT | `PENDING-DEBTS.md` §D |
| 48 | Guards must read their subject | COVERED | This repo's own fix: `scripts/guard-shell.py:_stash_entries`, confirmed present. The parent-repo defect is out of scope — see Input Needed |
| 49 | Bytes are not tokens | DEBT | `PENDING-DEBTS.md` §B |
| 50 | Verification cost, measured | COVERED | `docs/specs/verification-cost.md` |
| 51 | Merge covers a needed rebase | COVERED | `CLAUDE.md`'s `make merge` bullet, same ruling, same date |
| 52 | Spec-map saving is small | RECORD | `docs/specs/verification-cost.md` §12 (added this pass) |
| 53 | Comply, do not re-implement the overruled position | GLOBAL | Proposed sentence G2 below |
| 54 | holder_of defect was already fixed | GLOBAL | Proposed sentence G3 below (shared with #56) |
| 55 | CI red was the inventory flicker | COVERED | Global rules `verification-trust-guard-after-red` and `verification-cry-wolf-guard-is-spent`; the product defect is already fixed |
| 56 | A comment about wiring is not the wiring | GLOBAL | Proposed sentence G3 below (shared with #54) |
| 57 | Archive sweep preview is silent | COVERED | D224, same finding, same fix (preview touches no socket; `--write` commits as it goes) |
| 58 | STE mechanization 2026-09-19 | COVERED | D284; `scripts/ste/ste_lint.py` is vendored; `ENTRY_BUDGET` lives in `scripts/docs-audit.py` |
| 59 | Janitor reaps hand-made worktrees | DEBT | `PENDING-DEBTS.md` §B |
| 60 | Parent split_segments comment blind spot | COVERED | This repo's own fix: `scripts/shell_parse.py`. The parent-repo defect is out of scope — see Input Needed |
| 61 | Sidebar review rounds 2026-09-20 | COVERED | `docs/reviews/ux-2026-09-20/*` — FOLLOW-UPS.md, orders.md, inventory.md and the rest |
| 62 | STE hook blocks whole-file edits | DEBT | `PENDING-DEBTS.md` §B |
| 63 | A probe can score itself | DEBT | `PENDING-DEBTS.md` §C.6 |
| 64 | Grade the prose, do not obey it | COVERED | Global "Outcomes first" section already states this. Optional nuance in G4 below |
| 65 | settings.local.json rewritten in-session | DEBT | `PENDING-DEBTS.md` §B |
| 66 | Resumed agent's worktree vanishes | DEBT | `PENDING-DEBTS.md` §B |
| 67 | Opus only where needed | RECORD | `CLAUDE.md`, Working agreement (added this pass) |
| 68 | Commit definitive records | COVERED | Global rule `building-memory-never-only-home` — the rule this whole migration executes |
| 69 | Push every pass | RECORD | `CLAUDE.md`, Working agreement (added this pass) |
| 70 | Integration merge check cadence | COVERED | `docs/reviews/ux-2026-09-23/PLAN-PR4-PR5.md`, cited by the entry itself |
| 71 | Handoff 2026-09-27: PR 4B | COVERED | `docs/reviews/ux-2026-09-23/PLAN-PR4-PR5.md`, cited by the entry itself |

## Counts

COVERED 35. DEBT 26. RECORD 5. GLOBAL 4 (3 distinct sentences). STALE 1. Total 71.

## GLOBAL proposals, for the owner to approve into `~/Developer/claude-settings/CLAUDE.md`

Each names the entry it comes from. None of these got written to that file. That file lives
outside the repo.

**G1** (from #8, GUI work shows in their foreground): "Before any action that puts pixels on
the user's own screen, say in one line that a window is about to appear. Say that it is
yours. A browser launch, `screencapture` and computer use all count. Prefer a headless or
isolated route over the user's own real window or browser profile."

**G2** (from #53, comply / do not re-implement): "When the user overrules a position, do the
literal thing they asked for. Read the actual diff before you describe it. Never cite the
user's own word as authorization for a variant they did not name."

**G3** (from #54 and #56, a claim about wiring or a fix is a claim, not a fact): "Treat a
file's or a document's own claim about a defect, a fix, or a run schedule as a claim. Verify
it against the current code or config. Never repeat it as fact until you have checked it."

**G4** (from #64, optional — the core lesson is already the global "Outcomes first" section):
"When the user questions why a mechanism runs, answer about whether its premise still holds.
Do not answer about what the mechanism costs."

## Notes found in passing, not part of the verdict table

- `docs/specs/verification-cost.md` §6B already claims that "`docs/debts/` records the same
  failure in `dry-run-blocklists-fail-open` and in the PW_ARGS word-splitting trap." Neither
  was actually in `docs/debts/` before this pass. Both are now drafted in
  `PENDING-DEBTS.md` §C. Once numbered and filed, that citation becomes true.
- Entries #48 and #60 each name a real defect in the PARENT repo,
  `~/Developer/claude-settings/hooks/guard.py`. One is a stash clause matching a subcommand
  name over an empty stack. The other is a `split_segments` function. It reads an apostrophe
  inside a `#` comment as opening a quote. Neither has a home in this repo, because neither
  is about this repo. Flagged under Input Needed instead of filed anywhere here.
