## DEBT-send-file-outside-lock — a send writes its import file outside the store lock

**A send plans and writes its import file, then takes the store lock to stamp. A copy that sells or is retired in that gap is skipped by the stamp, but its row is already in the file.** The send prints a loud line naming the file and the copy. It cannot un-write the row.

- **Window:** from the send's second `store.read` to its `store.write`. It holds pricing, the file build and the prints, all on local disk.
- **Result:** the file can hold a copy the store did not send. If the person uploads it as is, TCGplayer lists a copy that is no longer here. D59 (a send never counts a copy it did not send) and D26 (sold and retired are terminal) hold in the store, and not in the file.
- **Not fixed because** the complete fix is to write the file inside the store lock. That holds the lock through pricing and disk writes, which blocks every other writer. The window is short, and the loud line names the row to drop.
- **Closes when** the file is written inside the lock, or the plan and the write move to one transaction.
- **Points to** D59, D26 and the `ahead` list in `cli/cmd_emit.py`'s `_stamp_single` and `_stamp_merged`.

**Outcome at risk.** A listing goes live for a copy that has sold. The buyer's order cannot be filled.
