# Phone pull, blind designer 1: notes

Mockup: `docs/design/phone-pull-blind-1.html`. Designer kind: blind. I saw no current screen,
spec, token file or other mockup. Every name, card, count and spot in the mockup is made up.

The job: a helper who is not technical, phone in one hand, takes the day's owed cards off a shelf
of six long boxes, checks each against the photo of the exact copy, puts it in the buyer's
envelope and marks it sold, and the owner hears which cards could not be found. The owner uses
the same phone to ask "where is this card?" and to sell or move one copy.

Blind run, so there is no "Today:" part and no "Departs from:" line: I cannot know today's
behaviour. Every part is marked "New: the whole flow".

## Devices and sources

- iPhone Duo, folded: drawn at 402 x 874 pt. My choice: `layout.py devices` lists no size for
  this device, and no Apple page gives one.
- iPhone Duo, unfolded: drawn at 780 x 874 pt. My choice, for the same reason.
- I drew the top and bottom safe areas (54 and 34 pt), the status bar and the home bar myself.
  They are drawing values, not Apple figures. The frames also pad with `env(safe-area-inset-*)`.
- Apple pages read 2026-11-21 through the `tutorials/data` JSON, all answered 200: layout,
  typography, accessibility, buttons, sheets, tab-bars, toolbars, lists-and-tables.
  - Type: Dynamic Type at Large (default), from the typography table. Large Title 34/41,
    Title 1 28/34, Title 2 22/28, Title 3 20/25, Headline 17/22, Body 17/22, Subhead 15/20,
    Footnote 13/18, Caption 1 12/16, Caption 2 11/13.
  - Targets: 44 x 44 pt (accessibility, buttons). Minimum text is 11 pt (accessibility).
  - Sheets: Cancel on the leading edge, the confirming act on the trailing edge (sheets).
  - Tab bar for navigation only, at the bottom (tab-bars). Safe areas respected (layout).
- House tokens: 4 px space step, 8 px radius, colour by role, a light and a dark set, the system
  font. The colours are my own, since `tokens.md` gives no colour values. The device frame, the
  tab-bar capsule and the sheet corners use iOS shapes, not the 8 px radius.

## Choices

1. **Concept: Walk.** One route for the whole day, in shelf order. Pull shows one stop at a time,
   with a huge box, spot and section, the photo, and Took it / Can't find it under the thumb.
   At the table, Pack takes the stack off in the same order, and each card names its envelope.
   Unfolded: the route list beside the stop, and the stack beside the four envelopes.
   Gain: the fewest steps along the shelf, and one decision per screen for a helper who should
   never need it explained twice. Loss: it depends on the stack staying in pull order. The
   fallback is "Top card is a different one", which opens a pick list. Two passes, shelf and then
   table. Pick: yes, my first choice.
2. **Concept: Envelopes.** Buyer first: fill one envelope, seal it, take the next. Each card's
   photo-check sheet puts it straight into the envelope and marks it sold.
   Gain: the most familiar model ("fill Theo's envelope"). There is no stack to keep in order,
   and the sale is marked at the moment the card goes in. Loss: more walking on a busy day
   (11 orders) and at the peak (39), because the walk restarts at Box 1 for each envelope.
   Pick: second. It is the strongest fit for a median day of 3 orders of 1 card.
3. **Concept: Shelf map (bold).** The screen is the shelf seen from above. Six columns are the
   boxes, lines are the section dividers, and lit dots are the cards to take. Find lights a
   card's copies on the same map, and the dock at the thumb sells or moves the chosen copy.
   The packing table is its own tab. No common app of this kind uses this structure.
   Gain: the owner's "where is this card?" and the helper's pull are one screen, and position on
   screen matches position on the shelf. Loss: at the peak (39 orders, up to 43 cards each), the
   dots crowd. Two dots closer than 44 pt split left and right, but that does not fix a crowd.
   A count bubble per section would; it is not drawn. Pick: keep as an option. Strong on the
   unfolded table pose.
4. **The press is the photo check.** "Took it" and "In envelope" each mean "this matches the
   photo". There is no separate confirm step. Gain: one press per card. Loss: there is no proof
   that the person looked. Pick: one press. The photo sits beside the button, and a tap enlarges it.
5. **When a card is marked sold.** Walk and Shelf map mark it at "In envelope", at the table.
   Envelopes marks it at the shelf, because the envelope is in hand. Gain: sold means "in the
   envelope" in every concept. Loss: in Walk, cards taken but not yet packed are not sold yet.
   Pick: at the envelope. Owner grant: yes (it sets when a sale is recorded).
6. **Can't find it.** The sheet first says to look two spots either side. If another copy is on
   the shelf, it offers "Take the other copy" with that copy's spot and photo. Otherwise it offers
   "Add to the owner's list". Gain: no dead end, and a spare copy saves the sale. Loss: the
   spare copy may differ in condition from the one the buyer was promised. Pick: offer the spare.
   Owner grant: yes (it changes which copy is sold).
7. **The owner's list.** Owed cards with no known spot are on it from the start and never enter a
   walk. Cards not found join it. It shows as "N for the owner" on every working screen and on the
   done screen. The copy says the owner sees it on the home Mac. That is a new surface, not
   drawn here. Owner grant: yes (a new place where the owner reads it).
8. **Away from the home Mac, two options, both drawn.** (a) `offline`: ticks stay on the phone and
   go home when it answers. (b) `offline-hold`: ticks wait. The act buttons are off, with the
   reason under them. Gain of (a): the walk goes on. Loss of (a): a copy the owner sells
   meanwhile could be sold twice. Pick: (a), with the banner. Owner grant: yes (it changes how a
   sale reaches the records). The page has no per-option hide control: open either state from its link.
9. **First load.** Loading has Stop. A failed read says "Can't reach the home Mac. Join the home
   Wi-Fi, then try again", with Try again, and keeps the machine text in a closed disclosure.
   Empty says "No orders to fill. New orders show here when buyers pay", with Check again. Each
   state is distinct from the others (house rule `ux-unknown-is-not-empty`).
10. **Two copies of one card in two boxes.** The stop says "Theo R. wants 2 of this card. This is
    copy 1; the other is in Box 5." The third copy stays on the shelf. Gain: the helper does not
    take the wrong one twice from one box.
11. **Sell one and Move (owner).** Find lists each copy with its spot and status (owed to a buyer,
    or sold). Sell one asks once ("Mark sold"). Move is a sheet with box, section and spot. Its
    trailing act is "Move". The spot stepper should give a light haptic per step
    (`ux-haptics-feel-substantial`). Each of the two acts shows its answer, with Undo, where it was pressed.
12. **Undo.** Every act that writes (took, in envelope, owner's list, spare, sold, move, seal)
    shows its answer at the press with Undo, until the next act.
13. **Navigation.** Walk: Pull, Pack, Find. Envelopes: Envelopes, Find. Shelf map: Shelf, Table;
    there Find is the map's search field, not a tab. Each tab label is its screen's title.
14. **Colour roles.** Action indigo, envelope manila (each buyer's envelope wears it), done green,
    owner's-list amber, find magenta. Map dots also differ by shape (circle, square, diamond), so
    colour is not the only cue.

## Critique (impeccable, run on this mockup)

Degraded: single context, because this agent has no tool that starts sub-agents. Detector: one
advisory, "repeating-gradient decorative stripes". That is the drawn text lines on the sample
card photo, which stand for content. A false alarm, kept. Score 28/40, Good.

- Fixed: map dots closer than one tap target now split left and right.
- Fixed: the unfolded Shelf map's copy panel sat under an empty gap. It now sits under search.
- Fixed: small photo thumbnails drew a clipped name. They now draw no name.
- Fixed: "Owed to Sam K.." and "Goes to June P.." double full stops.
- Open: a crowded map at the peak needs a count bubble per section (choice 3).
- Open: Walk depends on stack order (choice 1).
- Open: "N for the owner" sits at the top, outside the thumb zone. It is a secondary act.
