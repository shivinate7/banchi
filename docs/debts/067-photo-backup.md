## DEBT67 — capture photographs exist in one place

**Gap.** Nothing backs up the card photographs or the store. A photograph cannot be re-shot: the card is back in a box. Losing the disk leaves the realign (D36) nothing to bind to and the re-shoot (D26) nothing to compare against. On the owner's Mac, `photos/` holds about 7.9 GB and `inventory/` about 757 MB. Time Machine has no destination. iCloud syncs only Desktop and Documents, so it does not cover `~/Developer`.

**What a fix copies.** `photos/` and `captures/` as files. `inventory/store.sqlite` only as a snapshot taken with `sqlite3 .backup`, never the live file.

**Options, owner to choose.**
- First copy: Time Machine to a USB drive of 1 TB or more, or a cloud service from the Mac. A home server is a second copy only.
- Second copy, the Home Assistant box's 2 TB drive: not yet. It is the main suspect in that box's open data-corruption case (the home repo's `records/ha-green-freeze.md`). A drive health re-read on 2026-10-26 decides it. If cleared: `rsync -a --partial` over the SSH add-on already running, to `/media/banchi-backup/`, which Home Assistant's own backups skip. A nightly Mac launchd job, no `--delete`, and a weekly `rsync -c -n` check.
- A scheduled copy needs a line in `make status` saying when it last ran and whether it worked.

**Not a fix.** Do not move the live store or photographs onto a network share. `fcntl.flock` and `os.replace` do not hold over SMB, and the join hashes every photograph in a box, which is slow over wifi.
