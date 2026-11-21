Designer kind: informed
Blind designers: 1
Designer: phone-pull-informed-1

## Screen
First design pass of a native iPhone app for Banchi. No iPhone app exists yet; this run is the first look. Its jobs, from an audit: pull owed cards at the shelf with photo check and mark sold (today's `#/fulfillment`, the one web screen already built for touch); walk the boxes for orders (`#/orders` walk); find a card and sell or move one copy (`#/inventory`); add a graded slab by scanning its cert with the camera (`#/slabs`); a read-only glance at shipping lanes, Home and Sales. Mac-only, not in the app: Capture, Review, Pricing and send, Identify, Kit.
Live demo: https://shivinate7.github.io/banchi/ (take your own shots at 375 wide). Shots at 820/1440: /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/fulfillment-*.png, /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/orders-walk-*.png, /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/inventory-*.png. Read docs/DESIGN.md (Fulfillment and the `--bn-*` tokens), docs/specs/capture-app.md (Fulfillment sections), docs/debts/ DEBT76 and DEBT77 (the phone view), and docs/specs/lean-server.md section 7 (the store lives on the Mac, reached over the home network; writes are origin-checked). One section at a time.

## Pain points to fix, largest first
1. Today's pull list shows every copy with its own Pull and never says how many to pull.
2. A pull is a very long scroll; nothing groups cards by buyer envelope; unlocated cards are a warning with no action.
3. Counts of the same work differ between screens.

## Cover
App structure (tabs), the pull flow end to end, one card's photo check, mark sold, a short or unlocated card, find a card, the slab cert scan, and the state when the Mac is out of reach.

## Device
iPhone Duo, folded first, then unfolded, each its own layout. Follow skill `ios-apps`, section Mockups: read the Apple pages it names, native controls, system font, safe areas, 44pt targets, and run `python3 ~/.claude/lint/check_ios_mockup.py <mockup>` before you report. Map `--bn-*` colours onto a native look; light and dark.

## Deliver
Interactive HTML: each tap, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/phone-pull-informed-1.html and docs/design/phone-pull-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push your branch `design-mock/phone-pull-informed-1`. The repo is public: made-up names and cards only. Report in 20 lines or fewer: files, branch, check result, and the one idea that matters most.
