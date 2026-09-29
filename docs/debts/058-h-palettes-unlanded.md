## DEBT58 — the Lane H palette record is on a branch, not in main

**Symptom.** The Lane H record lives only on branch `ux/h-record` at e7c8358a. Main does not
hold it. It is eight dark palettes, 32 JPEG screenshots under a `design-refs` folder,
the palette CSS, a contact sheet and the method (49 files).

**Cause.** The old pre-commit hook refused every staged image, so the record never merged.
Since 2026-09-27 the hook QR-scans every staged image instead ("EVERY STAGED IMAGE GETS THE QR
SCAN"), so landing should now be possible.

**Measured, 2026-09-28.** Cherry-picked onto origin/main 291b1e88 and committed with the armed
hook, no bypass: the hook passed on all 32 images. Added 5,960,480 bytes (about 5.7 MiB) in 49
files. `make docs-audit` `repo map` and `raw color` rows passed. One prose row failed
(`identifier spelling`, a British spelling in the notes file), fixed by rewriting the word. Full
`make ci-check` on the landed tree: unmeasured.

**Why not fixed.** The owner chose to land it later. The measured commit is kept only as a
local branch in one worktree and is not pushed.

**Fix.** Cherry-pick 029c7dfe and e7c8358a onto main, use the American spelling of that word in
the notes file, commit through the hook, run `make ci-check`. Delete
this entry in the same change.
