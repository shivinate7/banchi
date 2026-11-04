## DEBT114 — the waiting-page scan misses address and credential-name shapes

**What.** The shared waiting-page export (claude-settings skill `waiting-page`, `export_page.py`) scans each value before it writes the copy to this public repo's record branch. It replaced banchi's own scan, which refused both shapes below. Measured, each item alone in a fetched folder:

- **Addresses.** "Ship to 123 Main Street", "PO BOX 1234" and "AUSTIN, TX 78701" printed `changed 3`, not `refused`.
- **Credential names.** "Set TCG_TRACKING_KEY=k9Qx7vLm2Npw4Rt8", "API_SECRET=abcdefgh12345678" and "SESSION_TOKEN=abcdefgh12345678" each printed `changed 1`. A name ending in key, secret or token, set to 8 or more characters, has no known token shape, so it passes. "password=hunter22secret" is refused.
- **Owner.** shivinate7.
- **Outcome at risk.** A buyer's address or a credential pasted into a waiting-page item reaches a public commit. The page writer's read of the diff before each commit (D327, the waiting page is a committed record) is the cover until then.
- **Closes when.** The shared scan refuses each shape above, each with a red test case in claude-settings, and stays green on prose such as "3 records in place" and "join key:". The fix is a claude-settings lane, never a banchi-side scan.
