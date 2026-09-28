## D-every-image-is-scanned — Every staged image gets the QR scan, and a missing scanner refuses

The owner's ruling, 2026-09-27: every image gets the QR scan.

**The outcome this protects has never changed.** A live unredeemed code card is a bearer
instrument (D70, D24). Anyone who reads the image or the printed string owns the code.
`scripts/githooks/pre-commit` exists to stop one from ever reaching a tracked path. The QR
decode in `scripts/qr-clear-check.py` is the one thing that proves an image is clear of one.
Everything else in the hook is a proxy for that.

**The path list was the blunt part.** Before this change, the hook refused every staged
image outside `captures/` outright. It gave no inspection at all, unless the image sat in
one of three hand-typed exceptions: `demo-assets/photos/`, `demo-assets/extra/photos/`,
`demo-assets/mirror/photos/`. Only those three got re-decoded. A folder list can only ever
answer "was this meant to hold a photo." It cannot answer "does this photo carry a code." A
photograph landing anywhere the list did not anticipate was refused. That sounds safe, but
the refusal carried no inspection either. It was blocked on the accident of its path, never
proven clear or proven live. The list was also a ceiling nobody could safely raise. Widening
it by hand for a legitimate new photo location would have re-created the same blind spot one
folder wider. There was never a way to tell from outside whether a given image had gone
through the scanner. It might just as easily have landed somewhere the list refused it
before one was ever run.

**The fix removes the list rather than growing it.** Every staged image, in any folder, now
goes into `scripts/qr-clear-check.py`. `captures/` stays the one exemption, and for a reason
that has nothing to do with trust in its contents. It is gitignored (see the file header in
`scripts/githooks/pre-commit`). A file reaches it only through a forced `git add -f` against
the ignore rule, not through the ordinary staging every other path uses. Nothing else is
exempted by name. An image is refused on what the scan finds, never on where it sits.

**A scanner that cannot run now refuses the commit, where it used to warn and allow.** A
missing `python3`, or `zxing-cpp` failing to import, used to print a warning and let the
commit through unscanned. That is fail-open on the one day the rule matters. The one commit
where the scanner is broken gets treated as evidence nothing is wrong, when it is evidence
nothing was checked. `qr-clear-check.py` already exits 2 when the decoder is unavailable, or
an image cannot be opened (`qr.QrUnavailable`, or any decode exception). The hook itself was
the only piece softening that into a warning for the missing-interpreter case. It no longer
does. Unavailable is not the same as clear.

**What did not change.** The printed-code layout check (four hyphen-separated groups) stays
untouched. `PKMNSCAN_QR=off` still bypasses the whole block, loudly, exactly as before.
`captures/` stays exempt, for the reason stated above.

Proved by `make githooks-selftest`, extended rather than rewritten. A decodable QR in a
folder that was never an exception (`docs/`) is refused. A clean PNG in that same folder is
allowed. A QR image in `demo-assets/mirror/photos/` is still refused. A missing scanner
refuses rather than warns.
