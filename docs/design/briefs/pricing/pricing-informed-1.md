Designer kind: informed
Blind designers: 1
Designer: pricing-informed-1

## Screen
Pricing (route `#/pricing`, `app/src/Pricing.tsx`; run `make orient ARGS=app/src/Pricing.tsx`). Read docs/specs/pricing-suggest.md and docs/specs/stale-listings.md, docs/debts DEBT89, DEBT90, DEBT91, and the existing pricing mockups in docs/design/ (pricing-owed, pricing-send-notices, pricing-suggest).
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: pricing-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. About 9 status lines (send bar, five tallies, movers, two 'no read has run' lines, markup, value line, 'readings not matched') come before row 1 of 1,110.
2. The page is ~122,000px tall at 820 and the send bar jumps (DEBT89-91).
3. '64 copies ready' here, '18 ready' on Home, '18 SKUs, 92 Live Copies' on the send button: one count, three units.

## Cover
the header and send bar, the row list with its filters, one row's detail and price history, holding back an item, the send review and its receipt, and the empty and done states.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/pricing-informed-1.html and docs/design/pricing-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/pricing-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
