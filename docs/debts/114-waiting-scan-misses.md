## DEBT114 — the waiting-page scan misses some address and credential shapes

**What.** The shared waiting-page export (claude-settings skill `waiting-page`, `export_page.py`) scans each value before it writes the copy to this public repo's record branch. Each shape below passes it, measured one item per run (`changed 1`, not `refused`). Banchi's old scan let each of them through too.

- **Addresses.** Lower-case "123 main street" and "12 elm st", and a CSV city line, "Austin,TX,78701".
- **Credential names.** A name that ends in no trigger word, such as "TCG_PASS=abcd1234efgh" and "SESSION=abcd1234efgh", and a colon value with no digit, such as "secret: abcdefghijkl".
- **Owner.** shivinate7.
- **Outcome at risk.** A buyer's address or a credential pasted into a waiting-page item reaches a public commit. The page writer's read of the diff before each commit (D327, the waiting page is a committed record) is the cover until then.
- **Closes when.** The shared scan refuses each shape above, each with a red test case in claude-settings, and stays green on prose such as "3 records in place" and "join key:". The fix is a claude-settings lane, never a banchi-side scan.
