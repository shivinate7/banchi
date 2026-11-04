## DEBT114 — the waiting-page export scan misses some address and key shapes

**What.** `scripts/waiting-export.py`'s `PATTERNS` let some buyer-address and secret shapes through to the public `docs/waiting/`. Found by review round 3 of the lane that built it, with inline probes.

- **All-caps PO box and city line.** "PO BOX 1234" and "AUSTIN, TX 78701", the USPS form a shipping file carries, pass. So do lower-case "123 main street" and "12 elm st". The `street address` pattern is case-sensitive so that "3 records in place" and "5 cards in this lane" pass; that also made its PO box and city branches case-sensitive. A scoped `(?i:...)` on those two branches restores them.
- **Street suffixes.** Terrace, Way, Cir, Pkwy and Hwy pass, as do "McDonald Dr", "St. Charles Ave", names of 4 or more words, and a CSV city line (`Austin,TX,78701`).
- **Key values.** A quoted JSON name (`"TCG_TRACKING_KEY": "<value>"`) passes. So do names that end in no trigger word (`TCG_PASS=`, `SESSION=`), a `:` value with no digit, and a `=` value that starts with `$`.
- **Owner.** shivinate7.
- **Outcome at risk.** A buyer's address or a credential pasted into a waiting-page item reaches a public commit. The page writer's read of the diff before each commit (D327, the waiting page is a committed record) is the cover until then.
- **Closes when.** Each shape above has a red self-test case and stops the export, and the self-test's idiom cases stay green.
