Designer kind: blind
Designer: orders-blind-1

## Job
The owner sees who is owed which cards and then walks the boxes to pick them. At a desk first, then standing at the shelf. They must find out which buyers are owed what, which cards are short, and the walking order through the boxes. Done looks like: every pickable card picked, each short card named, and each copy marked sold.

Things the job handles:
- About 74 open buyers (948 in all), 256 copies owed, 92 to pick over 18 sections on a busy run.
- A card may be owed 2 and have 3 on hand in different boxes; some are short; some can come from either of two printings.
- Each copy has a box, a section and a position number, and a photo.
- The owner will click through every concept: each press, sheet, state and step works in the page. Use made-up names and cards only. Drawings only: build nothing, open no pull request, commit and push after each pass to the branch `design-mock/orders-blind-1`.

## Device
desktop width: 1440. Then 820 (a tablet or narrow window). Light and dark themes. Pointer at 1440; touch at 820.

## House rules
Read `~/.claude/docs/design/principles.md`, `~/.claude/docs/design/layout.md` and `~/.claude/docs/design/tokens.md`. Take type, spacing and colour from `tokens.md`, and where it gives no value, choose your own. Use no colour, font or spacing of any product or repo. Read no other file in `~/.claude/docs/design/` (`repo-colours.json` holds each repo's brand colour) and no token, style or design file in the repo. A repo name in a house file is a credit, not a place to look.

## Deliver
Start from the job, not from a product you know. You see no current screen, on purpose. Draw at least two concepts that answer the job at the root, each with its own structure, its own way to move around and its own first screen. Make one concept deliberately bold: a structure that no common app of this kind uses. Write `<designer>.html` and `<designer>-notes.md` in the design folder, where `<designer>` is the value of the Designer line. Read no other file in the design folder.
