# Compliance scorecard

Rewritten in place on each run by compliance-check.

| Group | Score | Gold standard | Gap | Source |
| --- | --- | --- | --- | --- |
| Outcomes | in shape | in shape | supersede and restates probes read 10 files each, no hit; CLAUDE.md is 172 lines; docs-audit rule enforcement row: 15 hard rules, 10 name a mechanism, 5 argue why none can | make docs-audit |
| Outcomes: supersede | pass | in shape | in shape, 10 files | compliance_probes.py supersede . |
| Outcomes: restates | pass | in shape | in shape, 10 files | compliance_probes.py restates . |
| Outcomes: local rule checks | pass | in shape | each local rule has a check or a NOT MECHANIZED line | make docs-audit, rule enforcement |
| Roles | in shape | in shape | test branches exist (test/*, sales-stock-*-tests, banchi-retire-map-py-tests*); the model-raise file is gitignored and unreadable here | GitHub list_branches; git check-ignore -v .claude/settings.local.json |
| Roles: stale model raise | unknown | in shape | .claude/settings.local.json is untracked and absent in this worktree | git check-ignore -v .claude/settings.local.json |
| Roles: test-first order | partial | in shape | read from branch names only, commit order not walked | GitHub list_branches |
| Parallelism | in shape | in shape | .claude/worktrees/ ignored, worktrees in use, lanecap probe reads 1 brief or plan file and finds no cap | .gitignore; compliance_probes.py lanecap . |
| Shared trees | in shape | in shape | 0 stashes, live hooks equal the clone's, Playwright reuse has globalSetup checkoutIdentity.ts and vite strictPort is true | git stash list; compliance_probes.py hooks; app/playwright.config.ts; app/vite.config.ts |
| Git | in shape | in shape | main moves by PR, protection holds all-jobs-passed and equals stamp requiredChecks; silent-undo history is unknown | GitHub list_pull_requests closed, 20 listed, base main each; gh api branches/main/protection; .github/stamp.json |
| Git: silent undo history | unknown | in shape | the history is shallow; fetch with depth 0 | check_silent_undo.py --repo . --history |
| Git: record slugs | pass | in shape | no added slug over 32 characters; 149 old long slugs on main, one note | compliance_probes.py slugs . |
| Git: remote branch pile | partial | in shape | at least 300 remote branches, most outside archive/, merged state not checked | GitHub list_branches, 3 pages |
| Verification | partial | in shape | CI shape not run here, screens have no shared screenshot config, one sleep loop waits on a clock edge | compliance_probes.py design .; git grep -n sleep |
| Verification: ci shape | unknown | in shape | ci-hygiene skill not run in this audit; defer to it | .github/workflows/ |
| Verification: playwright apt | pass | in shape | no apt step | compliance_probes.py playwright . |
| Verification: screens at every size and theme | partial | in shape | app/playwright.config.ts design-check exists, but no shoot config yet (to be added by lane add-shoot-config), so the shared shoot cannot run | compliance_probes.py design . |
| Verification: sleep waiters | partial | in shape | harness/tests/t7/cli_identify.py loops on a clock edge with time.sleep(0.005); identify/batch.py and identify/sweep.py poll an outside job; the rest are bounded retries and test waits | git grep -n sleep |
| Verification: docs and map checks | pass | in shape | make docs-audit exit 0 with 87 ok rows and 4 asks, none red; make map-check pass | make docs-audit; make map-check |
| Tokens | n/a | in shape | session practice | probes.md |
| Building | in shape | in shape | find_copies.py reports no copies; docs/plans holds only README.md; 306 test or spec files | find_copies.py . --parent; git ls-files |
| Building: module has a test | unknown | in shape | one test per product module was not walked | git ls-files '*test*' |
| Speak plainly | unknown | in shape | id-gloss greps match thousands of lines in 488 md files and need a read by hand; CLAUDE.md glosses its ids by convention | grep -rnE over *.md |
| Output | partial | in shape | 7 STE errors in 7 md files, 98 warnings, 488 md files read; UI copy is a known gap, 84 UI files get no STE check | ste_lint.py --fail-on error --quiet; compliance_probes.py design . |
| Output: docs/decisions/D239-four-stored-data-identity-checks.md, one line | finding | in shape | gap - STE011, a phrase longer than it needs to be (ste_lint.py) | none cited |
| Output: docs/map/app-tests.md, one line | finding | in shape | gap - STE013, a negative of a negative (ste_lint.py) | none cited |
| Output: docs/specs/batch-script.md, one line | finding | in shape | gap - STE013, a negative of a negative (ste_lint.py) | none cited |
| Output: docs/specs/motion-trigger.md, one line | finding | in shape | gap - STE013, a negative of a negative (ste_lint.py) | none cited |
| Output: docs/specs/multi-game.md, two lines | finding | in shape | gap - STE013, a negative of a negative, twice (ste_lint.py) | none cited |
| Output: docs/specs/undo.md, one line | finding | in shape | gap - STE013, a negative of a negative (ste_lint.py) | none cited |
| Reports | parent-covered | in shape | hooks in shape and guard.log has verdict lines in the last 7 days | compliance_probes.py hooks; guard_log_report.py --days 7 |
| Style | n/a | in shape | session practice | probes.md |
| Layout | unknown | in shape | folder shape and core kinds read clean, waiting copy not readable locally because the roadmap record branch is not fetched here | compliance_probes.py layout . |
| Layout: stray folders | pass | in shape | no folder outside the layout or its extras | compliance_probes.py layout . |
| Layout: core kinds | pass | in shape | none missing | compliance_probes.py layout . |
| Layout: waiting copy | unknown | in shape | no local roadmap ref; a GitHub read shows waiting/ on origin roadmap with answers, groups, items, meta, page | compliance_probes.py layout .; GitHub get_file_contents waiting |
| Design | out | in shape | no shoot config (to be added by lane add-shoot-config), 84 UI files | compliance_probes.py design . |
| Design: screens named | gap | in shape | no shoot config (to be added by lane add-shoot-config) | compliance_probes.py design . |
| Design: sizes named | gap | in shape | no shoot config (to be added by lane add-shoot-config) | compliance_probes.py design . |
| Design: themes named | gap | in shape | no shoot config (to be added by lane add-shoot-config) | compliance_probes.py design . |
| Design: screenshot command | partial | in shape | own command, not the shared shoot: scripts/screenshot.mjs; scripts/screenshot.sh; Makefile target screenshot | compliance_probes.py design . |
| Design: token file | pass | in shape | app/src/tokens.css | compliance_probes.py design . |
| Copies | in shape | in shape | no copies of claude-settings things | find_copies.py . --parent |
| iOS | n/a | in shape | no iOS app | compliance_probes.py ios . |
| Words | in shape | in shape | glossary read at e443aea of claude-settings | compliance_probes.py words . |
| Supersede | in shape | in shape | 10 file(s) read | compliance_probes.py supersede . |
| STE lint on UI files | partial | in shape | UI text the lint does not read: known gap, no UI linter | lint/ui_suffixes.py |

## Notes

- Caution: listing - level public; 1 rule restricts a secret, in .claude/rules/server.md ("A secret stays on the server"), blocks no login (layout.py caution .)
