## 17 — Four blocks still ask the viewport a question only their column can answer

**Named by `make docs-audit`'s `breakpoint columns` row on every run, ADVISORY, and left
standing on purpose (D123, 2026-09-07).** The rule the register states is: below 1024px a
`@media` width is honest, because the shell is force-railed there and a viewport question and a
column question differ by a constant. At or above 1024 they do not — every screen but the
Fulfiller's draws inside `.bn-shell-main`, which is the viewport minus 236px, or minus 64px when
the rail is collapsed, and **172px is wider than the gap between two ladder steps.**

Four blocks are over that line today:

| where | what it does | the two columns it cannot tell apart |
|---|---|---|
| `RunPanel.css:13` | splits the run list into master and detail | 788px / 960px |
| `RunPanel.css:55` | makes the master sticky, with a `100vh` max-height | 788px / 960px |
| `CaptureScreen.css:964` | lifts the eyebrow above the title, raises `--cap-head-h` | 1044px / 1216px |
| `CaptureScreen.css:972` | squeezes the two capture rails on a narrow desktop | 1044px / 1216px |

**Why it is ADVISORY rather than blocking, and this is the row's shape and not its confidence.**
Whether a `min-width` is asking the wrong thing depends on what the rule DOES. `RunPanel.css:55`
is half viewport question already — it sets `max-height: calc(100vh - ...)`, which no container
query can answer — and the capture screen is `min-height: 100dvh` with a viewfinder sized by
`container-type: size` against the window. A script can see the width and not the intent, so it
prints the question and lets the commit through. That is D16's line.

**What discharging one looks like**: a cap (`--bn-page-max`) or a `container-type: inline-size`
on an ancestor inside that screen, the way `Pricing.css` and `BoxBrowse.css` do — or a line under
COLUMN-BLIND in `docs/DESIGN.md` with the reason, which the row then checks is still true.

**The hazard that stops this being a five-minute change**, and the reason none of the four was
converted in the change that found them: `container-type: inline-size` computes to
`contain: layout style inline-size`, and `contain: layout` makes the element **a containing block
for its `position: fixed` descendants**. `.runs-detail` is already a container, so `.runs-body`
becoming one is probably safe; the capture screen was not audited for it. Verified casualties if
containment were applied naively higher up: `ReviewQueue.css:797`/`:819` (`.review-rail` as a
fixed sheet), `ReviewQueue.tsx:1705`/`:1900` (scrim and dialog), `BoxBrowse.css:649`
(`.browse-actionbar`). **Review and Inventory must never become containers.**

**Not a build-order step**, for §15's reason: there is no deliverable to schedule, and the row
already says the same thing on every run in a form a person can act on one sheet at a time.
