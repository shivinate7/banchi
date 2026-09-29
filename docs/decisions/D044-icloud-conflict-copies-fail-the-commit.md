## D44 — iCloud conflict copies fail the commit

**iCloud resolves a same-file race by writing a second file beside the original with ` 2` appended to the stem (`pre-push 2`).** Three guards stay, graded by how sure a machine can be. The hazard is a property of a directory, so they stay although the repo left iCloud.

- **`make hooks` installs only what `git ls-files` returns.** A hook directory decided by what lies on disk has given up the reviewability that is the reason hooks are tracked.
- **The pre-commit hook refuses a staged conflict copy.** Such copies are untracked until something runs `git add -A`, which an agent session does. A committed `foo 2.py` is a module no import reaches. `PKMNSCAN_DUPES=off` is the bypass.
- **`make icloud-sweep` deletes only a copy byte-identical to its original** and reports every differing one untouched. Differing may be the newer of two real edits, and guessing there is the one way a cleanup tool destroys work. It is in neither `make check` nor the hook (D18: it is the only target that can delete a file). `make status` reports the count.

An in-place overwrite on iCloud can serve Python's import machinery stale bytes while `read()` returns the new ones. A same-directory stage plus `os.replace` swaps the inode and cannot be served stale, and `scripts/status.py`'s helper keeps the mode too.
