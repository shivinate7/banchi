## DEBT67 — capture photographs exist in one place

**Gap.** A capture photograph cannot be regenerated: the card is back in a box. Losing the disk leaves the realign (D36) nothing to bind to and the re-shoot (D26) nothing to compare against. Back up `inventory/` and `captures/` with Time Machine to the NAS, or a scheduled `rsync`. An `rsync` needs a line in `make status` saying when it last ran and whether it worked.

**Not a fix.** Do not move the live store or photographs onto the NAS. `fcntl.flock` and `os.replace` do not hold over SMB, and the join hashes every photograph in a box, which is slow over wifi.
