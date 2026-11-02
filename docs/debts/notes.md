# Debt notes

One line per finding that is not yet a debt. A note becomes a debt after a real incident.

- `card_attribute_typos` (`harness/tests/t7/store_core.py`) skips the inline tuple of card field names in `capture_server`'s `claims`.
- It scans only the receivers `card`, `existing` and `x["card"]`.
- It scans only `store/master.py` and `server/capture_server.py`.
- `prose-guard.py`'s `check_structure` message says `decision-context.py` drops a `## D` entry. It no longer does; only the message is stale.
- No self-test pins that a `## D<n>` decision title is refused. The `decision structure` row catches it on the live corpus only.
- An entry ends only at the next entry title, so a non-entry heading at the foot of a decision file folds into that entry (`prose-guard.py`'s `entries`, `decision-context.py`'s `decision_gists`). No file has one.
- The records page gists: 33 open a bold run they never close, and about 45 lead with who ruled, not what (D260, D263, D273, D277, D289, D307). D138's gist is vague.
- `guard-shell.py`'s `_sanctioned_outside`: the side-session notes folder skips the `_repo_holding` check the temp folder has, so a checkout placed under it would take writes and `cd`.
- `guard-shell.py`'s `_resolve_target` resolves only the parent folder, so a file symlink inside a sanctioned folder that points into a checkout is written through (same on main for `~/.claude`).
- The one-list send (`server/send_routes.py`): with runs on disk and a corrupt `prices.json`, `pipeline_routes.do_pipeline_worklist` still draws default-policy suggestions and sets no `error`. The send then refuses `live_check_failed`, so no wrong price goes out.
- `readings_stale` has no cure for a SKU whose newest market reading came from an old run table, since the live export carries no market for it. Its named remedy cannot fix that case.
- The `readings_stale` sentence names bare SKU ids, where `suggestion_changed` and the held refusal name cards. `postings.SUGGESTED` and `suggest.SOURCE` are two constants for nearly one thing.
- `send_routes._refuse_stale_readings`'s docstring, and the docstring of the T7 case `check_send_with_run_refuses_stale_readings`, say `refresh_before_send` never touches a suggestion's reading. When the refresh runs, its live fetch rewrites those readings. Wording only.
- `send_routes._send`: the `nothing_to_send` branch re-parses the live CSV through `_names`. A file deleted mid-press turns the 409 into a 500.
- `send_routes._name_held`: a refusal carries `held` at `error.data.held`, a sent answer at top level. No client reads either yet. A held suggestion dropped from a press refused `under_cut_off` or `needs_price` is not named; nothing is sent then.
- The T7 contract's `Pass` line must equal `PASS_CRITERIA` in `harness/tests/t7_store_and_seams.py`, and that string runs 36 words. The line carries an `ste-disable-next-line STE001` comment. Shorten the string, then the line, and drop the comment.
- No row checks the `paths:` globs in `.claude/rules/`. A glob that matches no file stops its rule from loading, and nothing says so.
- `rules.folder_rule_roster_findings` has no self-test. Only the live `CLAUDE.md` exercises it.
- `make docs-audit` reads a symlinked `AGENTS.md` or `CLAUDE.md` as its own file, so one defect can be reported up to six times, once per path to the same text.
- `hygiene.check_agent_links` has no self-test. Only the live tree exercises its composed-file branch.
