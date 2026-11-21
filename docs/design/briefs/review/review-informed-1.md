Designer kind: informed
Blind designers: 1
Designer: review-informed-1

## Screen
Review (route `#/review`, `app/src/Review.tsx`; run `make orient ARGS=app/src/Review.tsx`), and its runs sheet with the Identify composer (RunsComposer, RunPanel). Read docs/specs/capture-app.md (review sections), docs/DESIGN.md section 'The review queue', docs/specs/term-audit.md items 3 and 8. The demo cannot show the question card: read the code for it.
Live demo: https://shivinate7.github.io/banchi/ . Screenshots already taken in /private/tmp/claude-501/-Users-shivinate-Developer-banchi/e3381887-beb3-49b4-a5fe-098ebd7169ad/scratchpad/shots/: review-*.png. Read one section at a time.

## Pain points to fix, largest first (from an audit)
1. The one press that spends money is four layers deep: an unlabeled clock icon, a sheet of 46 runs (most read 'This run has no box on record. Written'), Identify, then a 3-step dialog.
2. 'Hover a bar to see its steps' fails on touch.
3. The question card's four count labels name pipeline steps ('Waiting for a Paid Look', 'Not Looked at Yet'), not the words the owner uses for them.

## Cover
the question card with its candidates and keyboard flow, the counts header, the history of sittings, starting a paid read with its cost, a read in progress, and its result.

## Device
1440, then 820. Light and dark. `--bn-*` tokens only (docs/DESIGN.md).

## Deliver
Interactive HTML: each press, sheet, state and step works, with hash deep links per state, so the owner can click through and pick. Write docs/design/review-informed-1.html and docs/design/review-informed-1-notes.md, and print your designer kind on the page. Load `frontend-design` first. Mockups only: the owner has not ruled on any of this, so build nothing, change no product code, open no pull request. Commit and push branch `design-mock/review-informed-1` after each pass. The repo is public: made-up names and cards only, never a buyer name from the demo. Report in 20 lines or fewer: files, branch, and the one idea that matters most.
