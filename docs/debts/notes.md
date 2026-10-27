# Debt notes

One line per finding that is not yet a debt. A note becomes a debt after a real incident.

- `card_attribute_typos` (`harness/tests/t7/store_core.py`) skips the inline tuple of card field names in `capture_server`'s `claims`.
- It scans only the receivers `card`, `existing` and `x["card"]`.
- It scans only `store/master.py` and `server/capture_server.py`.
