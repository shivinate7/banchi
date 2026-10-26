## DEBT67 — capture photographs exist in one place

**Gap.** One copy exists. A nightly job (`make backup`, installed by `make backup-agent`) copies `photos/`, `captures/` and a SQLite snapshot of `inventory/store.sqlite` to the iCloud Drive folder `Banchi backup`. The second copy is still missing. A photograph cannot be re-shot: the card is back in a box. Losing the disk and iCloud together leaves the realign (D36) nothing to bind to and the re-shoot (D26) nothing to compare against. On the owner's Mac, `photos/` holds about 7.9 GB and `inventory/` about 757 MB. Time Machine has no destination.

**What the first copy does.** It copies as files, skips a file whose size and mtime match, and never deletes in the destination, so a sold card's photograph (D89) stays. It never reads the destination. A missing iCloud Drive folder is a failed run, and `make status` shows the last run.

**Second copy, on hold.** The Home Assistant box's 2 TB drive is the main suspect in that box's open data-corruption case (the home repo's `records/ha-green-freeze.md`). A drive health re-read on 2026-10-26 decides it. If cleared: `rsync -a --partial` over the SSH add-on already running, to `/media/banchi-backup/`, which Home Assistant's own backups skip. A nightly Mac launchd job, no `--delete`, and a weekly `rsync -c -n` check.

**Not a fix.** Do not move the live store or photographs onto a network share. `fcntl.flock` and `os.replace` do not hold over SMB, and the join hashes every photograph in a box, which is slow over wifi.
