Designer kind: blind
Designer: review-blind-1

## Job
The owner photographs thousands of cards, and a reader names most of them. For the doubtful ones, the owner must answer which exact printing the card is, one card at a time, for hours, at a desk with a keyboard. They also start a paid reading of a batch of photos now and then, which costs money. Done looks like: every doubtful card has an answer, nothing was guessed, and the owner knows what each paid read cost and found.

Things the job handles:
- A batch is a box of 545 to 732 photos; 1 to 100 cards per sitting; about 46 sittings on record.
- A doubtful card has its photo and 2 to 8 candidate printings, each with its own image, set, number and market price.
- Reasons a card is doubtful: about 19 kinds (for example two printings look the same, the set symbol is unreadable).
- The paid read costs real money per card; the owner must see the cost before starting it.
- The owner will click through every concept: each press, sheet, state and step works in the page. Use made-up names and cards only. Drawings only: build nothing, open no pull request, commit and push after each pass to the branch `design-mock/review-blind-1`.

## Device
desktop width: 1440. Then 820 (a tablet or narrow window). Light and dark themes. Pointer at 1440; touch at 820.

## House rules
Read `~/.claude/docs/design/principles.md`, `~/.claude/docs/design/layout.md` and `~/.claude/docs/design/tokens.md`. Take type, spacing and colour from `tokens.md`, and where it gives no value, choose your own. Use no colour, font or spacing of any product or repo. Read no other file in `~/.claude/docs/design/` (`repo-colours.json` holds each repo's brand colour) and no token, style or design file in the repo. A repo name in a house file is a credit, not a place to look.

## Deliver
Start from the job, not from a product you know. You see no current screen, on purpose. Draw at least two concepts that answer the job at the root, each with its own structure, its own way to move around and its own first screen. Make one concept deliberately bold: a structure that no common app of this kind uses. Write `<designer>.html` and `<designer>-notes.md` in the design folder, where `<designer>` is the value of the Designer line. Read no other file in the design folder.
