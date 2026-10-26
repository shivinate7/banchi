## DEBT-send-file-outside-lock — a send writes its import file outside the store lock

**A send plans and writes its import file, then takes the store lock to stamp. A copy that sells or is retired in that gap is skipped by the stamp, but its row is already in the file.** A send never counts a copy it did not send, so the store never counts that copy sent (D26 (retired is a terminal card state); D59 (live count is per SKU)).

- **Window:** from the send's second `store.read` to its `store.write`. It holds pricing, the file build and the prints, all on local disk.
- **Screen send:** it refuses. `send_routes._write_and_send` reads the `send_ahead` line from `emit` and fails the press with `send_file_ahead` (409). Nothing is pushed or offered as a download. The copies the store did stamp go back on the list. No person step is left.
- **Command line:** `banchi emit` still leaves the file written. It prints a WARNING that names the folder the file is in and the copies, and the person must not upload that file as is.
- **Runs-sheet Emit step:** a remaining door. `RunPanel`'s `doStep('emit')` calls the per-run emit route with no `--send-dir`. A file that is ahead of the store is served from the run folder, and the warning shows only in the log well, so the person may upload it.
- **Not fixed because** the complete fix is to write the file inside the store lock. That holds the lock through pricing and disk writes, which blocks every other writer. The window is short, and the refused press costs one more press.
- **Closes when** the file is written inside the lock, or the plan and the write move to one transaction.
- **Points to** D26 (retired is a terminal card state), D59 (live count is per SKU), D273 and the `ahead` list in `cli/cmd_emit.py`'s `_stamp_single` and `_stamp_merged`.

**Outcome at risk.** A person who runs `banchi emit` by hand uploads the file anyway, and a listing goes live for a copy that has sold. The screen send cannot do this.
