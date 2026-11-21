Designer kind: informed
Blind designers: 1
Designer: orders-informed-1

## Screen
Orders (route `#/orders`, `app/src/Orders.tsx`, its walk pane OrdersWalkPane/OrderPickPane; run `make orient ARGS=app/src/Orders.tsx`). Read docs/specs/order-flow.md, docs/specs/order-walk-plan.md, docs/specs/order-pipeline.md, decision D288 (repeated actions are labeled icons), and docs/design/orders-ship-to.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: orders-*.png and orders-walk-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Sell is a bare $ glyph on each copy, its word only in a hover tooltip.
2. At 820 the rail is icons only.
3. 92 picks over 18 sections carry '3 short' and '(either)' pills nobody explains.

## Cover
the buyer list, the walk with its sections, one pick, selling a copy, a short card, an either-printing card, and the done state.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/orders-informed-1.html and docs/design/orders-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/orders-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
