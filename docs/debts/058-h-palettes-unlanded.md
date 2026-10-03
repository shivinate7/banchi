## DEBT58 — the Lane H palette record is on a branch, not in main

The Lane H record (eight dark palettes, 32 JPEG screenshots in a `design-refs` folder, the palette CSS, a contact sheet and the method: 49 files, about 5.7 MiB) lives only on `ux/h-record` on origin (e7c8358a). The old pre-commit hook refused every staged image, and it now QR-scans each one instead. Landing was measured on a cherry-pick over a then-current main: the hook passed all 32 images with no bypass, `repo map` and `raw color` passed, and one prose row (`identifier spelling`, a British spelling in the notes file) failed and was fixed. A full `make ci-check` on the landed tree is unmeasured.

**Outcome at risk.** The record is lost if the branch is deleted.

**Closes when.** The owner lands it: cherry-pick 029c7dfe and e7c8358a onto main, use the American spelling in the notes file, commit through the hook, run `make ci-check`, and delete this entry in the same change.

Two of the eight palettes, Abyssal Bloom and Carnival Midway, have landed as themes in `app/src/tokens.css` (`THEMES` in `app/src/deviceMemory.ts`). Their CSS files in the record are now redundant; the other six, the screenshots and the method are still only on the branch.
