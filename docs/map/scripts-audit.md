# Docs audit

The checks behind `make docs-audit`, one module for each row group, with each row's self-test.

## Code files

- `scripts/docs_audit/__init__.py` — Imports every module of the docs-audit package in dependency order and lists them in `MODULES`, which is what `scripts/docs-audit.py` copies onto its own namespace.
- `scripts/docs_audit/capability_homes.py` — The capability homes row: each named capability has one home, and a call to its primitives outside it is a finding, past an allow list that only shrinks.
- `scripts/docs_audit/code_invariants.py` — The rows that read an invariant out of code with `ast`: import layering, identity writers, claim decode and clients, server concurrency, estimate wire and column counts.
- `scripts/docs_audit/core.py` — The shared half of the audit: `Finding`, `Row` and `Report`, the staged-mode readers (`read`, `exists`, `glob_files`), `ROOT` and `set_root`, the module-globals mapping the self-test patches through, and the helpers two row modules both use.
- `scripts/docs_audit/design.py` — The design-token, raw-color, breakpoint and JS-breakpoint rows over `docs/DESIGN.md`, `tokens.css` and the stylesheets.
- `scripts/docs_audit/dispatch.py` — The row that reconciles every defined check with the ones `rows.audit` runs, the subject-count row and the coupling question.
- `scripts/docs_audit/env_map.py` — The rows over environment variables, hatches, the subagent override, the map data and map sections rows, the hook roster, Claude hooks and the build-order mirror.
- `scripts/docs_audit/games.py` — The rows over game and export vocabulary: the registry against the committed exports, coverage, the matrix superset and the join-key shape.
- `scripts/docs_audit/harness_criteria.py` — The rows that reconcile harness test counts, published pass criteria and their evidence with `harness/run.py` and `docs/GATES.md`.
- `scripts/docs_audit/hygiene.py` — The doc-hygiene, route-roster, recorded-deletion, spec-seal, design-check verdict and positional-reference rows.
- `scripts/docs_audit/paths_commands.py` — The rows that read paths, line anchors, `make` targets, the commands roster and `banchi` subcommands out of the markdown.
- `scripts/docs_audit/reasons.py` — The rows over reason codes and their neighbors: motion params, pricing presets, hint reasons, the transport promise and the export request.
- `scripts/docs_audit/records.py` — The rows over the decision, gate and debt records: decision ids, id claims, numbering growth, heading structure and the debts index.
- `scripts/docs_audit/registry_scopes.py` — The rows over the check registry, the commit path, the suite lock, the browser, spec, serve and guard scopes, and how callers invoke the audit.
- `scripts/docs_audit/rows.py` — `ROWS`, the mode filter and `audit()`: the one table that names every row with its tier, and the loop that runs it.
- `scripts/docs_audit/rules.py` — The rule-enforcement row over CLAUDE.md's hard rules and the identifier-spelling row.
- `scripts/docs_audit/screens.py` — The logo, storage-key, views-manifest and render rows over the front end's screens.
- `scripts/docs_audit/selftest.py` — The `--self-test` driver.
- `scripts/docs_audit/selftest_capability_homes.py` — Self-test cases for the capability homes row, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_code_invariants_1.py` — Self-test cases for the code invariants rows, part `1`, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_code_invariants_2.py` — Self-test cases for the code invariants rows, part `2`, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_code_invariants_3.py` — Self-test cases for the code invariants rows, part `3`, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_data.py` — Fixture lines the path-extractor self-test cases read.
- `scripts/docs_audit/selftest_design.py` — Self-test cases for the design rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_env_map.py` — Self-test cases for the env map rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_paths_commands_1.py` — Self-test cases for the paths commands rows, part `1`, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_paths_commands_2.py` — Self-test cases for the paths commands rows, part `2`, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_records.py` — Self-test cases for the records rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_registry_scopes.py` — Self-test cases for the registry scopes rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_sleeps.py` — Self-test cases for the fixed sleeps row, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_spelling.py` — Self-test cases for the spelling rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_stability.py` — Self-test cases for the stability rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_status_reach.py` — Self-test cases for the status reach rows, called by `selftest.self_test`.
- `scripts/docs_audit/selftest_strings.py` — Self-test cases for the strings rows, called by `selftest.self_test`.
- `scripts/docs_audit/sleeps.py` — The fixed sleeps row: a `waitForTimeout` in the browser specs carries a `keep:` reason or waits on a condition, past a per-file allow list that only shrinks.
- `scripts/docs_audit/spelling.py` — The American-spelling reader and the shell-substitution row.
- `scripts/docs_audit/stability.py` — The rows that read the causes of screen shake out of the source: the stable scrollbar gutter, the font preloads and metric fallbacks, transitions on layout properties and hover or focus rules that resize a box.
- `scripts/docs_audit/status_reach.py` — The closed-vocabulary, tested-by reach and status-source rows.
- `scripts/docs_audit/strings.py` — The rows over screen strings: mechanism words, the typed interpunct, the offender-list ratchet and views opsec.
