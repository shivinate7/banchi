Designer kind: informed
Blind designers: 1
Designer: counts-informed-1

## Screen
Cross-screen: the counts on Home (`app/src/Home.tsx`), Orders (`Orders.HEADLINE_LABELS`), Cards to Pull (`Fulfillment` totalWanted/shortfallCount) and Pricing. Read docs/specs/term-audit.md. Draw Home plus the headline strip of each of those screens with one shared vocabulary.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: home-*.png, orders-*.png, fulfillment-*.png, pricing-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Home: 75, '256 owed, 164 unfilled'. Orders: 74 buyers, 92 to pick, 164 not in boxes. Cards to Pull: 74 Left, 176 unlocated. Pricing: '64 copies ready' vs '18 ready' on Home vs '18 SKUs, 92 Live Copies' on send.
2. Each counts a different thing under a different word, and no screen says which.

## Cover
Home and each screen's headline, a 'what does this count' popover, and a glossary view.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/counts-informed-1.html and docs/design/counts-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/counts-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
