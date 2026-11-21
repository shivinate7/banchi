Designer kind: blind
Designer: pricing-blind-1

## Job
The owner sells trading cards online and must set and send the price of every card they have for sale. They hold nothing; they sit at a desk. They must find out which prices need their eye, which are ready, and what will change when they send. Done looks like: every price they mean to send is sent, the ones they hold back are held on purpose, and they can see what went out.

Things the job handles:
- About 1,100 items for sale, each with a current price, a market price and a suggested price; one item may have several copies.
- On a typical day about 34 need the owner's eye, about 60 copies are ready to go, about 90 prices would move, and about 30 are held back by choice.
- Some items have no market price at all and must be priced by hand.
- Sending changes the live prices buyers see; the owner wants to know exactly what a send will do before it happens.
- The owner will click through every concept: each press, sheet, state and step works in the page. Use made-up names and cards only. Drawings only: build nothing, open no pull request, commit and push after each pass to the branch `design-mock/pricing-blind-1`.

## Device
desktop width: 1440. Then 820 (a tablet or narrow window). Light and dark themes. Pointer at 1440; touch at 820.

## House rules
Read `~/.claude/docs/design/principles.md`, `~/.claude/docs/design/layout.md` and `~/.claude/docs/design/tokens.md`. Take type, spacing and colour from `tokens.md`, and where it gives no value, choose your own. Use no colour, font or spacing of any product or repo. Read no other file in `~/.claude/docs/design/` (`repo-colours.json` holds each repo's brand colour) and no token, style or design file in the repo. A repo name in a house file is a credit, not a place to look.

## Deliver
Start from the job, not from a product you know. You see no current screen, on purpose. Draw at least two concepts that answer the job at the root, each with its own structure, its own way to move around and its own first screen. Make one concept deliberately bold: a structure that no common app of this kind uses. Write `<designer>.html` and `<designer>-notes.md` in the design folder, where `<designer>` is the value of the Designer line. Read no other file in the design folder.
