Designer kind: directed
Blind designers: 1
Designer: phone-slabs-directed-1
Direction: the camera is the home screen: open the app and it is already reading a cert

## Screen
Slabs (`#/slabs`, SlabSheet) as a native iPhone flow: add a graded slab by pointing the camera at its cert label, see the ledger and each slab's value. Read docs/specs/my-slabs.md and docs/specs/lean-server.md section 7 (a plain-http page loses the camera; a native app keeps it).
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: slabs-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Adding one means typing a cert number and picking a grader.

## Cover
the ledger, scanning a cert, the confirm sheet with grade and value, a failed scan, and a slab's detail.

## Device
iPhone Duo, folded first, then unfolded, each its own layout. Follow skill `ios-apps`, section Mockups: native controls, system font, safe areas, 44pt targets; run `python3 ~/.claude/lint/check_ios_mockup.py <mockup>` before you report. Never wait for or boot a simulator: read Apple's pages on the web and be directionally accurate. Map `--bn-*` colours onto a native look; light and dark.

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/phone-slabs-directed-1.html and docs/design/phone-slabs-directed-1-notes.md, and print your designer kind and direction on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/phone-slabs-directed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
