## 6 — T7 leaves two capture-server facts unchecked

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two devices. Twenty-way is what found `request_queue_size` at its default of 5 (8 served, 12 reset by the OS). The `accept backlog` row of `make docs-audit` (`scripts/docs_audit/code_invariants.py`) pins `request_queue_size = 128` as text. No leg opens 20 connections.
- **The bare-interpreter start.** `make server` runs `$(PYTHON)`. T7 imports the module under the interpreter that runs the harness, so it cannot see a dependency added outside the standard library.

**Outcome at risk.** The capture server resets captures under a burst, or fails to start, with `make harness` green.

**Closes when.** An on-demand T7 leg opens twenty connections against the accept backlog, and one starts the server under a bare interpreter.
