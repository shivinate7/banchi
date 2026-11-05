# App setup

The app's build, dev-server and test-runner setup.

## Code files

- `app/checkoutIdentity.ts` — A reused dev server must name this checkout.
  - Decisions: `D261`, `D43`
- `app/demoSplit.ts` — The demo build's split of the recorded responses (DEBT84): a Vite plugin loaded only when `VITE_DEMO=1`, writing `demo-data/` beside the app, one file per small route family or per large response, and an index of key to file.
  - Decisions: `D172`
- `app/design-check-reporter.ts` — THE VERDICT, AS ONE SMALL FILE.
  - Decisions: `D43`, `D16`
- `app/devPort.ts` — The ONE dev port for this checkout, imported by both vite.config.ts and playwright.config.ts so they cannot disagree.
  - Decisions: `D261`, `D43`, `D5`, `D13`
- `app/eslint.config.js` — The two v1-bug rules docs/decisions/'s table has named as guards since it was written and never had: no facingMode (bug `3`), no split(",") CSV parsing (bug `2`).
  - Decisions: `D27`, `D13`, `D16`, `D18`, `D271`, `D91`, `D132`, `D142`
- `app/index.html` — The single page: the root element that `main.tsx` mounts into, the Banchi title, the SVG favicon and a link to `src/fonts.css`, where the three Banchi faces come from this checkout.
  - Decisions: `D5`, `D13`, `D94`, `D124`
- `app/playwright.config.ts` — How `make design-check` runs the spec, including the Vite it starts for itself. reuseExistingServer stays ON, and `globalSetup` (checkoutIdentity.ts) refuses the run unless the server names this checkout.
  - Decisions: `D261`, `D16`, `D128`, `D5`
- `app/playwright.unit.config.ts` — The unit tier: the same runner as playwright.config.ts with no browser, no dev server and no globalSetup, over `tests/unit/*.unit.ts`.
  - Decisions: `D18`
- `app/vite.config.ts` — The dev server, strictPort — a busy port fails loudly rather than serving on `5174`, where CLAUDE.md, the Makefile and scripts/views.txt would all three be wrong.
  - Decisions: `D43`, `D13`, `D261`
