Designer kind: informed
Blind designers: 1
Designer: inventory-informed-1

## Screen
Inventory (route `#/inventory`, `app/src/Inventory.tsx`, CardPane, CopiesPanel, CopyMapView; run `make orient ARGS=app/src/Inventory.tsx`). Read docs/specs/box-map.md, docs/specs/holdings-roster.md, docs/specs/master-set.md, docs/specs/card-detail.md, and docs/design/inventory-*.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: inventory-*.png, inventory-shelf-*.png, inventory-sets-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Sell, retire and move are bare icons on each copy.
2. The box list scrolls inside a 4-row box.
3. The photo is a zoomed slice with the card's name cut off.

## Cover
search, the result list, the card pane with its copies, the map of boxes with the card lit, sell/retire/move with undo, and set progress.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/inventory-informed-1.html and docs/design/inventory-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/inventory-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
