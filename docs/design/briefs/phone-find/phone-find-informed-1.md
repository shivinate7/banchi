Designer kind: informed
Blind designers: 1
Designer: phone-find-informed-1

## Screen
Inventory (`#/inventory`, CardPane, CopiesPanel, CopyMapView) moved to a native iPhone app. Read docs/specs/box-map.md, docs/specs/card-detail.md, docs/debts DEBT76 and DEBT77, docs/specs/lean-server.md section 7.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: inventory-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Sell, retire and move are bare icons.
2. The box list scrolls inside a 4-row box.
3. The photo crops the card's name.

## Cover
search, scan a card in hand, result, card with copies, map of boxes, sell/retire/move with undo, and Mac out of reach.

## Device
iPhone Duo, folded first, then unfolded, each its own layout. Follow skill `ios-apps`, section Mockups: native controls, system font, safe areas, 44pt targets; run `python3 ~/.claude/lint/check_ios_mockup.py <mockup>` before you report. Never wait for or boot a simulator: read Apple's pages on the web and be directionally accurate. Map `--bn-*` colours onto a native look; light and dark.

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/phone-find-informed-1.html and docs/design/phone-find-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/phone-find-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
