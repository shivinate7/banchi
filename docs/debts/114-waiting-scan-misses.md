## DEBT114 — the waiting-page scan misses address and credential-name shapes

**What.** The shared waiting-page export (claude-settings skill `waiting-page`, `export_page.py`) scans each value before it writes the copy to this public repo's record branch. Each shape below passes it, measured one item per run (`changed 1`, not `refused`):

- **Addresses.** "Ship to 123 Main Street", "PO BOX 1234" and "AUSTIN, TX 78701". Banchi's old scan refused only the street address; its PO box and city patterns were case-sensitive.
- **Credential names.** "Set TCG_TRACKING_KEY=k9Qx7vLm2Npw4Rt8", "API_SECRET=abcdefgh12345678", "SESSION_TOKEN=abcdefgh12345678" and "SESSION_COOKIE=abcdefgh12345678". A name ending in key, secret, token or cookie, set to 8 or more characters, has no known token shape. The colon forms pass too: "X-API-Key: abcdef1234567890", "secret: abcd1234efgh" and "token: abcd1234efgh". "password=hunter22secret" is refused. Banchi's old scan refused all seven.
- **Bare cookies and auth values.** "cf_clearance=c3c3c3c3c3c3c3c3", "sessionid=abcdef0123456789abcd" and "Bearer abcdefghijklmnopqrstuvwx" and "Basic abcdefghijklmnopqrst". The shared scan refuses a `Cookie:` header and `connect.sid` only. Banchi's old scan refused all four.
- **Owner.** shivinate7.
- **Outcome at risk.** A buyer's address or a credential pasted into a waiting-page item reaches a public commit. The page writer's read of the diff before each commit (D327, the waiting page is a committed record) is the cover until then.
- **Closes when.** The shared scan refuses each shape above, each with a red test case in claude-settings, and stays green on prose such as "3 records in place" and "join key:". The fix is a claude-settings lane, never a banchi-side scan.
