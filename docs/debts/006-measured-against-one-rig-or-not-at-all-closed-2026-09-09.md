## 6 — ~~Measured against one rig, or not at all~~ — CLOSED 2026-09-09, on the owner's word

**The provenance argument is retired.** The owner ruled, 2026-09-27, that a closed entry's
own record belongs in git, not in this file forever (the preamble's own rule: "an entry
leaves when someone argues it should"). The argument the owner closed on 2026-09-09, and the
59-frame eye-pass question it left open, are both kept in full at commit b61ffa32.

**This section cannot leave whole, and that is why it stays a section rather than a git-only
record.** `make docs-audit`'s `detector standing` row reads five figures straight out of its
prose, against `harness/results/detect.json`. Deleting the section once already made that row
fail over a claim nobody removed on purpose. So the five figures stay published here, and
only the argument around them is retired.

`detect_card` has been run over 1,625 photographs in the owner's six boxes. It returned
a box for every one and refused none, and the crop guard declined 59 —
`harness/results/detect.json`. The same run, over the same 1,625 photographs across six boxes,
is the one `detector standing` reads twice on purpose. A stale twin cannot pass unnoticed
that way. And the 59 frames nobody has looked at are still named by box and filename in the
score file.

**The declines are entirely boxes 3 and 4** (42 of 723, and 17 of 56).

### What T7 leaves uncovered in `server/`

**Untouched by the closure above — this was never about the rig, and stays open.**

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 — 8
  served, 12 reset by the OS. Re-running it every turn buys nothing the smaller case does
  not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which is
  what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the module
  under whichever interpreter runs the harness, so it cannot see this.

Both cost more at every turn end than they can return.
