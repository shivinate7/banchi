Designer kind: directed
Blind designers: 1
Designer: capture-directed-1
Direction: heads-up at pace: one glance from across the rig tells the owner it is fine

## Screen
Capture (route `#/capture`, `app/src/Capture.tsx`; run `make orient ARGS=app/src/Capture.tsx`). The owner photographs each card as a dispenser drops it under a 4K camera, picking box and section first; 802 cards in 37 minutes. Read docs/specs/capture-app.md section 2, docs/specs/dispenser.md, docs/specs/subbox-capture.md, docs/specs/term-audit.md item 2.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: capture-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. Four panels, nine one-letter keys.
2. Words like 'Stack', 'Rig', 'Set Hint Needed', 'Background Match' and 'Tuning'.
3. The free reader has 11 names.

## Cover
setup (box, section), the live feed at pace, a section divider, undo, a jam or misread, and the end of a sitting.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/capture-directed-1.html and docs/design/capture-directed-1-notes.md, and print your designer kind and direction on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/capture-directed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
