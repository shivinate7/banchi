## DEBT-dock-icon-drop-shadow-untried — the Mac dock icon has no drop shadow, and none was tried

**Gap.** Safari, Mail and Calculator carry a drop shadow out to 87.5% of the canvas. The Banchi icon carries none, so it sits slightly flatter on the dock's shelf. `docs/specs/logo.md` section 17 leaves the shadow out on purpose, because a shadow is a drawing decision and section 3 locks the drawing.

**Cost.** A small visual mismatch beside the system icons in one surface, the installed web app's dock icon.

**Why unfixed.** The value must come from a sweep, and not from typing a number into the generator. The sweep has not run.

**What would close it.** A sheet that shows candidate shadows at 128, 64 and 32px beside the same three system icons, judged by the method in section 7 of the spec. Then a decision on whether `build-mark.mjs` draws the shadow into the manifest icons.
