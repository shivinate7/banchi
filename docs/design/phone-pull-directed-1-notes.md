# Phone pull, directed designer 1: notes

Designer kind: directed. Direction: camera check: the phone confirms the card in hand by pointing at it.
Mockup: `docs/design/phone-pull-directed-1.html`. Sample data only: every name, card, buyer and price is made up.
Each option below has a Hide button on the page. Each item says what it is, the gain, the loss and the pick.

## The idea

The phone holds the owed card's stored photo. The picker holds the real card up to the camera. The camera reads
the name and the printed number, and the reticle snaps green when both match. Only then does Mark It Sold
appear. The picker never compares a photo to a card by eye unless the camera cannot read it.

## Items

1. **Check Card replaces Pull as the first step.** Today `Fulfillment.actionFor` shows `Pull`, then "Pulled." and
   `Mark it sold` below it. Here the first step is pointing the camera; the match is the confirm.
   Gain: the check is real, not a tap. A wrong card cannot be sold. Loss: one camera step per card; glare and
   sleeves can block a read (item 4). Pick: yes. Departs from: `Fulfillment.actionFor` (Pull is a press today).
   Owner grant: yes.
2. **The match is the displacement guard.** DESIGN.md "Two-step pull" stops a double tap from selling an unseen card.
   Here Mark It Sold appears only after the camera holds a match, which needs the card in front of the lens, so a
   double tap cannot reach it. On the By Eye path the two steps stay exactly as today (`It Matches`, then
   "Pulled." with Mark It Sold below). Gain: same safety, fewer presses. Loss: the "Two-step pull" test in
   `app/tests/fulfillment.spec.ts` would need a new form for a native app. Pick: yes. Owner grant: yes.
3. **The camera reads name and number only. Finish and condition stay a human check.** The match panel says
   "Check by eye: Foil, Near Mint". Gain: no guessed variant (CLAUDE.md "Never guess an identification, a
   variant or a price"). Loss: one glance still needed for foil cards. Pick: yes.
4. **Can't read: Compare by Eye.** Glare or a sleeve gives "Can't read the number" with Compare by Eye, which is
   today's flow: the stored photo at 320 pt or wider (DESIGN.md `PHOTO_FLOOR`) and the two steps.
   Pick: yes. Keeps behaviour.
5. **Wrong card: Pull This One Instead** (option, hideable). When the camera reads another owed card, it names
   it and its place, and offers to pull it instead. Gain: no lost motion when the picker grabs a neighbour.
   Loss: the walk order breaks for one card. Pick: show it; owner culls.
6. **One count, said one way.** Pull, its header and the Today tile all say "N cards left", where N is the sum of
   `Owed.wanted` minus copies sold here (`Fulfillment.owedFrom`). Cards not in a box are counted apart.
   Gain: fixes pain point 3. Loss: none. Pick: yes. Owner grant: yes (it sets the one count for every screen).
7. **Each card row says how many to pull.** A row is one card with a "x2" pill, not one row per copy. The card
   screen lists each copy's place and its buyer, with a step number. Gain: fixes pain point 1. Loss: a copy is
   one tap deeper. Pick: yes. Departs from: `CardLocations` (one action per copy). Owner grant: yes.
8. **By Box or By Envelope** (option, hideable). A segmented control switches the list between box-walk order
   (default, today's order) and one group per buyer's envelope. This folds the web Orders walk into Pull.
   Gain: fixes pain point 2 and ends a second screen with its own count. Loss: two orders to learn.
   Pick: show it. Departs from: `#/orders` walk as its own screen. Owner grant: yes.
9. **Every copy says which envelope it goes in.** The card screen and the receipt name the buyer
   ("Into Mara Quill's envelope"). Gain: the pile sorts itself as it is pulled. Pick: yes.
10. **Not in a Box gets actions** (option, hideable). Today the screen shows "N unlocated" and "Ask for help
    finding them" (`Fulfillment`, the shortfall branch). New: Scan a Loose Copy, Search Every Box, and Ship
    Envelope Short. Ship Short needs a new route that tells the Mac. Gain: no dead end (house rule
    ux-no-dead-end). Loss: a new write. Pick: show it. Owner grant: yes.
11. **Mark It Sold receipt with Undo, no clock.** The newest sale keeps Undo until a newer one replaces it, as
    `Fulfillment`'s `Sale` type says (no clock, rank replaces it). Pick: yes. Keeps behaviour.
12. **Mac out of reach.** A banner says so, with Try Again. The last list stays, marked with its time. The camera
    check still works on the phone. Default: Mark It Sold is off and says why. Option, hideable: Set Aside, Save
    Later holds the sale on the phone until the Mac answers. Gain: the walk goes on. Loss: a queued write that
    the store has not seen (`docs/specs/lean-server.md` section 7: one store, one writer). Pick: show it; I lean
    to the default. Owner grant: yes.
13. **Find by camera** (option, hideable). Find has a search field and a scan button. Pointing at a card lists
    its copies; a copy opens a sheet with Move Copy and Mark It Sold. Pick: show it.
14. **Slab cert scan.** Scan a Slab reads the label code; Card Ladder names the slab; Add Slab saves it. The cert
    number is never drawn (`Slabs.tsx` header comment). Not found keeps `Slabs.tsx`'s wording and offers Type
    the Cert Number. Pick: yes.
15. **Today tab, read only.** Names only what is not normal (house rule ux-all-is-well), then Pull, Shipping and
    Sales. Pricing and sending stay on the Mac.
16. **Tabs: Pull, Find, Slabs, Today.** Four, floating, navigation only (tab-bars page). The camera is an action
    inside a tab, never a tab.
17. **Unfolded is its own layout.** List beside detail. The stored photo sits beside the live camera, so the
    picker sees both at once. By Eye hides the list so the photo keeps 320 pt.
18. **Colour.** `--bn-*` tokens in both themes. The camera is a stage, dark in both themes (`--bn-stage-*`).
    Vermilion marks only the live camera dot (`--bn-live`'s one job). Indigo marks Mark It Sold; green marks
    only a match. Body text in Pull is 20 pt (Title 3), the place is 34 pt (Large Title): DESIGN.md
    `BODY_FLOOR` 20 and `PLACE_FLOOR` 32. The main button is 64 pt tall (DESIGN.md, The pull-confirm).

## Sizes

No Duo size is written in `~/.claude/lint/layout.json` (`size: null`). Folded is drawn at 375 x 812 pt, the
brief's width. Unfolded is drawn at 820 x 812 pt, a stand-in. Status bar and home-indicator insets (54 and
34 px) are stand-ins too: no Apple page gives them. Real Duo sizes would change both frames.

## Apple pages read (2026-11-21, each answered 200)

layout, typography (Large (default) table: Large Title 34, Title 1 28, Title 2 22, Title 3 20, Headline 17,
Body 17, Callout 16, Subhead 15, Footnote 13, Caption 1 12, Caption 2 11), accessibility (44x44 pt default
control, 17 pt default text), buttons, sheets (Cancel leading, Done trailing; medium and large detents),
lists-and-tables, tab-bars (floats above content; navigation, not actions), toolbars, camera-control, and the
SwiftUI pages navigationstack, tabview and list. All under `https://developer.apple.com/tutorials/data/`.

## Critique (impeccable, design review only: native platform)

Fixed: the camera banner was unreadable on the dark stage; Mark It Sold was green in the camera and indigo
elsewhere (now indigo everywhere); By Eye drew the photo under 320 pt; the unfolded Today repeated its tiles;
"Open" said nothing about what opens. Open: envelope rows wrap the place to two lines on the folded width.
