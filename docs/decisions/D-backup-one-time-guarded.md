## D-backup-one-time-guarded — The photo backup runs once, and never overwrites a good copy

Kind: process
Home: scripts/backup-daily.py

**The owner ruled it** (waiting-page items 60 and 60's follow-up). The backup to the iCloud Drive
folder `Banchi backup` runs when the owner asks, through `make backup`. No nightly job is installed:
`make backup-agent` stays in the Commands block and is not run.

**A later bad copy never replaces an earlier good one.** A photo already in the backup is never
overwritten; a difference is counted and the run ends `failed`. Each store copy is dated and kept,
and is checked with `PRAGMA integrity_check` before it lands. A `--verify` pass compares each file's
SHA-256, source against backup. The photo-storage lane builds these three in
`scripts/backup-daily.py`, with DEBT67 (capture photographs exist in one place) rewritten to match.

**Reopen** if the owner wants a schedule again, or a second copy off iCloud.
