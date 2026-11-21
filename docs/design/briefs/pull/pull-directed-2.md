Designer kind: directed
Blind designers: 1
Designer: pull-directed-2
Direction: the route first: the physical walk along the boxes as a map, cards placed on it in walking order

## Screen
Cards to Pull: the Fulfiller's whole product (route `#/fulfillment`). Run `make orient ARGS=app/src/Fulfillment.tsx` to see which components draw it. Live demo: https://shivinate7.github.io/banchi/#/fulfillment (also #/orders and its walk). Screenshots already taken: /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/fulfillment-*.png, /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/orders-walk-*.png, /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/home-*.png. Read docs/specs/capture-app.md (its Fulfillment sections), docs/DESIGN.md (section Fulfillment and the `--bn-*` token block), docs/specs/order-walk-plan.md, and decision D5 (two personas). One section at a time.

## Pain points to fix, largest first (from an audit)
1. Every on-hand copy of a card shows with its own Pull, and the screen never says how many to pull; the Orders walk says "Pick 2 of 3" for the same card.
2. One card fills a 1440x900 screen, so Pull is below the fold; a pull is a very long scroll at 820. Nothing groups cards by buyer or envelope. "176 unlocated" is a warning the Fulfiller cannot act on.
3. Home, Orders, this screen and Pricing count the same open work in different units under different words.

## Cover
The list of cards to pull; one pull with its photo check; mark sold; a short or unlocated card; grouping by buyer envelope; the done state; an empty day.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only.

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/pull-directed-2.html and docs/design/pull-directed-2-notes.md, and print your designer kind and direction on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push your branch `design-mock/pull-directed-2`. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
