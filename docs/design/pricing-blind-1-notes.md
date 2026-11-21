# Pricing, blind designer 1: notes

Designer kind: blind. I saw no current screen, spec, tokens or other mockup. Every part of
`pricing-blind-1.html` is new, so the mockup carries no "Today:" label. The "Part labels" press
in the mockup bar outlines each new part with a dashed "New: <part>" tag.

The job: about 1,100 cards for sale. The owner finds what needs an eye, sends what is ready,
holds back on purpose, and sees what went out. Sample data hits the brief's day: 34 need an eye
(9 with no market price), 60 copies ready on 48 cards, 90 prices would move, 30 held.

Deep links: `#c=desk|band|manifest`, `&s=loaded|loading|error|empty|sending|sent`,
`&t=light|dark`, `&w=1440|820`, `&p=eye|ready|held|sent` (Desk pile), `&h=<concept>` hides a
concept, `&labels=1` shows part labels. Each concept tab has a × that hides that concept.

## 1. Desk (concept)

What: three columns. Piles on the left (Needs your eye, Ready to send, Held back, Sent). One card
at a time in the middle, with live, market and suggested price side by side. The send on the
right, always in view. Keys: Enter uses the suggestion, P types a price, H holds, J and K move.
At 820 the piles become a row of tabs and the send becomes a bar at the bottom.
Focus: `#desk-focus`.
Gain: the fastest route through 34 cards; the send total is never out of sight.
Loss: the owner sees one card at a time, so a pattern across cards (a whole set dropped) is hard
to see. The most common structure of the three.
Pick: keep, as the safe concept.

## 2. Band (concept, the bold one)

What: the owner sets a rule, not 90 prices. Every proposed move is a dot on one line from
down 60% to up 60%. Two handles set a band; a move inside the band sends without a look. Dots
outside are rings that need an eye. Cards with no market price stack in a gutter to the left.
Held cards sit on a shelf below. A sentence over the chart says the rule in words, and the
figures under it change as the handles move. Press a dot to open the card on the right.
Focus: `#band-chart`.
Gain: one drag answers "which prices need me" for the whole stock, and a set-wide drop shows as
a cluster. The rule carries to the next day.
Loss: a new idea to learn. Dots are small targets; at 820 they grow to 20 px and the bins widen
to 5%. A screen reader walks dots with the arrow keys, which is slower than a list.
Pick: keep. This is the concept I would push furthest.

## 3. Manifest (concept)

What: the first screen is the send itself, written as a document: Waiting for your price (blank
lines to fill), Going up, Going down, Held back on purpose, Not changing. A line at the foot
gives the totals and the Send press. Past sends sit in a rail on the left, each one the same
document, read-only. At 820 the rail folds into a menu.
Focus: `#manifest-doc`.
Gain: "what will this send do" and "what went out" are the same page, so the owner reads one
shape for both.
Loss: 34 blank lines with four controls each are a long form. Slower than Desk for a big day.
Pick: keep.

## 4. Send is always previewed

What: in every concept, Send opens a sheet that lists each change, the totals up and down, and
what stays put (held, not looked at). A line whose price moves by more than half is tagged.
Gain: the owner sees exactly what buyers will see before it happens.
Loss: one more press per send.
Pick: keep.

## 5. Send runs with Stop, and Undo send

What: the send shows "23 of 60 copies" with a Stop press. Stop keeps what was sent and offers
"Send the other 37". After a send, Undo send puts the old prices back; only the latest send can
be undone.
Gain: no send is a one-way door.
Loss: Undo needs the old prices kept per send.
Pick: keep. Owner grant: yes, because it promises a capability (undo of a live price change)
that the product may not have.

## 6. Cards not looked at keep their price

What: a send never includes a card that still needs an eye. The send sheet and the totals say
how many stay at their live price.
Gain: nothing goes out unseen, and nothing blocks the send.
Loss: a card can sit unpriced for days; the pile count is the only nudge.
Pick: keep.

## 7. Held back needs a press, and says why

What: Hold back is its own press; a held card keeps its price until Release. Held cards show
their reason, or "No reason given".
Gain: every hold is on purpose, as the job asks.
Loss: none seen.
Pick: keep.

## 8. Floor and thin market flag a card

What: a suggestion below a $0.25 floor, or a market price that rests on one sale, sends the card
to Needs your eye even when the move is small.
Gain: the two quiet ways a suggestion goes wrong get an eye.
Loss: the floor value and the one-sale rule are my own sample rules.
Pick: keep. Owner grant: yes, because both rules are invented here and need the owner's values.

## 9. Unknown is not zero

What: while market prices load or fail, pile counts show a dash, and the send press is off with
its reason on hover. A failed load says nothing was sent, offers Try again, and hides the
server's words behind "What the server said".
Pick: keep.

## Sizes and themes

Each concept draws at 1440 (pointer) and 820 (touch, 44 px targets, keys hidden), light and
dark. 820 is the brief's size; no device list exists for this repo (`layout.py devices` printed
"unknown"). Colours, type and spacing are my own, on the house 4 px step and 8 px radius.

## Critique (impeccable, single-context)

Detector: no findings. Fixed: band dots too small for touch at 820; band chart had one tab stop
per dot (now one stop, arrow keys walk the dots); band handles sat off the band edges; edge
axis labels wrapped. Open: Manifest's blank lines are a long form on a big day (item 3, Loss).
