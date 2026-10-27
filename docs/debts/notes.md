# Debt notes

One line per finding that is not yet a debt. A note becomes a debt after a real incident.

- `card_attribute_typos` (`harness/tests/t7/store_core.py`) skips the inline tuple of card field names in `capture_server`'s `claims`.
- It scans only the receivers `card`, `existing` and `x["card"]`.
- It scans only `store/master.py` and `server/capture_server.py`.
- `prose-guard.py`'s `check_structure` message says `decision-context.py` drops a `## D` entry. It no longer does; only the message is stale.
- No self-test pins that a `## D<n>` decision title is refused. The `decision structure` row catches it on the live corpus only.
- An entry ends only at the next entry title, so a non-entry heading at the foot of a decision file folds into that entry (`prose-guard.py`'s `entries`, `decision-context.py`'s `decision_gists`). No file has one.
- The records page gists: 33 open a bold run they never close, and about 45 lead with who ruled, not what (D260, D263, D273, D277, D289, D307). D138's gist is vague.
