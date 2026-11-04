# App setup

The app's build, dev-server and test-runner setup.

## Code files

- `app/checkoutIdentity.ts` — A reused dev server must name this checkout.
- `app/demoSplit.ts` — The demo build's split of the recorded responses (DEBT84): a Vite plugin loaded only when `VITE_DEMO=1`, writing `demo-data/` beside the app, one file per small route family or per large response, and an index of key to file.
- `app/design-check-reporter.ts` — THE VERDICT, AS ONE SMALL FILE.
- `app/devPort.ts` — The ONE dev port for this checkout, imported by both vite.config.ts and playwright.config.ts so they cannot disagree.
- `app/eslint.config.js` — The two v1-bug rules docs/decisions/'s table has named as guards since it was written and never had: no facingMode (bug `3`), no split(",") CSV parsing (bug `2`).
- `app/index.html` — The single page: the root element that `main.tsx` mounts into, the Banchi title, the SVG favicon and a link to `src/fonts.css`, where the three Banchi faces come from this checkout.
- `app/playwright.config.ts` — How `make design-check` runs the spec, including the Vite it starts for itself. reuseExistingServer stays ON, and `globalSetup` (checkoutIdentity.ts) refuses the run unless the server names this checkout.
- `app/playwright.unit.config.ts` — The unit tier: the same runner as playwright.config.ts with no browser, no dev server and no globalSetup, over `tests/unit/*.unit.ts`.
- `app/vite.config.ts` — The dev server, strictPort — a busy port fails loudly rather than serving on `5174`, where CLAUDE.md, the Makefile and scripts/views.txt would all three be wrong.
