## DEBT114 — the waiting-page scan misses address shapes

**What.** The shared waiting-page export (claude-settings skill `waiting-page`, `export_page.py`) scans each value before it writes the copy to this public repo's record branch. It has no address shapes. Measured: items holding "Ship to 123 Main Street", "PO BOX 1234" and "AUSTIN, TX 78701" printed `changed 3`, not `refused`.

- **Owner.** shivinate7.
- **Outcome at risk.** A buyer's address pasted into a waiting-page item reaches a public commit. The page writer's read of the diff before each commit (D327, the waiting page is a committed record) is the cover until then.
- **Closes when.** The shared scan refuses a street address, a PO box and a USPS city line, each with a red test case in claude-settings, and stays green on prose such as "3 records in place". The fix is a claude-settings lane, never a banchi-side scan.
